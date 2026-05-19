"""
Light temporal smoothing for MediaPipe landmark trajectories.

Uses a centered moving average of window N (default 5) over each of the 33
landmarks' (x, y) channels. Missing frames (landmarks=None) are linearly
interpolated from the nearest detected neighbours, capped at ±3 frames.

Returns a new dict with the same shape as input; does not mutate input.
"""

from __future__ import annotations

import copy


def _interpolate_missing(frames: list[dict], max_gap: int = 3) -> list[dict]:
    n = len(frames)
    last_seen: dict[int, int | None] = {}   # landmark idx → last frame idx w/ detection

    # Pass 1: forward-fill
    for i, f in enumerate(frames):
        if f["landmarks"] is not None:
            last_seen["all"] = i
    # Simple per-frame imputation: if None, borrow from previous+next within max_gap
    for i, f in enumerate(frames):
        if f["landmarks"] is not None:
            continue
        prev_idx = next((j for j in range(i - 1, max(-1, i - max_gap - 1), -1)
                         if frames[j]["landmarks"] is not None), None)
        next_idx = next((j for j in range(i + 1, min(n, i + max_gap + 1))
                         if frames[j]["landmarks"] is not None), None)
        if prev_idx is None and next_idx is None:
            continue
        if prev_idx is not None and next_idx is not None:
            t = (i - prev_idx) / (next_idx - prev_idx)
            a = frames[prev_idx]["landmarks"]
            b = frames[next_idx]["landmarks"]
            f["landmarks"] = [
                {
                    "x": a[k]["x"] + t * (b[k]["x"] - a[k]["x"]),
                    "y": a[k]["y"] + t * (b[k]["y"] - a[k]["y"]),
                    "z": a[k]["z"] + t * (b[k]["z"] - a[k]["z"]),
                    "v": min(a[k]["v"], b[k]["v"]) * 0.75,   # mark lower confidence
                }
                for k in range(len(a))
            ]
        else:
            src = frames[prev_idx if prev_idx is not None else next_idx]["landmarks"]
            f["landmarks"] = [dict(p, v=p["v"] * 0.5) for p in src]
    return frames


def _moving_average(frames: list[dict], window: int = 5) -> list[dict]:
    if window < 2:
        return frames
    n = len(frames)
    half = window // 2
    smoothed = copy.deepcopy(frames)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        neighbours = [frames[j]["landmarks"] for j in range(lo, hi) if frames[j]["landmarks"]]
        if not neighbours or frames[i]["landmarks"] is None:
            continue
        K = len(frames[i]["landmarks"])
        smoothed[i]["landmarks"] = [
            {
                "x": sum(n_[k]["x"] for n_ in neighbours) / len(neighbours),
                "y": sum(n_[k]["y"] for n_ in neighbours) / len(neighbours),
                "z": sum(n_[k]["z"] for n_ in neighbours) / len(neighbours),
                "v": frames[i]["landmarks"][k]["v"],
            }
            for k in range(K)
        ]
    return smoothed


def smooth_landmarks(pose_data: dict, window: int = 5, max_gap: int = 3) -> dict:
    out = copy.deepcopy(pose_data)
    out["frames"] = _interpolate_missing(out["frames"], max_gap=max_gap)
    out["frames"] = _moving_average(out["frames"], window=window)
    out["smoothed"] = True
    return out
