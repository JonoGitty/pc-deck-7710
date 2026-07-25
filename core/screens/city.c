/* Screen 5 — EQ cityscape: coarse tower blocks with a rising scan sweep.
 * Ported from vizCity in legacy/web/viz.js. */
#include "../screens.h"

/* Bass gets the broad towers. Widths are for a 192-wide grid and scale from it. */
static const int TOWER_W[DECK_BANDS] = { 20, 16, 14, 12, 12, 10, 10, 10, 10, 10, 10, 8, 8 };

/* The sweep is animation state that survives between frames, exactly as the
 * module-level _sweepY does in the JS. */
static double sweep_y = 60.0;

void deck_screen_city_reset(void) { sweep_y = 60.0; }

void deck_screen_city(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int bot = (int)g->h - 1;
  const int big = deck_big_top(g);
  const int span = bot - big;

  int x0 = 2;
  for (int b = 0; b < DECK_BANDS; b++) {
    const int tw = TOWER_W[b] * (int)g->w / 192;

    int h = deck_round(v->bands[b] * span);
    int top = bot - h;
    for (int y = bot; y > top; y--)
      for (int x = 0; x < tw - 2; x++)
        deck_set(fb, x0 + x, y, y == top + 1 ? DECK_HOT : DECK_MAIN);

    int pk = bot - deck_round(v->peaks[b] * span);
    if (pk < bot)
      for (int x = 2; x < tw - 4; x++) deck_set(fb, x0 + x, pk, deck_thin_inten(g, DECK_HOT));

    x0 += tw;
  }

  sweep_y -= 0.35;
  if (sweep_y < big - 14) sweep_y = 62.0;
  int sy = deck_round(sweep_y);
  if (sy >= big && sy <= bot)
    for (int x = 0; x < (int)g->w; x += 2) deck_set(fb, x, sy, deck_thin_inten(g, DECK_DIM));
}
