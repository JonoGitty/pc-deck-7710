/* The deck, running on your computer.
 *
 * This compiles the *firmware's own logic* — the UI state machine, the idle
 * rules, the audio analysis, the movie player, the output stage and every
 * screen — against stub drivers, so the whole thing runs on a laptop with no
 * ESP32, no panel and no phone.
 *
 * WHY THIS EXISTS AND WHAT IT IS NOT
 *
 * The browser preview already renders `core/`. What it does *not* run is the
 * layer above: which screen is on, when the dolphins take over, how a track
 * change interrupts, how the wipe behaves, what a movie does when it reaches
 * its last frame. That layer is firmware, it is the part most likely to be
 * wrong, and until now the only way to exercise it was to flash a board
 * nobody has.
 *
 * So the split is: anything that touches a register lives behind a stub, and
 * everything above that is the real file the ESP32 compiles. `deck_ui.c` here
 * is `deck_ui.c` there. If the idle machine is wrong on the bench it is wrong
 * here, and here it is a two-second test run instead of a reflash.
 *
 * It is NOT a simulation of the hardware. It does not model SPI timing, the
 * Bluetooth stack, DMA, or what the panel does when the supply sags. Those
 * fail on hardware and only on hardware, and pretending otherwise would make
 * this more dangerous than useful. See docs/TESTING.md for which questions
 * this answers and which it cannot.
 *
 *   sh tools/sim/run.sh                    # 20 seconds of deck, as ASCII
 *   sh tools/sim/run.sh --gif out.gif      # ...as an animation
 *   sh tools/sim/run.sh --script demo.txt  # ...driven by an event script
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "deck.h"
#include "deck_ui.h"
#include "movie.h"
#include "out.h"
#include "screens.h"
#include "sim_stubs.h"

static int W = 256, H = 64, LEVELS = 16;

static uint8_t fbpx[512 * 128];
static uint8_t dev[512 * 128];
static uint8_t moviegrid[512 * 128];

static deck_state_t state;
static deck_meta_t  meta;
static deck_ui_t    ui;

/* Synthetic music, identical in shape to tools/media/shots.c. Sharing the
 * recipe rather than the code on purpose: they are separate programs, and a
 * third file existing only to be included by two others is worse than the
 * duplication it removes. */
static double envelope(double p, double d) { return p < 0 ? 0 : exp(-p * d); }

static void synth(double t) {
  const double beat = t * 2.0;
  const double kick = envelope(fmod(beat, 1.0), 7.0);
  const double hat = envelope(fmod(beat + 0.5, 1.0), 16.0);
  const double sweep = 4.5 + 3.5 * sin(t * 0.7);
  for (int b = 0; b < DECK_BANDS; b++) {
    double v = 0.07 + 0.06 * sin(t * 1.3 + b * 0.8);
    v += kick * exp(-b * 0.80) * 0.90;
    v += hat * (b >= 9 ? 0.70 : 0.06);
    v += 0.58 * exp(-fabs(b - sweep) * 0.42);
    v += 0.26 * exp(-fabs(b - 5.5) * 0.22);
    v *= 1.0 - 0.022 * b;
    if (v > 1) v = 1;
    const double a = v > state.bands[b] ? 0.55 : 0.16;
    state.bands[b] += (v - state.bands[b]) * a;
    state.peaks[b] = state.bands[b] > state.peaks[b] ? state.bands[b]
                                                     : state.peaks[b] - 0.012;
    if (state.peaks[b] < 0) state.peaks[b] = 0;
    state.bandsL[b] = state.bands[b] * 0.95;
    state.bandsR[b] = state.bands[b] * 1.02;
  }
  double sum = 0;
  for (int b = 0; b < DECK_BANDS; b++) sum += state.bands[b] / DECK_BANDS;
  state.rms01 = sum;
  state.bassAvg = (state.bands[0] + state.bands[1] + state.bands[2]) / 3;
  state.hfAvg = state.bands[11];
  state.vuL = sum * 2.4 > 1.15 ? 1.15 : sum * 2.4;
  state.vuR = state.vuL * 0.96;
  for (int t2 = DECK_TRACES - 1; t2 > 0; t2--)
    memcpy(state.waveHist[t2], state.waveHist[t2 - 1], sizeof state.waveHist[0]);
  memcpy(state.waveHist[0], state.wave, sizeof state.wave);
  state.waveHistCount = DECK_TRACES;
  for (int i = 0; i < DECK_WAVE; i++) {
    const double u = (double)i / DECK_WAVE;
    state.wave[i] = (0.30 + 0.62 * sum) *
                    (0.62 * sin(u * 6.2831853 * 2 + t * 5) +
                     0.26 * sin(u * 6.2831853 * 5 - t * 3.1));
  }
  state.scopeGain = 2.4;
  for (int r = DECK_WF_ROWS - 1; r > 0; r--)
    memcpy(state.wfHist[r], state.wfHist[r - 1], sizeof state.wfHist[0]);
  for (int c = 0; c < DECK_WF_COLS; c++) {
    const double f = (double)c * (DECK_BANDS - 1) / (DECK_WF_COLS - 1);
    const int b0 = (int)f, b1 = b0 + 1 < DECK_BANDS ? b0 + 1 : b0;
    state.wfHist[0][c] = (float)(state.bands[b0] +
                                 (state.bands[b1] - state.bands[b0]) * (f - b0));
  }
  state.wfCount = DECK_WF_ROWS;
}

/* --- the event script --------------------------------------------------
 * Plain text so a test is a file rather than a recompile:
 *
 *   3.0  key art          press a button at t=3s
 *   8.0  track "Name" "Artist"
 *   12.0 silence          stop the music (the idle machine takes over)
 *   20.0 audio            start it again
 */
#define MAX_EV 64
static struct { double t; char cmd[16]; char a[64], b[64]; } ev[MAX_EV];
static int nev, evi;

static void load_script(const char *path) {
  FILE *f = fopen(path, "r");
  if (!f) { fprintf(stderr, "sim: cannot open %s\n", path); exit(2); }
  char line[256];
  while (nev < MAX_EV && fgets(line, sizeof line, f)) {
    if (line[0] == '#' || line[0] == '\n') continue;
    ev[nev].a[0] = ev[nev].b[0] = 0;
    /* The quoted form must match all four fields. Accepting a partial match
     * here looked harmless and silently ate the argument off every unquoted
     * line — so `key art` parsed as `key` with no argument and no button was
     * ever pressed. The behaviour tests caught it; nothing else would have. */
    if (sscanf(line, "%lf %15s \"%63[^\"]\" \"%63[^\"]\"", &ev[nev].t,
               ev[nev].cmd, ev[nev].a, ev[nev].b) == 4) nev++;
    else if (sscanf(line, "%lf %15s %63s", &ev[nev].t, ev[nev].cmd, ev[nev].a) == 3) nev++;
    else if (sscanf(line, "%lf %15s", &ev[nev].t, ev[nev].cmd) == 2) nev++;
  }
  fclose(f);
}

static int audio_live = 1;

static void run_events(double now) {
  while (evi < nev && now >= ev[evi].t) {
    const char *c = ev[evi].cmd;
    if (!strcmp(c, "key")) {
      const struct { const char *n; deck_action_t a; } K[] = {
          {"mode", DECK_ACT_MODE_NEXT}, {"art", DECK_ACT_ART},
          {"lyrics", DECK_ACT_LYRICS},  {"ocean", DECK_ACT_OCEAN},
          {"movie", DECK_ACT_MOVIE_NEXT}, {"demo", DECK_ACT_DEMO},
          {"src", DECK_ACT_SRC},        {"up", DECK_ACT_ENC_CW},
          {"down", DECK_ACT_ENC_CCW},
      };
      for (size_t i = 0; i < sizeof K / sizeof *K; i++)
        if (!strcmp(ev[evi].a, K[i].n)) deck_ui_action(&ui, K[i].a, now);
    } else if (!strcmp(c, "track")) {
      snprintf(meta.title, DECK_STR_MAX, "%s", ev[evi].a);
      snprintf(meta.artist, DECK_STR_MAX, "%s", ev[evi].b);
      meta.position = 0;
      deck_ui_track_changed(&ui, now);
    } else if (!strcmp(c, "silence")) {
      audio_live = 0;
    } else if (!strcmp(c, "audio")) {
      audio_live = 1;
    }
    printf("# %6.1fs  %s %s %s\n", ev[evi].t, c, ev[evi].a, ev[evi].b);
    evi++;
  }
}

int main(int argc, char **argv) {
  const char *gif = NULL, *script = NULL, *movie = NULL;
  double secs = 20.0;
  int fps = 20, ascii_every = 0, trace = 0;

  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--gif") && i + 1 < argc) gif = argv[++i];
    else if (!strcmp(argv[i], "--script") && i + 1 < argc) script = argv[++i];
    else if (!strcmp(argv[i], "--movie") && i + 1 < argc) movie = argv[++i];
    else if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = atof(argv[++i]);
    else if (!strcmp(argv[i], "--fps") && i + 1 < argc) fps = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--ascii") && i + 1 < argc) ascii_every = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--grid") && i + 2 < argc) {
      W = atoi(argv[++i]); H = atoi(argv[++i]);
    } else if (!strcmp(argv[i], "--levels") && i + 1 < argc) LEVELS = atoi(argv[++i]);
    /* Machine-readable, one line per frame. This is what turns the simulator
     * from something you look at into something a test can assert on — see
     * tools/sim/test_behaviour.py. */
    else if (!strcmp(argv[i], "--trace")) trace = 1;
  }
  if (script) load_script(script);

  const deck_geom_t geom = {(uint16_t)W, (uint16_t)H, DECK_LEVELS, 0};
  deck_fb_t fb = {&geom, fbpx};

  memset(&meta, 0, sizeof meta);
  snprintf(meta.app, sizeof meta.app, "BT");
  snprintf(meta.title, DECK_STR_MAX, "Downhill");
  snprintf(meta.artist, DECK_STR_MAX, "The Night Shift");
  meta.status = DECK_PLAYING;
  meta.duration = 214;

  deck_ui_init(&ui, 0);

  static deck_movie_t film;
  if (movie) {
    FILE *f = fopen(movie, "rb");
    if (f) {
      static uint8_t blob[1 << 21];
      const uint32_t n = (uint32_t)fread(blob, 1, sizeof blob, f);
      fclose(f);
      if (deck_movie_open(&film, blob, n)) {
        deck_movie_start(&ui.play, &film, moviegrid);
        ui.movie_ready = 1;
        ui.mode = 10;
        printf("# movie %s  %ux%u  %u frames\n", film.name, film.w, film.h,
               film.frameCount);
      }
    }
  }

  sim_out_begin(gif, W, H, fps);

  const double dt = 1.0 / fps;
  const int frames = (int)(secs * fps);
  double tick_acc = 0, movie_acc = 0;

  for (int f = 0; f < frames; f++) {
    const double now = f * dt;
    run_events(now);

    if (audio_live) synth(now);
    else {
      /* Decay rather than freeze, matching deck_audio.c — a paused deck whose
       * bars are still standing up is the bug this mirrors. */
      for (int b = 0; b < DECK_BANDS; b++) {
        state.bands[b] *= 0.86; state.peaks[b] -= 0.012;
        if (state.peaks[b] < 0) state.peaks[b] = 0;
      }
      state.rms01 *= 0.86; state.vuL *= 0.86; state.vuR *= 0.86;
    }

    tick_acc += dt;
    while (tick_acc >= 0.1) { tick_acc -= 0.1; ui.tick++; }

    if (ui.movie_ready && ui.mode == 10) {
      movie_acc += dt;
      const double period = 1.0 / (film.fps ? film.fps : 10);
      while (movie_acc >= period) {
        movie_acc -= period;
        if (!deck_movie_step(&ui.play)) { ui.movie_ready = 0; break; }
      }
    }

    meta.position += dt;
    deck_ui_step(&ui, audio_live, now, dt);
    deck_ui_draw(&ui, &fb, &state, &meta, now, dt);
    deck_out_frame(&fb, dev, (uint8_t)LEVELS);

    sim_out_frame(dev, fbpx, W, H);
    if (trace) {
      int lit = 0;
      for (int i = 0; i < W * H; i++) if (fbpx[i]) lit++;
      printf("T %.3f %d %d %d %d\n", now, ui.mode, (int)ui.state, lit, ui.wipe);
    }
    if (ascii_every && f % ascii_every == 0) {
      printf("\n--- t=%.1fs  mode=%d state=%d ---\n", now, ui.mode, (int)ui.state);
      sim_ascii(fbpx, W, H);
    }
  }

  sim_out_end();
  return 0;
}
