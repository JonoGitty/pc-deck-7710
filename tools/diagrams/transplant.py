#!/usr/bin/env python3
"""Two drawings for the fiddly half: aligning the panel, and rewiring buttons.

    python3 tools/diagrams/transplant.py [outdir]

These cover the parts of the build where the instruction "fit the panel" and
"reuse the buttons" hide a day of work each, and where the mistake is not
recoverable because it is a hole in a fascia.

**Panel alignment.** The one that catches everybody: the module's PCB is
100.5 × 33.5 mm and its lit area is only 76.8 × 19.2 mm, so the board is far
bigger than the hole and the lit area is NOT centred on it. Mark the window
from the glass and the deck looks bought; mark it from the PCB and it is
several millimetres out, permanently.

**The button ladder.** A donor's front panel is a scanned matrix, and the
deck reads one analogue pin. The drawing shows what the rewire actually is —
break the matrix, common one side of every switch, and put each switch's other
leg to ground through its own resistor.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svg import (Svg, AMBER, BLUE, CLIP, DIM, EDGE, GREEN,      # noqa: E402
                 HOT, INK, PANEL)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The 3.12" SSD1322 module, from the listings this project recommends.
PCB_W, PCB_H = 100.5, 33.5
LIT_W, LIT_H = 76.8, 19.2
WIN_W, WIN_H = 84.0, 27.0

LADDER = [("SRC", "0 R", 0), ("DISP", "1 k", 300), ("BAND", "2k2", 595),
          ("ART", "4k7", 1055), ("LYRICS", "10 k", 1650), ("DEMO", "18 k", 2121)]


def panel_alignment(out):
    W, H = 1060, 560
    s = Svg(W, H, "MOVING THE SCREEN",
            "The module is bigger than the hole, and its lit area is not "
            "centred on it. Mark from the glass.")

    sc = 5.4
    px = (W - PCB_W * sc) / 2
    py = 132

    # the module PCB
    s.rect(px, py, PCB_W * sc, PCB_H * sc, fill="#14321f", stroke="#2f6b46",
           sw=1.5, rx=3)
    s.caption(px, py - 12, "the SSD1322 module — PCB 100.5 × 33.5 mm")

    # the lit area. Deliberately drawn OFF-CENTRE, because on the real
    # modules it is: the driver and the FFC take one end of the board.
    lit_x = px + (PCB_W - LIT_W) * sc / 2 - 4 * sc
    lit_y = py + (PCB_H - LIT_H) * sc / 2
    s.rect(lit_x, lit_y, LIT_W * sc, LIT_H * sc, fill="#000", stroke=AMBER,
           sw=2)
    s.text(lit_x + LIT_W * sc / 2, lit_y + LIT_H * sc / 2 + 4,
           "lit area  76.8 × 19.2", size=11, fill=AMBER, anchor="middle")

    # the driver end
    s.rect(px + PCB_W * sc - 14 * sc, py + 3 * sc, 11 * sc, 27 * sc,
           fill="#0f2417", stroke="#2f6b46", sw=1, rx=2)
    s.text(px + PCB_W * sc - 8.5 * sc, py + 17 * sc, "FFC", size=8, fill=DIM,
           anchor="middle")

    # centre lines, which is the whole point
    pcb_cx = px + PCB_W * sc / 2
    lit_cx = lit_x + LIT_W * sc / 2
    s.line(pcb_cx, py - 4, pcb_cx, py + PCB_H * sc + 30, stroke=CLIP, sw=1,
           dash="4 4")
    s.text(pcb_cx, py + PCB_H * sc + 44, "centre of the PCB", size=8.5,
           fill=CLIP, anchor="middle")
    s.line(lit_cx, py - 22, lit_cx, py + PCB_H * sc + 4, stroke=AMBER, sw=1,
           dash="4 4")
    s.text(lit_cx, py - 30, "centre of the GLASS — mark from this", size=8.5,
           fill=AMBER, anchor="middle")

    # the offset, called out
    s.line(lit_cx, py + PCB_H * sc + 16, pcb_cx, py + PCB_H * sc + 16,
           stroke=HOT, sw=1.6)
    s.text((lit_cx + pcb_cx) / 2, py + PCB_H * sc + 12,
           "this offset ⚠️ measure yours", size=8, fill=HOT, anchor="middle")

    # the window, over the top
    wx = lit_x + (LIT_W - WIN_W) * sc / 2
    wy = lit_y + (LIT_H - WIN_H) * sc / 2
    s.rect(wx, wy, WIN_W * sc, WIN_H * sc, fill="none", stroke=INK, sw=1.6,
           dash="6 4")
    s.text(wx + WIN_W * sc / 2, wy - 10,
           "window 84 × 27 — a 4 mm border all round the glass", size=9,
           fill=INK, anchor="middle")

    y = 348
    s.rect(28, y, W - 56, 150, fill="#0f0f14", stroke=EDGE, rx=5)
    s.rect(28, y, 3, 150, fill=AMBER, rx=1.5)
    s.text(44, y + 22, "THE FOUR THINGS THAT DECIDE THIS", size=9, fill=HOT,
           spacing="0.14em")
    for i, t in enumerate([
            "1.  Mark the window from the LIT AREA, never from the PCB "
            "outline and never from a measurement. Hold the module against "
            "the fascia, power it, and scribe round what glows.",
            "2.  The panel sits AT the fascia plane, not behind it. Recess a "
            "dot-matrix display and you are looking down a tunnel — contrast "
            "and viewing angle both go.",
            "3.  The PCB is 100.5 mm wide against a 182 mm fascia, so it "
            "clears easily side to side. It is the 33.5 mm height against a "
            "53 mm face that gets tight once the bezel is on.",
            "4.  Note which end the FFC leaves from and orient the module so "
            "it exits towards the main board, with a service loop. A ribbon "
            "pulled taut tears at the connector, not in the middle."]):
        s.caption(44, y + 46 + i * 26, t, size=9.5)

    s.caption(28, H - 22,
              "⚠️  Module dimensions are from the listings this project "
              "recommends; the lit area's offset within the PCB varies by "
              "supplier. Measure the one you bought.", fill=CLIP)
    return s.save(os.path.join(out, "transplant-panel.svg"))


def button_ladder(out):
    W, H = 1060, 660
    s = Svg(W, H, "MOVING THE BUTTONS",
            "A donor's panel is a scanned matrix. The deck reads one analogue "
            "pin. This is the rewire.")

    # ---- left: what the donor gives you
    s.box(40, 110, 300, 190, "WHAT THE DONOR HAS",
          ["a scanned matrix on a flexi", "rows × columns, decoded by a chip",
           "you are binning the chip"], accent=DIM)
    for r in range(3):
        for c in range(3):
            s.rect(70 + c * 44, 190 + r * 34, 30, 22, fill="#191920",
                   stroke=EDGE, rx=2)
    for r in range(3):
        s.line(60, 201 + r * 34, 210, 201 + r * 34, stroke="#4a4854", sw=1)
    for c in range(3):
        s.line(85 + c * 44, 180, 85 + c * 44, 292, stroke="#4a4854", sw=1)
    s.caption(230, 205, "3 rows")
    s.caption(230, 222, "× 3 columns")
    s.caption(230, 246, "= 9 switches,")
    s.caption(230, 262, "6 wires, and a")
    s.caption(230, 278, "decoder you do")
    s.caption(230, 294, "not have")

    # arrow
    s.path("M 360 200 H 420", stroke=AMBER, sw=2.4)
    s.path("M 410 193 L 420 200 L 410 207", stroke=AMBER, sw=2.4)
    s.text(390, 188, "break it", size=8.5, fill=AMBER, anchor="middle")

    # ---- right: the ladder
    lx = 470
    s.text(lx, 128, "WHAT THE DECK WANTS — ONE WIRE", size=9.5, fill=HOT,
           spacing="0.12em")
    s.text(lx, 148, "3V3", size=9, fill=CLIP)
    s.rect(lx + 34, 140, 46, 12, fill="#191920", stroke=CLIP, rx=2)
    s.text(lx + 57, 149, "10k", size=8, fill=INK, anchor="middle")
    s.line(lx + 80, 146, lx + 150, 146, stroke=CLIP, sw=1.6)
    s.circle(lx + 150, 146, 3.4, fill=AMBER)
    s.text(lx + 160, 150, "GPIO 35  (ADC1_CH7)", size=9, fill=AMBER,
           weight="600")
    s.text(lx + 160, 163, "this node is the old matrix's COMMON", size=8,
           fill=DIM)

    s.line(lx + 150, 146, lx + 150, 178 + len(LADDER) * 40, stroke=CLIP,
           sw=1.6)
    for i, (name, res, mv) in enumerate(LADDER):
        y = 200 + i * 40
        s.line(lx + 150, y, lx + 190, y, stroke=INK, sw=1.2)
        s.rect(lx + 190, y - 9, 54, 18, fill="#191920", stroke=EDGE, rx=2)
        s.text(lx + 217, y + 4, name, size=8, fill=INK, anchor="middle")
        s.text(lx + 250, y + 4, "⏻", size=8, fill=DIM)
        s.rect(lx + 268, y - 7, 42, 14, fill="#191920", stroke=AMBER, rx=2)
        s.text(lx + 289, y + 3.5, res, size=8, fill=HOT, anchor="middle")
        s.line(lx + 310, y, lx + 350, y, stroke=INK, sw=1.2)
        s.circle(lx + 350, y, 2.6, fill="#4a4854")
        s.text(lx + 362, y + 4, f"{mv} mV", size=8, fill=DIM)
    gy = 200 + (len(LADDER) - 1) * 40
    s.line(lx + 350, 200, lx + 350, gy, stroke="#4a4854", sw=1.4)
    s.line(lx + 336, gy + 14, lx + 364, gy + 14, stroke="#4a4854", sw=2)
    s.line(lx + 342, gy + 19, lx + 358, gy + 19, stroke="#4a4854", sw=2)
    s.text(lx + 350, gy + 34, "GND", size=8, fill=DIM, anchor="middle")

    y = H - 176
    s.rect(28, y, W - 56, 134, fill="#0f0f14", stroke=EDGE, rx=5)
    s.rect(28, y, 3, 134, fill=AMBER, rx=1.5)
    s.text(44, y + 22, "TWO KINDS OF DONOR PANEL, AND THEY ARE NOT THE SAME "
           "JOB", size=9, fill=HOT, spacing="0.12em")
    s.text(44, y + 46, "Discrete tactile switches on a PCB", size=9.5,
           fill=GREEN, weight="600", mono=False)
    s.caption(268, y + 46,
              "— the easy case. Cut the board free, cut the matrix traces, "
              "and wire each switch: one leg")
    s.caption(268, y + 60,
              "to the common node, the other through its resistor to ground.")
    s.text(44, y + 82, "Carbon pads on a flexi", size=9.5, fill=HOT,
           weight="600", mono=False)
    s.caption(200, y + 82,
              "— rubber caps pressing onto interdigitated traces. Same "
              "electrical job, much fiddlier:")
    s.caption(200, y + 96,
              "the traces are fine-pitch and they melt. Practise on a spare "
              "corner of the flexi first.")
    s.caption(44, y + 118,
              "Either way the resistors can live on your own board rather "
              "than on the fascia — only the switch wires have to cross.",
              fill=AMBER)
    return s.save(os.path.join(out, "transplant-buttons.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    for fn in (panel_alignment, button_ladder):
        p = fn(out)
        print(f"  {os.path.relpath(p, ROOT):<38} "
              f"{os.path.getsize(p) / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
