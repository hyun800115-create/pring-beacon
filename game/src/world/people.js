// 주민: 걷기·일하기·쉬기·수다·감정 표현·연애·결혼·출산·장례·이주민.
// 한 사람의 행동은 "할 일 줄(q)"에 쌓인 동작을 하나씩 처리한다: walk(걷기) / wait(동작하며 기다리기) / do(즉시 실행) / until(조건까지 반복).

import { Assets } from '../core/assets.js';
import { DIR_BASE, DIR_FLIP, dirFromVec, TX, TY } from '../core/iso.js';
import { PHASE } from './clock.js';
import { NUM, LOOKS, NAMES, TRAITS, LINES, BUILDER_LOOK } from '../data/defs.js';

const STEP_PX = Math.hypot(TX, TY * 2);   // 한 칸 걷는 거리(땅 기준 거리)
const KID_ADULT_AGE = 2;                   // 시제품: 아이는 2년이면 어른 (시간 압축)
const ELDER_DEATH_AGE = 79;
const FALLBACK = { carry_idle: 'idle', work: 'idle', dance: 'happy', sit: 'idle', run: 'walk', shiver: 'idle', perform: 'happy', talk: 'idle', laugh: 'happy', wave: 'happy', sad: 'idle', angry: 'idle', happy: 'idle', surprised: 'idle' };
const pick = (a, r) => a[Math.floor(r() * a.length)];

export class People {
  constructor(world, clock) {
    this.w = world; this.clock = clock; this.scene = world.scene;
    this.list = [];
    this.nid = 1;
    this.jobT = 0; this.tickT = 0;
    this.event = null;           // 진행 중인 마을 행사
    this.eventQueue = [];
    this.offer = null;           // 이주민 제안
    this.offerDays = 0;
    this.bubbles = 0;
    this.graves = [];
    this.log = [];               // 소식
    this.r = () => world.rng.next();
    world.people = this;
    clock.on((ev) => this.onClock(ev));
  }

  news(text, kind = 'info') { this.log.unshift({ text, kind, day: this.clock.day }); this.w.emit('news', text, kind); }

  // ================================================================ 주민 만들기
  makePerson(o) {
    const r = this.r;
    const gender = o.gender || (r() < 0.5 ? 'm' : 'f');
    const stage = o.stage || 'adult';
    const looks = stage === 'kid' ? (gender === 'm' ? LOOKS.kidM : LOOKS.kidF) : stage === 'elder' ? (gender === 'm' ? LOOKS.oldM : LOOKS.oldF) : LOOKS[gender];
    let look = o.look || pick(looks.filter((k) => Assets.chars[k]), r) || 'npc_yellow';
    if (!Assets.chars[look]) look = Object.keys(Assets.chars).find((k) => k.startsWith('npc_')) || look;
    const used = new Set(this.list.map((p) => p.name));
    const names = NAMES[gender].filter((n) => !used.has(n));
    const p = {
      id: this.nid++, name: o.name || (names.length ? pick(names, r) : pick(NAMES[gender], r)), gender, stage,
      age: o.age != null ? o.age : (stage === 'elder' ? 76 + Math.floor(r() * 2) : stage === 'kid' ? 0 : 20 + Math.floor(r() * 15)),
      trait: o.trait || pick(Object.keys(TRAITS), r), look, lookNow: look,
      energy: 1, mood: 0.65, hungry: false, home: null, spouse: null, partner: null, parents: o.parents || [],
      friends: new Map(), romance: new Map(), job: null, x: o.x, y: o.y, dir: 2, q: [], cur: null,
      hidden: false, sleeping: false, inside: false, atWork: false, onRoad: false, ri: 0, carry: null, trip: null,
      lastExpr: -99, born: this.clock.day, workRate: 1, idleT: 0,
    };
    p.spr = this.scene.add.sprite(p.x, p.y, Assets.chars[look] ? Assets.chars[look].atlas : 'gen_box').setOrigin(0.5, 0.8125);
    p.shadow = this.scene.add.image(p.x, p.y, 'gen_shadow').setDepth(-11000);
    if (stage === 'kid') { p.spr.setScale(0.82); p.shadow.setScale(0.8); }
    this.setAnim(p, 'idle');
    this.list.push(p);
    return p;
  }

  // ================================================================ 그림·동작
  setLook(p, look) {
    if (!Assets.chars[look] || p.lookNow === look) return;
    p.lookNow = look; p.animKey = null;
  }
  setAnim(p, name, dir = p.dir) {
    const c = Assets.chars[p.lookNow];
    if (!c) return;
    let n = name;
    while (!c.anims[n] && FALLBACK[n] && FALLBACK[n] !== n) n = FALLBACK[n];
    if (!c.anims[n]) n = 'idle';
    let base = DIR_BASE[dir];
    const dirs = c.anims[n].dirs || c.dirs;
    let flip = DIR_FLIP[dir];
    if (!dirs.includes(base)) { base = dirs.includes('SE') ? (base === 'N' ? 'S' : 'SE') : dirs[0]; if (DIR_BASE[dir] === 'N') flip = false; }
    const key = `${p.lookNow}:${n}:${base}`;
    if (p.animKey !== key && this.scene.anims.exists(key)) { p.spr.play(key); p.animKey = key; }
    p.spr.flipX = flip;
  }

  say(p, kind, force) {
    if (!force && (this.scene.time.now / 1000 - p.lastExpr < 7)) return;
    p.lastExpr = this.scene.time.now / 1000;
    const em = { tired: 'emote_sweat', grumble: 'emote_anger', happy: 'emote_heart', brave: 'emote_thumbs', chat: 'emote_laugh', love: 'emote_love', hungry: 'emote_bread', cold: 'emote_cold', sad: 'emote_tear', party: 'emote_music', wait: 'emote_dots', star: 'emote_star', zzz: 'emote_zzz', idea: 'emote_idea' }[kind];
    if (p.hidden || !this.scene.isVisible(p.x, p.y)) return;
    if (em) {
      const e = this.scene.add.image(p.x, p.y - 96, 'emotes', em).setScale(0.2).setDepth(40000);
      this.scene.tweens.add({ targets: e, scale: 0.55, duration: 220, ease: 'Back.out' });
      this.scene.tweens.add({ targets: e, alpha: 0, delay: 1700, duration: 300, onComplete: () => e.destroy() });
      e.__p = p; p.emoteSpr = e;
    }
    const lines = LINES[kind];
    if (lines && this.bubbles < 7 && (force || this.r() < 0.7)) {
      this.bubbles++;
      const t = this.scene.add.text(p.x, p.y - 128, pick(lines, this.r), {
        fontFamily: 'Pretendard, "Malgun Gothic", "Apple SD Gothic Neo", sans-serif', fontSize: '17px', color: '#2b2f3a',
        backgroundColor: 'rgba(255,255,255,0.93)', padding: { x: 8, y: 4 }, resolution: 2,
      }).setOrigin(0.5, 1).setDepth(40001);
      t.__p = p; p.bubble = t;
      this.scene.time.delayedCall(2300, () => { t.destroy(); this.bubbles--; if (p.bubble === t) p.bubble = null; });
    }
  }

  /** 잠깐 감정 동작 (할 일 줄 맨 앞에 끼워 넣기) */
  emote(p, kind, anim, secs = 1.2) {
    this.say(p, kind);
    if (anim) p.q.unshift({ t: 'wait', s: secs, anim });
  }

  // ================================================================ 할 일 줄
  walk(p, pts, mul = 1) { p.q.push({ t: 'walk', pts: pts.slice(), mul }); }
  walkTo(p, x, y, mul) { this.walk(p, [{ x, y }], mul); }
  wait(p, s, anim = 'idle', dir) { p.q.push({ t: 'wait', s, anim, dir }); }
  doit(p, fn) { p.q.push({ t: 'do', fn }); }
  until(p, fn, anim = 'idle', dir) { p.q.push({ t: 'until', fn, anim, dir }); }
  clearQ(p) { p.q.length = 0; p.cur = null; }

  speed(p, mul) {
    const tr = TRAITS[p.trait] || {};
    let s = NUM.walkSpeed * STEP_PX * mul * (tr.speed || 1);
    if (p.energy < 0.25) s *= 0.75;
    if (p.stage === 'elder') s *= 0.75;
    return s;
  }

  stepPerson(p, dt) {
    if (!p.cur && p.q.length) p.cur = p.q.shift();
    const c = p.cur;
    if (!c) { p.idleT += dt; this.setAnim(p, p.carry ? 'carry_idle' : 'idle'); return; }
    p.idleT = 0;
    if (c.t === 'walk') {
      let move = this.speed(p, c.mul || 1) * dt;
      while (move > 0 && c.pts.length) {
        const tg = c.pts[0];
        const dx = tg.x - p.x, dy = tg.y - p.y;
        const gd = Math.hypot(dx, dy * 2);
        if (gd < 0.5) { c.pts.shift(); continue; }
        p.dir = dirFromVec(dx, dy);
        if (gd <= move) { p.x = tg.x; p.y = tg.y; move -= gd; c.pts.shift(); }
        else { p.x += dx * move / gd; p.y += dy * move / gd; move = 0; }
      }
      this.setAnim(p, p.carry ? 'carry_walk' : (c.mul > 1.3 ? 'run' : 'walk'));
      if (!c.pts.length) p.cur = null;
    } else if (c.t === 'wait') {
      if (c.dir != null) p.dir = c.dir;
      this.setAnim(p, c.anim);
      c.s -= dt;
      if (c.s <= 0) p.cur = null;
    } else if (c.t === 'do') {
      p.cur = null;
      c.fn(p);
    } else if (c.t === 'until') {
      if (c.dir != null) p.dir = c.dir;
      const res = c.fn(p, dt);
      this.setAnim(p, typeof res === 'string' ? res : c.anim);
      if (res === true) p.cur = null;
    }
  }

  // ================================================================ 매 프레임
  update(dt) {
    const phase = this.clock.phase;
    this.jobT += dt; this.tickT += dt;
    if (this.jobT > 1) { this.jobT = 0; if (phase === PHASE.DAY && !this.event) this.assignJobs(); }
    if (this.tickT > 1) { this.tickT = 0; this.tickNeeds(1); }
    if (this.event) this.updateEvent(dt); else this.tickEvents();
    for (const p of this.list) {
      if (p.dead) continue;
      if (p.hidden) { if (p.sleeping) p.energy = Math.min(1, p.energy + dt * 0.016); continue; }
      if (!p.cur && !p.q.length) this.think(p, phase);
      this.stepPerson(p, dt);
      this.place(p);
    }
  }

  place(p) {
    const vis = !p.hidden && this.scene.isVisible(p.x, p.y);
    p.spr.setVisible(vis); p.shadow.setVisible(vis);
    if (!vis) { if (p.carry) p.carry.spr.setVisible(false); return; }
    p.spr.setPosition(p.x, p.y).setDepth(p.y);
    p.shadow.setPosition(p.x, p.y);
    if (p.carry) {
      const c = Assets.chars[p.lookNow];
      const base = DIR_BASE[p.dir], flip = DIR_FLIP[p.dir];
      const cp = (c && c.carryPoint && c.carryPoint[base]) || [0, -32, false];
      const sc = p.stage === 'kid' ? 0.82 : 1;
      p.carry.spr.setVisible(true).setScale(0.62 * sc)
        .setPosition(p.x + (flip ? -cp[0] : cp[0]) * sc, p.y + cp[1] * sc + 12)
        .setDepth(p.y + (cp[2] ? -0.5 : 0.5));
    }
    if (p.bubble) p.bubble.setPosition(p.x, p.y - 112);
    if (p.emoteSpr && p.emoteSpr.active) p.emoteSpr.setPosition(p.x, p.y - 92);
  }

  hide(p) { p.hidden = true; p.spr.setVisible(false); p.shadow.setVisible(false); if (p.carry) p.carry.spr.setVisible(false); }
  show(p, x, y) { p.hidden = false; p.sleeping = false; if (x != null) { p.x = x; p.y = y; } }

  // ================================================================ 생각하기 (할 일이 없을 때)
  think(p, phase) {
    if (p.event) { this.wait(p, 0.5, p.eventAnim || 'idle'); return; }
    if (phase === PHASE.NIGHT) { this.offDuty(p); this.goSleep(p); return; }
    if (phase === PHASE.EVENING) { this.offDuty(p); this.freeTime(p, true); return; }
    if (p.stage === 'adult' && p.job) { this.doJob(p); return; }
    this.freeTime(p, false);
  }

  /** 일을 멈추고 일터에서 나오기 */
  offDuty(p) {
    if (p.inside && p.job && p.job.bld && !p.job.bld.dead) { this.show(p, p.job.bld.door.x, p.job.bld.door.y); }
    p.inside = false; p.atWork = false;
    if (p.onRoad) { p.onRoad = false; }
    this.setLook(p, p.look);
  }

  homeOf(p) {
    if (p.home && !p.home.dead) return p.home;
    const h = this.w.hall;
    return h && !h.dead && h.state === 'active' ? h : null;
  }

  goSleep(p) {
    const h = this.homeOf(p);
    if (h) {
      const sleepers = this.list.filter((q) => q !== p && q.sleeping && q.sleepAt === h).length;
      if (h !== this.w.hall || sleepers < this.w.capacity(h)) {
        this.walkTo(p, h.door.x + (this.r() - 0.5) * 20, h.door.y);
        this.doit(p, () => { if (this.clock.phase === PHASE.NIGHT) { this.hide(p); p.sleeping = true; p.sleepAt = h; } });
        return;
      }
    }
    // 잘 곳이 없다 → 밖에서 웅크리고 잔다
    const c = this.w.wagon || this.w.hall;
    if (c && Math.hypot(p.x - c.x, p.y - c.y) > 260) { this.walkTo(p, c.x + (this.r() - 0.5) * 220, c.y + 40 + this.r() * 90); return; }
    p.coldNight = true;
    if (this.r() < 0.15) this.say(p, this.w.hall ? 'cold' : 'zzz');
    this.wait(p, 3, 'sit');
  }

  wake(p) {
    if (!p.hidden || p.dead) return;
    const h = p.sleepAt || this.homeOf(p);
    this.show(p, h ? h.door.x : p.x, h ? h.door.y + 8 : p.y);
    p.sleepAt = null;
  }

  // ================================================================ 쉬는 시간: 산책, 수다, 놀이
  freeTime(p, evening) {
    const r = this.r();
    const home = this.homeOf(p) || this.w.wagon;
    if (p.stage === 'kid') {
      if (r < 0.5) { const t = this.near(home, 4); this.walkTo(p, t.x, t.y, 1.5); this.wait(p, 1.5, this.r() < 0.5 ? 'dance' : 'happy'); }
      else this.chatOrWander(p, home);
      return;
    }
    if (p.stage === 'elder' && r < 0.4) { const t = this.near(home, 2); this.walkTo(p, t.x, t.y, 0.8); this.wait(p, 4 + this.r() * 4, 'sit'); return; }
    if (evening && p.partner && !p.partner.dead && !p.partner.event && r < 0.5) { this.dateWalk(p, p.partner); return; }
    this.chatOrWander(p, home);
  }

  near(b, rad) {
    const c = b ? { x: b.door ? b.door.x : b.x, y: b.door ? b.door.y + 40 : b.y + 40 } : { x: 0, y: 0 };
    const a = this.r() * Math.PI * 2, d = (0.4 + this.r() * 0.6) * rad * TX;
    return { x: c.x + Math.cos(a) * d, y: c.y + Math.sin(a) * d * 0.5 + 10 };
  }

  chatOrWander(p, home) {
    const shy = (TRAITS[p.trait] || {}).social || 1;
    if (this.r() < 0.55 * shy) {
      let best = null, bd = 900;
      for (const q of this.list) {
        if (q === p || q.dead || q.hidden || q.event || q.chatting || q.cur || q.q.length) continue;
        if (q.stage !== 'kid' && q.job && this.clock.phase === PHASE.DAY) continue;
        const d = Math.hypot(q.x - p.x, q.y - p.y) - (p.friends.get(q.id) || 0) * 40 - (p.partner === q ? 300 : 0);
        if (d < bd) { bd = d; best = q; }
      }
      if (best) { this.chat(p, best); return; }
    }
    const t = this.near(home, 5);
    this.walkTo(p, t.x, t.y, 0.8);
    this.wait(p, 1.5 + this.r() * 3, 'idle');
    if (p.mood > 0.75 && this.r() < 0.25) this.doit(p, () => this.emote(p, 'happy', 'happy'));
    if (p.trait === 'brave' && this.r() < 0.2) this.doit(p, () => this.emote(p, 'brave', 'wave'));
  }

  /** 두 사람이 만나서 수다 */
  chat(a, b) {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const off = TX * 0.42;
    a.chatting = b; b.chatting = a;
    const pa = { x: mx - off, y: my + off * 0.25 }, pb = { x: mx + off, y: my - off * 0.25 };
    this.clearQ(b);
    this.walkTo(a, pa.x, pa.y); this.walkTo(b, pb.x, pb.y);
    const ready = () => !a.cur && !b.cur;
    let tmo = 10;
    const meet = (p, q) => this.until(p, (pp, dt) => { tmo -= dt / 2; if (q.chatting !== p) return true; return (ready() || tmo < 0) ? true : 'idle'; });
    meet(a, b); meet(b, a);
    const love = this.compatible(a, b);
    const n = 2 + Math.floor(this.r() * 3);
    for (const [p, q] of [[a, b], [b, a]]) {
      for (let k = 0; k < n; k++) {
        const mine = (k % 2 === 0) === (p === a);
        this.doit(p, () => { p.dir = dirFromVec(q.x - p.x, q.y - p.y); if (mine) this.say(p, love && (p.romance.get(q.id) || 0) > 1 ? 'love' : 'chat', true); });
        this.wait(p, 1.6, mine ? 'talk' : (this.r() < 0.4 ? 'laugh' : 'idle'));
      }
      this.doit(p, () => {
        p.chatting = null;
        p.friends.set(q.id, Math.min(5, (p.friends.get(q.id) || 0) + 0.35));
        p.mood = Math.min(1, p.mood + 0.04);
        if (love) {
          const shy = (TRAITS[p.trait] || {}).social || 1;
          p.romance.set(q.id, (p.romance.get(q.id) || 0) + 0.45 * shy);
          if (p === a) this.checkLove(a, b);
        }
      });
    }
  }

  compatible(a, b) {
    return a.stage === 'adult' && b.stage === 'adult' && a.gender !== b.gender && !a.spouse && !b.spouse &&
      (!a.partner || a.partner === b) && (!b.partner || b.partner === a) && !a.parents.includes(b) && !b.parents.includes(a);
  }

  checkLove(a, b) {
    const ra = a.romance.get(b.id) || 0, rb = b.romance.get(a.id) || 0;
    if (!a.partner && ra >= 1.8 && rb >= 1.8) {
      a.partner = b; b.partner = a;
      this.say(a, 'love', true); this.say(b, 'love', true);
      this.news(`💕 ${a.name}와(과) ${b.name}이(가) 사귀기 시작했어요`, 'love');
    } else if (a.partner === b && ra >= 4 && rb >= 4 && !a.weddingPlanned) {
      a.weddingPlanned = b.weddingPlanned = true;
      this.eventQueue.push({ kind: 'wedding', a, b });
      this.news(`💍 ${a.name}와(과) ${b.name}이(가) 결혼을 약속했어요! 곧 마을 잔치가 열려요`, 'love');
    }
  }

  dateWalk(a, b) {
    if (b.cur || b.q.length || b.hidden) { this.chatOrWander(a, this.homeOf(a)); return; }
    const home = this.homeOf(a) || this.w.wagon;
    const t = this.near(home, 6);
    this.clearQ(b);
    this.walkTo(a, t.x, t.y, 0.7); this.walkTo(b, t.x + 34, t.y - 10, 0.7);
    this.doit(a, () => this.say(a, 'love'));
    this.wait(a, 2.5, 'happy'); this.wait(b, 2.5, 'happy');
    this.doit(a, () => { a.romance.set(b.id, (a.romance.get(b.id) || 0) + 0.4); b.romance.set(a.id, (b.romance.get(a.id) || 0) + 0.4); this.checkLove(a, b); });
  }

  // ================================================================ 일
  assignJobs() {
    const w = this.w;
    const jobs = [];
    for (const b of w.blds) {
      if (b.dead) continue;
      if (b.con) {
        const max = b.type === 'hall' ? 99 : 1;
        const anyMat = Object.keys(b.con.need).length === 0 || Object.keys(b.con.have).some((t) => b.con.have[t] > 0);
        if (b.builders.length < max) jobs.push({ kind: 'builder', bld: b, x: b.x, y: b.y, pri: anyMat ? 3 : 0.5 });
      } else if (b.state === 'active' && !b.worker && (b.def.kind === 'gather' || b.def.kind === 'farm' || b.def.kind === 'process')) {
        jobs.push({ kind: 'worker', bld: b, x: b.x, y: b.y, pri: 2 });
      }
    }
    // 짐꾼은 물건이 기다리는 길에만 (한가하면 다른 일로 옮겨 간다)
    const waiting = new Set();
    for (const it of w.items) if (it.flag && it.road && !it.carrier) waiting.add(it.road);
    for (const r of waiting) if (!r.carrier && !r.dead) { const m = r.pts[r.pts.length >> 1]; jobs.push({ kind: 'carrier', road: r, x: m.x, y: m.y, pri: 2.2 }); }
    jobs.sort((a, b) => b.pri - a.pri);
    for (const j of jobs) {
      let best = null, bd = Infinity;
      for (const p of this.list) {
        if (p.dead || p.stage !== 'adult' || p.job || p.event || p.hidden || p.leaving) continue;
        const d = Math.hypot(p.x - j.x, p.y - j.y);
        if (d < bd) { bd = d; best = p; }
      }
      if (!best) break;
      this.giveJob(best, j);
    }
  }

  giveJob(p, j) {
    p.job = j;
    if (j.kind === 'builder') j.bld.builders.push(p);
    if (j.kind === 'worker') j.bld.worker = p;
    if (j.kind === 'carrier') j.road.carrier = p;
    if (p.chatting) { const q = p.chatting; q.chatting = null; p.chatting = null; }
    this.clearQ(p);
    // 일을 받을 때의 표정
    const tr = TRAITS[p.trait] || {};
    if ((tr.grumble && this.r() < tr.grumble) || p.mood < 0.35) this.emote(p, 'grumble', 'angry', 1.0);
    else if (tr.brave && this.r() < tr.brave) this.emote(p, 'brave', 'wave', 0.9);
    else if (p.mood > 0.75 && this.r() < 0.3) this.emote(p, 'happy', 'happy', 0.9);
  }

  loseJob(p) {
    const j = p.job;
    if (!j) return;
    if (j.kind === 'builder' && j.bld) { const k = j.bld.builders.indexOf(p); if (k >= 0) j.bld.builders.splice(k, 1); }
    if (j.kind === 'worker' && j.bld && j.bld.worker === p) j.bld.worker = null;
    if (j.kind === 'carrier' && j.road && j.road.carrier === p) j.road.carrier = null;
    this.abortTrip(p);
    if (p.inside && j.bld) this.show(p, j.bld.door.x, j.bld.door.y);
    p.inside = false; p.atWork = false; p.onRoad = false;
    p.job = null;
    this.clearQ(p);
    this.setLook(p, p.look);
  }

  abortTrip(p) {
    const t = p.trip;
    if (t) {
      if (!t.into && !t.dropped && t.to) t.to.incoming = Math.max(0, t.to.incoming - 1);
      if (t.it && !t.it.dead && t.it.carrier === p) t.it.carrier = null;
      p.trip = null;
    }
    if (p.carry && !p.carry.dead) {
      const it = p.carry; p.carry = null;
      const r = p.job && p.job.road;
      const f = r && !r.a.dead ? r.a : null;
      if (f) this.w.putItem(it, f); else this.w.killItem(it);
    }
    if (p.toolItem) { p.toolItem.destroy(); p.toolItem = null; }
  }

  buildingGone(b) {
    for (const p of this.list) {
      if (p.job && p.job.bld === b) this.loseJob(p);
      if (p.home === b) p.home = null;
      if (p.sleepAt === b) { this.show(p, b.door.x, b.door.y); p.sleepAt = null; }
    }
  }

  doJob(p) {
    const j = p.job;
    if (j.kind === 'carrier') return this.doCarrier(p);
    if (j.bld && j.bld.dead) { this.loseJob(p); return; }
    if (j.kind === 'builder') return this.doBuilder(p);
    const k = j.bld.def.kind;
    if (k === 'gather') return this.doGather(p);
    if (k === 'farm') return this.doFarm(p);
    if (k === 'process') return this.doProcess(p);
  }

  // ---------------------------------------------------------------- 짐꾼
  roadIdx(r, f) { return f === r.a ? 0 : r.tiles.length - 1; }
  walkAlong(p, r, k) {
    const pts = [];
    const st = k > p.ri ? 1 : -1;
    for (let i = p.ri + st; st > 0 ? i <= k : i >= k; i += st) pts.push(r.pts[i]);
    if (pts.length) this.walk(p, pts);
    this.doit(p, () => { p.ri = k; });
  }

  doCarrier(p) {
    const r = p.job.road;
    if (r.dead) { this.loseJob(p); return; }
    const mid = r.pts.length >> 1;
    if (!p.onRoad) {
      const m = r.pts[mid];
      this.walkTo(p, m.x, m.y);
      this.doit(p, () => { p.onRoad = true; p.ri = mid; });
      return;
    }
    const pk = this.w.pickFor(r);
    if (pk) {
      p.jobIdle = 0;
      const { it, from, to, into } = pk;
      it.carrier = p;
      if (!into) to.incoming++;
      p.trip = { it, to, into, dropped: false };
      this.walkAlong(p, r, this.roadIdx(r, from));
      this.doit(p, () => {
        if (it.dead || it.flag !== from || r.dead) { this.abortTrip(p); this.clearQ(p); return; }
        this.w.takeItem(it); p.carry = it;
        if (p.energy < 0.3 && this.r() < 0.35) this.emote(p, 'tired', 'sad', 0.8);
      });
      this.walkAlong(p, r, this.roadIdx(r, to));
      this.doit(p, () => this.dropAt(p, r, to));
      return;
    }
    p.jobIdle = (p.jobIdle || 0) + 0.5;
    // 한가하면 다른 일 찾기: 다른 길에 물건이 쌓였거나, 아주 오래 한가할 때
    if (p.jobIdle > 30 || (p.jobIdle > 8 && this.w.items.some((x) => x.flag && x.road && !x.carrier && !x.road.carrier))) { p.jobIdle = 0; this.loseJob(p); return; }
    if (p.ri !== mid && p.idleT > 0.6) { this.walkAlong(p, r, mid); return; }
    this.wait(p, 0.5, 'idle', 2);
    if (this.r() < 0.02) this.doit(p, () => this.idleMood(p));
  }

  dropAt(p, r, to) {
    const t = p.trip, it = p.carry;
    if (!t || !it) return;
    p.energy = Math.max(0, p.energy - 0.025);
    const dest = it.dest;
    if (dest && !dest.perf && !dest.dead && dest.flag === to) {
      if (!t.into) to.incoming = Math.max(0, to.incoming - 1);
      t.dropped = true;
      this.walkTo(p, dest.door.x, dest.door.y);
      this.doit(p, () => { p.carry = null; p.trip = null; it.carrier = null; this.w.deliver(it, dest); if (this.r() < 0.12) this.idleMood(p); });
      this.walkTo(p, to.x, to.y);
      return;
    }
    if (!t.into) to.incoming = Math.max(0, to.incoming - 1);
    t.dropped = true;
    p.carry = null; p.trip = null;
    if (to.dead) { this.w.killItem(it); return; }
    this.w.putItem(it, to);
    if (dest && dest.perf && to === dest.flag) this.w.emit('perfArrive', it);
  }

  idleMood(p) {
    if (p.energy < 0.25) this.emote(p, 'tired', 'sad', 1);
    else if (p.mood > 0.75) this.emote(p, 'happy', 'happy', 1);
    else if (p.trait === 'brave') this.emote(p, 'brave', 'wave', 0.9);
    else if (p.mood < 0.35) this.emote(p, 'grumble', 'angry', 0.9);
  }

  // ---------------------------------------------------------------- 공사
  doBuilder(p) {
    const b = p.job.bld;
    if (!b.con) { this.loseJob(p); return; }
    const k = b.builders.indexOf(p);
    const n = Math.max(1, b.builders.length);
    // 공사장 둘레에 나눠 서기 (앞쪽 두 변)
    const u = (k + 0.5) / n;
    const edge = (b.s - 1) / 2 + 0.75;
    const ti = u < 0.5 ? b.cti - edge + u * 2 * edge * 2 : b.cti + edge;
    const tj = u < 0.5 ? b.ctj - edge : b.ctj - edge + (u - 0.5) * 2 * edge * 2;
    const spot = this.w.W(ti, tj);
    this.walkTo(p, spot.x, spot.y);
    this.doit(p, () => { this.setLook(p, BUILDER_LOOK); p.dir = dirFromVec(b.x - p.x, b.y - p.y); });
    let waitT = 0;
    this.until(p, (pp, dt) => {
      if (!b.con || b.dead) { this.setLook(p, p.look); this.loseJob(p); return true; }
      if (this.clock.phase !== PHASE.DAY || p.event) { this.setLook(p, p.look); return true; }
      const before = b.con.work;
      this.w.addConWork(b, dt * (p.workRate || 1));
      if (b.con && b.con.work !== before) p.jobIdle = 0;
      p.energy = Math.max(0, p.energy - dt * 0.0015);
      if (b.con && b.con.work === before) {   // 재료 기다리는 중
        waitT += dt; p.jobIdle = (p.jobIdle || 0) + dt;
        if (waitT > 6) { waitT = 0; this.say(p, 'wait'); }
        if (p.jobIdle > 20 && b.type !== 'hall' && !b.free) { p.jobIdle = 0; this.setLook(p, p.look); this.loseJob(p); return true; }
        return 'idle';
      }
      if (!b.con) { this.setLook(p, p.look); this.say(p, p.trait === 'brave' ? 'brave' : 'happy'); this.loseJob(p); return true; }
      return 'work';
    }, 'work');
  }

  // ---------------------------------------------------------------- 나무꾼·채석장
  findRes(b) {
    const w = this.w, m = w.map, R = b.def.radius;
    let best = null, bd = Infinity;
    for (let j = Math.floor(b.ctj - R); j <= b.ctj + R; j++) for (let i = Math.floor(b.cti - R); i <= b.cti + R; i++) {
      const o = m.objAt(i, j);
      if (!o || o.type !== b.def.res || o.reserved) continue;
      const d = Math.hypot(i - b.cti, j - b.ctj);
      if (d <= R && d < bd) { bd = d; best = o; }
    }
    return best;
  }

  enter(p, b) {
    this.walkTo(p, b.door.x, b.door.y);
    this.doit(p, () => { this.hide(p); p.inside = true; this.setLook(p, p.look); });
  }

  doGather(p) {
    const b = p.job.bld;
    if (!p.inside) { this.enter(p, b); return; }
    if (b.out >= NUM.outputCap) { this.wait(p, 2); return; }
    const o = this.findRes(b);
    if (!o) { this.wait(p, 3); if (this.r() < 0.1) b.noRes = true; return; }
    b.noRes = false;
    o.reserved = true;
    this.show(p, b.door.x, b.door.y); p.inside = false;
    this.setLook(p, b.def.tool);
    const stand = { x: o.x - TX * 0.42, y: o.y + TY * 0.2 };
    this.walkTo(p, stand.x, stand.y);
    const dir = dirFromVec(o.x - stand.x, o.y - stand.y);
    this.doit(p, () => { if (this.scene.isVisible(p.x, p.y)) Assets.play(this.scene, b.def.res === 'tree' ? 'sfx_chop_1' : 'sfx_mine_1', 0.25); });
    this.wait(p, b.def.work / Math.max(0.5, p.workRate || 1), 'work', dir);
    this.doit(p, () => {
      p.energy = Math.max(0, p.energy - 0.04);
      o.reserved = false;
      const cur = this.w.map.objAt(o.i, o.j);
      if (cur !== o) { this.walkTo(p, b.door.x, b.door.y); this.doit(p, () => { this.hide(p); p.inside = true; }); return; }
      if (o.type === 'tree') this.w.chopTree(o); else this.w.mineRock(o);
      p.carry = { spr: this.w.itemSprite(b.def.out), dead: false, fake: true };
      if (p.energy < 0.3) this.emote(p, 'tired', 'sad', 0.8);
      else if (this.r() < 0.15) this.idleMood(p);
      this.walkTo(p, b.door.x, b.door.y);
      this.doit(p, () => { if (p.carry) { p.carry.spr.destroy(); p.carry = null; } b.out++; this.hide(p); p.inside = true; });
    });
  }

  // ---------------------------------------------------------------- 밀 농장
  doFarm(p) {
    const b = p.job.bld, w = this.w;
    if (!p.inside) { this.enter(p, b); return; }
    if (b.out >= NUM.outputCap) { this.wait(p, 2); return; }
    const ripe = b.plots.find((q) => q.stage === 3 && !q.reserved);
    let spot = null;
    if (!ripe && b.plots.length < (b.plotWanted || 0)) spot = w.findPlotSpot(b);
    if (!ripe && !spot) { this.wait(p, 2.5); return; }
    const tgt = ripe ? { x: ripe.x, y: ripe.y } : w.W(spot.i, spot.j);
    if (ripe) ripe.reserved = true;
    else w.map.setOcc(spot.i, spot.j, { type: 'plot', ref: null });   // 자리 맡기
    this.show(p, b.door.x, b.door.y); p.inside = false;
    this.setLook(p, b.def.tool);
    const stand = { x: tgt.x - TX * 0.36, y: tgt.y + TY * 0.18 };
    this.walkTo(p, stand.x, stand.y);
    this.wait(p, b.def.work / Math.max(0.5, p.workRate || 1), 'work', dirFromVec(tgt.x - stand.x, tgt.y - stand.y));
    this.doit(p, () => {
      p.energy = Math.max(0, p.energy - 0.03);
      if (ripe) {
        ripe.reserved = false;
        if (b.dead) return;
        w.setPlotStage(ripe, 0); ripe.t = 0;
        if (this.scene.isVisible(p.x, p.y)) Assets.play(this.scene, 'sfx_harvest_1', 0.25);
        p.carry = { spr: w.itemSprite(b.def.out), dead: false, fake: true };
        if (this.r() < 0.2) this.idleMood(p);
      } else {
        w.map.setOcc(spot.i, spot.j, null);
        if (!b.dead) w.addPlot(b, spot.i, spot.j);
      }
      this.walkTo(p, b.door.x, b.door.y);
      this.doit(p, () => { if (p.carry) { p.carry.spr.destroy(); p.carry = null; b.out++; } this.hide(p); p.inside = true; });
    });
  }

  // ---------------------------------------------------------------- 가공 (제재소·풍차·빵집)
  doProcess(p) {
    const b = p.job.bld;
    if (!p.atWork) {
      this.walkTo(p, b.work.x, b.work.y);
      this.doit(p, () => { p.atWork = true; p.dir = dirFromVec(b.x - p.x, b.y - p.y); });
      return;
    }
    const dir = dirFromVec(b.x - p.x, b.y - p.y);
    this.until(p, (pp, dt) => {
      if (b.dead) return true;
      if (this.clock.phase !== PHASE.DAY || p.event) { p.atWork = false; return true; }
      pp.workT = (pp.workT || 0) + dt;
      if (b.working) { p.energy = Math.max(0, p.energy - dt * 0.003); }
      if (pp.workT > 9) { pp.workT = 0; if (this.r() < 0.4) { this.idleMood(p); return true; } }
      if (b.type === 'sawmill' && b.working) { this.setLook(p, 'lumberjack'); return 'work'; }
      this.setLook(p, p.look);
      return b.working ? (this.r() < 0.004 ? 'happy' : 'idle') : 'idle';
    }, 'idle', dir);
  }

  // ================================================================ 필요: 기운, 기분, 먹기, 집
  tickNeeds(dt) {
    for (const p of this.list) {
      if (p.dead) continue;
      const tr = TRAITS[p.trait] || {};
      if (!p.hidden && !p.sleeping) p.energy = Math.max(0, p.energy - dt * (p.job ? 0.0016 : 0.0006));
      let target = 0.6 + (tr.mood || 0);
      if (p.hungry) target -= 0.25;
      if (!p.home) target -= this.w.hall ? 0.12 : 0.05;
      if (p.coldNight) target -= 0.1;
      if (p.partner) target += 0.08;
      let fr = 0; for (const v of p.friends.values()) if (v > 1) fr++;
      target += Math.min(0.15, fr * 0.04);
      target += (p.joy || 0);
      p.joy = Math.max(0, (p.joy || 0) - dt * 0.002);
      p.mood += (Math.max(0, Math.min(1, target)) - p.mood) * dt * 0.02;
      p.workRate = (tr.work || 1) * (0.6 + 0.4 * p.energy) * (0.8 + 0.4 * p.mood);
    }
  }

  assignHomes() {
    const houses = this.w.blds.filter((b) => b.def.kind === 'house' && b.state === 'active' && !b.dead);
    const count = (h) => this.list.filter((q) => !q.dead && q.home === h).length;
    for (const p of this.list) {
      if (p.dead || (p.home && !p.home.dead)) continue;
      // 가족이 사는 집 먼저
      const fam = [p.spouse, ...p.parents].find((q) => q && !q.dead && q.home && !q.home.dead && count(q.home) < this.w.capacity(q.home));
      if (fam) { p.home = fam.home; continue; }
      let best = null, bd = Infinity;
      for (const h of houses) {
        if (count(h) >= this.w.capacity(h)) continue;
        const d = Math.hypot(h.x - p.x, h.y - p.y);
        if (d < bd) { bd = d; best = h; }
      }
      if (best) p.home = best;
    }
  }

  // ================================================================ 시간 사건
  onClock(ev) {
    if (ev === 'morning') this.morning();
    if (ev === 'night') for (const p of this.list) { if (p.chatting) { p.chatting = null; } }
    if (ev === 'season') this.news(`🌱 계절이 바뀌었어요: ${this.clock.season.name}`, 'season');
  }

  morning() {
    // 나이 먹기 (해가 바뀌면)
    if ((this.clock.day - 1) % (NUM.daysPerSeason * 4) === 0) {
      for (const p of this.list) if (!p.dead) { p.age++; if (p.stage === 'kid' && p.age >= KID_ADULT_AGE) this.growUp(p); }
    }
    for (const p of this.list) { this.wake(p); p.coldNight = false; }
    this.assignHomes();
    // 아침 식사
    const alive = this.list.filter((p) => !p.dead);
    let need = alive.length * NUM.foodPerDay;
    const s = this.w.stock;
    const eat = (t) => { const k = Math.min(s[t] || 0, Math.ceil(need)); s[t] = (s[t] || 0) - k; need -= k; };
    eat('bread'); eat('fish');
    const hungryN = Math.max(0, Math.ceil(need / NUM.foodPerDay));
    alive.forEach((p, k) => { p.hungry = k < hungryN; if (p.hungry) this.say(p, 'hungry'); });
    if (hungryN > 0) this.news(`🍞 식량이 모자라요! ${hungryN}명이 배고파요`, 'warn');
    this.w.emit('stock');
    // 사건: 결혼식, 출산, 장례
    for (const p of alive) {
      if (p.stage === 'elder' && p.age >= ELDER_DEATH_AGE && this.r() < 0.1) { this.die(p); break; }
    }
    for (const p of alive) {
      if (p.spouse && p.gender === 'f' && !p.dead && p.home && this.clock.day - (p.marriedDay || 0) >= 1 && this.r() < 0.35) {
        const h = p.home, cnt = this.list.filter((q) => !q.dead && q.home === h).length;
        if (cnt < this.w.capacity(h) && this.list.filter((q) => q.parents.includes(p)).length < 3) { this.eventQueue.push({ kind: 'birth', mom: p, dad: p.spouse }); break; }
      }
    }
    // 이주민
    this.offerDays += 1;
    if (this.w.hall && !this.offer && this.offerDays >= NUM.immigrantEvery) { this.offerDays = 0; this.makeOffer(); }
  }

  growUp(p) {
    p.stage = 'adult';
    p.look = pick(LOOKS[p.gender].filter((k) => Assets.chars[k]), this.r);
    this.setLook(p, p.look);
    p.spr.setScale(1); p.shadow.setScale(1);
    this.news(`🎓 ${p.name}이(가) 어른이 되었어요`, 'info');
  }

  die(p) {
    p.dying = true;
    this.eventQueue.unshift({ kind: 'funeral', p });
  }

  // ================================================================ 마을 행사
  startEvent(e) {
    const w = this.w, hall = w.hall;
    if (!hall || hall.state !== 'active') { this.eventQueue.push(e); return false; }
    this.event = e; e.t = 0;
    let center;
    if (e.kind === 'wedding') {
      center = { x: hall.door.x - TX * 1.6, y: hall.door.y + TY * 1.8 };
      e.dur = 16; e.anim = 'dance';
      e.decor = [];
      const lp = w.W(hall.cti - 3.2, hall.ctj - 3.6);
      e.decor.push(this.scene.add.image(lp.x, lp.y, 'life_props', 'lantern_string').setOrigin(0.5, 0.8).setDepth(lp.y));
      const tp = w.W(hall.cti - 1.2, hall.ctj - 4.2);
      e.decor.push(this.scene.add.image(tp.x, tp.y, 'life_props', 'picnic_table').setOrigin(0.5, 0.7).setDepth(tp.y));
      this.news(`🎉 ${e.a.name} ♥ ${e.b.name} 결혼식! 온 마을이 잔치를 열어요`, 'party');
      Assets.play(this.scene, 'sfx_complete', 0.9);
    } else if (e.kind === 'birth') {
      const h = e.mom.home || hall;
      center = { x: h.door.x, y: h.door.y + TY * 1.4 };
      e.dur = 10; e.anim = 'happy';
      const kidG = this.r() < 0.5 ? 'm' : 'f';
      const kid = this.makePerson({ stage: 'kid', gender: kidG, x: h.door.x, y: h.door.y + 6, parents: [e.mom, e.dad] });
      kid.home = h; kid.age = 0;
      e.kid = kid;
      this.news(`👶 ${e.mom.name}와(과) ${e.dad.name}에게 아기 ${kid.name}이(가) 태어났어요!`, 'party');
      Assets.play(this.scene, 'sfx_coin', 0.8);
    } else if (e.kind === 'funeral') {
      const p = e.p;
      const spot = this.graveSpot();
      const g = this.scene.add.image(spot.x, spot.y, 'gen_grave').setOrigin(0.5, 0.85).setDepth(spot.y);
      this.graves.push(g);
      center = { x: spot.x, y: spot.y + TY * 0.9 };
      e.dur = 13; e.anim = 'sad';
      p.dead = true; this.loseJob(p);
      p.spr.destroy(); p.shadow.destroy(); if (p.bubble) p.bubble.destroy();
      if (p.spouse) { p.spouse.spouse = null; p.spouse.joy = -0.3; }
      if (p.partner) p.partner.partner = null;
      this.list.splice(this.list.indexOf(p), 1);
      this.news(`🕯️ ${p.name}(${p.age}세)이(가) 세상을 떠났어요. 마을 사람들이 장례식을 열어요`, 'sad');
    }
    e.center = center;
    // 모두 모이기 (잠자는 사람 빼고)
    const who = this.list.filter((q) => !q.dead && !q.hidden && !q.leaving);
    who.forEach((q, k) => {
      this.abortTrip(q);
      if (q.inside) { const b = q.job && q.job.bld; if (b) this.show(q, b.door.x, b.door.y); q.inside = false; }
      q.atWork = false; q.onRoad = false; q.chatting = null;
      this.setLook(q, q.look);
      this.clearQ(q);
      q.event = e;
      const main = (e.kind === 'wedding' && (q === e.a || q === e.b)) || (e.kind === 'birth' && (q === e.mom || q === e.dad || q === e.kid));
      let pos;
      if (main) pos = { x: center.x + (q === e.a || q === e.mom ? -22 : q === e.kid ? 0 : 22), y: center.y + (q === e.kid ? 14 : 0) };
      else {
        const a = (k / Math.max(1, who.length)) * Math.PI * 2 + 0.3, rr = TX * (1.5 + (k % 2) * 0.6);
        pos = { x: center.x + Math.cos(a) * rr, y: center.y + Math.sin(a) * rr * 0.5 };
      }
      this.walkTo(q, pos.x, pos.y, 1.15);
      this.doit(q, () => { q.dir = dirFromVec(center.x - q.x, center.y - q.y); });
      q.eventAnim = main && e.kind === 'wedding' ? 'happy' : e.anim;
    });
    e.who = who;
    return true;
  }

  updateEvent(dt) {
    const e = this.event;
    e.t += dt;
    if (Math.floor(e.t * 1.3) !== Math.floor((e.t - dt) * 1.3)) {
      const q = e.who[Math.floor(this.r() * e.who.length)];
      if (q && !q.dead) this.say(q, e.kind === 'funeral' ? 'sad' : e.kind === 'wedding' ? (this.r() < 0.5 ? 'party' : 'happy') : 'star', true);
      if (e.kind === 'wedding' && this.r() < 0.5) this.heartBurst(e.center);
    }
    if (e.t < e.dur) return;
    for (const q of e.who) { if (q.dead) continue; q.event = null; q.eventAnim = null; q.joy = Math.max(-0.3, Math.min(0.3, (q.joy || 0) + (e.kind === 'funeral' ? -0.12 : 0.2))); this.clearQ(q); }
    if (e.kind === 'wedding') {
      e.a.spouse = e.b; e.b.spouse = e.a; e.a.marriedDay = e.b.marriedDay = this.clock.day;
      const h = e.a.home || e.b.home;
      if (h) { e.a.home = h; e.b.home = h; }
      this.news(`💒 ${e.a.name}와(과) ${e.b.name}이(가) 부부가 되었어요`, 'love');
    }
    if (e.decor) for (const d of e.decor) this.scene.tweens.add({ targets: d, alpha: 0, duration: 800, onComplete: () => d.destroy() });
    this.event = null;
  }

  heartBurst(c) {
    if (!this.scene.isVisible(c.x, c.y)) return;
    for (let k = 0; k < 3; k++) {
      const h = this.scene.add.image(c.x + (this.r() - 0.5) * 120, c.y - 40, 'emotes', this.r() < 0.5 ? 'emote_heart' : 'emote_sparkle').setScale(0.35).setDepth(40000);
      this.scene.tweens.add({ targets: h, y: h.y - 90 - this.r() * 60, alpha: 0, duration: 1600, onComplete: () => h.destroy() });
    }
  }

  graveSpot() {
    const h = this.w.hall;
    const base = { i: h.cti + 4, j: h.ctj + 3 };
    for (let r = 0; r < 8; r++) for (let dj = -r; dj <= r; dj++) for (let di = -r; di <= r; di++) {
      const i = Math.round(base.i + di), j = Math.round(base.j + dj);
      if (this.w.map.isFree(i, j, false) && !this.w.map.flagNear(i, j)) {
        this.w.map.setOcc(i, j, { type: 'grave', ref: null });
        return this.w.W(i, j);
      }
    }
    return this.w.W(base.i, base.j);
  }

  tickEvents() {
    if (this.event || !this.eventQueue.length || this.clock.phase !== PHASE.DAY) return;
    if (this.clock.frac < 0.12 || this.clock.frac > 0.5) return;
    this.startEvent(this.eventQueue.shift());
  }

  // ================================================================ 이주민
  makeOffer() {
    const n = 2 + Math.floor(this.r() * 2);
    const ppl = [];
    for (let k = 0; k < n; k++) {
      const g = this.r() < 0.5 ? 'm' : 'f';
      const used = new Set(this.list.map((p) => p.name).concat(ppl.map((q) => q.name)));
      const names = NAMES[g].filter((x) => !used.has(x));
      ppl.push({ gender: g, name: pick(names.length ? names : NAMES[g], this.r), trait: pick(Object.keys(TRAITS), this.r), age: 18 + Math.floor(this.r() * 20), look: pick(LOOKS[g].filter((k) => Assets.chars[k]), this.r) });
    }
    if (n >= 3 && this.r() < 0.5) { ppl[2].stage = 'kid'; ppl[2].age = 0; ppl[2].look = pick((ppl[2].gender === 'm' ? LOOKS.kidM : LOOKS.kidF).filter((k) => Assets.chars[k]), this.r); }
    this.offer = { ppl };
    this.w.emit('offer', this.offer);
  }

  answerOffer(yes) {
    const o = this.offer;
    if (!o) return;
    this.offer = null;
    if (!yes) { this.news('👋 이주민들이 다른 마을로 떠났어요', 'info'); return; }
    const w = this.w, n = w.n;
    const e = w.W(n - 2, Math.floor(n / 2) + Math.floor(this.r() * 10 - 5));
    const made = o.ppl.map((d, k) => this.makePerson(Object.assign({ x: e.x + k * 30, y: e.y + k * 14 }, d)));
    const adults = made.filter((p) => p.stage === 'adult');
    if (adults.length >= 2) { adults[0].partner = adults[1]; adults[1].partner = adults[0]; }
    for (const p of made) { p.leaving = true; const t = this.near(w.hall, 3); this.walkTo(p, t.x, t.y, 1.0); this.doit(p, () => { p.leaving = false; this.emote(p, 'happy', 'wave', 1.2); }); }
    // 스스로 오두막 짓기 (재료는 가져온 것으로)
    const spot = w.findHouseSpot();
    if (spot) {
      const h = w.placeBuilding('house', spot.bi, spot.bj, { free: true });
      if (h) {
        for (const p of made) p.home = h;
        for (const p of adults) { p.job = { kind: 'builder', bld: h, x: h.x, y: h.y }; h.builders.push(p); }
        this.news(`🏡 이주민 ${made.map((p) => p.name).join(', ')}이(가) 마을에 왔어요. 직접 오두막을 짓는대요`, 'party');
        return;
      }
    }
    this.news(`🏡 이주민 ${made.map((p) => p.name).join(', ')}이(가) 마을에 왔어요`, 'party');
  }

  // ================================================================ 시작: 마차와 정착
  startCaravan(x, y) {
    const plan = [
      { gender: 'm', look: 'npc_young_man', trait: 'brave' }, { gender: 'f', look: 'npc_aunt', trait: 'cheerful' },
      { gender: 'm', look: 'npc_uncle', trait: 'grumpy' }, { gender: 'f', look: 'npc_herbalist', trait: 'shy' },
      { gender: 'm', look: 'npc_blacksmith', trait: 'diligent' }, { gender: 'f', look: 'npc_red', trait: 'lazy' },
      { gender: 'm', look: 'npc_yellow', trait: 'cheerful' }, { gender: 'f', look: 'npc_fashion', trait: 'brave' },
      { gender: 'm', look: 'npc_blue', trait: 'diligent' }, { gender: 'f', look: 'npc_teen_girl', trait: 'cheerful' },
      { gender: 'm', look: 'npc_bard', trait: 'shy' }, { gender: 'm', look: 'npc_merchant', trait: 'lazy' },
      { gender: 'm', stage: 'elder', trait: 'diligent' }, { gender: 'f', stage: 'elder', trait: 'cheerful' },
    ];
    plan.forEach((d, k) => {
      const a = (k / plan.length) * Math.PI * 2;
      this.makePerson(Object.assign({ x: x + Math.cos(a) * 150, y: y + 60 + Math.sin(a) * 70 }, d));
    });
    const [g1, g2] = this.list.filter((p) => p.stage === 'elder');
    if (g1 && g2) { g1.spouse = g2; g2.spouse = g1; }
  }

  /** 정착지를 정했다 → 모두 마을회관을 지으러 */
  settle(hall) {
    for (const p of this.list) {
      if (p.stage !== 'adult') continue;
      this.clearQ(p);
      p.job = { kind: 'builder', bld: hall, x: hall.x, y: hall.y };
      hall.builders.push(p);
    }
  }

  /** 마을회관 완성 → 마차 짐을 옮기는 모습 */
  unloadWagon(hall, wagon) {
    const ad = this.list.filter((p) => p.stage === 'adult').slice(0, 4);
    const types = ['plank', 'fish', 'stone', 'log'];
    ad.forEach((p, k) => {
      this.clearQ(p);
      this.walkTo(p, wagon.x + 30 - k * 20, wagon.y + 10);
      this.doit(p, () => { p.carry = { spr: this.w.itemSprite(types[k]), dead: false, fake: true }; });
      this.walkTo(p, hall.door.x, hall.door.y);
      this.doit(p, () => { if (p.carry) { p.carry.spr.destroy(); p.carry = null; } if (k === 0) this.emote(p, 'brave', 'wave'); });
    });
  }

  /** 사람 정보 (화면 카드용) */
  describe(p) {
    const tr = TRAITS[p.trait] || { name: '' };
    const j = p.job;
    let job = '쉬는 중';
    if (p.stage === 'kid') job = '아이 (노는 중)';
    else if (p.stage === 'elder') job = '어르신 (쉬는 중)';
    else if (j) job = j.kind === 'carrier' ? '짐꾼' : j.kind === 'builder' ? `공사 (${j.bld.def.name})` : `${j.bld.def.name} 일꾼`;
    if (p.sleeping) job += ' · 자는 중';
    const mood = p.mood > 0.75 ? '😊 아주 좋음' : p.mood > 0.55 ? '🙂 좋음' : p.mood > 0.35 ? '😐 보통' : '😣 나쁨';
    const energy = p.energy > 0.6 ? '💪 넉넉' : p.energy > 0.3 ? '🙂 보통' : '😓 지침';
    let best = null, bv = 0;
    for (const [id, v] of p.friends) if (v > bv) { const q = this.list.find((x) => x.id === id); if (q) { bv = v; best = q; } }
    return {
      name: p.name, look: p.look, sub: `${p.gender === 'm' ? '남' : '여'} · ${p.age}세 · 성격: ${tr.name}`,
      rows: [
        ['하는 일', job], ['기분', mood + (p.hungry ? ' (배고픔)' : '')], ['기운', energy],
        ['집', p.home ? p.home.def.levels ? p.home.def.levels[p.home.level].name : p.home.def.name : (this.w.hall ? '없음 (마을회관에서 잠)' : '마차')],
        ['가족', p.spouse ? `배우자 ${p.spouse.name}` : p.partner ? `연인 ${p.partner.name} 💕` : '혼자'],
        ['친한 친구', best ? best.name : '아직 없음'],
      ],
    };
  }
}

