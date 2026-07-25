/* See deck_source.h. NEVER RUN ON HARDWARE. */
#include "deck_source.h"

#include "driver/gpio.h"

#include "deck_diag.h"

/* The 74HC4052's two select inputs.
 *
 * GPIO 2 and 12 are strapping pins, and this is the one job they are safe for.
 * The rule from BUILD.md §3 is that a strapping pin is fine as an OUTPUT and
 * never as a button: at power-on the ESP32 samples them before any of this
 * code runs, and an output is high-impedance at that moment, so the boot sees
 * the internal pulls and not us.
 *
 *   GPIO 12 must read LOW at boot   — internal pull-down, and nothing external
 *                                     drives it; the mux input is high-Z
 *   GPIO 2  must read LOW or float  — same
 *
 * Which means the mux wakes up selecting channel 0 before the firmware
 * touches it. Channel 0 is Bluetooth. If this driver never runs at all, the
 * deck still passes the DAC through, which is the failure mode to want. */
#define PIN_SEL_A 2
#define PIN_SEL_B 12

static deck_source_t s_cur = DECK_SRC_BT;

static const char *NAMES[DECK_SRC_COUNT] = {"BLUETOOTH", "RADIO", "AUX"};

int deck_source_start(deck_source_t initial) {
  const gpio_config_t io = {
      .pin_bit_mask = (1ULL << PIN_SEL_A) | (1ULL << PIN_SEL_B),
      .mode = GPIO_MODE_OUTPUT,
  };
  const esp_err_t err = gpio_config(&io);
  if (err != ESP_OK) {
    deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_DEGRADED, "source mux %d", err);
    return -1;
  }
  deck_source_set(initial);
  return 0;
}

void deck_source_set(deck_source_t s) {
  if (s < 0 || s >= DECK_SRC_COUNT) s = DECK_SRC_BT;
  s_cur = s;
  /* Channel number straight onto the two select lines. The enum order and the
   * mux channel order are the same on purpose — a lookup table here would be
   * one more thing to get out of step with the wiring diagram. */
  gpio_set_level(PIN_SEL_A, (int)s & 1);
  gpio_set_level(PIN_SEL_B, ((int)s >> 1) & 1);
  deck_diag_event(DECK_SUB_AUDIO, "source", "sel=%d name=%s", (int)s, NAMES[s]);
}

deck_source_t deck_source_get(void) { return s_cur; }

deck_source_t deck_source_next(void) {
  deck_source_set((deck_source_t)((s_cur + 1) % DECK_SRC_COUNT));
  return s_cur;
}

const char *deck_source_name(deck_source_t s) {
  return (s >= 0 && s < DECK_SRC_COUNT) ? NAMES[s] : "?";
}
