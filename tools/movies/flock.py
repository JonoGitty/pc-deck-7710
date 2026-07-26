#!/usr/bin/env python3
"""Cut the subjects out of a short clip and re-stage them as a long, looping flock.

    python3 tools/movies/flock.py ducks.gif --name=DUCKS
    python3 tools/movies/flock.py ducks.gif --name=DUCKS --legacy
    python3 tools/movies/flock.py ducks.gif --secs=30 --count=18 --sprites

WHAT THIS IS FOR, AND WHY IT IS NOT import_gif.py

`import_gif.py` plays a clip. That is the right tool when the clip is already
the animation you want. It is the wrong tool when the clip is only the *source
material* — a few seconds of some things drifting, when what you asked for was
more of them, for longer, looping cleanly.

You cannot do any of that to a played-back clip:

  * **More of them.** You cannot add a duck to a bitmap.
  * **Longer.** Five seconds stretched to thirty is the same five seconds six
    times, and a viewer spots the repeat inside two cycles.
  * **A clean loop.** A clip loops where it happens to end, which on real
    footage is a jump you learn to expect at a fixed interval.

So this takes the clip apart instead. The moving subjects are cut out of it as
sprites — the *actual* pixels, with the shading the source had — and then
re-staged: as many as you ask for, over as long as you ask for, on paths whose
periods all divide the movie length so frame N is frame 0 to the dot.

The result is the source's subjects. It is not the source's footage.

HOW THE CUT-OUT WORKS

**The background is the median of the clip.** Anything that moves is, by
definition, not at the same pixel in most frames, so a per-pixel median over
the whole clip is the scene with the subjects removed. This beats a colour key,
which needs telling what colour to key, and beats a brightness threshold, which
fails the moment the subject is darker than part of the background.

**A subject is a pixel far from that background**, in plain RGB distance. Then
the mask is flood-filled into connected components, and a component is a
candidate sprite if it is big enough and does not touch the frame edge —
because one that touches the edge is cut in half, and half a duck re-staged in
open water reads as a rendering fault.

**Candidates are taken from frames spread across the clip**, so the library
gets the subject at several attitudes rather than fifteen copies of one pose.

WHAT IT CANNOT DO

The sprite is a still. Subjects that rotate, flap or deform in a way the eye
tracks will look stiff — this suits things that hold their shape and move
through a field: ducks, balloons, fish, debris, snow. It is also only as good
as the separation: a subject the same colour as its background does not come
out, and the tool says so rather than emitting mush.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmv as M

try:
    from PIL import Image, ImageFilter, ImageSequence
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow")


# --------------------------------------------------------------- reading in
def load(path):
    """Every frame of the GIF as RGB, composited onto black."""
    out = []
    for f in ImageSequence.Iterator(Image.open(path)):
        src = f.convert("RGBA")
        bg = Image.new("RGBA", src.size, (0, 0, 0, 255))
        out.append(Image.alpha_composite(bg, src).convert("RGB"))
    if not out:
        raise SystemExit("no frames in " + path)
    return out


def background(frames, samples=24):
    """Per-pixel median across the clip: the scene with the subjects removed.

    Median rather than mean, because a mean is dragged towards whatever passed
    through — a bright subject leaves a ghost of itself in the background, and
    the ghost then subtracts out of the mask exactly where the subject is.
    """
    w, h = frames[0].size
    step = max(1, len(frames) // samples)
    stack = [f.tobytes() for f in frames[::step]]
    n = w * h
    out = bytearray(n * 3)
    mid = len(stack) // 2
    for i in range(n):
        for c in range(3):
            k = i * 3 + c
            vals = sorted(s[k] for s in stack)
            out[k] = vals[mid]
    return out


def mask_of(frame, bg, thresh):
    """1 where this frame differs from the background by more than `thresh`."""
    px = frame.tobytes()
    n = len(px) // 3
    m = bytearray(n)
    for i in range(n):
        k = i * 3
        d = (abs(px[k] - bg[k]) + abs(px[k + 1] - bg[k + 1])
             + abs(px[k + 2] - bg[k + 2]))
        if d > thresh:
            m[i] = 1
    return m


def components(mask, w, h, min_area):
    """Connected runs of mask, as (area, x0, y0, x1, y1, pixels).

    Iterative flood fill — a recursive one blows the stack on a subject a few
    thousand pixels across, which every subject worth extracting is.
    """
    seen = bytearray(len(mask))
    out = []
    for start in range(len(mask)):
        if not mask[start] or seen[start]:
            continue
        stack, pix = [start], []
        seen[start] = 1
        while stack:
            i = stack.pop()
            pix.append(i)
            x, y = i % w, i // w
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    j = ny * w + nx
                    if mask[j] and not seen[j]:
                        seen[j] = 1
                        stack.append(j)
        if len(pix) < min_area:
            continue
        xs = [i % w for i in pix]
        ys = [i // w for i in pix]
        out.append((len(pix), min(xs), min(ys), max(xs), max(ys), pix))
    return out


def harvest(frames, bg, thresh, min_area, want, edge=1):
    """A library of sprite cut-outs, taken from frames spread across the clip.

    One per sampled frame — the largest fully-visible component in it. Taking
    every component would return the same subject fifteen times over; spreading
    the samples is what gets the subject at several attitudes.
    """
    w, h = frames[0].size
    lib, tried = [], 0
    step = max(1, len(frames) // (want * 2))
    for fi in range(0, len(frames), step):
        if len(lib) >= want:
            break
        tried += 1
        comps = components(mask_of(frames[fi], bg, thresh), w, h, min_area)
        # Fully visible only: a component against the frame edge is cut off,
        # and half a subject re-staged in open water reads as a fault.
        comps = [c for c in comps
                 if c[1] > edge and c[2] > edge and c[3] < w - 1 - edge
                 and c[4] < h - 1 - edge]
        if not comps:
            continue
        area, x0, y0, x1, y1, pix = max(comps, key=lambda c: c[0])
        sw, sh = x1 - x0 + 1, y1 - y0 + 1
        cut = Image.new("RGB", (sw, sh), (0, 0, 0))
        src = frames[fi].load()
        dst = cut.load()
        for i in pix:
            x, y = i % w, i // w
            dst[x - x0, y - y0] = src[x, y]
        lib.append(dict(img=cut, frame=fi, area=area, aspect=sw / sh))
    if not lib:
        raise SystemExit(
            f"nothing separated from the background in {tried} frames.\n"
            "  The subject is too close to the background in colour, or the\n"
            "  clip is a locked-off still. Try --thresh= lower, or check the\n"
            "  clip actually has something moving in it.")
    return lib


def sprite(cut, dots, black, gamma):
    """A cut-out scaled to `dots` tall and quantised to deck levels.

    The stretch is over the *subject's own* range, because the background has
    already been removed — so the whole level budget goes to the subject
    instead of most of it being spent describing water.

    **Nearest level, not the Bayer dither `dmv.quantise` uses.** That is the
    one real departure here and it is the level-centre rule from
    docs/MOVIE-RENDERING.md, applied to a sprite instead of to a sky. A rubber
    duck is a broad even-toned object: its body sits at one luminance, that
    luminance lands between two levels, and an ordered dither renders the whole
    body as a 50/50 checkerboard. Dithering is right for a photograph, where it
    buys tonal resolution the panel does not have. On a fourteen-dot subject it
    buys nothing — there is no room for a pattern to average out at — and costs
    everything: the body reads as texture rather than as a body, the outline
    dissolves into it, and because the checkerboard moves with the sprite every
    frame differs everywhere, which quadrupled the encoded size.

    Snapping to the nearest level instead gives solid fields with real edges
    between them, which is what the head and the flank and the shadow are.

    Level 3 is the ceiling: 4 is the clipping indicator and renders red.
    """
    w = max(3, round(dots * cut.width / cut.height))
    # Blur, then area-average down — not Lanczos. Two different reasons, and
    # both of them showed up as speckle on the finished sprite. The source is a
    # photograph, so it carries grain and wet-plastic specular highlights that
    # are meaningless at fourteen dots but survive a sharp downscale as single
    # bright pixels. And Lanczos rings: at a 12:1 reduction it puts a dark
    # pixel next to every light one, which after quantising is indistinguishable
    # from the dither this function exists to avoid.
    k = max(1.0, cut.height / dots) * 0.5
    im = cut.filter(ImageFilter.GaussianBlur(k)).resize((w, dots), Image.BOX)
    px = im.tobytes()
    lum = [M.luma(px[i * 3], px[i * 3 + 1], px[i * 3 + 2]) for i in range(w * dots)]
    lit = [v for v in lum if v >= black]
    if not lit:
        return {}, w
    lo, hi = min(lit), max(lit)
    span = max(30.0, hi - lo)

    out = {}
    for y in range(dots):
        for x in range(w):
            v = lum[y * w + x]
            if v < black:
                continue
            f = min(1.0, (v - lo) / span) ** gamma
            # Round to the nearest of levels 1..3. The floor is 1, not 0: this
            # pixel is part of the subject — the background was removed before
            # we got here — so the dimmest part of a duck is a dim duck, not a
            # hole in one.
            q = min(3, max(1, round(1 + f * 2)))
            out[(x, y)] = q
    return out, w


def ascii_sprite(sp, w, h):
    ch = " .:*#"
    return "\n".join("".join(ch[sp.get((x, y), 0)] for x in range(w))
                     for y in range(h))


# ------------------------------------------------------------------ staging
# Each subject: where it sits, how big, how many complete rises it makes in the
# whole movie, and its sway and bob cycle counts. EVERY COUNT IS AN INTEGER —
# that is the entire loop guarantee, and it is why these are written out rather
# than drawn from a random seed.
#
# Size doubles as depth. Small ones are far off, so they are slower, dimmer and
# drift less; big ones are near. Nothing else cues distance on a panel with four
# levels and no perspective.
STAGE = [
    # x frac, dots tall, rises, sway cycles, sway px, bob cycles, dim
    (0.04, 17, 2, 2, 3.0, 4, 0),
    (0.13, 11, 3, 3, 2.0, 6, 1),
    (0.21, 15, 2, 2, 3.5, 3, 0),
    (0.30, 12, 4, 4, 2.0, 5, 1),
    (0.37, 18, 2, 1, 4.0, 3, 0),
    (0.46, 10, 4, 3, 1.5, 6, 1),
    (0.54, 16, 2, 2, 3.0, 4, 0),
    (0.62, 13, 3, 3, 2.5, 5, 1),
    (0.70, 18, 2, 1, 3.5, 2, 0),
    (0.78, 11, 4, 4, 2.0, 6, 1),
    (0.86, 15, 3, 2, 3.0, 3, 0),
    (0.94, 12, 3, 3, 2.5, 5, 1),
    (0.09, 13, 3, 2, 2.5, 4, 1),
    (0.26, 10, 4, 4, 1.5, 6, 1),
    (0.42, 14, 3, 3, 2.5, 4, 0),
    (0.58, 11, 4, 2, 2.0, 5, 1),
    (0.74, 14, 3, 3, 3.0, 4, 0),
    (0.90, 10, 4, 4, 1.5, 6, 1),
    (0.17, 16, 2, 2, 3.0, 3, 0),
    (0.34, 11, 4, 3, 2.0, 5, 1),
    (0.50, 13, 3, 2, 2.5, 4, 0),
    (0.66, 10, 4, 4, 1.5, 6, 1),
    (0.82, 17, 2, 1, 3.5, 3, 0),
    (0.98, 12, 3, 3, 2.0, 5, 1),
]


def cast(lib, w, h, count, black, gamma, flip):
    """Assign library sprites to staged positions, largest sprites to the near
    ones so the clearest cut-outs are the ones drawn biggest."""
    scale = h / 64.0
    order = sorted(range(len(lib)), key=lambda i: -lib[i]["area"])
    out = []
    for n, (xf, dots, rises, swayc, swaypx, bobc, dim) in \
            enumerate(STAGE[:count]):
        d = max(8, round(dots * scale))
        cut = lib[order[n % len(order)]]["img"]
        if flip and n % 2:
            cut = cut.transpose(Image.FLIP_LEFT_RIGHT)
        sp, sw = sprite(cut, d, black, gamma)
        if dim:                              # far away: a level down, floor at 1
            sp = {k: max(1, v - 1) for k, v in sp.items()}
        out.append(dict(x=xf * w, sp=sp, sw=sw, sh=d, rises=rises,
                        swayc=swayc, swaypx=swaypx * scale, bobc=bobc,
                        phase=(xf * 7.3) % 1.0))
    return out


def motes(w, n=26):
    """The specks between the subjects. Single dots, dim, faster than the
    subjects — they are what keeps the field reading as a medium once the
    medium itself is black. The source clip has them; at one dot each there is
    nothing to cut out, so they are placed rather than extracted."""
    return [dict(x=(i * 37.7) % w, rises=6 + (i % 4), phase=(i * 0.137) % 1.0,
                 lvl=1 if i % 3 else 2, swayc=2 + (i % 3),
                 swaypx=1.5 + (i % 3) * 0.7) for i in range(n)]


def render(fi, nf, w, h, cast_, motes_):
    fb = bytearray(w * h)
    t = fi / nf                                    # 0..1 over the whole movie

    for b in motes_:
        y = h + 2 - ((t * b["rises"] + b["phase"]) % 1.0) * (h + 4)
        x = b["x"] + math.sin(2 * math.pi * (b["swayc"] * t + b["phase"])) * b["swaypx"]
        xi, yi = round(x) % w, round(y)
        if 0 <= yi < h and b["lvl"] > fb[yi * w + xi]:
            fb[yi * w + xi] = b["lvl"]

    for d in cast_:
        travel = h + d["sh"] + 2
        y = h + 1 - ((t * d["rises"] + d["phase"]) % 1.0) * travel
        sway = math.sin(2 * math.pi * (d["swayc"] * t + d["phase"])) * d["swaypx"]
        # A small vertical wobble on top of the rise: a subject that ascends in
        # a straight line looks winched rather than floating.
        bob = math.sin(2 * math.pi * (d["bobc"] * t + d["phase"] * 2)) * 0.9
        px, py = round(d["x"] + sway) % w, round(y + bob)
        for (sx, sy), lvl in d["sp"].items():
            # X WRAPS, y does not. The field is continuous going round, so a
            # subject straddling the right edge has to come back on the left —
            # clip it instead and the two nearest the seam are permanently
            # half-drawn. Vertically they genuinely do leave: that is the
            # animation.
            x, yy = (px + sx) % w, py + sy
            if 0 <= yy < h:
                i = yy * w + x
                if lvl > fb[i]:
                    fb[i] = lvl
    return fb


# --------------------------------------------------------------------- main
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        sys.exit(__doc__)

    src = args[0]
    legacy = "--legacy" in flags
    w = int(args[1]) if len(args) > 1 else 256
    h = int(args[2]) if len(args) > 2 else 64
    if legacy:
        w, h = 192, 48

    fps, secs, count = 10, 30, 18
    thresh, min_area, black, gamma = 90, 400, 24, 1.0
    name = None
    for f in flags:
        if f.startswith("--fps="):
            fps = int(f.split("=")[1])
        elif f.startswith("--secs="):
            secs = float(f.split("=")[1])
        elif f.startswith("--count="):
            count = int(f.split("=")[1])
        elif f.startswith("--thresh="):
            thresh = int(f.split("=")[1])
        elif f.startswith("--min-area="):
            min_area = int(f.split("=")[1])
        elif f.startswith("--black="):
            black = int(f.split("=")[1])
        elif f.startswith("--gamma="):
            gamma = float(f.split("=")[1])
        elif f.startswith("--name="):
            name = f.split("=", 1)[1]
    name = name or os.path.splitext(os.path.basename(src))[0].upper()
    nf = int(round(secs * fps))
    count = min(count, len(STAGE))

    print(f"\n{name}: {w}x{h}, {nf} frames at {fps} fps = {nf / fps:g} s")
    frames = load(src)
    print(f"  source: {frames[0].size[0]}x{frames[0].size[1]}, "
          f"{len(frames)} frames")

    bg = background(frames)
    lib = harvest(frames, bg, thresh, min_area, want=10)
    print(f"  cut {len(lib)} subjects out of the clip "
          f"(frames {', '.join(str(s['frame']) for s in lib)})")

    cast_ = cast(lib, w, h, count, black, gamma, flip="--no-flip" not in flags)
    print(f"  staged {len(cast_)} of them, "
          f"{min(d['sh'] for d in cast_)}..{max(d['sh'] for d in cast_)} dots tall")

    if "--sprites" in flags:
        for d in cast_[:3]:
            print()
            print(ascii_sprite(d["sp"], d["sw"], d["sh"]))

    motes_ = motes(w)
    out = [render(i, nf, w, h, cast_, motes_) for i in range(nf)]

    # The loop, checked rather than claimed in a comment: frame nf would be
    # frame 0, so render one past the end and compare.
    wrap = render(nf, nf, w, h, cast_, motes_)
    same = sum(1 for a, b in zip(out[0], wrap) if a == b)
    print(f"  loop check: frame {nf} matches frame 0 on "
          f"{100 * same / len(wrap):.2f}% of dots")

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "movies", f"{name.lower()}_{w}x{h}.dmv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = M.write_dmv(path, out, w, h, fps, f"{name} {w}x{h}", loop=True)
    raw = w * h * nf
    print(f"wrote {os.path.relpath(path)}  {len(blob)} bytes "
          f"({100 * len(blob) / raw:.1f}% of raw {raw})")
    if legacy:
        M.install_legacy(path, name)
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(out[nf // 3], w, h))


if __name__ == "__main__":
    main()
