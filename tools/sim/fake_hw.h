/* The other side of the fake SDK: models of the parts, and a trace.
 *
 * See idf/README.md for the line this draws and why. In short: the drivers are
 * compiled unmodified and this is what they find at the end of the bus.
 *
 * EVERYTHING INTERESTING IS A TRACE LINE. The harness prints one line per
 * event — an I2C transfer decoded into what it meant, a GPIO edge, an NVS
 * write, a call-state change — with a virtual timestamp, and
 * `test_drivers.py` asserts on that. Asserting on a printed trace rather than
 * on C internals keeps the checks readable and keeps them honest: they can
 * only see what the driver actually did to the world.
 */
#ifndef FAKE_HW_H
#define FAKE_HW_H

#include <stdint.h>

#include "freertos/semphr.h"   /* for sim_sem_imbalance() */

/* --- the virtual clock -------------------------------------------------- */
void    sim_clock_reset(void);
void    sim_advance_ms(int ms);      /* the harness's own hand on the clock */
int64_t sim_now_us(void);

/* --- trace -------------------------------------------------------------- */
void sim_trace(const char *fmt, ...);
void sim_scenario(const char *name);  /* a header line, and resets counters */

/* --- what is plugged in ------------------------------------------------- */
/* The point of these: a build with no tuner and no audio processor is a
 * perfectly ordinary build, and "the deck copes" is a thing to test rather
 * than assume. Call before deck_*_start(). */
typedef enum {
  SIM_TUNER_NONE = 0,      /* nothing answers on either address */
  SIM_TUNER_AT_11,         /* SEN low  — the common module */
  SIM_TUNER_AT_63,         /* SEN high — so the probe has to try twice */
} sim_tuner_fit_t;

void sim_fit_tuner(sim_tuner_fit_t where);
void sim_fit_audioproc(int fitted);

/* Reset every model and the bus, so scenarios cannot leak into each other.
 * Also re-arms the drivers' own statics via the reset hooks below. */
void sim_hw_reset(void);

/* --- the Si4735 model --------------------------------------------------- */
/* A hardware seek moves the chip without telling the driver, which is the one
 * behaviour that makes the read-back path in deck_tuner_poll() necessary. */
void sim_si4735_seek_lands_on(int khz);

/* Signal quality the model reports, so the screen's RSSI has a source. */
void sim_si4735_signal(int rssi, int stereo);

/* Feed one RDS group as the four 16-bit blocks. The driver reads them out of
 * a 13-byte FM_RDS_STATUS response, and building that by hand in the test
 * would be testing the test. */
void sim_si4735_rds(uint16_t a, uint16_t b, uint16_t c, uint16_t d);

/* What the model saw, for assertions that are awkward to phrase as trace
 * greps. Frequency is in kHz, in whichever band the chip was last put in. */
int sim_si4735_freq_khz(void);
int sim_si4735_powered(void);

/* --- the HFP audio gateway (a scripted phone) --------------------------- */
void sim_hfp_connect(int slc);
void sim_hfp_disconnect(void);
void sim_hfp_indicator_call(int v);
void sim_hfp_indicator_setup(int v);
void sim_hfp_clip(const char *number);
void sim_hfp_ring(void);
void sim_hfp_audio(int state);

/* Counts of the AT commands the deck sent, which is the only externally
 * visible consequence of answer/reject/redial. */
int sim_hfp_answers(void);
int sim_hfp_rejects(void);
int sim_hfp_dials(void);

#endif /* FAKE_HW_H */
