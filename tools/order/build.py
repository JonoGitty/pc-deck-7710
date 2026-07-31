#!/usr/bin/env python3
"""The exact order list, for one set of choices.

    python3 tools/order/build.py                       # the recommended build
    python3 tools/order/build.py --radio --panel vfd
    python3 tools/order/build.py --amp buy --donor pocket

WHY THIS IS GENERATED

[BUYING.md](../../docs/BUYING.md) is the catalogue: everything, with the
alternatives, and the reasoning. That is the right shape for deciding and the
wrong shape for standing in a kitchen with a card in your hand, because half of
it does not apply to the build you actually chose.

So this takes the four decisions that change what you buy — which panel, radio
or not, buy the amplifier or reuse the donor's, and which donor route — and
prints only the things that survive them, in the order to order them.

It is generated rather than written for the same reason the pictures are: a
hand-kept order list is a third copy of the parts table, and the third copy is
the one that quietly stops matching. `tools/verify/test_buying.py` checks that
every part here is also findable in BUYING.md.

THE ONE RULE THAT IS NOT ABOUT MONEY

Order the bench parts, and nothing else, first. **The firmware has never run on
hardware.** Everything up to "it lights up on a desk" costs about £32 and
carries no risk; everything after it assumes that worked. Buying a donor first
means owning a fascia and not knowing whether the thing that goes behind it
runs at all.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------- the parts
# `when` is a predicate over the choices. One table, so a part cannot appear in
# one build and be forgotten in another.
#
# Prices are ⚠️ the ones in BUYING.md, seen once, excluding postage. They are
# here to tell you the shape of the bill, not to be correct to the penny.
PARTS = [
 # -- stage 1: it lights up on a desk ---------------------------------------
 dict(stage="bench", qty=1, name="ESP32-WROVER-E dev board, 8 or 16 MB flash",
      price=(9, 14), find="DigiKey ESP32-DEVKITC-VE ($11, WROVER-E, 8 MB "
      "flash + 8 MB PSRAM, in stock) — or eBay/AliExpress “ESP32 WROVER 16MB”",
      why="⚠️ The ORIGINAL ESP32. Not S3, C3 or C6 — they have no Bluetooth "
          "Classic, so no A2DP, so no audio from a phone. WROVER for the PSRAM "
          "the framebuffers need. 8 MB builds with `--flash 8`."),
 dict(stage="bench", qty=1, name="SSD1322 OLED, 256×64, SPI, yellow",
      price=(16, 26), when=lambda c: c.panel == "oled",
      find="Tindie “3.12 inch 256x64 OLED SSD1322” ($29.95) · eBay UK "
           "265720175865 (£25.89, ⚠️ seller away until 19 Aug)",
      why="The panel the whole project is tuned for: 16 greys, so all four "
          "intensity levels survive. Module is 100.5 × 33.5 mm; only "
          "76.8 × 19.2 mm of it lights."),
 dict(stage="bench", qty=1, name="Futaba GP1294AI VFD, 256×48, assembled",
      price=(140, 180), when=lambda c: c.panel == "vfd",
      find="eBay “VFD Futaba module 256×48 DIY SPI” (~$180 assembled, with "
           "driver and 4.5–24 V in)",
      why="⚠️ The bare panel is ~$15 and you design the filament and anode "
          "supply yourself. 1-bit: everything dithers, thin bright detail "
          "turns to noise. 4.8 mm shorter than the OLED, so it clears windows "
          "the OLED cannot."),
 dict(stage="bench", qty=1, name="PCM5102A I²S DAC board", price=(5, 5),
      find="eBay / AliExpress “PCM5102A DAC module”",
      why="Line out to whatever amplifies it. The ESP32's internal DAC is "
          "8-bit and audibly bad."),
 dict(stage="bench", qty=1, name="Breadboard + jumper wires", price=(3, 3),
      find="any", why="Nothing is soldered until it works."),
 dict(stage="bench", qty=1, name="USB data cable", price=(0, 0),
      find="any — ⚠️ **not** a charge-only one",
      why="A charge-only cable is an hour of debugging a deck that is fine."),

 # -- stage 2: controls and volume ------------------------------------------
 dict(stage="sound", qty=1, name="PT2313 or TDA7313 audio processor",
      price=(2, 4), find="eBay / AliExpress “PT2313 module” or “TDA7313 module”",
      why="⚠️ **Without this the deck has no volume control at all.** A bare "
          "74HC4052 mux only selects a source. The PT2313 does source "
          "selection *plus* volume, bass, treble, balance and fader over the "
          "I²C bus — and costs no extra pins."),
 dict(stage="sound", qty=1, name="EC11 rotary encoder, with push, 6 mm D-shaft",
      price=(2, 2), find="eBay / any component supplier",
      why="Volume, and press for mode. Reuse the donor's KNOB on top of it — "
          "the original's electrical type does not matter, only its cap does."),
 dict(stage="sound", qty=6, name="Tactile switches, 6 × 6 mm, 9–13 mm stem",
      price=(3, 3), when=lambda c: c.donor in ("pocket", "none"),
      find="eBay “6x6x13 tactile switch”",
      why="Only if you are not reusing a donor's buttons."),
 dict(stage="sound", qty=1,
      name="Resistors: 1 k, 2k2, 4k7, 10 k, 18 k, plus a 10 k pull-up",
      price=(5, 5), find="any starter assortment covers it",
      why="⚠️ **The button ladder, and on your build it is not optional** — "
          "see the note below. Six buttons on one analogue pin, each landing "
          "on its own voltage."),
 dict(stage="sound", qty=2, name="3.5 mm panel-mount sockets", price=(4, 4),
      find="any", why="Aux in, and one spare. They go through the CD slot, so "
                      "no drilling."),

 # -- stage 3: the radio, if you want it ------------------------------------
 dict(stage="radio", qty=1, name="Si4735 tuner module", price=(8, 14),
      when=lambda c: c.radio,
      find="eBay / AliExpress “Si4735 module”",
      why="FM and AM with RDS. Driver written and tested against a model of "
          "the chip — AN332 timing, both I²C addresses, all five band plans."),
 dict(stage="radio", qty=1, name="DIN aerial adapter for your car", price=(4, 12),
      when=lambda c: c.radio,
      find="Connects2 CT27AA01 universal ISO→DIN (£3.95, Dynamic Sounds)",
      why="⚠️ The S2000's aerial is an unamplified mast, so a plain adapter is "
          "enough. Meter yours anyway."),

 # -- stage 4: the donor ----------------------------------------------------
 dict(stage="donor", qty=1, name="Cassette-era 1-DIN donor, dead",
      price=(0, 15), when=lambda c: c.donor == "cassette",
      find="eBay “blaupunkt woodstock cassette” / “blaupunkt london” / "
           "“blaupunkt toronto” / “pioneer keh cassette” / “sony xr cassette” "
           "— or a scrapyard, in person, often free",
      why="✅ Free amplifier inside, the cassette door closes flush so there "
          "is no hole to fill, and the best buttons in the project: "
          "mechanical, real travel, often on a PCB rather than a carbon flexi."),
 dict(stage="donor", qty=1, name="Grade-A dot-matrix 1-DIN donor, dead",
      price=(8, 20), when=lambda c: c.donor == "pioneer",
      find="eBay “pioneer deh-p9000r spares” / “deh-p9100r” / “deh-p6600” / "
           "“deh-p6800mp” — add “spares or repair”, “no CD”, “display dead”",
      why="Solid fascia (the disc loads behind a fold-down panel) and a window "
          "already 84–90 mm wide. ⚠️ Avoid the motorised P9400MP/P9600MP "
          "unless they are cheap."),
 dict(stage="donor", qty=1, name="Brand-new empty 1-DIN pocket", price=(6, 12),
      when=lambda c: c.donor == "pocket",
      find="eBay “single din storage pocket” / “din dash tray” / "
           "“radio blanking plate”",
      why="Nothing to gut, no laser, no inverter, nothing charged. ⚠️ Plastic: "
          "no chassis ground, so run a proper earth wire."),
 dict(stage="donor", qty=1, name="ISO 7736 cage + removal keys", price=(0, 8),
      find="usually comes with the donor; otherwise Halfords or eBay",
      why="Goes in the car first and stays there."),
 dict(stage="donor", qty=1,
      name="M3/M2.5 screws, nylon standoffs, nyloc nuts, washers",
      price=(15, 15), find="an assortment box from eBay or Amazon",
      why="⚠️ Nylon standoffs, not brass — brass shorts to a chassis that is "
          "also your ground. Nyloc nuts, because a car vibrates for a living."),
 dict(stage="donor", qty=1, name="Smoked acrylic, 1 mm, ~100 × 40 mm",
      price=(4, 4), find="eBay “1mm smoked acrylic sheet”",
      why="The window, bonded behind the aperture. Smoked and not clear: an "
          "unlit dot has to look dead rather than grey."),

 # -- stage 5: into the car -------------------------------------------------
 dict(stage="car", qty=1, name="TDA7850 / TDA7388 4-channel amplifier board",
      price=(12, 20), when=lambda c: c.amp == "buy",
      find="eBay “TDA7850 amplifier board” or “XH-M180”",
      why="The deck's output is line level. ⚠️ Needs its own fused 12 V feed, "
          "not the deck's 5 V buck — and one shared ground point with the "
          "ESP32 or you get alternator whine."),
 dict(stage="car", qty=0, name="…or reuse the donor's amplifier — £0",
      price=(0, 0), when=lambda c: c.amp == "reuse",
      find="it is already inside the donor, bolted to the chassis as its "
           "heatsink and wired to the ISO connector",
      why="✅ Every CD-era head unit has one. Cut the four inputs free of the "
          "dead preamp and inject the deck's line out. ⚠️ Tie the ST-BY and "
          "MUTE pins to their enable level or it stays silent and you conclude "
          "the chip is dead. See REUSE.md."),
 dict(stage="car", qty=1, name="Honda ISO loom (Connects2 CT20HD02)",
      price=(10, 10), when=lambda c: c.car == "s2000",
      find="Dynamic Sounds, Honda S2000 — £9.99",
      why="Honda's own multi-pin connector to ISO 10487. ⚠️ Meter A4 and A7 "
          "before connecting: the connector is standard, the pinout is not."),
 dict(stage="car", qty=1, name="Buck converter 9–18 V → 5 V, ≥3 A, automotive",
      price=(6, 6), find="eBay “automotive buck converter 5V 3A”",
      why="The car's 12 V rail is a hostile place."),
 dict(stage="car", qty=1, name="PC817 opto-isolator + 4.7 kΩ", price=(1, 1),
      find="any component supplier",
      why="Ignition sense. It does not go straight to a GPIO — a load dump "
          "does not respect a 3.3 V input."),
 dict(stage="car", qty=1, name="Inline fuse holder + fuses", price=(3, 3),
      find="Halfords / any motor factor", why="Not optional."),
 dict(stage="car", qty=1, name="Multimeter, if you do not own one",
      price=(0, 15), find="Screwfix / Toolstation",
      why="⚠️ The one tool on this list that is genuinely not optional."),
]

STAGES = [
    ("bench", "1 · The bench deck — order this and NOTHING else first",
     "It plays music from your phone on a desk. Every risk in this project "
     "is concentrated in whether this works, and it costs about £32 to find "
     "out."),
    ("sound", "2 · Controls and volume",
     "Order with stage 1 or straight after it — none of it is wasted whatever "
     "happens next."),
    ("radio", "3 · The radio",
     "Only if you want FM/AM. The firmware treats an absent tuner as a "
     "perfectly normal build."),
    ("donor", "4 · The donor and the mechanical bits",
     "AFTER the bench deck lights up. Not before."),
    ("car", "5 · Into the car",
     "⚠️ Read SAFETY.md before this stage, not after it."),
]


def render(c):
    o = []
    w = o.append
    w("# Your order list\n")
    w("**Generated** by `tools/order/build.py` from the choices below. "
      "Rerun it with different flags and you get a different list — the "
      "catalogue with all the alternatives and the reasoning is "
      "[BUYING.md](BUYING.md).\n")

    w("| Decision | This list assumes |")
    w("|---|---|")
    panel = ("SSD1322 OLED 256×64" if c.panel == "oled"
             else "Futaba GP1294AI VFD 256×48")
    radio = "Si4735 FM/AM" if c.radio else "none — Bluetooth only for now"
    amp = "buy a TDA7850 board" if c.amp == "buy" else "reuse the donor's"
    donor = {"cassette": "cassette-era 1-DIN",
             "pioneer": "grade-A dot-matrix 1-DIN",
             "pocket": "brand-new empty pocket",
             "none": "none — fold your own"}[c.donor]
    car = ("Honda S2000 (AP1 or AP2 — no difference)" if c.car == "s2000"
           else c.car)
    w(f"| Panel | **{panel}** |")
    w(f"| Radio | **{radio}** |")
    w(f"| Amplifier | **{amp}** |")
    w(f"| Donor | **{donor}** |")
    w(f"| Car | **{car}** |")
    w("")

    w("> ### ⚠️ Order stage 1 and nothing else, first\n>\n"
      "> **The firmware has never run on hardware.** Everything up to *it "
      "lights up on a desk* is about £32 and risks nothing but your time. "
      "Everything after it assumes that worked. Buying a donor first means "
      "owning a fascia and not knowing whether the thing that goes behind it "
      "runs at all.\n")

    total_lo = total_hi = 0
    for key, title, blurb in STAGES:
        rows = [p for p in PARTS
                if p["stage"] == key and p.get("when", lambda _c: True)(c)]
        if not rows:
            continue
        w(f"---\n\n## {title}\n")
        w(f"{blurb}\n")
        lo = sum(p["price"][0] for p in rows)
        hi = sum(p["price"][1] for p in rows)
        total_lo += lo
        total_hi += hi
        w("| | Part | ~£ | Where |")
        w("|---|---|---|---|")
        for p in rows:
            q = f"{p['qty']}×" if p["qty"] else "—"
            cost = ("—" if p["price"] == (0, 0)
                    else (f"{p['price'][0]}" if p["price"][0] == p["price"][1]
                          else f"{p['price'][0]}–{p['price'][1]}"))
            w(f"| {q} | **{p['name']}** | {cost} | {p['find']} |")
        w("")
        for p in rows:
            w(f"- **{p['name']}** — {p['why']}")
        w("")
        w(f"**Stage total: £{lo}–{hi}**\n")

    w("---\n")
    w(f"## The whole bill: £{total_lo}–{total_hi}\n")
    w("Excluding postage, and every price was seen once. "
      "See [BUYING.md §6](BUYING.md) for what could not be checked.\n")
    return "\n".join(o) + "\n"


def consequences(c):
    """The things that follow from the choices and would otherwise be found
    out with a soldering iron in hand."""
    out = []
    if not c.radio:
        out.append((
            "No radio does NOT mean you can use discrete buttons",
            "The three discrete button pins are the same three pins as the "
            "I²C bus and the tuner's reset: **GPIO 33 is SRC and SCL, GPIO 32 "
            "is DISP and SDA, GPIO 13 is ART and the tuner reset.** So wiring "
            "buttons one-per-pin takes the I²C bus away — and the PT2313 lives "
            "on that bus. Discrete buttons therefore mean **no volume "
            "control**. Use the resistor ladder on GPIO 35 instead; it is one "
            "wire for all six buttons and it leaves I²C alone. The firmware "
            "probes for the ladder at boot and tells you which it found."))
    if c.donor == "cassette":
        out.append((
            "Your donor's buttons are the easy case",
            "Cassette-era units usually put their switches on a proper PCB "
            "rather than carbon pads on a flexi — so the ladder rewire is cut "
            "the traces, common one side of every switch, and take the other "
            "leg to ground through its own resistor. You never have to work "
            "out the original scanning order."))
        out.append((
            "And the aperture problem solves itself",
            "The cassette door is hinged and closes flush, so there is no hole "
            "to fill. Either leave it shut and cut your window elsewhere, or "
            "take the door off and use its aperture — it is wide, flat and "
            "square-cornered, which makes it the best window in the project."))
    if c.amp == "reuse":
        out.append((
            "⚠️ The amplifier reuse has one step people fail on",
            "The old microcontroller drove the amp IC's `ST-BY` and `MUTE` "
            "pins. With it gone they float, the amplifier stays muted, and you "
            "conclude the chip is dead and buy a board. Tie both to their "
            "enable level through the resistor the datasheet specifies. If it "
            "does not work you have lost an evening and buy the £12–20 board "
            "you were going to buy anyway."))
    if c.panel == "oled":
        out.append((
            "The window is marked from the glass, not the board",
            "The SSD1322 module is 100.5 × 33.5 mm and only 76.8 × 19.2 mm of "
            "it lights, and the lit area is **not centred** on the PCB. Hold "
            "the module against the fascia, power it, and scribe round what "
            "glows. Mark it from the board outline and it is permanently a few "
            "millimetres out."))
    return out


def main():
    ap = argparse.ArgumentParser(description="The exact order list.")
    ap.add_argument("--panel", choices=("oled", "vfd"), default="oled")
    ap.add_argument("--radio", action="store_true",
                    help="include the Si4735 tuner")
    ap.add_argument("--amp", choices=("reuse", "buy"), default="reuse")
    ap.add_argument("--donor",
                    choices=("cassette", "pioneer", "pocket", "none"),
                    default="cassette")
    ap.add_argument("--car", default="s2000")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "docs",
                                                        "ORDER.md"))
    c = ap.parse_args()

    body = render(c)
    cons = consequences(c)
    if cons:
        body += "\n---\n\n## What these choices mean, before you solder\n\n"
        for head, text in cons:
            body += f"### {head}\n\n{text}\n\n"
    body += ("---\n\n⚠️ **Nothing in this project has been built and the "
             "firmware has never run on hardware.** This is a list of what to "
             "buy to find out, in the order that finds out cheapest.\n")

    with open(c.out, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"  {os.path.relpath(c.out, ROOT):<28} "
          f"panel={c.panel} radio={int(c.radio)} amp={c.amp} donor={c.donor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
