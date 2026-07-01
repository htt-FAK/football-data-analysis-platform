import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Calendar,
  Crosshair,
  MapPin,
  Shield,
  Target,
  TrendingUp,
  User,
  Zap,
} from "lucide-react";

import { getTeam, getTeamRadar, getTeamShots, getTeamStats } from "@/api/teams";
import { RadarChart } from "@/components/charts/RadarChart";
import type { RadarSeries } from "@/components/charts/RadarChart";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, LoadingState, PageHeader, StatCard } from "@/components/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatNumber, getRadarDimensionLabels, getShotResultLabel, getTeamIdentity } from "@/lib/utils";
import type { RadarData, Shot, Team, TeamStat } from "@/types";

function getFriendlyField(value?: string | number | null, fallback = "资料补充中"): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "number") return String(value);
  return value.trim() || fallback;
}

export function TeamDetail() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const teamId = id ? parseInt(id, 10) : 0;
  const rawTab = searchParams.get("tab") || "overview";
  const activeTab = rawTab === "shots" ? "heatmap" : rawTab;

  function handleTabChange(tab: string) {
    const next = new URLSearchParams(searchParams);
    if (tab === "overview") {
      next.delete("tab");
    } else {
      next.set("tab", tab === "heatmap" ? "shots" : tab);
    }
    setSearchParams(next, { replace: true });
  }

  const { data: team, isLoading: teamLoading } = useQuery<Team>({
    queryKey: ["team", teamId],
    queryFn: () => getTeam(teamId),
    enabled: !!teamId,
  });

  const { data: stats, isLoading: statsLoading } = useQuery<TeamStat>({
    queryKey: ["teamStats", teamId],
    queryFn: () => getTeamStats(teamId),
    enabled: !!teamId,
  });

  const { data: radar, isLoading: radarLoading } = useQuery<RadarData>({
    queryKey: ["teamRadar", teamId],
    queryFn: () => getTeamRadar(teamId),
    enabled: !!teamId,
  });

  const { data: shots = [], isLoading: shotsLoading } = useQuery<Shot[]>({
    queryKey: ["teamShots", teamId],
    queryFn: () => getTeamShots(teamId),
    enabled: !!teamId,
  });

  if (teamLoading) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="球队详情" description="查看球队档案、赛季统计、雷达画像和射门数据。" />
        <LoadingState rows={8} />
      </div>
    );
  }

  if (!team) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="球队详情" description="查看球队档案、赛季统计、雷达画像和射门数据。" />
        <EmptyState
          icon={Shield}
          title="未找到球队"
          description="后端没有返回这支球队的详情数据。"
        />
      </div>
    );
  }

  const firstLetter = team.name ? team.name.charAt(0).toUpperCase() : "?";
  const identity = getTeamIdentity(team.name);
  const titleLabel = identity.displayName || team.name || "球队详情";
  const originalName = identity.countryLabel ? null : identity.originalName && identity.originalName !== identity.displayName
    ? identity.originalName
    : team.name !== titleLabel
      ? team.name
      : null;

  const shotSummary = {
    total: stats?.shots ?? stats?.shots_total ?? 0,
    onTarget: stats?.shots_on_target ?? stats?.shots_on_target_total ?? 0,
    xg: stats?.xg ?? 0,
  };

  return (
    <div className="animate-fade-in">
      <Breadcrumb items={[{ label: "球队中心", to: "/teams" }, { label: titleLabel }]} />
      <PageHeader title={titleLabel} description="查看球队资料、赛季表现、能力雷达和真实射门记录。">
        {identity.countryLabel ? (
          <Badge variant="outline" className="gap-1.5 text-sm">
            <MapPin className="h-3.5 w-3.5" />
            {identity.countryLabel}
          </Badge>
        ) : null}
      </PageHeader>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <Card className="glass-card">
            <CardContent className="p-6">
              <div className="flex flex-col items-center text-center">
                <div className="mb-4 flex h-24 w-24 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 text-3xl font-display font-bold text-primary">
                  {identity.flagUrl ? (
                    <img
                      src={identity.flagUrl}
                      alt={identity.countryLabel || titleLabel}
                      className="h-14 w-20 rounded-lg object-cover shadow-sm"
                    />
                  ) : (
                    firstLetter
                  )}
                </div>
                <h2 className="font-display text-xl font-bold">{titleLabel}</h2>
                {originalName ? <p className="mt-1 text-sm text-muted-foreground">{originalName}</p> : null}
                {!identity.countryLabel && team.full_name && team.full_name !== team.name && team.full_name !== titleLabel ? (
                  <p className="mt-1 text-sm text-muted-foreground">{team.full_name}</p>
                ) : null}
              </div>

              <div className="mt-6 space-y-4">
                {identity.countryLabel ? <InfoRow icon={MapPin} label="国家" value={identity.countryLabel} /> : null}
                <InfoRow icon={Calendar} label="成立年份" value={getFriendlyField(team.founded)} />
                <InfoRow icon={Shield} label="主场" value={getFriendlyField(team.venue)} />
                <InfoRow icon={User} label="主教练" value={getFriendlyField(team.coach)} />
              </div>

              {stats && stats.stats !== null ? (
                <div className="mt-6 border-t border-border/50 pt-6">
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div>
                      <p className="font-display text-2xl font-bold text-emerald-400">{stats.wins ?? 0}</p>
                      <p className="mt-1 text-xs text-muted-foreground">胜</p>
                    </div>
                    <div>
                      <p className="font-display text-2xl font-bold text-muted-foreground">{stats.draws ?? 0}</p>
                      <p className="mt-1 text-xs text-muted-foreground">平</p>
                    </div>
                    <div>
                      <p className="font-display text-2xl font-bold text-rose-400">{stats.losses ?? 0}</p>
                      <p className="mt-1 text-xs text-muted-foreground">负</p>
                    </div>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList className="w-full">
              <TabsTrigger value="overview" className="flex-1 gap-2">
                <Activity className="h-4 w-4" />
                概览
              </TabsTrigger>
              <TabsTrigger value="stats" className="flex-1 gap-2">
                <TrendingUp className="h-4 w-4" />
                赛季统计
              </TabsTrigger>
              <TabsTrigger value="radar" className="flex-1 gap-2">
                <Zap className="h-4 w-4" />
                雷达
              </TabsTrigger>
              <TabsTrigger value="heatmap" className="flex-1 gap-2">
                <Target className="h-4 w-4" />
                射门
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              {statsLoading ? (
                <LoadingState rows={5} />
              ) : !stats || stats.stats === null ? (
                <EmptyState
                  icon={Activity}
                  title="暂无赛季统计"
                  description="后端暂未返回这支球队的赛季统计。"
                />
              ) : (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <StatCard title="比赛场次" value={stats.matches_played ?? 0} icon={Calendar} />
                  <StatCard title="进球" value={stats.goals_for ?? 0} icon={Target} />
                  <StatCard title="失球" value={stats.goals_against ?? 0} icon={Activity} />
                  <StatCard
                    title="胜率"
                    value={`${stats.matches_played ? Math.round(((stats.wins ?? 0) / stats.matches_played) * 100) : 0}%`}
                    icon={TrendingUp}
                  />
                  <StatCard title="零封" value={stats.clean_sheets ?? 0} icon={Shield} />
                  <StatCard title="射门" value={stats.shots ?? 0} icon={Crosshair} />
                </div>
              )}
            </TabsContent>

            <TabsContent value="stats">
              {statsLoading ? (
                <LoadingState rows={6} />
              ) : !stats || stats.stats === null ? (
                <EmptyState
                  icon={TrendingUp}
                  title="暂无详细统计"
                  description="后端暂未返回这支球队的结构化赛季统计。"
                />
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="grid grid-cols-1 divide-y divide-border/50 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
                      <div className="space-y-4 p-5">
                        <h3 className="flex items-center gap-2 text-sm font-semibold">
                          <Target className="h-4 w-4 text-emerald-400" />
                          进攻
                        </h3>
                        <StatRow label="进球" value={stats.goals_for ?? 0} />
                        <StatRow label="xG" value={formatNumber(stats.xg)} />
                        <StatRow label="射门" value={stats.shots ?? 0} />
                        <StatRow label="射正" value={stats.shots_on_target ?? 0} />
                        <StatRow label="角球" value={stats.corners ?? 0} />
                        {stats.attack_score != null ? (
                          <StatRow label="进攻评分" value={formatNumber(stats.attack_score, 0)} highlight />
                        ) : null}
                      </div>
                      <div className="space-y-4 p-5">
                        <h3 className="flex items-center gap-2 text-sm font-semibold">
                          <Shield className="h-4 w-4 text-sky-400" />
                          防守
                        </h3>
                        <StatRow label="失球" value={stats.goals_against ?? 0} />
                        <StatRow label="xGA" value={formatNumber(stats.xga)} />
                        <StatRow label="零封" value={stats.clean_sheets ?? 0} />
                        <StatRow label="犯规" value={stats.fouls ?? 0} />
                        <StatRow label="红牌" value={stats.red_cards ?? 0} />
                        {stats.defense_score != null ? (
                          <StatRow label="防守评分" value={formatNumber(stats.defense_score, 0)} highlight />
                        ) : null}
                      </div>
                    </div>
                    <div className="border-t border-border/50 p-5">
                      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold">
                        <Activity className="h-4 w-4 text-accent" />
                        控球与传球
                      </h3>
                      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        <MiniStat label="控球率" value={`${stats.possession ?? 0}%`} />
                        <MiniStat label="传球" value={stats.passes ?? 0} />
                        <MiniStat label="传球成功率" value={`${stats.pass_accuracy ?? 0}%`} />
                        {stats.overall_score != null ? (
                          <MiniStat label="总评" value={formatNumber(stats.overall_score, 0)} highlight />
                        ) : null}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="radar">
              {radarLoading ? (
                <LoadingState rows={4} />
              ) : !radar || !radar.dimensions || radar.dimensions.length === 0 ? (
                <EmptyState
                  icon={Zap}
                  title="暂无雷达数据"
                  description="后端暂未返回这支球队的雷达画像。"
                />
              ) : (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">攻防雷达</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const radarSeries: RadarSeries[] = [
                        {
                          name: titleLabel,
                          values: radar.values,
                          color: "hsl(142, 71%, 45%)",
                        },
                      ];

                      const radarDimensions = getRadarDimensionLabels(radar.dimensions);

                      return (
                        <RadarChart
                          dimensions={radarDimensions}
                          series={radarSeries}
                          max={100}
                          height={380}
                        />
                      );
                    })()}
                    <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {getRadarDimensionLabels(radar.dimensions).map((dimension, index) => (
                        <div
                          key={`${dimension}-${index}`}
                          className="rounded-lg border border-border/50 bg-muted/20 px-4 py-3"
                        >
                          <div className="text-xs text-muted-foreground">{dimension}</div>
                          <div className="mt-1 font-display text-lg font-semibold">
                            {formatNumber(radar.values[index] ?? 0, 0)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="heatmap">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">球队射门</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <MiniStat label="总射门" value={shotSummary.total} highlight={shotSummary.total > 0} />
                    <MiniStat label="射正" value={shotSummary.onTarget} highlight={shotSummary.onTarget > 0} />
                    <MiniStat label="累计 xG" value={formatNumber(shotSummary.xg)} highlight={shotSummary.xg > 0} />
                  </div>
                  {shotsLoading ? (
                    <LoadingState rows={4} />
                  ) : shots.length === 0 ? (
                    <EmptyState
                      icon={Crosshair}
                      title={shotSummary.total > 0 ? "暂无逐脚射门明细" : "暂无射门记录"}
                      description={
                        shotSummary.total > 0
                          ? "当前本地后端已有球队汇总射门统计，但还没有逐脚射门坐标明细；如果要展示热图和点位列表，还需要继续补 Shot 明细采集链路。"
                          : "后端当前返回了真实的空射门结果集。"
                      }
                    />
                  ) : (
                    shots.map((shot, index) => (
                      <div
                        key={`${shot.id ?? index}-${shot.match_id}-${shot.minute}`}
                        className="flex items-center justify-between rounded-lg border border-border/50 px-4 py-3"
                      >
                        <div>
                          <div className="text-sm font-medium">比赛 {shot.match_id} · {shot.minute}'</div>
                          <div className="text-xs text-muted-foreground">
                            {shot.player_name || "未知球员"} · {getShotResultLabel(shot.result)}
                            {shot.situation ? ` · ${shot.situation}` : ""}
                          </div>
                        </div>
                        <div className="text-right text-sm">
                          <div className="font-mono">xG {shot.xg?.toFixed(2) ?? "--"}</div>
                          <div className="text-xs text-muted-foreground">
                            ({shot.x}, {shot.y})
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary/50">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="truncate text-sm font-medium">{value}</p>
      </div>
    </div>
  );
}

function StatRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`font-display font-semibold ${highlight ? "text-lg text-primary" : ""}`}>
        {value}
      </span>
    </div>
  );
}

function MiniStat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="text-center">
      <p className={`font-display font-bold ${highlight ? "text-2xl text-primary" : "text-xl"}`}>
        {value}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
