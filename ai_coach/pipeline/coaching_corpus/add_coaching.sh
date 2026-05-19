#!/usr/bin/env bash
# Extract a coaching tutorial video into the bilingual coaching corpus.
# Saves a JSON entry under data/coaching_corpus/videos/<shot>/<key>.json
# and updates data/coaching_corpus/index.yaml.
#
# Usage:
#   features/coaching_corpus/add_coaching.sh <video> <key> <subject> <shot_type> [player]
#
# Example:
#   features/coaching_corpus/add_coaching.sh \
#       data/raw_videos/coach-kohli-cover-hindi.mp4 \
#       coach-kohli-cover-hindi \
#       "Virat Kohli cover drive — Hindi tutorial" \
#       cover_drive \
#       "Virat Kohli"

set -euo pipefail

if [ $# -lt 4 ]; then
    echo "Usage: $0 <video> <key> <subject> <shot_type> [player]"
    exit 1
fi

VIDEO="$1"
KEY="$2"
SUBJECT="$3"
SHOT="$4"
PLAYER="${5:-}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Coaching corpus extraction"
echo "  video   : $VIDEO"
echo "  key     : $KEY"
echo "  shot    : $SHOT"
echo "  subject : $SUBJECT"
[ -n "$PLAYER" ] && echo "  player  : $PLAYER"
echo

PLAYER_ARG=""
[ -n "$PLAYER" ] && PLAYER_ARG="--player $PLAYER"

python features/coaching_corpus/extract_coaching_video.py \
    --video "$VIDEO" \
    --key "$KEY" \
    --subject "$SUBJECT" \
    --shot-type "$SHOT" \
    $PLAYER_ARG
