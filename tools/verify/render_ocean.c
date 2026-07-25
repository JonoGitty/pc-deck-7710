/* C side for the ocean scene. Prints the same per-frame digests as
 * render_ocean.js, which drives the original JS in Chromium. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../core/deck.h"
#include "../../core/screens.h"

#define W 192
#define H 48

static uint32_t fnv1a(const uint8_t *p, size_t n) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
  return h;
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "tools/verify/ocean.tsv";
  FILE *f = fopen(path, "r");
  if (!f) { perror(path); return 1; }

  static uint8_t px[W * H];
  const deck_geom_t geom = { W, H, DECK_LEVELS, 0 };
  deck_fb_t fb = { &geom, px };
  static deck_state_t v;
  static deck_ocean_t o;

  char line[256];
  while (fgets(line, sizeof line, f)) {
    if (line[0] == '/' || line[0] == '\n') continue;
    char name[64];
    int frames;
    double rms, hf, bass, bassStep;
    if (sscanf(line, "%63s %d %lf %lf %lf %lf",
               name, &frames, &rms, &hf, &bass, &bassStep) != 6) continue;

    deck_ocean_reset(&o);
    memset(&v, 0, sizeof v);

    printf("%-14s", name);
    for (int t = 0; t < frames; t++) {
      deck_clear(&fb);
      v.rms01 = rms;
      v.hfAvg = hf;
      v.bassAvg = bass + (t > 8 ? bassStep : 0.0);
      deck_screen_ocean(&fb, &v, &o, (uint32_t)t);

      if (getenv("DECK_DEBUG")) {
        const deck_dolphin_t *d = &o.pod[0];
        printf("\nt%d x%.3f y%.3f m%d jt%d a%.3f f%d sp%d",
               t, d->x, d->ry, d->mode, d->jt, d->rang, d->rflex, o.nSpray);
        continue;
      }
      int nz = 0; long sum = 0;
      for (int i = 0; i < W * H; i++) { if (px[i]) nz++; sum += px[i]; }
      printf(" %d:%x:%d:%ld", t, fnv1a(px, sizeof px), nz, sum);
    }
    printf("\n");
  }
  fclose(f);
  return 0;
}
