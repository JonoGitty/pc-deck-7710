#include "art.h"

/* Same matrix as the output stage, so art and UI degrade together. */
static const uint8_t BAYER4[4][4] = {
  {  0,  8,  2, 10 },
  { 12,  4, 14,  6 },
  {  3, 11,  1,  9 },
  { 15,  7, 13,  5 },
};

void deck_art_dither(const uint8_t *lum, int s, uint8_t *out) {
  if (s <= 0) return;

  int lo = 255, hi = 0;
  for (int i = 0; i < s * s; i++) {
    int l = lum[i];
    if (l < lo) lo = l;
    if (l > hi) hi = l;
  }
  /* Floor the span so a flat sleeve doesn't get amplified into noise. */
  double span = (hi - lo) < 30 ? 30.0 : (double)(hi - lo);

  for (int y = 0; y < s; y++)
    for (int x = 0; x < s; x++) {
      const int i = y * s + x;
      double v = ((double)(lum[i] - lo) / span) * 3.999;
      double t = (BAYER4[y & 3][x & 3] + 0.5) / 16.0;
      double f = v + t - 0.5;
      int q = (int)f;                       /* f >= -0.5, so trunc == floor */
      if (f < 0) q = 0;
      if (q > 3) q = 3;
      out[i] = (uint8_t)q;
    }
}
