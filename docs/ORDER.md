# Your order list

**Generated** by `tools/order/build.py` from the choices below. Rerun it with different flags and you get a different list — the catalogue with all the alternatives and the reasoning is [BUYING.md](BUYING.md).

| Decision | This list assumes |
|---|---|
| Panel | **SSD1322 OLED 256×64** |
| Radio | **none — Bluetooth only for now** |
| Amplifier | **reuse the donor's** |
| Donor | **cassette-era 1-DIN** |
| Car | **Honda S2000 (AP1 or AP2 — no difference)** |

> ### ⚠️ Order stage 1 and nothing else, first
>
> **The firmware has never run on hardware.** Everything up to *it lights up on a desk* is about £32 and risks nothing but your time. Everything after it assumes that worked. Buying a donor first means owning a fascia and not knowing whether the thing that goes behind it runs at all.

---

## 1 · The bench deck — order this and NOTHING else first

It plays music from your phone on a desk. Every risk in this project is concentrated in whether this works, and it costs about £32 to find out.

| | Part | ~£ | Where |
|---|---|---|---|
| 1× | **ESP32-WROVER-E dev board, 8 or 16 MB flash** | 9–14 | DigiKey ESP32-DEVKITC-VE ($11, WROVER-E, 8 MB flash + 8 MB PSRAM, in stock) — or eBay/AliExpress “ESP32 WROVER 16MB” |
| 1× | **SSD1322 OLED, 256×64, SPI, yellow** | 16–26 | Tindie “3.12 inch 256x64 OLED SSD1322” ($29.95) · eBay UK 265720175865 (£25.89, ⚠️ seller away until 19 Aug) |
| 1× | **PCM5102A I²S DAC board** | 5 | eBay / AliExpress “PCM5102A DAC module” |
| 1× | **Breadboard + jumper wires** | 3 | any |
| 1× | **USB data cable** | — | any — ⚠️ **not** a charge-only one |

- **ESP32-WROVER-E dev board, 8 or 16 MB flash** — ⚠️ The ORIGINAL ESP32. Not S3, C3 or C6 — they have no Bluetooth Classic, so no A2DP, so no audio from a phone. WROVER for the PSRAM the framebuffers need. 8 MB builds with `--flash 8`.
- **SSD1322 OLED, 256×64, SPI, yellow** — The panel the whole project is tuned for: 16 greys, so all four intensity levels survive. Module is 100.5 × 33.5 mm; only 76.8 × 19.2 mm of it lights.
- **PCM5102A I²S DAC board** — Line out to whatever amplifies it. The ESP32's internal DAC is 8-bit and audibly bad.
- **Breadboard + jumper wires** — Nothing is soldered until it works.
- **USB data cable** — A charge-only cable is an hour of debugging a deck that is fine.

**Stage total: £33–48**

---

## 2 · Controls and volume

Order with stage 1 or straight after it — none of it is wasted whatever happens next.

| | Part | ~£ | Where |
|---|---|---|---|
| 1× | **PT2313 or TDA7313 audio processor** | 2–4 | eBay / AliExpress “PT2313 module” or “TDA7313 module” |
| 1× | **EC11 rotary encoder, with push, 6 mm D-shaft** | 2 | eBay / any component supplier |
| 1× | **Resistors: 1 k, 2k2, 4k7, 10 k, 18 k, plus a 10 k pull-up** | 5 | any starter assortment covers it |
| 2× | **3.5 mm panel-mount sockets** | 4 | any |

- **PT2313 or TDA7313 audio processor** — ⚠️ **Without this the deck has no volume control at all.** A bare 74HC4052 mux only selects a source. The PT2313 does source selection *plus* volume, bass, treble, balance and fader over the I²C bus — and costs no extra pins.
- **EC11 rotary encoder, with push, 6 mm D-shaft** — Volume, and press for mode. Reuse the donor's KNOB on top of it — the original's electrical type does not matter, only its cap does.
- **Resistors: 1 k, 2k2, 4k7, 10 k, 18 k, plus a 10 k pull-up** — ⚠️ **The button ladder, and on your build it is not optional** — see the note below. Six buttons on one analogue pin, each landing on its own voltage.
- **3.5 mm panel-mount sockets** — Aux in, and one spare. They go through the CD slot, so no drilling.

**Stage total: £13–15**

---

## 4 · The donor and the mechanical bits

AFTER the bench deck lights up. Not before.

| | Part | ~£ | Where |
|---|---|---|---|
| 1× | **Cassette-era 1-DIN donor, dead** | 0–15 | eBay “blaupunkt woodstock cassette” / “blaupunkt london” / “blaupunkt toronto” / “pioneer keh cassette” / “sony xr cassette” — or a scrapyard, in person, often free |
| 1× | **ISO 7736 cage + removal keys** | 0–8 | usually comes with the donor; otherwise Halfords or eBay |
| 1× | **M3/M2.5 screws, nylon standoffs, nyloc nuts, washers** | 15 | an assortment box from eBay or Amazon |
| 1× | **Smoked acrylic, 1 mm, ~100 × 40 mm** | 4 | eBay “1mm smoked acrylic sheet” |

- **Cassette-era 1-DIN donor, dead** — ✅ Free amplifier inside, the cassette door closes flush so there is no hole to fill, and the best buttons in the project: mechanical, real travel, often on a PCB rather than a carbon flexi.
- **ISO 7736 cage + removal keys** — Goes in the car first and stays there.
- **M3/M2.5 screws, nylon standoffs, nyloc nuts, washers** — ⚠️ Nylon standoffs, not brass — brass shorts to a chassis that is also your ground. Nyloc nuts, because a car vibrates for a living.
- **Smoked acrylic, 1 mm, ~100 × 40 mm** — The window, bonded behind the aperture. Smoked and not clear: an unlit dot has to look dead rather than grey.

**Stage total: £19–42**

---

## 5 · Into the car

⚠️ Read SAFETY.md before this stage, not after it.

| | Part | ~£ | Where |
|---|---|---|---|
| — | **…or reuse the donor's amplifier — £0** | — | it is already inside the donor, bolted to the chassis as its heatsink and wired to the ISO connector |
| 1× | **Honda ISO loom (Connects2 CT20HD02)** | 10 | Dynamic Sounds, Honda S2000 — £9.99 |
| 1× | **Buck converter 9–18 V → 5 V, ≥3 A, automotive** | 6 | eBay “automotive buck converter 5V 3A” |
| 1× | **PC817 opto-isolator + 4.7 kΩ** | 1 | any component supplier |
| 1× | **Inline fuse holder + fuses** | 3 | Halfords / any motor factor |
| 1× | **Multimeter, if you do not own one** | 0–15 | Screwfix / Toolstation |

- **…or reuse the donor's amplifier — £0** — ✅ Every CD-era head unit has one. Cut the four inputs free of the dead preamp and inject the deck's line out. ⚠️ Tie the ST-BY and MUTE pins to their enable level or it stays silent and you conclude the chip is dead. See REUSE.md.
- **Honda ISO loom (Connects2 CT20HD02)** — Honda's own multi-pin connector to ISO 10487. ⚠️ Meter A4 and A7 before connecting: the connector is standard, the pinout is not.
- **Buck converter 9–18 V → 5 V, ≥3 A, automotive** — The car's 12 V rail is a hostile place.
- **PC817 opto-isolator + 4.7 kΩ** — Ignition sense. It does not go straight to a GPIO — a load dump does not respect a 3.3 V input.
- **Inline fuse holder + fuses** — Not optional.
- **Multimeter, if you do not own one** — ⚠️ The one tool on this list that is genuinely not optional.

**Stage total: £20–35**

---

## The whole bill: £85–140

Excluding postage, and every price was seen once. See [BUYING.md §6](BUYING.md) for what could not be checked.


---

## What these choices mean, before you solder

### No radio does NOT mean you can use discrete buttons

The three discrete button pins are the same three pins as the I²C bus and the tuner's reset: **GPIO 33 is SRC and SCL, GPIO 32 is DISP and SDA, GPIO 13 is ART and the tuner reset.** So wiring buttons one-per-pin takes the I²C bus away — and the PT2313 lives on that bus. Discrete buttons therefore mean **no volume control**. Use the resistor ladder on GPIO 35 instead; it is one wire for all six buttons and it leaves I²C alone. The firmware probes for the ladder at boot and tells you which it found.

### Your donor's buttons are the easy case

Cassette-era units usually put their switches on a proper PCB rather than carbon pads on a flexi — so the ladder rewire is cut the traces, common one side of every switch, and take the other leg to ground through its own resistor. You never have to work out the original scanning order.

### And the aperture problem solves itself

The cassette door is hinged and closes flush, so there is no hole to fill. Either leave it shut and cut your window elsewhere, or take the door off and use its aperture — it is wide, flat and square-cornered, which makes it the best window in the project.

### ⚠️ The amplifier reuse has one step people fail on

The old microcontroller drove the amp IC's `ST-BY` and `MUTE` pins. With it gone they float, the amplifier stays muted, and you conclude the chip is dead and buy a board. Tie both to their enable level through the resistor the datasheet specifies. If it does not work you have lost an evening and buy the £12–20 board you were going to buy anyway.

### The window is marked from the glass, not the board

The SSD1322 module is 100.5 × 33.5 mm and only 76.8 × 19.2 mm of it lights, and the lit area is **not centred** on the PCB. Hold the module against the fascia, power it, and scribe round what glows. Mark it from the board outline and it is permanently a few millimetres out.

---

⚠️ **Nothing in this project has been built and the firmware has never run on hardware.** This is a list of what to buy to find out, in the order that finds out cheapest.
