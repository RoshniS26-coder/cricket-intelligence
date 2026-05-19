"""Cricket heatmap renderers.

Three visualisations:

  1. render_pitch_heatmap(counts, ...) — 5 × 5 line × length grid for
     frequency / runs / dismissals (any int/float metric per cell).
     Reused for bowler-perspective ("balls bowled here") and batter-perspective
     ("balls faced here").

  2. render_danger_map(profile, ...) — same 5 × 5 grid but driven by a
     weakness profile dict (with per-zone danger_score, dismissals, total).
     Cells labelled "{dismissals}w/{total}". Empty zones rendered grey.

  3. render_wagon_wheel(direction_metric, handedness, ...) — polar bar chart
     of the 16-position field map. Used for batter scoring zones (runs per
     direction).

All three write a PNG and return its absolute path.
"""

from __future__ import annotations

from pathlib import Path

# ── Pitch-map config ─────────────────────────────────────────────────

# Line order: left (leg) → right (off) when viewing from BEHIND THE BOWLER
# (i.e. broadcast side-on view of a right-handed batter).
_LINES = ["outside_leg", "leg", "middle", "off_stump", "outside_off"]
_LINE_LABELS = ["Outside\nLeg", "Leg", "Middle", "Off\nStump", "Outside\nOff"]

# Length order: top = yorker (closest to batter) → bottom = short (furthest)
_LENGTHS = ["yorker", "full", "good", "short_of_length", "short"]
_LENGTH_LABELS = ["Yorker", "Full", "Good\nlength", "Short of\nlength", "Short"]


def render_pitch_heatmap(
    counts: dict,
    title: str,
    subtitle: str = "",
    output_path: str = "data/heatmaps/pitch.png",
    cmap_name: str = "YlOrRd",
    cell_label: str = "balls",
    show_zero_cells: bool = True,
) -> str:
    """Render a 5 × 5 line × length heatmap.

    Args:
        counts: dict keyed by (length, line) → int/float. Missing keys = 0.
        title: top chart title (typically the player name).
        subtitle: second-line title (e.g. "balls bowled" or "scoring map").
        output_path: where to save the PNG.
        cmap_name: matplotlib colormap. Use "YlOrRd" for frequency,
                   "RdYlGn_r" for danger (high=red), etc.
        cell_label: word displayed in legend (e.g. "balls", "runs").
        show_zero_cells: if True, zero-cells are drawn dim grey;
                         if False, left blank.

    Returns:
        Absolute path to saved PNG.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    n_len = len(_LENGTHS)
    n_lin = len(_LINES)

    # Build value matrix
    grid = np.zeros((n_len, n_lin))
    for row, length in enumerate(_LENGTHS):
        for col, line in enumerate(_LINES):
            grid[row, col] = counts.get((length, line), 0)

    vmax = grid.max() if grid.max() > 0 else 1
    cmap = plt.get_cmap(cmap_name)

    fig, ax = plt.subplots(figsize=(8, 10))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    for row in range(n_len):
        for col in range(n_lin):
            val = grid[row, col]
            if val == 0 and not show_zero_cells:
                continue
            norm = val / vmax if vmax else 0
            color = cmap(norm) if val > 0 else "#2a2a3e"
            text_color = "white" if norm > 0.4 else ("#222" if val > 0 else "#555566")
            label = str(int(val)) if val > 0 else "–"

            rect = mpatches.FancyBboxPatch(
                (col + 0.05, n_len - row - 0.95),
                0.9, 0.9,
                boxstyle="round,pad=0.05",
                facecolor=color,
                edgecolor="#1a1a2e",
                linewidth=2,
            )
            ax.add_patch(rect)
            ax.text(
                col + 0.5, n_len - row - 0.5,
                label,
                ha="center", va="center",
                fontsize=11, color=text_color, fontweight="bold",
            )

    ax.set_xlim(0, n_lin)
    ax.set_ylim(0, n_len)
    ax.set_xticks([i + 0.5 for i in range(n_lin)])
    ax.set_xticklabels(_LINE_LABELS, color="white", fontsize=9)
    ax.set_yticks([n_len - i - 0.5 for i in range(n_len)])
    ax.set_yticklabels(_LENGTH_LABELS, color="white", fontsize=9)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.text(n_lin / 2, -0.6, "← Leg side          Off side →",
            ha="center", color="#aaaacc", fontsize=8)
    ax.text(-0.8, n_len / 2, "Short\n↑\nFull",
            ha="center", va="center", color="#aaaacc", fontsize=8, rotation=90)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(cell_label, color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white")
    for label in cbar.ax.yaxis.get_ticklabels():
        label.set_color("white")

    total = int(grid.sum())
    full_title = f"{title}\n{subtitle}" if subtitle else title
    ax.set_title(
        f"{full_title}    (total: {total} {cell_label})",
        color="white", fontsize=13, fontweight="bold", pad=16,
    )

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return str(out.resolve())


def render_danger_map(
    profile: dict,
    output_path: str = "data/reports/danger_map.png",
    title: str | None = None,
) -> str:
    """Render a 5 × 5 danger heatmap PNG from a weakness profile.

    The grid colour is driven by per-zone danger_score (0=safe → 1=danger).
    Each cell is labelled "{dismissals}w/{total}". Zones with no data show
    as grey.

    Args:
        profile: Output of compute_weakness_profile() — dict with "zones"
            list (each zone has "line", "length", "danger_score",
            "dismissals", "total"), "batsman_name", "total_balls".
        output_path: Where to save the PNG.
        title: Optional chart title (defaults to batsman name).

    Returns:
        Absolute path to the saved PNG.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    n_len = len(_LENGTHS)
    n_lin = len(_LINES)
    grid = np.full((n_len, n_lin), np.nan)
    annotations = [["" for _ in range(n_lin)] for _ in range(n_len)]

    zone_index = {(z["length"], z["line"]): z for z in profile.get("zones", [])}
    for row, length in enumerate(_LENGTHS):
        for col, line in enumerate(_LINES):
            z = zone_index.get((length, line))
            if z:
                grid[row, col] = z["danger_score"]
                annotations[row][col] = f"{z['dismissals']}w/{z['total']}"

    fig, ax = plt.subplots(figsize=(8, 10))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    cmap = plt.cm.RdYlGn_r  # green=safe, red=danger
    for row in range(n_len):
        for col in range(n_lin):
            val = grid[row, col]
            if np.isnan(val):
                color = "#2a2a3e"
                text_color = "#555566"
                label = "–"
            else:
                color = cmap(val)
                text_color = "white" if val > 0.4 else "#222"
                label = annotations[row][col]

            rect = mpatches.FancyBboxPatch(
                (col + 0.05, n_len - row - 0.95),
                0.9, 0.9,
                boxstyle="round,pad=0.05",
                facecolor=color,
                edgecolor="#1a1a2e",
                linewidth=2,
            )
            ax.add_patch(rect)
            ax.text(
                col + 0.5, n_len - row - 0.5,
                label,
                ha="center", va="center",
                fontsize=9, color=text_color, fontweight="bold",
            )

    ax.set_xlim(0, n_lin)
    ax.set_ylim(0, n_len)
    ax.set_xticks([i + 0.5 for i in range(n_lin)])
    ax.set_xticklabels(_LINE_LABELS, color="white", fontsize=9)
    ax.set_yticks([n_len - i - 0.5 for i in range(n_len)])
    ax.set_yticklabels(_LENGTH_LABELS, color="white", fontsize=9)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.text(n_lin / 2, -0.6, "← Off side          Leg side →",
            ha="center", color="#aaaacc", fontsize=8)
    ax.text(-0.8, n_len / 2, "Short\n↑\nFull",
            ha="center", va="center", color="#aaaacc", fontsize=8, rotation=90)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Danger Score", color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    chart_title = title or profile.get("batsman_name") or "Batsman Weakness Map"
    total = profile.get("total_balls", 0)
    ax.set_title(
        f"{chart_title}\nWeakness Pitch Map  ({total} balls)",
        color="white", fontsize=13, fontweight="bold", pad=16,
    )
    fig.text(
        0.5, 0.02,
        "Cell label = dismissals / total balls  |  Grey = insufficient data",
        ha="center", color="#888899", fontsize=7,
    )

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return str(out.resolve())


# ── Wagon wheel config ───────────────────────────────────────────────

# Angles in DEGREES for a RHB (batter facing 0° = up toward bowler).
# Standard cricket field: looking down on the ground with bowler at TOP.
# Off side = batter's RIGHT (clockwise from straight).
# Leg side = batter's LEFT (anticlockwise from straight).
#
# Angles measured clockwise from straight (12 o'clock).
_DIRECTION_ANGLE_RHB = {
    "straight":         0,
    "long_off":         30,
    "mid_off":          50,
    "deep_cover":       70,
    "cover":            85,
    "deep_point":       100,
    "point":            110,
    "deep_third":       135,
    "third_man":        150,
    "behind_wicket":    180,
    "deep_fine_leg":    210,
    "fine_leg":         225,
    "deep_square_leg":  250,
    "square_leg":       265,
    "deep_mid_wicket":  290,
    "mid_wicket":       305,
    "mid_on":           320,
    "long_on":          340,
}


def render_wagon_wheel(
    direction_metric: dict,
    handedness: str = "right_handed",
    title: str = "",
    subtitle: str = "",
    output_path: str = "data/heatmaps/wagon.png",
    metric_label: str = "runs",
) -> str:
    """Polar bar chart of cricket field directions.

    Args:
        direction_metric: dict keyed by shot_direction enum string →
                          int/float metric (typically runs scored).
        handedness: "right_handed" or "left_handed". LHB mirrors the
                    leg/off side automatically.
        title: chart title (player name).
        subtitle: second-line subtitle.
        output_path: where to save PNG.
        metric_label: label for the value (e.g. "runs", "balls").

    Returns:
        Absolute path to saved PNG.
    """
    import math

    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#0d1b2a")

    # In matplotlib polar, 0 rad is at 3 o'clock and angles go counter-clockwise.
    # We want 0° at 12 o'clock and clockwise. Use set_theta_zero_location +
    # set_theta_direction.
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)  # clockwise

    angles_deg = list(_DIRECTION_ANGLE_RHB.values())
    directions = list(_DIRECTION_ANGLE_RHB.keys())

    # Mirror for LHB: off becomes leg and vice-versa.
    if handedness == "left_handed":
        angles_deg = [(360 - a) % 360 for a in angles_deg]

    values = np.array([direction_metric.get(d, 0) for d in directions], dtype=float)
    angles_rad = np.array([math.radians(a) for a in angles_deg])

    vmax = values.max() if values.max() > 0 else 1
    cmap = plt.get_cmap("YlOrRd")
    colors = [cmap(v / vmax) if v > 0 else "#1f2540" for v in values]

    # Bar width per direction segment
    width = 2 * math.pi / 24

    bars = ax.bar(
        angles_rad, values,
        width=width,
        bottom=vmax * 0.15,  # ring centred on the batter
        color=colors,
        edgecolor="#1a1a2e",
        linewidth=1.5,
        align="center",
    )

    # Annotate each non-zero direction
    for ang_rad, val, d in zip(angles_rad, values, directions):
        if val == 0:
            continue
        # Place label slightly outside the bar
        label_r = vmax * 0.15 + val + vmax * 0.07
        ax.text(
            ang_rad, label_r,
            f"{int(val)}",
            ha="center", va="center",
            color="white", fontsize=8, fontweight="bold",
        )

    # Hide radial / angular grid clutter
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines["polar"].set_visible(False)

    # Side labels: where Off and Leg sides are
    off_label, leg_label = ("OFF →", "← LEG") if handedness == "right_handed" else ("← OFF", "LEG →")
    ax.text(math.pi / 2, vmax * 1.45, off_label, ha="center", color="#88aaff", fontsize=10, fontweight="bold")
    ax.text(3 * math.pi / 2, vmax * 1.45, leg_label, ha="center", color="#ffaa88", fontsize=10, fontweight="bold")
    ax.text(0, vmax * 1.55, "STRAIGHT (bowler)", ha="center", color="#aaaacc", fontsize=8)
    ax.text(math.pi, vmax * 1.55, "BEHIND (keeper)", ha="center", color="#aaaacc", fontsize=8)

    # Center marker (batter position)
    ax.scatter([0], [0], color="#ffd166", s=80, zorder=10, marker="o")

    total = int(values.sum())
    full_title = f"{title}\n{subtitle}" if subtitle else title
    fig.suptitle(
        f"{full_title}    (total: {total} {metric_label}, {handedness.replace('_', '-')})",
        color="white", fontsize=13, fontweight="bold",
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return str(out.resolve())
