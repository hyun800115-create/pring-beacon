// 계절 모습 시험: 마을을 짓고 네 계절을 같은 두 카메라(마을 가까이 · 넓은 숲)로 찍는다. 밤 장면, 천천히 바뀌는 장면,
// 초당 프레임, 오류, 나무꾼이 활엽수를 베는지까지 본다.
//   cd game && PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers node tools/test/seasons_test.mjs <출력폴더> [--soft] [--quick] [--models]
//   (기본은 창을 띄우지 않고 진짜 그래픽카드를 쓰는 크롬 = launchGpu. --soft 는 소프트웨어 그리기라 느리다)
//   --models : 계절 모델(활엽수·소나무·덤불·꽃 무더기 등)을 한 줄로 세워 가까이 찍기만 하고 끝낸다
//   --nopng  : 봄·여름·가을 땅 그림 요청을 일부러 막아 '대신 그림'(그 자리에서 그리는 풀밭)으로 돌려 본다
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, launchGpu } from './pw.mjs';

const OUT = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : '../.cache/shots/seasons';
fs.mkdirSync(OUT, { recursive: true });
const soft = process.argv.includes('--soft');
const quick = process.argv.includes('--quick');
const modelsOnly = process.argv.includes('--models');
const noPng = process.argv.includes('--nopng');
const srv = await start(0);
const b = soft ? await launch() : await launchGpu();
const page = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
const errs = [];
page.on('pageerror', (e) => errs.push('pageerror: ' + (e.stack || e)));
if (noPng) await page.route(/ground_(grass_spring|grass_summer|autumn)\.png/, (r) => r.fulfill({ status: 404, body: 'not found' }));
page.on('console', (m) => { if ((m.type() === 'error' || m.type() === 'warning') && !m.text().includes('404') && !/GPU stall|ReadPixels/.test(m.text())) errs.push(m.type() + ': ' + m.text()); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);
const shot = async (n) => { await page.screenshot({ path: path.join(OUT, n) }); console.log('  shot', n); };
const log = (...a) => console.log(...a);
const fpsNow = async (ms = 2500) => {   // 실제 화면 프레임 세기 (requestAnimationFrame)
  return page.evaluate((ms2) => new Promise((res) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 < ms2) requestAnimationFrame(f); else res(Math.round(n * 1000 / (performance.now() - t0))); }; requestAnimationFrame(f); }), ms);
};
const result = { fps: {}, checks: {} };
const check = (name, ok, info = '') => { result.checks[name] = ok; log(ok ? '  OK  ' : '  FAIL', name, info); };

try {
  await page.goto(srv.url + 'index.html');
  await page.waitForFunction(() => window.__SM && window.__SM.api && window.__SM.api.season, null, { timeout: 180000 });
  log('season at start', JSON.stringify((await api('season')).name));
  const st = await api('start');
  if (modelsOnly) {
    // 계절 모델 줄 세우기 (마을 자리 옆 빈 땅에)
    const rows = [
      ['season_decid_a_winter', 'season_decid_a_spring', 'season_decid_a_summer', 'season_decid_a_autumn'],
      ['season_decid_b_winter', 'season_decid_b_spring', 'season_decid_b_summer', 'season_decid_b_autumn'],
      ['season_pine_a', 'season_pine_b', 'season_pine_c', 'season_stump'],
      ['season_bush_spring', 'season_bush_summer', 'season_bush_autumn', 'season_flowers_a', 'season_flowers_b', 'season_grass', 'season_grass_dry', 'season_leaves'],
    ];
    const at = await page.evaluate(async ([rows2, x0, z0]) => {
      const g = window.__SM.game, sc = g.stage.scene, w = g.world;
      // 둘레 자연물 치우기 (잘 보이게)
      const near = [];
      w.natureNear(x0, z0, 16, (o) => near.push(o));
      for (const o of near) w.removeNature(o);
      for (let r = 0; r < rows2.length; r++) for (let i = 0; i < rows2[r].length; i++) {
        const k = rows2[r][i];
        await g.lib.loadProp(k);
        const o = g.lib.prop(k);
        const small = r === 3;
        o.position.set(x0 + (small ? i * 1.3 - 4.5 : i * 3.2 - 4.8), 0, z0 + r * 3.4 - 5);
        if (small) o.scale.setScalar(1.6);
        o.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } });
        sc.add(o);
      }
      return [x0, z0];
    }, [rows, st.x + 30, st.z + 30]);
    await api('setSeason', 2); await api('skipTo', 0.3); await api('speed', 0);
    await api('cam', at[0], at[1], 24, 0.0, 0.5); await sleep(2500);
    await shot('models_front.png');
    await api('cam', at[0], at[1], 22, 0.8, 0.75); await sleep(1500);
    await shot('models_top.png');
    throw new Error('__done');
  }
  await api('settle', st.x + 6, st.z - 6, 0.3); await api('finishAll');
  await sleep(1200);
  const h = await api('hall');
  const place = async (type, dx, dz, rot = 0) => {
    const sp = await api('findSpot', type, h.x + dx, h.z + dz, rot);
    if (!sp) { log('no spot', type); return null; }
    const r = await api('build', type, sp[0], sp[1], rot); log('  build', type, typeof r === 'string' ? r : 'ok');
    return sp;
  };
  for (const [t, dx, dz, rot] of [['house', -9, 3, 0.4], ['house', -8, -6, 0.9], ['house', 2, 9, 3.1], ['tavern', 9, 7, -0.6], ['windmill', 11, -4, 0], ['well', -2, 6, 0], ['woodcutter', 15, -12, 0.8], ['coop', -14, 12, 0.5]]) await place(t, dx, dz, rot);
  await api('finishAll');
  // 큰 눈사람 장식: 몸통이 눈 재질이지만 '지붕 눈'이 아니라서 어느 계절에도 녹으면 안 된다 (모자·목도리만 떠 있으면 안 됨)
  const smSpot = await api('findSpot', 'deco_snowman_big', h.x - 3, h.z + 7, 0);
  if (smSpot) {
    await page.evaluate(() => { window.__SM.game.econ.decos.deco_snowman_big = 1; });
    log('  deco snowman', await api('placeDeco', 'deco_snowman_big', smSpot[0], smSpot[1]));
  } else log('no spot for snowman');
  await api('road', [[h.x, h.z + 4], [h.x - 6, h.z + 8], [h.x - 12, h.z + 6]]);
  await api('road', [[h.x, h.z + 4], [h.x + 8, h.z + 3], [h.x + 14, h.z - 6]]);
  await sleep(1500);
  const spots = await page.evaluate(() => { const w = window.__SM.game.world, wc = w.blds.find((b) => b.type === 'woodcutter'); return { lake: w.lake ? [w.lake.cx, w.lake.cz] : null, wc: wc ? [wc.x, wc.z] : null }; });
  const cams = {
    close: [h.x - 1, h.z + 1, 40, 0.5, 0.8],
    wide: [h.x + 8, h.z - 6, 95, 2.4, 0.62],
  };
  if (spots.wc) cams.edge = [spots.wc[0] + 3, spots.wc[1] - 5, 20, 0.9, 0.55];   // 숲 가장자리 (나무·덤불 자리 가까이)
  if (spots.lake) cams.lake = [spots.lake[0], spots.lake[1], 42, 0.7, 0.85];
  const names = ['0_winter', '1_spring', '2_summer', '3_autumn'];
  for (let s = 0; s < 4; s++) {
    const r = await api('setSeason', s);
    await api('skipTo', 0.22); await api('speed', 1);
    log(`season ${s} ${r.name}: trees ${r.trees} decid ${r.decid} (${Math.round(r.decid / r.trees * 100)}%) snow ${r.snowShown}/${r.snow} parts ${r.particles} ground ${r.ground} ice ${r.ice}`);
    check(`season${s}-index`, r.index === s && r.shown === s);
    check(`season${s}-snow`, s === 0 ? r.snowShown === r.snow && r.snow > 0 : r.snowShown === 0, `${r.snowShown}/${r.snow}`);
    if (smSpot) check(`season${s}-snowman`, r.snowBody === 1, `눈사람 몸통 ${r.snowBody}`);
    check(`season${s}-decid`, r.decid / r.trees > 0.18 && r.decid / r.trees < 0.45, `${r.decid}/${r.trees}`);
    const m = r.models;
    const piles = (m.snow_pile_a || 0) + (m.snow_pile_b || 0);
    check(`season${s}-piles`, s === 0 ? piles > 0 : piles === 0, `snow piles ${piles}`);
    if (s !== 0) check(`season${s}-greenpines`, !m.tree_pine_a && !m.tree_pine_b && !m.tree_pine_snow, JSON.stringify(Object.keys(m).filter((k) => k.includes('pine'))));
    for (const [k, c] of Object.entries(cams)) {
      await api('cam', ...c); await sleep(k === 'wide' ? 1800 : 1400);
      await shot(`${names[s]}_${k}.png`);
      if (k === 'wide') { result.fps[names[s]] = await fpsNow(); log('  fps (wide)', result.fps[names[s]]); }
    }
    if (s === 2 || s === 0 || !quick) {
      await api('skipTo', 0.86); await api('cam', ...cams.close); await sleep(2500);
      await shot(`${names[s]}_night.png`);
      await api('skipTo', 0.22);
    }
  }
  // 천천히 바뀌기: 겨울 → (날짜 넘김) 봄
  await api('setSeason', 0); await api('skipTo', 0.22);
  await api('cam', ...cams.close); await sleep(1200);
  await page.evaluate(() => { const c = window.__SM.game.clock; c.day += 4; });
  await sleep(1800);
  const mid = await api('season');
  log('mid-change', JSON.stringify({ changing: mid.changing, melt: mid.melt, ground: mid.ground }));
  check('transition-gradual', mid.changing === true && mid.melt > 0 && mid.melt < 1);
  await shot('4_change_mid.png');
  await sleep(5500);
  const after = await api('season');
  check('transition-done', !after.changing && after.shown === 1 && after.snowShown === 0, JSON.stringify({ changing: after.changing, snow: after.snowShown }));
  if (smSpot) check('transition-snowman', after.snowBody === 1, `눈사람 몸통 ${after.snowBody}`);
  await shot('4_change_done.png');
  if (smSpot) { await api('cam', smSpot[0], smSpot[1], 9, 0.6, 0.45); await sleep(1200); await shot('4_snowman_spring.png'); }
  log('news', JSON.stringify((await api('news')).slice(0, 3)));
  // 놓기 그림자(반투명 건물)에도 여름엔 지붕 눈이 없어야 한다
  await api('setSeason', 2);
  await page.evaluate(() => window.__SM.game.setMode('build:house'));
  await sleep(1500);
  const gh = await page.evaluate(() => { const g = window.__SM.game.ghost; if (!g) return null; let n = 0, shown = 0; g.traverse((o) => { if (o.isMesh && o.material && o.material.name === 'snow') { n++; if (o.visible) shown++; } }); return { n, shown }; });
  check('ghost-nosnow', gh && gh.n > 0 && gh.shown === 0, JSON.stringify(gh));
  await page.evaluate(() => window.__SM.game.setMode('view'));
  // 나무꾼이 활엽수를 베는가 (여름)
  await api('setSeason', 2); await api('skipTo', 0.1); await api('speed', 6);
  const target = await page.evaluate(() => {
    const g = window.__SM.game, w = g.world, wc = w.blds.find((b) => b.type === 'woodcutter');
    if (!wc) return null;
    let best = null, bd = Infinity;
    for (const o of w.nature.values()) if (o.type === 'tree' && o.model.startsWith('season_decid')) { const d = Math.hypot(o.x - wc.x, o.z - wc.z); if (d < bd && d < wc.def.radius - 1) { bd = d; best = o; } }
    if (!best) return null;
    // 다른 나무는 잠깐 예약해 두어 이 활엽수만 고르게
    for (const o of w.nature.values()) if (o.type === 'tree' && o !== best && Math.hypot(o.x - wc.x, o.z - wc.z) < wc.def.radius + 2) { o.reserved = true; o.__t = true; }
    window.__decid = best;
    return { id: best.id, model: best.model, x: best.x, z: best.z, wx: wc.x, wz: wc.z };
  });
  log('decid target', JSON.stringify(target));
  if (target) {
    await api('cam', target.x, target.z, 18, 0.9, 0.7);
    let felled = false, shotTaken = false;
    for (let k = 0; k < 120 && !felled; k++) {
      await sleep(1000);
      const r = await page.evaluate(() => { const w = window.__SM.game.world, o = window.__decid; const ppl = window.__SM.game.people.list.filter((p) => p.job && p.job.bld && p.job.bld.type === 'woodcutter').map((p) => Math.round(Math.hypot(p.x - o.x, p.z - o.z))); let stump = null; w.natureNear(o.x, o.z, 0.3, (q) => { if (q.type === 'stump') stump = q.model; }); return { gone: !w.nature.has(o.id), stump, ppl }; });
      if (!shotTaken && r.ppl.some((d) => d <= 2)) { await sleep(1500); await shot('5_chop.png'); shotTaken = true; }
      if (r.gone) { felled = true; await sleep(800); await shot('5_chop_done.png'); check('woodcutter-decid', r.stump === 'season_stump', 'stump ' + r.stump); }
      if (k % 15 === 0) log('  waiting for woodcutter', JSON.stringify(r));
    }
    if (!felled) check('woodcutter-decid', false, 'not felled in time');
    await page.evaluate(() => { for (const o of window.__SM.game.world.nature.values()) if (o.__t) { o.reserved = false; delete o.__t; } });
  } else check('woodcutter-decid', false, 'no deciduous tree near woodcutter');
  await api('speed', 1);
  // 봉화 → 봄 (겨울에서)
  await api('setSeason', 0); await api('skipTo', 0.3);
  const bsp = await place('beacon', -4, -12, 0);
  if (bsp) {
    await api('beacon');
    await sleep(800);
    const b1 = await api('season');
    await sleep(6500);
    const b2 = await api('season');
    check('beacon-spring', b1.index === 1 && b2.shown === 1 && !b2.changing && b2.snowShown === 0, JSON.stringify({ idx: b1.index, shown: b2.shown, snow: b2.snowShown }));
    await shot('6_beacon_spring.png');
  } else check('beacon-spring', false, 'no spot');
  log('stats', JSON.stringify(await api('stats')));
} catch (e) { if (String(e.message) !== '__done') { errs.push('test: ' + (e.stack || e)); try { await shot('fail.png'); } catch (e2) { /* */ } } }
log('fps', JSON.stringify(result.fps));
log('checks', Object.values(result.checks).filter(Boolean).length + '/' + Object.keys(result.checks).length);
log('errors', errs.length ? '\n' + errs.slice(0, 20).join('\n') : 0);
await b.close(); await srv.close();
