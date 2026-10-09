// 저장하기·불러오기: 마을 전체(시간·창고·자연·길·건물·주민·이웃 마을·코인)를 브라우저 저장 공간 한 칸에 담고,
// 다시 열면 "이어하기 / 새로 시작"을 물어본다.
//  - 저장 칸: localStorage 'spring-march-save-v1'. 접근은 모두 try/catch (못 쓰면 알림만 띄우고 계속 논다)
//  - 자동 저장: 게임 아침마다, 창을 숨기거나 닫을 때. 위쪽 💾 버튼으로 바로 저장
//  - 불러오면 모두 "쉬는 중"으로 시작한다 (일은 1초 안에 다시 나눠진다). 들고 가던 짐은 창고로, 깔던 길 재료는 되돌려 준다
//  - 다른 기능이 자기 상태도 담고 싶으면: game.<seasons|diplo>.saveData() → JSON 으로 바꿀 수 있는 값,
//    불러올 때 game.<seasons|diplo>.loadData(값) 을 부른다 (await 가능, Seasons.init() 보다 먼저)
//    외교(diplo)에 saveData 가 아직 없으면 숫자·글자·참/거짓과 그런 값만 든 작은 묶음(우호도·서리골 창고·제안 등)만
//    대신 담아 둔다 (사람·건물·화면 물건을 가리키는 값은 담지 않는다)
//  - 자연물은 계절 모델(season_*)이 아니라 원래(겨울) 모델 이름으로 담는다. 불러온 뒤 계절 기능이 지금 계절 모습으로 바꾼다
//    (자연물 자리는 반올림하지 않는다: 계절 기능이 자리 값으로 활엽수·꽃밭을 고르기 때문)
//  - 반쯤 망가진 저장: 틀린 값이 든 사람·건물·나무·길 하나만 빼고 불러오고 알림. 원래 저장은 '-broken' 칸에 남긴다.
//    그래도 못 불러오면 새로고침해서 새 마을로 시작하고 알림 (화면에는 영어 오류 글을 보이지 않는다)

import { Building } from './buildings.js';
import { Lake, decorate } from './ranch.js';
import { BUILDINGS, NUM, SEASONS, ROADS, ROAD_ORDER, TRAITS, DECOS, LOOKS } from './defs.js';

const KEY = 'spring-march-save-v1';
const BROKEN = KEY + '-broken';          // 읽지 못한 저장은 지우지 않고 여기로 옮겨 둔다
const AUTOLOAD = 'spring-march-autoload'; // 시험·다시 불러오기: 새로고침 뒤 묻지 않고 바로 이어하기
const LOADFAIL = 'spring-march-loadfail'; // 불러오다 실패해서 새로고침한 뒤: 새 마을에서 알림 띄우기
const VER = 1;
const STAGES = ['adult', 'kid', 'elder'];
// 미뤄 둔 행사: 종류별로 꼭 있어야 하는 사람·자리 (없으면 그 행사는 빼고 불러온다)
const EVENT_NEED = { wedding: ['a', 'b'], birth: ['mom', 'dad'], funeral: ['p'], festival: [] };
const EXT = ['seasons', 'diplo'];        // saveData/loadData 를 가진 다른 기능
const PERSON_REFS = ['a', 'b', 'mom', 'dad', 'p'];

const rd = (v, k) => { const m = 10 ** k; return Math.round((+v || 0) * m) / m; };
const r1 = (v) => rd(v, 1), r2 = (v) => rd(v, 2), r3 = (v) => rd(v, 3), r4 = (v) => rd(v, 4);
// 불러올 때 값 고르기: 저장이 반쯤 망가져 있어도 이상한 값을 그대로 쓰지 않는다
const fin = (v) => typeof v === 'number' && Number.isFinite(v);
const num = (v, d = 0) => (fin(v) ? v : d);
const arr = (v) => (Array.isArray(v) ? v : []);
const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {});
/** 이름 → 숫자 묶음에서 숫자만 (창고·공사 재료·장식) */
const nums = (v) => { const o = {}; for (const [k, x] of Object.entries(obj(v))) if (fin(x)) o[k] = x; return o; };
/** 상인 물건: 지금 게임이 이름·값을 알 수 있는 것만 (없어진 장식이나 빠진 값은 버린다 → 상인 창이 깨지지 않게) */
const okOffer = (o) => !!o && typeof o === 'object' && fin(o.price) && (o.kind === 'deco' ? !!DECOS[o.key]
  : o.kind === 'buff' ? typeof o.name === 'string' && !!o.buff && typeof o.buff === 'object' && fin(o.buff.days)
    : o.kind === 'goods' ? typeof o.name === 'string' && !!o.goods && typeof o.goods === 'object' : false);
const ALL_LOOKS = new Set(Object.values(LOOKS).flat());
/** 이주민 제안 속 사람: 이름·성별·나이·모습이 다 있어야 한다 (반쯤 빈 사람은 버린다) */
const okNewcomer = (x) => !!x && typeof x === 'object' && typeof x.name === 'string' && (x.gender === 'm' || x.gender === 'f')
  && fin(x.age) && ALL_LOOKS.has(x.look) && (x.stage == null || STAGES.includes(x.stage)) && (x.trait == null || !!TRAITS[x.trait]);
/** [[번호, 값], ...] 에서 바른 것만 (친구·사랑) */
const pairs = (v) => arr(v).filter((e) => Array.isArray(e) && fin(e[0]) && fin(e[1])).map((e) => [e[0], e[1]]);
const str = (v) => (typeof v === 'string' && v ? v : undefined);
const NATURE_STD = new Set(['id', 'type', 'model', 'x', 'z', 'ry', 'sc', 'reserved']);
// 외교 기능에 saveData 가 없을 때 대신 담지 않는 것 (화면·임시 값, 사람을 맡은 나들이)
const PLAIN_SKIP = new Set(['g', 'btn', 'panelOpen', 'panelH', 'modalQ', 'tk', 'fxT', 'trips', 'fest', 'ready', 'loaded']);

/** 계절 모델 → 원래(겨울) 모델. 활엽수 자리·꽃밭 자리는 계절 기능이 자리(x,z)로 다시 정한다 */
function baseModel(o) {
  const m = o.model;
  if (typeof m !== 'string' || !m.startsWith('season_')) return m;
  if (typeof o.sv === 'string' && o.sv) return o.sv;            // 눈 더미 자리 (꽃·풀·낙엽·숨김)
  if (m === 'season_pine_b') return 'tree_pine_b';
  if (m === 'season_pine_c') return 'tree_pine_snow';
  if (/^season_(pine|decid)/.test(m)) return 'tree_pine_a';
  if (m.startsWith('season_bush')) return 'bush_snow';
  if (m.startsWith('season_rock_b')) return 'rock_ore_b';
  if (m.startsWith('season_rock')) return 'rock_ore';
  if (m === 'season_stump') return 'tree_stump';
  return o.type === 'bush' ? 'snow_pile_a' : m;
}

/** 숫자·글자·참/거짓과 그런 값만 든 작은 묶음인가 (사람·건물·Map·화면 물건은 아님) */
function isPlain(v, depth = 0) {
  if (v == null || ['number', 'string', 'boolean'].includes(typeof v)) return typeof v !== 'number' || Number.isFinite(v);
  if (typeof v !== 'object' || depth > 3) return false;
  const proto = Object.getPrototypeOf(v);
  if (proto !== Object.prototype && proto !== Array.prototype) return false;
  const vals = Array.isArray(v) ? v : Object.values(v);
  if (vals.length > 60) return false;
  return vals.every((x) => isPlain(x, depth + 1));
}
function plainState(m) {
  const out = {};
  for (const [k, v] of Object.entries(m)) if (!PLAIN_SKIP.has(k) && typeof v !== 'function' && isPlain(v)) out[k] = v;
  return JSON.parse(JSON.stringify(out));
}
function applyPlain(m, data) {
  if (!data || typeof data !== 'object') return;
  for (const [k, v] of Object.entries(data)) {
    if (PLAIN_SKIP.has(k) || !(k in m) || typeof m[k] === 'function') continue;
    const cur = m[k];
    const same = cur == null || v == null || typeof cur === typeof v && Array.isArray(cur) === Array.isArray(v);
    if (same && (cur == null || isPlain(cur))) m[k] = v;
  }
}

/** 저장 공간 (막혀 있으면 null / false) */
const store = {
  get(k) { try { return window.localStorage.getItem(k); } catch (e) { return undefined; } },
  set(k, v) { try { window.localStorage.setItem(k, v); return null; } catch (e) { return e || new Error('저장 실패'); } },
  del(k) { try { window.localStorage.removeItem(k); return true; } catch (e) { return false; } },
};

export class SaveSystem {
  constructor(game) {
    this.g = game;
    this.ready = false;        // 첫 프레임부터 true (그 전에는 저장하지 않는다: 반쯤 만든 마을을 덮어쓰지 않게)
    this.autoPending = false;
    this.lastAutoToast = -1e9;
    this.autoN = 0;
    this.warned = false;
    this.later = [];           // 게임이 보이면 띄울 알림
    this.report = null;        // 불러온 직후 점검 (시험용)
    this.skipped = 0;          // 불러올 때 망가져서 건너뛴 것 수
    this.loaded = false;       // 저장된 마을을 불러왔는가
    this.waitToast = null;     // 다른 알림이 떠 있어서 미뤄 둔 저장 실패 알림
    game.clock.on((ev) => { if (ev === 'morning') this.autoPending = true; });
  }

  // ================================================================ 시작
  /** 시작할 때: 저장이 있으면 "이어하기/새로 시작"을 물어보고, 이어하면 불러온 뒤 true */
  async offerContinue() {
    const g = this.g;
    if (g.hud && !this.btn) this.btn = g.hud.addSysButton('💾', '저장하기 (아침마다 저절로 저장돼요)', () => this.manualSave());
    if (g.perf) return false;
    // 지난번에 불러오다 실패해서 새로고침했으면: 새 마을로 시작한다고 알려 준다
    let failed = false;
    try { failed = window.sessionStorage.getItem(LOADFAIL) === '1'; if (failed) window.sessionStorage.removeItem(LOADFAIL); } catch (e) { failed = false; }
    if (failed) this.later.push(['저장된 마을을 불러오지 못해서 새 마을로 시작했어요', true]);
    const raw = store.get(KEY);
    if (raw === undefined) { this.later.push(['이 브라우저에서는 저장할 수 없어요. 그래도 계속 놀 수 있어요', true]); return false; }
    if (!raw) return false;
    const data = parseSave(raw);
    if (!data) {
      store.set(BROKEN, raw); store.del(KEY);
      this.later.push(['저장된 마을을 읽을 수 없어서 새 마을로 시작해요', true]);
      return false;
    }
    let auto = false;
    try { auto = window.sessionStorage.getItem(AUTOLOAD) === '1'; window.sessionStorage.removeItem(AUTOLOAD); } catch (e) { auto = false; }
    const choice = auto ? 'load' : await this.ask(data);
    if (choice === 'new') { store.del(KEY); return false; }
    setLoadText('저장된 마을을 불러오는 중…');
    try {
      await this.restore(data);
    } catch (e) {
      // 망가진 부분은 하나씩 건너뛰므로 여기까지 오는 일은 드물다. 반쯤 만든 마을은 버리고 새로고침해서 새 마을로
      // (자세한 오류는 개발자 콘솔에만: 화면에는 쉬운 한국어만 보인다)
      console.warn('save: 불러오기 실패', e);
      store.set(BROKEN, raw); store.del(KEY);
      if (store.get(KEY) == null) {
        try { window.sessionStorage.setItem(LOADFAIL, '1'); } catch (e2) { /* 알림만 못 띄운다 */ }
        setLoadText('저장된 마을을 불러오지 못해서 새 마을로 시작해요…');
        setTimeout(() => location.reload(), 1500);
        return new Promise(() => {});   // 새로고침될 때까지 시작하지 않는다 (반쯤 만든 마을이 저장되지 않게)
      }
      if (window.__smShowError) window.__smShowError('저장된 마을을 불러오지 못했어요. 새로고침해 주세요.');
      return new Promise(() => {});
    }
    this.loaded = true;
    if (this.skipped) {
      store.set(BROKEN, raw);          // 원래 저장은 따로 남겨 둔다 (다음 저장이 빠진 채로 덮어쓰니까)
      this.later.push(['📂 지난번 마을을 이어서 해요 (망가진 몇 가지는 빼고 불러왔어요)', true]);
    } else this.later.push(['📂 지난번 마을을 이어서 해요', false]);
    return true;
  }

  /** 불러오는 화면 위에 고르기 창 (불러오는 화면 z-index 20 안에 넣어서 HUD(5)에 가리지 않게) */
  ask(data) {
    injectCss();
    const host = document.getElementById('sm-loading') || (() => {
      const d = document.createElement('div');
      d.style.cssText = 'position:fixed;inset:0;z-index:25;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#eef4fb,#d6e2f0)';
      document.body.appendChild(d); d.__own = true; return d;
    })();
    const txt = document.getElementById('sm-loading-txt');
    if (txt) txt.style.display = 'none';
    const box = document.createElement('div');
    box.className = 'smsv';
    host.appendChild(box);
    const s = data.sum || {};
    const when = ago(data.savedAt);
    return new Promise((resolve) => {
      const done = (v) => { box.remove(); if (txt) txt.style.display = ''; if (host.__own) host.remove(); resolve(v); };
      const main = () => {
        box.innerHTML = `<div class="smsv-t">🏘️ 저장된 마을이 있어요</div>${when ? `<div class="smsv-s">마지막 저장 · ${when}</div>` : ''}` +
          `<button class="smsv-go" data-a="load">▶ 이어하기 <small>(${esc(sumText(s))})</small></button>` +
          '<button class="smsv-new" data-a="new">새로 시작</button>';
        box.querySelector('[data-a=load]').onclick = () => done('load');
        box.querySelector('[data-a=new]').onclick = confirm;
      };
      const confirm = () => {
        box.innerHTML = '<div class="smsv-t">정말 새로 시작할까요?</div><div class="smsv-s">저장된 마을이 지워지고 되돌릴 수 없어요</div>' +
          '<button class="smsv-del" data-a="del">지우고 새로 시작</button><button class="smsv-new" data-a="back">돌아가기</button>';
        box.querySelector('[data-a=del]').onclick = () => done('new');
        box.querySelector('[data-a=back]').onclick = main;
      };
      main();
    });
  }

  // ================================================================ 매 프레임
  /** 매 프레임 (자동 저장 등) */
  update(real) {
    void real;
    const g = this.g;
    if (g.perf) return;
    if (!this.ready) {
      this.ready = true;
      const hide = () => this.autoSave('hide');
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') hide(); });
      window.addEventListener('pagehide', hide);
      const msgs = this.later.splice(0);
      if (msgs.length) setTimeout(() => { for (const [m, err] of msgs) g.hud.toast(m, err); }, 700);
      // 멈춘 채로 불러와도 위쪽 '서리골' 버튼이 바로 보이게 (외교 버튼은 원래 시간이 흐를 때 생긴다)
      const dp = g.diplo;
      if (this.loaded && dp) { try { if (typeof dp.ensureButton === 'function') dp.ensureButton(); if (typeof dp.refreshUi === 'function') dp.refreshUi(); } catch (e) { /* 다음 프레임에 외교 기능이 직접 만든다 */ } }
      return;
    }
    if (this.autoPending) { this.autoPending = false; this.autoSave('morning'); }
    // 미뤄 둔 저장 실패 알림: 다른 알림이 사라진 뒤에
    if (this.waitToast && !this.toastBusy()) { const m = this.waitToast; this.waitToast = null; g.hud.toast(m, true); }
  }

  /** 지금 다른 알림이 떠 있는가 (자동 저장 알림이 그 알림을 덮지 않게) */
  toastBusy() {
    const t = this.g.hud && this.g.hud.toastEl;
    return !!t && +t.style.opacity > 0 && !!t.textContent;
  }

  autoSave(why) {
    if (!this.ready || this.g.perf) return;
    const r = this.save();
    if (!r.ok) {
      // 실패 알림은 꼭 보여 준다: 다른 알림(아침 교환 제안 등)이 떠 있으면 그게 사라진 뒤에
      if (why === 'morning' && !this.warned) { this.warned = true; if (this.toastBusy()) this.waitToast = r.msg; else this.g.hud.toast(r.msg, true); }
      return;
    }
    this.autoN++;
    // 자동 저장 알림은 가끔만 (처음 한 번, 그 뒤로는 실제 4분에 한 번쯤). 다른 알림이 떠 있으면 덮지 않고 이번엔 건너뛴다
    const now = performance.now();
    if (why === 'morning' && now - this.lastAutoToast > 240000 && !this.toastBusy()) { this.lastAutoToast = now; this.g.hud.toast('💾 자동 저장했어요'); }
  }

  manualSave() {
    if (!this.ready) return;
    const r = this.save();
    if (r.ok) { this.g.hud.toast('💾 저장했어요'); this.g.audio && this.g.audio.play('click', 0.6); }
    else this.g.hud.toast(r.msg, true);
  }

  /** 지금 마을을 저장 칸에 쓴다 → {ok, size, msg} */
  save() {
    let txt;
    try { txt = JSON.stringify(this.serialize()); } catch (e) { console.error(e); return { ok: false, msg: '저장하지 못했어요 (마을 정보를 담다가 문제가 생겼어요)' }; }
    const err = store.set(KEY, txt);
    if (err) {
      const full = err && (err.name === 'QuotaExceededError' || err.code === 22 || err.code === 1014);
      return { ok: false, size: txt.length, msg: full ? '저장 공간이 꽉 차서 저장하지 못했어요' : '이 브라우저에서는 저장할 수 없어요 (저장 공간이 막혀 있어요)' };
    }
    return { ok: true, size: txt.length };
  }

  // ================================================================ 담기
  serialize() {
    const g = this.g, w = g.world, pp = g.people, c = g.clock, rv = g.rival, e = g.econ;
    const alive = pp.list.filter((p) => !p.dead);
    const stock = {};
    for (const [k, v] of Object.entries(w.stock)) stock[k] = r2(v);
    const give = (t, n = 1) => { if (t) stock[t] = r2((stock[t] || 0) + n); };
    // 들고 가던 짐은 창고로 (불러오면 모두 빈손으로 시작하니까)
    for (const p of alive) {
      const j = p.job;
      if (!j) continue;
      if (j.kind === 'haul') { if (j.taken && !j.done) for (const o of [j.task, ...(j.extra || [])]) give(o.type); }
      else if (p.carry) give(p.carry);
    }
    // 깔던 길: 쓴 재료를 되돌려 준다 (불러오면 아무도 깔지 않으니까)
    for (const ed of w.roads.edges.values()) {
      if (!ed.busy) continue;
      const nr = ROADS[ROAD_ORDER[ROAD_ORDER.indexOf(ed.type) + 1]];
      if (nr && nr.cost) { const n = Math.max(1, Math.ceil(ed.len / nr.per)); for (const [k, v] of Object.entries(nr.cost)) give(k, v * n); }
    }

    // 자연 (나무·바위·덤불·그루터기): [id, 종류, 모델, x, z, 방향, 크기, {남은 양 등}]
    const types = [], models = [], nat = [];
    const idx = (a, v) => { let k = a.indexOf(v); if (k < 0) { k = a.length; a.push(v); } return k; };
    for (const o of w.nature.values()) {
      // 자리(x,z)는 반올림하지 않는다: 계절 기능이 자리로 활엽수·꽃밭 모양을 정해서, 조금만 달라져도 숲 모습이 바뀐다
      const row = [o.id, idx(types, o.type), idx(models, baseModel(o)), o.x, o.z, r2(o.ry), r3(o.sc)];
      let ex = null;
      for (const [k, v] of Object.entries(o)) {
        if (NATURE_STD.has(k) || v == null || !['number', 'string', 'boolean'].includes(typeof v)) continue;
        (ex = ex || {})[k] = typeof v === 'number' ? r3(v) : v;
      }
      if (ex) row.push(ex);
      nat.push(row);
    }

    // 길
    const nodeSet = new Set(w.roads.nodes.values());
    for (const ed of w.roads.edges.values()) { nodeSet.add(ed.a); nodeSet.add(ed.b); }   // 길 끝 교차점은 빠짐없이
    const roads = {
      nid: w.roads.nid,
      nodes: [...nodeSet].map((n) => (n.keep ? [n.id, r3(n.x), r3(n.z), 1] : [n.id, r3(n.x), r3(n.z)])),
      edges: [...w.roads.edges.values()].map((ed) => [ed.id, ed.a.id, ed.b.id, ed.type, ed.pts.flatMap((p) => [r2(p.x), r2(p.z)])]),
    };

    // 건물
    const blds = w.blds.filter((b) => !b.dead).map((b) => {
      const d = { i: b.id, k: b.type, x: r3(b.x), z: r3(b.z), r: r4(b.rot), s: b.state === 'active' ? 'a' : 's' };
      if (b.level) d.l = b.level;
      if (b.ai) d.ai = 1;
      if (b.free) d.f = 1;
      if (b.con) d.c = { k: b.con.kind, n: b.con.need, h: b.con.have, u: b.con.used, w: r3(b.con.work), W: b.con.workNeeded };
      if (b.inputs) d.in = r2(b.inputs);
      if (b.out) d.o = b.out;
      if (b.working) d.wk = 1;
      if (b.t) d.t = r3(b.t);
      if (b.plots && b.plots.length) d.pl = b.plots.map((p) => [r2(p.x), r2(p.z), p.stage, r1(p.t)]);
      if (b.animals) d.an = b.animals.map((a) => [a.key, r2(a.x), r2(a.z), r2(a.yaw), a.ready ? 1 : 0, r1(a.prod)]);
      if (b.trees) d.tr = b.trees.map((t) => [r1(t.t), t.ready ? 1 : 0]);
      if (b.pinned) d.pin = 1;
      if (b.fire) d.lit = 1;
      if (b.worker && !b.worker.dead) d.wr = b.worker.id;   // 일하던 사람 (불러온 뒤 바로 일터로)
      return d;
    });

    // 주민
    const ev = (x) => {
      const o = { k: x.kind };
      for (const f of PERSON_REFS) if (x[f]) o[f] = x[f].id;
      if (x.at) o.at = [r2(x.at.x), r2(x.at.z)];
      return o;
    };
    const q = pp.eventQueue.map(ev);
    // 하고 있던 결혼식·축제는 다시 연다 (아기 탄생·장례는 이미 일어난 일이라 넘어간다)
    if (pp.event && (pp.event.kind === 'wedding' || pp.event.kind === 'festival')) q.unshift(ev(pp.event));
    const ppl = alive.map((p) => {
      const d = { i: p.id, n: p.name, g: p.gender, st: p.stage, a: p.age, tr: p.trait, lk: p.look, e: r3(p.energy), m: r3(p.mood), x: r2(p.x), z: r2(p.z), y: r2(p.yaw) };
      if (p.hungry) d.h = 1;
      if (p.joy) d.j = r3(p.joy);
      if (p.home && !p.home.dead) d.home = p.home.id;
      if (p.spouse && !p.spouse.dead) d.sp = p.spouse.id;
      if (p.partner && !p.partner.dead) d.pa = p.partner.id;
      const par = (p.parents || []).filter((q2) => q2 && !q2.dead).map((q2) => q2.id);
      if (par.length) d.par = par;
      if (p.friends.size) d.fr = [...p.friends].map(([k, v]) => [k, r2(v)]);
      if (p.romance.size) d.ro = [...p.romance].map(([k, v]) => [k, r2(v)]);
      if (p.ai) d.ai = 1;
      if (p.special) d.spc = 1;
      if (p.marriedDay != null) d.md = p.marriedDay;
      if (p.weddingPlanned) d.wp = 1;
      if (p.coldNight) d.cold = 1;
      if (p.ate && p.ate.size) d.ate = [...p.ate];
      return d;
    });

    const ext = {}, plain = {};
    for (const k of EXT) {
      const m = g[k];
      if (m && typeof m.saveData === 'function') { try { const v = m.saveData(); if (v !== undefined) ext[k] = v; } catch (err) { console.warn('save ext', k, err); } }
      else if (m && k === 'diplo') { try { plain[k] = plainState(m); } catch (err) { console.warn('save plain', k, err); } }
    }
    const gl = g.stage.goal;
    return {
      v: VER, savedAt: Date.now(),
      sum: { year: c.year, season: c.season.name, day: c.dayOfSeason, pop: alive.filter((p) => !p.ai).length },
      clock: { day: c.day, t: r4(c.t) },
      w: {
        stock, nid: w.nid, rng: w.rng.s, start: w.start ? { x: r2(w.start.x), z: r2(w.start.z) } : null,
        stats: Object.assign({}, w.stats), tt: w.treeTarget, rt: r2(w.regrowT || 0),
        lake: w.lake ? [r2(w.lake.cx), r2(w.lake.cz), r2(w.lake.rx), r2(w.lake.rz)] : null,
        wagon: w.wagon ? [r2(w.wagon.x), r2(w.wagon.z), r2(w.wagon.obj ? w.wagon.obj.rotation.y : 0.5)] : null,
      },
      nat: { types, models, rows: nat },
      roads,
      blds, hall: w.hall && !w.hall.dead ? w.hall.id : null,
      graves: pp.graves || 0,
      rival: { b: r4(rv.beacon), lit: rv.lit ? 1 : 0, st: rv.step, t: r1(rv.t), home: rv.home ? [r2(rv.home.x), r2(rv.home.z)] : null, hall: rv.hall && !rv.hall.dead ? rv.hall.id : null },
      econ: {
        coins: e.coins, decos: Object.assign({}, e.decos), buffs: e.buffs.map((b) => ({ name: b.name, buff: b.buff, until: b.until })),
        ds: e.daysSince, earned: e.earned,
        merchant: e.merchant ? { offers: e.merchant.offers.map((o) => Object.assign({}, o)), until: e.merchant.until, ry: e.merchant.sled ? r3(e.merchant.sled.rotation.y) : null } : null,
      },
      won: g.won ? 1 : 0,
      ppl: { nid: pp.nid, list: ppl, q, offer: pp.offer || null, od: r2(pp.offerDays), log: pp.log.slice(0, 40) },
      cam: [r2(gl.tx), r2(gl.tz), r2(gl.dist), r3(gl.yaw), r3(gl.pitch)],
      ext, plain,
    };
  }

  // ================================================================ 풀기
  // 저장이 반쯤 망가져 있어도(값 하나가 틀림 등) 그 사람·건물·나무·길 하나만 건너뛰고 나머지는 불러온다.
  // 건너뛴 수는 this.skipped (불러온 뒤 알림으로 알려 준다)
  skip(what, e) { this.skipped++; console.warn('save: 망가져서 건너뜀 —', what, (e && e.message) || e); }
  part(what, fn) { try { return fn(); } catch (e) { this.skip(what, e); return null; } }
  async partAsync(what, fn) { try { return await fn(); } catch (e) { this.skip(what, e); return null; } }

  async restore(d) {
    const g = this.g, w = g.world, pp = g.people, lib = g.lib;
    this.skipped = 0;
    const W = obj(d.w), P = obj(d.ppl), CK = obj(d.clock);
    // 시간
    g.clock.day = Math.max(1, num(CK.day, 1) | 0);
    g.clock.t = Math.min(0.9999, Math.max(0, num(CK.t)));
    // 창고·숫자 (다른 기능이 붙잡고 있을 수 있는 객체는 바꿔 끼우지 않고 안을 채운다)
    refill(w.stock, nums(W.stock));
    w.stats = Object.assign({ breadMade: 0 }, nums(W.stats));
    if (fin(W.rng)) w.rng.s = (W.rng >>> 0) || 1;
    const sp = obj(W.start);
    w.start = fin(sp.x) && fin(sp.z) ? { x: sp.x, z: sp.z } : { x: NUM.mapSize * 0.45, z: NUM.mapSize * 0.5 };
    w.regrowT = num(W.rt);
    w.nid = Math.max(w.nid, num(W.nid));
    pp.nid = Math.max(pp.nid, num(P.nid));
    // 호수
    const lk = arr(W.lake);
    if (lk.length === 4 && lk.every(fin)) this.part('호수', () => { w.lake = new Lake(w, ...lk); });
    else if (W.lake != null) this.skip('호수', null);

    // 자연
    const nt = obj(d.nat), ntTypes = arr(nt.types), ntModels = arr(nt.models);
    let trees = 0;
    for (const row of arr(nt.rows)) {
      this.part('자연', () => {
        if (!Array.isArray(row)) throw new Error('나무 줄 모양이 틀림');
        const [id, ti, mi, x, z, ry, sc, ex] = row;
        const type = ntTypes[ti];
        if (!fin(id) || !fin(x) || !fin(z) || typeof type !== 'string' || w.nature.has(id)) throw new Error('나무 값이 틀림');
        const ex0 = obj(ex);
        let model = ntModels[mi];
        // 지금 없는 모델이면 (옛 저장의 계절 모델 등) 원래 모델 → 종류별 기본 모델
        if (!w.pools[model]) model = baseModel({ model, type, sv: ex0.sv });
        if (!w.pools[model]) model = Object.keys(w.pools).find((k) => k.startsWith(type === 'tree' ? 'tree_pine' : type === 'rock' ? 'rock_' : type === 'stump' ? 'tree_stump' : 'bush'));
        if (!model || !w.pools[model]) return;
        const extra = {};
        for (const [k, v] of Object.entries(ex0)) if (!NATURE_STD.has(k) && (typeof v === 'string' || typeof v === 'boolean' || fin(v))) extra[k] = v;
        extra.id = id;
        if (type === 'rock' && !fin(extra.amount)) extra.amount = NUM.rockAmount;
        if (type === 'stump' && !fin(extra.t)) extra.t = NUM.stumpTime;
        const o = w.addNature(type, model, x, z, num(ry), num(sc, 1) || 1, extra);
        // 캐다 만 바위는 줄어든 크기로
        if (o && type === 'rock' && o.amount < NUM.rockAmount && w.pools[o.model]) w.pools[o.model].set(o.id, o.x, 0, o.z, o.ry, o.sc * (0.45 + 0.55 * Math.max(0, o.amount) / NUM.rockAmount));
        if (type === 'tree') trees++;
      });
    }
    w.treeTarget = num(W.tt) || trees;

    // 길 (새로 붙는 번호가 저장된 번호와 겹치지 않게 번호를 먼저 올려 둔다)
    const R = w.roads, nodeOf = new Map(), RD = obj(d.roads);
    const isId = (v) => Number.isInteger(v) && v >= 0;
    const rNodes = arr(RD.nodes).filter((n) => Array.isArray(n) && isId(n[0]) && fin(n[1]) && fin(n[2]));
    const rEdges = arr(RD.edges).filter((e) => Array.isArray(e) && isId(e[0]) && isId(e[1]) && isId(e[2]) && typeof e[3] === 'string' && ROADS[e[3]] && Array.isArray(e[4]));
    const badRoads = arr(RD.nodes).length - rNodes.length + arr(RD.edges).length - rEdges.length;
    for (let k = 0; k < badRoads; k++) this.skip('길', null);
    let top = Math.max(R.nid, num(RD.nid));
    for (const n of rNodes) top = Math.max(top, n[0] + 1);
    for (const e of rEdges) top = Math.max(top, e[0] + 1);
    R.nid = top;
    for (const [id, x, z, keep] of rNodes) {
      if (nodeOf.has(id)) continue;
      this.part('길 교차점', () => {
        const n = R.addNode(x, z);
        R.nodes.delete(n.id); n.id = id; R.nodes.set(id, n);
        if (keep) n.keep = true;
        nodeOf.set(id, n);
      });
    }
    for (const [id, a, b, type, flat] of rEdges) {
      this.part('길', () => {
        const na = nodeOf.get(a), nb = nodeOf.get(b);
        if (!na || !nb || R.edges.has(id)) return;
        const pts = [];
        for (let k = 0; k + 1 < flat.length; k += 2) if (fin(flat[k]) && fin(flat[k + 1])) pts.push({ x: flat[k], z: flat[k + 1] });
        if (pts.length < 2) return;
        const e = R.makeEdge(na, nb, pts, type);
        if (!e) return;
        R.edges.delete(e.id); e.id = id; R.edges.set(id, e);
      });
    }
    for (const n of [...R.nodes.values()]) if (!n.edges.size && !n.keep) R.nodes.delete(n.id);
    R.rebuildJoints();
    R.changed();

    // 건물
    const byId = new Map(), lit = [], wrOf = new Map();
    for (const bd of arr(d.blds)) {
      const b = await this.partAsync('건물', () => this.restoreBuilding(bd));
      if (!b) continue;
      byId.set(bd.i, b);
      if (bd.lit) lit.push(b);
      if (fin(bd.wr)) wrOf.set(b, bd.wr);
    }
    w.hall = byId.get(d.hall) || w.blds.find((b) => b.def.kind === 'hq' && !b.ai) || null;
    const hallUp = !!(w.hall && w.hall.state === 'active');

    // 마차 (마을회관이 다 지어지면 곧 떠나므로 그때는 두지 않는다)
    const wgd = arr(W.wagon);
    if (wgd.length >= 2 && fin(wgd[0]) && fin(wgd[1]) && !hallUp) {
      await this.partAsync('마차', async () => {
        const [x, z] = wgd, ry = num(wgd[2], 0.5);
        await lib.loadProp('trade_post');
        const wg = lib.prop('trade_post');
        wg.position.set(x, 0, z); wg.rotation.y = ry;
        g.stage.scene.add(wg);
        w.wagon = { x, z, obj: wg, door: { x, z: z + 2 } };
      });
    }

    // 무덤 (장례 때와 같은 자리)
    pp.graves = Math.max(0, Math.min(200, num(d.graves) | 0));
    if (w.hall) this.part('무덤', () => { for (let k = 0; k < pp.graves; k++) { const gp = w.hall.toWorld(w.hall.size[0] / 2 + 6, -w.hall.size[1] / 2 + k * 1.4); w.makeGrave(gp.x, gp.z, w.hall.rot); } });

    // 봉화 불꽃 (모습만: 소식·봄으로 넘기기·축제는 다시 하지 않는다)
    for (const b of lit) this.part('봉화 불꽃', () => this.quiet(() => g.lightBeacon(b, true)));

    // 이웃 마을
    const rv = g.rival, rd2 = obj(d.rival), rh = arr(rd2.home);
    rv.beacon = num(rd2.b); rv.lit = !!rd2.lit; rv.step = num(rd2.st) | 0; rv.t = num(rd2.t);
    if (rh.length >= 2 && fin(rh[0]) && fin(rh[1])) rv.home = { x: rh[0], z: rh[1] };
    rv.hall = byId.get(rd2.hall) || w.blds.find((b) => b.ai && b.def.kind === 'hq') || null;
    if (rv.hall && !rv.home) rv.home = { x: rv.hall.x, z: rv.hall.z };

    // 경제
    const e = g.econ, ed = obj(d.econ);
    e.coins = Math.max(0, num(ed.coins) | 0);
    refill(e.decos, nums(ed.decos));
    e.buffs.length = 0; e.buffs.push(...arr(ed.buffs).filter((b) => b && typeof b === 'object' && b.buff && typeof b.buff === 'object'));
    e.daysSince = num(ed.ds) | 0;
    e.earned = num(ed.earned) | 0;
    g.won = !!d.won;

    // 주민
    const pById = new Map(), pDat = [];
    for (const pd of arr(P.list)) {
      const p = await this.partAsync('주민', () => this.restorePerson(pd, byId));
      if (!p) continue;
      pById.set(pd.i, p); pDat.push([p, pd]);
    }
    for (const [p, pd] of pDat) {
      this.part('주민 사이', () => {
        p.spouse = pById.get(pd.sp) || null;
        p.partner = pById.get(pd.pa) || null;
        p.parents = arr(pd.par).map((id) => pById.get(id)).filter(Boolean);
      });
    }
    pp.log.length = 0; pp.log.push(...arr(P.log).filter((x) => x && typeof x === 'object' && typeof x.text === 'string'));
    pp.offerDays = num(P.od);
    pp.eventQueue.length = 0;
    for (const x of arr(P.q)) {
      const ev = this.part('행사', () => {
        if (!x || typeof x !== 'object' || !EVENT_NEED[x.k]) throw new Error('모르는 행사');
        const o = { kind: x.k };
        for (const f of PERSON_REFS) if (x[f] != null) { o[f] = pById.get(x[f]); if (!o[f]) return null; }   // 그 사람이 없으면 행사도 없다
        for (const f of EVENT_NEED[x.k]) if (!o[f]) return null;
        const at = arr(x.at);
        if (at.length >= 2 && fin(at[0]) && fin(at[1])) o.at = { x: at[0], z: at[1] };
        if (x.k === 'festival' && !o.at) { if (!w.hall) return null; o.at = w.hall.door; }
        return o;
      });
      if (ev) pp.eventQueue.push(ev);
    }

    // 번호 이어 쓰기 (다시 만들면서 붙은 임시 번호 말고, 실제로 쓰는 번호 다음부터)
    let wn = num(W.nid, 1);
    for (const o of w.nature.values()) wn = Math.max(wn, o.id + 1);
    for (const b of w.blds) wn = Math.max(wn, b.id + 1);
    w.nid = wn;
    let pn = num(P.nid, 1);
    for (const p of pp.list) pn = Math.max(pn, p.id + 1);
    pp.nid = pn;
    let rn = num(RD.nid, 1);
    for (const n of R.nodes.values()) rn = Math.max(rn, n.id + 1);
    for (const ed2 of R.edges.values()) rn = Math.max(rn, ed2.id + 1);
    R.nid = rn;

    // 상인 (오늘 머물던 상인은 그대로)
    const md = ed.merchant;
    if (md && typeof md === 'object' && Array.isArray(md.offers) && w.hall) {
      await this.partAsync('상인', async () => {
        await this.quietAsync(() => e.arrive());
        if (e.merchant) {
          e.merchant.offers = md.offers.filter(okOffer);
          if (e.merchant.offers.length < md.offers.length) this.skip('상인 물건', `${md.offers.length - e.merchant.offers.length}개`);
          e.merchant.until = num(md.until, e.merchant.until);
          if (fin(md.ry) && e.merchant.sled) e.merchant.sled.rotation.y = md.ry;   // 수레 방향도 그대로
        }
      });
    }

    // 마을회관을 다 지었는데 이웃 마을이 아직 없으면 (그 순간에 저장된 경우) 지금 세운다
    if (hallUp && !rv.hall) {
      const S = NUM.mapSize, b = w.hall, rx = b.x < S / 2 ? S * 0.82 : S * 0.18, rz = b.z < S / 2 ? S * 0.8 : S * 0.2;
      await rv.found(rx, rz);
    }

    // 일 다시 나누기: 짓는 중인 마을회관은 모두가, 이주민 오두막은 그 집 사람들이 (나머지 일은 저절로 나눠진다)
    if (w.hall && w.hall.con) pp.settle(w.hall);
    for (const b of w.blds) {
      if (!b.con || b.con.kind !== 'build' || b.ai || !b.free || b === w.hall) continue;
      for (const p of pp.list) if (p.home === b && p.stage === 'adult' && !p.ai && !p.job) { p.job = { kind: 'builder', bld: b, x: b.x, z: b.z }; b.builders.push(p); }
    }
    // 일터마다 일하던 사람을 다시 붙인다 (안 그러면 나르기가 먼저 나눠져서 한동안 일터가 빈다)
    for (const [b, id] of wrOf) {
      const p = pp.list.find((q) => q.id === id);
      if (!p || p.dead || p.ai || p.stage !== 'adult' || p.job || b.dead || b.state !== 'active' || b.worker) continue;
      p.job = { kind: 'worker', bld: b, x: b.x, z: b.z }; b.worker = p;
    }

    // 이주민 제안이 떠 있었으면 다시 보여 준다
    const of = P.offer;
    const ofPpl = of && typeof of === 'object' && Array.isArray(of.ppl) ? of.ppl.filter(okNewcomer) : [];
    if (of && ofPpl.length < arr(of.ppl).length) this.skip('이주민 제안 속 사람', `${arr(of.ppl).length - ofPpl.length}명`);
    if (ofPpl.length) this.part('이주민 제안', () => { pp.offer = Object.assign({}, of, { ppl: ofPpl }); try { w.emit('offer', pp.offer); } catch (err) { pp.offer = null; throw err; } });

    // 다른 기능 상태
    for (const k of EXT) {
      const m = g[k];
      if (d.ext && d.ext[k] !== undefined && m && typeof m.loadData === 'function') {
        try { await m.loadData(d.ext[k]); } catch (err) { console.warn('load ext', k, err); }
      } else if (d.plain && d.plain[k] && m && typeof m.loadData !== 'function') {
        try { applyPlain(m, d.plain[k]); } catch (err) { console.warn('load plain', k, err); }
      }
    }

    // 화면
    g.speed = 1;
    const cam = arr(d.cam), camOk = cam.length === 5 && cam.every(fin);
    if (camOk) { const gl = g.stage.goal; [gl.tx, gl.tz, gl.dist, gl.yaw, gl.pitch] = cam; g.stage.applyCamera(true); }
    else if (w.hall) { g.stage.centerOn(w.hall.x, w.hall.z + 2, 40); g.stage.applyCamera(true); }
    g.territory.dirty = true;
    if (!w.hall) {
      if (!w.wagon) {   // 마차도 마을회관도 없으면 처음 자리에 마차를 다시 둔다
        await lib.loadProp('trade_post');
        const wg = lib.prop('trade_post'); wg.position.set(w.start.x, 0, w.start.z); wg.rotation.y = 0.5; g.stage.scene.add(wg);
        w.wagon = { x: w.start.x, z: w.start.z, obj: wg, door: { x: w.start.x, z: w.start.z + 2 } };
      }
      if (!camOk) { g.stage.centerOn(w.start.x, w.start.z + 2, 30); g.stage.applyCamera(true); }
      g.setMode('settle');
    } else g.setMode('view');
    g.hud.fillTools(); g.hud.refresh();
    w.emit('stock');

    // 점검 (시험용): 아무도 옛 일·자리·건물 안을 붙잡고 있지 않은지
    const L = pp.list;
    this.report = {
      people: L.length, blds: w.blds.length, nature: w.nature.size, roads: R.edges.size, skipped: this.skipped,
      tasks: w.tasks.length, jobs: L.filter((p) => p.job).length,
      stale: L.filter((p) => p.slot || p.inside || p.sleepAt || p.q.length || p.cur || p.carry || p.chatting || p.event || p.hidden).length,
    };
  }

  /** 주민 한 명 (망가진 값이면 만들다 만 사람을 치우고 오류를 던진다 → 이 사람만 건너뜀) */
  async restorePerson(pd, byId) {
    const g = this.g, pp = g.people, lib = g.lib;
    if (!pd || typeof pd !== 'object' || !fin(pd.i) || !fin(pd.x) || !fin(pd.z)) throw new Error('주민 값이 틀림');
    if (pp.list.some((q) => q.id === pd.i)) throw new Error('같은 번호의 주민');
    const look = str(pd.lk);
    if (look) { try { await lib.loadChar(look); } catch (err) { /* 없는 모습이면 기본 모습 */ } }
    const stage = STAGES.includes(pd.st) ? pd.st : 'adult';
    const p = pp.makePerson({
      x: pd.x, z: pd.z, gender: pd.g === 'f' ? 'f' : 'm', stage, look, name: str(pd.n),
      trait: typeof pd.tr === 'string' && TRAITS[pd.tr] ? pd.tr : undefined, age: fin(pd.a) ? Math.max(0, Math.round(pd.a)) : undefined,
    });
    try {
      p.id = pd.i; p.yaw = num(pd.y);
      p.energy = num(pd.e, 1); p.mood = num(pd.m, 0.65);
      p.hungry = !!pd.h; p.joy = num(pd.j);
      p.ai = !!pd.ai;
      if (pd.spc) p.special = true;
      if (fin(pd.md)) p.marriedDay = pd.md;
      if (pd.wp) p.weddingPlanned = true;
      p.coldNight = !!pd.cold;
      if (Array.isArray(pd.ate)) p.ate = new Set(pd.ate.filter((x) => typeof x === 'string'));
      p.friends = new Map(pairs(pd.fr));
      p.romance = new Map(pairs(pd.ro));
      p.home = pd.home != null ? byId.get(pd.home) || null : null;
      // 첫 프레임 전(멈춤 상태)에도 제자리에 보이게
      if (p.doll) { p.doll.root.position.set(p.x, 0, p.z); p.doll.root.rotation.y = p.yaw; try { p.doll.update(0.2); } catch (err) { /* 자세는 첫 프레임에 잡힌다 */ } }
    } catch (err) {
      for (const dl of Object.values(p.dolls || {})) g.stage.scene.remove(dl.root);
      const k = pp.list.indexOf(p); if (k >= 0) pp.list.splice(k, 1);
      throw err;
    }
    return p;
  }

  /** 건물 하나 (망가진 값이면 만들다 만 건물을 치우고 오류를 던진다 → 이 건물만 건너뜀) */
  async restoreBuilding(bd) {
    const g = this.g, w = g.world;
    if (!bd || typeof bd !== 'object') throw new Error('건물 값이 틀림');
    const def = BUILDINGS[bd.k];
    if (!def) { console.warn('save: unknown building', bd.k); return null; }
    if (!fin(bd.i) || !fin(bd.x) || !fin(bd.z) || w.blds.some((x) => x.id === bd.i)) throw new Error('건물 자리·번호가 틀림');
    const b = new Building(w, bd.k, bd.x, bd.z, num(bd.r), { free: !!bd.f });
    w.blds.push(b);
    try {
      await this.fillBuilding(b, bd, def);
    } catch (err) {
      this.dropBuilding(b);
      throw err;
    }
    w.emit('bld', b);
    return b;
  }

  async fillBuilding(b, bd, def) {
    const g = this.g, w = g.world;
    b.id = bd.i;
    b.ai = !!bd.ai;
    if (def.levels) b.level = Math.max(0, Math.min(def.levels.length - 1, num(bd.l) | 0));
    const con = (c0) => {
      const c = obj(c0);
      return {
        kind: c.k === 'upgrade' ? 'upgrade' : 'build', need: nums(c.n), have: nums(c.h), used: nums(c.u),
        work: Math.max(0, num(c.w)), workNeeded: num(c.W) > 0 ? c.W : def.work || 8,
      };
    };
    if (bd.s !== 'a') {
      // 공사 현장: 터·비계·재료 더미, 올라간 만큼
      b.state = 'site';
      await b.buildVisual();
      b.startSite();
      if (bd.c) b.con = con(bd.c);
      b.pileKey = null; b.updatePile();
      b.setProgress(Math.min(1, b.con.work / Math.max(1e-6, b.con.workNeeded)));
    } else {
      b.state = 'active';
      await b.buildVisual();
      if (bd.c && bd.c.k === 'upgrade' && def.levels && def.levels[b.level + 1]) {
        b.con = con(bd.c);
        b.makeSiteVisual();
        if (b.scaffold) b.scaffold.visible = true;
        b.pileKey = null; b.updatePile();
      }
    }
    b.inputs = Math.max(0, num(bd.in));
    b.out = Math.max(0, num(bd.o) | 0);
    b.working = !!bd.wk;
    b.t = num(bd.t);
    if (b.state === 'active') {
      for (const row of arr(bd.pl)) {
        if (!Array.isArray(row) || !fin(row[0]) || !fin(row[1])) { this.skip('밭', null); continue; }
        const [x, z, st, t] = row;
        const p = w.addPlot(b, x, z);
        if (fin(st) && st > 0) w.setPlotStage(p, Math.min(3, st | 0));
        p.t = num(t);
      }
      if (def.kind === 'ranch') {
        decorate(b, w);
        await g.herds.spawn(b);
        const an = arr(bd.an);
        (b.animals || []).forEach((a, k) => {
          const s = an[k]; if (!Array.isArray(s)) return;
          a.x = num(s[1], a.x); a.z = num(s[2], a.z); a.yaw = num(s[3], a.yaw); a.ready = !!s[4]; a.prod = num(s[5]);
          if (a.doll) { a.doll.root.position.set(a.x, 0, a.z); a.doll.root.rotation.y = a.yaw; }
        });
      }
      if (def.kind === 'orchard') {
        decorate(b, w);
        arr(bd.tr).forEach((row, k) => { const tr = b.trees && b.trees[k]; if (!tr || !Array.isArray(row)) return; tr.t = num(row[0]); tr.ready = !!row[1]; if (tr.fruit) tr.fruit.visible = tr.ready; });
      }
      if (def.out && b.out) b.updateOutPile();
      if (bd.pin) { b.pinned = true; b.setCutaway(true); }
    }
  }

  /** 만들다 만 건물 치우기 (불러오다 망가진 값을 만났을 때) */
  dropBuilding(b) {
    const g = this.g, w = g.world;
    b.dead = true;
    try { for (const p of b.plots) w.removePlot(p); } catch (e) { /* */ }
    try { g.herds.remove(b); } catch (e) { /* */ }
    try { if (b.bees) for (const e of b.bees) w.stage.scene.remove(e.m); } catch (e) { /* */ }
    try { b.dispose(); } catch (e) { /* */ }
    const k = w.blds.indexOf(b); if (k >= 0) w.blds.splice(k, 1);
  }

  /** 소식 없이 실행 (봉화 불꽃·상인을 다시 놓을 때) */
  quiet(fn) { const pp = this.g.people, nw = pp.news; pp.news = () => {}; try { fn(); } finally { pp.news = nw; } }
  async quietAsync(fn) { const pp = this.g.people, nw = pp.news; pp.news = () => {}; try { await fn(); } finally { pp.news = nw; } }

  hasSave() { return !!parseSave(store.get(KEY) || ''); }

  // ================================================================ 시험용
  /** 자동 시험용 함수 등록 */
  api(obj) {
    obj.save = () => this.save();
    obj.load = () => {
      if (!this.hasSave()) return false;
      try { window.sessionStorage.setItem(AUTOLOAD, '1'); } catch (e) { /* 막혀 있으면 새로고침 뒤 물어본다 */ }
      setTimeout(() => location.reload(), 30);
      return true;
    };
    obj.hasSave = () => this.hasSave();
    obj.clearSave = () => store.del(KEY);
    obj.saveSize = () => { const s = store.get(KEY); return s ? s.length : 0; };
    obj.loadReport = () => this.report;
    obj.autoSaves = () => this.autoN;
  }
}

// ---------------------------------------------------------------- 도우미
function parseSave(raw) {
  if (!raw || typeof raw !== 'string') return null;
  let d;
  try { d = JSON.parse(raw); } catch (e) { return null; }
  if (!d || typeof d !== 'object' || d.v !== VER) return null;
  if (!d.clock || !d.w || !d.w.stock || !Array.isArray(d.blds) || !d.ppl || !Array.isArray(d.ppl.list) || !d.roads || !Array.isArray(d.roads.nodes) || !Array.isArray(d.roads.edges)) return null;
  if (!d.nat || !Array.isArray(d.nat.rows)) return null;
  return d;
}

function sumText(s) {
  return `${s.year || 1}년 ${s.season || SEASONS[0].name} ${s.day || 1}일 · 주민 ${s.pop || 0}명`;
}

function ago(t) {
  const s = (Date.now() - t) / 1000;
  if (!(s >= 0)) return '';
  if (s < 60) return '방금 전';
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}

/** 객체를 바꿔 끼우지 않고 안의 값만 새로 채운다 */
function refill(obj, src) { for (const k of Object.keys(obj)) delete obj[k]; Object.assign(obj, src || {}); }

function setLoadText(t) { const e = document.getElementById('sm-loading-txt'); if (e) e.textContent = t; }
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function injectCss() {
  if (document.getElementById('smsv-css')) return;
  const st = document.createElement('style');
  st.id = 'smsv-css';
  st.textContent = `
.smsv { margin-top: 4px; width: min(360px, calc(100vw - 32px)); padding: 16px 18px 14px; border-radius: 20px; background: rgba(255,255,255,.96);
  box-shadow: 0 8px 26px rgba(40,50,80,.18); display: flex; flex-direction: column; gap: 9px; text-align: center; animation: smsvIn .35s ease-out; }
.smsv-t { font-size: 18px; font-weight: 900; color: #2b2f3a; }
.smsv-s { font-size: 12.5px; font-weight: 700; color: #5d6b80; margin-top: -5px; }
.smsv button { border: 0; border-radius: 14px; padding: 12px 14px; font-family: inherit; font-size: 17px; font-weight: 900; color: #fff; cursor: pointer;
  background: #3d8be0; box-shadow: 0 3px 0 #2c6db8; transition: transform .08s; }
.smsv button:active { transform: translateY(2px); box-shadow: 0 1px 0 #2c6db8; }
#sm-loading .smsv button small, .smsv button small { display: block; margin-top: 3px; font-size: 13px; font-weight: 700; color: inherit; opacity: .92; }
.smsv button.smsv-new { background: #eef1f6; color: #4a5568; box-shadow: 0 3px 0 #d3d9e3; font-size: 14.5px; padding: 10px; }
.smsv button.smsv-del { background: #e2574a; box-shadow: 0 3px 0 #b8432f; }
@keyframes smsvIn { from { opacity: 0; transform: translateY(10px) scale(.97); } to { opacity: 1; transform: none; } }
@media (max-height: 420px) { .smsv { padding: 12px 14px 10px; gap: 7px; } .smsv button { padding: 9px 12px; font-size: 15.5px; } }`;
  document.head.appendChild(st);
}
