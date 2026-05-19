# archive/

Files that were superseded but kept for reference rather than deleted.
Anything here is **not used by the current pipeline**. Safe to ignore
unless you're reconstructing the history of a decision.

## Contents

### `chunk_mode_pipeline/`
The pre-synthesis pipeline that processed broadcast video in 5-minute
chunks via Gemini and emitted per-chunk JSONs. Retired around 2026-05-09
in favour of the text-only synthesis pipeline (Cricsheet + ESPN +
optional video, gemini-2.5-pro). The chunk-mode approach produced
~30 colliding `ball_id`s per match because each chunk's extractor only
de-duplicated locally, so the DB lost ~50% of unique deliveries on save.

Code:
- `prompt.py` — full-extraction prompt (video → all 28 fields)
- `prompt_technique_only.py` — chunk-mode-v2 prompt
- `extract_balls_from_clips.py` — chunk-mode v1 extractor (calls `prompt.py`)
- `extract_with_cricsheet.py` — chunk-mode v2 extractor (calls `prompt_technique_only.py`)
- `segment_video.py` — chunk-mode video segmenter
- `merge_and_save_to_db.py` — merges chunk JSONs into the DB (replaced by `scripts/load_synth_to_db.py`)
- `eval_against_cricsheet.py` — eval tool comparing chunk-mode outputs to Cricsheet
- `run_broadcast.sh`, `run_extract_balls_from_clips.sh`, `run_segment_video.sh`, `run_nets.sh`
  — shell wrappers around the above
- `test_prompts.py` — tests for `prompt.py` only (no synthesis-prompt tests yet — gap to address)

### `data/chunk_mode_experiments/`
Per-chunk Gemini outputs from chunk-mode prompt-iteration rounds (v1-v4)
and a few ad-hoc test outputs:

- `IndvsEng_60min_v3/`, `IndvsEng_ball_by_ball/`, `IndvsEng_ball_by_ball_60min/`,
  `IndvsEng_ball_by_ball_v2/`, `IndvsEng_ball_by_ball_v3_25pro/`,
  `IndvsEng_ball_by_ball_v3_pro31/` — per-iteration `chunk_001_balls.json`
  + `all_records.jsonl` outputs
- `T20-IndvsEng-IndBat-chunkmode-c1-90s_extracted.json` — 90-second smoke-test chunk
- `T20-IndvsEng-IndBat_extracted.json` — chunk-mode full IndBat extraction
- `T20-IndvsEng_extracted.json` — chunk-mode full-match extraction
- `IndvsEng_balls.csv`, `IndvsEng_india_only.csv` — chunk-mode merged CSV exports

The current canonical match output lives in `data/IndvsEng_full_match_correct.json`
(innings 2) and `data/IndvsEng_innings1_full_match_correct.json` (innings 1).
The current canonical CSV is `data/IndvsEng_match_1276906_full.csv` (240 rows).

### `data/chunk_prompt_experiments/`
Older per-chunk Gemini outputs from very early prompt-iteration rounds
(pre-synthesis pipeline):

- `IndvsEng_chunk1_with_espn.json` — first cut, ESPN as a third signal
- `IndvsEng_chunk1_with_espn_v2.json` — added Rule A but with leaked ball IDs in the prompt
- `IndvsEng_chunk1_with_espn_v3.json` — de-leaked Rule A, but Rule B still had a Pant example
- `IndvsEng_chunk1_with_espn_v4_clean.json` — fully clean prompt (no train-on-test contamination)
- `IndvsEng_chunk2_with_espn{,_v4_clean}.json` — chunk 2 versions of the above
- `IndvsEng_chunk1_with_whisper.json` — Whisper-only commentary attempt before ESPN PDF route was chosen
- `IndvsEng_merged.json` — old chunk-mode merge output

### `data/cricket_intelligence.db.pre-tier1.bak`
SQLite snapshot from before the Tier-1 migration (May 2026). Contained
12 test/legacy matches with the old non-innings-qualified `ball_id`
format. Kept in case we need to recover any of those rows; otherwise
ignore.
