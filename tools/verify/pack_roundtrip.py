#!/usr/bin/env python3
"""Pack movies into a partition image, then read it back the way the firmware
will and check every blob still decodes.

The firmware reads this container in C (firmware/esp32/components/deck_movies)
on a chip nobody here can run, so the directory format is exactly the kind of
thing that drifts silently: an off-by-one in the entry stride or the alignment
padding would produce an image that looks fine and boots to garbage. Reading it
back with an independent implementation is cheap insurance.

    python3 tools/verify/pack_roundtrip.py build/movies.bin
"""
import os
import struct
import subprocess
import sys

HEADER, ENTRY = 8, 40


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else "build/movies.bin"
    img = open(img_path, "rb").read()
    if img[:4] != b"DMVP":
        sys.exit("bad container magic")
    count, _ = struct.unpack_from("<HH", img, 4)

    seen = 0
    for i in range(count):
        name, off, length = struct.unpack_from("<32sII", img, HEADER + i * ENTRY)
        name = name.split(b"\0")[0].decode("ascii", "replace")
        if off + length > len(img):
            sys.exit(f"{name}: entry runs past the end of the image")
        blob = img[off:off + length]
        if blob[:4] != b"DMV1":
            sys.exit(f"{name}: entry does not point at a .dmv")
        # The name in the directory must match the name inside the movie, or
        # the deck's menu lies about what it is about to play.
        nl = struct.unpack_from("<H", blob, 12)[0]
        inner = blob[14:14 + nl].decode("ascii", "replace")[:31]
        if inner != name:
            sys.exit(f"directory says {name!r}, movie says {inner!r}")

        tmp = f"/tmp/packcheck_{i}.dmv"
        with open(tmp, "wb") as fh:
            fh.write(blob)
        r = subprocess.run(["build/verify_movie_c", tmp],
                           capture_output=True, text=True)
        os.unlink(tmp)
        if r.returncode != 0 or not r.stdout.startswith("open "):
            sys.exit(f"{name}: does not replay out of the container\n{r.stderr}")
        seen += 1

    print(f"movie container round-trips: {seen} movies, "
          f"{len(img) / 1024:.0f} KB image")


if __name__ == "__main__":
    main()
