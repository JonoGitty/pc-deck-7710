# firmware/esp32 — the car deck

ESP32-S3 + SSD1322. Bluetooth A2DP sink for audio, AVRCP for metadata and
transport, WiFi to a phone hotspot for lyrics and album art, `core/` for every
dot on the panel.

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
```

`core/` is pulled in as an IDF component from the repo root, unmodified — the
same source the browser preview compiles.

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
