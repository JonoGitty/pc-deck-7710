# DECK·7710 handbook

Build your own 1-DIN head unit. Pick a display, see it before you buy it, flash
your setup, make your own animations.

> **Status.** The renderer and the preview are done and verified. The firmware
> is written and compiles for both panels, and has never run on hardware.
> Sections below are marked accordingly — nothing here claims to be tested
> that isn't. Read [SAFETY.md](../SAFETY.md) before any of it meets a car.

## 1. Decide what you're building — ✅ ready

Three routes, and the cheapest one needs no soldering at all.

| | What | Cost | Needs |
|---|---|---|---|
| **Desk deck** | The legacy PC visualiser on a bar LCD as a second monitor | ~£70 | A PC. No firmware at all |
| **Bench deck** | ESP32 WROVER-E + SSD1322 on a desk | ~£30 | Soldering iron, USB |
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

## 4. Build the hardware — ⚠️ untested

**[BUILD.md](BUILD.md) is the end-to-end guide**: shopping list with part
numbers, pin-by-pin wiring, flashing, pairing, then the car install. Component
survey and alternatives in [HARDWARE.md](HARDWARE.md); the ISO 10487 pinout and
the ISO 7736 cage are there, including which pins do the ignition sense and the
dimmer.

## 5. Flash it — ⚠️ compiles, never run

```sh
python3 tools/deckctl.py          # guided: check, build, flash, load movies
```

The firmware builds for both panels and CI keeps it building. Nothing has
driven a pin. Bring-up order is in [firmware/esp32/](../firmware/esp32/), and
when it does not work, [DIAGNOSTICS.md](DIAGNOSTICS.md).

Before it goes in a dashboard, walk the bring-up checklist in
[TESTING.md](TESTING.md) — and you can run the deck's own logic on your
computer first, with `sh tools/sim/run.sh`, no board required.

## 6. Control it — ⚠️ partly

Actions, physical surface, and why the settings menu should live on your phone
rather than on the panel: [CONTROL.md](CONTROL.md).

## 7. Make a movie — ✅ ready

```sh
python3 tools/movies/scene_spin.py 256 64        # a 3D scene, for your panel
python3 tools/movies/scene_spin.py --legacy      # and onto the PC deck
python3 tools/movies/import_gif.py cat.gif 256 64 --keep=25   # or convert a GIF
```

Two kinds, and the difference decides everything else. **Procedural** is C in
`core/screens/` that draws a frame from the audio state — the dolphins are one,
which is why bass makes the pod breach. **Baked** is pre-rendered frames in a
`.dmv`: a 3D scene, a loop, an imported GIF. Baked is far easier and cannot
react to anything.

The 3D renderer is pure Python — no numpy, no GPU, no Blender — so it runs
anywhere, including a bare container. Start from `scene_spin.py`; the four
bundled scenes each work out a different problem and are worth reading first.

**The constraints are unusual enough that habits from normal screens actively
mislead**, and the shortest path is to let Claude do that thinking for you:
[CLAUDE.md](../CLAUDE.md) tells it the grid for your display, the level budget,
and the traps. Describe what you want and which panel you have.

Full detail, including why large flat areas must sit on a level centre and why
thin bright things cannot be dim: [MOVIE-RENDERING.md](MOVIE-RENDERING.md).

**Getting one onto hardware.** Movies are too big for the app image — one
256×64 scene is most of a megabyte — so they live in their own flash partition:

```sh
python3 tools/movies/pack.py build/movies.bin movies/*_256x64.dmv
esptool.py write_flash 0x5B0000 build/movies.bin
```

That reflashes the deck's animations without touching the firmware. ⚠️ Untested
on hardware, like everything under `firmware/`.

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

Font, screens, text handling, metadata screens, the ocean, and every bundled
movie decoded three separate ways — buffered C, streaming C and Python. **A screen is not ported until it matches.** If you change
a screen deliberately, the diff will fail — update the case, don't delete it.

This has caught real bugs that were invisible by eye: a one-frame-early dolphin
breach, waterfall thresholds landing differently at double precision, and text
dithering into mush on 1-bit panels. Trust the diff over your eyes.
