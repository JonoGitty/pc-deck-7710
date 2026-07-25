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

/* ---- atan / atan2, fdlibm kernel ---------------------------------------
 * Needed for the breach angle in the ocean scene. Same reasoning as sin/cos:
 * the result is quantised to 10 degrees, and a target whose libm rounds the
 * other side of a boundary would show the dolphin at a different attitude. */
static const double atanhi[4] = {
  4.63647609000806093515e-01, 7.85398163397448278999e-01,
  9.82793723247329054082e-01, 1.57079632679489655800e+00,
};
static const double atanlo[4] = {
  2.26987774529616870924e-17, 3.06161699786838301793e-17,
  1.39033110312309984516e-17, 6.12323399573676603587e-17,
};
static const double aT[11] = {
  3.33333333333329318027e-01, -1.99999999998764832476e-01,
  1.42857142725034663711e-01, -1.11111104054623557880e-01,
  9.09088713343650656196e-02, -7.69187620504482999495e-02,
  6.66107313738753120669e-02, -5.83357013379057348645e-02,
  4.97687799461593236017e-02, -3.65315727442169155270e-02,
  1.62858201153657823623e-02,
};

double deck_atan(double x) {
  const double ax = x < 0 ? -x : x;
  double t = ax, r;
  int id;

  if (ax < 0.4375)      { id = -1; }
  else if (ax < 0.6875) { id = 0; t = (2.0 * ax - 1.0) / (2.0 + ax); }
  else if (ax < 1.1875) { id = 1; t = (ax - 1.0) / (ax + 1.0); }
  else if (ax < 2.4375) { id = 2; t = (ax - 1.5) / (1.0 + 1.5 * ax); }
  else                  { id = 3; t = -1.0 / ax; }

  const double z = t * t, w = z * z;
  const double s1 = z * (aT[0] + w * (aT[2] + w * (aT[4] + w * (aT[6] + w * (aT[8] + w * aT[10])))));
  const double s2 = w * (aT[1] + w * (aT[3] + w * (aT[5] + w * (aT[7] + w * aT[9]))));

  if (id < 0) r = t - t * (s1 + s2);
  else        r = atanhi[id] - ((t * (s1 + s2) - atanlo[id]) - t);
  return x < 0 ? -r : r;
}

double deck_atan2(double y, double x) {
  if (x == 0.0) return y > 0 ? DECK_PI / 2 : (y < 0 ? -DECK_PI / 2 : 0.0);
  const double r = deck_atan(y / x);
  if (x > 0) return r;
  return y >= 0 ? r + DECK_PI : r - DECK_PI;
}
