// Worker chains end-to-end: unlockAll (late-game check), park the chief, and every 10 s empty the
// station outputs (test setup, so no station ever blocks). Reports products/min per chain, the share of
// time each worker spends in each state, and "stuck" episodes (moving state but no movement for 4 s).
//   node tools/test/review_gameplay_workers.mjs [minutes=10] [index2=0]
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const MIN = Number(process.argv[2] || 10);
const SECOND = process.argv[3] === '1';
const BO = process.argv[4] || '';
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  if (BO) await page.evaluate(async (bo) => { const b = await import(new URL('src/data/balance.js', location.href).href); const merge = (a, c) => { for (const k in c) { if (c[k] && typeof c[k] === 'object' && !Array.isArray(c[k])) merge(a[k] = a[k] || {}, c[k]); else a[k] = c[k]; } }; merge(b.BALANCE, JSON.parse(bo)); }, BO);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 60000);
  await sleep(400);
  await page.evaluate((second) => {
    const game = window.__FV.game; game.loop.sleep();
    let D = Date.now(), T = game.loop.time || performance.now(); Date.now = () => D; const DT = 1000 / 60;
    const gs = window.__FV.scene;
    window.__FV.unlockAll();
    if (!second) { // remove the hire2 workers that unlockAll adds, keep one per job
      for (let i = gs.workers.length - 1; i >= 0; i--) { const w = gs.workers[i]; if (w.index > 0) { w.sprite.destroy(); w.shadow.destroy(); w.stack.clear(gs.effects); gs.workers.splice(i, 1); gs.agents.splice(gs.agents.indexOf(w), 1); } }
    }
    gs.player.x = 990; gs.player.y = 1500;     // out of everyone's way
    const W = window.__W = { prod: {}, states: {}, stuck: [], last: new Map(), stillT: new Map() };
    for (const s of gs.stationList) W.prod[s.id] = 0;
    window.__sim = {
      run(sec) {
        for (let i = 0; i < Math.round(sec * 60); i++) {
          T += DT; D += DT; game.headlessStep(T, DT);
          for (const w of gs.workers) {
            const k = w.type + w.index;
            W.states[k] = W.states[k] || {}; W.states[k][w.state] = (W.states[k][w.state] || 0) + DT / 1000;
            const l = W.last.get(w) || { x: w.x, y: w.y };
            const mv = Math.hypot(w.x - l.x, w.y - l.y);
            W.last.set(w, { x: w.x, y: w.y });
            if ((w.state === 'goto' || w.state === 'deliver') && mv < 0.05 && !(w.type === 'hunter' && w.state === 'goto' && w.vx === 0)) { const st = (W.stillT.get(w) || 0) + DT / 1000; W.stillT.set(w, st); if (st > 4 && st - DT / 1000 <= 4) W.stuck.push({ w: k, state: w.state, x: Math.round(w.x), y: Math.round(w.y) }); }
            else W.stillT.set(w, 0);
          }
        }
      },
    };
  }, SECOND);
  for (let m = 1; m <= MIN; m++) {
    const r = await page.evaluate(() => {
      const gs = window.__FV.scene, W = window.__W;
      for (let k = 0; k < 6; k++) {
        window.__sim.run(10);
        for (const s of gs.stationList) { while (s.outStack.count) { const it = s.outStack.pop(); gs.effects.releaseItem(it.spr); W.prod[s.id]++; } }
      }
      return { prod: Object.assign({}, W.prod), inputs: Object.fromEntries(gs.stationList.map((s) => [s.id, s.inStack.count])), stuck: W.stuck.length };
    });
    console.log(`min ${m}: produced so far ${JSON.stringify(r.prod)} inputs=${JSON.stringify(r.inputs)} stuckEpisodes=${r.stuck}`);
  }
  const fin = await page.evaluate(() => {
    const W = window.__W;
    const share = {};
    for (const k in W.states) { const tot = Object.values(W.states[k]).reduce((a, b) => a + b, 0); share[k] = Object.fromEntries(Object.entries(W.states[k]).map(([s, v]) => [s, Math.round(v / tot * 100) + '%'])); }
    return { share, stuck: W.stuck.slice(0, 20) };
  });
  console.log('state share:', JSON.stringify(fin.share, null, 0));
  console.log('stuck episodes:', JSON.stringify(fin.stuck));
} catch (e) { console.log('FATAL', e.stack || e); }
console.log('errors', log.errors.length, log.errors.slice(0, 3));
await browser.close(); await srv.close();
