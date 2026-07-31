#!/usr/bin/env python3
"""Make a short clip longer, wider and busier, without redrawing any of it.

    python3 tools/movies/restage.py ducks.gif --name=DUCKS
    python3 tools/movies/restage.py ducks.gif --name=DUCKS --legacy
    python3 tools/movies/restage.py ducks.gif --tiles=4 --band=0.06,0.88 \
            --layers=8 --water=1 --secs=30 --no-complete

WHAT THIS IS FOR

`import_gif.py` plays a clip as it is. That is right when the clip already is
the animation you want. It is the wrong tool when you want *more of what is in
it, for longer, looping* — and none of those three can be done to a played-back
bitmap:

  * **Longer.** Five seconds stretched to thirty is the same five seconds six
    times, and the repeat is obvious inside two cycles.
  * **More of it.** A bitmap has as many ducks as it was filmed with.
  * **A clean loop.** A clip loops where it happens to end.

This keeps the footage — every duck on the panel is the source's own pixels,
moving the way the source moved it — and rebuilds the *staging* around it.

HOW

**The frame is widened by mirror-tiling.** A 200x200 clip on a 4:1 panel is
letterboxed into a third of the glass, and cropped to 4:1 it loses three
quarters of its height. So the canvas is several clips wide — as many as it
takes to match the panel's shape — and the background is mirrored between them,
which makes the seams match exactly rather than approximately: a mirrored edge
is continuous by construction.

**The subjects are layered.** The clip is composited over that water several
times, each copy at its own position, scale and *speed*, carrying only its
moving parts. Four ducks filmed once become twenty-odd on the panel, all with
real photographed motion, because each layer is the real clip.

**Every layer's period divides the movie.** That is the whole loop guarantee: a
layer plays its clip a whole number of times, so at frame 300 all of them are
back at their own frame 0 together. Which period and which starting phase each
layer gets is *solved* rather than chosen — see `solve_timing`, and the comment
above `LAYERS` for the two ways of choosing them by hand that both failed. The
loop is checked rather than claimed: it composes one frame past the end and
compares.

**The background is flattened to one level, and by default that level is 0.**
The level-centre rule from docs/MOVIE-RENDERING.md says it cannot be shaded: the
clip's water is teal, mid-luminance, so spread across four levels it lands on a
boundary and renders as a 50/50 checkerboard the size of the panel, louder than
anything in front of it. Flat at level 1 it is a calm lit field and the clip
still reads as water — but it leaves the subjects only levels 2 and 3, and two
levels is not enough for a duck: it comes out as a flat blob. Black gives them
1, 2 and 3, and the shading is what makes a duck a duck rather than a shape.
`--water=1` if you want the lit field back.

The moving parts are found the same way a locked-off camera always finds them:
**the per-pixel median of the clip is the background**, because anything that
moves is not at the same pixel in most frames. No colour key to tune, and it
does not care whether the subject is lighter or darker than what it is over.

**Subjects the clip cut in half are put back together first**, by `complete.py`,
using the same subjects from frames where they were whole. Played back, a
half-out-of-frame duck is invisible — the missing half is past the edge of the
picture. Here a layer sits in the middle of a wider canvas, so its frame edge is
nowhere in particular, and a duck bisected by an invisible vertical line reads
as a rendering fault. `--no-complete` turns it off.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmv as M

try:
    from PIL import Image, ImageChops, ImageFilter, ImageSequence
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow")

import complete as C

# THE BAND AND THE TILE COUNT ARE MEASURED, NOT SET.
#
# A square clip and a 4:1 panel cannot both be satisfied. Letterbox the whole
# 200x200 frame and it occupies a third of the glass; fit its full height into
# 64 dots and a duck filmed 55 pixels tall arrives 17 dots tall, which is a
# blob. So the clip is cropped to a horizontal BAND — the part of the frame the
# action is in — deep enough that a subject lands at `--dots` dots.
#
# Both numbers used to be constants, and constants tuned on one panel are wrong
# on the next: the same crop that gave 20-dot ducks at 256x64 gave 15-dot blobs
# at 192x48, because a smaller panel needs a TIGHTER crop rather than the same
# crop drawn smaller. So `measure()` finds how tall a subject actually is, the
# band follows from that and the requested dot height, and the tile count
# follows from the band — enough tiles that the canvas is the panel's shape,
# because any other count stretches the picture on the way down.
#
# The cost is vertical travel: subjects enter and leave the band instead of
# crossing the whole frame. On a strip four times wider than it is tall that is
# the right trade, and it is the same call `--trim` makes in import_gif.py.
# How far above the water's own luminance a dot has to be before it counts as
# subject. It wants to be LOW, and that is not obvious: a rubber duck seen
# through water sits only just above the water in luminance, so raising this to
# strip the dim fringe (16 was tried, to lose some formless smudges) strips the
# duck's whole body with it and leaves a bright rim round a hole. Solid ducks
# with a couple of dim smudges beat hollow ducks with none.
FLOOR = 8

# One row per copy of the clip: where it sits, how big it is, how long it takes
# to play the clip once, where in the clip it starts, and how far it slides
# sideways over the movie.
#
# THE PERIODS ARE THE LOOP. Every one divides the movie length, so at the last
# frame every layer is back at its own frame 0 simultaneously. They are also all
# longer than the clip's own 5 s, which slows the footage down — at 10 fps big
# slow movement reads and quick movement strobes.
#
# Scale doubles as depth: the small ones are further away, so they sit lower in
# the frame. Nothing else cues distance on a panel with four levels and no
# perspective.
#
# PHASES ARE SOLVED, NOT CHOSEN.
#
# Two versions of this got it wrong in opposite directions and both are worth
# recording, because the failure looks like a taste problem and is arithmetic.
#
# The first gave every layer a period dividing the movie and no phase at all.
# That is a correct loop and a bad movie: periods that divide 300 also AGREE at
# 300's common factors, so at frame 150 the layers at 60, 75, 100, 150 and 300
# all sat at phase 0.0 or 0.5 — two distinct pictures between fourteen layers.
#
# The second picked phase offsets by hand, spread out and not multiples of each
# other. Better, and still wrong, because it assumed the clip is a steady
# stream. It is not: THIS clip has ducks for its first 38 frames and is empty
# water for the remaining 33. Hand-spread phases therefore produced a panel that
# swung between packed and deserted every few seconds.
#
# So the phases are solved for. `solve_phases` measures how much subject each
# source frame actually contains and then picks each layer's offset to flatten
# the total across the movie — greedy, deterministic, no random seed. Adding a
# constant to a periodic function leaves it exactly as periodic, so the loop
# guarantee is untouched whatever it picks.
#
# Ordered so that any prefix of the table is still well spread — `--layers=N`
# takes the first N.
LAYERS = [
    # x (fraction of canvas), y (fraction of the room a scaled layer has),
    # dy (extra shift in canvas heights), scale, drift in canvas widths
    #
    # dy exists because a full-size layer fills the canvas height exactly and so
    # has no room to be positioned at all. Without it every full-size layer
    # showed its ducks at the same height as every other one, and the panel got
    # a horizontal BAND of ducks with empty water above and below — the clip's
    # own composition, repeated fourteen times instead of being spread out. A
    # layer shifted past the canvas edge simply loses what goes over it, which
    # for things rising out of frame is what should happen anyway.
    (0.00, 0.0,  0.00, 1.00,  0),
    (0.50, 0.0, -0.13, 1.00,  0),
    (0.25, 0.0,  0.11, 1.00,  0),
    (0.75, 0.0, -0.06, 1.00,  0),
    (0.12, 0.7,  0.00, 0.72,  1),
    (0.62, 0.2,  0.00, 0.72, -1),
    (0.37, 0.8,  0.00, 0.55,  1),
    (0.87, 0.4,  0.00, 0.55, -1),
    (0.06, 0.3,  0.00, 0.72,  1),
    (0.56, 0.9,  0.00, 0.55, -1),
    (0.31, 0.5,  0.00, 0.55,  1),
    (0.81, 0.6,  0.00, 0.72, -1),
    (0.43, 0.1,  0.17, 1.00,  0),
    (0.93, 0.9,  0.00, 0.55,  1),
]

# Every one of these divides 300, which is what makes the movie loop: a layer
# plays its clip a whole number of times, so at the last frame all of them are
# back at their own frame 0 together. They are also all longer than the clip's
# own 5 s — at 10 fps big slow movement reads and quick movement strobes.
PERIODS = (50, 60, 75, 100, 150, 300)


def solve_timing(areas, specs, nf, periods, steps=71):
    """Give every layer a period and a phase so the panel stays evenly full.

    **Periods are dealt round-robin, not optimised.** Letting the solver choose
    them looked obviously right and produced the worst bug this tool has had: it
    put eight layers onto three periods — 50, 100 and 150 — which flattens the
    occupancy beautifully and makes the MOVIE REPEAT EVERY 100 FRAMES. 50 and
    100 both divide 100, so at ten-second intervals almost every layer was back
    where it started and the panel showed the same picture. Thirty seconds of
    animation delivering ten, which is the exact thing this tool exists to avoid.
    The lowest-variance answer and the right answer were not the same answer.

    So the periods are dealt out in rotation, which guarantees the spread, and
    only the phases are solved. `areas[i]` is how much subject source frame i
    actually contains; a layer at period p and phase f shows areas[idx(k, p, f)]
    at output frame k, weighted by its size. Greedy over the layers: each takes
    the phase minimising the variance of the running total across the movie.

    Greedy rather than exhaustive because the result only has to be *even* —
    there is no prize for the optimum. Deterministic, with no random seed,
    because everything downstream is byte-compared against its generator.
    """
    n = len(areas)
    total = [0.0] * nf
    out = []
    for i, (_, _, _, scale, _) in enumerate(specs):
        p = periods[i % len(periods)]
        w = scale * scale
        best = None
        for st in range(steps):
            f = st / steps
            curve = [total[k] + w * areas[round(((k % p) / p + f) * n) % n]
                     for k in range(nf)]
            mean = sum(curve) / nf
            cost = sum((v - mean) ** 2 for v in curve)
            if best is None or cost < best[0]:
                best = (cost, f, curve)
        _, f, total = best
        out.append((p, f))
    return out, total


def repeat_check(frames, nf):
    """How close the movie comes to repeating before it is supposed to.

    The loop check proves frame NF equals frame 0. It says nothing about frame
    NF/2 equalling frame 0, and that is a real failure mode: give the layers
    periods that all divide some proper divisor of NF and the movie loops
    correctly at 30 s while actually repeating every 10, which a viewer reads as
    a much shorter animation than they were promised.

    Returns (worst divisor, worst agreement 0..1).
    """
    worst = (0, 0.0)
    d = 2
    divisors = []
    while d <= nf // 2:
        if nf % d == 0:
            divisors.append(nf // d)          # the shift, not the count
        d += 1
    for shift in sorted(set(divisors)):
        if shift < 5:
            continue
        # Over dots lit in EITHER frame, not over the whole panel. Most of this
        # movie is black water, and black matching black is not evidence of
        # anything — measured that way a badly repeating movie still scored 88%
        # and looked fine. Intersection over union of the lit dots is the
        # question actually being asked: are the same things in the same places?
        agree = tot = 0
        for k in range(0, nf, max(1, nf // 12)):
            a, b = frames[k], frames[(k + shift) % nf]
            for x, y in zip(a, b):
                if x or y:
                    tot += 1
                    if x == y:
                        agree += 1
        v = agree / tot if tot else 0.0
        if v > worst[1]:
            worst = (shift, v)
    return worst


def load(path):
    """Every frame of the GIF as RGB, composited onto black."""
    out = [Image.alpha_composite(
               Image.new("RGBA", f.size, (0, 0, 0, 255)), f.convert("RGBA")
           ).convert("RGB")
           for f in ImageSequence.Iterator(Image.open(path))]
    if not out:
        raise SystemExit("no frames in " + path)
    return out


def background(frames, samples=24):
    """Per-pixel median across the clip: the scene with the subjects removed.

    Median rather than mean — a mean is dragged towards whatever passed through,
    so a bright subject leaves a ghost of itself in the background, and the
    ghost then subtracts out of the mask exactly where the subject is.
    """
    w, h = frames[0].size
    stack = [f.tobytes() for f in frames[::max(1, len(frames) // samples)]]
    mid = len(stack) // 2
    out = bytearray(w * h * 3)
    for k in range(w * h * 3):
        out[k] = sorted(s[k] for s in stack)[mid]
    return Image.frombytes("RGB", (w, h), bytes(out))


def border(w, h):
    """How many columns of mask get blanked at the frame edge.

    Shared, because two different things need the same number: the masking,
    which blanks them, and the completion pass, which has to know that a
    subject stopping this far short of the edge was still cut by it.
    """
    return max(2, round(min(w, h) * 0.02))


def subject_mask(frame, bg, thresh, feather=1.0):
    """Where this frame differs from the background: the moving parts.

    Feathered, because a hard mask cut from a photograph leaves a one-pixel
    fringe of background around the subject, and after a 3:1 downscale that
    fringe is a visible dark outline on every duck.
    """
    d = ImageChops.difference(frame, bg).convert("L")
    m = d.point(lambda v: 255 if v > thresh else 0)
    # Blank a border. A clip's outermost columns flicker against the median by
    # a few levels — compression noise, or a camera that is not quite locked
    # off — which the threshold reads as a subject. Composited, that became a
    # thin dotted vertical line down each edge of every layer: not a duck, and
    # the eye goes straight to it because it is the only straight line on the
    # panel.
    w, h = m.size
    e = border(w, h)
    m.paste(0, (0, 0, w, e))
    m.paste(0, (0, h - e, w, h))
    m.paste(0, (0, 0, e, h))
    m.paste(0, (w - e, 0, w, h))
    return m.filter(ImageFilter.GaussianBlur(feather)) if feather else m


def drop_streaks(mask, min_area=20, max_aspect=3.0, max_h=18):
    """Remove mask components that are far wider than they are tall.

    The clip's water surface ripples, and a ripple survives the median as a
    long, thin, bright horizontal component. On this panel that is the worst
    possible object: a one-to-three dot line at full brightness, which the eye
    finds before it finds any duck, and which on a 1-bit panel dithers into a
    dotted rule. Nothing in this clip that is *supposed* to be seen is four
    times wider than it is tall.

    The numbers were measured, not guessed. At a 7px ceiling this missed the
    three that actually mattered — 34x9, 47x13 and 77x16 components sitting four
    pixels from the top of the frame, which is the water's surface, and which
    arrived on the panel as a solid bright horizontal rule with no business
    being there. A duck in this clip is 68px tall, and two side by side are
    still only twice as wide as they are tall, so an 18px ceiling at 3:1 cannot
    reach one.
    """
    w, h = mask.size
    out = mask
    for c in C.components(mask, w, h, min_area):
        x0, y0, x1, y1 = c["box"]
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bh <= max_h and bw >= bh * max_aspect:
            if out is mask:
                out = mask.copy()
            d = out.load()
            for x, y in c["pix"]:
                d[x, y] = 0
    return out


def measure(masks, size, sample=6):
    """How tall a subject is in this clip, and where they mostly are.

    Returns (median subject height in source pixels, median centre row). Both
    are needed before the crop can be chosen, which is why the background and
    the masks are computed on the uncropped frame.

    Median rather than mean: two ducks that overlap merge into one component
    twice the height, and a handful of those drags a mean badly.

    Small components are dropped first, and that is not a detail. The clip is
    full of specks — bubbles, particles, bits of glare — which pass the minimum
    area and are a fraction of a duck tall. Including them put the median at
    32px in a clip whose ducks are 55, so the band came out a third too tight
    and took most of the exemplars with it. A subject is measured against the
    biggest thing in the clip, not against the smallest thing that qualifies.
    """
    w, h = size
    found = []
    for m in masks[::max(1, len(masks) // sample)]:
        for c in C.components(m, w, h, C.MIN_AREA):
            x0, y0, x1, y1 = c["box"]
            found.append((c["area"], y1 - y0 + 1, (y0 + y1) / 2))
    if not found:
        return h // 3, h / 2
    big = max(a for a, _, _ in found)
    keep = [f for f in found if f[0] >= 0.25 * big] or found
    hs = sorted(f[1] for f in keep)
    ys = sorted(f[2] for f in keep)
    return hs[len(hs) // 2], ys[len(ys) // 2]


def water(bg, tiles):
    """The background, mirror-tiled to the full canvas width.

    Mirrored rather than repeated: a mirrored edge matches its neighbour
    exactly, so the seams are continuous by construction instead of being
    almost-continuous and showing as vertical bands once quantised.
    """
    w, h = bg.size
    out = Image.new("RGB", (w * tiles, h))
    flipped = bg.transpose(Image.FLIP_LEFT_RIGHT)
    for i in range(tiles):
        out.paste(flipped if i % 2 else bg, (i * w, 0))
    return out


def prepare(pairs, scale):
    """One layer's clip: every frame's subjects, scaled to this layer's size."""
    w, h = pairs[0][0].size
    sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
    if scale == 1.0:
        return pairs, sw, sh
    return ([(f.resize((sw, sh), Image.LANCZOS),
              m.resize((sw, sh), Image.LANCZOS)) for f, m in pairs], sw, sh)


def compose(k, nf, base, layers, cw, ch):
    """One canvas frame: the water, with every layer's subjects over it."""
    out = base.copy()
    for lay in layers:
        clip, lw = lay["clip"], lay["lw"]
        # The layer plays its whole clip once per `period` frames. Because every
        # period divides nf, frame nf puts every layer back at its own frame 0.
        src = clip[round(((k % lay["period"]) / lay["period"] + lay["phase"])
                         * len(clip)) % len(clip)]
        x = lay["x"] + round(lay["drift"] * cw * k / nf)
        x = x % cw if x >= 0 else -((-x) % cw)
        # The canvas is a cylinder, and a completed layer can start left of
        # zero, so try it either side as well as in place.
        for dx in (0, -cw, cw):
            if x + dx + lw > 0 and x + dx < cw:
                out.paste(src[0], (x + dx, lay["y"]), src[1])
    return out


def luminance(canvas, w, h):
    """Canvas -> panel-sized luminance, one value per dot.

    Blurred before the reduction and then area-averaged rather than resampled
    with Lanczos. Both are about the source being a photograph: it carries grain
    and wet-plastic specular highlights that mean nothing at twenty dots and
    survive a sharp downscale as isolated bright pixels, and Lanczos rings at
    this reduction — a dark pixel beside every light one, which quantises into
    something indistinguishable from noise.
    """
    im = canvas.filter(ImageFilter.GaussianBlur(canvas.height / h * 0.4)) \
               .resize((w, h), Image.BOX)
    px = im.tobytes()
    lum = [M.luma(px[i * 3], px[i * 3 + 1], px[i * 3 + 2]) for i in range(w * h)]
    return lum


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        sys.exit(__doc__)

    src = args[0]
    legacy = "--legacy" in flags
    W = int(args[1]) if len(args) > 1 else 256
    H = int(args[2]) if len(args) > 2 else 64
    if legacy:
        W, H = 192, 48

    fps, secs, thresh, water_level, name = 10, 30, 34, 0, None
    tiles, band_top, band_h, nlayers, dots = None, None, None, 10, 20
    for f in flags:
        if f.startswith("--layers="):
            nlayers = int(f.split("=")[1])
        elif f.startswith("--tiles="):
            tiles = int(f.split("=")[1])
        elif f.startswith("--band="):
            band_top, band_h = (float(v) for v in f.split("=")[1].split(","))
        elif f.startswith("--dots="):
            dots = int(f.split("=")[1])
        elif f.startswith("--fps="):
            fps = int(f.split("=")[1])
        elif f.startswith("--secs="):
            secs = float(f.split("=")[1])
        elif f.startswith("--thresh="):
            thresh = int(f.split("=")[1])
        elif f.startswith("--water="):
            water_level = int(f.split("=")[1])
        elif f.startswith("--name="):
            name = f.split("=", 1)[1]
    name = name or os.path.splitext(os.path.basename(src))[0].upper()
    NF = int(round(secs * fps))


    print(f"\n{name}: {W}x{H}, {NF} frames at {fps} fps = {NF / fps:g} s")
    frames = load(src)
    fw, fh = frames[0].size
    print(f"  source: {fw}x{fh}, {len(frames)} frames "
          f"({len(frames) * 70 / 1000:.1f} s as filmed)")

    # Trim the sides first. The clip is darker in its last few columns — a lens
    # vignette, an encoder, or both — and mirror-tiling puts two of those dark
    # edges against each other, which doubles them into a black vertical line at
    # every tile join. Nothing else in the picture is a straight line, so the eye
    # finds them immediately. There is nothing in those columns worth keeping.
    xm = round(fw * 0.03)
    frames = [f.crop((xm, 0, fw - xm, fh)) for f in frames]

    # A per-pixel median does not care what has been cropped off, so the
    # background and the masks are computed ONCE, on the full height, and then
    # cropped along with the frames. That is what makes it affordable to measure
    # the subjects before deciding where to cut.
    bg = background(frames)
    masks = [drop_streaks(subject_mask(f, bg, thresh)) for f in frames]

    subj, mid = measure(masks, frames[0].size)
    if band_top is None:
        # Choose the crop from the measurement rather than from a constant.
        # A duck should land `dots` dots tall, so the band has to be
        # subject_px * H / dots deep, centred on where the subjects actually
        # are. Hand-set band constants worked on the 256x64 panel and put a
        # 15-dot blob on the 192x48 one, because a smaller panel needs a
        # TIGHTER crop, not the same crop drawn smaller.
        band_px = max(24, min(fh, round(subj * H / dots)))
        y0 = max(0, min(fh - band_px, round(mid - band_px * 0.55)))
        y1 = y0 + band_px
    else:
        y0 = round(fh * band_top)
        y1 = min(fh, y0 + round(fh * band_h))

    frames = [f.crop((0, y0, fw - 2 * xm, y1)) for f in frames]
    masks = [m.crop((0, y0, fw - 2 * xm, y1)) for m in masks]
    bg = bg.crop((0, y0, fw - 2 * xm, y1))
    sw, sh = frames[0].size
    if tiles is None:
        # Enough tiles that the canvas is the panel's shape. Any other count
        # stretches the picture on the way down — a 25% horizontal stretch is
        # not subtle on something as round as a duck.
        tiles = max(1, round((W / H) * sh / sw))
    print(f"  band: rows {y0}..{y1} of {fh} — a subject measured {subj}px "
          f"lands ~{round(subj * H / sh)} dots tall")

    base = water(bg, tiles)
    cw, ch = base.size

    # The subjects, with the ones the clip's own frame edge cut in half filled
    # in from frames where they were whole. Without this a layer sitting in the
    # middle of a wider canvas shows half a duck bisected by an invisible line,
    # which reads as a rendering fault rather than as a duck leaving.
    pairs = list(zip(frames, masks))
    margin = 0
    if "--no-complete" not in flags:
        margin = round(sh * 0.30)
        cf, cm = C.complete_clip([p[0] for p in pairs], [p[1] for p in pairs],
                                 margin=margin, tol=border(sw, sh) + 2,
                                 report=print)
        # And again afterwards, with a looser ceiling. Before completion a wide
        # flat component might be a duck the frame cut down to a sliver, and
        # dropping it would throw away something completion could have fixed.
        # After completion anything still that shape is not a duck: it is the
        # water's surface, or a graft that only ever had a sliver to add.
        cm = [drop_streaks(m, max_h=round(sh * 0.16)) for m in cm]
        pairs = list(zip(cf, cm))

    specs = LAYERS[:nlayers]
    usable = [p for p in PERIODS if NF % p == 0]
    if not usable:
        sys.exit(f"no layer period divides {NF} frames — the movie would not "
                 f"loop. Periods are {PERIODS}; try --secs={NF / fps:g} with a "
                 f"frame count one of them divides.")
    areas = [sum(m.histogram()[128:]) for _, m in pairs]
    timing, occupancy = solve_timing(areas, specs, NF, usable)
    lo, hi_o = min(occupancy), max(occupancy)
    mean = sum(occupancy) / len(occupancy)
    print(f"  phases solved: subject cover stays within "
          f"{100 * lo / mean:.0f}%..{100 * hi_o / mean:.0f}% of its mean "
          f"(the clip itself is empty for {100 * sum(1 for a in areas if a < 200) / len(areas):.0f}% of its frames)")

    clips = {}
    layers = []
    for (period, phase), (xf, yf, dy, scale, drift) in zip(timing, specs):
        if scale not in clips:
            clips[scale] = prepare(pairs, scale)
        clip, lw, lh = clips[scale]
        # A completed layer is bigger than the clip it came from — the grafted
        # halves live in the margin — so it is positioned by the size of its
        # ORIGINAL content and then pasted back by the margin. Position the
        # padded image directly and every layer drifts up and left by however
        # much completion happened to add.
        pad = round(margin * scale)
        core_w, core_h = round(sw * scale), round(sh * scale)
        layers.append(dict(clip=clip, lw=lw, lh=lh, period=period, phase=phase,
                           drift=drift, x=round(xf * cw) % cw - pad,
                           y=round((ch - core_h) * yf + dy * ch) - pad,
                           core=core_w))
    print(f"  canvas {cw}x{ch} ({tiles} tiles, mirrored), "
          f"{len(layers)} layers on {sorted({l['period'] for l in layers})}-frame periods")

    # Luminance for every output frame, then one set of level boundaries for the
    # whole movie. Per-frame auto-levels pump: a frame the subjects have left
    # renormalises the water up to full brightness and the panel flashes.
    lums = [luminance(compose(k, NF, base, layers, cw, ch), W, H)
            for k in range(NF)]
    flat = sorted(v for f in lums for v in f[::5])
    wat = flat[len(flat) // 2]                       # the water is most of it
    hi = flat[int(len(flat) * 0.995)]
    print(f"  water sits at {wat:.0f}/255, subjects reach {hi:.0f}/255 — "
          f"water pinned to level {water_level}")

    def quantise(lum):
        fb = bytearray(W * H)
        span = max(30.0, hi - wat)
        for i, v in enumerate(lum):
            if v <= wat + FLOOR:
                fb[i] = water_level                  # flat, no dither: see above
            else:
                t = (v - wat) / span
                q = water_level + 1 + int(min(1.0, t) * (3 - water_level - 1) + 0.5)
                fb[i] = min(3, q)
        return fb

    out = [quantise(l) for l in lums]

    # The loop, checked rather than claimed in a comment: frame NF would be
    # frame 0, so compose one past the end and compare.
    wrap = quantise(luminance(compose(NF, NF, base, layers, cw, ch), W, H))
    same = sum(1 for a, b in zip(out[0], wrap) if a == b)
    print(f"  loop check:   frame {NF} matches frame 0 on "
          f"{100 * same / len(wrap):.2f}% of dots")

    shift, agree = repeat_check(out, NF)
    print(f"  repeat check: the closest it comes to repeating early is "
          f"{shift} frames apart, {100 * agree:.0f}% of the lit dots")
    if agree > 0.80:
        sys.exit(
            f"  FAIL — the movie repeats every {shift} frames "
            f"({shift / fps:g} s), not every {NF} ({NF / fps:g} s).\n"
            "  The layer periods all divide that shift, so every layer is back\n"
            "  where it started. Give them periods whose only common multiple\n"
            "  is the whole movie.")

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "movies", f"{name.lower()}_{W}x{H}.dmv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = M.write_dmv(path, out, W, H, fps, f"{name} {W}x{H}", loop=True)
    raw = W * H * NF
    print(f"wrote {os.path.relpath(path)}  {len(blob)} bytes "
          f"({100 * len(blob) / raw:.1f}% of raw {raw})")
    if legacy:
        M.install_legacy(path, name)
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(out[NF // 3], W, H))


if __name__ == "__main__":
    main()
