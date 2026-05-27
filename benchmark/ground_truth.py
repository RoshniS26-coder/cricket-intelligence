"""Load and filter ground truth records for benchmark overs."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from benchmark.config import GROUND_TRUTH_PATH, BENCHMARK_FIELDS, BENCHMARK_OVERS


def load_ground_truth(
    gt_path: Path = GROUND_TRUTH_PATH,
    overs: list[int] = BENCHMARK_OVERS,
    innings: Optional[int] = None,
) -> list[dict]:
    raw = json.loads(Path(gt_path).read_text())
    records = raw.get("balls", raw.get("records", raw)) if isinstance(raw, dict) else raw

    filtered = []
    for r in records:
        over = r.get("over_number", r.get("over", -1))
        inn = r.get("innings", 1)
        if over not in overs:
            continue
        if innings is not None and inn != innings:
            continue
        entry = {
            "ball_id":     r.get("ball_id", f"i{inn}_{over}_{r.get('ball_number', 0)}"),
            "over_number": over,
            "ball_number": r.get("ball_number", 0),
            "innings":     inn,
            "bowler_name":  r.get("bowler_name", ""),
            "batsman_name": r.get("batsman_name", ""),
        }
        for field in BENCHMARK_FIELDS:
            entry[field] = r.get(field, "unknown")
        filtered.append(entry)

    return filtered


def print_ground_truth_summary(records: list[dict]) -> None:
    from collections import Counter
    print(f"\nGround truth: {len(records)} balls | overs {sorted(set(r['over_number'] for r in records))}")
    for field in BENCHMARK_FIELDS:
        vals = Counter(r[field] for r in records if r[field] != "unknown")
        print(f"  {field}: {dict(vals)}")
