/* Photograph the legacy faceplate, with a fake deck plugged into it.
 *
 * The PC deck is a web page that renders whatever a WebSocket sends it, so the
 * cheapest honest way to get a picture of it is to run the real page in a real
 * browser and stub the socket. Nothing about the faceplate — the bezel, the
 * knob, the glass, the dot pitch, the illumination colour — is reproduced here;
 * it is all the actual thing, which is the point. Only the music is invented,
 * and it is invented to the same recipe as tools/media/shots.c so the analyser
 * in the screenshots matches the analyser in the screen GIFs.
 *
 *   node tools/media/faceplate.js <baseurl> <outdir>
 */
const { chromium } = require("playwright-core");
const path = require("path");

const EXE = process.env.CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

/* The same 120 bpm loop shots.c synthesises, in JS. Kept deliberately close to
 * that code rather than factored into something shared: they run in different
 * languages in different processes, and a "shared" version would be a third
 * copy plus a build step. */
const FEED = `
(() => {
  const BANDS = 13, WAVE = 96;
  const env = (p, d) => p < 0 ? 0 : Math.exp(-p * d);
  function bands(t) {
    const beat = t * 2;
    const kick = env(beat % 1, 7);
    const hat = env((beat + 0.5) % 1, 16) * ((beat % 2) < 1 ? 0.6 : 1);
    const snare = (beat % 4) >= 1 && (beat % 2) >= 1 ? env((beat - 1) % 2, 9) : 0;
    const sweep = 4.5 + 3.5 * Math.sin(t * 0.7);
    const out = [];
    for (let b = 0; b < BANDS; b++) {
      let v = 0.07 + 0.06 * Math.sin(t * 1.3 + b * 0.8);
      v += kick * Math.exp(-b * 0.80) * 0.90;
      v += snare * Math.exp(-Math.abs(b - 5) * 0.45) * 0.55;
      v += hat * (b >= 9 ? 0.70 : 0.06);
      v += 0.58 * Math.exp(-Math.abs(b - sweep) * 0.42);
      v += 0.26 * Math.exp(-Math.abs(b - 5.5) * 0.22) * (0.62 + 0.38 * Math.sin(t * 2.2 + b));
      v *= 1 - 0.022 * b;
      out.push(Math.max(0, Math.min(1, v)));
    }
    return out;
  }

  /* A sleeve, drawn on a canvas so the page's own dither path runs on it —
     the art in the screenshot goes through ditherArt() exactly as a real
     sleeve from Spotify would. */
  function sleeve() {
    const S = 300, c = document.createElement("canvas");
    c.width = c.height = S;
    const g = c.getContext("2d");
    g.fillStyle = "#241a2e"; g.fillRect(0, 0, S, S);
    const grad = g.createLinearGradient(0, 0, S, S);
    grad.addColorStop(0, "#4a3568"); grad.addColorStop(1, "#120d1a");
    g.fillStyle = grad; g.fillRect(0, 0, S, S);
    g.fillStyle = "#0a0710";
    g.beginPath(); g.arc(S / 2, S * 0.44, S * 0.30, 0, 7); g.fill();
    g.fillStyle = "#f6e7c8";
    g.beginPath(); g.arc(S / 2, S * 0.44, S * 0.26, 0, 7); g.fill();
    g.strokeStyle = "#f6e7c8"; g.lineWidth = S * 0.03;
    g.beginPath(); g.moveTo(S * 0.06, S * 0.90); g.lineTo(S * 0.94, S * 0.62); g.stroke();
    g.fillStyle = "#0a0710"; g.fillRect(0, S * 0.92, S, S * 0.08);
    return c.toDataURL("image/png");
  }

  const t0 = performance.now();
  class FakeSocket {
    constructor() {
      this.readyState = 1;
      setTimeout(() => {
        this.onopen && this.onopen();
        this.send_({ type: "meta", title: "Downhill",
                     artist: "The Night Shift", album: "Touge Sessions",
                     app: "Spotify", status: 1, art: sleeve() });
        this.send_({ type: "lyrics", synced: true, state: "ok", lines: [
          [0, "Nothing but the rain"],
          [3, "and the tail lights bleeding out ahead"],
          [7.5, "I know this road by heart"],
          [10.5, "every corner, every camber"],
          [17, "Hold it sideways, let it run"]] });
        setInterval(() => {
          const t = (performance.now() - t0) / 1000;
          const s = bands(t);
          const wave = [];
          const amp = 0.30 + 0.62 * s.reduce((a, b) => a + b, 0) / BANDS;
          for (let i = 0; i < WAVE; i++) {
            const u = i / WAVE;
            wave.push(amp * (0.62 * Math.sin(u * 6.2831853 * 2 + t * 5) +
                             0.26 * Math.sin(u * 6.2831853 * 5 - t * 3.1) +
                             0.12 * Math.sin(u * 6.2831853 * 11 + t * 8.7)));
          }
          const rms = s.reduce((a, b) => a + b, 0) / BANDS;
          this.send_({ type: "audio", spec: s,
                       specL: s.map((v, b) => v * (0.86 + 0.14 * Math.sin(t * 1.1 + b * 0.6))),
                       specR: s.map((v, b) => v * (0.86 + 0.14 * Math.sin(t * 1.1 + b * 0.6 + 2.1))),
                       rmsL: rms * 0.98, rmsR: rms * 1.02, wave, clip: false });
          this.send_({ type: "pos", position: 74 + t, duration: 214, status: 1 });
        }, 33);
      }, 30);
    }
    send_(o) { this.onmessage && this.onmessage({ data: JSON.stringify(o) }); }
    send() {}
    close() {}
  }
  window.WebSocket = FakeSocket;
})();
`;

/* Which key selects which mode, and how long to let it settle. The waterfall
 * and the ocean need real time before they are worth photographing: one has to
 * fill twelve rows of history, the other has to get a dolphin into the air. */
const SHOTS = [
  ["faceplate", "1", 2500],
  ["faceplate-vu", "3", 2500],
  ["faceplate-cover", "a", 3000],
  ["faceplate-lyrics", "l", 4000],
  ["faceplate-waterfall", "6", 6000],
  ["faceplate-ocean", "b", 9000],
];

(async () => {
  const base = process.argv[2] || "http://127.0.0.1:7799/web/index.html";
  const outdir = process.argv[3] || "docs/media";

  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 620 }, deviceScaleFactor: 2 });
  await page.addInitScript(FEED);
  await page.goto(base, { waitUntil: "load" });
  await page.waitForTimeout(1200);

  for (const [name, key, settle] of SHOTS) {
    await page.keyboard.press(key);
    await page.waitForTimeout(settle);
    const el = await page.$("#unit");
    const file = path.join(outdir, name + ".png");
    await el.screenshot({ path: file });
    console.log("  " + file);
  }
  await browser.close();
})();
