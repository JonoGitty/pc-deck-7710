#!/usr/bin/env python3
"""Turn a video into a deck movie.

Anything ffmpeg can open — a phone clip, a screen recording, an MP4 off the
internet — becomes a `.dmv` the firmware, the preview and the legacy faceplate
all play.

    python3 tools/movies/import_video.py clip.mov                    # 256x64
    python3 tools/movies/import_video.py clip.mp4 --legacy           # 192x48 + install
    python3 tools/movies/import_video.py clip.mov --from=3 --dur=8   # a section
    python3 tools/movies/import_video.py clip.mov --crop=0.43,0.41,0.32,0.13
    python3 tools/movies/import_video.py clip.mov --probe            # where to crop
    python3 tools/movies/import_video.py vfd.mov --invert --blur=3   # filmed off a screen

This is `import_gif.py` with a different front door, and it shares that file's
`fit`, `pick_levels` and `saturation` rather than reimplementing them — the
hard part was never the decoding, it is that footage assumes a tonal range and
a shape the deck does not have. Read that file's header for the reasoning; all
of it applies here and more so, because video is *always* photographic.

WHAT VIDEO ADDS OVER A GIF

  * **It is far too long.** A GIF someone saved is a few seconds; a phone clip
    is minutes, and a minute at 10 fps is 600 frames of flash. `--from` and
    `--dur` cut a section, and the default caps at 30 seconds rather than
    quietly writing a movie bigger than the partition it has to live in.

  * **It is the wrong shape, badly.** A GIF is roughly square; a phone video is
    9:16 or 16:9 against a panel that is 4:1. Letterboxed, a portrait clip
    occupies a ninth of the panel. So `--cover` is the DEFAULT here where it is
    not for GIFs, and `--letterbox` opts out.

  * **The subject is usually a small part of the frame.** Somebody filming a
    thing has the thing in the middle and a room around it. `--crop` takes
    fractions of the frame rather than pixels, so the numbers survive a
    rescale and can be read straight off `--probe`.

  * **60 fps.** Resampled to the deck's 10, by asking ffmpeg for the rate we
    want rather than decoding everything and throwing 5 frames in 6 away.

FILMING A SCREEN IS THE HARD CASE, AND IT HAS TWO FLAGS

A phone video of another display — a head unit, a monitor, a VFD — is the most
likely thing anyone points this at, and it fails twice without help:

  * `--blur=3` because the source's dot grid beats against the deck's and the
    moire drowns the picture. Blur it away before the downscale.
  * `--invert` because a VFD lights its background and leaves the subject dark,
    which is the opposite of how this deck draws.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmv as M
from import_gif import fit, pick_levels, saturation

try:
    from PIL import Image
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow")

# Long enough for anything worth watching on a head unit, short enough that a
# careless import cannot fill the movies partition. Override with --dur.
MAX_SECONDS = 30
# Decode width. The panel is 256 dots across; anything past a few hundred
# pixels is thrown away by the downscale and only costs time.
DECODE_W = 640


def need_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            sys.exit(f"needs {tool}.  apt install ffmpeg  /  brew install ffmpeg")


def probe(path):
    """(width, height, duration_seconds)."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    vals = [v for v in r.stdout.split() if v]
    if len(vals) < 3:
        sys.exit(f"ffprobe could not read {path}:\n{r.stderr.strip()}")
    return int(vals[0]), int(vals[1]), float(vals[2])


def decode(path, fps, start, dur, crop, sw, sh, blur=0.0):
    """Frames as PIL images, at `fps`, cropped and scaled down.

    Read as raw rgb24 off a pipe rather than written to a directory of PNGs:
    the frame count is knowable in advance, the format is fixed, and a
    temporary directory of ten thousand images is a worse failure mode than a
    pipe when somebody points this at a feature film.
    """
    vf = [f"fps={fps}"]
    # Blur BEFORE the downscale, which is the only place it works. Filming a
    # dot-matrix panel and resampling it onto another dot-matrix panel beats
    # one grid against the other, and the moire wins: the subject vanishes into
    # a 50% checkerboard. A couple of pixels of blur removes the source's own
    # dots and leaves its picture, and the difference is not subtle — it is the
    # difference between two readable dolphins and a field of noise.
    if blur:
        vf.append(f"boxblur={blur}:1")
    if crop:
        x, y, w, h = crop
        vf.append("crop=%d:%d:%d:%d" % (max(2, int(sw * w)), max(2, int(sh * h)),
                                        int(sw * x), int(sh * y)))
        cw, ch = max(2, int(sw * w)), max(2, int(sh * h))
    else:
        cw, ch = sw, sh
    ow = min(DECODE_W, cw)
    oh = max(2, int(round(ch * ow / cw)))
    ow -= ow & 1
    oh -= oh & 1
    vf.append(f"scale={ow}:{oh}")

    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", str(start)]          # before -i: seeks, rather than decoding to
    cmd += ["-i", path, "-t", str(dur), "-vf", ",".join(vf),
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = ow * oh * 3
    out = []
    while True:
        buf = p.stdout.read(size)
        if not buf or len(buf) < size:
            break
        out.append(Image.frombytes("RGB", (ow, oh), buf))
    err = p.stderr.read().decode("utf-8", "replace")
    p.wait()
    if not out:
        sys.exit(f"no frames decoded from {path}\n{err.strip()}")
    return out


def show_probe(path, sw, sh, dur):
    """Suggest a --crop, by finding the part of the frame that MOVES.

    The obvious heuristic — "crop to the brightest region" — is wrong, and
    wrong in a way that looks right until you try it. Pointed at a head unit on
    a desk it selects the lit wall behind the deck, because a room is brighter
    in aggregate than a small blue display in it. Tried, failed, replaced.

    What actually distinguishes a screen from a room is that the screen
    changes. So: sample frames across the clip and take the per-pixel spread.
    That alone is not enough either — a hand-held shot moves every
    high-contrast edge in the room — so the busy pixels go into a coarse
    density map, and the box grows outward from the densest cell. A screen is
    busy *throughout*; a wobbling table edge is busy along a line.

    Still a suggestion, not a measurement: on a hand-held clip it lands in the
    right neighbourhood and usually somewhat wide. Look at the ASCII before
    believing it, which is why this prints one.
    """
    n = 8
    frames = decode(path, max(1, int(n / max(0.5, dur))), 0.0, dur, None, sw, sh)
    frames = frames[:: max(1, len(frames) // n)][:n]
    if len(frames) < 2:
        print("  too short to detect movement — crop by eye")
        return
    w, h = frames[0].size
    gray = [f.convert("L").load() for f in frames]

    spread, vals = {}, []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            v = [g[x, y] for g in gray]
            s = max(v) - min(v)
            spread[(x, y)] = s
            vals.append(s)
    vals.sort()
    thr = max(18, vals[int(len(vals) * 0.90)])       # floor: sensor noise moves too
    busy = [p for p, s in spread.items() if s >= thr]

    print(f"\n  source {sw}x{sh}, {dur:.1f}s")
    if len(busy) > 20:
        # A percentile box over the busy pixels is not enough either: a
        # hand-held shot moves every high-contrast edge in the room, so the box
        # grows to the whole frame. What separates a screen from a wobbling
        # table edge is DENSITY — the screen is busy everywhere inside itself,
        # an edge is busy along a line. So: coarse density map, find the peak,
        # and grow a box outward while its neighbours are still busy.
        GX, GY = 24, 18
        cw, ch = w / GX, h / GY
        dens = [[0] * GX for _ in range(GY)]
        for (x, y) in busy:
            dens[min(GY - 1, int(y / ch))][min(GX - 1, int(x / cw))] += 1
        peak = max((dens[j][i], i, j) for j in range(GY) for i in range(GX))
        pv, pi, pj = peak
        keep = pv * 0.30
        i0 = i1 = pi
        j0 = j1 = pj
        grew = True
        while grew:
            grew = False
            if i0 > 0 and max(dens[j][i0 - 1] for j in range(j0, j1 + 1)) >= keep:
                i0 -= 1; grew = True
            if i1 < GX - 1 and max(dens[j][i1 + 1] for j in range(j0, j1 + 1)) >= keep:
                i1 += 1; grew = True
            if j0 > 0 and max(dens[j0 - 1][i] for i in range(i0, i1 + 1)) >= keep:
                j0 -= 1; grew = True
            if j1 < GY - 1 and max(dens[j1 + 1][i] for i in range(i0, i1 + 1)) >= keep:
                j1 += 1; grew = True
        x0, x1 = i0 * cw, (i1 + 1) * cw
        y0, y1 = j0 * ch, (j1 + 1) * ch
        print("  the part of the frame that moves is roughly:")
        print("    --crop=%.3f,%.3f,%.3f,%.3f"
              % (x0 / w, y0 / h, (x1 - x0) / w, (y1 - y0) / h))
        crop = frames[len(frames) // 2].crop((int(x0), int(y0), int(x1), int(y1)))
        print("\n  that region, as the deck would show it:\n")
        print(M.to_ascii(M.quantise(bytearray(fit(crop, 96, 24, True).tobytes()),
                                    96, 24), 96, 24))
    else:
        print("  nothing moves much — crop by eye")
    print("\n  the whole frame, as the deck would show it:\n")
    print(M.to_ascii(M.quantise(bytearray(fit(frames[0], 96, 24, True).tobytes()),
                                96, 24), 96, 24))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        sys.exit(__doc__)
    need_ffmpeg()

    src = args[0]
    legacy = "--legacy" in flags
    w = int(args[1]) if len(args) > 1 else 256
    h = int(args[2]) if len(args) > 2 else 64
    if legacy:
        w, h = 192, 48

    fps, keep, gamma, name = 10, None, 1.0, None
    start, dur, crop, blur = 0.0, None, None, 0.0
    for f in flags:
        if f.startswith("--fps="):      fps = int(f.split("=")[1])
        elif f.startswith("--keep="):   keep = float(f.split("=")[1])
        elif f.startswith("--gamma="):  gamma = float(f.split("=")[1])
        elif f.startswith("--name="):   name = f.split("=", 1)[1]
        elif f.startswith("--from="):   start = float(f.split("=")[1])
        elif f.startswith("--dur="):    dur = float(f.split("=")[1])
        elif f.startswith("--blur="):   blur = float(f.split("=")[1])
        elif f.startswith("--crop="):
            crop = tuple(float(v) for v in f.split("=")[1].split(","))
            if len(crop) != 4:
                sys.exit("--crop wants four fractions: x,y,w,h")

    sw, sh, total = probe(src)
    if "--probe" in flags:
        show_probe(src, sw, sh, total)
        return

    if dur is None:
        dur = min(MAX_SECONDS, max(0.1, total - start))
        if total - start > MAX_SECONDS:
            print(f"  ! {total:.0f}s of source; taking the first {MAX_SECONDS}."
                  "  --dur= for more, --from= to start elsewhere")

    print(f"decoding {os.path.basename(src)}  {sw}x{sh} "
          f"-> {w}x{h} @ {fps}fps, {dur:.1f}s from {start:.1f}s")
    imgs = decode(src, fps, start, dur, crop, sw, sh, blur)

    # Cover by default, unlike the GIF importer: a phone video letterboxed onto
    # a 4:1 panel is a postage stamp in the middle of a black strip.
    cover = "--letterbox" not in flags
    fitted = [fit(im, w, h, cover) for im in imgs]

    # --invert exists for footage of a POSITIVE display: a VFD lights its
    # background and leaves the subject dark, which is the opposite of how this
    # deck draws. Imported as-is, the lit field becomes a full-panel
    # checkerboard and the subject disappears into it. Also right for anything
    # filmed off paper or a white screen.
    if "--invert" in flags:
        from PIL import ImageOps
        fitted = [ImageOps.invert(im) for im in fitted]

    sat = saturation(fitted[len(fitted) // 2])
    if sat > 60:
        print(f"  ! strongly coloured source (mean chroma {sat:.0f}/255).\n"
              "    The deck has no hue — anything that reads by colour alone\n"
              "    merges into one shape. Try --keep= to drop the background.")

    lo = hi = None
    if keep is not None:
        lo, hi = pick_levels(fitted[::4] or fitted, keep)
        print(f"  levels: keeping the brightest {keep:g}% — "
              f"black at {lo:.0f}/255, white at {hi:.0f}/255")

    frames = []
    for k, img in enumerate(fitted):
        frames.append(M.quantise(bytearray(img.tobytes()), w, h,
                                 stretch=True, lo=lo, hi=hi, gamma=gamma))
        print(f"  {k + 1}/{len(fitted)}", end="\r", flush=True)
    print()

    name = (name or os.path.splitext(os.path.basename(src))[0]).upper()[:24]
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "..", "movies",
                       f"{name.lower().replace(' ', '_')}_{w}x{h}.dmv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    blob = M.write_dmv(out, frames, w, h, fps, name, loop=True)
    print(f"wrote {os.path.relpath(out)}  {len(blob)} bytes  "
          f"{len(frames)} frames @ {fps}fps")
    if legacy:
        M.install_legacy(out, name)
        print("installed into the PC deck — press V on the faceplate")
    print(M.to_ascii(frames[len(frames) // 3], w, h))


if __name__ == "__main__":
    main()
