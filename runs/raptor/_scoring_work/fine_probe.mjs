// Fine-grained probe: poll every 100ms for the first ~3s to see exactly
// when enemies appear and how player.x actually evolves, to distinguish
// "real threat-driven movement" from "wall-hugging tie-break default".
import path from 'node:path';
import http from 'node:http';
import fs from 'node:fs';

const buildDir = 'D:/dev/ab-tasks/_runs/raptor/dsv4/scratch';
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
        if (err) { res.writeHead(404); res.end('not found'); return; }
        const ext = path.extname(fp).toLowerCase();
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.listen(p, '127.0.0.1', () => resolve(server));
  });
}

const { chromium } = await import('playwright');
const server = await serve(buildDir, 8937);
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8937/', { waitUntil: 'load' });
  const t0 = Date.now();
  await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, { timeout: 15000 });
  const readyAt = Date.now() - t0;
  console.error('ready at +' + readyAt + 'ms');

  // Snapshot state immediately at ready, before any key input.
  const atReady = await page.evaluate(() => {
    const r = window.__raptor;
    return {
      player: r.player,
      enemies: (r.enemies || []).filter(e => e && e.alive !== false).map(e => ({x: e.x, y: e.y})),
    };
  });
  console.log(JSON.stringify({ event: 'at_ready', t_ms: readyAt, ...atReady }));

  // Now hold Space (fire) but issue NO steering input at all -- pure baseline,
  // to see whether the game itself moves the player (it shouldn't) and to
  // watch threat/enemy arrival independent of the checker's dodge logic.
  await page.keyboard.down('Space');
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 100));
    const s = await page.evaluate(() => {
      const r = window.__raptor;
      if (!r) return null;
      return {
        x: r.player && r.player.x,
        y: r.player && r.player.y,
        aliveEnemies: (r.enemies || []).filter(e => e && e.alive !== false).length,
        enemyPositions: (r.enemies || []).filter(e => e && e.alive !== false).map(e => ({x: e.x, y: e.y})),
      };
    });
    console.log(JSON.stringify({ t_ms: Date.now() - t0, ...s }));
  }
  await page.keyboard.up('Space');
} finally {
  await browser.close().catch(() => {});
  await new Promise((r) => server.close(r));
}
