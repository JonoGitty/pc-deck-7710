# Making animations for the deck

The deck plays two kinds of animation. Both end up as levels on a dot grid, so
the difference is only where the levels come from.

| | **Procedural** | **Baked** |
|---|---|---|
| What it is | Code that draws a frame | Pre-rendered frames in a `.dmv` |
| Reacts to music | **Yes** — reads the analysis state | No |
| Costs | Code, and a rebuild to change | Flash, roughly 500–800 bytes/frame |
| Written in | C, in `core/screens/` | Anything that can emit frames |
| Example | The dolphins | `tools/movies/scene_spin.py` |

The dolphins are procedural, which is why bass makes the pod breach. That is
worth understanding before you start: if your animation should respond to the
music, it has to be code. If it just needs to look good, bake it.

## Designing for this display

The constraints are unusual enough that habits from normal screens actively
mislead.

**There is no colour.** Five intensity levels — off, dim, main, hot, clip — and
the panel decides what those become. Two objects at the same luminance are the
same object, however different you imagined them. Design in brightness.

**It is a letterbox.** 4:1 or wider. A composition that works on a monitor
becomes a subject stranded in the middle with two-thirds of the panel empty.
Think frieze, not portrait: things move across, or there are several of them.

**Levels are scarce and thin things lose them.** A one-dot line cannot be dim on
a 1-bit panel — it either lights or it doesn't. Fills can carry shading; edges,
lettering and single dots cannot. See [UI-SPEC.md](UI-SPEC.md).

**It's 10 fps.** Fast motion strobes. Big, slow, deliberate movement reads; a
quick pan turns into a smear of unrelated frames.

**Verify with pixels, not eyes.** `to_ascii()` dumps a frame as text. If you
cannot tell what it is at that size, neither can the panel — and looking at a
1000% zoom of a render will lie to you about both.

## The shortcut: import a GIF

If you already have an animation, skip the renderer entirely:

```sh
python3 tools/movies/import_gif.py cat.gif --legacy     # onto the PC deck
python3 tools/movies/import_gif.py cat.gif 256 64       # for an SSD1322
```

It folds colour to luminance, dithers to the four levels, composites
transparency onto black, and resamples the GIF's per-frame delays onto one
fixed rate. `--cover` crops to fill the panel instead of letterboxing.

The thing to watch for is colour: a GIF that reads by hue — a red shape on
green, say — becomes one flat blob here. The importer measures how saturated
the source is and says so, but it cannot tell you which shapes were *meant* to
be distinct, so check the ASCII dump it prints.

### `--keep`, and why footage needs it

A straight import of photographic footage almost always comes out as mush, and
the reason is not resolution. A camera uses the whole tonal range; the deck has
four levels. A mid-grey background does not become "background" — it becomes a
50% dither, and that checkerboard is visually louder than the subject in front
of it. Everything is lit, so nothing reads.

```sh
python3 tools/movies/import_gif.py reef.gif 256 64 --cover --keep=22
```

`--keep=P` lights the brightest P% of the picture and crushes the rest to off,
so the four levels all land on the subject and the background is simply black —
which is what a head unit looks like anyway. Start at 20 and adjust: too low
and parts of the subject drop out, too high and the background creeps back in.

The black point is measured once across the whole movie, not per frame. Frames
are auto-stretched individually by default, which is right for a rendered scene
(it always contains its own black and white) and wrong for footage, where a
frame the subject has left re-normalises the background up to full brightness
and the panel flashes.

`--gamma=` shapes the curve between the two points if the midtones need pushing
either way.

## The bundled animations

Four, and they are worth reading before writing your own — each one solves a
different version of the same problem, which is that four levels is not many.

| | What it is | The thing it works out |
|---|---|---|
| `scene_spin.py` | A rotating solid, 8 s | The minimal template. Start here. |
| `scene_solar.py` | Sun to Pluto, 56 s | A camera path, and labels that survive a bright background — see `deckfont.plate`. |
| `scene_dolphins.py` | A pod breaching, 24 s | A bright subject needs something dim to sit against; the sea is shaded on a steep curve so only crests glint. |
| `scene_touge.py` | A car sideways at night, 30 s | The inverse: an almost-black frame, lit only by the car's own headlights, where the subject is the *hole* in the light. |

Each takes a grid — `scene_touge.py 256 64` — or `--legacy` for the PC deck.

`scene_touge.py` is also where the level-centre trick is written down. The
quantiser puts level *n* at shade (n + 0.5) / 4, so 0.375, 0.625 and 0.875 are
solid fields and 0.25 or 0.5 — which look like the reasonable round numbers —
are exactly the 50/50 checkerboards. Anything covering a large area wants to be
pinned to a centre, or it becomes the loudest thing on the panel.

## The renderer

`tools/movies/render3d.py` — pure Python, no numpy, no GPU, no Blender, so it
runs anywhere including a bare container.

- `Cam(eye, target, w, h, f)` — perspective projection
- `FB` — z-buffered barycentric triangle rasteriser with distance fog
- `icosphere()`, `lathe()`, `box()` — meshes are generated, not modelled
- `draw_mesh()` — flat shading, backface culling
- `render_frame(w, h, draw, ss=3)` — supersample and box-downsample

Then `tools/movies/dmv.py` quantises luminance to the five levels using the same
ordered dither as the album art, and delta-compresses to a `.dmv`.

Start by copying `scene_spin.py`. It is deliberately small.

## Traps

These have all been hit for real. They are cheap to avoid and expensive to
diagnose.

**Handedness.** The camera basis is right-handed. Get it wrong and the entire
world is silently x-mirrored — and *nothing looks wrong* until you render text,
which comes out backwards. If a scene feels subtly off, put a letter in it.
Text is the canary.

**Motion trails drawn at past positions.** With a chase camera, "behind" is
closer to the lens, so a trail rendered at the subject's previous positions
appears *in front of it* and swallows it. Trails must go in the direction of
travel, not the history of it.

**Float endpoints in a stepping loop.** A line stepper walking from a float
start to a float end can step *past* its termination condition and never
terminate. Round endpoints to integers before stepping. A render that appears
to hang is usually this.

**Clamp before writing bytes.** Specular and additive light push channels past
255, and `bytearray` raises rather than wrapping. Clamp at the write.

**Supersample or lose the shape.** At this dot pitch an aliased silhouette does
not read as a rougher version of the shape — it reads as a *different* shape.
`ss=3` is the default for that reason. Drop to `ss=1` for quick iteration, never
for the final render.

**Test one frame before rendering two hundred.** Render frame 30 alone, look at
the ASCII, fix the composition. A full pass at supersample is slow enough that
designing blind through it wastes a lot of time.

## Contributing an animation

1. Copy `scene_spin.py`, change the scene.
2. Render for the grid you have: `python3 tools/movies/scene_spin.py 256 64`.
3. Check the ASCII dump reads as the thing you meant.
4. Preview it on a real panel geometry: `sh tools/serve.sh`.
5. For the PC deck as well: `--legacy` writes a copy the legacy faceplate plays.

If you would rather not think about any of the above, ask Claude — see
[../CLAUDE.md](../CLAUDE.md). Describe the animation you want and which display
you have, and it will pick the grid, the composition and the level budget for
you.
