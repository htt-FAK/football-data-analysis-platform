import { apiClient } from "./client";
import type { MatchPredictionResponse, PredictableMatch } from "@/types";

export async function getPrediction(matchId: number): Promise<MatchPredictionResponse> {
  try {
    const { data } = await apiClient.get<MatchPredictionResponse>(`/api/v1/predict/matches/${matchId}`);
    return data;
  } catch (error: any) {
    if (error?.response?.status === 404) {
      return null as unknown as MatchPredictionResponse;
    }
    throw error;
  }
}

export async function getPredictableMatches(limit = 50): Promise<PredictableMatch[]> {
  const { data } = await apiClient.get<{ matches: PredictableMatch[] }>(
    "/api/v1/predict/matches",
    { params: { limit } }
  );
  return Array.isArray(data?.matches) ? data.matches : [];
}

export async function getPredictionStatus(): Promise<{
  enabled: boolean;
  stepfun_configured: boolean;
  deepseek_configured: boolean;
  ready: boolean;
}> {
  const { data } = await apiClient.get("/api/v1/predict/status");
  return data;
}

export async function triggerPrediction(
  matchId: number,
  sync = false
): Promise<MatchPredictionResponse | { match_id: number; status: string; message: string }> {
  const { data } = await apiClient.post(`/api/v1/predict/matches/${matchId}/trigger`, null, {
    params: { sync },
  });
  return data;
}
