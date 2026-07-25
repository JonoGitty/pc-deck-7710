/* Fake ESP-IDF — see idf/README.md.
 *
 * Single-threaded harness, so a mutex is a counter that records whether it was
 * balanced. Not decoration: deck_hfp.c takes the lock in a callback and in
 * poll(), and a missing unlock on one branch would deadlock on hardware and be
 * invisible in a code review. Here it fails a test. */
#ifndef SIM_FREERTOS_SEMPHR_H
#define SIM_FREERTOS_SEMPHR_H

#include "freertos/FreeRTOS.h"

typedef struct sim_sem *SemaphoreHandle_t;

SemaphoreHandle_t xSemaphoreCreateMutex(void);
BaseType_t xSemaphoreTake(SemaphoreHandle_t s, TickType_t wait);
BaseType_t xSemaphoreGive(SemaphoreHandle_t s);

/* Non-zero if any mutex was ever given without being held, or is still held
 * when the scenario ends. */
int sim_sem_imbalance(void);

#endif
