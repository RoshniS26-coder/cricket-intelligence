"""Generate benchmark report — console + JSON + Markdown."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from benchmark.config import BENCHMARK_FIELDS


def print_report(model_results: dict, comparison: dict, n_balls: int, output_dir: Path) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*68}")
    print(f"  Cricket Video Analysis Benchmark  —  {now}")
    print(f"  Balls: {n_balls}  |  Fields: {', '.join(BENCHMARK_FIELDS)}")
    print(f"{'='*68}\n")

    print("OVERALL ACCURACY RANKING:")
    for i, entry in enumerate(comparison["ranking"], 1):
        bar = "█" * int(entry["overall"] * 30)
        print(f"  {i}. {entry['model']:<28} {entry['overall']:.1%}  {bar}")

    print(f"\n{'─'*68}\nPER-FIELD ACCURACY:\n")
    header = f"  {'Field':<20}" + "".join(f"  {m[:14]:<16}" for m in model_results)
    print(header)
    for field in BENCHMARK_FIELDS:
        row = f"  {field:<20}"
        for results in model_results.values():
            acc = results.get(field, {}).get("accuracy")
            row += f"  {acc:.1%}{'':>10}" if acc is not None else f"  {'—':>12}"
        print(row)

    print(f"\n{'─'*68}\nLATENCY (avg s/ball):")
    for model, results in model_results.items():
        lat = results.get("_avg_latency_s", "—")
        print(f"  {model:<32} {lat}s")

    print(f"\n{'='*68}")

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_out = output_dir / f"benchmark_{ts}.json"
    json_out.write_text(json.dumps({
        "timestamp": now,
        "n_balls": n_balls,
        "model_results": model_results,
        "comparison": comparison,
    }, indent=2))
    print(f"\n  Results saved → {json_out}")

    md_out = output_dir / f"benchmark_{ts}.md"
    _write_markdown(md_out, model_results, comparison, n_balls, now)
    print(f"  Markdown report → {md_out}\n")


def _write_markdown(path: Path, model_results: dict, comparison: dict, n_balls: int, ts: str) -> None:
    lines = [
        "# Cricket Video Analysis Benchmark",
        f"**Date:** {ts}  |  **Balls:** {n_balls}",
        "",
        "## Overall Ranking",
        "| Rank | Model | Accuracy |",
        "|------|-------|----------|",
    ]
    for i, e in enumerate(comparison["ranking"], 1):
        lines.append(f"| {i} | `{e['model']}` | **{e['overall']:.1%}** |")

    lines += [
        "", "## Per-Field Accuracy",
        "| Field | " + " | ".join(f"`{m}`" for m in model_results) + " |",
        "|-------|" + "|".join("---" for _ in model_results) + "|",
    ]
    for field in BENCHMARK_FIELDS:
        row = f"| {field} |"
        for res in model_results.values():
            acc = res.get(field, {}).get("accuracy")
            row += f" {acc:.1%} |" if acc is not None else " — |"
        lines.append(row)

    lines += [
        "", "## Latency", "| Model | Avg s/ball |", "|-------|-----------|",
    ]
    for model, res in model_results.items():
        lines.append(f"| `{model}` | {res.get('_avg_latency_s', '—')} |")

    lines += [
        "", "## Scoring Notes",
        "- Exact match for: `line`, `length`, `bowler_type`",
        "- Partial credit (0.5) for `shot_type` when same family (e.g. `cover_drive` vs `off_drive`)",
        "- GT fields with value `unknown` are excluded from scoring",
        "- Ollama models receive extracted PNG frames, not raw video",
    ]
    path.write_text("\n".join(lines))
