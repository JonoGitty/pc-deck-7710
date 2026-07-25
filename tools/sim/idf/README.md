# A fake ESP-IDF, so the drivers can be tested without an ESP32

`tools/sim/` already runs `deck_ui.c` on a host. It could not run
`deck_tuner.c`, `deck_audioproc.c` or `deck_hfp.c`, because those are the files
that actually touch hardware — and those three are the newest code in the
repository and the least tested. "It compiles for the ESP32" was the entire
guarantee.

So this directory is the smallest ESP-IDF that those three files will compile
against, and `../fake_hw.c` is a model of what is on the other side of it.

## The line, and why it is drawn here

The stubs replace **the SDK, not the driver**. `deck_tuner.c` is compiled
unmodified, byte for byte the file the ESP32 runs, and what it talks to is a
Si4735 model that answers like the datasheet says a Si4735 answers. Every
assertion in `test_drivers.py` is therefore about the real driver's behaviour.

The alternative — reimplementing the drivers' logic in Python and testing
that — would pass forever while the firmware rotted, which is the failure this
whole repository is built to avoid.

## The one that makes it worth doing: time is virtual

`vTaskDelay()` does not sleep. It **advances a virtual clock**, and
`esp_timer_get_time()` reads that clock. Two things follow, and the first is
the reason this exists:

- **AN332's 110 ms wait after POWER_UP becomes observable.** The datasheet
  says the chip needs 110 ms before it accepts another command, and that CTS
  goes high *before* that is true — so a driver that waits on CTS alone works
  on a bench and fails one boot in five. The Si4735 model records the virtual
  time of every command and `test_drivers.py` asserts the gap. On real
  hardware that bug is a rare, unreproducible boot failure; here it is a
  failing test.
- **The suite runs in milliseconds.** A call that ends and clears itself
  2.5 seconds later is tested by advancing the clock 2.5 seconds, not by
  waiting.

## What is modelled, and what is not

| | |
|---|---|
| **I²C** | A bus with devices at addresses. Transfers are recorded and answered by a device model. Both Si4735 addresses (0x11, 0x63) exist so the probe-both-addresses path is real |
| **Si4735** | Command semantics, the CTS bit, response payloads, RDS groups, and a hardware seek that moves the frequency behind the driver's back |
| **PT2313** | Every single-byte write decoded back into function and value, so the encoding is checked rather than the bytes being counted |
| **GPIO** | Level changes, timestamped — enough to assert the reset pulse happens before any bus traffic |
| **NVS** | An in-memory blob store that survives a simulated reboot, which is what makes region persistence testable |
| **HFP** | The client API surface, plus a scripted Audio Gateway: the test plays a phone, including the awkward orders real phones use |
| **Not modelled** | Bus arbitration, clock stretching, timeouts, SCO packet timing, actual audio |

That last row matters. This proves the drivers' **logic** — command order,
encoding, state derivation, timing rules they are supposed to honour. It cannot
prove the electrical layer, and it does not claim to. The firmware still has
never run on hardware.
