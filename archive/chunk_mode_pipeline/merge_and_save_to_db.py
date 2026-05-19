#!/usr/bin/env python3
"""Merge per-chunk Cricsheet+Gemini JSONs and update the DB with technique fields.

Pipeline:
  1. Load all `data/IndvsEng_chunk*_with_cricsheet.json` files (or via --inputs).
  2. Group records by ball_id. For balls that appear in multiple chunks (overlap),
     pick the version with the most non-`unknown` technique fields.
  3. Write `merged_balls.json` for inspection.
  4. UPDATE the DB's `balls` table: technique fields only, WHO/WHAT/RUNS untouched.
  5. Optionally export to CSV.

Usage:
    python features/ball_extraction/merge_and_save_to_db.py \\
        --inputs 'data/IndvsEng_chunk*_with_cricsheet.json' \\
        --match-id T20-IndvsEng-IndBat \\
        --merged-out data/IndvsEng_merged.json \\
        --csv-out data/IndvsEng_balls.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


TECHNIQUE_FIELDS = (
    "bowler_type", "line", "length", "variation", "movement",
    "swing_direction", "swing_type", "spin_direction", "bowler_crease",
    "bowling_speed_kmph", "ball_age_phase",
    "shot_type", "footwork", "contact_quality", "edge_type",
    "shot_direction", "batsman_handedness",
)

UNKNOWN_SENTINELS = {"unknown", "none", "", None}


def technique_score(rec: dict) -> tuple[int, float]:
    """Score a record for merge tie-breaking: (non-unknown count, avg confidence)."""
    non_unknown = sum(1 for f in TECHNIQUE_FIELDS if rec.get(f) not in UNKNOWN_SENTINELS)
    conf = rec.get("confidence") or {}
    confs = [v for v in conf.values() if isinstance(v, (int, float))]
    return (non_unknown, sum(confs) / len(confs) if confs else 0.0)


def merge_records(records_by_id: dict[str, list[dict]]) -> list[dict]:
    """Pick the best record per ball_id."""
    merged = []
    for ball_id, recs in records_by_id.items():
        best = max(recs, key=technique_score)
        merged.append(best)
    merged.sort(key=lambda r: (r.get("innings", 1), r.get("over", 0), r.get("ball_number", 0)))
    return merged


def update_db(match_id: str, merged: list[dict], db) -> tuple[int, int]:
    """UPDATE balls table with technique fields. Returns (updated, missing)."""
    from sqlalchemy import text
    updated = 0
    missing = 0
    with db.engine.begin() as conn:
        for r in merged:
            cricsheet_ball_id = r.get("ball_id")
            innings = r.get("innings")
            over = r.get("over")
            ball_number = r.get("ball_number")
            db_ball_id = f"{match_id}_i{innings}_{over}_{ball_number}"
            conf = r.get("confidence") or {}
            res = conn.execute(text("""
                UPDATE balls SET
                    bowler_type = COALESCE(:bowler_type, bowler_type),
                    line = COALESCE(:line, line),
                    length = COALESCE(:length, length),
                    variation = COALESCE(:variation, variation),
                    movement = COALESCE(:movement, movement),
                    swing_direction = COALESCE(:swing_direction, swing_direction),
                    swing_type = COALESCE(:swing_type, swing_type),
                    spin_direction = COALESCE(:spin_direction, spin_direction),
                    bowler_crease = COALESCE(:bowler_crease, bowler_crease),
                    bowling_speed_kmph = COALESCE(:bowling_speed_kmph, bowling_speed_kmph),
                    ball_age_phase = COALESCE(:ball_age_phase, ball_age_phase),
                    shot_type = COALESCE(:shot_type, shot_type),
                    footwork = COALESCE(:footwork, footwork),
                    contact_quality = COALESCE(:contact_quality, contact_quality),
                    edge_type = COALESCE(:edge_type, edge_type),
                    shot_direction = COALESCE(:shot_direction, shot_direction),
                    batsman_handedness = COALESCE(:batsman_handedness, batsman_handedness),
                    confidence_bowler_type = :conf_bowler_type,
                    confidence_line = :conf_line,
                    confidence_length = :conf_length,
                    confidence_shot_type = :conf_shot_type,
                    confidence_outcome = :conf_outcome,
                    confidence_contact = :conf_contact,
                    raw_description = :raw_description,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ball_id = :ball_id
            """), {
                "bowler_type": r.get("bowler_type"),
                "line": r.get("line") if r.get("line") != "unknown" else None,
                "length": r.get("length") if r.get("length") != "unknown" else None,
                "variation": r.get("variation"),
                "movement": r.get("movement"),
                "swing_direction": r.get("swing_direction"),
                "swing_type": r.get("swing_type"),
                "spin_direction": r.get("spin_direction"),
                "bowler_crease": r.get("bowler_crease") if r.get("bowler_crease") != "unknown" else None,
                "bowling_speed_kmph": r.get("bowling_speed_kmph") if r.get("bowling_speed_kmph") else None,
                "ball_age_phase": r.get("ball_age_phase"),
                "shot_type": r.get("shot_type") if r.get("shot_type") != "unknown" else None,
                "footwork": r.get("footwork") if r.get("footwork") != "unknown" else None,
                "contact_quality": r.get("contact_quality") if r.get("contact_quality") != "unknown" else None,
                "edge_type": r.get("edge_type"),
                "shot_direction": r.get("shot_direction") if r.get("shot_direction") != "unknown" else None,
                "batsman_handedness": r.get("batsman_handedness"),
                "conf_bowler_type": float(conf.get("bowler_type", 0.0) or 0.0),
                "conf_line": float(conf.get("line", 0.0) or 0.0),
                "conf_length": float(conf.get("length", 0.0) or 0.0),
                "conf_shot_type": float(conf.get("shot_type", 0.0) or 0.0),
                "conf_outcome": float(conf.get("outcome", 1.0) or 1.0),  # Cricsheet outcome is always certain
                "conf_contact": float(conf.get("contact_quality", 0.0) or 0.0),
                "raw_description": f"[cricsheet+gemini-tech] {r.get('raw_description', '')}",
                "ball_id": db_ball_id,
            })
            if res.rowcount:
                updated += 1
            else:
                missing += 1
                print(f"  ⚠ no DB row matched ball_id={db_ball_id}")
    return updated, missing


def export_csv(match_id: str, csv_path: str, db) -> int:
    """Dump the populated balls into a flat CSV."""
    from sqlalchemy import text
    cols = [
        "ball_id", "innings", "over_number", "ball_number",
        "bowler_name", "batsman_name",
        "outcome", "runs_scored", "dismissal_type", "dismissal_fielder",
        "bowler_type", "line", "length", "variation", "bowler_crease",
        "swing_direction", "movement", "spin_direction", "bowling_speed_kmph", "ball_age_phase",
        "shot_type", "footwork", "contact_quality", "edge_type", "shot_direction",
        "batsman_handedness", "phase",
        "raw_description",
    ]
    sql = f"SELECT {', '.join(cols)} FROM balls WHERE match_id = :mid ORDER BY innings, over_number, ball_number"
    with db.engine.begin() as conn:
        rows = list(conn.execute(text(sql), {"mid": match_id}))
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
    return len(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inputs", default="data/IndvsEng_chunk*_with_cricsheet.json", help="Glob for per-chunk JSON files")
    p.add_argument("--match-id", required=True, help="DB match_id, e.g. T20-IndvsEng-IndBat")
    p.add_argument("--merged-out", default="data/IndvsEng_merged.json")
    p.add_argument("--csv-out", default=None, help="Optional CSV export path")
    p.add_argument("--skip-db", action="store_true", help="Only merge, don't touch the DB")
    args = p.parse_args()

    paths = sorted(glob.glob(args.inputs))
    if not paths:
        print(f"✗ No files matched {args.inputs}")
        sys.exit(1)
    print(f"Loading {len(paths)} per-chunk JSON files...")
    records_by_id: dict[str, list[dict]] = {}
    for p_ in paths:
        for r in json.loads(Path(p_).read_text()):
            records_by_id.setdefault(r["ball_id"], []).append(r)

    total_raw = sum(len(v) for v in records_by_id.values())
    print(f"  {total_raw} total records → {len(records_by_id)} unique ball_ids")
    duplicates = sum(1 for v in records_by_id.values() if len(v) > 1)
    print(f"  {duplicates} ball_ids appeared in 2+ chunks (overlap dedup applied)")

    merged = merge_records(records_by_id)
    Path(args.merged_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.merged_out).write_text(json.dumps(merged, indent=2))
    print(f"✓ Wrote merged JSON → {args.merged_out}")

    filled = sum(1 for r in merged if r.get("shot_type") not in UNKNOWN_SENTINELS)
    print(f"  Technique-filled: {filled}/{len(merged)} ({100*filled/len(merged):.0f}%)")

    if args.skip_db:
        print("Skipping DB update (--skip-db).")
    else:
        from src.storage.db import CricketDB
        db = CricketDB()
        updated, missing = update_db(args.match_id, merged, db)
        print(f"✓ DB: updated {updated}/{len(merged)} ball rows  ({missing} missing)")

        if args.csv_out:
            n = export_csv(args.match_id, args.csv_out, db)
            print(f"✓ CSV: wrote {n} rows → {args.csv_out}")


if __name__ == "__main__":
    main()
