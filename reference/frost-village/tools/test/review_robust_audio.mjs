// Audio robustness: Safari-like mp3-only path, .ogg network failure, mute persistence,
// overlapping sfx during busy moments (near vs far from the work), window blur accumulation,
// visibility hidden/visible (loop pause, autosave, timers).
//   node tools/test/review_robust_audio.mjs [only=<name>]
import { newPage, bootToGame, launch, start, sleep, waitFor, tapStart, writeJSON, OUT } from './review_robust_lib.mjs';

const only = (process.argv.find((a) => a.startsWith('only=')) || '').slice(5);
const run = (n) => !only || only === n;
const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const browser = await launch();
const results = {};
const hide = (page) => page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(false); });

async function audioInventory(page) {
  return page.evaluate(() => {
    const g = window.__FV.game, out = {};
    const keys = g.cache.audio.getKeys();
    for (const k of ['bgm_village', 'bgm_title', 'amb_wind', 'amb_sea', 'amb_fire']) {
      const b = g.cache.audio.get(k);
      out[k] = b ? { dur: +b.duration.toFixed(4), sr: b.sampleRate, len: b.length } : null;
    }
    return { cached: keys.length, ctxRate: g.sound.context && g.sound.context.sampleRate, ctxState: g.sound.context && g.sound.context.state, loops: out, device: { ogg: g.device.audio.ogg, mp3: g.device.audio.mp3, opus: g.device.audio.opus } };
  });
}

// ---------------------------------------------------------------- A. normal (ogg) vs Safari-like mp3-only
for (const mode of ['ogg', 'mp3only', 'oggBlockedNoFallback']) {
  if (!run(mode)) continue;
  const { page, ctx, log } = await newPage(browser);
  const reqs = { ogg: 0, mp3: 0, oggAborted: 0 };
  page.on('request', (r) => { if (/\.ogg$/.test(r.url())) reqs.ogg++; if (/\.mp3$/.test(r.url())) reqs.mp3++; });
  if (mode === 'mp3only') {
    await page.addInitScript(() => {
      const orig = HTMLMediaElement.prototype.canPlayType;
      HTMLMediaElement.prototype.canPlayType = function (t) { return /ogg|vorbis|opus|webm/i.test(t) ? '' : orig.call(this, t); };
    });
  }
  if (mode !== 'ogg') await page.route('**/*.ogg', (route) => { reqs.oggAborted++; route.abort(); });
  const r = { mode };
  try {
    await bootToGame(page, URL);
    r.inv = await audioInventory(page);
    const manifestKeys = await page.evaluate(() => Object.keys(window.__FV.game.cache.json.get('manifest_audio').audio));
    r.manifestAudioKeys = manifestKeys.length;
    r.missingAudio = await page.evaluate((ks) => ks.filter((k) => !window.__FV.game.cache.audio.exists(k)), manifestKeys);
    await hide(page);
    await sleep(1500);
    r.playing = await page.evaluate(() => window.__FV.game.sound.sounds.filter((s) => s.isPlaying).map((s) => s.key));
  } catch (e) { r.error = e.message.split('\n')[0]; }
  r.reqs = reqs;
  r.errors = log.errors.slice(0, 5);
  r.warnings = [...new Set(log.warnings)].slice(0, 6);
  r.failedReq = log.failedReq.length;
  results[mode] = r;
  console.log(mode, JSON.stringify(r).slice(0, 1400));
  await ctx.close();
}

// ---------------------------------------------------------------- B. mute toggles persist + ambience while the panel is open
if (run('mute')) {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hide(page);
  await sleep(1500);
  const r = {};
  r.beforeToggle = await page.evaluate(() => window.__FV.game.sound.sounds.filter((s) => s.isPlaying).map((s) => s.key + '@' + s.volume.toFixed(3)));
  r.toggle = await page.evaluate(async () => {
    const g = window.__FV.game, ui = g.scene.getScene('UI');
    ui.openSettings();
    const press = (txt) => { const b = ui.panelItems.find((o) => o.text && o.text.text === txt); if (b) { b.emit('pointerdown'); return true; } return false; };
    press('켜짐'); // sound -> off (first ON button)
    await new Promise((r) => setTimeout(r, 300));
    press('켜짐'); // music -> off
    await new Promise((r) => setTimeout(r, 1500));
    const whilePanelOpen = g.sound.sounds.filter((s) => s.isPlaying).map((s) => s.key + '@' + s.volume.toFixed(3));
    ui.closeSettings(true);
    await new Promise((r) => setTimeout(r, 2500));
    const afterClose = g.sound.sounds.filter((s) => s.isPlaying).map((s) => s.key + '@' + s.volume.toFixed(3));
    return { whilePanelOpen, afterClose, settings: JSON.parse(localStorage.getItem('frostVillage.settings.v1')) };
  });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 30000);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 20000);
  await hide(page);
  await sleep(2500);
  r.afterReload = await page.evaluate(() => ({ settings: JSON.parse(localStorage.getItem('frostVillage.settings.v1')), playing: window.__FV.game.sound.sounds.filter((s) => s.isPlaying).map((s) => s.key + '@' + s.volume.toFixed(3)) }));
  r.errors = log.errors;
  results.mute = r;
  console.log('mute', JSON.stringify(r));
  await ctx.close();
}

// ---------------------------------------------------------------- C. busy moment: how many sfx, near vs far
if (run('busy')) {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hide(page);
  const r = await page.evaluate(async () => {
    const FV = window.__FV, g = FV.game, gs = FV.scene;
    FV.unlockAll();
    // all 10 workers keep working forever: never let their station input fill
    for (const s of gs.stationList) { s.inStack.max = 1e6; }
    const counts = {}; let maxPlaying = 0, sumPlaying = 0, n = 0;
    const sp = g.sound.play.bind(g.sound);
    g.sound.play = function (k, c) { counts[k] = (counts[k] || 0) + 1; return sp(k, c); };
    const measure = async (label, x, y, frames) => {
      for (const k in counts) delete counts[k];
      maxPlaying = 0; sumPlaying = 0; n = 0;
      FV.teleport(x, y);
      const f0 = g.loop.frame, t0 = gs.time.now;
      while (g.loop.frame - f0 < frames) {
        await new Promise((r) => setTimeout(r, 50));
        const p = g.sound.sounds.filter((s) => s.isPlaying).length;
        maxPlaying = Math.max(maxPlaying, p); sumPlaying += p; n++;
      }
      const secs = (gs.time.now - t0) / 1000;
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      return { label, at: [x, y], gameSecs: +secs.toFixed(1), playsPerSec: +(total / secs).toFixed(1), maxConcurrent: maxPlaying, avgConcurrent: +(sumPlaying / n).toFixed(1), byKey: Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, v]) => [k, +(v / secs).toFixed(2)])) };
    };
    await new Promise((r) => setTimeout(r, 4000));
    const plaza = FV.where('shelf');
    const near = await measure('plaza (centre of the loop)', plaza.x + 40, plaza.y + 80, 600);
    const far = await measure('far south-east corner (no work on screen)', 1700, 2540, 600);
    const cam = gs.cameras.main.worldView;
    return { near, far, farView: { x: Math.round(cam.x), y: Math.round(cam.y), w: Math.round(cam.width), h: Math.round(cam.height) } };
  });
  r.errors = log.errors;
  results.busy = r;
  console.log('busy', JSON.stringify(r, null, 1));
  await ctx.close();
}

// ---------------------------------------------------------------- D. window blur (game keeps running, context suspended)
if (run('blur')) {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hide(page);
  const r = await page.evaluate(async () => {
    const FV = window.__FV, g = FV.game, gs = FV.scene;
    FV.unlockAll();
    for (const s of gs.stationList) s.inStack.max = 1e6;
    const p = FV.where('shelf'); FV.teleport(p.x + 40, p.y + 80);
    await new Promise((r) => setTimeout(r, 3000));
    const snap = () => ({ frame: g.loop.frame, ctx: g.sound.context.state, sounds: g.sound.sounds.length, playing: g.sound.sounds.filter((s) => s.isPlaying).length });
    const before = snap();
    window.dispatchEvent(new Event('blur'));
    await new Promise((r) => setTimeout(r, 300));
    const f0 = g.loop.frame;
    while (g.loop.frame - f0 < 900) await new Promise((r) => setTimeout(r, 100));   // ~15 s of 60 fps game time
    const blurred = snap();
    window.dispatchEvent(new Event('focus'));
    await new Promise((r) => setTimeout(r, 400));
    const refocused = snap();
    await new Promise((r) => setTimeout(r, 3000));
    const later = snap();
    return { before, blurred, refocused, later, framesWhileBlurred: blurred.frame - f0 };
  });
  r.errors = log.errors;
  results.blur = r;
  console.log('blur', JSON.stringify(r));
  await ctx.close();
}

// ---------------------------------------------------------------- E. visibility hidden -> visible
if (run('visibility')) {
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hide(page);
  const r = await page.evaluate(async () => {
    const FV = window.__FV, g = FV.game, gs = FV.scene;
    FV.give(37);
    window.__FV.setInput(1, 0);   // simulate holding the joystick
    gs.ui; const Input = null; void Input;
    localStorage.removeItem('frostVillage.save.v1');
    let hidden = true;
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (hidden ? 'hidden' : 'visible') });
    const t0 = gs.time.now, f0 = g.loop.frame;
    document.dispatchEvent(new Event('visibilitychange'));
    const savedOnHide = !!localStorage.getItem('frostVillage.save.v1');
    await new Promise((r) => setTimeout(r, 8000));
    const whileHidden = { frames: g.loop.frame - f0, ctx: g.sound.context.state };
    hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    const f1 = g.loop.frame, t1 = gs.time.now;
    await new Promise((r) => setTimeout(r, 1500));
    window.__FV.setInput(0, 0);
    return { savedOnHide, whileHidden, gameTimeJumpMs: Math.round(t1 - t0), framesAfter: g.loop.frame - f1, ctxAfter: g.sound.context.state, loopDelta: g.loop.delta };
  });
  r.errors = log.errors;
  results.visibility = r;
  console.log('visibility', JSON.stringify(r));
  await ctx.close();
}

writeJSON('audio_results.json', results);
await browser.close(); await srv.close();
