#!/usr/bin/env python3
"""TOUGE — a roadster sideways down a mountain pass, at night.

    python3 tools/movies/scene_touge.py            # 256x64, SSD1322
    python3 tools/movies/scene_touge.py --legacy   # 192x48 + install

The composition problem here is the opposite of the dolphins'. That scene had a
bright subject and needed something dim to sit against. This one is a night
shot: almost everything is black, and the few lit things have to do all the
work. Four decisions follow from that, and they are most of the scene.

**The headlights are the light source — the only one.** There is no key light,
no ambient, no fog term. Every surface is shaded by how much of the car's beam
falls on it, which means the road ahead fades to black on its own at exactly
the distance a real one does. Trying to light this scene globally and then
darken the distance with fog looks like a lit scene someone turned down; making
the beam the light gets night for free, and gets the corner ahead lighting up
as the car turns into it, which is the whole feeling of a night touge run.

**The road is drawn as a ribbon, the scenery as reflectors.** A mountainside
modelled in geometry would be a dark mass against a dark sky — nothing. The
things that actually read at night are the ones built to be seen at night:
white edge lines, guardrail, and the delineator posts every few metres, whose
reflectors go from off to fully lit as the beam sweeps across them. They stream
past the camera and are the entire sensation of speed.

**The drift is a yaw offset, not a physics simulation.** The car's heading is
the road's heading plus a slip angle proportional to how hard the corner is.
That is enough: what reads as a drift at this size is the body pointing
somewhere other than where it is going, and it is stable and cheap where a
simulation would be neither.

**The camera follows the road, not the car.** It sits back along the
centreline, so when the car steps out it swings across the frame instead of
staying pinned in the middle. Locking the camera to the car would cancel out
the one thing the shot is about.
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
NF = 300           # 30 s
SS = 2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "movies", f"touge_{W}x{H}.dmv")


# ---------------------------------------------------------------- the road
# (length m, curvature 1/m, grade). Positive curvature turns right; the grade
# is negative throughout because this is a downhill run, and a road that falls
# away from the camera shows more of itself than one that climbs.
PLAN = [
    (55, 0.000, -0.030),
    (45, 0.020, -0.045),
    (28, 0.000, -0.050),
    (55, -0.016, -0.045),
    (24, 0.000, -0.035),
    (42, 0.045, -0.055),        # hairpin right
    (34, 0.000, -0.040),
    (62, -0.010, -0.030),       # sweeper left
    (28, 0.000, -0.045),
    (44, -0.046, -0.055),       # hairpin left
    (38, 0.000, -0.035),
    (50, 0.022, -0.045),
    (75, 0.000, -0.025),
]

STEP = 1.0                       # sample spacing, metres
HALF = 3.1                       # carriageway half-width
LINE = 0.14                      # edge line half-width


def build_track():
    """Integrate the plan into samples of (pos, heading, curvature)."""
    pts = []
    x, y, z, head = 0.0, 0.0, 0.0, 0.0
    for (length, k, grade) in PLAN:
        for _ in range(int(length / STEP)):
            pts.append((x, y, z, head, k))
            head += k * STEP
            x += math.sin(head) * STEP
            z += math.cos(head) * STEP
            y += grade * STEP
    return pts


TRACK = build_track()
TRACK_M = len(TRACK) * STEP


def at(s):
    """Sample the track at s metres, linearly interpolated. Clamped, not
    wrapped: the movie fades out before it reaches the end."""
    u = D.clamp(s / STEP, 0.0, len(TRACK) - 1.001)
    i = int(u)
    f = u - i
    a, b = TRACK[i], TRACK[i + 1]
    # heading is monotone within a segment, so a plain lerp is safe here
    return ((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f,
             a[2] + (b[2] - a[2]) * f),
            a[3] + (b[3] - a[3]) * f, a[4] + (b[4] - a[4]) * f)


def basis(head):
    """Forward and right vectors for a heading. Right-handed, y up."""
    fwd = (math.sin(head), 0.0, math.cos(head))
    right = (math.cos(head), 0.0, -math.sin(head))
    return fwd, right


def curv_smooth(s, span=18.0):
    """Curvature averaged over the car's length of road.

    The plan is piecewise constant, so raw curvature steps instantly at a
    segment join and the car would snap into full opposite lock in one frame.
    Averaging is what turns those steps into something a driver could have
    done.
    """
    n, tot = 0, 0.0
    d = -span
    while d <= span:
        tot += at(s + d)[2]
        n += 1
        d += 3.0
    return tot / n


# ---------------------------------------------------------------- the car
def loft(stations, chamf=0.10, close=True):
    """Loft a chamfered rectangular tube through (z, halfwidth, ylo, yhi).

    Cross-sections rather than stacked boxes: at 50-odd dots wide the whole car
    is a silhouette, and a silhouette with corners cut reads as a car where a
    box reads as a box.
    """
    verts, tris = [], []
    per = 8
    for (z, hw, ylo, yhi) in stations:
        c = min(chamf, hw * 0.5, (yhi - ylo) * 0.5)
        verts += [(-hw, ylo + c, z), (-hw + c, ylo, z), (hw - c, ylo, z),
                  (hw, ylo + c, z), (hw, yhi - c, z), (hw - c, yhi, z),
                  (-hw + c, yhi, z), (-hw, yhi - c, z)]
    for i in range(len(stations) - 1):
        for k in range(per):
            k2 = (k + 1) % per
            a, b = i * per + k, i * per + k2
            c, d = (i + 1) * per + k, (i + 1) * per + k2
            tris += [(a, c, d), (a, d, b)]
    if close:                                   # flat caps, front and rear
        for k in range(1, per - 1):
            tris.append((0, k, k + 1))
        base = (len(stations) - 1) * per
        for k in range(1, per - 1):
            tris.append((base, base + k + 1, base + k))
    return verts, tris


def cylinder(r, halfw, segs=9):
    """A wheel: a cylinder about the X axis."""
    verts, tris = [], []
    for s in range(segs):
        a = 2 * math.pi * s / segs
        verts += [(-halfw, math.sin(a) * r, math.cos(a) * r),
                  (halfw, math.sin(a) * r, math.cos(a) * r)]
    for s in range(segs):
        s2 = (s + 1) % segs
        a, b = s * 2, s * 2 + 1
        c, d = s2 * 2, s2 * 2 + 1
        tris += [(a, b, d), (a, d, c), (a, d, b), (a, c, d)]
    return verts, tris


def merge(*parts):
    verts, tris = [], []
    for (v, t) in parts:
        off = len(verts)
        verts += v
        tris += [(a + off, b + off, c + off) for (a, b, c) in t]
    return verts, tris


# AP1 proportions, in metres: 4.14 long, 1.75 wide, 1.29 tall, 2.40 wheelbase.
# The long bonnet and the cab set right back are the whole recognisable shape,
# so the stations spend their detail there rather than on the tail.
BODY = loft([
    (-2.07, 0.62, 0.44, 0.78),      # tail panel
    (-1.80, 0.82, 0.36, 0.84),
    (-1.25, 0.87, 0.30, 0.86),      # rear arch
    (-0.70, 0.87, 0.29, 0.88),
    (0.00, 0.85, 0.29, 0.87),
    (0.70, 0.85, 0.29, 0.84),
    (1.25, 0.87, 0.30, 0.80),       # front arch
    (1.78, 0.78, 0.32, 0.70),
    (2.07, 0.58, 0.38, 0.60),       # nose
])

CABIN = loft([
    (-0.90, 0.60, 0.86, 0.94),      # deck behind the seats
    (-0.72, 0.64, 0.86, 1.20),      # rear screen
    (-0.30, 0.68, 0.90, 1.29),      # roof
    (0.16, 0.70, 0.90, 1.26),
    (0.52, 0.72, 0.88, 0.98),       # windscreen base, raked hard
], chamf=0.07)

CAR = merge(BODY, CABIN)
WHEEL = cylinder(0.32, 0.115)
WHEELS = [(0.74, 0.32, 1.20), (-0.74, 0.32, 1.20),
          (0.76, 0.32, -1.20), (-0.76, 0.32, -1.20)]

# Tail lamps: the one part of the car that emits rather than reflects. Kept to
# the outer corners, because a pair of separated lights at the same height is
# what says "back of a car" at a distance where nothing else is legible.
LAMPS = [(0.52, 0.62, -2.08), (-0.52, 0.62, -2.08)]


# ---------------------------------------------------------------- headlights
BEAM_LEN = 46.0
BEAM_COS = 0.938                   # ~20 degrees half-angle


def beam(p, car_pos, car_fwd):
    """How much light lands on a point. 0..1, and the only light in the scene.

    Two terms. The cone is the dipped beam: soft-edged rather than a torch
    spot, with a falloff gentler than inverse-square because a real dipped beam
    is aimed down at the road and so is far more even along it than a point
    source would be.

    The second term is spill, and it is not decoration. The beam points
    *forward from the car*, so by construction it lights nothing under or
    behind the car — which is exactly where the camera is looking. Without
    spill the subject is a black car on black tarmac and the shot has no
    subject. Physically it is beam scatter off the road, the plate lamp and the
    tail lamps; practically it is the pool the silhouette sits in, and it is
    strong enough to hold a *solid* level 1 out to a few metres rather than a
    sparse dither. A sparse dither around a sparsely dithered car is two kinds
    of noise and no subject.
    """
    d = D.vsub(p, car_pos)
    dist = math.sqrt(D.dot(d, d))
    if dist > BEAM_LEN:
        return 0.0
    spill = 1.05 / (1.0 + (dist / 7.0) ** 2)
    if dist < 0.001:
        return spill
    dn = D.vmul(d, 1.0 / dist)
    a = D.dot(dn, car_fwd)
    if a < BEAM_COS:
        return D.clamp(spill, 0.0, 1.0)
    cone = ((a - BEAM_COS) / (1.0 - BEAM_COS)) ** 0.45
    return D.clamp(spill + cone / (1.0 + (dist / 15.0) ** 2), 0.0, 1.0)


# ---------------------------------------------------------------- scenery
SMOKE = []                         # (pos, radius, life)


NEAR = 1.2                         # metres; see quad()

# The chase shot. Wide and close rather than long and far: at 4:1 a longer lens
# leaves the road as a wedge in the middle with a third of the panel dark
# either side, and there is nothing out here at night to put in the gap.
CAM_BACK, CAM_HIGH = 8.5, 2.45
CAM_AHEAD, CAM_AIM_Y = 12.0, 1.05
CAM_F = 0.46

# Shades that land on the *centre* of a level rather than the boundary between
# two. With four levels the quantiser puts level n at shade (n + 0.5) / 4, so
# 0.375 is a solid field of level 1, 0.625 of level 2, 0.875 of level 3 — and
# 0.25 or 0.50, which look like reasonable round numbers, are precisely the
# 50/50 checkerboards. Everything large in this scene is pinned to a centre.
L1, L2, L3 = 0.375, 0.625, 0.875

ASPH_A, ASPH_B = 0.02, L1 - 0.02   # see draw_road
CAR_SHADE = 0.05                   # under the level-1 threshold: a silhouette


def quad(cam, pts, fb, shade):
    """Project four world points and fill, or give up.

    The give-up is the point. `Cam.proj` rejects points behind the lens but a
    point *just* in front projects to an enormous screen coordinate, so a quad
    straddling the near plane — which every road quad under the camera does —
    turns into a triangle the size of the panel. That was the first thing this
    scene did, and it looked like a torn slab of light across the top of the
    frame. Clipping properly would mean splitting the polygon; at this size,
    dropping any quad with a corner nearer than a metry-and-a-half costs
    nothing visible and costs one comparison.
    """
    q = [cam.proj(p) for p in pts]
    if any(v is None or v[2] < NEAR for v in q):
        return
    fb.tri(q[0], q[1], q[2], shade)
    fb.tri(q[0], q[2], q[3], shade)


def draw_road(fb, cam, s_car, car_pos, car_fwd):
    """The ribbon, its edge lines, the guardrail and the reflector posts.

    Drawn from the far end back so that where the z-buffer ties — and it does
    tie, on coplanar road and line quads — the nearer intent wins.
    """
    # Starts just in front of the lens, not just in front of the car. The road
    # has to run off the bottom corners of a 4:1 panel or the shot is a wedge
    # of light in the middle of a lot of nothing.
    s0 = s_car - CAM_BACK + 0.5
    s1 = s_car + BEAM_LEN + 12.0
    step = 2.0
    n = int((s1 - s0) / step)

    ring = []
    for i in range(n + 1):
        s = s0 + i * step
        p, head, _ = at(s)
        _, right = basis(head)
        ring.append((p, right, s))

    for i in range(n - 1, -1, -1):
        (pa, ra, _), (pb, rb, _) = ring[i], ring[i + 1]

        def edge(p, r, off):
            return (p[0] + r[0] * off, p[1] + 0.01, p[2] + r[2] * off)

        mid = D.vmul(D.vadd(pa, pb), 0.5)
        lit = beam(mid, car_pos, car_fwd)
        if lit <= 0.002:
            continue

        # Asphalt, pinned to the centre of level 1 — see L1 above. A large area
        # landing between two levels is a 50/50 checkerboard, and a
        # checkerboard covering a third of the panel is the loudest thing in
        # the frame: it beat both the markings and the car. A near-solid field
        # is quiet, and quiet is what lets a black silhouette and a pair of
        # white lamps read.
        quads = [(-HALF, HALF, ASPH_A + ASPH_B * lit)]
        # Edge lines get the top level. They are the only thing in the frame
        # that tells you where the road goes before the car gets there, so they
        # win every contest for brightness.
        for side in (-1, 1):
            o = side * (HALF - LINE)
            quads.append((o - LINE, o + LINE, 0.10 + (L3 - 0.10) * lit))
        # centre dashes, one level down so they read as markings, not as edges
        if int((ring[i][2] + 400.0) / 4.0) % 2 == 0:
            quads.append((-LINE, LINE, 0.08 + (L2 - 0.08) * lit))

        for (o0, o1, shade) in quads:
            quad(cam, (edge(pa, ra, o0), edge(pa, ra, o1),
                       edge(pb, rb, o1), edge(pb, rb, o0)), fb, shade)

    # Guardrail and delineators, both sides. The rail starts a couple of metres
    # ahead of the car rather than at the camera: a 0.26 m band a metre from
    # the lens is a slab across half the panel, and it was reading as a second
    # road. Ahead of the car it does its actual job, which is to show the shape
    # of the corner before the car gets there.
    for i in range(n - 1, -1, -1):
        (pa, ra, sa), (pb, rb, sb) = ring[i], ring[i + 1]
        if sa < s_car + 2.0:
            continue
        for side in (-1, 1):
            o = side * (HALF + 0.55)
            a0 = (pa[0] + ra[0] * o, pa[1] + 0.52, pa[2] + ra[2] * o)
            b0 = (pb[0] + rb[0] * o, pb[1] + 0.52, pb[2] + rb[2] * o)
            lit = beam(D.vmul(D.vadd(a0, b0), 0.5), car_pos, car_fwd)
            if lit > 0.004:
                a1 = (a0[0], a0[1] + 0.26, a0[2])
                b1 = (b0[0], b0[1] + 0.26, b0[2])
                # the rail is a horizontal band catching the beam nearly
                # edge-on, so it stays under the edge lines and does not
                # compete with them for the top level
                quad(cam, (a0, a1, b1, b0), fb, 0.06 + (L2 - 0.06) * lit)

            # Reflector posts every 8 m. These are one or two dots wide, so by
            # the thin-feature rule they cannot be dim — a dithered post is
            # noise. They are full brightness inside the beam and absent
            # outside it, which is also exactly what a real one does.
            if int(sa) % 8 == 0 and abs(sa - int(sa)) < step:
                head = (pa[0] + ra[0] * o, pa[1] + 0.95, pa[2] + ra[2] * o)
                if beam(head, car_pos, car_fwd) > 0.05:
                    pr = cam.proj(head)
                    if pr is not None:
                        r = D.clamp(34.0 / max(3.0, pr[2]), 0.9, 3.4)
                        fb.dot2(pr[0], pr[1], r, 1.0, pr[2])


def draw_smoke(fb, cam):
    """Tyre smoke, kept deliberately thin.

    With a chase camera "behind the car" is between the car and the lens, so
    smoke is the one element that can cover the subject. It dies fast for that
    reason — enough to say the tyres are alight, never enough to hide what they
    are doing.

    It sits on level 2, one step above the road. Dimmer than the road it is
    invisible; equal to the road it is invisible; it has to be a step brighter
    to exist at all — and a step brighter is also true, because lit smoke over
    unlit tarmac is the brighter of the two.
    """
    for (p, r, life) in SMOKE:
        q = cam.proj(p)
        if q is None:
            continue
        rad = D.clamp(r * 30.0 / max(2.0, q[2]), 0.7, 5.0)
        fb.dot2(q[0], q[1], rad, 0.32 + (L2 - 0.32) * life, q[2])


def step_smoke(car_pos, car_fwd, car_right, slip):
    for i in range(len(SMOKE) - 1, -1, -1):
        p, r, life = SMOKE[i]
        SMOKE[i] = ((p[0], p[1] + 0.10, p[2]), r * 1.16, life - 0.16)
        if life <= 0.16:
            SMOKE.pop(i)
    if abs(slip) < 0.16:
        return
    for side in (-1, 1):
        base = D.vadd(car_pos, D.vadd(D.vmul(car_fwd, -1.20),
                                      D.vmul(car_right, side * 0.76)))
        SMOKE.append(((base[0] - car_fwd[0] * 0.6, 0.22,
                       base[2] - car_fwd[2] * 0.6), 0.30, 1.0))


# ---------------------------------------------------------------- the run
BASE_SPEED = 21.0                  # m/s on a straight


def speed_at(s):
    """Slower where it is tighter. Also the reason the hairpins do not flash
    past in three frames at 10 fps."""
    k = abs(curv_smooth(s, 26.0))
    return BASE_SPEED / (1.0 + 26.0 * k)


def run_profile():
    """Integrate speed to get distance per frame, once, up front."""
    s, out = 6.0, []
    for _ in range(NF):
        out.append(s)
        s += speed_at(s) / FPS
    return out


PROFILE = run_profile()


def scene(fi):
    s = PROFILE[fi]
    k = curv_smooth(s)
    path_pos, path_head, _ = at(s)
    fwd, right = basis(path_head)

    # Racing line: tight to the apex, which is on the inside — the same hand as
    # the curvature, so a left-hander puts the car on the left. It crosses the
    # frame between corners of opposite hand, and that lateral travel is most
    # of what the shot has to look at on the straights.
    lat = D.clamp(k * 42.0, -1.0, 1.0) * (HALF - 1.15)
    car_pos = (path_pos[0] + right[0] * lat, path_pos[1],
               path_pos[2] + right[2] * lat)

    slip = D.clamp(k * 9.0, -0.62, 0.62)
    car_head = path_head + slip
    car_fwd, car_right = basis(car_head)

    def draw(fb, cw, ch):
        # Camera on the centreline, back and up. Following the road rather than
        # the car is what lets the car swing across frame.
        eye_p, eye_head, _ = at(s - CAM_BACK)
        _, eye_right = basis(eye_head)
        eye = (eye_p[0] + eye_right[0] * lat * 0.30, eye_p[1] + CAM_HIGH,
               eye_p[2] + eye_right[2] * lat * 0.30)
        # Look-ahead shortens as the corner tightens. Fixed at twelve metres it
        # is fine on a sweeper and wrong in a hairpin: the aim point is most of
        # a right angle round from the camera's own tangent, so the frame is
        # filled with road the car has not reached and the car itself is out
        # near the edge with the piece of road it is standing on off-screen
        # entirely. It looked like the car was driving on black.
        ahead = CAM_AHEAD * (1.0 - 0.62 * min(1.0, abs(k) / 0.046))
        aim_p, _, _ = at(s + ahead)
        cam = D.Cam(eye, (aim_p[0], aim_p[1] + CAM_AIM_Y, aim_p[2]),
                    cw, ch, f=cw * CAM_F)

        draw_road(fb, cam, s, car_pos, car_fwd)

        rot = D.roty(car_head)
        # Near enough a silhouette. Its own lamps face away from it and there
        # is nothing else out here, so anything that lit the bodywork properly
        # would be a light that does not exist — but a black lump is not a car
        # either. What is left is skylight: upward-facing panels pick up a
        # little, vertical ones almost none, and that alone gives the roofline
        # and the bonnet, which is the whole silhouette at forty dots wide.
        D.draw_mesh(fb, cam, CAR[0], CAR[1], rot, car_pos, CAR_SHADE)
        for (wx, wy, wz) in WHEELS:
            off = D.mv(rot, (wx, wy, wz))
            D.draw_mesh(fb, cam, WHEEL[0], WHEEL[1], rot,
                        D.vadd(car_pos, off), CAR_SHADE * 0.3)
        for (lx, ly, lz) in LAMPS:
            c = D.vadd(car_pos, D.mv(rot, (lx, ly, lz)))
            q = cam.proj(c)
            if q is not None:
                # biased toward the lens so the lamp wins the z-fight with the
                # tail panel it is mounted flush to
                fb.dot2(q[0], q[1], D.clamp(52.0 / max(2.0, q[2]), 1.2, 3.6),
                        1.0, q[2] - 0.35)
        draw_smoke(fb, cam)

    return draw, car_pos, car_fwd, car_right, slip


def main():
    print(f"TOUGE — {W}x{H}, {NF} frames, {NF / FPS:.0f}s, "
          f"{TRACK_M:.0f} m of road")
    frames = []
    for fi in range(NF):
        draw, car_pos, car_fwd, car_right, slip = scene(fi)
        step_smoke(car_pos, car_fwd, car_right, slip)
        lum = D.render_frame(W, H, draw, ss=SS, fog=(1e9, 2e9))

        # Fade both ends. The track does not close, so the loop is a cut; from
        # black to black nobody can see it.
        fade = min(1.0, fi / 8.0, (NF - 1 - fi) / 8.0)
        if fade < 1.0:
            lum = bytearray(int(v * fade) for v in lum)

        rgb = bytearray(len(lum) * 3)
        for i, v in enumerate(lum):
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = v
        levels = M.quantise(rgb, W, H, black=14, stretch=False)
        if 10 <= fi < 34:
            F.plate(levels, W, H, 3, H - 9, "TOUGE DOWNHILL", 3, 1)
        frames.append(levels)
        print(f"  {fi + 1}/{NF}   ", end="\r", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, "TOUGE", loop=True)
    print(f"\nwrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / (W * H * NF):.1f}% of raw)")
    if LEGACY:
        M.install_legacy(OUT, "TOUGE")
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(frames[NF // 3], W, H))


if __name__ == "__main__":
    main()
