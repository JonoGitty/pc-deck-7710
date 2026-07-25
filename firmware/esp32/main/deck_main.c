/* DECK-7710 — the car deck.
 *
 * Boot order is a diagnostic decision as much as a functional one. Each stage
 * can only fail for reasons the stages before it have already ruled out, and
 * each announces itself, so a deck that stops halfway says where.
 *
 *   1  NVS and diagnostics      — so everything after can be reported
 *   2  why the last boot ended  — brownout and watchdog say a lot
 *   3  the panel, and self-test — proves the glass before proving the renderer
 *   4  movies                   — content, may legitimately be absent
 *   5  input                    — before Bluetooth, so a stuck button is
 *                                 visible while there is still a screen to
 *                                 show it on
 *   6  Bluetooth                — the radio, last of the essentials
 *   7  WiFi                     — optional; a deck without it is normal
 *   8  the render loop          — from here the deck is running
 *
 * WHY ONE RENDER LOOP AND NOT A TASK PER SCREEN. Every screen reads one
 * deck_state_t and writes one framebuffer. Concurrency would buy nothing and
 * cost a lock around the thing that runs forty times a second. The audio
 * callback is the only other writer and it only appends to a ring.
 *
 * STATUS: NEVER RUN ON HARDWARE. Read SAFETY.md before this goes in a car.
 */
#include <stdio.h>
#include <string.h>

#include "esp_attr.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "deck.h"
#include "deck_audio.h"
#include "deck_bt.h"
#include "deck_config.h"
#include "deck_diag.h"
#include "deck_display.h"
#include "deck_input.h"
#include "deck_movies.h"
#include "deck_net.h"
#include "deck_selftest.h"
#include "deck_hfp.h"
#include "deck_audioproc.h"
#include "deck_source.h"
#include "deck_swc.h"
#include "deck_tuner.h"
#include "deck_ui.h"
#include "out.h"

#define MAX_W 256
#define MAX_H 64
#define TARGET_FPS 40

/* I2S pins for the line-out DAC. Zero of the deck's function depends on these
 * being connected; a bench build with no DAC simply logs that it did not come
 * up and carries on displaying. */
#define PIN_I2S_BCLK 26
#define PIN_I2S_LRCK 25
#define PIN_I2S_DOUT 22
/* Microphone data in. Shares BCLK and LRCK with the DAC — full duplex on one
 * I2S controller, which is what makes hands-free calling fit on a chip with
 * six spare pins. GPIO 15 is a strapping pin and is safe here for a specific
 * reason: an I2S mic's data line is high-impedance until the clock starts, so
 * the internal pull-up wins at boot. A button on the same pin would be a
 * short to ground and would break the boot. See docs/CALLING.md. */
#define PIN_I2S_MIC  15

/* The three big buffers go to PSRAM. Together they are 48 KB against 320 KB of
 * internal DRAM that Bluetooth, WiFi and lwIP have first claim on — left
 * internal, the image does not link, over by about 37 KB.
 *
 * The scratch buffer is the exception and must stay internal: it is what the
 * SPI peripheral DMAs from, and on this chip DMA cannot reach external RAM.
 * That single asymmetry is the reason the blit takes a caller-owned scratch
 * rather than writing wherever it likes. */
EXT_RAM_BSS_ATTR static uint8_t s_fbpx[MAX_W * MAX_H];
EXT_RAM_BSS_ATTR static uint8_t s_dev[MAX_W * MAX_H];
EXT_RAM_BSS_ATTR static uint8_t s_moviegrid[MAX_W * MAX_H];
static uint8_t s_scratch[MAX_W * MAX_H / 4];

static deck_state_t   s_state;
static deck_meta_t    s_meta;
static deck_ui_t      s_ui;
static deck_cfg_t     s_cfg;
static deck_movies_t  s_lib;

static void load_movie(int index) {
  if (!s_lib.count) { s_ui.movie_ready = 0; return; }
  const int i = ((index % (int)s_lib.count) + (int)s_lib.count) % (int)s_lib.count;
  if (!deck_movies_open(&s_lib, i, &s_ui.film)) {
    s_ui.movie_ready = 0;
    deck_diag_set(DECK_SUB_MOVIES, DECK_HEALTH_DEGRADED, "movie %d unreadable", i);
    return;
  }
  if ((uint32_t)s_ui.film.w * s_ui.film.h > sizeof s_moviegrid) {
    s_ui.movie_ready = 0;
    deck_diag_set(DECK_SUB_MOVIES, DECK_HEALTH_DEGRADED,
                  "%s is %dx%d, too big", s_ui.film.name, s_ui.film.w, s_ui.film.h);
    return;
  }
  deck_movie_start(&s_ui.play, &s_ui.film, s_moviegrid);
  s_ui.movie_ready = 1;
  deck_diag_event(DECK_SUB_MOVIES, "load", "name=%s frames=%u",
                  s_ui.film.name, (unsigned)s_ui.film.frameCount);
}

void app_main(void) {
  /* --- 1. the basics --------------------------------------------------- */
  esp_err_t nv = nvs_flash_init();
  if (nv == ESP_ERR_NVS_NO_FREE_PAGES || nv == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    nvs_flash_erase();
    nvs_flash_init();
  }
  deck_diag_init();
  deck_diag_report();

  /* --- 2. why we are here ---------------------------------------------- */
  deck_diag_boot_reason();

  deck_cfg_load(&s_cfg);
  memset(&s_meta, 0, sizeof s_meta);
  memcpy(s_meta.app, "BT", 3);

  /* --- 3. the panel ----------------------------------------------------- */
  const deck_panel_t *panel = deck_panel();
  if (panel->init() != 0) {
    /* Nothing after this point can be seen, so say it as loudly as the only
     * remaining channel allows and keep running: the serial log and the
     * Bluetooth audio still work, and a deck that plays music with a dead
     * screen is more useful than one that halts. */
    deck_diag_set(DECK_SUB_DISPLAY, DECK_HEALTH_FAILED, "panel init failed");
    printf("\n*** THE PANEL DID NOT INITIALISE ***\n"
           "    Check: MOSI/SCLK/CS/DC/RST wiring, panel supply, and that this\n"
           "    image was built for the panel you actually have (%s).\n"
           "    Everything else will keep running; watch this log.\n\n",
           panel->name);
  } else {
    panel->brightness(s_cfg.brightness);
    deck_selftest_run(s_fbpx, s_dev, s_scratch, 2000);
  }

  /* --- 4. movies -------------------------------------------------------- */
  const int nmovies = deck_movies_mount(&s_lib);
  deck_diag_set(DECK_SUB_MOVIES,
                nmovies > 0 ? DECK_HEALTH_OK : DECK_HEALTH_UNKNOWN,
                nmovies > 0 ? "%d installed" : "none installed", nmovies);

  /* --- 5. controls ------------------------------------------------------ */
  deck_input_start();
  /* Steering wheel controls come through a universal interface box on a
   * resistive line. Started after the panel so the learning wizard has
   * somewhere to print its prompts. */
  deck_swc_start();

  /* --- 6. the radio ----------------------------------------------------- */
  deck_audio_init();
  /* The microphone rides the DAC's clocks, so it is declared before the
   * channel is built and costs nothing until a call actually arrives. */
  deck_i2s_set_mic_pin(PIN_I2S_MIC);
  if (deck_i2s_start(PIN_I2S_BCLK, PIN_I2S_LRCK, PIN_I2S_DOUT, 44100) != 0)
    deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_DEGRADED,
                  "no I2S DAC — display only");
  deck_bt_start(&s_meta, "DECK 7710");
  /* Hands-free, alongside A2DP rather than instead of it. Both are Bluetooth
   * Classic and both live on the one radio; see docs/CALLING.md. */
  deck_hfp_start();

  /* Sources, and the volume control. The audio processor is probed FIRST,
   * because if one is fitted it does the source selection too and the mux's
   * GPIOs are not wanted. Absent, deck_source falls back to the 74HC4052 and
   * the deck has no volume control at all — which is logged, because it is
   * the sort of thing to find out on a bench rather than on a slip road. */
  deck_audioproc_start();
  deck_source_start((deck_source_t)s_cfg.source);
  if (deck_audioproc_present()) deck_audioproc_volume(s_cfg.volume);
  /* A tuner is optional. Absent, this returns non-zero, logs "no tuner" and
   * the deck carries on with two sources instead of three.
   *
   * It is only *started* when a button ladder was found, because the Si4735's
   * I2C pins and its reset line are the same three GPIOs the discrete buttons
   * use — there is no fourth option on this module. Probing the bus anyway
   * would drive a pin deck_input.c has already claimed as an input, so the
   * check is a precondition rather than a preference. */
  if (deck_input_has_ladder()) {
    deck_tuner_start();
  } else {
    /* An event, not a health state: DECK_SUB_AUDIO already carries whether the
     * DAC came up, and overwriting that with a note about the radio would lose
     * the more important fact. */
    deck_diag_event(DECK_SUB_AUDIO, "tuner",
                    "skipped=1 why=discrete-buttons-hold-13/32/33");
  }

  /* --- 7. optional network ---------------------------------------------- */
  deck_net_start(s_cfg.wifi_ssid, s_cfg.wifi_pass);

  /* --- 8. run ----------------------------------------------------------- */
  deck_ui_init(&s_ui, s_cfg.mode);
  s_ui.brightness = s_cfg.brightness;
  s_ui.demo = s_cfg.demo;
  s_ui.loud = s_cfg.loud;
  load_movie(s_cfg.movie);

  const deck_geom_t geom = {(uint16_t)panel->w, (uint16_t)panel->h, DECK_LEVELS, 0};
  deck_fb_t fb = {&geom, s_fbpx};

  /* A confirmed-good image stops the bootloader treating it as suspect. Done
   * here, after the panel and the radio have come up, rather than at the top
   * of main — an image that boots and then fails to drive anything is exactly
   * the image rollback exists to escape. */
  esp_ota_mark_app_valid_cancel_rollback();

  esp_task_wdt_add(NULL);

  int64_t last_us = esp_timer_get_time();
  int64_t movie_acc_us = 0, tick_acc_us = 0, report_at = 10;
  char last_track[DECK_STR_MAX] = "";
  int  selftest_hold = 0;

  while (1) {
    const int64_t t0 = esp_timer_get_time();
    const double dt = (double)(t0 - last_us) / 1000000.0;
    last_us = t0;
    const double now = (double)t0 / 1000000.0;

    /* input */
    {
      const deck_action_t sw = deck_swc_poll();
      if (sw != DECK_ACT_NONE) deck_input_post(sw, 1);
    }
    deck_event_t ev;
    while (deck_input_get(&ev)) {
      switch (ev.action) {
      case DECK_ACT_SELFTEST:
        selftest_hold = !selftest_hold;
        break;
      case DECK_ACT_SWC_LEARN:
        deck_swc_run_wizard(s_fbpx, s_dev, s_scratch);
        break;
      case DECK_ACT_IGNITION_OFF:
        /* Whatever hold-up the supply has, spend it on the things that are
         * expensive to lose: the settings, and leaving the glass dark rather
         * than frozen on the last frame. */
        deck_cfg_save(&s_cfg);
        panel->sleep(1);
        deck_diag_event(DECK_SUB_INPUT, "shutdown", "cause=ignition");
        break;
      case DECK_ACT_IGNITION_ON:
        panel->sleep(0);
        panel->brightness(s_ui.brightness);
        break;
      /* While the phone is doing anything, the transport keys are the call
       * keys. Answering is the single most time-critical thing this deck
       * does and it must not need a different button from the one already
       * under your thumb. */
      case DECK_ACT_PLAY_PAUSE:
        if (deck_hfp_busy()) deck_hfp_answer();
        else deck_bt_send_key(0x44);                            /* PLAY */
        break;
      case DECK_ACT_NEXT_TRACK:
        if (deck_hfp_busy()) deck_hfp_reject();
        else deck_bt_send_key(0x4b);                            /* FORWARD */
        break;
      case DECK_ACT_PREV_TRACK:  deck_bt_send_key(0x4c); break; /* BACKWARD */

      case DECK_ACT_SRC: {
        if (deck_hfp_busy()) { deck_hfp_reject(); break; }
        /* Skip the tuner in the cycle when none is fitted, rather than
         * offering a silent source and letting the driver work out why. */
        deck_source_t s = deck_source_next();
        if (s == DECK_SRC_RADIO && !deck_tuner_present()) s = deck_source_next();
        s_cfg.source = (uint8_t)s;
        s_ui.source = (int)s;
        deck_cfg_mark_dirty();
        break;
      }
      default:
        deck_ui_action(&s_ui, ev.action, now);
        if (ev.action == DECK_ACT_MOVIE_NEXT) load_movie(++s_ui.movie);
        /* The encoder is the VOLUME knob. It used to change panel
         * brightness, which meant the steering wheel's VOLUME UP button —
         * labelled exactly that in deck_swc.c — dimmed the display. On a deck
         * with an audio processor fitted the knob now does what it says; with
         * only the mux there is nothing to turn, so it keeps the old
         * behaviour rather than doing nothing at all. */
        if (ev.action == DECK_ACT_ENC_CW || ev.action == DECK_ACT_ENC_CCW) {
          if (deck_audioproc_present()) {
            const int step = ev.action == DECK_ACT_ENC_CW ? 1 : -1;
            deck_audioproc_volume(deck_audioproc_volume_get() + step);
            s_cfg.volume = (uint8_t)deck_audioproc_volume_get();
            /* ⚠️ Not shown on the panel yet. core/ has no volume overlay and
             * adding one means new expectations in the differential suite —
             * a real gap, recorded rather than half-done. */
          } else {
            panel->brightness(s_ui.brightness);
            s_cfg.brightness = s_ui.brightness;
          }
        }
        s_cfg.mode = (uint8_t)s_ui.mode;
        s_cfg.demo = (uint8_t)s_ui.demo;
        deck_cfg_mark_dirty();
        break;
      }
    }

    /* metadata */
    deck_bt_position(&s_meta.position, &s_meta.duration);
    if (strcmp(last_track, s_meta.title) != 0) {
      snprintf(last_track, sizeof last_track, "%s", s_meta.title);
      if (s_meta.title[0]) {
        deck_ui_track_changed(&s_ui, now);
        if (s_cfg.lyrics_enabled)
          deck_net_want_lyrics(&s_meta, deck_lyric_rows(&geom) ? (panel->w - 8) / 6 : 30);
      }
    }

    /* the telephone, the tuner, and which of them the panel belongs to */
    deck_hfp_poll(&s_ui.call);
    s_ui.source = (int)deck_source_get();
    if (s_ui.source == DECK_SRC_RADIO) deck_tuner_poll(&s_ui.radio);

    /* A call takes the audio path off the music and gives it to the far end,
     * at the call's sample rate, and hands it back afterwards. Idempotent, so
     * this is safe to call every frame. */
    {
      static int was_call;
      const int in_call = s_ui.call.state == DECK_CALL_ACTIVE;
      if (in_call != was_call) {
        was_call = in_call;
        deck_i2s_mode(in_call, in_call ? 16000 : 44100);
        if (in_call) deck_bt_send_key(0x46);      /* PAUSE the music */
      }
    }

    /* audio */
    deck_audio_update(&s_state, dt);
    s_ui.clip = s_state.clip;

    /* the world ticks at 10 Hz whatever the frame rate — the ocean and the
     * movies are 10 fps by design and must not speed up on a fast panel */
    tick_acc_us += (int64_t)(dt * 1000000.0);
    if (tick_acc_us >= 100000) { tick_acc_us -= 100000; s_ui.tick++; }

    if (s_ui.movie_ready && s_ui.mode == 10) {
      movie_acc_us += (int64_t)(dt * 1000000.0);
      const int64_t period = 1000000 / (s_ui.film.fps ? s_ui.film.fps : 10);
      while (movie_acc_us >= period) {
        movie_acc_us -= period;
        if (!deck_movie_step(&s_ui.play)) { s_ui.movie_ready = 0; break; }
      }
    }

    deck_ui_step(&s_ui, deck_audio_is_live(), now, dt);

    /* draw */
    const int64_t t1 = esp_timer_get_time();
    if (selftest_hold) deck_selftest_status(s_fbpx, s_dev, s_scratch);
    else               deck_ui_draw(&s_ui, &fb, &s_state, &s_meta, now, dt);
    const int64_t t2 = esp_timer_get_time();

    if (!selftest_hold) {
      deck_out_frame(&fb, s_dev, panel->levels);
      panel->blit(s_dev, s_scratch);
    }
    const int64_t t3 = esp_timer_get_time();
    deck_diag_frame((uint32_t)(t2 - t1), (uint32_t)(t3 - t2));

    /* housekeeping */
    deck_cfg_flush_if_due(&s_cfg);
    if (now > report_at) {
      report_at = now + 60;
      deck_diag_heap_check();
      deck_diag_event(DECK_SUB_DISPLAY, "alive", "mode=%d state=%d heap=%u",
                      s_ui.mode, (int)s_ui.state,
                      (unsigned)esp_get_free_heap_size());
    }

    esp_task_wdt_reset();

    /* Pace the loop. Delaying by the remainder rather than a fixed tick keeps
     * the frame rate steady when a heavy screen (the 3D spectrum) costs more
     * than a light one. */
    const int64_t spent = esp_timer_get_time() - t0;
    const int64_t budget = 1000000 / TARGET_FPS;
    vTaskDelay(pdMS_TO_TICKS(spent < budget ? (uint32_t)((budget - spent) / 1000) + 1 : 1));
  }
}
