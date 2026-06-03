---
description: Estimate Gemini cost + wall-clock time for processing a video of N hours (or a text-only synthesis), using the project's known rates
---

You are giving a quick, honest cost + time estimate for a Gemini job on
cricket-intelligence. The user asks this often ("how much for a 4-hour T20?") —
answer from the rates below, show your arithmetic, and don't overstate precision.

## Inputs
Parse from the user's args / message:
- **duration** — video hours (e.g. `4`, `1.5`) OR "text-only" for a synthesis run
- **model** (optional) — defaults: video → `gemini-3.1-pro`; text → `gemini-2.5-pro`
- **innings count** (optional, for text-only) — defaults to 1

## Rates (project-calibrated; state these as approximate)
- **Text-only synthesis** (Cricsheet + ESPN, gemini-2.5-pro): **~$0.50 and ~17 min per innings.**
- **Video pass** (chunks, gemini-3.1-pro): **~$1.3–1.5 per video-hour**, and wall
  time roughly **0.5–0.75 hr of processing per video-hour** (upload + chunking +
  inference). A full ~4-hr T20 broadcast ≈ **$5–6 and ~2–3 hrs**.
- A single trimmed innings (~1.5–2 hr of footage) ≈ **$2–3 and ~1–1.5 hrs**.

## Steps
1. Compute the estimate. For video: `cost ≈ hours × $1.4`; `time ≈ hours × ~0.6 hr`.
   For text-only: `cost ≈ innings × $0.50`; `time ≈ innings × ~17 min`.
2. Present a one-line headline (`≈ $X, ≈ Y hrs`) then the arithmetic underneath.
3. **Always recommend the default:** unless the deliverable needs bowler-side
   speed/crease, text-only is ~10× cheaper and far faster — say so.
4. Note the model-overload fallback (`gemini-2.5-pro` → `gemini-3.1-flash`) if relevant.

## Rules
- These are estimates from past runs, not a billing API — label them approximate.
- Don't invent precise per-token math; the per-hour heuristic is what's calibrated.
- If asked for the cheapest path, the answer is almost always **text-only synthesis**.
