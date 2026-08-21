#!/usr/bin/env node
/**
 * capture_m1.mjs -- takes a 320x200 screenshot of #raptor-canvas once
 * window.__raptor.ready is true, for M1 SSIM scoring.
 *
 * Usage: node capture_m1.mjs <url> <out-png> [--timeout-ms 30000]
 */
import { chromium } from 'playwright';

const [, , url, outPng, ...rest] = process.argv;
let timeoutMs = 30000;
for (let i = 0; i < rest.length; i++) {
  if (rest[i] === '--timeout-ms') timeoutMs = parseInt(rest[++i], 10);
}

if (!url || !outPng) {
  console.error('Usage: node capture_m1.mjs <url> <out-png> [--timeout-ms 30000]');
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 640, height: 480 } });
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message));

  await page.goto(url, { waitUntil: 'load', timeout: timeoutMs });

  // Wait for window.__raptor.ready === true
  try {
    await page.waitForFunction(
      () => window.__raptor && window.__raptor.ready === true,
      null,
      { timeout: timeoutMs }
    );
  } catch (e) {
    console.error('WARNING: window.__raptor.ready never became true within timeout:', e.message);
  }

  // Give it a couple extra frames to settle
  await page.waitForTimeout(300);

  const canvas = await page.$('#raptor-canvas');
  if (!canvas) {
    console.error('ERROR: #raptor-canvas not found on page');
    console.error('console errors seen:', JSON.stringify(consoleErrors, null, 2));
    await browser.close();
    process.exit(1);
  }

  const box = await canvas.evaluate((el) => ({
    width: el.width,
    height: el.height,
    cssWidth: el.getBoundingClientRect().width,
    cssHeight: el.getBoundingClientRect().height,
  }));
  console.error('canvas internal size:', box.width, 'x', box.height, ' css size:', box.cssWidth, 'x', box.cssHeight);

  // Screenshot the raw canvas pixel buffer via toDataURL to avoid CSS-scaling artifacts.
  const dataUrl = await canvas.evaluate((el) => el.toDataURL('image/png'));
  const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
  const fs = await import('node:fs');
  fs.writeFileSync(outPng, Buffer.from(base64, 'base64'));
  console.error('wrote', outPng);

  const raptorState = await page.evaluate(() => window.__raptor || null);
  console.error('window.__raptor at capture time:', JSON.stringify(raptorState));
  if (consoleErrors.length) {
    console.error('console errors seen during load:', JSON.stringify(consoleErrors.slice(0, 20), null, 2));
  }

  await browser.close();
  console.log(JSON.stringify({ ok: true, canvas: box, ready: raptorState ? raptorState.ready : null }));
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
