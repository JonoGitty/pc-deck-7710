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

### `--trim`, because not every shot in a clip belongs here

`--keep` fixes the tones. It cannot fix the framing, and the commonest framing
problem in found footage is a shot that pulls back.

```sh
python3 tools/movies/import_gif.py ae86.gif --cover --keep=30 --trim=0:62
```

`--trim=A:B` keeps source frames A up to B and discards the rest. The delays
the GIF gave the surviving frames are preserved, so a trimmed import plays at
the same speed as an untrimmed one — it is a cut, not a time-stretch.

The reason it earns a flag: on a panel with four levels and a 4:1 aspect, a
subject that shrinks does not merely get smaller, it *inverts*. In a wide shot
the car occupies a dozen dots and the road it is driving on occupies half the
frame — so the brightest, largest, most attention-grabbing object on the panel
becomes the tarmac, and the thing the clip is about disappears. The same
footage cut before the camera pulls back is excellent.

Look at the source before assuming all of it belongs on a head unit. A four
second clip that reads is worth more than a ten second one that stops reading
halfway.

## Or import a video

Anything ffmpeg can open — a phone clip, a screen recording, an MP4:

```sh
python3 tools/movies/import_video.py clip.mov --probe          # where to crop
python3 tools/movies/import_video.py clip.mov --crop=0.43,0.41,0.32,0.13 \
        --from=4 --dur=8 --keep=25
```

Same tonal problems as a GIF and more of them, because video is always
photographic. Everything above about `--keep` applies, harder. Three
differences worth knowing:

- **`--cover` is the default here**, not letterbox. A portrait phone video
  letterboxed onto a 4:1 panel occupies about a ninth of it.
- **`--from` and `--dur` cut a section**, and an import caps at 30 seconds
  unless told otherwise. A minute at 10 fps is 600 frames of flash.
- **`--probe` suggests a crop** by finding the part of the frame that *moves*,
  which is a better detector for "the screen in this shot" than brightness —
  brightness selects the lit wall behind it. It is a suggestion; look at the
  ASCII it prints before believing it.

### Filming a display is the case that does not work

The obvious thing to point this at is another head unit, and it is the one
source that resists every flag here. It fails three times over:

1. **Moiré.** The source's dot grid beats against the deck's. `--blur=3`
   before the downscale removes the source's dots and keeps its picture, and
   the difference is not subtle.
2. **Inversion.** A VFD lights its background and leaves the subject dark —
   the opposite of how this deck draws. `--invert` fixes that.
3. **The tone that is left lands in the middle**, and the middle is the 50/50
   checkerboard. A whole panel of it beats anything in front of it.

The first two have flags. The third does not, because there is nothing to
recover: a hand-held camera photographing a lit panel produces an image whose
dominant tone *is* mid-grey, and no black point puts it anywhere good. This was
tried on real footage of a real head unit, at every setting in this document,
and came out as noise every time.

**So film a display for reference, not for import.** If you want what it shows,
draw it — which is what `core/screens/ocean.c` is.

## Or re-stage the clip instead of playing it

`import_gif.py` plays a clip as it is. That is right when the clip already is
the animation you want. It is wrong when you want **more of what is in it, for
longer, looping** — and a played-back bitmap can give you none of the three.
Five seconds stretched to thirty is the same five seconds six times; a bitmap
has as many ducks as it was filmed with; and a clip loops where it happens to
end.

```sh
python3 tools/movies/restage.py ducks.gif --name=DUCKS
python3 tools/movies/restage.py ducks.gif --name=DUCKS --legacy
python3 tools/movies/restage.py ducks.gif --tiles=4 --band=0.06,0.88 \
        --layers=8 --water=1 --secs=30
```

**This keeps the footage.** Every duck on the panel is the source's own pixels
moving the way the source moved them; what gets rebuilt is the staging around
them. `DUCKS` is 71 frames of four or five ducks turned into thirty seconds of
about twenty-five.

**The frame is widened by mirror-tiling.** A square clip letterboxed onto a 4:1
panel occupies a third of the glass. So the canvas is several tiles wide and
the background is mirrored between them — a mirrored edge matches its neighbour
*exactly*, so the seams are continuous by construction rather than nearly.

**The clip is composited over itself.** Each layer carries only its moving parts
and has its own position, scale, speed and starting phase. Layers are what turn
four ducks into twenty-five, and every one of them is real photographed motion.

**The moving parts are found by median.** Anything that moves is not at the same
pixel in most frames, so a per-pixel median of the clip is the scene with the
subjects removed. Nothing to key, and it does not care whether the subject is
lighter or darker than what it is over.

### The two things that were wrong first

**`--band`, because a square clip and a 4:1 panel cannot both be satisfied.**
Fit the full 200-pixel height into 64 dots and a duck filmed 55 pixels tall
arrives 17 dots tall — a blob. Cropping to the horizontal band the action
happens in puts a duck at twenty dots, where it reads as a duck. The cost is
vertical travel: subjects enter and leave the band instead of crossing the whole
frame. On a strip four times wider than it is tall, that is the right trade.

**The phase column, because periods that all divide 300 also all agree.** The
first version gave every layer a period dividing the movie and no phase offset,
which is a correct loop and a bad movie: at frame 150 the layers at 60, 75, 100,
150 and 300 sit at phases 0.5, 0.0, 0.5, 0.0 and 0.5 — *two* distinct phases
between fourteen layers. Every layer showed one of two clip frames, and since a
clip like this is a burst rather than a steady stream, those two frames were
mostly empty water. A constant phase offset per layer fixes it for nothing:
adding a constant to a periodic function leaves it exactly as periodic, so the
loop guarantee is untouched.

```
loop check: frame 300 matches frame 0 on 100.00% of dots
```

### `--water`, and the level-centre rule again

The background gets pinned to **one flat level** rather than being dithered.
This is the same rule as everywhere else in this document: the clip's water is
teal — mid-luminance — so shaded across four levels it lands on a boundary and
renders as a 50/50 checkerboard the size of the panel, which beats every duck in
it for attention. Pinned to level 1 it is a calm lit field with the ducks bright
on top, which is what the clip looks like. `--water=0` for black instead.

**What it cannot do:** it is only as good as the separation. A subject the same
colour as its background does not come out, and a clip shot handheld has no
stable median to subtract — this wants a locked-off camera, which is what most
short loops of this kind are.

## The bundled animations

Five procedural scenes, and they are worth reading before writing your own —
each one solves a different version of the same problem, which is that four
levels is not many. (Two more, `REEF` and `AE86`, are imports rather than
scenes; there is no source to read, only the flags above. `DUCKS` is a third
thing again — a clip re-staged rather than played, by `restage.py`.)

| | What it is | The thing it works out |
|---|---|---|
| `scene_spin.py` | A rotating solid, 8 s | The minimal template. Start here. |
| `scene_solar.py` | Sun to Pluto, 56 s | A camera path, and labels that survive a bright background — see `deckfont.plate`. |
| `scene_dolphins.py` | A pod breaching, 24 s | A bright subject needs something dim to sit against; the sea is shaded on a steep curve so only crests glint. |
| `scene_touge.py` | A car sideways at night, 30 s | The inverse: an almost-black frame, lit only by the car's own headlights, where the subject is the *hole* in the light. |
| `scene_vtec.py` | A bar tachometer, 26 s | Instrumentation rather than a scene: a bar tacho *is* a 4:1 strip, and the revs are a crude engine with a limiter rather than a waveform. |

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
