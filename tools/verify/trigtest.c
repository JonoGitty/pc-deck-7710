/* Check core/trig.c against the platform libm.
 *
 * libm is the reference for ACCURACY only — the core deliberately does not use
 * it, because three targets would give three answers. What matters is that
 * deck_sin/deck_cos are close enough that rounding to a dot position can never
 * land on a different dot. */
#include <stdio.h>
#include <math.h>
#include "../../core/trig.h"

static int sweep(const char *label, double lo, double hi, double tol) {
  double worst_s = 0, worst_c = 0, at_s = 0, at_c = 0;
  const long N = 2000000;
  for (long i = 0; i <= N; i++) {
    double x = lo + (hi - lo) * ((double)i / (double)N);
    double ds = fabs(deck_sin(x) - sin(x));
    double dc = fabs(deck_cos(x) - cos(x));
    if (ds > worst_s) { worst_s = ds; at_s = x; }
    if (dc > worst_c) { worst_c = dc; at_c = x; }
  }
  double worst = worst_s > worst_c ? worst_s : worst_c;
  printf("  %-22s sin %.2e (x=%+.4f)  cos %.2e (x=%+.4f)  %s\n",
         label, worst_s, at_s, worst_c, at_c, worst < tol ? "ok" : "FAIL");
  return worst < tol;
}

int main(void) {
  int ok = 1;
  printf("core/trig.c vs libm:\n");
  /* What the screens actually use: VU needle angles are +/-50 degrees. */
  /* 2.22e-16 is DBL_EPSILON — one ulp near 1.0 is the floor, not a defect. */
  ok &= sweep("screen range +/-1 rad", -1.0, 1.0, 3e-16);
  ok &= sweep("+/- pi", -DECK_PI, DECK_PI, 5e-16);
  ok &= sweep("+/- 20 rad", -20.0, 20.0, 2e-15);

  /* A dot position is round(centre + radius * sin). With radius <= 32, an
   * error of 2e-15 moves a coordinate by 6.4e-14 — it cannot change which dot
   * is chosen unless the true value sits that close to a .5 boundary. */
  printf("  worst-case dot shift at radius 32: %.1e dots\n", 32 * 2e-15);

  printf("  landmarks: sin(0)=%g cos(0)=%g sin(pi/2)=%.17g cos(pi)=%g\n",
         deck_sin(0.0), deck_cos(0.0), deck_sin(DECK_PI / 2), deck_cos(DECK_PI));
  return ok ? 0 : 1;
}
