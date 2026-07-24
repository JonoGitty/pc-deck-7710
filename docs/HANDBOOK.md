# PC·DECK handbook

Build your own 1-DIN head unit. Pick a display, see it before you buy it, flash
your setup, make your own animations.

> **Status.** The renderer and the preview are done and verified. The firmware
> is a skeleton that has not been run on hardware. Sections below are marked
> accordingly — nothing here claims to be tested that isn't.

## 1. Decide what you're building — ✅ ready

Three routes, and the cheapest one needs no soldering at all.

| | What | Cost | Needs |
|---|---|---|---|
| **Desk deck** | The legacy PC visualiser on a bar LCD as a second monitor | ~£70 | A PC. No firmware at all |
| **Bench deck** | ESP32-S3 + SSD1322 on a desk | ~£30 | Soldering iron, USB |
| **Car deck** | The above, in a 1-DIN cage, on ignition power | ~£80 | The bench deck first |

Start at the preview either way: `sh tools/serve.sh` renders every screen on
every candidate panel, so you can choose glass by looking at it.
See [HARDWARE.md](HARDWARE.md) for parts and [UI-SPEC.md](UI-SPEC.md) for how
layouts adapt.

## 2. Run the preview — ✅ ready

```sh
sh tools/serve.sh        # builds the wasm, serves on :7720
```

Pick a display, a level count, a screen. What you see is what the panel shows:
the page runs the same C the firmware compiles. See [preview/](../preview/).

## 3. Run the PC deck — ✅ ready

The original visualiser, unchanged. `legacy/` — see the [main README](../README.md).

## 4. Build the hardware — ⚠️ skeleton

Wiring, cage, connector and power: [HARDWARE.md](HARDWARE.md). The ISO 10487
pinout and the ISO 7736 cage are there, including which pins do the ignition
sense and the dimmer.

## 5. Flash it — ⚠️ not yet

[firmware/esp32/](../firmware/esp32/) has the structure and the bring-up order.
Update mechanism is undecided — [VERSIONING.md](VERSIONING.md).

## 6. Control it — ⚠️ partly

Actions, physical surface, and why the settings menu should live on your phone
rather than on the panel: [CONTROL.md](CONTROL.md).

## 7. Make a movie — ✅ ready

```sh
python3 tools/ledcine/movie_spin.py 256 64     # renders for your panel
```

Two kinds: procedural (code, reacts to audio — the dolphins) and baked
(pre-rendered frames — 3D scenes, loops, GIFs). The 3D renderer is pure Python,
no GPU, no Blender. See [MOVIES.md](MOVIES.md).

## 8. Contribute a display — ⚠️ needs the firmware first

Adding a panel is meant to be config plus a driver, not a rewrite. The
abstraction is in [ARCHITECTURE.md](ARCHITECTURE.md); the driver contract is
`deck_display.h`.

---

## How this project verifies things

Worth knowing before changing anything: `core/` was ported from working
JavaScript, and every part of it is checked by rendering the same input through
both and diffing the framebuffers.

```sh
sh tools/verify/run.sh
```

Font, screens, text handling, metadata screens, the ocean, and the movie
container round-trip. **A screen is not ported until it matches.** If you change
a screen deliberately, the diff will fail — update the case, don't delete it.

This has caught real bugs that were invisible by eye: a one-frame-early dolphin
breach, waterfall thresholds landing differently at double precision, and text
dithering into mush on 1-bit panels. Trust the diff over your eyes.
