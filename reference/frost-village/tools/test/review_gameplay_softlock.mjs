// Repro: bag full of raw items while that station's input (30) AND output (36) are full -> nothing can
// ever leave the bag (no discard, no other consumer) -> carrying is dead, and the stack is saved.
//   node tools/test/review_gameplay_softlock.mjs
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const OUT = '/tmp/fv_review/gameplay';
fs.mkdirSync(OUT, { recursive: true });
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
const S = () => page.evaluate(() => { const s = window.__FV.state(); return { coins: s.coins, bag: s.player.stack.join(','), grill: s.stations.grill, w: s.workers.map((w) => w.state + ':' + w.carry).join(' '), obj: s.objective, pos: [s.player.x, s.player.y] }; });
async function boot() {
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  await sleep(300);
  await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 20000);
  await sleep(400);
  await page.evaluate(() => {
    const game = window.__FV.game; game.loop.sleep();
    let D = Date.now(), T = game.loop.time || performance.now(); Date.now = () => D; const DT = 1000 / 60;
    window.__sim = { run(sec, f) { for (let i = 0; i < Math.round(sec * 60); i++) { if (f) f(); T += DT; D += DT; game.headlessStep(T, DT); } }, render() { T += DT; D += DT; game.step(T, DT); } };
    // tiny steering helper (joystick only)
    window.__go = (x, y, tol = 8, maxSec = 20) => {
      const gs = window.__FV.scene; let t = 0;
      while (t < maxSec) {
        const p = gs.player; const dx = x - p.x, dy = (y - p.y) / 0.74; const d = Math.hypot(x - p.x, (y - p.y) * 2);
        if (d < tol) break;
        const m = Math.hypot(dx, dy) || 1, k = Math.min(1, Math.max(0.25, d / 70));
        window.__FV.setInput(dx / m * k, dy / m * k);
        window.__sim.run(1 / 60); t += 1 / 60;
      }
      window.__FV.setInput(0, 0);
      return t;
    };
  });
}
const shot = async (n) => { await page.evaluate(() => { for (let i = 0; i < 3; i++) window.__sim.render(); }); await sleep(120); await page.screenshot({ path: path.join(OUT, n + '.jpg'), type: 'jpeg', quality: 72 }); };

try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await boot();
  // setup shortcut (allowed for late checks): 30 coins -> hire the fisherman by standing on the pad
  await page.evaluate(() => { window.__FV.give(30); const p = window.__FV.where('hire_fisherman'); window.__go(p.x, p.y, 6); window.__sim.run(3); });
  console.log('after hire', await S());
  // the player walks off to the trade-post side of the plaza and leaves the fish chain alone for 2.5 min
  await page.evaluate(() => { window.__go(1100, 900, 10); window.__sim.run(150); });
  console.log('after 150 s away', await S());
  // come back, stand at the net -> auto-gather fills the bag with raw fish
  await page.evaluate(() => { const n = window.__FV.where('net'); window.__go(n.x, n.y, 10); window.__sim.run(8); });
  console.log('after fishing', await S());
  // try to drop at the grill input, then try to take from the output
  await page.evaluate(() => { const n = window.__FV.where('grillIn'); window.__go(n.x, n.y, 6); window.__sim.run(5); });
  const a = await S(); console.log('on grill input', a);
  await shot('softlock_1_grill_input_full');
  await page.evaluate(() => { const n = window.__FV.where('grillOut'); window.__go(n.x, n.y, 6); window.__sim.run(5); });
  const b = await S(); console.log('on grill output', b);
  await shot('softlock_2_grill_output_full_bag_full');
  // wait a full minute on the output pad: nothing changes
  await page.evaluate(() => window.__sim.run(60));
  const c = await S(); console.log('after 60 s more', c);
  // try every other drop point: market shelf, trade post (not open), cash
  await page.evaluate(() => { const n = window.__FV.where('shelf'); window.__go(n.x, n.y, 6); window.__sim.run(3); });
  console.log('on market shelf', await S());
  // save + reload: the raw stack is restored
  await page.evaluate(() => window.__FV.save());
  await page.reload({ waitUntil: 'load' });
  await boot();
  await page.evaluate(() => window.__sim.run(3));
  const d = await S(); console.log('after reload', d);
  await shot('softlock_3_after_reload');
  const locked = d.bag.split(',').filter((x) => x === 'item_fish_raw').length >= 6 && d.grill.in >= 30 && d.grill.out >= 36;
  console.log(locked ? 'SOFTLOCK REPRODUCED (persists across reload)' : 'not reproduced');
} catch (e) { console.log('FATAL', e.stack || e); }
console.log('errors', log.errors.length, log.errors.slice(0, 3));
await browser.close(); await srv.close();
