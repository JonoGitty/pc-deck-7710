/* WiFi, and the one lookup that needs it: synced lyrics from LRCLIB.
 *
 * WHY THIS IS OPTIONAL AND OFF BY DEFAULT UNTIL CONFIGURED. A car has no WiFi.
 * The deck joins your phone's hotspot if you give it one, and does without if
 * you do not — every screen except lyrics works with the radio off, and the
 * lyrics screen degrades to a message rather than to a hang. Anything that
 * made the deck depend on a network would be a deck that does not work in a
 * tunnel.
 *
 * WHY ALBUM ART IS NOT FETCHED HERE. The PC deck falls back to the iTunes
 * Search API for a sleeve when the player supplies none, and the ESP32 could
 * do the same — but it would have to decode a JPEG, which means a decoder,
 * which in ESP-IDF means a managed component and therefore a build that needs
 * a network round trip. This project is one people clone onto a laptop and
 * build offline, so art arrives the other way: the deck shows whatever the
 * phone sends over AVRCP, and `deckctl art` can push a set of pre-dithered
 * sleeves into the storage partition. See docs/BUILD.md.
 *
 * The one thing that leaves the deck is a track title, artist and album. No
 * audio, ever. See SAFETY.md.
 *
 * NEVER RUN ON HARDWARE.
 */
#include "deck_net.h"

#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "esp_event.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "deck_diag.h"

/* Everything worth reading goes through deck_diag_event() in the structured
 * DECK| format, not through ESP_LOG — one parseable stream beats two. The tag
 * stays declared and unused-suppressed because a temporary ESP_LOGI while
 * debugging a TLS handshake is the single most likely edit to this file. */
__attribute__((unused)) static const char *TAG = "deck.net";
static volatile int s_up;
static TaskHandle_t s_task;

static deck_meta_t *s_meta;
static int          s_cells;
static char         s_want_key[192];
static char         s_done_key[192];

/* Bounded because it lands in RAM alongside the Bluetooth and WiFi stacks. A
 * long song's LRC is a few kilobytes; anything past this is not lyrics. */
#define LRC_MAX 8192

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
  (void)arg; (void)data;
  if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
    esp_wifi_connect();
  } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
    s_up = 0;
    deck_diag_set(DECK_SUB_WIFI, DECK_HEALTH_DEGRADED, "disconnected, retrying");
    /* Reconnect forever rather than giving up after N tries: the hotspot is a
     * phone, and phones go out of range and come back constantly. */
    esp_wifi_connect();
  } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
    s_up = 1;
    deck_diag_set(DECK_SUB_WIFI, DECK_HEALTH_OK, "connected");
  }
}

int deck_net_is_up(void) { return s_up; }

int deck_net_start(const char *ssid, const char *pass) {
  if (!ssid || !ssid[0]) {
    deck_diag_set(DECK_SUB_WIFI, DECK_HEALTH_UNKNOWN, "no network configured");
    return 0;                 /* not an error: a deck without WiFi is normal */
  }
  esp_netif_init();
  esp_event_loop_create_default();
  esp_netif_create_default_wifi_sta();

  wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
  esp_err_t err = esp_wifi_init(&cfg);
  if (err) { deck_diag_set(DECK_SUB_WIFI, DECK_HEALTH_FAILED, "init %d", err); return err; }

  esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL, NULL);
  esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL, NULL);

  wifi_config_t wc = {0};
  snprintf((char *)wc.sta.ssid, sizeof wc.sta.ssid, "%s", ssid);
  snprintf((char *)wc.sta.password, sizeof wc.sta.password, "%s", pass ? pass : "");
  esp_wifi_set_mode(WIFI_MODE_STA);
  esp_wifi_set_config(WIFI_IF_STA, &wc);
  /* Modem sleep, not full power save: the radio is idle almost always, and
   * the deck shares an antenna with a Bluetooth link that must not stutter. */
  esp_wifi_set_ps(WIFI_PS_MIN_MODEM);
  err = esp_wifi_start();
  if (err) { deck_diag_set(DECK_SUB_WIFI, DECK_HEALTH_FAILED, "start %d", err); return err; }

  deck_diag_set(DECK_SUB_WIFI, DECK_HEALTH_DEGRADED, "joining %s", ssid);
  return 0;
}

/* --- LRCLIB ------------------------------------------------------------- */
static void url_escape(char *dst, size_t cap, const char *src) {
  size_t o = 0;
  for (const unsigned char *p = (const unsigned char *)src; *p && o + 4 < cap; p++) {
    if ((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
        (*p >= '0' && *p <= '9') || *p == '-' || *p == '_' || *p == '.') {
      dst[o++] = (char)*p;
    } else {
      o += (size_t)snprintf(dst + o, cap - o, "%%%02X", *p);
    }
  }
  dst[o] = 0;
}

/* Parse "[mm:ss.cc] text" lines into the meta's row table. The wrapping and
 * folding are core/'s, so the firmware and the PC deck break lines in exactly
 * the same places — a lyric that fits on the PC fits on the panel. */
static int parse_lrc(deck_meta_t *m, const char *lrc, int cells) {
  deck_lyrics_reset(m);
  int added = 0;
  const char *p = lrc;
  while (*p) {
    const char *eol = strchr(p, '\n');
    const size_t len = eol ? (size_t)(eol - p) : strlen(p);
    if (len > 10 && p[0] == '[' && p[3] == ':') {
      const int mm = (p[1] - '0') * 10 + (p[2] - '0');
      const int ss = (p[4] - '0') * 10 + (p[5] - '0');
      const int cc = (p[6] == '.') ? (p[7] - '0') * 10 + (p[8] - '0') : 0;
      const char *txt = strchr(p, ']');
      if (txt && (size_t)(txt - p) < len) {
        char buf[160];
        size_t n = len - (size_t)(txt + 1 - p);
        if (n >= sizeof buf) n = sizeof buf - 1;
        memcpy(buf, txt + 1, n);
        buf[n] = 0;
        if (deck_lyrics_add(m, mm * 60 + ss + cc / 100.0, buf, cells)) added++;
      }
    }
    if (!eol) break;
    p = eol + 1;
  }
  return added;
}

static void fetch_task(void *arg) {
  (void)arg;
  static char url[1024], q1[192], q2[192], q3[192];
  static char *body;

  while (1) {
    /* Nothing to do, or the same track we already handled. Comparing keys
     * rather than a flag is what makes this safe against the several AVRCP
     * notifications a single track change produces. */
    if (!s_up || !s_want_key[0] || !strcmp(s_want_key, s_done_key)) {
      vTaskDelay(pdMS_TO_TICKS(400));
      continue;
    }
    char key[sizeof s_want_key];
    snprintf(key, sizeof key, "%s", s_want_key);

    s_meta->lyricState = DECK_LYR_SEARCHING;
    url_escape(q1, sizeof q1, s_meta->title);
    url_escape(q2, sizeof q2, s_meta->artist);
    url_escape(q3, sizeof q3, s_meta->album);
    snprintf(url, sizeof url,
             "https://lrclib.net/api/get?track_name=%s&artist_name=%s&album_name=%s",
             q1, q2, q3);

    if (!body) body = heap_caps_malloc(LRC_MAX, MALLOC_CAP_SPIRAM);
    if (!body) body = malloc(LRC_MAX);

    int ok = 0;
    if (body) {
      esp_http_client_config_t cfg = {
          .url = url,
          .timeout_ms = 6000,
          /* Verified TLS, using ESP-IDF's root bundle. It costs about 200 KB
           * of flash, which is most of the reason the app partitions are the
           * size they are — and it is the right trade: the alternative is
           * skipping certificate checks on a request that carries what you
           * are listening to. */
          .crt_bundle_attach = esp_crt_bundle_attach,
          .user_agent = "deck7710 (github.com/JonoGitty/pc-deck-7710)",
      };
      esp_http_client_handle_t c = esp_http_client_init(&cfg);
      if (c && esp_http_client_open(c, 0) == ESP_OK) {
        esp_http_client_fetch_headers(c);
        const int n = esp_http_client_read(c, body, LRC_MAX - 1);
        if (n > 0) {
          body[n] = 0;
          cJSON *j = cJSON_Parse(body);
          if (j) {
            const cJSON *sy = cJSON_GetObjectItem(j, "syncedLyrics");
            const cJSON *pl = cJSON_GetObjectItem(j, "plainLyrics");
            if (cJSON_IsString(sy) && sy->valuestring[0]) {
              ok = parse_lrc(s_meta, sy->valuestring, s_cells) > 0;
              s_meta->synced = 1;
            } else if (cJSON_IsString(pl) && pl->valuestring[0]) {
              /* Unsynced text, paced by track progress. Worse, and clearly
               * marked as such on screen rather than pretending. */
              deck_lyrics_reset(s_meta);
              s_meta->synced = 0;
              ok = 1;
            }
            cJSON_Delete(j);
          }
        }
        esp_http_client_close(c);
      }
      if (c) esp_http_client_cleanup(c);
    }

    s_meta->lyricState = ok ? DECK_LYR_OK : DECK_LYR_NONE;
    deck_diag_event(DECK_SUB_WIFI, "lyrics", "found=%d rows=%d",
                    ok, s_meta->rowCount);
    snprintf(s_done_key, sizeof s_done_key, "%s", key);
  }
}

void deck_net_want_lyrics(deck_meta_t *m, int cells) {
  s_meta = m;
  s_cells = cells;
  snprintf(s_want_key, sizeof s_want_key, "%s|%s", m->title, m->artist);
  if (!s_task)
    xTaskCreate(fetch_task, "deck_net", 6144, NULL, 3, &s_task);
}
