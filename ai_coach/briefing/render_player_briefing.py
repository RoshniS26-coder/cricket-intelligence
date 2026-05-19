"""
End-to-end CLI: clip → 1-page hybrid PDF briefing.

Combines four AI engines into one printable artifact:
  1. Gemini extraction (line, length, swing, shot, outcome)
  2. MediaPipe pose features (head offset, stride, shoulder)         [optional]
  3. Few-shot Gemini critique vs reference clips                      [optional]
  4. Coaching corpus context (drills + cues from extracted tutorials) [optional]

Usage:
    # Full hybrid briefing (all four engines)
    source venv312/bin/activate    # MediaPipe needs Python 3.12
    python scripts/render_player_briefing.py \\
        --clip data/raw_videos/student_drive.mp4 \\
        --player "Rahul Kumar" \\
        --shot-type cover_drive \\
        --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \\
                     "data/reference_library/videos/cover-drive/kohli-explains-cover-1.mp4:Virat Kohli" \\
        --coaching-keys "coach-kohli-cover-hindi,kohli-explains-cover-1" \\
        --out data/reports/rahul_briefing.pdf

    # Skip pose (works in plain venv, no MediaPipe required)
    source venv/bin/activate
    python scripts/render_player_briefing.py \\
        --clip data/raw_videos/student_drive.mp4 \\
        --player "Rahul Kumar" \\
        --shot-type cover_drive \\
        --references "data/reference_library/videos/cover-drive/kohli-cover-1.mp4:Virat Kohli" \\
        --coaching-keys "coach-kohli-cover-hindi" \\
        --skip-pose \\
        --out data/reports/rahul_briefing.pdf

    # Minimal — just Gemini extraction + raw description, no critique
    python scripts/render_player_briefing.py \\
        --clip data/raw_videos/student_drive.mp4 \\
        --player "Rahul Kumar" \\
        --shot-type cover_drive \\
        --skip-pose \\
        --out data/reports/rahul_briefing.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uuid
from datetime import datetime

from rich.console import Console

from ai_coach.lib.coaching_loader import load_coaching_context
from ai_coach.lib.session_catalog import (
    _video_duration_seconds,
    run_session_catalog,
)

console = Console()


def _save_to_db(
    player: str,
    shot_type: str,
    clip_path: str,
    match_id: str,
    gemini: dict | None,
    records: list | None = None,
) -> int:
    """Save ball records from a briefing run into the DB for weakness analysis.

    Single-ball mode: builds one record from the gemini dict.
    Net-session mode: saves all records from the catalog pre-pass (batsman_name patched in).

    Returns number of balls saved.
    """
    try:
        from src.storage.db import CricketDB
        from src.intelligence.schema import (
            BallRecord, BowlerType, Line, Length, Variation,
            ShotType, Footwork, ContactQuality, Outcome,
            SwingDirection, SwingType, SpinDirection, BallAgePhase,
            BounceBehavior, Movement, ConfidenceScores,
        )
        from src.validation.normalizer import BallNormalizer
    except Exception as e:
        console.print(f"[yellow]⚠ DB save skipped (import error): {e}[/yellow]")
        return 0

    db = CricketDB()
    db.create_match({
        "match_id": match_id,
        "format": "nets",
        "team_a": player,
        "team_b": "",
    })

    if records:
        # Net-session: patch batsman_name into every record then batch-save
        for r in records:
            r.batsman_name = player
            r.match_id = match_id
        normalizer = BallNormalizer()
        validated, _ = normalizer.validate_batch(records)
        saved = db.save_balls_batch(validated)
        return saved

    if gemini:
        # Single-ball: reconstruct a minimal BallRecord from the gemini dict
        def _e(cls, val, default):
            try:
                return cls(val)
            except Exception:
                return default

        ball_id = f"{match_id}_1_1"
        rec = BallRecord(
            ball_id=ball_id,
            match_id=match_id,
            innings=1, over=1, ball_number=1,
            batsman_name=player,
            bowler_type=_e(BowlerType, gemini.get("bowler_type"), BowlerType.UNKNOWN),
            line=_e(Line, gemini.get("line"), Line.UNKNOWN),
            length=_e(Length, gemini.get("length"), Length.UNKNOWN),
            variation=_e(Variation, gemini.get("variation"), Variation.NONE),
            shot_type=_e(ShotType, gemini.get("shot_type"), ShotType.UNKNOWN),
            footwork=_e(Footwork, gemini.get("footwork"), Footwork.UNKNOWN),
            contact_quality=_e(ContactQuality, gemini.get("contact_quality"), ContactQuality.UNKNOWN),
            outcome=_e(Outcome, gemini.get("outcome"), Outcome.UNKNOWN),
            swing_direction=_e(SwingDirection, gemini.get("swing_direction"), SwingDirection.UNKNOWN),
            swing_type=_e(SwingType, gemini.get("swing_type"), SwingType.UNKNOWN),
            spin_direction=_e(SpinDirection, gemini.get("spin_direction"), SpinDirection.UNKNOWN),
            ball_age_phase=_e(BallAgePhase, gemini.get("ball_age_phase"), BallAgePhase.UNKNOWN),
            bounce_behavior=_e(BounceBehavior, gemini.get("bounce_behavior"), BounceBehavior.UNKNOWN),
            movement=_e(Movement, gemini.get("movement"), Movement.UNKNOWN),
            raw_description=gemini.get("raw_description", ""),
            clip_path=clip_path,
            confidence=ConfidenceScores(),
        )
        db.save_ball(rec)
        return 1

    return 0


def parse_reference(entry: str) -> dict:
    if ":" in entry:
        path, player = entry.split(":", 1)
        return {"path": path.strip(), "player": player.strip()}
    return {"path": entry.strip(), "player": "professional batsman"}


def run_gemini_extraction(clip_path: str, model: str = "gemini-2.5-flash") -> dict | None:
    try:
        from match_intelligence.lib.extractor import GeminiExtractor
    except Exception as e:
        console.print(f"[yellow]⚠ Gemini extractor import failed: {e}[/yellow]")
        return None
    try:
        ex = GeminiExtractor(model_name=model)
        rec = ex.extract_from_clip(clip_path, match_id="briefing_demo", over=0, ball_number=1)
        if not rec:
            return None
        return {
            "bowler_type":     rec.bowler_type.value,
            "line":            rec.line.value,
            "length":          rec.length.value,
            "variation":       rec.variation.value,
            "shot_type":       rec.shot_type.value,
            "footwork":        rec.footwork.value,
            "contact_quality": rec.contact_quality.value,
            "outcome":         rec.outcome.value,
            "movement":        rec.movement.value,
            "bounce_behavior": rec.bounce_behavior.value,
            "swing_direction": rec.swing_direction.value,
            "swing_type":      rec.swing_type.value,
            "spin_direction":  rec.spin_direction.value,
            "ball_age_phase":  rec.ball_age_phase.value,
            "raw_description": rec.raw_description,
        }
    except Exception as e:
        console.print(f"[yellow]⚠ Gemini extraction failed: {e}[/yellow]")
        return None


def run_pose_pipeline(clip_path: str) -> dict | None:
    try:
        from ai_coach.lib.pose.extractor import extract_pose_from_clip
        from ai_coach.lib.pose.smoothing import smooth_landmarks
        from ai_coach.lib.pose.features.batsman import compute_features
    except Exception as e:
        console.print(f"[yellow]⚠ pose pipeline import failed (need MediaPipe / venv312): {e}[/yellow]")
        return None
    try:
        pose = extract_pose_from_clip(clip_path)
        smoothed = smooth_landmarks(pose, window=5, max_gap=3)
        return compute_features(smoothed)
    except Exception as e:
        console.print(f"[yellow]⚠ pose pipeline failed: {e}[/yellow]")
        return None


def run_critique(
    student_clip: str,
    references: list[dict],
    shot_type: str,
    coaching_context: list[dict] | None,
    mode: str = "single_ball",
    model: str = "gemini-2.5-flash",
    player_name: str = "the player",
    reference_player: str | None = None,
    auto_anchor: bool = True,
) -> dict | None:
    # Note: empty references no longer aborts — solo mode is supported.
    try:
        from ai_coach.lib.few_shot_critique import critique_against_references
    except Exception as e:
        console.print(f"[yellow]⚠ critique import failed: {e}[/yellow]")
        return None
    try:
        return critique_against_references(
            student_clip=student_clip,
            reference_clips=references,
            shot_type=shot_type,
            coaching_context=coaching_context or None,
            mode=mode,
            model=model,
            player_name=player_name,
            reference_player=reference_player,
            auto_anchor=auto_anchor,
        )
    except Exception as e:
        console.print(f"[yellow]⚠ critique failed: {e}[/yellow]")
        return None


def load_critique_from_json(path: str) -> dict | None:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as e:
        console.print(f"[red]✗ failed to load critique JSON {path}: {e}[/red]")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a 1-page hybrid PDF briefing for a single ball / single clip."
    )
    parser.add_argument("--clip", required=True, help="Path to the student/match clip.")
    parser.add_argument("--player", required=True, help="Player name shown in the briefing header.")
    parser.add_argument("--shot-type", required=True, help="Shot label, e.g. cover_drive, pull, defend.")
    parser.add_argument("--references", nargs="*", default=[],
                        help="Zero or more 'path' or 'path:Player Name' reference clips.")
    parser.add_argument("--coaching-keys", default=None,
                        help="Comma-separated coaching corpus keys.")
    parser.add_argument("--out", required=True, help="Output PDF path.")
    parser.add_argument("--academy", default=None, help="Academy name shown in subtitle.")
    parser.add_argument("--ball-id", default=None, help="Optional ball ID shown in header.")
    parser.add_argument("--skip-pose", action="store_true",
                        help="Skip MediaPipe pose extraction (run in main venv without venv312).")
    parser.add_argument("--skip-gemini", action="store_true",
                        help="Skip Gemini extraction (e.g. when working offline).")
    parser.add_argument("--model", default="gemini-2.5-flash",
                        help="Gemini model used for extraction + critique. "
                             "Try gemini-3.1-flash-lite-preview if 2.5-flash 503s.")
    parser.add_argument("--critique-json", default=None,
                        help="Load a pre-computed critique JSON from this path INSTEAD of re-running "
                             "the critique. Useful when you already ran scripts/critique_student_clip.py.")
    parser.add_argument("--mode", default="single_ball",
                        choices=["single_ball", "net_session"],
                        help="single_ball (default) — clip is ONE delivery. "
                             "net_session — clip is a net practice with multiple attempts; "
                             "deviations describe recurring patterns across attempts.")
    parser.add_argument("--reference-player", default=None,
                        help="Solo-mode anchor: name a famous player (e.g. 'Virat Kohli') "
                             "to use as the canonical reference. Overrides auto-anchor. "
                             "Ignored when --references is also provided.")
    parser.add_argument("--no-auto-anchor", action="store_true",
                        help="Disable canonical player auto-anchor in solo mode. "
                             "Use generic textbook-ideal prompt instead.")
    parser.add_argument("--skip-catalog", action="store_true",
                        help="In net_session mode, skip the batch-extract pre-pass that "
                             "counts deliveries by shot type for the PDF footer. "
                             "Saves one Gemini call (~₹2).")
    parser.add_argument("--catalog-model", default="gemini-2.5-pro",
                        help="Model used for the net-session catalog pre-pass. "
                             "Default is gemini-2.5-pro (flagship — strongest at "
                             "exhaustive enumeration over long videos). Lite/flash "
                             "variants tend to summarize and undercount.")
    parser.add_argument("--force-catalog", action="store_true",
                        help="Use the catalog count even if the anomaly detector "
                             "thinks the model undercounted. Useful for very slow / "
                             "paused net sessions where the natural ball rate is low.")
    parser.add_argument("--match-id", default=None,
                        help="Match/session ID for DB storage (default: player-slug + date). "
                             "Used to group balls for weakness analysis later.")
    parser.add_argument("--no-db", action="store_true",
                        help="Skip saving to database (default: always save for weakness analysis).")
    args = parser.parse_args()

    if not Path(args.clip).exists():
        console.print(f"[red]✗ clip not found:[/red] {args.clip}")
        return 1

    references = [parse_reference(r) for r in args.references]
    for r in references:
        if not Path(r["path"]).exists():
            console.print(f"[red]✗ reference clip not found:[/red] {r['path']}")
            return 1

    coaching_keys = []
    if args.coaching_keys:
        coaching_keys = [k.strip() for k in args.coaching_keys.split(",") if k.strip()]

    console.print()
    console.print(f"[bold cyan]Hybrid Player Briefing[/bold cyan]")
    console.print(f"  player:    {args.player}")
    console.print(f"  shot:      {args.shot_type}")
    console.print(f"  clip:      {args.clip}")
    console.print(f"  refs:      {len(references)}")
    console.print(f"  coaching:  {len(coaching_keys)} key(s)")
    console.print(f"  out:       {args.out}")
    console.print()

    # 1. Coaching context (lookup is cheap — do this first)
    console.print(f"[bold]Step 1/5:[/bold] load coaching context")
    coaching_context = load_coaching_context(coaching_keys)

    # 2. Gemini extraction
    console.print(f"\n[bold]Step 2/5:[/bold] Gemini extraction")
    gemini = None if args.skip_gemini else run_gemini_extraction(args.clip, model=args.model)
    if gemini:
        console.print(f"  shot={gemini.get('shot_type')} length={gemini.get('length')} outcome={gemini.get('outcome')}")

    # 3. Pose pipeline
    console.print(f"\n[bold]Step 3/5:[/bold] MediaPipe pose")
    pose_features = None if args.skip_pose else run_pose_pipeline(args.clip)
    if pose_features and "error" not in pose_features:
        console.print(f"  head_offset={pose_features.get('head_lateral_offset')} "
                      f"stride={pose_features.get('stride_length_norm')}")
    elif pose_features:
        console.print(f"  [yellow]pose error: {pose_features['error']}[/yellow]")

    # 4. Critique — either load pre-computed JSON or run live
    console.print(f"\n[bold]Step 4/5:[/bold] few-shot critique  (mode={args.mode})")
    if args.critique_json:
        console.print(f"  loading pre-computed critique → {args.critique_json}")
        critique = load_critique_from_json(args.critique_json)
    else:
        critique = run_critique(
            args.clip, references, args.shot_type, coaching_context,
            mode=args.mode, model=args.model, player_name=args.player,
            reference_player=args.reference_player,
            auto_anchor=not args.no_auto_anchor,
        )
    if critique:
        console.print(f"  rating={critique.get('overall_quality_rating')} "
                      f"deviations={len(critique.get('deviations', []) or [])}")

    # 4.5 (net_session only) — catalog pre-pass for PDF footer
    shot_counts = None
    contact_counts = None
    catalog_records = None
    if args.mode == "net_session" and not args.skip_catalog:
        console.print(f"\n[bold]Step 4.5/5:[/bold] net-session catalog pre-pass  "
                      f"(model={args.catalog_model})")
        catalog_result = run_session_catalog(
            args.clip,
            model=args.catalog_model,
            force=args.force_catalog,
        )
        if catalog_result:
            shot_counts, contact_counts, catalog_records = catalog_result
            total = sum(shot_counts.values())
            shot_breakdown = ", ".join(
                f"{n} {s}" for s, n in sorted(shot_counts.items(), key=lambda kv: -kv[1])
            )
            console.print(f"  shots ({total}): {shot_breakdown}")
            if contact_counts:
                contact_breakdown = ", ".join(
                    f"{n} {c}" for c, n in sorted(contact_counts.items(), key=lambda kv: -kv[1])
                )
                console.print(f"  contact: {contact_breakdown}")

    # 4.9 — save to DB for weakness analysis (unless --no-db)
    if not args.no_db:
        player_slug = args.player.lower().replace(" ", "-")
        match_id = args.match_id or f"{player_slug}-{datetime.now().strftime('%Y%m%d')}"
        saved = _save_to_db(
            player=args.player,
            shot_type=args.shot_type,
            clip_path=args.clip,
            match_id=match_id,
            gemini=gemini,
            records=catalog_records,
        )
        if saved:
            console.print(
                f"\n[green]✓[/green] {saved} ball(s) saved to DB "
                f"(match_id={match_id}) — run weakness analysis with:\n"
                f"  python scripts/analyse_batsman_weakness.py "
                f"--batsman \"{args.player}\" --min-confidence 0.0 --pitch-map"
            )

    # 5. Assemble + render
    console.print(f"\n[bold]Step 5/5:[/bold] assemble + render PDF")
    from ai_coach.lib.briefing import assemble_briefing
    from ai_coach.report.pdf import render_briefing_pdf

    briefing = assemble_briefing(
        player_name=args.player,
        shot_type=args.shot_type,
        clip_path=args.clip,
        gemini=gemini,
        pose_features=pose_features,
        critique=critique,
        coaching_context=coaching_context,
        reference_clips=references,
        coaching_keys=coaching_keys,
        ball_id=args.ball_id,
        academy=args.academy,
        mode=args.mode,
        shot_counts=shot_counts,
        contact_counts=contact_counts,
    )
    out_path = render_briefing_pdf(briefing, args.out)
    console.print(f"\n[bold green]done[/bold green] → {out_path}\n  open {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
