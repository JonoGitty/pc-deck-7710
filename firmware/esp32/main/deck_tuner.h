/* The FM/AM tuner: an Si4735 on I2C.
 *
 * Fills a deck_radio_t for core/screens/radio.c to draw. The screen knows
 * nothing about I2C and this knows nothing about pixels, which is the same
 * split the rest of the deck uses and the reason both can be worked on
 * separately.
 *
 * WHAT THE Si4735 IS
 *
 * Not an analogue front end with a PLL bolted on — a DSP receiver. You send it
 * a command over I2C, it does the demodulation, the stereo decode and the RDS
 * in silicon, and hands back status bytes and audio on a pair of analogue
 * pins. That is why the driver is short: almost all of the radio is inside the
 * chip.
 *
 * The command set is documented in Silicon Labs AN332. The sequences here
 * follow it, cross-checked against the PU2CLR Arduino library, which is
 * C++ and therefore a reference rather than a dependency.
 *
 * ⚠️ NEVER RUN ON HARDWARE. No Si4735 has been bought, wired or talked to.
 */
#ifndef DECK_TUNER_H
#define DECK_TUNER_H

#include "screens.h"

/* Brings the chip up in FM and tunes to the last-used frequency, or to the
 * bottom of the band if there is none. Returns 0, or negative if the chip did
 * not answer — which on I2C means "nothing is plugged in", and the deck
 * carries on without a radio rather than refusing to boot. */
int deck_tuner_start(void);
int deck_tuner_present(void);

/* --- region ------------------------------------------------------------
 *
 * The band plan, channel step, de-emphasis and RDS/RBDS mode, as one choice.
 *
 * ⚠️ It follows WHERE THE DECK IS DRIVEN, not where the car was built. An
 * imported car receives the stations of the country it is now in. Everything
 * else about fitting a deck to an import — fascia, harness, aerial plug —
 * follows the car's market; this one follows the postcode. docs/VEHICLES.md
 * spells the distinction out because it is the one people get backwards.
 *
 * Stored in NVS, so it survives a reflash and is set once. */
#define DECK_REGION_DEFAULT 1        /* UK — this project's home market */

int         deck_tuner_region_count(void);
const char *deck_tuner_region_name(int i);
int         deck_tuner_region_get(void);
void        deck_tuner_region_set(int i);

void deck_tuner_band(deck_band_t b);
void deck_tuner_tune(int khz);
void deck_tuner_step(int up);        /* one channel spacing */
void deck_tuner_seek(int up);        /* hardware seek to the next station */

/* Copies the current state — frequency, RSSI, stereo flag, RDS — into `r`.
 * Cheap enough to call every frame: it only touches I2C on a slow cadence of
 * its own, because a status poll takes about a millisecond and doing it at
 * 30 fps would spend more time on the bus than on the picture. */
void deck_tuner_poll(deck_radio_t *r);

/* Presets live in NVS with everything else the deck remembers. */
void deck_tuner_preset_recall(int n);   /* 1..DECK_PRESETS */
void deck_tuner_preset_store(int n);

#endif /* DECK_TUNER_H */
