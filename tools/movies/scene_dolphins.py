#!/usr/bin/env python3
"""DOLPHINS — the classic head-unit screensaver, in actual 3D.

The deck already has dolphins: `core/screens/ocean.c` plays 2D silhouettes
rasterised from bezier curves, the way the period units did it. This is the
same idea built properly — a real dolphin mesh, a real sea surface, real
perspective — and baked to a movie.

    python3 tools/movies/scene_dolphins.py            # 256x64, SSD1322
    python3 tools/movies/scene_dolphins.py --legacy   # 192x48 + install

Design, for a 4:1 strip with four brightness levels:

  * The sea is a displaced grid, drawn dim, so wave crests catch the light and
    the troughs fall away. It carries the horizon without needing a line.
  * Dolphins are lit brightest, and break the waterline against it — the whole
    read of the shot is a bright arc over a dim sea.
  * Pitch follows velocity. A dolphin that leaves the water nose-first and
    re-enters nose-first is the single thing that makes it look alive; one that
    stays level looks like a thrown fish.
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
NF = 240           # 24 s
SS = 2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "movies", f"dolphins_{W}x{H}.dmv")


# ---------------------------------------------------------------- the animal
def dolphin_mesh(rings=9):
    """A dolphin, built as a tapered body of revolution plus fins.

    Stations run nose (x=1) to tail stock (x=0). The profile matters more than
    the polygon count at this resolution: get the beak, the shoulder and the
    taper right and eight sides is plenty.
    """
    prof = [(0.00, 0.012), (0.08, 0.052), (0.20, 0.086), (0.34, 0.104),
            (0.48, 0.103), (0.62, 0.092), (0.76, 0.068), (0.88, 0.040),
            (1.00, 0.010)]
    verts, tris = [], []
    for (x, r) in prof:
        for s in range(rings):
            a = 2 * math.pi * s / rings
            # slightly taller than wide, like the real animal
            verts.append((x - 0.5, math.sin(a) * r * 1.18, math.cos(a) * r * 0.95))
    n = len(prof)
    for i in range(n - 1):
        for s in range(rings):
            s2 = (s + 1) % rings
            a, b = i * rings + s, i * rings + s2
            c, d = (i + 1) * rings + s, (i + 1) * rings + s2
            tris += [(a, c, d), (a, d, b)]

    def quad(p0, p1, p2, p3):
        i = len(verts)
        verts.extend([p0, p1, p2, p3])
        # both faces: fins are thin, and a culled fin flickers as it turns
        tris.extend([(i, i + 1, i + 2), (i, i + 2, i + 3),
                     (i, i + 2, i + 1), (i, i + 3, i + 2)])

    # dorsal fin — swept back, the most recognisable silhouette cue
    quad((-0.02, 0.10, 0.0), (0.06, 0.24, 0.0), (0.14, 0.22, 0.0), (0.10, 0.09, 0.0))
    # pectorals, one each side, angled down
    for sgn in (1, -1):
        quad((0.10, -0.02, sgn * 0.05), (0.02, -0.12, sgn * 0.17),
             (0.10, -0.13, sgn * 0.18), (0.16, -0.03, sgn * 0.06))
    # tail flukes, horizontal
    quad((-0.50, 0.0, 0.0), (-0.60, 0.02, 0.16), (-0.54, 0.0, 0.19),
         (-0.46, 0.0, 0.04))
    quad((-0.50, 0.0, 0.0), (-0.60, 0.02, -0.16), (-0.54, 0.0, -0.19),
         (-0.46, 0.0, -0.04))
    return verts, tris


DOLPHIN = dolphin_mesh()


# ---------------------------------------------------------------- the sea
SEA_X, SEA_Z = 30, 15
SEA_W, SEA_D = 44.0, 34.0
SUN_POS = (14.0, 2.2, 34.0)


def wave_h(x, z, t):
    return (0.30 * math.sin(x * 0.55 + t * 1.5) +
            0.20 * math.sin(z * 0.42 - t * 1.1) +
            0.12 * math.sin((x + z) * 0.9 + t * 2.1))


def draw_sea(fb, cam, t):
    """Displaced grid. Crests catch the key light and read as glints; the rest
    stays dim so the dolphins own the bright end of the range."""
    pts = []
    for iz in range(SEA_Z + 1):
        z = 2.0 + SEA_D * iz / SEA_Z
        row = []
        for ix in range(SEA_X + 1):
            x = -SEA_W / 2 + SEA_W * ix / SEA_X
            row.append((x, wave_h(x, z, t), z))
        pts.append(row)

    for iz in range(SEA_Z):
        for ix in range(SEA_X):
            p00, p10 = pts[iz][ix], pts[iz][ix + 1]
            p01, p11 = pts[iz + 1][ix], pts[iz + 1][ix + 1]
            for (a, b, c) in ((p00, p01, p11), (p00, p11, p10)):
                q0, q1, q2 = cam.proj(a), cam.proj(b), cam.proj(c)
                if q0 is None or q1 is None or q2 is None:
                    continue
                nrm = D.norm(D.cross(D.vsub(b, a), D.vsub(c, a)))
                lam = max(0.0, D.dot(nrm, D.LIGHT))
                # A sharp knee, not a ramp. A gentle curve lit the whole sea
                # to mid-brightness and the dolphins had nothing to stand out
                # against; a steep power means only near-specular crests glint.
                shade = 0.05 + 0.62 * (lam ** 6)

                # Sun glitter: the column of broken reflection running from the
                # sun back toward the eye. Without it the sun sits on the water
                # like a sticker; with it the sea reads as reflective, which is
                # most of what makes the shot look like water at all.
                mx = (a[0] + b[0] + c[0]) / 3.0
                mz = max(0.001, (a[2] + b[2] + c[2]) / 3.0)
                off = mx - SUN_POS[0] * (mz / SUN_POS[2])
                path = math.exp(-(off * off) / (1.8 + mz * 0.30))
                shade += 0.75 * path * (0.35 + 0.65 * lam)

                fb.tri(q0, q1, q2, min(1.0, shade))


# ---------------------------------------------------------------- the pod
class Dolphin:
    def __init__(self, x0, z, period, offset, scale, speed):
        self.x0, self.z, self.period = x0, z, period
        self.offset, self.scale, self.speed = offset, scale, speed

    def state(self, t):
        """Position and pitch on a parabolic arc, plus whether it is airborne."""
        u = (t * self.speed + self.offset) % self.period
        x = self.x0 + (u - self.period / 2) * 3.2
        air = self.period * 0.42
        if u < air:
            k = u / air
            y = 4.0 * 3.60 * k * (1 - k) - 0.20          # arc peak ~3.4
            vy = 4.0 * 3.60 * (1 - 2 * k) / air
        else:
            y = -0.9 - 0.5 * math.sin((u - air) * 2.0)   # cruising under
            vy = 0.0
        pitch = math.atan2(vy, 3.2 / max(0.001, air))
        return x, y, self.z, pitch, (u < air)


POD = [
    Dolphin(-5.0,  9.0, 7.0, 0.0, 3.0, 1.0),
    Dolphin(3.0, 14.0, 8.5, 3.1, 2.3, 0.85),
    Dolphin(-2.0, 20.0, 9.5, 5.4, 1.7, 0.7),
]

SPRAY = []          # (x, y, z, life) seeded on water entry/exit


def draw_spray(fb, cam):
    for (x, y, z, life) in SPRAY:
        p = cam.proj((x, y, z))
        if p is None:
            continue
        px, py, pz = p
        if 0 <= px < fb.w and 0 <= py < fb.h:
            i = int(py) * fb.w + int(px)
            if pz < fb.zb[i]:
                fb.buf[i] = 255 if life > 3 else 150


def scene(fi):
    t = fi / FPS

    def draw(fb, cw, ch):
        # slow lateral drift, low over the water — the classic screensaver eye
        # Eye just above the water. From higher up the dolphins arc against
        # the sea and vanish into it; from here they break the horizon, which
        # is the whole shot.
        cam = D.Cam((3.0 * math.sin(t * 0.11), 1.15, -9.0),
                    (0.0, 1.60, 16.0), cw, ch, f=cw * 0.52)

        # sun low on the horizon, behind the pod
        sv, st = D.icosphere(1)
        sm = tuple(tuple(c * 2.6 for c in row) for row in D.IDENT)
        D.draw_mesh(fb, cam, sv, st, sm, SUN_POS, 1.0, True)

        draw_sea(fb, cam, t)

        for d in POD:
            x, y, z, pitch, airborne = d.state(t)
            rot = D.mmul(D.roty(-0.18), D.rotz(pitch))
            model = tuple(tuple(c * d.scale for c in row) for row in rot)
            # airborne dolphins are the brightest thing in frame; submerged
            # ones dim right down so the leap reads as the event
            D.draw_mesh(fb, cam, DOLPHIN[0], DOLPHIN[1], model, (x, y, z),
                        1.0 if airborne else 0.30)
        draw_spray(fb, cam)

    return draw


def step_spray(fi):
    """Seed spray as a dolphin crosses the waterline, then let it fall."""
    t = fi / FPS
    for i in range(len(SPRAY) - 1, -1, -1):
        x, y, z, life = SPRAY[i]
        SPRAY[i] = (x, y - 0.16, z, life - 1)
        if life <= 1:
            SPRAY.pop(i)
    prev = (fi - 1) / FPS
    for d in POD:
        y0 = d.state(prev)[1]
        x1, y1, z1, _, _ = d.state(t)
        if (y0 < 0.0) != (y1 < 0.0):                   # crossed the surface
            for k in range(9):
                a = k / 9 * 6.28318
                SPRAY.append((x1 + math.cos(a) * 0.5 * d.scale, 0.15,
                              z1 + math.sin(a) * 0.5 * d.scale, 4 + (k % 4)))


def main():
    print(f"DOLPHINS — {W}x{H}, {NF} frames, {NF / FPS:.0f}s")
    frames = []
    for fi in range(NF):
        step_spray(fi)
        lum = D.render_frame(W, H, scene(fi), ss=SS, fog=(22.0, 60.0))
        rgb = bytearray(len(lum) * 3)
        for i, v in enumerate(lum):
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = v
        levels = M.quantise(rgb, W, H, black=16)
        if fi < 26:
            F.plate(levels, W, H, 3, H - 9, "OCEAN CRUISE", 3, 1)
        frames.append(levels)
        print(f"  {fi + 1}/{NF}   ", end="\r", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, "DOLPHINS", loop=True)
    print(f"\nwrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / (W * H * NF):.1f}% of raw)")
    if LEGACY:
        M.install_legacy(OUT, "DOLPHINS")
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(frames[8], W, H))


if __name__ == "__main__":
    main()
