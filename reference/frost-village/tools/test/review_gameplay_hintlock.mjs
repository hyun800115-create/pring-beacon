// Repro: the forest zone hint ("판자를 가져가세요") keeps pointing at the sawmill output while the chief's
// bag is full of grilled fish, so following the arrow can never succeed (it never says "sell the fish first").
//   node tools/test/review_gameplay_hintlock.mjs
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const OUT = '/tmp/fv_review/gameplay';
fs.mkdirSync(OUT, { recursive: true });
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
const S = () => page.evaluate(() => { const s = window.__FV.state(); return { coins: s.coins, bag: s.player.stack.length + '/' + s.player.capacity + ' ' + [...new Set(s.player.stack)].join(','), grill: s.stations.grill, saw: s.stations.sawmill, obj: s.objective, arrowAt: window.__FV.scene.tutorial.target ? [Math.round(window.__FV.scene.tutorial.target.x), Math.round(window.__FV.scene.tutorial.target.y)] : null, sawOut: window.__FV.where('sawmillOut') }; });
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 60000);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 60000);
  await sleep(400);
  await page.evaluate(() => {
    const game = window.__FV.game; game.loop.sleep();
    let D = Date.now(), T = game.loop.time || performance.now(); Date.now = () => D; const DT = 1000 / 60;
    window.__sim = { run(sec) { for (let i = 0; i < Math.round(sec * 60); i++) { T += DT; D += DT; game.headlessStep(T, DT); } }, render() { T += DT; D += DT; game.step(T, DT); } };
    window.__go = (x, y, tol = 8, maxSec = 25) => { const gs = window.__FV.scene; let t = 0; while (t < maxSec) { const p = gs.player; const dx = x - p.x, dy = (y - p.y) / 0.74; const d = Math.hypot(x - p.x, (y - p.y) * 2); if (d < tol) break; const m = Math.hypot(dx, dy) || 1, k = Math.min(1, Math.max(0.25, d / 70)); window.__FV.setInput(dx / m * k, dy / m * k); window.__sim.run(1 / 60); t += 1 / 60; } window.__FV.setInput(0, 0); return t; };
    const W = (n) => window.__FV.where(n);
    // setup shortcut (coins only): hire the fisherman and open the forest by standing on the pads
    window.__FV.give(30); let p = W('hire_fisherman'); window.__go(p.x, p.y, 6); window.__sim.run(3);
    window.__FV.give(80); p = W('zone_forest'); window.__go(p.x, p.y, 6); window.__sim.run(4);
    // chop a few logs by hand and put them in the sawmill (the guided forest run)
    p = W('tree'); window.__go(p.x, p.y, 6); window.__sim.run(5);
    p = W('sawmillIn'); window.__go(p.x, p.y, 6); window.__sim.run(2);
    // meanwhile the fisherman has filled the grill: grab a full bag of grilled fish
    p = W('grillOut'); window.__go(p.x, p.y, 6); window.__sim.run(3);
  });
  console.log('bag full of fish:', await S());
  // follow the arrow
  await page.evaluate(() => { const t = window.__FV.scene.tutorial.target; if (t) window.__go(t.x, t.y, 6); window.__sim.run(20); });
  const s = await S();
  console.log('after following the arrow for 20 s:', s);
  await page.evaluate(() => { for (let i = 0; i < 4; i++) window.__sim.render(); });
  await sleep(200);
  await page.screenshot({ path: path.join(OUT, 'hintlock_sawmill_bag_full.jpg'), type: 'jpeg', quality: 75 });
} catch (e) { console.log('FATAL', e.stack || e); }
console.log('errors', log.errors.length, log.errors.slice(0, 3));
await browser.close(); await srv.close();
