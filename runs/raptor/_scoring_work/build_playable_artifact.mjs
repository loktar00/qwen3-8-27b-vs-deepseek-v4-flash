// Build the ARTIFACT-READY variant of the single-file playable Raptor build.
// Same wrapper concept as build_playable.mjs, but formatted as page CONTENT
// only (no <!DOCTYPE>/<html>/<head>/<body> -- the artifact viewer supplies
// those), starting with <title> per spec.
import fs from 'node:fs';
import path from 'node:path';

const buildDir = 'D:/dev/ab-tasks/_runs/raptor/dsv4/scratch';
const outPath = 'D:/dev/ab-tasks/_runs/raptor/dsv4/artifacts/showcase/raptor-deepseek-playable.artifact.html';

const glb0 = fs.readFileSync(path.join(buildDir, 'data/FILE0000.GLB'));
const glb1 = fs.readFileSync(path.join(buildDir, 'data/FILE0001.GLB'));

function stripModuleSyntax(src) {
  let out = src.replace(/^import\s[\s\S]*?;\s*\n/gm, '');
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
  ' * PACKAGING WRAPPER -- game code unmodified. Artifact-viewer variant:',
  ' * this file is page CONTENT ONLY (no <!DOCTYPE>/<html>/<head>/<body> --',
  ' * the hosting artifact viewer supplies those and wraps this file in them',
  ' * at publish time).',
  ' *',
  ' * This is a single-file, offline-playable repackaging of DeepSeek V4',
  ' * Flash\u2019s HTML5 Raptor port produced during the DSV4-vs-Qwen3.8 A/B run',
  ' * (original multi-file source: raptor-web-ab/deepseek-v4-flash-0731/). It',
  ' * does NOT change any game logic. Two mechanical transforms were applied,',
  ' * both documented here:',
  ' *',
  ' * 1. MODULE MERGE: the 5 original ES modules (js/gfx.js, js/glb.js,',
  ' *    js/audio.js, js/engine.js, js/main.js) are concatenated below in',
  ' *    their original dependency order, each file\u2019s body copied',
  ' *    byte-for-byte EXCEPT for its `import {...} from \u2018...\u2019;` lines',
  ' *    (removed -- everything now shares one scope) and the `export`',
  ' *    keyword on each top-level declaration (stripped -- no module',
  ' *    boundary is needed to share declarations across a single scope). No',
  ' *    function body, class body, or any other line of game logic was',
  ' *    edited. This is the same transformation a JS bundler',
  ' *    (esbuild/rollup, --format=iife) performs.',
  ' *',
  ' * 2. DATA EMBEDDING: the port\u2019s only two runtime-fetched files, the',
  ' *    shareware GLB archives data/FILE0000.GLB (' + glb0.length + ' bytes) and',
  ' *    data/FILE0001.GLB (' + glb1.length + ' bytes) -- confirmed to be the',
  ' *    ONLY fetch() calls anywhere in the port\u2019s source (js/glb.js\u2019s',
  ' *    loadGLB()) -- are embedded below as base64 and served through a',
  ' *    fetch() shim installed BEFORE the game code runs. The shim',
  ' *    intercepts exactly the two literal URL strings the game requests',
  ' *    (\u2018data/FILE0000.GLB\u2019, \u2018data/FILE0001.GLB\u2019) and returns a Response',
  ' *    built from the embedded bytes; it makes NO network request of its',
  ' *    own for any URL -- anything that isn\u2019t one of those two exact',
  ' *    strings falls through to the page\u2019s real fetch() unchanged (the',
  ' *    game never requests anything else, so in practice this file makes',
  ' *    zero network requests at runtime).',
  ' *',
  ' * Everything else (canvas element, window.__raptor grader contract, Web',
  ' * Audio, keyboard handling) is the port\u2019s own unmodified code. The',
  ' * caption/note text, canvas centering/3x scale, dark chrome background,',
  ' * click-to-focus, and arrow-key page-scroll prevention below are',
  ' * artifact page chrome only -- not game logic.',
  ' */',
].join('\n');

const html = `<title>DeepSeek Raptor Port</title>
<style>
  :root {
    color-scheme: dark;
  }
  html, body {
    margin: 0;
    padding: 0;
    background: #0a0a0a;
    color: #cfc;
    overflow: hidden;
    height: 100%;
  }
  body {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
  }
  #caption {
    font-size: 13px;
    color: #9fd89f;
    margin-bottom: 10px;
    text-align: center;
    max-width: min(92vw, 960px);
    line-height: 1.4;
  }
  #raptor-canvas {
    width: 960px;
    height: 600px;
    max-width: 92vw;
    max-height: 70vh;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    border: 2px solid #2a5a2a;
    background: #000;
    cursor: pointer;
    display: block;
  }
  #raptor-canvas:focus {
    outline: 2px solid #4caf4c;
    outline-offset: 2px;
  }
  #wrapper-note {
    margin-top: 10px;
    font-size: 11px;
    color: #6a8a6a;
    text-align: center;
  }
  #status:empty {
    display: none;
  }
  #status {
    margin-top: 8px;
    font-size: 12px;
    color: #e0a060;
  }
</style>
<div id="caption">DeepSeek V4 Flash \u2014 Raptor: Call of the Shadows, shareware sector 1, web port produced during the A/B run. Click the game to focus; arrows move, Space fires.</div>
<canvas id="raptor-canvas" width="320" height="200" tabindex="0"></canvas>
<div id="status"></div>
<div id="wrapper-note">Packaging wrapper only \u2014 game code unmodified.</div>
<script type="module">
${wrapperHeader}

// Click-to-focus affordance (page chrome only, not game logic).
const __canvasEl = document.getElementById('raptor-canvas');
__canvasEl.addEventListener('click', (e) => {
  e.currentTarget.focus();
});

// Belt-and-suspenders: the game's own keydown handler already calls
// preventDefault() on Arrow*/Space (see js/main.js below), which stops
// page scroll. This listener is chrome-level insurance only, added before
// the game's own listener runs, and never overrides game behavior -- it
// only prevents default scroll on the same keys the game already handles.
window.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === ' ') {
    e.preventDefault();
  }
}, { passive: false });

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
// fetch() shim: answers ONLY the 2 embedded GLB URLs; makes no network
// request of its own. Installed before the game code below runs.
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
`;

fs.writeFileSync(outPath, html, 'utf8');
const stat = fs.statSync(outPath);
console.log(JSON.stringify({ outPath, sizeBytes: stat.size, sizeMB: (stat.size / (1024 * 1024)).toFixed(2) }));
