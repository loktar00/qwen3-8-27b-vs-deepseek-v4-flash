# Raptor Support Material

Reference material for the `raptor` task — porting *Raptor: Call of the Shadows* (Apogee,
1994, shareware sector 1) to a vanilla HTML5/Canvas/Web Audio browser game. See
[../tasks/raptor/brief.md](../tasks/raptor/brief.md) for the full task brief.

- `reference/` — reference screenshots (title/menu screen, sector 1 gameplay) used as visual
  ground truth when scoring the port.
- `checks/` — automated verification scripts: `m1_ssim.py` (structural similarity scoring
  against reference screenshots) and `m2_m5_playwright.mjs` (Playwright-driven milestone
  checks against the running port).
- `GLB-FORMAT.md` — a reverse-engineered spec of the original `.GLB` game-data archive
  format, used as an answer key for asset-extraction correctness (not shown to the models).
- `brief-draft.md` — an earlier draft of the task brief, kept for reference.

Not included here: the shareware game data itself (`FILE0000.GLB`, `FILE0001.GLB`,
`RAP.EXE`, etc.) and the DOSBox reference emulator used to capture the screenshots above —
both are excluded from this public repo (no game data or binaries redistributed here beyond
what the original 1994 shareware release already permits free redistribution of, and even
that isn't included to keep this repo small and dependency-free).

## Provenance of the shareware source data used during task construction

The original shareware package (`1rap12.zip`, v1.2, 2,013,010 bytes) was obtained from a
Wayback Machine capture of 3D Realms' own official FTP server:

- **Download URL:** `http://web.archive.org/web/20201123054950if_/ftp://ftp.3drealms.com/share/1rap12.zip`
- **SHA256:** `7d6b062dcdc76d9ea02d8d71af14e5043223581d792f6ead4eb1316fd0351552`

Raptor's shareware episode was explicitly licensed by Apogee/Cygnus Studios for free,
unrestricted redistribution (per the package's own `VENDOR.DOC`); only the registered
(paid) episodes 2–3 were restricted, and no registered-episode data was used anywhere in
this task. Version was confirmed as the genuine patched v1.2 build by matching the
`RAPTOR: Call Of The Shadows V1.2` banner string against the GPL'd source in `RAP.C`.
