import { apiClient } from "./client";
import type { Match, MatchEvent, MatchReport, MatchXgTimeline, Shot, RawMatch } from "@/types";

function normalizeMatch(row: RawMatch): Match {
  const dateTime = row?.date_time ?? row?.match_date ?? undefined;
  return {
    ...row,
    id: row?.id ?? 0,
    home_team_id: row?.home_team_id ?? 0,
    home_team_name: row?.home_team_name ?? "",
    away_team_id: row?.away_team_id ?? 0,
    away_team_name: row?.away_team_name ?? "",
    date_time: dateTime,
    match_date: row?.match_date ?? dateTime,
    group_name: row?.group_name ?? row?.group ?? undefined,
  };
}

function getMatchTime(match: Match): number {
  const value = match.date_time ?? match.match_date;
  if (!value) return Number.MAX_SAFE_INTEGER;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? Number.MAX_SAFE_INTEGER : time;
}

export async function getMatches(params?: {
  league_id?: number;
  matchday?: number;
  status?: string;
  date?: string;
  stage?: string;
  group?: string;
  limit?: number;
}): Promise<Match[]> {
  const { data } = await apiClient.get<Match[]>("/api/v1/matches", { params });
  return Array.isArray(data)
    ? data
        .map(normalizeMatch)
        .sort((a, b) => getMatchTime(a) - getMatchTime(b) || a.id - b.id)
    : [];
}

export async function getMatch(id: number): Promise<Match> {
  const { data } = await apiClient.get<Match>(`/api/v1/matches/${id}`);
  return normalizeMatch(data);
}

export async function getMatchEvents(id: number): Promise<MatchEvent[]> {
  const { data } = await apiClient.get<MatchEvent[]>(`/api/v1/matches/${id}/events`);
  return Array.isArray(data) ? data : [];
}

export async function getMatchXgTimeline(id: number): Promise<MatchXgTimeline> {
  const { data } = await apiClient.get<MatchXgTimeline>(`/api/v1/matches/${id}/xg-timeline`);
  return data;
}

export async function getMatchShots(id: number): Promise<Shot[]> {
  const { data } = await apiClient.get<Shot[]>(`/api/v1/matches/${id}/shots`);
  return Array.isArray(data) ? data : [];
}

export async function getMatchReport(id: number): Promise<MatchReport> {
  const { data } = await apiClient.get<MatchReport>(`/api/v1/matches/${id}/report`);
  return data;
}

export async function refreshMatch(id: number): Promise<{ status: string; message?: string }> {
  const { data } = await apiClient.post<{ status: string; message?: string }>(
    `/api/v1/matches/${id}/refresh`
  );
  return data;
}
