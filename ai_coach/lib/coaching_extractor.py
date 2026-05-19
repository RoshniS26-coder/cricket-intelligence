"""
Coaching corpus extractor — turns an expert tutorial video into structured
coaching knowledge.

Usage:
    from ai_coach.lib.coaching_extractor import extract_coaching_points
    result = extract_coaching_points(
        video_path="data/raw_videos/coach-kohli-cover-hindi.mp4",
        subject_hint="cover_drive technique by Virat Kohli",
    )
    # result has: shot_or_skill, key_technique_points, drills, common_mistakes,
    #             coaching_cues, ideal_outcome, extraction_confidence
    # Bilingual fields ({en, hi}): point, common_mistakes[], coaching_cues[], ideal_outcome.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console

from ai_coach.lib.coaching_prompts import (
    COACHING_EXTRACT_JSON_SCHEMA,
    get_coaching_extract_prompt,
    get_coaching_system_prompt,
)

load_dotenv()
console = Console()


def _wait_for_processing(client: genai.Client, file_obj, timeout_sec: int = 180):
    elapsed = 0
    while file_obj.state == "PROCESSING" and elapsed < timeout_sec:
        time.sleep(2)
        elapsed += 2
        file_obj = client.files.get(name=file_obj.name)
    return file_obj


def extract_coaching_points(
    video_path: str,
    subject_hint: str = "cricket batting technique",
    model: str = "gemini-2.5-flash",
    cleanup_upload: bool = True,
) -> dict:
    """
    Args:
        video_path:    Path to the coaching tutorial video.
        subject_hint:  Free-text hint about what the tutorial covers
                       (improves extraction quality). Examples:
                         "cover_drive technique by Virat Kohli"
                         "pull shot — Rohit Sharma's technique in Hindi"
                         "front-foot defence drills for U-16 academy players"
        model:         Gemini model. Default: gemini-2.5-flash.
        cleanup_upload: Delete the uploaded file from Gemini after the call.

    Returns:
        dict matching COACHING_EXTRACT_JSON_SCHEMA.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    p = Path(video_path)
    if not p.exists():
        raise FileNotFoundError(video_path)

    client = genai.Client(api_key=api_key)

    console.print(f"[blue]⟳[/blue] Uploading coaching video to Gemini: {p.name}")
    f = client.files.upload(file=video_path)
    f = _wait_for_processing(client, f)
    if f.state == "FAILED":
        raise RuntimeError(f"Upload failed: {video_path}")

    parts = [
        types.Part.from_text(text=f"COACHING TUTORIAL — subject: {subject_hint}"),
        types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type),
        types.Part.from_text(text=get_coaching_extract_prompt(subject_hint=subject_hint)),
    ]

    console.print(f"[blue]⟳[/blue] Calling Gemini ({model}) to extract coaching content")
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=get_coaching_system_prompt(),
            response_mime_type="application/json",
            response_schema=COACHING_EXTRACT_JSON_SCHEMA,
            temperature=0.2,
        ),
    )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ invalid JSON: {e}[/red]")
        console.print(f"[dim]raw: {response.text[:500]}...[/dim]")
        raise

    if cleanup_upload:
        try:
            client.files.delete(name=f.name)
        except Exception:
            pass

    n_points = len(result.get("key_technique_points", []) or [])
    n_drills = len(result.get("drills", []) or [])
    n_cues   = len(result.get("coaching_cues", []) or [])
    conf     = result.get("extraction_confidence", "?")
    console.print(
        f"[green]✓[/green] coaching extracted — "
        f"shot={result.get('shot_or_skill')} | "
        f"points={n_points} | drills={n_drills} | cues={n_cues} | conf={conf}"
    )
    return result


def _bilingual_en(value) -> str:
    """Return the English string from a bilingual {en, hi} dict.

    Backwards-compatible: legacy plain-string entries (pre-bilingual schema)
    are returned as-is so existing JSON files in the corpus keep working
    without re-extraction.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("en") or value.get("hi") or ""
    return str(value)


def _bilingual_hi(value) -> str:
    """Return the Hindi string from a bilingual {en, hi} dict, or "" for legacy strings."""
    if isinstance(value, dict):
        return value.get("hi") or ""
    return ""


def coaching_context_block(coaching: dict) -> str:
    """
    Render an extracted coaching dict into a compact text block suitable
    for injection into the few-shot critique prompt.

    Use case: when critiquing a student, include this block as
    "EXPERT COACHING GUIDANCE FOR THIS SHOT" so Gemini's critique aligns with
    what an Indian academy coach actually teaches.
    """
    lines = [f"EXPERT COACHING GUIDANCE — {coaching.get('shot_or_skill', 'this shot')}"]
    if coaching.get("reference_player"):
        lines.append(f"Reference player: {coaching['reference_player']}")
    if coaching.get("ideal_outcome"):
        lines.append(f"Ideal outcome: {_bilingual_en(coaching['ideal_outcome'])}")

    if coaching.get("key_technique_points"):
        lines.append("\nKey technique points:")
        for p in coaching["key_technique_points"]:
            lines.append(f"  - [{p.get('aspect', '?')}] {_bilingual_en(p.get('point'))}")

    if coaching.get("common_mistakes"):
        lines.append("\nCommon mistakes:")
        for m in coaching["common_mistakes"]:
            lines.append(f"  - {_bilingual_en(m)}")

    if coaching.get("coaching_cues"):
        lines.append("\nCoaching cues to use with the student:")
        for c in coaching["coaching_cues"]:
            lines.append(f'  - "{_bilingual_en(c)}"')

    if coaching.get("drills"):
        lines.append("\nDrills suggested:")
        for d in coaching["drills"]:
            lines.append(
                f"  - {d.get('drill_name', '?')}"
                + (f" ({d.get('duration_minutes')}min)" if d.get("duration_minutes") else "")
                + (f" — addresses {d.get('addresses_aspect')}" if d.get("addresses_aspect") else "")
            )

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--subject", default="cricket batting technique")
    args = p.parse_args()
    out = extract_coaching_points(args.video, subject_hint=args.subject)
    print(json.dumps(out, indent=2, ensure_ascii=False))
