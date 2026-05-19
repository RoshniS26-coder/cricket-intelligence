# Batsman Analysis

Compute danger-zone (line × length) and strength-zone profiles for any batsman
already in the database. Optional bilingual Gemini coaching narrative and
matplotlib pitch-map PNG.

Library code: `src/analytics/weakness.py`, `src/analytics/pitch_map.py`,
`src/intelligence/weakness_narrator.py`.

## Quick recipes

| Scenario | Recipe |
|---|---|
| Full report (pitch map + bilingual narrative + JSON) for one batsman | `features/batsman_analysis/run_weakness.sh "<batsman_name>"` |
| List every batsman currently in the DB | `features/batsman_analysis/run_weakness.sh --list` |

For finer control (`--min-confidence`, `--match-id`, custom output paths), use the Python CLI directly — see below.

## Command

```bash
python features/batsman_analysis/analyse_batsman_weakness.py [options]
```

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--batsman NAME` | required | Partial-match batsman name from the DB (e.g. `"Kohli"`) |
| `--match-id ID` | — | Restrict to a single match |
| `--min-confidence FLOAT` | `0.5` | Drop balls where Gemini's average line/length confidence is below this. Set to `0.0` to include every ball regardless of confidence. |
| `--narrative` | off | Call Gemini for a bilingual (EN + HI) coaching narrative — Strengths, Bowling Plan, Batting Advice |
| `--pitch-map` | off | Render a danger-heatmap PNG (red = high danger, green = safe) |
| `--pitch-map-out PATH` | `data/reports/<batsman>_pitch_map.png` | Override output path |
| `--output PATH` | — | Save full JSON profile (zones + narrative) to disk |
| `--list-batsmen` | off | Print every batsman in the DB and exit |

## Output

The CLI prints two Rich tables (Danger Zones, Strength Zones), the primary
weakness/strength callouts, an optional narrative, and writes a pitch map +
JSON if requested. The JSON file matches the shape consumed by the API
(`/analytics/weakness`) and the Streamlit UI Weakness tab.

## Examples

```bash
# List every batsman in the DB
python features/batsman_analysis/analyse_batsman_weakness.py --list-batsmen

# Statistical profile only
python features/batsman_analysis/analyse_batsman_weakness.py --batsman "Virat Kohli"

# Full report — narrative + pitch map + JSON dump
python features/batsman_analysis/analyse_batsman_weakness.py \
    --batsman "Virat Kohli" \
    --narrative --pitch-map \
    --output data/reports/kohli_full_profile.json

# Confidence-relaxed query for a small sample size
python features/batsman_analysis/analyse_batsman_weakness.py \
    --batsman "V Sooryavanshi" --min-confidence 0.0
```
