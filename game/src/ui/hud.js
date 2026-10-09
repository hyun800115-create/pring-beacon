// 화면 위 메뉴 (HTML): 시간·속도, 창고, 소식, 할 일, 분류별 건축 메뉴, 카메라 버튼, 정보 카드, 이주민 팝업, 알림.

import { BUILDINGS, BUILD_MENU, CATEGORIES, ITEMS, ITEM_ORDER, NUM, ROADS, ROAD_ORDER, CARDS, CARD_COST, DECOS } from '../game/defs.js';
import { josa } from '../core/josa.js';

const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ITEM_EMOJI = { log: '🪵', plank: '🟫', stone: '🪨', wheat: '🌾', flour: '🥡', bread: '🍞', fish: '🐟', egg: '🥚', milk: '🥛', cheese: '🧀', wool: '🧶', meat: '🍖', apple: '🍎', honey: '🍯' };
export const costText = (c) => (c ? Object.keys(c).map((t) => `${ITEMS[t].name}${c[t]}`).join(' ') : '');

export class Hud {
  constructor(game) {
    this.g = game;
    this.root = document.getElementById('hud');
    this.root.innerHTML = '';
    this.t = 0;
    this.cat = 'house';
    this.thumbs = {};
    this.build();
    this.refresh();
  }

  build() {
    const r = this.root, g = this.g;
    const top = el('div', 'top');
    this.clockEl = el('div', 'clock panel pe');
    this.clockTxt = el('span');
    this.clockEl.appendChild(this.clockTxt);
    const sp = el('span', 'speed');
    this.speedBtns = [0, 1, 2, 3].map((v) => {
      const b = el('button', '', v === 0 ? '⏸' : '▶'.repeat(v));
      b.title = v === 0 ? '멈춤' : `${v}배속`;
      b.onclick = () => { g.speed = v; this.refresh(); };
      sp.appendChild(b); return b;
    });
    this.clockEl.appendChild(sp);
    this.stockEl = el('div', 'stock panel');
    this.chips = {};
    for (const t of ITEM_ORDER) {
      const c = el('div', 'chip');
      c.title = ITEMS[t].name;
      c.innerHTML = `<span style="font-size:17px">${ITEM_EMOJI[t]}</span><span>0</span>`;
      this.stockEl.appendChild(c); this.chips[t] = c;
    }
    this.rightEl = el('div', 'right panel pe');
    this.rightTxt = el('span');
    this.rightEl.appendChild(this.rightTxt);
    this.coinEl = el('span', '', '🪙 0');
    this.coinEl.style.cssText = 'font-weight:900;color:#a8770c';
    this.rightEl.appendChild(this.coinEl);
    const card = el('button', 'sysb', '🎴 카드');
    card.title = '코인으로 카드 뽑기';
    card.onclick = () => this.cardModal();
    this.rightEl.appendChild(card);
    this.merchBtn = el('button', 'sysb', '🧳 상인');
    this.merchBtn.title = '외부 상인 가게';
    this.merchBtn.style.background = '#ffe7a8';
    this.merchBtn.onclick = () => this.merchantModal();
    this.rightEl.appendChild(this.merchBtn);
    const snd = el('button', 'sysb', '🔊');
    snd.title = '소리 켜기/끄기';
    snd.onclick = () => { g.audio.setOn(!g.audio.on); snd.textContent = g.audio.on ? '🔊' : '🔇'; };
    this.rightEl.appendChild(snd);
    this.sndBtn = snd;
    top.append(this.clockEl, this.stockEl, this.rightEl);
    r.appendChild(top);

    this.newsEl = el('div', 'news'); r.appendChild(this.newsEl);
    this.goalEl = el('div', 'goal panel'); this.goalEl.style.bottom = 'calc(150px + env(safe-area-inset-bottom, 0px))'; r.appendChild(this.goalEl);

    // 아래: 분류 탭 + 도구
    this.dock = el('div', 'dock');
    this.catBar = el('div', 'cats');
    this.catBtns = CATEGORIES.map((c) => {
      const b = el('button', 'cat pe', `${c.icon} ${c.name}`);
      b.onclick = () => { this.cat = c.key; this.fillTools(); this.refresh(); };
      this.catBar.appendChild(b); b.dataset.k = c.key; return b;
    });
    this.bar = el('div', 'bar panel pe');
    this.dock.append(this.catBar, this.bar);
    r.appendChild(this.dock);
    this.fillTools();

    // 카메라 버튼
    const cam = el('div', 'camctl panel pe');
    const btn = (t, title, fn) => { const b = el('button', '', t); b.title = title; b.onclick = fn; cam.appendChild(b); };
    btn('＋', '확대', () => g.stage.zoomBy(0.78));
    btn('－', '축소', () => g.stage.zoomBy(1.28));
    btn('⟲', '왼쪽으로 돌리기', () => g.stage.rotateBy(Math.PI / 4));
    btn('⟳', '오른쪽으로 돌리기', () => g.stage.rotateBy(-Math.PI / 4));
    btn('⬆', '위에서 보기', () => { g.stage.goal.pitch = g.stage.goal.pitch > 1.2 ? 0.84 : 1.4; });
    btn('🏛', '마을회관으로', () => { const h = g.world.hall || g.world.wagon; if (h) g.stage.centerOn(h.x, h.z, 34); });
    r.appendChild(cam);

    // 건물 놓을 때 돌리기
    this.placeBar = el('div', 'placebar panel pe');
    this.placeBar.innerHTML = '<button data-a="l">⟲ 돌리기</button><span class="pn"></span><button data-a="r">돌리기 ⟳</button><button data-a="ok" class="go">✔ 짓기</button><button data-a="x">취소</button>';
    this.okBtn = this.placeBar.querySelector('[data-a=ok]');
    this.okBtn.onclick = () => g.confirmPlace();
    this.placeBar.querySelector('[data-a=l]').onclick = () => g.rotatePlacing(Math.PI / 8);
    this.placeBar.querySelector('[data-a=r]').onclick = () => g.rotatePlacing(-Math.PI / 8);
    this.placeBar.querySelector('[data-a=x]').onclick = () => g.setMode('view');
    r.appendChild(this.placeBar);

    this.promptEl = el('div', 'prompt panel'); r.appendChild(this.promptEl);
    this.cardEl = el('div', 'card panel pe'); this.cardEl.style.display = 'none'; r.appendChild(this.cardEl);
    this.toastEl = el('div', 'toast'); this.toastEl.style.opacity = 0; r.appendChild(this.toastEl);
    this.modalEl = el('div', 'modal panel pe'); this.modalEl.style.display = 'none'; r.appendChild(this.modalEl);
  }

  fillTools() {
    const g = this.g;
    this.bar.innerHTML = '';
    const tools = [{ m: 'view', em: '👆', nm: '보기' }];
    if (this.cat === 'road') tools.push({ m: 'road', em: '🛤️', nm: '흙길 그리기', co: '끌어서 그리기' });
    else if (this.cat === 'deco') {
      const inv = Object.entries(g.econ ? g.econ.decos : {}).filter(([, n]) => n > 0);
      for (const [k, n] of inv) tools.push({ m: 'deco:' + k, key: k, em: '🌷', nm: DECOS[k].name, co: `${n}개 있음` });
      if (!inv.length) tools.push({ m: 'view', em: '🧳', nm: '장식 없음', co: '상인·카드로 얻기' });
    }
    else for (const t of BUILD_MENU[this.cat] || []) tools.push({ m: 'build:' + t, key: t, em: BUILDINGS[t].icon || '🏠', nm: BUILDINGS[t].name, co: costText(BUILDINGS[t].cost) });
    tools.push({ m: 'remove', em: '🧹', nm: '없애기' });
    this.toolBtns = [];
    for (const t of tools) {
      const b = el('button', 'tool');
      const img = t.key && this.thumbs[t.key] ? `<img alt="" src="${this.thumbs[t.key]}">` : `<span class="em">${t.em}</span>`;
      b.innerHTML = img + `<span class="nm">${esc(t.nm)}</span>` + (t.co ? `<span class="co">${esc(t.co)}</span>` : '');
      b.onclick = () => { if (g.mode === 'settle') { this.toast('먼저 마을회관 자리를 정해 주세요', true); return; } g.setMode(g.mode === t.m ? 'view' : t.m); };
      b.dataset.m = t.m;
      this.bar.appendChild(b); this.toolBtns.push(b);
    }
  }
  setThumb(key, url) { this.thumbs[key] = url; this.fillTools(); this.refresh(); }

  refresh() {
    const g = this.g;
    this.speedBtns.forEach((b, v) => b.classList.toggle('on', g.speed === v));
    for (const b of this.toolBtns) b.classList.toggle('on', b.dataset.m === g.mode);
    for (const b of this.catBtns) b.classList.toggle('on', b.dataset.k === this.cat);
    // 손가락 화면: 땅을 누르면 미리 보기가 옮겨지고 ✔ 로 짓는다 (마우스는 누르면 바로 짓기)
    const m = g.mode, touch = !!(g.touchy && g.touchy());
    const prompts = {
      settle: touch ? '🛷 마차가 도착했어요! 마을회관 자리를 누르고 ✔ 짓기를 눌러 주세요' : '🛷 마차가 도착했어요! 주변에 마을회관을 세울 곳을 눌러 주세요 (Q·E 또는 ⟲⟳ 로 방향 돌리기)',
      road: '🛤️ 땅을 누른 채 끌면 그린 대로 길이 생겨요. 다른 길이나 건물 문 앞에 이어 주세요',
      remove: '🧹 없앨 길이나 건물을 눌러 주세요',
    };
    let p = prompts[m] || '', cost = '', ok = '✔ 짓기';
    if (m.startsWith('build:')) {
      const d = BUILDINGS[m.slice(6)];
      p = `🏗️ ${d.name}을(를) 놓을 곳을 ${touch ? '누르고 ✔ 짓기' : '눌러 주세요'} · 노란 화살표가 정문이에요`;
      cost = costText(d.cost);
    }
    if (m.startsWith('deco:')) {
      const k = m.slice(5);
      p = `🌷 ${DECOS[k] ? DECOS[k].name : '장식'}을(를) 놓을 곳을 ${touch ? '누르고 ✔ 놓기' : '눌러 주세요'}`;
      cost = `${(g.econ && g.econ.decos[k]) || 0}개 있음`; ok = '✔ 놓기';
    }
    if (m.startsWith('move:')) { p = `↔ ${g.moving ? g.moving.name : '건물'}을(를) 옮길 곳을 ${touch ? '누르고 ✔ 옮기기' : '눌러 주세요 (Q·E 로 돌리기)'}`; ok = '✔ 옮기기'; }
    this.promptEl.textContent = josa(p);
    this.promptEl.style.display = p ? '' : 'none';
    this.root.classList.toggle('prompting', !!p);   // 좁은 화면: 안내 띠가 있는 동안은 같은 줄의 소식을 숨긴다
    const placing = m === 'settle' || m.startsWith('build:') || m.startsWith('deco:') || m.startsWith('move:');
    this.placeBar.style.display = placing ? '' : 'none';
    this.placeBar.querySelector('.pn').textContent = cost;
    this.okBtn.textContent = ok;
    this.okBtn.style.display = touch ? '' : 'none';
    this.root.classList.toggle('placing', placing);
    this.dock.style.display = g.mode === 'settle' ? 'none' : '';
  }

  tick(dt) {
    this.t += dt;
    if (this.t < 0.25) return;
    this.t = 0;
    const g = this.g, w = g.world, c = g.clock, ppl = g.people;
    this.clockTxt.innerHTML = `<span class="yr">${c.year}년 </span><span class="sea">${c.season.name} ${c.dayOfSeason}일</span> · ${c.timeText} ${c.phase === 'night' ? '🌙' : c.phase === 'evening' ? '🌇' : '☀️'}`;
    for (const t of ITEM_ORDER) { const v = Math.max(0, Math.floor(w.stock[t] || 0)); this.chips[t].lastChild.textContent = v; this.chips[t].style.display = v > 0 || ['log', 'plank', 'stone', 'bread', 'fish'].includes(t) ? '' : 'none'; }
    this.coinEl.textContent = `🪙 ${g.econ.coins}`;
    this.merchBtn.style.display = g.econ.merchant ? '' : 'none';
    const alive = ppl.list.filter((p) => !p.dead && !p.ai);   // 우리 마을 사람만 (이웃 서리골 주민은 빼고)
    const homes = w.blds.filter((b) => b.def.kind === 'house' && b.state === 'active' && !b.ai);
    const cap = homes.reduce((a, b) => a + b.def.levels[b.level].cap, 0);
    const idle = alive.filter((p) => p.stage === 'adult' && !p.job).length;
    let txt = `👥 ${alive.length}명<span class="ex"> · 🏠 ${cap}칸 · 🙋 쉬는 사람 ${idle}</span>`;
    const food = (w.stock.bread || 0) + (w.stock.fish || 0);
    if (food < alive.length * NUM.foodPerDay * 2) txt += ' · <span style="color:#c43e30">🍞 부족</span>';
    if (g.rival && g.rival.hall) txt += `<span class="ex"> · 🏘️ 서리골 봉화 ${Math.round(g.rival.beacon * 100)}%</span>`;
    if (g.showFps) txt += ` · ${Math.round(g.fps)}fps`;
    this.rightTxt.innerHTML = txt;
    this.updateGoals();
    if (this.cardFn) this.cardFn();
    for (const d of [...this.newsEl.children]) if (performance.now() - d.__t > 12000) { d.style.opacity = 0; setTimeout(() => d.remove(), 700); d.__t = Infinity; }
    this.fitLayout();
  }

  /** 자원 줄이 두 줄로 늘면 소식·카드·안내 띠를 그 아래로 내리고, 소식은 '할 일' 판에 가리지 않을 만큼만 보인다 */
  fitLayout() {
    const sb = Math.ceil(this.stockEl.getBoundingClientRect().bottom + 6);
    if (sb !== this.stockB) { this.stockB = sb; this.root.style.setProperty('--below-stock', sb + 'px'); }
    this.fitNews();
  }
  fitNews() {
    const n = this.newsEl;
    if (n.children.length < 2 || !n.offsetParent) return;
    const gr = this.goalEl.getBoundingClientRect(), nr = n.getBoundingClientRect();
    const lim = Math.min(gr.height ? gr.top - 6 : Infinity, nr.bottom + 0.5);   // 할 일 판 위, (좁은 화면) 소식 칸 높이 안
    while (n.children.length > 1 && n.lastChild.getBoundingClientRect().bottom > lim) n.lastChild.remove();
  }

  updateGoals() {
    const w = this.g.world;
    const has = (t) => w.blds.some((b) => b.type === t && b.state === 'active');
    const houses = w.blds.filter((b) => b.def.kind === 'house' && b.state === 'active').length;
    const g = [
      ['마을회관 세우기', has('hall')],
      ['오두막 2채 짓기', houses >= 2],
      ['길 이어 그리기', w.roads.edges.size >= 2],
      ['나무꾼 작업장·제재소로 판자 만들기', has('woodcutter') && has('sawmill')],
      ['채석장에서 돌 캐기', has('quarry')],
      ['밀 농장 → 풍차 → 빵집 잇기', has('farm') && has('windmill') && has('bakery')],
      ['선술집에서 저녁 모임', has('tavern')],
      ['목축: 닭장이나 외양간 짓기', has('coop') || has('barn')],
      ['화톳불 망루로 땅 넓히기', has('watchtower')],
      [this.g.won ? '봄의 봉화를 서리골보다 먼저 밝히기 🏆' : '봄의 봉화 밝히기', w.blds.some((b) => b.type === 'beacon' && !b.ai && b.state === 'active')],
    ];
    const html = '<b>📋 할 일</b>' + g.map(([t, ok]) => `<div class="${ok ? 'ok' : 'no'}">${esc(t)}</div>`).join('');
    if (this.goalEl.__h !== html) { this.goalEl.innerHTML = html; this.goalEl.__h = html; }
  }

  news(text, kind) {
    const d = el('div', kind || 'info');
    d.textContent = josa(text); d.__t = performance.now();
    this.newsEl.prepend(d);
    while (this.newsEl.children.length > 5) this.newsEl.lastChild.remove();
    this.fitNews();
  }
  toast(msg, err) {
    const t = this.toastEl;
    t.textContent = josa(msg); t.className = 'toast' + (err ? ' err' : '');
    t.style.opacity = 1;
    clearTimeout(this.toastT);
    this.toastT = setTimeout(() => { t.style.opacity = 0; }, 2600);
  }

  // ---------------------------------------------------------------- 정보 카드
  closeCard() { this.cardEl.style.display = 'none'; this.root.classList.remove('carded'); this.cardFn = null; if (this.onClose) this.onClose(); this.onClose = null; }
  card(fn) {
    this.cardFn = () => { const h = fn(); if (h == null) { this.closeCard(); return; } if (this.cardEl.__h !== h) { this.cardEl.innerHTML = h; this.cardEl.__h = h; this.bindCard(); } };
    this.cardEl.style.display = ''; this.cardEl.__h = null; this.cardEl.scrollTop = 0;
    this.root.classList.add('carded');   // 휴대폰 가로 화면: 카드가 열린 동안은 아래 도구 막대를 접어 카드를 끝까지 보여 준다
    this.cardFn();
  }
  bindCard() {
    const x = this.cardEl.querySelector('.x'); if (x) x.onclick = () => this.closeCard();
    for (const b of this.cardEl.querySelectorAll('[data-act]')) b.onclick = () => this.g.act(b.dataset.act, this.sel);
  }

  showPerson(p) {
    this.sel = p;
    this.card(() => {
      if (p.dead) return null;
      const d = this.g.people.describe(p);
      return `<button class="x">✕</button><h3>${esc(d.name)}</h3><div class="sub">${esc(d.sub)}</div>` +
        `<table>${d.rows.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table>` +
        `<div class="btns"><button class="gray" data-act="follow">${this.g.follow === p ? '따라가기 그만' : '따라가 보기'}</button></div>`;
    });
  }

  showBuilding(b) {
    this.sel = b;
    this.card(() => {
      if (b.dead) return null;
      const w = this.g.world, def = b.def;
      const rows = [];
      if (b.con) {
        const pct = Math.round((b.con.work / b.con.workNeeded) * 100);
        const mats = Object.keys(b.con.need).map((t) => `${ITEMS[t].name} ${Math.min(b.con.have[t] || 0, b.con.need[t])}/${b.con.need[t]}`).join(', ') || '재료 필요 없음 (가져온 것으로)';
        rows.push([b.con.kind === 'upgrade' ? '업그레이드 중' : '공사 중', `${pct}%<div class="bar2"><i style="width:${pct}%"></i></div>`]);
        rows.push(['재료', mats]);
        rows.push(['일꾼', b.builders.length ? b.builders.map((p) => p.name).join(', ') : '<span style="color:#c43e30">기다리는 중 (일손 부족)</span>']);
      }
      if (b.state === 'active') {
        if (def.kind === 'house') {
          const res = this.g.people.list.filter((p) => !p.dead && p.home === b);
          rows.push(['사는 사람', `${res.length}/${def.levels[b.level].cap}명 ${res.map((p) => p.name).join(', ')}`]);
        } else if (def.kind === 'hq') {
          rows.push(['창고', ITEM_ORDER.map((t) => `${ITEMS[t].name} ${Math.floor(w.stock[t] || 0)}`).join(' · ')]);
        } else if (['gather', 'farm', 'process'].includes(def.kind)) {
          rows.push(['일꾼', b.worker ? b.worker.name : '<span style="color:#c43e30">없음 (일손 부족)</span>']);
          if (def.kind === 'process') rows.push(['재료', `${ITEMS[def.in].name} ${b.inputs}개`], ['만드는 것', `${ITEMS[def.out].name} ${b.working ? '(만드는 중)' : ''}`]);
          if (def.kind === 'farm') rows.push(['밭', `${b.plots.length}/${def.plots}칸, 다 익은 밭 ${b.plots.filter((p) => p.stage === 3).length}`]);
          if (def.kind === 'gather' && b.noRes) rows.push(['알림', `<span style="color:#c43e30">주변에 ${def.res === 'tree' ? '나무' : '바위'}가 없어요</span>`]);
          if (def.out) rows.push(['쌓인 결과물', `${ITEMS[def.out].name} ${b.out}개`]);
        } else if (def.kind === 'shop') rows.push(['손님', `${this.g.people.list.filter((p) => p.slot && p.slot.b === b).length}명`]);
        if (b.hasInterior) rows.push(['실내', b.slots.length ? `가구 자리 ${b.slots.length}곳` : '']);
      }
      let btns = '';
      if (b.hasInterior && b.state === 'active') btns += `<button data-act="inside">${b.pinned ? '🏠 지붕 덮기' : '🔍 실내 보기'}</button>`;
      if (def.kind === 'house' && b.state === 'active' && !b.con && !b.ai && def.levels[b.level + 1]) {   // 이웃 마을(서리골) 집은 고치거나 옮길 수 없다
        const nx = def.levels[b.level + 1];
        btns += `<button data-act="upgrade">⬆ ${esc(josa(nx.name + '(으)로'))} (${esc(costText(nx.cost))})</button>`;
      }
      if ((def.kind === 'house' || def.deco) && b.state === 'active' && !b.con && !b.ai) btns += `<button class="gray" data-act="move">↔ 옮기기</button>`;
      if (def.kind === 'beacon') rows.push(['봉화', b.state === 'active' ? '🔥 타오르는 중 · 봄이 왔어요' : '공사가 끝나면 봉화가 켜져요']);
      if (def.kind === 'ranch') { rows.push(['동물', `${(b.animals || []).length}마리, 거둘 것 ${(b.animals || []).filter((a) => a.ready).length}`]); if (def.feed) rows.push(['먹이', `${ITEMS[def.feed].name} ${Math.ceil(b.inputs)}개`]); }
      if (def.kind === 'orchard') rows.push([def.hives ? '벌통' : '나무', `${(b.trees || []).length}개, 다 익은 것 ${(b.trees || []).filter((t) => t.ready).length}`]);
      if (b.ai) rows.unshift(['마을', '🏘️ 이웃 마을 서리골']);
      if (def.kind !== 'hq' && !b.ai) btns += `<button class="red" data-act="remove">없애기</button>`;
      return `<button class="x">✕</button><h3>${def.icon || '🏛️'} ${esc(b.name)}</h3><div class="sub">${esc(def.desc)}</div>` +
        `<table>${rows.map(([a, c]) => `<tr><td>${esc(a)}</td><td>${c}</td></tr>`).join('')}</table><div class="btns">${btns}</div>`;
    });
  }

  showRoad(e) {
    this.sel = e;
    this.card(() => {
      if (!this.g.world.roads.edges.has(e.id)) return null;
      const r = ROADS[e.type];
      const i = ROAD_ORDER.indexOf(e.type), next = ROAD_ORDER[i + 1];
      let btns = '';
      if (next && !e.busy) {
        const nr = ROADS[next], n = Math.max(1, Math.ceil(e.len / nr.per));
        const cost = Object.fromEntries(Object.entries(nr.cost).map(([k, v]) => [k, v * n]));
        btns += `<button data-act="roadup">⬆ ${esc(josa(nr.name + '(으)로'))} (${esc(costText(cost))})</button>`;
      }
      btns += '<button class="red" data-act="roadrm">길 없애기</button>';
      return `<button class="x">✕</button><h3>🛤️ ${esc(r.name)}</h3><div class="sub">길이 ${e.len.toFixed(0)}m · 걷는 속도 ×${r.speed}${e.busy ? ' · 공사 중' : ''}</div>` +
        `<table><tr><td>길 종류</td><td>흙길 → 자갈길 → 돌길 순서로 좋아져요</td></tr></table><div class="btns">${btns}</div>`;
    });
  }

  merchantModal() {
    const e = this.g.econ, m = this.modalEl;
    if (!e.merchant) { this.toast('지금은 상인이 없어요. 며칠마다 찾아와요'); return; }
    const render = () => {
      const rows = e.merchant.offers.map((o, i) => `<div style="display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px solid #eef1f5;text-align:left${o.sold ? ';opacity:.45' : ''}">
        <span style="font-size:11px;background:#eef3f9;border-radius:6px;padding:2px 6px;white-space:nowrap">${esc(o.tag)}</span>
        <span style="flex:1"><b>${esc(e.offerName(o))}</b><br><small style="color:#5d6b80">${esc(e.offerDesc(o))}</small></span>
        <button data-i="${i}" ${o.sold ? 'disabled' : ''} style="margin:0;padding:7px 10px">${o.sold ? '팔림' : '🪙 ' + o.price}</button></div>`).join('');
      m.innerHTML = `<h2>🧳 외부 상인</h2><div style="color:#5d6b80;font-size:13px">내일 아침에 떠나요 · 가진 코인 🪙 ${e.coins}</div><div style="max-height:52vh;overflow:auto;margin:8px 0">${rows}</div><button class="gray" data-x="1">닫기</button>`;
      m.style.display = '';
      for (const b of m.querySelectorAll('button[data-i]')) b.onclick = () => { const err = e.buy(e.merchant.offers[+b.dataset.i]); if (err) this.toast(err, true); render(); this.fillTools(); };
      m.querySelector('[data-x]').onclick = () => { m.style.display = 'none'; };
    };
    render();
  }

  cardModal() {
    const e = this.g.econ, m = this.modalEl;
    const odds = CARDS.map((c) => `<tr><td>${esc(c.name)}</td><td style="text-align:right">${(c.rate * 100).toFixed(0)}%</td><td style="color:#5d6b80;font-size:12px">${esc(c.desc)}</td></tr>`).join('');
    const show = (res) => {
      const card = res ? `<div style="margin:10px auto;width:180px;padding:16px 10px;border-radius:16px;background:linear-gradient(160deg,#fff4d6,#ffd9e6);box-shadow:0 6px 18px rgba(0,0,0,.15);animation:smflip .5s ease-out">
          <div style="font-size:12px;color:#8a6a2a;font-weight:800">${esc(res.card.name)}</div><div style="font-size:20px;font-weight:900;margin:6px 0">${esc(res.title)}</div><div style="font-size:12.5px">${esc(res.desc)}</div></div>` : '';
      m.innerHTML = `<style>@keyframes smflip{from{transform:rotateY(90deg) scale(.6)}to{transform:none}}</style><h2>🎴 카드 뽑기</h2>
        <div style="font-size:13px;color:#5d6b80">한 번에 🪙 ${CARD_COST} · 가진 코인 🪙 ${e.coins}</div>${card}
        <table style="margin:8px auto;font-size:13px;border-collapse:collapse"><tr><th colspan="3" style="text-align:left;padding-bottom:4px">나올 확률 (공개)</th></tr>${odds}</table>
        <button data-d="1">뽑기 (🪙 ${CARD_COST})</button><button class="gray" data-x="1">닫기</button>`;
      m.style.display = '';
      m.querySelector('[data-d]').onclick = () => { const r = e.draw(); if (r.err) { this.toast(r.err, true); return; } show(r); this.fillTools(); };
      m.querySelector('[data-x]').onclick = () => { m.style.display = 'none'; };
    };
    show(null);
  }

  /** 다른 기능이 위쪽 오른쪽에 버튼을 더한다 (소리 버튼 앞) */
  addSysButton(label, title, onClick) {
    const b = el('button', 'sysb', label);
    b.title = title; b.onclick = onClick;
    this.rightEl.insertBefore(b, this.sndBtn);
    return b;
  }
  /** 가운데 팝업: html 을 넣고 bind(팝업 요소) 로 버튼을 연결. 닫기 함수를 돌려준다 */
  modal(html, bind) {
    const m = this.modalEl;
    m.innerHTML = html; m.style.display = '';
    const close = () => { m.style.display = 'none'; };
    if (bind) bind(m, close);
    return close;
  }

  offer(o) {
    const m = this.modalEl;
    const ppl = o.ppl.map((d) => `<div><span style="font-size:40px">${d.stage === 'kid' ? '🧒' : d.gender === 'm' ? '🧑' : '👩'}</span><br>${esc(d.name)}<br>${d.stage === 'kid' ? '아이' : d.age + '세'}</div>`).join('');
    m.innerHTML = `<h2>🧳 이주민이 찾아왔어요</h2><div>우리 마을에서 함께 살고 싶대요. 받아 줄까요?<br><small>받으면 스스로 오두막을 지어 살아요. 식량은 더 필요해요.</small></div><div class="ppl">${ppl}</div>` +
      '<button data-y="1">🤗 받기</button><button class="gray" data-y="0">돌려보내기</button>';
    m.style.display = '';
    for (const b of m.querySelectorAll('button')) b.onclick = () => { m.style.display = 'none'; this.g.people.answerOffer(b.dataset.y === '1'); };
  }
}
