/* The physical surface: one encoder with a push, the buttons — three on
 * GPIOs or six on a resistor ladder — an ignition sense and a dimmer.
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

#include "deck_adc.h"
#include "deck_diag.h"

/* Pin map. Matches docs/BUILD.md; change both together.
 *
 * THE PIN BUDGET, BECAUSE IT IS TIGHTER THAN IT LOOKS
 *
 * On an ESP32-WROVER-E, GPIO 6-11 are the SPI flash and **GPIO 16 and 17 are
 * the PSRAM** — the datasheet says so, and the PSRAM is the entire reason this
 * build uses a WROVER rather than a WROOM. GPIO 1 and 3 are the serial console
 * you read the logs on. GPIO 0, 2, 12 and 15 are strapping pins: fine as
 * outputs, never as buttons, because a button held at power-on changes the
 * boot mode. GPIO 34-39 are input-only with no internal pull-ups.
 *
 * What is left for something a human presses is exactly six pins:
 *
 *     13  14  21  27  32  33
 *
 * The encoder takes three of them. So a plain-GPIO build gets three buttons,
 * not six, and the sixth version of this pin map — which had them — could not
 * have worked on the recommended module. The fix is not to shuffle pins; there
 * is nowhere to shuffle to.
 *
 * SO THE FULL PANEL IS A RESISTOR LADDER ON ONE ADC PIN
 *
 * Six buttons, six resistors, one wire. Identical in principle to the
 * steering-wheel input in deck_swc.c — which is the point: it is the same
 * technique a car's wheel uses, and it is how you wire the front panel of a
 * gutted donor head unit, whose buttons are already a matrix on a flexi you
 * would otherwise have to reverse-engineer.
 *
 * Both paths are compiled in and the ladder is detected at boot, so a bench
 * build with three buttons and a car build with a full fascia run the same
 * binary.
 *
 * AND THE LADDER IS WHAT PAYS FOR THE RADIO
 *
 * Those same three pins — 13, 32, 33 — are the only ones left for the Si4735's
 * I2C bus and its reset line. There is no third option: on this module the
 * tuner and the discrete buttons want the same three holes.
 *
 * So it is one or the other, decided by whether a ladder is fitted, which is
 * why the probe below happens BEFORE anything is configured rather than after.
 * With a ladder, the six-button fascia is on GPIO 35 and 13/32/33 are left
 * alone for deck_tuner.c to claim. Without one, the three buttons are wired
 * there and the radio cannot be, and deck_main.c does not start the tuner.
 *
 * Getting this wrong is not subtle-but-survivable. deck_tuner drives GPIO 13
 * as an output to reset the chip; configuring it here as a pulled-up input
 * means the reset pulse goes nowhere, the tuner probe fails, and the deck
 * reports no radio fitted while one is sitting on the bus. */
#define PIN_ENC_A    21
#define PIN_ENC_B    27
#define PIN_ENC_SW   14
#define PIN_BTN_SRC  33
#define PIN_BTN_DISP 32
#define PIN_BTN_ART  13
#define PIN_IGNITION 39      /* via opto-isolator — never straight from 12 V */
#define PIN_DIMMER   36      /* likewise */

/* GPIO 34-39 are input-only and have NO internal pull-ups on this chip. The
 * ignition sense, the dimmer, the steering-wheel line and the button ladder
 * all live there, and all four are driven by something external — an
 * opto-isolator, an interface box, or the ladder's own divider — so none of
 * them floats. Nothing is wired directly to one of those pins as a bare
 * switch: a floating input reads as random presses and looks exactly like a
 * firmware bug. */

typedef struct {
  int      pin;
  deck_action_t action;
  uint8_t  stable, count, level;
  int64_t  down_at;         /* for long-press; 0 when up */
} btn_t;

/* The encoder's own switch is first and always present — it is on GPIO 14,
 * which nothing else wants. The three after it share their pins with the
 * tuner, and s_nbtn drops to 1 when a ladder is fitted so they are never
 * configured, never polled, and never fire on I2C traffic. */
static btn_t s_btn[] = {
    {PIN_ENC_SW,   DECK_ACT_MODE_NEXT, 1, 0, 1, 0},
    {PIN_BTN_SRC,  DECK_ACT_SRC,       1, 0, 1, 0},
    {PIN_BTN_DISP, DECK_ACT_MODE_NEXT, 1, 0, 1, 0},
    {PIN_BTN_ART,  DECK_ACT_ART,       1, 0, 1, 0},
};
#define NBTN_ALL  (sizeof s_btn / sizeof *s_btn)
#define NBTN_ENC  1                  /* just the encoder push, when shared */

static size_t s_nbtn = NBTN_ALL;

/* --- the button ladder --------------------------------------------------
 *
 *   3V3 ── 10k ──┬── GPIO 35 (ADC1_CH7)
 *                │
 *                ├── [SRC]    ── 0R    ── GND
 *                ├── [DISP]   ── 1k    ── GND
 *                ├── [BAND]   ── 2k2   ── GND
 *                ├── [ART]    ── 4k7   ── GND
 *                ├── [LYRICS] ── 10k   ── GND
 *                └── [DEMO]   ── 18k   ── GND
 *
 * The values are not arbitrary. Each is far enough from its neighbours that
 * the gap survives resistor tolerance, and all of them sit below about
 * 2.2 V — the original ESP32's ADC is badly non-linear above roughly 2.5 V
 * and saturates before the rail, so a ladder that used the top of the range
 * would merge its highest buttons with "nothing pressed".
 *
 * Unlike the steering-wheel input this does NOT need to be learned, because
 * you built it: the resistors are specified above, so the expected voltages
 * are known. Learning exists over there because a car's values are whatever
 * the interface box was configured for, and there is nothing to look up. */
#define LADDER_ADC_CHAN ADC_CHANNEL_7      /* GPIO 35 */
#define LADDER_MATCH_MV 110                /* smallest gap is 295 mV */
#define LADDER_IDLE_MV  2700               /* above this, nothing is pressed */

static const struct { int mv; deck_action_t act; } LADDER[] = {
    {   0, DECK_ACT_SRC},
    { 300, DECK_ACT_MODE_NEXT},
    { 595, DECK_ACT_OCEAN},
    {1055, DECK_ACT_ART},
    {1650, DECK_ACT_LYRICS},
    {2121, DECK_ACT_DEMO},
};
#define NLADDER ((int)(sizeof LADDER / sizeof *LADDER))

static int s_have_ladder;
static int s_ladder_idx = -1, s_ladder_count;
static int64_t s_ladder_down_at;

static int ladder_mv(void) { return deck_adc1_mv(LADDER_ADC_CHAN); }

/* Which rung, or -1. A reading that lands between rungs is deliberately
 * nothing: two buttons pressed together put the resistors in parallel and
 * produce a value in one of the gaps, so a chord is ignored rather than
 * silently read as some third button. */
static int ladder_lookup(int mv) {
  if (mv < 0 || mv >= LADDER_IDLE_MV) return -1;
  for (int i = 0; i < NLADDER; i++) {
    const int d = mv - LADDER[i].mv;
    if (d > -LADDER_MATCH_MV && d < LADDER_MATCH_MV) return i;
  }
  return -1;
}

/* Long presses, and only two of them. A head unit whose every button does
 * something different when held is one nobody can use without the manual;
 * these two are setup actions you perform once. */
#define LONG_PRESS_US (5 * 1000000LL)

static QueueHandle_t s_q;
static uint8_t s_enc_state;
static int8_t  s_enc_accum;
static int     s_ladder_div;

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

    for (size_t i = 0; i < s_nbtn; i++) {
      const uint8_t lv = gpio_get_level(s_btn[i].pin);
      if (lv == s_btn[i].level) { s_btn[i].count = 0; continue; }
      /* 25 consecutive contrary samples at 1 kHz = 25 ms of quiet. Longer than
       * any bounce, shorter than any deliberate press. */
      if (++s_btn[i].count >= 25) {
        s_btn[i].count = 0;
        s_btn[i].level = lv;
        if (lv == 0) {
          s_btn[i].down_at = esp_timer_get_time();
          deck_input_post(s_btn[i].action, 1);              /* active low */
        } else {
          s_btn[i].down_at = 0;
        }
      }
    }

    /* The ladder, if one is fitted. Sampled every 10th pass rather than every
     * pass: an ADC conversion is far more expensive than reading a GPIO, and
     * 100 Hz is still ten times faster than anybody presses a button. */
    if (s_have_ladder && (++s_ladder_div >= 10)) {
      s_ladder_div = 0;
      const int idx = ladder_lookup(ladder_mv());
      if (idx != s_ladder_idx) {
        if (++s_ladder_count >= 4) {          /* 40 ms of agreement */
          s_ladder_count = 0;
          s_ladder_idx = idx;
          if (idx >= 0) {
            s_ladder_down_at = esp_timer_get_time();
            deck_input_post(LADDER[idx].act, 1);
          } else {
            s_ladder_down_at = 0;
          }
        }
      } else {
        s_ladder_count = 0;
      }
    }

    /* Long-press: SRC opens the steering-wheel learning wizard, DISP the
     * self-test screen. Fired once, by zeroing the timestamp, so holding does
     * not re-enter the wizard every second. */
    for (size_t i = 0; i < s_nbtn; i++) {
      if (!s_btn[i].down_at) continue;
      if (esp_timer_get_time() - s_btn[i].down_at < LONG_PRESS_US) continue;
      s_btn[i].down_at = 0;
      if (s_btn[i].pin == PIN_BTN_SRC)       deck_input_post(DECK_ACT_SWC_LEARN, 1);
      else if (s_btn[i].pin == PIN_BTN_DISP) deck_input_post(DECK_ACT_SELFTEST, 1);
    }

    /* ...and the same two from the ladder, so a donor fascia can reach the
     * setup screens without also needing a discrete button soldered on. */
    if (s_ladder_down_at &&
        esp_timer_get_time() - s_ladder_down_at >= LONG_PRESS_US) {
      const deck_action_t a = LADDER[s_ladder_idx].act;
      s_ladder_down_at = 0;
      if (a == DECK_ACT_SRC)            deck_input_post(DECK_ACT_SWC_LEARN, 1);
      else if (a == DECK_ACT_MODE_NEXT) deck_input_post(DECK_ACT_SELFTEST, 1);
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

  /* Is a ladder fitted? With no divider on the pin the 10k pull-up is absent
   * too, so the input floats and reads as anything at all. With one fitted and
   * nothing pressed it sits at the top of the range. So: sample a few times,
   * and only believe in a ladder if every reading agrees it is idle. A
   * floating pin will not do that twice in a row, which is exactly the
   * property being tested for.
   *
   * Detecting rather than configuring, because the alternative is a build flag
   * that half the people who need it will not know exists, and whose symptom
   * when wrong is a deck with dead buttons.
   *
   * FIRST, before a single pin is configured. The answer decides whether the
   * three shared pins belong to this file or to deck_tuner.c, and touching
   * them and then changing our mind would leave GPIO 13 pulled up underneath
   * the tuner's reset line. */
  if (deck_adc1_channel(LADDER_ADC_CHAN) == 0) {
    int idle = 1;
    for (int i = 0; i < 8; i++)
      if (ladder_mv() < LADDER_IDLE_MV) idle = 0;
    s_have_ladder = idle;
  }
  s_nbtn = s_have_ladder ? NBTN_ENC : NBTN_ALL;

  uint64_t mask = 0;
  for (size_t i = 0; i < s_nbtn; i++) mask |= 1ULL << s_btn[i].pin;
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
  deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_OK, "encoder + %u button%s%s",
                (unsigned)s_nbtn, s_nbtn == 1 ? "" : "s",
                s_have_ladder ? " + 6-way ladder" : "");
  deck_diag_event(DECK_SUB_INPUT, "ladder", "fitted=%d buttons=%u",
                  s_have_ladder, (unsigned)s_nbtn);
  return 0;
}

/* deck_main.c asks this before starting the tuner: a ladder means GPIO 13, 32
 * and 33 were left alone and the Si4735 may have them. */
int deck_input_has_ladder(void) { return s_have_ladder; }

void deck_input_post(deck_action_t a, int repeat) {
  const deck_event_t e = {a, repeat};
  if (s_q) xQueueSend(s_q, &e, 0);
}

int deck_input_get(deck_event_t *out) {
  return s_q && xQueueReceive(s_q, out, 0) == pdTRUE;
}
