/* Movies — the deck's animation system.
 *
 * Two kinds, deliberately:
 *
 *   PROCEDURAL  generated per frame from code and audio energy. The dolphins
 *               are one of these, which is why they react to bass. Cheap in
 *               flash, expensive in code, and the only kind that can respond
 *               to what is playing.
 *
 *   BAKED       pre-rendered frames played back. Anything can be baked —
 *               3D scenes from tools/movies, hand-drawn loops, converted
 *               GIFs — because by the time it gets here it is just levels on
 *               a grid. Cheap in code, costs flash, cannot react.
 *
 * A baked movie is a .dmv: delta-compressed runs against the deck's five
 * intensity levels. The format is deliberately dumb so the firmware decoder is
 * a loop with no allocation, and so anyone can write an exporter.
 *
 *   off  size  field
 *   0    4     magic "DMV1"
 *   4    2     grid width   (u16 LE)
 *   6    2     grid height
 *   8    1     fps
 *   9    1     flags: bit0 loop
 *   10   2     frame count
 *   12   2     name length
 *   14   n     name, ASCII
 *   ..         per frame: u16 run count, then runs of
 *              { u16 start, u16 len, u8 level }
 *
 * Frames are deltas against the previous frame, and the decoder starts from a
 * cleared grid — so frame 0 encodes everything lit, and looping means clearing
 * and replaying rather than seeking.
 *
 * WHERE THE BYTES COME FROM
 *
 * A movie is read strictly forwards. Nothing seeks except the rewind to frame
 * 0 that looping does, and that is a rewind to a known offset, not a search.
 * So the decoder does not need the file — it needs a thing that will hand over
 * bytes at an offset, which is `deck_movie_src_t`.
 *
 * That is not abstraction for its own sake. A 256x64 movie is most of a
 * megabyte; the ESP32's app partition is a megabyte and a half in a common
 * 4 MB layout. Baking even one into the firmware image does not fit, and
 * baking three is absurd. With a source, a movie lives in its own read-only
 * partition, or on an SD card, and plays out of a 320-byte stack buffer at
 * whatever size it happens to be. The flash cost of a movie stops being a
 * firmware problem and becomes a "how big is your card" problem.
 *
 * `deck_movie_open` still takes a flat pointer, because in the browser preview
 * and in the verifier the whole file genuinely is in memory, and because an
 * ESP32 can memory-map a flash partition and get a flat pointer for free.
 */
#ifndef DECK_MOVIE_H
#define DECK_MOVIE_H

#include "deck.h"

#define DECK_MOVIE_MAGIC "DMV1"
#define DECK_MOVIE_LOOP  0x01
#define DECK_MOVIE_NAME_MAX 31

/* Read `n` bytes at absolute offset `off` into `dst`; return how many were
 * actually read. Short reads are treated as end-of-movie. Must be safe to call
 * with any offset — the decoder relies on it to bound-check, not the caller. */
typedef struct {
  uint32_t (*read)(void *ctx, uint32_t off, uint8_t *dst, uint32_t n);
  void     *ctx;
  uint32_t  size;
} deck_movie_src_t;

typedef struct {
  deck_movie_src_t src;
  /* Set only when opened over a flat buffer; `src.ctx` then points at this
   * struct, so a deck_movie_t opened that way must not be moved or copied. */
  const uint8_t *mem;
  uint16_t       w, h;
  uint8_t        fps, flags;
  uint16_t       frameCount;
  /* Copied, not borrowed: with a streaming source there is nothing to borrow
   * from. Longer names are truncated rather than rejected. */
  char           name[DECK_MOVIE_NAME_MAX + 1];
  uint8_t        nameLen;
  uint32_t       firstFrame;      /* byte offset of frame 0 */
} deck_movie_t;

/* Playback cursor. `grid` is caller-owned and must hold w*h bytes — the
 * decoder writes levels into it and never allocates. */
typedef struct {
  const deck_movie_t *movie;
  uint8_t            *grid;
  uint32_t            cursor;     /* byte offset of the next frame */
  uint16_t            frame;
  int                 done;       /* set on a non-looping movie's last frame */
} deck_movie_play_t;

/* Validate a .dmv. Returns 1 on success, 0 if malformed.
 *
 * `_open` wraps a flat buffer; `_open_src` takes any source. The source is
 * copied into the movie, so the caller's deck_movie_src_t need not outlive the
 * call — but whatever `ctx` points at must. */
int  deck_movie_open(deck_movie_t *m, const uint8_t *data, uint32_t size);
int  deck_movie_open_src(deck_movie_t *m, const deck_movie_src_t *src);

/* Rewind to frame 0 and clear the grid. */
void deck_movie_start(deck_movie_play_t *p, const deck_movie_t *m, uint8_t *grid);

/* Apply the next frame's deltas. Returns 1 if a frame was applied. */
int  deck_movie_step(deck_movie_play_t *p);

/* Draw the decoded grid, centred, cropping or letterboxing as needed. A movie
 * baked for one panel therefore still plays on another. */
void deck_movie_blit(deck_fb_t *fb, const deck_movie_play_t *p);

#endif /* DECK_MOVIE_H */
