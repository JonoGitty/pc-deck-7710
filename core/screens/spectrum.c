/* Screen 1 — classic 13-band segmented spectrum with peak-hold dots.
 * Ported from vizSpectrum in legacy/web/viz.js. */
#include "../screens.h"

void deck_screen_spectrum(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int bot = deck_viz_bot(g);
  const int segH = 2, segs = 8;

  /* The JS hard-codes pitch 14, bar 11, margin 5 for a 192-wide grid. Derived
   * this way they reproduce those numbers exactly and generalise to others. */
  const int pitch = ((int)g->w - 4) / DECK_BANDS;
  const int barW  = pitch - 3;
  const int x0    = ((int)g->w - DECK_BANDS * pitch) / 2;

  for (int b = 0; b < DECK_BANDS; b++) {
    int lit = deck_round(v->bands[b] * segs);
    for (int s = 0; s < lit; s++) {
      int y = bot - 1 - s * segH;
      uint8_t i = (s >= segs - 1) ? DECK_HOT : DECK_MAIN;
      for (int dy = 0; dy < segH; dy++)
        for (int x = 0; x < barW; x++)
          deck_set(fb, x0 + b * pitch + x, y - dy + 1, i);
    }

    int pk = deck_round(v->peaks[b] * segs);
    if (pk > 0) {
      int y = bot - (pk - 1) * segH - segH;
      for (int x = 2; x < barW - 2; x++)
        deck_set(fb, x0 + b * pitch + x, y, DECK_HOT);
    }
  }
}
