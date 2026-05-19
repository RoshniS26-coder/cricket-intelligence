#!/usr/bin/env bash
# Multi-shot net session critique → multi-section PDF.
# Catalogs every ball, then runs one critique per shot type with ≥3 attempts.
#
# Usage:
#   features/critiques/run_net_critique.sh <clip> <player_name> [out_pdf]
#
# Example:
#   features/critiques/run_net_critique.sh \
#       data/raw_videos/aakash-multishot-netpractice.mp4 \
#       "Aakash" \
#       data/reports/aakash_multi_shot.pdf

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <clip> <player_name> [out_pdf]"
    exit 1
fi

CLIP="$1"
PLAYER="$2"
OUT="${3:-data/reports/$(basename "${CLIP%.*}")_multi_shot.pdf}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Multi-shot net session critique"
echo "  clip   : $CLIP"
echo "  player : $PLAYER"
echo "  out    : $OUT"
echo "  rule   : ≥3 attempts → its own section"
echo

mkdir -p "$(dirname "$OUT")"

python features/critiques/critique_multi_shot_session.py \
    --clip "$CLIP" \
    --player "$PLAYER" \
    --min-attempts 3 \
    --out "$OUT"
