import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout/AppLayout";
import { LiveScoreProvider } from "@/components/providers/LiveScoreProvider";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { TeamList } from "@/pages/teams/TeamList";
import { TeamDetail } from "@/pages/teams/TeamDetail";
import { PlayerList } from "@/pages/players/PlayerList";
import { PlayerDetail } from "@/pages/players/PlayerDetail";
import { MatchList } from "@/pages/matches/MatchList";
import { MatchDetail } from "@/pages/matches/MatchDetail";
import { AIPredict } from "@/pages/AIPredict";
import { WorldCupDashboard } from "@/pages/worldcup/WorldCupDashboard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LiveScoreProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/worldcup" replace />} />
              <Route path="/leagues" element={<Navigate to="/worldcup" replace />} />
              <Route path="/leagues/:id" element={<Navigate to="/worldcup" replace />} />
              <Route path="/teams" element={<TeamList />} />
              <Route path="/teams/:id" element={<TeamDetail />} />
              <Route path="/players" element={<PlayerList />} />
              <Route path="/players/:id" element={<PlayerDetail />} />
              <Route path="/matches" element={<MatchList />} />
              <Route path="/matches/:id" element={<MatchDetail />} />
              <Route path="/ai-predict" element={<AIPredict />} />
              <Route path="/players/compare" element={<Navigate to="/players" replace />} />
              <Route path="/players/top-scorers" element={<Navigate to="/players" replace />} />
              <Route path="/live" element={<Navigate to="/" replace />} />
              <Route path="/worldcup" element={<WorldCupDashboard />} />
              <Route path="/admin" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
          </ErrorBoundary>
        </BrowserRouter>
      </LiveScoreProvider>
    </QueryClientProvider>
  );
}
