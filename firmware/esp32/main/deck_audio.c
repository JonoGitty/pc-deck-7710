#include "deck_audio.h"

#include <math.h>
#include <string.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#include "deck_diag.h"
#include "trig.h"

/* Matched to legacy/server.py. The screens are the same screens, so the
 * numbers that feed them have to behave the same way or the analyser is a
 * different instrument wearing the same coat. */
#define DB_FLOOR (-58.0f)
#define DB_TILT  (1.6f)
#define RATE     44100

static const float BAND_CENTERS[DECK_BANDS] = {
    63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000};

/* --- the ring ----------------------------------------------------------- */
/* Two FFT windows deep. One would mean the analysis task racing the audio
 * callback for the same memory every single frame; four would add latency you
 * can see as the bars lagging the beat. */
#define RING_N (DECK_FFT_N * 2)
static float    s_ringL[RING_N], s_ringR[RING_N];
static volatile uint32_t s_write;          /* monotonic sample counter */
static volatile int64_t  s_last_us;
static volatile int      s_clip;

void deck_audio_feed(const uint8_t *data, uint32_t len) {
  /* Runs on the Bluedroid task. Copy and get out: any arithmetic here shows
   * up as a stutter in the music, and a music player that stutters is broken
   * no matter how good the display is. */
  const int16_t *pcm = (const int16_t *)data;
  const uint32_t frames = len / 4;                 /* 16-bit stereo */
  uint32_t w = s_write;
  int clip = 0;
  for (uint32_t i = 0; i < frames; i++) {
    const int16_t l = pcm[i * 2], r = pcm[i * 2 + 1];
    if (l >= 32700 || l <= -32700 || r >= 32700 || r <= -32700) clip = 1;
    s_ringL[w & (RING_N - 1)] = (float)l / 32768.0f;
    s_ringR[w & (RING_N - 1)] = (float)r / 32768.0f;
    w++;
  }
  s_write = w;
  if (clip) s_clip = 1;
  s_last_us = esp_timer_get_time();
}

int deck_audio_is_live(void) {
  /* Silence for a third of a second is a pause. Long enough not to trip on a
   * gap between tracks, short enough that the clock appears when it should. */
  return (esp_timer_get_time() - s_last_us) < 300000;
}

/* --- FFT ---------------------------------------------------------------- */
/* Iterative radix-2, written out rather than pulled in.
 *
 * esp-dsp would be faster and is the obvious choice, but it is a managed
 * component: adding it means the firmware cannot be built without a network
 * round trip, and this is a project people will clone onto a laptop on a
 * kitchen table. 512 points of float FFT is around 200 us on this part, which
 * against a 25 ms frame is not the thing worth optimising.
 */
static float s_re[DECK_FFT_N], s_im[DECK_FFT_N], s_win[DECK_FFT_N];
static int   s_win_ready;

static void fft(float *re, float *im, int n) {
  for (int i = 1, j = 0; i < n; i++) {
    int bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      float t = re[i]; re[i] = re[j]; re[j] = t;
      t = im[i]; im[i] = im[j]; im[j] = t;
    }
  }
  for (int len = 2; len <= n; len <<= 1) {
    const double ang = -2.0 * 3.14159265358979323846 / len;
    for (int i = 0; i < n; i += len) {
      for (int k = 0; k < len / 2; k++) {
        /* core/trig.c, not libm: the same reason the dolphins use it. The
         * renderer is verified bit-for-bit against the JS and the analysis
         * feeding it should not be the one thing that drifts per toolchain. */
        const float wr = (float)deck_cos(ang * k);
        const float wi = (float)deck_sin(ang * k);
        const int a = i + k, b = a + len / 2;
        const float xr = re[b] * wr - im[b] * wi;
        const float xi = re[b] * wi + im[b] * wr;
        re[b] = re[a] - xr; im[b] = im[a] - xi;
        re[a] += xr;        im[a] += xi;
      }
    }
  }
}

void deck_audio_init(void) {
  for (int i = 0; i < DECK_FFT_N; i++) {
    /* Hann, matching the PC deck. */
    s_win[i] = 0.5f - 0.5f * (float)deck_cos(2.0 * 3.14159265358979323846 * i /
                                             (DECK_FFT_N - 1));
  }
  s_win_ready = 1;
  s_write = 0;
  s_last_us = 0;
  deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_UNKNOWN, "no stream yet");
}

/* Which FFT bins belong to which band. Edges are geometric means of adjacent
 * centres, exactly as the PC deck computes them. */
static void band_range(int b, int *lo, int *hi) {
  const float below = (b == 0) ? BAND_CENTERS[0] * BAND_CENTERS[0] /
                                     BAND_CENTERS[1]
                               : BAND_CENTERS[b - 1];
  const float above = (b == DECK_BANDS - 1) ? BAND_CENTERS[b] * 1.35f
                                            : BAND_CENTERS[b + 1];
  const float f0 = sqrtf(below * BAND_CENTERS[b]);
  const float f1 = sqrtf(BAND_CENTERS[b] * above);
  const float hz_per_bin = (float)RATE / DECK_FFT_N;
  *lo = (int)(f0 / hz_per_bin);
  *hi = (int)(f1 / hz_per_bin);
  if (*lo < 1) *lo = 1;
  if (*hi > DECK_FFT_N / 2 - 1) *hi = DECK_FFT_N / 2 - 1;
  if (*hi < *lo) *hi = *lo;
}

void deck_audio_update(deck_state_t *v, double dt) {
  static uint32_t s_seen;
  const uint32_t w = s_write;

  if (!s_win_ready) return;

  if (w - s_seen < DECK_FFT_N / 2) {
    /* Not enough new audio for a fresh window. Decay what is on screen rather
     * than freezing it: a paused deck whose bars are still standing up looks
     * broken, and this is also what makes the idle transition feel right. */
    for (int b = 0; b < DECK_BANDS; b++) {
      v->bands[b] *= 0.86;
      v->bandsL[b] *= 0.86;
      v->bandsR[b] *= 0.86;
      v->peaks[b] -= 0.012;
      if (v->peaks[b] < 0) v->peaks[b] = 0;
    }
    v->vuL *= 0.86; v->vuR *= 0.86;
    v->rms01 *= 0.86; v->bassAvg *= 0.86; v->hfAvg *= 0.86;
    return;
  }
  s_seen = w;

  const uint32_t start = w - DECK_FFT_N;
  double sumL = 0, sumR = 0;
  for (int i = 0; i < DECK_FFT_N; i++) {
    const float l = s_ringL[(start + i) & (RING_N - 1)];
    const float r = s_ringR[(start + i) & (RING_N - 1)];
    sumL += (double)l * l;
    sumR += (double)r * r;
    s_re[i] = (l + r) * 0.5f * s_win[i];
    s_im[i] = 0.0f;
  }
  fft(s_re, s_im, DECK_FFT_N);

  /* Power reference folds in the window and length gains so a band's dB reads
   * roughly as dBFS — the same normalisation the PC deck uses. */
  double wsum = 0;
  for (int i = 0; i < DECK_FFT_N; i++) wsum += s_win[i];
  const double ref = (wsum / 2.0) * (wsum / 2.0);

  for (int b = 0; b < DECK_BANDS; b++) {
    int lo, hi;
    band_range(b, &lo, &hi);
    double p = 0;
    for (int k = lo; k <= hi; k++)
      p += (double)s_re[k] * s_re[k] + (double)s_im[k] * s_im[k];
    p = p / (hi - lo + 1) / ref + 1e-12;

    const double db = 10.0 * log10(p) + b * DB_TILT;
    double val = (db - DB_FLOOR) / (0.0 - DB_FLOOR);
    if (val < 0) val = 0;
    if (val > 1) val = 1;
    val = pow(val, 0.85);

    /* Asymmetric: jump to a transient, fall back slowly. This single line is
     * most of what makes an analyser look alive rather than like a bar chart
     * being redrawn. */
    const double a = val > v->bands[b] ? 0.55 : 0.16;
    v->bands[b] += (val - v->bands[b]) * a;
    v->peaks[b] = v->bands[b] > v->peaks[b] ? v->bands[b] : v->peaks[b] - 0.012;
    if (v->peaks[b] < 0) v->peaks[b] = 0;
    v->bandsL[b] = v->bands[b];
    v->bandsR[b] = v->bands[b];
  }

  /* Stereo split comes from channel RMS rather than a second FFT: two more
   * transforms per frame to make the mirror screen asymmetric is not a trade
   * worth making, and the eye reads the level difference anyway. */
  const double rmsL = sqrt(sumL / DECK_FFT_N), rmsR = sqrt(sumR / DECK_FFT_N);
  const double tot = rmsL + rmsR + 1e-9;
  for (int b = 0; b < DECK_BANDS; b++) {
    v->bandsL[b] = v->bands[b] * (2.0 * rmsL / tot);
    v->bandsR[b] = v->bands[b] * (2.0 * rmsR / tot);
  }

  /* VU ballistics: rise fast, fall slow, overshoot. A needle without
   * overshoot is a bar graph with a line drawn on it. */
  {
    static double nL, nR, dL, dR;
    const double tgtL = fmin(1.15, rmsL * 3.2), tgtR = fmin(1.15, rmsR * 3.2);
    const double k = fmin(1.0, dt * 24.0);
    dL += (tgtL - nL) * 0.55 * k - dL * 0.42 * k;
    dR += (tgtR - nR) * 0.55 * k - dR * 0.42 * k;
    nL += dL; nR += dR;
    if (nL < 0) { nL = 0; dL = 0; }
    if (nR < 0) { nR = 0; dR = 0; }
    v->vuL = nL; v->vuR = nR;
  }

  double lo3 = 0, hi4 = 0, all = 0;
  for (int b = 0; b < 3; b++) lo3 += v->bands[b] / 3.0;
  for (int b = 9; b < DECK_BANDS; b++) hi4 += v->bands[b] / 4.0;
  for (int b = 0; b < DECK_BANDS; b++) all += v->bands[b] / DECK_BANDS;
  v->bassAvg = lo3; v->hfAvg = hi4; v->rms01 = all;
  v->clip = s_clip;
  s_clip = 0;

  /* Scope: the newest window, decimated to the trace width, with the previous
   * two kept for the phosphor persistence the screen draws behind the live
   * one. */
  for (int t = DECK_TRACES - 1; t > 0; t--)
    memcpy(v->waveHist[t], v->waveHist[t - 1], sizeof v->waveHist[0]);
  memcpy(v->waveHist[0], v->wave, sizeof v->wave);
  v->waveHistCount = DECK_TRACES;
  for (int i = 0; i < DECK_WAVE; i++) {
    const uint32_t k = start + (uint32_t)i * DECK_FFT_N / DECK_WAVE;
    v->wave[i] = (s_ringL[k & (RING_N - 1)] + s_ringR[k & (RING_N - 1)]) * 0.5;
  }
  v->scopeGain = 2.4;

  /* Waterfall history scrolls one row per analysis, at analysis rate rather
   * than frame rate — otherwise the same spectrum is pushed several times and
   * the display crawls at whatever the render loop happens to manage. */
  for (int r = DECK_WF_ROWS - 1; r > 0; r--)
    memcpy(v->wfHist[r], v->wfHist[r - 1], sizeof v->wfHist[0]);
  for (int c = 0; c < DECK_WF_COLS; c++) {
    const double f = (double)c * (DECK_BANDS - 1) / (DECK_WF_COLS - 1);
    const int b0 = (int)f, b1 = (b0 + 1 < DECK_BANDS) ? b0 + 1 : b0;
    v->wfHist[0][c] = (float)(v->bands[b0] + (v->bands[b1] - v->bands[b0]) * (f - b0));
  }
  v->wfCount = DECK_WF_ROWS;

  deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_OK, "%d Hz, rms %.3f", RATE, all);
}
