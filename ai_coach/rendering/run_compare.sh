#!/usr/bin/env bash
# Render a side-by-side (hstack) comparison MP4 of two clips.
# Defaults to "STUDENT" / "REFERENCE" labels — edit the script to override.
#
# Usage:
#   features/rendering/run_compare.sh <left_video> <right_video> [out_mp4]
#
# Example:
#   features/rendering/run_compare.sh \
#       data/raw_videos/student_drive.mp4 \
#       data/reference_library/videos/cover-drive/kohli-cover-1.mp4 \
#       data/reports/student_vs_kohli.mp4

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <left_video> <right_video> [out_mp4]"
    exit 1
fi

LEFT="$1"
RIGHT="$2"
OUT="${3:-data/reports/$(basename "${LEFT%.*}")_vs_$(basename "${RIGHT%.*}").mp4}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Side-by-side render"
echo "  left   : $LEFT  (label: STUDENT)"
echo "  right  : $RIGHT  (label: REFERENCE)"
echo "  out    : $OUT"
echo

mkdir -p "$(dirname "$OUT")"

python features/rendering/render_side_by_side.py \
    --left "$LEFT" --right "$RIGHT" \
    --left-label STUDENT --right-label REFERENCE \
    --out "$OUT"
