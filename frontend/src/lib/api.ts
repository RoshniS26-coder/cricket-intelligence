import axios from 'axios'
import type {
  Match, SeriesSummary, PlayerListItem,
  BattingProfile, BowlingProfile, Matchup,
  TeamWeaknesses, PlayerComparison,
  CorpusKey, ReferenceClip, CritiqueResponse,
  SessionCatalogResponse, BriefingListItem,
  InsightsData, BallUpdate,
} from './types'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 300000, // 5 min for long Gemini calls
})

// ── Matches ───────────────────────────────────────────────────────────────────

export const getMatches = () =>
  api.get<Match[]>('/matches').then(r => r.data)

export const getMatch = (matchId: string) =>
  api.get<Match>(`/matches/${matchId}`).then(r => r.data)

export const getSeriesSummary = (teamA?: string, teamB?: string) =>
  api.get<SeriesSummary>('/series/summary', { params: { team_a: teamA, team_b: teamB } }).then(r => r.data)

// ── Players ───────────────────────────────────────────────────────────────────

export const getPlayers = (role?: 'batsman' | 'bowler' | 'all') =>
  api.get<PlayerListItem[]>('/players', { params: { role } }).then(r => r.data)

export const getBattingProfile = (name: string, options?: {
  matchId?: string
  minConfidence?: number
  narrative?: boolean
}) =>
  api.get<BattingProfile>(`/players/${encodeURIComponent(name)}/batting`, {
    params: {
      match_id: options?.matchId,
      min_confidence: options?.minConfidence,
      narrative: options?.narrative,
    },
  }).then(r => r.data)

export const getBowlingProfile = (name: string, matchId?: string) =>
  api.get<BowlingProfile>(`/players/${encodeURIComponent(name)}/bowling`, {
    params: { match_id: matchId },
  }).then(r => r.data)

export const getWagonWheel = (name: string, matchId?: string) =>
  api.get(`/players/${encodeURIComponent(name)}/wagon-wheel`, {
    params: { match_id: matchId },
  }).then(r => r.data)

export const getPhaseBreakdown = (name: string, matchId?: string) =>
  api.get(`/players/${encodeURIComponent(name)}/phases`, {
    params: { match_id: matchId },
  }).then(r => r.data)

export const comparePlayers = (playerA: string, playerB: string, role: 'batsman' | 'bowler' = 'batsman') =>
  api.get<PlayerComparison>('/players/compare', {
    params: { player_a: playerA, player_b: playerB, role },
  }).then(r => r.data)

// ── Matchup ───────────────────────────────────────────────────────────────────

export const getMatchup = (bowler: string, batsman: string, matchId?: string) =>
  api.get<Matchup>('/matchup', {
    params: { bowler, batsman, match_id: matchId },
  }).then(r => r.data)

// ── Team weaknesses ───────────────────────────────────────────────────────────

export const getTeamWeaknesses = (teamName: string, matchId?: string, topN?: number) =>
  api.get<TeamWeaknesses>(`/team/${encodeURIComponent(teamName)}/weaknesses`, {
    params: { match_id: matchId, top_n: topN },
  }).then(r => r.data)

// ── Insights ──────────────────────────────────────────────────────────────────

export const getInsights = (matchId?: string, batsmanName?: string) =>
  api.get<InsightsData>('/insights', { params: { match_id: matchId, batsman_name: batsmanName || undefined } }).then(r => r.data)

// ── AI Coach ──────────────────────────────────────────────────────────────────

export const getCorpusKeys = (shotType?: string) =>
  api.get<CorpusKey[]>('/ai-coach/corpus/keys', { params: { shot_type: shotType } }).then(r => r.data)

export const getReferenceClips = (shotType?: string) =>
  api.get<ReferenceClip[]>('/ai-coach/corpus/references', { params: { shot_type: shotType } }).then(r => r.data)

export const runSessionCatalog = (formData: FormData) =>
  api.post<SessionCatalogResponse>('/ai-coach/session-catalog', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)

export const critiqueClip = (formData: FormData) =>
  api.post<CritiqueResponse>('/ai-coach/critique', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)

export const critiqueSession = (formData: FormData) =>
  api.post('/ai-coach/critique-session', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
  }).then(r => r.data)

export const generateBriefing = (formData: FormData) =>
  api.post('/ai-coach/briefing', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
  }).then(r => r.data)

export const getBriefings = () =>
  api.get<BriefingListItem[]>('/ai-coach/briefings').then(r => r.data)

export const downloadBriefing = (id: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/ai-coach/briefings/${id}/download`

// ── Ball review ───────────────────────────────────────────────────────────────

export const reviewBall = (ballId: string, update: BallUpdate) =>
  api.put(`/balls/${encodeURIComponent(ballId)}/review`, update).then(r => r.data)
