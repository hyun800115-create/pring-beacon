// Soak test: unlock everything, let the workers run for N seconds, sample state + object counts.
//   node tools/test/soak.mjs [seconds=120]
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';
const secs = Number(process.argv[2] || 120);
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 390, height: 844 }, dpr: 1 });
await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
await page.reload();
await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
await sleep(400); await tapStart(page);
await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 20000);
await page.evaluate(() => { window.__FV.give(100); window.__FV.unlockAll(); window.__FV.teleport(1000, 1000); });
const t0 = Date.now();
let first = null, last = null;
while (Date.now() - t0 < secs * 1000) {
  await sleep(10000);
  const s = await page.evaluate(() => {
    const st = window.__FV.state(), gs = window.__FV.scene;
    return { t: Math.round(gs.time.now / 1000), children: gs.children.length, tweens: gs.tweens.getTweens().length, pool: gs.effects.itemPool.length,
      workers: st.workers.map((w) => w.type[0] + ':' + w.state + '/' + w.carry).join(' '),
      stations: Object.entries(st.stations).map(([k, v]) => k.slice(0, 5) + ' ' + v.in + '>' + v.out).join(' | '),
      market: st.market, trade: st.trade, coins: st.coins };
  });
  if (!first) first = s; last = s;
  console.log(JSON.stringify(s));
}
console.log('errors', log.errors.length, log.errors.slice(0, 5).join('\n'));
console.log('children growth', first.children, '->', last.children, ' tweens', first.tweens, '->', last.tweens);
await browser.close(); await srv.close();
