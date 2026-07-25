#!/usr/bin/env python3
"""Two drawings for the maximum-reuse route: the amplifier, and the back panel.

    python3 tools/diagrams/reuse.py [outdir]

[docs/REUSE.md](../../docs/REUSE.md) argues that the default build throws away
a £12–20 part and then tells you to buy it again. These are the two drawings
that argument needs, because both are jobs where prose describes the goal and
hides the work.

**The amplifier.** The donor's power amp IC sits at the end of a signal chain
you are deleting. Every word of "cut its inputs free and feed them the deck's
line out" is easy to write and hard to picture, and the step people actually
fail on — the mute and standby pins floating once the old microcontroller is
gone — is invisible in a block diagram. So it gets its own inset with the
resistors drawn in.

**The back panel.** The connectors, the aerial socket and the fusing are all
on one pressing, already wired to the parts you are keeping. Drawing it makes
the point faster than a list does: the reuse route is mostly *not unbolting
things*, and the wiring you avoid is the wiring behind the dash.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svg import (Svg, AMBER, BLUE, CLIP, DIM, EDGE, GREEN,      # noqa: E402
                 HOT, INK, PANEL)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wrap(text, cols):
    """Break a sentence at word boundaries. Truncating instead — which is what
    the first draft of this file did — silently loses the second half of every
    caption, and a caption that stops mid-word is worse than a shorter one."""
    lines, line = [], ""
    for word in text.split(" "):
        if len(line) + len(word) + 1 > cols and line:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines

# The chain as it leaves the factory. Everything up to the coupling capacitors
# is dead the moment the microcontroller goes; everything after it is a working
# 4-channel amplifier that is already bolted down and already wired up.
CHAIN = [
    ("CD / TAPE\nMECHANISM", "the source you are\nreplacing", CLIP, "bin"),
    ("PREAMP &\nTONE STAGE", "volume, bass, treble —\nthe deck does this now",
     CLIP, "bin"),
    ("COUPLING\nCAPS  ×4", "the cut point.\nOne per channel", AMBER, "cut"),
    ("POWER AMP IC\nTDA7388 / 7850", "4 × 40 W, on the chassis\nas its heatsink",
     GREEN, "KEEP"),
    ("ISO SPEAKER\nCONNECTOR", "already wired,\nalready fused", GREEN, "KEEP"),
]


def amplifier(out):
    W, H = 1100, 700
    s = Svg(W, H, "REUSING THE DONOR'S AMPLIFIER",
            "The last two boxes in the donor's signal chain are the part "
            "BUILD.md tells you to go and buy.")

    bw, bh, gap = 176, 92, 22
    x0 = 34
    cy = 150

    for i, (label, sub, colour, verdict) in enumerate(CHAIN):
        x = x0 + i * (bw + gap)
        dead = verdict == "bin"
        s.rect(x, cy, bw, bh, fill="#0e0e12" if dead else PANEL, stroke=EDGE,
               sw=1, rx=4, op=0.55 if dead else None)
        s.rect(x, cy, 3, bh, fill=colour, rx=1.5)
        for j, ln in enumerate(label.split("\n")):
            s.text(x + 13, cy + 22 + j * 14, ln, size=10.5,
                   fill=DIM if dead else INK, weight="600")
        for j, ln in enumerate(sub.split("\n")):
            s.caption(x + 13, cy + 58 + j * 13, ln, size=9,
                      fill="#5c5a63" if dead else DIM)
        # Pills sit at the LEFT of each box. On the right they collided with
        # the cut marker's label, which is the one annotation on this drawing
        # that must not be ambiguous about which gap it means.
        s.pill(x + 10, cy - 8, verdict,
               fill=colour, ink="#17110a" if colour != CLIP else "#1a0805")

        if i:                                     # the link from the previous
            lx = x - gap
            s.line(lx, cy + bh / 2, x, cy + bh / 2,
                   stroke="#3a3844" if i <= 2 else GREEN, sw=1.8)

    # ---- the cut, drawn on the link into the coupling caps
    cut_x = x0 + 2 * (bw + gap) - gap / 2
    s.line(cut_x - 9, cy + bh / 2 - 11, cut_x + 9, cy + bh / 2 + 11,
           stroke=CLIP, sw=2.2)
    s.line(cut_x - 9, cy + bh / 2 + 11, cut_x + 9, cy + bh / 2 - 11,
           stroke=CLIP, sw=2.2)
    s.text(cut_x, cy - 42, "CUT HERE", size=9, fill=CLIP, anchor="middle",
           weight="700", spacing="0.1em")
    s.caption(cut_x, cy - 28, "on the preamp side of the caps", size=8.5,
              fill=CLIP, anchor="middle")

    # ---- the deck's line out, coming up from underneath into the caps
    caps_x = x0 + 2 * (bw + gap)
    inj_y = cy + bh + 78
    s.box(caps_x - 118, inj_y, 250, 56, "THE DECK'S LINE OUT",
          ["PCM5102A, or the PT2313's fader outputs"], accent=AMBER)
    s.path(f"M {caps_x + 7} {inj_y} V {cy + bh + 14}", stroke=AMBER, sw=2.4)
    s.path(f"M {caps_x} {cy + bh + 24} L {caps_x + 7} {cy + bh + 12} "
           f"L {caps_x + 14} {cy + bh + 24}", stroke=AMBER, sw=2.4)
    s.text(caps_x + 22, cy + bh + 40, "inject here — 4 wires", size=9,
           fill=AMBER, weight="600")
    s.caption(caps_x + 22, cy + bh + 54,
              "front L/R from the deck; rear from the same pair unless a "
              "PT2313 is fitted", size=8.5)

    # ---- the inset that decides whether it works at all
    y = 400
    s.rect(34, y, 520, 250, fill="#0f0f14", stroke=CLIP, sw=1.2, rx=5)
    s.text(50, y + 24, "⚠️  THE STEP EVERYBODY MISSES", size=9.5, fill=CLIP,
           spacing="0.12em", weight="700")
    s.caption(50, y + 46,
              "The old microcontroller drove ST-BY and MUTE. With it gone "
              "they float, the amplifier stays", size=9.5)
    s.caption(50, y + 60,
              "muted, and you conclude the chip is dead and buy a board. "
              "Tie them to their enable level.", size=9.5)

    px, py = 78, y + 92
    s.rect(px, py, 150, 118, fill=PANEL, stroke=EDGE, rx=4)
    s.rect(px, py, 3, 118, fill=GREEN, rx=1.5)
    s.text(px + 75, py + 66, "TDA7388", size=11, fill=INK, anchor="middle",
           weight="600")
    for j, (pin, note) in enumerate((("ST-BY", "brings it out of standby"),
                                     ("MUTE", "un-mutes it"))):
        ly = py + 36 + j * 46
        s.line(px + 150, ly, px + 212, ly, stroke=INK, sw=1.4)
        s.text(px + 140, ly + 4, pin, size=8.5, fill=DIM, anchor="end")
        s.rect(px + 212, ly - 8, 46, 16, fill="#191920", stroke=AMBER, rx=2)
        s.text(px + 235, ly + 4, "R", size=8.5, fill=HOT, anchor="middle")
        s.line(px + 258, ly, px + 300, ly, stroke=INK, sw=1.4)
        s.circle(px + 300, ly, 3, fill=CLIP)
        s.text(px + 310, ly + 4, f"enable — {note}", size=8.5, fill=CLIP)
        s.caption(px + 310, ly + 17, "value from the datasheet", size=8)

    s.caption(50, y + 232,
              "Both pins, both resistors, before you conclude anything. "
              "The datasheet gives the value.", fill=AMBER, size=9)

    # ---- what it is worth, beside it
    s.rect(574, y, W - 574 - 34, 250, fill="#0f0f14", stroke=EDGE, rx=5)
    s.rect(574, y, 3, 250, fill=GREEN, rx=1.5)
    s.text(590, y + 24, "WHAT THE REUSE ROUTE IS WORTH", size=9.5, fill=HOT,
           spacing="0.12em")
    rows = [
        ("Saves", "£12–20, plus a heatsink and mounting you would "
                  "otherwise have to arrange", GREEN),
        ("Costs", "an evening with a datasheet and a scalpel", INK),
        ("Risk", "low — worst case it does not work and you buy the board "
                 "you were going to buy", INK),
        ("Easiest on", "cassette-era donors: single-IC amps, generous "
                       "layouts, no digital preamp in the way", GREEN),
        ("Hardest on", "late CD units where the tone stage is inside the "
                       "same package as the DAC", AMBER),
    ]
    for i, (k, v, col) in enumerate(rows):
        ry = y + 56 + i * 38
        s.text(590, ry, k, size=9.5, fill=col, weight="600")
        for j, ln in enumerate(wrap(v, 52)):
            s.caption(680, ry + j * 13, ln, size=9)

    s.caption(34, H - 16,
              "⚠️  Described from the datasheets of these ICs and from how "
              "these units are built — not from having cut one open. "
              "docs/REUSE.md", fill=CLIP)
    return s.save(os.path.join(out, "reuse-amp.svg"))


# The back panel, roughly to the ISO 7736 chassis it is pressed into: 180 mm
# across the back, 50 mm tall. Positions are indicative — every manufacturer
# arranges these differently — but the sizes are the standards' own.
BACK_W, BACK_H = 180.0, 50.0


def back_panel(out):
    W, H = 1060, 660
    s = Svg(W, H, "KEEP THE BACK PANEL",
            "Every connector the car plugs into is already on it, already "
            "wired, already fused.")

    sc = 4.6
    bx = (W - BACK_W * sc) / 2
    by = 104

    s.rect(bx, by, BACK_W * sc, BACK_H * sc, fill="#101018", stroke="#3a3844",
           sw=1.6, rx=3)
    s.caption(bx, by - 12,
              "the donor's rear pressing — 180 × 50 mm, ISO 7736")

    def mm(x, y):
        return bx + x * sc, by + y * sc

    # Nothing gets a sentence inside the pressing: the label column below does
    # that. Crowding explanations between the connectors was the first draft
    # and every caption landed on the connector under it.
    blk_w, blk_h = 40.0, 18.0
    for i, (label, colour) in enumerate((("ISO  A", BLUE),
                                         ("ISO  B", GREEN))):
        # 4 mm between the halves, not 2: the labels go UNDER each block
        # and at 2 mm the first one lands on the second block's edge.
        x, y = mm(8.0, 5.0 + i * (blk_h + 4))
        s.rect(x, y, blk_w * sc, blk_h * sc, fill="#151520", stroke=colour,
               sw=1.6, rx=3)
        for c in range(4):
            for r in range(2):
                s.circle(x + 24 + c * 40, y + 26 + r * 36, 6.5,
                         fill="#0a0a0e", stroke=colour, sw=1.2)
        s.text(x + blk_w * sc / 2, y + blk_h * sc + 13, label, size=9,
               fill=colour, anchor="middle", weight="700", spacing="0.1em")

    dx, dy = mm(88.0, 25.0)
    s.circle(dx, dy, 6.5 * sc, fill="#151520", stroke=GREEN, sw=1.6)
    s.circle(dx, dy, 3.4, fill=GREEN)
    s.text(dx, dy + 6.5 * sc + 15, "AERIAL", size=9, fill=GREEN,
           anchor="middle", weight="700", spacing="0.1em")

    fx, fy = mm(112.0, 7.0)
    s.rect(fx, fy, 20 * sc, 13 * sc, fill="#151520", stroke=GREEN, sw=1.4,
           rx=3)
    s.text(fx + 10 * sc, fy + 8 * sc, "FUSE", size=9.5, fill=GREEN,
           anchor="middle", weight="600")

    lx, ly = mm(142.0, 29.0)
    s.rect(lx, ly, 30 * sc, 14 * sc, fill="#0e0e12", stroke=CLIP, sw=1.2,
           rx=3, dash="4 3")
    s.text(lx + 15 * sc, ly + 8.5 * sc, "OLD LINE OUT", size=8.5, fill=CLIP,
           anchor="middle")

    # ---- the label column, with leaders back to what each one means
    ly0 = by + BACK_H * sc + 40
    items = [
        (BLUE,  "ISO  A — power", "permanent, ignition, dimmer, earth. "
         "Four wires you would otherwise crimp."),
        (GREEN, "ISO  B — speakers", "all four pairs, already run to the "
         "corners of the car."),
        (GREEN, "AERIAL", "DIN 41585. Your car's adapter plugs straight "
         "into it."),
        (GREEN, "FUSE and protection", "already rated for a car, already "
         "reverse-polarity protected."),
        (CLIP,  "⚠️ OLD LINE OUT, if fitted", "these come off the preamp you "
         "are deleting. Dead until rewired."),
    ]
    col_w = (W - 56 - 4 * 14) / 5
    for i, (colour, head, body) in enumerate(items):
        x = 28 + i * (col_w + 14)
        s.rect(x, ly0, col_w, 92, fill=PANEL, stroke=EDGE, rx=4)
        s.rect(x, ly0, 3, 92, fill=colour, rx=1.5)
        s.text(x + 12, ly0 + 20, head, size=9, fill=colour, weight="700")
        for j, line in enumerate(wrap(body, 26)):
            s.caption(x + 12, ly0 + 38 + j * 13, line, size=8.5)

    y = ly0 + 116
    s.rect(28, y, W - 56, 122, fill="#0f0f14", stroke=EDGE, rx=5)
    s.rect(28, y, 3, 122, fill=GREEN, rx=1.5)
    s.text(44, y + 24, "WHY THIS IS THE CHEAPEST PART OF THE REUSE ROUTE",
           size=9.5, fill=HOT, spacing="0.12em")
    for i, (head, body, col) in enumerate((
            ("It is free, and it is not a job.",
             "the connectors stay on the pressing, and the pressing stays on "
             "the chassis. Nothing to unbolt.", GREEN),
            ("It removes £8–15 of adapters",
             "— an ISO power tail and an ISO speaker tail, otherwise bought "
             "and crimped one pin at a time.", GREEN),
            ("On an OEM donor, the harness adapter goes too:",
             "the back panel already carries your car's exact connector.",
             AMBER),
            ("⚠️ Meter it before you trust it.",
             "ISO 10487 standardises the connector, not the pinout — A4 and "
             "A7 get swapped. True of a bought adapter too.", CLIP))):
        ry = y + 48 + i * 20
        s.text(44, ry, head, size=9, fill=col, weight="600", mono=False)
        # A fixed body column rather than one measured from the heading's
        # length: there is no text metric here, and a guessed one put the
        # longest heading straight through its own sentence.
        s.caption(404, ry, body, size=9)

    s.caption(28, H - 14,
              "⚠️  Layout is indicative — every manufacturer arranges the "
              "back panel differently. The connector standards are not.",
              fill=CLIP)
    return s.save(os.path.join(out, "reuse-rear.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    for fn in (amplifier, back_panel):
        p = fn(out)
        print(f"  {os.path.relpath(p, ROOT):<38} "
              f"{os.path.getsize(p) / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
