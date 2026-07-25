/* Si4735 tuner. See deck_tuner.h. NEVER RUN ON HARDWARE.
 *
 * Structure, because AN332 is 300 pages and this is not:
 *
 *   cmd()          write a command, wait for CTS
 *   getresp()      read status bytes back
 *   power_up()     into FM or AM, analogue output
 *   tune/seek      set frequency, or let the chip hunt
 *   poll()         cheap status read on a slow cadence, plus RDS
 *
 * TWO THINGS THAT ARE EASY TO GET WRONG AND EXPENSIVE TO DEBUG
 *
 * The chip is not ready when you think it is. Every command must wait for CTS
 * (clear-to-send) in the status byte before the next one, and POWER_UP takes
 * far longer than the rest — 110 ms against a few hundred microseconds. Firing
 * commands at a chip that has not finished booting produces a tuner that
 * mostly works, which is the worst kind.
 *
 * Frequency units differ per band, which is exactly the sort of detail that
 * produces a receiver stuck at the bottom of the dial. FM is in **10 kHz**
 * units (9810 = 98.1 MHz); AM is in **1 kHz** units (1053 = 1053 kHz). This
 * driver speaks kHz at its own interface and converts at the chip boundary,
 * once, in one place.
 */
#include "deck_tuner.h"

#include <string.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"

#include "deck_diag.h"
#include "deck_i2c.h"

#define PIN_SDA 32
#define PIN_SCL 33
#define PIN_RST 13
#define I2C_HZ  100000
/* 0x11 with the chip's SEN pin low, 0x63 with it high. Modules differ and
 * both are tried at start-up rather than made a build option, because the
 * failure is silent and the probe costs two milliseconds once. */
#define ADDR_A  0x11
#define ADDR_B  0x63

/* AN332 command bytes. */
#define CMD_POWER_UP        0x01
#define CMD_GET_REV         0x10
#define CMD_POWER_DOWN      0x11
#define CMD_FM_TUNE_FREQ    0x20
#define CMD_FM_SEEK_START   0x21
#define CMD_FM_TUNE_STATUS  0x22
#define CMD_FM_RSQ_STATUS   0x23
#define CMD_FM_RDS_STATUS   0x24
#define CMD_AM_TUNE_FREQ    0x40
#define CMD_AM_SEEK_START   0x41
#define CMD_AM_TUNE_STATUS  0x42
#define CMD_AM_RSQ_STATUS   0x43
#define CMD_SET_PROPERTY    0x12

#define PROP_FM_DEEMPHASIS  0x1100
#define PROP_RDS_INT_SOURCE 0x1500
#define PROP_RDS_CONFIG     0x1502
#define PROP_RX_VOLUME      0x4000

#define NVS_NS  "deck"
#define NVS_KEY "tuner"

/* Band limits in kHz, the channel step, and the de-emphasis time constant.
 *
 * THIS IS SET BY WHERE YOU DRIVE, NOT BY WHERE THE CAR CAME FROM
 *
 * Worth stating because it is the one thing people get backwards. A JDM import
 * sitting in Britain receives British stations, so it wants the European plan
 * — the fact that the car was built for Japan is irrelevant to its aerial.
 * Everything *else* about fitting a deck to an imported car follows the car's
 * market; the tuner follows the postcode. See docs/VEHICLES.md.
 *
 * Getting it wrong is not subtle:
 *
 *   · Japan's FM band is 76-95 MHz and does not overlap Europe's 87.5-108 at
 *     all below 87.5. A deck built for Europe and driven in Japan can tune
 *     roughly a tenth of the band and finds almost nothing.
 *   · The Americas use 10 kHz AM spacing against 9 kHz everywhere else. On the
 *     wrong step every station lands between channels and the whole band
 *     sounds like it is mistuned, which it is.
 *   · US FM sits on odd tenths (87.9, 88.1 ...) on a 200 kHz raster, so a
 *     100 kHz step offers 200 channels of which half are empty.
 *   · De-emphasis is 75 us in the Americas and 50 us elsewhere. Wrong, and the
 *     radio is simply dull or hissy — it still works, so nobody suspects it. */
typedef struct { int lo, hi, step; } band_t;

typedef struct {
  const char *name;
  band_t      fm, am;
  int         deemph_us;      /* 50 or 75 */
  int         rbds;           /* 1 in North America, 0 = RDS elsewhere */
} region_t;

static const region_t REGIONS[] = {
    /*  name          FM lo    hi     step     AM lo  hi   step  deemph rbds */
    {"EU",   {87500, 108000, 100}, {  522, 1710,  9}, 50, 0},
    {"UK",   {87500, 108000, 100}, {  522, 1710,  9}, 50, 0},
    {"US",   {87900, 107900, 200}, {  530, 1710, 10}, 75, 1},
    {"JP",   {76000,  95000, 100}, {  522, 1710,  9}, 50, 0},
    {"AU",   {87500, 108000, 100}, {  531, 1710,  9}, 50, 0},
};
#define N_REGIONS ((int)(sizeof REGIONS / sizeof *REGIONS))

typedef struct {
  uint8_t region;                   /* index into REGIONS; survives a reflash */
  uint8_t band;
  int     freq_khz[2];              /* last frequency per band */
  int     preset[DECK_PRESETS];
  uint8_t n_presets;
} tuner_nv_t;

static i2c_master_dev_handle_t s_dev;
static int       s_present;
static tuner_nv_t s_nv;
static int64_t   s_next_poll_us;
static uint8_t   s_rssi, s_stereo;
static char      s_ps[9];              /* RDS programme service, 8 + NUL */
static char      s_rt[65];             /* RDS radio text, 64 + NUL */
static char      s_ps_build[9];

static const region_t *region(void) {
  return &REGIONS[s_nv.region < N_REGIONS ? s_nv.region : 0];
}

static const band_t *band(void) {
  const region_t *r = region();
  return (s_nv.band & 1) == DECK_BAND_FM ? &r->fm : &r->am;
}

/* Clamp a frequency into the current region's band. Called after a region
 * change, because the frequency saved before it may not exist any more — the
 * 88.1 a car was left on in Britain is below the bottom of the Japanese band,
 * and a tuner asked for a frequency outside its plan does not fail, it simply
 * sits there receiving nothing. */
static int clamp_to_band(int khz) {
  const band_t *bd = band();
  if (khz < bd->lo) return bd->lo;
  if (khz > bd->hi) return bd->hi;
  return khz;
}

/* --- the bus ------------------------------------------------------------ */
static int wait_cts(int ms) {
  const int64_t end = esp_timer_get_time() + (int64_t)ms * 1000;
  uint8_t st = 0;
  do {
    if (i2c_master_receive(s_dev, &st, 1, 50) == ESP_OK && (st & 0x80)) return 0;
    vTaskDelay(1);
  } while (esp_timer_get_time() < end);
  return -1;
}

static int cmd(const uint8_t *buf, size_t n, int cts_ms) {
  if (!s_dev) return -1;
  if (i2c_master_transmit(s_dev, buf, n, 100) != ESP_OK) return -1;
  return wait_cts(cts_ms);
}

static int getresp(uint8_t *out, size_t n) {
  if (!s_dev) return -1;
  return i2c_master_receive(s_dev, out, n, 100) == ESP_OK ? 0 : -1;
}

static void set_prop(uint16_t prop, uint16_t val) {
  const uint8_t b[6] = {CMD_SET_PROPERTY, 0,
                        (uint8_t)(prop >> 8), (uint8_t)prop,
                        (uint8_t)(val >> 8), (uint8_t)val};
  cmd(b, sizeof b, 20);
}

/* --- bring-up ----------------------------------------------------------- */
static int power_up(deck_band_t b) {
  /* ARG1: bit6 XOSCEN (external 32 kHz crystal, which the modules all have),
   * bits 3:0 function — 0 = FM receive, 1 = AM receive.
   * ARG2: 0x05 = analogue audio out. Digital out exists and this build does
   * not use it; the audio goes to the analogue source switch, see
   * deck_source.h for why. */
  const uint8_t arg1 = (uint8_t)(0x10 | (b == DECK_BAND_FM ? 0x00 : 0x01));
  const uint8_t p[3] = {CMD_POWER_UP, arg1, 0x05};
  if (cmd(p, sizeof p, 200) != 0) return -1;
  /* AN332: POWER_UP needs 110 ms before the chip will accept anything else,
   * and CTS goes high before that is true. Waiting on CTS alone gets you a
   * tuner that works on the bench and fails one boot in five. */
  vTaskDelay(pdMS_TO_TICKS(120));

  if (b == DECK_BAND_FM) {
    /* 1 = 50 us, 2 = 75 us. Wrong and the radio still works, just dull or
     * hissy, which is why it goes unnoticed for years. */
    set_prop(PROP_FM_DEEMPHASIS, region()->deemph_us == 75 ? 2 : 1);
    set_prop(PROP_RDS_CONFIG, 0xFF01);    /* RDS on, all error levels */
    set_prop(PROP_RDS_INT_SOURCE, 0x0001);
  }
  set_prop(PROP_RX_VOLUME, 63);
  return 0;
}

static void apply_tune(int khz) {
  const band_t *bd = band();
  if (khz < bd->lo) khz = bd->lo;
  if (khz > bd->hi) khz = bd->hi;
  s_nv.freq_khz[s_nv.band & 1] = khz;

  if (s_nv.band == DECK_BAND_FM) {
    const uint16_t u = (uint16_t)(khz / 10);     /* 10 kHz units */
    const uint8_t b[5] = {CMD_FM_TUNE_FREQ, 0,
                          (uint8_t)(u >> 8), (uint8_t)u, 0};
    cmd(b, sizeof b, 100);
  } else {
    const uint16_t u = (uint16_t)khz;            /* 1 kHz units */
    const uint8_t b[6] = {CMD_AM_TUNE_FREQ, 0,
                          (uint8_t)(u >> 8), (uint8_t)u, 0, 0};
    cmd(b, sizeof b, 100);
  }
  s_ps[0] = s_rt[0] = s_ps_build[0] = 0;   /* new station, old RDS is a lie */
}

/* --- persistence -------------------------------------------------------- */
static void nv_load(void) {
  memset(&s_nv, 0, sizeof s_nv);
  s_nv.region = DECK_REGION_DEFAULT;
  s_nv.band = DECK_BAND_FM;
  s_nv.freq_khz[0] = REGIONS[s_nv.region].fm.lo;
  s_nv.freq_khz[1] = REGIONS[s_nv.region].am.lo;
  nvs_handle_t h;
  if (nvs_open(NVS_NS, NVS_READONLY, &h) != ESP_OK) return;
  size_t n = sizeof s_nv;
  nvs_get_blob(h, NVS_KEY, &s_nv, &n);
  nvs_close(h);
  if (s_nv.n_presets > DECK_PRESETS) s_nv.n_presets = DECK_PRESETS;
}

static void nv_save(void) {
  nvs_handle_t h;
  if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) return;
  nvs_set_blob(h, NVS_KEY, &s_nv, sizeof s_nv);
  nvs_commit(h);
  nvs_close(h);
}

/* --- RDS ---------------------------------------------------------------- */
/* Group 0A/0B carry the programme service name two characters at a time,
 * indexed by the bottom two bits of block B. Group 2A carries radio text four
 * characters at a time. Anything else is traffic and clock data this deck has
 * no use for.
 *
 * The name is assembled into a shadow buffer and only published when all four
 * pairs have arrived, because a half-decoded name flickering between "RA" and
 * "RADIO 1" on a dashboard is worse than a blank. */
static void rds_feed(const uint8_t *r) {
  const uint16_t b = (uint16_t)((r[6] << 8) | r[7]);
  const uint16_t c = (uint16_t)((r[8] << 8) | r[9]);
  const uint16_t d = (uint16_t)((r[10] << 8) | r[11]);
  const int group = (b >> 12) & 0xF;
  const int ver_b = (b >> 11) & 1;
  static uint8_t ps_seen;

  if (group == 0) {
    const int idx = (b & 0x3) * 2;
    s_ps_build[idx] = (char)(d >> 8);
    s_ps_build[idx + 1] = (char)(d & 0xFF);
    ps_seen |= (uint8_t)(1 << (b & 0x3));
    if (ps_seen == 0x0F) {
      s_ps_build[8] = 0;
      memcpy(s_ps, s_ps_build, sizeof s_ps);
      ps_seen = 0;
    }
  } else if (group == 2 && !ver_b) {
    const int idx = (b & 0xF) * 4;
    if (idx + 3 < (int)sizeof s_rt - 1) {
      s_rt[idx]     = (char)(c >> 8);
      s_rt[idx + 1] = (char)(c & 0xFF);
      s_rt[idx + 2] = (char)(d >> 8);
      s_rt[idx + 3] = (char)(d & 0xFF);
      /* 0x0D terminates radio text early; without honouring it the tail of
       * the previous, longer message stays on screen forever. */
      for (int i = 0; i < (int)sizeof s_rt - 1; i++) {
        if (s_rt[i] == 0x0D) { s_rt[i] = 0; break; }
        if (i == (int)sizeof s_rt - 2) s_rt[i + 1] = 0;
      }
    }
  }
}

/* --- public ------------------------------------------------------------- */
int deck_tuner_start(void) {
  nv_load();

  gpio_config_t rst = {.pin_bit_mask = 1ULL << PIN_RST, .mode = GPIO_MODE_OUTPUT};
  gpio_config(&rst);
  gpio_set_level(PIN_RST, 0);

  /* The bus is shared with the audio processor, so neither driver creates it
   * — see deck_i2c.h. This used to live here only because the tuner was the
   * first device on it. */
  if (!deck_i2c_bus()) {
    deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_DEGRADED, "no I2C for tuner");
    return -1;
  }

  /* Release reset. The chip latches its I2C address from SEN at this edge, so
   * nothing may talk to it for a moment afterwards. */
  vTaskDelay(pdMS_TO_TICKS(10));
  gpio_set_level(PIN_RST, 1);
  vTaskDelay(pdMS_TO_TICKS(10));

  const uint8_t addrs[2] = {ADDR_A, ADDR_B};
  for (int i = 0; i < 2 && !s_present; i++) {
    s_dev = deck_i2c_device(addrs[i], I2C_HZ);
    if (!s_dev) continue;
    if (power_up((deck_band_t)s_nv.band) == 0) {
      uint8_t rev[9] = {0};
      const uint8_t g[1] = {CMD_GET_REV};
      if (cmd(g, 1, 50) == 0 && getresp(rev, sizeof rev) == 0) {
        s_present = 1;
        deck_diag_event(DECK_SUB_AUDIO, "tuner", "addr=0x%02x part=Si47%02d",
                        addrs[i], rev[1]);
        break;
      }
    }
    i2c_master_bus_rm_device(s_dev);
    s_dev = NULL;
  }

  if (!s_present) {
    /* No tuner fitted is a perfectly normal build. Degraded, not failed —
     * the deck has three other sources and refusing to boot over an absent
     * optional part would be absurd. */
    deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_DEGRADED, "no tuner");
    return -1;
  }
  apply_tune(s_nv.freq_khz[s_nv.band & 1]);
  deck_diag_set(DECK_SUB_AUDIO, DECK_HEALTH_OK, "tuner ready");
  return 0;
}

int deck_tuner_present(void) { return s_present; }

int deck_tuner_region_count(void) { return N_REGIONS; }

const char *deck_tuner_region_name(int i) {
  return (i >= 0 && i < N_REGIONS) ? REGIONS[i].name : "?";
}

int deck_tuner_region_get(void) { return s_nv.region; }

void deck_tuner_region_set(int i) {
  if (i < 0 || i >= N_REGIONS || i == s_nv.region) return;
  s_nv.region = (uint8_t)i;

  /* Both saved frequencies and every preset are dragged into the new plan.
   * Skipping this leaves a deck that changed region and still shows 88.1 in
   * Japan — a frequency the chip will accept, tune to, and receive nothing
   * on, which looks like a dead aerial rather than a settings mistake. */
  for (int b = 0; b < 2; b++) {
    const band_t *bd = b == DECK_BAND_FM ? &region()->fm : &region()->am;
    if (s_nv.freq_khz[b] < bd->lo || s_nv.freq_khz[b] > bd->hi)
      s_nv.freq_khz[b] = bd->lo;
  }
  for (int p = 0; p < s_nv.n_presets; p++)
    s_nv.preset[p] = clamp_to_band(s_nv.preset[p]);

  if (s_present) {
    power_up((deck_band_t)(s_nv.band & 1));
    apply_tune(s_nv.freq_khz[s_nv.band & 1]);
  }
  nv_save();
  deck_diag_event(DECK_SUB_AUDIO, "region", "name=%s fm=%d-%d step=%d",
                  region()->name, region()->fm.lo, region()->fm.hi,
                  region()->fm.step);
}

void deck_tuner_band(deck_band_t b) {
  if (!s_present || (s_nv.band & 1) == (b & 1)) return;
  s_nv.band = (uint8_t)(b & 1);
  power_up(b);
  apply_tune(s_nv.freq_khz[s_nv.band & 1]);
  nv_save();
}

void deck_tuner_tune(int khz) {
  if (!s_present) return;
  apply_tune(khz);
  nv_save();
}

void deck_tuner_step(int up) {
  if (!s_present) return;
  const band_t *bd = band();
  int f = s_nv.freq_khz[s_nv.band & 1] + (up ? bd->step : -bd->step);
  /* Wrap rather than stop. A tuner that sticks at the end of the band feels
   * broken; every real one rolls round. */
  if (f > bd->hi) f = bd->lo;
  if (f < bd->lo) f = bd->hi;
  apply_tune(f);
  nv_save();
}

void deck_tuner_seek(int up) {
  if (!s_present) return;
  /* ARG1 bit3 SEEKUP, bit2 WRAP. The chip hunts on its own and the next
   * status poll picks up wherever it stopped, which is why this does not
   * block: a seek across a quiet band takes a second or more and freezing the
   * panel for it would look like a crash. */
  const uint8_t arg = (uint8_t)((up ? 0x08 : 0x00) | 0x04);
  if (s_nv.band == DECK_BAND_FM) {
    const uint8_t b[2] = {CMD_FM_SEEK_START, arg};
    cmd(b, sizeof b, 50);
  } else {
    const uint8_t b[6] = {CMD_AM_SEEK_START, arg, 0, 0, 0, 0};
    cmd(b, sizeof b, 50);
  }
  s_ps[0] = s_rt[0] = 0;
}

void deck_tuner_poll(deck_radio_t *r) {
  const band_t *bd = band();

  /* The screen gets an answer every frame whether or not the bus was touched;
   * everything below only refreshes what that answer is made of. */
  memset(r, 0, sizeof *r);
  r->band = (deck_band_t)(s_nv.band & 1);
  r->freq_khz = s_nv.freq_khz[s_nv.band & 1];
  r->band_lo_khz = bd->lo;
  r->band_hi_khz = bd->hi;
  r->rssi = s_rssi;
  r->stereo = s_stereo;
  r->n_presets = s_nv.n_presets;
  for (int i = 0; i < DECK_PRESETS; i++) r->preset_khz[i] = s_nv.preset[i];
  snprintf(r->name, sizeof r->name, "%s", s_ps);
  snprintf(r->text, sizeof r->text, "%s", s_rt);
  if (!s_present) return;

  /* 100 ms. A status read is about a millisecond of I2C and the numbers it
   * returns do not change faster than a person can read them; doing it every
   * frame would spend more of the deck on the bus than on the picture. */
  const int64_t now = esp_timer_get_time();
  if (now < s_next_poll_us) return;
  s_next_poll_us = now + 100000;

  uint8_t st[8] = {0};
  const uint8_t tq[2] = {s_nv.band == DECK_BAND_FM ? CMD_FM_TUNE_STATUS
                                                   : CMD_AM_TUNE_STATUS, 0x00};
  if (cmd(tq, sizeof tq, 30) == 0 && getresp(st, sizeof st) == 0) {
    const int u = (st[2] << 8) | st[3];
    const int khz = s_nv.band == DECK_BAND_FM ? u * 10 : u;
    if (khz >= bd->lo && khz <= bd->hi) {
      /* A hardware seek moves the chip without telling us, so the frequency
       * is read back rather than assumed. This is the line that makes seek
       * work at all. */
      if (khz != s_nv.freq_khz[s_nv.band & 1]) {
        s_nv.freq_khz[s_nv.band & 1] = khz;
        s_ps[0] = s_rt[0] = 0;
      }
      r->freq_khz = khz;
    }
    s_rssi = (uint8_t)(st[4] > 64 ? 255 : st[4] * 4);   /* dBuV -> 0..255 */
    s_stereo = (uint8_t)((st[3 + 0] & 0x80) ? 1 : 0);
    r->rssi = s_rssi;
  }

  if (s_nv.band == DECK_BAND_FM) {
    uint8_t rds[13] = {0};
    const uint8_t rq[2] = {CMD_FM_RDS_STATUS, 0x01};
    if (cmd(rq, sizeof rq, 30) == 0 && getresp(rds, sizeof rds) == 0) {
      if (rds[1] & 0x01) {            /* RDSRECV: a group is waiting */
        rds_feed(rds);
        snprintf(r->name, sizeof r->name, "%s", s_ps);
        snprintf(r->text, sizeof r->text, "%s", s_rt);
      }
      s_stereo = (uint8_t)((rds[3] & 0x80) ? 1 : 0);
    }
  }
  r->stereo = s_stereo;

  /* Which preset, if any, matches where we are. Recomputed rather than
   * remembered so that tuning away from a preset clears the indicator without
   * anything having to notice that it should. */
  r->preset = 0;
  for (int i = 0; i < s_nv.n_presets; i++)
    if (s_nv.preset[i] == r->freq_khz) { r->preset = i + 1; break; }
}

void deck_tuner_preset_recall(int n) {
  if (!s_present || n < 1 || n > DECK_PRESETS || n > s_nv.n_presets) return;
  apply_tune(s_nv.preset[n - 1]);
  nv_save();
}

void deck_tuner_preset_store(int n) {
  if (!s_present || n < 1 || n > DECK_PRESETS) return;
  s_nv.preset[n - 1] = s_nv.freq_khz[s_nv.band & 1];
  if (n > s_nv.n_presets) s_nv.n_presets = (uint8_t)n;
  nv_save();
  deck_diag_event(DECK_SUB_AUDIO, "preset", "n=%d khz=%d", n,
                  s_nv.preset[n - 1]);
}
