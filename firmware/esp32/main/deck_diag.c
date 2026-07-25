#include "deck_diag.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_core_dump.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"

#include "deck_display.h"

static const char *TAG = "deck";

#define DETAIL_MAX 64

static struct {
  deck_health_t health;
  char          detail[DETAIL_MAX];
} s_sub[DECK_SUB_COUNT];

static struct {
  uint32_t frames;
  uint32_t render_us_max, blit_us_max;
  uint64_t render_us_sum;
  uint32_t heap_min;
} s_stat;

static const char *SUB_NAME[DECK_SUB_COUNT] = {
    "display", "bt", "audio", "wifi", "movies", "input", "storage"};
static const char *HEALTH_NAME[] = {"unknown", "ok", "degraded", "failed"};

const char *deck_diag_sub_name(deck_sub_t s) {
  return (s < DECK_SUB_COUNT) ? SUB_NAME[s] : "?";
}
const char *deck_diag_health_name(deck_health_t h) {
  return (h <= DECK_HEALTH_FAILED) ? HEALTH_NAME[h] : "?";
}
deck_health_t deck_diag_get(deck_sub_t s) {
  return (s < DECK_SUB_COUNT) ? s_sub[s].health : DECK_HEALTH_UNKNOWN;
}
const char *deck_diag_detail(deck_sub_t s) {
  return (s < DECK_SUB_COUNT) ? s_sub[s].detail : "";
}

void deck_diag_init(void) {
  memset(s_sub, 0, sizeof s_sub);
  memset(&s_stat, 0, sizeof s_stat);
  s_stat.heap_min = 0xffffffffu;
}

void deck_diag_set(deck_sub_t sub, deck_health_t h, const char *fmt, ...) {
  if (sub >= DECK_SUB_COUNT) return;
  const deck_health_t was = s_sub[sub].health;
  s_sub[sub].health = h;
  if (fmt) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(s_sub[sub].detail, DETAIL_MAX, fmt, ap);
    va_end(ap);
  }
  /* Only log transitions. A subsystem that reports "ok" forty times a second
   * is a subsystem whose log nobody reads. */
  if (was != h) {
    printf("DECK|%llu|%s|health|from=%s to=%s detail=%s\n",
           (unsigned long long)(esp_timer_get_time() / 1000),
           SUB_NAME[sub], HEALTH_NAME[was], HEALTH_NAME[h], s_sub[sub].detail);
  }
}

void deck_diag_event(deck_sub_t sub, const char *event, const char *fmt, ...) {
  char kv[128] = "";
  if (fmt) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(kv, sizeof kv, fmt, ap);
    va_end(ap);
  }
  printf("DECK|%llu|%s|%s|%s\n",
         (unsigned long long)(esp_timer_get_time() / 1000),
         deck_diag_sub_name(sub), event, kv);
}

void deck_diag_frame(uint32_t render_us, uint32_t blit_us) {
  s_stat.frames++;
  s_stat.render_us_sum += render_us;
  if (render_us > s_stat.render_us_max) s_stat.render_us_max = render_us;
  if (blit_us > s_stat.blit_us_max) s_stat.blit_us_max = blit_us;
}

void deck_diag_heap_check(void) {
  const uint32_t free_now = (uint32_t)esp_get_free_heap_size();
  if (free_now < s_stat.heap_min) s_stat.heap_min = free_now;
  /* Fifty kilobytes is not a cliff, it is a warning shot: below it the WiFi
   * stack starts failing to allocate and the symptom shows up as lyrics not
   * loading, which looks like a network bug. */
  if (free_now < 50 * 1024) {
    deck_diag_set(DECK_SUB_STORAGE, DECK_HEALTH_DEGRADED,
                  "heap low: %u B", (unsigned)free_now);
  }
}

void deck_diag_boot_reason(void) {
  static const char *R[] = {"unknown", "power-on",  "external", "software",
                            "panic",   "int-wdt",   "task-wdt", "wdt",
                            "deepsleep", "brownout", "sdio"};
  const esp_reset_reason_t r = esp_reset_reason();
  const char *name = ((size_t)r < sizeof R / sizeof *R) ? R[r] : "?";

  deck_diag_event(DECK_SUB_STORAGE, "boot", "reason=%s code=%d", name, (int)r);

  /* Brownout deserves its own sentence because in a car it is almost never a
   * firmware bug — it is cranking, or a supply that cannot hold up through
   * one. Saying so here saves someone a week in the debugger. */
  if (r == ESP_RST_BROWNOUT) {
    ESP_LOGE(TAG, "brownout reset: the 5V rail sagged. In a vehicle this is "
                  "usually cranking or an undersized buck converter, not "
                  "software. See docs/HARDWARE.md section 3.");
  }
  if (r == ESP_RST_TASK_WDT || r == ESP_RST_INT_WDT || r == ESP_RST_WDT) {
    ESP_LOGE(TAG, "watchdog reset: something blocked. If there is a core dump "
                  "below, pull it with: deckctl coredump");
  }

  if (esp_core_dump_image_check() == ESP_OK) {
    esp_core_dump_summary_t sum;
    if (esp_core_dump_get_summary(&sum) == ESP_OK) {
      deck_diag_event(DECK_SUB_STORAGE, "coredump",
                      "present=1 task=%s pc=0x%08x",
                      sum.exc_task, (unsigned)sum.exc_pc);
      ESP_LOGE(TAG, "a core dump from a previous crash is in flash. "
                    "Retrieve it with: python3 tools/deckctl.py coredump");
    } else {
      deck_diag_event(DECK_SUB_STORAGE, "coredump", "present=1 summary=failed");
    }
  }
}

void deck_diag_report(void) {
  const esp_app_desc_t *app = esp_app_get_description();
  const esp_partition_t *run = esp_ota_get_running_partition();
  const deck_panel_t *p = deck_panel();

  printf("\n");
  printf("=== DECK-7710 ==============================================\n");
  printf("  firmware   %s  %s %s\n", app->version, app->date, app->time);
  printf("  idf        %s\n", app->idf_ver);
  printf("  panel      %s  %dx%d  %u levels\n",
         p->name, p->w, p->h, (unsigned)p->levels);
  printf("  running    %s @ 0x%06x\n", run ? run->label : "?",
         run ? (unsigned)run->address : 0u);
  printf("  heap       %u free, %u min, %u psram\n",
         (unsigned)esp_get_free_heap_size(),
         (unsigned)(s_stat.heap_min == 0xffffffffu ? 0 : s_stat.heap_min),
         (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
  if (s_stat.frames) {
    printf("  frames     %u drawn, avg %u us, worst render %u us, blit %u us\n",
           (unsigned)s_stat.frames,
           (unsigned)(s_stat.render_us_sum / s_stat.frames),
           (unsigned)s_stat.render_us_max, (unsigned)s_stat.blit_us_max);
  }
  printf("  ---------------------------------------------------------\n");
  for (int i = 0; i < DECK_SUB_COUNT; i++) {
    printf("  %-9s  %-9s %s\n", SUB_NAME[i],
           HEALTH_NAME[s_sub[i].health], s_sub[i].detail);
  }
  printf("============================================================\n\n");
}
