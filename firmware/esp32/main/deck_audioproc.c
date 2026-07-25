/* See deck_audioproc.h. NEVER RUN ON HARDWARE.
 *
 * THE REGISTER MODEL, BECAUSE IT IS NOT A REGISTER MODEL
 *
 * The PT2313 has no register addresses. Every write is a SINGLE BYTE whose
 * top bits say which function it is and whose bottom bits are the value:
 *
 *     0 0 v v v v v v     volume        0 = 0 dB, 63 = -78.75 dB
 *     0 1 0 l g g s s     audio switch  loudness, input gain, input select
 *     0 1 1 0 x b b b b   bass
 *     0 1 1 1 x t t t t   treble
 *     1 0 0 x a a a a a   speaker  left rear
 *     1 0 1 x a a a a a   speaker  right rear
 *     1 1 0 x a a a a a   speaker  left front
 *     1 1 1 x a a a a a   speaker  right front
 *
 * Two consequences worth stating because they are easy to get backwards:
 *
 * ATTENUATION, NOT VOLUME. Every field counts DOWN from loud. 0 is 0 dB and
 * bigger numbers are quieter. Everything above this driver thinks in volume
 * going up, so the inversion happens once, here, at the chip boundary — not
 * scattered through the UI where half of it will get missed.
 *
 * TONE AND BALANCE ARE SIGNED AND STORED AS MAGNITUDE-PLUS-DIRECTION, not as
 * two's complement. Bass of -7 and +7 are different bytes with the same low
 * nibble, and a driver that just casts an int gets the sign silently wrong.
 *
 * ⚠️ The encoding above is from the datasheet. Nothing here has been on a
 * scope, and the bit that is most likely to be wrong on first power-up is the
 * speaker-attenuator addressing — the four channels differ only in the top
 * three bits and a transposed pair swaps front and rear.
 */
#include "deck_audioproc.h"

#include "deck_diag.h"
#include "deck_i2c.h"

/* 0x44 is the standard write address for the PT2313 and TDA7313. Unlike the
 * tuner there is no strapping pin, so there is one address and a device that
 * does not answer on it is a device that is not fitted. */
#define ADDR    0x44
#define I2C_HZ  100000

#define VOL_MAX 63

static i2c_master_dev_handle_t s_dev;
static int s_present;
static int s_vol = 24;                 /* a sane first power-on, not maximum */
static int s_bass, s_treble, s_bal, s_fade;
static int s_mute;
static deck_source_t s_src = DECK_SRC_BT;

static int wr(uint8_t b) {
  if (!s_dev) return -1;
  return i2c_master_transmit(s_dev, &b, 1, 50) == ESP_OK ? 0 : -1;
}

/* --- the four speaker attenuators ---------------------------------------
 *
 * Balance and fader are not separate registers on this part: they are the
 * four per-speaker attenuators, and the driver works out what each one should
 * be. Doing it here rather than exposing four channels means the UI can offer
 * the two controls a driver actually thinks in.
 */
static void push_speakers(void) {
  /* Attenuation for each corner, 0 = full. Balance pushes one side down,
   * fader pushes one end down; a corner gets the sum, clamped. */
  const int l = s_bal > 0 ? s_bal * 2 : 0;      /* right-biased: cut left */
  const int r = s_bal < 0 ? -s_bal * 2 : 0;
  const int f = s_fade > 0 ? s_fade * 2 : 0;    /* rear-biased: cut front */
  const int b = s_fade < 0 ? -s_fade * 2 : 0;

  const int lf = l + f, rf = r + f, lr = l + b, rr = r + b;
  const int m = 31;
  wr((uint8_t)(0xC0 | (lf > m ? m : lf)));      /* 1 1 0 — left front  */
  wr((uint8_t)(0xE0 | (rf > m ? m : rf)));      /* 1 1 1 — right front */
  wr((uint8_t)(0x80 | (lr > m ? m : lr)));      /* 1 0 0 — left rear   */
  wr((uint8_t)(0xA0 | (rr > m ? m : rr)));      /* 1 0 1 — right rear  */
}

/* Input select plus gain plus loudness, all in one byte.
 *
 * The enum order matches the mux's channel order on purpose — a build that
 * swaps the 4052 for a PT2313 does not have to rewire the inputs, and
 * deck_source.c's numbering stays the single description of which socket is
 * which. */
static void push_switch(void) {
  const int in = (int)s_src & 0x03;
  /* Gain 0 keeps the deck's own line-level sources from clipping the tone
   * stage. Loudness is OFF (bit 3 high) because on a car's speakers it is a
   * bass boost applied to a signal that has already had one. */
  wr((uint8_t)(0x40 | 0x08 | (0 << 2) | in));
}

static void push_volume(void) {
  const int v = s_mute ? 0 : (s_vol < 0 ? 0 : (s_vol > VOL_MAX ? VOL_MAX
                                                              : s_vol));
  /* Invert: the chip counts attenuation, the deck counts loudness. */
  wr((uint8_t)(0x00 | (VOL_MAX - v)));
}

static void push_tone(void) {
  /* Magnitude and direction, not two's complement. The chip reads the low
   * nibble as a magnitude and bit 3 as which way. */
  const int bmag = s_bass < 0 ? -s_bass : s_bass;
  const int tmag = s_treble < 0 ? -s_treble : s_treble;
  wr((uint8_t)(0x60 | (s_bass >= 0 ? 0x08 : 0x00) | (bmag & 0x07)));
  wr((uint8_t)(0x70 | (s_treble >= 0 ? 0x08 : 0x00) | (tmag & 0x07)));
}

/* --- public ------------------------------------------------------------- */
int deck_audioproc_start(void) {
  s_dev = deck_i2c_device(ADDR, I2C_HZ);
  if (!s_dev) {
    deck_diag_event(DECK_SUB_AUDIO, "audioproc", "no bus");
    return -1;
  }
  /* The part is write-only — there is nothing to read back and therefore no
   * way to identify it beyond "did the write ACK". That is enough: an absent
   * chip NAKs and a fitted one does not. */
  if (wr(0x00 | VOL_MAX) != 0) {              /* silence, as a probe */
    deck_diag_event(DECK_SUB_AUDIO, "audioproc",
                    "not fitted — no volume control, mux only");
    s_dev = NULL;
    return -1;
  }
  s_present = 1;

  push_switch();
  push_tone();
  push_speakers();
  push_volume();
  deck_diag_event(DECK_SUB_AUDIO, "audioproc",
                  "PT2313 at 0x%02x — volume, tone and source", ADDR);
  return 0;
}

int deck_audioproc_present(void) { return s_present; }

void deck_audioproc_volume(int vol) {
  if (vol < 0) vol = 0;
  if (vol > VOL_MAX) vol = VOL_MAX;
  if (vol == s_vol) return;
  s_vol = vol;
  s_mute = 0;                     /* touching volume is an intent to hear it */
  push_volume();
}

int deck_audioproc_volume_get(void) { return s_vol; }

void deck_audioproc_source(deck_source_t s) {
  if (s == s_src) return;
  s_src = s;
  push_switch();
}

static int clamp7(int v) { return v < -7 ? -7 : (v > 7 ? 7 : v); }

void deck_audioproc_bass(int v)    { s_bass = clamp7(v);   push_tone(); }
void deck_audioproc_treble(int v)  { s_treble = clamp7(v); push_tone(); }
void deck_audioproc_balance(int v) { s_bal = clamp7(v);  push_speakers(); }
void deck_audioproc_fader(int v)   { s_fade = clamp7(v); push_speakers(); }

void deck_audioproc_mute(int on) {
  if (!!on == s_mute) return;
  s_mute = !!on;
  push_volume();
}
