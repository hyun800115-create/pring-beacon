// Long soak with everything unlocked + an in-page "player bot" that keeps the economy moving
// (take products -> sell -> collect cash -> upgrades). Samples object counts, tweens, timers,
// sounds, listeners, JS heap (after forced GC), per-frame logic/render cost every 30 s.
//   node tools/test/review_robust_soak.mjs [seconds=720]
import { newPage, bootToGame, launch, start, sleep, writeJSON, OUT } from './review_robust_lib.mjs';

const secs = Number(process.argv[2] || 720);
const NORENDER = process.argv.includes('--norender');   // hide cameras: many more frames per wall second (logic soak)
const TAG = NORENDER ? 'soak_norender' : 'soak';
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await newPage(browser, { viewport: { width: 390, height: 844 }, dpr: 1 });
const cdp = await page.context().newCDPSession(page);
await cdp.send('Performance.enable');
await cdp.send('HeapProfiler.enable');

await bootToGame(page, srv.url + 'index.html');
await page.evaluate(() => { window.__FV.give(200); window.__FV.unlockAll(); window.__FV.teleport(900, 1300); });
if (NORENDER) await page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(false); });

// ---- in-page instrumentation + bot
await page.evaluate(() => {
  const g = window.__FV.game, gs = window.__FV.scene;
  const R = window.__RV = { upd: [], ren: [], gsUpd: [], frames: 0, soundPlays: 0, playsByKey: {}, botLog: [] };
  const su = g.scene.update.bind(g.scene), sr = g.scene.render.bind(g.scene);
  g.scene.update = function (t, d) { const a = performance.now(); su(t, d); R.upd.push(performance.now() - a); R.frames++; };
  g.scene.render = function (r) { const a = performance.now(); sr(r); R.ren.push(performance.now() - a); };
  const gu = gs.sys.sceneUpdate;
  gs.sys.sceneUpdate = function (t, d) { const a = performance.now(); gu.call(this, t, d); R.gsUpd.push(performance.now() - a); };
  const sp = g.sound.play.bind(g.sound);
  g.sound.play = function (k, c) { R.soundPlays++; R.playsByKey[k] = (R.playsByKey[k] || 0) + 1; return sp(k, c); };

  // bot
  const FOODS = ['item_fish_cooked', 'item_bread', 'item_meat_cooked'];
  const W = (n) => window.__FV.where(n);
  let plan = [], cur = null, lastPos = null, stuckT = 0, waitT = 0;
  const st = () => window.__FV.state();
  function newPlan() {
    const s = st();
    // pick the station with the largest output
    const ids = Object.keys(s.stations).filter((k) => s.stations[k].out > 0).sort((a, b) => s.stations[b].out - s.stations[a].out);
    plan = [];
    if (ids.length) plan.push({ to: ids[0] + 'Out', until: () => { const q = st(); return q.player.stack.length >= q.player.capacity || q.stations[ids[0]].out === 0; }, max: 4000 });
    plan.push({ to: 'shelf', until: () => !st().player.stack.some((x) => FOODS.includes(x)), max: 3500 });
    plan.push({ to: 'tradeShelf', until: () => st().player.stack.length === 0, max: 3500 });
    plan.push({ to: 'cash', until: () => st().market.cash === 0, max: 1500 });
    plan.push({ to: 'tradeCash', until: () => st().trade.cash === 0, max: 1500 });
    if (Math.random() < 0.3) plan.push({ to: Math.random() < 0.5 ? 'up_capacity' : 'up_speed', until: () => false, max: 2500 });
  }
  setInterval(() => {
    if (!window.__RV_BOT) { window.__FV.setInput(0, 0); return; }
    if (!cur) { if (!plan.length) newPlan(); cur = plan.shift(); cur.t0 = performance.now(); cur.arrived = false; }
    const p = gs.player, tg = W(cur.to);
    if (!tg) { cur = null; return; }
    const dx = tg.x - p.x, dy = tg.y - p.y, d = Math.hypot(dx, dy * 2);
    if (!cur.arrived) {
      if (d < 16) { cur.arrived = true; cur.ta = performance.now(); window.__FV.setInput(0, 0); return; }
      const l = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 50);
      window.__FV.setInput((dx / l) * k, (dy / l) * k);
      if (lastPos && Math.hypot(p.x - lastPos.x, p.y - lastPos.y) < 0.8) stuckT += 50; else stuckT = 0;
      lastPos = { x: p.x, y: p.y };
      if (stuckT > 2500 || performance.now() - cur.t0 > 15000) { window.__FV.teleport(tg.x, tg.y); stuckT = 0; R.botLog.push('teleport ' + cur.to); }
    } else {
      window.__FV.setInput(0, 0);
      if (cur.until() || performance.now() - cur.ta > cur.max) cur = null;
    }
  }, 50);
  window.__RV_BOT = true;
});

const pct = (a, q) => { if (!a.length) return 0; const s = a.slice().sort((x, y) => x - y); return +s[Math.min(s.length - 1, Math.floor(q * s.length))].toFixed(2); };
const avg = (a) => (a.length ? +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(2) : 0);
const samples = [];
const t0 = Date.now();
let i = 0;
while (Date.now() - t0 < secs * 1000) {
  await sleep(30000);
  i++;
  const inPage = await page.evaluate(() => {
    const R = window.__RV, g = window.__FV.game, gs = window.__FV.scene, ui = g.scene.getScene('UI');
    const st = window.__FV.state();
    const types = {};
    let visible = 0;
    for (const o of gs.children.list) { types[o.type] = (types[o.type] || 0) + 1; if (o.visible) visible++; }
    const texKeys = g.textures.getTextureKeys();
    let canvasTex = 0, canvasPx = 0;
    for (const k of texKeys) { const t = g.textures.get(k); const s = t.source[0]; if (s && s.isCanvas) { canvasTex++; canvasPx += s.width * s.height; } }
    const evCount = (em) => { if (!em || !em.eventNames) return -1; let n = 0; for (const e of em.eventNames()) n += em.listenerCount(e); return n; };
    const out = {
      gameTime: Math.round(gs.time.now / 1000), frames: R.frames,
      upd: R.upd.splice(0), ren: R.ren.splice(0), gsUpd: R.gsUpd.splice(0),
      children: gs.children.length, visible, types, uiChildren: ui.children.length,
      tweens: gs.tweens.getTweens().length, uiTweens: ui.tweens.getTweens().length,
      timers: gs.time._active.length + gs.time._pendingInsertion.length, uiTimers: ui.time._active.length,
      sounds: g.sound.sounds.length, playing: g.sound.sounds.filter((s) => s.isPlaying).length, soundPlays: R.soundPlays,
      ctx: g.sound.context && g.sound.context.state,
      itemPool: gs.effects.itemPool.length, sheetPool: gs.effects.sheetPool.length, textPool: gs.effects.textPool.length,
      agents: gs.agents.length, queue: gs.market.queue.length, leaving: gs.market.leaving.length, workers: gs.workers.length,
      workerStates: st.workers.map((w) => w.type[0] + w.state[0]).join(''),
      stations: Object.values(st.stations).map((v) => v.in + '>' + v.out).join(' '),
      coins: st.coins, coinsInt: Number.isInteger(st.coins), cash: [st.market.cash, st.trade.cash], stock: [st.market.stock, st.trade.stock],
      up: st.upgrades, cap: st.player.capacity,
      textures: texKeys.length, canvasTex, canvasMPx: +(canvasPx / 1e6).toFixed(2),
      emitters: { gameEvents: evCount(g.events), gsEvents: evCount(gs.events), gsSys: evCount(gs.sys.events), scale: evCount(g.scale), anims: evCount(g.anims), sound: evCount(g.sound), input: evCount(ui.input) },
      bot: R.botLog.splice(0).length,
      leavingPos: gs.market.leaving.map((c) => [Math.round(c.x), Math.round(c.y), c.state, c.path.length]),
      shelf: { m: gs.market.stock.count, t: gs.trade.stock.count, mp: gs.market.cash.pile.count, tp: gs.trade.cash.pile.count },
      playsByKey: Object.assign({}, R.playsByKey),
    };
    R.playsByKey = {};
    return out;
  });
  const m1 = await cdp.send('Performance.getMetrics');
  const met = Object.fromEntries(m1.metrics.map((x) => [x.name, x.value]));
  const h0 = await cdp.send('Runtime.getHeapUsage');
  await cdp.send('HeapProfiler.collectGarbage');
  const h1 = await cdp.send('Runtime.getHeapUsage');
  const s = {
    i, wall: Math.round((Date.now() - t0) / 1000), gameTime: inPage.gameTime, framesTotal: inPage.frames,
    fps: +(inPage.upd.length / 30).toFixed(1),
    logicMs: { avg: avg(inPage.upd), p95: pct(inPage.upd, 0.95), max: pct(inPage.upd, 1) },
    gameUpdMs: { avg: avg(inPage.gsUpd), p95: pct(inPage.gsUpd, 0.95) },
    renderMs: { avg: avg(inPage.ren), p95: pct(inPage.ren, 0.95) },
    heapMB: +(h0.usedSize / 1048576).toFixed(2), heapAfterGcMB: +(h1.usedSize / 1048576).toFixed(2),
    jsListeners: met.JSEventListeners, nodes: met.Nodes,
    ...Object.fromEntries(Object.entries(inPage).filter(([k]) => !['upd', 'ren', 'gsUpd', 'frames', 'gameTime'].includes(k))),
  };
  samples.push(s);
  console.log(JSON.stringify({ i: s.i, wall: s.wall, gt: s.gameTime, fps: s.fps, logic: s.logicMs, gsUpd: s.gameUpdMs, render: s.renderMs, heapGc: s.heapAfterGcMB, heap: s.heapMB, listeners: s.jsListeners, children: s.children, vis: s.visible, tweens: s.tweens, timers: s.timers, sounds: s.sounds, playing: s.playing, plays: s.soundPlays, pool: s.itemPool, sheetPool: s.sheetPool, agents: s.agents, q: s.queue, leaving: s.leaving, coins: s.coins, int: s.coinsInt, tex: s.textures, emit: s.emitters, up: s.up, shelf: s.shelf, lv: s.leavingPos, st: s.stations, ws: s.workerStates, bot: s.bot }));
  writeJSON(TAG + '_samples.json', { samples, errors: log.errors, warnings: log.warnings });
}
await page.evaluate(() => { window.__RV_BOT = false; });
if (NORENDER) await page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(true); });
await sleep(1500);
await page.screenshot({ path: OUT + '/' + TAG + '_end.jpg', type: 'jpeg', quality: 70 });
// texture inventory at the end
const tex = await page.evaluate(() => {
  const g = window.__FV.game, out = [];
  for (const k of g.textures.getTextureKeys()) {
    const t = g.textures.get(k);
    for (const s of t.source) out.push({ key: k, w: s.width, h: s.height, canvas: !!s.isCanvas, mpx: +(s.width * s.height / 1e6).toFixed(3) });
  }
  return out.sort((a, b) => b.mpx - a.mpx);
});
writeJSON(TAG + '_samples.json', { samples, textures: tex, errors: log.errors, warnings: log.warnings, failedReq: log.failedReq });
console.log('errors', log.errors.length, log.errors.slice(0, 8).join('\n'));
console.log('warnings', log.warnings.length, [...new Set(log.warnings)].slice(0, 12).join('\n'));
console.log('top textures', JSON.stringify(tex.slice(0, 15)));
await browser.close(); await srv.close();
