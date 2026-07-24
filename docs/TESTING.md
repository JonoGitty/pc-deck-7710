# Testing

Two halves, and they answer different questions.

**On your computer** you can run the renderer, the deck's own UI logic, the
movie decoder and the flash container, and assert on all of them. That covers
most of the code and all of the code that is easy to get subtly wrong.

**On the bench** you find out whether any of it survives contact with a panel,
a phone and a car. Nothing on this page pretends the first replaces the second.

| Layer | Command | Proves | Runs in CI |
|---|---|---|---|
| The renderer | `sh tools/verify/run.sh` | `core/` renders identically to the JavaScript it was ported from — fonts, screens, text, metadata, the ocean, every `.dmv` | ✅ |
| The container | (same script) | A packed movie blob unpacks to the bytes that went in, read by an independent reader | ✅ |
| The deck's behaviour | `sh tools/sim/run.sh` + `test_behaviour.py` | The firmware's own UI layer: which screen is on, when the dolphins take over, how a track change interrupts | ✅ |
| The firmware compiles | `idf.py build`, both panels | It builds for SSD1322 *and* GP1294AI, and fits the app slot | ✅ |
| The hardware | This page, §3 | Everything that only fails on hardware | ❌ — it cannot |

---

## 1. The renderer, and the one rule

```sh
sh tools/verify/run.sh
```

This is the rule the whole project rests on: `core/` is verified against the
JavaScript it was ported from. Both implementations render the same input and
the framebuffers are diffed. It is not a lint job — it is a differential test
of two independent implementations, and it is the only reason it is safe to
trust the browser preview about what the hardware will do.

What it checks, in order:

| Stage | Cases | What a failure means |
|---|---|---|
| `trigtest` | fixed-point sin/cos vs libm | The no-libm trig tables drifted |
| fonts and primitives | `cases.tsv` | A glyph or a drawing primitive changed |
| every screen | `screens.tsv` | A screen's output changed |
| text helpers | `text.tsv` | Scrolling, folding or ellipsis changed |
| cover / lyrics | `meta.tsv` | The metadata screens changed |
| the ocean | `ocean.tsv` | Dolphin timing or waterfall thresholds moved |
| every `.dmv` in `movies/` | all frames | The movie decoders disagree |
| the flash container | `build/movies.bin` | Packing and unpacking are not inverses |
| the deck's behaviour | 20 assertions | See §2 |

Two of those deserve a note.

**The movie check decodes each file twice** — once from a buffer, once through
the streaming source that never holds the whole file — and fails if they
disagree. The streaming path is the one the firmware uses, reading forwards
from flash into a 320-byte stack buffer, and it is the path nobody would
otherwise exercise.

**The ocean check needs Chromium** because its JavaScript reference draws
dolphin silhouettes on a canvas. It skips itself when Playwright is absent and
says so, so the rest of the suite still runs on a bare machine.

If you change a screen's output *deliberately*, this will fail. **Update the
expectation; never delete the case.** It has caught things invisible by eye: a
dolphin breach starting one frame early, waterfall thresholds landing
differently at double precision, text dithering into mush on 1-bit panels.

---

## 2. The deck, on your computer

```sh
sh tools/sim/run.sh                              # 20 s of deck, as ASCII
sh tools/sim/run.sh --gif /tmp/deck.gif          # ...as an animation
sh tools/sim/run.sh --script tools/sim/scripts/tour.txt
sh tools/sim/run.sh --movie movies/vtec_256x64.dmv --secs 26
sh tools/sim/run.sh --grid 192 48 --levels 2     # a 1-bit VFD instead
```

No ESP32, no panel, no phone. It compiles in about a second.

### What is real and what is stubbed

The browser preview already renders `core/`. What it does *not* run is the
layer above: which screen is on, when the deck gives up and shows the clock,
how a track change interrupts, what a movie does at its last frame. That layer
is firmware, it is the part most likely to be wrong, and until the simulator
existed the only way to exercise it was to flash a board nobody has.

So the line is drawn as low as it will go:

| Real — the file the ESP32 compiles | Stubbed |
|---|---|
| `firmware/esp32/main/deck_ui.c` | the panel driver (frames go to a PPM stream) |
| all of `core/` — screens, fonts, text, output stage, dither | the SPI bus, DMA, timers |
| `core/movie.c`, decoding real `.dmv` files off disk | the Bluetooth stack (audio and metadata are synthesised) |
| the intensity model and level mapping for any panel | NVS, Wi-Fi, OTA |

`deck_ui.c` here is `deck_ui.c` there. Every level is put through the same
`deck_out_frame()` the firmware calls, so the ASCII dump and the GIF show the
dither the glass will show — including on `--levels 2`, which is how you check
a screen on a 1-bit VFD without owning one.

### Driving it with a script

A test is a file rather than a recompile:

```
# tools/sim/scripts/idle.txt
4.0   silence                       stop the music; the idle machine takes over
20.0  audio                         start it again
24.0  track "Nightcall" "Kavinsky"  a track change
28.0  key art                       press a button
```

Commands: `key <mode|art|lyrics|ocean|movie|demo|src|up|down>`, `track "T" "A"`,
`silence`, `audio`.

### The assertions

```sh
python3 tools/sim/test_behaviour.py
```

Twenty checks, each named after something a person would notice:

```
idle machine — silence at 4s
  ok    plays live while there is audio
  ok    clock after ~3s of silence
  ok    dolphins after ~12s of silence
  ok    back to live when the music returns
  ok    a wipe runs when the music returns
track change
  ok    NOW PLAYING interstitial on a track change
  ok    and it ends
metadata screens hold through a pause
  ok    album art selected
  ok    lyrics selected
every screen draws something
  ok    mode 0..10 lights dots
movie playback
  ok    a loaded movie animates
all behaviour checks passed
```

They work off a state trace — `--trace` prints one line per frame,
`T <t> <mode> <state> <lit> <wipe>` — rather than off pixels, because a test
that asserts on exact pixels is a test that fails every time a font changes.
Pixels are `run.sh`'s job (§1); this is about behaviour over time.

Two of these are worth their existence on their own. **"Dolphins after ~12s of
silence"** takes fifteen seconds of standing in silence to check on hardware,
per attempt. **"Every screen lights dots"** catches the failure where a screen
renders nothing at all, which is invisible until you happen to press that
button in a car park.

This suite has already caught a real bug in its own harness — the script
parser accepted a partial match and silently ate the argument off every
unquoted line, so `key art` pressed nothing. Nothing else in the project would
have found it.

### What it cannot tell you

This is a simulation of **the deck's logic**, not of the hardware. It does not
model:

- SPI timing, or a panel init sequence that is subtly wrong
- what the display does when the supply sags on engine crank
- the Bluetooth stack: pairing, reconnects, AVRCP quirks per phone, the
  codec actually negotiated
- DMA, PSRAM bandwidth, or the frame rate you really get
- heat, in a dashboard, in summer
- the resistance ladder in your steering wheel

Every one of those fails on hardware and only on hardware. A simulator that
claimed otherwise would be worse than none, because it would be believed.

---

## 3. The firmware, on a bench

Do this on a desk with a bench supply or a USB cable, **before** the deck goes
anywhere near a dashboard. Every step below fails for one reason, which is the
entire point of the order.

### 3.0 — before you power anything

```sh
python3 tools/deckctl.py doctor
```

Checks the toolchain, finds the serial port, and reads the chip ID — which
catches the single most expensive mistake available here: an **ESP32-S3 cannot
do this build at all.** No Bluetooth Classic means no A2DP means no audio from
a phone. It must be the original ESP32, WROVER-E for the PSRAM.

Then, with the panel wired and *before* flashing:

- [ ] 3V3 measures 3.25–3.35 V at the panel connector, not just at the regulator
- [ ] the panel's own supply (+12 V or +16 V, depending on glass) is present
- [ ] CS, DC, RST and SCLK are not swapped — check against `docs/BUILD.md`, twice
- [ ] nothing is warm

### 3.1 — the four-stage self-test

```sh
python3 tools/deckctl.py build
python3 tools/deckctl.py flash
```

Every boot runs a self-test in an order where each stage can only fail for a
reason the previous ones have ruled out. **A blank panel at stage 1 is a
hardware problem; a blank panel after stage 1 is a software problem.** That
single distinction is why it exists.

| Stage | On screen | Record | If it fails |
|---|---|---|---|
| 1 | Grey ramp, one-dot grid, border | ramp shows distinct steps? grid is one dot, not two? border reaches all four edges? | Wiring, supply, SPI clock or init. Straight from the driver — no `core/` involved |
| 2 | Five vertical bands | are all five distinguishable on *your* glass? | Level mapping or dither — software, in code stage 1 bypassed |
| 3 | "DECK 7710", version, alphabet | is the text the right way round? | Font, geometry, or a mirrored axis |
| 4 | Subsystem table | note every `unknown` / `degraded` / `failed` | Read what it says |

The stage-1 pattern is chosen, not decorative. The one-dot grid catches the
classic SSD1322 first-day fault, where nibble packing doubles or halves the
width and everything still looks plausible. The border catches an addressing
window that covers a convincing subset of the panel.

Full detail: [DIAGNOSTICS.md](DIAGNOSTICS.md).

### 3.2 — the serial line

```sh
python3 tools/deckctl.py logs
```

Everything worth machine-reading comes out as
`DECK|<uptime_ms>|<subsystem>|<event>|<key=value ...>`. Only *transitions* are
logged, and health is four-state — `unknown` is **not** a failure, it means
that subsystem has had no reason to run yet. Conflating the two is how people
spend an evening debugging Bluetooth on a deck nobody has paired.

If the deck has crashed and rebooted, the backtrace is in flash:

```sh
python3 tools/deckctl.py coredump
```

### 3.3 — audio

- [ ] the deck appears in the phone's Bluetooth list as `DECK 7710`
- [ ] it pairs, and `DECK|...|bt|connect` appears in the log
- [ ] audio plays, and the spectrum on the panel moves with it
- [ ] title and artist appear — some phones send metadata late, or not until
      the track changes; change track before concluding it is broken
- [ ] play/pause and skip from the deck's buttons reach the phone
- [ ] power-cycle: it reconnects on its own, without touching the phone

The reconnect test is the one people skip and the one that matters in a car,
because you will never once pair it while driving.

### 3.4 — steering wheel controls

Hold **SRC** for five seconds. The panel walks you through each function and
records the voltage your wheel's ladder produces.

- [ ] each button you press is accepted, showing a millivolt value
- [ ] buttons you do not have time out and skip — that is not a failure; plenty
      of wheels have four buttons, not seven
- [ ] a button that clashes with one already learned is rejected, and says so
- [ ] `SAVED` at the end
- [ ] power-cycle, and they still work

Learning rather than decoding is deliberate: the aftermarket standardised the
*radio* side — resistance to ground on a 3.5 mm jack — but the values differ
per model and per adapter. Learning makes any universal interface work,
including on an S2000.

### 3.5 — content

```sh
python3 tools/deckctl.py movies      # choose animations, write them to flash
python3 tools/deckctl.py pictures    # your own photos
```

- [ ] every installed movie plays, and loops without a visible cut
- [ ] the last one wraps back to the first
- [ ] a photo you added looks like the thing it is a photo of

### 3.6 — soak

Leave it running for an hour with music playing.

- [ ] no reboots in the log
- [ ] free heap at the end is within a few kilobytes of free heap at the start
- [ ] nothing is too hot to keep a finger on

A slow heap leak is invisible in a five-minute test and will drop the deck on
the motorway.

---

## 4. In the car

Before the fascia goes back on:

- [ ] it powers up with the ignition and powers down with it — **A7 is
      switched, A4 is permanent**; getting these backwards flattens the battery
      over a weekend
- [ ] it survives cranking the engine: it may reboot, but it must come back
- [ ] the dimmer input (A6) actually dims it at night
- [ ] steering wheel controls work at the wheel, not just on the bench
- [ ] the audio path is quiet with the engine running — alternator whine here
      is a ground-loop problem, not a firmware one

**Then** put the fascia on.

---

## 5. Continuous integration

Two workflows, kept apart because they cost very different amounts.

- **`verify.yml`** runs on every push: the differential suite, the WASM
  preview build, the simulator's behaviour tests, and the animation tools.
  Fast enough that nobody resents it.
- **`firmware.yml`** runs when `firmware/` or `core/` changes, in an
  ESP-IDF container, building **both** panel targets and printing the image
  size. They differ by one `-D` and a driver, which is exactly the sort of
  thing that quietly stops compiling because nobody builds the one they do not
  own.

Neither can flash a board. The gap between "the firmware compiles for both
panels" and "the firmware works" is §3, and it is yours to close.

---

## 6. Adding a test

**A screen changed?** Add a row to the right `.tsv` in `tools/verify/` and
regenerate the expectation. The JavaScript reference is the authority.

**A behaviour changed?** Add a `check()` to `tools/sim/test_behaviour.py`,
named after what a person would notice — "clock after ~3s of silence", not
"state transition at frame 60". A test named after an implementation detail
stops being maintained the moment the implementation changes.

**Sample near a boundary, not on it.** The idle checks sample at 8 s for a 7 s
transition, because a test that depends on which side of a frame a boundary
rounds to is testing the harness, not the deck.
