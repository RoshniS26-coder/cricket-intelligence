#!/usr/bin/env python3
"""Bowler-analysis showcase from the ball-by-ball DB.

For a given match, picks the BOWLING side of one innings (i.e. innings 2
when India batted → English bowlers; or innings 1 when England batted →
Indian bowlers) and emits per-bowler analytics:

  - Basic line: balls, overs, runs conceded, wickets, dot %, economy
  - Line + length distribution (% of deliveries in each bucket)
  - Variation usage
  - Crease split (over_the_wicket vs round_the_wicket)
  - Bowling speed range (where scoreboard speed was visible)
  - Per-batter matchups (balls / runs / dots / wickets per (bowler, batter))
  - Shot-played-against distribution (which shots the batter chose)
  - Contact outcomes (clean / edge / miss / mistimed)
  - Phase split (powerplay / middle / death)

Outputs:
  - Rich console tables
  - JSON file with the full structured analysis
  - Markdown report alongside the JSON

Usage:
    python features/bowler_analysis/bowler_report.py \\
        --match-id 1276906 \\
        --innings 2 \\
        --out data/bowler_analysis/match_1276906_innings_2.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console
from rich.table import Table

from src.storage.db import CricketDB, BallDBRecord


console = Console()


def _phase_for_over(over_idx: int, format_: str = "T20") -> str:
    """T20: powerplay=0-5, middle=6-14, death=15-19 (0-indexed overs)."""
    if format_ == "T20":
        if over_idx <= 5:
            return "powerplay"
        if over_idx <= 14:
            return "middle"
        return "death"
    return "unknown"


def _pct(part: int, total: int) -> str:
    return f"{(part / total * 100):.0f}%" if total else "—"


def analyse_bowler(balls: list[BallDBRecord]) -> dict:
    """Compute the structured per-bowler analysis from a list of DB rows."""
    if not balls:
        return {}

    legal = [b for b in balls if b.outcome != "wide" and b.outcome != "no_ball"]
    n_balls = len(balls)
    n_legal = len(legal)
    runs_conceded = sum((b.runs_scored or 0) for b in balls)  # off-bat; extras separate
    wickets = sum(1 for b in balls if b.outcome == "wicket")
    dots = sum(1 for b in balls if b.outcome == "dot")
    overs_bowled = round(n_legal / 6, 1)
    economy = round(runs_conceded / (n_legal / 6), 2) if n_legal else 0.0

    # Distributions
    line_dist = Counter(b.line for b in balls if b.line)
    length_dist = Counter(b.length for b in balls if b.length)
    variation_dist = Counter(b.variation for b in balls if b.variation and b.variation != "none")
    crease_dist = Counter(b.bowler_crease for b in balls if b.bowler_crease)
    contact_dist = Counter(b.contact_quality for b in balls if b.contact_quality)
    shot_dist = Counter(b.shot_type for b in balls if b.shot_type and b.shot_type != "unknown")

    # Speed (only when > 0)
    speeds = [b.bowling_speed_kmph for b in balls if b.bowling_speed_kmph and b.bowling_speed_kmph > 0]
    speed_summary = None
    if speeds:
        speed_summary = {
            "avg": round(sum(speeds) / len(speeds), 1),
            "min": round(min(speeds), 1),
            "max": round(max(speeds), 1),
            "samples": len(speeds),
        }

    # Per-batter matchups
    matchup: dict[str, dict] = defaultdict(lambda: {"balls": 0, "runs": 0, "dots": 0, "wickets": 0})
    for b in balls:
        m = matchup[b.batsman_name or "unknown"]
        m["balls"] += 1
        m["runs"] += (b.runs_scored or 0)
        if b.outcome == "dot":
            m["dots"] += 1
        if b.outcome == "wicket":
            m["wickets"] += 1
    matchups = [{"batter": k, **v} for k, v in matchup.items()]
    matchups.sort(key=lambda m: -m["balls"])

    # Phase split
    phase_split: dict[str, dict] = defaultdict(lambda: {"balls": 0, "runs": 0, "dots": 0, "wickets": 0})
    for b in balls:
        ph = _phase_for_over(b.over_number)
        s = phase_split[ph]
        s["balls"] += 1
        s["runs"] += (b.runs_scored or 0)
        if b.outcome == "dot":
            s["dots"] += 1
        if b.outcome == "wicket":
            s["wickets"] += 1

    return {
        "balls": n_balls,
        "legal_balls": n_legal,
        "overs": overs_bowled,
        "runs_conceded_off_bat": runs_conceded,
        "wickets": wickets,
        "dots": dots,
        "dot_pct": round(dots / n_balls * 100, 1) if n_balls else 0,
        "economy": economy,
        "line_distribution": dict(line_dist.most_common()),
        "length_distribution": dict(length_dist.most_common()),
        "variation_usage": dict(variation_dist.most_common()),
        "crease": dict(crease_dist.most_common()),
        "contact_quality_distribution": dict(contact_dist.most_common()),
        "shot_played_distribution": dict(shot_dist.most_common(10)),
        "speed_kmph": speed_summary,
        "matchups": matchups,
        "phase_split": {k: v for k, v in phase_split.items()},
    }


def print_bowler_table(bowler: str, a: dict) -> None:
    """Pretty-print one bowler's analysis to the console."""
    console.print(f"\n[bold cyan]══ {bowler} ══[/bold cyan]")
    console.print(
        f"  [white]{a['overs']} overs | {a['balls']} balls | "
        f"{a['runs_conceded_off_bat']} runs (off bat) | "
        f"{a['wickets']} wkts | "
        f"dots {a['dots']}/{a['balls']} ({a['dot_pct']}%) | "
        f"econ {a['economy']}[/white]"
    )

    # Line + length
    ll_table = Table(show_header=True, header_style="bold magenta", title="Line × Length")
    ll_table.add_column("Bucket")
    ll_table.add_column("Count", justify="right")
    ll_table.add_column("%", justify="right")
    for label, dist in [("LINE", a["line_distribution"]), ("LENGTH", a["length_distribution"])]:
        ll_table.add_row(f"[bold]{label}[/bold]", "", "")
        total = sum(dist.values()) or 1
        for k, v in dist.items():
            ll_table.add_row(f"  {k}", str(v), f"{(v/total*100):.0f}%")
    console.print(ll_table)

    # Variation + crease
    if a["variation_usage"]:
        var_str = ", ".join(f"{k}={v}" for k, v in a["variation_usage"].items())
        console.print(f"  [yellow]variations:[/yellow] {var_str}")
    if a["crease"]:
        crease_str = ", ".join(f"{k}={v}" for k, v in a["crease"].items())
        console.print(f"  [yellow]crease:[/yellow] {crease_str}")
    if a["speed_kmph"]:
        s = a["speed_kmph"]
        console.print(
            f"  [yellow]speed:[/yellow] avg {s['avg']} kph "
            f"(min {s['min']} / max {s['max']}, {s['samples']} readings)"
        )

    # Matchups
    if a["matchups"]:
        m_table = Table(show_header=True, header_style="bold green", title="Matchups (per batter)")
        m_table.add_column("Batter")
        m_table.add_column("Balls", justify="right")
        m_table.add_column("Runs", justify="right")
        m_table.add_column("Dots", justify="right")
        m_table.add_column("Wkts", justify="right")
        m_table.add_column("Avg/ball", justify="right")
        for m in a["matchups"]:
            avg = round(m["runs"] / m["balls"], 2) if m["balls"] else 0
            m_table.add_row(m["batter"], str(m["balls"]), str(m["runs"]), str(m["dots"]),
                            str(m["wickets"]), str(avg))
        console.print(m_table)

    # Phase split
    if a["phase_split"]:
        p_table = Table(show_header=True, header_style="bold blue", title="Phase split")
        p_table.add_column("Phase")
        p_table.add_column("Balls", justify="right")
        p_table.add_column("Runs", justify="right")
        p_table.add_column("Dots", justify="right")
        p_table.add_column("Wkts", justify="right")
        for ph in ["powerplay", "middle", "death"]:
            if ph in a["phase_split"]:
                s = a["phase_split"][ph]
                p_table.add_row(ph, str(s["balls"]), str(s["runs"]), str(s["dots"]), str(s["wickets"]))
        console.print(p_table)

    # Shot-played
    if a["shot_played_distribution"]:
        sp = ", ".join(f"{k}={v}" for k, v in a["shot_played_distribution"].items())
        console.print(f"  [yellow]shots played against:[/yellow] {sp}")

    # Contact quality
    if a["contact_quality_distribution"]:
        cq = a["contact_quality_distribution"]
        total = sum(cq.values()) or 1
        cq_str = ", ".join(f"{k}={v} ({v/total*100:.0f}%)" for k, v in cq.items())
        console.print(f"  [yellow]contact quality vs this bowler:[/yellow] {cq_str}")


def make_markdown(match_id: str, innings: int, by_bowler: dict[str, dict]) -> str:
    lines = [f"# Bowling analysis — match {match_id}, innings {innings}", ""]
    for bowler, a in by_bowler.items():
        lines.append(f"## {bowler}")
        lines.append("")
        lines.append(
            f"**{a['overs']} overs** · {a['balls']} balls · "
            f"{a['runs_conceded_off_bat']} runs (off bat) · "
            f"{a['wickets']} wkts · "
            f"dot% {a['dot_pct']} · economy {a['economy']}"
        )
        lines.append("")
        if a["speed_kmph"]:
            s = a["speed_kmph"]
            lines.append(f"- **Speed**: avg {s['avg']} kph (min {s['min']}, max {s['max']}, {s['samples']} readings)")
        if a["crease"]:
            lines.append(f"- **Crease**: " + ", ".join(f"{k}={v}" for k, v in a["crease"].items()))
        if a["variation_usage"]:
            lines.append(f"- **Variations**: " + ", ".join(f"{k}={v}" for k, v in a["variation_usage"].items()))

        lines.append("")
        lines.append("### Line distribution")
        lines.append("| line | count | % |")
        lines.append("|---|---:|---:|")
        total = sum(a["line_distribution"].values()) or 1
        for k, v in a["line_distribution"].items():
            lines.append(f"| {k} | {v} | {v/total*100:.0f}% |")

        lines.append("")
        lines.append("### Length distribution")
        lines.append("| length | count | % |")
        lines.append("|---|---:|---:|")
        total = sum(a["length_distribution"].values()) or 1
        for k, v in a["length_distribution"].items():
            lines.append(f"| {k} | {v} | {v/total*100:.0f}% |")

        lines.append("")
        lines.append("### Matchups")
        lines.append("| batter | balls | runs | dots | wkts | avg/ball |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for m in a["matchups"]:
            avg = round(m["runs"] / m["balls"], 2) if m["balls"] else 0
            lines.append(f"| {m['batter']} | {m['balls']} | {m['runs']} | {m['dots']} | {m['wickets']} | {avg} |")

        lines.append("")
        lines.append("### Phase split")
        lines.append("| phase | balls | runs | dots | wkts |")
        lines.append("|---|---:|---:|---:|---:|")
        for ph in ["powerplay", "middle", "death"]:
            if ph in a["phase_split"]:
                s = a["phase_split"][ph]
                lines.append(f"| {ph} | {s['balls']} | {s['runs']} | {s['dots']} | {s['wickets']} |")

        if a["shot_played_distribution"]:
            lines.append("")
            lines.append("### Shots played against (top 10)")
            for k, v in a["shot_played_distribution"].items():
                lines.append(f"- {k}: {v}")

        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--match-id", required=True)
    ap.add_argument("--innings", type=int, required=True, help="Innings to analyse (1 or 2)")
    ap.add_argument("--out", required=True, help="Output JSON path; .md report written alongside")
    args = ap.parse_args()

    db = CricketDB()
    session = db.get_session()
    try:
        balls = (
            session.query(BallDBRecord)
            .filter_by(match_id=args.match_id, innings=args.innings)
            .order_by(BallDBRecord.over_number, BallDBRecord.ball_number)
            .all()
        )
        console.print(f"Loaded {len(balls)} balls from DB for match {args.match_id} innings {args.innings}")
        if not balls:
            console.print("[red]No data — exiting[/red]")
            sys.exit(1)

        by_bowler_balls: dict[str, list[BallDBRecord]] = defaultdict(list)
        for b in balls:
            by_bowler_balls[b.bowler_name].append(b)

        console.print(f"Bowlers: {sorted(by_bowler_balls.keys())}\n")

        by_bowler = {}
        for bowler in sorted(by_bowler_balls.keys(), key=lambda x: -len(by_bowler_balls[x])):
            a = analyse_bowler(by_bowler_balls[bowler])
            by_bowler[bowler] = a
            print_bowler_table(bowler, a)

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "match_id": args.match_id,
            "innings": args.innings,
            "total_balls": len(balls),
            "by_bowler": by_bowler,
        }, indent=2))
        console.print(f"\n[green]✓[/green] JSON written → {out_path}")

        md_path = out_path.with_suffix(".md")
        md_path.write_text(make_markdown(args.match_id, args.innings, by_bowler))
        console.print(f"[green]✓[/green] Markdown report → {md_path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
