// Geometry check: can the chief actually stand on every unlock / hire / upgrade pad once it appears?
// Walks the progression in order (completing zone steps through Progression.completeStep so the zone's
// obstacles become active exactly like in play), then for each visible pad: is its centre blocked by an
// active obstacle, what fraction of its trigger disc is standable, and does joystick-walking onto it work.
//   node tools/test/review_gameplay_pads.mjs
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';
import { fileURLToPath as fvToPath } from 'node:url';
const FV_REVIEW = process.env.FV_REVIEW || path.resolve(fvToPath(import.meta.url), '../../../../.cache/fv_review');  // 저장소/.cache/fv_review

const OUT = path.join(FV_REVIEW, 'gameplay');
fs.mkdirSync(OUT, { recursive: true });
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 20000);
  await sleep(400);
  await page.evaluate(() => {
    const game = window.__FV.game; game.loop.sleep();
    let D = Date.now(), T = game.loop.time || performance.now(); Date.now = () => D; const DT = 1000 / 60;
    window.__sim = { run(sec) { for (let i = 0; i < Math.round(sec * 60); i++) { T += DT; D += DT; game.headlessStep(T, DT); } }, render() { T += DT; D += DT; game.step(T, DT); } };
  });
  const res = await page.evaluate(async () => {
    const gs = window.__FV.scene, pr = gs.progress, FV = window.__FV;
    const { STEPS } = await import(new URL('src/systems/Progression.js', location.href).href);
    const gd = (ax, ay, bx, by) => Math.hypot(ax - bx, (ay - by) * 2);
    const check = (id, p) => {
      let ok = 0, tot = 0;
      for (let a = 0; a < 24; a++) for (let rr = 0; rr < p.pad.r; rr += 6) {
        const x = p.x + Math.cos(a / 24 * 6.283) * rr, y = p.y + Math.sin(a / 24 * 6.283) * rr / 2;
        tot++; if (!gs.collision.blocked(x, y, 16)) ok++;
      }
      const hits = gs.collision.all.filter((o) => o.active && gd(p.x, p.y, o.x, o.y) < o.r + 16).map((o) => `${o.tag}@${Math.round(o.x)},${Math.round(o.y)} r${Math.round(o.r)}`);
      // try to walk onto it with the joystick from 260 px below
      const sx = p.x, sy = p.y + 140;
      gs.player.x = sx; gs.player.y = sy; gs.player.sync(0);      // (geometry probe only: start position)
      gs.collision.resolve(gs.player, 16);
      let t = 0, onPad = false, minD = 1e9;
      while (t < 8) {
        const pl = gs.player; const dx = p.x - pl.x, dy = (p.y - pl.y) / 0.74; const m = Math.hypot(dx, dy) || 1;
        FV.setInput(dx / m, dy / m); window.__sim.run(1 / 60); t += 1 / 60;
        minD = Math.min(minD, gd(pl.x, pl.y, p.x, p.y));
        if (p.pad.contains(pl.x, pl.y)) { onPad = true; break; }
      }
      FV.setInput(0, 0);
      return { id, x: Math.round(p.x), y: Math.round(p.y), triggerR: Math.round(p.pad.r), centreBlocked: gs.collision.blocked(p.x, p.y, 16), standableFrac: +(ok / tot).toFixed(2), reachedByWalking: onPad, closestApproach: Math.round(minD), overlaps: hits };
    };
    const out = [];
    for (const s of STEPS) {
      pr.syncPads();
      const pad = pr.pads[s.id];
      if (!pad) { out.push({ id: s.id, missing: true }); continue; }
      out.push(check(s.id, pad));
      // complete the step the same way paying would
      pr.completeStep(s, pad);
      window.__sim.run(2.5);
    }
    for (const k in pr.upPads) out.push(check('up_' + k, pr.upPads[k]));
    return out;
  });
  for (const r of res) console.log(JSON.stringify(r));
  // close-up of the mine hire pad area
  await page.evaluate(() => { window.__FV.camera(430, 1820, 1.2); for (let i = 0; i < 90; i++) window.__sim.render(); });
  await sleep(200);
  await page.screenshot({ path: path.join(OUT, 'pad_hire_miner_area.jpg'), type: 'jpeg', quality: 75 });
} catch (e) { console.log('FATAL', e.stack || e); }
console.log('errors', log.errors.length, log.errors.slice(0, 3));
await browser.close(); await srv.close();
