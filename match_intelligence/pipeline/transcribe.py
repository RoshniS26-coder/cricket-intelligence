#!/usr/bin/env python3
"""Transcribe a broadcast video's audio with faster-whisper.

Produces a JSON with one entry per Whisper segment:
    {
      "video_path": ...,
      "model": "small",
      "language": "en",
      "segments": [
        {"start": 26.4, "end": 33.1, "text": "Willey to Sharma, full ball outside off..."},
        ...
      ]
    }

Designed to be ingested by per-ball Gemini calls — each Cricsheet ball joins
to the segments whose time range overlaps the ball's video window.

Usage:
    python features/audio_pipeline/transcribe.py \\
        --video data/raw_videos/IndiaBatting-T20-IndvsEng.mp4 \\
        --out data/whisper/IndvsEng_transcript.json \\
        --model small
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", required=True, help="Path to source video / audio file")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"], help="Whisper model size (default: small)")
    p.add_argument("--language", default="en", help="Force language (default: en)")
    p.add_argument("--compute-type", default="int8", help="int8 for CPU, float16 for GPU")
    args = p.parse_args()

    from faster_whisper import WhisperModel

    print(f"Loading model: {args.model} (compute_type={args.compute_type})...")
    t0 = time.time()
    model = WhisperModel(args.model, device="cpu", compute_type=args.compute_type)
    print(f"  loaded in {time.time()-t0:.1f}s")

    print(f"Transcribing {args.video}...")
    t0 = time.time()
    segments, info = model.transcribe(
        args.video,
        language=args.language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=False,  # segment-level is enough; word-level is much slower
    )

    payload = {
        "video_path": args.video,
        "model": args.model,
        "language": info.language,
        "duration_sec": info.duration,
        "segments": [],
    }
    n_chars = 0
    for seg in segments:
        payload["segments"].append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        n_chars += len(seg.text)
        if len(payload["segments"]) % 50 == 0:
            print(f"  ...{len(payload['segments'])} segments  (t={time.time()-t0:.0f}s)")

    wall = time.time() - t0
    print(f"✓ Transcribed {len(payload['segments'])} segments, {n_chars} chars in {wall:.0f}s")
    print(f"  realtime factor: {payload['duration_sec']/wall:.1f}x")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"✓ Wrote → {out_path}")


if __name__ == "__main__":
    main()
