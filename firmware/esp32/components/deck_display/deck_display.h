/* Panel drivers. One per display target; the deck picks at build time.
 *
 * Every driver takes the device bytes deck_out_frame() produced and does
 * nothing but pack them for the wire. All the decisions about what a dot should
 * look like happen in core/out.c, which is why the browser preview and the
 * panel agree.
 */
#ifndef DECK_DISPLAY_H
#define DECK_DISPLAY_H

#include <stdint.h>
#include <stddef.h>

void ssd1322_init(void);
void ssd1322_set_brightness(uint8_t level0_15);
void ssd1322_sleep(int on);
/* scratch must hold at least width/2 bytes. */
void ssd1322_blit(const uint8_t *dev, int w, int h, uint8_t *scratch);

#endif /* DECK_DISPLAY_H */
