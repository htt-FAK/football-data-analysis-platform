import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getWorldCupSummary, getWorldCupTeams } from "@/api/worldcup";
import { getGroupLabel, getTeamIdentity } from "@/lib/utils";
import type { WorldCupSummary, WorldCupTeam } from "@/types";

const ALL_GROUPS_LABEL = "全部";

export function WCStandings() {
  const [activeGroup, setActiveGroup] = useState<string>(ALL_GROUPS_LABEL);

  const { data: summary } = useQuery<WorldCupSummary>({
    queryKey: ["worldcup-summary"],
    queryFn: () => getWorldCupSummary(),
  });

  const { data: teams = [], isLoading } = useQuery<WorldCupTeam[]>({
    queryKey: ["worldcup-teams", activeGroup],
    queryFn: () => getWorldCupTeams(activeGroup === ALL_GROUPS_LABEL ? undefined : activeGroup),
  });

  const groups = useMemo(() => {
    const summaryGroups = summary?.group_names?.length ? summary.group_names : [];
    const teamGroups = Array.from(new Set(teams.map((team) => team.group))).sort();
    const merged = Array.from(new Set([...summaryGroups, ...teamGroups])).filter(Boolean);
    return [ALL_GROUPS_LABEL, ...merged];
  }, [summary?.group_names, teams]);

  const groupedTeams = teams.reduce<Record<string, WorldCupTeam[]>>((acc, team) => {
    if (!acc[team.group]) {
      acc[team.group] = [];
    }
    acc[team.group].push(team);
    return acc;
  }, {});

  const sortedGroups = Object.keys(groupedTeams).sort();

  return (
    <div className="border-b border-[#23262d] py-12">
      <div className="mx-auto max-w-[1400px] px-4">
        <div className="mb-6 flex items-baseline justify-between">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#f1f5f9]">小组积分榜</h2>
          <span className="text-xs text-[#64748b]">
            {summary?.group_count ?? sortedGroups.length} 个分组 / {summary?.team_count ?? teams.length} 支球队
          </span>
        </div>

        <div className="mb-6 flex flex-wrap gap-0 border-b border-[#23262d]">
          {groups.map((group) => (
            <button
              key={group}
              onClick={() => setActiveGroup(group)}
              className={`relative px-4 py-2 text-xs font-medium uppercase tracking-wider transition-colors ${
                activeGroup === group ? "text-[#22c55e]" : "text-[#94a3b8] hover:text-[#f1f5f9]"
              }`}
            >
              {group === ALL_GROUPS_LABEL ? ALL_GROUPS_LABEL : getGroupLabel(group)}
              {activeGroup === group && (
                <span className="absolute bottom-[-1px] left-0 right-0 h-0.5 bg-[#22c55e]" />
              )}
            </button>
          ))}
        </div>

        {isLoading && teams.length === 0 ? (
          <div className="text-sm text-[#94a3b8]">正在加载小组积分榜...</div>
        ) : sortedGroups.length === 0 ? (
          <div className="text-sm text-[#94a3b8]">本地后端暂未返回世界杯积分榜数据。</div>
        ) : (
          <div className="space-y-8">
            {sortedGroups.map((group) => (
              <div key={group}>
                <div className="mb-3 text-xs font-bold uppercase tracking-wider text-[#64748b]">
                  {getGroupLabel(group)}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#23262d]">
                        <th className="w-10 pr-2 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          #
                        </th>
                        <th className="py-2 text-left text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          球队
                        </th>
                        <th className="w-12 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          P
                        </th>
                        <th className="w-12 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          W
                        </th>
                        <th className="w-12 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          D
                        </th>
                        <th className="w-12 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          L
                        </th>
                        <th className="w-14 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          GF
                        </th>
                        <th className="w-14 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          GA
                        </th>
                        <th className="w-14 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          GD
                        </th>
                        <th className="w-14 py-2 text-right text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
                          Pts
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {groupedTeams[group]
                        .slice()
                        .sort((a, b) => b.points - a.points || b.goal_diff - a.goal_diff || a.rank - b.rank)
                        .map((team, idx) => (
                          <tr
                            key={team.team_id}
                            className={`h-9 border-b border-[#23262d]/50 ${
                              idx < 2 ? "border-l-2 border-[#22c55e]" : "border-l-2 border-transparent"
                            }`}
                          >
                            <td className="pr-2">
                              <span className="block text-right font-mono text-[#64748b]">
                                {String(team.rank || idx + 1).padStart(2, "0")}
                              </span>
                            </td>
                            <td className="pl-2 font-medium text-[#f1f5f9]">
                              {getTeamIdentity(team.name).displayName}
                            </td>
                            <td className="text-right font-mono text-[#94a3b8]">{team.played}</td>
                            <td className="text-right font-mono text-[#f1f5f9]">{team.wins}</td>
                            <td className="text-right font-mono text-[#94a3b8]">{team.draws}</td>
                            <td className="text-right font-mono text-[#94a3b8]">{team.losses}</td>
                            <td className="text-right font-mono text-[#f1f5f9]">{team.goals_for}</td>
                            <td className="text-right font-mono text-[#94a3b8]">{team.goals_against}</td>
                            <td className="text-right font-mono">
                              <span
                                className={
                                  team.goal_diff > 0
                                    ? "text-[#22c55e]"
                                    : team.goal_diff < 0
                                      ? "text-[#ef4444]"
                                      : "text-[#94a3b8]"
                                }
                              >
                                {team.goal_diff > 0 ? `+${team.goal_diff}` : team.goal_diff}
                              </span>
                            </td>
                            <td className="text-right font-mono font-bold text-[#f1f5f9]">{team.points}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
