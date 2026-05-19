# AI-Coach Briefing

One-page hybrid PDF briefing per player, combining four AI engines:
1. Gemini per-ball extraction (line, length, swing, shot, contact, outcome)
2. MediaPipe pose features (head offset, stride, shoulder angle) — optional
3. Few-shot Gemini critique vs reference clips — optional
4. Coaching corpus context (drills + cues from extracted tutorials) — optional

Library code: `src/analytics/briefing.py`, `src/report/pdf.py`,
`src/intelligence/session_catalog.py`, `src/intelligence/coaching_loader.py`.

## Quick recipes

| Scenario | Recipe |
|---|---|
| One-page PDF briefing for a single ball clip (no pose, no references) | `features/ai_coach_briefing/run_briefing.sh <clip> "<player>" <shot_type>` |
| Quick prose preview from balls already in the DB (no PDF) | `features/ai_coach_briefing/run_preview.sh <match_id> ["<batsman>"]` |

For pose features, references, coaching keys, or net-session mode, use the Python CLIs directly — see below.

## Commands

### `render_player_briefing.py` — full hybrid briefing

```bash
python features/ai_coach_briefing/render_player_briefing.py [options]
```

| Flag | Required | Purpose |
|---|---|---|
| `--clip PATH` | yes | Student / player video |
| `--player NAME` | yes | Shown in the PDF |
| `--shot-type TYPE` | yes | `cover_drive`, `pull`, `defend`, etc. |
| `--out PATH` | yes | Output PDF path |
| `--mode {single_ball,net_session}` | no (default `single_ball`) | net_session triggers the catalog pre-pass for multi-ball videos |
| `--references "PATH:Player Name"` | no | Zero or more reference clips (space-separated). Empty = solo mode |
| `--coaching-keys "key1,key2"` | no | Inject coaching-corpus extracts (looked up in `data/coaching_corpus/index.yaml`) |
| `--reference-player NAME` | no | Solo-mode anchor (e.g. `"Virat Kohli"`); overrides auto-anchor |
| `--no-auto-anchor` | no | Disable canonical-player auto-anchor in solo mode |
| `--catalog-model MODEL` | no | Model for the net-session catalog pre-pass (default `gemini-2.5-pro`) |
| `--force-catalog` | no | Skip the undercount safeguard on the catalog pre-pass |
| `--skip-pose` | no | Skip MediaPipe (works in plain venv, no MediaPipe needed) |
| `--skip-gemini` | no | Skip Gemini extraction; pose-only briefing |
| `--academy NAME` | no | Subtitle on PDFs |

Pre-req for the pose layer: `source venv312/bin/activate` (MediaPipe needs
Python 3.12). Without `--skip-pose`, the script will import MediaPipe.

### `preview_coach_briefing.py` — quick text preview

Pre-PDF, qualitative prose summary using only Gemini extraction already in the
DB. No pose, no critique — useful when you've just run `run_pipeline.py` and
want to eyeball the output before generating a full PDF.

```bash
python features/ai_coach_briefing/preview_coach_briefing.py [options]
```

| Flag | Required | Purpose |
|---|---|---|
| `--match-id ID` | yes | Match key in the DB |
| `--batsman NAME` | no | Filter to one batsman |

## Examples

```bash
# Full hybrid briefing — needs venv312 (MediaPipe)
source venv312/bin/activate
python features/ai_coach_briefing/render_player_briefing.py \
    --clip data/raw_videos/student_drive.mp4 \
    --player "Rahul Kumar" --shot-type cover_drive \
    --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \
    --coaching-keys "coach-kohli-cover-hindi" \
    --out data/reports/rahul_briefing.pdf

# Pose-skipped (works in plain venv)
python features/ai_coach_briefing/render_player_briefing.py \
    --clip data/raw_videos/kohli-nets-20260506.mp4 \
    --player "Virat Kohli" --shot-type cover_drive \
    --skip-pose --mode net_session \
    --out data/reports/kohli_nets_briefing.pdf

# Quick prose preview
python features/ai_coach_briefing/preview_coach_briefing.py \
    --match-id kohli-nets-20260506 --batsman "Virat Kohli-Net Practice"
```
