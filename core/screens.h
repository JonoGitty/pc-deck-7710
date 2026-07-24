#ifndef DECK_SCREENS_H
#define DECK_SCREENS_H

#include "deck.h"
#include "state.h"

/* Visualiser strip bounds, derived from the grid rather than hard-coded.
 * At the legacy 192x48 these give 32 and 47, matching the JS constants. */
static inline int deck_viz_top(const deck_geom_t *g) { return (int)g->h - 16; }
static inline int deck_viz_bot(const deck_geom_t *g) { return (int)g->h - 1; }
static inline int deck_big_top(const deck_geom_t *g) { return (int)g->h / 2; }

void deck_screen_spectrum(deck_fb_t *fb, const deck_state_t *v);

#endif /* DECK_SCREENS_H */
