# Versioning and updates

Four things ship independently and each can break the others, so each is
versioned separately rather than everything sharing one number.

| Component | Versioned as | Changes when |
|---|---|---|
| **core** | semver `core-1.4.0` | the renderer changes. A minor bump may change pixels; a major bump changes the API screens are written against |
| **firmware** | `<board>-<display>-<semver>` e.g. `esp32-ssd1322-0.3.1` | anything in `firmware/` changes, or it is rebuilt against a new core |
| **movies** | `.dmv` container version in the magic (`DMV1`) | the container format changes. Individual movies are content, not versions |
| **legacy PC deck** | `legacy-1.x` | the Python/JS deck changes. Deliberately slow-moving |

## Why firmware carries the display in its name

There is no single firmware. A build is `core` + a platform layer + **one panel
driver and its geometry**, and a GP1294AI build is not a variant of an SSD1322
build — it is a different binary with a different grid, different level count
and a different layout tier. Naming them apart is what stops someone flashing
the wrong one and concluding the project is broken.

A release therefore publishes a **matrix**, not a file:

```
esp32-ssd1322-0.3.1.bin        256x64, 16 levels
esp32-gp1294ai-0.3.1.bin      256x48, 1-bit
pi-ssd1322-0.3.1.tar.gz        same core, Linux platform layer
```

Same `core` version across a row; that is the point of the shared renderer.

## Compatibility rules

- **core minor bumps may move pixels.** That is allowed and expected — the
  thin-feature rule changed every 1-bit target's output, correctly. What a
  minor bump must not do is change the API screens compile against.
- **firmware must pin a core version.** A build records the core version it was
  compiled from, and the deck shows it in the service screen. When someone
  reports "the lyrics look wrong", the first question is answerable.
- **`.dmv` is forward-compatible by refusal.** A decoder that does not
  recognise the magic refuses to play rather than rendering noise. The magic
  carries the version precisely so a future format cannot be misread as this
  one.
- **Movies are not tied to a panel.** A movie baked at 192×48 plays on a 256×64
  panel, centred. That is why `deck_movie_blit` centres rather than scales.

## Updates — OTA over BLE

Decided: **firmware updates arrive over Bluetooth LE**, from a phone, with no
cable and no fascia removal.

This works because the deck runs the **original ESP32**, which is dual-mode: it
uses Bluetooth **Classic** for A2DP audio and **BLE** for the update channel, on
one radio. (It would not have worked on an ESP32-S3, which has no Classic BT at
all — see [HARDWARE.md](HARDWARE.md).)

Espressif publish a BLE OTA component, and the standard partition layout gives
the safety property that matters:

```
factory   the image that always boots — never overwritten
ota_0     ┐ new firmware lands here, is verified, and only then
ota_1     ┘ marked bootable; a bad flash rolls back to the last good one
```

**Updates are only accepted while the deck is idle** — not streaming. Classic
and BLE coexisting on one radio is supported but tight, and running an OTA
during A2DP playback is the case most likely to expose it. Refusing to update
mid-song costs nothing: nobody wants to flash firmware while driving to music.

⚠️ Coexistence has not been proven on hardware yet. If it turns out to be
unreliable even when idle, the fallback is OTA over the WiFi hotspot the deck
already joins for lyrics — same partition scheme, different transport.

## Movies ship beside the firmware, not inside it

> **Reversed.** This section used to say movies were compiled into the binary,
> for the good reason that it keeps the firmware self-contained — no filesystem,
> no storage layer, no corrupt file able to stop the deck booting. Then the
> movies got made and the numbers settled it: SOLAR is 848 KB, DOLPHINS 347 KB,
> TOUGE 282 KB, against an app partition of 1.5 MB that also has to hold
> Bluetooth, WiFi, TLS, the FFT and the renderer. One movie would take most of
> what is left and the four bundled ones do not fit at all. Self-contained was
> never on the table; it just looked like it was until someone did the sums.

Movies live in their own read-only partition and the decoder streams out of it
— see `core/movie.h` and `firmware/esp32/partitions.csv`. They are **content**,
not code, and they version like content:

- A movie is identified by the name inside its own header, not by a number.
  Replacing one is replacing a file.
- The container is versioned by its magic (`DMV1`), and a decoder that does not
  recognise the magic refuses to play rather than rendering noise.
- The partition survives an OTA untouched, and reflashing it changes the deck's
  animations without touching the firmware — which is the property the
  compiled-in scheme was trying to buy and could not afford.

The safety argument still has to be answered, since a corrupt file can no
longer be ruled out by construction: the decoder bounds-checks every run
against the grid, treats a short read as end-of-movie, and applies a frame
whole or not at all. A damaged partition stops a movie, not the deck.

The dolphins stay **procedural and compiled in** regardless. They are the
fallback that always works, and being code rather than data is what lets them
react to the bass.
