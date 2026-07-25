#!/usr/bin/env python3
"""Every vehicle file is complete, and every claim carries its confidence.

    python3 tools/verify/test_vehicles.py

This is a schema check, not a fact check — nothing here can tell you whether a
Honda harness adapter really is a 20-pin. What it can do is stop the two
failures that make a fitment table actively harmful:

**A missing field.** A car with no `swc` key reads as "the question was not
considered", which is indistinguishable on the page from "this car has none".
Those are very different for somebody deciding whether to buy a £30 interface
box, so a field that does not apply must say so out loud.

**A claim with no confidence marker.** Everything in this directory is either
checked, believed, or must be measured on the individual car, and a reader
cannot tell which by looking at the prose. If the marker is missing the claim
reads as fact, which for a part number is how somebody buys the wrong thing.

It also enforces the one invariant the whole directory exists to protect: a
vehicle file may describe adapters, apertures and looms, and may NOT describe
the deck. The moment a car file starts specifying a different DAC, the claim
that the deck is car-independent has quietly stopped being true.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "vehicles")

CONFIDENCE = {"verified", "unverified", "measure"}

REQUIRED_FIELDS = ["fits", "aperture", "depth_mm", "fascia_adapter", "harness",
                   "aerial", "swc", "illumination", "ignition"]
REQUIRED_KEYS = ["brand", "model", "generation", "years", "markets",
                 "market_notes", "gotchas"]

# Words that belong to the deck, not to a car. If one turns up in a vehicle
# file, either the deck has stopped being car-independent or somebody has put
# a note in the wrong place.
DECK_ONLY = ["esp32", "wrover", "ssd1322", "gp1294", "pcm5102", "si4735",
             "74hc4052", "inmp441", "gpio"]

_fails = []


def check(name, cond, detail=""):
    print(f"  {'ok   ' if cond else 'FAIL '} {name}   {'' if cond else detail}")
    if not cond:
        _fails.append(name)


def main():
    files = []
    for dirpath, _d, names in os.walk(SRC):
        files += [os.path.join(dirpath, n) for n in sorted(names)
                  if n.endswith(".json")]
    print(f"\n{len(files)} vehicle files")
    check("there are vehicles at all", len(files) >= 1)

    for path in files:
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as f:
            try:
                car = json.load(f)
            except json.JSONDecodeError as e:
                check(f"{rel} parses", False, str(e))
                continue

        missing = [k for k in REQUIRED_KEYS if k not in car]
        check(f"{rel} has the identity keys", not missing,
              f"missing {missing}")

        bad = []
        for key in REQUIRED_FIELDS:
            f_ = car.get(key)
            if not isinstance(f_, dict):
                bad.append(f"{key} missing — say 'not applicable' rather than "
                           "leaving it out")
            elif "v" not in f_:
                bad.append(f"{key} has no value")
            elif f_.get("c") not in CONFIDENCE:
                bad.append(f"{key} confidence is {f_.get('c')!r}, "
                           f"expected one of {sorted(CONFIDENCE)}")
        check(f"{rel} answers every question, with a confidence", not bad,
              "; ".join(bad))

        # The invariant: cars describe adapters, never the deck.
        blob = json.dumps(car).lower()
        leaked = sorted({w for w in DECK_ONLY if w in blob})
        check(f"{rel} does not specify deck parts", not leaked,
              f"mentions {leaked} — the deck is the same in every car, so this "
              "belongs in BUILD.md, not here")

        # A part number in here is a maintenance liability with a shelf life.
        for key in ("fascia_adapter", "harness", "aerial"):
            v = car.get(key, {}).get("v", "")
            check(f"{rel} {key} gives a search, not a part number",
                  "search:" in v or "not applicable" in v.lower(),
                  f"{v!r} — say what to search for; retailer part numbers go "
                  "stale and a stale one looks authoritative")

    print("\nthe generated page is up to date")
    tmp = os.path.join(tempfile.mkdtemp(prefix="deck-veh-"), "VEHICLES.md")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "vehicles", "build.py"),
                        tmp], capture_output=True, text=True)
    check("the generator runs", r.returncode == 0,
          (r.stderr or r.stdout)[-400:])
    live = os.path.join(ROOT, "docs", "VEHICLES.md")
    if r.returncode == 0 and os.path.exists(live):
        check("docs/VEHICLES.md matches the data",
              open(tmp, encoding="utf-8").read() ==
              open(live, encoding="utf-8").read(),
              "run: python3 tools/vehicles/build.py")
    elif r.returncode == 0:
        check("docs/VEHICLES.md exists", False,
              "run: python3 tools/vehicles/build.py")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails[:4])}"
              f"{' …' if len(_fails) > 4 else ''}\n")
        return 1
    print("vehicle checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
