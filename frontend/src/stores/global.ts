import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { League } from "@/types";

interface GlobalState {
  selectedLeagueId: number | null;
  setSelectedLeagueId: (id: number | null) => void;
  selectedSeason: string | null;
  setSelectedSeason: (season: string | null) => void;
  leagues: League[];
  setLeagues: (leagues: League[]) => void;
  pendingPredictionMatchIds: string[];
  setPendingPredictionMatchIds: (matchIds: string[]) => void;
  addPendingPredictionMatchId: (matchId: string) => void;
  removePendingPredictionMatchId: (matchId: string) => void;
}

export const useGlobalStore = create<GlobalState>()(
  persist(
    (set, get) => ({
      selectedLeagueId: null,
      setSelectedLeagueId: (id) => set({ selectedLeagueId: id }),
      selectedSeason: null,
      setSelectedSeason: (season) => set({ selectedSeason: season }),
      leagues: [],
      setLeagues: (leagues) => set({ leagues }),
      pendingPredictionMatchIds: [],
      setPendingPredictionMatchIds: (matchIds) => set({ pendingPredictionMatchIds: Array.from(new Set(matchIds)) }),
      addPendingPredictionMatchId: (matchId) => {
        const current = get().pendingPredictionMatchIds;
        if (current.includes(matchId)) return;
        set({ pendingPredictionMatchIds: [...current, matchId] });
      },
      removePendingPredictionMatchId: (matchId) =>
        set({
          pendingPredictionMatchIds: get().pendingPredictionMatchIds.filter((id) => id !== matchId),
        }),
    }),
    {
      name: "sportsdata-global-store",
      partialize: (state) => ({
        pendingPredictionMatchIds: state.pendingPredictionMatchIds,
      }),
    }
  )
);
