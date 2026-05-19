"""
ffmpeg muxer: combine annotated video with narration audio.

If `match_video_to_audio=True`, stretches the video's playback speed (setpts)
so its duration matches the narration length. This keeps the whole clip
playing while the narration speaks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def _duration(path: str) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    return float(out.strip())


def mux_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    match_video_to_audio: bool = True,
) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    audio_dur = _duration(audio_path)
    video_dur = _duration(video_path)
    console.print(f"  audio: {audio_dur:.2f}s   video: {video_dur:.2f}s")

    if match_video_to_audio and video_dur > 0:
        stretch = max(1.0, audio_dur / video_dur)   # never speed up past original
        console.print(f"  matching: stretching video × {stretch:.2f}")
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-filter:v", f"setpts={stretch}*PTS",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
        ]

    subprocess.run(cmd, check=True, capture_output=True)
    console.print(f"[green]✓[/green] final video → {output_path}")
    return output_path
