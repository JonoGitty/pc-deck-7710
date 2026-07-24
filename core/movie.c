#include "movie.h"

static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

int deck_movie_open(deck_movie_t *m, const uint8_t *data, uint32_t size) {
  if (!data || size < 14) return 0;
  if (data[0] != 'D' || data[1] != 'M' || data[2] != 'V' || data[3] != '1') return 0;

  m->data = data;
  m->size = size;
  m->w = rd16(data + 4);
  m->h = rd16(data + 6);
  m->fps = data[8];
  m->flags = data[9];
  m->frameCount = rd16(data + 10);
  m->nameLen = (uint8_t)rd16(data + 12);
  if (14u + m->nameLen > size) return 0;
  m->name = (const char *)(data + 14);
  m->firstFrame = 14u + m->nameLen;

  if (m->w == 0 || m->h == 0 || m->fps == 0) return 0;
  if ((uint32_t)m->w * m->h > 65535u) return 0;   /* runs address the grid as u16 */
  return 1;
}

void deck_movie_start(deck_movie_play_t *p, const deck_movie_t *m, uint8_t *grid) {
  p->movie = m;
  p->grid = grid;
  p->cursor = m->firstFrame;
  p->frame = 0;
  p->done = 0;
  const uint32_t n = (uint32_t)m->w * m->h;
  for (uint32_t i = 0; i < n; i++) grid[i] = 0;
}

int deck_movie_step(deck_movie_play_t *p) {
  const deck_movie_t *m = p->movie;
  if (!m) return 0;

  if (p->frame >= m->frameCount) {
    if (!(m->flags & DECK_MOVIE_LOOP)) { p->done = 1; return 0; }
    deck_movie_start(p, m, p->grid);          /* deltas: loop by replaying */
  }

  if (p->cursor + 2 > m->size) { p->done = 1; return 0; }
  const uint16_t runs = rd16(m->data + p->cursor);
  uint32_t at = p->cursor + 2;
  if (at + (uint32_t)runs * 5u > m->size) { p->done = 1; return 0; }

  const uint32_t cells = (uint32_t)m->w * m->h;
  for (uint16_t r = 0; r < runs; r++) {
    const uint16_t start = rd16(m->data + at);
    const uint16_t len = rd16(m->data + at + 2);
    const uint8_t level = m->data[at + 4];
    at += 5;
    if ((uint32_t)start + len > cells) continue;      /* malformed run, skip */
    const uint8_t v = level > DECK_CLIP ? DECK_CLIP : level;
    for (uint16_t i = 0; i < len; i++) p->grid[start + i] = v;
  }

  p->cursor = at;
  p->frame++;
  return 1;
}

void deck_movie_blit(deck_fb_t *fb, const deck_movie_play_t *p) {
  const deck_movie_t *m = p->movie;
  if (!m || !p->grid) return;
  const deck_geom_t *g = fb->geom;

  /* Centre rather than scale: these are dot-matrix animations, and resampling
   * them would blur the exact thing that makes them look like a head unit.
   * A movie wider than the panel crops; narrower letterboxes. */
  const int ox = ((int)g->w - (int)m->w) / 2;
  const int oy = ((int)g->h - (int)m->h) / 2;

  for (int y = 0; y < (int)m->h; y++) {
    const int dy = oy + y;
    if (dy < 0 || dy >= (int)g->h) continue;
    for (int x = 0; x < (int)m->w; x++) {
      const uint8_t v = p->grid[y * m->w + x];
      if (v) deck_set(fb, ox + x, dy, v);
    }
  }
}
