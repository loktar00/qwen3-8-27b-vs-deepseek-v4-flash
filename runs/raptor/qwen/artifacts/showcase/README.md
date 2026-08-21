# Qwen3.8-27B Raptor port -- showcase (minimal)

This run only completed the M1 milestone before the pod's hard stop cut it off (see
`../../score.json`'s `run_context` and M1 notes for the full story). There is no full
75s autoplay video / playable single-file build here, unlike the DeepSeek showcase --
two reasons:

1. **The canvas renders almost nothing.** `js/game.js` has a real bug: the reusable
   `ImageData` buffer's alpha channel is only initialized for its first 256 of 64,000
   pixels (`for (let i = 0; i < 256; i++) { px[i*4+3] = 255; }`, should be `i < W*H`),
   so >99% of the canvas stays fully transparent every frame. The underlying per-pixel
   color computation runs correctly (confirmed via direct `getImageData()` sampling),
   it just never becomes visible.
2. **There is no gameplay to show.** Only M1 (background + ship render) was built --
   arrow-key movement, firing, enemies, HUD, and audio (M2-M5) were never attempted
   (their turns never started; see score.json). A 75-second autoplay recording would
   just be 75 seconds of a static, near-blank frame.

Two screenshots instead:
- `what-a-viewer-sees.png` -- a full-page screenshot, i.e. what a human opening this
  build in a browser actually sees (effectively a blank black page).
- `m1-state-raw-canvas.png` -- the raw canvas pixel buffer via `canvas.toDataURL()`
  (the same capture method used for M1 scoring), showing the tiny opaque sliver in
  the top-left corner where the alpha bug's `i < 256` loop bound happens to land.

If a fuller showcase (video/playable-HTML) is wanted once a corrected/later run
exists, it can be built the same way as DeepSeek's.
