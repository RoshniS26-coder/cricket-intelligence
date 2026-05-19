"""
Cricket Intelligence Engine - Validation & Normalization Layer
Ensures Gemini outputs conform to schema and normalizes fuzzy text to enums.
"""

import re
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

from src.intelligence.schema import (
    BallRecord, Line, Length, ShotType, BowlerType,
    Footwork, ContactQuality, Outcome, Variation,
    BounceBehavior, Movement,
    SwingDirection, SwingType, SpinDirection, BallAgePhase,
    InningsPhase,
)

console = Console()

# ===== Player Name Canonicalisation =====
# Loaded once from data/player_aliases.yaml. Curate that file as you spot
# new short-forms in Gemini output.

_PLAYER_ALIASES_PATH = Path("data/player_aliases.yaml")
_PLAYER_ALIASES_CACHE: dict[str, str] | None = None


def _load_player_aliases() -> dict[str, str]:
    """Lazy-load player aliases YAML (case-insensitive lookup)."""
    global _PLAYER_ALIASES_CACHE
    if _PLAYER_ALIASES_CACHE is not None:
        return _PLAYER_ALIASES_CACHE
    if not _PLAYER_ALIASES_PATH.exists():
        _PLAYER_ALIASES_CACHE = {}
        return _PLAYER_ALIASES_CACHE
    try:
        data = yaml.safe_load(_PLAYER_ALIASES_PATH.read_text()) or {}
        raw = data.get("aliases", {}) or {}
        _PLAYER_ALIASES_CACHE = {k.strip().lower(): v.strip() for k, v in raw.items()}
    except Exception as e:
        console.print(f"[yellow]⚠ player_aliases.yaml parse failed: {e}[/yellow]")
        _PLAYER_ALIASES_CACHE = {}
    return _PLAYER_ALIASES_CACHE


def resolve_player_name(name: Optional[str]) -> Optional[str]:
    """Replace short-form / partial player names with canonical full names.
    Returns the input unchanged if no alias is registered. None-safe."""
    if not name:
        return name
    aliases = _load_player_aliases()
    return aliases.get(name.strip().lower(), name)


# ===== Innings-Phase Derivation =====
# T20: PP=1-6, middle=7-15, death=16-20.
# ODI: PP=1-10, middle=11-40, death=41-50.
# Anything else (Test / nets / unknown format) → UNKNOWN.

def derive_phase(over: int, format_str: str = "T20") -> InningsPhase:
    """Derive innings phase from over number + match format. Returns UNKNOWN
    if the over is missing or the format doesn't have phase semantics."""
    if not over or over < 1:
        return InningsPhase.UNKNOWN
    fmt = (format_str or "").upper()
    if fmt in ("T20", "T20I"):
        if 1 <= over <= 6:
            return InningsPhase.POWERPLAY
        if 7 <= over <= 15:
            return InningsPhase.MIDDLE_OVERS
        if 16 <= over <= 20:
            return InningsPhase.DEATH
    elif fmt in ("ODI", "OD"):
        if 1 <= over <= 10:
            return InningsPhase.POWERPLAY
        if 11 <= over <= 40:
            return InningsPhase.MIDDLE_OVERS
        if 41 <= over <= 50:
            return InningsPhase.DEATH
    return InningsPhase.UNKNOWN


# ===== Normalization Maps =====
# Maps fuzzy/natural language terms to our strict enum values

LINE_NORMALIZATIONS = {
    # outside_off
    "outside off": Line.OUTSIDE_OFF,
    "wide outside off": Line.OUTSIDE_OFF,
    "just outside off": Line.OUTSIDE_OFF,
    "wide of off": Line.OUTSIDE_OFF,
    "outside off stump": Line.OUTSIDE_OFF,
    "5th stump": Line.OUTSIDE_OFF,
    "fourth stump": Line.OUTSIDE_OFF,
    # off_stump
    "off stump": Line.OFF_STUMP,
    "on off": Line.OFF_STUMP,
    "off": Line.OFF_STUMP,
    "on the off": Line.OFF_STUMP,
    "off stump line": Line.OFF_STUMP,
    # middle
    "middle": Line.MIDDLE,
    "middle stump": Line.MIDDLE,
    "on middle": Line.MIDDLE,
    "middle and off": Line.MIDDLE,
    "middle and leg": Line.MIDDLE,
    # leg
    "leg": Line.LEG,
    "leg stump": Line.LEG,
    "on leg": Line.LEG,
    "on the pads": Line.LEG,
    "on his pads": Line.LEG,
    "leg stump line": Line.LEG,
    # outside_leg
    "outside leg": Line.OUTSIDE_LEG,
    "down leg": Line.OUTSIDE_LEG,
    "down the leg side": Line.OUTSIDE_LEG,
    "wide down leg": Line.OUTSIDE_LEG,
}

LENGTH_NORMALIZATIONS = {
    # yorker
    "yorker": Length.YORKER,
    "yorker length": Length.YORKER,
    "full toss": Length.FULL,  # technically different but close enough for POC
    # full
    "full": Length.FULL,
    "full length": Length.FULL,
    "overpitched": Length.FULL,
    "fullish": Length.FULL,
    "half volley": Length.FULL,
    # good
    "good": Length.GOOD,
    "good length": Length.GOOD,
    "nagging length": Length.GOOD,
    "testing length": Length.GOOD,
    # short_of_length
    "short of length": Length.SHORT_OF_LENGTH,
    "short of a length": Length.SHORT_OF_LENGTH,
    "short-ish": Length.SHORT_OF_LENGTH,
    "shortish": Length.SHORT_OF_LENGTH,
    "back of a length": Length.SHORT_OF_LENGTH,
    "back of length": Length.SHORT_OF_LENGTH,
    # short
    "short": Length.SHORT,
    "short ball": Length.SHORT,
    "bouncer": Length.SHORT,
    "very short": Length.SHORT,
    "banged in short": Length.SHORT,
}

SHOT_NORMALIZATIONS = {
    # Drive family — prefer specific subtypes
    "drive": ShotType.DRIVE,
    "cover drive": ShotType.COVER_DRIVE,
    "cover-drive": ShotType.COVER_DRIVE,
    "cover_drive": ShotType.COVER_DRIVE,
    "straight drive": ShotType.STRAIGHT_DRIVE,
    "straight-drive": ShotType.STRAIGHT_DRIVE,
    "straight_drive": ShotType.STRAIGHT_DRIVE,
    "on drive": ShotType.ON_DRIVE,
    "on-drive": ShotType.ON_DRIVE,
    "on_drive": ShotType.ON_DRIVE,
    "off drive": ShotType.OFF_DRIVE,
    "off-drive": ShotType.OFF_DRIVE,
    "off_drive": ShotType.OFF_DRIVE,
    "square drive": ShotType.SQUARE_DRIVE,
    "square_drive": ShotType.SQUARE_DRIVE,

    # Cut family
    "cut": ShotType.CUT,
    "square cut": ShotType.SQUARE_CUT,
    "square_cut": ShotType.SQUARE_CUT,
    "late cut": ShotType.LATE_CUT,
    "late_cut": ShotType.LATE_CUT,
    "upper cut": ShotType.UPPER_CUT,
    "upper_cut": ShotType.UPPER_CUT,

    # Pull / hook
    "pull": ShotType.PULL,
    "pull shot": ShotType.PULL,
    "hook": ShotType.HOOK,
    "hook shot": ShotType.HOOK,

    # Defense family — prefer specific subtypes
    "defend": ShotType.DEFEND,
    "defensive": ShotType.DEFEND,
    "block": ShotType.DEFEND,
    "forward defense": ShotType.FRONT_FOOT_DEFENCE,
    "forward defence": ShotType.FRONT_FOOT_DEFENCE,
    "front foot defense": ShotType.FRONT_FOOT_DEFENCE,
    "front foot defence": ShotType.FRONT_FOOT_DEFENCE,
    "front-foot defence": ShotType.FRONT_FOOT_DEFENCE,
    "front_foot_defence": ShotType.FRONT_FOOT_DEFENCE,
    "back foot defense": ShotType.BACK_FOOT_DEFENCE,
    "back foot defence": ShotType.BACK_FOOT_DEFENCE,
    "back-foot defence": ShotType.BACK_FOOT_DEFENCE,
    "back_foot_defence": ShotType.BACK_FOOT_DEFENCE,

    # Sweep family
    "sweep": ShotType.SWEEP,
    "sweep shot": ShotType.SWEEP,
    "conventional sweep": ShotType.SWEEP,
    "slog sweep": ShotType.SLOG_SWEEP,
    "slog_sweep": ShotType.SLOG_SWEEP,
    "paddle sweep": ShotType.PADDLE_SWEEP,
    "paddle_sweep": ShotType.PADDLE_SWEEP,
    "reverse sweep": ShotType.REVERSE_SWEEP,
    "reverse_sweep": ShotType.REVERSE_SWEEP,
    "reverse": ShotType.REVERSE_SWEEP,

    # Wristy / leg-side
    "glance": ShotType.GLANCE,
    "leg glance": ShotType.LEG_GLANCE,
    "leg-glance": ShotType.LEG_GLANCE,
    "leg_glance": ShotType.LEG_GLANCE,
    "fine glance": ShotType.LEG_GLANCE,
    "flick": ShotType.FLICK,
    "wrist flick": ShotType.FLICK,
    "wristy flick": ShotType.FLICK,
    "clip": ShotType.FLICK,

    # Aerial / innovation
    "lofted": ShotType.LOFTED,
    "lofted shot": ShotType.LOFTED,
    "slog": ShotType.LOFTED,
    "big shot": ShotType.LOFTED,
    "aerial": ShotType.LOFTED,
    "helicopter": ShotType.HELICOPTER,
    "helicopter shot": ShotType.HELICOPTER,
    "scoop": ShotType.SCOOP,
    "ramp": ShotType.SCOOP,
    "ramp shot": ShotType.SCOOP,
    "dilscoop": ShotType.SCOOP,

    # Leave
    "leave": ShotType.LEAVE,
    "left alone": ShotType.LEAVE,
    "shouldered arms": ShotType.LEAVE,
    "no shot": ShotType.LEAVE,
}

SWING_DIRECTION_NORMALIZATIONS = {
    "in-swing": SwingDirection.IN_SWING,
    "in swing": SwingDirection.IN_SWING,
    "inswing": SwingDirection.IN_SWING,
    "inswinger": SwingDirection.IN_SWING,
    "swinging in": SwingDirection.IN_SWING,
    "tailing in": SwingDirection.IN_SWING,
    "out-swing": SwingDirection.OUT_SWING,
    "out swing": SwingDirection.OUT_SWING,
    "outswing": SwingDirection.OUT_SWING,
    "outswinger": SwingDirection.OUT_SWING,
    "swinging away": SwingDirection.OUT_SWING,
    "leaving the batsman": SwingDirection.OUT_SWING,
    "shaping away": SwingDirection.OUT_SWING,
}

SWING_TYPE_NORMALIZATIONS = {
    "conventional swing": SwingType.CONVENTIONAL,
    "conventional": SwingType.CONVENTIONAL,
    "late swing": SwingType.LATE,
    "late movement": SwingType.LATE,
    "hooping late": SwingType.LATE,
    "reverse swing": SwingType.REVERSE,
    "reverse": SwingType.REVERSE,
    "reversing": SwingType.REVERSE,
}

SPIN_DIRECTION_NORMALIZATIONS = {
    "off break": SpinDirection.OFF_BREAK,
    "off-break": SpinDirection.OFF_BREAK,
    "offbreak": SpinDirection.OFF_BREAK,
    "off spin": SpinDirection.OFF_BREAK,
    "off-spin": SpinDirection.OFF_BREAK,
    "offspin": SpinDirection.OFF_BREAK,
    "turning in": SpinDirection.OFF_BREAK,
    "leg break": SpinDirection.LEG_BREAK,
    "leg-break": SpinDirection.LEG_BREAK,
    "legbreak": SpinDirection.LEG_BREAK,
    "leg spin": SpinDirection.LEG_BREAK,
    "leg-spin": SpinDirection.LEG_BREAK,
    "turning away": SpinDirection.LEG_BREAK,
    "googly": SpinDirection.GOOGLY,
    "wrong-un": SpinDirection.GOOGLY,
    "wrong un": SpinDirection.GOOGLY,
    "arm ball": SpinDirection.ARM_BALL,
    "arm-ball": SpinDirection.ARM_BALL,
    "slider": SpinDirection.SLIDER,
    "doosra": SpinDirection.DOOSRA,
    "carrom": SpinDirection.CARROM,
    "carrom ball": SpinDirection.CARROM,
    "top spin": SpinDirection.TOP_SPIN,
    "top-spin": SpinDirection.TOP_SPIN,
    "topspinner": SpinDirection.TOP_SPIN,
}

BALL_AGE_NORMALIZATIONS = {
    "new ball": BallAgePhase.NEW_BALL,
    "new-ball": BallAgePhase.NEW_BALL,
    "shiny new": BallAgePhase.NEW_BALL,
    "old ball": BallAgePhase.OLD,
    "old-ball": BallAgePhase.OLD,
    "older ball": BallAgePhase.OLD,
    "worn ball": BallAgePhase.OLD,
    "reverse window": BallAgePhase.REVERSE_WINDOW,
    "reverse swing window": BallAgePhase.REVERSE_WINDOW,
}

OUTCOME_NORMALIZATIONS = {
    "dot": Outcome.DOT,
    "dot ball": Outcome.DOT,
    "no run": Outcome.DOT,
    "0": Outcome.DOT,
    "single": Outcome.ONE,
    "1 run": Outcome.ONE,
    "one": Outcome.ONE,
    "double": Outcome.TWO,
    "2 runs": Outcome.TWO,
    "two": Outcome.TWO,
    "three": Outcome.THREE,
    "3 runs": Outcome.THREE,
    "four": Outcome.FOUR,
    "boundary": Outcome.FOUR,
    "4 runs": Outcome.FOUR,
    "six": Outcome.SIX,
    "maximum": Outcome.SIX,
    "6 runs": Outcome.SIX,
    "over the rope": Outcome.SIX,
    "wicket": Outcome.WICKET,
    "out": Outcome.WICKET,
    "bowled": Outcome.WICKET,
    "caught": Outcome.WICKET,
    "lbw": Outcome.WICKET,
    "stumped": Outcome.WICKET,
    "run out": Outcome.WICKET,
    "wide": Outcome.WIDE,
    "wide ball": Outcome.WIDE,
    "no ball": Outcome.NO_BALL,
    "no-ball": Outcome.NO_BALL,
}


def normalize_field(value: str, normalization_map: dict, default=None):
    """
    Normalize a fuzzy text value to a strict enum value.

    Args:
        value: Raw text value from model output
        normalization_map: Dict mapping fuzzy text → enum value
        default: Value to return if no match found
    """
    if not value or value.lower() in ("unknown", ""):
        return default

    cleaned = value.lower().strip()

    # Direct match
    if cleaned in normalization_map:
        return normalization_map[cleaned]

    # Partial match (check if any key is contained in the value)
    for key, enum_val in normalization_map.items():
        if key in cleaned or cleaned in key:
            return enum_val

    return default


class BallRecordValidator:
    """Validates and normalizes ball records."""

    def validate_record(self, record: BallRecord, format_str: str = "T20") -> tuple[BallRecord, list[str]]:
        """
        Validate and normalize a BallRecord.

        Args:
            record:     BallRecord to normalize.
            format_str: Match format ("T20" | "ODI" | "Test" | "nets") used for phase
                        derivation. Default T20.

        Returns:
            Tuple of (normalized record, list of warnings)
        """
        warnings = []

        # ── Player-name canonicalisation (Tier-1 analytics enrichment) ──
        # Replace "Iyer" → "Shreyas Iyer" etc. so per-batsman queries don't
        # split across short and long forms.
        original_batsman = record.batsman_name
        original_bowler = record.bowler_name
        record.batsman_name = resolve_player_name(record.batsman_name)
        record.bowler_name = resolve_player_name(record.bowler_name)
        if original_batsman and record.batsman_name != original_batsman:
            warnings.append(
                f"Canonicalised batsman_name: '{original_batsman}' → '{record.batsman_name}'"
            )
        if original_bowler and record.bowler_name != original_bowler:
            warnings.append(
                f"Canonicalised bowler_name: '{original_bowler}' → '{record.bowler_name}'"
            )

        # ── Phase derivation ──
        # If Gemini left phase=UNKNOWN, derive from over + format. Trust Gemini if it set it.
        if record.phase == InningsPhase.UNKNOWN:
            derived = derive_phase(record.over, format_str)
            if derived != InningsPhase.UNKNOWN:
                record.phase = derived

        # Normalize fields if they contain fuzzy text
        if record.raw_description:
            description_lower = record.raw_description.lower()

            # Try to infer missing fields from raw description
            if record.line == Line.UNKNOWN:
                inferred_line = normalize_field(
                    record.raw_description, LINE_NORMALIZATIONS, Line.UNKNOWN
                )
                if inferred_line != Line.UNKNOWN:
                    record.line = inferred_line
                    warnings.append(f"Inferred line '{inferred_line.value}' from description")

            if record.length == Length.UNKNOWN:
                inferred_length = normalize_field(
                    record.raw_description, LENGTH_NORMALIZATIONS, Length.UNKNOWN
                )
                if inferred_length != Length.UNKNOWN:
                    record.length = inferred_length
                    warnings.append(f"Inferred length '{inferred_length.value}' from description")

            # Infer delivery sub-type from raw description when Gemini left it unknown.
            # These are conservative — normalize_field only flips UNKNOWN → known.
            if record.swing_direction == SwingDirection.UNKNOWN:
                inferred = normalize_field(
                    record.raw_description, SWING_DIRECTION_NORMALIZATIONS, SwingDirection.UNKNOWN
                )
                if inferred != SwingDirection.UNKNOWN:
                    record.swing_direction = inferred
                    warnings.append(f"Inferred swing_direction '{inferred.value}' from description")

            if record.swing_type == SwingType.UNKNOWN:
                inferred = normalize_field(
                    record.raw_description, SWING_TYPE_NORMALIZATIONS, SwingType.UNKNOWN
                )
                if inferred != SwingType.UNKNOWN:
                    record.swing_type = inferred
                    warnings.append(f"Inferred swing_type '{inferred.value}' from description")

            if record.spin_direction == SpinDirection.UNKNOWN:
                inferred = normalize_field(
                    record.raw_description, SPIN_DIRECTION_NORMALIZATIONS, SpinDirection.UNKNOWN
                )
                if inferred != SpinDirection.UNKNOWN:
                    record.spin_direction = inferred
                    warnings.append(f"Inferred spin_direction '{inferred.value}' from description")

            if record.ball_age_phase == BallAgePhase.UNKNOWN:
                inferred = normalize_field(
                    record.raw_description, BALL_AGE_NORMALIZATIONS, BallAgePhase.UNKNOWN
                )
                if inferred != BallAgePhase.UNKNOWN:
                    record.ball_age_phase = inferred
                    warnings.append(f"Inferred ball_age_phase '{inferred.value}' from description")

            # Consistency: spin_direction only meaningful for spin bowling
            if record.bowler_type == BowlerType.PACE and record.spin_direction not in (
                SpinDirection.NONE, SpinDirection.UNKNOWN
            ):
                warnings.append(
                    f"Clearing spin_direction '{record.spin_direction.value}' for pace bowler"
                )
                record.spin_direction = SpinDirection.NONE

            # Consistency: swing fields only meaningful for pace bowling
            if record.bowler_type == BowlerType.SPIN and record.swing_direction not in (
                SwingDirection.NONE, SwingDirection.UNKNOWN
            ):
                warnings.append(
                    f"Clearing swing_direction '{record.swing_direction.value}' for spin bowler"
                )
                record.swing_direction = SwingDirection.NONE

            if record.bowler_type == BowlerType.SPIN and record.swing_type not in (
                SwingType.NONE, SwingType.UNKNOWN
            ):
                record.swing_type = SwingType.NONE

        # Cross-field consistency checks
        if record.shot_type == ShotType.LEAVE and record.contact_quality != ContactQuality.MISS:
            record.contact_quality = ContactQuality.MISS
            warnings.append("Set contact_quality to 'miss' for leave")

        if record.outcome == Outcome.WICKET and record.contact_quality == ContactQuality.CLEAN:
            warnings.append("Wicket with clean contact — possible catch or run out")

        if record.outcome == Outcome.DOT:
            record.runs_scored = 0
        elif record.outcome in (Outcome.ONE, Outcome.TWO, Outcome.THREE, Outcome.FOUR, Outcome.SIX):
            record.runs_scored = int(record.outcome.value)

        # Flag low confidence records for human review
        avg_confidence = (
            record.confidence.line
            + record.confidence.length
            + record.confidence.shot_type
        ) / 3

        if avg_confidence < 0.5:
            warnings.append(f"Low average confidence ({avg_confidence:.2f}) — needs human review")

        # Count unknowns
        unknown_count = sum(1 for field in [
            record.line, record.length, record.shot_type,
            record.bowler_type, record.contact_quality
        ] if hasattr(field, 'value') and field.value == "unknown")

        if unknown_count >= 3:
            warnings.append(f"High unknown count ({unknown_count}/5) — poor extraction quality")

        return record, warnings

    def validate_batch(self, records: list[BallRecord]) -> tuple[list[BallRecord], dict]:
        """
        Validate a batch of records.

        Returns:
            Tuple of (validated records, summary stats)
        """
        validated = []
        all_warnings = []
        low_confidence_count = 0
        high_unknown_count = 0

        for record in records:
            validated_record, warnings = self.validate_record(record)
            validated.append(validated_record)
            all_warnings.extend(warnings)

            avg_conf = (
                record.confidence.line
                + record.confidence.length
                + record.confidence.shot_type
            ) / 3
            if avg_conf < 0.5:
                low_confidence_count += 1

            unknown_count = sum(1 for field in [
                record.line, record.length, record.shot_type,
                record.bowler_type, record.contact_quality
            ] if hasattr(field, 'value') and field.value == "unknown")
            if unknown_count >= 3:
                high_unknown_count += 1

        stats = {
            "total_records": len(records),
            "low_confidence": low_confidence_count,
            "high_unknowns": high_unknown_count,
            "warnings_count": len(all_warnings),
            "needs_review_pct": (
                low_confidence_count / len(records) * 100 if records else 0
            ),
        }

        console.print(f"\n[bold]Validation Summary:[/bold]")
        console.print(f"  Total records: {stats['total_records']}")
        console.print(f"  Low confidence: {stats['low_confidence']}")
        console.print(f"  High unknowns: {stats['high_unknowns']}")
        console.print(f"  Needs review: {stats['needs_review_pct']:.1f}%")

        return validated, stats
