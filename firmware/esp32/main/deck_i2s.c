/* Audio out: the decoded A2DP stream to an I2S DAC.
 *
 * Deliberately its own file. The deck's job is the display, and a build with
 * no DAC fitted — the common bench case, and the case where the deck feeds an
 * existing amplifier over line-out — should not need the audio path compiled
 * differently. Everything here degrades to a no-op if the bus never came up.
 *
 * A word on why this is not "just" a write. The A2DP callback runs on the
 * Bluedroid task; if the I2S write blocks waiting for DMA space, Bluetooth
 * stalls and the music stutters. So the write is bounded: it waits a few
 * milliseconds for room and then drops the buffer. Dropping audio is bad;
 * stalling the Bluetooth task is worse, because it drops audio *and* takes
 * the connection down with it.
 *
 * THE MICROPHONE SHARES THIS PERIPHERAL, AND THAT IS THE WHOLE TRICK
 *
 * A call needs audio in as well as out. The ESP32's I2S runs FULL DUPLEX on
 * one controller — transmit and receive sharing the bit clock and the word
 * select — so the microphone costs exactly one extra wire, its data line, and
 * no extra clock pins. On a build with six GPIOs left that is the difference
 * between hands-free calling being possible and not. See docs/CALLING.md.
 *
 * The consequence is that the mic and the DAC always run at the same rate.
 * During a call that is what you want anyway — both ends of a conversation
 * are 8 or 16 kHz — and the music is paused, so nothing else cares.
 */
#include "deck_bt.h"

#include "driver/i2s_std.h"
#include "esp_log.h"
#include "deck_diag.h"

static i2s_chan_handle_t s_tx, s_rx;
static int s_bclk, s_lrck, s_dout, s_din = -1;
static int s_rate;

static void teardown(void) {
  if (s_tx) { i2s_channel_disable(s_tx); i2s_del_channel(s_tx); s_tx = NULL; }
  if (s_rx) { i2s_channel_disable(s_rx); i2s_del_channel(s_rx); s_rx = NULL; }
}

/* Build the channel pair at `rate`. `duplex` adds the RX half, which needs a
 * data-in pin; without one it is transmit only and the mic calls no-op. */
static int bring_up(int rate, int duplex) {
  teardown();
  s_rate = rate;

  i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  chan.dma_desc_num = 6;
  chan.dma_frame_num = 240;
  const int want_rx = duplex && s_din >= 0;
  esp_err_t err = i2s_new_channel(&chan, &s_tx, want_rx ? &s_rx : NULL);
  if (err != ESP_OK) { s_tx = NULL; s_rx = NULL; return err; }

  i2s_std_config_t std = {
      .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG((uint32_t)rate),
      .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,
                                                      I2S_SLOT_MODE_STEREO),
      .gpio_cfg = {
          .mclk = I2S_GPIO_UNUSED,
          .bclk = s_bclk, .ws = s_lrck, .dout = s_dout,
          .din = want_rx ? s_din : I2S_GPIO_UNUSED,
          .invert_flags = {0},
      },
  };
  err = i2s_channel_init_std_mode(s_tx, &std);
  if (err == ESP_OK) err = i2s_channel_enable(s_tx);
  if (err == ESP_OK && s_rx) {
    err = i2s_channel_init_std_mode(s_rx, &std);
    if (err == ESP_OK) err = i2s_channel_enable(s_rx);
  }
  if (err != ESP_OK) { teardown(); return err; }
  return 0;
}

int deck_i2s_start(int bclk, int lrck, int dout, int rate) {
  s_bclk = bclk; s_lrck = lrck; s_dout = dout;
  return bring_up(rate, 0);
}

void deck_i2s_set_mic_pin(int din) { s_din = din; }

int deck_i2s_mode(int call, int rate) {
  /* Nothing to do if the channel is already the shape we want. Rebuilding it
   * needlessly puts an audible gap in the music every time something asks. */
  if (!!s_rx == !!call && s_rate == rate) return 0;
  return bring_up(rate, call);
}

/* Microphone, for the call path. Returns how many bytes were actually read,
 * which at the start of a call is less than asked for because the RX ring has
 * not filled yet — the caller passes that straight on to Bluetooth, which is
 * happy with a short frame and unhappy with a blocking one. */
uint32_t deck_i2s_mic_read(uint8_t *pcm, uint32_t len) {
  if (!s_rx) return 0;
  size_t got = 0;
  if (i2s_channel_read(s_rx, pcm, len, &got, pdMS_TO_TICKS(10)) != ESP_OK)
    return 0;
  return (uint32_t)got;
}

/* Far-end speech, out through the same DAC the music uses. Separate from
 * deck_i2s_write only so a frame dropped during a call is counted separately
 * from one dropped during music — different causes, and conflating them makes
 * the log useless. */
void deck_i2s_call_write(const uint8_t *pcm, uint32_t len) {
  if (!s_tx) return;
  size_t wrote = 0;
  if (i2s_channel_write(s_tx, pcm, len, &wrote, pdMS_TO_TICKS(20)) != ESP_OK ||
      wrote != len) {
    static uint32_t dropped;
    if (++dropped % 100 == 1)
      deck_diag_event(DECK_SUB_AUDIO, "call-drop", "count=%u", (unsigned)dropped);
  }
}

void deck_i2s_write(const uint8_t *pcm, uint32_t len) {
  if (!s_tx) return;
  size_t wrote = 0;
  /* 20 ms is about two DMA buffers: long enough to ride out a scheduling
   * hiccup, short enough that a genuinely stuck DAC cannot take Bluetooth
   * down with it. */
  if (i2s_channel_write(s_tx, pcm, len, &wrote, pdMS_TO_TICKS(20)) != ESP_OK ||
      wrote != len) {
    static uint32_t dropped;
    if (++dropped % 100 == 1)
      deck_diag_event(DECK_SUB_AUDIO, "i2s-drop", "count=%u", (unsigned)dropped);
  }
}
