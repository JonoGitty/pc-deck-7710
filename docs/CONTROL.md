# Controlling the deck

The legacy deck is already fully driven by keys and a wheel, and that is the
gift: every action the hardware needs already exists as a named action with a
binding. The job is to route physical inputs to the same actions, not to invent
a new interface.

## The action set

Everything the deck can be told to do, independent of how:

| Action | Legacy binding | Notes |
|---|---|---|
| `MODE_NEXT` / `MODE_PREV` | `D`, knob click | cycles the ten screens |
| `MODE_SET(n)` | `1`–`9`, `0` | direct |
| `SCREEN_ART`, `SCREEN_LYRICS` | `A`, `L` | direct to a metadata screen |
| `MOVIE_NEXT`, `MOVIE_SET(id)` | — | **new**: the movies list |
| `BRIGHT_UP` / `BRIGHT_DOWN` | scroll wheel | master contrast on the panel |
| `COLOUR_NEXT` | `C` | colour-capable targets only |
| `DEMO_TOGGLE` | `M` | attract loop |
| `SAVER_TOGGLE` | `B` | force the movie screen |
| `LOUD_TOGGLE` | EQ | |
| `LYRIC_NUDGE(±)` | `[`, `]` | sync trim |
| `SOURCE` | SRC | which input |
| **`TRANSPORT_PLAY/PAUSE/NEXT/PREV`** | — | **new**: AVRCP back to the phone |
| `VOLUME_UP/DOWN` | — | **new** |

The two new families are what make it a head unit rather than a display: it
sends commands *back* to the phone.

## Physical surface

Minimum that feels like a real deck:

- **Rotary encoder with push.** Rotate = **volume**; push = **play/pause**,
  which also answers a call — answering must not need a different button from
  the one already under your thumb.
- **Six buttons**: `SRC`, `DISP`, `|◀◀`, `▶‖`, `▶▶|`, `DEMO`.

⚠️ **Three of those six used to be screen shortcuts, and that was a bug.** The
ladder was `SRC`, `DISP`, `OCEAN`, `ART`, `LYRICS`, `DEMO` — four buttons
choosing a screen, three of them shortcuts to screens `DISP` already cycles to,
and **not one that changed the music**. The transport actions existed and
`deck_main.c` sent the right AVRCP codes; the only thing that raised them was
`deck_swc.c`, the steering wheel. So in a car without wheel controls — and the
**Honda S2000 has none in any market** — you could not skip a track from the
deck at all. Nothing was broken; the join was simply missing, which is why
`tools/verify/test_diagrams.py` now asserts that all three transport actions
appear in a table a hand can reach.

The resistor values did not change. It is which action each voltage means, so a
fascia already wired to the old table needs no rework.

**Long-press** is deliberately only two things, and neither is skip: hold `SRC`
for the steering-wheel learning wizard, hold `DISP` for the self-test. A head
unit whose every button does something else when held is one nobody can use
without the manual.

How many of those you can actually wire is decided by the chip, not the UI: an
ESP32-WROVER-E has **six** pins left for a human to press once the panel, the
DAC and the encoder are wired, because GPIO 16/17 are the module's PSRAM. Three
buttons go straight on GPIOs; all six go on one ADC pin as a resistor ladder —
which is also how you reuse a donor head unit's own fascia. Values and wiring
are in [BUILD.md §3](BUILD.md#controls-the-full-six-on-one-pin), reasoning in
[HARDWARE.md §5](HARDWARE.md#5-controls).

An **infrared remote** is possible — a TSOP38238 and the ESP32's RMT
peripheral, which times the pulses in hardware — but by the time a microphone
and a tuner are fitted there is no pin left for it without combining the
ignition and dimmer inputs onto one ADC channel. The full budget, and the
resistor network that buys the pin back, are in
[HARDWARE.md §5c](HARDWARE.md#5c-the-remote-control-aux-and-usb). In a car the
steering wheel beats a remote anyway: no line of sight, no aim, no hand off
the wheel.

Brightness deserves comment: on the SSD1322 it should drive **master contrast**,
not scale the framebuffer. Dimming in software costs levels — a dot at DIM on a
half-brightness frame quantises to nothing — whereas master contrast keeps the
whole greyscale ramp intact and just makes it dimmer. Same reasoning as the
thin-feature rule: don't spend levels you can keep.

## The second control surface

A deck in a dashboard has no keyboard, and some things (picking a movie,
choosing a colour scheme, entering hotspot credentials) are miserable on an
encoder. So:

**The deck serves its own web UI over WiFi.** It is already on the phone's
hotspot for lyrics and art, so the phone can reach it. That page is the settings
screen — display target, brightness curve, movie list, WiFi, sync trim,
firmware version — and it can host the movie uploader.

This is not extra work so much as relocated work: the alternative is building a
menu system on a 256×64 strip driven by one encoder, which is more code and
worse to use. The encoder then only has to cover what you'd want to do while
driving, which is a much smaller list — and that is the right split anyway,
because a menu you can only reach while parked is not a menu you can crash into.

## Open questions

- Encoder for volume, or volume on the phone and the encoder for browsing?
- Should the web UI be reachable when the deck is *not* on a hotspot — i.e.
  does the deck run its own AP as a fallback? (Probably yes, for first-run
  setup, but it is another radio mode to get right.)
- Is a physical volume knob even wanted, given AVRCP volume is the phone's?
