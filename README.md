# PC·DECK 7710

A Pioneer-style OEM head-unit display for your PC. Whatever the machine plays —
Spotify, YouTube, games — shows up live on an amber VFD faceplate: 13-band
spectrum analyzer, VU needles, oscilloscope, waterfall, and the classic
dolphin ocean screensaver when the music stops.

Co-designed with GPT 5.6 (Sol) — visual spec, ballistics, and the album-art
dither idea came out of that consult.

## Run

Type **`music visualiser`** in a PowerShell terminal (set up as a profile
command), or double-click `start.cmd`. Either opens http://127.0.0.1:7710 and
starts the server if it isn't already running. Play music anywhere; the deck
lights up on its own.

- Audio: WASAPI loopback of the default output device (survives device switches).
- Track/artist/album art: Windows SMTC — works with Spotify, browsers, most players.
- Nothing is recorded or sent anywhere; it all stays on 127.0.0.1.

Always-on: put a shortcut to `start.cmd` in `shell:startup`, drag the browser
tab to the TV, press `T` for TV mode.

## Controls

| Control | Action |
|---|---|
| DISP / knob click / `D` | cycle display mode |
| Presets 1–6 / keys `1–8` | jump straight to a mode |
| BAND / `B` | force the ocean cruise (dolphins) |
| EQ | LOUD on/off (loudness lamp + fatter bass bars) |
| AUDIO | second line: artist ↔ clock |
| COLOR / `C` | cycle colour scheme (8 illumination colours) |
| DEMO / `M` | attract loop: auto-cycles every display until you touch it |
| TV / `T` | **TV mode** — fullscreen the display only (visuals, no chrome) |
| `F` / double-click display | fullscreen the whole faceplate |
| SRC | flash the current source |
| scroll on knob | display dimmer |

## Colour schemes (COLOR / `C`)

Authentic head-unit illumination colours, cycled with the COLOR button:
**Amber** (default), **Pioneer Red**, **Emerald**, **Ice Blue**, **Purple**,
**White**, plus two round-LED-bulb variants — **LED Amber** and **LED COOKD**
(lime/cyan), whose bulb look adapts the COOKD LED-board renderer
(`C:\AI\Cooked\src\core\led.js`, itself from the Blender LED signs) to the
deck's OEM dot pitch.

## TV mode (TV / `T`)

Fills a TV with just the visuals — no bezel, buttons, knob or hint text. Built
for the **Panasonic TX-32LXD70** (1366×768): the head-unit display strip
width-fills the screen, centred on black. The separate `F` / double-click
fullscreen keeps the whole faceplate instead.

## Display modes (keys 1–8)

1. **Spectrum Analyzer** — 13-band segmented bars, 63 Hz–16 kHz, peak-hold dots
2. **Mirror Spectrum** — L/R split growing out from centre
3. **VU Meter** — twin needles with overshoot and recoil
4. **Oscilloscope** — dot-matrix scope with phosphor persistence
5. **Cityscape EQ** — coarse tower blocks with rising scan sweeps
6. **Waterfall** — chunky 32×12 spectral memory climbing upward
7. **3D Spectrum** — perspective-receding analyzer landscape with hidden-line removal
8. **Ocean Cruise** — the dolphin movie as a full-time display

The dolphins are rasterized from a smooth bezier silhouette per frame (rotation
quantized to 10°, stepped 10 fps playback), so they arc through breaches like the
period animations rather than looping rigid sprites. Bass transients make the pod
breach; high-frequency energy drives the bubbles.

Idle behaviour, faithful to the era: music stops → 3 s → clock; 12 s → the
dolphins take over; music returns → hard horizontal wipe back to the analyzer.
On every track change the album art is ordered-dithered into a 3-tone amber
bitmap and shown as a "NOW PLAYING" interstitial for two seconds.

## Files

- `server.py` — WASAPI loopback capture, 13-band FFT, SMTC metadata, WebSocket
- `web/` — the faceplate: `app.js` (renderer/state), `viz.js` (modes),
  `dolphin.js` (ocean movie), `font.js` (5×7 + 3×5 dot fonts)
- `launch.ps1` — opens the deck, starting the server if needed (used by the
  `music visualiser` command in the PowerShell profile)
- `start.cmd` — double-click launcher

Tunables at the top of `server.py`: `DB_FLOOR` (sensitivity), `DB_TILT`
(treble lift), `BROADCAST_FPS`.

## `music visualiser` command

The PowerShell profile (`Documents\PowerShell\Microsoft.PowerShell_profile.ps1`)
defines a `music` function, so typing `music visualiser` (or just `music`) in a
new PowerShell window launches the deck via `launch.ps1`.
