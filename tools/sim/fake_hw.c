/* See fake_hw.h. The parts, modelled well enough to catch a driver bug.
 *
 * The two models here are written from the same documents the drivers were
 * written from — AN332 for the Si4735, the PT2313 datasheet for the audio
 * processor — and deliberately not from the drivers. A model derived from the
 * code under test agrees with it about everything, including its mistakes.
 */
#include "fake_hw.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_hf_client_api.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"

/* ======================================================================
 * the clock
 * ==================================================================== */
static int64_t s_now_us;

void sim_clock_reset(void) { s_now_us = 0; }
int64_t sim_now_us(void) { return s_now_us; }
int64_t esp_timer_get_time(void) { return s_now_us; }

void sim_advance_ms(int ms) { s_now_us += (int64_t)ms * 1000; }

void vTaskDelay(TickType_t ticks) {
  /* One tick is one millisecond here — see freertos/FreeRTOS.h. This is the
   * function that makes the whole timing story work: a driver that waits is a
   * driver whose wait is visible in the trace. */
  s_now_us += (int64_t)ticks * 1000;
}

BaseType_t xTaskCreate(void (*fn)(void *), const char *name, uint32_t stack,
                       void *arg, unsigned prio, TaskHandle_t *out) {
  /* No threads. A task that is never run is better than a task that runs at an
   * unpredictable moment: the harness drives everything explicitly, and a
   * background thread would make the trace non-deterministic and the whole
   * suite flaky. Anything that must be exercised gets called directly. */
  (void)fn; (void)stack; (void)arg; (void)prio;
  if (out) *out = NULL;
  sim_trace("task|created|name=%s not-run=1", name ? name : "?");
  return 1;
}

/* ======================================================================
 * trace
 * ==================================================================== */
void sim_trace(const char *fmt, ...) {
  printf("T|%lld|", (long long)(s_now_us / 1000));
  va_list ap;
  va_start(ap, fmt);
  vprintf(fmt, ap);
  va_end(ap);
  putchar('\n');
}

void sim_scenario(const char *name) { printf("== %s\n", name); }

/* ======================================================================
 * mutexes
 * ==================================================================== */
struct sim_sem { int held; };
static int s_imbalance;
static struct sim_sem *s_sems[8];
static int s_nsem;

SemaphoreHandle_t xSemaphoreCreateMutex(void) {
  struct sim_sem *s = calloc(1, sizeof *s);
  if (s_nsem < 8) s_sems[s_nsem++] = s;
  return s;
}

BaseType_t xSemaphoreTake(SemaphoreHandle_t s, TickType_t wait) {
  (void)wait;
  if (!s) return 0;
  if (s->held) {
    /* On hardware this is a deadlock in a Bluetooth callback: the deck stops
     * updating and looks like a crash. Recorded rather than reproduced. */
    sim_trace("mutex|reentered| ");
    s_imbalance++;
  }
  s->held++;
  return 1;
}

BaseType_t xSemaphoreGive(SemaphoreHandle_t s) {
  if (!s) return 0;
  if (!s->held) { sim_trace("mutex|given-not-held| "); s_imbalance++; }
  else s->held--;
  return 1;
}

int sim_sem_imbalance(void) {
  int n = s_imbalance;
  for (int i = 0; i < s_nsem; i++)
    if (s_sems[i] && s_sems[i]->held) n++;    /* still held at scenario end */
  return n;
}

/* ======================================================================
 * GPIO
 * ==================================================================== */
#define NPINS 40
static int s_level[NPINS];
static int s_configured[NPINS];

esp_err_t gpio_config(const gpio_config_t *cfg) {
  if (!cfg) return ESP_ERR_INVALID_ARG;
  for (int p = 0; p < NPINS; p++)
    if (cfg->pin_bit_mask & (1ULL << p)) {
      s_configured[p] = 1;
      sim_trace("gpio|config|pin=%d mode=%d", p, cfg->mode);
    }
  return ESP_OK;
}

esp_err_t gpio_set_level(gpio_num_t pin, uint32_t level) {
  if (pin < 0 || pin >= NPINS) return ESP_ERR_INVALID_ARG;
  if (!s_configured[pin])
    sim_trace("gpio|unconfigured-write|pin=%d", pin);
  s_level[pin] = (int)level;
  sim_trace("gpio|level|pin=%d v=%d", pin, (int)level);
  return ESP_OK;
}

int gpio_get_level(gpio_num_t pin) {
  return (pin >= 0 && pin < NPINS) ? s_level[pin] : 0;
}

/* ======================================================================
 * NVS — a blob store in a FILE, so it survives a reboot
 *
 * A reboot has to be a new process: the drivers keep their state in file
 * statics, and a scenario that ran after another one in the same process would
 * inherit "the tuner is already present" from it — which is how the first draft
 * of this harness reported a working tuner in the scenario where none is
 * fitted. So the harness runs one scenario per process, and the only thing that
 * is supposed to outlive a reboot lives where a reboot cannot reach it.
 *
 * Which is also the honest model. On the deck, NVS is flash.
 * ==================================================================== */
#define NVS_MAX 8
typedef struct {
  int used;
  char key[24];
  unsigned char val[256];
  size_t len;
} nvs_entry_t;
static nvs_entry_t s_nvs[NVS_MAX];
static int s_nvs_loaded;

static const char *nvs_path(void) {
  const char *p = getenv("SIM_NVS");
  return p ? p : "build/sim_nvs.bin";
}

static void nvs_load_file(void) {
  if (s_nvs_loaded) return;
  s_nvs_loaded = 1;
  FILE *f = fopen(nvs_path(), "rb");
  if (!f) return;
  if (fread(s_nvs, sizeof s_nvs, 1, f) != 1) memset(s_nvs, 0, sizeof s_nvs);
  fclose(f);
}

static void nvs_save_file(void) {
  FILE *f = fopen(nvs_path(), "wb");
  if (!f) return;
  fwrite(s_nvs, sizeof s_nvs, 1, f);
  fclose(f);
}

void sim_nvs_erase_all(void) {
  memset(s_nvs, 0, sizeof s_nvs);
  s_nvs_loaded = 1;
  remove(nvs_path());
}

esp_err_t nvs_open(const char *ns, nvs_open_mode_t mode, nvs_handle_t *out) {
  (void)ns; (void)mode;
  nvs_load_file();
  if (out) *out = 1;
  return ESP_OK;
}

static nvs_entry_t *find(const char *key, int create) {
  for (int i = 0; i < NVS_MAX; i++)
    if (s_nvs[i].used && strcmp(s_nvs[i].key, key) == 0) return &s_nvs[i];
  if (!create) return NULL;
  for (int i = 0; i < NVS_MAX; i++)
    if (!s_nvs[i].used) {
      s_nvs[i].used = 1;
      snprintf(s_nvs[i].key, sizeof s_nvs[i].key, "%s", key);
      return &s_nvs[i];
    }
  return NULL;
}

esp_err_t nvs_get_blob(nvs_handle_t h, const char *key, void *out,
                       size_t *len) {
  (void)h;
  nvs_entry_t *e = find(key, 0);
  if (!e) return ESP_ERR_NOT_FOUND;
  size_t n = e->len < *len ? e->len : *len;
  if (out) memcpy(out, e->val, n);
  *len = n;
  return ESP_OK;
}

esp_err_t nvs_set_blob(nvs_handle_t h, const char *key, const void *v,
                       size_t n) {
  (void)h;
  nvs_entry_t *e = find(key, 1);
  if (!e || n > sizeof e->val) return ESP_FAIL;
  memcpy(e->val, v, n);
  e->len = n;
  sim_trace("nvs|write|key=%s bytes=%zu", key, n);
  return ESP_OK;
}

esp_err_t nvs_get_u8(nvs_handle_t h, const char *key, uint8_t *out) {
  size_t n = 1;
  return nvs_get_blob(h, key, out, &n);
}
esp_err_t nvs_set_u8(nvs_handle_t h, const char *key, uint8_t v) {
  return nvs_set_blob(h, key, &v, 1);
}
esp_err_t nvs_commit(nvs_handle_t h) {
  (void)h;
  nvs_save_file();
  return ESP_OK;
}
void nvs_close(nvs_handle_t h) { (void)h; }

/* ======================================================================
 * the Si4735, per AN332
 * ==================================================================== */
#define CMD_POWER_UP       0x01
#define CMD_GET_REV        0x10
#define CMD_POWER_DOWN     0x11
#define CMD_SET_PROPERTY   0x12
#define CMD_FM_TUNE_FREQ   0x20
#define CMD_FM_SEEK_START  0x21
#define CMD_FM_TUNE_STATUS 0x22
#define CMD_FM_RSQ_STATUS  0x23
#define CMD_FM_RDS_STATUS  0x24
#define CMD_AM_TUNE_FREQ   0x40
#define CMD_AM_SEEK_START  0x41
#define CMD_AM_TUNE_STATUS 0x42
#define CMD_AM_RSQ_STATUS  0x43

/* AN332: the chip needs 110 ms after POWER_UP before it will accept another
 * command, and CTS goes high before that is true. The model enforces it. */
#define POWER_UP_SETTLE_MS 110

typedef struct {
  int      present;
  uint8_t  addr;
  int      powered;
  int      am;                 /* 0 = FM, 1 = AM */
  int      freq_khz;
  int      seek_target_khz;
  int      rssi, stereo;
  int64_t  power_up_at_us;
  int      pending;            /* which command is awaiting a response read */
  uint16_t rds[4];
  int      rds_ready;
} si_t;
static si_t s_si;

static void si_reply_len(si_t *s, uint8_t *buf, size_t n);

void sim_si4735_seek_lands_on(int khz) { s_si.seek_target_khz = khz; }
void sim_si4735_signal(int rssi, int stereo) {
  s_si.rssi = rssi;
  s_si.stereo = stereo;
}
void sim_si4735_rds(uint16_t a, uint16_t b, uint16_t c, uint16_t d) {
  s_si.rds[0] = a; s_si.rds[1] = b; s_si.rds[2] = c; s_si.rds[3] = d;
  s_si.rds_ready = 1;
}
int sim_si4735_freq_khz(void) { return s_si.freq_khz; }
int sim_si4735_powered(void) { return s_si.powered; }

static void si_write(si_t *s, const uint8_t *b, size_t n) {
  const uint8_t c = b[0];

  /* The rule that matters. A command inside the settle window is one the real
   * chip may simply ignore, so it is reported rather than obeyed — and the
   * driver's own trace then shows a tune that never happened. */
  if (s->powered && c != CMD_POWER_UP &&
      s_now_us - s->power_up_at_us < (int64_t)POWER_UP_SETTLE_MS * 1000)
    sim_trace("si4735|too-soon|cmd=0x%02x since_power_up_ms=%lld", c,
              (long long)((s_now_us - s->power_up_at_us) / 1000));

  switch (c) {
  case CMD_POWER_UP:
    s->powered = 1;
    s->am = (b[1] & 0x0F) == 1;
    s->power_up_at_us = s_now_us;
    sim_trace("si4735|power_up|arg1=0x%02x arg2=0x%02x band=%s xosc=%d",
              b[1], n > 2 ? b[2] : 0, s->am ? "AM" : "FM", (b[1] >> 4) & 1);
    break;

  case CMD_POWER_DOWN:
    s->powered = 0;
    sim_trace("si4735|power_down| ");
    break;

  case CMD_SET_PROPERTY: {
    const uint16_t prop = (uint16_t)((b[2] << 8) | b[3]);
    const uint16_t val = (uint16_t)((b[4] << 8) | b[5]);
    sim_trace("si4735|property|prop=0x%04x val=0x%04x", prop, val);
    break;
  }

  case CMD_FM_TUNE_FREQ: {
    const int u = (b[2] << 8) | b[3];
    s->freq_khz = u * 10;                       /* 10 kHz units on FM */
    sim_trace("si4735|tune|band=FM units=%d khz=%d", u, s->freq_khz);
    break;
  }

  case CMD_AM_TUNE_FREQ: {
    const int u = (b[2] << 8) | b[3];
    s->freq_khz = u;                            /* 1 kHz units on AM */
    sim_trace("si4735|tune|band=AM units=%d khz=%d", u, s->freq_khz);
    break;
  }

  case CMD_FM_SEEK_START:
  case CMD_AM_SEEK_START:
    /* The chip hunts on its own. Landing somewhere the driver did not ask for
     * is the entire point: it has to read the frequency back. */
    sim_trace("si4735|seek|up=%d wrap=%d", (b[1] >> 3) & 1, (b[1] >> 2) & 1);
    if (s->seek_target_khz) s->freq_khz = s->seek_target_khz;
    break;

  case CMD_GET_REV:
  case CMD_FM_TUNE_STATUS:
  case CMD_AM_TUNE_STATUS:
  case CMD_FM_RSQ_STATUS:
  case CMD_AM_RSQ_STATUS:
  case CMD_FM_RDS_STATUS:
    break;

  default:
    sim_trace("si4735|unknown-cmd|cmd=0x%02x", c);
    break;
  }
  s->pending = c;
}

/* A read is either the status byte the driver polls for CTS, or the response
 * payload for the last command — the real part distinguishes them by length,
 * and so does this. */
static void si_reply_len(si_t *s, uint8_t *buf, size_t n) {
  memset(buf, 0, n);
  buf[0] = 0x80;                                  /* CTS, no error */
  if (n == 1) return;

  switch (s->pending) {
  case CMD_GET_REV:
    buf[1] = 35;                                  /* part number: Si4735 */
    buf[2] = '2'; buf[3] = '0';
    break;

  case CMD_FM_TUNE_STATUS:
  case CMD_AM_TUNE_STATUS: {
    buf[1] = 0x01;                                /* valid */
    const int u = s->am ? s->freq_khz : s->freq_khz / 10;
    buf[2] = (uint8_t)(u >> 8);
    buf[3] = (uint8_t)u;
    buf[4] = (uint8_t)s->rssi;
    if (s->stereo) buf[1] |= 0x80;
    break;
  }

  case CMD_FM_RSQ_STATUS:
  case CMD_AM_RSQ_STATUS:
    buf[2] = (uint8_t)(s->stereo ? 0x80 : 0);
    buf[4] = (uint8_t)s->rssi;
    break;

  case CMD_FM_RDS_STATUS:
    if (s->rds_ready && n >= 13) {
      buf[1] = 0x01;                              /* RDS sync, group ready */
      buf[2] = 1;                                 /* one group waiting */
      for (int i = 0; i < 4; i++) {
        buf[4 + i * 2] = (uint8_t)(s->rds[i] >> 8);
        buf[5 + i * 2] = (uint8_t)(s->rds[i] & 0xFF);
      }
      s->rds_ready = 0;
    }
    break;

  default:
    break;
  }
}

/* ======================================================================
 * the PT2313
 * ==================================================================== */
typedef struct {
  int present;
  int vol_atten;                 /* as written: 0 = 0 dB, 63 = -78.75 dB */
  int bass, treble;              /* decoded back to signed steps */
  int atten[4];                  /* LR, RR, LF, RF — as written */
  int loudness, input, gain;
} pt_t;
static pt_t s_pt;

static const char *PT_SPK[4] = {"left-rear", "right-rear",
                                "left-front", "right-front"};

/* Decode magnitude-plus-direction back to a signed value. The driver has to
 * encode it; doing the inverse here means a driver that wrote two's complement
 * would produce a nonsense number in the trace rather than a plausible one. */
static int pt_tone(uint8_t low) {
  const int mag = low & 0x07;
  const int up = (low & 0x08) != 0;
  return up ? mag : -mag;
}

static void pt_write(pt_t *p, uint8_t b) {
  if ((b & 0xC0) == 0x00) {
    p->vol_atten = b & 0x3F;
    sim_trace("pt2313|volume|atten_steps=%d db=%.2f", p->vol_atten,
              -1.25 * p->vol_atten);
  } else if ((b & 0xE0) == 0x40) {
    p->loudness = !((b >> 2) & 1);          /* active low on this part */
    p->gain = (b >> 3) & 0x03;
    p->input = b & 0x03;
    sim_trace("pt2313|switch|input=%d gain=%d loudness=%d", p->input, p->gain,
              p->loudness);
  } else if ((b & 0xF0) == 0x60) {
    p->bass = pt_tone(b & 0x0F);
    sim_trace("pt2313|bass|steps=%d raw=0x%02x", p->bass, b);
  } else if ((b & 0xF0) == 0x70) {
    p->treble = pt_tone(b & 0x0F);
    sim_trace("pt2313|treble|steps=%d raw=0x%02x", p->treble, b);
  } else {
    const int ch = (b >> 5) & 0x03;         /* 100,101,110,111 → 0..3 */
    p->atten[ch] = b & 0x1F;
    sim_trace("pt2313|speaker|ch=%s atten_steps=%d%s", PT_SPK[ch],
              p->atten[ch], p->atten[ch] == 0x1F ? " muted=1" : "");
  }
}

/* ======================================================================
 * the bus
 * ==================================================================== */
struct sim_i2c_bus { int up; };
struct sim_i2c_dev { uint8_t addr; uint32_t hz; int open; };

static struct sim_i2c_bus s_bus;
static struct sim_i2c_dev s_devs[8];
static int s_ndev;

void sim_fit_tuner(sim_tuner_fit_t where) {
  s_si.present = where != SIM_TUNER_NONE;
  s_si.addr = where == SIM_TUNER_AT_63 ? 0x63 : 0x11;
  s_si.rssi = 40;
  s_si.stereo = 1;
}

void sim_fit_audioproc(int fitted) { s_pt.present = fitted; }

void sim_hw_reset(void) {
  const sim_tuner_fit_t fit = s_si.present
      ? (s_si.addr == 0x63 ? SIM_TUNER_AT_63 : SIM_TUNER_AT_11)
      : SIM_TUNER_NONE;
  const int pt = s_pt.present;
  memset(&s_si, 0, sizeof s_si);
  memset(&s_pt, 0, sizeof s_pt);
  memset(&s_bus, 0, sizeof s_bus);
  memset(s_devs, 0, sizeof s_devs);
  memset(s_level, 0, sizeof s_level);
  memset(s_configured, 0, sizeof s_configured);
  s_ndev = 0;
  s_imbalance = 0;
  s_nsem = 0;
  sim_fit_tuner(fit);
  sim_fit_audioproc(pt);
  sim_clock_reset();
}

esp_err_t i2c_new_master_bus(const i2c_master_bus_config_t *cfg,
                             i2c_master_bus_handle_t *out) {
  if (!cfg || !out) return ESP_ERR_INVALID_ARG;
  s_bus.up = 1;
  *out = &s_bus;
  sim_trace("i2c|bus|sda=%d scl=%d", cfg->sda_io_num, cfg->scl_io_num);
  return ESP_OK;
}

esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t bus,
                                    const i2c_device_config_t *cfg,
                                    i2c_master_dev_handle_t *out) {
  if (!bus || !bus->up || !cfg || !out) return ESP_ERR_INVALID_ARG;
  for (int i = 0; i < s_ndev; i++)
    if (s_devs[i].open && s_devs[i].addr == cfg->device_address) {
      /* The real driver refuses a duplicate address, and deck_i2c.h documents
       * that as the reason the tuner probe has to remove a device before
       * trying the other address. */
      sim_trace("i2c|add-dup|addr=0x%02x", cfg->device_address);
      return ESP_FAIL;
    }
  if (s_ndev >= 8) return ESP_FAIL;
  struct sim_i2c_dev *d = &s_devs[s_ndev++];
  d->addr = (uint8_t)cfg->device_address;
  d->hz = cfg->scl_speed_hz;
  d->open = 1;
  *out = d;
  sim_trace("i2c|add|addr=0x%02x hz=%u", d->addr, (unsigned)d->hz);
  return ESP_OK;
}

esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t dev) {
  if (!dev) return ESP_ERR_INVALID_ARG;
  dev->open = 0;
  sim_trace("i2c|rm|addr=0x%02x", dev->addr);
  return ESP_OK;
}

esp_err_t i2c_master_probe(i2c_master_bus_handle_t bus, uint16_t addr, int to) {
  (void)to;
  if (!bus || !bus->up) return ESP_FAIL;
  const int here = (s_si.present && addr == s_si.addr) ||
                   (s_pt.present && addr == 0x44);
  return here ? ESP_OK : ESP_FAIL;
}

/* NAK if nothing is at the address. This is what makes an absent part absent
 * rather than a part that silently accepts everything — and "no tuner fitted
 * is a normal build" is only testable because of it. */
static int answers(uint8_t addr) {
  if (s_si.present && addr == s_si.addr) return 1;
  if (s_pt.present && addr == 0x44) return 1;
  return 0;
}

esp_err_t i2c_master_transmit(i2c_master_dev_handle_t dev, const uint8_t *buf,
                              size_t n, int timeout_ms) {
  (void)timeout_ms;
  if (!dev || !dev->open || !buf || !n) return ESP_ERR_INVALID_ARG;
  if (!answers(dev->addr)) return ESP_FAIL;

  if (dev->addr == 0x44) {
    for (size_t i = 0; i < n; i++) pt_write(&s_pt, buf[i]);
  } else {
    si_write(&s_si, buf, n);
  }
  return ESP_OK;
}

esp_err_t i2c_master_receive(i2c_master_dev_handle_t dev, uint8_t *buf,
                             size_t n, int timeout_ms) {
  (void)timeout_ms;
  if (!dev || !dev->open || !buf || !n) return ESP_ERR_INVALID_ARG;
  if (!answers(dev->addr)) return ESP_FAIL;
  if (dev->addr == 0x44) { memset(buf, 0, n); return ESP_OK; }
  si_reply_len(&s_si, buf, n);
  return ESP_OK;
}

esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t dev,
                                      const uint8_t *tx, size_t txn,
                                      uint8_t *rx, size_t rxn,
                                      int timeout_ms) {
  esp_err_t e = i2c_master_transmit(dev, tx, txn, timeout_ms);
  if (e != ESP_OK) return e;
  return i2c_master_receive(dev, rx, rxn, timeout_ms);
}

/* ======================================================================
 * the HFP audio gateway — a scripted phone
 * ==================================================================== */
static esp_hf_client_cb_t s_hf_cb;
static esp_hf_client_incoming_data_cb_t s_hf_in;
static esp_hf_client_outgoing_data_cb_t s_hf_out;
static int s_answers, s_rejects, s_dials;

esp_err_t esp_hf_client_register_callback(esp_hf_client_cb_t cb) {
  s_hf_cb = cb;
  return ESP_OK;
}
esp_err_t esp_hf_client_init(void) {
  sim_trace("hfp|init| ");
  return ESP_OK;
}
void esp_hf_client_register_data_callback(esp_hf_client_incoming_data_cb_t in,
                                          esp_hf_client_outgoing_data_cb_t out) {
  s_hf_in = in;
  s_hf_out = out;
}
esp_err_t esp_hf_client_answer_call(void) {
  s_answers++;
  sim_trace("hfp|at|cmd=ATA");
  return ESP_OK;
}
esp_err_t esp_hf_client_reject_call(void) {
  s_rejects++;
  sim_trace("hfp|at|cmd=AT+CHUP");
  return ESP_OK;
}
esp_err_t esp_hf_client_dial(const char *number) {
  s_dials++;
  sim_trace("hfp|at|cmd=ATD%s", number ? number : "L");
  return ESP_OK;
}

int sim_hfp_answers(void) { return s_answers; }
int sim_hfp_rejects(void) { return s_rejects; }
int sim_hfp_dials(void) { return s_dials; }

static void hf_send(esp_hf_client_cb_event_t ev,
                    esp_hf_client_cb_param_t *p) {
  if (s_hf_cb) s_hf_cb(ev, p);
}

void sim_hfp_connect(int slc) {
  esp_hf_client_cb_param_t p = {0};
  p.conn_stat.state = slc ? ESP_HF_CLIENT_CONNECTION_STATE_SLC_CONNECTED
                          : ESP_HF_CLIENT_CONNECTION_STATE_CONNECTED;
  hf_send(ESP_HF_CLIENT_CONNECTION_STATE_EVT, &p);
}

void sim_hfp_disconnect(void) {
  esp_hf_client_cb_param_t p = {0};
  p.conn_stat.state = ESP_HF_CLIENT_CONNECTION_STATE_DISCONNECTED;
  hf_send(ESP_HF_CLIENT_CONNECTION_STATE_EVT, &p);
}

void sim_hfp_indicator_call(int v) {
  esp_hf_client_cb_param_t p = {0};
  p.call.status = (esp_hf_call_status_t)v;
  sim_trace("phone|cind|call=%d", v);
  hf_send(ESP_HF_CLIENT_CIND_CALL_EVT, &p);
}

void sim_hfp_indicator_setup(int v) {
  esp_hf_client_cb_param_t p = {0};
  p.call_setup.status = (esp_hf_call_setup_status_t)v;
  sim_trace("phone|cind|setup=%d", v);
  hf_send(ESP_HF_CLIENT_CIND_CALL_SETUP_EVT, &p);
}

void sim_hfp_clip(const char *number) {
  esp_hf_client_cb_param_t p = {0};
  p.clip.number = number;
  hf_send(ESP_HF_CLIENT_CLIP_EVT, &p);
}

void sim_hfp_ring(void) {
  esp_hf_client_cb_param_t p = {0};
  hf_send(ESP_HF_CLIENT_RING_IND_EVT, &p);
}

void sim_hfp_audio(int state) {
  esp_hf_client_cb_param_t p = {0};
  p.audio_stat.state = (esp_hf_client_audio_state_t)state;
  hf_send(ESP_HF_CLIENT_AUDIO_STATE_EVT, &p);
}
