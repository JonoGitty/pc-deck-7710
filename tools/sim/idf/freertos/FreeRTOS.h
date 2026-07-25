/* Fake ESP-IDF — see idf/README.md. */
#ifndef SIM_FREERTOS_H
#define SIM_FREERTOS_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t TickType_t;
typedef int BaseType_t;

#define portMAX_DELAY   ((TickType_t)0xFFFFFFFFu)
#define portTICK_PERIOD_MS 1
#define pdTRUE  1
#define pdFALSE 0

/* One tick is one millisecond here. The real port is 10 ms by default, which
 * would round the driver's waits and make a timing assertion argue with the
 * tick rate instead of with the driver. */
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))

#endif
