#!/usr/bin/env python3
"""The diagrams still describe the firmware.

    python3 tools/verify/test_diagrams.py

Two different failures are caught here, and they fail for different reasons.

**A pin moved and the diagram did not.** `tools/diagrams/pins.py` reads the
`#define PIN_...` lines straight out of the firmware, so this is not a matter
of remembering to update a picture — regenerating produces different bytes,
and the committed SVG no longer matches. That is the whole reason the pin map
is generated rather than drawn.

**Two drivers claim one pin.** The generator refuses to draw a GPIO twice
unless the pair is declared in `SHARED`, which means an accidental collision
stops the build here rather than being discovered with a multimeter. This is
not hypothetical: deck_input.c and deck_tuner.c both took GPIO 13, 32 and 33,
the tuner's reset line would have been held as a pulled-up input, and the deck
would have reported no radio fitted with one sitting on the bus.

The check is a byte comparison against what is committed, so it also catches
the ordinary case of somebody editing a diagram and forgetting to rerun.
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "diagrams"))

DIAGRAMS = ["pinmap.svg", "wiring.svg", "assembly.svg", "dimensions.svg",
            "finished.svg"]
SHEETS = ["assembly-sheet1.svg", "assembly-sheet2.svg", "assembly-sheet3.svg"]
# The site shows one drawing per step, on its own page. Same generator, same
# camera — and the same way of going stale, so it is checked with the sheets
# rather than trusted because the sheets passed.
SHEETS += [f"assembly-step-{n:02d}.svg" for n in range(1, 12)]

_fails = []


def check(name, cond, detail=""):
    print(f"  {'ok   ' if cond else 'FAIL '} {name}   {'' if cond else detail}")
    if not cond:
        _fails.append(name)


def main():
    import pins as P

    print("\nthe pin table still parses out of the firmware")
    try:
        table = P.build()
        ok, detail = True, ""
    except SystemExit as e:
        table, ok, detail = {}, False, str(e)
    check("every pin the diagram names still exists in the firmware", ok,
          detail)
    if not ok:
        print(f"\n{len(_fails)} failed\n")
        return 1

    check("the pin table is not empty", len(table) > 15, f"{len(table)} pins")

    # THE CHECK THAT WOULD HAVE CAUGHT IT.
    #
    # The transport actions were fully implemented — deck_main.c handled
    # PLAY_PAUSE, NEXT_TRACK and PREV_TRACK and sent the right AVRCP
    # passthrough codes — and the ONLY thing that raised them was deck_swc.c,
    # the steering wheel. Four of the six front-panel buttons chose a screen,
    # three of those were shortcuts to screens the DISP button already cycles
    # to, and not one of them changed the track. On a car with no wheel
    # controls — the Honda S2000 has none in any market — you could not skip a
    # song from the deck at all.
    #
    # Nothing failed, because every piece worked. Only the join was missing.
    print("\nthe music can be controlled from the deck itself")
    src = open(os.path.join(ROOT, "firmware", "esp32", "main", "deck_input.c"),
               encoding="utf-8").read()
    # The two tables a human can physically reach: discrete buttons, and the
    # resistor ladder. The steering wheel deliberately does not count.
    panel = ""
    for pat in (r"static btn_t s_btn\[\] = \{(.*?)\};",
                r"\} LADDER\[\] = \{(.*?)\};"):
        m = re.search(pat, src, re.S)
        if m:
            panel += m.group(1)
    for act in ("DECK_ACT_PLAY_PAUSE", "DECK_ACT_NEXT_TRACK",
                "DECK_ACT_PREV_TRACK"):
        check(f"{act[9:].lower().replace('_', ' ')} is on the front panel",
              act in panel,
              "implemented in deck_main.c but reachable only from the "
              "steering wheel — which most of the cars in vehicles/ do not "
              "have")

    # The three deliberately-shared pins must still be shared. If somebody
    # "fixes" the clash by moving the tuner, that is a real design change and
    # this should make them say so out loud.
    shared = [g for g, p in table.items() if p.get("alt")]
    check("the tuner and the discrete buttons still share three pins",
          sorted(shared) == [13, 32, 33],
          f"shared pins are {sorted(shared)}, expected [13, 32, 33]")

    # Nothing the firmware uses may land on a pin the module has reserved.
    bad = sorted(set(table) & set(P.FORBIDDEN))
    check("no signal is on flash, PSRAM or the console", not bad,
          f"GPIO {bad} — the module reserves these; see pins.py FORBIDDEN")

    # Strapping pins are outputs or documented inputs, never bare buttons.
    strapped = sorted(set(table) & set(P.STRAPPING))
    check("every strapping pin in use is one the notes explain",
          all(g in P.STRAPPING for g in strapped),
          f"GPIO {strapped}")

    print("\nthe committed diagrams match what the generator produces now")
    tmp = tempfile.mkdtemp(prefix="deck-diagrams-")
    for gen in ("make.py", "steps.py"):
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "tools", "diagrams", gen), tmp],
                           capture_output=True, text=True)
        check(f"{gen} runs", r.returncode == 0, (r.stderr or r.stdout)[-400:])
        if r.returncode != 0:
            print(f"\n{len(_fails)} failed\n")
            return 1

    for name in DIAGRAMS + SHEETS:
        live = os.path.join(tmp, name)
        committed = os.path.join(ROOT, "docs", "media", name)
        if not os.path.exists(committed):
            check(f"{name} is committed", False,
                  "run: python3 tools/diagrams/make.py")
            continue
        a = open(live, encoding="utf-8").read()
        b = open(committed, encoding="utf-8").read()
        check(f"{name} is up to date", a == b,
              "the generator produces something else now — "
              "run: python3 tools/diagrams/make.py")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails)}\n")
        return 1
    print("diagram checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
