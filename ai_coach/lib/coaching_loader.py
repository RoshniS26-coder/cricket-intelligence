"""
Load coaching-corpus extracts by key.

Resolves keys from data/coaching_corpus/index.yaml and returns the parsed
JSON content for each. Used by the few-shot critique and the player briefing
to inject expert coaching context into prompts.

Originally duplicated across scripts/critique_student_clip.py and
scripts/render_player_briefing.py — consolidated here.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from rich.console import Console

console = Console()

COACHING_CORPUS_INDEX = Path("data/coaching_corpus/index.yaml")


def load_coaching_context(keys: list[str]) -> list[dict]:
    """Load coaching extracts by key from data/coaching_corpus/index.yaml.

    Skips (with a warning) any key that's missing or whose JSON file is gone.
    Returns one parsed-JSON dict per resolved key.
    """
    if not keys:
        return []
    if not COACHING_CORPUS_INDEX.exists():
        console.print(
            f"[yellow]⚠ coaching corpus manifest not found:[/yellow] {COACHING_CORPUS_INDEX}"
        )
        return []

    with COACHING_CORPUS_INDEX.open() as fh:
        manifest = yaml.safe_load(fh) or {}
    by_key = {e["key"]: e for e in (manifest.get("entries") or [])}

    out = []
    for k in keys:
        entry = by_key.get(k)
        if not entry:
            console.print(f"[yellow]⚠ coaching key not in manifest:[/yellow] {k}")
            continue
        json_path = Path(entry.get("json_path", ""))
        if not json_path.exists():
            console.print(f"[yellow]⚠ coaching JSON missing:[/yellow] {json_path}")
            continue
        try:
            out.append(json.loads(json_path.read_text()))
            console.print(
                f"  [green]✓[/green] coaching context: [cyan]{k}[/cyan] "
                f"(shot={entry.get('shot_type', '?')}, "
                f"language={entry.get('language', '?')}, "
                f"conf={entry.get('confidence', '?')})"
            )
        except json.JSONDecodeError as e:
            console.print(f"[red]✗ failed to parse coaching JSON {json_path}: {e}[/red]")
    return out
