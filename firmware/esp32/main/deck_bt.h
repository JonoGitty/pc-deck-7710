/* Bluetooth: audio in, metadata in, transport out. See deck_bt.c. */
#ifndef DECK_BT_H
#define DECK_BT_H

#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "meta.h"

/* Brings up the controller, Bluedroid, A2DP sink and both AVRCP roles, and
 * makes the deck discoverable under `name`. `meta` is filled in from the
 * phone and must outlive the call. */
int  deck_bt_start(deck_meta_t *meta, const char *name);

/* Playhead, interpolated between the roughly once-a-second AVRCP updates.
 * Lyrics need this every frame or lines land visibly late. */
void deck_bt_position(double *pos, double *dur);

/* ESP_AVRC_PT_CMD_PLAY / PAUSE / FORWARD / BACKWARD — the deck's buttons and
 * the car's steering-wheel controls both end up here. */
void deck_bt_send_key(uint8_t passthrough_cmd);

void deck_bt_set_discoverable(int on);

/* Audio out. Separated from the Bluetooth file so a build with no DAC fitted
 * is a link-time swap rather than an #ifdef through the callback. */
int  deck_i2s_start(int bclk, int lrck, int dout, int rate);
void deck_i2s_write(const uint8_t *pcm, uint32_t len);

/* The microphone shares the DAC's clocks — full duplex on one controller — so
 * it needs only a data-in pin. Set it before a call is ever taken; -1, the
 * default, means no microphone is fitted and the call path stays mute rather
 * than failing. See docs/CALLING.md. */
void     deck_i2s_set_mic_pin(int din);

/* Reshape the channel: `call` adds the receive half, `rate` is 8000 or 16000
 * for a call and 44100 for music. Cheap and idempotent when already correct. */
int      deck_i2s_mode(int call, int rate);

uint32_t deck_i2s_mic_read(uint8_t *pcm, uint32_t len);
void     deck_i2s_call_write(const uint8_t *pcm, uint32_t len);

#endif /* DECK_BT_H */
