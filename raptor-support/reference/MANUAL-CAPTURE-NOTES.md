# Manual capture notes — Raptor: Call of the Shadows (shareware v1.2)

Automated capture worked end-to-end for this task (see `CAPTURE-README.md`),
so these notes are provided as a fallback / recipe for capturing *additional*
reference frames by hand (different sectors, waves, difficulty, etc.),
using the same DOSBox build and config already set up in
`D:\dev\ab-tasks\_raptor-support\dosbox\`.

## Launch

Run `D:\dev\ab-tasks\_raptor-support\dosbox\run_raptor.bat`. This boots
straight into `RAP.EXE` (no DOS prompt needed) because the autoexec in
`raptor.conf` mounts the game directory as `C:` and runs it directly.

Prerequisite: `SETUP.INI` must exist in
`..\shareware\extracted\game\` (it already does — SETUP.EXE was run once
during automated capture with all-default answers, which exactly match
DOSBox's emulated Sound Blaster: port 220, IRQ 7, DMA 1, 4 digital
channels). If that file is ever deleted, run `SETUP.EXE` first and accept
every default (press Enter through all 8 prompts, "Save Settings" is
pre-highlighted on the final screen).

## Screenshot hotkey

**Ctrl+F5** saves a screenshot. `raptor.conf` sets
`default_image_capture_formats = raw`, so this produces an exact
**320x200** PNG (no upscaling/aspect correction) in
`D:\dev\ab-tasks\_raptor-support\dosbox\capture\imageNNNN-raw.png`.

## Exact key sequence: boot → title menu → sector-1 wave-1 gameplay

All of this is keyboard-only (no mouse needed, verified working):

1. **Boot.** The Apogee "Height of Gaming Excitement" logo appears after
   ~1-2 seconds.
2. Press **Enter** once. This skips the entire intro movie sequence
   (`INTRO_PlayMain` / `MOVIE_Play` treats any keypress as "skip all") and
   lands on the **Main Menu** (RAPTOR: CALL OF THE SHADOWS, with NEW
   MISSION / LOAD MISSION / GAME OPTIONS / ORDER INFO / CREDITS / QUIT).
   → **This is the `title-menu.png` shot.** Press Ctrl+F5 here.
3. Press **Enter** (NEW MISSION is the default-focused field) →
   pilot registration screen ("Change ID Picture", NAME field active).
4. Type a **name** (e.g. `Ace`), press **Enter** → focus moves to CALLSIGN.
5. Type a **callsign** (e.g. `Raven`), press **Enter**.
   - If that exact name+callsign combo was already used by a saved pilot,
     you'll see "Pilot NAME and CALLSIGN Used!" — press Enter to dismiss
     and pick a different name/callsign.
6. **Choose Difficulty** screen appears (Training Mode / Rookie / Veteran /
   Elite / Abort Mission). Press **Enter** to accept the default
   (top-most/auto) selection.
7. You land in the **Hangar** ("Supply Room" background). The default
   focus here is the **Supplies/Store** hotspot, which immediately opens
   **"Harrold's Death Emporium"** (the shop). Press **Esc** to back out —
   this returns to the Hangar with **"FLY MISSION"** now shown highlighted
   at the bottom of the screen.
8. Press **Enter** → **NAVCOM** sector-select screen (BRAVO SECTOR / TANGO
   SECTOR / OUTER REGIONS / AUTO-PILOT).
9. Press **Enter** to accept the default (**Bravo Sector** = sector 1).
   Gameplay begins immediately: the player ship appears flying over
   water/island terrain, score readout at top-left, health bar at the
   right edge.
   → **This is the `sector1-wave1-gameplay.png` shot.** Press Ctrl+F5
   within the first second or two — enemy waves show up quickly and the
   ship can be shot down (a first attempt died within ~2 seconds; the
   working shot was captured ~0.8s after the mission started).

Notes / gotchas found during automated capture:
- The Hangar's default focus depends on internal state (`hangto`): a fresh
  pilot's very first hangar visit defaults to the **Store**, not
  "Fly Mission" — hence the Esc-to-back-out step above.
- `TAB` cycles keyboard focus through the 6 main-menu fields
  (New→Load→Options→Order→Credits→Quit→wraps to New) and, once in the
  Hangar, through its 4 hotspots — but the Hangar's own key handling
  reads raw keypresses directly (not the generic dialog focus system), so
  `TAB`/`UP`/`LEFT` step forward and `DOWN`/`RIGHT` step backward through
  its 4 options in a fixed cycle (Mission → Supplies → Exit Hangar →
  Quick-Save → wraps to Mission).
- The NAVCOM sector-select and Choose-Difficulty screens did **not** show
  a visible keyboard-focus highlight in testing, but pressing Enter with
  no prior navigation reliably worked (their default field is set
  explicitly in the game's source, `SWD_SetActiveField`, even though nothing
  visibly indicates it before you press a key).

## If you need to automate this yourself

The scripts used for the actual automated capture are in
`D:\dev\ab-tasks\_raptor-support\dosbox\`:
- `post_keys.ps1 -Keys "token|token|..."` — sends key presses to the
  DOSBox game window via `PostMessage` (WM_KEYDOWN/WM_KEYUP), which works
  reliably even when DOSBox isn't the real OS foreground window. Tokens are
  literal text (typed character-by-character with correct Shift state),
  `{ENTER}` `{ESC}` `{TAB}` `{UP}` `{DOWN}` `{LEFT}` `{RIGHT}` `{F1}`..`{F12}`
  `{SPACE}` `{BACKSPACE}`, or a `+`-joined combo like `LCONTROL+F5`.
- `screenshot.ps1 -OutFile <path>` — grabs whatever's currently on screen
  via `ffmpeg`'s `gdigrab` (upscaled/CRT-shaded, useful for eyeballing
  state while navigating menus; **not** the native-resolution capture —
  use Ctrl+F5 via `post_keys.ps1` for that).
- `list_windows.ps1` — diagnostic: lists all top-level windows owned by
  the DOSBox process (useful because DOSBox Staging owns *two* windows
  when stdout/stderr are redirected — a `ConsoleWindowClass` "DOSBox
  Status Window" log console, and the actual `SDL_app`-class render/input
  window; `post_keys.ps1`/`screenshot.ps1` both find the right one
  automatically by enumerating for class `SDL_app`).

Both scripts expect `dosbox.pid` (the DOSBox process ID) at
`D:\dev\ab-tasks\_raptor-support\dosbox\dosbox.pid` — write it there
yourself (e.g. `(Start-Process dosbox.exe -ArgumentList '-conf','raptor.conf' -PassThru).Id`)
if launching DOSBox some other way than through their sibling
`start_dosbox.ps1` pattern.
