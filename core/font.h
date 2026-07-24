/* Dot-matrix text. Both ROMs come from the legacy JS via tools/gen_font_rom.js.
 *
 * Input is UTF-8. ASCII is folded to uppercase by the ROM table itself; the
 * five non-ASCII glyphs the deck uses (· ° ♪ ▶ ‖) are looked up by codepoint.
 * Anything else draws as '?' at 5x7 and blank at 3x5, matching the JS.
 */
#ifndef DECK_FONT_H
#define DECK_FONT_H

#include "deck.h"

/* Both return the pixel width advanced, as the JS does. `scale` 0 is treated
 * as 1 and `inten` 0 as DECK_MAIN, preserving the JS default-argument idiom. */
int deck_text5(deck_fb_t *fb, int x, int y, const char *s, uint8_t inten, int scale);
int deck_text3(deck_fb_t *fb, int x, int y, const char *s, uint8_t inten);

int deck_width5(const char *s, int scale);
int deck_width3(const char *s);

#endif /* DECK_FONT_H */
