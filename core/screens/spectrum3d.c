/* Screen 7 — perspective-receding analyzer landscape.
 * Front ridge is the live spectrum, ranks behind are waterfall history
 * shrinking toward a vanishing point. Painter's algorithm front-to-back with a
 * per-column skyline for hidden-line removal.
 * Ported from viz3D in legacy/web/viz.js. */
#include "../screens.h"

#define MAX_COLS 512

void deck_screen_3d(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, bot = (int)g->h - 1;
  const int floorY = deck_big_top(g) - 1;        /* 23 on the legacy grid */

  /* int8_t, matching the JS Int8Array — 127 means "nothing drawn here yet". */
  int8_t skyline[MAX_COLS];
  for (int i = 0; i < W && i < MAX_COLS; i++) skyline[i] = 127;

  for (int d = 0; d < DECK_WF_ROWS; d++) {
    const float *row = (d == 0) ? 0 : v->wfHist[d - 1];
    if (d > 0 && d - 1 >= v->wfCount) break;

    const int inset = d * 6;
    const int rw = W - inset * 2;
    if (rw < 24) break;

    const double yBase = bot - d * 1.8;
    const double hMax = 15 - d * 0.7;
    const uint8_t inten = (d == 0) ? DECK_HOT : (d < 5 ? DECK_MAIN : DECK_DIM);

    int prevY = -1;
    for (int x = inset; x < W - inset; x++) {
      const double u = (double)(x - inset) / rw;
      double val;
      if (row) {
        int c = deck_round(u * (DECK_WF_COLS - 1));
        if (c > DECK_WF_COLS - 1) c = DECK_WF_COLS - 1;
        val = row[c];
      } else {
        double f = u * 12;
        int i = (int)f;                          /* u < 1, so floor == trunc */
        if (i > 11) i = 11;
        double fr = f - i;
        val = v->bands[i] * (1 - fr) + v->bands[i + 1] * fr;
      }

      int y = deck_round(yBase - val * hMax);
      if (y < floorY) y = floorY;

      const int lo = (prevY < 0) ? y : (prevY < y ? prevY : y);
      const int hi = (prevY < 0) ? y : (prevY > y ? prevY : y);
      for (int yy = lo; yy <= hi; yy++)
        if (yy < skyline[x]) deck_set(fb, x, yy, deck_thin_inten(g, inten));
      if (y < skyline[x]) skyline[x] = (int8_t)y;
      prevY = y;
    }
  }
}
