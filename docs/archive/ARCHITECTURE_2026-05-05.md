# 🏏 Cricket Intelligence Engine — Architecture

> **Mindset:** Modularity · Longitudinal data · Coach-in-the-loop
> Product goal: *"An AI Analyst in a box for Indian cricket academies — upload match/net video, get per-player technique briefings, weakness reports, and narrated overlay videos."*

---

## Table of Contents

1. [Product Direction](#product-direction)
2. [System Layers](#system-layers)
3. [Phase 1 Status — What's Built](#phase-1-status)
4. [Directory Structure](#directory-structure)
5. [Data Flow End-to-End](#data-flow)
6. [Role Model (Batsman → Bowler → Keeper)](#role-model)
7. [Camera Setup Tiers](#camera-setup)
8. [Continuous Learning Flywheel](#flywheel)
9. [Success Metrics](#success-metrics)
10. [Non-Goals](#non-goals)

---

## 1. Product Direction {#product-direction}

The engine is being positioned as an **AI Analyst for premium Indian cricket academies** — not a broadcast tool, not a D2C consumer app.

| Decision | Rationale |
|---|---|
| **Buyer = private academy head coach / owner** | ₹25k–₹1L/year tooling budgets exist; fast 1–3 month sales cycle; single decision-maker. |
| **Not pro/franchise tier** | Hawk-Eye + CricViz + Dartfish already own it; hardware-gated, multi-year cycles. |
| **Not D2C** | Fulltrack AI owns that segment with 2M users and peer-reviewed validation. |
| **Moat = narrative + longitudinal + pose** | Competitors ship heatmaps; nobody ships LLM-written weakness briefings, pose-based technique trends over weeks, or coach-corrected India-specific datasets. |
| **Start with batsman** | Higher ball volume per session, parents demand it, side-on camera is the industry-standard angle. Bowler + keeper extend the same pose pipeline later. |

**One-line positioning:** replace a ₹8L/yr Dartfish + junior-analyst combination with a ₹50k/yr SaaS that ships overnight player briefings and shareable narrated clip reels.

---

## 2. System Layers {#system-layers}

The engine is a **six-layer stack**. Layers 1, 4 (weakness), 5, and 6 are built; layers 2–3 are the current roadmap.

```
Layer 6:  Delivery        — PDF report · narrated overlay video · WhatsApp share · dashboard  ✅
Layer 5:  Narrative       — LLM-generated weakness briefings + coaching cues                  ✅
Layer 4:  Analytics       — weakness cross-tabs, pitch map, danger zone scoring               ✅
Layer 3:  Technique       — MediaPipe pose → role-specific feature engineering
Layer 2:  Identity        — scoreboard OCR + roster + manual tag, linked to batsman_name/bowler_name
Layer 1:  Extraction      — Gemini + Roboflow CV → per-ball structured JSON                   ✅
```

### Batsman Weakness Analysis (Layer 4 + 5)

Queries `line`, `length`, `outcome`, `contact_quality` per ball from the DB and computes a **danger zone matrix**:

```
danger_score = (dismissal_rate × 0.6) + (false_shot_rate × 0.4)
```

Four-layer stack:

| Layer | File | What it does |
|---|---|---|
| Statistics | `src/analytics/weakness.py` | Line × length crosstab, danger scoring, bowler-type/variation breakdowns |
| LLM Narrative | `src/intelligence/weakness_narrator.py` | Gemini → bilingual {en, hi} summary, bowling plan, batting advice |
| Pitch Map | `src/analytics/pitch_map.py` | matplotlib bird's-eye danger heatmap PNG (no YOLO needed) |
| CLI | `scripts/analyse_batsman_weakness.py` | `--batsman`, `--narrative`, `--pitch-map`, `--output` |

API: `GET /analytics/weakness?batsman_name=Rohit+Sharma&narrative=true`

Streamlit: "Weakness Analysis" tab — zone grid, breakdown tabs, on-demand Gemini narrative.

| Layer | State | Owner modules |
|---|---|---|
| 1 Extraction | ✅ Built | `src/ingestion/`, `src/segmentation/`, `src/intelligence/`, `src/detection/`, `src/validation/`, `src/storage/` |
| 2 Identity | ❌ To build | `src/identity/` (scoreboard OCR, roster, review-UI tagging) |
| 3 Technique | ❌ To build | `src/pose/` (MediaPipe extractor + role-specific feature modules) |
| 4 Analytics | ❌ To build | `src/analytics/profile.py`, `src/analytics/benchmarks.py` |
| 5 Narrative | ❌ To build | `src/analytics/briefing.py` (Claude/Gemini prose, clip-linked) |
| 6 Delivery | ❌ To build | `src/report/pdf.py`, `src/report/video_renderer.py`, `src/report/tts.py`, `src/report/mux.py` |

**Key insight:** Layer 1 is **role-agnostic**. `BallRecord` already captures both bowler-side (`bowler_type`, `line`, `length`, `variation`, `movement`) and batsman-side (`shot_type`, `footwork`, `contact_quality`) fields. The only role-specific work lives in Layers 3–5 (pose features, briefing prompts, overlay labels).

---

## 3. Phase 1 Status — What's Built ✅ {#phase-1-status}

| Module | Status | File |
|---|---|---|
| Video ingestion (YouTube + local) | ✅ | `src/ingestion/downloader.py` |
| Ball segmentation — uniform | ✅ | `src/segmentation/clip_extractor.py` |
| Ball segmentation — timestamp-based | ✅ | Same file |
| Batch mode — Gemini auto-detects all deliveries | ✅ | `run_pipeline.py --batch-mode` |
| Gemini vision extraction (10+ fields + confidence) | ✅ | `src/intelligence/extractor.py` |
| Pydantic schema (single source of truth) | ✅ | `src/intelligence/schema.py` |
| Prompts (system, single, batch, CV-augmented) | ✅ | `src/intelligence/prompt.py` |
| Roboflow CV (DualModelDetector + geometric line/length) | ✅ | `src/detection/detect.py` |
| Ball trajectory (YOLO, 7–31% detection rate — weak) | ⚠ | `src/tracking/tracker.py` |
| Validation + normalization | ✅ | `src/validation/normalizer.py` |
| SQLite storage (matches + balls tables) | ✅ | `src/storage/db.py` |
| REST API (FastAPI) | ✅ | `src/api/main.py` |
| Review UI (Streamlit, 3 modes) | ✅ | `ui/app.py` |
| Custom YOLO training pipeline | ✅ Built, unused | `scripts/train_yolo.py` |
| Cric-360 validation | ✅ Built, unused | `scripts/validate_cric360.py` |

**Current DB state:** 32 balls across 8 matches. POC phase — needs to scale to 500+ reviewed balls before analytics layer is statistically meaningful.

---

## 4. Directory Structure {#directory-structure}

```
cricket-intelligence/
├── data/
│   ├── raw_videos/          # Downloaded match + net video + metadata JSON
│   ├── ball_clips/          # Per-ball clips (segmented mode)
│   ├── pose/                # [NEW] Per-clip pose JSON (33 MediaPipe keypoints × N frames)
│   ├── reports/             # [NEW] Generated PDFs, markdown briefings
│   ├── reports/videos/      # [NEW] Annotated + narrated clip output
│   ├── narration/           # [NEW] TTS .mp3 files for briefings
│   ├── rosters/             # [NEW] Per-academy player lineups (YAML/JSON)
│   └── cricket_intelligence.db  # SQLite (matches, balls, +pose_features, +ground_truth)
├── models/                  # Custom weights (YOLO, pose classifiers)
├── src/
│   ├── ingestion/           ✅ YouTube + local registration
│   ├── segmentation/        ✅ ffmpeg clip cutter
│   ├── detection/           ✅ Roboflow + YOLO (scene + geometry)
│   ├── tracking/            ⚠ Ball trajectory (park until perspective calibration)
│   ├── intelligence/        ✅ Gemini extraction + prompts + schema
│   ├── validation/          ✅ Schema normalization
│   ├── storage/             ✅ SQLAlchemy + SQLite
│   ├── api/                 ✅ FastAPI REST
│   ├── identity/            [NEW] scoreboard_ocr.py · roster.py · tagger.py
│   ├── pose/                [NEW] extractor.py · features/batsman.py · features/bowler.py · smoothing.py
│   ├── analytics/           [NEW] profile.py · benchmarks.py · briefing.py
│   └── report/              [NEW] pdf.py · video_renderer.py · tts.py · mux.py · subtitles.py
├── ui/                      ✅ Streamlit review (extends with tagging + briefing preview)
├── scripts/
│   ├── train_yolo.py        ✅ Future use
│   ├── validate_cric360.py  ✅ Future use
│   ├── analyze_player.py    [NEW] end-to-end player-level entry point
│   ├── render_player_video.py [NEW] annotated+narrated clip generator
│   └── calibrate_pose_thresholds.py [NEW] threshold calibration on pro reference clips
├── run_pipeline.py          ✅ Match-level orchestrator (extend with `--pose`, `--briefing` flags)
├── requirements.txt
├── ARCHITECTURE.md          This file
├── PLAN.md                  6-week execution plan
├── ENGINEERING.md           Module specs + interface contracts
├── DIAGRAMS.md
└── README.md
```

---

## 5. Data Flow End-to-End {#data-flow}

```
                 ┌──────────────────────────────────────────┐
                 │  YouTube URL | local .mp4 | pilot upload │
                 └────────────────┬─────────────────────────┘
                                  ▼
                       src/ingestion/downloader.py
                 → data/raw_videos/<match-id>.mp4 + _meta.json
                                  │
                 ┌────────────────┴──────────────────────┐
                 │                                       │
         BATCH MODE                              SEGMENTED MODE
  (upload whole video to Gemini)       (ffmpeg split → per-clip analysis)
                 │                                       │
                 │                                       ▼
                 │                    src/segmentation/clip_extractor.py
                 │                    → data/ball_clips/<match-id>/*.mp4
                 │                                       │
                 │                                       ▼
                 │                       src/detection/detect.py
                 │                       (optional — Roboflow CV geometry)
                 │                                       │
                 ▼                                       ▼
        src/intelligence/extractor.py ──────────────────┘
        → per-ball BallRecord (line, length, shot, outcome, + confidence)

                                  │
                                  ▼
   ┌──────────────────────────────┼─────────────────────────────────┐
   │                              │                                 │
   ▼                              ▼                                 ▼
[NEW] src/identity/       [NEW] src/pose/                 src/validation/
 scoreboard_ocr +          extractor.py → 33 keypoints     (existing)
 roster + tagger            per frame
 → batsman_name            src/pose/features/batsman.py
   bowler_name              → head_offset, stride,
   (reliable)                 shoulder_angle, etc.
   │                         │
   └───────────┬──────────────┘
               ▼
     src/storage/db.py
     (balls + pose_features + ground_truth tables)
               │
               ▼
       [NEW] src/analytics/profile.py
       → PlayerProfile (aggregated across matches)
       → Weakness cross-tabs
       → Peer benchmarking vs academy median
               │
               ▼
       [NEW] src/analytics/briefing.py
       (Claude/Gemini → 400-word narrative + clip timestamps)
               │
               ▼
   ┌───────────┴──────────┬─────────────────────────┐
   ▼                      ▼                         ▼
[NEW] src/report/    [NEW] src/report/        ui/app.py + src/api/main.py
 pdf.py              video_renderer.py +       (review + tagging + briefing preview)
 → A4 one-pager      tts.py + mux.py
                     → narrated MP4
                       with pose overlay
```

**Existing (Layer 1) arrows are unchanged.** New modules attach at specific joins and do not require schema breakage to the Pydantic `BallRecord`.

---

## 6. Role Model — Batsman → Bowler → Keeper {#role-model}

| Element | Batsman (v1) | Bowler (v2) | Keeper (v3) |
|---|---|---|---|
| Gemini fields used | `shot_type`, `footwork`, `contact_quality`, `outcome` | `bowler_type`, `line`, `length`, `variation`, `movement`, `bounce_behavior` | derived from scene detection |
| Pose features module | `pose/features/batsman.py` | `pose/features/bowler.py` | `pose/features/keeper.py` |
| Key metrics | head offset, stride length, shoulder angle, balance, backlift direction | run-up rhythm, front-foot landing, hip–shoulder separation, arm angle at release, follow-through balance | squat depth, hand position, head stability, lateral foot speed |
| Camera angle | side-on behind batsman (45°) | behind-bowler end OR side-on to run-up | behind stumps keeper-end |
| Briefing prompt variant | batsman-focused cues | delivery + injury-prevention cues | glove-work + head stability |

**v2 plan:** reuse `src/pose/extractor.py`, add `features/bowler.py` and a bowler briefing prompt. Gemini extraction is already role-agnostic — no Layer 1 changes needed.

---

## 7. Camera Setup Tiers {#camera-setup}

| Tier | Cameras | What works | Target customer |
|---|---|---|---|
| **A — MVP** | 1 phone, side-on at 45°, 3–5 m from crease, chest-height tripod | Batsman pose + ball metadata via Gemini | Every pilot academy |
| **B — Recommended** | + 1 behind-bowler phone | Adds bowler pose + tighter line/length + pitch landing view | Phase-2 academies |
| **C — Full kit** | + elevated 45° pitch-map camera | True pitch coordinates via homography | Future, state-assoc tier |

**Product ships a physical kit** (tripod + phone mount + SD card + placement guide) in Tier A. The kit doubles as an installation moat — switching cost increases as the recording setup becomes the academy's default.

Camera requirements for pose (Tier A minimum):
- 1080p, 30 fps minimum (60 fps preferred for impact-frame detection)
- Batsman occupies ≥ 40% of vertical frame height
- Landscape orientation, locked exposure
- Stable (tripod or rigid phone mount)

---

## 8. Continuous Learning Flywheel {#flywheel}

```
Gemini extracts ball  ──▶  MediaPipe pose  ──▶  Feature module (batsman)
                                                         │
                                                         ▼
                                       Per-ball record in SQLite
                                                         │
                                                         ▼
                          Low confidence? Unknowns? Fault flag?
                                                         │
                                           YES ──▶ Review UI
                                                         │
                                                         ▼
                                  Coach corrects field / confirms
                                                         │
                                                         ▼
                            ground_truth table logs the delta:
                            (ball_id, field, old_value, new_value,
                             coach_id, timestamp, pose_features_at_time)
                                                         │
                    ┌────────────────────────────────────┴─────────────────────┐
                    ▼                                                          ▼
  Short-term: prompt tuning / threshold               Long-term: fine-tune a compact
  recalibration based on correction patterns         India-cricket-tuned pose classifier
                                                      on ≥ 50k labels → drops Gemini cost
                                                      10× and builds a proprietary moat
```

Every correction in `ui/app.py` writes a row to `ground_truth` (new table). That table is the company's proprietary dataset. CricHeroes has manual-scored data; they do not have pose-corrected data. This is the asset.

**Design rules for the flywheel**:
1. Every field the coach can change in the UI is logged with `(old, new, context, who, when)`.
2. Corrections trigger a `retrain-candidate` flag on the ball — batched into weekly retraining runs later.
3. Review UI must make corrections **one-tap** wherever possible. Friction = fewer labels = weaker moat.

---

## 9. Success Metrics {#success-metrics}

### Phase 0 — 5-coach validation (before writing Phase 1 code)
| Metric | Target |
|---|---|
| Coaches who say report told them something new | ≥ 3 of 5 |
| Coaches who ask to share with a player/parent unprompted | ≥ 2 of 5 |
| Coaches who name a fair price ≥ ₹25k/yr | ≥ 2 of 5 |
| "Green" scorecards (≥ 4 of 5 signals hit) | ≥ 3 of 5 |

### Phase 1 — Extraction (current)
| Metric | Target |
|---|---|
| Gemini field accuracy (manual check) | > 75% |
| Avg confidence across fields | > 0.75 |
| Unknown rate | < 20% |
| Processing time / ball (batch mode) | < 30 s |
| Reviewed balls in DB | 500+ |

### Phase 2 — Technique layer
| Metric | Target |
|---|---|
| MediaPipe detection rate (side-on Tier A video) | > 90% frames |
| Pose feature computation rate per ball | > 80% balls |
| Coach-agreed technique flag accuracy | > 70% |

### Phase 3 — Pilot
| Metric | Target |
|---|---|
| Pilot academies onboarded | 3 |
| Weekly reports delivered per academy | ≥ 10 players |
| Coaches opening report within 48h | > 70% |
| Coaches sharing with players/parents | > 50% |
| Paid conversions after 3-month pilot | ≥ 1 of 3 |

---

## 10. Non-Goals {#non-goals}

Explicitly out of scope for the current roadmap:

- Exact ball speed detection from single-camera phone video (physics + calibration problem Hawk-Eye solves with 6 synced stadium cameras)
- Real-time / live streaming analysis (batch overnight is sufficient for the academy use case)
- Field placement reconstruction from broadcast
- Broadcast-quality 3D ball trajectory (current YOLO detection rate 7–31% — shelve until perspective calibration is built)
- Match simulation / captain decision engine
- BCCI / IPL franchise sales motion (different buyer, different product)
- Fielder analysis (sparse events, multi-camera requirement — defer indefinitely)
- D2C individual-player subscriptions (Fulltrack owns; distribution war we can't win)

---

**See also:** [PLAN.md](./PLAN.md) for the 6-week execution plan · [ENGINEERING.md](./ENGINEERING.md) for module specs + interface contracts · [DIAGRAMS.md](./DIAGRAMS.md) for sequence + data-flow diagrams.
