/**
 * CLIP: search
 * Records a full search query — typing, results loading, AI summary, result cards.
 *
 * Output: demo/output/clip_search.webm
 */

import { launch, close } from 'C:/Users/nipun/.ai/tools/playwright/core/browser.js';
import { waitForLoad, pause, typeSlowly, scrollDown } from 'C:/Users/nipun/.ai/tools/playwright/core/interact.js';
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

// Focus and type query slowly — looks intentional on camera
await page.click('#workspace-search');
await pause(500);
await typeSlowly(page, '#workspace-search', 'multi-turn context manipulation', 75);
await pause(1000);

// Click Search
await page.click('button:has-text("Search")');

// Wait for AI summary to appear
await page.waitForSelector('h2:has-text("AI Summary")', { timeout: 20000 });
await pause(1200);

// Let viewer read the summary
await pause(2000);

// Scroll down to show result cards
await scrollDown(page, 300, 10);
await pause(1000);

await scrollDown(page, 300, 10);
await pause(1500);

await close({ browser, page, record: true, outputName: 'clip_search' });
