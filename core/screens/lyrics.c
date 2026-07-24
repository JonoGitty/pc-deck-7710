/* Screen 10 — lyrics.
 * Synced LRC scrolls with the playhead, current line hot and neighbours dim,
 * instrumental gaps drawn as a rest. Ported from vizLyrics in
 * legacy/web/viz.js, with one addition: on panels that cannot hold a brightness
 * difference, the current line gets a marker instead. See docs/UI-SPEC.md.
 */
#include "../screens.h"
#include "../font.h"
#include "../meta.h"
#include "../text.h"

#define ROW_PITCH 11

void deck_lyrics_reset(deck_meta_t *m) {
  m->lineCount = 0;
  m->rowCount = 0;
}

int deck_lyrics_add(deck_meta_t *m, double t, const char *raw, int cells) {
  if (m->lineCount >= DECK_LYRIC_LINES || m->rowCount >= DECK_LYRIC_ROWS) return 0;
  if (cells > DECK_LYRIC_COLS - 1) cells = DECK_LYRIC_COLS - 1;

  const int li = m->lineCount++;
  m->lineTime[li] = t;

  char folded[DECK_LYRIC_COLS * 6];
  deck_fold(raw, folded, sizeof folded);

  char rows[DECK_LYRIC_ROWS][DECK_LYRIC_COLS];
  const int room = DECK_LYRIC_ROWS - m->rowCount;
  const int n = deck_wrap(folded, cells, &rows[0][0], DECK_LYRIC_COLS, room);

  for (int r = 0; r < n; r++) {
    int c = 0;
    for (; rows[r][c] && c < DECK_LYRIC_COLS - 1; c++) m->rows[m->rowCount][c] = rows[r][c];
    m->rows[m->rowCount][c] = 0;
    m->rowLine[m->rowCount] = li;
    m->rowCount++;
  }
  return n;
}

int deck_lyric_index_at(const deck_meta_t *m, double t) {
  int lo = 0, hi = m->lineCount - 1, res = -1;
  while (lo <= hi) {
    const int mid = (lo + hi) / 2;
    if (m->lineTime[mid] <= t) { res = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return res;
}

/* Rows of pitch 11 above the status row, the last needing only glyph height. */
int deck_lyric_rows(const deck_geom_t *g) {
  const int avail = (int)g->h - 8;
  if (avail < 7) return 1;
  return (avail - 7) / ROW_PITCH + 1;
}

static void centre5(deck_fb_t *fb, int y, const char *s, uint8_t inten) {
  const int w = deck_width5(s, 1);
  int x = ((int)fb->geom->w - w) / 2;
  if (x < 0) x = 0;
  deck_text5(fb, x, y, s, inten, 1);
}

void deck_screen_lyrics(deck_fb_t *fb, const deck_state_t *v, const deck_meta_t *m,
                        double now_ms) {
  const deck_geom_t *g = fb->geom;
  const int W = (int)g->w, H = (int)g->h;
  const double pos = m->position + m->offsetMs / 1000.0;
  const int nrows = deck_lyric_rows(g);

  if (m->lyricState != DECK_LYR_OK || m->rowCount == 0) {
    char msg[32];
    int n = 0;
    if (m->lyricState == DECK_LYR_SEARCHING) {
      const char *base = "SEARCHING LYRICS";
      while (*base) msg[n++] = *base++;
      const int dots = ((int)(now_ms / 400.0)) % 4;
      for (int i = 0; i < dots; i++) msg[n++] = '.';
    } else {
      const char *base = m->title[0] ? "NO LYRICS FOUND" : "NO TRACK";
      while (*base) msg[n++] = *base++;
    }
    msg[n] = 0;
    centre5(fb, H * 14 / 48, msg, DECK_MAIN);
    if (m->title[0])  centre5(fb, H * 27 / 48, m->title, deck_thin_inten(g, DECK_DIM));
    if (m->artist[0]) centre5(fb, H * 37 / 48, m->artist, deck_thin_inten(g, DECK_DIM));
    return;
  }

  int cur = -1, top;
  if (m->synced) {
    cur = deck_lyric_index_at(m, pos);
    int first = 0;                               /* first row of the current line */
    if (cur >= 0)
      for (int i = 0; i < m->rowCount; i++)
        if (m->rowLine[i] == cur) { first = i; break; }
    top = first - 1;
  } else {
    double frac = m->duration > 0 ? pos / m->duration : 0;
    if (frac < 0) frac = 0;
    if (frac > 1) frac = 1;
    const int spread = m->rowCount - (nrows - 1) > 1 ? m->rowCount - (nrows - 1) : 1;
    top = (int)(frac * spread);
  }
  const int maxTop = m->rowCount - nrows > 0 ? m->rowCount - nrows : 0;
  if (top < 0) top = 0;
  if (top > maxTop) top = maxTop;

  for (int k = 0; k < nrows; k++) {
    const int ri = top + k;
    if (ri >= m->rowCount) break;
    const int y = 1 + k * ROW_PITCH;
    const int isCur = m->synced && cur >= 0 && m->rowLine[ri] == cur;
    const char *text = m->rows[ri];

    if (isCur && !text[0]) {                     /* instrumental rest */
      centre5(fb, y, "\xe2\x99\xaa", v->bassAvg > 0.45 ? DECK_HOT : DECK_MAIN);
      continue;
    }

    /* Glyphs are thin: the current line has to go through the rule too, or it
     * dithers to mush on 1-bit while the dim lines around it stay crisp. */
    const uint8_t inten = m->synced ? deck_thin_inten(g, isCur ? DECK_HOT : DECK_DIM)
                                    : deck_thin_inten(g, DECK_MAIN);
    centre5(fb, y, text, inten);

    /* Once both are solid, brightness no longer marks the current line, so a
     * caret does — on its first row only, or a wrapped line gets one per row. */
    const int firstOfLine = (ri == 0) || (m->rowLine[ri - 1] != m->rowLine[ri]);
    if (isCur && firstOfLine && g->levels < DECK_LEVELS && text[0]) {
      const int tw = deck_width5(text, 1);
      int mx = (W - tw) / 2 - 7;
      if (mx < 0) mx = 0;
      deck_text5(fb, mx, y, "\xe2\x96\xb6", DECK_CLIP, 1);
    }
  }

  if (m->duration > 0)
    deck_progress_bar(fb, H - 1, 4, W - 5, pos / m->duration);

  const uint8_t lab = deck_thin_inten(g, DECK_DIM);
  if (m->offsetMs != 0) {
    char s[16];
    int n = 0;
    double a = m->offsetMs < 0 ? -m->offsetMs : m->offsetMs;
    s[n++] = m->offsetMs > 0 ? '+' : '-';
    const int hundredths = deck_round(a / 10.0);
    s[n++] = (char)('0' + (hundredths / 100) % 10);
    s[n++] = '.';
    s[n++] = (char)('0' + (hundredths / 10) % 10);
    s[n++] = (char)('0' + hundredths % 10);
    s[n++] = 'S';
    s[n] = 0;
    deck_text3(fb, 2, H - 6, s, lab);
  }
  if (!m->synced)
    deck_text3(fb, W - 2 - deck_width3("NO SYNC"), H - 6, "NO SYNC", lab);
}
