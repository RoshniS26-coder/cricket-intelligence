"""ESPNCricinfo ball-by-ball commentary loader + Cricsheet join.

ESPN uses LEGAL ball numbering (over.legal_ball_pos). Cricsheet uses
array-position numbering (which counts wides + no-balls as separate balls).
This module joins ESPN's structured commentary to Cricsheet ball_ids so
the technique-only Gemini prompt can use it as primary technique signal.

Usage:
    from match_intelligence.lib.espn_commentary import (
        load_espn_commentary, build_commentary_by_ball,
    )

    espn = load_espn_commentary("data/espncricinfo/.../match_xxx_commentary.json")
    commentary_by_ball = build_commentary_by_ball(espn, cricsheet_balls)
"""

from __future__ import annotations

import json
from pathlib import Path


def load_espn_commentary(path: str) -> list[dict]:
    """Load the structured ESPN commentary JSON (from parse_espn_pdf.py)."""
    data = json.loads(Path(path).read_text())
    return data.get("balls", [])


def _surname(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().split()[-1].lower()


def build_commentary_by_ball(
    espn_balls: list[dict],
    cricsheet_balls: list[dict],
) -> dict[str, list[str]]:
    """Map each Cricsheet ball_id → list with one element (the ESPN commentary).

    Join key: (over, legal_ball_pos) on both sides, with surname fallback.
    Cricsheet's array position is converted to legal-ball-pos by counting
    only deliveries where is_legal_delivery=True.
    """
    # Index ESPN by (over, legal_ball)
    espn_by_key: dict[tuple[int, int], dict] = {}
    for eb in espn_balls:
        key = (eb["scoreboard_over"], eb["scoreboard_ball"])
        espn_by_key[key] = eb

    # Build Cricsheet legal-ball positions: for each over, the i-th legal
    # delivery in array order gets legal_ball_pos = i+1
    cs_with_legal_pos = []
    over_legal_count: dict[int, int] = {}
    for cb in cricsheet_balls:
        if not cb.get("is_legal_delivery"):
            cs_with_legal_pos.append((cb, None))
            continue
        o = cb["over"]
        n = over_legal_count.get(o, 0) + 1
        over_legal_count[o] = n
        cs_with_legal_pos.append((cb, n))

    commentary_by_ball: dict[str, list[str]] = {}
    for cb, legal_pos in cs_with_legal_pos:
        if legal_pos is None:
            commentary_by_ball[cb["ball_id"]] = []
            continue
        eb = espn_by_key.get((cb["over"], legal_pos))
        if eb is None:
            commentary_by_ball[cb["ball_id"]] = []
            continue
        # Sanity-check the join via surname match — if bowler/batter
        # surnames disagree the join is wrong and we skip
        cs_bowler_surname = _surname(cb.get("bowler_name"))
        cs_batter_surname = _surname(cb.get("batsman_name"))
        eb_bowler_surname = _surname(eb.get("bowler"))
        eb_batter_surname = _surname(eb.get("batter"))
        # Strip generic terms ESPN sometimes uses (e.g., "Suryakumar" full vs "Yadav")
        if cs_bowler_surname == eb_bowler_surname or eb_bowler_surname in cs_bowler_surname or cs_bowler_surname in eb_bowler_surname:
            ok_bowler = True
        else:
            ok_bowler = False
        if cs_batter_surname == eb_batter_surname or eb_batter_surname in cs_batter_surname or cs_batter_surname in eb_batter_surname:
            ok_batter = True
        else:
            ok_batter = False

        if not (ok_bowler and ok_batter):
            commentary_by_ball[cb["ball_id"]] = [
                f"[ESPN match ambiguous — found {eb.get('bowler')}→{eb.get('batter')} at {cb['over']}.{legal_pos}, "
                f"but Cricsheet expects {cb.get('bowler_name')}→{cb.get('batsman_name')}]: "
                f"{eb.get('commentary', '')}"
            ]
        else:
            commentary_by_ball[cb["ball_id"]] = [eb.get("commentary", "")]

    return commentary_by_ball
