"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getTeamWeaknesses, getMatchup, getPlayers } from "@/lib/api"
import PlayerDropdown from "@/components/shared/PlayerDropdown"
import PitchHeatmap from "@/components/charts/PitchHeatmap"
import StatCard from "@/components/shared/StatCard"
import { Target, Crosshair } from "lucide-react"

const TEAMS = ["India", "England"]

function fmt(v: string) { return v.replace(/_/g, " ") }

export default function PrepPage() {
  const [team, setTeam] = useState<string>(TEAMS[0])
  const [bowler, setBowler] = useState("")
  const [batsman, setBatsman] = useState("")

  const { data: players = [] } = useQuery({ queryKey: ["players"], queryFn: () => getPlayers() })

  const { data: weaknesses, isLoading: loadingWeaknesses } = useQuery({
    queryKey: ["team-weaknesses", team],
    queryFn: () => getTeamWeaknesses(team, undefined, 100),
  })

  const { data: matchup, isLoading: loadingMatchup } = useQuery({
    queryKey: ["matchup", bowler, batsman],
    queryFn: () => getMatchup(bowler, batsman),
    enabled: !!(bowler && batsman),
  })

  return (
    <div className="space-y-6 fade-in-up">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Opposition Prep</h1>
        <p className="text-[var(--text-secondary)] mt-1 text-sm">Bowling plans and head-to-head matchup analysis</p>
      </div>

      {/* ── Head-to-Head Matchup (top) ───────────────────────────────── */}
      <div className="relative z-10 border border-[var(--border)] rounded-xl p-5 bg-[var(--bg-card)] backdrop-blur-sm">
        <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wide mb-4 flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-violet-500" />
          Head-to-Head Matchup
        </h2>

        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <PlayerDropdown
            players={players}
            value={bowler}
            onChange={setBowler}
            role="bowler"
            label="Bowler"
            placeholder="Select bowler…"
          />
          <PlayerDropdown
            players={players}
            value={batsman}
            onChange={setBatsman}
            role="batsman"
            label="Batsman"
            placeholder="Select batsman…"
          />
        </div>

        {(!bowler || !batsman) && (
          <p className="text-[var(--text-muted)] text-sm">Select a bowler and batsman to see their head-to-head record.</p>
        )}

        {loadingMatchup && <div className="h-32 rounded-lg shimmer" />}

        {matchup && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard label="Balls"          value={matchup.balls} />
              <StatCard label="Runs"           value={matchup.runs} />
              <StatCard label="Wickets"        value={matchup.wickets} accent={matchup.wickets > 0 ? "red" : undefined} />
              <StatCard label="Dot Balls"      value={matchup.dot_balls} />
              <StatCard label="Strike Rate"    value={matchup.strike_rate.toFixed(1)} />
              <StatCard label="Economy"        value={matchup.economy.toFixed(1)} />
              <StatCard label="Dismissal Rate" value={matchup.dismissal_rate.toFixed(2)} accent={matchup.dismissal_rate >= 0.15 ? "red" : undefined} />
            </div>

            {matchup.weakness_zones.length > 0 && (
              <div>
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-3">Danger Zones in This Matchup</p>
                <PitchHeatmap zones={matchup.weakness_zones} mode="danger" />
              </div>
            )}

            {matchup.raw_balls.length > 0 && (
              <div>
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-2">Ball-by-Ball</p>
                <div className="max-h-52 overflow-y-auto space-y-1">
                  {matchup.raw_balls.map((b, i) => (
                    <div
                      key={i}
                      className="text-xs bg-[var(--bg-muted)] rounded px-3 py-1.5 flex gap-3 border border-[var(--border)]"
                    >
                      <span className="font-mono text-[var(--text-muted)] shrink-0">{b.over}.{b.ball}</span>
                      <span className="text-[var(--text-secondary)] shrink-0">{fmt(b.line)} / {fmt(b.length)}</span>
                      <span className={`shrink-0 ${b.outcome === "wicket" ? "text-red-500 font-medium" : "text-[var(--text-primary)]"}`}>
                        {b.outcome}
                      </span>
                      <span className="text-[var(--text-muted)] flex-1 truncate">{b.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Team Batting Weaknesses (compact table) ──────────────────── */}
      <div className="relative z-0 border border-[var(--border)] rounded-xl bg-[var(--bg-card)] backdrop-blur-sm overflow-hidden">
        {/* Team toggle inside the section header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wide flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-500" />
            Batting Weaknesses
          </h2>
          <div className="flex gap-1.5">
            {TEAMS.map(t => (
              <button
                key={t}
                onClick={() => setTeam(t)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all duration-200 ${
                  team === t
                    ? "bg-gradient-to-r from-blue-600 to-violet-600 text-white"
                    : "bg-[var(--bg-muted)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {loadingWeaknesses ? (
          <div className="p-5 space-y-2">
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-8 rounded shimmer" />)}
          </div>
        ) : weaknesses?.profiles.length === 0 ? (
          <p className="px-5 py-4 text-[var(--text-muted)] text-sm">No weakness data for {team}.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[var(--text-muted)] uppercase border-b border-[var(--border)] bg-[var(--bg-muted)]">
                <th className="px-4 py-2.5 text-left font-medium">Player</th>
                <th className="px-4 py-2.5 text-center font-medium w-16">Balls</th>
                <th className="px-4 py-2.5 text-left font-medium">Top Weakness</th>
                <th className="px-4 py-2.5 text-center font-medium w-20">Danger</th>
                <th className="px-4 py-2.5 text-left font-medium">Exploit Zones</th>
              </tr>
            </thead>
            <tbody>
              {weaknesses?.profiles.map((p, idx) => (
                <tr
                  key={p.player}
                  className={`border-b border-[var(--border)] last:border-0 ${idx % 2 === 0 ? "bg-[var(--bg-card-solid)]" : "bg-transparent"}`}
                >
                  <td className="px-4 py-2.5 text-[var(--text-primary)] font-medium whitespace-nowrap">{p.player}</td>
                  <td className="px-4 py-2.5 text-center text-[var(--text-secondary)]">{p.balls_faced}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    {p.top_weakness ? (
                      <span className="text-red-400 font-medium">
                        {fmt(p.top_weakness.length)} / {fmt(p.top_weakness.line)}
                      </span>
                    ) : (
                      <span className="text-[var(--text-muted)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {p.top_weakness ? (
                      <span className={`font-mono font-semibold ${p.top_weakness.danger_score >= 0.6 ? "text-red-500" : p.top_weakness.danger_score >= 0.3 ? "text-amber-500" : "text-emerald-500"}`}>
                        {p.top_weakness.danger_score.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-[var(--text-muted)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {p.danger_zones.slice(0, 3).map((z, i) => (
                        <span
                          key={i}
                          className="text-[10px] bg-red-500/10 border border-red-500/20 text-red-400 px-1.5 py-0.5 rounded whitespace-nowrap"
                        >
                          {fmt(z.length)} × {fmt(z.line)}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
