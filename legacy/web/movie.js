// .dmv playback for the legacy faceplate.
//
// The PC deck can play the same animations the firmware does, so an animation
// made for a head unit can be watched here first — which for most people is
// the only display they have while they wait for parts.
//
// Format is documented in core/movie.h. Deltas against a cleared grid, so
// looping means replaying from frame 0 rather than seeking.
"use strict";

const MOVIES = {
  list: [],          // [{name, url}]
  loaded: null,      // decoded movie
  grid: null,
  frame: 0,
  cursor: 0,
  acc: 0,
  index: 0,          // which of MOVIES.list
  error: "",
};

function parseDMV(buf) {
  const d = new DataView(buf);
  if (d.getUint8(0) !== 0x44 || d.getUint8(1) !== 0x4d ||
      d.getUint8(2) !== 0x56 || d.getUint8(3) !== 0x31) return null;   // "DMV1"
  const w = d.getUint16(4, true), h = d.getUint16(6, true);
  const fps = d.getUint8(8), flags = d.getUint8(9);
  const frameCount = d.getUint16(10, true), nameLen = d.getUint16(12, true);
  let at = 14;
  let name = "";
  for (let i = 0; i < nameLen; i++) name += String.fromCharCode(d.getUint8(at + i));
  at += nameLen;
  return { d, w, h, fps, flags, frameCount, name, first: at, bytes: buf.byteLength };
}

function movieStart(m) {
  MOVIES.loaded = m;
  MOVIES.grid = new Uint8Array(m.w * m.h);
  MOVIES.frame = 0;
  MOVIES.cursor = m.first;
  MOVIES.acc = 0;
}

function movieStep() {
  const m = MOVIES.loaded;
  if (!m) return;
  if (MOVIES.frame >= m.frameCount) {
    if (!(m.flags & 1)) return;
    movieStart(m);                              // deltas: loop by replaying
  }
  if (MOVIES.cursor + 2 > m.bytes) return;
  const runs = m.d.getUint16(MOVIES.cursor, true);
  let at = MOVIES.cursor + 2;
  const cells = m.w * m.h;
  for (let r = 0; r < runs; r++) {
    const start = m.d.getUint16(at, true);
    const len = m.d.getUint16(at + 2, true);
    const level = m.d.getUint8(at + 4);
    at += 5;
    if (start + len > cells) continue;
    const v = Math.min(level, 4);
    for (let i = 0; i < len; i++) MOVIES.grid[start + i] = v;
  }
  MOVIES.cursor = at;
  MOVIES.frame++;
}

async function loadMovieList() {
  try {
    const res = await fetch("/web/movies/index.json");
    if (!res.ok) throw new Error("no index");
    MOVIES.list = await res.json();
    if (MOVIES.list.length) await loadMovie(0);
  } catch (e) {
    MOVIES.error = "NO MOVIES";
  }
}

async function loadMovie(i) {
  if (!MOVIES.list.length) return;
  MOVIES.index = ((i % MOVIES.list.length) + MOVIES.list.length) % MOVIES.list.length;
  try {
    const res = await fetch(MOVIES.list[MOVIES.index].url);
    const m = parseDMV(await res.arrayBuffer());
    if (!m) { MOVIES.error = "BAD MOVIE"; return; }
    MOVIES.error = "";
    movieStart(m);
  } catch (e) {
    MOVIES.error = "LOAD FAILED";
  }
}

// --- the screen ------------------------------------------------------------
function vizMovie(fb, V, dt, now) {
  const m = MOVIES.loaded;
  if (!m) {
    const msg = MOVIES.error || "LOADING";
    drawText5(fb, Math.floor((GRID_W - textWidth5(msg, 1)) / 2), 14, msg, 2, 1);
    drawText3(fb, Math.floor((GRID_W - textWidth3("PUT .DMV FILES IN WEB/MOVIES")) / 2),
              30, "PUT .DMV FILES IN WEB/MOVIES", 1);
    return;
  }

  MOVIES.acc += dt;
  const step = 1000 / (m.fps || 10);
  while (MOVIES.acc >= step) { movieStep(); MOVIES.acc -= step; }

  // centre rather than scale — resampling would blur the dot matrix, which is
  // the whole look
  const ox = Math.floor((GRID_W - m.w) / 2), oy = Math.floor((GRID_H - m.h) / 2);
  for (let y = 0; y < m.h; y++)
    for (let x = 0; x < m.w; x++) {
      const v = MOVIES.grid[y * m.w + x];
      if (v) setDot(fb, ox + x, oy + y, v);
    }
}

loadMovieList();
