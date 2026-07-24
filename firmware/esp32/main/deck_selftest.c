/* Boot self-test and the status screen.
 *
 * The problem this solves: a deck that shows nothing has six equally likely
 * causes and, from the outside, one symptom. Is it dead? Is the SPI miswired?
 * Did the panel init sequence not take? Did the renderer crash? Is it fine and
 * simply waiting for a phone? You cannot tell, and you will spend an evening
 * finding out.
 *
 * So the boot sequence proves things in an order where each stage can only
 * fail for one reason, and says which stage it reached.
 *
 *   STAGE 1  Driver test pattern, straight from the panel driver. No core/, no
 *            framebuffer, no output stage. If this appears, the wiring, the
 *            SPI clock and the init sequence are all good, and every later
 *            failure is software. If it does not, nothing after it can.
 *
 *   STAGE 2  The same pattern through core/'s output stage. This is the one
 *            that catches a level-mapping or dither fault, because stage 1
 *            bypassed exactly that code.
 *
 *   STAGE 3  Text from the character ROM. Proves the font, the framebuffer and
 *            the coordinate system — and text is the canary for a mirrored
 *            axis, because a flipped display draws everything else plausibly.
 *
 *   STAGE 4  The status screen: what each subsystem thinks of itself.
 *
 * The whole thing takes about two seconds and runs on every boot. It is also
 * reachable later by holding DISP at power-on, which is how you diagnose a
 * deck that has been in a dashboard for six months.
 */
#include "deck_selftest.h"

#include <stdio.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include "esp_system.h"

#include "deck.h"
#include "deck_diag.h"
#include "deck_display.h"
#include "font.h"
#include "out.h"

void deck_selftest_run(uint8_t *fbpx, uint8_t *dev, uint8_t *scratch, int ms) {
  const deck_panel_t *p = deck_panel();
  const deck_geom_t geom = {(uint16_t)p->w, (uint16_t)p->h, DECK_LEVELS, 0};
  deck_fb_t fb = {&geom, fbpx};

  deck_diag_event(DECK_SUB_DISPLAY, "selftest", "stage=1 what=driver-pattern");
  for (int i = 0; i < ms / 40 / 4; i++) {
    p->test_pattern(dev, i);
    p->blit(dev, scratch);
    deck_delay_ms(40);
  }

  deck_diag_event(DECK_SUB_DISPLAY, "selftest", "stage=2 what=output-stage");
  for (int i = 0; i < ms / 40 / 4; i++) {
    /* A full intensity sweep 0..4 across the panel, drawn as core/ levels and
     * pushed through deck_out_frame. On a 16-grey panel this should be five
     * clean bands; on a 1-bit panel, four dither densities and black. Anything
     * else is an output-stage fault, and it can only be an output-stage fault,
     * because stage 1 already proved the glass. */
    deck_clear(&fb);
    for (int y = 0; y < p->h; y++)
      for (int x = 0; x < p->w; x++)
        deck_set(&fb, x, y, (uint8_t)((x * 5) / p->w));
    deck_out_frame(&fb, dev, p->levels);
    p->blit(dev, scratch);
    deck_delay_ms(40);
  }

  deck_diag_event(DECK_SUB_DISPLAY, "selftest", "stage=3 what=font");
  {
    const esp_app_desc_t *app = esp_app_get_description();
    char line[40];
    deck_clear(&fb);
    deck_text5(&fb, 2, 2, "DECK 7710", DECK_HOT, 2);
    snprintf(line, sizeof line, "%s  %s", app->version, p->name);
    deck_text5(&fb, 2, p->h / 2 + 2, line, DECK_MAIN, 1);
    /* Both ends of the alphabet and a digit run, because a partially
     * populated font ROM fails on exactly the characters nobody tests. */
    deck_text3(&fb, 2, p->h - 8, "ABCXYZ 0123456789 ...", DECK_DIM);
    deck_out_frame(&fb, dev, p->levels);
    p->blit(dev, scratch);
    deck_delay_ms(ms / 4);
  }

  deck_diag_set(DECK_SUB_DISPLAY, DECK_HEALTH_OK, "%s %dx%d/%u",
                p->name, p->w, p->h, (unsigned)p->levels);
}

void deck_selftest_status(uint8_t *fbpx, uint8_t *dev, uint8_t *scratch) {
  const deck_panel_t *p = deck_panel();
  const deck_geom_t geom = {(uint16_t)p->w, (uint16_t)p->h, DECK_LEVELS, 0};
  deck_fb_t fb = {&geom, fbpx};
  char line[48];

  deck_clear(&fb);
  deck_text3(&fb, 2, 0, "SELF TEST", DECK_HOT);
  snprintf(line, sizeof line, "HEAP %uK", (unsigned)(esp_get_free_heap_size() / 1024));
  deck_text3(&fb, p->w - 6 * (int)strlen(line) / 2 - 40, 0, line, DECK_DIM);

  /* Health as text rather than as a lamp. A row of coloured dots needs a key,
   * and the panel has no colour anyway — the point of the screen is that
   * someone can photograph it and read it. */
  int y = 8;
  for (int i = 0; i < DECK_SUB_COUNT && y + 6 <= p->h; i++) {
    const deck_health_t h = deck_diag_get((deck_sub_t)i);
    snprintf(line, sizeof line, "%-8s %-8s %s",
             deck_diag_sub_name((deck_sub_t)i),
             deck_diag_health_name(h),
             deck_diag_detail((deck_sub_t)i));
    deck_text3(&fb, 2, y, line,
               h == DECK_HEALTH_FAILED ? DECK_CLIP
             : h == DECK_HEALTH_OK     ? DECK_MAIN
                                       : DECK_DIM);
    y += 6;
  }
  deck_out_frame(&fb, dev, p->levels);
  p->blit(dev, scratch);
}
