"""
PDF renderer for hybrid PlayerBriefing.

Single-page A4. Uses reportlab Platypus. Designed to be readable at arm's
length, printable in black & white (no color-only signals — uses text symbols
✓/⚠/✗ alongside any color), and shareable on WhatsApp.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ai_coach.lib.briefing import PlayerBriefing


# ── Style palette ────────────────────────────────────────────────────────────
_INK = colors.HexColor("#1a1a1a")
_MUTED = colors.HexColor("#6a6a6a")
_OK = colors.HexColor("#2e7d32")
_WARN = colors.HexColor("#c77700")
_BAD = colors.HexColor("#b00020")
_HEADER_BG = colors.HexColor("#0f3a5f")
_HEADER_FG = colors.white
_RULE = colors.HexColor("#cccccc")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title":     ParagraphStyle("title",     parent=base["Heading1"], fontSize=18, leading=22, textColor=_INK, spaceAfter=2),
        "subtitle":  ParagraphStyle("subtitle",  parent=base["Normal"],  fontSize=10, leading=12, textColor=_MUTED, spaceAfter=6),
        "section":   ParagraphStyle("section",   parent=base["Heading2"], fontSize=11, leading=14, textColor=_HEADER_BG, spaceBefore=8, spaceAfter=4),
        "body":      ParagraphStyle("body",      parent=base["Normal"],  fontSize=9.5, leading=12, textColor=_INK),
        "muted":     ParagraphStyle("muted",     parent=base["Normal"],  fontSize=9, leading=11, textColor=_MUTED),
        "tag":       ParagraphStyle("tag",       parent=base["Normal"],  fontSize=8, leading=10, textColor=_MUTED),
        "drill":     ParagraphStyle("drill",     parent=base["Normal"],  fontSize=9.5, leading=12, leftIndent=10, textColor=_INK),
        "cue":       ParagraphStyle("cue",       parent=base["Italic"],  fontSize=10, leading=13, leftIndent=10, textColor=_INK),
    }


def _flag_color(flag: str) -> colors.Color:
    return {"✓": _OK, "⚠": _WARN, "✗": _BAD}.get(flag, _MUTED)


def _severity_color(severity: str) -> colors.Color:
    return {"low": _OK, "medium": _WARN, "high": _BAD}.get((severity or "").lower(), _MUTED)


def _rating_color(rating: str | None) -> colors.Color:
    return {
        "close_to_ideal":   _OK,
        "needs_minor_work": _WARN,
        "needs_major_work": _BAD,
    }.get(rating or "", _MUTED)


def _header_block(b: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    mode_tag = " &nbsp;<font size=9 color='#888'>[net session]</font>" if b.mode == "net_session" else ""
    title_text = f"<b>{b.player_name}</b> &nbsp;·&nbsp; {b.shot_type.replace('_', ' ').title()}{mode_tag}"
    sub_bits = [b.generated_at.strftime("%d %b %Y, %H:%M")]
    if b.academy:
        sub_bits.append(b.academy)
    if b.ball_id:
        sub_bits.append(f"ball: {b.ball_id}")
    sub_bits.append(f"clip: {Path(b.clip_path).name}")

    out = [
        Paragraph(title_text, S["title"]),
        Paragraph("  ·  ".join(sub_bits), S["subtitle"]),
    ]

    # Net-session catalog footer (Phase-1 multi-shot polish):
    # Show "Session: 18 deliveries — 12 cover_drive · 4 defend · 2 pull"
    # Plus contact-quality breakdown if available (net practice has no real
    # outcomes; contact_quality is the meaningful signal).
    if b.shot_counts:
        total = sum(b.shot_counts.values())
        shot_breakdown = " · ".join(
            f"{n} {s}" for s, n in sorted(b.shot_counts.items(), key=lambda kv: -kv[1])
        )
        out.append(Paragraph(
            f"<font color='#555'>Session detected:</font> "
            f"<b>{total}</b> deliveries — {shot_breakdown}",
            S["muted"],
        ))
        if b.contact_counts:
            contact_breakdown = " · ".join(
                f"{n} {c}" for c, n in sorted(b.contact_counts.items(), key=lambda kv: -kv[1])
            )
            out.append(Paragraph(
                f"<font color='#555'>Contact quality:</font> {contact_breakdown}",
                S["muted"],
            ))

    out.append(HRFlowable(width="100%", thickness=1.2, color=_RULE, spaceBefore=2, spaceAfter=6))
    return out


def _technique_metrics_block(b: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    out = [Paragraph("TECHNIQUE METRICS &nbsp;<font size=8 color='#888'>(MediaPipe pose, at impact frame)</font>", S["section"])]
    if not b.metrics:
        out.append(Paragraph("Pose analysis not available for this clip "
                             "(camera angle off, low resolution, or no impact detected).", S["muted"]))
        return out

    rows = [["Metric", "Value", "Target", ""]]
    for m in b.metrics:
        val_str = "—" if m.value is None else str(m.value)
        rows.append([m.name, val_str, m.target or "—", m.flag])

    table = Table(rows, colWidths=[88 * mm, 30 * mm, 25 * mm, 12 * mm])
    style = TableStyle([
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",    (0, 0), (-1, 0), _HEADER_FG),
        ("BACKGROUND",   (0, 0), (-1, 0), _HEADER_BG),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f6f6")]),
        ("ALIGN",        (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN",        (3, 1), (3, -1), "CENTER"),
    ])
    for i, m in enumerate(b.metrics, start=1):
        style.add("TEXTCOLOR", (3, i), (3, i), _flag_color(m.flag))
    table.setStyle(style)
    out.append(table)
    return out


def _gemini_block(b: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    out = [Paragraph("DELIVERY &amp; SHOT &nbsp;<font size=8 color='#888'>(Gemini extraction)</font>", S["section"])]
    g = b.gemini or {}
    if not g:
        out.append(Paragraph("Gemini extraction not available.", S["muted"]))
        return out

    line1_bits = [
        f"<b>Bowler:</b> {g.get('bowler_type', '?')}",
        f"<b>Line:</b> {g.get('line', '?')}",
        f"<b>Length:</b> {g.get('length', '?')}",
        f"<b>Swing:</b> {g.get('swing_direction', '?')}",
        f"<b>Spin:</b> {g.get('spin_direction', '?')}",
    ]
    line2_bits = [
        f"<b>Shot:</b> {g.get('shot_type', '?')}",
        f"<b>Footwork:</b> {g.get('footwork', '?')}",
        f"<b>Contact:</b> {g.get('contact_quality', '?')}",
        f"<b>Outcome:</b> {g.get('outcome', '?')}",
    ]
    out.append(Paragraph("&nbsp;|&nbsp; ".join(line1_bits), S["body"]))
    out.append(Paragraph("&nbsp;|&nbsp; ".join(line2_bits), S["body"]))
    if g.get("raw_description"):
        out.append(Spacer(1, 3))
        out.append(Paragraph(f"<i>“{g['raw_description']}”</i>", S["muted"]))
    return out


def _critique_block(b: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    out = [Paragraph("CRITIQUE vs REFERENCES &amp; COACHING CONTEXT", S["section"])]
    if not b.critique:
        out.append(Paragraph("Critique not run for this clip — pass --references to enable.", S["muted"]))
        return out

    rating = b.overall_rating or "?"
    rating_para = Paragraph(
        f"<b>Overall rating:</b> "
        f"<font color='{_rating_color(rating).hexval()}'><b>{rating.replace('_', ' ').upper()}</b></font>"
        + (f" &nbsp;<font size=8 color='#888'>(vs {len(b.reference_clips)} reference(s)</font>" if b.reference_clips else "")
        + (f"<font size=8 color='#888'> + coaching context: {', '.join(b.coaching_keys_used)})</font>" if b.coaching_keys_used else
           "<font size=8 color='#888'>)</font>" if b.reference_clips else ""),
        S["body"],
    )
    out.append(rating_para)
    out.append(Spacer(1, 4))

    # Deviations table
    if b.deviations:
        rows = [["#", "Aspect", "Observed", "Ideal (per reference)", "Sev"]]
        for i, d in enumerate(b.deviations, start=1):
            rows.append([
                str(i),
                Paragraph(d.aspect, S["body"]),
                Paragraph(d.observed, S["body"]),
                Paragraph(d.ideal, S["body"]),
                d.severity.upper(),
            ])
        table = Table(rows, colWidths=[8 * mm, 42 * mm, 58 * mm, 58 * mm, 12 * mm])
        style = TableStyle([
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR",    (0, 0), (-1, 0), _HEADER_FG),
            ("BACKGROUND",   (0, 0), (-1, 0), _HEADER_BG),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("VALIGN",       (0, 1), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f6f6")]),
            ("ALIGN",        (4, 0), (4, -1), "CENTER"),
            ("ALIGN",        (0, 0), (0, -1), "CENTER"),
        ])
        for i, d in enumerate(b.deviations, start=1):
            style.add("TEXTCOLOR", (4, i), (4, i), _severity_color(d.severity))
            style.add("FONTNAME",  (4, i), (4, i), "Helvetica-Bold")
        table.setStyle(style)
        out.append(table)
    else:
        out.append(Paragraph("No deviations flagged.", S["muted"]))

    return out


def _drills_and_cues_block(b: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    out = []

    if b.drills:
        out.append(Paragraph("RECOMMENDED DRILLS", S["section"]))
        for i, d in enumerate(b.drills, start=1):
            bits = [d.name]
            extra = []
            if d.duration_minutes:
                extra.append(f"{d.duration_minutes} min")
            if d.frequency:
                extra.append(d.frequency)
            if d.addresses:
                extra.append(f"→ {d.addresses}")
            tail = f" &nbsp;<font size=8 color='#888'>({'  ·  '.join(extra)})</font>" if extra else ""
            src_tag = f" <font size=7 color='#888'>[{d.source}]</font>"
            out.append(Paragraph(f"{i}. {bits[0]}{tail}{src_tag}", S["drill"]))

    if b.coaching_cues:
        out.append(Paragraph("COACHING CUES &nbsp;<font size=8 color='#888'>(from coaching corpus)</font>", S["section"]))
        for cue in b.coaching_cues[:5]:        # cap to keep the page clean
            out.append(Paragraph(f"“{cue}”", S["cue"]))

    if b.common_mistakes_quoted:
        out.append(Paragraph("COMMON MISTAKES TO WATCH FOR", S["section"]))
        for m in b.common_mistakes_quoted[:4]:
            out.append(Paragraph(f"• {m}", S["body"]))

    return out


def _footer_block(b: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    out = []
    if b.encouragement:
        out.append(Paragraph("ENCOURAGEMENT", S["section"]))
        out.append(Paragraph(f"<i>{b.encouragement}</i>", S["body"]))

    out.append(Spacer(1, 14))
    out.append(HRFlowable(width="100%", thickness=0.4, color=_RULE))
    out.append(Spacer(1, 6))
    sig = (
        f"<font size=8 color='#888'>"
        f"Generated {b.generated_at.strftime('%Y-%m-%d %H:%M')} &nbsp;·&nbsp; "
        f"Reviewed by coach: ___________________________  &nbsp;·&nbsp;  "
        f"Date: ____________"
        f"</font>"
    )
    out.append(Paragraph(sig, S["muted"]))
    return out


def _build_briefing_story(briefing: PlayerBriefing, S: dict[str, ParagraphStyle]) -> list:
    """Build the reportlab flowable list for one briefing.

    Used by both render_briefing_pdf (single-shot) and render_multi_shot_pdf
    (multi-section). Inserts PageBreak before subsequent sections externally.
    """
    story = []
    story += _header_block(briefing, S)
    story += _technique_metrics_block(briefing, S)
    story.append(Spacer(1, 6))
    story += _gemini_block(briefing, S)
    story.append(Spacer(1, 6))
    story += _critique_block(briefing, S)
    story.append(Spacer(1, 6))
    story += _drills_and_cues_block(briefing, S)
    story += _footer_block(briefing, S)
    return story


def render_briefing_pdf(briefing: PlayerBriefing, output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"{briefing.player_name} — {briefing.shot_type} briefing",
        author="Cricket Intelligence Engine",
    )

    S = _styles()
    doc.build(_build_briefing_story(briefing, S))
    return str(out)


def render_multi_shot_pdf(
    briefings: list[PlayerBriefing],
    output_path: str,
    document_title: str | None = None,
) -> str:
    """Render multiple briefings into one multi-page PDF, one section per shot type.

    Each briefing renders as a full single-shot section, with a page break
    between sections. Useful for net practice sessions where the player
    attempted multiple shot types and you want coaching for each.
    """
    if not briefings:
        raise ValueError("render_multi_shot_pdf requires at least one briefing")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    title = document_title or (
        f"{briefings[0].player_name} — multi-shot session briefing "
        f"({len(briefings)} shot types)"
    )
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
        author="Cricket Intelligence Engine",
    )

    S = _styles()
    story = []
    for i, b in enumerate(briefings):
        if i > 0:
            story.append(PageBreak())
        story.extend(_build_briefing_story(b, S))

    doc.build(story)
    return str(out)
