// Render tools/verify/cases.tsv through the ORIGINAL legacy JS font code and
// print the same digest format as render.c. Any difference between the two
// outputs is an unfaithful port.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const W = 192, H = 48;
const ROOT = path.join(__dirname, "..", "..");
const px = new Uint8Array(W * H);

// setDot, lifted verbatim from legacy/web/app.js
const ctx = {
  GRID_W: W,
  GRID_H: H,
  setDot(f, x, y, i) {
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    const idx = y * W + x;
    if (i > f[idx]) f[idx] = i;
  },
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(
  fs.readFileSync(path.join(ROOT, "legacy", "web", "font.js"), "utf8") +
    ";globalThis.__t5 = drawText5; globalThis.__t3 = drawText3;" +
    ";globalThis.__w5 = textWidth5; globalThis.__w3 = textWidth3;",
  ctx
);

function fnv1a(buf) {
  let h = 2166136261 >>> 0;
  for (const b of buf) { h = (h ^ b) >>> 0; h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}

const casesPath = process.argv[2] || path.join(ROOT, "tools", "verify", "cases.tsv");
for (const raw of fs.readFileSync(casesPath, "utf8").split("\n")) {
  if (!raw || raw.startsWith("/")) continue;
  const line = raw.replace(/\r$/, "");
  const parts = line.split("\t");
  if (parts.length < 7) continue;
  let [name, fn, x, y, inten, scale] = parts;
  const text = parts.slice(6).join("\t");
  x = +x; y = +y; inten = +inten; scale = +scale;

  if (name.startsWith("+")) name = name.slice(1);
  else px.fill(0);

  const adv = fn === "3" ? ctx.__t3(px, x, y, text, inten)
                         : ctx.__t5(px, x, y, text, inten, scale);
  const width = fn === "3" ? ctx.__w3(text) : ctx.__w5(text, scale);

  let nz = 0, x0 = W, y0 = H, x1 = -1, y1 = -1;
  for (let yy = 0; yy < H; yy++)
    for (let xx = 0; xx < W; xx++)
      if (px[yy * W + xx]) {
        nz++;
        if (xx < x0) x0 = xx;
        if (xx > x1) x1 = xx;
        if (yy < y0) y0 = yy;
        if (yy > y1) y1 = yy;
      }

  console.log(
    `${name.padEnd(16)} hash=${fnv1a(px).toString(16).padStart(8, "0")} ` +
    `nz=${String(nz).padEnd(5)} bbox=${x0},${y0},${x1},${y1} adv=${adv} width=${width}`
  );
}
