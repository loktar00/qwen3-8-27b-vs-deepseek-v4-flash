#!/usr/bin/env node
/**
 * m2_m5_playwright.mjs -- M2..M5 milestone checker for the Raptor A/B benchmark.
 *
 * PREREQUISITE (not installed by this script):
 *     npm install playwright
 *     npx playwright install chromium
 *
 * This is a skeleton: it is syntactically complete and runnable end to end,
 * but several checks (M3 hit alignment, M5 dodge/respawn handling) are
 * explicitly best-effort and marked TODO -- see the comments in each check
 * function.
 *
 * What it does:
 *   1. Starts a local static file server (built-in `http` module only, no
 *      external framework) rooted at a model's build directory
 *      (which must contain index.html).
 *   2. Launches Chromium via Playwright and navigates to it.
 *   3. Runs checkM2 -> checkM3 -> checkM4 -> checkM5 in sequence, each
 *      gated on the previous one's `pass` (since M2..M5 form a ladder --
 *      see the "GATING" note in main() for the one caveat re: M3's
 *      best-effort pass criterion). Each check function is standalone and
 *      independently callable/testable -- they only need a Playwright
 *      `page` (and, for M5, a timeout) as input.
 *   4. Prints exactly one JSON object to stdout:
 *          {"m2": {...}, "m3": {...}, "m4": {...}, "m5": {...}}
 *      Each milestone's value includes at least `pass: boolean` plus
 *      whatever details were measured along the way. (M1 is scored
 *      separately by m1_ssim.py via screenshot, not by this script.)
 *
 * Usage:
 *   node m2_m5_playwright.mjs <build-dir> [--port 8934] [--timeout-ms 300000] [--headed]
 *
 *   <build-dir>     Path to the model's build directory (contains index.html). Required.
 *   --port          Port for the local static server. Default: 8934.
 *   --timeout-ms    Bound on the M5 autoplay loop, in ms. Default: 300000 (5 min).
 *   --headed        Run Chromium with a visible window (default: headless).
 *   --help          Print usage and exit.
 *
 * Interface contract this script checks against (given verbatim to models too):
 *   - <canvas id="raptor-canvas"> with canvas.width===320, canvas.height===200.
 *   - ArrowUp/Down/Left/Right move the ship; Space fires. Standard DOM
 *     keydown/keyup on the page/window -- Playwright's real
 *     page.keyboard.down/up work directly, no special hook needed.
 *   - window.__raptor = {
 *       ready, player: {x,y,alive}, projectiles: [...], enemies: [...],
 *       hud: {score, shields}, audio: {contextState, sfxCount},
 *       wave, sectorComplete
 *     }
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

// Playwright is an external dependency (see prerequisite note above). It is
// only imported lazily inside main() so that other scripts can still
// `import { checkM2, checkM3, checkM4, checkM5 } from './m2_m5_playwright.mjs'`
// (e.g. for unit testing individual checks against a hand-built `page`
// stub) without needing playwright installed just to load this module.
let chromium;

// --------------------------------------------------------------------------
// Small helpers
// --------------------------------------------------------------------------

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Tap a key: keydown, hold briefly, keyup. */
async function tapKey(page, key, holdMs = 60) {
  await page.keyboard.down(key);
  await sleep(holdMs);
  await page.keyboard.up(key);
}

/** Read the full window.__raptor state (or null if not present yet). */
async function readRaptorState(page) {
  return page.evaluate(() => window.__raptor || null);
}

// --------------------------------------------------------------------------
// Static file server (build dir -> http://127.0.0.1:PORT/)
// --------------------------------------------------------------------------

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.wav': 'audio/wav',
  '.mp3': 'audio/mpeg',
  '.ogg': 'audio/ogg',
  '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.wasm': 'application/wasm',
  '.map': 'application/json; charset=utf-8',
};

/**
 * Start a static file server rooted at `buildDir`. Resolves with the
 * listening `http.Server` once bound (so the caller can read the actual
 * port via server.address().port, useful if port 0 / an auto-assigned
 * port was requested).
 */
function createStaticServer(buildDir, port) {
  const root = path.resolve(buildDir);
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
        const relPath = urlPath === '/' ? '/index.html' : urlPath;
        const filePath = path.resolve(path.join(root, relPath));

        // Prevent path traversal outside the build dir.
        if (!filePath.startsWith(root)) {
          res.writeHead(403, { 'Content-Type': 'text/plain' });
          res.end('Forbidden');
          return;
        }

        fs.readFile(filePath, (err, data) => {
          if (err) {
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end(`Not found: ${urlPath}`);
            return;
          }
          const ext = path.extname(filePath).toLowerCase();
          res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
          res.end(data);
        });
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end(`Server error: ${e && e.message}`);
      }
    });
    server.on('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

// --------------------------------------------------------------------------
// M2: movement + fire
// --------------------------------------------------------------------------

/**
 * M2: ArrowRight moves the ship; Space fires and adds a projectile.
 * @param {import('playwright').Page} page
 * @param {{readyTimeoutMs?: number}} [opts]
 */
export async function checkM2(page, opts = {}) {
  const readyTimeoutMs = opts.readyTimeoutMs ?? 15000;

  try {
    await page.waitForFunction(() => window.__raptor && window.__raptor.ready === true, {
      timeout: readyTimeoutMs,
    });
  } catch {
    return { pass: false, reason: `window.__raptor.ready did not become true within ${readyTimeoutMs}ms` };
  }

  const before = await readRaptorState(page);
  if (!before || !before.player) {
    return { pass: false, reason: 'window.__raptor.player missing after ready' };
  }
  const startX = before.player.x;
  const startY = before.player.y;
  const projectilesBefore = Array.isArray(before.projectiles) ? before.projectiles.length : 0;

  // Dispatch a few ArrowRight keydown/keyup events (real DOM key events via
  // Playwright -- no special test hook needed per the interface contract).
  for (let i = 0; i < 5; i++) {
    await tapKey(page, 'ArrowRight', 60);
    await sleep(40);
  }

  const afterMove = await readRaptorState(page);
  const moved =
    !!afterMove &&
    !!afterMove.player &&
    (afterMove.player.x !== startX || afterMove.player.y !== startY);

  // Fire once and confirm a projectile was added.
  await tapKey(page, 'Space', 60);
  await sleep(150); // allow the game loop a frame or two to update state

  const afterFire = await readRaptorState(page);
  const projectilesAfter =
    afterFire && Array.isArray(afterFire.projectiles) ? afterFire.projectiles.length : projectilesBefore;
  const fired = projectilesAfter > projectilesBefore;

  return {
    pass: moved && fired,
    moved,
    fired,
    player_start: { x: startX, y: startY },
    player_after_move: afterMove && afterMove.player ? { x: afterMove.player.x, y: afterMove.player.y } : null,
    projectiles_before: projectilesBefore,
    projectiles_after: projectilesAfter,
  };
}

// --------------------------------------------------------------------------
// M3: enemies spawn + hit registration + death flag presence
// --------------------------------------------------------------------------

/**
 * M3: wave-1 enemies spawn; a projectile hit decrements enemy HP / removes
 * the enemy; player can die.
 *
 * BEST-EFFORT: precise player-under-enemy alignment depends entirely on the
 * model's actual movement speed/hitbox/game feel, which we don't know ahead
 * of time. This does a coarse "nudge toward the enemy's x, then hold fire"
 * loop rather than anything that guarantees a hit. Treat `hit_registered:
 * false` as inconclusive, not necessarily a real M3 failure -- a human (or
 * a smarter aim loop) should double check borderline cases.
 *
 * TODO: full death-triggering (actually getting the player killed by an
 * enemy/projectile to exercise player.alive -> false) is out of scope for
 * this skeleton. We only report whether `player.alive` is *present* as a
 * boolean, not that death actually works end to end.
 *
 * @param {import('playwright').Page} page
 * @param {{enemyTimeoutMs?: number, alignMs?: number, fireMs?: number}} [opts]
 */
export async function checkM3(page, opts = {}) {
  const enemyTimeoutMs = opts.enemyTimeoutMs ?? 10000;
  const alignMs = opts.alignMs ?? 1500;
  const fireMs = opts.fireMs ?? 2000;

  try {
    await page.waitForFunction(
      () => window.__raptor && Array.isArray(window.__raptor.enemies) && window.__raptor.enemies.length > 0,
      { timeout: enemyTimeoutMs }
    );
  } catch {
    return { pass: false, reason: `no enemies spawned within ${enemyTimeoutMs}ms` };
  }

  const state = await readRaptorState(page);
  const target = state.enemies.find((e) => e && e.alive !== false) || state.enemies[0];
  if (!target) {
    return { pass: false, reason: 'enemies array present but empty on read' };
  }
  const targetId = target.id;
  const initialHp = target.hp;

  // TODO(best-effort): coarse alignment toward the target enemy's x. This
  // assumes ArrowLeft/ArrowRight move the player toward lower/higher x,
  // which matches the interface contract but not necessarily the model's
  // exact speed/acceleration curve.
  const alignDeadline = Date.now() + alignMs;
  while (Date.now() < alignDeadline) {
    const s = await readRaptorState(page);
    if (!s || !s.player) break;
    const dx = target.x - s.player.x;
    if (Math.abs(dx) < 4) break;
    await tapKey(page, dx > 0 ? 'ArrowRight' : 'ArrowLeft', 50);
    await sleep(30);
  }

  // Hold fire for a bit.
  await page.keyboard.down('Space');
  await sleep(fireMs);
  await page.keyboard.up('Space');
  await sleep(150);

  const finalState = await readRaptorState(page);
  const stillPresent = finalState && Array.isArray(finalState.enemies)
    ? finalState.enemies.find((e) => e && e.id === targetId)
    : undefined;

  let hitRegistered;
  if (stillPresent === undefined) {
    // Enemy no longer in the array at all -- treat as killed/removed.
    hitRegistered = true;
  } else {
    hitRegistered = typeof stillPresent.hp === 'number' && typeof initialHp === 'number'
      ? stillPresent.hp < initialHp
      : stillPresent.alive === false;
  }

  const aliveReported =
    !!finalState && !!finalState.player && typeof finalState.player.alive === 'boolean';

  return {
    pass: hitRegistered && aliveReported,
    hit_registered: hitRegistered,
    hit_registered_note: 'best-effort: coarse aim, not a precision hit test -- see TODO in checkM3',
    alive_reported: aliveReported,
    target_enemy_id: targetId,
    initial_hp: initialHp,
    final_hp: stillPresent ? stillPresent.hp : null,
    enemy_removed: stillPresent === undefined,
  };
}

// --------------------------------------------------------------------------
// M4: HUD + Web Audio
// --------------------------------------------------------------------------

/**
 * M4: HUD (score/shields) renders; Web Audio context running and >=1 SFX
 * triggered on fire.
 * @param {import('playwright').Page} page
 */
export async function checkM4(page) {
  // A user gesture (click) is required for AudioContext autoplay policies
  // in Chromium before it will report 'running'.
  try {
    await page.mouse.click(160, 100);
  } catch {
    // Non-fatal -- fall through and let the contextState check fail below
    // with useful diagnostics if the click didn't help.
  }
  await sleep(200);

  const afterClick = await readRaptorState(page);
  const contextState = afterClick && afterClick.audio ? afterClick.audio.contextState : undefined;
  const audioRunning = contextState === 'running';

  const scoreIsNumber = !!afterClick && !!afterClick.hud && typeof afterClick.hud.score === 'number';
  const shieldsIsNumber = !!afterClick && !!afterClick.hud && typeof afterClick.hud.shields === 'number';

  const sfxBefore = afterClick && afterClick.audio ? afterClick.audio.sfxCount : 0;
  await tapKey(page, 'Space', 60);
  await sleep(200);
  const afterFire = await readRaptorState(page);
  const sfxAfter = afterFire && afterFire.audio ? afterFire.audio.sfxCount : sfxBefore;
  const sfxIncreased = typeof sfxAfter === 'number' && typeof sfxBefore === 'number' && sfxAfter > sfxBefore;

  return {
    pass: audioRunning && scoreIsNumber && shieldsIsNumber && sfxIncreased,
    context_state: contextState,
    audio_running: audioRunning,
    hud_score_is_number: scoreIsNumber,
    hud_shields_is_number: shieldsIsNumber,
    sfx_before: sfxBefore,
    sfx_after: sfxAfter,
    sfx_increased: sfxIncreased,
  };
}

// --------------------------------------------------------------------------
// M5: sector-1 autoplay loop
// --------------------------------------------------------------------------

/**
 * M5: sector-1 loop: wave counter advances to 9 and the sector-complete
 * screen appears. Autoplay harness allowed -- this holds fire and jitters
 * movement to dodge, polling state until the win condition or timeout.
 *
 * TODO: this assumes death ends the run (no lives/respawn handling). If a
 * model implements a lives/respawn system, `player.alive` may flip back to
 * true after a death -- a fuller harness would keep polling through that
 * instead of stopping at the first death. Left as-is for the skeleton
 * since it's model-dependent behavior we can't know in advance.
 *
 * @param {import('playwright').Page} page
 * @param {{timeoutMs?: number, pollMs?: number, jitterEveryMs?: number}} [opts]
 */
export async function checkM5(page, opts = {}) {
  const timeoutMs = opts.timeoutMs ?? 300000;
  const pollMs = opts.pollMs ?? 500;
  const jitterEveryMs = opts.jitterEveryMs ?? 1500;

  const deadline = Date.now() + timeoutMs;
  let lastJitter = 0;
  let died = false;
  let finalWave = null;
  let sectorComplete = false;
  const jitterKeys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];

  await page.keyboard.down('Space'); // hold fire continuously
  try {
    while (Date.now() < deadline) {
      const state = await readRaptorState(page);
      if (state) {
        finalWave = typeof state.wave === 'number' ? state.wave : finalWave;
        sectorComplete = !!state.sectorComplete;
        if (state.player && state.player.alive === false) {
          died = true;
        }
        if (typeof state.wave === 'number' && state.wave >= 9 && sectorComplete) {
          break;
        }
        if (died) {
          break;
        }
      }

      const now = Date.now();
      if (now - lastJitter >= jitterEveryMs) {
        lastJitter = now;
        const key = jitterKeys[Math.floor(Math.random() * jitterKeys.length)];
        await tapKey(page, key, 80);
      }

      await sleep(pollMs);
    }
  } finally {
    // Always release the held key, even on error/timeout, so we don't leave
    // Chromium (or a shared page in a longer test run) with a stuck key.
    await page.keyboard.up('Space').catch(() => {});
  }

  const timedOut = !(typeof finalWave === 'number' && finalWave >= 9 && sectorComplete) && !died;
  const pass = typeof finalWave === 'number' && finalWave >= 9 && sectorComplete;

  let reason;
  if (pass) reason = 'sector complete';
  else if (died) reason = 'player died';
  else if (timedOut) reason = 'timeout';

  return {
    pass,
    reason,
    final_wave: finalWave,
    sector_complete: sectorComplete,
    died,
    timed_out: timedOut,
    elapsed_ms: timeoutMs - Math.max(0, deadline - Date.now()),
  };
}

// --------------------------------------------------------------------------
// CLI arg parsing (vanilla Node, no external CLI library)
// --------------------------------------------------------------------------

function printUsage() {
  console.error(
    [
      'Usage: node m2_m5_playwright.mjs <build-dir> [--port 8934] [--timeout-ms 300000] [--headed]',
      '',
      '  <build-dir>     Path to the model build directory (contains index.html). Required.',
      '  --port          Port for the local static server. Default: 8934.',
      '  --timeout-ms    Bound on the M5 autoplay loop, in ms. Default: 300000 (5 min).',
      '  --headed        Run Chromium with a visible window (default: headless).',
      '  --help          Show this message.',
    ].join('\n')
  );
}

function parseArgs(argv) {
  const args = { buildDir: null, port: 8934, timeoutMs: 300000, headless: true };
  const positional = [];

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--help' || a === '-h') {
      printUsage();
      process.exit(0);
    } else if (a === '--port') {
      args.port = parseInt(argv[++i], 10);
    } else if (a.startsWith('--port=')) {
      args.port = parseInt(a.split('=')[1], 10);
    } else if (a === '--timeout-ms') {
      args.timeoutMs = parseInt(argv[++i], 10);
    } else if (a.startsWith('--timeout-ms=')) {
      args.timeoutMs = parseInt(a.split('=')[1], 10);
    } else if (a === '--headed') {
      args.headless = false;
    } else if (a.startsWith('--')) {
      console.error(`Unknown argument: ${a}`);
      printUsage();
      process.exit(1);
    } else {
      positional.push(a);
    }
  }

  args.buildDir = positional[0] || null;
  if (!args.buildDir) {
    printUsage();
    process.exit(1);
  }
  if (!Number.isFinite(args.port) || args.port <= 0) {
    console.error(`Invalid --port: ${args.port}`);
    process.exit(1);
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    console.error(`Invalid --timeout-ms: ${args.timeoutMs}`);
    process.exit(1);
  }
  return args;
}

// --------------------------------------------------------------------------
// Main
// --------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const buildDir = path.resolve(args.buildDir);
  if (!fs.existsSync(path.join(buildDir, 'index.html'))) {
    console.error(`ERROR: ${buildDir} does not contain an index.html`);
    process.exit(1);
  }

  ({ chromium } = await import('playwright'));

  const server = await createStaticServer(buildDir, args.port);
  const boundPort = server.address().port;

  const browser = await chromium.launch({ headless: args.headless });
  const results = { m2: null, m3: null, m4: null, m5: null };

  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${boundPort}/`, { waitUntil: 'load' });

    results.m2 = await checkM2(page);

    // GATING NOTE: M3's `pass` is best-effort (see checkM3 docstring) --
    // strictly gating M4 on it may under-run M4 for models with imprecise
    // hit registration but otherwise-working gameplay. Gating is kept
    // literal here per the milestone-ladder spec; a caller who wants to
    // run M4/M5 regardless of M3's fuzzy verdict can call checkM4/checkM5
    // directly instead of going through main().
    if (results.m2.pass) {
      results.m3 = await checkM3(page);
    } else {
      results.m3 = { pass: false, skipped: true, reason: 'skipped: M2 did not pass' };
    }

    if (results.m3.pass) {
      results.m4 = await checkM4(page);
    } else {
      results.m4 = { pass: false, skipped: true, reason: 'skipped: M3 did not pass' };
    }

    if (results.m4.pass) {
      results.m5 = await checkM5(page, { timeoutMs: args.timeoutMs });
    } else {
      results.m5 = { pass: false, skipped: true, reason: 'skipped: M4 did not pass' };
    }
  } finally {
    await browser.close().catch(() => {});
    await new Promise((resolve) => server.close(resolve));
  }

  console.log(JSON.stringify(results));
}

// Only auto-run when executed directly (`node m2_m5_playwright.mjs ...`),
// not when imported as a module (e.g. for testing individual check
// functions against a hand-built page stub).
const isMain = process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
if (isMain) {
  main().catch((err) => {
    console.error('FATAL:', err && err.stack ? err.stack : err);
    process.exit(1);
  });
}
