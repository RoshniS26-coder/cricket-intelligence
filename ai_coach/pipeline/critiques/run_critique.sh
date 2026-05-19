#!/usr/bin/env bash
# Single-ball critique: student clip vs canonical professional (auto-anchored).
# Solo mode — no reference clips required, Gemini uses its intrinsic cricket
# knowledge plus the auto-anchored player for the named shot.
#
# Usage:
#   features/critiques/run_critique.sh <clip> <shot_type> <player_name> [out_json]
#
# Example:
#   features/critiques/run_critique.sh \
#       data/raw_videos/student_drive.mp4 cover_drive "Rahul" \
#       data/reports/rahul_critique.json

set -euo pipefail

if [ $# -lt 3 ]; then
    echo "Usage: $0 <clip> <shot_type> <player_name> [out_json]"
    exit 1
fi

CLIP="$1"
SHOT="$2"
PLAYER="$3"
OUT="${4:-data/reports/$(basename "${CLIP%.*}")_critique.json}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Single-ball critique (solo, auto-anchored)"
echo "  clip   : $CLIP"
echo "  shot   : $SHOT"
echo "  player : $PLAYER"
echo "  out    : $OUT"
echo

mkdir -p "$(dirname "$OUT")"

python features/critiques/critique_student_clip.py \
    --clip "$CLIP" \
    --shot-type "$SHOT" \
    --player "$PLAYER" \
    --out "$OUT"
