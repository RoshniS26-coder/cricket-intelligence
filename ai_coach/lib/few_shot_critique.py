"""
Few-shot Gemini critique.

Compares a student's shot video against N reference clips of ideal technique
in a single Gemini API call, returning a structured JSON critique.

Why this matters: works on ANY camera angle (broadcast, bowler's-end, side-on),
unlike the pose layer which requires side-on framing. Coach gets natural-language
corrections in the form they think in: "play it like Kohli."

Usage:
    from ai_coach.lib.few_shot_critique import critique_against_references
    result = critique_against_references(
        student_clip="data/raw_videos/student.mp4",
        reference_clips=[
            {"path": "data/raw_videos/kohli-cover-1.mp4", "player": "Virat Kohli"},
            {"path": "data/raw_videos/kohli-cover-2.mp4", "player": "Virat Kohli"},
        ],
        shot_type="cover_drive",
    )
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

from ai_coach.lib.critique_prompts import (
    CRITIQUE_JSON_SCHEMA,
    get_critique_prompt,
    get_critique_system_prompt,
    get_net_session_critique_prompt,
    get_net_session_solo_critique_prompt,
    get_solo_critique_prompt,
    resolve_reference_player,
)
from ai_coach.lib.coaching_extractor import coaching_context_block

load_dotenv()
console = Console()


def _wait_for_processing(client: genai.Client, file_obj, timeout_sec: int = 120):
    """Poll Gemini Files API until the upload finishes processing."""
    elapsed = 0
    while file_obj.state == "PROCESSING" and elapsed < timeout_sec:
        time.sleep(2)
        elapsed += 2
        file_obj = client.files.get(name=file_obj.name)
    return file_obj


def _upload(client: genai.Client, path: str, label: str):
    f = client.files.upload(file=path)
    f = _wait_for_processing(client, f)
    if f.state == "FAILED":
        raise RuntimeError(f"Gemini upload failed: {label} ({path})")
    return f


def critique_against_references(
    student_clip: str,
    reference_clips: list[dict],
    shot_type: str,
    coaching_context: list[dict] | None = None,
    mode: str = "single_ball",
    model: str = "gemini-2.5-flash",
    cleanup_uploads: bool = True,
    player_name: str = "the player",
    reference_player: str | None = None,
    auto_anchor: bool = True,
) -> dict:
    """
    Args:
        student_clip:    Path to the student's attempt video.
        reference_clips: List of {"path": str, "player": str} dicts.
                         "player" is optional but improves prompt quality.
        shot_type:       Cricket shot label (e.g. "cover_drive", "pull", "defend").
                         Should match a value the student is attempting.
        coaching_context: Optional list of extracted coaching dicts (the JSON
                         output of src.intelligence.coaching_extractor). If
                         provided, each is injected as an EXPERT COACHING
                         GUIDANCE block before the visual references — the
                         critique then aligns its deviations with what coaches
                         actually teach (drills, cues, common mistakes), not
                         only with what the reference clips visually show.
        mode:            "single_ball" (default) — student clip is one delivery;
                         "net_session" — student clip is a net practice with
                         multiple attempts at the same shot. Selects the
                         prompt variant. Output schema unchanged.
        model:           Gemini model name. Default: gemini-2.5-flash.
        cleanup_uploads: Whether to delete uploaded files from Gemini after the call.

    Returns:
        Parsed JSON dict matching CRITIQUE_JSON_SCHEMA.
    """
    if mode not in ("single_ball", "net_session"):
        raise ValueError(f"mode must be 'single_ball' or 'net_session', got {mode!r}")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Add it to .env or export it."
        )

    student_path = Path(student_clip)
    if not student_path.exists():
        raise FileNotFoundError(f"Student clip not found: {student_clip}")
    # reference_clips is OPTIONAL — empty list = solo mode (Gemini's intrinsic
    # cricket knowledge + optional coaching corpus). Reference clips add visual
    # grounding ("play it like Kohli") but are no longer required.
    if reference_clips is None:
        reference_clips = []
    for r in reference_clips:
        if not Path(r["path"]).exists():
            raise FileNotFoundError(f"Reference clip not found: {r['path']}")
    solo = len(reference_clips) == 0

    client = genai.Client(api_key=api_key)
    uploaded = []     # track for cleanup
    parts = []

    # ── Inject expert coaching guidance FIRST (frames the critique) ──────────
    if coaching_context:
        console.print(
            f"[blue]⟳[/blue] Injecting {len(coaching_context)} coaching "
            "context block(s) before visual references"
        )
        for i, coaching in enumerate(coaching_context, start=1):
            block_header = (
                f"--- COACHING CONTEXT {i} of {len(coaching_context)} ---"
            )
            block_text = coaching_context_block(coaching)
            parts.append(types.Part.from_text(text=f"{block_header}\n{block_text}"))
        # Brief framing instruction
        parts.append(types.Part.from_text(text=(
            "Use the coaching guidance above to inform what 'ideal' looks like "
            "for the videos that follow. When you list deviations, prefer "
            "language and corrections that align with the coaching cues, "
            "common mistakes, and drills cited in the coaching context."
        )))

    # ── Upload + add reference clips (skipped in solo mode) ──────────────────
    if solo:
        console.print(
            f"[blue]⟳[/blue] Solo mode (no references) — uploading 1 student clip"
        )
    else:
        console.print(
            f"[blue]⟳[/blue] Uploading {len(reference_clips)} reference clip(s) "
            f"+ 1 student clip to Gemini Files API"
        )
        for i, ref in enumerate(reference_clips, start=1):
            ref_path = ref["path"]
            ref_player = ref.get("player", "a professional batsman")
            ref_file = _upload(client, ref_path, f"reference {i}")
            uploaded.append(ref_file)
            label = f"REFERENCE {i} — ideal {shot_type} by {ref_player}:"
            parts.append(types.Part.from_text(text=label))
            parts.append(types.Part.from_uri(file_uri=ref_file.uri, mime_type=ref_file.mime_type))
            console.print(f"  [green]✓[/green] reference {i}: {Path(ref_path).name} ({ref_player})")

    # ── Upload + add student clip ─────────────────────────────────────────────
    student_file = _upload(client, str(student_path), "student")
    uploaded.append(student_file)
    name_upper = player_name.upper() if player_name and player_name != "the player" else "STUDENT"
    if mode == "net_session":
        student_label = (
            f"{name_upper} — NET PRACTICE SESSION with multiple attempts at the {shot_type} "
            f"by {player_name}, a player learning the technique:"
        )
    else:
        student_label = (
            f"{name_upper} — attempt at the same {shot_type} by {player_name}, "
            f"a player learning the technique:"
        )
    parts.append(types.Part.from_text(text=student_label))
    parts.append(types.Part.from_uri(file_uri=student_file.uri, mime_type=student_file.mime_type))
    console.print(f"  [green]✓[/green] student: {student_path.name}  (mode={mode}, player={player_name!r})")

    # ── Final instruction (prompt depends on mode + solo + auto-anchor) ──────
    # In solo mode, resolve the reference player to use as text anchor:
    #   1. Explicit --reference-player wins
    #   2. Auto-anchor from CANONICAL_PLAYERS_BY_SHOT table (default ON)
    #   3. None → generic textbook ideal
    # In with-references mode, the videos themselves are the anchor; we ignore
    # reference_player to avoid mixing signals.
    resolved_anchor = (
        resolve_reference_player(shot_type, explicit=reference_player, auto_anchor=auto_anchor)
        if solo else None
    )
    if resolved_anchor:
        if reference_player:
            console.print(f"  [dim]anchor: {resolved_anchor} (explicit)[/dim]")
        else:
            console.print(f"  [dim]anchor: {resolved_anchor} (auto from canonical table)[/dim]")

    if mode == "net_session" and solo:
        prompt_text = get_net_session_solo_critique_prompt(
            shot_type=shot_type, player_name=player_name,
            reference_player=resolved_anchor,
        )
    elif mode == "net_session":
        prompt_text = get_net_session_critique_prompt(
            n_references=len(reference_clips), shot_type=shot_type, player_name=player_name,
        )
    elif solo:
        prompt_text = get_solo_critique_prompt(
            shot_type=shot_type, player_name=player_name,
            reference_player=resolved_anchor,
        )
    else:
        prompt_text = get_critique_prompt(
            n_references=len(reference_clips), shot_type=shot_type, player_name=player_name,
        )
    parts.append(types.Part.from_text(text=prompt_text))

    # ── Call Gemini ───────────────────────────────────────────────────────────
    console.print(f"[blue]⟳[/blue] Calling Gemini ({model}) — single-call multi-video comparison")
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=get_critique_system_prompt(),
            response_mime_type="application/json",
            response_schema=CRITIQUE_JSON_SCHEMA,
            temperature=0.2,
        ),
    )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ Gemini returned invalid JSON: {e}[/red]")
        console.print(f"[dim]raw response: {response.text[:500]}...[/dim]")
        raise

    # ── Cleanup uploads ───────────────────────────────────────────────────────
    if cleanup_uploads:
        for f in uploaded:
            try:
                client.files.delete(name=f.name)
            except Exception:
                pass

    # ── Log summary ───────────────────────────────────────────────────────────
    n_dev = len(result.get("deviations", []))
    rating = result.get("overall_quality_rating", "?")
    color = {"close_to_ideal": "green",
             "needs_minor_work": "yellow",
             "needs_major_work": "red"}.get(rating, "white")
    console.print(
        f"[{color}]✓[/{color}] critique complete — "
        f"shot={result.get('identified_shot_type')} | "
        f"rating={rating} | "
        f"deviations={n_dev}"
    )
    return result


if __name__ == "__main__":
    # Minimal CLI for quick testing — full CLI is in scripts/critique_student_clip.py
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--student", required=True)
    p.add_argument("--reference", action="append", required=True,
                   help="Repeatable. Path or 'path:player_name'.")
    p.add_argument("--shot-type", required=True)
    args = p.parse_args()

    refs = []
    for r in args.reference:
        if ":" in r:
            path, player = r.split(":", 1)
            refs.append({"path": path, "player": player})
        else:
            refs.append({"path": r})

    result = critique_against_references(
        student_clip=args.student,
        reference_clips=refs,
        shot_type=args.shot_type,
    )
    print(json.dumps(result, indent=2))
