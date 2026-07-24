# BUILDLOG — how the GETTING COOKD renderer got made

A log of how a hand-rolled software 3D renderer ended up in a party-game repo. Everything below
happened in one build push (2026-07-06), commit by commit, on top of the SVG cutscene work from the
days before. It's written down because half the value is the mistakes — see `tools/README.md` for
the distilled findings; this is the story they came from.

## 0. The provocation

The cutscene existed first as an animated SVG (`assets/svg/anim/getting-cookd.svg`, `d2227fd`) —
the bowling-alley gag storyboarded in flat vector: LAST PLACE in the spotlight, flaming ball,
strike, loser launched, upside-down landing, COOKD verdict. Then the question that started the
whole ladder: could it be rendered **frame by frame at the real LED resolution** — the 192×92 grid
from `src/core/led.js` — instead of pretending with SVG? And then: "that was shit, I hoped you
could do 3D."

Fair. So: 3D, from scratch, in pure Python, because the container has no Blender, no GPU, no numpy
— just `math`, `json`, `random`, and time.

## 1. Flat edition (`render_cutscene.py`, `6a3d113`–`f0aa96c`)

A 2.5D painter: hand-animated sprites composited back-to-front straight onto the 192×92 grid, plus
the two output paths every later rung reuses —

- the **frames JSON** (delta-compressed runs against an 18-colour palette, the same format
  `parseFramesJSON` already plays for `assets/lore_frames.json`), and
- the **mp4 preview**: raw frames upscaled nearest-neighbour, multiplied by a round-bulb mask in
  ffmpeg so every pixel reads as an LED.

First casualty: the mp4 came out **black and white**. ffmpeg's `blend` filter converts mismatched
inputs to a common pixel format, and against a gray PGM mask the common format is grayscale.
`format=gbrp` on *both* streams fixed it (`f0aa96c`). Second discovery: the Playwright-bundled
ffmpeg is a stripped VP8-only build with no libx264 and no `blend` at all — `pip install
imageio-ffmpeg` provides a real static binary.

## 2. PS1 edition (`render_ps1.py`, `069da0a`)

The actual renderer is born, and it's small:

- `FB.tri` — a z-buffered triangle rasterizer: bounding box, barycentric inside-test, depth
  interpolation. ~60 lines, still the heart of every later rung.
- `Cam` — eye/target/focal-length perspective projection, ~15 lines.
- Meshes are generated, not modelled: icosphere subdivision for the ball, a lathed profile for the
  pins, capsules for limbs.
- Era flavour, deliberately: flat shading, **vertex snapping** to half-pixels, Bayer dithering,
  distance fog, low poly counts.

The one that hurt: a render hung at frame 60 for 25 minutes. `faulthandler.dump_traceback_later`
(left in every renderer since, as a tripwire) pointed at the Bresenham line loop — float endpoints
from camera-shake offsets let the stepper walk *past* its end condition forever. `int(round())`
on endpoints before stepping. Never again.

## 3. PS2 edition (`render_ps2.py`, `2e93c78`, fixed in `9a17fe6` + `4f45bf0`)

The big jump: per-vertex normals with gouraud + Blinn specular, subdiv-2 ball, an articulated
capsule ragdoll that flails mid-air, planar floor reflections (mirror the geometry under the lane,
draw the varnish translucently over it), motion-blur ghosts, debris, smoke, additive glow, an
in-scene 3D scoreboard, letterbox, FOV punch on impact.

It shipped broken twice, instructively:

- **The maroon dome.** Ghosts were drawn at the ball's *past* positions — which, with a chase
  camera, sit closer to the lens than the ball itself, so the "trail" rendered as a giant dome
  swallowing the subject. Ghosts must trail in the travel direction (`9a17fe6`).
- **The mirrored world.** Everything looked fine until the scoreboard text rendered backwards.
  The camera basis was left-handed (`right = cross(fwd, up)`), silently x-mirroring the entire
  world; only text could betray it. Rebuilt right-handed (`right = cross((0,1,0), fwd)`), with the
  backface-cull sign flipped to match (`4f45bf0`). Text is the canary for handedness bugs.

Also here: specular pushed colour channels past 255 and `bytearray` raised `ValueError` — clamp
before writing, always.

## 4. PS3 edition (`render_ps3.py`, `11da68b`)

Techniques, not just tuning: dynamic planar shadows (every mesh projected along the key light onto
the lane), per-vertex fresnel rim, velocity-stretched spark streaks, a slow cinematic push-in, and
internal resolution up to 576×276 with a 3×3 box downsample to the true grid (this is where the
jaggies died).

The lesson of the rung: the new **HDR bloom** post-pass turned the lime COOKD verdict *yellow*.
Diagnosed not by eye but by sampling actual output pixels — `(255,255,30)`: a luminance-keyed
bloom had saturated the red channel. Fix: bloom **per channel**, and store the board's emissive
colours pre-compensated so they land in the right palette buckets *after* the post pipeline.
Verify by rebuilding a frame from the frames JSON and counting which palette indices the board
region actually uses. "Looks right" is not a measurement.

## 5. PS4 edition (`render_ps4.py`, `19baafc`)

Built the same day the pipeline was ported into `tools/` (`0bb9c81`) so none of this could die
with the scratchpad again. New per rung:

- the flaming ball becomes a real **point light** — per-vertex additive rgb, interpolated by the
  rasterizer, playing across pins, loser and lane as it rolls;
- **SSAO** from the z-buffer (half-res, range-checked) and two-pass penumbra shadows;
- **rack-focus depth of field** — focus tracks the ball, snaps to the wreck, pulls to the verdict
  board;
- a volumetric spotlight cone with drifting dust motes over LAST PLACE;
- filmic tonemap + teal/orange grade + vignette as per-channel 256-LUTs applied with
  `bytearray.translate` (C speed), chromatic aberration on the impact flash;
- sub-pixel projection — the PS1 vertex snap finally retired — subdiv-3 ball, boarded lane with
  range arrows.

Board colours re-pre-compensated for bloom *plus* tonemap, and re-verified from the JSON. New
workflow trick worth keeping: while the full 200-frame render ran, a parallel **21-frame test
render** proved out the intro (cone, motes, DoF) instead of designing blind for ten minutes.

And one last ffmpeg trap for the collection: `-stream_loop -1` on the single-image bulb mask gives
it broken timestamps, and `blend`'s framesync buffers forever — 99% CPU, 48-byte file, no end.
Loop the mask with an explicit `-framerate` and a finite count (frames − 1).

## The shape of the thing

Each rung is a fork of the last, self-contained and runnable on its own — the ladder *is* the
documentation. PS1 is the whole system at its simplest (~350 lines); PS4 is the same skeleton with
six more passes (~700 lines). Nothing here is a platform decision: textures, a physics solver,
more light types are all just the next pass someone writes. The hard constraint was never the
renderer — it's the display: 192×92, 18 colours, 16 fps. Design bold shapes; verify with pixels,
not eyes.
