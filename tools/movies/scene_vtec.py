#!/usr/bin/env python3
"""VTEC — a roadster's instrument cluster, wound out and back.

    python3 tools/movies/scene_vtec.py            # 256x64, SSD1322
    python3 tools/movies/scene_vtec.py --legacy   # 192x48 + install

The car this is drawn from puts a **digital bar tachometer straight across the
top of the binnacle** and a digital speed readout below it — no analogue
needles at all, which is why it works here when a normal dial cluster would
not. A round dial on a 4:1 panel is a circle with two thirds of the frame
empty beside it. A bar tacho *is* a 4:1 strip. The instrument and the display
are the same shape, and that is the whole reason this scene exists.

What it has to get right, in order of how badly it reads when wrong:

  * **The bar is the subject.** It runs nearly the full width, and everything
    else — speed, gear, the redline marks — is arranged around it rather than
    competing with it.

  * **Revs do not ramp, they fight.** A tacho sweeping smoothly up and down is
    a progress bar. Real ones hang against the limiter, drop off the clutch,
    and hesitate at the top of a gear. The rev model here is a crude engine
    with load, inertia and a limiter, driven by a gearchange script, because
    the *hesitation* is what makes it look like driving.

  * **VTEC is a threshold, so it gets a threshold's treatment.** Below the
    crossover the bar is level 2 and the top marks are dim. Above it the bar
    goes hot, a VTEC lamp lights, and the segments past the crossover pick up
    a brighter cap. It is the one moment in the loop and the panel should say
    so without any subtlety at all.

  * **The limiter flashes.** Not smoothly — on and off at 10 fps, which on a
    dot-matrix panel is exactly the ugly, urgent thing it is on a real dash.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckfont as F
import dmv as M

LEGACY = "--legacy" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
W = int(ARGS[0]) if len(ARGS) > 0 else 256
H = int(ARGS[1]) if len(ARGS) > 1 else 64
if LEGACY:
    W, H = 192, 48

FPS = 10
NF = 260                    # 26 s
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                   "movies", f"vtec_{W}x{H}.dmv")

# The car: 9000 rpm redline, VTEC crossover just under 6000, limiter at 9000.
RPM_MAX   = 9000
RPM_VTEC  = 5800
RPM_LIMIT = 8900
# Ratios chosen so the speed readout is plausible across a 26-second loop —
# roughly 60 km/h at the limiter in first and 240 in sixth — rather than
# transcribed from a workshop manual. The animation is not a simulator and
# saying so here is cheaper than a number nobody can check being quietly wrong.
GEARS     = [4.17, 2.73, 1.97, 1.55, 1.29, 1.08]
FINAL     = 4.10
TYRE_M    = 1.99            # rolling circumference, metres (205/55R16)

# Level centres. The quantiser puts level n at (n + 0.5) / 4, so these are the
# solid fields; 0.25 and 0.5 are the 50/50 checkerboards that would drown the
# bar in noise. See CLAUDE.md.
L1, L2, L3 = 0.375, 0.625, 0.875


# ---------------------------------------------------------------- the engine
def torque(rpm):
    """A crude curve with a step at the crossover.

    Not accurate and not trying to be. What it has to do is make the engine
    pull harder above VTEC than below it, so the bar visibly *accelerates* as
    it crosses — the acceleration is the tell, not the lamp.
    """
    x = rpm / RPM_MAX
    base = 0.55 + 0.85 * x - 0.75 * x * x
    if rpm > RPM_VTEC:
        base *= 1.0 + 0.34 * min(1.0, (rpm - RPM_VTEC) / 1400.0)
    return max(0.05, base)


def drive():
    """Rev and gear per frame, from a script of shifts.

    A state machine rather than a waveform: pulling to the limiter, holding
    against it, the dip through a shift, then doing it again a gear higher. A
    sine wave would sweep the bar prettily and look nothing like a car.
    """
    rpm, gear, t = 1200.0, 0, 0.0
    shift_until = -1.0
    out = []
    for f in range(NF):
        t = f / FPS
        limiting = False
        if t < shift_until:
            # Clutch in: revs fall on their own inertia, no drive.
            rpm -= 2600 * (1.0 / FPS)
        else:
            if shift_until > 0 and t >= shift_until and out and out[-1][2]:
                pass
            rpm += torque(rpm) * 3400 * (1.0 / FPS) / (1.0 + gear * 0.55)
            if rpm >= RPM_LIMIT:
                # The limiter does not hold a steady value, it bounces off it.
                rpm = RPM_LIMIT - 120 - 90 * abs(math.sin(t * 26.0))
                limiting = True
                if gear < len(GEARS) - 1:
                    shift_until = t + 0.32
                    gear += 1
                    rpm *= GEARS[gear] / GEARS[gear - 1]
        rpm = max(900.0, min(RPM_MAX, rpm))
        speed = rpm / (GEARS[gear] * FINAL) * TYRE_M * 60 / 1000  # km/h
        out.append((rpm, gear, limiting, speed))

        # Once through the box, lift and start again — a loop that ends where
        # it began, so the .dmv can repeat without a visible cut.
        if gear == len(GEARS) - 1 and rpm > RPM_LIMIT - 400 and f < NF - 40:
            rpm, gear, shift_until = 1500.0, 0, -1.0
    return out


PROFILE = drive()


# ---------------------------------------------------------------- drawing
def rect(buf, x0, y0, x1, y1, level):
    for y in range(max(0, y0), min(H, y1 + 1)):
        row = y * W
        for x in range(max(0, x0), min(W, x1 + 1)):
            if level > buf[row + x]:
                buf[row + x] = level


def frame(fi):
    rpm, gear, limiting, speed = PROFILE[fi]
    buf = bytearray(W * H)

    # --- the bar tacho, straight across the top -------------------------
    bx0, bx1 = 2, W - 3
    by0 = 3
    bh = 11 if H >= 56 else 9
    span = bx1 - bx0

    seg_w = 3 if W >= 240 else 2
    gap = 1
    nseg = span // (seg_w + gap)
    lit = int(nseg * rpm / RPM_MAX + 0.5)
    vtec_seg = int(nseg * RPM_VTEC / RPM_MAX)

    for s in range(nseg):
        x = bx0 + s * (seg_w + gap)
        if s < lit:
            # Past the crossover the segments are hot; before it they are the
            # middle level. Two solid fields, no gradient — a ramp across a
            # bar this size dithers and the eye reads texture, not level.
            lv = 3 if s >= vtec_seg else 2
            if limiting and (fi % 2 == 0):
                lv = 0                      # the flash, hard on and off
            rect(buf, x, by0, x + seg_w - 1, by0 + bh - 1, lv)
        elif s >= vtec_seg:
            # Unlit segments past the crossover still show, dim, so you can
            # see where VTEC is before you get there.
            rect(buf, x, by0 + bh - 2, x + seg_w - 1, by0 + bh - 1, 1)

    # crossover tick, above the bar
    vx = bx0 + vtec_seg * (seg_w + gap)
    rect(buf, vx, by0 - 2, vx + seg_w - 1, by0 - 2, 3)

    # --- the numbers ----------------------------------------------------
    ty = by0 + bh + 3
    F.draw(buf, W, H, 2, ty, f"{int(speed):3d}", 3, 2 if H >= 56 else 1)
    kmh_x = 2 + F.width(f"{int(speed):3d}", 2 if H >= 56 else 1) + 2
    F.draw(buf, W, H, kmh_x, ty + (8 if H >= 56 else 4), "KM/H", 1, 1)

    # Gear, hard right. Big, because it is the other thing a driver reads
    # without looking, and it changes rarely enough to be worth the space.
    gtxt = str(gear + 1)
    gx = W - 2 - F.width(gtxt, 2)
    F.draw(buf, W, H, gx, ty, gtxt, 3, 2)
    F.draw(buf, W, H, gx - F.width("GEAR", 1) - 3, ty + 4, "GEAR", 1, 1)

    # rpm, centred under the bar
    rtxt = f"{int(rpm / 10) * 10}"
    F.draw(buf, W, H, (W - F.width(rtxt, 1)) // 2, ty + 2, rtxt, 2, 1)
    F.draw(buf, W, H, (W - F.width("RPM", 1)) // 2, ty + 10, "RPM", 1, 1)

    # --- the lamps ------------------------------------------------------
    ly = H - 8
    if rpm > RPM_VTEC:
        # Knocked out, not overdrawn: the one thing in the frame that must be
        # unmissable gets a box of its own. deckfont.plate clears first.
        F.plate(buf, W, H, 2, ly, "VTEC", 3, 1)
    if limiting and (fi % 2 == 0):
        F.plate(buf, W, H, 40, ly, "LIMIT", 3, 1)

    if fi < 26:
        F.plate(buf, W, H, W - 2 - F.width("S2K CLUSTER", 1), ly,
                "S2K CLUSTER", 3, 1)
    return buf


def main():
    print(f"VTEC — {W}x{H}, {NF} frames, {NF / FPS:.0f}s")
    frames = [frame(i) for i in range(NF)]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = M.write_dmv(OUT, frames, W, H, FPS, "VTEC", loop=True)
    print(f"wrote {os.path.relpath(OUT)}  {len(blob)} bytes "
          f"({100 * len(blob) / (W * H * NF):.1f}% of raw)")
    if LEGACY:
        M.install_legacy(OUT, "VTEC")
        print("installed into the PC deck — press V on the faceplate")
    # A frame from just after the crossover, which is the one worth checking.
    peak = max(range(NF), key=lambda i: PROFILE[i][0] if PROFILE[i][1] == 1 else 0)
    print(M.to_ascii(frames[peak], W, H))


if __name__ == "__main__":
    main()
