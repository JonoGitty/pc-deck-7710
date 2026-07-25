# Donor units

The chassis, the fascia, the cage, the buttons and the knob, for less than the
cage alone costs new. One file per donor family, graded, with the instructions
that family specifically needs.

```
donors/
  aftermarket/   the ones you buy to gut
  oem/           your car's own unit — the sleeper build
  none/          fold your own, if you would rather
```

`python3 tools/donors/build.py` generates [docs/DONORS.md](../docs/DONORS.md)
and a scale window-fit drawing for each. `python3 tools/deckctl.py donor` picks
one at the bench.

---

## Buy a broken one. That is the whole trick.

**You are buying a box, a face and a bag of buttons.** The CD mechanism, the
amplifier, the tuner and the microcontroller all go in the bin on the first
evening, so a unit that does not work is worth exactly as much to you as one
that does — and costs a fraction.

Search "spares or repair", "faulty", "no CD", "display dead", "untested". A
working head unit is £30–60 and the same model with a jammed CD mechanism is
£8–15, because to everybody else it is scrap and to you it is a chassis.

Two things worth paying a little more for:

- **With the cage and trim ring.** A new ISO 7736 cage is £8–15 on its own, so
  a £15 unit that includes one is cheaper than a £8 one that does not.
- **With the fascia undamaged.** It is the part you cannot replace, the part
  everybody sees, and the part sellers most often lose.

And one thing not to pay for at all: **a working CD mechanism**. It is the
single biggest driver of price on a listing and the first thing you remove.

## What actually matters, in order

### 1. The window, and nothing else comes close

The deck's panel has an active area of about **76 × 19 mm** (SSD1322) or
**76 × 14 mm** (GP1294AI VFD). If the donor's window is smaller than that, you
are cutting the fascia — and a cut fascia is why home-built decks look
home-built.

This is why **the best donors are the ones with a big amber dot-matrix
display**, roughly 1998–2008. Their window is already a wide letterbox of
roughly the right size, in roughly the right place, in the right colour. A unit
with a small segment LCD has a window a third of the size, and no amount of
careful filing makes that look deliberate.

### 2. Depth

A 1-DIN aperture is standard; how far back the car lets you go is not, and
neither is how much of that the donor's own chassis wastes. Measure both.

### 3. The buttons

A donor's front panel is a scanned matrix on a flexible circuit. You are not
reverse-engineering it — you lift the switch commons and wire each switch to a
resistor, which turns the whole fascia into the six-button ladder the firmware
already reads on one pin. See [BUILD.md](../docs/BUILD.md).

Six or more buttons plus a rotary knob is ideal. Fewer than four and you are
better off with new tactile switches behind the original caps.

### 4. What it is made of

Steel chassis, not plastic. Almost all are steel; the very cheapest are not.

---

## ⚠️ Three hazards, and one of them is genuinely dangerous

| | |
|---|---|
| **The CD laser** | Class 1 *with the lid shut* and not with it off. Do not power the original board up "to see if it still works". |
| **The amplifier's electrolytics** | Store energy. Discharge them and bin the board. |
| **A VFD unit's inverter** ⚠️ | The real one. A head unit with a vacuum-fluorescent display generates its own filament and anode supplies — **tens of volts, from a small inverter, held on a capacitor after power-off**. Treat any VFD donor's power board as live until you have proved otherwise. |

That last one is the reason the safest donors to gut are the ones with an LCD,
even though the ones with a VFD are prettier.

---

## The two strategies

**Aftermarket donor.** You get a proper ISO cage, a generic fascia, and a deck
that looks like an aftermarket deck — which it is. Easiest, cheapest, most
availability.

**Your own car's OEM unit.** The fascia already fits your dashboard exactly,
because it was made for it. The result looks factory, which is the point for
some people and irrelevant for others. Costs more, is car-specific, and the
window is usually small — see the entry for your car in
[VEHICLES.md](../docs/VEHICLES.md).

**Or no donor at all.** 1 mm folded aluminium, a cage bought new, and an
acrylic face. Cheapest in money, most expensive in evenings, and the only
option that gives you exactly the window you want.

---

## Adding a donor

Copy the nearest file, measure yours, run the generator. Every dimension
carries a confidence marker for the same reason the vehicle files do: ✅
checked, ⚠️ believed, 📏 measure yours. `tools/verify/test_donors.py` fails on
a claim without one.

**Measure the window with calipers, not from a photograph.** It is the one
number that decides whether the build looks bought or looks made.
