# Coaching Corpus & Reference Library

Two related capabilities that build the knowledge bases used by the
critique and briefing pipelines:

- **Coaching corpus** — extract structured technique guidance (key points,
  drills, common mistakes, coaching cues) from coach-tutorial videos.
  Stored as bilingual `{en, hi}` JSON.
- **Reference library** — download / register short YouTube clips of
  ideal-form professionals for the few-shot critique.

Library code: `src/intelligence/coaching_extractor.py`,
`src/intelligence/coaching_prompts.py`,
`src/intelligence/coaching_loader.py`.

## Quick recipes

| Scenario | Recipe |
|---|---|
| Add a coaching tutorial video to the corpus | `features/coaching_corpus/add_coaching.sh <video> <key> "<subject>" <shot_type> ["<player>"]` |
| Download a YouTube reference clip into the library | `features/coaching_corpus/add_reference.sh <youtube_url> <key> <shot_type> "<player>"` |

For pose validation on the reference clip (`--validate`, requires venv312), use the Python CLI directly — see below.

## Commands

### `extract_coaching_video.py` — corpus extraction

Sends a coaching tutorial to Gemini and saves a structured JSON entry into
`data/coaching_corpus/videos/<shot-slug>/<key>.json`, then updates
`data/coaching_corpus/index.yaml`.

```bash
python features/coaching_corpus/extract_coaching_video.py [options]
```

| Flag | Required | Purpose |
|---|---|---|
| `--video PATH` | yes | Tutorial video file |
| `--key SLUG` | yes | Short identifier (e.g. `coach-kohli-cover-hindi`) |
| `--subject "TEXT"` | yes | Free-text subject hint (Gemini grounding) |
| `--shot-type TYPE` | yes | `cover_drive`, `pull`, `front_foot_defence`, etc. |
| `--player NAME` | no | Reference player named in the video, if any |
| `--source-url URL` | no | Original YouTube URL |
| `--model NAME` | `gemini-2.5-flash` | Gemini model |
| `--no-summary` | off | Skip console summary |

### `add_reference_clip.py` — reference library ingestion

Downloads a YouTube clip directly into
`data/reference_library/videos/<shot-slug>/<key>.mp4`, then optionally runs
the pose pipeline to populate validation gates and update `index.yaml`.

```bash
python features/coaching_corpus/add_reference_clip.py [options]
```

| Flag | Required | Purpose |
|---|---|---|
| `--url URL` | yes | YouTube URL |
| `--key SLUG` | yes | e.g. `kohli-cover-3` |
| `--shot-type TYPE` | yes | Subdir under `data/reference_library/videos/` |
| `--player NAME` | yes | Reference player (e.g. `"Virat Kohli"`) |
| `--validate` | off | Run MediaPipe pose validation. **Requires venv312.** |
| `--notes "TEXT"` | no | Free-text notes saved with the manifest entry |

## Examples

```bash
# Add a Hindi-language Kohli cover-drive tutorial
python features/coaching_corpus/extract_coaching_video.py \
    --video data/raw_videos/coach-kohli-cover-hindi.mp4 \
    --key coach-kohli-cover-hindi \
    --subject "Virat Kohli cover drive — Hindi tutorial" \
    --shot-type cover_drive \
    --player "Virat Kohli"

# Download a new reference clip without pose validation
python features/coaching_corpus/add_reference_clip.py \
    --url "https://youtube.com/shorts/EXAMPLE" \
    --key kohli-cover-3 \
    --shot-type cover_drive --player "Virat Kohli"

# Same, with pose validation (requires venv312)
source venv312/bin/activate
python features/coaching_corpus/add_reference_clip.py \
    --url "https://youtube.com/shorts/EXAMPLE" \
    --key kohli-cover-3 \
    --shot-type cover_drive --player "Virat Kohli" \
    --validate
```

## Manifests

- `data/coaching_corpus/index.yaml` — entries with `key`, `shot_type`,
  `player`, `language`, `video_path`, `json_path`, `confidence`, counts of
  technique points / drills / mistakes / cues
- `data/reference_library/index.yaml` — entries with `key`, `shot_type`,
  `player`, `handedness`, `clip_path`, `pose_path`, validation gates
