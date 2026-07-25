/* The telephone screens: incoming, dialling, in a call, and just ended.
 *
 * These are the only screens on the deck that are not decoration. Everything
 * else is a nice way to look at music; this is the one you read while moving,
 * and the constraints are different in kind:
 *
 *   * IT MUST BE READABLE IN A GLANCE. A caller's name at the largest size the
 *     panel can draw, and nothing else competing with it. No analyser, no
 *     clock, no track. The screen has one job for as long as it is up.
 *
 *   * IT MUST NOT DEPEND ON BRIGHTNESS. On a 1-bit VFD the four levels
 *     collapse, and "the dim one is the number, the bright one is the name" is
 *     an instruction that stops being true on half the panels this runs on. So
 *     the hierarchy here is carried by SIZE and POSITION, which survive.
 *
 *   * IT MUST SAY WHAT THE BUTTONS DO. Nobody learns a control layout while a
 *     phone is ringing at them. The prompt is on screen, always, in the same
 *     place, in both of the states where a decision is needed.
 *
 * THE ONE PLACE LEVEL 4 IS USED ON PURPOSE
 *
 * DECK_CLIP is reserved: it is the audio clipping indicator, and on a colour
 * panel it renders red. It is used here, for the incoming-call pulse, and the
 * reasoning is that during a call there IS no audio path to clip — the
 * analyser is not running, the indicator has no other job for the duration,
 * and red is the correct colour for a telephone ringing. It is not used in any
 * other call state.
 *
 * Everything below draws from `deck_call_t`, which the firmware fills in from
 * HFP events. The screen has no idea Bluetooth exists, which is what lets the
 * PC deck and the simulator drive it from a script.
 */
#include "../screens.h"
#include "../font.h"
#include "../trig.h"

/* Fill a rectangle, overwriting rather than max-blending.
 *
 * deck_set() is a max-blend — a dot never dims what is already under it, which
 * is right for everything that draws a picture and wrong for a plate that has
 * to knock a hole in one. So this writes the buffer directly. Bounds are
 * clipped here rather than trusted, because unlike deck_set there is no
 * out-of-range drop underneath. */
static void fillrect(deck_fb_t *fb, int x, int y, int w, int h, uint8_t v) {
  const int W = (int)fb->geom->w, H = (int)fb->geom->h;
  for (int yy = y < 0 ? 0 : y; yy < y + h && yy < H; yy++)
    for (int xx = x < 0 ? 0 : x; xx < x + w && xx < W; xx++)
      fb->px[yy * W + xx] = v;
}

/* Text knocked out of a filled plate: draw the block, then punch the glyphs
 * back out to DECK_OFF. Legible on a 1-bit panel, which plain dim text is
 * not. */
static void plate3(deck_fb_t *fb, int x, int y, const char *s) {
  const int w = deck_width3(s) + 3;
  fillrect(fb, x - 1, y - 1, w, 7, DECK_MAIN);
  /* Draw into a scratch pass: deck_text3 max-blends, so it cannot write OFF.
   * Drawing at HOT and then inverting only the glyph dots is the trick that
   * keeps this to one framebuffer and no scratch buffer. */
  const int W = (int)fb->geom->w, H = (int)fb->geom->h;
  const int x0 = x - 1 < 0 ? 0 : x - 1, y0 = y - 1 < 0 ? 0 : y - 1;
  const int x1 = x - 1 + w > W ? W : x - 1 + w, y1 = y + 6 > H ? H : y + 6;
  deck_text3(fb, x + 1, y, s, DECK_HOT);
  for (int yy = y0; yy < y1; yy++)
    for (int xx = x0; xx < x1; xx++)
      if (fb->px[yy * W + xx] == DECK_HOT) fb->px[yy * W + xx] = DECK_OFF;
}


/* Who is calling, in the largest form that fits.
 *
 * A number is drawn at a smaller size than a name on purpose: a name is three
 * or four glyphs of information and a number is eleven, so the same box gives
 * one of them room and the other a scroll. Nobody wants to read a scrolling
 * phone number at a junction. */
static void who(deck_fb_t *fb, const deck_call_t *c, int y) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w;

  if (c->name[0]) {
    /* Widest scale that still fits, tried largest first. Computing the fit
     * rather than picking a size means a short name gets the big treatment
     * and a long one stays on one line instead of running off the glass. */
    for (int sc = 3; sc >= 1; sc--) {
      const int wpx = deck_width5(c->name, sc);
      if (wpx <= W - 8 || sc == 1) {
        deck_text5(fb, (W - wpx) / 2, y, c->name, DECK_HOT, sc);
        return;
      }
    }
  }
  if (c->number[0]) {
    const int sc = deck_width5(c->number, 2) <= W - 8 ? 2 : 1;
    const int wpx = deck_width5(c->number, sc);
    deck_text5(fb, (W - wpx) / 2, y, c->number, DECK_HOT, sc);
    return;
  }
  const int wpx = deck_width5("WITHHELD", 2);
  deck_text5(fb, (W - wpx) / 2, y, "WITHHELD", DECK_MAIN, 2);
}

/* The prompt strip along the bottom: what each control does, right now.
 *
 * Drawn as a knocked-out plate rather than as plain text because it has to
 * survive being read against whatever the rest of the screen is doing, on a
 * panel with no colour and possibly no greyscale. An inverted block is legible
 * on every target this compiles for. */
static void prompt(deck_fb_t *fb, const char *left, const char *right) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, y = (int)g->h - 7;

  if (left) plate3(fb, 2, y, left);
  if (right) plate3(fb, W - deck_width3(right) - 4, y, right);
}

/* The incoming-call pulse: a frame around the whole panel, breathing.
 *
 * The first version of this was a little handset glyph with concentric arcs
 * leaving it, tucked into the left margin. It was six lit dots and it read as
 * a smudge — which is the same lesson the dolphins taught: a small shape on a
 * dot-matrix panel is not a small version of a big shape, it is nothing.
 *
 * A phone ringing has to be caught in peripheral vision by somebody watching
 * a road, so the indicator is the largest thing available: the panel's own
 * border, pulsing. It costs no space that the name or the prompts wanted, it
 * cannot be confused with any other screen, and it works at any grid size.
 *
 * Driven off the caller's clock rather than a frame counter, so the pulse
 * rate is the same on a 10 fps movie loop and a 30 fps live panel. A ring
 * that speeds up with the frame rate reads as panic.
 */
static void ringing(deck_fb_t *fb, double now_ms) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  double p = now_ms / 900.0;
  p -= (double)(long)p;
  /* Two thick beats and a rest, which is a telephone's cadence rather than a
   * metronome's. */
  const int on = (p < 0.22) || (p >= 0.34 && p < 0.56);
  if (!on) return;
  const uint8_t v = deck_thin_inten(g, DECK_CLIP);
  for (int t = 0; t < 2; t++) {
    for (int x = t; x < W - t; x++) {
      deck_set(fb, x, t, v);
      deck_set(fb, x, H - 1 - t, v);
    }
    for (int y = t; y < H - t; y++) {
      deck_set(fb, t, y, v);
      deck_set(fb, W - 1 - t, y, v);
    }
  }
}

/* mm:ss, without divmod on a chip where it costs, and without snprintf. */
static void clockstr(char *out, int secs) {
  if (secs < 0) secs = 0;
  if (secs > 99 * 60 + 59) secs = 99 * 60 + 59;
  const int m = secs / 60, s = secs - m * 60;
  out[0] = (char)('0' + m / 10);
  out[1] = (char)('0' + m % 10);
  out[2] = ':';
  out[3] = (char)('0' + s / 10);
  out[4] = (char)('0' + s % 10);
  out[5] = 0;
}

/* Live microphone level, as a row of blocks.
 *
 * This is here because it answers the question the driver actually has, which
 * is "can they hear me?" — and because it is the only feedback in the whole
 * system that the microphone is wired up and working. A call screen without it
 * looks identical whether the mic is connected or in a box on the bench. */
static void miclevel(deck_fb_t *fb, int x0, int y, int w, int h, uint8_t level) {
  const deck_geom_t *g = fb->geom;
  const int n = w / 4;
  const int lit = (level * n + 127) / 255;
  for (int i = 0; i < n; i++) {
    /* Segments 3 wide and the full height of the strip. An earlier version
     * drew them 2x3 and the meter read as a dotted line rather than as a
     * level — same failure as every other thin feature on this panel. */
    const uint8_t v = i < lit ? (i > n * 3 / 4 ? DECK_HOT : DECK_MAIN)
                              : deck_thin_inten(g, DECK_DIM);
    fillrect(fb, x0 + i * 4, y, 3, h, v);
  }
}

void deck_screen_call(deck_fb_t *fb, const deck_call_t *c, double now_ms) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  char buf[8];

  switch (c->state) {
  case DECK_CALL_INCOMING: {
    const int wl = deck_width3("INCOMING CALL");
    deck_text3(fb, (W - wl) / 2, 3, "INCOMING CALL", DECK_MAIN);
    who(fb, c, 11);
    /* The number under the name, small, when both are known. It is the thing
     * you check when the name is a nickname you do not recognise, and it is
     * never the thing you read first — hence small and below. */
    if (c->name[0] && c->number[0]) {
      const int wn = deck_width3(c->number);
      deck_text3(fb, (W - wn) / 2, H - 16, c->number, DECK_DIM);
    }
    prompt(fb, "ANSWER", "REJECT");
    ringing(fb, now_ms);          /* last: the border sits over everything */
    break;
  }

  case DECK_CALL_OUTGOING:
    deck_text3(fb, 2, 1, "CALLING", DECK_MAIN);
    who(fb, c, 9);
    /* Three dots filling in turn. The only moving thing on the screen, which
     * is what distinguishes "still connecting" from "frozen". */
    for (int i = 0; i < 3; i++) {
      const int on = ((int)(now_ms / 400.0) % 3) >= i;
      fillrect(fb, W / 2 - 8 + i * 7, H - 12, 4, 3,
               on ? DECK_HOT : deck_thin_inten(g, DECK_DIM));
    }
    prompt(fb, 0, "END");
    break;

  case DECK_CALL_ACTIVE:
    who(fb, c, 1);
    clockstr(buf, c->secs);
    deck_text5(fb, 2, H / 2 + 1, buf, DECK_MAIN, 2);
    deck_text3(fb, W / 2 + 2, H / 2 + 1, "MIC", DECK_DIM);
    miclevel(fb, W / 2 + 2, H / 2 + 8, W / 2 - 6, H / 8 + 2, c->mic);
    prompt(fb, 0, "END");
    break;

  case DECK_CALL_ENDED: {
    const int w1 = deck_width5("CALL ENDED", 1);
    deck_text5(fb, (W - w1) / 2, H / 2 - 8, "CALL ENDED", DECK_MAIN, 1);
    clockstr(buf, c->secs);
    const int w2 = deck_width5(buf, 2);
    deck_text5(fb, (W - w2) / 2, H / 2, buf, DECK_HOT, 2);
    break;
  }

  case DECK_CALL_IDLE:
  default:
    break;
  }
}
