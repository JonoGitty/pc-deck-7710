#!/usr/bin/env python3
"""Turn donors/*.json into docs/DONORS.md.

    python3 tools/donors/build.py [outfile]

Same arrangement as the vehicle tree and for the same reason: the buying
advice, the grades and the per-family teardown steps live in data, and the page
is generated, so adding a donor family is a file rather than an edit to four
places that will drift apart.

The grade is the load-bearing field. Somebody standing in front of a table of
scrap head units at a car boot sale has thirty seconds and no calipers, and the
question they need answered is "is this one worth two pounds". Everything else
on the page is for after they have got it home.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "donors")

MARK = {"verified": "✅", "unverified": "⚠️", "measure": "📏"}

FIELDS = [
    ("price", "What to pay"),
    ("window_w_mm", "Window width"),
    ("window_h_mm", "Window height"),
    ("chassis", "Chassis"),
    ("cage_included", "Cage"),
    ("buttons", "Buttons"),
    ("knob", "Knob"),
    ("display_tech", "Its own display"),
]

GRADE_NOTE = {
    "A": "Buy this if you see one.",
    "B": "Good, with one thing to think about first.",
    "C": "Usable. You will be cutting the fascia.",
    "D": "Only if it is free and you like the chassis.",
}


def load():
    out = []
    for dirpath, _d, files in os.walk(SRC):
        for fn in sorted(files):
            if fn.endswith(".json"):
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                d["_slug"] = os.path.splitext(fn)[0]
                d["_path"] = os.path.relpath(p, ROOT)
                out.append(d)
    out.sort(key=lambda d: (d["grade"], d["_slug"]))
    return out


def mark(f):
    v = f["v"]
    if isinstance(v, (int, float)):
        v = f"{v:g} mm" if v else "—"
    return f"{MARK[f['c']]} {v}"


def anchor(d):
    return d["_slug"]


def render(donors):
    o = []
    w = o.append
    w("# Donor units\n")
    w("**Generated** from `donors/*.json` by `tools/donors/build.py`. Do not "
      "edit this file — edit the donor and rerun.\n")
    w("Where the chassis, the fascia, the cage, the buttons and the knob come "
      "from, for less than the cage alone costs new.\n")

    w("---\n")
    w("## Buy a broken one. That is the whole trick.\n")
    w("**You are buying a box, a face and a bag of buttons.** The CD "
      "mechanism, the amplifier, the tuner and the microcontroller all go in "
      "the bin on the first evening, so a unit that does not work is worth "
      "exactly as much to you as one that does — and costs a fraction.\n")
    w("Search *spares or repair*, *faulty*, *no CD*, *display dead*, "
      "*untested*. A working head unit is £30–60; the same model with a "
      "jammed mechanism is £8–15, because to everybody else it is scrap and "
      "to you it is a chassis.\n")
    w("| Pay more for | Do not pay for |")
    w("|---|---|")
    w("| **The cage and trim ring** — a new ISO 7736 cage is £8–15, so a £15 "
      "unit with one beats a £8 unit without | **A working CD mechanism** — "
      "the biggest single driver of price on a listing, and the first thing "
      "you remove |")
    w("| **An undamaged fascia** — the part you cannot replace, the part "
      "everybody sees, and the part sellers most often lose | **A working "
      "display** — you are fitting your own |")
    w("")

    w("> **Already got one?** [TRANSPLANT.md](TRANSPLANT.md) covers the "
      "fiddly half — aligning the panel to its lit area rather than to its "
      "PCB, and turning the donor's scanned button matrix into the deck's "
      "one-wire ladder.\n")
    w("## The window is the only thing that really decides it\n")
    w("The deck's lit area is about **76 × 19 mm** (SSD1322) or **76 × 14 "
      "mm** (GP1294AI). Everything else about a donor is recoverable — the "
      "chassis can be shimmed, the buttons rewired, the knob swapped. The "
      "window cannot: it is a hole in the one part you chose the donor for, "
      "and enlarging it is the difference between a deck that looks bought "
      "and one that looks made in a shed.\n")
    w("Which is why the best donors are the ones with a **big amber "
      "dot-matrix display**, roughly 1998–2008. Their window is already a "
      "wide letterbox of about the right size, in about the right place, in "
      "the right colour.\n")

    w("## ⚠️ Three hazards, and one is genuinely dangerous\n")
    w("| | |")
    w("|---|---|")
    w("| **The CD laser** | Class 1 *with the lid shut* and not with it off. "
      "Do not power the original board up to see if it still works. |")
    w("| **The amplifier's electrolytics** | Store energy. Discharge them and "
      "bin the board. |")
    w("| **A VFD unit's inverter** ⚠️ | The real one. A head unit with a "
      "vacuum-fluorescent display makes its own filament and anode supplies — "
      "**tens of volts, from a small inverter, held on a capacitor after "
      "power-off**. Treat any VFD donor's power board as live until proved "
      "otherwise. |")
    w("")
    w("That last one is why the safest donors to gut are the ones with an "
      "LCD, even though the ones with a VFD are prettier.\n")

    # ---- the table somebody reads at a car boot sale
    w("---\n")
    w("## At a glance\n")
    w("| Grade | Family | Era | ~Price | Window | Verdict |")
    w("|---|---|---|---|---|---|")
    for d in donors:
        ww = d["window_w_mm"]["v"]
        hh = d["window_h_mm"]["v"]
        win = f"{ww:g} × {hh:g} mm" if ww and hh else "none / you cut it"
        w(f"| **{d['grade']}** | [{d['family']}](#{anchor(d)}) | {d['era']} "
          f"| {d['price']['v'].split(';')[0]} | {win} | {d['one_liner']} |")
    w("")

    for d in donors:
        w("---\n")
        w(f"## {d['family']}\n")
        w(f"<a id=\"{anchor(d)}\"></a>")
        w(f"**Grade {d['grade']}** — {GRADE_NOTE.get(d['grade'], '')} "
          f"· {d['era']}\n")
        w(f"<sub>`{d['_path']}`</sub>\n")
        if d.get("examples"):
            w("*For example: " + ", ".join(d["examples"]) + ".*\n")

        w(f"![Window fit for {d['family']}](media/donor-{d['_slug']}.svg)\n")

        w("| | | |")
        w("|---|---|---|")
        for key, label in FIELDS:
            f = d[key]
            w(f"| **{label}** | {mark(f)} | {f.get('why') or ''} |")
        w("")

        if d.get("models"):
            w("### Specific units to search for\n")
            w("| | Model | Years | Its own display | Notes |")
            w("|---|---|---|---|---|")
            for m in d["models"]:
                icon = {"good": "✅", "caution": "⚠️", "avoid": "❌"}[m["flag"]]
                w(f"| {icon} | **{m['name']}** | {m['years']} "
                  f"| {m['display']} | {m['note']} |")
            w("")
            w("<sub>✅ buy it · ⚠️ workable, read the note · ❌ avoid for this "
              "build. Model names are ⚠️ researched, not handled — and no "
              "window here has been measured.</sub>\n")

        if d.get("teardown"):
            w("### Stripping it down\n")
            w(f"![Strip-down order for {d['family']}]"
              f"(media/teardown-{d['_slug']}.svg)\n")
            w("| | Part | | What happens to it |")
            w("|---|---|---|---|")
            ic = {"keep": "🟩 **KEEP**", "bin": "🟥 BIN",
                  "hazard": "🟧 **HAZARD**"}
            for i, t in enumerate(d["teardown"], 1):
                w(f"| {i} | **{t['part']}** | {ic[t['action']]} "
                  f"| {t['note'] or ''} |")
            w("")

        for key, label in (("why", "Why this one"),
                           ("watch_out", "⚠️ Watch out for"),
                           ("steps", "How to gut it")):
            items = d.get(key)
            if not items:
                continue
            w(f"**{label}**\n")
            if key == "steps":
                for i, it in enumerate(items, 1):
                    w(f"{i}. {it}")
            else:
                for it in items:
                    w(f"- {it}")
            w("")

    w("---\n")
    w("## Adding a donor\n")
    w("Copy the nearest file in `donors/`, measure yours, run "
      "`python3 tools/donors/build.py` and "
      "`python3 tools/diagrams/donors.py`. Every dimension carries a "
      "confidence marker and `tools/verify/test_donors.py` fails on a claim "
      "without one.\n")
    w("**Measure the window with calipers, not from a photograph.** It is the "
      "one number that decides whether the build looks bought or looks made, "
      "and the drawing above is to scale — so a wrong number is wrong "
      "visibly.\n")
    return "\n".join(o) + "\n"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "DONORS.md")
    donors = load()
    if not donors:
        sys.exit("no donors found under " + SRC)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(donors))
    print(f"  {os.path.relpath(out, ROOT):<28} {len(donors)} donor families, "
          f"{os.path.getsize(out) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
