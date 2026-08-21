// Instrumented replica of checkM5's dodge decision logic (IDENTICAL math,
// logging added) to verify the strict-> gate and see exactly what threat
// state triggers the first movement. Does not modify the shared checker.
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

function mulberry32(seed) {
  let a = seed >>> 0;
  return function rng() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const { chromium } = await import('playwright');
const server = await serve(buildDir, 8938);
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8938/', { waitUntil: 'load' });
  const t0 = Date.now();
  await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, { timeout: 15000 });
  console.error('ready at +' + (Date.now() - t0) + 'ms');

  const rng = mulberry32(1);
  const reachDx = 24, columnStep = 2, collisionRadius = 24, collisionMultiplier = 4, verticalWindow = 120;
  let heldDirection = null;
  let firstMoveLogged = false;

  function threatAtColumn(colX, sources) {
    let total = 0;
    for (const src of sources) {
      const dy = src.py - src.y;
      if (!(dy > 0 && dy < verticalWindow)) continue;
      const dx = colX - src.x;
      const w = 1 / (1 + Math.abs(dx) / 16);
      total += w;
      if (Math.hypot(dx, dy) < collisionRadius) total += collisionMultiplier * w;
    }
    return total;
  }
  async function setDirection(desired) {
    if (desired === heldDirection) return;
    if (heldDirection) await page.keyboard.up(heldDirection).catch(() => {});
    if (desired) await page.keyboard.down(desired).catch(() => {});
    heldDirection = desired;
  }

  await page.keyboard.down('Space');
  const deadline = Date.now() + 8000; // 8s probe window, not the real 600s cap
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => window.__raptor || null);
    if (state && state.player && typeof state.player.x === 'number') {
      const px = state.player.x, py = state.player.y;
      const aliveEnemies = (Array.isArray(state.enemies) ? state.enemies : [])
        .filter((e) => e && e.alive !== false && typeof e.x === 'number' && typeof e.y === 'number')
        .map((e) => ({ x: e.x, y: e.y, py }));
      const sources = aliveEnemies; // no owner-marked projectiles in this build
      const currentThreat = threatAtColumn(px, sources);

      let bestCol = px, bestThreat = currentThreat, ties = [px];
      for (let dx = -reachDx; dx <= reachDx; dx += columnStep) {
        const col = px + dx;
        const t = threatAtColumn(col, sources);
        if (t < bestThreat - 1e-9) { bestThreat = t; bestCol = col; ties = [col]; }
        else if (Math.abs(t - bestThreat) <= 1e-9) ties.push(col);
      }
      if (ties.length > 1) bestCol = ties[Math.floor(rng() * ties.length)];

      let desired = null;
      const willMove = currentThreat > bestThreat + 1e-9;
      if (willMove) {
        if (bestCol < px) desired = 'ArrowLeft';
        else if (bestCol > px) desired = 'ArrowRight';
      }

      if (willMove && !firstMoveLogged) {
        firstMoveLogged = true;
        console.log(JSON.stringify({
          event: 'FIRST_MOVE_TRIGGER', t_ms: Date.now() - t0, px, py, currentThreat, bestThreat, bestCol,
          tieCount: ties.length, desired, aliveEnemyCount: aliveEnemies.length,
          enemiesInWindow: aliveEnemies.filter(e => { const dy = py - e.y; return dy > 0 && dy < verticalWindow; }).length,
          enemyDetail: aliveEnemies.map(e => ({ x: e.x, y: e.y, dy: py - e.y })),
        }));
      } else if (!willMove) {
        console.log(JSON.stringify({ t_ms: Date.now() - t0, px, currentThreat, bestThreat, tieCount: ties.length, willMove: false, aliveEnemyCount: aliveEnemies.length }));
      }

      await setDirection(desired);
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  await setDirection(null).catch(() => {});
  await page.keyboard.up('Space').catch(() => {});
} finally {
  await browser.close().catch(() => {});
  await new Promise((r) => server.close(r));
}
