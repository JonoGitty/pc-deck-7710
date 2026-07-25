# Where to actually buy it

[BUILD.md §1](BUILD.md#1-the-shopping-list) says *what* the parts are and why.
This page says *where*, in the order you should order them, so you are not
waiting on a fascia adapter while the interesting part sits on a desk.

> **Prices and stock move, and links rot.** Every link here was checked once,
> on the date of the last commit to this file. Nothing has been ordered or
> received. Where a listing is a specific product I have marked it ✅; where it
> is a search or a category I have said so, because those stay valid longer.

---

## 0. The one decision that affects what you order

**Check the flash size before you buy the board.** This is the single sourcing
trap in the whole build.

The recommended layout wants **16 MB**, and `ESP32-WROVER-E-N16R8` — the 16 MB,
8 MB-PSRAM part — is easy to buy as a **bare surface-mount module** and
genuinely hard to buy as **a board with pins on it**. Most assembled WROVER dev
boards are 8 MB or 4 MB.

| You have | Build with | What it costs you |
|---|---|---|
| 16 MB | default | Nothing. Two OTA slots, 7.6 MB of animations |
| **8 MB** | `--flash 8` | One OTA slot instead of two, and 3.2 MB of animations instead of 7.6. Both builds are in CI |
| 4 MB | ❌ | Does not fit. Movies would have to go on an SD card |

```sh
python3 tools/deckctl.py build --flash 8      # or leave it off for 16 MB
```

`firmware/esp32/partitions-8mb.csv` spells out exactly what the smaller layout
gives up. **8 MB is a perfectly good build** — take it if that is what you can
get, rather than soldering a carrier for a bare module.

⚠️ **Do not buy an ESP32-S3, C3 or C6.** They have no Bluetooth Classic, so no
A2DP, so no audio from a phone. `deckctl doctor` reads the chip ID and will
tell you, but after you have paid.

---

## 1. First order: the bench deck (~£35)

Get this working on a desk before anything else is ordered. It is a complete,
functioning deck.

| Part | Where | ~Price |
|---|---|---|
| **ESP32-WROVER dev board** — WROVER-E or -IE, **8 MB or 16 MB**, PSRAM | [DigiKey ESP32-DEVKITC-VE](https://www.digikey.com/en/products/detail/espressif-systems/ESP32-DEVKITC-VE/12091812) ✅ (8 MB, assembled), or eBay/AliExpress for "ESP32 WROVER 16MB" ⚠️ | £9–14 |
| **SSD1322 OLED, 256×64, SPI, yellow** | [eBay UK, 3.12" 256×64 SSD1322](https://www.ebay.co.uk/itm/265720175865) ✅ · [Tindie, UK seller](https://www.tindie.com/products/displaymodules/312-inch-256x64-oled-display-module-ssd1322/) ✅ · [Newhaven, if you want a datasheet and an invoice](https://newhavendisplay.com/3-12-inch-yellow-graphic-oled-module/) ✅ | £16–23 |
| **Futaba GP1294AI VFD, 256×48** — *the period look, instead of the OLED* | See the three routes below ⚠️ | £12–£140 |
| Breadboard, jumper wires | any | £3 |
| USB data cable | any — **not a charge-only one** | — |

### The VFD, if you want the period look — three routes, and they are not equal

The firmware drives a **GP1294AI** and it is genuinely the technology the
original decks used. What you cannot buy cheaply is the *supply*: a VFD needs a
filament supply and tens of volts of anode drive, and the bare glass gives you
neither.

| Route | ~Price | What you are taking on |
|---|---|---|
| **Bare panel**, sold as an air-purifier / appliance spare — [AliExpress "VFD25648 GP1294AI"](https://www.aliexpress.com/item/1005003360434382.html) ⚠️ | ~$15 | **You build the inverter.** ⚠️ [HARDWARE.md §1](HARDWARE.md) — confirm the filament and anode requirements before ordering |
| **Pulled from a car radio** — [eBay, GP1294 256×48 pulls](https://www.ebay.com/itm/285247576592) ⚠️ | ~$15 | Same, plus unknown history. ✅ Worth knowing: **these panels really are commonly sold as car-radio pulls**, which is what [REUSE.md](REUSE.md) claims — so if your donor has one, the firmware already drives it |
| **Assembled module with driver, USB-C or 4.5–24 V in** — [eBay, "VFD Futaba module 256×48 DIY SPI"](https://www.ebay.com/itm/135447013329) ✅ | ~$180 | Nothing. It is SPI in and light out |
| Trade quantity, with an invoice | ask | [Giant Supplier](https://www.giant-supplier.com/GIANT-SUPPLIER/Futaba-VFD.html), an authorised Futaba distributor ✅ |

⚠️ **£16 of SSD1322 is the recommended build and this is not false modesty.**
The VFD costs either an inverter you design or ten times the money, and it
costs you the greyscale either way — everything dithers to 1-bit. Buy the OLED,
get the deck working, and treat the VFD as the second build.

Bare `ESP32-WROVER-E-N16R8` modules, if you are making your own carrier:
[DigiKey](https://www.digikey.com/en/products/detail/espressif-systems/ESP32-WROVER-E-16MB/11613135) ·
[Mouser](https://www.mouser.com/ProductDetail/Espressif-Systems/ESP32-WROVER-E-N16R8?qs=Li%2BoUPsLEnsfUZ%2By2eNF6g%3D%3D) ·
[LCSC, ~$4.25](https://www.lcsc.com/product-detail/C529589.html) — all ✅.

**Stop here until it boots and shows the self-test.** Everything below assumes
it does.

---

## 2. Second order: sound and controls (~£20)

| Part | Where | ~Price |
|---|---|---|
| **PCM5102A** I²S DAC board | eBay / AliExpress — search "PCM5102A DAC module" (category link ⚠️) | £5 |
| **EC11 rotary encoder** with push, 6 mm D-shaft | eBay / any component supplier | £2 |
| **Tactile switches, 6×6 mm, 9–13 mm stem** ×6 | eBay — search "6x6x13 tactile switch" | £3 |
| Resistor assortment (needs 1 k, 2.2 k, 4.7 k, 10 k, 18 k) | any starter kit covers it | £5 |
| 3.5 mm panel-mount sockets ×2 | any | £4 |

---

## 3. Third order: the car side — **from your car's own file**

```sh
python3 tools/deckctl.py fit s2000 ap1
```

**This section used to list part numbers per car and that is how it went wrong.**
It recommended an **InCarTec 29-629 "Honda S2000 steering-wheel audio control
interface"** — a real part, listed under the S2000 by name, at **£59.99**. The
S2000 has no steering-wheel controls. Not audio, not cruise, no buttons on the
wheel at all, in any market or trim. So that was £60 for an interface box with
nothing to interface to, recommended by this file, contradicting
[VEHICLES.md](VEHICLES.md) two clicks away.

Retailers list these interfaces per *vehicle family* — the "& ISO cable" half is
the part that is actually useful — and a list of SKUs maintained by hand in a
second place drifts from the data until it says something like that.

So: **what your car needs comes from `vehicles/`**, which is one file per
generation and the only place it is written down. This page now says where to
buy the *categories*, and how much they should cost.

| What | Where | ~Price |
|---|---|---|
| **Harness adapter** — your car's connector to ISO 10487 | [Dynamic Sounds, by vehicle](https://www.dynamicsounds.co.uk/vehicles) ✅ · [InCarTec](https://incartec.co.uk) ✅ · eBay by search term | £6–15 |
| **Fascia adapter / surround** | same two ✅ — or **reuse the car's own surround**, which looks better and costs nothing | £0–15 |
| **Aerial adapter** — usually ISO/Motorola to DIN | [Connects2 CT27AA01, universal ISO→DIN](https://www.dynamicsounds.co.uk/vehicles) ✅ | £4–12 |
| **Steering-wheel interface** | **Only if your car has wheel controls.** Check `vehicles/` first — the S2000, MX-5 NA/NB and every MR2 in the list have none | £40–60 |
| Buck converter 9–18 V → 5 V ≥3 A, automotive | eBay — search "automotive buck converter 5V 3A" | £6 |
| PC817 opto-isolator + 4.7 kΩ | any component supplier | £1 |
| Inline fuse holder + fuses | Halfords / any motor factor | £3 |

For the S2000 specifically, verified on the date of this commit: a **Honda ISO
loom (CT20HD02) is £9.99** and a **universal ISO→DIN aerial adaptor (CT27AA01)
is £3.95**, both from Dynamic Sounds. That is the whole car-side bill — £14 —
because the car has no wheel controls and its own surround can be reused.

⚠️ **The S2000's aerial is an unamplified mast**, so a plain DIN adapter is
enough — no phantom power needed. Meter yours before ordering anyway;
[RADIO.md §3](RADIO.md#3-the-aerial-which-is-where-people-get-stuck) explains
what goes wrong if you get this wrong on another car.

---

## 3b. To make a sound at all — **this was missing from this page entirely**

[BUILD.md](BUILD.md#to-make-a-sound--️-the-deck-has-no-amplifier-1260) has said
for a while that the deck's output is line level and that a bare mux has no
volume control. This page never caught up, so it was possible to order
everything on it and end up with a deck that could not drive a speaker or change
how loud it was.

| Part | Where | ~Price |
|---|---|---|
| **PT2313 / TDA7313** audio processor ✅ *(strongly preferred over the 74HC4052)* | eBay / AliExpress — search "PT2313 module" or "TDA7313 module" | £2–4 |
| **TDA7850 or TDA7388 4-channel amplifier board** | eBay — search "TDA7850 amplifier board" or "XH-M180" | £12–20 |
| **…or reuse the donor's amplifier** | **£0** — every CD-era head unit contains one, already heatsinked and wired. See [REUSE.md](REUSE.md) | **free** |

The PT2313 replaces the 74HC4052 rather than joining it: same three inputs,
plus volume, tone, balance and fader over the I²C bus the tuner already uses. It
costs no pins and gives two back.

---

## 4. The case and the mechanical bits (~£90–120)

All of it is in
[BUILD.md §1](BUILD.md#the-mechanical-bits--the-ones-everybody-forgets) with
quantities. Where to get it:

| What | Where |
|---|---|
| **Donor 1-DIN head unit, dead** | See §7 below — the searches, the models, and what to check before bidding |
| DIN cage, removal keys | Usually with the donor. Otherwise Halfords or eBay |
| **M3/M2.5 screws, nylon standoffs, nyloc nuts, washers** | An assortment box from eBay or Amazon beats counting. ~£15 the lot |
| Wire, heat-shrink, crimps, JST/Dupont kit | eBay or Amazon starter kits |
| Neoprene foam strip, VHB tape, cable ties | Any hardware shop |
| **Step drill, files, crimp tool, multimeter** | Screwfix / Toolstation. The multimeter is not optional |

For anything you want a datasheet and a real invoice for rather than a
marketplace listing: **[RS Components](https://uk.rs-online.com)** and
**[Farnell](https://uk.farnell.com)** stock all of the passives, connectors and
fasteners, at higher prices and with next-day delivery.

---

## 5. Optional: calls and radio

Only once the deck works. Both are [designed but not yet driven by
firmware](CALLING.md) — buy them when you are ready to write that, not before.

| Part | Where | ~Price |
|---|---|---|
| **INMP441** I²S microphone | eBay / AliExpress — search "INMP441 module" | £4 |
| **Si4735** tuner module | eBay / AliExpress — search "Si4735 module" | £8–14 |
| 74HC4052 analogue mux | RS / Farnell / eBay | £1 |
| TSOP38238 IR receiver | RS / Farnell / eBay | £1 |

---

## 6. What I could not check

Being explicit, because a shopping list that hides its uncertainty is worse
than one that admits it:

- **Nothing here has been ordered, received, or tested.** Fit, quality and
  whether a given eBay module is what its listing claims are all unknown.
- **Marketplace links go stale fastest.** eBay item numbers disappear; the
  search terms next to them are what will still work in a year.
- **Prices exclude VAT and postage** unless stated, and were seen once.
- **The S2000 fascia adapter part number is not pinned down** — Dynamic Sounds
  and InCarTec both list S2000 kits, but I have not confirmed a specific SKU
  against a car. Ring them with the registration; they do this all day.


---

## 7. Hunting a donor, with the searches

[DONORS.md](DONORS.md) has eight routes and 42 named models, each flagged
✅ buy it / ⚠️ read the note / ❌ avoid. These are the searches that find them.
**Search terms, not item numbers** — item numbers are dead within weeks and a
dead link that once said ✅ is worse than no link.

### The words that find a cheap one

You want a unit whose *only* fault is the bit you are removing. These are the
phrases sellers use for exactly that:

```
spares or repair    ·  no CD  ·  CD stuck  ·  jammed  ·  won't eject
display dead        ·  untested  ·  no power  ·  faulty  ·  for parts
```

A working CD mechanism is the single biggest driver of price on a listing, and
it is the first thing you remove. **A jammed unit at £8 is worth exactly as much
to this build as a working one at £40.**

### Grade A — the big dot-matrix displays

The best windows in the project. Any of these, spares-or-repair, £8–20:

| Search | What you are looking for |
|---|---|
| `pioneer deh-p9000r spares` | The 1998–99 flagship. Widest window of the lot |
| `pioneer meh-p9000r` | Same face, cassette instead of CD |
| `pioneer deh-p9100r` · `deh-p6600` · `deh-p6800mp` | 2001–03, common and cheap |
| `pioneer deh-p9400mp` · `deh-p7800mp` · `deh-p9600mp` | 2003–04, the last of the big displays |
| `alpine cda-9855` · `alpine cda-9887` | Alpine's equivalent, ≈2005–07 |
| `sony cdx-m9905x` | Rarer, big display |
| `blaupunkt bremen mp76` · `blaupunkt woodstock dab53` | The German option, ≈2004–05 |

### Grade B — cassette-era, the cheapest complete route

Free to £15, and with [REUSE.md](REUSE.md) the amplifier comes with it:

| Search | Note |
|---|---|
| `blaupunkt woodstock cassette` · `blaupunkt london` · `blaupunkt toronto` | City-named Blaupunkts. Everywhere, and nobody wants them |
| `pioneer keh cassette car stereo` | The KEH- series, ≈1988–97 |
| `sony xr cassette car stereo` | The XR- series, ≈1990–98 |
| `blaupunkt bremen sqr 46` | ⚠️ The cult classic — you may pay *more* than for a grade A |
| A scrapyard, in person | Ask for anything with a cassette slot. Often free |

### Grade A — the new empty pocket, if you would rather not gut anything

| Search | Note |
|---|---|
| `single din storage pocket` · `din dash tray` · `radio blanking plate` | £6–12 new. No laser, no inverter, nothing charged. Already exactly 1-DIN |

### ❌ Do not buy these

| Avoid | Why |
|---|---|
| `DEH-P85BT` · `Clarion DXZ925` · `Kenwood KDC-716S` | Motorised or dual faceplates. The mechanism eats the depth this build has least of |
| Anything described as **smashed**, **cracked fascia**, **water damaged** | The fascia is the one part you are buying |
| Anything **2-DIN** unless you have a 2-DIN aperture | See [VEHICLES.md](VEHICLES.md) for which cars do |

### Before you bid, check these five things

The window is the only part of a donor that cannot be fixed later — everything
else is shims, rewiring and a different knob.

1. **Is the fascia intact and unmarked?** That is what you are paying for.
2. **How wide is the display window?** Compare against the drawing in
   [DONORS.md](DONORS.md) for that family. The deck needs **84 × 27 mm** for an
   SSD1322 module; "needs 3 mm" is a filing job, "needs 24 mm" is a different
   donor.
3. **Is the faceplate fixed, flip-down, or motorised?** Fixed is what you want.
4. **Does it come with the cage and the trim ring?** Often does, worth £8.
5. **Is it a VFD?** ⚠️ Prettier, and its inverter holds tens of volts on a
   capacitor after power-off. The LCD ones are the safe ones to gut.

Photographs of the **front** and the **back panel** answer four of those five.
