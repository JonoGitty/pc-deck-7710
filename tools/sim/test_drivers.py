#!/usr/bin/env python3
"""Assert on what the three hardware drivers did.

    sh tools/sim/drivers.sh --check          (this, with the trace built first)
    python3 tools/sim/test_drivers.py build/drivers.txt

Every check below names the failure it exists to catch, because a test whose
name is "test_volume_2" tells the next person nothing about whether it is safe
to delete. The three drivers under test — `deck_tuner.c`, `deck_audioproc.c`,
`deck_hfp.c` — have never run on hardware, and each fails in a way that looks
like something else, which is what makes asserting on their logic worth the
harness underneath it.

The trace format is one line per event:

    T|<ms>|<what>|<detail>|k=v k=v      from the harness and the part models
    # DECK|<ms>|<sub>|<event>|k=v       from the firmware's own diagnostics
    == <scenario>                       a scenario boundary

⚠️ Passing here does not mean the firmware works. It means the drivers' command
order, encodings, timing rules and state derivation are right. The electrical
layer is not modelled and cannot be.
"""
import re
import sys

fails = []
checks = 0


def check(name, ok, detail=""):
    global checks
    checks += 1
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<62} {'' if ok else detail}")
    if not ok:
        fails.append(name)


class Trace:
    """One scenario's lines, with the small amount of querying the checks need.

    Deliberately thin. A query language here would be a second implementation
    of the thing being tested, and the point of asserting on a printed trace is
    that the assertions stay legible to somebody who has never seen this file.
    """

    def __init__(self, name, lines):
        self.name = name
        self.lines = lines

    def find(self, needle):
        return [ln for ln in self.lines if needle in ln]

    def one(self, needle):
        m = self.find(needle)
        return m[0] if m else ""

    def kv(self, needle, key):
        """The value of k= on the first line containing `needle`."""
        m = re.search(rf"\b{key}=([^\s]+)", self.one(needle))
        return m.group(1) if m else None

    def num(self, needle, key):
        v = self.kv(needle, key)
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def ms(self, needle):
        m = re.match(r"T\|(\d+)\|", self.one(needle))
        return int(m.group(1)) if m else None

    def all_ms(self, needle):
        out = []
        for ln in self.find(needle):
            m = re.match(r"T\|(\d+)\|", ln)
            if m:
                out.append(int(m.group(1)))
        return out

    def order(self, *needles):
        """True if each needle first appears after the previous one."""
        at = []
        for n in needles:
            hits = [i for i, ln in enumerate(self.lines) if n in ln]
            if not hits:
                return False
            at.append(hits[0])
        return all(a < b for a, b in zip(at, at[1:]))


def load(path):
    scen, name, buf = {}, None, []
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("== "):
            if name:
                scen[name] = Trace(name, buf)
            name, buf = ln[3:].strip(), []
        else:
            buf.append(ln)
    if name:
        scen[name] = Trace(name, buf)
    return scen


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build/drivers.txt"
    s = load(path)
    need = ["tuner-bringup-addr-0x11", "tuner-absent", "audioproc-volume-is-attenuation",
            "hfp-incoming-answered-then-ended"]
    for n in need:
        if n not in s:
            print(f"trace is missing scenario {n} — did the harness run?")
            return 1

    # ==================================================================
    print("\nthe tuner: AN332, and the band plan")
    t = s["tuner-bringup-addr-0x11"]

    # The one this harness exists for. AN332 says the chip needs 110 ms after
    # POWER_UP before it accepts a command, and that CTS rises before that is
    # true — so waiting on CTS alone gives a deck that works on a bench and
    # fails one boot in five, reporting "no radio", which reads as a wiring
    # fault. Nobody finds that by looking at the code.
    up = t.ms("si4735|power_up")
    nxt = min([m for m in t.all_ms("si4735|property") if m is not None]
              or [10 ** 9])
    check("POWER_UP is followed by at least 110 ms before the next command",
          up is not None and nxt - up >= 110, f"gap was {nxt - up} ms")
    check("and the model saw no command inside the settle window",
          not t.find("si4735|too-soon"), "; ".join(t.find("si4735|too-soon")))

    # Reset before traffic. The chip latches its I2C address from SEN on this
    # edge, so talking to it first gets the address it had before the reset.
    check("reset is pulsed low, released, and only then is the chip addressed",
          t.order("gpio|level|pin=13 v=0", "gpio|level|pin=13 v=1",
                  "si4735|power_up"))

    check("POWER_UP asks for FM receive with the external crystal and "
          "analogue out",
          t.kv("si4735|power_up", "arg1") == "0x10"
          and t.kv("si4735|power_up", "arg2") == "0x05")
    check("bring-up reports the part it found",
          "part=Si4735" in t.one("audio|tuner"))
    check("the tuner comes up healthy", t.num("check|start", "present") == 1)

    # Modules differ in how SEN is strapped and the failure is silent, so the
    # driver has to try both addresses rather than making it a build option.
    t = s["tuner-bringup-addr-0x63"]
    check("a module at 0x63 is found after 0x11 does not answer",
          t.order("i2c|add|addr=0x11", "i2c|rm|addr=0x11", "i2c|add|addr=0x63")
          and t.num("check|start", "present") == 1)

    # No tuner fitted is an ordinary build. The deck has three other sources
    # and refusing to boot over an absent optional part would be absurd.
    t = s["tuner-absent"]
    check("no tuner fitted is degraded, not failed",
          t.kv("check|start", "health") == "degraded"
          and t.num("check|start", "present") == 0)
    check("and the radio screen still gets a sane band to draw",
          t.num("check|poll-without-tuner", "lo") == 87500)

    # FM is in 10 kHz units and AM in 1 kHz. Out by ten receives nothing at
    # all, which looks exactly like a dead aerial.
    t = s["tuner-frequency-units"]
    check("FM tunes in 10 kHz units", t.num("check|fm-tune", "chip") == 98500)
    check("AM tunes in 1 kHz units", t.num("check|am-tune", "chip") == 909)
    check("switching band powers the chip up again in the new mode",
          "band=AM" in t.one("si4735|power_up|arg1=0x11"))

    t = s["tuner-step-and-wrap"]
    check("stepping past the top of the band wraps to the bottom",
          t.num("check|wrap-up", "freq") == 87500)
    check("and stepping down from the bottom wraps to the top",
          t.num("check|wrap-down", "freq") == 108000)

    # The defect the region table was added for: a frequency saved under one
    # plan may not exist under the next, and a Si4735 asked for one outside its
    # plan does not fail — it sits there receiving nothing, which reads as a
    # dead aerial rather than a settings mistake.
    t = s["tuner-region-change-clamps"]
    check("all five band plans are present",
          len(t.find("info|region")) == 5)
    check("switching to Japan drags the presets into the Japanese band",
          t.num("check|after-jp", "p1") == 95000
          and t.num("check|after-jp", "lo") == 76000
          and t.num("check|after-jp", "hi") == 95000)
    check("the US plan steps 200 kHz, not 100",
          t.num("check|us-step", "freq") == 88300)
    check("de-emphasis follows the region: 50 us in Europe, 75 in the US",
          "val=0x0001" in t.one("prop=0x1100")
          and any("val=0x0002" in ln for ln in t.find("prop=0x1100")))

    # A reboot is a new process here, so this is the real question rather than a
    # restatement of the setter.
    t = s["tuner-region-survives-reboot"]
    check("the region survives a reboot",
          t.kv("check|after-reboot", "region") == "US")
    check("and so does the frequency",
          t.num("check|after-reboot", "freq") == 101100)

    # A hardware seek moves the chip without telling the driver. Without the
    # read-back, seek appears to do nothing: the audio changes station and the
    # display does not.
    t = s["tuner-seek-is-read-back"]
    check("seek sets SEEKUP and WRAP",
          t.kv("si4735|seek", "up") == "1" and t.kv("si4735|seek", "wrap") == "1")
    check("a hardware seek is read back rather than assumed",
          t.num("check|seek", "driver") == 96700
          and t.num("check|seek", "chip") == 96700)

    # A name flickering between "BB" and "BBC R2" on a dashboard is worse than
    # a blank one, so it is only published once all four pairs have arrived.
    t = s["tuner-rds-assembly"]
    partial = [ln for ln in t.find("check|rds-ps") if "pairs=4" not in ln]
    check("an RDS name is not shown until all four pairs have arrived",
          all("name=[]" in ln for ln in partial),
          "; ".join(partial))
    check("and then it is shown in full",
          "name=[BBC R2  ]" in t.one("pairs=4"))
    # "NOW " then "ON" then 0x0D. Without honouring the terminator the tail of
    # the previous, longer message stays on the screen for ever.
    check("radio text honours the 0x0D terminator",
          "text=[NOW ON]" in t.one("check|rds-text"),
          t.one("check|rds-text"))

    # ==================================================================
    print("\nthe audio processor: attenuation, and signed tone")
    t = s["audioproc-absent"]
    check("an absent processor is reported, not faked",
          t.num("check|start", "present") == 0)
    check("and asking an absent processor to do things is harmless",
          bool(t.find("check|no-op-when-absent")))

    # The PT2313 counts attenuation DOWN from loud: 0 is 0 dB, 63 is
    # -78.75 dB. Everything above the driver thinks in volume going up, so the
    # inversion happens once, at the chip boundary. Get it backwards and the
    # volume control works perfectly in reverse.
    t = s["audioproc-volume-is-attenuation"]
    vols = t.find("pt2313|volume")

    def atten_after(tag):
        idx = next(i for i, ln in enumerate(t.lines) if tag in ln)
        for ln in reversed(t.lines[:idx]):
            m = re.search(r"pt2313\|volume\|atten_steps=(\d+)", ln)
            if m:
                return int(m.group(1))
        return None

    check("deck volume 63 writes 0 steps of attenuation",
          atten_after("check|loudest") == 0)
    check("deck volume 0 writes 63 steps of attenuation",
          atten_after("check|quietest") == 63)
    check("and the middle is the middle",
          atten_after("check|middle") == 31)
    check("volume out of range clamps rather than wrapping",
          t.num("check|clamp-high", "get") == 63
          and t.num("check|clamp-low", "get") == 0)
    check("the chip is initialised silent and only then turned up",
          len(vols) >= 2 and "atten_steps=63" in vols[0])

    # Magnitude-plus-direction, not two's complement: -7 and +7 share a
    # magnitude nibble and differ in one bit. A driver that casts an int gets
    # the sign silently wrong, and wrong tone sounds like taste rather than
    # like a bug.
    t = s["audioproc-tone-is-magnitude-plus-direction"]
    for kind in ("bass", "treble"):
        raws = {}
        asked = None
        for ln in t.lines:
            m = re.search(rf"info\|asking-{kind}\|v=(-?\d+)", ln)
            if m:
                asked = int(m.group(1))
                continue
            m = re.search(rf"pt2313\|{kind}\|steps=(-?\d+) raw=(0x[0-9a-f]+)", ln)
            if m and asked is not None:
                raws[asked] = (int(m.group(1)), m.group(2))
                asked = None
        check(f"{kind} round-trips through the chip's encoding for every step",
              all(raws.get(v, (None,))[0] == v for v in (7, -7, 3, -3, 0)),
              str(raws))
        if 7 in raws and -7 in raws:
            hi, lo = int(raws[7][1], 16), int(raws[-7][1], 16)
            check(f"{kind} +7 and -7 share a magnitude and differ by the "
                  f"direction bit",
                  (hi & 0x07) == (lo & 0x07) and (hi ^ lo) == 0x08,
                  f"{raws[7][1]} vs {raws[-7][1]}")

    # Balance and fader are not registers on this part — the driver derives
    # four speaker attenuators. The channels differ only in the top three bits,
    # so a transposed pair swaps front and rear, which the driver's own comment
    # calls the most likely first-power-up mistake.
    t = s["audioproc-balance-and-fader"]

    def block(tag):
        idx = next(i for i, ln in enumerate(t.lines) if tag in ln)
        out = {}
        for ln in t.lines[idx + 1:]:
            m = re.search(r"pt2313\|speaker\|ch=(\S+) atten_steps=(\d+)", ln)
            if not m:
                if "info|" in ln:
                    break
                continue
            out[m.group(1)] = int(m.group(2))
        return out

    centred = block("info|centred")
    check("centred means all four speakers un-attenuated",
          centred and set(centred.values()) == {0}, str(centred))
    left = block("info|hard-left")
    check("hard left attenuates both right speakers and neither left one",
          left.get("left-front") == 0 and left.get("left-rear") == 0
          and left.get("right-front", 0) > 0 and left.get("right-rear", 0) > 0,
          str(left))
    right = block("info|hard-right")
    check("hard right is the mirror image",
          right.get("right-front") == 0 and right.get("right-rear") == 0
          and right.get("left-front", 0) > 0 and right.get("left-rear", 0) > 0,
          str(right))
    front = block("info|centre-then-full-front")
    check("full front attenuates the REAR pair — not one side",
          front.get("left-front") == 0 and front.get("right-front") == 0
          and front.get("left-rear", 0) > 0 and front.get("right-rear", 0) > 0,
          str(front))
    rear = block("info|full-rear")
    check("full rear attenuates the FRONT pair",
          rear.get("left-rear") == 0 and rear.get("right-rear") == 0
          and rear.get("left-front", 0) > 0 and rear.get("right-front", 0) > 0,
          str(rear))

    t = s["audioproc-mute-keeps-the-volume"]
    check("mute does not lose the volume setting",
          t.num("check|muted", "get") == 40
          and t.num("check|unmuted", "get") == 40)

    t = s["audioproc-source-select"]
    inputs = [int(re.search(r"input=(\d)", ln).group(1))
              for ln in t.find("pt2313|switch")]
    check("each source selects a different chip input",
          len(set(inputs[-2:])) == 2, str(inputs))

    # ==================================================================
    print("\nhands-free: state derived from the indicator pair")
    t = s["hfp-incoming-answered-then-ended"]
    check("an incoming call is INCOMING with its caller ID",
          t.kv("check|ringing", "state") == "incoming"
          and "+441632960123" in t.one("check|ringing"))
    check("answering sends ATA exactly once",
          t.num("check|at-counts", "answers") == 1)
    # The instant that matters: a phone does not move both indicators
    # atomically, so the deck must be ACTIVE the moment `call` goes to 1 —
    # not once `setup` gets round to clearing.
    check("ACTIVE the moment call=1, with setup still 1",
          t.kv("check|call-set-while-setup-still-1", "state") == "active",
          t.one("check|call-set-while-setup-still-1"))
    check("and still ACTIVE after setup clears",
          t.kv("check|answered", "state") == "active")
    check("the duration counts from the ACTIVE transition, not from the ring",
          t.num("check|42s-in", "secs") == 42)
    check("hanging up shows ENDED, with the duration still on screen",
          t.kv("check|hung-up", "state") == "ended"
          and t.num("check|hung-up", "secs") == 42)
    check("ENDED is still up 2 s later",
          t.kv("check|2s-after-end", "state") == "ended")
    check("and has cleared itself by 3 s, releasing the music",
          t.kv("check|3s-after-end", "state") == "idle"
          and t.num("check|3s-after-end", "busy") == 0)

    # THE ONE THE DESIGN EXISTS FOR. Some phones send `call` before `setup`
    # clears. A state machine tracked through event order breaks here — on
    # somebody else's phone, which is the worst place for it to break.
    t = s["hfp-indicators-in-the-other-order"]
    check("a phone that clears setup late is still ACTIVE",
          t.kv("check|call-first", "state") == "active")
    check("and stays ACTIVE for as long as it takes",
          t.kv("check|1500ms-later-setup-still-1", "state") == "active")
    check("and does not glitch when setup finally clears",
          t.kv("check|setup-cleared", "state") == "active")

    t = s["hfp-outgoing-dial-and-alert"]
    check("redial sends ATD once", t.num("check|at-counts", "dials") == 1)
    check("setup=2 (dialling) is OUTGOING",
          t.kv("check|dialling", "state") == "outgoing")
    check("setup=3 (remote alerting) is still OUTGOING",
          t.kv("check|alerting", "state") == "outgoing")
    check("and it becomes ACTIVE when the far end picks up",
          t.kv("check|connected", "state") == "active")

    # A deck that sends AT+CHUP on an idle link hangs up somebody else's call
    # the moment it connects to their phone.
    t = s["hfp-incoming-rejected"]
    check("reject sends nothing when there is no call",
          t.num("check|reject-while-idle", "rejects") == 0)
    check("answer sends nothing when nothing is ringing",
          t.num("check|answer-while-idle", "answers") == 0)
    check("reject sends AT+CHUP when a call is ringing",
          t.num("check|reject-while-ringing", "rejects") == 1)

    # A phone that leaves the car mid-call sends no indicator update, because
    # it is gone. Without the disconnect handler the deck shows a call that
    # does not exist, forever, and the music never comes back.
    t = s["hfp-phone-walks-away-mid-call"]
    check("a phone disconnecting mid-call ends the call",
          t.kv("check|phone-gone", "state") == "ended")
    check("and the deck returns to idle rather than showing a ghost call",
          t.kv("check|after-ended-timeout", "state") == "idle")
    check("every mutex taken was given back",
          t.num("check|locks", "imbalance") == 0)

    print()
    if fails:
        print(f"{len(fails)} of {checks} driver checks FAILED")
        for f in fails:
            print(f"  · {f}")
        return 1
    print(f"all {checks} driver checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
