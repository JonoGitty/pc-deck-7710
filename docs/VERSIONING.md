# Versioning and updates

Four things ship independently and each can break the others, so each is
versioned separately rather than everything sharing one number.

| Component | Versioned as | Changes when |
|---|---|---|
| **core** | semver `core-1.4.0` | the renderer changes. A minor bump may change pixels; a major bump changes the API screens are written against |
| **firmware** | `<board>-<display>-<semver>` e.g. `esp32s3-ssd1322-0.3.1` | anything in `firmware/` changes, or it is rebuilt against a new core |
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
esp32s3-ssd1322-0.3.1.bin      256x64, 16 levels
esp32s3-gp1294ai-0.3.1.bin     256x48, 1-bit
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

## Updates on the deck

Deliberately not decided yet — it depends on the control surface (see
[CONTROL.md](CONTROL.md)), and getting it wrong means bricking a unit behind a
dashboard. The options, with the tradeoff that actually matters:

1. **USB only.** Pull the fascia, plug in, flash. Zero risk of a half-written
   OTA, zero attack surface, and genuinely annoying if the deck is fitted.
2. **OTA over WiFi**, from the phone hotspot the deck already uses for lyrics.
   Convenient, and needs an A/B partition scheme with rollback or one bad
   flash in a tunnel leaves a dead dashboard.
3. **SD card.** Drop a `.bin` on a card, hold a button at power-on. No network,
   recoverable by hand, and the card slot is a mechanical part that fails.

**Whatever is chosen, movies must update separately from firmware.** Adding an
animation should not mean reflashing, and a corrupt movie must not stop the deck
booting — that is the single most important safety property here, because
movies are the part users will be adding constantly.

## Open questions

- Which update path (above)?
- Does the deck need to boot with no valid movies at all? It should, falling
  back to the built-in procedural dolphins — which is an argument for the
  dolphins staying compiled in rather than shipping as a `.dmv`.
