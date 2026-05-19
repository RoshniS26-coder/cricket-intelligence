"""Whisper commentary → Cricsheet ball alignment helpers.

The strategy: a 10-min broadcast video has ~12 deliveries and ~150 commentary
segments. For each Cricsheet ball, find the segments that fall within the
plausible time window for that ball.

Without ground-truth ball timestamps we approximate by:
  - Total chunk video duration (from manifest)
  - Cricsheet ball position within the chunk
  - Pace heuristic (~50 sec per legal ball in T20 broadcasts)

For a tighter join, use audio-peak detection later (bat-on-ball transients).
This module gives the simpler "uniform-spacing" approximation that already
captures ~80% of the relevant commentary.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_transcript(transcript_path: str) -> dict:
    return json.loads(Path(transcript_path).read_text())


def segments_in_window(transcript: dict, start_sec: float, end_sec: float) -> list[dict]:
    """All transcript segments whose midpoint falls within [start, end]."""
    return [
        s for s in transcript["segments"]
        if start_sec <= (s["start"] + s["end"]) / 2 <= end_sec
    ]


def commentary_for_chunk(
    transcript: dict,
    chunk_offset_sec: float,
    chunk_duration_sec: float,
    cricsheet_balls: list[dict],
    pad_sec: float = 5.0,
) -> dict[str, list[str]]:
    """Map each Cricsheet ball_id → list of commentary segment texts.

    Args:
        transcript: full broadcast transcript (from whisper).
        chunk_offset_sec: where in the source video this chunk starts.
        chunk_duration_sec: how long this chunk is.
        cricsheet_balls: legal deliveries that are supposed to be in this chunk.
        pad_sec: extend each ball's window by this many seconds on each side.

    Uniform-spacing model: divide the chunk into equal windows for each ball.
    For chunks with N balls in T seconds, each ball gets T/N seconds.
    """
    n = len(cricsheet_balls)
    if n == 0:
        return {}

    per_ball = chunk_duration_sec / n
    out: dict[str, list[str]] = {}
    for i, ball in enumerate(cricsheet_balls):
        ball_start_in_chunk = i * per_ball
        ball_end_in_chunk = (i + 1) * per_ball
        # convert to source-video coordinates
        src_start = chunk_offset_sec + ball_start_in_chunk - pad_sec
        src_end = chunk_offset_sec + ball_end_in_chunk + pad_sec
        segs = segments_in_window(transcript, src_start, src_end)
        out[ball["ball_id"]] = [s["text"] for s in segs]
    return out


def format_commentary_for_prompt(commentary_by_ball: dict[str, list[str]]) -> str:
    """Render the per-ball commentary into a prompt-friendly block.

    Output shape:
        ball_id 1276906_0_1:
          "Willey to Rohit Sharma, full ball outside off, driven through cover..."
        ball_id 1276906_0_2:
          "Willey to Pant, length ball outside off, defended on the front foot..."
    """
    lines = []
    for bid, segs in commentary_by_ball.items():
        if not segs:
            lines.append(f"  ball_id {bid}: (no commentary segments aligned)")
        else:
            joined = " ".join(segs)
            lines.append(f"  ball_id {bid}: \"{joined}\"")
    return "\n".join(lines)
