import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [bundleJsonPath, outputXlsxPath, previewDirArg] = process.argv.slice(2);

if (!bundleJsonPath || !outputXlsxPath) {
  console.error("Usage: node build_fifa_group_stage_attachment.mjs <bundle.json> <output.xlsx> [preview_dir]");
  process.exit(1);
}

const previewDir = previewDirArg || path.join(path.dirname(outputXlsxPath), "previews");
const bundle = JSON.parse(await fs.readFile(bundleJsonPath, "utf8"));

function normalizeRows(rows) {
  return Array.isArray(rows) ? rows : [];
}

function topRows(playerStats, metric, topN = 20) {
  return [...playerStats]
    .sort((a, b) => {
      const bv = Number(b[metric] ?? 0);
      const av = Number(a[metric] ?? 0);
      if (bv !== av) return bv - av;
      return String(a["球员姓名"] ?? "").localeCompare(String(b["球员姓名"] ?? ""));
    })
    .slice(0, topN)
    .map((row, index) => ({
      排名: index + 1,
      球员姓名: row["球员姓名"],
      球队: row["球队"],
      位置: row["位置"],
      [metric]: row[metric],
    }));
}

function writeTable(sheet, rows) {
  const safeRows = normalizeRows(rows);
  if (!safeRows.length) {
    sheet.getRange("A1").values = [["暂无数据"]];
    return;
  }
  const headers = Object.keys(safeRows[0]);
  const matrix = [
    headers,
    ...safeRows.map((row) => headers.map((header) => row[header] ?? null)),
  ];
  sheet.getRangeByIndexes(0, 0, matrix.length, headers.length).values = matrix;
  const headerRange = sheet.getRangeByIndexes(0, 0, 1, headers.length);
  headerRange.format = {
    fill: "#1D4ED8",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "Center",
    verticalAlignment: "Center",
  };
  sheet.getUsedRange().format.autofitColumns();
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
}

function capColumnWidth(sheet, a1, width) {
  sheet.getRange(a1).format.columnWidth = width;
}

const workbook = Workbook.create();

const summarySheet = workbook.worksheets.add("说明");
summarySheet.getRange("A1:B1").merge();
summarySheet.getRange("A1").values = [["世界杯小组赛球员数据附件"]];
summarySheet.getRange("A1").format = {
  fill: "#0F172A",
  font: { bold: true, color: "#FFFFFF", size: 14 },
  horizontalAlignment: "Center",
  verticalAlignment: "Center",
};
summarySheet.getRange("A3:B3").values = [["项目", "值"]];
summarySheet.getRange("A3:B3").format = {
  fill: "#1D4ED8",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "Center",
  verticalAlignment: "Center",
};
const sourceRows = normalizeRows(bundle.sources);
if (sourceRows.length) {
  const matrix = sourceRows.map((row) => [row["项目"] ?? null, row["值"] ?? null]);
  summarySheet.getRangeByIndexes(3, 0, matrix.length, 2).values = matrix;
}
summarySheet.getUsedRange().format.autofitColumns();
summarySheet.showGridLines = false;
summarySheet.freezePanes.freezeRows(3);
capColumnWidth(summarySheet, "A:A", 20);
capColumnWidth(summarySheet, "B:B", 28);

const playerInfoSheet = workbook.worksheets.add("球员信息");
writeTable(playerInfoSheet, bundle.players);

const playerStatsSheet = workbook.worksheets.add("球员统计");
writeTable(playerStatsSheet, bundle.player_stats);

const standingsSheet = workbook.worksheets.add("小组积分榜");
writeTable(standingsSheet, bundle.standings);

const topScorersSheet = workbook.worksheets.add("射手榜TOP20");
writeTable(topScorersSheet, topRows(normalizeRows(bundle.player_stats), "进球"));

const topAssistsSheet = workbook.worksheets.add("助攻榜TOP20");
writeTable(topAssistsSheet, topRows(normalizeRows(bundle.player_stats), "助攻"));

const topRatingSheet = workbook.worksheets.add("评分TOP20");
writeTable(topRatingSheet, topRows(normalizeRows(bundle.player_stats), "评分"));

await fs.mkdir(path.dirname(outputXlsxPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const inspect = await workbook.inspect({
  kind: "table",
  range: "A1:F12",
  sheetId: "说明",
  tableMaxRows: 12,
  tableMaxCols: 6,
});
console.log(inspect.ndjson);

const previewRanges = {
  "说明": "A1:B12",
  "球员信息": "A1:N20",
  "球员统计": "A1:AC20",
  "小组积分榜": "A1:N20",
};

for (const [sheetName, range] of Object.entries(previewRanges)) {
  const image = await workbook.render({
    sheetName,
    range,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(previewDir, `${sheetName}.png`),
    new Uint8Array(await image.arrayBuffer()),
  );
}

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputXlsxPath);
