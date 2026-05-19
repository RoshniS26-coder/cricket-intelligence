"""
Cut a full broadcast video into overlapping chunks via ffmpeg stream-copy.

Phase 1 of the two-phase ball-extraction workflow:
    Phase 1 (this CLI): video → N overlapping mp4 clips + manifest.json
    Phase 2 (extract_balls_from_clips.py): clips → Gemini per clip → per-clip
            JSON + merged JSON (no DB write, JSON only)

This step does NO Gemini calls and no extraction — it just shards the video
so the per-clip Gemini work in Phase 2 is parallelisable, restartable, and
inspectable (you can play the actual mp4 clips to verify ground truth).

Default config: 10-minute chunks with 2-minute overlap. For a 2-hour video:
    duration = 7200s
    step     = 600s - 120s = 480s
    n_chunks = ceil(7200 / 480) = 15

Usage:
    python features/ball_extraction/segment_video.py \\
        --video data/raw_videos/IndiaBatting-T20-IndvsEng.mp4 \\
        --match-id T20-IndvsEng-IndBat \\
        --out-dir data/video_clips_IndvsEng \\
        --chunk-min 10 \\
        --overlap-sec 120
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)

console = Console()


def plan_chunks(
    total_sec: float,
    chunk_duration: float,
    overlap_sec: float,
) -> list[tuple[float, float]]:
    """Compute (start_sec, length_sec) for each chunk so consecutive chunks
    overlap by overlap_sec. The last chunk's length is clipped to whatever's
    left so we don't seek past EOF.

    Example: total=900s, chunk=300s, overlap=30s →
        (0, 300), (270, 300), (540, 300), (810, 90)
    """
    if chunk_duration <= overlap_sec:
        raise ValueError(
            f"chunk_duration ({chunk_duration}) must exceed overlap_sec ({overlap_sec})"
        )
    if total_sec <= 0:
        return []

    plan: list[tuple[float, float]] = []
    step = chunk_duration - overlap_sec
    start = 0.0
    while start < total_sec:
        length = min(chunk_duration, total_sec - start)
        plan.append((start, length))
        if start + chunk_duration >= total_sec:
            break
        start += step
    return plan


def _video_duration_seconds(video_path: str) -> float:
    """Read total video duration via ffprobe."""
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        text=True, timeout=15,
    )
    return float(out.strip())


def _cut_chunk(video_path: str, start_sec: float, length_sec: float, out_path: str) -> tuple[bool, str]:
    """Cut one chunk via ffmpeg stream-copy (no re-encode → fast, ~1-2s/chunk).

    Returns (success, stderr_excerpt).
    """
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(start_sec), "-i", video_path,
        "-t", str(length_sec),
        "-c", "copy", "-avoid_negative_ts", "make_zero",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    ok = result.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 1024
    return ok, (result.stderr or "")[:300]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cut a broadcast video into overlapping chunks for per-clip Gemini extraction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--video", required=True, help="Path to broadcast video file")
    parser.add_argument("--match-id", required=True,
                        help="Match identifier — used in clip filenames and manifest")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Where to save clips (default: data/video_clips_<match_id>/)")
    parser.add_argument("--chunk-min", type=float, default=10.0,
                        help="Chunk duration in MINUTES (default: 10)")
    parser.add_argument("--overlap-sec", type=float, default=120.0,
                        help="Overlap between consecutive chunks in SECONDS (default: 120 = 2 min)")
    parser.add_argument("--start-sec", type=float, default=0.0,
                        help="Skip the first N seconds of the source video before chunking (default: 0)")
    parser.add_argument("--end-sec", type=float, default=0.0,
                        help="Stop chunking at N seconds (default: 0 = until end of video)")
    parser.add_argument("--max-chunks", type=int, default=0,
                        help="Stop after N chunks (default: 0 = all). Useful for quick test runs.")
    args = parser.parse_args()

    if not Path(args.video).exists():
        console.print(f"[red]✗[/red] Video not found: {args.video}")
        return 1

    if args.out_dir is None:
        args.out_dir = Path(f"data/video_clips_{args.match_id}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    chunk_duration_sec = args.chunk_min * 60.0

    # Use ffprobe to find video duration, then plan_chunks() to compute offsets
    total_sec = _video_duration_seconds(args.video)
    if args.end_sec <= 0 or args.end_sec > total_sec:
        args.end_sec = total_sec
    effective_total = args.end_sec - args.start_sec

    plan = plan_chunks(
        total_sec=effective_total,
        chunk_duration=chunk_duration_sec,
        overlap_sec=args.overlap_sec,
    )
    if args.max_chunks > 0:
        plan = plan[: args.max_chunks]

    console.print(
        f"\n[bold cyan]Video segmentation[/bold cyan]\n"
        f"  video           : {args.video}\n"
        f"  duration        : {total_sec:.0f}s ({total_sec/60:.1f} min)\n"
        f"  segment range   : {args.start_sec:.0f}s → {args.end_sec:.0f}s\n"
        f"  chunk duration  : {args.chunk_min:.1f} min ({chunk_duration_sec:.0f}s)\n"
        f"  overlap         : {args.overlap_sec:.0f}s\n"
        f"  plan            : {len(plan)} chunk(s)\n"
        f"  out_dir         : {args.out_dir}"
    )

    manifest = {
        "source_video":   str(Path(args.video).resolve()),
        "match_id":       args.match_id,
        "total_sec":      total_sec,
        "segment_start":  args.start_sec,
        "segment_end":    args.end_sec,
        "chunk_min":      args.chunk_min,
        "overlap_sec":    args.overlap_sec,
        "chunks":         [],
    }

    n_ok = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Cutting chunks", total=len(plan))

        for i, (relative_start, length_sec) in enumerate(plan):
            abs_start = args.start_sec + relative_start
            clip_name = f"{args.match_id}_chunk_{i+1:03d}.mp4"
            clip_path = args.out_dir / clip_name

            ok, err = _cut_chunk(args.video, abs_start, length_sec, str(clip_path))
            entry = {
                "index":      i + 1,
                "filename":   clip_name,
                "path":       str(clip_path.resolve()),
                "abs_start_sec": round(abs_start, 2),
                "length_sec":  round(length_sec, 2),
                "abs_end_sec": round(abs_start + length_sec, 2),
            }
            if ok:
                size_mb = clip_path.stat().st_size / (1024 * 1024)
                entry["size_mb"] = round(size_mb, 2)
                entry["status"] = "ok"
                n_ok += 1
                progress.console.print(
                    f"  [green]✓[/green] chunk {i+1:>2}/{len(plan)}  "
                    f"+{abs_start:6.0f}s len {length_sec:5.0f}s  "
                    f"{size_mb:5.1f} MB  [dim]→ {clip_name}[/dim]"
                )
            else:
                entry["status"] = "failed"
                entry["error"] = err
                progress.console.print(
                    f"  [red]✗[/red] chunk {i+1}: ffmpeg failed — {err[:120]}"
                )
            manifest["chunks"].append(entry)
            progress.advance(task)

    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    total_size_mb = sum(
        c.get("size_mb", 0.0) for c in manifest["chunks"] if c["status"] == "ok"
    )
    console.print(
        f"\n[bold]Done.[/bold]\n"
        f"  chunks cut     : [green]{n_ok}[/green] / {len(plan)}\n"
        f"  total size     : {total_size_mb:.1f} MB\n"
        f"  manifest       : {manifest_path}\n"
        f"\n"
        f"Next step — run Gemini per clip (Phase 2):\n"
        f"  python features/ball_extraction/extract_balls_from_clips.py \\\n"
        f"      --manifest {manifest_path} \\\n"
        f"      --model gemini-2.5-pro"
    )
    return 0 if n_ok == len(plan) else 2


if __name__ == "__main__":
    sys.exit(main())
