"""Where every GPIO goes — read out of the firmware, not typed in again.

THE POINT OF THIS FILE

A pin diagram is the one picture a person is holding when they have a board in
one hand and a soldering iron in the other, and it is also the picture most
likely to be quietly wrong. Pins move during development. The diagram does
not, because nobody remembers it exists.

So it is not maintained. It is *derived*: this parses `#define PIN_...` out of
the firmware sources and fails loudly if a pin it expects has gone. If someone
moves the tuner's reset line, the diagram moves with it or the build stops.
The same reason `font_rom.h` is generated and the same reason `docs/media/` is
regenerated rather than screenshotted.

What is NOT derived is the *forbidden* list — flash, PSRAM, strapping,
input-only, console. Those are facts about the ESP32-WROVER-E from its
datasheet, not facts about this firmware, so they are written down here with
the reason attached. They are also the entire reason the pin budget is tight,
and half of them cost this project a rewrite to discover.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FW = os.path.join(ROOT, "firmware", "esp32")

# Which file owns which signal. Listed explicitly rather than globbed so that a
# pin appearing in a new file is a deliberate addition to this table and not a
# silent one.
SOURCES = {
    "input":   "main/deck_input.c",
    "main":    "main/deck_main.c",
    "source":  "main/deck_source.c",
    "tuner":   "main/deck_tuner.c",
    "swc":     "main/deck_swc.c",
    "display": "components/deck_display/ssd1322.c",
}

_DEFINE = re.compile(r"^#define\s+(PIN_[A-Z0-9_]+)\s+(\d+)", re.M)


def read_defines():
    """{module: {PIN_NAME: gpio}} for every source above."""
    out = {}
    for mod, rel in SOURCES.items():
        path = os.path.join(FW, rel)
        with open(path, encoding="utf-8") as f:
            out[mod] = {m.group(1): int(m.group(2))
                        for m in _DEFINE.finditer(f.read())}
    return out


# Every GPIO the firmware claims, as (module, define, short label, group).
# The label is what goes on the diagram; the group picks the colour and says
# which subsystem it belongs to.
WANTED = [
    ("display", "PIN_MOSI",     "PANEL DIN",   "panel"),
    ("display", "PIN_SCLK",     "PANEL CLK",   "panel"),
    ("display", "PIN_CS",       "PANEL CS",    "panel"),
    ("display", "PIN_DC",       "PANEL DC",    "panel"),
    ("display", "PIN_RST",      "PANEL RST",   "panel"),
    ("main",    "PIN_I2S_BCLK", "DAC BCK",     "audio"),
    ("main",    "PIN_I2S_LRCK", "DAC LRCK",    "audio"),
    ("main",    "PIN_I2S_DOUT", "DAC DIN",     "audio"),
    ("main",    "PIN_I2S_MIC",  "MIC DATA",    "audio"),
    ("source",  "PIN_SEL_A",    "MUX A",       "mux"),
    ("source",  "PIN_SEL_B",    "MUX B",       "mux"),
    ("input",   "PIN_ENC_A",    "ENCODER A",   "control"),
    ("input",   "PIN_ENC_B",    "ENCODER B",   "control"),
    ("input",   "PIN_ENC_SW",   "ENCODER PUSH", "control"),
    ("input",   "PIN_BTN_SRC",  "SRC",         "shared"),
    ("input",   "PIN_BTN_DISP", "DISP",        "shared"),
    ("input",   "PIN_BTN_ART",  "ART",         "shared"),
    # These three land on the pins SRC/DISP/ART just took, on purpose and
    # unavoidably — see SHARED. Listed second so the button is the primary
    # label and the tuner is the alternate, which matches what the firmware
    # does: discrete buttons are what you get unless a ladder is detected.
    ("tuner",   "PIN_SDA",      "TUNER SDA",   "tuner"),
    ("tuner",   "PIN_SCL",      "TUNER SCL",   "tuner"),
    ("tuner",   "PIN_RST",      "TUNER RST",   "tuner"),
    ("input",   "PIN_IGNITION", "IGNITION",    "car"),
    ("input",   "PIN_DIMMER",   "DIMMER",      "car"),
]

# The two ADC lines are channel constants rather than pin numbers in the
# source, because that is what the driver API takes. The mapping from ADC1
# channel to GPIO is fixed silicon, so it is asserted here rather than parsed.
ADC = [
    (35, "BUTTON LADDER", "shared", "ADC1_CH7", "input/deck_input.c"),
    (34, "WHEEL CONTROLS", "car",   "ADC1_CH6", "input/deck_swc.c"),
]

# Datasheet facts about the module, not about this firmware.
FORBIDDEN = {
    6:  ("FLASH", "internal SPI flash — the chip boots off these"),
    7:  ("FLASH", "internal SPI flash"),
    8:  ("FLASH", "internal SPI flash"),
    9:  ("FLASH", "internal SPI flash"),
    10: ("FLASH", "internal SPI flash"),
    11: ("FLASH", "internal SPI flash"),
    16: ("PSRAM", "PSRAM on WROVER-E — the reason this build is a WROVER"),
    17: ("PSRAM", "PSRAM on WROVER-E"),
    1:  ("CONSOLE", "UART0 TX — the log you read when it will not boot"),
    3:  ("CONSOLE", "UART0 RX"),
}

# The three pins two subsystems both want, which the module cannot resolve and
# the firmware therefore has to. Declared here so that an *undeclared* clash
# still stops the build — the check is not being switched off, it is being told
# the one place the answer is "both, exclusively".
#
# deck_input.c probes for a button ladder before configuring anything, and its
# answer hands these three to the buttons or to the tuner. See its pin-budget
# comment, and docs/HARDWARE.md.
SHARED = {
    ("PIN_BTN_SRC",  "PIN_SCL"),
    ("PIN_BTN_DISP", "PIN_SDA"),
    ("PIN_BTN_ART",  "PIN_RST"),
}

# Strapping pins: the chip samples these at power-on to decide how to boot, so
# what matters is what they read during reset, not what they do afterwards.
# Each carries its own requirement, because they are not the same requirement —
# a blanket "output only" is wrong for GPIO 15, which this deck uses as an
# input and legitimately can.
STRAPPING = {
    0:  "strapping — must be HIGH at boot",
    2:  "strapping — LOW or floating at boot",
    12: "strapping — must be LOW at boot",
    15: "strapping — LOW here only mutes the boot log",
}

# Input-only, and with no internal pull-up. Nothing goes here as a bare switch.
INPUT_ONLY = {34, 35, 36, 37, 38, 39}

GROUPS = {
    "panel":   ("Display",        "#f3a52b"),
    "audio":   ("Audio out / mic", "#ffd978"),
    "tuner":   ("Radio",          "#7fcf8f"),
    "mux":     ("Source switch",  "#c9a0ff"),
    "control": ("Encoder",        "#d8d4cc"),
    "shared":  ("Buttons",        "#ff9d5c"),
    "car":     ("Car inputs",     "#7fb4e8"),
}


def build():
    """{gpio: dict} for every pin the firmware touches, plus the reserved ones.

    Raises if a define the diagram depends on has vanished — a missing pin is
    a diagram that has silently stopped describing the firmware, which is the
    exact failure this is here to prevent.
    """
    defs = read_defines()
    pins = {}

    for mod, name, label, group in WANTED:
        if name not in defs[mod]:
            raise SystemExit(
                f"{name} is gone from {SOURCES[mod]}.\n"
                "The pin diagram is generated from the firmware, so this is\n"
                "not a diagram problem — either restore the define or update\n"
                "WANTED in tools/diagrams/pins.py to match the new design.")
        gpio = defs[mod][name]
        if gpio in pins:
            pair = (pins[gpio]["define"], name)
            if pair not in SHARED and pair[::-1] not in SHARED:
                raise SystemExit(
                    f"GPIO {gpio} is claimed twice: {pins[gpio]['label']} "
                    f"({pins[gpio]['define']}) and {label} ({name}).\n"
                    "Two drivers configuring one pin is exactly the bug that "
                    "made the tuner\nundebuggable. If this is deliberate and "
                    "the firmware resolves it at boot,\nadd the pair to "
                    "SHARED in tools/diagrams/pins.py. Otherwise fix the "
                    "firmware.")
            # Deliberate: the second claim becomes the alternate role.
            pins[gpio]["alt"] = {"label": label, "group": group,
                                 "src": SOURCES[mod], "define": name}
            continue
        pins[gpio] = {"label": label, "group": group, "src": SOURCES[mod],
                      "define": name, "alt": None}

    for gpio, label, group, chan, src in ADC:
        pins[gpio] = {"label": label, "group": group, "src": src,
                      "define": chan}

    return pins


def describe(gpio, pins):
    """(label, colour, note) for one GPIO — used by the diagram and by the
    build-time check that the two agree."""
    if gpio in pins:
        p = pins[gpio]
        return p["label"], GROUPS[p["group"]][1], None
    if gpio in FORBIDDEN:
        kind, why = FORBIDDEN[gpio]
        return kind, "#ff4938", why
    return "", "#3a3a44", None


if __name__ == "__main__":
    pins = build()
    print(f"{len(pins)} GPIOs claimed by the firmware\n")
    for g in sorted(pins):
        p = pins[g]
        print(f"  GPIO {g:<3} {p['label']:<15} {p['define']:<14} {p['src']}")
    used = set(pins)
    free = [g for g in list(range(0, 40))
            if g not in used and g not in FORBIDDEN
            and g not in {37, 38}]          # not bonded out on the module
    print(f"\n  free: {', '.join(str(g) for g in free) or 'none'}")
