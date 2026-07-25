/* Fake ESP-IDF — see idf/README.md.
 *
 * The clock is VIRTUAL and only vTaskDelay() and the test harness move it.
 * That is the whole trick: a driver's timing rules become assertions instead
 * of a stopwatch, and a test that covers 2.5 seconds of call teardown runs in
 * no time at all. */
#ifndef SIM_ESP_TIMER_H
#define SIM_ESP_TIMER_H

#include <stdint.h>
#include <stdio.h>

int64_t esp_timer_get_time(void);

#endif
