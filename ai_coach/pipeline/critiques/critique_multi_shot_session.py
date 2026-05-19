"""
Multi-shot session critique orchestrator.

Pipeline:
  1. Run net-session catalog pre-pass to enumerate all balls + shot types
  2. For each shot type with >= --min-attempts, run a net_session + solo +
     auto-anchored critique
  3. Save combined JSON: {"session_summary": {...}, "shot_critiques": [...]}
  4. Render one multi-page PDF (one section per shot type)

NO --references and NO --coaching-keys required — auto-anchor + Gemini
intrinsic knowledge handle the critiques.

Usage:
    python scripts/critique_multi_shot_session.py \\
        --clip data/raw_videos/aakash-multishot-netpractice.mp4 \\
        --player "Aakash" \\
        --model gemini-3.1-flash-lite-preview \\
        --catalog-model gemini-3.1-flash-lite-preview \\
        --min-attempts 3 \\
        --academy "Net Practice" \\
        --out data/reports/aakash_multi_shot_briefing.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console

from ai_coach.lib.briefing import assemble_briefing
from ai_coach.lib.critique_prompts import resolve_reference_player
from ai_coach.lib.few_shot_critique import critique_against_references
from ai_coach.report.pdf import render_multi_shot_pdf

console = Console()


def run_catalog(clip_path: str, model: str) -> tuple[dict[str, int], dict[str, int], list] | None:
    """Run net-session catalog pre-pass via the shared src helper."""
    from ai_coach.lib.session_catalog import run_session_catalog
    return run_session_catalog(clip_path, model=model, force=False)


def _field_val(r, field: str) -> str:
    """Get a field value from either a Pydantic enum record or a plain DB string record."""
    val = getattr(r, field, None)
    if val is None:
        return "unknown"
    return val.value if hasattr(val, "value") else str(val)


def _aggregate_gemini_per_shot(records: list, shot_value: str) -> dict | None:
    """Aggregate per-ball Gemini fields for one shot type.

    Returns a dict shaped like a single Gemini extraction but with values that
    are summary strings (e.g. 'off_stump (18), outside_off (3)') so the PDF's
    DELIVERY & SHOT section shows the real distribution for THIS shot type
    instead of "Gemini extraction not available."

    Handles both Pydantic enum records (from catalog pre-pass) and plain-string
    BallDBRecord objects (from --from-match-id DB path).
    """
    from collections import Counter
    rs = [r for r in records if _field_val(r, "shot_type") == shot_value]
    if not rs:
        return None

    def top(field: str, n: int = 3) -> str:
        cnt = Counter(_field_val(r, field) for r in rs)
        items = cnt.most_common(n)
        return ", ".join(f"{k} ({v})" for k, v in items) if items else "?"

    n = len(rs)
    line_summary   = top("line", 3)
    length_summary = top("length", 3)
    contact_top    = top("contact_quality", 1)

    return {
        "bowler_type":     top("bowler_type", 2),
        "line":            line_summary,
        "length":          length_summary,
        "variation":       top("variation", 2),
        "shot_type":       f"{shot_value}  ({n} attempts)",
        "footwork":        top("footwork", 2),
        "contact_quality": top("contact_quality", 3),
        "outcome":         top("outcome", 3),
        "movement":        top("movement", 2),
        "bounce_behavior": top("bounce_behavior", 2),
        "swing_direction": top("swing_direction", 2),
        "spin_direction":  top("spin_direction", 2),
        "ball_age_phase":  top("ball_age_phase", 1),
        "raw_description": (
            f"Across {n} {shot_value} attempts: most often "
            f"{line_summary.split(',')[0].strip()} line at "
            f"{length_summary.split(',')[0].strip()} length, "
            f"with {contact_top} as the dominant contact quality."
        ),
    }


def _video_duration_seconds(clip_path: str) -> float | None:
    import subprocess
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", clip_path,
        ], text=True, timeout=10)
        return float(out.strip())
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser(
        description="Multi-shot session critique: identifies all shots played and "
                    "produces a coaching critique per major shot type."
    )
    p.add_argument("--clip", default=None,
                   help="Path to the net session video. Required unless --from-match-id is used.")
    p.add_argument("--player", required=True, help="Player name shown in PDFs.")
    p.add_argument("--academy", default=None, help="Academy name shown in subtitles.")
    p.add_argument("--model", default="gemini-3.1-flash-lite-preview",
                   help="Model used for per-shot critique calls. Default: lite-preview (cheap).")
    p.add_argument("--catalog-model", default="gemini-2.5-pro",
                   help="Model used for catalog pre-pass. Default: pro (best at exhaustive enumeration).")
    p.add_argument("--min-attempts", type=int, default=3,
                   help="Minimum attempts a shot type must have to get its own critique section. "
                        "Default: 3.")
    p.add_argument("--max-shots", type=int, default=None,
                   help="Optional cap on number of shot types to critique (top-N by frequency). "
                        "Default: no cap — every shot type with >= --min-attempts gets its own section. "
                        "Set this only if you want a shorter report (e.g. --max-shots 3 for top 3).")
    p.add_argument("--coaching-keys", default=None,
                   help="Optional comma-separated coaching corpus keys to apply to ALL shots. "
                        "(Per-shot coaching is a Phase-2 enhancement.)")
    p.add_argument("--out", required=True, help="Output PDF path.")
    p.add_argument("--out-json", default=None,
                   help="Optional output path for the combined critiques JSON. "
                        "Defaults to <out>.json")
    p.add_argument("--from-match-id", default=None,
                   help="Skip catalog pre-pass — load ball records directly from DB for this match ID. "
                        "Use when you have already run run_pipeline.py on the video.")
    args = p.parse_args()

    if not args.from_match_id and not args.clip:
        console.print("[red]✗ provide --clip or --from-match-id[/red]")
        return 1
    if args.clip and not Path(args.clip).exists():
        console.print(f"[red]✗ clip not found:[/red] {args.clip}")
        return 1

    console.print()
    console.print(f"[bold cyan]Multi-Shot Session Critique[/bold cyan]")
    console.print(f"  clip:           {args.clip}")
    console.print(f"  player:         {args.player}")
    console.print(f"  catalog model:  {args.catalog_model}")
    console.print(f"  critique model: {args.model}")
    console.print(f"  min attempts:   {args.min_attempts}")
    console.print(f"  max shots:      {args.max_shots if args.max_shots is not None else 'no cap (all eligible)'}")
    console.print()

    # ── Step 1: catalog pre-pass OR load from DB ─────────────────────────────
    if args.from_match_id:
        console.print(
            f"[bold]Step 1/3:[/bold] loading ball records from DB "
            f"(match_id=[cyan]{args.from_match_id}[/cyan]) — skipping Gemini catalog"
        )
        from collections import Counter
        from src.storage.db import CricketDB
        db = CricketDB()
        records = db.get_balls_for_match(args.from_match_id)
        if not records:
            console.print(f"[red]✗ no balls found for match '{args.from_match_id}' in DB[/red]")
            return 1
        shot_counts = dict(Counter(r.shot_type for r in records if r.shot_type))
        contact_counts = dict(Counter(r.contact_quality for r in records if r.contact_quality))
        total = len(records)
        console.print(f"  loaded {total} balls, {len(shot_counts)} shot types from DB")
        for shot, n in sorted(shot_counts.items(), key=lambda kv: -kv[1]):
            marker = "✓" if n >= args.min_attempts else "·"
            console.print(f"    {marker} {shot:25} {n:3d}")
    else:
        console.print("[bold]Step 1/3:[/bold] catalog pre-pass — enumerate all balls + shot types")
        catalog = run_catalog(args.clip, model=args.catalog_model)
        if not catalog:
            console.print("[red]✗ catalog failed or undercounted — aborting[/red]")
            return 1
        shot_counts, contact_counts, records = catalog
        total = sum(shot_counts.values())
        console.print(f"  detected {total} balls, {len(shot_counts)} shot types")
        for shot, n in sorted(shot_counts.items(), key=lambda kv: -kv[1]):
            marker = "✓" if n >= args.min_attempts else "·"
            console.print(f"    {marker} {shot:25} {n:3d}")

    # ── Step 2: pick shot types and run per-shot critiques ────────────────────
    eligible = [(s, n) for s, n in shot_counts.items() if n >= args.min_attempts]
    eligible.sort(key=lambda x: -x[1])
    if args.max_shots is not None:
        eligible = eligible[: args.max_shots]
    if not eligible:
        console.print(
            f"[red]✗ no shot type has ≥{args.min_attempts} attempts — "
            f"lower --min-attempts and retry[/red]"
        )
        return 1
    console.print()
    console.print(f"[bold]Step 2/3:[/bold] running {len(eligible)} per-shot critique(s)")

    # Optional: coaching context (applied to all shots if provided)
    coaching_context = []
    if args.coaching_keys:
        from ai_coach.lib.coaching_loader import load_coaching_context
        keys = [k.strip() for k in args.coaching_keys.split(",") if k.strip()]
        coaching_context = load_coaching_context(keys)

    briefings = []
    shot_critiques_for_json = []
    for shot, n_attempts in eligible:
        anchor = resolve_reference_player(shot, explicit=None, auto_anchor=True)
        anchor_label = anchor or "textbook ideal (no canonical player)"
        console.print(f"\n  [cyan]→[/cyan] {shot} ({n_attempts} attempts)  anchor: {anchor_label}")

        try:
            critique = critique_against_references(
                student_clip=args.clip,
                reference_clips=[],
                shot_type=shot,
                coaching_context=coaching_context or None,
                mode="net_session",
                model=args.model,
                player_name=args.player,
                reference_player=None,        # let resolve_reference_player auto-anchor
                auto_anchor=True,
            )
        except Exception as e:
            console.print(f"  [yellow]⚠ critique failed for {shot}: {e}[/yellow]")
            continue

        shot_critiques_for_json.append({
            "shot_type": shot,
            "n_attempts": n_attempts,
            "anchor_player": anchor,
            "critique": critique,
        })

        # Aggregate Gemini fields across the catalog records for THIS shot.
        # Replaces "Gemini extraction not available" with the real distribution.
        gemini_aggregate = _aggregate_gemini_per_shot(records, shot)

        # Build per-shot PlayerBriefing.
        briefing = assemble_briefing(
            player_name=args.player,
            shot_type=shot,
            clip_path=args.clip,
            gemini=gemini_aggregate,
            pose_features=None,
            critique=critique,
            coaching_context=coaching_context,
            reference_clips=[],
            coaching_keys=keys if args.coaching_keys else [],
            ball_id=f"net_session_{shot}",
            academy=args.academy,
            mode="net_session",
            shot_counts=shot_counts if briefings == [] else None,        # show catalog only on first section
            contact_counts=contact_counts if briefings == [] else None,
        )
        briefings.append(briefing)
        console.print(f"     rating={critique.get('overall_quality_rating')} "
                      f"deviations={len(critique.get('deviations', []) or [])}")

    if not briefings:
        console.print("[red]✗ all per-shot critiques failed — no PDF produced[/red]")
        return 1

    # ── Step 3: save JSON + render multi-section PDF ──────────────────────────
    console.print()
    console.print(f"[bold]Step 3/3:[/bold] save JSON + render multi-section PDF")
    out_json = Path(args.out_json) if args.out_json else Path(args.out).with_suffix(".json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({
        "generated_at":     datetime.now().isoformat(),
        "clip":             args.clip,
        "player":           args.player,
        "session_summary":  {
            "total_balls":     total,
            "shot_counts":     shot_counts,
            "contact_counts":  contact_counts,
        },
        "shot_critiques":   shot_critiques_for_json,
    }, indent=2, ensure_ascii=False))
    console.print(f"  [green]✓[/green] combined JSON → {out_json}")

    pdf_path = render_multi_shot_pdf(briefings, args.out)
    console.print(f"  [green]✓[/green] multi-shot PDF → {pdf_path}")
    console.print()
    console.print(f"  open {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
