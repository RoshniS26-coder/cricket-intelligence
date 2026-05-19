#!/usr/bin/env python3
"""Import a Cricsheet match's ball-by-ball data into the local SQLite DB.

WHO/WHAT/RUNS fields come from Cricsheet at 100% accuracy. Technique fields
(shot, line, length, contact, etc.) stay at UNKNOWN defaults — fill those
later with a per-ball Gemini call against aligned video clips.

Usage:
    python features/ball_extraction/import_cricsheet.py \\
        --cricsheet-id 1276906 \\
        --match-id T20-IndvsEng-IndBat \\
        --video-path data/raw_videos/IndiaBatting-T20-IndvsEng.mp4

Use --replace to delete existing rows for this match_id before importing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from match_intelligence.lib.cricsheet import load_match, match_metadata, to_ball_records
from src.storage.db import CricketDB


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--cricsheet-id", required=True, help="Cricsheet match ID, e.g. 1276906")
    p.add_argument("--match-id", required=True, help="Local match_id used in the DB and ball_id prefix")
    p.add_argument("--video-path", default=None, help="Optional path to the video file for this match")
    p.add_argument("--replace", action="store_true", help="Delete existing rows for this match_id before importing")
    args = p.parse_args()

    match = load_match(args.cricsheet_id)
    meta = match_metadata(match)
    meta["match_id"] = args.match_id
    if args.video_path:
        meta["video_path"] = args.video_path
    meta["source_url"] = f"https://cricsheet.org/matches/{args.cricsheet_id}/"

    records = to_ball_records(match, video_match_id=args.match_id)
    print(f"Loaded {len(records)} ball records from Cricsheet match {args.cricsheet_id}")

    db = CricketDB()

    if args.replace:
        from sqlalchemy import text
        with db.engine.begin() as conn:
            n_balls = conn.execute(
                text("DELETE FROM balls WHERE match_id = :mid"), {"mid": args.match_id}
            ).rowcount
            n_match = conn.execute(
                text("DELETE FROM matches WHERE match_id = :mid"), {"mid": args.match_id}
            ).rowcount
        print(f"  Deleted {n_balls} prior ball rows + {n_match} match row for {args.match_id}")

    db.create_match(meta)
    saved = db.save_balls_batch(records)
    print(f"Imported {saved}/{len(records)} balls into DB for match_id={args.match_id}")


if __name__ == "__main__":
    main()
