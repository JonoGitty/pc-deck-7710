/* Futaba GP1294AI — 256x48 vacuum fluorescent, 1-bit.
 *
 * The authenticity tier. Real VFD glass, genuinely the technology the period
 * decks used, and unbeatable in daylight. What it costs is the greyscale: one
 * bit means the four intensity levels have to be dithered, which core/out.c
 * already does with the same ordered matrix the album art uses. Nothing in
 * this file knows about that — by the time bytes arrive they are 0 or not.
 *
 * Two things about this panel bite.
 *
 * FRAME MEMORY IS COLUMN-MAJOR. The controller addresses the glass in vertical
 * strips: one byte holds eight stacked pixels of a single x. The deck's
 * framebuffer is row-major like every other framebuffer, so the blit is a
 * transpose, and getting it wrong produces a display that looks like static
 * rather than like an offset — which at least fails obviously.
 *
 * BRIGHTNESS IS NOT A CONTRAST REGISTER. A VFD is dimmed by shortening the
 * grid/anode drive duty cycle. The GP1294AI exposes that as a "dimming" command
 * with a wide range, and unlike an OLED's contrast it interacts with the
 * refresh rate, so very low settings can flicker on camera even when they look
 * fine to an eye.
 *
 * SUPPLY: this module needs a filament AC drive and an anode boost, and it is
 * NOT clear from the datasheet whether a bare panel includes them. See
 * docs/HARDWARE.md — resolve that before buying, not after.
 *
 * NEVER RUN ON HARDWARE. Command values are from the datasheet and the
 * published community work referenced in docs/HARDWARE.md.
 */
#include "deck_display.h"

#define GP_W 256
#define GP_H 48
#define GP_STRIPS (GP_H / 8)              /* 6 vertical bytes per column */

/* Pin map. Shares the bus with the SSD1322 build deliberately — only one panel
 * is ever compiled in, and keeping one wiring diagram is worth more than
 * per-panel pin optimisation. */
#define PIN_MOSI 23
#define PIN_SCLK 18
#define PIN_CS    5
#define PIN_DC   17     /* unused by this panel; kept so the harness is common */
#define PIN_RST  16
#define SPI_MHZ   4     /* datasheet tops out well below the SSD1322 */

/* --- commands ----------------------------------------------------------- */
#define GP_CMD_WRITE_GRAM 0x08
#define GP_CMD_DISPLAY_ON 0x20
#define GP_CMD_STANDBY    0x61
#define GP_CMD_DIMMING    0xa0
#define GP_CMD_OSC        0x78
#define GP_CMD_DUTY       0xa1
#define GP_CMD_MODE       0xcc
#define GP_CMD_VFD_ON     0x6d

/* This panel takes command and parameters as one continuous stream on the data
 * line with no D/C distinction, so everything goes out as "data" after the
 * command byte. Wrapping it keeps the intent readable. */
static void send(const uint8_t *b, size_t n) { deck_spi_data(b, n); }

int gp1294ai_init(void) {
  int err = deck_spi_begin(PIN_MOSI, PIN_SCLK, PIN_CS, PIN_DC, PIN_RST, SPI_MHZ);
  if (err) return err;

  deck_reset_pin(0);
  deck_delay_ms(2);
  deck_reset_pin(1);
  /* The filament needs time before the controller will answer. This is the
   * step people skip, and skipping it looks exactly like a dead panel. */
  deck_delay_ms(100);

  { const uint8_t c[] = {GP_CMD_VFD_ON, 0x01}; send(c, sizeof c); }
  deck_delay_ms(10);
  { const uint8_t c[] = {GP_CMD_OSC, 0x08, 0x00}; send(c, sizeof c); }
  { const uint8_t c[] = {GP_CMD_DUTY, 0x00, 0x00}; send(c, sizeof c); }
  { const uint8_t c[] = {GP_CMD_MODE, 0x00}; send(c, sizeof c); }
  gp1294ai_brightness(70);
  { const uint8_t c[] = {GP_CMD_DISPLAY_ON, 0x00}; send(c, sizeof c); }
  deck_delay_ms(10);
  return 0;
}

void gp1294ai_brightness(uint8_t pct) {
  if (pct > 100) pct = 100;
  /* Below roughly a fifth the duty cycle gets short enough to strobe, so the
   * usable range is compressed into the top four fifths rather than letting
   * the knob turn the panel into a flicker source. */
  const uint16_t d = (uint16_t)(0x0100 + (uint32_t)pct * (0x0700 - 0x0100) / 100);
  const uint8_t c[] = {GP_CMD_DIMMING, (uint8_t)(d & 0xff), (uint8_t)(d >> 8)};
  send(c, sizeof c);
}

void gp1294ai_sleep(int on) {
  const uint8_t c[] = {GP_CMD_STANDBY, (uint8_t)(on ? 0x01 : 0x00)};
  send(c, sizeof c);
}

/* Row-major 0..255 in, column-major bits out.
 *
 * `dev` is one byte per dot from deck_out_frame(), already reduced to this
 * panel's two levels — so the only question left is whether a dot is lit, and
 * the threshold is the midpoint. Doing anything more here would be second
 * guessing the output stage the preview also runs.
 */
void gp1294ai_blit(const uint8_t *dev, uint8_t *scratch) {
  for (int x = 0; x < GP_W; x++) {
    for (int s = 0; s < GP_STRIPS; s++) {
      uint8_t byte = 0;
      for (int bit = 0; bit < 8; bit++) {
        const int y = s * 8 + bit;
        if (dev[y * GP_W + x] >= 128) byte |= (uint8_t)(1u << bit);
      }
      scratch[x * GP_STRIPS + s] = byte;
    }
  }
  const uint8_t hdr[] = {GP_CMD_WRITE_GRAM, 0x00, 0x00,
                         (uint8_t)(GP_W - 1), (uint8_t)(GP_STRIPS - 1)};
  send(hdr, sizeof hdr);
  send(scratch, (size_t)GP_W * GP_STRIPS);
}

void gp1294ai_test_pattern(uint8_t *dev, int phase) {
  for (int y = 0; y < GP_H; y++) {
    for (int x = 0; x < GP_W; x++) {
      uint8_t v;
      /* No ramp: there is nothing to ramp. Instead the top band is a run of
       * vertical bars at increasing pitch, which is the fastest way to see
       * that the column-major transpose is right — a wrong transpose turns
       * clean bars into noise rather than into a shifted picture. */
      if (y < 12)                   v = ((x / (1 + y / 3)) & 1) ? 255 : 0;
      else if (y < 24)              v = ((x + phase) % 8 < 4) ? 255 : 0;
      else if (x == 0 || y == 0 ||
               x == GP_W - 1 || y == GP_H - 1) v = 255;
      else                          v = 0;
      dev[y * GP_W + x] = v;
    }
  }
}
