"""
Text-to-speech via Microsoft Edge voices (free, no API key).

Default voice: en-IN-PrabhatNeural (Indian English, male). Alternatives:
  - en-IN-NeerjaNeural (female)
  - en-US-GuyNeural
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console

console = Console()


async def _synth(text: str, output_path: str, voice: str, rate: str, volume: str) -> None:
    # Import lazily so the rest of the pipeline can run without edge-tts installed
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(output_path)


def generate_narration(
    text: str,
    output_path: str,
    voice: str = "en-IN-PrabhatNeural",
    rate: str = "-10%",
    volume: str = "+0%",
) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    console.print(f"[blue]⟳[/blue] Edge TTS → {output_path}  ({voice}, rate={rate})")
    asyncio.run(_synth(text, output_path, voice, rate, volume))
    console.print(f"[green]✓[/green] narration → {output_path}")
    return output_path
