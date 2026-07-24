# Architecture

## Decisions taken

| | Decision |
|---|---|
| **Renderer** | Portable C99, compiled to both WASM (preview) and native (firmware) |
| **First brain** | ESP32 **WROVER-E** (dual-mode BT — the S3 has no Classic BT and so cannot do A2DP). Pi kept as an alternative |
| **First display** | SSD1322 256×64. The others stay scheduled, not dropped |
| **Movies** | Compiled into the firmware; dolphins stay the default and stay procedural |
| **Updates** | OTA over BLE, only while idle |
| **Control** | Full transport + volume back to the phone over AVRCP |
| **Legacy split** | Done — the PC deck lives in `legacy/`, still launched by the same commands |


The goal: **one repo where anyone can build their own 1-DIN head unit**, pick
their display, preview it in a browser before spending money, and download a
firmware package for their exact setup. Plus the original PC visualiser, kept
working for people who just want that.

## The central decision: one renderer, compiled twice

The preview is only useful if it is **the same code** as the firmware. If the
preview is JavaScript and the firmware is C++, they drift, and the preview
starts lying about what the hardware does — at which point it is worse than
useless, because you trust it.

So the renderer becomes **portable C99 with no dependencies**, compiled two ways:

```
                    ┌── WASM ──────► browser preview (any display emulated)
   core/ (C99) ─────┤
                    ├── ESP32-S3 ──► firmware
                    └── Linux/Pi ──► firmware
```

This is a real cost — roughly 1,600 lines of JavaScript to port — but the
existing code is already written in a C-shaped style. `fb` is a `Uint8Array`
indexed by `y * W + x`; the draw functions are plain `(fb, state)` calls with no
closures or object graphs. It is mostly mechanical translation, and it buys:

- a preview that is **pixel-identical** to the hardware, by construction
- one place to fix a bug, not two
- new display targets as config, not as a rewrite
- reproducible per-display firmware builds in CI

## Repo layout

```
legacy/            the PC deck exactly as it is today — frozen, still works
  server.py        WASAPI + SMTC + lyrics/art lookups
  web/             JS renderer, 192x48, eight colour schemes

core/              portable C99, no deps, no allocation          [started]
  deck.h           geometry descriptor + public API              ✅
  fb.c             framebuffer, setDot, intensity model          ✅
  font.c           5x7 and 3x5 ROMs (+ larger fonts for big panels) ✅
  layout.c         picks a layout tier from the geometry
  screens/         spectrum, mirror, vu, scope, city, waterfall, 3d,
                   ocean, cover, lyrics                        ✅ all ten
  out/             output stages: 1-bit dither, 4-level, 16-grey, RGB

preview/           the browser harness — core compiled to WASM
                   display picker: grid size, levels, tech, pixel shape,
                   colour, bezel. Feeds it fake or live deck data

firmware/
  esp32/           A2DP sink, AVRCP, esp-dsp FFT, SPI display driver,
                   WiFi lookups, GPIO controls, BLE OTA
  pi/              BlueZ + PipeWire equivalent

docs/              this, HARDWARE.md, UI-SPEC.md, build guides, diagrams
```

`legacy/` is frozen on purpose. It is the thing that already works, it is what
most people will actually run, and it should not break because the firmware
build churned.

## The display abstraction

The renderer never knows what it is drawing on. It writes intensity values
`0..4` — the deck's existing scale — into a framebuffer described by:

```c
typedef struct {
  uint16_t w, h;       // dot grid, e.g. 192x48, 256x64, 256x48
  uint8_t  levels;     // 2 = 1-bit, 5 = the deck's 0..4, 16 = greyscale
  uint8_t  flags;      // colour capable, round pixels, ...
} deck_geom_t;
```

An **output stage** then maps `0..4` onto the device:

| Device | Mapping |
|---|---|
| 1-bit VFD / mono OLED | ordered dither, denser pattern per level |
| SSD1322 | level × 3.75 → 16 greys, near-lossless |
| RGB panel | palette lookup — the eight colour schemes live here |

This is why the 1-bit preview is free: it is the same output stage the firmware
uses, running in the browser.

## Data plane

Every platform produces the same event stream, so the renderer is identical:

| | Legacy PC | ESP32 / Pi |
|---|---|---|
| Audio | WASAPI loopback | decoded A2DP stream |
| Metadata | Windows SMTC | AVRCP over Bluetooth |
| Position | SMTC timeline, interpolated | AVRCP position, interpolated |
| Lyrics | LRCLIB over HTTP | LRCLIB over WiFi |
| Art | SMTC thumbnail → iTunes fallback | iTunes lookup (AVRCP cover art is unreliable) |

## Phasing

1. **Spec and preview.** Port the core to C, get WASM preview running with a
   display picker. No hardware needed, nothing to buy.
   - Every port step is verified against the JS original by rendering the same
     cases both ways and diffing framebuffers — `sh tools/verify/run.sh`. A
     screen is not ported until it matches.
2. **Bench firmware.** ESP32-S3 + SSD1322 on a desk. Bluetooth, audio, display.
3. **Car build.** Power, ignition, enclosure, controls.
4. **Guides.** Per-display build docs, diagrams, downloadable firmware packages,
   and a `CLAUDE.md` so others can get an assistant to walk them through it.

## Roadmap / parked

- **GIF support** — animated GIFs as a display source, dithered to the deck's
  intensity levels. Wanted, deliberately deferred until the core port lands.
- **Detachable head** — our own detach mechanism, not a replacement face for a
  donor deck. If the brain lives in the head, the head is the whole deck and
  the chassis becomes a dumb dock: a car dock or a desk stand. See
  [HARDWARE.md §7](HARDWARE.md). Parked, but it constrains enclosure and
  connector design, so decide before anything is 3D-printed.
- Additional display families: HUB75 LED matrix (suits the LED bulb schemes),
  larger colour panels.
- FM tuner, local media playback — explicitly out of scope. The phone is the
  source and the browser.
