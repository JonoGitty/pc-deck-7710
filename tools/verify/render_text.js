// Reference side for the text helpers.
//
// deckText, wrapLyric and scrollText live in legacy/web/app.js, which touches
// the DOM at load and cannot simply be evaluated. Rather than transcribe them
// (and risk verifying a copy against itself), cut the three function bodies out
// of the source by brace matching and run the originals.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..", "..");
const src = fs.readFileSync(path.join(ROOT, "legacy", "web", "app.js"), "utf8");

function extract(name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`${name} not found in app.js`);
  let i = src.indexOf("{", start), depth = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === "{") depth++;
    else if (src[j] === "}") { depth--; if (depth === 0) return src.slice(start, j + 1); }
  }
  throw new Error(`unbalanced braces in ${name}`);
}

const ctx = { LYRIC_CELLS: 30 };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(
  [extract("deckText"), extract("wrapLyric"), extract("scrollText")].join("\n") +
  ";globalThis.__fold = deckText; globalThis.__wrap = wrapLyric;" +
  " globalThis.__scroll = scrollText;", ctx);

function out(name, s) { console.log(`${name.padEnd(18)} |${s}|`); }

const casesPath = process.argv[2] || path.join(ROOT, "tools", "verify", "text.tsv");
for (const raw of fs.readFileSync(casesPath, "utf8").split("\n")) {
  if (!raw || raw.startsWith("/")) continue;
  const line = raw.replace(/\r$/, "");
  const parts = line.split("\t");
  if (parts.length < 4) continue;
  const [name, kind, a, b] = parts;
  const text = parts.slice(4).join("\t");

  if (kind === "fold") {
    out(name, ctx.__fold(text));
  } else if (kind === "wrap") {
    const folded = ctx.__fold(text);
    out(name, ctx.__wrap(folded, Number(a)).join("/"));
  } else if (kind === "scroll") {
    // a = cells, b = number of 100 ms steps
    const folded = ctx.__fold(text);
    const sc = { offset: 0, phase: 0, t: 0 };
    const frames = [];
    for (let i = 0; i < Number(b); i++) frames.push(ctx.__scroll(sc, 100, folded, Number(a)));
    out(name, frames.join("/"));
  }
}
