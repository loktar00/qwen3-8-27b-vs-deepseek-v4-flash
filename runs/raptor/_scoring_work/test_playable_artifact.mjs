// Test the artifact-ready variant the same two ways as the standalone build.
import path from 'node:path';
import http from 'node:http';
import fs from 'node:fs';
import { checkM2 } from '../../../_raptor-support/checks/m2_m5_playwright.mjs';

const playableDir = 'D:/dev/ab-tasks/_runs/raptor/dsv4/artifacts/showcase';
const fileName = 'raptor-deepseek-playable.artifact.html';
const playableFile = path.join(playableDir, fileName);

const MIME = { '.html': 'text/html; charset=utf-8' };
function serve(dir, p) {
  return new Promise((resolve) => {
    const root = path.resolve(dir);
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const rel = urlPath === '/' ? '/' + fileName : urlPath;
      const fp = path.resolve(path.join(root, rel));
      if (!fp.startsWith(root)) { res.writeHead(403); res.end(); return; }
      fs.readFile(fp, (err, data) => {
        if (err) { res.writeHead(404); res.end('not found: ' + urlPath); return; }
        const ext = path.extname(fp).toLowerCase();
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.listen(p, '127.0.0.1', () => resolve(server));
  });
}

const { chromium } = await import('playwright');
const browser = await chromium.launch({ headless: true });
const results = {};

{
  const server = await serve(playableDir, 8942);
  const consoleErrors = [];
  try {
    const page = await browser.newPage();
    page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message));
    await page.goto('http://127.0.0.1:8942/', { waitUntil: 'load' });
    const m2 = await checkM2(page);
    const title = await page.title();
    results.http = { m2, consoleErrors, title };
    await page.close();
  } finally {
    await new Promise((r) => server.close(r));
  }
}

{
  const consoleErrors = [];
  const page = await browser.newPage();
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message));
  const fileUrl = 'file:///' + playableFile.replace(/\\/g, '/');
  await page.goto(fileUrl, { waitUntil: 'load' });
  try {
    await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, { timeout: 15000 });
    const state = await page.evaluate(() => ({
      ready: window.__raptor.ready,
      player: window.__raptor.player,
      wave: window.__raptor.wave,
    }));
    const title = await page.title();
    results.file = { booted: true, state, consoleErrors, title };
  } catch (e) {
    results.file = { booted: false, error: e.message, consoleErrors };
  }
  await page.close();
}

await browser.close();
console.log(JSON.stringify(results, null, 2));
