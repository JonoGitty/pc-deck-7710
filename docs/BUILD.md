# Building a DECK·7710, end to end

From nothing to a head unit playing music off your phone.

> **Read [SAFETY.md](../SAFETY.md) before any of this goes in a vehicle.** The
> firmware has never run on hardware. Steps 1–6 happen on a desk from USB and
> risk nothing but your own time; step 7 is where a car is involved and where
> the consequences change.

Work through it in order. Each stage can only fail for reasons the previous
stages have ruled out, which is what makes it debuggable.

---

## 0. What you are building

An ESP32 that pretends to be a pair of Bluetooth speakers. Your phone connects
to it in the normal Bluetooth menu with no app and no pairing code, plays music
to it, and the deck shows the analyser, the track, the lyrics and the dolphins
on a dot-matrix panel — then passes the audio out to an amplifier.

```
   phone ──Bluetooth A2DP──►  ESP32  ──I2S──►  DAC ──► amplifier ──► speakers
                               │  │
                     AVRCP ────┘  └──── SPI ──► the panel
              (title, artist,              (SSD1322 or VFD)
               position, transport)
```

---

## 1. The shopping list

Prices are ⚠️ approximate and move; part numbers are ✅ checked against a
datasheet or a live listing. Full survey and alternatives in
[HARDWARE.md](HARDWARE.md).

### First decide the panel, because everything else follows from it

| Want | Buy | ~Cost | What you get | What it costs you |
|---|---|---|---|---|
| **Just make it work** | **SSD1322 OLED 256×64** ✅ | £16–23 | 16 greys, so all four intensity levels survive. Exactly 4:1, fits 1-DIN with room. Driver written and building | Nothing. **This is the recommended build** |
| **The period look** | Futaba GP1294AI VFD 256×48 ✅ | £15–40 | Real vacuum fluorescent — unbeatable in daylight, and genuinely the technology the original decks used | 1-bit. Everything dithers; thin bright detail turns to noise. ⚠️ Confirm the filament/anode supply before ordering |
| **Colour** | 4.58" bar IPS TFT 960×320 ✅ **+ a second chip** | £14 + £8 | Full colour, fits 1-DIN with 60 mm spare, and level 4 finally renders red like the core always said it would | **Two microcontrollers.** The panel needs a parallel RGB bus; the original ESP32 has no RGB peripheral, and the chips that do cannot do A2DP. ⚠️ No firmware for this yet — [HARDWARE.md §1b](HARDWARE.md#1b-colour--yes-and-here-is-the-exact-catch) |
| **A big desk display** | 8.8" bar LCD 1920×480 | £50–70 | Enormous, and the legacy PC deck drives it today with no firmware at all | ⚠️ **~217 mm wide — it does not fit a 1-DIN slot.** Desk use or a custom fascia |

If you do not have a strong reason, take the first row. It is the cheapest, the
easiest to drive, and the only one where the deck looks the way it was designed
to look.

### The bench build — everything you need to see it work (~£35)

| # | Part | Why this one | ~Cost |
|---|---|---|---|
| 1 | **ESP32-WROVER-E** dev board, **16 MB flash**, PSRAM ✅ | The *original* ESP32. Nothing else has Bluetooth Classic, so nothing else can receive audio. WROVER-E for the PSRAM the framebuffers need. 16 MB because movies get 7.6 MB of their own | £8–14 |
| 2 | **SSD1322 OLED, 256×64**, SPI, module ~100.5 × 33.5 mm ✅ | The only panel that keeps all four intensity levels. Yellow variant reads as amber | £16–23 |
| 3 | Jumper wires, breadboard | | £3 |
| 4 | USB data cable | Charge-only cables look identical and waste an hour | — |

That is a complete, working deck on a desk. Everything below adds a car.

### To hear it (~£8)

| # | Part | Why | ~Cost |
|---|---|---|---|
| 5 | **PCM5102A** I2S DAC board ⚠️ | Line-out to any amplifier. The ESP32's internal DAC is 8-bit and audibly bad | £5 |
| 6 | 3.5 mm socket or RCA pair | | £3 |

### To use it (~£12)

| # | Part | Why | ~Cost |
|---|---|---|---|
| 7 | **Rotary encoder with push**, EC11 type ⚠️ | Dim, and push to change screen | £2 |
| 8 | 3 × momentary tactile buttons | SRC, DISP, ART — all the pins a WROVER-E has left. See §3 | £1 |
| 8b | *or* 6 buttons + a resistor ladder: 1 kΩ, 2.2 kΩ, 4.7 kΩ, 10 kΩ, 18 kΩ, plus one 10 kΩ pull-up | The full fascia on one ADC pin. Also how you reuse a donor deck's own front panel | £3 |
| 9 | 3.5 mm TRS socket + 10 kΩ resistor | Steering wheel control input. See below | £2 |
| 10 | **Steering wheel interface box** ⚠️ | Only if you want the wheel buttons. Universal (PAC SWI-RC-1, Metra ASWC-1) or S2000-specific (InCarTec 29-629) | £30–45 |

### To put it in a car (~£30)

| # | Part | Why | ~Cost |
|---|---|---|---|
| 11 | **Buck converter**, 9–18 V → 5 V, ≥3 A, automotive-rated ⚠️ | A car's 12 V rail is neither 12 V nor clean | £6 |
| 12 | **PC817** opto-isolator + 4.7 kΩ ⚠️ | Ignition sense. **Never** feed car 12 V to a GPIO through a divider | £1 |
| 13 | **ISO 10487 harness adapter** for your car ✅ | Turns the whole install into plug-in work | £6 |
| 14 | **DIN cage** (ISO 7736) + removal keys ✅ | Commodity parts. Buy, do not design | £6 |
| 15 | Inline fuse holder + fuses | See SAFETY.md. Not optional | £3 |
| 16 | Donor 1-DIN head unit, dead ⚠️ | Gutted for its chassis, fascia and cage. Keeps the OEM look and the fiddly mounting hardware | £10–25 |

### Instead of the OLED, if you want real VFD glass

| Part | Trade | ~Cost |
|---|---|---|
| **Futaba GP1294AI**, 256×48 ✅ | Genuinely the period technology, unbeatable in daylight. Costs you the greyscale — everything dithers to 1-bit. ⚠️ **Confirm the filament and anode supply before buying**; see HARDWARE.md §1 | £15–40 |

---

## 2. Get the tools

```sh
git clone https://github.com/JonoGitty/pc-deck-7710.git
cd pc-deck-7710
python3 tools/deckctl.py doctor
```

`doctor` tells you what is missing and exactly how to get it. The big one is
ESP-IDF, about 2 GB, once:

```sh
git clone -b release/v5.3 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf
~/esp/esp-idf/install.sh esp32
. ~/esp/esp-idf/export.sh
```

That last line has to be run **in every new terminal**. Forgetting it is the
commonest first failure and the error it produces does not say so.

`doctor` also reads the chip ID off the board, which catches the single most
expensive mistake in this project: an ESP32-S3 cannot do A2DP at all, and
looks identical in a listing.

---

## 3. Wire it

Pin numbers are GPIO numbers, and they match the firmware. If you change one,
change it in `firmware/esp32/components/deck_display/ssd1322.c` and here
together.

### First, why the pins are where they are

A WROVER-E has fewer usable pins than the pinout suggests, and the reasons are
not guessable:

| GPIO | Why you cannot have it |
|---|---|
| **6–11** | The SPI flash, inside the module |
| **16, 17** | **The PSRAM**, inside the module ✅ [datasheet](https://documentation.espressif.com/esp32-wrover-e_esp32-wrover-ie_datasheet_en.html). The PSRAM is the whole reason this build specifies a WROVER rather than the cheaper WROOM |
| **1, 3** | UART0 — the serial console you read the logs on |
| **0, 2, 12, 15** | Strapping pins. Fine as outputs. **Never as buttons**: one held at power-on changes the boot mode |
| **34–39** | Input-only, and no internal pull-ups |

Which leaves exactly six pins for something a human presses — 13, 14, 21, 27,
32, 33 — and the encoder takes three. **So a plain-GPIO build gets three
buttons, not six.** For a full fascia, the six buttons go on one ADC pin as a
resistor ladder; see below. Both work with the same firmware binary.

### The panel — SPI

| Panel pin | ESP32 | Note |
|---|---|---|
| VCC | 3V3 | |
| GND | GND | |
| DIN / MOSI | **GPIO 23** | |
| CLK / SCLK | **GPIO 18** | |
| CS | **GPIO 5** | |
| DC | **GPIO 19** | command/data select |
| RST | **GPIO 4** | |

### The DAC — I2S

| DAC pin | ESP32 |
|---|---|
| VIN | 5V (or 3V3 — check your board) |
| GND | GND |
| BCK | **GPIO 26** |
| LRCK / WS | **GPIO 25** |
| DIN | **GPIO 22** |

### Controls: the bench build

All buttons are wired **to ground** — one leg to the pin, one to GND.

| Control | ESP32 | Pull-up |
|---|---|---|
| Encoder A | GPIO 21 | internal |
| Encoder B | GPIO 27 | internal |
| Encoder push | GPIO 14 | internal |
| SRC | GPIO 33 | internal |
| DISP | GPIO 32 | internal |
| ART | GPIO 13 | internal |

That is enough to drive everything: the encoder push and DISP both cycle
screens, so every mode is reachable. **Hold SRC** for the wheel-control
learner, **hold DISP** for the self-test.

### Controls: the full six, on one pin

Six buttons, six resistors, one wire into **GPIO 35**:

```
  3V3 ──[10k]──┬── GPIO 35  (ADC1_CH7)
               │
               ├──[ SRC    ]── 0R   ──┐
               ├──[ DISP   ]── 1k   ──┤
               ├──[ BAND   ]── 2k2  ──┤
               ├──[ ART    ]── 4k7  ──┼── GND
               ├──[ LYRICS ]── 10k  ──┤
               └──[ DEMO   ]── 18k  ──┘
```

| Button | Resistor | Reads |
|---|---|---|
| SRC | 0 Ω (wire) | 0 mV |
| DISP | 1 kΩ | 300 mV |
| BAND | 2.2 kΩ | 595 mV |
| ART | 4.7 kΩ | 1055 mV |
| LYRICS | 10 kΩ | 1650 mV |
| DEMO | 18 kΩ | 2121 mV |
| nothing pressed | — | ~3300 mV |

E24 5% resistors are fine — the smallest gap is 295 mV and the firmware
accepts ±110 mV. Values above about 2.2 V are deliberately unused: the
original ESP32's ADC goes non-linear near the rail and saturates before it,
so a ladder using the top of the range merges its highest button with
"nothing pressed".

**Nothing to configure.** The deck measures the pin at boot: a fitted ladder
sits at the top of the range, an unfitted pin floats and does not read
consistently idle. It logs `DECK|…|input|ladder|fitted=1` either way, so you
can tell.

Two presses become long-presses here too, so a fascia with no discrete buttons
can still reach the setup screens: **hold SRC** for the wheel-control learner,
**hold DISP** for the self-test.

**This is also how you use a donor head unit's own front panel.** Its buttons
are a scanned matrix on a flexi you would otherwise have to reverse-engineer;
lift the switch commons, wire each switch to a resistor, and it becomes this.

> **GPIO 34–39 are input-only and have no internal pull-up.** Nothing is wired
> to one as a bare switch — the encoder is on 21/27 for exactly this reason.
> The four signals that live there (ignition, dimmer, steering wheel, button
> ladder) are all driven by something external, so none of them floats. Put a
> bare button on one and it will read as random presses and look exactly like
> a firmware bug.

### Steering wheel controls

Your car's wheel buttons work, and they work through the same route every
aftermarket head unit uses.

**The deck does not talk to your car.** Every manufacturer wired their wheel
buttons differently, and an S2000's are on a 20-pin connector behind the radio
that no aftermarket unit understands. What the industry standardised is the
*radio* side: a **resistance to ground on a 3.5 mm jack**. A universal
interface box sits between the two and does the car-specific translation it
was built for.

So you need one box, and then it works:

| Interface | Fits | ~Cost |
|---|---|---|
| **PAC SWI-RC-1** | Universal, analogue or CAN, DIP-switch programmed | £45 ⚠️ |
| **Metra ASWC-1** | Universal, self-programming | £40 ⚠️ |
| **InCarTec 29-629** | **S2000-specific**, 20-pin, plug-in | £30 ⚠️ |
| **Connects2 CTSHO00xx** | Honda-specific | £30 ⚠️ |

Wire the interface's **3.5 mm output** (the "Pioneer/Alpine/Sony" one, not the
Kenwood blue-yellow wire) to:

| Jack | ESP32 |
|---|---|
| Tip | **GPIO 34**, and a **10 kΩ resistor from GPIO 34 to 3V3** |
| Sleeve | GND |

**Then teach it.** Hold **SRC for five seconds**. The panel asks for each
function in turn — volume up, volume down, next, previous, play/pause, display,
source — and you press the matching wheel button. Wait a few seconds to skip
one your wheel does not have. It saves to flash and remembers.

It learns rather than shipping a lookup table because there is nothing to look
up: Pioneer's own published values disagree between their own models, and an
interface box is configured for whichever radio you told it you had. Learning
is the only approach that works with any box, any car and a cheap resistor's
tolerance.

### The car side, when you get there

| Signal | ISO 10487 | ESP32 | How |
|---|---|---|---|
| Ignition sense | **A7** | GPIO 39 | **Through the opto-isolator.** 12 V → 4.7 kΩ → PC817 LED; transistor side pulls GPIO 39 to ground |
| Dash dimmer | **A6** | GPIO 36 | Same arrangement |
| Permanent 12 V | **A4** | buck in | **Fused within 150 mm** |
| Ground | **A8** | buck GND | |
| Speakers | **B1–B8** | your amplifier | The deck is line-out only; it has no amplifier |

⚠️ ISO 10487 fixes the connector, not the pinout. **A4 and A7 are commonly
swapped.** Meter the harness.

---

## 4. Build and flash

```sh
. ~/esp/esp-idf/export.sh
python3 tools/deckctl.py build --display ssd1322
python3 tools/deckctl.py flash --display ssd1322
```

Or just `python3 tools/deckctl.py` for the guided version, which asks which
panel you have and does all of it.

The display is a **build-time** choice because it fixes the grid the whole UI
is laid out against — see [VERSIONING.md](VERSIONING.md). Binaries are named
after it so you cannot flash the wrong one and conclude the project is broken.

---

## 5. Watch it boot

```sh
python3 tools/deckctl.py logs
```

Press reset. You should see, in this order:

```
   0.0s storage  boot       reason=power-on code=1
   0.1s display  selftest   stage=1 what=driver-pattern
   0.6s display  selftest   stage=2 what=output-stage
   1.1s display  selftest   stage=3 what=font
   1.6s display  health     from=unknown to=ok detail=ssd1322 256x64/16
   1.7s movies   health     from=unknown to=ok detail=4 installed
   1.8s input    health     from=unknown to=ok detail=encoder + 7 buttons
   2.1s bt       start      name=DECK 7710 addr=...
```

**The self-test stages are the diagnosis.** Each proves something the next one
depends on:

| Stage | Shows | If it fails |
|---|---|---|
| 1 | Grey ramp, dot grid, border — straight from the panel driver | Wiring, panel power, SPI, or the wrong panel build. Nothing after this can work |
| 2 | Five intensity bands through `core/`'s output stage | The glass is fine. The level mapping or dither is wrong |
| 3 | "DECK 7710" and an alphabet | Framebuffer and font. Text is also the canary for a mirrored axis |
| 4 | The subsystem table | Everything is up; read what it says |

A blank panel at stage 1 is a hardware problem. A blank panel *after* stage 1
is a software problem. That distinction is the whole reason the self-test
exists — see [DIAGNOSTICS.md](DIAGNOSTICS.md) for the rest.

---

## 6. Pair your phone

1. On the deck, wait for `bt start` in the log.
2. On the phone: **Settings → Bluetooth → DECK 7710**.
3. Accept. There is no code — the deck uses Just Works pairing, because a head
   unit has no keypad and requiring a passkey produces a device nothing will
   pair with.
4. Play something.

What should happen, and what it means if it does not:

| Symptom | Cause |
|---|---|
| Deck not in the phone's list | Not discoverable. It stops advertising once something is connected — disconnect the other device, or reset |
| Pairs but no sound | The DAC. `deckctl logs` will show `audio health ... no I2S DAC`. The display still works |
| Sound but a still display | Audio is reaching the DAC but not the analyser. Should be impossible — file a bug with the log |
| Display moves, no track name | AVRCP did not connect, or the player does not publish metadata. Some do not |
| Everything works, no lyrics | Expected. Lyrics need WiFi; see below |

**Lyrics** need a network, and a car does not have one. The deck can join your
phone's hotspot: set the SSID and password in NVS, or leave it — every other
screen works with the radio off, which is the point.

---

## 7. Put it in the car

Only after all of the above works on a desk.

1. **Disconnect the battery.**
2. Fit the DIN cage into the dash aperture, tabs bent out to lock.
3. Wire the ISO adapter to your loom: A4 fused to the buck input, A8 to
   ground, A7 through the opto to GPIO 39, A6 likewise to GPIO 36.
4. **Meter it before connecting.** A4 and A7 get swapped by manufacturers.
5. Slide the deck in, reconnect, and check standby current before you leave it
   for a week.

Read [SAFETY.md](../SAFETY.md). Fire, airbags, battery drain and driver
distraction are all real and all avoidable.

---

## 8. Put your own animations on it

Movies are content, not firmware. They live in their own flash partition, so
changing them does not touch the image and an update does not touch them.

```sh
# render the bundled scenes for your panel
python3 tools/movies/scene_touge.py 256 64
python3 tools/movies/scene_dolphins.py 256 64
python3 tools/movies/scene_solar.py 256 64

# or convert a GIF you already have
python3 tools/movies/import_gif.py yours.gif 256 64 --keep=22

# or your own photographs
python3 tools/deckctl.py pictures holiday/*.jpg --keep=30 --hold=4

# then choose what goes on the deck
python3 tools/deckctl.py movies
```

`deckctl movies` lists what is available for your panel, packs what you pick,
checks it fits, and writes it — without touching the firmware.

To design one from scratch, ask Claude: [CLAUDE.md](../CLAUDE.md) carries the
constraints, and [MOVIE-RENDERING.md](MOVIE-RENDERING.md) has the detail.

---

## When it does not work

[DIAGNOSTICS.md](DIAGNOSTICS.md) — the self-test stages, the log format, how to
get a crash out of a deck that is already in a dashboard, and a table of
symptoms with causes.
