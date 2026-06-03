---
description: Ingest one T20 match end-to-end (Cricsheet + ESPN → synthesize → load to Neon → reports → heatmaps) with the exact commands, checkpointed
---

You are running the **text-only match-ingestion pipeline** for cricket-intelligence
— the path the user otherwise reconstructs by hand every time. Drive it end to end,
printing each exact command before you run it, checkpointing, and stopping on the
first failure.

**Default and only recommended path is text-only (Cricsheet + ESPN).** Do NOT add
a video/segmentation/OCR pass unless the user explicitly asks for bowler-side
speed/crease (that path is retired — see `archive/`).

## Step 1 — Collect inputs (ask in one message if not given)

1. **Cricsheet match id** (e.g. `1439899`)
2. **Both innings' batting teams** as Cricsheet names them (e.g. `England`, `India`)
3. **A short label** for output files (e.g. `IndvsEng_1439899`)
4. **ESPN commentary PDFs** — one per innings — path(s) under `data/espncricinfo/`
   (the user saves these manually; confirm the files exist first)
5. **team-a / team-b / format** for the DB row (format defaults to `T20`)

Verify prerequisites before running anything:
```bash
ls data/cricsheet/ | head ; echo "GEMINI key:"; python -c "import os,dotenv;dotenv.load_dotenv();print(bool(os.getenv('GEMINI_API_KEY')))"
python -c "import os,dotenv;dotenv.load_dotenv();print('DB:', os.getenv('DATABASE_URL','')[:15])"   # must be postgres (Neon)
```
If the Cricsheet JSON for the id isn't under `data/cricsheet/`, tell the user to
download it from cricsheet.org first.

## Step 2 — Run the pipeline (per innings, then load)

For **each innings** (run the existing scripts; substitute the real values):

```bash
# a. Export the innings from Cricsheet
python match_intelligence/pipeline/export_cricsheet_innings.py \
  --cricsheet-id <ID> --innings <Team> \
  --out data/cricsheet/<dir>/<team>_innings.json

# b. Parse that innings' ESPN PDF → commentary JSON
python match_intelligence/pipeline/parse_espn_pdf.py \
  --pdf "data/espncricinfo/<file>.pdf" \
  --out data/espncricinfo/<dir>/match_<ID>_innings<n>_commentary.json \
  --match-id <ID>

# c. Synthesize text-only (resume-aware; ~$0.50, ~17 min). No video glob.
python match_intelligence/pipeline/synthesize_match_json.py \
  --cricsheet-json data/cricsheet/<dir>/<team>_innings.json \
  --espn-commentary data/espncricinfo/<dir>/match_<ID>_innings<n>_commentary.json \
  --gemini-video-glob 'data/NONEXISTENT_chunk*.json' \
  --out data/<label>_innings<n>_full_match_correct.json \
  --resume-dir data/<label>_innings<n>_synthesized \
  --model gemini-2.5-pro
```
If synthesis reports "model is overloaded", retry that step with
`--model gemini-3.1-flash`. The `--resume-dir` means a re-run picks up where it
stopped — never restart from scratch on a crash.

Then load each innings into **Neon** (first innings wipes the match; second uses
`--skip-wipe`):
```bash
python scripts/load_synth_to_db.py \
  --input data/<label>_innings1_full_match_correct.json \
  --match-id <ID> --team-a <A> --team-b <B> --format T20
python scripts/load_synth_to_db.py \
  --input data/<label>_innings2_full_match_correct.json \
  --match-id <ID> --team-a <A> --team-b <B> --format T20 --skip-wipe
```

## Step 3 — Reports + heatmaps (per innings)

```bash
python match_intelligence/reports/bowler_report.py  --match-id <ID> --innings <n> --out data/bowler_analysis/match_<ID>_innings_<n>.md
python match_intelligence/reports/batsman_report.py --match-id <ID> --innings <n> --out data/batsman_analysis/match_<ID>_innings_<n>.md
python match_intelligence/reports/generate_heatmaps.py --match-id <ID> --innings <n> --out-dir data/heatmaps/match_<ID>_innings_<n>/
```

## Step 4 — Verify + report
- Run the verification equivalent of `/db-status` for this match (Neon counts +
  coverage) and confirm both innings loaded with the expected ball counts.
- Tell the user the artifact paths created and any step that failed.
- Remind them to run `/update-context` at session end if this was substantive.

## Rules
- Print every command before running; stop at the first failure and surface the error.
- Text-only only — no video pass unless explicitly requested.
- Loads go to **Neon** (via `DATABASE_URL`), never the SQLite fallback.
- Never embed match-specific "expected value" corrections into any prompt
  (ESPN is the ground truth — see memory).
