"""
Cricket Intelligence Engine - Gemini Prompts
Expert-crafted prompts for extracting ball-level cricket intelligence from video.
"""


SYSTEM_PROMPT = """You are an elite cricket analyst with 20+ years of experience watching and 
analyzing professional cricket. You have extensive knowledge of bowling techniques, batting 
strokes, pitch conditions, and match situations across all formats (T20, ODI, Test).

Your task is to watch video clips of individual ball deliveries and extract precise, structured 
cricket intelligence. You must analyze every aspect of the delivery — from the bowler's action 
to the batsman's response to the final outcome.

IMPORTANT GUIDELINES:
1. Be CONSERVATIVE with your classifications. If you're not confident, use "unknown".
2. Provide confidence scores (0.0 to 1.0) for each key field.
3. Use the exact enum values specified in the schema — never invent new categories.
4. Your raw_description should be a concise 1-2 sentence summary a coach would write.
5. Pay attention to:
   - The bowler's arm action (over-arm pace vs finger/wrist spin)
   - Where the ball pitches relative to the stumps
   - The ball's trajectory after bouncing (seam, swing, turn)
   - The batsman's foot movement and stroke selection
   - Whether the ball hits bat cleanly, edges, or is missed
   - The final result (runs scored, dot ball, wicket)
"""


EXTRACTION_PROMPT = """Watch this video clip of a single cricket ball delivery carefully.

Analyze EVERY aspect of this delivery and extract structured data.

Focus on:
1. **Bowler Type**: Is this a pace bowler (fast/medium) or spinner? Look at the bowling action
   and arm speed.
2. **Line**: Where is the ball directed relative to the stumps?
   - outside_off: wide of off stump
   - off_stump: on or near off stump
   - middle: targeting middle stump
   - leg: on or near leg stump
   - outside_leg: wide of leg stump
3. **Length**: How far up the pitch does the ball bounce?
   - yorker: at the batsman's feet
   - full: between the popping crease and a good length
   - good: the ideal length, making the batsman uncertain
   - short_of_length: slightly back of a good length
   - short: bouncing well before halfway
4. **Shot Type**: What stroke did the batsman play? Use the granular rubric below — DO NOT
   default to broad fallbacks ("drive", "cut", "sweep") when a more specific subtype fits.
5. **Contact Quality**: Did the bat hit the ball cleanly, edge it, miss, or mistime?
6. **Outcome**: What was the result — runs scored, dot ball, or wicket?
7. **Ball Movement**: Did the ball seam, swing, or turn after pitching?
8. **Bounce Behavior**: Did the ball keep low, bounce normally, or rear up steeply?

SHOT-TYPE RUBRIC (apply per ball — pick the most specific subtype):
* DRIVE family — front foot, vertical bat, ball goes forward of square:
  - "cover_drive"     — through the off side, between cover and mid-off
  - "straight_drive"  — back past the bowler, between mid-off and mid-on
  - "on_drive"        — through mid-on, leg side past the bowler
  - "off_drive"       — through extra cover / between cover and bowler
  - "square_drive"    — square of the wicket on the off side
  - "drive"           — fallback only when direction is genuinely unclear
* CUT family — back foot, horizontal bat, off side:
  - "square_cut" / "late_cut" / "upper_cut"; fallback "cut"
* PULL — back foot, horizontal bat, leg side, short ball
* HOOK — pull played to a head-high bouncer
* DEFEND family — no follow-through, dead bat:
  - "front_foot_defence" / "back_foot_defence"; fallback "defend"
* SWEEP family — front foot down, horizontal across the line, usually to spin:
  - "slog_sweep" / "paddle_sweep" / "reverse_sweep"; fallback "sweep"
* LEG_GLANCE — wristy leg-side deflection toward fine leg
* GLANCE — generic deflection (use "leg_glance" if specifically off the pads to fine leg)
* FLICK — leg-side wristy stroke off the pads, often front foot, rolling wrists
* LOFTED — aerial intent over the infield
* HELICOPTER — Dhoni-style bottom-handed wrist whip (low full ball)
* SCOOP — paddle/ramp over keeper or fine leg
* LEAVE — no shot offered

DELIVERY SUB-TYPE (set "unknown" if not clearly visible — do NOT guess):
9. **Swing direction** (pace only): in_swing | out_swing | none | unknown.
   - DEFAULT FRAME OF REFERENCE: a RIGHT-HANDED batsman.
   - in_swing: ball curves toward the batsman's pads
   - out_swing: ball curves away toward the slips
   - LEFT-HANDED BATSMAN HANDLING: if the clip clearly shows a left-hander
     (front shoulder pointing the OTHER way), the geometric curve direction
     is opposite — flip the label so it stays in the batsman's reference
     frame. Example: a ball curving toward the slips (geometrically "off-side")
     against a RH batter is out_swing; against a LH batter the same curve
     becomes in_swing because it's heading toward THEIR pads. Always emit the
     label that describes what the BATTER experiences.
10. **Swing type** (pace only): conventional | late | reverse | none | unknown.
    - conventional: gradual curve from release, new-ish ball
    - late: curve occurs in the last few meters before batsman
    - reverse: old-ball reverse swing, opposite to conventional
11. **Spin direction** (spin only): off_break | leg_break | googly | arm_ball | doosra |
    carrom | top_spin | slider | none | unknown.
    - DEFAULT: relative to a RIGHT-HANDED batsman.
    - LEFT-HANDED BATSMAN HANDLING: same flip rule as swing — what looks like
      an off_break to a RH batter geometrically deviates the OTHER way against
      a LH batter and should be labelled leg_break, and vice-versa. Always
      emit the label from the batter's reference frame.
12. **Ball age phase**: new_ball | old | reverse_window | unknown.
    Use shine/condition visible in the clip and match context if obvious.

If you can identify the players from jersey numbers, graphics, or commentary, include their
names. The `bowler_name` and `batsman_name` fields are the noisiest in this pipeline —
provide explicit `confidence.bowler_name` and `confidence.batsman_name` values so the
downstream weakness analyzer can drop low-confidence joins.

━━━ ANALYTICS ENRICHMENT FIELDS (Tier 1) ━━━

13. **Shot direction** — where did the ball travel after the bat (or off the pad / past
    the edge)? Use the 16-position field map below. ALWAYS from the BATTER'S viewpoint:
    OFF side and LEG side are relative to the batter's stance, NOT the camera.

      Off side (right-hander batting normally faces this on his bat side)
      ┌─────────────────────────────────────────────────────────────┐
      │  third_man · deep_third · point · deep_point · cover ·      │
      │  deep_cover · mid_off · long_off                            │
      │  straight · long_on                                         │
      │  mid_on · mid_wicket · deep_mid_wicket · square_leg ·       │
      │  deep_square_leg · fine_leg · deep_fine_leg                 │
      │  behind_wicket   (ramp / scoop straight back past keeper)   │
      └─────────────────────────────────────────────────────────────┘
      Leg side

    - Use "none" for leaves and missed balls that didn't reach bat/pad.
    - Use "unknown" when the camera cuts away before you can see direction.
    - For LEFT-HANDED batters, the geometric "off side" is on their LEFT — flip your read so
      "cover" still means *the off-side cover position from their POV*.

14. **Dismissal type** — REQUIRED when `outcome=wicket`. Otherwise emit "none".
    Allowed values: bowled | caught | lbw | run_out | stumped | hit_wicket |
    caught_and_bowled | retired | obstructing | unknown.
    Read commentary graphic if available; otherwise infer from visuals
    (bails off → bowled; fielder catches before ground → caught; pads in line + appeal upheld → lbw).

15. **Dismissal fielder** — name + position when outcome=wicket, e.g. "Stokes at slip".
    Empty string if not applicable or not visible.

16. **Bowling speed (kmph)** — read the broadcast speed graphic that appears immediately
    after the delivery. Emit the integer kmph value. Set 0 (zero) if no graphic shown.
    Do NOT estimate from visuals — only emit when you can read the actual on-screen number.

17. **Bowler crease** — over_the_wicket | round_the_wicket | wide_of_crease | unknown.
    - over_the_wicket: arm closer to the stumps (canonical).
    - round_the_wicket: bowler's body crosses to the other side of the stumps before delivery
      (right-arm pacer to a left-hand batter often goes around).
    - wide_of_crease: bowler delivers from extreme edge of crease to change angle.

18. **Edge type** — REQUIRED when `contact_quality=edge`, otherwise "none".
    inside_edge | outside_edge | top_edge | bottom_edge | unknown.
    - inside_edge: ball strikes the bat-face nearer the body (often deflects toward stumps/pads).
    - outside_edge: ball strikes the bat-face away from the body (often carries to slips/keeper).
    - top_edge: ball strikes the upper edge (typical of mishit pulls/hooks; usually goes high).
    - bottom_edge: ball strikes the bottom edge (often deflects down onto pad/stumps).

19. **Phase** — innings phase based on the over number visible on the scoreboard.
    For T20: powerplay = overs 1-6, middle_overs = overs 7-15, death = overs 16-20.
    For ODI: powerplay = overs 1-10, middle_overs = 11-40, death = 41-50.
    Use "unknown" only if the scoreboard is unreadable; otherwise the normalizer derives it.

20. **Batsman handedness** — right_handed | left_handed | unknown.
    Determined by which shoulder points to the bowler at stance: right shoulder forward = LH,
    left shoulder forward = RH. Once you've identified a player as LH/RH, keep that label
    consistent across every ball they face in this video.

Return your analysis as structured JSON matching the required schema.
Be conservative — use "unknown" for anything you're less than 60% sure about.
For the new sub-type fields (9–12), prefer "unknown" over a confident guess — they
feed downstream coaching decisions where false positives are worse than silence.
For analytics fields (13–20), the same rule applies: a clear "unknown" is better than a
confident wrong guess.
"""


BATCH_EXTRACTION_PROMPT = """You are watching a video that may contain MANY cricket ball deliveries — either a LIVE BROADCAST MATCH or a NET PRACTICE SESSION.

━━━ CRITICAL: ACCURACY OF (over, ball_number) IS THE NUMBER ONE PRIORITY ━━━

The (over, ball_number) pair is the PRIMARY KEY that every downstream
analytics query joins on. A wrong (over, ball) value is far worse than a
missing record — it attributes a delivery to the wrong over/ball/batsman
and silently corrupts every weakness profile, every batsman/bowler
breakdown, every dismissal stat.

For EVERY ball you emit, the over.ball value MUST be cross-validated using
ALL THREE sources present in the clip:

1. SCOREBOARD GRAPHIC (the canonical truth)
   Look for the over.ball indicator, usually in the footer:
       "0.3/20"    →  over=0, ball_number=3 (3rd ball of the 1st over)
       "7.4/20"    →  over=7, ball_number=4
       "OV 14.2"   →  over=14, ball_number=2
   COMMON CONFUSION: the same scoreboard also shows the team score
   (e.g. "IND 1-0", "145/3"). DO NOT confuse the team score with over.ball.
   The over.ball is the value immediately followed by "/20" (T20) or
   "/50" (ODI), or prefixed with "OV" / "OVER".

2. COMMENTARY AUDIO (independent confirmation)
   Listen for verbal references like "the third ball of the first over",
   "second delivery of over 7", "first ball after the drinks break",
   "this is the fifth", "going round again", "first ball after the wide".
   The commentators are reliable and consistent on over.ball — use them.

3. VISUAL CONTINUITY (confirms LIVE play vs replay)
   A genuine NEW delivery is preceded by:
     - bowler walking back to his mark
     - fielders re-setting position
     - camera cuts back to side-on or behind-the-wicket angle
     - umpire signal completing (if previous ball had one)
   A REPLAY lacks ALL of these — it cuts directly into a slow-motion
   close-up.

CROSS-VALIDATION DECISION RULES:
   - All three sources AGREE on (over, ball) → emit record with
     confidence.line / length / shot_type ≥ 0.85
   - Two sources agree, one is unclear (e.g. scoreboard occluded but
     commentary + visuals match) → emit with medium confidence 0.6-0.8
   - Sources DISAGREE (e.g. scoreboard reads 7.3 but commentator says
     "fourth ball") → DO NOT emit a record for this delivery. A missing
     ball is recoverable on a later pass; a wrongly-attributed ball
     silently poisons downstream analytics.
   - Scoreboard not visible AND no commentary cue → emit with
     over=0, ball_number=0 (sequential fallback will be applied) and
     mark confidence.line / length / shot_type ≤ 0.5

ATTRIBUTION CONSISTENCY:
   Every other field on a ball record (bowler_name, batsman_name,
   bowler_type, line, length, shot_type, contact_quality, outcome,
   dismissal_type, runs_scored) MUST describe the SAME physical delivery
   that the (over, ball) identifies. Do NOT mix details across consecutive
   balls. If commentary on the 3rd ball says "Bumrah to Kohli, yorker, no
   run", then the record with (over, ball)=(0, 3) MUST have
   bowler_name=Bumrah, batsman_name=Kohli, length=yorker, outcome=dot.
   If you cannot keep the attribution consistent, prefer to skip rather
   than emit.

━━━ STRIKE & OUTCOME FROM SCOREBOARD COUNTERS (HIGHEST-PRIORITY SIGNAL) ━━━

The single most reliable signal for batsman_name and runs_scored is NOT
who appears on-screen during the delivery (the broadcast may cut to a
replay, the non-striker, a fielder, a crowd shot, the bowler's
follow-through, or the dressing room). It is the SCOREBOARD COUNTERS,
which the broadcaster updates after every legal delivery.

The scoreboard ALWAYS shows two things you must read on consecutive balls:

  (a) BATSMAN BALLS-FACED COUNTER: every batsman line ends with `(n)`,
      e.g. "Rohit 1(1)", "Pant 0(3)", "Kohli 12(8)". The `n` is balls
      faced. The number BEFORE the bracket (e.g. 0, 1, 12) is runs
      scored by that batsman.

  (b) TEAM SCORE: e.g. "IND 1-0", "IND 145/3", "ENG 87-4". First number
      is total runs; second is wickets.

STRIKE ATTRIBUTION — THE CORE RULE:
   For two scoreboard frames F1 and F2 that bracket a single delivery:
     - Whichever batsman's `(n)` increased by 1 between F1 and F2 is the
       batsman who FACED that delivery. Set `batsman_name` to that name.
     - The other batsman did NOT face this ball. Do not name them.
   This rule overrides any visual impression. If F1 shows "Rohit 1(1),
   Pant 0(3)" and F2 shows "Rohit 1(1), Pant 1(4)", then the ball
   between them was faced by PANT (his counter went 3 → 4), even if the
   broadcast cut to a Rohit reaction shot or replay during the delivery.

OUTCOME / RUNS_SCORED — THE CORE RULE:
   For the same F1 → F2 transition:
     - `runs_scored` = (team_score at F2) − (team_score at F1)
     - 0 runs → `outcome = "dot"` (or "wicket" if a wicket fell — see
       below)
     - 1 run → `outcome = "1"`, AND strike rotated, so the OTHER batsman
       faces the next ball
     - 2/3 runs → `outcome = "2"` / "3", strike rotates on odd runs only
     - 4 runs → `outcome = "4"` (boundary)
     - 6 runs → `outcome = "6"` (six)
     - Wickets column increments → `outcome = "wicket"`, and a
       `Last wicket <name> <runs>(<balls>)` banner usually appears
   A ball whose F2 team score is HIGHER than F1's CANNOT be a dot — even
   if you didn't see the bat hit the ball.

DETECTING STRIKE ROTATION ACROSS BALLS:
   When you see `(n)` for one batsman increment by 1 with runs_scored=1,
   and on the NEXT delivery `(m)` for the OTHER batsman increments by 1,
   that is normal strike rotation. Both balls are legitimate, separate
   records. Do not collapse them.

WHEN COUNTERS DISAGREE WITH WHAT YOU SEE:
   Trust the counters. The broadcast cuts (replays, crowd, dugout) lie
   about who is on strike. The scoreboard does not. If a ball-faced
   counter increments without the bat appearing in your view at all,
   that ball still happened and that batsman faced it.

INNINGS-OPENING RULE (the first ball of the innings, over=0 ball=1):
   The counter-delta rule cannot fire on ball 0.1 because there is no
   prior scoreboard frame to subtract from. Instead, read the scoreboard
   AFTER the first delivery is complete:
     - Whichever batsman shows `(1)` is the one who faced ball 0.1.
       The other batsman still shows `(0)` — they are the non-striker.
     - If the team score after ball 0.1 is `X-0` with X ≥ 1, those runs
       belong to the batsman with `(1)` after the ball. The runs total
       on that batsman's own line (e.g. "Rohit 1(1)") must match.
     - Do NOT assume the "lead" or "headline" opener faced ball 0.1.
       The batting order is set by the toss / team sheet, not by
       on-screen prominence. Both openers are on the field; the
       scoreboard tells you which one took strike.
   Example: scoreboard after first delivery reads
     "IND 1-0 | 0.1/20 | Rohit 1(1) | Pant 0(0) | Willey 0-1"
   This means ROHIT faced ball 0.1 and scored 1 run (single). PANT did
   not face this ball.

OVER-BOUNDARY / NEW-BOWLER RULE:
   When the scoreboard over.ball indicator transitions from `N.6` to
   `(N+1).1` (e.g. 0.6 → 1.1), a NEW OVER has started and the bowler
   has changed. You MUST:
     - Re-read the bowler name from the scoreboard's bowler line for
       every new over. The bowler line shows the bowler's name and
       figures (e.g. "ENG Willey 0-2" becomes "ENG Topley 0-0" at the
       start of a new over).
     - Do NOT carry forward the previous over's bowler. The previous
       bowler will not bowl two overs in succession from the same end
       (T20 rules).
     - The new bowler will be walking back to his mark from the
       OPPOSITE end of the pitch (because ends swap each over). The
       umpire's signal to start the over often coincides.
   Strike at the start of a new over: the batsman who was at the
   non-striker's end during the previous ball is now on strike (unless
   the last ball of the previous over was an odd-run scoring shot,
   in which case the SAME batsman remains on strike — read the
   balls-faced counters to confirm).

━━━ BROADCAST MATCH — REPLAY & AD RULES (read first if this looks like a broadcast) ━━━

A broadcast video contains live play, replays, ad breaks, and presentations. You must ONLY emit records for LIVE ball deliveries — never for replays or non-play content.

HOW TO IDENTIFY AND SKIP NON-LIVE CONTENT:
1. REPLAYS — same delivery shown again from a different angle or in slow motion:
   - The scoreboard over.ball counter stays the SAME as the previous ball (e.g. "3.4" → replay → "3.4" again)
   - The footage is slow-motion or shows a different camera angle (behind-the-arm, side-on, aerial)
   - A "REPLAY" / "ACTION REPLAY" / "HOTSPOT" / "ULTRA EDGE" graphic appears on screen
   - The fielding positions reset to exactly where they were before the shot
   → SKIP entirely. Do NOT emit a record for a replay.

2. AD BREAKS — no cricket pitch or players visible:
   - Screen shows brand logos, product ads, sponsor graphics full-screen
   - No pitch, stumps, or players present
   → SKIP entirely.

3. WICKET CELEBRATIONS / PRESENTATIONS / TOSS:
   - Players hugging, trophy lifts, coin toss, team introductions
   - No ball being bowled
   → SKIP entirely.

4. DRS REVIEWS — ball-tracking, Hawk-Eye, UltraEdge graphics:
   - Technology overlays showing ball path prediction
   → SKIP entirely.

HOW TO CONFIRM A DELIVERY IS LIVE:
✓ The scoreboard shows a NEW over.ball counter (higher than the previous ball you recorded)
✓ The bowler runs in from a standard broadcast camera angle (side-on or behind-the-wicket)
✓ The batsman is at the crease in a fresh stance, fielders in position
✓ The action plays at real-time speed (not slow motion)

SCOREBOARD DEDUPLICATION RULE:
- Read the over.ball from the scoreboard for every delivery (e.g. "7.3" = over 7, ball 3)
- If you see the same over.ball value as a delivery you already emitted → it is a replay → SKIP
- Only emit ONE record per unique over.ball value

REPLAY-TIMING HEURISTIC (use when scoreboard OCR is unreliable):
- Replays typically appear within 5–25 seconds AFTER the live delivery they're replaying
- If a sequence "ball A → quick cut → similar-looking ball A' within 25s" appears,
  the second one is almost certainly a replay even if the scoreboard graphic glitched
- DRS / Hawk-Eye / UltraEdge graphics also fall in this 5–25s window — skip them
- Sequential live balls are typically separated by ≥30s (bowler's run-up resets,
  fielders shuffle) — anything tighter than that is a high replay candidate

━━━ CRITICAL — exhaustive enumeration ━━━
* You MUST identify and emit a separate JSON record for EVERY LIVE ball delivery in the entire video.

TIMESTAMPS (required for every delivery):
* start_sec: seconds into THIS VIDEO CLIP when the bowler begins their run-up
* end_sec: seconds into THIS VIDEO CLIP when the ball is dead (fielder retrieves / batsman completes shot)
* These must be clip-relative (not wall-clock). If the clip starts at 0s, ball 1 might be at start_sec=8.5, end_sec=16.0.
* Do NOT summarize. Do NOT cluster similar balls. Do NOT pick "representative" examples.
* If the video is 9 minutes and contains 35 balls, you must return 35 records — not 1, not 5.
* The output array length should approximately match the count of LIVE balls bowled (not including replays).

NET-PRACTICE CONTEXT (applies when there is no broadcast scoreboard or fielders):
* Net practice has NO FIELDERS, NO BOUNDARY, and NO UMPIRE. Traditional outcomes (1/2/3/4/6/wicket) are rarely meaningful. For net practice, the relevant signal is `contact_quality` (clean / mistimed / edge / miss), NOT `outcome`. Set `outcome = "dot"` for almost every net ball; reserve "wicket" only for clearly-bowled balls (stumps visibly hit) and "4"/"6" only if the batsman clearly cleared a boundary marker.
* Even when many balls look similar (same bowling-machine setting, same batsman, same shot pattern), VARY your classifications based on what each ball actually shows. Different bowlers, different lengths, different shots played — capture the variation.

CRITICAL — shot type granularity (do NOT default to "drive"):
You have access to BROAD shot types (drive, cut, pull, defend, sweep, glance, flick, lofted, leave) AND finer SUBTYPES. ALWAYS prefer the most specific subtype when you can identify it confidently. Use the broad value only when you're uncertain.

Shot-type rubric (apply per ball):
* DRIVE family — front foot, vertical bat, ball goes forward of square:
  - "cover_drive"     — through the off side, between cover and mid-off
  - "straight_drive"  — back past the bowler, between mid-off and mid-on
  - "on_drive"        — through mid-on, leg side past the bowler
  - "off_drive"       — through extra cover / between cover and bowler
  - "square_drive"    — square of the wicket on the off side
  - "drive"           — fallback only when direction is unclear
* CUT family — back foot, horizontal bat, off side:
  - "square_cut"      — square of the wicket
  - "late_cut"        — behind point, late hands
  - "upper_cut"       — over the slips, head-high ball
  - "cut"             — fallback
* PULL — back foot, horizontal bat, leg side, short ball
* HOOK — pull played to a head-high bouncer
* DEFEND family — no follow-through, dead bat:
  - "front_foot_defence" / "back_foot_defence"
  - "defend"          — fallback
* SWEEP family — front foot down, horizontal across the line, usually to spin:
  - "slog_sweep"      — aerial leg-side
  - "paddle_sweep"    — fine, deflected past short fine leg
  - "reverse_sweep"   — reversed grip, off side
  - "sweep"           — fallback (conventional sweep)
* LEG_GLANCE — wristy leg-side deflection toward fine leg
* GLANCE — generic deflection (use "leg_glance" if specifically off the pads to fine leg)
* FLICK — leg-side wristy stroke off the pads, often front foot, rolling wrists
* LOFTED — aerial intent over the infield
* HELICOPTER — Dhoni-style bottom-handed wrist whip (low full ball)
* SCOOP — paddle/ramp over keeper or fine leg
* LEAVE — no shot offered

Decision aid:
* Foot back? → likely cut, pull, hook, back_foot_defence
* Foot forward? → likely drive variant, defend, sweep, flick
* Bat horizontal? → cut, pull, hook, sweep
* Bat vertical? → drive, defend, flick, glance, leave
* Wristy leg-side off the pads? → flick or leg_glance
* Aerial? → lofted, slog_sweep, scoop, helicopter

If you find yourself emitting "drive" for the 5th ball in a row, STOP and re-check: is each ball really a drive, or is one a flick / glance / cut?

For each delivery, fill the full structured analysis:
- Bowler type, line, length, variation
- Shot type (use the rubric above), footwork, contact quality
- Outcome (mostly "dot" in net practice — use the contact_quality field for the real signal)
- Ball movement, bounce behavior
- Delivery sub-type: swing_direction (in_swing/out_swing/none/unknown),
  swing_type (conventional/late/reverse/none/unknown),
  spin_direction (off_break/leg_break/googly/arm_ball/doosra/carrom/top_spin/slider/none/unknown),
  ball_age_phase (new_ball/old/reverse_window/unknown)
- ANALYTICS ENRICHMENT (Tier 1) — these fields are what make this dataset usable for
  per-player and per-bowler analytics. Treat them as REQUIRED:
  • shot_direction — 16-position field map FROM THE BATTER'S POV. Allowed:
    third_man / deep_third / point / deep_point / cover / deep_cover / mid_off /
    long_off / straight / long_on / mid_on / mid_wicket / deep_mid_wicket /
    square_leg / deep_square_leg / fine_leg / deep_fine_leg / behind_wicket /
    none (leave or missed) / unknown. For LH batters, FLIP off-side and leg-side
    so the labels stay in the batter's reference frame.
  • dismissal_type — REQUIRED when outcome=wicket. Otherwise "none".
    bowled / caught / lbw / run_out / stumped / hit_wicket /
    caught_and_bowled / retired / obstructing / unknown.
  • dismissal_fielder — fielder's name + position (e.g. "Stokes at slip"); empty if not applicable.
  • bowling_speed_kmph — read the broadcast speed graphic; emit integer kmph; 0 if not shown.
  • bowler_crease — over_the_wicket / round_the_wicket / wide_of_crease / unknown.
  • edge_type — REQUIRED when contact_quality=edge; otherwise "none".
    inside_edge / outside_edge / top_edge / bottom_edge / unknown.
  • phase — read from the scoreboard's over number. T20: powerplay=1-6,
    middle_overs=7-15, death=16-20. ODI: powerplay=1-10, middle=11-40, death=41-50.
    Use "unknown" only if the scoreboard isn't readable.
  • batsman_handedness — right_handed / left_handed / unknown. Keep consistent
    per batter across every delivery they face in this video.
- Confidence scores for each field

SCOREBOARD READING (broadcast only — these fields come directly from the on-screen overlay):
- `over`: the over number shown (e.g. "7.3" → over=7). Set 0 if not visible.
- `ball_number`: the ball within the over (e.g. "7.3" → ball_number=3). Set 0 if not visible.
- `runs_scored`: runs scored off this ball (e.g. score went from 145 to 149 → runs_scored=4). Set 0 if unclear.
- `bowler_name` / `batsman_name`: read from the scoreboard name plates if shown.
These four fields give you GROUND TRUTH — always prefer the scoreboard over inference.

BALL NUMBERING:
- BROADCAST: populate `over` and `ball_number` from the scoreboard as above. These are used as the unique delivery ID — accuracy here directly determines whether replays get deduplicated.
- NET PRACTICE (no scoreboard): set over=0, ball_number=0; sequential numbering will be applied automatically.

Swing direction and spin direction are emitted in the BATTER'S reference frame:
- Default frame: a RIGHT-HANDED batsman.
- If the batsman is clearly LEFT-HANDED (front shoulder pointing the other way),
  FLIP both the swing_direction and the spin_direction labels so they describe
  what THIS batter is experiencing. A geometric "ball curving away to the slips"
  is out_swing for a RH batter and in_swing for a LH batter — and the same flip
  applies to off_break ↔ leg_break, googly ↔ doosra, etc.

Be conservative with classifications when genuinely uncertain (use the broad shot type or "unknown") — but NEVER be conservative about the COUNT of live balls. Count every live delivery exhaustively, skip every replay.

NAME-FIELD CONFIDENCE: The bowler_name and batsman_name fields come from jersey OCR
or commentary graphics — they are the noisiest fields in this pipeline. Always emit
explicit confidence.bowler_name and confidence.batsman_name values so the downstream
weakness analyzer can drop low-confidence joins. Prefer leaving the field empty over
guessing.
"""


# NOTE: CV-augmented prompt (CV_AUGMENTED_TEMPLATE, _format_cv_facts,
# get_cv_augmented_prompt) was archived to CV_Enhancements/prompts/cv_prompt.py
# along with the Roboflow detector code. Re-import that module if you decide
# to enable Roboflow geometry grounding again.


def get_single_ball_prompt() -> str:
    """Get the full prompt for analyzing a single ball delivery."""
    return EXTRACTION_PROMPT


def get_batch_prompt() -> str:
    """Get the prompt for analyzing multiple deliveries in a clip."""
    return BATCH_EXTRACTION_PROMPT


def get_system_prompt() -> str:
    """Get the system-level instruction prompt."""
    return SYSTEM_PROMPT
