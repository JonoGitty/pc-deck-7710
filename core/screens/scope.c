/* Screen 4 — dot-matrix oscilloscope with phosphor persistence.
 * Ported from vizScope in legacy/web/viz.js. */
#include "../screens.h"

void deck_screen_scope(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  const int big = deck_big_top(g);
  const int cy = H - 12, amp = 11;

  for (int x = 0; x < W; x += 8) deck_set(fb, x, cy, DECK_DIM);          /* centreline */
  for (int x = 0; x < W; x += 48)                                        /* timing ticks */
    for (int y = big + 1; y < H; y += 4) deck_set(fb, x, y, DECK_DIM);

  /* Oldest trace first so the live one paints over it. */
  for (int t = 0; t < DECK_TRACES + 1; t++) {
    const double *tr;
    uint8_t base;
    if (t < DECK_TRACES) {
      if (t >= v->waveHistCount) continue;
      tr = v->waveHist[t];
      base = DECK_DIM;
    } else {
      tr = v->wave;
      base = DECK_MAIN;
    }

    for (int i = 0; i < DECK_WAVE; i++) {
      int y = deck_round(cy - tr[i] * v->scopeGain * amp);
      if (y < big) y = big;
      if (y > H - 1) y = H - 1;
      int x = (i * W) / DECK_WAVE;                 /* 2i on a 192-wide grid */
      double a = tr[i] < 0 ? -tr[i] : tr[i];
      deck_set(fb, x, y, base);
      deck_set(fb, x + 1, y, (base == DECK_MAIN && a > 0.6) ? DECK_HOT : base);
    }
  }
}
