# Hardware — component survey and BOM

Everything needed to build a 1-DIN head unit that runs the deck. Parts are
grouped by the decision they belong to, so you can mix tiers.

**Confidence marking.** Prices and specs below are marked ✅ verified against a
datasheet or a live listing during research, or ⚠️ approximate / unverified —
check before ordering. Nothing here has been bought or bench-tested yet.

---

## 1. The display

This is the decision the whole build hangs off, because it fixes the dot grid
the UI is laid out on. A 1-DIN fascia is **180 × 50 mm** (ISO 7736 — see §6), so the
active area has to fit inside roughly 178 × 48 mm unless you build a
non-standard fascia.

| Part | Grid | Levels | Interface | Size | Price | Notes |
|---|---|---|---|---|---|---|
| **SSD1322 OLED** | 256×64 | **16 grey** ✅ | SPI / 8080 | 3.12", module 100.5 × 33.5 mm ✅ | ~$16–23 ✅ | Exactly 4:1 — same aspect as the current grid. Yellow variant reads as amber. Fits DIN easily |
| **Futaba GP1294AI** | 256×48 | 1-bit | SPI, 3.3 V logic | ~6" | ~$15–40 ✅ | Real VFD. Sold as pulls from car radios. [u8g2 supports it](https://github.com/olikraus/u8g2/issues/2213) |
| **Futaba GP1287BI** | 256×50 | 1-bit | SPI | ~6.1" | ~$16 ✅ | Same family, [known-good Arduino project](https://hackaday.io/project/194849-arduino-fft-spectrum-analyzer-on-vfddisplay-gp1287) |
| **Noritake GU256×64D-3900B** | 256×64 | 1-bit | RS232 / parallel, USB opt. | 115 × 28.6 mm | RFQ only ⚠️ | Current production, industrial. Every distributor quotes rather than lists |
| **8.8" bar LCD** | 1920×480 | full colour | HDMI + USB | ~217 × 54 mm ⚠️ | ~£50–70 ⚠️ | **Too wide for a 1-DIN slot.** Desk/bench use, or a custom fascia |

### Decision — SSD1322 first, the rest scheduled

Display targets are a queue, not a choice: the point of the display abstraction
is that adding one is config, not a rewrite. The order is SSD1322 → GP1294AI
VFD → Noritake → bar LCD, and nothing is dropped.

**SSD1322 for the first hardware target.** It is the only option that keeps the
deck's four intensity levels intact — 16 greys means the peak-hold dots, the art
dither and the hot/dim lyric distinction all survive, where 1-bit glass
flattens them. It's the cheapest, it's the easiest to drive, and 256×64 is the
current grid's exact aspect ratio so the layouts scale rather than reflow.

**GP1294AI as the authenticity tier.** Real vacuum fluorescent, genuinely the
part the original decks used, unbeatable in daylight. Costs you the greyscale.

### Open items before ordering ⚠️

- **GP1294AI supply requirements are unconfirmed.** VFDs need a filament AC
  drive (typically under 1 V) and an anode/grid boost (15–30 V). I could not
  confirm from the datasheet whether the bare GP1294AI panel includes these or
  needs a carrier board. An [open-hardware carrier (UNL-200AP-C)](https://oshwhub.com/xact/gp1294ai-256x48-vfd-xian-shi-mo-kuai-unl-200ap-c-_2023-09-13_19-56-46)
  exists, which suggests it needs one. **Resolve this from the datasheet before
  buying.**
- **OLED burn-in.** A head unit shows static annunciators for hours. The deck
  already has a screensaver and mode cycling, but a dedicated pixel-shift and
  an idle blank need to be in the firmware from day one.
- Bar LCD physical dimensions are computed from the diagonal and aspect, not
  read off a datasheet.

---

## 2. The brain

> ### ⚠️ Correction — it is the ORIGINAL ESP32, not the S3
>
> An earlier draft of this document recommended the ESP32-S3. That was wrong,
> and it would have killed the build: **the S3 has no Bluetooth Classic**, so it
> cannot do A2DP, so it cannot receive audio from a phone. Espressif closed the
> request to add it as ["Resolution: Won't Do"](https://github.com/espressif/esp-idf/issues/16232).
>
> The **original ESP32** is dual-mode — Classic BR/EDR *and* BLE — which is what
> makes it the right part here, and it is why every ESP32 Bluetooth speaker
> project uses it. Get a **WROVER-E** variant for the PSRAM: album art means
> decoding a 600×600 JPEG, which will not fit in internal RAM.
>
> Being dual-mode also gives the update path for free: **Classic for audio, BLE
> for firmware updates**, on one radio.

| | ESP32 (WROVER-E) | Raspberry Pi Zero 2 W |
|---|---|---|
| Boot | Under a second | 20–30 s |
| Power loss | Safe, no filesystem | Corrupts the SD card without protection |
| Bluetooth | **Dual-mode.** Classic A2DP sink + [AVRCP metadata, position and play-status callbacks](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_avrc.html) ✅, plus BLE | BlueZ, richer, D-Bus |
| Lyrics / art lookup | WiFi to a phone hotspot | Same, easier |
| Album art decode | JPEG decode + dither on-device — **needs the PSRAM** | Trivial |
| Cost | ~£8–14 ⚠️ | ~£18 ⚠️ |
| Firmware language | C / C++ | Anything |

### Decision — ESP32 (WROVER-E) primary, Pi supported

**The original ESP32 as the primary target.** In a car, instant-on and surviving a
yanked ignition matter more than convenience — a head unit that takes half a
minute to appear is a head unit you resent. The Pi stays a supported target for
people who want the easy path, which the architecture gives us for free.

The catch is honest: ESP32 means the renderer has to be portable C. See
[ARCHITECTURE.md](ARCHITECTURE.md) — that's the central decision of the build.

---

## 3. Power

A car's 12 V rail is noisy, unregulated, and swings hard on cranking.

- **Buck converter**, 12 V (9–18 V tolerant) → 5 V, automotive-rated, 3 A+.
- **Ignition sense.** Switched-live tells the deck to wake and to shut down.
  Use an **opto-isolator**, not a resistor divider — wiring car 12 V to a GPIO
  through a divider risks the board.
- **Hold-up.** On ESP32 this is barely needed. On a Pi it's mandatory: a
  supercapacitor hold-up or a UPS HAT (the Geekworm X1205 takes 9–18 V in and
  does auto power-on, power-loss detect and safe shutdown ✅) buys the seconds
  needed to unmount cleanly. Alternatively, run a read-only root filesystem.

## 4. Audio path

The deck currently only *displays* — it has no amplifier. Options:

- **Line-out only** — I2S DAC into an existing amp. Cleanest, least work.
- **Class-D board** (TPA3116-class) for a self-contained unit. ⚠️ Not yet
  specced — needs work on supply current, heat and speaker impedance.

Audio for the analyser comes from the decoded A2DP stream, tapped before
output. That's a cleaner signal than the loopback capture the PC version uses.

## 5. Controls

The existing UI is already keyboard- and wheel-driven, which makes this easy:

- **Rotary encoder with push** — volume/dimmer, push to change mode. Maps to
  the existing wheel handler.
- **6–8 momentary tactile buttons** — SRC, DISP, BAND, ART, LYRICS, and presets.
  Every one of these already has a key binding.
- On ESP32 these are GPIO. On a Pi, GPIO or a USB macropad with zero firmware.

## 6. Fitting the car — cage and connector

Two standards do the work here, and between them they mean a home-built deck
can drop into any car that takes a normal head unit.

### The cage — ISO 7736

Defines the slot, not the box. **Single DIN is a 180 × 50 mm fascia**; double
DIN is 180 × 100.3 mm. The aperture behind it is at least 188 mm wide and
182 ± 8 mm tall.

**Depth is deliberately not standardised** ✅ — which is the trap. Some cars
have a correct front aperture but a shallow cavity that only ever fitted the
original radio. Measure the car before designing the enclosure depth, not
after. The published guidance is 175 mm minimum plus room for connectors, but
treat that as aspirational rather than guaranteed.

Mounting is via a **metal cage/sleeve** that slides into the dash, with tabs
bent outward to lock it. The unit then slides into the cage and is released
with a pair of U-shaped **DIN removal keys** pushed into holes at each end of
the fascia. Both the cage and the keys are cheap commodity parts — buy, don't
design. Some cars use side brackets bolted to factory rails instead; a donor
deck usually comes with whichever its era used.

### The connector — ISO 10487

Standard since 1995 ✅. Two mandatory blocks, often moulded as one:

**Connector A — power and control (black)**

| Pin | Signal |
|---|---|
| A4 | +12 V constant, from battery — memory/standby |
| A5 | Antenna remote out, +12 V, 150–300 mA |
| A6 | Dash illumination, +12 V in when the lights are on |
| A7 | +12 V switched — ignition in ACC or ON |
| A8 | Ground / chassis |

**Connector B — speakers (brown)**

| Pin | | Pin | |
|---|---|---|---|
| B1 | Right rear + | B2 | Right rear − |
| B3 | Right front + | B4 | Right front − |
| B5 | Left front + | B6 | Left front − |
| B7 | Left rear + | B8 | Left rear − |

Three of these map straight onto things the build already needs:

- **A7** is the ignition sense — exactly the wake/shutdown signal §3 calls for.
  Opto-isolate it; don't feed it to a GPIO through a divider.
- **A4** is the standby rail, if the deck should remember state with the key out.
- **A6** is a free dimmer input. The deck already has a brightness control, and
  wiring it to the headlight feed is what a real head unit does at dusk.

⚠️ **The standard fixes the plastics, not the pinout.** ISO 10487 specifies the
physical connectors; signal assignment is manufacturer-defined, and A4/A7 are
commonly swapped. Meter the harness before connecting anything.

An **ISO adapter loom** for the specific car turns all of this into plug-in
work, and costs a few pounds.

## 7. Enclosure

- **Donor deck.** A dead 1-DIN head unit off eBay (~£10–25 ⚠️) gutted for its
  chassis, fascia and DIN cage. Keeps the OEM look and the mounting hardware,
  which is genuinely fiddly to reproduce.
- **Custom fascia.** 3D-printed bezel over the chosen panel, in the standard
  DIN chassis. Needed if the donor's window doesn't match your display.

## 8. Detachable head — parked, but shapes the enclosure

Most period decks had a detachable face for anti-theft. Two ways to read that
idea, and only one of them works.

### What doesn't work: building a face for someone else's chassis

The face↔chassis connector is proprietary and different on every model. Worse,
the deck's main MCU owns the display — it sends draw commands to the face. A
replacement face would have to *emulate the original* well enough that the MCU
doesn't fault, and would then be rendering **their** UI, not ours. That defeats
the entire point.

The community evidence matches: people successfully *relocate* an OEM faceplate
by desoldering the connector and running ribbon cable (around 20 conductors a
side), but nobody publishes a general protocol spec, and the connectors are
[non-standard per manufacturer](https://www.diymobileaudio.com/threads/head-unit-removable-face-connector-identification.395970/).
Extending a face is a wiring job. Replacing one is a per-model reverse
engineering project with a bad prize at the end.

### What does work: our head, detachable from our chassis

Build the detach mechanism ourselves. This is a real feature — anti-theft, and
you can take the face indoors — and it costs nothing but connector design.

The decision it forces:

| | Brain in the head | Brain in the chassis |
|---|---|---|
| Head contains | ESP32, display, buttons, Bluetooth | display + buttons only |
| Connector carries | 5 V, ground, line-level audio, ignition sense | display bus (SPI), button matrix, power |
| Detached head is | a complete deck — dock it anywhere with 5 V | inert |
| Pairing | travels with the head | stays in the car |
| Risk | the expensive part is the removable part | SPI over a wear connector, signal integrity |

**Brain in the head** is the more interesting answer, and it fits the project:
the head *is* the deck, and the chassis becomes a dumb dock. That means the
same head can dock to a **car chassis** (12 V, ignition, amplifier) or a **desk
stand** (USB power, line out to speakers) — one unit, both use cases, which is
exactly the split the software already has between the car build and the legacy
PC deck.

### Design notes for when this happens

- **Gold-plated spring/pogo contacts**, as the OEM faces use — they survive
  thousands of cycles and car vibration better than a board-to-board connector.
- Keep the pin count low. Brain-in-head needs roughly six: 5 V, GND, L, R,
  ignition sense, and one spare.
- The dock is then trivial to make in more than one form factor, including a
  3D-printed desk stand — which doubles as the hardware preview rig.

---

## Build tiers

| Tier | Display | Brain | Rough cost ⚠️ | For |
|---|---|---|---|---|
| **Bench** | SSD1322 | ESP32-WROVER-E | ~£32 | Developing firmware on a desk |
| **Car — greyscale** | SSD1322 | ESP32-WROVER-E | ~£82 | The recommended build |
| **Car — authentic VFD** | GP1294AI | ESP32-WROVER-E | ~£92 | Real glass, 1-bit |
| **Desk — full colour** | 8.8" bar LCD | none, PC drives it | ~£90 | No firmware at all; the legacy PC deck on a second monitor |
