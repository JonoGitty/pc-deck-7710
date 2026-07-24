#!/usr/bin/env python3
"""Turn a .dmv into an animated GIF that looks like the panel.

For sharing an animation, and for checking one without a deck. Each dot is
drawn as a round bulb with a halo over an unlit dot grid, which is the same
model the browser preview uses — a flat pixel grid badly misrepresents how a
dot-matrix display actually reads.

    python3 tools/movies/preview_gif.py movies/solar_256x64.dmv out.gif [scale]
"""
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
        imgs.append(base.convert("P", palette=Image.ADAPTIVE, colors=64))
    return imgs


def main():
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.rsplit(".", 1)[0] + ".gif"
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    name, w, h, fps, frames = decode(src)
    print(f"{name}  {w}x{h}  {len(frames)} frames @ {fps}fps -> {dst}")
    imgs = render(frames, w, h, scale)
    imgs[0].save(dst, save_all=True, append_images=imgs[1:],
                 duration=int(1000 / fps), loop=0, optimize=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()
