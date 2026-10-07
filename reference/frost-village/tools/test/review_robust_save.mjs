// Save / load robustness: throwing localStorage, corrupted & old saves, upgrade-pad stale "paid",
// designer lowering a cost below a saved partial payment, cost 0, reload during payment,
// reload mid-transfer (item conservation), reset flow.
//   node tools/test/review_robust_save.mjs [only=<name>]
import { newPage, bootToGame, launch, start, sleep, waitFor, tapStart, writeJSON, OUT } from './review_robust_lib.mjs';

const only = (process.argv.find((a) => a.startsWith('only=')) || '').slice(5);
const skip = ((process.argv.find((a) => a.startsWith('skip=')) || '').slice(5)).split(',').filter(Boolean);
const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const browser = await launch();
const results = {};
const KEY = 'frostVillage.save.v1';

async function probe(page) {
  return page.evaluate(async () => {
    const FV = window.__FV, gs = FV.scene;
    const frames = (n, cond) => new Promise((r) => { const f0 = FV.game.loop.frame; const iv = setInterval(() => { if (FV.game.loop.frame - f0 >= n || (cond && cond())) { clearInterval(iv); r(FV.game.loop.frame - f0); } }, 16); });
    const s0 = FV.state();
    const p0 = { x: gs.player.x, y: gs.player.y };
    FV.setInput(1, 0.3);
    await frames(30);
    FV.setInput(0, 0);
    const p1 = { x: gs.player.x, y: gs.player.y };
    // try to gather at the net
    FV.clearStack();
    const n = FV.where('net');
    FV.teleport(n.x, n.y);
    const gatherFrames = await frames(240, () => FV.state().player.stack.length >= 2);
    const s1 = FV.state();
    return {
      coins: s0.coins, coinsType: typeof s0.coins, coinsNaN: Number.isNaN(s0.coins),
      hudText: FV.game.scene.getScene('UI').coinText.text,
      player0: s0.player, moved: Math.round(Math.hypot(p1.x - p0.x, p1.y - p0.y)), posNaN: Number.isNaN(p1.x) || Number.isNaN(p1.y),
      capacity: s0.player.capacity, gathered: s1.player.stack.length, gatherFrames, stackAfter: s1.player.stack.slice(0, 8),
      done: s0.done, zones: s0.zones, workers: s0.workers.length, market: s0.market, trade: s0.trade, stations: s0.stations,
      cam: { x: Math.round(gs.cameras.main.scrollX), y: Math.round(gs.cameras.main.scrollY) },
      warnings: FV.warnings(),
    };
  });
}

export async function hideRender(page) {
  await page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) { const sc = g.scene.getScene(k); if (sc) sc.cameras.main.setVisible(false); } });
}

async function withSave(name, raw, extra = {}) {
  if (only && only !== name && !name.startsWith(only)) return;
  if (skip.includes(name)) return;
  const { page, ctx, log } = await newPage(browser);
  await page.addInitScript(([k, v]) => { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); try { localStorage.setItem(k, v); } catch (e) { /* */ } } }, [KEY, raw]);
  if (extra.route) await extra.route(page);
  let r = { raw: raw.slice(0, 200) };
  try {
    await bootToGame(page, URL, { fresh: false, timeout: 90000 });
    await page.screenshot({ path: `${OUT}/save_${name}.jpg`, type: 'jpeg', quality: 60 }).catch(() => {});
    await hideRender(page);
    await sleep(300);
    r.probe = await probe(page);
    if (extra.after) r.after = await extra.after(page);
    r.gameActive = await page.evaluate(() => window.__FV.game.scene.isActive('Game'));
  } catch (e) {
    r.bootError = e.message.split('\n')[0];
    r.scenes = await page.evaluate(() => window.__FV && window.__FV.game && window.__FV.game.scene.scenes.map((s) => s.sys.settings.key + ':' + s.sys.settings.status)).catch((e2) => 'eval failed ' + e2.message);
  }
  r.errors = log.errors.slice(0, 6);
  r.warnings = [...new Set(log.warnings)].filter((w) => !/AudioContext|GPU stall/.test(w)).slice(0, 6);
  results[name] = r;
  const p = r.probe || {};
  console.log(name, JSON.stringify({ boot: r.bootError || 'ok', scenes: r.scenes, coins: p.coins, hud: p.hudText, pos: p.player0 && [p.player0.x, p.player0.y], moved: p.moved, posNaN: p.posNaN, cap: p.capacity, gathered: p.gathered, stack: p.stackAfter, done: p.done, workers: p.workers, market: p.market, stations: p.stations && Object.fromEntries(Object.entries(p.stations).map(([k, v]) => [k, v.in + '>' + v.out])), cam: p.cam, warn: p.warnings, after: r.after, errors: r.errors, warnings: r.warnings }));
  writeJSON('save_results.json', results);
  await ctx.close();
}

// ---------------------------------------------------------------- A. localStorage throws
if ((!only || only === 'throwingStorage') && !skip.includes('throwingStorage')) {
  const { page, ctx, log } = await newPage(browser);
  await page.addInitScript(() => {
    const boom = () => { throw new DOMException('denied', 'SecurityError'); };
    for (const m of ['getItem', 'setItem', 'removeItem', 'clear', 'key']) Storage.prototype[m] = boom;
    Object.defineProperty(window, 'localStorage', { configurable: true, get: boom });
    Object.defineProperty(window, 'sessionStorage', { configurable: true, get: boom });
  });
  const r = {};
  try {
    await page.goto(URL, { waitUntil: 'load' });
    await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 90000);
    await sleep(300); await tapStart(page);
    await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 90000);
    await sleep(500);
    await hideRender(page);
    r.probe = await probe(page);
    // settings toggles + language + save + reset
    r.ui = await page.evaluate(async () => {
      const g = window.__FV.game, ui = g.scene.getScene('UI');
      ui.openSettings();
      const press = (txt) => { const b = ui.panelItems.find((o) => o.text && o.text.text === txt); if (b) b.emit('pointerdown'); return !!b; };
      const out = { soundBtn: press('켜짐') };
      await new Promise((r) => setTimeout(r, 200));
      out.musicBtn = press('켜짐');
      ui.closeSettings(true);
      window.__FV.save();
      window.__FV.give(50);
      window.__FV.reset();
      await new Promise((r) => setTimeout(r, 1500));
      out.afterReset = window.__FV.state().coins;
      out.gameActive = g.scene.isActive('Game');
      return out;
    });
    // visibility hidden -> save path
    await page.evaluate(() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('pagehide')); });
    await sleep(300);
  } catch (e) { r.error = e.message.split('\n')[0]; }
  r.errors = log.errors; r.warnings = [...new Set(log.warnings)].slice(0, 8);
  results.throwingStorage = r;
  console.log('throwingStorage', JSON.stringify(r).slice(0, 1500));
  await ctx.close();
}

// ---------------------------------------------------------------- B. corrupted / odd saves
const base = { v: 1, t: Date.now(), coins: 120, progress: { done: { hire_fisherman: true }, paid: {}, up: { capacity: 0, speed: 0 } }, stations: {}, market: { stock: {}, cash: 0 }, trade: { stock: {}, cash: 0 }, player: { x: 900, y: 1150, stack: [] } };
const J = (o) => JSON.stringify(o);
const variants = {
  invalidJson: '{"v":1,"coins":12',
  emptyString: '',
  jsonNull: 'null',
  jsonArray: '[1,2,3]',
  oldVersion0: J({ ...base, v: 0, coins: 999 }),
  futureVersion2: J({ ...base, v: 2, coins: 999 }),
  coinsString: J({ ...base, coins: 'abc' }),
  coinsNumString: J({ ...base, coins: '250' }),
  coinsNegative: J({ ...base, coins: -500 }),
  coinsHuge: J({ ...base, coins: 1e308 }),
  playerXString: J({ ...base, player: { x: 'abc', y: 1150, stack: [] } }),
  playerXNull: J({ ...base, player: { x: null, y: null, stack: [] } }),
  playerOffWorld: J({ ...base, player: { x: -5000, y: 99999, stack: [] } }),
  stackObject: J({ ...base, player: { x: 900, y: 1150, stack: {} } }),
  stackString: J({ ...base, player: { x: 900, y: 1150, stack: 'item_fish_raw' } }),
  stackBadTypes: J({ ...base, player: { x: 900, y: 1150, stack: ['item_fish_raw', 5, null, 'nope'] } }),
  upgradeNegative: J({ ...base, progress: { ...base.progress, up: { capacity: -1, speed: -1 } } }),
  upgradeString: J({ ...base, progress: { ...base.progress, up: { capacity: 'x', speed: 'y' } } }),
  upgradeFloat: J({ ...base, progress: { ...base.progress, up: { capacity: 1.5, speed: 0.5 } } }),
  paidNegative: J({ ...base, progress: { ...base.progress, paid: { zone_forest: -500 } } }),
  progressNull: J({ ...base, progress: null }),
  doneSkipAhead: J({ ...base, progress: { done: { hire_hunter: true, hire2_miner: true }, paid: {}, up: {} } }),
  stationsWeird: J({ ...base, stations: { grill: { i: 'abc', o: 1e9 }, bogus: { i: 3 } } }),
  marketBadStock: J({ ...base, market: { stock: { item_fish_cooked: 'lots', item_log: 5, __proto__x: 3 }, cash: 'NaN' } }),
  marketStockArray: J({ ...base, market: { stock: [3, 4], cash: 10 } }),
  cashHuge: J({ ...base, market: { stock: {}, cash: 1e15 } }),
};
for (const [name, raw] of Object.entries(variants)) await withSave(name, raw);

// what got written back after an ignored old-version save?
if (!only || only === 'oldOverwrite') {
  const { page, ctx } = await newPage(browser);
  await page.addInitScript(([k, v]) => { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); localStorage.setItem(k, v); } }, [KEY, variants.oldVersion0]);
  await bootToGame(page, URL, { fresh: false });
  await sleep(6000);
  results.oldOverwrite = await page.evaluate((k) => { const s = JSON.parse(localStorage.getItem(k)); return { v: s.v, coins: s.coins }; }, KEY);
  console.log('oldOverwrite (v0 save with 999 coins, after 6 s)', JSON.stringify(results.oldOverwrite));
  await ctx.close();
}

// ---------------------------------------------------------------- C. upgrade pad: stale paid after an upgrade
if (!only || only === 'upgradeStalePaid') {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hideRender(page);
  const r = await page.evaluate(async () => {
    const FV = window.__FV, gs = FV.scene;
    FV.unlockAll();
    FV.give(60 - FV.state().coins);              // exactly the level-1 capacity cost
    const pad = FV.where('up_capacity');
    FV.teleport(pad.x, pad.y);
    const t0 = performance.now();
    while (FV.state().upgrades.capacity < 1 && performance.now() - t0 < 8000) await new Promise((r) => setTimeout(r, 50));
    const lvl = FV.state().upgrades.capacity;
    FV.teleport(pad.x + 250, pad.y + 150);       // step off right away
    const savedNow = JSON.parse(localStorage.getItem('frostVillage.save.v1')).progress.paid;
    await new Promise((r) => setTimeout(r, 1500));
    FV.save();
    const savedLater = JSON.parse(localStorage.getItem('frostVillage.save.v1')).progress.paid;
    return { lvl, coinsLeft: FV.state().coins, savedPaidRightAfterUpgrade: savedNow, savedPaidLater: savedLater, padPaidInMemory: gs.progress.upPads.capacity.paid, padCost: gs.progress.upPads.capacity.cost };
  });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 90000);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 90000);
  await sleep(500);
  r.afterReload = await page.evaluate(() => { const p = window.__FV.scene.progress.upPads.capacity; return { cost: p.cost, paid: p.paid, remaining: p.remaining, coins: window.__FV.state().coins }; });
  r.errors = log.errors;
  results.upgradeStalePaid = r;
  console.log('upgradeStalePaid', JSON.stringify(r));
  await ctx.close();
}

// ---------------------------------------------------------------- D. designer lowers a cost below a saved partial payment / sets cost 0
async function balanceRoute(page, edits) {
  await page.route('**/src/data/balance.js', async (route) => {
    const resp = await route.fetch();
    let body = await resp.text();
    for (const [a, b] of edits) body = body.replace(a, b);
    await route.fulfill({ response: resp, body });
  });
}
if (!only || only === 'costLowered') {
  const save = J({ ...base, coins: 500, progress: { done: { hire_fisherman: true, zone_forest: true, hire_lumberjack: true }, paid: { zone_farm: 150 }, up: { capacity: 0, speed: 0 } } });
  await withSave('costLowered', save, {
    route: (page) => balanceRoute(page, [[/zone_farm: 200,/, 'zone_farm: 100,']]),
    after: (page) => page.evaluate(async () => {
      const FV = window.__FV, pad = FV.scene.progress.pads.zone_farm;
      const before = { cost: pad.cost, paid: pad.paid, remaining: pad.remaining, label: pad.costText.text };
      FV.teleport(pad.x, pad.y);
      const f0 = FV.game.loop.frame; while (FV.game.loop.frame - f0 < 300) await new Promise((r) => setTimeout(r, 30));
      return { before, doneAfter300FramesOnPad: FV.state().done.includes('zone_farm'), coins: FV.state().coins, padStillThere: !!FV.scene.progress.pads.zone_farm };
    }),
  });
}
if (!only || only === 'costZero') {
  await withSave('costZero', J({ ...base, coins: 50, progress: { done: {}, paid: {}, up: {} } }), {
    route: (page) => balanceRoute(page, [[/hire_fisherman: 30,/, 'hire_fisherman: 0,']]),
    after: (page) => page.evaluate(async () => {
      const FV = window.__FV, pad = FV.scene.progress.pads.hire_fisherman;
      FV.teleport(pad.x, pad.y);
      const f0 = FV.game.loop.frame; while (FV.game.loop.frame - f0 < 300) await new Promise((r) => setTimeout(r, 30));
      return { cost: pad.cost, label: pad.costText.text, doneAfter300FramesOnPad: FV.state().done.includes('hire_fisherman') };
    }),
  });
}

// ---------------------------------------------------------------- E. reload during an unlock payment
if (!only || only === 'reloadDuringPayment') {
  const out = [];
  for (const delay of [500, 900, 1300]) {
    const { page, ctx } = await newPage(browser);
    const save = J({ ...base, coins: 1000, progress: { done: { hire_fisherman: true, zone_forest: true, hire_lumberjack: true, zone_farm: true, hire_farmer: true, zone_mine: true, hire_miner: true }, paid: {}, up: {} } });
    await page.addInitScript(([k, v]) => { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); localStorage.setItem(k, v); } }, [KEY, save]);
    await bootToGame(page, URL, { fresh: false });
    await hideRender(page);
    const mid = await page.evaluate(async (d) => {
      const FV = window.__FV, pad = FV.scene.progress.pads.zone_hunt;
      FV.teleport(pad.x, pad.y);
      await new Promise((r) => setTimeout(r, d));
      return { coins: FV.state().coins, paid: pad.paid };
    }, delay);
    await page.reload({ waitUntil: 'load' });
    await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 90000);
    const saved = await page.evaluate((k) => { const s = JSON.parse(localStorage.getItem(k)); return { coins: s.coins, paid: s.progress.paid, done: Object.keys(s.progress.done).length }; }, KEY);
    await sleep(200); await tapStart(page);
    await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 90000);
    await sleep(400);
    const after = await page.evaluate(() => { const FV = window.__FV, p = FV.scene.progress.pads.zone_hunt; return { coins: FV.state().coins, paid: p ? p.paid : 'done', done: FV.state().done.includes('zone_hunt') }; });
    out.push({ delay, mid, saved, after, conserved: after.done ? 'zone done' : after.coins + after.paid === 1000 });
    await ctx.close();
  }
  results.reloadDuringPayment = out;
  console.log('reloadDuringPayment', JSON.stringify(out));
}

// ---------------------------------------------------------------- F. reload mid-transfer: item conservation
if (!only || only === 'reloadMidTransfer') {
  const out = [];
  for (const delay of [60, 150, 400]) {
    const { page, ctx } = await newPage(browser);
    const save = J({ ...base, coins: 0, progress: { done: { hire_fisherman: true }, paid: {}, up: {} }, player: { x: 900, y: 1150, stack: ['item_fish_raw', 'item_fish_raw', 'item_fish_raw', 'item_fish_raw', 'item_fish_raw', 'item_fish_raw'] }, stations: { grill: { i: 0, o: 0 } } });
    await page.addInitScript(([k, v]) => { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); localStorage.setItem(k, v); } }, [KEY, save]);
    await bootToGame(page, URL, { fresh: false });
    await hideRender(page);
    // stop the fisherman from adding fish, then walk on the grill input
    const before = await page.evaluate(async (d) => {
      const FV = window.__FV, gs = FV.scene;
      for (const w of gs.workers) { w.update = () => {}; }
      const total = () => { const s = FV.state(); return s.player.stack.length + s.stations.grill.in + s.stations.grill.out; };
      const t0 = total();
      const pad = FV.where('grillIn');
      FV.teleport(pad.x, pad.y);
      await new Promise((r) => setTimeout(r, d));
      return { total0: t0, totalVisibleAtReload: total(), incoming: gs.stations.grill.inStack.incoming + gs.stations.grill.outStack.incoming + gs.player.stack.incoming };
    }, delay);
    await page.reload({ waitUntil: 'load' });
    await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 90000);
    const saved = await page.evaluate((k) => { const s = JSON.parse(localStorage.getItem(k)); return s.player.stack.length + s.stations.grill.i + s.stations.grill.o; }, KEY);
    out.push({ delay, ...before, savedTotal: saved, lost: before.total0 - saved });
    await ctx.close();
  }
  results.reloadMidTransfer = out;
  console.log('reloadMidTransfer', JSON.stringify(out));
}

// ---------------------------------------------------------------- G. reset flow survives autosave + reload
if (!only || only === 'resetFlow') {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hideRender(page);
  const r = await page.evaluate(async () => {
    const FV = window.__FV, g = FV.game, ui = g.scene.getScene('UI');
    FV.give(500); FV.unlockAll(); FV.save();
    ui.openSettings();
    ui.buildPanelContent(true);
    const yes = ui.panelItems.find((o) => o.text && /다시 할래요|start over/i.test(o.text.text));
    yes.emit('pointerdown');
    const rawImmediately = localStorage.getItem('frostVillage.save.v1');
    await new Promise((r) => setTimeout(r, 6500));
    const s = JSON.parse(localStorage.getItem('frostVillage.save.v1') || 'null');
    return { rawImmediately, after: s && { coins: s.coins, done: Object.keys(s.progress.done) }, state: FV.state().coins, gameActive: g.scene.isActive('Game'), uiActive: g.scene.isActive('UI'), musicKey: !!g.sound.sounds.find((x) => x.key === 'bgm_village' && x.isPlaying) };
  });
  r.errors = log.errors;
  results.resetFlow = r;
  console.log('resetFlow', JSON.stringify(r));
  await ctx.close();
}

// ---------------------------------------------------------------- H. corrupted settings
await withSave('settingsCorrupt', J(base), {
  route: async (page) => page.addInitScript(() => { try { localStorage.setItem('frostVillage.settings.v1', '{"sound":"no","music":0,"lang":"fr","__proto__":{"x":1}}'); } catch (e) { /* */ } }),
  after: (page) => page.evaluate(() => ({ title: window.__FV.game.scene.getScene('UI').coinText.text, lang: document.documentElement.lang })),
});

writeJSON('save_results.json', results);
await browser.close(); await srv.close();
