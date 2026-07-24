# core — the portable renderer

C99, no dependencies, no allocation. Compiles unchanged for the browser
preview (WASM), ESP32-S3 firmware, and a Pi. See
[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## What's here

| File | |
|---|---|
| `deck.h` | geometry descriptor, intensity scale, framebuffer, layout tiers |
| `fb.c` | framebuffer ops — `deck_set` is max-blend, matching the JS `setDot` |
| `font.h/.c` | 5×7 and 3×5 text, UTF-8 in |
| `font_rom.h` | **generated** — do not edit, see below |
| `trig.c/.h` | deterministic sin/cos — the core never calls libm |
| `out.c/.h` | output stage: 0..4 mapped onto what a panel can show |
| `compat.c` | memset/memcpy/memmove/memcmp for freestanding builds |
| `screens/` | one file per screen |

## Two things that bite freestanding builds

**libm is off limits.** Not just because `-nostdlib` has none — V8's `Math.sin`,
glibc's and the ESP32's are three implementations that can disagree in the last
bit, so a screen positioning dots from trig would render differently per
target. `core/trig.c` carries its own, accurate to one ulp over the range the
screens use, and `tools/verify/trigtest.c` checks it against libm.

**The compiler emits memset even when you don't.** clang turns the skyline init
in `screens/spectrum3d.c` into a `memset` call. Freestanding C still requires
the implementation to provide it, so `core/compat.c` does — compiled only into
freestanding builds, since a hosted build wants libc's.

## The ROM is generated, not transcribed

`font_rom.h` is emitted from `legacy/web/font.js` by
`tools/gen_font_rom.js`. Hand-copying ninety glyphs is an excellent way to
introduce a silent one-bit error, so we don't. Regenerate with:

```sh
node tools/gen_font_rom.js > core/font_rom.h
```

The generated ASCII tables bake in the JS lookup rules — `toUpperCase`, and the
fallbacks for characters the ROM lacks (`?` at 5×7, blank at 3×5) — so the C
code needs neither.

## Verifying the port

Every piece of `core/` is ported from working JavaScript, so "does it match?"
is answerable rather than a matter of trust:

```sh
sh tools/verify/run.sh
```

This renders `tools/verify/cases.tsv` twice — once through `core/`, once
through the original `legacy/web/font.js` in Node — and diffs a digest of the
resulting framebuffers (hash, lit-dot count, bounding box, advance, measured
width). Cases cover the full ASCII range in both fonts, the five non-ASCII
glyphs, case folding, scales 1–3, every intensity, clipping past all four
edges, and max-blend overlap in both orders.

The harness is checked for sensitivity, not just for passing: shifting the
glyph advance by one pixel, or dropping a single dot from every glyph, both
fail it.

**Add cases as screens are ported.** A screen isn't ported until it renders
identically to its JS original.

## Conventions

- Screens write only `DECK_OFF`..`DECK_CLIP`. Never assume more than five
  levels — the output stage decides what the panel can show.
- Never encode meaning in intensity alone; it collapses on 1-bit targets.
- No literals for positions. Derive from `deck_geom_t`, per
  [../docs/UI-SPEC.md](../docs/UI-SPEC.md).
