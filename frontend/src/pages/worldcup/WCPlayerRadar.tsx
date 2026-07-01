import { useQuery } from "@tanstack/react-query";

import { getWorldCupLeaders, getWorldCupPlayerRadar } from "@/api/worldcup";
import { RadarChart } from "@/components/charts/RadarChart";
import { getPositionDimensions } from "@/lib/position-dimensions";
import { getPlayerNameLabel, getRadarDimensionLabels, getTeamIdentity } from "@/lib/utils";
import type { RadarData, WorldCupLeaderItem, WorldCupLeaders } from "@/types";

function positionLabel(position?: string) {
  switch (position) {
    case "FW":
      return "前锋";
    case "MF":
      return "中场";
    case "DF":
      return "后卫";
    case "GK":
      return "门将";
    default:
      return position || "球员";
  }
}

export function WCPlayerRadar() {
  const { data: leaders } = useQuery<WorldCupLeaders>({
    queryKey: ["worldcup-leaders"],
    queryFn: () => getWorldCupLeaders(10),
  });

  const topPlayer: WorldCupLeaderItem | undefined = leaders?.top_ratings?.[0];

  const { data: radarData, isError } = useQuery<RadarData>({
    queryKey: ["worldcup-player-radar", topPlayer?.player_id],
    queryFn: () => getWorldCupPlayerRadar(topPlayer!.player_id),
    enabled: !!topPlayer,
    retry: false,
  });

  const position = radarData?.position || topPlayer?.position || "FW";
  const dimensions = radarData?.dimensions?.length
    ? getRadarDimensionLabels(radarData.dimensions)
    : getPositionDimensions(position);
  const teamIdentity = getTeamIdentity(topPlayer?.team_name);
  const displayName = getPlayerNameLabel(topPlayer?.name);

  const playerValues = radarData?.values ?? [];
  const medianValues = radarData?.median_values ?? [];
  const hasRadar = playerValues.length === dimensions.length && playerValues.length > 0;
  const hasMedian = medianValues.length === dimensions.length && medianValues.some((value) => Number(value) > 0);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-6 flex items-baseline justify-between">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[#f1f5f9]">最佳评分球员</h2>
        <span className="text-xs text-[#64748b]">评分榜首</span>
      </div>

      {!topPlayer ? (
        <div className="text-sm text-[#94a3b8]">暂无评分球员数据。</div>
      ) : (
        <div className="flex flex-1 flex-col gap-6 md:flex-row">
          <div className="md:w-48 flex-shrink-0">
            <div className="mb-4 flex h-16 w-16 items-center justify-center bg-[#1a1f2e]">
              <span className="text-2xl font-bold text-[#64748b]">{displayName.charAt(0)}</span>
            </div>
            <div className="mb-1 text-xl font-bold text-[#f1f5f9]">{displayName}</div>
            <div className="mb-4 text-sm text-[#94a3b8]">
              {positionLabel(position)} · {topPlayer.team_name ? teamIdentity.displayName : "未知球队"}
            </div>
            <div className="font-mono text-3xl font-black text-[#eab308]">{topPlayer.value.toFixed(1)}</div>
            <div className="mt-1 text-xs uppercase tracking-wider text-[#64748b]">评分</div>
          </div>

          <div className="min-h-[280px] flex-1">
            {hasRadar ? (
              <RadarChart
                dimensions={dimensions}
                series={[
                  {
                    name: displayName,
                    values: playerValues,
                    color: "#22c55e",
                    lineStyle: "solid",
                    areaOpacity: 0.15,
                  },
                  {
                    name: "同位置中位数",
                    values: hasMedian ? medianValues : new Array(dimensions.length).fill(0),
                    color: "#64748b",
                    lineStyle: "dashed",
                    areaOpacity: 0,
                  },
                ]}
                max={100}
                height={280}
                showLegend={false}
              />
            ) : (
              <div className="flex h-full min-h-[280px] items-center justify-center border border-[#23262d] text-sm text-[#94a3b8]">
                {isError ? "该球员的雷达指标暂不可用。" : "正在等待雷达指标..."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
