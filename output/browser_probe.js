const { chromium } = require('playwright-core');
(async() => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = [];
  page.on('console', msg => logs.push(`[console:${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => logs.push(`[pageerror] ${err.message}`));
  page.on('requestfailed', req => logs.push(`[requestfailed] ${req.method()} ${req.url()} ${req.failure()?.errorText || ''}`));
  const urls = [
    'http://127.0.0.1:4176/ai-predict',
    'http://127.0.0.1:4176/matches/1594',
    'http://127.0.0.1:4176/players/2350?tab=radar'
  ];
  for (const url of urls) {
    logs.push(`=== ${url} ===`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(8000);
    logs.push((await page.locator('body').innerText()).slice(0, 3500));
  }
  console.log(logs.join('\n\n'));
  await browser.close();
})();
