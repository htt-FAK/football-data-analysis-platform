import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";

import { repairPossiblyMojibake } from "@/lib/text";

interface MermaidDiagramProps {
  chart: string;
  className?: string;
}

let mermaidInitialized = false;

function ensureMermaid() {
  if (mermaidInitialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    suppressErrorRendering: true,
    themeVariables: {
      background: "#0d0f12",
      primaryColor: "#163124",
      primaryTextColor: "#f1f5f9",
      primaryBorderColor: "#22c55e",
      lineColor: "#64748b",
      tertiaryColor: "#111827",
      fontFamily: "Inter, system-ui, sans-serif",
    },
  });
  mermaidInitialized = true;
}

function cleanupMermaidLine(line: string): string {
  return line
    .replace(/\r/g, "")
    .replace(/\t/g, "  ")
    .replace(/[锛汇€怾]/g, "[")
    .replace(/[锛姐€慮]/g, "]")
    .replace(/[锛圿]/g, "(")
    .replace(/[锛塢]/g, ")")
    .replace(/[鈥溾€漖]/g, '"')
    .replace(/[鈥樷€橾]/g, "'")
    .trimEnd();
}

function quoteMindmapLine(line: string): string {
  const trimmed = line.trim();
  if (!trimmed || /^mindmap$/i.test(trimmed) || /^root\(\(/i.test(trimmed)) {
    return line;
  }

  const indentMatch = line.match(/^\s*/);
  const indent = indentMatch?.[0] ?? "";
  const content = trimmed.replace(/^["']|["']$/g, "").trim();
  if (!content) return line;
  return `${indent}"${content.replace(/"/g, "'")}"`;
}

function decodeEscapedWhitespace(text: string): string {
  return text
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "  ");
}

function normalizeMermaidChart(chart: string): string {
  const repaired = decodeEscapedWhitespace(repairPossiblyMojibake(chart));
  const cleaned = repaired
    .replace(/^```mermaid\s*/i, "")
    .replace(/```$/i, "")
    .trim();

  return cleaned
    .split("\n")
    .map(cleanupMermaidLine)
    .map(quoteMindmapLine)
    .filter(Boolean)
    .join("\n")
    .trim();
}

function parseMindmapPoints(rawText: string): { title: string; points: string[] } {
  const source = decodeEscapedWhitespace(repairPossiblyMojibake(rawText))
    .replace(/^```mermaid\s*/i, "")
    .replace(/```$/i, "")
    .replace(/\r/g, "")
    .trim();

  const lines = source
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const titleMatch = source.match(/root\(\((.*?)\)\)/);
  const title = titleMatch?.[1]?.trim() || "比赛预测";

  const points = lines
    .filter((line) => !/^mindmap$/i.test(line))
    .filter((line) => !/^root\(\(/i.test(line))
    .map((line) => line.replace(/^[-*]\s*/, "").replace(/^["']|["']$/g, "").trim())
    .filter(Boolean)
    .filter((line) => !/^(subgraph|end)$/i.test(line))
    .slice(0, 12);

  return {
    title,
    points:
      points.length > 0
        ? points
        : ["模型已生成摘要", "原始 Mermaid 语法不完整", "已自动回退到简化展示"],
  };
}

function buildFallbackMindmap(rawText: string): string {
  const { title, points } = parseMindmapPoints(rawText);
  return [
    "mindmap",
    `  root(("${title.replace(/"/g, "'")}"))`,
    ...points.map((point) => `    ${point.replace(/"/g, "'")}`),
  ].join("\n");
}

function stripMermaidErrorArtifacts() {
  if (typeof document === "undefined") return;
  const selectors = [
    'svg[aria-roledescription="error"]',
    'g[aria-roledescription="error"]',
    '[id^="dmermaid"]',
    ".mermaid-error",
    ".error-icon",
    ".error-text",
  ];
  selectors.forEach((selector) => {
    document.querySelectorAll(selector).forEach((node) => node.remove());
  });
  document.querySelectorAll("body > div, body > pre, body > svg").forEach((node) => {
    const text = node.textContent?.trim().toLowerCase() || "";
    if (text.includes("syntax error in text") && text.includes("version")) {
      node.remove();
    }
  });
}

export function MermaidDiagram({ chart, className }: MermaidDiagramProps) {
  const reactId = useId();
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function renderWithFallback(primaryChart: string) {
      ensureMermaid();
      stripMermaidErrorArtifacts();

      const candidates = [primaryChart, buildFallbackMindmap(chart)];
      for (let index = 0; index < candidates.length; index += 1) {
        const source = candidates[index];
        if (!source) continue;
        const renderId = `mermaid-${reactId.replace(/[:]/g, "")}-${index}`;
        try {
          const valid = await mermaid.parse(source, { suppressErrors: true });
          if (valid === false) continue;
          const { svg: rendered } = await mermaid.render(renderId, source);
          stripMermaidErrorArtifacts();
          if (!cancelled) {
            setSvg(rendered);
            setError("");
          }
          return;
        } catch {
          stripMermaidErrorArtifacts();
        }
      }

      if (!cancelled) {
        setSvg("");
        setError("思维导图语法暂时无法稳定渲染，已保留源码内容。");
      }
    }

    async function renderChart() {
      if (!chart?.trim()) {
        setSvg("");
        setError("");
        return;
      }

      const normalizedChart = normalizeMermaidChart(chart);
      await renderWithFallback(normalizedChart);
    }

    void renderChart();

    return () => {
      cancelled = true;
      stripMermaidErrorArtifacts();
    };
  }, [chart, reactId]);

  if (error) {
    return (
      <div className={className}>
        <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-300">
          {error}
        </div>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className={className}>
        <div className="flex min-h-[280px] items-center justify-center rounded border border-[#1a1f2e] bg-[#0f1419] text-sm text-[#64748b]">
          正在渲染思维导图...
        </div>
      </div>
    );
  }

  return <div className={className} suppressHydrationWarning dangerouslySetInnerHTML={{ __html: svg }} />;
}
