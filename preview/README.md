# preview — the hardware preview

The browser preview runs `core/` compiled to WebAssembly. It is the same C the
firmware builds from, so the dots on screen are the dots the panel will light —
including how a target with fewer levels than the renderer dithers them.

```sh
sh tools/serve.sh      # builds the wasm and serves on :7720
```

## Why it is built this way

`preview.js` does no drawing of its own. It pushes state into the core, calls a
screen, calls the output stage, and paints the bytes that come back. Every dot
position, intensity and dither decision is made in C. If the preview and the
hardware ever disagree, it is a bug in one shared implementation rather than a
drift between two.

## Build

No emscripten. The core is freestanding, so plain clang targets wasm32:

```sh
sh tools/build_wasm.sh
```

Entry points are marked with `export_name` in `api.c` — wasm-ld garbage-collects
anything unreachable, and a library has no entry point to be reachable from.

## Picker

Targets are the real parts from [../docs/HARDWARE.md](../docs/HARDWARE.md), so
the picker doubles as a shopping list. Selecting one sets its native level
count; you can then override it to see what the same frame looks like on
different glass.

Content modes:

- **Spectrum analyzer** — a ported screen, animated
- **Text / font sheet** — both ROMs, scales and intensities
- **Intensity ramp** — the five levels as solid blocks. The quickest way to see
  what a target's output stage can and cannot separate.
