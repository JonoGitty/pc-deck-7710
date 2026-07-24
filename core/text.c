#include "text.h"
#include "fold_table.h"

uint32_t deck_utf8_next(const char **p) {
  const unsigned char *s = (const unsigned char *)*p;
  uint32_t c = s[0];
  int extra;
  if (c < 0x80)                { *p += 1; return c; }
  else if ((c & 0xe0) == 0xc0) { c &= 0x1f; extra = 1; }
  else if ((c & 0xf0) == 0xe0) { c &= 0x0f; extra = 2; }
  else if ((c & 0xf8) == 0xf0) { c &= 0x07; extra = 3; }
  else                         { *p += 1; return 0xfffd; }

  for (int i = 1; i <= extra; i++) {
    if ((s[i] & 0xc0) != 0x80) { *p += 1; return 0xfffd; }
    c = (c << 6) | (s[i] & 0x3f);
  }
  *p += extra + 1;
  return c;
}

static const char *fold_one(uint32_t cp) {
  if (cp >= FOLD_LO && cp <= FOLD_HI) return FOLD_LATIN[cp - FOLD_LO];
  for (int i = 0; i < FOLD_EXTRA_N; i++)
    if (FOLD_EXTRA[i].cp == cp) return FOLD_EXTRA[i].out;
  return " ";
}

size_t deck_fold(const char *src, char *dst, size_t cap) {
  if (cap == 0) return 0;
  size_t n = 0;
  int pending_space = 0;                 /* collapse runs, and drop leading */

  while (*src && n + 1 < cap) {
    uint32_t cp = deck_utf8_next(&src);
    const char *rep;
    char one[2];

    if (cp >= 0x20 && cp <= 0x7e) { one[0] = (char)cp; one[1] = 0; rep = one; }
    else                          { rep = fold_one(cp); }

    for (const char *q = rep; *q && n + 1 < cap; q++) {
      if (*q == ' ') { pending_space = 1; continue; }
      if (pending_space && n > 0) { dst[n++] = ' '; if (n + 1 >= cap) break; }
      pending_space = 0;
      dst[n++] = *q;
    }
  }
  dst[n] = 0;                            /* trailing space never emitted */
  return n;
}

static size_t slen(const char *s) { size_t n = 0; while (s[n]) n++; return n; }

void deck_scroll(deck_scroll_t *sc, double dt, const char *text, int cells,
                 char *out, size_t outcap) {
  if (outcap == 0) return;
  const int n = (int)slen(text);
  int room = (int)outcap - 1;
  if (cells > room) cells = room;

  if (n <= cells) {                      /* fits: no motion, no state */
    sc->offset = 0;
    int i = 0;
    for (; i < n && i < cells; i++) out[i] = text[i];
    out[i] = 0;
    return;
  }

  const int loop = n + 5;                /* five blank cells before it repeats */
  sc->t += dt;
  if (sc->phase == 0) {
    if (sc->t > 1200) { sc->phase = 1; sc->t = 0; }
  } else {
    sc->offset = (int)(sc->t / 125.0);   /* 8 cells per second */
    if (sc->offset >= loop) { sc->phase = 0; sc->t = 0; sc->offset = 0; }
  }

  /* The JS concatenates the padded text with itself and slices; index into
   * that virtual string instead of building it. */
  for (int i = 0; i < cells; i++) {
    int idx = sc->offset + i;
    if (idx >= loop) idx -= loop;
    out[i] = (idx < n) ? text[idx] : ' ';
  }
  out[cells] = 0;
}

int deck_wrap(const char *text, int cells, char *rows, int rowcap, int maxrows) {
  int used = 0;
  char *line = rows;
  int len = 0;
  if (maxrows <= 0 || rowcap <= 1) return 0;
  if (cells > rowcap - 1) cells = rowcap - 1;

  const char *p = text;
  for (;;) {
    while (*p == ' ') p++;                       /* split on whitespace runs */
    if (!*p) break;
    const char *ws = p;
    while (*p && *p != ' ') p++;
    int wlen = (int)(p - ws);

    /* a word longer than a row is hard-split, flushing anything pending */
    while (wlen > cells) {
      if (len) {
        line[len] = 0; used++;
        if (used >= maxrows) return used;
        line = rows + (size_t)used * rowcap; len = 0;
      }
      for (int i = 0; i < cells; i++) line[i] = ws[i];
      line[cells] = 0; used++;
      if (used >= maxrows) return used;
      line = rows + (size_t)used * rowcap; len = 0;
      ws += cells; wlen -= cells;
    }

    if (len == 0) {
      for (int i = 0; i < wlen; i++) line[i] = ws[i];
      len = wlen;
    } else if (len + 1 + wlen <= cells) {
      line[len++] = ' ';
      for (int i = 0; i < wlen; i++) line[len + i] = ws[i];
      len += wlen;
    } else {
      line[len] = 0; used++;
      if (used >= maxrows) return used;
      line = rows + (size_t)used * rowcap; len = 0;
      for (int i = 0; i < wlen; i++) line[i] = ws[i];
      len = wlen;
    }
  }

  if (len) { line[len] = 0; used++; }
  if (used == 0) { rows[0] = 0; used = 1; }      /* always at least one row */
  return used;
}
