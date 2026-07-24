#!/usr/bin/env sh
# Prove the C core renders identically to the legacy JS it was ported from.
# Run from the repo root:  sh tools/verify/run.sh
set -e
cd "$(dirname "$0")/../.."

mkdir -p build

gcc -std=c99 -Wall -Wextra -Werror -O2 \
    -o build/trigtest tools/verify/trigtest.c core/trig.c -lm
build/trigtest

gcc -std=c99 -Wall -Wextra -Werror -O2 \
    -o build/verify_c core/fb.c core/font.c tools/verify/render.c

build/verify_c tools/verify/cases.tsv > build/out_c.txt
node tools/verify/render.js tools/verify/cases.tsv > build/out_js.txt

if diff -u build/out_js.txt build/out_c.txt > build/out_diff.txt; then
  printf 'core matches legacy JS on %s cases\n' "$(wc -l < build/out_c.txt | tr -d ' ')"
else
  printf 'MISMATCH — C core differs from legacy JS:\n\n'
  cat build/out_diff.txt
  exit 1
fi

gcc -std=c99 -Wall -Wextra -Werror -O2 \
    -o build/verify_screens_c core/fb.c core/font.c core/trig.c core/text.c core/art.c core/screens/*.c tools/verify/render_screens.c

build/verify_screens_c tools/verify/screens.tsv > build/scr_c.txt
node tools/verify/render_screens.js tools/verify/screens.tsv > build/scr_js.txt

if diff -u build/scr_js.txt build/scr_c.txt > build/scr_diff.txt; then
  printf 'screens match legacy JS on %s cases\n' "$(wc -l < build/scr_c.txt | tr -d ' ')"
else
  printf 'MISMATCH — ported screens differ from legacy JS:\n\n'
  cat build/scr_diff.txt
  exit 1
fi

gcc -std=c99 -Wall -Wextra -Werror -O2 \
    -o build/verify_text_c core/text.c tools/verify/render_text.c

build/verify_text_c tools/verify/text.tsv > build/txt_c.txt
node tools/verify/render_text.js tools/verify/text.tsv > build/txt_js.txt

if diff -u build/txt_js.txt build/txt_c.txt > build/txt_diff.txt; then
  printf 'text helpers match legacy JS on %s cases\n' "$(wc -l < build/txt_c.txt | tr -d ' ')"
else
  printf 'MISMATCH — text helpers differ from legacy JS:\n\n'
  cat build/txt_diff.txt
  exit 1
fi

gcc -std=c99 -Wall -Wextra -Werror -O2 -o build/verify_meta_c \
    core/fb.c core/font.c core/text.c core/art.c core/trig.c \
    core/screens/cover.c core/screens/lyrics.c tools/verify/render_meta.c

build/verify_meta_c tools/verify/meta.tsv > build/meta_c.txt
node tools/verify/render_meta.js tools/verify/meta.tsv > build/meta_js.txt

if diff -u build/meta_js.txt build/meta_c.txt > build/meta_diff.txt; then
  printf 'metadata screens match legacy JS on %s cases\n' "$(wc -l < build/meta_c.txt | tr -d ' ')"
else
  printf 'MISMATCH — cover/lyrics differ from legacy JS:\n\n'
  cat build/meta_diff.txt
  exit 1
fi

# The ocean reference needs Canvas for the dolphin silhouettes, so its JS side
# runs in Chromium rather than bare node. Skipped when that isn't available,
# so the rest of the suite still works without Playwright installed.
CHROMIUM="${CHROMIUM:-/opt/pw-browsers/chromium-1194/chrome-linux/chrome}"
if [ -x "$CHROMIUM" ] && node -e "require('playwright-core')" 2>/dev/null; then
  gcc -std=c99 -Wall -Wextra -Werror -O2 \
      -o build/verify_ocean_c core/fb.c core/trig.c core/screens/ocean.c \
      tools/verify/render_ocean.c

  build/verify_ocean_c tools/verify/ocean.tsv > build/oc_c.txt
  CHROMIUM="$CHROMIUM" node tools/verify/render_ocean.js tools/verify/ocean.tsv > build/oc_js.txt

  if diff -u build/oc_js.txt build/oc_c.txt > build/oc_diff.txt; then
    printf 'ocean matches legacy JS on %s scenarios\n' "$(wc -l < build/oc_c.txt | tr -d ' ')"
  else
    printf 'MISMATCH — ocean differs from legacy JS\n'
    exit 1
  fi
else
  printf 'ocean check SKIPPED (needs playwright-core + Chromium)\n'
fi

if [ -f movies/spin_192x48.dmv ]; then
  gcc -std=c99 -Wall -Wextra -Werror -O2 \
      -o build/verify_movie_c core/fb.c core/movie.c tools/verify/render_movie.c
  build/verify_movie_c movies/spin_192x48.dmv > build/mv_c.txt
  python3 tools/verify/render_movie.py movies/spin_192x48.dmv > build/mv_py.txt
  if diff -u build/mv_py.txt build/mv_c.txt > build/mv_diff.txt; then
    printf '.dmv round-trips: C and python decoders agree on %s frames\n' \
      "$(( $(wc -l < build/mv_c.txt) - 1 ))"
  else
    printf 'MISMATCH — .dmv decoders disagree:\n\n'; cat build/mv_diff.txt; exit 1
  fi
fi
