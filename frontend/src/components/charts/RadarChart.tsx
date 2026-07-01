import ReactECharts from "echarts-for-react";
import { useMemo } from "react";

export interface RadarSeries {
  name: string;
  values: number[];
  color?: string;
  lineStyle?: "solid" | "dashed";
  areaOpacity?: number;
}

interface RadarChartProps {
  dimensions: string[];
  series: RadarSeries[];
  max?: number;
  height?: number | string;
  showLegend?: boolean;
}

const DEFAULT_COLORS = [
  "#22c55e",
  "#38bdf8",
  "#94a3b8",
  "#f59e0b",
  "#f43f5e",
];

export function RadarChart({
  dimensions,
  series,
  max = 100,
  height = 380,
  showLegend = true,
}: RadarChartProps) {
  const safeDimensions = dimensions.filter(Boolean);
  const safeSeries = series
    .map((item) => ({
      ...item,
      values: item.values
        .slice(0, safeDimensions.length)
        .map((value) => (Number.isFinite(value) ? value : 0)),
    }))
    .filter((item) => item.values.length === safeDimensions.length && item.values.length > 0);

  const option = useMemo(() => {
    const indicator = safeDimensions.map((d) => ({ name: d, max, min: 0 }));
    return {
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(20, 22, 30, 0.95)",
        borderColor: "rgba(255,255,255,0.1)",
        textStyle: { color: "#e2e8f0", fontSize: 12 },
      },
      legend: showLegend
        ? {
            data: safeSeries.map((s) => s.name),
            textStyle: { color: "#94a3b8", fontSize: 12 },
            bottom: 0,
            itemGap: 20,
          }
        : undefined,
      radar: {
        indicator,
        shape: "polygon",
        radius: "65%",
        center: ["50%", "48%"],
        splitNumber: 5,
        axisName: {
          color: "#94a3b8",
          fontSize: 11,
          fontWeight: 500,
        },
        splitLine: {
          lineStyle: { color: "rgba(148,163,184,0.15)" },
        },
        splitArea: {
          areaStyle: {
            color: ["rgba(148,163,184,0.02)", "rgba(148,163,184,0.05)"],
          },
        },
        axisLine: {
          lineStyle: { color: "rgba(148,163,184,0.2)" },
        },
      },
      series: [
        {
          type: "radar",
          data: safeSeries.map((s, i) => ({
            value: s.values,
            name: s.name,
            symbol: "circle",
            symbolSize: 4,
            lineStyle: {
              width: s.lineStyle === "dashed" ? 2 : 2.5,
              type: s.lineStyle || "solid",
              color: s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
            },
            areaStyle: {
              color: s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
              opacity: s.areaOpacity ?? (s.lineStyle === "dashed" ? 0.05 : 0.15),
            },
            itemStyle: {
              color: s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
            },
          })),
        },
      ],
    };
  }, [safeDimensions, safeSeries, max, showLegend]);

  if (safeDimensions.length === 0 || safeSeries.length === 0) {
    return <div style={{ height, width: "100%" }} />;
  }

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
    />
  );
}
