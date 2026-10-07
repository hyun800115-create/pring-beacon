// Geometry probe: free spots for the mine hire pad, and whether worker home points are inside obstacles.
//   node tools/test/review_gameplay_geo.mjs
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
await page.reload({ waitUntil: 'load' });
await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
await sleep(300); await tapStart(page);
await waitFor(page, () => window.__FV.scene && window.__FV.scene.player, 20000);
const r = await page.evaluate(async () => {
  const gs = window.__FV.scene;
  const { WORLD, Z } = await import(new URL('src/data/world.js', location.href).href);
  window.__FV.unlockAll();
  const frac = (x, y, R) => { let ok = 0, tot = 0; for (let a = 0; a < 24; a++) for (let rr = 0; rr < R; rr += 6) { tot++; if (!gs.collision.blocked(x + Math.cos(a / 24 * 6.283) * rr, y + Math.sin(a / 24 * 6.283) * rr / 2, 16)) ok++; } return ok / tot; };
  const out = { homes: {}, mineSpots: [] };
  for (const w of gs.workers) out.homes[w.type + w.index] = { home: w.home.map(Math.round), blocked: gs.collision.blocked(w.home[0], w.home[1], 14) };
  for (let mx = -4; mx <= 4.01; mx += 0.4) for (let my = 2.0; my <= 4.6; my += 0.3) {
    const [x, y] = Z('mine', mx, my); const f = frac(x, y, 69);
    if (f >= 0.97) out.mineSpots.push({ mx: +mx.toFixed(1), my: +my.toFixed(1), x, y, f: +f.toFixed(2) });
  }
  return out;
});
console.log(JSON.stringify(r.homes));
console.log(r.mineSpots.slice(0, 40).map((s) => `Z('mine', ${s.mx}, ${s.my}) -> ${s.x},${s.y} free=${s.f}`).join('\n'));
await browser.close(); await srv.close();
