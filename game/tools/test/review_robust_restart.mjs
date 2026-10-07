// Scene restart hygiene: run the in-game reset 6 times and compare listener / object / texture /
// sound / heap counts (anything not cleaned on shutdown accumulates).
//   node tools/test/review_robust_restart.mjs
import { newPage, bootToGame, launch, start, writeJSON } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await newPage(browser);
const cdp = await page.context().newCDPSession(page);
await cdp.send('Performance.enable');
await bootToGame(page, srv.url + 'index.html');
const snap = async (label) => {
  await cdp.send('HeapProfiler.collectGarbage');
  const h = await cdp.send('Runtime.getHeapUsage');
  const m = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  const s = await page.evaluate(() => {
    const g = window.__FV.game, gs = g.scene.getScene('Game'), ui = g.scene.getScene('UI');
    const ev = (em) => { if (!em || typeof em.eventNames !== "function") return -1; let n = 0; for (const e of em.eventNames()) n += em.listenerCount(e); return n; };
    return { gameEvents: ev(g.events), scale: ev(g.scale), anims: ev(g.anims), sound: ev(g.sound), textures: g.textures.getTextureKeys().length, sounds: g.sound.sounds.length, children: gs.children.length, uiChildren: ui.children.length, gameTimers: gs.time._active.length, inputPlugin: ev(ui.input), kb: g.input.keyboard ? ev(g.input.keyboard) : -1, emittersAudioAmb: Object.keys(window.__FV.scene.sys.game.sound.sounds.reduce((a, s) => (a[s.key] = (a[s.key] || 0) + 1, a), {})).length };
  });
  return { label, heapMB: +(h.usedSize / 1048576).toFixed(2), jsListeners: m.JSEventListeners, docs: m.Documents, ...s };
};
const rows = [await snap('boot')];
for (let i = 1; i <= 6; i++) {
  await page.evaluate(async () => {
    const FV = window.__FV, g = FV.game;
    for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(false);
    FV.give(300); FV.unlockAll();
    const W = (n) => new Promise((r) => { const f0 = g.loop.frame; const iv = setInterval(() => { if (g.loop.frame - f0 >= n) { clearInterval(iv); r(); } }, 10); });
    await W(60);
    FV.reset();
    await W(60);
  });
  rows.push(await snap('after reset ' + i));
}
for (const r of rows) console.log(JSON.stringify(r));
writeJSON('restart.json', { rows, errors: log.errors, warnings: log.warnings });
console.log('errors', log.errors);
await browser.close(); await srv.close();
