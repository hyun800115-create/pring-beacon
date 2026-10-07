// Resize / orientation: viewport changes on title, in game, with the settings panel open,
// plus a resize storm. Records game size, camera sizes, HUD positions and screenshots.
//   node tools/test/review_robust_resize.mjs
import { newPage, bootToGame, launch, start, sleep, waitFor, writeJSON, OUT } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const browser = await launch();
const results = { title: [], game: [], panel: [] };
const info = (page) => page.evaluate(() => {
  const g = window.__FV.game, ui = g.scene.getScene('UI'), gs = g.scene.getScene('Game');
  const c = document.querySelector('canvas').getBoundingClientRect();
  const o = { gameSize: [g.scale.gameSize.width, g.scale.gameSize.height], canvasCss: [Math.round(c.width), Math.round(c.height), Math.round(c.left), Math.round(c.top)], win: [innerWidth, innerHeight] };
  if (ui && ui.sys.isActive()) {
    o.uiCam = [ui.cameras.main.width, ui.cameras.main.height];
    o.gameCam = [gs.cameras.main.width, gs.cameras.main.height];
    o.setBtnX = Math.round(ui.setBtn.x); o.toastY = Math.round(ui.toastBox.y);
    o.panelOpen = ui.panelOpen;
    if (ui.panelBg) o.panelCenter = [Math.round(ui.panelBg.x), Math.round(ui.panelBg.y)];
  }
  return o;
});
const sizes = [[390, 844], [844, 390], [1280, 800], [360, 640], [430, 932], [768, 1024], [390, 844]];

const { page, ctx, log } = await newPage(browser, { viewport: { width: 390, height: 844 } });
await page.goto(URL, { waitUntil: 'load' });
await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
await page.reload({ waitUntil: 'load' });
await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 30000);
await sleep(500);
for (const [w, h] of sizes.slice(0, 3)) {
  await page.setViewportSize({ width: w, height: h });
  await sleep(700);
  results.title.push({ vp: [w, h], ...(await info(page)) });
  await page.screenshot({ path: `${OUT}/resize_title_${w}x${h}.jpg`, type: 'jpeg', quality: 55 });
}
await page.setViewportSize({ width: 390, height: 844 });
await sleep(600);
await bootToGame(page, URL, { fresh: false });
for (const [w, h] of sizes) {
  await page.setViewportSize({ width: w, height: h });
  await sleep(800);
  results.game.push({ vp: [w, h], ...(await info(page)) });
  await page.screenshot({ path: `${OUT}/resize_game_${w}x${h}.jpg`, type: 'jpeg', quality: 55 });
}
// settings panel open, then resize tall -> short
await page.setViewportSize({ width: 430, height: 932 });
await sleep(600);
await page.evaluate(() => window.__FV.game.scene.getScene('UI').openSettings());
await sleep(500);
results.panel.push({ vp: [430, 932], ...(await info(page)) });
await page.setViewportSize({ width: 360, height: 640 });
await sleep(800);
results.panel.push({ vp: [360, 640], ...(await info(page)) });
await page.screenshot({ path: `${OUT}/resize_panel_430x932_to_360x640.jpg`, type: 'jpeg', quality: 55 });
await page.evaluate(() => window.__FV.game.scene.getScene('UI').closeSettings(true));
// storm
const t0 = Date.now();
for (let i = 0; i < 40; i++) { await page.setViewportSize({ width: 300 + (i * 37) % 900, height: 400 + (i * 53) % 700 }); }
await page.evaluate(() => window.dispatchEvent(new Event('orientationchange')));
await page.setViewportSize({ width: 390, height: 844 });
await sleep(900);
results.storm = { ms: Date.now() - t0, final: await info(page), fps: await page.evaluate(() => Math.round(window.__FV.game.loop.actualFps)) };
await page.screenshot({ path: `${OUT}/resize_after_storm.jpg`, type: 'jpeg', quality: 55 });
results.errors = log.errors; results.warnings = [...new Set(log.warnings)].slice(0, 6);
console.log(JSON.stringify(results, null, 1));
writeJSON('resize_results.json', results);
await ctx.close();
await browser.close(); await srv.close();
