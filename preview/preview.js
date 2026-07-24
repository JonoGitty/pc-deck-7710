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

  const zoom = Number($("zoom").value);
  canvas.width = W * zoom;
  canvas.height = H * zoom;
  $("scheme").disabled = !colourCapable;

  const tier = ["STRIP", "CLASSIC", "LARGE"][wasm.deck_tier_of()];
  $("readout").textContent =
    `${W}×${H} dots · ${levels} level${levels > 1 ? "s" : ""} · tier ${tier} · ` +
    `${(W * H / 1000).toFixed(1)}k dots · zoom ${zoom}×`;
}

// --- content -------------------------------------------------------------
function drawSpectrum(t) {
  for (let b = 0; b < 13; b++) {
    const v = 0.5 + 0.45 * Math.sin(t / 520 + b * 0.7) * Math.sin(t / 1730 + b);
    wasm.deck_set_band(b, Math.max(0, Math.min(1, v)));
    wasm.deck_set_peak(b, Math.max(0, Math.min(1, v + 0.12)));
  }
  wasm.deck_render_spectrum();
  writeStr("SPECTRUM ANALYZER");
  wasm.deck_draw_text3(2, 0, 1);
}

function drawText() {
  writeStr("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
  wasm.deck_draw_text5(2, 1, 2, 1);
  writeStr("0123456789 .,:;-'\"!?()/&+=");
  wasm.deck_draw_text5(2, 10, 2, 1);
  writeStr("DIM · MAIN · HOT · ♪");
  wasm.deck_draw_text5(2, 19, 1, 1);
  writeStr("HALLELUJAH");
  wasm.deck_draw_text5(2, 29, 3, H >= 60 ? 2 : 1);
  writeStr("JEFF BUCKLEY · GRACE");
  wasm.deck_draw_text3(2, H - 7, 1);
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
    wasm.deck_draw_text3(i * bw + 2, H - 8, i === 0 ? 1 : i);
  }
}

// --- loop ----------------------------------------------------------------
function frame(t) {
  wasm.deck_begin();
  const mode = $("content").value;
  if (mode === "spectrum") drawSpectrum(t);
  else if (mode === "text") drawText();
  else drawRamp();
  wasm.deck_emit();

  const scheme = SCHEMES[Number($("scheme").value) || 0];
  const zoom = Number($("zoom").value);
  const round = $("shape").value === "round";

  ctx.fillStyle = scheme.bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // unlit dot grid, so dark areas still read as a panel rather than a void
  ctx.fillStyle = "rgba(255,255,255,0.035)";
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const r = zoom * 0.28;
      ctx.beginPath();
      ctx.arc(x * zoom + zoom / 2, y * zoom + zoom / 2, r, 0, 6.2832);
      ctx.fill();
    }

  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const v = dev[y * W + x];
      if (!v) continue;
      const [r, g, b] = dotColour(v, scheme);
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      const cx = x * zoom + zoom / 2, cy = y * zoom + zoom / 2;
      if (round) {
        ctx.beginPath();
        ctx.arc(cx, cy, zoom * 0.42, 0, 6.2832);
        ctx.fill();
      } else {
        ctx.fillRect(x * zoom, y * zoom, Math.max(1, zoom - 1), Math.max(1, zoom - 1));
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

  // sensible defaults per target: a real panel's level count
  $("target").addEventListener("change", () => {
    const t = TARGETS.find((x) => x.id === $("target").value);
    $("levels").value = String(t.levels);
    reconfigure();
  });

  reconfigure();
  requestAnimationFrame(frame);
})();
