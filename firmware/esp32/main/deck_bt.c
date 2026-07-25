/* Bluetooth: audio in, metadata in, transport out.
 *
 * The deck is an A2DP *sink*. Your phone sees it as a pair of speakers, picks
 * it in the normal Bluetooth menu, and plays to it — no app, no account, no
 * pairing code. That is the whole user story, and everything below exists to
 * make those three sentences true.
 *
 * Three profiles, doing three jobs:
 *
 *   A2DP sink    the audio itself, SBC-decoded by the stack. The PCM lands in
 *                a callback, which forwards it to two places: the I2S DAC so
 *                you can hear it, and the analyser so the bars move. The
 *                analysis tap is *before* the DAC, which is why the display
 *                matches what is playing rather than what a microphone hears.
 *
 *   AVRCP CT     the deck as controller: it asks the phone for title, artist,
 *                album and position, and gets told when they change. This is
 *                what puts a track name on the glass without an app.
 *
 *   AVRCP TG     the deck as target: the phone's lock screen and the car's
 *                steering wheel controls send play/pause/next here.
 *
 * WHY THE ORIGINAL ESP32. A2DP is Bluetooth Classic. The S3, C3 and C6 are
 * BLE-only, so none of them can be an audio sink at all — Espressif closed the
 * request to add it "Won't Do". This is the single hardware decision the whole
 * build hangs off; see docs/HARDWARE.md.
 *
 * NEVER RUN ON HARDWARE.
 */
#include "deck_bt.h"

#include <string.h>

#include "esp_a2dp_api.h"
#include "esp_avrc_api.h"
#include "esp_bt.h"
#include "esp_bt_device.h"
#include "esp_bt_main.h"
#include "esp_gap_bt_api.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "deck_audio.h"
#include "deck_diag.h"
#include "text.h"

static const char *TAG = "deck.bt";

static deck_meta_t *s_meta;
static SemaphoreHandle_t s_lock;
static uint8_t s_tl;                       /* AVRCP transaction label */
static int64_t s_pos_at_us;
static double  s_pos_base;

/* Metadata arrives as UTF-8 of arbitrary length and the core wants folded
 * ASCII that fits the ROM. Folding once here rather than every frame is the
 * same split the PC deck makes. */
static void set_str(char *dst, size_t cap, const uint8_t *src) {
  if (!src) return;
  xSemaphoreTake(s_lock, portMAX_DELAY);
  deck_fold((const char *)src, dst, cap);
  xSemaphoreGive(s_lock);
}

void deck_bt_position(double *pos, double *dur) {
  xSemaphoreTake(s_lock, portMAX_DELAY);
  /* Interpolate between updates. AVRCP reports position about once a second;
   * lyrics need it every frame or lines land visibly late, so the last report
   * is extrapolated with the clock and corrected whenever a new one lands. */
  double p = s_pos_base;
  if (s_meta->status == DECK_PLAYING)
    p += (double)(esp_timer_get_time() - s_pos_at_us) / 1000000.0;
  if (s_meta->duration > 0 && p > s_meta->duration) p = s_meta->duration;
  *pos = p;
  *dur = s_meta->duration;
  xSemaphoreGive(s_lock);
}

/* --- A2DP --------------------------------------------------------------- */
static void a2dp_data_cb(const uint8_t *data, uint32_t len) {
  /* Bluedroid's own task. Nothing here may block or do arithmetic. */
  deck_audio_feed(data, len);
  /* The I2S write is where audio actually leaves the deck. Kept last so that
   * if it ever blocks, the analyser has already been fed and the display
   * keeps moving — a deck that goes silent should not also freeze. */
  deck_i2s_write(data, len);
}

static void a2dp_event_cb(esp_a2d_cb_event_t event, esp_a2d_cb_param_t *p) {
  switch (event) {
  case ESP_A2D_CONNECTION_STATE_EVT: {
    const esp_a2d_connection_state_t st = p->conn_stat.state;
    if (st == ESP_A2D_CONNECTION_STATE_CONNECTED) {
      deck_diag_set(DECK_SUB_BT, DECK_HEALTH_OK, "connected %02x:%02x:%02x",
                    p->conn_stat.remote_bda[3], p->conn_stat.remote_bda[4],
                    p->conn_stat.remote_bda[5]);
      deck_diag_event(DECK_SUB_BT, "connect", "addr=%02x%02x%02x%02x%02x%02x",
                      p->conn_stat.remote_bda[0], p->conn_stat.remote_bda[1],
                      p->conn_stat.remote_bda[2], p->conn_stat.remote_bda[3],
                      p->conn_stat.remote_bda[4], p->conn_stat.remote_bda[5]);
      /* Stop advertising once something is connected. A head unit that stays
       * discoverable forever is one that a passenger's phone will grab at the
       * worst moment. */
      esp_bt_gap_set_scan_mode(ESP_BT_NON_CONNECTABLE, ESP_BT_NON_DISCOVERABLE);
    } else if (st == ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
      deck_diag_set(DECK_SUB_BT, DECK_HEALTH_DEGRADED, "waiting for a phone");
      deck_diag_event(DECK_SUB_BT, "disconnect", "reason=%d", p->conn_stat.disc_rsn);
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_meta->status = DECK_STOPPED;
      xSemaphoreGive(s_lock);
      esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
    }
    break;
  }
  case ESP_A2D_AUDIO_STATE_EVT:
    deck_diag_event(DECK_SUB_BT, "audio", "state=%d", p->audio_stat.state);
    break;
  case ESP_A2D_AUDIO_CFG_EVT:
    /* SBC only — it is the mandatory codec and every phone has it. AAC would
     * sound better from an iPhone and costs a licence question this project
     * does not want to answer. */
    deck_diag_event(DECK_SUB_BT, "codec", "type=%d", p->audio_cfg.mcc.type);
    break;
  default:
    break;
  }
}

/* --- AVRCP controller: what the phone tells us -------------------------- */
static void avrc_ct_cb(esp_avrc_ct_cb_event_t event, esp_avrc_ct_cb_param_t *p) {
  switch (event) {
  case ESP_AVRC_CT_CONNECTION_STATE_EVT:
    if (p->conn_stat.connected) {
      s_tl = 0;
      /* Ask for everything once, then subscribe to changes. Polling metadata
       * would work and would also wake the phone's radio forever. */
      esp_avrc_ct_send_metadata_cmd(s_tl++,
          ESP_AVRC_MD_ATTR_TITLE | ESP_AVRC_MD_ATTR_ARTIST |
          ESP_AVRC_MD_ATTR_ALBUM | ESP_AVRC_MD_ATTR_PLAYING_TIME);
      esp_avrc_ct_send_register_notification_cmd(
          s_tl++, ESP_AVRC_RN_TRACK_CHANGE, 0);
      esp_avrc_ct_send_register_notification_cmd(
          s_tl++, ESP_AVRC_RN_PLAY_STATUS_CHANGE, 0);
      esp_avrc_ct_send_register_notification_cmd(
          s_tl++, ESP_AVRC_RN_PLAY_POS_CHANGED, 1);
    }
    break;

  case ESP_AVRC_CT_METADATA_RSP_EVT:
    switch (p->meta_rsp.attr_id) {
    case ESP_AVRC_MD_ATTR_TITLE:
      set_str(s_meta->title, DECK_STR_MAX, p->meta_rsp.attr_text); break;
    case ESP_AVRC_MD_ATTR_ARTIST:
      set_str(s_meta->artist, DECK_STR_MAX, p->meta_rsp.attr_text); break;
    case ESP_AVRC_MD_ATTR_ALBUM:
      set_str(s_meta->album, DECK_STR_MAX, p->meta_rsp.attr_text); break;
    case ESP_AVRC_MD_ATTR_PLAYING_TIME: {
      char buf[24] = {0};
      const uint16_t n = p->meta_rsp.attr_length < sizeof buf - 1
                           ? p->meta_rsp.attr_length : sizeof buf - 1;
      memcpy(buf, p->meta_rsp.attr_text, n);
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_meta->duration = atof(buf) / 1000.0;      /* AVRCP reports ms */
      xSemaphoreGive(s_lock);
      break;
    }
    default: break;
    }
    deck_diag_event(DECK_SUB_BT, "meta", "attr=%u", (unsigned)p->meta_rsp.attr_id);
    break;

  case ESP_AVRC_CT_CHANGE_NOTIFY_EVT:
    switch (p->change_ntf.event_id) {
    case ESP_AVRC_RN_TRACK_CHANGE:
      /* A track change invalidates everything, including the lyrics the net
       * task fetched for the last one. Re-ask rather than assume. */
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_pos_base = 0; s_pos_at_us = esp_timer_get_time();
      s_meta->lyricState = DECK_LYR_IDLE;
      s_meta->rowCount = 0; s_meta->lineCount = 0;
      xSemaphoreGive(s_lock);
      esp_avrc_ct_send_metadata_cmd(s_tl++,
          ESP_AVRC_MD_ATTR_TITLE | ESP_AVRC_MD_ATTR_ARTIST |
          ESP_AVRC_MD_ATTR_ALBUM | ESP_AVRC_MD_ATTR_PLAYING_TIME);
      esp_avrc_ct_send_register_notification_cmd(
          s_tl++, ESP_AVRC_RN_TRACK_CHANGE, 0);
      break;
    case ESP_AVRC_RN_PLAY_STATUS_CHANGE:
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_meta->status = (p->change_ntf.event_parameter.playback ==
                        ESP_AVRC_PLAYBACK_PLAYING) ? DECK_PLAYING
                     : (p->change_ntf.event_parameter.playback ==
                        ESP_AVRC_PLAYBACK_PAUSED) ? DECK_PAUSED : DECK_STOPPED;
      xSemaphoreGive(s_lock);
      esp_avrc_ct_send_register_notification_cmd(
          s_tl++, ESP_AVRC_RN_PLAY_STATUS_CHANGE, 0);
      break;
    case ESP_AVRC_RN_PLAY_POS_CHANGED:
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_pos_base = p->change_ntf.event_parameter.play_pos / 1000.0;
      s_pos_at_us = esp_timer_get_time();
      xSemaphoreGive(s_lock);
      esp_avrc_ct_send_register_notification_cmd(
          s_tl++, ESP_AVRC_RN_PLAY_POS_CHANGED, 1);
      break;
    default: break;
    }
    break;

  default:
    break;
  }
}

/* --- AVRCP target: what we send back ------------------------------------ */
static void avrc_tg_cb(esp_avrc_tg_cb_event_t event, esp_avrc_tg_cb_param_t *p) {
  (void)p;
  if (event == ESP_AVRC_TG_CONNECTION_STATE_EVT)
    deck_diag_event(DECK_SUB_BT, "avrc-tg", "connected=%d", p->conn_stat.connected);
}

void deck_bt_send_key(uint8_t passthrough_cmd) {
  /* Press then release. Phones ignore a press that is never released, which is
   * the kind of thing that costs an afternoon. */
  esp_avrc_ct_send_passthrough_cmd(s_tl++, passthrough_cmd, ESP_AVRC_PT_CMD_STATE_PRESSED);
  esp_avrc_ct_send_passthrough_cmd(s_tl++, passthrough_cmd, ESP_AVRC_PT_CMD_STATE_RELEASED);
}

/* --- GAP: pairing ------------------------------------------------------- */
static void gap_cb(esp_bt_gap_cb_event_t event, esp_bt_gap_cb_param_t *p) {
  switch (event) {
  case ESP_BT_GAP_AUTH_CMPL_EVT:
    if (p->auth_cmpl.stat == ESP_BT_STATUS_SUCCESS)
      deck_diag_event(DECK_SUB_BT, "paired", "name=%s", p->auth_cmpl.device_name);
    else
      deck_diag_set(DECK_SUB_BT, DECK_HEALTH_DEGRADED,
                    "pairing failed (%d)", p->auth_cmpl.stat);
    break;
  case ESP_BT_GAP_CFM_REQ_EVT:
    /* Just Works. A head unit has no keypad and nothing worth typing a code
     * into; requiring one produces a device that nothing will pair with. */
    esp_bt_gap_ssp_confirm_reply(p->cfm_req.bda, true);
    break;
  case ESP_BT_GAP_MODE_CHG_EVT:
    deck_diag_event(DECK_SUB_BT, "mode", "mode=%d", p->mode_chg.mode);
    break;
  default:
    break;
  }
}

int deck_bt_start(deck_meta_t *meta, const char *name) {
  s_meta = meta;
  s_lock = xSemaphoreCreateMutex();
  if (!s_lock) return -1;

  esp_bt_controller_config_t cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
  /* Dual mode: Classic for the audio, BLE for firmware updates, one radio.
   * This is the arrangement the original ESP32 exists to provide. */
  cfg.mode = ESP_BT_MODE_BTDM;
  esp_err_t err = esp_bt_controller_init(&cfg);
  if (err) { deck_diag_set(DECK_SUB_BT, DECK_HEALTH_FAILED, "ctrl init %d", err); return err; }
  err = esp_bt_controller_enable(ESP_BT_MODE_BTDM);
  if (err) { deck_diag_set(DECK_SUB_BT, DECK_HEALTH_FAILED, "ctrl enable %d", err); return err; }
  if ((err = esp_bluedroid_init())) return err;
  if ((err = esp_bluedroid_enable())) return err;

  esp_bt_gap_set_device_name(name);
  esp_bt_gap_register_callback(gap_cb);

  esp_avrc_ct_init();
  esp_avrc_ct_register_callback(avrc_ct_cb);
  esp_avrc_tg_init();
  esp_avrc_tg_register_callback(avrc_tg_cb);

  /* Tell the phone which notifications we understand, or it will not send
   * any — including the track change that drives most of the display. */
  esp_avrc_rn_evt_cap_mask_t cap = {0};
  esp_avrc_rn_evt_bit_mask_operation(ESP_AVRC_BIT_MASK_OP_SET, &cap,
                                     ESP_AVRC_RN_VOLUME_CHANGE);
  esp_avrc_tg_set_rn_evt_cap(&cap);

  esp_a2d_register_callback(a2dp_event_cb);
  esp_a2d_sink_register_data_callback(a2dp_data_cb);
  esp_a2d_sink_init();

  esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);

  const uint8_t *mac = esp_bt_dev_get_address();
  deck_diag_set(DECK_SUB_BT, DECK_HEALTH_DEGRADED, "discoverable as \"%s\"", name);
  deck_diag_event(DECK_SUB_BT, "start", "name=%s addr=%02x%02x%02x%02x%02x%02x",
                  name, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  ESP_LOGI(TAG, "discoverable as \"%s\" — pair from the phone's Bluetooth menu", name);
  return 0;
}

void deck_bt_set_discoverable(int on) {
  esp_bt_gap_set_scan_mode(on ? ESP_BT_CONNECTABLE : ESP_BT_NON_CONNECTABLE,
                           on ? ESP_BT_GENERAL_DISCOVERABLE : ESP_BT_NON_DISCOVERABLE);
}
