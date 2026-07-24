/* Decode a .dmv through the C player and digest every frame. The Python side
 * in render_movie.py decodes the same file independently — if the two agree,
 * the format round-trips and neither codec is quietly wrong.
 *
 * Every frame is decoded twice: once over a flat buffer, once over a streaming
 * source that hands out bytes through a file handle and never holds the movie
 * in memory. That second pass is the one the firmware will use, since a movie
 * is bigger than the ESP32's app partition; running both against the same
 * digest is what stops the streaming path from rotting unnoticed. */
#include <stdio.h>
#include <stdlib.h>
#include "../../core/deck.h"
#include "../../core/movie.h"

/* A source with no buffer at all — deliberately the least helpful thing that
 * could work, so any assumption the decoder makes about contiguity or read
 * size shows up here rather than on hardware. */
static uint32_t src_file(void *ctx, uint32_t off, uint8_t *dst, uint32_t n) {
  FILE *f = (FILE *)ctx;
  if (fseek(f, (long)off, SEEK_SET) != 0) return 0;
  return (uint32_t)fread(dst, 1, n, f);
}

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

  /* The streaming twin, opened over the file itself. */
  FILE *sf = fopen(argv[1], "rb");
  if (!sf) { perror(argv[1]); return 1; }
  deck_movie_src_t src = { src_file, sf, n };
  deck_movie_t sm;
  if (!deck_movie_open_src(&sm, &src)) { fprintf(stderr, "bad dmv (stream)\n"); return 1; }

  static uint8_t grid[65536], sgrid[65536];
  deck_movie_play_t p, sp;
  deck_movie_start(&p, &m, grid);
  deck_movie_start(&sp, &sm, sgrid);

  const uint32_t cells = (uint32_t)m.w * m.h;
  /* one and a half passes, so the loop-and-replay path is exercised too */
  for (int i = 0; i < (int)m.frameCount * 3 / 2; i++) {
    const int ok = deck_movie_step(&p);
    const int sok = deck_movie_step(&sp);
    if (ok != sok) { fprintf(stderr, "stream disagreed at step %d\n", i); return 1; }
    if (!ok) { printf("step %d: stopped\n", i); break; }
    const uint32_t hash = fnv1a(grid, cells);
    if (hash != fnv1a(sgrid, cells)) {
      fprintf(stderr, "stream frame %d differs from buffered\n", i);
      return 1;
    }
    uint32_t lit = 0;
    for (uint32_t c = 0; c < cells; c++) if (grid[c]) lit++;
    printf("%d %08x %u\n", i, hash, lit);
  }
  fclose(sf);
  return 0;
}
