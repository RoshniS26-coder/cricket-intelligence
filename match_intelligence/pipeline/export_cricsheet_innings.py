#!/usr/bin/env python3
"""Export ONE innings from a Cricsheet match as a standalone JSON.

Useful when the video covers only one team's batting (e.g. a trim-and-keep
of "India batting" from a full match broadcast). The exported file is the
ground-truth context to feed into a per-ball Gemini call later — Gemini
gets bowler/batter/runs/wicket per ball and only needs to fill technique
fields (shot_type, line, length, etc.).

Usage:
    python features/ball_extraction/export_cricsheet_innings.py \\
        --cricsheet-id 1276906 \\
        --innings India \\
        --out data/cricsheet/IndvsEng/india_innings.json

Output JSON shape: a list of dicts, one per legal delivery.
Wides and no-balls are kept (with `is_legal_delivery: false`) so byte-by-byte
ball numbering is preserved if you need it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from match_intelligence.lib.cricsheet import iter_balls, load_match, match_metadata


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--cricsheet-id", required=True, help="Cricsheet match ID, e.g. 1276906")
    p.add_argument("--innings", required=True, help="Team name whose innings to export, e.g. India")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument("--legal-only", action="store_true", help="Drop wides/no-balls from the output")
    args = p.parse_args()

    match = load_match(args.cricsheet_id)
    meta = match_metadata(match)
    all_balls = iter_balls(match, match_id_for_record=args.cricsheet_id)
    innings_balls = [b for b in all_balls if b["innings_team"] == args.innings]
    if args.legal_only:
        innings_balls = [b for b in innings_balls if b["is_legal_delivery"]]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "match": {
            "cricsheet_id": args.cricsheet_id,
            **meta,
            "innings_team": args.innings,
        },
        "balls": innings_balls,
    }
    out_path.write_text(json.dumps(payload, indent=2))

    legal_count = sum(1 for b in innings_balls if b["is_legal_delivery"])
    wickets = sum(1 for b in innings_balls if b["outcome"] == "wicket")
    overs = (innings_balls[-1]["over"] + 1) if innings_balls else 0
    print(f"✓ Wrote {len(innings_balls)} ball records ({legal_count} legal, {wickets} wickets, {overs} overs) → {out_path}")


if __name__ == "__main__":
    main()
