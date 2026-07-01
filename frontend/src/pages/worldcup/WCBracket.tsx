import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, Flag, Medal, RefreshCw, Repeat, Target, Trophy } from "lucide-react";

import { getWorldCupMatches } from "@/api/worldcup";
import { getMatchReport } from "@/api/matches";
import {
  cn,
  formatDateTime,
  formatWorldCupDateTime,
  getEventTypeLabel,
  getCountryLabel,
  getGroupLabel,
  getStageLabel,
  getStatusLabel,
  getTeamIdentity,
  getWorldCupMatchTime,
  resolveWorldCupDisplayStatus,
  shouldDisplayMatchScore,
} from "@/lib/utils";
import type { MatchEvent, MatchReport, WorldCupMatch } from "@/types";

type BracketRound = "r32" | "r16" | "qf" | "sf" | "final" | "third";

interface BracketMatch {
  id: string;
  round: BracketRound;
  matchIndex: number;
  homeTeam: string | null;
  awayTeam: string | null;
  homeScore: number | null;
  awayScore: number | null;
  status: "scheduled" | "finished" | "live";
  date?: string | null;
  stageLabel: string;
  venue?: string | null;
  sourceMatch?: WorldCupMatch;
}

const ROUND_LABELS: Record<BracketRound, string> = {
  r32: "32强",
  r16: "16强",
  qf: "1/4决赛",
  sf: "半决赛",
  final: "决赛",
  third: "季军赛",
};

const ROUND_ORDER: BracketRound[] = ["r32", "r16", "qf", "sf", "final"];

const STAGE_TO_ROUND: Array<{ patterns: string[]; round: BracketRound }> = [
  { patterns: ["round of 32"], round: "r32" },
  { patterns: ["round of 16"], round: "r16" },
  { patterns: ["quarterfinal", "quarter final", "quarter-finals", "quarter finals"], round: "qf" },
  { patterns: ["semifinal", "semi final", "semi-finals", "semi finals"], round: "sf" },
  { patterns: ["third place", "third-place"], round: "third" },
  { patterns: ["final"], round: "final" },
];

function normalizeStage(stage?: string | null): BracketRound | null {
  if (!stage) return null;
  const normalized = stage.trim().toLowerCase().replace(/[_-]+/g, " ");
  for (const item of STAGE_TO_ROUND) {
    if (item.patterns.some((pattern) => normalized.includes(pattern))) {
      return item.round;
    }
  }
  return null;
}

function normalizeMatchStatus(
  status?: string | null,
  kickoff?: string | null,
  venue?: string | null
): "scheduled" | "finished" | "live" {
  const resolved = resolveWorldCupDisplayStatus(status, kickoff, venue);
  if (resolved === "finished") return "finished";
  if (resolved === "live") return "live";
  return "scheduled";
}

function formatTeamName(teamName: string | null | undefined): string {
  if (!teamName) return "待定";
  return getTeamIdentity(teamName).displayName || getCountryLabel(teamName) || teamName;
}

function TeamFlag({
  label,
  flagUrl,
}: {
  label: string;
  flagUrl?: string;
}) {
  return (
    <div className="flex h-5 w-5 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[#23262d] bg-[#11151d]">
      {flagUrl ? (
        <img src={flagUrl} alt={label} className="h-full w-full object-cover" />
      ) : (
        <span className="text-[9px] font-bold text-[#94a3b8]">{label.charAt(0) || "?"}</span>
      )}
    </div>
  );
}

function buildBracketData(matches: WorldCupMatch[]): BracketMatch[] {
  const roundBuckets: Record<BracketRound, WorldCupMatch[]> = {
    r32: [],
    r16: [],
    qf: [],
    sf: [],
    final: [],
    third: [],
  };

  matches.forEach((match) => {
    const round = normalizeStage(match.stage);
    if (!round) return;
    roundBuckets[round].push(match);
  });

  return (Object.entries(roundBuckets) as Array<[BracketRound, WorldCupMatch[]]>).flatMap(
    ([round, roundMatches]) =>
      roundMatches
        .sort((a, b) => {
          const timeA = getWorldCupMatchTime(a.match_date, a.venue);
          const timeB = getWorldCupMatchTime(b.match_date, b.venue);
          return timeA - timeB || a.match_id - b.match_id;
        })
        .map((match, index) => ({
          id: `${round}-${match.match_id}`,
          round,
          matchIndex: index,
          homeTeam: match.home_team,
          awayTeam: match.away_team,
          homeScore: shouldDisplayMatchScore(
            resolveWorldCupDisplayStatus(match.status, match.match_date, match.venue),
            match.home_score,
            match.away_score
          )
            ? (match.home_score ?? null)
            : null,
          awayScore: shouldDisplayMatchScore(
            resolveWorldCupDisplayStatus(match.status, match.match_date, match.venue),
            match.home_score,
            match.away_score
          )
            ? (match.away_score ?? null)
            : null,
          status: normalizeMatchStatus(match.status, match.match_date, match.venue),
          date: match.match_date,
          venue: match.venue,
          stageLabel: getStageLabel(match.stage),
          sourceMatch: match,
        }))
  );
}

function SummaryEventIcon({ eventType }: { eventType?: string | null }) {
  const type = (eventType || "").toLowerCase();
  if (type.includes("goal")) return <Target className="h-3.5 w-3.5 text-emerald-400" />;
  if (type.includes("card")) return <Flag className="h-3.5 w-3.5 text-amber-400" />;
  if (type.includes("substitution")) return <Repeat className="h-3.5 w-3.5 text-sky-400" />;
  return <Clock className="h-3.5 w-3.5 text-[#64748b]" />;
}

function KeyEventSummary({ events }: { events: MatchEvent[] }) {
  if (events.length === 0) {
    return <div className="text-[11px] text-[#64748b]">这场比赛的关键事件摘要补充中。</div>;
  }

  return (
    <div className="space-y-2">
      {events.slice(0, 3).map((event, index) => (
        <div
          key={`${event.id ?? index}-${event.minute}-${event.event_type}`}
          className="flex items-start gap-2 text-[11px] text-[#cbd5e1]"
        >
          <div className="mt-0.5 shrink-0">
            <SummaryEventIcon eventType={event.event_type} />
          </div>
          <div className="min-w-0">
            <div className="font-mono text-[10px] text-[#22c55e]">
              {event.minute != null ? `${event.minute}'` : "--"}
            </div>
            <div className="leading-5">
              {event.detail || `${getEventTypeLabel(event.event_type)} · ${event.player_name || event.team_name || "比赛事件"}`}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BracketMatchCard({
  match,
  isHighlighted,
  onClick,
}: {
  match: BracketMatch;
  isHighlighted?: boolean;
  onClick?: () => void;
}) {
  const homeIdentity = getTeamIdentity(match.homeTeam);
  const awayIdentity = getTeamIdentity(match.awayTeam);
  const homeWin =
    match.status === "finished" &&
    match.homeScore !== null &&
    match.awayScore !== null &&
    match.homeScore > match.awayScore;
  const awayWin =
    match.status === "finished" &&
    match.homeScore !== null &&
    match.awayScore !== null &&
    match.awayScore > match.homeScore;
  const isFinished = match.status === "finished";

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative w-full border bg-[#0d0f12] text-left transition-all duration-200",
        isHighlighted ? "border-[#22c55e]" : "border-[#23262d]",
        onClick && "cursor-pointer hover:border-[#22c55e]/50"
      )}
    >
      <div className="px-3 py-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[10px] uppercase tracking-widest text-[#64748b]">{match.stageLabel}</span>
          <span className="text-[10px] text-[#64748b]">{formatWorldCupDateTime(match.date, match.venue)}</span>
        </div>
        <div
          className={cn(
            "flex items-center justify-between gap-2 h-7",
            isFinished && homeWin ? "bg-[#22c55e]/5 -mx-3 px-3" : ""
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <TeamFlag label={homeIdentity.displayName} flagUrl={homeIdentity.flagUrl} />
            <span
              className={cn(
                "text-xs truncate min-w-0",
                homeWin ? "text-[#f1f5f9] font-medium" : isFinished ? "text-[#64748b]" : "text-[#94a3b8]"
              )}
            >
              {homeIdentity.displayName}
            </span>
          </div>
          <span
            className={cn(
              "font-mono text-sm font-bold ml-2 w-6 text-right",
              homeWin ? "text-[#22c55e]" : isFinished ? "text-[#94a3b8]" : "text-[#475569]"
            )}
          >
            {match.homeScore !== null ? match.homeScore : match.homeTeam ? "—" : ""}
          </span>
        </div>
        <div
          className={cn(
            "flex items-center justify-between gap-2 h-7 border-t border-[#23262d]/50",
            isFinished && awayWin ? "bg-[#22c55e]/5 -mx-3 px-3" : ""
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <TeamFlag label={awayIdentity.displayName} flagUrl={awayIdentity.flagUrl} />
            <span
              className={cn(
                "text-xs truncate min-w-0",
                awayWin ? "text-[#f1f5f9] font-medium" : isFinished ? "text-[#64748b]" : "text-[#94a3b8]"
              )}
            >
              {awayIdentity.displayName}
            </span>
          </div>
          <span
            className={cn(
              "font-mono text-sm font-bold ml-2 w-6 text-right",
              awayWin ? "text-[#22c55e]" : isFinished ? "text-[#94a3b8]" : "text-[#475569]"
            )}
          >
            {match.awayScore !== null ? match.awayScore : match.awayTeam ? "—" : ""}
          </span>
        </div>
      </div>
      {match.status === "live" && (
        <div className="absolute top-1 right-1 flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-[#ef4444] animate-pulse" />
          <span className="text-[9px] uppercase text-[#ef4444] font-bold">LIVE</span>
        </div>
      )}
    </button>
  );
}

function FeatureCard({
  title,
  icon: Icon,
  accent,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`border ${accent} bg-[#0d0f12]`}>
      <div className="px-4 py-3 border-b border-current/20 flex items-center justify-center gap-2">
        <Icon className="w-4 h-4" />
        <span className="text-xs font-bold uppercase tracking-widest">{title}</span>
      </div>
      {children}
    </div>
  );
}

function RoundColumn({
  round,
  matches,
  selectedMatchId,
  onSelectMatch,
}: {
  round: BracketRound;
  matches: BracketMatch[];
  selectedMatchId: string | null;
  onSelectMatch: (match: BracketMatch) => void;
}) {
  const gap =
    round === "r32" ? "gap-2" : round === "r16" ? "gap-4" : round === "qf" ? "gap-8" : "gap-16";

  return (
    <div className="flex-1 flex flex-col">
      <div className="text-center mb-4">
        <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#64748b]">
          {ROUND_LABELS[round]}
        </span>
      </div>
      <div className={cn("flex-1 flex flex-col justify-around", gap)}>
        {matches.length === 0 ? (
          <div className="border border-dashed border-[#23262d] px-3 py-8 text-center text-xs text-[#64748b]">
            暂无该轮次赛程
          </div>
        ) : (
          matches.map((match) => (
            <BracketMatchCard
              key={match.id}
              match={match}
              isHighlighted={selectedMatchId === match.id}
              onClick={() => onSelectMatch(match)}
            />
          ))
        )}
      </div>
    </div>
  );
}

export function WCBracket() {
  const navigate = useNavigate();
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [activeRound, setActiveRound] = useState<BracketRound>("r32");

  const { data: apiMatches = [], isLoading, dataUpdatedAt } = useQuery<WorldCupMatch[]>({
    queryKey: ["worldcup-matches-knockout"],
    queryFn: () => getWorldCupMatches(undefined, 128),
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const bracketData = useMemo(() => buildBracketData(apiMatches), [apiMatches]);

  const matchesByRound = useMemo(() => {
    const map: Record<BracketRound, BracketMatch[]> = {
      r32: [],
      r16: [],
      qf: [],
      sf: [],
      final: [],
      third: [],
    };
    bracketData.forEach((m) => {
      map[m.round].push(m);
    });
    Object.values(map).forEach((arr) => arr.sort((a, b) => a.matchIndex - b.matchIndex));
    return map;
  }, [bracketData]);

  const displayRounds = useMemo(() => {
    const startIdx = ROUND_ORDER.indexOf(activeRound);
    return ROUND_ORDER.slice(startIdx, startIdx + 3);
  }, [activeRound]);

  const selectedMatch = bracketData.find((m) => m.id === selectedMatchId) || null;
  const selectedMatchReportId = selectedMatch?.sourceMatch?.match_id;
  const { data: selectedReport } = useQuery<MatchReport>({
    queryKey: ["worldcup-bracket-match-report", selectedMatchReportId],
    queryFn: () => getMatchReport(selectedMatchReportId as number),
    enabled: Boolean(selectedMatchReportId),
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });
  const finishedCount = useMemo(
    () => bracketData.filter((m) => m.status === "finished").length,
    [bracketData]
  );
  const liveCount = useMemo(() => bracketData.filter((m) => m.status === "live").length, [bracketData]);
  const totalCount = bracketData.filter((m) => m.round !== "third").length;

  return (
    <div className="border-b border-[#23262d] py-12">
      <div className="mx-auto max-w-[1400px] px-4">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-[#64748b]">
              <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
              淘汰赛实时对阵
            </div>
            <h2 className="mt-2 text-xl font-black tracking-tight text-[#f1f5f9]">世界杯对阵图</h2>
            <p className="mt-1 text-sm text-[#94a3b8]">
              直接使用世界杯真实赛程，自动每 30 秒刷新一次。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-[#64748b]">
            <span>
              已完赛 <span className="font-mono font-bold text-[#22c55e]">{finishedCount}</span> / {totalCount}
            </span>
            <span>
              进行中 <span className="font-mono font-bold text-[#ef4444]">{liveCount}</span>
            </span>
            <span>更新于 {dataUpdatedAt ? formatDateTime(new Date(dataUpdatedAt).toISOString()) : "--"}</span>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap items-center gap-1 border border-[#23262d] bg-[#11151d] p-1">
          {(["r32", "r16", "qf", "sf"] as BracketRound[]).map((round) => (
            <button
              key={round}
              type="button"
              onClick={() => setActiveRound(round)}
              className={cn(
                "px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors",
                activeRound === round
                  ? "bg-[#22c55e] text-[#0d0f12]"
                  : "text-[#64748b] hover:text-[#f1f5f9]"
              )}
            >
              {ROUND_LABELS[round]}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr,300px] gap-8">
          <div className="relative overflow-x-auto">
            <div className="flex min-w-[780px] items-stretch gap-4 min-h-[500px]">
              {displayRounds.map((round) => (
                <RoundColumn
                  key={round}
                  round={round}
                  matches={matchesByRound[round]}
                  selectedMatchId={selectedMatchId}
                  onSelectMatch={(m) => {
                    setSelectedMatchId(m.id);
                    if (m.sourceMatch?.match_id) {
                      navigate(`/matches/${m.sourceMatch.match_id}`);
                    }
                  }}
                />
              ))}
            </div>
          </div>

          <div className="space-y-6">
            {matchesByRound.final[0] && (
            <FeatureCard title="决赛" icon={Trophy} accent="border-[#eab308]/40 text-[#eab308]">
                <div className="p-4">
                  <BracketMatchCard
                    match={matchesByRound.final[0]}
                    onClick={() => {
                      const match = matchesByRound.final[0];
                      setSelectedMatchId(match.id);
                      if (match.sourceMatch?.match_id) {
                        navigate(`/matches/${match.sourceMatch.match_id}`);
                      }
                    }}
                  />
                </div>
              </FeatureCard>
            )}

            {matchesByRound.third[0] && (
              <FeatureCard title="季军赛" icon={Medal} accent="border-[#94a3b8]/30 text-[#94a3b8]">
                <div className="p-4">
                  <BracketMatchCard
                    match={matchesByRound.third[0]}
                    onClick={() => {
                      const match = matchesByRound.third[0];
                      setSelectedMatchId(match.id);
                      if (match.sourceMatch?.match_id) {
                        navigate(`/matches/${match.sourceMatch.match_id}`);
                      }
                    }}
                  />
                </div>
              </FeatureCard>
            )}

            <FeatureCard title="赛事进度" icon={Activity} accent="border-[#23262d] text-[#94a3b8]">
              <div className="p-4 space-y-3">
                {ROUND_ORDER.map((round) => {
                  const roundMatches = matchesByRound[round];
                  const finished = roundMatches.filter((m) => m.status === "finished").length;
                  const total = roundMatches.length;
                  const pct = total > 0 ? (finished / total) * 100 : 0;
                  return (
                    <div key={round}>
                      <div className="mb-1 flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-wider text-[#94a3b8]">
                          {ROUND_LABELS[round]}
                        </span>
                        <span className="font-mono text-[10px] text-[#64748b]">
                          {finished}/{total}
                        </span>
                      </div>
                      <div className="h-1 bg-[#1a1f2e]">
                        <div
                          className="h-full bg-[#22c55e] transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </FeatureCard>

            {selectedMatch && (
              <div className="border border-[#22c55e]/30 bg-[#22c55e]/5">
                <div className="px-3 py-2 border-b border-[#22c55e]/20 flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[#22c55e]">
                    当前选中
                  </span>
                  <span className="text-[10px] text-[#64748b]">{selectedMatch.stageLabel}</span>
                </div>
                <div className="p-3 space-y-2 text-xs text-[#94a3b8]">
                  <div className="flex items-center gap-2">
                    <Clock className="w-3 h-3 text-[#64748b]" />
                    <span>{formatWorldCupDateTime(selectedMatch.date, selectedMatch.venue)}</span>
                  </div>
                  <div>
                    <span className="text-[#f1f5f9]">{formatTeamName(selectedMatch.homeTeam)}</span>
                    <span className="text-[#64748b] mx-2">vs</span>
                    <span className="text-[#f1f5f9]">{formatTeamName(selectedMatch.awayTeam)}</span>
                  </div>
                  <div className="text-[10px] text-[#64748b]">
                    状态：{getStatusLabel(selectedMatch.status)}
                    {selectedMatch.sourceMatch?.group_name
                      ? ` · ${getGroupLabel(selectedMatch.sourceMatch.group_name)}`
                      : ""}
                  </div>
                  {selectedMatch.venue ? (
                    <div className="text-[10px] text-[#64748b]">场地：{selectedMatch.venue}</div>
                  ) : null}
                  {selectedMatch.status === "finished" ? (
                    <div className="border-t border-[#22c55e]/20 pt-3">
                      <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-[#22c55e]">
                        完赛摘要
                      </div>
                      <KeyEventSummary
                        events={selectedReport?.impact_summary?.key_events ?? selectedReport?.events ?? []}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
