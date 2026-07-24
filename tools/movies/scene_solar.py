#!/usr/bin/env python3
"""SOLAR — a tour of the solar system, one body at a time.

The camera runs outward from the Sun, stopping at each planet: drift in, hold
while it turns and its name comes up, then move on. Built for a 4:1 head-unit
strip, so it is composed as a frieze — the tour moves sideways across the panel
rather than the subject sitting in the middle of it.

    python3 tools/movies/scene_solar.py             # 256x64, the SSD1322 build
    python3 tools/movies/scene_solar.py 192 48      # the legacy PC faceplate
    python3 tools/movies/scene_solar.py --legacy    # ...and install it there

Design notes, since the constraints are unusual (docs/MOVIE-RENDERING.md):

  * Four brightness levels and no colour, so the planets are distinguished by
    SIZE, SURFACE and MOTION, never by hue. Jupiter gets banding, Saturn gets
    rings, Earth gets a moon, Mars is small and dim, the Sun is emissive.
  * Labels use the deck's own 5x7 ROM at full brightness — text cannot be
    dithered without turning to mush.
  * 10 fps means slow, deliberate camera work. Nothing whips past.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckfont as F
import dmv as M
import render3d as D

LEGACY = "--legacy" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
W = int(ARGS[0]) if len(ARGS) > 0 else 256
H = int(ARGS[1]) if len(ARGS) > 1 else 64
if LEGACY:
    W, H = 192, 48

FPS = 10
# Everything at half the original pace: twice as long at each body and between
# them, AND the spin/orbit rates halved to match. Doubling only the frame counts
# would have kept the rotation rate and just shown more of it.
HOLD = 28          # frames parked at a body
TRAVEL = 16        # frames between bodies
RATE = 1.1         # was 2.2
SS = 2             # supersample; 3 is prettier and much slower

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "movies", f"solar_{W}x{H}.dmv")

# name, radius, orbit x, spin rate, surface shade, tilt
BODIES = [
    ("SUN",      4.60,   0.0, 0.10, 1.00, 0.00),
    ("MERCURY",  0.62,  17.0, 0.30, 0.52, 0.00),
    ("VENUS",    0.95,  26.0, 0.16, 0.86, 0.10),
    ("EARTH",    1.00,  36.0, 0.42, 0.74, 0.41),
    ("MARS",     0.72,  48.0, 0.40, 0.60, 0.44),
    ("CERES",    0.34,  58.0, 0.50, 0.50, 0.06),   # in the belt
    ("JUPITER",  2.70,  72.0, 0.60, 0.80, 0.05),
    ("IO",       0.36,  78.5, 0.45, 0.66, 0.00),   # Jupiter's moon
    ("SATURN",   2.30,  92.0, 0.55, 0.72, 0.47),
    ("TITAN",    0.40,  98.5, 0.38, 0.58, 0.00),   # Saturn's moon
    ("URANUS",   1.55, 112.0, 0.34, 0.66, 1.71),
    ("NEPTUNE",  1.50, 126.0, 0.36, 0.62, 0.49),
    ("PLUTO",    0.32, 138.0, 0.28, 0.48, 0.99),
]

SPHERE = D.icosphere(2)
SPHERE_LO = D.icosphere(1)

# Deterministic starfield — same every render, so a re-render is comparable.
STARS = []
_s = 12345
for _ in range(90):
    _s = (_s * 1103515245 + 12345) & 0x7fffffff
    sx = (_s % 10000) / 10000.0
    _s = (_s * 1103515245 + 12345) & 0x7fffffff
    sy = (_s % 10000) / 10000.0
    _s = (_s * 1103515245 + 12345) & 0x7fffffff
    STARS.append((sx, sy, 1 if (_s % 3) else 2))


# The belt is drawn as projected points, not meshes — sixty tiny spheres would
# cost more than the rest of the frame and read as the same dots anyway.
BELT = []
_b = 987654321
for _ in range(150):
    _b = (_b * 1103515245 + 12345) & 0x7fffffff
    ang = (_b % 10000) / 10000.0 * 6.28318
    _b = (_b * 1103515245 + 12345) & 0x7fffffff
    rr = 9.0 + (_b % 10000) / 10000.0 * 7.0
    _b = (_b * 1103515245 + 12345) & 0x7fffffff
    yy = ((_b % 10000) / 10000.0 - 0.5) * 1.6
    BELT.append((math.cos(ang) * rr, yy, math.sin(ang) * rr))
BELT_CX = 58.0


def draw_belt(fb, cam, t):
    spin = D.roty(t * 0.03)
    for p in BELT:
        w = D.vadd(D.mv(spin, p), (BELT_CX, 0.0, 0.0))
        pr = cam.proj(w)
        if pr is None:
            continue
        x, y, z = pr
        if not (0 <= x < fb.w and 0 <= y < fb.h):
            continue
        i = int(y) * fb.w + int(x)
        if z < fb.zb[i]:
            fb.zb[i] = z
            fb.buf[i] = 200 if z < 26 else 120


def ring_mesh(inner, outer, segs=28):
    """Flat annulus for Saturn — two triangles per segment, both faces, so it
    stays visible from underneath as the camera rises."""
    verts, tris = [], []
    for s in range(segs):
        a = 2 * math.pi * s / segs
        ca, sa = math.cos(a), math.sin(a)
        verts.append((inner * ca, 0.0, inner * sa))
        verts.append((outer * ca, 0.0, outer * sa))
    for s in range(segs):
        s2 = (s + 1) % segs
        i0, o0, i1, o1 = s * 2, s * 2 + 1, s2 * 2, s2 * 2 + 1
        tris += [(i0, o0, o1), (i0, o1, i1), (i0, o1, o0), (i0, i1, o1)]
    return verts, tris


RINGS = ring_mesh(1.35, 2.25)


def banded_shade(base, world_y, radius):
    """Jupiter's belts: latitude bands, because a flat-shaded sphere with no
    texture and no colour is otherwise just a disc."""
    lat = max(-1.0, min(1.0, world_y / max(0.001, radius)))
    return base * (0.78 + 0.30 * (0.5 + 0.5 * math.sin(lat * 7.5)))


def build_timeline():
    """(body index, phase 0..1 through its segment, kind) per frame."""
    tl = []
    for bi in range(len(BODIES)):
        for f in range(HOLD):
            tl.append((bi, f / max(1, HOLD - 1), "hold"))
        if bi < len(BODIES) - 1:
            for f in range(TRAVEL):
                tl.append((bi, f / max(1, TRAVEL - 1), "travel"))
    return tl


TIMELINE = build_timeline()
NF = len(TIMELINE)


def ease(t):
    return t * t * (3 - 2 * t)


def camera_for(bi, phase, kind):
    """Eye and target. Holding = slow push in; travelling = slide to the next."""
    name, rad, ox, spin, shade, tilt = BODIES[bi]
    if kind == "hold":
        # Framing is deliberately NOT proportional to radius. Distance = k*rad
        # would frame every planet identically and throw away the one thing
        # that distinguishes them without colour: Jupiter has to look bigger
        # than Mercury. This keeps a floor distance so small bodies stay small.
        # 3.2 + 3.5r frames the Sun to just fill the panel height and leaves
        # Mercury a little over a third of it — enough that scale reads without
        # the small bodies becoming specks.
        dist = 3.2 + rad * 3.5 - rad * 0.30 * ease(phase)
        tx = ox
        trad = rad
    else:
        n = BODIES[bi + 1]
        e = ease(phase)
        tx = ox + (n[2] - ox) * e
        trad = rad + (n[1] - rad) * e
        # pull back through the middle of the move so the scale change reads
        dist = 3.2 + (rad + n[1]) * 1.75 + 7.0 * math.sin(math.pi * e)
    height = trad * 0.55 + 0.8
    return (tx - dist * 0.32, height, -dist), (tx, 0.0, 0.0)


def draw_stars(fb, cw, ch):
    for (sx, sy, lvl) in STARS:
        x, y = int(sx * cw), int(sy * ch)
        fb.buf[y * cw + x] = 90 if lvl == 1 else 150


def scene(fi):
    bi, phase, kind = TIMELINE[fi]
    t = fi / FPS

    def draw(fb, cw, ch):
        draw_stars(fb, cw, ch)
        eye, target = camera_for(bi, phase, kind)
        cam = D.Cam(eye, target, cw, ch, f=cw * 0.5)
        if abs(target[0] - BELT_CX) < 34:
            draw_belt(fb, cam, t)

        # Draw every body; the z-buffer and the frustum sort out what is seen.
        for (name, rad, ox, spin, shade, tilt) in BODIES:
            if abs(ox - target[0]) > 46:
                continue                      # far off-screen, skip the work
            rot = D.mmul(D.roty(t * spin * RATE), D.rotx(tilt * 0.6))
            model = tuple(tuple(c * rad for c in row) for row in rot)
            verts, tris = SPHERE if rad > 1.2 else SPHERE_LO

            if name == "SUN":
                D.draw_mesh(fb, cam, verts, tris, model, (ox, 0, 0), 1.0, True)
            elif name == "JUPITER":
                world = [D.vadd(D.mv(model, v), (ox, 0, 0)) for v in verts]
                proj = [cam.proj(p) for p in world]
                for (i0, i1, i2) in tris:
                    p0, p1, p2 = proj[i0], proj[i1], proj[i2]
                    if p0 is None or p1 is None or p2 is None:
                        continue
                    if (p1[0] - p0[0]) * (p2[1] - p0[1]) - \
                       (p1[1] - p0[1]) * (p2[0] - p0[0]) <= 0:
                        continue
                    n = D.norm(D.cross(D.vsub(world[i1], world[i0]),
                                       D.vsub(world[i2], world[i0])))
                    lam = D.clamp(0.22 + 0.78 * max(0.0, D.dot(n, D.LIGHT)), 0, 1)
                    cy = (world[i0][1] + world[i1][1] + world[i2][1]) / 3.0
                    fb.tri(p0, p1, p2, D.clamp(banded_shade(lam * shade, cy, rad), 0, 1))
            else:
                D.draw_mesh(fb, cam, verts, tris, model, (ox, 0, 0), shade)

            if name == "SATURN":
                rr = D.mmul(D.roty(t * 0.06), D.rotx(0.42))
                rm = tuple(tuple(c * rad for c in row) for row in rr)
                D.draw_mesh(fb, cam, RINGS[0], RINGS[1], rm, (ox, 0, 0), 0.62)

            if name == "EARTH":
                ma = t * 0.75
                moon = (ox + 2.1 * math.cos(ma), 0.5 * math.sin(ma * 0.7),
                        2.1 * math.sin(ma))
                mm = tuple(tuple(c * 0.28 for c in row) for row in D.IDENT)
                D.draw_mesh(fb, cam, SPHERE_LO[0], SPHERE_LO[1], mm, moon, 0.55)

    return draw


def main():
    print(f"SOLAR — {W}x{H}, {NF} frames, {NF / FPS:.1f}s")
    frames = []
    for fi in range(NF):
        bi, phase, kind = TIMELINE[fi]
        lum = D.render_frame(W, H, scene(fi), ss=SS, fog=(30.0, 90.0))
        rgb = bytearray(len(lum) * 3)
        for i, v in enumerate(lum):
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = v
        levels = M.quantise(rgb, W, H, black=18)

        # Label during the hold, fading in and out by appearing/disappearing —
        # text has to be solid, so it cannot fade by brightness.
        if kind == "hold" and 0.15 < phase < 0.92:
            name = BODIES[bi][0]
            F.plate(levels, W, H, 3, H - 9, name, 3, 1)
            tag = f"{bi + 1}/{len(BODIES)}"
            F.plate(levels, W, H, W - 3 - F.width(tag), H - 9, tag, 2, 1)

        frames.append(levels)
        print(f"  {fi + 1}/{NF} {BODIES[bi][0]:<8} {kind}   ", end="\r", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, "SOLAR SYSTEM", loop=True)
    raw = W * H * NF
    print(f"\nwrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / raw:.1f}% of raw)")
    if LEGACY:
        M.install_legacy(OUT, "SOLAR SYSTEM")
        print("installed into the PC deck — press V on the faceplate")
    # a couple of stills, to check composition without opening anything
    for probe in (HOLD // 2, HOLD * 4 + TRAVEL * 4 + HOLD // 2):
        if probe < NF:
            print(f"\n--- frame {probe} ---")
            print(M.to_ascii(frames[probe], W, H))


if __name__ == "__main__":
    main()
