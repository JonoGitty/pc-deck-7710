// swift-tools-version: 5.9
//
// DECK·7710's renderer, as a Swift package.
//
// `core/` is C99 with no allocation, no libm and nothing from libc beyond
// <string.h>. That is what makes this possible at all: the same translation
// units the ESP32 firmware links, and the same ones the browser preview
// compiles to WebAssembly, build unmodified for iOS, iPadOS and macOS. There is
// no port here and there must never be one — a second implementation is a
// second thing to keep in step, and the whole point of `tools/verify/` is that
// there is exactly one renderer.
//
//   dependencies: [
//     .package(url: "https://github.com/JonoGitty/pc-deck-7710", from: "1.0.0")
//   ]
//
// Then `import DeckCore` and call the same functions the firmware calls. Every
// screen takes a `deck_fb_t` and a `deck_state_t`; fill the state from an FFT,
// render, and read back one intensity 0..4 per dot. What a host does with those
// intensities is its own business — that is the same split as the firmware's
// output stage, and it is why this package draws nothing itself.
//
// WHAT THIS PACKAGE DELIBERATELY DOES NOT CONTAIN
//
// The movies. `movies/*.dmv` are content, not code: some are rendered from
// scenes in this repository and some are re-staged from clips whose rights
// belong to whoever filmed them. A shipping application needs to be able to
// answer for every frame it distributes, so it brings its own. `core/movie.c`
// is here — the decoder — and it will play any .dmv you hand it.
import PackageDescription

let package = Package(
    name: "DeckCore",
    // Deliberately old floors. Nothing in here is newer than C99, so the
    // constraint should come from the app, not from its renderer.
    platforms: [
        .iOS(.v13), .macCatalyst(.v13), .macOS(.v10_15),
        .tvOS(.v13), .watchOS(.v6),
    ],
    products: [
        .library(name: "DeckCore", targets: ["DeckCore"]),
    ],
    targets: [
        .target(
            name: "DeckCore",
            path: "core",
            // Everything else under core/ is a .c or a .h, including the three
            // generated ROMs. They are generated, not written — see CLAUDE.md.
            exclude: ["README.md"],
            // The headers ARE the sources directory. core/deck.h, core/screens.h
            // and core/state.h are the interface; the rest come along, which is
            // untidy and harmless, and beats maintaining a parallel include tree
            // that could drift from the code the firmware compiles.
            publicHeadersPath: "."
            // No cSettings. unsafeFlags would make this package unusable as a
            // versioned dependency, which is the only way it is meant to be
            // used, and the code needs no flags: it compiles clean under
            // -Wall -Wextra at C99 and at the toolchain default.
        ),
    ]
)
