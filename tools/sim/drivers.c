/* The three drivers that touch hardware, run on this computer.
 *
 *     sh tools/sim/drivers.sh
 *
 * WHAT THIS IS FOR
 *
 * `deck_tuner.c`, `deck_audioproc.c` and `deck_hfp.c` are the newest code in
 * this repository and, until this file existed, the least tested: "it compiles
 * for the ESP32" was the whole guarantee. They are also the three files whose
 * bugs are hardest to find on hardware, because each of them fails in a way
 * that looks like something else —
 *
 *   · a tuner command sent inside AN332's 110 ms settle window is *sometimes*
 *     ignored, so the deck works on the bench and fails one boot in five, and
 *     the symptom is "no radio", which reads as a wiring fault;
 *   · an audio processor written with two's complement tone instead of
 *     magnitude-plus-direction produces bass that is wrong only on one side of
 *     zero, which sounds like taste;
 *   · a call state machine tracked through event order instead of derived from
 *     the indicator pair breaks only on phones that send them in the other
 *     order, which is to say on somebody else's phone.
 *
 * So each scenario below drives the real driver and prints what it did to the
 * world. `test_drivers.py` asserts on that trace. The drivers are compiled
 * unmodified — see tools/sim/idf/README.md for where the line is drawn.
 *
 * ⚠️ This does not prove the firmware works on hardware and nothing here
 * claims it does. It proves the logic: command order, encodings, timing rules
 * the drivers are supposed to honour, and state derivation. The electrical
 * layer is untested and the firmware has still never run on an ESP32.
 */
#include <stdio.h>
#include <string.h>

#include "fake_hw.h"
#include "sim_stubs.h"

#include "deck_audioproc.h"
#include "deck_diag.h"
#include "deck_hfp.h"
#include "deck_tuner.h"
#include "nvs.h"

/* The shared diagnostics stub stamps its lines with this. Virtual time here,
 * so a driver's own log lines interleave with the trace in the right order. */
double sim_stub_now_ms(void) { return (double)(sim_now_us() / 1000); }

/* deck_i2s is only reached by the HFP audio callbacks, which this harness does
 * not drive — modelling SCO packet timing would be modelling the thing we
 * cannot check. Declared and stubbed so the link succeeds and so it is obvious
 * that they are deliberately out of scope. */
uint32_t deck_i2s_mic_read(uint8_t *buf, uint32_t len) {
  (void)buf;
  (void)len;
  return 0;
}
void deck_i2s_call_write(const uint8_t *buf, uint32_t len) {
  (void)buf;
  (void)len;
}

/* deck_source.c owns the 74HC4052 fallback and pulls in more of the firmware
 * than this harness needs; the audio processor only reports which source it
 * was asked for. */
const char *deck_source_name(deck_source_t s) {
  static const char *N[] = {"bt", "radio", "aux", "usb"};
  return s < 4 ? N[s] : "?";
}

/* ======================================================================
 * the tuner
 * ==================================================================== */
static void scen_tuner_bringup(void) {
  sim_scenario("tuner-bringup-addr-0x11");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();

  const int rc = deck_tuner_start();
  sim_trace("check|start|rc=%d present=%d powered=%d", rc,
            deck_tuner_present(), sim_si4735_powered());
}

static void scen_tuner_second_address(void) {
  /* Modules differ in how SEN is strapped, so the driver tries 0x11 and then
   * 0x63. The failure when it does not is silent — "no tuner" — which is why
   * this path is worth a scenario of its own. */
  sim_scenario("tuner-bringup-addr-0x63");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_63);
  deck_diag_init();

  const int rc = deck_tuner_start();
  sim_trace("check|start|rc=%d present=%d", rc, deck_tuner_present());
}

static void scen_tuner_absent(void) {
  sim_scenario("tuner-absent");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_NONE);
  deck_diag_init();

  const int rc = deck_tuner_start();
  /* Degraded, not failed: no tuner fitted is an ordinary build and the deck
   * has three other sources. Refusing to boot over an absent optional part
   * would be absurd, so the check is that it says so and carries on. */
  sim_trace("check|start|rc=%d present=%d health=%s detail=%s", rc,
            deck_tuner_present(),
            deck_diag_health_name(deck_diag_get(DECK_SUB_AUDIO)),
            deck_diag_detail(DECK_SUB_AUDIO));

  deck_radio_t r;
  deck_tuner_poll(&r);
  sim_trace("check|poll-without-tuner|freq=%d lo=%d hi=%d", r.freq_khz,
            r.band_lo_khz, r.band_hi_khz);
}

static void scen_tuner_units(void) {
  /* FM is in 10 kHz units and AM is in 1 kHz units. Getting that wrong gives a
   * tuner that is out by a factor of ten and receives nothing, which looks
   * like a dead aerial. */
  sim_scenario("tuner-frequency-units");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();

  deck_tuner_tune(98500);
  sim_trace("check|fm-tune|asked=98500 chip=%d", sim_si4735_freq_khz());

  deck_tuner_band(DECK_BAND_AM);
  deck_tuner_tune(909);
  sim_trace("check|am-tune|asked=909 chip=%d", sim_si4735_freq_khz());
}

static void scen_tuner_step_wrap(void) {
  sim_scenario("tuner-step-and-wrap");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();

  deck_tuner_tune(107900);
  deck_tuner_step(1);
  deck_tuner_step(1);
  deck_radio_t r;
  deck_tuner_poll(&r);
  /* A tuner that sticks at the top of the band feels broken; every real one
   * rolls round. Two steps from 107.9 in Europe: 108.0, then wrap to 87.5. */
  sim_trace("check|wrap-up|freq=%d lo=%d hi=%d", r.freq_khz, r.band_lo_khz,
            r.band_hi_khz);

  deck_tuner_step(0);
  deck_tuner_poll(&r);
  sim_trace("check|wrap-down|freq=%d", r.freq_khz);
}

static void scen_tuner_regions(void) {
  /* The defect this scenario exists for: a frequency saved under one band plan
   * may not exist under the next. 88.1 in Britain is below the bottom of the
   * Japanese band, and a Si4735 asked for a frequency outside its plan does
   * not fail — it sits there receiving nothing. */
  sim_scenario("tuner-region-change-clamps");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();

  for (int i = 0; i < deck_tuner_region_count(); i++)
    sim_trace("info|region|i=%d name=%s", i, deck_tuner_region_name(i));

  deck_tuner_tune(98500);
  deck_tuner_preset_store(1);
  deck_tuner_tune(88100);
  deck_tuner_preset_store(2);

  deck_radio_t r;
  deck_tuner_poll(&r);
  sim_trace("check|before|region=%s freq=%d p1=%d p2=%d",
            deck_tuner_region_name(deck_tuner_region_get()), r.freq_khz,
            r.preset_khz[0], r.preset_khz[1]);

  /* Japan: 76–95 MHz. Both presets and the current frequency are above it. */
  int jp = -1;
  for (int i = 0; i < deck_tuner_region_count(); i++)
    if (strcmp(deck_tuner_region_name(i), "JP") == 0) jp = i;
  deck_tuner_region_set(jp);

  deck_tuner_poll(&r);
  sim_trace("check|after-jp|region=%s freq=%d lo=%d hi=%d p1=%d p2=%d",
            deck_tuner_region_name(deck_tuner_region_get()), r.freq_khz,
            r.band_lo_khz, r.band_hi_khz, r.preset_khz[0], r.preset_khz[1]);

  /* The US plan is the other awkward one: a 200 kHz FM raster and 10 kHz AM
   * spacing, so the step size itself has to change with the region. */
  int us = -1;
  for (int i = 0; i < deck_tuner_region_count(); i++)
    if (strcmp(deck_tuner_region_name(i), "US") == 0) us = i;
  deck_tuner_region_set(us);
  deck_tuner_tune(88100);
  deck_tuner_step(1);
  deck_tuner_poll(&r);
  sim_trace("check|us-step|freq=%d", r.freq_khz);
}

/* The reboot pair. Two scenarios, run in order, and the second one does NOT
 * erase NVS — that is the whole point. It has to be two processes: a reboot
 * that the drivers' own file statics survive is not a reboot. */
static void scen_tuner_set_region(void) {
  sim_scenario("tuner-region-set-us");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();

  int us = -1;
  for (int i = 0; i < deck_tuner_region_count(); i++)
    if (strcmp(deck_tuner_region_name(i), "US") == 0) us = i;
  deck_tuner_region_set(us);
  deck_tuner_tune(101100);

  deck_radio_t r;
  deck_tuner_poll(&r);
  sim_trace("check|set|region=%s freq=%d",
            deck_tuner_region_name(deck_tuner_region_get()), r.freq_khz);
}

static void scen_tuner_after_reboot(void) {
  sim_scenario("tuner-region-survives-reboot");
  sim_hw_reset();                    /* the chip forgets; the flash does not */
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();

  deck_radio_t r;
  deck_tuner_poll(&r);
  sim_trace("check|after-reboot|region=%s freq=%d",
            deck_tuner_region_name(deck_tuner_region_get()), r.freq_khz);
}

static void scen_tuner_seek_readback(void) {
  /* A hardware seek moves the chip without telling the driver. If the status
   * poll does not read the frequency back, seek appears to do nothing at all
   * — the audio changes station and the display does not. */
  sim_scenario("tuner-seek-is-read-back");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();
  deck_tuner_tune(90000);

  sim_si4735_seek_lands_on(96700);
  deck_tuner_seek(1);

  deck_radio_t r;
  sim_advance_ms(150);                /* past the 100 ms status-poll interval */
  deck_tuner_poll(&r);
  sim_trace("check|seek|chip=%d driver=%d", sim_si4735_freq_khz(), r.freq_khz);
}

static void scen_tuner_rds(void) {
  /* Group 0 carries the programme service name two characters at a time. The
   * name is only published once all four pairs have arrived, because a name
   * flickering between "BB" and "BBC R2" on a dashboard is worse than a blank
   * one. Group 2A carries radio text, and 0x0D terminates it early. */
  sim_scenario("tuner-rds-assembly");
  sim_hw_reset();
  sim_nvs_erase_all();
  sim_fit_tuner(SIM_TUNER_AT_11);
  deck_diag_init();
  deck_tuner_start();

  deck_radio_t r;
  const char *pairs = "BBC R2  ";
  for (int i = 0; i < 4; i++) {
    const uint16_t b = (uint16_t)(0x0000 | i);          /* group 0A, index i */
    const uint16_t d = (uint16_t)((pairs[i * 2] << 8) | pairs[i * 2 + 1]);
    sim_si4735_rds(0xC201, b, 0x0000, d);
    sim_advance_ms(150);
    deck_tuner_poll(&r);
    sim_trace("check|rds-ps|pairs=%d name=[%s]", i + 1, r.name);
  }

  /* Radio text: group 2A, segment 0, four characters, then a 0x0D that should
   * cut it short rather than leaving the tail of a longer message behind. */
  sim_si4735_rds(0xC201, 0x2000, ('N' << 8) | 'O', ('W' << 8) | ' ');
  sim_advance_ms(150);
  deck_tuner_poll(&r);
  sim_si4735_rds(0xC201, 0x2001, ('O' << 8) | 'N', (0x0D << 8) | 'X');
  sim_advance_ms(150);
  deck_tuner_poll(&r);
  sim_trace("check|rds-text|text=[%s]", r.text);
}

/* ======================================================================
 * the audio processor
 * ==================================================================== */
static void scen_ap_absent(void) {
  sim_scenario("audioproc-absent");
  sim_hw_reset();
  sim_fit_audioproc(0);
  deck_diag_init();

  const int rc = deck_audioproc_start();
  sim_trace("check|start|rc=%d present=%d", rc, deck_audioproc_present());
  /* And the important part: asking it to do things must not crash or pretend.
   * A deck with a 74HC4052 has no volume control and that is a documented
   * build, not a fault. */
  deck_audioproc_volume(40);
  deck_audioproc_mute(1);
  sim_trace("check|no-op-when-absent|vol=%d", deck_audioproc_volume_get());
}

static void scen_ap_volume_inverted(void) {
  /* The PT2313 counts attenuation DOWN from loud: 0 is 0 dB and 63 is
   * -78.75 dB. Everything above the driver thinks in volume going up. The
   * inversion happens once, here, and this is the check that it happened. */
  sim_scenario("audioproc-volume-is-attenuation");
  sim_hw_reset();
  sim_fit_audioproc(1);
  deck_diag_init();
  deck_audioproc_start();

  deck_audioproc_volume(63);
  sim_trace("check|loudest|deck=63 get=%d", deck_audioproc_volume_get());
  deck_audioproc_volume(0);
  sim_trace("check|quietest|deck=0 get=%d", deck_audioproc_volume_get());
  deck_audioproc_volume(32);
  sim_trace("check|middle|deck=32 get=%d", deck_audioproc_volume_get());

  /* Out of range in both directions, because the encoder can be spun forever
   * and a wrapped volume is a very unpleasant surprise in a car. */
  deck_audioproc_volume(200);
  sim_trace("check|clamp-high|get=%d", deck_audioproc_volume_get());
  deck_audioproc_volume(-50);
  sim_trace("check|clamp-low|get=%d", deck_audioproc_volume_get());
}

static void scen_ap_tone_signed(void) {
  /* Magnitude-plus-direction, not two's complement. Bass -7 and +7 have the
   * same magnitude nibble and differ in one bit, so a driver that casts an int
   * gets the sign silently wrong — and wrong tone sounds like taste. */
  sim_scenario("audioproc-tone-is-magnitude-plus-direction");
  sim_hw_reset();
  sim_fit_audioproc(1);
  deck_diag_init();
  deck_audioproc_start();

  const int v[] = {7, -7, 3, -3, 0};
  for (unsigned i = 0; i < sizeof v / sizeof *v; i++) {
    sim_trace("info|asking-bass|v=%d", v[i]);
    deck_audioproc_bass(v[i]);
    sim_trace("info|asking-treble|v=%d", v[i]);
    deck_audioproc_treble(v[i]);
  }
}

static void scen_ap_balance_fader(void) {
  /* Balance and fader are not registers on this part: they are the four
   * speaker attenuators, and the driver derives them. The four channels differ
   * only in the top three bits, so a transposed pair swaps front and rear —
   * the failure the driver's own comment calls most likely on first power-up. */
  sim_scenario("audioproc-balance-and-fader");
  sim_hw_reset();
  sim_fit_audioproc(1);
  deck_diag_init();
  deck_audioproc_start();

  sim_trace("info|centred| ");
  deck_audioproc_balance(0);
  deck_audioproc_fader(0);
  sim_trace("info|hard-left| ");
  deck_audioproc_balance(-7);
  sim_trace("info|hard-right| ");
  deck_audioproc_balance(7);
  sim_trace("info|centre-then-full-front| ");
  deck_audioproc_balance(0);
  deck_audioproc_fader(-7);
  sim_trace("info|full-rear| ");
  deck_audioproc_fader(7);
}

static void scen_ap_mute(void) {
  sim_scenario("audioproc-mute-keeps-the-volume");
  sim_hw_reset();
  sim_fit_audioproc(1);
  deck_diag_init();
  deck_audioproc_start();

  deck_audioproc_volume(40);
  deck_audioproc_mute(1);
  sim_trace("check|muted|get=%d", deck_audioproc_volume_get());
  deck_audioproc_mute(0);
  sim_trace("check|unmuted|get=%d", deck_audioproc_volume_get());
}

static void scen_ap_source(void) {
  sim_scenario("audioproc-source-select");
  sim_hw_reset();
  sim_fit_audioproc(1);
  deck_diag_init();
  deck_audioproc_start();

  const deck_source_t order[] = {DECK_SRC_BT, DECK_SRC_RADIO, DECK_SRC_AUX};
  for (unsigned i = 0; i < sizeof order / sizeof *order; i++) {
    sim_trace("info|selecting|src=%s", deck_source_name(order[i]));
    deck_audioproc_source(order[i]);
  }
}

/* ======================================================================
 * hands-free calling
 * ==================================================================== */
static const char *CALL_STATE[] = {"idle", "incoming", "outgoing", "active",
                                   "ended"};

static void call_trace(const char *tag) {
  deck_call_t c;
  deck_hfp_poll(&c);
  sim_trace("check|%s|state=%s secs=%d number=[%s] busy=%d", tag,
            c.state <= DECK_CALL_ENDED ? CALL_STATE[c.state] : "?", c.secs,
            c.number, deck_hfp_busy());
}

static void scen_hfp_incoming_answered(void) {
  sim_scenario("hfp-incoming-answered-then-ended");
  sim_hw_reset();
  deck_diag_init();
  deck_hfp_start();
  sim_hfp_connect(1);
  call_trace("at-rest");

  /* The order a phone actually uses: setup goes to 1, caller ID arrives, RING
   * repeats. `call` stays 0 until it is answered. */
  sim_hfp_indicator_setup(1);
  sim_hfp_clip("+441632960123");
  sim_hfp_ring();
  call_trace("ringing");

  deck_hfp_answer();
  sim_trace("check|at-counts|answers=%d rejects=%d dials=%d",
            sim_hfp_answers(), sim_hfp_rejects(), sim_hfp_dials());

  /* The phone confirms by moving both indicators — and it does not do it
   * atomically. `call` goes to 1 while `setup` is still 1, and the deck must
   * already be ACTIVE at that instant: this is the moment a driver that waits
   * for setup to clear gets it wrong, and it is only wrong for one event, on
   * some phones, which is why it would never be found by hand. */
  sim_hfp_indicator_call(1);
  call_trace("call-set-while-setup-still-1");
  sim_hfp_indicator_setup(0);
  sim_hfp_audio(3);                          /* mSBC, so wideband */
  call_trace("answered");

  sim_advance_ms(42000);
  call_trace("42s-in");

  sim_hfp_indicator_call(0);
  call_trace("hung-up");
  sim_advance_ms(2000);
  call_trace("2s-after-end");
  sim_advance_ms(1000);                      /* ENDED_MS is 2500 */
  call_trace("3s-after-end");
}

static void scen_hfp_order_swapped(void) {
  /* The same call, with the indicators arriving in the other order — which is
   * what some phones do. A state machine tracked through event order breaks
   * here; one derived from the pair does not. This is the scenario the driver's
   * design exists for. */
  sim_scenario("hfp-indicators-in-the-other-order");
  sim_hw_reset();
  deck_diag_init();
  deck_hfp_start();
  sim_hfp_connect(1);

  /* setup goes to 1 and STAYS there while the call connects, which is what
   * some phones do — they clear it late, or in the same batch as the next
   * update. A state machine tracked through event order sees "still ringing". */
  sim_hfp_indicator_setup(1);
  call_trace("ringing");
  sim_hfp_indicator_call(1);
  call_trace("call-first");
  sim_advance_ms(1500);
  call_trace("1500ms-later-setup-still-1");
  sim_hfp_indicator_setup(0);
  call_trace("setup-cleared");
}

static void scen_hfp_outgoing(void) {
  sim_scenario("hfp-outgoing-dial-and-alert");
  sim_hw_reset();
  deck_diag_init();
  deck_hfp_start();
  sim_hfp_connect(1);

  deck_hfp_redial();
  sim_trace("check|at-counts|answers=%d rejects=%d dials=%d",
            sim_hfp_answers(), sim_hfp_rejects(), sim_hfp_dials());

  sim_hfp_indicator_setup(2);                /* dialling */
  call_trace("dialling");
  sim_hfp_indicator_setup(3);                /* remote alerting */
  call_trace("alerting");
  sim_hfp_indicator_call(1);
  sim_hfp_indicator_setup(0);
  call_trace("connected");
}

static void scen_hfp_rejected(void) {
  sim_scenario("hfp-incoming-rejected");
  sim_hw_reset();
  deck_diag_init();
  deck_hfp_start();
  sim_hfp_connect(1);

  /* Reject when nothing is happening must send nothing at all. A deck that
   * sends AT+CHUP on an idle link is a deck that hangs up somebody else's
   * call the moment it connects. */
  deck_hfp_reject();
  sim_trace("check|reject-while-idle|rejects=%d", sim_hfp_rejects());

  /* And answer when nothing is ringing, for the same reason. */
  deck_hfp_answer();
  sim_trace("check|answer-while-idle|answers=%d", sim_hfp_answers());

  sim_hfp_indicator_setup(1);
  deck_hfp_reject();
  sim_trace("check|reject-while-ringing|rejects=%d", sim_hfp_rejects());
  sim_hfp_indicator_setup(0);
  call_trace("after-reject");
}

static void scen_hfp_walks_away(void) {
  /* A phone that leaves the car mid-call sends no indicator update, because it
   * is gone. Without the disconnect handler the deck shows a call that does not
   * exist, forever, and the music never comes back. */
  sim_scenario("hfp-phone-walks-away-mid-call");
  sim_hw_reset();
  deck_diag_init();
  deck_hfp_start();
  sim_hfp_connect(1);

  sim_hfp_indicator_setup(1);
  sim_hfp_indicator_call(1);
  sim_hfp_indicator_setup(0);
  call_trace("mid-call");

  sim_hfp_disconnect();
  call_trace("phone-gone");
  sim_advance_ms(3000);
  call_trace("after-ended-timeout");
  sim_trace("check|locks|imbalance=%d", sim_sem_imbalance());
}

/* ======================================================================
 * main
 * ==================================================================== */
/* ONE SCENARIO PER PROCESS, and the order matters for exactly one pair.
 *
 * The drivers keep their state in file statics — `s_present` in the tuner,
 * `s_bus` in deck_i2c.c — and nothing in the firmware resets them, because on
 * the deck nothing needs to: a reboot does it. Running two scenarios in one
 * process therefore leaks the first into the second, and the first draft of
 * this harness cheerfully reported a working tuner in the scenario where no
 * tuner is fitted.
 *
 * Adding reset hooks to the firmware to suit the test would be testing a
 * different program. So `drivers.sh` runs this binary once per scenario. */
static const struct {
  const char *name;
  void (*fn)(void);
} SCENARIOS[] = {
    {"tuner-bringup", scen_tuner_bringup},
    {"tuner-second-address", scen_tuner_second_address},
    {"tuner-absent", scen_tuner_absent},
    {"tuner-units", scen_tuner_units},
    {"tuner-step-wrap", scen_tuner_step_wrap},
    {"tuner-regions", scen_tuner_regions},
    {"tuner-set-region", scen_tuner_set_region},
    {"tuner-after-reboot", scen_tuner_after_reboot},   /* must follow the above */
    {"tuner-seek-readback", scen_tuner_seek_readback},
    {"tuner-rds", scen_tuner_rds},
    {"ap-absent", scen_ap_absent},
    {"ap-volume", scen_ap_volume_inverted},
    {"ap-tone", scen_ap_tone_signed},
    {"ap-balance-fader", scen_ap_balance_fader},
    {"ap-mute", scen_ap_mute},
    {"ap-source", scen_ap_source},
    {"hfp-incoming", scen_hfp_incoming_answered},
    {"hfp-order-swapped", scen_hfp_order_swapped},
    {"hfp-outgoing", scen_hfp_outgoing},
    {"hfp-rejected", scen_hfp_rejected},
    {"hfp-walks-away", scen_hfp_walks_away},
};
#define N_SCENARIOS ((int)(sizeof SCENARIOS / sizeof *SCENARIOS))

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "--list") == 0) {
    for (int i = 0; i < N_SCENARIOS; i++) printf("%s\n", SCENARIOS[i].name);
    return 0;
  }
  if (argc < 2) {
    fprintf(stderr, "usage: drivers <scenario> | --list\n");
    return 2;
  }
  for (int i = 0; i < N_SCENARIOS; i++)
    if (strcmp(argv[1], SCENARIOS[i].name) == 0) {
      SCENARIOS[i].fn();
      return 0;
    }
  fprintf(stderr, "drivers: no scenario named %s\n", argv[1]);
  return 2;
}
