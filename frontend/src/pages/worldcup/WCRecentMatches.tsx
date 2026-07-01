import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock, Flag, Repeat, Target } from "lucide-react";

import { getMatchReport } from "@/api/matches";
import { getWorldCupMatches } from "@/api/worldcup";
import {
  formatWorldCupDateTime,
  getStageLabel,
  getTeamIdentity,
  shouldDisplayMatchScore,
} from "@/lib/utils";
import type { MatchEvent, MatchReport, WorldCupMatch } from "@/types";

function TeamFlag({
  label,
  flagUrl,
}: {
  label: string;
  flagUrl?: string;
}) {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[#23262d] bg-[#11151d]">
      {flagUrl ? (
        <img src={flagUrl} alt={label} className="h-full w-full object-cover" />
      ) : (
        <span className="text-[10px] font-bold text-[#94a3b8]">{label.charAt(0) || "?"}</span>
      )}
    </div>
  );
}

function SummaryEventIcon({ eventType }: { eventType?: string | null }) {
  const type = (eventType || "").toLowerCase();
  if (type.includes("goal")) return <Target className="h-3.5 w-3.5 text-emerald-400" />;
  if (type.includes("card")) return <Flag className="h-3.5 w-3.5 text-amber-400" />;
  if (type.includes("substitution")) return <Repeat className="h-3.5 w-3.5 text-sky-400" />;
  return <Clock className="h-3.5 w-3.5 text-[#64748b]" />;
}

function buildMatchSummary(report?: MatchReport | null): MatchEvent[] {
  if (!report) return [];
  const keyEvents = report.impact_summary?.key_events ?? [];
  if (keyEvents.length > 0) return keyEvents.slice(0, 2);
  return (report.events ?? []).slice(0, 2);
}

function formatSummaryEvent(event: MatchEvent): string {
  if (event.detail) return event.detail;
  return event.player_name || event.team_name || "比赛事件";
}

function RecentMatchRow({
  match,
  report,
}: {
  match: WorldCupMatch;
  report?: MatchReport | null;
}) {
  const showScore = shouldDisplayMatchScore(match.status, match.home_score, match.away_score);
  const homeScore = showScore ? (match.home_score ?? 0) : null;
  const awayScore = showScore ? (match.away_score ?? 0) : null;
  const homeWin = homeScore !== null && awayScore !== null && homeScore > awayScore;
  const awayWin = homeScore !== null && awayScore !== null && awayScore > homeScore;
  const isDraw = homeScore !== null && awayScore !== null && homeScore === awayScore;
  const homeTeam = getTeamIdentity(match.home_team);
  const awayTeam = getTeamIdentity(match.away_team);
  const summaryEvents = buildMatchSummary(report);
  const availability = report?.data_availability?.events;

  return (
    <Link
      to={`/matches/${match.match_id}`}
      className="grid gap-3 border-b border-[#23262d] py-4 transition-colors hover:bg-[#11151d]"
    >
      <div className="flex items-center gap-4">
        <div className="w-28 flex-shrink-0">
          <div className="text-xs text-[#94a3b8]">{getStageLabel(match.stage || "阶段待定")}</div>
          <div className="text-xs text-[#64748b]">{formatWorldCupDateTime(match.match_date, match.venue)}</div>
        </div>

        <div className="flex min-w-0 flex-1 items-center justify-end gap-2 text-right font-medium">
          <span className={homeWin || isDraw ? "text-[#f1f5f9]" : "text-[#94a3b8]"}>{homeTeam.displayName}</span>
          <TeamFlag label={homeTeam.displayName} flagUrl={homeTeam.flagUrl} />
        </div>

        <div className="flex flex-shrink-0 items-center gap-2 font-mono text-lg font-bold">
          <span className={homeWin || isDraw ? "text-[#f1f5f9]" : "text-[#94a3b8]"}>{homeScore ?? "—"}</span>
          <span className="text-[#64748b]">-</span>
          <span className={awayWin || isDraw ? "text-[#f1f5f9]" : "text-[#94a3b8]"}>{awayScore ?? "—"}</span>
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <TeamFlag label={awayTeam.displayName} flagUrl={awayTeam.flagUrl} />
          <span className={awayWin || isDraw ? "text-[#f1f5f9]" : "text-[#94a3b8]"}>{awayTeam.displayName}</span>
        </div>

        <div className="flex w-20 flex-shrink-0 items-center justify-end gap-2">
          <span className="text-xs font-medium uppercase tracking-wider text-[#22c55e]">已结束</span>
          <ArrowRight className="h-4 w-4 text-[#64748b]" />
        </div>
      </div>

      <div className="pl-28">
        {summaryEvents.length > 0 ? (
          <div className="space-y-1.5">
            {summaryEvents.map((event, index) => (
              <div
                key={`${event.id ?? index}-${event.minute}-${event.event_type}`}
                className="flex items-start gap-2 text-xs text-[#cbd5e1]"
              >
                <div className="mt-0.5 shrink-0">
                  <SummaryEventIcon eventType={event.event_type} />
                </div>
                <div className="min-w-0">
                  <span className="font-mono text-[#22c55e]">
                    {event.minute != null ? `${event.minute}'` : "--"}
                  </span>
                  <span className="mx-2 text-[#64748b]">·</span>
                  <span>{formatSummaryEvent(event)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-[#64748b]">{availability?.note || "这场比赛的事件摘要回填中。"}</div>
        )}
      </div>
    </Link>
  );
}

export function WCRecentMatches() {
  const { data: matches = [], isLoading } = useQuery<WorldCupMatch[]>({
    queryKey: ["worldcup-matches-finished"],
    queryFn: () => getWorldCupMatches("finished", 8),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const matchIds = useMemo(() => matches.map((match) => match.match_id), [matches]);
  const { data: reports = {} } = useQuery<Record<number, MatchReport | null>>({
    queryKey: ["worldcup-recent-match-reports", matchIds],
    enabled: matchIds.length > 0,
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    queryFn: async () => {
      const entries = await Promise.all(
        matchIds.map(async (matchId) => {
          try {
            const report = await getMatchReport(matchId);
            return [matchId, report] as const;
          } catch {
            return [matchId, null] as const;
          }
        })
      );
      return Object.fromEntries(entries);
    },
  });

  return (
    <div className="border-b border-[#23262d] py-12">
      <div className="mx-auto max-w-[1400px] px-4">
        <div className="mb-6 flex items-baseline justify-between">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#f1f5f9]">最近赛果</h2>
          <span className="text-xs text-[#64748b]">最近 8 场已结束世界杯比赛</span>
        </div>

        <div className="border-t border-[#23262d]">
          {isLoading && matches.length === 0 ? (
            <div className="flex h-12 items-center text-sm text-[#94a3b8]">正在加载最近比赛...</div>
          ) : matches.length === 0 ? (
            <div className="flex h-12 items-center text-sm text-[#94a3b8]">暂时还没有已结束的世界杯比赛。</div>
          ) : (
            matches.map((match) => (
              <RecentMatchRow key={match.match_id} match={match} report={reports[match.match_id] ?? null} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
