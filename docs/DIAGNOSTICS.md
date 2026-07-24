# When it does not work

The deck is designed to tell you what is wrong with it. This is how to make it.

The problem being solved: a deck showing nothing has six equally plausible
causes and, from the outside, one symptom. Dead board? SPI miswired? Panel init
wrong? Renderer crashed? Never paired? Working perfectly and waiting? You
cannot tell, and without help you will spend an evening finding out.

So there are three layers of reporting, each usable when the one above it is
not.

---

## Layer 1 — the panel tells you

Every boot runs a four-stage self-test, in an order where each stage can only
fail for reasons the previous ones have already ruled out.

| Stage | On screen | Proves | If it fails |
|---|---|---|---|
| **1** | Grey ramp, one-dot grid, border | Wiring, supply, SPI clock, init sequence. Comes **straight from the panel driver** — no `core/`, no framebuffer, no output stage | It is hardware, or the wrong panel build. Nothing after this can work |
| **2** | Five vertical intensity bands | `core/`'s output stage: how five levels collapse onto your glass, and where the dither falls | Glass is fine. Level mapping or dither is wrong — a software bug in a place stage 1 bypassed |
| **3** | "DECK 7710", version, alphabet | Framebuffer, coordinates, character ROM | Font or geometry. Text is also the canary for a mirrored axis, because everything else still looks plausible when flipped |
| **4** | Subsystem table | Everything else | Read what it says |

**A blank panel at stage 1 is a hardware problem. A blank panel after stage 1
is a software problem.** That single distinction is why the self-test exists.

The stage-1 pattern is chosen, not decorative: the ramp proves all sixteen
greys reach the glass, the one-dot grid proves the nibble packing is not
doubling or halving the width — the classic SSD1322 first-day fault — and the
border proves the addressing window covers the whole panel rather than a
plausible-looking subset of it.

**Hold DISP while powering on** to get the status screen at any time, which is
how you diagnose a deck that has been in a dashboard for six months.

---

## Layer 2 — the serial line

```sh
python3 tools/deckctl.py logs
```

Anything worth machine-reading comes out as one structured line:

```
DECK|<uptime_ms>|<subsystem>|<event>|<key=value ...>
```

That format exists so a tool can parse it. A log needing a regexp per message
is a log nobody writes the tool for. `deckctl logs` colours it, tracks event
counts and prints a summary when you stop.

### Health is a four-state thing, not a boolean

| State | Means |
|---|---|
| `unknown` | Has not been tried yet. **Not a failure** |
| `ok` | Working |
| `degraded` | Working, but not as intended |
| `failed` | Tried, did not work |

Conflating `unknown` with `failed` is how people end up chasing a Bluetooth bug
on a deck nobody has paired. A subsystem that has had no reason to run yet says
so.

Only *transitions* are logged. A subsystem reporting "ok" forty times a second
is a subsystem whose log nobody reads.

### Boot reasons worth knowing

The deck prints why the last boot happened, because "it rebooted and I do not
know why" is the commonest and least actionable bug report there is.

| Reason | What it usually means |
|---|---|
| `power-on` | Normal |
| `brownout` | **The 5 V rail sagged.** In a car this is almost always cranking or an undersized buck converter, not software |
| `task-wdt` / `int-wdt` | Something blocked for ten seconds. There will be a core dump |
| `panic` | A crash. There will be a core dump |
| `software` | A deliberate restart, usually after an update |

---

## Layer 3 — the crash survives the reboot

The crash you care about happens in a car, not on the bench, and there is no
debugger attached. So a core dump goes to flash and stays there.

```sh
python3 tools/deckctl.py coredump
```

You get the faulting task, the program counter and a full backtrace.

> **The ELF must be the exact binary that crashed.** Rebuilding between the
> crash and reading it moves every address and produces a confident, wrong
> trace. If you are chasing something intermittent, keep the build directory.

---

## Symptoms, causes

| What you see | Almost always |
|---|---|
| Nothing at all, no serial output | Power, or a charge-only USB cable. They are visually identical to data cables |
| Serial works, panel blank, no stage 1 | Panel wiring or supply. Check DC and RST especially — they are the two that produce a *silent* failure rather than garbage |
| Stage 1 doubles or halves the image | Nibble packing / column addressing. The grid pattern is there to make this obvious |
| Stage 1 fine, stage 2 wrong levels | Built for the wrong panel — a 1-bit image on 16-grey glass or vice versa |
| Text backwards | Mirrored axis. Text is the only thing that shows it |
| Panel fine, no Bluetooth device visible | Already connected to something else; it stops advertising on connect. Disconnect or reset |
| Pairs, plays, display frozen | Should be impossible: the analyser is fed before the DAC. File a bug with the log |
| Pairs, display moves, no sound | I2S DAC. `audio health ... no I2S DAC` will be in the log |
| No track name | AVRCP did not connect, or the player publishes no metadata. Some do not |
| Random button presses | GPIO 34–39 floating. They have **no internal pull-up**; fit external resistors |
| Knob sometimes goes the wrong way | Encoder wired to pins whose pull-ups are missing, or A and B swapped |
| Reboots when starting the engine | Brownout. The supply, not the firmware |
| Lyrics never appear | Needs WiFi. Expected in a car |
| `MOVIE` says none installed | `python3 tools/deckctl.py movies` |

---

## Reporting a bug so it can be fixed

Include:

1. `python3 tools/deckctl.py doctor` output — tools, chip, PSRAM.
2. `python3 tools/deckctl.py logs` from a reset, through the failure.
3. Which panel and which build (the log's first lines say both).
4. A photograph of the panel if the fault is visual. On a dot-matrix display
   the *pattern* of what is wrong is most of the diagnosis, and no description
   of it is as useful as the picture.

If it crashed, add `deckctl coredump` and say whether you rebuilt in between.

---

## What the deck does *not* do

It has no functional safety design, no verified fail-safe state, and no
guarantee it will not hang with the panel lit. The watchdog reboots a blocked
render loop, which is a mitigation and not a promise. See
[SAFETY.md](../SAFETY.md).
