// Corrupted / odd save variants, fast path: one boot, then for each variant write the raw save into
// localStorage and restart the Game scene (Game.create is the only reader of the save).
// A variant that crashes Game.create triggers a full page reload to confirm the crash survives reloads.
//   node tools/test/review_robust_save_fast.mjs
import { newPage, bootToGame, launch, start, sleep, writeJSON, OUT } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const browser = await launch();
const KEY = 'frostVillage.save.v1';
const base = { v: 1, t: Date.now(), coins: 120, progress: { done: { hire_fisherman: true }, paid: {}, up: { capacity: 0, speed: 0 } }, stations: {}, market: { stock: {}, cash: 0 }, trade: { stock: {}, cash: 0 }, player: { x: 900, y: 1150, stack: [] } };
const J = (o) => JSON.stringify(o);
const variants = {
  oldVersion0: J({ ...base, v: 0, coins: 999 }),
  futureVersion2: J({ ...base, v: 2, coins: 999 }),
  coinsString: J({ ...base, coins: 'abc' }),
  coinsNumString: J({ ...base, coins: '250' }),
  coinsNegative: J({ ...base, coins: -500 }),
  coinsFloat: J({ ...base, coins: 12.7 }),
  coinsHuge: J({ ...base, coins: 1e308 }),
  playerXString: J({ ...base, player: { x: 'abc', y: 1150, stack: [] } }),
  playerXNull: J({ ...base, player: { x: null, y: null, stack: [] } }),
  playerOffWorld: J({ ...base, player: { x: -5000, y: 99999, stack: [] } }),
  stackString: J({ ...base, player: { x: 900, y: 1150, stack: 'item_fish_raw' } }),
  stackBadTypes: J({ ...base, player: { x: 900, y: 1150, stack: ['item_fish_raw', 5, null, 'nope'] } }),
  stackTooBig: J({ ...base, player: { x: 900, y: 1150, stack: Array(500).fill('item_log') } }),
  upgradeNegative: J({ ...base, progress: { ...base.progress, up: { capacity: -1, speed: -1 } } }),
  upgradeString: J({ ...base, progress: { ...base.progress, up: { capacity: 'x', speed: 'y' } } }),
  upgradeFloat: J({ ...base, progress: { ...base.progress, up: { capacity: 1.5, speed: 0.5 } } }),
  paidNegative: J({ ...base, progress: { ...base.progress, paid: { zone_forest: -500 } } }),
  progressNull: J({ ...base, progress: null }),
  doneArray: J({ ...base, progress: { done: ['hire_fisherman'], paid: {}, up: {} } }),
  doneSkipAhead: J({ ...base, progress: { done: { hire_hunter: true, hire2_miner: true }, paid: {}, up: {} } }),
  stationsWeird: J({ ...base, stations: { grill: { i: 'abc', o: 1e9 }, bogus: { i: 3 } } }),
  marketBadStock: J({ ...base, market: { stock: { item_fish_cooked: 'lots', item_log: 5 }, cash: 'NaN' } }),
  marketStockArray: J({ ...base, market: { stock: [3, 4], cash: 10 } }),
  marketCashString: J({ ...base, market: { stock: {}, cash: '15' } }),
  cashHuge: J({ ...base, market: { stock: {}, cash: 1e15 } }),
  stackObject: J({ ...base, player: { x: 900, y: 1150, stack: {} } }),
  marketNull: J({ ...base, market: { stock: null, cash: null }, trade: null }),
};

const { page, ctx, log } = await newPage(browser);
await bootToGame(page, URL);
const hide = () => page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) { const s = g.scene.getScene(k); if (s && s.cameras && s.cameras.main) s.cameras.main.setVisible(false); } });
await hide();
const from = (process.argv.find((a) => a.startsWith('from=')) || '').slice(5);
let results = {};
try { if (from) results = JSON.parse((await import('node:fs')).readFileSync(OUT + '/save_fast_results.json', 'utf8')); } catch (e) { /* */ }
let started = !from;
for (const [name, raw] of Object.entries(variants)) {
  if (!started) { if (name === from) started = true; else continue; }
  const errBefore = log.errors.length;
  const r = await page.evaluate(async ([k, raw]) => {
    const FV = window.__FV, g = FV.game;
    const frames = (n, cond) => new Promise((res, rej) => { const f0 = g.loop.frame, t0 = performance.now(); const iv = setInterval(() => { if (g.loop.frame - f0 >= n || (cond && cond())) { clearInterval(iv); res(g.loop.frame - f0); } else if (performance.now() - t0 > 20000) { clearInterval(iv); rej(new Error('LOOP DEAD: frame counter stuck at ' + g.loop.frame + ' for 20 s')); } }, 16); });
    try { localStorage.setItem(k, raw); } catch (e) { /* */ }
    const gs0 = g.scene.getScene('Game');
    g.scene.stop('UI');
    gs0.scene.restart({ fresh: false });
    await frames(20);
    const gs = g.scene.getScene('Game');
    const out = { gameStatus: gs.sys.settings.status, uiActive: g.scene.isActive('UI') };
    if (!g.scene.isActive('UI') || !FV.state) return out;
    for (const sc of ['Game', 'UI']) g.scene.getScene(sc).cameras.main.setVisible(false);
    const s0 = FV.state();
    Object.assign(out, { coins: s0.coins, coinsIsNaN: Number.isNaN(gs.economy.coins), hud: g.scene.getScene('UI').coinText.text, pos: [s0.player.x, s0.player.y], cap: s0.player.capacity, speed: gs.player.speed, stack: s0.player.stack.length, stackTypes: [...new Set(s0.player.stack)].slice(0, 6), done: s0.done, workers: s0.workers.length, market: s0.market, trade: s0.trade, grill: s0.stations.grill, padPaid: Object.fromEntries(Object.entries(gs.progress.pads).map(([id, p]) => [id, p.paid + '/' + p.cost + ' ' + p.costText.text])) });
    // can the chief move?
    const p0 = { x: gs.player.x, y: gs.player.y };
    FV.setInput(1, 0.3); await frames(30); FV.setInput(0, 0);
    out.moved = Math.round(Math.hypot(gs.player.x - p0.x, gs.player.y - p0.y));
    out.posAfter = [gs.player.x, gs.player.y].map((v) => (Number.isFinite(v) ? Math.round(v) : String(v)));
    out.camScroll = [gs.cameras.main.scrollX, gs.cameras.main.scrollY].map((v) => (Number.isFinite(v) ? Math.round(v) : String(v)));
    // can the chief gather?
    FV.clearStack();
    const n = FV.where('net'); FV.teleport(n.x, n.y);
    out.gatherFrames = await frames(240, () => FV.state().player.stack.length >= 2);
    out.gathered = FV.state().player.stack.length;
    // can the chief earn? put 3 cooked fish on the shelf and wait for a sale, then collect
    for (let i = 0; i < 3; i++) gs.market.stock.push('item_fish_cooked', null, gs.effects);
    await frames(240, () => gs.market.cash.value > 0 && !Number.isNaN(gs.market.cash.value));
    out.marketCashAfterSale = String(gs.market.cash.value);
    const c = FV.where('cash'); FV.teleport(c.x, c.y); await frames(40);
    out.coinsAfterCollect = String(gs.economy.coins);
    // what does the next save look like?
    FV.save();
    try { const sv = JSON.parse(localStorage.getItem(k)); out.savedBack = { v: sv.v, coins: sv.coins, cash: sv.market && sv.market.cash, pos: [sv.player.x, sv.player.y], stackLen: sv.player.stack.length, up: sv.progress.up, paid: sv.progress.paid }; } catch (e) { out.savedBack = 'unreadable ' + e.message; }
    out.warnings = FV.warnings();
    return out;
  }, [KEY, raw]).catch((e) => ({ evalError: e.message.split('\n')[0] }));
  r.errors = log.errors.slice(errBefore).map((e) => e.slice(0, 220));
  if (r.evalError && /LOOP DEAD/.test(r.evalError)) r.loopDead = true;
  if (!r.uiActive || r.loopDead) {
    // crashed: does it survive a full reload (the bad save is still there)?
    await page.screenshot({ path: `${OUT}/savefast_${name}_crash.jpg`, type: 'jpeg', quality: 60 });
    await page.reload({ waitUntil: 'load' });
    try {
      await page.waitForFunction(() => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), null, { timeout: 90000 });
      await sleep(300);
      const c = await page.$('canvas'); const b = await c.boundingBox();
      await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height * 0.6);
      await sleep(8000);
      r.afterReload = await page.evaluate(() => ({ uiActive: window.__FV.game.scene.isActive('UI'), gameStatus: window.__FV.game.scene.getScene('Game').sys.settings.status, saveStillThere: !!localStorage.getItem('frostVillage.save.v1') }));
      await page.screenshot({ path: `${OUT}/savefast_${name}_after_reload.jpg`, type: 'jpeg', quality: 60 });
    } catch (e) { r.afterReload = 'error ' + e.message.split('\n')[0]; }
    r.errorsAfterReload = log.errors.slice(errBefore + r.errors.length).map((e) => e.slice(0, 220));
    // recover for the next variant
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: 'load' });
    await bootToGame(page, URL, { fresh: false });
    await hide();
  }
  results[name] = { raw: raw.slice(0, 160), ...r };
  console.log(name, JSON.stringify(r));
  writeJSON('save_fast_results.json', results);
}
await browser.close(); await srv.close();
