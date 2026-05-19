# 🔧 Cricket Intelligence Engine — Engineering Handbook

> **Purpose:** file-by-file specs, interface contracts, and operational guides for the new modules added on top of the existing Gemini extraction pipeline.
> **Audience:** the engineer implementing the 6-week plan (currently: you).

## Module status snapshot (2026-04-28)

| Status | Modules |
|---|---|
| ✅ **LANDED** (weakness analysis) | `src/analytics/weakness.py` (danger zone stats), `src/intelligence/weakness_narrator.py` (bilingual Gemini narrative), `src/analytics/pitch_map.py` (matplotlib heatmap PNG), `scripts/analyse_batsman_weakness.py` (CLI), `src/storage/db.py` extended with `get_balls_for_batsman` + `list_batsmen`, `src/api/main.py` extended with `/analytics/weakness`, `ui/app.py` extended with Weakness Analysis tab |
| ✅ **LANDED** (briefing layer) | `src/analytics/briefing.py` (PlayerBriefing + assemble_briefing), `src/report/pdf.py` (reportlab 1-page A4 hybrid briefing), `scripts/render_player_briefing.py` (end-to-end CLI with `--skip-pose` / `--skip-gemini` for graceful degradation), `requirements.txt` extended with `reportlab>=4.1.0` |
| ✅ **LANDED** (coaching corpus) | `src/intelligence/coaching_prompts.py` (bilingual {en,hi} schema), `src/intelligence/coaching_extractor.py`, `scripts/extract_coaching_video.py`, `scripts/add_reference_clip.py`, `scripts/render_side_by_side.py`, `data/coaching_corpus/index.yaml`, `src/intelligence/few_shot_critique.py`, `scripts/critique_student_clip.py`, `src/ingestion/downloader.py` |
| ✅ **LANDED** (pose + detection) | `src/pose/extractor.py` (Tasks API), `src/pose/smoothing.py`, `src/pose/features/batsman.py`, `src/report/video_renderer.py`, `src/report/tts.py`, `src/report/mux.py`, `scripts/render_ball_video.py`, `src/intelligence/critique_prompts.py`, `data/reference_library/index.yaml` |
| ✅ **EXISTING** | `src/intelligence/{extractor,schema,prompt}.py`, `src/detection/detect.py`, `src/storage/db.py`, `src/validation/normalizer.py`, `src/api/main.py`, `ui/app.py`, `src/segmentation/clip_extractor.py` |
| 🔜 **PLANNED** | `src/identity/{scoreboard_ocr,roster,tagger}.py`, `src/analytics/{profile,benchmarks}.py` (peer benchmarks + multi-match aggregation), `src/report/{subtitles,comparison}.py`, embedded impact-frame snapshot in PDF, multi-ball / weekly briefing |

---

## Table of Contents

1. [Repo Layout](#repo-layout)
2. [New Dependencies](#deps)
3. [Module Specs](#module-specs)
   - 3.1 [`src/pose/extractor.py`](#pose-extractor)
   - 3.2 [`src/pose/smoothing.py`](#pose-smoothing)
   - 3.3 [`src/pose/features/batsman.py`](#pose-features-batsman)
   - 3.4 [`src/identity/scoreboard_ocr.py`](#scoreboard-ocr)
   - 3.5 [`src/identity/roster.py`](#roster)
   - 3.6 [`src/identity/tagger.py`](#tagger)
   - 3.7 [`src/analytics/profile.py`](#analytics-profile)
   - 3.8 [`src/analytics/benchmarks.py`](#analytics-benchmarks)
   - 3.9 [`src/analytics/briefing.py`](#analytics-briefing)
   - 3.10 [`src/report/pdf.py`](#report-pdf)
   - 3.11 [`src/report/video_renderer.py`](#report-video)
   - 3.12 [`src/report/tts.py`](#report-tts)
   - 3.13 [`src/report/mux.py`](#report-mux)
4. [Schema Additions](#schema)
5. [DB Migrations](#migrations)
6. [CLI Integration with `run_pipeline.py`](#cli)
7. [Camera Setup Spec](#camera-spec)
8. [Threshold Calibration Guide](#thresholds)
9. [Report Template](#report-template)
10. [Flywheel Hooks in Review UI](#flywheel-hooks)
11. [Testing & Validation](#testing)

---

## 1. Repo Layout {#repo-layout}

```
cricket-intelligence/
├── src/
│   ├── ingestion/           ✅ existing
│   ├── segmentation/        ✅ existing
│   ├── detection/           ✅ existing
│   ├── tracking/            ⚠ shelved
│   ├── intelligence/        ✅ existing  (schema, prompt, extractor)
│   ├── validation/          ✅ existing
│   ├── storage/             ✅ existing  (extend with pose_features + ground_truth)
│   ├── api/                 ✅ existing  (extend with /players, /briefings endpoints)
│   │
│   ├── identity/            🆕
│   │   ├── __init__.py
│   │   ├── scoreboard_ocr.py
│   │   ├── roster.py
│   │   └── tagger.py
│   │
│   ├── pose/                🆕
│   │   ├── __init__.py
│   │   ├── extractor.py
│   │   ├── smoothing.py
│   │   ├── thresholds.json         # committed, calibrated from reference clips
│   │   └── features/
│   │       ├── __init__.py
│   │       ├── batsman.py
│   │       └── bowler.py           # v2
│   │
│   ├── analytics/           🆕
│   │   ├── __init__.py
│   │   ├── profile.py
│   │   ├── benchmarks.py
│   │   └── briefing.py
│   │
│   └── report/              🆕
│       ├── __init__.py
│       ├── pdf.py
│       ├── video_renderer.py
│       ├── tts.py
│       ├── subtitles.py
│       └── mux.py
│
├── scripts/
│   ├── train_yolo.py        ✅ existing
│   ├── validate_cric360.py  ✅ existing
│   ├── migrate_add_pose.py  🆕
│   ├── calibrate_pose_thresholds.py  🆕
│   ├── analyze_player.py    🆕  end-to-end: player → PDF
│   └── render_player_video.py  🆕  player → narrated MP4
│
├── data/
│   ├── raw_videos/          ✅ existing
│   ├── ball_clips/          ✅ existing
│   ├── pose/                🆕  per-clip MediaPipe JSON
│   ├── reference_clips/     🆕  YouTube-scraped technique clips for calibration
│   ├── rosters/             🆕  per-match YAML rosters
│   ├── reports/             🆕  generated PDFs
│   ├── reports/videos/      🆕  narrated MP4s
│   └── cricket_intelligence.db  (extended — see §4)
│
└── ui/app.py                ✅ extend with pose inspector + over-tagger
```

---

## 2. New Dependencies {#deps}

Add to `requirements.txt`:

```
# ===== Pose Estimation =====
mediapipe>=0.10.11        # landmark detection

# ===== Identity / OCR =====
easyocr>=1.7.1            # scoreboard OCR (batsman/bowler names, score)
PyYAML>=6.0.0             # roster files (already present, confirm version)

# ===== Narration (TTS) =====
edge-tts>=6.1.10          # free Microsoft voices, en-IN voices included

# ===== Reporting =====
reportlab>=4.1.0          # PDF generation
# Pillow already in requirements.txt — used for overlay text rendering

# ===== AI Briefing =====
anthropic>=0.25.0         # Claude API for narrative briefings (or reuse google-genai)
```

**Python compatibility:** current repo uses Python 3.14. Confirm MediaPipe + EasyOCR both support it; fall back to 3.12 if not (document in README).

**System deps:** `ffmpeg` already required. Add `espeak-ng` as a fallback local TTS if Edge TTS network access is unreliable.

---

## 3. Module Specs {#module-specs}

### 3.1 `src/pose/extractor.py` {#pose-extractor}

**Purpose:** run MediaPipe Pose on a clip and persist per-frame landmarks.

**Interface:**
```python
def extract_pose_from_clip(
    clip_path: str,
    output_path: str | None = None,
    model_complexity: int = 2,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> dict:
    """
    Returns:
      {
        "clip_path":  str,
        "fps":        float,
        "frame_count": int,
        "frames": [
          {"frame": int, "time_sec": float,
           "landmarks": [{"x": float, "y": float, "z": float, "v": float}, ...] | None}
        ],
        "mean_confidence": float,
        "detection_rate": float,   # fraction of frames with landmarks
      }
    """
```

**Guarantees:**
- Writes `data/pose/<clip_stem>.json` when `output_path` omitted.
- Returns `landmarks=None` for frames where MediaPipe fails. Never raises on per-frame failures.
- Logs via `rich.console` at start + end; no per-frame chatter.

**Performance target:** ≤ 2× real-time on a 2020+ Mac (M-series). A 6 s clip → ≤ 12 s compute.

**Caller:** `run_pipeline.py` (new `--pose` flag), `scripts/analyze_player.py`.

---

### 3.2 `src/pose/smoothing.py` {#pose-smoothing}

**Purpose:** reduce per-frame MediaPipe jitter before feature computation.

**Interface:**
```python
def smooth_landmarks(pose_data: dict, sigma: float = 1.0, window: int = 5) -> dict:
    """
    Apply a 1D Gaussian filter over each of the 33 landmarks' (x, y) across
    a 5-frame window. Frames with None landmarks are interpolated linearly
    from the nearest neighbours (capped at ±3 frames).

    Returns:
      Same shape as input `pose_data`, but with smoothed and imputed landmarks.
      Adds {"smoothed": True, "imputed_frame_count": int} to top-level dict.
    """
```

**Why it matters:** unsmoothed pose feeds produce oscillating head-offset values frame-to-frame. Visual overlays jitter badly; technique metrics become noisy. Smoothing is applied *before* feature engineering and *before* video rendering.

---

### 3.3 `src/pose/features/batsman.py` {#pose-features-batsman}

**Purpose:** compute measurable batsman technique features from a smoothed pose.

**Interface:**
```python
def compute_features(smoothed_pose_data: dict) -> dict:
    """
    Returns a flat dict suitable for storage alongside BallRecord:
      {
        "impact_frame":        int,        # heuristic: max wrist-velocity frame
        "impact_time_sec":     float,
        "stance_frame":        int,        # first frame where mean confidence > 0.6

        "head_lateral_offset": float,      # at impact, |nose_x - hip_midline_x|
        "head_over_ball":      bool,       # head_lateral_offset < thresholds.head_offset_target
        "stride_length_norm":  float,      # |L_ankle.x - R_ankle.x| / body_height at impact
        "stride_adequate":     bool,       # > thresholds.stride_target

        "stance_width_norm":   float,      # at stance_frame
        "shoulder_angle_deg":  float,      # at impact, angle of L_SH→R_SH line
        "backlift_direction":  str,        # categorical: straight | second_slip | third_slip | gully (heuristic from wrist trajectory pre-impact)
        "balance_at_impact":   float,      # 0–1 score from COM stability
        "weight_transfer":     float,      # 0–1 forward transfer at impact

        "mean_pose_confidence": float,
        "feature_confidence":   float,     # scalar 0–1 — compound of the above
      }
    Returns {"error": "no_pose"} if impact frame cannot be detected.
    """
```

**Key design rules:**
- **No hidden thresholds.** All cutoffs (e.g. `head_offset < 0.03`) live in `src/pose/thresholds.json` and are calibrated in Phase 1 week 2 via `scripts/calibrate_pose_thresholds.py`.
- **Confidence-gated.** If `mean_pose_confidence < 0.5`, return `{"error": "low_confidence"}`. Do not emit misleading metrics.
- **Camera-angle check.** Reject clips where `|shoulder_angle_deg| > 30°` (means batsman is facing the camera, not side-on) — return `{"error": "wrong_angle"}`.

**Stored in:** `balls.pose_features` JSON column (see §4).

**Bowler v2 module:** `src/pose/features/bowler.py` will add run-up rhythm (stride-length series), front-foot landing angle, hip–shoulder separation, arm angle at release, follow-through balance. Same interface contract; different field names.

---

### 3.4 `src/identity/scoreboard_ocr.py` {#scoreboard-ocr}

**Purpose:** read batsman + bowler + score from the scoreboard strip in pro/broadcast videos.

**Interface:**
```python
def detect_scoreboard_region(frame: np.ndarray) -> tuple[int,int,int,int] | None:
    """Heuristic bounding box for the persistent scoreboard strip.
    Typically bottom-left 30% of frame, consistent across frames."""

def read_scoreboard(frame: np.ndarray) -> dict:
    """
    Returns:
      {
        "batsman":  str | None,
        "bowler":   str | None,
        "score":    str | None,   # e.g. "182/4"
        "overs":    str | None,   # e.g. "34.2"
        "confidence": float,
      }
    """
```

**Implementation:**
- Use EasyOCR with English + optional Hindi.
- Only looks at scoreboard region (cuts OCR time 10×).
- Normalize player names: strip asterisks, handle initials (`V Kohli` → `V Kohli`, not `V. Kohli`).
- Cache per-video — if the batsman hasn't changed, don't re-run OCR every ball.

**Fallback:** returns `{"batsman": None, ...}` on failure. `tagger.py` then falls back to roster or manual tag.

---

### 3.5 `src/identity/roster.py` {#roster}

**Purpose:** load per-match rosters; treat them as the source of truth for academy matches where scoreboard OCR isn't reliable.

**Roster file format** — `data/rosters/<match-id>.yaml`:

```yaml
match_id: pilot_academy_a_u19_week12
date: 2026-05-10
teams:
  home:
    name: "Academy A U-19 Blue"
    players:
      - name: "Rahul Kumar"
        role: "batsman"
        jersey: 7
        handedness: "right"
      - name: "Arjun Mehta"
        role: "all-rounder"
        jersey: 12
        handedness: "right"
      # ...11 total
  away:
    name: "Academy A U-19 Red"
    players:
      - name: "Vivek Shah"
        role: "batsman"
        jersey: 3
        handedness: "left"
      # ...
batting_order_home: [7, 12, 4, 8, ...]   # by jersey
bowling_order_home: [12, 3, 9, ...]
```

**Interface:**
```python
class Roster:
    @classmethod
    def load(cls, match_id: str) -> "Roster": ...
    def find_by_jersey(self, jersey: int, team: str = "home") -> dict | None: ...
    def batter_for_innings(self, innings: int, wicket_number: int) -> str: ...
    def bowler_for_over(self, innings: int, over: int) -> str: ...
    def list_names(self) -> list[str]: ...
```

---

### 3.6 `src/identity/tagger.py` {#tagger}

**Purpose:** single entry point that combines OCR + roster + manual fallback.

**Interface:**
```python
def tag_ball(
    ball_record: BallRecord,
    video_path: str,
    roster: Roster | None = None,
) -> tuple[str | None, str | None, float]:
    """
    Strategy:
      1. If roster available → use roster.batter_for_innings + roster.bowler_for_over
      2. Else → sample frame at ball_record.clip_start_time → scoreboard OCR
      3. Else → return (None, None, 0.0) — review UI will prompt manual tag

    Returns: (batsman_name, bowler_name, confidence)
    """
```

**Integration:** wire into `run_pipeline.py` after Gemini extraction, before DB save.

---

### 3.7 `src/analytics/profile.py` {#analytics-profile}

**Purpose:** aggregate ball-level records + pose features into a per-player profile.

**Interface:**
```python
@dataclass
class PlayerProfile:
    player_id: str
    balls: int
    matches: int
    runs: int
    dismissals: int

    shot_distribution: dict[str, int]        # {"drive": 12, "cut": 4, ...}
    outcome_distribution: dict[str, int]
    by_length: dict[str, dict]               # "short" → {total, false_shot_rate, sr}
    by_bowler_type: dict[str, dict]          # "pace" vs "spin"

    technique: dict[str, float | None]       # avg_head_offset, avg_stride, fault_rates
    weakness: dict | None                    # {length, false_shot_pct, sample_size, root_cause_hint}
    strength: dict | None

    clip_ids_top_weakness: list[str]
    clip_ids_top_strength: list[str]

    as_of: datetime


def build_player_profile(
    balls: list[dict],                      # merged ball records + pose_features
    player_id: str,
    as_of: datetime | None = None,
) -> PlayerProfile: ...
```

**Rules:**
- Minimum balls for a meaningful profile: 20. Below that, return a profile flagged `insufficient_data=True`.
- Weakness detection = length bucket with highest `false_shot_rate` AND `n ≥ 3`.
- `root_cause_hint` is a short string derived from pose features: e.g. `"head_falling_across + short_stride"` if both fault rates > 0.5.

---

### 3.8 `src/analytics/benchmarks.py` {#analytics-benchmarks}

**Purpose:** compute per-academy / per-age-group benchmarks so individual player profiles can say "top quartile" or "bottom 10%."

**Interface:**
```python
@dataclass
class AcademyBenchmark:
    academy_id: str
    age_group: str | None       # "U-16", "U-19", etc.
    n_players: int
    n_balls: int

    medians:     dict[str, float]  # technique fields
    percentiles: dict[str, dict[str, float]]   # "head_offset" → {"p25": 0.03, "p50": 0.05, "p75": 0.08}
    shot_mix:    dict[str, float]

    computed_at: datetime


def benchmark_academy(
    academy_id: str, age_group: str | None = None
) -> AcademyBenchmark: ...
```

Use simple SQL `GROUP BY batsman_name` over existing records — no ML.

---

### 3.9 `src/analytics/briefing.py` {#analytics-briefing}

**Purpose:** turn `PlayerProfile + AcademyBenchmark + top-N raw descriptions` into a 400-word markdown briefing.

**Interface:**
```python
def generate_briefing(
    profile: PlayerProfile,
    benchmark: AcademyBenchmark | None = None,
    recent_raw_descriptions: list[str] | None = None,
    model: str = "claude-sonnet-4-6",   # or "gemini-2.5-flash"
    brevity: str = "standard",          # "standard" | "short" (for TTS)
) -> str: ...
```

**Prompt template** (maintained in `src/analytics/briefing_prompts.py`):
- Strict 5-section structure: session summary, top strength, top weakness, drill recommendation, what to re-measure
- Prose paragraphs, no bullets
- Plain language, no hedging, Indian academy context
- Target 380–420 words for `"standard"`, 70–90 words for `"short"`

**Output handling:** `briefing` may reference clip timestamps in the form `[clip:match_id_over_ball]` — downstream renderers resolve those to actual file paths.

---

### 3.10 `src/report/pdf.py` {#report-pdf}

**Purpose:** render a profile + briefing into a 1-page A4 PDF.

**Interface:**
```python
def render_report_pdf(
    profile: PlayerProfile,
    briefing_markdown: str,
    benchmark: AcademyBenchmark | None,
    clip_links: list[str],
    output_path: str,
    academy_logo_path: str | None = None,
) -> str:
    """Returns output_path. Writes 1-page A4 PDF via reportlab."""
```

Template: see [§9](#report-template).

---

### 3.11 `src/report/video_renderer.py` {#report-video}

**Purpose:** draw pose + labels on a ball clip, save as annotated MP4 ready for audio muxing.

**Interface:**
```python
def render_annotated_video(
    clip_path: str,
    pose_data: dict,                    # smoothed
    features: dict,                     # from batsman.py
    gemini_fields: dict,                # shot, line, length, outcome, etc.
    player_id: str,
    ball_idx: int,
    briefing_cues: list[str],           # rotating bottom banner text
    output_path: str,
    slowdown: float = 2.0,
    freeze_impact_ms: int = 800,
) -> str: ...
```

**Overlay spec:**

- **Persistent UI**
  - Top-left: `player_id` + `ball #` + `outcome`
  - Top-right: metric panel with live flags (head offset, stride, shoulder angle, contact quality)
  - Bottom-banner: rotates every 3 s through `briefing_cues`
- **On the skeleton**
  - Bones (white, 2px), joints (yellow, 4px)
  - Head circle — green if `head_over_ball`, red if fault
  - Hip midline reference (yellow, 1px)
  - Foot labels "F" (front foot) / "B" (back foot)
  - Wrist trail — last 10 frames (cyan→yellow gradient)
- **At impact frame** — freeze `freeze_impact_ms` + arrow callouts:
  - "head offset 0.058" with arrow to nose
  - "stride 0.28" with arrow between ankles
- **Post-processing** — ffmpeg `setpts={slowdown}*PTS`, `libx264 + yuv420p` for compatibility

**Fonts:** use Pillow for Unicode symbols (✓ ⚠). OpenCV `putText` only for ASCII panels.

---

### 3.12 `src/report/tts.py` {#report-tts}

**Purpose:** turn briefing text into narration MP3.

**Interface:**
```python
def generate_narration(
    text: str,
    output_path: str,
    voice: str = "en-IN-PrabhatNeural",
    rate: str = "-10%",
    save_srt: bool = True,
) -> str: ...
```

**Defaults:** Edge TTS, Indian-English male voice. Rate `-10%` for coach-pacing clarity. Produce `.srt` subtitles via SubMaker alongside the MP3.

Alternative voices for A/B testing: `en-IN-NeerjaNeural` (female), `en-IN-PrabhatNeural` (male). Add a config-driven switch so academies can pick.

---

### 3.13 `src/report/mux.py` {#report-mux} ✅ LANDED

**Purpose:** mux annotated video with narration. Option to stretch video to match audio length.

**Interface:**
```python
def mux_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    match_video_to_audio: bool = True,
    burn_subtitles: str | None = None,  # path to .srt — if set, burn in
) -> str: ...
```

Uses ffmpeg via subprocess. Outputs h264+aac MP4 (WhatsApp-compatible).

---

### 3.14 `src/intelligence/critique_prompts.py` {#critique-prompts} ✅ LANDED

**Purpose:** all prompts and the JSON schema for the few-shot Gemini critique. Kept separate from the critique module so prompts can be tuned without touching orchestration.

**Exports:**
- `CRITIQUE_SYSTEM_PROMPT` — system instruction (elite Indian academy coach persona)
- `CRITIQUE_PROMPT_TEMPLATE` — formatted with `n_references` + `shot_type`
- `CRITIQUE_JSON_SCHEMA` — strict response_schema with `identified_shot_type`, `shot_match_confidence`, `overall_quality_rating`, `deviations[]`, `drill_recommendations[]`, `encouragement`
- `get_critique_prompt(n_references, shot_type) → str`
- `get_critique_system_prompt() → str`

**Schema design rules:**
- `deviations[].aspect` is free-text (head_position, bat_swing_path, etc.) so the LLM picks the natural label per case
- `severity` and `estimated_correction_effort` are enum-constrained
- `encouragement` is required so no critique reads as purely negative
- All required keys are at the top of the response — easier debugging

---

### 3.15 `src/intelligence/few_shot_critique.py` {#few-shot-critique} ✅ LANDED — extended with `coaching_context`

**Purpose:** compare a student's shot clip against N reference clips of pro batsmen in a single Gemini call, optionally with extracted coaching corpus knowledge injected. Returns structured JSON.

**Interface:**
```python
def critique_against_references(
    student_clip: str,
    reference_clips: list[dict],            # [{"path": str, "player": str}]
    shot_type: str,                         # "cover_drive", "pull", "defend", etc.
    coaching_context: list[dict] | None = None,  # NEW — list of coaching extracts
    model: str = "gemini-2.5-flash",
    cleanup_uploads: bool = True,
) -> dict:
    """Returns JSON matching CRITIQUE_JSON_SCHEMA."""
```

**New: `coaching_context` parameter.** Each item is the JSON output of `coaching_extractor.extract_coaching_points()`. When provided, each is rendered into a `COACHING CONTEXT N of M` text block via `coaching_context_block()` and injected into the prompt **before** the visual references, followed by a brief framing instruction ("use the coaching guidance above to inform what 'ideal' looks like..."). The result: the critique's deviations cite real coach language, drills, and common-mistake phrasings rather than generic LLM advice.

**Behavior:**
1. Validates inputs (paths exist, GEMINI_API_KEY set, ≥ 1 reference)
2. Uploads each reference + student via Gemini Files API; waits for `state == "PROCESSING"` to clear
3. Builds a single `Content` with parts in order: REFERENCE 1 label → ref 1 video → ... → STUDENT label → student video → critique prompt
4. Calls `generate_content` with `response_schema=CRITIQUE_JSON_SCHEMA`, `temperature=0.2`
5. Parses JSON, deletes uploaded files, returns dict

**Cost:** ~₹3–5 per critique with 2 references + 1 student at ~5 s each (Gemini 2.5 Flash).

**Failure modes handled:**
- Missing API key → `ValueError`
- Missing file → `FileNotFoundError`
- Failed upload → `RuntimeError`
- Invalid JSON response → re-raises `json.JSONDecodeError` after logging the first 500 chars

**Caller:** `scripts/critique_student_clip.py` (CLI). Future: hybrid briefing module will call this and merge with pose features.

---

### 3.16 `scripts/critique_student_clip.py` {#critique-cli} ✅ LANDED — extended with `--coaching-keys`

CLI wrapper around `critique_against_references()` with human-readable terminal summary.

**Usage:**
```bash
python scripts/critique_student_clip.py \
    --clip data/raw_videos/student_drive.mp4 \
    --shot-type cover_drive \
    --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \
                 "data/reference_library/videos/cover-drive/kohli-cover-2.mp4:Virat Kohli" \
    --coaching-keys "coach-kohli-cover-hindi,kohli-explains-cover-1" \
    --out data/reports/student_critique.json
```

**Reference format:** `path` or `path:Player Name`. Player name flows into the prompt as `"REFERENCE 1 — ideal cover_drive by Virat Kohli:"`.

**Coaching keys (`--coaching-keys`):** comma-separated keys looked up in `data/coaching_corpus/index.yaml`. Each match's JSON file is parsed and passed to `critique_against_references()` as a `coaching_context` block. Missing or unparseable keys log a warning and are skipped — they don't fail the critique.

**Outputs:**
- JSON file at `--out` (full critique)
- Coloured terminal summary: rating + numbered deviations + drill list (suppressible with `--no-summary`)

Runs in main `venv` (no MediaPipe).

---

### 3.17 `src/intelligence/coaching_prompts.py` {#coaching-prompts} ✅ LANDED

**Purpose:** prompts and JSON schema for extracting structured coaching guidance from expert tutorial videos. Different from `critique_prompts.py` — those compare visuals, these extract teachable knowledge from spoken explanation.

**Exports:**
- `COACHING_EXTRACT_SYSTEM_PROMPT` — system instruction (expert cricket coach + translator persona, handles Hindi/English/Hinglish)
- `COACHING_EXTRACT_PROMPT_TEMPLATE` — formatted with `subject_hint`
- `COACHING_EXTRACT_JSON_SCHEMA` — strict response schema:
  - `shot_or_skill` (e.g. `cover_drive`)
  - `reference_player` (the player the tutorial cites)
  - `language_detected`
  - `key_technique_points[]` — each `{point, aspect}` where `aspect` is a body-region enum
  - `drills[]` — each `{drill_name, equipment, duration_minutes, addresses_aspect}`
  - `common_mistakes[]` — string list
  - `coaching_cues[]` — short verbal prompts coaches use
  - `ideal_outcome`
  - `extraction_confidence` (0–1)
- `get_coaching_system_prompt() → str`
- `get_coaching_extract_prompt(subject_hint) → str`

**Schema design rules:**
- `aspect` is enum-constrained to keep cross-tutorial joins clean (head, stance, grip, backlift, front_foot, back_foot, bat_swing, weight_transfer, balance, follow_through, eye_line, shoulder, hip, other)
- `coaching_cues` are quoted directly (Hindi phrases preserved with English translation in parens) so the critique can echo coach voice authentically

---

### 3.18 `src/intelligence/coaching_extractor.py` {#coaching-extractor} ✅ LANDED

**Purpose:** extract structured coaching knowledge from a tutorial video.

**Interface:**
```python
def extract_coaching_points(
    video_path: str,
    subject_hint: str = "cricket batting technique",
    model: str = "gemini-2.5-flash",
    cleanup_upload: bool = True,
) -> dict:
    """Returns dict matching COACHING_EXTRACT_JSON_SCHEMA."""

def coaching_context_block(coaching: dict) -> str:
    """Render an extracted coaching dict into a compact text block for
    prompt injection into critique_against_references()."""
```

**Behavior:** uploads the video to Gemini Files API, waits for processing, calls `generate_content` with the structured-output schema, returns parsed JSON.

**Cost estimate:** ~₹3–8 per coaching extraction depending on tutorial length (a 6-min Hindi tutorial costs ~₹6).

**Caller:** `scripts/extract_coaching_video.py` (CLI) and downstream — `critique_against_references()` accepts the extracted dict directly via its `coaching_context` argument.

---

### 3.19 `scripts/extract_coaching_video.py` {#extract-coaching-cli} ✅ LANDED

CLI wrapper around `extract_coaching_points()`. Saves JSON to `data/coaching_corpus/<key>.json` and upserts an entry into `data/coaching_corpus/index.yaml`.

**Usage:**
```bash
python scripts/extract_coaching_video.py \
    --video data/raw_videos/coach-kohli-cover-hindi.mp4 \
    --key coach-kohli-cover-hindi \
    --subject "Virat Kohli cover drive technique — Hindi tutorial" \
    --shot-type cover_drive \
    --player "Virat Kohli" \
    --source-url "https://youtu.be/TetcPMFjSrE"
```

**Outputs:**
- `data/coaching_corpus/<key>.json` (full extracted knowledge)
- Updated `data/coaching_corpus/index.yaml` (manifest)
- Coloured terminal summary

---

### 3.20 `scripts/add_reference_clip.py` {#add-reference-clip} ✅ LANDED

**Purpose:** one-shot CLI to add a YouTube clip to the reference shot library — downloads via `yt-dlp` directly into `data/reference_library/videos/<shot-slug>/<key>.mp4`, optionally runs pose validation, upserts into the manifest.

**Usage:**
```bash
# Download only
python scripts/add_reference_clip.py \
    --url "https://youtube.com/shorts/EXAMPLE" \
    --key kohli-cover-3 \
    --shot-type cover_drive \
    --player "Virat Kohli"

# Download + validate via pose (auto-tier)
source venv312/bin/activate
python scripts/add_reference_clip.py \
    --url "..." --key kohli-cover-3 --shot-type cover_drive \
    --player "Virat Kohli" --validate
```

**Validation tier logic:**
- `gold` — all 6 gates pass (detection_rate ≥ 0.85, mean_confidence ≥ 0.70, side_on_camera, head_over_ball, stride_adequate, gemini_shot_match)
- `silver` — 4 of 6
- `bronze` — 1–3
- `pending` — `--validate` not passed

Idempotent — won't re-download if file exists (use `--force-overwrite` to redo).

---

### 3.21 `scripts/render_side_by_side.py` {#side-by-side} ✅ LANDED

**Purpose:** stack two videos via ffmpeg `hstack` / `vstack` with labels burned in. No pose, no narration, no impact-frame alignment — the visual MVP for "show student vs Kohli."

**Interface (Python):**
```python
def render(
    left: Path, right: Path, out: Path,
    layout: str = "hstack",        # "hstack" | "vstack"
    target_size: int = 720,
    left_label: str = "LEFT",
    right_label: str = "RIGHT",
    slowdown: float = 1.0,
    shortest: bool = True,
) -> Path: ...
```

**Notes:**
- ffmpeg `drawtext` filter burns the labels in (white-on-translucent-black box, top-left of each panel)
- `slowdown` applied via `setpts={slowdown}*PTS`
- `shortest=True` clips to the shorter input duration (cleaner ending; pass `--no-shortest` for full duration of the longer)
- Drops audio (`-an`) — caller can mux narration later via `src/report/mux.py`

**Future:** `src/report/comparison.py` (Part C) will add pose overlay on both panels + impact-frame time alignment + single-narration mux for the coach-grade version.

---

### 3.22a `src/analytics/briefing.py` {#briefing-assembler} ✅ LANDED

**Purpose:** assemble all four engines' outputs into a single `PlayerBriefing` dataclass that the PDF renderer consumes. Pure data-shaping layer — no I/O.

**Interface:**
```python
@dataclass
class PlayerBriefing:
    # Header
    player_name: str
    shot_type: str
    generated_at: datetime
    clip_path: str
    ball_id: str | None
    academy: str | None

    # Source-data raw blobs
    gemini: dict | None              # raw Gemini extraction
    pose_features: dict | None       # raw batsman feature dict
    critique: dict | None            # raw critique JSON

    # Derived structured content
    metrics: list[TechniqueMetric]   # name, value, target, flag
    deviations: list[Deviation]      # aspect, observed, ideal, severity, effort
    drills: list[Drill]              # name, duration, frequency, addresses, source
    coaching_cues: list[str]
    common_mistakes_quoted: list[str]
    encouragement: str | None
    overall_rating: str | None       # close_to_ideal | needs_minor_work | needs_major_work

    # Provenance
    reference_clips: list[dict]
    coaching_keys_used: list[str]


def assemble_briefing(
    player_name: str,
    shot_type: str,
    clip_path: str,
    gemini: dict | None = None,
    pose_features: dict | None = None,
    critique: dict | None = None,
    coaching_context: list[dict] | None = None,
    reference_clips: list[dict] | None = None,
    coaching_keys: list[str] | None = None,
    ball_id: str | None = None,
    academy: str | None = None,
) -> PlayerBriefing: ...
```

**Threshold rules** (currently inline; will move to `src/pose/thresholds.json` once calibrated):
- `head_lateral_offset` < 0.03 → ✓
- `stride_length_norm` > 0.35 → ✓

**Drill deduplication:** drills from `critique.drill_recommendations` come first; drills from `coaching_corpus[*].drills` are appended only if their lower-cased name isn't already present. Each drill has a `source` field (`"critique"` | `"coaching_corpus"`) shown in the PDF as a small tag.

**No DB I/O** — caller passes already-extracted dicts.

---

### 3.22b `src/report/pdf.py` {#briefing-pdf} ✅ LANDED

**Purpose:** render a `PlayerBriefing` to a 1-page A4 PDF using reportlab Platypus.

**Interface:**
```python
def render_briefing_pdf(briefing: PlayerBriefing, output_path: str) -> str: ...
```

**Page layout (top → bottom):**
1. Header — bold player name + shot type, muted subtitle (date · academy · ball id · clip name), thin rule
2. Technique metrics table (4 rows max) — Metric | Value | Target | Flag (✓ / ⚠ / —)
3. Delivery & shot — two compressed lines from Gemini fields + italic raw_description quote
4. Critique table — # | Aspect | Observed | Ideal | Sev (severity colour-coded)
5. Recommended drills — numbered list with duration · frequency · aspect tags + source tag (critique/coaching_corpus)
6. Coaching cues — italic quoted lines from coaching corpus (capped at 5)
7. Common mistakes — bullet list (capped at 4)
8. Encouragement — short italic paragraph
9. Footer — generated timestamp + coach signature line

**Design rules:**
- Color used as a SECONDARY signal — every state also has a text/symbol representation so the PDF prints cleanly in B&W
- Severity colours match flag colours (✓ green, ⚠ amber, ✗ red)
- Page margins 12-14mm — fits ~A4 sheet with comfortable density
- Built with `SimpleDocTemplate` + `Platypus` (Paragraph, Table, Spacer, HRFlowable) — no PDF templates, no external assets needed

**Graceful empty states:** any section whose source data is absent renders a one-line "not available" muted note instead of crashing or being omitted.

---

### 3.22c `scripts/render_player_briefing.py` {#briefing-cli} ✅ LANDED

End-to-end orchestrator that runs (or skips) each engine, assembles the briefing, and renders the PDF.

**Pipeline (5 steps, each with graceful degradation):**
1. Load coaching context from `data/coaching_corpus/index.yaml`
2. Run Gemini extraction (skippable with `--skip-gemini`)
3. Run pose pipeline — MediaPipe + smoothing + features (skippable with `--skip-pose`)
4. Run few-shot critique if `--references` provided
5. Assemble `PlayerBriefing` + render PDF

**Failure handling:** any step that fails (missing dependency, bad clip, Gemini error) logs a yellow warning and the pipeline continues with that section blank. Only a missing student clip or missing reference clip aborts.

**venv split awareness:** `--skip-pose` lets the script run in main `venv` (no MediaPipe). With pose enabled, must run in `venv312`.

**Usage:**
```bash
python scripts/render_player_briefing.py \
    --clip data/raw_videos/student_drive.mp4 \
    --player "Rahul Kumar" \
    --shot-type cover_drive \
    --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \
    --coaching-keys "coach-kohli-cover-hindi" \
    --academy "Demo Academy U-19" \
    --out data/reports/rahul_briefing.pdf
```

---

### 3.22 `src/ingestion/downloader.py` {#downloader-extended} ✅ EXTENDED

CLI now supports two new flags:

| Flag | Values | Meaning |
|---|---|---|
| `--target` | `raw` (default) / `reference-library` / `coaching-corpus` | Which storage area to save into |
| `--shot-type` | e.g. `cover_drive`, `pull` | Required when `--target=reference-library`; determines the subdir slug |

**Examples:**
```bash
# Default (raw_videos/)
python -m src.ingestion.downloader --url URL --match-id my-match

# Save to reference library subdir
python -m src.ingestion.downloader --url URL --match-id kohli-cover-1 \
    --target reference-library --shot-type cover_drive
# → data/reference_library/videos/cover-drive/kohli-cover-1.mp4
```

`--shot-type cover_drive` becomes the slug `cover-drive` (underscore → hyphen) for the directory name. Schema enums use underscores; directory paths use hyphens.

For reference clips, prefer `scripts/add_reference_clip.py` — it does the download AND updates the manifest. The downloader's `--target reference-library` is for cases where you want to download but defer manifest registration.

---

## 4. Schema Additions {#schema}

### 4.−1 Reference library manifest — ✅ LANDED

`data/reference_library/index.yaml` is the single source of truth for which reference clips exist, their quality, and which shot they're canonical for.

**Storage layout (organized by shot type):**

```
data/reference_library/
├── index.yaml
└── videos/
    ├── cover-drive/
    │   ├── kohli-cover-1.mp4
    │   ├── kohli-cover-1.pose.json         # alongside the video
    │   └── kohli-cover-1.features.json
    ├── pull/
    ├── front-foot-defence/
    └── ...                                 # one subdir per shot
```

Pre-created subdirs: `cover-drive`, `pull`, `hook`, `cut`, `late-cut`, `straight-drive`, `on-drive`, `off-drive`, `front-foot-defence`, `back-foot-defence`, `sweep`, `slog-sweep`, `reverse-sweep`, `helicopter`, `leg-glance`, `flick`, `leave`. Add more as needed (any underscore in `--shot-type` becomes a hyphen in the slug — e.g. `cover_drive` → `cover-drive`).

**Schema** (per the file's own header comments):
```yaml
clips:
  - key:           kohli-cover-1               # unique slug
    shot_type:     drive                       # matches schema.ShotType enum
    shot_subtype:  cover_drive                 # finer label, free-form
    player:        Virat Kohli
    handedness:    right
    source_url:    https://youtube.com/...
    clip_path:     data/reference_library/videos/cover-drive/kohli-cover-1.mp4
    pose_path:     data/reference_library/videos/cover-drive/kohli-cover-1.pose.json
    features_path: data/reference_library/videos/cover-drive/kohli-cover-1.features.json
    quality_rating: gold | silver | bronze | pending
    validation:
      detection_rate:    0.94
      mean_confidence:   0.81
      side_on_camera:    true
      head_over_ball:    true
      stride_adequate:   true
      gemini_shot_match: true
    notes: "..."
```

**Adding clips — single command:** `scripts/add_reference_clip.py` downloads via `yt-dlp` directly into `videos/<shot-slug>/<key>.mp4` (skipping `raw_videos/`), optionally runs MediaPipe pose if `--validate` is passed, computes the validation gates, and upserts the entry into `index.yaml` with the right quality rating.

**Promotion gates** (manual for now; `scripts/promote_to_reference.py` will automate later):

| Tier | Gates |
|---|---|
| `gold` | All 6 validation fields true; `detection_rate ≥ 0.85`, `mean_confidence ≥ 0.70` |
| `silver` | 4 of 6 |
| `bronze` | 1–3 |
| `pending` | not yet validated |

**Used by:**
- `src/intelligence/few_shot_critique.py` (selection of references for a given `shot_type`)
- `src/report/comparison.py` (planned, pose-based side-by-side)
- `src/analytics/briefing.py` (planned, narrative cite — "play it like Kohli")

### 4.−2 Coaching corpus manifest — ✅ LANDED

`data/coaching_corpus/index.yaml` is the single source of truth for which coaching tutorials have been extracted, what shot they cover, and where their JSON lives.

**Schema** (auto-populated by `scripts/extract_coaching_video.py`):

```yaml
entries:
  - key:        coach-kohli-cover-hindi
    shot_type:  cover_drive            # the shot/skill the tutorial teaches
    player:     Virat Kohli            # player cited in the tutorial (may be empty)
    language:   hindi                  # detected — hindi | english | hinglish | ...
    source_url: https://youtu.be/...
    video_path: data/raw_videos/coach-kohli-cover-hindi.mp4
    json_path:  data/coaching_corpus/coach-kohli-cover-hindi.json
    confidence: 0.95                   # extraction_confidence (0-1)
    n_points:   8                      # # of key_technique_points extracted
    n_drills:   3
    n_mistakes: 4
    n_cues:     5
```

**Per-entry JSON file** matches `COACHING_EXTRACT_JSON_SCHEMA` (see §3.17).

**Used by:**
- `src/intelligence/few_shot_critique.py` — accepts a list of these JSONs as `coaching_context` and renders each via `coaching_context_block()` into the critique prompt
- `scripts/critique_student_clip.py --coaching-keys k1,k2,...` — looks up keys in this manifest and passes the parsed JSONs to the critique
- Future `src/analytics/briefing.py` — will cite drills + cues directly in PDF briefings

**Dual-purpose Short pattern:** a single Short (e.g. *"Kohli explains cover drive to kids"*) can have entries in BOTH `data/reference_library/index.yaml` (for visual comparison) AND `data/coaching_corpus/index.yaml` (for spoken-coaching context). Same `key`, same MP4 file, indexed twice — workflow is `add_reference_clip.py` then `extract_coaching_video.py` on the same video path.

### 4.0 Delivery sub-type fields — ✅ LANDED

Already added to `BallRecord` + `BallDBRecord` + `GEMINI_JSON_SCHEMA` + prompts + normalizer.
Existing DB migrated via `scripts/migrate_delivery_subtype.py`.

| Field | Enum | Notes |
|---|---|---|
| `swing_direction` | `SwingDirection` (`in_swing` / `out_swing` / `none` / `unknown`) | Pace only; relative to RH batsman. |
| `swing_type` | `SwingType` (`conventional` / `late` / `reverse` / `none` / `unknown`) | Pace only. |
| `spin_direction` | `SpinDirection` (`off_break` / `leg_break` / `googly` / `arm_ball` / `doosra` / `carrom` / `top_spin` / `slider` / `none` / `unknown`) | Spin only. |
| `ball_age_phase` | `BallAgePhase` (`new_ball` / `old` / `reverse_window` / `unknown`) | Either. |

Confidence additions: `confidence.swing_direction`, `confidence.spin_direction`, `confidence.swing_type` (each `0.0–1.0`, default `0.0`). Analytics layer must gate by a minimum threshold before reporting these in briefings — Gemini is often uncertain at this granularity.

Pace/spin consistency is enforced in `BallRecordValidator`:
- `pace` bowler with a non-`unknown` `spin_direction` → cleared to `none` + warning
- `spin` bowler with any non-`unknown` swing field → cleared to `none` + warning

Raw-description fallback normalization in `normalizer.py` handles coach-speak:
`"outswinger"`, `"arm ball"`, `"reverse swing"`, `"leg-break"`, etc. → correct enum.

**Impact on analytics.** Cross-tab becomes `GROUP BY (length, variation, movement, swing_direction, spin_direction)`. A batter's weakness against "in-swinging yorker" or "off-break on leg stump" is now a queryable combination, not just a text guess from `raw_description`.

### 4.1 `balls` table — add one JSON column

```sql
ALTER TABLE balls ADD COLUMN pose_features JSON;
```

Contents: dict produced by `src/pose/features/batsman.py::compute_features()`. Keep as JSON to stay forward-compatible with bowler/keeper feature sets.

### 4.2 New table — `ground_truth`

```sql
CREATE TABLE ground_truth (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ball_id        TEXT NOT NULL REFERENCES balls(ball_id),
    field_name     TEXT NOT NULL,       -- 'line', 'head_over_ball', etc.
    old_value      TEXT,
    new_value      TEXT NOT NULL,
    coach_id       TEXT NOT NULL,       -- from auth context or default 'system'
    timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP,
    pose_features_snapshot JSON,        -- full pose_features at correction time
    source         TEXT DEFAULT 'ui'    -- 'ui' | 'api' | 'batch_import'
);
CREATE INDEX idx_ground_truth_ball  ON ground_truth(ball_id);
CREATE INDEX idx_ground_truth_field ON ground_truth(field_name);
```

**Every Streamlit field change + every API PUT writes a row.** This is the proprietary dataset.

### 4.3 New table — `player_profile_cache`

```sql
CREATE TABLE player_profile_cache (
    player_id    TEXT NOT NULL,
    academy_id   TEXT NOT NULL,
    as_of        DATETIME DEFAULT CURRENT_TIMESTAMP,
    profile_json JSON NOT NULL,
    PRIMARY KEY (player_id, academy_id, as_of)
);
```

Profiles are expensive to recompute; cache with a TTL (`as_of + 6 hours`).

### 4.4 New table — `academy_benchmarks`

```sql
CREATE TABLE academy_benchmarks (
    academy_id   TEXT NOT NULL,
    age_group    TEXT,
    computed_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    benchmark_json JSON NOT NULL,
    PRIMARY KEY (academy_id, age_group, computed_at)
);
```

Recompute weekly via a cron script (out of scope for the 6-week plan — manual trigger is fine).

---

## 5. DB Migrations {#migrations}

`scripts/migrate_add_pose.py` — idempotent migration that adds the new columns and tables.

```python
# scripts/migrate_add_pose.py
from sqlalchemy import create_engine, text
import os

def migrate():
    url = os.getenv("DATABASE_URL", "sqlite:///./data/cricket_intelligence.db")
    engine = create_engine(url)
    with engine.begin() as conn:
        # idempotent guards
        conn.execute(text("PRAGMA foreign_keys = ON"))
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(balls)")).fetchall()}
        if "pose_features" not in cols:
            conn.execute(text("ALTER TABLE balls ADD COLUMN pose_features JSON"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ground_truth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ball_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                coach_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                pose_features_snapshot JSON,
                source TEXT DEFAULT 'ui'
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ground_truth_ball ON ground_truth(ball_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ground_truth_field ON ground_truth(field_name)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS player_profile_cache (
                player_id TEXT NOT NULL,
                academy_id TEXT NOT NULL,
                as_of DATETIME DEFAULT CURRENT_TIMESTAMP,
                profile_json JSON NOT NULL,
                PRIMARY KEY (player_id, academy_id, as_of)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS academy_benchmarks (
                academy_id TEXT NOT NULL,
                age_group TEXT,
                computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                benchmark_json JSON NOT NULL,
                PRIMARY KEY (academy_id, age_group, computed_at)
            )
        """))

if __name__ == "__main__":
    migrate()
    print("✓ migration complete")
```

Run once per environment: `python scripts/migrate_add_pose.py`.

---

## 6. CLI Integration with `run_pipeline.py` {#cli}

Add these flags to `run_pipeline.py`:

| Flag | Default | Purpose |
|---|---|---|
| `--pose` | false | Run pose extraction on each clip; populate `balls.pose_features` |
| `--roster` | `None` | Path to roster YAML; enables identity tagging |
| `--briefing` | false | After storage, generate per-player briefing PDFs for all batsmen with ≥ 20 balls |
| `--render-videos` | false | Also generate narrated MP4s per player |
| `--academy-id` | `default` | Academy context for benchmarks + report naming |

Pipeline order with all flags on:

```
Step 1  Ingestion        [existing]
Step 2  Segmentation     [existing]  (skipped if --batch-mode)
Step 2.5 CV detection    [existing]  (if Roboflow key present)
Step 3  Gemini extraction [existing]
Step 3.5 Identity tagging [NEW]     — scoreboard OCR + roster
Step 3.6 Pose extraction  [NEW]     — if --pose
Step 3.7 Feature compute  [NEW]     — if --pose
Step 4  Validation        [existing]
Step 5  Storage           [existing]
Step 6  Profile build     [NEW]     — if --briefing
Step 7  Briefing + PDF    [NEW]     — if --briefing
Step 8  Video render      [NEW]     — if --render-videos
Step 9  Summary + exit    [existing]
```

Keep each new step behind a flag — the existing path must still work untouched.

---

## 7. Camera Setup Spec {#camera-spec}

### Tier A — MVP (ship with the product)

```
Camera:        Any phone with 1080p / 30 fps+ recording
Mount:         Tripod + phone mount, chest-height adjustable (1.3–1.5 m)
Position:      3–5 m behind batsman, 45° to the crease line
               (between square leg and fine leg, NOT straight-square)
Orientation:   Landscape, orientation-locked
Frame coverage: Batsman occupies ≥ 40% of vertical frame
               Pitch strip visible; bowler run-up not required
Lighting:      Daylight or academy floodlights; avoid backlight
Audio:         Disabled / muted (narration will be added later)
Recording time: Continuous through the net session; no start/stop per ball
```

### Validation checklist (before every session)

1. Frame batsman standing at the crease — should fill ~40% vertical
2. Check tripod is stable — a 5-second hand-check: does the frame drift?
3. Capture 2 test deliveries, play back for 10 s, confirm batsman visible
4. Lock the focus/exposure if the phone supports it

### Tier B — Recommended

Add a second phone behind the bowler's arm (5–8 m back, 2 m height). Same settings. Enables bowler pose analysis (v2) and tighter line/length.

### Tier C — Full kit

Add a 45° elevated camera for pitch-map homography. Defer until a state-association customer asks for it.

### Kit hardware shipped

| Item | Spec | Approx cost (INR) |
|---|---|---|
| Tripod | 1.5 m collapsible aluminium | 600 |
| Phone mount (swivel + clamp) | Fits 60–90 mm phones | 200 |
| SD card | 64 GB, Class 10 | 400 |
| Laminated placement guide | A4, 2-sided, diagrams + checklist | 50 |
| Branded sleeve / carry pouch | Optional | 300 |

Total BOM: ₹1,500–2,000. Ship with first pilot visit; amortize in first-year subscription.

---

## 8. Threshold Calibration Guide {#thresholds}

`src/pose/thresholds.json` is a committed file. It is the single place all feature cutoffs live.

### 8.1 What thresholds look like

```json
{
  "batsman": {
    "head_offset_target":   0.03,
    "head_offset_p25":      0.02,
    "head_offset_p75":      0.05,
    "stride_norm_target":   0.35,
    "stride_norm_p25":      0.28,
    "stride_norm_p75":      0.42,
    "shoulder_angle_max":   30.0,
    "mean_conf_min":        0.50,
    "calibrated_on":        "2026-04-30",
    "calibration_source":   "300 youtube reference clips, U-19 to pro level",
    "n_samples":            300
  }
}
```

### 8.2 `scripts/calibrate_pose_thresholds.py`

```python
# Input: directory of reference pose JSONs + metadata (player level)
# Process: compute features for each; take P25/P50/P75 of each metric on "clean technique" subset
# Output: thresholds.json with calibrated values + calibration_source
```

### 8.3 When to re-calibrate

- End of Phase 1 week 2 (initial calibration, on YouTube reference clips)
- End of Phase 5 week 6 (re-calibrate on first 2,000 academy pilot balls)
- Every +500 ground-truth corrections: check for drift, diff and commit

### 8.4 Age-group overrides

U-12 batters have different body proportions. Add `thresholds.u12`, `thresholds.u14`, etc. keys when academies start asking.

---

## 9. Report Template {#report-template}

**PDF must be 1 page A4.** Printable in black and white (no color-only signals). ~90 second read for the coach.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 [ACADEMY LOGO]   PLAYER NAME   AGE-GROUP   [ACADEMY]
 Week of YYYY-MM-DD — YYYY-MM-DD
 Balls analyzed: N   Matches: M   Net sessions: P
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 TECHNIQUE SNAPSHOT          This wk   Last wk   Target
   Head-over-ball at impact   6.2°     9.1°     <5°    ✓
   Front-foot stride (× h)    0.34     0.31     0.40   ⚠
   Backlift direction         3rd slip 3rd slip 2nd    ⚠
   Balance at impact          82%      79%      85%    ✓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 TOP WEAKNESS THIS WEEK
   Short balls outside off
   28 balls │ 11 false shots (39%) │ 2 dismissals
   Root cause: head falling across + late back-foot press
   Drill rec: cross-line roller-ball practice 15 min × 4 days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 TOP STRENGTH
   Front-foot drive to full balls
   21 balls │ 0 false shots │ SR 142
   Technique: clean, no fault flags

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 VS ACADEMY [AGE-GROUP] MEDIAN (n = N players)
   False-shot %:   18%   (median 22%)   top quartile
   Technique score: 71   (median 65)    top quartile
   Short ball %:   39%   (median 28%)   bottom quartile

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 CLIPS TO REVIEW  (video links)
   1. Match 3, over 8.2  — dismissal, head across line
   2. Match 3, over 12.4 — edge, same fault
   3. Net 2, ball 14     — short-ball fault, slow motion
   4. Match 2, over 5.1  — clean cover drive (reference)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Generated YYYY-MM-DD │ Reviewed by coach: ___________
```

Implementation notes:
- Use `reportlab.platypus` with `Paragraph`, `Table`, `Spacer`
- Monospace font for the tables (Courier). Sans-serif for headers.
- Symbols `✓ ⚠ ✗` render correctly in reportlab with DejaVu Sans — register it.
- Include QR code linking to the video folder (academies love this).

---

## 10. Flywheel Hooks in Review UI {#flywheel-hooks}

Every state-changing action in `ui/app.py` writes to `ground_truth`. Concrete insertion points:

### 10.1 Ball field edits

Existing code path: Streamlit dropdown for `line`, `length`, `shot_type`, `outcome`. On change, before `db.update_ball_review()`:

```python
for field, new_val in updates.items():
    old_val = getattr(current_ball, field)
    if old_val != new_val:
        db.log_ground_truth(
            ball_id=current_ball.ball_id,
            field_name=field,
            old_value=str(old_val),
            new_value=str(new_val),
            coach_id=st.session_state.get("coach_id", "anonymous"),
            pose_features_snapshot=current_ball.pose_features,
            source="ui",
        )
```

### 10.2 Pose inspector confirmations

New UI panel: show overlay video + 5 technique flag booleans (`head_over_ball`, `stride_adequate`, `balance_ok`, `backlift_straight`, `weight_forward`). Each has "✓ correct" / "✗ fix" / "skip" buttons. Each click logs.

### 10.3 Player-tagging corrections

When coach corrects `batsman_name` or `bowler_name` in the over-tagger panel, log it — these corrections train the scoreboard-OCR fallback logic.

### 10.4 Label-volume report

Add a small admin panel:
```
This week:    247 corrections across 3 academies
Last 30 days: 1,842 corrections
Top-corrected field: shot_type (312 corrections)
```

This is your internal dashboard. Put the link in the weekly metrics email.

---

## 11. Testing & Validation {#testing}

**Explicit non-goal:** full unit-test coverage. This is pilot-stage code.

**What must be tested:**

1. **Schema migrations** — `scripts/migrate_add_pose.py` runs twice without error (idempotency)
2. **Pose extractor** — runs on 5 known side-on clips without crashing; `detection_rate > 0.8` on all
3. **Feature computer** — runs on all 5 clips; returns numeric values (not errors) for at least 4 of 5
4. **Profile builder** — handles edge cases: 0 balls, 1 ball, all-unknown balls, missing pose features
5. **Briefing generator** — end-to-end on mock profile; asserts 300–500 word output, 5 required section keywords present
6. **Video renderer** — produces a valid MP4 that plays in QuickTime + VLC
7. **TTS** — produces a non-empty MP3; duration within ±20% of expected (word_count / 150 wpm)
8. **Mux** — final MP4 plays on WhatsApp web preview (manual check, documented per release)

**Integration test:** one scripted end-to-end run per week of Phase 1–5.

```bash
# scripts/smoke_test.sh
python scripts/migrate_add_pose.py
python run_pipeline.py --video data/raw_videos/smoke.mp4 \
    --match-id smoke --pose --roster data/rosters/smoke.yaml \
    --briefing --render-videos --academy-id pilot_a
ls -la data/reports/pilot_a/*.pdf
ls -la data/reports/videos/pilot_a/*.mp4
```

Pass criteria: exits 0, produces ≥ 1 PDF, ≥ 1 MP4.

---

**See also:** [ARCHITECTURE.md](./ARCHITECTURE.md) for the layer model · [PLAN.md](./PLAN.md) for the 6-week execution plan · [DIAGRAMS.md](./DIAGRAMS.md) for sequence + data-flow diagrams.
