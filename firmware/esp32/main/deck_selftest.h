/* Boot self-test and the on-panel status screen. See deck_selftest.c for why
 * the stages are ordered the way they are. */
#ifndef DECK_SELFTEST_H
#define DECK_SELFTEST_H

#include <stdint.h>

/* Runs the four stages over roughly `ms` milliseconds. All three buffers are
 * caller-owned; nothing in the firmware's display path allocates. */
void deck_selftest_run(uint8_t *fbpx, uint8_t *dev, uint8_t *scratch, int ms);

/* One frame of the subsystem health table, for holding on screen. */
void deck_selftest_status(uint8_t *fbpx, uint8_t *dev, uint8_t *scratch);

/* The steering-wheel learning wizard, drawn on the panel because it is done
 * sitting in the driver's seat. See deck_swc.c for why it learns rather than
 * decoding a table. */
void deck_swc_run_wizard(uint8_t *fbpx, uint8_t *dev, uint8_t *scratch);

#endif /* DECK_SELFTEST_H */
