# 📅 Cricket Intelligence Engine — 6-Week Execution Plan

> **Goal:** take the existing Gemini extraction pipeline and ship a working AI Analyst MVP for 3 pilot academies within 6 weeks.
> **Non-goal:** polish. Everything in this plan is "good enough to put in front of a coach," not "ready for the App Store."

---

## 0. Ground rules

1. **Phase 0 (Validation) gates everything.** Write zero new production code until 5 coach conversations are complete and ≥ 3 are green.
2. **Ship weekly.** Every Friday, something runs end-to-end on at least one real video.
3. **Batsman only.** No bowler/keeper work until Phase 5 pilot signals pull from at least one academy.
4. **Labels first, models later.** Every Streamlit correction must write to `ground_truth` from week 2 onward. The dataset is the moat, not the code.
5. **Measure what ships.** Each phase has a binary exit criterion. Don't move forward if it isn't hit.

---

## Phase 0 — Validation Sprint (Weeks −2 → 0, before any new code)

**Goal:** establish that coaches will pay for the artifact before building the pipeline that generates it.

See also: the 5-coach script is in [README-ish validation kit from the conversation]. Summary:

| Day | Deliverable |
|---|---|
| 1 | Pick 3 academy / U-19 / school matches from YouTube. List 15 coach targets in Bangalore / Mumbai / Delhi. |
| 2–3 | Run existing Gemini pipeline on the 3 matches. Pick 3 players with ≥ 40 balls each. |
| 4–5 | Hand-run MediaPipe on ~30 clips per player (90 clips). Manually tabulate head offset, stride, shoulder angle. |
| 6 | Build 3 PDF briefings in Google Docs (template in [ENGINEERING.md §9](./ENGINEERING.md#report-template)). |
| 7 | Send 15 outreach DMs (WhatsApp / LinkedIn / email). |
| 8–12 | Run five 30-minute coach meetings. Score each on the 5-signal rubric. |
| 13 | Aggregate scores. Decide: **build / iterate / pivot**. |
| 14 | Write a 1-page "what I learned" memo to self. |

### Exit criterion (hard gate)

- **≥ 3 of 5 coaches** hit "green" on the 5-signal scorecard:
  1. Report told them something new about at least 1 player
  2. Picked up / asked to keep the PDF
  3. Asked to share with a player, parent, or other coach
  4. Named a price ≥ ₹25k/yr
  5. Forward-looking ask ("when can I have it for my squad?")

**If green:** proceed to Phase 1. **If not:** do not write code. Either redo with different buyers (heads of academy instead of junior coaches), or pivot the artifact (try dismissal forensics instead of technique snapshot, or try bowling-action legality report instead of batting).

---

## Phase 1 — Pose Pipeline + Batsman Features (Weeks 1–2)

**Goal:** on any side-on batting clip, produce per-ball technique features automatically.

### Week 1 — ✅ DONE

| # | Task | Status |
|---|---|---|
| 1.1 | Add `mediapipe` + `edge-tts` to `requirements.txt`. **Note:** Python 3.14 wheel ships only `mediapipe.tasks` (no `solutions`), and on macOS the pose layer requires Python 3.12. Workaround: separate `venv312` for pose work. | ✅ landed |
| 1.2 | `src/pose/extractor.py` — uses MediaPipe **Tasks API** (`PoseLandmarker`), auto-downloads `pose_landmarker_full.task` (~10 MB) on first run, saves JSON to `data/pose/<clip>.json` | ✅ working (validated against test clip) |
| 1.3 | `src/pose/smoothing.py` — moving average + linear interpolation across gaps (≤ 3 frames). | ✅ landed |
| 1.4 | `src/pose/features/batsman.py` — impact frame (wrist-velocity), head_lateral_offset, stride_length_norm, shoulder_angle_deg, stance_width_norm, side_on_camera flag. | ✅ landed |
| 1.5 | SQLite migration — `pose_features` JSON column on `balls` table + `ground_truth` table for the flywheel. | ✅ `scripts/migrate_add_pose.py` run on live DB |

**Friday checkpoint:** ✅ end-to-end pose extraction working on test clip; pose JSON populated; render script produces annotated MP4.

### Week 2

| # | Task | Output |
|---|---|---|
| 2.1 | Scrape 300 batting-technique clips from YouTube (Cricket Bowling Drills, academy channels). Filter to side-on with batsman ≥ 40% frame. | `data/reference_clips/` populated |
| 2.2 | Run pose pipeline on all 300. Throw out ~30% that fail (mean confidence < 0.6). | ~200 clean pose sets |
| 2.3 | Write `scripts/calibrate_pose_thresholds.py` — computes target ranges (P25/P50/P75) for head_offset, stride_norm, shoulder_angle across the 200 reference clips. Save to `src/pose/thresholds.json`. | Thresholds file committed |
| 2.4 | Extend Streamlit review UI (`ui/app.py`) with: **pose inspector panel** (overlay MediaPipe skeleton on clip) + **one-tap technique-flag confirm/correct** buttons. Every click writes to `ground_truth` table. | Coach can approve/flip 5 technique flags per ball in < 10 s |
| 2.5 | Hand-label 200 balls across 3 players via the new UI. Own this yourself — don't outsource. | 200 labeled rows in `ground_truth` |

**Friday checkpoint (Phase 1 exit):**
- ✅ `pose_features` populated for ≥ 300 balls in SQLite
- ✅ `ground_truth` table has ≥ 200 rows with at least one technique flag corrected or confirmed
- ✅ Threshold ranges calibrated against 200 reference clips
- ✅ Pose pipeline runs end-to-end: `python run_pipeline.py --video X.mp4 --match-id Y --pose` succeeds

---

## Phase 2 — Identity Layer (Week 3)

**Goal:** reliably attach `batsman_name` + `bowler_name` to every ball. Without identity, there is no per-player product.

| # | Task | Output |
|---|---|---|
| 3.1 | `src/identity/scoreboard_ocr.py` — detect scoreboard region (heuristic: bottom strip + persistent text), run EasyOCR, parse batsman + bowler + score. Works on pro/broadcast videos. | `identify_from_scoreboard(frame) → {batsman, bowler, score}` |
| 3.2 | `src/identity/roster.py` — load per-match roster from `data/rosters/<match-id>.yaml` (simple list of 11 players per side + bowling order). | Roster object with `find_by_jersey(number)`, `list_batsmen()` |
| 3.3 | `src/identity/tagger.py` — integrates OCR + roster + manual fallback. Exposes `tag_ball(ball_record, video_frame) → (batsman_name, bowler_name, confidence)`. | Batting-side assignment deterministic given roster |
| 3.4 | Extend Streamlit with a **per-over tagger** screen: shows first ball of an over, coach picks bowler from roster dropdown (1 click), picks batsman (1 click). Remaining 5 balls inherit automatically. | Full innings of 120 balls taggable in < 10 minutes |
| 3.5 | Wire `tagger` into `run_pipeline.py` after extraction. Default behavior: OCR first, fall back to "unknown" if no roster + no scoreboard. | One academy match video → all balls have names populated |

**Friday checkpoint (Phase 2 exit):**
- ✅ On one pilot-academy video, ≥ 95% of balls have correct `batsman_name`
- ✅ Bowler assignment correct for ≥ 90% of overs after manual tagging
- ✅ `data/rosters/` has YAML lineups for each pilot academy's U-19 squad

---

## Phase 3 — Analytics + Narrative Briefing (Week 4)

**Goal:** aggregate ball-level data per player and produce a coach-facing briefing.

| # | Task | Output |
|---|---|---|
| 4.1 | `src/analytics/profile.py::build_player_profile(balls, player_id) → PlayerProfile` — aggregates balls with pose features: shot distribution, outcome distribution, technique means, fault rates, weakness cross-tab (length × outcome), per-bowler-type splits. | One function, deterministic, < 200 lines |
| 4.2 | `src/analytics/benchmarks.py` — compute academy-level medians + percentiles across all players in an academy's DB. Returns `AcademyBenchmark` usable as peer-comparison context in profiles. | `benchmark_academy(academy_id) → {median_head_offset, p25, p75, ...}` |
| 4.3 | `src/analytics/briefing.py` — Claude/Gemini call with a fixed prompt template. Takes `PlayerProfile + AcademyBenchmark + 3–5 raw clip descriptions` → returns 400-word markdown briefing with inline clip timestamps. | Briefing reads like a coach wrote it; no hedging, no marketing fluff |
| 4.4 | `src/report/pdf.py` — render `PlayerProfile + briefing + clip_links` to a 1-page A4 PDF using reportlab or Pillow. Template in [ENGINEERING.md §9](./ENGINEERING.md#report-template). | `data/reports/<academy>/<player>_<week>.pdf` generated |
| 4.5 | `scripts/analyze_player.py` — end-to-end: `python scripts/analyze_player.py --match X --player Y --out report.pdf`. Uses Phase 1–3 modules. | One command → one PDF in < 30 s (pose + Gemini already cached) |

**Friday checkpoint (Phase 3 exit):**
- ✅ For any tagged player with ≥ 20 balls, the pipeline produces a 1-page PDF briefing
- ✅ PDFs for 5 players (across the 3 pilot videos from Phase 0) printed and inspected
- ✅ Self-audit: would you show this to a coach? If no, iterate the briefing prompt.

---

## Phase 4 — Narrated Overlay Video — ✅ DONE (shipped early)

**Goal:** produce shareable MP4s that a coach can WhatsApp to a player. This is the demo-closer.

| # | Task | Status |
|---|---|---|
| 5.1 | `src/report/video_renderer.py` — OpenCV pipeline overlaying: skeleton, hip-line reference, head-offset dot (green/red), foot labels (F/B), wrist trail, impact-frame freeze + callouts, persistent metric panel, rotating bottom-banner cue. | ✅ landed |
| 5.2 | `src/report/tts.py` — Edge TTS (`en-IN-PrabhatNeural`), rate `-10%`. | ✅ landed |
| 5.3 | `src/report/mux.py` — ffmpeg muxer with `match_video_to_audio=True` (stretches slowed video to match narration length). | ✅ landed |
| 5.4 | `src/report/subtitles.py` — `.srt` from Edge TTS SubMaker. | 🔜 deferred — not blocking the pilot demo |
| 5.5 | `scripts/render_ball_video.py` — single-clip end-to-end orchestrator (Gemini → pose → smoothing → features → briefing text → TTS → overlay → mux). | ✅ landed |
| 5.6 | Compilation reel script (top-3 weakness + top-2 strength clips per player) | 🔜 needs analytics profile (Phase 3) first |

**Phase 4 exit criteria — met:**
- ✅ Single-clip render produces an annotated narrated MP4
- ✅ Overlay readable; metric panel visible
- ✅ Slowdown via ffmpeg `setpts`; audio length matches via secondary stretch

---

## Part F — Few-Shot Gemini Critique — ✅ DONE (NEW, not in original plan)

Added in response to user request: feed Gemini multiple ideal reference clips + the student clip in a single API call; get structured JSON listing technique deviations and drill recommendations.

| # | Task | Status |
|---|---|---|
| F.1 | `src/intelligence/critique_prompts.py` — `CRITIQUE_PROMPT_TEMPLATE` + `CRITIQUE_JSON_SCHEMA` + `CRITIQUE_SYSTEM_PROMPT` | ✅ landed |
| F.2 | `src/intelligence/few_shot_critique.py` — `critique_against_references()` orchestrates multi-video Gemini call | ✅ landed |
| F.3 | `scripts/critique_student_clip.py` — CLI with human-readable summary printer | ✅ landed |
| F.4 | Extend critique with optional `coaching_context` parameter | ✅ landed |
| F.5 | Extend CLI with `--coaching-keys` for index.yaml lookup | ✅ landed |
| F.6 | Sanity test: Kohli vs Kohli should rate `close_to_ideal` | 🔜 user to run on the 3 Kohli clips |
| F.7 | Real test: student vs Kohli reference | 🔜 needs a real student clip |

**Why this beat Phase 3 (full briefing module) to ship:** works on any camera angle, no pose pipeline required, ~₹3–5 per critique, ~1 day to build vs ~2-3 for the full briefing module.

---

## Part G — Coaching Corpus Extractor — ✅ DONE (NEW, not in original plan)

Added in response to user request: extract structured coaching knowledge from expert tutorial videos (Hindi / English / Hinglish) so the critique can cite real Indian-coach language, drills, and common mistakes.

| # | Task | Status |
|---|---|---|
| G.1 | `src/intelligence/coaching_prompts.py` — `COACHING_EXTRACT_JSON_SCHEMA` + `COACHING_EXTRACT_PROMPT_TEMPLATE` | ✅ landed |
| G.2 | `src/intelligence/coaching_extractor.py` — `extract_coaching_points()` + `coaching_context_block()` | ✅ landed |
| G.3 | `scripts/extract_coaching_video.py` — CLI with manifest auto-update | ✅ landed |
| G.4 | `data/coaching_corpus/index.yaml` — manifest scaffold | ✅ landed |
| G.5 | Wire into `few_shot_critique.py` via `coaching_context` parameter | ✅ landed |
| G.6 | Test on 6-min Hindi Kohli tutorial | ✅ verified — 0.95 confidence, 8 technique points, 2 cues, 4 mistakes |
| G.7 | Process 3 short Kohli/coach Shorts for cover_drive corpus | 🔜 user to run |
| G.8 | Build curated corpus across 15+ Phase-1 shot types | 🔜 ongoing |

**Why this matters:** the differentiator vs CricHeroes/Fulltrack is critique that quotes real coach language, not generic LLM advice. Each new tutorial ingested compounds the dataset asset.

---

## Part H — Visual Side-by-Side Renderer — ✅ DONE (NEW, MVP)

`scripts/render_side_by_side.py` — ffmpeg `hstack`/`vstack` with burned-in labels and optional slowdown. No pose, no narration, no impact-frame alignment. Quick visual comparison a coach can WhatsApp today.

The pose-aligned, narrated, impact-synced version is still planned as Part C (`src/report/comparison.py`) — that needs ~2 days more work. The current renderer is enough to show "you vs Kohli" today.

---

## Downloader — ✅ EXTENDED

`src/ingestion/downloader.py` CLI now supports `--target {raw, reference-library, coaching-corpus}` and `--shot-type`. Routes the file to:
- `data/raw_videos/` (default — match/student videos)
- `data/reference_library/videos/<shot-slug>/` (reference clips)
- `data/raw_videos/` (coaching tutorials — extracted JSON lives in `data/coaching_corpus/`)

---

## Part I — Hybrid Briefing PDF — ✅ DONE (NEW, the deliverable a coach hands to a parent)

Combines all four engines' outputs into a single 1-page A4 PDF.

| # | Task | Status |
|---|---|---|
| I.1 | Add `reportlab>=4.1.0` to requirements + install | ✅ landed |
| I.2 | `src/analytics/briefing.py` — `PlayerBriefing` dataclass + `assemble_briefing()` | ✅ landed |
| I.3 | `src/report/pdf.py` — `render_briefing_pdf()` using reportlab Platypus | ✅ landed |
| I.4 | `scripts/render_player_briefing.py` — end-to-end CLI with graceful degradation | ✅ landed |
| I.5 | Smoke test: fake-data PDF generation | ✅ verified — 1-page, ~5 KB, well-formed metadata |
| I.6 | Real-clip test: full hybrid on a Kohli/student clip | 🔜 user to run |
| I.7 | Embed impact-frame snapshot (with skeleton overlay) into PDF | 🔜 +30 min |
| I.8 | Devanagari font registration for verbatim Hindi cues | 🔜 +2 hours |
| I.9 | Multi-ball briefing (current is single-ball/single-clip) | 🔜 needs `src/analytics/profile.py` first |

**This closes the loop** — for the first time, a coach can run ONE COMMAND on a student clip and walk away with a printable artifact:

```bash
python scripts/render_player_briefing.py \
    --clip student.mp4 --player "Rahul" --shot-type cover_drive \
    --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \
    --coaching-keys "coach-kohli-cover-hindi" \
    --academy "Demo U-19" \
    --out rahul_briefing.pdf
```

That PDF is what gets WhatsApped to the parent. It's also what you bring to the 5-coach validation meetings.

---

## Implementation status — final summary

| Phase / Part | Status |
|---|---|
| Phase 0 — 5-coach validation | 🔜 user to run |
| Phase 1 — Pose pipeline (week 1) | ✅ DONE |
| Phase 1 — Pose calibration (week 2, on 200 reference clips) | 🔜 needs `scripts/calibrate_pose_thresholds.py` |
| Phase 2 — Identity layer (OCR + roster) | 🔜 designed, not built |
| Phase 3 — Per-player profile aggregator | 🔜 designed, not built |
| Phase 4 — Narrated overlay video render | ✅ DONE |
| Part F — Few-shot Gemini critique | ✅ DONE |
| Part G — Coaching corpus extractor | ✅ DONE |
| Part H — Visual side-by-side renderer (MVP) | ✅ DONE |
| Part C — Pose-aligned side-by-side renderer | 🔜 designed, not built |
| **Part I — Hybrid briefing PDF** | ✅ **DONE** |
| Phase 5 — Pilot deployment to 3 academies | 🔜 after coach validation |

**The product is now in shippable demo state.** Everything needed to take the 5-coach validation meetings (per Phase 0) is built. The next non-trivial work items are calibration (week 2 of Phase 1), identity (Phase 2), and multi-ball aggregation (Phase 3).

---

## Part E — Reference Library — ✅ scaffolded; curation in progress

Curated library of side-on, pose-validated clips of pro batsmen. Used by both critique (mandatory references) and pose comparison (planned).

| # | Task | Status |
|---|---|---|
| E.1 | `data/reference_library/` directory structure with `pose/` and `features/` subdirs | ✅ created |
| E.2 | `data/reference_library/index.yaml` manifest with documented schema, quality tiers, and 3 Kohli clips registered (status: pending validation) | ✅ landed |
| E.3 | Validate the 3 Kohli clips via `render_ball_video.py` and promote to gold/silver/bronze | 🔜 user to run + manually update YAML |
| E.4 | Curate 12 more gold-rated clips (one per Phase-1 shot type) — Tendulkar straight drive, Rohit pull, Dravid front-foot defence, etc. | 🔜 ongoing |
| E.5 | `scripts/promote_to_reference.py` — automate validation + copy + manifest update | 🔜 deferred (manual flow OK for first 15 clips) |

Canonical players per shot type documented inline in `data/reference_library/index.yaml` and in `README_NEW.md`.

---

## Phase 5 — Pilot Deployment (Week 6)

**Goal:** get the product into 3 academies with real weekly usage.

| # | Task | Output |
|---|---|---|
| 6.1 | Close 3 pilot academies via the Phase 0 relationships. Terms: **3 months free** in exchange for video + written data-rights agreement (use clips for model training, anonymized). | Signed LOI (even informal) per academy |
| 6.2 | Physical setup: deliver Tier A camera kit (tripod + phone mount + SD card + laminated placement guide). Install + train coach in a 30-minute visit. | 1 kit per academy deployed |
| 6.3 | Onboarding: upload roster YAML; tag first 2 practice sessions together with the coach (so they learn the workflow). | Roster saved; 2 × 120+ balls tagged per academy |
| 6.4 | Cadence: receive videos by Tuesday night, deliver briefings + narrated clips by Thursday morning. | Weekly Monday → Thursday cycle |
| 6.5 | Instrumentation: log every coach open, share, correction, and feature-flag request. Minimal analytics — email-yourself metrics weekly. | Weekly metrics email |

**Friday checkpoint (Phase 5 exit / Month 2 kickoff decision):**
- ✅ 3 academies receiving briefings for ≥ 10 players each, weekly
- ✅ Coaches open reports within 48 hours > 70% of the time
- ✅ At least 1 academy shares briefings with players/parents unprompted

**Month 2 decision gate:** at the end of the 3-month pilot, do at least 1 of 3 academies convert to a paid annual contract? If yes, build v2 (bowler module + keeper module). If no, debrief: wrong ICP, wrong price, wrong artifact — choose one and iterate.

---

## Parallel track (every week) — Flywheel instrumentation

Alongside the phase work, the following is ongoing from Week 2:

- **Every Streamlit correction → `ground_truth` row.** Fields: `(ball_id, field_name, old_value, new_value, coach_id, timestamp, pose_features_snapshot)`
- **Weekly label count report.** Target by end of Phase 5: ≥ 2,000 corrected labels across 3 academies.
- **Threshold re-calibration.** At end of every 500 new labels, re-run `calibrate_pose_thresholds.py` and diff against the committed thresholds file. Document any drift.

This is the dataset that becomes the moat. Do not skip.

---

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Phase 0 coaches don't light up | Medium | Pivot artifact (dismissal forensics / bowling-action legality) before building |
| MediaPipe detection fails on Indian skin tones / small players | Low–Medium | Validate on Phase 1 reference clips first; fall back to smoothing + imputation |
| Pose thresholds don't generalize from pro clips to U-19 academy kids | High | Re-calibrate against academy Phase 5 data in Month 2; keep thresholds per-age-group |
| Academy coach won't operate a camera tripod consistently | Medium | Kit + 30-minute install + laminated guide + follow-up visit after 2 weeks |
| Gemini cost at scale | Low in pilot | At 3 academies × 2 matches/week × ₹20 per match = ₹5k/month. Fine. Re-evaluate at 30+ academies. |
| CricHeroes ships competing pose feature | Low in 12 months | Defenses documented in [ARCHITECTURE.md §8](./ARCHITECTURE.md#flywheel) — speed, dataset, contracts. |
| Fulltrack AI enters India market | Medium in 18 months | India-specific UX (vernacular), lower price point, academy distribution are pre-built moats |

---

## What is explicitly NOT in this plan

- Bowler analysis (Phase 6, after pilot signals pull)
- Keeper analysis (Phase 7)
- Fielder analysis (not in near-term roadmap)
- Mobile app (browser-served PDFs + WhatsApp MP4 is enough for pilot)
- Multi-tenant SaaS infra (pilot runs on the same local DB + scripts per academy — formalize later)
- Payment integration (pilot is free; billing comes in Month 4)
- Performance optimization (render time, API costs) — address only when a customer complains

---

**See also:** [ARCHITECTURE.md](./ARCHITECTURE.md) for the layer model · [ENGINEERING.md](./ENGINEERING.md) for module specs · [DIAGRAMS.md](./DIAGRAMS.md) for sequence + data-flow diagrams.
