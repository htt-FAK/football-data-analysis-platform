import { chromium } from "../../frontend/node_modules/playwright/index.js";
import fs from "node:fs/promises";
import path from "node:path";

const baseUrl = "http://127.0.0.1:4176";
const pages = [
  { name: "players", path: "/players" },
  { name: "matches", path: "/matches" },
  { name: "ai-predict", path: "/ai-predict" },
];

const outputDir = path.resolve("output/playwright");
await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1080 },
});

for (const pageInfo of pages) {
  const page = await context.newPage();
  const consoleMessages = [];
  const requestFailures = [];
  const pageErrors = [];

  page.on("console", (msg) => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });
  page.on("requestfailed", (req) => {
    requestFailures.push({
      url: req.url(),
      error: req.failure()?.errorText ?? "unknown",
    });
  });
  page.on("pageerror", (err) => {
    pageErrors.push(err.stack || err.message);
  });

  await page.goto(`${baseUrl}${pageInfo.path}`, { waitUntil: "networkidle", timeout: 45000 });
  await page.screenshot({ path: path.join(outputDir, `${pageInfo.name}.png`), fullPage: true });

  const bodyText = await page.locator("body").innerText();
  await fs.writeFile(
    path.join(outputDir, `${pageInfo.name}.json`),
    JSON.stringify(
      {
        url: `${baseUrl}${pageInfo.path}`,
        consoleMessages,
        requestFailures,
        pageErrors,
        bodyPreview: bodyText.slice(0, 4000),
      },
      null,
      2
    ),
    "utf-8"
  );

  await page.close();
}

await browser.close();
