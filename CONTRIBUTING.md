# Contributing

Contributions are welcome. A few things are worth knowing before you start,
because this project has one unusual rule and it will bite you otherwise.

## The one rule

**`core/` is verified against the JavaScript it was ported from.**

```sh
sh tools/verify/run.sh
```

Both implementations render the same input and the framebuffers are diffed.
If you change a screen's output *on purpose*, the diff will fail — **update
the expectation, never delete the case.** A deleted case is a regression
nobody will ever notice again.

This is not ceremony. It has caught a dolphin breaching one frame early,
waterfall thresholds landing differently at double precision, and text
dithering into mush on 1-bit panels — none of which was visible by eye.

## Before opening a pull request

1. `sh tools/verify/run.sh` passes. It runs the behaviour suite too, so this is
   the single command that matters.
2. If you touched the firmware's UI layer, run it: `sh tools/sim/run.sh --gif
   /tmp/deck.gif` and look at it. The simulator compiles the real `deck_ui.c`
   in about a second, which is faster than reasoning about it.
3. If you touched anything a screen draws, `sh tools/media/make.sh` and commit
   the regenerated pictures. A README showing the old behaviour is worse than
   one with no pictures, because it is convincing.
4. If you touched the firmware, it builds: `python3 tools/deckctl.py build`.
5. CI runs 1 and 4 on every push.

New behaviour deserves a new assertion in `tools/sim/test_behaviour.py`, named
after what a person would notice rather than after the code that does it. The
conventions are in [docs/TESTING.md](docs/TESTING.md).

## What the project wants

- **New display targets.** Adding a panel should be a driver plus a table
  entry. If it is not, that is a bug in the abstraction and worth saying so.
- **Animations.** See [docs/MOVIE-RENDERING.md](docs/MOVIE-RENDERING.md), and
  read one of the bundled scenes first — each solves a different version of
  "four brightness levels is not many".
- **Anything tested on real hardware.** The firmware has never been flashed.
  A bug report from a bench is worth more than any amount of review.

## What it does not want

- **Anything derived from a manufacturer's firmware.** No disassembly, no
  decompilation, no extracted fonts or artwork. Every asset here is generated
  by code here and it stays that way.
- **Meaning encoded in brightness alone.** It collapses on 1-bit glass. Use a
  marker, an offset or an inverted row — see [docs/UI-SPEC.md](docs/UI-SPEC.md).
- **Hand-drawn pictures in `docs/media/`.** Everything there is generated. If
  something needs a picture the pipeline cannot produce, extend the pipeline.

## Style

Match the file you are in. Comments explain *why*, especially where the code
looks odd — most of the odd-looking code here is odd for a reason that cost
somebody an evening, and the comment is that evening written down.

## Licensing

By contributing you agree your work is licensed under the MIT licence in
[LICENSE](LICENSE), and you confirm you have the right to license it that way.
See [NOTICE](NOTICE).
