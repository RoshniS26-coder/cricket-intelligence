#!/usr/bin/env python3
"""Batsman-analysis report — symmetric to bowler_report.py.

For a given match + innings, picks the BATTING side and emits per-batter
analytics:

  - Basic: balls faced, runs, SR, 4s/6s, dots, dismissal
  - Line + length FACED distribution (what bowlers attacked with)
  - Shot-type distribution (what the batter chose to play)
  - Footwork distribution
  - Contact-quality distribution (clean / mistimed / edge / miss %)
  - Per-bowler matchups (balls faced + runs + dismissed-by-this-bowler)
  - Phase split (powerplay / middle / death)
  - Shot-direction map (scoring zones)

Outputs:
  - Rich console tables
  - JSON file with full structured analysis
  - Markdown report alongside

Usage:
    python features/batsman_analysis/batsman_report.py \\
        --match-id 1276906 \\
        --innings 2 \\
        --out data/batsman_analysis/match_1276906_innings_2.json
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
    if format_ == "T20":
        if over_idx <= 5:
            return "powerplay"
        if over_idx <= 14:
            return "middle"
        return "death"
    return "unknown"


def analyse_batsman(balls: list[BallDBRecord]) -> dict:
    """Compute per-batter analytics from a list of DB rows where this
    batter was on strike."""
    if not balls:
        return {}

    n_balls = len(balls)
    runs = sum((b.runs_scored or 0) for b in balls)
    fours = sum(1 for b in balls if (b.runs_scored or 0) == 4)
    sixes = sum(1 for b in balls if (b.runs_scored or 0) == 6)
    dots = sum(1 for b in balls if b.outcome == "dot")
    wkts = sum(1 for b in balls if b.outcome == "wicket")
    sr = round(runs / n_balls * 100, 2) if n_balls else 0.0

    # Dismissal — there should be at most one per batter per innings
    dismissal = None
    for b in balls:
        if b.outcome == "wicket":
            dismissal = {
                "dismissal_type": b.dismissal_type,
                "dismissal_fielder": b.dismissal_fielder,
                "bowler": b.bowler_name,
                "over": b.over_number,
                "ball": b.ball_number,
            }
            break

    line_dist = Counter(b.line for b in balls if b.line)
    length_dist = Counter(b.length for b in balls if b.length)
    shot_dist = Counter(b.shot_type for b in balls if b.shot_type and b.shot_type != "unknown")
    footwork_dist = Counter(b.footwork for b in balls if b.footwork and b.footwork != "unknown")
    contact_dist = Counter(b.contact_quality for b in balls if b.contact_quality)
    direction_dist = Counter(
        b.shot_direction for b in balls
        if b.shot_direction and b.shot_direction not in ("unknown", "none")
    )

    # Per-bowler matchups
    matchup: dict[str, dict] = defaultdict(
        lambda: {"balls": 0, "runs": 0, "dots": 0, "dismissed": False}
    )
    for b in balls:
        m = matchup[b.bowler_name or "unknown"]
        m["balls"] += 1
        m["runs"] += (b.runs_scored or 0)
        if b.outcome == "dot":
            m["dots"] += 1
        if b.outcome == "wicket":
            m["dismissed"] = True
    matchups = [{"bowler": k, **v, "sr": round(v["runs"] / v["balls"] * 100, 1) if v["balls"] else 0} for k, v in matchup.items()]
    matchups.sort(key=lambda m: -m["balls"])

    # Phase split
    phase_split: dict[str, dict] = defaultdict(lambda: {"balls": 0, "runs": 0, "dots": 0, "fours": 0, "sixes": 0})
    for b in balls:
        ph = _phase_for_over(b.over_number)
        s = phase_split[ph]
        s["balls"] += 1
        s["runs"] += (b.runs_scored or 0)
        if b.outcome == "dot":
            s["dots"] += 1
        if (b.runs_scored or 0) == 4:
            s["fours"] += 1
        if (b.runs_scored or 0) == 6:
            s["sixes"] += 1

    # Handedness — usually consistent across the innings
    handedness = next(
        (b.batsman_handedness for b in balls if b.batsman_handedness and b.batsman_handedness != "unknown"),
        "unknown",
    )

    return {
        "handedness": handedness,
        "balls_faced": n_balls,
        "runs": runs,
        "fours": fours,
        "sixes": sixes,
        "dots": dots,
        "dot_pct": round(dots / n_balls * 100, 1) if n_balls else 0,
        "strike_rate": sr,
        "wicket": wkts > 0,
        "dismissal": dismissal,
        "line_faced": dict(line_dist.most_common()),
        "length_faced": dict(length_dist.most_common()),
        "shot_played": dict(shot_dist.most_common(15)),
        "footwork": dict(footwork_dist.most_common()),
        "contact_quality": dict(contact_dist.most_common()),
        "shot_direction": dict(direction_dist.most_common(15)),
        "matchups": matchups,
        "phase_split": {k: v for k, v in phase_split.items()},
    }


def print_batsman_table(name: str, a: dict) -> None:
    console.print(f"\n[bold cyan]══ {name}[/bold cyan] [white]({a['handedness']})[/white]")
    console.print(
        f"  [white]{a['runs']} ({a['balls_faced']}b, SR {a['strike_rate']}) | "
        f"{a['fours']}x4, {a['sixes']}x6 | "
        f"dots {a['dots']}/{a['balls_faced']} ({a['dot_pct']}%) | "
        f"{'OUT' if a['wicket'] else 'not out'}[/white]"
    )
    if a["dismissal"]:
        d = a["dismissal"]
        console.print(
            f"  [red]Dismissal:[/red] {d['dismissal_type']} b. {d['bowler']} "
            f"({d['over']}.{d['ball']})"
            + (f", caught by {d['dismissal_fielder']}" if d.get("dismissal_fielder") else "")
        )

    # Line + length faced
    ll_table = Table(show_header=True, header_style="bold magenta", title="Line × Length faced")
    ll_table.add_column("Bucket")
    ll_table.add_column("Count", justify="right")
    ll_table.add_column("%", justify="right")
    for label, dist in [("LINE", a["line_faced"]), ("LENGTH", a["length_faced"])]:
        ll_table.add_row(f"[bold]{label}[/bold]", "", "")
        total = sum(dist.values()) or 1
        for k, v in dist.items():
            ll_table.add_row(f"  {k}", str(v), f"{(v/total*100):.0f}%")
    console.print(ll_table)

    # Shot + footwork + contact
    if a["shot_played"]:
        top_shots = ", ".join(f"{k}={v}" for k, v in a["shot_played"].items())
        console.print(f"  [yellow]shots played:[/yellow] {top_shots}")
    if a["footwork"]:
        fw = ", ".join(f"{k}={v}" for k, v in a["footwork"].items())
        console.print(f"  [yellow]footwork:[/yellow] {fw}")
    if a["contact_quality"]:
        cq = a["contact_quality"]
        total = sum(cq.values()) or 1
        cq_str = ", ".join(f"{k}={v} ({v/total*100:.0f}%)" for k, v in cq.items())
        console.print(f"  [yellow]contact quality:[/yellow] {cq_str}")
    if a["shot_direction"]:
        sd = ", ".join(f"{k}={v}" for k, v in a["shot_direction"].items())
        console.print(f"  [yellow]scoring zones:[/yellow] {sd}")

    # Matchups
    if a["matchups"]:
        m_table = Table(show_header=True, header_style="bold green", title="Matchups (per bowler)")
        m_table.add_column("Bowler")
        m_table.add_column("Balls", justify="right")
        m_table.add_column("Runs", justify="right")
        m_table.add_column("Dots", justify="right")
        m_table.add_column("SR", justify="right")
        m_table.add_column("Got out?", justify="center")
        for m in a["matchups"]:
            m_table.add_row(
                m["bowler"], str(m["balls"]), str(m["runs"]),
                str(m["dots"]), str(m["sr"]),
                "✓" if m["dismissed"] else "",
            )
        console.print(m_table)

    # Phase split
    if a["phase_split"]:
        p_table = Table(show_header=True, header_style="bold blue", title="Phase split")
        p_table.add_column("Phase")
        p_table.add_column("Balls", justify="right")
        p_table.add_column("Runs", justify="right")
        p_table.add_column("Dots", justify="right")
        p_table.add_column("4s", justify="right")
        p_table.add_column("6s", justify="right")
        p_table.add_column("SR", justify="right")
        for ph in ["powerplay", "middle", "death"]:
            if ph in a["phase_split"]:
                s = a["phase_split"][ph]
                sr = round(s["runs"] / s["balls"] * 100, 1) if s["balls"] else 0
                p_table.add_row(ph, str(s["balls"]), str(s["runs"]), str(s["dots"]),
                                str(s["fours"]), str(s["sixes"]), str(sr))
        console.print(p_table)


def make_markdown(match_id: str, innings: int, by_batter: dict[str, dict]) -> str:
    lines = [f"# Batting analysis — match {match_id}, innings {innings}", ""]
    for name, a in by_batter.items():
        lines.append(f"## {name} ({a['handedness']})")
        lines.append("")
        lines.append(
            f"**{a['runs']} ({a['balls_faced']}b)**  ·  "
            f"SR {a['strike_rate']}  ·  "
            f"{a['fours']}×4, {a['sixes']}×6  ·  "
            f"dot% {a['dot_pct']}  ·  "
            f"{'OUT' if a['wicket'] else 'not out'}"
        )
        if a["dismissal"]:
            d = a["dismissal"]
            tail = f", c. {d['dismissal_fielder']}" if d.get("dismissal_fielder") else ""
            lines.append(f"")
            lines.append(f"**Dismissal:** {d['dismissal_type']} b. {d['bowler']} ({d['over']}.{d['ball']}){tail}")

        lines.append("")
        lines.append("### Line faced")
        lines.append("| line | count | % |")
        lines.append("|---|---:|---:|")
        total = sum(a["line_faced"].values()) or 1
        for k, v in a["line_faced"].items():
            lines.append(f"| {k} | {v} | {v/total*100:.0f}% |")

        lines.append("")
        lines.append("### Length faced")
        lines.append("| length | count | % |")
        lines.append("|---|---:|---:|")
        total = sum(a["length_faced"].values()) or 1
        for k, v in a["length_faced"].items():
            lines.append(f"| {k} | {v} | {v/total*100:.0f}% |")

        if a["shot_played"]:
            lines.append("")
            lines.append("### Shots played (top 15)")
            for k, v in a["shot_played"].items():
                lines.append(f"- {k}: {v}")

        if a["footwork"]:
            lines.append("")
            lines.append("### Footwork")
            for k, v in a["footwork"].items():
                lines.append(f"- {k}: {v}")

        if a["contact_quality"]:
            lines.append("")
            lines.append("### Contact quality")
            total = sum(a["contact_quality"].values()) or 1
            for k, v in a["contact_quality"].items():
                lines.append(f"- {k}: {v} ({v/total*100:.0f}%)")

        if a["shot_direction"]:
            lines.append("")
            lines.append("### Scoring zones (shot direction)")
            for k, v in a["shot_direction"].items():
                lines.append(f"- {k}: {v}")

        lines.append("")
        lines.append("### Matchups")
        lines.append("| bowler | balls | runs | dots | SR | got out? |")
        lines.append("|---|---:|---:|---:|---:|:---:|")
        for m in a["matchups"]:
            lines.append(
                f"| {m['bowler']} | {m['balls']} | {m['runs']} | {m['dots']} | {m['sr']} | "
                f"{'✓' if m['dismissed'] else ''} |"
            )

        lines.append("")
        lines.append("### Phase split")
        lines.append("| phase | balls | runs | dots | 4s | 6s | SR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for ph in ["powerplay", "middle", "death"]:
            if ph in a["phase_split"]:
                s = a["phase_split"][ph]
                sr = round(s["runs"] / s["balls"] * 100, 1) if s["balls"] else 0
                lines.append(
                    f"| {ph} | {s['balls']} | {s['runs']} | {s['dots']} | "
                    f"{s['fours']} | {s['sixes']} | {sr} |"
                )

        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--match-id", required=True)
    ap.add_argument("--innings", type=int, required=True)
    ap.add_argument("--out", required=True)
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

        by_batter_balls: dict[str, list[BallDBRecord]] = defaultdict(list)
        for b in balls:
            by_batter_balls[b.batsman_name].append(b)

        console.print(f"Batters: {sorted(by_batter_balls.keys())}\n")

        # Sort by batting order: first ball faced
        first_appearance = {
            name: min((b.over_number, b.ball_number) for b in lst)
            for name, lst in by_batter_balls.items()
        }
        sorted_names = sorted(by_batter_balls.keys(), key=lambda n: first_appearance[n])

        by_batter = {}
        for name in sorted_names:
            a = analyse_batsman(by_batter_balls[name])
            by_batter[name] = a
            print_batsman_table(name, a)

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "match_id": args.match_id,
            "innings": args.innings,
            "total_balls": len(balls),
            "by_batter": by_batter,
        }, indent=2))
        console.print(f"\n[green]✓[/green] JSON written → {out_path}")

        md_path = out_path.with_suffix(".md")
        md_path.write_text(make_markdown(args.match_id, args.innings, by_batter))
        console.print(f"[green]✓[/green] Markdown report → {md_path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
