// Screen-level reference: renders the ORIGINAL legacy/web/viz.js screens from
// the same seeded state as render_screens.c and prints the same digest.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const W = 192, H = 48;
const ROOT = path.join(__dirname, "..", "..");
const px = new Uint8Array(W * H);

const ctx = {
  GRID_W: W,
  GRID_H: H,
  setDot(f, x, y, i) {
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    const idx = y * W + x;
    if (i > f[idx]) f[idx] = i;
  },
  oceanFrame() {},                        // dolphins live in dolphin.js
};
ctx.globalThis = ctx;
vm.createContext(ctx);
const load = (p) => vm.runInContext(fs.readFileSync(path.join(ROOT, p), "utf8"), ctx);
load("legacy/web/font.js");
load("legacy/web/viz.js");
vm.runInContext(
  "globalThis.__s = { spectrum: vizSpectrum, mirror: vizMirror, scope: vizScope," +
  " city: vizCity, waterfall: vizWaterfall, vu: vizVU, '3d': viz3D };", ctx);

let s = 0;
const seed = (n) => { s = n >>> 0; };
const next = () => {
  s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
  return s / 4294967296;
};

function makeState(sd) {
  seed(sd);
  const v = {
    bands: [], peaks: [], bandsL: [], bandsR: [], wave: [],
    waveHist: [], wfHist: [], clip: 0, oceanTick: 0,
  };
  for (let b = 0; b < 13; b++) v.bands.push(next());
  for (let b = 0; b < 13; b++) v.peaks.push(next());
  for (let b = 0; b < 13; b++) v.bandsL.push(next());
  for (let b = 0; b < 13; b++) v.bandsR.push(next());
  v.vuL = next(); v.vuR = next();
  for (let i = 0; i < 96; i++) v.wave.push(next() * 2 - 1);
  v.bassAvg = next(); v.hfAvg = next();
  v.rms01 = next(); v.scopeGain = 1 + next() * 8;

  v.wfHist = [];
  for (let r = 0; r < 12; r++) {
    const row = new Float32Array(32);          // matches app.js stepBuffers
    for (let c = 0; c < 32; c++) row[c] = next();
    v.wfHist.push(row);
  }
  v.waveHist = [];
  for (let t = 0; t < 2; t++) {
    const tr = [];
    for (let i = 0; i < 96; i++) tr.push(next() * 2 - 1);
    v.waveHist.push(tr);
  }
  v.clip = next() > 0.5;
  return v;
}

function fnv1a(buf) {
  let h = 2166136261 >>> 0;
  for (const b of buf) { h = (h ^ b) >>> 0; h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}

const casesPath = process.argv[2] || path.join(ROOT, "tools", "verify", "screens.tsv");
for (const raw of fs.readFileSync(casesPath, "utf8").split("\n")) {
  if (!raw || raw.startsWith("/")) continue;
  const [name, screen, sd] = raw.trim().split(/\s+/);
  if (!name || !screen || sd === undefined) continue;

  const v = makeState(Number(sd));
  px.fill(0);
  const fn = ctx.__s[screen];
  if (!fn) { console.error("unknown screen " + screen); process.exit(1); }
  fn(px, v);

  let nz = 0, sum = 0;
  for (const b of px) { if (b) nz++; sum += b; }
  console.log(
    `${name.padEnd(16)} hash=${fnv1a(px).toString(16).padStart(8, "0")} ` +
    `nz=${String(nz).padEnd(5)} sum=${sum}`
  );
}
