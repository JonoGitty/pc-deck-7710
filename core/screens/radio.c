/* The radio screen.
 *
 * A head unit is a radio. Everything else this deck does is something people
 * added to radios later, and it would be strange for the one screen that is
 * actually a radio to be the weakest.
 *
 * WHAT A DRIVER READS, IN ORDER
 *
 * The design follows what a person actually needs off a tuner, ranked, and
 * gives space in that order rather than in the order the data arrives:
 *
 *   1. The station.        RDS gives a name — CAPITAL FM, RADIO 4 — and a name
 *                          is what you tuned for. It goes first and biggest.
 *   2. The frequency.      What you fall back on when there is no RDS, and
 *                          what you say out loud. Big, but under the name.
 *   3. Where you are.      A band scale with a marker, so seek and manual
 *                          tuning have somewhere to move. Without it, tuning
 *                          is a number changing with no sense of travel.
 *   4. Preset, band, signal, stereo. Small, in the margins, glanced at.
 *   5. RDS radio text.     The scrolling "NOW PLAYING" line. Last, because it
 *                          is the only part that is never urgent.
 *
 * WHY THE SCALE IS DRAWN AND NOT JUST THE NUMBER
 *
 * A tuner without a scale feels broken when you seek: the number jumps, and
 * nothing tells you whether you moved a little or crossed the band. The scale
 * costs six rows and turns seeking from an event into a movement, which is the
 * entire feel of a radio.
 *
 * SIGNAL AND STEREO ARE NOT DRAWN IN BRIGHTNESS
 *
 * The obvious way to show a weak signal is to dim something. That works on the
 * OLED and vanishes on a 1-bit VFD, where every level collapses to lit. So
 * signal is a *count* of segments and stereo is a *glyph that is there or is
 * not*, both of which survive. See docs/UI-SPEC.md.
 */
#include "../screens.h"
#include "../font.h"

/* Fill, overwriting rather than max-blending — see call.c for why deck_set
 * cannot do this. */
static void fillrect(deck_fb_t *fb, int x, int y, int w, int h, uint8_t v) {
  const int W = (int)fb->geom->w, H = (int)fb->geom->h;
  for (int yy = y < 0 ? 0 : y; yy < y + h && yy < H; yy++)
    for (int xx = x < 0 ? 0 : x; xx < x + w && xx < W; xx++)
      fb->px[yy * W + xx] = v;
}

/* "98.50" or "1053" — no snprintf, and no float formatting on a chip where
 * that pulls in a printf the rest of the firmware does not need. */
static void freqstr(char *out, const deck_radio_t *r) {
  if (r->band == DECK_BAND_FM) {
    /* kHz to one decimal of MHz: 98500 -> "98.5" */
    const int t = (r->freq_khz + 50) / 100;      /* tenths of a MHz */
    const int whole = t / 10, frac = t - whole * 10;
    int i = 0;
    if (whole >= 100) out[i++] = (char)('0' + whole / 100);
    out[i++] = (char)('0' + (whole / 10) % 10);
    out[i++] = (char)('0' + whole % 10);
    out[i++] = '.';
    out[i++] = (char)('0' + frac);
    out[i] = 0;
  } else {
    int v = r->freq_khz, i = 0;
    char tmp[8];
    if (v <= 0) { out[0] = '0'; out[1] = 0; return; }
    while (v > 0 && i < 7) { tmp[i++] = (char)('0' + v % 10); v /= 10; }
    for (int k = 0; k < i; k++) out[k] = tmp[i - 1 - k];
    out[i] = 0;
  }
}

/* The band scale: a ruler with ticks, the presets marked, and the current
 * frequency as a full-height cursor. */
static void scale(deck_fb_t *fb, const deck_radio_t *r, int y) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w;
  const int x0 = 2, x1 = W - 3;
  const int span = r->band_hi_khz - r->band_lo_khz;
  if (span <= 0) return;

  /* baseline */
  for (int x = x0; x <= x1; x++)
    deck_set(fb, x, y + 4, deck_thin_inten(g, DECK_DIM));

  /* Ten major ticks. Not labelled: at this width the labels collide, and the
   * numbers are already on screen twice the size directly above. */
  for (int i = 0; i <= 10; i++) {
    const int x = x0 + (x1 - x0) * i / 10;
    for (int k = 0; k < ((i % 5) ? 2 : 4); k++)
      deck_set(fb, x, y + 4 - k, deck_thin_inten(g, DECK_DIM));
  }

  /* Presets, as stubs below the line, so a glance shows where your stations
   * are relative to where you have tuned. */
  for (int i = 0; i < r->n_presets && i < DECK_PRESETS; i++) {
    const int f = r->preset_khz[i];
    if (f < r->band_lo_khz || f > r->band_hi_khz) continue;
    const int x = x0 + (int)((long)(x1 - x0) * (f - r->band_lo_khz) / span);
    deck_set(fb, x, y + 5, deck_thin_inten(g, DECK_MAIN));
    deck_set(fb, x, y + 6, deck_thin_inten(g, DECK_MAIN));
  }

  /* The cursor. Solid and full height — this is the thing that moves, so it
   * has to win against every tick and stub behind it. */
  int f = r->freq_khz;
  if (f < r->band_lo_khz) f = r->band_lo_khz;
  if (f > r->band_hi_khz) f = r->band_hi_khz;
  const int cx = x0 + (int)((long)(x1 - x0) * (f - r->band_lo_khz) / span);
  fillrect(fb, cx - 1, y, 3, 7, DECK_HOT);
  deck_set(fb, cx, y - 1, DECK_HOT);
}

/* Signal strength: a count of segments, never a brightness. */
static void signal_bars(deck_fb_t *fb, int x, int y, uint8_t rssi) {
  const deck_geom_t *g = fb->geom;
  const int n = 5;
  const int lit = (rssi * n + 127) / 255;
  for (int i = 0; i < n; i++) {
    const int h = 2 + i;
    fillrect(fb, x + i * 3, y + (6 - h), 2, h,
             i < lit ? DECK_MAIN : deck_thin_inten(g, DECK_DIM));
  }
}

void deck_screen_radio(deck_fb_t *fb, const deck_radio_t *r,
                       deck_scroll_t *sc, double dt) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  char buf[12];

  /* --- top line: band, preset, signal, stereo ------------------------- */
  const char *bn = r->band == DECK_BAND_FM ? "FM" : "AM";
  deck_text3(fb, 2, 1, bn, DECK_MAIN);
  if (r->preset > 0) {
    char p[4] = {'P', (char)('0' + (r->preset % 10)), 0, 0};
    deck_text3(fb, 2 + deck_width3(bn) + 4, 1, p, DECK_HOT);
  }
  signal_bars(fb, W - 18, 1, r->rssi);
  /* Stereo is present or absent, not bright or dim — the one that survives a
   * 1-bit panel. */
  if (r->stereo) deck_text3(fb, W - 34, 1, "ST", DECK_HOT);

  /* --- the station, then the frequency -------------------------------- */
  int y = 9;
  if (r->name[0]) {
    /* RDS station names are eight characters by specification, so they always
     * fit at scale 2 on any panel this project targets. */
    const int wn = deck_width5(r->name, 2);
    deck_text5(fb, (W - wn) / 2, y, r->name, DECK_HOT, 2);
    y += 16;
  }

  freqstr(buf, r);
  {
    /* Largest scale that fits, so a station with no RDS still gets a big
     * readout rather than a small one in a mostly empty panel. */
    const int sc2 = r->name[0] ? 1 : 3;
    const int wf = deck_width5(buf, sc2);
    deck_text5(fb, (W - wf) / 2, y, buf, DECK_MAIN, sc2);
    const int unit_x = (W + wf) / 2 + 3;
    deck_text3(fb, unit_x, y + (sc2 > 1 ? 10 : 0),
               r->band == DECK_BAND_FM ? "MHZ" : "KHZ", DECK_DIM);
  }

  /* --- the band scale -------------------------------------------------- */
  scale(fb, r, H - 20);

  /* --- RDS radio text, scrolling --------------------------------------- */
  /* RDS radio text is 64 characters and it does not fit, ever. The marquee is
   * the same one the album-art screen uses — same hold, same speed — so the
   * two scrolling things on the deck move identically instead of at two
   * subtly different rates, which is the sort of detail nobody names and
   * everybody notices. */
  if (r->text[0]) {
    char win[48];
    const int cells = (W - 4) / 4;              /* 3x5 glyph plus one space */
    deck_scroll(sc, dt, r->text, cells > 47 ? 47 : cells, win, sizeof win);
    deck_text3(fb, 2, H - 6, win, DECK_DIM);
  }
}
