# Task: Two-phase ffmpeg-then-Gemini ball extraction for long broadcasts

**Created:** 2026-05-11
**Status:** code complete · pending live validation on IndiaBatting.mp4
**Owner:** see git blame

This task is the source of truth for the implementation. The implementation
must read this document and refer back to it. The historical exploration
(PaddleOCR and Gemini-timeline-only approaches) is summarised in §9.

## 1. Context

The current `run_broadcast.sh` chunk-mode pipeline produced 86 records on
the IndiaBatting T20 video, but ~30 of them have colliding `ball_id`s
because each chunk's `extract_from_video()` does dedup only locally — and
broadcast realities (pre-match graphics, replays, ad-break stickers all
show "1.1") mean the same `(over, ball)` value gets emitted by multiple
chunks. `CricketDB.save_ball()` uses `session.merge()` keyed on `ball_id`,
so the second save silently overwrites the first. The DB ends up with ~55
unique balls vs the ~117-120 actual deliveries in a T20 innings.

We considered:
- PaddleOCR on cropped scoreboards — works but the broadcast scoreboard
  contains *two* number-pair fields ("team-score 1-0" and "over.ball
  0.1/20"), and our regex was grabbing the team score. Could be fixed but
  user opted to switch to a Gemini-based approach.
- Gemini timeline-only chunks — focused prompt that asks Gemini to return
  *only* over.ball timestamps. Worked but Gemini's timestamp precision was
  noisy and a separate Pass-2 was still needed to fill in line / length /
  shot data.

**Chosen architecture:** a single Gemini pass per chunk that extracts the
FULL ball data (BATCH_EXTRACTION_PROMPT), with overlapping chunks +
confidence-weighted cross-clip merge to handle the collision problem.
Persistent on-disk clips so each phase is independently inspectable. JSON-
only output so the user can iterate without DB primary-key headaches.

## 2. Goal

Produce a clean per-ball merged JSON for an arbitrary T20 broadcast such
that:

- ≥ 110 unique deliveries detected from a 2-hour video (vs current 55)
- Zero `(over, ball, innings)` duplicates in the merged JSON
- Every record has the full BATCH_EXTRACTION_PROMPT field set
  (line, length, shot, contact, outcome, dismissal info, bowling speed,
  …) — Tier-1 analytics fields included
- No DB write — JSON only — until quality is verified

## 3. Architecture

```
INPUT
  data/raw_videos/IndiaBatting-T20-IndvsEng.mp4     (105 min, 358 MB)
                  │
                  ▼
PHASE 1 — Persistent chunking (ffmpeg only, no Gemini)
  features/ball_extraction/segment_video.py
    1. ffprobe → total duration
    2. plan_chunks(total, chunk_min=10, overlap_sec=120)
       → ~15 chunks for a 2-hour video, 2-min overlap
    3. ffmpeg stream-copy per chunk → data/video_clips_<match>/chunk_NNN.mp4
    4. Write manifest.json with abs_start_sec / length_sec per chunk
                  │
                  ▼
PHASE 2 — Gemini per clip + cross-clip merge (JSON only)
  features/ball_extraction/extract_balls_from_clips.py
    1. Read manifest.json
    2. For each chunk:
       - Upload to Gemini Files API
       - Call BATCH_EXTRACTION_PROMPT + GEMINI_JSON_SCHEMA
       - Convert clip-relative timestamps → absolute (chunk_offset + ts)
       - Save per-clip raw JSON
    3. Merge across clips via merge_records_across_clips():
       - Group by (innings, over, ball_number)
       - Keep highest avg-confidence version
       - Append unscored records (over=0, ball=0) separately
       - Sort by (innings, over, ball)
    4. Write merged_balls.json + all_records.jsonl
       NO DB WRITE
```

## 4. Files

### New

| Path | Purpose | LoC |
|---|---|---|
| `features/ball_extraction/segment_video.py` | Phase 1 CLI: ffmpeg-cut + manifest | ~240 |
| `features/ball_extraction/run_segment_video.sh` | Phase 1 recipe | ~60 |
| `features/ball_extraction/extract_balls_from_clips.py` | Phase 2 CLI: Gemini per clip + merge | ~240 |
| `features/ball_extraction/run_extract_balls_from_clips.sh` | Phase 2 recipe | ~70 |
| `tests/test_extract_balls_from_clips.py` | 11 unit tests for the merge logic (mocked, no live Gemini) | ~165 |
| `docs/tasks/2026-05-11-paddle-ocr-scoreboard-timeline.md` | (this file) | — |

### Reused (no changes)

- `src/intelligence/prompt.py:BATCH_EXTRACTION_PROMPT` — the user prompt
- `src/intelligence/prompt.py:SYSTEM_PROMPT` — the system instruction
- `src/intelligence/schema.py:GEMINI_JSON_SCHEMA` — the structured-output JSON schema

### Untouched (consumed by future DB-import step, not by this task)

- `src/storage/db.py:CricketDB.save_balls_batch()`
- `src/validation/normalizer.py:BallRecordValidator`

## 5. CLI contracts

### Phase 1 — `segment_video.py`

```
python features/ball_extraction/segment_video.py \
    --video PATH                # required
    --match-id ID               # required
    --out-dir DIR               # default data/video_clips_<match_id>/
    --chunk-min FLOAT           # default 10.0
    --overlap-sec FLOAT         # default 120.0 (2 min)
    --start-sec FLOAT           # default 0.0
    --end-sec FLOAT             # default 0 = end of video
    --max-chunks INT            # default 0 = all; >0 for debug
```

Recipe wrapper: `features/ball_extraction/run_segment_video.sh <video> <match_id> [chunk_min] [extra flags…]`

### Phase 2 — `extract_balls_from_clips.py`

```
python features/ball_extraction/extract_balls_from_clips.py \
    --manifest PATH                  # required (output of Phase 1)
    --model NAME                     # default gemini-3.1-pro-preview
    --max-clips INT                  # default 0 = all
    --out-dir DIR                    # default <manifest_dir>/balls/
    --sleep-between-clips FLOAT      # default 1.0
```

Recipe wrapper: `features/ball_extraction/run_extract_balls_from_clips.sh <manifest_path> [extra flags…]`

## 6. Merge semantics (the only new business logic)

`merge_records_across_clips(records)` in
`features/ball_extraction/extract_balls_from_clips.py`:

1. Group records by `(over, ball_number, innings)` triple.
2. For each group, keep the record with the highest
   `_record_avg_confidence` (averaged across line, length, shot_type,
   outcome, contact_quality).
3. Ties go to the first record encountered (insertion order).
4. Records with `over=0 AND ball_number=0` (no scoreboard read) are kept
   separately and appended at the end, sorted by `abs_start_sec` — they
   aren't deduped because they have no usable identity.
5. Output is sorted by `(innings, over, ball_number)` followed by the
   unscored tail.

11 unit tests in `tests/test_extract_balls_from_clips.py` cover the merge
behavior with mocked records — no live Gemini calls.

## 7. Acceptance criteria

After running both phases on `IndiaBatting-T20-IndvsEng.mp4` and inspecting
the merged JSON:

```bash
jq 'length' data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json
# Expected: >= 110

jq -r '[.[] | select(.over > 0) | "\(.over).\(.ball_number)"] | unique | length' \
    data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json
# Expected: equal to the `length` above (no duplicates among scored balls)

jq -r '.[] | .over' data/video_clips_T20-IndvsEng-IndBat/balls/merged_balls.json | sort -n | uniq -c
# Expected: balls spread across overs 1 through 20 (or however many the innings lasted)
```

## 8. Verification checklist

- [x] `pytest tests/test_extract_balls_from_clips.py` passes — **11/11**
- [x] `python -m py_compile $(find src features -name '*.py')` passes
- [x] Phase 1 recipe (no args) prints usage cleanly
- [x] Phase 2 recipe (no args) prints usage cleanly
- [ ] On a 2-clip debug run: `merged_balls.json` contains ~15-25 unique balls with full BATCH_EXTRACTION_PROMPT fields — **awaiting validation**
- [ ] On the full 15-chunk run: ≥110 unique balls with no collisions — **awaiting full run**
- [ ] DB import script written + run (separate task, not this one)

## 9. History — what was tried before

Two earlier approaches were built and then retired:

### PaddleOCR + regex on cropped scoreboards (retired 2026-05-11)
- Idea: sample 1 frame/sec, crop the scoreboard footer `0 318 640 42`, run
  PaddleOCR locally, regex-extract `X.Y/20` as the over.ball.
- Outcome: PaddleOCR's raw OCR was actually 90-97% accurate, but our
  regex was matching the *team score* (`1-0`) instead of the over.ball
  (`0.1/20`). Fixable in 10 minutes by tightening the regex, but the user
  opted for a Gemini-based path instead.
- Removed: `src/intelligence/scoreboard_ocr.py`,
  `features/ball_extraction/extract_timestamps.py`,
  `features/ball_extraction/run_extract_timestamps.sh`,
  `tests/test_scoreboard_ocr.py`, `[ocr]` group from `pyproject.toml`.

### Gemini-timeline-only via overlapping chunks (retired 2026-05-11)
- Idea: focused prompt asking Gemini only for over.ball + first-seen
  timestamps per chunk (no shot / line / length data), then feed
  timestamps into `run_pipeline.py --timestamps` for Pass-2.
- Outcome: Worked but Gemini's timestamp precision was rough (±5-10s with
  Flash, ±2-4s with Pro); some chunks hallucinated timestamps past their
  own length (e.g. emitting `217s` for a `180s` chunk); chunk 10 of one
  test run returned `None` instead of JSON and lost ~12 deliveries. The
  user decided that running the *full* extraction (BATCH_EXTRACTION_PROMPT)
  per chunk gives the same dedup benefit AND fills in the rich fields in
  one pass — no second pass needed.
- Removed: `src/intelligence/scoreboard_timeline_gemini.py`,
  `features/ball_extraction/extract_timestamps_gemini.py`,
  `features/ball_extraction/run_extract_timestamps_gemini.sh`,
  `tests/test_scoreboard_timeline_gemini.py`.

## 10. Out of scope

- DB import. The merged JSON is the artifact this task produces; importing
  it into the SQLite DB is a separate small task (~30 LoC, will be added
  later once Gemini extraction quality is validated).
- Re-architecting Phase 2's Gemini call — it uses the same
  `BATCH_EXTRACTION_PROMPT` as everything else in the codebase. Prompt
  improvements are a separate exercise.
- Validation / alias resolution / phase derivation — that lives in
  `src/validation/normalizer.py` and will be applied at DB-import time.

## 11. References

- `src/intelligence/prompt.py:BATCH_EXTRACTION_PROMPT` (lines 178-342) —
  the prompt sent to Gemini per chunk.
- `src/intelligence/schema.py:GEMINI_JSON_SCHEMA` — the structured-output
  schema Gemini is constrained to.
- `data/over-time-stamps-json-segment/T20-IndvsEng_timestamps.json` —
  reference format for the legacy `--timestamps` pipeline (not used here).
