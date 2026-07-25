#!/usr/bin/env python3
"""The GIF importer produces a movie that moves.

This exists because it once did not, silently. `ImageSequence.Iterator` yields
the same `Image` object seeked to each position rather than independent frames,
so materialising it into a list gave N references to one object — and the
import emitted a perfectly valid .dmv of N identical stills.

Nothing caught it. The container round-trips, the decoders agree, the ASCII
dump looks like the picture, the preview GIF looks like the picture. Every
check in this project passed on a movie that had lost its animation, because
they all check *fidelity* and none of them checked that anything changed.

So this one asserts on movement, which is a different question:

  * a GIF whose frames differ produces a .dmv whose frames differ
  * the subject ends up where the source put it, not somewhere else
  * a genuinely still GIF still imports, without special-casing

    python3 tools/verify/test_import.py
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "movies"))

try:
    from PIL import Image
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow")

import import_gif  # noqa: E402

_fails = []


def check(name, cond, detail=""):
    print(f"  {'ok   ' if cond else 'FAIL '} {name}   {'' if cond else detail}")
    if not cond:
        _fails.append(name)


def make_gif(path, frames, size=(120, 60), duration=100):
    """`frames` is a list of (x, y) for a white 20x20 block on black."""
    imgs = []
    for (x, y) in frames:
        im = Image.new("RGB", size, (0, 0, 0))
        for yy in range(y, min(size[1], y + 20)):
            for xx in range(x, min(size[0], x + 20)):
                im.putpixel((xx, yy), (255, 255, 255))
        imgs.append(im)
    imgs[0].save(path, save_all=True, append_images=imgs[1:],
                 duration=duration, loop=0)


def centroid(frame, w, h):
    """Mean x of the lit dots, or None. Coarse on purpose — this is asking
    'did the block move right', not measuring anything."""
    tot, n = 0, 0
    for y in range(h):
        for x in range(w):
            if frame[y * w + x]:
                tot += x
                n += 1
    return tot / n if n else None


def main():
    tmp = tempfile.mkdtemp(prefix="deck-import-")
    W, H = 96, 24

    print("\na GIF that moves")
    src = os.path.join(tmp, "moving.gif")
    make_gif(src, [(0, 20), (40, 20), (90, 20), (40, 20)])
    frames, n, _ = import_gif.convert(src, W, H, 10)

    check("every source frame reached the movie", n >= 4, f"got {n}")
    check("the frames are not all identical",
          len({bytes(f) for f in frames}) > 1,
          "all frames were byte-identical — the importer lost the animation")

    xs = [centroid(f, W, H) for f in frames]
    xs = [x for x in xs if x is not None]
    check("something is lit in every frame", len(xs) == len(frames),
          f"{len(frames) - len(xs)} frames were blank")
    if xs:
        # The block starts left, ends right of centre, comes back. Testing the
        # span rather than per-frame positions: the timeline is resampled onto
        # a fixed fps, so which output frame holds which source frame is an
        # implementation detail, but the travel is not.
        check("the subject actually travels across the panel",
              max(xs) - min(xs) > W * 0.25,
              f"centroid moved {max(xs) - min(xs):.1f} dots of {W}")
        check("it starts on the left half", xs[0] < W / 2, f"x0={xs[0]:.1f}")

    print("\na GIF that does not move")
    src2 = os.path.join(tmp, "still.gif")
    make_gif(src2, [(30, 20), (30, 20), (30, 20)])
    frames2, n2, _ = import_gif.convert(src2, W, H, 10)
    check("a still GIF still imports", n2 >= 3 and len(frames2) == n2,
          f"n={n2} frames={len(frames2)}")
    check("and its frames are identical, as they should be",
          len({bytes(f) for f in frames2}) == 1)

    print("\n--trim keeps the frames it says it keeps")
    # Six source frames at 100 ms: the block creeps along the left for three,
    # then jumps to the right for three. Trimming to the first three must give
    # a movie that stays on the left — a stronger assertion than a frame count,
    # because an off-by-one in the timeline re-basing would still produce the
    # right *number* of frames while playing the wrong ones.
    #
    # Each frame differs slightly on purpose: PIL collapses a run of identical
    # frames into one with a longer delay, so `[(0,2)] * 3` is not three source
    # frames and a test written that way silently tests nothing.
    src3 = os.path.join(tmp, "halves.gif")
    make_gif(src3, [(0, 2), (2, 2), (4, 2), (70, 2), (72, 2), (74, 2)])
    left, n3, ms3 = import_gif.convert(src3, W, H, 10, trim=(0, 3))
    check("trimming to the first half keeps half the frames",
          n3 == 3, f"got {n3}")
    check("and 300 ms of source", abs(ms3 - 300) < 1, f"got {ms3}")
    lxs = [x for x in (centroid(f, W, H) for f in left) if x is not None]
    check("the trimmed half is the LEFT half",
          lxs and max(lxs) < W / 2, f"centroids {lxs}")

    right, n4, _ = import_gif.convert(src3, W, H, 10, trim=(3, 6))
    rxs = [x for x in (centroid(f, W, H) for f in right) if x is not None]
    check("trimming to the second half gets the other one",
          n4 == 3 and rxs and min(rxs) > W / 2, f"n={n4} centroids {rxs}")

    # An open end means "to the end", and an empty range is an error rather
    # than a zero-frame .dmv that fails somewhere further downstream.
    _, n5, _ = import_gif.convert(src3, W, H, 10, trim=(3, 1 << 30))
    check("an open end runs to the end of the source", n5 == 3, f"got {n5}")
    try:
        import_gif.convert(src3, W, H, 10, trim=(4, 2))
        check("an empty trim is refused", False, "it was accepted")
    except SystemExit:
        check("an empty trim is refused", True)

    print("\nthe whole tool, end to end")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "movies", "import_gif.py"),
                        src, "96", "24", "--name=IMPORTTEST"],
                       capture_output=True, text=True)
    out = os.path.join(ROOT, "movies", "importtest_96x24.dmv")
    check("import_gif.py runs and writes a .dmv",
          r.returncode == 0 and os.path.exists(out),
          (r.stderr or r.stdout)[-300:])
    if os.path.exists(out):
        sys.path.insert(0, os.path.join(ROOT, "tools", "movies"))
        from preview_gif import decode
        _, w, h, _, fr = decode(out)
        check("the written .dmv decodes to moving frames",
              len(set(fr)) > 1, f"{len(fr)} frames, {len(set(fr))} distinct")
        os.remove(out)

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails)}\n")
        return 1
    print("importer checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
