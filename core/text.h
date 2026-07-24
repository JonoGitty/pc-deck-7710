/* Text handling shared by the metadata screens.
 *
 * Everything here works on folded ASCII, so lengths are bytes and the scroller
 * and wrapper can index directly. Fold first, then wrap or scroll.
 */
#ifndef DECK_TEXT_H
#define DECK_TEXT_H

#include <stdint.h>
#include <stddef.h>

/* Decode one UTF-8 codepoint and advance *p. Malformed bytes are consumed
 * singly and reported as U+FFFD, so a bad string cannot run off the end. */
uint32_t deck_utf8_next(const char **p);

/* Fold to the character ROM: accents stripped, curly punctuation squared off,
 * anything undrawable turned to a space, whitespace runs collapsed, trimmed.
 * Writes at most cap-1 bytes plus a terminator. Returns the length written. */
size_t deck_fold(const char *src, char *dst, size_t cap);

/* Marquee, matching the legacy deck: hold 1.2 s, then run at 8 cells/s with a
 * five-space gap before the text comes round again. `dt` is milliseconds.
 * Writes exactly the visible window into out. */
typedef struct { int offset; int phase; double t; } deck_scroll_t;

void deck_scroll(deck_scroll_t *sc, double dt, const char *text, int cells,
                 char *out, size_t outcap);

/* Word-wrap into a flat array of maxrows fixed-width rows. Words longer than
 * `cells` are hard-split. Always writes at least one row, blank if need be.
 * Returns the number of rows used. */
int deck_wrap(const char *text, int cells, char *rows, int rowcap, int maxrows);

#endif /* DECK_TEXT_H */
