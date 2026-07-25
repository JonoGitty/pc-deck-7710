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
| Breadboard, jumper wires | any | £3 |
| USB data cable | any — **not a charge-only one** | — |

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

## 3. Third order: the car side — **S2000-specific**

This is the one to order early, because it ships from specialist retailers
rather than next-day.

| Part | Where | Price |
|---|---|---|
| **InCarTec 29-629** — S2000 1999–2009 steering-wheel interface **and ISO cable in one** | [InCarTec direct](https://incartec.co.uk/products/Honda) ✅ | **£32.49 + VAT (£38.99)** ✅ |
| **Single-DIN fascia adapter** for S2000 | [Dynamic Sounds — Honda S2000 parts](https://www.dynamicsounds.co.uk/vehicles/Honda/S2000) ✅ · [InCarTec Honda](https://incartec.co.uk/products/Honda) ✅ | £8–15 |
| ISO harness adapter (if not using the 29-629's) | [eBay UK, Honda HD-102 loom](https://www.ebay.co.uk/p/1052490355) ✅ | £6 |
| DIN aerial adapter | Dynamic Sounds / InCarTec, same pages | £6–12 |
| Buck converter 9–18 V → 5 V ≥3 A, automotive | eBay — search "automotive buck converter 5V 3A" | £6 |
| PC817 opto-isolator + 4.7 kΩ | any component supplier | £1 |
| Inline fuse holder + fuses | Halfords / any motor factor | £3 |

**The 29-629 replaces two lines of the BOM**, since it carries the ISO cable as
well as the wheel interface. Buy it and skip the separate harness adapter.

⚠️ **The S2000's aerial is an unamplified mast**, so a plain DIN adapter is
enough — no phantom power needed. Meter yours before ordering anyway;
[RADIO.md §3](RADIO.md#3-the-aerial-which-is-where-people-get-stuck) explains
what goes wrong if you get this wrong on another car.

---

## 4. The case and the mechanical bits (~£90–120)

All of it is in
[BUILD.md §1](BUILD.md#the-mechanical-bits--the-ones-everybody-forgets) with
quantities. Where to get it:

| What | Where |
|---|---|
| **Donor 1-DIN head unit, dead** | eBay — search "faulty car stereo single din spares repairs". £10–25. Wanted: intact chassis and fascia. Smashed is no good |
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
