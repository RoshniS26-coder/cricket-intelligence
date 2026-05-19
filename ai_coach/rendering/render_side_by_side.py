"""
Simple side-by-side (or top/bottom) comparison renderer.

Stacks two clips into one MP4 via ffmpeg, with labels burned in. No pose
overlays, no audio-narration mux, no impact-frame alignment — just a fast
visual comparison the coach can WhatsApp to the student.

For richer synced-impact pose-overlay comparison, see Part C in PLAN.md
(scripts/render_comparison_video.py — planned next).

Usage:
    # student on left, Kohli reference on right (default hstack)
    python scripts/render_side_by_side.py \\
        --left  data/raw_videos/student_drive.mp4 \\
        --right data/reference_library/videos/cover-drive/kohli-cover-1.mp4 \\
        --left-label  "STUDENT" \\
        --right-label "VIRAT KOHLI" \\
        --out data/reports/side_by_side_kohli.mp4

    # vertical stack (better for two vertical Shorts)
    python scripts/render_side_by_side.py \\
        --left  data/reference_library/videos/cover-drive/kohli-cover-1.mp4 \\
        --right data/reference_library/videos/cover-drive/kohli-explains-1.mp4 \\
        --layout vstack \\
        --out data/reports/kohli_vs_kohli_vertical.mp4
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def _escape_drawtext(s: str) -> str:
    """ffmpeg drawtext requires escaping of `:`, `'`, `\\`, `%`."""
    return s.replace("\\", "\\\\").replace("'", "\\\'").replace(":", "\\:").replace("%", "\\%")


@lru_cache(maxsize=1)
def _drawtext_available() -> bool:
    """Some Homebrew / minimal ffmpeg builds ship without libfreetype, which
    means the drawtext filter is missing. We detect once and gracefully fall
    back to a label-less render."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=5,
        )
        # Filter listing has the form '... T.. drawtext  V->V  Draw text...'
        return any("drawtext" in line for line in out.stdout.splitlines())
    except Exception:
        return False


def render(
    left: Path,
    right: Path,
    out: Path,
    layout: str = "hstack",          # "hstack" | "vstack"
    target_size: int = 720,           # height for hstack, width for vstack
    left_label: str = "LEFT",
    right_label: str = "RIGHT",
    slowdown: float = 1.0,            # 1.0 = original speed; 2.0 = half speed; etc.
    shortest: bool = True,            # clip to shorter input (clean ending)
) -> Path:
    if not left.exists():
        raise FileNotFoundError(left)
    if not right.exists():
        raise FileNotFoundError(right)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Scale strategy:
    #   hstack — both inputs scaled to same HEIGHT, width auto (-2 keeps even)
    #   vstack — both inputs scaled to same WIDTH, height auto
    if layout == "hstack":
        scale_a = f"scale=-2:{target_size}"
        scale_b = f"scale=-2:{target_size}"
    elif layout == "vstack":
        scale_a = f"scale={target_size}:-2"
        scale_b = f"scale={target_size}:-2"
    else:
        raise ValueError(f"layout must be hstack or vstack, got {layout!r}")

    # setpts for slowdown
    setpts = f",setpts={slowdown}*PTS" if slowdown != 1.0 else ""

    # drawtext requires ffmpeg built with libfreetype. Some Homebrew bottles
    # ship without it. If unavailable, skip burned-in labels and warn the
    # user — the side-by-side video itself still renders fine.
    if _drawtext_available():
        label_a = _escape_drawtext(left_label)
        label_b = _escape_drawtext(right_label)
        drawtext_common = (
            "fontcolor=white:fontsize=36:x=20:y=20:"
            "box=1:boxcolor=black@0.55:boxborderw=10"
        )
        label_filter_a = f",drawtext=text='{label_a}':{drawtext_common}"
        label_filter_b = f",drawtext=text='{label_b}':{drawtext_common}"
    else:
        print(
            "⚠ ffmpeg drawtext filter unavailable (libfreetype missing) — "
            "rendering without burned-in labels. "
            "To enable: `brew reinstall ffmpeg` (Homebrew bottles include libfreetype)."
        )
        label_filter_a = ""
        label_filter_b = ""

    filter_complex = (
        f"[0:v]{scale_a},setsar=1{setpts}{label_filter_a}[a];"
        f"[1:v]{scale_b},setsar=1{setpts}{label_filter_b}[b];"
        f"[a][b]{layout}=inputs=2"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(left),
        "-i", str(right),
        "-filter_complex", filter_complex,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an",   # drop audio for a clean comparison file (caller can mux narration later)
    ]
    if shortest:
        cmd.append("-shortest")
    cmd.append(str(out))

    print("Running:", " ".join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)
    print(f"✓ side-by-side video → {out}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Render two videos side-by-side.")
    p.add_argument("--left", required=True, help="Path to the left/top video.")
    p.add_argument("--right", required=True, help="Path to the right/bottom video.")
    p.add_argument("--out", required=True, help="Output MP4 path.")
    p.add_argument("--layout", choices=["hstack", "vstack"], default="hstack",
                   help="hstack = side-by-side; vstack = top/bottom (better for vertical Shorts).")
    p.add_argument("--target-size", type=int, default=720,
                   help="Height (hstack) or width (vstack) to normalize each clip to.")
    p.add_argument("--left-label", default="STUDENT")
    p.add_argument("--right-label", default="REFERENCE")
    p.add_argument("--slowdown", type=float, default=1.0,
                   help="1.0 = original speed; 2.0 = half speed.")
    p.add_argument("--no-shortest", action="store_true",
                   help="Don't clip output to the shorter input duration.")
    args = p.parse_args()

    render(
        left=Path(args.left),
        right=Path(args.right),
        out=Path(args.out),
        layout=args.layout,
        target_size=args.target_size,
        left_label=args.left_label,
        right_label=args.right_label,
        slowdown=args.slowdown,
        shortest=not args.no_shortest,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
