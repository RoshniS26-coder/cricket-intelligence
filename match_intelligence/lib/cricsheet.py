"""Cricsheet (https://cricsheet.org) ball-by-ball data loader.

Cricsheet ships per-match JSONs in bulk ZIPs (t20s_male_json.zip etc.); there
is no query API. This module locates a match in a local Cricsheet directory
by metadata filters and emits ball-level dicts ready to join against the
Gemini pipeline's BallRecord schema.

Cricsheet covers WHO / WHAT / HOW-MANY (bowler, batter, runs, wicket-type)
with 100% accuracy. It does NOT cover technique fields (shot_type, line,
length, footwork, contact_quality, speed). Use this loader for ground-truth
joins; let Gemini fill the technique fields.

Default directory: $CRICSHEET_DIR or ~/Downloads/t20s_male_json/
"""

from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DIR = os.environ.get(
    "CRICSHEET_DIR", os.path.expanduser("~/Downloads/t20s_male_json")
)

# Cricsheet "kind" strings → DismissalType enum values in src/intelligence/schema.py
DISMISSAL_MAP = {
    "caught": "caught",
    "bowled": "bowled",
    "lbw": "lbw",
    "run out": "run_out",
    "stumped": "stumped",
    "hit wicket": "hit_wicket",
    "caught and bowled": "caught_and_bowled",
    "retired hurt": "retired",
    "retired out": "retired",
    "retired not out": "retired",
    "obstructing the field": "obstructing",
    "handled the ball": "obstructing",
    "timed out": "obstructing",
}

OUTCOME_BY_RUNS = {0: "dot", 1: "1", 2: "2", 3: "3", 4: "4", 6: "6"}


def find_matches(
    teams: Iterable[str] | None = None,
    date: str | None = None,
    venue: str | None = None,
    players_required: Iterable[str] | None = None,
    cricsheet_dir: str = DEFAULT_DIR,
) -> list[tuple[str, dict]]:
    """Scan a Cricsheet directory and return matches matching all given filters.

    Returns a list of (match_id, full_match_dict) tuples sorted by date.
    """
    teams_set = set(teams) if teams else None
    needed_players = list(players_required or [])

    hits: list[tuple[str, dict]] = []
    for path in glob(f"{cricsheet_dir}/*.json"):
        try:
            with open(path) as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        info = d.get("info") or {}
        if teams_set and set(info.get("teams", [])) != teams_set:
            continue
        if date and date not in info.get("dates", []):
            continue
        if venue and venue.lower() not in (info.get("venue") or "").lower():
            continue
        if needed_players:
            all_players = [
                p for plist in (info.get("players") or {}).values() for p in plist
            ]
            if not all(
                any(needle in p for p in all_players) for needle in needed_players
            ):
                continue
        hits.append((Path(path).stem, d))

    hits.sort(key=lambda h: (h[1].get("info") or {}).get("dates", [""])[0])
    return hits


def load_match(match_id: str, cricsheet_dir: str = DEFAULT_DIR) -> dict:
    """Load a single Cricsheet match JSON by ID."""
    path = Path(cricsheet_dir) / f"{match_id}.json"
    with open(path) as f:
        return json.load(f)


def _ball_outcome(runs_total: int, has_wicket: bool, extras: dict | None) -> str:
    if has_wicket:
        return "wicket"
    if extras and extras.get("wides", 0) > 0:
        return "wide"
    if extras and extras.get("noballs", 0) > 0:
        return "no_ball"
    return OUTCOME_BY_RUNS.get(runs_total, "unknown")


def iter_balls(match: dict, match_id_for_record: str | None = None) -> list[dict]:
    """Flatten a Cricsheet match into a list of ball-level dicts.

    Each dict has the shape:
        {
          "ball_id": "<match_id>_<over>_<ball_number>",
          "match_id": match_id_for_record,
          "innings": 1 or 2,
          "innings_team": "India",
          "over": 0-indexed over,
          "ball_number": 1-indexed ball position within the over,
          "bowler_name": "DJ Willey",
          "batsman_name": "RG Sharma",
          "non_striker_name": "RR Pant",
          "runs_scored": runs.batter (the batter's own runs, not total),
          "runs_total": runs.total (including extras),
          "outcome": "dot" | "1" | ... | "wicket" | "wide" | "no_ball",
          "dismissal_type": "caught" | "lbw" | ... | "none",
          "dismissal_fielder": "JC Buttler" or None,
          "is_legal_delivery": bool (False for wides/no-balls),
          "extras_kind": "wides" | "noballs" | "byes" | "legbyes" | None,
        }

    Ball_number convention: the position of the delivery within its over
    (1-indexed), counting extras. Cricsheet preserves order within `deliveries`.
    For analytics-friendly joins, you may want to additionally compute a
    "legal ball number" by skipping wides/no-balls.
    """
    mid = match_id_for_record or "cricsheet"
    out: list[dict] = []
    for innings_idx, innings in enumerate(match.get("innings", []), start=1):
        team = innings.get("team")
        for ov in innings.get("overs", []):
            over_num = ov.get("over", 0)
            for ball_idx, dl in enumerate(ov.get("deliveries", []), start=1):
                runs = dl.get("runs") or {}
                extras = dl.get("extras") or {}
                wickets = dl.get("wickets") or []
                wkt0 = wickets[0] if wickets else None
                fielders = (wkt0 or {}).get("fielders") or []
                extras_kind = next(
                    (k for k in ("wides", "noballs", "byes", "legbyes") if extras.get(k)),
                    None,
                )
                out.append(
                    {
                        "ball_id": f"{mid}_{over_num}_{ball_idx}",
                        "match_id": mid,
                        "innings": innings_idx,
                        "innings_team": team,
                        "over": over_num,
                        "ball_number": ball_idx,
                        "bowler_name": dl.get("bowler"),
                        "batsman_name": dl.get("batter"),
                        "non_striker_name": dl.get("non_striker"),
                        "runs_scored": runs.get("batter", 0),
                        "runs_total": runs.get("total", 0),
                        "outcome": _ball_outcome(
                            runs.get("total", 0), bool(wickets), extras
                        ),
                        "dismissal_type": DISMISSAL_MAP.get(
                            (wkt0 or {}).get("kind", "").lower(), "none"
                        ),
                        "dismissal_player": (wkt0 or {}).get("player_out"),
                        "dismissal_fielder": fielders[0].get("name") if fielders else None,
                        "is_legal_delivery": extras_kind not in ("wides", "noballs"),
                        "extras_kind": extras_kind,
                    }
                )
    return out


def balls_in_range(
    balls: list[dict],
    over_min: int,
    over_max: int,
    innings_team: str | None = None,
    legal_only: bool = True,
) -> list[dict]:
    """Filter a list of ball dicts (from iter_balls) to a contiguous over range.

    over_min, over_max are inclusive and 0-indexed (over 0 = the first over).
    If innings_team is given, restrict to that team's innings.
    """
    out = balls
    if innings_team is not None:
        out = [b for b in out if b.get("innings_team") == innings_team]
    out = [b for b in out if over_min <= b["over"] <= over_max]
    if legal_only:
        out = [b for b in out if b["is_legal_delivery"]]
    return out


def to_ball_records(match: dict, video_match_id: str, t20_phases: bool = True) -> list:
    """Convert a Cricsheet match into a list of BallRecord pydantic objects.

    WHO / WHAT / RUNS fields are populated at 100% Cricsheet accuracy.
    Technique fields (shot_type, line, length, footwork, contact_quality,
    swing/spin, edge, speed, bowler_crease) keep their UNKNOWN defaults —
    fill those in later via a per-ball Gemini call against aligned video.

    Args:
        match: parsed Cricsheet match JSON.
        video_match_id: identifier used for the DB match_id and ball_id prefix.
        t20_phases: if True, derive InningsPhase from over (PP 0–5, middle 6–14,
            death 15+). Set False for ODI/Test or to leave as UNKNOWN.
    """
    # Imported lazily so this module is usable without the full pipeline.
    from src.intelligence.schema import (
        BallRecord, Outcome, DismissalType, InningsPhase,
    )

    OUTCOME_BY_BATTER_RUNS = {
        0: Outcome.DOT, 1: Outcome.ONE, 2: Outcome.TWO,
        3: Outcome.THREE, 4: Outcome.FOUR, 6: Outcome.SIX,
    }

    records: list = []
    for innings_idx, innings in enumerate(match.get("innings", []), start=1):
        for ov in innings.get("overs", []):
            over_num = ov.get("over", 0)
            for ball_idx, dl in enumerate(ov.get("deliveries", []), start=1):
                runs = dl.get("runs") or {}
                extras = dl.get("extras") or {}
                wickets = dl.get("wickets") or []
                wkt0 = wickets[0] if wickets else None

                if wickets:
                    outcome = Outcome.WICKET
                elif extras.get("wides", 0) > 0:
                    outcome = Outcome.WIDE
                elif extras.get("noballs", 0) > 0:
                    outcome = Outcome.NO_BALL
                else:
                    outcome = OUTCOME_BY_BATTER_RUNS.get(
                        runs.get("batter", 0), Outcome.UNKNOWN
                    )

                if wkt0:
                    dt_value = DISMISSAL_MAP.get((wkt0.get("kind") or "").lower(), "unknown")
                    try:
                        dismissal_type = DismissalType(dt_value)
                    except ValueError:
                        dismissal_type = DismissalType.UNKNOWN
                else:
                    dismissal_type = DismissalType.NONE

                fielders = (wkt0 or {}).get("fielders") or []
                dismissal_fielder = fielders[0].get("name") if fielders else None

                if t20_phases:
                    if over_num <= 5:
                        phase = InningsPhase.POWERPLAY
                    elif over_num <= 14:
                        phase = InningsPhase.MIDDLE_OVERS
                    else:
                        phase = InningsPhase.DEATH
                else:
                    phase = InningsPhase.UNKNOWN

                records.append(BallRecord(
                    ball_id=f"{video_match_id}_i{innings_idx}_{over_num}_{ball_idx}",
                    match_id=video_match_id,
                    innings=innings_idx,
                    over=over_num,
                    ball_number=ball_idx,
                    bowler_name=dl.get("bowler"),
                    batsman_name=dl.get("batter"),
                    runs_scored=runs.get("batter", 0),
                    outcome=outcome,
                    dismissal_type=dismissal_type,
                    dismissal_fielder=dismissal_fielder,
                    phase=phase,
                    raw_description=(
                        f"[cricsheet] {over_num}.{ball_idx} {dl.get('bowler')} → "
                        f"{dl.get('batter')} runs={runs.get('total', 0)}"
                        + (f" WICKET ({wkt0.get('kind')})" if wkt0 else "")
                    ),
                ))
    return records


def match_metadata(match: dict) -> dict:
    """Extract MatchMetadata-shaped dict from a Cricsheet match."""
    info = match.get("info") or {}
    teams = info.get("teams", [])
    return {
        "format": "T20" if info.get("match_type") in ("T20", "IT20") else info.get("match_type", "T20"),
        "team_a": teams[0] if len(teams) > 0 else "",
        "team_b": teams[1] if len(teams) > 1 else "",
        "venue": info.get("venue"),
        "date": info.get("dates", [None])[0],
        "match_date": info.get("dates", [None])[0],
        "day_or_night": None,
    }
