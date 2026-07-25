/* See deck_i2c.h. NEVER RUN ON HARDWARE. */
#include "deck_i2c.h"

#include "deck_diag.h"

/* The tuner's pins, which are the bus's pins — they were only ever in
 * deck_tuner.c because it was the first device on it. Documented in
 * docs/BUILD.md §3 and drawn in docs/media/pinmap.svg, both of which are
 * generated from or checked against these numbers. */
#define PIN_SDA 32
#define PIN_SCL 33
#define I2C_HZ  100000

static i2c_master_bus_handle_t s_bus;
static int s_tried;

i2c_master_bus_handle_t deck_i2c_bus(void) {
  if (s_bus || s_tried) return s_bus;
  s_tried = 1;

  const i2c_master_bus_config_t bc = {
      .i2c_port = I2C_NUM_0,
      .sda_io_num = PIN_SDA,
      .scl_io_num = PIN_SCL,
      .clk_source = I2C_CLK_SRC_DEFAULT,
      .glitch_ignore_cnt = 7,
      .flags = {.enable_internal_pullup = true},
  };
  if (i2c_new_master_bus(&bc, &s_bus) != ESP_OK) {
    s_bus = NULL;
    deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_DEGRADED,
                  "no I2C bus — no tuner and no volume");
    return NULL;
  }
  deck_diag_event(DECK_SUB_AUDIO, "i2c", "up sda=%d scl=%d hz=%d",
                  PIN_SDA, PIN_SCL, I2C_HZ);
  return s_bus;
}

i2c_master_dev_handle_t deck_i2c_device(uint8_t addr, uint32_t hz) {
  i2c_master_bus_handle_t bus = deck_i2c_bus();
  if (!bus) return NULL;
  i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7,
                            .device_address = addr,
                            .scl_speed_hz = hz ? hz : I2C_HZ};
  i2c_master_dev_handle_t dev = NULL;
  if (i2c_master_bus_add_device(bus, &dc, &dev) != ESP_OK) return NULL;
  return dev;
}
