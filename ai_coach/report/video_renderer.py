"""
Overlay MediaPipe pose + technique labels onto a clip.

Produces an intermediate OpenCV MP4, then slows it down via ffmpeg setpts
(re-encoded to h264+yuv420p so WhatsApp / Safari can play it).

Usage:
    from ai_coach.report.video_renderer import render_annotated_video
    render_annotated_video(clip, pose_data, features, gemini_fields,
                           player_id, briefing_cues, out_path, slowdown=2.0)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np
from rich.console import Console

console = Console()

# ── MediaPipe indices ────────────────────────────────────────────────────────
NOSE = 0
L_SH, R_SH = 11, 12
L_EL, R_EL = 13, 14
L_WR, R_WR = 15, 16
L_HIP, R_HIP = 23, 24
L_KN, R_KN = 25, 26
L_ANK, R_ANK = 27, 28

SKELETON_EDGES = [
    (L_SH, R_SH), (L_SH, L_HIP), (R_SH, R_HIP), (L_HIP, R_HIP),
    (L_SH, L_EL), (L_EL, L_WR), (R_SH, R_EL), (R_EL, R_WR),
    (L_HIP, L_KN), (L_KN, L_ANK), (R_HIP, R_KN), (R_KN, R_ANK),
]

WHITE  = (255, 255, 255)
BLACK  = (0, 0, 0)
YELLOW = (0, 220, 220)
GREEN  = (60, 200, 60)
RED    = (60, 60, 230)
CYAN   = (255, 220, 0)


def _px(lm: list[dict], w: int, h: int) -> np.ndarray:
    return np.array([[p["x"] * w, p["y"] * h, p["v"]] for p in lm])


def _draw_skeleton(frame: np.ndarray, lm: list[dict], w: int, h: int, head_fault: bool):
    pts = _px(lm, w, h)
    for a, b in SKELETON_EDGES:
        if pts[a, 2] > 0.3 and pts[b, 2] > 0.3:
            cv2.line(frame, tuple(pts[a, :2].astype(int)), tuple(pts[b, :2].astype(int)), WHITE, 2)
    for i, (x, y, v) in enumerate(pts):
        if v > 0.3:
            cv2.circle(frame, (int(x), int(y)), 4, YELLOW, -1)
    if pts[NOSE, 2] > 0.3:
        cv2.circle(frame, tuple(pts[NOSE, :2].astype(int)), 12, RED if head_fault else GREEN, 2)
    # hip midline
    if pts[L_HIP, 2] > 0.3 and pts[R_HIP, 2] > 0.3:
        mx = int((pts[L_HIP, 0] + pts[R_HIP, 0]) / 2)
        top = int(pts[L_SH, 1]) if pts[L_SH, 2] > 0.3 else 0
        bot = int((pts[L_HIP, 1] + pts[R_HIP, 1]) / 2)
        cv2.line(frame, (mx, top), (mx, bot), YELLOW, 1, cv2.LINE_AA)
    for lmi, tag in ((L_ANK, "F"), (R_ANK, "B")):
        if pts[lmi, 2] > 0.3:
            cv2.putText(frame, tag, (int(pts[lmi, 0]) + 5, int(pts[lmi, 1]) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)


def _draw_panel(frame, lines, origin, scale=0.55, bg=BLACK, fg=WHITE):
    x, y = origin
    line_h = int(22 * scale / 0.55)
    pad = 8
    if not lines:
        return
    tw = max(cv2.getTextSize(ln, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0] for ln in lines)
    th = line_h * len(lines) + pad * 2
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - pad, y - pad), (x + tw + pad, y + th - pad), bg, -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
    for i, ln in enumerate(lines):
        cv2.putText(frame, ln, (x, y + (i + 1) * line_h - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, fg, 1, cv2.LINE_AA)


def _metric_panel_lines(features: dict, gemini: dict) -> list[str]:
    flag = lambda bad: " !" if bad else " ok"
    lines = [
        f"shot:    {gemini.get('shot_type', '?')}",
        f"length:  {gemini.get('length', '?')}",
        f"swing:   {gemini.get('swing_direction', '?')}",
        f"contact: {gemini.get('contact_quality', '?')}",
        "---",
    ]
    if "error" not in features:
        lines += [
            f"head off:  {features.get('head_lateral_offset', '-')}{flag(not features.get('head_over_ball', True))}",
            f"stride:    {features.get('stride_length_norm', '-')}{flag(not features.get('stride_adequate', True))}",
            f"shoulder:  {features.get('shoulder_angle_deg', '-')} deg",
        ]
    else:
        lines += [f"pose: {features['error']}"]
    return lines


def render_annotated_video(
    clip_path: str,
    pose_data: dict,
    features: dict,
    gemini_fields: dict,
    player_id: str,
    briefing_cues: list[str],
    output_path: str,
    slowdown: float = 2.0,
    freeze_impact_ms: int = 800,
) -> str:
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        raise FileNotFoundError(clip_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frames_pose = pose_data["frames"]
    impact_idx = features.get("impact_frame")
    head_fault = not features.get("head_over_ball", True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tmp = str(Path(output_path).with_suffix(".raw.mp4"))
    writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    wrist_trail: list[tuple[int, int]] = []
    cue_rotate_every = int(fps * 3)   # change banner every ~3 s
    metric_lines = _metric_panel_lines(features, gemini_fields)

    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        lm = frames_pose[idx]["landmarks"] if idx < len(frames_pose) else None
        if lm:
            _draw_skeleton(frame, lm, w, h, head_fault)
            pts = _px(lm, w, h)
            if pts[R_WR, 2] > 0.3:
                wrist_trail.append(tuple(pts[R_WR, :2].astype(int)))
                wrist_trail = wrist_trail[-10:]
            for i in range(1, len(wrist_trail)):
                cv2.line(frame, wrist_trail[i - 1], wrist_trail[i], CYAN, 2)

            if impact_idx is not None and idx == impact_idx:
                _draw_impact_callouts(frame, lm, features, w, h)

        _draw_panel(frame, [f"{player_id}", f"outcome: {gemini_fields.get('outcome', '?')}"],
                    origin=(20, 20))
        _draw_panel(frame, metric_lines, origin=(max(20, w - 320), 20))

        if briefing_cues:
            cue = briefing_cues[(idx // max(1, cue_rotate_every)) % len(briefing_cues)]
            _draw_panel(frame, [cue], origin=(20, h - 60), scale=0.7, bg=(30, 30, 30))

        writer.write(frame)

        # Freeze on impact frame
        if impact_idx is not None and idx == impact_idx and freeze_impact_ms > 0:
            n_freeze = int(fps * freeze_impact_ms / 1000)
            for _ in range(n_freeze):
                writer.write(frame)

        idx += 1

    cap.release()
    writer.release()

    # Slow down + re-encode to h264 (WhatsApp / Safari compatible)
    console.print(f"[blue]⟳[/blue] ffmpeg setpts={slowdown}x → h264")
    slowed = str(Path(output_path).with_suffix(".slowed.mp4"))
    subprocess.run([
        "ffmpeg", "-y", "-i", tmp,
        "-filter:v", f"setpts={slowdown}*PTS",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        slowed,
    ], check=True, capture_output=True)
    Path(tmp).unlink(missing_ok=True)
    Path(slowed).rename(output_path)
    console.print(f"[green]✓[/green] annotated video → {output_path}")
    return output_path


def _draw_impact_callouts(frame, lm, features, w, h):
    pts = _px(lm, w, h)
    if "error" in features:
        return
    if pts[NOSE, 2] > 0.3:
        hx, hy = int(pts[NOSE, 0]), int(pts[NOSE, 1])
        col = RED if not features.get("head_over_ball") else GREEN
        cv2.arrowedLine(frame, (hx + 80, hy - 30), (hx + 15, hy - 5), col, 2)
        cv2.putText(frame, f"head {features['head_lateral_offset']}",
                    (hx + 85, hy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
    if pts[L_ANK, 2] > 0.3 and pts[R_ANK, 2] > 0.3:
        ax = int((pts[L_ANK, 0] + pts[R_ANK, 0]) / 2)
        ay = int((pts[L_ANK, 1] + pts[R_ANK, 1]) / 2)
        col = RED if not features.get("stride_adequate") else GREEN
        cv2.arrowedLine(frame, (ax + 100, ay + 30), (ax + 20, ay + 5), col, 2)
        cv2.putText(frame, f"stride {features['stride_length_norm']}",
                    (ax + 105, ay + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
