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

# Off, dim, main, hot. Level 4 is DECK_CLIP — the over/clipping indicator,
# which renders red on colour targets and means "the audio is clipping". A
# movie must never produce it, for the same reason the album art dither
# doesn't: it is a status colour, not a brightness.
LEVELS = 4


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def quantise(rgb, w, h, black=24, stretch=True, lo=None, hi=None, gamma=1.0):
    """RGB bytes -> one level per dot.

    `black` is the luminance below which a dot is off rather than dim; without
    it a dark scene dithers into a grey haze instead of reading as night.

    `lo`/`hi` override the input range the levels are stretched across, and
    `gamma` shapes the curve between them. Rendered scenes never need these —
    they are composed against black already. Imported footage usually does: a
    photographic source spreads its luminance over the whole range, and with
    only four levels a mid-grey background does not become "background", it
    becomes a 50% dither that is visually louder than the subject. Pulling `lo`
    up to sit above the background crushes it to off and hands all four levels
    to the thing you actually wanted to see.
    """
    lum = [luma(rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]) for i in range(w * h)]
    if lo is None:
        lo = min(lum) if stretch else 0.0
    if hi is None:
        hi = max(lum) if stretch else 255.0
    span = max(30.0, hi - lo)
    black = max(black, lo)

    out = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if lum[i] < black:
                continue                       # stays 0
            v = (lum[i] - lo) / span
            if v > 1.0:
                v = 1.0
            if gamma != 1.0:
                v = v ** gamma
            v *= LEVELS - 0.001
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


def install_legacy(dmv_path, name, repo_root=None):
    """Copy a .dmv into the legacy faceplate and register it in its index.

    The PC deck plays the same container the firmware does, so an animation
    made for a head unit can be watched on the PC first — which is the only
    display most people have while they wait for parts.
    """
    import os
    import shutil
    root = repo_root or os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    dest_dir = os.path.join(root, "legacy", "web", "movies")
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.basename(dmv_path)
    shutil.copy2(dmv_path, os.path.join(dest_dir, base))

    index_path = os.path.join(dest_dir, "index.json")
    try:
        with open(index_path) as fh:
            entries = json.load(fh)
    except Exception:
        entries = []
    url = "/web/movies/" + base
    entries = [e for e in entries if e.get("url") != url]
    entries.append({"name": name, "url": url})
    with open(index_path, "w") as fh:
        json.dump(entries, fh, indent=1)
    return url
