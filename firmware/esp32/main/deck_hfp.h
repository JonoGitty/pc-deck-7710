/* Hands-free calling: HFP client, alongside A2DP.
 *
 * Fills a deck_call_t for core/screens/call.c to draw. The screen has no idea
 * Bluetooth exists — same split as everything else here, and the reason the
 * simulator can drive those screens from a text script.
 *
 * ROLES, BECAUSE THEY ARE THE OPPOSITE OF WHAT YOU EXPECT
 *
 * In HFP the phone is the *Audio Gateway* and the car kit is the *Hands-Free
 * unit*. So this deck is the HF, and it uses esp_hf_client — not esp_hf_ag,
 * which is for building a phone. Picking the wrong one gives you an API that
 * compiles and a deck that no phone will talk to.
 *
 * It is Bluetooth Classic, like A2DP, so it lands on the same side of the
 * chip question: the original ESP32 has it and the S3/C3/C6 do not. Adding
 * calls does not change the hardware choice, it reinforces it.
 *
 * ⚠️ NEVER RUN ON HARDWARE.
 */
#ifndef DECK_HFP_H
#define DECK_HFP_H

#include "screens.h"

int  deck_hfp_start(void);

/* The current call, copied out for drawing. Safe to call every frame. */
void deck_hfp_poll(deck_call_t *c);

void deck_hfp_answer(void);
void deck_hfp_reject(void);          /* also ends an active call */
void deck_hfp_redial(void);

/* True while a call is doing anything at all — the main loop uses this to
 * decide whether the music should be paused and whether the call screen
 * outranks whatever the user last selected. */
int  deck_hfp_busy(void);

#endif /* DECK_HFP_H */
