# Ball Extraction

End-to-end pipeline: video in → per-ball structured records.

Library code: `src/intelligence/`, `src/segmentation/`, `src/storage/`.

## Quick recipes

| Scenario | Recipe |
|---|---|
| Net practice (one batsman, all balls labeled with their name) | `features/ball_extraction/run_nets.sh <video> <batsman_name>` |
| T20 broadcast — quick start (chunked, may have ball_id collisions on long videos) | `features/ball_extraction/run_broadcast.sh <video> <match_id> <team_a> <team_b>` |
| **T20 broadcast — two-phase ffmpeg+Gemini (recommended for long videos)** | Phase 1: `features/ball_extraction/run_segment_video.sh <video> <match_id>` · Phase 2: `features/ball_extraction/run_extract_balls_from_clips.sh <manifest>` |

For full control of every flag, use `python run_pipeline.py` directly — see "Mode selection" below.

## Two-phase workflow (recommended for long broadcasts)

The cleanest end-to-end path for full T20 / ODI broadcasts:

1. **Phase 1 — ffmpeg cuts** the full video into overlapping clips on disk.
   The clips persist so you can play them, verify them, and re-process them
   if Phase 2 fails partway through.
2. **Phase 2 — Gemini per clip** extracts ball-by-ball data with the full
   `BATCH_EXTRACTION_PROMPT`. Output is JSON only (per-clip + cross-clip
   merged); **no DB write** until you're satisfied with quality and explicitly
   import.

### Why this beats `--chunk-mode`

`--chunk-mode` does its dedup *within a single chunk's Gemini call*, so the
same `(over, ball)` value emitted by two different chunks collides at DB
save time and one silently overwrites the other. The two-phase workflow
keeps each chunk's records separate, then merges them with **confidence-
weighted dedup**: the version of `(over=1, ball=4)` with the highest avg
Gemini confidence wins.

### Run it

```bash
# Phase 1 — cut a 2-hour broadcast into ~15 × 10-min overlapping clips (~1-2 min wall, $0)
features/ball_extraction/run_segment_video.sh \
    data/raw_videos/IndiaBatting-T20-IndvsEng.mp4 \
    T20-IndvsEng-IndBat

# Output: data/video_clips_T20-IndvsEng-IndBat/
#   ├── T20-IndvsEng-IndBat_chunk_001.mp4
#   ├── ...
#   ├── T20-IndvsEng-IndBat_chunk_015.mp4
#   └── manifest.json

# Phase 2 — Gemini per clip with the production-grade model (~15-30 min, ~$5-10)
features/ball_extraction/run_extract_balls_from_clips.sh \
    data/video_clips_T20-IndvsEng-IndBat/manifest.json

# Output: data/video_clips_T20-IndvsEng-IndBat/balls/
#   ├── chunk_001_balls.json     (raw per-clip Gemini output)
#   ├── ...
#   ├── chunk_015_balls.json
#   └── all_records.jsonl        (every raw record with chunk provenance — one JSON object per line)

# Phase 2b (optional) — once you've reviewed per-clip JSONs and you're happy,
# re-run with --merge to produce a deduplicated cross-clip artifact:
features/ball_extraction/run_extract_balls_from_clips.sh \
    data/video_clips_T20-IndvsEng-IndBat/manifest.json --merge

# Adds: data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json
```

Defaults: **10-min chunks, 2-min overlap, gemini-3.1-pro-preview** for
Phase 2. Merging is **off by default** — inspect per-clip output first,
then opt in with `--merge` when you're ready. Override anything with the
recipe's pass-through flags or call the Python CLIs directly.

### Quick validation run

Before committing to the full 2-hour run, validate end-to-end on 2 clips:

```bash
features/ball_extraction/run_segment_video.sh \
    data/raw_videos/IndiaBatting-T20-IndvsEng.mp4 \
    T20-IndvsEng-IndBat-test \
    10 --max-chunks 2

features/ball_extraction/run_extract_balls_from_clips.sh \
    data/video_clips_T20-IndvsEng-IndBat-test/manifest.json \
    --max-clips 2
```

~2-4 min wall + ~$1 cost. Inspect `merged_balls.json` to confirm Gemini is
identifying balls correctly before paying for the full run.

### Inspecting `merged_balls.json`

```bash
# Total balls detected
jq 'length' data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json

# One-line summary per ball
jq -r '.[] | "\(.over).\(.ball_number) \(.bowler_name) → \(.batsman_name)  \(.shot_type)  \(.outcome)"' \
    data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json

# Coverage check
jq -r '.[] | .over' data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json | sort -n | uniq -c

# Any wickets?
jq '.[] | select(.outcome == "wicket")' data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json
```

### Importing to the DB (when ready)

The merged JSON has the same shape as `BallRecord`. When the output looks
right, a separate small import script (TBD — ~30 lines) will: load the JSON,
run the validator + alias resolver, and call `CricketDB.save_balls_batch()`.
Until then, the JSON is the artifact.

See [`docs/tasks/2026-05-11-paddle-ocr-scoreboard-timeline.md`](../../docs/tasks/2026-05-11-paddle-ocr-scoreboard-timeline.md)
for the full task spec and architectural rationale.

## Direct CLI — `python run_pipeline.py`

For one-shot extraction without the two-phase persistence layer (suitable
for short videos):

```bash
python run_pipeline.py [options]
```

### Input source (one required)

| Flag | Purpose |
|---|---|
| `--video PATH` | Local video file to ingest |
| `--youtube-url URL` | Download via yt-dlp into `data/raw_videos/` |

### Match metadata

| Flag | Default | Purpose |
|---|---|---|
| `--match-id NAME` | `test_match_001` | Used as DB key + ball_id prefix |
| `--format` | `T20` | T20 / ODI / Test |
| `--team-a`, `--team-b` | `Team A`, `Team B` | Stored in matches table |
| `--batsman-name NAME` | — | Override batsman_name on every extracted ball (use when one player faces every delivery, e.g. nets) |

### Mode selection (one path)

| Flag | What happens | When to use |
|---|---|---|
| `--batch-mode` | Upload the whole video to Gemini; Gemini auto-detects every live ball delivery (1 API call) | **Short videos** (≤ ~12 min): nets, highlight reels |
| `--chunk-mode` `--chunk-duration 90.0` | Cut video into 90s ffmpeg chunks (in-memory tempdir, no overlap); batch Gemini per chunk; save direct to DB | Quick-and-dirty long video extraction. **Has cross-chunk collision issues — prefer the two-phase workflow above for production.** |
| `--timestamps FILE` | Cut on supplied JSON timestamps, then Gemini per clip | You have hand-curated or externally-OCR'd timestamps |
| `--uniform` `--segment-duration 8.0` `--max-clips 30` | Uniformly slice the video, then Gemini per clip | Quick demo / test mode |

### Other

| Flag | Purpose |
|---|---|
| `--model NAME` | Gemini model (default `gemini-2.5-flash`) |
| `--skip-extraction` | Stop after segmentation |

### Outputs

- `data/ball_clips/<match_id>/*.mp4` — ffmpeg cuts (segmented modes only)
- `data/<match_id>_extracted.json` — flat per-ball JSON
- `data/cricket_intelligence.db` — `balls` and `matches` tables

### Examples

```bash
# Net practice — batch mode is right
python run_pipeline.py \
    --video data/raw_videos/kohli-nets-20260506.mp4 \
    --match-id kohli-nets-20260506 --format nets \
    --batsman-name "Virat Kohli-Net Practice" \
    --batch-mode

# Short broadcast highlights
python run_pipeline.py \
    --video data/raw_videos/highlight.mp4 \
    --match-id ind-eng-2026 --format T20 --team-a India --team-b England \
    --batch-mode

# Long broadcast: use the two-phase workflow instead — see top of this README.
```
