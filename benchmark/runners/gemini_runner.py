"""Gemini video-native and frame-based runner."""
from __future__ import annotations
import json, os, time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from benchmark.prompt import build_prompt
from benchmark.config import BENCHMARK_FIELDS

load_dotenv()


class GeminiRunner:
    def __init__(self, model_id: str):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id
        self.prompt = build_prompt(BENCHMARK_FIELDS)

    def run_clip(self, clip_path: Path) -> dict:
        start = time.time()
        try:
            mime = {"mp4": "video/mp4", "mov": "video/quicktime", "avi": "video/avi"}.get(
                clip_path.suffix.lstrip(".").lower(), "video/mp4"
            )
            video_bytes = clip_path.read_bytes()
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Part.from_bytes(data=video_bytes, mime_type=mime),
                    self.prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            result = json.loads(response.text)
            result["_latency_s"] = round(time.time() - start, 2)
            result["_error"] = None
            return result
        except Exception as e:
            return {f: "unknown" for f in BENCHMARK_FIELDS} | {
                "_latency_s": round(time.time() - start, 2),
                "_error": str(e),
            }

    def run_frames(self, frame_paths: list[Path]) -> dict:
        start = time.time()
        try:
            parts = [
                types.Part.from_bytes(data=fp.read_bytes(), mime_type="image/png")
                for fp in frame_paths
            ]
            parts.append(self.prompt)
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            result = json.loads(response.text)
            result["_latency_s"] = round(time.time() - start, 2)
            result["_error"] = None
            return result
        except Exception as e:
            return {f: "unknown" for f in BENCHMARK_FIELDS} | {
                "_latency_s": round(time.time() - start, 2),
                "_error": str(e),
            }
