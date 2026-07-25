/* See deck_adc.h for why this file exists at all. NEVER RUN ON HARDWARE. */
#include "deck_adc.h"

#include "deck_diag.h"

static adc_oneshot_unit_handle_t s_adc1;
static int s_tried;

adc_oneshot_unit_handle_t deck_adc1(void) {
  if (!s_tried) {
    s_tried = 1;
    adc_oneshot_unit_init_cfg_t unit = {.unit_id = ADC_UNIT_1};
    if (adc_oneshot_new_unit(&unit, &s_adc1) != ESP_OK) {
      s_adc1 = NULL;
      deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_DEGRADED, "no ADC1");
    }
  }
  return s_adc1;
}

int deck_adc1_channel(adc_channel_t chan) {
  adc_oneshot_unit_handle_t h = deck_adc1();
  if (!h) return -1;
  /* Widest attenuation. Both users need a divider that swings nearly rail to
   * rail, and clipping the top would merge the highest resistance on the
   * ladder with "nothing pressed at all". */
  adc_oneshot_chan_cfg_t cfg = {.bitwidth = ADC_BITWIDTH_12,
                                .atten = ADC_ATTEN_DB_12};
  return adc_oneshot_config_channel(h, chan, &cfg) == ESP_OK ? 0 : -1;
}

int deck_adc1_mv(adc_channel_t chan) {
  int raw = 0;
  adc_oneshot_unit_handle_t h = deck_adc1();
  if (!h) return -1;
  if (adc_oneshot_read(h, chan, &raw) != ESP_OK) return -1;
  return raw * 3300 / 4095;
}
