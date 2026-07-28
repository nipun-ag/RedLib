/**
 * Runs all 4 demo clips sequentially.
 * Each clip saves to demo/output/ as clip_*.webm
 *
 * Usage: node demo/scripts/run_all.js
 */

import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const clips = ['clip_gate', 'clip_browse', 'clip_search', 'clip_modal'];

for (const clip of clips) {
  console.log(`\n▶ Recording ${clip}...`);
  try {
    execSync(`node "${path.join(__dirname, clip + '.js')}"`, { stdio: 'inherit' });
    console.log(`✓ ${clip} done`);
  } catch (err) {
    console.error(`✗ ${clip} failed:`, err.message);
  }
}

console.log('\n✓ All clips recorded. Check demo/output/');
