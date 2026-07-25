#!/usr/bin/env python3
"""Turn the simulator's raw frame dump into a GIF that looks like the panel.

Same dot model as the browser preview and every other preview in this repo —
a round bulb with a halo over an unlit grid. Uniform on purpose: if the
simulator drew its frames differently from the README, a difference between
them would be impossible to attribute.
"""
import struct
import sys

from PIL import Image, ImageDraw

BG = (2, 4, 3)
UNLIT = (16, 12, 8)
LEVEL = {1: (154, 85, 24), 2: (243, 165, 43), 3: (255, 217, 120), 4: (255, 73, 56)}
BLOOM = (255, 122, 22)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    with open(src, "rb") as fh:
        hdr = fh.readline().decode().split()
        w, h, fps = int(hdr[1]), int(hdr[2]), int(hdr[3])
        data = fh.read()
    n = len(data) // (w * h)
    print(f"{n} frames  {w}x{h} @ {fps}fps -> {dst}")

    imgs = []
    r, halo = scale * 0.42, scale * 0.95
    for i in range(n):
        f = data[i * w * h:(i + 1) * w * h]
        base = Image.new("RGB", (w * scale, h * scale), BG)
        d = ImageDraw.Draw(base)
        for y in range(h):
            for x in range(w):
                if f[y * w + x]:
                    continue
                cx, cy = x * scale + scale / 2, y * scale + scale / 2
                d.ellipse([cx - scale * .22, cy - scale * .22,
                           cx + scale * .22, cy + scale * .22], fill=UNLIT)
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
                d.ellipse([cx - r, cy - r, cx + r, cy + r],
                          fill=LEVEL.get(v, LEVEL[3]))
        imgs.append(base.convert("P", palette=Image.ADAPTIVE, colors=48))
    imgs[0].save(dst, save_all=True, append_images=imgs[1:],
                 duration=int(1000 / fps), loop=0, optimize=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()
