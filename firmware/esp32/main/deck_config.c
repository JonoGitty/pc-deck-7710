#include "deck_config.h"

#include <string.h>

#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"

#include "deck_diag.h"

#define NS "deck"
#define FLUSH_AFTER_US (5 * 1000000LL)

static int64_t s_dirty_at;

void deck_cfg_load(deck_cfg_t *c) {
  memset(c, 0, sizeof *c);
  /* Defaults chosen so a deck that has never been configured still does
   * something reasonable the first time it is powered up. */
  c->mode = 0;
  c->brightness = 80;
  c->lyrics_enabled = 1;
  c->art_enabled = 1;

  nvs_handle_t h;
  if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) {
    deck_diag_set(DECK_SUB_STORAGE, DECK_HEALTH_OK, "defaults (no saved config)");
    return;
  }
  size_t n = sizeof *c;
  uint8_t tmp[sizeof *c];
  if (nvs_get_blob(h, "cfg", tmp, &n) == ESP_OK && n == sizeof *c)
    memcpy(c, tmp, sizeof *c);
  nvs_close(h);
  deck_diag_set(DECK_SUB_STORAGE, DECK_HEALTH_OK, "config loaded");
}

void deck_cfg_save(const deck_cfg_t *c) {
  nvs_handle_t h;
  if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK) {
    deck_diag_set(DECK_SUB_STORAGE, DECK_HEALTH_DEGRADED, "nvs open failed");
    return;
  }
  nvs_set_blob(h, "cfg", c, sizeof *c);
  nvs_commit(h);
  nvs_close(h);
  s_dirty_at = 0;
  deck_diag_event(DECK_SUB_STORAGE, "config", "saved=1");
}

void deck_cfg_mark_dirty(void) {
  if (!s_dirty_at) s_dirty_at = esp_timer_get_time();
}

void deck_cfg_flush_if_due(const deck_cfg_t *c) {
  if (s_dirty_at && esp_timer_get_time() - s_dirty_at > FLUSH_AFTER_US)
    deck_cfg_save(c);
}
