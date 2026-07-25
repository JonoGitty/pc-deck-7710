#include "sim_stubs.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#include "deck_input.h"

/* --- the clock the diagnostics stub stamps with ------------------------- */
static double s_now;
void   sim_set_now(double seconds) { s_now = seconds; }
double sim_stub_now_ms(void) { return s_now * 1000.0; }

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
