// The dolphin display movie, v2 — native 192x48 resolution.
// Dolphins are rasterized from a smooth bezier silhouette (rotated per frame,
// snapped to the dot grid) so they read as real dolphins, not submarines.
// Playback is stepped at 10 movie-fps like a period OEL animation.
"use strict";

const WAVE_Y = 13;

// ---- silhouette -> dot raster, cached by (length, angle, tail-flex) -------
const _rcache = new Map();

function drawDolphinPath(g, flex) {
  const fl = (flex - 1) * 0.05;                 // tail flex: -0.05 / 0 / +0.05
  g.beginPath();                                // body: tail stock -> back -> beak -> belly
  g.moveTo(0.02, -0.015);
  g.bezierCurveTo(0.25, -0.15, 0.55, -0.13, 0.82, -0.045);
  g.quadraticCurveTo(0.94, -0.025, 1.0, -0.005);
  g.quadraticCurveTo(0.93, 0.02, 0.84, 0.035);
  g.bezierCurveTo(0.58, 0.11, 0.28, 0.10, 0.02, 0.025);
  g.closePath();
  g.moveTo(0.03, 0);                            // tail flukes, two swept lobes
  g.quadraticCurveTo(-0.05, -0.02 + fl * 2, -0.14, -0.11 + fl);
  g.quadraticCurveTo(-0.04, -0.01 + fl, -0.02, 0.005);
  g.quadraticCurveTo(-0.06, 0.03 + fl, -0.13, 0.10 + fl);
  g.quadraticCurveTo(-0.04, 0.025, 0.03, 0.012);
  g.closePath();
  g.moveTo(0.40, -0.095);                       // falcate dorsal fin
  g.quadraticCurveTo(0.47, -0.26, 0.55, -0.23);
  g.quadraticCurveTo(0.53, -0.14, 0.59, -0.085);
  g.closePath();
  g.moveTo(0.60, 0.05);                         // pectoral fin
  g.quadraticCurveTo(0.55, 0.15, 0.47, 0.19);
  g.quadraticCurveTo(0.52, 0.08, 0.56, 0.04);
  g.closePath();
}

function dolphinRaster(len, angleDeg, flex) {
  const a = Math.round(angleDeg / 10) * 10;     // quantize: bitmap-movie feel + small cache
  const key = `${len}:${a}:${flex}`;
  if (_rcache.has(key)) return _rcache.get(key);
  const D = Math.ceil(len * 1.5);
  const c = document.createElement("canvas");
  c.width = c.height = D;
  const g = c.getContext("2d");
  g.translate(D / 2, D / 2);
  g.rotate(a * Math.PI / 180);
  g.scale(len, len);
  g.translate(-0.5, 0);
  drawDolphinPath(g, flex);
  g.fillStyle = "#fff";
  g.fill();
  const img = g.getImageData(0, 0, D, D).data;
  const data = new Uint8Array(D * D);
  for (let i = 0; i < D * D; i++) data[i] = img[i * 4 + 3] > 120 ? 1 : 0;
  const r = { w: D, h: D, data };
  _rcache.set(key, r);
  return r;
}

function blit(fb, r, cx, cy, inten) {
  const ox = cx - (r.w >> 1), oy = cy - (r.h >> 1);
  for (let y = 0; y < r.h; y++)
    for (let x = 0; x < r.w; x++)
      if (r.data[y * r.w + x]) setDot(fb, ox + x, oy + y, inten);
}

// ---- dolphin actors -------------------------------------------------------
function makeDolphin(len, depth, x0, breachEvery, breachOffset) {
  return { len, depth, x: x0, t: 0, mode: "swim", jt: 0, y0: depth,
           breachEvery, breachOffset, wantBreach: false };
}
const _pod = [
  makeDolphin(30, 30, -20, 150, 40),
  makeDolphin(21, 38, -95, 150, 115),
];
const _spray = [];
let _lastBass = 0;

function spawnSpray(x, dir) {
  for (let i = 0; i < 7; i++) {
    _spray.push({
      x: x + ((i * 5) % 7) - 3,
      y: WAVE_Y - 1,
      vx: (((i * 37) % 7) - 3) / 2.2,
      vy: -1.4 - ((i * 13) % 3) * 0.5 * dir,
      life: 6 + (i % 3),
    });
  }
}

function stepDolphin(d, tick) {
  d.t++;
  if (d.mode === "swim") {
    d.x += 2;
    if (d.x > 225) d.x = -40;
    const bob = 2 * Math.sin(d.t / 5);
    d.y0 = d.depth + bob;
    const due = (tick + d.breachOffset) % d.breachEvery === 0;
    if ((due || d.wantBreach) && d.x > 25 && d.x < 140) {
      d.mode = "jump"; d.jt = 0; d.wantBreach = false;
    }
    return { y: d.y0, ang: 8 * Math.sin(d.t / 5 + 1), flex: (d.t >> 1) % 3, inten: 2 };
  }
  // parabolic breach: launch, clear the wave, re-enter
  const V = 4.2, G = 0.34;
  d.jt++;
  d.x += 2.6;
  const y = d.depth - V * d.jt + 0.5 * G * d.jt * d.jt;
  const vy = -V + G * d.jt;
  const ang = Math.atan2(vy, 2.6) * 180 / Math.PI;
  const prevY = d.depth - V * (d.jt - 1) + 0.5 * G * (d.jt - 1) ** 2;
  if (prevY > WAVE_Y && y <= WAVE_Y) spawnSpray(d.x, 1);        // bursting out
  if (prevY < WAVE_Y && y >= WAVE_Y) spawnSpray(d.x, 0.6);      // re-entry
  if (d.jt >= Math.ceil(2 * V / G) || y > d.depth) d.mode = "swim";
  return { y, ang, flex: 1, inten: y < WAVE_Y ? 3 : 2 };
}

// ---- the scene ------------------------------------------------------------
const _bubbles = [];
let _lastTick = -1;

function oceanFrame(fb, tick, energy) {
  const step = tick !== _lastTick;          // world advances at movie fps only
  if (step) _lastTick = tick;
  const glow = energy.rms01 > 0.55 ? 3 : energy.rms01 > 0.18 ? 2 : 1;

  // sun, top right
  for (let dy = -2; dy <= 2; dy++)
    for (let dx = -3; dx <= 3; dx++)
      if (dx * dx + dy * dy * 1.8 <= 6.5) setDot(fb, 176 + dx, 4 + dy, 1);
  setDot(fb, 176, 4, 2); setDot(fb, 175, 4, 2); setDot(fb, 176, 3, 2);

  // scrolling wave line (8-cell pattern, two alternating shapes)
  const pat = (tick & 2) ? [0, 0, 1, 1, 0, 0, 0, 1] : [1, 0, 0, 0, 1, 1, 0, 0];
  for (let x = 0; x < 192; x++) {
    const p = pat[(x + tick) % 8];
    setDot(fb, x, WAVE_Y + p, glow);
    if (((x + tick * 3) % 24) === 7) setDot(fb, x, WAVE_Y + 2, 1);  // undersheen
  }

  // underwater shimmer — deterministic twinkle
  for (let y = 20; y < 43; y += 4)
    for (let x = 0; x < 192; x++)
      if ((x * 7 + y * 13 + (tick >> 1) * 5) % 131 < 1) setDot(fb, x, y, 1);

  // seabed
  for (let x = 0; x < 192; x++) {
    setDot(fb, x, 47, 1);
    if (x % 11 === 0 || x % 11 === 5) setDot(fb, x, 46, 1);
    if (x % 23 === 9) setDot(fb, x, 45, 1);
  }

  // bubbles rise on high-frequency energy
  if (step) {
    if (_bubbles.length < 14 && (tick * 37) % 100 < energy.hf01 * 120)
      _bubbles.push({ x: (tick * 53) % 192, y: 43 });
    for (let i = _bubbles.length - 1; i >= 0; i--) {
      _bubbles[i].y -= 2;
      if (_bubbles[i].y <= WAVE_Y + 2) _bubbles.splice(i, 1);
    }
  }
  for (let i = 0; i < _bubbles.length; i++)
    setDot(fb, _bubbles[i].x + ((tick + i) % 4 < 2 ? 0 : 1), _bubbles[i].y, 1);

  if (step) {
    // a bass hit sends the pod over the wave
    if (energy.bass01 - _lastBass > 0.3)
      for (const d of _pod) if (d.mode === "swim") d.wantBreach = true;
    _lastBass = _lastBass * 0.9 + energy.bass01 * 0.1;

    for (const d of _pod) d.render = stepDolphin(d, tick);

    for (let i = _spray.length - 1; i >= 0; i--) {
      const p = _spray[i];
      p.x += p.vx; p.y += p.vy; p.vy += 0.32; p.life--;
      if (p.life <= 0 || p.y > WAVE_Y + 2) _spray.splice(i, 1);
    }
  }

  for (const d of _pod) {
    const s = d.render || (d.render = stepDolphin(d, tick));
    blit(fb, dolphinRaster(d.len, s.ang, s.flex), Math.round(d.x), Math.round(s.y), s.inten);
  }
  for (const p of _spray)
    setDot(fb, Math.round(p.x), Math.round(p.y), p.life > 3 ? 2 : 1);
}
