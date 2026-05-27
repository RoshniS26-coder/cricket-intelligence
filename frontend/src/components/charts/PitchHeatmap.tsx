"use client"

import type { Zone } from "@/lib/types"

// Left → Right from bowler's POV: leg side on left, off side on right
const LINES = ["outside_leg", "leg", "middle", "off_stump", "outside_off"]
const LENGTHS = ["short", "short_of_length", "good", "full", "yorker"]

const LINE_LABELS: Record<string, string> = {
  outside_leg: "Outside\nLeg",
  leg: "Leg",
  middle: "Middle",
  off_stump: "Off\nStump",
  outside_off: "Outside\nOff",
}
const LENGTH_LABELS: Record<string, string> = {
  short: "Short",
  short_of_length: "Short of\nLength",
  good: "Good\nLength",
  full: "Full",
  yorker: "Yorker",
}

// T20-calibrated thresholds: dismissal_rate of 33% (2w/6) = orange, 50% = red
function dangerColor(score: number): string {
  if (score >= 0.50) return "#dc2626"  // red-600
  if (score >= 0.30) return "#ea580c"  // orange-600
  if (score >= 0.15) return "#ca8a04"  // yellow-600
  if (score >= 0.05) return "#16a34a"  // green-600
  return "#15803d"                      // green-700
}

// YlOrRd for frequency: matches Streamlit version
function freqColor(norm: number): string {
  if (norm >= 0.75) return "#b45309"   // amber-700
  if (norm >= 0.5)  return "#d97706"   // amber-600
  if (norm >= 0.25) return "#f59e0b"   // amber-500
  if (norm > 0)     return "#fde68a"   // amber-200
  return ""
}

interface PitchHeatmapProps {
  counts?: Record<string, number>   // "length|line" → count
  zones?: Zone[]                    // for danger mode
  mode?: "frequency" | "danger"
  title?: string
}

const CELL_W = 64
const CELL_H = 72
const ML = 80   // left margin for length labels
const MT = 32   // top margin
const MB = 56   // bottom margin for line labels + axis text
const MR = 16

const W = ML + CELL_W * 5 + MR
const H = MT + CELL_H * 5 + MB

export default function PitchHeatmap({ counts = {}, zones = [], mode = "frequency", title }: PitchHeatmapProps) {
  const maxCount = Math.max(...Object.values(counts), 1)
  const dangerLookup = new Map<string, Zone>()
  zones.forEach(z => dangerLookup.set(`${z.length}|${z.line}`, z))

  return (
    <div className="space-y-1">
      {title && <p className="text-xs text-gray-400 uppercase tracking-wide">{title}</p>}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}>
        {/* Background */}
        <rect width={W} height={H} fill="#0d1117" rx="10" />

        {/* Length labels (left) */}
        {LENGTHS.map((length, row) => {
          const cy = MT + row * CELL_H + CELL_H / 2
          const lines = LENGTH_LABELS[length].split("\n")
          return (
            <text key={length} x={ML - 8} y={cy} textAnchor="end" fontSize="10" fill="#9ca3af">
              {lines.length === 1 ? (
                <tspan dominantBaseline="middle">{lines[0]}</tspan>
              ) : (
                <>
                  <tspan x={ML - 8} dy="-6" dominantBaseline="middle">{lines[0]}</tspan>
                  <tspan x={ML - 8} dy="14" dominantBaseline="middle">{lines[1]}</tspan>
                </>
              )}
            </text>
          )
        })}

        {/* Cells */}
        {LENGTHS.map((length, row) =>
          LINES.map((line, col) => {
            const key = `${length}|${line}`
            const count = counts[key] ?? 0
            const zone = dangerLookup.get(key)
            const danger = zone?.danger_score ?? 0

            const x = ML + col * CELL_W + 3
            const y = MT + row * CELL_H + 3
            const cw = CELL_W - 6
            const ch = CELL_H - 6

            let fill = "#1c2333"
            if (mode === "danger" && zone) fill = dangerColor(danger)
            else if (mode === "frequency" && count > 0) fill = freqColor(count / maxCount) || "#2a2a3e"

            const isEmpty = mode === "danger" ? !zone : count === 0
            const mainLabel = mode === "danger"
              ? (zone ? `${zone.dismissals}w/${zone.total}` : "–")
              : (count > 0 ? String(count) : "–")
            const subLabel = mode === "danger" && zone
              ? danger.toFixed(2)
              : ""

            const textDark = mode === "danger" && danger >= 0.35 && danger < 0.55
            const textColor = isEmpty ? "#4b5563" : (textDark ? "#1f2937" : "white")

            return (
              <g key={key}>
                <rect
                  x={x} y={y} width={cw} height={ch}
                  rx="6" ry="6"
                  fill={fill}
                  stroke="#0d1117"
                  strokeWidth="2.5"
                />
                <text x={x + cw / 2} y={y + ch / 2 - (subLabel ? 6 : 0)}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize="11" fontWeight="bold" fill={textColor}
                >
                  {mainLabel}
                </text>
                {subLabel && (
                  <text x={x + cw / 2} y={y + ch / 2 + 10}
                    textAnchor="middle" dominantBaseline="middle"
                    fontSize="9" fill={textColor} opacity="0.85"
                  >
                    {subLabel}
                  </text>
                )}
              </g>
            )
          })
        )}

        {/* Line labels (bottom) */}
        {LINES.map((line, col) => {
          const cx = ML + col * CELL_W + CELL_W / 2
          const labelY = MT + 5 * CELL_H + 14
          const lines = LINE_LABELS[line].split("\n")
          return (
            <text key={line} x={cx} textAnchor="middle" fontSize="9.5" fill="#9ca3af">
              {lines.length === 1 ? (
                <tspan y={labelY + 5} dominantBaseline="middle">{lines[0]}</tspan>
              ) : (
                <>
                  <tspan x={cx} y={labelY}>{lines[0]}</tspan>
                  <tspan x={cx} dy="13">{lines[1]}</tspan>
                </>
              )}
            </text>
          )
        })}

        {/* Axis direction text */}
        <text x={ML + (CELL_W * 5) / 2} y={H - 6}
          textAnchor="middle" fontSize="9" fill="#6b7280">
          ← Leg side &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Off side →
        </text>
        <text x={10} y={MT + (CELL_H * 5) / 2}
          textAnchor="middle" fontSize="9" fill="#6b7280"
          transform={`rotate(-90, 10, ${MT + (CELL_H * 5) / 2})`}>
          Short ↑ Yorker
        </text>

        {/* Legend */}
        {mode === "danger" && (
          <g transform={`translate(${ML}, ${H - 22})`}>
            {["#15803d", "#ca8a04", "#dc2626"].map((c, i) => (
              <rect key={i} x={i * 30} y={0} width={26} height={10} rx="2" fill={c} />
            ))}
            <text x={0} y={22} fontSize="8" fill="#6b7280">Safe</text>
            <text x={55} y={22} fontSize="8" fill="#6b7280">Danger</text>
            <text x={4} y={14} fontSize="7" fill="#9ca3af">0</text>
            <text x={34} y={14} fontSize="7" fill="#9ca3af">0.3</text>
            <text x={64} y={14} fontSize="7" fill="#9ca3af">0.5+</text>
          </g>
        )}
      </svg>

      {mode === "danger" && (
        <p className="text-xs text-gray-600">Cell label = dismissals / total balls · colour = danger score</p>
      )}
    </div>
  )
}
