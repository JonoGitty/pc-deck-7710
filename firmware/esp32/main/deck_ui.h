/* Which screen is on, and the idle machine. Ported from legacy/web/app.js —
 * see deck_ui.c for why that is a port rather than a redesign. */
#ifndef DECK_UI_H
#define DECK_UI_H

#include "deck.h"
#include "meta.h"
#include "movie.h"
#include "screens.h"
#include "state.h"
#include "text.h"

#include "deck_input.h"

typedef enum {
  DECK_UI_LIVE = 0,
  DECK_UI_CLOCK,
  DECK_UI_OCEAN,
  DECK_UI_NOWPLAYING,
} deck_ui_state_t;

typedef struct {
  int    mode;
  deck_ui_state_t state;
  double silent_since, np_until, flash_until, demo_next, touched_at;
  int    demo, loud, clip;
  int    wipe;              /* column the wipe edge has reached, -1 when idle */
  uint8_t brightness;
  char   flash[24];

  uint32_t tick;            /* 10 Hz, drives the ocean */
  int      movie, movie_ready;
  deck_movie_t      film;
  deck_movie_play_t play;
  deck_ocean_t      ocean;
  deck_scroll_t     scroll;
} deck_ui_t;

void deck_ui_init(deck_ui_t *u, int mode);
void deck_ui_action(deck_ui_t *u, deck_action_t a, double now);
void deck_ui_track_changed(deck_ui_t *u, double now);
void deck_ui_step(deck_ui_t *u, int audio_live, double now, double dt);
void deck_ui_draw(deck_ui_t *u, deck_fb_t *fb, deck_state_t *v,
                  deck_meta_t *m, double now, double dt);
int         deck_ui_mode_count(void);
const char *deck_ui_mode_name(int m);

#endif /* DECK_UI_H */
