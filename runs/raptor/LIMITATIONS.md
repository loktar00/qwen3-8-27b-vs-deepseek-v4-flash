# Raptor ladder — known limitations

- **M1 is frame-timing sensitive.** The DOSBox reference frame was captured at a fixed, non-deterministic-to-reproduce
  point in wave-1 gameplay (a specific terrain-scroll offset and enemy layout). A model's screenshot is taken at
  whatever moment `window.__raptor.ready` first flips true, which will generally land at a different scroll/spawn
  position even from a faithfully-ported, deterministic RNG. A low SSIM can therefore reflect frame misalignment
  rather than a real rendering-fidelity gap; this applies identically to both models and is not corrected for.
- **M5's autoplay was amended after calibration.** The original naive policy (hold fire, jitter one random arrow key
  every ~1.5s) was pre-committed to be replaced with a state-aware `window.__raptor`-only dodge if the original
  shareware game, driven by that same naive policy in DOSBox, could not itself survive — which calibration confirmed
  (destroyed in <30s in 3/3 runs), so the amendment was applied identically to both models before either was scored.
- **Commit hygiene is not scored.** Milestone turns request a commit after each step, but the checks run against the
  model's actual working-tree state at session end, uncommitted changes included; a model that under-commits is not
  penalized on the primary ladder score for that alone.
- **n=1 per model.** Unlike the bug-fix task classes (n=2), Raptor runs once per model per effort setting, for cost
  reasons; a single run's result is not averaged against any other attempt of the same milestone turns.
