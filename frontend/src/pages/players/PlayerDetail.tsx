import { useParams, Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Calendar,
  MapPin,
  Ruler,
  Weight,
  Trophy,
  Target,
  Activity,
  User,
  AlertCircle,
  Shield,
  Zap,
  Crosshair,
  TrendingUp,
  Shirt,
  Clock,
  Flag,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  PageHeader,
  SectionHeader,
  StatCard,
  LoadingState,
  EmptyState,
} from "@/components/ui/stat-card";
import { RadarChart } from "@/components/charts/RadarChart";
import type { RadarSeries } from "@/components/charts/RadarChart";
import {
  getPlayer,
  getPlayerStats,
  getPlayerRadar,
  getPlayerPositionRank,
  getPositionStats,
} from "@/api/players";
import {
  getPlayerPhoto,
  handleImageError,
  getPositionLabel,
  getPositionColor,
  getPlayerNameLabel,
  formatDate,
  formatNumber,
  getCountryLabel,
  getRadarDimensionLabels,
  getTeamIdentity,
  cn,
} from "@/lib/utils";
import type { Player, PlayerStat, RadarData, PositionStats } from "@/types";
import {
  getPositionConfig,
  getPositionDimensions,
  getPlayerPositionValues,
} from "@/lib/position-dimensions";

function buildFallbackRadar(player: Player): { dimensions: string[]; values: number[] } {
  return {
    dimensions: getPositionDimensions(player.position),
    values: getPlayerPositionValues(player, player.position),
  };
}

const dimensionLabelMap: Record<string, string> = (() => {
  const map: Record<string, string> = {};
  (["GK", "DF", "MF", "FW"] as const).forEach((key) => {
    getPositionConfig(key).dimensions.forEach((d) => {
      map[d.field as string] = d.label;
    });
  });
  return map;
})();

function getRatingColor(rating: number | undefined): string {
  if (!rating) return "text-slate-400";
  if (rating >= 85) return "text-rose-400";
  if (rating >= 80) return "text-amber-400";
  if (rating >= 75) return "text-emerald-400";
  if (rating >= 70) return "text-sky-400";
  return "text-slate-400";
}

function getRatingBg(rating: number | undefined): string {
  if (!rating) return "from-slate-600/30 to-slate-800/30 border-slate-600/30";
  if (rating >= 85) return "from-rose-500/20 to-rose-700/10 border-rose-500/30";
  if (rating >= 80) return "from-amber-500/20 to-amber-700/10 border-amber-500/30";
  if (rating >= 75) return "from-emerald-500/20 to-emerald-700/10 border-emerald-500/30";
  if (rating >= 70) return "from-sky-500/20 to-sky-700/10 border-sky-500/30";
  return "from-slate-500/20 to-slate-700/10 border-slate-500/30";
}

function PlayerInfoPanel({ player }: { player: Player }) {
  const rating = player.overall_rating ?? 0;
  const teamIdentity = getTeamIdentity(player.team_name);
  const displayName = getPlayerNameLabel(player.name, player.full_name);
  const originalName =
    player.full_name && player.full_name !== player.name
      ? player.full_name
      : !/[\u4e00-\u9fff]/.test(player.name)
        ? player.name
        : "";
  return (
    <Card className="overflow-hidden">
      <div className="relative h-32 bg-gradient-to-br from-primary/10 via-accent/5 to-transparent">
        <div className="absolute inset-0 bg-dots opacity-30" />
      </div>
      <CardContent className="relative -mt-16 pt-0 px-6 pb-6">
        <div className="flex flex-col items-center text-center">
          <img
            src={getPlayerPhoto(player.photo_url)}
            alt={displayName}
            className="w-32 h-32 rounded-2xl object-cover object-[center_8%] border-4 border-card shadow-xl bg-secondary"
            onError={handleImageError}
          />
          <h2 className="mt-4 text-2xl font-bold font-display tracking-tight">
            {displayName}
          </h2>
          {originalName && originalName !== displayName && (
            <p className="text-sm text-muted-foreground mt-0.5">{originalName}</p>
          )}
          <div className="flex items-center gap-2 mt-3">
            {player.position && (
              <Badge className={getPositionColor(player.position)}>
                {getPositionLabel(player.position)}
              </Badge>
            )}
            {player.jersey_number != null && (
              <Badge variant="outline">
                <Shirt className="w-3 h-3 mr-1" />
                {player.jersey_number}号
              </Badge>
            )}
          </div>
        </div>

        <div className={cn(
          "mt-6 mx-auto w-36 h-36 rounded-full flex items-center justify-center",
          "bg-gradient-to-br border-2",
          getRatingBg(rating),
        )}>
          <div className="text-center">
            <div className={cn("font-display text-5xl font-bold tabular-nums", getRatingColor(rating))}>
              {rating || "--"}
            </div>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground mt-1">
              总评
            </div>
          </div>
        </div>

        <div className="mt-6 space-y-3">
          {player.nationality && (
            <InfoItem icon={MapPin} label="国籍" value={getCountryLabel(player.nationality)} />
          )}
          {player.birth_date && (
            <InfoItem icon={Calendar} label="出生日期" value={formatDate(player.birth_date)} />
          )}
          {player.height_cm != null && (
            <InfoItem icon={Ruler} label="身高" value={`${player.height_cm} cm`} />
          )}
          {player.weight_kg != null && (
            <InfoItem icon={Weight} label="体重" value={`${player.weight_kg} kg`} />
          )}
        </div>

        {player.team_id && player.team_name && (
          <div className="mt-6 pt-5 border-t border-border/50">
            <Link
              to={`/teams/${player.team_id}`}
              className="group flex items-center gap-3 p-3 rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                <Trophy className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-muted-foreground">所属球队</div>
                <div className="font-semibold text-sm truncate group-hover:text-primary transition-colors">
                  {teamIdentity.displayName}
                </div>
              </div>
              <ArrowLeft className="w-4 h-4 text-muted-foreground rotate-180 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function InfoItem({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-secondary/50 flex items-center justify-center flex-shrink-0">
        <Icon className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="flex-1">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-sm font-medium">{value}</div>
      </div>
    </div>
  );
}

function StatGridSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

function PlayerDetailSkeleton() {
  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <Skeleton className="h-10 w-48 rounded-lg mb-2" />
        <Skeleton className="h-5 w-72 rounded-lg" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
        <div>
          <Skeleton className="h-[600px] rounded-xl" />
        </div>
        <div>
          <Skeleton className="h-10 w-80 rounded-lg mb-6" />
          <StatGridSkeleton />
        </div>
      </div>
    </div>
  );
}

function OverviewTab({ player, stats }: { player: Player; stats?: PlayerStat }) {
  const teamIdentity = getTeamIdentity(player.team_name);
  const summaryCards = [
    { label: "所属球队", value: teamIdentity.displayName || "资料补充中" },
    { label: "小组", value: player.group_name ? player.group_name.replace(/^Group\s+/i, "") + "组" : "--" },
    { label: "球衣号码", value: player.jersey_number != null ? `${player.jersey_number}号` : "--" },
    { label: "综合评分", value: player.overall_rating != null ? formatNumber(player.overall_rating, 2) : "--" },
  ];
  return (
    <div className="space-y-6">
      <div>
        <SectionHeader title="基本信息" description="球员个人档案" />
        <Card>
          <CardContent className="p-5">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
              <OverviewItem label="姓名" value={getPlayerNameLabel(player.name, player.full_name)} />
              <OverviewItem label="位置" value={player.position ? getPositionLabel(player.position) : "--"} />
              <OverviewItem label="国籍" value={getCountryLabel(player.nationality)} />
              <OverviewItem label="出生日期" value={formatDate(player.birth_date)} />
              <OverviewItem label="身高" value={player.height_cm ? `${player.height_cm} cm` : "--"} />
              <OverviewItem label="体重" value={player.weight_kg ? `${player.weight_kg} kg` : "--"} />
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        <SectionHeader title="身份概览" description="当前世界杯报名与基础表现" />
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          {summaryCards.map((item) => (
            <StatCard key={item.label} title={item.label} value={item.value} />
          ))}
        </div>
      </div>

      {stats && (
        <div>
          <SectionHeader title="赛季概览" description="本赛季核心数据" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="出场" value={stats.appearances ?? 0} icon={Activity} />
            <StatCard title="进球" value={stats.goals ?? 0} icon={Target} />
            <StatCard title="助攻" value={stats.assists ?? 0} icon={Zap} />
            <StatCard title="评分" value={formatNumber(stats.rating, 2)} icon={TrendingUp} />
          </div>
        </div>
      )}

      <div>
        <SectionHeader title="近期事件" description="最近比赛动态" />
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            <Clock className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">近期比赛事件数据即将上线</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function OverviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className="text-sm font-semibold">{value}</div>
    </div>
  );
}

function isGKPosition(position?: string): boolean {
  return position === "GK" || position === "Goalkeeper";
}

function SeasonStatsTab({ stats, isGK }: { stats?: PlayerStat; isGK: boolean }) {
  if (!stats) {
    return <EmptyState icon={Activity} title="暂无赛季数据" description="该球员本赛季暂无统计数据" />;
  }

  const outfieldStats = [
    { label: "出场次数", value: stats.appearances ?? 0, icon: Activity },
    { label: "进球", value: stats.goals ?? 0, icon: Target, highlight: true },
    { label: "助攻", value: stats.assists ?? 0, icon: Zap, highlight: true },
    { label: "出场分钟", value: stats.minutes_played ?? 0, icon: Clock },
    { label: "射门", value: stats.shots ?? 0, icon: Crosshair },
    { label: "射正", value: stats.shots_on_target ?? 0, icon: Target },
    { label: "预期进球(xG)", value: formatNumber(stats.xg, 2), icon: TrendingUp },
    { label: "预期助攻(xA)", value: formatNumber(stats.xa, 2), icon: TrendingUp },
    { label: "传球次数", value: stats.passes ?? 0, icon: Activity },
    { label: "传球成功率", value: stats.pass_accuracy != null ? `${formatNumber(stats.pass_accuracy, 1)}%` : "--", icon: Target },
    { label: "抢断", value: stats.tackles ?? 0, icon: Shield },
    { label: "拦截", value: stats.interceptions ?? 0, icon: Shield },
    { label: "黄牌", value: stats.yellow_cards ?? 0, icon: Flag },
    { label: "红牌", value: stats.red_cards ?? 0, icon: Flag },
    { label: "场均评分", value: formatNumber(stats.rating, 2), icon: Trophy, highlight: true },
  ];

  const gkStats = [
    { label: "出场次数", value: stats.appearances ?? 0, icon: Activity },
    { label: "出场分钟", value: stats.minutes_played ?? 0, icon: Clock },
    { label: "扑救", value: stats.saves ?? 0, icon: Shield, highlight: true },
    { label: "扑救成功率", value: stats.save_pct != null ? `${formatNumber(stats.save_pct, 1)}%` : "--", icon: Target },
    { label: "失球", value: stats.goals_conceded ?? 0, icon: Flag },
    { label: "预期失球(xGA)", value: formatNumber(stats.xga, 2), icon: TrendingUp },
    { label: "传中拦截", value: stats.crosses_stopped ?? 0, icon: Crosshair },
    { label: "场均评分", value: formatNumber(stats.rating, 2), icon: Trophy, highlight: true },
  ];

  const statList = isGK ? gkStats : outfieldStats;

  return (
    <div className="animate-fade-in">
      <SectionHeader title="赛季统计" description="各项数据统计详情" />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 animate-stagger">
        {statList.map((s, i) => (
          <StatCard
            key={i}
            title={s.label}
            value={s.value}
            icon={s.icon}
            className={s.highlight ? "border-primary/20" : undefined}
          />
        ))}
      </div>
    </div>
  );
}

function RadarTab({
  player,
  radarData,
  posStats,
  radarLoading,
  posLoading,
}: {
  player: Player;
  radarData?: RadarData;
  posStats?: PositionStats;
  radarLoading: boolean;
  posLoading: boolean;
}) {
  const positionConfig = getPositionConfig(player.position);
  const fallback = buildFallbackRadar(player);

  let dimensions: string[];
  let playerValues: number[];
  let medianValues: number[] | undefined;

  if (radarData && radarData.dimensions && radarData.values && radarData.dimensions.length > 0) {
    dimensions = getRadarDimensionLabels(radarData.dimensions);
    playerValues = radarData.values.map((value) => (Number.isFinite(value) ? value : 0));
    if (radarData.median_values && radarData.median_values.length === dimensions.length) {
      medianValues = radarData.median_values.map((value) => (Number.isFinite(value) ? value : 0));
    }
  } else {
    dimensions = fallback.dimensions;
    playerValues = fallback.values;
  }

  if (!medianValues && posStats && posStats.dimensions && posStats.median) {
    const medianMap: Record<string, number> = {};
    posStats.dimensions.forEach((d, i) => {
      medianMap[d] = posStats.median[i] ?? 0;
    });
    medianValues = dimensions.map((dimension) => {
      const exact = medianMap[dimension];
      if (exact != null) return exact;

      const configDimension = positionConfig.dimensions.find(
        (item) => item.label === dimension || (item.field as string) === dimension
      );
      if (configDimension) {
        return medianMap[configDimension.field as string] ?? 0;
      }
      return 0;
    });
  }

  if (radarLoading || posLoading) {
    return (
      <div className="animate-fade-in">
        <SectionHeader title="能力雷达" description="六维能力分析" />
        <Card>
          <CardContent className="p-6">
            <Skeleton className="h-[380px] rounded-lg" />
          </CardContent>
        </Card>
      </div>
    );
  }

  const series: RadarSeries[] = [
    {
      name: getPlayerNameLabel(player.name, player.full_name),
      values: playerValues,
      color: "#22c55e",
      areaOpacity: 0.2,
    },
  ];

  if (medianValues && medianValues.length === dimensions.length) {
    series.push({
      name: "同位置中位数",
      values: medianValues,
      color: "#94a3b8",
      lineStyle: "dashed",
      areaOpacity: 0.05,
    });
  }

  return (
    <div className="animate-fade-in">
      <SectionHeader
        title="能力雷达"
        description={`${positionConfig.label}能力分析${medianValues ? "（含同位置中位数）" : ""}`}
      />
      <Card>
        <CardContent className="p-6">
          <RadarChart dimensions={dimensions} series={series} max={100} height={420} />
        </CardContent>
      </Card>
    </div>
  );
}

interface PositionRank {
  position?: string;
  total_players?: number;
  rank?: number;
  overall_rank?: number;
  dimensions?: Record<string, { rank: number; total: number }>;
  [key: string]: unknown;
}

function PositionRankTab({
  rankData,
  isLoading,
  position,
}: {
  rankData?: PositionRank;
  isLoading: boolean;
  position?: string;
}) {
  if (isLoading) {
    return (
      <div className="animate-fade-in">
        <SectionHeader title="位置排名" description="同位置能力排名" />
        <LoadingState rows={4} />
      </div>
    );
  }

  if (!rankData) {
    return <EmptyState icon={Trophy} title="暂无排名数据" description="该球员暂无排名信息" />;
  }

  const totalPlayers = rankData.total_players ?? 0;
  const overallRank = rankData.rank ?? rankData.overall_rank ?? 0;
  const aheadPercent =
    totalPlayers > 1 && overallRank > 0
      ? Math.round(((totalPlayers - overallRank) / (totalPlayers - 1)) * 100)
      : 0;
  const topPercent =
    totalPlayers > 0 && overallRank > 0
      ? Math.max(1, Math.round((overallRank / totalPlayers) * 100))
      : 0;

  const dimensionRanks = rankData.dimensions as Record<string, { rank: number; total: number }> | undefined;

  return (
    <div className="animate-fade-in space-y-6">
      <SectionHeader
        title="位置排名"
        description={position ? `${getPositionLabel(position)} 位置排名` : "同位置能力排名"}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-primary/10 to-transparent border-primary/20">
          <CardContent className="p-6 text-center">
            <Trophy className="w-8 h-8 text-primary mx-auto mb-3" />
            <div className="font-display text-5xl font-bold text-primary tabular-nums">
              {overallRank || "--"}
            </div>
            <div className="text-sm text-muted-foreground mt-2">
              同位置排名 / {totalPlayers || "--"} 人
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 text-center">
            <Target className="w-8 h-8 text-accent mx-auto mb-3" />
            <div className="font-display text-5xl font-bold text-accent tabular-nums">
              {overallRank > 0 ? `前${topPercent}%` : "--"}
            </div>
            <div className="text-sm text-muted-foreground mt-2">
              {overallRank > 0 ? `超越 ${aheadPercent}% 同位置球员` : "超越同位置球员"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 text-center">
            <User className="w-8 h-8 text-amber-400 mx-auto mb-3" />
            <div className="font-display text-5xl font-bold text-amber-400 tabular-nums">
              {totalPlayers || "--"}
            </div>
            <div className="text-sm text-muted-foreground mt-2">同位置总人数</div>
          </CardContent>
        </Card>
      </div>

      {dimensionRanks && Object.keys(dimensionRanks).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">各维度排名</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border/50">
              {Object.entries(dimensionRanks).map(([key, val]) => {
                const label = dimensionLabelMap[key] || key;
                const p = val.total > 0 ? Math.round((1 - (val.rank - 1) / val.total) * 100) : 0;
                return (
                  <div key={key} className="flex items-center gap-4 px-5 py-3">
                    <div className="w-20 text-sm font-medium">{label}</div>
                    <div className="flex-1">
                      <div className="h-2 bg-secondary/50 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-primary to-accent rounded-full transition-all duration-700"
                          style={{ width: `${p}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-24 text-right">
                      <span className="font-display font-bold text-sm">第{val.rank}名</span>
                      <span className="text-muted-foreground text-xs ml-1">/ {val.total}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function PlayerDetail() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const playerId = id ? parseInt(id, 10) : 0;
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

  const {
    data: player,
    isLoading: playerLoading,
    error: playerError,
  } = useQuery<Player>({
    queryKey: ["player", playerId],
    queryFn: () => getPlayer(playerId),
    enabled: !!playerId,
  });

  const { data: stats } = useQuery<PlayerStat>({
    queryKey: ["player-stats", playerId],
    queryFn: () => getPlayerStats(playerId),
    enabled: !!playerId,
  });

  const { data: radarData, isLoading: radarLoading } = useQuery<RadarData>({
    queryKey: ["player-radar", playerId, player?.position],
    queryFn: () => getPlayerRadar(playerId, undefined, player?.position),
    enabled: !!playerId,
  });

  const { data: positionRank, isLoading: rankLoading } = useQuery<PositionRank>({
    queryKey: ["player-position-rank", playerId],
    queryFn: () => getPlayerPositionRank(playerId),
    enabled: !!playerId,
  });

  const isGK = isGKPosition(player?.position);

  const { data: posStats, isLoading: posLoading } = useQuery<PositionStats>({
    queryKey: ["position-stats", player?.position],
    queryFn: () => getPositionStats(player!.position!),
    enabled: !!player?.position,
  });

  if (playerLoading) {
    return <PlayerDetailSkeleton />;
  }

  if (playerError || !player) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="球员详情" />
        <Card className="p-12 text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-rose-400" />
          <CardTitle className="text-lg mb-2">加载失败</CardTitle>
          <p className="text-sm text-muted-foreground mb-4">无法加载球员信息，请稍后重试</p>
          <Link to="/players">
            <Button variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回球员列表
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  const teamIdentity = getTeamIdentity(player.team_name);

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <Link to="/players" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4">
          <ArrowLeft className="w-4 h-4" />
          返回球员列表
        </Link>
        <Breadcrumb
          items={[
            { label: "球员中心", to: "/players" },
            { label: getPlayerNameLabel(player?.name, player?.full_name) || "球员详情" },
          ]}
        />
        <PageHeader
          title={getPlayerNameLabel(player.name, player.full_name)}
          description={player.team_name ? `${teamIdentity.displayName} · ${getPositionLabel(player.position ?? "")}` : getPositionLabel(player.position ?? "")}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
        <div className="space-y-6">
          <PlayerInfoPanel player={player} />
        </div>

        <div>
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList>
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="stats">赛季统计</TabsTrigger>
              <TabsTrigger value="radar">能力雷达</TabsTrigger>
              <TabsTrigger value="rank">位置排名</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <OverviewTab player={player} stats={stats} />
            </TabsContent>

            <TabsContent value="stats">
              <SeasonStatsTab stats={stats} isGK={isGK} />
            </TabsContent>

            <TabsContent value="radar">
              <RadarTab
                player={player}
                radarData={radarData}
                posStats={posStats}
                radarLoading={radarLoading}
                posLoading={posLoading}
              />
            </TabsContent>

            <TabsContent value="rank">
              <PositionRankTab
                rankData={positionRank}
                isLoading={rankLoading}
                position={player.position}
              />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
