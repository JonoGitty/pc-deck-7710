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
    -o build/verify_screens_c core/fb.c core/font.c core/trig.c core/screens/*.c tools/verify/render_screens.c

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
