# docs/

The documentation, and the project's web page.

| | |
|---|---|
| [HANDBOOK.md](HANDBOOK.md) | Build one. Tiers, parts, bring-up order, what to do first |
| [BUYING.md](BUYING.md) | Where to actually buy it, in the order to order it |
| [HARDWARE.md](HARDWARE.md) | The component survey and BOM. Every claim marked ✅ verified or ⚠️ not |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Why there is one renderer compiled twice, and what that cost |
| [UI-SPEC.md](UI-SPEC.md) | Layout tiers, the intensity model, the thin-feature rule |
| [MOVIE-RENDERING.md](MOVIE-RENDERING.md) | Making animations, and the traps that have been hit for real |
| [CONTROL.md](CONTROL.md) | Buttons, encoder, and what goes back to the phone over AVRCP |
| [CALLING.md](CALLING.md) | Taking calls: HFP, the microphone, and the four call screens |
| [RADIO.md](RADIO.md) | The tuner, the aerial, and a radio screen worth having |
| [TESTING.md](TESTING.md) | Running the deck on your computer, and the bring-up checks on hardware |
| [DIAGNOSTICS.md](DIAGNOSTICS.md) | When it does not work: the self-test, the serial line, crash dumps |
| [DONORS.md](DONORS.md) | Which scrap head unit to buy and gut — generated from `donors/` |
| [VEHICLES.md](VEHICLES.md) | What each car needs on top of the deck — generated from `vehicles/` |
| [VERSIONING.md](VERSIONING.md) | How the PC deck, the core and the firmware version separately |

## The site

`index.html` is the project page. It is a single hand-written file with no
build step, no framework and no external requests — every image it uses is in
`media/`, which is why it renders the same whether it is served by GitHub Pages
or opened off a disk.

**To publish it:** repository *Settings → Pages → Build and deployment*, source
*Deploy from a branch*, then **all three** of these:

| Field | Must be |
|---|---|
| Branch | **`master`** — this repository's default branch, **not `main`**, which does not exist here |
| Folder | **`/docs`** — *not* `/ (root)`, which is the default |
| Source | *Deploy from a branch* |

The page then appears at `https://jonogitty.github.io/pc-deck-7710/`.

⚠️ **The folder is the one that gets missed**, because `/ (root)` is what the
dropdown offers first and it *appears to work*: Pages goes green, the URL
returns 200, and you get a Jekyll rendering of the top-level `README.md` with
the repository description as its title. It is a real page, so nothing looks
broken — it is simply the wrong one. The giveaway is that images 404 while
`…/pc-deck-7710/docs/` serves the actual site.

`.nojekyll` lives in this folder, so with `/docs` selected the HTML is served
exactly as written. Under `/ (root)` it has no effect, which is why the root
deploy goes through Jekyll at all.

### If the URL is wrong or missing

| Symptom | Cause |
|---|---|
| 404, GitHub's "no site here" page | Pages is off — nobody has set the source |
| 200, but the title is the repo description and images 404 | Folder is `/ (root)`; set it to `/docs` |
| 404 after setting a branch | It was pointed at `main`; the default branch is `master` |
| 404 and everything above is right | `docs/` is not on the default branch yet — merge first |

None of this can be set from inside the repository: no workflow, token or API
call here can turn Pages on or choose its source, branch or folder. A human has
to click it, in a browser — **the GitHub mobile app has no repository settings
at all**. The direct link is
`https://github.com/JonoGitty/pc-deck-7710/settings/pages`.

Links from the page into the documentation point at GitHub rather than at
Pages, because with Jekyll disabled a `.md` file served over Pages arrives as
plain text.

## The pictures

Nothing in `media/` is drawn by hand, and one command rebuilds all of it:

```sh
sh tools/media/make.sh
```

- **Screen animations** come from `tools/media/shots.c`, which links the same
  `core/` the firmware links, driven by a synthesised 120 bpm loop. If a screen
  regresses, its picture regresses with it.
- **Faceplate stills** are the real `legacy/web` page in real Chromium with the
  WebSocket stubbed — the bezel, the knob, the glass and the dot pitch are the
  actual thing.
- **Movie previews** are the shipped `.dmv` files decoded, trimmed to excerpts
  because a preview GIF costs about 3 KB a frame.
- **Diagrams** come from `tools/diagrams/`, as SVG rather than PNG so that a
  change is a diff you can read. `pinmap.svg` is the important one: it is
  parsed out of the firmware's own `#define PIN_...` lines rather than drawn
  alongside them, it refuses to draw a GPIO that two drivers both claim, and
  `tools/verify/test_diagrams.py` fails if the committed picture and the code
  have diverged. `wiring.svg`, `assembly.svg`, `dimensions.svg` and
  `finished.svg` are laid out by hand in code but regenerate from the same
  command.

That is the point of the pipeline rather than a folder of screenshots: a README
full of stale mockups is worse than one with no pictures, because it is
convincing.

The wiring diagram is the case that justifies the effort. A hand-drawn one is
correct on the day it is drawn and silently wrong afterwards, and the person it
misleads is holding a soldering iron over a £30 module. Deriving it from the
firmware turns "somebody must remember to update the picture" into "the build
stops".
