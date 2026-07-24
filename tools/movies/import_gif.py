#!/usr/bin/env python3
"""Turn an animated GIF into a deck movie.

The quickest way to get an animation onto the deck: point this at any GIF and
it comes out as a .dmv the firmware, the preview and the legacy faceplate all
play.

    python3 tools/movies/import_gif.py cat.gif                  # 256x64
    python3 tools/movies/import_gif.py cat.gif --legacy         # 192x48 + install
    python3 tools/movies/import_gif.py cat.gif 256 64 --cover   # crop, don't letterbox
    python3 tools/movies/import_gif.py reef.gif --keep=20       # subject only, bg to black

The interesting work is not the decoding — it is that a GIF assumes things this
display does not have:

  * **Colour.** Folded to luminance, then dithered to four levels. A GIF that
    reads by hue alone (red shape on green) becomes one flat blob. Check the
    ASCII dump before assuming it worked.
  * **A whole tonal range.** Photographic footage uses all of it, and with four
    levels a mid-grey background does not read as background — it becomes a 50%
    dither pattern louder than the subject. `--keep=P` lights only the brightest
    P% of the picture and crushes the rest to off, which is what turns busy
    footage into something a head unit can actually show. See `pick_levels`.
  * **Its own frame timing.** GIFs carry a per-frame delay; a .dmv has one
    rate. Frames are resampled onto a fixed fps by sampling the GIF's timeline,
    so a 30 ms frame does not become a 100 ms one.
  * **A different shape.** Most GIFs are square-ish; the deck is 4:1 or wider.
    Letterboxing (default) keeps the whole frame and wastes the sides; --cover
    fills the panel and crops. Neither is right for every GIF.
  * **Transparency.** Composited onto black, since the deck has no alpha —
    "transparent" and "off" are the same dot.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmv as M

try:
    from PIL import Image, ImageSequence
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow")


def gif_timeline(im):
    """(frame index, cumulative ms) for each GIF frame, with its own delays."""
    out, t = [], 0
    for i, frame in enumerate(ImageSequence.Iterator(im)):
        out.append((i, t))
        # GIF delays are in centiseconds; 0 means "as fast as possible", which
        # browsers historically clamp to 100 ms. Do the same rather than
        # producing a movie that plays at whatever the panel's refresh is.
        d = frame.info.get("duration", 100) or 100
        t += max(20, d)
    return out, t


def fit(frame, w, h, cover):
    """RGB image scaled into the panel, letterboxed or cropped."""
    src = frame.convert("RGBA")
    bg = Image.new("RGBA", src.size, (0, 0, 0, 255))     # no alpha on the deck
    src = Image.alpha_composite(bg, src).convert("RGB")

    sw, sh = src.size
    scale = max(w / sw, h / sh) if cover else min(w / sw, h / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    src = src.resize((nw, nh), Image.LANCZOS)

    out = Image.new("RGB", (w, h), (0, 0, 0))
    out.paste(src, ((w - nw) // 2, (h - nh) // 2))
    return out


def saturation(img):
    """Mean chroma of the LIT pixels, 0..255.

    Deliberately not a detector for "two hues that collide in luminance" — that
    is what actually ruins an import, but establishing it needs to know which
    regions are meant to be distinct, which the file does not say. So this
    measures the thing that is measurable, a strongly coloured source, and the
    caller turns it into advice rather than a verdict.

    Averaging over the whole frame is useless here: most animations are mostly
    background, which drags any average to nothing. Only lit pixels count.
    """
    px = img.tobytes()
    n = len(px) // 3
    tot, lit = 0.0, 0
    for i in range(0, n, 3):                       # sampled; this is only advice
        r, g, b = px[i * 3], px[i * 3 + 1], px[i * 3 + 2]
        if 0.299 * r + 0.587 * g + 0.114 * b <= 20:
            continue
        tot += max(r, g, b) - min(r, g, b)
        lit += 1
    return tot / lit if lit else 0.0


def pick_levels(imgs, keep):
    """Black and white points that light the brightest `keep` percent, fixed
    for the whole movie.

    Two decisions worth spelling out.

    *Percentile, not a fixed threshold*, because the caller knows how much of
    the picture is subject ("the fish, not the water") and does not know what
    luminance the water happens to be.

    *One value for every frame, not per-frame.* The default auto-stretch is
    per-frame, which is fine for a rendered scene that always contains its own
    black and white. On footage it pumps: a frame where the subject leaves
    re-normalises the background up to full brightness and the panel flashes.
    Sampling across the movie and freezing the result is what stops that.
    """
    lum = []
    for img in imgs:
        px = img.tobytes()
        n = len(px) // 3
        lum.extend(M.luma(px[i * 3], px[i * 3 + 1], px[i * 3 + 2])
                   for i in range(0, n, 7))          # sampled; this is a histogram
    lum.sort()
    lo = lum[min(len(lum) - 1, int(len(lum) * (1.0 - keep / 100.0)))]
    hi = lum[min(len(lum) - 1, int(len(lum) * 0.998))]   # ignore specular outliers
    return lo, max(lo + 30.0, hi)


def convert(path, w, h, fps, cover=False, black=20, stretch=True,
            keep=None, gamma=1.0):
    im = Image.open(path)
    timeline, total_ms = gif_timeline(im)
    if not timeline:
        raise SystemExit("no frames in " + path)

    step = 1000.0 / fps
    n_out = max(1, int(round(total_ms / step)))
    seq = list(ImageSequence.Iterator(Image.open(path)))

    fitted = []
    for k in range(n_out):
        want = k * step
        # last GIF frame whose start time has passed
        idx = 0
        for (i, t) in timeline:
            if t <= want:
                idx = i
            else:
                break
        fitted.append(fit(seq[idx], w, h, cover))

    sat = saturation(fitted[n_out // 2])
    if sat > 60:
        print(f"  ! strongly coloured source (mean chroma {sat:.0f}/255).\n"
              "    The deck has no hue — anything that reads by colour\n"
              "    alone will merge into one shape. Check the dump below;\n"
              "    if it looks flat, try --keep= to drop the background out.")

    lo = hi = None
    if keep is not None:
        # every 4th frame is plenty for a histogram and keeps this quick
        lo, hi = pick_levels(fitted[::4] or fitted, keep)
        print(f"  levels: keeping the brightest {keep:g}% — "
              f"black at {lo:.0f}/255, white at {hi:.0f}/255")

    frames = []
    for k, img in enumerate(fitted):
        frames.append(M.quantise(bytearray(img.tobytes()), w, h, black=black,
                                 stretch=stretch, lo=lo, hi=hi, gamma=gamma))
        print(f"  {k + 1}/{n_out}", end="\r", flush=True)
    print()
    return frames, n_out, total_ms


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
    fps, keep, gamma, name = 10, None, 1.0, None
    for f in flags:
        if f.startswith("--fps="):
            fps = int(f.split("=")[1])
        elif f.startswith("--keep="):
            keep = float(f.split("=")[1])
        elif f.startswith("--gamma="):
            gamma = float(f.split("=")[1])
        elif f.startswith("--name="):
            name = f.split("=", 1)[1]

    name = (name or os.path.splitext(os.path.basename(src))[0]).upper()[:24]
    frames, n, total = convert(src, w, h, fps, cover="--cover" in flags,
                               stretch="--no-stretch" not in flags,
                               keep=keep, gamma=gamma)

    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "..", "movies",
                       f"{name.lower().replace(' ', '_')}_{w}x{h}.dmv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    blob = M.write_dmv(out, frames, w, h, fps, name, loop=True)
    print(f"wrote {os.path.relpath(out)}  {len(blob)} bytes  "
          f"{n} frames @ {fps}fps ({total / 1000:.1f}s of source)")
    if legacy:
        M.install_legacy(out, name)
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(frames[len(frames) // 3], w, h))


if __name__ == "__main__":
    main()
