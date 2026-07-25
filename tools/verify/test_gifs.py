#!/usr/bin/env python3
"""Every GIF in docs/media actually animates.

This exists because all sixteen of them once did not, and nobody could tell.

Pillow's `convert("P", palette=ADAPTIVE)` gives each frame its own local colour
table. That is a legal GIF, it animates correctly in a browser — which is where
it was checked — and it is rendered as a single motionless frame by a great
many other things: chat clients, file managers, image previews, anything that
draws the first frame and stops. The motion was in every file the whole time
and most people looking at the README could not see it.

Nothing caught it, and nothing would have. The frames were all present and all
different; the movies decoded correctly; the previews looked right in a
browser. The fault was one flag in the container, three layers below anything
the project tests.

So this asserts on the container itself, by parsing the GIF block structure:

  * one global colour table, and **zero** local ones — the regression guard,
    and it applies to every file without exception
  * more than one frame, and frames that differ from each other, for
    everything except the handful of screens that are static by design

    python3 tools/verify/test_gifs.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA = os.path.join(ROOT, "docs", "media")

# Screens with genuinely nothing moving in them. Each is here for a stated
# reason rather than because it failed and got silenced — a whitelist nobody
# has to justify is how a test stops meaning anything.
STATIC_BY_DESIGN = {
    "call-ended.gif":  "fixed text and a fixed duration; there is nothing to animate",
    "radio-am.gif":    "AM has no RDS, so there is no marquee and nothing else moves",
    "radio-noRds.gif": "the whole point of this one is a station sending no RDS",
}

_fails = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}   {detail}")
        _fails.append(name)


def scan(path):
    """(has_global_table, frame_count, local_table_count, delays).

    Walks the GIF block structure directly rather than through Pillow: Pillow
    normalises what it hands back, and the whole point here is to see what is
    genuinely in the file.
    """
    b = open(path, "rb").read()
    if b[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError(f"{path} is not a GIF")
    flags = b[10]
    gct = bool(flags & 0x80)
    i = 13
    if gct:
        i += 3 * (2 ** ((flags & 7) + 1))

    frames, local, delays = 0, 0, []
    pending_delay = None
    while i < len(b):
        blk = b[i]
        if blk == 0x3B:                       # trailer
            break
        if blk == 0x21:                       # extension
            label = b[i + 1]
            i += 2
            if label == 0xF9 and b[i] >= 4:   # graphic control
                pending_delay = b[i + 2] | (b[i + 3] << 8)
            while b[i]:
                i += b[i] + 1
            i += 1
        elif blk == 0x2C:                     # image descriptor
            frames += 1
            delays.append(pending_delay)
            pending_delay = None
            f = b[i + 9]
            if f & 0x80:
                local += 1
                i += 3 * (2 ** ((f & 7) + 1))
            i += 10
            i += 1                            # LZW minimum code size
            while b[i]:
                i += b[i] + 1
            i += 1
        else:
            raise ValueError(f"{path}: unexpected block 0x{blk:02x} at {i}")
    return gct, frames, local, delays


def main():
    if not os.path.isdir(MEDIA):
        sys.exit(f"no {MEDIA} — run sh tools/media/make.sh first")
    gifs = sorted(f for f in os.listdir(MEDIA) if f.endswith(".gif"))
    if not gifs:
        sys.exit("no GIFs in docs/media — run sh tools/media/make.sh first")

    print(f"\n{len(gifs)} animations in docs/media")
    for name in gifs:
        path = os.path.join(MEDIA, name)
        gct, frames, local, delays = scan(path)

        # The one that was actually wrong. A local table per frame is what made
        # every one of these look like a still.
        check(f"{name}: one shared colour table", gct and local == 0,
              f"global={gct} local tables={local} of {frames} frames")

        if name in STATIC_BY_DESIGN:
            continue

        check(f"{name}: more than one frame", frames > 1, f"{frames} frames")

        # A missing or zero delay means "as fast as possible", which browsers
        # clamp and other viewers do not. Either way it is not what was meant.
        bad = [d for d in delays if not d]
        check(f"{name}: every frame has a delay", not bad,
              f"{len(bad)} frames with no delay")

    # Frame-to-frame difference, for a sample. Decoding every frame of every
    # file is slow and the container checks above are the ones that regress;
    # this is here so "it animates" is asserted and not merely implied.
    try:
        from PIL import Image, ImageSequence
    except ImportError:
        print("\n  (skipping the pixel check — no Pillow)")
    else:
        print()
        for name in gifs:
            if name in STATIC_BY_DESIGN:
                continue
            im = Image.open(os.path.join(MEDIA, name))
            seen = {f.convert("RGB").tobytes() for f in ImageSequence.Iterator(im)}
            check(f"{name}: frames differ from each other", len(seen) > 1,
                  "every frame rendered identically")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails[:6])}"
              f"{' ...' if len(_fails) > 6 else ''}\n")
        return 1
    n_static = len(set(STATIC_BY_DESIGN) & set(gifs))
    print(f"all {len(gifs) - n_static} animations animate; "
          f"{n_static} static by design\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
