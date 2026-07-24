#include "movie.h"

static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

/* The built-in source: a flat buffer. Bounds-checks here rather than at every
 * call site, which is what lets the decoder treat a short read as "the movie
 * ended" and stop caring whether the file was truncated or merely finished. */
static uint32_t src_mem(void *ctx, uint32_t off, uint8_t *dst, uint32_t n) {
  const deck_movie_t *m = (const deck_movie_t *)ctx;
  if (off >= m->src.size) return 0;
  uint32_t avail = m->src.size - off;
  if (n > avail) n = avail;
  for (uint32_t i = 0; i < n; i++) dst[i] = m->mem[off + i];
  return n;
}

int deck_movie_open_src(deck_movie_t *m, const deck_movie_src_t *src) {
  if (!src || !src->read || src->size < 14) return 0;

  uint8_t hdr[14];
  if (src->read(src->ctx, 0, hdr, 14) != 14) return 0;
  if (hdr[0] != 'D' || hdr[1] != 'M' || hdr[2] != 'V' || hdr[3] != '1') return 0;

  /* Assign before reading the name: with a memory source, ctx points at `m`
   * itself and src_mem needs src.size populated to bound the read. */
  m->src = *src;
  m->w = rd16(hdr + 4);
  m->h = rd16(hdr + 6);
  m->fps = hdr[8];
  m->flags = hdr[9];
  m->frameCount = rd16(hdr + 10);

  const uint16_t nameLen = rd16(hdr + 12);
  if (14u + nameLen > src->size) return 0;
  m->firstFrame = 14u + nameLen;

  uint16_t keep = nameLen > DECK_MOVIE_NAME_MAX ? DECK_MOVIE_NAME_MAX : nameLen;
  if (keep && m->src.read(m->src.ctx, 14, (uint8_t *)m->name, keep) != keep) return 0;
  m->name[keep] = 0;
  m->nameLen = (uint8_t)keep;

  if (m->w == 0 || m->h == 0 || m->fps == 0) return 0;
  if ((uint32_t)m->w * m->h > 65535u) return 0;   /* runs address the grid as u16 */
  return 1;
}

int deck_movie_open(deck_movie_t *m, const uint8_t *data, uint32_t size) {
  if (!data) return 0;
  m->mem = data;
  deck_movie_src_t src;
  src.read = src_mem;
  src.ctx = m;                    /* see the note on deck_movie_t.mem */
  src.size = size;
  return deck_movie_open_src(m, &src);
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

/* Runs are pulled in batches rather than one at a time, so a source backed by
 * flash or an SD card does one read per 64 runs instead of one per run. 320
 * bytes of stack; still no allocation anywhere in the decoder. */
#define RUN_BATCH 64

int deck_movie_step(deck_movie_play_t *p) {
  const deck_movie_t *m = p->movie;
  if (!m) return 0;

  if (p->frame >= m->frameCount) {
    if (!(m->flags & DECK_MOVIE_LOOP)) { p->done = 1; return 0; }
    deck_movie_start(p, m, p->grid);          /* deltas: loop by replaying */
  }

  uint8_t hdr[2];
  if (m->src.read(m->src.ctx, p->cursor, hdr, 2) != 2) { p->done = 1; return 0; }
  uint16_t runs = rd16(hdr);
  uint32_t at = p->cursor + 2;
  /* Checked up front, as it always was: a frame is applied whole or not at
   * all, so a truncated file cannot leave half a frame on the panel. */
  if (at + (uint32_t)runs * 5u > m->src.size) { p->done = 1; return 0; }

  const uint32_t cells = (uint32_t)m->w * m->h;
  uint8_t buf[RUN_BATCH * 5];
  while (runs) {
    const uint16_t batch = runs > RUN_BATCH ? RUN_BATCH : runs;
    const uint32_t want = (uint32_t)batch * 5u;
    if (m->src.read(m->src.ctx, at, buf, want) != want) { p->done = 1; return 0; }
    for (uint16_t r = 0; r < batch; r++) {
      const uint8_t *e = buf + r * 5;
      const uint16_t start = rd16(e);
      const uint16_t len = rd16(e + 2);
      if ((uint32_t)start + len > cells) continue;    /* malformed run, skip */
      const uint8_t v = e[4] > DECK_CLIP ? DECK_CLIP : e[4];
      for (uint16_t i = 0; i < len; i++) p->grid[start + i] = v;
    }
    at += want;
    runs = (uint16_t)(runs - batch);
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
