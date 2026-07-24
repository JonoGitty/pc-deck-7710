#!/usr/bin/env python3
"""Turn an animated GIF into a deck movie.

The quickest way to get an animation onto the deck: point this at any GIF and
it comes out as a .dmv the firmware, the preview and the legacy faceplate all
play.

    python3 tools/movies/import_gif.py cat.gif                  # 256x64
    python3 tools/movies/import_gif.py cat.gif --legacy         # 192x48 + install
    python3 tools/movies/import_gif.py cat.gif 256 64 --cover   # crop, don't letterbox

The interesting work is not the decoding — it is that a GIF assumes things this
display does not have:

  * **Colour.** Folded to luminance, then dithered to four levels. A GIF that
    reads by hue alone (red shape on green) becomes one flat blob. Check the
    ASCII dump before assuming it worked.
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


def convert(path, w, h, fps, cover=False, black=20, stretch=True):
    im = Image.open(path)
    timeline, total_ms = gif_timeline(im)
    if not timeline:
        raise SystemExit("no frames in " + path)

    step = 1000.0 / fps
    n_out = max(1, int(round(total_ms / step)))
    frames = []
    seq = list(ImageSequence.Iterator(Image.open(path)))

    for k in range(n_out):
        want = k * step
        # last GIF frame whose start time has passed
        idx = 0
        for (i, t) in timeline:
            if t <= want:
                idx = i
            else:
                break
        img = fit(seq[idx], w, h, cover)
        if k == n_out // 2:
            sat = saturation(img)
            if sat > 60:
                print(f"\n  ! strongly coloured source (mean chroma {sat:.0f}/255).\n"
                      "    The deck has no hue — anything that reads by colour\n"
                      "    alone will merge into one shape. Check the dump below;\n"
                      "    if it looks flat, raise the contrast in the source.")
        frames.append(M.quantise(bytearray(img.tobytes()), w, h,
                                 black=black, stretch=stretch))
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
    fps = 10
    for f in flags:
        if f.startswith("--fps="):
            fps = int(f.split("=")[1])

    name = os.path.splitext(os.path.basename(src))[0].upper()[:24]
    frames, n, total = convert(src, w, h, fps, cover="--cover" in flags,
                               stretch="--no-stretch" not in flags)

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
