// Market-only test: keep the food shelf stocked (test setup), let customers run for N minutes.
// Measures customers served / min, items sold / min, how many "leaving" customers never despawn,
// total agents, and the CPU cost of one simulated frame as the crowd grows.
//   node tools/test/review_gameplay_market.mjs [minutes=20]
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';
import { fileURLToPath as fvToPath } from 'node:url';
const FV_REVIEW = process.env.FV_REVIEW || path.resolve(fvToPath(import.meta.url), '../../../../.cache/fv_review');  // 저장소/.cache/fv_review

const MIN = Number(process.argv[2] || 20);
const WO = process.argv[3] || '';   // optional WORLD override JSON (runtime, before the Game scene starts)
const TAG = process.argv[4] || '';
const BO = process.argv[5] || '';   // optional BALANCE override JSON
const OUT = path.join(FV_REVIEW, 'gameplay');
fs.mkdirSync(OUT, { recursive: true });
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  if (WO) await page.evaluate(async (wo) => { const w = await import(new URL('src/data/world.js', location.href).href); const merge = (a, b) => { for (const k in b) { if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) merge(a[k] = a[k] || {}, b[k]); else a[k] = b[k]; } }; merge(w.WORLD, JSON.parse(wo)); }, WO);
  if (BO) await page.evaluate(async (bo) => { const b = await import(new URL('src/data/balance.js', location.href).href); const merge = (a, c) => { for (const k in c) { if (c[k] && typeof c[k] === 'object' && !Array.isArray(c[k])) merge(a[k] = a[k] || {}, c[k]); else a[k] = c[k]; } }; merge(b.BALANCE, JSON.parse(bo)); }, BO);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 20000);
  await sleep(400);
  await page.evaluate(() => {
    const game = window.__FV.game; game.loop.sleep();
    let D = Date.now(), T = game.loop.time || performance.now(); Date.now = () => D; const DT = 1000 / 60;
    window.__sim = { run(sec) { for (let i = 0; i < Math.round(sec * 60); i++) { T += DT; D += DT; game.headlessStep(T, DT); } }, render() { T += DT; D += DT; game.step(T, DT); } };
    const gs = window.__FV.scene;
    window.__mk = { sold: 0, value: 0, arriveTimes: [] };
    gs.events.on('sold', (v) => { window.__mk.sold++; window.__mk.value += v; });
    // park the chief out of the way
    gs.player.x = 700; gs.player.y = 900;
  });
  for (let m = 1; m <= MIN; m++) {
    const r = await page.evaluate(() => {
      const gs = window.__FV.scene, m = gs.market;
      const s0 = window.__mk.sold, v0 = window.__mk.value;
      let wall = 0, frames = 0;
      for (let k = 0; k < 6; k++) {
        // keep 20+ of fish on the shelf (test setup = a perfect supplier)
        while (m.stock.countOf('item_fish_cooked') < 30) m.stock.push('item_fish_cooked', null, gs.effects);
        const a = performance.now(); window.__sim.run(10); wall += performance.now() - a; frames += 600;
      }
      const ys = m.leaving.map((c) => Math.round(c.y));
      return { served: window.__mk.sold - s0, coins: window.__mk.value - v0, queue: m.queue.length, atCounter: m.queue.filter((c) => c.arrived).length, leaving: m.leaving.length, agents: gs.agents.length, children: gs.children.length, msPerFrame: +(wall / frames).toFixed(2), leavingYmin: Math.min(...ys), leavingYmax: Math.max(...ys) };
    });
    console.log(`min ${m}: ` + JSON.stringify(r));
  }
  await page.evaluate(() => { window.__FV.camera(990, 2480, 1.0); for (let i = 0; i < 60; i++) window.__sim.render(); });
  await sleep(300);
  await page.screenshot({ path: path.join(OUT, 'market_leaving_crowd' + TAG + '.jpg'), type: 'jpeg', quality: 75 }).catch((e) => console.log('shot failed', e.message));
} catch (e) { console.log('FATAL', e.stack || e); }
console.log('errors', log.errors.length, log.errors.slice(0, 3));
await browser.close(); await srv.close();
