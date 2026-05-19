#!/usr/bin/env bash
# Run net-practice ball extraction.
#   Mode  : --batch-mode (whole video to Gemini in one call)
#   Format: nets
#   Labels every extracted ball with the named batsman.
#
# Usage:
#   features/ball_extraction/run_nets.sh <video> <batsman_name> [match_id]
#
# Examples:
#   features/ball_extraction/run_nets.sh data/raw_videos/kohli-nets-20260506.mp4 "Virat Kohli"
#   features/ball_extraction/run_nets.sh data/raw_videos/aakash-net1.mov "Aakash" aakash-may-09

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <video> <batsman_name> [match_id]"
    echo "  match_id defaults to the video filename (without extension)."
    exit 1
fi

VIDEO="$1"
BATSMAN="$2"
MATCH_ID="${3:-$(basename "${VIDEO%.*}")}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Net-practice extraction"
echo "  video    : $VIDEO"
echo "  batsman  : $BATSMAN"
echo "  match_id : $MATCH_ID"
echo

python run_pipeline.py \
    --video "$VIDEO" \
    --match-id "$MATCH_ID" \
    --format nets \
    --batsman-name "$BATSMAN" \
    --batch-mode
