#!/usr/bin/env python3
"""Will the panel fit THIS donor? Measured off a listing photograph.

    python3 tools/donors/fit.py --fascia 1180 --window 476x104
    python3 tools/donors/fit.py --fascia 1180 --window 476x104 --slot 812x78
    python3 tools/donors/fit.py --mm 86x26

WHY THIS EXISTS RATHER THAN A TABLE OF NUMBERS

Nobody publishes the window size of a 1998 head unit. Not the service manual,
not the spec sheet, not the listing. I went looking, model by model, and what
exists is the display's *pixel count* for a handful of units and nothing at all
for the rest. A table of forty guessed windows would look authoritative and be
wrong, and somebody would buy a fascia on it.

But you do not need a table, because **every 1-DIN fascia is the same width.**
ISO 7736 fixes the aperture at 182 × 53 mm and the fascia fills it. So any
straight-on photograph of any head unit — the listing you are looking at right
now — is a ruler with a known scale:

    real mm  =  pixels measured  ×  182  /  fascia width in pixels

That is accurate to a millimetre or two, which is the precision that matters
when the question is "do I file this or buy a different one". It takes twenty
seconds in any image viewer that shows a selection size — Preview, Paint, GIMP,
the Windows Photos crop tool, or a phone screenshot editor.

Measure the fascia's OUTER edges, not the bezel's inner ones, and use a photo
taken square-on: a three-quarter view is a foreshortened ruler and will tell you
the window is narrower than it is.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FASCIA_MM = 182.0                 # ISO 7736. The scale reference for everything.

# The two panels the firmware drives, as a module and as the area that lights.
# A window has to clear the LIT area with a border, and the MODULE has to fit
# behind the fascia — those are different numbers and people conflate them.
PANELS = [
    {"name": "SSD1322 OLED 256×64",
     "lit_w": 76.8, "lit_h": 19.2, "pcb_w": 100.5, "pcb_h": 33.5,
     "note": "the recommended build — 16 greys, all four levels survive"},
    {"name": "GP1294AI VFD 256×48",
     "lit_w": 76.8, "lit_h": 14.4, "pcb_w": 99.0, "pcb_h": 30.0,
     "note": "1-bit, and 4.8 mm shorter — the one that fits a shallow window"},
]
BORDER = 3.5                      # mm of fascia you want around the lit area


def mm(px, fascia_px):
    return px * FASCIA_MM / fascia_px


def verdict(win_w, win_h, slot_w=None, slot_h=None):
    """What each panel needs, in millimetres, one way or the other."""
    out = []
    for p in PANELS:
        need_w = p["lit_w"] + 2 * BORDER
        need_h = p["lit_h"] + 2 * BORDER
        short_w = max(0.0, need_w - win_w)
        short_h = max(0.0, need_h - win_h)

        if short_w == 0 and short_h == 0:
            state, how = "✅ FITS", "no cutting at all"
        elif short_w == 0 and short_h <= 6:
            state, how = "✅ FILE IT", f"open the window {short_h:.1f} mm taller"
        elif short_w <= 6 and short_h <= 6:
            state = "✅ FILE IT"
            how = (f"open it {short_w:.1f} mm wider and {short_h:.1f} mm taller")
        elif slot_w and slot_w >= need_w:
            state = "⚠️ USE THE SLOT"
            how = (f"the window is {short_w:.0f}×{short_h:.0f} mm short — but "
                   f"the CD slot is {slot_w:.0f} mm wide, which is "
                   f"{slot_w - need_w:.0f} mm MORE than you need. Open the slot "
                   f"from {slot_h:.0f} to {need_h:.0f} mm tall and use it as "
                   f"the window instead")
        else:
            state = "❌ TOO SMALL"
            how = (f"short by {short_w:.1f} mm wide and {short_h:.1f} mm tall — "
                   "cutting that much of a fascia is a new aperture, not a file")
        out.append((p, state, how, short_w, short_h))
    return out


def report(win_w, win_h, slot_w=None, slot_h=None, source=""):
    print()
    print(f"  window   {win_w:6.1f} × {win_h:5.1f} mm" +
          (f"   ({source})" if source else ""))
    if slot_w:
        print(f"  CD slot  {slot_w:6.1f} × {slot_h:5.1f} mm")
    print(f"  fascia   {FASCIA_MM:6.1f} × 53.0 mm   (ISO 7736, the reference)")
    print()

    for p, state, how, _sw, _sh in verdict(win_w, win_h, slot_w, slot_h):
        print(f"  {state:<16} {p['name']}")
        print(f"  {'':16} needs {p['lit_w'] + 2 * BORDER:.1f} × "
              f"{p['lit_h'] + 2 * BORDER:.1f} mm of window "
              f"({p['lit_w']} × {p['lit_h']} lit, {BORDER} mm border)")
        print(f"  {'':16} {how}")
        # The module is bigger than the hole and has to live behind the fascia.
        if p["pcb_w"] > FASCIA_MM - 8:
            print(f"  {'':16} ⚠️ the {p['pcb_w']} mm module is tight behind a "
                  f"{FASCIA_MM:.0f} mm face")
        print()

    print("  ⚠️  Measured off a photograph is ±1–2 mm. Before you file anything,")
    print("      put calipers on the actual fascia. Before you BUY, this is")
    print("      exactly the right amount of certainty.")
    print()


def main():
    ap = argparse.ArgumentParser(
        description="Will the deck's panel fit this donor's window?",
        epilog="Measure from any straight-on photo: the fascia is 182 mm wide.")
    ap.add_argument("--fascia", type=float, metavar="PX",
                    help="fascia width in PIXELS, measured outer edge to outer "
                         "edge on the photo")
    ap.add_argument("--window", metavar="WxH",
                    help="display window in PIXELS on the same photo, e.g. "
                         "476x104")
    ap.add_argument("--slot", metavar="WxH",
                    help="the CD slot in PIXELS, if it has one — it is usually "
                         "the widest aperture on the face and often the answer")
    ap.add_argument("--mm", metavar="WxH",
                    help="skip the photo: the window in MILLIMETRES, if you "
                         "have already measured it")
    a = ap.parse_args()

    def pair(s):
        w, _, h = s.lower().partition("x")
        return float(w), float(h)

    if a.mm:
        w, h = pair(a.mm)
        report(w, h, source="measured")
        return 0

    if not (a.fascia and a.window):
        ap.print_help()
        print("\n  Example, from a typical eBay photo:\n")
        print("      python3 tools/donors/fit.py --fascia 1180 --window 476x104")
        print()
        return 2

    ww, wh = pair(a.window)
    sw = sh = None
    if a.slot:
        s1, s2 = pair(a.slot)
        sw, sh = mm(s1, a.fascia), mm(s2, a.fascia)
    report(mm(ww, a.fascia), mm(wh, a.fascia), sw, sh,
           source=f"scaled from {a.fascia:.0f} px = 182 mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
