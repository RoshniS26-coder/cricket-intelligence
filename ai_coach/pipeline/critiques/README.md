# Critiques

Few-shot Gemini critiques: compare a student's shot clip (or a whole net
practice session) against reference clips of professionals, return a
structured JSON critique with deviations + drill recommendations.

Library code: `src/intelligence/few_shot_critique.py`,
`src/intelligence/critique_prompts.py`,
`src/intelligence/session_catalog.py` (multi-shot pre-pass),
`src/intelligence/coaching_loader.py` (corpus injection).

## Quick recipes

| Scenario | Recipe |
|---|---|
| Single-ball critique, solo mode (auto-anchored to canonical pro for the shot) | `features/critiques/run_critique.sh <clip> <shot_type> "<player>"` |
| Multi-shot net-session critique → multi-section PDF | `features/critiques/run_net_critique.sh <clip> "<player>"` |

For explicit reference clips, coaching keys, or a different model, use the Python CLIs directly — see below.

## Commands

### `critique_student_clip.py` — one shot, one critique

```bash
python features/critiques/critique_student_clip.py [options]
```

| Flag | Required | Purpose |
|---|---|---|
| `--clip PATH` | yes | Student attempt video |
| `--shot-type TYPE` | yes | `cover_drive`, `pull`, `defend`, `sweep`, etc. |
| `--player NAME` | no (`"the player"`) | Used in deviations / encouragement so output addresses the student by name |
| `--references "PATH:Player Name"` | no | Zero or more reference clips (space-separated). When omitted runs in SOLO mode |
| `--reference-player NAME` | no | Solo-mode anchor (e.g. `"Virat Kohli"`); overrides auto-anchor |
| `--no-auto-anchor` | no | Disable canonical-player auto-anchor in solo mode |
| `--coaching-keys "k1,k2"` | no | Inject coaching corpus extracts as expert context |
| `--mode {single_ball,net_session}` | `single_ball` | net_session = student clip is a multi-attempt practice session |
| `--out PATH` | no | JSON output path (printed to stdout if omitted) |
| `--model NAME` | `gemini-2.5-flash` | Gemini model |
| `--no-summary` | off | Skip the human-readable summary; print raw JSON only |

### `critique_multi_shot_session.py` — orchestrator for net sessions

Multi-step: catalog pre-pass enumerates every ball; one critique per shot
type that has ≥ `--min-attempts`; combined multi-section PDF.

```bash
python features/critiques/critique_multi_shot_session.py [options]
```

| Flag | Required | Purpose |
|---|---|---|
| `--clip PATH` | yes¹ | Net practice session video |
| `--player NAME` | yes | Player name on PDFs |
| `--out PATH` | yes | Output PDF path |
| `--academy NAME` | no | Subtitle on PDFs |
| `--min-attempts N` | `3` | Minimum attempts a shot type must have to get its own section |
| `--max-shots N` | no cap | Cap number of shot-type sections (top-N by frequency) |
| `--catalog-model NAME` | `gemini-2.5-pro` | Model for the enumeration pre-pass |
| `--model NAME` | `gemini-3.1-flash-lite-preview` | Model for per-shot critiques |
| `--coaching-keys "k1,k2"` | no | Coaching context applied to all shots |
| `--out-json PATH` | `<out>.json` | Combined critiques JSON |
| `--from-match-id ID` | yes¹ | Skip catalog pre-pass; load ball records from DB for this match (use after `run_pipeline.py`) |

¹ Provide `--clip` OR `--from-match-id`.

## Examples

```bash
# Student vs Kohli, single ball
python features/critiques/critique_student_clip.py \
    --clip data/raw_videos/student_drive.mp4 \
    --shot-type cover_drive --player "Rahul" \
    --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \
    --out data/reports/rahul_critique.json

# Solo mode, auto-anchor to Kohli
python features/critiques/critique_student_clip.py \
    --clip data/raw_videos/student_drive.mp4 \
    --shot-type cover_drive --player "Rahul"

# Multi-shot net session (one PDF for the whole net)
python features/critiques/critique_multi_shot_session.py \
    --clip data/raw_videos/aakash-multishot-netpractice.mp4 \
    --player "Aakash" --academy "Net Practice" \
    --min-attempts 3 \
    --out data/reports/aakash_multi_shot.pdf
```
