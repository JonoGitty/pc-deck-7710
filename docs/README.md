# docs/

The documentation, and the project's web page.

| | |
|---|---|
| [HANDBOOK.md](HANDBOOK.md) | Build one. Tiers, parts, bring-up order, what to do first |
| [HARDWARE.md](HARDWARE.md) | The component survey and BOM. Every claim marked ✅ verified or ⚠️ not |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Why there is one renderer compiled twice, and what that cost |
| [UI-SPEC.md](UI-SPEC.md) | Layout tiers, the intensity model, the thin-feature rule |
| [MOVIE-RENDERING.md](MOVIE-RENDERING.md) | Making animations, and the traps that have been hit for real |
| [CONTROL.md](CONTROL.md) | Buttons, encoder, and what goes back to the phone over AVRCP |
| [VERSIONING.md](VERSIONING.md) | How the PC deck, the core and the firmware version separately |

## The site

`index.html` is the project page. It is a single hand-written file with no
build step, no framework and no external requests — every image it uses is in
`media/`, which is why it renders the same whether it is served by GitHub Pages
or opened off a disk.

**To publish it:** repository *Settings → Pages → Build and deployment*, source
*Deploy from a branch*, branch `main`, folder `/docs`. That is the whole setup;
`.nojekyll` is already here so the HTML is served as written rather than fed
through Jekyll. The page then appears at
`https://jonogitty.github.io/pc-deck-7710/`.

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

That is the point of the pipeline rather than a folder of screenshots: a README
full of stale mockups is worse than one with no pictures, because it is
convincing.
