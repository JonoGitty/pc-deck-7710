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
#include "deck_ui.h"
#include "out.h"

#define MAX_W 256
#define MAX_H 64
#define TARGET_FPS 40

/* I2S pins for the line-out DAC. Zero of the deck's function depends on these
 * being connected; a bench build with no DAC simply logs that it did not come
 * up and carries on displaying. */
#define PIN_I2S_BCLK 4
#define PIN_I2S_LRCK 15
#define PIN_I2S_DOUT 2

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

  /* --- 6. the radio ----------------------------------------------------- */
  deck_audio_init();
  if (deck_i2s_start(PIN_I2S_BCLK, PIN_I2S_LRCK, PIN_I2S_DOUT, 44100) != 0)
    deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_DEGRADED,
                  "no I2S DAC — display only");
  deck_bt_start(&s_meta, "DECK 7710");

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
    deck_event_t ev;
    while (deck_input_get(&ev)) {
      switch (ev.action) {
      case DECK_ACT_SELFTEST:
        selftest_hold = !selftest_hold;
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
      case DECK_ACT_PLAY_PAUSE:  deck_bt_send_key(0x44); break;  /* PLAY */
      case DECK_ACT_NEXT_TRACK:  deck_bt_send_key(0x4b); break;  /* FORWARD */
      case DECK_ACT_PREV_TRACK:  deck_bt_send_key(0x4c); break;  /* BACKWARD */
      default:
        deck_ui_action(&s_ui, ev.action, now);
        if (ev.action == DECK_ACT_MOVIE_NEXT) load_movie(++s_ui.movie);
        if (ev.action == DECK_ACT_ENC_CW || ev.action == DECK_ACT_ENC_CCW) {
          panel->brightness(s_ui.brightness);
          s_cfg.brightness = s_ui.brightness;
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
