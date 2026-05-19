#!/usr/bin/env bash
# Phase 1 of the two-phase ball-extraction workflow: cut a full broadcast
# video into overlapping chunks via ffmpeg stream-copy.
#
# After this, run Phase 2 (run_extract_balls_from_clips.sh) to send each
# clip to Gemini for ball-by-ball extraction.
#
# Usage:
#   features/ball_extraction/run_segment_video.sh <video> <match_id> [chunk_min] [extra flags...]
#
# Positional args:
#   <video>      Required. Path to broadcast video.
#   <match_id>   Required. Used in clip filenames + output dir name.
#   [chunk_min]  Optional. Chunk duration in MINUTES (default 10). Pass "" to
#                keep the default while still supplying extra flags.
#
# Extra flags (passed through to segment_video.py):
#   --overlap-sec N      Overlap seconds between chunks (default 120 = 2 min)
#   --max-chunks N       Stop after N chunks (for quick debug runs)
#   --start-sec / --end-sec   Slice the video before chunking
#   --out-dir DIR        Override default data/video_clips_<match_id>/
#
# Examples:
#   # Default: 10-min chunks, 2-min overlap, full video
#   features/ball_extraction/run_segment_video.sh \
#       data/raw_videos/IndiaBatting-T20-IndvsEng.mp4 T20-IndvsEng-IndBat
#
#   # Quick test: 2 chunks only
#   features/ball_extraction/run_segment_video.sh \
#       data/raw_videos/IndiaBatting-T20-IndvsEng.mp4 T20-IndvsEng-IndBat-test \
#       10 --max-chunks 2

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <video> <match_id> [chunk_min] [extra flags...]"
    echo "  chunk_min defaults to 10 (minutes). Pass '' to keep default while adding flags."
    echo
    echo "  Run python features/ball_extraction/segment_video.py --help"
    echo "  for the full list of flags."
    exit 1
fi

VIDEO="$1"
MATCH_ID="$2"
shift 2

# Third positional is chunk duration in MINUTES (optional). Skip if it's a flag.
CHUNK_MIN=10
if [ $# -gt 0 ] && [[ "$1" != --* ]]; then
    if [ -n "$1" ]; then
        CHUNK_MIN="$1"
    fi
    shift
fi
EXTRA_ARGS=("$@")

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT_DIR="data/video_clips_${MATCH_ID}"

echo "Phase 1 — video segmentation (ffmpeg)"
echo "  video       : $VIDEO"
echo "  match_id    : $MATCH_ID"
echo "  chunk_min   : $CHUNK_MIN min"
echo "  out_dir     : $OUT_DIR"
if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
    echo "  extra       : ${EXTRA_ARGS[*]}"
fi
echo

python features/ball_extraction/segment_video.py \
    --video "$VIDEO" \
    --match-id "$MATCH_ID" \
    --out-dir "$OUT_DIR" \
    --chunk-min "$CHUNK_MIN" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
