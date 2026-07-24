/* Decode a .dmv through the C player and digest every frame. The Python side
 * in render_movie.py decodes the same file independently — if the two agree,
 * the format round-trips and neither codec is quietly wrong. */
#include <stdio.h>
#include <stdlib.h>
#include "../../core/deck.h"
#include "../../core/movie.h"

static uint32_t fnv1a(const uint8_t *p, uint32_t n) {
  uint32_t h = 2166136261u;
  for (uint32_t i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
  return h;
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s file.dmv\n", argv[0]); return 2; }
  FILE *f = fopen(argv[1], "rb");
  if (!f) { perror(argv[1]); return 1; }
  static uint8_t blob[1 << 20];
  const uint32_t n = (uint32_t)fread(blob, 1, sizeof blob, f);
  fclose(f);

  deck_movie_t m;
  if (!deck_movie_open(&m, blob, n)) { fprintf(stderr, "bad dmv\n"); return 1; }
  printf("open %.*s %ux%u fps=%u frames=%u loop=%d\n",
         m.nameLen, m.name, m.w, m.h, m.fps, m.frameCount, !!(m.flags & DECK_MOVIE_LOOP));

  static uint8_t grid[65536];
  deck_movie_play_t p;
  deck_movie_start(&p, &m, grid);

  const uint32_t cells = (uint32_t)m.w * m.h;
  /* one and a half passes, so the loop-and-replay path is exercised too */
  for (int i = 0; i < (int)m.frameCount * 3 / 2; i++) {
    if (!deck_movie_step(&p)) { printf("step %d: stopped\n", i); break; }
    uint32_t lit = 0;
    for (uint32_t c = 0; c < cells; c++) if (grid[c]) lit++;
    printf("%d %08x %u\n", i, fnv1a(grid, cells), lit);
  }
  return 0;
}
