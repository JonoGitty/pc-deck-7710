#!/usr/bin/env sh
# Compile the portable core to WASM for the browser preview.
# No emscripten needed: the core is freestanding, so plain clang + wasm-ld do it.
set -e
cd "$(dirname "$0")/.."
mkdir -p preview
clang --target=wasm32 -nostdlib -O2 -std=c99 -Wall -Wextra -Werror \
  -Wl,--no-entry -Wl,--export-dynamic -Wl,--export-memory -Wl,--initial-memory=1114112 \
  -o preview/deck.wasm \
  core/fb.c core/font.c core/out.c core/screens/spectrum.c preview/api.c
printf 'preview/deck.wasm  %s bytes\n' "$(wc -c < preview/deck.wasm | tr -d ' ')"
