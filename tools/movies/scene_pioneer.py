#!/usr/bin/env python3
"""PIONEER — dolphins the way a real head unit drew them.

    python3 tools/movies/scene_pioneer.py            # 256x64, SSD1322
    python3 tools/movies/scene_pioneer.py --legacy   # 192x48 + install

There is already a DOLPHINS in this repository and this does not replace it.
That one is *our* reading of the screensaver: bright animals against a dark
sea, which is the natural way to draw on a panel that starts black.

This one is drawn from footage of an actual Pioneer deck playing its own
version, and the striking thing about that footage is that it is **the other
way round**. The panel lights the *sea* — a solid field of it, edge to edge —
and the dolphins are where the light is not. They are holes.

That inversion is the whole scene, and it is worth understanding why a
manufacturer chose it. On a vacuum fluorescent display, lit is the default
state: the phosphor is either excited or it is not, and a big lit field is
what the technology is good at. Drawing the sea as the lit thing gives you a
panel that reads as bright and expensive from across a car park, where the
same picture inverted reads as mostly-off. It is a decision about the glass,
not about dolphins.

WHY IT WORKS ON FOUR LEVELS

The trap with a full-panel lit field is the level-centre rule: the quantiser
puts level *n* at shade (n + 0.5) / 4, so a sea painted at 0.5 is a 50/50
checkerboard covering the whole display, and every dolphin in front of it
loses. Painted at 0.625 it is a solid field of level 2 and the silhouettes cut
straight out of it. Same picture, two lines of difference, and one of them is
unreadable. See CLAUDE.md.

So the palette here is deliberate and there are only four things in it:

    level 0  the dolphins, and the troughs between waves
    level 1  reflections under an animal, and the far sea
    level 2  the sea — a solid field, pinned to 0.625
    level 3  foam, crests, spray, and the analyser bars

WHAT CAME FROM THE FOOTAGE

The clip is 11.7 seconds of a deck on a desk, filmed on a phone, and it does
not survive being imported — the panel's dot grid beats against ours and its
mid-grey lands on the checkerboard (docs/MOVIE-RENDERING.md says so at
length). What it *does* give, once stabilised and thresholded, is the
choreography: animals arriving in twos and threes rather than singly, a
breach that clears the surface completely, reflections directly beneath, and
an analyser block holding the right-hand sixth of the panel the whole time.
All of that is reproduced here. The pixels are drawn; the staging is theirs.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmv as M


LEGACY = "--legacy" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
W = int(ARGS[0]) if len(ARGS) > 0 else 256
H = int(ARGS[1]) if len(ARGS) > 1 else 64
if LEGACY:
    W, H = 192, 48

FPS = 10
NF = 240                                    # 24 s
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "movies", f"pioneer_{W}x{H}.dmv")

# Level centres. Everything in this file is one of these four numbers, and
# that is not tidiness — anything between them dithers.
L0, L1, L2, L3 = 0.0, 0.375, 0.625, 0.875

# The analyser block on the right. In the footage it is always there, always
# moving, and it is a sixth of the panel — leaving it out would be leaving out
# the thing that makes the picture read as a head unit rather than a screensaver.
BAR_W = max(28, W // 6)
SEA_X1 = W - BAR_W - 3                      # the sea ends here
HORIZON = int(H * 0.55)

# The animal, as a closed outline rather than as a mesh.
#
# There is a perfectly good 3D dolphin in scene_dolphins.py and it was tried
# here first. It renders a convincing animal when it is lit — and this one is
# never lit. A silhouette has no interior: shading, depth, the roll of the
# body, the far pectoral, every cue that makes the mesh read, all of it
# collapses to one flat black shape, and what survived looked like a bat.
#
# For a flat silhouette the OUTLINE is the entire signal, so the outline is
# what gets authored. Nose at x=+1, tail at x=-0.15, y up, drawn as one loop
# over the back and returning along the belly. The three features that make a
# viewer say "dolphin" are the beak, the swept dorsal, and the notched
# flukes — everything else is a tapered tube.
DOLPHIN = [
    (1.00,  0.000),                                    # tip of the beak
    (0.90,  0.055), (0.80,  0.090), (0.70,  0.108),    # melon
    (0.58,  0.115),
    (0.50,  0.112), (0.41,  0.250), (0.33,  0.110),    # dorsal fin
    (0.20,  0.092), (0.10,  0.062), (0.03,  0.038),    # taper to the stock
    (-0.06, 0.130), (-0.15, 0.115), (-0.03, 0.005),    # upper fluke + notch
    (-0.15, -0.100), (-0.06, -0.110), (0.03, -0.033),  # lower fluke
    (0.12, -0.060), (0.24, -0.085),                    # belly
    (0.30, -0.090), (0.27, -0.230), (0.42, -0.095),    # pectoral
    (0.55, -0.088), (0.75, -0.062), (0.88, -0.030),    # chin back to the beak
]


# ---------------------------------------------------------------- the sea
def wave(x, t):
    """Surface height at column x, in dots above the horizon line.

    Three components at incommensurate periods so the swell never visibly
    repeats inside a 24-second loop, and slow: at 10 fps a fast wave strobes.
    """
    u = x / max(1.0, SEA_X1)
    return (1.9 * math.sin(u * 7.1 + t * 0.9) +
            1.1 * math.sin(u * 13.3 - t * 1.35) +
            0.6 * math.sin(u * 23.7 + t * 2.1))


def draw_sea(px, t):
    """A solid lit field with wave structure cut into it.

    Drawn as columns rather than as a mesh: the sea here is a backdrop, not a
    surface anything is standing on, and a column loop gives exact control
    over which level every dot lands on — which is the whole game at four
    levels.
    """
    for x in range(SEA_X1):
        wv = wave(x, t)
        surf = HORIZON + int(round(wv))
        for y in range(H):
            if y < surf - 1:
                # Sky, and it is LIT — dimmer than the water, but lit. The
                # reference panel has no black anywhere in it: the display's
                # resting state is on, and the only dark things in the picture
                # are the animals. Painting the sky off would make the breach
                # read as a bright shape against black, which is our DOLPHINS
                # and the opposite of this one.
                v = L1
            elif y < surf + 1:
                # the surface line itself — the brightest thing in the water
                v = L3
            else:
                # The water: one solid field, no gradient. A ramp across this
                # many rows dithers, and the field boils.
                v = L2
            px[y * W + x] = v

    # Foam. Sparse bright dots riding the crests, which is what stops a solid
    # field from looking like a rectangle of light.
    for x in range(0, SEA_X1, 3):
        wv = wave(x, t)
        if wv < 1.1:
            continue
        surf = HORIZON + int(round(wv))
        if ((x * 7 + int(t * 11)) % 17) < 5:
            for yy in (surf - 1, surf):
                if 0 <= yy < H:
                    px[yy * W + x] = L3


# ---------------------------------------------------------------- the animals
class Leap:
    """One dolphin's arc. Out of the water, over, and back in.

    Parameterised by where it enters and how long it is airborne rather than
    by a physical launch velocity: the arc has to fit the panel, and tuning
    gravity until it does is a worse way to spend an evening than saying where
    the animal should be.
    """

    def __init__(self, t0, x0, x1, height, period, scale=1.0):
        self.t0, self.x0, self.x1 = t0, x0, x1
        self.height, self.period, self.scale = height, period, scale

    def state(self, t):
        """(x, y, roll, airborne) in dot coordinates, or None if not up."""
        p = (t - self.t0) / self.period
        if p < 0.0 or p > 1.0:
            return None
        x = self.x0 + (self.x1 - self.x0) * p
        # sin arc: leaves and enters the water at a shallow angle, which is
        # what a real one does and what reads at this size.
        y = HORIZON + wave(x, t) - self.height * math.sin(math.pi * p)
        # pitch follows the tangent of the arc
        roll = -math.cos(math.pi * p) * 0.85
        return x, y, roll, True


def leaps():
    """The choreography, taken off the reference: pairs and threes, never one.

    A lone dolphin crossing an empty sea is what you write first and it looks
    like a screensaver. Two animals leaving the water a beat apart looks like
    something happening.
    """
    out, t = [], 1.0
    while t < NF / FPS:
        # a pair, offset by a third of a second
        # Spread the groups across the width rather than stacking them in one
        # corner. An irrational step so successive groups never land in the
        # same place inside a 24-second loop.
        x0 = 0.06 + 0.72 * ((len(out) * 0.618) % 1.0)
        out.append(Leap(t, SEA_X1 * (x0 - 0.10), SEA_X1 * (x0 + 0.28),
                        H * 0.44, 1.7, 1.0))
        out.append(Leap(t + 0.35, SEA_X1 * (x0 - 0.02), SEA_X1 * (x0 + 0.34),
                        H * 0.34, 1.6, 0.82))
        # every third group, a third animal further out and smaller
        if len(out) % 6 == 2:
            out.append(Leap(t + 0.7, SEA_X1 * (x0 + 0.24), SEA_X1 * (x0 + 0.52),
                            H * 0.25, 1.4, 0.62))
        t += 3.1
    return out


LEAPS = leaps()


def draw_dolphin(px, x, y, roll, scale, level):
    """The mesh, projected and stamped flat at one level.

    No shading at all, on purpose. The animal is a hole in the sea, and a hole
    with a gradient in it is not a hole — it is a grey dolphin, which dithers,
    which is exactly the mush this scene exists to avoid.
    """
    # Nose to tail, in dots, and it has to be BIG. An early pass drew them at
    # a fifth of this and they read as specks of dirt on the panel: with no
    # interior detail the outline is the whole signal, and a small outline is
    # no signal. On the reference panel an animal spans a quarter of the width.
    span = H * 0.72 * scale
    ca, sa = math.cos(roll), math.sin(roll)
    poly = [(x + (px_ * ca - py_ * sa) * span,
             y - (px_ * sa + py_ * ca) * span) for (px_, py_) in DOLPHIN]
    fill_poly(px, poly, level)


def fill_poly(px, poly, level):
    """Even-odd scanline fill.

    Even-odd rather than nonzero winding because the outline is authored by
    hand and self-intersects at the fluke notch if a point is nudged; even-odd
    degrades into a small visual artefact there, where nonzero winding would
    silently drop the whole tail.
    """
    ys = [p[1] for p in poly]
    y0, y1 = max(0, int(min(ys))), min(H - 1, int(max(ys)) + 1)
    n = len(poly)
    for yy in range(y0, y1 + 1):
        cy = yy + 0.5
        xs = []
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if (ay <= cy) != (by <= cy):
                xs.append(ax + (cy - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for xx in range(max(0, int(xs[k])), min(W - 1, int(xs[k + 1]) + 1)):
                px[yy * W + xx] = level


def draw_bars(px, fi):
    """The analyser block. Thirteen columns, peak-hold caps, always moving."""
    n = 13
    x0 = W - BAR_W
    cw = max(1, BAR_W // n)
    for b in range(n):
        # A fake spectrum: low bands slower and taller, high bands twitchy.
        t = fi / FPS
        v = (0.55 + 0.45 * math.sin(t * (1.7 + b * 0.42) + b)) * \
            (1.0 - 0.045 * b)
        top = H - 2 - int(v * (H - 6))
        x = x0 + b * cw
        for y in range(top, H - 1):
            for k in range(cw - 1):
                if x + k < W:
                    px[y * W + x + k] = L2
        # peak cap, one level brighter, which is the detail that makes an
        # analyser look like an analyser rather than a bar chart
        for k in range(cw - 1):
            if x + k < W and 0 <= top - 2 < H:
                px[(top - 2) * W + x + k] = L3


def frame(fi):
    t = fi / FPS
    px = [0.0] * (W * H)
    draw_sea(px, t)

    for lp in LEAPS:
        st = lp.state(t)
        if not st:
            continue
        x, y, roll, _ = st
        # Reflection first, underneath, dimmer and squashed — it goes down
        # where the animal goes up. Drawn before so the animal wins any overlap.
        surf = HORIZON + wave(x, t)
        # Only when the animal is properly clear of the water, and smaller.
        # A reflection drawn for an animal still breaking the surface overlaps
        # it and the pair reads as one large indistinct blob.
        if y < surf - H * 0.12:
            draw_dolphin(px, x, surf + (surf - y) * 0.5, -roll,
                         lp.scale * 0.62, L1)
        draw_dolphin(px, x, y, roll, lp.scale, L0)

    draw_bars(px, fi)

    rgb = bytearray(W * H * 3)
    for i, v in enumerate(px):
        c = int(max(0.0, min(1.0, v)) * 255)
        rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = c
    return M.quantise(rgb, W, H, black=1, stretch=False)


def main():
    print(f"PIONEER — {W}x{H}, {NF} frames, {NF / FPS:.0f}s, {len(LEAPS)} leaps")
    frames = []
    for i in range(NF):
        frames.append(frame(i))
        print(f"  {i + 1}/{NF}", end="\r", flush=True)
    print()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, "PIONEER", loop=True)
    print(f"wrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / (W * H * NF):.1f}% of raw)")
    if LEGACY:
        M.install_legacy(OUT, "PIONEER")
        print("installed into the PC deck — press V on the faceplate")
    # A frame with animals in the air, which is the one worth checking.
    best = max(range(NF), key=lambda i: sum(
        1 for lp in LEAPS if lp.state(i / FPS)))
    print(M.to_ascii(frames[best], W, H))


if __name__ == "__main__":
    main()
