/* Fake ESP-IDF — see idf/README.md.
 *
 * vTaskDelay ADVANCES THE VIRTUAL CLOCK rather than sleeping. Every wait the
 * drivers perform therefore shows up in the recorded timeline, which is how
 * AN332's 110 ms post-POWER_UP rule gets asserted at all. */
#ifndef SIM_FREERTOS_TASK_H
#define SIM_FREERTOS_TASK_H

#include "freertos/FreeRTOS.h"

void vTaskDelay(TickType_t ticks);

typedef void *TaskHandle_t;
BaseType_t xTaskCreate(void (*fn)(void *), const char *name, uint32_t stack,
                       void *arg, unsigned prio, TaskHandle_t *out);

#endif
