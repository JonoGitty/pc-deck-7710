<h1 align="center">DECK·7710</h1>

<p align="center">
  <b>Build your own 1-DIN car head unit.</b><br>
  One portable C renderer drives real glass, a browser preview and a PC
  visualiser — the same code, the same dots, on all three.
</p>

![The PC deck playing, showing the 13-band spectrum analyser](docs/media/faceplate.png)

A *deck* is what a head unit is called. This one started as a music visualiser
for a PC and turned into a kit for building the real thing: pick a display,
preview it in a browser before spending money, flash the firmware for your
setup, and slide it into the dash.

Two things live here and both are supported:

|  | What it is | Status |
|---|---|---|
| **The PC deck** | A Pioneer-style faceplate in a browser, fed by whatever your PC is playing | **Working.** This is what most people run |
| **The car deck** | ESP32 + an OLED or VFD panel, Bluetooth audio from your phone | **Renderer verified, firmware written and compiling — but never run on hardware** |

Everything below was rendered by the code in this repo. Nothing is a mockup —
`sh tools/media/make.sh` regenerates the lot.

---

## The screens

Ten display modes, all drawn by `core/` — the same C the firmware runs.

| | |
|---|---|
| **Spectrum analyser** — 13 bands, 63 Hz–16 kHz, peak-hold dots<br>![](docs/media/spectrum.gif) | **Mirror spectrum** — L/R split growing out from centre<br>![](docs/media/mirror.gif) |
| **VU meter** — twin needles with overshoot and recoil<br>![](docs/media/vu.gif) | **Oscilloscope** — dot-matrix scope with phosphor persistence<br>![](docs/media/scope.gif) |
| **Cityscape EQ** — coarse tower blocks with a rising scan sweep<br>![](docs/media/city.gif) | **Waterfall** — 32×12 spectral memory climbing upward<br>![](docs/media/waterfall.gif) |
| **3D spectrum** — a receding analyser landscape, hidden lines removed<br>![](docs/media/3d.gif) | **Ocean cruise** — the dolphins, and they react to the bass<br>![](docs/media/ocean.gif) |
| **Album art** — the sleeve, ordered-dithered to four levels<br>![](docs/media/cover.gif) | **Lyrics** — synced from LRCLIB, current line hot<br>![](docs/media/lyrics.gif) |

<details>
<summary><b>And the whole faceplate</b> — VU, album art, lyrics, waterfall, dolphins</summary>

![VU meter on the faceplate](docs/media/faceplate-vu.png)
![Album art screen on the faceplate](docs/media/faceplate-cover.png)
![Lyrics screen on the faceplate](docs/media/faceplate-lyrics.png)
![Waterfall on the faceplate](docs/media/faceplate-waterfall.png)
![Ocean cruise on the faceplate](docs/media/faceplate-ocean.png)

</details>

## The movies

Animations you can make yourself, in pure Python, with no GPU and no Blender.
They play on the PC deck and on the hardware — same file, same decoder.

![SOLAR — a tour of the solar system](docs/media/solar.gif)

*`SOLAR` — thirteen stops from the Sun to Pluto, with labels drawn from the
deck's own character ROM. `tools/movies/scene_solar.py`.*

![TOUGE — a roadster sideways down a mountain pass at night](docs/media/touge.gif)

*`TOUGE` — a night run lit only by the car's own headlights, where the subject
is the hole in the light. `tools/movies/scene_touge.py`.*

![VTEC — a roadster's bar tachometer wound out through the crossover](docs/media/vtec.gif)

*`VTEC` — a bar tacho, a speed readout and a gear number, because the car this
is drawn from uses a bar rather than a dial and a bar *is* a 4:1 strip. The
revs are a crude engine with load and a limiter, not a sine wave: the
hesitation at the top of a gear is what makes it look like driving.
`tools/movies/scene_vtec.py`.*

![DOLPHINS — the classic head-unit screensaver in 3D](docs/media/dolphins.gif)

*`DOLPHINS` — the classic screensaver, rebuilt with a real mesh and a real sea.
`tools/movies/scene_dolphins.py`.*

![SPIN — the minimal template scene](docs/media/spin.gif)

*`SPIN` — the minimal template. Copy `tools/movies/scene_spin.py` and change
the scene; it is deliberately small.*

Already have a GIF? `tools/movies/import_gif.py` converts it:

![REEF — an imported reef clip](docs/media/reef.gif)

*Footage needs `--keep`. A camera uses the whole tonal range and the deck has
four levels, so a mid-grey background becomes a checkerboard louder than the
subject; lighting only the brightest fifth is what fixes it.*

**Making one is a conversation, not a tutorial.** [CLAUDE.md](CLAUDE.md) tells
Claude the constraints — the grid for your panel, the level budget, why thin
bright things dither into noise — so you can describe what you want and get
something that reads on the glass. Full detail in
[docs/MOVIE-RENDERING.md](docs/MOVIE-RENDERING.md).

---

## Run the PC deck

Windows, because it captures WASAPI loopback and Windows media metadata.

```sh
python legacy/server.py          # or double-click start.cmd
```

Opens <http://127.0.0.1:7710>. Play music anywhere — Spotify, YouTube, a game —
and the deck lights up on its own.

- **Audio** — WASAPI loopback of the default output, surviving device switches
- **Track, art, position** — Windows SMTC
- **Lyrics** — [lrclib.net](https://lrclib.net), no account
- **Album art fallback** — the [iTunes Search API](https://performance-partners.apple.com/search-api), only when the player supplies none

Those two lookups are the only things that leave the machine, and both send
just title, artist and album. No audio ever leaves. `LYRICS_ENABLED = False`
and `ART_LOOKUP_ENABLED = False` at the top of `legacy/server.py` turn them off.

### Controls

| | |
|---|---|
| `D` / DISP / knob click | cycle display mode |
| `1`–`9`, `0` | jump to a mode |
| `A` / `L` | album art / lyrics |
| `[` `]` | nudge lyric sync ±0.25 s |
| `V` / `N` | movies / next movie |
| `B` | force the ocean cruise |
| `C` | colour scheme — eight OEM illumination colours |
| `M` | demo: auto-cycle everything |
| `T` | TV mode — fullscreen the display only |
| `F` | fullscreen the whole faceplate |

**Idle behaviour, faithful to the era:** music stops → 3 s → clock; 12 s → the
dolphins take over; music returns → a hard horizontal wipe back to the
analyser. On every track change the album art is dithered to a 3-tone bitmap
and shown as a NOW PLAYING interstitial for two seconds.

## Preview a panel you have not bought

```sh
sh tools/serve.sh          # http://127.0.0.1:7720
```

Compiles `core/` to WASM and emulates any panel: grid size, level count, dot
shape, illumination colour. Because it is the same C the firmware runs, what
you see is what the glass does — not an artist's impression of it.

## Run the deck itself, without a deck

```sh
sh tools/sim/run.sh                      # 20 seconds of deck, as ASCII
sh tools/sim/run.sh --gif /tmp/deck.gif  # ...as an animation
sh tools/sim/run.sh --grid 192 48 --levels 2    # on a 1-bit VFD you do not own
```

The preview above runs `core/`. This runs the layer above it — the firmware's
own `deck_ui.c`, unmodified, against stub drivers. Which screen is on, when the
deck gives up and shows the clock, how a track change interrupts, what a movie
does at its last frame: all of it, on a laptop, in about a second.

```sh
python3 tools/sim/test_behaviour.py      # 20 assertions about what it does
```

It is not a simulation of the hardware, and
[docs/TESTING.md](docs/TESTING.md) is explicit about which questions it cannot
answer — SPI timing, the Bluetooth stack, a supply that sags on crank. Those
fail on hardware and only on hardware.

## Build the hardware

**[docs/BUILD.md](docs/BUILD.md) is the end-to-end guide** — shopping list with
part numbers, pin-by-pin wiring, flashing, pairing, and the car install last.
One tool does the whole loop:

```sh
python3 tools/deckctl.py            # guided: check, build, flash, load movies
```

```sh
python3 tools/deckctl.py doctor     # what is plugged in, and does it work
python3 tools/deckctl.py build      # compile for your panel
python3 tools/deckctl.py flash      # firmware onto the deck
python3 tools/deckctl.py movies     # choose animations, write them to flash
python3 tools/deckctl.py pictures *.jpg   # your own photographs
python3 tools/deckctl.py logs       # watch it run
python3 tools/deckctl.py coredump   # why it crashed
```

`doctor` reads the chip ID off the board, which catches the most expensive
mistake here: an ESP32-S3 cannot do A2DP and looks identical in a listing.

**When it does not work:** [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md). The deck
runs a four-stage self-test at every boot, in an order where each stage can
only fail for reasons the previous ones ruled out — so a blank panel at stage 1
is hardware and a blank panel after stage 1 is software.

Then [docs/HARDWARE.md](docs/HARDWARE.md) for the full component survey, where
every claim is marked ✅ verified against a datasheet or listing, or ⚠️ not, and
[docs/HANDBOOK.md](docs/HANDBOOK.md) for the tiers and bring-up order.

| Tier | Display | Brain | Rough cost |
|---|---|---|---|
| Bench | SSD1322 OLED 256×64, 16 grey | ESP32-WROVER-E | ~£32 |
| Car — greyscale | SSD1322 | ESP32-WROVER-E | ~£82 |
| Car — authentic VFD | Futaba GP1294AI, 1-bit | ESP32-WROVER-E | ~£92 |
| Car — colour ⚠️ | 4.58" bar IPS, 960×320 | ESP32 **+ ESP32-S3** | ~£90 |

Two corrections already made the hard way, so you do not have to:

- **It must be the original ESP32, not the S3.** The S3 has no Bluetooth
  Classic, so no A2DP, so no audio from a phone. Espressif closed that request
  "Won't Do".
- **The 8.8" bar LCD does not fit a 1-DIN slot** — ~217 mm wide against a
  180 mm fascia. There *is* a colour panel that fits; see
  [HARDWARE.md §1b](docs/HARDWARE.md).

---

## How it holds together

```
                     ┌── WASM ─────► browser preview (emulates any panel)
   core/  (C99) ─────┼── ESP32 ────► car firmware
                     └── Linux/Pi ─► firmware
   legacy/ (JS)  ───────────────────► the PC deck
```

`core/` is C99 with no libc, no libm, no allocation and no floating-point
surprises — it ships its own trig so a dolphin breaches on the same frame in
V8, glibc and on an ESP32. Screens write intensity levels 0–4; a per-target
output stage decides what a panel shows, whether that is 16 greys, a 1-bit
Bayer dither or an RGB palette.

### The one rule

**`core/` is verified against the JavaScript it was ported from.**

```sh
sh tools/verify/run.sh
```

Both implementations render the same input and the framebuffers are diffed:
fonts, every screen, text handling, metadata screens, the ocean, and every
movie decoded three ways. If you change a screen's output on purpose the diff
fails — **update the expectation, never delete the case.**

This is not ceremony. It has caught a dolphin breaching one frame early,
waterfall thresholds landing differently at double precision, and text
dithering into mush on 1-bit panels.

## What is in here

| Path | |
|---|---|
| `legacy/` | The PC deck. Python server + JS faceplate. Moves slowly and deliberately |
| `core/` | The portable renderer. C99, no deps, no allocation |
| `preview/` | `core/` as WASM, emulating any panel in a browser |
| `firmware/esp32/` | The car deck. Written and compiling — **never run on hardware** |
| `tools/deckctl.py` | Build, flash, load movies and pictures, read logs and crashes |
| `tools/movies/` | The animation maker: 3D renderer, GIF and photo importers, `.dmv` packer |
| `tools/verify/` | The differential test suite |
| `tools/sim/` | The deck's own firmware, running on your computer |
| `tools/media/` | Regenerates every picture in this README |
| `docs/` | Handbook, hardware, architecture, UI spec, control, versioning |

## Status, honestly

| | |
|---|---|
| PC deck | Working, in daily use |
| `core/` renderer | Complete, all ten screens, verified against the JS |
| Browser preview | Working |
| Movie tooling | Working — 3D scenes, GIF import, flash packing |
| ESP32 firmware | **Written and compiles.** A2DP + AVRCP, FFT analyser, SSD1322 and VFD drivers, movies from flash, self-test and diagnostics. 1.74 MB image, ESP-IDF v5.3. **Never run on hardware** |
| Flash tooling | Working — `deckctl` does build, flash, content and logs |
| Colour panel | Researched, part identified, ⚠️ nothing bought or wired |

## Docs

[Build guide](docs/BUILD.md) · [Diagnostics](docs/DIAGNOSTICS.md) ·
[Safety](SAFETY.md) · [Handbook](docs/HANDBOOK.md) · [Hardware](docs/HARDWARE.md) ·
[Architecture](docs/ARCHITECTURE.md) · [UI spec](docs/UI-SPEC.md) ·
[Making animations](docs/MOVIE-RENDERING.md) · [Control](docs/CONTROL.md) ·
[Testing](docs/TESTING.md) · [Versioning](docs/VERSIONING.md) ·
[For Claude](CLAUDE.md)

---

## Before you wire anything to a car

> **This is an unfinished hobby project published as source, not a product.**
> Nothing here has been tested in a vehicle, certified by anyone, or approved
> for road use. The firmware has never run on hardware. If you build one, you
> are the manufacturer, and every consequence is yours — including fire,
> battery drain, airbag circuits, driver distraction, insurance and type
> approval.
>
> **Read [SAFETY.md](SAFETY.md) first.** It is short, specific, and lists the
> things that actually go wrong.

Everything in this project can be built and run on a desk from USB before any
of it goes near a dashboard, and the handbook is ordered so that it is.

---

Co-designed with GPT 5.6 (Sol) — the visual spec, the meter ballistics and the
album-art dither idea came out of that consult.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

MIT licensed — see [LICENSE](LICENSE), [NOTICE](NOTICE) and [SAFETY.md](SAFETY.md).
Build one.
