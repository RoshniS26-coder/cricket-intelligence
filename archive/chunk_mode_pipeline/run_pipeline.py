"""
Cricket Intelligence Engine - Main Pipeline Runner
Orchestrates the full pipeline: ingest → segment → extract → validate → store.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()


def _video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _cut_chunk(video_path: str, start_sec: float, duration: float, out_path: str) -> bool:
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start_sec), "-i", video_path,
            "-t", str(duration),
            "-c", "copy", "-avoid_negative_ts", "make_zero",
            out_path,
        ],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def run_full_pipeline(
    video_path: str = None,
    youtube_url: str = None,
    match_id: str = "test_match_001",
    format_type: str = "T20",
    team_a: str = "Team A",
    team_b: str = "Team B",
    timestamps_file: str = None,
    use_uniform_split: bool = False,
    segment_duration: float = 8.0,
    max_clips: int = 30,
    gemini_model: str = "gemini-2.5-flash",
    skip_extraction: bool = False,
    batch_mode: bool = False,            # send full video to Gemini, skip segmentation
    batsman_name: str = None,            # Override batsman_name for all extracted balls
    chunk_mode: bool = False,            # Gemini chunk segmentation → timestamps → per-clip extraction
    chunk_duration: float = 90.0,        # seconds per chunk sent to Gemini
):
    """Run the complete cricket intelligence pipeline.

    The CV-augmented variant — `--cv-segment` mode (OpenCV delivery tracker),
    `--no-cv` toggle, and Step 2.5 Roboflow line/length pre-analysis — is
    archived in CV_Enhancements/pipeline/run_pipeline_with_cv.py for the day
    you switch off pure-Gemini and back to CV grounding.
    """

    console.print(Panel.fit(
        "[bold cyan]🏏 Cricket Intelligence Engine[/bold cyan]\n"
        "Ball-Level Video Understanding Pipeline",
        border_style="cyan",
    ))

    # ===== Step 1: Video Ingestion =====
    console.print("\n[bold]Step 1: Video Ingestion[/bold]")

    from src.ingestion.downloader import VideoIngestion
    ingestion = VideoIngestion()

    if youtube_url:
        metadata = ingestion.download_from_youtube(
            youtube_url, match_id, format_type, team_a, team_b
        )
        if not metadata:
            console.print("[red]Failed to download video. Exiting.[/red]")
            return
        video_path = metadata["video_path"]
    elif video_path:
        metadata = ingestion.register_local_video(
            video_path, match_id, format_type, team_a, team_b
        )
    else:
        console.print("[red]Provide --video or --youtube-url[/red]")
        return

    # ===== Batch Mode: full video → Gemini auto-detects deliveries =====
    if batch_mode:
        console.print("\n[bold cyan]Batch Mode: Full Video → Gemini Auto-Detection[/bold cyan]")
        console.print("  [dim]Skipping ffmpeg segmentation — Gemini will identify all ball deliveries[/dim]")

        from src.intelligence.extractor import GeminiExtractor
        gemini = GeminiExtractor(model_name=gemini_model)
        records = gemini.extract_from_video(video_path, match_id=match_id)

        if batsman_name and records:
            for r in records:
                r.batsman_name = batsman_name

        if not records:
            console.print("[red]✗ No deliveries detected. Exiting.[/red]")
            return

        console.print(f"\n[bold]Step 4: Validation & Normalization[/bold]")
        from src.validation.normalizer import BallRecordValidator
        validator = BallRecordValidator()
        validated_records, val_stats = validator.validate_batch(records)

        console.print(f"\n[bold]Step 5: Database Storage[/bold]")
        from src.storage.db import CricketDB
        db = CricketDB()
        db.create_match({"match_id": match_id, "format": format_type, "team_a": team_a, "team_b": team_b})
        db.save_balls_batch(validated_records)

        output_json = f"data/{match_id}_extracted.json"
        gemini.export_to_json(validated_records, output_json)

        stats = db.get_stats(match_id)
        batsman_line = f"\nBatsman label: {batsman_name}" if batsman_name else ""
        weakness_cmd = (
            f"  3. Weakness: python features/batsman_analysis/analyse_batsman_weakness.py --batsman \"{batsman_name}\" --min-confidence 0.0"
            if batsman_name else
            "  3. Weakness: python features/batsman_analysis/analyse_batsman_weakness.py --batsman <name>"
        )
        console.print(Panel.fit(
            f"[bold green]✅ Batch Pipeline Complete![/bold green]\n\n"
            f"Match: {match_id} ({team_a} vs {team_b}){batsman_line}\n"
            f"Balls detected by Gemini: {stats['total']}\n"
            f"Avg confidence: {stats['avg_confidence']:.1%}\n"
            f"JSON export: {output_json}\n\n"
            f"[cyan]Next steps:[/cyan]\n"
            f"  1. Review: streamlit run ui/app.py\n"
            f"  2. API: python -m src.api.main\n"
            f"{weakness_cmd}",
            border_style="green",
        ))
        return

    # ===== Chunk Mode: FFmpeg chunks → batch Gemini analysis per chunk =====
    if chunk_mode:
        console.print("\n[bold cyan]Chunk Mode: FFmpeg → Gemini Batch Analysis per Chunk[/bold cyan]")
        console.print(
            f"  [dim]Cuts video into {chunk_duration:.0f}s chunks, sends each to Gemini "
            f"(BATCH_EXTRACTION_PROMPT — same as batch mode but chunk by chunk)[/dim]"
        )

        import tempfile
        from src.intelligence.extractor import GeminiExtractor

        gemini = GeminiExtractor(model_name=gemini_model)
        all_records = []
        total_balls_so_far = 0

        try:
            total_sec = _video_duration(video_path)
        except Exception as e:
            console.print(f"[red]✗ ffprobe failed: {e}[/red]")
            return

        n_chunks = int(total_sec / chunk_duration) + (1 if total_sec % chunk_duration else 0)
        console.print(f"  Video: {total_sec:.0f}s → {n_chunks} × {chunk_duration:.0f}s chunks\n")

        with tempfile.TemporaryDirectory(prefix="cricket_chunks_") as tmpdir:
            for i in range(n_chunks):
                chunk_start = i * chunk_duration
                chunk_path = str(Path(tmpdir) / f"chunk_{i:04d}.mp4")

                ok = _cut_chunk(video_path, chunk_start, chunk_duration, chunk_path)
                if not ok or not Path(chunk_path).exists():
                    console.print(f"  [yellow]⚠ Chunk {i}: ffmpeg cut failed, skipping[/yellow]")
                    continue

                console.print(f"  [bold]Chunk {i+1}/{n_chunks}[/bold] (+{chunk_start:.0f}s)")
                chunk_records = gemini.extract_from_video(
                    chunk_path,
                    match_id=match_id,
                    innings=1,
                    chunk_offset=chunk_start,
                    ball_index_offset=total_balls_so_far,
                )
                all_records.extend(chunk_records)
                total_balls_so_far += len(chunk_records)

        if not all_records:
            console.print("[red]✗ No deliveries detected across all chunks.[/red]")
            return

        if batsman_name:
            for r in all_records:
                r.batsman_name = batsman_name

        console.print(f"\n[green]✓ {len(all_records)} ball records from {n_chunks} chunks[/green]")

        console.print(f"\n[bold]Step 4: Validation & Normalization[/bold]")
        from src.validation.normalizer import BallRecordValidator
        validator = BallRecordValidator()
        validated_records, _ = validator.validate_batch(all_records)

        console.print(f"\n[bold]Step 5: Database Storage[/bold]")
        from src.storage.db import CricketDB
        db = CricketDB()
        db.create_match({"match_id": match_id, "format": format_type, "team_a": team_a, "team_b": team_b})
        db.save_balls_batch(validated_records)

        output_json = f"data/{match_id}_extracted.json"
        gemini.export_to_json(validated_records, output_json)

        stats = db.get_stats(match_id)
        batsman_line = f"\nBatsman label: {batsman_name}" if batsman_name else ""
        weakness_cmd = (
            f"  3. Weakness: python features/batsman_analysis/analyse_batsman_weakness.py --batsman \"{batsman_name}\" --min-confidence 0.0"
            if batsman_name else
            "  3. Weakness: python features/batsman_analysis/analyse_batsman_weakness.py --batsman <name>"
        )
        console.print(Panel.fit(
            f"[bold green]✅ Chunk Mode Pipeline Complete![/bold green]\n\n"
            f"Match: {match_id} ({team_a} vs {team_b}){batsman_line}\n"
            f"Chunks processed: {n_chunks}\n"
            f"Balls detected: {stats['total']}\n"
            f"Avg confidence: {stats['avg_confidence']:.1%}\n"
            f"JSON export: {output_json}\n\n"
            f"[cyan]Next steps:[/cyan]\n"
            f"  1. Review: streamlit run ui/app.py\n"
            f"  2. API: python -m src.api.main\n"
            f"{weakness_cmd}",
            border_style="green",
        ))
        return

    # ===== Step 2: Ball Segmentation =====
    console.print("\n[bold]Step 2: Ball Clip Segmentation[/bold]")

    from src.segmentation.clip_extractor import ClipExtractor
    extractor = ClipExtractor()

    if timestamps_file:
        clips = extractor.extract_from_timestamps(video_path, timestamps_file, match_id)
    elif use_uniform_split:
        clips = extractor.extract_uniform_segments(
            video_path, match_id,
            segment_duration=segment_duration,
            max_clips=max_clips,
        )
    else:
        console.print(
            "[yellow]⚠ No timestamps provided.[/yellow]\n"
            "Use --timestamps FILE or --uniform to split the video.\n"
            "Generate a template with: python -m src.segmentation.clip_extractor "
            f"--template --match-id {match_id}"
        )
        return

    clip_paths = [c["clip_path"] for c in clips if c.get("clip_path")]
    console.print(f"[green]✓ {len(clip_paths)} clips ready[/green]")

    if skip_extraction:
        console.print("[yellow]Skipping Gemini extraction (--skip-extraction)[/yellow]")
        return

    # ===== Step 3: Gemini Intelligence Extraction =====
    console.print("\n[bold]Step 3: Gemini Intelligence Extraction[/bold]")

    from src.intelligence.extractor import GeminiExtractor
    gemini = GeminiExtractor(model_name=gemini_model)

    clips_dir = f"data/ball_clips/{match_id}"
    records = gemini.extract_batch(clips_dir, match_id=match_id)

    if batsman_name and records:
        for r in records:
            r.batsman_name = batsman_name

    # ===== Step 4: Validation =====
    console.print("\n[bold]Step 4: Validation & Normalization[/bold]")

    from src.validation.normalizer import BallRecordValidator
    validator = BallRecordValidator()
    validated_records, val_stats = validator.validate_batch(records)

    # ===== Step 5: Storage =====
    console.print("\n[bold]Step 5: Database Storage[/bold]")

    from src.storage.db import CricketDB
    db = CricketDB()

    db.create_match({
        "match_id": match_id,
        "format": format_type,
        "team_a": team_a,
        "team_b": team_b,
    })

    saved = db.save_balls_batch(validated_records)

    # ===== Step 6: Export =====
    output_json = f"data/{match_id}_extracted.json"
    gemini.export_to_json(validated_records, output_json)

    # ===== Summary =====
    stats = db.get_stats(match_id)
    console.print(Panel.fit(
        f"[bold green]✅ Pipeline Complete![/bold green]\n\n"
        f"Match: {match_id} ({team_a} vs {team_b})\n"
        f"Balls processed: {stats['total']}\n"
        f"Avg confidence: {stats['avg_confidence']:.1%}\n"
        f"Needs review: {stats['total'] - stats['reviewed']}\n"
        f"JSON export: {output_json}\n\n"
        f"[cyan]Next steps:[/cyan]\n"
        f"  1. Review: streamlit run ui/app.py\n"
        f"  2. API: python -m src.api.main\n"
        f"  3. Track ball: python -m src.tracking.tracker --video <clip>",
        border_style="green",
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="🏏 Cricket Intelligence Engine - Full Pipeline"
    )
    parser.add_argument("--video", type=str, help="Local video file path")
    parser.add_argument("--youtube-url", type=str, help="YouTube URL")
    parser.add_argument("--match-id", type=str, default="test_match_001")
    parser.add_argument("--format", type=str, default="T20")
    parser.add_argument("--team-a", type=str, default="Team A")
    parser.add_argument("--team-b", type=str, default="Team B")
    parser.add_argument("--timestamps", type=str, help="Timestamps JSON file")
    parser.add_argument("--uniform", action="store_true", help="Uniform split")
    parser.add_argument("--segment-duration", type=float, default=8.0)
    parser.add_argument("--max-clips", type=int, default=30)
    parser.add_argument("--model", type=str, default="gemini-2.5-flash")
    parser.add_argument("--skip-extraction", action="store_true")
    parser.add_argument("--batch-mode", action="store_true",
                        help="Send full video to Gemini — Gemini auto-detects all ball deliveries (no segmentation)")
    parser.add_argument("--batsman-name", type=str, default=None,
                        help="Override batsman name for all extracted balls (e.g. 'kohli-net-practice')")
    parser.add_argument("--chunk-mode", action="store_true",
                        help="Segment broadcast video via Gemini (90s chunks → live-play timestamps → per-clip extraction)")
    parser.add_argument("--chunk-duration", type=float, default=90.0,
                        help="Chunk length in seconds sent to Gemini for segmentation (default: 90)")
    args = parser.parse_args()

    run_full_pipeline(
        video_path=args.video,
        youtube_url=args.youtube_url,
        match_id=args.match_id,
        format_type=args.format,
        team_a=args.team_a,
        team_b=args.team_b,
        timestamps_file=args.timestamps,
        use_uniform_split=args.uniform,
        segment_duration=args.segment_duration,
        max_clips=args.max_clips,
        gemini_model=args.model,
        skip_extraction=args.skip_extraction,
        batch_mode=args.batch_mode,
        batsman_name=args.batsman_name,
        chunk_mode=args.chunk_mode,
        chunk_duration=args.chunk_duration,
    )
