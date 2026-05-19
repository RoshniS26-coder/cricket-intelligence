#!/usr/bin/env bash
# Compute batsman weakness profile + bilingual narrative + pitch-map PNG.
# Reads from data/cricket_intelligence.db (must already contain extracted balls).
#
# Usage:
#   features/batsman_analysis/run_weakness.sh <batsman_name> [match_id]
#
# Examples:
#   features/batsman_analysis/run_weakness.sh "Virat Kohli"
#   features/batsman_analysis/run_weakness.sh "V Sooryavanshi" suryavanshi-ind-aus
#   features/batsman_analysis/run_weakness.sh --list   # list all batsmen in DB

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <batsman_name> [match_id]"
    echo "       $0 --list              # list every batsman in the DB"
    exit 1
fi

if [ "$1" = "--list" ]; then
    python features/batsman_analysis/analyse_batsman_weakness.py --list-batsmen
    exit 0
fi

BATSMAN="$1"
MATCH_ARG=""
if [ -n "${2:-}" ]; then
    MATCH_ARG="--match-id $2"
fi

echo "Weakness analysis"
echo "  batsman  : $BATSMAN"
[ -n "${2:-}" ] && echo "  match_id : $2"
echo "  outputs  : pitch map PNG, bilingual narrative, JSON profile"
echo

python features/batsman_analysis/analyse_batsman_weakness.py \
    --batsman "$BATSMAN" \
    --min-confidence 0.0 \
    --narrative \
    --pitch-map \
    $MATCH_ARG
