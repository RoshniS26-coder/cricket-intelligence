#!/usr/bin/env bash
# Generate a one-page AI Coach briefing PDF for a single ball clip.
# Defaults to --skip-pose so it runs in the plain venv (no MediaPipe needed).
# To include pose features, edit this script (remove --skip-pose) and source venv312 first.
#
# Usage:
#   features/ai_coach_briefing/run_briefing.sh <clip> <player> <shot_type> [out_pdf]
#
# Example:
#   features/ai_coach_briefing/run_briefing.sh \
#       data/raw_videos/student_drive.mp4 \
#       "Rahul Kumar" cover_drive \
#       data/reports/rahul_briefing.pdf

set -euo pipefail

if [ $# -lt 3 ]; then
    echo "Usage: $0 <clip> <player> <shot_type> [out_pdf]"
    exit 1
fi

CLIP="$1"
PLAYER="$2"
SHOT="$3"
OUT="${4:-data/reports/$(basename "${CLIP%.*}")_briefing.pdf}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "AI Coach briefing (single ball, solo mode, no pose)"
echo "  clip     : $CLIP"
echo "  player   : $PLAYER"
echo "  shot     : $SHOT"
echo "  out      : $OUT"
echo

mkdir -p "$(dirname "$OUT")"

python features/ai_coach_briefing/render_player_briefing.py \
    --clip "$CLIP" \
    --player "$PLAYER" \
    --shot-type "$SHOT" \
    --skip-pose \
    --out "$OUT"
