import { useParams, useSearchParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Brain, Calendar, CheckCircle2, Clock, ExternalLink, FileText, Flag, Loader2, MapPin, RefreshCw, Repeat, Target, TrendingUp } from "lucide-react";

import { getMatch, getMatchEvents, getMatchReport, refreshMatch } from "@/api/matches";
import { getPrediction } from "@/api/predict";
import { useLiveScore } from "@/hooks/useLiveScore";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, LoadingState, PageHeader, StatCard } from "@/components/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  cn,
  formatDateTime,
  formatWorldCupDateTime,
  getEventTypeLabel,
  getGroupLabel,
  getShotResultLabel,
  getShotTypeLabel,
  getStageLabel,
  getStatusColor,
  getStatusLabel,
  getTeamIdentity,
} from "@/lib/utils";
import type { Match, MatchEvent, MatchPredictionResponse, MatchReport } from "@/types";

function getAvailabilitySourceLabel(source?: string | null): string | null {
  if (!source) return null;
  if (source === "match_events") return "真实比赛事件";
  if (source === "match_result_summary") return "赛果派生摘要";
  if (source === "shots") return "真实射门明细";
  return source;
}

function translateDataAvailabilityNote(note?: string | null): string | null {
  if (!note) return null;
  if (note.includes("尚未采集到真实逐脚射门数据") || note.includes("当前比赛没有真实逐脚射门数据")) {
    return "当前没有真实逐脚射门数据，无法生成 xG 时间线。";
  }
  if (note.includes("缺少生成真实时间线所需的关键字段")) {
    return "已有射门记录，但缺少生成真实 xG 时间线所需的关键字段。";
  }
  if (note.includes("未纳入 xG 时间线")) {
    return note;
  }
  if (note.includes("本场比赛双方") || note.includes("主队或客队")) {
    return "已有射门记录，但暂时无法可靠归属到本场比赛双方。";
  }
  if (note.includes("no real shot rows")) {
    return "当前没有真实逐脚射门数据，无法生成 xG 时间线。";
  }
  if (note.includes("不会用估算值伪造射门列表")) {
    return "当前没有真实逐脚射门数据，射门列表保持空值，不会使用估算结果代替。";
  }
  if (note.includes("已退化为基于赛果生成的比赛摘要时间线")) {
    return "当前没有真实逐分钟事件，已改为基于赛果生成的比赛摘要时间线。";
  }
  if (note.includes("聚合报告会如实返回赛果、赛程和数据覆盖情况")) {
    return "报告会如实展示赛果、赛程和数据覆盖情况；xG 与射门只会在真实明细存在时生成。";
  }
  return note;
}

function matchTimeLabel(match: Match): string {
  const value = match.date_time ?? match.match_date;
  return match.stage ? formatWorldCupDateTime(value, match.venue) : formatDateTime(value);
}

function TeamName({ teamName, align = "left" }: { teamName?: string | null; align?: "left" | "right" }) {
  const identity = getTeamIdentity(teamName);
  const flag = identity.flagUrl ? (
    <img src={identity.flagUrl} alt={identity.displayName} className="h-full w-full object-cover" />
  ) : (
    <span className="text-sm font-bold text-muted-foreground">{identity.displayName.charAt(0) || "?"}</span>
  );
  return (
    <div className={cn("flex min-w-0 items-center gap-3", align === "right" && "justify-end")}>
      {align === "left" && <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full border border-border bg-secondary/60 flex items-center justify-center">{flag}</div>}
      <div className={cn("min-w-0", align === "right" && "text-right")}>
        <div className="truncate text-lg font-bold">{identity.displayName}</div>
      </div>
      {align === "right" && <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full border border-border bg-secondary/60 flex items-center justify-center">{flag}</div>}
    </div>
  );
}

function EventIcon({ eventType }: { eventType?: string | null }) {
  const type = (eventType || "").toLowerCase();
  if (type.includes("goal")) return <Target className="h-4 w-4 text-emerald-400" />;
  if (type.includes("card")) return <Flag className="h-4 w-4 text-amber-400" />;
  if (type.includes("substitution")) return <Repeat className="h-4 w-4 text-sky-400" />;
  return <Clock className="h-4 w-4 text-muted-foreground" />;
}

function EventTimeline({ events }: { events: MatchEvent[] }) {
  if (events.length === 0) {
    return <EmptyState icon={Clock} title="暂无事件数据" description="这场比赛当前还没有可展示的事件时间线。" />;
  }
  return (
    <div className="divide-y divide-border/50">
      {events.map((event, index) => (
        <div key={event.id ?? index} className="flex items-center gap-4 py-3">
          <div className="w-12 font-mono text-sm font-bold text-primary">{event.minute}'</div>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary/50"><EventIcon eventType={event.event_type} /></div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold">{getEventTypeLabel(event.event_type)}</div>
            <div className="text-xs text-muted-foreground">
              {event.player_name || "球员待定"}{event.team_name ? ` · ${event.team_name}` : ""}{event.detail ? ` · ${event.detail}` : ""}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ReportSummary({ report }: { report: MatchReport }) {
  const breakdown = Object.entries(report.impact_summary.event_type_breakdown || {});
  const availability = Object.entries(report.data_availability || {});
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>关键事件</CardTitle></CardHeader>
        <CardContent>
          {report.impact_summary.key_events.length === 0 ? (
            <p className="text-sm text-muted-foreground">当前没有记录到高影响事件。</p>
          ) : (
            <div className="space-y-3">
              {report.impact_summary.key_events.slice(0, 8).map((event, index) => (
                <div key={`${event.id ?? index}-${event.minute}`} className="flex items-start justify-between gap-3 border-b border-border/50 pb-3 last:border-b-0 last:pb-0">
                  <div>
                    <div className="text-sm font-medium">{event.minute}' · {getEventTypeLabel(event.event_type)}</div>
                    <div className="text-xs text-muted-foreground">{event.player_name || event.team_name || event.detail || "详情待补充"}</div>
                  </div>
                  <div className="font-mono text-sm text-primary">{event.impact_score ?? "--"}</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>事件分布</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {breakdown.length === 0 ? <p className="text-sm text-muted-foreground">当前没有可展示的事件分布。</p> : breakdown.map(([type, count]) => (
            <div key={type} className="flex items-center justify-between"><span className="text-sm text-muted-foreground">{getEventTypeLabel(type)}</span><span className="font-display text-lg font-bold">{count}</span></div>
          ))}
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader><CardTitle>数据覆盖</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {availability.length === 0 ? (
            <p className="text-sm text-muted-foreground">报告暂未返回数据覆盖说明。</p>
          ) : availability.map(([key, item]) => (
            <div key={key} className="rounded-lg border border-border/50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold">
                  {key === "events" ? "事件" : key === "shots" ? "射门" : key === "xg_timeline" ? "xG 时间线" : "聚合报告"}
                </div>
                <Badge variant={item.available ? "success" : "outline"}>{item.available ? "可用" : "降级"}</Badge>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                记录数：{item.rows ?? "--"}
                {getAvailabilitySourceLabel(item.source) ? ` · 来源：${getAvailabilitySourceLabel(item.source)}` : ""}
              </div>
              {item.note ? <div className="mt-2 text-xs text-muted-foreground">{item.note}</div> : null}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export function MatchDetail() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const matchId = id ? Number(id) : 0;
  const activeTab = searchParams.get("tab") || "overview";

  function handleTabChange(tab: string) {
    const next = new URLSearchParams(searchParams);
    if (tab === "overview") {
      next.delete("tab");
    } else {
      next.set("tab", tab);
    }
    setSearchParams(next, { replace: true });
  }

  const { data: match, isLoading: matchLoading } = useQuery<Match>({
    queryKey: ["match", matchId],
    queryFn: () => getMatch(matchId),
    enabled: !!matchId,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  // 比赛进行中时缩短事件/报告的轮询间隔，配合 WebSocket 实现近实时刷新
  const matchLive = match?.status === "live" || match?.status === "in_progress" || match?.status === "half_time";
  const liveInterval = matchLive ? 10_000 : 30_000;

  const { data: events = [], isLoading: eventsLoading } = useQuery<MatchEvent[]>({
    queryKey: ["matchEvents", matchId],
    queryFn: () => getMatchEvents(matchId),
    enabled: !!matchId,
    refetchInterval: liveInterval,
    refetchOnWindowFocus: true,
  });
  const { data: report, isLoading: reportLoading } = useQuery<MatchReport>({
    queryKey: ["matchReport", matchId],
    queryFn: () => getMatchReport(matchId),
    enabled: !!matchId,
    refetchInterval: liveInterval,
    refetchOnWindowFocus: true,
  });

  // 实时比分 WebSocket：比分变化由全局 Provider 自动合并进 ["match", matchId] 缓存，
  // 无需在此手动 refetch。此处保留订阅以确保页面在 WS 链路上保持活跃。
  useLiveScore();

  // 获取该比赛的 AI 预测数据（用于显示预测摘要卡片）
  const { data: prediction } = useQuery<MatchPredictionResponse | null>({
    queryKey: ["prediction", matchId],
    queryFn: () => getPrediction(matchId),
    enabled: !!matchId,
    staleTime: 60_000,
    retry: 1,
  });

  // 刷新比赛数据 mutation
  const queryClient = useQueryClient();
  const refreshMutation = useMutation({
    mutationFn: () => refreshMatch(matchId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["match", matchId] });
      void queryClient.invalidateQueries({ queryKey: ["matchEvents", matchId] });
      void queryClient.invalidateQueries({ queryKey: ["matchReport", matchId] });
      void queryClient.invalidateQueries({ queryKey: ["prediction", matchId] });
    },
  });

  if (!matchId) return <EmptyState icon={AlertCircle} title="比赛 ID 无效" />;
  if (matchLoading) return <LoadingState rows={8} />;
  if (!match) return <EmptyState icon={AlertCircle} title="未找到比赛" description="后端没有返回这场比赛的详情数据。" />;

  const isLive = match.status === "live" || match.status === "in_progress" || match.status === "half_time";
  const isScheduled = match.status === "scheduled";
  const hasScore = match.home_score != null && match.away_score != null;
  const xgTimeline = report?.xg_timeline;
  const shots = report?.shots?.shots ?? [];
  // xG 来源优先级：逐脚时间线（真实射门累加）> 单场汇总（Fotmob，存在 Match.home_xg/away_xg）
  const homeXgTimeline = xgTimeline?.available ? xgTimeline?.home_team?.final_xg : null;
  const awayXgTimeline = xgTimeline?.available ? xgTimeline?.away_team?.final_xg : null;
  const homeXgValue = homeXgTimeline ?? match.home_xg ?? null;
  const awayXgValue = awayXgTimeline ?? match.away_xg ?? null;
  const hasAggregateXg = match.home_xg != null || match.away_xg != null;
  const resolvedLeagueName =
    match.league_name && match.league_name !== "???"
      ? match.league_name
      : match.stage || match.group_name
        ? "世界杯"
        : "--";
  const translatedXgNote = translateDataAvailabilityNote(
    report?.data_availability?.xg_timeline?.note || xgTimeline?.note
  );
  const translatedShotNote = translateDataAvailabilityNote(report?.data_availability?.shots?.note || report?.shots?.note);
  const xgUnavailableNote = isScheduled
    ? "比赛尚未开始，开赛后才会逐步生成 xG。"
    : hasAggregateXg
      ? "基于 Fotmob 单场汇总 xG（逐脚时间线暂不可用）。"
      : translatedXgNote || "2026 世界杯暂无免费逐脚射门数据源，当前无法生成 xG。";
  const shotUnavailableNote = isScheduled
    ? "开赛后这里会展示真实射门记录。"
    : translatedShotNote || "比赛结果和事件已更新，但当前仍缺少真实逐脚射门数据，因此暂时没有射门明细和热图。";

  return (
    <div className="animate-fade-in">
      <Breadcrumb items={[{ label: "比赛中心", to: "/matches" }, { label: "比赛详情" }]} />
      <PageHeader title="比赛详情" description="查看事件时间线、xG、射门和聚合报告。" />

      {/* AI 预测摘要卡 + 刷新按钮 */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <Card className="flex-1">
          <CardContent className="p-4">
            {prediction && prediction.status === "completed" ? (
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex items-center gap-2">
                    <Brain className="h-4 w-4 text-emerald-400" />
                    <span className="text-sm font-semibold">AI 预测分析</span>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  </div>
                  <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <span>
                      胜/平/负：
                      <span className="font-mono font-bold text-foreground">
                        {Math.round(prediction.home_win_prob ?? 0)}%
                      </span>
                      {" / "}
                      <span className="font-mono font-bold text-foreground">
                        {Math.round(prediction.draw_prob ?? 0)}%
                      </span>
                      {" / "}
                      <span className="font-mono font-bold text-foreground">
                        {Math.round(prediction.away_win_prob ?? 0)}%
                      </span>
                    </span>
                    {prediction.confidence != null ? (
                      <span>
                        置信度：
                        <span className="font-mono font-bold text-emerald-400">
                          {Math.round(prediction.confidence)}%
                        </span>
                      </span>
                    ) : null}
                    {prediction.predicted_home_score != null ? (
                      <span>
                        预测比分：
                        <span className="font-mono font-bold text-foreground">
                          {prediction.predicted_home_score} : {prediction.predicted_away_score}
                        </span>
                      </span>
                    ) : null}
                  </div>
                </div>
                <Link to={`/ai-predict?match=${matchId}`}>
                  <Button variant="outline" size="sm" className="shrink-0">
                    <ExternalLink className="h-3.5 w-3.5" />
                    查看完整分析
                  </Button>
                </Link>
              </div>
            ) : isLive ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Brain className="h-4 w-4 text-muted-foreground" />
                比赛进行中，预测已锁定
              </div>
            ) : isScheduled ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="h-4 w-4 text-muted-foreground" />
                比赛未开始，开赛后可生成 AI 预测
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <AlertCircle className="h-4 w-4 text-amber-400" />
                AI 预测不可用
              </div>
            )}
          </CardContent>
        </Card>

        <Button
          variant="outline"
          size="sm"
          className="shrink-0 sm:mt-0"
          disabled={refreshMutation.isPending}
          onClick={() => refreshMutation.mutate()}
        >
          {refreshMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          {refreshMutation.isPending
            ? "刷新中..."
            : refreshMutation.isSuccess
              ? "已刷新"
              : refreshMutation.isError
                ? "刷新失败"
                : "刷新比赛数据"}
        </Button>
      </div>

      {isScheduled ? (
        <Card className="mb-6 border-primary/20 bg-primary/5">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <Flag className="mt-0.5 h-5 w-5 text-primary" />
              <div>
                <div className="text-sm font-semibold">这场比赛还未开始</div>
                <div className="mt-1 text-sm text-muted-foreground">当前只有赛前信息，事件时间线、xG、射门记录和比赛报告会在开赛后逐步出现。</div>
                <div className="mt-2 text-xs text-muted-foreground">北京时间：{matchTimeLabel(match)}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card className="mb-6 overflow-hidden">
        <CardContent className="p-0">
          <div className="bg-gradient-to-b from-primary/5 to-transparent p-6 md:p-8">
            <div className="mb-4 flex items-center justify-center gap-2">
              {match.status ? <Badge variant={isLive ? "danger" : "default"} className={isLive ? "animate-pulse" : getStatusColor(match.status)}>{getStatusLabel(match.status)}</Badge> : null}
              {match.stage ? <Badge variant="outline">{getStageLabel(match.stage)}</Badge> : null}
              {match.group_name ? <span className="text-xs text-muted-foreground">{getGroupLabel(match.group_name)}</span> : null}
            </div>
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 md:gap-8">
              <TeamName teamName={match.home_team_name} align="right" />
              <div className="flex items-center gap-3 md:gap-4">
                <span className="font-display text-4xl font-bold tabular-nums md:text-6xl">{hasScore ? match.home_score : "-"}</span>
                <span className="font-display text-2xl font-light text-muted-foreground md:text-3xl">:</span>
                <span className="font-display text-4xl font-bold tabular-nums md:text-6xl">{hasScore ? match.away_score : "-"}</span>
              </div>
              <TeamName teamName={match.away_team_name} />
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-4 border-t border-border/50 px-6 py-4 text-sm text-muted-foreground md:gap-6">
            <span className="flex items-center gap-1.5"><Calendar className="h-4 w-4" />北京时间 {matchTimeLabel(match)}</span>
            {match.venue ? <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4" />{match.venue}</span> : null}
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="events">事件</TabsTrigger>
          <TabsTrigger value="xg">xG 时间线</TabsTrigger>
          <TabsTrigger value="shots">射门</TabsTrigger>
          <TabsTrigger value="report">报告</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard title="主队 xG" value={homeXgValue != null ? homeXgValue.toFixed(2) : "--"} icon={TrendingUp} description={xgTimeline?.available ? "基于真实逐脚射门生成" : hasAggregateXg ? "基于 Fotmob 单场汇总 xG" : xgUnavailableNote} />
            <StatCard title="客队 xG" value={awayXgValue != null ? awayXgValue.toFixed(2) : "--"} icon={TrendingUp} description={xgTimeline?.available ? "基于真实逐脚射门生成" : hasAggregateXg ? "基于 Fotmob 单场汇总 xG" : xgUnavailableNote} />
            <StatCard title="联赛" value={resolvedLeagueName} icon={FileText} />
            <StatCard title="赛季" value={match.season ?? "--"} icon={Calendar} />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-[1.25fr_1fr]">
            <Card>
              <CardHeader>
                <CardTitle>比赛摘要</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {eventsLoading ? (
                  <LoadingState rows={4} />
                ) : report?.impact_summary?.key_events?.length ? (
                  report.impact_summary.key_events.slice(0, 5).map((event, index) => (
                    <div
                      key={`${event.id ?? index}-${event.minute}`}
                      className="flex items-start justify-between gap-3 border-b border-border/50 pb-3 last:border-b-0 last:pb-0"
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium">
                          {event.minute}' · {getEventTypeLabel(event.event_type)}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {event.detail || event.player_name || event.team_name || "摘要补充中"}
                        </div>
                      </div>
                      <span className="font-mono text-sm text-primary">{event.impact_score ?? "--"}</span>
                    </div>
                  ))
                ) : (
                  <EmptyState
                    icon={Clock}
                    title="暂无比赛摘要"
                    description="比赛摘要会优先展示关键事件和影响较大的赛况变化。"
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>数据可用性</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(report?.data_availability || {}).slice(0, 4).map(([key, item]) => (
                  <div key={key} className="rounded-lg border border-border/50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">
                        {key === "events" ? "事件" : key === "shots" ? "射门" : key === "xg_timeline" ? "xG 时间线" : "聚合报告"}
                      </div>
                      <Badge variant={item.available ? "success" : "outline"}>
                        {item.available ? "可用" : "降级"}
                      </Badge>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      记录数：{item.rows ?? "--"}
                      {getAvailabilitySourceLabel(item.source) ? ` · 来源：${getAvailabilitySourceLabel(item.source)}` : ""}
                    </div>
                    {item.note ? (
                      <div className="mt-2 text-xs text-muted-foreground">
                        {translateDataAvailabilityNote(item.note) || item.note}
                      </div>
                    ) : null}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="events">
          <Card><CardContent className="p-5">{eventsLoading ? <LoadingState rows={6} /> : <EventTimeline events={events} />}</CardContent></Card>
        </TabsContent>

        <TabsContent value="xg">
          <Card>
            <CardHeader><CardTitle>xG 时间线</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {reportLoading ? <LoadingState rows={4} /> : !xgTimeline ? <EmptyState icon={TrendingUp} title="暂无 xG 数据" description="比赛报告没有返回 xG 时间线对象。" /> : (
                <>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <StatCard title="可用状态" value={xgTimeline.available ? "可用" : "不可用"} icon={TrendingUp} />
                    <StatCard title="射门数" value={xgTimeline.shot_count} icon={Target} />
                    <StatCard title="时间线节点" value={(xgTimeline.timeline.home?.length ?? 0) + (xgTimeline.timeline.away?.length ?? 0)} icon={Clock} />
                  </div>
                  {xgTimeline.available ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      {(["home", "away"] as const).map((side) => (
                        <div key={side} className="rounded-lg border border-border/50 p-4">
                          <div className="mb-2 text-sm font-medium">{side === "home" ? "主队推进" : "客队推进"}</div>
                          {(xgTimeline.timeline[side] ?? []).length === 0 ? <p className="text-sm text-muted-foreground">暂无 xG 节点。</p> : (xgTimeline.timeline[side] ?? []).map((point, index) => (
                            <div key={`${side}-${index}`} className="flex items-center justify-between text-sm"><span>{point.minute}' · {getShotResultLabel(point.result)}</span><span className="font-mono">{point.cumulative_xg.toFixed(2)}</span></div>
                          ))}
                        </div>
                      ))}
                    </div>
                  ) : hasAggregateXg ? (
                    <div className="rounded-lg border border-border/50 p-4">
                      <div className="mb-2 text-sm font-medium">单场 xG 汇总</div>
                      <div className="flex items-center justify-between text-lg">
                        <span className="text-muted-foreground">主 {xgTimeline?.home_team?.name ?? "主队"}</span>
                        <span className="font-mono font-semibold tabular-nums">{homeXgValue != null ? homeXgValue.toFixed(2) : "--"} : {awayXgValue != null ? awayXgValue.toFixed(2) : "--"}</span>
                        <span className="text-muted-foreground">{xgTimeline?.away_team?.name ?? "客队"} 客</span>
                      </div>
                      <div className="mt-3 text-xs text-muted-foreground">基于 Fotmob 单场汇总 xG。逐脚射门时间线暂无免费数据源（FBref 2026 年 1 月下线 xG，Understat/StatsBomb 不覆盖 2026 世界杯）。</div>
                    </div>
                  ) : <div className="rounded-lg border border-border/50 p-4 text-sm text-muted-foreground">{xgUnavailableNote}</div>}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shots">
          <Card>
            <CardHeader><CardTitle>射门记录</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {reportLoading ? <LoadingState rows={4} /> : shots.length === 0 ? <EmptyState icon={Target} title={isScheduled ? "比赛尚未开始" : "暂无射门数据"} description={shotUnavailableNote} /> : shots.map((shot, index) => (
                <div key={`${shot.id ?? index}-${shot.minute}`} className="flex items-center justify-between rounded-lg border border-border/50 px-4 py-3">
                  <div><div className="text-sm font-medium">{shot.minute}' · {shot.player_name || "球员待定"}</div><div className="text-xs text-muted-foreground">{shot.team_name || "球队待定"} · {getShotTypeLabel(shot.shot_type)} · {getShotResultLabel(shot.result)}</div></div>
                  <div className="font-mono text-sm text-primary">xG {shot.xg?.toFixed(2) ?? "--"}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="report">
          {reportLoading ? <LoadingState rows={5} /> : report ? <ReportSummary report={report} /> : <EmptyState icon={FileText} title="暂无报告" description="比赛报告数据暂未返回。" />}
        </TabsContent>
      </Tabs>
    </div>
  );
}
