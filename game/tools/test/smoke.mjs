// Frost Village smoke test (Playwright + Chromium, mobile viewport 390x844).
//   node tools/test/smoke.mjs            (screenshots -> docs/previews/screens/)
// Drives the first loop with __FV.setInput like a joystick (fish -> grill -> counter -> coins ->
// first unlock), then __FV.give + unlockAll to visit every zone. Fails on any page error or
// console error. 404s for missing optional manifest fragments are reported, not fatal.
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor, walkTo } from './pw.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const OUT = path.join(ROOT, 'docs', 'previews', 'screens');
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const step = (name, ok, info = '') => { results.push({ name, ok, info }); console.log((ok ? '  ok  ' : ' FAIL ') + name + (info ? '  — ' + info : '')); };

const srv = await start(0, { prefix: '/game/frost-village/' });   // sub-path on purpose
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 390, height: 844 } });
const shot = async (n) => { await page.screenshot({ path: path.join(OUT, n + '.jpg'), type: 'jpeg', quality: 82 }); };
const st = () => page.evaluate(() => window.__FV.state());
const where = (n) => page.evaluate((k) => window.__FV.where(k), n);
const count = (s, type) => s.player.stack.filter((x) => x === type).length;

let fatal = null;
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  await sleep(900);
  await shot('01_title');
  step('title screen', true);

  await tapStart(page);
  await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 20000);
  await sleep(1200);
  await shot('02_start');
  let s = await st();
  step('game started', s.coins === 0 && s.market.queue > 0, `coins=${s.coins} queue=${s.market.queue}`);

  // ---------------- first loop (repeat until we can afford the fisherman)
  let loops = 0;
  while ((await st()).coins < 30 && loops < 5) {
    loops++;
    // fish at the net
    await walkTo(page, await where('net'), { tol: 18 });
    await waitFor(page, () => { const s = window.__FV.state(); return s.player.stack.length >= Math.min(5, s.player.capacity); }, 20000).catch(() => {});
    s = await st();
    if (loops === 1) { await shot('03_fishing'); step('fishing at the net', count(s, 'item_fish_raw') >= 3, `raw=${count(s, 'item_fish_raw')} anim=${s.player.anim}`); }
    // drop on the grill
    await walkTo(page, await where('grillIn'), { tol: 18 });
    await waitFor(page, () => window.__FV.state().player.stack.filter((x) => x === 'item_fish_raw').length === 0, 10000).catch(() => {});
    if (loops === 1) { await sleep(300); await shot('04_grill_input'); s = await st(); step('fish dropped on grill', s.stations.grill.in + s.stations.grill.out > 0, JSON.stringify(s.stations.grill)); }
    // wait for cooking then take the products
    await waitFor(page, () => { const g = window.__FV.state().stations.grill; return g.in === 0 && g.out > 0; }, 15000).catch(() => {});
    await walkTo(page, await where('grillOut'), { tol: 18 });
    await waitFor(page, () => { const s = window.__FV.state(); return s.stations.grill.out === 0 || s.player.stack.length >= s.player.capacity; }, 10000).catch(() => {});
    if (loops === 1) { await sleep(300); await shot('05_carry_tower'); s = await st(); step('picked up grilled fish', count(s, 'item_fish_cooked') > 0, `cooked=${count(s, 'item_fish_cooked')}`); }
    // put on the counter
    await walkTo(page, await where('shelf'), { tol: 18 });
    await waitFor(page, () => window.__FV.state().player.stack.length === 0, 10000).catch(() => {});
    if (loops === 1) { await sleep(500); await shot('06_counter'); }
    // customers buy -> coins on the cash pad
    await waitFor(page, () => { const s = window.__FV.state(); return s.market.cash > 0 && s.market.stock === 0; }, 20000).catch(() => {});
    if (loops === 1) { await sleep(400); await shot('07_customers_pay'); s = await st(); step('customers paid', s.market.cash > 0, `cash=${s.market.cash}`); }
    await walkTo(page, await where('cash'), { tol: 18 });
    await sleep(900);
    s = await st();
    if (loops === 1) { await shot('08_collect_coins'); step('collected coins', s.coins > 0, `coins=${s.coins}`); }
  }
  s = await st();
  step('earned 30 coins by playing', s.coins >= 30, `coins=${s.coins} after ${loops} loops`);
  if (s.coins < 30) await page.evaluate((n) => window.__FV.give(n), 30 - s.coins);

  // ---------------- first unlock: hire the fisherman
  await walkTo(page, await where('hire_fisherman'), { tol: 14 });
  await sleep(500);
  await shot('09_paying_unlock');
  await waitFor(page, () => window.__FV.state().done.includes('hire_fisherman'), 8000).catch(() => {});
  await sleep(900);
  await shot('10_fisherman_hired');
  s = await st();
  step('hired the fisherman', s.done.includes('hire_fisherman') && s.workers.length === 1, `done=${s.done} workers=${JSON.stringify(s.workers)}`);
  await sleep(5000);
  s = await st();
  step('fisherman works', s.workers[0] && ['work', 'deliver', 'drop', 'goto'].includes(s.workers[0].state), JSON.stringify(s.workers[0]));
  await shot('11_fisherman_working');

  // ---------------- second unlock by paying (forest), then everything
  await page.evaluate(() => { const p = window.__FV.scene.progress.pads.zone_forest; window.__FV.give(p ? p.remaining : 0); });
  await walkTo(page, await where('zone_forest'), { tol: 14 });
  await waitFor(page, () => window.__FV.state().done.includes('zone_forest'), 8000).catch(() => {});
  await sleep(1300);
  await shot('12_forest_reveal');
  s = await st();
  step('forest unlocked by pad', s.zones.forest === true && s.trade.enabled, `zones=${JSON.stringify(s.zones)}`);
  await sleep(2500);

  await page.evaluate(() => { window.__FV.give(5000); return window.__FV.unlockAll(); });
  await sleep(800);
  s = await st();
  step('unlockAll', Object.values(s.zones).every(Boolean) && s.workers.length >= 5, `workers=${s.workers.length}`);
  {
    // test setup: some finished goods on every output pad; the couriers must pick them up
    await page.evaluate(() => { const gs = window.__FV.scene; for (const st of gs.stationList) for (let i = 0; i < 8; i++) st.outStack.push(st.output, null, gs.effects); });
    await waitFor(page, () => window.__FV.scene.workers.filter((w) => w.role === 'porter').some((w) => w.stack.count > 0), 25000).catch(() => {});
    const couriers = await page.evaluate(() => window.__FV.scene.workers.filter((w) => w.role === 'porter').map((w) => w.type + ':' + w.state + ':' + (w.stack.count + w.stack.incoming)));
    step('couriers pick up finished goods', couriers.length === 5 && couriers.some((c) => /:[1-9]\d*$/.test(c)), couriers.join(' '));
  }

  // chop a tree
  await page.evaluate(() => window.__FV.clearStack());
  await waitFor(page, () => window.__FV.where('tree'), 15000).catch(() => {});
  await walkTo(page, (await where('tree')) || (await where('zone:forest')), { tol: 10, teleport: true });
  await waitFor(page, () => window.__FV.state().player.stack.includes('item_log'), 8000).catch(() => {});
  s = await st();
  step('chopping gives logs', s.player.stack.includes('item_log'), `anim=${s.player.anim} stack=${s.player.stack.length}`);
  await shot('13_forest_chop');
  // sawmill + trade post
  await walkTo(page, await where('sawmillIn'), { tol: 16 });
  await sleep(1500);
  await walkTo(page, await where('zone:farm'), { tol: 30 });
  await page.evaluate(() => window.__FV.clearStack());
  await waitFor(page, () => window.__FV.where('wheat'), 15000).catch(() => {});
  await walkTo(page, (await where('wheat')) || (await where('zone:farm')), { tol: 10 });
  await waitFor(page, () => window.__FV.state().player.stack.includes('item_wheat'), 8000).catch(() => {});
  s = await st();
  step('harvesting gives wheat', s.player.stack.includes('item_wheat'), `anim=${s.player.anim}`);
  await shot('14_farm');
  await page.evaluate(() => window.__FV.clearStack());
  await waitFor(page, () => window.__FV.where('rock'), 15000).catch(() => {});
  await walkTo(page, (await where('rock')) || (await where('zone:mine')), { tol: 10 });
  await waitFor(page, () => window.__FV.state().player.stack.includes('item_ore'), 8000).catch(() => {});
  s = await st();
  step('mining gives ore', s.player.stack.includes('item_ore'), `anim=${s.player.anim}`);
  await shot('15_mine');
  {
    let caught = false;
    await page.evaluate(() => window.__FV.clearStack());
    for (let tries = 0; tries < 6 && !caught; tries++) {
      const a = await page.evaluate(() => window.__FV.where('animal'));
      if (!a) { await sleep(1500); continue; }
      await page.evaluate(([x, y]) => window.__FV.teleport(x, y), [a.x, a.y]);
      caught = await waitFor(page, () => window.__FV.state().player.stack.includes('item_meat_raw'), 9000).then(() => true).catch(() => false);
    }
    step('catching an animal gives meat', caught);
  }
  await shot('16_hunt');
  await page.evaluate(() => { window.__FV.teleport(990, 2200); });
  await sleep(1200);
  await shot('17_village');
  // upgrades
  await page.evaluate(() => window.__FV.teleport(990, 1000));
  const cap0 = (await st()).player.capacity;
  await walkTo(page, await where('up_capacity'), { tol: 10 });
  await waitFor(page, (c) => window.__FV.state().player.capacity > c, 16000, cap0).catch(() => {});
  s = await st();
  step('backpack upgrade', s.player.capacity > cap0, `${cap0} -> ${s.player.capacity}`);
  await shot('18_upgrade');
  // trade post selling
  await page.evaluate(() => window.__FV.teleport(1000, 900));
  await sleep(500);
  await walkTo(page, await where('tradeShelf'), { tol: 14 });
  await sleep(1500);
  await shot('19_trade_post');

  // overview
  await page.evaluate(() => window.__FV.camera(900, 1300, 0.42));
  await sleep(1200);
  await shot('20_overview');
  await page.evaluate(() => window.__FV.camera());

  // settings panel (tap the gear)
  const c = await page.$('canvas'); const b = await c.boundingBox();
  const sx = b.width / 720;
  await page.touchscreen.tap(b.x + (720 - 62) * sx, b.y + 62 * sx);
  await sleep(600);
  await shot('21_settings');
  const paused = await page.evaluate(() => window.__FV.game.scene.isPaused('Game'));
  step('settings panel opens (game paused)', paused);
  await page.touchscreen.tap(b.x + (360 + 0) * sx, b.y + (b.height / sx / 2 + 170) * sx); // reset -> confirm view
  await sleep(500);
  await shot('22_reset_confirm');
  await page.touchscreen.tap(b.x + 360 * sx, b.y + (b.height / sx / 2 + 160) * sx);      // "no"
  await sleep(400);
  await page.touchscreen.tap(b.x + 360 * sx, b.y + (b.height / sx / 2 + 262) * sx);      // close
  await sleep(500);
  step('settings closed', !(await page.evaluate(() => window.__FV.game.scene.isPaused('Game'))));

  // celebration
  await page.evaluate(() => window.__FV.scene.celebrate());
  await sleep(1300);
  await shot('23_village_complete');

  // save + reload
  await page.evaluate(() => window.__FV.save());
  const before = await st();
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  await sleep(500);
  await tapStart(page);
  await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 20000);
  await sleep(1500);
  s = await st();
  step('save / load', s.done.length === before.done.length && Math.abs(s.coins - before.coins) < 5 && s.workers.length === before.workers.length, `done ${before.done.length}->${s.done.length} coins ${before.coins}->${s.coins}`);
  await shot('24_reloaded');
  // reset progress through the in-game confirm (settings -> reset -> yes)
  {
    const c2 = await page.$('canvas'); const b2 = await c2.boundingBox();
    const k = b2.width / 720, Hh = b2.height / k;
    await page.touchscreen.tap(b2.x + (720 - 62) * k, b2.y + 62 * k); await sleep(600);
    await page.touchscreen.tap(b2.x + 360 * k, b2.y + (Hh / 2 + 170) * k); await sleep(500);
    await page.touchscreen.tap(b2.x + 360 * k, b2.y + (Hh / 2 + 60) * k); await sleep(2500);
    await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 15000).catch(() => {});
    s = await st();
    step('reset progress (in-game confirm)', s.coins === 0 && s.done.length === 0 && s.workers.length === 0, `coins=${s.coins} done=${s.done.length}`);
    await shot('25_after_reset');
  }
  const fps = await page.evaluate(async () => { await new Promise((r) => setTimeout(r, 1500)); return window.__FV.state().fps; });
  step('fps sample (headless software GL, informational)', true, String(fps));
} catch (e) {
  fatal = e;
  console.log('FATAL', e && e.stack || e);
  await shot('99_failure').catch(() => {});
}

const warnings = await page.evaluate(() => (window.__FV && window.__FV.warnings ? window.__FV.warnings() : [])).catch(() => []);
await browser.close();
await srv.close();

const manifest404 = [...new Set(log.missing404.filter((m) => /manifest\.json/.test(m)).map((m) => m.replace(/^.*(assets\/[a-z]+\/manifest\.json).*$/, '$1')))];
const other404 = log.missing404.filter((m) => !/manifest\.json/.test(m) && /^404 /.test(m));
console.log('\nmissing manifest fragments (placeholders used):', manifest404.join(', ') || 'none');
console.log('placeholder keys:', warnings.length, warnings.join(', '));
if (other404.length) console.log('other 404s:', other404.join('\n'));
console.log('page/console errors:', log.errors.length);
for (const e of log.errors) console.log('  ' + e);
const failed = results.filter((r) => !r.ok);
const ok = !fatal && log.errors.length === 0 && other404.length === 0 && failed.length === 0;
console.log(`\n${ok ? 'PASS' : 'FAIL'}: ${results.length - failed.length}/${results.length} steps ok, ${log.errors.length} errors. Screens in docs/previews/screens/`);
process.exit(ok ? 0 : 1);
