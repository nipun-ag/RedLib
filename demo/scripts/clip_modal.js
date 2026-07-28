/**
 * CLIP: modal
 * Records opening a result card into the full prompt modal.
 * Shows prompt text and source attribution.
 *
 * Output: demo/output/clip_modal.webm
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
await pause(1500);

// Run a search to get results
await page.click('#workspace-search');
await pause(400);
await typeSlowly(page, '#workspace-search', 'system prompt override', 70);
await pause(800);
await page.click('button:has-text("Search")');

// Wait for results
await page.waitForSelector('h2:has-text("AI Summary")', { timeout: 20000 });
await pause(1500);

// Scroll to first result card
await scrollDown(page, 280, 8);
await pause(1000);

// Click "View Full Prompt →" on first result
const viewButton = page.locator('button:has-text("View Full Prompt")').first();
await viewButton.scrollIntoViewIfNeeded();
await pause(600);
await viewButton.click();

// Wait for modal to open and prompt to load
await page.waitForSelector('pre', { timeout: 8000 });
await pause(1500);

// Scroll through the modal content slowly
const scrollArea = page.locator('[data-radix-scroll-area-viewport]').first();
await scrollArea.evaluate(el => {
  el.scrollBy({ top: 200, behavior: 'smooth' });
});
await pause(1000);

await scrollArea.evaluate(el => {
  el.scrollBy({ top: 200, behavior: 'smooth' });
});
await pause(1500);

await close({ browser, page, record: true, outputName: 'clip_modal' });
