/* PC-DECK — portable core.
 *
 * The renderer never knows what it is drawing on. It writes intensity values
 * 0..4 into a framebuffer described by deck_geom_t; a per-target output stage
 * maps those onto the device (1-bit dither, 16-level grey, RGB palette).
 *
 * C99, freestanding-friendly: no allocation, no libc beyond <string.h>.
 */
#ifndef DECK_H
#define DECK_H

/* stdint.h and stddef.h are freestanding headers — available with -nostdlib,
 * unlike string.h. The core pulls in nothing else. */
#include <stdint.h>
#include <stddef.h>

/* Canonical intensity scale. Every screen speaks these five values and nothing
 * else, so a target with fewer levels degrades in one place instead of ten. */
enum {
  DECK_OFF  = 0,
  DECK_DIM  = 1,
  DECK_MAIN = 2,
  DECK_HOT  = 3,
  DECK_CLIP = 4
};
#define DECK_LEVELS 5

/* Device capabilities. `levels` is what the panel can actually show: 2 for
 * 1-bit VFD/OLED, 5 for the deck's native scale, 16 for SSD1322 greyscale. */
#define DECK_FLAG_COLOR 0x01u   /* palette/colour schemes are meaningful */
#define DECK_FLAG_ROUND 0x02u   /* round bulb pixels rather than square */

typedef struct {
  uint16_t w, h;
  uint8_t  levels;
  uint8_t  flags;
} deck_geom_t;

typedef struct {
  const deck_geom_t *geom;
  uint8_t           *px;      /* geom->w * geom->h, each 0..4 */
} deck_fb_t;

/* Layout tier, chosen from grid height. See docs/UI-SPEC.md. */
typedef enum {
  DECK_TIER_STRIP = 0,        /* h < 40  */
  DECK_TIER_CLASSIC,          /* 40..79  */
  DECK_TIER_LARGE             /* h >= 80 */
} deck_tier_t;

deck_tier_t deck_tier(const deck_geom_t *g);

void    deck_clear(deck_fb_t *fb);

/* Max-blend, matching the JS setDot: a dot never dims what is already there.
 * Out-of-bounds writes are dropped, which several screens rely on. */
void    deck_set(deck_fb_t *fb, int x, int y, uint8_t inten);
uint8_t deck_get(const deck_fb_t *fb, int x, int y);

/* Hard horizontal wipe: blank every column at or right of `edge`. */
void    deck_wipe_from(deck_fb_t *fb, int edge);

#endif /* DECK_H */
