// Platform checks: Canvas-renderer fallback (WebGL unavailable / blocklisted GPU), decoded audio
// memory, texture inventory, designer balance.js edge values (payDuration 0, fractional prices,
// autosaveEvery 0).
//   node tools/test/review_robust_platform.mjs [only=<name>]
import { loadPlaywright } from './pw.mjs';
import { newPage, bootToGame, launch, start, sleep, writeJSON, OUT } from './review_robust_lib.mjs';

const only = (process.argv.find((a) => a.startsWith('only=')) || '').slice(5);
const run = (n) => !only || only === n;
const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const results = {};

// ---------------------------------------------------------------- A. canvas fallback
if (run('canvas')) {
  const { chromium } = loadPlaywright();
  const b = await chromium.launch({ headless: true, args: ['--disable-webgl', '--disable-3d-apis', '--no-sandbox'] });
  const { page, ctx, log } = await newPage(b);
  const r = {};
  try {
    await page.goto(URL, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), null, { timeout: 40000 });
    await sleep(800);
    r.renderer = await page.evaluate(() => ({ type: window.__FV.game.renderer.type, isCanvas: window.__FV.game.renderer.type === Phaser.CANVAS }));
    await page.screenshot({ path: `${OUT}/canvas_title.jpg`, type: 'jpeg', quality: 60 });
    await bootToGame(page, URL, { fresh: false });
    await page.evaluate(() => { window.__FV.give(500); window.__FV.unlockAll(); const p = window.__FV.where('shelf'); window.__FV.teleport(p.x, p.y + 60); });
    await sleep(2500);
    await page.screenshot({ path: `${OUT}/canvas_game.jpg`, type: 'jpeg', quality: 60 });
    r.perf = await page.evaluate(async () => {
      const g = window.__FV.game, R = { upd: [], ren: [] };
      const su = g.scene.update.bind(g.scene), sr = g.scene.render.bind(g.scene);
      g.scene.update = function (t, d) { const a = performance.now(); su(t, d); R.upd.push(performance.now() - a); };
      g.scene.render = function (x) { const a = performance.now(); sr(x); R.ren.push(performance.now() - a); };
      const f0 = g.loop.frame, t0 = performance.now();
      await new Promise((r) => setTimeout(r, 8000));
      const avg = (a) => +(a.reduce((x, y) => x + y, 0) / Math.max(1, a.length)).toFixed(2);
      const p95 = (a) => { const s = a.slice().sort((x, y) => x - y); return +(s[Math.floor(s.length * 0.95)] || 0).toFixed(2); };
      return { fps: +((g.loop.frame - f0) / ((performance.now() - t0) / 1000)).toFixed(1), logicAvg: avg(R.upd), renderAvg: avg(R.ren), renderP95: p95(R.ren) };
    });
    await page.evaluate(() => window.__FV.game.scene.getScene('UI').openSettings());
    await sleep(600);
    await page.screenshot({ path: `${OUT}/canvas_settings.jpg`, type: 'jpeg', quality: 60 });
  } catch (e) { r.error = e.message.split('\n')[0]; }
  r.errors = log.errors.slice(0, 6); r.warnings = [...new Set(log.warnings)].slice(0, 6);
  results.canvas = r;
  console.log('canvas', JSON.stringify(r));
  await b.close();
}

const browser = await launch();

// ---------------------------------------------------------------- B. memory: decoded audio + textures (WebGL)
if (run('memory')) {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await page.evaluate(() => window.__FV.unlockAll());
  await sleep(1000);
  results.memory = await page.evaluate(() => {
    const g = window.__FV.game;
    let audioBytes = 0; const aud = [];
    for (const k of g.cache.audio.getKeys()) { const b = g.cache.audio.get(k); if (b && b.length) { const by = b.length * b.numberOfChannels * 4; audioBytes += by; aud.push([k, +(by / 1048576).toFixed(2), b.numberOfChannels, b.sampleRate]); } }
    aud.sort((a, b) => b[1] - a[1]);
    let texBytes = 0, canvasBytes = 0, n = 0, maxDim = 0, big = [];
    const textList = [];
    for (const k of g.textures.getTextureKeys()) {
      const t = g.textures.get(k);
      for (const s of t.source) { n++; const by = s.width * s.height * 4; texBytes += by; if (s.isCanvas) canvasBytes += by; maxDim = Math.max(maxDim, s.width, s.height); if (by > 2e6) big.push([k, s.width, s.height, s.isCanvas ? 'canvas' : 'image']); }
    }
    // Text objects each own a canvas texture (not listed in the texture manager)
    let textBytes = 0, texts = 0;
    for (const sc of g.scene.getScenes(true)) for (const o of sc.children.list) {
      const walk = (x) => { if (x.type === 'Text') { texts++; textBytes += x.canvas.width * x.canvas.height * 4; } if (x.list) x.list.forEach(walk); };
      walk(o);
    }
    const gl = g.renderer.gl;
    return {
      decodedAudioMB: +(audioBytes / 1048576).toFixed(1), topAudio: aud.slice(0, 6),
      textureSources: n, textureMB_GPU_estimate: +(texBytes / 1048576).toFixed(1), canvasTextureMB: +(canvasBytes / 1048576).toFixed(1), maxDim, bigTextures: big,
      textObjects: texts, textCanvasMB: +(textBytes / 1048576).toFixed(1),
      glMaxTexture: gl && gl.getParameter(gl.MAX_TEXTURE_SIZE),
      canvasInternal: [g.canvas.width, g.canvas.height],
    };
  });
  console.log('memory', JSON.stringify(results.memory));
  await ctx.close();
}

// ---------------------------------------------------------------- C. designer balance.js edge values
async function withBalance(name, edits, fn) {
  if (!run(name)) return;
  const { page, ctx, log } = await newPage(browser);
  await page.route('**/src/data/balance.js', async (route) => {
    const resp = await route.fetch();
    let body = await resp.text();
    for (const [a, b] of edits) { if (!a.test(body)) console.log('  (pattern not found)', a); body = body.replace(a, b); }
    await route.fulfill({ response: resp, body });
  });
  const r = {};
  try {
    await bootToGame(page, URL);
    await page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(false); });
    r.out = await page.evaluate(fn);
  } catch (e) { r.error = e.message.split('\n')[0]; }
  r.errors = log.errors.slice(0, 4);
  results[name] = r;
  console.log(name, JSON.stringify(r));
  await ctx.close();
}
const waitFrames = `const W = (n) => new Promise((r) => { const g = window.__FV.game, f0 = g.loop.frame; const iv = setInterval(() => { if (g.loop.frame - f0 >= n) { clearInterval(iv); r(); } }, 16); });`;

await withBalance('payDuration0', [[/payDuration: 1\.6,/, 'payDuration: 0,']], new Function(`return (async () => { ${waitFrames}
  const FV = window.__FV; FV.give(100);
  const pad = FV.scene.progress.pads.hire_fisherman; FV.teleport(pad.x, pad.y);
  await W(240);
  return { coins: FV.state().coins, paid: pad.paid, acc: String(pad.acc), hired: FV.state().done.includes('hire_fisherman') };
})()`));

await withBalance('fractionalPrice', [[/item_fish_cooked: 4,/, 'item_fish_cooked: 4.5,']], new Function(`return (async () => { ${waitFrames}
  const FV = window.__FV, gs = FV.scene;
  for (let i = 0; i < 12; i++) gs.market.stock.push('item_fish_cooked', null, gs.effects);
  await W(400);
  const cash = gs.market.cash.value;
  const c = FV.where('cash'); FV.teleport(c.x, c.y); await W(60);
  return { cashBeforeCollect: cash, coinsAfterCollect: FV.state().coins, lostFraction: +(cash - FV.state().coins).toFixed(3) };
})()`));

await withBalance('autosave0', [[/autosaveEvery: 5,/, 'autosaveEvery: 0,']], new Function(`return (async () => { ${waitFrames}
  let n = 0; const o = Storage.prototype.setItem; Storage.prototype.setItem = function (...a) { n++; return o.apply(this, a); };
  const g = window.__FV.game, f0 = g.loop.frame; await W(120);
  return { setItemCallsPerFrame: +(n / (g.loop.frame - f0)).toFixed(2), bytes: localStorage.getItem('frostVillage.save.v1').length };
})()`));

writeJSON('platform_results.json', results);
await browser.close(); await srv.close();
