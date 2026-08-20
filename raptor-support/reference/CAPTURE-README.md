# Raptor: Call of the Shadows — reference screenshot capture

Ground-truth reference frames of the DOS game running under DOSBox, for use
as reference frames when grading an LLM-generated HTML5-canvas port's
rendering. Capture was **fully automated** end-to-end (no human input
needed): launch, boot, menu navigation, pilot creation, and gameplay entry
were all driven by script, with each step visually verified via screenshot
before proceeding to the next.

## DOSBox build

**dosbox-staging v0.82.2** (Windows x64 portable zip), downloaded from the
official GitHub releases page:
https://github.com/dosbox-staging/dosbox-staging/releases/download/v0.82.2/dosbox-staging-windows-x64-v0.82.2.zip

Extracted to `D:\dev\ab-tasks\_raptor-support\dosbox\`. A `dosbox-staging.conf`
marker file was added alongside `dosbox.exe` to enable dosbox-staging's
"portable layout" mode — this makes it read/write its config, mapper file,
and captures inside that folder instead of `%LOCALAPPDATA%\DOSBox`, keeping
everything inside the sandboxed support directory as required.

## Files created

| Path | Purpose |
|---|---|
| `dosbox\dosbox-staging.conf` | Portable-layout marker (keeps DOSBox's own state inside this folder, not `%LOCALAPPDATA%`). |
| `dosbox\raptor.conf` | Real DOSBox config: mounts the staged shareware game dir as `C:`, autoexecs `RAP.EXE`, sets screenshot capture to native `raw` (320x200) format. |
| `dosbox\run_raptor.bat` | Human-usable launcher: `dosbox.exe -conf raptor.conf`. |
| `dosbox\start_dosbox.ps1` | Script-usable launcher: starts DOSBox as a background process and records its PID to `dosbox.pid` for the automation scripts below. |
| `dosbox\post_keys.ps1` | Sends keystrokes to the DOSBox game window via Win32 `PostMessage` (WM_KEYDOWN/WM_KEYUP) — see "How the automation works" below. |
| `dosbox\screenshot.ps1` | Grabs whatever's currently on screen via `ffmpeg` `gdigrab` (upscaled, for eyeballing state while navigating — not the native-res reference output). |
| `dosbox\list_windows.ps1` | Diagnostic: lists DOSBox's top-level windows (see below — there are two). |
| `dosbox\capture\image000N-raw.png` | Every native 320x200 screenshot taken during the session (title menu, hangar, store, NAVCOM, gameplay, etc.) — a superset of what's in `reference\`. |
| `reference\title-menu.png` | **Deliverable.** Native 320x200. Main menu, a couple seconds after boot (intro movie sequence auto-skipped by the boot script). |
| `reference\sector1-wave1-gameplay.png` | **Deliverable.** Native 320x200. Player ship flying over water/island terrain, ~1 second into sector-1 ("Bravo Sector") wave-1 gameplay — score readout and health bar visible. |
| `reference\MANUAL-CAPTURE-NOTES.md` | Exact key sequence + gotchas, for capturing further/different frames by hand or extending the automation later. Not needed to reproduce the two deliverables above (automation handled that), but documents the recipe. |

## How the automation works

Two problems had to be solved to make this fully scriptable:

1. **DOSBox Staging owns two Windows top-level windows** when its
   stdout/stderr are redirected (as `start_dosbox.ps1` does, to capture
   logs): a `ConsoleWindowClass` **"DOSBox Status Window"** (a debug log
   console) and the actual **`SDL_app`**-class render/input window.
   `.NET`'s `Process.MainWindowHandle` unreliably picked the console
   window rather than the game window, which silently ate all keyboard
   input. `post_keys.ps1`/`screenshot.ps1` fix this by enumerating all
   top-level windows owned by the DOSBox PID and explicitly selecting the
   one with class `SDL_app`.

2. **Windows blocks background processes from stealing OS keyboard
   focus** (and separately, from injecting synthetic input via
   `SendInput`/`SendKeys` reliably) unless a few specific conditions are
   met. `post_keys.ps1` sidesteps both issues entirely by posting
   `WM_KEYDOWN`/`WM_KEYUP` messages **directly to the SDL window's message
   queue** via `PostMessage`, with a correct hardware scancode
   (`MapVirtualKey`) in each message's `lParam` — SDL2's Windows backend
   reads the scancode from there to resolve the SDL key, and processes a
   posted message exactly like a real one regardless of actual OS focus
   state. This turned out to be far more reliable than fighting the
   OS-level foreground-window/focus-stealing restrictions.

Once input worked, DOSBox's own **Ctrl+F5** ("save a screenshot of the
DOS pre-rendered image") hotkey was used for every reference capture.
`raptor.conf` sets `default_image_capture_formats = raw`, which captures
the **untouched 320x200 framebuffer** — no upscaling, no CRT-shader
artifacts, no aspect-ratio correction — exactly the native pixels the
game itself rendered.

## Exact commands used

```powershell
# One-time: download + extract dosbox-staging, add portable marker,
# write raptor.conf / run_raptor.bat (see files above).

# Launch (records PID for the automation scripts):
powershell -File dosbox\start_dosbox.ps1

# Send keys (examples from the actual session):
powershell -File dosbox\post_keys.ps1 -Keys "{ENTER}"                # skip intro -> main menu
powershell -File dosbox\post_keys.ps1 -Keys "LCONTROL+F5"            # capture title-menu.png
powershell -File dosbox\post_keys.ps1 -Keys "Ace|{ENTER}|Raven|{ENTER}"  # register pilot
powershell -File dosbox\post_keys.ps1 -Keys "{ENTER}"                # accept difficulty
powershell -File dosbox\post_keys.ps1 -Keys "{ESC}"                  # back out of store -> hangar
powershell -File dosbox\post_keys.ps1 -Keys "{ENTER}"                # fly mission -> NAVCOM
powershell -File dosbox\post_keys.ps1 -Keys "{ENTER}"                # accept sector (Bravo/1) -> gameplay
powershell -File dosbox\post_keys.ps1 -Keys "LCONTROL+F5"            # capture sector1-wave1-gameplay.png

# Screenshots were then copied from dosbox\capture\imageNNNN-raw.png
# into reference\ under their final names.
```

The exact full key sequence (with the reasoning for each step, and the
one gotcha — a fresh pilot's first hangar visit defaults to the Store, not
"Fly Mission") is written up in `MANUAL-CAPTURE-NOTES.md`.

## Result

Capture was **fully automated** — both required reference screenshots
exist at native 320x200 resolution:
- `reference\title-menu.png`
- `reference\sector1-wave1-gameplay.png`

`MANUAL-CAPTURE-NOTES.md` is provided anyway (not because automation
failed, but as a recipe/reference for capturing additional frames later,
e.g. different sectors, waves, or difficulties) — the `run_raptor.bat`
launcher points to it for that purpose.
