// Reference side for the ocean scene.
//
// Unlike every other screen, this one cannot run in bare node: the dolphin
// silhouettes come out of Canvas. So it runs the original dolphin.js in real
// Chromium and prints the same digests render_ocean.c does.
//
// The scene keeps a world between frames, so each case gets a fresh page —
// that is what resets the module-level pod, spray and bubbles.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright-core");

const W = 192, H = 48;
const ROOT = path.join(__dirname, "..", "..");
const EXE = process.env.CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const HARNESS = `
  window.__fb = new Uint8Array(${W} * ${H});
  window.setDot = function (f, x, y, i) {
    if (x < 0 || x >= ${W} || y < 0 || y >= ${H}) return;
    const idx = y * ${W} + x;
    if (i > f[idx]) f[idx] = i;
  };
  window.fnv1a = function (buf) {
    let h = 2166136261 >>> 0;
    for (const b of buf) { h = (h ^ b) >>> 0; h = Math.imul(h, 16777619) >>> 0; }
    return h >>> 0;
  };
`;

(async () => {
  const cases = fs.readFileSync(
    process.argv[2] || path.join(ROOT, "tools", "verify", "ocean.tsv"), "utf8");
  const dolphin = fs.readFileSync(path.join(ROOT, "legacy", "web", "dolphin.js"), "utf8");

  const browser = await chromium.launch({ executablePath: EXE });
  for (const raw of cases.split("\n")) {
    if (!raw || raw.startsWith("/")) continue;
    const [name, framesS, rmsS, hfS, bassS, bassStepS] = raw.trim().split(/\s+/);
    if (!name || framesS === undefined) continue;

    const page = await browser.newPage();          // fresh world per case
    await page.setContent("<canvas id=c></canvas>");
    await page.addScriptTag({ content: HARNESS });
    await page.addScriptTag({ content: dolphin });
    if (process.env.DECK_DEBUG) await page.evaluate(() => { window.__DEBUG = 1; });

    const digest = await page.evaluate((a) => {
      const [frames, rms, hf, bass, bassStep] = a;
      let out = "";
      for (let t = 0; t < frames; t++) {
        window.__fb.fill(0);
        // bass ramps so the breach trigger fires partway through
        const energy = { rms01: rms, hf01: hf, bass01: bass + (t > 8 ? bassStep : 0) };
        oceanFrame(window.__fb, t, energy);
        let nz = 0, sum = 0;
        for (const b of window.__fb) { if (b) nz++; sum += b; }
        if (window.__DEBUG) {
          const d = _pod[0];
          out += `t${t} x${d.x.toFixed(3)} y${(d.render ? d.render.y : 0).toFixed(3)} ` +
                 `m${d.mode} jt${d.jt} a${(d.render ? d.render.ang : 0).toFixed(3)} ` +
                 `f${d.render ? d.render.flex : 0} sp${_spray.length}\n`;
        } else out += `${t}:${fnv1a(window.__fb).toString(16)}:${nz}:${sum} `;
      }
      return out.trim();
    }, [Number(framesS), Number(rmsS), Number(hfS), Number(bassS), Number(bassStepS)]);

    await page.close();
    console.log(`${name.padEnd(14)} ${digest}`);
  }
  await browser.close();
})();
