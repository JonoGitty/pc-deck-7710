#!/usr/bin/env python3
"""Deck movie container — RGB frames in, a .dmv out.

The deck has no colours: it has five intensity levels, and the panel's output
stage decides what those become. So the quantiser maps luminance to 0..4 using
the same 4x4 ordered dither as the album art and the output stage, which is
what makes a rendered movie look like it belongs on the same glass rather than
like something pasted onto it.

Frames are delta-compressed as runs, which suits dot-matrix animation: most of
a frame does not move, and the parts that do tend to move in horizontal
stretches.
"""
import json
import struct

# Same matrix as core/out.c and core/art.c.
BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

LEVELS = 5          # DECK_OFF..DECK_CLIP


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def quantise(rgb, w, h, black=24, stretch=True):
    """RGB bytes -> one level per dot.

    `black` is the luminance below which a dot is off rather than dim; without
    it a dark scene dithers into a grey haze instead of reading as night.
    """
    lum = [luma(rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]) for i in range(w * h)]
    lo, hi = (min(lum), max(lum)) if stretch else (0.0, 255.0)
    span = max(30.0, hi - lo)

    out = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if lum[i] < black:
                continue                       # stays 0
            v = ((lum[i] - lo) / span) * (LEVELS - 0.001)
            t = (BAYER4[y & 3][x & 3] + 0.5) / 16.0
            q = int(v + t - 0.5)
            out[i] = 0 if q < 0 else (LEVELS - 1 if q > LEVELS - 1 else q)
    return out


def encode(frames, w, h, fps, name, loop=True):
    """frames: list of level buffers (bytes-like, w*h each). -> .dmv bytes."""
    name_b = name.encode("ascii", "replace")[:255]
    out = bytearray()
    out += b"DMV1"
    out += struct.pack("<HHBBHH", w, h, fps, 1 if loop else 0, len(frames), len(name_b))
    out += name_b

    prev = bytearray(w * h)                    # decoder starts from a clear grid
    for cur in frames:
        runs = []
        i = 0
        n = w * h
        while i < n:
            if cur[i] != prev[i]:
                v = cur[i]
                j = i
                while j < n and cur[j] == v and cur[j] != prev[j]:
                    j += 1
                runs.append((i, j - i, v))
                i = j
            else:
                i += 1
        out += struct.pack("<H", len(runs))
        for start, length, level in runs:
            out += struct.pack("<HHB", start, length, level)
        prev = bytearray(cur)
    return bytes(out)


def write_dmv(path, frames, w, h, fps, name, loop=True):
    blob = encode(frames, w, h, fps, name, loop)
    with open(path, "wb") as fh:
        fh.write(blob)
    return blob


def write_preview_json(path, frames, w, h, fps, name):
    """A JSON twin of the same data, for eyeballing in the browser preview."""
    doc = {"name": name, "w": w, "h": h, "fps": fps,
           "frames": [list(f) for f in frames]}
    with open(path, "w") as fh:
        json.dump(doc, fh, separators=(",", ":"))


def to_ascii(levels, w, h):
    """Dump one frame as text — the quickest way to see if a render is sane."""
    ramp = " .:*#"
    return "\n".join(
        "".join(ramp[levels[y * w + x]] for x in range(w)) for y in range(h))
