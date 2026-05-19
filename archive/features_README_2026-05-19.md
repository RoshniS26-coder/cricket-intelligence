# Features

Each subfolder is one capability of the Cricket Intelligence Engine. Folders
hold their own CLI scripts; supporting library code lives in `src/`.

## One-liner recipes (copy-paste)

| Scenario | Recipe |
|---|---|
| Net practice extraction (one batsman) | `features/ball_extraction/run_nets.sh <video> "<batsman>"` |
| T20 broadcast extraction (chunked) | `features/ball_extraction/run_broadcast.sh <video> <match_id> <team_a> <team_b>` |
| Batsman weakness profile + pitch map + bilingual narrative | `features/batsman_analysis/run_weakness.sh "<batsman>"` |
| List every batsman in the DB | `features/batsman_analysis/run_weakness.sh --list` |
| One-page AI Coach PDF for a single ball | `features/ai_coach_briefing/run_briefing.sh <clip> "<player>" <shot_type>` |
| Quick prose preview (no PDF) | `features/ai_coach_briefing/run_preview.sh <match_id>` |
| Critique a single shot vs auto-anchored pro | `features/critiques/run_critique.sh <clip> <shot_type> "<player>"` |
| Multi-shot net session critique → PDF | `features/critiques/run_net_critique.sh <clip> "<player>"` |
| Add a coaching tutorial to the corpus | `features/coaching_corpus/add_coaching.sh <video> <key> "<subject>" <shot_type>` |
| Add a YouTube reference clip | `features/coaching_corpus/add_reference.sh <url> <key> <shot_type> "<player>"` |
| Render annotated pose MP4 (needs venv312) | `source venv312/bin/activate && features/pose_analysis/run_render.sh <clip> "<player>"` |
| Side-by-side comparison MP4 | `features/rendering/run_compare.sh <left> <right>` |

Run any recipe with no arguments to see its expected inputs.

| Folder | What it does | Primary entry point |
|---|---|---|
| [`ball_extraction/`](ball_extraction/README.md) | Run the full ingest → segment → Gemini-extract → store pipeline | `python run_pipeline.py` (project root) |
| [`batsman_analysis/`](batsman_analysis/README.md) | Compute danger-zone profile + pitch map + bilingual narrative for a batsman | `analyse_batsman_weakness.py` |
| [`ai_coach_briefing/`](ai_coach_briefing/README.md) | One-page hybrid PDF briefing per player (Gemini + pose + critique + coaching corpus) | `render_player_briefing.py` |
| [`critiques/`](critiques/README.md) | Few-shot Gemini critique of a student's shot vs reference clips | `critique_student_clip.py`, `critique_multi_shot_session.py` |
| [`coaching_corpus/`](coaching_corpus/README.md) | Build the corpus of coach-tutorial knowledge & the reference shot library | `extract_coaching_video.py`, `add_reference_clip.py` |
| [`pose_analysis/`](pose_analysis/README.md) | MediaPipe pose features → narrated annotated video | `render_ball_video.py` |
| [`rendering/`](rendering/README.md) | Video utilities (side-by-side comparison, etc.) | `render_side_by_side.py` |
| [`db_migrations/`](db_migrations/README.md) | Idempotent SQLite schema migrations | `migrate_*.py` |

Cross-cutting code lives outside `features/`:

- `src/` — library code (intelligence/extractor, storage/db, analytics/weakness, etc.)
- `ui/app.py` — Streamlit review UI
- `src/api/main.py` — FastAPI REST API
- `run_pipeline.py` — top-level pipeline orchestrator

CV / YOLO / Roboflow capabilities (Roboflow `DualModelDetector`, OpenCV ball
tracker, custom YOLO training, line/length geometry, ball-trajectory tracker)
have been archived into `CV_Enhancements/` (gitignored, kept locally for the
day they're needed again). See `CV_Enhancements/README.md`.

See [`/FEATURES.md`](../FEATURES.md) for the canonical list of implemented and
planned features.
