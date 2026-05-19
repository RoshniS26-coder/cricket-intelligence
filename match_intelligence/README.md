# Match Intelligence

T20/ODI broadcast match → structured ball-by-ball dataset → per-batter/per-bowler scouting reports + pitch maps + wagon wheels. One of the two products in this repo (the other is [`ai_coach/`](../ai_coach/)).

## What it produces

For any match in the corpus:

| Artifact | What it is |
|---|---|
| **Per-ball table** | ~240 rows × 28 fields. Line, length, shot type, footwork, contact, outcome, dismissal, plus optional bowling speed + crease |
| **Per-batsman scouting card** | Balls faced, SR, shot distribution, scoring zones, per-bowler matchups, phase splits, dismissal pattern |
| **Per-bowler scouting card** | Balls bowled, economy, dot %, length distribution, per-batter matchups, dismissals taken |
| **Pitch map** | 5×5 line × length frequency heatmap |
| **Wagon wheel** | 8-zone polar scoring chart, auto-mirrored for LHB |
| **Weakness heatmap** | Per-cell danger score, highlighting exploitable zones |

## Layout

```
match_intelligence/
├── README.md                   ← this file
│
├── lib/                        ← internal libraries
│   ├── cricsheet.py            ← Cricsheet JSON loader + innings/ball helpers
│   ├── espn_commentary.py      ← parse ESPN JSON → join to Cricsheet ball_ids
│   ├── synthesis_prompt.py     ← ⭐ ACTIVE — text-only synthesis prompt (gemini-2.5-pro)
│   ├── extractor.py            ← Gemini-on-video extractor (used for video chunks)
│   ├── weakness_narrator.py    ← bilingual narrative on weakness profiles
│   └── commentary.py
│
├── pipeline/                   ← data ingestion CLIs
│   ├── export_cricsheet_innings.py ← cricsheet → per-innings JSON
│   ├── import_cricsheet.py         ← bulk cricsheet import
│   ├── parse_espn_pdf.py           ← ESPN PDF → structured commentary JSON
│   ├── synthesize_match_json.py    ← ⭐ THE pipeline entrypoint
│   └── transcribe.py               ← optional Whisper audio transcription
│
└── reports/                    ← analysis CLIs
    ├── batsman_report.py       ← per-batter stats + matchups + markdown/JSON
    ├── bowler_report.py        ← per-bowler stats + matchups + markdown/JSON
    ├── generate_heatmaps.py    ← bulk pitch maps + wagon wheels for all players
    ├── analyse_batsman_weakness.py ← danger-map + bilingual narrative for one batter
    └── run_weakness.sh
```

## The 10-step recipe (add a new match)

```bash
MATCH_ID=<cricsheet_id>          # e.g. 1276906
LABEL=<readable_label>           # e.g. IndvsEng_2024_T20I_1

# 1. Download Cricsheet JSON manually from cricsheet.org
#    → data/cricsheet/<match_dir>/

# 2. Export one innings (repeat for innings 2)
python match_intelligence/pipeline/export_cricsheet_innings.py \
    --cricsheet-id $MATCH_ID --innings <BattingTeam> \
    --out data/cricsheet/<dir>/<team>_innings.json

# 3. Save ESPN ball-by-ball page as PDF
#    espncricinfo.com → ball-by-ball tab → scroll TOP to BOTTOM
#    → Cmd+P → Save as PDF → data/espncricinfo/

# 4. Parse the PDF
python match_intelligence/pipeline/parse_espn_pdf.py \
    --pdf "data/espncricinfo/<file>.pdf" \
    --out data/espncricinfo/<dir>/match_${MATCH_ID}_innings<n>_commentary.json \
    --match-id $MATCH_ID

# 5. (Optional) Process broadcast video chunks for speed + crease
#    Only worth it for showcase matches. ~$5 + 2-3 hrs per innings.
#    Legacy chunk-mode in archive/chunk_mode_pipeline/.

# 6. Synthesize per-ball JSON (~$0.50, ~17 min per innings)
python match_intelligence/pipeline/synthesize_match_json.py \
    --cricsheet-json data/cricsheet/<dir>/<team>_innings.json \
    --espn-commentary data/espncricinfo/<dir>/match_${MATCH_ID}_innings<n>_commentary.json \
    --gemini-video-glob 'data/NONEXISTENT_chunk*.json' \
    --out data/${LABEL}_innings<n>_full.json \
    --resume-dir data/${LABEL}_innings<n>_synthesized \
    --model gemini-2.5-pro

# 7. Load to DB (use --skip-wipe for second innings of same match)
python scripts/load_synth_to_db.py \
    --input data/${LABEL}_innings<n>_full.json \
    --match-id $MATCH_ID --team-a <A> --team-b <B> --format T20

# 8. Per-bowler + per-batter reports
python match_intelligence/reports/bowler_report.py \
    --match-id $MATCH_ID --innings <n> \
    --out data/bowler_analysis/match_${MATCH_ID}_innings_<n>.json

python match_intelligence/reports/batsman_report.py \
    --match-id $MATCH_ID --innings <n> \
    --out data/batsman_analysis/match_${MATCH_ID}_innings_<n>.json

# 9. Pitch maps + wagon wheels
python match_intelligence/reports/generate_heatmaps.py \
    --match-id $MATCH_ID --innings <n> \
    --out-dir data/heatmaps/match_${MATCH_ID}_innings_<n>

# 10. Browse in Streamlit UI (Weakness Analysis + Full Dataset)
streamlit run ui/app.py
```

## Three data sources, one synthesized record

| Field group | Source | Why |
|---|---|---|
| `match_id`, `innings`, `over_number`, `ball_number` | Cricsheet | Authoritative ball identity |
| `bowler_name`, `batsman_name`, `runs_scored`, `outcome`, `dismissal_*` | Cricsheet | Authoritative WHO and WHAT |
| `line`, `length`, `shot_type`, `footwork`, `contact_quality`, `shot_direction`, `edge_type` | ESPN commentary | Analyst-described technique |
| `bowler_type`, `variation`, `movement`, `swing_*`, `spin_*`, `ball_age_phase` | ESPN + Cricsheet inference | Technique + format inference |
| **`bowling_speed_kmph`**, **`bowler_crease`** | Gemini-on-video only | Visible only in broadcast |
| `phase`, `batsman_handedness` | Derived | Computed from over_number, Cricsheet |

**Precedence rule:** Cricsheet WHO/WHAT/RUNS > ESPN technique > Gemini video for visual-only fields.

## Cost per match

- **Text-only** (Cricsheet + ESPN): ~$0.50 + ~17 min per innings
- **+ video pass**: ~$5-6 + 2-3 hrs per innings. Worth it only when bowler-side speed/crease is the deliverable.

## Resilience

Synthesis is checkpointed per over to `data/<label>_synthesized/over_NN.json`. A crash mid-run resumes losslessly — re-run the same command and only the missing overs get re-called.

## Where the data lives

| Type | Path |
|---|---|
| Cricsheet match JSONs | `data/cricsheet/<match_dir>/` |
| ESPN PDFs + parsed JSON | `data/espncricinfo/` |
| Synthesized per-innings JSON | `data/<label>_innings<n>_full.json` |
| Per-over checkpoints | `data/<label>_innings<n>_synthesized/over_NN.json` |
| DB | `data/cricket_intelligence.db` |
| Generated reports (markdown + JSON) | `data/{batsman,bowler}_analysis/match_<id>_innings_<n>.*` |
| Generated heatmaps | `data/heatmaps/match_<id>_innings_<n>/` |

## Separation contract

- `match_intelligence/` **never** imports from `ai_coach/`
- `match_intelligence/` freely uses `src/` (shared schema, DB, analytics, validators)
- `ai_coach/` may optionally import from `match_intelligence/` (currently doesn't)

For the moat analysis (what this gives you vs. ESPN, Cricsheet, CricViz), see [`../docs/architecture.md`](../docs/architecture.md).
