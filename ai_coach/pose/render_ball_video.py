"""
Single-command demo: one clip → annotated + narrated slow-motion video.

Pipeline:
    1. Run Gemini on the clip (optional — skip with --no-gemini)
    2. MediaPipe pose → smooth → compute batsman features
    3. Build a short narration text (Gemini if key present, else template)
    4. Edge TTS → narration.mp3
    5. OpenCV overlay + ffmpeg slowdown → annotated.mp4
    6. ffmpeg mux (stretches video to match audio length) → final.mp4

Usage:
    venv/bin/python scripts/render_ball_video.py \\
        --clip data/raw_videos/net_test.mp4 \\
        --player "Rahul" \\
        --out data/reports/videos/rahul_demo.mp4

Prereqs:
    pip install mediapipe edge-tts
    python scripts/migrate_add_pose.py   (already done)
    GEMINI_API_KEY in .env  (optional — pipeline runs pose-only without it)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


NARRATION_TEMPLATE = (
    "Watch the head position at impact. "
    "Head offset: {head_offset}, target is under {head_target}. "
    "Stride length: {stride}, target is above {stride_target}. "
    "Overall technique: {verdict}. "
    "Coaching cue: stay still, let the ball come, transfer weight forward."
)


def _llm_narration(player: str, features: dict, gemini: dict) -> str:
    """Use Gemini to produce a short (~60-word) narration if key is available."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return _template_narration(features)

    try:
        from google import genai
        from google.genai import types
    except Exception:
        return _template_narration(features)

    prompt = f"""Write a 60-word Indian academy coach briefing for this single ball.
Plain English, direct, no hedging, no marketing fluff. 3-4 sentences max.

Player: {player}
Shot: {gemini.get('shot_type', '?')}
Length: {gemini.get('length', '?')}
Swing: {gemini.get('swing_direction', '?')}
Contact: {gemini.get('contact_quality', '?')}
Outcome: {gemini.get('outcome', '?')}

Pose metrics:
  head_lateral_offset: {features.get('head_lateral_offset', '?')} (target < 0.03)
  head_over_ball:      {features.get('head_over_ball', '?')}
  stride_length_norm:  {features.get('stride_length_norm', '?')} (target > 0.35)
  stride_adequate:     {features.get('stride_adequate', '?')}
  shoulder_angle_deg:  {features.get('shoulder_angle_deg', '?')}

Structure:
1. One sentence on what happened on this ball
2. One sentence on the main technique observation (cite the number)
3. One sentence coaching cue
"""
    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return resp.text.strip()
    except Exception as e:
        console.print(f"[yellow]⚠ Gemini narration failed: {e} → using template[/yellow]")
        return _template_narration(features)


def _template_narration(features: dict) -> str:
    if "error" in features:
        return (
            f"Unable to compute technique metrics for this ball "
            f"({features['error']}). Check camera angle and batsman framing."
        )
    verdict = "clean" if features.get("head_over_ball") and features.get("stride_adequate") else "needs work"
    return NARRATION_TEMPLATE.format(
        head_offset=features.get("head_lateral_offset"),
        head_target=0.03,
        stride=features.get("stride_length_norm"),
        stride_target=0.35,
        verdict=verdict,
    )


def _extract_gemini(clip: str) -> dict:
    """Call Gemini on the clip. Returns a dict of fields or defaults."""
    defaults = {
        "shot_type": "?", "length": "?", "outcome": "?",
        "swing_direction": "?", "contact_quality": "?",
    }
    if not os.getenv("GEMINI_API_KEY"):
        console.print("[yellow]⚠ GEMINI_API_KEY missing — skipping Gemini extraction[/yellow]")
        return defaults
    try:
        from match_intelligence.lib.extractor import GeminiExtractor
        ex = GeminiExtractor()
        rec = ex.extract_from_clip(clip, match_id="render_demo", over=0, ball_number=1)
        if not rec:
            return defaults
        return {
            "shot_type":       rec.shot_type.value,
            "length":          rec.length.value,
            "outcome":         rec.outcome.value,
            "swing_direction": rec.swing_direction.value,
            "spin_direction":  rec.spin_direction.value,
            "contact_quality": rec.contact_quality.value,
        }
    except Exception as e:
        console.print(f"[yellow]⚠ Gemini extraction failed: {e}[/yellow]")
        return defaults


def _cues(features: dict, gemini: dict) -> list[str]:
    cues = ["Watch the head at impact"]
    if "head_lateral_offset" in features:
        cues.append(f"Head offset: {features['head_lateral_offset']}   target < 0.03")
    if "stride_length_norm" in features:
        cues.append(f"Stride: {features['stride_length_norm']}   target > 0.35")
    if gemini.get("length") and gemini["length"] != "?":
        cues.append(f"Delivery: {gemini.get('length')} / {gemini.get('swing_direction', '-')}")
    cues.append("Freeze frame — watch the impact")
    return cues


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--clip",   required=True, help="Path to a single-ball clip (MP4)")
    p.add_argument("--player", default="Player A")
    p.add_argument("--out",    default="data/reports/videos/ball_demo.mp4")
    p.add_argument("--slowdown", type=float, default=2.0, help="Base slowdown factor (ffmpeg setpts)")
    p.add_argument("--no-gemini", action="store_true", help="Skip Gemini extraction")
    p.add_argument("--voice",  default="en-IN-PrabhatNeural")
    args = p.parse_args()

    clip = args.clip
    if not Path(clip).exists():
        console.print(f"[red]✗ clip not found:[/red] {clip}")
        return 1

    console.print(f"[bold cyan]AI Coach — Ball Render[/bold cyan]")
    console.print(f"clip:   {clip}")
    console.print(f"player: {args.player}")
    console.print(f"out:    {args.out}\n")

    # 1. Gemini fields
    console.print("[bold]Step 1/5:[/bold] Gemini extraction")
    gemini = {} if args.no_gemini else _extract_gemini(clip)
    console.print(f"  {gemini}\n")

    # 2. Pose + features
    console.print("[bold]Step 2/5:[/bold] MediaPipe pose")
    from ai_coach.lib.pose.extractor import extract_pose_from_clip
    from ai_coach.lib.pose.smoothing import smooth_landmarks
    from ai_coach.lib.pose.features.batsman import compute_features

    pose_raw = extract_pose_from_clip(clip)
    pose = smooth_landmarks(pose_raw, window=5, max_gap=3)
    features = compute_features(pose)
    console.print(f"  features: {json.dumps(features, indent=2)}\n")

    # 3. Narration text
    console.print("[bold]Step 3/5:[/bold] Briefing text")
    narration = _llm_narration(args.player, features, gemini)
    console.print(f"[dim]{narration}[/dim]\n")

    # 4. TTS
    console.print("[bold]Step 4/5:[/bold] Edge TTS narration")
    from ai_coach.report.tts import generate_narration
    mp3 = str(Path(args.out).with_suffix(".mp3"))
    generate_narration(narration, mp3, voice=args.voice)

    # 5. Overlay video
    console.print("\n[bold]Step 5/5:[/bold] Overlay + slowdown + mux")
    from ai_coach.report.video_renderer import render_annotated_video
    annotated = str(Path(args.out).with_suffix(".annotated.mp4"))
    render_annotated_video(
        clip_path=clip,
        pose_data=pose,
        features=features,
        gemini_fields=gemini,
        player_id=args.player,
        briefing_cues=_cues(features, gemini),
        output_path=annotated,
        slowdown=args.slowdown,
    )

    # 6. Mux
    from ai_coach.report.mux import mux_audio_video
    mux_audio_video(annotated, mp3, args.out, match_video_to_audio=True)
    Path(annotated).unlink(missing_ok=True)

    console.print(
        f"\n[bold green]done[/bold green] → {args.out}\n"
        f"  open {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
