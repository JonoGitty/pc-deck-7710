#!/usr/bin/env sh
# Run the deck on your computer. No ESP32, no panel, no phone.
#
#   sh tools/sim/run.sh                          20 s, ASCII every second
#   sh tools/sim/run.sh --gif /tmp/deck.gif      ...and an animation
#   sh tools/sim/run.sh --script tools/sim/scripts/idle.txt
#   sh tools/sim/run.sh --movie movies/vtec_256x64.dmv --secs 26
#
# This compiles the firmware's own deck_ui.c against stub drivers, so the
# thing under test is the file the ESP32 runs. See tools/sim/sim.c for where
# the line between "real" and "stub" is drawn and why.
set -e
cd "$(dirname "$0")/../.."
mkdir -p build

RAW=""
ARGS=""
GIF=""
while [ $# -gt 0 ]; do
  case "$1" in
    --gif) GIF="$2"; RAW="build/sim.raw"; ARGS="$ARGS --gif $RAW"; shift 2 ;;
    *) ARGS="$ARGS $1"; shift ;;
  esac
done

gcc -std=gnu99 -Wall -Wextra -O2 -o build/sim \
    core/fb.c core/font.c core/text.c core/art.c core/out.c core/trig.c \
    core/movie.c core/screens/*.c \
    firmware/esp32/main/deck_ui.c \
    tools/sim/sim.c tools/sim/sim_stubs.c \
    -Icore -Ifirmware/esp32/main -Itools/sim -lm

# shellcheck disable=SC2086
build/sim $ARGS

if [ -n "$GIF" ]; then
  python3 tools/sim/to_gif.py "$RAW" "$GIF"
fi
