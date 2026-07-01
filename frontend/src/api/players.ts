import { apiClient } from "./client";
import type { Player, PlayerStat, RadarData, PositionStats, PlayerCompareResult } from "@/types";
import { getRadarDimensionLabels } from "@/lib/utils";
import { getPositionConfig, normalizePosition } from "@/lib/position-dimensions";

function normalizePlayer(raw: any): Player {
  return {
    id: raw?.id ?? raw?.player_id ?? 0,
    name: raw?.name ?? "",
    full_name: raw?.full_name ?? raw?.name ?? undefined,
    position: raw?.position ?? undefined,
    jersey_number: raw?.jersey_number ?? raw?.shirt_number ?? undefined,
    nationality: raw?.nationality ?? undefined,
    birth_date: raw?.birth_date ?? undefined,
    height_cm: raw?.height_cm ?? raw?.height ?? undefined,
    weight_kg: raw?.weight_kg ?? raw?.weight ?? undefined,
    photo_url: raw?.photo_url ?? undefined,
    team_id: raw?.team_id ?? undefined,
    team_name: raw?.team_name ?? undefined,
    overall_rating: raw?.overall_rating ?? raw?.rating ?? undefined,
    group_name: raw?.group_name ?? raw?.group ?? undefined,
    atk_score: raw?.atk_score ?? undefined,
    org_score: raw?.org_score ?? undefined,
    def_score: raw?.def_score ?? undefined,
    gk_score: raw?.gk_score ?? undefined,
    phy_score: raw?.phy_score ?? undefined,
    dis_score: raw?.dis_score ?? undefined,
  };
}

function normalizePlayerStat(raw: any): PlayerStat {
  return {
    player_id: raw?.player_id ?? 0,
    season: raw?.season ?? undefined,
    appearances: raw?.appearances ?? undefined,
    goals: raw?.goals ?? undefined,
    assists: raw?.assists ?? undefined,
    yellow_cards: raw?.yellow_cards ?? undefined,
    red_cards: raw?.red_cards ?? undefined,
    minutes_played: raw?.minutes_played ?? undefined,
    shots: raw?.shots ?? undefined,
    shots_on_target: raw?.shots_on_target ?? undefined,
    xg: raw?.xg ?? undefined,
    xa: raw?.xa ?? undefined,
    passes: raw?.passes ?? undefined,
    pass_accuracy: raw?.pass_accuracy ?? undefined,
    tackles: raw?.tackles ?? undefined,
    interceptions: raw?.interceptions ?? undefined,
    rating: raw?.rating ?? undefined,
    saves: raw?.saves ?? undefined,
    save_pct: raw?.save_pct ?? raw?.save_rate ?? undefined,
    goals_conceded: raw?.goals_conceded ?? undefined,
    xga: raw?.xga ?? raw?.xcs ?? undefined,
    crosses_stopped: raw?.crosses_stopped ?? raw?.sweeper_actions ?? undefined,
  };
}

function enrichLeaderboardPlayers(rows: any[]): Player[] {
  return rows.map((row) => ({
    ...normalizePlayer(row),
    overall_rating: row?.overall_rating ?? row?.rating ?? row?.goals ?? 0,
    stats: [
      normalizePlayerStat({
        player_id: row?.player_id ?? row?.id,
        appearances: row?.appearances,
        goals: row?.goals,
        assists: row?.assists,
        minutes_played: row?.minutes_played,
        shots: row?.shots,
        shots_on_target: row?.shots_on_target,
        xg: row?.xg,
        xa: row?.xa,
        passes: row?.passes,
        pass_accuracy: row?.pass_accuracy,
        tackles: row?.tackles,
        interceptions: row?.interceptions,
        rating: row?.rating ?? row?.overall_rating,
      }),
    ],
  })) as Player[];
}

export async function getPlayers(
  teamId?: number,
  position?: string,
  name?: string
): Promise<Player[]> {
  const { data } = await apiClient.get<Player[]>("/api/v1/players", {
    params: { team_id: teamId, position, name },
  });
  return Array.isArray(data) ? data.map(normalizePlayer) : [];
}

export async function getPlayer(id: number): Promise<Player> {
  const { data } = await apiClient.get<Player>(`/api/v1/players/${id}`);
  return normalizePlayer(data);
}

export async function getPlayerStats(id: number, season?: string): Promise<PlayerStat> {
  const { data } = await apiClient.get<{ player_id: number; season?: string; stats?: Record<string, unknown> | null }>(
    `/api/v1/players/${id}/stats`,
    {
      params: { season },
    }
  );
  return normalizePlayerStat({
    player_id: data?.player_id ?? id,
    season: data?.season,
    ...(data?.stats ?? {}),
  });
}

export async function getPlayerRadar(id: number, season?: string, position?: string): Promise<RadarData> {
  const { data } = await apiClient.get<RadarData>(`/api/v1/players/${id}/radar`, {
    params: { season, position },
  });
  return {
    dimensions: Array.isArray(data?.dimensions) ? getRadarDimensionLabels(data.dimensions) : [],
    values: Array.isArray(data?.values) ? data.values : [],
    recommended_visualization:
      (data as any)?.recommended_visualization ??
      (data as any)?.mode ??
      (data as any)?.completeness?.recommended_visualization ??
      "advanced_radar",
    completeness:
      typeof (data as any)?.completeness === "string"
        ? (data as any).completeness
        : (data as any)?.completeness?.label ?? "available",
    median_values: Array.isArray((data as any)?.median_values) ? (data as any).median_values : undefined,
    position: (data as any)?.position ?? position,
  };
}

export async function getPlayerPositionRank(id: number, season?: string) {
  const { data } = await apiClient.get(`/api/v1/players/${id}/position-rank`, {
    params: { season },
  });
  return {
    ...data,
    total_players: data?.total_players ?? data?.total,
  };
}

export async function comparePlayers(playerA: number, playerB: number): Promise<PlayerCompareResult> {
  const { data } = await apiClient.get<any>("/api/v1/players/compare", {
    params: { player_a: playerA, player_b: playerB },
  });
  return {
    player_a: normalizePlayer(data?.player_a ?? {}),
    player_b: normalizePlayer(data?.player_b ?? {}),
    stats_a: normalizePlayerStat({ player_id: data?.player_a?.id, ...(data?.season_stats?.player_a ?? {}) }),
    stats_b: normalizePlayerStat({ player_id: data?.player_b?.id, ...(data?.season_stats?.player_b ?? {}) }),
    radar_a: data?.radar?.player_a,
    radar_b: data?.radar?.player_b,
    comparison_summary: data?.comparison_summary ?? {},
    recommended_visualization: data?.recommended_visualization ?? "summary_only",
    completeness: data?.completeness ?? {},
  };
}

export async function getTopScorers(limit = 50, season?: string): Promise<Player[]> {
  const { data } = await apiClient.get<any[]>("/api/v1/players/top-scorers", {
    params: { limit, season },
  });
  return Array.isArray(data) ? enrichLeaderboardPlayers(data) : [];
}

export async function getPositionStats(position: string): Promise<PositionStats> {
  const { data } = await apiClient.get<any>("/api/v1/players/position-stats", {
    params: { position },
  });

  const distributions = data?.distributions ?? {};
  const distributionKeys = Object.keys(distributions);

  if (distributionKeys.length > 0) {
    const normalizedPosition = normalizePosition(position);
    const positionConfig = getPositionConfig(normalizedPosition);
    const fieldToLabel = new Map(
      positionConfig.dimensions.map((dimension) => [String(dimension.field), dimension.label])
    );

    return {
      position: data?.position ?? position,
      total_players: data?.total_players ?? data?.count ?? 0,
      count: data?.count ?? data?.total_players ?? 0,
      dimensions: distributionKeys.map((key) => fieldToLabel.get(key) ?? key),
      median: distributionKeys.map((key) => Number(distributions[key]?.median ?? 0)),
      q1: distributionKeys.map((key) => Number(distributions[key]?.q1 ?? 0)),
      q3: distributionKeys.map((key) => Number(distributions[key]?.q3 ?? 0)),
      min: distributionKeys.map((key) => Number(distributions[key]?.min ?? 0)),
      max: distributionKeys.map((key) => Number(distributions[key]?.max ?? 0)),
    };
  }

  return {
    ...data,
    total_players: data?.total_players ?? data?.count ?? 0,
  };
}
