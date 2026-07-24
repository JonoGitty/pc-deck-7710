/* Render tools/verify/cases.tsv through the C core and print a digest per case.
 * tools/verify/render.js prints the same digest via the legacy JS. If the two
 * outputs differ, the port is not faithful. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../core/deck.h"
#include "../../core/font.h"

#define W 192
#define H 48

static uint32_t fnv1a(const uint8_t *p, size_t n) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
  return h;
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "tools/verify/cases.tsv";
  FILE *f = fopen(path, "r");
  if (!f) { perror(path); return 1; }

  static uint8_t px[W * H];
  const deck_geom_t geom = { W, H, DECK_LEVELS, 0 };
  deck_fb_t fb = { &geom, px };
  deck_clear(&fb);

  char line[1024];
  while (fgets(line, sizeof line, f)) {
    if (line[0] == '/' || line[0] == '\n') continue;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;

    /* six tab-separated fields, then the text runs to end of line */
    char *fld[6];
    char *p = line;
    int ok = 1;
    for (int i = 0; i < 6; i++) {
      char *t = strchr(p, '\t');
      if (!t) { ok = 0; break; }
      *t = 0; fld[i] = p; p = t + 1;
    }
    if (!ok) continue;

    const char *name = fld[0];
    int fn = atoi(fld[1]), x = atoi(fld[2]), y = atoi(fld[3]);
    int inten = atoi(fld[4]), scale = atoi(fld[5]);
    const char *text = p;

    if (name[0] == '+') name++; else deck_clear(&fb);

    int adv = (fn == 3) ? deck_text3(&fb, x, y, text, (uint8_t)inten)
                        : deck_text5(&fb, x, y, text, (uint8_t)inten, scale);
    int width = (fn == 3) ? deck_width3(text) : deck_width5(text, scale);

    int nz = 0, x0 = W, y0 = H, x1 = -1, y1 = -1;
    for (int yy = 0; yy < H; yy++)
      for (int xx = 0; xx < W; xx++)
        if (px[yy * W + xx]) {
          nz++;
          if (xx < x0) x0 = xx;
          if (xx > x1) x1 = xx;
          if (yy < y0) y0 = yy;
          if (yy > y1) y1 = yy;
        }

    printf("%-16s hash=%08x nz=%-5d bbox=%d,%d,%d,%d adv=%d width=%d\n",
           name, fnv1a(px, sizeof px), nz, x0, y0, x1, y1, adv, width);
  }
  fclose(f);
  return 0;
}
