#!/usr/bin/env sh
# Regenerate everything in docs/media. Run from the repo root:
#
#   sh tools/media/make.sh
#
# Nothing in docs/media is drawn by hand. The screen animations come out of the
# same C core the firmware links, the faceplate stills are the real legacy page
# running in a real browser with a stubbed WebSocket, and the movie previews are
# the shipped .dmv files decoded. That is deliberate: a README full of mockups
# rots the moment the code changes, and nobody notices. These regenerate.
set -e
cd "$(dirname "$0")/../.."

OUT=docs/media
mkdir -p "$OUT" build/shots

printf '\n== display modes (C core, 192x48) ==\n'
gcc -std=c99 -Wall -Wextra -O2 -o build/mkshots \
    core/fb.c core/font.c core/text.c core/art.c core/trig.c core/screens/*.c \
    tools/media/shots.c -lm
build/mkshots build/shots
python3 tools/media/shots.py build/shots "$OUT" 20 4

printf '\n== telephone screens ==\n'
# Driven by a call state machine rather than by audio, so they get their own
# harness. Same .raw format, same renderer.
gcc -std=c99 -Wall -Wextra -O2 -Icore -o build/mkcall \
    core/fb.c core/font.c core/text.c core/art.c core/trig.c core/screens/*.c \
    tools/media/callshots.c -lm
mkdir -p build/callshots
build/mkcall build/callshots 256 64
python3 tools/media/shots.py build/callshots "$OUT" 20 3

printf '\n== movie previews ==\n'
# Excerpts, not the whole film. A preview GIF costs about 3 KB a frame, so the
# full 56-second SOLAR is 1.5 MB on its own — the point of the picture is to
# show what the thing looks like, and the deck is where you watch it.
#   name  frames-from  frames-max
# VTEC starts from 40 so the excerpt opens with the bar already climbing
# through the crossover, which is the whole point of the animation. From zero
# it opens on a car idling.
# AE86 opens on headlights in the dark — correct for the animation, useless as
# a thumbnail, which is a still. From 8 it opens on the tofu-shop door.
set -- "spin 0 0" "solar 0 190" "dolphins 24 170" "touge 60 190" "reef 0 0" \
       "vtec 40 190" "ae86 8 0"
for spec in "$@"; do
  set -- $spec
  m=$1; from=$2; max=$3
  src=movies/${m}_256x64.dmv
  [ -f "$src" ] || src=movies/${m}_192x48.dmv
  [ -f "$src" ] || continue
  opt="--from=$from"
  [ "$max" != "0" ] && opt="$opt --max=$max"
  # shellcheck disable=SC2086
  python3 tools/movies/preview_gif.py "$src" "$OUT/$m.gif" 3 $opt
done

printf '\n== diagrams (pin map read out of the firmware) ==\n'
# SVG rather than PNG: it is text, so a pin moving shows up as a diff you can
# read. The pin map is parsed from the deck_*.c defines and refuses to draw a
# GPIO twice, so it cannot quietly stop describing the firmware.
python3 tools/diagrams/make.py "$OUT"
# ...and the step-by-step build manual, drawn isometrically from the same
# millimetre dimensions the overview drawings use.
python3 tools/diagrams/steps.py "$OUT"
# ...and one window-fit drawing per donor family, scaled from the measured
# window in donors/*.json.
python3 tools/diagrams/donors.py "$OUT"
# ...and the two transplant drawings: aligning the panel to its lit area,
# and turning a donor's scanned matrix into the deck's one-wire ladder.
python3 tools/diagrams/transplant.py "$OUT"

printf '\n== faceplate stills (real page, real browser) ==\n'
CHROMIUM="${CHROMIUM:-/opt/pw-browsers/chromium-1194/chrome-linux/chrome}"
if [ -x "$CHROMIUM" ] && node -e "require('playwright-core')" 2>/dev/null; then
  ( cd legacy && python3 -m http.server 7799 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > /tmp/deckshot.pid )
  sleep 1
  CHROMIUM="$CHROMIUM" node tools/media/faceplate.js \
      http://127.0.0.1:7799/web/index.html "$OUT" || true
  kill "$(cat /tmp/deckshot.pid)" 2>/dev/null || true
  rm -f /tmp/deckshot.pid
  python3 - "$OUT" <<'PY'
import sys, os
from PIL import Image

# A faceplate screenshot is a black panel, one amber hue and a few greys. Left
# as truecolour PNG that is 400 KB of nothing; on an adaptive palette it is
# under a tenth of that and visually identical, because there was never more
# than a hundred distinct colours in it. The hero keeps its full pixel size —
# it is the first thing anyone sees — and the rest come down to 1500 px, which
# is still wider than GitHub will ever render them.
out = sys.argv[1]
SHOTS = {"faceplate": None, "faceplate-vu": 1500, "faceplate-cover": 1500,
         "faceplate-lyrics": 1500, "faceplate-waterfall": 1500,
         "faceplate-ocean": 1500}
for name, width in SHOTS.items():
    p = os.path.join(out, name + ".png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("RGB")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG) \
      .save(p, optimize=True)
    print(f"  {p}  {os.path.getsize(p)/1024:.0f} KB")
PY
else
  printf '  SKIPPED (needs playwright-core + Chromium)\n'
fi

printf '\n== total ==\n'
du -sh "$OUT"
