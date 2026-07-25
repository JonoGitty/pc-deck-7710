/* C side for the cover art and lyrics screens. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../core/deck.h"
#include "../../core/screens.h"
#include "../../core/art.h"
#include "../../core/text.h"

#define W 192
#define H 48

static uint32_t lcg_s;
static double lcg_next(void) {
  lcg_s = lcg_s * 1664525u + 1013904223u;
  return (double)lcg_s / 4294967296.0;
}

static uint32_t fnv1a(const uint8_t *p, size_t n) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
  return h;
}

static void copy_folded(char *dst, size_t cap, const char *src) {
  deck_fold(src, dst, cap);
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "tools/verify/meta.tsv";
  FILE *f = fopen(path, "r");
  if (!f) { perror(path); return 1; }

  static uint8_t px[W * H];
  static uint8_t lum[48 * 48], art[48 * 48];
  const deck_geom_t geom = { W, H, DECK_LEVELS, 0 };
  deck_fb_t fb = { &geom, px };
  static deck_state_t v;
  static deck_meta_t m;

  char line[4096];
  while (fgets(line, sizeof line, f)) {
    if (line[0] == '/' || line[0] == '\n') continue;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;

    /* 12 tab-separated fields then the lyrics blob. A line whose trailing
     * fields are all empty has no final tab, so the last field may simply run
     * to end of line with an empty remainder — JS's split() yields those, and
     * this has to agree with it or cases silently disappear. */
    char *fld[12], *p = line;
    int ok = 1;
    for (int i = 0; i < 12; i++) {
      char *t = strchr(p, '\t');
      if (t) { *t = 0; fld[i] = p; p = t + 1; }
      else if (i == 11) { fld[i] = p; p = line + len; }
      else { ok = 0; break; }
    }
    if (!ok) continue;
    const char *name = fld[0], *screen = fld[1];
    const unsigned seed = (unsigned)strtoul(fld[2], NULL, 10);
    const char *lyrics = p;

    memset(&v, 0, sizeof v);
    memset(&m, 0, sizeof m);
    lcg_s = seed;
    for (int b = 0; b < DECK_BANDS; b++) v.bands[b] = lcg_next();
    for (int b = 0; b < DECK_BANDS; b++) v.peaks[b] = lcg_next();
    v.bassAvg = lcg_next();

    const int S = 48;
    for (int i = 0; i < S * S; i++) lum[i] = (uint8_t)(lcg_next() * 256.0);
    deck_art_dither(lum, S, art);

    copy_folded(m.title,  sizeof m.title,  fld[8]);
    copy_folded(m.artist, sizeof m.artist, fld[9]);
    copy_folded(m.album,  sizeof m.album,  fld[10]);
    copy_folded(m.app,    sizeof m.app,    fld[11]);
    m.position   = atof(fld[3]);
    m.duration   = atof(fld[4]);
    m.lyricState = atoi(fld[5]);
    m.synced     = atoi(fld[6]);
    m.offsetMs   = atof(fld[7]);
    m.art     = seed == 0 ? NULL : art;
    m.artSide = seed == 0 ? 0 : S;

    /* lyrics blob: "time|text;time|text;..." */
    char blob[3072];
    strncpy(blob, lyrics, sizeof blob - 1);
    blob[sizeof blob - 1] = 0;
    char *save = blob;
    while (*save) {
      char *semi = strchr(save, ';');
      if (semi) *semi = 0;
      char *bar = strchr(save, '|');
      if (bar) {
        *bar = 0;
        deck_lyrics_add(&m, atof(save), bar + 1, 30);
      }
      if (!semi) break;
      save = semi + 1;
    }

    deck_clear(&fb);
    if (strcmp(screen, "cover") == 0) {
      deck_scroll_t sc = { 0, 0, 0.0 };
      deck_screen_cover(&fb, &v, &m, &sc, 100.0);
    } else {
      deck_screen_lyrics(&fb, &v, &m, 0.0);
    }

    int nz = 0; long sum = 0;
    for (int i = 0; i < W * H; i++) { if (px[i]) nz++; sum += px[i]; }
    printf("%-16s hash=%08x nz=%-5d sum=%ld\n", name, fnv1a(px, sizeof px), nz, sum);
  }
  fclose(f);
  return 0;
}
