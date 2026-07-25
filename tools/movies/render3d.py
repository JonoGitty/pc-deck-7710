#!/usr/bin/env python3
"""render3d — a software 3D renderer for DECK·7710 movies.

Pure Python. No numpy, no GPU, no Blender — because this has to run anywhere
someone might want to make an animation, including inside a container with
nothing but the standard library.

A z-buffered barycentric triangle rasteriser, an eye/target camera, and meshes
that are generated rather than modelled. That is the whole renderer; everything
else is a scene using it.

Three things about it are specific to this display, and they are the ones worth
understanding before you design anything:

  * **The grid is a parameter.** The same scene renders for a 192x48 legacy
    panel or a 256x64 SSD1322. Write scenes against proportions, not pixels.
  * **Output is luminance, not colour.** The deck has five intensity levels and
    no hue, so shading, fog and specular all collapse into one channel. Design
    in brightness: two objects at the same luminance are the same object, no
    matter what colour you imagined them.
  * **Supersampling is on by default.** At this dot pitch an aliased edge reads
    as a different shape — the difference between a dolphin and a submarine.

See docs/MOVIE-RENDERING.md for the techniques and the traps.
"""
import math

# ---------------------------------------------------------------- vec / mat
def vsub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def vadd(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def vmul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


def rotx(a):
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))


def roty(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))


def rotz(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def mmul(m, n):
    return tuple(tuple(sum(m[i][k] * n[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def mv(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


IDENT = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def clamp(v, a, b): return a if v < a else (b if v > b else v)


# ---------------------------------------------------------------- camera
class Cam:
    """Right-handed: `right = cross(up, fwd)`.

    Get this wrong and the whole world is silently x-mirrored — and nothing
    looks wrong until you render text, which is why text is the canary for
    handedness bugs. If a scene feels subtly off, put a letter in it."""

    def __init__(self, eye, target, w, h, f=None):
        self.eye = eye
        self.w, self.h = w, h
        self.f = f if f is not None else w * 0.5
        fwd = norm(vsub(target, eye))
        right = norm(cross((0, 1, 0), fwd))
        up = cross(fwd, right)
        self.R = (right, up, fwd)

    def view(self, p):
        d = vsub(p, self.eye)
        return (dot(self.R[0], d), dot(self.R[1], d), dot(self.R[2], d))

    def proj(self, p):
        v = self.view(p)
        if v[2] < 0.28:
            return None
        return (self.w * 0.5 + self.f * v[0] / v[2],
                self.h * 0.5 - self.f * v[1] / v[2],
                v[2])


# ---------------------------------------------------------------- framebuffer
class FB:
    """Luminance + z. One channel, because the panel has one."""

    __slots__ = ("w", "h", "buf", "zb", "fog_a", "fog_b")

    def __init__(self, w, h, fog=(14.0, 42.0)):
        self.w, self.h = w, h
        self.buf = bytearray(w * h)
        self.zb = [1e9] * (w * h)
        self.fog_a, self.fog_b = fog

    def clear(self):
        for i in range(len(self.buf)):
            self.buf[i] = 0
        for i in range(len(self.zb)):
            self.zb[i] = 1e9

    def tri(self, p0, p1, p2, shade, emissive=False):
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = p0, p1, p2
        w, h = self.w, self.h
        minx = max(0, int(min(x0, x1, x2)))
        maxx = min(w - 1, int(max(x0, x1, x2)) + 1)
        miny = max(0, int(min(y0, y1, y2)))
        maxy = min(h - 1, int(max(y0, y1, y2)) + 1)
        if minx > maxx or miny > maxy:
            return
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-9:
            return
        invd = 1.0 / d
        zmid = (z0 + z1 + z2) / 3.0
        fog = 0.0 if emissive else clamp((zmid - self.fog_a) /
                                         (self.fog_b - self.fog_a), 0.0, 0.9)
        buf, zb = self.buf, self.zb
        for y in range(miny, maxy + 1):
            for x in range(minx, maxx + 1):
                w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) * invd
                if w0 < 0: continue
                w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) * invd
                if w1 < 0: continue
                w2 = 1.0 - w0 - w1
                if w2 < 0: continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                i = y * w + x
                if z < zb[i]:
                    zb[i] = z
                    buf[i] = int(clamp(shade * (1.0 - fog), 0.0, 1.0) * 255)

    def dot2(self, x, y, r, shade, z=None):
        r2 = r * r
        for yy in range(max(0, int(y - r)), min(self.h - 1, int(y + r)) + 1):
            for xx in range(max(0, int(x - r)), min(self.w - 1, int(x + r)) + 1):
                if (xx - x) ** 2 + (yy - y) ** 2 <= r2:
                    i = yy * self.w + xx
                    if z is None or z < self.zb[i]:
                        self.buf[i] = int(clamp(shade, 0.0, 1.0) * 255)

    def to_rgb(self):
        """Grey RGB, for the shared quantiser and any image preview."""
        out = bytearray(len(self.buf) * 3)
        for i, v in enumerate(self.buf):
            out[i * 3] = out[i * 3 + 1] = out[i * 3 + 2] = v
        return out


LIGHT = norm((-0.4, 0.8, -0.45))


def draw_mesh(fb, cam, verts, tris, model_r, model_t, shade_base=1.0,
              emissive=False):
    """Flat-shaded, backface-culled. tris are (i0, i1, i2)."""
    world = [vadd(mv(model_r, v), model_t) for v in verts]
    proj = [cam.proj(p) for p in world]
    for (i0, i1, i2) in tris:
        p0, p1, p2 = proj[i0], proj[i1], proj[i2]
        if p0 is None or p1 is None or p2 is None:
            continue
        if (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]) <= 0:
            continue
        if emissive:
            fb.tri(p0, p1, p2, shade_base, True)
        else:
            n = norm(cross(vsub(world[i1], world[i0]), vsub(world[i2], world[i0])))
            lam = clamp(0.22 + 0.78 * max(0.0, dot(n, LIGHT)), 0.0, 1.0)
            fb.tri(p0, p1, p2, lam * shade_base)


# ---------------------------------------------------------------- meshes
def icosphere(subdiv=1):
    t = (1 + 5 ** 0.5) / 2
    verts = [norm(v) for v in [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]]
    tris = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
            (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
            (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
            (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache, out = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                verts.append(norm(vmul(vadd(verts[a], verts[b]), 0.5)))
                cache[k] = len(verts) - 1
            return cache[k]

        for (a, b, c) in tris:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        tris = out
    return verts, tris


def lathe(profile, segs=10):
    """profile: [(radius, y), ...] revolved about Y."""
    verts, tris = [], []
    for s in range(segs):
        a = 2 * math.pi * s / segs
        ca, sa = math.cos(a), math.sin(a)
        for (r, y) in profile:
            verts.append((r * ca, y, r * sa))
    n = len(profile)
    for s in range(segs):
        s2 = (s + 1) % segs
        for i in range(n - 1):
            a, b = s * n + i, s * n + i + 1
            c, d = s2 * n + i, s2 * n + i + 1
            tris += [(a, b, d), (a, d, c)]
    return verts, tris


def box(w, h, d):
    hw, hh, hd = w / 2, h / 2, d / 2
    verts = [(-hw, -hh, -hd), (hw, -hh, -hd), (hw, hh, -hd), (-hw, hh, -hd),
             (-hw, -hh, hd), (hw, -hh, hd), (hw, hh, hd), (-hw, hh, hd)]
    tris = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
            (2, 3, 7), (2, 7, 6), (1, 2, 6), (1, 6, 5), (0, 4, 7), (0, 7, 3)]
    return verts, tris


# ---------------------------------------------------------------- supersample
def render_frame(w, h, draw, ss=3, fog=(14.0, 42.0)):
    """Render at ss× and box-downsample. `draw(fb, cam_w, cam_h)` does the work.

    Supersampling is what kills the jaggies, and it matters more here than on a
    normal screen: at this dot pitch an aliased edge reads as a different shape
    rather than a rougher one.
    """
    big = FB(w * ss, h * ss, fog=fog)
    draw(big, w * ss, h * ss)
    out = bytearray(w * h)
    n = ss * ss
    for y in range(h):
        for x in range(w):
            acc = 0
            for dy in range(ss):
                row = (y * ss + dy) * big.w + x * ss
                for dx in range(ss):
                    acc += big.buf[row + dx]
            out[y * w + x] = acc // n
    return out
