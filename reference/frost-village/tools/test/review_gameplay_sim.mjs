// Gameplay-review simulation: a bot plays from a fresh save using only __FV.setInput (joystick),
// at a fixed 60 fps simulated clock (headlessStep + fake Date.now), much faster than real time.
//   node tools/test/review_gameplay_sim.mjs --name smart --policy smart --upg greedy --minutes 40 [--bal '{"prices":{"item_fish_cooked":5}}'] [--shots]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const has = (k) => args.includes(k);
const NAME = opt('--name', 'run');
const OUT = opt('--out', '/tmp/fv_review/gameplay');
fs.mkdirSync(OUT, { recursive: true });
const MINUTES = Number(opt('--minutes', '40'));
const AFTER = Number(opt('--after', '0'));            // keep playing N minutes after village complete
const BAL = opt('--bal', '');
const WORLDO = opt('--world', '');
const SHOTS = has('--shots');
const HERE = path.dirname(fileURLToPath(import.meta.url));

const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await openPage(browser, srv.url + 'index.html', { viewport: { width: 360, height: 720 }, dpr: 1 });
const t0 = Date.now();
try {
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 120000);
  await page.evaluate(async (bal) => {
    const m = await import(new URL('src/data/balance.js', location.href).href);
    window.__BAL = m.BALANCE;
    const merge = (a, b) => { for (const k in b) { if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) merge(a[k] = a[k] || {}, b[k]); else a[k] = b[k]; } };
    if (bal) merge(window.__BAL, JSON.parse(bal[0] || 'null') || {});
    const w = await import(new URL('src/data/world.js', location.href).href);
    window.__WORLD = w.WORLD;
    if (bal[1]) merge(window.__WORLD, JSON.parse(bal[1]));
  }, [BAL, WORLDO]);
  await sleep(300);
  await tapStart(page);
  await waitFor(page, () => window.__FV.scene && window.__FV.game.scene.isActive('UI') && window.__FV.scene.player, 120000);
  await sleep(500);
  // fixed-step driver
  await page.evaluate(() => {
    const game = window.__FV.game;
    game.loop.sleep();
    const realNow = Date.now.bind(Date);
    let D = realNow();
    let T = game.loop.time || performance.now();
    Date.now = () => D;
    const DT = 1000 / 60;
    window.__sim = {
      simT: 0,
      run(sec, botTick) {
        const n = Math.round(sec * 60);
        for (let i = 0; i < n; i++) {
          if (botTick) botTick(DT / 1000);
          T += DT; D += DT; this.simT += DT / 1000;
          game.headlessStep(T, DT);
        }
      },
      render() { T += DT; D += DT; this.simT += DT / 1000; game.step(T, DT); },
    };
  });
  if (has('--fixmarket')) await page.evaluate(() => {
    // in-memory patch for measurement only: a partly served customer switches to another food when theirs runs out
    const m = window.__FV.scene.market, orig = m.update.bind(m);
    const FOODS = ['item_fish_cooked', 'item_bread', 'item_meat_cooked'];
    m.update = (dt) => { const f = m.queue[0]; if (f && f.state === 'wait' && f.arrived && f.need > 0 && m.stock.countOf(f.want.type) === 0) { for (const x of FOODS) if (m.stock.countOf(x) > 0) { f.setWant(x); break; } } return orig(dt); };
  });
  await page.addScriptTag({ path: path.join(HERE, 'review_gameplay_bot.js') });
  await page.evaluate((o) => Object.assign(window.__bot.opts, o), { policy: opt('--policy', 'smart'), upg: opt('--upg', 'greedy'), minBatch: Number(opt('--minbatch', '3')), think: Number(opt('--think', '0')), mag: Number(opt('--mag', '1')) });

  let completeAt = -1, lastEvents = 0;
  const samples = [];
  const shot = async (n) => {
    if (!SHOTS) return;
    await page.evaluate(() => { for (let i = 0; i < 3; i++) window.__sim.render(); });
    await sleep(120);
    await page.screenshot({ path: path.join(OUT, `${NAME}_${n}.jpg`), type: 'jpeg', quality: 70 });
  };
  await shot('000_start');
  for (let sec = 0; sec < MINUTES * 60; sec += 10) {
    const r = await page.evaluate(() => {
      window.__sim.run(10, window.__bot.tick);
      const s = window.__bot.sample();
      return { s, events: window.__bot.events.length, done: window.__FV.state().done };
    });
    samples.push(r.s);
    if (r.events > lastEvents) {
      const evs = await page.evaluate((k) => window.__bot.events.slice(k), lastEvents);
      for (const e of evs) { console.log(`[${NAME}] t=${e.t.toFixed(1)}s (${(e.t / 60).toFixed(2)} min) ${e.ev} coins=${e.coins ?? ''}`); await shot(String(Math.round(e.t)).padStart(4, '0') + '_' + e.ev); }
      lastEvents = r.events;
    }
    if (sec % 60 === 50) console.log(`[${NAME}] ${r.s.t}s coins=${r.s.coins} earned=${r.s.earned} cap=${r.s.cap} task=${r.s.task} st=${JSON.stringify(r.s.st)} mk=${JSON.stringify(r.s.mk)} w=${r.s.w} obj=${r.s.obj} shelf=${JSON.stringify(r.s.shelf)} front=${JSON.stringify(r.s.front)} leaving=${r.s.leaving} stall=${r.s.stall}  (wall ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    if (completeAt < 0 && r.done.includes('hire_hunter')) completeAt = r.s.t;
    if (completeAt >= 0 && r.s.t >= completeAt + AFTER * 60) break;
  }
  const fin = await page.evaluate(() => {
    const b = window.__bot;
    return { events: b.events, taskTime: b.taskTime, noGuideRuns: b.noGuideRuns, stuck: b.stuckEvents, blockedT: b.blockedT, idleT: b.idleT, huntCatches: b.huntCatches, accidental: b.accidental || 0, accList: (b.accList || []).slice(0, 60), huntChaseTime: b.huntChaseTime, log: b.log.slice(-400), state: window.__FV.state(), simT: window.__sim.simT };
  });
  await shot('999_end');
  fs.writeFileSync(path.join(OUT, NAME + '.json'), JSON.stringify({ args, fin, samples, errors: log.errors }, null, 1));
  console.log(`[${NAME}] DONE sim=${fin.simT.toFixed(0)}s completeAt=${completeAt} stuck=${fin.stuck} accidentalPay=${fin.accidental} blocked=${fin.blockedT.toFixed(1)} idle=${fin.idleT.toFixed(1)} tasks=${JSON.stringify(Object.fromEntries(Object.entries(fin.taskTime).map(([k, v]) => [k, Math.round(v)])))} errors=${log.errors.length} wall=${((Date.now() - t0) / 1000).toFixed(0)}s`);
  for (const e of log.errors.slice(0, 5)) console.log('  ERR', e.slice(0, 300));
} catch (e) {
  console.log('FATAL', e && e.stack || e);
  for (const e2 of log.errors.slice(0, 5)) console.log('  ERR', e2.slice(0, 300));
}
await browser.close();
await srv.close();
