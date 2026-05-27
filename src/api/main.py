"""
Cricket Intelligence Engine - FastAPI REST API
Endpoints for the cricket intelligence platform.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.storage.db import CricketDB, BallDBRecord
from src.api.ai_coach_router import router as ai_coach_router

app = FastAPI(
    title="Cricket Intelligence Engine API",
    description="Ball-level cricket analytics for coaches and franchise analysts",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_coach_router)

db = CricketDB()


# ─── Pydantic models ──────────────────────────────────────────────────────────

class MatchCreate(BaseModel):
    match_id: str
    format: str = "T20"
    team_a: str = ""
    team_b: str = ""


class BallUpdate(BaseModel):
    line: Optional[str] = None
    length: Optional[str] = None
    shot_type: Optional[str] = None
    outcome: Optional[str] = None
    reviewed_by: str = "human"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _phase(over: int) -> str:
    if over < 6:
        return "powerplay"
    if over < 15:
        return "middle"
    return "death"


def _batting_stats(balls: list[BallDBRecord]) -> dict:
    """Aggregate runs, SR, boundaries, dismissals from a list of balls."""
    total = len(balls)
    if total == 0:
        return {}
    runs = sum(b.runs_scored or 0 for b in balls)
    legal = sum(1 for b in balls if getattr(b, "is_legal_delivery", True))
    dismissals = sum(1 for b in balls if b.outcome == "wicket")
    fours = sum(1 for b in balls if b.outcome == "4")
    sixes = sum(1 for b in balls if b.outcome == "6")
    dot_balls = sum(1 for b in balls if (b.runs_scored or 0) == 0 and b.outcome != "wicket")
    sr = round(runs / legal * 100, 1) if legal else 0
    return {
        "balls": total,
        "runs": runs,
        "strike_rate": sr,
        "dismissals": dismissals,
        "fours": fours,
        "sixes": sixes,
        "dot_balls": dot_balls,
        "dot_pct": round(dot_balls / total * 100, 1) if total else 0,
    }


def _bowling_stats(balls: list[BallDBRecord]) -> dict:
    """Aggregate wickets, economy, dot% from a list of balls."""
    total = len(balls)
    if total == 0:
        return {}
    runs = sum(b.runs_scored or 0 for b in balls)
    wickets = sum(1 for b in balls if b.outcome == "wicket")
    dots = sum(1 for b in balls if (b.runs_scored or 0) == 0 and b.outcome != "wicket")
    overs = total / 6
    economy = round(runs / overs, 2) if overs else 0
    return {
        "balls": total,
        "runs_conceded": runs,
        "wickets": wickets,
        "economy": economy,
        "dot_balls": dots,
        "dot_pct": round(dots / total * 100, 1) if total else 0,
        "avg": round(runs / wickets, 1) if wickets else None,
    }


def _phase_breakdown(balls: list[BallDBRecord], stats_fn) -> dict:
    buckets: dict[str, list] = defaultdict(list)
    for b in balls:
        buckets[_phase(b.over_number)].append(b)
    return {phase: stats_fn(group) for phase, group in buckets.items()}


def _shot_distribution(balls: list[BallDBRecord]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for b in balls:
        shot = b.shot_type or "unknown"
        counts[shot] += 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _footwork_distribution(balls: list[BallDBRecord]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for b in balls:
        fw = b.footwork or "unknown"
        if fw != "unknown":
            counts[fw] += 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _contact_quality_distribution(balls: list[BallDBRecord]) -> dict:
    total = len(balls)
    counts: dict[str, int] = defaultdict(int)
    for b in balls:
        cq = b.contact_quality or "unknown"
        if cq != "unknown":
            counts[cq] += 1
    return {k: {"count": v, "pct": round(v / total * 100, 1) if total else 0}
            for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)}


def _wagon_wheel_data(balls: list[BallDBRecord]) -> dict:
    """Return runs per shot_direction for wagon wheel rendering."""
    direction_runs: dict[str, int] = defaultdict(int)
    for b in balls:
        direction = b.shot_direction or "unknown"
        if direction != "unknown":
            direction_runs[direction] += b.runs_scored or 0
    return dict(direction_runs)


def _dismissal_profile(balls: list[BallDBRecord]) -> dict:
    wicket_balls = [b for b in balls if b.outcome == "wicket"]
    by_type: dict[str, int] = defaultdict(int)
    by_bowler_type: dict[str, int] = defaultdict(int)
    by_length: dict[str, int] = defaultdict(int)
    by_line: dict[str, int] = defaultdict(int)
    for b in wicket_balls:
        by_type[b.dismissal_type or "unknown"] += 1
        by_bowler_type[b.bowler_type or "unknown"] += 1
        by_length[b.length or "unknown"] += 1
        by_line[b.line or "unknown"] += 1
    return {
        "total_dismissals": len(wicket_balls),
        "by_type": dict(by_type),
        "by_bowler_type": dict(by_bowler_type),
        "by_length": dict(by_length),
        "by_line": dict(by_line),
    }


def _heatmap_counts(balls: list[BallDBRecord]) -> dict:
    """Return {(length, line): count} for pitch heatmap."""
    counts: dict[tuple, int] = defaultdict(int)
    for b in balls:
        if b.length and b.line and b.length != "unknown" and b.line != "unknown":
            counts[(b.length, b.line)] += 1
    return {f"{k[0]}|{k[1]}": v for k, v in counts.items()}


# ─── Basic routes ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "Cricket Intelligence Engine", "status": "running", "version": "0.2.0"}


@app.get("/health")
def health():
    return {"status": "healthy", "db_stats": db.get_stats()}


# ─── Matches ──────────────────────────────────────────────────────────────────

@app.post("/matches")
def create_match(match: MatchCreate):
    db.create_match(match.model_dump())
    return {"message": f"Match {match.match_id} created"}


@app.get("/matches")
def list_matches():
    matches = db.list_matches()
    return [
        {
            "match_id": m.match_id,
            "format": m.format,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "venue": m.venue,
            "date": m.date,
        }
        for m in matches
    ]


@app.get("/matches/{match_id}/innings/{innings}/bowlers")
def innings_bowler_report(match_id: str, innings: int):
    """Per-bowler report for a specific match innings — mirrors bowler_report.py output.

    Returns line/length distributions, speed stats, crease, variations,
    per-batter matchups, phase split, and shots played against for every bowler.
    Bowling innings N = same balls as batting innings N (bowlers are fielding side).
    """
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B
        from sqlalchemy import and_
        balls = session.query(B).filter(
            and_(B.match_id == match_id, B.innings == innings)
        ).all()
    finally:
        session.close()

    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls for match {match_id} innings {innings}")

    # Group by bowler preserving first-ball order
    bowler_order: list[str] = []
    by_bowler: dict[str, list] = defaultdict(list)
    for b in sorted(balls, key=lambda x: (x.over_number, x.ball_number)):
        if b.bowler_name and b.bowler_name not in bowler_order:
            bowler_order.append(b.bowler_name)
        if b.bowler_name:
            by_bowler[b.bowler_name].append(b)

    def _dist(bs: list, field: str) -> list[dict]:
        total = len(bs)
        counts: dict[str, int] = defaultdict(int)
        for b in bs:
            val = getattr(b, field, None) or "unknown"
            counts[val] += 1
        return [
            {"value": k, "count": v, "pct": round(v / total * 100, 0)}
            for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def _speed_stats(bs: list) -> dict | None:
        speeds = [b.bowling_speed_kmph for b in bs if b.bowling_speed_kmph]
        if not speeds:
            return None
        return {
            "avg": round(sum(speeds) / len(speeds), 1),
            "min": round(min(speeds), 1),
            "max": round(max(speeds), 1),
            "readings": len(speeds),
        }

    def _crease_dist(bs: list) -> dict:
        counts: dict[str, int] = defaultdict(int)
        for b in bs:
            c = b.bowler_crease or "unknown"
            counts[c] += 1
        return dict(counts)

    def _variations(bs: list) -> dict:
        counts: dict[str, int] = defaultdict(int)
        for b in bs:
            v = b.variation or "none"
            if v not in ("none", "unknown"):
                counts[v] += 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def _matchups(bs: list) -> list[dict]:
        m: dict[str, dict] = defaultdict(lambda: {"balls": 0, "runs": 0, "dots": 0, "wickets": 0})
        for b in bs:
            key = b.batsman_name or "unknown"
            m[key]["balls"] += 1
            m[key]["runs"] += b.runs_scored or 0
            if (b.runs_scored or 0) == 0:
                m[key]["dots"] += 1
            if b.outcome == "wicket":
                m[key]["wickets"] += 1
        return [
            {"batter": k, "balls": v["balls"], "runs": v["runs"],
             "dots": v["dots"], "wickets": v["wickets"],
             "avg_per_ball": round(v["runs"] / v["balls"], 2) if v["balls"] else 0}
            for k, v in sorted(m.items(), key=lambda x: x[1]["balls"], reverse=True)
        ]

    def _phase_split(bs: list) -> list[dict]:
        buckets: dict[str, list] = defaultdict(list)
        for b in bs:
            buckets[_phase(b.over_number)].append(b)
        rows = []
        for phase in ["powerplay", "middle", "death"]:
            if phase not in buckets:
                continue
            pb = buckets[phase]
            total = len(pb)
            runs = sum(b.runs_scored or 0 for b in pb)
            dots = sum(1 for b in pb if (b.runs_scored or 0) == 0)
            wkts = sum(1 for b in pb if b.outcome == "wicket")
            rows.append({"phase": phase, "balls": total, "runs": runs, "dots": dots, "wickets": wkts})
        return rows

    def _shots_against(bs: list) -> list[dict]:
        counts: dict[str, int] = defaultdict(int)
        for b in bs:
            shot = b.shot_type or "unknown"
            if shot != "unknown":
                counts[shot] += 1
        return [{"shot": k, "count": v}
                for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]]

    bowlers = []
    for name in bowler_order:
        bs = by_bowler[name]
        total = len(bs)
        runs = sum(b.runs_scored or 0 for b in bs)
        wkts = sum(1 for b in bs if b.outcome == "wicket")
        dots = sum(1 for b in bs if (b.runs_scored or 0) == 0)
        overs = round(total / 6, 1)
        economy = round(runs / (total / 6), 2) if total else 0

        bowlers.append({
            "name": name,
            "balls": total,
            "overs": overs,
            "runs": runs,
            "wickets": wkts,
            "dots": dots,
            "dot_pct": round(dots / total * 100, 1) if total else 0,
            "economy": economy,
            "speed": _speed_stats(bs),
            "crease": _crease_dist(bs),
            "variations": _variations(bs),
            "line_dist": _dist(bs, "line"),
            "length_dist": _dist(bs, "length"),
            "matchups": _matchups(bs),
            "phase_split": _phase_split(bs),
            "shots_against": _shots_against(bs),
        })

    match = db.get_match(match_id)
    return {
        "match_id": match_id,
        "innings": innings,
        "bowling_team": match.team_b if innings == 1 else match.team_a if match else None,
        "batting_team": match.team_a if innings == 1 else match.team_b if match else None,
        "bowlers": bowlers,
    }


@app.get("/matches/{match_id}")
def get_match(match_id: str):
    match = db.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    balls = db.get_balls_for_match(match_id)
    return {
        "match_id": match.match_id,
        "format": match.format,
        "team_a": match.team_a,
        "team_b": match.team_b,
        "venue": match.venue,
        "date": match.date,
        "total_balls": len(balls),
        "innings": _summarise_innings(balls),
    }


@app.get("/matches/{match_id}/innings/{innings}/batsmen")
def innings_batsman_report(match_id: str, innings: int):
    """Per-batsman report for a specific match innings — mirrors batsman_report.py output.

    Returns line/length faced distributions, shot types, footwork, contact quality,
    per-bowler matchups, phase split, and scoring zones for every batter in the innings.
    """
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B
        from sqlalchemy import and_
        balls = session.query(B).filter(
            and_(B.match_id == match_id, B.innings == innings)
        ).all()
    finally:
        session.close()

    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls for match {match_id} innings {innings}")

    # Group by batsman in batting order (first appearance)
    batsman_order: list[str] = []
    by_batsman: dict[str, list] = defaultdict(list)
    for b in sorted(balls, key=lambda x: (x.over_number, x.ball_number)):
        if b.batsman_name and b.batsman_name not in batsman_order:
            batsman_order.append(b.batsman_name)
        if b.batsman_name:
            by_batsman[b.batsman_name].append(b)

    def _line_length_dist(bs: list, field: str) -> list[dict]:
        total = len(bs)
        counts: dict[str, int] = defaultdict(int)
        for b in bs:
            val = getattr(b, field, None) or "unknown"
            counts[val] += 1
        return [
            {"value": k, "count": v, "pct": round(v / total * 100, 0)}
            for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def _matchups(bs: list) -> list[dict]:
        m: dict[str, dict] = defaultdict(lambda: {"balls": 0, "runs": 0, "dots": 0, "dismissed": False})
        for b in bs:
            key = b.bowler_name or "unknown"
            m[key]["balls"] += 1
            m[key]["runs"] += b.runs_scored or 0
            if (b.runs_scored or 0) == 0:
                m[key]["dots"] += 1
            if b.outcome == "wicket":
                m[key]["dismissed"] = True
        return [
            {"bowler": k, "balls": v["balls"], "runs": v["runs"],
             "dots": v["dots"], "sr": round(v["runs"] / v["balls"] * 100, 1),
             "dismissed": v["dismissed"]}
            for k, v in sorted(m.items(), key=lambda x: x[1]["balls"], reverse=True)
        ]

    def _phase_split(bs: list) -> list[dict]:
        buckets: dict[str, list] = defaultdict(list)
        for b in bs:
            buckets[_phase(b.over_number)].append(b)
        rows = []
        for phase in ["powerplay", "middle", "death"]:
            if phase not in buckets:
                continue
            pb = buckets[phase]
            total = len(pb)
            runs = sum(b.runs_scored or 0 for b in pb)
            dots = sum(1 for b in pb if (b.runs_scored or 0) == 0)
            fours = sum(1 for b in pb if (b.runs_scored or 0) == 4)
            sixes = sum(1 for b in pb if (b.runs_scored or 0) == 6)
            rows.append({
                "phase": phase, "balls": total, "runs": runs, "dots": dots,
                "fours": fours, "sixes": sixes,
                "sr": round(runs / total * 100, 1) if total else 0,
            })
        return rows

    batsmen = []
    for name in batsman_order:
        bs = by_batsman[name]
        total = len(bs)
        runs = sum(b.runs_scored or 0 for b in bs)
        fours = sum(1 for b in bs if (b.runs_scored or 0) == 4)
        sixes = sum(1 for b in bs if (b.runs_scored or 0) == 6)
        dots = sum(1 for b in bs if (b.runs_scored or 0) == 0)
        dismissed = any(b.outcome == "wicket" for b in bs)
        dismissal_ball = next((b for b in bs if b.outcome == "wicket"), None)

        batsmen.append({
            "name": name,
            "handedness": next((b.batsman_handedness for b in bs if b.batsman_handedness and b.batsman_handedness != "unknown"), "unknown"),
            "balls": total,
            "runs": runs,
            "sr": round(runs / total * 100, 2) if total else 0,
            "fours": fours,
            "sixes": sixes,
            "dots": dots,
            "dot_pct": round(dots / total * 100, 1) if total else 0,
            "dismissed": dismissed,
            "dismissal": {
                "type": dismissal_ball.dismissal_type,
                "fielder": dismissal_ball.dismissal_fielder,
                "bowler": dismissal_ball.bowler_name,
                "over": dismissal_ball.over_number,
                "ball": dismissal_ball.ball_number,
            } if dismissal_ball else None,
            "line_faced": _line_length_dist(bs, "line"),
            "length_faced": _line_length_dist(bs, "length"),
            "shot_types": [{"shot": k, "count": v} for k, v in
                           sorted(_shot_distribution(bs).items(), key=lambda x: x[1], reverse=True)[:15]],
            "footwork": _footwork_distribution(bs),
            "contact_quality": _contact_quality_distribution(bs),
            "scoring_zones": dict(sorted(_wagon_wheel_data(bs).items(), key=lambda x: x[1], reverse=True)),
            "matchups": _matchups(bs),
            "phase_split": _phase_split(bs),
        })

    match = db.get_match(match_id)
    return {
        "match_id": match_id,
        "innings": innings,
        "venue": match.venue if match else None,
        "team_a": match.team_a if match else None,
        "team_b": match.team_b if match else None,
        "batting_team": match.team_a if innings == 1 else match.team_b if match else None,
        "total_balls": len(balls),
        "batsmen": batsmen,
    }


def _summarise_innings(balls: list[BallDBRecord]) -> list[dict]:
    by_innings: dict[int, list] = defaultdict(list)
    for b in balls:
        by_innings[b.innings].append(b)
    result = []
    for innings_num in sorted(by_innings.keys()):
        inn_balls = by_innings[innings_num]
        batting_team = inn_balls[0].innings_team if hasattr(inn_balls[0], "innings_team") else "unknown"
        runs = sum(b.runs_scored or 0 for b in inn_balls)
        wickets = sum(1 for b in inn_balls if b.outcome == "wicket")
        result.append({
            "innings": innings_num,
            "runs": runs,
            "wickets": wickets,
            "balls": len(inn_balls),
        })
    return result


# ─── Players ──────────────────────────────────────────────────────────────────

@app.get("/players")
def list_players(
    role: Optional[str] = Query(default=None, description="batsman | bowler | all"),
    match_id: Optional[str] = None,
    team: Optional[str] = None,
):
    """List all players in the DB with ball counts."""
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B
        from sqlalchemy import func

        batsmen = (
            session.query(B.batsman_name, func.count(B.ball_id).label("balls_faced"))
            .filter(B.batsman_name.isnot(None), B.batsman_name != "")
            .group_by(B.batsman_name)
            .all()
        )
        bowlers = (
            session.query(B.bowler_name, func.count(B.ball_id).label("balls_bowled"))
            .filter(B.bowler_name.isnot(None), B.bowler_name != "")
            .group_by(B.bowler_name)
            .all()
        )

        batter_map = {r.batsman_name: r.balls_faced for r in batsmen}
        bowler_map = {r.bowler_name: r.balls_bowled for r in bowlers}
        all_names = set(batter_map) | set(bowler_map)

        players = []
        for name in sorted(all_names):
            players.append({
                "name": name,
                "balls_faced": batter_map.get(name, 0),
                "balls_bowled": bowler_map.get(name, 0),
            })

        if role == "batsman":
            players = [p for p in players if p["balls_faced"] > 0]
        elif role == "bowler":
            players = [p for p in players if p["balls_bowled"] > 0]

        return players
    finally:
        session.close()


# ─── Batting profile ──────────────────────────────────────────────────────────

@app.get("/players/{name}/batting")
def batting_profile(
    name: str,
    match_id: Optional[str] = None,
    min_confidence: float = Query(default=0.3, ge=0.0, le=1.0),
    narrative: bool = Query(default=False, description="Include Gemini AI narrative (slower, ~3s)"),
):
    """Full batting profile: stats, phases, shot distribution, dismissals, weakness + AI narrative."""
    balls = db.get_balls_for_batsman(name, match_id=match_id, min_confidence=min_confidence)
    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls found for '{name}'")

    from src.analytics.weakness import compute_weakness_profile

    handedness = balls[0].batsman_handedness or "unknown"
    weakness = compute_weakness_profile(balls, batsman_name=name)

    result = {
        "name": name,
        "handedness": handedness,
        "matches_played": len({b.match_id for b in balls}),
        "overall": _batting_stats(balls),
        "by_phase": _phase_breakdown(balls, _batting_stats),
        "shot_distribution": _shot_distribution(balls),
        "footwork": _footwork_distribution(balls),
        "contact_quality": _contact_quality_distribution(balls),
        "wagon_wheel": _wagon_wheel_data(balls),
        "dismissals": _dismissal_profile(balls),
        "weakness_profile": weakness,
        "pitch_heatmap_counts": _heatmap_counts(balls),
        "narrative": None,
    }

    if narrative:
        from match_intelligence.lib.weakness_narrator import narrate_weakness

        cached = db.get_narrative(name, role="batsman")
        if cached:
            result["narrative"] = cached.narrative_json
            result["narrative_meta"] = {
                "cached": True,
                "generated_at": cached.generated_at.isoformat(),
                "model_used": cached.model_used,
                "based_on_balls": cached.total_balls,
                "based_on_matches": cached.total_matches,
                "matches": cached.matches_metadata,
            }
        else:
            generated = narrate_weakness(weakness)
            # Build per-match metadata for display
            match_ids = list({b.match_id for b in balls})
            matches_meta = []
            for mid in match_ids:
                m = db.get_match(mid)
                match_balls = [b for b in balls if b.match_id == mid]
                runs = sum(b.runs_scored or 0 for b in match_balls)
                dismissed = any(b.outcome == "wicket" for b in match_balls)
                dismissal = next(
                    (b.dismissal_type for b in match_balls if b.outcome == "wicket"), None
                )
                matches_meta.append({
                    "match_id": mid,
                    "date": m.date if m else None,
                    "year": m.date[:4] if m and m.date else None,
                    "venue": m.venue if m else None,
                    "team_a": m.team_a if m else None,
                    "team_b": m.team_b if m else None,
                    "format": m.format if m else "T20",
                    "day_or_night": m.day_or_night if m else "unknown",
                    "balls_faced": len(match_balls),
                    "runs_scored": runs,
                    "dismissed": dismissed,
                    "dismissal_type": dismissal,
                })

            db.save_narrative(
                player_name=name,
                role="batsman",
                narrative_json=generated,
                matches_metadata=matches_meta,
                total_balls=len(balls),
                total_matches=len(match_ids),
                total_runs=sum(b.runs_scored or 0 for b in balls),
                model_used="gemini-2.5-pro",
            )
            result["narrative"] = generated
            result["narrative_meta"] = {
                "cached": False,
                "generated_at": None,
                "model_used": "gemini-2.5-pro",
                "based_on_balls": len(balls),
                "based_on_matches": len(match_ids),
                "matches": matches_meta,
            }

    return result


@app.get("/players/{name}/heatmap")
def batting_heatmap(
    name: str,
    match_id: Optional[str] = None,
    min_confidence: float = Query(default=0.3, ge=0.0, le=1.0),
):
    """Return pitch heatmap data (line × length counts) for a batter."""
    balls = db.get_balls_for_batsman(name, match_id=match_id, min_confidence=min_confidence)
    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls found for '{name}'")
    return {
        "name": name,
        "total_balls": len(balls),
        "heatmap": _heatmap_counts(balls),
        "danger_zones": compute_danger_zones(balls),
    }


def compute_danger_zones(balls: list[BallDBRecord]) -> list[dict]:
    from src.analytics.weakness import compute_weakness_profile
    profile = compute_weakness_profile(balls)
    return [z for z in profile.get("zones", []) if z["danger_score"] > 0.3]


@app.get("/players/{name}/wagon-wheel")
def wagon_wheel(
    name: str,
    match_id: Optional[str] = None,
):
    """Return wagon wheel direction data (runs per field region)."""
    balls = db.get_balls_for_batsman(name, match_id=match_id, min_confidence=0.0)
    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls found for '{name}'")
    handedness = balls[0].batsman_handedness or "right_handed"
    return {
        "name": name,
        "handedness": handedness,
        "total_runs": sum(b.runs_scored or 0 for b in balls),
        "direction_runs": _wagon_wheel_data(balls),
    }


@app.get("/players/{name}/phases")
def batting_phases(
    name: str,
    match_id: Optional[str] = None,
):
    """Phase breakdown (powerplay / middle / death) for a batter."""
    balls = db.get_balls_for_batsman(name, match_id=match_id, min_confidence=0.0)
    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls found for '{name}'")
    return {
        "name": name,
        "phases": _phase_breakdown(balls, _batting_stats),
    }


# ─── Bowling profile ──────────────────────────────────────────────────────────

@app.get("/players/{name}/bowling")
def bowling_profile(
    name: str,
    match_id: Optional[str] = None,
):
    """Full bowling profile: stats, phases, line/length map, variation breakdown."""
    balls = _get_balls_for_bowler(name, match_id)
    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls found for bowler '{name}'")

    return {
        "name": name,
        "matches": len({b.match_id for b in balls}),
        "overall": _bowling_stats(balls),
        "by_phase": _phase_breakdown(balls, _bowling_stats),
        "line_length_map": _heatmap_counts(balls),
        "by_variation": _crosstab_bowling(balls, "variation"),
        "by_line": _crosstab_bowling(balls, "line"),
        "by_length": _crosstab_bowling(balls, "length"),
        "wicket_delivery_profile": _wicket_delivery_profile(balls),
    }


def _get_balls_for_bowler(name: str, match_id: Optional[str] = None) -> list[BallDBRecord]:
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B
        query = session.query(B).filter(B.bowler_name.ilike(f"%{name}%"))
        if match_id:
            query = query.filter_by(match_id=match_id)
        return query.all()
    finally:
        session.close()


def _crosstab_bowling(balls: list[BallDBRecord], field: str) -> dict:
    buckets: dict[str, list] = defaultdict(list)
    for b in balls:
        key = getattr(b, field, None) or "unknown"
        buckets[key].append(b)
    return {k: _bowling_stats(v) for k, v in buckets.items() if len(v) >= 2}


def _wicket_delivery_profile(balls: list[BallDBRecord]) -> dict:
    wicket_balls = [b for b in balls if b.outcome == "wicket"]
    by_length: dict[str, int] = defaultdict(int)
    by_line: dict[str, int] = defaultdict(int)
    by_variation: dict[str, int] = defaultdict(int)
    for b in wicket_balls:
        by_length[b.length or "unknown"] += 1
        by_line[b.line or "unknown"] += 1
        by_variation[b.variation or "none"] += 1
    return {
        "total_wickets": len(wicket_balls),
        "by_length": dict(by_length),
        "by_line": dict(by_line),
        "by_variation": dict(by_variation),
    }


# ─── Head-to-head matchup ─────────────────────────────────────────────────────

@app.get("/matchup")
def head_to_head(
    bowler: str = Query(..., description="Bowler name (partial match)"),
    batsman: str = Query(..., description="Batsman name (partial match)"),
    match_id: Optional[str] = None,
):
    """Specific bowler vs batsman matchup across all matches."""
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B
        query = session.query(B).filter(
            B.bowler_name.ilike(f"%{bowler}%"),
            B.batsman_name.ilike(f"%{batsman}%"),
        )
        if match_id:
            query = query.filter_by(match_id=match_id)
        balls = query.all()
    finally:
        session.close()

    if not balls:
        raise HTTPException(
            status_code=404,
            detail=f"No balls found for matchup: {bowler} vs {batsman}",
        )

    from src.analytics.weakness import compute_weakness_profile

    runs = sum(b.runs_scored or 0 for b in balls)
    wickets = sum(1 for b in balls if b.outcome == "wicket")
    dots = sum(1 for b in balls if (b.runs_scored or 0) == 0 and b.outcome != "wicket")

    return {
        "bowler": balls[0].bowler_name,
        "batsman": balls[0].batsman_name,
        "matches": len({b.match_id for b in balls}),
        "balls": len(balls),
        "runs": runs,
        "wickets": wickets,
        "dot_balls": dots,
        "strike_rate": round(runs / len(balls) * 100, 1) if balls else 0,
        "economy": round(runs / (len(balls) / 6), 2) if balls else 0,
        "dismissal_rate": round(wickets / len(balls), 3) if balls else 0,
        "shot_distribution": _shot_distribution(balls),
        "pitch_heatmap": _heatmap_counts(balls),
        "weakness_zones": compute_weakness_profile(balls, min_sample=1).get("zones", []),
        "raw_balls": [
            {
                "match_id": b.match_id,
                "over": b.over_number,
                "ball": b.ball_number,
                "line": b.line,
                "length": b.length,
                "variation": b.variation,
                "outcome": b.outcome,
                "runs": b.runs_scored,
                "shot_type": b.shot_type,
                "contact_quality": b.contact_quality,
                "description": b.raw_description,
            }
            for b in balls
        ],
    }


# ─── Team weakness (Opposition Prep) ─────────────────────────────────────────

@app.get("/team/{team_name}/weaknesses")
def team_weaknesses(
    team_name: str,
    match_id: Optional[str] = None,
    top_n: int = Query(default=50, ge=1, le=100),
):
    """
    Batting weakness profile for every player in a team.
    Used for opposition prep — 'how do we bowl to this team?'
    """
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B, MatchRecord as M
        # Identify which matches this team played in and which innings they batted
        # team_a bats in innings 1, team_b bats in innings 2 (standard T20 convention)
        match_rows = session.query(M).filter(
            (M.team_a.ilike(f"%{team_name}%")) | (M.team_b.ilike(f"%{team_name}%"))
        ).all()
        if not match_rows:
            raise HTTPException(status_code=404, detail=f"No matches found for team '{team_name}'")

        # Build set of (match_id, innings) where this team batted
        batting_innings: list[tuple[str, int]] = []
        for m in match_rows:
            if match_id and m.match_id != match_id:
                continue
            if team_name.lower() in (m.team_a or "").lower():
                batting_innings.append((m.match_id, 1))
            if team_name.lower() in (m.team_b or "").lower():
                batting_innings.append((m.match_id, 2))

        if not batting_innings:
            raise HTTPException(status_code=404, detail=f"No batting innings found for team '{team_name}'")

        from sqlalchemy import or_, and_
        conditions = [and_(B.match_id == mid, B.innings == inn) for mid, inn in batting_innings]
        balls = session.query(B).filter(or_(*conditions)).all()
    finally:
        session.close()

    if not balls:
        raise HTTPException(status_code=404, detail=f"No balls found for team '{team_name}'")

    from src.analytics.weakness import compute_weakness_profile

    by_player: dict[str, list] = defaultdict(list)
    for b in balls:
        if b.batsman_name:
            by_player[b.batsman_name].append(b)

    profiles = []
    for player_name, player_balls in by_player.items():
        if len(player_balls) < 6:
            continue
        profile = compute_weakness_profile(player_balls, batsman_name=player_name)
        profiles.append({
            "player": player_name,
            "balls_faced": len(player_balls),
            "top_weakness": profile.get("top_weakness"),
            "danger_zones": [z for z in profile.get("zones", []) if z["danger_score"] > 0.3],
        })

    profiles.sort(key=lambda p: len(p["danger_zones"]), reverse=True)
    return {
        "team": team_name,
        "match_id": match_id,
        "players_analysed": len(profiles),
        "profiles": profiles[:top_n],
    }


# ─── Insights ─────────────────────────────────────────────────────────────────

@app.get("/insights")
def get_insights(match_id: Optional[str] = None, batsman_name: Optional[str] = None):
    """Pre-computed answers to analytical questions for the Insights page."""
    session = db.get_session()
    try:
        from src.storage.db import BallDBRecord as B
        q = session.query(B)
        if match_id:
            q = q.filter(B.match_id == match_id)
        if batsman_name:
            q = q.filter(B.batsman_name.ilike(f"%{batsman_name}%"))
        balls = q.all()
    finally:
        session.close()

    if not balls:
        return {
            "top_danger_zone": None, "most_wicket_zone": None,
            "spin_vs_pace": [], "phase_vulnerability": [],
            "leg_side_reliant": [], "bowler_best_variation": [],
            "bowler_phase_economy": [], "anchors_vs_strokemakers": [],
            "shot_zone_map": [], "shot_false_shot_rate": [],
            "top_shot_per_zone": [], "dismissal_shot_type": [],
        }

    FALSE_SHOT = {"edge", "miss", "mistimed"}
    LEG_DIRS = {"fine_leg", "deep_fine_leg", "square_leg", "deep_square_leg",
                "mid_wicket", "deep_mid_wicket", "mid_on", "long_on"}
    OFF_DIRS = {"cover", "deep_cover", "point", "deep_point", "third_man",
                "deep_third", "mid_off", "long_off"}

    # 1. Zone danger & wicket stats
    zone_stats: dict = defaultdict(lambda: {"total": 0, "wickets": 0, "false_shots": 0, "runs": 0, "batsmen": set()})
    for b in balls:
        if not b.line or not b.length:
            continue
        k = f"{b.length}|{b.line}"
        z = zone_stats[k]
        z["total"] += 1
        if b.batsman_name:
            z["batsmen"].add(b.batsman_name)
        if b.outcome == "wicket":
            z["wickets"] += 1
        if (b.contact_quality or "") in FALSE_SHOT:
            z["false_shots"] += 1
        z["runs"] += b.runs_scored or 0

    best_zone = None
    best_score = 0
    most_wicket_zone = None
    most_wickets = 0
    for k, z in zone_stats.items():
        if z["total"] < 4:
            continue
        dr = z["wickets"] / z["total"]
        fsr = z["false_shots"] / z["total"]
        score = dr * 0.6 + fsr * 0.4
        length, line = k.split("|", 1)
        if score > best_score:
            best_score = score
            best_zone = {"line": line, "length": length, "dismissals": z["wickets"],
                         "total": z["total"], "false_shots": z["false_shots"],
                         "danger_score": round(score, 2), "top_batsmen": list(z["batsmen"])[:3]}
        if z["wickets"] > most_wickets:
            most_wickets = z["wickets"]
            most_wicket_zone = {"line": line, "length": length, "wickets": z["wickets"],
                                "total": z["total"], "dismissal_rate": round(dr, 2)}

    # 2. Spin vs pace false shot rate
    pbtype: dict = defaultdict(lambda: defaultdict(lambda: {"total": 0, "false_shots": 0}))
    for b in balls:
        if not b.batsman_name or not b.bowler_type:
            continue
        bt = "spin" if "spin" in (b.bowler_type or "").lower() else "pace"
        s = pbtype[b.batsman_name][bt]
        s["total"] += 1
        if (b.contact_quality or "") in FALSE_SHOT:
            s["false_shots"] += 1

    spin_vs_pace = []
    for player, by_type in pbtype.items():
        pace = by_type.get("pace", {"total": 0, "false_shots": 0})
        spin = by_type.get("spin", {"total": 0, "false_shots": 0})
        if pace["total"] < 5 or spin["total"] < 3:
            continue
        p_fsr = round(pace["false_shots"] / pace["total"], 2)
        s_fsr = round(spin["false_shots"] / spin["total"], 2)
        spin_vs_pace.append({"player": player, "pace_balls": pace["total"], "spin_balls": spin["total"],
                             "pace_false_shot_rate": p_fsr, "spin_false_shot_rate": s_fsr,
                             "weaker_vs": "spin" if s_fsr > p_fsr else "pace"})
    spin_vs_pace.sort(key=lambda x: abs(x["spin_false_shot_rate"] - x["pace_false_shot_rate"]), reverse=True)

    # 3. Phase vulnerability
    pphase: dict = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "runs": 0}))
    for b in balls:
        if not b.batsman_name or not b.phase:
            continue
        s = pphase[b.batsman_name][b.phase]
        s["balls"] += 1
        s["runs"] += b.runs_scored or 0

    phase_vulnerability = []
    for player, phases in pphase.items():
        pp = phases.get("powerplay", {"balls": 0, "runs": 0})
        md = phases.get("middle", {"balls": 0, "runs": 0})
        dt = phases.get("death", {"balls": 0, "runs": 0})
        if pp["balls"] < 4:
            continue
        pp_sr = round(pp["runs"] / pp["balls"] * 100, 1) if pp["balls"] else 0
        md_sr = round(md["runs"] / md["balls"] * 100, 1) if md["balls"] else 0
        dt_sr = round(dt["runs"] / dt["balls"] * 100, 1) if dt["balls"] else 0
        active = {k: v for k, v in [("powerplay", pp_sr), ("middle", md_sr), ("death", dt_sr)] if v > 0}
        if not active:
            continue
        phase_vulnerability.append({
            "player": player, "powerplay_sr": pp_sr, "middle_sr": md_sr, "death_sr": dt_sr,
            "weakest_phase": min(active, key=active.get), "strongest_phase": max(active, key=active.get),
            "pp_balls": pp["balls"], "md_balls": md["balls"], "dt_balls": dt["balls"],
        })
    phase_vulnerability.sort(key=lambda x: x.get(f"{x['weakest_phase']}_sr", 0))

    # 4. Leg-side reliance
    pdirs: dict = defaultdict(lambda: {"leg": 0, "off": 0, "total": 0})
    for b in balls:
        if not b.batsman_name or not b.shot_direction:
            continue
        d = (b.shot_direction or "").lower()
        pd = pdirs[b.batsman_name]
        pd["total"] += 1
        if d in LEG_DIRS:
            pd["leg"] += 1
        elif d in OFF_DIRS:
            pd["off"] += 1

    leg_side_reliant = []
    for player, dirs in pdirs.items():
        if dirs["total"] < 8:
            continue
        leg_side_reliant.append({
            "player": player,
            "leg_pct": round(dirs["leg"] / dirs["total"] * 100),
            "off_pct": round(dirs["off"] / dirs["total"] * 100),
            "total_shots": dirs["total"],
        })
    leg_side_reliant.sort(key=lambda x: x["leg_pct"], reverse=True)

    # 5. Best wicket variation per bowler
    bvar: dict = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "wickets": 0, "false_shots": 0}))
    for b in balls:
        if not b.bowler_name or not b.variation or b.variation in ("normal", "unknown", ""):
            continue
        s = bvar[b.bowler_name][b.variation]
        s["balls"] += 1
        if b.outcome == "wicket":
            s["wickets"] += 1
        if (b.contact_quality or "") in FALSE_SHOT:
            s["false_shots"] += 1

    bowler_best_variation = []
    for bowler, variations in bvar.items():
        best = max(({"variation": v, **s} for v, s in variations.items() if s["balls"] >= 3),
                   key=lambda x: (x["wickets"], x["false_shots"]), default=None)
        if best and best["wickets"] > 0:
            bowler_best_variation.append({"bowler": bowler, **best})
    bowler_best_variation.sort(key=lambda x: x["wickets"], reverse=True)

    # 6. Bowler phase economy
    bphase: dict = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "runs": 0}))
    for b in balls:
        if not b.bowler_name or not b.phase:
            continue
        s = bphase[b.bowler_name][b.phase]
        s["balls"] += 1
        s["runs"] += b.runs_scored or 0

    bowler_phase_economy = []
    for bowler, phases in bphase.items():
        pp = phases.get("powerplay", {"balls": 0, "runs": 0})
        md = phases.get("middle", {"balls": 0, "runs": 0})
        dt = phases.get("death", {"balls": 0, "runs": 0})
        pp_eco = round(pp["runs"] / pp["balls"] * 6, 1) if pp["balls"] >= 6 else None
        md_eco = round(md["runs"] / md["balls"] * 6, 1) if md["balls"] >= 6 else None
        dt_eco = round(dt["runs"] / dt["balls"] * 6, 1) if dt["balls"] >= 6 else None
        if not any([pp_eco, md_eco, dt_eco]):
            continue
        bowler_phase_economy.append({
            "bowler": bowler, "powerplay": pp_eco, "middle": md_eco, "death": dt_eco,
            "pp_balls": pp["balls"], "md_balls": md["balls"], "dt_balls": dt["balls"],
        })
    bowler_phase_economy.sort(key=lambda x: x["powerplay"] or 99)

    # 7. Anchor vs strokemaker
    poverall: dict = defaultdict(lambda: {"balls": 0, "runs": 0})
    for b in balls:
        if not b.batsman_name:
            continue
        s = poverall[b.batsman_name]
        s["balls"] += 1
        s["runs"] += b.runs_scored or 0

    all_balls = sum(s["balls"] for s in poverall.values())
    all_runs = sum(s["runs"] for s in poverall.values())
    avg_sr = (all_runs / all_balls * 100) if all_balls > 0 else 130.0

    anchors_vs_strokemakers = []
    for player, s in poverall.items():
        if s["balls"] < 10:
            continue
        sr = round(s["runs"] / s["balls"] * 100, 1)
        role = "anchor" if sr < avg_sr * 0.85 else ("strokemaker" if sr > avg_sr * 1.15 else "balanced")
        anchors_vs_strokemakers.append({"player": player, "balls": s["balls"], "runs": s["runs"],
                                        "sr": sr, "role": role, "avg_sr": round(avg_sr, 1)})
    anchors_vs_strokemakers.sort(key=lambda x: x["sr"])

    # 8. Shot type × line/length — which shot is played most in each zone
    #    and how often it results in a false shot or wicket
    shot_zone: dict = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "wickets": 0, "false_shots": 0, "runs": 0}))
    for b in balls:
        if not b.line or not b.length or not b.shot_type or b.shot_type in ("unknown", ""):
            continue
        s = shot_zone[f"{b.length}|{b.line}"][b.shot_type]
        s["balls"] += 1
        if b.outcome == "wicket":
            s["wickets"] += 1
        if (b.contact_quality or "") in FALSE_SHOT:
            s["false_shots"] += 1
        s["runs"] += b.runs_scored or 0

    shot_zone_map = []
    for zone_key, shots in shot_zone.items():
        length, line = zone_key.split("|", 1)
        total_balls = sum(s["balls"] for s in shots.values())
        if total_balls < 4:
            continue
        top_shot = max(shots.items(), key=lambda x: x[1]["balls"])
        shot_name, top_s = top_shot
        shot_zone_map.append({
            "line": line, "length": length,
            "top_shot": shot_name,
            "shot_balls": top_s["balls"],
            "shot_pct": round(top_s["balls"] / total_balls * 100),
            "wickets": top_s["wickets"],
            "false_shots": top_s["false_shots"],
            "avg_runs": round(top_s["runs"] / top_s["balls"], 2) if top_s["balls"] else 0,
            "zone_total": total_balls,
        })
    shot_zone_map.sort(key=lambda x: x["false_shots"], reverse=True)

    # 9. Per shot type — false shot rate and dismissal rate (how risky is each shot?)
    shot_stats: dict = defaultdict(lambda: {"balls": 0, "wickets": 0, "false_shots": 0, "runs": 0})
    for b in balls:
        if not b.shot_type or b.shot_type in ("unknown", ""):
            continue
        s = shot_stats[b.shot_type]
        s["balls"] += 1
        if b.outcome == "wicket":
            s["wickets"] += 1
        if (b.contact_quality or "") in FALSE_SHOT:
            s["false_shots"] += 1
        s["runs"] += b.runs_scored or 0

    shot_false_shot_rate = []
    for shot, s in shot_stats.items():
        if s["balls"] < 3:
            continue
        shot_false_shot_rate.append({
            "shot_type": shot,
            "balls": s["balls"],
            "false_shot_rate": round(s["false_shots"] / s["balls"], 2),
            "dismissal_rate": round(s["wickets"] / s["balls"], 2),
            "avg_runs": round(s["runs"] / s["balls"], 2),
            "wickets": s["wickets"],
        })
    shot_false_shot_rate.sort(key=lambda x: x["false_shot_rate"], reverse=True)

    # 10. Top scoring shot per line/length zone (strength signal — what shot to play)
    top_shot_per_zone = []
    for zone_key, shots in shot_zone.items():
        length, line = zone_key.split("|", 1)
        qualifying = [(name, s) for name, s in shots.items() if s["balls"] >= 2]
        if not qualifying:
            continue
        best = max(qualifying, key=lambda x: x[1]["runs"] / x[1]["balls"] if x[1]["balls"] else 0)
        shot_name, best_s = best
        top_shot_per_zone.append({
            "line": line, "length": length,
            "best_shot": shot_name,
            "avg_runs": round(best_s["runs"] / best_s["balls"], 2) if best_s["balls"] else 0,
            "balls": best_s["balls"],
            "boundaries": sum(1 for _ in range(best_s["balls"])),  # approximation
        })
    top_shot_per_zone.sort(key=lambda x: x["avg_runs"], reverse=True)

    # 11. What shot type leads to most dismissals? (coaching signal)
    dismissal_shot_type = [
        {"shot_type": s["shot_type"], "wickets": s["wickets"],
         "balls": s["balls"], "dismissal_rate": s["dismissal_rate"]}
        for s in shot_false_shot_rate if s["wickets"] > 0
    ]
    dismissal_shot_type.sort(key=lambda x: x["dismissal_rate"], reverse=True)

    return {
        "top_danger_zone": best_zone,
        "most_wicket_zone": most_wicket_zone,
        "spin_vs_pace": spin_vs_pace[:8],
        "phase_vulnerability": phase_vulnerability[:8],
        "leg_side_reliant": leg_side_reliant[:8],
        "bowler_best_variation": bowler_best_variation[:8],
        "bowler_phase_economy": bowler_phase_economy[:8],
        "anchors_vs_strokemakers": anchors_vs_strokemakers[:10],
        "shot_zone_map": shot_zone_map[:10],
        "shot_false_shot_rate": shot_false_shot_rate[:10],
        "top_shot_per_zone": top_shot_per_zone[:8],
        "dismissal_shot_type": dismissal_shot_type[:8],
    }


# ─── Series summary ───────────────────────────────────────────────────────────

@app.get("/series/summary")
def series_summary(
    team_a: Optional[str] = None,
    team_b: Optional[str] = None,
):
    """Cross-match series overview — match results, top performers."""
    matches = db.list_matches()
    if team_a:
        matches = [m for m in matches if team_a.lower() in (m.team_a or "").lower() or team_a.lower() in (m.team_b or "").lower()]
    if team_b:
        matches = [m for m in matches if team_b.lower() in (m.team_a or "").lower() or team_b.lower() in (m.team_b or "").lower()]

    result = []
    for m in matches:
        balls = db.get_balls_for_match(m.match_id)
        result.append({
            "match_id": m.match_id,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "venue": m.venue,
            "date": m.date,
            "total_balls": len(balls),
        })

    return {"matches": result, "total_matches": len(result)}


# ─── Player comparison (Scouting) ─────────────────────────────────────────────

@app.get("/players/compare")
def compare_players(
    player_a: str = Query(..., description="First player name"),
    player_b: str = Query(..., description="Second player name"),
    role: str = Query(default="batsman", description="batsman | bowler"),
    match_id: Optional[str] = None,
):
    """Side-by-side player comparison for scouting."""
    if role == "bowler":
        balls_a = _get_balls_for_bowler(player_a, match_id)
        balls_b = _get_balls_for_bowler(player_b, match_id)
        stats_fn = _bowling_stats
        phase_fn = lambda balls: _phase_breakdown(balls, _bowling_stats)
    else:
        balls_a = db.get_balls_for_batsman(player_a, match_id=match_id, min_confidence=0.0)
        balls_b = db.get_balls_for_batsman(player_b, match_id=match_id, min_confidence=0.0)
        stats_fn = _batting_stats
        phase_fn = lambda balls: _phase_breakdown(balls, _batting_stats)

    if not balls_a:
        raise HTTPException(status_code=404, detail=f"No balls found for '{player_a}'")
    if not balls_b:
        raise HTTPException(status_code=404, detail=f"No balls found for '{player_b}'")

    def profile(name, balls):
        p = {
            "name": name,
            "matches": len({b.match_id for b in balls}),
            "overall": stats_fn(balls),
            "by_phase": phase_fn(balls),
        }
        if role == "batsman":
            from src.analytics.weakness import compute_weakness_profile
            wp = compute_weakness_profile(balls, batsman_name=name)
            p["top_weakness"] = wp.get("top_weakness")
            p["top_strength"] = wp.get("top_strength")
            p["dismissals"] = _dismissal_profile(balls)
            p["wagon_wheel"] = _wagon_wheel_data(balls)
        else:
            p["wicket_profile"] = _wicket_delivery_profile(balls)
        return p

    return {
        "role": role,
        "player_a": profile(player_a, balls_a),
        "player_b": profile(player_b, balls_b),
    }


# ─── Analytics summary ────────────────────────────────────────────────────────

@app.get("/analytics/summary")
def analytics_summary(match_id: Optional[str] = None):
    return db.get_stats(match_id)


@app.get("/analytics/weakness")
def batsman_weakness(
    batsman_name: Optional[str] = None,
    match_id: Optional[str] = None,
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
    narrative: bool = False,
):
    from src.analytics.weakness import compute_weakness_profile

    if not batsman_name:
        return {"batsmen": db.list_batsmen(match_id)}

    balls = db.get_balls_for_batsman(
        batsman_name=batsman_name,
        match_id=match_id,
        min_confidence=min_confidence,
    )
    if not balls:
        raise HTTPException(
            status_code=404,
            detail=f"No qualifying balls found for '{batsman_name}' (confidence ≥ {min_confidence}).",
        )

    profile = compute_weakness_profile(balls, batsman_name=batsman_name)

    if narrative:
        from match_intelligence.lib.weakness_narrator import narrate_weakness
        profile["narrative"] = narrate_weakness(profile)

    return profile


# ─── Ball-level routes ────────────────────────────────────────────────────────

@app.get("/balls")
def list_balls(match_id: Optional[str] = None, needs_review: bool = False):
    if needs_review:
        balls = db.get_balls_needing_review(match_id)
    elif match_id:
        balls = db.get_balls_for_match(match_id)
    else:
        return []

    return [{
        "ball_id": b.ball_id, "over": b.over_number, "ball": b.ball_number,
        "bowler_name": b.bowler_name, "batsman_name": b.batsman_name,
        "bowler_type": b.bowler_type, "line": b.line, "length": b.length,
        "shot_type": b.shot_type, "outcome": b.outcome, "runs": b.runs_scored,
        "confidence_avg": round((b.confidence_line + b.confidence_length + b.confidence_shot_type) / 3, 2),
        "is_reviewed": b.is_reviewed, "raw_description": b.raw_description,
    } for b in balls]


@app.put("/balls/{ball_id}/review")
def review_ball(ball_id: str, update: BallUpdate):
    updates = {k: v for k, v in update.model_dump().items() if v is not None and k != "reviewed_by"}
    success = db.update_ball_review(ball_id, updates, reviewed_by=update.reviewed_by)
    if not success:
        raise HTTPException(status_code=404, detail="Ball not found")
    return {"message": f"Ball {ball_id} reviewed"}


@app.get("/clips/{ball_id}")
def serve_clip(ball_id: str):
    ball = db.get_ball(ball_id)
    if not ball or not ball.clip_path:
        raise HTTPException(status_code=404, detail="Clip not found")
    clip_path = Path(ball.clip_path)
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip file missing")
    return FileResponse(clip_path, media_type="video/mp4")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
