/* Screen 9 — album art, full time.
 * The dithered sleeve at full panel height, with the track beside it and a
 * slim analyzer along the bottom so it still breathes with the music.
 * Ported from vizCover in legacy/web/viz.js. */
#include "../screens.h"
#include "../font.h"
#include "../text.h"

static void time_str(double sec, char *out) {
  int s = (int)(sec < 0 ? 0 : sec);
  int m = s / 60;
  s %= 60;
  int n = 0;
  if (m >= 100) { out[n++] = (char)('0' + (m / 100) % 10); }
  if (m >= 10)  { out[n++] = (char)('0' + (m / 10) % 10); }
  out[n++] = (char)('0' + m % 10);
  out[n++] = ':';
  out[n++] = (char)('0' + s / 10);
  out[n++] = (char)('0' + s % 10);
  out[n] = 0;
}

void deck_progress_bar(deck_fb_t *fb, int y, int x0, int x1, double frac) {
  const deck_geom_t *g = fb->geom;
  if (frac < 0) frac = 0;
  if (frac > 1) frac = 1;
  const int edge = x0 + deck_round((x1 - x0) * frac);
  const uint8_t lit = deck_thin_inten(g, DECK_MAIN);
  const uint8_t dim = deck_thin_inten(g, DECK_DIM);
  for (int x = x0; x <= x1; x++) {
    if (x <= edge) deck_set(fb, x, y, lit);
    else if ((x - x0) % 3 == 0) deck_set(fb, x, y, dim);
  }
}

void deck_screen_cover(deck_fb_t *fb, const deck_state_t *v, const deck_meta_t *m,
                       deck_scroll_t *sc, double dt) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  const int ax = 2, S = H;                    /* sleeve is a full-height square */

  if (m->art && m->artSide > 0) {
    const int a = m->artSide;
    for (int y = 0; y < S; y++)
      for (int x = 0; x < S; x++) {
        /* nearest-neighbour if the dither was made at another size */
        const int sx = (a == S) ? x : (x * a) / S;
        const int sy = (a == S) ? y : (y * a) / S;
        const uint8_t px = m->art[sy * a + sx];
        if (px) deck_set(fb, ax + x, y, px);
      }
  } else {                                     /* empty sleeve */
    const uint8_t e = deck_thin_inten(g, DECK_DIM);
    for (int x = 0; x < S; x++) { deck_set(fb, ax + x, 0, e); deck_set(fb, ax + x, S - 1, e); }
    for (int y = 0; y < S; y++) { deck_set(fb, ax, y, e); deck_set(fb, ax + S - 1, y, e); }
    deck_text5(fb, ax + S / 2 - 5, H * 14 / 48, "\xe2\x99\xaa", DECK_MAIN, 2);
    deck_text3(fb, ax + S / 2 - 12, H * 34 / 48, "NO ART", e);
  }

  const int tx = ax + S + 10;
  if (tx >= W - 12) return;                    /* no room for the text column */
  const int cells = (W - tx - 2) / 6;

  const uint8_t lab = deck_thin_inten(g, DECK_DIM);
  deck_text3(fb, tx, 2, m->app[0] ? m->app : "PC", lab);

  if (m->duration > 0) {
    char el[16], du[16], both[34];
    time_str(m->position, el);
    time_str(m->duration, du);
    int n = 0;
    for (const char *p = el; *p; p++) both[n++] = *p;
    both[n++] = '/';
    for (const char *p = du; *p; p++) both[n++] = *p;
    both[n] = 0;
    deck_text3(fb, W - 2 - deck_width3(both), 2, both, lab);
  }

  char win[DECK_STR_MAX + 8];
  const char *title = m->title[0] ? m->title : "PC DECK 7710";
  deck_scroll(sc, dt, title, cells, win, sizeof win);
  deck_text5(fb, tx, H * 11 / 48, win, DECK_HOT, 1);

  char cut[DECK_STR_MAX];
  int i = 0;
  for (; m->artist[i] && i < cells && i < DECK_STR_MAX - 1; i++) cut[i] = m->artist[i];
  cut[i] = 0;
  deck_text5(fb, tx, H * 21 / 48, cut, DECK_MAIN, 1);

  const int acells = (W - tx - 2) / 4;
  for (i = 0; m->album[i] && i < acells && i < DECK_STR_MAX - 1; i++) cut[i] = m->album[i];
  cut[i] = 0;
  deck_text3(fb, tx, H * 31 / 48, cut, lab);

  /* mini analyzer, segmented like the deck's other bars */
  const int pitch = (W - tx - 2) / DECK_BANDS;
  const int bw = pitch - 2, segs = 3, segH = 2;
  if (bw < 1) return;
  for (int b = 0; b < DECK_BANDS; b++) {
    const int x0 = tx + b * pitch;
    if (x0 + bw > W) break;
    const int lit = deck_round(v->bands[b] * segs);
    for (int s = 0; s < lit; s++)
      for (int dy = 0; dy < segH; dy++)
        for (int x = 0; x < bw; x++)
          deck_set(fb, x0 + x, H - 3 - s * segH - dy, s >= segs - 1 ? DECK_HOT : DECK_MAIN);
    for (int x = 0; x < bw; x++) deck_set(fb, x0 + x, H - 1, lab);   /* baseline rail */
  }
}
