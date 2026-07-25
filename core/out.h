/* Output stage: map the canonical 0..4 intensity scale onto what a panel can
 * actually show. This is the ONLY place that knows a device has fewer levels
 * than the renderer, and it is shared by the firmware and the browser preview
 * — which is what makes the preview truthful rather than approximate.
 */
#ifndef DECK_OUT_H
#define DECK_OUT_H

#include "deck.h"

/* One dot, mapped to `levels` device steps and returned as 0..255 so callers
 * can drive greyscale, 1-bit, or a palette index from the same number.
 *
 * levels >= 5 quantises cleanly. levels < 5 cannot represent the scale, so the
 * shortfall is made up with an ordered dither keyed on (x, y) — which is why
 * the position is a parameter. Deterministic: same frame in, same pixels out.
 */
uint8_t deck_out_pixel(uint8_t inten, int x, int y, uint8_t levels);

/* Whole framebuffer into `dst`, one byte per dot, 0..255. */
void deck_out_frame(const deck_fb_t *fb, uint8_t *dst, uint8_t levels);

#endif /* DECK_OUT_H */
