// Showcase recording: serve Qwen3.8-27B's Raptor port, drive it with the SAME
// amended M5 autoplay checker used for scoring, record video, and grab 3
// screenshots (first wave ~2s, mid-fight ~20s w/ HUD, ~40s or death frame).
// Headless only. Adapted from DeepSeek's showcase_record.mjs in this same
// directory (same script, different paths/canvas scale for this build's own
// index.html; run from here so playwright resolves the same way DSV4's did).
import path from 'node:path';
import http from 'node:http';
import fs from 'node:fs';
import { checkM5, CHECKER_VERSION } from '../../../_raptor-support/checks/m2_m5_playwright.mjs';

const buildDir = 'D:/dev/ab-tasks/_runs/raptor/qwen/scratch';
const outDir = 'D:/dev/ab-tasks/_runs/raptor/qwen/artifacts/showcase';
fs.mkdirSync(outDir, { recursive: true });

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
const server = await serve(buildDir, 8954);
const browser = await chromium.launch({ headless: true });

const consoleErrors = [];
let died = false, deathShotTaken = false;
const shots = {};

try {
  const context = await browser.newContext({
    viewport: { width: 960, height: 600 },
    recordVideo: { dir: outDir, size: { width: 960, height: 600 } },
  });
  const page = await context.newPage();
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message));

  await page.goto('http://127.0.0.1:8954/', { waitUntil: 'load' });

  // Presentation-only override for the recording: fill the 960x600 frame
  // at a clean integer 3x scale (canvas internal buffer stays 320x200,
  // untouched) so the capture is clean. This build has no #status/#controls
  // overlay elements to hide (its own index.html is minimal). Does not
  // modify any port source file on disk.
  await page.addStyleTag({
    content: `
      html, body { background:#000 !important; }
      canvas#raptor-canvas { width:960px !important; height:600px !important; image-rendering:pixelated; }
    `,
  });

  await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, { timeout: 15000 });
  const t0 = Date.now();
  console.error('ready, starting 75s showcase run, CHECKER_VERSION=' + CHECKER_VERSION);

  async function screenshotScheduler() {
    // Shot 1: ~2s, first wave.
    await new Promise((r) => setTimeout(r, Math.max(0, 2000 - (Date.now() - t0))));
    shots.shot1 = path.join(outDir, 'shot1_first-wave.png');
    await page.screenshot({ path: shots.shot1 }).catch((e) => console.error('shot1 failed', e.message));
    console.error('shot1 taken at +' + (Date.now() - t0) + 'ms');

    // Shot 2: ~20s, mid-fight with HUD.
    await new Promise((r) => setTimeout(r, Math.max(0, 20000 - (Date.now() - t0))));
    shots.shot2 = path.join(outDir, 'shot2_mid-fight.png');
    await page.screenshot({ path: shots.shot2 }).catch((e) => console.error('shot2 failed', e.message));
    console.error('shot2 taken at +' + (Date.now() - t0) + 'ms');

    // Shot 3: whichever comes first -- death, or ~40s.
    while (Date.now() - t0 < 40000 && !died) {
      await new Promise((r) => setTimeout(r, 200));
    }
    shots.shot3 = path.join(outDir, died ? 'shot3_death.png' : 'shot3_t40s.png');
    await page.screenshot({ path: shots.shot3 }).catch((e) => console.error('shot3 failed', e.message));
    deathShotTaken = true;
    console.error('shot3 (' + (died ? 'death' : 't40s') + ') taken at +' + (Date.now() - t0) + 'ms');
  }

  async function deathWatcher() {
    while (!deathShotTaken) {
      const alive = await page.evaluate(() => window.__raptor && window.__raptor.player ? window.__raptor.player.alive : true).catch(() => true);
      if (alive === false) { died = true; break; }
      await new Promise((r) => setTimeout(r, 150));
    }
  }

  const [m5result] = await Promise.all([
    checkM5(page, { timeoutMs: 75000 }),
    screenshotScheduler(),
    deathWatcher(),
  ]);

  console.error('M5 run result: ' + JSON.stringify(m5result));
  const elapsed = Date.now() - t0;

  await context.close(); // finalizes the video file
  const videoPath = await page.video().path();
  console.log(JSON.stringify({ videoPath, elapsed_ms: elapsed, m5result, shots, consoleErrors }));
} finally {
  await browser.close().catch(() => {});
  await new Promise((r) => server.close(r));
}
