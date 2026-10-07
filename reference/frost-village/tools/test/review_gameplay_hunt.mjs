// Can the chief catch animals by hand with the joystick? Opens zones up to the hunting ground (no hunter
// hired, so the chief has the animals to himself), then chases with a simple "run at the nearest animal,
// let go of the stick when close" strategy for N minutes. Reports meat/min and seconds per catch.
//   node tools/test/review_gameplay_hunt.mjs [minutes=3] [stopDist=55]
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const MIN = Number(process.argv[2] || 3);
const STOP = Number(process.argv[3] || 55);
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 60000);
  await sleep(400);
  const r = await page.evaluate(async ([MIN, STOP]) => {
    const game = window.__FV.game; game.loop.sleep();
    let D = Date.now(), T = game.loop.time || performance.now(); Date.now = () => D; const DT = 1000 / 60;
    const run = (sec, f) => { for (let i = 0; i < Math.round(sec * 60); i++) { if (f) f(); T += DT; D += DT; game.headlessStep(T, DT); } };
    const gs = window.__FV.scene, pr = gs.progress, FV = window.__FV;
    const { STEPS } = await import(new URL('src/systems/Progression.js', location.href).href);
    for (const s of STEPS) { if (s.id === 'hire_hunter') break; pr.syncPads(); const p = pr.pads[s.id]; if (p) { pr.completeStep(s, p); run(2.2); } }
    // the chief deposits at the smokehouse whenever the bag is full; we only count catches
    const z = gs.zones.hunt.cfg.center;
    FV.teleport(z[0], z[1] + 120);
    gs.progress.up.capacity = 5;          // big bag so we never stop to unload (measurement only)
    let caught = 0, meat0 = 0, flee = 0, lastFleeState = new Map(), stops = 0, chaseT = 0;
    const gd = (ax, ay, bx, by) => Math.hypot(ax - bx, (ay - by) * 2);
    let target = null;
    const tick = () => {
      const p = gs.player;
      for (const a of gs.animals) { const was = lastFleeState.get(a); if (a.state === 'flee' && was !== 'flee') flee++; lastFleeState.set(a, a.state); }
      if (!target || !target.ready()) {
        target = null; let bd = 1e9;
        for (const a of gs.animals) if (a.ready()) { const d = gd(p.x, p.y, a.x, a.y); if (d < bd) { bd = d; target = a; } }
      }
      if (!target) { FV.setInput(0, 0); return; }
      const d = gd(p.x, p.y, target.x, target.y);
      if (d < STOP) { FV.setInput(0, 0); return; }
      chaseT += DT / 1000;
      const dx = target.x - p.x, dy = (target.y - p.y) / 0.74, m = Math.hypot(dx, dy) || 1;
      FV.setInput(dx / m, dy / m);
    };
    const t0 = performance.now();
    const meatAt = [];
    for (let s = 0; s < MIN * 60; s += 1) {
      run(1, tick);
      if (false) { const p = gs.player; window.__dbg = (window.__dbg || []); window.__dbg.push({ s, p: [Math.round(p.x), Math.round(p.y)], anim: p.animName, still: +p.stillT.toFixed(2), node: p.node ? p.node.kind : null, onPad: gs.playerOnPad, room: p.room, cap: p.capacity, bag: p.stack.count, tgt: target ? [Math.round(target.x), Math.round(target.y), target.state, Math.round(gd(p.x, p.y, target.x, target.y))] : null }); }
      for (const a of gs.animals) { if (a.dead && !a.__counted) { a.__counted = true; meat0 += 2; meatAt.push(s); } if (!a.dead) a.__counted = false; }
      if (gs.player.stack.count > 12) FV.clearStack();   // measurement only: never let the bag fill up
    }
    FV.setInput(0, 0);
    return { meat: meat0, catches: meat0 / 2, fleeEvents: flee, chaseSeconds: Math.round(chaseT), firstMeatAt: meatAt[0], meatTimes: meatAt.slice(0, 20), wallMs: Math.round(performance.now() - t0), dbg: window.__dbg };
  }, [MIN, STOP]);
  console.log(JSON.stringify(r));
  console.log(`meat per minute: ${(r.meat / MIN).toFixed(1)}  (= ${(r.meat / MIN * 12).toFixed(0)} coins/min after smoking)`);
} catch (e) { console.log('FATAL', e.stack || e); }
console.log('errors', log.errors.length, log.errors.slice(0, 3));
await browser.close(); await srv.close();
