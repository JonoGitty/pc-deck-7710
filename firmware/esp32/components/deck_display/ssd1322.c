/* SSD1322 256x64 driver.
 *
 * The panel is 4-bit greyscale, and the controller packs TWO horizontal pixels
 * per byte — high nibble left, low nibble right. Its column addressing is in
 * those byte pairs, not pixels, which is the classic first-day mistake: writing
 * a 256-wide window and getting a display half filled and doubled.
 *
 * NOT YET RUN ON HARDWARE. Command values are from the datasheet; the init
 * sequence follows the common reference for the 256x64 module and will want
 * checking against whichever board turns up.
 */
#include "deck_display.h"

#define SSD1322_W 256
#define SSD1322_H 64
#define COL_START 0x1c            /* the 256-wide glass sits offset in GDDRAM */

/* --- commands ---------------------------------------------------------- */
#define CMD_ENABLE_GRAY_TABLE 0x00
#define CMD_SET_COLUMN        0x15
#define CMD_WRITE_RAM         0x5c
#define CMD_SET_ROW           0x75
#define CMD_SET_REMAP         0xa0
#define CMD_SET_START_LINE    0xa1
#define CMD_SET_OFFSET        0xa2
#define CMD_MODE_OFF          0xa4
#define CMD_MODE_NORMAL       0xa6
#define CMD_EXIT_PARTIAL      0xa9
#define CMD_FN_SELECT         0xab
#define CMD_SLEEP_ON          0xae
#define CMD_SLEEP_OFF         0xaf
#define CMD_PHASE_LENGTH      0xb1
#define CMD_CLOCK_DIVIDER     0xb3
#define CMD_DISPLAY_ENHANCE   0xb4
#define CMD_GPIO              0xb5
#define CMD_SECOND_PRECHARGE  0xb6
#define CMD_GRAY_TABLE        0xb8
#define CMD_DEFAULT_GRAY      0xb9
#define CMD_PRECHARGE_VOLTAGE 0xbb
#define CMD_VCOMH             0xbe
#define CMD_CONTRAST          0xc1
#define CMD_MASTER_CONTRAST   0xc7
#define CMD_MUX_RATIO         0xca
#define CMD_COMMAND_LOCK      0xfd

/* Pin map. These are the defaults deckctl and the wiring guide assume; change
 * them here and in docs/BUILD.md together or the two will disagree and the
 * disagreement will be discovered with a soldering iron in hand. */
#define PIN_MOSI 23
#define PIN_SCLK 18
#define PIN_CS    5
#define PIN_DC   19
#define PIN_RST   4
#define SPI_MHZ  20      /* datasheet allows more; 20 is a frame in ~1.6 ms */

static void cmd1(uint8_t c, uint8_t a) { deck_spi_cmd(c); deck_spi_data1(a); }

int ssd1322_init(void) {
  int err = deck_spi_begin(PIN_MOSI, PIN_SCLK, PIN_CS, PIN_DC, PIN_RST, SPI_MHZ);
  if (err) return err;

  deck_reset_pin(0);
  deck_delay_ms(10);
  deck_reset_pin(1);
  deck_delay_ms(10);

  cmd1(CMD_COMMAND_LOCK, 0x12);          /* unlock */
  deck_spi_cmd(CMD_SLEEP_ON);
  cmd1(CMD_CLOCK_DIVIDER, 0x91);
  cmd1(CMD_MUX_RATIO, 0x3f);             /* 64 rows */
  cmd1(CMD_SET_OFFSET, 0x00);
  cmd1(CMD_SET_START_LINE, 0x00);

  deck_spi_cmd(CMD_SET_REMAP);           /* horizontal increment, nibble order */
  deck_spi_data1(0x14);
  deck_spi_data1(0x11);

  cmd1(CMD_GPIO, 0x00);
  cmd1(CMD_FN_SELECT, 0x01);             /* internal VDD regulator */
  deck_spi_cmd(CMD_DISPLAY_ENHANCE);
  deck_spi_data1(0xa0);
  deck_spi_data1(0xfd);
  cmd1(CMD_CONTRAST, 0x9f);
  cmd1(CMD_MASTER_CONTRAST, 0x0f);
  deck_spi_cmd(CMD_DEFAULT_GRAY);        /* linear grey ramp */
  cmd1(CMD_PHASE_LENGTH, 0xe2);
  deck_spi_cmd(CMD_DISPLAY_ENHANCE);
  cmd1(CMD_PRECHARGE_VOLTAGE, 0x1f);
  cmd1(CMD_SECOND_PRECHARGE, 0x08);
  cmd1(CMD_VCOMH, 0x07);
  deck_spi_cmd(CMD_MODE_NORMAL);
  deck_spi_cmd(CMD_EXIT_PARTIAL);
  deck_spi_cmd(CMD_SLEEP_OFF);
  deck_delay_ms(10);
  return 0;
}

/* Master contrast is the deck's brightness knob, and it is the right one:
 * dimming in software would spend intensity levels on brightness, which on a
 * panel that only has sixteen of them is the difference between a readable
 * peak-hold dot and no peak-hold dot. The controller dims the whole ramp
 * instead and the levels survive intact. */
void ssd1322_brightness(uint8_t pct) {
  if (pct > 100) pct = 100;
  cmd1(CMD_MASTER_CONTRAST, (uint8_t)((pct * 15 + 50) / 100));
}

void ssd1322_sleep(int on) {
  deck_spi_cmd(on ? CMD_SLEEP_ON : CMD_SLEEP_OFF);
}

/* Pack the device bytes the output stage produced into the panel's two-pixels
 * -per-byte layout and push one full frame.
 *
 * `dev` is 0..255 per dot from deck_out_frame(); the panel wants 4 bits, so the
 * top nibble is taken. That is the whole of the conversion — every decision
 * about what a dot should look like was already made in core/out.c, which is
 * why the preview and the panel agree. */
void ssd1322_blit(const uint8_t *dev, uint8_t *scratch) {
  const int w = SSD1322_W, h = SSD1322_H;
  const int cols = SSD1322_W / 2;

  deck_spi_cmd(CMD_SET_COLUMN);
  deck_spi_data1(COL_START);
  deck_spi_data1(COL_START + cols - 1);
  deck_spi_cmd(CMD_SET_ROW);
  deck_spi_data1(0);
  deck_spi_data1(SSD1322_H - 1);
  deck_spi_cmd(CMD_WRITE_RAM);

  for (int y = 0; y < SSD1322_H; y++) {
    for (int c = 0; c < cols; c++) {
      const int xl = c * 2, xr = xl + 1;
      uint8_t l = 0, r = 0;
      if (y < h) {
        if (xl < w) l = dev[y * w + xl] >> 4;
        if (xr < w) r = dev[y * w + xr] >> 4;
      }
      scratch[c] = (uint8_t)((l << 4) | r);
    }
    deck_spi_data(scratch, (size_t)cols);
  }
}

/* Device-format test pattern for the boot self-test.
 *
 * Deliberately not a picture: it is a grey ramp, a one-dot grid and a border.
 * The ramp proves all sixteen levels reach the glass, the grid proves the
 * nibble packing is not doubling or halving the width — the classic SSD1322
 * first-day fault — and the border proves the addressing window covers the
 * whole panel rather than a plausible-looking subset of it.
 */
void ssd1322_test_pattern(uint8_t *dev, int phase) {
  for (int y = 0; y < SSD1322_H; y++) {
    for (int x = 0; x < SSD1322_W; x++) {
      uint8_t v;
      if (y < 16)                       v = (uint8_t)((x * 16 / SSD1322_W) * 17);
      else if (y < 32)                  v = ((x + y + phase) & 1) ? 255 : 0;
      else if (x == 0 || y == 0 ||
               x == SSD1322_W - 1 || y == SSD1322_H - 1) v = 255;
      else                              v = 0;
      dev[y * SSD1322_W + x] = v;
    }
  }
}
