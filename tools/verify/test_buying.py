#!/usr/bin/env python3
"""Check that the buying page has not drifted from the parts list or the cars.

    python3 tools/verify/test_buying.py

WHY THIS EXISTS, WHICH IS A BUG THIS REPOSITORY SHIPPED

`docs/BUYING.md` is maintained by hand, and it drifted twice:

**It told you to buy something the car cannot use.** It recommended an InCarTec
29-629 "Honda S2000 steering-wheel audio control interface", £59.99 — a real
part, listed under the S2000 by name. The S2000 has no steering-wheel controls
in any market or trim, which `vehicles/honda/s2000/*.json` says in as many
words. Two clicks apart, and the buying page won.

**It left out the part without which nothing makes a sound.** The amplifier and
the PT2313 were added to `BUILD.md` and never reached `BUYING.md`, so it was
possible to order everything on the page and end up with a deck that could
neither drive a speaker nor change how loud it was.

Both are the same failure: a second copy of information that already exists
somewhere, going stale quietly. So this checks the two joins rather than the
prose — every part named in the BOM must be buyable from the buying page, and no
car may be sold a wheel-control interface it has no wheel controls for.

It cannot check that a price is current or a link alive. Nothing here can; that
is what §6 of the page is for.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Every part the BOM says you need, by the name you would search for. Kept as a
# literal list rather than parsed out of BUILD.md's tables: the tables are prose
# and change shape, and a parser that silently matched nothing would make this
# check pass by accident — which is exactly the failure mode being fixed.
BOM = [
    "WROVER",            # the board
    "SSD1322",           # the panel
    "GP1294AI",          # the other panel
    "PCM5102A",          # the DAC
    "PT2313",            # volume, and the mux replacement
    "TDA7850",           # the amplifier
    "Si4735",            # the tuner
    "INMP441",           # the microphone
    "74HC4052",          # the mux, for the builds that keep it
    "PC817",             # ignition sense
]

_fails = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<58} {'' if ok else detail}")
    if not ok:
        _fails.append(name)


def main():
    buying = open(os.path.join(ROOT, "docs", "BUYING.md"),
                  encoding="utf-8").read()

    print("the buying page still matches the parts list")
    for part in BOM:
        check(f"you can find out where to buy a {part}",
              part.lower() in buying.lower(),
              "in BUILD.md's BOM but not in BUYING.md")

    # An amplifier is the one whose absence is silent — the deck boots, plays,
    # shows the analyser, and drives nothing.
    check("the page says the deck needs an amplifier",
          "amplifier" in buying.lower()
          and ("line level" in buying.lower() or "TDA7850" in buying))

    print("\nand has not started selling parts the cars cannot use")
    for path in sorted(glob.glob(os.path.join(ROOT, "vehicles", "*", "*", "*.json"))):
        with open(path, encoding="utf-8") as f:
            car = json.load(f)
        name = f"{car['brand']} {car['model']} {car['generation']}"
        if not car["swc"]["v"].lower().startswith(("none", "⚠️ none", "no ")):
            continue
        # A car with no wheel controls must not have a wheel-control interface
        # recommended for it BY NAME. The generic "only if your car has them"
        # row is the correct way to mention the category at all.
        model = car["model"].lower().replace("-", "")
        bad = []
        for line in buying.splitlines():
            low = line.lower().replace("-", "")
            if model in low and ("steering wheel" in low or "swc" in low):
                if "only if" in low or "have none" in low or "no wheel" in low:
                    continue          # the warning itself, which is wanted
                bad.append(line.strip()[:90])
        check(f"{name} is not sold a wheel-control interface",
              not bad, " | ".join(bad))

    # The doctrine, restated as a check: per-car SKUs belong in vehicles/, which
    # is one file per generation, not in a page somebody edits by hand.
    skus = re.findall(r"\b(?:29-629|CTSHO\d+|CT20HD\d+|CT55-HD\d+)\b", buying)
    named_as_recommendation = [
        s for s in skus
        if re.search(rf"^\|.*{re.escape(s)}", buying, re.M)
    ]
    check("no per-car part number is a table row on this page",
          not named_as_recommendation,
          f"{named_as_recommendation} — put it in vehicles/ instead")

    print()
    if _fails:
        print(f"{len(_fails)} buying check(s) failed")
        return 1
    print("buying checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
