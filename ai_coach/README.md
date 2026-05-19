# AI Coach

Student-clip critique + AI-generated coaching briefings + pose analysis. One of the two products in this repo (the other is [`match_intelligence/`](../match_intelligence/)).

## What it produces

Given a video of a student's shot (or a whole net-practice session) and optional references of professionals doing the same shot:

| Artifact | What it is |
|---|---|
| **Structured JSON critique** | Per-shot deviations from reference form + drill recommendations |
| **One-page PDF briefing** | Hybrid coaching output combining Gemini analysis + MediaPipe pose features + few-shot critique + drills from the coaching corpus |
| **Annotated narrated video** | MediaPipe pose landmarks drawn on the clip, with TTS narration of the technique notes |
| **Side-by-side compare video** | Student vs reference, stacked horizontally or vertically |

## Layout

```
ai_coach/
├── README.md                     ← this file
│
├── lib/                          ← internal libraries
│   ├── coaching_extractor.py    ← extract structured guidance from coach tutorials
│   ├── coaching_loader.py       ← inject coaching corpus into prompts
│   ├── coaching_prompts.py
│   ├── critique_prompts.py      ← few-shot critique prompts
│   ├── few_shot_critique.py     ← critique runner against reference clips
│   ├── session_catalog.py       ← multi-shot net-session pre-pass
│   ├── briefing.py              ← assembles PlayerBriefing dataclass
│   └── pose/                    ← MediaPipe wrappers + smoothing + batsman features
│
├── briefing/                    ← AI Coach briefing CLI (full hybrid PDF)
│   ├── render_player_briefing.py
│   ├── preview_coach_briefing.py
│   ├── run_briefing.sh
│   └── run_preview.sh
│
├── pipeline/
│   ├── critiques/               ← critique CLIs (single shot or net session)
│   │   ├── critique_student_clip.py
│   │   ├── critique_multi_shot_session.py
│   │   ├── run_critique.sh
│   │   └── run_net_critique.sh
│   └── coaching_corpus/         ← build the knowledge bases
│       ├── extract_coaching_video.py  ← tutorial → structured JSON
│       ├── add_reference_clip.py      ← YouTube clip → reference library
│       ├── add_coaching.sh
│       └── add_reference.sh
│
├── pose/                        ← pose render CLI
│   ├── render_ball_video.py
│   └── run_render.sh
│
├── rendering/                   ← side-by-side video compare
│   ├── render_side_by_side.py
│   └── run_compare.sh
│
└── report/                      ← PDF / TTS / video mux primitives
    ├── pdf.py, mux.py, tts.py, video_renderer.py
```

## Pre-requisites

- **Python 3.10+** for everything except the pose layer
- **Python 3.12 + MediaPipe** for the pose features and the full briefing
  ```bash
  python3.12 -m venv venv312 && source venv312/bin/activate
  pip install mediapipe edge-tts
  ```
- `GEMINI_API_KEY` in `.env`

## Quick recipes

| Scenario | Command |
|---|---|
| Single-ball critique vs canonical pro | `ai_coach/pipeline/critiques/run_critique.sh <clip> <shot_type> "<player>"` |
| Multi-shot net-session critique → PDF | `ai_coach/pipeline/critiques/run_net_critique.sh <clip> "<player>"` |
| Full hybrid one-page PDF briefing | `ai_coach/briefing/run_briefing.sh <clip> "<player>" <shot_type>` |
| Quick prose preview (no PDF) | `ai_coach/briefing/run_preview.sh <match_id> ["<batsman>"]` |
| Annotated narrated pose video | `source venv312/bin/activate && ai_coach/pose/run_render.sh <clip> "<player>"` |
| Add a coaching tutorial to the corpus | `ai_coach/pipeline/coaching_corpus/add_coaching.sh <video> <key> "<subject>" <shot_type>` |
| Add a YouTube reference clip | `ai_coach/pipeline/coaching_corpus/add_reference.sh <youtube_url> <key> <shot_type> "<player>"` |
| Side-by-side compare video | `ai_coach/rendering/run_compare.sh <left_video> <right_video>` |

For full flag reference on any command, use `--help` on the Python CLI.

## Key flows

### 1. Student critique (`pipeline/critiques/`)

Take a student clip + (optional) reference clips of pros doing the same shot. Send to Gemini with a few-shot prompt that anchors the critique to the references. Get back structured JSON: deviations, drill recommendations, encouragement.

- **Solo mode** (no references): auto-anchored to a canonical pro for the shot type
- **Net-session mode**: a `session_catalog` pre-pass first identifies individual shots in a long multi-shot video, then critiques each one

### 2. AI Coach briefing (`briefing/`)

Combines four signals into one PDF:
1. Gemini per-ball extraction (line, length, swing, shot, contact, outcome)
2. MediaPipe pose features (head offset, stride, shoulder angle)
3. Few-shot critique vs reference clips
4. Coaching corpus drills + cues from extracted tutorials

Designed to be readable at arm's length and shareable on WhatsApp.

### 3. Coaching corpus (`pipeline/coaching_corpus/`)

Extracts structured technique guidance from coach tutorial videos. Stored as bilingual `{en, hi}` JSON in `data/coaching_corpus/`. Used by `briefing/` and `critiques/` to inject domain knowledge.

### 4. Pose layer (`lib/pose/` + `pose/`)

MediaPipe Tasks API pose extraction → smoothing → batsman-specific features (head over front foot, stride length, shoulder rotation) → narrated annotated video render.

Requires Python 3.12 + MediaPipe. Side-on camera angle is required for usable features.

## Separation contract

- `ai_coach/` **never** imports from `match_intelligence/`
- `ai_coach/` freely uses `src/` (shared schema, DB, validators)
- `match_intelligence/` may optionally import from `ai_coach/` (currently doesn't)

## Where the data lives

| Type | Path |
|---|---|
| Coaching tutorials (extracted JSON) | `data/coaching_corpus/` |
| Reference clips (pro footage) | `data/reference_library/` |
| Pose extraction outputs | `data/pose/` |
| Generated PDF briefings | `data/reports/` |
| Side-by-side videos | wherever you point `--out` |
