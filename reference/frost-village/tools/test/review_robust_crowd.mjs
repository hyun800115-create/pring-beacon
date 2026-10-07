// Projection of the "customers never despawn" leak: inject N customers that have bought and are
// leaving (same state the market puts them in) and measure the Game update cost per frame.
//   node tools/test/review_robust_crowd.mjs
import { newPage, bootToGame, launch, start, writeJSON, OUT } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await newPage(browser);
await bootToGame(page, srv.url + 'index.html');
const res = await page.evaluate(async () => {
  const FV = window.__FV, g = FV.game, gs = FV.scene, m = gs.market;
  FV.unlockAll();
  for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(false);
  const times = [];
  const gu = gs.sys.sceneUpdate;
  gs.sys.sceneUpdate = function (t, d) { const a = performance.now(); gu.call(this, t, d); times.push(performance.now() - a); };
  const W = (n) => new Promise((r) => { const f0 = g.loop.frame; const iv = setInterval(() => { if (g.loop.frame - f0 >= n) { clearInterval(iv); r(); } }, 10); });
  const measure = async () => { await W(30); times.length = 0; await W(200); const s = times.slice().sort((a, b) => a - b); return { avg: +(s.reduce((a, b) => a + b, 0) / s.length).toFixed(2), p95: +s[Math.floor(s.length * 0.95)].toFixed(2) }; };
  const out = [];
  out.push({ leaving: m.leaving.length, agents: gs.agents.length, children: gs.children.length, gameUpdateMs: await measure() });
  for (const target of [100, 300, 600]) {
    while (m.leaving.length < target) {
      const c = m.spawnCustomer();
      m.queue.splice(m.queue.indexOf(c), 1);
      c.x = 900 + Math.random() * 200; c.y = 2560;
      c.state = 'leave';
      for (let i = 0; i < 6; i++) c.stack.push(c.want.type, null, gs.effects);
      c.path = [{ x: 990 + (Math.random() - 0.5) * 50, y: 2660 }];
      m.leaving.push(c);
    }
    await W(60);
    out.push({ leaving: m.leaving.length, agents: gs.agents.length, children: gs.children.length, gameUpdateMs: await measure() });
  }
  // are they still there after a while (i.e. really stuck)?
  await W(600);
  out.push({ after600frames: { leaving: m.leaving.length, sampleY: m.leaving.slice(0, 5).map((c) => Math.round(c.y)) } });
  return out;
});
for (const r of res) console.log(JSON.stringify(r));
writeJSON('crowd.json', { res, errors: log.errors });
await page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(true); window.__FV.teleport(990, 2450); });
await new Promise((r) => setTimeout(r, 2500));
await page.screenshot({ path: OUT + '/crowd_600_stuck_customers.jpg', type: 'jpeg', quality: 65, timeout: 120000 }).catch((e) => console.log('screenshot failed', e.message.split('\n')[0]));
writeJSON('crowd.json', { res, errors: log.errors });
await browser.close(); await srv.close();
