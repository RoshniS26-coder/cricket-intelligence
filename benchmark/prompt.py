"""Shared extraction prompt — identical across all models for comparable results."""

FIELD_DESCRIPTIONS = {
    "line":            "outside_off | off_stump | middle | leg | outside_leg | unknown",
    "length":          "yorker | full | good | short_of_length | short | unknown",
    "shot_type":       "drive | cover_drive | straight_drive | on_drive | off_drive | cut | square_cut | late_cut | pull | hook | defend | front_foot_defence | back_foot_defence | sweep | slog_sweep | reverse_sweep | glance | flick | lofted | leave | unknown",
    "bowler_type":     "pace | spin | unknown",
    "contact_quality": "clean | edge | miss | mistimed | unknown",
    "footwork":        "front_foot | back_foot | neutral | unknown",
}


def build_prompt(fields: list[str] | None = None) -> str:
    if fields is None:
        fields = list(FIELD_DESCRIPTIONS.keys())
    field_lines = "\n".join(f'  "{f}": "{FIELD_DESCRIPTIONS[f]}"' for f in fields)
    return f"""You are a cricket ball-tracking analyst. Analyse this delivery carefully.

Return ONLY a valid JSON object with exactly these fields:
{{
{field_lines}
}}

Rules:
- Use ONLY the exact enum values listed — no free text
- Use "unknown" only when you genuinely cannot determine a field
- No markdown, no explanation, no extra keys — JSON only
"""
