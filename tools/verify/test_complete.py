#!/usr/bin/env python3
"""The completion pass fills in what the clip cut, and nothing else.

    python3 tools/verify/test_complete.py

`tools/movies/complete.py` finishes subjects that a clip's own frame edge cut in
half, using the same subjects from frames where they were whole. Two things
about that need proving rather than asserting in a comment, because both fail
silently and both fail as *plausible pictures*:

**It must not invent.** A completion pass that hallucinates is worse than no
pass at all: a clipped duck looks cut, which a viewer forgives, and an invented
one looks broken, which they do not. So the tests here are mostly about refusal
— on an empty clip, on a clip whose subjects are never whole, and on subjects
cut on both axes at once, the right answer is to change nothing.

**It must be deterministic.** Every generated file in this repository is
byte-compared against its generator. A pass that returned something slightly
different each run would quietly break that rule for every movie downstream of
it, and the failure would show up as an unrelated staleness error weeks later.
This is also the concrete reason the fill is exemplar matching and not a
generative model — see the module docstring.

The fixture is synthetic on purpose. A disc is the one subject whose completed
area is known in closed form, so "did it finish the shape" is a number here
rather than an opinion.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "movies"))

from PIL import Image, ImageDraw

import complete as C

W = H = 120
R = 18                                   # disc radius
_fails = []


def check(name, cond, detail=""):
    print(f"  {'ok   ' if cond else 'FAIL '} {name}   {'' if cond else detail}")
    if not cond:
        _fails.append(name)


def clip(centres, r=R):
    """A clip of one bright disc at the given centres, on a dark field, with
    the matching subject masks. One frame per centre."""
    frames, masks = [], []
    for cx, cy in centres:
        f = Image.new("RGB", (W, H), (20, 20, 24))
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(f).ellipse((cx - r, cy - r, cx + r, cy + r),
                                  fill=(230, 200, 90))
        ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        frames.append(f)
        masks.append(m)
    return frames, masks


def lit(mask):
    return sum(mask.histogram()[128:])


def main():
    margin = 30
    full = 3.14159 * R * R

    print("\na subject the frame cut in half is finished from another frame")
    # Three frames where the disc is whole — those are the exemplars — and one
    # where it has drifted half out of the left edge, which is the case.
    frames, masks = clip([(60, 60), (45, 55), (75, 62), (2, 60)])
    out_f, out_m = C.complete_clip(frames, masks, margin)

    before = lit(masks[-1])
    after = lit(out_m[-1])
    check("the clipped frame gained pixels", after > before * 1.4,
          f"{before} -> {after} lit pixels, expected roughly {full:.0f}")
    check("it gained about the missing half, not more",
          0.8 * full <= after <= 1.35 * full,
          f"{after} lit, a whole disc is {full:.0f}")
    check("the frames it did not cut are untouched",
          all(lit(out_m[i]) == lit(masks[i]) for i in range(3)),
          "a whole subject was modified — the pass should ignore it")
    check("the canvas grew by the margin on every side",
          out_f[0].size == (W + 2 * margin, H + 2 * margin),
          f"{out_f[0].size}")

    print("\nthe filled pixels come from the clip, not from nowhere")
    # The disc is one flat colour, so any grafted pixel must be that colour. A
    # generative fill would be free to put anything here; a matched one cannot.
    px = out_f[-1].convert("RGB").load()
    mk = out_m[-1].load()
    off = []
    for y in range(0, H + 2 * margin, 2):
        for x in range(0, W + 2 * margin, 2):
            if mk[x, y] >= 200:
                r, g, b = px[x, y]
                if not (150 < r < 255 and 120 < g < 240 and b < 190):
                    off.append((x, y, r, g, b))
    check("every filled pixel is the subject's own colour", len(off) < 8,
          f"{len(off)} sampled pixels are not, e.g. {off[:3]}")

    print("\nit refuses rather than guesses")
    # No exemplar anywhere: the disc is against the edge in every frame, so
    # there is nothing whole to match against.
    frames, masks = clip([(2, 60), (3, 62), (2, 58)])
    _, out_m = C.complete_clip(frames, masks, margin)
    check("a clip with no whole subject is left alone",
          all(lit(a) == lit(b) for a, b in zip(out_m, masks)),
          "something was completed with no exemplar to complete it from")

    # Cut on both axes at once. There is no free extent to take a scale or an
    # alignment from, so geometry alone refuses this before any matching.
    frames, masks = clip([(60, 60), (50, 65), (2, 2)])
    _, out_m = C.complete_clip(frames, masks, margin)
    check("a subject cut at a corner is refused",
          lit(out_m[-1]) == lit(masks[-1]),
          f"{lit(masks[-1])} -> {lit(out_m[-1])}: a corner case was guessed at")

    # Nothing moving at all.
    blank = [Image.new("RGB", (W, H), (20, 20, 24)) for _ in range(3)]
    empty = [Image.new("L", (W, H), 0) for _ in range(3)]
    _, out_m = C.complete_clip(blank, empty, margin)
    check("an empty clip stays empty", all(lit(m) == 0 for m in out_m),
          "a subject was invented where the clip had none")

    print("\nit is deterministic, which is what lets the movies be "
          "byte-compared")
    frames, masks = clip([(60, 60), (45, 55), (75, 62), (2, 60)])
    a_f, a_m = C.complete_clip(frames, masks, margin)
    b_f, b_m = C.complete_clip(frames, masks, margin)
    check("two runs agree to the byte",
          all(x.tobytes() == y.tobytes() for x, y in zip(a_f, b_f))
          and all(x.tobytes() == y.tobytes() for x, y in zip(a_m, b_m)),
          "the same input produced different output")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails)}\n")
        return 1
    print("completion checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
