import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, StatCard, SectionHeader, LoadingState, EmptyState } from "@/components/ui/stat-card";
import { MatchCard } from "@/components/cards/MatchCard";
import { BarChart } from "@/components/charts/BarChart";
import { DonutChart } from "@/components/charts/DonutChart";
import { getLeagues } from "@/api/leagues";
import { getTopScorers } from "@/api/players";
import { getMatches } from "@/api/matches";
import { getPlayerPhoto, getTeamIdentity, handleImageError } from "@/lib/utils";
import type { Player } from "@/types";
import {
  Trophy,
  Users,
  Calendar,
  Target,
  Sparkles,
  User,
  Activity,
  ArrowRight,
} from "lucide-react";

const quickLinks = [
  { to: "/leagues", icon: Trophy, label: "联赛", desc: "各大联赛数据", color: "text-amber-400", bg: "bg-amber-500/10" },
  { to: "/teams", icon: Users, label: "球队", desc: "球队战绩统计", color: "text-sky-400", bg: "bg-sky-500/10" },
  { to: "/players", icon: User, label: "球员", desc: "榜单与对比", color: "text-rose-400", bg: "bg-rose-500/10" },
  { to: "/matches", icon: Calendar, label: "比赛", desc: "赛程赛果", color: "text-emerald-400", bg: "bg-emerald-500/10" },
  { to: "/ai-predict", icon: Sparkles, label: "AI预测", desc: "智能分析", color: "text-amber-400", bg: "bg-amber-500/10" },
];

export default function Dashboard() {
  const { data: leagues = [] } = useQuery({
    queryKey: ["leagues"],
    queryFn: () => getLeagues(),
  });

  const { data: topScorers = [], isLoading: scorersLoading } = useQuery({
    queryKey: ["topScorers"],
    queryFn: () => getTopScorers(5),
  });

  const { data: recentMatches = [], isLoading: matchesLoading } = useQuery({
    queryKey: ["matches", "recent"],
    queryFn: () => getMatches({ limit: 6 }),
  });

  // 射手榜数据：优先使用 goals，缺失时回退到 overall_rating
  const scorerData = topScorers.slice(0, 5);
  const hasGoals = scorerData.some(
    (p) => (p as Player & { goals?: number }).goals != null
  );
  const scorerNames = scorerData.map((p) =>
    p.name.length > 6 ? `${p.name.slice(0, 6)}…` : p.name
  );
  const scorerValues = scorerData.map((p) =>
    hasGoals
      ? (p as Player & { goals?: number }).goals ?? 0
      : p.overall_rating ?? 0
  );

  // 近期比赛统计
  const finishedMatches = recentMatches.filter((m) => m.status === "finished");
  const recentGoals = finishedMatches.reduce(
    (sum, m) => sum + (m.home_score ?? 0) + (m.away_score ?? 0),
    0
  );
  const liveCount = recentMatches.filter(
    (m) =>
      m.status === "live" ||
      m.status === "in_progress" ||
      m.status === "half_time"
  ).length;
  const scheduledCount = recentMatches.length - finishedMatches.length - liveCount;
  const statusData = [
    { name: "已结束", value: finishedMatches.length, color: "#64748b" },
    { name: "进行中", value: liveCount, color: "#22c55e" },
    { name: "未开始", value: scheduledCount, color: "#38bdf8" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="数据中心"
        description="全面的足球赛事数据分析与统计"
      >
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-secondary border border-border">
            <Activity className="w-3 h-3 text-emerald-400 animate-pulse" />
            <span className="font-mono font-bold text-emerald-400">LIVE</span>
            <span className="text-muted-foreground">数据同步中</span>
          </div>
        </div>
      </PageHeader>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-stagger">
        <StatCard
          title="联赛"
          value={leagues.length}
          icon={Trophy}
          description="覆盖联赛数量"
        />
        <StatCard
          title="TOP球员"
          value={topScorers.length}
          icon={Users}
          description="射手榜球员"
        />
        <StatCard
          title="比赛"
          value={recentMatches.length}
          icon={Calendar}
          description="近期比赛"
        />
        <StatCard
          title="近期进球"
          value={recentGoals}
          icon={Target}
          description="已结束比赛进球"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <SectionHeader
            title={hasGoals ? "射手榜TOP5" : "评分TOP5"}
            description={hasGoals ? "本赛季进球数领先球员" : "综合评分领先球员"}
          />
          {scorersLoading ? (
            <Card>
              <CardContent className="p-4">
                <LoadingState rows={4} />
              </CardContent>
            </Card>
          ) : scorerData.length === 0 ? (
            <EmptyState icon={Target} title="暂无球员数据" description="球员数据加载中" />
          ) : (
            <Card>
              <CardContent className="p-4">
                <BarChart
                  horizontal
                  showLabel
                  height={320}
                  categories={scorerNames}
                  series={[
                    {
                      name: hasGoals ? "进球数" : "评分",
                      values: scorerValues,
                      color: "#22c55e",
                    },
                  ]}
                />
              </CardContent>
            </Card>
          )}
        </div>

        <div>
          <SectionHeader
            title="比赛状态分布"
            description="近期比赛状态概览"
          />
          {matchesLoading ? (
            <Card>
              <CardContent className="p-4">
                <LoadingState rows={4} />
              </CardContent>
            </Card>
          ) : recentMatches.length === 0 ? (
            <EmptyState icon={Calendar} title="暂无比赛数据" description="比赛数据加载中" />
          ) : (
            <Card>
              <CardContent className="p-4">
                <DonutChart
                  height={320}
                  centerLabel="近期比赛"
                  centerValue={String(recentMatches.length)}
                  data={statusData}
                />
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <SectionHeader
            title="近期赛果"
            description="最新比赛结果与比分"
            action={
              <Link to="/matches" className="flex items-center gap-1 text-xs font-bold text-primary hover:underline uppercase tracking-wider">
                全部比赛 <ArrowRight className="w-3 h-3" />
              </Link>
            }
          />
          {matchesLoading ? (
            <LoadingState rows={3} />
          ) : recentMatches.length === 0 ? (
            <EmptyState icon={Calendar} title="暂无比赛数据" description="比赛数据加载中" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 animate-stagger">
              {recentMatches.slice(0, 6).map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <SectionHeader
            title="快速入口"
            description="数据导航"
          />
          <Card>
            <CardContent className="p-0">
              <div className="divide-y divide-border/60">
                {quickLinks.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    className="flex items-center gap-3 p-4 hover:bg-secondary/40 transition-colors group"
                  >
                    <div className={`w-9 h-9 flex items-center justify-center ${link.bg} border border-border`}>
                      <link.icon className={`w-4 h-4 ${link.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-bold text-sm group-hover:text-primary transition-colors">{link.label}</p>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{link.desc}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>

          <div>
            <SectionHeader
              title="球员榜"
              description="评分TOP球员"
              action={
                <Link to="/players" className="flex items-center gap-1 text-xs font-bold text-primary hover:underline uppercase tracking-wider">
                  更多 <ArrowRight className="w-3 h-3" />
                </Link>
              }
            />
            {scorersLoading ? (
              <LoadingState rows={5} />
            ) : topScorers.length === 0 ? (
              <EmptyState icon={Target} title="暂无球员数据" description="球员数据加载中" />
            ) : (
              <Card>
                <CardContent className="p-0">
                  <div className="divide-y divide-border/60">
                    {topScorers.slice(0, 5).map((player, index) => {
                      const medalColors = [
                        "bg-amber-500 text-black",
                        "bg-slate-300 text-black",
                        "bg-amber-700 text-white",
                      ];
                      const identity = getTeamIdentity(player.team_name);
                      return (
                        <Link
                          key={player.id}
                          to={`/players/${player.id}`}
                          className="flex items-center gap-3 p-3 hover:bg-secondary/40 transition-colors"
                        >
                          <div className={`w-6 h-6 flex items-center justify-center text-[10px] font-black font-mono ${
                            index < 3 ? medalColors[index] : "bg-secondary text-muted-foreground"
                          }`}>
                            {index + 1}
                          </div>
                          <img
                            src={getPlayerPhoto(player.photo_url)}
                            alt={player.name}
                            className="w-10 h-10 object-cover object-[center_12%] bg-secondary border border-border flex-shrink-0"
                            onError={handleImageError}
                            loading="lazy"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="font-bold text-sm truncate">{player.name}</p>
                            <p className="text-[10px] text-muted-foreground truncate">
                              {player.team_name ? identity.displayName : "未知球队"}
                              {player.position && ` · ${player.position}`}
                            </p>
                          </div>
                          <div className="text-right">
                            <div className="font-mono font-black text-lg text-primary">
                              {player.overall_rating ?? "--"}
                            </div>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
