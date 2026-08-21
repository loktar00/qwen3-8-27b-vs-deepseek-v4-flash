// Build a single-file playable HTML from DeepSeek's Raptor port snapshot.
// PACKAGING ONLY -- see the header comment written into the output file for
// the full explanation. This script does not alter any game logic: it only
// (1) strips ES module import/export syntax so the 5 source files can share
// one script scope (a standard bundling transform -- no function/class body
// is touched), and (2) embeds the 2 runtime-fetched GLB archives as base64
// behind a fetch() shim so no network/file access is needed at runtime.
import fs from 'node:fs';
import path from 'node:path';

const buildDir = 'D:/dev/ab-tasks/_runs/raptor/dsv4/scratch';
const outPath = 'D:/dev/ab-tasks/_runs/raptor/dsv4/artifacts/showcase/raptor-deepseek-playable.html';

const glb0 = fs.readFileSync(path.join(buildDir, 'data/FILE0000.GLB'));
const glb1 = fs.readFileSync(path.join(buildDir, 'data/FILE0001.GLB'));
console.error('FILE0000.GLB', glb0.length, 'bytes; FILE0001.GLB', glb1.length, 'bytes; total', glb0.length + glb1.length);

function stripModuleSyntax(src) {
  // Remove `import ... ;` statements (may span multiple lines).
  let out = src.replace(/^import\s[\s\S]*?;\s*\n/gm, '');
  // Remove the `export ` keyword from declarations (export class/function/const/async function).
  out = out.replace(/^export\s+/gm, '');
  return out;
}

const files = ['gfx.js', 'glb.js', 'audio.js', 'engine.js', 'main.js'];
const merged = files
  .map((f) => {
    const src = fs.readFileSync(path.join(buildDir, 'js', f), 'utf8');
    return '// ---- begin js/' + f + ' (verbatim game code; only import/export syntax stripped for single-scope merge) ----\n' +
      stripModuleSyntax(src) +
      '\n// ---- end js/' + f + ' ----\n';
  })
  .join('\n');

const b64_0 = glb0.toString('base64');
const b64_1 = glb1.toString('base64');

const wrapperHeader = [
  '/*',
  ' * PACKAGING WRAPPER -- game code unmodified.',
  ' *',
  ' * This file is a single-file, offline-playable repackaging of DeepSeek V4',
  ' * Flash\u2019s HTML5 Raptor port (see D:\\dev\\raptor-web-ab\\deepseek-v4-flash-0731\\',
  ' * for the original multi-file source tree this was built from). It does NOT',
  ' * change any game logic. Two mechanical transforms were applied, both',
  ' * documented here:',
  ' *',
  ' * 1. MODULE MERGE: the 5 original ES modules (js/gfx.js, js/glb.js,',
  ' *    js/audio.js, js/engine.js, js/main.js) are concatenated below in their',
  ' *    original dependency order, each file\u2019s body copied byte-for-byte',
  ' *    EXCEPT for its `import {...} from \u2018...\u2019;` lines (removed -- everything',
  ' *    now shares one scope) and the `export` keyword on each top-level',
  ' *    declaration (stripped -- no module boundary is needed to share',
  ' *    declarations across a single scope). No function body, class body, or',
  ' *    any other line of game logic was edited. This is the same',
  ' *    transformation a JS bundler (esbuild/rollup, --format=iife) performs.',
  ' *',
  ' * 2. DATA EMBEDDING: the port\u2019s only two runtime-fetched files, the',
  ' *    shareware GLB archives data/FILE0000.GLB (' + glb0.length + ' bytes) and',
  ' *    data/FILE0001.GLB (' + glb1.length + ' bytes) -- confirmed to be the ONLY',
  ' *    fetch() calls anywhere in the port\u2019s source (js/glb.js\u2019s loadGLB()) --',
  ' *    are embedded below as base64 and served through a fetch() shim',
  ' *    installed BEFORE the game code runs. The shim intercepts exactly the',
  ' *    two literal URL strings the game requests (\u2018data/FILE0000.GLB\u2019,',
  ' *    \u2018data/FILE0001.GLB\u2019) and returns a Response built from the embedded',
  ' *    bytes; every other URL falls through to the real fetch() unchanged.',
  ' *    This makes the file playable via a plain file:// double-click, with',
  ' *    no local server and no separate data files, while leaving the GLB',
  ' *    decoding logic (js/glb.js\u2019s decrypt()/GLBFile, unmodified) to do',
  ' *    exactly what it always did against those bytes.',
  ' *',
  ' * Everything else (canvas element, window.__raptor grader contract, Web',
  ' * Audio, keyboard handling) is the port\u2019s own unmodified code. A one-line',
  ' * caption and click-to-focus affordance were added to the page chrome',
  ' * (outside the game canvas/logic) for this packaged build only.',
  ' */',
].join('\n');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Raptor: Call of the Shadows \u2014 Sector 1 (HTML5 Port, packaged single-file build)</title>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      background: #000;
      color: #cfc;
      font-family: monospace;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      overflow: hidden;
    }
    #caption {
      font-size: 12px;
      color: #8a8;
      margin-bottom: 8px;
      text-align: center;
      max-width: 90vw;
    }
    canvas {
      width: min(96vw, 640px);
      image-rendering: pixelated;
      image-rendering: crisp-edges;
      border: 2px solid #262;
      background: #000;
      cursor: pointer;
    }
    canvas:focus { outline: 2px solid #4a4; }
    #status {
      margin-top: 10px;
      font-size: 14px;
    }
    #controls {
      margin-top: 8px;
      font-size: 12px;
      color: #8a8;
    }
  </style>
</head>
<body>
  <div id="caption">DeepSeek V4 Flash's Raptor port \u2014 packaging wrapper only, game code unmodified</div>
  <canvas id="raptor-canvas" width="320" height="200" tabindex="0"></canvas>
  <div id="status">Loading game data...</div>
  <div id="controls">Arrow keys: move &nbsp; Space: fire &nbsp; (click the game to focus it)</div>
  <script type="module">
${wrapperHeader}

// Click-to-focus affordance (page chrome only, not game logic).
document.getElementById('raptor-canvas').addEventListener('click', (e) => {
  e.currentTarget.focus();
});

// ---------------------------------------------------------------------
// Embedded runtime data (base64) -- the port's only two fetched files.
// ---------------------------------------------------------------------
const __EMBEDDED_GLB0_B64 = "${b64_0}";
const __EMBEDDED_GLB1_B64 = "${b64_1}";

function __b64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// ---------------------------------------------------------------------
// fetch() shim: intercept the 2 GLB URLs, pass everything else through.
// Installed before the game code below runs.
// ---------------------------------------------------------------------
const __realFetch = window.fetch.bind(window);
window.fetch = async function (input, init) {
  const url = typeof input === 'string' ? input : (input && input.url) || '';
  if (url === 'data/FILE0000.GLB' || url.endsWith('data/FILE0000.GLB')) {
    return new Response(__b64ToArrayBuffer(__EMBEDDED_GLB0_B64), { status: 200, headers: { 'Content-Type': 'model/gltf-binary' } });
  }
  if (url === 'data/FILE0001.GLB' || url.endsWith('data/FILE0001.GLB')) {
    return new Response(__b64ToArrayBuffer(__EMBEDDED_GLB1_B64), { status: 200, headers: { 'Content-Type': 'model/gltf-binary' } });
  }
  return __realFetch(input, init);
};

// =======================================================================
// Game code below is DeepSeek V4 Flash's port, verbatim (see header above
// for the exact, mechanical module-merge transform applied).
// =======================================================================
${merged}
  </script>
</body>
</html>
`;

fs.writeFileSync(outPath, html, 'utf8');
const stat = fs.statSync(outPath);
console.log(JSON.stringify({ outPath, sizeBytes: stat.size, sizeMB: (stat.size / (1024 * 1024)).toFixed(2) }));
