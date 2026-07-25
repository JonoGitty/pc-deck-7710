#!/usr/bin/env python3
"""Build the project site: one shell, many pages, one linear build guide.

    python3 tools/site/build.py [outdir]

WHY THIS EXISTS

The site used to be a single hand-written `docs/index.html` — one 800-line
scroll holding the hero, the screens, the movies, the whole build, the donor
tree and the diagnostics. Every one of those sections was fine; the *shape*
was wrong. Somebody standing at a bench with a screwdriver had to scroll past
album art and dolphins to find step 6, and there was no way to know how much
was left.

So the content is now pages, and the build is a **sequence**: each chapter has
a next and a previous, the eleven mechanical steps are a page each, and every
page says where you are in the whole. Flicking, not scrolling.

HOW IT WORKS

- `content/*.html` are body fragments — no `<html>`, no nav, no footer.
- `PAGES` gives each one a slug, a title and a place. `guide=True` puts a page
  in the linear sequence, in list order.
- The eleven assembly steps are NOT written here. They are generated from the
  same `STEPS` table `tools/diagrams/steps.py` draws from, so a step's title,
  its parts list and its caption cannot drift between the drawing and the page
  standing next to it.
- Everything is emitted; nothing under `docs/` is hand-edited. That is the
  same rule the pictures follow, for the same reason: a page nobody
  regenerates is a page that quietly stops being true.

The stylesheet is a real file rather than inlined into every page — it is a
same-origin request, so it works over Pages and off a disk alike, and it means
a colour changes in one place instead of in fifteen.
"""
import html
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "diagrams"))

from steps import STEPS                                        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CONTENT = os.path.join(HERE, "content")

GH = "https://github.com/JonoGitty/pc-deck-7710"
BLOB = GH + "/blob/master"

# ---------------------------------------------------------------- the pages
# (slug, title, nav label or None, one-line description, guide?)
#
# Guide order is build order. It is also the order somebody spends money in,
# which is why "plan" and "car" come before "parts": the two questions that
# change what you buy are answered before anything is bought.
PAGES = [
    ("index", "DECK·7710 — build your own 1-DIN car head unit", "Home",
     "An open-source 1-DIN car head unit. One portable C renderer drives real "
     "glass, a browser preview and a PC music visualiser.", False),
    ("screens", "The screens", "Screens",
     "Ten display modes, every dot drawn by the portable C renderer.", False),
    ("calls", "Calls, and the radio", "Calls & radio",
     "Hands-free calling over HFP, and an FM/AM tuner whose audio never "
     "enters the microcontroller.", False),
    ("movies", "The animations", "Animations",
     "Baked animations for the deck, and the tools that make them from a "
     "scene, a GIF or a video.", False),
    ("run", "Try it now", "Try it",
     "Run the PC deck, or preview a panel you have not bought yet.", False),

    # ---- the guide, in order
    ("guide/plan", "Plan the build", None,
     "Decide what you are building and which display it has, because that "
     "fixes the grid everything else is laid out on.", True),
    ("guide/car", "Your car", None,
     "Whether the deck fits, what adapters it needs, and where the amplifier "
     "is going to live.", True),
    ("guide/donor", "Choose a donor", None,
     "Which scrap head unit to buy, and the one measurement that decides it.",
     True),
    ("guide/strip", "Strip it down", None,
     "The order it comes apart in, and the hazard that is not the one people "
     "expect.", True),
    ("guide/reuse", "Keep what you can", None,
     "The donor already contains the amplifier the shopping list tells you to "
     "buy.", True),
    ("guide/parts", "Buy the parts", None,
     "The shopping list, the tools, and what each tier actually costs.", True),
    ("guide/wire", "Wire the boards", None,
     "The pin map, the audio path, and the two traps that each cost an "
     "evening.", True),
    ("guide/flash", "Flash it, and first light", None,
     "Build the firmware, flash it, and read the four-stage self-test.", True),
    ("guide/transplant", "Move the screen and the buttons", None,
     "Aligning the panel to its lit area, and turning a scanned matrix into "
     "the deck's one-wire ladder.", True),
    ("guide/assemble", "Assemble it — eleven steps", None,
     "One action per step, drawn to scale. Start at step 1 and flick "
     "through.", True),
    # the eleven step pages are inserted here, generated from STEPS
    ("guide/install", "Into the car", None,
     "The cage, the harness, the aerial, and the part where consequences "
     "change.", True),
    ("guide/tune", "Pair it, tune it, load it", None,
     "Pairing, the radio region, the volume control, and choosing what it "
     "plays.", True),
    ("guide/fix", "When it does not work", None,
     "A blank panel has six causes and one symptom, so the deck reports on "
     "itself.", True),

    ("architecture", "How it holds together", "Architecture",
     "One renderer compiled twice, verified against the JavaScript it was "
     "ported from.", False),
    ("status", "Status, honestly", "Status",
     "What is finished, what is written but unproven, and what has never run "
     "on hardware.", False),
]

STEP_AT = "guide/assemble"          # step pages follow this one, in order


def step_slug(n):
    return f"guide/step-{n:02d}"


def expand(pages):
    """Insert the eleven step pages into the sequence after the assembly
    overview, so next/previous runs straight through them rather than dumping
    the reader back on an index between every step."""
    out = []
    for p in pages:
        out.append(p)
        if p[0] == STEP_AT:
            for n, (title, _cap, _parts, _draw) in enumerate(STEPS, 1):
                out.append((step_slug(n), f"Step {n} — {title}", None,
                            f"Step {n} of {len(STEPS)} of the mechanical "
                            f"assembly.", True))
    return out


ALL = expand(PAGES)
GUIDE = [p for p in ALL if p[4]]
NAV = [p for p in ALL if p[2]]


def rel(slug, target):
    """A link from one page to another, as a relative path. Relative and not
    absolute because the site is served from a project subdirectory on Pages
    and from a plain folder on a disk, and only relative paths survive both."""
    up = "../" * slug.count("/")
    return up + target


def shell(slug, title, desc, body, extra_head=""):
    up = "../" * slug.count("/")
    nav = "".join(
        f'<a class="{"on" if p[0] == slug else ""}" href="{rel(slug, p[0])}.html">'
        f'{html.escape(p[2])}</a>'
        for p in NAV)
    guide_on = " on" if slug.startswith("guide/") else ""
    nav += (f'<a class="guide{guide_on}" href="{rel(slug, "guide/plan")}.html">'
            f'Build guide</a>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="{up}media/faceplate.png">
<meta name="theme-color" content="#0a0a0c">
<link rel="stylesheet" href="{up}deck.css">
{extra_head}</head>
<body>

<nav class="topnav"><div class="wrap">
  <a class="mark" href="{up}index.html">DECK<b>·</b>7710</a>
  <div class="links">{nav}</div>
</div></nav>

{body}

<footer>
  <div class="wrap">
    <div class="links">
      <a href="{up}index.html">Home</a>
      <a href="{up}guide/plan.html">Build guide</a>
      <a href="{GH}">GitHub</a>
      <a href="{BLOB}/docs/BUILD.md">BUILD.md</a>
      <a href="{BLOB}/docs/HARDWARE.md">Hardware</a>
      <a href="{BLOB}/docs/DONORS.md">Donors</a>
      <a href="{BLOB}/docs/VEHICLES.md">Vehicles</a>
      <a href="{BLOB}/docs/REUSE.md">Reuse</a>
      <a href="{BLOB}/docs/DIAGNOSTICS.md">Diagnostics</a>
      <a href="{BLOB}/SAFETY.md">Safety</a>
    </div>
    <p><b>This is an unfinished hobby project published as source, not a
      product.</b> Nothing here has been tested in a vehicle or certified by
      anybody, and the firmware has never run on hardware. If you build one you
      are the manufacturer, and every consequence is yours — including fire,
      battery drain, airbag circuits, driver distraction, insurance and type
      approval. <a href="{BLOB}/SAFETY.md">Read SAFETY.md</a> before wiring
      anything to a car.</p>
    <p>Co-designed with GPT 5.6 (Sol) — the visual spec, the meter ballistics
      and the album-art dither idea came out of that consult.
      MIT licensed. Build one.</p>
  </div>
</footer>

</body>
</html>
"""


def chapter_rail(slug):
    """Where you are, and how much is left. The count is the whole point: a
    guide that does not say how long it is reads as endless."""
    i = [p[0] for p in GUIDE].index(slug)
    total = len(GUIDE)
    pct = round((i + 1) * 100 / total)
    dots = "".join(
        f'<a class="{"done" if j < i else "now" if j == i else ""}" '
        f'href="{rel(slug, p[0])}.html" title="{html.escape(p[1])}"></a>'
        for j, p in enumerate(GUIDE))
    return (f'<div class="rail"><div class="wrap">'
            f'<span class="of">Build guide · {i + 1} of {total}</span>'
            f'<div class="dots">{dots}</div>'
            f'<span class="pct">{pct}%</span>'
            f'</div></div>')


def prevnext(slug):
    i = [p[0] for p in GUIDE].index(slug)
    out = ['<nav class="prevnext"><div class="wrap">']
    if i:
        p = GUIDE[i - 1]
        out.append(f'<a class="prev" href="{rel(slug, p[0])}.html">'
                   f'<span>← Previous</span><b>{html.escape(p[1])}</b></a>')
    else:
        out.append('<a class="prev" href="' + rel(slug, "index") + '.html">'
                   '<span>←</span><b>Back to the front page</b></a>')
    if i + 1 < len(GUIDE):
        p = GUIDE[i + 1]
        out.append(f'<a class="next" href="{rel(slug, p[0])}.html">'
                   f'<span>Next →</span><b>{html.escape(p[1])}</b></a>')
    else:
        out.append(f'<a class="next" href="{GH}">'
                   f'<span>That is the guide →</span><b>The source</b></a>')
    out.append("</div></nav>")
    return "".join(out)


def chapter_no(slug):
    """'Chapter 4' — counting chapters, not pages, so the eleven step pages do
    not each claim to be one."""
    n = 0
    for p in GUIDE:
        if p[0].startswith("guide/step-"):
            continue
        n += 1
        if p[0] == slug:
            return f"Chapter {n}"
    return ""


def chapter_cards(slug):
    """The guide's table of contents, for the front page. Generated from the
    same list that orders the pages, so a chapter added to the sequence appears
    here without anybody remembering to add it."""
    out = ['<div class="chapters">']
    n = 0
    for p in GUIDE:
        if p[0].startswith("guide/step-"):
            continue            # the eleven live under their own chapter
        n += 1
        extra = (f" Eleven steps, a page each." if p[0] == STEP_AT else "")
        out.append(f'<a href="{rel(slug, p[0])}.html">'
                   f'<span class="n">{n:02d}</span>'
                   f'<span class="t">{html.escape(p[1])}</span>'
                   f'<span class="d">{html.escape(p[3])}{extra}</span></a>')
    out.append("</div>")
    return "".join(out)


def step_body(n, slug):
    """A step page, built from the same tuple the drawing is built from."""
    title, caption, parts, _draw = STEPS[n - 1]
    rows = "".join(f"<tr><td><b>{q}×</b></td><td>{html.escape(name)}</td></tr>"
                   for q, name in parts)
    warn = ""
    if "⚠️" in caption:
        before, _, after = caption.partition("⚠️")
        caption = before.strip()
        warn = (f'<div class="note danger"><p><b>⚠️ '
                f'{html.escape(after.strip())}</b></p></div>')
    nav = "".join(
        f'<a class="{"on" if m == n else ""}" '
        f'href="{rel(slug, step_slug(m))}.html">{m}</a>'
        for m in range(1, len(STEPS) + 1))
    return f"""<section class="step">
  <div class="wrap">
    <div class="steptabs">{nav}</div>
    <h2>Step {n} of {len(STEPS)}</h2>
    <p class="lede">{html.escape(title)}</p>
    <figure class="film"><img src="{rel(slug, 'media')}/assembly-step-{n:02d}.svg"
      alt="{html.escape(title)}, drawn isometrically to scale"></figure>
    <div class="stepcols">
      <div>
        <h3>What you are doing</h3>
        <p class="muted">{html.escape(caption)}</p>
        {warn}
      </div>
      <div>
        <h3>You need</h3>
        <table class="parts">{rows}</table>
      </div>
    </div>
  </div>
</section>"""


def build(out):
    os.makedirs(out, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "style.css"),
                    os.path.join(out, "deck.css"))
    written = ["deck.css"]

    for slug, title, _label, desc, is_guide in ALL:
        if slug.startswith("guide/step-"):
            n = int(slug.rsplit("-", 1)[1])
            body = step_body(n, slug)
        else:
            with open(os.path.join(CONTENT, slug.replace("/", "-") + ".html"),
                      encoding="utf-8") as f:
                body = f.read()
            body = body.replace("{{ROOT}}", "../" * slug.count("/"))
            body = body.replace("{{GH}}", GH).replace("{{BLOB}}", BLOB)
            body = body.replace("{{CHAPTERS}}", chapter_cards(slug))
            # Chapter numbers are computed, never typed. Inserting a chapter
            # into the sequence must not mean renumbering a dozen headings by
            # hand — that is exactly the edit somebody does nine tenths of.
            body = body.replace("{{CHAPTER}}", chapter_no(slug))
        if is_guide:
            body = chapter_rail(slug) + body + prevnext(slug)
        path = os.path.join(out, slug + ".html")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(shell(slug, title, desc, body))
        written.append(slug + ".html")
    return written


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs")
    written = build(out)
    total = sum(os.path.getsize(os.path.join(out, w)) for w in written)
    print(f"  {os.path.relpath(out, ROOT):<28} {len(written)} files, "
          f"{total / 1024:.1f} KB  ({len(GUIDE)} guide pages, "
          f"{len(STEPS)} of them steps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
