// Browser preview driven by core/ compiled to WebAssembly.
//
// This file deliberately does NO drawing of its own beyond turning the device
// bytes the core emits into screen pixels. Every dot position, every intensity
// and every dither decision comes from the same C the firmware runs.
"use strict";

// Real parts, so the picker is a shopping list as much as a preview control.
const TARGETS = [
  { id: "legacy",  name: "Legacy PC deck — 192×48",        w: 192, h: 48, levels: 5 },
  { id: "ssd1322", name: "SSD1322 OLED — 256×64",          w: 256, h: 64, levels: 16 },
  { id: "gp1294",  name: "Futaba GP1294AI VFD — 256×48",   w: 256, h: 48, levels: 2 },
  { id: "gp1287",  name: "Futaba GP1287BI VFD — 256×50",   w: 256, h: 50, levels: 2 },
  { id: "noritake",name: "Noritake GU256×64 — 256×64",     w: 256, h: 64, levels: 2 },
  { id: "bar",     name: "8.8\" bar LCD — 192×48 logical", w: 192, h: 48, levels: 256 },
];

// Illumination colours, carried over from the legacy deck. Only meaningful on
// colour-capable targets; the picker disables them elsewhere.
const SCHEMES = [
  { id: "AMBER",   bg: "#020403", dim: "#9A5518", main: "#F3A52B", hot: "#FFD978", bloom: "#FF7A16" },
  { id: "RED",     bg: "#050101", dim: "#8a1f1f", main: "#ff2e2e", hot: "#ff9a7a", bloom: "#ff2a00" },
  { id: "EMERALD", bg: "#010402", dim: "#237a35", main: "#2bff6a", hot: "#c8ffd0", bloom: "#10ff55" },
  { id: "ICE",     bg: "#01050c", dim: "#2b6390", main: "#3ab8ff", hot: "#c2f2ff", bloom: "#1e86ff" },
  { id: "PURPLE",  bg: "#050109", dim: "#6a2f9a", main: "#c46bff", hot: "#eecbff", bloom: "#9a3fff" },
  { id: "WHITE",   bg: "#02050b", dim: "#5c7d8e", main: "#dff4ff", hot: "#ffffff", bloom: "#7ad0ff" },
  { id: "VFD GREEN", bg: "#010402", dim: "#1d6f6a", main: "#5ff0e0", hot: "#d6fffb", bloom: "#22d8c8" },
];

const $ = (id) => document.getElementById(id);
const canvas = $("screen"), ctx = canvas.getContext("2d");

let wasm = null, mem = null, dev = null, W = 0, H = 0;
let bands, peaks, bandsL, bandsR, wave, wfHist, waveHist;

function rgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a, b, t) {
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t));
}

// Device byte (0..255) -> colour. The core has already decided how bright each
// dot is for this panel; all that remains is choosing a hue for it.
function dotColour(v, scheme) {
  const dim = rgb(scheme.dim), main = rgb(scheme.main), hot = rgb(scheme.hot);
  const t = v / 255;
  return t <= 0.5 ? mix(dim, main, t / 0.5) : mix(main, hot, (t - 0.5) / 0.5);
}

function writeStr(s) {
  const p = wasm.deck_str_ptr();
  const bytes = new TextEncoder().encode(s);
  const buf = new Uint8Array(mem.buffer, p, 256);
  buf.set(bytes.subarray(0, 255));
  buf[Math.min(bytes.length, 255)] = 0;
}

function reconfigure() {
  const t = TARGETS.find((x) => x.id === $("target").value);
  const levels = Number($("levels").value);
  const colourCapable = levels > 16;
  wasm.deck_config(t.w, t.h, levels, colourCapable ? 1 : 0);
  W = wasm.deck_w(); H = wasm.deck_h();
  dev = new Uint8Array(mem.buffer, wasm.deck_dev_ptr(), W * H);
  const b = mem.buffer;
  bands    = new Float64Array(b, wasm.deck_bands_ptr(), 13);
  peaks    = new Float64Array(b, wasm.deck_peaks_ptr(), 13);
  bandsL   = new Float64Array(b, wasm.deck_bandsl_ptr(), 13);
  bandsR   = new Float64Array(b, wasm.deck_bandsr_ptr(), 13);
  wave     = new Float64Array(b, wasm.deck_wave_ptr(), 96);
  wfHist   = new Float32Array(b, wasm.deck_wf_ptr(), 12 * 32);
  waveHist = new Float64Array(b, wasm.deck_wavehist_ptr(), 2 * 96);
  wasm.deck_set_counts(12, 2);
  wasm.deck_set_scope_gain(3.0);

  const zoom = Number($("zoom").value);
  canvas.width = W * zoom;
  canvas.height = H * zoom;
  $("scheme").disabled = !colourCapable;

  rebuildAppearance();
  trackLoaded = false;
  oceanReady = false;

  const tier = ["STRIP", "CLASSIC", "LARGE"][wasm.deck_tier_of()];
  $("readout").textContent =
    `${W}×${H} dots · ${levels} level${levels > 1 ? "s" : ""} · tier ${tier} · ` +
    `${(W * H / 1000).toFixed(1)}k dots · zoom ${zoom}×`;
}

// --- content -------------------------------------------------------------
// Plausible-looking analysis data so every screen has something to chew on.
function feed(t) {
  for (let b = 0; b < 13; b++) {
    const v = 0.5 + 0.45 * Math.sin(t / 520 + b * 0.7) * Math.sin(t / 1730 + b);
    bands[b] = Math.max(0, Math.min(1, v));
    peaks[b] = Math.max(0, Math.min(1, v + 0.12));
    bandsL[b] = Math.max(0, Math.min(1, v * (0.7 + 0.3 * Math.sin(t / 900))));
    bandsR[b] = Math.max(0, Math.min(1, v * (0.7 + 0.3 * Math.cos(t / 900))));
  }
  for (let i = 0; i < 96; i++) {
    const p = i / 96;
    wave[i] = Math.sin(p * 18 + t / 190) * 0.55 * Math.sin(t / 1400 + p * 3);
    waveHist[i] = wave[i] * 0.8;
    waveHist[96 + i] = wave[i] * 0.6;
  }
  wasm.deck_set_vu(0.5 + 0.42 * Math.sin(t / 640), 0.5 + 0.42 * Math.sin(t / 710 + 1));
  wasm.deck_set_clip(Math.sin(t / 2600) > 0.85 ? 1 : 0);
  for (let r = 0; r < 12; r++)
    for (let c = 0; c < 32; c++)
      wfHist[r * 32 + c] =
        Math.max(0, 0.55 + 0.45 * Math.sin(c / 3.1 + t / 700 - r * 0.45) *
                              Math.cos(r * 0.6 + t / 2100));
}

// A canned track so the metadata screens have something real to show.
const TRACK = {
  title: "Hallelujah (Live At The Beacon Theatre)",
  artist: "Jeff Buckley", album: "Grace", app: "SPOTIFY",
  duration: 414,
  lyrics: [
    [0, ""], [4, "Well I heard there was a secret chord"],
    [9.5, "That David played and it pleased the Lord"],
    [15, "But you don\u2019t really care for music, do you?"],
    [21, "It goes like this, the fourth, the fifth"],
    [26, "The minor fall, the major lift"],
    [31, "The baffled king composing hallelujah"],
    [38, ""], [42, "Hallelujah"], [46, "Hallelujah"],
    [50, "Hallelujah"], [54, "Hallelujah"],
  ],
};

let trackLoaded = false;
function loadTrack() {
  writeStr(TRACK.title);  wasm.deck_set_title();
  writeStr(TRACK.artist); wasm.deck_set_artist();
  writeStr(TRACK.album);  wasm.deck_set_album();
  writeStr(TRACK.app);    wasm.deck_set_app();
  wasm.deck_set_lyric_state(2 /* ok */, 1 /* synced */, 0);
  wasm.deck_lyrics_clear();
  for (const [t, text] of TRACK.lyrics) { writeStr(text); wasm.deck_lyrics_push(t, 30); }

  // A stand-in sleeve: luminance written into wasm memory, dithered by the
  // core — the same call the firmware makes after decoding a JPEG.
  const S = Math.min(H, 128);
  const lum = new Uint8Array(mem.buffer, wasm.deck_lum_ptr(), S * S);
  for (let y = 0; y < S; y++)
    for (let x = 0; x < S; x++) {
      const dx = x / S - 0.5, dy = y / S - 0.5;
      const r = Math.sqrt(dx * dx + dy * dy);
      const ring = r < 0.09 ? 235 : r < 0.34 ? 20 : 40 + 200 * (1 - r);
      lum[y * S + x] = Math.max(0, Math.min(255, Math.round(ring)));
    }
  wasm.deck_make_art(S);
  wasm.deck_scroll_reset();
  trackLoaded = true;
}

const SCREENS = {
  spectrum:  ["SPECTRUM ANALYZER", () => wasm.deck_render_spectrum()],
  mirror:    ["MIRROR SPECTRUM",   () => wasm.deck_render_mirror()],
  scope:     ["OSCILLOSCOPE",      () => wasm.deck_render_scope()],
  city:      ["CITYSCAPE EQ",      () => wasm.deck_render_city()],
  waterfall: ["WATERFALL",         () => wasm.deck_render_waterfall()],
  vu:        ["VU METER",          () => wasm.deck_render_vu()],
  "3d":      ["3D SPECTRUM",       () => wasm.deck_render_3d()],
};

// The metadata screens own the whole panel, so they draw no label of their own.
let oceanReady = false;
const META_SCREENS = {
  ocean: (t) => {
    if (!oceanReady) { wasm.deck_ocean_init(); oceanReady = true; }
    wasm.deck_render_ocean(Math.floor(t / 100));   // 10 movie fps
  },
  cover:  (t) => { wasm.deck_set_transport((t / 1000) % TRACK.duration, TRACK.duration, 1);
                   wasm.deck_render_cover(16.7); },
  lyrics: (t) => { wasm.deck_set_transport((t / 1000) % 60, TRACK.duration, 1);
                   wasm.deck_render_lyrics(t); },
};

function drawScreen(key, t) {
  feed(t);
  const [label, run] = SCREENS[key];
  run();
  writeStr(label);
  wasm.deck_draw_text3(2, 0, wasm.deck_text_i(1));
}

function drawText() {
  writeStr("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
  wasm.deck_draw_text5(2, 1, 2, 1);
  writeStr("0123456789 .,:;-'\"!?()/&+=");
  wasm.deck_draw_text5(2, 10, 2, 1);
  writeStr("DIM · MAIN · HOT · ♪");
  wasm.deck_draw_text5(2, 19, wasm.deck_text_i(1), 1);
  writeStr("HALLELUJAH");
  wasm.deck_draw_text5(2, 29, 3, H >= 60 ? 2 : 1);
  writeStr("JEFF BUCKLEY · GRACE");
  wasm.deck_draw_text3(2, H - 7, wasm.deck_text_i(1));
}

// Each intensity as a solid block, so you can see exactly how a target's
// output stage separates them — or fails to.
function drawRamp() {
  const labels = ["OFF", "DIM", "MAIN", "HOT", "CLIP"];
  const bw = Math.floor(W / 5);
  for (let i = 0; i < 5; i++)
    for (let y = 10; y < H - 10; y++)
      for (let x = 0; x < bw - 4; x++) wasm.deck_dot(i * bw + x + 2, y, i);
  for (let i = 0; i < 5; i++) {
    writeStr(labels[i]);
    wasm.deck_draw_text3(i * bw + 2, H - 8, wasm.deck_text_i(i === 0 ? 1 : i));
  }
}

// --- panel appearance ----------------------------------------------------
// A lit dot on real glass is not a flat square: it blooms into its neighbours,
// which is most of why dim text stays readable. The legacy deck models that
// with a haloed sprite per intensity, so the preview does the same — otherwise
// low intensities look far weaker here than on the panel.
const BUCKETS = 16;
let sprites = null, unlitLayer = null;

function buildSprites() {
  const scheme = SCHEMES[Number($("scheme").value) || 0];
  const zoom = Number($("zoom").value);
  const round = $("shape").value === "round";
  const S = Math.max(6, Math.round(zoom * 2.6));      // room for the halo
  const c = S / 2;

  sprites = [];
  for (let b = 0; b < BUCKETS; b++) {
    const cv = document.createElement("canvas");
    cv.width = cv.height = S;
    const g = cv.getContext("2d");
    const v = Math.round((b + 0.5) * 255 / BUCKETS);
    const [r, gg, bb] = dotColour(v, scheme);
    const [hr, hg, hb] = rgb(scheme.bloom);

    // halo first, strength rising with intensity as the legacy sprites do
    const alpha = 0.10 + 0.12 * (b / (BUCKETS - 1));
    const rad = g.createRadialGradient(c, c, zoom * 0.15, c, c, c);
    rad.addColorStop(0, `rgba(${hr},${hg},${hb},${alpha})`);
    rad.addColorStop(1, `rgba(${hr},${hg},${hb},0)`);
    g.fillStyle = rad;
    g.fillRect(0, 0, S, S);

    g.fillStyle = `rgb(${r},${gg},${bb})`;
    if (round) {
      const rr = zoom * 0.46;
      const sh = g.createRadialGradient(c - rr * 0.35, c - rr * 0.35, rr * 0.15, c, c, rr);
      sh.addColorStop(0, "#ffffff");
      sh.addColorStop(0.28, `rgb(${r},${gg},${bb})`);
      sh.addColorStop(1, `rgb(${Math.round(r * 0.45)},${Math.round(gg * 0.45)},${Math.round(bb * 0.45)})`);
      g.fillStyle = sh;
      g.beginPath();
      g.arc(c, c, rr, 0, 6.2832);
      g.fill();
    } else {
      const s = Math.max(1, zoom * 0.82);
      g.beginPath();
      g.roundRect(c - s / 2, c - s / 2, s, s, Math.max(0.5, zoom * 0.14));
      g.fill();
    }
    sprites.push(cv);
  }
}

function buildUnlit() {
  const scheme = SCHEMES[Number($("scheme").value) || 0];
  const zoom = Number($("zoom").value);
  unlitLayer = document.createElement("canvas");
  unlitLayer.width = canvas.width;
  unlitLayer.height = canvas.height;
  const g = unlitLayer.getContext("2d");
  g.fillStyle = scheme.bg;
  g.fillRect(0, 0, unlitLayer.width, unlitLayer.height);
  g.fillStyle = "rgba(255,255,255,0.045)";
  const r = Math.max(0.5, zoom * 0.26);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      g.beginPath();
      g.arc(x * zoom + zoom / 2, y * zoom + zoom / 2, r, 0, 6.2832);
      g.fill();
    }
}

function rebuildAppearance() { buildSprites(); buildUnlit(); }

// --- loop ----------------------------------------------------------------
function frame(t) {
  wasm.deck_begin();
  const mode = $("content").value;
  if (META_SCREENS[mode]) { if (!trackLoaded) loadTrack(); feed(t); META_SCREENS[mode](t); }
  else if (SCREENS[mode]) drawScreen(mode, t);
  else if (mode === "text") drawText();
  else drawRamp();
  wasm.deck_emit();

  const zoom = Number($("zoom").value);
  const off = Math.round((sprites[0].width - zoom) / 2);

  ctx.drawImage(unlitLayer, 0, 0);
  for (let y = 0; y < H; y++) {
    const row = y * W;
    for (let x = 0; x < W; x++) {
      const v = dev[row + x];
      if (!v) continue;
      const b = Math.min(BUCKETS - 1, v >> 4);
      ctx.drawImage(sprites[b], x * zoom - off, y * zoom - off);
    }
  }

  requestAnimationFrame(frame);
}

// --- boot ----------------------------------------------------------------
(async () => {
  TARGETS.forEach((t) => $("target").add(new Option(t.name, t.id)));
  SCHEMES.forEach((s, i) => $("scheme").add(new Option(s.id, String(i))));

  const res = await WebAssembly.instantiateStreaming(fetch("deck.wasm"), {});
  wasm = res.instance.exports;
  mem = wasm.memory;

  for (const id of ["target", "levels", "zoom"])
    $(id).addEventListener("change", reconfigure);
  for (const id of ["scheme", "shape"])
    $(id).addEventListener("change", rebuildAppearance);

  // sensible defaults per target: a real panel's level count
  $("target").addEventListener("change", () => {
    const t = TARGETS.find((x) => x.id === $("target").value);
    $("levels").value = String(t.levels);
    reconfigure();
  });

  reconfigure();
  requestAnimationFrame(frame);
})();
