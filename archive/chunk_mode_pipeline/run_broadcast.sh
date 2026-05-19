#!/usr/bin/env bash
# Run T20 / ODI / Test broadcast ball extraction.
#   Mode  : --chunk-mode --chunk-duration 90 (90s ffmpeg chunks → batch Gemini per chunk)
#   Format: T20 (override with --format ODI / Test by editing this file)
#
# Usage:
#   features/ball_extraction/run_broadcast.sh <video> <match_id> <team_a> <team_b>
#
# Example:
#   features/ball_extraction/run_broadcast.sh \
#       data/raw_videos/T20-IndvsEng.mp4 \
#       T20-IndvsEng India England

set -euo pipefail

if [ $# -lt 4 ]; then
    echo "Usage: $0 <video> <match_id> <team_a> <team_b>"
    exit 1
fi

VIDEO="$1"
MATCH_ID="$2"
TEAM_A="$3"
TEAM_B="$4"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Broadcast extraction"
echo "  video    : $VIDEO"
echo "  match_id : $MATCH_ID"
echo "  team A   : $TEAM_A"
echo "  team B   : $TEAM_B"
echo "  chunk    : 90s × N chunks → Gemini per chunk"
echo

python run_pipeline.py \
    --video "$VIDEO" \
    --match-id "$MATCH_ID" \
    --format T20 \
    --team-a "$TEAM_A" \
    --team-b "$TEAM_B" \
    --chunk-mode --chunk-duration 90
