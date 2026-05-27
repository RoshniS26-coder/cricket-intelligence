"""
Benchmark configuration — models, fields to score, ground truth path.
"""
from pathlib import Path

# Ground truth — path to the synthesized JSON (ball records with all fields)
GROUND_TRUTH_PATH = Path("data/IndvsEng_full_match_correct.json")

# Fields to benchmark accuracy on (subset of BallRecord — vision-extractable only)
BENCHMARK_FIELDS = [
    "line",            # outside_off / off_stump / middle / leg / outside_leg
    "length",          # yorker / full / good / short_of_length / short
    "shot_type",       # drive / cut / pull / defend / sweep etc.
    "bowler_type",     # pace / spin
    "contact_quality", # clean / edge / miss / mistimed
    "footwork",        # front_foot / back_foot / neutral
]

# Models to benchmark
MODELS = {
    "gemini-2.5-pro": {
        "provider": "gemini",
        "model_id": "gemini-2.5-pro",
        "supports_video": True,
        "description": "Production model — video-native",
    },
    "gemini-2.5-flash": {
        "provider": "gemini",
        "model_id": "gemini-2.5-flash",
        "supports_video": True,
        "description": "Faster Gemini — video-native",
    },
    "llava:13b": {
        "provider": "ollama",
        "model_id": "llava:13b",
        "supports_video": False,  # image frames only
        "description": "LLaVA 13B local — frame-by-frame",
    },
    "llava:7b": {
        "provider": "ollama",
        "model_id": "llava:7b",
        "supports_video": False,
        "description": "LLaVA 7B local — frame-by-frame",
    },
    "moondream": {
        "provider": "ollama",
        "model_id": "moondream",
        "supports_video": False,
        "description": "Moondream local — lightweight vision",
    },
    "bakllava": {
        "provider": "ollama",
        "model_id": "bakllava",
        "supports_video": False,
        "description": "BakLLaVA local — Mistral + vision",
    },
}

# Frames to extract per ball clip for image-based models
FRAMES_PER_BALL = 4  # start / mid-delivery / release / follow-through

# Overs to include in benchmark (0-indexed over numbers)
# Default: overs 0-3 (first 4 overs = 24 balls)
BENCHMARK_OVERS = [0, 1, 2, 3]

# Scoring: exact match weight vs partial credit
EXACT_MATCH_FIELDS = ["line", "length", "bowler_type"]    # binary
PARTIAL_MATCH_FIELDS = ["shot_type", "contact_quality", "footwork"]  # grouped families

# Shot type families for partial credit scoring
SHOT_FAMILIES = {
    "drive": ["drive", "cover_drive", "straight_drive", "on_drive", "off_drive", "square_drive"],
    "cut": ["cut", "square_cut", "late_cut", "upper_cut"],
    "sweep": ["sweep", "slog_sweep", "reverse_sweep", "paddle_sweep"],
    "defend": ["defend", "front_foot_defence", "back_foot_defence"],
    "aerial": ["pull", "hook", "lofted"],
    "leg": ["glance", "flick", "leg_glance"],
}
