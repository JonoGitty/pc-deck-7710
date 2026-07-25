#!/usr/bin/env python3
"""One exploded strip-down per donor family: what comes out, and what you keep.

    python3 tools/diagrams/teardown.py [outdir]

WHY THIS IS A DRAWING AND NOT A LIST

A teardown list tells you the order. It does not tell you the thing that
actually matters when you are holding a screwdriver over a thirty-year-old
head unit, which is **which of these am I about to throw away**.

Get that wrong in one direction and you bin the fascia's button flexi with the
main board still attached to it. Get it wrong in the other and you spend an
evening carefully preserving a CD mechanism.

So every part is colour-coded, and there are only three colours:

    green   KEEP    this is why you bought it
    red     BIN     goes in the bin, first evening
    amber   HAZARD  discharge it, or prove it is safe, before you touch it

The order is top-to-bottom in the order it comes apart, which for every unit
in this document starts with the fascia and ends with the bare chassis.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svg import (Svg, AMBER, CLIP, DIM, EDGE, GREEN, HOT,        # noqa: E402
                 INK, PANEL)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "donors")

ACTION = {
    "keep":   (GREEN, "KEEP",   "this is why you bought it"),
    "bin":    (CLIP,  "BIN",    "first evening, in the bin"),
    "hazard": (AMBER, "HAZARD", "discharge before you touch it"),
}


def load():
    out = []
    for dirpath, _d, files in os.walk(SRC):
        for fn in sorted(files):
            if fn.endswith(".json"):
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                d["_slug"] = os.path.splitext(fn)[0]
                out.append(d)
    out.sort(key=lambda d: (d["grade"], d["_slug"]))
    return out


def draw(d, out):
    parts = d.get("teardown") or []
    rows = len(parts)
    ROW = 46
    W = 1120
    H = 150 + rows * ROW + 96
    s = Svg(W, H, "STRIP-DOWN  ·  " + d["family"].upper(),
            "In the order it comes apart. Green you keep, red goes in the "
            "bin, amber gets discharged first.")

    # legend
    lx = 28
    for key in ("keep", "bin", "hazard"):
        col, label, blurb = ACTION[key]
        s.rect(lx, 78, 11, 11, fill=col, rx=2)
        s.text(lx + 18, 88, label, size=8.5, fill=col, weight="700")
        s.caption(lx + 18 + len(label) * 6.6 + 8, 88, blurb, size=8.5)
        lx += 18 + len(label) * 6.6 + 14 + len(blurb) * 5.2 + 28

    # the stack: each part is a slab, stepped right as it comes off, so the
    # eye reads it as a sequence rather than as a parts list with colours.
    x0, y0 = 40, 128
    bw, bh = 440, 30
    step = 13
    # The verdict column starts clear of the WIDEST slab, not of the first
    # one — the stack steps right as it comes apart, so a fixed column that
    # suits row 1 is underneath row 10.
    vx = x0 + (rows - 1) * step + bw + 26

    for i, p in enumerate(parts):
        col, label, _b = ACTION.get(p["action"], ACTION["bin"])
        x = x0 + i * step
        y = y0 + i * ROW

        # the slab
        s.path(f"M {x} {y} L {x + bw} {y} L {x + bw - 22} {y + bh} "
               f"L {x - 22} {y + bh} Z", stroke=col, sw=1.3, fill=PANEL)
        s.path(f"M {x} {y} L {x + bw} {y}", stroke=col, sw=2.4)

        s.text(x + 14, y + 20, f"{i + 1}", size=13, fill=col, weight="700",
               op=0.5)
        s.text(x + 40, y + 20, p["part"], size=11, fill=INK, weight="600")

        # the verdict, in its own column so the eye can scan it alone
        s.rect(vx, y + 3, 62, 20, fill=col, rx=4)
        s.text(vx + 31, y + 17, label, size=8.5, fill="#0c0c10",
               anchor="middle", weight="700")

        if p.get("note"):
            note = p["note"]
            room = int((W - (vx + 90)) / 5.1)
            if len(note) > room:
                cut = note.rfind(" ", 0, room)
                s.caption(vx + 76, y + 13, note[:cut], size=9)
                s.caption(vx + 76, y + 26, note[cut + 1:][:room + 4], size=9)
            else:
                s.caption(vx + 76, y + 19, note, size=9)

        # the removal arrow, off to the left
        if i < rows - 1:
            ay = y + bh + 4
            s.path(f"M {x - 30} {ay} L {x - 30} {ay + ROW - bh - 8}",
                   stroke=EDGE, sw=1, dash="3 3")

    keep = sum(1 for p in parts if p["action"] == "keep")
    binned = sum(1 for p in parts if p["action"] == "bin")
    haz = sum(1 for p in parts if p["action"] == "hazard")

    y = H - 74
    s.rect(28, y, W - 56, 46, fill="#0f0f14", stroke=EDGE, rx=5)
    s.rect(28, y, 3, 46, fill=AMBER, rx=1.5)
    s.text(44, y + 20, f"{keep} KEEP", size=10, fill=GREEN, weight="700")
    s.text(120, y + 20, f"{binned} BIN", size=10, fill=CLIP, weight="700")
    s.text(190, y + 20, f"{haz} HAZARD", size=10, fill=AMBER, weight="700")
    s.caption(290, y + 20,
              "Grade " + d["grade"] + " · " + d["one_liner"], size=9.5)
    s.caption(44, y + 37,
              "⚠️  Never performed. This is the intended order, from the "
              "construction these units are known to use — not a log of "
              "having done it.", fill=CLIP)
    return s.save(os.path.join(out, f"teardown-{d['_slug']}.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    donors = [d for d in load() if d.get("teardown")]
    if not donors:
        sys.exit("no donor has a teardown yet")
    for d in donors:
        p = draw(d, out)
        print(f"  {os.path.relpath(p, ROOT):<40} "
              f"{os.path.getsize(p) / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
