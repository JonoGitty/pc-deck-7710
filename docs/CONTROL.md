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

- **Rotary encoder with push.** Rotate = volume; push = mode; push-and-hold =
  enter the menu. Long-press for a second function is how every OEM deck
  handles a small panel, and it means one part covers three jobs.
- **Six buttons**: `SRC`, `DISP`, `BAND`, `ART`, `LYRICS`, `DEMO`. Skip/back
  double as long-press, which is how every OEM deck handles a small panel.

How many of those you can actually wire is decided by the chip, not the UI: an
ESP32-WROVER-E has **six** pins left for a human to press once the panel, the
DAC and the encoder are wired, because GPIO 16/17 are the module's PSRAM. Three
buttons go straight on GPIOs; all six go on one ADC pin as a resistor ladder —
which is also how you reuse a donor head unit's own fascia. Values and wiring
are in [BUILD.md §3](BUILD.md#controls-the-full-six-on-one-pin), reasoning in
[HARDWARE.md §5](HARDWARE.md#5-controls).

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
