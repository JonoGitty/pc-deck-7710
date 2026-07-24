/* Screen 3 — twin VU needles with overshoot and recoil.
 * Ported from vizVU in legacy/web/viz.js.
 *
 * Uses core/trig.c rather than libm so every target places the needle on the
 * same dot. See trig.h for why that matters. */
#include "../screens.h"
#include "../font.h"
#include "../trig.h"

static void needle(deck_fb_t *fb, int cx, double v, const char *label, double sc) {
  const deck_geom_t *g = fb->geom;
  const int cy = (int)g->h + 10;                 /* pivot sits below the panel */
  const double th = ((v - 0.5) * 100.0) * DECK_PI / 180.0;

  /* scale arc, -50..+50 degrees, last mark in clip red */
  for (int d = -50; d <= 50; d += 10) {
    double t = d * DECK_PI / 180.0;
    int x = deck_round(cx + 32 * sc * deck_sin(t));
    int y = deck_round(cy - 32 * sc * deck_cos(t));
    deck_set(fb, x, y, d == 50 ? DECK_CLIP : deck_thin_inten(g, DECK_DIM));
    if (d == 50) deck_set(fb, x - 1, y, DECK_CLIP);
  }

  deck_text3(fb, cx - 34, (int)g->h - 6, "-", deck_thin_inten(g, DECK_DIM));
  deck_text3(fb, cx + 30, (int)g->h - 6, "+", deck_thin_inten(g, DECK_DIM));

  /* The 0.7 step accumulates in floating point exactly as the JS loop does;
   * keeping the loop in unscaled units means sc == 1.0 reproduces it bit for
   * bit on the legacy grid. */
  for (double rr = 12; rr <= 30; rr += 0.7) {
    double r = rr * sc;
    int x = deck_round(cx + r * deck_sin(th));
    int y = deck_round(cy - r * deck_cos(th));
    deck_set(fb, x, y, deck_thin_inten(g, DECK_HOT));
  }

  deck_text3(fb, cx - 1, (int)g->h - 5, label, deck_thin_inten(g, DECK_MAIN));
}

void deck_screen_vu(deck_fb_t *fb, const deck_state_t *v) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w;
  const double sc = (double)g->h / 48.0;         /* 1.0 on the legacy grid */

  needle(fb, W * 52 / 192, v->vuL, "L", sc);
  needle(fb, W * 140 / 192, v->vuR, "R", sc);

  deck_text3(fb, W * 89 / 192, deck_big_top(g) + 1, "VU", deck_thin_inten(g, DECK_DIM));
  if (v->clip) deck_text3(fb, W * 85 / 192, (int)g->h - 5, "OVER", DECK_CLIP);
}
