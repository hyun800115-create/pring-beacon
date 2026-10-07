// 화면 위 메뉴 (HTML): 시간·속도, 창고, 소식, 할 일, 도구 막대, 정보 카드, 이주민 팝업, 알림.

import { Assets } from '../core/assets.js';
import { BUILDINGS, BUILD_MENU, ITEMS, ITEM_ORDER, NUM } from '../data/defs.js';

const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export class Hud {
  constructor(scene) {
    this.s = scene;
    this.root = document.getElementById('hud');
    this.root.innerHTML = '';
    this.icons = {};
    let sky = document.getElementById('sky');
    if (!sky) { sky = el('div'); sky.id = 'sky'; document.body.appendChild(sky); }
    this.sky = sky;
    this.t = 0;
    this.build();
    this.refresh();
  }

  icon(atlas, frame) {
    const k = atlas + '/' + frame;
    if (this.icons[k] !== undefined) return this.icons[k];
    let url = '';
    try {
      const [key, f] = Assets.tex(this.s, atlas, frame);
      url = this.s.textures.getBase64(key, f);
    } catch (e) { url = ''; }
    this.icons[k] = url;
    return url;
  }
  itemIcon(t) { const x = ITEMS[t].tex; return this.icon(x[0], x[1]); }
  bldIcon(type) { const d = BUILDINGS[type]; const sp = d.levels ? d.levels[0].sprite : d.sprite; return this.icon(sp[0], sp[1]); }
  personIcon(look) { const c = Assets.chars[look]; return c ? this.icon(c.atlas, 'idle_S_0') : ''; }

  build() {
    const r = this.root, s = this.s;
    // 위
    const top = el('div', 'top');
    this.clockEl = el('div', 'clock panel pe');
    this.clockTxt = el('span');
    this.clockEl.appendChild(this.clockTxt);
    const sp = el('span', 'speed');
    this.speedBtns = [0, 1, 2, 3].map((v) => {
      const b = el('button', '', v === 0 ? '⏸' : '▶'.repeat(v));
      b.title = v === 0 ? '멈춤' : `${v}배속`;
      b.onclick = () => { s.speed = v; this.refresh(); };
      sp.appendChild(b); return b;
    });
    this.clockEl.appendChild(sp);
    this.stockEl = el('div', 'stock panel');
    this.rightEl = el('div', 'right panel pe');
    this.rightTxt = el('span');
    this.rightEl.appendChild(this.rightTxt);
    const pb = el('button', 'sysb', s.perf ? '↩ 마을로' : '⚡ 성능 시험');
    pb.title = s.perf ? '처음 마을로 돌아가기' : '넓은 지도에 짐꾼 수백 명을 띄워 속도를 재요';
    pb.onclick = () => { location.search = s.perf ? '' : '?perf=1'; };
    this.rightEl.appendChild(pb);
    top.append(this.clockEl, this.stockEl, this.rightEl);
    r.appendChild(top);
    this.chips = {};
    for (const t of ITEM_ORDER) {
      const c = el('div', 'chip');
      c.title = ITEMS[t].name;
      c.innerHTML = `<img alt="" src="${this.itemIcon(t)}"><span>0</span>`;
      this.stockEl.appendChild(c);
      this.chips[t] = c;
    }
    // 소식, 할 일
    this.newsEl = el('div', 'news');
    r.appendChild(this.newsEl);
    this.goalEl = el('div', 'goal panel');
    if (!s.perf) r.appendChild(this.goalEl);
    // 도구 막대
    this.bar = el('div', 'bar panel pe');
    const tools = [
      { m: 'view', em: '👆', nm: '보기' },
      { m: 'road', em: '🛤️', nm: '길', co: '깃발→끌기' },
      { m: 'flag', em: '🚩', nm: '깃발' },
      { sep: true },
      ...BUILD_MENU.map((t) => ({ m: 'build:' + t, img: this.bldIcon(t), nm: BUILDINGS[t].name, co: costText(BUILDINGS[t].cost) })),
      { sep: true },
      { m: 'remove', em: '🧹', nm: '없애기' },
    ];
    this.toolBtns = [];
    for (const t of tools) {
      if (t.sep) { this.bar.appendChild(el('div', 'tool sep')); continue; }
      const b = el('button', 'tool');
      b.innerHTML = (t.img ? `<img alt="" src="${t.img}">` : `<span class="em">${t.em}</span>`) + `<span class="nm">${esc(t.nm)}</span>` + (t.co ? `<span class="co">${esc(t.co)}</span>` : '');
      b.onclick = () => { if (s.mode === 'settle') { this.toast('먼저 마을회관 자리를 정해 주세요', true); return; } s.setMode(s.mode === t.m ? 'view' : t.m); };
      b.dataset.m = t.m;
      this.bar.appendChild(b); this.toolBtns.push(b);
    }
    if (!s.perf) r.appendChild(this.bar);
    // 확대·축소
    const z = el('div', 'zoom panel pe');
    const zi = el('button', '', '＋'), zo = el('button', '', '－');
    zi.title = '확대'; zo.title = '축소';
    zi.onclick = () => s.zoomBy(1.25); zo.onclick = () => s.zoomBy(0.8);
    z.append(zi, zo);
    r.appendChild(z);
    // 안내 띠, 카드, 알림, 팝업
    this.promptEl = el('div', 'prompt panel');
    r.appendChild(this.promptEl);
    this.cardEl = el('div', 'card panel pe');
    this.cardEl.style.display = 'none';
    r.appendChild(this.cardEl);
    this.toastEl = el('div', 'toast');
    this.toastEl.style.opacity = 0;
    r.appendChild(this.toastEl);
    this.modalEl = el('div', 'modal panel pe');
    this.modalEl.style.display = 'none';
    r.appendChild(this.modalEl);
  }

  refresh() {
    const s = this.s;
    this.speedBtns.forEach((b, v) => b.classList.toggle('on', s.speed === v));
    for (const b of this.toolBtns) b.classList.toggle('on', b.dataset.m === s.mode);
    const prompts = {
      settle: '🛷 마차가 도착했어요! 마을을 세울 곳을 눌러 주세요 (마을회관이 들어서요)',
      road: '🛤️ 깃발이나 건물을 누른 채 끌면 길이 생겨요. 빈 땅을 누르면 깃발을 꽂아요',
      flag: '🚩 길 위나 빈 땅을 누르면 깃발을 꽂아요 (깃발 사이마다 짐꾼 한 명)',
      remove: '🧹 없앨 길·깃발·건물을 눌러 주세요',
    };
    let p = prompts[s.mode] || '';
    if (s.mode.startsWith('build:')) p = `🏗️ ${BUILDINGS[s.mode.slice(6)].name}을(를) 지을 곳을 눌러 주세요 (노란 칸에 깃발이 생겨요)`;
    if (s.perf) p = '⚡ 성능 시험: 넓은 지도에 짐꾼이 물건을 나르고 있어요. 마음껏 움직이고 확대·축소해 보세요';
    this.promptEl.textContent = p;
    this.promptEl.style.display = p ? '' : 'none';
  }

  tick(dt) {
    this.t += dt;
    if (this.t < 0.25) return;
    this.t = 0;
    const s = this.s, w = s.world, c = s.clock, ppl = s.people;
    this.sky.style.backgroundColor = s.perf ? 'transparent' : c.skyColor();
    this.clockTxt.innerHTML = `<span class="yr">${c.year}년 </span><span class="sea">${c.season.name} ${c.dayOfSeason}일</span> · ${c.timeText} ${c.phase === 'night' ? '🌙' : c.phase === 'evening' ? '🌇' : '☀️'}`;
    for (const t of ITEM_ORDER) {
      const v = Math.max(0, Math.floor(w.stock[t] || 0));
      const ch = this.chips[t];
      ch.lastChild.textContent = v;
      ch.classList.toggle('low', ITEMS[t].food ? false : false);
    }
    const food = (w.stock.bread || 0) + (w.stock.fish || 0);
    const alive = ppl.list.filter((p) => !p.dead);
    const homes = w.blds.filter((b) => b.def.kind === 'house' && b.state === 'active');
    const cap = homes.reduce((a, b) => a + w.capacity(b), 0);
    const idle = alive.filter((p) => p.stage === 'adult' && !p.job).length;
    const waitRoads = new Set(); for (const it of w.items) if (it.flag && it.road && !it.carrier && !it.road.carrier) waitRoads.add(it.road);
    const need = waitRoads.size + w.blds.filter((b) => (b.con && !b.builders.length) || (b.state === 'active' && !b.worker && ['gather', 'farm', 'process'].includes(b.def.kind))).length;
    let txt = `👥 ${alive.length}명<span class="ex"> · 🏠 ${cap}칸 · 🙋 쉬는 사람 ${idle}</span>`;
    if (need > idle && !s.perf) txt += `<span class="ex"> · <span style="color:#c43e30">일손 ${need - idle}명 부족</span></span>`;
    if (!s.perf && food < alive.length * NUM.foodPerDay) txt += ` · <span style="color:#c43e30">🍞 부족</span>`;
    if (s.perf) txt = `⚡ ${Math.round(s.game.loop.actualFps)} fps · 👥 ${alive.length}명 · 📦 ${w.items.length}개 · 🌲 지도 ${w.n}×${w.n}`;
    this.rightTxt.innerHTML = txt;
    if (!s.perf) this.updateGoals();
    if (this.cardFn) this.cardFn();
    // 오래된 소식 지우기
    const kids = [...this.newsEl.children];
    kids.forEach((d) => { if (performance.now() - d.__t > 12000) { d.style.opacity = 0; setTimeout(() => d.remove(), 700); d.__t = Infinity; } });
  }

  updateGoals() {
    const w = this.s.world;
    const has = (type) => w.blds.some((b) => b.type === type && b.state === 'active');
    const houses = w.blds.filter((b) => b.def.kind === 'house' && b.state === 'active').length;
    const g = [
      ['마을회관 세우기', has('hall')],
      ['오두막 2채 짓기', houses >= 2],
      ['나무꾼 작업장·제재소로 판자 만들기', has('woodcutter') && has('sawmill')],
      ['채석장에서 돌 캐기', has('stonecutter')],
      ['밀 농장 → 풍차 → 빵집 잇기', has('farm') && has('windmill') && has('bakery')],
      [`빵 ${10}개 만들기 (${w.stats.breadMade}/10)`, w.stats.breadMade >= 10],
    ];
    const html = '<b>📋 할 일</b>' + g.map(([t, ok]) => `<div class="${ok ? 'ok' : 'no'}">${esc(t)}</div>`).join('');
    if (this.goalEl.__h !== html) { this.goalEl.innerHTML = html; this.goalEl.__h = html; }
  }

  news(text, kind) {
    const d = el('div', kind || 'info');
    d.textContent = text; d.__t = performance.now();
    this.newsEl.prepend(d);
    while (this.newsEl.children.length > 5) this.newsEl.lastChild.remove();
  }

  toast(msg, err) {
    const t = this.toastEl;
    t.textContent = msg; t.className = 'toast' + (err ? ' err' : '');
    t.style.opacity = 1;
    clearTimeout(this.toastT);
    this.toastT = setTimeout(() => { t.style.opacity = 0; }, 2600);
  }

  // ---------------------------------------------------------------- 정보 카드
  closeCard() { this.cardEl.style.display = 'none'; this.cardFn = null; }
  card(fn) { this.cardFn = () => { const h = fn(); if (h == null) { this.closeCard(); return; } if (this.cardEl.__h !== h) { this.cardEl.innerHTML = h; this.cardEl.__h = h; this.bindCard(); } }; this.cardEl.style.display = ''; this.cardEl.__h = null; this.cardFn(); }
  bindCard() {
    const x = this.cardEl.querySelector('.x'); if (x) x.onclick = () => this.closeCard();
    for (const b of this.cardEl.querySelectorAll('[data-act]')) b.onclick = () => this.act(b.dataset.act);
  }

  showPerson(p) {
    this.sel = p;
    this.card(() => {
      if (p.dead) return null;
      const d = this.s.people.describe(p);
      return `<button class="x">✕</button><h3><img alt="" src="${this.personIcon(d.look)}">${esc(d.name)}</h3><div class="sub">${esc(d.sub)}</div>` +
        `<table>${d.rows.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table>` +
        `<div class="btns"><button class="gray" data-act="follow">따라가 보기</button></div>`;
    });
  }

  showBuilding(b) {
    this.sel = b;
    this.card(() => {
      if (b.dead) return null;
      const w = this.s.world, def = b.def;
      const lv = def.levels ? def.levels[b.level] : null;
      const rows = [];
      if (b.con) {
        const mats = Object.keys(b.con.need).map((t) => `${ITEMS[t].name} ${Math.min(b.con.have[t] || 0, b.con.need[t])}/${b.con.need[t]}`).join(', ') || '재료 필요 없음';
        rows.push([b.con.kind === 'upgrade' ? '업그레이드 중' : '공사 중', `${Math.round(w.conProgress(b) * 100)}%<div class="bar2"><i style="width:${Math.round(w.conProgress(b) * 100)}%"></i></div>`]);
        rows.push(['재료', mats]);
        rows.push(['일꾼', b.builders.length ? b.builders.map((p) => p.name).join(', ') : '<span style="color:#c43e30">기다리는 중 (일손 부족)</span>']);
        if (Object.keys(b.con.need).length && w.dist(w.hall ? w.hall.flag : b.flag, b.flag) === Infinity) rows.push(['길', '<span style="color:#c43e30">마을회관과 길이 이어지지 않았어요</span>']);
      }
      if (b.state === 'active') {
        if (def.kind === 'house' || def.kind === 'hq') {
          const res = this.s.people.list.filter((p) => !p.dead && p.home === b);
          if (def.kind === 'house') rows.push(['사는 사람', `${res.length}/${w.capacity(b)}명 ${res.map((p) => p.name).join(', ')}`]);
          if (def.kind === 'hq') rows.push(['창고', ITEM_ORDER.map((t) => `${ITEMS[t].name} ${Math.floor(w.stock[t] || 0)}`).join(' · ')]);
        } else {
          rows.push(['일꾼', b.worker ? b.worker.name : '<span style="color:#c43e30">없음 (일손 부족)</span>']);
          if (def.kind === 'process') rows.push(['재료', `${ITEMS[def.in].name} ${b.inputs}개`], ['만드는 것', `${ITEMS[def.out].name} ${b.working ? '(만드는 중)' : ''}`]);
          if (def.kind === 'farm') rows.push(['밭', `${b.plots.length}/${def.plots}칸, 다 익은 밭 ${b.plots.filter((p) => p.stage === 3).length}`]);
          if (def.kind === 'gather' && b.noRes) rows.push(['알림', `<span style="color:#c43e30">주변에 ${def.res === 'tree' ? '나무' : '바위'}가 없어요</span>`]);
          if (b.out) rows.push(['내보낼 것', `${ITEMS[def.out].name} ${b.out}개 (깃발이 꽉 찼어요)`]);
          if (w.hall && w.dist(w.hall.flag, b.flag) === Infinity) rows.push(['길', '<span style="color:#c43e30">마을회관과 길이 이어지지 않았어요</span>']);
        }
      }
      let btns = '';
      if (def.kind === 'house' && b.state === 'active' && !b.con && def.levels[b.level + 1]) {
        const nx = def.levels[b.level + 1];
        btns += `<button data-act="upgrade">⬆ ${esc(nx.name)}로 (${esc(costText(nx.cost))})</button>`;
      }
      if (def.kind !== 'hq') btns += `<button class="red" data-act="remove">없애기</button>`;
      return `<button class="x">✕</button><h3><img alt="" src="${this.bldIcon(b.type)}">${esc(lv ? lv.name : def.name)}</h3><div class="sub">${esc(def.desc)}</div>` +
        `<table>${rows.map(([a, c]) => `<tr><td>${esc(a)}</td><td>${c}</td></tr>`).join('')}</table><div class="btns">${btns}</div>`;
    });
  }

  showFlag(f) {
    this.sel = f;
    this.card(() => {
      if (f.dead) return null;
      const carriers = f.roads.map((r) => r.carrier ? r.carrier.name : '(없음)').join(', ');
      return `<button class="x">✕</button><h3>🚩 깃발</h3><div class="sub">짐꾼들이 여기서 물건을 주고받아요</div>` +
        `<table><tr><td>물건</td><td>${f.items.length}/${NUM.flagCap}개 ${f.items.map((i) => ITEMS[i.type].name).join(', ')}</td></tr><tr><td>이어진 길</td><td>${f.roads.length}개</td></tr><tr><td>짐꾼</td><td>${esc(carriers || '-')}</td></tr></table>` +
        `<div class="btns"><button class="red" data-act="remove">깃발 없애기</button></div>`;
    });
  }

  act(a) {
    const s = this.s, w = s.world, sel = this.sel;
    if (a === 'follow' && sel) { s.centerOn(sel.x, sel.y); s.applyZoom(Math.max(s.zoom, 1.0)); }
    if (a === 'upgrade' && sel) {
      const nx = sel.def.levels[sel.level + 1];
      if (w.upgradeHouse(sel)) { this.toast(`${nx.name}로 업그레이드를 시작해요. 재료가 오면 공사해요`); Assets.play(s, 'sfx_build', 0.6); }
    }
    if (a === 'remove' && sel) {
      if (sel.bld !== undefined && sel.items) w.removeFlag(sel); else w.removeBuilding(sel);
      this.closeCard();
    }
    this.cardEl.__h = null;
  }

  // ---------------------------------------------------------------- 이주민 팝업
  offer(o) {
    const m = this.modalEl;
    const ppl = o.ppl.map((d) => {
      const look = d.look || (d.gender === 'm' ? 'npc_young_man' : 'npc_herbalist');
      return `<div><img alt="" src="${this.personIcon(look)}"><br>${esc(d.name)}<br>${d.stage === 'kid' ? '아이' : d.age + '세'}</div>`;
    }).join('');
    m.innerHTML = `<h2>🧳 이주민이 찾아왔어요</h2><div>우리 마을에서 함께 살고 싶대요. 받아 줄까요?<br><small>받으면 스스로 오두막을 지어 살아요. 식량은 더 필요해요.</small></div><div class="ppl">${ppl}</div>` +
      `<button data-y="1">🤗 받기</button><button class="gray" data-y="0">돌려보내기</button>`;
    m.style.display = '';
    for (const b of m.querySelectorAll('button')) b.onclick = () => { m.style.display = 'none'; this.s.people.answerOffer(b.dataset.y === '1'); };
  }
}

function costText(c) {
  if (!c) return '';
  return Object.keys(c).map((t) => `${ITEMS[t].name}${c[t]}`).join(' ');
}
