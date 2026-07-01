import ReactECharts from "echarts-for-react";
import { useMemo } from "react";

export interface DonutChartData {
  name: string;
  value: number;
  color?: string;
}

interface DonutChartProps {
  data: DonutChartData[];
  height?: number;
  centerLabel?: string;
  centerValue?: string;
}

const DEFAULT_COLORS = ["#64748b", "#22c55e", "#38bdf8"];

export function DonutChart({
  data,
  height = 300,
  centerLabel,
  centerValue,
}: DonutChartProps) {
  const option = useMemo(() => {
    return {
      backgroundColor: "transparent",
      title: centerValue
        ? {
            text: centerValue,
            subtext: centerLabel,
            left: "center",
            top: "40%",
            textStyle: {
              color: "#e2e8f0",
              fontSize: 26,
              fontWeight: 700,
            },
            subtextStyle: {
              color: "#94a3b8",
              fontSize: 11,
            },
          }
        : undefined,
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(20,22,30,0.95)",
        borderColor: "rgba(255,255,255,0.1)",
        textStyle: { color: "#e2e8f0", fontSize: 12 },
        formatter: "{b}: {c} ({d}%)",
      },
      legend: {
        bottom: 0,
        textStyle: { color: "#94a3b8", fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 20,
      },
      series: [
        {
          type: "pie" as const,
          radius: ["45%", "70%"],
          center: ["50%", "45%"],
          avoidLabelOverlap: false,
          label: { show: false },
          labelLine: { show: false },
          itemStyle: {
            borderColor: "rgba(20,22,30,1)",
            borderWidth: 2,
          },
          data: data.map((d, i) => ({
            name: d.name,
            value: d.value,
            itemStyle: {
              color: d.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
            },
          })),
        },
      ],
    };
  }, [data, centerLabel, centerValue]);

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
    />
  );
}
