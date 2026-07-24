/* Panel drivers, behind one interface.
 *
 * Every driver takes the device bytes `deck_out_frame()` produced and does
 * nothing but pack them for the wire. All the decisions about what a dot
 * should look like — how five intensity levels collapse onto sixteen greys or
 * onto one bit, and where the ordered dither falls — happen in core/out.c,
 * which is shared with the browser preview. That is the entire reason the
 * preview can be trusted about the panel, and it is why nothing below is
 * allowed to be clever.
 *
 * The active panel is fixed at build time by -DDECK_DISPLAY_SSD1322 or
 * -DDECK_DISPLAY_GP1294AI. It decides the grid the whole UI is laid out on,
 * so it is not a runtime setting; see docs/VERSIONING.md.
 *
 * STATUS: never run on hardware. The command sequences come from datasheets.
 * Treat them as a first draft to be corrected on the bench.
 */
#ifndef DECK_DISPLAY_H
#define DECK_DISPLAY_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
  const char *name;
  int      w, h;
  uint8_t  levels;        /* what the glass can actually show */
  size_t   scratch;       /* bytes of scratch the blit needs, caller-owned */
  int    (*init)(void);
  void   (*blit)(const uint8_t *dev, uint8_t *scratch);
  void   (*brightness)(uint8_t pct);        /* 0..100 */
  void   (*sleep)(int on);
  /* Fills a device-format test pattern. The boot self-test has to be able to
   * prove the panel works before core/ is involved at all, or a blank screen
   * has two possible causes and no way to tell them apart. */
  void   (*test_pattern)(uint8_t *dev, int phase);
} deck_panel_t;

/* The panel this image was built for. Never NULL. */
const deck_panel_t *deck_panel(void);

/* --- the platform hooks the drivers call ------------------------------- */
/* Implemented once in deck_spi.c. Keeping the drivers on this tiny surface is
 * what lets them be read against a datasheet without ESP-IDF in the way. */
int  deck_spi_begin(int mosi, int sclk, int cs, int dc, int rst, int mhz);
void deck_spi_cmd(uint8_t c);
void deck_spi_data(const uint8_t *d, size_t n);
void deck_spi_data1(uint8_t d);
void deck_delay_ms(uint32_t ms);
void deck_reset_pin(int level);

int  ssd1322_init(void);
void ssd1322_blit(const uint8_t *dev, uint8_t *scratch);
void ssd1322_brightness(uint8_t pct);
void ssd1322_sleep(int on);
void ssd1322_test_pattern(uint8_t *dev, int phase);

int  gp1294ai_init(void);
void gp1294ai_blit(const uint8_t *dev, uint8_t *scratch);
void gp1294ai_brightness(uint8_t pct);
void gp1294ai_sleep(int on);
void gp1294ai_test_pattern(uint8_t *dev, int phase);

#endif /* DECK_DISPLAY_H */
