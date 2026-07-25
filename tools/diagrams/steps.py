"""The build manual: one part per step, drawn isometrically, with a parts call-out.

    python3 tools/diagrams/steps.py [outdir]

WHAT THIS IS TRYING TO BE

A furniture or toy instruction sheet. One action per step, the parts for that
step boxed in the corner with quantities, the sub-assembly drawn as it looks
*before* the action with the new part ghosted where it is going, and no prose
you have to read to know what to do.

That format has one property the prose in BUILD.md cannot have: you can tell
at a glance whether you have done it right, because the drawing shows the
state you should be looking at. Text says "fit the standoffs"; a picture says
"four of them, in these corners, threaded end up."

EVERY DIMENSION IS IN MILLIMETRES AND REAL

The chassis is 178 mm wide because a 1-DIN aperture is 182 mm and the cage
takes 2 mm a side. The board is 100 × 70 because that is what the ESP32 plus a
DAC plus a mux fits on. If a number here is wrong the drawing is wrong in a way
you can measure, which is the point of drawing to scale rather than sketching.

⚠️ NEVER BUILT. This is an intended assembly derived from the standard and the
part datasheets. No step below has been performed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iso import Scene, fit                                     # noqa: E402
from svg import (Svg, AMBER, BLUE, CLIP, DIM, EDGE, GREEN,     # noqa: E402
                 HOT, INK, PANEL)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------- geometry
# Millimetres. Sources: ISO 7736 for the aperture, the SSD1322 module listing
# for the panel, and a typical 1990s single-DIN donor for the chassis.
CH_W, CH_D, CH_H = 178.0, 160.0, 48.0      # chassis, inside the cage
WALL = 1.0
BD_W, BD_D, BD_T = 100.0, 70.0, 1.6        # main board
STANDOFF_H = 8.0
PANEL_W, PANEL_H, PANEL_T = 90.0, 30.0, 5.0
FASCIA_W, FASCIA_H, FASCIA_T = 182.0, 53.0, 3.0
CAGE_D = 150.0

# Where things sit inside the chassis.
#
# ⚠️ y IS MEASURED FROM THE BACK OF THE DECK, not the front. In this
# projection sy grows with (x + y), so a larger y lands lower on the page —
# nearer the viewer. Putting the fascia at y = 0 draws the deck facing away,
# which is what the first version of this file did and it looked subtly and
# unaccountably wrong until you noticed the panel was at the far end.
BD_X, BD_Y = 24.0, 40.0                    # board's back-left corner
PANEL_Y = CH_D - 24.0                      # display, near the front
WINDOW_Y = CH_D - 12.0
ENCODER_Y = CH_D - 10.0
FASCIA_Y = CH_D + 2.0                      # in front of the chassis
POSTS = [(BD_X + 5, BD_Y + 5), (BD_X + BD_W - 5, BD_Y + 5),
         (BD_X + 5, BD_Y + BD_D - 5), (BD_X + BD_W - 5, BD_Y + BD_D - 5)]

# One camera for every step. Wide enough to hold the cage, the fascia in
# front of the chassis, and the drop arrows above it — so the deck sits still
# on the page from step 1 to step 11 and the only thing that changes between
# panels is the thing the step is about.
WORLD = ((-4.0, -26.0, -6.0), (182.0, 176.0, 74.0))

C_CHASSIS = "#6e6e7a"
C_BOARD = "#2f6b46"
C_PANEL = "#2b2b36"
C_FASCIA = "#4a4a58"
C_BRASS = "#a98b4a"
C_NYLON = "#8e8e99"
C_CAGE = "#5a6675"


# ------------------------------------------------------------ sub-assemblies
def draw_chassis(sc, floor_only=False):
    """The gutted donor: a floor and two sides. Drawn open-topped so that
    everything fitted into it afterwards stays visible — a closed box would
    hide every step after the first."""
    sc.box((0, 0, 0), (CH_W, CH_D, WALL), C_CHASSIS)              # floor
    if floor_only:
        return
    sc.box((0, 0, 0), (CH_W, WALL, CH_H), C_CHASSIS)              # back wall
    sc.box((0, 0, 0), (WALL, CH_D, CH_H), C_CHASSIS)              # left wall
    sc.box((CH_W - WALL, 0, 0), (WALL, CH_D, CH_H), C_CHASSIS)    # right wall


def draw_standoffs(sc):
    for (x, y) in POSTS:
        sc.post((x, y, WALL), STANDOFF_H, 2.5, C_NYLON)


def draw_board(sc):
    z = WALL + STANDOFF_H
    sc.plate((BD_X, BD_Y, z), (BD_W, BD_D, BD_T), C_BOARD)
    # the module, the DAC and the mux, so the board is recognisable as a board
    sc.box((BD_X + 8, BD_Y + 10, z + BD_T), (26, 52, 3.5), "#20202a")
    sc.box((BD_X + 44, BD_Y + 12, z + BD_T), (22, 16, 2.5), "#20202a")
    sc.box((BD_X + 44, BD_Y + 36, z + BD_T), (18, 12, 2.5), "#20202a")
    sc.box((BD_X + 72, BD_Y + 14, z + BD_T), (20, 30, 3.0), "#20202a")


def draw_panel(sc, z0=None):
    """The display module, standing upright near the front of the chassis: a
    thin slab in the x-z plane, with the lit area proud on its front face so
    which way round it goes is visible rather than stated."""
    z = z0 if z0 is not None else 12.0
    x = (CH_W - PANEL_W) / 2
    sc.box((x, PANEL_Y, z), (PANEL_W, PANEL_T, PANEL_H), C_PANEL)
    sc.box((x + 7, PANEL_Y + PANEL_T, z + 5), (76, 0.6, 19), "#000")


def draw_fascia(sc, z0=0.0, y=None, ghost=False):
    """The face, with its window aperture and knob hole cut in it.

    `y` lets a step draw it exploded forward of its home position — the
    convention that makes an exploded view read as an instruction. Without the
    aperture it is just a slab and does not look like a fascia at all, which
    matters here because it is the part the reader is holding."""
    x = (CH_W - FASCIA_W) / 2
    yy = FASCIA_Y if y is None else y
    if ghost:
        sc.ghost((x, yy, z0), (FASCIA_W, FASCIA_T, FASCIA_H), INK)
        return
    sc.box((x, yy, z0), (FASCIA_W, FASCIA_T, FASCIA_H), C_FASCIA)
    # window aperture, proud of the face so it reads as a hole
    sc.box((x + 26, yy + FASCIA_T, z0 + 14), (84, 0.6, 28), "#08080b")
    # and the knob, which protrudes FORWARD out of the face — a box along +y,
    # not one of the vertical posts, or it reads as a chimney
    sc.box((x + FASCIA_W - 38, yy + FASCIA_T, z0 + 18), (16, 11, 16),
           "#33333f")


def draw_cage(sc):
    sc.box((-2, 0, -2), (FASCIA_W, CAGE_D, 1.2), C_CAGE)
    sc.box((-2, 0, -2), (1.2, CAGE_D, FASCIA_H), C_CAGE)
    sc.box((-2 + FASCIA_W - 1.2, 0, -2), (1.2, CAGE_D, FASCIA_H), C_CAGE)


# ------------------------------------------------------------------- steps
# (title, caption, parts, draw) — parts are (qty, name) and appear boxed in
# the corner of the panel, which is the bit that makes a manual usable: you
# collect the pieces before you start the step, not during it.
def _s1(sc):
    draw_chassis(sc)
    sc.measure((0, CH_D, 0), (CH_W, CH_D, 0), "178 mm", off=26)


def _s2(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    for (x, y) in POSTS:
        sc.drop_arrow((x, y, WALL + STANDOFF_H), 26, HOT)


def _s3(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    z = WALL + STANDOFF_H
    sc.ghost((BD_X, BD_Y, z), (BD_W, BD_D, BD_T), GREEN)
    sc.drop_arrow((BD_X + BD_W / 2, BD_Y + BD_D / 2, z + BD_T), 34, GREEN,
                  "board, components up")


def _s4(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    z = WALL + STANDOFF_H + BD_T
    for (x, y) in POSTS:
        sc.post((x, y, z), 3.0, 3.0, C_BRASS)
        sc.drop_arrow((x, y, z + 3), 22, AMBER)


def _s5(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    sc.ghost(((CH_W - PANEL_W) / 2, PANEL_Y, 12.0),
             (PANEL_W, PANEL_T, PANEL_H), AMBER)
    sc.drop_arrow((CH_W / 2, PANEL_Y + 2, 12.0 + PANEL_H), 28, AMBER,
                  "glass forward")


def _s6(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    draw_panel(sc)
    # ribbon, panel back to board front
    a = sc.p((CH_W / 2, PANEL_Y - 1, 34.0))
    top = sc.p((CH_W / 2, (PANEL_Y + BD_Y + BD_D) / 2, 52.0))
    b = sc.p((BD_X + BD_W / 2, BD_Y + BD_D - 8, WALL + STANDOFF_H + BD_T + 2))
    sc.s.path(f"M {a[0]:.1f} {a[1]:.1f} Q {top[0]:.1f} {top[1]:.1f} "
              f"{b[0]:.1f} {b[1]:.1f}", stroke="#d49a45", sw=3)
    sc.s.text(top[0] + 10, top[1] - 4, "leave slack", size=8, fill="#d49a45")


def _s7(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    draw_panel(sc)
    x = (CH_W - PANEL_W) / 2
    sc.ghost((x + 4, WINDOW_Y, 8.0), (82, 1.0, 27), HOT)
    sc.drop_arrow((CH_W / 2, WINDOW_Y, 36.0), 24, HOT, "smoked side out")


def _s8(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    draw_panel(sc)
    # The shaft runs forward out of the face, so it is a box along +y rather
    # than one of the vertical posts used for standoffs.
    sc.box((CH_W - 42, ENCODER_Y - 4, 14.0), (18, 16, 18), "#33333f")
    sc.box((CH_W - 36, ENCODER_Y + 12, 20.0), (6, 12, 6), C_BRASS)
    sc.drop_arrow((CH_W - 33, ENCODER_Y + 18, 34.0), 22, AMBER, "encoder")


def _s9(sc):
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    draw_panel(sc)
    # Exploded 46 mm forward of home, with the target ghosted where it lands.
    # Drawn in its final place it merges with the chassis outline and the step
    # stops looking like an action.
    draw_fascia(sc, z0=-2.0, ghost=True)
    draw_fascia(sc, z0=-2.0, y=FASCIA_Y + 46)
    a = sc.p((CH_W / 2, FASCIA_Y + 44, 26))
    b = sc.p((CH_W / 2, FASCIA_Y + 8, 26))
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    sc.s.path(f"M {a[0]:.1f} {a[1]:.1f} L {b[0]:.1f} {b[1]:.1f}", stroke=INK,
              sw=2.2, dash="6 4")
    sc.s.path(f"M {b[0] - ux * 10 - uy * 5.5:.1f} "
              f"{b[1] - uy * 10 + ux * 5.5:.1f} L {b[0]:.1f} {b[1]:.1f} "
              f"L {b[0] - ux * 10 + uy * 5.5:.1f} "
              f"{b[1] - uy * 10 - ux * 5.5:.1f}", stroke=INK, sw=2.2)
    sc.s.text(a[0], a[1] + 20, "clips on last", size=8, fill=INK,
              anchor="middle")


def _s10(sc):
    draw_cage(sc)
    sc.measure((-2, CAGE_D, -2), (-2 + FASCIA_W, CAGE_D, -2), "182 mm",
               off=26)
    sc.s.text(*sc.p((FASCIA_W / 2, 0, FASCIA_H + 40)),
              "bend the tabs outward, from inside the dash", size=8,
              fill=BLUE, anchor="middle")


def _s11(sc):
    draw_cage(sc)
    draw_chassis(sc)
    draw_standoffs(sc)
    draw_board(sc)
    draw_panel(sc)
    draw_fascia(sc, z0=-2.0)
    # sliding in: an arrow along the deck's own axis, the direction of travel
    a = sc.p((CH_W / 2, CH_D + 74, 26))
    b = sc.p((CH_W / 2, CH_D + 22, 26))
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    sc.s.path(f"M {a[0]:.1f} {a[1]:.1f} L {b[0]:.1f} {b[1]:.1f}", stroke=CLIP,
              sw=2.6)
    sc.s.path(f"M {b[0] - ux * 11 - uy * 6:.1f} {b[1] - uy * 11 + ux * 6:.1f} "
              f"L {b[0]:.1f} {b[1]:.1f} "
              f"L {b[0] - ux * 11 + uy * 6:.1f} {b[1] - uy * 11 - ux * 6:.1f}",
              stroke=CLIP, sw=2.6)
    sc.s.text(a[0] - 6, a[1] + 16, "push until both tabs click", size=8,
              fill=CLIP, anchor="middle")


STEPS = [
    ("The chassis, empty",
     "Gut the donor first — §7.1. Keep the covers, the fascia and every "
     "screw. What you want is a box with a floor, two sides and a back.",
     [(1, "donor chassis"), (1, "hour, realistically")], _s1),

    ("Four nylon standoffs",
     "M3 × 8 mm, nylon not brass — brass shorts to a chassis that is also "
     "your ground. Threaded end up. Mark and drill the floor from the board, "
     "not from a measurement.",
     [(4, "M3 × 8 nylon standoff"), (4, "M3 nylon screw"), (1, "3 mm drill")],
     _s2),

    ("The main board, components up",
     "Lower it flat onto all four posts at once. If it only meets three, the "
     "fourth hole is out and forcing it cracks the board.",
     [(1, "main board, populated")], _s3),

    ("Four nuts, finger tight plus a quarter",
     "Nyloc. A car vibrates for a living and plain nuts back off. Finger "
     "tight and a quarter turn — a PCB is not a structural member.",
     [(4, "M3 nyloc nut")], _s4),

    ("The panel, glass forward",
     "It sets the position of everything the user can see, so it goes in "
     "before anything is bonded. Dry-fit it against the fascia aperture and "
     "check the lit area is centred before committing.",
     [(1, "SSD1322 or GP1294AI module"), (2, "M2 screw")], _s5),

    ("The ribbon, with a service loop",
     "Leave enough slack to lift the panel clear of the chassis without "
     "unplugging it. You will do that more than once, and a taut ribbon "
     "tears at the connector rather than in the middle.",
     [(1, "FFC / DuPont loom")], _s6),

    ("The window, smoked side out",
     "1 mm smoked acrylic, bonded behind the fascia aperture. Smoked and not "
     "clear: an unlit dot has to look dead rather than grey, and that "
     "difference is the whole character of the panel.",
     [(1, "smoked acrylic, 82 × 27"), (1, "clear bonding tape")], _s7),

    ("The encoder, through the fascia",
     "Nut on the outside, star washer inside. Fit it before the fascia goes "
     "on so you can reach the nut.",
     [(1, "rotary encoder"), (1, "M7 nut + washer"), (1, "knob")], _s8),

    ("The fascia",
     "Last on, first off. Nothing behind it should ever need it removed. "
     "Check every button reaches before you clip it home.",
     [(1, "fascia"), (3, "button cap")], _s9),

    ("The cage, in the car",
     "This goes in and stays in. Bend the tabs outward from inside the dash, "
     "and only the tabs that reach metal — the rest bend back and rattle.",
     [(1, "ISO 7736 cage"), (1, "flat screwdriver")], _s10),

    ("Slide it home",
     "Connect ISO A and ISO B first, then push until both spring tabs click. "
     "⚠️ Meter A4 and A7 before this: the connector is standard, the pinout "
     "is not, and they are commonly swapped.",
     [(1, "ISO 10487 A + B"), (1, "rear support strap")], _s11),
]


# ------------------------------------------------------------------ layout
PW, PH = 566, 396               # one step panel
COLS = 2
MARGIN = 28
GAP = 16


def panel(s, col, row, n, title, caption, parts, draw):
    px = MARGIN + col * (PW + GAP)
    py = 96 + row * (PH + GAP)

    s.rect(px, py, PW, PH, fill="#0c0c10", stroke=EDGE, rx=6)

    # step number, in a circle, because that is where the eye goes first
    s.circle(px + 30, py + 30, 17, fill=AMBER)
    s.text(px + 30, py + 35, str(n), size=16, fill="#17110a", anchor="middle",
           weight="700")
    s.text(px + 58, py + 28, title, size=11.5, fill=INK, weight="700")

    # parts call-out
    bx, by = px + PW - 186, py + 46
    bh = 20 + len(parts) * 16
    s.rect(bx, by, 172, bh, fill="#141419", stroke=EDGE, rx=4)
    s.text(bx + 10, by + 15, "YOU NEED", size=7.5, fill=AMBER,
           spacing="0.16em")
    for i, (q, name) in enumerate(parts):
        s.text(bx + 10, by + 31 + i * 16, f"{q}×", size=9, fill=HOT,
               weight="700")
        s.text(bx + 30, by + 31 + i * 16, name, size=9, fill=DIM)

    # The drawing, framed by the shared camera below the parts call-out and
    # above the caption.
    scale, ox, oy = fit(WORLD, (px + 14, py + 104, PW - 28, PH - 176))
    draw(Scene(s, scale, ox, oy))

    # caption, wrapped by hand — no text engine, and a manual caption is
    # three lines or it is not a manual
    words, line, lines = caption.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > 74:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    lines.append(line)
    for i, ln in enumerate(lines[:4]):
        s.caption(px + 18, py + PH - 58 + i * 14, ln, size=9.5)


def sheet(out, index, items, first):
    rows = (len(items) + COLS - 1) // COLS
    W = MARGIN * 2 + COLS * PW + (COLS - 1) * GAP
    H = 96 + rows * (PH + GAP) + 52
    s = Svg(W, H, f"ASSEMBLY  ·  SHEET {index}",
            f"Steps {first}–{first + len(items) - 1} of {len(STEPS)}. "
            "Every dimension is in millimetres and to scale.")
    for i, (title, cap, parts, draw) in enumerate(items):
        panel(s, i % COLS, i // COLS, first + i, title, cap, parts, draw)
    s.caption(MARGIN, H - 24,
              "⚠️  Never built. An intended assembly drawn from ISO 7736 and "
              "the part datasheets — not a photograph of a working deck.",
              fill=CLIP)
    return s.save(os.path.join(out, f"assembly-sheet{index}.svg"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs",
                                                             "media")
    os.makedirs(out, exist_ok=True)
    per = 4
    paths = []
    for k in range(0, len(STEPS), per):
        idx = k // per + 1
        paths.append(sheet(out, idx, STEPS[k:k + per], k + 1))
    for p in paths:
        print(f"  {os.path.relpath(p, ROOT):<34} "
              f"{os.path.getsize(p) / 1024:6.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
