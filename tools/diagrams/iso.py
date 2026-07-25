"""Isometric solids in SVG — enough to draw a build manual.

WHY ISOMETRIC AND NOT A PHOTOGRAPH OR A PERSPECTIVE RENDER

A photograph needs the thing to exist, and it does not yet. A perspective
render needs a camera the reader has to mentally locate. Isometric needs
neither: parallel edges stay parallel, every distance along an axis is to
scale, and the reader can measure the drawing. It is what every furniture and
toy instruction sheet uses, for exactly those reasons.

The projection is the standard one:

    sx = (x - y) · cos30
    sy = (x + y) · sin30 − z

so +x goes down-right, +y goes down-left, and +z is straight up the page. All
inputs are millimetres, which means the drawing and docs/HARDWARE.md cannot
quietly disagree about how big anything is.

DEPTH IS EXPLICIT, NOT COMPUTED

There is no z-buffer and no BSP tree. Solids are drawn in the order given and
later ones paint over earlier ones, which is the painter's algorithm with the
sorting done by whoever wrote the step. For a build manual that is not a
limitation — the order things are drawn in *is* the order they go together in,
so getting it right is the same work as getting the instruction right.
"""
import math

COS30 = math.cos(math.radians(30))
SIN30 = math.sin(math.radians(30))


def project(p, scale=1.0, ox=0.0, oy=0.0):
    x, y, z = p
    return (ox + (x - y) * COS30 * scale,
            oy + ((x + y) * SIN30 - z) * scale)


def shade(hexcol, f):
    """Multiply a #rrggbb by f. Faces of one solid must differ or the solid
    reads as a flat hexagon — which is the single most common way an
    isometric drawing fails."""
    h = hexcol.lstrip("#")
    if len(h) == 3:                      # #abc is a real thing people write
        h = "".join(c * 2 for c in h)
    if h == "none":
        return "none"
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * f))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def fit(bbox, rect):
    """Camera for a world bounding box inside a page rectangle.

    `bbox` is ((x0,y0,z0), (x1,y1,z1)) in mm, `rect` is (x, y, w, h) in px.
    Returns (scale, ox, oy) for Scene.

    Every step in a manual is given the SAME bbox on purpose, even though most
    steps do not fill it. A camera fitted per step makes the object change size
    from panel to panel, and the reader reads that as the object changing —
    which is precisely the signal a build manual is using to say "something
    happened here".
    """
    (x0, y0, z0), (x1, y1, z1) = bbox
    xs, ys = [], []
    for x in (x0, x1):
        for y in (y0, y1):
            for z in (z0, z1):
                sx, sy = project((x, y, z))
                xs.append(sx)
                ys.append(sy)
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    rx, ry, rw, rh = rect
    scale = min(rw / w, rh / h) if w and h else 1.0
    ox = rx + rw / 2 - (min(xs) + max(xs)) / 2 * scale
    oy = ry + rh / 2 - (min(ys) + max(ys)) / 2 * scale
    return scale, ox, oy


class Scene:
    """A drawing surface in millimetre space.

    `scale` is px per mm and (ox, oy) is where the origin lands on the page.
    Everything else takes millimetres.
    """

    def __init__(self, svg, scale, ox, oy):
        self.s = svg
        self.scale = scale
        self.ox = ox
        self.oy = oy

    def p(self, pt):
        return project(pt, self.scale, self.ox, self.oy)

    def _poly(self, pts, fill, stroke, sw=1.0, op=None, dash=None):
        d = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}"
                     for i, (x, y) in enumerate(self.p(q) for q in pts)) + " Z"
        self.s.path(d, stroke=stroke, sw=sw, fill=fill, dash=dash)
        if op is not None:                       # a translucent overlay pass
            self.s.path(d, stroke="none", sw=0, fill=fill)

    # ---------------------------------------------------------------- solids
    def box(self, origin, size, colour, edge=None, sw=1.0, top_only=False,
            dash=None):
        """A cuboid with its near-bottom corner at `origin`, extending +x, +y,
        +z. Three faces are visible from this angle and that is all that is
        drawn — the hidden three would only cost bytes."""
        x, y, z = origin
        dx, dy, dz = size
        # Edges are LIGHTER than the fill, not darker. On a near-black page a
        # dark outline round a dark solid is no outline at all — the fascia
        # was drawn correctly for two iterations and simply could not be seen.
        # Lightening also gives every solid the same line-art silhouette,
        # which is what makes a stack of parts read as separate parts.
        edge = edge or shade(colour, 1.6)

        top = [(x, y, z + dz), (x + dx, y, z + dz),
               (x + dx, y + dy, z + dz), (x, y + dy, z + dz)]
        if top_only:
            self._poly(top, shade(colour, 1.0), edge, sw, dash=dash)
            return
        # +x face catches the light, +y face is in shadow. Consistent across
        # every solid or the drawing stops reading as one object.
        right = [(x + dx, y, z), (x + dx, y + dy, z),
                 (x + dx, y + dy, z + dz), (x + dx, y, z + dz)]
        left = [(x, y + dy, z), (x + dx, y + dy, z),
                (x + dx, y + dy, z + dz), (x, y + dy, z + dz)]
        self._poly(left, shade(colour, 0.62), edge, sw, dash=dash)
        self._poly(right, shade(colour, 0.82), edge, sw, dash=dash)
        self._poly(top, shade(colour, 1.0), edge, sw, dash=dash)

    def plate(self, origin, size, colour, **kw):
        """A board or panel: a very flat box. Named separately because that is
        what it is in the parts list."""
        self.box(origin, size, colour, **kw)

    def post(self, base, h, r, colour):
        """A standoff, a screw shank, a knob — a cylinder, drawn as a
        rectangle with an ellipse on top, which at this scale is
        indistinguishable from the real projection and far cheaper."""
        x, y, z = base
        cx, cy = self.p((x, y, z))
        tx, ty = self.p((x, y, z + h))
        rx = r * self.scale * COS30 * 2
        ry = r * self.scale * SIN30 * 2
        self.s.path(
            f"M {cx - rx:.1f} {cy:.1f} L {tx - rx:.1f} {ty:.1f} "
            f"L {tx + rx:.1f} {ty:.1f} L {cx + rx:.1f} {cy:.1f} Z",
            fill=shade(colour, 0.7), stroke=shade(colour, 1.6), sw=0.8)
        self.s.parts.append(
            f'<ellipse cx="{tx:.1f}" cy="{ty:.1f}" rx="{rx:.1f}" '
            f'ry="{ry:.1f}" fill="{shade(colour, 1.0)}" '
            f'stroke="{shade(colour, 1.6)}" stroke-width="0.8"/>')

    def hole(self, centre, r, colour="#050507"):
        cx, cy = self.p(centre)
        rx = r * self.scale * COS30 * 2
        ry = r * self.scale * SIN30 * 2
        self.s.parts.append(
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" '
            f'ry="{ry:.1f}" fill="{colour}" stroke="#000" '
            f'stroke-width="0.6"/>')

    # ------------------------------------------------------------- annotation
    def ghost(self, origin, size, colour):
        """Where a part is going to end up: dashed outline, no fill. The
        drop-in target that makes a step read as an action rather than a
        state — without it every panel looks like a finished object and the
        reader has to diff two pictures to find the instruction."""
        x, y, z = origin
        dx, dy, dz = size
        for face in (
                [(x, y, z + dz), (x + dx, y, z + dz),
                 (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
                [(x + dx, y, z), (x + dx, y + dy, z),
                 (x + dx, y + dy, z + dz), (x + dx, y, z + dz)],
                [(x, y + dy, z), (x + dx, y + dy, z),
                 (x + dx, y + dy, z + dz), (x, y + dy, z + dz)]):
            self._poly(face, "none", colour, 1.1, dash="4 3")

    def drop_arrow(self, at, from_h, colour, label=None):
        """The 'this goes in here, downwards' arrow. Always vertical in world
        space, so it always reads as gravity."""
        x, y, z = at
        tx, ty = self.p((x, y, z + from_h))
        bx, by = self.p((x, y, z + 3))
        self.s.path(f"M {tx:.1f} {ty:.1f} L {bx:.1f} {by:.1f}", stroke=colour,
                    sw=2, dash="5 4")
        self.s.path(f"M {bx - 5:.1f} {by - 9:.1f} L {bx:.1f} {by:.1f} "
                    f"L {bx + 5:.1f} {by - 9:.1f}", stroke=colour, sw=2)
        if label:
            self.s.text(tx + 8, ty - 2, label, size=8, fill=colour)

    def measure(self, a, b, label, colour="#7fb4e8", off=14):
        """A dimension between two world points, drawn flat on the page."""
        ax, ay = self.p(a)
        bx, by = self.p(b)
        self.s.line(ax, ay + off, bx, by + off, stroke=colour, sw=0.9)
        self.s.line(ax, ay + off - 4, ax, ay + off + 4, stroke=colour, sw=0.9)
        self.s.line(bx, by + off - 4, bx, by + off + 4, stroke=colour, sw=0.9)
        self.s.text((ax + bx) / 2, (ay + by) / 2 + off - 6, label, size=8,
                    fill=colour, anchor="middle")
