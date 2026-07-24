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
