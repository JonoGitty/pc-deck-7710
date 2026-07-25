#!/usr/bin/env python3
"""Demo movie: a rotating wireframe-ish globe over a horizon.

Deliberately simple — it exists to prove the pipeline end to end (3D render ->
luminance -> dither to five levels -> delta-compressed .dmv -> the C decoder)
and to be the thing someone copies when writing their own.

    python3 tools/movies/scene_spin.py             # 192x48, the legacy grid
    python3 tools/movies/scene_spin.py 256 64      # an SSD1322 panel
    python3 tools/movies/scene_spin.py --legacy    # ...and install it into the
                                                   #    PC deck so you can watch
                                                   #    it without hardware
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render3d as D
import dmv as M

LEGACY = "--legacy" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
W = int(ARGS[0]) if len(ARGS) > 0 else 192
H = int(ARGS[1]) if len(ARGS) > 1 else 48
if LEGACY:
    W, H = 192, 48                     # the legacy faceplate's grid, fixed
FPS, FRAMES = 10, 24
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                   "movies", f"spin_{W}x{H}.dmv")

verts, tris = D.icosphere(1)
ground, gtris = D.box(80, 0.5, 80)

# A 4:1 strip is nearly all width, so fill it: three globes across, the outer
# two further away. Composition for this panel is a frieze, not a portrait.
POSTS = ((-5.2, 2.2, 0.62), (0.0, 0.0, 1.0), (5.2, 2.2, 0.62))


def scene(fi):
    ang = 2 * math.pi * fi / FRAMES

    def draw(fb, cw, ch):
        cam = D.Cam((0, 1.15, -10.5), (0, 0.55, 0), cw, ch, f=cw * 0.42)
        # horizon slab, dim so the globes stay the subject
        D.draw_mesh(fb, cam, ground, gtris, D.IDENT, (0, -1.9, 0), 0.34)
        for (x, dz, sc) in POSTS:
            r = D.mmul(D.roty(ang + x * 0.3), D.rotx(0.40))
            r = tuple(tuple(c * sc for c in row) for row in r)
            D.draw_mesh(fb, cam, verts, tris, r,
                        (x, 0.55 + 0.42 * math.sin(ang * 2 + x), dz), 1.0)
    return draw


def main():
    frames = []
    for fi in range(FRAMES):
        lum = D.render_frame(W, H, scene(fi), ss=3)
        rgb = bytearray(len(lum) * 3)
        for i, v in enumerate(lum):
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = v
        frames.append(M.quantise(rgb, W, H))
        print(f"  frame {fi + 1}/{FRAMES}", end="\r", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, f"SPIN {W}x{H}", loop=True)
    raw = W * H * FRAMES
    print(f"\nwrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / raw:.1f}% of raw {raw})")
    if LEGACY:
        M.install_legacy(OUT, "SPIN")
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(frames[FRAMES // 4], W, H))


if __name__ == "__main__":
    main()
