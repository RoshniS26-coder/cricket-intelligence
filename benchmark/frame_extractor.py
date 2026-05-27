"""Extract key frames from a ball video clip using ffmpeg."""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from benchmark.config import FRAMES_PER_BALL


def extract_frames(clip_path: Path, n_frames: int = FRAMES_PER_BALL) -> list[Path]:
    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    tmpdir = Path(tempfile.mkdtemp())

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path)],
        capture_output=True, text=True,
    )
    duration = float(result.stdout.strip() or "3.0")
    interval = duration / (n_frames + 1)

    frame_paths = []
    for i in range(n_frames):
        ts = interval * (i + 1)
        out = tmpdir / f"frame_{i:02d}.png"
        subprocess.run(
            ["ffmpeg", "-ss", str(ts), "-i", str(clip_path),
             "-frames:v", "1", "-q:v", "2", str(out), "-y"],
            capture_output=True,
        )
        if out.exists():
            frame_paths.append(out)

    return frame_paths


def cleanup_frames(frame_paths: list[Path]) -> None:
    for p in frame_paths:
        p.unlink(missing_ok=True)
    if frame_paths:
        try:
            frame_paths[0].parent.rmdir()
        except OSError:
            pass
