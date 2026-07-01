import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, Filter, RotateCcw, Search } from "lucide-react";

import { getMatchReport } from "@/api/matches";
import { getWorldCupMatches } from "@/api/worldcup";
import { MatchCard } from "@/components/cards/MatchCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, LoadingState, PageHeader } from "@/components/ui/stat-card";
import { parseWorldCupMatchDate, resolveWorldCupDisplayStatus } from "@/lib/utils";
import type { Match, MatchReport, WorldCupMatch } from "@/types";

const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "scheduled", label: "未开始" },
  { value: "result_pending", label: "赛果待同步" },
  { value: "live", label: "进行中" },
  { value: "finished", label: "已结束" },
];

function toMatch(row: WorldCupMatch): Match {
  return {
    id: row.match_id,
    league_id: 6,
    matchday: undefined,
    stage: row.stage,
    group_name: row.group_name,
    date_time: row.match_date,
    match_date: row.match_date,
    home_team_id: row.home_team_id ?? 0,
    home_team_name: row.home_team,
    away_team_id: row.away_team_id ?? 0,
    away_team_name: row.away_team,
    home_score: row.home_score,
    away_score: row.away_score,
    status: row.status,
    venue: row.venue,
  };
}

function getMatchTime(match: Match): number {
  const value = match.date_time ?? match.match_date;
  if (!value) return Number.MAX_SAFE_INTEGER;

  const date = match.stage ? parseWorldCupMatchDate(value, match.venue) : new Date(value);
  const time = date?.getTime() ?? Number.MAX_SAFE_INTEGER;
  return Number.isNaN(time) ? Number.MAX_SAFE_INTEGER : time;
}

function resolveDisplayStatus(match: Match): string {
  return resolveWorldCupDisplayStatus(match.status, match.date_time ?? match.match_date, match.venue);
}

function compareMatches(a: Match, b: Match): number {
  const statusA = resolveDisplayStatus(a);
  const statusB = resolveDisplayStatus(b);
  const timeA = getMatchTime(a);
  const timeB = getMatchTime(b);

  const rank = (status: string) => {
    if (status === "live") return 0;
    if (status === "scheduled") return 1;
    if (status === "finished") return 2;
    return 3;
  };

  const rankDiff = rank(statusA) - rank(statusB);
  if (rankDiff !== 0) return rankDiff;

  if (statusA === "finished" && statusB === "finished") {
    return timeB - timeA || b.id - a.id;
  }

  return timeA - timeB || a.id - b.id;
}

function getBeijingDateKey(match: Match): string {
  const value = match.date_time ?? match.match_date;
  const date = match.stage ? parseWorldCupMatchDate(value, match.venue) : value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return "";

  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function MatchList() {
  const [filters, setFilters] = useState({
    status: "",
    date: "",
    stage: "",
  });
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 12;

  const { data: matches = [], isLoading: matchesLoading } = useQuery<Match[]>({
    queryKey: ["matches", "worldcup", 256],
    queryFn: async () => {
      const rows = await getWorldCupMatches(undefined, 256);
      return rows.map(toMatch);
    },
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const filteredMatches = useMemo(() => {
    return matches
      .filter((match) => {
        if (filters.status && resolveDisplayStatus(match) !== filters.status) return false;
        if (filters.date && getBeijingDateKey(match) !== filters.date) return false;
        if (filters.stage) {
          const stage = (match.stage ?? "").toLowerCase();
          if (!stage.includes(filters.stage.trim().toLowerCase())) return false;
        }
        return true;
      })
      .sort(compareMatches);
  }, [matches, filters.status, filters.date, filters.stage]);

  const paginatedMatches = filteredMatches.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const pageFinishedIds = useMemo(
    () => paginatedMatches.filter((match) => resolveDisplayStatus(match) === "finished").map((match) => match.id),
    [paginatedMatches]
  );

  const { data: pageReports = {} } = useQuery<Record<number, MatchReport | null>>({
    queryKey: ["match-page-reports", pageFinishedIds],
    enabled: pageFinishedIds.length > 0,
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    queryFn: async () => {
      const entries = await Promise.all(
        pageFinishedIds.map(async (matchId) => {
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

  function handleFilterChange(key: "status" | "date" | "stage", value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  }

  function handleReset() {
    setFilters({ status: "", date: "", stage: "" });
    setCurrentPage(1);
  }

  return (
    <div className="animate-fade-in">
      <PageHeader title="比赛中心" description="仅保留 2026 世界杯赛程，按北京时间查看、筛选和进入详情。" />

      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">世界杯筛选</span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Select value={filters.status} onChange={(e) => handleFilterChange("status", e.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>

            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input type="date" value={filters.date} onChange={(e) => handleFilterChange("date", e.target.value)} className="pl-9" />
            </div>

            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="阶段（小组赛 / 淘汰赛）"
                value={filters.stage}
                onChange={(e) => handleFilterChange("stage", e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          <div className="mt-3 flex justify-end">
            <Button variant="ghost" size="sm" onClick={handleReset}>
              <RotateCcw className="mr-1 h-3.5 w-3.5" />
              重置筛选
            </Button>
          </div>
        </CardContent>
      </Card>

      {matchesLoading ? (
        <LoadingState rows={6} />
      ) : filteredMatches.length === 0 ? (
        <EmptyState icon={Calendar} title="暂无比赛" description="当前筛选条件下没有找到世界杯比赛。" />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {paginatedMatches.map((match) => (
              <MatchCard
                key={match.id}
                match={{ ...match, status: resolveDisplayStatus(match) }}
                report={pageReports[match.id] ?? null}
              />
            ))}
          </div>
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(filteredMatches.length / pageSize)}
            onPageChange={setCurrentPage}
          />
        </>
      )}
    </div>
  );
}
