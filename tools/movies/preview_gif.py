#!/usr/bin/env python3
"""Turn a .dmv into an animated GIF that looks like the panel.

For sharing an animation, and for checking one without a deck. Each dot is
drawn as a round bulb with a halo over an unlit dot grid, which is the same
model the browser preview uses — a flat pixel grid badly misrepresents how a
dot-matrix display actually reads.

    python3 tools/movies/preview_gif.py movies/solar_256x64.dmv out.gif [scale]
    python3 tools/movies/preview_gif.py in.dmv out.gif 3 --from=40 --max=200

`--from` / `--max` cut an excerpt. A GIF is roughly 3 KB a frame, so the full
56-second SOLAR is a megabyte and a half — fine to play on a deck, not fine to
put at the top of a README that someone opens on a phone.
"""
import os
import struct
import sys

from PIL import Image, ImageDraw

# Amber, matching the deck's default illumination.
BG = (2, 4, 3)
UNLIT = (16, 12, 8)
LEVEL = {1: (154, 85, 24), 2: (243, 165, 43), 3: (255, 217, 120), 4: (255, 73, 56)}
BLOOM = (255, 122, 22)


def decode(path):
    b = open(path, "rb").read()
    assert b[:4] == b"DMV1", "not a .dmv"
    w, h, fps, flags, nf, nl = struct.unpack_from("<HHBBHH", b, 4)
    name = b[14:14 + nl].decode("ascii", "replace")
    at = 14 + nl
    grid = bytearray(w * h)
    frames = []
    for _ in range(nf):
        runs, = struct.unpack_from("<H", b, at); at += 2
        for _ in range(runs):
            start, length, level = struct.unpack_from("<HHB", b, at); at += 5
            for k in range(length):
                grid[start + k] = level
        frames.append(bytes(grid))
    return name, w, h, fps, frames


COLORS = 32          # the panel is one hue; more just costs bytes


def render(frames, w, h, scale):
    imgs = []
    r = scale * 0.42
    halo = scale * 0.95
    for f in frames:
        im = Image.new("RGB", (w * scale, h * scale), BG)
        d = ImageDraw.Draw(im)
        for y in range(h):
            for x in range(w):
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                v = f[y * w + x]
                if not v:
                    d.ellipse([cx - scale * 0.22, cy - scale * 0.22,
                               cx + scale * 0.22, cy + scale * 0.22], fill=UNLIT)
        # bloom pass, then cores, so neighbouring dots glow into each other
        glow = Image.new("RGB", im.size, (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for y in range(h):
            for x in range(w):
                v = f[y * w + x]
                if not v:
                    continue
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                a = 0.10 + 0.06 * v
                gd.ellipse([cx - halo, cy - halo, cx + halo, cy + halo],
                           fill=tuple(int(c * a) for c in BLOOM))
        im = Image.blend(im, Image.blend(im, glow, 0.0), 0.0)
        base = Image.new("RGB", im.size)
        base.paste(im)
        base = Image.blend(base, glow, 0.45)
        d = ImageDraw.Draw(base)
        for y in range(h):
            for x in range(w):
                v = f[y * w + x]
                if not v:
                    continue
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LEVEL.get(v, LEVEL[3]))
        imgs.append(base)
    return imgs


def to_palette(imgs):
    """One palette for the whole animation, not one per frame.

    `convert("P", palette=ADAPTIVE)` per frame gives every frame its own local
    colour table. That is a legal GIF and it plays correctly in a browser — and
    it is shown as a single still by a great many other things: chat clients,
    file managers, image previews, anything that renders the first frame and
    stops. The animation was there the whole time and nobody could see it.

    So the palette is computed once, from a frame sampled out of the middle
    where the picture is busiest, and every frame is mapped onto it. The panel
    is one hue over a black field, so a shared palette costs nothing visually
    and makes the file smaller as well.
    """
    base = imgs[len(imgs) // 2].convert("P", palette=Image.ADAPTIVE,
                                        colors=COLORS)
    return [im.quantize(palette=base, dither=Image.NONE) for im in imgs]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    src = args[0]
    dst = args[1] if len(args) > 1 else src.rsplit(".", 1)[0] + ".gif"
    scale = int(args[2]) if len(args) > 2 else 4
    start, limit = 0, None
    for f in flags:
        if f.startswith("--from="):
            start = int(f.split("=")[1])
        elif f.startswith("--max="):
            limit = int(f.split("=")[1])

    name, w, h, fps, frames = decode(src)
    total = len(frames)
    frames = frames[start: None if limit is None else start + limit]
    cut = "" if len(frames) == total else f"  (excerpt of {total})"
    print(f"{name}  {w}x{h}  {len(frames)} frames @ {fps}fps{cut} -> {dst}")
    imgs = to_palette(render(frames, w, h, scale))
    # `palette=` is what actually forces one global colour table. Mapping every
    # frame onto the same palette is not enough on its own — Pillow still emits
    # a local table per frame, and it is that per-frame table which some
    # viewers take as licence to render the first frame and stop.
    imgs[0].save(dst, save_all=True, append_images=imgs[1:],
                 duration=int(1000 / fps), loop=0, optimize=False,
                 disposal=1, palette=imgs[0].getpalette())
    print(f"wrote {dst}  {len(imgs)} frames, "
          f"{os.path.getsize(dst) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
