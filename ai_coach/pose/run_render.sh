#!/usr/bin/env bash
# Render an annotated, narrated MP4 for one ball clip:
#   MediaPipe pose → batsman features → Gemini narration → Edge TTS → ffmpeg overlay/mux
#
# REQUIRES Python 3.12 with MediaPipe — activate venv312 BEFORE running:
#   source venv312/bin/activate
#
# Usage:
#   features/pose_analysis/run_render.sh <clip> <player_name> [out_mp4]
#
# Example:
#   source venv312/bin/activate
#   features/pose_analysis/run_render.sh \
#       data/raw_videos/kohli-nets-20260506.mp4 "Virat Kohli" \
#       data/reports/videos/kohli_demo.mp4

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <clip> <player_name> [out_mp4]"
    exit 1
fi

CLIP="$1"
PLAYER="$2"
OUT="${3:-data/reports/videos/$(basename "${CLIP%.*}")_pose.mp4}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# Light sanity check — MediaPipe needs Python 3.12
PY_VER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$PY_VER" != "3.12" ]; then
    echo "⚠ Pose pipeline needs Python 3.12 (you're on $PY_VER)."
    echo "  Run:  source venv312/bin/activate  before re-running this script."
    exit 1
fi

echo "Pose render"
echo "  clip    : $CLIP"
echo "  player  : $PLAYER"
echo "  out     : $OUT"
echo

mkdir -p "$(dirname "$OUT")"

python features/pose_analysis/render_ball_video.py \
    --clip "$CLIP" \
    --player "$PLAYER" \
    --out "$OUT"
