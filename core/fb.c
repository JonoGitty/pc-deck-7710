#include "deck.h"

/* No libc: this compiles freestanding for wasm32 and for bare-metal firmware. */

deck_tier_t deck_tier(const deck_geom_t *g) {
  if (g->h < 40) return DECK_TIER_STRIP;
  if (g->h < 80) return DECK_TIER_CLASSIC;
  return DECK_TIER_LARGE;
}

void deck_clear(deck_fb_t *fb) {
  size_t n = (size_t)fb->geom->w * fb->geom->h;
  for (size_t i = 0; i < n; i++) fb->px[i] = 0;
}

void deck_set(deck_fb_t *fb, int x, int y, uint8_t inten) {
  const deck_geom_t *g = fb->geom;
  if (x < 0 || y < 0 || x >= (int)g->w || y >= (int)g->h) return;
  size_t i = (size_t)y * g->w + (size_t)x;
  if (inten > fb->px[i]) fb->px[i] = inten;
}

uint8_t deck_get(const deck_fb_t *fb, int x, int y) {
  const deck_geom_t *g = fb->geom;
  if (x < 0 || y < 0 || x >= (int)g->w || y >= (int)g->h) return 0;
  return fb->px[(size_t)y * g->w + (size_t)x];
}

void deck_wipe_from(deck_fb_t *fb, int edge) {
  const deck_geom_t *g = fb->geom;
  if (edge < 0) edge = 0;
  for (int y = 0; y < (int)g->h; y++)
    for (int x = edge; x < (int)g->w; x++)
      fb->px[(size_t)y * g->w + (size_t)x] = 0;
}
