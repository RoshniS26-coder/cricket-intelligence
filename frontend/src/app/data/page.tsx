"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getMatches, reviewBall } from "@/lib/api"
import { Download, Database, CheckCircle, ChevronDown, ChevronUp } from "lucide-react"

interface BallRow {
  ball_id: string; over: number; ball: number
  bowler_name: string; batsman_name: string
  bowler_type: string; line: string; length: string
  shot_type: string; outcome: string; runs: number
  confidence_avg: number; is_reviewed: boolean; raw_description: string
}

async function fetchBalls(matchId: string): Promise<BallRow[]> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/balls?match_id=${matchId}`)
  return res.json()
}

function toCSV(rows: BallRow[]): string {
  const cols: (keyof BallRow)[] = [
    "ball_id", "over", "ball", "bowler_name", "batsman_name",
    "bowler_type", "line", "length", "shot_type", "outcome", "runs",
    "confidence_avg", "is_reviewed", "raw_description",
  ]
  const escape = (v: unknown) => {
    const s = String(v ?? "")
    return s.includes(",") || s.includes('"') || s.includes("\n")
      ? `"${s.replace(/"/g, '""')}"`
      : s
  }
  return `${cols.join(",")}\n${rows.map(r => cols.map(c => escape(r[c])).join(",")).join("\n")}`
}

const LINE_OPTS = ["outside_off", "off_stump", "middle", "leg", "outside_leg", "unknown"]
const LENGTH_OPTS = ["yorker", "full", "good", "short_of_length", "short", "unknown"]
const SHOT_OPTS = [
  "drive", "cut", "pull", "hook", "defend", "sweep", "reverse_sweep",
  "glance", "flick", "lofted", "leave", "cover_drive", "straight_drive",
  "on_drive", "off_drive", "square_drive", "square_cut", "late_cut",
  "upper_cut", "front_foot_defence", "back_foot_defence", "slog_sweep",
  "paddle_sweep", "leg_glance", "helicopter", "scoop", "unknown",
]
const OUTCOME_OPTS = ["0", "1", "2", "3", "4", "6", "wicket", "wide", "no_ball", "bye", "leg_bye"]

function fmt(v: string) { return v.replace(/_/g, " ") }

function ReviewPanel({
  ball,
  onSaved,
  onClose,
}: {
  ball: BallRow
  onSaved: (updated: BallRow) => void
  onClose: () => void
}) {
  const [line, setLine] = useState(ball.line)
  const [length, setLength] = useState(ball.length)
  const [shotType, setShotType] = useState(ball.shot_type)
  const [outcome, setOutcome] = useState(ball.outcome)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setSaving(true)
    setError(null)
    try {
      await reviewBall(ball.ball_id, { line, length, shot_type: shotType, outcome })
      onSaved({ ...ball, line, length, shot_type: shotType, outcome, is_reviewed: true })
    } catch {
      setError("Save failed — is the API running?")
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className="bg-[var(--bg-card-solid)]">
      <td colSpan={12} className="px-4 py-3">
        <div className="space-y-3">
          <p className="text-xs text-[var(--text-muted)] leading-relaxed italic">
            &ldquo;{ball.raw_description}&rdquo;
          </p>
          <div className="flex flex-wrap gap-3 items-end">
            {([
              ["Line", line, setLine, LINE_OPTS],
              ["Length", length, setLength, LENGTH_OPTS],
              ["Shot", shotType, setShotType, SHOT_OPTS],
              ["Outcome", outcome, setOutcome, OUTCOME_OPTS],
            ] as [string, string, (v: string) => void, string[]][]).map(([label, val, setter, opts]) => (
              <div key={label}>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wide mb-0.5">{label}</label>
                <select
                  value={val}
                  onChange={e => setter(e.target.value)}
                  className="themed-input rounded px-2 py-1 text-xs capitalize"
                >
                  {opts.map(o => <option key={o} value={o}>{fmt(o)}</option>)}
                </select>
              </div>
            ))}
            <button
              onClick={save}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white text-xs rounded transition-colors"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              {saving ? "Saving…" : "Mark Reviewed"}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              Cancel
            </button>
            {error && <span className="text-xs text-red-400">{error}</span>}
          </div>
        </div>
      </td>
    </tr>
  )
}

export default function DataPage() {
  const [selectedMatch, setSelectedMatch] = useState<string>("")
  const [balls, setBalls] = useState<BallRow[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedBallId, setExpandedBallId] = useState<string | null>(null)

  const { data: matches = [] } = useQuery({ queryKey: ["matches"], queryFn: () => getMatches() })

  async function load() {
    if (!selectedMatch) return
    setLoading(true)
    setBalls(null)
    setExpandedBallId(null)
    const rows = await fetchBalls(selectedMatch)
    setBalls(rows)
    setLoading(false)
  }

  function downloadCSV() {
    if (!balls) return
    const csv = toCSV(balls)
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `match_${selectedMatch}_balls.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleSaved(updated: BallRow) {
    setBalls(prev => prev?.map(b => b.ball_id === updated.ball_id ? updated : b) ?? prev)
    setExpandedBallId(null)
  }

  const reviewed = balls?.filter(b => b.is_reviewed).length ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Database className="w-6 h-6 text-blue-500" />
          Full Dataset
        </h1>
        <p className="text-[var(--text-secondary)] mt-1 text-sm">Browse, review, and export ball-by-ball records</p>
      </div>

      <div className="flex items-end gap-3 flex-wrap">
        <div>
          <label className="block text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Match</label>
          <select
            value={selectedMatch}
            onChange={e => setSelectedMatch(e.target.value)}
            className="themed-input rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Select a match…</option>
            {matches.map(m => (
              <option key={m.match_id} value={m.match_id}>
                {m.team_a} vs {m.team_b} — {m.venue ?? m.match_id}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={load}
          disabled={!selectedMatch || loading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:text-blue-700 text-white text-sm rounded-lg transition-colors"
        >
          {loading ? "Loading…" : "Load"}
        </button>
        {balls && (
          <button
            onClick={downloadCSV}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--bg-muted)] hover:bg-[var(--border)] text-[var(--text-primary)] text-sm rounded-lg transition-colors border border-[var(--border)]"
          >
            <Download className="w-4 h-4" />
            Export CSV ({balls.length} rows)
          </button>
        )}
      </div>

      {balls && (
        <div>
          <p className="text-[var(--text-muted)] text-xs mb-2">
            {balls.length} balls · {reviewed}/{balls.length} reviewed · click a row to review
          </p>
          <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
            <table className="text-xs w-full">
              <thead>
                <tr className="bg-[var(--bg-card-solid)] border-b border-[var(--border)] text-[var(--text-muted)] uppercase">
                  {["Ball ID", "Ov", "B", "Bowler", "Batsman", "Line", "Length", "Shot", "Outcome", "Runs", "Conf", "Rev", ""].map(h => (
                    <th key={h} className="px-3 py-2 text-left whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {balls.map(b => {
                  const isOpen = expandedBallId === b.ball_id
                  return [
                    <tr
                      key={b.ball_id}
                      onClick={() => setExpandedBallId(isOpen ? null : b.ball_id)}
                      className={`border-b border-[var(--border)] last:border-0 table-row-hover cursor-pointer ${isOpen ? "bg-[var(--bg-card-solid)]" : ""}`}
                    >
                      <td className="px-3 py-1.5 font-mono text-[var(--text-muted)]">{b.ball_id}</td>
                      <td className="px-3 py-1.5 text-[var(--text-secondary)]">{b.over}</td>
                      <td className="px-3 py-1.5 text-[var(--text-secondary)]">{b.ball}</td>
                      <td className="px-3 py-1.5 text-[var(--text-primary)]">{b.bowler_name}</td>
                      <td className="px-3 py-1.5 text-[var(--text-primary)]">{b.batsman_name}</td>
                      <td className="px-3 py-1.5 text-[var(--text-secondary)] capitalize">{fmt(b.line)}</td>
                      <td className="px-3 py-1.5 text-[var(--text-secondary)] capitalize">{fmt(b.length)}</td>
                      <td className="px-3 py-1.5 text-[var(--text-secondary)] capitalize">{fmt(b.shot_type)}</td>
                      <td className="px-3 py-1.5">
                        <span className={b.outcome === "wicket" ? "text-red-500 font-medium" : b.outcome === "4" || b.outcome === "6" ? "text-emerald-500" : "text-[var(--text-secondary)]"}>
                          {b.outcome}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-[var(--text-primary)] text-center">{b.runs}</td>
                      <td className="px-3 py-1.5 text-center">
                        <span className={b.confidence_avg >= 0.7 ? "text-emerald-500" : b.confidence_avg >= 0.4 ? "text-amber-500" : "text-red-500"}>
                          {(b.confidence_avg * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-center">
                        {b.is_reviewed
                          ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500 inline" />
                          : <span className="text-[var(--text-muted)]">—</span>}
                      </td>
                      <td className="px-3 py-1.5 text-[var(--text-muted)]">
                        {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </td>
                    </tr>,
                    isOpen && (
                      <ReviewPanel
                        key={`${b.ball_id}-review`}
                        ball={b}
                        onSaved={handleSaved}
                        onClose={() => setExpandedBallId(null)}
                      />
                    ),
                  ]
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
