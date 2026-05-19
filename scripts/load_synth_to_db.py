#!/usr/bin/env python3
"""Load a synthesised match JSON into the SQLite DB.

Wipes existing rows for the target match (under both the canonical
Cricsheet match_id and any legacy match_id used during chunk extraction),
upserts the matches row, then inserts the new ball records.

Usage:
    python scripts/load_synth_to_db.py \\
        --input data/IndvsEng_full_match_correct.json \\
        --match-id 1276906 \\
        --legacy-match-ids T20-IndvsEng-IndBat \\
        --team-a India --team-b England \\
        --format T20
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from src.storage.db import CricketDB, MatchRecord, BallDBRecord


_TECH_STR_FIELDS = (
    "bowler_type", "line", "length", "variation", "movement",
    "swing_direction", "swing_type", "spin_direction",
    "shot_type", "footwork", "contact_quality",
    "shot_direction", "dismissal_type", "bowler_crease",
    "edge_type", "batsman_handedness", "ball_age_phase",
)


def _as_str(v, default="unknown"):
    if v is None or v == "":
        return default
    return str(v)


def _as_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _as_optional_float(v):
    # Treat 0, -1, and negative values as "not available"
    if v in (None, "", 0, 0.0):
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--match-id", required=True, help="Target match_id to insert under")
    ap.add_argument("--legacy-match-ids", nargs="*", default=[],
                    help="Additional match_ids whose rows should be wiped first")
    ap.add_argument("--team-a", default="")
    ap.add_argument("--team-b", default="")
    ap.add_argument("--format", default="T20")
    ap.add_argument("--venue", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-wipe", action="store_true",
                    help="Don't delete existing rows under --match-id (used when loading a second innings)")
    args = ap.parse_args()

    records = json.loads(Path(args.input).read_text())
    print(f"Loaded {len(records)} records from {args.input}")
    sample = records[0]
    src_match_ids = sorted(set(r.get("match_id") for r in records))
    print(f"Source match_ids in JSON: {src_match_ids}")

    db = CricketDB()
    session = db.get_session()
    try:
        # 1. Delete existing rows for target + legacy match_ids
        if args.skip_wipe:
            print("  --skip-wipe set; leaving existing rows in place")
        else:
            wipe_ids = [args.match_id] + list(args.legacy_match_ids)
            for mid in wipe_ids:
                n = session.query(BallDBRecord).filter_by(match_id=mid).count()
                print(f"  DB has {n} balls under match_id={mid!r} — will delete")
                if not args.dry_run:
                    session.execute(delete(BallDBRecord).where(BallDBRecord.match_id == mid))
                    session.execute(delete(MatchRecord).where(MatchRecord.match_id == mid))
            if not args.dry_run:
                session.commit()
                print("  ✓ Wiped old rows")

        # 2. Upsert matches row
        if not args.dry_run:
            mrec = MatchRecord(
                match_id=args.match_id,
                format=args.format,
                team_a=args.team_a,
                team_b=args.team_b,
                venue=args.venue,
                created_at=datetime.now(),
            )
            session.merge(mrec)
            session.commit()
            print(f"  ✓ Upserted matches row for {args.match_id}")

        # 3. Insert balls — construct innings-qualified ball_id so innings 1
        #    and innings 2 records don't collide on the (match,over,ball)
        #    primary key. Format: {match_id}_i{innings}_{over}_{ball_number}.
        n_inserted = 0
        for r in records:
            conf = r.get("confidence") or {}
            new_ball_id = f"{args.match_id}_i{int(r.get('innings', 1))}_{int(r['over'])}_{int(r['ball_number'])}"
            db_rec = BallDBRecord(
                ball_id=new_ball_id,
                match_id=args.match_id,
                innings=int(r.get("innings", 1)),
                over_number=int(r["over"]),
                ball_number=int(r["ball_number"]),
                bowler_name=r.get("bowler_name"),
                batsman_name=r.get("batsman_name"),
                bowler_type=_as_str(r.get("bowler_type")),
                line=_as_str(r.get("line")),
                length=_as_str(r.get("length")),
                variation=_as_str(r.get("variation"), default="none"),
                movement=_as_str(r.get("movement")),
                swing_direction=_as_str(r.get("swing_direction")),
                swing_type=_as_str(r.get("swing_type")),
                spin_direction=_as_str(r.get("spin_direction")),
                ball_age_phase=_as_str(r.get("ball_age_phase")),
                shot_type=_as_str(r.get("shot_type")),
                footwork=_as_str(r.get("footwork")),
                contact_quality=_as_str(r.get("contact_quality")),
                outcome=_as_str(r.get("outcome")),
                runs_scored=int(r.get("runs_scored", 0)),
                shot_direction=_as_str(r.get("shot_direction")),
                dismissal_type=_as_str(r.get("dismissal_type"), default="none"),
                dismissal_fielder=r.get("dismissal_fielder"),
                bowling_speed_kmph=_as_optional_float(r.get("bowling_speed_kmph")),
                bowler_crease=_as_str(r.get("bowler_crease")),
                edge_type=_as_str(r.get("edge_type"), default="none"),
                batsman_handedness=_as_str(r.get("batsman_handedness")),
                confidence_bowler_type=_as_float(conf.get("bowler_type")),
                confidence_line=_as_float(conf.get("line")),
                confidence_length=_as_float(conf.get("length")),
                confidence_shot_type=_as_float(conf.get("shot_type")),
                confidence_outcome=_as_float(conf.get("outcome", 1.0)),
                confidence_contact=_as_float(conf.get("contact_quality")),
                raw_description=r.get("raw_description"),
                is_reviewed=False,
            )
            if not args.dry_run:
                session.merge(db_rec)
            n_inserted += 1
        if not args.dry_run:
            session.commit()
        print(f"  ✓ Inserted {n_inserted} ball records under match_id={args.match_id}")

        # 4. Verify
        n_after = session.query(BallDBRecord).filter_by(match_id=args.match_id).count()
        print(f"\nFINAL: match_id={args.match_id} has {n_after} balls in DB")
    finally:
        session.close()


if __name__ == "__main__":
    main()
