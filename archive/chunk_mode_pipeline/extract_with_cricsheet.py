#!/usr/bin/env python3
"""Pattern A — Cricsheet-anchored Gemini extraction (technique-only).

Sends one video clip + a JSON list of ground-truth ball deliveries
(from Cricsheet) to Gemini, asks it to ONLY fill in technique fields
(shot_type, line, length, footwork, contact, swing, bowler_crease, etc.)
without modifying any of the WHO/WHAT/RUNS fields.

Usage:
    python features/ball_extraction/extract_with_cricsheet.py \\
        --clip data/video_clips_T20-IndvsEng-IndBat/T20-IndvsEng-IndBat_chunk_001.mp4 \\
        --cricsheet-json data/cricsheet/IndvsEng/india_innings.json \\
        --over-range 0-2 \\
        --model gemini-3.1-pro-preview \\
        --out data/IndvsEng_chunk1_with_cricsheet.json

Output JSON shape: list of records with WHO/WHAT/RUNS copied from the
input + technique fields populated from Gemini.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()


def parse_over_range(s: str) -> tuple[int, int]:
    if "-" not in s:
        n = int(s)
        return n, n
    a, b = s.split("-", 1)
    return int(a), int(b)


def call_gemini_technique(
    clip_path: str,
    cricsheet_balls: list[dict],
    model_name: str,
    commentary_by_ball: dict | None = None,
) -> list[dict]:
    """Upload clip to Gemini and ask for technique fields per ball."""
    from google import genai
    from google.genai import types

    from src.intelligence.prompt_technique_only import (
        TECHNIQUE_SYSTEM_PROMPT, build_technique_prompt,
    )
    from src.intelligence.schema import GEMINI_JSON_SCHEMA

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing from env / .env")

    prompt = build_technique_prompt(cricsheet_balls, commentary_by_ball=commentary_by_ball)
    print(f"  prompt length: {len(prompt)} chars / {prompt.count(chr(10))+1} lines")

    client = genai.Client(api_key=api_key)
    print(f"  uploading {clip_path} ({Path(clip_path).stat().st_size / 1e6:.1f} MB)...")
    uploaded = client.files.upload(file=clip_path)
    while uploaded.state == "PROCESSING":
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)
    if uploaded.state == "FAILED":
        raise RuntimeError(f"Gemini upload FAILED for {clip_path}")

    batch_schema = {"type": "array", "items": GEMINI_JSON_SCHEMA}

    print(f"  calling {model_name}...")
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
                    types.Part.from_text(text=prompt),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=TECHNIQUE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=batch_schema,
            temperature=0.1,
        ),
    )

    try:
        client.files.delete(name=uploaded.name)
    except Exception:
        pass

    raw = json.loads(response.text)
    if not isinstance(raw, list):
        raw = [raw]
    return raw


def merge_cricsheet_into_gemini(cricsheet_balls: list[dict], gemini_records: list[dict]) -> list[dict]:
    """Stitch Gemini's technique fields onto Cricsheet's ground-truth balls.

    Joins by ball_id when possible, falls back to positional join. Cricsheet
    fields ALWAYS win for WHO/WHAT/RUNS — Gemini's claims for those are
    discarded since the prompt told it not to change them.
    """
    by_id = {g.get("ball_id"): g for g in gemini_records if g.get("ball_id")}
    out = []
    for i, cs in enumerate(cricsheet_balls):
        gem = by_id.get(cs["ball_id"]) or (gemini_records[i] if i < len(gemini_records) else {})
        merged = dict(cs)  # start from Cricsheet (ground truth wins)
        # Overlay only the technique fields from Gemini
        TECH_FIELDS = (
            "bowler_type", "line", "length", "variation", "movement",
            "swing_direction", "swing_type", "spin_direction",
            "bowler_crease", "bowling_speed_kmph", "ball_age_phase",
            "shot_type", "footwork", "contact_quality", "edge_type",
            "shot_direction", "batsman_handedness", "confidence",
            "raw_description",
        )
        for f in TECH_FIELDS:
            if f in gem:
                merged[f] = gem[f]
        merged["_gemini_emitted"] = bool(gem)
        out.append(merged)
    return out


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--clip", required=True, help="Path to video clip (e.g. chunk_001.mp4)")
    p.add_argument("--cricsheet-json", required=True, help="Path to innings JSON (from export_cricsheet_innings.py)")
    p.add_argument("--over-range", required=True, help="Inclusive 0-indexed over range, e.g. '0-2' for first three overs")
    p.add_argument("--model", default="gemini-3.1-pro-preview")
    p.add_argument("--out", required=True, help="Output merged JSON path")
    p.add_argument("--whisper-transcript", default=None, help="Optional Whisper transcript JSON (from features/audio_pipeline/transcribe.py)")
    p.add_argument("--chunk-offset-sec", type=float, default=0.0, help="When using a Whisper transcript, where this clip starts in the source video")
    p.add_argument("--chunk-duration-sec", type=float, default=600.0, help="Clip duration for commentary alignment (default 600s = 10min)")
    p.add_argument("--espn-commentary", default=None, help="Optional ESPNCricinfo commentary JSON (from features/audio_pipeline/parse_espn_pdf.py). Preferred over Whisper when available.")
    args = p.parse_args()

    from src.intelligence.cricsheet import balls_in_range

    cs_payload = json.loads(Path(args.cricsheet_json).read_text())
    all_balls = cs_payload.get("balls", cs_payload if isinstance(cs_payload, list) else [])
    over_min, over_max = parse_over_range(args.over_range)
    relevant = balls_in_range(all_balls, over_min, over_max, legal_only=True)
    print(f"Filtered Cricsheet to overs {over_min}-{over_max}: {len(relevant)} legal balls")
    if not relevant:
        print("✗ No Cricsheet balls in that range — aborting.")
        sys.exit(1)

    commentary_by_ball = None
    if args.espn_commentary:
        # PREFER ESPN — analyst-curated per-ball text, much cleaner than Whisper
        from src.intelligence.espn_commentary import load_espn_commentary, build_commentary_by_ball
        espn_balls = load_espn_commentary(args.espn_commentary)
        # Pass the FULL innings of cricsheet balls (not just the range) so the
        # legal-ball position numbering is computed correctly per over.
        all_balls = cs_payload.get("balls", cs_payload if isinstance(cs_payload, list) else [])
        commentary_by_ball = build_commentary_by_ball(espn_balls, all_balls)
        aligned = sum(1 for b in relevant if commentary_by_ball.get(b["ball_id"]))
        print(f"  ESPN commentary aligned for {aligned}/{len(relevant)} balls")
    elif args.whisper_transcript:
        from src.intelligence.commentary import load_transcript, commentary_for_chunk
        transcript = load_transcript(args.whisper_transcript)
        commentary_by_ball = commentary_for_chunk(
            transcript,
            chunk_offset_sec=args.chunk_offset_sec,
            chunk_duration_sec=args.chunk_duration_sec,
            cricsheet_balls=relevant,
        )
        aligned = sum(1 for v in commentary_by_ball.values() if v)
        print(f"  Whisper commentary aligned for {aligned}/{len(relevant)} balls")

    gemini_records = call_gemini_technique(args.clip, relevant, args.model, commentary_by_ball=commentary_by_ball)
    print(f"  ✓ Gemini returned {len(gemini_records)} record(s)")
    if len(gemini_records) != len(relevant):
        print(f"  ⚠ count mismatch — expected {len(relevant)}, got {len(gemini_records)}")

    merged = merge_cricsheet_into_gemini(relevant, gemini_records)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2))
    print(f"✓ Wrote {len(merged)} merged records → {out_path}")

    # Quick technique-fill summary
    filled = sum(1 for m in merged if m.get("shot_type") and m["shot_type"] != "unknown")
    print(f"  Technique filled (shot_type != unknown): {filled}/{len(merged)}")


if __name__ == "__main__":
    main()
