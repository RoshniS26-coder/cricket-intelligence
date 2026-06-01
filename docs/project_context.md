# Project context — dynamic session log

This file is a **rolling log** of what's been worked on, what's in the DB,
and what's blocked. Updated at the end of each working session via the
`/update-context` slash command (or manually).

For static project info (architecture, conventions, directory map),
see **`CLAUDE.md`** at the repo root.

---

## Current state (latest entry on top)

### 2026-06-01 — Video-only model benchmark attempted, found non-viable, and archived

**Done today:**
- Worked on `benchmark/` branch (video-only ball extraction across Gemini + local Ollama VLMs). Goal: run benchmark with **qwen only, chunk_001**.
- Attempted `qwen2.5vl:7b` on `data/video_clips_T20-IndvsEng-IndBat/T20-IndvsEng-IndBat_chunk_001.mp4` — repeatedly failed:
  - Root cause 1: Ollama default `num_ctx=4096` silently **truncated** the 16-frame prompt (5524 tok) → empty output. Fixed runner to set `num_ctx=8192`, `num_predict=2048`, timeout 180→900s.
  - Root cause 2: hardware ceiling — 7B (Q4, ~5.5 GB) requests ~15 GiB on an **8 GB M1**, output layer offloads to CPU, swaps. Measured **~0.23 tok/s** → a full 12-ball JSON would take 60–110 min; every run hit the timeout.
- Pulled `qwen2.5vl:3b` (fits memory, ~4.9 GiB) but it **segfaults on load** under Ollama 0.17.7: `GGML_ASSERT([rsets->data count] == 0)` Metal residency-set bug (crashes even text-only, even on a fresh server). brew offers 0.17.7→0.24.0 as the likely fix; **upgrade NOT performed** (user declined to run it).
- **Conclusion (agreed):** local single-image Ollama VLMs cannot do video/motion analysis — no temporal channel, ~1 frame/38s sampling can't capture a sub-second pitch point; they only plausibly read static scoreboard OCR (speed/names/runs). Benchmark is a negative/baseline result, not a viable extraction path. Real path stays Gemini-video-native + ESPN/Cricsheet synthesis.
- **Archived the benchmark:** `mv benchmark → benchmark_archive/`, swapped `.gitignore` block to ignore `benchmark_archive/`, `git rm -r --cached benchmark` (12 files untracked, kept on disk). Also moved the `/benchmark-video` slash command → `benchmark_archive/benchmark-video.command.md` (was untracked).
- Disk cleanup: volume was at 98% (`no space left on device` during 3B pull). User deleted `bakllava` + `moondream` (reclaimed ~4 GiB → 8.9 GiB free). Remaining Ollama models still ~26 GB.

**DB state:**
- **4 matches, 5 innings, 290 ball rows** — unchanged this session.
- `1276906`: 120 + 120 (innings 1 + 2). `kohli-nets-20260506`: 22. `srilanka-match`: 14. `suryavanshi-ind-aus`: 14.

**Reports + artifacts added/changed:**
- `benchmark/` → `benchmark_archive/` (whole tree, gitignored, off version control — code, results, edited runner/config, `build_analysis.py`).
- `.claude/commands/benchmark-video.md` → `benchmark_archive/benchmark-video.command.md` (slash command archived; no longer an active skill).
- `.gitignore` — `benchmark/results/` block replaced with `benchmark_archive/`.
- Staged-but-uncommitted: deletion of 12 `benchmark/` files + `.gitignore` edit.

**Open questions / decisions pending:**
- Whether to upgrade Ollama 0.17.7→0.24.0 (would fix the 3B Metal crash) — deferred; benchmark likely not worth resuming regardless.
- Whether to delete the remaining ~26 GB of Ollama vision models (volume still ~96% full).
- Whether to commit the benchmark-archival changes (staged deletions + `.gitignore`) on this `benchmark` branch or fold into `main`.

**Next session (next priority):**
- Benchmark is closed/archived — resume the **pre-benchmark** priority: run the 2025 IND vs ENG synthesis pipeline (`run_synthesis_2025.sh` → `load_all_2025.sh`) to get 10 more innings into the DB (ESPN PDFs ready since 2026-05-21).
- Then the frontend scouting/weakness pages become genuinely useful on a multi-match corpus.

---

### 2026-05-21 — Full Next.js frontend built; per-match batting + bowling innings reports live

**Done today:**
- Built entire `frontend/` Next.js 16.2.6 app (App Router, TypeScript, Tailwind v4, React Query)
- **Phase 4 shared components:** `PitchHeatmap` (SVG, 5×5 grid, frequency + danger modes), `WagonWheel` (custom SVG polar bar chart, 18 directions, handedness mirroring), `PhaseBreakdown`, `PlayerDropdown`, `NarrativeCard` (EN/HI toggle), `MatchMetaTable`
- **Pages built:** `/scouting` (player grid + tabs), `/scouting/player/[name]` (full batter/bowler profile with pitch map, wagon wheel, weakness breakdown, matchups), `/scouting/compare` (side-by-side), `/prep` (team weaknesses + head-to-head matchup), `/coach` (clip critique + briefings), `/data` (ball table + CSV export), `/matches/[id]` (per-match batting + bowling innings report)
- **API additions to `src/api/main.py`:**
  - Fixed `GET /team/{team_name}/weaknesses` — removed non-existent `innings_team` column, replaced with `matches.team_a/team_b` + innings number join
  - Added `footwork` and `contact_quality` distributions to `GET /players/{name}/batting`
  - Added `GET /matches/{match_id}/innings/{innings}/batsmen` — per-batsman line/length/shots/footwork/contact/matchups/phase split/scoring zones
  - Added `GET /matches/{match_id}/innings/{innings}/bowlers` — per-bowler speed/crease/variations/line/length/matchups/shots-against/phase split
- **`src/analytics/weakness.py`:** Added `unknown` zone filter so "unknown/middle" no longer appears as top weakness
- Pitch map / wagon wheel rebuilt as SVG to match Streamlit visual quality
- `npm run build` clean — 9 routes, zero TypeScript errors
- New ESPN PDFs landed: `data/espncricinfo/IndvsEng/` — 10 PDFs covering all 5 IND vs ENG 2025 T20Is (both innings each)
- New scripts staged (not yet run): `match_intelligence/pipeline/run_synthesis_2025.sh`, `scripts/load_all_2025.sh`
- Deleted stale web-asset folder: `data/espncricinfo/Match Stats - IND vs ENG 5th T20I, Best Performances by Batters & Bowlers_files/`

**DB state:**
- **4 matches, 5 innings, 290 ball rows** — unchanged this session
- `1276906` (ENG vs IND, Trent Bridge 2022): 240 rows (120 × 2 innings) — only match with full frontend coverage
- `kohli-nets-20260506`: 22 rows / `srilanka-match`: 14 rows / `suryavanshi-ind-aus`: 14 rows — legacy, no ESPN commentary
- 2025 IND vs ENG series (matches 1439899–1439903) not yet synthesized/loaded — ESPN PDFs are ready

**Reports + artifacts added/changed:**
- `frontend/` — entire Next.js app (new, untracked)
- `src/api/main.py` — 3 new endpoints + innings_team bugfix
- `src/analytics/weakness.py` — unknown zone filter
- `data/espncricinfo/IndvsEng/*.pdf` — 10 ESPN PDFs for 2025 series (untracked)
- `data/cricsheet/IndvsEng2025/` — cricsheet data for 2025 series (untracked)
- `scripts/db_migrations/migrate_add_player_narratives.py` (untracked, not yet run)
- `src/api/ai_coach_router.py` (untracked, not yet integrated)

**Open questions / decisions pending:**
- Whether to commit the `frontend/` directory now or after 2025 data is loaded
- `_MIN_SAMPLE` in `weakness.py` still at 2 — heatmap shows red cells from tiny samples; bump to 5–8 for multi-match corpus
- AI coach router (`src/api/ai_coach_router.py`) exists but not yet wired into `main.py`

**Next session (next priority):**
- Run the 2025 synthesis pipeline: `run_synthesis_2025.sh` → `load_all_2025.sh` → verify 10 innings load cleanly
- Once 2025 data is in DB, weakness analysis and scouting pages become genuinely useful (multi-match sample)
- Add "Matches" nav tab to Navbar (currently matches only reachable from home page table)

---

### 2026-05-18 — Project structure cleanup + context system

**Done today:**
- Audited repo for cruft; moved 8 superseded files to `archive/data/chunk_prompt_experiments/`:
  - `IndvsEng_chunk1_with_espn{,_v2,_v3,_v4_clean,_whisper}.json`
  - `IndvsEng_chunk2_with_espn{,_v4_clean}.json`
  - `IndvsEng_merged.json`
  - All replaced by the synthesis pipeline; kept for historical reference
- Wrote `CLAUDE.md` at repo root — auto-loaded by Claude Code at session start.
  Captures project purpose, three-source pipeline, directory map, DB schema,
  conventions, and a 10-step "add a new match" cheatsheet.
- Created this file (`docs/project_context.md`) — dynamic state log.
- Created `/update-context` slash command so end-of-session updates take 1
  command instead of manual editing.
- Created `.claude/settings.local.json` with a `SessionEnd` hook (agent type)
  that auto-runs the context-update logic when Claude session ends.
  Improved prompt to MERGE into same-date entries instead of duplicating.
- Added `.claude/settings.local.json` to `.gitignore` (personal automation).
- (Manual dry-run today) Merged corrected DB-state facts into this entry.

**DB state (corrected — was incomplete in original entry):**
- **4 matches, 5 innings, 290 ball rows total**
- `1276906` (ENG vs IND, 3rd T20I, Trent Bridge, 2022-07-10): 240 rows
  (120 innings 1 + 120 innings 2) — today's main work
- `kohli-nets-20260506`: 22 rows, innings 1 — leftover from prior video pipeline
- `srilanka-match`: 14 rows, innings 1 — leftover
- `suryavanshi-ind-aus`: 14 rows, innings 1 — leftover
- Only 1276906 has the new innings-qualified ball_id format (`1276906_i{1,2}_{o}_{b}`);
  legacy matches still use the older `{match}_{o}_{b}` scheme — collisions are
  not possible there since each has only one innings.
- innings 2 had video processing → 94% bowler_crease, 62% speed coverage
- innings 1 was ESPN-only → 18% bowler_crease, 22% speed coverage (expected)
- All other technique fields well-populated in both innings (88-99%)

**Reports + artifacts ready:**
- `data/IndvsEng_match_1276906_full.csv` — 240 rows × 28 cols, combined CSV
- `data/bowler_analysis/match_1276906_innings_{1,2}.md` — per-bowler reports
- `data/batsman_analysis/match_1276906_innings_{1,2}.md` — per-batter reports
- `data/heatmaps/match_1276906_innings_{1,2}/` — pitch maps + wagon wheels
- Streamlit UI: rich CSV export (28 cols), wagon wheel section added

**Open questions / decisions pending:**
- Whether to scale to a 30-match corpus (would make weakness maps statistically
  trustworthy). Cost: ~$30 + 1 work-day for text-only on 30 matches.
- Whether to add a `shot_intended` field to the schema (decided not to today —
  see conversation about Pant pull/on_drive disagreement).
- Whether to bump `_MIN_SAMPLE` in `src/analytics/weakness.py` from 2 → 5/8
  so the UI heatmap stops painting cells red from tiny samples.

**Next session (next priority):**
- Decide on corpus expansion: pick the next 3-5 matches to add.
- Or: tighten `_MIN_SAMPLE` in weakness.py + add ball-count overlay to UI heatmap.
- Or: build "Setup-to-Dismissal Sequence Miner" feature now that 240 clean balls exist.

---

<!-- Older entries go below. Newer entries pushed to the top by /update-context. -->
