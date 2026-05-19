"""
Batsman weakness + strength analysis — statistical aggregation over ball records.

Takes a list of BallDBRecord objects and returns a structured profile with:
  - zones: all line × length combinations with dismissal rate, false-shot rate,
    danger score, strength score, and run stats
  - top_weakness: highest danger_score zone
  - top_strength: highest strength_score zone
  - strengths: zones ranked by strength score (good scoring, low dismissal rate)
  - by_bowler_type / by_variation / by_swing / by_spin breakdowns

Scoring formulas
----------------
  danger_score   = (dismissal_rate × 0.6) + (false_shot_rate × 0.4)
  strength_score = avg_runs × (1 - dismissal_rate)
                   — rewards zones where the batsman scores freely without
                   getting dismissed; naturally penalises any zone with wickets.

Zones with < 2 balls are excluded as statistically unreliable.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.db import BallDBRecord

_FALSE_SHOT_CONTACTS = {"edge", "miss", "mistimed"}
_MIN_SAMPLE = 2
_MAX_AVG_RUNS = 6.0  # theoretical maximum (all sixes) for normalisation


def _zone_stats(balls: list) -> dict:
    """Compute dismissal, false-shot, runs, and scoring stats for a list of balls."""
    total = len(balls)
    if total == 0:
        return {}
    dismissals = sum(1 for b in balls if b.outcome == "wicket")
    false_shots = sum(1 for b in balls if (b.contact_quality or "") in _FALSE_SHOT_CONTACTS)
    boundaries = sum(1 for b in balls if b.outcome in ("4", "6"))
    runs = sum(b.runs_scored or 0 for b in balls)
    dismissal_rate = dismissals / total
    false_shot_rate = false_shots / total
    avg_runs = runs / total

    danger_score = dismissal_rate * 0.6 + false_shot_rate * 0.4
    # Strength: runs scored freely without dismissal.
    # Capped normalisation so a 6-per-ball zone scores 1.0.
    strength_score = min(avg_runs / _MAX_AVG_RUNS, 1.0) * (1 - dismissal_rate)

    return {
        "total": total,
        "dismissals": dismissals,
        "false_shots": false_shots,
        "boundaries": boundaries,
        "runs": runs,
        "avg_runs": round(avg_runs, 2),
        "dismissal_rate": round(dismissal_rate, 3),
        "false_shot_rate": round(false_shot_rate, 3),
        "danger_score": round(danger_score, 3),
        "strength_score": round(strength_score, 3),
    }


def _crosstab_field(balls: list, field: str) -> dict[str, dict]:
    """Group balls by a single field and compute zone stats for each bucket."""
    buckets: dict[str, list] = defaultdict(list)
    for b in balls:
        key = getattr(b, field, None) or "unknown"
        buckets[key].append(b)
    result = {}
    for key, group in buckets.items():
        if len(group) >= _MIN_SAMPLE:
            result[key] = _zone_stats(group)
    return result


def compute_weakness_profile(
    balls: list,
    batsman_name: str = "",
) -> dict:
    """
    Build a full weakness + strength profile from a list of BallDBRecord objects.

    Args:
        balls: List of BallDBRecord rows (pre-filtered by DB query).
        batsman_name: Display name for the report header.

    Returns:
        Structured profile dict ready for CLI display, API response, Gemini
        narration input, or pitch map rendering.
    """
    if not balls:
        return {
            "batsman_name": batsman_name,
            "total_balls": 0,
            "zones": [],
            "strengths": [],
            "top_weakness": None,
            "top_strength": None,
            "by_bowler_type": {},
            "by_variation": {},
            "by_swing": {},
            "by_spin": {},
        }

    # Line × Length zone matrix
    zone_buckets: dict[tuple, list] = defaultdict(list)
    for b in balls:
        line = b.line or "unknown"
        length = b.length or "unknown"
        zone_buckets[(line, length)].append(b)

    zones = []
    for (line, length), group in zone_buckets.items():
        if len(group) < _MIN_SAMPLE:
            continue
        stats = _zone_stats(group)
        zones.append({"line": line, "length": length, **stats})

    # Weaknesses — highest danger first
    weaknesses = sorted(zones, key=lambda z: z["danger_score"], reverse=True)
    # Strengths — highest strength_score first (must have > 0 avg_runs)
    strengths = sorted(
        [z for z in zones if z["avg_runs"] > 0],
        key=lambda z: z["strength_score"],
        reverse=True,
    )

    return {
        "batsman_name": batsman_name,
        "total_balls": len(balls),
        "zones": weaknesses,          # all zones, danger-sorted
        "strengths": strengths,        # same zones, strength-sorted
        "top_weakness": weaknesses[0] if weaknesses else None,
        "top_strength": strengths[0] if strengths else None,
        "by_bowler_type": _crosstab_field(balls, "bowler_type"),
        "by_variation": _crosstab_field(balls, "variation"),
        "by_swing": _crosstab_field(balls, "swing_direction"),
        "by_spin": _crosstab_field(balls, "spin_direction"),
    }
