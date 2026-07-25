/* Fake ESP-IDF — see idf/README.md.
 *
 * The HFP *client* surface, which is the side a car kit is. Only the events
 * and fields `deck_hfp.c` actually uses are here, with the same names and the
 * same shapes as the real header, because the point is to compile the real
 * driver rather than a version of it edited to suit a test.
 *
 * The indicator values are the ones the AT specification defines and are worth
 * writing down, since the whole call state machine is derived from them:
 *
 *     call        0 = no call in progress          1 = a call is connected
 *     call_setup  0 = none   1 = incoming   2 = outgoing dialling
 *                 3 = outgoing, remote alerting
 */
#ifndef SIM_ESP_HF_CLIENT_API_H
#define SIM_ESP_HF_CLIENT_API_H

#include <stdint.h>
#include "esp_err.h"

typedef enum {
  ESP_HF_CLIENT_CONNECTION_STATE_EVT = 0,
  ESP_HF_CLIENT_AUDIO_STATE_EVT,
  ESP_HF_CLIENT_BVRA_EVT,
  ESP_HF_CLIENT_CIND_CALL_EVT,
  ESP_HF_CLIENT_CIND_CALL_SETUP_EVT,
  ESP_HF_CLIENT_CIND_SERVICE_AVAILABILITY_EVT,
  ESP_HF_CLIENT_CIND_SIGNAL_STRENGTH_EVT,
  ESP_HF_CLIENT_CIND_BATTERY_LEVEL_EVT,
  ESP_HF_CLIENT_CLIP_EVT,
  ESP_HF_CLIENT_RING_IND_EVT,
} esp_hf_client_cb_event_t;

typedef enum {
  ESP_HF_CLIENT_CONNECTION_STATE_DISCONNECTED = 0,
  ESP_HF_CLIENT_CONNECTION_STATE_CONNECTING,
  ESP_HF_CLIENT_CONNECTION_STATE_CONNECTED,
  ESP_HF_CLIENT_CONNECTION_STATE_SLC_CONNECTED,
  ESP_HF_CLIENT_CONNECTION_STATE_DISCONNECTING,
} esp_hf_client_connection_state_t;

typedef enum {
  ESP_HF_CLIENT_AUDIO_STATE_DISCONNECTED = 0,
  ESP_HF_CLIENT_AUDIO_STATE_CONNECTING,
  ESP_HF_CLIENT_AUDIO_STATE_CONNECTED,
  ESP_HF_CLIENT_AUDIO_STATE_CONNECTED_MSBC,
} esp_hf_client_audio_state_t;

typedef enum {
  ESP_HF_CALL_STATUS_NO_CALLS = 0,
  ESP_HF_CALL_STATUS_CALL_IN_PROGRESS = 1,
} esp_hf_call_status_t;

typedef enum {
  ESP_HF_CALL_SETUP_STATUS_NONE = 0,
  ESP_HF_CALL_SETUP_STATUS_INCOMING = 1,
  ESP_HF_CALL_SETUP_STATUS_OUTGOING_DIALING = 2,
  ESP_HF_CALL_SETUP_STATUS_OUTGOING_ALERTING = 3,
} esp_hf_call_setup_status_t;

typedef union {
  struct { esp_hf_client_connection_state_t state; } conn_stat;
  struct { esp_hf_client_audio_state_t state; } audio_stat;
  struct { esp_hf_call_status_t status; } call;
  struct { esp_hf_call_setup_status_t status; } call_setup;
  struct { const char *number; } clip;
} esp_hf_client_cb_param_t;

typedef void (*esp_hf_client_cb_t)(esp_hf_client_cb_event_t event,
                                   esp_hf_client_cb_param_t *param);
typedef void (*esp_hf_client_incoming_data_cb_t)(const uint8_t *buf,
                                                 uint32_t len);
typedef uint32_t (*esp_hf_client_outgoing_data_cb_t)(uint8_t *buf,
                                                     uint32_t len);

esp_err_t esp_hf_client_register_callback(esp_hf_client_cb_t cb);
esp_err_t esp_hf_client_init(void);
void esp_hf_client_register_data_callback(esp_hf_client_incoming_data_cb_t in,
                                          esp_hf_client_outgoing_data_cb_t out);
esp_err_t esp_hf_client_answer_call(void);
esp_err_t esp_hf_client_reject_call(void);
esp_err_t esp_hf_client_dial(const char *number);

#endif
