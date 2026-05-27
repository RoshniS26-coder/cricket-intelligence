// ── Match ─────────────────────────────────────────────────────────────────────

export interface Match {
  match_id: string
  format: string
  team_a: string
  team_b: string
  venue: string | null
  date: string | null
}

export interface MatchMeta {
  match_id: string
  date: string | null
  year: string | null
  venue: string | null
  team_a: string | null
  team_b: string | null
  format: string
  day_or_night: string
  balls_faced: number
  runs_scored: number
  dismissed: boolean
  dismissal_type: string | null
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export interface BattingStats {
  balls: number
  runs: number
  strike_rate: number
  dismissals: number
  fours: number
  sixes: number
  dot_balls: number
  dot_pct: number
}

export interface BowlingStats {
  balls: number
  runs_conceded: number
  wickets: number
  economy: number
  dot_balls: number
  dot_pct: number
  avg: number | null
}

export interface PhaseStats {
  powerplay?: BattingStats | BowlingStats
  middle?: BattingStats | BowlingStats
  death?: BattingStats | BowlingStats
}

// ── Weakness ──────────────────────────────────────────────────────────────────

export interface Zone {
  line: string
  length: string
  total: number
  dismissals: number
  false_shots: number
  boundaries: number
  runs: number
  avg_runs: number
  dismissal_rate: number
  false_shot_rate: number
  danger_score: number
  strength_score: number
}

export interface WeaknessProfile {
  batsman_name: string
  total_balls: number
  zones: Zone[]
  strengths: Zone[]
  top_weakness: Zone | null
  top_strength: Zone | null
  by_bowler_type: Record<string, Zone>
  by_variation: Record<string, Zone>
  by_swing: Record<string, Zone>
  by_spin: Record<string, Zone>
}

// ── Dismissals ────────────────────────────────────────────────────────────────

export interface DismissalProfile {
  total_dismissals: number
  by_type: Record<string, number>
  by_bowler_type: Record<string, number>
  by_length: Record<string, number>
  by_line: Record<string, number>
}

// ── Narrative ─────────────────────────────────────────────────────────────────

export interface Narrative {
  summary_en: string
  summary_hi: string
  strengths_en: string
  strengths_hi: string
  bowling_plan_en: string
  bowling_plan_hi: string
  batting_advice_en: string
  batting_advice_hi: string
}

export interface NarrativeMeta {
  cached: boolean
  generated_at: string | null
  model_used: string
  based_on_balls: number
  based_on_matches: number
  matches: MatchMeta[]
}

// ── Player profiles ───────────────────────────────────────────────────────────

export interface BattingProfile {
  name: string
  handedness: string
  matches_played: number
  overall: BattingStats
  by_phase: PhaseStats
  shot_distribution: Record<string, number>
  wagon_wheel: Record<string, number>
  dismissals: DismissalProfile
  weakness_profile: WeaknessProfile
  pitch_heatmap_counts: Record<string, number>
  narrative: Narrative | null
  narrative_meta: NarrativeMeta | null
}

export interface BowlingProfile {
  name: string
  matches: number
  overall: BowlingStats
  by_phase: PhaseStats
  line_length_map: Record<string, number>
  by_variation: Record<string, BowlingStats>
  by_line: Record<string, BowlingStats>
  by_length: Record<string, BowlingStats>
  wicket_delivery_profile: {
    total_wickets: number
    by_length: Record<string, number>
    by_line: Record<string, number>
    by_variation: Record<string, number>
  }
}

export interface PlayerListItem {
  name: string
  balls_faced: number
  balls_bowled: number
}

// ── Matchup ───────────────────────────────────────────────────────────────────

export interface MatchupBall {
  match_id: string
  over: number
  ball: number
  line: string
  length: string
  variation: string
  outcome: string
  runs: number
  shot_type: string
  contact_quality: string
  description: string
}

export interface Matchup {
  bowler: string
  batsman: string
  matches: number
  balls: number
  runs: number
  wickets: number
  dot_balls: number
  strike_rate: number
  economy: number
  dismissal_rate: number
  shot_distribution: Record<string, number>
  pitch_heatmap: Record<string, number>
  weakness_zones: Zone[]
  raw_balls: MatchupBall[]
}

// ── Team weaknesses ───────────────────────────────────────────────────────────

export interface PlayerWeaknessSummary {
  player: string
  balls_faced: number
  top_weakness: Zone | null
  danger_zones: Zone[]
}

export interface TeamWeaknesses {
  team: string
  match_id: string | null
  players_analysed: number
  profiles: PlayerWeaknessSummary[]
}

// ── Player comparison ─────────────────────────────────────────────────────────

export interface PlayerComparisonSide {
  name: string
  matches: number
  overall: BattingStats | BowlingStats
  by_phase: PhaseStats
  top_weakness?: Zone | null
  top_strength?: Zone | null
  dismissals?: DismissalProfile
  wagon_wheel?: Record<string, number>
  wicket_profile?: {
    total_wickets: number
    by_length: Record<string, number>
    by_line: Record<string, number>
    by_variation: Record<string, number>
  }
}

export interface PlayerComparison {
  role: string
  player_a: PlayerComparisonSide
  player_b: PlayerComparisonSide
}

// ── Series ────────────────────────────────────────────────────────────────────

export interface SeriesSummary {
  matches: Match[]
  total_matches: number
}

// ── AI Coach ──────────────────────────────────────────────────────────────────

export interface CorpusKey {
  key: string
  shot_type: string
  player: string
  language: string
  confidence: number | null
  n_drills: number
  n_cues: number
  n_mistakes: number
}

export interface ReferenceClip {
  key: string
  player: string
  shot_type: string
  handedness: string
  clip_path: string
  quality_rating: string
}

export interface Deviation {
  aspect: string
  description: string
  severity: 'low' | 'medium' | 'high'
  drill_suggestion?: string
}

export interface CritiqueResult {
  identified_shot_type: string
  overall_quality_rating: 'close_to_ideal' | 'needs_minor_work' | 'needs_major_work'
  deviations: Deviation[]
  drill_recommendations: string[]
  encouragement: string
}

export interface CritiqueResponse {
  player_name: string
  shot_type: string
  mode: string
  model_used: string
  critique: CritiqueResult
}

export interface SessionCatalogResponse {
  shot_counts: Record<string, number>
  contact_counts: Record<string, number>
  total_balls: number
}

export interface BriefingListItem {
  id: string
  filename: string
  size_kb: number
  created_at: number
}

// ── Ball review ───────────────────────────────────────────────────────────────

export interface BallUpdate {
  line?: string
  length?: string
  shot_type?: string
  outcome?: string
  reviewed_by?: string
}

// ── Insights ──────────────────────────────────────────────────────────────────

export interface DangerZoneInsight {
  line: string
  length: string
  dismissals: number
  total: number
  false_shots: number
  danger_score: number
  top_batsmen: string[]
}

export interface WicketZoneInsight {
  line: string
  length: string
  wickets: number
  total: number
  dismissal_rate: number
}

export interface SpinVsPaceItem {
  player: string
  pace_balls: number
  spin_balls: number
  pace_false_shot_rate: number
  spin_false_shot_rate: number
  weaker_vs: string
}

export interface PhaseVulnerabilityItem {
  player: string
  powerplay_sr: number
  middle_sr: number
  death_sr: number
  weakest_phase: string
  strongest_phase: string
  pp_balls: number
  md_balls: number
  dt_balls: number
}

export interface LegSideItem {
  player: string
  leg_pct: number
  off_pct: number
  total_shots: number
}

export interface BowlerVariationItem {
  bowler: string
  variation: string
  balls: number
  wickets: number
  false_shots: number
}

export interface BowlerPhaseEconomyItem {
  bowler: string
  powerplay: number | null
  middle: number | null
  death: number | null
  pp_balls: number
  md_balls: number
  dt_balls: number
}

export interface AnchorStrokemakerItem {
  player: string
  balls: number
  runs: number
  sr: number
  role: string
  avg_sr: number
}

export interface InsightsData {
  top_danger_zone: DangerZoneInsight | null
  most_wicket_zone: WicketZoneInsight | null
  spin_vs_pace: SpinVsPaceItem[]
  phase_vulnerability: PhaseVulnerabilityItem[]
  leg_side_reliant: LegSideItem[]
  bowler_best_variation: BowlerVariationItem[]
  bowler_phase_economy: BowlerPhaseEconomyItem[]
  anchors_vs_strokemakers: AnchorStrokemakerItem[]
  shot_zone_map: ShotZoneItem[]
  shot_false_shot_rate: ShotFalseShotItem[]
  top_shot_per_zone: TopShotZoneItem[]
  dismissal_shot_type: DismissalShotItem[]
}

export interface ShotZoneItem {
  line: string
  length: string
  top_shot: string
  shot_balls: number
  shot_pct: number
  wickets: number
  false_shots: number
  avg_runs: number
  zone_total: number
}

export interface ShotFalseShotItem {
  shot_type: string
  balls: number
  false_shot_rate: number
  dismissal_rate: number
  avg_runs: number
  wickets: number
}

export interface TopShotZoneItem {
  line: string
  length: string
  best_shot: string
  avg_runs: number
  balls: number
}

export interface DismissalShotItem {
  shot_type: string
  wickets: number
  balls: number
  dismissal_rate: number
}
