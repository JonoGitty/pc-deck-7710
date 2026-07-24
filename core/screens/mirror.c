/* Screen 2 — mirrored L/R spectrum, low frequencies at the centre.
 * Ported from vizMirror in legacy/web/viz.js. */
#include "../screens.h"
#include "../font.h"

void deck_screen_mirror(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int top = deck_viz_top(g), bot = deck_viz_bot(g);
  const int segH = 2, segs = 8;
  const int cx = (int)g->w / 2;

  /* JS uses pitch 7, bar 5 against a 96-dot half-width; derived this way those
   * are exactly what a 192-wide grid produces. */
  const int pitch = (cx - 5) / DECK_BANDS;
  const int barW  = pitch - 2;

  for (int b = 0; b < DECK_BANDS; b++) {
    const int xs[2] = { cx - (b + 1) * pitch, cx + b * pitch + 2 };
    const double vv[2] = { v->bandsL[b], v->bandsR[b] };

    for (int side = 0; side < 2; side++) {
      int lit = deck_round(vv[side] * segs);
      for (int s = 0; s < lit; s++) {
        int y = bot - s * segH;
        uint8_t i = (s >= segs - 1) ? DECK_HOT : DECK_MAIN;
        for (int x = 0; x < barW; x++) deck_set(fb, xs[side] + x, y - 1, i);
        for (int x = 0; x < barW; x++) deck_set(fb, xs[side] + x, y, i);
      }
    }
  }

  for (int y = top; y <= bot; y += 2) deck_set(fb, cx - 1, y, deck_thin_inten(g, DECK_DIM));
  const uint8_t ti = deck_thin_inten(g, DECK_DIM);
  deck_text3(fb, 2, bot - 4, "L", ti);
  deck_text3(fb, (int)g->w - 5, bot - 4, "R", ti);
}
