# cricket-intelligence — project context for Claude

This file is auto-loaded at the start of every Claude Code session. It
captures the STATIC understanding of the project (purpose, structure,
conventions). For dynamic day-to-day state (what's in the DB right now,
what was worked on yesterday), see **`docs/project_context.md`** —
updated via the `/update-context` slash command at the end of a session.

---

## Purpose

A cricket-intelligence pipeline that turns one T20 broadcast match into
a structured ball-by-ball dataset (~120-240 records per match, 28 fields
per ball) usable for opposition prep, weakness analysis, and franchise
scouting. Primary deliverable today: clean per-match data; downstream:
multi-match analytics + UI for coaches.

## Three data sources (always combined)

1. **Cricsheet** — open-source ball-by-ball JSON. Authoritative for
   WHO bowled / batted / runs / outcome / dismissals.
2. **ESPNCricinfo commentary** — analyst prose per ball, saved manually
   as PDF and parsed with `pypdf`. Primary truth for technique fields
   (line, length, shot, footwork, contact).
3. **Gemini-on-broadcast-video** (optional, expensive) — adds visual-only
   fields: `bowling_speed_kmph` (scoreboard speed gun) and
   `bowler_crease` (over-the-wicket vs round-the-wicket).

## The pipeline (text-only synthesis)

`gemini-2.5-pro` is given Cricsheet + ESPN (+ optional video records)
per over and emits one synthesized record per ball. Per-over outputs
are checkpointed to a resume directory so a crash mid-run loses nothing.

Final merged JSON → loaded into SQLite via `scripts/load_synth_to_db.py`
under `match_id={cricsheet_match_id}` with **innings-qualified ball_ids**
(`{match_id}_i{innings}_{over}_{ball}`) to prevent collisions between
the two innings of the same match.

### Cost per match
- Text-only (ESPN + Cricsheet): ~$0.50 + ~17 min wall time per innings
- + video pass (gemini-3.1-pro on chunks): ~$5-6 + ~2-3 hrs extra per innings

Recommended default: text-only for everything; add video selectively
for matches where bowler-side speed/crease analysis is the deliverable.

---

## Directory map

```
cricket-intelligence/
├── CLAUDE.md                       ← this file
├── README.md                       ← user-facing readme
├── pyproject.toml, requirements.txt
├── run_pipeline.py                 ← legacy chunk-mode orchestrator (kept; not part of active flow)
│
├── src/                            ← reusable libraries
│   ├── analytics/
│   │   ├── pitch_map.py            ← DANGER heatmap renderer (weakness-aware)
│   │   ├── heatmaps.py             ← FREQUENCY heatmap + wagon wheel (newer, generic)
│   │   ├── weakness.py             ← per-batter weakness aggregation
│   │   └── briefing.py             ← AI coaching narrative generator
│   ├── intelligence/
│   │   ├── cricsheet.py            ← Cricsheet loader + innings/ball helpers
│   │   ├── espn_commentary.py      ← Parse ESPN JSON → join to Cricsheet ball_ids
│   │   ├── extractor.py            ← Gemini-on-video extractor (used by run_pipeline.py)
│   │   ├── prompt_synthesis.py     ← ⭐ ACTIVE — text-only synthesis prompt (gemini-2.5-pro)
│   │   └── schema.py               ← Pydantic + Gemini JSON schemas
│   ├── storage/db.py               ← SQLAlchemy models + CricketDB class
│   ├── segmentation/               ← Video clip extraction
│   ├── detection/                  ← (moved to CV_Enhancements/)
│   └── validation/normalizer.py
│
├── features/                       ← CLI scripts grouped by feature
│   ├── ball_extraction/            ← ⭐ ACTIVE pipeline (4 files only)
│   │   ├── export_cricsheet_innings.py ← cricsheet match JSON → one innings JSON
│   │   ├── import_cricsheet.py         ← bulk cricsheet importer
│   │   └── synthesize_match_json.py    ← TEXT-ONLY synth (cricsheet + ESPN + opt video)
│   ├── audio_pipeline/
│   │   ├── parse_espn_pdf.py       ← ESPN PDF → structured commentary JSON
│   │   └── transcribe.py           ← faster-whisper audio transcription
│   ├── bowler_analysis/
│   │   └── bowler_report.py        ← per-bowler stats + matchups + markdown/JSON
│   ├── batsman_analysis/
│   │   ├── analyse_batsman_weakness.py ← danger-map analysis (uses pitch_map.py)
│   │   ├── batsman_report.py           ← per-batter stats + matchups + markdown/JSON
│   │   └── run_weakness.sh
│   ├── heatmap/
│   │   └── generate_heatmaps.py    ← bulk pitch maps + wagon wheels for all players
│   ├── rendering/                  ← side-by-side video comparisons
│   ├── pose_analysis/              ← OpenPose-derived pose data
│   ├── coaching_corpus/            ← coaching video tagged corpus
│   ├── ai_coach_briefing/          ← AI-generated coaching briefs
│   ├── critiques/
│   └── db_migrations/
│
├── scripts/                        ← one-off operational scripts
│   └── load_synth_to_db.py         ← load synthesized JSON into DB (wipe + insert)
│
├── ui/
│   └── app.py                      ← Streamlit UI (Weakness Analysis + Full Dataset)
│
├── data/                           ← match data + outputs (large; .gitignore for big files)
│   ├── cricket_intelligence.db     ← SQLite — current DB
│   ├── cricsheet/<match_dir>/      ← cricsheet raw + per-innings JSONs
│   ├── espncricinfo/               ← raw ESPN PDFs + parsed per-innings JSONs
│   ├── IndvsEng_chunk*_with_cricsheet.json  ← per-chunk video extraction (innings 2)
│   ├── IndvsEng_full_match_correct.json     ← canonical innings 2 synth output
│   ├── IndvsEng_innings1_full_match_correct.json ← canonical innings 1 synth output
│   ├── IndvsEng_match_1276906_full.csv      ← combined 240-row CSV
│   ├── IndvsEng_synthesized/                ← innings 2 per-over resume checkpoints
│   ├── IndvsEng_innings1_synthesized/       ← innings 1 per-over resume checkpoints
│   ├── bowler_analysis/<match_innings>/     ← per-bowler markdown + JSON
│   ├── batsman_analysis/<match_innings>/    ← per-batter markdown + JSON
│   ├── heatmaps/match_<id>_innings_<n>/     ← pitch map + wagon wheel PNGs + index.md
│   └── raw_videos/                          ← downloaded broadcast videos
│
├── docs/
│   ├── architecture.md             ← deep technical reference (current state)
│   ├── schema.md                   ← DB schema + field provenance
│   ├── heatmaps_explained.md       ← frequency vs danger heatmap explainer
│   ├── project_context.md          ← DYNAMIC rolling log, updated via /update-context
│   ├── tasks/                      ← per-task docs (document-first approach)
│   └── archive/                    ← retired docs (engineering, features, dated snapshots)
│
├── archive/                        ← superseded files kept for reference only
│   ├── README.md                   ← what's in here and why
│   ├── chunk_mode_pipeline/        ← retired chunk-mode code (prompt.py, extractors, runners)
│   └── data/
│       ├── chunk_mode_experiments/ ← chunk-mode test outputs (v2, v3, 60min, etc.)
│       ├── chunk_prompt_experiments/ ← old v1-v4 prompt iteration outputs
│       └── cricket_intelligence.db.pre-tier1.bak ← pre-migration DB snapshot
│
├── tests/                          ← pytest
├── models/                         ← model weights / configs
├── CV_Enhancements/                ← detection + tracking code (moved out of src/)
├── venv/, venv312/                 ← Python virtual environments
└── .claude/                        ← Claude Code settings + slash commands
```

---

## Database schema (high level)

Two tables in `data/cricket_intelligence.db`:

- **`matches`** — `match_id` (PK), format, team_a, team_b, venue, date
- **`balls`** — `ball_id` (PK, format: `{match_id}_i{innings}_{over}_{ball_number}`),
  match_id (FK), innings, over_number, ball_number, bowler_name, batsman_name,
  + 23 technique fields (line, length, shot_type, contact_quality, footwork,
  bowler_type, variation, movement, swing_direction, swing_type, spin_direction,
  bowler_crease, bowling_speed_kmph, ball_age_phase, shot_type, edge_type,
  shot_direction, dismissal_type, dismissal_fielder, batsman_handedness, phase,
  raw_description, confidence scores), is_reviewed flag, timestamps.

See `src/storage/db.py` and `src/intelligence/schema.py` for full
column definitions and enums.

### Current contents (refresh in `docs/project_context.md` after each session)
At the time CLAUDE.md was last hand-edited, the DB contained:
- **1 match** (`1276906` — ENG vs IND, 3rd T20I, Trent Bridge, Jul 2022)
- **240 ball rows** (innings 1: 120, innings 2: 120)

For up-to-date state, see `docs/project_context.md`.

---

## Conventions

### File naming
- Match-level outputs: `{match_id_or_label}_full_match_correct.json` (synth)
- Innings 1 variant: `{label}_innings1_full_match_correct.json`
- Per-over checkpoints live in `{label}_synthesized/over_{NN}.json`
- Per-chunk video extraction: `{label}_chunk{N}_with_cricsheet.json`

### Don't do
- **Never embed ad-hoc cricket-colleague corrections into prompts as expected
  values.** They are validation signal only. (Memorialized in `~/.claude/.../memory/project_ground_truth_precedence.md`.)
- **Never write a per-broadcaster crop+regex or PaddleOCR pipeline as the
  primary alignment.** Use audio peaks, Whisper, Gemini-for-timestamps,
  or Cricsheet joins — must generalize across broadcasters.
  (Memorialized in `~/.claude/.../memory/feedback_alignment_must_generalize.md`.)
- **Don't add new chunk-mode experiments to `data/IndvsEng_chunk*_with_*.json`.**
  The synthesis pipeline is the current path. Old experiments live in `archive/`.

### Where to put new code
- A new analysis lens (per-team, per-tournament, etc.) → `features/<feature_name>/<name>_report.py`
- A new data source loader → `src/intelligence/<source>.py`
- A new visualisation → `src/analytics/<type>.py`
- A one-off script → `scripts/<name>.py`
- A new doc/explainer → `docs/<topic>.md`

### Git
- Branch: `main` (no PR workflow established yet — direct commits)
- Don't commit `data/raw_videos/*.mp4` (big files; tracked via `.gitignore`)
- Don't commit `data/cricket_intelligence.db` if it gets large — currently small enough

---

## Pipeline cheatsheet (how to add a new match)

```bash
# 1. Get Cricsheet JSON for the match
# Manually: cricsheet.org → download → put under data/cricsheet/<match_dir>/

# 2. Export one innings (or both)
python features/ball_extraction/export_cricsheet_innings.py \
    --cricsheet-id <id> --innings <Team> --out data/cricsheet/<dir>/<team>_innings.json

# 3. Save ESPN PDF manually
# Open the ball-by-ball page on espncricinfo.com → switch to the right innings tab
# → scroll TOP-to-BOTTOM so all 20 overs render in DOM → Cmd+P → Save as PDF
# → drop in data/espncricinfo/

# 4. Parse the PDF
python features/audio_pipeline/parse_espn_pdf.py \
    --pdf "data/espncricinfo/<file>.pdf" \
    --out data/espncricinfo/<match_dir>/match_<id>_innings<n>_commentary.json \
    --match-id <id>

# 5. (Optional) Process video chunks for the "bowling speed + crease" fields
# Only worth it for bowler-side analysis. ~$5 + 2-3 hrs per innings.
# See features/ball_extraction/extract_with_cricsheet.py + run_pipeline.py

# 6. Synthesise — text-only, ~$0.50, ~17 min per innings
python features/ball_extraction/synthesize_match_json.py \
    --cricsheet-json data/cricsheet/<dir>/<team>_innings.json \
    --espn-commentary data/espncricinfo/<dir>/match_<id>_innings<n>_commentary.json \
    --gemini-video-glob 'data/<label>_chunk*_with_cricsheet.json' \  # or 'data/NONEXISTENT_chunk*.json' if no video
    --out data/<label>_innings<n>_full_match_correct.json \
    --resume-dir data/<label>_innings<n>_synthesized \
    --model gemini-2.5-pro

# 7. Load to DB
python scripts/load_synth_to_db.py \
    --input data/<label>_innings<n>_full_match_correct.json \
    --match-id <id> --team-a <team> --team-b <team> --format T20 \
    [--skip-wipe if a second innings of same match]

# 8. Generate analysis (any of these stand-alone)
python features/bowler_analysis/bowler_report.py --match-id <id> --innings <n> --out data/bowler_analysis/...
python features/batsman_analysis/batsman_report.py --match-id <id> --innings <n> --out data/batsman_analysis/...
python features/heatmap/generate_heatmaps.py --match-id <id> --innings <n> --out-dir data/heatmaps/...

# 9. Export combined CSV from DB
python -c "from src.storage.db import CricketDB; from features.ball_extraction.merge_and_save_to_db import export_csv; export_csv('<id>', 'data/<label>_full.csv', CricketDB())"

# 10. Update project context — at session end
# (Type the /update-context slash command and follow the template)
```

---

## When in doubt
- For dynamic state ("what's in DB today", "what did we work on yesterday"),
  read `docs/project_context.md`.
- For decisions/preferences ("why is ESPN the primary truth"), check
  Claude's auto-memory in `~/.claude/projects/.../memory/`.
- For design rationale on a specific component, look in `docs/`.
