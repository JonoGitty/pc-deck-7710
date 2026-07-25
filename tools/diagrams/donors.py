#!/usr/bin/env python3
"""One drawing per donor family: does the deck's panel fit behind its window?

    python3 tools/diagrams/donors.py [outdir]

THE ONE QUESTION A DONOR DRAWING SHOULD ANSWER

Everything else about a scrap head unit is recoverable. The chassis can be
shimmed, the buttons rewired, the knob swapped, the depth worked around. The
window cannot: it is a hole in the one part you chose the donor for, and
enlarging it is the difference between a deck that looks bought and a deck
that looks made in a shed.

So the drawing is a fascia at 1:1 proportions with two rectangles on it — the
donor's window, and the panel's lit area — and a verdict. Nothing else. A
drawing that also showed the buttons and the knob would be prettier and would
bury the only thing worth looking at.

The panel sizes are the real ones, from the module datasheets:

    SSD1322 256×64    ≈ 76 × 19 mm active
    GP1294AI 256×48   ≈ 76 × 14 mm active

⚠️ Donor window sizes are believed, not measured — see the confidence marker on
each. The drawing is to scale, which means a wrong number is wrong visibly.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svg import (Svg, AMBER, BLUE, CLIP, DIM, EDGE, GREEN,      # noqa: E402
                 HOT, INK, PANEL)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "donors")

FASCIA_W, FASCIA_H = 182.0, 53.0
PANELS = [
    ("SSD1322 256×64", 76.0, 19.0, AMBER),
    ("GP1294AI 256×48", 76.0, 14.0, GREEN),
]
BORDER = 4.0            # the margin that makes a window look deliberate

MARK = {"verified": "✅", "unverified": "⚠️", "measure": "📏"}


def load():
    out = []
    for dirpath, _d, files in os.walk(SRC):
        for fn in sorted(files):
            if fn.endswith(".json"):
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                d["_slug"] = os.path.splitext(fn)[0]
                d["_path"] = os.path.relpath(p, ROOT)
                out.append(d)
    out.sort(key=lambda d: (d["grade"], d["_slug"]))
    return out


def verdict(win_w, win_h):
    """(text, colour) for the biggest panel that fits, or what is missing.

    Deliberately reports the SHORTFALL in millimetres rather than just
    pass/fail. 'Needs 3 mm' is a filing job; 'needs 14 mm' is a different
    donor, and the two should not read the same."""
    if win_w <= 0 or win_h <= 0:
        return ("no usable window — you are cutting one, which for this "
                "family is the plan rather than the problem", BLUE)
    best = None
    for name, pw, ph, _c in PANELS:
        if win_w >= pw and win_h >= ph:
            best = name
            break
    if best:
        slack_w = win_w - PANELS[0][1]
        slack_h = win_h - PANELS[0][2]
        if win_w >= PANELS[0][1] + 2 * BORDER and \
           win_h >= PANELS[0][2] + 2 * BORDER:
            return (f"fits with a border — {slack_w:.0f} mm spare across, "
                    f"{slack_h:.0f} mm up", GREEN)
        return (f"fits, but tight — {slack_w:.0f} × {slack_h:.0f} mm spare. "
                "The panel will nearly touch the edge", HOT)
    # Name only the dimension that is actually short. "needs 24 mm across and
    # 0 mm up" makes the reader work out which half of the sentence matters.
    need_w = max(0.0, PANELS[1][1] - win_w)
    need_h = max(0.0, PANELS[1][2] - win_h)
    short = []
    if need_w > 0:
        short.append(f"{need_w:.0f} mm wider")
    if need_h > 0:
        short.append(f"{need_h:.0f} mm taller")
    return ("too small even for the VFD — the window needs to be "
            + " and ".join(short)
            + ". Enlarge it, or plan on a new face", CLIP)


def draw(d, out):
    W, H = 1060, 460
    name = f"{d['brand'] if 'brand' in d else ''}{d['family']}"
    s = Svg(W, H, "WINDOW FIT  ·  " + d["family"].upper(),
            "The fascia to scale, the donor's window, and the deck's lit area "
            "on top of it. Nothing else, because nothing else decides this.")

    sc = 3.9                                  # px per mm
    fx = 40
    fy = 132

    # the fascia
    s.rect(fx, fy, FASCIA_W * sc, FASCIA_H * sc, fill=PANEL, stroke=EDGE,
           sw=1.5, rx=5)
    s.caption(fx, fy - 12, "the donor's face — 182 × 53 mm, ISO 7736")

    win_w = float(d["window_w_mm"]["v"])
    win_h = float(d["window_h_mm"]["v"])
    txt, col = verdict(win_w, win_h)

    if win_w > 0 and win_h > 0:
        wx = fx + (FASCIA_W - win_w) * sc / 2
        wy = fy + (FASCIA_H - win_h) * sc / 2
        s.rect(wx, wy, win_w * sc, win_h * sc, fill="#07070a", stroke=INK,
               sw=1.4)
        s.text(wx + win_w * sc / 2, wy - 8,
               f"window {win_w:.0f} × {win_h:.0f} mm "
               f"{MARK[d['window_w_mm']['c']]}",
               size=9, fill=INK, anchor="middle")
    else:
        wx = fx + (FASCIA_W - 84) * sc / 2
        wy = fy + (FASCIA_H - 27) * sc / 2
        s.rect(wx, wy, 84 * sc, 27 * sc, fill="none", stroke=BLUE, sw=1.4,
               dash="5 4")
        s.text(wx + 84 * sc / 2, wy - 8, "no window — cut one, 84 × 27 mm",
               size=9, fill=BLUE, anchor="middle")

    # The panels, concentric with the window because that is how they will be
    # fitted. Their labels are keyed out to the right at fixed heights rather
    # than beside each rectangle: the two panels differ by 5 mm of height, so
    # labels centred on each land on top of one another.
    right = fx + FASCIA_W * sc + 16
    for i, (pname, pw, ph, pcol) in enumerate(reversed(PANELS)):
        px = fx + (FASCIA_W - pw) * sc / 2
        py = fy + (FASCIA_H - ph) * sc / 2
        solid = i == len(PANELS) - 1
        s.rect(px, py, pw * sc, ph * sc, fill="none", stroke=pcol, sw=1.6,
               dash=None if solid else "4 3")
        ly = fy + 24 + i * 28
        s.line(px + pw * sc, py + (0 if solid else ph * sc), right - 8, ly - 4,
               stroke=pcol, sw=0.8, dash="2 3")
        s.circle(right - 8, ly - 4, 2.4, fill=pcol)
        s.text(right, ly, f"{pname}", size=8.5, fill=pcol, weight="600")
        s.text(right, ly + 11, f"{pw:.0f} × {ph:.0f} mm lit", size=8,
               fill=DIM)

    # verdict
    s.rect(28, 336, W - 56, 52, fill="#0f0f14", stroke=col, sw=1, rx=5)
    s.rect(28, 336, 3, 52, fill=col, rx=1.5)
    s.text(44, 358, "VERDICT", size=8.5, fill=col, spacing="0.16em")
    s.caption(120, 358, txt, size=10, fill=INK)
    s.caption(120, 376,
              f"grade {d['grade']}  ·  {d['one_liner']}", size=9.5)

    s.caption(28, H - 26,
              "⚠️  Window sizes are believed, not measured. The drawing is to "
              "scale, so measure yours with calipers and correct the file — a "
              "wrong number here is wrong visibly.", fill=CLIP)
    return s.save(os.path.join(out, f"donor-{d['_slug']}.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    donors = load()
    if not donors:
        sys.exit("no donors found under " + SRC)
    for d in donors:
        p = draw(d, out)
        print(f"  {os.path.relpath(p, ROOT):<38} "
              f"{os.path.getsize(p) / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
