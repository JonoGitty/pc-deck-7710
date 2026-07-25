/* The hardware, replaced by nothing at all.
 *
 * Everything the firmware calls that touches a register is declared here and
 * implemented in sim_stubs.c as either a no-op or a host equivalent. The line
 * is drawn deliberately low: the further up it goes, the more of the real
 * firmware gets replaced by something that only resembles it, and the less a
 * passing test means.
 */
#ifndef SIM_STUBS_H
#define SIM_STUBS_H

#include <stdint.h>
#include <math.h>

/* Output: raw frames to a PPM stream a Python script turns into a GIF, or
 * nothing at all when only the ASCII matters. */
void sim_out_begin(const char *gifpath, int w, int h, int fps);
void sim_out_frame(const uint8_t *dev, const uint8_t *levels, int w, int h);
void sim_out_end(void);
void sim_ascii(const uint8_t *levels, int w, int h);

#endif /* SIM_STUBS_H */
