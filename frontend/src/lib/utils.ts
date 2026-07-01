import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { repairPossiblyMojibake } from "@/lib/text";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function parseApiDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  const normalized = dateStr.trim();
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

const BEIJING_TIME_ZONE = "Asia/Shanghai";

const RADAR_DIMENSION_LABEL_OVERRIDES: Record<string, string> = {
  "attacking impact": "\u8fdb\u653b\u5f71\u54cd",
  "physical duel": "\u8eab\u4f53\u5bf9\u6297",
  "overall level": "\u7efc\u5408\u6c34\u5e73",
};

function parseNaiveIsoParts(dateStr: string): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
} | null {
  const match = dateStr
    .trim()
    .match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
  if (!match) return null;
  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: Number(match[4] ?? 0),
    minute: Number(match[5] ?? 0),
    second: Number(match[6] ?? 0),
  };
}

export function parseWorldCupMatchDate(
  dateStr: string | null | undefined,
  _venue?: string | null
): Date | null {
  if (!dateStr) return null;
  const normalized = dateStr.trim();
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(normalized)) {
    return parseApiDate(normalized);
  }

  const parts = parseNaiveIsoParts(normalized);
  if (!parts) {
    return parseApiDate(normalized);
  }

  const utcTime = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second
  );
  return new Date(utcTime);
}

export function formatBeijingDateTime(date: Date | null, fallback = "--"): string {
  if (!date || Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatWorldCupDateTime(
  dateStr: string | null | undefined,
  venue?: string | null
): string {
  if (!dateStr) return "--";
  const date = parseWorldCupMatchDate(dateStr, venue);
  return formatBeijingDateTime(date, dateStr);
}

export function formatWorldCupDateLabel(
  dateStr: string | null | undefined,
  venue?: string | null
): string {
  const date = parseWorldCupMatchDate(dateStr, venue);
  if (!date) return "时间待定";
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const getPart = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${getPart("month")}月${getPart("day")}日 ${getPart("hour")}:${getPart("minute")}`;
}

export function getWorldCupMatchTime(
  dateStr: string | null | undefined,
  venue?: string | null
): number {
  const date = parseWorldCupMatchDate(dateStr, venue);
  return date ? date.getTime() : Number.MAX_SAFE_INTEGER;
}

export function isWorldCupDateToday(
  dateStr: string | null | undefined,
  venue?: string | null
): boolean {
  const date = parseWorldCupMatchDate(dateStr, venue);
  if (!date) return false;
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: BEIJING_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(date) === formatter.format(new Date());
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "--";
  const d = parseApiDate(dateStr);
  if (!d) return dateStr;
  return d.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "--";
  const d = parseApiDate(dateStr);
  if (!d) return dateStr;
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMinutes(min: number | null | undefined): string {
  if (min == null) return "--";
  return `${Math.floor(min / 60)}'`;
}

export function getRadarDimensionLabel(label: string | null | undefined): string {
  if (!label) return "--";
  const repaired = repairPossiblyMojibake(label).trim();
  const normalized = repaired.toLowerCase().replace(/[_-]+/g, " ");
  const map: Record<string, string> = {
    goals: "进球",
    assists: "助攻",
    minutes: "出场时间",
    discipline: "纪律",
    "decision making": "决策稳定性",
    impact: "影响力",
    availability: "出勤率",
    goalkeeping: "门将能力",
    distribution: "出球组织",
    positioning: "站位判断",
    aerial: "高空能力",
    stability: "稳定性",
    defending: "防守能力",
    "build up": "出球推进",
    support: "进攻支援",
    overall: "综合能力",
    "ball winning": "夺回球权",
    creation: "进攻创造",
    coverage: "覆盖能力",
    finishing: "终结能力",
    movement: "跑位能力",
    "chance creation": "机会创造",
    duel: "对抗能力",
    efficiency: "效率",
    pressing: "压迫能力",
  };
  return RADAR_DIMENSION_LABEL_OVERRIDES[normalized] || map[normalized] || repaired;
}

export function getRadarDimensionLabels(labels: Array<string | null | undefined>): string[] {
  return labels.map((label) => getRadarDimensionLabel(label));
}

export function getPositionLabel(pos: string): string {
  const map: Record<string, string> = {
    GK: "门将",
    DF: "后卫",
    MF: "中场",
    FW: "前锋",
    Goalkeeper: "门将",
    Defender: "后卫",
    Midfielder: "中场",
    Forward: "前锋",
  };
  return map[pos] || pos;
}

export function getPositionColor(pos: string): string {
  if (pos === "GK" || pos === "Goalkeeper") return "bg-amber-500/20 text-amber-400";
  if (pos === "DF" || pos === "Defender") return "bg-sky-500/20 text-sky-400";
  if (pos === "MF" || pos === "Midfielder") return "bg-emerald-500/20 text-emerald-400";
  if (pos === "FW" || pos === "Forward") return "bg-rose-500/20 text-rose-400";
  return "bg-gray-500/20 text-gray-400";
}

export function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    scheduled: "未开始",
    result_pending: "赛果待同步",
    live: "进行中",
    in_progress: "进行中",
    half_time: "中场休息",
    finished: "已结束",
    postponed: "延期",
    cancelled: "取消",
  };
  return map[status] || status;
}

export function getStatusColor(status: string): string {
  if (status === "live" || status === "in_progress" || status === "half_time") return "bg-emerald-500/20 text-emerald-400";
  if (status === "finished") return "bg-slate-500/20 text-slate-400";
  if (status === "result_pending") return "bg-amber-500/20 text-amber-300";
  if (status === "scheduled") return "bg-blue-500/20 text-blue-400";
  if (status === "postponed" || status === "cancelled") return "bg-rose-500/20 text-rose-400";
  return "bg-slate-500/20 text-slate-400";
}

export function normalizeMatchStatus(status: string | null | undefined): string {
  const value = (status || "").trim().toLowerCase();
  if (value === "in_progress" || value === "half_time" || value === "playing") return "live";
  if (value === "not_started") return "scheduled";
  return value || "scheduled";
}

export function resolveWorldCupDisplayStatus(
  status: string | null | undefined,
  kickoff: string | null | undefined,
  venue?: string | null,
  staleAfterHours = 3
): string {
  const normalized = normalizeMatchStatus(status);
  if (normalized !== "scheduled") return normalized;
  if (!kickoff) return normalized;

  const kickoffTime = getWorldCupMatchTime(kickoff, venue);
  if (!Number.isFinite(kickoffTime) || kickoffTime === Number.MAX_SAFE_INTEGER) {
    return normalized;
  }

  if (Date.now() >= kickoffTime + staleAfterHours * 60 * 60 * 1000) {
    return "result_pending";
  }
  return normalized;
}

export function shouldDisplayMatchScore(
  status: string | null | undefined,
  homeScore: number | null | undefined,
  awayScore: number | null | undefined
): boolean {
  if (homeScore == null || awayScore == null) return false;
  const normalized = normalizeMatchStatus(status);
  return normalized === "finished" || normalized === "live";
}

export function getCrawlStatusLabel(status: string): string {
  const map: Record<string, string> = {
    success: "成功",
    partial: "部分成功",
    failed: "失败",
    running: "进行中",
  };
  return map[status] || status;
}

export function getCrawlStatusColor(status: string): string {
  if (status === "success") return "bg-emerald-500/20 text-emerald-400";
  if (status === "partial") return "bg-amber-500/20 text-amber-400";
  if (status === "failed") return "bg-rose-500/20 text-rose-400";
  if (status === "running") return "bg-sky-500/20 text-sky-400";
  return "bg-slate-500/20 text-slate-400";
}

export function getQualificationStatusLabel(status: string): string {
  const normalized = status.trim().toLowerCase();
  const map: Record<string, string> = {
    confirmedqualified: "已出线",
    qualified: "已出线",
    eliminated: "已出局",
    pending: "待定",
    playoff: "附加赛",
  };
  return map[normalized] || status;
}

export function getStageLabel(stage: string | null | undefined): string {
  if (!stage) return "--";

  const groupMatch = stage.match(/^group\s+([a-z])$/i);
  if (groupMatch) {
    return `${groupMatch[1].toUpperCase()}组`;
  }

  const normalized = stage.trim().toLowerCase().replace(/[_-]+/g, " ");
  const map: Record<string, string> = {
    "first stage": "小组赛",
    "group stage": "小组赛",
    "round of 32": "32强",
    "round of 16": "16强",
    "round of 8": "8强",
    quarterfinal: "1/4决赛",
    quarterfinals: "1/4决赛",
    "quarter finals": "1/4决赛",
    "quarter-finals": "1/4决赛",
    semifinal: "半决赛",
    semifinals: "半决赛",
    "semi finals": "半决赛",
    "semi-finals": "半决赛",
    "third place": "季军赛",
    "third-place": "季军赛",
    final: "决赛",
    playoff: "附加赛",
    playoffs: "附加赛",
  };

  return map[normalized] || stage;
}

export function getGroupLabel(group: string | null | undefined): string {
  if (!group) return "--";

  const groupMatch = group.match(/^group\s+([a-z])$/i);
  if (groupMatch) {
    return `${groupMatch[1].toUpperCase()}组`;
  }

  if (/^[a-z]$/i.test(group.trim())) {
    return `${group.trim().toUpperCase()}组`;
  }

  return group;
}

export function getPlayerNameLabel(
  name: string | null | undefined,
  fullName?: string | null | undefined
): string {
  const cnName = getPlayerChineseName(name) ?? getPlayerChineseName(fullName);
  if (cnName) return cnName;

  const source = (fullName && fullName.trim()) || (name && name.trim()) || "";
  if (!source) return "--";
  if (/[\u4e00-\u9fff]/.test(source)) return source;

  return source
    .split(/\s+/)
    .map((word) =>
      word
        .split(/([-'`])/)
        .map((part) => {
          if (!part || /^[-'`]$/.test(part)) return part;
          if (!/[A-Za-z]/.test(part)) return part;
          if (part === part.toUpperCase() || part === part.toLowerCase()) {
            return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
          }
          return part.charAt(0).toUpperCase() + part.slice(1);
        })
        .join("")
    )
    .join(" ");
}

export function getEventTypeLabel(eventType: string | null | undefined): string {
  if (!eventType) return "--";

  const normalized = eventType.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const map: Record<string, string> = {
    goal: "进球",
    own_goal: "乌龙球",
    yellow_card: "黄牌",
    red_card: "红牌",
    substitution: "换人",
    penalty: "点球",
    penalty_goal: "点球命中",
    penalty_miss: "点球未进",
    var: "VAR",
    kickoff: "开球",
    full_time: "全场结束",
    half_time: "中场结束",
  };

  return map[normalized] || eventType;
}

export function getShotResultLabel(result: string | null | undefined): string {
  if (!result) return "--";

  const normalized = result.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const map: Record<string, string> = {
    goal: "进球",
    saved: "被扑出",
    save: "被扑出",
    miss: "打偏",
    missed: "打偏",
    off_target: "偏出",
    on_target: "射正",
    blocked: "被封堵",
    woodwork: "中柱",
    post: "中柱",
  };

  return map[normalized] || result;
}

export function getShotTypeLabel(shotType: string | null | undefined): string {
  if (!shotType) return "--";

  const normalized = shotType.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const map: Record<string, string> = {
    left_foot: "左脚",
    right_foot: "右脚",
    head: "头球",
    penalty: "点球",
    free_kick: "任意球",
    open_play: "运动战",
  };

  return map[normalized] || shotType;
}

type CountryMeta = {
  label: string;
  code?: string;
};

const FLAG_BASE_URL = "https://cdn.jsdelivr.net/gh/lipis/flag-icons/flags/4x3";

const COUNTRY_META_MAP: Record<string, CountryMeta> = {
  world: { label: "国际" },
  england: { label: "英格兰", code: "gb-eng" },
  eng: { label: "英格兰", code: "gb-eng" },
  scotland: { label: "苏格兰", code: "gb-sct" },
  sco: { label: "苏格兰", code: "gb-sct" },
  wales: { label: "威尔士", code: "gb-wls" },
  wal: { label: "威尔士", code: "gb-wls" },
  argentina: { label: "阿根廷", code: "ar" },
  arg: { label: "阿根廷", code: "ar" },
  australia: { label: "澳大利亚", code: "au" },
  aus: { label: "澳大利亚", code: "au" },
  austria: { label: "奥地利", code: "at" },
  aut: { label: "奥地利", code: "at" },
  algeria: { label: "阿尔及利亚", code: "dz" },
  alg: { label: "阿尔及利亚", code: "dz" },
  belgium: { label: "比利时", code: "be" },
  bel: { label: "比利时", code: "be" },
  "bosnia and herzegovina": { label: "波黑", code: "ba" },
  bih: { label: "波黑", code: "ba" },
  brazil: { label: "巴西", code: "br" },
  bra: { label: "巴西", code: "br" },
  "cabo verde": { label: "佛得角", code: "cv" },
  cpv: { label: "佛得角", code: "cv" },
  cameroon: { label: "喀麦隆", code: "cm" },
  cmr: { label: "喀麦隆", code: "cm" },
  canada: { label: "加拿大", code: "ca" },
  can: { label: "加拿大", code: "ca" },
  curacao: { label: "库拉索", code: "cw" },
  "curaçao": { label: "库拉索", code: "cw" },
  cuw: { label: "库拉索", code: "cw" },
  colombia: { label: "哥伦比亚", code: "co" },
  col: { label: "哥伦比亚", code: "co" },
  "congo dr": { label: "刚果（金）", code: "cd" },
  cod: { label: "刚果（金）", code: "cd" },
  "costa rica": { label: "哥斯达黎加", code: "cr" },
  cri: { label: "哥斯达黎加", code: "cr" },
  croatia: { label: "克罗地亚", code: "hr" },
  cro: { label: "克罗地亚", code: "hr" },
  czechia: { label: "捷克", code: "cz" },
  "czech republic": { label: "捷克", code: "cz" },
  cze: { label: "捷克", code: "cz" },
  chile: { label: "智利", code: "cl" },
  chi: { label: "智利", code: "cl" },
  denmark: { label: "丹麦", code: "dk" },
  den: { label: "丹麦", code: "dk" },
  ecuador: { label: "厄瓜多尔", code: "ec" },
  ecu: { label: "厄瓜多尔", code: "ec" },
  egypt: { label: "埃及", code: "eg" },
  egy: { label: "埃及", code: "eg" },
  france: { label: "法国", code: "fr" },
  fra: { label: "法国", code: "fr" },
  germany: { label: "德国", code: "de" },
  ger: { label: "德国", code: "de" },
  ghana: { label: "加纳", code: "gh" },
  gha: { label: "加纳", code: "gh" },
  haiti: { label: "海地", code: "ht" },
  hai: { label: "海地", code: "ht" },
  hungary: { label: "匈牙利", code: "hu" },
  hun: { label: "匈牙利", code: "hu" },
  "ir iran": { label: "伊朗", code: "ir" },
  irn: { label: "伊朗", code: "ir" },
  iraq: { label: "伊拉克", code: "iq" },
  irq: { label: "伊拉克", code: "iq" },
  italy: { label: "意大利", code: "it" },
  ita: { label: "意大利", code: "it" },
  japan: { label: "日本", code: "jp" },
  jpn: { label: "日本", code: "jp" },
  jordan: { label: "约旦", code: "jo" },
  jor: { label: "约旦", code: "jo" },
  "korea republic": { label: "韩国", code: "kr" },
  kor: { label: "韩国", code: "kr" },
  mexico: { label: "墨西哥", code: "mx" },
  mex: { label: "墨西哥", code: "mx" },
  morocco: { label: "摩洛哥", code: "ma" },
  mar: { label: "摩洛哥", code: "ma" },
  "new zealand": { label: "新西兰", code: "nz" },
  nzl: { label: "新西兰", code: "nz" },
  netherlands: { label: "荷兰", code: "nl" },
  ned: { label: "荷兰", code: "nl" },
  nigeria: { label: "尼日利亚", code: "ng" },
  nga: { label: "尼日利亚", code: "ng" },
  norway: { label: "挪威", code: "no" },
  nor: { label: "挪威", code: "no" },
  poland: { label: "波兰", code: "pl" },
  pol: { label: "波兰", code: "pl" },
  panama: { label: "巴拿马", code: "pa" },
  pan: { label: "巴拿马", code: "pa" },
  portugal: { label: "葡萄牙", code: "pt" },
  por: { label: "葡萄牙", code: "pt" },
  paraguay: { label: "巴拉圭", code: "py" },
  par: { label: "巴拉圭", code: "py" },
  qatar: { label: "卡塔尔", code: "qa" },
  qat: { label: "卡塔尔", code: "qa" },
  "saudi arabia": { label: "沙特阿拉伯", code: "sa" },
  ksa: { label: "沙特阿拉伯", code: "sa" },
  senegal: { label: "塞内加尔", code: "sn" },
  sen: { label: "塞内加尔", code: "sn" },
  serbia: { label: "塞尔维亚", code: "rs" },
  srb: { label: "塞尔维亚", code: "rs" },
  "south africa": { label: "南非", code: "za" },
  rsa: { label: "南非", code: "za" },
  spain: { label: "西班牙", code: "es" },
  esp: { label: "西班牙", code: "es" },
  sweden: { label: "瑞典", code: "se" },
  swe: { label: "瑞典", code: "se" },
  switzerland: { label: "瑞士", code: "ch" },
  sui: { label: "瑞士", code: "ch" },
  "cote d'ivoire": { label: "科特迪瓦", code: "ci" },
  "côte d'ivoire": { label: "科特迪瓦", code: "ci" },
  "cã´te d'ivoire": { label: "科特迪瓦", code: "ci" },
  "ivory coast": { label: "科特迪瓦", code: "ci" },
  civ: { label: "科特迪瓦", code: "ci" },
  "curaã§ao": { label: "库拉索", code: "cw" },
  tunisia: { label: "突尼斯", code: "tn" },
  tun: { label: "突尼斯", code: "tn" },
  turkey: { label: "土耳其", code: "tr" },
  "türkiye": { label: "土耳其", code: "tr" },
  "tã¼rkiye": { label: "土耳其", code: "tr" },
  turkiye: { label: "土耳其", code: "tr" },
  tur: { label: "土耳其", code: "tr" },
  usa: { label: "美国", code: "us" },
  "united states": { label: "美国", code: "us" },
  uzbekistan: { label: "乌兹别克斯坦", code: "uz" },
  uzb: { label: "乌兹别克斯坦", code: "uz" },
  uruguay: { label: "乌拉圭", code: "uy" },
  uru: { label: "乌拉圭", code: "uy" },
};

function normalizeCountryKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ß/g, "ss")
    .replace(/æ/g, "ae")
    .replace(/ø/g, "o")
    .replace(/đ/g, "d")
    .replace(/ł/g, "l")
    .replace(/œ/g, "oe")
    .replace(/ı/g, "i")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}

export function getCountryMeta(value: string | null | undefined): CountryMeta | null {
  if (!value) return null;
  const repaired = repairPossiblyMojibake(value);
  return COUNTRY_META_MAP[normalizeCountryKey(repaired)] ?? null;
}

export function getCountryLabel(value: string | null | undefined): string {
  if (!value) return "--";
  const repaired = repairPossiblyMojibake(value);
  return getCountryMeta(repaired)?.label ?? repaired;
}

export function getCountryFlagUrl(value: string | null | undefined): string | undefined {
  const code = getCountryMeta(value)?.code;
  if (!code) return undefined;
  return `${FLAG_BASE_URL}/${code.toLowerCase()}.svg`;
}

export function getLeagueTypeLabel(type: string | null | undefined): string {
  if (!type) return "--";
  const map: Record<string, string> = {
    league: "联赛",
    cup: "杯赛",
    international: "国际赛事",
  };
  return map[type.trim().toLowerCase()] || type;
}

export function getTeamIdentity(teamName: string | null | undefined, country?: string | null) {
  const repairedTeamName = repairPossiblyMojibake(teamName);
  const repairedCountry = repairPossiblyMojibake(country);
  const teamMeta = getCountryMeta(repairedTeamName);
  const countryMeta = getCountryMeta(repairedCountry);
  const fallbackMeta = countryMeta ?? teamMeta;
  const isNationalTeam = !repairedCountry && !!teamMeta;

  return {
    displayName: isNationalTeam ? fallbackMeta?.label ?? repairedTeamName ?? "--" : repairedTeamName ?? "--",
    originalName:
      isNationalTeam && repairedTeamName && fallbackMeta?.label && fallbackMeta.label !== repairedTeamName
        ? repairedTeamName
        : undefined,
    countryLabel: fallbackMeta?.label ?? repairedCountry ?? undefined,
    flagUrl: getCountryFlagUrl(repairedCountry ?? repairedTeamName),
    isNationalTeam,
  };
}

export function getNormalizedTeamKey(teamName: string | null | undefined, country?: string | null): string {
  const identity = getTeamIdentity(teamName, country);
  return normalizeCountryKey(identity.countryLabel ?? identity.displayName ?? teamName ?? "");
}

const DEFAULT_AVATAR =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='32' fill='%232a2d3a'/%3E%3Ccircle cx='32' cy='24' r='10' fill='%234a4d5a'/%3E%3Cpath d='M12 56c0-11 9-20 20-20s20 9 20 20' fill='%234a4d5a'/%3E%3C/svg%3E";

const PLAYER_NAME_CN_MAP: Record<string, string> = {
  "Lionel MESSI": "梅西",
  "Kylian MBAPPE": "姆巴佩",
  "VINICIUS JUNIOR": "维尼修斯",
  "Ousmane DEMBELE": "登贝莱",
  "Erling HAALAND": "哈兰德",
  "Deniz UNDAV": "温达夫",
  "Ismaila SARR": "萨尔",
  "Johan MANZAMBI": "曼赞比",
  "Harry KANE": "凯恩",
  "Mikel OYARZABAL": "奥亚萨瓦尔",
  "Raul JIMENEZ": "劳尔·希门尼斯",
  "Luis ROMO": "路易斯·罗莫",
  "Julian QUINONES": "胡利安·基尼奥内斯",
  "Teboho MOKOENA": "特博霍·莫科纳",
  "OH Hyeongyu": "吴贤揆",
  "Ladislav KREJCI": "拉迪斯拉夫·克雷伊奇",
  "Michal SADILEK": "米哈尔·萨迪莱克",
  "HWANG Inbeom": "黄仁范",
  "Yoane WISSA": "约安·维萨",
  "Cole PALMER": "科尔·帕尔默",
  "Phil FODEN": "菲尔·福登",
  "Bukayo SAKA": "布卡约·萨卡",
  "Jude BELLINGHAM": "裘德·贝林厄姆",
  "Harry MAGUIRE": "哈里·马奎尔",
  "Declan RICE": "德克兰·赖斯",
  "Jamal MUSIALA": "贾马尔·穆西亚拉",
  "Florian WIRTZ": "弗洛里安·维尔茨",
  "Kai HAVERTZ": "凯·哈弗茨",
  "Niclas FULLKRUG": "菲尔克鲁格",
  "Leroy SANE": "勒鲁瓦·萨内",
  "KAI MERK": "凯·默克",
  "Kylian MBappe": "姆巴佩",
  "Cristiano RONALDO": "克里斯蒂亚诺·罗纳尔多",
  "Bruno FERNANDES": "布鲁诺·费尔南德斯",
  "Bernardo SILVA": "贝尔纳多·席尔瓦",
  "Rafael LEAO": "拉斐尔·莱奥",
  "Ruben DIAS": "鲁本·迪亚斯",
  "Rodri": "罗德里",
  "Pedri": "佩德里",
  "Lamine YAMAL": "拉明·亚马尔",
  "Alvaro MORATA": "阿尔瓦罗·莫拉塔",
  "Nico WILLIAMS": "尼科·威廉斯",
  "Dani OLMO": "达尼·奥尔莫",
  "Achraf HAKIMI": "阿什拉夫·哈基米",
  "Hakim ZIYECH": "齐耶赫",
  "Sofyan AMRABAT": "索菲扬·阿姆拉巴特",
  "Youssef EN-NESYRI": "优素福·恩内斯里",
  "Luka MODRIC": "卢卡·莫德里奇",
  "Josko GVARDIOL": "约什科·格瓦迪奥尔",
  "Marcelo BROZOVIC": "马塞洛·布罗佐维奇",
  "Andrej KRAMARIC": "安德烈·克拉马里奇",
  "Lautaro MARTINEZ": "劳塔罗·马丁内斯",
  "Julian ALVAREZ": "胡利安·阿尔瓦雷斯",
  "Angel DI MARIA": "安赫尔·迪马利亚",
  "Alexis MAC ALLISTER": "亚历克西斯·麦卡利斯特",
  "Enzo FERNANDEZ": "恩佐·费尔南德斯",
  "Antoine GRIEZMANN": "安托万·格列兹曼",
  "Aurelien TCHOUAMENI": "奥雷利安·楚阿梅尼",
  "Theo HERNANDEZ": "特奥·埃尔南德斯",
  "Randal KOLO MUANI": "科洛·穆阿尼",
  "Memphis DEPAY": "孟菲斯·德佩",
  "Virgil VAN DIJK": "范戴克",
  "Frenkie DE JONG": "弗朗基·德容",
  "Cody GAKPO": "加克波",
  "Xavi SIMONS": "哈维·西蒙斯",
  "Santiago GIMENEZ": "圣地亚哥·希门尼斯",
  "Orbelin PINEDA": "奥尔韦林·皮内达",
  "Edson ALVAREZ": "埃德松·阿尔瓦雷斯",
  "Hirving LOZANO": "欧文·洛萨诺",
  "Takefusa KUBO": "久保建英",
  "Kaoru MITOMA": "三笘薰",
  "Wataru ENDO": "远藤航",
  "Ayase UEDA": "上田绮世",
  "Daichi KAMADA": "镰田大地",
  "Lee KANG IN": "李刚仁",
  "Heung Min SON": "孙兴慜",
  "Min Jae KIM": "金玟哉",
  "Hwang HEE CHAN": "黄喜灿",
  "Kim MIN JAE": "金玟哉",
  "Mohamed SALAH": "穆罕默德·萨拉赫",
  "Omar MARMOUSH": "奥马尔·马尔穆什",
  "Mahmoud TREZEGUET": "特雷泽盖",
  "Victor OSIMHEN": "维克托·奥斯梅恩",
  "Ademola LOOKMAN": "阿德莫拉·卢克曼",
  "Wilfred NDIDI": "威尔弗雷德·恩迪迪",
  "Victor BONIFACE": "维克托·博尼费斯",
  "Alphonso DAVIES": "阿方索·戴维斯",
  "Jonathan DAVID": "乔纳森·戴维",
  "Cyle LARIN": "赛尔·拉林",
  "Tajon BUCHANAN": "塔琼·布坎南",
  "Milan BORJAN": "米兰·博尔扬",
  "Percy TAU": "珀西·陶",
  "Lyle FOSTER": "莱尔·福斯特",
  "Elias MOKWENA": "埃利亚斯·莫科埃纳",
  "Sadio MANE": "萨迪奥·马内",
  "Nicolas JACKSON": "尼古拉斯·杰克逊",
  "Kalidou KOULIBALY": "卡利杜·库利巴利",
  "Pape SARR": "帕普·萨尔",
  "Tajon Buchanan": "塔琼·布坎南",
  "Eldor SHOMURODOV": "埃尔多尔·肖穆罗多夫",
  "Abbosbek FAYZULLAEV": "阿博斯别克·法伊祖拉耶夫",
  "Azizbek AMONOV": "阿齐兹别克·阿莫诺夫",
  "Odiljon XAMROBEKOV": "奥迪尔洪·哈姆罗别科夫",
  "Igor Sergeev": "伊戈尔·谢尔盖耶夫",
  "Abdukodir KHUSANOV": "阿卜杜科迪尔·胡萨诺夫",
  "Eldor SHOMURODOV ": "埃尔多尔·肖穆罗多夫",
  "Ruben VARGAS": "鲁文·巴尔加斯",
  "Maxi ARAUJO": "马克西·阿劳霍",
  "Riyad Mahrez": "里亚德·马赫雷斯",
  "Riyad MAHREZ": "里亚德·马赫雷斯",
  "Viktor GYOKERES": "维克托·约克雷斯",
  "MATHEUS CUNHA": "马特乌斯·库尼亚",
  "Ramin REZAEIAN": "拉明·礼萨扬",
  "Crysencio SUMMERVILLE": "克里森西奥·萨默维尔",
  "Elijah JUST": "以利亚·贾斯特",
  "Ismael SAIBARI": "伊斯梅尔·赛巴里",
  "Breel EMBOLO": "布雷尔·恩博洛",
  "Brian BROBBEY": "布赖恩·布罗贝伊",
  "MOHAMED SALAH": "穆罕默德·萨拉赫",
  "CRISTIANO RONALDO": "克里斯蒂亚诺·罗纳尔多",
  "Alexander Isak": "亚历山大·伊萨克",
  "Pape GUEYE": "帕普·盖耶",
  "Leandro TROSSARD": "莱安德罗·特罗萨德",
  "Folarin BALOGUN": "福拉林·巴洛贡",
  "Marko ARNAUTOVIC": "马尔科·阿瑙托维奇",
  "Julio ENCISO": "胡利奥·恩西索",
  "Nicolas PEPE": "尼古拉·佩佩",
  "MOUSA ALTAMARI": "穆萨·塔马里",
  "Luis DIAZ": "路易斯·迪亚斯",
  "Soufiane RAHIMI": "苏菲扬·拉希米",
  "Anthony ELANGA": "安东尼·埃兰加",
  "Iliman NDIAYE": "伊利曼·恩迪亚耶",
  "Nathan SALIBA": "内森·萨利巴",
  "Promise DAVID": "普罗米斯·戴维",
  "Daniel MUNOZ": "丹尼尔·穆尼奥斯",
  "Yasin AYARI": "亚辛·阿亚里",
  "TREZEGUET": "特雷泽盖",
  "Felix NMECHA": "费利克斯·恩梅查",
  "Michael OLISE": "迈克尔·奥利塞",
  "MOSTAFA ZICO": "穆斯塔法·齐科",
  "Ermin MAHMIC": "埃尔明·马赫米奇",
  "Gonzalo PLATA": "贡萨洛·普拉塔",
  "Kevin DE BRUYNE": "凯文·德布劳内",
  "Alex FREEMAN": "亚历克斯·弗里曼",
  "Romelu LUKAKU": "罗梅卢·卢卡库",
  "Arda GULER": "阿尔达·居莱尔",
  "Bradley BARCOLA": "布拉德利·巴尔科拉",
  "Nathaniel BROWN": "纳撒尼尔·布朗",
  "Chris WOOD": "克里斯·伍德",
  "Keito Nakamura": "中村敬斗",
  "Amad DIALLO": "阿马德·迪亚洛",
  "Abdulelah ALAMRI": "阿卜杜勒拉赫·阿姆里",
  "Granit XHAKA": "格拉尼特·扎卡",
  "Kaishu SANO": "佐野海舟",
  "Matias GALARZA": "马蒂亚斯·加拉萨",
  "Sebastian BERHALTER": "塞巴斯蒂安·伯哈尔特",
  "Petar SUCIC": "佩塔尔·苏契奇",
  "Nestory IRANKUNDA": "内斯托里·伊兰昆达",
  "Martin ODEGAARD": "马丁·厄德高",
  "Brahim DIAZ": "卜拉欣·迪亚斯",
  "CASEMIRO": "卡塞米罗",
  "GABRIEL MARTINELLI": "马丁内利",
  "ENDRICK": "恩德里克",
  "Desire DOUE": "德西雷·杜埃",
  "EMAM ASHOUR": "埃马姆·阿舒尔",
  "Daizen MAEDA": "前田大然",
  "Amine GOUIRI": "阿明·古伊里",
  "BRUNO GUIMARAES": "布鲁诺·吉马良斯",
  "Caleb YIRENKYI": "凯莱布·伊伦基",
  "Agustin CANOBBIO": "阿古斯丁·卡诺比奥",
  "Fiston MAYELE": "菲斯顿·马耶莱",
  "Baris Alper YILMAZ": "巴里什·阿尔珀·伊尔马兹",
  "Joshua KIMMICH": "约书亚·基米希",
  "Junya ITO": "伊东纯也",
  "HASSAN ALHAYDOS": "哈桑·海多斯",
  "Marcel SABITZER": "马塞尔·萨比策",
  "Aaron HICKEY": "阿伦·希基",
  "Aaron TSHIBOLA": "阿伦·奇博拉",
  "Aaron WAN-BISSAKA": "阿伦·万-比萨卡",
  "ABDALLAH ALFAKHORI": "阿卜杜拉·法赫里",
};

function normalizePlayerNameKey(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’'`.-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

const NORMALIZED_PLAYER_NAME_CN_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(PLAYER_NAME_CN_MAP).map(([key, value]) => [normalizePlayerNameKey(key), value])
);

export function getPlayerChineseName(name: string | null | undefined): string | undefined {
  if (!name) return undefined;
  const trimmed = repairPossiblyMojibake(name).trim();
  return PLAYER_NAME_CN_MAP[trimmed] ?? NORMALIZED_PLAYER_NAME_CN_MAP[normalizePlayerNameKey(trimmed)];
}

export function getPlayerPhoto(photoUrl: string | null | undefined): string {
  if (!photoUrl) return DEFAULT_AVATAR;
  return photoUrl;
}

export function handleImageError(e: React.SyntheticEvent<HTMLImageElement>) {
  const img = e.currentTarget;
  img.src = DEFAULT_AVATAR;
  img.onerror = null;
}

export function formatNumber(n: number | null | undefined, digits = 1): string {
  if (n == null) return "--";
  return n.toFixed(digits);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
