/* Diagnostics: how you find out what a deck bolted into a dashboard is doing.
 *
 * This is the part of a hobby firmware that is usually missing, and its
 * absence is why people give up. The failure mode is always the same: the
 * panel is blank, and there are six equally plausible reasons — no power, SPI
 * miswired, panel init wrong, Bluetooth never connected, no audio arriving,
 * renderer crashed — with no way to tell them apart from the outside.
 *
 * So the deck reports on itself in three layers, each usable when the one
 * above is not:
 *
 *   1. THE PANEL ITSELF. A boot self-test draws a pattern from the driver
 *      before core/ is involved, so "the glass works" and "the renderer works"
 *      are separately answerable. Then a status screen with the actual state.
 *
 *   2. A SERIAL LINE. Structured one-line-per-event records over USB, greppable
 *      and parseable, plus a subsystem health table on demand. This is what
 *      `deckctl logs` and `deckctl doctor` read.
 *
 *   3. A CORE DUMP IN FLASH. When it panics, the stack trace survives the
 *      reboot and can be pulled off later — which matters because the crash
 *      you care about happens in a car, not on the bench.
 *
 * The health model is deliberately not a boolean. A subsystem is UNKNOWN until
 * it has had a chance to try, which is different from FAILED, and conflating
 * the two is how you end up chasing a Bluetooth bug on a deck that simply has
 * not been paired yet.
 */
#ifndef DECK_DIAG_H
#define DECK_DIAG_H

#include <stdint.h>

typedef enum {
  DECK_SUB_DISPLAY = 0,
  DECK_SUB_BT,
  DECK_SUB_AUDIO,
  DECK_SUB_WIFI,
  DECK_SUB_MOVIES,
  DECK_SUB_INPUT,
  DECK_SUB_STORAGE,
  DECK_SUB_COUNT
} deck_sub_t;

typedef enum {
  DECK_HEALTH_UNKNOWN = 0,   /* has not been tried yet — not a failure */
  DECK_HEALTH_OK,
  DECK_HEALTH_DEGRADED,      /* working, but not as intended */
  DECK_HEALTH_FAILED
} deck_health_t;

void deck_diag_init(void);

/* Record where a subsystem stands. `detail` is short, human, and shows up in
 * both the serial log and the on-panel status screen; pass NULL to keep the
 * previous one. */
void deck_diag_set(deck_sub_t sub, deck_health_t h, const char *fmt, ...);

deck_health_t deck_diag_get(deck_sub_t sub);
const char   *deck_diag_detail(deck_sub_t sub);
const char   *deck_diag_sub_name(deck_sub_t sub);
const char   *deck_diag_health_name(deck_health_t h);

/* One structured line on the serial port. Machine-readable on purpose: the
 * host tool greps these, and a format that needs a regexp per message is a
 * format nobody writes the tool for.
 *
 *   DECK|<uptime_ms>|<subsystem>|<event>|<key=value ...>
 */
void deck_diag_event(deck_sub_t sub, const char *event, const char *fmt, ...);

/* Everything at once: build, panel, heap, reset reason, per-subsystem health.
 * Printed at boot, and again whenever the host asks. */
void deck_diag_report(void);

/* Why the last boot happened, and whether a core dump is waiting. Printed
 * early, because "it rebooted and I do not know why" is the commonest and
 * least actionable bug report there is. */
void deck_diag_boot_reason(void);

/* Counters that tell you whether the deck is keeping up, sampled by the render
 * loop. Frame time is the one that matters: a movie at 10 fps and an analyser
 * at 40 have very different budgets and the same symptom when missed. */
void deck_diag_frame(uint32_t render_us, uint32_t blit_us);
void deck_diag_heap_check(void);

#endif /* DECK_DIAG_H */
