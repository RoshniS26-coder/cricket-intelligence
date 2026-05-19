# Architecture

Deep technical reference for the Cricket Intelligence pipeline. For a quick overview, install instructions, and the "add a match" recipe, see the [root README](../README.md).

---

## Table of contents

1. [Product positioning](#product-positioning)
2. [The competitive moat](#the-competitive-moat)
3. [System layers](#system-layers)
4. [Pipeline data flow](#pipeline-data-flow)
5. [Three data sources, one synthesized record](#three-data-sources-one-synthesized-record)
6. [Synthesis prompt design](#synthesis-prompt-design)
7. [Storage layer](#storage-layer)
8. [Analytics layer](#analytics-layer)
9. [Resilience: checkpointing + resume](#resilience-checkpointing--resume)
10. [Cost model](#cost-model)
11. [Scaling: from 1 match to N matches](#scaling-from-1-match-to-n-matches)

---

## Product positioning

**One sentence:** a structured, queryable layer on top of public cricket data, designed for opposition prep and weakness analysis at the ball-by-ball level.

**Who it's for:** T20 franchise coaching staffs, performance analysts, and scouting teams who need to answer questions like *"how does Pant score against round-the-wicket left-arm pace at 135+ kph in the death overs?"* — questions that ESPN's prose-based commentary and Cricsheet's outcome-only records cannot answer in queryable form.

**What it's not:** a real-time match-tracking system, a video-only computer vision pipeline, or a coaching-feedback product for individual players.

---

## The competitive moat

| Layer | This project | ESPN | Cricsheet | CricViz / Hawkeye |
|---|---|---|---|---|
| Ball-by-ball outcome (runs / wicket / who) | ✅ | ✅ | ✅ | ✅ |
| Line / length / shot type (structured) | ✅ | prose only | ❌ | ✅ (walled garden) |
| Footwork / contact quality (structured) | ✅ | prose only | ❌ | ✅ (walled garden) |
| Bowling speed per ball | ✅ (via video) | ❌ | ❌ | ✅ (walled garden) |
| Bowler crease per ball | ✅ (via video) | ❌ | ❌ | ✅ (walled garden) |
| Multi-match queryable DB | ✅ (when scaled) | ❌ | ✅ raw only | ✅ (walled garden) |
| Per-batter scouting reports | ✅ | ❌ | ❌ | ✅ (walled garden) |
| **Public-data, queryable, multi-source synthesis** | **✅** | ❌ | ❌ | ❌ |

The differentiation lives in the last row. CricViz has more data per ball (Hawkeye tracking), but it's only accessible to broadcaster partners. This project rebuilds an analytically-equivalent dataset entirely from **public sources** that a franchise can ingest without licensing deals.

---

## System layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  USER-FACING                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Streamlit UI │  │ Markdown     │  │ CSV / JSON exports       │   │
│  │ (ui/app.py)  │  │ reports      │  │                          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│  ANALYTICS                                                          │
│  • Per-bowler reports       (features/bowler_analysis/)             │
│  • Per-batsman reports      (features/batsman_analysis/)            │
│  • Pitch maps + wagon wheels (features/heatmap/, src/analytics/)    │
│  • Weakness aggregation     (src/analytics/weakness.py)             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│  STORAGE                                                            │
│  SQLite (data/cricket_intelligence.db)                              │
│   • matches table — match metadata                                  │
│   • balls table   — 28 fields per delivery, innings-qualified PK    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│  SYNTHESIS                                                          │
│  features/ball_extraction/synthesize_match_json.py                  │
│   + src/intelligence/prompt_synthesis.py                            │
│   + gemini-2.5-pro (per over)                                       │
│   → checkpointed per-over JSON → merged full-match JSON             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│  DATA SOURCES                                                       │
│  Cricsheet JSON  +  ESPN PDF commentary  +  (opt) Gemini video      │
│  (who/what/runs)    (technique)                  (speed/crease)     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline data flow

```
┌─────────────────┐
│ cricsheet.org   │──────► data/cricsheet/<match>/
└─────────────────┘
                          │
                          ▼
                  features/ball_extraction/
                  export_cricsheet_innings.py
                          │
                          ▼ <team>_innings.json (per innings)

┌─────────────────┐       │
│ ESPNCricinfo    │──PDF─►│ features/audio_pipeline/parse_espn_pdf.py
└─────────────────┘       │
                          ▼ match_<id>_innings<n>_commentary.json

┌─────────────────┐       │
│ broadcast .mp4  │──────►│ (optional, legacy: archive/chunk_mode_pipeline/)
└─────────────────┘       │
                          ▼ IndvsEng_chunk*_with_cricsheet.json

                          │
                          ▼
                  features/ball_extraction/
                  synthesize_match_json.py
                      │
                      │  for each over:
                      │    1. Build bundle (cricsheet + espn + optional video)
                      │    2. Render synthesis prompt
                      │    3. Call gemini-2.5-pro
                      │    4. Validate against Pydantic schema
                      │    5. Write resume checkpoint over_NN.json
                      │
                      ▼ <label>_innings<n>_full_match_correct.json

                          │
                          ▼
                  scripts/load_synth_to_db.py
                  (wipe + insert, or --skip-wipe)
                          │
                          ▼
                  SQLite balls + matches tables
                          │
                          ▼
                  Analytics + UI
```

---

## Three data sources, one synthesized record

Each output ball record is the **synthesis** of up to three input records. Each source has a different role; the prompt enforces precedence so no source can override another's primary fields.

| Field group | Primary source | Why |
|---|---|---|
| `match_id`, `innings`, `over_number`, `ball_number` | Cricsheet | Authoritative ball identity |
| `bowler_name`, `batsman_name` | Cricsheet | Authoritative WHO |
| `runs_scored`, `outcome`, `dismissal_type`, `dismissal_fielder` | Cricsheet | Authoritative WHAT happened |
| `line`, `length`, `shot_type`, `footwork`, `contact_quality`, `shot_direction`, `edge_type` | ESPN commentary | Analyst-described technique |
| `bowler_type`, `variation`, `movement`, `swing_direction`, `swing_type`, `spin_direction`, `ball_age_phase` | ESPN commentary + Cricsheet inference | Technique + format inference |
| **`bowling_speed_kmph`**, **`bowler_crease`** | Gemini-on-video only | Visible only in broadcast |
| `phase`, `batsman_handedness` | Derived (over_number, Cricsheet) | Computed |
| `raw_description` | All three concatenated | Audit trail |

**Precedence rule:** *Cricsheet WHO/WHAT/RUNS > ESPN technique > Gemini video for visual-only fields.* The prompt explicitly forbids the model from overriding Cricsheet outcomes with ESPN prose, even if the ESPN commentary describes the ball differently (e.g., ESPN might call a misfield "lucky four" that Cricsheet records as a `1`).

---

## Synthesis prompt design

Lives in [`src/intelligence/prompt_synthesis.py`](../src/intelligence/prompt_synthesis.py).

Key design decisions:

1. **Per-over batching**, not per-ball or per-innings. Each Gemini call gets one over's worth of input (6-8 balls) — small enough for the model to handle precisely, large enough to amortize the prompt overhead.

2. **Structured bundle input.** The prompt is rendered from a Python dict `{cricsheet: [...], espn: [...], video: [...]}` so the model sees parallel arrays it can index by ball number.

3. **Shot-type mapping table** baked into the prompt. ESPN uses prose ("drove uppishly through cover") which the model maps to one of ~25 enum values (`cover_drive`, `lofted`, etc.). The mapping table is in the prompt itself for transparency.

4. **No ground-truth contamination.** The prompt never contains "expected outputs" for the specific match being processed. (Earlier prompt iterations leaked test-set examples — see `archive/data/chunk_prompt_experiments/` for the failed v2/v3 attempts.)

5. **Structured output via Gemini JSON schema.** The model returns valid JSON conforming to `src/intelligence/schema.py:BallRecord` directly — no string parsing.

---

## Storage layer

Two tables in `data/cricket_intelligence.db` (full reference in [`schema.md`](schema.md)):

```sql
CREATE TABLE matches (
  match_id   TEXT PRIMARY KEY,
  format     TEXT,
  team_a     TEXT,
  team_b     TEXT,
  venue      TEXT,
  date       DATE
);

CREATE TABLE balls (
  ball_id    TEXT PRIMARY KEY,        -- '{match_id}_i{innings}_{over}_{ball}'
  match_id   TEXT REFERENCES matches(match_id),
  innings    INTEGER,
  over_number INTEGER,
  ball_number INTEGER,
  bowler_name TEXT, batsman_name TEXT,
  -- 23 technique fields:
  line, length, shot_type, contact_quality, footwork,
  bowler_type, variation, movement, swing_direction, swing_type,
  spin_direction, bowler_crease, bowling_speed_kmph,
  ball_age_phase, shot_direction, dismissal_type, dismissal_fielder,
  batsman_handedness, phase, edge_type, runs_scored,
  raw_description, outcome,
  -- meta:
  is_reviewed BOOLEAN,
  created_at, updated_at
);
```

**Innings-qualified `ball_id`** prevents the collision that earlier non-innings IDs caused (innings 1's over 0 ball 1 had the same PK as innings 2's over 0 ball 1, silently dropping one of them on insert).

---

## Analytics layer

Three independent renderers, each operating directly on the SQLite DB so they can be regenerated any time:

| Module | Output | Used by |
|---|---|---|
| `src/analytics/heatmaps.py` | Pitch map (5×5 line×length), wagon wheel (8-zone polar) | `features/heatmap/generate_heatmaps.py` |
| `src/analytics/weakness.py` | Per-batter weighted weakness score per (line, length) cell | `features/batsman_analysis/analyse_batsman_weakness.py`, Streamlit UI |
| `src/analytics/pitch_map.py` | Danger-aware heatmap (older, weakness-specific renderer) | Streamlit UI |

See [`heatmaps_explained.md`](heatmaps_explained.md) for when to use which.

Per-bowler and per-batsman reports are pure SQL aggregations plus markdown templating ([`features/bowler_analysis/bowler_report.py`](../features/bowler_analysis/bowler_report.py), [`features/batsman_analysis/batsman_report.py`](../features/batsman_analysis/batsman_report.py)).

---

## Resilience: checkpointing + resume

Synthesis takes ~17 minutes per innings — long enough that a network blip or rate-limit hit is statistically likely. The pipeline mitigates this with **per-over checkpoints**:

```
data/IndvsEng_innings1_synthesized/
├── over_00.json    ← written after over 0's Gemini call returns
├── over_01.json
├── ...
└── over_19.json
```

`synthesize_match_json.py` checks the resume dir on start and skips overs that already have a checkpoint file. A crashed run can be resumed losslessly by re-running the same command — only the missing overs get re-called.

---

## Cost model

| Per match (text-only) | Per match (+ video) |
|---|---|
| **~$0.50** Gemini API per innings | + **~$5-6** for video chunks per innings |
| **~17 min** wall time per innings | + **2-3 hrs** wall time per innings |
| Coverage: 23/28 fields well-populated | + speed + crease coverage |

**Decision rule:** add video only when the deliverable explicitly needs bowling speed or crease analysis (e.g., showcase matches for franchise pitch). For pure batter scouting at scale, text-only gives 95% of the analytical value at 1/10th the cost.

---

## Scaling: from 1 match to N matches

The structural value compounds non-linearly with match count:

| Matches | What it unlocks |
|---|---|
| 1 | Descriptive analytics for that game (what happened) |
| 3-5 | Initial matchup patterns (Bowler X vs Batter Y across 3 innings) |
| **8-10** | **Statistically usable pitch maps + wagon wheels for top 6 batters of each side** |
| 15-20 | Weakness heatmaps cross statistical significance threshold for top order |
| 30+ | Per-bowler-type splits become reliable; phase-specific patterns emerge |

**For format-mixing:** don't. T20 and ODI batter behavior diverges enough that combining them in one heatmap is misleading. Pick one format and stay in it; 8 T20s ≈ 5 ODIs in terms of per-batter ball count.

For the per-format scaling math, see the [main README](../README.md#status).

---

## Retired pipelines

The following lived in `src/intelligence/` and `features/ball_extraction/` until 2026-05-09, then moved to `archive/chunk_mode_pipeline/`:

| Pipeline | Why retired |
|---|---|
| **Chunk-mode video extraction** (`prompt.py` + `extract_balls_from_clips.py`) | Each 5-min chunk's extractor de-duplicated only locally, causing ~30 ball_id collisions per match and ~50% row loss on DB save. |
| **Chunk-mode v2 with Cricsheet join** (`prompt_technique_only.py` + `extract_with_cricsheet.py`) | Improved over v1 but still produced 60ms bogus clips and inherited the collision problem. |

The current synthesis pipeline takes the per-chunk video JSONs from chunk-mode v2 as *optional input* (for the speed + crease fields), but the chunk-mode extractors themselves are no longer invoked.

See [`archive/README.md`](../archive/README.md) for the full file-by-file inventory.
