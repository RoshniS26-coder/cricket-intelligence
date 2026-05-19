"""
Batsman technique features from MediaPipe pose data.

Thresholds default to the values in src/pose/thresholds.json if present,
otherwise fall back to constants below. Re-calibrate with
scripts/calibrate_pose_thresholds.py after 200+ reference clips.
"""

from __future__ import annotations

import json
from pathlib import Path

# MediaPipe POSE landmark indices
NOSE = 0
L_SH, R_SH = 11, 12
L_EL, R_EL = 13, 14
L_WR, R_WR = 15, 16
L_HIP, R_HIP = 23, 24
L_KN, R_KN = 25, 26
L_ANK, R_ANK = 27, 28

# Defaults (calibrate later)
_DEFAULTS = {
    "head_offset_target": 0.03,     # normalized (frame width units)
    "stride_norm_target": 0.35,     # stride / body_height
    "shoulder_angle_max": 30.0,     # degrees; above → camera is not side-on
    "mean_conf_min":      0.50,
}


def _load_thresholds() -> dict:
    p = Path("src/pose/thresholds.json")
    if p.exists():
        try:
            return json.loads(p.read_text()).get("batsman", _DEFAULTS)
        except Exception:
            return _DEFAULTS
    return _DEFAULTS


def _pt(lm, i): return (lm[i]["x"], lm[i]["y"])
def _v(lm, i):  return lm[i]["v"]


def _detect_impact_frame(frames: list[dict]) -> int | None:
    """Max wrist vertical velocity ≈ bat-ball impact. Robust enough for MVP."""
    ys = []
    for f in frames:
        lm = f["landmarks"]
        if lm and _v(lm, L_WR) > 0.3 and _v(lm, R_WR) > 0.3:
            ys.append((lm[L_WR]["y"] + lm[R_WR]["y"]) / 2.0)
        else:
            ys.append(None)
    # discrete diff skipping Nones
    best_idx, best_v = None, -1.0
    for i in range(1, len(ys)):
        if ys[i] is None or ys[i - 1] is None:
            continue
        v = abs(ys[i] - ys[i - 1])
        if v > best_v:
            best_v = v
            best_idx = i
    return best_idx


def compute_features(pose_data: dict, thresholds: dict | None = None) -> dict:
    """Return a flat dict of measurable technique features + qualitative flags."""
    t = thresholds or _load_thresholds()
    frames = pose_data["frames"]

    mean_conf = pose_data.get("mean_confidence", 0.0)
    if mean_conf < t.get("mean_conf_min", 0.5):
        return {"error": "low_pose_confidence", "mean_confidence": mean_conf}

    impact = _detect_impact_frame(frames)
    if impact is None:
        return {"error": "no_impact_frame"}

    lm = frames[impact]["landmarks"]
    if lm is None:
        return {"error": "no_landmarks_at_impact"}

    # Camera-angle sanity check: side-on if shoulder line is roughly horizontal
    sh_dx = lm[L_SH]["x"] - lm[R_SH]["x"]
    sh_dy = lm[L_SH]["y"] - lm[R_SH]["y"]
    import math
    shoulder_angle = math.degrees(math.atan2(sh_dy, sh_dx))

    # Head offset from hip midline (both in normalized frame coords)
    hip_mid_x = (lm[L_HIP]["x"] + lm[R_HIP]["x"]) / 2.0
    head_offset = abs(lm[NOSE]["x"] - hip_mid_x)

    # Body height proxy: right shoulder → right ankle (abs y)
    body_h = abs(lm[R_SH]["y"] - lm[R_ANK]["y"]) or 1e-6
    stride = abs(lm[L_ANK]["x"] - lm[R_ANK]["x"])
    stride_norm = stride / body_h

    # Stance (first good frame) — width between ankles
    stance_width_norm = None
    for f in frames[:30]:
        if f["landmarks"] and _v(f["landmarks"], L_ANK) > 0.5 and _v(f["landmarks"], R_ANK) > 0.5:
            bh = abs(f["landmarks"][R_SH]["y"] - f["landmarks"][R_ANK]["y"]) or 1e-6
            stance_width_norm = abs(f["landmarks"][L_ANK]["x"] - f["landmarks"][R_ANK]["x"]) / bh
            break

    features = {
        "impact_frame":         impact,
        "impact_time_sec":      frames[impact]["time_sec"],
        "head_lateral_offset":  round(head_offset, 4),
        "head_over_ball":       head_offset < t["head_offset_target"],
        "stride_length_norm":   round(stride_norm, 3),
        "stride_adequate":      stride_norm > t["stride_norm_target"],
        "shoulder_angle_deg":   round(shoulder_angle, 2),
        "side_on_camera":       abs(shoulder_angle) <= t["shoulder_angle_max"] or
                                 abs(abs(shoulder_angle) - 180.0) <= t["shoulder_angle_max"],
        "stance_width_norm":    round(stance_width_norm, 3) if stance_width_norm else None,
        "mean_pose_confidence": round(mean_conf, 3),
    }

    # Compound feature confidence (used downstream to gate briefings)
    faults = sum(1 for k in ("head_over_ball", "stride_adequate") if not features[k])
    features["feature_confidence"] = round(max(0.0, mean_conf - 0.1 * faults), 3)
    return features
