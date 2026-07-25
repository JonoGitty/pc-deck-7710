/* Fake ESP-IDF — see idf/README.md.
 *
 * The new-style (v5.x) I2C master API, which is the one the firmware uses.
 * Every transfer is recorded and then handed to whichever device model owns
 * the address, so `deck_tuner.c` is talking to something that answers like a
 * Si4735 rather than to a function that returns ESP_OK.
 */
#ifndef SIM_DRIVER_I2C_MASTER_H
#define SIM_DRIVER_I2C_MASTER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include "esp_err.h"

#define I2C_NUM_0 0
#define I2C_CLK_SRC_DEFAULT 0
#define I2C_ADDR_BIT_LEN_7  0

typedef struct sim_i2c_bus *i2c_master_bus_handle_t;
typedef struct sim_i2c_dev *i2c_master_dev_handle_t;

typedef struct {
  int i2c_port;
  int sda_io_num;
  int scl_io_num;
  int clk_source;
  int glitch_ignore_cnt;
  struct { int enable_internal_pullup; } flags;
} i2c_master_bus_config_t;

typedef struct {
  int      dev_addr_length;
  uint16_t device_address;
  uint32_t scl_speed_hz;
} i2c_device_config_t;

esp_err_t i2c_new_master_bus(const i2c_master_bus_config_t *cfg,
                             i2c_master_bus_handle_t *out);
esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t bus,
                                    const i2c_device_config_t *cfg,
                                    i2c_master_dev_handle_t *out);
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t dev);
esp_err_t i2c_master_probe(i2c_master_bus_handle_t bus, uint16_t addr, int to);

esp_err_t i2c_master_transmit(i2c_master_dev_handle_t dev, const uint8_t *buf,
                              size_t n, int timeout_ms);
esp_err_t i2c_master_receive(i2c_master_dev_handle_t dev, uint8_t *buf,
                             size_t n, int timeout_ms);
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t dev,
                                      const uint8_t *tx, size_t txn,
                                      uint8_t *rx, size_t rxn, int timeout_ms);

#endif
