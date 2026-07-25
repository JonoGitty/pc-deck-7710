#include "out.h"

/* Same 4x4 Bayer matrix the album-art dither uses, so art and UI degrade
 * consistently on a 1-bit panel. */
static const uint8_t BAYER4[4][4] = {
  {  0,  8,  2, 10 },
  { 12,  4, 14,  6 },
  {  3, 11,  1,  9 },
  { 15,  7, 13,  5 },
};

uint8_t deck_out_pixel(uint8_t inten, int x, int y, uint8_t levels) {
  if (inten == 0) return 0;
  if (inten > DECK_CLIP) inten = DECK_CLIP;
  if (levels < 2) levels = 2;

  /* Panel resolves the full scale: straight quantise, no dither needed. */
  if (levels >= DECK_LEVELS)
    return (uint8_t)((inten * 255) / (DECK_LEVELS - 1));

  /* Fewer steps than we draw with. Scale into the device range and use the
   * fractional part as a dither probability, so intensity 1 and 2 stay
   * distinguishable on 1-bit glass as sparse and dense patterns. */
  int span = (levels - 1) * 255;
  int scaled = (inten * span) / (DECK_LEVELS - 1);   /* 0 .. (levels-1)*255 */
  int step = scaled / 255;
  int frac = scaled - step * 255;                    /* 0..254 */

  int thresh = (BAYER4[y & 3][x & 3] * 255) / 16;
  if (frac > thresh) step++;
  if (step > levels - 1) step = levels - 1;

  return (uint8_t)((step * 255) / (levels - 1));
}

void deck_out_frame(const deck_fb_t *fb, uint8_t *dst, uint8_t levels) {
  const deck_geom_t *g = fb->geom;
  for (int y = 0; y < (int)g->h; y++)
    for (int x = 0; x < (int)g->w; x++) {
      size_t i = (size_t)y * g->w + (size_t)x;
      dst[i] = deck_out_pixel(fb->px[i], x, y, levels);
    }
}
