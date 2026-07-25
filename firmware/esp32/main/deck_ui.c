/* Which screen is on, and the era-faithful idle behaviour.
 *
 * This is the direct counterpart of composeLive() and the idle machine in
 * legacy/web/app.js, and it is deliberately a port rather than a fresh design:
 * the PC deck's behaviour is the specification, it has been lived with, and
 * anything that felt wrong there was already fixed.
 *
 * The idle rules, which are the part people notice:
 *
 *   music stops  ->  3 s  ->  the clock
 *                ->  12 s ->  the dolphins take over
 *   music back   ->  a hard horizontal wipe back to the analyser
 *
 * with one exception: the two metadata screens hold through a pause instead of
 * handing over, because they are about the track rather than about the audio,
 * and dropping the album art the moment someone pauses to talk is annoying in
 * a way the wipe is not.
 */
#include "deck_ui.h"

#include <stdio.h>
#include <string.h>

#include "deck_diag.h"
#include "font.h"
#include "screens.h"

/* Mirrors MODES[] in legacy/web/viz.js. Same order, so a preset button means
 * the same thing on both, and `big` decides how much chrome the screen gets:
 * false = short visualiser with title and artist above it, true = tall
 * visualiser with the title only, full = the screen owns the panel. */
typedef enum { CHROME_SHORT = 0, CHROME_TALL, CHROME_NONE } chrome_t;

static const struct { const char *name; chrome_t chrome; int hold_idle; } MODES[] = {
    {"SPECTRUM ANALYZER", CHROME_SHORT, 0},
    {"MIRROR SPECTRUM",   CHROME_SHORT, 0},
    {"VU METER",          CHROME_TALL,  0},
    {"OSCILLOSCOPE",      CHROME_TALL,  0},
    {"CITYSCAPE EQ",      CHROME_TALL,  0},
    {"WATERFALL",         CHROME_TALL,  0},
    {"3D SPECTRUM",       CHROME_TALL,  0},
    {"OCEAN CRUISE",      CHROME_NONE,  0},
    {"ALBUM ART",         CHROME_NONE,  1},
    {"LYRICS",            CHROME_NONE,  1},
    {"MOVIE",             CHROME_NONE,  1},
};
#define NMODES ((int)(sizeof MODES / sizeof *MODES))

int deck_ui_mode_count(void) { return NMODES; }
const char *deck_ui_mode_name(int m) {
  return (m >= 0 && m < NMODES) ? MODES[m].name : "";
}

void deck_ui_init(deck_ui_t *u, int mode) {
  memset(u, 0, sizeof *u);
  u->mode = (mode >= 0 && mode < NMODES) ? mode : 0;
  u->state = DECK_UI_LIVE;
  u->wipe = -1;
  deck_ocean_reset(&u->ocean);
}

void deck_ui_action(deck_ui_t *u, deck_action_t a, double now) {
  u->touched_at = now;
  switch (a) {
  case DECK_ACT_MODE_NEXT: u->mode = (u->mode + 1) % NMODES; u->demo = 0; break;
  case DECK_ACT_MODE_PREV: u->mode = (u->mode + NMODES - 1) % NMODES; u->demo = 0; break;
  case DECK_ACT_ART:    u->mode = 8; u->demo = 0; break;
  case DECK_ACT_LYRICS: u->mode = 9; u->demo = 0; break;
  case DECK_ACT_OCEAN:  u->mode = 7; u->demo = 0; break;
  case DECK_ACT_MOVIE_NEXT:
    if (u->mode == 10) u->movie++; else u->mode = 10;
    u->demo = 0;
    break;
  case DECK_ACT_DEMO:
    u->demo = !u->demo;
    u->demo_next = now + 8.0;
    break;
  case DECK_ACT_SRC:
    snprintf(u->flash, sizeof u->flash, "BLUETOOTH");
    u->flash_until = now + 1.5;
    break;
  /* The knob dims. It is the one control whose behaviour a driver should be
   * able to guess without looking, and on every deck this shape it dims. */
  case DECK_ACT_ENC_CW:
    u->brightness = (u->brightness >= 95) ? 100 : u->brightness + 5;
    snprintf(u->flash, sizeof u->flash, "DIM %u", (unsigned)u->brightness);
    u->flash_until = now + 1.0;
    break;
  case DECK_ACT_ENC_CCW:
    u->brightness = (u->brightness <= 10) ? 5 : u->brightness - 5;
    snprintf(u->flash, sizeof u->flash, "DIM %u", (unsigned)u->brightness);
    u->flash_until = now + 1.0;
    break;
  default: break;
  }
}

void deck_ui_track_changed(deck_ui_t *u, double now) {
  /* The NOW PLAYING interstitial, unchanged from the PC deck: two seconds of
   * the sleeve and the title on every track change, including while the album
   * art and lyrics screens are up. It is the single most-liked thing about
   * the deck and it stays exactly as it is. */
  u->state = DECK_UI_NOWPLAYING;
  u->np_until = now + 2.3;
}

/* --- the idle machine --------------------------------------------------- */
void deck_ui_step(deck_ui_t *u, int audio_live, double now, double dt) {
  (void)dt;
  if (u->demo && now > u->demo_next) {
    u->mode = (u->mode + 1) % NMODES;
    u->demo_next = now + 8.0;
  }

  if (u->state == DECK_UI_NOWPLAYING) {
    if (now > u->np_until) u->state = DECK_UI_LIVE;
    return;
  }

  if (audio_live) {
    if (u->state != DECK_UI_LIVE) {
      /* The wipe. A hard vertical edge sweeping across, not a fade — a fade on
       * five intensity levels is a smear, and the wipe is what the period
       * units did because it is what a dot-matrix panel can do cleanly. */
      u->wipe = 0;
      u->state = DECK_UI_LIVE;
      deck_diag_event(DECK_SUB_AUDIO, "idle", "state=live");
    }
    u->silent_since = 0;
    return;
  }

  if (!u->silent_since) u->silent_since = now;
  const double quiet = now - u->silent_since;

  if (MODES[u->mode].hold_idle) return;   /* art and lyrics hold through a pause */

  if (quiet > 12.0 && u->state != DECK_UI_OCEAN) {
    u->state = DECK_UI_OCEAN;
    deck_diag_event(DECK_SUB_AUDIO, "idle", "state=ocean");
  } else if (quiet > 3.0 && u->state == DECK_UI_LIVE) {
    u->state = DECK_UI_CLOCK;
    deck_diag_event(DECK_SUB_AUDIO, "idle", "state=clock");
  }
}

/* --- drawing ------------------------------------------------------------ */
static void chrome(deck_fb_t *fb, const deck_meta_t *m, const deck_ui_t *u,
                   chrome_t c, double now) {
  const int W = fb->geom->w;

  deck_text3(fb, 2, 0, m->app[0] ? m->app : "BT", DECK_MAIN);
  const int px = 4 + deck_width3(m->app[0] ? m->app : "BT");
  if (m->status == DECK_PLAYING) {
    static const uint8_t PLAY[5] = {4, 6, 7, 6, 4};
    for (int r = 0; r < 5; r++)
      for (int col = 0; col < 3; col++)
        if (PLAY[r] & (4 >> col)) deck_set(fb, px + col, r, DECK_MAIN);
  }

  deck_text3(fb, W * 130 / 192, 0, "ST", m->status == DECK_PLAYING ? DECK_MAIN : DECK_DIM);
  deck_text3(fb, W * 140 / 192, 0, "DEMO", u->demo ? DECK_HOT : DECK_DIM);
  deck_text3(fb, W * 158 / 192, 0, "LOUD", u->loud ? DECK_MAIN : DECK_DIM);
  deck_text3(fb, W * 176 / 192, 0, "OVER", u->clip ? DECK_CLIP : DECK_DIM);

  const char *title = m->title[0] ? m->title : "DECK 7710";
  deck_text5(fb, 2, 8, title, DECK_MAIN, 2);

  if (c == CHROME_SHORT) {
    if (now < u->flash_until) deck_text5(fb, 2, 24, u->flash, DECK_HOT, 1);
    else                      deck_text5(fb, 2, 24, m->artist, DECK_DIM, 1);
  } else if (now < u->flash_until) {
    deck_text3(fb, 2, 25, u->flash, DECK_HOT);
  }
}

void deck_ui_draw(deck_ui_t *u, deck_fb_t *fb, deck_state_t *v,
                  deck_meta_t *m, double now, double dt) {
  deck_clear(fb);

  /* Idle overrides the selected mode without changing it, so when the music
   * comes back the deck returns to the screen you chose rather than to
   * whatever the idle machine last showed. */
  int mode = u->mode;
  if (u->state == DECK_UI_OCEAN) mode = 7;
  else if (u->state == DECK_UI_CLOCK) mode = -1;
  else if (u->state == DECK_UI_NOWPLAYING) mode = -2;

  if (mode == -1) {
    char hm[8];
    snprintf(hm, sizeof hm, "%02d:%02d", (int)(now / 3600) % 24, (int)(now / 60) % 60);
    deck_text5(fb, (fb->geom->w - deck_width5(hm, 3)) / 2,
               (fb->geom->h - 21) / 2, hm, DECK_MAIN, 3);
  } else if (mode == -2) {
    deck_text3(fb, 2, 1, "NOW PLAYING", DECK_HOT);
    deck_text5(fb, 2, 10, m->title, DECK_MAIN, 2);
    deck_text5(fb, 2, 26, m->artist, DECK_DIM, 1);
  } else {
    const chrome_t c = MODES[mode].chrome;
    if (c != CHROME_NONE) chrome(fb, m, u, c, now);
    switch (mode) {
    case 0: deck_screen_spectrum(fb, v); break;
    case 1: deck_screen_mirror(fb, v); break;
    case 2: deck_screen_vu(fb, v); break;
    case 3: deck_screen_scope(fb, v); break;
    case 4: deck_screen_city(fb, v); break;
    case 5: deck_screen_waterfall(fb, v); break;
    case 6: deck_screen_3d(fb, v); break;
    case 7: deck_screen_ocean(fb, v, &u->ocean, u->tick); break;
    case 8: deck_screen_cover(fb, v, m, &u->scroll, dt * 1000.0); break;
    case 9: deck_screen_lyrics(fb, v, m, now * 1000.0); break;
    case 10:
      if (u->movie_ready) deck_movie_blit(fb, &u->play);
      else deck_text3(fb, 2, fb->geom->h / 2, "NO MOVIES INSTALLED", DECK_DIM);
      break;
    default: break;
    }
  }

  /* The wipe runs last so it cuts whatever was drawn, which is what makes it
   * read as the panel changing rather than as a screen animating. */
  if (u->wipe >= 0) {
    deck_wipe_from(fb, u->wipe);
    u->wipe += (int)(fb->geom->w * dt * 4.0) + 1;
    if (u->wipe >= fb->geom->w) u->wipe = -1;
  }
}
