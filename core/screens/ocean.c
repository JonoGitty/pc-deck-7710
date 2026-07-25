/* Screen 8 — the ocean cruise, and the screensaver.
 * Ported from oceanFrame in legacy/web/dolphin.js. The silhouettes come from
 * core/dolphin_rom.h, baked from the original Canvas rasteriser.
 *
 * This is the only screen with a world: dolphins, spray and bubbles persist
 * between frames, and the world advances once per movie tick rather than per
 * render, so the animation stays at 10 fps however fast the panel refreshes.
 */
#include "../screens.h"
#include "../trig.h"
#include "../dolphin_rom.h"

#define WAVE_Y 13

/* Quantise exactly as the JS does — on the raw angle, not a pre-rounded one. */
static const dolphin_mask_t *find_mask(int len, double angleDeg, int flex) {
  int a = deck_round(angleDeg / 10.0) * 10;      /* quantised, movie-bitmap feel */
  if (a < -90) a = -90;
  if (a > 90) a = 90;
  for (int i = 0; i < DOLPHIN_N; i++)
    if (DOLPHIN_MASKS[i].len == len && DOLPHIN_MASKS[i].angle == a &&
        DOLPHIN_MASKS[i].flex == flex)
      return &DOLPHIN_MASKS[i];
  return 0;
}

static void blit(deck_fb_t *fb, const dolphin_mask_t *m, int cx, int cy, uint8_t inten) {
  if (!m) return;
  const int ox = cx - (m->w >> 1), oy = cy - (m->h >> 1);
  const uint8_t *bits = DOLPHIN_BITS + m->off;
  for (int y = 0; y < m->h; y++)
    for (int x = 0; x < m->w; x++) {
      const int i = y * m->w + x;
      if (bits[i >> 3] & (1u << (i & 7))) deck_set(fb, ox + x, oy + y, inten);
    }
}

/* ---- world ------------------------------------------------------------- */
static void dolphin_init(deck_dolphin_t *d, int len, double depth, double x0,
                         int breachEvery, int breachOffset) {
  d->len = len; d->depth = depth; d->x = x0; d->t = 0;
  d->mode = 0; d->jt = 0; d->y0 = depth;
  d->breachEvery = breachEvery; d->breachOffset = breachOffset;
  d->wantBreach = 0;
  d->ry = depth; d->rang = 0; d->rflex = 0; d->rinten = DECK_MAIN;
}

void deck_ocean_reset(deck_ocean_t *o) {
  uint8_t *p = (uint8_t *)o;
  for (size_t i = 0; i < sizeof *o; i++) p[i] = 0;
  o->lastTick = -1;
  o->lastBass = 0;
  o->nBubbles = o->nSpray = 0;
  dolphin_init(&o->pod[0], 30, 30, -20, 150, 40);
  dolphin_init(&o->pod[1], 21, 38, -95, 150, 115);
}

static void spawn_spray(deck_ocean_t *o, double x, double dir) {
  for (int i = 0; i < 7; i++) {
    if (o->nSpray >= DECK_SPRAY_MAX) return;
    deck_spray_t *p = &o->spray[o->nSpray++];
    p->x = x + ((i * 5) % 7) - 3;
    p->y = WAVE_Y - 1;
    p->vx = (double)(((i * 37) % 7) - 3) / 2.2;
    p->vy = -1.4 - ((i * 13) % 3) * 0.5 * dir;
    p->life = 6 + (i % 3);
  }
}

static void step_dolphin(deck_ocean_t *o, deck_dolphin_t *d, int tick) {
  d->t++;
  if (d->mode == 0) {                            /* swimming */
    d->x += 2;
    if (d->x > 225) d->x = -40;
    d->y0 = d->depth + 2 * deck_sin(d->t / 5.0);
    const int due = ((tick + d->breachOffset) % d->breachEvery) == 0;
    if ((due || d->wantBreach) && d->x > 25 && d->x < 140) {
      d->mode = 1; d->jt = 0; d->wantBreach = 0;
    }
    /* The JS returns here even when the breach has just been armed, so the
     * dolphin holds one more swim pose before launching. Falling through
     * instead starts the arc a frame early and shifts the whole breach. */
    d->ry = d->y0;
    d->rang = 8 * deck_sin(d->t / 5.0 + 1);
    d->rflex = (d->t >> 1) % 3;
    d->rinten = DECK_MAIN;
    return;
  }
  /* parabolic breach: launch, clear the wave, re-enter */
  const double V = 4.2, G = 0.34;
  d->jt++;
  d->x += 2.6;
  const double y = d->depth - V * d->jt + 0.5 * G * d->jt * d->jt;
  const double vy = -V + G * d->jt;
  const double prev = d->jt - 1;
  const double prevY = d->depth - V * prev + 0.5 * G * prev * prev;

  if (prevY > WAVE_Y && y <= WAVE_Y) spawn_spray(o, d->x, 1.0);      /* bursting out */
  if (prevY < WAVE_Y && y >= WAVE_Y) spawn_spray(o, d->x, 0.6);      /* re-entry */

  const double span = 2 * V / G;                 /* Math.ceil in the JS */
  const int maxJt = (int)span + ((double)(int)span < span ? 1 : 0);
  if (d->jt >= maxJt || y > d->depth) d->mode = 0;

  d->ry = y;
  d->rang = deck_atan2(vy, 2.6) * 180.0 / DECK_PI;
  d->rflex = 1;
  d->rinten = y < WAVE_Y ? DECK_HOT : DECK_MAIN;
}

/* ---- the scene --------------------------------------------------------- */
void deck_screen_ocean(deck_fb_t *fb, const deck_state_t *v, deck_ocean_t *o,
                       uint32_t tick) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  const int step = ((int)tick != o->lastTick);
  if (step) o->lastTick = (int)tick;

  const uint8_t glow = v->rms01 > 0.55 ? DECK_HOT : (v->rms01 > 0.18 ? DECK_MAIN : DECK_DIM);
  const uint8_t dim = deck_thin_inten(g, DECK_DIM);
  const int sunX = W * 176 / 192;

  /* sun, top right */
  for (int dy = -2; dy <= 2; dy++)
    for (int dx = -3; dx <= 3; dx++)
      if (dx * dx + dy * dy * 1.8 <= 6.5) deck_set(fb, sunX + dx, 4 + dy, dim);
  deck_set(fb, sunX, 4, DECK_MAIN);
  deck_set(fb, sunX - 1, 4, DECK_MAIN);
  deck_set(fb, sunX, 3, DECK_MAIN);

  /* scrolling wave line, two alternating 8-cell shapes */
  static const uint8_t patA[8] = { 0, 0, 1, 1, 0, 0, 0, 1 };
  static const uint8_t patB[8] = { 1, 0, 0, 0, 1, 1, 0, 0 };
  const uint8_t *pat = (tick & 2) ? patA : patB;
  const uint8_t wave = deck_thin_inten(g, glow);
  for (int x = 0; x < W; x++) {
    deck_set(fb, x, WAVE_Y + pat[(x + (int)tick) % 8], wave);
    if (((x + (int)tick * 3) % 24) == 7) deck_set(fb, x, WAVE_Y + 2, dim);
  }

  /* underwater shimmer — deterministic twinkle, no randomness to diverge */
  for (int y = 20; y < H - 5; y += 4)
    for (int x = 0; x < W; x++)
      if ((x * 7 + y * 13 + ((int)tick >> 1) * 5) % 131 < 1) deck_set(fb, x, y, dim);

  /* seabed */
  for (int x = 0; x < W; x++) {
    deck_set(fb, x, H - 1, dim);
    if (x % 11 == 0 || x % 11 == 5) deck_set(fb, x, H - 2, dim);
    if (x % 23 == 9) deck_set(fb, x, H - 3, dim);
  }

  if (step) {
    if (o->nBubbles < DECK_BUBBLE_MAX && ((int)tick * 37) % 100 < v->hfAvg * 120) {
      o->bubbles[o->nBubbles].x = ((int)tick * 53) % W;
      o->bubbles[o->nBubbles].y = H - 5;
      o->nBubbles++;
    }
    for (int i = o->nBubbles - 1; i >= 0; i--) {
      o->bubbles[i].y -= 2;
      if (o->bubbles[i].y <= WAVE_Y + 2) {
        for (int j = i; j < o->nBubbles - 1; j++) o->bubbles[j] = o->bubbles[j + 1];
        o->nBubbles--;
      }
    }
  }
  for (int i = 0; i < o->nBubbles; i++)
    deck_set(fb, o->bubbles[i].x + (((int)tick + i) % 4 < 2 ? 0 : 1), o->bubbles[i].y, dim);

  if (step) {
    /* a bass hit sends the pod over the wave */
    if (v->bassAvg - o->lastBass > 0.3)
      for (int i = 0; i < 2; i++) if (o->pod[i].mode == 0) o->pod[i].wantBreach = 1;
    o->lastBass = o->lastBass * 0.9 + v->bassAvg * 0.1;

    for (int i = 0; i < 2; i++) step_dolphin(o, &o->pod[i], (int)tick);

    for (int i = o->nSpray - 1; i >= 0; i--) {
      deck_spray_t *p = &o->spray[i];
      p->x += p->vx; p->y += p->vy; p->vy += 0.32; p->life--;
      if (p->life <= 0 || p->y > WAVE_Y + 2) {
        for (int j = i; j < o->nSpray - 1; j++) o->spray[j] = o->spray[j + 1];
        o->nSpray--;
      }
    }
  }

  for (int i = 0; i < 2; i++) {
    const deck_dolphin_t *d = &o->pod[i];
    blit(fb, find_mask(d->len, d->rang, d->rflex),
         deck_round(d->x), deck_round(d->ry), d->rinten);
  }
  for (int i = 0; i < o->nSpray; i++)
    deck_set(fb, deck_round(o->spray[i].x), deck_round(o->spray[i].y),
             o->spray[i].life > 3 ? DECK_MAIN : DECK_DIM);
}
