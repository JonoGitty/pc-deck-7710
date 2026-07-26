#!/usr/bin/env python3
"""Complete the subjects a clip cut in half at its own frame edge.

A short loop of things drifting through a field always has some of them
half-out of frame. Play the clip and that is invisible — the missing half is
past the edge of the picture, where the eye expects a picture to stop. Re-stage
it (see `restage.py`) and it is not: a layer sits in the middle of a wider
canvas, so its frame edge is nowhere in particular and a duck bisected by an
invisible vertical line reads as a rendering fault, which is the one thing an
animation cannot afford.

This finds those and fills them in.

WHERE THE MISSING PIXELS COME FROM

**Out of the clip itself, from a frame where that subject was whole.** A duck
clipped by the right edge at second four drifted in from the middle at second
one, and there it is complete: same duck, same lighting, same lens, same
compression. So the completion is not invented, it is *recovered* — the pixels
were filmed, just not in this frame.

The mechanism is exemplar matching, and the whole design follows from the fact
that a clip's frame edge is a straight line:

1. **Harvest.** Every connected subject that touches no edge, in every frame, is
   a complete exemplar. A 71-frame clip of five ducks yields dozens.
2. **Classify.** A subject touching an edge is partial. One touching two
   opposite edges, or edges on both axes, is refused outright — with no free
   extent there is nothing to scale or align against, and a guess at that point
   is a guess.
3. **Align without searching.** Because the cut is a straight edge, the axis
   *not* cut is intact: a duck clipped on the left still shows its true top,
   bottom and right. That gives the exemplar's scale (matched heights) and its
   position (matched right edge) in one step, instead of sweeping offsets and
   scales over every exemplar.
4. **Score, then decide.** The scaled exemplar is compared with the visible part
   over the visible region only — intersection over union. Best over every
   exemplar and both reflections; below `MIN_SCORE` the subject is refused
   rather than completed. A wrong completion is worse than a clipped one,
   because a clipped duck merely looks cut and a wrong one looks broken.
5. **Graft.** Only the pixels *outside* the original frame are taken from the
   exemplar; everything the clip actually filmed is kept. Brightness is matched
   over the overlap first, so the grafted half is not a shade off the half it is
   joined to.

WHY NOT A GENERATIVE MODEL

It would be the obvious reach, and it is the wrong tool three times over:

- **Reproducibility.** Every generated file in this repository is byte-compared
  against its generator in `tools/verify/`. A sampler that returns something
  different each run cannot be checked that way, so the staleness rule — the
  thing that stops the pictures quietly diverging from the code — would have to
  be dropped for this one tool.
- **No network in CI, and none should be needed.** The build must run from a
  clone with Pillow and nothing else.
- **It has no idea what your ducks look like.** A model would invent a plausible
  duck; the clip contains *these* ducks, photographed under this light. Matching
  beats generating whenever the missing content is already in the dataset, and
  here the dataset is the clip.

If someone does want a generative backend, the seam to cut is `match` and
`graft`: everything else — finding the partial subjects, deciding which are
completable at all, and refusing the rest — is independent of where the pixels
come from. Keep the refusal path. It is most of the value.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageChops, ImageFilter

MIN_SCORE = 0.55        # IoU over the visible part, below which we refuse
MIN_AREA = 150          # px in the source frame; smaller things are specks


# ------------------------------------------------------------------ finding
def components(mask, w, h, min_area):
    """Connected runs of a 0/255 mask, as dicts with bbox, area and pixels.

    Iterative flood fill; a recursive one blows the stack on any subject a few
    thousand pixels across, which every subject worth completing is.
    """
    m = mask.load()
    seen = bytearray(w * h)
    out = []
    for sy in range(h):
        for sx in range(w):
            if m[sx, sy] < 128 or seen[sy * w + sx]:
                continue
            stack, pix = [(sx, sy)], []
            seen[sy * w + sx] = 1
            x0 = x1 = sx
            y0 = y1 = sy
            while stack:
                x, y = stack.pop()
                pix.append((x, y))
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] \
                            and m[nx, ny] >= 128:
                        seen[ny * w + nx] = 1
                        stack.append((nx, ny))
            if len(pix) >= min_area:
                out.append(dict(area=len(pix), box=(x0, y0, x1, y1), pix=pix))
    return out


def touched(box, w, h, tol=1):
    """Which frame edges this component runs into."""
    x0, y0, x1, y1 = box
    e = set()
    if x0 <= tol: e.add("L")
    if x1 >= w - 1 - tol: e.add("R")
    if y0 <= tol: e.add("T")
    if y1 >= h - 1 - tol: e.add("B")
    return e


def as_mask(comp, w, h):
    """One component on its own, as an L image the size of the frame."""
    buf = bytearray(w * h)
    for x, y in comp["pix"]:
        buf[y * w + x] = 255
    return Image.frombytes("L", (w, h), bytes(buf))


def area_of(mask):
    """Lit pixels in an L mask. histogram() is a C loop; summing in Python
    over a few hundred thousand pixels, a few thousand times, is not."""
    return sum(mask.histogram()[128:])


# ------------------------------------------------------------- the matching
def exemplars(frames, masks, min_area, tol=1):
    """Every whole subject in the clip, cropped to itself.

    These are the source of every completed pixel: the same subjects, in the
    frames where they happened not to be against an edge.
    """
    out = []
    for f, m in zip(frames, masks):
        w, h = f.size
        for c in components(m, w, h, min_area):
            if touched(c["box"], w, h, tol):
                continue
            x0, y0, x1, y1 = c["box"]
            cm = as_mask(c, w, h).crop((x0, y0, x1 + 1, y1 + 1))
            out.append(dict(rgb=f.crop((x0, y0, x1 + 1, y1 + 1)), mask=cm,
                            w=x1 - x0 + 1, h=y1 - y0 + 1, area=c["area"]))
    return out


def placement(box, edges, ew, eh):
    """Where a whole exemplar would sit, given which edges cut the subject.

    The straight-edge insight: whichever axis is NOT cut is intact, so it gives
    both the scale and the alignment with no search at all. Returns
    (x, y, scale) in frame coordinates, or None when there is no free extent —
    a subject cut on both axes, or spanning the frame, is refused rather than
    guessed at.
    """
    x0, y0, x1, y1 = box
    vw, vh = x1 - x0 + 1, y1 - y0 + 1
    horiz = bool(edges & {"L", "R"})
    vert = bool(edges & {"T", "B"})
    if horiz and vert:
        return None                      # a corner: neither axis survived
    if edges >= {"L", "R"} or edges >= {"T", "B"}:
        return None                      # spans the frame: no extent at all
    if horiz:
        s = vh / eh                      # height survived the cut
        w = ew * s
        return ((x1 - w + 1) if "L" in edges else x0, y0, s)
    s = vw / ew                          # width survived the cut
    h = eh * s
    return (x0, (y1 - h + 1) if "T" in edges else y0, s)


def score(ex_mask, ex_box, part_mask, w, h):
    """Agreement between a placed exemplar and the visible part, over the part
    of the frame that actually exists — intersection over union.

    Restricted to the frame on purpose. Outside it there is nothing to agree
    with, and counting the missing region would score every exemplar by how
    much it sticks out rather than by how well it fits.
    """
    placed = Image.new("L", (w, h), 0)
    placed.paste(ex_mask, ex_box)
    inter = area_of(ImageChops.multiply(placed, part_mask))
    union = area_of(ImageChops.lighter(placed, part_mask))
    return inter / union if union else 0.0


def match(part, lib, w, h):
    """The best whole subject for this partial one, or None to refuse it."""
    pm = part["mask"]
    best = None
    for ex in lib:
        for flip in (False, True):
            place = placement(part["box"], part["edges"], ex["w"], ex["h"])
            if place is None:
                return None                       # refused on geometry alone
            x, y, s = place
            sw, sh = max(1, round(ex["w"] * s)), max(1, round(ex["h"] * s))
            m = ex["mask"].resize((sw, sh), Image.NEAREST)
            if flip:
                m = m.transpose(Image.FLIP_LEFT_RIGHT)
                # A reflected exemplar keeps its right edge against the cut, so
                # nothing moves — the box is the same, the content is mirrored.
            box = (round(x), round(y))
            v = score(m, box, pm, w, h)
            if best is None or v > best["score"]:
                best = dict(score=v, ex=ex, flip=flip, box=box, size=(sw, sh))
    return best


# -------------------------------------------------------------- the graft
def graft(canvas, cmask, part, best, margin, fw, fh):
    """Paste the missing half in, and only the missing half.

    Everything the clip filmed is kept. The exemplar contributes exactly the
    pixels that fall outside the original frame, matched in brightness first so
    the join does not step.
    """
    sw, sh = best["size"]
    rgb = best["ex"]["rgb"].resize((sw, sh), Image.LANCZOS)
    m = best["ex"]["mask"].resize((sw, sh), Image.NEAREST)
    if best["flip"]:
        rgb = rgb.transpose(Image.FLIP_LEFT_RIGHT)
        m = m.transpose(Image.FLIP_LEFT_RIGHT)

    # Brightness match over the region both of them cover. A grafted half that
    # is a shade off reads as two ducks stuck together.
    x, y = best["box"]
    overlap = Image.new("L", (fw, fh), 0)
    overlap.paste(m, (x, y))
    overlap = ImageChops.multiply(overlap, part["mask"])
    n = area_of(overlap)
    if n > 40:
        want = _mean_luma(part["rgbframe"], overlap)
        placed = Image.new("RGB", (fw, fh))
        placed.paste(rgb, (x, y))
        have = _mean_luma(placed, overlap)
        if have > 4:
            r = min(1.6, max(0.6, want / have))
            rgb = rgb.point(lambda v, r=r: min(255, round(v * r)))

    # Only outside the original frame: inside it, the clip wins. Exemplar-local
    # (u, v) is frame (x + u, y + v), so the frame rectangle lands at
    # u in [-x, fw - x), v in [-y, fh - y) — clamped to the exemplar.
    outside = Image.new("L", (sw, sh), 255)
    ix0, iy0 = max(0, -x), max(0, -y)
    ix1, iy1 = min(sw, fw - x), min(sh, fh - y)
    if ix1 > ix0 and iy1 > iy0:
        outside.paste(0, (ix0, iy0, ix1, iy1))
    m = ImageChops.multiply(m, outside)
    # Feather the join by one pixel. A hard graft against a photograph shows as
    # a seam at the panel's scale even when the brightness matches, because the
    # two halves were resampled differently on the way in.
    m = m.filter(ImageFilter.GaussianBlur(1.0))

    canvas.paste(rgb, (x + margin, y + margin), m)
    cmask.paste(m, (x + margin, y + margin), m)


def _mean_luma(img, mask):
    px, mk = img.convert("L"), mask
    return sum(a * (b >= 128) for a, b in zip(px.getdata(), mk.getdata())) \
        / max(1, area_of(mask))


# --------------------------------------------------------------- the pass
def complete_clip(frames, masks, margin, min_score=MIN_SCORE,
                  min_area=MIN_AREA, tol=1, report=None):
    """Expand every frame by `margin` and fill in the subjects its edges cut.

    `tol` is how close to the edge counts as touching it. It is not cosmetic:
    the caller blanks a few columns of mask around the frame border (a clip's
    outermost pixels flicker against the median and read as subject), and that
    blanking also stops a clipped subject from reaching the edge at all. Passed
    a tolerance of 1, this pass found *zero* clipped subjects in a clip visibly
    full of them. It has to know how much was blanked.

    Returns (frames, masks) on the expanded canvas. Subjects that cannot be
    completed confidently are left exactly as the clip had them — clipped —
    rather than being finished with a guess.
    """
    fw, fh = frames[0].size
    lib = exemplars(frames, masks, min_area, tol)
    lib.sort(key=lambda e: -e["area"])
    lib = lib[:24]                       # the biggest are the cleanest cut-outs

    out_f, out_m = [], []
    seen = done = refused = 0
    for f, m in zip(frames, masks):
        canvas = Image.new("RGB", (fw + 2 * margin, fh + 2 * margin))
        canvas.paste(f, (margin, margin))
        cmask = Image.new("L", (fw + 2 * margin, fh + 2 * margin), 0)
        cmask.paste(m, (margin, margin))

        if lib:
            for c in components(m, fw, fh, min_area):
                edges = touched(c["box"], fw, fh, tol)
                if not edges:
                    continue
                seen += 1
                part = dict(box=c["box"], edges=edges,
                            mask=as_mask(c, fw, fh), rgbframe=f)
                best = match(part, lib, fw, fh)
                if best is None or best["score"] < min_score:
                    refused += 1
                    continue
                graft(canvas, cmask, part, best, margin, fw, fh)
                done += 1

        out_f.append(canvas)
        out_m.append(cmask)

    if report:
        report(f"  completion: {done} of {seen} clipped subjects filled in "
               f"from the clip's own frames, {refused} refused "
               f"({len(lib)} exemplars)")
    return out_f, out_m
