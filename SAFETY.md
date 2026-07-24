# Safety, liability, and what this project is not

Read this before you wire anything to a car.

## The short version

**This is an unfinished hobby project published as source. It is not a
product. Nothing here has been tested in a vehicle, certified by anybody, or
approved for road use. You are the manufacturer of whatever you build, and
every consequence of it is yours.**

The MIT licence in [LICENSE](LICENSE) already says the software comes with no
warranty and that the authors are not liable. That clause is about software.
This project also tells you to cut into a car's electrical system, so the same
disclaimer is repeated here in the terms that actually apply:

> THE DESIGNS, SCHEMATICS, PART LISTS, WIRING GUIDANCE, FIRMWARE AND
> DOCUMENTATION IN THIS REPOSITORY ARE PROVIDED "AS IS", WITHOUT WARRANTY OF
> ANY KIND. THE AUTHORS AND CONTRIBUTORS ACCEPT NO LIABILITY FOR ANY DAMAGE TO
> VEHICLES, PROPERTY OR EQUIPMENT, FOR ANY INJURY OR DEATH, FOR ANY FINANCIAL
> LOSS, OR FOR ANY LEGAL, INSURANCE OR REGULATORY CONSEQUENCE ARISING FROM THE
> USE, MISUSE, MODIFICATION OR DISTRIBUTION OF ANYTHING IN THIS REPOSITORY.
> YOU ASSUME ALL RISK.

## Specific things that can actually go wrong

These are not hypothetical. They are the failure modes this build has.

**Fire.** A car battery will deliver hundreds of amps into a short without
noticing. Any wire you run from the battery or from a permanent live **must**
be fused within 150 mm of where it takes power, at or below the rating of the
smallest wire in the run. An ISO harness adapter usually inherits the car's
existing fusing; a wire you add yourself does not.

**Airbags.** Modern dashboards route airbag wiring, and some route it near the
radio aperture. Yellow connectors and yellow loom are the convention for
pyrotechnic circuits. Do not cut, pierce, unplug or probe them. Disconnect the
battery and wait for the manufacturer's stated time before working near them —
several minutes is typical, because the airbag controller holds charge.

**Battery drain.** A deck wired to permanent live that does not sleep properly
will flatten a car battery in days. Ignition sense (ISO 10487 pin A7) exists
for this. Measure your standby current before leaving the car for a week.

**Distraction.** A bright animated display in a driver's eyeline is a
distraction, and in many jurisdictions a moving image visible to the driver is
specifically illegal. Whatever you build, you are responsible for it being
legal where you drive it. Fit a dimmer to the illumination feed (pin A6), and
consider whether the dolphins should run while the car is moving.

**Insurance and type approval.** A non-approved electronic device wired into a
vehicle can invalidate insurance and can fail a roadworthiness inspection. That
is between you, your insurer and your local law. This project does not know
where you live and offers no opinion.

**Radio compliance.** The ESP32 module is certified as a component; a finished
device containing one is generally not. Selling or distributing what you build
may require CE/UKCA/FCC assessment. Building one for yourself usually does not.
Again: your jurisdiction, your responsibility.

## Working practices this project assumes

- **Disconnect the battery** before touching anything behind the dash.
- **Meter the harness.** ISO 10487 standardises the plastics, not the pinout.
  A4 and A7 are commonly swapped. Assuming is how people let smoke out.
- **Opto-isolate the ignition sense.** Do not feed car 12 V into a GPIO through
  a resistor divider; a load dump transient will go straight through it.
- **Bench first.** Everything in this project can be built and run on a desk
  from USB before any of it goes near a vehicle, and the
  [handbook](docs/HANDBOOK.md) is ordered so that it is.
- **Do not develop while driving.** Obviously, and yet.

## What the firmware does and does not guarantee

The firmware **has never run on hardware**. Read that again before flashing it
to something bolted into a dashboard. It contains no functional safety design,
no watchdog-verified fail-safe state, and no assurance that it will not hang,
crash, or hold the panel at full brightness at the worst moment. It is written
carefully; that is not the same as verified.

The renderer in `core/` *is* verified — against the JavaScript it was ported
from, which is a correctness check on drawing, not a safety property.

## Third-party services

The deck can query two public services. Both are optional and both can be
switched off in one line — see the README.

- **[LRCLIB](https://lrclib.net)** for synced lyrics.
- **[iTunes Search API](https://performance-partners.apple.com/search-api)**
  for album art when the player supplies none.

Each request sends only the track title, artist and album. Neither is operated
by this project, neither is under any obligation to keep working, and both
have their own terms which you are responsible for respecting. No audio is ever
transmitted anywhere.

## Trademarks

Pioneer, Futaba, Noritake, Espressif, Spotify, Apple and any other marks
mentioned belong to their owners. This project is not affiliated with,
endorsed by, or connected to any of them. Where the visual design recalls
1990s head units, it does so as homage; no manufacturer's branding, artwork,
firmware or fonts are reproduced here. The character ROM and every graphic
asset in this repository were generated by code in this repository.
