// Input robustness: multi-touch joystick ownership, release outside the canvas (touch & mouse),
// touchcancel, keyboard + touch together, blur with a key held, very fast taps on buttons / field.
//   node tools/test/review_robust_input.mjs
import { newPage, bootToGame, launch, start, sleep, writeJSON, OUT } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const browser = await launch();
const results = {};
const hide = (page) => page.evaluate(() => { const g = window.__FV.game; g.scene.getScene('Game').cameras.main.setVisible(false); });
const frames = (page, n) => page.evaluate((n) => new Promise((r) => { const g = window.__FV.game, f0 = g.loop.frame; const iv = setInterval(() => { if (g.loop.frame - f0 >= n) { clearInterval(iv); r(); } }, 16); }), n);
const joy = (page) => page.evaluate(() => {
  const ui = window.__FV.game.scene.getScene('UI'), gs = window.__FV.scene;
  // Input is a module singleton; reach it through the joystick visuals + player velocity
  return { knobVisible: ui.joyKnob.visible, vx: Math.round(gs.player.vx), vy: Math.round(gs.player.vy), x: Math.round(gs.player.x), y: Math.round(gs.player.y) };
});

// ---------------------------------------------------------------- touch tests (mobile viewport)
{
  const { page, ctx, log } = await newPage(browser, { viewport: { width: 390, height: 844 } });
  await bootToGame(page, URL);
  await hide(page);
  const cdp = await ctx.newCDPSession(page);
  const T = (type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map(([x, y, id]) => ({ x, y, id })) });
  const r = {};
  await page.evaluate(() => { const n = window.__FV.where('zone:plaza'); window.__FV.teleport(n.x, n.y + 120); });
  await frames(page, 10);
  // A: finger 1 drives right, finger 2 lands & drags up -> joystick must stay with finger 1
  await T('touchStart', [[120, 600, 1]]);
  await T('touchMove', [[200, 600, 1]]);
  await frames(page, 15);
  r.finger1Right = await joy(page);
  await T('touchStart', [[200, 600, 1], [300, 400, 2]]);
  await T('touchMove', [[200, 600, 1], [300, 250, 2]]);
  await frames(page, 15);
  r.finger2DragsUp = await joy(page);
  // finger 1 lifts while finger 2 stays down and keeps moving
  await T('touchEnd', [[300, 250, 2]]);
  await T('touchMove', [[320, 200, 2]]);
  await frames(page, 15);
  r.afterFinger1Up_finger2Moving = await joy(page);
  await T('touchEnd', []);
  await frames(page, 5);
  r.allUp = await joy(page);
  // B: touchcancel (system gesture / notification) while steering
  await T('touchStart', [[120, 600, 3]]);
  await T('touchMove', [[220, 600, 3]]);
  await frames(page, 10);
  r.beforeCancel = await joy(page);
  await T('touchCancel', []);
  await frames(page, 15);
  r.afterCancel = await joy(page);
  // C: settings button tapped by a 2nd finger while steering
  await T('touchStart', [[120, 600, 4]]);
  await T('touchMove', [[220, 600, 4]]);
  await frames(page, 5);
  const btn = await page.evaluate(() => { const ui = window.__FV.game.scene.getScene('UI'); const c = document.querySelector('canvas').getBoundingClientRect(); const k = c.width / ui.scale.gameSize.width; return { x: c.left + ui.setBtn.x * k, y: c.top + ui.setBtn.y * k }; });
  await T('touchStart', [[220, 600, 4], [btn.x, btn.y, 5]]);
  await T('touchEnd', [[220, 600, 4]]);
  await frames(page, 10);
  r.settingsWhileSteering = { panelOpen: await page.evaluate(() => window.__FV.game.scene.getScene('UI').panelOpen), gamePaused: await page.evaluate(() => window.__FV.game.scene.isPaused('Game')) };
  await T('touchMove', [[300, 600, 4]]);
  await T('touchEnd', []);
  await page.evaluate(() => window.__FV.game.scene.getScene('UI').closeSettings(true));
  await frames(page, 10);
  r.afterClose = await joy(page);
  // D: very fast taps on the settings button (40 taps)
  for (let i = 0; i < 40; i++) { await T('touchStart', [[btn.x, btn.y, 10 + i]]); await T('touchEnd', []); }
  await frames(page, 5);
  r.fastTapsSettings = await page.evaluate(() => { const ui = window.__FV.game.scene.getScene('UI'); return { panelOpen: ui.panelOpen, panels: ui.children.list.filter((o) => o.type === 'Container' && o.depth === 80).length, paused: window.__FV.game.scene.isPaused('Game') }; });
  // fast taps on the language button inside the panel (20 taps => should end on the starting language)
  const lang = await page.evaluate(() => { const ui = window.__FV.game.scene.getScene('UI'); const b = ui.panelItems.find((o) => o.text && (o.text.text === '한국어' || o.text.text === 'English')); const c = document.querySelector('canvas').getBoundingClientRect(); const k = c.width / ui.scale.gameSize.width; return b && { x: c.left + b.x * k, y: c.top + b.y * k, before: b.text.text }; });
  if (lang) {
    for (let i = 0; i < 20; i++) { await T('touchStart', [[lang.x, lang.y, 100 + i]]); await T('touchEnd', []); }
    await frames(page, 5);
    r.fastTapsLanguage = await page.evaluate(() => { const ui = window.__FV.game.scene.getScene('UI'); const b = ui.panelItems.find((o) => o.text && (o.text.text === '한국어' || o.text.text === 'English')); return { label: b && b.text.text, panelItems: ui.panelItems.length, uiChildren: ui.children.length }; });
    r.fastTapsLanguage.before = lang.before;
  }
  await page.evaluate(() => window.__FV.game.scene.getScene('UI').closeSettings(true));
  // E: 150 random taps on the field in quick succession
  for (let i = 0; i < 150; i++) { const x = 30 + Math.random() * 330, y = 200 + Math.random() * 600; await T('touchStart', [[x, y, 300 + i]]); if (i % 3) await T('touchMove', [[x + 20, y, 300 + i]]); await T('touchEnd', []); }
  await frames(page, 10);
  r.afterFieldTaps = await joy(page);
  r.errors = log.errors;
  results.touch = r;
  console.log('touch', JSON.stringify(r, null, 0));
  await ctx.close();
}

// ---------------------------------------------------------------- desktop: release outside canvas, keyboard + touch, blur with key held
{
  const { page, ctx, log } = await newPage(browser, { viewport: { width: 1280, height: 800 }, isMobile: false, hasTouch: true });
  await bootToGame(page, URL);
  await hide(page);
  const cdp = await ctx.newCDPSession(page);
  const T = (type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map(([x, y, id]) => ({ x, y, id })) });
  const r = {};
  const cb = await page.evaluate(() => { const c = document.querySelector('canvas').getBoundingClientRect(); return { l: c.left, r: c.right, t: c.top, b: c.bottom }; });
  r.canvasRect = cb;
  await page.evaluate(() => { const n = window.__FV.where('zone:plaza'); window.__FV.teleport(n.x, n.y + 120); });
  const cx = (cb.l + cb.r) / 2, cy = (cb.t + cb.b) / 2 + 100;
  // mouse drag, release outside the canvas (page margin)
  await page.mouse.move(cx, cy); await page.mouse.down(); await page.mouse.move(cx + 60, cy, { steps: 4 });
  await frames(page, 8);
  r.mouseDragging = await joy(page);
  await page.mouse.move(cb.l - 150, cy, { steps: 6 });
  await page.mouse.up();
  await frames(page, 10);
  r.mouseReleasedOutside = await joy(page);
  // same with touch
  await T('touchStart', [[cx, cy, 1]]); await T('touchMove', [[cx + 60, cy, 1]]);
  await frames(page, 8);
  await T('touchMove', [[cb.r + 150, cy, 1]]); await T('touchEnd', []);
  await frames(page, 10);
  r.touchReleasedOutside = await joy(page);
  // mouse leaves the browser window entirely while held (mouseup never arrives)
  await page.mouse.move(cx, cy); await page.mouse.down(); await page.mouse.move(cx + 60, cy, { steps: 4 });
  await page.evaluate(() => { const c = document.querySelector('canvas'); c.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: null })); document.dispatchEvent(new MouseEvent('mouseleave')); window.dispatchEvent(new Event('blur')); });
  await frames(page, 10);
  r.mouseHeldThenWindowBlur = await joy(page);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.mouse.up();
  await frames(page, 5);
  // keyboard + touch at once
  await page.keyboard.down('d');
  await T('touchStart', [[cx, cy, 2]]); await T('touchMove', [[cx - 80, cy, 2]]);
  await frames(page, 10);
  r.keyDPlusTouchLeft = await joy(page);
  await page.keyboard.up('d');
  await frames(page, 10);
  r.keyReleasedTouchStillLeft = await joy(page);
  await T('touchEnd', []);
  // blur with a key held
  await page.keyboard.down('d');
  await frames(page, 6);
  r.keyHeld = await joy(page);
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await frames(page, 15);
  r.afterBlurKeyHeld = await joy(page);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.keyboard.up('d');
  await frames(page, 5);
  r.errors = log.errors;
  results.desktop = r;
  console.log('desktop', JSON.stringify(r));
  await ctx.close();
}

// ---------------------------------------------------------------- double tap on title / tap during fade
{
  const { page, ctx, log } = await newPage(browser);
  await page.goto(URL, { waitUntil: 'load' });
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await page.waitForFunction(() => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), null, { timeout: 30000 });
  await sleep(300);
  await page.evaluate(() => { const G = window.__FV.game.scene.getScene('Game'); const c = G.create; window.__creates = 0; G.create = function (...a) { window.__creates++; return c.apply(this, a); }; });
  const c = await page.$('canvas'); const b = await c.boundingBox();
  for (let i = 0; i < 12; i++) await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height * 0.6);
  await page.waitForFunction(() => window.__FV.state && window.__FV.game.scene.isActive('UI'), null, { timeout: 20000 });
  await sleep(1500);
  results.titleMultiTap = { gameCreates: await page.evaluate(() => window.__creates), music: await page.evaluate(() => window.__FV.game.sound.sounds.filter((s) => s.key.startsWith('bgm')).map((s) => s.key + (s.isPlaying ? ':playing' : ':stopped'))), errors: log.errors };
  console.log('titleMultiTap', JSON.stringify(results.titleMultiTap));
  await ctx.close();
}

writeJSON('input_results.json', results);
await browser.close(); await srv.close();
