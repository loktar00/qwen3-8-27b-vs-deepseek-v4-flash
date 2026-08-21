// Smoke test: confirm the amended (v2) checkM5 dodge actually moves the
// player. Serves DeepSeek's build, runs a SHORT capped M5 session (30s),
// logging player.x every ~1s so we can see whether the dodge logic is
// steering the ship (not just holding Space and standing still).
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkM5, CHECKER_VERSION } from '../../../_raptor-support/checks/m2_m5_playwright.mjs';
import http from 'node:http';
import fs from 'node:fs';

const buildDir = 'D:/dev/ab-tasks/_runs/raptor/dsv4/scratch';

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.glb': 'model/gltf-binary',
  '.png': 'image/png', '.wav': 'audio/wav', '.mp3': 'audio/mpeg',
};

function serve(dir, port) {
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
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

const { chromium } = await import('playwright');

const server = await serve(buildDir, 8935);
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8935/', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, { timeout: 15000 });

  const xLog = [];
  const pollHandle = setInterval(async () => {
    try {
      const s = await page.evaluate(() => window.__raptor ? { x: window.__raptor.player && window.__raptor.player.x, wave: window.__raptor.wave, alive: window.__raptor.player && window.__raptor.player.alive, enemies: (window.__raptor.enemies||[]).filter(e=>e && e.alive!==false).length } : null);
      xLog.push({ t: Date.now(), ...s });
    } catch {}
  }, 1000);

  console.error('CHECKER_VERSION:', CHECKER_VERSION);
  const result = await checkM5(page, { timeoutMs: 30000 }); // 30s smoke cap, not the real 600s
  clearInterval(pollHandle);

  console.log(JSON.stringify({ result, xLog }, null, 2));
} finally {
  await browser.close().catch(() => {});
  await new Promise((r) => server.close(r));
}
