#include "font.h"
#include "font_rom.h"

/* Minimal UTF-8 decode. Returns the codepoint and advances *p. Malformed
 * bytes are consumed one at a time and reported as U+FFFD, so a bad string
 * can't run off the end. */
static uint32_t utf8_next(const char **p) {
  const unsigned char *s = (const unsigned char *)*p;
  uint32_t c = s[0];
  int extra;
  if (c < 0x80)             { *p += 1; return c; }
  else if ((c & 0xe0) == 0xc0) { c &= 0x1f; extra = 1; }
  else if ((c & 0xf0) == 0xe0) { c &= 0x0f; extra = 2; }
  else if ((c & 0xf8) == 0xf0) { c &= 0x07; extra = 3; }
  else                      { *p += 1; return 0xfffd; }

  for (int i = 1; i <= extra; i++) {
    if ((s[i] & 0xc0) != 0x80) { *p += 1; return 0xfffd; }
    c = (c << 6) | (s[i] & 0x3f);
  }
  *p += extra + 1;
  return c;
}

static const uint8_t *glyph5(uint32_t cp) {
  if (cp >= FONT_ASCII_LO && cp <= FONT_ASCII_HI)
    return FONT5_ASCII[cp - FONT_ASCII_LO];
  for (int i = 0; i < FONT5_SPECIAL_N; i++)
    if (FONT5_SPECIAL[i].cp == cp) return FONT5_SPECIAL[i].rows;
  return FONT5_ASCII['?' - FONT_ASCII_LO];
}

static const uint8_t *glyph3(uint32_t cp) {
  if (cp >= FONT_ASCII_LO && cp <= FONT_ASCII_HI)
    return FONT3_ASCII[cp - FONT_ASCII_LO];
  for (int i = 0; i < FONT3_SPECIAL_N; i++)
    if (FONT3_SPECIAL[i].cp == cp) return FONT3_SPECIAL[i].rows;
  return FONT3_ASCII[' ' - FONT_ASCII_LO];
}

int deck_text5(deck_fb_t *fb, int x, int y, const char *s, uint8_t inten, int scale) {
  if (scale <= 0) scale = 1;
  if (inten == 0) inten = DECK_MAIN;
  int cx = x;
  while (*s) {
    const uint8_t *g = glyph5(utf8_next(&s));
    for (int row = 0; row < 7; row++) {
      uint8_t bits = g[row];
      for (int col = 0; col < 5; col++) {
        if (!(bits & (0x10 >> col))) continue;
        for (int sy = 0; sy < scale; sy++)
          for (int sx = 0; sx < scale; sx++)
            deck_set(fb, cx + col * scale + sx, y + row * scale + sy, inten);
      }
    }
    cx += (5 + 1) * scale;
  }
  return cx - x;
}

int deck_text3(deck_fb_t *fb, int x, int y, const char *s, uint8_t inten) {
  if (inten == 0) inten = DECK_MAIN;
  int cx = x;
  while (*s) {
    const uint8_t *g = glyph3(utf8_next(&s));
    for (int row = 0; row < 5; row++) {
      uint8_t bits = g[row];
      for (int col = 0; col < 3; col++)
        if (bits & (4 >> col)) deck_set(fb, cx + col, y + row, inten);
    }
    cx += 4;
  }
  return cx - x;
}

static int codepoints(const char *s) {
  int n = 0;
  while (*s) { utf8_next(&s); n++; }
  return n;
}

/* The JS measures with String.length (UTF-16 units) while it draws per
 * codepoint. Those agree for every glyph in the ROM, all of which are BMP. */
int deck_width5(const char *s, int scale) {
  return codepoints(s) * 6 * (scale <= 0 ? 1 : scale);
}

int deck_width3(const char *s) {
  return codepoints(s) * 4;
}
