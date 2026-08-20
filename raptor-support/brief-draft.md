# Task Brief: Port Raptor: Call of the Shadows (Sector 1) to HTML5

## 1. Goal

Port *Raptor: Call of the Shadows* (Apogee, 1994) — sector 1 only, the shareware
content — from the original DOS game to a browser game built with HTML5 canvas,
vanilla JavaScript, and the Web Audio API. The port must render real game assets
(graphics and sounds) extracted from the original shareware data files, either at
build time or at runtime — no placeholder art, no placeholder audio. Do not use
any external frameworks or libraries beyond what ships in the browser (no React,
Phaser, PixiJS, Howler, etc.). A small vanilla test runner is fine if you want
one, but it is not required.

## 2. Worktree Layout

Your worktree root (`./`) contains the GPL C/ASM source of the original DOS game,
provided for reference and porting purposes, under `SOURCE/`, `GFX/`, `audiolib/`,
and `apodmx/`. It also contains the original shareware game data files under
`./data/` — GLB archive files, the shareware `RAP.EXE` for reference, and whatever
else the shareware distribution contained.

Build your web port as new files alongside/above this existing tree (for example
`index.html`, an asset-extraction or build script, and your JS source), and keep
the original source tree intact for reference — do not delete or rewrite it.

You must write and maintain a `README` documenting a working dev-server command
(for example `npx serve .`, `python -m http.server`, or similar) so that the port
can be opened and played in a browser at any milestone. Keep this command accurate
and working as you go — it will be used to check your progress at each milestone.

## 3. Standing Rules

- Vanilla JavaScript + HTML5 canvas + Web Audio API only. No external runtime
  frameworks or libraries. A lightweight bundler or dev-only tool is fine if it
  produces plain output, but avoid dependency-heavy tooling.
- Always leave behind a documented, working dev server command that serves a
  working build.
- Commit to git after completing each milestone (M1 through M5, below), so
  progress is checkpointed.
- Sector 1 (shareware) content only — you do not need to support later sectors
  or the registered/full game.

## 4. Milestone Ladder (M1–M5)

This is the actual grading spec. Copied verbatim:

- **M1**: level-1 background + player ship rendered on canvas from the real GLB
  data. Graded by screenshot similarity (SSIM) to a reference DOSBox frame on the
  playfield region (target >= 0.80), and >= 90% of the reference color palette
  present.
- **M2**: arrow keys move the ship; firing spawns a projectile.
- **M3**: wave-1 enemies spawn; a projectile hit decrements enemy HP or removes
  the enemy; the player can die.
- **M4**: HUD (score/shields) renders; a Web Audio context is running and at
  least one sound effect is triggered on firing.
- **M5**: the sector-1 loop completes — the wave counter advances through wave 9
  and a sector-complete screen appears.

## 5. Grader Interface Contract

You **must** implement exactly this. An automated Playwright script checks
against it — this is a hard requirement, not a suggestion.

- A canvas element `<canvas id="raptor-canvas">` whose internal pixel buffer is
  exactly 320x200 (`canvas.width === 320`, `canvas.height === 200`), independent
  of any CSS display scaling.
- Controls: `ArrowUp` / `ArrowDown` / `ArrowLeft` / `ArrowRight` move the ship;
  the Space bar fires. Use standard `keydown`/`keyup` DOM listeners — no custom
  input hook needed.
- A live-updated global object `window.__raptor` with this exact shape:

  ```js
  window.__raptor = {
    ready: boolean,            // true once the first frame (background + player ship) is drawn from real game data
    player: { x: number, y: number, alive: boolean },
    projectiles: [ { x: number, y: number, owner: 'player'|'enemy' }, /* ... */ ],
    enemies: [ { id: string|number, hp: number, x: number, y: number, alive: boolean }, /* ... */ ],
    hud: { score: number, shields: number },
    audio: { contextState: 'running'|'suspended'|'closed', sfxCount: number },  // sfxCount increments on every SFX triggered
    wave: number,               // current wave within sector 1
    sectorComplete: boolean
  };
  ```

- Keep this object's fields in sync with actual game state at all times. The
  grader polls it, drives real keyboard input to test M2/M3/M4/M5, and takes a
  canvas screenshot to test M1. For M5 the grader is allowed to auto-play (hold
  fire, jitter movement) rather than requiring skilled play, so you do not need
  to build any special "autoplay" or "god mode" feature — just make the interface
  accurately reflect real game state during ordinary play.
