#!/usr/bin/env python3
"""Put your own pictures on the deck.

    python3 tools/movies/import_image.py photo.jpg 256 64
    python3 tools/movies/import_image.py *.jpg --legacy --hold=4
    python3 tools/movies/import_image.py logo.png 256 64 --name=BOOT --keep=30

A still is a movie with one frame, and a set of stills is a slideshow. Saying
it that way is the whole design: pictures come out as a `.dmv`, so they use the
decoder that already exists, the flash partition that already exists and the
MOVIE screen that already exists. A separate image format would have needed a
new container, a new firmware path and a new failure mode, to display fewer
things.

WHAT A PHOTOGRAPH LOSES HERE, AND WHY

The panel has four brightness levels and no colour. A photograph has millions
of both, and the naive conversion — luminance, then dither — reliably produces
grey noise. Three things save it, and all three are on by default:

  * **Levels.** `--keep` lights only the brightest N percent and crushes the
    rest to black, because a mid-grey background does not become "background"
    on four levels, it becomes a checkerboard louder than the subject. This is
    the same control the GIF importer needs and for the same reason.

  * **Local contrast.** A face against a window is two flat regions after
    quantisation. Subtracting a blurred copy of the image restores the edges
    that carry the shape, at the cost of the overall tonal balance — which was
    never survivable anyway.

  * **Fitting.** The deck is 4:1. A portrait letterboxed into it is a stripe of
    picture between two thirds of nothing, so `--cover` crops to fill by
    default and `--fit` letterboxes if you would rather keep the whole frame.

Faces, incidentally, mostly do not work. Text, logos, silhouettes, skylines and
anything with a hard edge do. That is not a limitation of this script.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmv as M

try:
    from PIL import Image, ImageFilter
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow")


def fit(img, w, h, cover=True):
    src = img.convert("RGBA")
    bg = Image.new("RGBA", src.size, (0, 0, 0, 255))
    src = Image.alpha_composite(bg, src).convert("RGB")
    sw, sh = src.size
    scale = max(w / sw, h / sh) if cover else min(w / sw, h / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    src = src.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGB", (w, h), (0, 0, 0))
    out.paste(src, ((w - nw) // 2, (h - nh) // 2))
    return out


def local_contrast(img, amount):
    """Unsharp against a wide blur.

    Not sharpening — the radius is deliberately large. The aim is to remove the
    slow brightness gradient across the picture, which quantisation cannot
    represent anyway, and keep the fast changes, which are the shapes. A small
    radius would sharpen edges and leave the gradient exactly where it was.
    """
    if amount <= 0:
        return img
    blur = img.filter(ImageFilter.GaussianBlur(radius=max(2, img.width // 12)))
    return Image.blend(img, Image.eval(blur, lambda v: 255 - v), amount * 0.5)


def levels_from_keep(img, keep):
    """Black and white points that light the brightest `keep` percent."""
    px = img.convert("L").tobytes()
    lum = sorted(px)
    lo = lum[min(len(lum) - 1, int(len(lum) * (1.0 - keep / 100.0)))]
    hi = lum[min(len(lum) - 1, int(len(lum) * 0.995))]
    return float(lo), float(max(lo + 30, hi))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if not args:
        sys.exit(__doc__)

    legacy = "--legacy" in flags
    cover = "--fit" not in flags
    keep, hold, contrast, name = 35.0, 3.0, 0.35, None
    for f in flags:
        if f.startswith("--keep="):     keep = float(f.split("=")[1])
        elif f.startswith("--hold="):   hold = float(f.split("=")[1])
        elif f.startswith("--contrast="): contrast = float(f.split("=")[1])
        elif f.startswith("--name="):   name = f.split("=", 1)[1]

    srcs = [a for a in args if os.path.exists(a)]
    dims = [a for a in args if a.isdigit()]
    w = int(dims[0]) if len(dims) > 0 else 256
    h = int(dims[1]) if len(dims) > 1 else 64
    if legacy:
        w, h = 192, 48
    if not srcs:
        sys.exit("no readable image files given")

    fps = 10
    frames = []
    for path in srcs:
        img = fit(Image.open(path), w, h, cover)
        img = local_contrast(img, contrast)
        lo, hi = levels_from_keep(img, keep)
        lv = M.quantise(bytearray(img.tobytes()), w, h, black=int(lo), lo=lo, hi=hi)
        # Every picture is held for `hold` seconds by repeating it. The .dmv is
        # delta-coded, so a repeated frame costs two bytes — a five-second
        # still is fifty frames and about a hundred bytes.
        frames += [lv] * max(1, int(hold * fps))
        print(f"  {os.path.basename(path):<28} black {lo:3.0f}  white {hi:3.0f}")

    label = (name or (os.path.splitext(os.path.basename(srcs[0]))[0]
                      if len(srcs) == 1 else "PICTURES")).upper()[:24]
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "..", "movies",
                       f"{label.lower().replace(' ', '_')}_{w}x{h}.dmv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    blob = M.write_dmv(out, frames, w, h, fps, label, loop=True)
    print(f"\nwrote {os.path.relpath(out)}  {len(blob)} bytes  "
          f"{len(srcs)} picture(s), {len(frames) / fps:.0f}s")
    if legacy:
        M.install_legacy(out, label)
        print("installed into the PC deck — press V on the faceplate")
    print("\n" + M.to_ascii(frames[0], w, h))
    print("\nIf that dump is not recognisable, the picture will not be either.\n"
          "Try --keep=25 for a brighter subject, --contrast=0.6 for more edge,\n"
          "or --fit to stop cropping.")


if __name__ == "__main__":
    main()
