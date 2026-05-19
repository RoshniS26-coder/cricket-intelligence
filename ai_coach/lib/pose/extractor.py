"""
MediaPipe pose extractor for cricket clips.

Uses the MediaPipe Tasks API (`mp.tasks.vision.PoseLandmarker`) which is the
supported path on newer Apple-Silicon / Python 3.12+ wheels where the legacy
`mp.solutions.pose` module was dropped.

The output shape is unchanged — consumers (`src.pose.smoothing`, features
modules, video renderer) keep working as-is.

Usage:
    from ai_coach.lib.pose.extractor import extract_pose_from_clip
    data = extract_pose_from_clip("data/raw_videos/net_test.mp4")
    # data["frames"] = [{"frame": 0, "time_sec": 0.0, "landmarks": [...]}, ...]
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import cv2
from rich.console import Console

console = Console()

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision
except Exception as e:  # pragma: no cover
    mp = None
    _MP_ERROR = e
else:
    _MP_ERROR = None


# MediaPipe hosts the model files at deterministic URLs.
# `full` is a good accuracy/size balance (~10 MB). Alternatives:
#   lite   — pose_landmarker_lite.task   (~5 MB,  fastest, lower accuracy)
#   full   — pose_landmarker_full.task   (~10 MB, default for us)
#   heavy  — pose_landmarker_heavy.task  (~30 MB, best accuracy, slowest)
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)
_MODEL_PATH = Path("models/pose_landmarker_full.task")


def _ensure_model() -> str:
    """Download the pose model once and cache under models/."""
    if _MODEL_PATH.exists() and _MODEL_PATH.stat().st_size > 0:
        return str(_MODEL_PATH)
    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"[blue]⟳[/blue] Downloading pose model (~10 MB) → {_MODEL_PATH}")
    urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    console.print(f"[green]✓[/green] Model cached at {_MODEL_PATH}")
    return str(_MODEL_PATH)


def extract_pose_from_clip(
    clip_path: str,
    output_path: str | None = None,
    model_complexity: int = 1,          # retained for API compatibility (ignored by Tasks API)
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> dict:
    if mp is None:
        raise RuntimeError(
            f"MediaPipe import failed: {_MP_ERROR}. "
            "pip install mediapipe inside a Python 3.12+ venv."
        )

    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open clip: {clip_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    console.print(
        f"[blue]⟳[/blue] MediaPipe pose on {Path(clip_path).name} "
        f"({total} frames @ {fps:.1f} fps)"
    )

    model_path = _ensure_model()
    options = vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=min_detection_confidence,
        min_pose_presence_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )

    frames: list[dict] = []
    detected = 0

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms = int(i * 1000 / fps)

            try:
                result = landmarker.detect_for_video(mp_image, ts_ms)
            except Exception:
                result = None

            if result and result.pose_landmarks:
                pose = result.pose_landmarks[0]   # first detected pose
                lm = [
                    {
                        "x": float(p.x),
                        "y": float(p.y),
                        "z": float(p.z),
                        "v": float(getattr(p, "visibility", 0.0)),
                    }
                    for p in pose
                ]
                detected += 1
            else:
                lm = None

            frames.append({"frame": i, "time_sec": round(i / fps, 3), "landmarks": lm})
            i += 1

    cap.release()

    detection_rate = detected / max(total, 1)
    mean_conf = 0.0
    if detected:
        vals = [p["v"] for f in frames if f["landmarks"] for p in f["landmarks"]]
        if vals:
            mean_conf = sum(vals) / len(vals)

    result = {
        "clip_path": str(clip_path),
        "fps": fps,
        "frame_count": total,
        "detection_rate": round(detection_rate, 3),
        "mean_confidence": round(mean_conf, 3),
        "frames": frames,
    }

    out = output_path or str(Path("data/pose") / (Path(clip_path).stem + ".json"))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result))
    console.print(
        f"[green]✓[/green] pose saved → {out}  "
        f"(detection_rate={detection_rate:.2%}, mean_conf={mean_conf:.2f})"
    )
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("clip")
    p.add_argument("--out", default=None)
    args = p.parse_args()
    extract_pose_from_clip(args.clip, output_path=args.out)
