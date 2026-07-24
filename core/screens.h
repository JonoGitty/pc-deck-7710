#ifndef DECK_SCREENS_H
#define DECK_SCREENS_H

#include "deck.h"
#include "state.h"
#include "meta.h"
#include "text.h"

/* Visualiser strip bounds, derived from the grid rather than hard-coded.
 * At the legacy 192x48 these give 32 and 47, matching the JS constants. */
static inline int deck_viz_top(const deck_geom_t *g) { return (int)g->h - 16; }
static inline int deck_viz_bot(const deck_geom_t *g) { return (int)g->h - 1; }
static inline int deck_big_top(const deck_geom_t *g) { return (int)g->h / 2; }

void deck_screen_spectrum(deck_fb_t *fb, const deck_state_t *v);
void deck_screen_mirror(deck_fb_t *fb, const deck_state_t *v);
void deck_screen_scope(deck_fb_t *fb, const deck_state_t *v);
void deck_screen_city(deck_fb_t *fb, const deck_state_t *v);
void deck_screen_waterfall(deck_fb_t *fb, const deck_state_t *v);
void deck_screen_vu(deck_fb_t *fb, const deck_state_t *v);
void deck_screen_3d(deck_fb_t *fb, const deck_state_t *v);

/* The metadata screens also read track state; cover additionally owns a
 * marquee, so it takes the scroller and a frame delta. */
void deck_screen_cover(deck_fb_t *fb, const deck_state_t *v, const deck_meta_t *m,
                       deck_scroll_t *sc, double dt);
void deck_screen_lyrics(deck_fb_t *fb, const deck_state_t *v, const deck_meta_t *m,
                        double now_ms);

void deck_progress_bar(deck_fb_t *fb, int y, int x0, int x1, double frac);
int  deck_lyric_rows(const deck_geom_t *g);

/* City carries a rising sweep between frames; reset it for deterministic runs. */
void deck_screen_city_reset(void);

#endif /* DECK_SCREENS_H */
