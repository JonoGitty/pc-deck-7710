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
#include "../core/art.h"
#include "../core/text.h"

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
static deck_meta_t  meta;
static deck_scroll_t cover_scroll;
static uint8_t lum[128 * 128];
static uint8_t artbuf[128 * 128];

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

/* Bulk access: JS builds typed-array views over these rather than making a
 * call per element. wfHist is float to match the JS Float32Array exactly. */
EXPORT(deck_bands_ptr)  double *deck_bands_ptr(void)  { return st.bands; }
EXPORT(deck_peaks_ptr)  double *deck_peaks_ptr(void)  { return st.peaks; }
EXPORT(deck_bandsl_ptr) double *deck_bandsl_ptr(void) { return st.bandsL; }
EXPORT(deck_bandsr_ptr) double *deck_bandsr_ptr(void) { return st.bandsR; }
EXPORT(deck_wave_ptr)   double *deck_wave_ptr(void)   { return st.wave; }
EXPORT(deck_wf_ptr)     float  *deck_wf_ptr(void)     { return &st.wfHist[0][0]; }
EXPORT(deck_wavehist_ptr) double *deck_wavehist_ptr(void) { return &st.waveHist[0][0]; }

EXPORT(deck_set_counts) void deck_set_counts(int wf, int wh) {
  st.wfCount = wf; st.waveHistCount = wh;
}
EXPORT(deck_set_scope_gain) void deck_set_scope_gain(double g) { st.scopeGain = g; }
EXPORT(deck_set_clip) void deck_set_clip(int c) { st.clip = c; }
EXPORT(deck_text_i) int deck_text_i(int want) { return deck_thin_inten(&geom, (uint8_t)want); }

/* --- track metadata ----------------------------------------------------- */
static void copy_str(char *dst, size_t cap, const char *src) {
  size_t i = 0;
  for (; src[i] && i + 1 < cap; i++) dst[i] = src[i];
  dst[i] = 0;
}

EXPORT(deck_set_title)  void deck_set_title(void)  { copy_str(meta.title,  DECK_STR_MAX, strbuf); }
EXPORT(deck_set_artist) void deck_set_artist(void) { copy_str(meta.artist, DECK_STR_MAX, strbuf); }
EXPORT(deck_set_album)  void deck_set_album(void)  { copy_str(meta.album,  DECK_STR_MAX, strbuf); }
EXPORT(deck_set_app)    void deck_set_app(void)    { copy_str(meta.app,    16, strbuf); }

EXPORT(deck_set_transport) void deck_set_transport(double pos, double dur, int status) {
  meta.position = pos; meta.duration = dur; meta.status = status;
}
EXPORT(deck_set_lyric_state) void deck_set_lyric_state(int state, int synced, double offsetMs) {
  meta.lyricState = state; meta.synced = synced; meta.offsetMs = offsetMs;
}
EXPORT(deck_lyrics_clear) void deck_lyrics_clear(void) { deck_lyrics_reset(&meta); }
EXPORT(deck_lyrics_push) int deck_lyrics_push(double t, int cells) {
  return deck_lyrics_add(&meta, t, strbuf, cells);
}

/* JS writes luminance here, the core dithers it — the same call the firmware
 * makes after decoding a JPEG. */
EXPORT(deck_lum_ptr) uint8_t *deck_lum_ptr(void) { return lum; }
EXPORT(deck_make_art) void deck_make_art(int side) {
  if (side <= 0 || side > 128) { meta.art = 0; meta.artSide = 0; return; }
  deck_art_dither(lum, side, artbuf);
  meta.art = artbuf; meta.artSide = side;
}
EXPORT(deck_clear_art) void deck_clear_art(void) { meta.art = 0; meta.artSide = 0; }

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

EXPORT(deck_render_spectrum)  void deck_render_spectrum(void)  { deck_screen_spectrum(&fb, &st); }
EXPORT(deck_render_mirror)    void deck_render_mirror(void)    { deck_screen_mirror(&fb, &st); }
EXPORT(deck_render_scope)     void deck_render_scope(void)     { deck_screen_scope(&fb, &st); }
EXPORT(deck_render_city)      void deck_render_city(void)      { deck_screen_city(&fb, &st); }
EXPORT(deck_render_waterfall) void deck_render_waterfall(void) { deck_screen_waterfall(&fb, &st); }
EXPORT(deck_render_vu)        void deck_render_vu(void)        { deck_screen_vu(&fb, &st); }
EXPORT(deck_render_3d)        void deck_render_3d(void)        { deck_screen_3d(&fb, &st); }
EXPORT(deck_render_cover)     void deck_render_cover(double dt) {
  deck_screen_cover(&fb, &st, &meta, &cover_scroll, dt);
}
EXPORT(deck_render_lyrics)    void deck_render_lyrics(double now) {
  deck_screen_lyrics(&fb, &st, &meta, now);
}

EXPORT(deck_dot) void deck_dot(int x, int y, int inten) { deck_set(&fb, x, y, (uint8_t)inten); }
EXPORT(deck_wipe) void deck_wipe(int edge) { deck_wipe_from(&fb, edge); }

/* --- output stage ------------------------------------------------------- */
EXPORT(deck_emit) void deck_emit(void) { deck_out_frame(&fb, dev, geom.levels); }
