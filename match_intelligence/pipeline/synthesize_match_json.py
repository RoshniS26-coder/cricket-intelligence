#!/usr/bin/env python3
"""Text-only synthesis of one match's ball-by-ball JSON.

Inputs:
  --cricsheet-json   Cricsheet innings JSON (anchors WHO/WHAT/RUNS)
  --espn-commentary  ESPN PDF-parsed commentary JSON (primary technique truth)
  --gemini-video-glob  Glob to existing per-chunk Gemini video JSONs
                     (visual-only fields + backup)
  --out              Output unified ball-by-ball JSON

For each over 0..N-1, sends Cricsheet + ESPN + prior-video for the 6 legal
balls to gemini-2.5-pro (TEXT ONLY) and merges the response. Writes
per-over outputs to a resume directory so a partial run can be continued.

Usage:
  python match_intelligence/pipeline/synthesize_match_json.py \\
      --cricsheet-json data/cricsheet/IndvsEng/india_innings.json \\
      --espn-commentary data/espncricinfo/IndvsEng/match_1276906_commentary.json \\
      --gemini-video-glob 'data/IndvsEng_chunk*_with_cricsheet.json' \\
      --out data/IndvsEng_full_match_correct.json \\
      --resume-dir data/IndvsEng_synthesized \\
      --model gemini-2.5-pro
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()


# --- Quality scoring for chunk-record dedup ----------------------------

_TECHNIQUE_FIELDS = (
    "bowler_type", "line", "length", "shot_type", "footwork",
    "contact_quality", "shot_direction", "bowler_crease",
)


def _record_quality(r: dict) -> int:
    """How many of the 8 key technique fields are non-unknown/none."""
    return sum(
        1 for f in _TECHNIQUE_FIELDS
        if r.get(f) not in ("unknown", None, "none", "")
    )


def load_gemini_video_by_ball_id(glob_pattern: str) -> dict[str, dict]:
    """Dedupe across chunk JSONs, keeping the highest-quality record per ball_id."""
    paths = sorted(glob.glob(glob_pattern))
    by_id: dict[str, dict] = {}
    for p in paths:
        try:
            data = json.load(open(p))
        except Exception as e:
            print(f"  ! could not read {p}: {e}", file=sys.stderr)
            continue
        records = data if isinstance(data, list) else data.get("balls", [])
        for r in records:
            bid = r.get("ball_id")
            if not bid:
                continue
            if bid not in by_id or _record_quality(r) > _record_quality(by_id[bid]):
                by_id[bid] = r
    return by_id


# --- Gemini call -------------------------------------------------------

_SYNTH_OUT_SCHEMA_ITEM = {
    "type": "object",
    "properties": {
        "ball_id": {"type": "string"},
        "bowler_type": {"type": "string", "enum": ["pace", "spin", "unknown"]},
        "line": {"type": "string", "enum": ["outside_off", "off_stump", "middle", "leg", "outside_leg", "unknown"]},
        "length": {"type": "string", "enum": ["yorker", "full", "good", "short_of_length", "short", "unknown"]},
        "variation": {"type": "string", "enum": ["none", "slower", "cutter", "bouncer", "yorker", "spin_variation", "unknown"]},
        "movement": {"type": "string", "enum": ["none", "seam", "swing", "turn", "unknown"]},
        "swing_direction": {"type": "string", "enum": ["in_swing", "out_swing", "none", "unknown"]},
        "swing_type": {"type": "string", "enum": ["conventional", "late", "reverse", "none", "unknown"]},
        "spin_direction": {"type": "string", "enum": ["off_break", "leg_break", "googly", "arm_ball", "doosra", "carrom", "top_spin", "slider", "none", "unknown"]},
        "bowler_crease": {"type": "string", "enum": ["over_the_wicket", "round_the_wicket", "wide_of_crease", "unknown"]},
        "bowling_speed_kmph": {"type": "number"},
        "ball_age_phase": {"type": "string", "enum": ["new_ball", "old", "reverse_window", "unknown"]},
        "shot_type": {"type": "string", "enum": [
            "drive", "cut", "pull", "hook", "defend", "sweep", "reverse_sweep",
            "glance", "flick", "lofted", "leave", "unknown",
            "cover_drive", "straight_drive", "on_drive", "off_drive", "square_drive",
            "square_cut", "late_cut", "upper_cut",
            "front_foot_defence", "back_foot_defence",
            "slog_sweep", "paddle_sweep",
            "leg_glance", "helicopter", "scoop",
        ]},
        "footwork": {"type": "string", "enum": ["front_foot", "back_foot", "neutral", "unknown"]},
        "contact_quality": {"type": "string", "enum": ["clean", "mistimed", "edge", "miss", "unknown"]},
        "edge_type": {"type": "string", "enum": ["inside_edge", "outside_edge", "top_edge", "bottom_edge", "none", "unknown"]},
        "shot_direction": {"type": "string", "enum": [
            "third_man", "deep_third", "point", "deep_point",
            "cover", "deep_cover", "mid_off", "long_off",
            "straight", "long_on", "mid_on", "mid_wicket",
            "deep_mid_wicket", "square_leg", "deep_square_leg",
            "fine_leg", "deep_fine_leg", "behind_wicket",
            "none", "unknown",
        ]},
        "batsman_handedness": {"type": "string", "enum": ["right_handed", "left_handed", "unknown"]},
        "raw_description": {"type": "string"},
        "confidence": {
            "type": "object",
            "properties": {
                "bowler_type": {"type": "number"},
                "line": {"type": "number"},
                "length": {"type": "number"},
                "shot_type": {"type": "number"},
                "contact_quality": {"type": "number"},
                "shot_direction": {"type": "number"},
                "swing_direction": {"type": "number"},
                "spin_direction": {"type": "number"},
                "swing_type": {"type": "number"},
                "bowler_crease": {"type": "number"},
                "edge_type": {"type": "number"},
                "handedness": {"type": "number"},
            },
        },
    },
    "required": ["ball_id", "line", "length", "shot_type", "contact_quality", "raw_description"],
}


def call_gemini_synthesise(
    over_number: int,
    bundles: list[dict],
    model_name: str,
) -> list[dict]:
    """Send one over's bundles to gemini-2.5-pro text-only."""
    from google import genai
    from google.genai import types

    from match_intelligence.lib.synthesis_prompt import (
        SYNTHESIS_SYSTEM_PROMPT, build_synthesis_prompt,
    )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing from env / .env")

    prompt = build_synthesis_prompt(over_number=over_number, balls_with_sources=bundles)
    client = genai.Client(api_key=api_key)

    batch_schema = {"type": "array", "items": _SYNTH_OUT_SCHEMA_ITEM}

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYNTHESIS_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=batch_schema,
            temperature=0.1,
        ),
    )

    raw = json.loads(response.text)
    if not isinstance(raw, list):
        raw = [raw]
    return raw


# --- Merge synthesised output back onto Cricsheet anchor ---------------

_TECHNIQUE_OUT_FIELDS = (
    "bowler_type", "line", "length", "variation", "movement",
    "swing_direction", "swing_type", "spin_direction",
    "bowler_crease", "bowling_speed_kmph", "ball_age_phase",
    "shot_type", "footwork", "contact_quality", "edge_type",
    "shot_direction", "batsman_handedness",
    "raw_description", "confidence",
)


def merge_synth_into_cricsheet(
    cricsheet_balls: list[dict],
    synth_records: list[dict],
) -> list[dict]:
    """Overlay synthesised technique fields onto the Cricsheet records.

    Joins by ball_id. Cricsheet always wins WHO/WHAT/RUNS.
    """
    by_id = {s.get("ball_id"): s for s in synth_records if s.get("ball_id")}
    out = []
    for i, cs in enumerate(cricsheet_balls):
        s = by_id.get(cs["ball_id"]) or (synth_records[i] if i < len(synth_records) else {})
        merged = dict(cs)
        for f in _TECHNIQUE_OUT_FIELDS:
            if f in s:
                merged[f] = s[f]
        merged["_synth_emitted"] = bool(s)
        out.append(merged)
    return out


# --- Main --------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--cricsheet-json", required=True)
    p.add_argument("--espn-commentary", required=True)
    p.add_argument("--gemini-video-glob", required=True,
                   help="Glob for existing chunk JSONs e.g. 'data/IndvsEng_chunk*_with_cricsheet.json'")
    p.add_argument("--out", required=True, help="Final unified output JSON")
    p.add_argument("--resume-dir", required=True,
                   help="Directory for per-over outputs (enables resume)")
    p.add_argument("--model", default="gemini-2.5-pro")
    p.add_argument("--over-range", default=None,
                   help="Optional 'a-b' to limit overs (inclusive); default = all overs")
    p.add_argument("--smoke-test", action="store_true",
                   help="Run only the first over (or --over-range first over) and exit")
    args = p.parse_args()

    from match_intelligence.lib.espn_commentary import (
        load_espn_commentary, build_commentary_by_ball,
    )

    # --- Load inputs ---
    cs_payload = json.loads(Path(args.cricsheet_json).read_text())
    all_balls = cs_payload.get("balls", cs_payload if isinstance(cs_payload, list) else [])
    legal = [b for b in all_balls if b.get("is_legal_delivery")]
    overs_present = sorted(set(b["over"] for b in legal))
    print(f"Cricsheet: {len(all_balls)} total balls, {len(legal)} legal, overs {overs_present[0]}..{overs_present[-1]}")

    espn_balls = load_espn_commentary(args.espn_commentary)
    print(f"ESPN: {len(espn_balls)} commentary entries")

    # ESPN join uses the FULL ball list to compute legal_ball_pos correctly
    commentary_by_ball = build_commentary_by_ball(espn_balls, all_balls)
    # Also retain the raw ESPN records keyed by (over, legal_pos) for full
    # fields (bowler/batter/outcome_text/commentary) — re-derive here.
    espn_by_key: dict[tuple[int, int], dict] = {
        (e["scoreboard_over"], e["scoreboard_ball"]): e for e in espn_balls
    }
    # Compute legal_ball_pos for cricsheet balls
    legal_pos_by_ball_id: dict[str, int] = {}
    over_legal_count: dict[int, int] = {}
    for b in all_balls:
        if not b.get("is_legal_delivery"):
            continue
        o = b["over"]
        n = over_legal_count.get(o, 0) + 1
        over_legal_count[o] = n
        legal_pos_by_ball_id[b["ball_id"]] = n

    video_by_ball_id = load_gemini_video_by_ball_id(args.gemini_video_glob)
    print(f"Gemini video: {len(video_by_ball_id)} unique ball_ids after dedup")

    # --- Resume dir ---
    resume_dir = Path(args.resume_dir)
    resume_dir.mkdir(parents=True, exist_ok=True)

    # --- Determine overs to process ---
    if args.over_range:
        a, b = args.over_range.split("-")
        target_overs = list(range(int(a), int(b) + 1))
    else:
        target_overs = overs_present
    if args.smoke_test:
        target_overs = target_overs[:1]
    print(f"Processing overs: {target_overs[0]}..{target_overs[-1]} ({len(target_overs)} overs)")

    # --- Per-over loop ---
    all_synth_records: list[dict] = []
    for over in target_overs:
        out_path = resume_dir / f"over_{over:02d}.json"
        if out_path.exists():
            print(f"  over {over}: resume — using {out_path.name}")
            all_synth_records.extend(json.loads(out_path.read_text()))
            continue

        over_balls = [b for b in legal if b["over"] == over]
        bundles = []
        for cs in over_balls:
            legal_pos = legal_pos_by_ball_id.get(cs["ball_id"])
            espn_rec = espn_by_key.get((over, legal_pos)) if legal_pos else None
            vid = video_by_ball_id.get(cs["ball_id"])
            bundles.append({"cricsheet": cs, "espn": espn_rec, "video": vid})

        n_espn = sum(1 for x in bundles if x["espn"])
        n_vid = sum(1 for x in bundles if x["video"])
        print(f"  over {over}: {len(bundles)} balls (ESPN: {n_espn}, video: {n_vid}) → calling {args.model}...")

        start = time.time()
        try:
            synth = call_gemini_synthesise(over_number=over, bundles=bundles, model_name=args.model)
        except Exception as e:
            print(f"  ! over {over} FAILED: {e}", file=sys.stderr)
            print(f"  ! stopping — fix the issue and re-run; per-over outputs already written are kept")
            sys.exit(2)
        dt = time.time() - start
        print(f"    ✓ {len(synth)} records in {dt:.1f}s")
        if len(synth) != len(bundles):
            print(f"    ⚠ count mismatch — expected {len(bundles)}, got {len(synth)}", file=sys.stderr)

        out_path.write_text(json.dumps(synth, indent=2))
        all_synth_records.extend(synth)

    # --- Final merge ---
    legal_for_merge = [b for b in legal if b["over"] in target_overs]
    final = merge_synth_into_cricsheet(legal_for_merge, all_synth_records)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(final, indent=2))
    print(f"\n✓ Wrote {len(final)} merged records → {args.out}")

    # Quality summary
    filled = sum(1 for m in final if m.get("shot_type") and m["shot_type"] != "unknown")
    has_speed = sum(1 for m in final if m.get("bowling_speed_kmph") not in (None, 0))
    has_crease = sum(1 for m in final if m.get("bowler_crease") not in (None, "unknown"))
    print(f"  shot_type filled: {filled}/{len(final)}")
    print(f"  bowling_speed_kmph populated: {has_speed}/{len(final)}")
    print(f"  bowler_crease populated: {has_crease}/{len(final)}")


if __name__ == "__main__":
    main()
