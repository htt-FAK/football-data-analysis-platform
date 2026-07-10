export interface League {
  id: number;
  name: string;
  country?: string;
  logo_url?: string;
  type?: string;
  season?: string;
}

export interface Season {
  id: number;
  league_id: number;
  season: string;
  start_date?: string;
  end_date?: string;
  is_current: boolean;
}

export interface Team {
  id: number;
  name: string;
  full_name?: string;
  country?: string;
  logo_url?: string;
  founded?: number;
  venue?: string;
  coach?: string;
  league_id?: number;
}

export interface Player {
  id: number;
  name: string;
  full_name?: string;
  position?: string;
  jersey_number?: number;
  nationality?: string;
  birth_date?: string;
  height_cm?: number;
  weight_kg?: number;
  photo_url?: string;
  team_id?: number;
  team_name?: string;
  overall_rating?: number;
  group_name?: string;
  atk_score?: number;
  org_score?: number;
  def_score?: number;
  gk_score?: number;
  phy_score?: number;
  dis_score?: number;
  stats?: PlayerStat[];
}

export interface WorldCupPlayer {
  player_id: number;
  name: string;
  position?: string;
  team_id?: number;
  team_name?: string;
  group?: string;
  group_rank?: number;
  qualification_status?: string;
  photo_url?: string;
  nationality?: string;
  appearances?: number;
  goals?: number;
  assists?: number;
  minutes_played?: number;
  rating?: number;
  shots?: number;
  passes?: number;
  xg?: number;
  xa?: number;
  overall_rating?: number;
  atk_score?: number;
  org_score?: number;
  def_score?: number;
  gk_score?: number;
  phy_score?: number;
  dis_score?: number;
}

export interface PlayerStat {
  id?: number;
  player_id: number;
  season?: string;
  appearances?: number;
  goals?: number;
  assists?: number;
  yellow_cards?: number;
  red_cards?: number;
  minutes_played?: number;
  shots?: number;
  shots_on_target?: number;
  xg?: number;
  xa?: number;
  passes?: number;
  pass_accuracy?: number;
  tackles?: number;
  interceptions?: number;
  rating?: number;
  saves?: number;
  save_pct?: number;
  goals_conceded?: number;
  xga?: number;
  crosses_stopped?: number;
}

export interface Match {
  id: number;
  league_id?: number;
  league_name?: string;
  season?: string;
  season_id?: number;
  matchday?: number;
  stage?: string;
  group_name?: string;
  date_time?: string;
  match_date?: string;
  home_team_id: number;
  home_team_name: string;
  home_team_logo?: string;
  away_team_id: number;
  away_team_name: string;
  away_team_logo?: string;
  home_score?: number;
  away_score?: number;
  home_ht_score?: number;
  away_ht_score?: number;
  status?: string;
  minute?: number;
  venue?: string;
  referee?: string;
  attendance?: number;
  home_xg?: number;
  away_xg?: number;
}

export interface MatchEvent {
  id?: number;
  match_id: number;
  minute: number;
  team_id?: number;
  team_name?: string;
  player_id?: number;
  player_name?: string;
  event_type: string;
  detail?: string;
  assist_player_id?: number;
  assist_player_name?: string;
  derived?: boolean;
  source?: string | null;
}

export interface MatchXgTimelineSide {
  id?: number | null;
  name?: string | null;
  goals?: number | null;
  final_xg?: number | null;
  performance?: string | null;
}

export interface MatchXgTimelinePoint {
  minute: number;
  cumulative_xg: number;
  team_id?: number | null;
  team_name?: string | null;
  player_id?: number | null;
  player_name?: string | null;
  xg?: number | null;
  result?: string | null;
}

export interface MatchXgTimeline {
  match_id: number;
  home_team: MatchXgTimelineSide;
  away_team: MatchXgTimelineSide;
  timeline: {
    home: MatchXgTimelinePoint[];
    away: MatchXgTimelinePoint[];
  };
  available: boolean;
  shot_count: number;
  source?: string | null;
  coverage?: {
    total_rows?: number;
    timeline_ready_rows?: number;
    excluded_rows?: number;
  };
  note?: string | null;
}

export interface MatchImpactSummary {
  key_events_count: number;
  key_events: Array<
    MatchEvent & {
      type?: string;
      side?: string;
      impact_score?: number;
    }
  >;
  momentum_curve: Array<{
    minute: number;
    side?: string;
    event?: string;
    swing?: number;
    home_momentum?: number;
    away_momentum?: number;
    net_momentum?: number;
  }>;
  event_type_breakdown: Record<string, number>;
}

export interface MatchReport {
  match: {
    id: number;
    match_date?: string | null;
    status?: string | null;
    home_team: { id?: number | null; name?: string | null };
    away_team: { id?: number | null; name?: string | null };
    home_score?: number | null;
    away_score?: number | null;
    home_score_ht?: number | null;
    away_score_ht?: number | null;
    venue?: string | null;
    stage?: string | null;
    group?: string | null;
  };
  events: MatchEvent[];
  impact_summary: MatchImpactSummary;
  xg_timeline: MatchXgTimeline;
  shots: {
    match_id: number;
    home_team_id?: number | null;
    away_team_id?: number | null;
    total: number;
    available?: boolean;
    source?: string | null;
    note?: string | null;
    shots: Shot[];
  };
  data_availability?: Record<
    string,
    {
      available?: boolean;
      rows?: number;
      source?: string | null;
      note?: string | null;
    }
  >;
}

export interface StandingsEntry {
  id?: number;
  league_id?: number;
  team_id: number;
  team_name: string;
  team_logo?: string;
  position?: number;
  played?: number;
  wins?: number;
  draws?: number;
  losses?: number;
  goals_for?: number;
  goals_against?: number;
  goal_diff?: number;
  points?: number;
  form?: string;
  stage?: string;
  group_name?: string;
  qualification_status?: string;
}

export interface TeamStat {
  id?: number;
  team_id: number;
  team_name?: string;
  season?: string;
  matches_played?: number;
  wins?: number;
  draws?: number;
  losses?: number;
  goals_for?: number;
  goals_against?: number;
  xg?: number;
  xga?: number;
  xg_for?: number;
  xg_against?: number;
  possession?: number;
  shots?: number;
  shots_total?: number;
  shots_on_target?: number;
  shots_on_target_total?: number;
  passes?: number;
  passes_total?: number;
  pass_accuracy?: number;
  corners?: number;
  fouls?: number;
  yellow_cards?: number;
  red_cards?: number;
  clean_sheets?: number;
  attack_score?: number;
  defense_score?: number;
  overall_score?: number;
  attack_rating?: number;
  defense_rating?: number;
  overall_rating?: number;
  stats?: Record<string, unknown> | null;
}

export interface Shot {
  id?: number;
  match_id: number;
  team_id?: number;
  team_name?: string;
  player_id?: number;
  player_name?: string;
  minute: number;
  x: number;
  y: number;
  result: string;
  xg?: number;
  shot_type?: string;
  situation?: string;
}

export interface RadarData {
  dimensions: string[];
  values: number[];
  recommended_visualization: string;
  completeness: string;
  median_values?: number[];
  position?: string;
}

// ── Raw API 响应类型 (Track F: 类型安全) ─────────────────────────
export type RawPlayer = Partial<Player> & {
  player_id?: number;
  shirt_number?: number;
  height?: number;
  weight?: number;
  rating?: number;
  group?: string;
};

export type RawPlayerStat = Partial<PlayerStat> & {
  save_rate?: number;
  xcs?: number;
  sweeper_actions?: number;
};

export type RawMatch = Partial<Match> & { group?: string };

export interface RawRadarData {
  dimensions?: string[];
  values?: number[];
  recommended_visualization?: string;
  completeness?: string | { label?: string; recommended_visualization?: string };
  median_values?: number[];
  position?: string;
  mode?: string;
}

export type RawLeaderboardRow = Partial<Player> & Partial<PlayerStat> & {
  player_id?: number;
  shirt_number?: number;
  height?: number;
  weight?: number;
  group?: string;
  [key: string]: unknown;
};

export type LeaderboardResponse = RawLeaderboardRow[];

export interface PlayerCompareResponse {
  player_a?: RawPlayer;
  player_b?: RawPlayer;
  season_stats?: {
    player_a?: Partial<PlayerStat>;
    player_b?: Partial<PlayerStat>;
  };
  radar?: {
    player_a?: RadarData;
    player_b?: RadarData;
  };
  comparison_summary?: Record<string, { a: number; b: number; better: string }>;
  recommended_visualization?: string;
  completeness?: string | Record<string, unknown>;
}

export interface PositionStatsResponse {
  position?: string;
  total_players?: number;
  count?: number;
  total?: number;
  distributions?: Record<string, {
    median?: number;
    q1?: number;
    q3?: number;
    min?: number;
    max?: number;
  }>;
  [key: string]: unknown;
}

export interface PositionStats {
  position: string;
  total_players: number;
  count?: number;
  dimensions: string[];
  median: number[];
  q1: number[];
  q3: number[];
  min: number[];
  max: number[];
}

export interface PlayerCompareResult {
  player_a: Player;
  player_b: Player;
  stats_a: PlayerStat;
  stats_b: PlayerStat;
  radar_a?: RadarData;
  radar_b?: RadarData;
  comparison_summary: Record<string, { a: number; b: number; better: string }>;
  recommended_visualization: string;
  completeness: string | Record<string, unknown>;
}

export interface CrawlLog {
  id: number;
  source_id?: string;
  source_name?: string;
  target?: string;
  started_at?: string;
  finished_at?: string;
  duration_seconds?: number;
  items_fetched?: number;
  items_updated?: number;
  items_failed?: number;
  status?: string;
  error_message?: string;
}

export interface DataSource {
  id: string;
  name: string;
  source_type?: string;
  priority?: number;
  enabled?: boolean;
  health_status?: string;
  last_crawl_at?: string;
  last_log_summary?: string;
}

export interface WorldCupSummary {
  league_id: number;
  league_name: string;
  season: string;
  group_count: number;
  group_names?: string[];
  match_count: number;
  finished_match_count: number;
  team_count: number;
  player_count: number;
  active_player_count: number;
  rated_player_count: number;
  qualified_team_count: number;
  total_goals?: number;
  avg_goals_per_match?: number;
  top_scorer_name?: string;
  top_scorer_goals?: number;
}

export interface WorldCupTeam {
  team_id: number;
  name: string;
  group: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
  rank: number;
}

export interface WorldCupPlayer {
  player_id: number;
  name: string;
  position?: string;
  team_name?: string;
  group?: string;
  goals?: number;
  assists?: number;
  rating?: number;
  matches_played?: number;
  minutes_played?: number;
  team_id?: number;
  photo_url?: string;
  appearances?: number;
  shots?: number;
  passes?: number;
  xg?: number;
  xa?: number;
  overall_rating?: number;
  atk_score?: number;
  org_score?: number;
  def_score?: number;
  gk_score?: number;
  phy_score?: number;
  dis_score?: number;
}

export interface WorldCupLeaderItem {
  player_id: number;
  name: string;
  team_name?: string;
  value: number;
  type: string;
  position?: string;
  photo_url?: string;
  appearances?: number;
  matches_played?: number;
}

export interface WorldCupLeaders {
  top_scorers: WorldCupLeaderItem[];
  top_assists: WorldCupLeaderItem[];
  top_ratings: WorldCupLeaderItem[];
}

export interface WorldCupMatch {
  match_id: number;
  home_team: string;
  away_team: string;
  home_score?: number;
  away_score?: number;
  stage?: string;
  match_date?: string;
  status?: string;
  group_name?: string;
  home_team_id?: number;
  away_team_id?: number;
  venue?: string;
}

export interface WorldCupCoverageItem {
  module: string;
  status: "ready" | "partial" | "missing";
  detail?: string;
}

export interface WorldCupCoverage {
  season: string;
  coverage: WorldCupCoverageItem[];
}

export interface WorldCupUpcomingMatch {
  match_id: number;
  match_date?: string | null;
  status?: string;
  stage?: string | null;
  group?: string | null;
  home_team_id?: number | null;
  home_team_name?: string | null;
  away_team_id?: number | null;
  away_team_name?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  venue?: string | null;
  is_ready_for_prediction: boolean;
}

export interface WorldCupUpcomingResponse {
  season: string;
  matches: WorldCupUpcomingMatch[];
}

export interface LiveStatus {
  status: string;
  live_matches: number;
  mode: string;
}

export interface LeagueTrendPoint {
  match_id: number;
  matchday?: number | null;
  match_date?: string | null;
  points: number;
}

export interface LeagueTrendEntry {
  team_id: number;
  team_name: string;
  current_points: number;
  position?: number | null;
  form?: string | null;
  played?: number | null;
  won?: number | null;
  drawn?: number | null;
  lost?: number | null;
  goals_for?: number | null;
  goals_against?: number | null;
  goal_diff?: number | null;
  group?: string | null;
  points_timeline: LeagueTrendPoint[];
}

export interface LeagueTrendsResponse {
  league_id: number;
  season: string;
  note?: string;
  trends: LeagueTrendEntry[];
}

// ── AI 预测 ──
export interface PredictionSearchResult {
  title: string;
  url: string;
  snippet: string;
}

/** 预测命中等级：score_hit=命中比分 / result_hit=命中胜负 / miss=未中 */
export type PredictionAccuracyLevel = "score_hit" | "result_hit" | "miss";

/** 列表徽章用的精简命中摘要 */
export interface PredictionAccuracySummary {
  level: PredictionAccuracyLevel;
  label: string;
}

/** 详情页用的完整命中信息 */
export interface PredictionAccuracyDetail extends PredictionAccuracySummary {
  predicted_home: number;
  predicted_away: number;
  real_home: number;
  real_away: number;
  predicted_outcome: "home_win" | "draw" | "away_win";
  real_outcome: "home_win" | "draw" | "away_win";
}

export interface PredictionRound {
  round: number;
  focus: string;
  model: string;
  status: "completed" | "failed" | "no_json" | "partial";
  reasoning: string;
  search_results: PredictionSearchResult[];
  conclusion: Record<string, unknown>;
  tokens: number;
  cost_ms: number;
  error?: string | null;
  // 顶层结论字段（可能存在）
  home_win_prob?: number;
  draw_prob?: number;
  away_win_prob?: number;
  predicted_home_score?: number;
  predicted_away_score?: number;
  conservative_verdict?: string;
  aggressive_verdict?: string;
  confidence?: number;
  key_reasons?: string[];
  thinking?: string;
}

export interface MatchPredictionResponse {
  id: number;
  match_id: number;
  status: string;
  home_team: {
    id: number | null;
    name: string | null;
    country: string | null;
  };
  away_team: {
    id: number | null;
    name: string | null;
    country: string | null;
  };
  kickoff: string | null;
  stage: string | null;
  group: string | null;
  venue: string | null;
  home_win_prob: number | null;
  draw_prob: number | null;
  away_win_prob: number | null;
  predicted_home_score: number | null;
  predicted_away_score: number | null;
  /** 真实比分（来自关联 Match，比赛未结束时为 null） */
  real_home_score: number | null;
  real_away_score: number | null;
  /** 命中判定（仅已结束比赛有值，未结算为 null） */
  accuracy: PredictionAccuracyDetail | null;
  conservative_verdict: string | null;
  aggressive_verdict: string | null;
  key_reasons: string[];
  confidence: number | null;
  mermaid_mindmap: string | null;
  rounds: PredictionRound[];
  final_summary: string | null;
  total_tokens: number;
  total_cost_ms: number;
  error_msg: string | null;
  generated_at: string | null;
}

export interface PredictableMatch {
  match_id: number;
  status: string;
  predicted_home_score: number | null;
  predicted_away_score: number | null;
  confidence: number | null;
  home_team_name: string | null;
  away_team_name: string | null;
  kickoff: string | null;
  stage: string | null;
  match_status?: string | null;
  real_home_score: number | null;
  real_away_score: number | null;
  accuracy?: PredictionAccuracySummary | null;
  generated_at: string | null;
  conservative_verdict: string | null;
}
