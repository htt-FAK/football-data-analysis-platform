import { apiClient } from "./client";
import type { Team, TeamStat, RadarData, Shot } from "@/types";

export async function getTeams(leagueId?: number, name?: string, season?: string): Promise<Team[]> {
  const { data } = await apiClient.get<Team[]>("/api/v1/teams", {
    params: { league_id: leagueId, name, season },
  });
  return Array.isArray(data) ? data : [];
}

export async function getTeam(id: number): Promise<Team> {
  const { data } = await apiClient.get<Team>(`/api/v1/teams/${id}`);
  return data;
}

export async function getTeamStats(id: number, season?: string): Promise<TeamStat> {
  const { data } = await apiClient.get<TeamStat>(`/api/v1/teams/${id}/stats`, {
    params: { season },
  });
  return data;
}

export async function getTeamRadar(id: number, season?: string): Promise<RadarData> {
  const { data } = await apiClient.get<RadarData>(`/api/v1/teams/${id}/radar`, {
    params: { season },
  });
  return data;
}

export async function getTeamShots(id: number, season?: string): Promise<Shot[]> {
  const { data } = await apiClient.get<Shot[]>(`/api/v1/teams/${id}/shots`, {
    params: { season },
  });
  return Array.isArray(data) ? data : [];
}
