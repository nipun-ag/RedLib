/**
 * CLIP: browse
 * Records browsing the corpus by technique category.
 * Shows sidebar, category selection, results loading, slow scroll.
 *
 * Output: demo/output/clip_browse.webm
 */

import { launch, close } from 'C:/Users/nipun/.ai/tools/playwright/core/browser.js';
import { waitForLoad, pause, scrollDown } from 'C:/Users/nipun/.ai/tools/playwright/core/interact.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.resolve(__dirname, '../output');

const { browser, context, page } = await launch({
  headless: true,
  record: true,
  outputDir: OUTPUT_DIR,
  width: 1280,
  height: 800,
});

// Bypass gate
await context.addInitScript(() => {
  window.localStorage.setItem('redlib.researchGateAcknowledged', 'true');
});

await page.goto('https://redlib.bynipun.com/workspace');
await waitForLoad(page);
await pause(1800);

// Switch to Browse tab
await page.click('[data-value="browse"]');
await pause(1000);

// Click first category in sidebar — wait for it to appear
await page.waitForSelector('[role="button"]', { timeout: 6000 });
const categoryButtons = await page.locator('aside button, [role="listitem"] button').all();
if (categoryButtons.length > 0) {
  await categoryButtons[0].click();
}
await pause(800);

// Wait for results to load
await page.waitForSelector('article.panel', { timeout: 10000 });
await pause(1200);

// Scroll slowly through results
await scrollDown(page, 500, 14);
await pause(1000);

// Scroll a bit more
await scrollDown(page, 300, 10);
await pause(1500);

await close({ browser, page, record: true, outputName: 'clip_browse' });
