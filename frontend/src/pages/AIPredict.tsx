import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  ExternalLink,
  Globe,
  Loader2,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";

import { getWorldCupUpcomingFixtures } from "@/api/leagues";
import { getPrediction, getPredictableMatches, triggerPrediction } from "@/api/predict";
import { useLiveScore } from "@/hooks/useLiveScore";
import { MermaidDiagram } from "@/components/charts/MermaidDiagram";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, LoadingState } from "@/components/ui/stat-card";
import { repairPossiblyMojibake, repairTextList } from "@/lib/text";
import {
  cn,
  formatWorldCupDateLabel,
  getStageLabel,
  getTeamIdentity,
  getWorldCupMatchTime,
  isWorldCupDateToday,
} from "@/lib/utils";
import { useGlobalStore } from "@/stores/global";
import type {
  MatchPredictionResponse,
  PredictionAccuracyLevel,
  PredictionAccuracySummary,
  PredictableMatch,
  PredictionRound,
  WorldCupUpcomingMatch,
} from "@/types";

const SEASON = "2026";

const INTERNAL_TEXT_PATTERNS = [
  /home_win_prob|draw_prob|away_win_prob|predicted_home_score|predicted_away_score/gi,
  /conservative_verdict|aggressive_verdict|key_reasons|thinking|reasoning/gi,
  /search_results|tool_calls|annotations|citations/gi,
  /json|schema|markdown/gi,
  /mermaid|结构化结论损坏|完整 json|已提取/gi,
  /cannot browse|unable to browse|simulate search|无法联网|模拟搜索/gi,
  /^snippet=/i,
];

const JSONISH_LINE_PREFIX =
  /^["'{\[]|^(home_win_prob|draw_prob|away_win_prob|predicted_home_score|predicted_away_score|conservative_verdict|aggressive_verdict|confidence|thinking|mermaid_mindmap)\b/i;

function truncateReadableText(text: string, maxLength = 220): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength).trim()}...`;
}

function isReadableNarrativeLine(line: string): boolean {
  if (!line) return false;
  if (JSONISH_LINE_PREFIX.test(line)) return false;
  if (line.length < 4) return false;
  if (!/[\u4e00-\u9fffA-Za-z]/.test(line)) return false;
  return !INTERNAL_TEXT_PATTERNS.some((pattern) => pattern.test(line));
}

function isFinishedLikeStatus(status?: string | null, kickoff?: string | null): boolean {
  if ((status || "").toLowerCase() === "finished") return true;
  if (!kickoff) return false;
  const kickoffTime = getWorldCupMatchTime(kickoff, null);
  if (!Number.isFinite(kickoffTime) || kickoffTime === Number.MAX_SAFE_INTEGER) return false;
  return Date.now() >= kickoffTime + 4 * 60 * 60 * 1000;
}

function resolvePredictionMatchStatus(
  status?: string | null,
  kickoff?: string | null
): "scheduled" | "result_pending" | "finished" | "live" | "in_progress" | "half_time" | string {
  const normalized = (status || "").trim().toLowerCase();
  if (normalized && normalized !== "scheduled" && normalized !== "not_started") {
    return normalized;
  }
  if (!kickoff) return normalized || "scheduled";

  const kickoffTime = getWorldCupMatchTime(kickoff, null);
  if (!Number.isFinite(kickoffTime) || kickoffTime === Number.MAX_SAFE_INTEGER) {
    return normalized || "scheduled";
  }

  if (Date.now() >= kickoffTime + 3 * 60 * 60 * 1000) {
    return "result_pending";
  }
  return normalized || "scheduled";
}

function normalizeReadableText(text?: string | null): string {
  const repaired = repairPossiblyMojibake(text);
  if (!repaired) return "";

  return repaired
    .replace(/\r/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/\*\*/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) =>
      line
        .replace(/^[-*]\s+/, "")
        .replace(/\[advantage\]/gi, "优势")
        .replace(/\[risk\]/gi, "风险")
        .replace(/\[possible\]/gi, "可能")
        .replace(/\[very low\]/gi, "极低")
        .replace(/^step\s*\d+[:：]?\s*/i, "")
        .replace(/^round\s*\d+[:：]?\s*/i, "")
        .replace(/^analysis[:：]?\s*/i, "")
        .replace(/^reasoning[:：]?\s*/i, "")
        .replace(/^summary[:：]?\s*/i, "")
        .replace(/^scenario[:：]?\s*/i, "情景：")
        .replace(/^key factors?[:：]?\s*/i, "关键因素：")
        .replace(/^predicted score[:：]?\s*/i, "预测比分：")
        .replace(/^analysis result[:：]?\s*/i, "")
        .replace(/^分析结果[:：]?\s*/i, "")
        .replace(/^总结[:：]?\s*/i, "")
        .replace(/^其他[:：]?\s*/i, "")
        .replace(/^场地天气[:：]?\s*/i, "场地与天气：")
        .replace(/^球迷氛围[:：]?\s*/i, "球迷氛围：")
        .replace(/^教练态度[:：]?\s*/i, "教练态度：")
        .replace(/^球员状态[:：]?\s*/i, "球员状态：")
        .replace(/^阵容\/阵型[:：]?\s*/i, "阵容与阵型：")
        .replace(/\s{2,}/g, " ")
        .trim()
    )
    .filter(isReadableNarrativeLine)
    .join("\n")
    .trim();
}

function splitReadablePoints(text?: string | null): string[] {
  const normalized = normalizeReadableText(text);
  if (!normalized) return [];
  return normalized
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => truncateReadableText(line, 180))
    .slice(0, 8);
}

function cleanPredictionText(text?: string | null): string {
  return normalizeReadableText(text) || repairPossiblyMojibake(text) || "--";
}

function isPlaceholderPredictionText(text?: string | null): boolean {
  const normalized = repairPossiblyMojibake(text).trim().toLowerCase();
  if (!normalized) return true;
  const exactMatches = [
    "结构化结论损坏，暂按保守平局兜底。",
    "等待下一轮或裁决轮给出更明确方向。",
    "已提取 mermaid 导图，但未获得完整 json 结论",
    "历史预测结论保留不完整，请优先参考比分概率和关键依据。",
    "该场历史预测的激进结论未完整保存。",
    "历史预测文本保留不完整，已优先展示仍可参考的结构化结果。",
  ].some((item) => normalized === item.toLowerCase());
  if (exactMatches) return true;
  return [
    "结构化结论损坏",
    "暂按保守平局兜底",
    "等待下一轮或裁决轮",
    "未获得完整 json 结论",
    "已提取 mermaid 导图",
    "历史预测结论保留不完整",
    "激进结论未完整保存",
    "历史预测文本保留不完整",
  ].some((fragment) => normalized.includes(fragment.toLowerCase()));
}

function presentPredictionText(text?: string | null, fallback = "模型已给出倾向，但这条历史结论保留得不够完整。"): string {
  if (isPlaceholderPredictionText(text)) return fallback;
  return cleanPredictionText(text);
}

function isFallbackQualityPrediction(prediction?: MatchPredictionResponse | null): boolean {
  if (!prediction) return false;
  const hasPlaceholderVerdict =
    isPlaceholderPredictionText(prediction.conservative_verdict) ||
    isPlaceholderPredictionText(prediction.aggressive_verdict);
  const equalProbability =
    Math.round(prediction.home_win_prob ?? 0) === 33 &&
    Math.round(prediction.draw_prob ?? 0) === 33 &&
    Math.round(prediction.away_win_prob ?? 0) === 33;
  const partialArbiter = (prediction.rounds ?? []).some(
    (round) => round.round === 4 && round.status === "partial"
  );
  return hasPlaceholderVerdict || (equalProbability && partialArbiter);
}

function isFallbackQualityRound(round: PredictionRound): boolean {
  const conclusion = round.conclusion || {};
  const conservative = round.conservative_verdict ?? (conclusion.conservative_verdict as string | undefined);
  const aggressive = round.aggressive_verdict ?? (conclusion.aggressive_verdict as string | undefined);
  const homeProb = (round.home_win_prob ?? (conclusion.home_win_prob as number | undefined)) as number | undefined;
  const drawProb = (round.draw_prob ?? (conclusion.draw_prob as number | undefined)) as number | undefined;
  const awayProb = (round.away_win_prob ?? (conclusion.away_win_prob as number | undefined)) as number | undefined;

  const hasPlaceholderVerdict =
    isPlaceholderPredictionText(conservative) || isPlaceholderPredictionText(aggressive);
  const equalProbability =
    Math.round(homeProb ?? 0) === 33 &&
    Math.round(drawProb ?? 0) === 33 &&
    Math.round(awayProb ?? 0) === 33;

  return hasPlaceholderVerdict || (round.status === "partial" && equalProbability);
}

function getPredictionCardSummary(item?: PredictableMatch | null): string | null {
  if (!item?.conservative_verdict) return null;
  if (isPlaceholderPredictionText(item.conservative_verdict)) {
    return item.match_status === "finished"
      ? "这场比赛已保留历史预测比分和核心摘要，点开可继续查看。"
      : "这场比赛的预测已经生成，点开可查看完整分析。";
  }
  return presentPredictionText(
    item.conservative_verdict,
    item.match_status === "finished"
      ? "这场历史预测的完整结论保留不够完整，建议点开查看多轮分析摘要。"
      : "这场预测已经生成，但当前展示摘要还不够完整。"
  );
}

function mergeHistoricalIntoUpcoming(
  match: WorldCupUpcomingMatch,
  predicted?: PredictableMatch | null
): WorldCupUpcomingMatch {
  if (!predicted) return match;

  return {
    ...match,
    status: resolvePredictionMatchStatus(predicted.match_status ?? match.status, predicted.kickoff ?? match.match_date ?? null),
    home_score: predicted.predicted_home_score ?? match.home_score,
    away_score: predicted.predicted_away_score ?? match.away_score,
  };
}

function presentKeyReasons(reasons: string[] | null | undefined): string[] {
  const cleaned = repairTextList(reasons);
  const useful = cleaned.filter((item) => !isPlaceholderPredictionText(item));
  if (useful.length > 0) return useful;
  return [];
}

function shouldRenderMindmap(prediction?: MatchPredictionResponse | null): boolean {
  const chart = repairPossiblyMojibake(prediction?.mermaid_mindmap);
  return Boolean(chart && chart.trim());
}

function getFriendlyRoundError(error?: string | null): string | null {
  const text = repairPossiblyMojibake(error);
  if (!text) return null;
  const normalized = text.toLowerCase();

  if (normalized.includes("结构化解析未完整成功")) {
    return "这一轮只保留了部分可参考内容。";
  }
  if (normalized.includes("json") || normalized.includes("snippet=") || normalized.includes("expecting value")) {
    return "这一轮输出不够稳定，页面已整理成精简摘要。";
  }
  if (normalized.includes("http") || normalized.includes("timeout")) {
    return "这一轮外部资料补充不够充分，已优先保留核心判断。";
  }
  return truncateReadableText(text, 120);
}

function getAccuracyVisual(level?: PredictionAccuracyLevel | null) {
  if (level === "score_hit") {
    return {
      label: "命中比分",
      icon: CheckCircle2,
      tone: "border-[#22c55e]/40 bg-[#22c55e]/[0.08] text-[#22c55e]",
      dot: "bg-[#22c55e]",
      chip: "border-[#22c55e]/40 bg-[#22c55e]/[0.08] text-[#22c55e]",
    };
  }
  if (level === "result_hit") {
    return {
      label: "命中胜负",
      icon: Target,
      tone: "border-[#eab308]/40 bg-[#eab308]/[0.08] text-[#eab308]",
      dot: "bg-[#eab308]",
      chip: "border-[#eab308]/40 bg-[#eab308]/[0.08] text-[#eab308]",
    };
  }
  return {
    label: "未中",
    icon: XCircle,
    tone: "border-[#475569]/40 bg-[#475569]/[0.08] text-[#94a3b8]",
    dot: "bg-[#475569]",
    chip: "border-[#475569]/40 bg-[#475569]/[0.08] text-[#94a3b8]",
  };
}

function AccuracyBadge({ accuracy }: { accuracy?: PredictionAccuracySummary | null }) {
  if (!accuracy) return null;
  const visual = getAccuracyVisual(accuracy.level);
  const Icon = visual.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[10px] font-bold",
        visual.chip,
      )}
    >
      <Icon className="h-3 w-3" />
      {accuracy.label || visual.label}
    </span>
  );
}

/** 已结束比赛详情区顶部的命中横幅：预测比分 vs 真实比分 */
function AccuracyBanner({
  accuracy,
  realHome,
  realAway,
  homeName,
  awayName,
}: {
  accuracy: NonNullable<MatchPredictionResponse["accuracy"]>;
  realHome: number | null;
  realAway: number | null;
  homeName: string;
  awayName: string;
}) {
  const visual = getAccuracyVisual(accuracy.level);
  const Icon = visual.icon;
  return (
    <div className={cn("flex flex-col gap-3 rounded-md border p-4 sm:flex-row sm:items-center sm:justify-between", visual.tone)}>
      <div className="flex items-center gap-3">
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full", visual.dot)}>
          <Icon className="h-5 w-5 text-[#0d0f12]" />
        </div>
        <div>
          <div className="text-sm font-bold">{accuracy.label || visual.label}</div>
          <div className="mt-0.5 text-[11px] opacity-80">
            {accuracy.level === "score_hit"
              ? "预测比分与真实比分完全一致"
              : accuracy.level === "result_hit"
                ? `胜负方向判断正确（${accuracy.predicted_outcome === "draw" ? "预测平局" : accuracy.real_outcome === "home_win" ? "主胜" : accuracy.real_outcome === "away_win" ? "客胜" : "平局"}）`
                : "预测方向与真实结果不一致"}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-4 sm:gap-6">
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wider opacity-70">预测比分</div>
          <div className="mt-1 font-mono text-2xl font-black">
            {accuracy.predicted_home} : {accuracy.predicted_away}
          </div>
          <div className="mt-0.5 truncate text-[9px] opacity-60">
            {homeName} v {awayName}
          </div>
        </div>
        <span className="text-lg font-light opacity-40">→</span>
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wider opacity-70">真实比分</div>
          <div className="mt-1 font-mono text-2xl font-black">
            {realHome != null && realAway != null ? `${realHome} : ${realAway}` : "-- : --"}
          </div>
          <div className="mt-0.5 truncate text-[9px] opacity-60">
            {homeName} v {awayName}
          </div>
        </div>
      </div>
    </div>
  );
}

/** 把模型名转成更友好的展示名 */
function getFriendlyModelName(model?: string | null): string | null {
  if (!model) return null;
  const name = model.trim();
  if (!name) return null;
  // 已知模型友好名
  const known: Record<string, string> = {
    "step-3.7-flash": "Step 3.7 Flash",
    "step-1o-turbo-vision": "Step 1o 视觉",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
  };
  return known[name] || name;
}

function getRoundTitle(round: PredictionRound): string {
  switch (round.round) {
    case 0:
      return "视觉情报";
    case 1:
      return "战术与基本面";
    case 2:
      return "场外情报与变量";
    case 3:
      return "综合推理";
    case 4:
      return "最终裁决";
    default:
      return cleanPredictionText(round.focus) || `第 ${round.round} 轮`;
  }
}

function getRoundMetaLabel(round: PredictionRound): string {
  const parts: string[] = [];
  const model = getFriendlyModelName(round.model);
  if (model) parts.push(model);
  if (round.tokens != null) parts.push(`信息量 ${round.tokens}`);
  if (round.cost_ms != null) {
    const seconds = Math.max(1, Math.round(round.cost_ms / 1000));
    parts.push(`处理约 ${seconds} 秒`);
  }
  return parts.join(" · ");
}

/** 每轮是否使用了联网搜索 */
function roundUsesWebSearch(round: PredictionRound): boolean {
  return (round.search_results ?? []).some((result) => result.title || result.url || result.snippet);
}

function getRoundSummary(round: PredictionRound): string {
  const roundError = getFriendlyRoundError(round.error);
  if (roundError) return roundError;

  const candidates = [
    round.conservative_verdict,
    round.aggressive_verdict,
    ...(round.key_reasons ?? []),
    round.thinking,
    round.reasoning,
  ];

  for (const item of candidates) {
    const cleaned = normalizeReadableText(item);
    if (cleaned) return cleaned.split("\n")[0];
  }

  if (round.status === "failed") return "这一轮没有留下可继续参考的结论。";
  if (round.status === "no_json") return "这一轮没有产出稳定摘要，页面已改为精简展示。";
  return "本轮暂时没有可展示摘要。";
}

function TeamBadge({
  teamName,
  align = "left",
}: {
  teamName?: string | null;
  align?: "left" | "right";
}) {
  const identity = getTeamIdentity(teamName);
  const flag = identity.flagUrl ? (
    <img src={identity.flagUrl} alt={identity.displayName} className="h-full w-full object-cover" />
  ) : (
    <span className="text-xs font-bold text-[#64748b]">{identity.displayName.charAt(0) || "?"}</span>
  );

  return (
    <div className={cn("flex min-w-0 items-center gap-2", align === "right" && "justify-end")}>
      {align === "left" && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[#23262d] bg-[#1a1f2e]">
          {flag}
        </div>
      )}
      <span className="truncate text-sm font-medium text-[#f1f5f9]">{identity.displayName}</span>
      {align === "right" && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[#23262d] bg-[#1a1f2e]">
          {flag}
        </div>
      )}
    </div>
  );
}

function getPredictionItemDate(item: WorldCupUpcomingMatch | PredictableMatch): string | null | undefined {
  if ("match_date" in item) return item.match_date;
  return (item as PredictableMatch).kickoff;
}

function ProbabilityBar({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-[#94a3b8]">{label}</span>
        <span className="font-mono font-bold text-[#f1f5f9]">{value}%</span>
      </div>
      <div className="h-2 bg-[#1a1f2e]">
        <div className={cn("h-full transition-all", className)} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function RoundPanel({ round, defaultOpen = false }: { round: PredictionRound; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const isArbiter = round.round === 4;
  const isFailed = round.status === "failed";
  const searchResults = (round.search_results ?? []).filter((result) => result.title || result.url || result.snippet);
  const hasSearch = searchResults.length > 0;
  const conclusion = round.conclusion || {};
  const homeProb = (round.home_win_prob ?? (conclusion.home_win_prob as number | undefined)) as number | undefined;
  const drawProb = (round.draw_prob ?? (conclusion.draw_prob as number | undefined)) as number | undefined;
  const awayProb = (round.away_win_prob ?? (conclusion.away_win_prob as number | undefined)) as number | undefined;
  const conservative = round.conservative_verdict ?? (conclusion.conservative_verdict as string | undefined);
  const aggressive = round.aggressive_verdict ?? (conclusion.aggressive_verdict as string | undefined);
  const thinking = round.thinking ?? (conclusion.thinking as string | undefined);
  const readablePoints = splitReadablePoints(thinking || round.reasoning);
  const summary = getRoundSummary(round);
  const title = getRoundTitle(round);
  const friendlyError = getFriendlyRoundError(round.error);
  const fallbackRound = isFallbackQualityRound(round);
  const hasRealConservative = Boolean(conservative && !isPlaceholderPredictionText(conservative));
  const hasRealAggressive = Boolean(aggressive && !isPlaceholderPredictionText(aggressive));
  const shouldShowRoundNote = Boolean(friendlyError && friendlyError !== summary);

  return (
    <div className={cn("border", isArbiter ? "border-[#22c55e]/40 bg-[#22c55e]/[0.03]" : "border-[#23262d] bg-[#0d0f12]")}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          {open ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-[#64748b]" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-[#64748b]" />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={cn("text-xs font-bold uppercase tracking-wider", isArbiter ? "text-[#22c55e]" : "text-[#f1f5f9]")}>
                {title}
              </span>
              {isFailed ? (
                <Badge variant="danger">失败</Badge>
              ) : isArbiter ? (
                <Badge variant="success">结论</Badge>
              ) : hasSearch ? (
                <Badge variant="gold">参考资料</Badge>
              ) : (
                <Badge variant="outline">推理</Badge>
              )}
            </div>
            <div className="mt-0.5 text-[10px] text-[#64748b]">{getRoundMetaLabel(round) || "本轮分析已完成"}</div>
          </div>
        </div>
        {/* 折叠态：显示模型 + 联网标记 */}
        {!open ? (
          <div className="flex shrink-0 items-center gap-1.5">
            {getFriendlyModelName(round.model) ? (
              <span className="hidden rounded border border-[#1a1f2e] bg-[#0f1419] px-1.5 py-0.5 text-[9px] font-medium text-[#94a3b8] sm:inline">
                {getFriendlyModelName(round.model)}
              </span>
            ) : null}
            {roundUsesWebSearch(round) ? (
              <span className="hidden items-center gap-0.5 text-[9px] font-medium text-[#22c55e] sm:inline-flex">
                <Globe className="h-2.5 w-2.5" /> 联网
              </span>
            ) : (
              <span className="hidden text-[9px] font-medium text-[#64748b] sm:inline">知识库</span>
            )}
          </div>
        ) : null}
        {summary && !open ? (
          <span className="hidden max-w-[48%] truncate text-xs text-[#94a3b8] sm:block">{summary}</span>
        ) : null}
      </button>

      {open ? (
        <div className="space-y-4 border-t border-[#23262d] p-4">
          {/* 展开态顶部：模型 + 联网标记 */}
          <div className="flex flex-wrap items-center gap-2">
            {getFriendlyModelName(round.model) ? (
              <span className="inline-flex items-center gap-1 rounded border border-[#1a1f2e] bg-[#0f1419] px-2 py-0.5 text-[10px] font-medium text-[#cbd5e1]">
                <Brain className="h-3 w-3 text-[#22c55e]" />
                {getFriendlyModelName(round.model)}
              </span>
            ) : null}
            {roundUsesWebSearch(round) ? (
              <span className="inline-flex items-center gap-1 rounded border border-[#22c55e]/30 bg-[#22c55e]/[0.06] px-2 py-0.5 text-[10px] font-medium text-[#22c55e]">
                <Globe className="h-3 w-3" /> 联网搜索
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded border border-[#23262d] bg-[#0f1419] px-2 py-0.5 text-[10px] font-medium text-[#64748b]">
                知识库
              </span>
            )}
          </div>

          <div className="rounded-md border border-[#1a1f2e] bg-[#11161d] p-3">
            <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-[#64748b]">本轮结论</div>
            <p className="text-sm leading-6 text-[#e2e8f0]">{summary}</p>
          </div>

          {(homeProb != null || hasRealConservative || hasRealAggressive) && (
            <div className="grid gap-3 sm:grid-cols-3">
              {homeProb != null && !fallbackRound ? (
                <div className="text-center">
                  <div className="text-[10px] uppercase tracking-wider text-[#64748b]">胜 / 平 / 负</div>
                  <div className="mt-1 font-mono text-sm font-bold text-[#f1f5f9]">
                    {Math.round(homeProb)}% / {Math.round(drawProb ?? 0)}% / {Math.round(awayProb ?? 0)}%
                  </div>
                </div>
              ) : null}
              {hasRealConservative ? (
                <div className="text-center">
                  <div className="text-[10px] uppercase tracking-wider text-[#64748b]">保守判断</div>
                  <div className="mt-1 text-xs text-[#94a3b8]">
                    {cleanPredictionText(conservative)}
                  </div>
                </div>
              ) : null}
              {hasRealAggressive ? (
                <div className="text-center">
                  <div className="text-[10px] uppercase tracking-wider text-[#64748b]">激进判断</div>
                  <div className="mt-1 text-xs text-[#94a3b8]">
                    {cleanPredictionText(aggressive)}
                  </div>
                </div>
              ) : null}
              {fallbackRound ? (
                <div className="text-center sm:col-span-3">
                  <div className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
                    这一轮的结构化裁决不够完整，概率结果已降级隐藏，建议结合下方摘要和来源一起判断。
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {readablePoints.length > 0 ? (
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[#22c55e]">
                <Brain className="h-3 w-3" /> 分析要点
              </div>
              <div className="space-y-2">
                {readablePoints.map((point, index) => (
                  <div
                    key={`${round.round}-${index}`}
                    className="flex items-start gap-2 rounded border border-[#1a1f2e] bg-[#0f1419] px-3 py-2 text-sm text-[#cbd5e1]"
                  >
                    <span className="mt-0.5 font-mono text-[10px] font-bold text-[#22c55e]">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="leading-6">{point}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {hasSearch ? (
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[#eab308]">
                <Search className="h-3 w-3" /> 参考资料（{searchResults.length}）
              </div>
              <div className="space-y-1.5">
                {searchResults.slice(0, 6).map((result, index) => (
                  <a
                    key={`${result.url || result.title || "result"}-${index}`}
                    href={result.url || undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 rounded border border-[#1a1f2e] bg-[#0d0f12] p-2 text-xs transition-colors hover:border-[#22c55e]/40"
                  >
                    <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-[#64748b]" />
                    <div className="min-w-0">
                      <div className="truncate font-medium text-[#cbd5e1]">
                        {cleanPredictionText(result.title || result.url || "搜索结果")}
                      </div>
                      {result.snippet ? (
                        <div className="mt-0.5 line-clamp-2 text-[#64748b]">{cleanPredictionText(result.snippet)}</div>
                      ) : null}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          ) : null}

          {shouldShowRoundNote ? (
            <div className="rounded border border-rose-500/30 bg-rose-500/5 p-2 text-xs text-rose-400">
              说明：{friendlyError}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PredictionListItem({
  label,
  item,
  selected,
  showHistory,
  pending,
  predictedMeta,
  onSelect,
}: {
  label: string;
  item: WorldCupUpcomingMatch | PredictableMatch;
  selected: boolean;
  showHistory?: boolean;
  pending?: boolean;
  predictedMeta?: PredictableMatch | null;
  onSelect: () => void;
}) {
  const homeName = item.home_team_name;
  const awayName = item.away_team_name;
  const kickoff = getPredictionItemDate(item);
  const venue = "venue" in item ? item.venue : null;
  const stage = item.stage ?? null;
  const cardSummary = getPredictionCardSummary(predictedMeta);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full border bg-[#0d0f12] p-4 text-left transition-colors",
        selected ? "border-[#22c55e]" : "border-[#23262d] hover:border-[#22c55e]/50"
      )}
    >
      <div className="mb-3 flex items-center justify-between gap-3 text-[10px] text-[#64748b]">
        <span className="inline-flex items-center gap-1.5">
          <Clock className="h-3 w-3" />
          {formatWorldCupDateLabel(kickoff, venue)}
        </span>
        {showHistory ? (
          <div className="flex items-center gap-1.5">
            {predictedMeta?.accuracy ? <AccuracyBadge accuracy={predictedMeta.accuracy} /> : null}
            <Badge variant="secondary">历史结果</Badge>
          </div>
        ) : pending ? (
          <Badge variant="warning">生成中</Badge>
        ) : predictedMeta?.status === "completed" ? (
          <Badge variant="success">已预测</Badge>
        ) : (
          <Badge variant="outline">{label}</Badge>
        )}
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <TeamBadge teamName={homeName} />
        <span className="font-mono text-xs text-[#64748b]">
          {predictedMeta?.predicted_home_score != null
            ? `${predictedMeta.predicted_home_score}:${predictedMeta.predicted_away_score}`
            : "VS"}
        </span>
        <TeamBadge teamName={awayName} align="right" />
      </div>
      <div className="mt-3 flex items-center gap-3 border-t border-[#23262d]/70 pt-3 text-[10px] text-[#64748b]">
        {venue ? (
          <span className="inline-flex min-w-0 items-center gap-1">
            <MapPin className="h-3 w-3" />
            <span className="truncate">{cleanPredictionText(venue)}</span>
          </span>
        ) : null}
          <span className="inline-flex items-center gap-1">
            <Target className="h-3 w-3" />
            {getStageLabel(stage || "World Cup")}
          </span>
        </div>
      {cardSummary ? (
        <div className="mt-2 line-clamp-2 text-xs leading-5 text-[#94a3b8]">
          {cardSummary}
        </div>
      ) : null}
    </button>
  );
}

export function AIPredict() {
  const [selectedMatchId, setSelectedMatchId] = useState<string>("");
  const [hasUserSelectedMatch, setHasUserSelectedMatch] = useState(false);
  const {
    pendingPredictionMatchIds,
    setPendingPredictionMatchIds,
    addPendingPredictionMatchId,
    removePendingPredictionMatchId,
  } = useGlobalStore();

  const fixturesQuery = useQuery({
    queryKey: ["worldcup-upcoming", SEASON, 50],
    queryFn: () => getWorldCupUpcomingFixtures(SEASON, 50),
    staleTime: 60_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const predictedQuery = useQuery({
    queryKey: ["predicted-matches"],
    queryFn: () => getPredictableMatches(80),
    staleTime: 30_000,
    refetchInterval: pendingPredictionMatchIds.length > 0 ? 8000 : 30_000,
    refetchOnWindowFocus: true,
  });

  const predictedMap = useMemo(() => {
    const map = new Map<string, PredictableMatch>();
    (predictedQuery.data ?? []).forEach((item) => map.set(String(item.match_id), item));
    return map;
  }, [predictedQuery.data]);

  const allUpcomingMatches = useMemo(() => {
    const rows = fixturesQuery.data?.matches ?? [];
    return [...rows].sort(
      (a, b) => getWorldCupMatchTime(a.match_date, a.venue) - getWorldCupMatchTime(b.match_date, b.venue)
    );
  }, [fixturesQuery.data]);

  const playableUpcomingMatches = useMemo(
    () => allUpcomingMatches.filter((match) => !isFinishedLikeStatus(match.status, match.match_date ?? null)),
    [allUpcomingMatches]
  );

  const mergedUpcomingMatches = useMemo(
    () =>
      playableUpcomingMatches.map((match) => {
        const predicted = predictedMap.get(String(match.match_id));
        return mergeHistoricalIntoUpcoming(match, predicted);
      }),
    [playableUpcomingMatches, predictedMap]
  );

  const todayUpcoming = useMemo(
    () => mergedUpcomingMatches.filter((match) => isWorldCupDateToday(match.match_date, match.venue)),
    [mergedUpcomingMatches]
  );

  const displayUpcomingMatches = useMemo(
    () => (todayUpcoming.length > 0 ? todayUpcoming : mergedUpcomingMatches.slice(0, 8)),
    [mergedUpcomingMatches, todayUpcoming]
  );

  const historicalPredictions = useMemo(
    () =>
      (predictedQuery.data ?? []).filter((item) =>
        isFinishedLikeStatus(item.match_status ?? item.status, item.kickoff ?? null)
      ),
    [predictedQuery.data]
  );

  const selectedUpcomingMatch = useMemo(
    () =>
      displayUpcomingMatches.find((item) => String(item.match_id) === selectedMatchId) ??
      displayUpcomingMatches[0] ??
      null,
    [displayUpcomingMatches, selectedMatchId]
  );

  const selectedHistoricalMatch = useMemo(
    () => historicalPredictions.find((item) => String(item.match_id) === selectedMatchId) ?? null,
    [historicalPredictions, selectedMatchId]
  );

  const activeMatchId = selectedHistoricalMatch ? selectedHistoricalMatch.match_id : selectedUpcomingMatch?.match_id;
  const selectedPredictedMeta = activeMatchId != null ? predictedMap.get(String(activeMatchId)) ?? null : null;
  const shouldFetchPrediction = Boolean(activeMatchId && (selectedHistoricalMatch || selectedPredictedMeta));

  const predictionQuery = useQuery<MatchPredictionResponse | null>({
    queryKey: ["prediction", activeMatchId],
    queryFn: () => {
      if (!shouldFetchPrediction || !activeMatchId) {
        return Promise.resolve(null);
      }
      return getPrediction(activeMatchId);
    },
    enabled: shouldFetchPrediction,
    staleTime: 30_000,
    retry: 1,
    refetchInterval:
      shouldFetchPrediction && activeMatchId && pendingPredictionMatchIds.includes(String(activeMatchId)) ? 8000 : false,
  });

  // 实时比分 WebSocket：当前选中比赛有更新时，刷新其预测（重新结算命中等级与真实比分）
  useLiveScore((data) => {
    if (activeMatchId != null && String(data.match_id) === String(activeMatchId)) {
      void predictionQuery.refetch();
      void predictedQuery.refetch();
    }
  });

  useEffect(() => {
    if (!(predictedQuery.data ?? []).length) return;
    const completedIds = new Set(
      (predictedQuery.data ?? [])
        .filter((item) => item.status === "completed")
        .map((item) => String(item.match_id))
    );
    const nextPending = pendingPredictionMatchIds.filter((id) => !completedIds.has(id));
    if (nextPending.length !== pendingPredictionMatchIds.length) {
      setPendingPredictionMatchIds(nextPending);
    }
  }, [pendingPredictionMatchIds, predictedQuery.data, setPendingPredictionMatchIds]);

  useEffect(() => {
    if (!hasUserSelectedMatch) {
      const nextDefault = displayUpcomingMatches[0]?.match_id ?? historicalPredictions[0]?.match_id;
      if (nextDefault != null) setSelectedMatchId(String(nextDefault));
      return;
    }

    const exists =
      historicalPredictions.some((item) => String(item.match_id) === selectedMatchId) ||
      displayUpcomingMatches.some((item) => String(item.match_id) === selectedMatchId);

    if (!exists) {
      const fallback = displayUpcomingMatches[0]?.match_id ?? historicalPredictions[0]?.match_id ?? "";
      setSelectedMatchId(fallback ? String(fallback) : "");
    }
  }, [displayUpcomingMatches, hasUserSelectedMatch, historicalPredictions, selectedMatchId]);

  const activeMatch = selectedHistoricalMatch ?? selectedUpcomingMatch;
  const activePredictedMeta = activeMatch
    ? predictedMap.get(String(activeMatch.match_id)) ?? selectedHistoricalMatch ?? null
    : null;
  const triggering = activeMatch ? pendingPredictionMatchIds.includes(String(activeMatch.match_id)) : false;
  const prediction = predictionQuery.data;
  const predictionError = predictionQuery.isError;
  const isLoadingPrediction = predictionQuery.isLoading && !activePredictedMeta;
  const isFetchingPrediction = predictionQuery.isFetching;
  const isFallbackPrediction = isFallbackQualityPrediction(prediction);
  const selectedHome = getTeamIdentity(activeMatch?.home_team_name);
  const selectedAway = getTeamIdentity(activeMatch?.away_team_name);
  const repairedKeyReasons = presentKeyReasons(prediction?.key_reasons);
  const repairedMindmap = repairPossiblyMojibake(prediction?.mermaid_mindmap);
  const showMindmap = shouldRenderMindmap(prediction);
  const conservativeVerdict =
    prediction && !isPlaceholderPredictionText(prediction.conservative_verdict)
      ? cleanPredictionText(prediction.conservative_verdict)
      : null;
  const aggressiveVerdict =
    prediction && !isPlaceholderPredictionText(prediction.aggressive_verdict)
      ? cleanPredictionText(prediction.aggressive_verdict)
      : null;

  async function handleTrigger() {
    if (!selectedUpcomingMatch?.match_id || triggering) return;

    const key = String(selectedUpcomingMatch.match_id);
    addPendingPredictionMatchId(key);

    try {
      await triggerPrediction(selectedUpcomingMatch.match_id, false);
      void predictionQuery.refetch();
      void predictedQuery.refetch();
    } catch {
      removePendingPredictionMatchId(key);
    }
  }

  return (
    <div className="min-h-screen bg-[#0d0f12] text-[#f1f5f9]">
      <div className="mx-auto max-w-[1400px] px-4 py-10">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] text-[#64748b]">
              <Sparkles className="h-3 w-3 text-[#22c55e]" /> 2026 世界杯 · AI 预测中心
            </div>
            <h1 className="text-3xl font-black tracking-tight md:text-4xl">赛前前瞻 · 多模型深度预测</h1>
            <p className="mt-2 text-sm text-[#94a3b8]">
              未开赛比赛支持生成预测；已结束比赛保留赛前分析与历史结果。触发后会在后台持续运行，切换页面也不会中断。
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void fixturesQuery.refetch();
              void predictedQuery.refetch();
              if (shouldFetchPrediction) {
                void predictionQuery.refetch();
              }
            }}
            disabled={fixturesQuery.isFetching || predictedQuery.isFetching}
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", (fixturesQuery.isFetching || predictedQuery.isFetching) && "animate-spin")}
            />
            刷新
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
          <Card className="border-[#23262d] bg-[#0d0f12]">
            <CardHeader className="border-b border-[#23262d]">
              <CardTitle className="text-xs uppercase tracking-widest">可预测比赛</CardTitle>
            </CardHeader>
            <CardContent className="max-h-[420px] space-y-2 overflow-y-auto p-3">
              {fixturesQuery.isLoading ? (
                <LoadingState rows={4} />
              ) : displayUpcomingMatches.length === 0 ? (
                <EmptyState title="暂无未开赛比赛" description="已结束比赛会在下方历史预测区域展示。" />
              ) : (
                displayUpcomingMatches.map((match) => (
                  <PredictionListItem
                    key={match.match_id}
                    label="待生成"
                    item={match}
                    selected={String(match.match_id) === selectedMatchId}
                    pending={pendingPredictionMatchIds.includes(String(match.match_id))}
                    predictedMeta={predictedMap.get(String(match.match_id)) ?? null}
                    onSelect={() => {
                      setHasUserSelectedMatch(true);
                      setSelectedMatchId(String(match.match_id));
                    }}
                  />
                ))
              )}
            </CardContent>

            <CardHeader className="border-y border-[#23262d]">
              <CardTitle className="text-xs uppercase tracking-widest">历史预测结果</CardTitle>
            </CardHeader>
            <CardContent className="max-h-[360px] space-y-2 overflow-y-auto p-3">
              {predictedQuery.isLoading ? (
                <LoadingState rows={3} />
              ) : historicalPredictions.length === 0 ? (
                <EmptyState title="暂无历史预测" description="已结束比赛的赛前预测会保留在这里。" />
              ) : (
                historicalPredictions.map((match) => (
                  <PredictionListItem
                    key={match.match_id}
                    label="历史结果"
                    item={match}
                    selected={String(match.match_id) === selectedMatchId}
                    showHistory
                    predictedMeta={match}
                    onSelect={() => {
                      setHasUserSelectedMatch(true);
                      setSelectedMatchId(String(match.match_id));
                    }}
                  />
                ))
              )}
            </CardContent>
          </Card>

          {!activeMatch ? (
            <Card className="border-[#23262d] bg-[#0d0f12]">
              <CardContent className="flex min-h-[520px] items-center justify-center">
                <EmptyState
                  icon={Brain}
                  title="选择一场比赛"
                  description="从左侧选择一场未开赛比赛进行预测，或查看已结束比赛的历史预测结果。"
                />
              </CardContent>
            </Card>
          ) : (
            <Card className="border-[#23262d] bg-[#0d0f12]">
              <CardHeader className="border-b border-[#23262d]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>{selectedHistoricalMatch ? "历史预测结果" : "AI 赛前前瞻"}</CardTitle>
                    <p className="mt-1 text-xs text-[#64748b]">
                      {formatWorldCupDateLabel(
                        getPredictionItemDate(activeMatch),
                        "venue" in activeMatch ? activeMatch.venue : null
                      )}
                    </p>
                  </div>
                  <Badge variant={selectedHistoricalMatch ? "secondary" : "success"}>
                    {getStageLabel(activeMatch.stage || "World Cup")}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-6 p-6">
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
                  <TeamBadge teamName={activeMatch.home_team_name} />
                  <span className="font-mono text-2xl font-black text-[#64748b]">VS</span>
                  <TeamBadge teamName={activeMatch.away_team_name} align="right" />
                </div>

                {isLoadingPrediction ? (
                  <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                    <Loader2 className="h-6 w-6 animate-spin text-[#22c55e]" />
                    <p className="text-sm text-[#94a3b8]">正在读取预测结果...</p>
                  </div>
                ) : null}

                {!isLoadingPrediction && !prediction && !activePredictedMeta && predictionError ? (
                  <EmptyState title="暂时无法读取预测结果" description="请稍后刷新，或切换到其他比赛。" />
                ) : null}

                {!selectedHistoricalMatch && !prediction && !activePredictedMeta && !isLoadingPrediction ? (
                  <div className="flex flex-col items-center justify-center gap-4 rounded-md border border-dashed border-[#23262d] py-12 text-center">
                    <Brain className="h-8 w-8 text-[#64748b]" />
                    <div>
                      <p className="text-sm font-medium text-[#f1f5f9]">这场比赛还没有生成预测</p>
                      <p className="mt-1 text-xs text-[#64748b]">
                        你可以立即触发，后台会持续运行，即使切换到其他页面也不会中断。
                      </p>
                    </div>
                    <Button
                      onClick={handleTrigger}
                      disabled={triggering || !selectedUpcomingMatch?.is_ready_for_prediction}
                      className="h-10 px-6"
                    >
                      {triggering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                      {triggering ? "生成中..." : "立即生成预测"}
                    </Button>
                  </div>
                ) : null}

                {!isLoadingPrediction && prediction ? (
                  <>
                    {selectedHistoricalMatch ? (
                      <div className="rounded-md border border-[#1a1f2e] bg-[#11161d] p-4 text-sm text-[#cbd5e1]">
                        比赛已经结束，当前页面展示的是赛前生成的历史预测结果，不支持重新预测。
                      </div>
                    ) : null}

                    {/* 命中结果横幅（仅已结束且有命中判定时显示） */}
                    {prediction.accuracy ? (
                      <AccuracyBanner
                        accuracy={prediction.accuracy}
                        realHome={prediction.real_home_score}
                        realAway={prediction.real_away_score}
                        homeName={selectedHome.displayName}
                        awayName={selectedAway.displayName}
                      />
                    ) : null}

                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-6 border-y border-[#23262d] py-8 text-center">
                      <div>
                        <div className="text-xs text-[#64748b]">{selectedHome.displayName}</div>
                        <div className="mt-2 font-mono text-6xl font-black text-[#22c55e]">
                          {prediction.predicted_home_score}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-widest text-[#64748b]">预测比分</div>
                        <div className="mt-2 inline-flex items-center gap-1 rounded bg-[#1a1f2e] px-2 py-1 text-[10px] text-[#22c55e]">
                          <Sparkles className="h-3 w-3" />
                          置信度 {Math.round(prediction.confidence ?? 0)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[#64748b]">{selectedAway.displayName}</div>
                        <div className="mt-2 font-mono text-6xl font-black">{prediction.predicted_away_score}</div>
                      </div>
                    </div>

                    {isFallbackPrediction ? (
                      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-200">
                        这场历史预测的结构化结果保留得不够完整，当前比分和概率仅供参考，建议重点查看下面保留下来的多轮分析摘要与依据。
                      </div>
                    ) : (
                      <div className="grid gap-4 md:grid-cols-3">
                        <ProbabilityBar label="主胜" value={Math.round(prediction.home_win_prob ?? 0)} className="bg-[#22c55e]" />
                        <ProbabilityBar label="平局" value={Math.round(prediction.draw_prob ?? 0)} className="bg-[#eab308]" />
                        <ProbabilityBar label="客胜" value={Math.round(prediction.away_win_prob ?? 0)} className="bg-[#3b82f6]" />
                      </div>
                    )}

                    {conservativeVerdict || aggressiveVerdict ? (
                      <div className="grid gap-4 md:grid-cols-2">
                        {conservativeVerdict ? (
                          <div className="rounded-md border border-[#23262d] p-4">
                            <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-[#94a3b8]">
                              保守预测
                            </div>
                            <p className="text-sm text-[#f1f5f9]">{conservativeVerdict}</p>
                          </div>
                        ) : null}
                        {aggressiveVerdict ? (
                          <div className="rounded-md border border-[#22c55e]/30 bg-[#22c55e]/[0.04] p-4">
                            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[#22c55e]">
                              <TrendingUp className="h-3 w-3" />
                              激进预测
                            </div>
                            <p className="text-sm text-[#f1f5f9]">{aggressiveVerdict}</p>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {repairedKeyReasons.length ? (
                      <div className="rounded-md border border-[#23262d] p-4">
                        <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[#94a3b8]">
                          <Target className="h-4 w-4" />
                          关键依据
                        </div>
                        <div className="space-y-2 text-sm text-[#94a3b8]">
                          {repairedKeyReasons.map((reason, index) => (
                            <p key={`${reason}-${index}`}>
                              <span className="mr-2 font-mono text-[#22c55e]">
                                {String(index + 1).padStart(2, "0")}
                              </span>
                              {reason}
                            </p>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div>
                      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#f1f5f9]">
                        <Brain className="h-4 w-4 text-[#22c55e]" />
                        分析过程
                        {isFetchingPrediction ? <Loader2 className="h-3.5 w-3.5 animate-spin text-[#22c55e]" /> : null}
                      </div>
                      <div className="space-y-2">
                        {prediction.rounds?.length ? (
                          prediction.rounds
                            .slice()
                            .sort((a, b) => a.round - b.round)
                            .map((round) => (
                              <RoundPanel key={`round-${round.round}`} round={round} defaultOpen={round.round === 4} />
                            ))
                        ) : (
                          <p className="text-xs text-[#64748b]">暂无可展示分析记录。</p>
                        )}
                      </div>
                    </div>

                    {showMindmap && repairedMindmap ? (
                      <details className="rounded-md border border-[#23262d] bg-[#0d0f12] open:border-[#22c55e]/40">
                        <summary className="cursor-pointer list-none px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-[10px] font-bold uppercase tracking-widest text-[#94a3b8]">思维导图</div>
                              <div className="mt-1 text-xs text-[#64748b]">已将本场判断整理成导图，展开后可直接查看。</div>
                            </div>
                            <Badge variant="outline">导图</Badge>
                          </div>
                        </summary>
                        <div className="space-y-4 border-t border-[#23262d] p-4">
                          <div className="overflow-auto rounded border border-[#1a1f2e] bg-[#0f1419] p-3">
                            <MermaidDiagram
                              chart={repairedMindmap}
                              className="[&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
                            />
                          </div>
                          <details className="rounded border border-[#1a1f2e] bg-[#0f1419]">
                            <summary className="cursor-pointer px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#64748b]">
                              查看导图源码
                            </summary>
                            <pre className="max-h-72 overflow-auto border-t border-[#1a1f2e] p-3 font-mono text-[11px] leading-relaxed text-[#cbd5e1]">
                              {repairedMindmap}
                            </pre>
                          </details>
                        </div>
                      </details>
                    ) : null}

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[#23262d] pt-3 text-[10px] text-[#64748b]">
                      <span>参考信息量：{prediction.total_tokens ?? 0}</span>
                      <span>
                        处理时长：{prediction.total_cost_ms != null ? `${Math.max(1, Math.round(prediction.total_cost_ms / 1000))} 秒` : "--"}
                      </span>
                      {prediction.generated_at ? (
                        <span>生成时间：{new Date(prediction.generated_at).toLocaleString("zh-CN")}</span>
                      ) : null}
                      {!selectedHistoricalMatch ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={handleTrigger}
                          disabled={triggering}
                          className="ml-auto h-7 px-2 text-[10px]"
                        >
                          {triggering ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                          重新分析
                        </Button>
                      ) : null}
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default AIPredict;
