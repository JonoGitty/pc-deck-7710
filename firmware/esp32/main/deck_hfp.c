/* See deck_hfp.h. NEVER RUN ON HARDWARE.
 *
 * The whole file is a translation layer: Bluetooth events in, a deck_call_t
 * out. It deliberately holds no opinion about what the panel does with it.
 *
 * WHY THE STATE IS REBUILT RATHER THAN TOGGLED
 *
 * HFP reports two indicators — `call` (is there a call up) and `call_setup`
 * (is one being established, incoming or outgoing) — and events for them
 * arrive in an order that varies by phone. Tracking a state machine by
 * reacting to each transition means guessing an order, and the guess is wrong
 * on somebody's Android.
 *
 * So both indicators are stored as the AG last reported them and the screen
 * state is *derived* from the pair, every time either changes. There is one
 * table, it is total, and no event ordering can put it somewhere invalid.
 *
 *      call  setup   ->  state
 *      ----  -----       -----
 *       0      0         idle (or ENDED, briefly, if we were mid-call)
 *       0      1         INCOMING
 *       0      2,3       OUTGOING
 *       1      any       ACTIVE
 */
#include "deck_hfp.h"

#include <string.h>

#include "esp_hf_client_api.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#include "deck_bt.h"
#include "deck_diag.h"

/* How long CALL ENDED stays up before the deck goes back to the music. Long
 * enough to read the duration, short enough not to be in the way. */
#define ENDED_MS 2500

static SemaphoreHandle_t s_lock;
static deck_call_t s_call;
static int      s_ind_call, s_ind_setup;
static int64_t  s_started_us, s_ended_at_us;
static uint8_t  s_mic;

static void lock(void)   { if (s_lock) xSemaphoreTake(s_lock, portMAX_DELAY); }
static void unlock(void) { if (s_lock) xSemaphoreGive(s_lock); }

/* The whole state machine, in one place, derived from both indicators. */
static void derive(void) {
  const deck_call_state_t was = s_call.state;
  deck_call_state_t now;

  if (s_ind_call) {
    now = DECK_CALL_ACTIVE;
  } else if (s_ind_setup == 1) {
    now = DECK_CALL_INCOMING;
  } else if (s_ind_setup == 2 || s_ind_setup == 3) {
    now = DECK_CALL_OUTGOING;
  } else {
    now = (was == DECK_CALL_ACTIVE || was == DECK_CALL_OUTGOING ||
           was == DECK_CALL_INCOMING)
              ? DECK_CALL_ENDED
              : DECK_CALL_IDLE;
  }
  if (now == was) return;

  if (now == DECK_CALL_ACTIVE && was != DECK_CALL_ACTIVE)
    s_started_us = esp_timer_get_time();
  if (now == DECK_CALL_ENDED) s_ended_at_us = esp_timer_get_time();
  if (now == DECK_CALL_IDLE) {
    s_call.name[0] = s_call.number[0] = 0;
    s_call.secs = 0;
  }
  s_call.state = now;
  deck_diag_event(DECK_SUB_BT, "call", "state=%d call=%d setup=%d",
                  (int)now, s_ind_call, s_ind_setup);
}

static void cb(esp_hf_client_cb_event_t ev, esp_hf_client_cb_param_t *p) {
  lock();
  switch (ev) {
  case ESP_HF_CLIENT_CONNECTION_STATE_EVT:
    deck_diag_event(DECK_SUB_BT, "hfp", "conn=%d", p->conn_stat.state);
    if (p->conn_stat.state == ESP_HF_CLIENT_CONNECTION_STATE_DISCONNECTED) {
      /* A phone that walks away mid-call leaves both indicators stale and the
       * deck showing a call that no longer exists. Clear them rather than
       * waiting for an update that is not coming. */
      s_ind_call = s_ind_setup = 0;
      derive();
    }
    break;

  case ESP_HF_CLIENT_AUDIO_STATE_EVT:
    /* Worth logging which codec was negotiated: mSBC is 16 kHz wideband and
     * CVSD is 8 kHz, and "the calls sound like 2005" has exactly one cause. */
    deck_diag_event(DECK_SUB_BT, "hfp-audio", "state=%d msbc=%d",
                    p->audio_stat.state,
                    p->audio_stat.state == ESP_HF_CLIENT_AUDIO_STATE_CONNECTED_MSBC);
    break;

  case ESP_HF_CLIENT_CIND_CALL_EVT:
    s_ind_call = (int)p->call.status;
    derive();
    break;

  case ESP_HF_CLIENT_CIND_CALL_SETUP_EVT:
    s_ind_setup = (int)p->call_setup.status;
    derive();
    break;

  case ESP_HF_CLIENT_CLIP_EVT:
    /* Caller ID. Numbers only — the AG sends a name only if the phone has one
     * and many do not, so the screen falls back to the number and then to
     * WITHHELD, in that order. */
    if (p->clip.number)
      snprintf(s_call.number, sizeof s_call.number, "%s", p->clip.number);
    break;

  case ESP_HF_CLIENT_RING_IND_EVT:
    /* Nothing to do — the indicators already say INCOMING. This exists so the
     * event is visibly handled rather than silently ignored, which is the
     * difference between "we decided" and "we forgot". */
    break;

  default:
    break;
  }
  unlock();
}

/* --- audio, over HCI ----------------------------------------------------
 *
 * With Voice-over-HCI the speech frames pass through software, which is why
 * the microphone meter on the call screen is possible at all. The deck's own
 * I2S carries them: the mic into `outgoing`, the far end out of `incoming`.
 *
 * ⚠️ These two callbacks are the least-tested code in this repository, which
 * is saying something. They are structurally right — the signatures, the
 * lengths and the peak-hold are — and whether the timing survives contact
 * with a real SCO link is unknown. */
static uint32_t on_outgoing(uint8_t *buf, uint32_t len) {
  /* deck_i2s owns the microphone; it hands over whatever it has captured and
   * returns how much, which may be less than asked for at the start of a call
   * before the RX ring has filled. */
  const uint32_t got = deck_i2s_mic_read(buf, len);

  /* Peak of this frame, for the meter. Samples are signed 16-bit; the meter
   * wants 0..255 and wants to move like a level, so the peak is held and
   * decayed rather than averaged — an average of speech sits near zero and
   * the bar would barely twitch. */
  int16_t peak = 0;
  for (uint32_t i = 0; i + 1 < got; i += 2) {
    int16_t v = (int16_t)(buf[i] | (buf[i + 1] << 8));
    if (v < 0) v = (int16_t)-v;
    if (v > peak) peak = v;
  }
  const uint8_t lvl = (uint8_t)(peak >> 7);
  s_mic = lvl > s_mic ? lvl : (uint8_t)(s_mic - (s_mic >> 3));
  return got;
}

static void on_incoming(const uint8_t *buf, uint32_t len) {
  deck_i2s_call_write(buf, len);
}

/* --- public ------------------------------------------------------------- */
int deck_hfp_start(void) {
  s_lock = xSemaphoreCreateMutex();
  if (!s_lock) return -1;
  memset(&s_call, 0, sizeof s_call);

  esp_err_t err = esp_hf_client_register_callback(cb);
  if (err) {
    deck_diag_set(DECK_SUB_BT, DECK_HEALTH_DEGRADED, "hfp cb %d", err);
    return err;
  }
  if ((err = esp_hf_client_init())) {
    deck_diag_set(DECK_SUB_BT, DECK_HEALTH_DEGRADED, "hfp init %d", err);
    return err;
  }
  esp_hf_client_register_data_callback(on_incoming, on_outgoing);
  deck_diag_event(DECK_SUB_BT, "hfp", "started");
  return 0;
}

void deck_hfp_poll(deck_call_t *c) {
  lock();
  if (s_call.state == DECK_CALL_ACTIVE)
    s_call.secs = (int)((esp_timer_get_time() - s_started_us) / 1000000);
  else if (s_call.state == DECK_CALL_ENDED &&
           esp_timer_get_time() - s_ended_at_us > (int64_t)ENDED_MS * 1000) {
    s_call.state = DECK_CALL_IDLE;
    s_call.name[0] = s_call.number[0] = 0;
    s_call.secs = 0;
  }
  s_call.mic = s_call.state == DECK_CALL_ACTIVE ? s_mic : 0;
  *c = s_call;
  unlock();
}

void deck_hfp_answer(void) {
  lock();
  const int inc = s_call.state == DECK_CALL_INCOMING;
  unlock();
  if (inc) esp_hf_client_answer_call();
}

void deck_hfp_reject(void) {
  lock();
  const int busy = s_call.state != DECK_CALL_IDLE &&
                   s_call.state != DECK_CALL_ENDED;
  unlock();
  /* One function for both: AT+CHUP rejects an incoming call and hangs up an
   * active one, and the deck deliberately puts both on the same button —
   * "make this stop" is one intention, not two. */
  if (busy) esp_hf_client_reject_call();
}

void deck_hfp_redial(void) { esp_hf_client_dial(NULL); }

int deck_hfp_busy(void) {
  lock();
  const int b = s_call.state != DECK_CALL_IDLE;
  unlock();
  return b;
}
