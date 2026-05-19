#!/usr/bin/env bash
# Quick prose-only AI Coach briefing using ONLY data already in the DB.
# No PDF, no pose, no critique — just a Gemini-narrated paragraph from the
# extracted ball records.
#
# Usage:
#   features/ai_coach_briefing/run_preview.sh <match_id> [batsman_name]
#
# Examples:
#   features/ai_coach_briefing/run_preview.sh kohli-nets-20260506
#   features/ai_coach_briefing/run_preview.sh kohli-nets-20260506 "Virat Kohli-Net Practice"

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <match_id> [batsman_name]"
    exit 1
fi

MATCH_ID="$1"
BATSMAN_ARG=""
if [ -n "${2:-}" ]; then
    BATSMAN_ARG="--batsman $2"
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "AI Coach prose preview"
echo "  match_id : $MATCH_ID"
[ -n "${2:-}" ] && echo "  batsman  : $2"
echo

python features/ai_coach_briefing/preview_coach_briefing.py \
    --match-id "$MATCH_ID" \
    $BATSMAN_ARG
