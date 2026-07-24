/* WASM surface for the browser preview.
 *
 * The preview draws whatever THIS renderer produces — the same core/ sources
 * the firmware compiles — so what you see is what the panel will show, not an
 * approximation of it. No allocation: fixed buffers sized for the largest
 * grid we intend to support.
 */
#include "../core/deck.h"
#include "../core/font.h"
#include "../core/out.h"
#include "../core/screens.h"

/* wasm-ld garbage-collects anything unreachable from an entry point, and this
 * library has none — so every entry point says so explicitly. */
#if defined(__wasm__)
#define EXPORT(n) __attribute__((export_name(#n), used))
#else
#define EXPORT(n)
#endif

#define MAX_W 512
#define MAX_H 128
#define STR_MAX 256

static uint8_t      px[MAX_W * MAX_H];
static uint8_t      dev[MAX_W * MAX_H];      /* after the output stage */
static char         strbuf[STR_MAX];
static deck_geom_t  geom = { 192, 48, DECK_LEVELS, 0 };
static deck_fb_t    fb   = { &geom, px };
static deck_state_t st;

/* --- setup ------------------------------------------------------------- */
EXPORT(deck_config) int deck_config(int w, int h, int levels, int flags) {
  if (w < 1 || h < 1 || w > MAX_W || h > MAX_H) return 0;
  geom.w = (uint16_t)w;
  geom.h = (uint16_t)h;
  geom.levels = (uint8_t)(levels < 2 ? 2 : levels);
  geom.flags = (uint8_t)flags;
  return 1;
}

EXPORT(deck_w) int deck_w(void)     { return geom.w; }
EXPORT(deck_h) int deck_h(void)     { return geom.h; }
EXPORT(deck_tier_of) int deck_tier_of(void) { return (int)deck_tier(&geom); }

EXPORT(deck_fb_ptr) uint8_t *deck_fb_ptr(void)  { return px; }
EXPORT(deck_dev_ptr) uint8_t *deck_dev_ptr(void) { return dev; }
EXPORT(deck_str_ptr) char    *deck_str_ptr(void) { return strbuf; }

/* --- state (JS pushes analysis values in) ------------------------------- */
EXPORT(deck_set_band) void deck_set_band(int i, double v) { if (i >= 0 && i < DECK_BANDS) st.bands[i] = v; }
EXPORT(deck_set_peak) void deck_set_peak(int i, double v) { if (i >= 0 && i < DECK_BANDS) st.peaks[i] = v; }
EXPORT(deck_set_vu) void deck_set_vu(double l, double r) { st.vuL = l; st.vuR = r; }

/* --- drawing ------------------------------------------------------------ */
EXPORT(deck_begin) void deck_begin(void) { deck_clear(&fb); }

EXPORT(deck_draw_text5) int deck_draw_text5(int x, int y, int inten, int scale) {
  return deck_text5(&fb, x, y, strbuf, (uint8_t)inten, scale);
}
EXPORT(deck_draw_text3) int deck_draw_text3(int x, int y, int inten) {
  return deck_text3(&fb, x, y, strbuf, (uint8_t)inten);
}
EXPORT(deck_measure5) int deck_measure5(int scale) { return deck_width5(strbuf, scale); }
EXPORT(deck_measure3) int deck_measure3(void)      { return deck_width3(strbuf); }

EXPORT(deck_render_spectrum) void deck_render_spectrum(void) { deck_screen_spectrum(&fb, &st); }

EXPORT(deck_dot) void deck_dot(int x, int y, int inten) { deck_set(&fb, x, y, (uint8_t)inten); }
EXPORT(deck_wipe) void deck_wipe(int edge) { deck_wipe_from(&fb, edge); }

/* --- output stage ------------------------------------------------------- */
EXPORT(deck_emit) void deck_emit(void) { deck_out_frame(&fb, dev, geom.levels); }
