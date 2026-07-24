/* Screen 6 — waterfall memory: chunky spectral history climbing upward,
 * cooling as it rises. Ported from vizWaterfall in legacy/web/viz.js. */
#include "../screens.h"

void deck_screen_waterfall(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int cellW = (int)g->w / DECK_WF_COLS;      /* 6 at 192 wide */

  for (int r = 0; r < DECK_WF_ROWS; r++) {
    if (r >= v->wfCount) continue;                 /* history not deep yet */
    for (int c = 0; c < DECK_WF_COLS; c++) {
      float val = v->wfHist[r][c];
      if (val < 0.28f) continue;

      uint8_t i = val > 0.82f ? DECK_HOT : (val > 0.55f ? DECK_MAIN : DECK_DIM);
      if (r > 3 && i > DECK_MAIN) i = DECK_MAIN;   /* memory cools as it climbs */
      if (r > 7) i = DECK_DIM;

      int y = (int)g->h - 2 - r * 2, x = c * cellW;
      for (int dx = 0; dx < cellW - 1; dx++) deck_set(fb, x + dx, y, i);
    }
  }
}
