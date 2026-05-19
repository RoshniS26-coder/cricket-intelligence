"""
Hybrid player briefing assembler.

Combines four data sources into one PlayerBriefing structure:
  1. Gemini extraction      (line, length, swing, shot, outcome — Layer 1)
  2. Pose features          (head offset, stride, shoulder — Layer 3)
  3. Few-shot critique      (deviations, drills, encouragement — Layer 5)
  4. Coaching corpus        (cited drills + cues from extracted tutorials)

The PlayerBriefing is then rendered to PDF by src.report.pdf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TechniqueMetric:
    name: str
    value: float | str | None
    target: str | None = None
    flag: str = "—"           # "✓" | "⚠" | "✗" | "—"


@dataclass
class Deviation:
    aspect: str
    observed: str
    ideal: str
    severity: str = "medium"   # low | medium | high
    effort: str | None = None  # 1-2 sessions | 1-2 weeks | ongoing


@dataclass
class Drill:
    name: str
    duration_minutes: int | None = None
    frequency: str | None = None
    addresses: str | None = None
    source: str = "critique"   # "critique" | "coaching_corpus"


@dataclass
class PlayerBriefing:
    # Header
    player_name: str
    shot_type: str
    generated_at: datetime
    clip_path: str
    ball_id: str | None = None
    academy: str | None = None

    # Source-data summary
    gemini: dict | None = None             # raw Gemini extraction fields
    pose_features: dict | None = None      # raw batsman feature dict
    critique: dict | None = None           # raw critique JSON

    # Derived structured content
    metrics: list[TechniqueMetric] = field(default_factory=list)
    deviations: list[Deviation] = field(default_factory=list)
    drills: list[Drill] = field(default_factory=list)
    coaching_cues: list[str] = field(default_factory=list)
    common_mistakes_quoted: list[str] = field(default_factory=list)
    encouragement: str | None = None
    overall_rating: str | None = None      # close_to_ideal | needs_minor_work | needs_major_work

    # Provenance
    reference_clips: list[dict] = field(default_factory=list)   # [{path, player}]
    coaching_keys_used: list[str] = field(default_factory=list)

    # Net-session catalog (Phase-1 multi-shot pipeline)
    # Populated only in net_session mode after a batch extract pre-pass.
    # Example: {"cover_drive": 12, "defend": 4, "pull": 2}
    mode: str = "single_ball"
    shot_counts: dict[str, int] | None = None        # None = catalog not run
    contact_counts: dict[str, int] | None = None     # contact_quality breakdown for net mode


# ── Threshold helpers ───────────────────────────────────────────────────────
_HEAD_OFFSET_TARGET = 0.03
_STRIDE_NORM_TARGET = 0.35


def _flag_below(val: float | None, target: float) -> str:
    if val is None:
        return "—"
    return "✓" if val < target else "⚠"


def _flag_above(val: float | None, target: float) -> str:
    if val is None:
        return "—"
    return "✓" if val > target else "⚠"


def _build_metrics(pose_features: dict | None) -> list[TechniqueMetric]:
    if not pose_features or "error" in pose_features:
        return []
    head = pose_features.get("head_lateral_offset")
    stride = pose_features.get("stride_length_norm")
    shoulder = pose_features.get("shoulder_angle_deg")
    side_on = pose_features.get("side_on_camera")
    return [
        TechniqueMetric(
            name="Head lateral offset at impact",
            value=head,
            target=f"<{_HEAD_OFFSET_TARGET}",
            flag=_flag_below(head, _HEAD_OFFSET_TARGET),
        ),
        TechniqueMetric(
            name="Stride length (× body height)",
            value=stride,
            target=f">{_STRIDE_NORM_TARGET}",
            flag=_flag_above(stride, _STRIDE_NORM_TARGET),
        ),
        TechniqueMetric(
            name="Shoulder angle",
            value=f"{shoulder}°" if shoulder is not None else None,
            target="—",
            flag="—",
        ),
        TechniqueMetric(
            name="Side-on camera",
            value="yes" if side_on else "no",
            target="yes",
            flag="✓" if side_on else "⚠",
        ),
    ]


def _build_deviations(critique: dict | None) -> list[Deviation]:
    if not critique:
        return []
    out = []
    for d in critique.get("deviations", []) or []:
        out.append(Deviation(
            aspect=d.get("aspect", "?"),
            observed=d.get("observed", ""),
            ideal=d.get("ideal_per_reference", ""),
            severity=d.get("severity", "medium"),
            effort=d.get("estimated_correction_effort"),
        ))
    return out


def _build_drills(critique: dict | None, coaching_context: list[dict] | None) -> list[Drill]:
    drills: list[Drill] = []

    # From critique recommendations
    for d in (critique or {}).get("drill_recommendations", []) or []:
        drills.append(Drill(
            name=d.get("drill_name", "?"),
            duration_minutes=d.get("duration_minutes"),
            frequency=d.get("frequency"),
            addresses=d.get("addresses_aspect"),
            source="critique",
        ))

    # From coaching corpus (deduplicated by lower-case name)
    seen = {dr.name.lower().strip() for dr in drills}
    for c in (coaching_context or []):
        for d in c.get("drills", []) or []:
            name = d.get("drill_name", "?")
            if name.lower().strip() in seen:
                continue
            drills.append(Drill(
                name=name,
                duration_minutes=d.get("duration_minutes"),
                addresses=d.get("addresses_aspect"),
                source="coaching_corpus",
            ))
            seen.add(name.lower().strip())

    return drills


def _collect_coaching_cues(coaching_context: list[dict] | None) -> list[str]:
    from ai_coach.lib.coaching_extractor import _bilingual_en
    cues = []
    for c in (coaching_context or []):
        for cue in c.get("coaching_cues", []) or []:
            text = _bilingual_en(cue)
            if text and text not in cues:
                cues.append(text)
    return cues


def _collect_common_mistakes(coaching_context: list[dict] | None) -> list[str]:
    from ai_coach.lib.coaching_extractor import _bilingual_en
    mistakes = []
    for c in (coaching_context or []):
        for m in c.get("common_mistakes", []) or []:
            text = _bilingual_en(m)
            if text and text not in mistakes:
                mistakes.append(text)
    return mistakes


def assemble_briefing(
    player_name: str,
    shot_type: str,
    clip_path: str,
    gemini: dict | None = None,
    pose_features: dict | None = None,
    critique: dict | None = None,
    coaching_context: list[dict] | None = None,
    reference_clips: list[dict] | None = None,
    coaching_keys: list[str] | None = None,
    ball_id: str | None = None,
    academy: str | None = None,
    mode: str = "single_ball",
    shot_counts: dict[str, int] | None = None,
    contact_counts: dict[str, int] | None = None,
) -> PlayerBriefing:
    """Pull together all the data sources into one PlayerBriefing."""
    return PlayerBriefing(
        player_name=player_name,
        shot_type=shot_type,
        generated_at=datetime.now(),
        clip_path=clip_path,
        ball_id=ball_id,
        academy=academy,
        gemini=gemini,
        pose_features=pose_features,
        critique=critique,
        metrics=_build_metrics(pose_features),
        deviations=_build_deviations(critique),
        drills=_build_drills(critique, coaching_context),
        coaching_cues=_collect_coaching_cues(coaching_context),
        common_mistakes_quoted=_collect_common_mistakes(coaching_context),
        encouragement=(critique or {}).get("encouragement"),
        overall_rating=(critique or {}).get("overall_quality_rating"),
        reference_clips=reference_clips or [],
        coaching_keys_used=coaching_keys or [],
        mode=mode,
        shot_counts=shot_counts,
        contact_counts=contact_counts,
    )
