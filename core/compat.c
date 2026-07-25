/* Freestanding support routines.
 *
 * A C compiler is allowed to turn an ordinary loop into a call to memset or
 * memcpy even when the source never mentions them — clang does exactly that
 * for the skyline init in screens/spectrum3d.c. With -nostdlib there is
 * nothing to link those against, so the core provides them.
 *
 * Only compiled into freestanding builds; a hosted build uses libc's, which
 * are faster and would otherwise clash.
 */
#if defined(__wasm__) || defined(DECK_FREESTANDING)

#include <stddef.h>

void *memset(void *dst, int c, size_t n) {
  unsigned char *p = (unsigned char *)dst;
  while (n--) *p++ = (unsigned char)c;
  return dst;
}

void *memcpy(void *dst, const void *src, size_t n) {
  unsigned char *d = (unsigned char *)dst;
  const unsigned char *s = (const unsigned char *)src;
  while (n--) *d++ = *s++;
  return dst;
}

void *memmove(void *dst, const void *src, size_t n) {
  unsigned char *d = (unsigned char *)dst;
  const unsigned char *s = (const unsigned char *)src;
  if (d == s || n == 0) return dst;
  if (d < s) { while (n--) *d++ = *s++; }
  else { d += n; s += n; while (n--) *--d = *--s; }
  return dst;
}

int memcmp(const void *a, const void *b, size_t n) {
  const unsigned char *p = (const unsigned char *)a, *q = (const unsigned char *)b;
  while (n--) { if (*p != *q) return *p - *q; p++; q++; }
  return 0;
}

#else
typedef int deck_compat_not_needed;   /* avoid an empty translation unit */
#endif
