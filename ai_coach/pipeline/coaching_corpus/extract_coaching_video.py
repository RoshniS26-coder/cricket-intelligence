"""
CLI: extract structured coaching guidance from a tutorial video.

Use this on long-form expert explainer videos (Hindi / English / Hinglish)
where a coach explains a technique. The output is structured JSON saved to
data/coaching_corpus/<key>.json that downstream modules (critique, briefing)
can inject as expert context.

Usage:
    python scripts/extract_coaching_video.py \\
        --video data/raw_videos/coach-kohli-cover-hindi.mp4 \\
        --key coach-kohli-cover-hindi \\
        --subject "Virat Kohli cover drive technique — Hindi tutorial" \\
        --shot-type cover_drive
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import yaml
from rich.console import Console

from ai_coach.lib.coaching_extractor import (
    _bilingual_en,
    _bilingual_hi,
    extract_coaching_points,
)

console = Console()

CORPUS_DIR = Path("data/coaching_corpus")
INDEX_YAML = CORPUS_DIR / "index.yaml"
VIDEOS_DIR = CORPUS_DIR / "videos"


def _shot_slug(shot_type: str) -> str:
    """cover_drive -> cover-drive (used as subdir name; mirrors reference_library convention)."""
    return shot_type.replace("_", "-").lower()


def _load_index() -> dict:
    if not INDEX_YAML.exists():
        return {"entries": []}
    with INDEX_YAML.open() as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("entries", [])
    return data


def _save_index(data: dict) -> None:
    INDEX_YAML.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_YAML.open("w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def _print_summary(result: dict) -> None:
    console.print()
    console.print("[bold]── COACHING EXTRACT SUMMARY ──[/bold]")
    console.print(f"Shot/skill:       {result.get('shot_or_skill', '?')}")
    if result.get("reference_player"):
        console.print(f"Reference player: {result['reference_player']}")
    console.print(f"Language:         {result.get('language_detected', '?')}")
    console.print(f"Confidence:       {result.get('extraction_confidence', '?')}")
    console.print()

    if result.get("ideal_outcome"):
        outcome = result["ideal_outcome"]
        console.print(f"[bold]Ideal outcome:[/bold] {_bilingual_en(outcome)}")
        if _bilingual_hi(outcome):
            console.print(f"                [dim]{_bilingual_hi(outcome)}[/dim]")
        console.print()

    pts = result.get("key_technique_points", []) or []
    if pts:
        console.print(f"[bold]Key technique points ({len(pts)}):[/bold]")
        for i, p in enumerate(pts, 1):
            point = p.get("point", "")
            console.print(f"  {i}. [cyan][{p.get('aspect', '?'):14}][/cyan] {_bilingual_en(point)}")
            if _bilingual_hi(point):
                console.print(f"     [dim]{'':14}  {_bilingual_hi(point)}[/dim]")
        console.print()

    drills = result.get("drills", []) or []
    if drills:
        console.print(f"[bold]Drills ({len(drills)}):[/bold]")
        for i, d in enumerate(drills, 1):
            line = f"  {i}. {d.get('drill_name', '?')}"
            if d.get("duration_minutes"):
                line += f"  ({d['duration_minutes']} min)"
            if d.get("addresses_aspect"):
                line += f"  → {d['addresses_aspect']}"
            console.print(line)
        console.print()

    mistakes = result.get("common_mistakes", []) or []
    if mistakes:
        console.print(f"[bold]Common mistakes ({len(mistakes)}):[/bold]")
        for m in mistakes:
            console.print(f"  - {_bilingual_en(m)}")
            if _bilingual_hi(m):
                console.print(f"    [dim]{_bilingual_hi(m)}[/dim]")
        console.print()

    cues = result.get("coaching_cues", []) or []
    if cues:
        console.print(f"[bold]Coaching cues ({len(cues)}):[/bold]")
        for c in cues:
            console.print(f'  - "{_bilingual_en(c)}"')
            if _bilingual_hi(c):
                console.print(f'    [dim]"{_bilingual_hi(c)}"[/dim]')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Path to the coaching tutorial video.")
    parser.add_argument("--key", required=True, help="Short slug identifying this entry in the corpus, e.g. coach-kohli-cover-hindi.")
    parser.add_argument("--subject", required=True, help="Free-text subject hint, e.g. 'Virat Kohli cover drive — Hindi tutorial'.")
    parser.add_argument("--shot-type", required=True, help="Shot label this tutorial covers, e.g. cover_drive, pull, defend.")
    parser.add_argument("--player", default="", help="Reference player named in the video, if any.")
    parser.add_argument("--source-url", default="", help="YouTube URL or original source.")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--no-summary", action="store_true")
    args = parser.parse_args()

    if not Path(args.video).exists():
        console.print(f"[red]✗ video not found:[/red] {args.video}")
        return 1

    console.print()
    console.print(f"[bold cyan]Coaching Corpus Extraction[/bold cyan]")
    console.print(f"video:   {args.video}")
    console.print(f"key:     {args.key}")
    console.print(f"subject: {args.subject}")
    console.print()

    result = extract_coaching_points(
        video_path=args.video,
        subject_hint=args.subject,
        model=args.model,
    )

    # Save extracted JSON alongside the per-shot subdir (mirrors reference_library layout)
    shot_subdir = VIDEOS_DIR / _shot_slug(args.shot_type)
    shot_subdir.mkdir(parents=True, exist_ok=True)
    out_path = shot_subdir / f"{args.key}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    console.print(f"[green]✓[/green] coaching JSON saved → {out_path}")

    # Update manifest
    index = _load_index()
    # Replace any existing entry with this key
    index["entries"] = [e for e in index["entries"] if e.get("key") != args.key]
    index["entries"].append({
        "key":         args.key,
        "shot_type":   args.shot_type,
        "player":      args.player or result.get("reference_player", ""),
        "language":    result.get("language_detected", ""),
        "source_url":  args.source_url,
        "video_path":  args.video,
        "json_path":   str(out_path),
        "confidence":  result.get("extraction_confidence", None),
        "n_points":    len(result.get("key_technique_points", []) or []),
        "n_drills":    len(result.get("drills", []) or []),
        "n_mistakes":  len(result.get("common_mistakes", []) or []),
        "n_cues":      len(result.get("coaching_cues", []) or []),
    })
    _save_index(index)
    console.print(f"[green]✓[/green] manifest updated → {INDEX_YAML}")

    if not args.no_summary:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
