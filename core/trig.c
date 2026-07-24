#include "trig.h"

/* Argument reduction to [-pi/4, pi/4] plus the fdlibm kernel polynomials.
 * pi/2 is carried in two pieces so the subtraction stays accurate once k is
 * large; the screens never go far from zero, but the cost is one multiply. */
#define PIO2_HI 1.57079632679489655800e+00
#define PIO2_LO 6.12323399573676603587e-17
#define TWO_OVER_PI 6.36619772367581382433e-01

static const double S1 = -1.66666666666666324348e-01;
static const double S2 =  8.33333333332248946124e-03;
static const double S3 = -1.98412698298579493134e-04;
static const double S4 =  2.75573137070700676789e-06;
static const double S5 = -2.50507602534068634195e-08;
static const double S6 =  1.58969099521155010221e-10;

static const double C1 =  4.16666666666666019037e-02;
static const double C2 = -1.38888888888741095749e-03;
static const double C3 =  2.48015872894767294178e-05;
static const double C4 = -2.75573143513906633035e-07;
static const double C5 =  2.08757232129817482790e-09;
static const double C6 = -1.13596475577881948265e-11;

static double kernel_sin(double r) {
  double z = r * r;
  double p = S1 + z * (S2 + z * (S3 + z * (S4 + z * (S5 + z * S6))));
  return r + r * z * p;
}

static double kernel_cos(double r) {
  double z = r * r;
  double p = C1 + z * (C2 + z * (C3 + z * (C4 + z * (C5 + z * C6))));
  return 1.0 - 0.5 * z + z * z * p;
}

/* Nearest integer, ties away from zero — no libm, no fenv dependency. */
static double nearest(double x) {
  return (x >= 0.0) ? (double)(long long)(x + 0.5) : (double)(long long)(x - 0.5);
}

/* Reduce x to (quadrant, remainder). */
static void reduce(double x, int *quad, double *rem) {
  double k = nearest(x * TWO_OVER_PI);
  *rem = (x - k * PIO2_HI) - k * PIO2_LO;
  long long ki = (long long)k;
  *quad = (int)(((ki % 4) + 4) % 4);
}

double deck_sin(double x) {
  int q; double r;
  reduce(x, &q, &r);
  switch (q) {
    case 0:  return  kernel_sin(r);
    case 1:  return  kernel_cos(r);
    case 2:  return -kernel_sin(r);
    default: return -kernel_cos(r);
  }
}

double deck_cos(double x) {
  int q; double r;
  reduce(x, &q, &r);
  switch (q) {
    case 0:  return  kernel_cos(r);
    case 1:  return -kernel_sin(r);
    case 2:  return -kernel_cos(r);
    default: return  kernel_sin(r);
  }
}
