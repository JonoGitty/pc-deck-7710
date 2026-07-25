/* The diagnostics layer, shared by both host harnesses.
 *
 * It lives in its own file because `tools/sim/sim.c` (the UI simulator) and
 * `tools/sim/drivers.c` (the driver harness) both need it and neither should
 * own it. Kept rather than stubbed to silence: the whole point of the
 * diagnostics layer is that it says what the deck is doing, and a harness that
 * threw that away would be testing the firmware with its instrumentation
 * removed — which is exactly the instrumentation somebody debugging a real
 * deck will be reading.
 *
 * The timestamp comes from `sim_stub_now_ms()`, which each harness defines
 * from its own clock: wall-ish seconds in the UI simulator, the virtual clock
 * in the driver harness. Before this was a hook the timestamp came from a
 * setter nobody ever called, so every line was stamped 0.
 */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "deck_diag.h"
#include "sim_stubs.h"

static const char *SUB[] = {"display", "bt", "audio", "wifi",
                            "movies", "input", "storage"};
static const char *HEALTH[] = {"unknown", "ok", "degraded", "failed"};
static deck_health_t s_h[DECK_SUB_COUNT];
static char s_d[DECK_SUB_COUNT][64];
void deck_diag_init(void) { memset(s_h, 0, sizeof s_h); }
void deck_diag_set(deck_sub_t sub, deck_health_t h, const char *fmt, ...) {
  if (sub >= DECK_SUB_COUNT) return;
  const deck_health_t was = s_h[sub];
  s_h[sub] = h;
  if (fmt) {
    va_list ap; va_start(ap, fmt);
    vsnprintf(s_d[sub], sizeof s_d[sub], fmt, ap);
    va_end(ap);
  }
  if (was != h)
    printf("# DECK|%.0f|%s|health|from=%s to=%s detail=%s\n",
           sim_stub_now_ms(), SUB[sub], HEALTH[was], HEALTH[h], s_d[sub]);
}
void deck_diag_event(deck_sub_t sub, const char *event, const char *fmt, ...) {
  char kv[128] = "";
  if (fmt) { va_list ap; va_start(ap, fmt); vsnprintf(kv, sizeof kv, fmt, ap); va_end(ap); }
  printf("# DECK|%.0f|%s|%s|%s\n", sim_stub_now_ms(),
         sub < DECK_SUB_COUNT ? SUB[sub] : "?", event, kv);
}
deck_health_t deck_diag_get(deck_sub_t s) { return s < DECK_SUB_COUNT ? s_h[s] : 0; }
const char *deck_diag_detail(deck_sub_t s) { return s < DECK_SUB_COUNT ? s_d[s] : ""; }
const char *deck_diag_sub_name(deck_sub_t s) { return s < DECK_SUB_COUNT ? SUB[s] : "?"; }
const char *deck_diag_health_name(deck_health_t h) { return h <= 3 ? HEALTH[h] : "?"; }
void deck_diag_frame(uint32_t a, uint32_t b) { (void)a; (void)b; }
void deck_diag_heap_check(void) {}
void deck_diag_report(void) {}
void deck_diag_boot_reason(void) {}

