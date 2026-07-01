import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Calendar, ChevronRight, Globe, TrendingUp, Trophy } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, LoadingState, PageHeader } from "@/components/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MatchCard } from "@/components/cards/MatchCard";
import { getLeague, getLeagueSchedule, getLeagueStandings, getLeagueTrends } from "@/api/leagues";
import { formatDateTime, getQualificationStatusLabel } from "@/lib/utils";
import type {
  League,
  LeagueTrendEntry,
  LeagueTrendsResponse,
  Match,
  StandingsEntry,
} from "@/types";

export function LeagueDetail() {
  const { id } = useParams<{ id: string }>();
  const leagueId = id ? parseInt(id, 10) : 0;
  const [activeTab, setActiveTab] = useState("standings");

  const { data: league, isLoading: leagueLoading } = useQuery<League>({
    queryKey: ["league", leagueId],
    queryFn: () => getLeague(leagueId),
    enabled: !!leagueId,
  });

  const { data: standings = [], isLoading: standingsLoading } = useQuery<StandingsEntry[]>({
    queryKey: ["leagueStandings", leagueId],
    queryFn: () => getLeagueStandings(leagueId),
    enabled: !!leagueId,
  });

  const { data: schedule = [], isLoading: scheduleLoading } = useQuery<Match[]>({
    queryKey: ["leagueSchedule", leagueId],
    queryFn: () => getLeagueSchedule(leagueId),
    enabled: !!leagueId,
  });

  const { data: trends, isLoading: trendsLoading } = useQuery<LeagueTrendsResponse>({
    queryKey: ["leagueTrends", leagueId],
    queryFn: () => getLeagueTrends(leagueId),
    enabled: !!leagueId,
  });

  const scheduleByMatchday = useMemo(() => {
    const grouped: Record<number, Match[]> = {};
    schedule.forEach((match) => {
      const matchday = match.matchday ?? 0;
      if (!grouped[matchday]) {
        grouped[matchday] = [];
      }
      grouped[matchday].push(match);
    });

    return Object.entries(grouped)
      .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
      .map(([matchday, matches]) => ({ matchday: parseInt(matchday, 10), matches }));
  }, [schedule]);

  if (leagueLoading) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="联赛详情" description="查看积分榜、赛程安排和积分走势。" />
        <LoadingState rows={5} />
      </div>
    );
  }

  if (!league) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="联赛详情" description="查看积分榜、赛程安排和积分走势。" />
        <EmptyState
          icon={Trophy}
          title="未找到联赛"
          description="后端没有返回这个联赛的详情数据。"
        />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <Breadcrumb items={[{ label: "联赛中心", to: "/leagues" }, { label: league.name }]} />
      <PageHeader
        title={league.name}
        description="查看当前联赛的分组积分榜、比赛赛程与累计积分趋势。"
      >
        {league.country ? (
          <Badge variant="outline" className="gap-1.5 text-sm">
            <Globe className="h-3.5 w-3.5" />
            {league.country}
          </Badge>
        ) : null}
      </PageHeader>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="standings" className="gap-2">
            <Trophy className="h-4 w-4" />
            积分榜
          </TabsTrigger>
          <TabsTrigger value="schedule" className="gap-2">
            <Calendar className="h-4 w-4" />
            赛程
          </TabsTrigger>
          <TabsTrigger value="trends" className="gap-2">
            <TrendingUp className="h-4 w-4" />
            趋势
          </TabsTrigger>
        </TabsList>

        <TabsContent value="standings">
          {standingsLoading ? (
            <LoadingState rows={10} />
          ) : standings.length === 0 ? (
            <EmptyState
              icon={Trophy}
              title="暂无积分榜数据"
              description="后端暂时没有返回这个联赛的积分榜记录。"
            />
          ) : (
            <StandingsSection standings={standings} />
          )}
        </TabsContent>

        <TabsContent value="schedule">
          {scheduleLoading ? (
            <LoadingState rows={8} />
          ) : scheduleByMatchday.length === 0 ? (
            <EmptyState
              icon={Calendar}
              title="暂无赛程数据"
              description="后端暂时没有返回这个联赛的比赛安排。"
            />
          ) : (
            <div className="space-y-6">
              {scheduleByMatchday.map(({ matchday, matches }) => (
                <div key={matchday}>
                  <div className="mb-3 flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                      比赛日 {matchday}
                    </Badge>
                    <div className="h-px flex-1 bg-border/50" />
                  </div>
                  <div className="grid gap-3">
                    {matches.map((match) => (
                      <MatchCard key={match.id} match={match} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="trends">
          {trendsLoading ? (
            <LoadingState rows={8} />
          ) : !trends || trends.trends.length === 0 ? (
            <EmptyState
              icon={TrendingUp}
              title="暂无趋势数据"
              description="后端暂时没有返回累计积分趋势数据。"
            />
          ) : (
            <LeagueTrendsView trends={trends.trends} note={trends.note} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StandingsSection({ standings }: { standings: StandingsEntry[] }) {
  const grouped = standings.reduce<Record<string, StandingsEntry[]>>((acc, entry) => {
    const key = entry.group_name || entry.stage || "总榜";
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(entry);
    return acc;
  }, {});

  const groups = Object.keys(grouped).sort();

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <Card key={group}>
          <CardHeader>
            <CardTitle className="text-base">{group}</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <StandingsTable standings={grouped[group]} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function StandingsTable({ standings }: { standings: StandingsEntry[] }) {
  const sorted = [...standings].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

  const getPositionStyle = (pos: number | undefined) => {
    if (!pos) return "";
    if (pos <= 2) return "bg-emerald-500/20 text-emerald-400";
    if (pos === 3) return "bg-sky-500/20 text-sky-400";
    return "bg-secondary text-muted-foreground";
  };

  return (
    <table className="data-table w-full">
      <thead>
        <tr>
          <th className="w-12 text-center">#</th>
          <th>球队</th>
          <th className="w-12 text-center">P</th>
          <th className="w-12 text-center">W</th>
          <th className="w-12 text-center">D</th>
          <th className="w-12 text-center">L</th>
          <th className="w-16 text-center">GF</th>
          <th className="w-16 text-center">GA</th>
          <th className="w-14 text-center">GD</th>
          <th className="w-14 text-center">Pts</th>
          <th className="w-10"></th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((entry) => (
          <tr key={entry.team_id} className="group transition-colors hover:bg-secondary/30">
            <td className="text-center">
              <span
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${getPositionStyle(entry.position)}`}
              >
                {entry.position}
              </span>
            </td>
            <td>
              <Link
                to={`/teams/${entry.team_id}`}
                className="flex items-center gap-2 font-semibold transition-colors group-hover:text-primary"
              >
                {entry.team_name}
                {entry.qualification_status ? (
                  <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                    {getQualificationStatusLabel(entry.qualification_status)}
                  </Badge>
                ) : null}
              </Link>
            </td>
            <td className="text-center font-medium">{entry.played ?? 0}</td>
            <td className="text-center font-medium text-emerald-400">{entry.wins ?? 0}</td>
            <td className="text-center font-medium text-muted-foreground">{entry.draws ?? 0}</td>
            <td className="text-center font-medium text-rose-400">{entry.losses ?? 0}</td>
            <td className="text-center font-medium">{entry.goals_for ?? 0}</td>
            <td className="text-center font-medium text-muted-foreground">
              {entry.goals_against ?? 0}
            </td>
            <td
              className={`text-center font-medium ${
                (entry.goal_diff ?? 0) > 0
                  ? "text-emerald-400"
                  : (entry.goal_diff ?? 0) < 0
                    ? "text-rose-400"
                    : ""
              }`}
            >
              {entry.goal_diff != null
                ? entry.goal_diff > 0
                  ? `+${entry.goal_diff}`
                  : entry.goal_diff
                : 0}
            </td>
            <td className="text-center">
              <span className="font-display text-lg font-bold text-primary">
                {entry.points ?? 0}
              </span>
            </td>
            <td>
              <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 transition-colors group-hover:text-primary group-hover:opacity-100" />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LeagueTrendsView({
  trends,
  note,
}: {
  trends: LeagueTrendEntry[];
  note?: string;
}) {
  const sorted = [...trends].sort((a, b) => {
    if ((a.group || "") !== (b.group || "")) {
      return (a.group || "").localeCompare(b.group || "");
    }
    return (a.position ?? 99) - (b.position ?? 99);
  });

  return (
    <div className="space-y-4">
      {note ? <p className="text-sm text-muted-foreground">{note}</p> : null}

      {sorted.map((entry) => (
        <Card key={entry.team_id}>
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-3 text-base">
              <span className="flex flex-wrap items-center gap-2">
                <span>{entry.team_name}</span>
                {entry.group ? (
                  <span className="text-sm font-normal text-muted-foreground">{entry.group}</span>
                ) : null}
              </span>
              <Badge variant="outline">{entry.current_points} 分 · 第 {entry.position ?? "--"} 名</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <TrendMiniStat label="场次" value={entry.played ?? 0} />
              <TrendMiniStat label="近期战绩" value={entry.form ?? "--"} />
              <TrendMiniStat label="净胜球" value={entry.goal_diff ?? 0} />
              <TrendMiniStat label="进球" value={entry.goals_for ?? 0} />
              <TrendMiniStat label="失球" value={entry.goals_against ?? 0} />
            </div>

            <div className="space-y-2">
              {entry.points_timeline.map((point, index) => (
                <div
                  key={`${entry.team_id}-${point.match_id}-${index}`}
                  className="flex items-center justify-between rounded-lg border border-border/50 px-4 py-3 text-sm"
                >
                  <div>
                    <div className="font-medium">比赛日 {point.matchday ?? "--"}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatDateTime(point.match_date)}
                    </div>
                  </div>
                  <div className="font-display text-lg font-bold text-primary">{point.points} 分</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TrendMiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-secondary/30 px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="font-display text-lg font-bold">{value}</div>
    </div>
  );
}
