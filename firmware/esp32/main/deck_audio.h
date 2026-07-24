/* Turn the A2DP PCM stream into the analysis state the screens read.
 *
 * This is the counterpart of the FFT in legacy/server.py, and it has to
 * produce a `deck_state_t` that behaves the same way, because the screens are
 * the same screens. Band edges, the dB floor, the tilt and the smoothing
 * constants are all matched to it deliberately — a spectrum analyser that
 * jumps differently is a different instrument even when the code that draws it
 * is byte-identical.
 *
 * The Bluetooth callback must not do this work. It runs on the Bluedroid task
 * and blocking it stutters the audio, which is the one failure a music player
 * cannot have. So the callback only copies samples into a ring buffer, and the
 * analysis runs on its own task at its own rate.
 */
#ifndef DECK_AUDIO_H
#define DECK_AUDIO_H

#include <stdint.h>
#include "state.h"

#define DECK_FFT_N 512          /* 11.6 ms at 44.1 kHz — the usual compromise
                                 * between bass resolution and a bar that still
                                 * moves with the music */

void deck_audio_init(void);

/* Called from the Bluetooth stack with interleaved 16-bit stereo. Copies and
 * returns; does no arithmetic beyond a peak. Safe to call at any rate. */
void deck_audio_feed(const uint8_t *data, uint32_t len);

/* Advance the analysis and write into `v`. Called from the render loop, so it
 * costs whatever it costs on the frame it runs — but it early-outs when no new
 * audio has arrived, which is what stops a paused deck burning the CPU. */
void deck_audio_update(deck_state_t *v, double dt);

/* True while samples are still arriving. The idle machine uses this rather
 * than the AVRCP play state, because a player can claim to be playing while
 * sending silence and the dolphins should come out for silence. */
int deck_audio_is_live(void);

#endif /* DECK_AUDIO_H */
