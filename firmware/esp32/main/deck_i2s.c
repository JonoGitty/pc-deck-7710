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
 */
#include "deck_bt.h"

#include "driver/i2s_std.h"
#include "esp_log.h"
#include "deck_diag.h"

static i2s_chan_handle_t s_tx;

int deck_i2s_start(int bclk, int lrck, int dout, int rate) {
  i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  chan.dma_desc_num = 6;
  chan.dma_frame_num = 240;
  esp_err_t err = i2s_new_channel(&chan, &s_tx, NULL);
  if (err != ESP_OK) { s_tx = NULL; return err; }

  i2s_std_config_t std = {
      .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG((uint32_t)rate),
      .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,
                                                      I2S_SLOT_MODE_STEREO),
      .gpio_cfg = {
          .mclk = I2S_GPIO_UNUSED,
          .bclk = bclk, .ws = lrck, .dout = dout, .din = I2S_GPIO_UNUSED,
          .invert_flags = {0},
      },
  };
  err = i2s_channel_init_std_mode(s_tx, &std);
  if (err == ESP_OK) err = i2s_channel_enable(s_tx);
  if (err != ESP_OK) { s_tx = NULL; return err; }
  return 0;
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
