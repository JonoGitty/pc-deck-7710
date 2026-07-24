/* Controls. Every action here has a key binding on the PC deck; see
 * docs/CONTROL.md for the table that keeps them aligned. */
#ifndef DECK_INPUT_H
#define DECK_INPUT_H

typedef enum {
  DECK_ACT_NONE = 0,
  DECK_ACT_MODE_NEXT,
  DECK_ACT_MODE_PREV,
  DECK_ACT_ART,
  DECK_ACT_LYRICS,
  DECK_ACT_OCEAN,
  DECK_ACT_MOVIE_NEXT,
  DECK_ACT_DEMO,
  DECK_ACT_SRC,
  DECK_ACT_ENC_CW,
  DECK_ACT_ENC_CCW,
  DECK_ACT_PLAY_PAUSE,
  DECK_ACT_NEXT_TRACK,
  DECK_ACT_PREV_TRACK,
  DECK_ACT_IGNITION_ON,
  DECK_ACT_IGNITION_OFF,
  DECK_ACT_SELFTEST,
  DECK_ACT_SWC_LEARN,
} deck_action_t;

typedef struct { deck_action_t action; int repeat; } deck_event_t;

int  deck_input_start(void);
void deck_input_post(deck_action_t a, int repeat);
int  deck_input_get(deck_event_t *out);

#endif /* DECK_INPUT_H */
