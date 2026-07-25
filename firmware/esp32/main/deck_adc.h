/* One ADC1 handle, shared.
 *
 * Two things read ADC1: the steering-wheel input on GPIO 34 and the button
 * ladder on GPIO 35. The oneshot driver allows exactly one handle per unit and
 * returns ESP_ERR_INVALID_STATE for the second caller — so whichever of them
 * started second would come up dead, and the symptom would be a working
 * steering wheel and a dead front panel, or the reverse depending on boot
 * order. That is a horrible bug to own.
 *
 * So neither of them creates the unit. This does, once, on first ask.
 */
#ifndef DECK_ADC_H
#define DECK_ADC_H

#include "esp_adc/adc_oneshot.h"

/* The shared ADC1 handle, or NULL if the unit could not be created. */
adc_oneshot_unit_handle_t deck_adc1(void);

/* Configure a channel on it: 12-bit, widest attenuation. Both users want the
 * same settings, and a resistor ladder read at the wrong attenuation looks
 * like a ladder with the wrong resistors in it. */
int deck_adc1_channel(adc_channel_t chan);

/* A reading in nominal millivolts, or -1. Raw counts scaled linearly rather
 * than corrected against the eFuse curve: both users learn or specify their
 * thresholds on this same scale, so a constant error cancels, where a
 * per-chip calibration would make a learned map non-portable. */
int deck_adc1_mv(adc_channel_t chan);

#endif /* DECK_ADC_H */
