// 저장하기·불러오기 시험
//   cd game && PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers node tools/test/save_test.mjs <출력폴더> [--soft] [--quick]
//   (기본: 창 없이 진짜 그래픽카드를 쓰는 크롬 · --soft: 그래픽카드 없이 느린 소프트웨어 그리기)
//  1) 풍성한 마을(회관·집·업그레이드·돌길·나무꾼·제재소·밭·닭장·과수원·선술집·망루·장식·부부와 아기·코인·이웃 마을)을 만들고
//     잠깐 돌린 뒤 저장 → 새로고침 → "이어하기" 눌러 불러오기 → 항목별로 비교 → 3배속 60초 이상 돌려 일·공사가 이어지는지
//  2) 공사 중 + 밤에 저장 → 불러오기 → 밤에는 자고, 아침에 자동 저장되고 다시 일하는지
//  3) "새로 시작" (한 번 더 묻기, 돌아가기 포함)  4) 망가진 저장  5) 저장 공간이 막힌 브라우저
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch, launchGpu } from './pw.mjs';

const OUT = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : '../.cache/shots/save'; fs.mkdirSync(OUT, { recursive: true });
const soft = process.argv.includes('--soft');
const quick = process.argv.includes('--quick');
const KEY = 'spring-march-save-v1';
const srv = await start(0);
// 대표님 화면에 창을 띄우지 않는다 (headless). 기본은 진짜 그래픽카드(D3D11)
const browser = soft ? await launch() : await launchGpu();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);
const results = [];
const check = (name, ok, info = '') => { results.push({ name, ok: !!ok, info }); log(`${ok ? 'PASS' : 'FAIL'}  ${name}${info ? '  — ' + info : ''}`); };
const errs = [], warns = [];
let page, ctx, richSave = null;

function watch(p, tag) {
  p.on('pageerror', (e) => errs.push(`[${tag}] pageerror: ${e.stack || e}`));
  p.on('console', (m) => {
    const t = m.text();
    // 소리 장치 오류(창 없는 크롬·소리 장치 없음)는 게임 잘못이 아니라 넘어간다
    if (m.type() === 'error' && !/Failed to load resource|404|AudioContext encountered an error/.test(t)) errs.push(`[${tag}] console.error: ${t}`);
    else if (m.type() === 'warning' && !/GPU stall|building missing/.test(t)) warns.push(`[${tag}] ${t}`);
  });
}
const api = (f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);
const shot = async (n) => { await page.screenshot({ path: path.join(OUT, n) }); log('shot', n); };
const waitGame = async () => { await page.waitForFunction(() => window.__SM && window.__SM.api && window.__SM.game, null, { timeout: 180000, polling: 'raf' }); };
const evalG = (fn, arg) => page.evaluate(fn, arg);

// 시험이 직접 읽는 자세한 상태 (저장 코드와 상관없이 살아 있는 게임 객체에서)
const SNAP = () => {
  const g = window.__SM.game, w = g.world, pp = g.people, c = g.clock;
  const r = (v, k = 2) => Math.round((+v || 0) * 10 ** k) / 10 ** k;
  const id = (o) => (o ? o.id : null);
  const people = {};
  for (const p of pp.list) {
    if (p.dead) continue;
    people[p.id] = {
      name: p.name, gender: p.gender, stage: p.stage, age: p.age, trait: p.trait, look: p.look, ai: !!p.ai, special: !!p.special,
      home: id(p.home), spouse: id(p.spouse), partner: id(p.partner), parents: p.parents.filter((q) => !q.dead).map(id).sort((a, b) => a - b),
      friends: [...p.friends].map(([k, v]) => [k, r(v)]).sort((a, b) => a[0] - b[0]), romance: [...p.romance].map(([k, v]) => [k, r(v)]).sort((a, b) => a[0] - b[0]),
      x: r(p.x), z: r(p.z), energy: r(p.energy, 3), mood: r(p.mood, 3), hungry: !!p.hungry, marriedDay: p.marriedDay ?? null, wp: !!p.weddingPlanned,
    };
  }
  const blds = {};
  for (const b of w.blds) {
    blds[b.id] = {
      type: b.type, name: b.name, x: r(b.x, 3), z: r(b.z, 3), rot: r(b.rot, 3), level: b.level, state: b.state, ai: !!b.ai, free: !!b.free,
      con: b.con ? { kind: b.con.kind, need: b.con.need, have: b.con.have, used: b.con.used, work: r(b.con.work, 1), workNeeded: b.con.workNeeded } : null,
      inputs: r(b.inputs, 1), out: b.out, working: !!b.working, pt: r(b.t, 2),
      plots: b.plots.length, plotStages: b.plots.reduce((s, p) => s + p.stage, 0),
      animals: b.animals ? b.animals.length : null, animalsReady: b.animals ? b.animals.filter((a) => a.ready).length : null,
      trees: b.trees ? b.trees.length : null, treesReady: b.trees ? b.trees.filter((t) => t.ready).length : null,
      pinned: !!b.pinned, cutaway: !!b.cutaway, lit: !!b.fire, flames: b.flames ? b.flames.length : 0,
    };
  }
  const roads = {};
  for (const e of w.roads.edges.values()) roads[e.id] = { type: e.type, a: e.a.id, b: e.b.id, len: r(e.len, 1) };
  const nature = {}, models = {};
  let rockAmt = 0, rockScale = 0;
  const mtx = new (Object.values(w.pools)[0].m.constructor)();   // THREE.Matrix4
  for (const o of w.nature.values()) {
    nature[o.type] = (nature[o.type] || 0) + 1;
    models[o.model] = (models[o.model] || 0) + 1;     // 계절 모습까지 같은지 (모델 이름별 개수)
    if (o.type === 'rock') {
      rockAmt += o.amount;
      // 캐다 만 바위의 실제 그려지는 크기 (인스턴스 행렬에서)
      const pl = w.pools[o.model], k = pl && pl.slot.get(o.id);
      if (k != null && pl.parts[0]) { pl.parts[0].im.getMatrixAt(k, mtx); const e = mtx.elements; rockScale += Math.hypot(e[0], e[1], e[2]) / (pl.parts[0].local.elements[0] ? Math.hypot(pl.parts[0].local.elements[0], pl.parts[0].local.elements[1], pl.parts[0].local.elements[2]) : 1); }
    }
  }
  rockScale = r(rockScale, 1);
  const dp = g.diplo;
  const diplo = dp ? { friend: r(dp.friend, 1), theirCoins: dp.theirCoins, intro: !!(dp.seen && dp.seen.intro), offer: !!dp.offer } : null;
  // 들고 가던 짐 (저장 때 창고로 돌아간다)
  const carried = {};
  const add = (t) => { if (t) carried[t] = (carried[t] || 0) + 1; };
  for (const p of pp.list) { const j = p.job; if (!j || p.dead) continue; if (j.kind === 'haul') { if (j.taken && !j.done) for (const o of [j.task, ...(j.extra || [])]) add(o.type); } else if (p.carry) add(p.carry); }
  const busyRoads = [...w.roads.edges.values()].filter((e) => e.busy).length;
  const st = {}; for (const [k, v] of Object.entries(w.stock)) st[k] = r(v);
  return {
    clock: { day: c.day, t: r(c.t, 4), phase: c.phase, season: c.season.name, year: c.year },
    stock: st, carried, busyRoads,
    coins: g.econ.coins, decos: Object.assign({}, g.econ.decos), buffs: g.econ.buffs.map((b) => b.name + '@' + b.until).sort(),
    merchant: g.econ.merchant ? g.econ.merchant.offers.map((o) => (o.key || o.name) + (o.sold ? ':sold' : '')) : null,
    merchantRy: g.econ.merchant && g.econ.merchant.sled ? r(g.econ.merchant.sled.rotation.y, 2) : null,
    won: !!g.won,
    rival: { beacon: r(g.rival.beacon, 3), lit: !!g.rival.lit, step: g.rival.step, home: g.rival.home ? [r(g.rival.home.x), r(g.rival.home.z)] : null, hall: id(g.rival.hall) },
    hall: id(w.hall), graves: pp.graves || 0, events: pp.eventQueue.map((e) => e.kind), offer: !!pp.offer,
    lake: w.lake ? [r(w.lake.cx), r(w.lake.cz), r(w.lake.rx), r(w.lake.rz)] : null, wagon: !!w.wagon,
    nodes: w.roads.nodes.size, roads, nature, models, rockAmt, rockScale, diplo, blds, people,
    wnid: w.nid, pnid: pp.nid, treeTarget: w.treeTarget,
  };
};

// 옛 객체를 가리키는 곳이 없는지 (사람·건물·일감)
const INTEGRITY = () => {
  const g = window.__SM.game, w = g.world, pp = g.people;
  const P = new Set(pp.list), B = new Set(w.blds), bad = [];
  for (const p of pp.list) {
    for (const f of ['home', 'inside', 'sleepAt']) if (p[f] && !B.has(p[f])) bad.push(`${p.name}.${f}`);
    for (const f of ['spouse', 'partner', 'chatting']) if (p[f] && !P.has(p[f])) bad.push(`${p.name}.${f}`);
    for (const q of p.parents) if (!q.dead && !P.has(q)) bad.push(`${p.name}.parent`);
    if (p.job && p.job.bld && !B.has(p.job.bld)) bad.push(`${p.name}.job.bld`);
    if (p.job && p.job.task && !w.tasks.includes(p.job.task) && !p.job.done && !p.job.taken) bad.push(`${p.name}.job.task`);
    if (p.slot && !B.has(p.slot.b)) bad.push(`${p.name}.slot`);
  }
  for (const b of w.blds) { for (const q of b.builders) if (!P.has(q)) bad.push(`${b.type}.builder`); if (b.worker && !P.has(b.worker)) bad.push(`${b.type}.worker`); }
  for (const t of w.tasks) if (!B.has(t.from) || !B.has(t.to)) bad.push('task');
  if (w.hall && !B.has(w.hall)) bad.push('hall');
  if (g.rival.hall && !B.has(g.rival.hall)) bad.push('rival.hall');
  for (const a of g.herds.list) if (!B.has(a.b)) bad.push('animal');
  return bad;
};

/** 깊은 비교: 다른 곳 목록 (tol: 키 이름별 허용 오차) */
function diff(a, b, tol, p = '', out = []) {
  if (out.length > 40) return out;
  const key = p.split('.').pop();
  if (typeof a === 'number' && typeof b === 'number') { const t = tol[key] ?? 1e-9; if (Math.abs(a - b) > t) out.push(`${p}: ${a} → ${b}`); return out; }
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') { if (a !== b && !(a == null && b == null)) out.push(`${p}: ${JSON.stringify(a)} → ${JSON.stringify(b)}`); return out; }
  const ks = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of ks) {
    if (!(k in a)) { out.push(`${p}.${k}: (없음) → ${JSON.stringify(b[k]).slice(0, 80)}`); continue; }
    if (!(k in b)) { out.push(`${p}.${k}: ${JSON.stringify(a[k]).slice(0, 80)} → (없음)`); continue; }
    diff(a[k], b[k], tol, `${p}.${k}`, out);
  }
  return out;
}

// 시험용: sessionStorage 't-freeze' 가 켜져 있으면 게임이 시작되는 바로 그 순간(첫 프레임 전)에 멈춘다 → 저장 때와 똑같은지 정확히 비교
const FREEZE = () => {
  try {
    if (sessionStorage.getItem('t-freeze') !== '1') return;
    let v;
    Object.defineProperty(window, '__SM', { configurable: true, get() { return v; }, set(x) { v = x; try { x.game.speed = 0; } catch (e) { /* */ } } });
  } catch (e) { /* */ }
};
const freeze = (on) => page.evaluate((o) => { if (o) sessionStorage.setItem('t-freeze', '1'); else sessionStorage.removeItem('t-freeze'); }, on);

async function newPage(tag, init, opts = {}) {
  if (ctx) await ctx.close().catch(() => {});
  ctx = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 720 }, locale: 'ko-KR' }, opts));
  if (init) await ctx.addInitScript(init);
  page = await ctx.newPage();
  watch(page, tag);
}
/** 같은 주소의 작은 파일에서 저장 공간 만지기 (게임이 돌지 않을 때) */
async function setStorage(kv) {
  const p = await ctx.newPage();
  await p.goto(srv.url + 'assets3d/buildings/index.json');
  await p.evaluate((o) => { for (const [k, v] of Object.entries(o)) { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } }, kv);
  await p.close();
}
async function waitModal() { await page.waitForSelector('.smsv', { state: 'visible', timeout: 180000 }); await sleep(500); }
const waitFor = (fn, arg, ms = 60000) => page.waitForFunction(fn, arg, { timeout: ms, polling: 250 });

try {
  // ============================================================ 1) 풍성한 마을
  await newPage('A', FREEZE);
  await setStorage({ [KEY]: null, [KEY + '-broken']: null });
  await page.goto(srv.url + 'index.html?debug=1');
  await waitGame();
  check('저장이 없으면 고르기 창 없이 바로 시작', !(await page.$('.smsv')) && (await evalG(() => window.__SM.game.mode)) === 'settle');
  const st = await api('start');
  await api('settle', st.x + 6, st.z - 6, 0.3);
  await api('finishAll');
  await waitFor(() => !!window.__SM.game.rival.hall, null, 30000);
  await sleep(1500);   // 영토(온기) 다시 계산될 때까지
  const h = await api('hall');
  await waitFor((hh) => !!window.__SM.api.findSpot('house', hh.x - 10, hh.z + 4, 0.4), h, 20000).catch(() => log('집 자리 기다리다 시간 초과'));
  const place = async (type, dx, dz, rot = 0, road = true) => {
    const sp = await api('findSpot', type, h.x + dx, h.z + dz, rot);
    if (!sp) { log('자리 없음', type, JSON.stringify(await evalG(([t, x, z, r]) => window.__SM.game.world.check(t, x, z, r), [type, h.x + dx, h.z + dz, rot]))); return null; }
    const r = await api('build', type, sp[0], sp[1], rot);
    if (typeof r === 'string') { log('못 지음', type, r); return null; }
    if (road) await api('road', [[r.door.x, r.door.z], [h.door.x, h.door.z]]);
    return { x: sp[0], z: sp[1], door: r.door };
  };
  for (const [t, dx, dz, rot] of [['house', -10, 4, 0.4], ['house', -10, -5, -0.3], ['house', -16, 0, 1.2], ['woodcutter', 14, 10, 0], ['sawmill', 9, 2, 0], ['farm', -2, 15, 0], ['coop', 14, -8, 0], ['orchard', -4, -16, 0], ['tavern', 6, 12, 0], ['watchtower', 0, -24, 0], ['quarry', -16, -14, 0.8]]) await place(t, dx, dz, rot);
  await api('finishAll');
  await sleep(800);
  // 집 하나 업그레이드 (끝까지)
  await evalG(() => { const w = window.__SM.game.world; const b = w.blds.find((x) => x.type === 'house' && x.state === 'active' && !x.ai); w.upgrade(b); });
  await api('finishAll');
  // 돌길·자갈길
  await api('road', [[h.x - 6, h.z + 9], [h.x + 4, h.z + 9], [h.x + 10, h.z + 6]], 'stone');
  await api('road', [[h.x - 8, h.z - 9], [h.x + 2, h.z - 10]], 'gravel');
  // 상인 → 장식 사서 놓기, 코인, 능력 효과
  await api('coins', 400);
  await api('merchant');
  const di = await evalG(() => window.__SM.game.econ.merchant.offers.findIndex((o) => o.kind === 'deco'));
  log('buy deco', di, await api('buy', di));
  const decoKey = await evalG(() => Object.keys(window.__SM.game.econ.decos).find((k) => window.__SM.game.econ.decos[k] > 0));
  const dsp = await api('findSpot', decoKey, h.x + 3, h.z + 8, 0);
  log('deco', decoKey, dsp && await api('placeDeco', decoKey, dsp[0], dsp[1]));
  await evalG(() => window.__SM.game.econ.apply({ kind: 'buff', name: '힘센 손', desc: '사흘 동안 일하는 속도 +25%', buff: { work: 0.25, days: 3 } }));
  // 실내 보기 고정
  await api('cutaway', 'tavern', true);
  // 부부 → 아기
  log('love', await api('forceLove'));
  await api('skipTo', 0.14); await api('speed', 3);
  await waitFor(() => window.__SM.game.people.list.some((p) => p.spouse && !p.ai && p.stage === 'adult' && p.marriedDay), null, 90000).catch(() => log('결혼식 기다리다 시간 초과'));
  log('birth q', await api('forceEvent', 'birth'));
  await waitFor(() => window.__SM.game.people.list.some((p) => p.stage === 'kid' && p.parents.length === 2), null, 90000).catch(() => log('아기 기다리다 시간 초과'));
  await api('skipTo', 0.2);
  await api('speed', 3);
  await sleep(quick ? 12000 : 22000);
  // 이주민 받기 → 스스로 짓는 오두막 (저장 때는 아직 공사 중)
  await evalG(() => window.__SM.game.people.makeOffer());
  log('immigrants', await api('offer', true));
  // 저장 바로 전에 짓기 시작한 것들: 우물·벤치·풍차(새로), 두 번째 집 업그레이드, 서리골 새 집
  await evalG(() => { const r = window.__SM.game.rival; r.beacon = 0.37; r.t = 118; });
  await place('well', 4, 6, 0, false); await place('bench', -4, 7, 0, false); await place('windmill', 8, 18, 0, false);
  await evalG(() => { const w = window.__SM.game.world; const b = w.blds.find((x) => x.type === 'house' && x.state === 'active' && !x.ai && x.level === 0 && !x.con); if (b) w.upgrade(b); });
  await sleep(3500);
  // ---- 저장 직전
  await api('speed', 0); await sleep(400);
  // 캐다 만 바위 몇 개 (줄어든 크기 그대로 돌아오는지), 서리골 우호도 (외교 상태도 이어지는지)
  await evalG(() => {
    const g = window.__SM.game, w = g.world;
    const rocks = [...w.nature.values()].filter((o) => o.type === 'rock' && o.amount >= 3).slice(0, 4);
    for (const o of rocks) { w.mineRock(o); w.mineRock(o); }
    if (g.diplo) { g.diplo.friend = 47; g.diplo.theirCoins = 123; }
  });
  await api('cam', h.x + 2, h.z + 2, 52, 0.75, 0.95); await sleep(1800);
  await shot('a1_before_save.png');
  const before = await evalG(SNAP);
  log('before:', JSON.stringify({ day: before.clock.day, t: before.clock.t, people: Object.keys(before.people).length, blds: Object.keys(before.blds).length, roads: Object.keys(before.roads).length, carried: before.carried, busyRoads: before.busyRoads, coins: before.coins }));
  const sv = await api('save');
  check('저장 성공', sv && sv.ok, `${sv && sv.size} 글자 (${Math.round((sv && sv.size || 0) / 1024)} KB)`);
  check('저장 크기가 작다 (1.5MB 미만)', sv && sv.size < 1.5e6);
  check('hasSave', await api('hasSave'));
  richSave = await evalG(() => localStorage.getItem('spring-march-save-v1'));
  const kidsB = Object.values(before.people).filter((p) => p.stage === 'kid' && p.parents.length === 2).length;
  const coupleB = Object.values(before.people).filter((p) => p.spouse && p.marriedDay && !p.ai).length;
  check('준비: 부부와 아기가 있다', kidsB >= 1 && coupleB >= 2, `아기 ${kidsB}, 결혼한 사람 ${coupleB}`);
  const bl = Object.values(before.blds);
  check('준비: 건물 종류가 다양하다', ['hall', 'house', 'woodcutter', 'sawmill', 'farm', 'coop', 'orchard', 'tavern', 'watchtower'].every((t) => bl.some((b) => b.type === t)) && bl.some((b) => b.ai) && bl.some((b) => b.type === 'house' && b.level >= 1) && bl.some((b) => b.con) && bl.some((b) => b.pinned),
    bl.map((b) => b.type + (b.ai ? '*' : '') + (b.con ? '(공사)' : '')).join(' '));
  check('준비: 돌길·밭·동물·장식', Object.values(before.roads).some((e) => e.type === 'stone') && bl.some((b) => b.plots > 0) && bl.some((b) => b.animals > 0) && bl.some((b) => b.type === decoKey));

  // ---- 새로고침 → 이어하기
  await freeze(true);
  await page.reload();
  await waitModal();
  await shot('a2_continue_modal.png');
  const label = await page.textContent('.smsv-go');
  check('이어하기 버튼 글', /이어하기 \(\d+년 (겨울|봄|여름|가을) \d+일 · 주민 \d+명\)/.test(label), label.trim());
  const popTxt = Number((label.match(/주민 (\d+)명/) || [])[1]);
  check('이어하기 버튼의 주민 수', popTxt === Object.values(before.people).filter((p) => !p.ai).length, `${popTxt}`);
  const vis = await page.evaluate(() => { const b = document.querySelector('.smsv-go').getBoundingClientRect(); const el = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2); return !!el && !!el.closest('.smsv'); });
  check('고르기 창이 맨 위에 보이고 눌린다', vis);
  await page.click('.smsv-go');
  await waitGame();
  await api('speed', 0);
  await freeze(false);
  const rep = await api('loadReport');
  log('loadReport', JSON.stringify(rep));
  check('불러온 직후: 일감·자리·건물 안 붙잡은 사람 없음', rep && rep.tasks === 0 && rep.stale === 0, JSON.stringify(rep));
  const offDoll = await evalG(() => window.__SM.game.people.list.filter((p) => !p.dead && (!p.doll.root.visible || Math.hypot(p.doll.root.position.x - p.x, p.doll.root.position.z - p.z) > 0.05)).map((p) => p.name));
  check('불러온 직후(멈춘 채로도): 주민 인형이 제자리에 보인다', offDoll.length === 0, offDoll.join(', '));
  await sleep(300);
  const dBtn = await evalG(() => [...document.querySelectorAll('button.sysb')].filter((b) => /서리골/.test(b.textContent)).map((b) => b.style.display !== 'none' && b.offsetParent !== null));
  check('불러온 직후(멈춘 채로도): 위쪽 서리골 버튼이 보인다', dBtn.length === 1 && dBtn[0], JSON.stringify(dBtn));
  const fh = await evalG(() => { const w = window.__SM.game.world, pp = window.__SM.game.people; return w.blds.filter((b) => b.free && b.con && b !== w.hall && !b.ai).map((b) => ({ builders: b.builders.length, adults: pp.list.filter((p) => p.home === b && p.stage === 'adult').length, jobs: pp.list.filter((p) => p.job && p.job.bld === b).length })); });
  check('이주민 오두막: 그 집 사람들이 다시 맡아 짓는다', fh.length >= 1 && fh.every((f) => f.builders === f.adults && f.adults > 0 && f.jobs === f.adults), JSON.stringify(fh));
  await api('cam', h.x + 2, h.z + 2, 52, 0.75, 0.95); await sleep(2500);
  await shot('a3_after_load.png');
  const after = await evalG(SNAP);
  // 창고 = 저장 때 창고 + 들고 가던 짐 (+ 깔던 길 재료)
  const expStock = Object.assign({}, before.stock);
  for (const [k, v] of Object.entries(before.carried)) expStock[k] = Math.round(((expStock[k] || 0) + v) * 100) / 100;
  const cmpB = Object.assign({}, before, { stock: expStock, carried: null, busyRoads: null, wnid: null, pnid: null });
  const cmpA = Object.assign({}, after, { carried: null, busyRoads: null, wnid: null, pnid: null });
  const tol = { x: 0.011, z: 0.011, rot: 0.0011, energy: 0.0011, mood: 0.0011, t: 0.0001, pt: 0.011, beacon: 0.0001, inputs: 0.051, work: 0.051, len: 0.051, rockScale: 0.3, friend: 0.11, merchantRy: 0.011 };
  const parts = ['clock', 'stock', 'coins', 'decos', 'buffs', 'merchant', 'merchantRy', 'won', 'rival', 'hall', 'graves', 'events', 'offer', 'lake', 'wagon', 'nodes', 'roads', 'nature', 'models', 'rockAmt', 'rockScale', 'diplo', 'blds', 'people', 'treeTarget'];
  for (const k of parts) {
    const d = diff(cmpB[k], cmpA[k], tol, k);
    check(`비교: ${k}`, d.length === 0, d.length ? d.slice(0, 8).join(' | ') : (typeof cmpB[k] === 'object' && cmpB[k] ? `${Object.keys(cmpB[k]).length}개 같음` : String(cmpB[k])));
  }
  check('번호(id) 이어 쓰기', after.wnid >= before.wnid && after.pnid >= before.pnid, `${before.wnid}/${before.pnid} → ${after.wnid}/${after.pnid}`);
  const bad1 = await evalG(INTEGRITY);
  check('옛 객체 참조 없음', bad1.length === 0, bad1.slice(0, 6).join(', '));

  // ---- 3배속 60초 넘게: 일 나누기·공사 진행
  const sites0 = Object.fromEntries(Object.entries(after.blds).filter(([, b]) => b.con && !b.ai).map(([k, b]) => [k, b.con.work]));
  log('공사 중:', JSON.stringify(sites0));
  await api('skipTo', Math.min(after.clock.t, 0.3));
  await api('speed', 3);
  const errN0 = errs.length;
  let maxJobs = {}, sawBuilder = false, sawWorker = false, sawHaul = false;
  const runS = quick ? 36 : 66;
  for (let k = 0; k < runS / 6; k++) {
    await sleep(6000);
    const s = await api('stats');
    for (const [j, n] of Object.entries(s.jobs)) maxJobs[j] = Math.max(maxJobs[j] || 0, n);
    if (s.jobs.builder) sawBuilder = true; if (s.jobs.worker) sawWorker = true; if (s.jobs.haul) sawHaul = true;
    if (k % 3 === 0) log(`  +${(k + 1) * 6}s`, JSON.stringify({ day: s.day, phase: s.phase, jobs: s.jobs, tasks: s.tasks, fps: s.fps }));
  }
  const after2 = await evalG(SNAP);
  const progressed = Object.entries(sites0).filter(([k, w0]) => { const b = after2.blds[k]; return !b || !b.con || b.con.work > w0 + 0.5 || b.state === 'active'; });
  check(`${runS}초 동안 오류 없음`, errs.length === errN0, errs.slice(errN0, errN0 + 3).join(' | '));
  check('불러온 뒤 일이 다시 나눠짐 (일꾼·나르기·공사)', sawWorker && sawHaul && sawBuilder, JSON.stringify(maxJobs));
  check('불러온 뒤 공사가 진행됨', progressed.length >= Math.min(2, Object.keys(sites0).length), `${progressed.length}/${Object.keys(sites0).length}곳`);
  check('불러온 뒤 마을 상태 정상', (await evalG(INTEGRITY)).length === 0);
  await api('speed', 0);
  await api('cam', h.x + 2, h.z + 2, 40, 0.75, 0.9); await sleep(1500);
  await shot('a4_after_run.png');

  // ============================================================ 2) 공사 중 + 밤에 저장
  const shopAt = await place('shop', 10, -2, 0, false);
  // 봉화: 우리 봉화를 먼저 밝히고(이김·축제), 서리골도 밝힌다 → 불꽃이 다시 켜지는지
  await api('coins', 0);
  const bk = await place('beacon', 4, -14, 0, false);
  log('beacon', !!bk, await api('beacon'));
  await sleep(500);
  await evalG(() => window.__SM.game.rival.light());
  await sleep(800);
  await api('skipTo', 0.79); await api('speed', 1);
  await sleep(5000);
  await api('speed', 0); await sleep(300);
  const nb = await evalG(SNAP);
  const shopB = Object.values(nb.blds).find((b) => b.type === 'shop');
  const sleepersB = await evalG(() => window.__SM.game.people.list.filter((p) => p.sleeping || p.hidden).length);
  log('night before:', nb.clock.phase, nb.clock.t, 'shop', JSON.stringify(shopB && shopB.con), 'sleeping/hidden', sleepersB);
  check('밤 저장', (await api('save')).ok && nb.clock.phase === 'night' && shopB && shopB.con);
  await freeze(true);
  await page.reload();
  await waitModal();
  await page.click('.smsv-go');
  await waitGame();
  await api('speed', 0);
  await freeze(false);
  await api('cam', shopAt ? shopAt.x : h.x, shopAt ? shopAt.z : h.z, 30, 0.75, 0.85); await sleep(2000);
  await shot('b1_night_after_load.png');
  const na = await evalG(SNAP);
  const shopA = Object.values(na.blds).find((b) => b.type === 'shop');
  check('밤: 시간·날짜 그대로', na.clock.phase === 'night' && na.clock.day === nb.clock.day && Math.abs(na.clock.t - nb.clock.t) < 0.0001, `${nb.clock.day}일 ${nb.clock.t} → ${na.clock.day}일 ${na.clock.t}`);
  check('밤: 공사 현장 그대로', shopA && shopA.state === 'site' && JSON.stringify(shopA.con) === JSON.stringify(shopB.con), JSON.stringify(shopA && shopA.con));
  check('밤: 주민·건물 수 그대로', Object.keys(na.people).length === Object.keys(nb.people).length && Object.keys(na.blds).length === Object.keys(nb.blds).length);
  const beac = (s) => Object.values(s.blds).filter((b) => b.type === 'beacon').map((b) => `${b.ai ? '서리골' : '우리'}:${b.state}:${b.lit ? '불' : '꺼짐'}:${b.flames}`).sort().join(' ');
  check('봉화·승리·축제 그대로', beac(na) === beac(nb) && /우리:active:불/.test(beac(na)) && /서리골:active:불/.test(beac(na)) && na.won === nb.won && na.rival.lit && JSON.stringify(na.events) === JSON.stringify(nb.events) && nb.events.includes('festival'),
    `${beac(na)} · won ${nb.won}→${na.won} · 행사 ${JSON.stringify(nb.events)}→${JSON.stringify(na.events)}`);
  const d2 = diff(Object.assign({}, nb, { stock: null, carried: null, wnid: null, pnid: null, clock: null }), Object.assign({}, na, { stock: null, carried: null, wnid: null, pnid: null, clock: null }), { x: 0.011, z: 0.011, rot: 0.0011, energy: 0.0011, mood: 0.0011, t: 0.0001, pt: 0.011, beacon: 0.0001, inputs: 0.051, work: 0.051, len: 0.051 });
  check('밤: 전체 비교', d2.length === 0, d2.slice(0, 8).join(' | '));
  await api('speed', 3);
  await sleep(12000);
  const sleepersA = await evalG(() => window.__SM.game.people.list.filter((p) => p.sleeping || p.hidden).length);
  check('밤: 불러온 뒤 집에 가서 잔다', sleepersA >= Math.min(5, sleepersB), `자는 사람 ${sleepersA} (저장 전 ${sleepersB})`);
  const autoN0 = await api('autoSaves');
  // 아침에 다른 알림(서리골 교환 제안 같은)이 뜨면 자동 저장 알림이 그 알림을 덮지 않는지: 알림 기록 + 아침마다 시험 알림 하나
  await evalG(() => {
    const g = window.__SM.game, h = g.hud, o = h.toast.bind(h);
    window.__toasts = []; h.toast = (m, e) => { window.__toasts.push([Math.round(performance.now()), m]); o(m, e); };
    g.saver.lastAutoToast = -1e9;   // 이번 아침엔 원래 자동 저장 알림을 띄울 차례
    window.__mornMsg = '🧪 아침 알림';
    g.clock.on((ev) => { if (ev === 'morning' && window.__mornMsg) { h.toast(window.__mornMsg); window.__mornMsg = null; } });
  });
  await api('skipTo', 0.995);
  await waitFor(() => window.__SM.game.clock.phase === 'day' && window.__SM.game.clock.t > 0.01, null, 30000);
  await sleep(1500);
  const autoN1 = await api('autoSaves');
  const toastTxt = await evalG(() => window.__SM.game.hud.toastEl.textContent);
  check('아침 자동 저장', autoN1 > autoN0, `${autoN0} → ${autoN1}, 알림 "${toastTxt}"`);
  const tl1 = await evalG(() => window.__toasts.map((t) => t[1]));
  const mi = tl1.indexOf('🧪 아침 알림');
  check('아침 자동 저장 알림이 다른 알림을 덮지 않는다', mi >= 0 && !tl1.slice(mi + 1).some((m) => /자동 저장/.test(m)), JSON.stringify(tl1));
  // 아침에 미뤄 둔 봄맞이 축제가 열리고 끝난 뒤
  const fest = await waitFor(() => { const pp = window.__SM.game.people; return pp.event && pp.event.kind === 'festival'; }, null, 40000).then(() => true, () => false);
  if (fest) await shot('b2_festival_after_load.png');
  await waitFor(() => { const pp = window.__SM.game.people; return !pp.event && !pp.eventQueue.length; }, null, 60000).catch(() => {});
  check('불러온 뒤 미뤄 둔 축제가 열림', fest);
  const shopW0 = await evalG(() => { const b = window.__SM.game.world.blds.find((x) => x.type === 'shop'); return b && b.con ? b.con.work : 999; });
  await sleep(quick ? 15000 : 22000);
  const sm = await api('stats');
  const shopW1 = await evalG(() => { const b = window.__SM.game.world.blds.find((x) => x.type === 'shop'); return b && b.con ? b.con.work : 999; });
  check('아침: 다시 일하러 감', (sm.jobs.worker || 0) + (sm.jobs.haul || 0) + (sm.jobs.builder || 0) > 3, JSON.stringify(sm.jobs));
  check('아침: 밤에 저장한 공사가 이어짐', shopW1 > shopW0, `${shopW0.toFixed ? shopW0.toFixed(1) : shopW0} → ${shopW1.toFixed ? shopW1.toFixed(1) : shopW1}`);
  await api('speed', 1);
  await api('cam', shopAt ? shopAt.x : h.x, shopAt ? shopAt.z : h.z, 34, 0.75, 0.85); await sleep(1500);
  await shot('b3_morning_work.png');
  // 저장 공간이 꽉 찼을 때 아침 실패 알림: 다른 알림이 떠 있으면 덮지 않고, 그 알림이 사라진 뒤에 꼭 띄운다
  await evalG(() => {
    const g = window.__SM.game; g.saver.warned = false; window.__toasts.length = 0;
    const S = Storage.prototype, o = S.setItem; window.__setItem = o;
    S.setItem = function (k, v) { if (k === 'spring-march-save-v1') throw new DOMException('꽉 참', 'QuotaExceededError'); return o.call(this, k, v); };
    window.__mornMsg = '🧪 아침 알림 2';
  });
  await api('speed', 3);
  await api('skipTo', 0.995);
  await waitFor(() => (window.__toasts || []).some((t) => /꽉 차서/.test(t[1])), null, 40000).catch(() => {});
  await api('speed', 1);
  const tl2 = await evalG(() => { Storage.prototype.setItem = window.__setItem; return window.__toasts.slice(); });
  const i2 = tl2.findIndex((t) => t[1] === '🧪 아침 알림 2'), f2 = tl2.findIndex((t) => /꽉 차서/.test(t[1]));
  check('저장 실패 알림은 다른 알림이 사라진 뒤에 뜬다', i2 >= 0 && f2 > i2 && tl2[f2][0] - tl2[i2][0] > 2000, JSON.stringify(tl2));
  check('2번 시험 동안 오류 없음', errs.length === errN0, errs.slice(errN0, errN0 + 3).join(' | '));

  // ============================================================ 3) 새로 시작
  await page.reload();
  await waitModal();
  await page.click('.smsv-new');
  await page.waitForSelector('.smsv-del', { state: 'visible' });
  await sleep(400);
  await shot('c1_new_confirm.png');
  check('새로 시작은 한 번 더 묻는다', !!(await page.$('.smsv-del')) && (await api('hasSave').catch(() => null)) === null);
  await page.click('.smsv [data-a=back]');
  await page.waitForSelector('.smsv-go', { state: 'visible' });
  check('돌아가기 → 다시 이어하기 버튼', !!(await page.$('.smsv-go')));
  await page.click('.smsv-new');
  await page.click('.smsv-del');
  await waitGame();
  await sleep(1500);
  const ns = await evalG(() => ({ mode: window.__SM.game.mode, people: window.__SM.game.people.list.length, hall: !!window.__SM.game.world.hall, wagon: !!window.__SM.game.world.wagon }));
  check('새로 시작: 저장 지워짐', (await api('hasSave')) === false);
  check('새로 시작: 처음 마차 화면', ns.mode === 'settle' && ns.people === 14 && !ns.hall && ns.wagon, JSON.stringify(ns));
  await shot('c2_new_game.png');
  // 3-2) 마차 화면(회관 자리 고르기 전)에서 저장 → 이어하기
  const e3 = errs.length;
  check('마차 화면에서 저장', (await api('save')).ok);
  await page.reload(); await waitModal(); await page.click('.smsv-go'); await waitGame(); await sleep(800);
  const s0 = await evalG(() => ({ mode: window.__SM.game.mode, people: window.__SM.game.people.list.length, hall: !!window.__SM.game.world.hall, wagon: !!window.__SM.game.world.wagon, nature: window.__SM.game.world.nature.size }));
  check('마차 화면에서 이어하기: 마차·14명·자리 고르기', s0.mode === 'settle' && s0.people === 14 && !s0.hall && s0.wagon && s0.nature > 100, JSON.stringify(s0));
  // 3-3) 마을회관을 짓는 중에 저장 → 이어하면 모두 다시 망치질
  const st2 = await api('start');
  await api('settle', st2.x + 6, st2.z - 6, 0.3);
  await api('speed', 1);
  await waitFor(() => { const g = window.__SM.game, h = g.world.hall; if (h && h.con && h.con.work > 4) { g.speed = 0; return true; } return false; }, null, 60000);
  const hw0 = await evalG(() => window.__SM.game.world.hall.con.work);
  check('회관 공사 중 저장', (await api('save')).ok && hw0 > 0, `공사 ${hw0.toFixed(1)}`);
  await freeze(true);
  await page.reload(); await waitModal(); await page.click('.smsv-go'); await waitGame(); await api('speed', 0); await freeze(false);
  const hs = await evalG(() => { const g = window.__SM.game, h = g.world.hall; return { state: h.state, work: h.con && h.con.work, builders: h.builders.length, adults: g.people.list.filter((p) => p.stage === 'adult').length, wagon: !!g.world.wagon, mode: g.mode }; });
  check('회관 공사 이어하기: 현장·일꾼·마차', hs.state === 'site' && Math.abs(hs.work - hw0) < 0.01 && hs.builders === hs.adults && hs.wagon && hs.mode === 'view', JSON.stringify(hs));
  await api('cam', st2.x + 6, st2.z - 4, 26, 0.75, 0.8);
  await api('speed', 3); await sleep(8000);
  const hw1 = await evalG(() => { const h = window.__SM.game.world.hall; return h.con ? h.con.work : 999; });
  check('회관 공사가 이어짐', hw1 > hw0 + 1, `${hw0.toFixed(1)} → ${hw1.toFixed(1)}`);
  await shot('c3_hall_site_after_load.png');
  check('3번 시험 동안 오류 없음', errs.length === e3, errs.slice(e3, e3 + 3).join(' | '));

  // ============================================================ 4) 망가진 저장
  for (const [nm, bad] of [['JSON 아님', '{"v":1,"clock":{"day":'], ['모양이 틀림', '{"v":1,"clock":{"day":2},"blds":"x"}'], ['다른 판', '{"v":99}']]) {
    await newPage('D');
    await setStorage({ [KEY]: bad, [KEY + '-broken']: null });
    const e0 = errs.length;
    await page.goto(srv.url + 'index.html');
    await waitGame();
    await sleep(1600);
    const r = await evalG(() => ({ mode: window.__SM.game.mode, modal: !!document.querySelector('.smsv'), toast: window.__SM.game.hud.toastEl.textContent, broken: localStorage.getItem('spring-march-save-v1-broken'), key: localStorage.getItem('spring-march-save-v1') }));
    check(`망가진 저장(${nm}): 새 마을로 시작, 알림, 따로 보관`, r.mode === 'settle' && !r.modal && /읽을 수 없어서/.test(r.toast) && r.broken === bad && r.key === null && errs.length === e0, JSON.stringify(r));
  }
  await shot('d1_broken_save.png');

  // 4-2) 모양은 맞는데 속에 틀린 값이 든 저장 → 그 사람·건물·나무·길만 빼고 이어하기 (영어 오류 상자 없이)
  if (richSave) {
    const d = JSON.parse(richSave);
    const nP = d.ppl.list.length, nB = d.blds.length;
    d.ppl.list[0].fr = 5;                    // 친구 값이 틀림 → 친구 관계만 비움
    d.ppl.list[1] = null;                    // 사람 하나가 통째로 망가짐 → 그 사람만 빠짐
    d.ppl.list[2].par = 9; d.ppl.list[2].ro = 'x';
    let bi = d.blds.findIndex((b) => ['well', 'bench', 'windmill'].includes(b.k));
    if (bi < 0) bi = d.blds.findIndex((b) => b.k !== 'hall' && !b.ai && b.i !== d.hall);
    d.blds[bi].x = 'abc';                    // 건물 하나 자리가 틀림 → 그 건물만 빠짐
    const fi = d.blds.findIndex((b) => b.pl && b.pl.length);
    if (fi >= 0) d.blds[fi].pl = 7;          // 밭 칸 값이 틀림 → 밭 칸만 빠짐
    d.nat.rows[0] = 5; d.nat.rows[1] = [1, 2];
    if (d.roads.edges[0]) d.roads.edges[0][4] = null;
    d.econ.buffs = 9; d.rival.home = 'x'; d.ppl.q = [{ k: '모름' }, 3]; d.clock.t = 'x';
    const bad = JSON.stringify(d);
    await newPage('D2');
    await setStorage({ [KEY]: bad, [KEY + '-broken']: null });
    const e0 = errs.length;
    await page.goto(srv.url + 'index.html');
    await waitModal();
    await page.click('.smsv-go');
    await waitGame();
    await sleep(1600);
    const r = await evalG(() => ({
      mode: window.__SM.game.mode, ppl: window.__SM.api.loadReport().people, blds: window.__SM.api.loadReport().blds,
      toast: window.__SM.game.hud.toastEl.textContent, errBox: document.getElementById('sm-error').style.display === 'block',
      broken: localStorage.getItem('spring-march-save-v1-broken'), skipped: window.__SM.api.loadReport().skipped,
    }));
    check('반쯤 망가진 저장: 망가진 것만 빼고 이어하기', r.mode === 'view' && r.ppl === nP - 1 && r.blds === nB - 1 && !r.errBox && /빼고 불러왔어요/.test(r.toast) && r.broken === bad && r.skipped >= 4 && errs.length === e0,
      JSON.stringify(Object.assign({}, r, { broken: r.broken === bad, nP, nB })));
    await api('speed', 3); await sleep(10000); await api('speed', 1);
    const bad2 = await evalG(INTEGRITY);
    check('반쯤 망가진 저장: 불러온 뒤 10초 오류 없음', errs.length === e0 && bad2.length === 0, errs.slice(e0, e0 + 3).join(' | ') + bad2.join(','));
    await shot('d2_semantic_broken.png');
  }

  // 4-3) 그래도 못 불러오는 경우(마지막 단계에서 오류) → 저절로 새로고침해서 새 마을 + 한국어 알림 (영어 오류 글 없이)
  if (richSave) {
    await newPage('D3', () => { try { if (!sessionStorage.getItem('t-fail-set')) { sessionStorage.setItem('t-fail-set', '1'); sessionStorage.setItem('t-fail', '1'); } } catch (e) { /* */ } });
    // 시험용: 불러오는 중에만 한 번 오류를 내는 hud.js (디스크 파일은 그대로)
    await page.route('**/src/ui/hud.js', async (route) => {
      const res = await route.fetch();
      const body = (await res.text()).replace('  fillTools() {', "  fillTools() { if (sessionStorage.getItem('t-fail') === '1' && /저장된 마을을 불러오는 중/.test((document.getElementById('sm-loading-txt') || {}).textContent || '')) { sessionStorage.removeItem('t-fail'); throw new Error('test failure'); }");
      await route.fulfill({ response: res, body });
    });
    await setStorage({ [KEY]: richSave, [KEY + '-broken']: null });
    const e0 = errs.length;
    await page.goto(srv.url + 'index.html');
    await waitModal();
    await Promise.all([page.waitForNavigation({ timeout: 90000 }), page.click('.smsv-go')]);
    await waitGame();
    await sleep(1600);
    const r = await evalG(() => ({
      mode: window.__SM.game.mode, ppl: window.__SM.game.people.list.length, toast: window.__SM.game.hud.toastEl.textContent,
      errBox: document.getElementById('sm-error').style.display === 'block', key: localStorage.getItem('spring-march-save-v1'),
      broken: localStorage.getItem('spring-march-save-v1-broken'), modal: !!document.querySelector('.smsv'),
    }));
    check('못 불러오면 저절로 새 마을 + 한국어 알림 (오류 상자 없음)', r.mode === 'settle' && r.ppl === 14 && !r.errBox && !r.modal && /불러오지 못해서 새 마을로/.test(r.toast) && r.key === null && r.broken === richSave && errs.length === e0,
      JSON.stringify(Object.assign({}, r, { key: !!r.key, broken: r.broken === richSave })));
    await shot('d3_load_failed_new_game.png');
  }

  // ============================================================ 5) 저장 공간이 막힌 브라우저
  await newPage('E', () => { Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new DOMException('막힘', 'SecurityError'); } }); });
  const e0 = errs.length;
  await page.goto(srv.url + 'index.html');
  await waitGame();
  await sleep(1600);
  const t1 = await evalG(() => window.__SM.game.hud.toastEl.textContent);
  await page.click('button.sysb[title^="저장하기"]');
  await sleep(300);
  const t2 = await evalG(() => window.__SM.game.hud.toastEl.textContent);
  const sv2 = await api('save');
  check('저장 공간 막힘: 알림만 띄우고 계속', /저장할 수 없어요/.test(t1) && /저장할 수 없어요/.test(t2) && sv2.ok === false && errs.length === e0 && (await evalG(() => window.__SM.game.mode)) === 'settle', `"${t1}" / "${t2}"`);
  await shot('e1_storage_blocked.png');

  // ============================================================ 6) 휴대폰 가로 화면: 고르기 창 모양, 손가락으로 이어하기
  if (richSave) {
    await newPage('F', null, { viewport: { width: 844, height: 390 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await setStorage({ [KEY]: richSave });
    const e6 = errs.length;
    await page.goto(srv.url + 'index.html');
    await waitModal();
    await shot('f1_mobile_modal.png');
    const fit = await page.evaluate(() => { const r = document.querySelector('.smsv').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth; });
    check('휴대폰: 고르기 창이 화면 안에', fit);
    await page.tap('.smsv-go');
    await waitGame(); await sleep(3000);
    const n = await evalG(() => window.__SM.game.people.list.filter((p) => !p.ai).length);
    check('휴대폰: 눌러서 이어하기', n === JSON.parse(richSave).sum.pop && errs.length === e6, `주민 ${n}`);
    await shot('f2_mobile_after_load.png');
  }
} catch (e) {
  errs.push('test: ' + (e.stack || e));
  try { await shot('fail.png'); } catch (e2) { /* */ }
}
const failed = results.filter((r) => !r.ok);
log('\n==== 결과:', results.length - failed.length, '/', results.length, '통과');
for (const f of failed) log('  FAIL', f.name, f.info);
log('errors', errs.length ? '\n' + errs.slice(0, 20).join('\n') : 0);
if (warns.length) log('warnings', warns.length, '\n' + [...new Set(warns)].slice(0, 10).join('\n'));
await browser.close(); await srv.close();
process.exit(failed.length || errs.length ? 1 : 0);
