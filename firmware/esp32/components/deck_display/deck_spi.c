/* The one file that knows this is an ESP32.
 *
 * Panel drivers below this line speak five calls: command, data, one byte of
 * data, delay, reset. Everything ESP-IDF-shaped lives here, so a driver can be
 * read side by side with its datasheet without an SDK in the way, and so
 * porting to another MCU is this file and nothing else.
 */
#include "deck_display.h"

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "deck.spi";
static spi_device_handle_t s_dev;
static int s_dc = -1, s_rst = -1;

int deck_spi_begin(int mosi, int sclk, int cs, int dc, int rst, int mhz) {
  s_dc = dc;
  s_rst = rst;

  gpio_config_t io = {
      .pin_bit_mask = (1ULL << dc) | (rst >= 0 ? (1ULL << rst) : 0ULL),
      .mode = GPIO_MODE_OUTPUT,
  };
  esp_err_t err = gpio_config(&io);
  if (err != ESP_OK) return err;

  spi_bus_config_t bus = {
      .mosi_io_num = mosi,
      .miso_io_num = -1,          /* every panel here is write-only */
      .sclk_io_num = sclk,
      .quadwp_io_num = -1,
      .quadhd_io_num = -1,
      /* One row of the widest panel, plus slack. Bigger transfers would need
       * DMA descriptors we gain nothing from: a frame is pushed row by row so
       * the scratch buffer stays one row, not one screen. */
      .max_transfer_sz = 4096,
  };
  err = spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO);
  if (err != ESP_OK) return err;

  spi_device_interface_config_t cfg = {
      .clock_speed_hz = mhz * 1000 * 1000,
      .mode = 0,
      .spics_io_num = cs,
      .queue_size = 4,
      .flags = SPI_DEVICE_NO_DUMMY,
  };
  err = spi_bus_add_device(SPI2_HOST, &cfg, &s_dev);
  if (err != ESP_OK) return err;

  ESP_LOGI(TAG, "spi up: mosi=%d sclk=%d cs=%d dc=%d rst=%d %dMHz",
           mosi, sclk, cs, dc, rst, mhz);
  return 0;
}

static void tx(const uint8_t *d, size_t n, int is_data) {
  if (!n || !s_dev) return;
  gpio_set_level((gpio_num_t)s_dc, is_data);
  spi_transaction_t t = {.length = n * 8, .tx_buffer = d};
  /* Polling rather than queued: the caller is the render task and has nothing
   * else to do while a row goes out. Queued transfers would buy overlap we
   * cannot use and cost a completion callback that can outlive the buffer. */
  spi_device_polling_transmit(s_dev, &t);
}

void deck_spi_cmd(uint8_t c)                 { tx(&c, 1, 0); }
void deck_spi_data1(uint8_t d)               { tx(&d, 1, 1); }
void deck_spi_data(const uint8_t *d, size_t n) { tx(d, n, 1); }

void deck_delay_ms(uint32_t ms) { vTaskDelay(pdMS_TO_TICKS(ms ? ms : 1)); }

void deck_reset_pin(int level) {
  if (s_rst >= 0) gpio_set_level((gpio_num_t)s_rst, level);
}

/* --- which panel this image was built for ------------------------------- */
#if defined(DECK_DISPLAY_GP1294AI)
static const deck_panel_t PANEL = {
    .name = "gp1294ai", .w = 256, .h = 48, .levels = 2, .scratch = 256 * 48 / 8,
    .init = gp1294ai_init, .blit = gp1294ai_blit,
    .brightness = gp1294ai_brightness, .sleep = gp1294ai_sleep,
    .test_pattern = gp1294ai_test_pattern,
};
#else
static const deck_panel_t PANEL = {
    .name = "ssd1322", .w = 256, .h = 64, .levels = 16, .scratch = 256 / 2,
    .init = ssd1322_init, .blit = ssd1322_blit,
    .brightness = ssd1322_brightness, .sleep = ssd1322_sleep,
    .test_pattern = ssd1322_test_pattern,
};
#endif

const deck_panel_t *deck_panel(void) { return &PANEL; }
