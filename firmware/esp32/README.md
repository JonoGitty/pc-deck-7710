# firmware/esp32 — the car deck

**Original ESP32 (WROVER-E)** + SSD1322. Bluetooth A2DP sink for audio, AVRCP
for metadata and transport, WiFi to a phone hotspot for lyrics and album art,
`core/` for every dot on the panel.

> Not the S3. The S3 has no Bluetooth Classic, so no A2DP, so no audio from a
> phone — see [HARDWARE.md §2](../../docs/HARDWARE.md). The WROVER-E variant is
> for the PSRAM, which album-art decoding needs.

> **Status: skeleton, not yet run on hardware.** Nothing here has been flashed.
> The structure, the pin map and the driver command sequences come from the
> datasheets and the ESP-IDF docs, and should be treated as a first draft to be
> corrected on the bench — not as tested code. `core/` is the part that is
> verified, and it is verified against the JS it was ported from, not against a
> panel.

## Layout

```
main/
  deck_main.c        boot, task wiring, the render loop
  deck_bt.c          A2DP sink + AVRCP: audio in, metadata and transport
  deck_audio.c       PCM tap -> 13-band FFT -> deck_state_t
  deck_net.c         WiFi, LRCLIB lyrics, iTunes art
  deck_input.c       encoder + buttons -> the same actions the keys drive
  deck_config.c      NVS-backed settings: display, colour, brightness, mode
components/
  deck_display/      panel drivers. SSD1322 first, GP1294AI next.
  deck_movies/       baked movies, streamed out of their own flash partition
partitions.csv       16 MB layout: factory + two OTA slots, 7.25 MB of movies
```

`core/` is pulled in as an IDF component from the repo root, unmodified — the
same source the browser preview compiles.

## Where the movies live, and why it is not in the app image

A baked 256×64 movie is 300–850 KB. The app partition is 1.5 MB and has to hold
Bluetooth, WiFi, TLS, the FFT and the renderer. One movie would take most of
what is left; the four bundled ones total 1.4 MB and would not fit at all.

So they do not go in the firmware. `partitions.csv` gives them 7.25 MB of their
own, `tools/movies/pack.py` builds the image, and the decoder streams out of it
through the source interface in `core/movie.h` — 320 bytes of stack at a time,
never the whole file:

```sh
python3 tools/movies/pack.py build/movies.bin movies/*_256x64.dmv
esptool.py write_flash 0x490000 build/movies.bin
```

Reflashing that partition changes the deck's movies without touching the
firmware, and an OTA update leaves them alone. The same source interface takes
an SD card instead, which is the answer on a 4 MB part, where the app slots
leave nothing worth having.

`sh tools/verify/run.sh` packs the container and reads it back with an
independent implementation, because the C that parses it at boot runs on a chip
the test suite cannot execute.

## Why the render loop looks like it does

The panel is refreshed at a fixed rate and the world is stepped separately.
Movies run at 10 fps by design; the analyser wants every frame it can get. Both
read the same `deck_state_t`, so the split lives in the loop rather than in the
screens.

## Bring-up order

1. Blink, then SSD1322 init and a test pattern — proves SPI and the panel.
2. `core/` test screens over that — proves the framebuffer path end to end.
3. A2DP sink to I2S, audio audible — proves Bluetooth before any analysis.
4. FFT into `deck_state_t` — the analyser screens come alive.
5. AVRCP metadata, then WiFi lookups — the metadata screens come alive.
6. Encoder and buttons.
7. Power, ignition sense, enclosure.

Each step is independently checkable, which matters because a deck that does
everything at once and shows nothing is very hard to debug.
