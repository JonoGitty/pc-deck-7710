#!/usr/bin/env python3
"""Pack .dmv movies into a flash partition image.

    python3 tools/movies/pack.py build/movies.bin movies/*_256x64.dmv
    esptool.py write_flash 0x490000 build/movies.bin

Movies do not go in the firmware image. A 256x64 movie is 300-850 KB and the
app partition is 1.5 MB, which has to hold Bluetooth, WiFi, TLS, the FFT and
the renderer; one movie would take most of what is left and three would not
fit at all. They get their own read-only partition instead, and the decoder
streams out of it — see core/movie.h and firmware/esp32/partitions.csv.

The container is deliberately trivial: a fixed-size directory, then the blobs.
No compression, because a .dmv is already delta-coded, and no index beyond the
offsets, because the firmware reads it once at boot into 16 slots.

    off  size  field
    0    4     magic "DMVP"
    4    2     entry count (u16 LE)
    6    2     reserved
    8    n*40  entries: char name[32], u32 offset, u32 length
    ..         the .dmv blobs, each 4-byte aligned
"""
import os
import struct
import sys

MAGIC = b"DMVP"
HEADER = 8
ENTRY = 40
MAX = 16


def dmv_name(blob, fallback):
    """The name the movie calls itself, so the deck's menu matches the file."""
    if len(blob) < 14 or blob[:4] != b"DMV1":
        raise SystemExit("not a .dmv")
    n = struct.unpack_from("<H", blob, 12)[0]
    return blob[14:14 + n].decode("ascii", "replace") or fallback


def pack(paths):
    if len(paths) > MAX:
        raise SystemExit(f"at most {MAX} movies (the firmware holds {MAX} slots)")
    blobs, names = [], []
    for p in paths:
        b = open(p, "rb").read()
        blobs.append(b)
        names.append(dmv_name(b, os.path.basename(p))[:31])

    out = bytearray(MAGIC + struct.pack("<HH", len(blobs), 0))
    out += bytes(ENTRY * len(blobs))
    body = bytearray()
    at = HEADER + ENTRY * len(blobs)
    for i, b in enumerate(blobs):
        off = at + len(body)
        body += b
        # Align so a partition read of the header lands on a word boundary; the
        # ESP32 does not require it for esp_partition_read, but an mmap'd
        # pointer handed straight to the decoder would.
        while (at + len(body)) % 4:
            body += b"\0"
        struct.pack_into("<32sII", out, HEADER + i * ENTRY,
                         names[i].encode("ascii", "replace"), off, len(b))
    return bytes(out + body), names, [len(b) for b in blobs]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    dst, srcs = sys.argv[1], sys.argv[2:]
    img, names, sizes = pack(srcs)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "wb") as fh:
        fh.write(img)
    for n, s, p in zip(names, sizes, srcs):
        print(f"  {n:<20s} {s / 1024:8.1f} KB  {p}")
    print(f"  {'-> ' + dst:<20s} {len(img) / 1024:8.1f} KB "
          f"({len(img) / 1048576:.2f} MB of the 7.25 MB partition)")


if __name__ == "__main__":
    main()
