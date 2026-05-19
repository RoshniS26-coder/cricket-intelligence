"""
Net-session catalog pre-pass.

Sends a full net-practice video to Gemini, returns a per-shot count, a
per-contact count, and the raw BallRecord list for downstream per-shot
aggregation. Includes anomaly detection so a Gemini summary (instead of
exhaustive enumeration) doesn't silently corrupt downstream multi-shot
critique.

Originally lived in scripts/render_player_briefing.py — extracted here so
the multi-shot critique pipeline can call it without a cross-script import.
"""

from __future__ import annotations

import subprocess
from collections import Counter

from rich.console import Console

console = Console()


def _video_duration_seconds(clip_path: str) -> float | None:
    """Read video duration via ffprobe. Returns None on failure."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", clip_path,
            ],
            text=True,
            timeout=10,
        )
        return float(out.strip())
    except Exception:
        return None


def run_session_catalog(
    clip_path: str,
    model: str = "gemini-2.5-pro",
    force: bool = False,
) -> tuple[dict[str, int], dict[str, int], list] | None:
    """Net-session pre-pass: count deliveries by shot_type AND contact_quality,
    and return the raw BallRecord list for downstream per-shot aggregation.

    Returns a tuple (shot_counts, contact_counts, records) or None on failure /
    suspicious undercount.

    Defaults to a flagship model (gemini-2.5-pro) rather than inheriting the
    smaller model passed for critique. Lite/flash variants tend to summarize
    on long videos rather than enumerate exhaustively.

    Anomaly detection (skip with `force=True`):
      1. Tiny absolute count: <5 balls in a video > 2 minutes → summarized
      2. Very low rate: <1 ball per 30 seconds → likely summarized
    """
    try:
        from match_intelligence.lib.extractor import GeminiExtractor
    except Exception as e:
        console.print(f"[yellow]⚠ catalog import failed: {e}[/yellow]")
        return None
    try:
        ex = GeminiExtractor(model_name=model)
        records = ex.extract_from_video(clip_path, match_id="net_session_catalog")
        if not records:
            return None

        n_balls = len(records)
        duration = _video_duration_seconds(clip_path)

        if not force and duration:
            tiny = (duration > 120 and n_balls < 5)
            slow = (duration > 60 and n_balls < (duration / 30))
            if tiny or slow:
                expected_min = max(5, int(duration / 30))
                console.print(
                    f"[yellow]⚠ catalog undercount: detected {n_balls} ball(s) "
                    f"in a {duration:.0f}s video — expected ≥{expected_min}.[/yellow]"
                )
                console.print(
                    f"  [dim]Catalog model ({model}) likely summarized instead "
                    f"of enumerating. Retry with --catalog-model gemini-2.5-pro "
                    f"or pass --force-catalog to use the result anyway.[/dim]"
                )
                return None

        shot_counts = dict(Counter(r.shot_type.value for r in records))
        contact_counts = dict(Counter(r.contact_quality.value for r in records))
        return shot_counts, contact_counts, records
    except Exception as e:
        console.print(f"[yellow]⚠ catalog pre-pass failed: {e}[/yellow]")
        return None
