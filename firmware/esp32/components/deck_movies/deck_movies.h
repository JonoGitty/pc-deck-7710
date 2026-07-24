/* Baked movies, read from the `movies` flash partition. See deck_movies.c and
 * firmware/esp32/partitions.csv for why they are not in the app image. */
#ifndef DECK_MOVIES_H
#define DECK_MOVIES_H

#include "esp_partition.h"
#include "movie.h"

#define DECK_MOVIES_MAX 16

typedef struct {
  char                       name[32];
  const esp_partition_t     *part;
  uint32_t                   base;      /* offset of the .dmv in the partition */
  uint32_t                   length;
} deck_movie_flash_t;

typedef struct {
  const esp_partition_t *part;
  uint16_t               count;
  deck_movie_flash_t     entry[DECK_MOVIES_MAX];
} deck_movies_t;

/* Read the directory. Returns the number of movies found, 0 if the partition
 * is missing or unformatted — which is not an error, just a deck with no
 * movies on it. */
int deck_movies_mount(deck_movies_t *lib);

/* Open one for playback. The library must outlive the movie: the decoder's
 * source points into `lib->entry[index]`. */
int deck_movies_open(deck_movies_t *lib, int index, deck_movie_t *out);

#endif /* DECK_MOVIES_H */
