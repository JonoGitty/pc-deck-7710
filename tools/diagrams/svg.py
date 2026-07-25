"""Just enough SVG to draw a wiring diagram, with no dependencies.

Deliberately not a library. A diagram generator that needs pip install is a
diagram generator nobody reruns, and a picture nobody reruns goes stale — which
is the failure this whole directory exists to prevent.

SVG rather than PNG for three reasons that all matter here:

  * it is text, so a change to a pin shows up as a diff you can read rather
    than as a binary blob you have to open;
  * it scales, and somebody is going to want this on paper next to the bench;
  * the fonts are the reader's, so a pin label is legible at any zoom.

Everything is absolute coordinates in a fixed viewBox. There is no layout
engine and there should not be one: these diagrams are drawn once and then
corrected, and a layout engine turns "move that label 4px left" into an
afternoon.
"""

# The deck's own palette — amber on near-black, the same values docs/index.html
# uses. A diagram of this thing should look like this thing.
BG      = "#08080a"
PANEL   = "#101014"
EDGE    = "#23232b"
INK     = "#d8d4cc"
DIM     = "#8a8578"
AMBER   = "#f3a52b"
HOT     = "#ffd978"
CLIP    = "#ff4938"
GREEN   = "#7fcf8f"     # only for "this is safe/verified", never for signal
BLUE    = "#7fb4e8"     # cold side: car inputs, things that are not audio

MONO = ("ui-monospace, 'SF Mono', 'Cascadia Mono', Menlo, Consolas, "
        "'DejaVu Sans Mono', monospace")
SANS = ("system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, "
        "sans-serif")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


class Svg:
    def __init__(self, w, h, title, subtitle="", chrome=True):
        """`chrome=False` keeps the <title> for screen readers but draws no
        visible heading. For a drawing embedded in a page that already has a
        heading, a caption and a parts table in real HTML — the site's
        single-step pages — the burnt-in version is the same words twice and
        half the drawing area."""
        self.w, self.h = w, h
        self.parts = []
        self.title = title
        self.subtitle = subtitle
        self.chrome = chrome

    # --- primitives ------------------------------------------------------
    def rect(self, x, y, w, h, fill="none", stroke=None, sw=1, rx=0,
             dash=None, op=None):
        a = f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"'
        if rx:
            a += f' rx="{rx}"'
        a += f' fill="{fill}"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        if dash:
            a += f' stroke-dasharray="{dash}"'
        if op is not None:
            a += f' opacity="{op}"'
        self.parts.append(f"<rect {a}/>")

    def line(self, x1, y1, x2, y2, stroke=EDGE, sw=1, dash=None, cap="round"):
        a = (f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
             f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"')
        if dash:
            a += f' stroke-dasharray="{dash}"'
        self.parts.append(f"<line {a}/>")

    def path(self, d, stroke=EDGE, sw=1, fill="none", dash=None):
        a = (f'd="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
             f'stroke-linecap="round" stroke-linejoin="round"')
        if dash:
            a += f' stroke-dasharray="{dash}"'
        self.parts.append(f"<path {a}/>")

    def circle(self, cx, cy, r, fill=AMBER, stroke=None, sw=1):
        a = f'cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        self.parts.append(f"<circle {a}/>")

    def text(self, x, y, s, size=11, fill=INK, anchor="start", mono=True,
             weight="normal", spacing=None, op=None):
        a = (f'x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
             f'text-anchor="{anchor}" font-family="{MONO if mono else SANS}"')
        if weight != "normal":
            a += f' font-weight="{weight}"'
        if spacing:
            a += f' letter-spacing="{spacing}"'
        if op is not None:
            a += f' opacity="{op}"'
        self.parts.append(f"<text {a}>{esc(s)}</text>")

    # --- composites ------------------------------------------------------
    def box(self, x, y, w, h, label, sub=None, accent=AMBER, fill=PANEL):
        """A labelled component. The accent is the left edge, not the whole
        border — a diagram where every box is outlined in colour has no
        hierarchy left to spend."""
        self.rect(x, y, w, h, fill=fill, stroke=EDGE, sw=1, rx=4)
        self.rect(x, y, 3, h, fill=accent, rx=1.5)
        self.text(x + 12, y + (17 if sub else h / 2 + 4), label,
                  size=11.5, fill=INK, weight="600")
        if sub:
            for i, ln in enumerate(sub if isinstance(sub, list) else [sub]):
                self.text(x + 12, y + 32 + i * 13, ln, size=9.5, fill=DIM)

    def pill(self, x, y, s, fill=AMBER, ink="#17110a", size=9, pad=6):
        w = len(str(s)) * size * 0.62 + pad * 2
        self.rect(x, y - size + 1, w, size + 6, fill=fill, rx=(size + 6) / 2)
        self.text(x + w / 2, y + 4, s, size=size, fill=ink, anchor="middle",
                  weight="600")
        return w

    def caption(self, x, y, s, size=9.5, fill=DIM, anchor="start"):
        self.text(x, y, s, size=size, fill=fill, anchor=anchor, mono=False)

    # --- output ----------------------------------------------------------
    def render(self):
        head = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} '
            f'{self.h}" width="{self.w}" height="{self.h}" '
            f'role="img" aria-label="{esc(self.title)}">',
            f"<title>{esc(self.title)}</title>",
            f'<rect width="{self.w}" height="{self.h}" fill="{BG}"/>',
        ]
        t = []
        if self.chrome:
            t.append(
                f'<text x="28" y="38" font-size="15" fill="{HOT}" '
                f'font-family="{MONO}" font-weight="700" letter-spacing="0.14em">'
                f"{esc(self.title)}</text>")
        if self.subtitle and self.chrome:
            t.append(f'<text x="28" y="58" font-size="11" fill="{DIM}" '
                     f'font-family="{SANS}">{esc(self.subtitle)}</text>')
        return "\n".join(head + t + self.parts + ["</svg>"]) + "\n"

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.render())
        return path
