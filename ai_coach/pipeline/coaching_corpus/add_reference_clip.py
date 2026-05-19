"""
Add a YouTube clip to the reference shot library.

Downloads directly to data/reference_library/videos/<shot-slug>/<key>.mp4
(skips data/raw_videos/ for cleaner organization), then optionally runs
the pose pipeline to populate validation gates and update index.yaml.

Usage:
    # Just download into the library
    python scripts/add_reference_clip.py \\
        --url "https://youtube.com/shorts/EXAMPLE" \\
        --key kohli-cover-3 \\
        --shot-type cover_drive \\
        --player "Virat Kohli"

    # Download + validate via pose (REQUIRES venv312 — MediaPipe needed)
    python scripts/add_reference_clip.py \\
        --url "https://youtube.com/shorts/EXAMPLE" \\
        --key kohli-cover-3 \\
        --shot-type cover_drive \\
        --player "Virat Kohli" \\
        --validate
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Make `src.*` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import yaml
from rich.console import Console

console = Console()

LIBRARY_ROOT = Path("data/reference_library")
VIDEOS_ROOT = LIBRARY_ROOT / "videos"
INDEX_YAML = LIBRARY_ROOT / "index.yaml"


def shot_slug(shot_type: str) -> str:
    """cover_drive -> cover-drive (used as subdir name)."""
    return shot_type.replace("_", "-").lower()


def download_youtube(url: str, out_path: Path) -> Path:
    """Download via yt-dlp directly to out_path (no intermediate raw_videos)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp not found in PATH. pip install yt-dlp")

    console.print(f"[blue]⟳[/blue] downloading {url} → {out_path}")
    subprocess.run(
        [
            "yt-dlp",
            "-f", "best[ext=mp4]/best",
            "-o", str(out_path),
            "--no-playlist",
            "--quiet", "--no-warnings",
            url,
        ],
        check=True,
    )
    if not out_path.exists():
        raise RuntimeError(f"yt-dlp succeeded but file missing: {out_path}")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    console.print(f"[green]✓[/green] downloaded {out_path.name} ({size_mb:.2f} MB)")
    return out_path


def run_pose_validation(clip_path: Path) -> dict | None:
    """Run pose extraction + features. Returns validation dict or None on failure.
    Requires MediaPipe (venv312)."""
    try:
        from ai_coach.lib.pose.extractor import extract_pose_from_clip
        from ai_coach.lib.pose.smoothing import smooth_landmarks
        from ai_coach.lib.pose.features.batsman import compute_features
    except RuntimeError as e:
        console.print(f"[yellow]⚠ pose validation skipped:[/yellow] {e}")
        return None

    pose_out = clip_path.with_suffix(".pose.json")
    features_out = clip_path.with_suffix(".features.json")

    pose = extract_pose_from_clip(str(clip_path), output_path=str(pose_out))
    smoothed = smooth_landmarks(pose, window=5, max_gap=3)
    features = compute_features(smoothed)
    features_out.write_text(json.dumps(features, indent=2))
    console.print(f"[green]✓[/green] features saved → {features_out}")

    if "error" in features:
        return {
            "detection_rate":    pose.get("detection_rate"),
            "mean_confidence":   pose.get("mean_confidence"),
            "side_on_camera":    None,
            "head_over_ball":    None,
            "stride_adequate":   None,
            "gemini_shot_match": None,
            "_pose_error":       features["error"],
        }
    return {
        "detection_rate":    pose.get("detection_rate"),
        "mean_confidence":   pose.get("mean_confidence"),
        "side_on_camera":    features.get("side_on_camera"),
        "head_over_ball":    features.get("head_over_ball"),
        "stride_adequate":   features.get("stride_adequate"),
        "gemini_shot_match": None,    # filled in by future Gemini-extract step
    }


def determine_quality_rating(validation: dict | None) -> str:
    if not validation:
        return "pending"
    gates = [
        (validation.get("detection_rate") or 0) >= 0.85,
        (validation.get("mean_confidence") or 0) >= 0.70,
        validation.get("side_on_camera") is True,
        validation.get("head_over_ball") is True,
        validation.get("stride_adequate") is True,
        validation.get("gemini_shot_match") is True,
    ]
    n_pass = sum(bool(g) for g in gates)
    if n_pass >= 6:
        return "gold"
    if n_pass >= 4:
        return "silver"
    if n_pass >= 1:
        return "bronze"
    return "pending"


def load_index() -> dict:
    if not INDEX_YAML.exists():
        return {"clips": []}
    with INDEX_YAML.open() as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("clips", [])
    return data


def save_index(data: dict) -> None:
    INDEX_YAML.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_YAML.open("w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def upsert_entry(data: dict, entry: dict) -> None:
    """Replace existing clip with same key, else append."""
    data["clips"] = [c for c in data["clips"] if c.get("key") != entry["key"]]
    data["clips"].append(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a clip to the reference shot library.")
    parser.add_argument("--url", required=True, help="YouTube URL.")
    parser.add_argument("--key", required=True, help="Slug for this clip, e.g. kohli-cover-3.")
    parser.add_argument("--shot-type", required=True,
                        help="e.g. cover_drive, pull, defend, sweep. Determines subdir.")
    parser.add_argument("--shot-subtype", default=None,
                        help="Finer label, free-form. Defaults to --shot-type.")
    parser.add_argument("--player", default="", help="Player name shown in clip, e.g. 'Virat Kohli'.")
    parser.add_argument("--handedness", default="right", choices=["right", "left"])
    parser.add_argument("--notes", default="", help="Free-text notes appended to the entry.")
    parser.add_argument("--validate", action="store_true",
                        help="Run pose pipeline immediately to populate validation gates. "
                             "Requires MediaPipe (venv312).")
    parser.add_argument("--force-overwrite", action="store_true",
                        help="Re-download even if the file already exists.")
    args = parser.parse_args()

    slug = shot_slug(args.shot_type)
    out_dir = VIDEOS_ROOT / slug
    out_path = out_dir / f"{args.key}.mp4"

    console.print()
    console.print(f"[bold cyan]Add Reference Clip[/bold cyan]")
    console.print(f"  url:        {args.url}")
    console.print(f"  key:        {args.key}")
    console.print(f"  shot:       {args.shot_type} (slug: {slug})")
    console.print(f"  player:     {args.player or '(unspecified)'}")
    console.print(f"  out:        {out_path}")
    console.print(f"  validate:   {args.validate}")
    console.print()

    # 1. Download
    if out_path.exists() and not args.force_overwrite:
        console.print(f"[yellow]⚠[/yellow] file already exists, skipping download (use --force-overwrite to redo)")
    else:
        download_youtube(args.url, out_path)

    # 2. Optional pose validation
    validation = run_pose_validation(out_path) if args.validate else None
    if validation:
        console.print(f"[bold]Validation:[/bold]")
        for k, v in validation.items():
            console.print(f"  {k:18} {v}")

    # 3. Build entry + upsert into index.yaml
    quality = determine_quality_rating(validation)
    entry = {
        "key":           args.key,
        "shot_type":     args.shot_type,
        "shot_subtype":  args.shot_subtype or args.shot_type,
        "player":        args.player,
        "handedness":    args.handedness,
        "source_url":    args.url,
        "clip_path":     str(out_path),
        "pose_path":     str(out_path.with_suffix(".pose.json")) if args.validate else None,
        "features_path": str(out_path.with_suffix(".features.json")) if args.validate else None,
        "quality_rating": quality,
        "validation":    validation or {
            "detection_rate":    None,
            "mean_confidence":   None,
            "side_on_camera":    None,
            "head_over_ball":    None,
            "stride_adequate":   None,
            "gemini_shot_match": None,
        },
        "notes":         args.notes,
    }

    index = load_index()
    upsert_entry(index, entry)
    save_index(index)
    console.print(f"[green]✓[/green] manifest updated → {INDEX_YAML} (rating: [bold]{quality}[/bold])")

    return 0


if __name__ == "__main__":
    sys.exit(main())
