#!/usr/bin/env python3
"""Independent .dmv decoder — the reference for the C player."""
import struct, sys

blob = open(sys.argv[1], "rb").read()
assert blob[:4] == b"DMV1", "bad magic"
w, h, fps, flags, nframes, namelen = struct.unpack_from("<HHBBHH", blob, 4)
name = blob[14:14 + namelen].decode("ascii")
print(f"open {name} {w}x{h} fps={fps} frames={nframes} loop={1 if flags & 1 else 0}")

def fnv1a(b):
    x = 2166136261
    for v in b:
        x = ((x ^ v) * 16777619) & 0xffffffff
    return x

first = 14 + namelen
cells = w * h
grid = bytearray(cells)
at, frame = first, 0
for i in range(nframes * 3 // 2):
    if frame >= nframes:
        if not (flags & 1):
            print(f"step {i}: stopped"); break
        grid = bytearray(cells); at, frame = first, 0
    runs, = struct.unpack_from("<H", blob, at); at += 2
    for _ in range(runs):
        start, length, level = struct.unpack_from("<HHB", blob, at); at += 5
        if start + length <= cells:
            for k in range(length):
                grid[start + k] = min(level, 4)
    frame += 1
    print(f"{i} {fnv1a(grid):08x} {sum(1 for v in grid if v)}")
