/* Steering wheel controls.
 *
 * On an S2000 the audio buttons are on the left spoke, and they are wired to a
 * 20-pin connector behind the radio. They are not, and cannot be, wired
 * straight to an aftermarket head unit: the car speaks its own resistance
 * scheme and every manufacturer's is different.
 *
 * WHAT THE AFTERMARKET ACTUALLY STANDARDISED
 *
 * Not the car side — the *radio* side. Every mainstream aftermarket head unit
 * (Pioneer, Alpine, Sony, Clarion, Kenwood, JVC) exposes one input that works
 * the same way: a **resistance to ground**, usually on a 3.5 mm jack labelled
 * "W/R" or "SWC". A button is a resistor; no button is open circuit. The
 * values differ per manufacturer and even per model, which is why the industry
 * settled on programmable interface boxes instead of a fixed table.
 *
 * So the deck implements the receiving half of that convention and nothing
 * else. A universal interface — PAC SWI-RC-1, Metra ASWC-1, Connects2, or the
 * S2000-specific InCarTec 29-629 — sits between the car and the deck, does the
 * car-specific translation it was built for, and hands over a resistance. That
 * puts the entire existing adapter ecosystem behind this deck for the price of
 * an ADC pin, and means an S2000, an E46 and a Fiesta all work without this
 * firmware knowing anything about any of them.
 *
 * WHY IT LEARNS INSTEAD OF DECODING
 *
 * There is no table to hard-code. Pioneer's own published values disagree
 * between models — one set has VOL UP at 2.1 kOhm, another at 16 kOhm — and an
 * interface box is configured for whichever radio you told it you had. Anything
 * baked in here would be right for one combination and silently wrong for the
 * rest.
 *
 * So: hold SRC for five seconds, and the deck walks you through the buttons.
 * Press each one, it records the voltage, and it stores the mapping in NVS.
 * Two minutes, once, and it works with any adapter and any car. That is also
 * the only design that can cope with the resistor tolerance in a cheap box or
 * a bad crimp adding a few hundred ohms.
 *
 * ELECTRICALLY
 *
 *   3.5 mm jack        tip ── 10k pull-up to 3V3 ──┐
 *                              │                    ADC (GPIO 34)
 *                       sleeve ┴ ground
 *
 * The adapter pulls the tip down through its resistor; the divider turns that
 * into a voltage the ADC can read. 10k puts the useful range (roughly 200 Ohm
 * to 30 kOhm) across most of the ADC's span without needing a second scale.
 *
 * A second line (the ring) exists on some adapters for a second bank of
 * buttons. It is read the same way on a second pin when fitted, and most
 * installations never need it.
 *
 * NEVER RUN ON HARDWARE.
 */
#include "deck_swc.h"

#include <string.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"

#include "deck_adc.h"
#include "deck_diag.h"

static const char *TAG = "deck.swc";

#define SWC_ADC_CHAN    ADC_CHANNEL_6      /* GPIO 34 */
#define NVS_NS          "deck"
#define NVS_KEY         "swc"

/* How close a reading has to be to a learned one to count as that button.
 * Wide enough to absorb resistor tolerance, temperature and a long cable;
 * narrow enough that adjacent buttons in a typical ladder stay distinct.
 * Adapters that pack buttons closer than this will report a clash during
 * learning rather than misfiring in traffic. */
#define MATCH_MV        90

/* A press has to be stable before it counts. Steering wheel buttons are
 * membrane switches on a long harness in an electrically filthy environment,
 * and a single ADC sample crossing a threshold is not a press. */
#define STABLE_SAMPLES  4
#define REPEAT_START_MS 600
#define REPEAT_EVERY_MS 140

static deck_swc_map_t s_map;
static int s_have_map;

/* The functions worth putting on a steering wheel, in the order the learning
 * wizard asks for them. Volume first because it is the one people reach for
 * without looking, and the one they will notice missing. */
static const struct { deck_action_t act; const char *prompt; } LEARN[] = {
    {DECK_ACT_ENC_CW,      "VOLUME UP"},
    {DECK_ACT_ENC_CCW,     "VOLUME DOWN"},
    {DECK_ACT_NEXT_TRACK,  "NEXT TRACK"},
    {DECK_ACT_PREV_TRACK,  "PREV TRACK"},
    {DECK_ACT_PLAY_PAUSE,  "PLAY / PAUSE"},
    {DECK_ACT_MODE_NEXT,   "DISPLAY / MODE"},
    {DECK_ACT_SRC,         "SOURCE"},
};
#define NLEARN ((int)(sizeof LEARN / sizeof *LEARN))

int deck_swc_learn_count(void) { return NLEARN; }
const char *deck_swc_learn_prompt(int i) {
    return (i >= 0 && i < NLEARN) ? LEARN[i].prompt : "";
}

/* --- reading ------------------------------------------------------------ */
/* Nominal millivolts on the shared ADC1 handle. Deliberately uncalibrated —
 * see deck_adc.h. The unit is shared with the front-panel button ladder
 * because the driver permits exactly one handle per ADC unit, and the second
 * caller to ask for its own would come up dead. */
static int read_mv(void) { return deck_adc1_mv(SWC_ADC_CHAN); }

int deck_swc_raw_mv(void) { return read_mv(); }

/* --- persistence -------------------------------------------------------- */
static void save(void) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) return;
    nvs_set_blob(h, NVS_KEY, &s_map, sizeof s_map);
    nvs_commit(h);
    nvs_close(h);
    deck_diag_event(DECK_SUB_INPUT, "swc", "saved=%d", s_map.count);
}

int deck_swc_start(void) {
    if (deck_adc1_channel(SWC_ADC_CHAN) != 0) {
        deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_DEGRADED, "no ADC for SWC");
        return -1;
    }

    memset(&s_map, 0, sizeof s_map);
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        size_t n = sizeof s_map;
        if (nvs_get_blob(h, NVS_KEY, &s_map, &n) == ESP_OK && n == sizeof s_map)
            s_have_map = s_map.count > 0;
        nvs_close(h);
    }

    /* Idle voltage is measured now rather than assumed. An adapter that is not
     * plugged in floats; one that is sits at the pull-up. Knowing which lets
     * the deck say "no adapter detected" instead of reporting a phantom
     * button held down forever. */
    const int idle = read_mv();
    s_map.idle_mv = idle;

    if (s_have_map) {
        deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_OK,
                      "swc: %d buttons learned", s_map.count);
    } else {
        deck_diag_set(DECK_SUB_INPUT, DECK_HEALTH_UNKNOWN,
                      "swc: not learned (hold SRC 5s)");
        ESP_LOGI(TAG, "steering wheel controls not learned yet — "
                      "hold SRC for five seconds to start");
    }
    deck_diag_event(DECK_SUB_INPUT, "swc", "idle_mv=%d learned=%d",
                    idle, s_map.count);
    return 0;
}

/* --- matching ----------------------------------------------------------- */
static deck_action_t match(int mv) {
    deck_action_t best = DECK_ACT_NONE;
    int bestd = MATCH_MV;
    for (int i = 0; i < s_map.count; i++) {
        const int d = mv > s_map.e[i].mv ? mv - s_map.e[i].mv : s_map.e[i].mv - mv;
        if (d < bestd) { bestd = d; best = (deck_action_t)s_map.e[i].action; }
    }
    return best;
}

deck_action_t deck_swc_poll(void) {
    static deck_action_t held;
    static int stable;
    static int64_t held_since, last_repeat;

    if (!s_have_map) return DECK_ACT_NONE;

    const int mv = read_mv();
    if (mv < 0) return DECK_ACT_NONE;

    /* Nothing pressed sits at the pull-up. Treated as release rather than as
     * an unmatched press, so a floating or unplugged adapter is quiet. */
    const int released = mv > s_map.idle_mv - MATCH_MV;
    const deck_action_t now = released ? DECK_ACT_NONE : match(mv);

    if (now != held) {
        if (++stable < STABLE_SAMPLES) return DECK_ACT_NONE;
        stable = 0;
        held = now;
        held_since = esp_timer_get_time();
        last_repeat = 0;
        if (now != DECK_ACT_NONE) {
            deck_diag_event(DECK_SUB_INPUT, "swc-press", "mv=%d action=%d",
                            mv, (int)now);
            return now;
        }
        return DECK_ACT_NONE;
    }
    stable = 0;

    /* Auto-repeat, but only for volume. Holding VOL UP should ramp; holding
     * NEXT TRACK should not skip the album. */
    if (held == DECK_ACT_ENC_CW || held == DECK_ACT_ENC_CCW) {
        const int64_t t = esp_timer_get_time();
        if (t - held_since > REPEAT_START_MS * 1000 &&
            t - last_repeat > REPEAT_EVERY_MS * 1000) {
            last_repeat = t;
            return held;
        }
    }
    return DECK_ACT_NONE;
}

/* --- learning ----------------------------------------------------------- */
int deck_swc_learn_step(int index, int *out_mv) {
    if (index < 0 || index >= NLEARN) return DECK_SWC_LEARN_DONE;

    /* Wait for a stable non-idle reading. Requiring several agreeing samples
     * is what stops the wizard recording the bounce at the start of a press
     * instead of the settled value it will see later at speed. */
    int last = -1, agree = 0;
    for (int i = 0; i < 400; i++) {          /* about four seconds */
        const int mv = read_mv();
        if (mv >= 0 && mv < s_map.idle_mv - MATCH_MV) {
            if (last >= 0 && (mv > last ? mv - last : last - mv) < 25) {
                if (++agree >= 6) {
                    /* Reject anything that collides with a button already
                     * learned — better to say so now than to have two wheel
                     * buttons doing the same thing on a motorway. */
                    for (int k = 0; k < s_map.count; k++) {
                        const int d = mv > s_map.e[k].mv ? mv - s_map.e[k].mv
                                                         : s_map.e[k].mv - mv;
                        if (d < MATCH_MV) {
                            *out_mv = mv;
                            return DECK_SWC_LEARN_CLASH;
                        }
                    }
                    if (s_map.count >= DECK_SWC_MAX) return DECK_SWC_LEARN_FULL;
                    s_map.e[s_map.count].mv = (int16_t)mv;
                    s_map.e[s_map.count].action = (uint8_t)LEARN[index].act;
                    s_map.count++;
                    *out_mv = mv;
                    save();
                    return DECK_SWC_LEARN_OK;
                }
            } else {
                agree = 0;
            }
            last = mv;
        } else {
            agree = 0; last = -1;
        }
        deck_delay_ms(10);
    }
    return DECK_SWC_LEARN_TIMEOUT;      /* skipped: not every wheel has it */
}

void deck_swc_learn_begin(void) {
    memset(&s_map.e, 0, sizeof s_map.e);
    s_map.count = 0;
    s_map.idle_mv = read_mv();
    s_have_map = 0;
    deck_diag_event(DECK_SUB_INPUT, "swc", "learning=1 idle_mv=%d", s_map.idle_mv);
}

void deck_swc_learn_end(void) {
    s_have_map = s_map.count > 0;
    save();
    deck_diag_set(DECK_SUB_INPUT,
                  s_have_map ? DECK_HEALTH_OK : DECK_HEALTH_UNKNOWN,
                  "swc: %d buttons learned", s_map.count);
}

int deck_swc_learned(void) { return s_have_map; }
