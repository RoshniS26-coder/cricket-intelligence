# Cricket Intelligence

**A structured, queryable layer on top of public cricket data — designed for opposition prep, scouting, and weakness analysis at the ball-by-ball level.**

Turn one T20 broadcast match into a clean per-ball dataset (~120-240 records, 28 fields each), then aggregate across matches to surface batter-vs-bowler matchups, line-length weakness maps, scoring zones, and dismissal patterns that no public source publishes as structured data.

## What it produces

For any T20 or ODI match in the corpus:

| Artifact | What it is |
|---|---|
| **240-row ball-by-ball table** | Every delivery with line, length, shot type, footwork, contact quality, outcome, dismissal, optional bowling speed + crease angle |
| **Per-batsman scouting card** | Balls faced, SR, shot distribution, scoring zones, per-bowler matchups, phase splits, dismissal pattern |
| **Per-bowler scouting card** | Balls bowled, economy, dot %, length distribution, per-batter matchups, dismissals taken |
| **Pitch map** | 5×5 line × length frequency heatmap, per batsman |
| **Wagon wheel** | 8-zone polar scoring chart, per batsman, auto-mirrored for LHB |
| **Weakness heatmap** | Per-cell danger score (dismissals + runs suppressed), highlighting exploitable zones |
| **Streamlit UI** | Browse the DB, export rich CSVs, view weakness analysis per batter |

## How it works

Three data sources, synthesized into one record per ball by `gemini-2.5-pro`:

1. **Cricsheet** — open ball-by-ball JSON. Authoritative for *who bowled, who batted, runs, dismissal*.
2. **ESPNCricinfo commentary** — analyst prose per ball, saved as PDF, parsed with `pypdf`. Primary truth for *technique* (line, length, shot, footwork, contact).
3. **Gemini-on-broadcast-video** *(optional)* — adds *bowling speed* (scoreboard speed gun) and *bowler crease* (over/round the wicket). The only fields not derivable from text sources.

Synthesis is checkpointed per over so a crash mid-run loses nothing. Loaded into SQLite under innings-qualified `ball_id` (`{match_id}_i{innings}_{over}_{ball}`).

### Cost per match
- **Text-only** (Cricsheet + ESPN): ~$0.50 + ~17 min wall time **per innings**
- **+ video pass** (Gemini-on-video chunks): adds ~$5-6 + 2-3 hrs **per innings** — worth it only when bowler-side speed/crease analysis is the deliverable

For the moat analysis (what this gives you vs. ESPN, Cricsheet, CricViz), see [`docs/architecture.md`](docs/architecture.md).

## Quick install

```bash
git clone <repo>
cd cricket-intelligence
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# .env — set GEMINI_API_KEY
cp .env.example .env
$EDITOR .env

# Run DB migrations (idempotent)
python scripts/db_migrations/migrate_add_pose.py
python scripts/db_migrations/migrate_delivery_subtype.py
python scripts/db_migrations/migrate_analytics_fields.py
```

## Add a new match (the 10-step recipe)

```bash
MATCH_ID=<cricsheet_id>          # e.g. 1276906
LABEL=<readable_label>           # e.g. IndvsEng_2024_T20I_1

# 1. Get the Cricsheet JSON (download from cricsheet.org)
# Drop under data/cricsheet/<match_dir>/

# 2. Export one innings (repeat for innings 2)
python match_intelligence/pipeline/export_cricsheet_innings.py \
    --cricsheet-id $MATCH_ID --innings <BattingTeam> \
    --out data/cricsheet/<dir>/<team>_innings.json

# 3. Save ESPN ball-by-ball page as PDF
# On espncricinfo.com → ball-by-ball tab for THIS innings → scroll TOP to
# BOTTOM so all 20 overs render → Cmd+P → Save as PDF → data/espncricinfo/

# 4. Parse the PDF
python match_intelligence/pipeline/parse_espn_pdf.py \
    --pdf "data/espncricinfo/<file>.pdf" \
    --out data/espncricinfo/<dir>/match_${MATCH_ID}_innings<n>_commentary.json \
    --match-id $MATCH_ID

# 5. (Optional) Process broadcast video chunks for speed + crease
# Only worth it for the ~3 "showcase" matches with bowling analysis.
# See archive/chunk_mode_pipeline/ for the legacy video path.

# 6. Synthesize the per-ball JSON (~$0.50, ~17 min)
python match_intelligence/pipeline/synthesize_match_json.py \
    --cricsheet-json data/cricsheet/<dir>/<team>_innings.json \
    --espn-commentary data/espncricinfo/<dir>/match_${MATCH_ID}_innings<n>_commentary.json \
    --gemini-video-glob 'data/NONEXISTENT_chunk*.json' \
    --out data/${LABEL}_innings<n>_full.json \
    --resume-dir data/${LABEL}_innings<n>_synthesized \
    --model gemini-2.5-pro

# 7. Load to DB (use --skip-wipe for the second innings of the same match)
python scripts/load_synth_to_db.py \
    --input data/${LABEL}_innings<n>_full.json \
    --match-id $MATCH_ID --team-a <A> --team-b <B> --format T20

# 8. Generate per-bowler + per-batter reports
python match_intelligence/reports/bowler_report.py \
    --match-id $MATCH_ID --innings <n> \
    --out data/bowler_analysis/match_${MATCH_ID}_innings_<n>.json

python match_intelligence/reports/batsman_report.py \
    --match-id $MATCH_ID --innings <n> \
    --out data/batsman_analysis/match_${MATCH_ID}_innings_<n>.json

# 9. Generate heatmaps + wagon wheels
python match_intelligence/reports/generate_heatmaps.py \
    --match-id $MATCH_ID --innings <n> \
    --out-dir data/heatmaps/match_${MATCH_ID}_innings_<n>

# 10. Browse in Streamlit UI
streamlit run ui/app.py
```

## Project layout

```
cricket-intelligence/
├── README.md                  ← this file
├── CLAUDE.md                  ← context for Claude Code sessions
│
├── src/                       ← SHARED infrastructure (used by both products)
│   ├── intelligence/schema.py    ← Pydantic + Gemini schemas
│   ├── analytics/                ← heatmap + wagon wheel + weakness renderers
│   ├── storage/db.py             ← SQLAlchemy DB layer
│   └── validation/, api/         ← shared validators + REST API
│
├── match_intelligence/        ← PRODUCT 1: T20/ODI broadcast analytics
│   ├── lib/                      ← cricsheet, espn_commentary, synthesis_prompt, extractor
│   ├── pipeline/                 ← synthesize_match_json.py (the active pipeline)
│   └── reports/                  ← batsman_report, bowler_report, generate_heatmaps
│
├── ai_coach/                  ← PRODUCT 2: Student critique + briefing + pose
│   ├── lib/                      ← coaching, critique, few-shot, briefing libs
│   ├── briefing/                 ← AI Coach PDF briefing CLI
│   ├── pipeline/                 ← critiques + coaching_corpus pipelines
│   ├── pose/                     ← pose render CLI
│   ├── rendering/                ← side-by-side video compare
│   └── report/                   ← PDF / TTS / video mux
│
├── scripts/                   ← shared ops (load_synth_to_db, db_migrations)
├── ui/app.py                  ← Streamlit UI (serves both products)
├── data/                      ← match data + DB (large files .gitignored)
├── docs/                      ← architecture, schema, heatmaps explainer
├── tests/                     ← pytest
└── archive/                   ← retired pipelines (chunk_mode_pipeline)
```

**Separation contract:** `match_intelligence/` never imports from `ai_coach/`. Both freely use `src/`. Coach may optionally import from Match (currently doesn't).

For deeper docs:
- [`docs/architecture.md`](docs/architecture.md) — system design, data flow, moat analysis
- [`docs/schema.md`](docs/schema.md) — DB schema + field provenance
- [`docs/heatmaps_explained.md`](docs/heatmaps_explained.md) — when to use frequency vs danger heatmap
- [`docs/project_context.md`](docs/project_context.md) — rolling session log (current DB state)
- [`CLAUDE.md`](CLAUDE.md) — context for AI-assisted development

## Status

| | |
|---|---|
| Current DB | 4 matches, 5 innings, 290 ball rows (1 fully-processed T20I + 3 legacy entries) |
| Active pipeline | Text-only synthesis (Cricsheet + ESPN + optional video) |
| Next milestone | Scale to 8-match T20I corpus to unlock multi-match weakness analytics |

## Documentation discipline

This repo follows a **single-source-of-truth** convention:

- **README.md** (this file) is the entry point. If you read nothing else, read this.
- **CLAUDE.md** is for AI agents only — different audience, kept in sync with this file.
- **docs/** holds *specific* deep dives. Each doc has one clear purpose; no overlap with this README.
- **archive/** holds retired code and old docs. Nothing in `archive/` is on any active code path.

If you're updating the system and tempted to write a new top-level `.md`, ask first whether the content belongs in this README, an existing `docs/` file, or `archive/` (if it's about something deprecated).
