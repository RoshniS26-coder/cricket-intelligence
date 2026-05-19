"""
Cricket Intelligence Engine - Ball-Level Schema
Defines the structured data model for ball-by-ball cricket analysis.
"""

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


# ===== Enum Definitions =====

class BowlerType(str, Enum):
    PACE = "pace"
    SPIN = "spin"
    UNKNOWN = "unknown"


class Line(str, Enum):
    OUTSIDE_OFF = "outside_off"
    OFF_STUMP = "off_stump"
    MIDDLE = "middle"
    LEG = "leg"
    OUTSIDE_LEG = "outside_leg"
    UNKNOWN = "unknown"


class Length(str, Enum):
    YORKER = "yorker"
    FULL = "full"
    GOOD = "good"
    SHORT_OF_LENGTH = "short_of_length"
    SHORT = "short"
    UNKNOWN = "unknown"


class Variation(str, Enum):
    NONE = "none"
    SLOWER = "slower"
    CUTTER = "cutter"
    BOUNCER = "bouncer"
    YORKER = "yorker"
    SPIN_VARIATION = "spin_variation"
    UNKNOWN = "unknown"


class ShotType(str, Enum):
    # Broad fallback values (use when Gemini is uncertain about the subtype)
    DRIVE = "drive"
    CUT = "cut"
    PULL = "pull"
    HOOK = "hook"
    DEFEND = "defend"
    SWEEP = "sweep"
    REVERSE_SWEEP = "reverse_sweep"
    GLANCE = "glance"
    FLICK = "flick"
    LOFTED = "lofted"
    LEAVE = "leave"
    UNKNOWN = "unknown"

    # Granular drive subtypes
    COVER_DRIVE = "cover_drive"
    STRAIGHT_DRIVE = "straight_drive"
    ON_DRIVE = "on_drive"
    OFF_DRIVE = "off_drive"
    SQUARE_DRIVE = "square_drive"

    # Granular cut subtypes
    SQUARE_CUT = "square_cut"
    LATE_CUT = "late_cut"
    UPPER_CUT = "upper_cut"

    # Granular defense subtypes
    FRONT_FOOT_DEFENCE = "front_foot_defence"
    BACK_FOOT_DEFENCE = "back_foot_defence"

    # Granular sweep subtypes (REVERSE_SWEEP already exists above)
    SLOG_SWEEP = "slog_sweep"
    PADDLE_SWEEP = "paddle_sweep"

    # Granular leg-side wristy subtypes
    LEG_GLANCE = "leg_glance"

    # Innovative shots
    HELICOPTER = "helicopter"
    SCOOP = "scoop"


class Footwork(str, Enum):
    FRONT_FOOT = "front_foot"
    BACK_FOOT = "back_foot"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ContactQuality(str, Enum):
    CLEAN = "clean"
    MISTIMED = "mistimed"
    EDGE = "edge"
    MISS = "miss"
    UNKNOWN = "unknown"


class Outcome(str, Enum):
    DOT = "dot"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    SIX = "6"
    WICKET = "wicket"
    WIDE = "wide"
    NO_BALL = "no_ball"
    UNKNOWN = "unknown"


class BounceBehavior(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    STEEP = "steep"
    UNKNOWN = "unknown"


class Movement(str, Enum):
    NONE = "none"
    SEAM = "seam"
    SWING = "swing"
    TURN = "turn"
    UNKNOWN = "unknown"


class SwingDirection(str, Enum):
    """Direction of in-air swing, relative to a right-handed batsman.
    in_swing  = ball curves toward the batsman's pads
    out_swing = ball curves away from the batsman, toward the slips"""
    IN_SWING = "in_swing"
    OUT_SWING = "out_swing"
    NONE = "none"
    UNKNOWN = "unknown"


class SwingType(str, Enum):
    """Character of swing, orthogonal to direction."""
    CONVENTIONAL = "conventional"  # new-ball swing, smooth side forward
    LATE = "late"                  # swing occurs in the last few meters
    REVERSE = "reverse"            # old-ball reverse swing
    NONE = "none"
    UNKNOWN = "unknown"


class SpinDirection(str, Enum):
    """Direction and type of spin, relative to a right-handed batsman."""
    OFF_BREAK = "off_break"        # right-arm finger-spin turning in toward batter
    LEG_BREAK = "leg_break"        # right-arm wrist-spin turning away from batter
    GOOGLY = "googly"              # wrong-un, turns opposite to leg_break
    ARM_BALL = "arm_ball"          # finger-spin sliding straight on
    DOOSRA = "doosra"              # finger-spin wrong-un, turns opposite
    CARROM = "carrom"              # middle-finger flick delivery
    TOP_SPIN = "top_spin"          # dips and bounces more
    SLIDER = "slider"              # wrist-spin skidder
    NONE = "none"
    UNKNOWN = "unknown"


class BallAgePhase(str, Enum):
    """Approximate ball age. Strongly affects swing/reverse swing behavior."""
    NEW_BALL = "new_ball"          # first ~10 overs (white) / first 25 (red)
    OLD = "old"                    # broken-in but pre-reverse window
    REVERSE_WINDOW = "reverse_window"  # conditions where reverse swing is live
    UNKNOWN = "unknown"


# ===== Analytics Enrichment Enums (Tier 1) =====

class ShotDirection(str, Enum):
    """16-position field map of where the ball travelled after the bat (or off
    pads / past edge). Names use the canonical broadcast cricket field
    convention from the BATSMAN'S point of view, regardless of handedness:
    OFF side = third_man → cover → mid_off, LEG side = mid_on → mid_wicket → fine_leg.
    """
    THIRD_MAN = "third_man"
    DEEP_THIRD = "deep_third"
    POINT = "point"
    DEEP_POINT = "deep_point"
    COVER = "cover"
    DEEP_COVER = "deep_cover"
    MID_OFF = "mid_off"
    LONG_OFF = "long_off"
    STRAIGHT = "straight"
    LONG_ON = "long_on"
    MID_ON = "mid_on"
    MID_WICKET = "mid_wicket"
    DEEP_MID_WICKET = "deep_mid_wicket"
    SQUARE_LEG = "square_leg"
    DEEP_SQUARE_LEG = "deep_square_leg"
    FINE_LEG = "fine_leg"
    DEEP_FINE_LEG = "deep_fine_leg"
    BEHIND_WICKET = "behind_wicket"  # straight back past keeper, e.g. ramp
    NONE = "none"                    # leave / dot ball where ball didn't reach bat
    UNKNOWN = "unknown"


class DismissalType(str, Enum):
    """How a wicket fell. Always set when outcome=wicket; otherwise NONE."""
    BOWLED = "bowled"
    CAUGHT = "caught"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"
    CAUGHT_AND_BOWLED = "caught_and_bowled"
    RETIRED = "retired"
    OBSTRUCTING = "obstructing"
    NONE = "none"
    UNKNOWN = "unknown"


class BowlerCrease(str, Enum):
    """Side of the stumps the bowler delivered from."""
    OVER_THE_WICKET = "over_the_wicket"
    ROUND_THE_WICKET = "round_the_wicket"
    WIDE_OF_CREASE = "wide_of_crease"
    UNKNOWN = "unknown"


class EdgeType(str, Enum):
    """Which face/edge of the bat made contact. Only meaningful when
    contact_quality=edge; otherwise NONE."""
    INSIDE_EDGE = "inside_edge"
    OUTSIDE_EDGE = "outside_edge"
    TOP_EDGE = "top_edge"
    BOTTOM_EDGE = "bottom_edge"
    NONE = "none"
    UNKNOWN = "unknown"


class InningsPhase(str, Enum):
    """Standard cricket innings phases. Auto-derivable from over + format
    if Gemini doesn't read it from the broadcast."""
    POWERPLAY = "powerplay"
    MIDDLE_OVERS = "middle_overs"
    DEATH = "death"
    UNKNOWN = "unknown"


class Handedness(str, Enum):
    """Batter handedness. Per ball but typically same for every ball faced
    by the same batter."""
    RIGHT_HANDED = "right_handed"
    LEFT_HANDED = "left_handed"
    UNKNOWN = "unknown"


# ===== Confidence Scores =====

class ConfidenceScores(BaseModel):
    """Confidence scores for key fields (0.0 to 1.0)"""
    bowler_type: float = Field(default=0.0, ge=0.0, le=1.0)
    line: float = Field(default=0.0, ge=0.0, le=1.0)
    length: float = Field(default=0.0, ge=0.0, le=1.0)
    shot_type: float = Field(default=0.0, ge=0.0, le=1.0)
    outcome: float = Field(default=0.0, ge=0.0, le=1.0)
    contact_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    # New — delivery sub-type confidences. Gemini is often uncertain here;
    # keep default 0.0 so downstream analytics can gate by a minimum threshold.
    swing_direction: float = Field(default=0.0, ge=0.0, le=1.0)
    spin_direction: float = Field(default=0.0, ge=0.0, le=1.0)
    swing_type: float = Field(default=0.0, ge=0.0, le=1.0)
    # Name OCR / commentary readings are the noisiest fields; expose explicit
    # confidences so the weakness join can drop low-confidence batsman names.
    bowler_name: float = Field(default=0.0, ge=0.0, le=1.0)
    batsman_name: float = Field(default=0.0, ge=0.0, le=1.0)
    # Tier-1 analytics enrichment confidences
    shot_direction: float = Field(default=0.0, ge=0.0, le=1.0)
    dismissal_type: float = Field(default=0.0, ge=0.0, le=1.0)
    bowling_speed: float = Field(default=0.0, ge=0.0, le=1.0)
    bowler_crease: float = Field(default=0.0, ge=0.0, le=1.0)
    edge_type: float = Field(default=0.0, ge=0.0, le=1.0)
    handedness: float = Field(default=0.0, ge=0.0, le=1.0)


# ===== Main Ball Record =====

class BallRecord(BaseModel):
    """Complete structured record for a single ball delivery."""
    ball_id: str = Field(..., description="Unique identifier: match_over_ball e.g. 'match001_14_3'")
    match_id: str = Field(..., description="Match identifier")
    innings: int = Field(default=1, ge=1, le=4)
    over: int = Field(default=0, ge=0)
    ball_number: int = Field(default=1, ge=1, le=10)  # up to 10 for extras

    # Players
    bowler_name: Optional[str] = None
    batsman_name: Optional[str] = None

    # Bowling analysis
    bowler_type: BowlerType = BowlerType.UNKNOWN
    line: Line = Line.UNKNOWN
    length: Length = Length.UNKNOWN
    variation: Variation = Variation.NONE
    bounce_behavior: BounceBehavior = BounceBehavior.UNKNOWN
    movement: Movement = Movement.UNKNOWN

    # Delivery sub-type (finer granularity for weakness cross-tabs).
    # All default to UNKNOWN so existing records are unaffected.
    swing_direction: SwingDirection = SwingDirection.UNKNOWN
    swing_type: SwingType = SwingType.UNKNOWN
    spin_direction: SpinDirection = SpinDirection.UNKNOWN
    ball_age_phase: BallAgePhase = BallAgePhase.UNKNOWN

    # Batting analysis
    shot_type: ShotType = ShotType.UNKNOWN
    footwork: Footwork = Footwork.UNKNOWN
    contact_quality: ContactQuality = ContactQuality.UNKNOWN

    # Result
    outcome: Outcome = Outcome.UNKNOWN
    runs_scored: int = Field(default=0, ge=0)

    # Tier-1 analytics enrichment
    shot_direction: ShotDirection = ShotDirection.UNKNOWN
    dismissal_type: DismissalType = DismissalType.NONE
    dismissal_fielder: Optional[str] = None
    bowling_speed_kmph: Optional[float] = None
    bowler_crease: BowlerCrease = BowlerCrease.UNKNOWN
    edge_type: EdgeType = EdgeType.NONE
    phase: InningsPhase = InningsPhase.UNKNOWN
    batsman_handedness: Handedness = Handedness.UNKNOWN

    # Confidence
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)

    # Metadata
    clip_path: Optional[str] = None
    clip_start_time: Optional[str] = None
    clip_end_time: Optional[str] = None
    raw_description: Optional[str] = None
    is_reviewed: bool = False
    reviewed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class MatchMetadata(BaseModel):
    """Metadata for a cricket match."""
    match_id: str
    format: str = Field(default="T20", description="T20, ODI, or Test")
    team_a: str = ""
    team_b: str = ""
    venue: Optional[str] = None
    date: Optional[str] = None
    match_date: Optional[str] = None        # ISO date if known (Tier-1 analytics)
    day_or_night: Optional[str] = None      # day | night | day_night | unknown
    source_url: Optional[str] = None
    video_path: Optional[str] = None


# ===== Gemini API Schema (for structured output) =====

GEMINI_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "bowler_type": {"type": "string", "enum": ["pace", "spin", "unknown"]},
        "line": {"type": "string", "enum": ["outside_off", "off_stump", "middle", "leg", "outside_leg", "unknown"]},
        "length": {"type": "string", "enum": ["yorker", "full", "good", "short_of_length", "short", "unknown"]},
        "variation": {"type": "string", "enum": ["none", "slower", "cutter", "bouncer", "yorker", "spin_variation", "unknown"]},
        "shot_type": {"type": "string", "enum": [
            # Broad fallbacks
            "drive", "cut", "pull", "hook", "defend", "sweep", "reverse_sweep",
            "glance", "flick", "lofted", "leave", "unknown",
            # Granular subtypes — prefer these when the shot is clearly identifiable
            "cover_drive", "straight_drive", "on_drive", "off_drive", "square_drive",
            "square_cut", "late_cut", "upper_cut",
            "front_foot_defence", "back_foot_defence",
            "slog_sweep", "paddle_sweep",
            "leg_glance",
            "helicopter", "scoop",
        ]},
        "footwork": {"type": "string", "enum": ["front_foot", "back_foot", "neutral", "unknown"]},
        "contact_quality": {"type": "string", "enum": ["clean", "mistimed", "edge", "miss", "unknown"]},
        "outcome": {"type": "string", "enum": ["dot", "1", "2", "3", "4", "6", "wicket", "wide", "no_ball", "unknown"]},
        "bounce_behavior": {"type": "string", "enum": ["low", "normal", "steep", "unknown"]},
        "movement": {"type": "string", "enum": ["none", "seam", "swing", "turn", "unknown"]},
        # Delivery sub-type fields — optional in required list so older matches
        # and low-confidence scenes don't block output.
        "swing_direction": {"type": "string", "enum": ["in_swing", "out_swing", "none", "unknown"]},
        "swing_type": {"type": "string", "enum": ["conventional", "late", "reverse", "none", "unknown"]},
        "spin_direction": {"type": "string", "enum": ["off_break", "leg_break", "googly", "arm_ball", "doosra", "carrom", "top_spin", "slider", "none", "unknown"]},
        "ball_age_phase": {"type": "string", "enum": ["new_ball", "old", "reverse_window", "unknown"]},
        # ── Tier-1 analytics enrichment ─────────────────────────────────────
        "shot_direction": {
            "type": "string",
            "enum": [
                "third_man", "deep_third", "point", "deep_point",
                "cover", "deep_cover", "mid_off", "long_off",
                "straight", "long_on", "mid_on", "mid_wicket",
                "deep_mid_wicket", "square_leg", "deep_square_leg",
                "fine_leg", "deep_fine_leg", "behind_wicket",
                "none", "unknown",
            ],
            "description": "16-position field map of where the ball travelled after bat/pad. From batter's POV."
        },
        "dismissal_type": {
            "type": "string",
            "enum": [
                "bowled", "caught", "lbw", "run_out", "stumped",
                "hit_wicket", "caught_and_bowled", "retired",
                "obstructing", "none", "unknown",
            ],
            "description": "How the wicket fell — required when outcome=wicket, otherwise 'none'."
        },
        "dismissal_fielder": {
            "type": "string",
            "description": "Fielder credited with the dismissal, e.g. 'Stokes at slip'. Empty if not applicable."
        },
        "bowling_speed_kmph": {
            "type": "number",
            "description": "Bowling speed read from the broadcast speed graphic (kmph). 0 if not visible."
        },
        "bowler_crease": {
            "type": "string",
            "enum": ["over_the_wicket", "round_the_wicket", "wide_of_crease", "unknown"]
        },
        "edge_type": {
            "type": "string",
            "enum": ["inside_edge", "outside_edge", "top_edge", "bottom_edge", "none", "unknown"],
            "description": "Bat-face / edge that contacted the ball. Required when contact_quality=edge, otherwise 'none'."
        },
        "phase": {
            "type": "string",
            "enum": ["powerplay", "middle_overs", "death", "unknown"],
            "description": "Innings phase. T20: powerplay=overs 1-6, middle=7-15, death=16-20. ODI: powerplay=1-10, middle=11-40, death=41-50. Auto-derived in normalizer if 'unknown'."
        },
        "batsman_handedness": {
            "type": "string",
            "enum": ["right_handed", "left_handed", "unknown"]
        },
        "over": {"type": "integer", "description": "Over number read from the scoreboard (e.g. 7 from '7.3'). 0 if not visible."},
        "ball_number": {"type": "integer", "description": "Ball within the over read from the scoreboard (e.g. 3 from '7.3'). 0 if not visible."},
        "runs_scored": {
            "type": "integer",
            "description": (
                "Runs scored off this ball — must be one of 0, 1, 2, 3, 4, 5, 6. "
                "Use 4 only for boundary fours and 6 only for sixes; do NOT use 4 "
                "for byes/leg-byes that ran four. Use 0 for dot balls, wickets, "
                "wides (the wide itself goes in `outcome`), and unclear cases."
            ),
            "minimum": 0,
            "maximum": 6,
        },
        "start_sec": {"type": "number", "description": "Seconds into this clip when the bowler begins run-up"},
        "end_sec": {"type": "number", "description": "Seconds into this clip when the ball is dead"},
        "bowler_name": {"type": "string"},
        "batsman_name": {"type": "string"},
        "raw_description": {"type": "string", "description": "Free-form 1-2 sentence description of what happened"},
        "confidence": {
            "type": "object",
            "properties": {
                "bowler_type": {"type": "number"},
                "line": {"type": "number"},
                "length": {"type": "number"},
                "shot_type": {"type": "number"},
                "outcome": {"type": "number"},
                "contact_quality": {"type": "number"},
                "swing_direction": {"type": "number"},
                "spin_direction": {"type": "number"},
                "swing_type": {"type": "number"},
                "bowler_name": {"type": "number"},
                "batsman_name": {"type": "number"},
                "shot_direction": {"type": "number"},
                "dismissal_type": {"type": "number"},
                "bowling_speed": {"type": "number"},
                "bowler_crease": {"type": "number"},
                "edge_type": {"type": "number"},
                "handedness": {"type": "number"}
            },
            "required": ["bowler_type", "line", "length", "shot_type", "outcome", "contact_quality"]
        }
    },
    "required": ["bowler_type", "line", "length", "shot_type", "outcome", "confidence", "raw_description"]
}
