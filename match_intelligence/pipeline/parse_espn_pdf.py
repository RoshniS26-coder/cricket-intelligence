#!/usr/bin/env python3
"""Parse an ESPNCricinfo ball-by-ball PDF into structured JSON.

The PDF (saved from the browser) lists balls in REVERSE chronological order.
Each ball entry follows the pattern:
    <over>.<ball>
    <runs digit or • or extras code like 2nb>
    <BOWLER> TO <BATTER>, <OUTCOME>
    <commentary paragraph spanning multiple lines until next ball marker>

Output JSON shape (chronological forward order):
    {
      "match_id": ...,
      "balls": [
        {
          "scoreboard_over": 0, "scoreboard_ball": 1,
          "bowler": "WILLEY", "batter": "ROHIT SHARMA",
          "outcome_text": "1 RUN",
          "commentary": "Full, angling across to off stump, pushed to the left of mid-off"
        },
        ...
      ]
    }

Usage:
    python features/audio_pipeline/parse_espn_pdf.py \\
        --pdf "data/espncricinfo/Ball by Ball Commentary & Live Score - ENG vs IND, 3rd T20I.pdf" \\
        --out data/espncricinfo/IndvsEng/match_1276906_commentary.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Match a ball delimiter: an "OVER.BALL" pattern at the start of a stanza,
# followed by the runs / dot marker, then the bowler-to-batter line.
# We capture multi-line commentary up to the NEXT ball marker.
BALL_HEADER_RE = re.compile(
    r"""
    ^\s*(?P<over>\d{1,2})\.(?P<ball>\d{1,2})
    [\s\n]+                                                # one or more whitespace/newlines
    (?:(?P<runs>•|W|\d{1,2}(?:nb|wd|lb|b)?|nb|wd|lb|b)[\s\n]+)?  # optional runs marker line
    (?P<bowler>[A-Z][A-Z\- ]+?)\s+TO\s+(?P<batter>[A-Z][A-Z\- ]+?),\s*(?P<outcome>[A-Z0-9() ]+)
    """,
    re.MULTILINE | re.VERBOSE,
)


def extract_text(pdf_path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def parse_balls(text: str) -> list[dict]:
    """Find every ball entry by sliding through the text."""
    balls = []
    matches = list(BALL_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        commentary = text[m.end():end].strip()
        # Trim everything from the next "OVER N" summary box if present
        commentary = re.split(r"\n\s*OVER\s+\d+\s*\n", commentary)[0].strip()
        # Trim ESPN page footers / preamble that may bleed into commentary
        commentary = re.split(r"\n?\d{1,2}/\d{1,2}/\d{2,4}", commentary)[0].strip()
        commentary = re.split(r"\n\s*Here's\s+\w+\.\s*\n", commentary)[0].strip()
        commentary = re.split(r"\n\s*Slip in place", commentary)[0].strip()
        commentary = re.split(r"\n\s*4\.\d{2}(?:pm|am)\b", commentary)[0].strip()
        # Drop fan-comment lines like "Johnnie: \"...\""
        lines = []
        for line in commentary.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.match(r"^[A-Z][A-Za-z]+:\s+\"", line):
                continue
            lines.append(line)
        # Join lines, fix hyphenated line breaks pypdf inserts
        commentary = " ".join(lines).strip()
        # Rejoin hyphenated words split across PDF line breaks ("follow- through" → "follow-through")
        commentary = re.sub(r"-\s+", "-", commentary)
        balls.append({
            "scoreboard_over": int(m.group("over")),
            "scoreboard_ball": int(m.group("ball")),
            "bowler": m.group("bowler").strip().title(),
            "batter": m.group("batter").strip().title(),
            "outcome_text": m.group("outcome").strip(),
            "runs_or_marker": (m.group("runs") or "").strip(),
            "commentary": commentary,
        })
    return balls


def to_chronological(balls: list[dict]) -> list[dict]:
    """ESPN ships reverse-chronological. Sort by (over, ball) ascending."""
    return sorted(balls, key=lambda b: (b["scoreboard_over"], b["scoreboard_ball"]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pdf", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--match-id", default="1276906")
    args = p.parse_args()

    text = extract_text(args.pdf)
    print(f"PDF extracted: {len(text)} chars")

    balls = parse_balls(text)
    print(f"Parsed: {len(balls)} ball entries (raw, reverse-chronological)")

    chronological = to_chronological(balls)

    out = {
        "match_id": args.match_id,
        "source": str(args.pdf),
        "balls": chronological,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"✓ Wrote {len(chronological)} balls → {args.out}")

    if chronological:
        print("\nFirst 3 balls (chronological):")
        for b in chronological[:3]:
            print(f"  {b['scoreboard_over']}.{b['scoreboard_ball']}  {b['bowler']} → {b['batter']}  ({b['outcome_text']})")
            print(f"    \"{b['commentary'][:120]}{'...' if len(b['commentary'])>120 else ''}\"")


if __name__ == "__main__":
    main()
