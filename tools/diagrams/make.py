#!/usr/bin/env python3
"""Draw the diagrams: pin map, wiring, assembly, dimensions, finished deck.

    python3 tools/diagrams/make.py [outdir]      # default docs/media

These are generated for the same reason every other picture in this repository
is generated. A hand-drawn wiring diagram is correct on the day it is drawn and
silently wrong forever after, and the person it misleads is holding a soldering
iron. The pin map in particular is read straight out of the firmware — see
pins.py — so it cannot drift from the code without the build stopping.

Five pictures, because five different questions get asked:

  pinmap      "which hole does this wire go in"
  wiring      "what connects to what, and what does not touch the ESP32"
  assembly    "what order do these go together in"
  dimensions  "will it fit, and what am I cutting"
  finished    "what am I aiming at"

⚠️ The deck has never been built. These describe an intended assembly, not a
photographed one, and they say so on their face.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pins as P                                             # noqa: E402
from svg import (Svg, AMBER, BLUE, CLIP, DIM, EDGE, GREEN,    # noqa: E402
                 HOT, INK, PANEL)

ROOT = P.ROOT

# The physical DevKitC-VE header order, top to bottom, as the board is held
# with the USB socket at the bottom. Strings are non-GPIO pins. This is the
# layout of the board you actually buy — a diagram in GPIO-number order is
# useless when you are counting header holes with a fingertip.
LEFT = ["3V3", "EN", 36, 39, 34, 35, 32, 33, 25, 26, 27, 14, 12, "GND", 13,
        9, 10, 11, "5V"]
RIGHT = ["GND", 23, 22, 1, 3, 21, "GND", 19, 18, 5, 17, 16, 4, 0, 2, 15,
         8, 7, 6]


# --------------------------------------------------------------- pin map
def pinmap(out):
    pins = P.build()
    W, H = 1180, 900
    s = Svg(W, H, "PIN MAP  ·  ESP32-WROVER-E",
            "Generated from the firmware sources. If a pin moves in the code, "
            "it moves here — see tools/diagrams/pins.py.")

    # module body
    mx, my, mw, mh = 470, 96, 240, 700
    s.rect(mx, my, mw, mh, fill=PANEL, stroke=EDGE, sw=1.5, rx=6)
    s.rect(mx + 26, my + 18, mw - 52, 190, fill="#191920", stroke=EDGE, rx=3)
    s.text(mx + mw / 2, my + 108, "WROVER-E", size=13, fill=DIM,
           anchor="middle", weight="600", spacing="0.12em")
    s.text(mx + mw / 2, my + 126, "shield", size=9, fill="#55535e",
           anchor="middle")
    s.rect(mx + 88, my + mh - 58, 64, 40, fill="#191920", stroke=EDGE, rx=3)
    s.text(mx + mw / 2, my + mh - 33, "USB", size=9, fill=DIM, anchor="middle")

    pitch = (mh - 40) / (len(LEFT) - 1)

    def row(items, side):
        for i, g in enumerate(items):
            y = my + 20 + i * pitch
            xin = mx if side == "L" else mx + mw
            xout = mx - 18 if side == "L" else mx + mw + 18
            anchor = "end" if side == "L" else "start"
            lx = xout - 8 if side == "L" else xout + 8

            if isinstance(g, str):                       # power / enable
                s.line(xin, y, xout, y, stroke="#3a3a44", sw=1)
                s.circle(xout, y, 3, fill="#3a3a44")
                s.text(lx, y + 3.5, g, size=9, fill="#6a6875", anchor=anchor)
                continue

            label, colour, why = P.describe(g, pins)
            claimed = g in pins
            bad = g in P.FORBIDDEN

            s.line(xin, y, xout, y, stroke=colour if claimed else "#2c2c35",
                   sw=1.6 if claimed else 1)
            s.circle(xout, y, 3.6 if claimed else 2.6,
                     fill=colour if claimed else "#2c2c35")

            # GPIO number always, hard against the module
            nx = xin + 10 if side == "L" else xin - 10
            s.text(nx, y + 3.5, str(g), size=9, fill="#6a6875",
                   anchor="start" if side == "L" else "end")

            if claimed:
                p = pins[g]
                s.text(lx, y + 3.5, label, size=10.5, fill=INK, anchor=anchor,
                       weight="600")
                w = len(label) * 6.3
                if p.get("alt"):
                    ax = lx - w - 10 if side == "L" else lx + w + 10
                    s.text(ax, y + 3.5, "or " + p["alt"]["label"], size=9,
                           fill=P.GROUPS[p["alt"]["group"]][1],
                           anchor=anchor, op=0.95)
            elif bad:
                s.text(lx, y + 3.5, label, size=9.5, fill=CLIP, anchor=anchor,
                       weight="600")
            elif g in P.STRAPPING:
                # Not "free". Unclaimed and unusable-as-a-button are different
                # facts, and the pin that looks free is the one somebody puts
                # a switch on.
                s.text(lx, y + 3.5, "strapping", size=9, fill="#8a7a4a",
                       anchor=anchor)
            else:
                s.text(lx, y + 3.5, "free", size=9, fill="#4a4854",
                       anchor=anchor)

            note = None
            if g in P.INPUT_ONLY:
                note = "input only, no pull-up"
            elif g in P.STRAPPING:
                note = P.STRAPPING[g]
            if note and (claimed or g in P.STRAPPING):
                bx = lx - 6 if side == "L" else lx + 6
                s.text(bx, y + 14, note, size=7.5, fill="#5f5d6b",
                       anchor=anchor)

    row(LEFT, "L")
    row(RIGHT, "R")

    # legend
    ly = H - 62
    s.text(28, ly - 16, "GROUPS", size=8.5, fill=AMBER, spacing="0.16em")
    x = 28
    for key, (name, colour) in P.GROUPS.items():
        s.circle(x + 4, ly - 3, 4, fill=colour)
        s.text(x + 14, ly, name, size=9.5, fill=DIM, mono=False)
        x += 16 + len(name) * 6.2 + 18
    s.circle(x + 4, ly - 3, 4, fill=CLIP)
    s.text(x + 14, ly, "Reserved by the module — never wire to these",
           size=9.5, fill=CLIP, mono=False)

    s.caption(28, H - 24,
              "GPIO 13/32/33 carry two labels because the tuner and the three "
              "discrete buttons want the same holes. Fit one or the other; "
              "the firmware decides at boot by probing for a button ladder.")
    return s.save(os.path.join(out, "pinmap.svg"))


# ---------------------------------------------------------------- wiring
def wiring(out):
    W, H = 1180, 872
    s = Svg(W, H, "WIRING  ·  THE WHOLE DECK",
            "Signal flow, not a schematic. The thing worth noticing is that "
            "audio never enters the ESP32.")

    def wire(x1, y1, x2, y2, colour, label=None, mid=None, dash=None):
        mx = mid if mid is not None else (x1 + x2) / 2
        s.path(f"M {x1} {y1} H {mx} V {y2} H {x2}", stroke=colour, sw=1.6,
               dash=dash)
        s.circle(x2, y2, 2.6, fill=colour)
        if label:
            s.text(mx + 6, (y1 + y2) / 2 + 3, label, size=8.5, fill=DIM)

    # ---- power, down the left
    s.box(28, 96, 190, 62, "CAR 12 V", ["ISO 10487 A4 / A7", "fused 5 A"],
          accent=CLIP)
    s.box(28, 186, 190, 62, "BUCK → 5 V 3 A",
          ["MP1584 or similar", "not a linear regulator"], accent=CLIP)
    s.box(28, 276, 190, 50, "3V3", ["the module's own LDO"], accent=CLIP)
    s.line(123, 158, 123, 186, stroke=CLIP, sw=1.6)
    s.line(123, 248, 123, 276, stroke=CLIP, sw=1.6)

    # ---- car inputs
    s.box(28, 366, 190, 78, "OPTO-ISOLATORS",
          ["PC817 ×2 — ignition A7,", "dimmer A6. NEVER a divider",
           "straight off 12 V"], accent=BLUE)
    s.box(28, 464, 190, 62, "WHEEL INTERFACE",
          ["universal box, 3.5 mm out", "learned, not decoded"], accent=BLUE)
    s.box(28, 546, 190, 62, "BUTTON LADDER",
          ["6 buttons, 6 resistors,", "one wire"], accent="#ff9d5c")

    # ---- the chip
    cx, cy, cw, ch = 430, 150, 250, 470
    s.rect(cx, cy, cw, ch, fill=PANEL, stroke=AMBER, sw=1.5, rx=6)
    s.text(cx + cw / 2, cy + 30, "ESP32-WROVER-E", size=13, fill=HOT,
           anchor="middle", weight="700", spacing="0.08em")
    s.text(cx + cw / 2, cy + 48, "original ESP32 — not S3/C3/C6", size=8.5,
           fill=DIM, anchor="middle", mono=False)
    s.text(cx + cw / 2, cy + 62, "Classic BT is the whole reason", size=8.5,
           fill=DIM, anchor="middle", mono=False)
    for i, (nm, col) in enumerate([
            ("A2DP + AVRCP   music & metadata", HOT),
            ("HFP client     calls", GREEN),
            ("core/ renderer 10 screens", AMBER),
            ("movies         from flash", AMBER),
            ("FFT analyser   13 bands", AMBER)]):
        s.rect(cx + 16, cy + 84 + i * 30, cw - 32, 24, fill="#191920",
               stroke=EDGE, rx=3)
        s.rect(cx + 16, cy + 84 + i * 30, 2.5, 24, fill=col, rx=1)
        s.text(cx + 26, cy + 100 + i * 30, nm, size=8.5, fill=INK)
    s.text(cx + cw / 2, cy + ch - 16,
           "16 MB flash  ·  PSRAM  ·  ESP-IDF v5.3", size=8, fill=DIM,
           anchor="middle")

    # ---- right-hand devices. Ordered so the mux comes *after* all three of
    # the things it selects between, because that is the order the signal
    # arrives in — a mux drawn above its own inputs reads backwards.
    # BUS is a clear channel to the right; the analogue path runs down it
    # rather than through the boxes it connects.
    BX, BW = 812, 236
    BUS = BX + BW + 40
    s.box(BX, 96, BW, 62, "PANEL",
          ["SSD1322 256×64 OLED", "or GP1294AI VFD"], accent=AMBER)
    s.box(BX, 178, BW, 62, "I²S DAC", ["PCM5102A", "line level out"],
          accent=HOT)
    s.box(BX, 260, BW, 62, "MICROPHONE",
          ["INMP441 — shares the", "DAC's clocks"], accent=HOT)
    s.box(BX, 342, BW, 62, "Si4735 TUNER",
          ["FM/AM + RDS", "0x11 or 0x63 — probed"], accent=GREEN)
    s.box(BX, 424, BW, 48, "AUX IN", ["3.5 mm, passive"], accent="#c9a0ff")
    s.box(BX, 492, BW, 68, "PT2313 AUDIO PROC",
          ["source + VOLUME + tone, I²C", "or a 74HC4052 — no volume"],
          accent="#c9a0ff")
    s.box(BX, 580, BW, 58, "AMPLIFIER  ⚠ NOT INCLUDED",
          ["TDA7850 / TDA7388 4×50 W", "its OWN fused 12 V feed"], accent=CLIP)

    # ---- wires in
    wire(218, 127, cx, 200, CLIP, "5 V", mid=330)
    wire(218, 405, cx, 300, BLUE, "GPIO 39 / 36", mid=318)
    wire(218, 495, cx, 340, BLUE, "GPIO 34", mid=346)
    wire(218, 577, cx, 380, "#ff9d5c", "GPIO 35", mid=374)

    # ---- control wires out. The label goes on two short lines immediately
    # after the chip, in the gap between it and the riser — a single long
    # label there runs straight under the device boxes, which is what the
    # first version of this diagram did.
    MID = 752
    for y1, y2, colour, bus_name, pin_list in [
            (200, 127, AMBER, "SPI", "23 18 5 19 4"),
            (248, 209, HOT, "I²S", "26 25 22"),
            (292, 291, HOT, "mic", "15"),
            (340, 373, GREEN, "I²C", "32 33 + 13"),
            (420, 526, "#c9a0ff", "I²C", "32 33")]:
        s.path(f"M {cx + cw} {y1} H {MID} V {y2} H {BX}", stroke=colour,
               sw=1.6)
        s.circle(BX, y2, 2.6, fill=colour)
        s.text(cx + cw + 10, y1 - 16, bus_name, size=8, fill=colour)
        s.text(cx + cw + 10, y1 - 5, pin_list, size=8, fill=DIM)

    # ---- the analogue path, in its own channel to the right of everything
    def bus(y_from, y_to, colour, label):
        s.path(f"M {BX + BW} {y_from} H {BUS} V {y_to} H {BX + BW}",
               stroke=colour, sw=2)
        s.circle(BX + BW, y_to, 3, fill=colour)
        s.text(BUS + 8, (y_from + y_to) / 2 + 3, label, size=8, fill=DIM)

    bus(209, 508, HOT, "line out")            # DAC   → mux ch0
    bus(373, 524, GREEN, "FM / AM")           # tuner → mux ch1
    bus(448, 540, "#c9a0ff", "aux")           # aux   → mux ch2

    # the one selected pair, out of the processor and into the amplifier
    s.path(f"M {BX + 40} 560 V 580", stroke=CLIP, sw=2.6)
    s.circle(BX + 40, 580, 3.4, fill=CLIP)
    s.text(BX + 52, 574, "one pair, selected", size=8, fill=CLIP)

    # The amplifier's own supply. Drawn straight from the car rather than
    # through the buck, because that is the mistake: four channels at 45 W is
    # tens of amps of peak current and the deck's little 3 A buck does not
    # survive being asked for it.
    s.path(f"M 218 110 H 262 V 800 H {BX + BW / 2} V 638",
           stroke=CLIP, sw=2, dash="7 4")
    s.circle(BX + BW / 2, 638, 3.4, fill=CLIP)
    s.text(272, 762, "12 V straight from the car, its OWN fuse — NOT through "
           "the 5 V buck", size=8.5, fill=CLIP)
    s.text(272, 778, "⚠ The amplifier is not part of this build. "
           "BUILD.md — 'To make a sound'.", size=8.5, fill=CLIP)

    # ---- the callout, under the chip where there is actually room
    s.rect(cx - 2, 640, 400, 100, fill="#1a1208", stroke=AMBER, sw=1, rx=5)
    s.rect(cx - 2, 640, 3, 100, fill=AMBER, rx=1.5)
    s.text(cx + 12, 662, "THE AUDIO NEVER ENTERS THE ESP32", size=10,
           fill=HOT, weight="700")
    s.caption(cx + 12, 681,
              "The tuner's analogue output goes to the mux, not to the chip,")
    s.caption(cx + 12, 696,
              "so nothing is resampled and nothing is re-encoded — the radio")
    s.caption(cx + 12, 711, "sounds like a radio rather than like a codec.")
    s.caption(cx + 12, 730,
              "The deck draws the screen. It is not in the signal path.",
              fill=AMBER)

    s.caption(28, H - 26,
              "⚠️  Never run on hardware. This is the intended wiring, drawn "
              "from the firmware's pin map — not a photograph of a working deck.",
              fill=CLIP)
    return s.save(os.path.join(out, "wiring.svg"))


# -------------------------------------------------------------- assembly
def assembly(out):
    W, H = 1180, 760
    s = Svg(W, H, "ASSEMBLY  ·  THE ORDER IT GOES TOGETHER",
            "Exploded, front-left. Each layer drops into the one behind it.")

    LAYERS = [
        ("FASCIA", "the donor's own face, or 3 mm acrylic",
         "Last on, first off. Nothing behind it should need it removed.", AMBER),
        ("DISPLAY WINDOW", "1 mm smoked acrylic, bonded",
         "Smoked, not clear — an unlit dot should look dead, not grey.", HOT),
        ("PANEL + CONTROL BOARD", "OLED/VFD, encoder, buttons",
         "Panel first: everything else is positioned relative to the glass.",
         AMBER),
        ("MAIN BOARD", "ESP32, DAC, mux, tuner",
         "Standoffs, not tape. It has to survive a dashboard in August.",
         GREEN),
        ("CHASSIS", "the gutted donor, or 1 mm folded aluminium",
         "Earth everything to one point on this, not to each other.", INK),
        ("ISO CAGE", "ISO 7736, 182 × 53 mm",
         "Goes in the car first and stays there. Tabs bent, not screwed.",
         BLUE),
    ]

    # Plates on the left, labels in a fixed column on the right with leader
    # lines. The obvious layout — a caption on each plate — does not survive
    # an exploded view: the plate in front covers the label behind it, and
    # only the topmost layer stays readable.
    x0, y0 = 74, 118
    dx, dy = 48, 74
    bw, bh = 280, 88
    skew = 48
    LX = 648                        # the label column, clear of every plate
    n = len(LAYERS)

    # `reversed` walks back-to-front — cage first — so d is depth *and* build
    # order. Drawing in this order also means each plate overlaps the one
    # behind it, which is what makes the stack read as a stack.
    for d, (name, part, note, colour) in enumerate(reversed(LAYERS)):
        px = x0 + d * dx
        py = y0 + (n - 1 - d) * dy          # cage at the bottom, fascia on top

        s.path(f"M {px} {py} L {px + bw} {py} L {px + bw - skew} {py + bh} "
               f"L {px - skew} {py + bh} Z",
               stroke=colour, sw=1.3, fill=PANEL)
        s.path(f"M {px} {py} L {px + bw} {py}", stroke=colour, sw=2.4)
        s.text(px + bw - 24, py + 26, str(d + 1), size=22, fill=colour,
               weight="700", op=0.4, anchor="middle")

        # leader from the plate's top-right corner out to the label column
        ly = py + 14
        s.path(f"M {px + bw + 6} {py + 2} L {LX - 24} {ly} H {LX - 10}",
               stroke=colour, sw=1, dash="2 3")
        s.circle(LX - 10, ly, 2.4, fill=colour)

        s.text(LX, ly + 4, f"{d + 1}.", size=11, fill=colour, weight="700")
        s.text(LX + 26, ly + 4, name, size=12, fill=INK, weight="700",
               spacing="0.06em")
        s.text(LX + 26, ly + 21, part, size=9, fill=DIM)
        s.caption(LX + 26, ly + 40, note, size=9.5, fill="#8f8b80")

    s.caption(28, H - 116,
              "Numbered in build order: the cage goes into the car first and "
              "stays there, the fascia goes on last.")
    s.caption(28, H - 98,
              "Reverse the numbers to take it apart, which you will do several "
              "times.")

    s.rect(28, H - 78, 1124, 52, fill="#1a1208", stroke=AMBER, rx=5)
    s.rect(28, H - 78, 3, 52, fill=AMBER, rx=1.5)
    s.text(44, H - 58, "THE TWO THAT BITE", size=9.5, fill=HOT, weight="700")
    s.caption(190, H - 58,
              "Depth, not width — a 1-DIN slot is 182 × 53 mm at the face and "
              "can be as little as 120 mm deep behind it. Measure the car, "
              "not the cage.")
    s.caption(190, H - 40,
              "The 8.8\" bar LCD does not fit a 1-DIN fascia: ~217 mm against "
              "180 mm. Desk use or a custom face only.")
    s.caption(44, H - 40, "⚠️  Never built.", fill=CLIP)
    return s.save(os.path.join(out, "assembly.svg"))


# ------------------------------------------------------------ dimensions
def dimensions(out):
    W, H = 1180, 620
    s = Svg(W, H, "DIMENSIONS  ·  ISO 7736 (1-DIN)",
            "What you are cutting, and what has to clear behind it.")

    def dim(x1, y1, x2, y2, text, off=0, vertical=False):
        s.line(x1, y1, x2, y2, stroke=BLUE, sw=1)
        t = 5
        if vertical:
            s.line(x1 - t, y1, x1 + t, y1, stroke=BLUE, sw=1)
            s.line(x2 - t, y2, x2 + t, y2, stroke=BLUE, sw=1)
            s.text(x1 + off, (y1 + y2) / 2 + 3, text, size=9.5, fill=BLUE)
        else:
            s.line(x1, y1 - t, x1, y1 + t, stroke=BLUE, sw=1)
            s.line(x2, y2 - t, x2, y2 + t, stroke=BLUE, sw=1)
            s.text((x1 + x2) / 2, y1 + off, text, size=9.5, fill=BLUE,
                   anchor="middle")

    # ---- front elevation, 2 px per mm
    sc = 2.0
    fx, fy = 120, 140
    fw, fh = 182 * sc, 53 * sc
    s.text(fx, fy - 22, "FRONT", size=9, fill=AMBER, spacing="0.16em")
    s.rect(fx, fy, fw, fh, fill=PANEL, stroke=INK, sw=1.5, rx=3)
    # the glass
    gx, gy, gw, gh = fx + 22, fy + 16, 256 * 0.62, 64 * 0.62
    s.rect(gx, gy, gw, gh, fill="#0b0b0e", stroke=AMBER, sw=1)
    s.text(gx + gw / 2, gy + gh / 2 + 3.5, "256 × 64", size=8, fill=AMBER,
           anchor="middle")
    # encoder + buttons
    s.circle(fx + fw - 34, fy + fh / 2, 13, fill="#191920", stroke=INK, sw=1.2)
    s.circle(fx + fw - 34, fy + fh / 2, 3, fill=DIM)
    for i in range(3):
        s.rect(gx + i * 26, fy + fh - 18, 18, 8, fill="#191920", stroke=EDGE,
               rx=2)

    dim(fx, fy + fh + 30, fx + fw, fy + fh + 30, "182 mm", off=16)
    dim(fx - 30, fy, fx - 30, fy + fh, "53 mm", off=-58, vertical=True)

    # ---- side elevation
    px, py = 620, 140
    pw, ph = 180 * sc * 0.9, 53 * sc
    s.text(px, py - 22, "SIDE", size=9, fill=AMBER, spacing="0.16em")
    s.rect(px, py, pw, ph, fill=PANEL, stroke=INK, sw=1.5, rx=3)
    s.rect(px, py, 10, ph, fill=AMBER, rx=2)
    s.text(px + 16, py + 18, "face", size=8, fill=DIM)
    s.rect(px + 40, py + 14, 96, ph - 28, fill="#191920", stroke=EDGE, rx=2)
    s.text(px + 88, py + ph / 2 + 3, "boards", size=8, fill=DIM,
           anchor="middle")
    s.rect(px + pw - 52, py + 18, 44, ph - 36, fill="#191920", stroke=EDGE,
           rx=2)
    s.text(px + pw - 30, py + ph / 2 + 3, "ISO", size=8, fill=DIM,
           anchor="middle")
    dim(px, py + ph + 30, px + pw, py + ph + 30, "≈160 mm deep", off=16)
    s.caption(px, py + ph + 66,
              "Plus 30–40 mm behind for the ISO plugs and the loom's bend "
              "radius.")
    s.caption(px, py + ph + 82,
              "Some cars give you 120 mm total. Measure before you build.")

    # ---- the numbers table
    ty = 400
    s.text(120, ty - 14, "THE NUMBERS THAT MATTER", size=9, fill=AMBER,
           spacing="0.16em")
    rows = [
        ("Aperture (ISO 7736)", "182 × 53 mm", "the hole in the dash"),
        ("Cage", "slides into the aperture", "tabs bent outward, not screwed"),
        ("Chassis depth", "≈160 mm", "plus 30–40 mm for plugs and loom"),
        ("SSD1322 panel", "256 × 64 px, ~76 × 19 mm active", "16 greys"),
        ("GP1294AI VFD", "256 × 48 px", "1-bit — no shading, real glass"),
        ("Fascia thickness", "3 mm", "acrylic, or the donor's own face"),
        ("Window", "1 mm smoked acrylic", "not clear — dead dots must look dead"),
    ]
    for i, (a, b, c) in enumerate(rows):
        y = ty + 12 + i * 26
        s.rect(120, y - 15, 940, 24, fill=PANEL if i % 2 == 0 else "none",
               rx=3)
        s.text(132, y, a, size=10, fill=INK)
        s.text(430, y, b, size=10, fill=HOT)
        s.caption(660, y, c, size=9.5)

    s.caption(120, H - 26,
              "⚠️  Verified against the standard and the panel datasheets. "
              "Nothing here has been cut, fitted, or measured in a real car.",
              fill=CLIP)
    return s.save(os.path.join(out, "dimensions.svg"))


# -------------------------------------------------------------- finished
def finished(out):
    W, H = 1180, 560
    s = Svg(W, H, "WHAT YOU ARE AIMING AT",
            "The deck in the slot, lit, playing. Drawn to the dimensions "
            "above.")

    # dash surround
    s.rect(150, 120, 880, 300, fill="#0d0d11", stroke=EDGE, rx=10)
    s.caption(160, 112, "dashboard aperture")

    sc = 3.6
    fw, fh = 182 * sc * 0.72, 53 * sc * 0.72
    fx, fy = 150 + (880 - fw) / 2, 120 + (300 - fh) / 2

    # faceplate
    s.rect(fx, fy, fw, fh, fill="#141419", stroke="#2e2e38", sw=2, rx=5)
    s.rect(fx + 3, fy + 3, fw - 6, fh - 6, fill="#0e0e12", rx=4)

    # The glass, lit. The panel is 256×64 and the VU screen spends the top
    # rows on the track and the rest on the bars — so the text gets its own
    # strip here rather than being laid over the spectrum, which is both
    # unreadable and not what core/ draws.
    gw, gh = 256 * 1.30, 64 * 1.30
    gx, gy = fx + 24, fy + 26
    s.rect(gx - 4, gy - 4, gw + 8, gh + 8, fill="#000", stroke="#26262f", rx=3)

    hdr = gh * 0.26
    s.text(gx + 5, gy + hdr - 6, "NIGHTCALL", size=10, fill=HOT, weight="700")
    s.text(gx + gw - 5, gy + hdr - 6, "KAVINSKY", size=9, fill=AMBER,
           anchor="end", op=0.75)

    import math
    n, floor_y = 13, gy + gh - 5
    span = floor_y - (gy + hdr + 5)
    for i in range(n):
        bw = gw / n - 4
        v = (math.sin(i * 1.7) * 0.5 + 0.5) ** 1.6
        bh = 6 + v * (span - 10)
        bx = gx + i * (gw / n) + 2
        s.rect(bx, floor_y - bh, bw, bh, fill=AMBER, rx=0.5, op=0.9)
        s.rect(bx, floor_y - bh - 4, bw, 2, fill=HOT, rx=0.5)   # peak hold
    s.rect(gx - 14, gy - 14, gw + 28, gh + 28, fill=AMBER, rx=8, op=0.06)

    # encoder, clear of the glass
    ex, ey = fx + fw - 46, fy + fh / 2
    s.circle(ex, ey, 24, fill="#191920", stroke="#33333d", sw=2)
    s.circle(ex, ey, 16, fill="#101014", stroke="#2a2a33", sw=1)
    s.line(ex, ey - 14, ex, ey - 7, stroke=DIM, sw=2)

    # buttons, on the strip below the glass
    for i, nm in enumerate(["SRC", "DISP", "ART"]):
        bx = gx + i * 58
        by = gy + gh + 12
        s.rect(bx, by, 50, 13, fill="#191920", stroke="#2c2c35", rx=2.5)
        s.text(bx + 25, by + 9, nm, size=7, fill=DIM, anchor="middle")

    # callouts, outside the faceplate so nothing sits on the artwork
    s.line(ex, fy + fh + 4, ex, fy + fh + 22, stroke=EDGE, sw=1)
    s.caption(ex, fy + fh + 36, "volume · push to change screen",
              anchor="middle")
    s.line(gx + 75, gy + gh + 25, gx + 75, fy + fh + 22, stroke=EDGE, sw=1)
    s.caption(gx + 75, fy + fh + 36, "or six, on a resistor ladder",
              anchor="middle")

    # badge
    s.text(fx + 14, fy + 16, "DECK·7710", size=8, fill="#4a4854",
           spacing="0.14em")

    s.caption(150, 466,
              "One hue, four brightness levels, and a fifth reserved for "
              "clipping. No colour, because the glass has none —")
    s.caption(150, 484,
              "which is the constraint every screen in core/ is designed "
              "around rather than fighting.")
    s.caption(150, 516,
              "⚠️  A drawing to the published dimensions, not a photograph. "
              "No deck has been built.", fill=CLIP)
    return s.save(os.path.join(out, "finished.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    for fn in (pinmap, wiring, assembly, dimensions, finished):
        path = fn(out)
        kb = os.path.getsize(path) / 1024
        print(f"  {os.path.relpath(path, ROOT):<34} {kb:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
