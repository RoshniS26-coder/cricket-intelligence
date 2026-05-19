"""
Phase 2 of the two-phase ball-extraction workflow.

Reads the manifest produced by Phase 1 (segment_video.py), sends each clip
to Gemini with BATCH_EXTRACTION_PROMPT, writes:
  - One JSON per clip (preserves per-chunk raw output for debugging)
  - One merged JSON across all clips (cross-clip dedup on (over, ball_number),
    highest-confidence version wins)
  - One transitions JSONL with every record's chunk provenance

NO DATABASE WRITE. Output is JSON only — you inspect the merged file, then
import to DB as a separate step when you're satisfied with quality.

Usage:
    python features/ball_extraction/extract_balls_from_clips.py \\
        --manifest data/video_clips_T20-IndvsEng-IndBat/manifest.json \\
        --model gemini-2.5-pro \\
        --out-dir data/over-time-stamps-json-segment/T20-IndvsEng-IndBat-balls

Pre-req: GEMINI_API_KEY in .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


# ─────────────────────────────────────────────────────────────────────────────
#  Per-clip Gemini call
# ─────────────────────────────────────────────────────────────────────────────

def extract_balls_from_one_clip(
    clip_path: str,
    chunk_offset_sec: float,
    chunk_index: int,
    model_name: str = "gemini-3.1-pro-preview",
) -> list[dict[str, Any]]:
    """Call Gemini on one clip with BATCH_EXTRACTION_PROMPT and return the
    parsed per-ball dicts. Absolute timestamps are computed by adding
    chunk_offset_sec to Gemini's clip-relative start_sec/end_sec.

    Returns an empty list on any failure; caller decides whether to retry.
    """
    from google import genai
    from google.genai import types

    from src.intelligence.prompt import (
        BATCH_EXTRACTION_PROMPT, SYSTEM_PROMPT,
    )
    from src.intelligence.schema import GEMINI_JSON_SCHEMA

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment or .env.")

    client = genai.Client(api_key=api_key)

    try:
        uploaded = client.files.upload(file=clip_path)
        # Wait for processing
        while uploaded.state == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        if uploaded.state == "FAILED":
            console.print(f"  [red]✗[/red] Gemini upload failed for chunk {chunk_index}")
            return []

        batch_schema = {"type": "array", "items": GEMINI_JSON_SCHEMA}

        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(
                            file_uri=uploaded.uri,
                            mime_type=uploaded.mime_type,
                        ),
                        types.Part.from_text(text=BATCH_EXTRACTION_PROMPT),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=batch_schema,
                temperature=0.2,
            ),
        )

        try:
            raw_list = json.loads(response.text)
            if not isinstance(raw_list, list):
                raw_list = [raw_list]
        except Exception as e:
            console.print(
                f"  [yellow]⚠[/yellow] chunk {chunk_index}: failed to parse Gemini JSON: {e}"
            )
            return []

        # Tag each record with chunk provenance + convert timestamps to absolute
        tagged: list[dict[str, Any]] = []
        for rec in raw_list:
            rec["_chunk_index"] = chunk_index
            start_rel = rec.get("start_sec")
            end_rel = rec.get("end_sec")
            if isinstance(start_rel, (int, float)):
                rec["abs_start_sec"] = round(chunk_offset_sec + float(start_rel), 2)
            if isinstance(end_rel, (int, float)):
                rec["abs_end_sec"] = round(chunk_offset_sec + float(end_rel), 2)
            tagged.append(rec)

        # Cleanup uploaded file (non-critical)
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass

        return tagged

    except Exception as e:
        err = str(e)
        console.print(f"  [red]✗[/red] chunk {chunk_index} Gemini call failed: {err[:200]}")
        if "PERMISSION_DENIED" in err or "401" in err or "403" in err:
            raise RuntimeError("Gemini API key invalid or revoked") from e
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  Cross-clip merge (highest-confidence wins per over.ball)
# ─────────────────────────────────────────────────────────────────────────────

def _record_avg_confidence(rec: dict[str, Any]) -> float:
    """Average across the key confidence fields. Records lacking a confidence
    dict are treated as 0 so the merge prefers ones that DO have confidence
    scores."""
    conf = rec.get("confidence") or {}
    if not isinstance(conf, dict) or not conf:
        return 0.0
    # Prioritise the scoreboard-related fields plus line/length/shot, which
    # determine whether the record is trustworthy.
    keys = ("line", "length", "shot_type", "outcome", "contact_quality")
    vals = [conf.get(k) for k in keys if isinstance(conf.get(k), (int, float))]
    if not vals:
        # Fall back to average of all numeric confidence values
        vals = [v for v in conf.values() if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else 0.0


def merge_records_across_clips(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Dedup records by (over, ball_number, innings); keep the highest-
    confidence version.

    Returns (merged, stats).

    Records with over=0 AND ball_number=0 (no scoreboard read) are kept
    separately and appended at the end with sequential synthetic IDs so they
    aren't silently lost.
    """
    by_key: dict[tuple[int, int, int], dict[str, Any]] = {}
    unscored: list[dict[str, Any]] = []

    for rec in records:
        over = rec.get("over", 0)
        ball = rec.get("ball_number", 0)
        innings = rec.get("innings", 1)
        if not over and not ball:
            unscored.append(rec)
            continue
        key = (int(over), int(ball), int(innings))
        if key in by_key:
            existing = by_key[key]
            if _record_avg_confidence(rec) > _record_avg_confidence(existing):
                by_key[key] = rec
        else:
            by_key[key] = rec

    # Sort merged records by (innings, over, ball)
    merged = sorted(by_key.values(), key=lambda r: (
        int(r.get("innings", 1)),
        int(r.get("over", 0)),
        int(r.get("ball_number", 0)),
    ))

    # Append unscored records at the end (sorted by abs_start_sec if available)
    unscored.sort(key=lambda r: r.get("abs_start_sec", 0) or 0)
    merged.extend(unscored)

    stats = {
        "total_raw_records":      len(records),
        "unique_scored_balls":    len(by_key),
        "unscored_records":       len(unscored),
        "total_after_merge":      len(merged),
    }
    return merged, stats


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2: Gemini ball extraction per pre-cut clip (JSON only, no DB write).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Path to manifest.json produced by segment_video.py")
    parser.add_argument("--model", default="gemini-3.1-pro-preview",
                        help="Gemini model (default: gemini-3.1-pro-preview). Override with e.g. gemini-2.5-pro if the preview model isn't available in your region.")
    parser.add_argument("--max-clips", type=int, default=0,
                        help="Stop after N clips (default: 0 = all). Useful for quick test runs.")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Where to write per-clip + merged JSON (default: alongside manifest)")
    parser.add_argument("--sleep-between-clips", type=float, default=1.0,
                        help="Seconds to sleep between Gemini calls to be kind to the API (default: 1.0)")
    parser.add_argument("--merge", action="store_true",
                        help="Run cross-clip dedup at the end (writes merged_balls.json). Off by default — "
                             "inspect per-clip JSONs first to decide on merge strategy, then re-run with --merge "
                             "or call merge_records_across_clips() directly.")
    args = parser.parse_args()

    if not args.manifest.exists():
        console.print(f"[red]✗[/red] Manifest not found: {args.manifest}")
        return 1

    manifest = json.loads(args.manifest.read_text())
    chunks = manifest.get("chunks", [])
    if not chunks:
        console.print(f"[red]✗[/red] Manifest contains no chunks")
        return 1

    # Default output dir: alongside the manifest
    if args.out_dir is None:
        args.out_dir = args.manifest.parent / "balls"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Filter to OK chunks only
    ok_chunks = [c for c in chunks if c.get("status") == "ok"]
    if args.max_clips > 0:
        ok_chunks = ok_chunks[: args.max_clips]

    console.print(
        f"\n[bold cyan]Phase 2 — per-clip ball extraction[/bold cyan]\n"
        f"  manifest         : {args.manifest}\n"
        f"  clips to process : {len(ok_chunks)} / {len(chunks)}\n"
        f"  model            : {args.model}\n"
        f"  out_dir          : {args.out_dir}\n"
    )

    all_records: list[dict[str, Any]] = []
    per_clip_counts: list[tuple[int, int]] = []

    for chunk in ok_chunks:
        idx = chunk["index"]
        offset = chunk["abs_start_sec"]
        clip_path = chunk["path"]
        console.print(
            f"\n[bold]Chunk {idx}/{len(chunks)}[/bold] "
            f"(+{offset:.0f}s, {chunk['length_sec']:.0f}s long, {chunk.get('size_mb', '?')} MB)"
        )

        records = extract_balls_from_one_clip(
            clip_path=clip_path,
            chunk_offset_sec=offset,
            chunk_index=idx,
            model_name=args.model,
        )
        console.print(f"  [green]✓[/green] {len(records)} ball records returned")

        # Save per-clip JSON
        per_clip_out = args.out_dir / f"chunk_{idx:03d}_balls.json"
        per_clip_out.write_text(json.dumps(records, indent=2, default=str))
        console.print(f"  [dim]→ {per_clip_out.relative_to(Path.cwd()) if per_clip_out.is_absolute() else per_clip_out}[/dim]")

        per_clip_counts.append((idx, len(records)))
        all_records.extend(records)

        # Be kind to the API
        if args.sleep_between_clips > 0:
            time.sleep(args.sleep_between_clips)

    # Always write the raw-records JSONL (one line per record, with chunk provenance).
    # This is the artifact you use to inspect what each clip independently produced.
    log_out = args.out_dir / "all_records.jsonl"
    with open(log_out, "w") as f:
        for r in all_records:
            f.write(json.dumps(r, default=str) + "\n")
    console.print(f"\n[green]✓[/green] raw per-clip records (one line/record) → {log_out}")

    # Per-clip yield summary
    console.print(f"\n[bold]Per-clip yield:[/bold]")
    for idx, count in per_clip_counts:
        console.print(f"  chunk {idx:>3}: {count:>3} ball record(s)")
    total_raw = sum(c for _, c in per_clip_counts)
    console.print(f"  [dim]total raw records across all clips: {total_raw}[/dim]")

    # Optional merge — off by default so the user can inspect per-clip JSONs first
    if args.merge:
        console.print(f"\n[bold]Merging across {len(ok_chunks)} clips...[/bold]")
        merged, stats = merge_records_across_clips(all_records)

        console.print(
            f"  raw records across all clips : {stats['total_raw_records']}\n"
            f"  unique scored deliveries     : {stats['unique_scored_balls']}\n"
            f"  unscored (no over.ball read) : {stats['unscored_records']}\n"
            f"  total in merged output       : {stats['total_after_merge']}"
        )

        # Distribution of over.ball coverage
        by_over = Counter(int(r.get("over", 0)) for r in merged if r.get("over"))
        if by_over:
            console.print("\n[bold]Coverage by over:[/bold]")
            for over in sorted(by_over):
                console.print(f"  over {over:>2}: {by_over[over]} ball(s)")

        merged_out = args.out_dir / "merged_balls.json"
        merged_out.write_text(json.dumps(merged, indent=2, default=str))
        console.print(f"\n[green]✓[/green] merged balls → {merged_out}")

    console.print(
        f"\n[bold green]✓ Done.[/bold green]\n"
        f"\nInspect per-clip output:\n"
        f"  ls {args.out_dir}/chunk_*_balls.json\n"
        f"  jq 'length' {args.out_dir}/chunk_001_balls.json     # records in clip 1\n"
        f"  jq -r '.[] | \"\\(.over).\\(.ball_number) \\(.bowler_name) → \\(.batsman_name) \\(.shot_type) \\(.outcome)\"' {args.out_dir}/chunk_001_balls.json\n"
        f"\nInspect all records together (raw, with chunk provenance):\n"
        f"  jq -s 'length' {log_out}     # total raw records\n"
        f"  jq -c 'select(._chunk_index == 1)' {log_out} | head      # all records from clip 1\n"
    )
    if not args.merge:
        console.print(
            f"\n[dim]Merging was skipped. When per-clip output looks right, re-run with --merge\n"
            f"to produce a deduplicated merged_balls.json.[/dim]"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
