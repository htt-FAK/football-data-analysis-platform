import type { RadarData, WorldCupLeaders, WorldCupMatch, WorldCupSummary, WorldCupTeam } from "@/types";

export const mockSummary: WorldCupSummary = {
  league_id: 0,
  league_name: "World Cup",
  season: "2026",
  group_count: 0,
  match_count: 0,
  finished_match_count: 0,
  team_count: 0,
  player_count: 0,
  active_player_count: 0,
  rated_player_count: 0,
  qualified_team_count: 0,
};

export function generateMockTeams(): WorldCupTeam[] {
  return [];
}

export function generateMockLeaders(): WorldCupLeaders {
  return {
    top_scorers: [],
    top_assists: [],
    top_ratings: [],
  };
}

export function generateMockPlayerRadar(): RadarData {
  return {
    dimensions: [],
    values: [],
    recommended_visualization: "radar",
    completeness: "empty",
    median_values: [],
  };
}

export function generateMockMatches(): WorldCupMatch[] {
  return [];
}
