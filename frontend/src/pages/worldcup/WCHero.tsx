import { useQuery } from "@tanstack/react-query";

import { getWorldCupSummary } from "@/api/worldcup";
import type { WorldCupSummary } from "@/types";

export function WCHero() {
  const { data, isLoading } = useQuery<WorldCupSummary>({
    queryKey: ["worldcup-summary"],
    queryFn: () => getWorldCupSummary(),
  });

  const averagePlayersPerTeam =
    data && data.team_count > 0 ? (data.player_count / data.team_count).toFixed(1) : null;

  return (
    <div className="border-b border-[#23262d] py-12">
      <div className="mx-auto max-w-[1400px] px-4">
        <div className="mb-8 flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-[0.25em] text-[#64748b]">2026 世界杯</span>
          <span className="text-[10px] uppercase tracking-[0.25em] text-[#64748b]">本地后端总览</span>
        </div>

        <div className="flex flex-col items-start justify-between gap-8 md:flex-row md:items-end">
          <div>
            <div className="font-mono text-7xl font-black tracking-tighter text-[#f1f5f9] md:text-8xl">
              {data?.player_count ?? "--"}
            </div>
            <div className="mt-2 text-[10px] uppercase tracking-[0.2em] text-[#64748b]">球员记录</div>
          </div>

          <div className="flex gap-8 md:gap-12">
            <div className="text-right">
              <div className="font-mono text-3xl font-bold text-[#f1f5f9] md:text-4xl">
                {data?.match_count ?? "--"}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-[#64748b]">比赛场次</div>
            </div>
            <div className="text-right">
              <div className="font-mono text-3xl font-bold text-[#f1f5f9] md:text-4xl">
                {data?.team_count ?? "--"}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-[#64748b]">球队数量</div>
            </div>
            <div className="text-right">
              <div className="font-mono text-3xl font-bold text-[#22c55e] md:text-4xl">
                {data?.finished_match_count ?? "--"}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-[#64748b]">已完赛</div>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-[#23262d] pt-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="h-px w-16 bg-[#23262d]" />
            <span className="text-sm text-[#94a3b8]">
              分组 <span className="font-mono font-bold text-[#f1f5f9]">{data?.group_count ?? "--"}</span>
            </span>
            <div className="h-px w-16 bg-[#23262d]" />
          </div>
          <div className="text-sm text-[#94a3b8]">
            {isLoading && !data
              ? "正在连接本地后端..."
              : averagePlayersPerTeam
                ? `场均球员数 ${averagePlayersPerTeam}`
                : "世界杯汇总暂不可用"}
          </div>
        </div>
      </div>
    </div>
  );
}
