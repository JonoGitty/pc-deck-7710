#!/usr/bin/env python3
"""DUCKS — rubber ducks rising through black water, for thirty seconds, seamlessly.

    python3 tools/movies/scene_ducks.py            # 256x64, SSD1322
    python3 tools/movies/scene_ducks.py --legacy   # 192x48 + install into the PC deck

WHY THIS IS DRAWN AND NOT IMPORTED

It started as a GIF: 200 x 200, 5.14 seconds, seventy-one frames of rubber
ducks drifting up through teal water. `import_gif.py` would have taken it in one
command — and could not have done what was actually asked, which was *more
ducks*, *thirty seconds*, and *a clean loop*. You cannot add a duck to a bitmap,
and stretching five seconds to thirty means playing the same five seconds six
times.

Two things about the source also had to go, and both are the standing advice in
docs/MOVIE-RENDERING.md rather than anything specific to ducks:

**The water.** It is teal — mid-luminance — and mid-luminance is the one thing
this panel cannot hold. Four levels put it on the 50/50 checkerboard, and a
checkerboard covering the whole frame beats every duck in it for attention. So
the water is black and the ducks are lit, which is the dolphins' composition and
the touge's: a bright subject against a dim field.

**The photograph.** Scaled to fourteen dots the traced duck came out almost
entirely at one level — a mushy blob with a suggestion of a beak. Drawn, the
same fourteen dots carry a bright head, a stub of beak and a body a shade below
them, which is legible on 1-bit glass as well. It also scales, and it does not
bake somebody else's GIF into this repository.

THE LOOP IS EXACT, NOT NEARLY

Every moving thing completes a whole number of cycles in `NF` frames. A duck's
rise is `k` complete traversals; its sway and bob are integer numbers of sine
cycles. So frame `NF` is frame 0 to the dot, and the deck's loop is invisible
rather than a jump you learn to expect at a junction.
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
NF = 300                      # 30 s exactly, and every period divides it

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "movies", f"ducks_{W}x{H}.dmv")


# ------------------------------------------------------------------- the duck
def duck(size, flip=False):
    """A rubber duck `size` dots tall, as {(x, y): level}.

    Proportions are off the source GIF — roughly square overall, a broad low
    body, a round head about a quarter of the height sitting forward, a beak
    stub. Two details are load-bearing at these sizes:

    **The beak.** Two dots at fourteen tall. Without it the silhouette reads as
    a bread roll.

    **The tail is the body swept upward**, column by column, rather than a shape
    drawn beside it. Anything placed alongside detaches into a floating island
    of dots at twelve dots tall, which is exactly the size this has to work at.
    """
    WD = int(round(size * 1.15))
    out = {}

    def put(x, y, lvl):
        if 0 <= x < WD and 0 <= y < size:
            out[(x, y)] = max(out.get((x, y), 0), lvl)

    bx, by = WD * 0.52, size * 0.72
    brx, bry = WD * 0.46, size * 0.30
    hx, hy, hr = WD * 0.30, size * 0.26, size * 0.24

    for y in range(size):
        for x in range(WD):
            fx, fy = (x - bx) / brx, (y - by) / bry
            if fx * fx + fy * fy <= 1.0:
                put(x, y, 3 if fy < -0.45 else 2)
            dx, dy = x - hx, y - hy
            if dx * dx + dy * dy <= hr * hr:
                put(x, y, 3)

    for y in range(int(hy - size * 0.02), int(hy + size * 0.12) + 1):
        for x in range(int(hx - hr - size * 0.16), int(hx - hr + size * 0.04) + 1):
            put(x, y, 3)

    x0, x1 = int(bx + brx * 0.30), int(bx + brx * 1.00)
    for x in range(x0, x1 + 1):
        t = (x - x0) / max(1, x1 - x0)
        rise = int(round(bry * 1.15 * t * t))
        top = next((y for y in range(size) if (x, y) in out), None)
        if top is None:
            continue
        for y in range(max(0, top - rise), top):
            put(x, y, 2)

    if flip:
        out = {(WD - 1 - x, y): v for (x, y), v in out.items()}
    return out, WD


# ------------------------------------------------------------------ the flock
# Each duck: x, size, how many complete rises it makes in NF frames, its sway
# and bob cycle counts, and which way round it faces. Every count is an INTEGER
# — that is the whole loop guarantee, and it is why these are written out
# rather than generated from a random seed.
#
# Size doubles as depth. The small ones are far off, so they are slower, dimmer
# and drift less; the big ones are near. Nothing else cues distance on a panel
# with four levels and no perspective.
def flock(w, h):
    scale = h / 64.0
    spec = [
        # x frac, size, rises, sway cycles, sway px, bob cycles, flip, dim
        (0.04, 17, 2, 2, 3.0, 4, False, 0),
        (0.13, 11, 3, 3, 2.0, 6, True,  1),
        (0.21, 15, 2, 2, 3.5, 3, False, 0),
        (0.30, 12, 4, 4, 2.0, 5, True,  1),
        (0.37, 18, 2, 1, 4.0, 3, False, 0),
        (0.46, 10, 4, 3, 1.5, 6, False, 1),
        (0.54, 16, 2, 2, 3.0, 4, True,  0),
        (0.62, 13, 3, 3, 2.5, 5, False, 1),
        (0.70, 18, 2, 1, 3.5, 2, True,  0),
        (0.78, 11, 4, 4, 2.0, 6, False, 1),
        (0.86, 15, 3, 2, 3.0, 3, True,  0),
        (0.94, 12, 3, 3, 2.5, 5, False, 1),
        (0.09, 13, 3, 2, 2.5, 4, True,  1),
        (0.26, 10, 4, 4, 1.5, 6, False, 1),
        (0.42, 14, 3, 3, 2.5, 4, True,  0),
        (0.58, 11, 4, 2, 2.0, 5, False, 1),
        (0.74, 14, 3, 3, 3.0, 4, False, 0),
        (0.90, 10, 4, 4, 1.5, 6, True,  1),
    ]
    out = []
    for (xf, size, rises, swayc, swaypx, bobc, flip, dim) in spec:
        s = max(8, int(round(size * scale)))
        sprite, sw = duck(s, flip)
        if dim:                       # far away: one level down, floor at 1
            sprite = {k: max(1, v - 1) for k, v in sprite.items()}
        out.append(dict(x=xf * w, sprite=sprite, sw=sw, sh=s, rises=rises,
                        swayc=swayc, swaypx=swaypx * scale, bobc=bobc,
                        phase=(xf * 7.3) % 1.0))
    return out


# Bubbles. Small, dim, faster than the ducks — they are what makes the water
# read as water once the water itself is black.
def bubbles(w, h):
    out = []
    for i in range(26):
        out.append(dict(x=(i * 37.7) % w, rises=6 + (i % 4),
                        phase=(i * 0.137) % 1.0,
                        lvl=1 if i % 3 else 2,
                        swayc=2 + (i % 3), swaypx=1.5 + (i % 3) * 0.7))
    return out


def render(fi, ducks, bubs):
    """One frame, as a level per dot."""
    fb = bytearray(W * H)
    t = fi / NF                       # 0..1 over the whole loop

    def blit(px, py, sprite):
        # X WRAPS, y does not. The water is a continuous field going round, so
        # a duck straddling the right edge has to come back on the left — clip
        # it instead and the two ducks nearest the seam are permanently
        # half-drawn, which reads as a rendering fault rather than as a duck.
        # Vertically they genuinely do leave: that is the whole animation.
        for (sx, sy), lvl in sprite.items():
            x, y = (px + sx) % W, py + sy
            if 0 <= y < H:
                i = y * W + x
                if lvl > fb[i]:
                    fb[i] = lvl

    for b in bubs:
        travel = H + 4
        y = H + 2 - ((t * b["rises"] + b["phase"]) % 1.0) * travel
        x = b["x"] + math.sin(2 * math.pi * (b["swayc"] * t + b["phase"])) * b["swaypx"]
        xi, yi = int(round(x)) % W, int(round(y))
        if 0 <= yi < H:
            i = yi * W + xi
            if b["lvl"] > fb[i]:
                fb[i] = b["lvl"]

    for d in ducks:
        travel = H + d["sh"] + 2
        # Rising: one whole number of traversals per loop, so frame NF == frame 0.
        y = H + 1 - ((t * d["rises"] + d["phase"]) % 1.0) * travel
        sway = math.sin(2 * math.pi * (d["swayc"] * t + d["phase"])) * d["swaypx"]
        # The bob is a small vertical wobble on top of the rise — a duck that
        # ascends in a straight line looks winched rather than floating.
        bob = math.sin(2 * math.pi * (d["bobc"] * t + d["phase"] * 2)) * 0.9
        blit(int(round(d["x"] + sway)) % W, int(round(y + bob)), d["sprite"])

    return fb


def main():
    ducks, bubs = flock(W, H), bubbles(W, H)
    frames = [render(fi, ducks, bubs) for fi in range(NF)]

    # The loop, checked rather than asserted in a comment: frame NF would be
    # frame 0, so render one past the end and compare.
    wrap = render(NF, ducks, bubs)
    same = sum(1 for a, b in zip(frames[0], wrap) if a == b)
    print(f"  loop check: frame {NF} matches frame 0 on "
          f"{100 * same / len(wrap):.2f}% of dots")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, f"DUCKS {W}x{H}", loop=True)
    raw = W * H * NF
    print(f"wrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / raw:.1f}% of raw {raw}), "
          f"{NF} frames = {NF / FPS:.0f} s")
    if LEGACY:
        M.install_legacy(OUT, "DUCKS")
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(frames[NF // 3], W, H))


if __name__ == "__main__":
    main()
