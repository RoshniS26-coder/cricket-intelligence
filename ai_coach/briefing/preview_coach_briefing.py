"""
Preview of the AI Coach narrative layer using ONLY Gemini extraction output.
No pose features required. Bridges the gap until Phase 3 (analytics + briefing
module) lands in src/analytics/.

Usage:
    python scripts/preview_coach_briefing.py --match-id net_test
    python scripts/preview_coach_briefing.py --match-id net_test --batsman "Rahul Kumar"
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console

from src.storage.db import CricketDB

load_dotenv()
console = Console()


PROMPT = """You are an elite Indian cricket academy coach writing a technique briefing
for a player using ONLY the structured per-ball data below.

Player: {player}
Balls analyzed: {n}

Shot distribution:      {shots}
Outcome distribution:   {outcomes}
By length:              {by_length}
By variation:           {by_variation}
By swing direction:     {by_swing}
By spin direction:      {by_spin}

Sample ball descriptions:
{descriptions}

IMPORTANT: Do NOT invent pose/biomechanical numbers (head angle, stride length, etc.) —
this briefing has only per-ball structured data, not pose. Stay qualitative about technique,
quantitative only about outcomes.

Write a ~350-word briefing in this exact structure (prose paragraphs, no bullets):
1. One-line session summary with ball count and dismissals
2. Top strength — cite the specific data that proves it
3. Top weakness — cite the specific combination (length × variation × swing/spin) and
   dismissal / false-shot rate over the sample size
4. Recommended drill — 10–15 min, specific
5. What to capture/re-measure next session (hint that technique metrics will be added later)

Indian academy context. Plain language. No hedging. No marketing fluff.
"""


def _crosstab(rows, field):
    out = defaultdict(lambda: {"total": 0, "dismissals": 0, "false_shots": 0})
    for r in rows:
        k = getattr(r, field, "unknown") or "unknown"
        out[k]["total"] += 1
        if r.outcome == "wicket":
            out[k]["dismissals"] += 1
        if r.contact_quality in ("edge", "miss", "mistimed"):
            out[k]["false_shots"] += 1
    # Keep only buckets with >= 2 samples so the LLM doesn't grandstand on n=1
    return {k: v for k, v in out.items() if v["total"] >= 2}


def aggregate(balls, player_filter=None):
    rows = [b for b in balls if (player_filter is None or (b.batsman_name or "") == player_filter)]
    return {
        "n": len(rows),
        "shots":        dict(Counter(r.shot_type for r in rows)),
        "outcomes":     dict(Counter(r.outcome for r in rows)),
        "by_length":    _crosstab(rows, "length"),
        "by_variation": _crosstab(rows, "variation"),
        "by_swing":     _crosstab(rows, "swing_direction"),
        "by_spin":      _crosstab(rows, "spin_direction"),
        "descriptions": [r.raw_description for r in rows[:10] if r.raw_description],
    }


def generate(summary, player):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = PROMPT.format(
        player=player or "this batsman",
        n=summary["n"],
        shots=json.dumps(summary["shots"]),
        outcomes=json.dumps(summary["outcomes"]),
        by_length=json.dumps(summary["by_length"]),
        by_variation=json.dumps(summary["by_variation"]),
        by_swing=json.dumps(summary["by_swing"]),
        by_spin=json.dumps(summary["by_spin"]),
        descriptions="\n".join(f"  - {d}" for d in summary["descriptions"]),
    )
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return resp.text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview AI-coach briefing from extraction output.")
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--batsman", default=None, help="Filter to one batsman name (optional).")
    args = parser.parse_args()

    db = CricketDB()
    balls = db.get_balls_for_match(args.match_id)

    if not balls:
        console.print(f"[red]✗[/red] No balls found for match [cyan]{args.match_id}[/cyan]")
        raise SystemExit(1)

    summary = aggregate(balls, args.batsman)
    if summary["n"] == 0:
        console.print(f"[red]✗[/red] No balls matched batsman [cyan]{args.batsman}[/cyan]")
        raise SystemExit(1)

    console.print(f"\n[bold cyan]AI Coach — Preview Briefing[/bold cyan]")
    console.print(f"Match: {args.match_id} | Player: {args.batsman or 'all'} | Balls: {summary['n']}\n")
    console.print("─" * 70)

    briefing = generate(summary, args.batsman)
    console.print(briefing)

    console.print("─" * 70)
    console.print(
        "[dim]Note: this is a qualitative preview using only Gemini extraction output. "
        "Quantitative technique metrics (head offset, stride length, etc.) require the "
        "pose layer — see PLAN.md Phase 1–3.[/dim]"
    )
