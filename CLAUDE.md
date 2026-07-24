# Working on PC·DECK with Claude

Notes for an assistant helping someone with this repo. Written for Claude, but
useful to a human skimming for how the project holds together.

## What this is

An open-source kit for building a 1-DIN car head unit, plus the PC music
visualiser it grew out of. One renderer in portable C serves both: compiled to
WebAssembly it drives the browser preview, compiled natively it drives firmware.

- `legacy/` — the PC deck. Python server + JS faceplate. **Still supported.**
- `core/` — the portable renderer. C99, no libc, no libm, no allocation.
- `preview/` — `core/` as WASM, emulating any panel.
- `firmware/` — ESP32. **Skeleton, never run on hardware.**
- `tools/movies/` — the animation maker.
- `docs/` — hardware, architecture, UI spec, handbook.

## The one rule

**`core/` is verified against the JavaScript it was ported from.**

```sh
sh tools/verify/run.sh
```

Both implementations render the same input and the framebuffers are diffed:
fonts, every screen, text handling, metadata screens, the ocean, and the movie
container. If you change a screen's output *deliberately*, the diff will fail —
**update the expectation, never delete the case.**

This is not ceremony. It has caught bugs invisible by eye: a dolphin breach
starting one frame early, waterfall thresholds landing differently at double
precision, text dithering into mush on 1-bit panels.

## Helping someone make an animation

This is the most common thing a newcomer will want, and they will not know the
constraints. Do the thinking for them.

**Ask, or infer, two things:** what they want to see, and which display they
have. If they don't know the display, assume the legacy PC deck — everyone has
that, and `--legacy` installs straight into it.

**Then pick the format yourself:**

| Their display | Grid | Notes |
|---|---|---|
| PC deck / don't know | 192×48 | use `--legacy`, they can watch it immediately |
| SSD1322 OLED | 256×64 | 16 greys, all four levels survive |
| GP1294AI / GP1287 VFD | 256×48 / 256×50 | 1-bit — **avoid thin bright detail**, it dithers to noise |
| Bar LCD | 192×48 logical | upscaled 10× |

**Reactive or not?** If they want it to respond to the music, it must be
*procedural* — C in `core/screens/`, like the dolphins. If it just needs to look
good, *bake* it with `tools/movies/`. Say which you've picked and why; people
assume everything can react.

**Do they already have a GIF?** Then use `tools/movies/import_gif.py` rather
than building a scene — it is one command. Warn them if the source is strongly
coloured: the deck has no hue, so shapes that differ only in colour merge.

**Otherwise pick a starting point:** `scene_spin.py` is the minimal template;
`scene_solar.py` shows a camera path, per-body detail and labels drawn from the
deck's own ROM; `scene_dolphins.py` is a bright subject against a dim field;
`scene_touge.py` is the inverse — a night scene lit only by its subject, and
the one that documents the level-centre rule below.

**Pin large areas to a level centre.** The quantiser puts level *n* at shade
(n + 0.5) / 4, so 0.375 / 0.625 / 0.875 are solid fields and 0.25 or 0.5 are
50/50 checkerboards. A checkerboard covering a third of the panel will beat
everything else in the frame for attention. This is the single most common
reason a render that looked fine in greyscale is a mess on the deck.

**Design decisions to make on their behalf**, because they are unobvious:

- **No colour.** Five brightness levels, and level 4 is reserved — it is the
  clipping indicator and renders red. Movies use 0–3 only.
- **It's a letterbox**, 4:1 or wider. Compose a frieze, not a portrait. A
  single centred subject wastes two-thirds of the panel.
- **10 fps.** Big slow movement reads; fast motion strobes.
- **Thin things can't be dim** on 1-bit panels. Fills carry shading, edges don't.

**Verify with the ASCII dump, not by imagining it.** `dmv.to_ascii()` prints a
frame as text. If it isn't recognisable there, it won't be on the panel.

Full detail: [docs/MOVIE-RENDERING.md](docs/MOVIE-RENDERING.md).

## Helping someone build hardware

Send them to [docs/HANDBOOK.md](docs/HANDBOOK.md) and be honest about status:
the renderer and preview are done and verified; **the firmware has never run on
hardware.** Do not describe untested firmware as working.

Two corrections already made the hard way, worth not repeating:

- **The ESP32-S3 cannot do this build.** No Bluetooth Classic means no A2DP
  means no audio from a phone. It must be the **original ESP32**, WROVER-E for
  the PSRAM.
- **The 8.8" bar LCD does not fit a 1-DIN slot** — it is ~217 mm wide against a
  180 mm fascia. Desk use or a custom fascia only.

Before recommending a part, check [docs/HARDWARE.md](docs/HARDWARE.md) — claims
there are marked ✅ verified or ⚠️ unverified, and the unverified ones are
unverified for a reason.

## Conventions

- Screens write intensities `0..4`; the output stage decides what a panel shows.
- Never encode meaning in brightness alone — it collapses on 1-bit glass.
- No literals for positions; derive from `deck_geom_t`. See
  [docs/UI-SPEC.md](docs/UI-SPEC.md).
- Generated files (`font_rom.h`, `fold_table.h`, `dolphin_rom.h`) are generated.
  Regenerate, don't edit.
- `legacy/` moves slowly and deliberately. It is what most people actually run.
