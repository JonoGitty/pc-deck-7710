/* Steering wheel controls, via the aftermarket resistive convention.
 *
 * The deck implements the *radio* side of what the industry standardised — a
 * resistance to ground — and a universal interface box does the car-specific
 * half. That is what makes an S2000, an E46 and a Fiesta all work without this
 * firmware knowing anything about any of them. See deck_swc.c.
 */
#ifndef DECK_SWC_H
#define DECK_SWC_H

#include <stdint.h>
#include "deck_input.h"
#include "deck_display.h"      /* deck_delay_ms */

#define DECK_SWC_MAX 12

enum {
  DECK_SWC_LEARN_OK = 0,
  DECK_SWC_LEARN_TIMEOUT,   /* nothing pressed — this wheel may not have it */
  DECK_SWC_LEARN_CLASH,     /* too close to a button already learned */
  DECK_SWC_LEARN_FULL,
  DECK_SWC_LEARN_DONE,
};

typedef struct {
  int16_t mv;
  uint8_t action;
  uint8_t pad;
} deck_swc_entry_t;

typedef struct {
  int32_t          idle_mv;      /* measured, not assumed: see deck_swc.c */
  int32_t          count;
  deck_swc_entry_t e[DECK_SWC_MAX];
} deck_swc_map_t;

int  deck_swc_start(void);
int  deck_swc_learned(void);
int  deck_swc_raw_mv(void);

/* One press per call, or DECK_ACT_NONE. Auto-repeats volume only. */
deck_action_t deck_swc_poll(void);

/* The learning wizard. begin(), then learn_step() for each index in
 * 0..learn_count()-1 showing learn_prompt(i) on the panel, then end(). */
void        deck_swc_learn_begin(void);
int         deck_swc_learn_step(int index, int *out_mv);
void        deck_swc_learn_end(void);
int         deck_swc_learn_count(void);
const char *deck_swc_learn_prompt(int index);

#endif /* DECK_SWC_H */
