# Vehicles

One file per car, grouped `brand / model / generation`, describing **only what
that car changes**. Everything else about the build is identical for every
vehicle on earth, and saying so explicitly is the point of this directory.

```
vehicles/
  honda/s2000/{ap1,ap2}.json
  mazda/mx-5/{na,nb,nc,nd}.json
  toyota/mr2/{w10,w20,w30}.json
```

`python3 tools/vehicles/build.py` turns them into
[docs/VEHICLES.md](../docs/VEHICLES.md), and `python3 tools/deckctl.py fit
s2000` prints one car's kit at the bench. The prose is generated, so adding a
car is adding a file.

---

## The three layers, because conflating them is the whole problem

| Layer | Varies with | Where it lives |
|---|---|---|
| **The deck** | nothing | [docs/BUILD.md](../docs/BUILD.md) — one shopping list, every car |
| **The fitting kit** | the car's *model and generation* | this directory |
| **The radio region** | **where you drive**, not the car | `deck_tuner.c`, set once |

The deck is the same object whether it goes in an S2000 or a Land Rover: the
same ESP32, panel, DAC, mux, tuner and firmware. It fits an **ISO 7736**
aperture and speaks **ISO 10487**, and those two standards are why a
home-built head unit can drop into anything.

What changes per car is a bag of adapters — a fascia to fill the hole, a
harness to reach the car's connector, a plug to reach its aerial — and how
much room there is behind the dash.

### The one people get backwards

**Radio region follows the postcode, not the badge.** A JDM import in Britain
receives British stations, so it wants the European band plan; the fact the car
was built for Japan is irrelevant to its aerial. Everything *else* about
fitting an import follows the car's market — the harness is the one Japan
fitted, the fascia is the one that fits a JDM dash.

Get it wrong and it is not subtle. Japan's FM band is 76–95 MHz against
Europe's 87.5–108, so a European deck driven in Japan can tune about a tenth of
the band. The Americas use 10 kHz AM spacing against 9 kHz elsewhere, and on
the wrong step every station lands between channels.

---

## What a file says, and what it deliberately does not

Every field carries a confidence marker, because a wrong part number costs
somebody money and a wrong measurement costs them a dashboard:

| | Means |
|---|---|
| ✅ `verified` | Checked against a datasheet, a standard, or a fact that is not in dispute |
| ⚠️ `unverified` | Believed true and **not confirmed**. Check before buying |
| 📏 `measure` | Varies between cars of the same model. Measure yours; do not trust any list, including this one |

**There are deliberately no retailer part numbers here.** They change, they are
regional, they go out of stock, and a stale one in a repository is worse than
none because it looks authoritative. What each file gives you is the *thing to
search for* — "Honda 20-pin to ISO 10487 harness adapter" — which does not go
stale and which any retailer's registration lookup will resolve.

## Adding a car

Copy the nearest file, change what differs, run the generator, and open a pull
request. If a field does not apply — many cars have no steering-wheel controls
at all — say so explicitly rather than leaving it out; "none fitted" is
information and a missing key is not.

`tools/verify/test_vehicles.py` checks every file has every field and that no
claim is left without a confidence marker.
