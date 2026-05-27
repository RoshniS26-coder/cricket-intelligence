"""Score model predictions against ground truth — exact match + partial credit."""
from __future__ import annotations
from collections import defaultdict
from benchmark.config import BENCHMARK_FIELDS, PARTIAL_MATCH_FIELDS, SHOT_FAMILIES


def _shot_family(shot: str) -> str | None:
    for family, members in SHOT_FAMILIES.items():
        if shot in members:
            return family
    return None


def score_ball(prediction: dict, ground_truth: dict) -> dict:
    scores = {}
    for field in BENCHMARK_FIELDS:
        pred = str(prediction.get(field, "unknown")).lower().strip()
        gt   = str(ground_truth.get(field, "unknown")).lower().strip()

        if gt == "unknown":
            scores[field] = None  # GT unknown — skip from scoring
            continue
        if pred == gt:
            scores[field] = 1.0
        elif field in PARTIAL_MATCH_FIELDS and field == "shot_type":
            pf, gf = _shot_family(pred), _shot_family(gt)
            scores[field] = 0.5 if (pf and pf == gf) else 0.0
        else:
            scores[field] = 0.0

    return scores


def aggregate_scores(ball_scores: list[dict]) -> dict:
    field_totals: dict[str, list[float]] = defaultdict(list)
    for bs in ball_scores:
        for field, score in bs.items():
            if score is not None:
                field_totals[field].append(score)

    results = {}
    for field, scores in field_totals.items():
        results[field] = {
            "accuracy": round(sum(scores) / len(scores), 3),
            "n":        len(scores),
            "correct":  sum(1 for s in scores if s == 1.0),
            "partial":  sum(1 for s in scores if s == 0.5),
            "wrong":    sum(1 for s in scores if s == 0.0),
        }

    all_scores = [s for scores in field_totals.values() for s in scores]
    results["_overall"] = round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0
    return results


def compare_models(model_results: dict[str, dict]) -> dict:
    ranked = sorted(model_results.items(), key=lambda x: x[1].get("_overall", 0), reverse=True)
    return {
        "ranking": [{"model": k, "overall": v.get("_overall", 0)} for k, v in ranked],
        "by_field": {
            field: {model: res.get(field, {}).get("accuracy") for model, res in model_results.items()}
            for field in BENCHMARK_FIELDS
        },
    }
