import ReactECharts from "echarts-for-react";
import { useMemo } from "react";

export interface BarChartSeries {
  name: string;
  values: number[];
  color?: string;
}

interface BarChartProps {
  categories: string[];
  series: BarChartSeries[];
  height?: number;
  horizontal?: boolean;
  showLabel?: boolean;
}

const DEFAULT_COLOR = "#22c55e";

export function BarChart({
  categories,
  series,
  height = 300,
  horizontal = false,
  showLabel = false,
}: BarChartProps) {
  const option = useMemo(() => {
    const categoryAxis = {
      type: "category" as const,
      data: categories,
      axisLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
      axisTick: { show: false },
      axisLabel: { color: "#94a3b8", fontSize: 11, interval: 0 },
    };
    const valueAxis = {
      type: "value" as const,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
      splitLine: { lineStyle: { color: "rgba(148,163,184,0.1)" } },
    };

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(20,22,30,0.95)",
        borderColor: "rgba(255,255,255,0.1)",
        textStyle: { color: "#e2e8f0", fontSize: 12 },
      },
      grid: horizontal
        ? { left: 8, right: 40, top: 16, bottom: 8, containLabel: true }
        : { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
      xAxis: horizontal ? valueAxis : categoryAxis,
      yAxis: horizontal ? categoryAxis : valueAxis,
      series: series.map((s) => ({
        name: s.name,
        type: "bar" as const,
        data: s.values,
        itemStyle: {
          color: s.color || DEFAULT_COLOR,
          borderRadius: horizontal ? [0, 2, 2, 0] : [2, 2, 0, 0],
        },
        label: {
          show: showLabel,
          position: horizontal ? "right" : "top",
          color: "#e2e8f0",
          fontSize: 11,
          fontWeight: 600,
        },
        barMaxWidth: 28,
      })),
    };
  }, [categories, series, horizontal, showLabel]);

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
    />
  );
}
