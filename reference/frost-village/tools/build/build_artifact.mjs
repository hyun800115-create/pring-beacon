// Frost Village (서리마을 개척기) — build the claude.ai Artifact package.
//
//   cd frost-village/tools/build && npm install          (once: installs esbuild locally)
//   node frost-village/tools/build/build_artifact.mjs [--no-minify] [--mp3-only] [--inline] [--webp]
//
// Output: frost-village/dist/artifact/
//   index.html        body-only page (the Artifact host adds <!doctype><html><head><body> itself):
//                     <title>, inline <style>, the game container, lib/phaser.min.js, game.js
//   game.js           src/main.js + every module it imports, bundled by esbuild into ONE classic
//                     script (IIFE, ES2019) — no ES modules, no import(), no module workers
//   lib/              phaser.min.js (+ its licence)
//   assets/           copy of frost-village/assets (manifests, atlases, images, audio)
// and frost-village/dist/artifact_files.json — the list of supporting files to pass to the
// Artifact tool as `files` (with `root` = frost-village/dist/artifact).
//
// Host limits checked here: <= 255 files, <= 64 MB in total, <= 16 MB per file, page file without
// doctype/html/head/body tags. If the file count would exceed 255, the .ogg copies are dropped and
// the audio manifest is rewritten to point at the .mp3 files only (also forced by --mp3-only).
//
// --inline (fallback, output: frost-village/dist/artifact_inline/): for a host whose frame has an
//   opaque origin AND serves the files without CORS headers, where the normal build cannot load a
//   single asset (Phaser loads everything with XMLHttpRequest). Every asset is embedded into
//   packs/assets_N.js classic scripts (images as data: URIs, JSON as objects, audio as base64 mp3)
//   and inline_loader.js re-routes Phaser's loader to them: no XHR/fetch at all, so it also works
//   with connect-src 'self'. Bigger download (+33 % base64), so use it only if the normal build fails.
//
// --webp (optional, needs python3 + Pillow): re-encode the big PNGs of the COPY as WebP (q90,
//   lossless alpha) when that saves > 40 %, and rewrite the copied manifests. assets/ is untouched.
//   About -3 MB (7.6 -> 4.7 MB of images). Works with --inline too.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');            // frost-village/
const args = process.argv.slice(2);
const MINIFY = !args.includes('--no-minify');
const INLINE = args.includes('--inline');
const WEBP = args.includes('--webp');
const FORCE_MP3_ONLY = args.includes('--mp3-only') || INLINE;   // mp3 plays everywhere; one format is enough

const OUT = path.join(ROOT, 'dist', INLINE ? 'artifact_inline' : 'artifact');
const LIST_OUT = path.join(ROOT, 'dist', INLINE ? 'artifact_inline_files.json' : 'artifact_files.json');
const PACK_MAX = 4 * 1024 * 1024;          // bytes of source data per packs/assets_N.js

const LIMITS = { files: 255, total: 64 * 1024 * 1024, perFile: 16 * 1024 * 1024 };
// Media types the host serves (anything else is skipped with a warning).
const WEB_TYPES = new Set(['.html', '.js', '.json', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.ogg', '.mp3', '.m4a', '.wav', '.css', '.txt', '.md', '.woff2']);
const JUNK = /(^|\/)(\.DS_Store|Thumbs\.db|desktop\.ini|\..*)$|\.(py|pyc|blend|blend1|psd|kra|xcf|aup3)$/i;

function loadEsbuild() {
  const require = createRequire(import.meta.url);
  try { return require('esbuild'); } catch (e) {
    console.error('\n[build] esbuild is not installed. Run this once:\n    cd ' + path.relative(process.cwd(), HERE) + ' && npm install\n');
    process.exit(1);
  }
}

const mb = (n) => (n / 1048576).toFixed(2) + ' MB';
const rel = (p) => path.relative(OUT, p).split(path.sep).join('/');

function walk(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else if (e.isFile()) out.push(p);
  }
  return out;
}

// ------------------------------------------------------------------ page (body content only)
const PAGE = `<title>서리마을 개척기</title>
<style>
  /* One-screen game: a portrait canvas centred on a deep, snowy night sky.
     Single dark look on purpose (no light theme), so every colour is set here explicitly. */
  :root {
    color-scheme: dark;
    --night: #0f1a2c;          /* page ground */
    --night-high: #1d3150;     /* glow behind the game */
    --frost: #eaf2fb;          /* text */
    --frost-dim: #9fb6d3;      /* secondary text */
    --ice: #7cc0ff;            /* snowflake accent */
    --panel: #fff8ec;          /* error card (game UI cream) */
    --panel-ink: #2b2f3a;
    --font: Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', system-ui, sans-serif;
  }
  html, body {
    margin: 0; width: 100%; height: 100%;
    overflow: hidden; overscroll-behavior: none;
    touch-action: none; -webkit-touch-callout: none;
    -webkit-user-select: none; user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  body {
    color: var(--frost);
    font-family: var(--font);
    background-color: var(--night);
    background-image:
      radial-gradient(1.5px 1.5px at 12% 18%, rgba(255,255,255,.55) 50%, transparent 51%),
      radial-gradient(1px 1px at 78% 9%, rgba(255,255,255,.45) 50%, transparent 51%),
      radial-gradient(2px 2px at 64% 72%, rgba(255,255,255,.35) 50%, transparent 51%),
      radial-gradient(1.5px 1.5px at 28% 84%, rgba(255,255,255,.4) 50%, transparent 51%),
      radial-gradient(1px 1px at 90% 46%, rgba(255,255,255,.5) 50%, transparent 51%),
      radial-gradient(1.5px 1.5px at 6% 58%, rgba(255,255,255,.35) 50%, transparent 51%),
      radial-gradient(ellipse 70% 60% at 50% 45%, var(--night-high) 0%, var(--night) 100%);
    background-size: 220px 260px, 180px 200px, 260px 240px, 240px 300px, 200px 220px, 300px 280px, 100% 100%;
  }
  /* The host pads :root by the phone's safe-area insets; a fixed layer ignores that, so add them here. */
  #game {
    position: fixed; left: 0; right: 0;
    top: env(safe-area-inset-top, 0px); bottom: env(safe-area-inset-bottom, 0px);
  }
  #game canvas { display: block; touch-action: none; outline: none; }
  #fv-loading {
    position: fixed; inset: 0; z-index: 2; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 14px;
    background: inherit; color: var(--frost);
    font-weight: 800; font-size: 22px; letter-spacing: 0.02em;
    pointer-events: none; transition: opacity .35s ease;
  }
  #fv-loading .flake { font-size: 44px; line-height: 1; color: var(--ice); animation: fvspin 2.4s linear infinite; }
  #fv-loading small { font-weight: 600; font-size: 13px; color: var(--frost-dim); letter-spacing: 0.08em; }
  #fv-loading.hide { opacity: 0; }
  @keyframes fvspin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { #fv-loading .flake { animation: none; } }
  #fv-error {
    display: none; position: fixed; z-index: 3; left: 16px; right: 16px;
    bottom: calc(16px + env(safe-area-inset-bottom, 0px)); padding: 12px 14px;
    border-radius: 12px; background: var(--panel); color: var(--panel-ink);
    font: 600 14px/1.45 var(--font); box-shadow: 0 4px 16px rgba(0,0,0,.35);
  }
  #fv-error small { display: block; margin-top: 4px; font-weight: 500; font-size: 12px; color: #5d6b80; word-break: break-all; }
  #fv-error button {
    margin: 10px 8px 0 0; padding: 9px 14px; border: 0; border-radius: 10px; font: 800 14px var(--font);
    color: #fff; background: #3d8be0; cursor: pointer;
  }
  #fv-error button.gray { background: #8e99a8; }
  /* landscape phone: ask to rotate (the game is portrait) */
  #fv-rotate {
    display: none; position: fixed; inset: 0; z-index: 4; flex-direction: column; align-items: center; justify-content: center;
    gap: 10px; background: var(--night); color: var(--frost); font-weight: 800; font-size: 20px; text-align: center;
  }
  #fv-rotate .phone { font-size: 46px; animation: fvrot 1.8s ease-in-out infinite; }
  #fv-rotate small { font-weight: 600; font-size: 13px; color: var(--frost-dim); }
  @keyframes fvrot { 0%, 30% { transform: rotate(-90deg); } 60%, 100% { transform: rotate(0deg); } }
  @media (orientation: landscape) and (max-height: 500px) and (pointer: coarse) { #fv-rotate { display: flex; } }
</style>
<div id="game"></div>
<div id="fv-loading"><div class="flake">❄</div><div>서리마을 개척기</div><small>FROST VILLAGE · 불러오는 중…</small></div>
<div id="fv-rotate"><div class="phone">📱</div><div>휴대폰을 세로로 돌려 주세요</div><small>Please rotate your phone to portrait</small></div>
<div id="fv-error" role="alert"></div>
<script>
  // Friendly messages: registered first and in the capture phase so a failed <script> load is seen too.
  // After boot only errors that actually stopped the game loop are reported (with Reload / Start over).
  (function () {
    var box = document.getElementById('fv-error'), shown = false;
    function show(msg, detail, crash) {
      if (shown || !box) return;
      shown = true;
      box.innerHTML = '';
      var p = document.createElement('div'); p.textContent = msg; box.appendChild(p);
      if (detail) { var d = document.createElement('small'); d.textContent = detail; box.appendChild(d); }
      var b = document.createElement('button'); b.textContent = '새로고침 · Reload'; b.onclick = function () { location.reload(); }; box.appendChild(b);
      if (crash) {
        var f = document.createElement('button'); f.className = 'gray'; f.textContent = '처음부터 하기 · Start over';
        f.onclick = function () {
          window.__FV_NO_SAVE = true;   // the crashed game must not write its state back while the page unloads
          try { var k = 'frostVillage.save.v1', v = localStorage.getItem(k); if (v) localStorage.setItem(k + '.bad', v); localStorage.removeItem(k); } catch (e) { /* */ }
          location.reload();
        };
        box.appendChild(f);
      }
      box.style.display = 'block';
    }
    window.__FV_SHOW_ERROR = show;
    function checkAlive(detail) {
      var g = window.__FV && window.__FV.game;
      if (!g || !g.loop) return;
      var f = g.loop.frame;
      setTimeout(function () {
        if (g.loop.frame === f && g.loop.running && document.visibilityState === 'visible') show('문제가 생겨서 게임이 멈췄어요. 새로고침 해 주세요.', detail, true);
      }, 1500);
    }
    window.addEventListener('error', function (e) {
      var el = e && e.target, isScript = el && el.tagName === 'SCRIPT';
      if (!isScript && !(e && e.message)) return;
      var detail = (e && e.message) || ('could not load ' + String(el && el.src).split('/').pop());
      if (!window.__FV_BOOTED) show('게임을 불러오지 못했어요. 새로고침 해 주세요.', detail);
      else checkAlive(detail);
    }, true);
    window.addEventListener('unhandledrejection', function (e) { if (window.__FV_BOOTED) checkAlive(String(e && e.reason)); });
    setTimeout(function () {
      if (!window.__FV_BOOTED) show('게임을 불러오지 못했어요. 새로고침 해 주세요.', 'The game files could not be loaded (blocked or offline).');
    }, 20000);
  })();
</script>
<script src="lib/phaser.min.js"></script>
<script src="game.js"></script>
`;

// ------------------------------------------------------------------ --inline: Phaser loader shim
// Runs after lib/phaser.min.js and the packs, before game.js. ES5 on purpose.
const INLINE_LOADER = `/* Frost Village inline-asset loader (generated by tools/build/build_artifact.mjs --inline).
   Phaser normally loads every file with XMLHttpRequest. Here the files come from window.__FV_PACK
   (packs/assets_N.js): JSON as objects, images as data: URIs, audio decoded from base64. */
(function () {
  var P = window.__FV_PACK;
  if (!P || !window.Phaser || !Phaser.Loader || !Phaser.Loader.FileTypesManager) return;
  var L = Phaser.Loader, FTM = L.FileTypesManager, orig = {};
  FTM.install(orig);
  var own = Object.prototype.hasOwnProperty;
  function has(u) { return typeof u === 'string' && own.call(P, u); }
  function res(u) { return has(u) ? P[u] : u; }
  FTM.register('json', function (key, url, dataKey, xhr) {
    return orig.json.call(this, key, typeof key === 'string' ? res(url) : url, dataKey, xhr);
  });
  FTM.register('image', function (key, url, xhr) {
    return orig.image.call(this, key, typeof key === 'string' ? res(url) : url, xhr);
  });
  FTM.register('spritesheet', function (key, url, cfg, xhr) {
    return orig.spritesheet.call(this, key, typeof key === 'string' ? res(url) : url, cfg, xhr);
  });
  FTM.register('atlas', function (key, tex, atlas, tx, ax) {
    if (typeof key === 'string') { tex = res(tex); atlas = res(atlas); }
    return orig.atlas.call(this, key, tex, atlas, tx, ax);
  });

  // Audio: decode the embedded mp3 with the game's AudioContext (works before the first tap).
  var InlineAudio = new Phaser.Class({
    Extends: L.File,
    initialize: function InlineAudio(loader, key, uri) {
      L.File.call(this, loader, { type: 'audio', cache: loader.cacheManager.audio, extension: 'mp3', key: key, url: 'inline/' + key + '.mp3' });
      this.uri = uri;
    },
    load: function () {
      var file = this, loader = this.loader, done = false;
      var sm = loader.systems.game.sound, ctx = sm && sm.context;
      this.state = L.FILE_LOADING;
      function ok(buf) { if (done) return; done = true; file.data = buf; file.state = L.FILE_LOADED; loader.nextFile(file, true); }
      function fail(e) { if (done) return; done = true; console.warn('[FrostVillage] could not decode audio ' + file.key, e && e.message); loader.nextFile(file, false); }
      try {
        var bin = atob(this.uri.slice(this.uri.indexOf(',') + 1)), n = bin.length, u8 = new Uint8Array(n);
        for (var i = 0; i < n; i++) u8[i] = bin.charCodeAt(i);
        var pr = ctx.decodeAudioData(u8.buffer, ok, fail);
        if (pr && pr.then) pr.then(ok, fail);
      } catch (e) { fail(e); }
    },
    onProcess: function () { this.state = L.FILE_PROCESSING; this.onProcessComplete(); }
  });
  FTM.register('audio', function (key, urls, config, xhr) {
    var sm = this.systems && this.systems.game && this.systems.game.sound;
    if (typeof key === 'string' && sm && sm.context) {
      var list = Array.isArray(urls) ? urls : [urls];
      for (var i = 0; i < list.length; i++) {
        if (has(list[i]) && String(P[list[i]]).indexOf('data:audio/') === 0) { this.addFile(new InlineAudio(this, key, P[list[i]])); return this; }
      }
    }
    return orig.audio.call(this, key, urls, config, xhr);
  });
})();
`;

const MIME = { '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.m4a': 'audio/mp4' };

/** move every file under OUT/assets into packs/assets_N.js; returns the pack paths (relative) */
function writePacks() {
  const files = walk(path.join(OUT, 'assets')).sort();
  const packs = [];
  let parts = [], bytes = 0;
  const flush = () => {
    if (!parts.length) return;
    const name = `packs/assets_${packs.length + 1}.js`;
    const body = '/* Frost Village assets (generated by tools/build/build_artifact.mjs --inline) */\n(function (P) {\n' + parts.join('\n') + '\n})(window.__FV_PACK = window.__FV_PACK || {});\n';
    fs.mkdirSync(path.join(OUT, 'packs'), { recursive: true });
    fs.writeFileSync(path.join(OUT, name), body);
    packs.push(name);
    parts = []; bytes = 0;
  };
  for (const f of files) {
    const r = rel(f), ext = path.extname(f).toLowerCase();
    const buf = fs.readFileSync(f);
    let val;
    if (ext === '.json') val = JSON.stringify(JSON.parse(buf.toString('utf8')));
    else if (MIME[ext]) val = JSON.stringify('data:' + MIME[ext] + ';base64,' + buf.toString('base64'));
    else { console.log('  (inline) skipped ' + r); continue; }
    if (bytes && bytes + buf.length > PACK_MAX) flush();
    parts.push('P[' + JSON.stringify(r) + ']=' + val + ';');
    bytes += buf.length;
  }
  flush();
  fs.rmSync(path.join(OUT, 'assets'), { recursive: true, force: true });
  return packs;
}

/** asset folders the game loads: the FRAGMENTS list in src/core/Assets.js */
function gameFragments() {
  const src = fs.readFileSync(path.join(ROOT, 'src', 'core', 'Assets.js'), 'utf8');
  const m = src.match(/export\s+const\s+FRAGMENTS\s*=\s*\[([^\]]*)\]/);
  const list = m ? (m[1].match(/['"]([a-z0-9_-]+)['"]/gi) || []).map((s) => s.slice(1, -1)) : [];
  return list.length ? list : ['characters', 'props', 'fx', 'ui', 'ground', 'audio'];
}

// ------------------------------------------------------------------ build
async function main() {
  const t0 = Date.now();
  const esbuild = loadEsbuild();
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  // 1) bundle the game into one classic script
  const res = await esbuild.build({
    entryPoints: [path.join(ROOT, 'src', 'main.js')],
    outfile: path.join(OUT, 'game.js'),
    bundle: true,
    format: 'iife',
    target: 'es2019',
    platform: 'browser',
    minify: MINIFY,
    legalComments: 'none',
    charset: 'ascii',            // Korean text as \\u escapes: safe whatever charset the host serves .js with
    logLevel: 'warning',
    banner: { js: '/* Frost Village - generated from src/ by tools/build/build_artifact.mjs. Do not edit this file: change src/ and rebuild. Phaser is loaded separately (lib/phaser.min.js, MIT licence). */' },
    metafile: true,
  });
  if (res.errors.length) throw new Error('esbuild failed');
  const bundled = Object.keys(res.metafile.inputs).length;

  // 2) copy lib/ and assets/
  const copied = [];
  const skipped = [];
  const copy = (src) => {
    const r = path.relative(ROOT, src).split(path.sep).join('/');
    if (JUNK.test(r)) { skipped.push(r + ' (not a game file)'); return; }
    if (!WEB_TYPES.has(path.extname(src).toLowerCase())) { skipped.push(r + ' (unsupported type)'); return; }
    const dst = path.join(OUT, r);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    copied.push(dst);
  };
  copy(path.join(ROOT, 'lib', 'phaser.min.js'));
  if (fs.existsSync(path.join(ROOT, 'lib', 'PHASER_LICENSE.md'))) copy(path.join(ROOT, 'lib', 'PHASER_LICENSE.md'));
  // only the asset folders the game actually loads (FRAGMENTS in src/core/Assets.js): folders that are
  // still being made (new characters, emotes, ...) stay out of the package until the game uses them
  const frags = gameFragments();
  for (const frag of frags) {
    const dir = path.join(ROOT, 'assets', frag);
    if (fs.existsSync(dir)) for (const f of walk(dir)) copy(f);
  }
  const notLoaded = fs.readdirSync(path.join(ROOT, 'assets'), { withFileTypes: true }).filter((e) => e.isDirectory() && !frags.includes(e.name)).map((e) => 'assets/' + e.name + '/');
  if (notLoaded.length) skipped.push(...notLoaded.map((d) => d + ' (not loaded by the game yet)'));

  // 2b) optional WebP re-encode of the copy
  if (WEBP) {
    try {
      const out = execFileSync(process.platform === 'win32' ? 'python' : 'python3', [path.join(HERE, 'webp_assets.py'), OUT, '90'], { encoding: 'utf8' });
      const r = JSON.parse(out.trim().split('\n').pop());
      if (r.error) throw new Error(r.error);
      console.log(`[build] --webp: ${r.converted} images as WebP, ${mb(r.png_bytes)} -> ${mb(r.webp_bytes)}`);
    } catch (e) {
      console.log('[build] --webp skipped (needs python3 with Pillow): ' + String(e.message || e).split('\n')[0]);
    }
  }

  // 3) the page (written in step 5 for --inline, once the packs exist)
  if (!INLINE) fs.writeFileSync(path.join(OUT, 'index.html'), PAGE);

  // 4) file-count limit: drop .ogg and point the audio manifest at .mp3 only
  let files = walk(OUT);
  let mp3Only = FORCE_MP3_ONLY;
  if (files.length > LIMITS.files) { mp3Only = true; console.log(`[build] ${files.length} files > ${LIMITS.files}: dropping .ogg copies`); }
  if (mp3Only) {
    const manPath = path.join(OUT, 'assets', 'audio', 'manifest.json');
    const man = JSON.parse(fs.readFileSync(manPath, 'utf8'));
    for (const k in man.audio || {}) {
      const a = man.audio[k];
      const mp3 = (a.files || []).filter((f) => /\.mp3$/i.test(f));
      if (mp3.length) a.files = mp3;
    }
    fs.writeFileSync(manPath, JSON.stringify(man, null, 1));
    for (const f of files) if (/\.ogg$/i.test(f)) fs.rmSync(f);
    files = walk(OUT);
  }

  // 5) checks: every manifest path exists, nothing absolute, no leftovers
  const problems = [];
  const referenced = new Set();
  for (const frag of gameFragments()) {
    const mp = path.join(OUT, 'assets', frag, 'manifest.json');
    if (!fs.existsSync(mp)) { problems.push('missing assets/' + frag + '/manifest.json'); continue; }
    referenced.add('assets/' + frag + '/manifest.json');
    const j = JSON.parse(fs.readFileSync(mp, 'utf8'));
    const paths = [];
    for (const kind of ['atlases', 'images', 'spritesheets']) for (const a of j[kind] || []) paths.push(a.png, a.json);
    for (const k in j.audio || {}) paths.push(...(j.audio[k].files || []));
    for (const p of paths.filter(Boolean)) {
      if (/^(\/|[a-z]+:)/i.test(p)) problems.push(`absolute URL in ${frag}/manifest.json: ${p}`);
      const fp = path.join(OUT, 'assets', p);
      referenced.add('assets/' + p);
      if (!fs.existsSync(fp)) problems.push(`assets/${p} is listed in ${frag}/manifest.json but missing`);
    }
  }
  const unreferenced = files.map(rel).filter((r) => r.startsWith('assets/') && !referenced.has(r));
  if (INLINE) {   // (after the manifest checks, which need the loose files)
    const packs = writePacks();
    fs.writeFileSync(path.join(OUT, 'inline_loader.js'), INLINE_LOADER);
    const tags = packs.map((p) => `<script src="${p}"></script>`).concat('<script src="inline_loader.js"></script>', '<script src="game.js"></script>').join('\n');
    fs.writeFileSync(path.join(OUT, 'index.html'), PAGE.replace('<script src="game.js"></script>', tags));
    files = walk(OUT);
    console.log(`[build] --inline: assets embedded into ${packs.length} pack scripts`);
  }
  const page = fs.readFileSync(path.join(OUT, 'index.html'), 'utf8');
  if (/<!doctype|<html[\s>]|<head[\s>]|<body[\s>]/i.test(page)) problems.push('index.html contains doctype/html/head/body tags');
  if (!/^<title>[^<]+<\/title>/.test(page)) problems.push('index.html must start with <title>');
  const gameJs = fs.readFileSync(path.join(OUT, 'game.js'), 'utf8');
  if (/\bimport\s*\(|\bimport\.meta\b|^\s*(import|export)\s/m.test(gameJs)) problems.push('game.js still contains import/export syntax');

  // 6) report
  const sizes = files.map((f) => ({ p: rel(f), s: fs.statSync(f).size })).sort((a, b) => b.s - a.s);
  const total = sizes.reduce((n, x) => n + x.s, 0);
  for (const x of sizes) if (x.s > LIMITS.perFile) problems.push(`${x.p} is ${mb(x.s)} (> 16 MB per file)`);
  if (sizes.length > LIMITS.files) problems.push(`${sizes.length} files (> ${LIMITS.files})`);
  if (total > LIMITS.total) problems.push(`total ${mb(total)} (> 64 MB)`);

  const supporting = sizes.map((x) => x.p).filter((p) => p !== 'index.html').sort();
  fs.writeFileSync(LIST_OUT, JSON.stringify({
    page: path.relative(path.dirname(ROOT), path.join(OUT, 'index.html')).split(path.sep).join('/'),
    root: path.relative(path.dirname(ROOT), OUT).split(path.sep).join('/'),
    files: supporting,
    note: 'Publish: Artifact({ file_path: page, root, files }). Supporting paths are relative to root.',
  }, null, 1));

  const byExt = {};
  for (const x of sizes) { const e = path.extname(x.p) || x.p; (byExt[e] = byExt[e] || { n: 0, s: 0 }).n++; byExt[e].s += x.s; }
  // bytes a browser actually downloads: one audio format, not both
  const audioUsed = mp3Only ? 0 : (byExt['.mp3'] ? byExt['.mp3'].s : 0);
  const downloaded = total - audioUsed - (byExt['.md'] ? byExt['.md'].s : 0);

  console.log(`\n[build] Frost Village artifact -> ${path.relative(process.cwd(), OUT) || OUT}`);
  console.log(`  game.js: ${bundled} source modules bundled (${MINIFY ? 'minified' : 'readable'}), ${mb(fs.statSync(path.join(OUT, 'game.js')).size)}`);
  console.log(`  audio: ${mp3Only ? '.mp3 only (manifest rewritten)' : '.ogg + .mp3 (browser picks one)'}`);
  console.log('  by type: ' + Object.entries(byExt).sort((a, b) => b[1].s - a[1].s).map(([e, v]) => `${e} ${v.n} (${mb(v.s)})`).join(', '));
  console.log('  biggest files:');
  for (const x of sizes.slice(0, 10)) console.log(`    ${mb(x.s).padStart(9)}  ${x.p}`);
  if (skipped.length) console.log('  skipped: ' + skipped.join(', '));
  if (unreferenced.length) console.log('  copied but not listed in any manifest: ' + unreferenced.join(', '));
  console.log(`\n  FILES: ${sizes.length} (limit ${LIMITS.files})   TOTAL: ${mb(total)} (limit 64 MB)   largest: ${mb(sizes[0].s)} (limit 16 MB)`);
  console.log(`  a first visit downloads about ${mb(downloaded)} (one audio format)`);
  console.log(`  file list for the Artifact tool: ${path.relative(process.cwd(), LIST_OUT)}`);
  if (problems.length) {
    console.log('\n[build] PROBLEMS:\n  - ' + problems.join('\n  - '));
    process.exit(2);
  }
  console.log(`[build] OK in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
}

main().catch((e) => { console.error('[build] FAILED:', e && e.stack || e); process.exit(1); });
