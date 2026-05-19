# Project context — dynamic session log

This file is a **rolling log** of what's been worked on, what's in the DB,
and what's blocked. Updated at the end of each working session via the
`/update-context` slash command (or manually).

For static project info (architecture, conventions, directory map),
see **`CLAUDE.md`** at the repo root.

---

## Current state (latest entry on top)

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
