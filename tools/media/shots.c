/* Render every display mode to frames, for the README and the site.
 *
 * The point of this tool is that the pictures are not mockups. It links the
 * same `core/` the firmware links and the same one the browser preview compiles
 * to WASM, so what comes out is the renderer, not a drawing of it. If a screen
 * regresses, the previews regress with it.
 *
 * What it does add is the music. There is no audio here, so the analysis state
 * the screens read is synthesised: a 120 bpm loop with a kick, a hat, a bass
 * line and a slow filter sweep, run through the same kind of smoothing the
 * server applies to real FFT output. It is fake, but it is fake in the shape
 * real input has — which is what makes a spectrum analyser look like a spectrum
 * analyser rather than a random bar chart.
 *
 * Built and driven by tools/media/make.sh; see there for the exact command.
 *   build/mkshots <outdir> [W H]
 *
 * Writes <outdir>/<mode>.raw, each: "DSHT", u16 w, u16 h, u16 frames, then
 * frames*w*h bytes of intensity 0..4. tools/media/shots.py turns those into
 * animated GIFs that look like the panel.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../core/deck.h"
#include "../../core/screens.h"
#include "../../core/art.h"
#include "../../core/text.h"

#define FPS    20
#define FRAMES 60                 /* 3 s, and it loops */

static int W = 192, H = 48;

/* ------------------------------------------------------------------ music */
/* 120 bpm: two beats a second, so a beat every FPS/2 frames. The loop length
 * is a whole number of bars at that tempo, which is what lets the GIF cycle
 * without a visible seam. */
#define BEAT_FRAMES (FPS / 2)

static double envelope(double phase, double decay) {
  return phase < 0.0 ? 0.0 : exp(-phase * decay);
}

/* Band centre frequencies are logarithmic, so band index maps to "how bassy".
 * The kick lives in 0..2, the bass line in 1..4, the hat in 9..12. */
static void synth_bands(double t, double *out) {
  const double beat = t * 2.0;                       /* beats elapsed */
  const double kick = envelope(fmod(beat, 1.0), 7.0);
  const double hat  = envelope(fmod(beat + 0.5, 1.0), 16.0) * (fmod(beat, 2.0) < 1.0 ? 0.6 : 1.0);
  const double snare = fmod(beat, 4.0) >= 1.0 && fmod(beat, 2.0) >= 1.0
                     ? envelope(fmod(beat - 1.0, 2.0), 9.0) : 0.0;
  /* A filter sweep over the loop, so the mid bands are not static. */
  const double sweep = 4.5 + 3.5 * sin(t * 0.7);

  for (int b = 0; b < DECK_BANDS; b++) {
    double v = 0.07 + 0.06 * sin(t * 1.3 + b * 0.8);
    v += kick  * exp(-b * 0.80) * 0.90;
    v += snare * exp(-fabs(b - 5.0) * 0.45) * 0.55;
    v += hat   * (b >= 9 ? 0.70 : 0.06);
    v += 0.58 * exp(-fabs(b - sweep) * 0.42);        /* the sweep itself */
    /* Broadband body. Without it the analyser is a kick at one end and a hat
     * at the other with a hole in the middle, which is what a drum machine
     * looks like, not a record. */
    v += 0.26 * exp(-fabs(b - 5.5) * 0.22) * (0.62 + 0.38 * sin(t * 2.2 + b));
    /* Real spectra tilt down with frequency; without this the top of the
     * analyser sits as high as the bottom and it reads as a bar chart. */
    v *= 1.0 - 0.022 * b;
    out[b] = v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v);
  }
}

static double synth_wave(double t, int i, double amp) {
  const double u = (double)i / DECK_WAVE;
  return amp * (0.62 * sin(u * 6.2831853 * 2.0 + t * 5.0) +
                0.26 * sin(u * 6.2831853 * 5.0 - t * 3.1) +
                0.12 * sin(u * 6.2831853 * 11.0 + t * 8.7));
}

/* ------------------------------------------------------------------- art */
/* A sleeve, invented. Something with a big shape and a hard edge, because that
 * is what survives being dithered to four levels at 48 dots square — a
 * photograph of a band standing in a field does not. */
static void synth_sleeve(uint8_t *lum, int s) {
  for (int y = 0; y < s; y++) {
    for (int x = 0; x < s; x++) {
      const double u = (x + 0.5) / s - 0.5, w = (y + 0.5) / s - 0.5;
      const double r = sqrt(u * u + w * w);
      double v = 0.20 + 0.30 * (0.5 - w);                  /* vertical gradient */
      if (r < 0.31) v = 0.92 - 0.5 * (u * 0.7 + w);        /* the disc */
      else if (r < 0.345) v = 0.06;                        /* a ring of black */
      if (w > 0.30) v = 0.10;                              /* a band at the foot */
      const double band = u * 1.4 + w;
      if (band > 0.16 && band < 0.24 && r > 0.35) v = 0.85; /* a diagonal slash */
      v += 0.035 * sin(x * 2.1) * cos(y * 1.7);            /* a little grain */
      lum[y * s + x] = (uint8_t)(v < 0 ? 0 : (v > 1 ? 255 : v * 255.0));
    }
  }
}

/* ------------------------------------------------------------------ output */
static void write_raw(const char *dir, const char *name,
                      const uint8_t *frames, int nf) {
  char path[512];
  snprintf(path, sizeof path, "%s/%s.raw", dir, name);
  FILE *f = fopen(path, "wb");
  if (!f) { perror(path); exit(1); }
  fwrite("DSHT", 1, 4, f);
  uint16_t hdr[3] = { (uint16_t)W, (uint16_t)H, (uint16_t)nf };
  fwrite(hdr, sizeof(uint16_t), 3, f);
  fwrite(frames, 1, (size_t)nf * W * H, f);
  fclose(f);
  printf("  %-10s %d frames  %dx%d\n", name, nf, W, H);
}

static const char *LYRICS[] = {
  "Nothing but the rain",
  "and the tail lights bleeding out ahead",
  "I know this road by heart",
  "every corner, every camber",
  "",
  "Hold it sideways, let it run",
};
static const double LYRIC_T[] = { 0.0, 3.0, 7.5, 10.5, 14.0, 17.0 };

int main(int argc, char **argv) {
  const char *dir = argc > 1 ? argv[1] : "build/shots";
  if (argc > 3) { W = atoi(argv[2]); H = atoi(argv[3]); }

  static uint8_t px[512 * 128];
  static uint8_t buf[FRAMES * 512 * 128];
  if ((size_t)W * H > sizeof px) { fprintf(stderr, "grid too large\n"); return 1; }

  const deck_geom_t geom = { (uint16_t)W, (uint16_t)H, DECK_LEVELS, 0 };
  deck_fb_t fb = { &geom, px };
  static deck_state_t v;
  static deck_meta_t m;

  static uint8_t lum[64 * 64], art[64 * 64];
  const int S = H >= 56 ? 64 : 48;
  synth_sleeve(lum, S);
  deck_art_dither(lum, S, art);

  memset(&m, 0, sizeof m);
  /* The same invented track the faceplate screenshots use, so the two sets of
   * pictures are of one deck playing one thing rather than of two demos. */
  deck_fold("Downhill", m.title, sizeof m.title);
  deck_fold("The Night Shift", m.artist, sizeof m.artist);
  deck_fold("Touge Sessions", m.album, sizeof m.album);
  deck_fold("Spotify", m.app, sizeof m.app);
  m.status = DECK_PLAYING;
  m.duration = 214.0;
  m.art = art;
  m.artSide = S;
  m.lyricState = DECK_LYR_OK;
  m.synced = 1;
  deck_lyrics_reset(&m);
  for (size_t i = 0; i < sizeof LYRICS / sizeof *LYRICS; i++)
    deck_lyrics_add(&m, LYRIC_T[i], LYRICS[i], (W - 8) / 6);

  /* Screens that carry state between frames need warming up, or the first
   * frames of every GIF are a screen booting rather than a screen running. */
  const int WARM = 40;

  const char *modes[] = { "spectrum", "mirror", "vu", "scope", "city",
                          "waterfall", "3d", "ocean", "cover", "lyrics" };

  for (size_t mi = 0; mi < sizeof modes / sizeof *modes; mi++) {
    const char *mode = modes[mi];
    memset(&v, 0, sizeof v);
    deck_screen_city_reset();
    static deck_ocean_t ocean;
    deck_ocean_reset(&ocean);
    deck_scroll_t scroll;
    memset(&scroll, 0, sizeof scroll);

    for (int f = -WARM; f < FRAMES; f++) {
      const double t = (double)f / FPS;

      /* --- advance the analysis state, the way the server would ---------- */
      double raw[DECK_BANDS];
      synth_bands(t, raw);
      for (int b = 0; b < DECK_BANDS; b++) {
        /* asymmetric smoothing: bars jump to a transient and fall back slowly,
         * which is the single thing that makes an analyser look alive */
        const double a = raw[b] > v.bands[b] ? 0.55 : 0.16;
        v.bands[b] += (raw[b] - v.bands[b]) * a;
        v.peaks[b] = v.bands[b] > v.peaks[b] ? v.bands[b]
                                             : v.peaks[b] - 0.012;
        if (v.peaks[b] < 0) v.peaks[b] = 0;
        /* a little stereo spread, so the mirror screen is not symmetrical */
        v.bandsL[b] = v.bands[b] * (0.86 + 0.14 * sin(t * 1.1 + b * 0.6));
        v.bandsR[b] = v.bands[b] * (0.86 + 0.14 * sin(t * 1.1 + b * 0.6 + 2.1));
      }

      double lo = 0.0, hi = 0.0, sum = 0.0;
      for (int b = 0; b < 3; b++)  lo += v.bands[b] / 3.0;
      for (int b = 9; b < DECK_BANDS; b++) hi += v.bands[b] / 4.0;
      for (int b = 0; b < DECK_BANDS; b++) sum += v.bands[b] / DECK_BANDS;
      v.bassAvg = lo; v.hfAvg = hi; v.rms01 = sum;

      /* VU ballistics. Needles are not a level readout: they rise fast, fall
       * slowly and overshoot, and a needle without overshoot looks like a bar
       * graph someone drew a line on. The two channels are given slightly
       * different targets so the pair is never mirror-symmetrical, which is
       * the other thing that gives a fake VU away. */
      {
        static double nL, nR, dL, dR;
        if (f == -WARM) { nL = nR = dL = dR = 0.0; }
        const double tgtL = sum * (0.94 + 0.10 * sin(t * 0.9));
        const double tgtR = sum * (0.94 + 0.10 * sin(t * 0.9 + 1.7));
        dL += (tgtL - nL) * 0.55 - dL * 0.42;    /* spring, lightly damped */
        dR += (tgtR - nR) * 0.55 - dR * 0.42;
        nL += dL; nR += dR;
        v.vuL = nL < 0 ? 0 : (nL > 1.15 ? 1.15 : nL);
        v.vuR = nR < 0 ? 0 : (nR > 1.15 ? 1.15 : nR);
      }

      const double amp = 0.30 + 0.62 * sum;
      for (int t2 = DECK_TRACES - 1; t2 > 0; t2--)
        memcpy(v.waveHist[t2], v.waveHist[t2 - 1], sizeof v.waveHist[0]);
      memcpy(v.waveHist[0], v.wave, sizeof v.wave);
      v.waveHistCount = DECK_TRACES;
      for (int i = 0; i < DECK_WAVE; i++) v.wave[i] = synth_wave(t, i, amp);
      v.scopeGain = 2.4;
      v.clip = 0;

      /* waterfall scrolls one row per frame at the deck's own rate */
      for (int r = DECK_WF_ROWS - 1; r > 0; r--)
        memcpy(v.wfHist[r], v.wfHist[r - 1], sizeof v.wfHist[0]);
      for (int c = 0; c < DECK_WF_COLS; c++) {
        const double b = (double)c * (DECK_BANDS - 1) / (DECK_WF_COLS - 1);
        const int b0 = (int)b;
        const int b1 = b0 + 1 < DECK_BANDS ? b0 + 1 : b0;
        v.wfHist[0][c] = (float)(v.bands[b0] + (v.bands[b1] - v.bands[b0]) * (b - b0));
      }
      v.wfCount = DECK_WF_ROWS;

      /* The two metadata screens run their own clock faster than real time.
       * Three seconds of a lyrics screen is one lyric line and a progress bar
       * that does not visibly move — a truthful preview of nothing. The audio
       * strip along the bottom keeps real time, so the part of the frame that
       * is about the music still moves at the rate the music does. */
      const double mrate = (!strcmp(mode, "lyrics") || !strcmp(mode, "cover"))
                         ? 5.0 : 1.0;
      m.position = 74.0 + t * mrate;

      /* --- draw ---------------------------------------------------------- */
      deck_clear(&fb);
      if      (!strcmp(mode, "spectrum"))  deck_screen_spectrum(&fb, &v);
      else if (!strcmp(mode, "mirror"))    deck_screen_mirror(&fb, &v);
      else if (!strcmp(mode, "vu"))        deck_screen_vu(&fb, &v);
      else if (!strcmp(mode, "scope"))     deck_screen_scope(&fb, &v);
      else if (!strcmp(mode, "city"))      deck_screen_city(&fb, &v);
      else if (!strcmp(mode, "waterfall")) deck_screen_waterfall(&fb, &v);
      else if (!strcmp(mode, "3d"))        deck_screen_3d(&fb, &v);
      else if (!strcmp(mode, "ocean"))
        /* the ocean steps on ticks, not frames: it runs at 10 fps however
         * often it is asked to draw, which is what keeps it period-correct */
        deck_screen_ocean(&fb, &v, &ocean, (uint32_t)((f + WARM) * 10 / FPS));
      else if (!strcmp(mode, "cover"))
        deck_screen_cover(&fb, &v, &m, &scroll, mrate * 1000.0 / FPS);
      else if (!strcmp(mode, "lyrics"))
        deck_screen_lyrics(&fb, &v, &m, (9.6 + t * mrate) * 1000.0);

      if (f >= 0) memcpy(buf + (size_t)f * W * H, px, (size_t)W * H);
    }
    write_raw(dir, mode, buf, FRAMES);
  }
  return 0;
}
