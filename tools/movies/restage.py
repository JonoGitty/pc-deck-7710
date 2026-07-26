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
quarters of its height. So the canvas is four tiles wide and the water is
mirrored between them, which makes the seams match exactly rather than
approximately — a mirrored edge is continuous by construction.

**The subjects are layered.** The clip is composited over that water several
times, each copy at its own position, scale and *speed*, carrying only its
moving parts. Four ducks filmed once become twenty-odd on the panel, all with
real photographed motion, because each layer is the real clip.

**Every layer's period divides the movie.** That is the whole loop guarantee.
Layer speeds are chosen so that a layer plays its clip a whole number of times
in the output — periods of 60, 75, 100 and 150 frames inside 300 — so at frame
300 every layer is simultaneously back at its own frame 0. That is checked
rather than claimed: it composes one frame past the end and compares.

**The water is flattened to one level.** This is the level-centre rule from
docs/MOVIE-RENDERING.md and it is not optional. The source's water is teal —
mid-luminance — and the deck has four levels, so a shaded body of water lands
across a boundary and renders as a 50/50 checkerboard covering the whole panel,
which beats every duck in it for attention. Pinned to a single level it is a
calm lit field with the ducks bright on top of it, which is what the clip looks
like. `--water=0` for black instead; `--water=2` if the panel is behind dark
glass and 1 vanishes.

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

# THE BAND, AND WHY THERE IS ONE.
#
# A square clip and a 4:1 panel cannot both be satisfied. Letterbox the whole
# 200x200 frame and it occupies a third of the glass; fit its full height into
# 64 dots and a duck filmed 55 pixels tall arrives 17 dots tall, which is a
# blob. So the clip is cropped to a horizontal BAND — the part of the frame the
# action happens in — and the panel shows that band at a scale where a duck is
# twenty dots and reads as a duck.
#
# The cost is vertical travel: subjects enter and leave the band instead of
# crossing the whole frame. On a strip four times wider than it is tall that is
# the right trade, and it is the same call `--trim` makes in import_gif.py —
# look at the source and keep the part of it that belongs on this panel.
BAND_TOP, BAND_HEIGHT = 0.06, 0.88          # fractions of the source frame
TILES = 4                                   # canvas is this many clips wide

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
# THE PHASE COLUMN IS NOT DECORATION.
#
# The first version had none, and the result was a movie that emptied out
# periodically. Periods that all divide 300 also all *agree* at 300's common
# factors: at frame 150 the layers at 60, 75, 100, 150 and 300 sit at phases
# 0.5, 0.0, 0.5, 0.0 and 0.5 — two distinct phases between fourteen layers, so
# every layer showed one of two clip frames and the panel was fourteen copies
# of the same two pictures. The clip is a burst rather than a steady stream, so
# those two pictures were mostly empty water.
#
# A constant phase offset per layer fixes it and costs nothing: adding a
# constant to a periodic function leaves it exactly as periodic, so the loop
# guarantee is untouched. Offsets are deliberately not multiples of each other.
#
# Ordered so that any prefix of the table is still well spread — `--layers=N`
# takes the first N, and the default is deliberately short of what fits. Four
# ducks filmed once, layered eight times, is about twenty-five on the panel; at
# fourteen layers they overlap into clumps that read as one large bright object
# rather than as ducks, which is the same mistake as filling the frame.
LAYERS = [
    # x (fraction of canvas), y (fraction of the room a scaled layer has),
    # scale, period, phase, drift in whole canvas widths over the movie
    (0.00, 0.0, 1.00, 100, 0.00,  0),
    (0.51, 0.0, 1.00,  60, 0.63,  0),
    (0.26, 0.0, 1.00, 150, 0.11,  0),
    (0.76, 0.0, 1.00,  75, 0.37,  0),
    (0.13, 0.7, 0.72, 150, 0.47,  1),
    (0.63, 0.2, 0.72,  75, 0.19, -1),
    (0.38, 0.8, 0.55, 300, 0.71,  1),
    (0.88, 0.4, 0.55,  60, 0.05, -1),
    (0.05, 0.3, 0.72, 100, 0.29,  1),
    (0.55, 0.9, 0.55, 300, 0.53, -1),
    (0.30, 0.5, 0.55,  60, 0.89,  1),
    (0.80, 0.6, 0.72, 150, 0.23, -1),
    (0.44, 0.1, 1.00, 300, 0.81,  0),
    (0.94, 0.9, 0.55,  75, 0.67,  1),
]


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

    fps, secs, thresh, water_level, name = 10, 30, 34, 1, None
    tiles, band_top, band_h, nlayers = TILES, BAND_TOP, BAND_HEIGHT, 8
    for f in flags:
        if f.startswith("--layers="):
            nlayers = int(f.split("=")[1])
        elif f.startswith("--tiles="):
            tiles = int(f.split("=")[1])
        elif f.startswith("--band="):
            band_top, band_h = (float(v) for v in f.split("=")[1].split(","))
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

    bad = [l for l in LAYERS if NF % l[3]]
    if bad:
        sys.exit(f"{NF} frames does not divide the layer periods "
                 f"{sorted({l[3] for l in bad})} — the movie would not loop.\n"
                 f"  Use a length whose frame count they all divide, "
                 f"e.g. --secs={NF / fps:g} needs periods dividing {NF}.")

    print(f"\n{name}: {W}x{H}, {NF} frames at {fps} fps = {NF / fps:g} s")
    frames = load(src)
    fw, fh = frames[0].size
    print(f"  source: {fw}x{fh}, {len(frames)} frames "
          f"({len(frames) * 70 / 1000:.1f} s as filmed)")

    y0 = round(fh * band_top)
    y1 = min(fh, y0 + round(fh * band_h))
    # Trim the sides as well. The clip is darker in its last few columns — a
    # lens vignette, an encoder, or both — and mirror-tiling puts two of those
    # dark edges against each other, which doubles them into a black vertical
    # line at every tile join. Nothing else in the picture is a straight line,
    # so the eye finds them immediately. Cropping the border off is the whole
    # fix; there is nothing in those columns worth keeping.
    xm = round(fw * 0.03)
    frames = [f.crop((xm, y0, fw - xm, y1)) for f in frames]
    sw, sh = frames[0].size
    print(f"  band: rows {y0}..{y1} of {fh} — a duck lands "
          f"~{round(0.28 * fh * H / sh)} dots tall")

    bg = background(frames)
    base = water(bg, tiles)
    cw, ch = base.size

    # The subjects, with the ones the clip's own frame edge cut in half filled
    # in from frames where they were whole. Without this a layer sitting in the
    # middle of a wider canvas shows half a duck bisected by an invisible line,
    # which reads as a rendering fault rather than as a duck leaving.
    pairs = [(f, subject_mask(f, bg, thresh)) for f in frames]
    margin = 0
    if "--no-complete" not in flags:
        margin = round(sh * 0.30)
        cf, cm = C.complete_clip([p[0] for p in pairs], [p[1] for p in pairs],
                                 margin=margin, tol=border(sw, sh) + 2,
                                 report=print)
        pairs = list(zip(cf, cm))

    clips = {}
    layers = []
    for (xf, yf, scale, period, phase, drift) in LAYERS[:nlayers]:
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
                           y=round((ch - core_h) * yf) - pad, core=core_w))
    print(f"  canvas {cw}x{ch} ({tiles} tiles, mirrored), "
          f"{len(layers)} layers at {sorted({l['period'] for l in layers})}-frame periods")

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
            if v <= wat + 8:
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
    print(f"  loop check: frame {NF} matches frame 0 on "
          f"{100 * same / len(wrap):.2f}% of dots")

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
