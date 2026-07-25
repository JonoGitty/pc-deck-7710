# Keeping as much of the donor as you can

[DONORS.md](DONORS.md) describes the **simple** build: keep the box, the face,
the cage, the buttons and the knob, and bin the rest on the first evening. That
is the right default, and it is what the strip-down drawings show.

This page is for the other approach — **keep everything you possibly can** —
and it is not just sentiment. One of the parts the default throws away is a
part [BUILD.md](BUILD.md) then tells you to go out and buy.

---

## The one that actually matters: the donor already has an amplifier

**Every CD-era head unit contains a 4-channel amplifier.** Usually a TDA7388,
a TDA7850 or something from the same family — the exact ICs BUILD.md
recommends you buy a board of. In the donor it is already:

- bolted to the chassis casting, which is already its heatsink
- wired to the ISO speaker connector on the back panel
- fed from the car's 12 V through protection that already exists
- fused

So the default build bins a £12–20 part, and then buys the same part again.

![Where to cut into the donor's signal chain, and the mute and standby pins that decide whether it works](media/reuse-amp.svg)

### How to reuse it

The amplifier IC sits at the end of a signal chain you are deleting. The job is
to cut its inputs free of the dead preamp and feed them the deck's line out
instead.

1. **Identify the IC.** The part number is printed on it. Find its datasheet —
   these are all common parts and all documented.
2. **Find the four input pins** from the pinout. They will have a coupling
   capacitor each, fed from the old preamp or tone stage.
3. **Cut the track** on the preamp side of those capacitors, or lift the
   capacitor's input leg.
4. **Inject the deck's line out** there — front left and right from the deck's
   two channels, and rear from the same pair unless you have fitted a PT2313,
   in which case take the fader outputs.
5. ⚠️ **Deal with the mute and standby pins.** This is the step people miss.
   Most automotive amp ICs have a `ST-BY` and a `MUTE` pin that the old
   microcontroller drove, and with that microcontroller gone they float — so
   the amplifier stays muted and you conclude it is dead. Tie them to their
   enable level through the resistor the datasheet specifies.
6. **Leave the speaker outputs and the power input alone.** They already go
   where they should.

### What it is worth

| | |
|---|---|
| **Saves** | £12–20, plus a heatsink and mounting you would have to arrange |
| **Costs** | An evening with a datasheet and a scalpel |
| **Risk** | Low. The worst case is that it does not work and you buy the board you were going to buy anyway |

**The cassette-era units are the easiest of all**, because their amplifiers are
discrete or single-IC with generous layouts and no digital preamp in the way —
the tape head fed them almost directly. If maximum reuse is the goal, that is
the family to choose.

---

## The rest, in order of what it saves

The back panel is the easiest win in the whole project, because keeping it is
**not a job**: the connectors stay on the pressing, and the pressing stays on
the chassis you are keeping anyway.

![The donor's back panel: ISO A, ISO B, the aerial socket, the fuse, and the one thing on it not worth keeping](media/reuse-rear.svg)

| Part | Saves | Difficulty |
|---|---|---|
| **The rear ISO connectors and aerial socket** | £8–15 of adapters | easy |
| **The heatsink** | Hard to buy in the right shape; usually part of the casting | easy |
| **The 12 V input protection** | A pound, and it is already fused and rated for a car | easy |
| **The illumination bulbs and light pipes** | The period look. Swap the bulbs for amber LEDs and keep the diffusers | easy |
| **The IR receiver**, if it had one | £1 and a clear line of sight already drilled | easy |
| **The car-specific connector** — OEM donors only | The harness adapter, entirely | easy |

That last one is worth calling out: on an **OEM donor from your own car**, the
back panel already carries your car's exact connector. Keep it and there is no
harness adapter to buy at all. The fascia usually gets all the credit for the
OEM route; the connector deserves half of it.

---

## Can you keep the CD player?

This is the first thing everybody asks, and it has two answers.

### Driving the mechanism yourself: no

A CD mechanism is **dumb hardware**. It is a spindle motor, a sled motor, a
laser diode and some photodiodes, and it knows nothing. Making it play a disc
takes four closed servo loops — disc, sled, focus and tracking — running on
analogue electronics that are sensitive to board layout, a DSP to turn the
pickup's wobble into bits, and a microcontroller to drive the whole thing.
Those are the parts you are removing. Reusing a mechanism without them means
designing the servo electronics and writing the low-level control code, which
people who do it for a living describe as a black art.

So: **❌ the ESP32 is not going to play a CD**, and no amount of wiring changes
that.

### Not gutting it at all: yes, and it is the best answer

The other reading of the question is the good one. **Do not take the CD player
apart. Leave it working, and put the deck above it.**

| | |
|---|---|
| **The old head unit** keeps | the CD, the radio, the volume knob, the tone controls, and its 4 × 45 W amplifier |
| **The deck** does | Bluetooth, the display, the animations — and feeds the old unit's **AUX input** |
| **You gut** | nothing |
| **You solder** | nothing |

The deck's line out goes into the donor's aux socket and the donor becomes,
from the deck's point of view, an amplifier that happens to also play CDs. Its
volume knob is your volume knob. Its speaker wiring is already done.

**⚠️ It needs two things.** A **2-DIN aperture** — deck in the top half, head
unit in the bottom — which in the fitment list means a **Mazda MX-5 NC** ✅ or a
**Toyota MR2 W20** ⚠️ (believed, measure it). And a donor **with an aux input**:
a front 3.5 mm socket is normal after about 2005, a rear RCA aux on the better
ones, and pre-2005 units mostly have neither.

**What you give up:** the deck cannot control the CD — track skip is the old
unit's buttons — and you have two volume controls, of which only one does
anything. In exchange it is the least destructive build in this project, and
the only one where the disc still spins.

---

## What to do with the hole

Take the mechanism out of a 1-DIN unit and you are left with a letterbox across
the front of the fascia. Everybody sees that as the problem. It is the best
thing about the donor.

![The CD slot, the deck's window, and the three things you can do with the hole](media/slot-options.svg)

**The coincidence is in the dimensions.** A CD slot is about **125 × 12 mm**,
and it is 125 because a CD is 120 across — that number cannot really vary. The
deck's window wants **84 × 27 mm**. So the hole you already have is **41 mm
wider than you need** and 15 mm too short.

That is a filing job along two straight edges that are already there. Compare it
with the alternative — cutting a fresh 84 × 27 rectangle into a thirty-year-old
fascia that cannot be replaced — and the slot stops looking like damage.

| What goes in it | When it is the right answer |
|---|---|
| **The window itself** — file it down to 27 mm tall, blank the extra width behind the bezel | ✅ Best on the **segment-LCD** family, whose own window is 52 × 18 mm and far too small. Rescues the cheapest donors in the project |
| **A row of buttons** — six caps at ~20 mm pitch | ✅ A 125 × 12 aperture is already a button strip. **No drilling at all**, which matters on the one part you cannot replace |
| **The aux and USB sockets** | ✅ Same argument. A blanking strip with two holes in it, made of something you can ruin freely |
| **Nothing — leave the door shut** | ✅ **Cassette-era donors only**, and it is why that family is so good: the door is hinged, it closes flush, and the deck looks factory |
| **A pocket** | If you would rather have somewhere to put a phone than another control |

⚠️ **Several of the best donors have no slot on the face at all.** The
late-1990s and 2000s flagships — the Pioneer DEH-P9000R generation and its
relatives — load the disc **behind a fold-down front panel**, so the fascia is
solid apart from its display window and its buttons. Nothing to fill, and the
window is already 84–90 mm wide. If the panel is *motorised*, take the motor and
gearbox out: it is depth you need and a mechanism you are not using, and then
pin the panel shut rather than leaving it sprung.

Which applies to your donor is in [DONORS.md](DONORS.md), per family, under
**The front of it**.

---

## And the buttons — reuse them, they are better than new ones

[TRANSPLANT.md](TRANSPLANT.md) covers the rewire: a donor's panel is a scanned
matrix into a decoder you are binning, the deck reads one analogue pin, so you
break the matrix, common one side of every switch and take the other leg to
ground through its own resistor. You never have to work out the original
scanning order, which is the part everybody assumes will be hard.

What is worth adding here is **which donors have the good buttons**:

| Family | Buttons | Rewiring them |
|---|---|---|
| **Cassette-era** | ✅ **The best in the project.** Large, mechanical, with real travel — and often on a proper PCB rather than a flexi | The easy case: cut the traces, solder to the switch legs |
| **Dot-matrix (grade A)** | 8–14, so you can pick the six that feel best and blank the rest | ⚠️ Carbon pads on a flexi. Fine pitch, and it melts. Practise on a spare corner |
| **Segment-LCD** | 5–8 — just enough, and this is the family where you might be one short | ⚠️ Usually flexi |
| **Empty pocket / fold your own** | None, so you fit new tactile switches on your own PCB | ✅ No rewire at all. The easiest front panel by a distance |

Nothing you can buy for 20p feels like a 1990s Blaupunkt button, which is the
real argument for the cassette-era route and the reason it keeps coming out on
top of every other question on this page.

---

## The display, honestly

This is the one everybody wants and the one that usually does not work. It is
worth understanding *why*, because the reason decides whether yours is the
exception.

**Most head-unit displays are segment or character devices.** Fixed shapes,
seven-segment digits, a few 5×7 character cells and a lot of dedicated icons.
They are wired to show a frequency and a track number and nothing else. A
256×64 graphic screen cannot be drawn on them at any effort — there are no
pixels to address. ❌

**A genuine graphic dot-matrix panel can, in principle.** But two things get in
the way. The controller is usually undocumented and often custom to the
manufacturer. And the resolution is frequently **128×32** — half the deck's
width and half its height — which would need a new layout tier in `core/`, not
just a driver.

**✅ The exception, and it is a real one:** if the donor's panel turns out to be
a **Futaba GP1294AI**, the firmware already has a driver for it. Those panels
are commonly sold as pulls from car radios, which is exactly where yours would
be coming from. Check the part number on the glass or its flexi before
assuming anything — this is the one case where the answer is yes and the work
is already done.

⚠️ And the standing hazard: a VFD's power board makes its own filament and
anode supplies, tens of volts, held on a capacitor after power-off. Reusing the
panel means keeping that board alive rather than binning it, so the caution
applies for longer.

---

## What this changes about the shopping list

If you reuse the donor's amplifier and connectors, the "to make a sound"
section of [BUILD.md](BUILD.md) drops to **£0** and the car-side wiring gets
simpler rather than harder, because the back panel is already right.

That makes the **cassette-era donor** the cheapest complete route in this
project: a £5–15 unit, often free from a scrapyard, containing a chassis, a
face, an amplifier, a heatsink, connectors, and knobs that are nicer than
anything you can buy.

---

⚠️ **None of this has been done.** The amplifier reuse in particular is
described from the datasheets of the ICs involved and from how these units are
built, not from having cut one open. The mute/standby detail is the one most
likely to bite, which is why it has a numbered step of its own.
