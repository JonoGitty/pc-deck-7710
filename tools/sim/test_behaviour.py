#!/usr/bin/env python3
"""Assert what the deck actually does, by running it.

The firmware's UI layer — which screen is on, when the dolphins take over,
what a track change interrupts, how the wipe behaves — is the part most likely
to be subtly wrong and the least practical to check on hardware: seeing the
idle machine takes fifteen seconds of silence per attempt, and you cannot
single-step a car stereo.

So the simulator emits a state trace and this asserts on it. Every test here
describes a behaviour a person would notice, in the terms they would notice it,
because a test named after an implementation detail stops being maintained the
moment the implementation changes.

    python3 tools/sim/test_behaviour.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIM = os.path.join(ROOT, "build", "sim")

LIVE, CLOCK, OCEAN, NOWPLAYING = 0, 1, 2, 3
STATE = {LIVE: "live", CLOCK: "clock", OCEAN: "ocean", NOWPLAYING: "now-playing"}

_fails = []


def run(args, script=None, secs=30):
    cmd = [SIM, "--trace", "--secs", str(secs)]
    if script:
        cmd += ["--script", os.path.join(ROOT, "tools", "sim", "scripts", script)]
    cmd += args
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        if line.startswith("T "):
            _, t, mode, state, lit, wipe = line.split()
            rows.append({"t": float(t), "mode": int(mode), "state": int(state),
                         "lit": int(lit), "wipe": int(wipe)})
    return rows


def check(name, cond, detail=""):
    if cond:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}   {detail}")
        _fails.append(name)


def at(rows, t):
    """The frame nearest t. Nearest rather than exact because the frame rate is
    a parameter and a test that breaks when you change --fps is testing the
    harness."""
    return min(rows, key=lambda r: abs(r["t"] - t))


def main():
    if not os.path.exists(SIM):
        sys.exit("build the simulator first: sh tools/sim/run.sh --secs 1")

    print("\nidle machine — silence at 4s")
    rows = run([], script="idle.txt", secs=24)
    check("plays live while there is audio", at(rows, 3.0)["state"] == LIVE,
          f'got {STATE[at(rows, 3.0)["state"]]}')
    # 3 s after silence, the clock. Sampled at 8 s rather than 7.1 so the test
    # is about the behaviour and not about where the boundary rounds.
    check("clock after ~3s of silence", at(rows, 8.0)["state"] == CLOCK,
          f'got {STATE[at(rows, 8.0)["state"]]}')
    check("dolphins after ~12s of silence", at(rows, 18.0)["state"] == OCEAN,
          f'got {STATE[at(rows, 18.0)["state"]]}')
    check("back to live when the music returns", at(rows, 21.0)["state"] == LIVE,
          f'got {STATE[at(rows, 21.0)["state"]]}')

    # The wipe is the transition, and a transition that never fires is the
    # commonest way for one to break — it looks fine in a still.
    wiped = [r for r in rows if 20.0 <= r["t"] <= 21.5 and r["wipe"] >= 0]
    check("a wipe runs when the music returns", len(wiped) > 0,
          "no frame had an active wipe edge")

    print("\ntrack change")
    rows2 = run([], script="idle.txt", secs=30)
    npl = [r for r in rows2 if 24.0 <= r["t"] <= 26.5 and r["state"] == NOWPLAYING]
    check("NOW PLAYING interstitial on a track change", len(npl) > 0)
    check("and it ends", at(rows2, 27.5)["state"] != NOWPLAYING)

    print("\nmetadata screens hold through a pause")
    rows3 = run([], script="idle.txt", secs=40)
    # ART is selected at 28 s; from 32 s LYRICS. Both must ignore the idle
    # machine, because they are about the track rather than the audio.
    check("album art selected", at(rows3, 30.0)["mode"] == 8,
          f'mode {at(rows3, 30.0)["mode"]}')
    check("lyrics selected", at(rows3, 34.0)["mode"] == 9,
          f'mode {at(rows3, 34.0)["mode"]}')

    print("\nevery screen draws something")
    rows4 = run([], script="tour.txt", secs=12)
    for m in range(11):
        frames = [r for r in rows4 if r["mode"] == m]
        if not frames:
            continue
        best = max(r["lit"] for r in frames)
        # The MOVIE screen with nothing installed legitimately draws only a
        # line of text, so the floor is low on purpose. Zero is the bug worth
        # catching: a screen that renders nothing at all.
        check(f"mode {m} lights dots", best > 20, f"best {best}")

    print("\nmovie playback")
    dmv = os.path.join(ROOT, "movies", "vtec_256x64.dmv")
    if os.path.exists(dmv):
        rows5 = run(["--movie", dmv], secs=8)
        moving = len({r["lit"] for r in rows5}) > 5
        check("a loaded movie animates", moving,
              "the lit-dot count never changed")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails)}\n")
        return 1
    print("all behaviour checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
