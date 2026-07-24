// Visualizer modes. Each draws into the 192x48 framebuffer from V, the
// smoothed analysis state maintained in app.js:
//   V.bands[13] 0..1, V.peaks[13] 0..1, V.vuL/V.vuR 0..1 (needle ballistics),
//   V.bandsL/R[13], V.wave[96], V.waveHist[][96], V.wfHist[][32], V.clip
// Intensities: 1 dim, 2 main, 3 hot, 4 clip-red.
"use strict";

const VIZ_TOP = 32, VIZ_BOT = 47;       // compact strip under the text lines
const BIG_TOP = 24;                     // tall modes hide the secondary line

// --- 1. classic 13-band segmented spectrum -------------------------------
function vizSpectrum(fb, V) {
  const segH = 2, segs = 8, pitch = 14, barW = 11, x0 = 5;
  for (let b = 0; b < 13; b++) {
    const lit = Math.round(V.bands[b] * segs);
    for (let s = 0; s < lit; s++) {
      const y = VIZ_BOT - 1 - s * segH;
      const i = s >= segs - 1 ? 3 : 2;
      for (let dy = 0; dy < segH - 0; dy++)
        for (let x = 0; x < barW; x++)
          setDot(fb, x0 + b * pitch + x, y - dy + 1, i);
    }
    const pk = Math.round(V.peaks[b] * segs);
    if (pk > 0) {
      const y = VIZ_BOT - (pk - 1) * segH - segH;
      for (let x = 2; x < barW - 2; x++) setDot(fb, x0 + b * pitch + x, y, 3);
    }
  }
}

// --- 2. mirrored L/R spectrum, low frequencies at the centre --------------
function vizMirror(fb, V) {
  const segH = 2, segs = 8, pitch = 7, barW = 5, cx = 96;
  for (let b = 0; b < 13; b++) {
    const xs = [cx - (b + 1) * pitch, cx + b * pitch + 2];
    const vv = [V.bandsL[b], V.bandsR[b]];
    for (let side = 0; side < 2; side++) {
      const lit = Math.round(vv[side] * segs);
      for (let s = 0; s < lit; s++) {
        const y = VIZ_BOT - s * segH;
        for (let x = 0; x < barW; x++)
          setDot(fb, xs[side] + x, y - 1, s >= segs - 1 ? 3 : 2);
        for (let x = 0; x < barW; x++)
          setDot(fb, xs[side] + x, y, s >= segs - 1 ? 3 : 2);
      }
    }
  }
  for (let y = VIZ_TOP; y <= VIZ_BOT; y += 2) setDot(fb, cx - 1, y, 1);
  drawText3(fb, 2, VIZ_BOT - 4, "L", 1);
  drawText3(fb, 187, VIZ_BOT - 4, "R", 1);
}

// --- 3. twin VU needles ----------------------------------------------------
function _needle(fb, cx, v, label) {
  const cy = 58, deg = (v - 0.5) * 100;               // -50..+50 degrees
  const th = deg * Math.PI / 180;
  // scale arc
  for (let d = -50; d <= 50; d += 10) {
    const t = d * Math.PI / 180;
    const x = Math.round(cx + 32 * Math.sin(t)), y = Math.round(cy - 32 * Math.cos(t));
    setDot(fb, x, y, d === 50 ? 4 : 1);
    if (d === 50) setDot(fb, x - 1, y, 4);
  }
  drawText3(fb, cx - 34, 42, "-", 1);
  drawText3(fb, cx + 30, 42, "+", 1);
  // needle
  for (let r = 12; r <= 30; r += 0.7) {
    const x = Math.round(cx + r * Math.sin(th)), y = Math.round(cy - r * Math.cos(th));
    setDot(fb, x, y, 3);
  }
  drawText3(fb, cx - 1, 43, label, 2);
}
function vizVU(fb, V) {
  _needle(fb, 52, V.vuL, "L");
  _needle(fb, 140, V.vuR, "R");
  drawText3(fb, 89, BIG_TOP + 1, "VU", 1);
  if (V.clip) drawText3(fb, 85, 43, "OVER", 4);
}

// --- 4. dot-matrix oscilloscope -------------------------------------------
function vizScope(fb, V) {
  const cy = 36, amp = 11;
  for (let x = 0; x < 192; x += 8) setDot(fb, x, cy, 1);          // centreline
  for (let x = 0; x < 192; x += 48)
    for (let y = BIG_TOP + 1; y < 48; y += 4) setDot(fb, x, y, 1); // timing ticks
  const traces = [[V.waveHist[0], 1], [V.waveHist[1], 1], [V.wave, 2]];
  for (const [tr, base] of traces) {
    if (!tr) continue;
    for (let i = 0; i < 96; i++) {
      const y = Math.max(BIG_TOP, Math.min(47, Math.round(cy - tr[i] * V.scopeGain * amp)));
      setDot(fb, i * 2, y, base);
      setDot(fb, i * 2 + 1, y, base === 2 && Math.abs(tr[i]) > 0.6 ? 3 : base);
    }
  }
}

// --- 5. EQ cityscape -------------------------------------------------------
let _sweepY = 60;
function vizCity(fb, V) {
  const widths = [20, 16, 14, 12, 12, 10, 10, 10, 10, 10, 10, 8, 8]; // bass = broad towers
  let x0 = 2;
  for (let b = 0; b < 13; b++) {
    const h = Math.round(V.bands[b] * (47 - BIG_TOP));
    const top = 47 - h;
    for (let y = 47; y > top; y--)
      for (let x = 0; x < widths[b] - 2; x++)
        setDot(fb, x0 + x, y, y === top + 1 ? 3 : 2);
    const pk = 47 - Math.round(V.peaks[b] * (47 - BIG_TOP));
    if (pk < 47) for (let x = 2; x < widths[b] - 4; x++) setDot(fb, x0 + x, pk, 3);
    x0 += widths[b];
  }
  _sweepY -= 0.35;                                   // occasional rising scan
  if (_sweepY < BIG_TOP - 14) _sweepY = 62;
  const sy = Math.round(_sweepY);
  if (sy >= BIG_TOP && sy <= 47)
    for (let x = 0; x < 192; x += 2) setDot(fb, x, sy, 1);
}

// --- 6. waterfall memory ---------------------------------------------------
function vizWaterfall(fb, V) {
  // 32 cols x 12 rows of chunky cells (1 lit row + 1 gap); newest at the bottom
  for (let r = 0; r < 12; r++) {
    const row = V.wfHist[r];
    if (!row) continue;
    for (let c = 0; c < 32; c++) {
      const v = row[c];
      if (v < 0.28) continue;
      let i = v > 0.82 ? 3 : v > 0.55 ? 2 : 1;
      if (r > 3) i = Math.min(i, 2);          // memory cools as it climbs
      if (r > 7) i = 1;
      const y = 46 - r * 2, x = c * 6;
      for (let dx = 0; dx < 5; dx++) setDot(fb, x + dx, y, i);
    }
  }
}

// --- 7. 3D spectrum mountain ----------------------------------------------
// Perspective-receding analyzer landscape: front ridge is the live spectrum,
// rows behind are waterfall history shrinking toward a vanishing point.
// Painter's algo front-to-back with a per-column skyline for hidden-line removal.
function viz3D(fb, V) {
  const skyline = new Int8Array(192).fill(127);
  for (let d = 0; d < 12; d++) {
    const row = d === 0 ? null : V.wfHist[d - 1];
    if (d > 0 && !row) break;
    const inset = d * 6, w = 192 - inset * 2;
    if (w < 24) break;
    const yBase = 47 - d * 1.8, hMax = 15 - d * 0.7;
    const inten = d === 0 ? 3 : d < 5 ? 2 : 1;
    let prevY = -1;
    for (let x = inset; x < 192 - inset; x++) {
      const u = (x - inset) / w;
      let v;
      if (row) {
        v = row[Math.min(31, Math.round(u * 31))];
      } else {
        const f = u * 12, i = Math.min(11, Math.floor(f)), fr = f - i;
        v = V.bands[i] * (1 - fr) + V.bands[i + 1] * fr;
      }
      const y = Math.max(23, Math.round(yBase - v * hMax));
      const lo = prevY < 0 ? y : Math.min(prevY, y);
      const hi = prevY < 0 ? y : Math.max(prevY, y);
      for (let yy = lo; yy <= hi; yy++)
        if (yy < skyline[x]) setDot(fb, x, yy, inten);
      if (y < skyline[x]) skyline[x] = y;
      prevY = y;
    }
  }
}

// --- 8. ocean movie (also the screensaver) --------------------------------
function vizOcean(fb, V) {
  oceanFrame(fb, V.oceanTick, { rms01: V.rms01, hf01: V.hfAvg, bass01: V.bassAvg });
}

const MODES = [
  { id: "SPECTRUM",  name: "SPECTRUM ANALYZER", draw: vizSpectrum,  big: false },
  { id: "MIRROR",    name: "MIRROR SPECTRUM",   draw: vizMirror,    big: false },
  { id: "VU",        name: "VU METER",          draw: vizVU,        big: true  },
  { id: "SCOPE",     name: "OSCILLOSCOPE",      draw: vizScope,     big: true  },
  { id: "CITY",      name: "CITYSCAPE EQ",      draw: vizCity,      big: true  },
  { id: "WATERFALL", name: "WATERFALL",         draw: vizWaterfall, big: true  },
  { id: "3D",        name: "3D SPECTRUM",       draw: viz3D,        big: true  },
  { id: "OCEAN",     name: "OCEAN CRUISE",      draw: vizOcean,     big: "full" },
];
