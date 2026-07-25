/* One I2C master bus, shared.
 *
 * The same problem deck_adc.c solves for ADC1 and for the same reason: the
 * driver allows one master per port, and this build now has two devices on
 * it — the Si4735 tuner and the PT2313 audio processor. Whichever started
 * first would own the bus and the second would fail with an error that reads
 * like a wiring fault.
 *
 * So neither owns it. Both ask for it, the first call creates it, and the
 * pins live here rather than in whichever file happened to need them first.
 *
 * ⚠️ NEVER RUN ON HARDWARE.
 */
#ifndef DECK_I2C_H
#define DECK_I2C_H

#include "driver/i2c_master.h"

/* The bus, created on first use. NULL if it could not be brought up. */
i2c_master_bus_handle_t deck_i2c_bus(void);

/* Add a device at `addr`. Returns NULL if the bus is down or the address is
 * already taken — the caller decides whether that is fatal, because for the
 * tuner it means "try the other address" and for the audio processor it means
 * "fall back to the mux". */
i2c_master_dev_handle_t deck_i2c_device(uint8_t addr, uint32_t hz);

#endif /* DECK_I2C_H */
