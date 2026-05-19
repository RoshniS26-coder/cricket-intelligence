"""
Cricket Intelligence Engine - Human Review UI
Streamlit app for reviewing and correcting ball-level extractions.
"""

import json
import sys
from pathlib import Path

import streamlit as st
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.db import CricketDB
from src.intelligence.schema import (
    Line, Length, ShotType, BowlerType,
    Footwork, ContactQuality, Outcome,
    Variation, BounceBehavior, Movement,
)


# ===== Page Config =====
st.set_page_config(
    page_title="Cricket Intelligence - Review",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== Custom CSS =====
st.markdown("""
<style>
    .stApp { background-color: #ffffff; }   
    .confidence-high { color: #00ff88; font-weight: bold; }
    .confidence-mid { color: #ffaa00; font-weight: bold; }
    .confidence-low { color: #ff4444; font-weight: bold; }
    .ball-header { 
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        padding: 1rem; border-radius: 0.5rem;
        border: 1px solid #333; margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ===== Initialize DB =====
@st.cache_resource
def get_db():
    return CricketDB()


db = get_db()


# ===== Sidebar =====
st.sidebar.title("🏏 Cricket Intelligence")
st.sidebar.markdown("### Ball Review Dashboard")

# Mode selection
mode = st.sidebar.radio(
    "Mode",
    ["📊 Dashboard", "🔍 Review Balls", "📋 Full Dataset", "⚠️ Weakness Analysis"],
    index=0,
)

# Match filter
matches = db.list_matches()
match_ids = [m.match_id for m in matches]
selected_match = st.sidebar.selectbox(
    "Select Match",
    ["All"] + match_ids,
    index=0,
)
match_filter = None if selected_match == "All" else selected_match


# ===== Dashboard Mode =====
if mode == "📊 Dashboard":
    st.title("📊 Cricket Intelligence Dashboard")

    stats = db.get_stats(match_filter)

    if stats.get("total", 0) == 0:
        st.info(
            "No ball records yet. Run the extraction pipeline first:\n\n"
            "```bash\n"
            "python -m src.intelligence.extractor --dir data/ball_clips/ --match-id my_match\n"
            "```"
        )
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Balls", stats["total"])
        with col2:
            st.metric("Reviewed", f"{stats['reviewed']}/{stats['total']}")
        with col3:
            st.metric("Avg Confidence", f"{stats['avg_confidence']:.1%}")
        with col4:
            st.metric("Unknowns", stats.get("unknown_count", 0))

        st.markdown("---")

        # Outcome distribution
        if stats.get("outcomes"):
            st.subheader("Outcome Distribution")
            outcomes_df = pd.DataFrame(
                list(stats["outcomes"].items()),
                columns=["Outcome", "Count"],
            )
            st.bar_chart(outcomes_df.set_index("Outcome"))

        # Review progress
        st.subheader("Review Progress")
        review_pct = stats.get("review_pct", 0)
        st.progress(review_pct / 100)
        st.caption(f"{review_pct:.1f}% reviewed")


# ===== Review Mode =====
elif mode == "🔍 Review Balls":
    st.title("🔍 Ball Review Interface")

    # Get unreviewed balls
    review_only = st.checkbox("Show only unreviewed", value=True)

    if review_only:
        balls = db.get_balls_needing_review(match_filter)
    elif match_filter:
        balls = db.get_balls_for_match(match_filter)
    else:
        balls = []

    if not balls:
        st.success("🎉 All balls reviewed!" if review_only else "No balls found.")
    else:
        st.info(f"📝 {len(balls)} balls to review")

        # Ball selector
        ball_options = [f"Over {b.over_number}.{b.ball_number} — {b.ball_id}" for b in balls]
        selected_idx = st.selectbox("Select Ball", range(len(ball_options)), format_func=lambda i: ball_options[i])

        ball = balls[selected_idx]

        st.markdown("---")

        # Two-column layout: Video + Fields
        col_video, col_fields = st.columns([1, 1])

        with col_video:
            st.subheader(f"🎬 Over {ball.over_number}.{ball.ball_number}")

            # Show video clip if available
            if ball.clip_path and Path(ball.clip_path).exists():
                st.video(ball.clip_path)
            else:
                st.warning("Video clip not available")

            # Raw description
            if ball.raw_description:
                st.markdown("**AI Description:**")
                st.info(ball.raw_description)

            # Confidence scores
            st.markdown("**Confidence Scores:**")
            conf_data = {
                "Line": ball.confidence_line,
                "Length": ball.confidence_length,
                "Shot": ball.confidence_shot_type,
                "Outcome": ball.confidence_outcome,
            }
            for field, score in conf_data.items():
                color = "🟢" if score > 0.7 else "🟡" if score > 0.4 else "🔴"
                st.write(f"{color} {field}: {score:.0%}")

        with col_fields:
            st.subheader("📝 Edit Fields")

            with st.form(key=f"review_{ball.ball_id}"):
                enum_options = lambda e: [v.value for v in e]

                new_bowler_type = st.selectbox("Bowler Type", enum_options(BowlerType), index=enum_options(BowlerType).index(ball.bowler_type))
                new_line = st.selectbox("Line", enum_options(Line), index=enum_options(Line).index(ball.line))
                new_length = st.selectbox("Length", enum_options(Length), index=enum_options(Length).index(ball.length))
                new_shot = st.selectbox("Shot Type", enum_options(ShotType), index=enum_options(ShotType).index(ball.shot_type))
                new_contact = st.selectbox("Contact", enum_options(ContactQuality), index=enum_options(ContactQuality).index(ball.contact_quality))
                new_outcome = st.selectbox("Outcome", enum_options(Outcome), index=enum_options(Outcome).index(ball.outcome))
                new_footwork = st.selectbox("Footwork", enum_options(Footwork), index=enum_options(Footwork).index(ball.footwork))
                review_notes = st.text_area("Notes", value=ball.review_notes or "")

                submitted = st.form_submit_button("✅ Save Review", use_container_width=True)

                if submitted:
                    updates = {
                        "bowler_type": new_bowler_type,
                        "line": new_line,
                        "length": new_length,
                        "shot_type": new_shot,
                        "contact_quality": new_contact,
                        "outcome": new_outcome,
                        "footwork": new_footwork,
                        "review_notes": review_notes,
                    }
                    db.update_ball_review(ball.ball_id, updates)
                    st.success(f"✅ Ball {ball.ball_id} reviewed!")
                    st.rerun()


# ===== Full Dataset Mode =====
elif mode == "📋 Full Dataset":
    st.title("📋 Full Ball Dataset")

    if match_filter:
        balls = db.get_balls_for_match(match_filter)
    else:
        balls = []
        for m in matches:
            balls.extend(db.get_balls_for_match(m.match_id))

    if not balls:
        st.info("No ball records found.")
    else:
        # Compact view (display only)
        df = pd.DataFrame([{
            "Ball ID": b.ball_id,
            "Inn": b.innings,
            "Over": f"{b.over_number}.{b.ball_number}",
            "Bowler": b.bowler_name,
            "Batsman": b.batsman_name,
            "Line": b.line,
            "Length": b.length,
            "Shot": b.shot_type,
            "Contact": b.contact_quality,
            "Outcome": b.outcome,
            "Runs": b.runs_scored,
            "Reviewed": "✅" if b.is_reviewed else "❌",
        } for b in balls])

        st.dataframe(df, use_container_width=True, height=600)

        # Rich export (full 28-column dataset — same columns as export_csv CLI helper)
        export_df = pd.DataFrame([{
            "ball_id": b.ball_id,
            "innings": b.innings,
            "over_number": b.over_number,
            "ball_number": b.ball_number,
            "bowler_name": b.bowler_name,
            "batsman_name": b.batsman_name,
            "outcome": b.outcome,
            "runs_scored": b.runs_scored,
            "dismissal_type": b.dismissal_type,
            "dismissal_fielder": b.dismissal_fielder,
            "bowler_type": b.bowler_type,
            "line": b.line,
            "length": b.length,
            "variation": b.variation,
            "bowler_crease": b.bowler_crease,
            "swing_direction": b.swing_direction,
            "movement": b.movement,
            "spin_direction": b.spin_direction,
            "bowling_speed_kmph": b.bowling_speed_kmph,
            "ball_age_phase": b.ball_age_phase,
            "shot_type": b.shot_type,
            "footwork": b.footwork,
            "contact_quality": b.contact_quality,
            "edge_type": b.edge_type,
            "shot_direction": b.shot_direction,
            "batsman_handedness": b.batsman_handedness,
            "phase": b.phase,
            "raw_description": b.raw_description,
        } for b in balls])
        csv = export_df.to_csv(index=False)
        st.caption(f"CSV export contains all {len(export_df.columns)} fields ({len(export_df)} rows, both innings).")
        st.download_button(
            "📥 Export CSV (full)",
            csv,
            file_name=f"match_{match_filter or 'all'}_balls.csv",
            mime="text/csv",
        )


# ===== Weakness Analysis Mode =====
elif mode == "⚠️ Weakness Analysis":
    st.title("⚠️ Batsman Weakness Analysis")

    from src.analytics.weakness import compute_weakness_profile

    # Batsman selector
    batsmen = db.list_batsmen(match_filter)
    if not batsmen:
        st.warning(
            "No batsman names found in the database yet.\n\n"
            "Batsman names are extracted by Gemini during ingestion. "
            "Run the pipeline with videos where the batsman is identifiable."
        )
        st.stop()

    selected_batsman = st.selectbox("Select Batsman", batsmen)
    min_conf = st.slider("Min line/length confidence", 0.0, 1.0, 0.5, 0.05,
                         help="Exclude balls where Gemini was less confident about line or length")

    balls = db.get_balls_for_batsman(
        batsman_name=selected_batsman,
        match_id=match_filter,
        min_confidence=min_conf,
    )

    if not balls:
        st.info(f"No qualifying balls for '{selected_batsman}' at confidence ≥ {min_conf:.0%}. Try lowering the threshold.")
        st.stop()

    profile = compute_weakness_profile(balls, batsman_name=selected_batsman)
    zones = profile.get("zones", [])
    top = profile.get("top_weakness")

    st.markdown(f"**{len(balls)} balls analysed** across {len(zones)} danger zones")

    # Top callouts — strength and weakness side by side
    top_s = profile.get("top_strength")
    col_w, col_s = st.columns(2)
    with col_w:
        if top:
            st.error(
                f"**⚠ PRIMARY WEAKNESS**\n\n"
                f"{top['line'].replace('_', ' ').title()} / {top['length'].replace('_', ' ').title()} — "
                f"{top['dismissals']} dismissals in {top['total']} balls "
                f"({top['dismissal_rate']:.0%} dismissal rate)"
            )
    with col_s:
        if top_s:
            st.success(
                f"**✅ PRIMARY STRENGTH**\n\n"
                f"{top_s['line'].replace('_', ' ').title()} / {top_s['length'].replace('_', ' ').title()} — "
                f"avg {top_s['avg_runs']} runs/ball, {top_s['boundaries']} boundaries "
                f"in {top_s['total']} balls"
            )

    st.markdown("---")

    # Pitch map — rendered inline automatically
    if zones:
        st.subheader("Pitch Map")
        from src.analytics.pitch_map import render_pitch_map
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            render_pitch_map(profile, output_path=tmp_path,
                             title=selected_batsman)
            st.image(tmp_path, use_container_width=True,
                     caption="Bird's-eye danger heatmap — red = high danger, green = safe, grey = no data")
        finally:
            os.unlink(tmp_path)

    st.markdown("---")

    # Wagon wheel — scoring zones from shot_direction
    runs_by_dir = {}
    for b in balls:
        if b.shot_direction and b.shot_direction not in ("unknown", "none"):
            runs_by_dir[b.shot_direction] = runs_by_dir.get(b.shot_direction, 0) + (b.runs_scored or 0)

    if runs_by_dir:
        st.subheader("Wagon Wheel")
        from src.analytics.heatmaps import render_wagon_wheel
        import tempfile, os

        handedness = next(
            (b.batsman_handedness for b in balls
             if b.batsman_handedness and b.batsman_handedness != "unknown"),
            "right_handed",
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            ww_path = tmp.name
        try:
            render_wagon_wheel(
                direction_metric=runs_by_dir,
                handedness=handedness,
                title=selected_batsman,
                subtitle="Runs scored by zone",
                output_path=ww_path,
                metric_label="runs",
            )
            st.image(
                ww_path,
                use_container_width=True,
                caption=(
                    f"Runs scored per scoring zone "
                    f"({handedness.replace('_', '-')}). "
                    "Bowler is at top, behind-the-keeper at bottom; off side and leg side "
                    "auto-mirror for left-handers."
                ),
            )
        finally:
            os.unlink(ww_path)

        st.markdown("---")

    # Zone grid (line × length heatmap as DataFrame)
    if zones:
        st.subheader("Danger Zone Grid")

        _LINES_ORDER = ["outside_leg", "leg", "middle", "off_stump", "outside_off"]
        _LENGTHS_ORDER = ["yorker", "full", "good", "short_of_length", "short"]

        zone_index = {(z["length"], z["line"]): z for z in zones}
        grid_data = {}
        for line in _LINES_ORDER:
            col_data = {}
            for length in _LENGTHS_ORDER:
                z = zone_index.get((length, line))
                col_data[length.replace("_", " ")] = round(z["danger_score"], 2) if z else None
            grid_data[line.replace("_", " ")] = col_data

        grid_df = pd.DataFrame(grid_data, index=[l.replace("_", " ") for l in _LENGTHS_ORDER])

        st.caption("Cells show danger score (0=safe, 1=very dangerous). Grey = insufficient data.")
        st.dataframe(
            grid_df.style.background_gradient(cmap="RdYlGn_r", vmin=0, vmax=1, axis=None),
            use_container_width=True,
        )

        # Full zone tables — weakness and strength side by side
        col_zt, col_st = st.columns(2)
        with col_zt:
            st.subheader("⚠ Danger Zones")
            zone_df = pd.DataFrame([{
                "Line": z["line"].replace("_", " "),
                "Length": z["length"].replace("_", " "),
                "Balls": z["total"],
                "Dismissals": z["dismissals"],
                "Avg runs": z["avg_runs"],
                "Danger": z["danger_score"],
            } for z in zones])
            st.dataframe(zone_df, use_container_width=True)

        strengths = profile.get("strengths", [])
        with col_st:
            st.subheader("✅ Strength Zones")
            if strengths:
                str_df = pd.DataFrame([{
                    "Line": z["line"].replace("_", " "),
                    "Length": z["length"].replace("_", " "),
                    "Balls": z["total"],
                    "Boundaries": z["boundaries"],
                    "Avg runs": z["avg_runs"],
                    "Strength": z["strength_score"],
                } for z in strengths])
                st.dataframe(str_df, use_container_width=True)
            else:
                st.info("No scoring zones with sufficient data yet.")

    st.markdown("---")

    # Breakdown tabs
    tab_bowler, tab_variation = st.tabs(["By Bowler Type", "By Variation"])

    with tab_bowler:
        by_bowler = profile.get("by_bowler_type", {})
        if by_bowler:
            bdf = pd.DataFrame([
                {"Type": k, "Balls": v["total"], "Dismissals": v["dismissals"],
                 "Danger Score": v["danger_score"]}
                for k, v in by_bowler.items()
            ])
            st.dataframe(bdf, use_container_width=True)
        else:
            st.info("Insufficient data per bowler type.")

    with tab_variation:
        by_var = profile.get("by_variation", {})
        if by_var:
            vdf = pd.DataFrame([
                {"Variation": k, "Balls": v["total"], "Dismissals": v["dismissals"],
                 "Danger Score": v["danger_score"]}
                for k, v in by_var.items()
            ])
            st.dataframe(vdf, use_container_width=True)
        else:
            st.info("Insufficient data per variation.")

    st.markdown("---")

    # Gemini narrative (on-demand)
    st.subheader("AI Coaching Narrative")
    if st.button("Generate Bilingual Analysis (Gemini)", type="primary"):
        from match_intelligence.lib.weakness_narrator import narrate_weakness
        with st.spinner("Calling Gemini..."):
            narrative = narrate_weakness(profile)
        if narrative:
            st.markdown("**Overall Profile**")
            st.info(narrative.get("summary_en", ""))
            st.caption(narrative.get("summary_hi", ""))

            col_str, col_bowl = st.columns(2)
            with col_str:
                st.markdown("**✅ Strengths**")
                st.success(narrative.get("strengths_en", ""))
                st.caption(narrative.get("strengths_hi", ""))
            with col_bowl:
                st.markdown("**⚠ Bowling Plan**")
                st.error(narrative.get("bowling_plan_en", ""))
                st.caption(narrative.get("bowling_plan_hi", ""))

            st.markdown("**Batting Advice**")
            st.warning(narrative.get("batting_advice_en", ""))
            st.caption(narrative.get("batting_advice_hi", ""))
        else:
            st.error("Narrative generation failed — check GEMINI_API_KEY.")
