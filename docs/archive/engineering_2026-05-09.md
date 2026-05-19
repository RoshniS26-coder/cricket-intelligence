# Engineering Handbook

For developers modifying the Cricket Intelligence Engine. Module-by-module
reference, schema field catalog, migration list, recipes for adding a new
feature, prompt-tuning guide, and common debugging recipes.

> Looking for **what the engine does** at a product level? See
> [`features.md`](features.md). For **system design + diagrams**, see
> [`architecture.md`](architecture.md).

## Table of contents

1. [Repo layout](#repo-layout)
2. [Setup](#setup)
3. [Module reference: `src/`](#module-reference-src)
4. [Module reference: `features/`](#module-reference-features)
5. [Schema field catalog](#schema-field-catalog)
6. [DB migrations](#db-migrations)
7. [Adding a new feature folder](#adding-a-new-feature-folder)
8. [Prompt-tuning guide](#prompt-tuning-guide)
9. [Common debugging recipes](#common-debugging-recipes)

## Repo layout

```
cricket-intelligence/
├── README.md                      # entry point
├── run_pipeline.py                # top-level orchestrator (modes: batch / chunk / timestamps / uniform)
├── requirements.txt
├── .env.example                   # template for GEMINI_API_KEY etc.
│
├── features/                      # user-facing capabilities + recipe shells
│   ├── README.md                  # one-liner index of every recipe
│   ├── ball_extraction/           # run_pipeline.py wrappers
│   │   ├── README.md
│   │   ├── run_nets.sh            # batch-mode wrapper for one batsman
│   │   └── run_broadcast.sh       # chunk-mode wrapper for full T20/ODI
│   ├── batsman_analysis/
│   │   ├── README.md
│   │   ├── analyse_batsman_weakness.py
│   │   └── run_weakness.sh
│   ├── ai_coach_briefing/
│   │   ├── README.md
│   │   ├── render_player_briefing.py     # full hybrid PDF (Gemini + pose + critique + corpus)
│   │   ├── preview_coach_briefing.py     # prose preview from DB
│   │   ├── run_briefing.sh
│   │   └── run_preview.sh
│   ├── critiques/
│   │   ├── README.md
│   │   ├── critique_student_clip.py      # single-ball
│   │   ├── critique_multi_shot_session.py # net session orchestrator
│   │   ├── run_critique.sh
│   │   └── run_net_critique.sh
│   ├── coaching_corpus/
│   │   ├── README.md
│   │   ├── extract_coaching_video.py     # Gemini → bilingual JSON
│   │   ├── add_reference_clip.py
│   │   ├── add_coaching.sh
│   │   └── add_reference.sh
│   ├── pose_analysis/
│   │   ├── README.md
│   │   ├── render_ball_video.py          # MediaPipe → annotated narrated MP4
│   │   └── run_render.sh
│   ├── rendering/
│   │   ├── README.md
│   │   ├── render_side_by_side.py        # ffmpeg hstack/vstack
│   │   └── run_compare.sh
│   └── db_migrations/
│       ├── README.md
│       ├── migrate_add_pose.py
│       ├── migrate_delivery_subtype.py
│       └── migrate_analytics_fields.py   # Tier-1 fields (2026-05-09)
│
├── src/                           # library code (no CLIs)
│   ├── ingestion/downloader.py
│   ├── segmentation/clip_extractor.py
│   ├── intelligence/
│   │   ├── prompt.py                     # SYSTEM, EXTRACTION, BATCH_EXTRACTION prompts
│   │   ├── schema.py                     # BallRecord + 14 enums + GEMINI_JSON_SCHEMA
│   │   ├── extractor.py                  # GeminiExtractor (extract_from_clip + extract_from_video)
│   │   ├── critique_prompts.py           # Few-shot critique prompts
│   │   ├── few_shot_critique.py          # critique_against_references()
│   │   ├── coaching_prompts.py           # bilingual {en,hi} prompts
│   │   ├── coaching_extractor.py         # Tutorial → corpus JSON
│   │   ├── coaching_loader.py            # Looks up corpus by key for prompt injection
│   │   ├── session_catalog.py            # Net-session enumeration pre-pass
│   │   └── weakness_narrator.py          # Bilingual EN+HI Gemini narrative
│   ├── pose/
│   │   ├── extractor.py                  # MediaPipe Tasks API (33-point pose)
│   │   ├── smoothing.py                  # Gap-fill + window smoothing
│   │   └── features/batsman.py           # head_offset, stride, shoulder
│   ├── analytics/
│   │   ├── weakness.py                   # 5×5 line × length grid scoring
│   │   ├── pitch_map.py                  # matplotlib heatmap PNG
│   │   └── briefing.py                   # PlayerBriefing + assemble_briefing
│   ├── report/
│   │   ├── pdf.py                        # reportlab A4 hybrid briefing
│   │   ├── video_renderer.py             # OpenCV overlay + ffmpeg slowdown
│   │   ├── tts.py                        # Edge TTS Indian voices
│   │   └── mux.py                        # ffmpeg audio + video mux
│   ├── validation/normalizer.py          # BallRecordValidator + name aliases + phase derivation
│   ├── storage/db.py                     # SQLAlchemy ORM + CricketDB manager
│   └── api/main.py                       # FastAPI REST API
│
├── ui/app.py                      # Streamlit review UI
│
├── data/
│   ├── raw_videos/                # source videos (gitignored .mp4s)
│   ├── ball_clips/                # ffmpeg-cut per-ball clips (segmented mode)
│   ├── coaching_corpus/           # tutorial videos + extracted JSON + index.yaml
│   ├── reference_library/         # canonical pro shot clips + index.yaml
│   ├── reports/                   # generated PDFs, JSONs, PNGs, MP4s
│   ├── over-time-stamps-json-segment/   # OCR'd scoreboard timestamps (when available)
│   ├── player_aliases.yaml        # short-form → canonical name map
│   └── cricket_intelligence.db    # SQLite (gitignored)
│
├── models/pose_landmarker_full.task   # MediaPipe pose model
│
├── docs/
│   ├── architecture.md            # system design + diagrams
│   ├── engineering.md             # this file
│   ├── features.md                # canonical feature catalog
│   └── archive/                   # superseded / historical docs
│
└── CV_Enhancements/               # gitignored — archived CV/YOLO/Roboflow code
```

## Setup

### Plain venv (default — no MediaPipe)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This works on any Python 3.10+ and supports every feature except pose
analysis. Gemini extraction, batsman weakness, AI Coach briefing
(`--skip-pose`), few-shot critique, coaching corpus, side-by-side
rendering, REST API, Streamlit UI all run here.

### Pose venv (Python 3.12 + MediaPipe)

MediaPipe Tasks API only ships wheels for Python 3.12 right now. Pose-aware
recipes need this venv:

```bash
python3.12 -m venv venv312
source venv312/bin/activate
pip install -r requirements.txt
pip install mediapipe edge-tts
```

Recipes that require it:
- `features/pose_analysis/run_render.sh` (annotated narrated MP4)
- `features/ai_coach_briefing/run_briefing.sh` if you remove `--skip-pose`
- `features/coaching_corpus/add_reference.sh --validate`

The render-render recipe sanity-checks the Python version and exits with
guidance if you forget to activate the right venv.

### External binaries

- `ffmpeg` (with libfreetype if you want side-by-side label burn-in)
- `ffprobe` (ships with ffmpeg)
- `yt-dlp` (for YouTube ingestion / reference-clip download)

### Required environment variables

`GEMINI_API_KEY` is the only one needed for the live pipeline.
`HUGGINGFACE_TOKEN` is needed only for Cric-360 dataset download in
`CV_Enhancements/`. `ROBOFLOW_API_KEY` is unused in the live pipeline.

## Module reference: `src/`

### `src/intelligence/prompt.py`

Holds the three Gemini prompts that drive extraction:

| Symbol | Used by | Purpose |
|---|---|---|
| `SYSTEM_PROMPT` | All Gemini calls | "You are an elite cricket analyst…" — system-level instruction |
| `EXTRACTION_PROMPT` | `extract_from_clip()` | Single-ball prompt with granular shot rubric, swing/spin LH-flip rule, name-confidence guidance, Tier-1 analytics block |
| `BATCH_EXTRACTION_PROMPT` | `extract_from_video()` | Multi-ball prompt with broadcast vs net-practice branching, replay/ad rules, scoreboard dedup, Tier-1 analytics block |

Three accessor functions: `get_system_prompt()`, `get_single_ball_prompt()`,
`get_batch_prompt()`. The CV-augmented variant (`CV_AUGMENTED_TEMPLATE`)
was archived to `CV_Enhancements/prompts/cv_prompt.py` when CV was retired.

### `src/intelligence/schema.py`

Defines `BallRecord` (Pydantic) — the structured per-ball record — plus
14 enums and the `GEMINI_JSON_SCHEMA` mirror used for Gemini structured
output mode.

Enum reference:

| Enum | Values |
|---|---|
| `BowlerType` | pace · spin · unknown |
| `Line` | outside_off · off_stump · middle · leg · outside_leg · unknown |
| `Length` | yorker · full · good · short_of_length · short · unknown |
| `Variation` | none · slower · cutter · bouncer · yorker · spin_variation · unknown |
| `ShotType` | 30 values — broad fallbacks (drive, cut, pull, defend, sweep, …) plus granular subtypes (cover_drive, slog_sweep, late_cut, helicopter, scoop, …) |
| `Footwork` | front_foot · back_foot · neutral · unknown |
| `ContactQuality` | clean · mistimed · edge · miss · unknown |
| `Outcome` | dot · 1 · 2 · 3 · 4 · 6 · wicket · wide · no_ball · unknown |
| `BounceBehavior` | low · normal · steep · unknown |
| `Movement` | none · seam · swing · turn · unknown |
| `SwingDirection` | in_swing · out_swing · none · unknown (in batter's frame) |
| `SwingType` | conventional · late · reverse · none · unknown |
| `SpinDirection` | off_break · leg_break · googly · arm_ball · doosra · carrom · top_spin · slider · none · unknown |
| `BallAgePhase` | new_ball · old · reverse_window · unknown |
| `ShotDirection` ⭑ T1 | 16-position field map (cover, mid_off, fine_leg, third_man, …) + behind_wicket, none, unknown |
| `DismissalType` ⭑ T1 | bowled · caught · lbw · run_out · stumped · hit_wicket · caught_and_bowled · retired · obstructing · none · unknown |
| `BowlerCrease` ⭑ T1 | over_the_wicket · round_the_wicket · wide_of_crease · unknown |
| `EdgeType` ⭑ T1 | inside_edge · outside_edge · top_edge · bottom_edge · none · unknown |
| `InningsPhase` ⭑ T1 | powerplay · middle_overs · death · unknown |
| `Handedness` ⭑ T1 | right_handed · left_handed · unknown |

⭑ T1 = Tier-1 analytics enrichment, added 2026-05-09.

### `src/intelligence/extractor.py`

`GeminiExtractor` class — two main entry points:

| Method | Used by | Behaviour |
|---|---|---|
| `extract_from_clip(clip_path, …)` | Per-clip workflow (timestamps mode, segmented mode) | Uploads one clip, runs `EXTRACTION_PROMPT`, returns one `BallRecord` |
| `extract_from_video(video_path, chunk_offset, ball_index_offset, …)` | Batch + chunk modes | Uploads a full video / chunk, runs `BATCH_EXTRACTION_PROMPT`, returns N `BallRecord`s. Applies replay/ad/scoreboard dedup as a post-validator. |

Both honour `GEMINI_JSON_SCHEMA` for structured output — Gemini returns
JSON conforming to the schema; no regex parsing. Sleeps 1 s between
per-clip calls to be kind to the API.

### `src/intelligence/session_catalog.py`

`run_session_catalog(clip, model, force)` — net-practice enumeration
pre-pass. Used by the multi-shot critique orchestrator to count deliveries
by `shot_type` and `contact_quality` before running per-shot critiques.

Has an undercount safeguard: if Gemini returns < 5 balls in a > 2-min
video or < 1 ball per 30 s, the result is dropped (assumed to be a
summarisation rather than enumeration). Bypass with `force=True`.

### `src/intelligence/coaching_loader.py`

`load_coaching_context(keys)` — reads `data/coaching_corpus/index.yaml`,
returns the parsed JSON for each key. Used by both `render_player_briefing`
and the critique CLIs to inject coaching corpus content into prompts.

### `src/validation/normalizer.py`

`BallRecordValidator.validate_record(record, format_str)` — runs the full
normalisation pass on every Gemini-emitted `BallRecord`:

1. **Player-name canonicalisation** — `resolve_player_name()` looks up
   `data/player_aliases.yaml` and replaces short forms (`Iyer` →
   `Shreyas Iyer`).
2. **Phase derivation** — if Gemini left `phase=unknown`, derive from
   `over` + `format_str` using T20 / ODI rules.
3. **Cross-field consistency** — clear `spin_direction` for pace bowlers,
   clear `swing_direction` for spin bowlers, force `contact_quality=miss`
   for `shot_type=leave`, etc.
4. **Inferred fields from `raw_description`** — fuzzy-match swing/spin
   keywords if Gemini left those fields unknown.
5. **Confidence flag** — append warning if avg confidence < 0.5 (review
   queue).

`derive_phase(over, format_str)` and `resolve_player_name(name)` are
exposed for direct use elsewhere.

### `src/storage/db.py`

`CricketDB` wraps SQLAlchemy + SQLite. Two ORM classes (`MatchRecord`,
`BallDBRecord`) mirror the Pydantic models. Key methods:

| Method | Purpose |
|---|---|
| `create_match(dict)` | Idempotent merge into matches table |
| `save_ball(BallRecord)` | Per-record save, idempotent on `ball_id` |
| `save_balls_batch(records)` | Batch save with per-record error handling |
| `get_balls_for_match(match_id)` | Ordered by innings → over → ball |
| `get_balls_for_batsman(name, match_id?, min_confidence)` | Partial-match, confidence-gated |
| `get_balls_needing_review(match_id?)` | Ordered by lowest avg confidence |
| `update_ball_review(ball_id, updates, reviewed_by)` | Coach correction path; sets `is_reviewed=True` |
| `list_batsmen(match_id?)` | Distinct non-null batsman names |
| `get_stats(match_id?)` | Aggregate counts + outcome breakdown |

### `src/analytics/weakness.py`

`compute_weakness_profile(balls, batsman_name)` — 5×5 line × length grid.
Per cell:

- `total` (balls in zone)
- `dismissals`
- `false_shots` (mistimed + edge + miss)
- `avg_runs`
- `boundaries`
- `danger_score = α·dismissal_rate + β·false_shot_rate + γ·(1 - avg_runs/4)`
- `strength_score = α·boundary_rate + β·(avg_runs/4)`

Picks `top_weakness` and `top_strength` for the call-out. Returns a dict
that the pitch-map renderer and bilingual narrator both consume.

### `src/analytics/pitch_map.py`

`render_pitch_map(profile, output_path, title)` — pure matplotlib. No
YOLO, no cv2. Renders the 5×5 grid as a heatmap with red = danger,
green = safe, grey = no data. Saves PNG.

### `src/analytics/briefing.py`

`assemble_briefing(player_name, shot_type, clip_path, gemini, pose_features,
critique, coaching_context, …)` — combines four data sources into a
`PlayerBriefing` Pydantic model. Consumed by `src/report/pdf.py`.

### `src/pose/`

- `extractor.py:extract_pose_from_clip(clip)` — MediaPipe Tasks API
  (downloads model on first use to `models/pose_landmarker_full.task`).
  Returns a list of 33-landmark dicts, one per frame.
- `smoothing.py:smooth_landmarks(pose, window, max_gap)` — moving-window
  + interpolation gap-fill.
- `features/batsman.py:compute_features(pose)` — head_lateral_offset,
  stride_length_norm, shoulder_angle_deg, plus boolean threshold flags.

### `src/report/`

| Module | Purpose |
|---|---|
| `pdf.py` | reportlab one-page A4 hybrid briefing + multi-section PDF |
| `video_renderer.py` | OpenCV overlay + ffmpeg slowdown for narrated annotated MP4 |
| `tts.py` | Edge TTS — Indian English voice (`en-IN-PrabhatNeural` default) |
| `mux.py` | ffmpeg mux audio + video, with stretch-to-match-audio option |

## Module reference: `features/`

Each `features/<name>/` folder is a user-facing capability. Two file types:

- **Python CLIs** (e.g. `analyse_batsman_weakness.py`) — full flag access.
  Argparse-driven. Self-documenting via `--help`.
- **Recipe shells** (e.g. `run_weakness.sh`) — wrapper that hard-codes
  sensible defaults and accepts only the 1–4 things that actually change
  per invocation.

Each folder also has a `README.md` listing its commands, flag tables, and
example invocations.

For an at-a-glance index of every recipe with copy-paste usage, see
[`features/README.md`](../features/README.md).

## Schema field catalog

The fields a `BallRecord` carries when produced by `GeminiExtractor`,
post-validation:

| Field | Type | Source | Notes |
|---|---|---|---|
| `ball_id` | str (PK) | Built as `{match_id}_{over}_{ball_number}` | Unique within DB |
| `match_id` | str (FK) | CLI flag | Foreign key to `matches` |
| `innings` | int | Default 1 | 1 or 2 |
| `over`, `ball_number` | int | Gemini scoreboard read OR sequential fallback | Used in dedup |
| `bowler_name`, `batsman_name` | str | Gemini scoreboard / commentary read | Validator canonicalises via `player_aliases.yaml` |
| `bowler_type` | enum | Gemini | pace / spin / unknown |
| `line`, `length` | enum | Gemini | 5-bucket each |
| `variation`, `bounce_behavior`, `movement` | enum | Gemini | |
| `swing_direction`, `swing_type`, `spin_direction`, `ball_age_phase` | enum | Gemini | Always in batter's reference frame (LH-flip rule in prompt) |
| `shot_type`, `footwork`, `contact_quality` | enum | Gemini | Granular shot rubric in prompt |
| `outcome` | enum | Gemini | dot / 1-6 / wicket / wide / no_ball |
| `runs_scored` | int 0-6 | Gemini | Bounded in prompt + schema |
| `shot_direction` ⭑ T1 | enum | Gemini | 16-position field map, batter's POV |
| `dismissal_type` ⭑ T1 | enum | Gemini | Required when `outcome=wicket` |
| `dismissal_fielder` ⭑ T1 | str? | Gemini | "Stokes at slip" |
| `bowling_speed_kmph` ⭑ T1 | float? | Gemini reads broadcast graphic | None if not visible |
| `bowler_crease` ⭑ T1 | enum | Gemini | over / round / wide |
| `edge_type` ⭑ T1 | enum | Gemini | Required when `contact_quality=edge` |
| `phase` ⭑ T1 | enum | Gemini OR validator-derived from over+format | T20: PP=1-6, mid=7-15, death=16-20 |
| `batsman_handedness` ⭑ T1 | enum | Gemini | Should be consistent per batter across video |
| `confidence.*` | float 0-1 | Gemini | Per-field confidence; review queue gates on these |
| `clip_path`, `clip_start_time`, `clip_end_time` | str | Pipeline | Where to find the source video + timestamps |
| `raw_description` | text | Gemini | 1–2 sentence free-form summary |
| `is_reviewed`, `reviewed_by` | bool, str | Streamlit Review UI | Set when coach corrects |
| `pose_features` | JSON? | Pose pipeline (separate write path) | head/stride/shoulder dict |
| `created_at`, `updated_at` | datetime | DB | |

## DB migrations

All idempotent (PRAGMA-guarded). Run all three in order on a fresh checkout:

```bash
python features/db_migrations/migrate_add_pose.py
python features/db_migrations/migrate_delivery_subtype.py
python features/db_migrations/migrate_analytics_fields.py
```

| Migration | Adds |
|---|---|
| `migrate_add_pose.py` | `balls.pose_features` (JSON) and the `ground_truth` table for the flywheel |
| `migrate_delivery_subtype.py` | `swing_direction`, `swing_type`, `spin_direction`, `ball_age_phase` to `balls` |
| `migrate_analytics_fields.py` | Tier-1 fields: `shot_direction`, `dismissal_type`, `dismissal_fielder`, `bowling_speed_kmph`, `bowler_crease`, `edge_type`, `phase`, `batsman_handedness` to `balls`; `match_date`, `day_or_night` to `matches` |

## Adding a new feature folder

```bash
mkdir features/my_new_feature
cd features/my_new_feature

# 1. Drop your Python CLI in here, e.g. my_thing.py
#    Add this at the top so src/* imports work:
#       sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# 2. Add a recipe shell with sensible defaults
cat > run_my_thing.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python features/my_new_feature/my_thing.py "$@"
EOF
chmod +x run_my_thing.sh

# 3. Add README.md following the same template as the other feature folders
#    (Quick recipes table → command reference → examples → library code pointers)

# 4. Add to features/README.md's recipe index
# 5. Add to docs/features.md table
```

## Prompt-tuning guide

When you observe systematic Gemini errors:

1. **Confirm the error pattern.** Query the DB for low-confidence rows or
   manually check ~20 Streamlit Review balls. Don't tune off a single
   anecdote.
2. **Locate the right prompt.** Single-ball errors → `EXTRACTION_PROMPT`.
   Broadcast-wide errors (replays counted, missing balls) →
   `BATCH_EXTRACTION_PROMPT`. Coaching extracts → `coaching_prompts.py`.
3. **Add a numbered rubric, not free prose.** Gemini follows enumerated
   rules better than narrative paragraphs.
4. **Test on a holdout.** Re-extract one short video before and after.
   Compare structured output diff.
5. **If you add a new field, also add it to:**
   - `BallRecord` in `schema.py`
   - `GEMINI_JSON_SCHEMA` (mirror)
   - Optional confidence subfield in `ConfidenceScores`
   - `extract_from_clip` AND `extract_from_video` in `extractor.py`
   - `BallDBRecord` in `storage/db.py`
   - `save_ball()` mapping in `storage/db.py`
   - A migration in `features/db_migrations/`
   - The schema field catalog in this doc

The Tier-1 enrichment pass (2026-05-09) followed exactly that checklist
and is a good worked example.

## Common debugging recipes

### "All my batsman_name fields are split across short/long forms"

Add the missing aliases to `data/player_aliases.yaml`. The validator picks
them up on next save. For already-stored rows, run a one-off SQL UPDATE or
re-extract.

### "Gemini is missing balls in a broadcast"

Common causes:
1. Scoreboard OCR is glitching — check `raw_description` for nonsense
   over.ball strings.
2. Chunk boundary is cutting a delivery in half — try `--chunk-duration 60`
   to make chunks smaller.
3. Gemini summarised instead of enumerated — switch to `--catalog-model
   gemini-2.5-pro` (only on critique pre-pass).

### "Pose extraction returns empty"

- Check Python version is 3.12 (`python --version`)
- Check MediaPipe is installed (`pip show mediapipe`)
- Check the source clip is side-on; pose models lose the batter on
  behind-the-arm shots
- Check `models/pose_landmarker_full.task` is present and ~9 MB

### "PDF generation fails with reportlab errors"

- Verify `reportlab>=4.1.0` is installed
- Check that `assemble_briefing` returned a non-None object
- For multi-section PDFs, confirm at least one shot type passed
  `--min-attempts`

### "Streamlit shows no batsmen for the Weakness tab"

- Run `features/batsman_analysis/run_weakness.sh --list` to confirm DB has
  batsman names
- If DB has names but none qualify: the default `--min-confidence 0.5`
  may exclude all rows. The Streamlit slider lets you drop to 0.0.

### "ffmpeg drawtext filter unavailable"

Some Homebrew bottles ship without libfreetype. The side-by-side renderer
gracefully falls back to label-less output. To enable burned-in labels:

```bash
brew reinstall ffmpeg --with-libfreetype  # or just `brew reinstall ffmpeg` on recent Homebrew
```

### "I want to re-enable Roboflow CV grounding"

See `CV_Enhancements/README.md` — three restore routes documented (full
restore, OpenCV ball tracker only, custom YOLO training).
