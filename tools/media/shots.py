#!/usr/bin/env python3
"""Turn raw frame dumps from build/mkshots into GIFs that look like the panel.

Same dot model as the browser preview and tools/movies/preview_gif.py: a round
bulb with a halo over an unlit grid. That matters more than it sounds. A flat
pixel grid makes a dot-matrix display look like a low-resolution monitor, and
readers judge the project on that picture — the dots, the gaps between them and
the bloom are most of why the real thing looks like a head unit.

    python3 tools/media/shots.py build/shots docs/media
"""
import os
import struct
import sys

from PIL import Image, ImageDraw

# Amber, the deck's default illumination. Level 4 is DECK_CLIP and renders red
# on colour targets, so it renders red here — a preview that quietly showed the
# clip indicator as just another bright dot would be lying about the one thing
# it exists to say.
BG = (2, 4, 3)
UNLIT = (16, 12, 8)
LEVEL = {1: (154, 85, 24), 2: (243, 165, 43), 3: (255, 217, 120), 4: (255, 73, 56)}
BLOOM = (255, 122, 22)
COLORS = 48


def read_raw(path):
    b = open(path, "rb").read()
    assert b[:4] == b"DSHT", path + " is not a shot dump"
    w, h, nf = struct.unpack_from("<HHH", b, 4)
    at = 10
    return w, h, [b[at + i * w * h: at + (i + 1) * w * h] for i in range(nf)]


def render(frames, w, h, scale):
    r = scale * 0.42
    halo = scale * 0.95
    out = []
    for f in frames:
        base = Image.new("RGB", (w * scale, h * scale), BG)
        d = ImageDraw.Draw(base)
        for y in range(h):
            for x in range(w):
                if f[y * w + x]:
                    continue
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                d.ellipse([cx - scale * 0.22, cy - scale * 0.22,
                           cx + scale * 0.22, cy + scale * 0.22], fill=UNLIT)
        glow = Image.new("RGB", base.size, (0, 0, 0))
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
        base = Image.blend(base, glow, 0.45)
        d = ImageDraw.Draw(base)
        for y in range(h):
            for x in range(w):
                v = f[y * w + x]
                if not v:
                    continue
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LEVEL[v])
        out.append(base.convert("P", palette=Image.ADAPTIVE, colors=COLORS))
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "build/shots"
    dst = sys.argv[2] if len(sys.argv) > 2 else "docs/media"
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    os.makedirs(dst, exist_ok=True)

    total = 0
    for name in sorted(os.listdir(src)):
        if not name.endswith(".raw"):
            continue
        w, h, frames = read_raw(os.path.join(src, name))
        imgs = render(frames, w, h, scale)
        out = os.path.join(dst, name[:-4] + ".gif")
        imgs[0].save(out, save_all=True, append_images=imgs[1:],
                     duration=int(1000 / fps), loop=0, optimize=True)
        size = os.path.getsize(out)
        total += size
        print(f"  {out:32s} {len(frames):3d} frames  {size / 1024:6.0f} KB")
    print(f"  {'total':32s} {total / 1024:20.0f} KB")


if __name__ == "__main__":
    main()
