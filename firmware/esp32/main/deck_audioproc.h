/* PT2313 / TDA7313 audio processor: source selection AND volume.
 *
 * WHY THIS EXISTS, WHICH IS A GAP THIS PROJECT SHIPPED WITH
 *
 * The deck could select a source and could not change how loud it was. Not
 * quietly, not badly — at all. The encoder was wired to panel brightness, the
 * steering wheel's VOLUME UP button was wired to the same place, the tuner's
 * output level was set to maximum once at boot and never touched, and the aux
 * socket was a passive path with nothing in it at all.
 *
 * You cannot fix that downstream of a 74HC4052, because a mux passes a signal
 * or it does not. So the fix is to replace the mux with the part a real head
 * unit uses for the same job:
 *
 *   · 3 stereo inputs with selection      — replaces the 74HC4052 entirely
 *   · volume, 1.25 dB steps               — the thing that was missing
 *   · bass and treble
 *   · balance and fader, four channels
 *   · mute
 *   · loudness
 *
 * All of it over I2C, on the bus the tuner already uses. So it costs NO new
 * pins and it RETURNS two: GPIO 2 and 12, which the mux's select lines had.
 *
 * FALLBACK, BECAUSE THE 4052 BUILD IS ALREADY DOCUMENTED
 *
 * The chip is probed at boot. If it answers, it owns the audio path. If it
 * does not, deck_source.c drives the 74HC4052 on GPIO 2 and 12 exactly as
 * before and the deck has no volume control — which is worth knowing about
 * rather than discovering in a car, so it is logged and shown by the
 * self-test.
 *
 * ⚠️ NEVER RUN ON HARDWARE, and the register encoding below is from the
 * datasheet rather than from a scope.
 */
#ifndef DECK_AUDIOPROC_H
#define DECK_AUDIOPROC_H

#include "deck_source.h"

/* Probe and initialise. Returns 0 if a processor answered. */
int deck_audioproc_start(void);
int deck_audioproc_present(void);

/* 0..63, where 63 is loudest. The deck's own scale, not the chip's — the
 * PT2313 counts attenuation downwards and every caller here thinks in volume
 * upwards, so the inversion happens once, at the chip boundary. */
void deck_audioproc_volume(int vol);
int  deck_audioproc_volume_get(void);

/* Which input reaches the speakers. Same enum as the mux, so callers do not
 * care which part is fitted. */
void deck_audioproc_source(deck_source_t s);

/* -7..+7, in the chip's 2 dB steps. */
void deck_audioproc_bass(int v);
void deck_audioproc_treble(int v);

/* -7..+7. Negative is left / front. */
void deck_audioproc_balance(int v);
void deck_audioproc_fader(int v);

void deck_audioproc_mute(int on);

#endif /* DECK_AUDIOPROC_H */
