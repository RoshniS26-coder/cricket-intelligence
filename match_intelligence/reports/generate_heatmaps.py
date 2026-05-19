#!/usr/bin/env python3
"""Generate per-bowler + per-batter heatmaps for one match-innings.

For every bowler in the innings:
  - Pitch map: 5 line × 5 length grid coloured by # balls bowled there

For every batter in the innings:
  - Pitch map: 5 × 5 grid coloured by # balls FACED there
  - Wagon wheel: polar chart of runs scored per shot_direction

Saves all PNGs under data/heatmaps/match_<id>_innings_<n>/ and writes
a small index.md linking them all.

Usage:
    python features/heatmap/generate_heatmaps.py \\
        --match-id 1276906 --innings 2 \\
        --out-dir data/heatmaps/match_1276906_innings_2
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console

from src.storage.db import CricketDB, BallDBRecord
from src.analytics.heatmaps import render_pitch_heatmap, render_wagon_wheel


console = Console()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
    return s or "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--match-id", required=True)
    ap.add_argument("--innings", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db = CricketDB()
    session = db.get_session()
    try:
        balls = (
            session.query(BallDBRecord)
            .filter_by(match_id=args.match_id, innings=args.innings)
            .order_by(BallDBRecord.over_number, BallDBRecord.ball_number)
            .all()
        )
        console.print(f"Loaded {len(balls)} balls from DB")
        if not balls:
            console.print("[red]No data — exiting[/red]")
            sys.exit(1)

        # ── BOWLER PITCH MAPS ──
        by_bowler: dict[str, list[BallDBRecord]] = defaultdict(list)
        for b in balls:
            by_bowler[b.bowler_name].append(b)

        bowler_files = []
        for bowler, bls in by_bowler.items():
            counts: Counter = Counter()
            for b in bls:
                if b.line and b.length:
                    counts[(b.length, b.line)] += 1
            png = render_pitch_heatmap(
                counts=counts,
                title=bowler,
                subtitle=f"Pitch map — {len(bls)} balls bowled",
                output_path=str(out_dir / f"bowler_{_slug(bowler)}_pitch_map.png"),
                cmap_name="YlOrRd",
                cell_label="balls",
            )
            bowler_files.append((bowler, png))
            console.print(f"  ✓ bowler pitch map → {Path(png).name}")

        # ── BATTER PITCH MAPS + WAGON WHEELS ──
        by_batter: dict[str, list[BallDBRecord]] = defaultdict(list)
        for b in balls:
            by_batter[b.batsman_name].append(b)

        batter_files = []
        for batter, bls in by_batter.items():
            counts: Counter = Counter()
            for b in bls:
                if b.line and b.length:
                    counts[(b.length, b.line)] += 1
            pm_png = render_pitch_heatmap(
                counts=counts,
                title=batter,
                subtitle=f"Balls faced — {len(bls)} deliveries",
                output_path=str(out_dir / f"batter_{_slug(batter)}_pitch_map.png"),
                cmap_name="Blues",
                cell_label="balls",
            )

            # Wagon wheel — runs to each direction
            runs_by_dir: Counter = Counter()
            for b in bls:
                if b.shot_direction and b.shot_direction not in ("unknown", "none"):
                    runs_by_dir[b.shot_direction] += (b.runs_scored or 0)
            handedness = next(
                (b.batsman_handedness for b in bls if b.batsman_handedness and b.batsman_handedness != "unknown"),
                "right_handed",
            )
            ww_png = render_wagon_wheel(
                direction_metric=runs_by_dir,
                handedness=handedness,
                title=batter,
                subtitle=f"Wagon wheel — runs scored per zone",
                output_path=str(out_dir / f"batter_{_slug(batter)}_wagon_wheel.png"),
                metric_label="runs",
            )
            batter_files.append((batter, pm_png, ww_png))
            console.print(f"  ✓ batter heatmaps for {batter}")

        # Index markdown
        idx_lines = [f"# Heatmaps — match {args.match_id}, innings {args.innings}", ""]
        idx_lines.append("## Bowlers (pitch maps)\n")
        for bowler, png in bowler_files:
            rel = Path(png).name
            idx_lines.append(f"### {bowler}\n")
            idx_lines.append(f"![{bowler} pitch map]({rel})\n")
        idx_lines.append("\n## Batters (pitch maps + wagon wheels)\n")
        for batter, pm, ww in batter_files:
            idx_lines.append(f"### {batter}\n")
            idx_lines.append(f"![{batter} balls faced]({Path(pm).name})\n")
            idx_lines.append(f"![{batter} wagon wheel]({Path(ww).name})\n")

        (out_dir / "index.md").write_text("\n".join(idx_lines))
        console.print(f"\n[green]✓[/green] Wrote {len(bowler_files)} bowler + {len(batter_files)} batter heatmaps → {out_dir}")
        console.print(f"[green]✓[/green] Index: {out_dir / 'index.md'}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
