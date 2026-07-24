/* Deterministic sine and cosine.
 *
 * The core cannot use libm: the wasm build is -nostdlib, and even where a libm
 * exists, V8's Math.sin, glibc's sin and the ESP32's sin are three different
 * implementations that may disagree in the last bit. A screen that positions
 * dots from trig would then render subtly differently per target — the exact
 * class of bug the shared-core architecture is meant to make impossible.
 *
 * So the core carries its own, and every target gets the same pixels.
 * Accuracy is under 1e-15 absolute over the range the screens use, which is
 * far tighter than the rounding to a dot position needs.
 */
#ifndef DECK_TRIG_H
#define DECK_TRIG_H

#define DECK_PI 3.14159265358979311600

double deck_sin(double x);
double deck_cos(double x);

#endif /* DECK_TRIG_H */
