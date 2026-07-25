/* Settings that survive a power cut, in NVS.
 *
 * A head unit loses power every time the key comes out, so anything the user
 * chose has to be on flash rather than in RAM. The set is deliberately small:
 * a settings menu on a 256x64 panel operated by one knob is a worse experience
 * than no settings menu, so the deck keeps the handful that matter and puts
 * the rest on the phone. See docs/CONTROL.md.
 */
#ifndef DECK_CONFIG_H
#define DECK_CONFIG_H

#include <stdint.h>

typedef struct {
  uint8_t mode;          /* display mode index at power-on */
  uint8_t brightness;    /* 0..100, overridden by the dimmer input when wired */
  uint8_t demo;          /* attract loop on */
  uint8_t movie;         /* which movie the MOVIE screen plays */
  uint8_t loud;          /* loudness lamp + fatter bass bars */
  uint8_t second_clock;  /* second line shows the clock instead of the artist */
  char    wifi_ssid[33];
  char    wifi_pass[65];
  uint8_t lyrics_enabled;
  uint8_t art_enabled;
  uint8_t source;        /* deck_source_t at power-on: a car radio comes back
                          * on the source it was left on, and being dropped
                          * onto Bluetooth every morning is not that */
} deck_cfg_t;

void deck_cfg_load(deck_cfg_t *c);
void deck_cfg_save(const deck_cfg_t *c);

/* Saving on every knob click would write NVS thousands of times a drive and
 * wear the sector out. Changes are marked dirty and flushed a few seconds
 * later, or at shutdown when the ignition drops. */
void deck_cfg_mark_dirty(void);
void deck_cfg_flush_if_due(const deck_cfg_t *c);

#endif /* DECK_CONFIG_H */
