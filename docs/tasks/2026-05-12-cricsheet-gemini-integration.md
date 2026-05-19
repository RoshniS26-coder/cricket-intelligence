# Cricsheet ↔ Gemini Integration

**Status:** Designed, not yet built. Foundation pieces (Cricsheet loader,
DB import, eval harness, India-innings export) are in place.
**Owner:** TBD
**Target:** First runnable `--cricsheet-json` extraction on chunk_001 within ~2 hours of build effort.

## Why this exists

Seven Gemini-only experiments on the Trent Bridge IND vs ENG video showed
a hard ceiling: ~67-69% accuracy on bowler / batsman / outcome, with
significant cost ($1-7/match) and reliability issues on long clips
(network drops, JSON truncation). See
[`2026-05-11-paddle-ocr-scoreboard-timeline.md`](2026-05-11-paddle-ocr-scoreboard-timeline.md)
for the full benchmarking narrative.

Cricsheet (https://cricsheet.org) ships per-match JSONs covering ~all
international T20s with **100% accuracy** on:
- `over`, `ball_number`, `innings`
- `bowler_name`, `batsman_name`, `non_striker`
- `runs.batter`, `runs.total`, `runs.extras` + extras breakdown
- `wickets[]` (kind, player_out, fielders)

Cricsheet **does not** have the technique fields the analytics layer
needs (`shot_type`, `line`, `length`, `footwork`, `contact_quality`,
`swing_direction`, `bowler_crease`, `bowling_speed_kmph`, `edge_type`).
That's exactly the gap a vision model is well-suited for.

The integration plan: **let Cricsheet do WHO/WHAT/RUNS at 100%, let Gemini
do HOW (technique) on a constrained per-ball task.**

## What is currently NOT integrated

There is **no Gemini call today that receives Cricsheet data as context**.
The existing `cricsheet.py` loader and `eval_against_cricsheet.py` are
read-only utilities — they let you score Gemini outputs against truth,
but they do not feed truth INTO Gemini.

## Two integration patterns

### Pattern A — Chunk-level context injection (quick win, ~2 hours to build)

For each 10-min video chunk: pull the relevant subset of Cricsheet balls
for that time window, embed in the Gemini prompt as ground-truth context,
ask Gemini to fill technique fields per ball.

```
┌──────────────────────────────────────────────────────────────────┐
│ INPUTS                                                            │
│  ┌────────────────────────┐    ┌────────────────────────────┐    │
│  │ chunk_001.mp4 (10 min) │    │ india_innings.json         │    │
│  │ video bytes            │    │ 128 balls (ground truth)   │    │
│  └───────────┬────────────┘    └────────────┬───────────────┘    │
│              │                               │                    │
│              │             ┌─────────────────┘                    │
│              ▼             ▼                                       │
│  ┌────────────────────────────────────────┐                        │
│  │ Filter: balls covered by this chunk    │                        │
│  │ (over-range param OR heuristic from    │                        │
│  │  chunk index × overs-per-chunk)        │                        │
│  └────────────┬───────────────────────────┘                        │
│               │ ~13 balls of context                               │
│               ▼                                                     │
│  ┌────────────────────────────────────────────────────────┐        │
│  │ TECHNIQUE_ONLY_PROMPT.format(                          │        │
│  │   cricsheet_context = JSON of those 13 balls,          │        │
│  │ )                                                       │        │
│  │                                                         │        │
│  │ Prompt tells Gemini:                                    │        │
│  │  - "Here are 13 deliveries that happened in this clip" │        │
│  │  - "DO NOT change over, ball_number, bowler, batter,   │        │
│  │     runs, outcome, dismissal_type — use as given"      │        │
│  │  - "Fill ONLY: shot_type, line, length, footwork,      │        │
│  │     contact_quality, swing_direction, bowler_crease,   │        │
│  │     edge_type, bowling_speed_kmph"                     │        │
│  │  - "Output the same 13 balls in the same order, each   │        │
│  │     with technique fields filled in"                   │        │
│  └────────────┬───────────────────────────────────────────┘        │
│               │ Gemini call (3.1-pro-preview, ~$0.40)              │
│               ▼                                                     │
│  ┌────────────────────────────────────────────────────────┐        │
│  │ Output: 13 records keyed by Cricsheet ball_id,         │        │
│  │ technique fields populated, WHO/WHAT/RUNS untouched    │        │
│  └────────────┬───────────────────────────────────────────┘        │
└───────────────┼─────────────────────────────────────────────────────┘
                ▼
        UPDATE balls SET shot_type=?, line=?, length=?, ...
        WHERE ball_id = '<cricsheet_id>_i2_0_1'
```

**Pros:**
- Works with existing 10-min chunk pipeline (no new alignment needed)
- One Gemini call per chunk = ~13 chunks for a full innings = ~$5
- Drops cognitive load: model isn't reading scoreboards or counting balls
- Testable on chunk_001 today

**Cons:**
- Wastes context on the broadcast video that Gemini doesn't strictly need
  (could trim to per-ball clips later)
- Heuristic mapping of "chunk index → over range" is approximate;
  needs manual `--over-range` flag for now
- Gemini may still hallucinate technique fields with low confidence;
  need confidence-gate before DB write

### Pattern B — Per-ball clip + technique-only call (production pipeline, ~1-2 days)

Once alignment is solved (audio bat-on-ball peaks, Whisper, or
Gemini-for-timestamps-only), each Cricsheet ball maps to a video
`(start_sec, end_sec)`. Then:

```
For each Cricsheet ball:
  1. ffmpeg-cut a 6-8 second clip from the broadcast video
  2. Send clip + 1 ball of context to Gemini:
       {bowler: "DJ Willey", batter: "RG Sharma",
        runs_total: 1, dismissal_type: "none"}
  3. Gemini returns ONLY technique fields
  4. UPDATE balls SET ... WHERE ball_id = ?
```

**Pros:**
- Tiny per-ball Gemini calls (6-8 sec video each = ~$0.003/ball, $0.40/match total)
- Resilient to network drops (one bad ball = $0.003 lost, not $5)
- Cleanest data: each call has perfectly-scoped context
- Gemini's task becomes trivial: describe ONE delivery's technique

**Cons:**
- Requires alignment first (not yet built)
- 120 sequential Gemini calls per innings (parallelizable but rate limited)

### Recommendation: build Pattern A first

Pattern A validates the technique-only prompt design without committing to
the alignment work. If accuracy on technique fields clears 90%+ in
Pattern A, the same prompt drops directly into Pattern B's per-ball
loop. If it fails, we learn that technique extraction from broadcast
video is harder than expected — *before* spending days on alignment.

## Data flow (Pattern A)

```mermaid
sequenceDiagram
    participant CLI as run_extract_with_cricsheet.sh
    participant Py as extract_balls_with_cricsheet.py
    participant Cricsheet as india_innings.json
    participant Prompt as TECHNIQUE_ONLY_PROMPT
    participant Gemini
    participant DB as SQLite balls table

    CLI->>Py: --video chunk_001.mp4 --cricsheet-json ... --over-range 0-2
    Py->>Cricsheet: load + filter balls in over range
    Cricsheet-->>Py: 13 ball dicts (bowler/batter/runs/outcome/dismissal)
    Py->>Prompt: format with cricsheet_context JSON
    Py->>Gemini: upload video + send formatted prompt
    Note over Gemini: Gemini sees ground-truth balls in prompt<br/>+ video bytes;<br/>fills only technique fields
    Gemini-->>Py: 13 records with technique fields populated
    Py->>Py: validate output count matches input count
    Py->>DB: UPDATE balls SET shot_type=...,line=... WHERE ball_id IN (...)
    DB-->>CLI: rows updated count
```

## Prompt design — technique-only

The new prompt (`src/intelligence/prompt_technique_only.py`, to be created)
inverts the current prompt's responsibilities. Today's `BATCH_EXTRACTION_PROMPT`
is 318 lines, of which ~200 are about reading scoreboards and counting
balls. All of that disappears.

Skeleton:

```text
You are a cricket video analyst. You will be shown:
  1. A video of a T20 broadcast segment
  2. A list of <N> ball deliveries that happened in this segment,
     with bowler, batter, runs, and dismissal already known.

Your task: for each ball in the list, fill in the TECHNIQUE fields
by observing the video. DO NOT modify any field that was given to you.

GROUND-TRUTH BALLS (in chronological order):
{cricsheet_context}

For each ball, return a JSON object with:
  - ball_id: the same ball_id from the input
  - over, ball_number, bowler_name, batsman_name, runs_scored, outcome,
    dismissal_type: COPY VERBATIM from the input
  - shot_type: cover_drive | pull | sweep | flick | drive | leave | ...
  - footwork: front_foot | back_foot | unknown
  - contact_quality: clean | edge | miss | pad | unknown
  - line: outside_off | off_stump | middle | leg_stump | wide_outside_off | ...
  - length: yorker | full | good | short | bouncer | unknown
  - swing_direction: in_swing | out_swing | none | unknown
  - bowler_crease: over_the_wicket | round_the_wicket | unknown
  - edge_type: inside | outside | top | bottom | none
  - bowling_speed_kmph: integer if scoreboard shows it, else null
  - batsman_handedness: left | right
  - confidence: per-field 0.0-1.0

Rules:
  - Output EXACTLY <N> records, in the same order as the input.
  - If you cannot observe a field for a particular ball (e.g. the
    broadcast cuts to a replay), set it to "unknown" with confidence < 0.5.
  - Do NOT invent technique details — better unknown than wrong.
```

Estimated prompt length: 50-80 lines (vs current 318). The
`{cricsheet_context}` block contributes ~30-50 lines per chunk for 13 balls.

### Commentary-audio signal (DECISION: include)

The technique-only prompt should explicitly instruct Gemini to use
broadcast commentary as a secondary signal for the technique fields.
Commentators consistently verbalize shot_type, footwork, length, line,
contact_quality, and speed — exactly the fields Gemini still has to
extract. Because Cricsheet anchors WHO/WHAT/RUNS, the historical risks
of relying on commentary (lag, replay re-discussion, ball mis-attribution)
are largely eliminated — commentary can no longer corrupt over/ball/batter
attribution.

Add this block after the field schema in the prompt:

```text
COMMENTARY AUDIO — secondary technique signal:

The broadcast audio contains live commentary describing each delivery.
Use it to corroborate or refine your visual reading of the technique
fields. Commentators almost always verbalize:
  - shot_type: "cover drive", "pulled away", "swept", "defended", "leave"
  - footwork: "front foot", "back and across", "down the track"
  - length:   "good length", "back of a length", "short ball", "yorker"
  - line:     "outside off", "on the pads", "wide of off-stump"
  - contact:  "middled", "edged", "thick edge", "missed", "padded away"
  - speed:    "144 ks", "87 mph" (cite only when broadcast shows the gun)

Two cautions:
  - Commentary LAGS the visual by 1-3 seconds. Match each comment to
    the ball it describes by checking what just happened on screen.
  - Commentary on REPLAYS may be re-discussed (the commentator says
    "watch this again" before describing the same ball). Use the
    Cricsheet ball_id list as the source of truth for which ball is
    which — do not emit a record from a replay-discussion segment.
```

## What needs to be built

Numbered for clarity. Steps 1-4 are Pattern A (quick win), 5-7 are Pattern B (production).

| # | Component | File | Effort |
|---|---|---|---|
| 1 | Technique-only prompt template | `src/intelligence/prompt_technique_only.py` | 1 hour |
| 2 | Filter helper: which Cricsheet balls fall in a chunk's over range | `src/intelligence/cricsheet.py::balls_in_range()` | 15 min |
| 3 | Pattern-A extractor CLI | `features/ball_extraction/extract_with_cricsheet.py` | 1 hour |
| 4 | Recipe shell + DB UPDATE logic | `run_extract_with_cricsheet.sh` + `src/storage/db.py::update_technique()` | 30 min |
| 5 | Alignment: video-time → Cricsheet-ball mapping (audio peaks first) | `src/intelligence/audio_alignment.py` | 1 day |
| 6 | Per-ball clip cutter (use the alignment) | `features/ball_extraction/cut_per_ball.py` | 2 hours |
| 7 | Pattern-B per-ball loop (uses #1's prompt with N=1) | `features/ball_extraction/extract_per_ball.py` | 2 hours |

## Acceptance criteria

Pattern A on chunk_001 should produce:
- 13 records, each with `ball_id` matching one of Cricsheet's first 13 India-innings balls
- All non-technique fields byte-identical to the Cricsheet input
- All technique fields populated (or `unknown` with low confidence — no nulls)
- After DB UPDATE, `SELECT * FROM balls WHERE match_id = 'T20-IndvsEng-IndBat' AND innings = 2 AND over <= 2` shows technique fields filled in alongside the existing Cricsheet WHO/WHAT/RUNS

## Open questions before building

1. **How is the chunk → over range mapping done?** Manual `--over-range`
   flag is fine for the first run. Long-term, this needs to be derived
   from the alignment work (Pattern B prerequisite). For chunk_001 we
   know empirically it covers overs 0-2 (13 balls).
2. **Should Gemini get the WHOLE innings as context or just the relevant
   subset?** Subset is cleaner and cheaper. Whole innings means Gemini
   could self-locate within the timeline (might help, might confuse).
   Start with subset; A/B if needed.
3. **DB UPDATE strategy on partial failure.** If Gemini returns 12 records
   instead of 13, do we (a) reject the whole batch, (b) update the 12 that
   came back, (c) update only those above a confidence threshold? Recommend
   option (b) with logging.
4. **Source-tagging in `raw_description`.** Cricsheet rows currently
   start `[cricsheet]`. After Gemini technique-fill, the row is a hybrid.
   Suggested convention: `[cricsheet+gemini-tech]` to make provenance
   queryable.

## Out of scope for this task

- Audio alignment (separate task — needed for Pattern B)
- Replacing the existing `extract_balls_from_clips.py` flow (this is a
  parallel pipeline; the old flow stays for non-Cricsheet matches)
- UI integration (existing UI reads from DB and works as-is once technique
  fields are populated)
- Cross-match generalization (this task is scoped to validating the
  pattern on the IND vs ENG match; multi-match support comes after)
