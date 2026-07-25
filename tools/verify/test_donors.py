#!/usr/bin/env python3
"""Every donor file is complete, and the drawings match the numbers.

    python3 tools/verify/test_donors.py

A schema check, like its sibling for vehicles. It cannot tell you whether a
Pioneer DEH-P really has an 86 mm window — only calipers can. What it can do is
stop the failures that make a buying guide worse than nothing:

**A dimension with no confidence marker**, which reads as measured fact when it
is a guess, and sends somebody to a car boot sale with a number in their head.

**A grade with no justification.** Every family has to say why it earns its
grade and what to watch out for, because "grade A" on its own is an opinion
with no argument attached.

**A drawing that has stopped matching its data.** The window-fit SVGs are drawn
to scale from these numbers, so a changed measurement that does not reach the
picture leaves a drawing that is confidently wrong — and a to-scale drawing is
believed precisely because it looks measured.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "donors")

CONFIDENCE = {"verified", "unverified", "measure"}
GRADES = {"A", "B", "C", "D"}

FIELDS = ["price", "window_w_mm", "window_h_mm", "chassis", "cage_included",
          "buttons", "knob", "display_tech"]
KEYS = ["family", "category", "era", "grade", "one_liner", "why", "watch_out",
        "steps"]

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
    print(f"\n{len(files)} donor families")
    check("there are donors at all", len(files) >= 1)

    for path in files:
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as f:
            try:
                d = json.load(f)
            except json.JSONDecodeError as e:
                check(f"{rel} parses", False, str(e))
                continue

        missing = [k for k in KEYS if not d.get(k)]
        check(f"{rel} has every section", not missing, f"missing {missing}")

        check(f"{rel} grade is one of {sorted(GRADES)}",
              d.get("grade") in GRADES, f"grade is {d.get('grade')!r}")

        bad = []
        for key in FIELDS:
            f_ = d.get(key)
            if not isinstance(f_, dict):
                bad.append(f"{key} missing")
            elif "v" not in f_:
                bad.append(f"{key} has no value")
            elif f_.get("c") not in CONFIDENCE:
                bad.append(f"{key} confidence is {f_.get('c')!r}")
        check(f"{rel} answers every question, with a confidence", not bad,
              "; ".join(bad))

        # A grade is an opinion. It has to come with the argument.
        check(f"{rel} justifies its grade",
              len(d.get("why") or []) >= 2 and len(d.get("watch_out") or []) >= 1,
              "every family needs at least two reasons and one warning — "
              "a grade with no argument is just an assertion")

        # Window dimensions are numbers, because the drawing scales them.
        for key in ("window_w_mm", "window_h_mm"):
            v = d.get(key, {}).get("v")
            check(f"{rel} {key} is a number",
                  isinstance(v, (int, float)),
                  f"{v!r} — the window-fit drawing scales this, so it cannot "
                  "be prose. Use 0 for 'no usable window'")

    print("\nthe generated page and the drawings are up to date")
    tmp = tempfile.mkdtemp(prefix="deck-donor-")
    md = os.path.join(tmp, "DONORS.md")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "donors", "build.py"), md],
                       capture_output=True, text=True)
    check("the page generator runs", r.returncode == 0,
          (r.stderr or r.stdout)[-400:])
    live = os.path.join(ROOT, "docs", "DONORS.md")
    if r.returncode == 0 and os.path.exists(live):
        check("docs/DONORS.md matches the data",
              open(md, encoding="utf-8").read() ==
              open(live, encoding="utf-8").read(),
              "run: python3 tools/donors/build.py")

    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "diagrams", "donors.py"),
                        tmp], capture_output=True, text=True)
    check("the drawing generator runs", r.returncode == 0,
          (r.stderr or r.stdout)[-400:])
    if r.returncode == 0:
        for path in files:
            slug = os.path.splitext(os.path.basename(path))[0]
            name = f"donor-{slug}.svg"
            a = os.path.join(tmp, name)
            b = os.path.join(ROOT, "docs", "media", name)
            if not os.path.exists(b):
                check(f"{name} is committed", False,
                      "run: python3 tools/diagrams/donors.py")
                continue
            check(f"{name} matches the measurements",
                  open(a, encoding="utf-8").read() ==
                  open(b, encoding="utf-8").read(),
                  "the drawing is to scale, so a stale one is confidently "
                  "wrong — run: python3 tools/diagrams/donors.py")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails[:4])}"
              f"{' …' if len(_fails) > 4 else ''}\n")
        return 1
    print("donor checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
