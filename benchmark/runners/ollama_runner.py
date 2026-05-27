"""Local Ollama vision runner — sends extracted frames as base64 images."""
from __future__ import annotations
import base64, json, time
from pathlib import Path
import requests
from benchmark.prompt import build_prompt
from benchmark.config import BENCHMARK_FIELDS

OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaRunner:
    def __init__(self, model_id: str, base_url: str = OLLAMA_BASE_URL):
        self.model_id = model_id
        self.base_url = base_url
        self.prompt = build_prompt(BENCHMARK_FIELDS)
        self._check_model()

    def _check_model(self) -> None:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            names = [m["name"] for m in r.json().get("models", [])]
            if not any(self.model_id in n for n in names):
                print(f"  [warn] '{self.model_id}' not pulled — run: ollama pull {self.model_id}")
        except requests.exceptions.ConnectionError:
            print("  [warn] Ollama not running — start with: ollama serve")

    def run_frames(self, frame_paths: list[Path]) -> dict:
        start = time.time()
        try:
            images = [
                base64.b64encode(fp.read_bytes()).decode()
                for fp in frame_paths if fp.exists()
            ]
            if not images:
                raise ValueError("No frames available")
            r = requests.post(
                f"{self.base_url}/api/generate",
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
