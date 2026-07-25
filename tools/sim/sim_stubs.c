#include "sim_stubs.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#include "deck_diag.h"
#include "deck_input.h"

/* --- diagnostics -------------------------------------------------------
 * Kept, not stubbed to silence. The whole point of the diagnostics layer is
 * that it says what the deck is doing, and a simulator that throws that away
 * would be testing the firmware with its instrumentation removed. */
static const char *SUB[] = {"display", "bt", "audio", "wifi",
                            "movies", "input", "storage"};
static const char *HEALTH[] = {"unknown", "ok", "degraded", "failed"};
static deck_health_t s_h[DECK_SUB_COUNT];
static char s_d[DECK_SUB_COUNT][64];
static double s_now;

void sim_set_now(double t) { s_now = t; }

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
           s_now * 1000, SUB[sub], HEALTH[was], HEALTH[h], s_d[sub]);
}
void deck_diag_event(deck_sub_t sub, const char *event, const char *fmt, ...) {
  char kv[128] = "";
  if (fmt) { va_list ap; va_start(ap, fmt); vsnprintf(kv, sizeof kv, fmt, ap); va_end(ap); }
  printf("# DECK|%.0f|%s|%s|%s\n", s_now * 1000,
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

/* --- input ------------------------------------------------------------- */
/* The simulator drives the UI directly from its script, so the queue is only
 * here to satisfy the link. Anything posted is dropped rather than silently
 * replayed, which would make script timing non-deterministic. */
void deck_input_post(deck_action_t a, int r) { (void)a; (void)r; }
int  deck_input_get(deck_event_t *e) { (void)e; return 0; }

/* --- frames out --------------------------------------------------------
 * Raw PPM to a file, converted by tools/sim/run.sh. Writing a GIF in C would
 * mean an LZW encoder in a test harness, which is a lot of surface area for
 * something Pillow already does in one line. */
static FILE *s_ppm;
static int s_pw, s_ph, s_pfps;

void sim_out_begin(const char *path, int w, int h, int fps) {
  s_pw = w; s_ph = h; s_pfps = fps;
  (void)s_pw; (void)s_ph; (void)s_pfps;
  if (!path) return;
  s_ppm = fopen(path, "wb");
  if (!s_ppm) { fprintf(stderr, "sim: cannot write %s\n", path); exit(2); }
  /* A tiny header of our own so the converter needs no arguments. */
  fprintf(s_ppm, "SIMDECK %d %d %d\n", w, h, fps);
}

void sim_out_frame(const uint8_t *dev, const uint8_t *levels, int w, int h) {
  (void)dev;
  if (!s_ppm) return;
  fwrite(levels, 1, (size_t)w * h, s_ppm);
}

void sim_out_end(void) { if (s_ppm) fclose(s_ppm); }

void sim_ascii(const uint8_t *levels, int w, int h) {
  static const char R[] = " .:*#";
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) putchar(R[levels[y * w + x] & 7]);
    putchar('\n');
  }
}
