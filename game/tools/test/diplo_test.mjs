// 서리골 교역·방문 시험: 교환(짐꾼 행렬)·마실(서로 놀러 가기)·잔치·창·이사·봉화 선물·저장·며칠 동안 저절로 돌아가기
//   PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers node tools/test/diplo_test.mjs <출력폴더> [--swift] [--only trade,visit,outing,late,fest,panel,move,beacon,save,days] [--days 2.3]
//   창을 띄우지 않는다 (기본: 진짜 그래픽카드를 쓰는 숨은 크롬, --swift: 소프트웨어 그리기)
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, launchGpu } from './pw.mjs';

const args = process.argv.slice(2);
const OUT = args[0] && !args[0].startsWith('--') ? args[0] : '../.cache/shots/diplo';
fs.mkdirSync(OUT, { recursive: true });
const has = (k) => args.includes(k);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const only = opt('--only', '') ? opt('--only', '').split(',') : null;
const want = (k) => !only || only.includes(k);
const DAYS = Number(opt('--days', 2.3));

const srv = await start(0);
const b = has('--swift') ? await launch() : await launchGpu();
const page = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
const errs = [], warns = [];
page.on('pageerror', (e) => errs.push('pageerror: ' + (e.stack || e)));
page.on('console', (m) => {
  if (m.type() === 'error' && !m.text().includes('404')) errs.push(m.text());
  if (m.type() === 'warning' && m.text().includes('서리골')) warns.push(m.text());
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);
const shot = async (n) => { await page.screenshot({ path: path.join(OUT, n) }); console.log('  📷', n); };
const log = (...a) => console.log(...a);
const st8 = () => api('diploState');
const fails = [];
const check = (ok, what) => { log(ok ? '  ✔' : '  ✘', what); if (!ok) fails.push(what); };
/** 조건이 될 때까지 기다리기 (ms 마다 확인) */
async function until(fn, ms = 60000, every = 400) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { const r = await fn(); if (r) return r; await sleep(every); }
  return null;
}
const tripOf = (s, kind) => s.trips.find((t) => t.kind === kind);
const camAt = (p, dist = 18, yaw, pitch) => api('cam', p.x, p.z, dist, yaw, pitch);
/** from 쪽에서 p 를 바라보게 (건물에 가리지 않게: 카메라를 건물 반대쪽에) */
const camAway = (p, from, dist = 16, pitch = 0.62) => api('cam', p.x, p.z, dist, Math.atan2(p.x - from.x, p.z - from.z), pitch);
const closeModal = () => page.evaluate(() => { const m = window.__SM.game.hud.modalEl; m.style.display = 'none'; });
const member = (q, kind, name) => { const t = tripOf(q, kind); return t && t.members.find((m) => m.n === name); };

try {
  await page.goto(srv.url + 'index.html?debug=1');
  await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 120000 });
  await closeModal();
  const s0 = await api('start');
  await api('settle', s0.x + 6, s0.z - 6, 0.3); await api('finishAll');
  await page.waitForFunction(() => window.__SM.game.rival.hall, null, { timeout: 60000 });
  const h = await api('hall');
  log('hall', JSON.stringify(h));
  const place = async (type, dx, dz, rot = 0) => {
    const sp = await api('findSpot', type, h.x + dx, h.z + dz, rot);
    if (!sp) { log('no spot', type); return null; }
    const r = await api('build', type, sp[0], sp[1], rot);
    if (typeof r !== 'string') await api('road', [[r.door.x, r.door.z], [h.door.x, h.door.z]]);
    log('build', type, typeof r === 'string' ? r : 'ok');
    return r;
  };
  for (const [t, dx, dz, r] of [['house', -9, 4, 0.4], ['house', -10, -4, -0.3], ['tavern', 9, 9, 0], ['well', 2, 11, 0], ['woodcutter', -14, 10, 0], ['coop', 14, -8, 0]]) await place(t, dx, dz, r);
  await api('finishAll');
  await api('skipTo', 0.12);
  await sleep(1500);
  let s = await st8();
  log('state0', JSON.stringify({ friend: s.friend, theirs: s.theirs, meet: s.meet, ourDoor: s.ourDoor, theirDoor: s.theirDoor, ai: s.ai }));
  check(s.friend === 30, '우호도 처음 30');
  check(await page.evaluate(() => [...document.querySelectorAll('.sysb')].some((b) => b.textContent.includes('서리골') && b.style.display !== 'none')), '🏘️ 서리골 버튼 보임');
  const OD = s.ourDoor, TD = s.theirDoor;
  // 두 마을은 따로 살아요: 우리 주민은 서리골 집을 받지 않고, 다른 마을 사람과는 사귀지 않아요
  check(s.cross.homes === 0, `서리골 집을 받은 우리 주민 없음 (${s.cross.homes})`);
  const compat = await page.evaluate(() => {
    const pp = window.__SM.game.people, L = pp.list.filter((p) => !p.dead && p.stage === 'adult' && !p.spouse && !p.partner);
    const pair = (fa, fb) => { for (const a of L) for (const b of L) if (fa(a) && fb(b) && a.gender !== b.gender) return pp.compatible(a, b); return null; };
    return { cross: pair((a) => !a.ai, (b) => b.ai), same: pair((a) => !a.ai, (b) => !b.ai) };
  });
  check(compat.cross === false && compat.same !== false, `다른 마을 사람끼리는 사랑이 안 싹터요 (다른 마을 ${compat.cross}, 같은 마을 ${compat.same})`);

  // ------------------------------------------------------------ 1. 교환 (짐꾼 행렬)
  if (want('trade')) {
    log('\n== 교환');
    // 거절하면 우호도 -1
    await api('forceTrade');
    const dec = await api('declineTrade');
    check(!dec.err && (await api('friendship')) === 29, `거절 → 우호도 29 (${dec.msg})`);
    await api('friendship', 30);
    const offer = await api('forceTrade');
    log('offer', offer);
    const o = await page.evaluate(() => window.__SM.game.diplo.offer);
    const before = await api('stats');
    const val = (st, t) => (t === 'coins' ? st.coins : st.stock[t] || 0);
    const acc = await api('acceptTrade');
    log('accept', JSON.stringify(acc));
    const after = await api('stats');
    check(Math.round(val(before, o.want.type) - val(after, o.want.type)) === o.want.n, `우리 ${o.want.type} ${o.want.n}개 빠짐 (${val(before, o.want.type)} → ${val(after, o.want.type)})`);
    s = await st8();
    check(s.friend === 35, `우호도 +5 → ${s.friend}`);
    const cv = tripOf(s, 'caravan');
    check(!!cv && cv.members.filter((m) => m.ai).length >= 1, `서리골 짐꾼 ${cv ? cv.members.filter((m) => m.ai).length : 0}명, 우리 짐꾼 ${cv ? cv.members.filter((m) => !m.ai).length : 0}명`);
    // 저장: 길 위의 짐도 담겨요
    const sv = await page.evaluate(() => JSON.parse(JSON.stringify(window.__SM.game.diplo.saveData())));
    check(sv.owed && sv.owed.us.length >= 1, `저장 자료에 길 위의 짐 ${JSON.stringify(sv.owed)}`);
    await api('speed', 2);
    // 모여서 한 줄로 출발
    const walk2 = await until(async () => { const q = await st8(); const t = tripOf(q, 'caravan'); if (!t) return null; const ai = t.members.filter((m) => m.ai); return ai.length && ai.every((m) => m.st === 'walk') ? q : null; }, 60000, 250);
    check(!!walk2, '짐꾼들이 모여서 출발');
    // 가는 길 한가운데
    const mid = await until(async () => {
      const q = await st8(); const t = tripOf(q, 'caravan'); if (!t) return null;
      const m = t.members.find((x) => x.ai && x.st === 'walk'); if (!m) return null;
      const dd = Math.hypot(m.x - OD.x, m.z - OD.z), dt = Math.hypot(m.x - TD.x, m.z - TD.z);
      return dd / (dd + dt) < 0.55 ? { m, q } : null;
    }, 90000, 300);
    if (mid) {
      const look = async () => { const q = await st8(); const m = member(q, 'caravan', mid.m.n); if (m) await api('cam', m.x, m.z, 13, Math.atan2(OD.x - TD.x, OD.z - TD.z) + 1.1, 0.85); };
      await look(); await sleep(500); await look(); await sleep(150);
      await shot('d1_caravan_walk.png');
      const ms = tripOf(await st8(), 'caravan').members;
      log('  porters', JSON.stringify(ms));
      const ai = ms.filter((m) => m.ai && m.st === 'walk');
      if (ai.length >= 2) { const gap = Math.hypot(ai[0].x - ai[1].x, ai[0].z - ai[1].z); check(gap > 1.2, `짐꾼이 겹치지 않고 줄지어 걸음 (${gap.toFixed(1)}m)`); }
    } else check(false, '짐꾼이 가는 길에 안 보임');
    // 우리 짐꾼도 가는 길에
    const ourMid = await until(async () => { const q = await st8(); const t = tripOf(q, 'caravan'); if (!t) return null; const m = t.members.find((x) => !x.ai && x.st === 'walk'); return m ? { m } : null; }, 8000, 300);
    if (ourMid) {
      const look = async () => { const q = await st8(); const m = member(q, 'caravan', ourMid.m.n); if (m) await api('cam', m.x, m.z, 12, Math.atan2(TD.x - OD.x, TD.z - OD.z) - 1.2, 0.85); };
      await look(); await sleep(400); await look(); await sleep(150); await shot('d2_our_porter.png');
    }
    // 마을회관 앞 도착
    const arr = await until(async () => { const q = await st8(); const t = tripOf(q, 'caravan'); return t && t.members.some((x) => x.ai && x.st === 'greet') ? q : null; }, 90000, 200);
    if (arr) { const m = tripOf(arr, 'caravan').members.find((x) => x.ai && x.st === 'greet'); await camAway(m, h, 14, 0.8); await sleep(400); await shot('d3_caravan_arrive.png'); }
    check(!!arr, '짐꾼이 마을회관 앞에 도착');
    const got = await until(async () => { const st = await api('stats'); const d = val(st, o.give.type) - val(after, o.give.type); return d >= o.give.n ? d : null; }, 60000, 500);
    check(got >= o.give.n, `창고에 ${o.give.type} +${got} (제안 ${o.give.n})`);
    await sleep(2200); await shot('d3b_greet.png');
    const end = await until(async () => { const q = await st8(); return !tripOf(q, 'caravan') ? q : null; }, 150000, 1000);
    check(!!end, '짐꾼들이 다 돌아감');
    if (end) {
      check(end.ctrl.length === 0 && end.stray.length === 0, `맡은 사람 정리됨 ctrl=${end.ctrl} stray=${end.stray}`);
      check(end.leaving.length === 0, `우리 주민 leaving 없음 ${end.leaving}`);
      check(o.want.type === 'coins' || (end.theirs[o.want.type] || 0) >= o.want.n, `서리골 창고에 ${o.want.type} 들어감 ${JSON.stringify(end.theirs)}`);
    }
    log('  news', JSON.stringify((await api('news')).slice(0, 5)));
  }

  // ------------------------------------------------------------ 2. 서리골 사람들이 놀러 옴
  if (want('visit')) {
    log('\n== 마실 (서리골 → 우리)');
    await api('skipTo', 0.3); await api('speed', 2);
    const names = await api('forceVisit', 'theirs');
    log('visitors', names);
    check(Array.isArray(names) && names.length >= 2, '손님 2명 이상');
    // 같이 걸어오는 모습
    const walking = await until(async () => { const q = await st8(); const t = tripOf(q, 'visit'); if (!t) return null; const w = t.members.filter((m) => m.st === 'walk'); if (w.length < t.members.length) return null; const m = w[w.length - 1]; return Math.hypot(m.x - OD.x, m.z - OD.z) < 32 ? m : null; }, 90000, 300);
    if (walking) {
      const look = async () => { const q = await st8(); const t = tripOf(q, 'visit'); if (!t) return; const ms = t.members; const cx = ms.reduce((a, m) => a + m.x, 0) / ms.length, cz = ms.reduce((a, m) => a + m.z, 0) / ms.length; await api('cam', cx, cz, 14, Math.atan2(OD.x - TD.x, OD.z - TD.z) + 1.3, 0.85); };
      await look(); await sleep(400); await look(); await sleep(150); await shot('d4a_visit_walk.png');
    }
    const arrived = await until(async () => { const q = await st8(); const t = tripOf(q, 'visit'); return t && t.members.filter((m) => m.st === 'stay').length >= Math.min(2, t.members.length) ? q : null; }, 120000, 500);
    check(!!arrived, '손님 도착');
    await api('cutaway', 'tavern', true);
    let sawSlot = false, sawChat = false;
    const t0 = Date.now();
    while (Date.now() - t0 < 70000) {
      const q = await st8(); const t = tripOf(q, 'visit'); if (!t) break;
      const inTav = t.members.find((m) => m.slot && m.inside === 'tavern');
      const chat = t.members.find((m) => m.chat && !m.slot && !m.inside);
      if (inTav && !sawSlot) { sawSlot = true; await camAt(inTav, 9, 0.7, 0.85); await sleep(500); await shot('d4_visit_tavern.png'); }
      if (chat && !sawChat) { sawChat = true; await sleep(900); const q2 = await st8(); const c2 = member(q2, 'visit', chat.n) || chat; await camAt(c2, 10, -0.5, 0.85); await sleep(400); await shot('d5_visit_chat.png'); }
      if (sawSlot && sawChat) break;
      await sleep(350);
    }
    check(sawSlot, '손님이 선술집 자리에 앉음');
    check(sawChat, '손님이 우리 주민과 수다');
    await api('cutaway', 'tavern', false);
    const bye = await until(async () => { const q = await st8(); const t = tripOf(q, 'visit'); return !t || t.members.some((m) => m.st === 'home') ? q : null; }, 150000, 600);
    check(!!bye, '손님들이 인사하고 돌아감');
    const end = await until(async () => { const q = await st8(); return !tripOf(q, 'visit') ? q : null; }, 150000, 1000);
    check(!!end, '손님들이 집에 도착');
    if (end) check(end.stray.length === 0, `맡은 사람 정리됨 stray=${end.stray}`);
    // 놀러 온 사람끼리 사랑은 싹트지 않아요 (마을이 달라서)
    const cross = await page.evaluate(() => window.__SM.game.people.list.filter((p) => !p.dead && p.partner && !!p.partner.ai !== !!p.ai).length);
    check(cross === 0, '다른 마을 사람과 사귀는 일 없음');
  }

  // ------------------------------------------------------------ 3. 우리 주민이 서리골에 놀러 감
  if (want('outing')) {
    log('\n== 마실 (우리 → 서리골)');
    await api('skipTo', 0.3); await api('speed', 2);
    const names = await api('forceVisit', 'ours');
    log('outing', names);
    check(Array.isArray(names) && names.length >= 1, '우리 주민 1명 이상 출발');
    const arrived = await until(async () => { const q = await st8(); const t = tripOf(q, 'outing'); return t && t.members.some((m) => m.st === 'stay') ? q : null; }, 120000, 500);
    if (arrived) {
      await sleep(2500);
      const q = await st8(); const t = tripOf(q, 'outing');
      const mm = t ? (t.members.find((m) => m.chat) || t.members[0]) : null;
      if (mm) { const look = async () => { const q2 = await st8(); const m2 = member(q2, 'outing', mm.n) || mm; await camAway(m2, TD, 15, 0.75); }; await look(); await sleep(400); await look(); await sleep(150); await shot('d6_outing.png'); }
    }
    check(!!arrived, '서리골에 도착');
    const end = await until(async () => { const q = await st8(); return !tripOf(q, 'outing') ? q : null; }, 150000, 1000);
    check(!!end, '집에 돌아옴');
    if (end) check(end.leaving.length === 0 && end.stray.length === 0, `정리됨 leaving=${end.leaving} stray=${end.stray}`);
  }

  // ------------------------------------------------------------ 3b. 창에서 마실 보내기: 늦으면 안 되고, 마지막 시각에 보내도 밤 전에 돌아와요
  if (want('late')) {
    log('\n== 늦은 마실 (창에서 보내기)');
    await closeModal();
    await api('speed', 0);
    const lt = (await st8()).outingLatest;
    await api('skipTo', Math.min(0.6, lt + 0.01));
    const tooLate = await page.evaluate(() => window.__SM.game.diplo.panelAct('outing'));
    check(tooLate && tooLate.err, `마지막 시각(${lt}) 뒤에는 못 보내요 (${tooLate && tooLate.msg})`);
    await api('skipTo', lt - 0.004);
    // 일하는 주민 몇 명을 쉬게 해서 함께 가게
    const r = await page.evaluate(() => { const g = window.__SM.game, pp = g.people; let n = 0; for (const p of pp.list) if (!p.ai && !p.dead && p.stage === 'adult' && p.job && p.job.kind === 'worker' && n < 3) { pp.loseJob(p); n++; } return g.diplo.panelAct('outing'); });
    check(r && !r.err, `마지막 시각 바로 전에 보내기 (${r && r.msg})`);
    if (r && !r.err) {
      await api('speed', 3);
      const end = await until(async () => { const q = await st8(); return !tripOf(q, 'outing') ? q : null; }, 200000, 300);
      const frac = end ? end.T - Math.floor(end.T) : 1;
      check(!!end && frac < 0.76 && end.phase !== 'night', `밤이 되기 전에 집에 돌아옴 (하루 ${frac.toFixed(3)}, ${end && end.phase})`);
      if (end) check(end.leaving.length === 0 && end.stray.length === 0, `정리됨 leaving=${end.leaving} stray=${end.stray}`);
    }
  }

  // ------------------------------------------------------------ 4. 두 마을 잔치
  if (want('fest')) {
    log('\n== 잔치');
    await api('skipTo', 0.2); await api('speed', 2);
    await api('friendship', 65);
    const f0 = await api('friendship');
    const r = await api('forceInvite');
    log('invite', JSON.stringify(r));
    check(r && r.at, '잔치 시작');
    if (r && r.at) {
      const full = await until(async () => { const q = await st8(); return q.fest && q.fest.arrived >= Math.max(3, (r.ours.length + r.ais.length) - 2) ? q : null; }, 120000, 500);
      check(!!full, '양쪽 주민이 들판에 모임');
      await camAt(r.at, 15, 0.8, 0.7); await sleep(2500); await shot('d7_fest.png');
      await camAt(r.at, 10, -0.9, 0.5); await sleep(1800); await shot('d7b_fest_close.png');
      const done = await until(async () => { const q = await st8(); return !q.fest ? q : null; }, 150000, 1000);
      check(!!done, '잔치 끝나고 모두 돌아감');
      if (done) {
        check(done.friend >= f0 + 6, `우호도 +6 → ${done.friend}`);
        const econ = await api('econ'); check(econ.buffs.includes('이웃 잔치의 여운'), '마을 기분 ↑ (이웃 잔치의 여운)');
        const decor = await page.evaluate(() => window.__SM.game.diplo.fest);
        check(!decor, '잔치 장식 치움');
        check(done.stray.length === 0 && done.leaving.length === 0, `정리됨 stray=${done.stray} leaving=${done.leaving}`);
      }
    }
  }

  // ------------------------------------------------------------ 5. 서리골 창 (교환·선물)
  if (want('panel')) {
    log('\n== 서리골 창');
    await api('skipTo', 0.15); await api('speed', 1);
    await api('friendship', 45);
    await api('forceTrade');
    // 이주민 팝업이 떠 있을 때 서리골 버튼을 눌러도 팝업을 덮지 않아요 (덮으면 이주민이 다시 안 와요)
    await page.evaluate(() => window.__SM.game.people.makeOffer());
    await sleep(300);
    await page.evaluate(() => { const b = [...document.querySelectorAll('.sysb')].find((x) => x.textContent.includes('서리골')); b.click(); });
    await sleep(400);
    const imm = await page.evaluate(() => { const m = window.__SM.game.hud.modalEl; return { vis: m.style.display !== 'none', diplo: !!m.querySelector('[data-diplo]'), y: !!m.querySelector('button[data-y="0"]'), offer: !!window.__SM.game.people.offer }; });
    check(imm.vis && !imm.diplo && imm.y && imm.offer, `이주민 팝업 위에 서리골 창이 안 덮임 ${JSON.stringify(imm)}`);
    await shot('d8a_immigrant_kept.png');
    await page.click('.modal button[data-y="0"]').catch((e) => log('immigrant answer', e.message));
    await sleep(300);
    check(!(await page.evaluate(() => !!window.__SM.game.people.offer)), '이주민 팝업에 답할 수 있음');
    // 위쪽 버튼을 눌러서 열기
    await page.evaluate(() => { const b = [...document.querySelectorAll('.sysb')].find((x) => x.textContent.includes('서리골')); b.click(); });
    await sleep(600);
    await shot('d8_panel.png');
    const btnTxt = await page.evaluate(() => [...document.querySelectorAll('.modal button[data-dp]')].map((b) => b.textContent));
    log('  buttons', JSON.stringify(btnTxt));
    check(btnTxt.some((t) => t.includes('받아들이기')) && btnTxt.filter((t) => t === '바꾸기').length === 3, '창: 제안 + 늘 하는 교환 3가지');
    // 창의 버튼으로 받아들이기
    const before = await api('friendship');
    await page.click('.modal button[data-dp="accept"]').catch((e) => log('click fail', e.message));
    await sleep(400);
    check((await api('friendship')) === before + 5 && (await st8()).offer === null, '창에서 받아들이기 (우호도 +5)');
    const f1 = await api('friendship');
    await page.click('.modal button[data-dp="deal"][data-i="0"]').catch((e) => log('deal click', e.message));
    await sleep(300);
    const f2 = await api('friendship');
    check(f2 === f1 + 2, `우리가 먼저 교환 → 우호도 +2 (${f1} → ${f2})`);
    await page.click('.modal button[data-dp="gift"][data-i="1"]').catch((e) => log('gift click', e.message));
    await sleep(300);
    const f3 = await api('friendship');
    check(f3 > f2, `코인 선물 → 우호도 ${f2} → ${f3}`);
    // 선물은 하루 두 번까지: 세 번째는 안 돼요 (우호도를 한꺼번에 살 수 없게)
    await api('coins', 500);
    let g2 = null;
    for (let k = 0; k < 15; k++) { g2 = await api('diploGift', 'coins'); if (!g2.err || !g2.msg.includes('들고 갈')) break; await sleep(1000); }   // 짐꾼이 다 나갔으면 조금 기다려요
    const g3 = await api('diploGift', 'coins');
    const f4 = await api('friendship');
    check(!g2.err && g3.err && f4 === f3 + 3, `선물 하루 두 번까지 (두 번째: ${g2.msg} / 세 번째: ${g3.msg}, 우호도 ${f3} → ${f4})`);
    await sleep(500);
    const giftDis = await page.evaluate(() => [...document.querySelectorAll('.modal button[data-dp="gift"]')].every((b) => b.disabled));
    check(giftDis, '선물 단추가 꺼짐 (오늘 남은 횟수 0)');
    // 들고 갈 주민이 없으면 선물을 못 보내요 (아무도 안 들고 가는데 바로 도착하지 않게)
    const noOne = await page.evaluate(() => { const d = window.__SM.game.diplo, f = d.freeOurs, n = d.giftsToday; d.freeOurs = () => []; d.giftsToday = 0; const r = d.gift('coins'); d.freeOurs = f; d.giftsToday = n; return r; });
    check(noOne.err, `들고 갈 주민이 없으면 선물 안 보냄 (${noOne.msg})`);
    const msg = await page.evaluate(() => { const m = document.querySelector('.modal [data-msg]'); return m ? m.textContent : null; });
    check(!!msg, `창 안에 결과 글 (${msg})`);
    await page.evaluate(() => { const sc = document.querySelector('.modal [data-scroll]'); if (sc) sc.scrollTop = 0; });
    await sleep(200);
    await shot('d8b_panel_after.png');
    // 휴대폰 크기
    await page.setViewportSize({ width: 390, height: 844 }); await sleep(600);
    await shot('d8c_panel_phone.png');
    const fit = await page.evaluate(() => { const r = document.querySelector('.modal').getBoundingClientRect(); return { l: Math.round(r.left), r: Math.round(r.right), w: innerWidth, sw: document.documentElement.scrollWidth }; });
    check(fit.l >= 0 && fit.r <= fit.w + 1 && fit.sw <= fit.w + 1, `휴대폰 화면 안에 창이 들어감 ${JSON.stringify(fit)}`);
    await page.setViewportSize({ width: 1280, height: 720 }); await sleep(300);
    await page.click('.modal button[data-x]').catch(() => closeModal());
    log('  log', JSON.stringify((await st8()).log.slice(0, 5)));
    await api('speed', 3);
    const end = await until(async () => { const q = await st8(); return !tripOf(q, 'caravan') ? q : null; }, 150000, 1000);
    check(!!end, '짐꾼(교환·선물) 모두 끝');
  }

  // ------------------------------------------------------------ 6. 이사
  if (want('move')) {
    log('\n== 이사');
    await api('skipTo', 0.2); await api('speed', 1);
    await api('friendship', 85);
    const nm = await api('forceMoveAsk');
    log('move ask', nm);
    await sleep(500); await shot('d9_move_modal.png');
    const pop0 = (await api('stats')).people;
    const r = await page.evaluate(() => { const m = window.__SM.game.hud.modalEl; const y = m.querySelector('button[data-y="1"]'); if (!y) return null; y.click(); return true; });
    check(r === true, '이사 팝업에서 받기 누름');
    await api('speed', 3);
    const done = await until(async () => { const q = await st8(); return !tripOf(q, 'move') ? q : null; }, 120000, 1000);
    const who = await page.evaluate((n) => { const p = window.__SM.game.people.list.find((x) => x.name === n && !x.dead); return p ? { ai: !!p.ai, home: p.home ? p.home.type + (p.home.ai ? ':ai' : '') : null, leaving: !!p.leaving } : null; }, nm);
    log('  moved', JSON.stringify(who));
    check(done && who && !who.ai && !who.leaving, '서리골 주민이 우리 주민이 됨');
    check((await api('stats')).people === pop0, '사람 수는 그대로 (서리골 → 우리)');
  }

  // ------------------------------------------------------------ 7. 봉화: 서리골이 먼저 밝히면 선물, 우리가 밝히면 축하하러 와요
  if (want('beacon')) {
    log('\n== 봉화');
    await api('skipTo', 0.15); await api('speed', 3);
    const c0 = (await api('stats')).coins;
    await page.evaluate(() => window.__SM.game.rival.light());
    const g = await until(async () => { const q = await st8(); const t = tripOf(q, 'caravan'); return t && t.why === 'gift' ? q : null; }, 10000, 300);
    check(!!g, '서리골이 먼저 밝힘 → 봄맞이 선물 짐꾼 출발');
    const arr = await until(async () => { const q = await st8(); const t = tripOf(q, 'caravan'); return t && t.members.some((x) => x.ai && x.st === 'greet') ? q : null; }, 120000, 300);
    if (arr) { const m = tripOf(arr, 'caravan').members.find((x) => x.ai && x.st === 'greet'); await camAway(m, h, 14, 0.8); await sleep(300); await shot('d10_gift.png'); }
    const end = await until(async () => { const q = await st8(); return !tripOf(q, 'caravan') ? q : null; }, 150000, 1000);
    const c1 = (await api('stats')).coins;
    check(c1 - c0 >= 25, `선물 코인 +${c1 - c0}`);
    log('  news', JSON.stringify((await api('news')).slice(0, 4)));
    if (end) check(end.stray.length === 0, '정리됨');
    // 우리 봉화 → 축하 방문 (서리골이 이미 밝혔으니 여기서는 축하 방문을 바로 불러 봐요)
    await api('skipTo', 0.15);
    const bp = await page.evaluate(async () => {
      const g = window.__SM.game, w = g.world, h = w.hall;
      const sp = window.__SM.api.findSpot('beacon', h.x + 4, h.z - 14, 0);
      if (!sp) return 'no spot';
      const b = await w.place('beacon', sp[0], sp[1], 0, { instant: true });
      return b ? [b.x, b.z] : null;
    });
    log('  our beacon', JSON.stringify(bp));
    if (Array.isArray(bp)) {
      await sleep(1500);
      await api('skipTo', 0.15);
      const names = await api('forceCheer');
      log('  cheer', JSON.stringify(names));
      const arrived = await until(async () => { const q = await st8(); const t = tripOf(q, 'cheer'); return t && t.members.some((m) => m.st === 'stay') ? q : null; }, 120000, 500);
      check(!!arrived, '서리골 사람들이 봉화 축하하러 옴');
      if (arrived) { await camAt({ x: bp[0], z: bp[1] }, 18, 0.5, 0.6); await sleep(1800); await shot('d10b_cheer.png'); }
      const ce = await until(async () => { const q = await st8(); return !tripOf(q, 'cheer') ? q : null; }, 120000, 1000);
      check(!!ce && ce.stray.length === 0, '축하 방문 끝나고 정리됨');
    }
  }

  // ------------------------------------------------------------ 8. 저장했다 불러오기 (상태가 이어져요)
  if (want('save')) {
    log('\n== 저장·불러오기 자료');
    const r = await page.evaluate(() => {
      const d = window.__SM.game.diplo;
      const before = { f: Math.round(d.friend), th: JSON.stringify(d.theirs), c: d.theirCoins };
      const data = JSON.parse(JSON.stringify(d.saveData()));
      d.friend = 3; d.theirs = {}; d.theirCoins = 0;
      d.loadData(data);
      return { before, after: { f: Math.round(d.friend), th: JSON.stringify(d.theirs), c: d.theirCoins }, size: JSON.stringify(data).length };
    });
    check(r.before.f === r.after.f && r.before.th === r.after.th && r.before.c === r.after.c, `저장 자료로 되살림 (${r.size}바이트)`);
    // 진짜 저장 → 새로고침 → 이어하기: 우호도·제안·길 위의 짐이 이어져요
    await api('skipTo', 0.15); await api('speed', 2);
    await api('friendship', 70);
    await api('forceTrade');
    await api('acceptTrade');
    await until(async () => { const q = await st8(); const t = tripOf(q, 'caravan'); return t && t.members.some((m) => m.ai && m.st === 'walk') ? q : null; }, 60000, 300);
    await api('forceTrade');
    const pre = await page.evaluate(() => { const g = window.__SM.game, d = g.diplo; return { f: Math.round(d.friend), offer: d.offer && d.offer.give.type + d.offer.give.n, owed: d.saveData().owed, stock: Object.assign({}, g.world.stock), coins: g.econ.coins }; });
    const sv = await api('save');
    check(sv && sv.ok, `저장했어요 (${sv && sv.size}바이트)`);
    await api('load');
    await sleep(1500);
    await page.waitForFunction(() => window.__SM && window.__SM.api && window.__SM.game.diplo && window.__SM.game.rival && window.__SM.game.rival.hall, null, { timeout: 120000 });
    await sleep(1500);
    const post = await page.evaluate(() => { const g = window.__SM.game, d = g.diplo; return { f: Math.round(d.friend), offer: d.offer && d.offer.give.type + d.offer.give.n, stock: Object.assign({}, g.world.stock), coins: g.econ.coins, trips: d.trips.length, btn: [...document.querySelectorAll('.sysb')].some((b) => b.textContent.includes('서리골')) }; });
    log('  저장 전', JSON.stringify(pre)); log('  불러온 뒤', JSON.stringify(post));
    check(post.f === pre.f && post.offer === pre.offer && post.btn, `불러온 뒤 우호도 ${post.f}, 제안 ${post.offer}, 서리골 버튼 있음`);
    const owedOk = pre.owed.us.every((l) => (l.type === 'coins' ? post.coins - pre.coins : (post.stock[l.type] || 0) - (pre.stock[l.type] || 0)) >= pre.owed.us.filter((x) => x.type === l.type).reduce((a, x) => a + x.n, 0) - 1);
    check(pre.owed.us.length > 0 && owedOk, `길 위에 있던 짐은 불러올 때 창고로 ${JSON.stringify(pre.owed.us)}`);
    await closeModal();
  }

  // ------------------------------------------------------------ 9. 며칠 동안 저절로 (3배속)
  if (want('days')) {
    log(`\n== ${DAYS}일 동안 저절로 (3배속)`);
    await api('friendship', 45);
    await api('speed', 3);
    const s1 = await st8();
    const endT = s1.T + DAYS;
    let offers = 0, accepted = 0, nightChecks = 0, nightBad = 0, lastDay = 0, maxTrips = 0, kinds = new Set(), shots = 0, lastOffer = null;
    while (true) {
      const q = await st8();
      if (q.T >= endT) break;
      for (const t of q.trips) kinds.add(t.kind);
      maxTrips = Math.max(maxTrips, q.trips.length);
      if (q.offer && q.offer !== lastOffer) {
        lastOffer = q.offer; offers++;
        const r = await api(offers % 3 === 0 ? 'declineTrade' : 'acceptTrade');
        if (!r.err && offers % 3 !== 0) accepted++;
        log(`  T=${q.T} 제안 ${q.offer} → ${offers % 3 === 0 ? '거절' : '받기'} ${r.msg}`);
        if (r.err) await api('declineTrade');
      }
      if (await page.evaluate(() => { const m = window.__SM.game.hud.modalEl; return m.style.display !== 'none'; })) {
        const txt = await page.evaluate(() => window.__SM.game.hud.modalEl.innerText.slice(0, 60));
        log('  팝업:', txt.replace(/\n/g, ' '));
        if (shots < 1 && txt.includes('잔치')) { shots++; await shot('d11_invite_modal.png'); }
        if (!(await api('offer', true))) await page.evaluate(() => { const m = window.__SM.game.hud.modalEl; const y = m.querySelector('button[data-y="1"]'); if (y) y.click(); else m.style.display = 'none'; });
      }
      const frac = q.T - Math.floor(q.T);
      if (frac > 0.9 && frac < 0.98 && Math.floor(q.T) !== lastDay) {
        lastDay = Math.floor(q.T); nightChecks++;
        // 밤: 우리가 맡은 사람 없음(서리골 사람은 people.aiThink 가 다시 맡아 집에 가서 자요), 마실·나들이 끝, 우리 마을에 남은 서리골 사람 없음
        //  (몇 명이 아직 걷고 있는 건 원래 게임도 그래요: 서리골이 넓어서 저녁 산책 끝에 늦게 자러 가요. 기능을 끈 채로 돌려 봐도 같음)
        //  우리 주민은 모두 우리 마을에서 자요 (서리골 집을 받아 서리골까지 자러 가지 않게)
        const ok = q.ai.inOurs === 0 && q.oursAway.length === 0 && q.cross.homes === 0 && q.stray.length === 0 && q.ctrl.length === 0 && !q.trips.some((t) => t.kind === 'visit' || t.kind === 'outing');
        if (!ok) nightBad++;
        log(`  밤 점검 ${lastDay}일: 서리골 ${q.ai.asleep}/${q.ai.total}명 잠, ${q.ai.bedward}명 자러 가는 중, 우리 마을에 ${q.ai.inOurs}명 · 서리골 쪽 우리 주민 ${q.oursAway} · 맡은 사람 ${q.ctrl.length} · 정리 안 된 사람 ${q.stray.length} · 진행 중 ${q.trips.map((t) => t.kind)}`);
        if (nightChecks === 1) { await camAt(TD, 30, 0.6, 0.9); await sleep(400); await shot('d12_night_rival.png'); }
      }
      const vt = q.trips.find((t) => (t.kind === 'visit' || t.kind === 'outing') && t.members.some((m) => m.st === 'stay'));
      if (vt && shots < 3) {
        const m = vt.members.find((x) => x.st === 'stay' && !x.inside) || vt.members.find((x) => x.st === 'stay');
        shots++; await camAt(m, 17, 0.6, 1.15); await sleep(400); await shot(`d13_natural_${vt.kind}_${shots}.png`);
      }
      await sleep(1200);
    }
    const q = await st8();
    log(`  제안 ${offers}번 (받기 ${accepted}), 밤 점검 ${nightChecks}번 (문제 ${nightBad}), 본 나들이 ${[...kinds]}, 동시 최대 ${maxTrips}, 우호도 ${q.friend}`);
    check(offers >= 1, `며칠 동안 서리골 제안 ${offers}번`);
    check(nightChecks >= 2 && nightBad === 0, `밤마다 손님이 모두 돌아가고 서리골 주민은 자기 마을에서 잠 (${nightChecks - nightBad}/${nightChecks})`);
    check(q.stray.length === 0, `정리 안 된 사람 없음 (${q.stray})`);
    check(q.cross.homes === 0 && q.cross.romance === 0 && q.cross.partners === 0, `두 마을이 섞이지 않음 (집 ${q.cross.homes}, 사랑 ${q.cross.romance}, 짝 ${q.cross.partners})`);
    log('  log', JSON.stringify(q.log));
  }
  const fin = await st8();
  log('\nfinal', JSON.stringify({ friend: fin.friend, trips: fin.trips.map((t) => t.kind), ctrl: fin.ctrl, stray: fin.stray, leaving: fin.leaving, ai: fin.ai, theirs: fin.theirs }));
  log('stats', JSON.stringify(await api('stats')));
} catch (e) { errs.push('test: ' + (e.stack || e)); try { await shot('fail.png'); } catch (e2) { /* */ } }
log('warnings', warns.length ? '\n' + warns.slice(0, 10).join('\n') : 0);
log('errors', errs.length ? '\n' + errs.slice(0, 20).join('\n') : 0);
log('checks failed', fails.length ? '\n - ' + fails.join('\n - ') : 0);
await b.close(); await srv.close();
process.exit(errs.length || fails.length ? 1 : 0);
