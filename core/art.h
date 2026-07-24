/* Album art dithering.
 *
 * Decoding and scaling stay OUT of the core — they are platform work (a canvas
 * in the browser, a JPEG decoder on the ESP32). The core takes an S x S
 * luminance buffer, already cropped square and scaled, and produces intensity
 * levels. That keeps the part that must render identically everywhere here,
 * and the part that depends on available libraries outside.
 */
#ifndef DECK_ART_H
#define DECK_ART_H

#include <stdint.h>

/* Contrast-stretch, then 4x4 ordered dither into levels 0..3.
 * `lum` and `out` are both s*s bytes and may not overlap. */
void deck_art_dither(const uint8_t *lum, int s, uint8_t *out);

#endif /* DECK_ART_H */
