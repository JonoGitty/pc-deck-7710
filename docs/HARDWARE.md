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
| **4.58" bar IPS TFT** | 960×320 | **full colour** ✅ | 3-wire SPI **+ parallel RGB** | outline 118.8 × 41.57 mm, active 110.3 × 36.77 mm ✅ | ~$14 ✅ | **Fits 1-DIN with room to spare.** Needs a host with an RGB peripheral — see §1b |
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
- 8.8" bar LCD physical dimensions are computed from the diagonal and aspect,
  not read off a datasheet.

---

## 1b. Colour — yes, and here is the exact catch

The question "can this be in colour?" has a better answer than it used to, and
a specific obstacle. Both halves matter.

**The panel exists, it is cheap, and it fits.** A 4.58" bar-type IPS TFT,
960 × 320 in landscape, is sold by several vendors off what appears to be one
piece of glass — BuyDisplay list it as **ER-TFT4.58-1** at
[**US$14.33**](https://www.buydisplay.com/bar-type-4-58-inch-320x960-ips-tft-lcd-display-spi-rgb-interface),
and the same 118.8 × 41.57 mm outline / 110.3 × 36.77 mm active area appears
under [ESHX046AQV8466ANT](https://www.lcdtftdisplays.com/quality-38363610-4-58-inch-bar-type-tft-display-320x960-40-pins-3spi-18rgb-interface-400c-d)
and [DBC046AVN40R030A](https://www.aptusdisplay.com/products/4-6-inch-320x960-rgb-mipi-interface-ips-bar-type-tft-lcd-display).
✅ Against a 180 × 50 mm single-DIN fascia that leaves 60 mm of width and 8 mm
of height spare. It is the first colour option in this document that is not a
compromise on fit.

**It maps onto the deck's grid exactly.** 960 × 320 is 192 × 64 logical dots at
5× — the legacy deck's exact width with sixteen rows added, landing in the same
`DECK_TIER_CLASSIC` layout tier as the SSD1322. At 5× each logical dot is
0.575 mm and can be drawn as a round bulb with a gap, which is the OEM
dot-matrix look rather than a tablet pretending to be one. Colour also finally
makes `DECK_CLIP` mean what the core has always said it means: level 4 renders
red, and the illumination schemes stop being a PC-only feature.

**The catch is the interface, and it is not negotiable.** The panel is
ST7701S. On that part SPI is *configuration only* — pixel data must go over a
parallel RGB bus, continuously refreshed, and no amount of cleverness gets a
frame in over three wires. That needs a host with an RGB/DPI peripheral, and
**the original ESP32 does not have one.** ESP-IDF publishes its RGB LCD driver
for the S3 and later only; the same page
[404s for `esp32`](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/lcd/rgb_lcd.html)
and [resolves for `esp32s3`](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/lcd/rgb_lcd.html).
✅ Plain ESP32 gets SPI, I²C and Intel-8080 parallel, and that is the list.

So colour collides head-on with §2: the chip that can drive the panel is the
chip that cannot do A2DP, and vice versa. Three ways out, none free:

| Route | How | Cost |
|---|---|---|
| **Two chips** | ESP32 (WROVER-E) does Bluetooth and the analysis; an ESP32-S3 does nothing but hold the framebuffer and refresh the panel. They talk over SPI or UART — a frame of 192 × 64 intensities is 12 KB, or far less delta-coded, which is nothing at 10–30 fps | ~£8 and a second board |
| **HMI panel** | The [same glass with an on-board controller and a UART command set](https://www.buydisplay.com/ips-4-58-inch-960x320-bar-type-hmi-display-intelligent-smart-uart-tft-lcd), US$28 ✅. One chip — but the deck pushes a full dot-matrix frame, not widgets, and whether that fits down a UART at frame rate is **unverified** ⚠️ | +$14, and a real risk it is too slow |
| **Pi Zero 2 W** | DPI or DSI out, BlueZ for A2DP, one board | boots in 20–30 s, needs the SD-card protection of §3 |

**Recommendation: two chips, and not yet.** The split is clean — it is exactly
the `core/` + output-stage boundary the architecture already has, with a wire
where a function call used to be — but it doubles the firmware surface on a
firmware that has never run on hardware at all. Get the SSD1322 working first.
Colour is a follow-on, and this section exists so that when someone does it
they start from the right part number instead of the search results.

⚠️ Nothing in this section has been bought, wired or run.

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

The existing UI is already keyboard- and wheel-driven, so every physical
control maps onto an action that already has a key binding. What is *not*
obvious is that the pin budget, not the UI, decides how many buttons you get.

### The pin budget ✅

On an ESP32-WROVER-E the module keeps more pins than the pinout admits:
GPIO 6–11 are the internal SPI flash and **GPIO 16 and 17 are the internal
PSRAM** ([datasheet](https://documentation.espressif.com/esp32-wrover-e_esp32-wrover-ie_datasheet_en.html)).
Add UART0 (1, 3), the strapping pins (0, 2, 12, 15 — usable as outputs, never
as buttons) and the input-only bank (34–39, no pull-ups), and after the panel
and the DAC are wired there are exactly **six** pins left for a human to press.

The encoder takes three. This is not a limit anyone would predict from the
board, and the first version of this project's pin map quietly exceeded it.

### Three ways to get buttons

| Option | Buttons | Cost | Trade |
|---|---|---|---|
| **Discrete GPIO** | 3 + encoder | £1 | Nothing to build. Every screen still reachable, because DISP and the encoder push both cycle modes |
| **Resistor ladder on one ADC pin** ✅ | 6 + encoder | £3 | Six resistors. One wire. The same technique the steering-wheel input uses, and the only one that scales |
| **I²C expander** (MCP23017, PCF8574) ⚠️ | 8–16 | £2 | More buttons than the UI has actions, an extra bus, and an interrupt line. Not implemented — the ladder covers the need |

**The ladder is the recommended build**, and not only for the pin count: it is
how you reuse a donor head unit's own front panel. Those buttons are a scanned
matrix on a flexi cable, driven by an MCU you have removed; reverse-engineering
the scan is a weekend. Lifting the switch commons and giving each switch a
resistor is an hour, and the result is an OEM fascia with your firmware behind
it.

Resistor values, expected voltages and the wiring diagram are in
[BUILD.md §3](BUILD.md#controls-the-full-six-on-one-pin). The values stay
below ~2.2 V deliberately: the original ESP32's SAR ADC is markedly non-linear
near the rail and saturates before it, so a ladder spread across the full range
merges its top button with "nothing pressed".

### The rest

- **Rotary encoder with push** — volume/dimmer, push to change mode. Read as a
  quadrature state machine, not as an edge interrupt; the naive version
  double-counts at detents and the symptom is a knob that sometimes goes the
  wrong way.
- On a Pi, all of this is GPIO, or a USB macropad with zero firmware.

## 5b. Steering wheel controls — and they work in any car

The deck **does not talk to your car**, and it does not need to. What the
aftermarket standardised is the *radio* side of the link: a **resistance to
ground**, usually on a 3.5 mm jack marked "SWC" or "W/R". A button is a
resistor; nothing pressed is open circuit. An interface box sits between the
car and the radio and does the car-specific translation it was built for.

So the deck implements the receiving half of that convention and nothing else,
which puts the whole existing adapter ecosystem behind it for the price of one
ADC pin — an S2000, an E46 and a Fiesta all work without this firmware knowing
anything about any of them.

| Interface | Fits | Programming | ~Cost ⚠️ |
|---|---|---|---|
| **InCarTec 29-629** | **S2000-specific**, plug-in to the car's 20-pin connector | none — pre-configured | £30 |
| **Connects2 CTSHO00xx** | Honda-specific, per-model looms | none | £30 |
| **Metra ASWC-1** | Universal, analogue and CAN | self-programming | £40 |
| **PAC SWI-RC-1** | Universal, analogue and CAN | DIP switches | £45 |

⚠️ Prices are typical UK retail and move. None of these has been bought or
tested against this firmware.

**It learns rather than decoding**, because there is nothing to decode:
Pioneer's own published values disagree between their own models, and a box is
configured for whichever radio you told it you had. Hold SRC for five seconds
and the panel walks you through each function. Two minutes, once. That is also
the only approach that copes with a cheap box's resistor tolerance or a bad
crimp adding a few hundred ohms.

Wiring and the learning procedure: [BUILD.md §3](BUILD.md#steering-wheel-controls).

## 5c. The remote control, aux and USB

### An infrared remote — possible, and not the first thing to fit

Pioneer shipped a credit-card IR remote with their decks and people used them,
so it is a period-correct idea as well as a practical one.

| Part | ~Cost ⚠️ | Notes |
|---|---|---|
| **TSOP38238** / VS1838B ✅ | £1 | 38 kHz IR receiver. Three pins, demodulated digital output, actively driven |
| Any NEC-protocol remote | £2–5 | A spare TV remote works; the deck learns the codes the same way it learns the wheel |

Decoding is free: the ESP32's **RMT** peripheral times the pulses in hardware,
which is what it exists for, and ESP-IDF ships an IR NEC example.

**The catch is one pin, and by the time the microphone and the tuner are in
there is not one.** See the budget below. The fix is the same trick the deck
already uses twice — put the ignition sense and the dimmer on *one* ADC pin
through a resistor network, since both are slow on/off signals from
opto-isolators:

```
   3V3 ──[10k]──┬── GPIO 36  (ADC1_CH0)
                ├──[10k]── ignition opto ── GND
                └──[22k]── dimmer   opto ── GND
```

| State | Reads |
|---|---|
| neither | ~3300 mV |
| dimmer only | ~2270 mV |
| ignition only | ~1650 mV |
| both | ~1350 mV |

The narrowest gap is 300 mV, the same margin the button ladder runs on. That
frees **GPIO 39** for the IR receiver.

⚠️ Do **not** put the receiver on GPIO 0, 2 or 12 instead. An IR receiver's
output idles *high*, and those are strapping pins with boot-time requirements
it will violate.

**Recommendation: fit the wheel controls first and see whether you still want
a remote.** In a car the wheel is strictly better — it needs no line of sight,
no aim, and no hand leaving the wheel. The remote is for a deck on a desk.

### Aux in

A 3.5 mm jack, and the audio should never enter the ESP32.

| Approach | ~Cost | Trade |
|---|---|---|
| **Audio processor — PT2313 / TDA7313** ✅ | £2–4 | **The recommended part, and the one that gives the deck a volume control.** Three stereo inputs with selection, volume in 1.25 dB steps, bass, treble, balance and fader, all over I²C on the bus the tuner already uses — so it costs no pins and returns GPIO 2 and 12. Pin-compatible with the TDA7313 |
| **Amplifier — TDA7850 or TDA7388 board** ✅ | £12–20 | ⚠️ **NOT part of the deck, and you need one.** The deck is line-out only; these are the exact ICs real head units contain — 4 × 45–50 W off the car's 12 V, with thermal and short-circuit protection. Its own fused feed, NOT through the deck's 5 V buck |
| **Analogue source switch** ✅ | £1 | A **74HC4052** dual 4-channel analogue mux: two GPIOs select one of four stereo sources — Bluetooth, radio, aux, spare. Nothing is resampled and nothing is degraded |
| Digitise it | £5 | A PCM1808 I²S ADC, so aux drives the spectrum analyser. Costs a pin this build does not have |

The switch is the right first version, and it is what every real head unit
does. The cost is that **the analyser goes flat on aux and radio**, which on a
deck built around an analyser is a genuine loss — so if that matters to you,
plan the I²S ADC in from the start rather than retrofitting it.

### USB — power and flashing, not media

**The original ESP32 has no USB peripheral at all.** Flashing and the serial
console go through a CP2102 or CH340 bridge, which is already on every dev
board.

| Want | Answer |
|---|---|
| USB-C on the fascia for flashing and logs | ✅ Wire the board's existing bridge to a panel-mount USB-C socket |
| USB-C for 5 V power on the bench | ✅ Same socket. In the car the buck converter feeds it instead |
| **A USB stick full of MP3s** | ❌ **Not possible on this chip.** USB host needs an external controller (MAX3421E over SPI), and the pins and the effort are better spent elsewhere. Music comes over Bluetooth |
| USB-C Power Delivery negotiation | ❌ Not implemented, and not needed — the deck draws well under 5 V/1 A |

An SD card over SPI is the cheap way to add local storage if you ever want it,
but the movies already live in flash and the music already arrives over
Bluetooth, so nothing currently wants one.

### The pin budget, with everything fitted

The deck fits a plain ESP32 twice over — until it does not. This is what the
options cost:

| Build | Pins used | Fits? |
|---|---|---|
| Panel + DAC + encoder + 3 buttons + car inputs | 18 | ✅ comfortably |
| ...with the 6-button ladder instead of 3 buttons | 16 | ✅ frees three pins |
| ...+ microphone (shares the I²S clocks; GPIO 15) | 17 | ✅ |
| ...+ Si4735 tuner (I²C + reset; GPIO 32/33/13) | 20 | ✅ exactly, using what the ladder freed |
| ...+ IR remote | 21 | ⚠️ **only** with ignition and dimmer combined onto one ADC pin |
| ...+ I²S ADC for aux/radio analyser | 22 | ❌ needs a GPIO expander or a bigger chip |

**The button ladder is what makes the full build possible.** It was added
because six discrete buttons did not fit; it turns out to be the thing that
pays for the tuner as well.

⚠️ **Read that fourth row as an exclusion, not an addition.** GPIO 13, 32 and
33 are the three discrete buttons *or* the tuner's I²C and reset. There is no
fourth option on this module, so a build with three buttons wired cannot have a
radio, and a build with a radio must use the ladder.

The firmware enforces this rather than trusting you to remember it. At boot
`deck_input.c` probes GPIO 35 for a ladder **before configuring any pin**, and:

| Found | GPIO 13 / 32 / 33 | Radio |
|---|---|---|
| Ladder | left alone for the tuner | started, probed, and used if it answers |
| No ladder | configured as SRC / DISP / ART | not started; logged as `tuner skipped=1` |

If you fit a tuner and the deck says no radio is present, check that your
ladder is actually being detected — `deckctl logs` prints `ladder fitted=`
at boot. A tuner on a deck that thinks it has discrete buttons never gets its
reset pulse, because that pin is an input with a pull-up on it.

---

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

## 7. Enclosure — and the answer is a donor deck

Three routes were looked at. Only one of them is actually available.

| Route | Verdict |
|---|---|
| **Gut a dead 1-DIN head unit** | ✅ **Do this.** ~£10–25 for a non-working unit on eBay. You get the steel chassis, the fascia, the DIN cage, the release-key slots, the trim ring and the fixing points — all of it correct, all of it fiddly to make, and none of it available separately |
| **Buy an empty 1-DIN chassis** | ⚠️ **They are not sold.** Searching for one returns hi-fi amplifier enclosures and 2-DIN Android housings. Nobody makes a blank 1-DIN case as a commodity part, because outside this project nobody wants one |
| **3D-print the whole thing** | ⚠️ Possible, unwise as a first attempt. A printed chassis has to survive a hot dashboard, take the cage's spring tabs without splitting, and hold the panel square. Print the *fascia* by all means — that is a flat plate with a window in it — but let steel be steel |

**What to look for in a donor.** Dead is fine; smashed is not. You want the
chassis and fascia intact, and ideally a unit whose display window is close to
the panel you have chosen — a 256×64 SSD1322 is 100.5 × 33.5 mm, and a period
head unit's window is often close enough that the bezel needs trimming rather
than replacing. Buy one with the cage and the removal keys still with it; they
are cheap separately but only if you know you need them.

**The fascia is the one part worth printing.** A 3D-printed bezel over the
chosen panel, screwed into the donor chassis, is a flat part with a rectangular
aperture and a couple of holes. It is the easy print, it is the part that has
to match your specific display, and it is the part a donor will never fit
exactly. Print it in something that survives a car interior — PETG or ASA, not
PLA, which sags in a dashboard in summer.

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
| **Car — greyscale** | SSD1322 | ESP32-WROVER-E | ~£82 electronics **+ £90–120 mechanical** | The recommended build |
| **Car — authentic VFD** | GP1294AI | ESP32-WROVER-E | ~£92 | Real glass, 1-bit |
| **Car — colour** ⚠️ | 4.58" bar IPS | ESP32-WROVER-E **+ ESP32-S3** | ~£90 | Fits 1-DIN, 960×320, but two chips and no firmware yet — see §1b |
| **Desk — full colour** | 8.8" bar LCD | none, PC drives it | ~£90 | No firmware at all; the legacy PC deck on a second monitor |

⚠️ **The electronics are the cheap half.** A car build also needs a donor
chassis, a cage, fasteners, wire, connectors and the tools to work steel and
plastic — £90–120, about half of it reusable tools. That is not a hidden cost
so much as an unglamorous one, and it is where builds stall. The full list with
quantities is [BUILD.md §1](BUILD.md#the-mechanical-bits--the-ones-everybody-forgets),
and the assembly it feeds into is [BUILD.md §7](BUILD.md#7-build-it-into-the-case).
