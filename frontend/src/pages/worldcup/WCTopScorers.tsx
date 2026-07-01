import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getWorldCupLeaders } from "@/api/worldcup";
import { getPlayerNameLabel, getTeamIdentity } from "@/lib/utils";
import type { WorldCupLeaderItem, WorldCupLeaders } from "@/types";

type LeaderTab = "goals" | "assists" | "rating";

const TABS: { key: LeaderTab; label: string }[] = [
  { key: "goals", label: "进球" },
  { key: "assists", label: "助攻" },
  { key: "rating", label: "评分" },
];

export function WCTopScorers() {
  const [activeTab, setActiveTab] = useState<LeaderTab>("goals");

  const { data } = useQuery<WorldCupLeaders>({
    queryKey: ["worldcup-leaders"],
    queryFn: () => getWorldCupLeaders(10),
  });

  const leaders = data ?? { top_scorers: [], top_assists: [], top_ratings: [] };

  const list =
    activeTab === "goals"
      ? leaders.top_scorers
      : activeTab === "assists"
        ? leaders.top_assists
        : leaders.top_ratings;
  const maxValue = list.length > 0 ? Math.max(...list.map((item) => item.value)) : 1;

  const formatValue = (val: number): string => (activeTab === "rating" ? val.toFixed(1) : String(val));

  return (
    <div className="flex h-full flex-col">
      <div className="mb-6 flex items-baseline justify-between">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[#f1f5f9]">球员榜单</h2>
        <span className="text-xs text-[#64748b]">{list.length} 名球员</span>
      </div>

      <div className="mb-4 flex gap-6 border-b border-[#23262d]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`relative pb-2 text-xs font-medium uppercase tracking-wider transition-colors ${
              activeTab === tab.key ? "text-[#22c55e]" : "text-[#94a3b8] hover:text-[#f1f5f9]"
            }`}
          >
            {tab.label}
            {activeTab === tab.key && (
              <span className="absolute bottom-[-1px] left-0 right-0 h-0.5 bg-[#22c55e]" />
            )}
          </button>
        ))}
      </div>

      <div className="flex-1">
        {list.length === 0 ? (
          <div className="text-sm text-[#94a3b8]">暂无榜单数据。</div>
        ) : (
          list.map((player, idx) => (
            <LeaderRow
              key={`${player.player_id}-${activeTab}`}
              player={player}
              index={idx}
              maxValue={maxValue}
              formatValue={formatValue}
            />
          ))
        )}
      </div>
    </div>
  );
}

function LeaderRow({
  player,
  index,
  maxValue,
  formatValue,
}: {
  player: WorldCupLeaderItem;
  index: number;
  maxValue: number;
  formatValue: (val: number) => string;
}) {
  const identity = getTeamIdentity(player.team_name);
  const displayName = getPlayerNameLabel(player.name);

  return (
    <div className="relative flex h-10 items-center border-b border-[#23262d]/50">
      <div
        className="absolute left-0 top-0 h-full bg-[#22c55e]/10"
        style={{ width: `${(player.value / maxValue) * 100}%` }}
      />
      <div className="relative w-6 flex-shrink-0 text-right font-mono text-sm text-[#64748b]">
        {String(index + 1).padStart(2, "0")}
      </div>
      <div className="relative ml-3 flex h-7 w-7 flex-shrink-0 items-center justify-center bg-[#1a1f2e]">
        <span className="text-[10px] font-bold text-[#64748b]">{displayName.charAt(0)}</span>
      </div>
      <div className="relative ml-3 min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-[#f1f5f9]">{displayName}</div>
        <div className="truncate text-xs text-[#94a3b8]">
          {player.team_name ? identity.displayName : "未知球队"}
        </div>
      </div>
      <div className="relative ml-4 font-mono font-bold text-[#f1f5f9]">{formatValue(player.value)}</div>
    </div>
  );
}
