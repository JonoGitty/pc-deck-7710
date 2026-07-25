/* Render the telephone screens, from the real core/, for the README and for
 * looking at.
 *
 * Separate from shots.c because these are not driven by audio — they are
 * driven by a call state machine, and faking one inside the music harness
 * would make both harder to read. Output is the same .raw format shots.py
 * already consumes.
 *
 *   gcc -o mkcall tools/media/callshots.c core/... core/screens/... -lm
 *   ./mkcall build/shots
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "deck.h"
#include "screens.h"

static uint8_t px[512 * 128];

static void write_raw(const char *dir, const char *name, int w, int h,
                      const uint8_t *frames, int n) {
  char path[512];
  snprintf(path, sizeof path, "%s/%s.raw", dir, name);
  FILE *f = fopen(path, "wb");
  if (!f) { perror(path); exit(1); }
  /* "DSHT" then w, h, frame count as little-endian u16 — the header
   * tools/media/shots.py already reads. */
  const uint8_t hdr[10] = {'D', 'S', 'H', 'T',
                           (uint8_t)(w & 255), (uint8_t)(w >> 8),
                           (uint8_t)(h & 255), (uint8_t)(h >> 8),
                           (uint8_t)(n & 255), (uint8_t)(n >> 8)};
  fwrite(hdr, 1, sizeof hdr, f);
  fwrite(frames, 1, (size_t)w * h * n, f);
  fclose(f);
  printf("  %-22s %3d frames  %dx%d\n", name, n, w, h);
}

/* One clip per state. Durations chosen so the GIF shows the animation doing
 * its whole cycle — the ring pulse is 0.9 s, so a 2 s incoming clip shows it
 * twice and reads as a rhythm rather than as a glitch. */
static void clip(const char *dir, const char *name, deck_call_state_t st,
                 const char *who, const char *num, int secs0, double dur_s,
                 int w, int h) {
  const int fps = 20, n = (int)(dur_s * fps);
  uint8_t *out = malloc((size_t)w * h * n);
  const deck_geom_t geom = {(uint16_t)w, (uint16_t)h, DECK_LEVELS, 0};
  deck_fb_t fb = {&geom, px};

  deck_call_t c;
  memset(&c, 0, sizeof c);
  c.state = st;
  snprintf(c.name, sizeof c.name, "%s", who);
  snprintf(c.number, sizeof c.number, "%s", num);

  for (int i = 0; i < n; i++) {
    const double t = i * 1000.0 / fps;
    c.secs = secs0 + i / fps;
    /* A plausible speaking level: mostly mid, with syllable-rate peaks. The
     * meter exists to show the mic is alive, so a flat bar would defeat it. */
    c.mic = (uint8_t)(90 + 70 * ((i % 13) < 5) + 40 * ((i % 31) < 3));
    deck_clear(&fb);
    deck_screen_call(&fb, &c, t);
    memcpy(out + (size_t)i * w * h, px, (size_t)w * h);
  }
  write_raw(dir, name, w, h, out, n);
  free(out);
}

/* The tuner, in the three states worth showing: a station with full RDS, one
 * with none (so the frequency gets the big treatment), and AM. */
static void radioclip(const char *dir, const char *name, deck_band_t band,
                      int khz, int lo, int hi, const char *rds, const char *txt,
                      uint8_t rssi, int stereo, int w, int h) {
  const int fps = 20, n = 60;
  uint8_t *out = malloc((size_t)w * h * n);
  const deck_geom_t geom = {(uint16_t)w, (uint16_t)h, DECK_LEVELS, 0};
  deck_fb_t fb = {&geom, px};
  deck_scroll_t sc;
  memset(&sc, 0, sizeof sc);

  deck_radio_t r;
  memset(&r, 0, sizeof r);
  r.band = band; r.freq_khz = khz;
  r.band_lo_khz = lo; r.band_hi_khz = hi;
  r.rssi = rssi; r.stereo = (uint8_t)stereo; r.preset = 3;
  snprintf(r.name, sizeof r.name, "%s", rds);
  snprintf(r.text, sizeof r.text, "%s", txt);
  r.n_presets = 5;
  for (int i = 0; i < 5; i++) r.preset_khz[i] = lo + (hi - lo) * (i + 1) / 7;

  for (int i = 0; i < n; i++) {
    deck_clear(&fb);
    deck_screen_radio(&fb, &r, &sc, 1000.0 / fps);
    memcpy(out + (size_t)i * w * h, px, (size_t)w * h);
  }
  write_raw(dir, name, w, h, out, n);
  free(out);
}

int main(int argc, char **argv) {
  const char *dir = argc > 1 ? argv[1] : "build/shots";
  const int w = argc > 2 ? atoi(argv[2]) : 256;
  const int h = argc > 3 ? atoi(argv[3]) : 64;

  clip(dir, "call-incoming", DECK_CALL_INCOMING, "MUM", "07700900123", 0, 2.0, w, h);
  clip(dir, "call-outgoing", DECK_CALL_OUTGOING, "", "07700900123", 0, 2.0, w, h);
  clip(dir, "call-active",   DECK_CALL_ACTIVE,   "MUM", "07700900123", 96, 2.5, w, h);
  clip(dir, "call-ended",    DECK_CALL_ENDED,    "MUM", "07700900123", 214, 1.0, w, h);

  /* RDS radio text runs to 64 characters, and the short sample this used to
   * carry fitted the panel — so the marquee never moved and the preview
   * showed a feature standing still. A realistic-length string is what
   * demonstrates it. */
  radioclip(dir, "radio-fm", DECK_BAND_FM, 98500, 87500, 108000,
            "RADIO 1", "NOW PLAYING - KAVINSKY / NIGHTCALL - "
            "TEXT THIS LONG IS WHAT A STATION ACTUALLY SENDS", 210, 1, w, h);
  radioclip(dir, "radio-noRds", DECK_BAND_FM, 104700, 87500, 108000,
            "", "", 120, 0, w, h);
  radioclip(dir, "radio-am", DECK_BAND_AM, 1053, 522, 1710,
            "", "", 90, 0, w, h);
  return 0;
}
