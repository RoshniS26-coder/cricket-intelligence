#!/usr/bin/env bash
# Phase 2 of the two-phase ball-extraction workflow.
# Reads the manifest.json from Phase 1 (run_segment_video.sh), sends each
# pre-cut clip to Gemini for full ball-by-ball extraction, merges across
# clips, writes JSON only (NO database write).
#
# Pre-req:
#   - Phase 1 must have run successfully (manifest.json exists)
#   - GEMINI_API_KEY in .env
#
# Usage:
#   features/ball_extraction/run_extract_balls_from_clips.sh <manifest_path> [extra flags...]
#
# Positional args:
#   <manifest_path>  Required. Path to manifest.json from Phase 1.
#
# Extra flags (passed through to extract_balls_from_clips.py):
#   --model NAME           Gemini model (default gemini-2.5-pro)
#   --max-clips N          Stop after N clips (for quick debug runs)
#   --out-dir DIR          Override where JSONs are written
#   --sleep-between-clips  Seconds to pause between Gemini calls
#
# Examples:
#   # Default run on a Phase-1 manifest
#   features/ball_extraction/run_extract_balls_from_clips.sh \
#       data/video_clips_T20-IndvsEng-IndBat/manifest.json
#
#   # Quick test on first 2 clips with Pro
#   features/ball_extraction/run_extract_balls_from_clips.sh \
#       data/video_clips_T20-IndvsEng-IndBat/manifest.json \
#       --max-clips 2 --model gemini-2.5-pro

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <manifest_path> [extra flags...]"
    echo "  <manifest_path> is the manifest.json from Phase 1 (run_segment_video.sh)."
    echo
    echo "  Run python features/ball_extraction/extract_balls_from_clips.py --help"
    echo "  for the full list of flags."
    exit 1
fi

MANIFEST="$1"
shift
EXTRA_ARGS=("$@")

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ ! -f "$MANIFEST" ]; then
    echo "✗ manifest not found: $MANIFEST"
    echo "  Did you run Phase 1 first?"
    echo "    features/ball_extraction/run_segment_video.sh <video> <match_id>"
    exit 1
fi

# Sanity check: GEMINI_API_KEY
if [ -z "${GEMINI_API_KEY:-}" ]; then
    if [ -f .env ] && grep -q "^GEMINI_API_KEY=" .env; then
        :  # python-dotenv will load it
    else
        echo "⚠ GEMINI_API_KEY not in environment or .env."
        echo "  Get a key at: https://aistudio.google.com/apikey"
        echo "  Then add to .env:  GEMINI_API_KEY=your_key"
        exit 1
    fi
fi

echo "Phase 2 — per-clip ball extraction (Gemini)"
echo "  manifest    : $MANIFEST"
if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
    echo "  extra       : ${EXTRA_ARGS[*]}"
fi
echo

python features/ball_extraction/extract_balls_from_clips.py \
    --manifest "$MANIFEST" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
