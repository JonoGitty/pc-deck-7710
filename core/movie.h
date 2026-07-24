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
 *               3D scenes from tools/ledcine, hand-drawn loops, converted
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
 */
#ifndef DECK_MOVIE_H
#define DECK_MOVIE_H

#include "deck.h"

#define DECK_MOVIE_MAGIC "DMV1"
#define DECK_MOVIE_LOOP  0x01

typedef struct {
  const uint8_t *data;
  uint32_t       size;
  uint16_t       w, h;
  uint8_t        fps, flags;
  uint16_t       frameCount;
  const char    *name;
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

/* Validate a .dmv in memory. Returns 1 on success, 0 if malformed. */
int  deck_movie_open(deck_movie_t *m, const uint8_t *data, uint32_t size);

/* Rewind to frame 0 and clear the grid. */
void deck_movie_start(deck_movie_play_t *p, const deck_movie_t *m, uint8_t *grid);

/* Apply the next frame's deltas. Returns 1 if a frame was applied. */
int  deck_movie_step(deck_movie_play_t *p);

/* Draw the decoded grid, centred, cropping or letterboxing as needed. A movie
 * baked for one panel therefore still plays on another. */
void deck_movie_blit(deck_fb_t *fb, const deck_movie_play_t *p);

#endif /* DECK_MOVIE_H */
