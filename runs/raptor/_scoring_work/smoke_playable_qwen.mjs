// Quick smoke test: does the single-file playable boot via file:// with no console errors?
import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const filePath = path.resolve('D:/dev/ab-tasks/_runs/raptor/qwen/artifacts/showcase/raptor-qwen-playable.html');
const fileUrl = pathToFileURL(filePath).href;

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
page.on('pageerror', (err) => errors.push('pageerror: ' + err.message));

await page.goto(fileUrl, { waitUntil: 'load', timeout: 30000 });
try {
  await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, null, { timeout: 15000 });
} catch (e) {
  console.error('WARNING: ready never true:', e.message);
}
const state = await page.evaluate(() => window.__raptor || null);
console.log(JSON.stringify({ fileUrl, ready: state ? state.ready : null, state, consoleErrors: errors.slice(0, 10) }, null, 2));
await browser.close();
