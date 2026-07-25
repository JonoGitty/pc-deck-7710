#!/usr/bin/env sh
# The three hardware drivers, run on this computer.
#
#   sh tools/sim/drivers.sh              print the trace
#   sh tools/sim/drivers.sh --check      ...and assert on it
#   sh tools/sim/drivers.sh --only tuner-rds     one scenario, for debugging
#
# deck_tuner.c, deck_audioproc.c and deck_hfp.c are compiled UNMODIFIED against
# the fake SDK in tools/sim/idf/ and the part models in tools/sim/fake_hw.c. So
# what is under test is the file the ESP32 runs, not a description of it.
#
# ONE PROCESS PER SCENARIO. The drivers keep their state in file statics and
# nothing in the firmware resets them — on the deck a reboot does that. So a
# fresh process is what a fresh boot is, and the NVS file that survives it is
# what flash is. See tools/sim/idf/README.md.
set -e
cd "$(dirname "$0")/../.."
mkdir -p build

gcc -std=gnu99 -Wall -Wextra -Werror -O1 -o build/drivers \
    firmware/esp32/main/deck_tuner.c \
    firmware/esp32/main/deck_audioproc.c \
    firmware/esp32/main/deck_hfp.c \
    firmware/esp32/main/deck_i2c.c \
    tools/sim/drivers.c tools/sim/fake_hw.c tools/sim/stub_diag.c \
    -Icore -Ifirmware/esp32/main -Itools/sim -Itools/sim/idf

SIM_NVS=build/sim_nvs.bin
export SIM_NVS
rm -f "$SIM_NVS"

if [ "$1" = "--only" ]; then
  build/drivers "$2"
  exit 0
fi

OUT=build/drivers.txt
: > "$OUT"
printf '# driver harness: the real drivers, a fake SDK, a virtual clock\n' >> "$OUT"
build/drivers --list | while read -r s; do
  build/drivers "$s" >> "$OUT"
done
printf '== end\n' >> "$OUT"

if [ "$1" = "--check" ]; then
  python3 tools/sim/test_drivers.py "$OUT"
else
  cat "$OUT"
fi
