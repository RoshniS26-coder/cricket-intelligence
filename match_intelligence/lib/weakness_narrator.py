"""
LLM narrative layer for batsman weakness + strength analysis.

Takes a structured profile (from src.analytics.weakness) and calls Gemini to
produce bilingual (English + Hindi) coaching-grade narrative covering:
  - Executive summary of overall batting profile
  - Strengths: which zones the batsman dominates and why
  - Weaknesses: which zones are dangerous and how to exploit them
  - Bowling plan: what to bowl to target this batsman
  - Batting advice: what the batsman should work on

Output is always bilingual {en, hi} regardless of input.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console

load_dotenv()
console = Console()

_SYSTEM_PROMPT = (
    "You are an elite Indian cricket analyst and coach with 20+ years of experience "
    "at first-class and international level. You analyse structured ball-by-ball data "
    "and produce precise, actionable insights in both English and Hindi. "
    "You speak directly to coaches and franchises — no fluff, no generic advice. "
    "Every recommendation must be grounded in the specific numbers you are given. "
    "Always cover BOTH strengths and weaknesses — a complete player profile, not just negatives."
)

_NARRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary_en": {
            "type": "string",
            "description": (
                "3-4 sentence complete batting profile in English — cover both the strongest zones "
                "(where the batsman scores freely) and the weakest zones (where dismissals/false shots occur). "
                "Cite specific zones and numbers. Franchise / head coach register."
            ),
        },
        "summary_hi": {
            "type": "string",
            "description": "Same complete batting profile in natural Hindi (Devanagari script). Coach register.",
        },
        "strengths_en": {
            "type": "string",
            "description": (
                "2-3 sentences describing the zones where this batsman is strongest — "
                "high run rate, clean contact, no dismissals. "
                "Name the specific line/length and what the batsman does well there."
            ),
        },
        "strengths_hi": {
            "type": "string",
            "description": "Same strengths analysis in Hindi (Devanagari script).",
        },
        "bowling_plan_en": {
            "type": "string",
            "description": (
                "3-4 sentence bowling plan — target the danger zones, avoid the strength zones. "
                "Include line, length, variation, and field placement suggestions."
            ),
        },
        "bowling_plan_hi": {
            "type": "string",
            "description": "Same bowling plan in Hindi (Devanagari script).",
        },
        "batting_advice_en": {
            "type": "string",
            "description": (
                "2-3 sentences coaching advice for the batsman — how to protect the weak zones "
                "and build on the strong ones. Specific, actionable."
            ),
        },
        "batting_advice_hi": {
            "type": "string",
            "description": "Same batting advice in Hindi (Devanagari script).",
        },
    },
    "required": [
        "summary_en", "summary_hi",
        "strengths_en", "strengths_hi",
        "bowling_plan_en", "bowling_plan_hi",
        "batting_advice_en", "batting_advice_hi",
    ],
}


def _build_prompt(profile: dict) -> str:
    batsman = profile.get("batsman_name") or "this batsman"
    total = profile.get("total_balls", 0)

    lines = [
        f"Batsman: {batsman}",
        f"Total balls analysed: {total}",
        "",
    ]

    # Danger zones
    danger_zones = profile.get("zones", [])[:5]
    if danger_zones:
        lines.append("TOP DANGER ZONES (line × length, sorted by danger score):")
        for z in danger_zones:
            lines.append(
                f"  {z['line']} / {z['length']}: "
                f"{z['total']} balls, {z['dismissals']} dismissals "
                f"({z['dismissal_rate']:.0%} dismissal rate), "
                f"{z['false_shots']} false shots ({z['false_shot_rate']:.0%}), "
                f"avg {z['avg_runs']} runs/ball, danger score {z['danger_score']:.2f}"
            )
        top = profile.get("top_weakness")
        if top:
            lines.append(
                f"\nPRIMARY WEAKNESS: {top['line'].replace('_', ' ')} / "
                f"{top['length'].replace('_', ' ')} — danger score {top['danger_score']:.2f}"
            )

    # Strength zones
    strength_zones = profile.get("strengths", [])[:5]
    if strength_zones:
        lines.append("\nTOP STRENGTH ZONES (line × length, sorted by strength score):")
        for z in strength_zones:
            lines.append(
                f"  {z['line']} / {z['length']}: "
                f"{z['total']} balls, {z['dismissals']} dismissals, "
                f"{z['boundaries']} boundaries, avg {z['avg_runs']} runs/ball, "
                f"strength score {z['strength_score']:.2f}"
            )
        top_s = profile.get("top_strength")
        if top_s:
            lines.append(
                f"\nPRIMARY STRENGTH: {top_s['line'].replace('_', ' ')} / "
                f"{top_s['length'].replace('_', ' ')} — "
                f"avg {top_s['avg_runs']} runs/ball, strength score {top_s['strength_score']:.2f}"
            )

    by_bowler = profile.get("by_bowler_type", {})
    if by_bowler:
        lines.append("\nBY BOWLER TYPE:")
        for bt, s in by_bowler.items():
            lines.append(
                f"  {bt}: {s['total']} balls, {s['dismissals']} dismissals, "
                f"avg {s['avg_runs']} runs/ball, danger {s['danger_score']:.2f}, "
                f"strength {s['strength_score']:.2f}"
            )

    by_var = profile.get("by_variation", {})
    if by_var:
        lines.append("\nBY VARIATION:")
        for v, s in by_var.items():
            lines.append(
                f"  {v}: {s['total']} balls, {s['dismissals']} dismissals, "
                f"avg {s['avg_runs']} runs/ball"
            )

    lines += [
        "",
        "Based on this data provide a complete bilingual batting profile covering:",
        "1. Overall summary (strengths AND weaknesses both).",
        "2. Strengths — which zones and deliveries this batsman handles well.",
        "3. Bowling plan — how to target this batsman.",
        "4. Batting advice — what to work on.",
        "",
        "Return strict JSON. No markdown.",
    ]
    return "\n".join(lines)


def narrate_weakness(
    profile: dict,
    model: str = "gemini-3-flash-preview",
) -> dict:
    """
    Call Gemini to narrate a complete weakness + strength profile bilingually.

    Args:
        profile: Output of compute_weakness_profile().
        model: Gemini model ID.

    Returns:
        Dict with bilingual keys: summary, strengths, bowling_plan, batting_advice.
        Returns empty dict on failure so callers can display gracefully.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print("[red]✗ GEMINI_API_KEY not set — skipping narrative[/red]")
        return {}

    if not profile.get("zones"):
        return {
            "summary_en": "Insufficient data — fewer than 2 balls in any zone.",
            "summary_hi": "अपर्याप्त डेटा — किसी भी ज़ोन में 2 से कम गेंदें हैं।",
            "strengths_en": "", "strengths_hi": "",
            "bowling_plan_en": "", "bowling_plan_hi": "",
            "batting_advice_en": "", "batting_advice_hi": "",
        }

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(profile)

    console.print("[blue]⟳[/blue] Generating bilingual batting profile via Gemini...")

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_NARRATION_SCHEMA,
                temperature=0.3,
            ),
        )
        result = json.loads(response.text)
        console.print("[green]✓[/green] Batting profile narrative generated")
        return result
    except Exception as e:
        console.print(f"[red]✗ Gemini narration failed: {e}[/red]")
        return {}
