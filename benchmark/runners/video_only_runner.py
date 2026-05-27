"""
Video-only runner — no Cricsheet, no ESPN.
Sends a raw video chunk (or extracted frames) to the model and returns structured fields.
Supports both Gemini (video-native) and Ollama (frame-based) providers.
"""
from __future__ import annotations
import base64, json, os, time
from pathlib import Path
from benchmark.prompt import build_prompt
from benchmark.config import BENCHMARK_FIELDS
from benchmark.frame_extractor import extract_frames, cleanup_frames


class VideoOnlyRunner:
    def __init__(
        self,
        model_key: str,
        provider: str,
        model_id: str,
        supports_video: bool,
        frames_per_ball: int = 4,
    ):
        self.model_key = model_key
        self.provider = provider
        self.model_id = model_id
        self.supports_video = supports_video
        self.frames_per_ball = frames_per_ball
        self.prompt = build_prompt(BENCHMARK_FIELDS)

    def run(self, video_path: Path) -> dict:
        if self.provider == "gemini":
            return self._run_gemini(video_path)
        if self.provider == "ollama":
            return self._run_ollama(video_path)
        return {f: "unknown" for f in BENCHMARK_FIELDS} | {
            "_latency_s": 0, "_error": f"Unknown provider: {self.provider}"
        }

    def _run_gemini(self, video_path: Path) -> dict:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types
        load_dotenv()

        start = time.time()
        try:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")

            client = genai.Client(api_key=api_key)

            if self.supports_video:
                # Send full video chunk
                mime = {
                    "mp4": "video/mp4", "mov": "video/quicktime", "avi": "video/avi"
                }.get(video_path.suffix.lstrip(".").lower(), "video/mp4")
                video_bytes = video_path.read_bytes()
                response = client.models.generate_content(
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
            else:
                # Extract frames and send as images
                frames = extract_frames(video_path, self.frames_per_ball)
                parts = [
                    types.Part.from_bytes(data=fp.read_bytes(), mime_type="image/png")
                    for fp in frames
                ]
                parts.append(self.prompt)
                response = client.models.generate_content(
                    model=self.model_id,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                cleanup_frames(frames)

            result = json.loads(response.text)
            result["_latency_s"] = round(time.time() - start, 2)
            result["_error"] = None
            return result

        except Exception as e:
            return {f: "unknown" for f in BENCHMARK_FIELDS} | {
                "_latency_s": round(time.time() - start, 2),
                "_error": str(e),
            }

    def _run_ollama(self, video_path: Path) -> dict:
        import requests
        start = time.time()
        try:
            frames = extract_frames(video_path, self.frames_per_ball)
            images = [
                base64.b64encode(fp.read_bytes()).decode()
                for fp in frames if fp.exists()
            ]
            cleanup_frames(frames)

            if not images:
                raise ValueError("No frames extracted from video")

            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_id,
                    "prompt": self.prompt,
                    "images": images,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=180,
            )
            r.raise_for_status()
            raw = r.json().get("response", "")
            j_start, j_end = raw.find("{"), raw.rfind("}") + 1
            result = json.loads(raw[j_start:j_end]) if j_start >= 0 else {}
            for f in BENCHMARK_FIELDS:
                result.setdefault(f, "unknown")
            result["_latency_s"] = round(time.time() - start, 2)
            result["_error"] = None
            return result

        except Exception as e:
            return {f: "unknown" for f in BENCHMARK_FIELDS} | {
                "_latency_s": round(time.time() - start, 2),
                "_error": str(e),
            }
