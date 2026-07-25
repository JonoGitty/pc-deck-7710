/* Fake ESP-IDF — see idf/README.md. Not the SDK; just enough of it. */
#ifndef SIM_ESP_ERR_H
#define SIM_ESP_ERR_H

/* The real esp_err.h pulls these in, and the drivers rely on it. A fake SDK
 * that is stingier than the real one makes the driver look buggy. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef int esp_err_t;

#define ESP_OK              0
#define ESP_FAIL           -1
#define ESP_ERR_NOT_FOUND   0x105
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_TIMEOUT     0x107

#endif
