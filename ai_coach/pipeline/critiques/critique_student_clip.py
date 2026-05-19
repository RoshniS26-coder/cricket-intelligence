"""
CLI for few-shot Gemini critique.

Compares a student's shot clip against one or more reference clips of ideal
technique by professional players, returns a structured JSON critique.

Pre-reqs:
    - GEMINI_API_KEY in .env
    - Runs in the main `venv` (Python 3.14 is fine — no MediaPipe needed)

Usage:
    # 1. Quick form — pass paths and player names directly
    python scripts/critique_student_clip.py \\
        --clip data/raw_videos/student_drive.mp4 \\
        --shot-type cover_drive \\
        --references "data/raw_videos/kohli-cover-1.mp4:Virat Kohli" \\
                     "data/raw_videos/kohli-cover-2.mp4:Virat Kohli" \\
        --out data/reports/student_critique.json

    # 2. Sanity test — Kohli vs Kohli (should rate close_to_ideal)
    python scripts/critique_student_clip.py \\
        --clip data/raw_videos/kohli-cover-1.mp4 \\
        --shot-type cover_drive \\
        --references "data/raw_videos/kohli-cover-2.mp4:Virat Kohli" \\
        --out data/reports/kohli_self_critique.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console

from ai_coach.lib.coaching_loader import load_coaching_context
from ai_coach.lib.few_shot_critique import critique_against_references

console = Console()


def parse_reference(entry: str) -> dict:
    """Accept 'path' or 'path:Player Name'. Player defaults to 'professional'."""
    if ":" in entry:
        path, player = entry.split(":", 1)
        return {"path": path.strip(), "player": player.strip()}
    return {"path": entry.strip(), "player": "professional batsman"}


def _print_human_summary(result: dict) -> None:
    rating = result.get("overall_quality_rating", "?")
    color = {"close_to_ideal": "green",
             "needs_minor_work": "yellow",
             "needs_major_work": "red"}.get(rating, "white")

    console.print()
    console.print("[bold]── CRITIQUE SUMMARY ──[/bold]")
    console.print(f"Shot identified:  {result.get('identified_shot_type', '?')}")
    console.print(
        f"Match confidence: {result.get('shot_match_confidence', '?')}  "
        f"(student played the requested shot — yes/no/partial)"
    )
    console.print(f"Overall rating:   [{color}]{rating}[/{color}]")
    console.print()

    devs = result.get("deviations", []) or []
    if devs:
        console.print(f"[bold]Deviations from reference ({len(devs)}):[/bold]")
        for i, d in enumerate(devs, 1):
            sev = d.get("severity", "?")
            sev_col = {"low": "green", "medium": "yellow", "high": "red"}.get(sev, "white")
            console.print(f"  {i}. [{sev_col}]{sev.upper():6}[/{sev_col}] {d.get('aspect', '?')}")
            console.print(f"     observed: {d.get('observed', '')}")
            console.print(f"     ideal:    {d.get('ideal_per_reference', '')}")
            if d.get("estimated_correction_effort"):
                console.print(f"     effort:   {d['estimated_correction_effort']}")
        console.print()

    drills = result.get("drill_recommendations", []) or []
    if drills:
        console.print(f"[bold]Drill recommendations ({len(drills)}):[/bold]")
        for i, dr in enumerate(drills, 1):
            console.print(
                f"  {i}. {dr.get('drill_name', '?')}  "
                f"({dr.get('duration_minutes', '?')} min, {dr.get('frequency', '?')})"
            )
            if dr.get("addresses_aspect"):
                console.print(f"     addresses: {dr['addresses_aspect']}")
        console.print()

    if result.get("encouragement"):
        console.print(f"[bold]Encouragement:[/bold] {result['encouragement']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Few-shot Gemini critique: student clip vs reference clips."
    )
    parser.add_argument("--clip", required=True, help="Path to the student's attempt video.")
    parser.add_argument("--player", default="the player",
                        help="Player's name. Used in the prompt so Gemini refers to them by "
                             "name in deviations + encouragement (instead of 'the student').")
    parser.add_argument("--shot-type", required=True,
                        help="The shot the student is attempting. e.g. cover_drive, pull, defend, sweep.")
    parser.add_argument("--references", nargs="*", default=[],
                        help="Zero or more 'path' or 'path:Player Name' entries. "
                             "If empty, runs in SOLO mode using Gemini's intrinsic "
                             "cricket knowledge + optional coaching corpus context.")
    parser.add_argument("--reference-player", default=None,
                        help="Solo-mode anchor: name a famous player (e.g. 'Virat Kohli') "
                             "to use as the canonical reference. Overrides auto-anchor. "
                             "Ignored when --references is also provided.")
    parser.add_argument("--no-auto-anchor", action="store_true",
                        help="Disable the canonical player auto-anchor in solo mode. "
                             "Use a pure textbook-ideal prompt without naming any player.")
    parser.add_argument("--coaching-keys", default=None,
                        help="Comma-separated coaching corpus keys to inject as "
                             "expert context, e.g. 'coach-kohli-cover-hindi'. "
                             "Looked up in data/coaching_corpus/index.yaml.")
    parser.add_argument("--mode", default="single_ball",
                        choices=["single_ball", "net_session"],
                        help="single_ball (default) — student clip is ONE delivery. "
                             "net_session — student clip is a net practice session "
                             "with multiple attempts at the same shot. The deviations "
                             "in the output describe recurring patterns across attempts.")
    parser.add_argument("--out", default=None,
                        help="Output JSON path. If omitted, JSON only printed to stdout.")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--no-summary", action="store_true",
                        help="Skip the human-readable summary; print raw JSON only.")
    args = parser.parse_args()

    if not Path(args.clip).exists():
        console.print(f"[red]✗ student clip not found:[/red] {args.clip}")
        return 1

    references = [parse_reference(r) for r in (args.references or [])]
    for r in references:
        if not Path(r["path"]).exists():
            console.print(f"[red]✗ reference clip not found:[/red] {r['path']}")
            return 1

    coaching_keys: list[str] = []
    if args.coaching_keys:
        coaching_keys = [k.strip() for k in args.coaching_keys.split(",") if k.strip()]

    console.print()
    console.print(f"[bold cyan]Few-Shot Cricket Critique[/bold cyan]")
    console.print(f"Student:   {args.clip}")
    console.print(f"Shot type: {args.shot_type}")
    console.print(f"Mode:      {args.mode}")
    if references:
        console.print(f"References:")
        for r in references:
            console.print(f"  - {r['path']}  ({r.get('player', '?')})")
    else:
        from ai_coach.lib.critique_prompts import resolve_reference_player
        resolved = resolve_reference_player(
            args.shot_type,
            explicit=args.reference_player,
            auto_anchor=not args.no_auto_anchor,
        )
        if resolved and args.reference_player:
            console.print(f"References: [dim](solo, explicit anchor: [cyan]{resolved}[/cyan])[/dim]")
        elif resolved:
            console.print(f"References: [dim](solo, auto-anchor: [cyan]{resolved}[/cyan])[/dim]")
        else:
            console.print(f"References: [dim](pure solo — generic textbook ideal)[/dim]")
    if coaching_keys:
        console.print(f"Coaching context:")
        coaching_context = load_coaching_context(coaching_keys)
    else:
        coaching_context = []
    console.print()

    result = critique_against_references(
        student_clip=args.clip,
        reference_clips=references,
        shot_type=args.shot_type,
        coaching_context=coaching_context or None,
        mode=args.mode,
        model=args.model,
        player_name=args.player,
        reference_player=args.reference_player,
        auto_anchor=not args.no_auto_anchor,
    )

    text = json.dumps(result, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        console.print(f"\n[green]✓[/green] critique JSON saved → {out_path}")

    if not args.no_summary:
        _print_human_summary(result)
    else:
        console.print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
