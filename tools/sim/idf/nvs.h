/* Fake ESP-IDF — see idf/README.md.
 *
 * An in-memory blob store that outlives a simulated reboot, because the thing
 * worth testing about the tuner's persistence is exactly that: set a region,
 * "reboot", and see whether the deck comes back in the same band plan. */
#ifndef SIM_NVS_H
#define SIM_NVS_H

#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

typedef uint32_t nvs_handle_t;

typedef enum { NVS_READONLY = 0, NVS_READWRITE = 1 } nvs_open_mode_t;

esp_err_t nvs_open(const char *ns, nvs_open_mode_t mode, nvs_handle_t *out);
esp_err_t nvs_get_blob(nvs_handle_t h, const char *key, void *out, size_t *len);
esp_err_t nvs_set_blob(nvs_handle_t h, const char *key, const void *v, size_t n);
esp_err_t nvs_get_u8(nvs_handle_t h, const char *key, uint8_t *out);
esp_err_t nvs_set_u8(nvs_handle_t h, const char *key, uint8_t v);
esp_err_t nvs_commit(nvs_handle_t h);
void      nvs_close(nvs_handle_t h);

/* The harness's own door into the store: wipe it to simulate a fresh chip. */
void sim_nvs_erase_all(void);

#endif
