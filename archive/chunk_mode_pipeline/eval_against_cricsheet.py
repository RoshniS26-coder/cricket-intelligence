#!/usr/bin/env python3
"""Score a Gemini ball-extraction output against Cricsheet ground truth.

Aligns Gemini-emitted ball records to Cricsheet's authoritative ball-by-ball
data, then reports per-field accuracy. Use this to benchmark any prompt /
model / pipeline change without hand-checking dozens of frames.

Usage:
    python features/ball_extraction/eval_against_cricsheet.py \\
        --gemini-json data/IndvsEng_ball_by_ball_v2/chunk_001_balls.json \\
        --cricsheet-id 1276906 \\
        --innings India

Alignment is reported two ways:
  - by (over, ball_number) label  — catches the "labels are right" case
  - by time-sorted sequence       — catches the "labels shifted but order ok"
The better of the two is usually the right read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.intelligence.cricsheet import iter_balls, load_match


def surname(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().split()[-1].lower()


def names_match(a: str | None, b: str | None) -> bool:
    sa, sb = surname(a), surname(b)
    return bool(sa) and sa == sb


def normalize_outcome(o) -> str:
    if o is None:
        return "unknown"
    s = str(o).lower().strip()
    return "dot" if s == "0" else s


def align_by_label(gemini_records, truth_balls):
    cs_by_key = {
        (b["over"], b["ball_number"]): b
        for b in truth_balls
        if b["is_legal_delivery"]
    }
    return [(g, cs_by_key.get((g.get("over", -1), g.get("ball_number", -1)))) for g in gemini_records]


def align_by_sequence(gemini_records, truth_balls):
    legal = [b for b in truth_balls if b["is_legal_delivery"]]
    sorted_g = sorted(
        gemini_records,
        key=lambda r: (
            r.get("start_sec") if r.get("start_sec") is not None
            else (r.get("over", 0) * 10 + r.get("ball_number", 0))
        ),
    )
    return [(g, legal[i] if i < len(legal) else None) for i, g in enumerate(sorted_g)]


def score(aligned):
    counters = {k: [0, 0] for k in ("bowler", "batsman", "outcome", "wicket_recall", "dismissal_type")}

    for g, t in aligned:
        if t is None:
            continue
        # bowler / batsman
        if g.get("bowler_name") and t.get("bowler_name"):
            counters["bowler"][1] += 1
            if names_match(g["bowler_name"], t["bowler_name"]):
                counters["bowler"][0] += 1
        if g.get("batsman_name") and t.get("batsman_name"):
            counters["batsman"][1] += 1
            if names_match(g["batsman_name"], t["batsman_name"]):
                counters["batsman"][0] += 1
        # outcome (full categorical match)
        g_out = normalize_outcome(g.get("outcome"))
        t_out = t.get("outcome")
        if g_out != "unknown" and t_out:
            counters["outcome"][1] += 1
            if g_out == t_out:
                counters["outcome"][0] += 1
        # wicket recall: of truth's wickets, how many did Gemini also flag as wicket?
        if t_out == "wicket":
            counters["wicket_recall"][1] += 1
            if g_out == "wicket":
                counters["wicket_recall"][0] += 1
                g_d = str(g.get("dismissal_type") or "").lower()
                t_d = t.get("dismissal_type")
                if g_d and g_d != "none" and t_d:
                    counters["dismissal_type"][1] += 1
                    if g_d == t_d:
                        counters["dismissal_type"][0] += 1
    return counters


def pct(n, d):
    if d == 0:
        return "  n/a"
    return f"{n}/{d} ({100 * n / d:5.1f}%)"


def report(label, aligned, emitted, truth_count):
    s = score(aligned)
    print(f"  [{label}]")
    print(f"    Recall (emitted vs truth):  {pct(emitted, truth_count)}")
    print(f"    Bowler correct:             {pct(*s['bowler'])}")
    print(f"    Batsman correct:            {pct(*s['batsman'])}")
    print(f"    Outcome correct:            {pct(*s['outcome'])}")
    print(f"    Wicket recall:              {pct(*s['wicket_recall'])}")
    print(f"    Dismissal type correct:     {pct(*s['dismissal_type'])}")


def eval_one(gemini_json: str, cricsheet_id: str, innings: str = "India", scope: str = "as-emitted") -> None:
    with open(gemini_json) as f:
        gemini = json.load(f)
    if isinstance(gemini, dict):
        gemini = gemini.get("records") or gemini.get("balls") or []

    match = load_match(cricsheet_id)
    all_balls = iter_balls(match, match_id_for_record=cricsheet_id)
    truth = [b for b in all_balls if b["innings_team"] == innings]

    if scope == "as-emitted" and gemini:
        max_over = max((g.get("over") or 0) for g in gemini)
        truth_scoped = [b for b in truth if b["over"] <= max_over]
    else:
        truth_scoped = truth
    legal_truth = [b for b in truth_scoped if b["is_legal_delivery"]]

    print(f"\n=== {Path(gemini_json).parent.name}/{Path(gemini_json).name} ===")
    print(f"  Emitted records: {len(gemini)}  |  Cricsheet scope: {len(legal_truth)} legal balls (overs 0–{truth_scoped[-1]['over'] if truth_scoped else '?'})")

    report("align: by (over, ball_number)", align_by_label(gemini, truth_scoped), len(gemini), len(legal_truth))
    report("align: by sequence (time-sorted)", align_by_sequence(gemini, truth_scoped), len(gemini), len(legal_truth))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gemini-json", action="append", required=True, help="Path to a Gemini output JSON. Pass multiple times to score many files.")
    p.add_argument("--cricsheet-id", required=True, help="Cricsheet match ID, e.g. 1276906")
    p.add_argument("--innings", default="India", help="Team name whose innings to score (default: India)")
    p.add_argument("--scope", choices=["full", "as-emitted"], default="as-emitted", help="Compare against full innings, or only the overs Gemini emitted (default).")
    args = p.parse_args()
    for path in args.gemini_json:
        eval_one(path, args.cricsheet_id, args.innings, args.scope)


if __name__ == "__main__":
    main()
