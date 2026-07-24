/* Smoothed analysis state the screens read — the C counterpart of `V` in
 * legacy/web/app.js. Doubles throughout, matching JS number semantics exactly,
 * so a ported screen produces bit-identical output to its original.
 */
#ifndef DECK_STATE_H
#define DECK_STATE_H

#include <stdint.h>

#define DECK_BANDS 13
#define DECK_WAVE  96

typedef struct {
  double bands[DECK_BANDS];
  double peaks[DECK_BANDS];
  double bandsL[DECK_BANDS];
  double bandsR[DECK_BANDS];
  double vuL, vuR;
  double wave[DECK_WAVE];
  double bassAvg, hfAvg, rms01, scopeGain;
  int    clip;
  uint32_t oceanTick;
} deck_state_t;

/* JS Math.round is floor(x + 0.5) — not C's round(), which breaks ties away
 * from zero. Screens must use this to stay faithful. */
static inline int deck_round(double x) {
  double f = x + 0.5;
  int i = (int)f;
  return (f < 0 && (double)i != f) ? i - 1 : i;
}

#endif /* DECK_STATE_H */
