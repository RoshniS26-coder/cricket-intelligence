"""
Cricket video analysis benchmark CLI.
Runs a video chunk through multiple models with NO Cricsheet or ESPN integration.
Each model receives only the raw video (or extracted frames) and returns structured fields.

Usage:
  python -m benchmark.run_benchmark --list-models
  python -m benchmark.run_benchmark --video data/raw_videos/chunk.mp4 --models gemini-2.5-pro gemini-2.5-flash
  python -m benchmark.run_benchmark --video data/raw_videos/chunk.mp4 --models llava:13b --frames-per-ball 6
  python -m benchmark.run_benchmark --video data/raw_videos/chunk.mp4 --models gemini-2.5-pro --dry-run
"""
from __future__ import annotations
import argparse, sys
from collections import defaultdict
from pathlib import Path

from benchmark.config import MODELS, BENCHMARK_FIELDS
from benchmark.runners.video_only_runner import VideoOnlyRunner
from benchmark.report import print_report


def _runner(model_key: str, frames_per_ball: int) -> VideoOnlyRunner:
    cfg = MODELS[model_key]
    return VideoOnlyRunner(
        model_key=model_key,
        provider=cfg["provider"],
        model_id=cfg["model_id"],
        supports_video=cfg["supports_video"],
        frames_per_ball=frames_per_ball,
    )


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--video", type=Path, required=False,
                    help="Video file to benchmark (mp4/mov). Whole file is sent to video-native models.")
    ap.add_argument("--models", nargs="+", default=["gemini-2.5-pro"],
                    help="Model keys to benchmark (space-separated)")
    ap.add_argument("--frames-per-ball", type=int, default=4,
                    help="Frames extracted per ball for image-only models (default 4)")
    ap.add_argument("--output-dir", type=Path, default=Path("benchmark/results"),
                    help="Directory for JSON + Markdown reports")
    ap.add_argument("--list-models", action="store_true",
                    help="Print available models and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate inputs without calling any model")
    args = ap.parse_args()

    if args.list_models:
        print("\nAvailable models:")
        for k, c in MODELS.items():
            print(f"  {k:<28} [{c['provider']}]  {c['description']}")
        sys.exit(0)

    for m in args.models:
        if m not in MODELS:
            print(f"Error: unknown model '{m}'. Run --list-models to see options.")
            sys.exit(1)

    if not args.video or not args.video.exists():
        print(f"Error: --video path not found: {args.video}")
        sys.exit(1)

    print(f"\nVideo  : {args.video}  ({args.video.stat().st_size / 1e6:.1f} MB)")
    print(f"Models : {', '.join(args.models)}")
    print(f"Fields : {', '.join(BENCHMARK_FIELDS)}")

    if args.dry_run:
        print("\n[DRY RUN] — no model calls made")
        sys.exit(0)

    model_results: dict[str, dict] = {}
    latencies: dict[str, list[float]] = defaultdict(list)

    for model_key in args.models:
        print(f"\n{'─'*50}\nModel: {model_key}")
        runner = _runner(model_key, args.frames_per_ball)
        result = runner.run(args.video)

        lat = result.pop("_latency_s", None)
        err = result.pop("_error", None)

        if err:
            print(f"  ERROR: {err}")
        else:
            print(f"  Done in {lat}s")
            for field in BENCHMARK_FIELDS:
                print(f"    {field:<20} {result.get(field, 'unknown')}")

        latencies[model_key].append(lat or 0)
        model_results[model_key] = {
            "raw": result,
            "_avg_latency_s": lat,
            "_error": err,
        }

    # Side-by-side comparison
    print(f"\n{'='*60}\nSIDE-BY-SIDE COMPARISON\n{'='*60}")
    print(f"  {'Field':<20}" + "".join(f"  {m[:16]:<18}" for m in args.models))
    for field in BENCHMARK_FIELDS:
        row = f"  {field:<20}"
        for mk in args.models:
            val = model_results[mk].get("raw", {}).get(field, "—")
            row += f"  {str(val)[:16]:<18}"
        print(row)

    # Save raw output JSON
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    import json
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.output_dir / f"video_only_{ts}.json"
    out.write_text(json.dumps({
        "video": str(args.video),
        "models": args.models,
        "results": model_results,
    }, indent=2))
    print(f"\nResults saved → {out}")


if __name__ == "__main__":
    main()
