/* Track metadata, playhead and lyrics — what the two metadata screens read.
 *
 * Everything here is already folded ASCII (see text.h): the platform folds
 * once when metadata arrives rather than every frame.
 *
 * Art is a borrowed pointer, not a buffer, so the core carries no image-sized
 * storage and the platform decides where the sleeve lives.
 */
#ifndef DECK_META_H
#define DECK_META_H

#include <stdint.h>

#define DECK_STR_MAX     96
#define DECK_LYRIC_ROWS  64
#define DECK_LYRIC_COLS  40
#define DECK_LYRIC_LINES 96

enum { DECK_STOPPED = 0, DECK_PLAYING, DECK_PAUSED };
enum { DECK_LYR_IDLE = 0, DECK_LYR_SEARCHING, DECK_LYR_OK, DECK_LYR_NONE };

typedef struct {
  char   title[DECK_STR_MAX];
  char   artist[DECK_STR_MAX];
  char   album[DECK_STR_MAX];
  char   app[16];
  int    status;

  /* Seconds. The platform interpolates between transport updates; the core
   * just draws what it is given, so screens stay deterministic. */
  double position, duration;

  const uint8_t *art;        /* artSide*artSide levels 0..3, or NULL */
  int            artSide;

  int    lyricState;
  int    synced;
  double offsetMs;           /* manual sync trim */

  int    lineCount;
  double lineTime[DECK_LYRIC_LINES];              /* stamp per lyric line */

  int    rowCount;
  char   rows[DECK_LYRIC_ROWS][DECK_LYRIC_COLS];  /* wrapped display rows */
  int    rowLine[DECK_LYRIC_ROWS];                /* line each row came from */
} deck_meta_t;

/* Index of the last lyric line whose stamp has passed, or -1. */
int deck_lyric_index_at(const deck_meta_t *m, double t);

/* Build the display rows. Feed lines in time order; each is folded and wrapped
 * to `cells`, and every resulting row remembers the line it came from so the
 * current line can highlight across all of its wrapped rows. Returns the rows
 * added, or 0 when full. */
void deck_lyrics_reset(deck_meta_t *m);
int  deck_lyrics_add(deck_meta_t *m, double t, const char *raw, int cells);

#endif /* DECK_META_H */
