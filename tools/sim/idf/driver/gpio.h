/* Fake ESP-IDF — see idf/README.md. Level changes are timestamped on the
 * virtual clock so "reset was pulsed before anything talked to the chip" is a
 * check rather than a hope. */
#ifndef SIM_DRIVER_GPIO_H
#define SIM_DRIVER_GPIO_H

#include <stdint.h>
#include "esp_err.h"

#define GPIO_MODE_INPUT        1
#define GPIO_MODE_OUTPUT       2
#define GPIO_MODE_INPUT_OUTPUT 3
#define GPIO_PULLUP_DISABLE    0
#define GPIO_PULLUP_ENABLE     1
#define GPIO_PULLDOWN_DISABLE  0
#define GPIO_PULLDOWN_ENABLE   1
#define GPIO_INTR_DISABLE      0

typedef int gpio_num_t;

typedef struct {
  uint64_t pin_bit_mask;
  int mode;
  int pull_up_en;
  int pull_down_en;
  int intr_type;
} gpio_config_t;

esp_err_t gpio_config(const gpio_config_t *cfg);
esp_err_t gpio_set_level(gpio_num_t pin, uint32_t level);
int       gpio_get_level(gpio_num_t pin);

#endif
