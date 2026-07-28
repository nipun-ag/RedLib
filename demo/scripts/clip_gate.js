/**
 * CLIP: gate
 * Records the responsible-use gate being acknowledged.
 * Shows RedLib's identity, corpus count, research conditions, and entry.
 *
 * Output: demo/output/clip_gate.webm (converted to mp4 separately)
 */

import { launch, close } from 'C:/Users/nipun/.ai/tools/playwright/core/browser.js';
import { waitForLoad, pause } from 'C:/Users/nipun/.ai/tools/playwright/core/interact.js';
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

// Clear any existing gate acknowledgement so gate actually shows
await context.addInitScript(() => {
  window.localStorage.removeItem('redlib.researchGateAcknowledged');
});

await page.goto('https://redlib.bynipun.com');
await waitForLoad(page);

// Hold on gate — let corpus count animate in
await pause(2500);

// Scroll down slightly to show conditions
await page.mouse.wheel(0, 120);
await pause(1200);

// Click the checkbox
await page.click('[id="agreement-copy"]');
await pause(800);

// Hold on checked state before entering
await pause(1000);

// Click Enter Research Workspace
await page.click('button[type="submit"]');

// Wait for workspace to load
await page.waitForURL('**/workspace', { timeout: 8000 });
await waitForLoad(page);
await pause(1500);

await close({ browser, page, record: true, outputName: 'clip_gate' });
