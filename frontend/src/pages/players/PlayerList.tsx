import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Search,
  Users,
  Filter,
  List,
  Trophy,
  ArrowLeftRight,
  ChevronDown,
  Target,
  Zap,
  Star,
} from "lucide-react";
import { comparePlayers, getPositionStats } from "@/api/players";
import { getWorldCupLeaders, getWorldCupPlayers } from "@/api/worldcup";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  PageHeader,
  SectionHeader,
  LoadingState,
  EmptyState,
} from "@/components/ui/stat-card";
import { RadarChart } from "@/components/charts/RadarChart";
import type { RadarSeries } from "@/components/charts/RadarChart";
import { PlayerCard } from "@/components/cards/PlayerCard";
import { Pagination } from "@/components/ui/pagination";
import { useDebounce } from "@/lib/hooks";
import {
  getGroupLabel,
  getPlayerPhoto,
  getPlayerNameLabel,
  handleImageError,
  getCountryLabel,
  getPositionLabel,
  getPositionColor,
  getTeamIdentity,
  formatNumber,
  getRadarDimensionLabels,
  cn,
} from "@/lib/utils";
import {
  getPositionDimensions,
  getPlayerPositionValues,
  normalizePosition,
  getCommonDimensions,
  getPlayerValuesByFields,
} from "@/lib/position-dimensions";
import type {
  Player,
  PlayerStat,
  PositionStats,
  PlayerCompareResult,
  WorldCupPlayer,
} from "@/types";

type LeaderTab = "goals" | "assists" | "rating";

const POSITION_OPTIONS = [
  { value: "", label: "全部位置" },
  { value: "GK", label: `门将 (GK)` },
  { value: "DF", label: `后卫 (DF)` },
  { value: "MF", label: `中场 (MF)` },
  { value: "FW", label: `前锋 (FW)` },
];

const GROUP_OPTIONS = [
  "",
  "Group A",
  "Group B",
  "Group C",
  "Group D",
  "Group E",
  "Group F",
  "Group G",
  "Group H",
  "Group I",
  "Group J",
  "Group K",
  "Group L",
];

const COMPARE_STATS = [
  { key: "goals", label: "进球", digits: 0 },
  { key: "assists", label: "助攻", digits: 0 },
  { key: "shots", label: "射门", digits: 0 },
  { key: "passes", label: "传球", digits: 0 },
  { key: "xg", label: "预期进球(xG)", digits: 2 },
  { key: "rating", label: "场均评分", digits: 2 },
  { key: "appearances", label: "出场次数", digits: 0 },
  { key: "minutes_played", label: "出场分钟", digits: 0 },
  { key: "tackles", label: "抢断", digits: 0 },
  { key: "interceptions", label: "拦截", digits: 0 },
] as const;

function getRatingColor(rating: number | undefined): string {
  if (!rating) return "text-slate-400";
  if (rating >= 85) return "text-rose-400";
  if (rating >= 80) return "text-amber-400";
  if (rating >= 75) return "text-emerald-400";
  if (rating >= 70) return "text-sky-400";
  return "text-slate-400";
}

function getRatingBg(rating: number | undefined): string {
  if (!rating) return "from-slate-600/20 to-slate-800/20 border-slate-600/30";
  if (rating >= 85) return "from-rose-500/20 to-rose-700/10 border-rose-500/30";
  if (rating >= 80) return "from-amber-500/20 to-amber-700/10 border-amber-500/30";
  if (rating >= 75) return "from-emerald-500/20 to-emerald-700/10 border-emerald-500/30";
  if (rating >= 70) return "from-sky-500/20 to-sky-700/10 border-sky-500/30";
  return "from-slate-500/20 to-slate-700/10 border-slate-500/30";
}

function normalizeWorldCupPlayer(player: WorldCupPlayer): Player {
  const identity = getTeamIdentity(player.team_name, player.nationality);
  return {
    id: player.player_id,
    name: player.name,
    full_name: player.name,
    position: player.position,
    team_id: player.team_id,
    team_name: identity.displayName || player.team_name,
    nationality: player.nationality,
    photo_url: player.photo_url,
    overall_rating: player.overall_rating ?? player.rating,
    group_name: player.group,
    atk_score: player.atk_score,
    org_score: player.org_score,
    def_score: player.def_score,
    gk_score: player.gk_score,
    phy_score: player.phy_score,
    dis_score: player.dis_score,
    stats: [
      {
        player_id: player.player_id,
        appearances: player.appearances ?? player.matches_played,
        goals: player.goals,
        assists: player.assists,
        minutes_played: player.minutes_played,
        shots: player.shots,
        passes: player.passes,
        xg: player.xg,
        xa: player.xa,
        rating: player.rating,
      },
    ],
  } as Player;
}

function mergePlayerWithReference(player: Player, referencePlayers: Player[]): Player {
  const reference = referencePlayers.find((item) => item.id === player.id);
  if (!reference) return player;

  return {
    ...reference,
    ...player,
    photo_url: player.photo_url ?? reference.photo_url,
    full_name: player.full_name ?? reference.full_name,
    nationality: player.nationality ?? reference.nationality,
    team_name: player.team_name ?? reference.team_name,
    team_id: player.team_id ?? reference.team_id,
    jersey_number: player.jersey_number ?? reference.jersey_number,
    overall_rating: player.overall_rating ?? reference.overall_rating,
    group_name: player.group_name ?? reference.group_name,
  };
}

function PlayerListTab() {
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("");
  const [group, setGroup] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;
  const debouncedSearch = useDebounce(search, 300);

  const { data: worldCupPlayers = [], isLoading } = useQuery<WorldCupPlayer[]>({
    queryKey: ["worldcup-players", group, position],
    queryFn: () =>
      getWorldCupPlayers({
        group: group || undefined,
        position: position || undefined,
        limit: 2000,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const players = useMemo(() => {
    const normalized = worldCupPlayers.map(normalizeWorldCupPlayer);
    if (!debouncedSearch.trim()) return normalized;
    const q = debouncedSearch.trim().toLowerCase();
    return normalized.filter((player) => {
      const displayName = getPlayerNameLabel(player.name, player.full_name).toLowerCase();
      const teamDisplay = getTeamIdentity(player.team_name, player.nationality).displayName.toLowerCase();
      const countryDisplay = getCountryLabel(player.nationality).toLowerCase();
      return (
        displayName.includes(q) ||
        (player.name ?? "").toLowerCase().includes(q) ||
        teamDisplay.includes(q) ||
        countryDisplay.includes(q)
      );
    });
  }, [worldCupPlayers, debouncedSearch]);

  const paginatedPlayers = players.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <div>
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Filter className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">筛选条件</span>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              <Input
                type="text"
                placeholder="搜索球员姓名..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setCurrentPage(1);
                }}
                className="pl-9"
              />
            </div>
            <Select
              value={position}
              onChange={(e) => {
                setPosition(e.target.value);
                setCurrentPage(1);
              }}
              className="sm:w-48"
            >
              {POSITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            <Select
              value={group}
              onChange={(e) => {
                setGroup(e.target.value);
                setCurrentPage(1);
              }}
              className="sm:w-56"
            >
              <option value="">全部小组</option>
              {GROUP_OPTIONS.filter(Boolean).map((groupName) => (
                <option key={groupName} value={groupName}>
                  {getGroupLabel(groupName)}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between mb-4">
        <SectionHeader
          title="球员列表"
          description={isLoading ? "加载中..." : `仅展示世界杯球员，共 ${formatNumber(players.length, 0)} 人`}
        />
        {!isLoading && players.length > 0 && (
          <Badge variant="secondary" className="gap-1.5">
            <Users className="w-3.5 h-3.5" />
            {formatNumber(players.length, 0)}
          </Badge>
        )}
      </div>

      {isLoading ? (
        <LoadingState rows={8} />
      ) : players.length === 0 ? (
        <EmptyState
          icon={Users}
          title="暂无球员数据"
          description="当前筛选条件下没有找到世界杯球员，请尝试调整搜索、小组或位置"
        />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 animate-stagger">
            {paginatedPlayers.map((player) => (
              <PlayerCard key={player.id} player={player} />
            ))}
          </div>
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(players.length / pageSize)}
            onPageChange={setCurrentPage}
          />
        </>
      )}
    </div>
  );
}

function sortPlayers(players: Player[], key: LeaderTab) {
  return [...players].sort((a, b) => {
    const getStat = (p: Player, k: string) => {
      const stat = (p as unknown as { stats?: PlayerStat[] }).stats?.[0];
      if (k === "goals") return stat?.goals ?? 0;
      if (k === "assists") return stat?.assists ?? 0;
      if (k === "rating") return stat?.rating ?? 0;
      return 0;
    };
    return getStat(b, key) - getStat(a, key);
  });
}

function LeadersTab() {
  const [tab, setTab] = useState<LeaderTab>("goals");
  const { data: leaders, isLoading } = useQuery({
    queryKey: ["worldcup-leaders", 50],
    queryFn: () => getWorldCupLeaders(50),
    staleTime: 5 * 60 * 1000,
  });

  const players = useMemo(() => {
    const rows =
      tab === "goals"
        ? leaders?.top_scorers ?? []
        : tab === "assists"
        ? leaders?.top_assists ?? []
        : leaders?.top_ratings ?? [];
    return rows.map((row) =>
      normalizeWorldCupPlayer({
        player_id: row.player_id,
        name: row.name,
        position: row.position,
        team_name: row.team_name,
        photo_url: row.photo_url,
        appearances: row.appearances ?? row.matches_played,
        goals: tab === "goals" ? row.value : undefined,
        assists: tab === "assists" ? row.value : undefined,
        rating: tab === "rating" ? row.value : undefined,
      })
    );
  }, [leaders, tab]);

  const sorted = sortPlayers(players ?? [], tab);
  const maxVal = Math.max(
    ...sorted.map((p) => {
      const stat = (p as unknown as { stats?: PlayerStat[] }).stats?.[0];
      if (tab === "goals") return stat?.goals ?? 0;
      if (tab === "assists") return stat?.assists ?? 0;
      if (tab === "rating") return stat?.rating ?? 0;
      return 0;
    }),
    1
  );

  return (
    <div>
      <Tabs value={tab} onValueChange={(v) => setTab(v as LeaderTab)}>
        <TabsList className="mb-4">
          <TabsTrigger value="goals">
            <Target className="w-4 h-4 mr-1.5" />
            射手榜
          </TabsTrigger>
          <TabsTrigger value="assists">
            <Zap className="w-4 h-4 mr-1.5" />
            助攻榜
          </TabsTrigger>
          <TabsTrigger value="rating">
            <Star className="w-4 h-4 mr-1.5" />
            评分榜
          </TabsTrigger>
        </TabsList>

        <TabsContent value={tab}>
          {isLoading ? (
            <LoadingState rows={8} />
          ) : sorted.length === 0 ? (
            <EmptyState icon={Trophy} title="暂无数据" description="排行榜数据加载中" />
          ) : (
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full data-table">
                  <thead>
                    <tr className="border-b border-border/50">
                      <th className="w-14 text-center">排名</th>
                      <th>球员</th>
                      <th>位置</th>
                      <th className="text-center w-20">
                        {tab === "goals" ? "进球" : tab === "assists" ? "助攻" : "评分"}
                      </th>
                      <th className="text-center w-16">出场</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((p, i) => (
                      <LeaderRow key={p.id} player={p} rank={i + 1} tab={tab} maxVal={maxVal} />
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function LeaderRow({ player, rank, tab, maxVal }: { player: Player; rank: number; tab: LeaderTab; maxVal: number }) {
  const stat = (player as unknown as { stats?: PlayerStat[] }).stats?.[0];
  const medals = [
    { bg: "bg-gradient-to-br from-yellow-400 to-yellow-600", text: "text-black", ring: "ring-yellow-500/30" },
    { bg: "bg-gradient-to-br from-gray-300 to-gray-500", text: "text-black", ring: "ring-gray-400/30" },
    { bg: "bg-gradient-to-br from-orange-400 to-orange-600", text: "text-black", ring: "ring-orange-500/30" },
  ];
  const isTop = rank <= 3;
  const medal = medals[rank - 1];

  const statValue =
    tab === "goals" ? stat?.goals ?? 0 : tab === "assists" ? stat?.assists ?? 0 : stat?.rating ?? 0;
  const statColor =
    tab === "goals" ? "text-emerald-400" : tab === "assists" ? "text-sky-400" : "text-amber-400";

  return (
    <tr className="hover:bg-secondary/30 transition-colors">
      <td className="px-4 py-3">
        <div className="flex justify-center">
          {isTop ? (
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shadow-sm",
                medal.bg,
                medal.text
              )}
            >
              {rank}
            </div>
          ) : (
            <span className="text-muted-foreground font-mono text-sm">{rank}</span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <Link to={`/players/${player.id}`} className="flex items-center gap-3 group">
          <div className="relative flex-shrink-0">
              <img
                src={getPlayerPhoto(player.photo_url)}
                alt={getPlayerNameLabel(player.name, player.full_name)}
                className={cn(
                  "w-11 h-11 rounded-full object-cover object-[center_8%] bg-secondary",
                  isTop && medal ? `ring-2 ${medal.ring}` : ""
                )}
                onError={handleImageError}
              loading="lazy"
            />
            {isTop && (
              <div
                className={cn(
                  "absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border-2 border-card shadow-sm",
                  medal.bg,
                  medal.text
                )}
              >
                {rank}
              </div>
            )}
          </div>
            <div className="min-w-0">
              <div className="font-semibold text-sm group-hover:text-primary transition-colors truncate">
                {getPlayerNameLabel(player.name, player.full_name)}
              </div>
              <div className="text-xs text-muted-foreground truncate">
              {player.team_name ? getTeamIdentity(player.team_name).displayName : getCountryLabel(player.nationality)}
              </div>
            </div>
        </Link>
      </td>
      <td className="px-4 py-3">
        {player.position && (
          <Badge className={getPositionColor(player.position)}>{getPositionLabel(player.position)}</Badge>
        )}
      </td>
      <td className="px-4 py-3 text-center relative">
        <div
          className="absolute inset-y-1 left-1 bg-primary/10 rounded"
          style={{ width: `${(statValue / maxVal) * 100}%` }}
        />
        <span className={cn("relative font-display font-bold text-lg tabular-nums", statColor)}>
          {tab === "rating" ? (stat as PlayerStat)?.rating?.toFixed(1) ?? "--" : statValue}
        </span>
      </td>
      <td className="px-4 py-3 text-center text-muted-foreground font-mono text-sm">
        {stat?.appearances ?? 0}
      </td>
    </tr>
  );
}

interface PlayerSelectorProps {
  label: string;
  color: "green" | "blue";
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  players: Player[];
}

function PlayerSelector({ label, color, selectedId, onSelect, players }: PlayerSelectorProps) {
  const [search, setSearch] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const colorClasses =
    color === "green"
      ? {
          ring: "focus:ring-emerald-500/30",
          border: "focus:border-emerald-500",
          dot: "bg-emerald-500",
        }
      : {
          ring: "focus:ring-sky-500/30",
          border: "focus:border-sky-500",
          dot: "bg-sky-500",
        };

  const filteredPlayers = useMemo(() => {
    if (!search.trim()) return players;
    const q = search.toLowerCase();
    return players.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        getPlayerNameLabel(p.name, p.full_name).toLowerCase().includes(q) ||
        (p.team_name && p.team_name.toLowerCase().includes(q))
    );
  }, [players, search]);

  const selectedPlayer = players.find((p) => p.id === selectedId);

  return (
    <div className="relative flex-1">
      <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
        {label}
      </label>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex h-11 w-full items-center justify-between rounded-lg bg-input border border-border px-4",
          "text-left text-sm transition-all",
          "hover:border-border/80",
          isOpen && `${colorClasses.ring} ring-2 ${colorClasses.border}`
        )}
      >
        {selectedPlayer ? (
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn("w-2 h-2 rounded-full flex-shrink-0", colorClasses.dot)} />
            <div className="flex items-center gap-2.5 min-w-0">
              <img
                src={getPlayerPhoto(selectedPlayer.photo_url)}
                alt={getPlayerNameLabel(selectedPlayer.name, selectedPlayer.full_name)}
                className="w-8 h-8 rounded-lg object-cover object-[center_8%] bg-secondary flex-shrink-0"
                onError={handleImageError}
              />
              <span className="font-medium truncate">{getPlayerNameLabel(selectedPlayer.name, selectedPlayer.full_name)}</span>
              {selectedPlayer.position && (
                <Badge
                  className={cn(
                    "flex-shrink-0 text-[10px] px-1.5 py-0",
                    getPositionColor(selectedPlayer.position)
                  )}
                >
                  {getPositionLabel(selectedPlayer.position)}
                </Badge>
              )}
            </div>
          </div>
        ) : (
          <span className="text-muted-foreground flex items-center gap-2">
            <Users className="w-4 h-4" />
            选择球员...
          </span>
        )}
        <ChevronDown
          className={cn(
            "w-4 h-4 text-muted-foreground transition-transform flex-shrink-0 ml-2",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 z-50 mt-2 rounded-lg border border-border bg-popover shadow-xl animate-fade-in overflow-hidden">
          <div className="p-2 border-b border-border/50">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索球员姓名或球队..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9"
                autoFocus
              />
            </div>
          </div>
          <div className="max-h-72 overflow-y-auto">
            {filteredPlayers.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                未找到匹配的球员
              </div>
            ) : (
              filteredPlayers.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    onSelect(p.id);
                    setIsOpen(false);
                    setSearch("");
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm transition-colors hover:bg-secondary/50",
                    selectedId === p.id && "bg-secondary"
                  )}
                >
                  <img
                    src={getPlayerPhoto(p.photo_url)}
                    alt={getPlayerNameLabel(p.name, p.full_name)}
                    className="w-8 h-8 rounded-lg object-cover object-[center_8%] bg-secondary flex-shrink-0"
                    onError={handleImageError}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{getPlayerNameLabel(p.name, p.full_name)}</div>
                    <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                      {p.position && <span>{getPositionLabel(p.position)}</span>}
                      {p.team_name && (
                        <>
                          <span>·</span>
                          <span className="truncate">
                            {getTeamIdentity(p.team_name, p.nationality).displayName}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  {p.overall_rating != null && (
                    <span className={cn("font-display font-bold text-sm", getRatingColor(p.overall_rating))}>
                      {p.overall_rating}
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {isOpen && <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />}
    </div>
  );
}

function ComparePlayerCard({ player, color }: { player: Player; color: "green" | "blue" }) {
  const teamIdentity = getTeamIdentity(player.team_name, player.nationality);
  const colorClasses =
    color === "green"
      ? {
          border: "border-emerald-500/20",
          accent: "text-emerald-400",
          ring: "ring-emerald-500/20",
          gradient: "from-emerald-500/10",
        }
      : {
          border: "border-sky-500/20",
          accent: "text-sky-400",
          ring: "ring-sky-500/20",
          gradient: "from-sky-500/10",
        };

  const rating = player.overall_rating ?? 0;

  return (
    <Card className={cn("overflow-hidden transition-all hover:shadow-lg", colorClasses.border)}>
      <div
        className={cn(
          "h-20 bg-gradient-to-r to-transparent via-primary/5",
          colorClasses.gradient
        )}
      />
      <CardContent className="relative -mt-12 pt-0 px-5 pb-5">
        <div className="flex items-start gap-4">
          <img
            src={getPlayerPhoto(player.photo_url)}
            alt={getPlayerNameLabel(player.name, player.full_name)}
            className={cn(
              "w-24 h-24 rounded-xl object-cover object-[center_8%] border-4 border-card shadow-lg bg-secondary ring-2",
              colorClasses.ring
            )}
            onError={handleImageError}
          />
          <div className="flex-1 min-w-0 pt-2">
            <h3 className="text-lg font-bold font-display tracking-tight truncate">
              {getPlayerNameLabel(player.name, player.full_name)}
            </h3>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {player.position && (
                <Badge className={cn(getPositionColor(player.position))}>
                  {getPositionLabel(player.position)}
                </Badge>
              )}
              {teamIdentity.displayName && (
                <span className="text-sm text-muted-foreground truncate flex items-center gap-1">
                  <Trophy className="w-3.5 h-3.5" />
                  {teamIdentity.displayName}
                </span>
              )}
            </div>
          </div>
          <div
            className={cn(
              "w-16 h-16 rounded-xl flex items-center justify-center bg-gradient-to-br border flex-shrink-0",
              getRatingBg(rating)
            )}
          >
            <div className="text-center">
              <div className={cn("font-display text-2xl font-bold tabular-nums", getRatingColor(rating))}>
                {rating || "--"}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CompareResult({
  result,
  referencePlayers,
}: {
  result: PlayerCompareResult;
  referencePlayers: Player[];
}) {
  const player_a = useMemo(
    () => mergePlayerWithReference(result.player_a, referencePlayers),
    [result.player_a, referencePlayers]
  );
  const player_b = useMemo(
    () => mergePlayerWithReference(result.player_b, referencePlayers),
    [result.player_b, referencePlayers]
  );
  const { stats_a, stats_b, radar_a, radar_b, recommended_visualization } = result;

  const isSummaryOnly = recommended_visualization === "summary_only";

  // 判断两名球员是否同位置
  const isSamePosition = useMemo(() => {
    return normalizePosition(player_a.position) === normalizePosition(player_b.position);
  }, [player_a.position, player_b.position]);

  // 同位置时才查询中位数
  const { data: posStats } = useQuery<PositionStats>({
    queryKey: ["position-stats", player_a.position],
    queryFn: () => getPositionStats(player_a.position!),
    enabled: isSamePosition && !!player_a.position,
  });

  const dimensions = useMemo(() => {
    if (isSamePosition) {
      // 同位置对比：优先使用后端返回的维度（已按位置映射），否则使用位置配置维度
      if (radar_a?.dimensions && radar_a.dimensions.length > 0) {
        return getRadarDimensionLabels(radar_a.dimensions);
      }
      if (radar_b?.dimensions && radar_b.dimensions.length > 0) {
        return getRadarDimensionLabels(radar_b.dimensions);
      }
      return getPositionDimensions(player_a.position);
    }
    // 跨位置对比：使用公共维度
    return getCommonDimensions().dimensions;
  }, [isSamePosition, radar_a, radar_b, player_a.position]);

  const radarSeries = useMemo<RadarSeries[]>(() => {
    let valuesA: number[];
    let valuesB: number[];

    if (isSamePosition) {
      // 同位置对比：后端返回统一维度时直接用，否则按位置映射提取数值
      if (radar_a?.values && radar_a.values.length === dimensions.length) {
        valuesA = radar_a.values;
      } else {
        valuesA = getPlayerPositionValues(player_a, player_a.position);
      }
      if (radar_b?.values && radar_b.values.length === dimensions.length) {
        valuesB = radar_b.values;
      } else {
        valuesB = getPlayerPositionValues(player_b, player_a.position);
      }
    } else {
      // 跨位置对比：按公共维度的字段分别提取
      const common = getCommonDimensions();
      valuesA = getPlayerValuesByFields(player_a, common.fieldA);
      valuesB = getPlayerValuesByFields(player_b, common.fieldB);
    }

    const series: RadarSeries[] = [
      {
        name: player_a.name,
        values: valuesA,
        color: "#22c55e",
        areaOpacity: 0.15,
      },
      {
        name: player_b.name,
        values: valuesB,
        color: "#38bdf8",
        areaOpacity: 0.15,
      },
    ];

    // 仅同位置对比时展示中位数参考线
    if (isSamePosition && posStats?.median && posStats.median.length > 0) {
      let medianValues = posStats.median;
      if (
        posStats.dimensions &&
        posStats.dimensions.length === posStats.median.length &&
        radar_a?.dimensions
      ) {
        const medianMap: Record<string, number> = {};
        posStats.dimensions.forEach((d, i) => {
          medianMap[d] = posStats.median[i] ?? 0;
        });
        medianValues = getRadarDimensionLabels(radar_a.dimensions).map((d) => medianMap[d] ?? 0);
      }
      if (medianValues.length === dimensions.length) {
        series.push({
          name: "同位置中位数",
          values: medianValues,
          color: "#94a3b8",
          lineStyle: "dashed",
          areaOpacity: 0.05,
        });
      }
    }

    return series;
  }, [
    isSamePosition,
    player_a,
    player_b,
    radar_a,
    radar_b,
    posStats,
    dimensions,
  ]);

  const getStatValue = (key: string, stats: typeof stats_a): number | null => {
    const val = (stats as unknown as Record<string, unknown>)[key];
    if (typeof val === "number") return val;
    return null;
  };

  return (
    <div className="animate-fade-in space-y-6">
      {isSummaryOnly && (
        <div className="animate-fade-in">
          <Badge variant="warning" className="text-sm py-1.5 px-3">
            数据完整度不足，仅展示基础数据对比
          </Badge>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ComparePlayerCard player={player_a} color="green" />
        <ComparePlayerCard player={player_b} color="blue" />
      </div>

      {!isSummaryOnly && (
        <div className="animate-stagger">
          <SectionHeader
            title="六维能力雷达"
            description={
              isSamePosition
                ? "球员能力对比（灰色虚线为同位置中位数）"
                : "位置不同，使用公共维度对比"
            }
          />
          <Card>
            <CardContent className="p-6">
              {!isSamePosition && (
                <Badge variant="warning" className="mb-3">
                  位置不同，已映射到公共维度对比
                </Badge>
              )}
              <RadarChart dimensions={dimensions} series={radarSeries} max={100} height={420} />
            </CardContent>
          </Card>
        </div>
      )}

      <div className="animate-stagger">
        <SectionHeader title="数据对比" description="各项赛季数据详细对比" />
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    数据项
                  </th>
                  <th className="text-right px-5 py-3.5 text-xs font-semibold uppercase tracking-wider">
                    <span className="text-emerald-400">{player_a.name}</span>
                  </th>
                  <th className="text-center px-5 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    对比
                  </th>
                  <th className="text-right px-5 py-3.5 text-xs font-semibold uppercase tracking-wider">
                    <span className="text-sky-400">{player_b.name}</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {COMPARE_STATS.map(({ key, label, digits }) => {
                  const valA = getStatValue(key, stats_a);
                  const valB = getStatValue(key, stats_b);
                  const aBetter = valA != null && valB != null && valA > valB;
                  const bBetter = valA != null && valB != null && valB > valA;
                  const equal = valA != null && valB != null && valA === valB;

                  return (
                    <tr key={key} className="hover:bg-secondary/20 transition-colors">
                      <td className="px-5 py-3.5 text-sm font-medium">{label}</td>
                      <td className="px-5 py-3.5 text-right">
                        <span
                          className={cn(
                            "font-display text-base font-bold tabular-nums",
                            aBetter
                              ? "text-emerald-400"
                              : equal
                              ? "text-slate-400"
                              : "text-slate-300"
                          )}
                        >
                          {formatNumber(valA, digits)}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        {equal ? (
                          <span className="text-slate-500 text-lg">—</span>
                        ) : (
                          <div className="flex items-center justify-center gap-1">
                            {aBetter && (
                              <>
                                <div className="h-1.5 w-8 bg-gradient-to-r from-emerald-500 to-emerald-500/30 rounded-full" />
                                <span className="text-emerald-400 text-xs font-bold">▲</span>
                              </>
                            )}
                            {bBetter && (
                              <>
                                <span className="text-sky-400 text-xs font-bold">▼</span>
                                <div className="h-1.5 w-8 bg-gradient-to-l from-sky-500 to-sky-500/30 rounded-full" />
                              </>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <span
                          className={cn(
                            "font-display text-base font-bold tabular-nums",
                            bBetter
                              ? "text-sky-400"
                              : equal
                              ? "text-slate-400"
                              : "text-slate-300"
                          )}
                        >
                          {formatNumber(valB, digits)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CompareTab() {
  const [playerAId, setPlayerAId] = useState<number | null>(null);
  const [playerBId, setPlayerBId] = useState<number | null>(null);
  const [shouldCompare, setShouldCompare] = useState(false);

  const { data: players = [], isLoading: playersLoading } = useQuery<Player[]>({
    queryKey: ["worldcup-players", "compare"],
    queryFn: () => getWorldCupPlayers({ limit: 2000 }).then((rows) => rows.map(normalizeWorldCupPlayer)),
    staleTime: 5 * 60 * 1000,
  });

  const { data: compareResult, isLoading: compareLoading } = useQuery<PlayerCompareResult>({
    queryKey: ["compare-players", playerAId, playerBId],
    queryFn: () => comparePlayers(playerAId!, playerBId!),
    enabled: shouldCompare && playerAId != null && playerBId != null,
  });

  const canCompare = playerAId != null && playerBId != null && playerAId !== playerBId;

  const handleCompare = () => {
    if (canCompare) {
      setShouldCompare(true);
    }
  };

  const handleSwap = () => {
    const temp = playerAId;
    setPlayerAId(playerBId);
    setPlayerBId(temp);
    setShouldCompare(true);
  };

  return (
    <div>
      <Card className="mb-8">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row items-end gap-4">
            <PlayerSelector
              label="球员 A"
              color="green"
              selectedId={playerAId}
              onSelect={(id) => {
                setPlayerAId(id);
                setShouldCompare(false);
              }}
              players={players}
            />

            <div className="flex items-center gap-2 lg:pb-0.5">
              <Button
                variant="outline"
                size="icon"
                onClick={handleSwap}
                disabled={!playerAId || !playerBId}
                className="rounded-full h-11 w-11 flex-shrink-0"
                title="交换球员"
              >
                <ArrowLeftRight className="w-4 h-4" />
              </Button>
            </div>

            <PlayerSelector
              label="球员 B"
              color="blue"
              selectedId={playerBId}
              onSelect={(id) => {
                setPlayerBId(id);
                setShouldCompare(false);
              }}
              players={players}
            />

            <Button
              onClick={handleCompare}
              disabled={!canCompare || compareLoading || playersLoading}
              className="h-11 px-6 flex-shrink-0 lg:w-auto w-full"
            >
              {compareLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  对比中...
                </>
              ) : (
                <>
                  <ArrowLeftRight className="w-4 h-4" />
                  对比
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {compareLoading && (
        <div className="space-y-6 animate-fade-in">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="h-36 rounded-xl bg-secondary/30 animate-pulse" />
            <div className="h-36 rounded-xl bg-secondary/30 animate-pulse" />
          </div>
          <Card>
            <CardContent className="p-6">
              <div className="h-[420px] rounded-lg bg-secondary/30 animate-pulse" />
            </CardContent>
          </Card>
        </div>
      )}

      {!compareLoading && compareResult && (
        <CompareResult result={compareResult} referencePlayers={players} />
      )}

      {!compareLoading && !compareResult && (
        <EmptyState
          icon={ArrowLeftRight}
          title="选择两名球员开始对比"
          description="从世界杯球员中选择两名球员，查看他们的六维能力雷达图和数据对比"
        />
      )}
    </div>
  );
}

export function PlayerList() {
  return (
    <div className="animate-fade-in">
      <PageHeader title="球员中心" description="仅保留世界杯球员，浏览榜单、详情与能力对比" />

      <Tabs defaultValue="list">
        <TabsList className="mb-6">
          <TabsTrigger value="list">
            <List className="w-4 h-4 mr-1.5" />
            球员列表
          </TabsTrigger>
          <TabsTrigger value="leaders">
            <Trophy className="w-4 h-4 mr-1.5" />
            排行榜
          </TabsTrigger>
          <TabsTrigger value="compare">
            <ArrowLeftRight className="w-4 h-4 mr-1.5" />
            球员对比
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list">
          <PlayerListTab />
        </TabsContent>
        <TabsContent value="leaders">
          <LeadersTab />
        </TabsContent>
        <TabsContent value="compare">
          <CompareTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
