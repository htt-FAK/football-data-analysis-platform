import { apiClient } from "./client";
import type {
  League,
  LeagueTrendsResponse,
  StandingsEntry,
  Match,
  WorldCupSummary,
  WorldCupUpcomingResponse,
} from "@/types";

interface LeagueStandingsResponse {
  league_id: number;
  season: string;
  standings: Array<{
    position?: number;
    group?: string | null;
    stage?: string | null;
    team_id: number;
    team_name: string;
    logo_url?: string | null;
    played?: number;
    won?: number;
    drawn?: number;
    lost?: number;
    goals_for?: number;
    goals_against?: number;
    goal_diff?: number;
    points?: number;
    form?: string | null;
    qualification_status?: string | null;
  }>;
}

interface LeagueScheduleResponse {
  league_id: number;
  season: string;
  matches: Array<{
    id: number;
    matchday?: number | null;
    match_date?: string | null;
    status?: string | null;
    home_team_id: number;
    home_team_name: string;
    away_team_id: number;
    away_team_name: string;
    home_score?: number | null;
    away_score?: number | null;
    venue?: string | null;
    stage?: string | null;
    group?: string | null;
  }>;
}

export async function getLeagues(country?: string): Promise<League[]> {
  const { data } = await apiClient.get<League[]>("/api/v1/leagues", {
    params: country ? { country } : undefined,
  });
  return Array.isArray(data) ? data : [];
}

export async function getLeague(id: number): Promise<League> {
  const { data } = await apiClient.get<League>(`/api/v1/leagues/${id}`);
  return data;
}

export async function getLeagueStandings(
  id: number,
  season?: string,
  stage?: string,
  group?: string
): Promise<StandingsEntry[]> {
  const { data } = await apiClient.get<LeagueStandingsResponse>(`/api/v1/leagues/${id}/standings`, {
    params: { season, stage, group },
  });
  return Array.isArray(data?.standings)
    ? data.standings.map((row) => ({
        team_id: row.team_id,
        team_name: row.team_name,
        team_logo: row.logo_url ?? undefined,
        position: row.position,
        played: row.played,
        wins: row.won,
        draws: row.drawn,
        losses: row.lost,
        goals_for: row.goals_for,
        goals_against: row.goals_against,
        goal_diff: row.goal_diff,
        points: row.points,
        form: row.form ?? undefined,
        stage: row.stage ?? undefined,
        group_name: row.group ?? undefined,
        qualification_status: row.qualification_status ?? undefined,
      }))
    : [];
}

export async function getLeagueSchedule(
  id: number,
  season?: string,
  matchday?: number,
  stage?: string,
  group?: string
): Promise<Match[]> {
  const { data } = await apiClient.get<LeagueScheduleResponse>(`/api/v1/leagues/${id}/schedule`, {
    params: { season, matchday, stage, group },
  });
  return Array.isArray(data?.matches)
    ? data.matches.map((row) => ({
        id: row.id,
        matchday: row.matchday ?? undefined,
        date_time: row.match_date ?? undefined,
        status: row.status ?? undefined,
        home_team_id: row.home_team_id,
        home_team_name: row.home_team_name,
        away_team_id: row.away_team_id,
        away_team_name: row.away_team_name,
        home_score: row.home_score ?? undefined,
        away_score: row.away_score ?? undefined,
        venue: row.venue ?? undefined,
        stage: row.stage ?? undefined,
        group_name: row.group ?? undefined,
      }))
    : [];
}

export async function getLeagueTrends(id: number, season?: string): Promise<LeagueTrendsResponse> {
  const { data } = await apiClient.get<LeagueTrendsResponse>(`/api/v1/leagues/${id}/trends`, {
    params: { season },
  });
  return data;
}

export async function getWorldCupSummary(season: string = "2026"): Promise<WorldCupSummary> {
  const { data } = await apiClient.get<WorldCupSummary>("/api/v1/worldcup/summary", {
    params: { season },
  });
  return data;
}

export async function getWorldCupUpcomingFixtures(
  season: string = "2026",
  limit: number = 16
): Promise<WorldCupUpcomingResponse> {
  const { data } = await apiClient.get<WorldCupUpcomingResponse>("/api/v1/worldcup/upcoming", {
    params: { season, limit },
  });
  return {
    season: data?.season ?? season,
    matches: Array.isArray(data?.matches) ? data.matches : [],
  };
}
