// 주민 (3D): 걷기(길 따라 빠르게), 일(공사·나르기·나무 베기·채석·농사·가공), 쉬기·수다·선술집·집안 생활(가구 사용),
// 잠(침대에 눕기), 감정 표현, 연애·결혼·출산·장례, 이주민, 마차로 시작.
// 한 사람의 행동은 "할 일 줄(q)"의 동작을 차례로: walk / wait / do / until

import * as THREE from 'three';
import { PHASE } from './clock.js';
import { NUM, LOOKS, NAMES, TRAITS, LINES, BUILDINGS } from './defs.js';

const KID_ADULT_AGE = 2, ELDER_DEATH_AGE = 79;
const BUILDER_LOOK = 'lumberjack';
const SLOT_ANIM = { sit: 'sit', eat: 'sit_eat', tea: 'sit_talk', read: 'sit_read', desk: 'sit_read', toilet: 'sit', cook: 'work_hands', bake: 'work_hands', work: 'work_hands', wash: 'work_hands', sell: 'idle', shop: 'idle', chat: 'talk', warm: 'idle', play: 'dance', pray: 'idle', sleep: 'sleep' };
const SLOT_LINE = { eat: 'eat', read: 'read', cook: 'cook', tea: 'tea', sit: 'home' };
const SEATED = new Set(['sit', 'eat', 'tea', 'read', 'desk', 'toilet']);
const pick = (a, r) => a[Math.floor(r() * a.length)];
const angTo = (fx, fz, tx, tz) => Math.atan2(tx - fx, tz - fz);

export class People {
  constructor(world, clock, bubbles) {
    this.w = world; this.clock = clock; this.bub = bubbles; this.lib = world.lib; this.scene = world.stage.scene;
    this.list = []; this.nid = 1;
    this.jobT = 0; this.tickT = 0; this.logT = 0;
    this.event = null; this.eventQueue = [];
    this.offer = null; this.offerDays = 0;
    this.log = [];
    this.r = () => world.rng.next();
    clock.on((ev) => this.onClock(ev));
  }

  news(text, kind = 'info') { this.log.unshift({ text, kind, day: this.clock.day }); this.w.emit('news', text, kind); }

  // ================================================================ 주민 만들기
  makePerson(o) {
    const r = this.r;
    const gender = o.gender || (r() < 0.5 ? 'm' : 'f');
    const stage = o.stage || 'adult';
    const pool = stage === 'kid' ? (gender === 'm' ? LOOKS.kidM : LOOKS.kidF) : stage === 'elder' ? (gender === 'm' ? LOOKS.oldM : LOOKS.oldF) : LOOKS[gender];
    const look = o.look || pick(pool, r);
    const used = new Set(this.list.map((p) => p.name));
    const names = NAMES[gender].filter((n) => !used.has(n));
    const p = {
      id: this.nid++, name: o.name || pick(names.length ? names : NAMES[gender], r), gender, stage,
      age: o.age != null ? o.age : stage === 'elder' ? 76 + Math.floor(r() * 2) : stage === 'kid' ? 0 : 20 + Math.floor(r() * 15),
      trait: o.trait || pick(Object.keys(TRAITS), r), look, lookNow: null,
      energy: 1, mood: 0.65, hungry: false, home: null, spouse: null, partner: null, parents: o.parents || [],
      friends: new Map(), romance: new Map(), job: null,
      x: o.x, z: o.z, y: 0, yaw: r() * 6.28, q: [], cur: null,
      hidden: false, sleeping: false, inside: null, slot: null, carry: null, lastSay: -99, idleT: 0, workRate: 1, headY: stage === 'kid' ? 1.15 : 1.55,
      dolls: {},
    };
    this.list.push(p);
    this.setLook(p, look);
    return p;
  }

  setLook(p, look) {
    if (p.lookNow === look) return;
    if (!p.dolls[look]) {
      const d = this.lib.char(look);
      if (p.stage === 'kid') d.root.scale.setScalar(0.85);
      d.root.traverse((o) => { o.userData.person = p; });
      this.scene.add(d.root);
      p.dolls[look] = d;
    }
    const old = p.doll;
    p.doll = p.dolls[look];
    p.lookNow = look;
    for (const d of Object.values(p.dolls)) d.root.visible = d === p.doll && !p.hidden;
    if (old && old.carryObj) { const c = old.carryObj; old.carry(null); p.doll.carry(c); }
    p.doll.curName = ''; p.doll.cur = null;
    this.anim(p, 'idle');
  }

  anim(p, name, speed = 1) { p.doll.play(name, 0.2, speed); }

  say(p, kind, force, emote) {
    const now = performance.now() / 1000;
    if (!force && now - p.lastSay < 7) return;
    p.lastSay = now;
    const em = emote || { tired: 'emote_sweat', grumble: 'emote_anger', happy: 'emote_heart', brave: 'emote_thumbs', chat: 'emote_laugh', love: 'emote_love', hungry: 'emote_bread', cold: 'emote_cold', sad: 'emote_tear', party: 'emote_music', wait: 'emote_dots', build: 'emote_sparkle', home: 'emote_star', eat: 'emote_bread', read: 'emote_idea', cook: 'emote_sparkle', tea: 'emote_heart', zzz: 'emote_zzz' }[kind];
    const lines = LINES[kind];
    const text = lines && (force || this.r() < 0.75) ? pick(lines, this.r) : '';
    if (!p.hidden) this.bub.show(p, text, em);
  }
  emote(p, kind, an, secs = 1.2) { this.say(p, kind); if (an) p.q.unshift({ t: 'wait', s: secs, anim: an }); }

  // ================================================================ 할 일 줄
  walkTo(p, x, z, mul = 1, opts = {}) {
    const route = this.w.roads.route(p.x, p.z, x, z);
    const pts = [];
    let fx = p.x, fz = p.z;
    for (const pt of route) {
      if (pt.sp <= NUM.offRoad + 1e-6) for (const d of this.w.detour(fx, fz, pt.x, pt.z, opts.skip)) pts.push({ x: d.x, z: d.z, sp: NUM.offRoad });
      pts.push(pt); fx = pt.x; fz = pt.z;
    }
    p.q.push({ t: 'walk', pts, mul });
  }
  walkDirect(p, x, z, mul = 1) { p.q.push({ t: 'walk', pts: [{ x, z, sp: 1 }], mul }); }
  wait(p, s, an = 'idle', yaw) { p.q.push({ t: 'wait', s, anim: an, yaw }); }
  doit(p, fn) { p.q.push({ t: 'do', fn }); }
  until(p, fn, an = 'idle', yaw) { p.q.push({ t: 'until', fn, anim: an, yaw }); }
  clearQ(p) { p.q.length = 0; p.cur = null; }

  speed(p, mul) {
    const tr = TRAITS[p.trait] || {};
    let s = NUM.walkSpeed * mul * (tr.speed || 1);
    if (p.energy < 0.25) s *= 0.8;
    if (p.stage === 'elder') s *= 0.72;
    if (p.stage === 'kid') s *= 1.05;
    return s;
  }

  step(p, dt) {
    if (!p.cur && p.q.length) p.cur = p.q.shift();
    const c = p.cur;
    if (!c) { p.idleT += dt; this.anim(p, 'idle'); return; }
    p.idleT = 0;
    if (c.t === 'walk') {
      if (p.y > 0 && !p.slot) p.y = Math.max(0, p.y - dt * 3);
      let move = 0, sp = 1;
      while (c.pts.length) {
        const tg = c.pts[0];
        sp = this.speed(p, c.mul || 1) * (tg.sp || 1);
        move = move || sp * dt;
        const dx = tg.x - p.x, dz = tg.z - p.z, d = Math.hypot(dx, dz);
        if (d < 0.02) { c.pts.shift(); continue; }
        const want = Math.atan2(dx, dz);
        p.yaw = turn(p.yaw, want, dt * 10);
        if (d <= move) { p.x = tg.x; p.z = tg.z; move -= d; c.pts.shift(); if (move <= 0.001) break; }
        else { p.x += dx / d * move; p.z += dz / d * move; move = 0; break; }
      }
      const an = p.carry ? 'carry_walk' : (c.mul > 1.3 ? 'run' : 'walk');
      this.anim(p, an, Math.max(0.6, Math.min(1.6, sp / NUM.walkSpeed)));
      if (!c.pts.length) p.cur = null;
    } else if (c.t === 'wait') {
      if (c.yaw != null) p.yaw = turn(p.yaw, c.yaw, dt * 8);
      this.anim(p, c.anim);
      c.s -= dt;
      if (c.s <= 0) p.cur = null;
    } else if (c.t === 'do') {
      p.cur = null;
      c.fn(p);
    } else if (c.t === 'until') {
      if (c.yaw != null) p.yaw = turn(p.yaw, c.yaw, dt * 8);
      const res = c.fn(p, dt);
      this.anim(p, typeof res === 'string' ? res : c.anim);
      if (res === true) p.cur = null;
    }
  }

  // ================================================================ 매 프레임
  update(dt, cam) {
    const phase = this.clock.phase;
    this.jobT += dt; this.tickT += dt; this.logT += dt;
    if (this.jobT > 1) { this.jobT = 0; if (phase === PHASE.DAY && !this.event) this.assignJobs(); }
    if (this.tickT > 1) { this.tickT = 0; this.tickNeeds(1); }
    if (this.logT > 0.5) { this.logT = 0; this.w.logistics(); }
    if (this.event) this.updateEvent(dt); else this.tickEvents();
    for (const p of this.list) {
      if (p.dead) continue;
      if (p.sleeping && p.hidden) { p.energy = Math.min(1, p.energy + dt * 0.012); continue; }
      if (p.sleeping) p.energy = Math.min(1, p.energy + dt * 0.012);
      if (!p.cur && !p.q.length) this.think(p, phase);
      this.step(p, dt);
      this.place(p, dt, cam);
    }
  }

  place(p, dt, cam) {
    const d = p.doll;
    d.root.visible = !p.hidden;
    if (p.hidden) return;
    d.root.position.set(p.x, p.y, p.z);
    d.root.rotation.y = p.yaw;
    // 멀리 있는 사람은 동작을 덜 자주 계산
    const far = cam && (Math.abs(p.x - cam.tx) > cam.dist * 1.4 || Math.abs(p.z - cam.tz) > cam.dist * 1.4);
    p.skip = (p.skip || 0) + dt;
    if (!far || p.skip > 0.2) { d.update(p.skip, !far); p.skip = 0; }
  }

  hide(p) { p.hidden = true; for (const d of Object.values(p.dolls)) d.root.visible = false; }
  show(p, x, z) { p.hidden = false; if (x != null) { p.x = x; p.z = z; } p.y = 0; }

  // ================================================================ 생각하기
  think(p, phase) {
    if (p.event) { this.wait(p, 0.5, p.eventAnim || 'idle'); return; }
    if (p.slot && !(phase === PHASE.NIGHT && p.slot.s.action === 'sleep')) this.leaveSlot(p);
    if (phase === PHASE.NIGHT) { this.offDuty(p); this.goSleep(p); return; }
    if (phase === PHASE.EVENING) { this.offDuty(p); this.freeTime(p, true); return; }
    if (p.stage === 'adult' && p.job) { this.doJob(p); return; }
    this.freeTime(p, false);
  }

  offDuty(p) {
    if (p.job && p.job.kind === 'haul' && p.carry) return;   // 들고 있는 건 마저 나른다
    if (p.inside && p.inside !== p.home) this.exitBuilding(p);
    p.atWork = false;
    if (p.lookNow !== p.look) this.setLook(p, p.look);
  }

  homeOf(p) {
    if (p.home && !p.home.dead && p.home.state === 'active') return p.home;
    const h = this.w.hall;
    return h && !h.dead && h.state === 'active' ? h : null;
  }

  // ---------------------------------------------------------------- 건물 안 드나들기
  enterBuilding(p, b, then) {
    this.walkTo(p, b.door.x, b.door.z, 1, { skip: b });
    this.doit(p, () => {
      p.inside = b;
      if (!b.hasInterior) { this.hide(p); if (then) then(); return; }
      this.walkDirect(p, b.doorIn.x, b.doorIn.z);
      if (then) this.doit(p, then);
    });
  }
  exitBuilding(p) {
    const b = p.inside;
    p.inside = null;
    if (!b || b.dead) { this.show(p); return; }
    if (p.slot) this.leaveSlot(p);
    if (p.hidden) { this.show(p, b.door.x, b.door.z); return; }
    this.walkDirect(p, b.doorIn.x, b.doorIn.z);
    this.walkDirect(p, b.door.x, b.door.z);
  }
  /** 가구 자리에 가서 동작하기 */
  useSlot(p, b, actions, secs, after) {
    const s = b.freeSlot(actions);
    if (!s) return false;
    b.reserved.add(s);
    const go = () => {
      const w = b.slotWorld(s);
      this.walkDirect(p, w.x, w.z, 0.8);
      this.doit(p, () => {
        p.slot = { b, s };
        const an = SLOT_ANIM[s.action] || 'idle';
        p.yaw = w.yaw;
        if (SEATED.has(s.action)) { p.y = (w.y || 0) + 0.4; p.x -= Math.sin(w.yaw) * 0.18; p.z -= Math.cos(w.yaw) * 0.18; }
        if (s.action === 'sleep') { p.y = (w.y || 0) + 0.05; p.x += Math.sin(w.yaw) * 0.5; p.z += Math.cos(w.yaw) * 0.5; p.sleeping = true; }
        if (SLOT_LINE[s.action] && this.r() < 0.35) this.say(p, SLOT_LINE[s.action]);
        this.wait(p, secs, an, w.yaw);
        this.doit(p, () => { if (s.action !== 'sleep' || this.clock.phase !== PHASE.NIGHT) this.leaveSlot(p); if (after) after(); });
      });
    };
    if (p.inside !== b) this.enterBuilding(p, b, go); else go();
    return true;
  }
  leaveSlot(p) {
    const sl = p.slot; if (!sl) return;
    sl.b.reserved.delete(sl.s);
    p.slot = null; p.y = 0; p.sleeping = false;
    const w = sl.b.slotWorld(sl.s);
    p.x = w.x; p.z = w.z;
  }

  // ---------------------------------------------------------------- 잠
  goSleep(p) {
    const h = this.homeOf(p);
    if (h) {
      if (h.hasInterior && h.slots.some((s) => s.action === 'sleep')) {
        if (this.useSlot(p, h, ['sleep'], 9999)) return;
      }
      const cap = this.w.hall === h ? (h.def.sleeps || 6) : 99;
      const n = this.list.filter((q) => q !== p && q.sleeping && q.sleepAt === h).length;
      if (n < cap) {
        this.enterBuilding(p, h, () => { if (this.clock.phase === PHASE.NIGHT) { this.hide(p); p.sleeping = true; p.sleepAt = h; } });
        return;
      }
    }
    // 잘 곳이 없다 → 밖에서 웅크리고 잔다
    const c = this.w.wagon || this.w.hall;
    if (c && Math.hypot(p.x - c.x, p.z - c.z) > 6) { this.walkTo(p, c.x + (this.r() - 0.5) * 6, c.z + 3 + this.r() * 3); return; }
    p.coldNight = true;
    if (this.r() < 0.12) this.say(p, this.w.hall ? 'cold' : 'zzz');
    this.wait(p, 4, 'sit');
  }
  wake(p) {
    if (p.dead) return;
    if (p.slot) this.leaveSlot(p);
    if (p.hidden) { const h = p.sleepAt || p.inside || this.homeOf(p); this.show(p, h ? h.door.x : p.x, h ? h.door.z : p.z); }
    p.sleeping = false; p.sleepAt = null; p.inside = null; p.y = 0;
    this.clearQ(p);
  }

  // ---------------------------------------------------------------- 쉬는 시간
  freeTime(p, evening) {
    const r = this.r();
    const home = this.homeOf(p);
    if (p.stage === 'kid') {
      if (r < 0.5) { const t = this.near(home || this.w.wagon, 5); this.walkTo(p, t.x, t.z, 1.6); this.wait(p, 1.5, this.r() < 0.5 ? 'dance' : 'happy'); }
      else this.chatOrWander(p, home);
      return;
    }
    if (evening) {
      // 선술집·가게 가기
      const shops = this.w.blds.filter((b) => b.def.kind === 'shop' && b.state === 'active');
      if (shops.length && r < 0.35) {
        const b = pick(shops, this.r);
        if (this.useSlot(p, b, ['eat', 'tea', 'sit', 'shop', 'chat'], 8 + this.r() * 8, () => { p.joy = Math.min(0.3, (p.joy || 0) + (b.def.fun || 0.1)); })) return;
        this.walkTo(p, b.door.x, b.door.z); this.wait(p, 3, 'talk'); this.doit(p, () => { p.joy = Math.min(0.3, (p.joy || 0) + (b.def.fun || 0.1) * 0.6); });
        return;
      }
      // 집안 생활
      if (home && home.hasInterior && r < 0.7) {
        const acts = this.r() < 0.4 ? ['cook', 'eat'] : this.r() < 0.5 ? ['read', 'sit', 'tea'] : ['sit', 'warm', 'eat', 'tea', 'read'];
        if (this.useSlot(p, home, acts, 6 + this.r() * 8)) return;
      }
      if (p.partner && !p.partner.dead && !p.partner.event && r < 0.85) { this.dateWalk(p, p.partner); return; }
    }
    if (p.stage === 'elder' && r < 0.45) {
      const benches = this.w.blds.filter((b) => b.type === 'bench' && b.state === 'active');
      if (benches.length && this.useSlot(p, pick(benches, this.r), ['sit'], 8 + this.r() * 6)) return;
      const t = this.near(home || this.w.wagon, 3); this.walkTo(p, t.x, t.z, 0.8); this.wait(p, 5, 'sit'); return;
    }
    // 낮에 일 없는 사람: 가끔 마을회관(사무실·식당)이나 우물
    if (!evening && this.w.hall && this.w.hall.hasInterior && r < 0.25 && this.useSlot(p, this.w.hall, ['desk', 'read', 'eat', 'tea', 'toilet', 'sit'], 6 + this.r() * 6)) return;
    this.chatOrWander(p, home);
  }

  near(b, rad) {
    const c = b ? (b.door ? b.door : b) : { x: this.w.size / 2, z: this.w.size / 2 };
    const a = this.r() * Math.PI * 2, d = (0.4 + this.r() * 0.6) * rad;
    return { x: c.x + Math.cos(a) * d, z: c.z + Math.sin(a) * d };
  }

  chatOrWander(p, home) {
    const shy = (TRAITS[p.trait] || {}).social || 1;
    if (this.r() < 0.55 * shy) {
      let best = null, bd = 30;
      for (const q of this.list) {
        if (q === p || q.dead || q.hidden || q.event || q.chatting || q.cur || q.q.length || q.slot) continue;
        if (q.stage !== 'kid' && q.job && this.clock.phase === PHASE.DAY) continue;
        const d = Math.hypot(q.x - p.x, q.z - p.z) - (p.friends.get(q.id) || 0) * 2 - (p.partner === q ? 12 : 0);
        if (d < bd) { bd = d; best = q; }
      }
      if (best) { this.chat(p, best); return; }
    }
    const wells = this.w.blds.filter((b) => b.type === 'well' && b.state === 'active');
    const t = wells.length && this.r() < 0.3 ? this.near(pick(wells, this.r), 2.5) : this.near(home || this.w.wagon, 7);
    this.walkTo(p, t.x, t.z, 0.8);
    this.wait(p, 1.5 + this.r() * 3, 'idle');
    if (p.mood > 0.75 && this.r() < 0.25) this.doit(p, () => this.emote(p, 'happy', 'happy'));
    if (p.trait === 'brave' && this.r() < 0.2) this.doit(p, () => this.emote(p, 'brave', 'wave'));
  }

  chat(a, b) {
    const mx = (a.x + b.x) / 2, mz = (a.z + b.z) / 2, ang = Math.atan2(b.x - a.x, b.z - a.z);
    const pa = { x: mx - Math.sin(ang) * 0.55, z: mz - Math.cos(ang) * 0.55 }, pb = { x: mx + Math.sin(ang) * 0.55, z: mz + Math.cos(ang) * 0.55 };
    a.chatting = b; b.chatting = a;
    this.clearQ(b);
    this.walkTo(a, pa.x, pa.z); this.walkTo(b, pb.x, pb.z);
    let tmo = 12;
    const meet = (p, q) => this.until(p, (pp, dt) => { tmo -= dt / 2; if (q.chatting !== p) return true; return (!a.cur || a.cur.t === 'until') && (!b.cur || b.cur.t === 'until') || tmo < 0 ? true : 'idle'; });
    meet(a, b); meet(b, a);
    const love = this.compatible(a, b);
    const n = 2 + Math.floor(this.r() * 3);
    for (const [p, q] of [[a, b], [b, a]]) {
      for (let k = 0; k < n; k++) {
        const mine = (k % 2 === 0) === (p === a);
        this.doit(p, () => { p.yaw = angTo(p.x, p.z, q.x, q.z); if (mine) this.say(p, love && (p.romance.get(q.id) || 0) > 1 ? 'love' : 'chat', true); });
        this.wait(p, 1.8, mine ? 'talk' : (this.r() < 0.4 ? 'laugh' : 'idle'));
      }
      this.doit(p, () => {
        p.chatting = null;
        p.friends.set(q.id, Math.min(5, (p.friends.get(q.id) || 0) + 0.35));
        p.mood = Math.min(1, p.mood + 0.04);
        if (love) { const shy = (TRAITS[p.trait] || {}).social || 1; p.romance.set(q.id, (p.romance.get(q.id) || 0) + 0.45 * shy); if (p === a) this.checkLove(a, b); }
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
    if (b.cur || b.q.length || b.hidden || b.slot) { this.chatOrWander(a, this.homeOf(a)); return; }
    const t = this.near(this.homeOf(a) || this.w.wagon, 8);
    this.clearQ(b);
    this.walkTo(a, t.x, t.z, 0.7); this.walkTo(b, t.x + 0.8, t.z + 0.3, 0.7);
    this.doit(a, () => this.say(a, 'love'));
    this.wait(a, 3, 'happy'); this.wait(b, 3, 'happy');
    this.doit(a, () => { a.romance.set(b.id, (a.romance.get(b.id) || 0) + 0.4); b.romance.set(a.id, (b.romance.get(a.id) || 0) + 0.4); this.checkLove(a, b); });
  }

  // ================================================================ 일 나누기
  assignJobs() {
    const w = this.w, jobs = [];
    for (const b of w.blds) {
      if (b.dead) continue;
      if (b.con) {
        if (b.free && b.type !== 'hall') continue;   // 이주민 집은 자기들이 짓는다
        const max = b.type === 'hall' ? 99 : 1;
        const any = !Object.keys(b.con.need).length || Object.values(b.con.have).some((v) => v > 0);
        if (b.builders.length < max) jobs.push({ kind: 'builder', bld: b, x: b.x, z: b.z, pri: any ? 3 : 0.6 });
      } else if (b.state === 'active' && !b.worker && ['gather', 'farm', 'process'].includes(b.def.kind)) jobs.push({ kind: 'worker', bld: b, x: b.x, z: b.z, pri: 2 });
    }
    for (const t of w.tasks) if (!t.carrier) jobs.push({ kind: 'haul', task: t, x: t.from.x, z: t.from.z, pri: 2.4 });
    jobs.sort((a, b) => b.pri - a.pri);
    for (const j of jobs) {
      let best = null, bd = Infinity;
      for (const p of this.list) {
        if (p.dead || p.stage !== 'adult' || p.job || p.event || p.hidden || p.leaving) continue;
        const d = Math.hypot(p.x - j.x, p.z - j.z) + (p.slot ? 8 : 0) + (p.chatting ? 6 : 0);
        if (d < bd) { bd = d; best = p; }
      }
      if (!best) break;
      this.giveJob(best, j);
    }
  }

  giveJob(p, j) {
    if (p.chatting) { const q = p.chatting; p.chatting = null; if (q.chatting === p) q.chatting = null; }
    if (p.slot) this.leaveSlot(p);
    if (p.inside) { const b = p.inside; p.inside = null; if (p.hidden) this.show(p, b.door.x, b.door.z); }
    p.job = j;
    if (j.kind === 'builder') j.bld.builders.push(p);
    if (j.kind === 'worker') j.bld.worker = p;
    if (j.kind === 'haul') j.task.carrier = p;
    this.clearQ(p);
    const tr = TRAITS[p.trait] || {};
    if ((tr.grumble && this.r() < tr.grumble) || p.mood < 0.35) this.emote(p, 'grumble', 'angry', 1.0);
    else if (tr.brave && this.r() < tr.brave) this.emote(p, 'brave', 'wave', 0.9);
    else if (p.mood > 0.75 && this.r() < 0.3) this.emote(p, 'happy', 'happy', 0.9);
  }

  loseJob(p) {
    const j = p.job; if (!j) return;
    if (j.kind === 'builder') { const k = j.bld.builders.indexOf(p); if (k >= 0) j.bld.builders.splice(k, 1); }
    if (j.kind === 'worker' && j.bld.worker === p) j.bld.worker = null;
    if (j.kind === 'haul') {
      if (j.task.carrier === p) j.task.carrier = null;
      if (j.taken && !j.done) for (const o of [j.task, ...(j.extra || [])]) { this.w.deliver(o.type, this.w.hall); const k = this.w.tasks.indexOf(o); if (k >= 0) this.w.tasks.splice(k, 1); }
    }
    if (p.carry) { p.doll.carry(null); p.carry = null; }
    if (p.inside && p.hidden) { const b = p.inside; this.show(p, b.door.x, b.door.z); }
    p.inside = null; p.atWork = false; p.job = null; p.y = 0;
    this.clearQ(p);
    if (p.lookNow !== p.look) this.setLook(p, p.look);
  }
  buildingGone(b) {
    for (const p of this.list) {
      if (p.job && p.job.bld === b) this.loseJob(p);
      if (p.job && p.job.kind === 'haul' && (p.job.task.to === b || p.job.task.from === b)) this.loseJob(p);
      if (p.home === b) p.home = null;
      if (p.inside === b || (p.slot && p.slot.b === b)) { p.slot = null; p.inside = null; this.show(p, b.door.x, b.door.z); p.sleeping = false; }
    }
  }

  doJob(p) {
    const j = p.job;
    if (j.kind === 'haul') return this.doHaul(p);
    if (j.bld.dead) { this.loseJob(p); return; }
    if (j.kind === 'builder') return this.doBuilder(p);
    const k = j.bld.def.kind;
    if (k === 'gather') return this.doGather(p);
    if (k === 'farm') return this.doFarm(p);
    if (k === 'process') return this.doProcess(p);
    this.loseJob(p);
  }

  carryItem(p, type, n = 1) {
    let o = null;
    if (type) {
      o = new THREE.Group();
      for (let k = 0; k < n; k++) { const m = this.w.itemModel(type); m.scale.multiplyScalar(0.8); m.position.y = k * (type === 'plank' ? 0.09 : 0.2); m.rotation.y = k * 0.25; o.add(m); }
    }
    p.doll.carry(o); p.carry = type || null;
  }

  // ---------------------------------------------------------------- 나르기
  doHaul(p) {
    const j = p.job, t = j.task;
    if (t.cancel || t.from.dead) { this.loseJob(p); return; }
    this.walkTo(p, t.from.door.x, t.from.door.z, 1, { skip: t.from });
    this.doit(p, () => {
      if (t.cancel || !this.w.take(t.type, t.from)) { const k = this.w.tasks.indexOf(t); if (k >= 0) this.w.tasks.splice(k, 1); j.done = true; this.loseJob(p); return; }
      j.taken = true;
      // 같은 곳으로 가는 같은 물건은 한 번에 3개까지
      j.extra = [];
      for (const o of this.w.tasks) {
        if (j.extra.length >= 2) break;
        if (o !== t && !o.carrier && o.from === t.from && o.to === t.to && o.type === t.type && this.w.take(o.type, o.from)) { o.carrier = p; j.extra.push(o); }
      }
      this.carryItem(p, t.type, 1 + j.extra.length);
      if (p.energy < 0.3 && this.r() < 0.4) this.emote(p, 'tired', 'sad', 0.8);
      const dest = t.to.dead ? this.w.hall : t.to;
      const spot = dest.con && dest.pileSpot ? dest.toWorld(dest.pileSpot.x - 0.6, dest.pileSpot.z + 0.6) : dest.door;
      this.walkTo(p, spot.x, spot.z, 1, { skip: dest });
      this.doit(p, () => {
        j.done = true;
        this.carryItem(p, null);
        for (const o of [t, ...(j.extra || [])]) {
          this.w.deliver(o.type, o.to.dead ? this.w.hall : o.to);
          const k = this.w.tasks.indexOf(o); if (k >= 0) this.w.tasks.splice(k, 1);
        }
        p.energy = Math.max(0, p.energy - 0.02);
        if (this.r() < 0.1) this.idleMood(p);
        p.job = null;
      });
    });
  }

  idleMood(p) {
    if (p.energy < 0.25) this.emote(p, 'tired', 'sad', 1);
    else if (p.mood > 0.75) this.emote(p, 'happy', 'happy', 1);
    else if (p.trait === 'brave') this.emote(p, 'brave', 'wave', 0.9);
    else if (p.mood < 0.35) this.emote(p, 'grumble', 'angry', 0.9);
  }

  // ---------------------------------------------------------------- 공사 (비계 위에서 망치질)
  doBuilder(p) {
    const b = p.job.bld;
    if (!b.con) { this.loseJob(p); return; }
    const k = Math.max(0, b.builders.indexOf(p)), n = Math.max(1, b.builders.length);
    // 정면·양옆 둘레에 나눠 서기 (비계 바깥)
    const [w, d] = b.size, per = 2 * (w + d);
    const u = ((k + 0.5) / n) * per;
    let lx, lz;
    if (u < w) { lx = -w / 2 + u; lz = d / 2 + 0.75; }
    else if (u < w + d) { lx = w / 2 + 0.75; lz = d / 2 - (u - w); }
    else if (u < 2 * w + d) { lx = w / 2 - (u - w - d); lz = -d / 2 - 0.75; }
    else { lx = -w / 2 - 0.75; lz = -d / 2 + (u - 2 * w - d); }
    const spot = b.toWorld(lx, lz);
    this.walkTo(p, spot.x, spot.z, 1, { skip: b });
    this.doit(p, () => { this.setLook(p, BUILDER_LOOK); p.yaw = angTo(p.x, p.z, b.x, b.z); });
    let waitT = 0, hitT = 0;
    this.until(p, (pp, dt) => {
      if (!b.con || b.dead) { p.y = 0; this.setLook(p, p.look); this.loseJob(p); return true; }
      if (this.clock.phase !== PHASE.DAY || p.event) { p.y = 0; this.setLook(p, p.look); return true; }
      // 공사가 올라가면 비계 발판 위로
      const lvl = b.progress > 0.66 && b.height > 4 ? 2.56 : b.progress > 0.33 && b.height > 2.6 ? 1.26 : 0;
      p.y += (lvl - p.y) * Math.min(1, dt * 3);
      const ok = this.w.addWork(b, dt * (p.workRate || 1) * 1.0);
      p.energy = Math.max(0, p.energy - dt * 0.0012);
      if (!ok) {
        waitT += dt; p.jobIdle = (p.jobIdle || 0) + dt;
        if (waitT > 7) { waitT = 0; this.say(p, 'wait'); }
        if (p.jobIdle > 25 && b.type !== 'hall' && !b.free) { p.jobIdle = 0; p.y = 0; this.setLook(p, p.look); this.loseJob(p); return true; }
        return 'idle';
      }
      p.jobIdle = 0;
      hitT += dt;
      if (hitT > 0.62) {
        hitT = 0;
        const hx = p.x + Math.sin(p.yaw) * 0.6, hz = p.z + Math.cos(p.yaw) * 0.6;
        if (this.w.stage.isNear(hx, hz)) { this.w.chips(hx, p.y + 0.9, hz, 0xc89c68, 2); if (this.r() < 0.25) this.w.audio && this.w.audio.play('build', 0.25, hx, hz); }
        if (this.r() < 0.03) this.say(p, 'build');
      }
      if (!b.con) { p.y = 0; this.setLook(p, p.look); this.say(p, p.trait === 'brave' ? 'brave' : 'happy'); this.loseJob(p); return true; }
      return 'work';
    }, 'work');
  }

  // ---------------------------------------------------------------- 나무꾼·채석장
  doGather(p) {
    const b = p.job.bld, def = b.def, w = this.w;
    if (b.out >= NUM.outputCap) {
      if (p.inside !== b) { this.enterBuilding(p, b); return; }
      this.wait(p, 2); return;
    }
    const o = w.findNature(def.res, b.x, b.z, def.radius);
    if (!o) { b.noRes = true; if (p.inside !== b) this.enterBuilding(p, b); else this.wait(p, 3); return; }
    b.noRes = false;
    if (p.inside === b) this.exitBuilding(p);
    o.reserved = true;
    this.doit(p, () => this.setLook(p, def.tool));
    const ang = angTo(o.x, o.z, b.x, b.z);
    const stand = { x: o.x + Math.sin(ang) * 0.95, z: o.z + Math.cos(ang) * 0.95 };
    this.walkTo(p, stand.x, stand.z);
    const face = angTo(stand.x, stand.z, o.x, o.z);
    let hitT = 0, t = 0;
    const total = def.workTime / Math.max(0.5, p.workRate || 1);
    this.until(p, (pp, dt) => {
      t += dt; hitT += dt;
      if (hitT > 0.58) {
        hitT = 0;
        if (w.stage.isNear(o.x, o.z)) {
          w.chips(o.x, def.res === 'tree' ? 0.7 : 0.5, o.z, def.res === 'tree' ? 0x9b6a3c : 0x8c96a3, 4);
          w.audio && w.audio.play(def.res === 'tree' ? 'chop' : 'mine', 0.3, o.x, o.z);
        }
      }
      return t >= total ? true : 'work';
    }, 'work', face);
    this.doit(p, () => {
      p.energy = Math.max(0, p.energy - 0.04);
      if (!w.nature.has(o.id)) { this.enterBuilding(p, b); return; }
      if (o.type === 'tree') {
        w.fellTree(o, p.x, p.z);
        this.wait(p, 1.6, 'surprised');
        const away = angTo(p.x, p.z, o.x, o.z);
        const lx = o.x + Math.sin(away) * 2.2, lz = o.z + Math.cos(away) * 2.2;
        this.walkTo(p, lx, lz);
        this.wait(p, 0.6, 'work_hands');
      } else {
        w.mineRock(o); o.reserved = false;
      }
      this.doit(p, () => {
        this.carryItem(p, def.out);
        if (p.energy < 0.3) this.emote(p, 'tired', 'sad', 0.8); else if (this.r() < 0.18) this.idleMood(p);
        const spot = b.toWorld(-b.size[0] / 2 + 0.6, b.size[1] / 2 + 1.2);
        this.walkTo(p, spot.x, spot.z, 1, { skip: b });
        this.doit(p, () => { this.carryItem(p, null); b.out++; b.updateOutPile(); });
      });
    });
  }

  // ---------------------------------------------------------------- 밀 농장
  doFarm(p) {
    const b = p.job.bld, def = b.def, w = this.w;
    if (b.out >= NUM.outputCap) { this.wait(p, 2); return; }
    const ripe = b.plots.find((q) => q.stage === 3 && !q.reserved);
    let spot = null;
    if (!ripe && b.plots.length < def.plots) spot = w.findPlotSpot(b);
    if (!ripe && !spot) { this.wait(p, 2.5, 'idle'); return; }
    const tgt = ripe || spot;
    if (ripe) ripe.reserved = true;
    this.doit(p, () => this.setLook(p, def.tool));
    const stand = { x: tgt.x - 0.6, z: tgt.z + 0.3 };
    this.walkTo(p, stand.x, stand.z);
    this.wait(p, def.workTime / Math.max(0.5, p.workRate || 1), 'work', angTo(stand.x, stand.z, tgt.x, tgt.z));
    this.doit(p, () => {
      p.energy = Math.max(0, p.energy - 0.03);
      if (b.dead) return;
      if (ripe) {
        ripe.reserved = false; w.setPlotStage(ripe, 0); ripe.t = 0;
        w.audio && w.audio.play('harvest', 0.3, ripe.x, ripe.z);
        this.carryItem(p, def.out);
        const s = b.toWorld(-b.size[0] / 2 + 0.6, b.size[1] / 2 + 1.2);
        this.walkTo(p, s.x, s.z, 1, { skip: b });
        this.doit(p, () => { this.carryItem(p, null); b.out++; b.updateOutPile(); });
      } else w.addPlot(b, spot.x, spot.z);
    });
  }

  // ---------------------------------------------------------------- 가공 (제재소·풍차·빵집)
  doProcess(p) {
    const b = p.job.bld, def = b.def;
    if (!p.atWork) {
      const s = b.hasInterior ? b.freeSlot(['work', 'bake', 'cook', 'sell']) : null;
      if (s) {
        this.useSlot(p, b, [s.action], 0.1);
        this.doit(p, () => { p.atWork = true; p.workSlot = s; });
        return;
      }
      this.walkTo(p, b.workSpot.x, b.workSpot.z, 1, { skip: b });
      this.doit(p, () => { p.atWork = true; p.yaw = angTo(p.x, p.z, b.x, b.z); });
      return;
    }
    let t = 0, fxT = 0;
    this.until(p, (pp, dt) => {
      if (b.dead) return true;
      if (this.clock.phase !== PHASE.DAY || p.event) { p.atWork = false; if (p.lookNow !== p.look) this.setLook(p, p.look); return true; }
      t += dt; fxT += dt;
      if (b.working) {
        p.energy = Math.max(0, p.energy - dt * 0.002);
        if (def.look && p.lookNow !== def.look) this.setLook(p, def.look);
        if (fxT > 0.7) {
          fxT = 0;
          if (this.w.stage.isNear(b.x, b.z)) {
            if (b.type === 'sawmill') this.w.chips(b.x, 1.0, b.z, 0xe0c08a, 3);
            if (b.type === 'bakery') this.w.smoke(b.x + Math.sin(b.rot) * -0.5, b.height + 0.3, b.z);
          }
        }
        if (t > 10) { t = 0; if (this.r() < 0.3) this.idleMood(p); }
        return def.anim || 'work';
      }
      if (p.lookNow !== p.look) this.setLook(p, p.look);
      return t > 6 ? true : 'idle';
    }, 'idle');
  }

  // ================================================================ 필요
  tickNeeds(dt) {
    for (const p of this.list) {
      if (p.dead) continue;
      const tr = TRAITS[p.trait] || {};
      if (!p.sleeping) p.energy = Math.max(0, p.energy - dt * (p.job ? 0.0014 : 0.0005));
      let target = 0.6 + (tr.mood || 0);
      if (p.hungry) target -= 0.25;
      if (!p.home) target -= this.w.hall ? 0.12 : 0.05;
      if (p.coldNight) target -= 0.1;
      if (p.partner) target += 0.08;
      let fr = 0; for (const v of p.friends.values()) if (v > 1) fr++;
      target += Math.min(0.15, fr * 0.04);
      target += (p.joy || 0);
      p.joy = Math.max(-0.3, (p.joy || 0) - dt * 0.002 * Math.sign(p.joy || 0));
      p.mood += (Math.max(0, Math.min(1, target)) - p.mood) * dt * 0.02;
      p.workRate = (tr.work || 1) * (0.6 + 0.4 * p.energy) * (0.8 + 0.4 * p.mood);
    }
  }

  assignHomes() {
    const houses = this.w.blds.filter((b) => b.def.kind === 'house' && b.state === 'active' && !b.dead);
    const count = (h) => this.list.filter((q) => !q.dead && q.home === h).length;
    for (const p of this.list) {
      if (p.dead || (p.home && !p.home.dead)) continue;
      const fam = [p.spouse, ...p.parents].find((q) => q && !q.dead && q.home && !q.home.dead && count(q.home) < capOf(q.home));
      if (fam) { p.home = fam.home; continue; }
      let best = null, bd = Infinity;
      for (const h of houses) { if (count(h) >= capOf(h)) continue; const d = Math.hypot(h.x - p.x, h.z - p.z); if (d < bd) { bd = d; best = h; } }
      if (best) p.home = best;
    }
  }

  // ================================================================ 시간 사건
  onClock(ev) {
    if (ev === 'morning') this.morning();
    if (ev === 'season') this.news(`🌱 계절이 바뀌었어요: ${this.clock.season.name}`, 'season');
  }

  morning() {
    if ((this.clock.day - 1) % (NUM.daysPerSeason * 4) === 0) for (const p of this.list) if (!p.dead) { p.age++; if (p.stage === 'kid' && p.age >= KID_ADULT_AGE) this.growUp(p); }
    for (const p of this.list) { this.wake(p); p.coldNight = false; }
    this.assignHomes();
    const alive = this.list.filter((p) => !p.dead);
    let need = alive.length * NUM.foodPerDay;
    const s = this.w.stock;
    const eat = (t) => { const k = Math.min(s[t] || 0, Math.ceil(need)); s[t] = (s[t] || 0) - k; need -= k; };
    eat('bread'); eat('fish');
    const hungryN = Math.max(0, Math.ceil(need / NUM.foodPerDay));
    alive.forEach((p, k) => { p.hungry = k < hungryN; if (p.hungry) this.say(p, 'hungry'); });
    if (hungryN > 0) this.news(`🍞 식량이 모자라요! ${hungryN}명이 배고파요`, 'warn');
    this.w.emit('stock');
    for (const p of alive) if (p.stage === 'elder' && p.age >= ELDER_DEATH_AGE && this.r() < 0.1) { this.eventQueue.unshift({ kind: 'funeral', p }); break; }
    for (const p of alive) {
      if (p.spouse && p.gender === 'f' && p.home && this.clock.day - (p.marriedDay || 0) >= 1 && this.r() < 0.35) {
        const h = p.home, cnt = this.list.filter((q) => !q.dead && q.home === h).length;
        if (cnt < capOf(h) && this.list.filter((q) => q.parents.includes(p)).length < 3) { this.eventQueue.push({ kind: 'birth', mom: p, dad: p.spouse }); break; }
      }
    }
    this.offerDays += 1;
    if (this.w.hall && !this.offer && this.offerDays >= NUM.immigrantEvery) { this.offerDays = 0; this.makeOffer(); }
  }

  growUp(p) {
    p.stage = 'adult'; p.headY = 1.55;
    p.look = pick(LOOKS[p.gender], this.r);
    for (const d of Object.values(p.dolls)) { this.scene.remove(d.root); }
    p.dolls = {}; p.lookNow = null;
    this.setLook(p, p.look);
    this.news(`🎓 ${p.name}이(가) 어른이 되었어요`, 'info');
  }

  // ================================================================ 마을 행사
  tickEvents() {
    if (this.event || !this.eventQueue.length || this.clock.phase !== PHASE.DAY) return;
    if (this.clock.frac < 0.12 || this.clock.frac > 0.5) return;
    this.startEvent(this.eventQueue.shift());
  }

  async startEvent(e) {
    const w = this.w, hall = w.hall;
    if (!hall || hall.state !== 'active') { this.eventQueue.push(e); return; }
    this.event = e; e.t = 0;
    const plaza = hall.toWorld(0, hall.size[1] / 2 + 5);
    let center = plaza;
    e.decor = [];
    const addProp = async (k, x, z, ry) => { await w.lib.loadProp(k); const o = w.lib.prop(k); o.position.set(x, 0, z); o.rotation.y = ry; w.stage.scene.add(o); e.decor.push(o); };
    if (e.kind === 'wedding') {
      e.dur = 18; e.anim = 'dance';
      await addProp('lantern_string', plaza.x - 3, plaza.z - 1, hall.rot);
      await addProp('lantern_string', plaza.x + 3, plaza.z - 1, hall.rot);
      await addProp('picnic_table', plaza.x, plaza.z + 3.5, hall.rot);
      this.news(`🎉 ${e.a.name} ♥ ${e.b.name} 결혼식! 온 마을이 잔치를 열어요`, 'party');
      w.audio && w.audio.play('complete', 0.9);
    } else if (e.kind === 'birth') {
      const h = e.mom.home || hall;
      center = h.door;
      e.dur = 10; e.anim = 'happy';
      const kid = this.makePerson({ stage: 'kid', gender: this.r() < 0.5 ? 'm' : 'f', x: h.door.x, z: h.door.z, parents: [e.mom, e.dad] });
      kid.home = h; kid.age = 0; e.kid = kid;
      this.news(`👶 ${e.mom.name}와(과) ${e.dad.name}에게 아기 ${kid.name}이(가) 태어났어요!`, 'party');
      w.audio && w.audio.play('coin', 0.8);
    } else if (e.kind === 'funeral') {
      const p = e.p;
      const g = hall.toWorld(hall.size[0] / 2 + 6, -hall.size[1] / 2 + (this.graves || 0) * 1.4);
      this.graves = (this.graves || 0) + 1;
      w.makeGrave(g.x, g.z, hall.rot);
      center = { x: g.x, z: g.z + 1.5 };
      e.dur = 14; e.anim = 'sad';
      p.dead = true; this.loseJob(p);
      for (const d of Object.values(p.dolls)) this.scene.remove(d.root);
      if (p.spouse) { p.spouse.spouse = null; p.spouse.joy = -0.3; }
      if (p.partner) p.partner.partner = null;
      this.list.splice(this.list.indexOf(p), 1);
      this.news(`🕯️ ${p.name}(${p.age}세)이(가) 세상을 떠났어요. 마을 사람들이 장례식을 열어요`, 'sad');
    }
    e.center = center;
    const who = this.list.filter((q) => !q.dead && !q.leaving && !(q.sleeping));
    who.forEach((q, k) => {
      if (q.job) this.loseJob(q);
      if (q.slot) this.leaveSlot(q);
      if (q.inside) { const b = q.inside; q.inside = null; if (q.hidden) this.show(q, b.door.x, b.door.z); }
      q.chatting = null; q.y = 0;
      if (q.lookNow !== q.look) this.setLook(q, q.look);
      this.clearQ(q);
      q.event = e;
      const main = (e.kind === 'wedding' && (q === e.a || q === e.b)) || (e.kind === 'birth' && (q === e.mom || q === e.dad || q === e.kid));
      let pos;
      if (main) pos = { x: center.x + (q === e.a || q === e.mom ? -0.5 : q === e.kid ? 0 : 0.5), z: center.z + (q === e.kid ? 0.6 : 0) };
      else { const a = (k / Math.max(1, who.length)) * Math.PI * 2 + 0.3, rr = 2.8 + (k % 2) * 1.0; pos = { x: center.x + Math.cos(a) * rr, z: center.z + Math.sin(a) * rr }; }
      this.walkTo(q, pos.x, pos.z, 1.15);
      this.doit(q, () => { q.yaw = angTo(q.x, q.z, center.x, center.z); });
      q.eventAnim = main && e.kind === 'wedding' ? 'happy' : e.anim;
    });
    e.who = who;
  }

  updateEvent(dt) {
    const e = this.event;
    if (e.t == null) return;
    e.t += dt;
    if (Math.floor(e.t * 1.2) !== Math.floor((e.t - dt) * 1.2)) {
      const q = e.who[Math.floor(this.r() * e.who.length)];
      if (q && !q.dead) this.say(q, e.kind === 'funeral' ? 'sad' : 'party', true);
      if (e.kind === 'wedding' && this.r() < 0.6) this.w.puff(e.center.x, e.center.z, [0xff8fb5, 0xffe066, 0x8fd3ff][Math.floor(this.r() * 3)], 4, 2.5, 1.8);
    }
    if (e.t < e.dur) return;
    for (const q of e.who) { if (q.dead) continue; q.event = null; q.eventAnim = null; q.joy = Math.max(-0.3, Math.min(0.3, (q.joy || 0) + (e.kind === 'funeral' ? -0.12 : 0.2))); this.clearQ(q); }
    if (e.kind === 'wedding') {
      e.a.spouse = e.b; e.b.spouse = e.a; e.a.marriedDay = e.b.marriedDay = this.clock.day;
      const h = e.a.home || e.b.home; if (h) { e.a.home = h; e.b.home = h; }
      this.news(`💒 ${e.a.name}와(과) ${e.b.name}이(가) 부부가 되었어요`, 'love');
    }
    for (const d of e.decor || []) this.scene.remove(d);
    this.event = null;
  }

  // ================================================================ 이주민
  makeOffer() {
    const n = 2 + Math.floor(this.r() * 2), ppl = [];
    for (let k = 0; k < n; k++) {
      const g = this.r() < 0.5 ? 'm' : 'f';
      const used = new Set(this.list.map((p) => p.name).concat(ppl.map((q) => q.name)));
      const names = NAMES[g].filter((x) => !used.has(x));
      ppl.push({ gender: g, name: pick(names.length ? names : NAMES[g], this.r), trait: pick(Object.keys(TRAITS), this.r), age: 18 + Math.floor(this.r() * 20), look: pick(LOOKS[g], this.r) });
    }
    if (n >= 3 && this.r() < 0.5) { ppl[2].stage = 'kid'; ppl[2].age = 0; ppl[2].look = pick(ppl[2].gender === 'm' ? LOOKS.kidM : LOOKS.kidF, this.r); }
    this.offer = { ppl };
    this.w.emit('offer', this.offer);
  }

  async answerOffer(yes) {
    const o = this.offer; if (!o) return;
    this.offer = null;
    if (!yes) { this.news('👋 이주민들이 다른 마을로 떠났어요', 'info'); return; }
    const w = this.w;
    await Promise.all(o.ppl.map((d) => this.lib.loadChar(d.look)));
    const ex = w.size - 2, ez = w.size / 2 + (this.r() - 0.5) * 30;
    const made = o.ppl.map((d, k) => this.makePerson(Object.assign({ x: ex - k * 0.8, z: ez + k * 0.5 }, d)));
    const adults = made.filter((p) => p.stage === 'adult');
    if (adults.length >= 2 && this.compatible(adults[0], adults[1])) { adults[0].partner = adults[1]; adults[1].partner = adults[0]; }
    for (const p of made) { p.leaving = true; const t = this.near(w.hall, 4); this.walkTo(p, t.x, t.z); this.doit(p, () => { p.leaving = false; this.emote(p, 'happy', 'wave', 1.2); }); }
    const spot = w.findHouseSpot();
    if (spot) {
      const h = await w.place('house', spot.x, spot.z, spot.rot, { free: true });
      for (const p of made) p.home = h;
      for (const p of adults) { p.job = { kind: 'builder', bld: h, x: h.x, z: h.z }; h.builders.push(p); }
      this.news(`🏡 이주민 ${made.map((p) => p.name).join(', ')}이(가) 마을에 왔어요. 직접 오두막을 짓는대요`, 'party');
      return;
    }
    this.news(`🏡 이주민 ${made.map((p) => p.name).join(', ')}이(가) 마을에 왔어요`, 'party');
  }

  // ================================================================ 시작: 마차와 정착
  startCaravan(x, z) {
    const plan = [
      { gender: 'm', look: 'npc_young_man', trait: 'brave' }, { gender: 'f', look: 'npc_aunt', trait: 'cheerful' },
      { gender: 'm', look: 'npc_uncle', trait: 'grumpy' }, { gender: 'f', look: 'npc_herbalist', trait: 'shy' },
      { gender: 'm', look: 'npc_blacksmith', trait: 'diligent' }, { gender: 'f', look: 'npc_red', trait: 'lazy' },
      { gender: 'm', look: 'npc_yellow', trait: 'cheerful' }, { gender: 'f', look: 'npc_fashion', trait: 'brave' },
      { gender: 'm', look: 'npc_blue', trait: 'diligent' }, { gender: 'f', look: 'npc_teen_girl', trait: 'cheerful' },
      { gender: 'm', look: 'npc_bard', trait: 'shy' }, { gender: 'm', look: 'npc_merchant', trait: 'lazy' },
      { gender: 'm', stage: 'elder', trait: 'diligent' }, { gender: 'f', stage: 'elder', trait: 'cheerful' },
    ];
    plan.forEach((d, k) => { const a = (k / plan.length) * Math.PI * 2; this.makePerson(Object.assign({ x: x + Math.cos(a) * 3.5, z: z + 2 + Math.sin(a) * 2.2 }, d)); });
    const [g1, g2] = this.list.filter((p) => p.stage === 'elder');
    if (g1 && g2) { g1.spouse = g2; g2.spouse = g1; }
  }
  settle(hall) {
    for (const p of this.list) {
      if (p.stage !== 'adult') continue;
      this.clearQ(p);
      p.job = { kind: 'builder', bld: hall, x: hall.x, z: hall.z };
      hall.builders.push(p);
    }
  }
  unloadWagon(hall, wagon) {
    const ad = this.list.filter((p) => p.stage === 'adult' && !p.job).slice(0, 5);
    const types = ['plank', 'fish', 'stone', 'log', 'plank'];
    ad.forEach((p, k) => {
      this.clearQ(p);
      this.walkTo(p, wagon.x + (k - 2) * 0.7, wagon.z + 1.6);
      this.doit(p, () => this.carryItem(p, types[k]));
      this.walkTo(p, hall.door.x, hall.door.z);
      this.doit(p, () => { this.carryItem(p, null); if (k === 0) this.emote(p, 'brave', 'wave'); });
    });
  }

  describe(p) {
    const tr = TRAITS[p.trait] || { name: '' };
    const j = p.job;
    let job = '쉬는 중';
    if (p.stage === 'kid') job = '아이 (노는 중)';
    else if (p.stage === 'elder') job = '어르신 (쉬는 중)';
    else if (j) job = j.kind === 'haul' ? `짐 나르기 (${j.task.type ? ({ log: '통나무', plank: '판자', stone: '돌', wheat: '밀', flour: '밀가루', bread: '빵', fish: '생선' })[j.task.type] : ''})` : j.kind === 'builder' ? `공사 (${j.bld.name})` : `${j.bld.name} 일꾼`;
    if (p.sleeping) job += ' · 자는 중';
    else if (p.slot) job += ` · ${({ sit: '앉아 쉬는 중', eat: '먹는 중', tea: '차 마시는 중', read: '책 읽는 중', desk: '책상에서 일하는 중', cook: '요리하는 중', bake: '빵 굽는 중', toilet: '화장실', wash: '씻는 중', warm: '불 쬐는 중' })[p.slot.s.action] || '쉬는 중'}`;
    const mood = p.mood > 0.75 ? '😊 아주 좋음' : p.mood > 0.55 ? '🙂 좋음' : p.mood > 0.35 ? '😐 보통' : '😣 나쁨';
    const energy = p.energy > 0.6 ? '💪 넉넉' : p.energy > 0.3 ? '🙂 보통' : '😓 지침';
    let best = null, bv = 0;
    for (const [id, v] of p.friends) if (v > bv) { const q = this.list.find((x) => x.id === id); if (q) { bv = v; best = q; } }
    return {
      name: p.name, look: p.look, sub: `${p.gender === 'm' ? '남' : '여'} · ${p.age}세 · 성격: ${tr.name}`,
      rows: [
        ['하는 일', job], ['기분', mood + (p.hungry ? ' (배고픔)' : '')], ['기운', energy],
        ['집', p.home ? p.home.name : (this.w.hall ? '없음 (마을회관에서 잠)' : '마차')],
        ['가족', p.spouse ? `배우자 ${p.spouse.name}` : p.partner ? `연인 ${p.partner.name} 💕` : '혼자'],
        ['친한 친구', best ? best.name : '아직 없음'],
      ],
    };
  }
}

function capOf(b) { return b.def.kind === 'house' ? b.def.levels[b.level].cap : 0; }
function turn(a, b, k) { let d = b - a; while (d > Math.PI) d -= Math.PI * 2; while (d < -Math.PI) d += Math.PI * 2; return a + d * Math.min(1, k); }
export { BUILDINGS, THREE };
