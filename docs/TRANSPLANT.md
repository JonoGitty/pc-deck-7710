# Moving the parts across

The instructions say "fit the panel" and "reuse the buttons". Both hide a day
of work, and both are where the mistake is a hole in a fascia rather than
something you can undo. This page is that day.

Read [DONORS.md](DONORS.md) first for *which* unit to gut.

---

## 1. Moving the screen

![The module, its lit area, and where the window goes](media/transplant-panel.svg)

**The module is bigger than the hole, and the lit area is not centred on it.**
A 3.12" SSD1322 board is about 100.5 × 33.5 mm and only 76.8 × 19.2 mm of that
lights up — the driver and the ribbon take one end. So the board hides behind
the fascia and only the glass shows, and the window has to be aligned to the
glass rather than to the board.

### The four things that decide it

**Mark from the lit area, never from the PCB and never from a measurement.**
Hold the module against the fascia, power it, and scribe round what actually
glows. Every other method introduces the offset you cannot see.

**The panel sits *at* the fascia plane, not behind it.** Recess a dot-matrix
display even a few millimetres and you are looking down a tunnel: contrast
falls, the viewing angle narrows, and the top row disappears from the driver's
seat. This is the difference between a deck that looks lit and one that looks
switched off in daylight.

**Height is the constraint, not width.** 100.5 mm across a 182 mm fascia is
easy. 33.5 mm against a 53 mm face is not, once the bezel and the mounting are
in — check it before you cut.

**Note which end the ribbon leaves from** and orient the module so it exits
towards the main board, with a service loop. A ribbon pulled taut tears at the
connector rather than in the middle, and the connector is the part you cannot
replace.

### Holding it there

Three ways, in order of preference:

| | |
|---|---|
| **M2 standoffs to a bracket** | The proper way. The module has mounting holes; a strip of 1 mm aluminium across the back of the fascia gives you something to screw to. Removable, which matters because you will take it out again. |
| **VHB tape to the fascia's inner ribs** | Fast and surprisingly solid. ⚠️ It is permanent — plan on never getting the module off intact. |
| **Trapped between the fascia and a foam block** | For a bench mock-up only. It will move in a car. |

⚠️ **Do not rely on the ribbon to hold the panel**, and do not let the panel
hang off the window's edge. A car vibrates continuously and the glass is the
part that does not survive being levered.

---

## 2. Moving the buttons

![Breaking the donor's matrix and rewiring it as a ladder](media/transplant-buttons.svg)

A donor's front panel is a **scanned matrix**: rows and columns into a decoder
chip you are about to bin. The deck reads **one analogue pin**. So the job is
to break the matrix and rebuild it as a ladder — every switch commoned on one
side, and its other leg to ground through its own resistor.

The good news is that a ladder is *simpler* than a matrix, so this is a
subtraction rather than a reverse-engineering exercise. You never need to know
what the original scanning order was.

### The two cases, which are not the same job

**Discrete tactile switches on a PCB** — the easy one. Cut the board free of
the main assembly, cut the matrix traces, and wire each switch: one leg to the
common node, the other through its resistor to ground. An hour with a scalpel
and a meter.

**Carbon pads on a flexi** — rubber caps pressing onto interdigitated traces.
Electrically identical, mechanically much fiddlier: the traces are fine-pitch
and they lift or melt if you dwell on them. Wire to the pads' trace pairs, and
practise on a spare corner of the flexi before touching the ones you need.

### Where the resistors live

**On your own board, not on the fascia.** Only the switch wires have to cross
the gap, which means six thin wires and a common return rather than six
resistors soldered to a thirty-year-old flexi. It also means changing a value
later is a board change, not a strip-down.

The values, and what they read, are in [BUILD.md](BUILD.md) — 0 R, 1 k, 2k2,
4k7, 10 k, 18 k against a 10 k pull-up.

### The knob

Donor knobs push onto a D-shaft or a splined shaft. An EC11 encoder has a 6 mm
shaft, either D-cut or knurled, and the two rarely match.

- **Best:** keep the donor's own encoder if it is a standard EC11-alike — many
  are, and then the knob fits by definition.
- **Usually:** ream or drill the donor knob to the encoder's shaft. Slow, and
  it works.
- **Last resort:** a shaft adapter, which adds length you may not have.

⚠️ **Check the depth before committing.** The encoder body has to sit where the
original one did or the knob will not seat against the fascia, and there is
usually less room than there looks.

### The lighting

Donor fascias light their buttons through moulded light pipes fed by LEDs on
the button board. Those pipes are the hard part and you already have them — fit
your own LEDs behind them and drive them from the dimmer line. Matching the
original colour is a matter of choosing the LED, and amber is easy to buy.

---

## 3. "Can I just buy one that is already built?"

Short answer: **no, and the nearest thing is cheaper than you would expect.**

**There is no 1-DIN head unit sold as a blank programmable platform.** Real
head units run locked firmware on proprietary SoCs with no published toolchain,
no documented pinout to the display, and no way in. Reflashing one with this
project is not a hard task, it is not a task — there is nothing to flash to.

Three things come close, and only one of them is this project:

| | What it actually is | Verdict for this build |
|---|---|---|
| **A new empty 1-DIN pocket** ✅ | A £6–12 ABS box, DIN-sized, with a fascia and trim bezel, sold to fill the hole left by a removed radio | **This is the answer.** Correctly sized, brand new, nothing to gut, no hazards. You cut your own window in fresh plastic and fit your own buttons. See [DONORS.md](DONORS.md) |
| **An Android 1-DIN unit** ⚠️ | An Android tablet in a DIN box — Joying, Dasaita, ATOTO and similar, 178 × 50 mm | You can install apps, so you could point a browser at the PC deck's page. But it is a different machine running a different stack, and you are not flashing `core/` onto it. A parallel project, not this one |
| **Other open-source head units** ⚠️ | [PILOT Drive](https://hackaday.io/project/191356-pilot-drive-an-open-source-headunit), OpenAuto/Crankshaft on a Raspberry Pi, [EHU32](https://github.com/PNKP237/EHU32) for Opel/Vauxhall | Real projects, worth reading, and aimed at screens and CarPlay rather than at a dot-matrix deck. Different goal |

So the "pre-built, no firmware" route is: **buy an empty pocket, buy the cage,
and put your own board in it.** It is the fastest path to a fitted deck, it is
the safest — no laser, no inverter, nothing charged — and it costs less than
most spares-or-repair head units.

⚠️ Its one real drawback is that it is **plastic**: no chassis ground, and less
stiff than a steel donor. Run a proper earth wire and support the boards
properly, and it is fine for something drawing under 5 W.

---

## What this page does not cover

The deck has **never been built**, so everything above is derived from the
part datasheets, the ISO standards and the module dimensions rather than from
having done it. The failure modes described are real and predictable; the
timings ("an hour with a scalpel") are estimates.

If you do this, the numbers that would most improve this page are the donor's
measured window, the module's measured lit-area offset, and how much depth the
bezel actually eats. All three are one-line edits to `donors/*.json` and the
drawings correct themselves.
