// PC-DECK 7710 — faceplate brain: phosphor renderer, ballistics, state machine.
"use strict";

const GRID_W = 192, GRID_H = 48, CELL = 4, PAD = 8;
const LYRIC_CELLS = 30;         // 5x7 glyphs at 6 px pitch, with a margin

// Sol's VFD palette
const PAL = {
  bg: "#020403",
  unlit: "#171008",
  dim: "#9A5518",
  main: "#F3A52B",
  hot: "#FFD978",
  bloom: "#FF7A16",
  clip: "#FF4938",
};

const fb = new Uint8Array(GRID_W * GRID_H);

function setDot(f, x, y, i) {
  if (x < 0 || x >= GRID_W || y < 0 || y >= GRID_H) return;
  const idx = y * GRID_W + x;
  if (i > f[idx]) f[idx] = i;
}

// ---------------------------------------------------------------- renderer
const canvas = document.getElementById("vfd");
canvas.width = GRID_W * CELL + PAD * 2;
canvas.height = GRID_H * CELL + PAD * 2;
const ctx = canvas.getContext("2d");

function makeSprite(color, halo, haloAlpha, coreScale, shape) {
  const c = document.createElement("canvas");
  c.width = c.height = 10;
  const g = c.getContext("2d");
  if (halo) {
    const rg = g.createRadialGradient(5, 5, 0.5, 5, 5, 5);
    rg.addColorStop(0, halo);
    rg.addColorStop(1, rgbaHex(halo, 0));      // fade to same hue, per colour scheme
    g.globalAlpha = haloAlpha;
    g.fillStyle = rg;
    g.fillRect(0, 0, 10, 10);
    g.globalAlpha = 1;
  }
  if (shape === "bulb-off") {
    g.fillStyle = color;
    g.beginPath();
    g.arc(5, 5, 1.7, 0, 6.2832);
    g.fill();
  } else if (shape === "bulb") {
    // round LED bulb with spherical shading — the LED-sign look, at OEM dot
    // pitch: a radial gradient from a white highlight through the base colour
    // to a shaded rim
    const r = 2.1 * (coreScale || 1);
    const rg = g.createRadialGradient(4.2, 4.2, r * 0.15, 5, 5, r);
    rg.addColorStop(0, "#ffffff");
    rg.addColorStop(0.25, color);
    rg.addColorStop(1, shadeHex(color, 0.45));
    g.fillStyle = rg;
    g.beginPath();
    g.arc(5, 5, r, 0, 6.2832);
    g.fill();
  } else {
    g.fillStyle = color;
    const s = 3 * (coreScale || 1);
    g.beginPath();
    g.roundRect(5 - s / 2, 5 - s / 2, s, s, 0.8);
    g.fill();
  }
  return c;
}

function shadeHex(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.round(((n >> 16) & 255) * f), g = Math.round(((n >> 8) & 255) * f),
        b = Math.round((n & 255) * f);
  return `rgb(${r},${g},${b})`;
}
function rgbaHex(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

// Colour schemes — authentic head-unit illumination colours (Pioneer let you
// set the display colour), plus round-LED-bulb variants.
const STYLES = [
  { id: "AMBER",     shape: "square", pal: PAL },
  { id: "PIONEER RED", shape: "square", pal: {
      bg: "#050101", unlit: "#1c0707", dim: "#8a1f1f", main: "#ff2e2e",
      hot: "#ff9a7a", bloom: "#ff2a00", clip: "#ffd24a" } },
  { id: "EMERALD",   shape: "square", pal: {
      bg: "#010402", unlit: "#08170c", dim: "#237a35", main: "#2bff6a",
      hot: "#c8ffd0", bloom: "#10ff55", clip: "#ff4938" } },
  { id: "ICE BLUE",  shape: "square", pal: {
      bg: "#01050c", unlit: "#0a1622", dim: "#2b6390", main: "#3ab8ff",
      hot: "#c2f2ff", bloom: "#1e86ff", clip: "#ff5a45" } },
  { id: "PURPLE",    shape: "square", pal: {
      bg: "#050109", unlit: "#160a20", dim: "#6a2f9a", main: "#c46bff",
      hot: "#eecbff", bloom: "#9a3fff", clip: "#ff5a45" } },
  { id: "WHITE",     shape: "square", pal: {
      bg: "#02050b", unlit: "#101720", dim: "#5c7d8e", main: "#dff4ff",
      hot: "#ffffff", bloom: "#7ad0ff", clip: "#ff5a45" } },
  { id: "LED AMBER", shape: "bulb", pal: PAL },
  { id: "LED LIME",  shape: "bulb", pal: {
      bg: "#04050a", unlit: "#0e1018", dim: "#3f5c0b", main: "#c6ff1a",
      hot: "#eaffff", bloom: "#12e0ff", clip: "#ff1a8c" } },
];

let SPRITES = null;
const unlitLayer = document.createElement("canvas");
unlitLayer.width = canvas.width; unlitLayer.height = canvas.height;

function buildStyle(i) {
  const st = STYLES[i];
  const offShape = st.shape === "bulb" ? "bulb-off" : undefined;
  SPRITES = {
    0: makeSprite(st.pal.unlit, null, 0, 0.9, offShape),
    1: makeSprite(st.pal.dim, st.pal.bloom, 0.10, 0.95, st.shape),
    2: makeSprite(st.pal.main, st.pal.bloom, 0.16, 1, st.shape),
    3: makeSprite(st.pal.hot, st.pal.bloom, 0.2, 1, st.shape),
    4: makeSprite(st.pal.clip, st.pal.clip, 0.18, 1, st.shape),
  };
  const g = unlitLayer.getContext("2d");
  g.fillStyle = st.pal.bg;
  g.fillRect(0, 0, unlitLayer.width, unlitLayer.height);
  for (let y = 0; y < GRID_H; y++)
    for (let x = 0; x < GRID_W; x++)
      g.drawImage(SPRITES[0], PAD + x * CELL - 3, PAD + y * CELL - 3);
}
buildStyle(0);

function render() {
  ctx.drawImage(unlitLayer, 0, 0);
  ctx.globalAlpha = UI.bright;
  for (let y = 0; y < GRID_H; y++) {
    const row = y * GRID_W;
    for (let x = 0; x < GRID_W; x++) {
      const i = fb[row + x];
      if (i) ctx.drawImage(SPRITES[i], PAD + x * CELL - 3, PAD + y * CELL - 3);
    }
  }
  ctx.globalAlpha = 1;
}

// ---------------------------------------------------------------- state
const A = {                     // raw targets from server
  spec: new Array(13).fill(0), specL: new Array(13).fill(0), specR: new Array(13).fill(0),
  rmsL: -70, rmsR: -70, wave: new Array(96).fill(0), clip: false,
  lastMsg: 0,
};
const V = {                     // smoothed values the visualizers read
  bands: new Array(13).fill(0), peaks: new Array(13).fill(0),
  peakHold: new Array(13).fill(0), peakFall: new Array(13).fill(0),
  bandsL: new Array(13).fill(0), bandsR: new Array(13).fill(0),
  vuL: 0, vuR: 0, _velL: 0, _velR: 0,
  wave: new Array(96).fill(0), waveHist: [], wfHist: [], scopeGain: 1,
  bassAvg: 0, hfAvg: 0, rms01: 0, clip: false, oceanTick: 0,
};
const META = {
  title: "", artist: "", album: "", app: "", status: "stopped",
  artFb: null,                  // 40x40 dither for the NOW PLAYING interstitial
  artBig: null,                 // 48x48 dither for the full-time cover screen
};
// playback head, from SMTC once a second; interpolated between updates
const POS = { base: 0, at: 0, duration: 0, status: "stopped" };
// lyrics for the current track, wrapped into display rows
const LYR = {
  key: "", state: "idle",       // idle | searching | ok | none
  synced: false, lines: [],     // [[seconds|null, text], ...]
  rows: [], rowStart: [],       // wrapped rows + first row of each lyric line
  offset: 0,                    // manual sync trim, ms
};
const UI = {
  mode: 0, illum: 0, loud: false, secondClock: false, bright: 1, forceSaver: false,
  state: "live",                // live | simplified | saver | nowplaying | nosignal
  silentMs: 0, npUntil: 0,
  flashText: "", flashUntil: 0,
  wipeStart: 0,                 // horizontal wipe on state return
  scroll: { offset: 0, phase: 0, t: 0 },
  coverScroll: { offset: 0, phase: 0, t: 0 },
  connected: false,
  demo: false, demoNext: 0,     // attract loop: auto-cycle every display
};

// ---------------------------------------------------------------- websocket
function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { UI.connected = true; };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "audio") {
      Object.assign(A, { spec: m.spec, specL: m.specL, specR: m.specR,
                         rmsL: m.rmsL, rmsR: m.rmsR, wave: m.wave, clip: m.clip });
      A.lastMsg = performance.now();
    } else if (m.type === "meta") {
      const title = deckText(m.title), artist = deckText(m.artist);
      const newTrack = title && (title !== META.title || artist !== META.artist);
      Object.assign(META, { title, artist, album: deckText(m.album),
                            app: deckText(m.app), status: m.status });
      document.title = m.title ? `${m.title} — PC·DECK 7710` : "PC·DECK 7710";
      if (m.art) ditherArt(m.art);
      else if (newTrack) { META.artFb = null; META.artBig = null; }
      if (newTrack) {
        UI.scroll = { offset: 0, phase: 0, t: 0 };
        UI.coverScroll = { offset: 0, phase: 0, t: 0 };
        if (UI.state === "live" || UI.state === "nowplaying") {
          UI.state = "nowplaying";
          UI.npUntil = performance.now() + 2300;
        }
      }
    } else if (m.type === "pos") {
      POS.base = m.position; POS.at = performance.now();
      POS.duration = m.duration; POS.status = m.status;
    } else if (m.type === "lyrics") {
      setLyrics(m);
    }
  };
  ws.onclose = () => { UI.connected = false; setTimeout(connect, 1500); };
  ws.onerror = () => ws.close();
}
connect();

// ---------------------------------------------------------------- art dither
const BAYER4 = [
  [0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5],
];
function ditherSquare(img, S) {
  const c = document.createElement("canvas");
  c.width = c.height = S;
  const g = c.getContext("2d");
  const m = Math.min(img.width, img.height);
  g.drawImage(img, (img.width - m) / 2, (img.height - m) / 2, m, m, 0, 0, S, S);
  const d = g.getImageData(0, 0, S, S).data;
  const out = new Uint8Array(S * S);
  // contrast-stretch luminance, then 4x4 ordered dither into 4 amber levels
  let lo = 255, hi = 0;
  const lum = new Float32Array(S * S);
  for (let i = 0; i < S * S; i++) {
    const l = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
    lum[i] = l; if (l < lo) lo = l; if (l > hi) hi = l;
  }
  const span = Math.max(30, hi - lo);
  for (let y = 0; y < S; y++)
    for (let x = 0; x < S; x++) {
      const v = ((lum[y * S + x] - lo) / span) * 3.999;
      const t = (BAYER4[y & 3][x & 3] + 0.5) / 16;
      out[y * S + x] = Math.max(0, Math.min(3, Math.floor(v + t - 0.5)));
    }
  return out;
}

function ditherArt(dataUrl) {
  const img = new Image();
  img.onload = () => {
    META.artFb = ditherSquare(img, 40);      // interstitial, beside the text
    META.artBig = ditherSquare(img, 48);     // cover screen, full panel height
  };
  img.src = dataUrl;
}

// ---------------------------------------------------------------- text
// The character ROM is 5x7 uppercase ASCII, so fold everything else down to it:
// accents stripped, typographic punctuation squared off. Without this, half the
// apostrophes in a lyric sheet come back as "?".
function deckText(s) {
  return (s || "")
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")
    // Letters with no Unicode decomposition — NFKD leaves them alone, so
    // without this they fall through to a space and "Ágætis" reads "Ag tis".
    .replace(/Æ/g, "AE").replace(/æ/g, "ae")
    .replace(/Œ/g, "OE").replace(/œ/g, "oe")
    .replace(/Ø/g, "O").replace(/ø/g, "o")
    .replace(/Ð/g, "D").replace(/ð/g, "d")
    .replace(/Đ/g, "D").replace(/đ/g, "d")
    .replace(/Þ/g, "TH").replace(/þ/g, "th")
    .replace(/ß/g, "ss")
    .replace(/Ł/g, "L").replace(/ł/g, "l")
    .replace(/Ħ/g, "H").replace(/ħ/g, "h")
    .replace(/Ŋ/g, "NG").replace(/ŋ/g, "ng")
    .replace(/Ŧ/g, "T").replace(/ŧ/g, "t")
    .replace(/ı/g, "i").replace(/ĸ/g, "k")
    .replace(/[‘’ʼ′]/g, "'")
    .replace(/[“”″]/g, '"')
    .replace(/[–—−]/g, "-")
    .replace(/…/g, "...")
    .replace(/[^\x20-\x7e]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// ---------------------------------------------------------------- lyrics
// Wrap each lyric line to the display width, keeping a map back to the line it
// came from so the "current" line highlights across all of its wrapped rows.
function wrapLyric(text, cells) {
  if (!text) return [""];
  const words = text.split(/\s+/).filter(Boolean);
  const rows = [];
  let line = "";
  for (let w of words) {
    while (w.length > cells) {                 // a single monster word
      if (line) { rows.push(line); line = ""; }
      rows.push(w.slice(0, cells));
      w = w.slice(cells);
    }
    if (!line) line = w;
    else if (line.length + 1 + w.length <= cells) line += " " + w;
    else { rows.push(line); line = w; }
  }
  if (line) rows.push(line);
  return rows.length ? rows : [""];
}

function setLyrics(m) {
  LYR.key = m.key; LYR.state = m.state; LYR.synced = m.synced;
  LYR.lines = m.lines || [];
  LYR.offset = 0;
  LYR.rows = []; LYR.rowStart = [];
  LYR.lines.forEach((ln, i) => {
    LYR.rowStart[i] = LYR.rows.length;
    for (const text of wrapLyric(deckText(ln[1]), LYRIC_CELLS)) LYR.rows.push({ i, text });
  });
}

// Binary search: index of the last lyric line whose stamp has passed.
function lyricIndexAt(t) {
  let lo = 0, hi = LYR.lines.length - 1, res = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (LYR.lines[mid][0] <= t) { res = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return res;
}

// Seconds into the current track, interpolated between SMTC updates.
function trackPos(now) {
  if (!POS.at) return 0;
  const t = POS.status === "playing" ? POS.base + (now - POS.at) / 1000 : POS.base;
  return POS.duration ? Math.min(t, POS.duration) : t;
}

function trackKey() { return `${META.title}\x1f${META.artist}`; }

// ---------------------------------------------------------------- ballistics
function stepAnalysis(dt, now) {
  const stale = now - A.lastMsg > 1500;
  const kAtt = 1 - Math.exp(-dt / 25);
  for (let b = 0; b < 13; b++) {
    const rel = 1 - Math.exp(-dt / (260 - b * 6));    // bass lingers a touch longer
    let t = stale ? 0 : A.spec[b];
    if (UI.loud && b < 3) t = Math.min(1, t * 1.25);
    const k = t > V.bands[b] ? kAtt : rel;
    V.bands[b] += (t - V.bands[b]) * k;
    V.bandsL[b] += ((stale ? 0 : A.specL[b]) - V.bandsL[b]) * k;
    V.bandsR[b] += ((stale ? 0 : A.specR[b]) - V.bandsR[b]) * k;
    // stepped peak-hold
    if (V.bands[b] >= V.peaks[b]) {
      V.peaks[b] = V.bands[b];
      V.peakHold[b] = now + 550;
    } else if (now > V.peakHold[b] && now > V.peakFall[b]) {
      V.peaks[b] = Math.max(0, V.peaks[b] - 0.125);
      V.peakFall[b] = now + 72;
    }
  }
  // VU needle spring (underdamped: real recoil)
  const s = dt / 1000;
  for (const ch of ["L", "R"]) {
    const raw = ch === "L" ? A.rmsL : A.rmsR;
    const target = stale ? 0 : Math.max(0, Math.min(1, (raw + 40) / 43));
    const v = ch === "L" ? "vuL" : "vuR", vel = ch === "L" ? "_velL" : "_velR";
    V[vel] += ((target - V[v]) * 180 - V[vel] * 14) * s;
    V[v] = Math.max(0, Math.min(1.04, V[v] + V[vel] * s));
  }
  V.wave = stale ? V.wave.map(() => 0) : A.wave;
  V.clip = !stale && A.clip;
  V.bassAvg = (V.bands[0] + V.bands[1] + V.bands[2]) / 3;
  V.hfAvg = (V.bands[10] + V.bands[11] + V.bands[12]) / 3;
  V.rms01 = Math.max(0, Math.min(1, (Math.max(A.rmsL, A.rmsR) + 58) / 58));
  // scope slow AGC
  let pk = 0.04;
  for (const w of V.wave) pk = Math.max(pk, Math.abs(w));
  const tg = Math.max(1, Math.min(9, 0.85 / pk));
  V.scopeGain += (tg - V.scopeGain) * (1 - Math.exp(-dt / 1800));
}

let _histAcc = 0, _wfAcc = 0, _oceanAcc = 0;
function stepBuffers(dt) {
  _histAcc += dt;
  if (_histAcc > 90) {                       // scope persistence traces
    V.waveHist.unshift(V.wave.slice());
    if (V.waveHist.length > 2) V.waveHist.pop();
    _histAcc = 0;
  }
  _wfAcc += dt;
  if (_wfAcc > 100) {                        // waterfall rows at 10 Hz
    const row = new Float32Array(32);
    for (let c = 0; c < 32; c++) {
      const f = (c * 12) / 31, i = Math.min(11, Math.floor(f)), fr = f - i;
      row[c] = V.bands[i] * (1 - fr) + V.bands[i + 1] * fr;
    }
    V.wfHist.unshift(row);
    if (V.wfHist.length > 12) V.wfHist.pop();
    _wfAcc = 0;
  }
  _oceanAcc += dt;
  while (_oceanAcc >= 100) { V.oceanTick++; _oceanAcc -= 100; }
}

// ---------------------------------------------------------------- state machine
function stepState(dt, now) {
  const silent = Math.max(A.rmsL, A.rmsR) < -55 || now - A.lastMsg > 1500;
  UI.silentMs = silent ? UI.silentMs + dt : 0;
  if (!UI.connected) { UI.state = "nosignal"; return; }

  if (UI.forceSaver) { UI.state = "saver"; return; }
  if (UI.state === "nowplaying") {
    if (now < UI.npUntil) return;
    UI.state = "live"; UI.wipeStart = now;
    return;
  }
  if (UI.demo) {                                   // demo owns the display, silence or not
    if (UI.state !== "live") UI.wipeStart = now;
    UI.state = "live";
    return;
  }
  if (!silent) {
    if (UI.state !== "live") UI.wipeStart = now;   // hard wipe back in
    UI.state = "live";
  } else if (MODES[UI.mode].holdIdle) {
    // cover art / lyrics are about the track, not the audio: they stay up
    // through a pause instead of handing over to the clock and the dolphins
    if (UI.state !== "live") UI.wipeStart = now;
    UI.state = "live";
  } else if (UI.silentMs > 12000) {
    UI.state = "saver";
  } else if (UI.silentMs > 3000) {
    UI.state = "simplified";
  }
}

// ---------------------------------------------------------------- composition
function pad2(n) { return String(n).padStart(2, "0"); }
function clockStr(now) {
  const d = new Date();
  const colon = Math.floor(now / 500) % 2 === 0 ? ":" : " ";
  return `${pad2(d.getHours())}${colon}${pad2(d.getMinutes())}`;
}

function drawAnnunciators(now) {
  const src = META.app || (UI.connected ? "PC" : "----");
  drawText3(fb, 2, 0, src, 2);
  // play / pause lamp
  const px = 4 + textWidth3(src);
  if (META.status === "playing") {
    for (let r = 0; r < 5; r++) for (let c = 0; c < 3; c++)
      if ([4, 6, 7, 6, 4][r] & (4 >> c)) setDot(fb, px + c, r, 2);
  } else if (META.status === "paused" && Math.floor(now / 600) % 2 === 0) {
    for (let r = 0; r < 5; r++) { setDot(fb, px, r, 2); setDot(fb, px + 2, r, 2); }
  }
  drawText3(fb, 100, 0, "RPT", 1);
  drawText3(fb, 114, 0, "RDM", 1);
  drawText3(fb, 130, 0, "ST", UI.connected && META.status === "playing" ? 2 : 1);
  drawText3(fb, 140, 0, "DEMO", UI.demo ? 3 : 1);
  drawText3(fb, 158, 0, "LOUD", UI.loud ? 2 : 1);
  drawText3(fb, 176, 0, "OVER", V.clip ? 4 : 1);
}

function stepScroll(dt, text, cells) { return scrollText(UI.scroll, dt, text, cells); }

function scrollText(sc, dt, text, cells) {
  // hold 1.2s -> scroll 8 cells/s -> 5 blank cells -> pause -> repeat
  if (text.length <= cells) { sc.offset = 0; return text; }
  const loop = text + "     ";
  sc.t += dt;
  if (sc.phase === 0) {                       // holding
    if (sc.t > 1200) { sc.phase = 1; sc.t = 0; }
  } else {
    sc.offset = Math.floor(sc.t / 125);       // 8 cells/s
    if (sc.offset >= loop.length) { sc.phase = 0; sc.t = 0; sc.offset = 0; }
  }
  const s = loop + loop;
  return s.slice(sc.offset, sc.offset + cells);
}

function composeLive(dt, now) {
  const mode = MODES[UI.mode];
  const title = META.title || (META.status === "playing" ? "" : "PC DECK 7710");

  if (mode.big === "full") {
    mode.draw(fb, V, dt, now);
    if (now < UI.flashUntil) drawText3(fb, 2, 0, UI.flashText, 3);
    return;
  }
  drawAnnunciators(now);
  drawText5(fb, 2, 8, stepScroll(dt, title, 15), 2, 2);
  // secondary line: flash label > artist/clock
  let second = UI.secondClock ? clockStr(now) : (META.artist || "").slice(0, 20);
  if (now < UI.flashUntil) second = UI.flashText;
  if (!mode.big) {
    drawText5(fb, 2, 24, second.slice(0, 21), 1, 1);
    const tw = textWidth5(second.slice(0, 21), 1);
    if (!UI.secondClock) drawText3(fb, Math.max(tw + 8, 160), 25, clockStr(now), 1);
  } else if (now < UI.flashUntil) {
    drawText3(fb, 2, 25, UI.flashText, 3);
  }
  mode.draw(fb, V, dt, now);
}

function composeSimplified(now) {
  drawAnnunciators(now);
  const c = clockStr(now);
  drawText5(fb, Math.floor((GRID_W - textWidth5(c, 2)) / 2), 12, c, 2, 2);
  const t = (META.title || "PC DECK 7710").slice(0, 31);
  drawText5(fb, Math.floor((GRID_W - textWidth5(t, 1)) / 2), 34, t, 1, 1);
}

function composeNowPlaying(dt, now) {
  if (META.artFb) {
    for (let y = 0; y < 40; y++)
      for (let x = 0; x < 40; x++) {
        const v = META.artFb[y * 40 + x];
        if (v) setDot(fb, 2 + x, 4 + y, v);
      }
  }
  const tx = META.artFb ? 48 : 4;
  drawText3(fb, tx, 5, "NOW PLAYING", 1);
  drawText5(fb, tx, 14, (META.title || "").slice(0, Math.floor((GRID_W - tx) / 6)), 3, 1);
  drawText5(fb, tx, 25, (META.artist || "").slice(0, Math.floor((GRID_W - tx) / 6)), 2, 1);
  drawText3(fb, tx, 36, (META.album || "").toUpperCase().slice(0, 30), 1);
}

function composeNoSignal(now) {
  const t = "NO SIGNAL";
  drawText5(fb, Math.floor((GRID_W - textWidth5(t, 2)) / 2), 12, t, 2, 2);
  drawText3(fb, Math.floor((GRID_W - textWidth3("START THE DECK SERVER · PORT 7710")) / 2), 34,
            "START THE DECK SERVER · PORT 7710", 1);
}

// ---------------------------------------------------------------- main loop
let _last = performance.now();
function frame(now) {
  const dt = Math.min(100, now - _last);
  _last = now;
  stepAnalysis(dt, now);
  stepBuffers(dt);
  stepState(dt, now);

  // demo attract loop: advance on a timer
  if (UI.demo && UI.state === "live" && now > UI.demoNext) demoAdvance();

  fb.fill(0);
  if (UI.state === "nosignal") composeNoSignal(now);
  else if (UI.state === "saver") vizOcean(fb, V);
  else if (UI.state === "simplified") composeSimplified(now);
  else if (UI.state === "nowplaying") composeNowPlaying(dt, now);
  else composeLive(dt, now);

  // hard horizontal wipe reveal (columns, left to right)
  const wipeAge = now - UI.wipeStart;
  if (wipeAge < 160) {
    const edge = Math.floor((wipeAge / 160) * GRID_W);
    for (let y = 0; y < GRID_H; y++)
      for (let x = edge; x < GRID_W; x++) fb[y * GRID_W + x] = 0;
  }
  render();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// ---------------------------------------------------------------- controls
let _actx = null;
function beep(freq) {
  try {
    _actx = _actx || new AudioContext();
    const o = _actx.createOscillator(), g = _actx.createGain();
    o.type = "square"; o.frequency.value = freq || 2093;
    g.gain.value = 0.025;
    o.connect(g); g.connect(_actx.destination);
    o.start(); o.stop(_actx.currentTime + 0.03);
  } catch (e) { /* no audio permission yet */ }
}

function flash(text) { UI.flashText = text; UI.flashUntil = performance.now() + 1300; }

function updatePresets() {
  document.querySelectorAll(".preset").forEach((el, n) =>
    el.classList.toggle("lit", n === UI.mode));
}

function modeIndex(id) { return MODES.findIndex((m) => m.id === id); }

function nudgeLyrics(ms) {
  LYR.offset += ms;
  flash("LYRIC SYNC " + (LYR.offset >= 0 ? "+" : "-") +
        Math.abs(LYR.offset / 1000).toFixed(2) + "S");
}

function setMode(i) {
  UI.mode = ((i % MODES.length) + MODES.length) % MODES.length;
  UI.forceSaver = false;
  UI.demo = false;              // touching the deck exits the attract loop
  flash(MODES[UI.mode].name);
  updatePresets();
}

function demoAdvance() {
  UI.mode = (UI.mode + 1) % MODES.length;
  UI.wipeStart = performance.now();
  UI.demoNext = performance.now() + 12000;
  flash(MODES[UI.mode].name);
  updatePresets();
}

function toggleDemo() {
  UI.demo = !UI.demo;
  UI.forceSaver = false;
  if (UI.demo) UI.demoNext = performance.now() + 12000;
  flash(UI.demo ? "DEMO · ALL DISPLAYS" : "DEMO OFF");
}

function cycleColor(dir) {
  const n = STYLES.length;
  UI.illum = (UI.illum + (dir === -1 ? -1 : 1) + n) % n;
  buildStyle(UI.illum);
  flash("COLOR · " + STYLES[UI.illum].id);
}

function bind(id, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener("click", () => { beep(); fn(); });
}
bind("btn-disp", () => setMode(UI.mode + 1));
bind("btn-band", () => { UI.forceSaver = !UI.forceSaver; if (!UI.forceSaver) UI.wipeStart = performance.now(); });
bind("btn-eq", () => { UI.loud = !UI.loud; flash(UI.loud ? "LOUDNESS ON" : "LOUDNESS OFF"); });
bind("btn-audio", () => { UI.secondClock = !UI.secondClock; });
bind("btn-illum", cycleColor);
bind("btn-demo", toggleDemo);
bind("btn-art", () => setMode(modeIndex("COVER")));
bind("btn-lyr", () => setMode(modeIndex("LYRICS")));
bind("btn-src", () => flash("SOURCE · " + (META.app || "PC")));
document.querySelectorAll(".preset").forEach((el, n) =>
  el.addEventListener("click", () => { beep(1568); setMode(n); }));

const knob = document.getElementById("knob");
let _knobDeg = 0;
knob.addEventListener("wheel", (ev) => {
  ev.preventDefault();
  UI.bright = Math.max(0.45, Math.min(1, UI.bright - Math.sign(ev.deltaY) * 0.05));
  _knobDeg += Math.sign(ev.deltaY) * -14;
  knob.style.setProperty("--rot", _knobDeg + "deg");
}, { passive: false });
knob.addEventListener("click", () => { beep(); setMode(UI.mode + 1); });

const screenWrap = document.getElementById("screen-wrap");
const unit = document.getElementById("unit");

// Original fullscreen: the whole unit (faceplate + chrome). Double-click.
function toggleUnitFull() {
  if (document.fullscreenElement) document.exitFullscreen();
  else unit.requestFullscreen().catch(() => {});
}
screenWrap.addEventListener("dblclick", toggleUnitFull);

// TV mode: fullscreen the display ONLY (no bezel/buttons) — fills the
// Panasonic TX-32LXD70 with just the visuals. Separate control.
function toggleTV() {
  if (document.fullscreenElement) document.exitFullscreen();
  else screenWrap.requestFullscreen().catch(() => {});
}
bind("btn-tv", toggleTV);

addEventListener("keydown", (ev) => {
  if (ev.key === "d" || ev.key === "D") { beep(); setMode(UI.mode + 1); }
  if (ev.key === "b" || ev.key === "B") { beep(); UI.forceSaver = !UI.forceSaver; }
  if (ev.key === "i" || ev.key === "I") { beep(); cycleColor(1); }
  if (ev.key === "c" || ev.key === "C") { beep(); cycleColor(1); }
  if (ev.key === "m" || ev.key === "M") { beep(); toggleDemo(); }
  if (ev.key === "t" || ev.key === "T") { beep(); toggleTV(); }
  if (ev.key === "f" || ev.key === "F") { beep(); toggleUnitFull(); }
  if (ev.key === "a" || ev.key === "A") { beep(1568); setMode(modeIndex("COVER")); }
  if (ev.key === "l" || ev.key === "L") { beep(1568); setMode(modeIndex("LYRICS")); }
  if (ev.key === "[") { nudgeLyrics(-250); }        // lyrics running early: hold back
  if (ev.key === "]") { nudgeLyrics(250); }         // lyrics running late: pull forward
  if (ev.key >= "1" && ev.key <= "9") { beep(1568); setMode(Number(ev.key) - 1); }
  if (ev.key === "0") { beep(1568); setMode(9); }
});
