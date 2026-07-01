import type { Player } from "@/types";

/**
 * 位置标准化键
 */
export type PositionKey = "GK" | "DF" | "MF" | "FW";

/**
 * 单个维度定义：标签 + 对应的 Player score 字段
 */
export interface DimensionDef {
  label: string;
  field: keyof Player;
}

/**
 * 位置维度配置
 * 依据项目方案 7.3 节，每个位置展示不同的 6 个维度
 */
export interface PositionConfig {
  key: PositionKey;
  label: string;
  dimensions: DimensionDef[];
}

const POSITION_CONFIGS: Record<PositionKey, PositionConfig> = {
  GK: {
    key: "GK",
    label: "门将",
    dimensions: [
      { label: "扑救反应", field: "gk_score" },
      { label: "出球能力", field: "org_score" },
      { label: "防守站位", field: "def_score" },
      { label: "高空处理", field: "phy_score" },
      { label: "决策稳定性", field: "dis_score" },
      { label: "综合水平", field: "overall_rating" },
    ],
  },
  DF: {
    key: "DF",
    label: "后卫",
    dimensions: [
      { label: "防守抢断", field: "def_score" },
      { label: "空中对抗", field: "phy_score" },
      { label: "出球组织", field: "org_score" },
      { label: "跑动覆盖", field: "phy_score" },
      { label: "进攻插上", field: "atk_score" },
      { label: "决策稳定性", field: "dis_score" },
    ],
  },
  MF: {
    key: "MF",
    label: "中场",
    dimensions: [
      { label: "进攻影响", field: "atk_score" },
      { label: "传球组织", field: "org_score" },
      { label: "防守拦截", field: "def_score" },
      { label: "跑动覆盖", field: "phy_score" },
      { label: "决策稳定性", field: "dis_score" },
      { label: "综合水平", field: "overall_rating" },
    ],
  },
  FW: {
    key: "FW",
    label: "前锋",
    dimensions: [
      { label: "进攻影响", field: "atk_score" },
      { label: "机会创造", field: "org_score" },
      { label: "身体对抗", field: "phy_score" },
      { label: "前场压迫", field: "def_score" },
      { label: "决策稳定性", field: "dis_score" },
      { label: "综合水平", field: "overall_rating" },
    ],
  },
};

const POSITION_ALIASES: Record<string, PositionKey> = {
  GK: "GK",
  DF: "DF",
  MF: "MF",
  FW: "FW",
  门将: "GK",
  后卫: "DF",
  中场: "MF",
  前锋: "FW",
  goalkeeper: "GK",
  defender: "DF",
  midfielder: "MF",
  forward: "FW",
};

/**
 * 将球员 position 字段标准化为 PositionKey
 * 无法识别的位置默认使用 FW
 */
export function normalizePosition(position?: string | null): PositionKey {
  if (!position) return "FW";
  const key = POSITION_ALIASES[position.trim().toUpperCase()];
  if (key) return key;
  const cnKey = POSITION_ALIASES[position.trim()];
  if (cnKey) return cnKey;
  return "FW";
}

/**
 * 获取位置维度配置
 */
export function getPositionConfig(position?: string | null): PositionConfig {
  return POSITION_CONFIGS[normalizePosition(position)];
}

/**
 * 获取位置的维度标签数组
 */
export function getPositionDimensions(position?: string | null): string[] {
  return getPositionConfig(position).dimensions.map((d) => d.label);
}

/**
 * 根据 Player 对象和位置，提取该位置的 6 维数值
 */
export function getPlayerPositionValues(player: Player, position?: string | null): number[] {
  const config = getPositionConfig(position ?? player.position);
  return config.dimensions.map((d) => {
    const v = player[d.field];
    return typeof v === "number" ? v : 0;
  });
}

/**
 * 跨位置公共维度配置
 * 当两名球员位置不同时，映射到公共维度对比
 */
export interface CommonDimension {
  label: string;
  fieldA: keyof Player;
  fieldB: keyof Player;
}

/**
 * 获取两名球员的公共维度配置
 * 返回公共维度列表，每项包含两名球员各自对应的 score 字段
 */
export function getCommonDimensions(): { dimensions: string[]; fieldA: (keyof Player)[]; fieldB: (keyof Player)[] } {
  // 公共维度：纪律 + 身体/运动能力 + 通用进攻 + 通用组织 + 通用防守 + 稳定性/效率
  return {
    dimensions: ["纪律", "身体素质", "进攻能力", "组织能力", "防守能力", "综合稳定性"],
    fieldA: ["dis_score", "phy_score", "atk_score", "org_score", "def_score", "overall_rating"],
    fieldB: ["dis_score", "phy_score", "atk_score", "org_score", "def_score", "overall_rating"],
  };
}

/**
 * 根据 Player 对象和公共维度字段列表，提取数值
 */
export function getPlayerValuesByFields(
  player: Player,
  fields: (keyof Player)[]
): number[] {
  return fields.map((f) => {
    const v = player[f];
    return typeof v === "number" ? v : 0;
  });
}
