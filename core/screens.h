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

/* ---- the telephone ------------------------------------------------------
 * Filled in by the firmware from HFP events; the screen itself knows nothing
 * about Bluetooth, which is what lets the PC deck and the simulator drive it
 * from a script. `mic` is 0..255 and exists so the driver can see that the
 * microphone is working — without it a call screen looks identical whether
 * the mic is wired up or still in its bag. */
typedef enum {
  DECK_CALL_IDLE = 0,
  DECK_CALL_INCOMING,
  DECK_CALL_OUTGOING,
  DECK_CALL_ACTIVE,
  DECK_CALL_ENDED
} deck_call_state_t;

typedef struct {
  deck_call_state_t state;
  char    name[DECK_STR_MAX];      /* caller ID, empty if the AG sent none */
  char    number[DECK_STR_MAX];
  int     secs;                    /* call duration, or how long it has rung */
  uint8_t mic;                     /* live microphone level, 0..255 */
} deck_call_t;

void deck_screen_call(deck_fb_t *fb, const deck_call_t *c, double now_ms);

/* ---- the tuner ----------------------------------------------------------
 * Filled in by the firmware from an Si4735 (or whatever tuner is fitted); the
 * screen knows nothing about I2C. Frequencies are in kHz throughout — one
 * unit for both bands, so nothing has to remember which scale it is holding.
 * `name` and `text` are RDS and are empty until the station sends them, which
 * on a weak signal can be never. */
#define DECK_PRESETS 6

typedef enum { DECK_BAND_FM = 0, DECK_BAND_AM } deck_band_t;

typedef struct {
  deck_band_t band;
  int      freq_khz;
  int      band_lo_khz, band_hi_khz;
  int      preset;                  /* 1..DECK_PRESETS, or 0 for none */
  int      n_presets;
  int      preset_khz[DECK_PRESETS];
  uint8_t  rssi;                    /* 0..255 */
  uint8_t  stereo;
  char     name[DECK_STR_MAX];      /* RDS programme service, 8 chars */
  char     text[DECK_STR_MAX];      /* RDS radio text, up to 64 */
} deck_radio_t;

void deck_screen_radio(deck_fb_t *fb, const deck_radio_t *r,
                       deck_scroll_t *sc, double dt);

/* ---- ocean --------------------------------------------------------------
 * The only screen with a world that persists between frames. The caller owns
 * the state and advances it by bumping `tick` — the scene steps once per tick
 * however often it is rendered, which is what keeps the movie at 10 fps. */
#define DECK_BUBBLE_MAX 14
#define DECK_SPRAY_MAX  32

typedef struct { int x, y; } deck_bubble_t;
typedef struct { double x, y, vx, vy; int life; } deck_spray_t;

typedef struct {
  int    len;
  double depth, x, y0;
  int    t, mode, jt;                 /* mode: 0 swim, 1 breach */
  int    breachEvery, breachOffset, wantBreach;
  double ry, rang;                    /* what the last step decided to draw */
  int    rflex;
  uint8_t rinten;
} deck_dolphin_t;

typedef struct {
  deck_dolphin_t pod[2];
  deck_bubble_t  bubbles[DECK_BUBBLE_MAX];
  deck_spray_t   spray[DECK_SPRAY_MAX];
  int            nBubbles, nSpray;
  int            lastTick;
  double         lastBass;
} deck_ocean_t;

void deck_ocean_reset(deck_ocean_t *o);
void deck_screen_ocean(deck_fb_t *fb, const deck_state_t *v, deck_ocean_t *o,
                       uint32_t tick);
int  deck_lyric_rows(const deck_geom_t *g);

/* City carries a rising sweep between frames; reset it for deterministic runs. */
void deck_screen_city_reset(void);

#endif /* DECK_SCREENS_H */
