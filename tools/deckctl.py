#!/usr/bin/env python3
"""deckctl — build a deck, put it on the hardware, and find out what it's doing.

One command for the whole loop, because the alternative is six tools with
different conventions and a wiki page nobody keeps current.

    python3 tools/deckctl.py doctor            # what is plugged in, what works
    python3 tools/deckctl.py build             # compile for your panel
    python3 tools/deckctl.py flash             # firmware onto the deck
    python3 tools/deckctl.py movies            # pick animations, write them
    python3 tools/deckctl.py logs              # watch it run
    python3 tools/deckctl.py coredump          # why it crashed

Run it with no arguments for a guided setup that does all of the above in the
right order.

WHY A TOOL AND NOT A README SECTION. Getting a deck working means holding four
things in your head at once: which panel you have, which partition offset the
movies go to, which serial port appeared, and what the flash size is. Every one
of them is knowable by the machine, and every one of them is a way to brick an
afternoon. So they are knowable by the machine.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(ROOT, "firmware", "esp32")

# Panels the firmware can be built for. The grid is not a preference — it is
# what the UI is laid out against, which is why this is a build-time choice
# and lives here rather than in a settings menu.
PANELS = {
    "ssd1322":  {"grid": (256, 64), "levels": 16, "desc": "SSD1322 OLED, 16 greys — the recommended build"},
    "gp1294ai": {"grid": (256, 48), "levels": 2,  "desc": "Futaba GP1294AI VFD, 1-bit — the authentic one"},
}

# Read from partitions.csv rather than hardcoded, so the table stays the single
# source of truth and a resize cannot silently desync the flash offset.
def partitions():
    out = {}
    path = os.path.join(FW, "partitions.csv")
    for line in open(path):
        line = line.split("#")[0].strip()
        if not line:
            continue
        f = [x.strip() for x in line.split(",")]
        if len(f) >= 5 and f[3].startswith("0x"):
            out[f[0]] = (int(f[3], 16), int(f[4], 16))
    return out


# ------------------------------------------------------------------ helpers
class Colour:
    ok = "\033[32m"; warn = "\033[33m"; bad = "\033[31m"
    dim = "\033[2m"; bold = "\033[1m"; off = "\033[0m"
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        ok = warn = bad = dim = bold = off = ""


C = Colour


def say(msg, kind="info"):
    mark = {"ok": C.ok + "  ok  " + C.off, "warn": C.warn + " warn " + C.off,
            "bad": C.bad + " fail " + C.off, "info": "      "}[kind]
    print(f"{mark} {msg}")


def run(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw)


def have(binary):
    return shutil.which(binary) is not None


def find_ports():
    """Serial ports that look like a dev board.

    Deliberately not "the first ttyUSB": on a laptop with a phone, an Arduino
    and a USB-serial adapter plugged in there will be several, and flashing the
    wrong one is a bad afternoon.
    """
    found = []
    for pat in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/cu.usbserial*",
                "/dev/cu.SLAB*", "/dev/cu.wchusbserial*", "COM*"):
        found += glob.glob(pat)
    return sorted(found)


def pick_port(explicit=None):
    if explicit:
        return explicit
    ports = find_ports()
    if not ports:
        say("no serial port found. Is the deck plugged in over USB?", "bad")
        print("""
      On Linux you may also need permission to use it:
          sudo usermod -aG dialout $USER      (then log out and back in)
      Some cheap boards need a driver on macOS (CP210x or CH340).
      If the board has a BOOT button, hold it while plugging in.
""")
        sys.exit(1)
    if len(ports) == 1:
        return ports[0]
    print("More than one serial port. Which is the deck?")
    for i, p in enumerate(ports):
        print(f"  {i + 1}) {p}")
    n = input("  number: ").strip()
    return ports[int(n) - 1]


def idf_env():
    """ESP-IDF, or a clear explanation of how to get it.

    The commonest first failure is running this in a shell where export.sh was
    never sourced, and the error idf.py gives for that is not obvious.
    """
    if have("idf.py"):
        return True
    idf = os.environ.get("IDF_PATH") or os.path.expanduser("~/esp/esp-idf")
    if os.path.isdir(idf):
        say(f"ESP-IDF found at {idf} but not activated in this shell", "warn")
        print(f"\n      Run this first, in this terminal:\n"
              f"          . {idf}/export.sh\n")
    else:
        say("ESP-IDF is not installed", "bad")
        print("""
      The firmware needs Espressif's SDK. About 2 GB, one time:

          git clone -b release/v5.3 --recursive \\
              https://github.com/espressif/esp-idf.git ~/esp/esp-idf
          ~/esp/esp-idf/install.sh esp32
          . ~/esp/esp-idf/export.sh

      Then run this command again in the same terminal.
""")
    return False


# ------------------------------------------------------------------ doctor
def cmd_doctor(args):
    """Everything that could be wrong before you have even started."""
    print(f"\n{C.bold}DECK-7710 — checking your setup{C.off}\n")

    ok = True
    say(f"python {sys.version.split()[0]}", "ok")

    if have("idf.py"):
        v = subprocess.run(["idf.py", "--version"], capture_output=True, text=True)
        say(f"esp-idf {v.stdout.strip() or v.stderr.strip()}", "ok")
    else:
        ok = False
        idf_env()

    try:
        import esptool  # noqa: F401
        say("esptool present", "ok")
    except ImportError:
        say("esptool missing — pip install esptool", "warn")

    try:
        import serial  # noqa: F401
        say("pyserial present", "ok")
    except ImportError:
        say("pyserial missing — pip install pyserial (needed for logs)", "warn")

    ports = find_ports()
    if ports:
        say(f"serial: {', '.join(ports)}", "ok")
    else:
        say("no serial port — plug the deck in over USB", "warn")

    # Chip identification is the check that catches the single most expensive
    # mistake in this project: buying an S3, which cannot do A2DP at all.
    if ports and have("esptool.py"):
        r = subprocess.run(["esptool.py", "--port", ports[0], "chip_id"],
                           capture_output=True, text=True, timeout=30)
        m = re.search(r"Chip is (ESP32[^\s(]*)", r.stdout)
        if m:
            chip = m.group(1)
            if chip.startswith("ESP32-S") or chip.startswith("ESP32-C"):
                say(f"chip is {chip} — THIS WILL NOT WORK", "bad")
                print("""
      Only the ORIGINAL ESP32 has Bluetooth Classic, and Bluetooth Classic is
      what A2DP audio needs. An S3, C3 or C6 cannot receive audio from a phone
      at all. Get an ESP32-WROVER-E. See docs/HARDWARE.md.
""")
                ok = False
            else:
                say(f"chip is {chip}", "ok")
        if "PSRAM" in r.stdout or "Features:" in r.stdout:
            feat = re.search(r"Features: (.*)", r.stdout)
            if feat and "PSRAM" not in feat.group(1):
                say("no PSRAM detected — get the WROVER-E variant", "warn")

    n = len(glob.glob(os.path.join(ROOT, "movies", "*.dmv")))
    say(f"{n} movies available to install", "ok" if n else "warn")

    print()
    if ok:
        print(f"  {C.ok}Ready.{C.off}  Next:  python3 tools/deckctl.py build\n")
    else:
        print(f"  {C.warn}Fix the above first.{C.off}\n")
    return 0 if ok else 1


# ------------------------------------------------------------------ build
def cmd_build(args):
    if not idf_env():
        return 1
    panel = args.display
    say(f"building for {panel} — {PANELS[panel]['desc']}")
    bdir = os.path.join(FW, "build" if panel == "ssd1322" else f"build-{panel}")
    r = run(["idf.py", "-B", bdir, f"-DDECK_DISPLAY={panel}", "build"], cwd=FW)
    if r.returncode:
        say("build failed — the compiler output above says why", "bad")
        return r.returncode
    binp = os.path.join(bdir, "deck7710.bin")
    say(f"{os.path.relpath(binp, ROOT)}  {os.path.getsize(binp) / 1024:.0f} KB", "ok")
    return 0


# ------------------------------------------------------------------ flash
def cmd_flash(args):
    panel = args.display
    bdir = os.path.join(FW, "build" if panel == "ssd1322" else f"build-{panel}")
    if not os.path.exists(os.path.join(bdir, "deck7710.bin")):
        say("nothing built yet for this panel", "warn")
        if cmd_build(args):
            return 1
    if not idf_env():
        return 1
    port = pick_port(args.port)
    say(f"flashing {panel} firmware to {port}")
    # idf.py flash rather than a hand-rolled esptool line: it reads the same
    # partition table the image was built against, so the offsets cannot drift.
    r = run(["idf.py", "-B", bdir, f"-DDECK_DISPLAY={panel}",
             "-p", port, "-b", str(args.baud), "flash"], cwd=FW)
    if r.returncode:
        say("flash failed", "bad")
        print("""
      Most often one of:
        - the board needs BOOT held down while it starts (some clones do)
        - another program has the port open (a serial monitor, the Arduino IDE)
        - a charge-only USB cable. They look identical to data cables.
""")
        return r.returncode
    say("flashed. Watch it boot:  python3 tools/deckctl.py logs", "ok")
    return 0


# ------------------------------------------------------------------ movies
def cmd_movies(args):
    """Choose what the deck plays, pack it, and write it to flash.

    Movies are content, not firmware. They live in their own partition, so
    changing them does not touch the image and an OTA does not touch them.
    """
    panel = args.display
    w, h = PANELS[panel]["grid"]
    avail = sorted(glob.glob(os.path.join(ROOT, "movies", f"*_{w}x{h}.dmv")))

    if not avail:
        say(f"no movies rendered at {w}x{h} yet", "warn")
        print(f"""
      Render the bundled ones for your panel:
          python3 tools/movies/scene_solar.py {w} {h}
          python3 tools/movies/scene_touge.py {w} {h}
          python3 tools/movies/scene_dolphins.py {w} {h}

      Or convert a GIF you already have:
          python3 tools/movies/import_gif.py yours.gif {w} {h} --keep=22
""")
        return 1

    chosen = []
    if args.all:
        chosen = avail
    elif args.movie:
        for want in args.movie:
            hit = [p for p in avail if want.lower() in os.path.basename(p).lower()]
            if not hit:
                say(f"no movie matching {want!r}", "bad")
                return 1
            chosen += hit
    else:
        print(f"\n{C.bold}Movies available at {w}x{h}{C.off}\n")
        for i, p in enumerate(avail):
            size = os.path.getsize(p) / 1024
            print(f"  {i + 1}) {os.path.basename(p)[:-4]:<22} {size:7.0f} KB")
        print(f"\n  Enter numbers separated by spaces, or 'all'.")
        pick = input("  choose: ").strip()
        chosen = avail if pick.lower() == "all" else [avail[int(i) - 1] for i in pick.split()]

    img = os.path.join(FW, "build", "movies.bin")
    os.makedirs(os.path.dirname(img), exist_ok=True)
    r = run([sys.executable, os.path.join(ROOT, "tools", "movies", "pack.py"), img] + chosen)
    if r.returncode:
        return r.returncode

    offset, size = partitions()["movies"]
    actual = os.path.getsize(img)
    if actual > size:
        say(f"{actual / 1048576:.1f} MB will not fit the {size / 1048576:.1f} MB "
            f"partition — choose fewer", "bad")
        return 1
    say(f"{actual / 1024:.0f} KB of {size / 1048576:.1f} MB partition used", "ok")

    if args.no_write:
        say(f"image at {os.path.relpath(img, ROOT)}, not written", "ok")
        return 0

    port = pick_port(args.port)
    say(f"writing to {port} at {offset:#x}")
    r = run([sys.executable, "-m", "esptool", "--chip", "esp32", "--port", port,
             "-b", str(args.baud), "write_flash", hex(offset), img])
    if r.returncode == 0:
        say("done — press the MOVIE button, or V on the PC deck", "ok")
    return r.returncode


# ------------------------------------------------------------------ pictures
def cmd_pictures(args):
    """Your own photos, via the movie path.

    A still is a movie with one frame, so pictures need no new container, no
    new firmware path and no new failure mode — they become a .dmv and go
    wherever movies go. See tools/movies/import_image.py for what a photograph
    loses on four brightness levels, and which pictures survive it.
    """
    w, h = PANELS[args.display]["grid"]
    cmd = [sys.executable, os.path.join(ROOT, "tools", "movies", "import_image.py"),
           *args.image, str(w), str(h),
           f"--keep={args.keep}", f"--hold={args.hold}"]
    if args.name:
        cmd.append(f"--name={args.name}")
    r = run(cmd)
    if r.returncode:
        return r.returncode
    say("added to movies/ — install it with:  deckctl movies", "ok")
    return 0


# ------------------------------------------------------------------ logs
def cmd_logs(args):
    """Stream the deck's serial output, with the structured lines pulled out.

    The firmware emits `DECK|uptime|subsystem|event|key=value` for anything
    worth machine-reading. Everything else is ESP-IDF's own logging and passes
    through untouched, because when something is genuinely broken you want the
    stack trace, not a filtered view of it.
    """
    try:
        import serial
    except ImportError:
        say("pyserial needed: pip install pyserial", "bad")
        return 1

    port = pick_port(args.port)
    say(f"listening on {port} at {args.baud} — ctrl-C to stop", "ok")
    print(f"{C.dim}    (reset the deck to see the boot sequence from the start){C.off}\n")

    counts = {}
    with serial.Serial(port, args.baud, timeout=1) as s:
        try:
            while True:
                raw = s.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", "replace").rstrip()
                if line.startswith("DECK|"):
                    parts = line.split("|", 4)
                    if len(parts) >= 4:
                        ms, sub, ev = parts[1], parts[2], parts[3]
                        kv = parts[4] if len(parts) > 4 else ""
                        counts[f"{sub}.{ev}"] = counts.get(f"{sub}.{ev}", 0) + 1
                        col = C.bad if "fail" in kv else C.ok if ev == "health" else C.dim
                        print(f"{C.dim}{int(ms) / 1000:8.1f}s{C.off} "
                              f"{col}{sub:<8}{C.off} {ev:<10} {kv}")
                        continue
                if args.all or not line.startswith(("I (", "D (", "V (")):
                    print(f"{C.dim}         {line}{C.off}")
        except KeyboardInterrupt:
            print(f"\n\n{C.bold}events seen{C.off}")
            for k, v in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"  {v:5d}  {k}")
            print()
    return 0


# ------------------------------------------------------------------ coredump
def cmd_coredump(args):
    if not idf_env():
        return 1
    port = pick_port(args.port)
    bdir = os.path.join(FW, "build" if args.display == "ssd1322" else f"build-{args.display}")
    elf = os.path.join(bdir, "deck7710.elf")
    if not os.path.exists(elf):
        say("no ELF for this build — a core dump is unreadable without the "
            "exact binary that produced it", "bad")
        return 1
    say("reading the crash from flash")
    # The ELF must be the one that crashed. A rebuild between the crash and
    # this command moves every address and produces a confident, wrong trace.
    return run([sys.executable, "-m", "esp_coredump", "info_corefile",
                "-t", "raw", "-c", "flash", "-p", port, elf]).returncode


# ------------------------------------------------------------------ setup
def cmd_setup(args):
    """The whole thing, in order, for someone who has just cloned this."""
    print(f"""
{C.bold}DECK-7710 setup{C.off}

This will check your tools, build firmware for your panel, flash it, and put
some animations on it. Ctrl-C at any point is safe.

{C.warn}Before this goes anywhere near a vehicle, read SAFETY.md.{C.off}
""")
    if cmd_doctor(args):
        return 1

    print(f"\n{C.bold}Which panel do you have?{C.off}\n")
    keys = list(PANELS)
    for i, k in enumerate(keys):
        print(f"  {i + 1}) {k:<10} {PANELS[k]['desc']}")
    print("\n  If you have not bought one yet, press enter for the recommended build.")
    pick = input("  choose: ").strip()
    args.display = keys[int(pick) - 1] if pick else "ssd1322"

    if cmd_build(args):
        return 1
    if input("\n  Flash it now? [Y/n] ").strip().lower() not in ("", "y"):
        return 0
    if cmd_flash(args):
        return 1
    if input("\n  Install movies? [Y/n] ").strip().lower() in ("", "y"):
        cmd_movies(args)
    print(f"\n  {C.ok}Done.{C.off}  Watch it:  python3 tools/deckctl.py logs\n")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Build, flash and diagnose a DECK-7710.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run with no command for guided setup.")
    ap.add_argument("--display", "-d", choices=list(PANELS), default="ssd1322",
                    help="which panel the firmware is for (default: ssd1322)")
    ap.add_argument("--port", "-p", help="serial port (autodetected if omitted)")
    ap.add_argument("--baud", "-b", type=int, default=460800)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("doctor", help="check tools, board and wiring assumptions")
    sub.add_parser("build", help="compile the firmware for your panel")
    sub.add_parser("flash", help="write the firmware to the deck")

    pic = sub.add_parser("pictures", help="put your own photos on the deck")
    pic.add_argument("image", nargs="+", help="image files")
    pic.add_argument("--keep", type=float, default=35.0,
                     help="light the brightest N%% of the picture (default 35)")
    pic.add_argument("--hold", type=float, default=3.0, help="seconds per picture")
    pic.add_argument("--name", help="what the deck calls the set")

    m = sub.add_parser("movies", help="choose animations and write them to flash")
    m.add_argument("movie", nargs="*", help="names to install (default: ask)")
    m.add_argument("--all", action="store_true")
    m.add_argument("--no-write", action="store_true", help="pack only, do not flash")

    lg = sub.add_parser("logs", help="watch the deck's serial output")
    lg.add_argument("--all", action="store_true", help="include ESP-IDF info lines")

    sub.add_parser("coredump", help="decode the crash stored in flash")
    sub.add_parser("setup", help="guided end-to-end setup")

    args = ap.parse_args()
    fn = {"doctor": cmd_doctor, "build": cmd_build, "flash": cmd_flash,
          "movies": cmd_movies, "pictures": cmd_pictures, "logs": cmd_logs,
          "coredump": cmd_coredump, "setup": cmd_setup}.get(args.cmd, cmd_setup)
    for k, v in (("movie", []), ("all", False), ("no_write", False)):
        if not hasattr(args, k):
            setattr(args, k, v)
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
