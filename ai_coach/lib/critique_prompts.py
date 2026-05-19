"""
Prompts and JSON schema for the few-shot Gemini critique module.

The critique compares a student's shot clip against N reference clips of ideal
technique by professional players (Kohli, Tendulkar, Rohit, Dravid, etc.) and
returns a structured JSON object with identified shot, technique deviations,
and drill recommendations.
"""

CRITIQUE_SYSTEM_PROMPT = (
    "You are an elite Indian cricket coach with 20+ years of experience analyzing "
    "batsman technique at academy and first-class level. You speak directly, cite "
    "specific visual details from the clips, and never give generic advice. "
    "Your job is to compare a student's shot attempt against textbook reference "
    "clips of professionals and produce structured, actionable corrections that "
    "an academy coach can give to a kid the same day."
)


CRITIQUE_PROMPT_TEMPLATE = """You have just been shown {n_references} REFERENCE video clip(s) demonstrating the IDEAL execution of a cricket {shot_type}, played by professional players. After the references, you have been shown 1 clip of {player_name} — an attempt at the same shot by a player who is learning.

Your task:

1. **Confirm the shot type {player_name} is attempting.** It should be {shot_type}. If {player_name} clearly played a different shot, set `identified_shot_type` to what they actually played and `overall_quality_rating` to `needs_major_work`, with one deviation about wrong shot selection.

2. **Identify 2–4 specific TECHNIQUE DEVIATIONS** from the references. Focus on observable details such as:
   - Head position at impact (over the ball vs. falling across)
   - Front-foot stride length and direction
   - Back-foot position and weight transfer
   - Bat swing path (vertical / across the line / angled)
   - Balance through the shot and into follow-through
   - Body shape (closed / open / sideways)
   - Hands and grip at impact
   - Eye line at the moment of contact

3. **For each deviation:**
   - `aspect`: short label, e.g. `head_position`, `front_foot_stride`, `bat_swing_path`
   - `observed`: 1–2 sentence factual description of what you saw in {player_name}'s clip. Use the player's name (or "they") rather than "the student" or "the batsman".
   - `ideal_per_reference`: 1–2 sentence description of what the REFERENCE clip(s) show as the correct version
   - `severity`: low | medium | high
   - `estimated_correction_effort`: 1-2 sessions | 1-2 weeks | ongoing

4. **Recommend 2–3 specific drills** (10–15 minutes each, equipment available at any Indian academy: cones, bowling machine, bat, tennis balls) that address the highest-severity deviations. Each drill must have a `drill_name`, `duration_minutes`, `frequency`, and the `addresses_aspect` it targets.

5. **Overall quality rating:** close_to_ideal | needs_minor_work | needs_major_work.

6. **Encouragement** — one short sentence (≤20 words) on what {player_name} is doing well. Address {player_name} by name or as "you" — do NOT use "the student" or "the batsman". Always include something positive — no player is hopeless.

Be specific and concrete. Cite actual visual details from the clips ("the bat angles toward the off side at impact" — NOT "improve technique"). Never give generic advice.

Return strict JSON matching the provided schema. No markdown, no commentary outside the JSON."""


CRITIQUE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "identified_shot_type": {
            "type": "string",
            "description": "The cricket shot the student actually played (e.g. cover_drive, pull, defend)."
        },
        "shot_match_confidence": {
            "type": "number",
            "description": "0.0–1.0 confidence that the student's shot matches the requested shot_type."
        },
        "overall_quality_rating": {
            "type": "string",
            "enum": ["close_to_ideal", "needs_minor_work", "needs_major_work"]
        },
        "deviations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "aspect": {"type": "string"},
                    "observed": {"type": "string"},
                    "ideal_per_reference": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "estimated_correction_effort": {
                        "type": "string",
                        "enum": ["1-2 sessions", "1-2 weeks", "ongoing"]
                    }
                },
                "required": ["aspect", "observed", "ideal_per_reference", "severity"]
            }
        },
        "drill_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "drill_name": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                    "frequency": {"type": "string"},
                    "addresses_aspect": {"type": "string"}
                },
                "required": ["drill_name", "duration_minutes", "frequency"]
            }
        },
        "encouragement": {"type": "string"}
    },
    "required": ["identified_shot_type", "overall_quality_rating", "deviations", "encouragement"]
}


def get_critique_system_prompt() -> str:
    return CRITIQUE_SYSTEM_PROMPT


def get_critique_prompt(n_references: int, shot_type: str, player_name: str = "the player") -> str:
    body = CRITIQUE_PROMPT_TEMPLATE.format(
        n_references=n_references,
        shot_type=shot_type,
        player_name=player_name,
    )
    return body + "\n\n" + get_focus_block(mode="single_ball", shot_type=shot_type)


# ── Net-session variant (Phase 1 multi-shot pipeline) ────────────────────────
# Used when the student clip is a full net practice session with MULTIPLE
# attempts at the same shot type, rather than one ball.
# Reuses CRITIQUE_JSON_SCHEMA — output shape is identical, but the deviations
# describe RECURRING patterns instead of one-off observations.
CRITIQUE_NET_SESSION_PROMPT_TEMPLATE = """You have just been shown {n_references} REFERENCE video clip(s) demonstrating the IDEAL execution of a cricket {shot_type}, played by professional players.

After the references, you have been shown 1 clip of {player_name} — but this one is a NET PRACTICE SESSION, not a single ball. {player_name} has attempted the {shot_type} MULTIPLE TIMES across this session.

Your task — adapted for the multi-attempt context:

1. **Confirm the dominant shot type {player_name} was practicing.** It should be {shot_type}. If {player_name} spent most of the session on a different shot, set `identified_shot_type` to what they actually played the most and lower the `shot_match_confidence`.

In all your output text (deviations.observed, encouragement, etc.), refer to the player by name ("{player_name}" or "they") — do NOT use "the student" or "the batsman".

2. **Identify 2–4 RECURRING TECHNIQUE DEVIATIONS** that appear across multiple attempts. Focus on patterns that repeat across the session (e.g. "head falls toward off side on most drives", "stride collapses against full balls"), NOT on one-off mistakes. A pattern that occurred in just 1 of 10 attempts is not a recurring deviation; either skip it or downgrade severity.

3. **For each deviation:**
   - `aspect`: short label, e.g. `head_position`, `front_foot_stride`, `bat_swing_path`
   - `observed`: cite frequency explicitly — e.g. *"Observed in roughly 7 of ~12 attempts: head dips toward the off side at impact, with eye line shifting right."* Make the count visible to the coach.
   - `ideal_per_reference`: 1–2 sentence description from the reference clips
   - `severity`: low | medium | high — should reflect (frequency × impact). A pattern in 8 of 10 balls = high; 3 of 10 = medium; 1 of 10 = low or skip.
   - `estimated_correction_effort`: 1-2 sessions | 1-2 weeks | ongoing

4. **Recommend 2–3 drills** that target the most-recurring issues (priority by severity × frequency). Each drill: `drill_name`, `duration_minutes`, `frequency`, `addresses_aspect`.

5. **Overall quality rating** — close_to_ideal | needs_minor_work | needs_major_work — reflecting the SESSION-AVERAGE quality, not the worst single ball.

6. **Encouragement** — one specific positive observation about the session as a whole. Cite a trend if visible ("your timing improved through the session" / "your balance was consistent across all attempts" / "you used your feet well to good-length balls").

Be specific and concrete. Cite actual visual details from the clips. Quote coaching language from the EXPERT COACHING GUIDANCE above when applicable. Never give generic advice.

If the student session contains essentially one usable attempt (e.g. only one ball played the requested shot, or the rest are unusable), say so in the deviations and rate based on that single attempt — but flag low confidence.

Return strict JSON matching the provided schema. No markdown."""


def get_net_session_critique_prompt(n_references: int, shot_type: str, player_name: str = "the player") -> str:
    body = CRITIQUE_NET_SESSION_PROMPT_TEMPLATE.format(
        n_references=n_references,
        shot_type=shot_type,
        player_name=player_name,
    )
    return body + "\n\n" + get_focus_block(mode="net_session", shot_type=shot_type)


# ── Solo variants (Phase 1 reference-free critique) ──────────────────────────
# Used when no reference clips are provided. Gemini uses its intrinsic cricket
# knowledge + the (optional) coaching corpus context to critique the student.
# Output schema unchanged.
CRITIQUE_SOLO_PROMPT_TEMPLATE = """You have been shown 1 clip of {player_name} — an attempt at a cricket {shot_type} by a player learning the technique. NO reference clips have been provided this time.

Use your intrinsic cricket knowledge to critique {player_name} against the TEXTBOOK IDEAL for a {shot_type}. If EXPERT COACHING GUIDANCE was provided above, ground your deviations in those specific points and quote the coach's language directly. Otherwise, draw on standard coaching principles for this shot.

In all your output text (deviations.observed, encouragement, etc.), refer to the player by name ("{player_name}" or "they") — do NOT use "the student" or "the batsman".

Your task:

1. **Confirm the shot type {player_name} is attempting.** It should be {shot_type}.

2. **Identify 2–4 specific TECHNIQUE DEVIATIONS** from the textbook ideal (or from the expert coaching guidance above, if provided). Focus on observable details:
   - Head position at impact
   - Front-foot stride direction and length
   - Bat swing path (vertical / across the line)
   - Balance through the shot
   - Body shape (closed / open / sideways)
   - Hands and grip at impact
   - Eye line at contact

3. **For each deviation:**
   - `aspect`: short label (head_position, front_foot_stride, etc.)
   - `observed`: 1–2 sentences on what you saw in the STUDENT clip
   - `ideal_per_reference`: describe the textbook ideal — "the textbook ideal for a {shot_type} is..." If you have coaching context, paraphrase from it. If not, use standard coaching principles. NEVER invent player-specific specifics you can't see (e.g., do NOT say "Kohli does X" if no reference clip showed that).
   - `severity`: low | medium | high
   - `estimated_correction_effort`: 1-2 sessions | 1-2 weeks | ongoing

4. **Recommend 2–3 drills** addressing the highest-severity deviations.

5. **Overall quality rating**: close_to_ideal | needs_minor_work | needs_major_work.

6. **Encouragement** — one short positive observation.

Important constraint without references:
* Be HONEST about uncertainty. If you cannot tell whether a specific aspect is correct (e.g., grip angle in a 5-second clip), set severity to low or skip that aspect — don't fabricate.
* Stay grounded in what you actually see in the student clip + what the textbook says. Do NOT invent specific numbers, angles, or player citations.

Return strict JSON matching the provided schema. No markdown."""


CRITIQUE_NET_SESSION_SOLO_PROMPT_TEMPLATE = """You have been shown 1 clip of {player_name} — a NET PRACTICE SESSION where {player_name} attempted a cricket {shot_type} MULTIPLE TIMES. NO reference clips have been provided this time.

Use your intrinsic cricket knowledge to critique {player_name} against the TEXTBOOK IDEAL for a {shot_type}, focusing on RECURRING patterns across attempts. If EXPERT COACHING GUIDANCE was provided above, ground your deviations in that coach's specific points; otherwise rely on standard coaching principles.

In all your output text (deviations.observed, encouragement, etc.), refer to the player by name ("{player_name}" or "they") — do NOT use "the student" or "the batsman".

Your task — adapted for multi-attempt + reference-free context:

1. **Confirm the dominant shot type** {player_name} was practicing. Should be {shot_type}. If the session was actually a different shot, set `identified_shot_type` accordingly and lower `shot_match_confidence`.

2. **Identify 2–4 RECURRING TECHNIQUE DEVIATIONS** that appear across multiple attempts. Cite frequency in `observed` (e.g. *"Observed in roughly 7 of ~12 attempts: head dips toward off side"*). One-off mistakes should not be recurring deviations.

3. **For each deviation:**
   - `aspect`: short label
   - `observed`: cite frequency + the specific visual detail
   - `ideal_per_reference`: describe the textbook ideal — "the textbook ideal for a {shot_type} is..." Quote coaching context if provided. NEVER invent player-specific citations you can't see.
   - `severity`: reflect frequency × impact
   - `estimated_correction_effort`

4. **Recommend 2–3 drills** targeting the most-recurring issues.

5. **Overall quality rating** — session-average, not the worst ball.

6. **Encouragement** — cite a specific positive trend across the session.

Important constraint without references:
* Be HONEST about uncertainty — if you can't see something clearly, skip it rather than fabricating specifics
* Stay grounded in textbook coaching for this shot + what you actually see
* Do NOT invent player citations or specific numbers you can't measure

Return strict JSON matching the provided schema. No markdown."""


# ── Auto-anchor: canonical reference player per shot ────────────────────────
# When the user runs solo mode (no reference clips uploaded) and doesn't pass
# an explicit --reference-player, we auto-anchor on the canonical player for
# that shot type. Gemini already has rich training on these famous players —
# naming them in the prompt steers the critique toward their known technique.
#
# Edit this table to change defaults; pass --no-auto-anchor to skip entirely.
CANONICAL_PLAYERS_BY_SHOT: dict[str, str] = {
    # Drives
    "cover_drive":         "Virat Kohli",
    "straight_drive":      "Sachin Tendulkar",
    "on_drive":            "Sachin Tendulkar",
    "off_drive":           "Rahul Dravid",
    "square_drive":        "Sourav Ganguly",
    "drive":               "Virat Kohli",            # broad fallback

    # Cuts
    "cut":                 "Virender Sehwag",
    "square_cut":          "Virender Sehwag",
    "late_cut":            "VVS Laxman",
    "upper_cut":           "Virender Sehwag",

    # Pull / hook
    "pull":                "Rohit Sharma",
    "hook":                "Ricky Ponting",

    # Defense
    "defend":              "Rahul Dravid",
    "front_foot_defence":  "Rahul Dravid",
    "back_foot_defence":   "Cheteshwar Pujara",

    # Sweep family
    "sweep":               "Kumar Sangakkara",
    "slog_sweep":          "Yuvraj Singh",
    "paddle_sweep":        "Tilakaratne Dilshan",
    "reverse_sweep":       "AB de Villiers",

    # Wristy / leg-side
    "glance":              "VVS Laxman",
    "leg_glance":          "VVS Laxman",
    "flick":               "Virat Kohli",

    # Innovative / aerial
    "lofted":              "Yuvraj Singh",
    "helicopter":          "MS Dhoni",
    "scoop":               "Tilakaratne Dilshan",

    # Leave
    "leave":               "Cheteshwar Pujara",
}


def resolve_reference_player(
    shot_type: str,
    explicit: str | None = None,
    auto_anchor: bool = True,
) -> str | None:
    """Pick which named player (if any) to anchor the critique on.

    Precedence:
      1. Explicit --reference-player wins (user override)
      2. If auto_anchor=True (default), look up the canonical player for shot_type
      3. Otherwise None — the prompt falls back to generic textbook ideal
    """
    if explicit:
        return explicit
    if auto_anchor:
        return CANONICAL_PLAYERS_BY_SHOT.get(shot_type.lower())
    return None


# ── Prompt-based focus (attention steering, no code_execution tool) ──────────
# These blocks tell Gemini WHERE in the video to focus its analysis without
# any zoom/crop mechanism. The model already sees the whole video at ~1fps;
# these instructions raise the attention weight on the diagnostic moments
# (impact frame, foot landing, head at contact) and the shot-specific cues
# that matter most for coaching.

FOCUS_IMPACT_FRAME_SINGLE = """ATTENTION FOCUS — devote the majority of your analysis to the moment of bat-ball contact (the IMPACT FRAME). Mentally pause on that single frame and scrutinize, in this order:

  1. HEAD POSITION at impact — is it directly over the front foot, or falling across the line?
  2. BAT ANGLE & DIRECTION at contact — vertical / across the line / angled? full face vs closing?
  3. EYE LINE at impact — tracking the ball or pulled away?
  4. FRONT-FOOT LANDING — toward the pitch of the ball, across, or short?
  5. BACK-FOOT POSITION — anchored or floating?
  6. BALANCE & WEIGHT TRANSFER — over which foot at the moment of strike?
  7. HANDS at contact — close to the body, or reaching forward?

Treat stance, run-up, and follow-through as SUPPORTING context — they explain WHY the impact-frame technique looks the way it does. The impact frame is where coaching deviations become observable.
"""

FOCUS_IMPACT_FRAME_NET_SESSION = """ATTENTION FOCUS — this is a multi-attempt net session. For EACH attempt at the {shot_type}, mentally pause on the moment of bat-ball contact and inspect head position, bat angle, foot landing, balance, and hands.

Then AGGREGATE across attempts:
  • Which technique aspects are CONSISTENT (a recurring fault, or a recurring strength)?
  • Which aspects are VARIABLE (the player is still figuring out)?
  • Are best-attempts visibly different from worst-attempts? In what way?

The deviations you flag must describe RECURRING patterns visible at the impact frame in MOST attempts — not one-off slips. Cite frequency in `observed` (e.g. "in roughly 7 of ~12 attempts").
"""

# Per-shot diagnostic addenda — what to look for at impact for THIS specific shot.
# Keep each entry to 1–2 sentences; this is concentrated coaching wisdom, not a textbook.
SHOT_SPECIFIC_FOCUS: dict[str, str] = {
    # Drive family
    "cover_drive":         "For a COVER DRIVE specifically, watch whether the front shoulder, front elbow, and bat backlift are aligned toward the bowler at impact. If they point toward the covers, the bat face is closing across the ball — the #1 cause of edges to slip.",
    "straight_drive":      "For a STRAIGHT DRIVE specifically, the bat must come straight down the line of the ball, head directly over the ball at contact, follow-through pointing back at the bowler. Any across-the-line bat path is a fault.",
    "on_drive":            "For an ON DRIVE specifically, the front leg must clear (NOT block the bat path); the bat threads through the gap between the front pad and the bowler. Head position is everything — falling across destroys this shot.",
    "off_drive":           "For an OFF DRIVE specifically, watch the bat path between cover and mid-off and whether the front foot lands toward the pitch of the ball (not across). Head must be over the ball.",
    "square_drive":        "For a SQUARE DRIVE specifically, scrutinize whether the back foot moved across to give space, and whether the head is over the line of the ball at impact.",
    "drive":               "For a DRIVE generically, the most diagnostic detail is HEAD over the FRONT FOOT at impact and BAT coming down the line of the ball (not across).",

    # Cut family
    "cut":                 "For a CUT specifically, head must be OVER the line of the ball (not pulled toward leg), back foot moves across to give space, hands play late. Hands too early = catches to slip.",
    "square_cut":          "For a SQUARE CUT specifically, watch the back foot moving across, late hands, and bat horizontal at impact. Head height — falling = top edge.",
    "late_cut":            "For a LATE CUT specifically, hands play VERY late, bat angles down to deflect, eyes track the ball INTO the bat. The latest contact possible is the right one.",
    "upper_cut":           "For an UPPER CUT specifically, eyes track the bouncing ball over the slips area; bat angled UP at contact. Loss of head control = top edge to keeper.",

    # Pull / hook
    "pull":                "For a PULL specifically, the BACK FOOT must be deep in the crease and braced. Head MUST stay level (not fall toward off side). Bat plane must be HORIZONTAL at impact, not angled.",
    "hook":                "For a HOOK specifically, head should be INSIDE the line (eyes watching the ball pass). Loss of head control = top edge to fine leg. Hook is a controlled-risk shot — note any breakdown of head discipline.",

    # Defence
    "defend":              "For a DEFENCE generically, soft hands at impact (giving with the ball), dead-faced bat, head over the ball, no follow-through.",
    "front_foot_defence":  "For FRONT-FOOT DEFENCE specifically, at impact: soft hands, bat slightly angled down, head OVER the ball, weight forward but balanced. Bat away from body = edges.",
    "back_foot_defence":   "For BACK-FOOT DEFENCE specifically, at impact: weight on back foot, head over the ball line, bat dead-faced. Body must rock back BEFORE the ball arrives.",

    # Sweep family
    "sweep":               "For a SWEEP specifically, head must be OVER the line of the ball, bat horizontal, front knee bent, body balanced for rotation. Head falling backward = top edge to fine leg.",
    "slog_sweep":          "For a SLOG SWEEP specifically, head still through the swing, bat coming UP through the ball (not across), full body rotation, balance maintained.",
    "paddle_sweep":        "For a PADDLE SWEEP specifically, hands deflect rather than strike, bat angled fine to dab past short fine leg, head completely still.",
    "reverse_sweep":       "For a REVERSE SWEEP specifically, hands cross during the shot, bat angled to deflect off side, head locked on the ball line.",

    # Wristy / leg-side
    "glance":              "For a GLANCE generically, wrists roll the ball, bat face deflects (does not strike), head completely still, balance maintained.",
    "leg_glance":          "For a LEG GLANCE specifically, the bat face deflects the ball off the pads toward fine leg. Head still and wrists relaxed = clean glance; tense hands = miscued contact.",
    "flick":               "For a FLICK specifically, hips rotate, wrists ROLL the ball off the pads, bat face vertical at impact, head still. Wrist roll is the signature — without it, it's a defend, not a flick.",

    # Aerial / innovation
    "lofted":              "For a LOFTED shot specifically, head MUST stay still through the swing, full follow-through over the shoulder, balance maintained over both feet at impact. Falling = miscued lofted shot.",
    "helicopter":          "For a HELICOPTER shot specifically, bottom-hand whips through and wrist rotation FINISHES HIGH above the head, balance over the back foot. Without the wrist rotation, it's just a flick.",
    "scoop":               "For a SCOOP specifically, head goes UNDER the ball line (not over), bat tilted upward, hands play under and through. Head over the ball = miscued.",

    # Leave
    "leave":               "For a LEAVE specifically, hands kept high and inside, head still tracking the ball, bat raised vertically out of the path. Reaching for the ball with bat = unintended edge.",
}


def get_focus_block(mode: str, shot_type: str) -> str:
    """Build the attention-focus instructions injected into critique prompts.

    Combines a generic impact-frame focus (single_ball or net_session variant)
    with a shot-specific diagnostic addendum from SHOT_SPECIFIC_FOCUS.
    """
    if mode == "net_session":
        base = FOCUS_IMPACT_FRAME_NET_SESSION.format(shot_type=shot_type)
    else:
        base = FOCUS_IMPACT_FRAME_SINGLE
    specific = SHOT_SPECIFIC_FOCUS.get(shot_type.lower(), "")
    if specific:
        return f"{base}\n{specific}\n"
    return f"{base}\n"


def _reference_player_clause(reference_player: str | None, shot_type: str) -> str:
    """Anchor text injected into solo prompts when a named reference player is set.

    When None (or auto_anchor=False), returns empty string and the prompt
    relies on a generic 'textbook ideal' framing.
    """
    if not reference_player:
        return ""
    rp = reference_player.strip()
    return (
        f"\nREFERENCE PLAYER ANCHOR — Use {rp}'s widely-known textbook execution "
        f"of the {shot_type} as the canonical reference for what 'ideal' looks like. "
        f"Draw on {rp}'s well-documented technical characteristics for this shot "
        f"(stance, head position, footwork, bat path, follow-through, common cues "
        f"associated with their style) from cricket commentary, coaching content, "
        f"and match footage you've been trained on.\n\n"
        f"In every `ideal_per_reference` field, phrase the ideal as "
        f"\"{rp}'s textbook execution shows...\" or \"as {rp} typically does...\". "
        f"Stay faithful to widely-documented aspects of their technique — do NOT "
        f"invent frame-specific details or fabricate quotes you cannot verify. "
        f"If you are uncertain about a specific aspect of {rp}'s technique, "
        f"fall back to the textbook ideal for that shot rather than guessing.\n"
    )


def get_solo_critique_prompt(
    shot_type: str,
    player_name: str = "the player",
    reference_player: str | None = None,
) -> str:
    body = CRITIQUE_SOLO_PROMPT_TEMPLATE.format(
        shot_type=shot_type,
        player_name=player_name,
    )
    return (
        _reference_player_clause(reference_player, shot_type)
        + body
        + "\n\n"
        + get_focus_block(mode="single_ball", shot_type=shot_type)
    )


def get_net_session_solo_critique_prompt(
    shot_type: str,
    player_name: str = "the player",
    reference_player: str | None = None,
) -> str:
    body = CRITIQUE_NET_SESSION_SOLO_PROMPT_TEMPLATE.format(
        shot_type=shot_type,
        player_name=player_name,
    )
    return (
        _reference_player_clause(reference_player, shot_type)
        + body
        + "\n\n"
        + get_focus_block(mode="net_session", shot_type=shot_type)
    )
