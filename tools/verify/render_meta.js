// Reference side for the cover art and lyrics screens.
//
// These read META/POS/LYR/UI globals and helpers that live in app.js, so the
// harness cuts the helpers out by brace matching and supplies the globals.
// vizCover/vizLyrics themselves come from viz.js unmodified.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const W = 192, H = 48;
const ROOT = path.join(__dirname, "..", "..");
const px = new Uint8Array(W * H);
const appSrc = fs.readFileSync(path.join(ROOT, "legacy", "web", "app.js"), "utf8");

function extract(name) {
  const start = appSrc.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`${name} not found`);
  let depth = 0;
  for (let j = appSrc.indexOf("{", start); j < appSrc.length; j++) {
    if (appSrc[j] === "{") depth++;
    else if (appSrc[j] === "}") { depth--; if (depth === 0) return appSrc.slice(start, j + 1); }
  }
  throw new Error(`unbalanced ${name}`);
}

const ctx = {
  GRID_W: W, GRID_H: H, LYRIC_CELLS: 30,
  setDot(f, x, y, i) {
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    const idx = y * W + x;
    if (i > f[idx]) f[idx] = i;
  },
  oceanFrame() {},
  META: {}, POS: {}, LYR: {}, UI: { coverScroll: { offset: 0, phase: 0, t: 0 } },
  // Position is supplied already interpolated, matching what the core is given.
  trackPos() { return ctx.POS.base; },
  clockStr() { return "00:00"; },   // never reached: cover cases all set a duration
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, "legacy", "web", "font.js"), "utf8"), ctx);
vm.runInContext([extract("deckText"), extract("wrapLyric"), extract("scrollText"),
                 extract("lyricIndexAt")].join("\n"), ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, "legacy", "web", "viz.js"), "utf8"), ctx);
vm.runInContext("globalThis.__cover = vizCover; globalThis.__lyrics = vizLyrics;", ctx);

function fnv1a(buf) {
  let h = 2166136261 >>> 0;
  for (const b of buf) { h = (h ^ b) >>> 0; h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}

// Deterministic art and bands, generated the same way as the C harness.
let s = 0;
const next = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };

const cases = fs.readFileSync(
  process.argv[2] || path.join(ROOT, "tools", "verify", "meta.tsv"), "utf8");

for (const raw of cases.split("\n")) {
  if (!raw || raw.startsWith("/")) continue;
  const f = raw.replace(/\r$/, "").split("\t");
  if (f.length < 12) continue;
  const [name, screen, seed, posS, durS, stateS, syncedS, offS, title, artist, album, app] = f;
  const lyrics = f.slice(12).join("\t");

  s = Number(seed) >>> 0;
  const V = { bands: [], peaks: [], bassAvg: 0 };
  for (let b = 0; b < 13; b++) V.bands.push(next());
  for (let b = 0; b < 13; b++) V.peaks.push(next());
  V.bassAvg = next();

  // 48x48 art, dithered the same way ditherSquare does
  const S = 48, lum = new Uint8Array(S * S);
  for (let i = 0; i < S * S; i++) lum[i] = Math.floor(next() * 256);
  let lo = 255, hi = 0;
  for (const l of lum) { if (l < lo) lo = l; if (l > hi) hi = l; }
  const span = Math.max(30, hi - lo);
  const BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];
  const art = new Uint8Array(S * S);
  for (let y = 0; y < S; y++)
    for (let x = 0; x < S; x++) {
      const v = ((lum[y * S + x] - lo) / span) * 3.999;
      const t = (BAYER4[y & 3][x & 3] + 0.5) / 16;
      art[y * S + x] = Math.max(0, Math.min(3, Math.floor(v + t - 0.5)));
    }

  ctx.META = {
    title: ctx.deckText(title), artist: ctx.deckText(artist),
    album: ctx.deckText(album), app: ctx.deckText(app),
    artBig: Number(seed) === 0 ? null : art,
  };
  ctx.POS = { base: Number(posS), duration: Number(durS), status: "paused", at: 1 };
  ctx.UI.coverScroll = { offset: 0, phase: 0, t: 0 };

  const state = ["idle", "searching", "ok", "none"][Number(stateS)];
  const lines = lyrics ? lyrics.split(";").filter(Boolean).map((e) => {
    const i = e.indexOf("|");
    return [Number(e.slice(0, i)), ctx.deckText(e.slice(i + 1))];
  }) : [];
  const rows = [], rowStart = [];
  lines.forEach((ln, i) => {
    rowStart[i] = rows.length;
    for (const text of ctx.wrapLyric(ln[1], 30)) rows.push({ i, text });
  });
  ctx.LYR = {
    state, synced: Number(syncedS) === 1, lines, rows, rowStart,
    offset: Number(offS), key: "k",
  };

  px.fill(0);
  if (screen === "cover") ctx.__cover(px, V, 100, 0);
  else ctx.__lyrics(px, V, 100, 0);

  let nz = 0, sum = 0;
  for (const b of px) { if (b) nz++; sum += b; }
  console.log(`${name.padEnd(16)} hash=${fnv1a(px).toString(16).padStart(8, "0")} ` +
              `nz=${String(nz).padEnd(5)} sum=${sum}`);
}
