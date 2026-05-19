#!/usr/bin/env bash
# Download a reference clip from YouTube into the reference shot library.
# Skips pose validation by default (no MediaPipe needed).
#
# Usage:
#   features/coaching_corpus/add_reference.sh <youtube_url> <key> <shot_type> <player>
#
# Example:
#   features/coaching_corpus/add_reference.sh \
#       "https://youtube.com/shorts/EXAMPLE" \
#       kohli-cover-3 cover_drive "Virat Kohli"

set -euo pipefail

if [ $# -lt 4 ]; then
    echo "Usage: $0 <youtube_url> <key> <shot_type> <player>"
    exit 1
fi

URL="$1"
KEY="$2"
SHOT="$3"
PLAYER="$4"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "Reference clip download"
echo "  url    : $URL"
echo "  key    : $KEY"
echo "  shot   : $SHOT"
echo "  player : $PLAYER"
echo "  note   : pose validation skipped — pass --validate manually for MediaPipe"
echo

python features/coaching_corpus/add_reference_clip.py \
    --url "$URL" \
    --key "$KEY" \
    --shot-type "$SHOT" \
    --player "$PLAYER"
