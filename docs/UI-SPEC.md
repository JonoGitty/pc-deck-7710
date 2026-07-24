# UI specification

The current deck is hard-coded to a 192×48 grid. To support several displays,
every layout becomes a function of the geometry. This spec defines how.

## Grid is a choice, not a panel property

On a low-res panel the dot grid *is* the panel: 256×64 pixels, 256×64 dots.

On a high-res panel (an 1920×480 bar LCD) the grid is a **logical choice** and
the renderer upscales by an integer factor — that's what preserves the OEM
dot-matrix look instead of producing smooth modern graphics. 1920×480 at 10×
gives exactly the current 192×48 grid, with each dot rendered as a 10×10 sprite
with room for its bloom halo.

So a display target is `(grid_w, grid_h, levels, scale, pixel_shape)`.

## Layout tiers

Chosen from grid height, since height is what constrains rows of text.

| Tier | Grid height | Example targets | Character of the layout |
|---|---|---|---|
| **S — strip** | < 40 | 512×32, 384×32 | One text row. Annunciators share it. Visualiser inline, half height |
| **M — classic** | 40–79 | **192×48**, 256×48, 256×64 | Today's layout: annunciator row, title, secondary line, visualiser strip |
| **L — large** | ≥ 80 | 384×96, custom | Double-height title, three text rows, taller visualiser |

Reference implementation is tier M at 192×48 — everything else derives from it.

## Metrics

All positions derive from these, never from literals:

| Symbol | Meaning | 192×48 | 256×64 |
|---|---|---|---|
| `W`,`H` | grid | 192, 48 | 256, 64 |
| `CH5` | 5×7 glyph pitch, scale 1 | 6 px | 6 px |
| `CH3` | 3×5 glyph pitch | 4 px | 4 px |
| `COLS5` | text columns at scale 1 | 32 | 42 |
| `ANN_H` | annunciator row height | 5 | 5 |
| `VIZ_TOP` | visualiser top, compact | 32 | 44 |
| `BIG_TOP` | visualiser top, tall modes | 24 | 32 |

Rule: **`VIZ_TOP = H − 16`, `BIG_TOP = H/2`.** Both hold for the current grid,
so tier M scales without reflowing.

## Intensity model

Unchanged and canonical across every target — `0` off, `1` dim, `2` main,
`3` hot, `4` clip. The output stage maps these to the device (see
[ARCHITECTURE.md](ARCHITECTURE.md)). Screens must never assume more than five
levels, and must stay legible when the output stage collapses them to 1-bit —
which means **never encode meaning in intensity alone** where it matters.

### Thin features cannot be dithered

Dithering trades resolution for levels. That works on filled areas and fails on
anything one or two dots wide: a 3x5 glyph, a scale mark, a needle, a peak-hold
dot, a graticule line. Below five device levels they come out as noise, or
vanish entirely when a lone dot lands on the wrong Bayer cell.

`deck_thin_inten(geom, want)` is the rule: on panels that resolve the full
scale it returns `want` unchanged; below that it returns solid. **Every thin
draw call must go through it.** Areas must not — they have the dots to carry a
pattern, and that is where the intensity information survives.

This was found by looking at the preview on a 1-bit target, not by reasoning:
the VU scale arc had almost entirely disappeared and the labels were mush.

The consequence is that brightness stops distinguishing thin features on 1-bit
panels. Screens must therefore not encode meaning in intensity alone:

- **Lyrics** distinguishes the current line from its neighbours by intensity
  only. On 1-bit, add a leading marker (`▶`) or invert the current row.
- **Spectrum peak-hold** dots are intensity 3 against intensity 2 bars. On
  1-bit, leave a one-dot gap under the peak marker instead.
- **3D spectrum** shades ranks by depth. On 1-bit every rank is solid, so
  depth has to come from the existing inset and hidden-line removal alone.

## Screens

Ten today. Each gets an adaptation rule per tier.

| # | Screen | S | M | L |
|---|---|---|---|---|
| 1 | Spectrum analyzer | 13 bars, half height | as today | taller bars, finer segments |
| 2 | Mirror spectrum | drop to 9 bands | as today | as M, wider pitch |
| 3 | VU meter | single needle | twin needles | twin, larger arc |
| 4 | Oscilloscope | one trace | trace + 2 persistence | + graticule |
| 5 | Cityscape EQ | as today, clipped | as today | taller towers |
| 6 | Waterfall | 6 rows | 12 rows | 24 rows |
| 7 | 3D spectrum | 6 ranks | 12 ranks | 20 ranks |
| 8 | Ocean cruise | horizon only | as today | as M, 2× dolphins |
| 9 | **Album art** | art only, no text | art `H×H` left, text right | art + full metadata block |
| 10 | **Lyrics** | 2 rows | 4 rows | 5–6 rows, double-height current line |

### Album art — layout rule

Art is a square of side `H`, left-aligned at `x = 2`. Text column starts at
`x = H + 10`, giving `(W − H − 12) / CH5` characters. At 192×48 that's 21
characters; at 256×64, 30. Rows: source and time at `y=2`, title at `y≈H/4`,
artist below, album below that, mini analyser on the bottom `6` rows.

### Lyrics — layout rule

`ROWS = floor((H − 8) / 11)` text rows, 11 px pitch, top margin 1. Status row
(sync trim, `NO SYNC`) at `H − 6`, progress bar on the last row. Wrap width is
`COLS5 − 2`. Current line highlighted across all of its wrapped rows.

## Annunciator row

Tier M and L keep the current row: source, play/pause lamp, RPT, RDM, ST, DEMO,
LOUD, OVER. Tier S drops to source + play lamp + OVER only. Positions become
fractions of `W` rather than the current literals.

## Fonts

- `FONT3` 3×5 — annunciators. Unchanged.
- `FONT5` 5×7 — everything else, scalable 1× and 2×. Unchanged.
- **New for tier L:** an 8×12 for double-height titles, so large panels don't
  just show chunky 2× 5×7.

Text is folded to the ROM's character set (accents stripped, curly quotes
squared) — already implemented, moves into `core/`.

## Preview app UI

The browser harness is a development tool, not a product, but it is how anyone
chooses their build. It needs:

- **Display picker** — grid size (presets per real part, plus custom),
  intensity levels, pixel shape (square / round bulb), colour scheme, physical
  scale, bezel on/off.
- **Side-by-side** — same frame rendered at two targets at once, for checking a
  layout survives a tier change.
- **Data source** — live from a running deck server, or a canned track with
  fake audio so the preview works with nothing else running.
- **Screen picker** — jump to any of the ten, plus the state machine's
  interstitials (NOW PLAYING, clock, screensaver, no signal).
- **Export** — PNG of the current frame, for the build guides' diagrams.

## Open questions

- Tier S is specified but no target part has been chosen for it. It may be
  premature — the 512×32 Noritake is RFQ-only.
- Colour schemes are meaningless on 1-bit and greyscale targets. The picker
  should hide them rather than offer eight identical options.
