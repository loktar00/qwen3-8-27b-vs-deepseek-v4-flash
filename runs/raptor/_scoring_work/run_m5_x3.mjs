// Run the real (600s-cap) amended checkM5 three times against a model's
// build. Each attempt starts a fresh browser page (fresh game session).
// Writes results as a JSON array to stdout (one line) and logs progress
// to stderr.
import path from 'node:path';
import { checkM5, CHECKER_VERSION } from '../../../_raptor-support/checks/m2_m5_playwright.mjs';
import http from 'node:http';
import fs from 'node:fs';

const buildDir = process.argv[2];
const port = parseInt(process.argv[3] || '8936', 10);
const nAttempts = parseInt(process.argv[4] || '3', 10);

if (!buildDir) {
  console.error('Usage: node run_m5_x3.mjs <build-dir> [port] [nAttempts]');
  process.exit(1);
}

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.glb': 'model/gltf-binary',
  '.png': 'image/png', '.wav': 'audio/wav', '.mp3': 'audio/mpeg',
};

function serve(dir, p) {
  return new Promise((resolve) => {
    const root = path.resolve(dir);
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const rel = urlPath === '/' ? '/index.html' : urlPath;
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

const server = await serve(buildDir, port);
const browser = await chromium.launch({ headless: true });
const attempts = [];
try {
  for (let i = 1; i <= nAttempts; i++) {
    console.error(`[attempt ${i}/${nAttempts}] starting at ${new Date().toISOString()}`);
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, { timeout: 15000 });
    const startedAt = Date.now();
    const result = await checkM5(page); // default 600000ms cap
    const elapsed_s = (Date.now() - startedAt) / 1000;
    console.error(`[attempt ${i}/${nAttempts}] done: pass=${result.pass} reason=${result.reason} final_wave=${result.final_wave} died=${result.died} elapsed_s=${elapsed_s.toFixed(1)}`);
    attempts.push({ attempt: i, ...result, elapsed_s });
    await page.close().catch(() => {});
  }
} finally {
  await browser.close().catch(() => {});
  await new Promise((r) => server.close(r));
}

console.log(JSON.stringify({ checker_version: CHECKER_VERSION, attempts }, null, 2));
