/* The physical surface: one encoder with a push, six buttons, an ignition
 * sense and a dimmer.
 *
 * Every one of these maps onto an action the PC deck already has bound to a
 * key, which is not a coincidence — it is why the firmware needed no new UI
 * concepts. See docs/CONTROL.md for the action table.
 *
 * Two things here are less obvious than they look.
 *
 * DEBOUNCING IS NOT OPTIONAL AND NOT A DELAY. A mechanical button bounces for
 * a few milliseconds and a car is a vibrating, electrically filthy place. The
 * approach is a periodic sample with a stability counter rather than an
 * interrupt plus a `vTaskDelay`, because delaying inside an ISR is how you get
 * a deck that misses presses when the display is busy.
 *
 * THE ENCODER IS READ AS A QUADRATURE STATE MACHINE, not as "A fell, look at
 * B". The naive version double-counts at detents and drops steps when turned
 * fast, and the symptom — a volume knob that sometimes goes the wrong way — is
 * infuriating and hard to attribute.
 *
 * NEVER RUN ON HARDWARE.
 */
#include "deck_input.h"

#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "deck_diag.h"

/* Pin map. Matches docs/BUILD.md; change both together. Every one of these is
 * an input with a pull-up, so a button shorts to ground and an unconnected
 * pin reads as "not pressed" rather than as noise. */
#define PIN_ENC_A   34
#define PIN_ENC_B   35
#define PIN_ENC_SW  32
#define PIN_BTN_SRC 33
#define PIN_BTN_DISP 25
#define PIN_BTN_BAND 26
#define PIN_BTN_ART  27
#define PIN_BTN_LYR  14
#define PIN_BTN_DEMO 13
#define PIN_IGNITION 39      /* via opto-isolator — never straight from 12 V */
#define PIN_DIMMER   36      /* likewise */

/* GPIO 34-39 are input-only and have NO internal pull-ups on this chip. Wiring
 * a button to one without an external resistor gives a floating input that
 * reads as random presses, which looks exactly like a firmware bug. */
#define NEEDS_EXTERNAL_PULLUP(p) ((p) >= 34)

typedef struct {
  int      pin;
  deck_action_t action;
  uint8_t  stable, count, level;
} btn_t;

static btn_t s_btn[] = {
    {PIN_ENC_SW,   DECK_ACT_MODE_NEXT, 1, 0, 1},
    {PIN_BTN_SRC,  DECK_ACT_SRC,       1, 0, 1},
    {PIN_BTN_DISP, DECK_ACT_MODE_NEXT, 1, 0, 1},
    {PIN_BTN_BAND, DECK_ACT_OCEAN,     1, 0, 1},
    {PIN_BTN_ART,  DECK_ACT_ART,       1, 0, 1},
    {PIN_BTN_LYR,  DECK_ACT_LYRICS,    1, 0, 1},
    {PIN_BTN_DEMO, DECK_ACT_DEMO,      1, 0, 1},
};
#define NBTN (sizeof s_btn / sizeof *s_btn)

static QueueHandle_t s_q;
static uint8_t s_enc_state;
static int8_t  s_enc_accum;

/* Full-step quadrature table. Index is (previous state << 2) | current state;
 * the value is -1, 0 or +1. Invalid transitions — the ones a bouncing contact
 * produces — map to 0 and are simply ignored, which is the whole trick. */
static const int8_t QUAD[16] = {0, -1, 1, 0, 1, 0, 0, -1,
                                -1, 0, 0, 1, 0, 1, -1, 0};

static void poll_task(void *arg) {
  (void)arg;
  int last_ign = -1;
  while (1) {
    /* Encoder. Sampled at 1 kHz, which comfortably outruns a hand. */
    const uint8_t a = gpio_get_level(PIN_ENC_A);
    const uint8_t b = gpio_get_level(PIN_ENC_B);
    const uint8_t st = (uint8_t)((a << 1) | b);
    if (st != s_enc_state) {
      s_enc_accum += QUAD[(s_enc_state << 2) | st];
      s_enc_state = st;
      /* Four transitions per detent on the common 20-detent encoder, so
       * report one step per four and keep the remainder. Reporting every
       * transition makes the knob feel like it has no detents at all. */
      if (s_enc_accum >= 4)  { deck_input_post(DECK_ACT_ENC_CW, 1);  s_enc_accum -= 4; }
      if (s_enc_accum <= -4) { deck_input_post(DECK_ACT_ENC_CCW, 1); s_enc_accum += 4; }
    }

    for (size_t i = 0; i < NBTN; i++) {
      const uint8_t lv = gpio_get_level(s_btn[i].pin);
      if (lv == s_btn[i].level) { s_btn[i].count = 0; continue; }
      /* 25 consecutive contrary samples at 1 kHz = 25 ms of quiet. Longer than
       * any bounce, shorter than any deliberate press. */
      if (++s_btn[i].count >= 25) {
        s_btn[i].count = 0;
        s_btn[i].level = lv;
        if (lv == 0) deck_input_post(s_btn[i].action, 1);   /* active low */
      }
    }

    /* Ignition. The one input that is not a user action: when it drops, the
     * deck has a second or two of held-up supply to save settings and blank
     * the panel, and using it is the difference between a deck that remembers
     * where it was and one that does not. */
    const int ign = gpio_get_level(PIN_IGNITION);
    if (ign != last_ign) {
      last_ign = ign;
      deck_input_post(ign ? DECK_ACT_IGNITION_ON : DECK_ACT_IGNITION_OFF, 1);
      deck_diag_event(DECK_SUB_INPUT, "ignition", "on=%d", ign);
    }

    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

int deck_input_start(void) {
  s_q = xQueueCreate(16, sizeof(deck_event_t));
  if (!s_q) return -1;

  uint64_t mask = 0;
  for (size_t i = 0; i < NBTN; i++) mask |= 1ULL << s_btn[i].pin;
  mask |= (1ULL << PIN_ENC_A) | (1ULL << PIN_ENC_B) |
          (1ULL << PIN_IGNITION) | (1ULL << PIN_DIMMER);

  gpio_config_t io = {
      .pin_bit_mask = mask,
      .mode = GPIO_MODE_INPUT,
      .pull_up_en = GPIO_PULLUP_ENABLE,
  };
  esp_err_t err = gpio_config(&io);
  if (err != ESP_OK) {
    deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_FAILED, "gpio config %d", err);
    return err;
  }

  s_enc_state = (uint8_t)((gpio_get_level(PIN_ENC_A) << 1) | gpio_get_level(PIN_ENC_B));

  if (xTaskCreate(poll_task, "deck_in", 2560, NULL, 6, NULL) != pdPASS) {
    deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_FAILED, "task create");
    return -1;
  }
  deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_OK, "encoder + %u buttons",
                (unsigned)NBTN);
  return 0;
}

void deck_input_post(deck_action_t a, int repeat) {
  const deck_event_t e = {a, repeat};
  if (s_q) xQueueSend(s_q, &e, 0);
}

int deck_input_get(deck_event_t *out) {
  return s_q && xQueueReceive(s_q, out, 0) == pdTRUE;
}
