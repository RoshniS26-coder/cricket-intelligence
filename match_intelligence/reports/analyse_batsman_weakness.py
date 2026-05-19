"""
Batsman Weakness Analyser — CLI.

Queries the database for all balls faced by a batsman, computes a danger
zone profile (line × length), optionally calls Gemini for a bilingual
coaching narrative, and optionally renders a pitch map PNG.

Usage:
    # Statistical profile only (no Gemini)
    python scripts/analyse_batsman_weakness.py --batsman "Rohit Sharma"

    # Filter to one match
    python scripts/analyse_batsman_weakness.py --batsman "Rohit" --match-id demo-match

    # With Gemini bilingual narrative
    python scripts/analyse_batsman_weakness.py --batsman "Rohit" --narrative

    # With pitch map PNG
    python scripts/analyse_batsman_weakness.py --batsman "Rohit" --pitch-map

    # Save full JSON output
    python scripts/analyse_batsman_weakness.py --batsman "Rohit" --output data/reports/rohit_weakness.json

    # List all batsmen in DB
    python scripts/analyse_batsman_weakness.py --list-batsmen
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.storage.db import CricketDB
from src.analytics.weakness import compute_weakness_profile

console = Console()


def _print_zone_table(profile: dict) -> None:
    batsman = profile.get("batsman_name") or "unknown"
    total = profile.get("total_balls", 0)
    zones = profile.get("zones", [])
    strengths = profile.get("strengths", [])

    console.print()
    console.print(Panel(
        f"[bold cyan]Batting Profile — {batsman}[/bold cyan]\n"
        f"Total balls analysed: [bold]{total}[/bold]",
        style="cyan",
    ))

    if not zones:
        console.print("[yellow]⚠  Not enough data (need ≥ 2 balls per zone).[/yellow]")
        return

    # ── Weakness table ──────────────────────────────────────────────────────
    w_table = Table(title="⚠  Danger Zones (weakness)", style="bold")
    w_table.add_column("Line", style="cyan")
    w_table.add_column("Length", style="cyan")
    w_table.add_column("Balls", justify="right")
    w_table.add_column("Dismissals", justify="right")
    w_table.add_column("False shots", justify="right")
    w_table.add_column("Avg runs/ball", justify="right")
    w_table.add_column("Danger Score", justify="right")

    for z in zones:
        score = z["danger_score"]
        color = "red" if score >= 0.4 else "yellow" if score >= 0.2 else "green"
        w_table.add_row(
            z["line"].replace("_", " "),
            z["length"].replace("_", " "),
            str(z["total"]),
            str(z["dismissals"]),
            str(z["false_shots"]),
            str(z["avg_runs"]),
            f"[{color}]{score:.2f}[/{color}]",
        )
    console.print(w_table)

    top = profile.get("top_weakness")
    if top:
        console.print(
            f"\n[bold red]PRIMARY WEAKNESS:[/bold red] "
            f"{top['line'].replace('_', ' ')} / {top['length'].replace('_', ' ')} — "
            f"{top['dismissals']} dismissals in {top['total']} balls "
            f"({top['dismissal_rate']:.0%} dismissal rate)"
        )

    # ── Strength table ──────────────────────────────────────────────────────
    if strengths:
        console.print()
        s_table = Table(title="✅  Strength Zones (scores freely)", style="bold")
        s_table.add_column("Line", style="cyan")
        s_table.add_column("Length", style="cyan")
        s_table.add_column("Balls", justify="right")
        s_table.add_column("Boundaries", justify="right")
        s_table.add_column("Avg runs/ball", justify="right")
        s_table.add_column("Dismissals", justify="right")
        s_table.add_column("Strength Score", justify="right")

        for z in strengths:
            score = z["strength_score"]
            color = "green" if score >= 0.3 else "yellow" if score >= 0.1 else "white"
            s_table.add_row(
                z["line"].replace("_", " "),
                z["length"].replace("_", " "),
                str(z["total"]),
                str(z["boundaries"]),
                str(z["avg_runs"]),
                str(z["dismissals"]),
                f"[{color}]{score:.2f}[/{color}]",
            )
        console.print(s_table)

        top_s = profile.get("top_strength")
        if top_s:
            console.print(
                f"\n[bold green]PRIMARY STRENGTH:[/bold green] "
                f"{top_s['line'].replace('_', ' ')} / {top_s['length'].replace('_', ' ')} — "
                f"avg {top_s['avg_runs']} runs/ball, {top_s['boundaries']} boundaries "
                f"in {top_s['total']} balls"
            )


def _print_narrative(narrative: dict) -> None:
    if not narrative:
        return
    console.print()
    console.print("[bold]── BATTING PROFILE NARRATIVE ──[/bold]")

    if narrative.get("summary_en"):
        console.print(f"\n[bold]Overall Profile (EN):[/bold] {narrative['summary_en']}")
    if narrative.get("summary_hi"):
        console.print(f"[dim]{narrative['summary_hi']}[/dim]")

    if narrative.get("strengths_en"):
        console.print(f"\n[bold green]Strengths (EN):[/bold green] {narrative['strengths_en']}")
    if narrative.get("strengths_hi"):
        console.print(f"[dim]{narrative['strengths_hi']}[/dim]")

    if narrative.get("bowling_plan_en"):
        console.print(f"\n[bold red]Bowling Plan (EN):[/bold red] {narrative['bowling_plan_en']}")
    if narrative.get("bowling_plan_hi"):
        console.print(f"[dim]{narrative['bowling_plan_hi']}[/dim]")

    if narrative.get("batting_advice_en"):
        console.print(f"\n[bold]Batting Advice (EN):[/bold] {narrative['batting_advice_en']}")
    if narrative.get("batting_advice_hi"):
        console.print(f"[dim]{narrative['batting_advice_hi']}[/dim]")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse batsman weakness zones from extracted ball data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--batsman", type=str, help="Batsman name (partial match OK)")
    parser.add_argument("--match-id", type=str, default=None, help="Restrict to one match")
    parser.add_argument("--min-confidence", type=float, default=0.5,
                        help="Minimum line/length confidence to include a ball (default: 0.5)")
    parser.add_argument("--narrative", action="store_true",
                        help="Call Gemini for bilingual coaching narrative")
    parser.add_argument("--pitch-map", action="store_true",
                        help="Render danger heatmap PNG")
    parser.add_argument("--pitch-map-out", type=str, default=None,
                        help="Path for pitch map PNG (default: data/reports/<batsman>_pitch_map.png)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save full JSON profile to this path")
    parser.add_argument("--list-batsmen", action="store_true",
                        help="List all batsmen with data in the DB and exit")
    args = parser.parse_args()

    db = CricketDB()

    if args.list_batsmen:
        names = db.list_batsmen(args.match_id)
        if names:
            console.print("[bold]Batsmen in database:[/bold]")
            for name in names:
                console.print(f"  • {name}")
        else:
            console.print("[yellow]No batsman names found — batsman_name fields may be empty.[/yellow]")
        return 0

    if not args.batsman:
        parser.error("--batsman is required (or use --list-batsmen)")

    # Fetch
    balls = db.get_balls_for_batsman(
        batsman_name=args.batsman,
        match_id=args.match_id,
        min_confidence=args.min_confidence,
    )

    if not balls:
        console.print(
            f"[yellow]⚠  No qualifying balls found for '{args.batsman}' "
            f"(confidence ≥ {args.min_confidence}).[/yellow]\n"
            "Tip: run with --min-confidence 0.0 to include all balls regardless of confidence."
        )
        return 1

    # Compute profile
    profile = compute_weakness_profile(balls, batsman_name=args.batsman)
    _print_zone_table(profile)

    # Narrative
    narrative = {}
    if args.narrative:
        from match_intelligence.lib.weakness_narrator import narrate_weakness
        narrative = narrate_weakness(profile)
        _print_narrative(narrative)

    # Pitch map
    if args.pitch_map:
        from src.analytics.heatmaps import render_danger_map
        slug = args.batsman.lower().replace(" ", "_")
        out_path = args.pitch_map_out or f"data/reports/{slug}_pitch_map.png"
        saved = render_danger_map(profile, output_path=out_path)
        console.print(f"\n[green]✓[/green] Pitch map saved → {saved}")

    # JSON output
    if args.output:
        full = {**profile, "narrative": narrative}
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(full, indent=2, ensure_ascii=False))
        console.print(f"[green]✓[/green] JSON saved → {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
