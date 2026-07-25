/* Which thing is making the noise.
 *
 * A head unit has sources, and only one of them reaches the amplifier at a
 * time. On this deck they are Bluetooth (the DAC), the radio (the Si4735's own
 * line output) and aux (a socket on the fascia) — three analogue signals that
 * must never be connected together.
 *
 * WHY THE AUDIO DOES NOT GO THROUGH THE ESP32
 *
 * The obvious design is to digitise everything and mix in software. It is also
 * the wrong one: it costs an I2S ADC and a pin this build does not have, it
 * resamples a tuner's output for no reason, and it puts a microcontroller in
 * the path of audio that was already analogue and already fine.
 *
 * So the switching is analogue — a 74HC4052 dual 4-channel mux, two GPIOs
 * selecting one stereo pair of four. This is what every real head unit does.
 *
 * THE COST, STATED PLAINLY
 *
 * The spectrum analyser is fed from the I2S stream, and on radio or aux there
 * is no I2S stream. **The analyser goes flat on any source but Bluetooth.**
 * On a deck built around an analyser that is a real loss, and the fix is a
 * PCM1808 I2S ADC on a pin that does not currently exist. deck_ui knows about
 * this and shows the radio screen rather than a dead analyser.
 */
#ifndef DECK_SOURCE_H
#define DECK_SOURCE_H

typedef enum {
  DECK_SRC_BT = 0,       /* the DAC, fed by A2DP */
  DECK_SRC_RADIO,        /* the Si4735's line output */
  DECK_SRC_AUX,          /* the fascia socket */
  DECK_SRC_COUNT
} deck_source_t;

/* Configures the two select pins and selects `initial`. Returns 0, or a
 * negative value if the GPIOs could not be configured — in which case the mux
 * is wherever its pull-downs left it, which is source 0, which is Bluetooth,
 * which is the one you want if something has gone wrong. */
int deck_source_start(deck_source_t initial);

void          deck_source_set(deck_source_t s);
deck_source_t deck_source_get(void);
deck_source_t deck_source_next(void);      /* what SRC does */
const char   *deck_source_name(deck_source_t s);

#endif /* DECK_SOURCE_H */
