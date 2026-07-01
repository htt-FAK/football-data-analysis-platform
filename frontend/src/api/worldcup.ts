import { apiClient } from "./client";
import type {
  RadarData,
  WorldCupCoverage,
  WorldCupLeaderItem,
  WorldCupLeaders,
  WorldCupMatch,
  WorldCupPlayer,
  WorldCupSummary,
  WorldCupTeam,
} from "@/types";

const BASE_PATH = "/api/v1/worldcup";
const DEFAULT_SEASON = "2026";

interface WorldCupPlayersResponse {
  season?: string;
  sort_by?: string;
  group?: string | null;
  position?: string | null;
  players?: WorldCupPlayer[];
}

interface RawWorldCupLeaderRow {
  player_id: number;
  name: string;
  position?: string | null;
  team_id?: number | null;
  team_name?: string | null;
  photo_url?: string | null;
  appearances?: number | null;
  goals?: number | null;
  assists?: number | null;
  minutes_played?: number | null;
  rating?: number | null;
  shots?: number | null;
  passes?: number | null;
}

interface RawWorldCupLeadersResponse {
  season?: string;
  top_scorers?: RawWorldCupLeaderRow[];
  top_assists?: RawWorldCupLeaderRow[];
  top_ratings?: RawWorldCupLeaderRow[];
}

interface RawWorldCupCoverageResponse {
  season?: string;
  coverage?: WorldCupCoverage["coverage"];
}

interface RawWorldCupTeamsResponse {
  season?: string;
  group?: string | null;
  teams?: WorldCupTeam[];
}

interface RawWorldCupMatchesResponse {
  season?: string;
  matches?: RawWorldCupMatchRow[];
}

interface RawWorldCupMatchRow {
    match_id: number;
    match_date?: string | null;
    status?: string | null;
    stage?: string | null;
    group?: string | null;
    home_team_id?: number | null;
    home_team_name?: string | null;
    away_team_id?: number | null;
    away_team_name?: string | null;
    home_score?: number | null;
    away_score?: number | null;
    venue?: string | null;
}

function normalizeLeaderItem(
  row: RawWorldCupLeaderRow,
  type: "goals" | "assists" | "rating"
): WorldCupLeaderItem {
  const rawValue =
    type === "goals" ? row.goals : type === "assists" ? row.assists : row.rating;

  return {
    player_id: row.player_id,
    name: row.name,
    team_name: row.team_name ?? undefined,
    value: Number(rawValue ?? 0),
    type,
    position: row.position ?? undefined,
    photo_url: row.photo_url ?? undefined,
  };
}

function normalizeWorldCupTeam(row: WorldCupTeam): WorldCupTeam {
  return {
    team_id: row.team_id,
    name: row.name,
    group: row.group ?? "Ungrouped",
    played: row.played ?? 0,
    wins: row.wins ?? 0,
    draws: row.draws ?? 0,
    losses: row.losses ?? 0,
    goals_for: row.goals_for ?? 0,
    goals_against: row.goals_against ?? 0,
    goal_diff: row.goal_diff ?? 0,
    points: row.points ?? 0,
    rank: row.rank ?? 0,
  };
}

function normalizeWorldCupMatch(row: RawWorldCupMatchRow): WorldCupMatch {
  return {
    match_id: row.match_id,
    home_team: row.home_team_name ?? "",
    away_team: row.away_team_name ?? "",
    home_score: row.home_score ?? undefined,
    away_score: row.away_score ?? undefined,
    stage: row.stage ?? undefined,
    match_date: row.match_date ?? undefined,
    status: row.status ?? undefined,
    group_name: row.group ?? undefined,
    home_team_id: row.home_team_id ?? undefined,
    away_team_id: row.away_team_id ?? undefined,
    venue: row.venue ?? undefined,
  };
}

export async function getWorldCupSummary(season?: string): Promise<WorldCupSummary> {
  const { data } = await apiClient.get<WorldCupSummary>(`${BASE_PATH}/summary`, {
    params: { season },
  });
  return data;
}

export async function getWorldCupTeams(group?: string): Promise<WorldCupTeam[]> {
  const { data } = await apiClient.get<RawWorldCupTeamsResponse>(`${BASE_PATH}/teams`, {
    params: { season: DEFAULT_SEASON, group },
  });
  return Array.isArray(data?.teams) ? data.teams.map(normalizeWorldCupTeam) : [];
}

export async function getWorldCupPlayers(params?: {
  group?: string;
  position?: string;
  limit?: number;
}): Promise<WorldCupPlayer[]> {
  const { data } = await apiClient.get<WorldCupPlayersResponse>(`${BASE_PATH}/players`, {
    params,
  });
  return Array.isArray(data?.players) ? data.players : [];
}

export async function getWorldCupLeaders(limit?: number): Promise<WorldCupLeaders> {
  const { data } = await apiClient.get<RawWorldCupLeadersResponse>(`${BASE_PATH}/leaders`, {
    params: { limit },
  });

  return {
    top_scorers: Array.isArray(data?.top_scorers)
      ? data.top_scorers.map((row) => normalizeLeaderItem(row, "goals"))
      : [],
    top_assists: Array.isArray(data?.top_assists)
      ? data.top_assists.map((row) => normalizeLeaderItem(row, "assists"))
      : [],
    top_ratings: Array.isArray(data?.top_ratings)
      ? data.top_ratings.map((row) => normalizeLeaderItem(row, "rating"))
      : [],
  };
}

export async function getWorldCupPlayerRadar(
  playerId: number | string
): Promise<RadarData> {
  const { data } = await apiClient.get<RadarData>(
    `${BASE_PATH}/players/${playerId}/radar`
  );
  return data;
}

export async function getWorldCupMatches(
  status?: string,
  limit?: number
): Promise<WorldCupMatch[]> {
  const { data } = await apiClient.get<RawWorldCupMatchesResponse>(`${BASE_PATH}/matches`, {
    params: { season: DEFAULT_SEASON, status, limit },
  });
  return Array.isArray(data?.matches) ? data.matches.map(normalizeWorldCupMatch) : [];
}

export async function getWorldCupCoverage(): Promise<WorldCupCoverage> {
  const { data } = await apiClient.get<RawWorldCupCoverageResponse>(`${BASE_PATH}/coverage`);
  return {
    season: data?.season ?? DEFAULT_SEASON,
    coverage: Array.isArray(data?.coverage) ? data.coverage : [],
  };
}
