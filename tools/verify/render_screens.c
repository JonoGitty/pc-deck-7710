/* Screen-level port check. State is generated from a seed by an LCG written
 * identically here and in render_screens.js, so both sides render from exactly
 * the same input and any output difference is the port's fault. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../core/deck.h"
#include "../../core/screens.h"

#define W 192
#define H 48

static uint32_t lcg_s;
static void   lcg_seed(uint32_t s) { lcg_s = s; }
static double lcg_next(void) {
  lcg_s = lcg_s * 1664525u + 1013904223u;
  return (double)lcg_s / 4294967296.0;
}

static void fill_state(deck_state_t *v, uint32_t seed) {
  memset(v, 0, sizeof *v);
  lcg_seed(seed);
  for (int b = 0; b < DECK_BANDS; b++) v->bands[b] = lcg_next();
  for (int b = 0; b < DECK_BANDS; b++) v->peaks[b] = lcg_next();
  for (int b = 0; b < DECK_BANDS; b++) v->bandsL[b] = lcg_next();
  for (int b = 0; b < DECK_BANDS; b++) v->bandsR[b] = lcg_next();
  v->vuL = lcg_next(); v->vuR = lcg_next();
  for (int i = 0; i < DECK_WAVE; i++) v->wave[i] = lcg_next() * 2.0 - 1.0;
  v->bassAvg = lcg_next(); v->hfAvg = lcg_next();
  v->rms01 = lcg_next(); v->scopeGain = 1.0 + lcg_next() * 8.0;
}

static uint32_t fnv1a(const uint8_t *p, size_t n) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
  return h;
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "tools/verify/screens.tsv";
  FILE *f = fopen(path, "r");
  if (!f) { perror(path); return 1; }

  static uint8_t px[W * H];
  const deck_geom_t geom = { W, H, DECK_LEVELS, 0 };
  deck_fb_t fb = { &geom, px };
  deck_state_t v;

  char line[512];
  while (fgets(line, sizeof line, f)) {
    if (line[0] == '/' || line[0] == '\n') continue;
    char name[64], screen[64];
    unsigned seed;
    if (sscanf(line, "%63s %63s %u", name, screen, &seed) != 3) continue;

    fill_state(&v, seed);
    deck_clear(&fb);
    if (strcmp(screen, "spectrum") == 0) deck_screen_spectrum(&fb, &v);
    else { fprintf(stderr, "unknown screen %s\n", screen); return 1; }

    int nz = 0;
    long sum = 0;
    for (int i = 0; i < W * H; i++) { if (px[i]) nz++; sum += px[i]; }
    printf("%-16s hash=%08x nz=%-5d sum=%ld\n", name, fnv1a(px, sizeof px), nz, sum);
  }
  fclose(f);
  return 0;
}
