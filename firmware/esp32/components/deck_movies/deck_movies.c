/* Play a .dmv straight out of flash, without ever holding it in RAM.
 *
 * The whole of this file exists because of one arithmetic problem. A baked
 * 256x64 movie is 300-850 KB. The ESP32 has 320 KB of DRAM, most of which is
 * spoken for by the Bluetooth stack, the WiFi stack and the FFT. Even with
 * PSRAM, reading a megabyte off flash into RAM so that a decoder can walk it
 * forwards once is work done for no reason.
 *
 * core/movie.c takes a source instead of a pointer, so the decoder reads
 * 320 bytes at a time out of a read-only partition and the movie is never
 * anywhere but flash. The same shape works for an SD card — swap this file's
 * read function for one that calls fread and nothing else changes.
 *
 * There is a second, simpler route on this chip: esp_partition_mmap() maps a
 * partition into the CPU's data address space and hands back a plain const
 * pointer, which deck_movie_open() takes directly with no source at all. It is
 * a good option and it is cheaper per read. It is not the default here because
 * the mapped data window is finite and shared with anything else that wants
 * it, and because the streaming path is the one that also works from a card.
 *
 * STATUS: never run on hardware. Like everything else under firmware/.
 */
#include "deck_movies.h"

#include "esp_partition.h"

/* The movies partition is a container, not a file: a tiny directory followed
 * by the .dmv blobs, so that adding a movie is a partition reflash and not a
 * rebuild. Written by tools/movies/pack.py.
 *
 *   off  size  field
 *   0    4     magic "DMVP"
 *   4    2     entry count
 *   6    2     reserved
 *   8    n*40  entries: { char name[32], u32 offset, u32 length }
 */
#define PACK_MAGIC   "DMVP"
#define PACK_ENTRY   40
#define PACK_HEADER  8

static uint32_t rd32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Offsets arriving here are movie-relative; the movie does not know it lives
 * at a base offset inside a larger partition, and should not have to. */
static uint32_t src_partition(void *ctx, uint32_t off, uint8_t *dst, uint32_t n) {
  deck_movie_flash_t *fm = (deck_movie_flash_t *)ctx;
  if (off >= fm->length) return 0;
  uint32_t avail = fm->length - off;
  if (n > avail) n = avail;
  if (esp_partition_read(fm->part, fm->base + off, dst, n) != ESP_OK) return 0;
  return n;
}

int deck_movies_mount(deck_movies_t *lib) {
  lib->part = esp_partition_find_first(ESP_PARTITION_TYPE_DATA,
                                       (esp_partition_subtype_t)0x40, "movies");
  lib->count = 0;
  if (!lib->part) return 0;

  uint8_t hdr[PACK_HEADER];
  if (esp_partition_read(lib->part, 0, hdr, sizeof hdr) != ESP_OK) return 0;
  if (hdr[0] != 'D' || hdr[1] != 'M' || hdr[2] != 'V' || hdr[3] != 'P') return 0;

  uint16_t n = (uint16_t)(hdr[4] | (hdr[5] << 8));
  if (n > DECK_MOVIES_MAX) n = DECK_MOVIES_MAX;

  for (uint16_t i = 0; i < n; i++) {
    uint8_t e[PACK_ENTRY];
    if (esp_partition_read(lib->part, PACK_HEADER + (uint32_t)i * PACK_ENTRY,
                           e, sizeof e) != ESP_OK) return (int)lib->count;
    deck_movie_flash_t *fm = &lib->entry[i];
    for (int c = 0; c < 32; c++) fm->name[c] = (char)e[c];
    fm->name[31] = 0;
    fm->part = lib->part;
    fm->base = rd32(e + 32);
    fm->length = rd32(e + 36);
    lib->count++;
  }
  return (int)lib->count;
}

int deck_movies_open(deck_movies_t *lib, int index, deck_movie_t *out) {
  if (index < 0 || index >= (int)lib->count) return 0;
  deck_movie_flash_t *fm = &lib->entry[index];
  deck_movie_src_t src = { src_partition, fm, fm->length };
  return deck_movie_open_src(out, &src);
}
