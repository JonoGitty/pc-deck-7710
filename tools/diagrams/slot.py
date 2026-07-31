#!/usr/bin/env python3
"""What to do with the hole the CD mechanism came out of.

    python3 tools/diagrams/slot.py [outdir]

The question this answers is one everybody asks and nobody can answer from a
list: the mechanism is out, there is a letterbox across the front of the fascia,
and it is not obvious whether that is a problem or an opportunity.

It is an opportunity, and the reason is a coincidence of dimensions that only
becomes obvious when the two are drawn to the same scale:

    a CD slot        ~125 × 12 mm     because a CD is 120 mm across
    the deck's window   84 × 27 mm     because a 256×64 panel is 76.8 × 19.2 lit

The slot is ALREADY 40 mm wider than the window needs to be. It is short — but
opening a hole DOWNWARD by 15 mm along one edge is a filing job, and cutting a
fresh 84 × 27 rectangle into a thirty-year-old fascia you cannot replace is the
job people abandon the build over.

Everything here is to scale in millimetres, so the overlaps are real overlaps.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svg import (Svg, AMBER, BLUE, CLIP, DIM, EDGE, GREEN,      # noqa: E402
                 HOT, INK, PANEL)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ISO 7736 fascia, and the two apertures that matter.
FASCIA_W, FASCIA_H = 182.0, 53.0
SLOT_W, SLOT_H = 125.0, 12.0        # ⚠️ typical; a CD is 120 mm so it cannot be
                                    #    much narrower. Height varies 10–14 mm.
WIN_W, WIN_H = 84.0, 27.0           # what a 256×64 module wants, with a border
LIT_W, LIT_H = 76.8, 19.2           # what actually glows


def draw(out):
    W, H = 1080, 1010
    s = Svg(W, H, "THE HOLE THE CD CAME OUT OF",
            "A CD slot is 125 mm wide because a CD is 120 mm. The deck's window "
            "needs 84. That is the whole idea.")

    # The fascia is drawn LEFT, and every note lives in a column to the RIGHT
    # of it. The first version centred the fascia and put the notes beside it,
    # which ran them off the page — and stacked the three panels 212 px apart
    # when a fascia at that scale is 223 tall, so they overlapped as well.
    sc = 3.4
    fx = 40
    CX = fx + FASCIA_W * sc + 34          # the note column
    PITCH = 250                            # comfortably more than 53 mm * sc

    def note(y, lines, fill=DIM):
        for i, ln in enumerate(lines):
            s.caption(CX, y + i * 14, ln, size=9.5,
                      fill=fill if not isinstance(fill, list) else fill[i])

    def fascia(y, label, sub):
        s.rect(fx, y, FASCIA_W * sc, FASCIA_H * sc, fill="#15151c",
               stroke="#3a3844", sw=1.6, rx=4)
        s.text(fx, y - 22, label, size=10.5, fill=HOT, weight="700",
               spacing="0.1em")
        s.caption(fx, y - 8, sub, size=9)

    # ---------------------------------------------------------------- 1. as found
    y1 = 100
    fascia(y1, "1 · AS YOU FIND IT",
           "a fixed-face CD unit: a small display window, and the slot")
    # the donor's own window, the small one this family is cursed with
    ow, oh = 52.0, 18.0
    s.rect(fx + (FASCIA_W - ow) / 2 * sc, y1 + 8 * sc, ow * sc, oh * sc,
           fill="#0a0a0e", stroke=DIM, sw=1.2, rx=2)
    s.text(fx + FASCIA_W * sc / 2, y1 + 8 * sc + oh * sc / 2 + 4,
           "its window  52 × 18", size=9, fill=DIM, anchor="middle")
    # the slot
    sy = y1 + 32 * sc
    s.rect(fx + (FASCIA_W - SLOT_W) / 2 * sc, sy, SLOT_W * sc, SLOT_H * sc,
           fill="#000", stroke=CLIP, sw=1.6, rx=2)
    s.text(fx + FASCIA_W * sc / 2, sy + SLOT_H * sc / 2 + 4,
           "the slot  ~125 × 12", size=9, fill=CLIP, anchor="middle")
    note(y1 + 30, [
        "⚠️  Its own display window is 52 × 18 mm.",
        "A 256×64 panel needs 84 × 27, so you are",
        "cutting a new aperture whichever way you",
        "go — the slot is not in the way of that.",
        "",
        "It is the thing that makes it easy.",
    ], fill=[DIM, DIM, DIM, DIM, DIM, AMBER])

    # ---------------------------------------------------------------- 2. overlay
    y2 = y1 + PITCH
    fascia(y2, "2 · THE COINCIDENCE, TO SCALE",
           "the window the deck wants, laid over the slot you already have")
    sy2 = y2 + 32 * sc
    s.rect(fx + (FASCIA_W - SLOT_W) / 2 * sc, sy2, SLOT_W * sc, SLOT_H * sc,
           fill="#000", stroke="#4a4854", sw=1.4, rx=2)
    # the window, centred on the slot's top edge — this is the actual proposal
    wx = fx + (FASCIA_W - WIN_W) / 2 * sc
    wy = sy2 - (WIN_H - SLOT_H) / 2 * sc
    s.rect(wx, wy, WIN_W * sc, WIN_H * sc, fill="none", stroke=AMBER, sw=2,
           dash="6 4")
    s.rect(wx + (WIN_W - LIT_W) / 2 * sc, wy + (WIN_H - LIT_H) / 2 * sc,
           LIT_W * sc, LIT_H * sc, fill="#1a1206", stroke=AMBER, sw=1)
    s.text(wx + WIN_W * sc / 2, wy + WIN_H * sc / 2 + 4, "84 × 27 window",
           size=9.5, fill=AMBER, anchor="middle", weight="600")

    # the width you already have, called out
    s.line(fx + (FASCIA_W - SLOT_W) / 2 * sc, sy2 + SLOT_H * sc + 22,
           fx + (FASCIA_W + SLOT_W) / 2 * sc, sy2 + SLOT_H * sc + 22,
           stroke=GREEN, sw=1.6)
    s.text(fx + FASCIA_W * sc / 2, sy2 + SLOT_H * sc + 38,
           "125 mm of width you already have — 41 mm more than you need",
           size=9, fill=GREEN, anchor="middle")
    # the height you have to make
    s.line(wx - 16, wy, wx - 16, wy + WIN_H * sc, stroke=HOT, sw=1.6)
    s.text(wx - 24, wy + WIN_H * sc / 2, "27", size=9, fill=HOT, anchor="end")
    note(y2 + 30, [
        "The slot is ALREADY 41 mm wider than the",
        "window needs to be. What it is short of is",
        "height: 12 mm against 27.",
        "",
        "So file 7.5 mm off the top edge and 7.5 off",
        "the bottom. One axis, one file, following",
        "two straight edges that are already there.",
        "",
        "Cutting a fresh 84 × 27 rectangle into a",
        "thirty-year-old fascia is the job people",
        "abandon the build over.",
    ], fill=[INK, INK, INK, INK, HOT, HOT, HOT, INK, DIM, DIM, DIM])

    # ---------------------------------------------------------------- 3. or not
    y3 = y2 + PITCH
    fascia(y3, "3 · OR, IF YOU WOULD RATHER NOT CUT IT",
           "the slot takes buttons or sockets with no drilling at all")
    sy3 = y3 + 32 * sc
    s.rect(fx + (FASCIA_W - SLOT_W) / 2 * sc, sy3, SLOT_W * sc, SLOT_H * sc,
           fill="#0e0e14", stroke="#4a4854", sw=1.4, rx=2)
    # buttons filling the slot
    n = 6
    bw = SLOT_W / n
    for i in range(n):
        bx = fx + ((FASCIA_W - SLOT_W) / 2 + i * bw + 1.5) * sc
        s.rect(bx, sy3 + 2, (bw - 3) * sc, SLOT_H * sc - 4, fill=PANEL,
               stroke=AMBER, sw=1.2, rx=2)
        s.text(bx + (bw - 3) * sc / 2, sy3 + SLOT_H * sc / 2 + 3.5,
               ["SRC", "DISP", "BAND", "ART", "LYR", "DEMO"][i], size=7.5,
               fill=HOT, anchor="middle")
    note(y3 + 30, [
        "A 125 × 12 mm aperture is a ready-made",
        "button strip: six caps at roughly 20 mm",
        "pitch, straight into a hole that is already",
        "the right shape.",
        "",
        "Or put the aux and USB sockets through it.",
        "",
        "Either way there is no hole saw anywhere",
        "near the one part you cannot replace.",
    ], fill=[INK, INK, INK, INK, INK, INK, INK, GREEN, GREEN])

    # ---------------------------------------------------------------- 4. the one
    # donor whose display size is actually published, and what it means.
    y4 = y3 + PITCH
    s.rect(fx, y4, W - 2 * fx, 96, fill="#0f0f14", stroke=GREEN, sw=1.2, rx=5)
    s.text(fx + 16, y4 + 24, "AND ONE DONOR WHOSE DISPLAY SIZE IS PUBLISHED",
           size=9.5, fill=HOT, spacing="0.12em")
    s.caption(fx + 16, y4 + 46,
              "The Pioneer MEH-P9000R's own screen is 256 × 52 pixels — a "
              "figure Pioneer printed. At the usual 0.3 mm pitch that is a "
              "76.8 × 15.6 mm", size=9.5)
    s.caption(fx + 16, y4 + 60,
              "lit area. The deck's SSD1322 is 256 × 64, which is 76.8 × 19.2 — "
              "THE SAME WIDTH, and 3.6 mm taller.", size=9.5, fill=GREEN)
    s.caption(fx + 16, y4 + 78,
              "So that one window is already the right width and wants opening "
              "by about 4 mm. Every other donor: measure it — "
              "tools/donors/fit.py.", size=9, fill=AMBER)

    s.caption(28, H - 22,
              "⚠️  Slot sizes are typical, not measured — a CD is 120 mm so the "
              "width is near enough fixed, but the height varies 10–14 mm by "
              "model. Measure yours before filing anything.", fill=CLIP)
    return s.save(os.path.join(out, "slot-options.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    p = draw(out)
    print(f"  {os.path.relpath(p, ROOT):<38} {os.path.getsize(p) / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
