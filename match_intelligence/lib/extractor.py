"""
Cricket Intelligence Engine - Gemini Vision Extractor
Sends ball clips to Gemini API and extracts structured cricket intelligence.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import track

from src.intelligence.schema import BallRecord, ConfidenceScores, GEMINI_JSON_SCHEMA
from src.intelligence.prompt import get_single_ball_prompt, get_system_prompt, get_batch_prompt

load_dotenv()
console = Console()


def _fmt_ts(seconds: float) -> str:
    """Format seconds as MM:SS for YouTube verification (e.g. 203.5 → '3:23')."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


class GeminiExtractor:
    """Extracts structured cricket intelligence from video clips using Gemini."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set it in .env file or environment.\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        console.print(f"[green]✓[/green] Gemini extractor initialized with model: {model_name}")

    def extract_from_clip(
        self,
        clip_path: str,
        match_id: str = "unknown",
        over: int = 0,
        ball_number: int = 1,
        innings: int = 1,
    ) -> Optional[BallRecord]:
        """
        Analyze a single ball clip and return structured data.

        Args:
            clip_path:   Path to the video clip file
            match_id:    Match identifier
            over:        Over number
            ball_number: Ball number within the over
            innings:     Innings number

        Returns:
            BallRecord with extracted fields, or None on failure

        Note: the Roboflow / CV-augmented variant of this method (with a
        cv_context kwarg, CV-augmented prompt, and line/length override)
        is archived in CV_Enhancements/pipeline/extractor_with_cv.py.
        """
        clip_file = Path(clip_path)
        if not clip_file.exists():
            console.print(f"[red]✗[/red] Clip not found: {clip_path}")
            return None

        try:
            console.print(f"[blue]⟳[/blue] Analyzing: {clip_file.name}...")

            # Upload the video file to Gemini
            uploaded_file = self.client.files.upload(file=clip_path)

            # Wait for processing
            while uploaded_file.state == "PROCESSING":
                time.sleep(2)
                uploaded_file = self.client.files.get(name=uploaded_file.name)

            if uploaded_file.state == "FAILED":
                console.print(f"[red]✗[/red] Video processing failed for {clip_file.name}")
                return None

            prompt_text = get_single_ball_prompt()

            # Call Gemini with structured output
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded_file.uri,
                                mime_type=uploaded_file.mime_type,
                            ),
                            types.Part.from_text(text=prompt_text),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(),
                    response_mime_type="application/json",
                    response_schema=GEMINI_JSON_SCHEMA,
                    temperature=0.2,
                ),
            )

            # Parse the response
            raw_json = json.loads(response.text)

            # Build BallRecord from Gemini's response
            ball_id = f"{match_id}_{over}_{ball_number}"
            record = BallRecord(
                ball_id=ball_id,
                match_id=match_id,
                innings=innings,
                over=over,
                ball_number=ball_number,
                bowler_type=raw_json.get("bowler_type", "unknown"),
                line=raw_json.get("line", "unknown"),
                length=raw_json.get("length", "unknown"),
                variation=raw_json.get("variation", "none"),
                shot_type=raw_json.get("shot_type", "unknown"),
                footwork=raw_json.get("footwork", "unknown"),
                contact_quality=raw_json.get("contact_quality", "unknown"),
                outcome=raw_json.get("outcome", "unknown"),
                bounce_behavior=raw_json.get("bounce_behavior", "unknown"),
                movement=raw_json.get("movement", "unknown"),
                # Delivery sub-type — default to UNKNOWN if Gemini didn't emit
                swing_direction=raw_json.get("swing_direction", "unknown"),
                swing_type=raw_json.get("swing_type", "unknown"),
                spin_direction=raw_json.get("spin_direction", "unknown"),
                ball_age_phase=raw_json.get("ball_age_phase", "unknown"),
                # Tier-1 analytics enrichment
                shot_direction=raw_json.get("shot_direction", "unknown"),
                dismissal_type=raw_json.get("dismissal_type", "none"),
                dismissal_fielder=(raw_json.get("dismissal_fielder") or None),
                # Gemini emits 0 when no speed graphic visible; treat as missing.
                bowling_speed_kmph=(raw_json.get("bowling_speed_kmph") or None),
                bowler_crease=raw_json.get("bowler_crease", "unknown"),
                edge_type=raw_json.get("edge_type", "none"),
                phase=raw_json.get("phase", "unknown"),
                batsman_handedness=raw_json.get("batsman_handedness", "unknown"),
                bowler_name=raw_json.get("bowler_name"),
                batsman_name=raw_json.get("batsman_name"),
                raw_description=raw_json.get("raw_description", ""),
                clip_path=str(clip_path),
                confidence=ConfidenceScores(**raw_json.get("confidence", {})),
            )

            # Log result
            avg_confidence = (
                record.confidence.line
                + record.confidence.length
                + record.confidence.shot_type
            ) / 3
            color = "green" if avg_confidence > 0.7 else "yellow" if avg_confidence > 0.4 else "red"
            console.print(
                f"[{color}]✓[/{color}] Ball {ball_id}: "
                f"{record.bowler_type.value} | {record.line.value} | "
                f"{record.length.value} | {record.shot_type.value} → "
                f"{record.outcome.value} (confidence: {avg_confidence:.2f})"
            )

            # Clean up uploaded file
            try:
                self.client.files.delete(name=uploaded_file.name)
            except Exception:
                pass  # Non-critical cleanup

            return record

        except Exception as e:
            console.print(f"[red]✗[/red] Error analyzing {clip_file.name}: {e}")
            return None

    def extract_batch(
        self,
        clips_dir: str,
        match_id: str = "unknown",
        innings: int = 1,
        start_over: int = 1,
    ) -> list[BallRecord]:
        """
        Process all clips in a directory.

        Args:
            clips_dir:   Directory containing ball clip videos
            match_id:    Match identifier
            innings:     Innings number
            start_over:  Starting over number for ball numbering

        Returns:
            List of BallRecord objects

        Note: the Roboflow / CV-augmented variant of this method (with a
        cv_contexts kwarg that grounds Gemini on per-clip stumps geometry)
        is archived in CV_Enhancements/pipeline/extractor_with_cv.py.
        """
        clips_path = Path(clips_dir)
        clip_files = sorted(clips_path.glob("*.mp4")) + sorted(clips_path.glob("*.webm"))

        if not clip_files:
            console.print(f"[red]✗[/red] No video clips found in {clips_dir}")
            return []

        console.print(f"\n[bold]Processing {len(clip_files)} clips from {clips_dir}[/bold]")

        records = []
        for i, clip_file in enumerate(track(clip_files, description="Extracting...")):
            over = start_over + (i // 6)   # 6 balls per over
            ball = (i % 6) + 1

            record = self.extract_from_clip(
                clip_path=str(clip_file),
                match_id=match_id,
                over=over,
                ball_number=ball,
                innings=innings,
            )

            if record:
                records.append(record)

            # Rate limiting — be kind to the API
            time.sleep(1)

        console.print(f"\n[bold green]✓ Extracted {len(records)}/{len(clip_files)} balls[/bold green]")
        return records

    def extract_from_video(
        self,
        video_path: str,
        match_id: str = "unknown",
        innings: int = 1,
        start_over: int = 1,
        chunk_offset: float = 0.0,
        ball_index_offset: int = 0,
    ) -> list[BallRecord]:
        """
        Send a full video to Gemini and let it auto-detect all ball deliveries.

        Gemini watches the entire video, identifies each delivery, and returns
        a JSON array — one object per ball. No ffmpeg segmentation required.

        Args:
            video_path:    Path to the full match/highlight video
            match_id:      Match identifier
            innings:       Innings number
            start_over:    Starting over number for ball numbering
            chunk_offset:  Seconds to add to every start_sec/end_sec Gemini returns,
                           so timestamps are absolute relative to the original full video.

        Returns:
            List of BallRecord objects, one per detected delivery
        """
        video_file = Path(video_path)
        if not video_file.exists():
            console.print(f"[red]✗[/red] Video not found: {video_path}")
            return []

        console.print(f"[blue]⟳[/blue] Uploading video to Gemini: {video_file.name}")
        console.print("  [dim]Gemini will auto-detect ball deliveries — no pre-segmentation[/dim]")

        try:
            uploaded_file = self.client.files.upload(file=video_path)

            while uploaded_file.state == "PROCESSING":
                time.sleep(2)
                uploaded_file = self.client.files.get(name=uploaded_file.name)

            if uploaded_file.state == "FAILED":
                console.print(f"[red]✗[/red] Video processing failed")
                return []

            batch_schema = {
                "type": "array",
                "items": GEMINI_JSON_SCHEMA,
            }

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded_file.uri,
                                mime_type=uploaded_file.mime_type,
                            ),
                            types.Part.from_text(text=get_batch_prompt()),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(),
                    response_mime_type="application/json",
                    response_schema=batch_schema,
                    temperature=0.2,
                ),
            )

            raw_list = json.loads(response.text)
            if not isinstance(raw_list, list):
                raw_list = [raw_list]

            console.print(f"[green]✓[/green] Gemini detected [bold]{len(raw_list)}[/bold] ball deliveries")

            records = []
            # ── Scoreboard validation + dedup ─────────────────────────────────────
            # Rules:
            #   1. Range:       over 1-50, ball_number 1-10 (extras can push past 6)
            #   2. Monotonic:   over.ball must not go backwards vs the last accepted ball
            #   3. Dedup:       same (over, ball_number) already seen = replay = skip
            #   4. Duration:    fallback when no scoreboard — skip sub-2s frames
            # Bad OCR → field is cleared (set to 0) and sequential fallback applies.
            seen_over_balls: set[tuple[int, int]] = set()
            last_accepted: tuple[int, int] = (0, 0)   # (over, ball) of most recent live delivery
            filtered_list = []

            for raw_json in raw_list:
                gemini_over = raw_json.get("over", 0) or 0
                gemini_ball = raw_json.get("ball_number", 0) or 0
                start_sec_raw = raw_json.get("start_sec")
                end_sec_raw   = raw_json.get("end_sec")

                scoreboard_ok = False
                if gemini_over and gemini_ball:
                    # Rule 1 — range check
                    if not (1 <= gemini_over <= 50 and 1 <= gemini_ball <= 10):
                        console.print(
                            f"  [yellow]⚠ Bad OCR: over={gemini_over} ball={gemini_ball} out of range — using sequential[/yellow]"
                        )
                        raw_json["over"] = 0
                        raw_json["ball_number"] = 0
                    else:
                        key = (gemini_over, gemini_ball)

                        # Rule 2 — monotonicity: reject if scoreboard went backwards
                        last_seq = last_accepted[0] * 10 + last_accepted[1]
                        this_seq = gemini_over * 10 + gemini_ball
                        if last_accepted != (0, 0) and this_seq < last_seq:
                            console.print(
                                f"  [yellow]⚠ Scoreboard went backwards {last_accepted[0]}.{last_accepted[1]} → {gemini_over}.{gemini_ball} — replay or bad OCR, skipping[/yellow]"
                            )
                            continue

                        # Rule 3 — dedup: same over.ball already recorded = replay
                        if key in seen_over_balls:
                            console.print(
                                f"  [dim]Skipping replay: {gemini_over}.{gemini_ball} already seen[/dim]"
                            )
                            continue

                        seen_over_balls.add(key)
                        last_accepted = key
                        scoreboard_ok = True

                if not scoreboard_ok:
                    # Rule 4 — no valid scoreboard: duration filter as safety net
                    if start_sec_raw is not None and end_sec_raw is not None:
                        if end_sec_raw - start_sec_raw < 2.0:
                            console.print(
                                f"  [dim]Skipping short frame ({end_sec_raw - start_sec_raw:.2f}s < 2s)[/dim]"
                            )
                            continue

                filtered_list.append(raw_json)

            for i, raw_json in enumerate(filtered_list):
                # Use validated scoreboard over/ball; fall back to sequential
                gemini_over = raw_json.get("over", 0) or 0
                gemini_ball = raw_json.get("ball_number", 0) or 0
                if gemini_over and gemini_ball:
                    over = gemini_over
                    ball = gemini_ball
                else:
                    global_index = ball_index_offset + i
                    over = 1 + (global_index // 6)
                    ball = (global_index % 6) + 1
                ball_id = f"{match_id}_{over}_{ball}"

                # Compute absolute timestamps (clip-relative + offset into full video)
                start_sec = raw_json.get("start_sec")
                end_sec   = raw_json.get("end_sec")
                abs_start = round(chunk_offset + start_sec, 2) if start_sec is not None else None
                abs_end   = round(chunk_offset + end_sec,   2) if end_sec   is not None else None
                ts_label  = (
                    f"{_fmt_ts(abs_start)}–{_fmt_ts(abs_end)} ({abs_start}s–{abs_end}s)"
                    if abs_start is not None else None
                )

                record = BallRecord(
                    ball_id=ball_id,
                    match_id=match_id,
                    innings=innings,
                    over=over,
                    ball_number=ball,
                    bowler_type=raw_json.get("bowler_type", "unknown"),
                    line=raw_json.get("line", "unknown"),
                    length=raw_json.get("length", "unknown"),
                    variation=raw_json.get("variation", "none"),
                    shot_type=raw_json.get("shot_type", "unknown"),
                    footwork=raw_json.get("footwork", "unknown"),
                    contact_quality=raw_json.get("contact_quality", "unknown"),
                    outcome=raw_json.get("outcome", "unknown"),
                    runs_scored=raw_json.get("runs_scored", 0),
                    bounce_behavior=raw_json.get("bounce_behavior", "unknown"),
                    movement=raw_json.get("movement", "unknown"),
                    swing_direction=raw_json.get("swing_direction", "unknown"),
                    swing_type=raw_json.get("swing_type", "unknown"),
                    spin_direction=raw_json.get("spin_direction", "unknown"),
                    ball_age_phase=raw_json.get("ball_age_phase", "unknown"),
                    # Tier-1 analytics enrichment
                    shot_direction=raw_json.get("shot_direction", "unknown"),
                    dismissal_type=raw_json.get("dismissal_type", "none"),
                    dismissal_fielder=(raw_json.get("dismissal_fielder") or None),
                    bowling_speed_kmph=(raw_json.get("bowling_speed_kmph") or None),
                    bowler_crease=raw_json.get("bowler_crease", "unknown"),
                    edge_type=raw_json.get("edge_type", "none"),
                    phase=raw_json.get("phase", "unknown"),
                    batsman_handedness=raw_json.get("batsman_handedness", "unknown"),
                    bowler_name=raw_json.get("bowler_name"),
                    batsman_name=raw_json.get("batsman_name"),
                    raw_description=raw_json.get("raw_description", ""),
                    clip_path=str(video_path),
                    clip_start_time=f"{_fmt_ts(abs_start)} ({abs_start}s)" if abs_start is not None else None,
                    clip_end_time=f"{_fmt_ts(abs_end)} ({abs_end}s)"     if abs_end   is not None else None,
                    confidence=ConfidenceScores(**raw_json.get("confidence", {})),
                )
                records.append(record)

                conf = (record.confidence.line + record.confidence.length + record.confidence.shot_type) / 3
                color = "green" if conf > 0.7 else "yellow" if conf > 0.4 else "red"
                ts_str = f" [dim]{ts_label}[/dim]" if ts_label else ""
                console.print(
                    f"  [{color}]Ball {ball_id}[/{color}]: "
                    f"{record.bowler_type.value} | {record.line.value} | "
                    f"{record.length.value} | {record.shot_type.value} → "
                    f"{record.outcome.value} (conf: {conf:.2f}){ts_str}"
                )

            try:
                self.client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            return records

        except Exception as e:
            err_str = str(e)
            console.print(f"[red]✗[/red] Batch video analysis failed: {e}")
            # Fail-fast on auth errors — no point retrying 70 more chunks
            if "PERMISSION_DENIED" in err_str or "API key" in err_str or "401" in err_str or "403" in err_str:
                console.print(
                    "[bold red]✗ API key error — aborting pipeline. "
                    "Update GEMINI_API_KEY in .env before retrying.[/bold red]"
                )
                raise RuntimeError("Gemini API key invalid or revoked") from e
            return []

    def export_to_json(self, records: list[BallRecord], output_path: str) -> None:
        """Export ball records to a JSON file."""
        data = [record.model_dump(mode="json") for record in records]
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"[green]✓[/green] Exported {len(records)} records to {output_path}")


# ===== CLI Entry Point =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract cricket intelligence from ball clips")
    parser.add_argument("--clip", type=str, help="Path to a single ball clip")
    parser.add_argument("--dir", type=str, help="Directory of ball clips")
    parser.add_argument("--match-id", type=str, default="test_match_001")
    parser.add_argument("--output", type=str, default="data/extracted_balls.json")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash")
    args = parser.parse_args()

    extractor = GeminiExtractor(model_name=args.model)

    if args.clip:
        record = extractor.extract_from_clip(args.clip, match_id=args.match_id)
        if record:
            extractor.export_to_json([record], args.output)
    elif args.dir:
        records = extractor.extract_batch(args.dir, match_id=args.match_id)
        extractor.export_to_json(records, args.output)
    else:
        parser.print_help()
