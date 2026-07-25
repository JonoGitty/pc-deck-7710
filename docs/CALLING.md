# Taking calls

**Short answer: yes, on the chip this build already specifies, and it needs
one £4 microphone and one extra wire.** The screens are written and you can
look at them today. The firmware side is designed, not written — this page is
explicit about which is which.

---

## 1. Can the ESP32 do it at all?

Yes, and this is the part worth being careful about, because it is the same
shape of question that killed the ESP32-S3 for this project.

Hands-free calling is **HFP** — the Hands-Free Profile. There are two roles: the
*Audio Gateway* (the phone) and the *Hands-Free unit* (a car kit, a headset,
this deck). ESP-IDF implements the HF side as
[`esp_hf_client`](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/bluetooth/esp_hf_client.html) ✅,
and it is Bluetooth Classic — so it lands on the same side of the S3 problem as
A2DP. The original ESP32 has it. The S3, C3 and C6 do not.

**Nothing about adding calls changes the chip choice.** It reinforces it.

### Running it alongside music

HFP and A2DP have to coexist: you are listening to music when the phone rings.
That combination is not theoretical —
[`walinsky/a2dpsinkhfpclient`](https://components.espressif.com/components/walinsky/a2dpsinkhfpclient/versions/0.0.9/readme) ✅
is a published ESP-IDF component doing exactly this (tested on IDF v5.1–v5.3;
this project is on 5.3), and there are working car-kit builds in the wild. The
audio path switches from A2DP to HFP when a call starts and back when it ends.

⚠️ Neither that component nor any of this has been run on hardware here.

### Codecs

| Codec | Rate | Notes |
|---|---|---|
| **CVSD** | 8 kHz | The HFP default. Narrowband, and it sounds like a phone call from 2005 |
| **mSBC** | 16 kHz | HFP 1.6 Wideband Speech. Noticeably better, and what you want |

The ESP32 supports both, negotiated with the phone. Take mSBC where the phone
offers it.

### Audio datapath

Two options, and the choice matters for wiring:

- **PCM** — dedicated hardware pins carrying the voice stream to an external
  codec. Fewer CPU cycles, more pins, and this build has no pins.
- **HCI** ("Voice over HCI") — the voice frames come up through the normal
  Bluetooth transport and the application moves them. More CPU, **no extra
  pins**, and the audio ends up somewhere software can see it — which is what
  makes the on-screen microphone meter possible.

**Use HCI.** The pin budget decides it, and the meter is worth having.

---

## 2. The microphone

An I²S MEMS microphone. No analogue front end, no codec chip, no gain
trimming — the part contains a sensor, an amplifier, an ADC and an I²S
interface, and it hands the ESP32 finished digital samples.

| Part | ~Cost | Notes |
|---|---|---|
| **INMP441** ✅ | £3–5 | The common one. 24-bit I²S, omnidirectional, sold on a small breakout with mounting holes |
| **SPH0645LM4H** ✅ | £5–7 | Adafruit's equivalent; same interface, slightly different startup timing |

Either works. Buy the INMP441 unless you already have the other.

**Where it goes matters more than which one you buy.** A microphone behind a
fascia, pointing into the dashboard, picks up the dashboard. It wants to be on
a short lead, up near the A-pillar or on the steering column, pointing at your
face — the same place every aftermarket car kit puts it, for the same reason.

### The one extra wire

The ESP32's I²S peripheral can run **full duplex**: transmit and receive on one
controller, sharing the bit clock and word-select lines. The DAC is already on
those. So the microphone needs its own **data** line and nothing else:

| Mic pin | ESP32 | Shared with |
|---|---|---|
| VDD | 3V3 | |
| GND | GND | |
| SCK | **GPIO 26** | the DAC's BCK |
| WS | **GPIO 25** | the DAC's LRCK |
| SD | **GPIO 15** | — this is the only new wire |
| L/R | GND | selects the left slot |

**Why GPIO 15 is safe here and would not be safe for a button.** GPIO 15 is a
strapping pin: it must read HIGH at power-on. It has an internal pull-up, and
an I²S microphone's data line is high-impedance until the clock starts — so at
boot nothing is driving it and the pull-up wins. A *button* on that pin would
be a short to ground and would break the boot. See
[BUILD.md §3](BUILD.md#first-why-the-pins-are-where-they-are) for the full
budget.

Sharing the clocks means the microphone and the DAC always run at the same
sample rate. During a call that is what you want anyway: both ends of the
conversation are at 8 or 16 kHz, and the music is paused.

---

## 3. The screens

Written, in `core/screens/call.c`, and rendered from the real core by
`tools/media/callshots.c`. Four states.

![Incoming call](media/call-incoming.gif)

**Incoming.** The caller's name at the largest size that fits, the number
underneath in case the name is a nickname you do not recognise, and the two
things you might do about it labelled in the corners. The border pulses in the
telephone's own cadence — two beats and a rest.

The border is the whole indicator, and it replaced a little handset glyph with
concentric rings that turned out to be about six lit dots and read as a smudge.
A phone ringing has to be caught in peripheral vision by somebody watching a
road; the largest thing a panel has is its own edge.

![Dialling out](media/call-outgoing.gif)

**Dialling.** The number, and three dots filling in turn — the only moving
thing on the screen, which is what distinguishes "still connecting" from
"crashed".

![In a call](media/call-active.gif)

**In a call.** Duration, who you are talking to, and a **live microphone
level**. That meter is not decoration: it is the only feedback in the entire
system that the microphone is plugged in, positioned somewhere useful, and
being heard. Without it a working call and a dead microphone look identical.

![Call ended](media/call-ended.gif)

**Ended.** How long it lasted, for a couple of seconds, then back to whatever
was playing.

### Rules these screens follow

- **No meaning in brightness.** On a 1-bit VFD the four levels collapse.
  Hierarchy here is carried by *size and position*, which survive.
- **The prompts are always on screen**, in the same corners. Nobody learns a
  control layout while a phone is ringing at them.
- **`DECK_CLIP` is used, once, on purpose.** Level 4 is reserved as the audio
  clipping indicator and renders red on a colour panel. During a call there is
  no audio path to clip, the indicator has no other job, and red is the correct
  colour for a telephone. It appears in no other call state.

---

## 4. Controls

| Action | Wheel | Panel | Remote |
|---|---|---|---|
| Answer | the phone/pick-up button, learned | **SRC** | ▶ |
| Reject / end | the same button held, or the hang-up button | **DISP** | ■ |
| Redial | — | hold **SRC** when idle | — |

The wheel buttons come through the same learning wizard as everything else
(hold SRC for five seconds) — a phone button on a steering wheel is just
another resistance on the ladder, so no new mechanism is needed. See
[BUILD.md §3](BUILD.md#steering-wheel-controls).

---

## 5. What is actually built

| Piece | State |
|---|---|
| The four call screens, in portable C | ✅ **Written**, rendered, in the media pipeline |
| `deck_call_t`, the state the screens read | ✅ Written |
| Microphone part selection and wiring | ✅ Researched, pin assigned, ⚠️ nothing bought |
| HFP client in the firmware | ⚠️ **Designed, not written.** `esp_hf_client` init, the event mapping below, and the A2DP↔HFP audio switch |
| Anything on hardware | ❌ Never |

### The event mapping, for whoever writes it

| ESP-IDF event | Becomes |
|---|---|
| `ESP_HF_CLIENT_CIND_CALL_SETUP_EVT` = incoming | `DECK_CALL_INCOMING` |
| `ESP_HF_CLIENT_CLIP_EVT` | `name` / `number` |
| `ESP_HF_CLIENT_RING_IND_EVT` | keeps the ring alive |
| `ESP_HF_CLIENT_CIND_CALL_SETUP_EVT` = outgoing | `DECK_CALL_OUTGOING` |
| `ESP_HF_CLIENT_CIND_CALL_EVT` = active | `DECK_CALL_ACTIVE`, start the timer |
| `ESP_HF_CLIENT_AUDIO_STATE_EVT` | which codec got negotiated; log it |
| call cleared | `DECK_CALL_ENDED` for two seconds, then idle |

And out: `esp_hf_client_answer_call()`, `esp_hf_client_reject_call()`,
`esp_hf_client_dial()`.

`mic` on the screen comes from the outgoing HCI voice frames — peak-hold over
the last frame, scaled to 0..255. Since those frames pass through software
anyway on the HCI datapath, the meter costs nothing.

---

## 6. Testing it

The screens run on your computer today:

```sh
sh tools/media/make.sh          # regenerates the four GIFs above
```

The bench procedure for the hardware, when the firmware exists, is in
[TESTING.md](TESTING.md) — and the microphone gets its own step, because
"nobody can hear me" is the failure this whole feature is prone to and it is
invisible from the deck's end without that meter.

> **Read [SAFETY.md](../SAFETY.md).** Answering a call is a control you will
> reach for while moving. That is the argument for the wheel buttons and
> against a menu.
