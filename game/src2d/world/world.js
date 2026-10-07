// 세계: 지도, 깃발·길, 물건, 건물(공사·생산), 물류(어디서 어디로 나를지).
// 주민 행동은 people.js, 시간은 clock.js, 화면·입력은 scenes/Play.js.

import { Iso } from '../core/iso.js';
import { Assets } from '../core/assets.js';
import { GridMap, Rng } from './map.js';
import { ITEMS, BUILDINGS, NUM } from '../data/defs.js';

const CH = 8;   // 화면 밖 그림 숨기기용 구역 크기(칸)

export class World {
  constructor(scene, opts = {}) {
    this.scene = scene;
    this.perf = !!opts.perf;
    this.n = opts.n || 64;
    this.iso = new Iso(this.n);
    this.map = new GridMap(this.n);
    this.rng = new Rng(opts.seed || 20261007);
    this.flags = []; this.roads = []; this.blds = []; this.items = []; this.plots = [];
    this.people = null;            // People (people.js) 가 채운다
    this.hall = null;
    this.wagon = null;
    this.stock = Object.assign({}, NUM.start);   // 마차/마을회관 창고
    this.nid = 1;
    this.distCache = new Map();
    this.logT = 0; this.regrowT = 0;
    this.treeTarget = 0;
    this.stats = { breadMade: 0 };
    this.listeners = {};
    this.chunkN = Math.ceil(this.n / CH);
    this.chunks = Array.from({ length: this.chunkN * this.chunkN }, () => new Set());
    this.chunkVis = new Uint8Array(this.chunkN * this.chunkN).fill(1);
  }

  on(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  emit(ev, a, b) { for (const f of this.listeners[ev] || []) f(a, b); }
  W(i, j) { return this.iso.toWorld(i, j); }

  // ---------------------------------------------------------------- 그림 등록 (화면 밖 숨기기)
  chunkOf(i, j) {
    const ci = Math.max(0, Math.min(this.chunkN - 1, Math.floor(i / CH)));
    const cj = Math.max(0, Math.min(this.chunkN - 1, Math.floor(j / CH)));
    return cj * this.chunkN + ci;
  }
  addStatic(spr, i, j) {
    const c = this.chunkOf(i, j);
    this.chunks[c].add(spr); spr.__c = c;
    spr.setVisible(!!this.chunkVis[c]);
    return spr;
  }
  killStatic(spr) {
    if (!spr) return;
    if (spr.__c != null) this.chunks[spr.__c].delete(spr);
    spr.destroy();
  }
  sprite(atlas, frame, x, y, i, j, scale = 1) {
    const [k, f, ax, ay] = Assets.tex(this.scene, atlas, frame);
    const s = this.scene.add.image(x, y, k, f).setOrigin(ax, ay).setScale(scale).setDepth(y);
    return this.addStatic(s, i, j);
  }

  // ---------------------------------------------------------------- 지도 만들기
  generate() {
    const n = this.n, r = this.rng, map = this.map;
    const c = Math.floor(n / 2);
    this.startTile = { i: c - 2, j: c + 2 };
    const clear = (i, j) => Math.hypot(i - this.startTile.i, j - this.startTile.j) < (this.perf ? 0 : 11);
    const blobs = [];
    const nb = this.perf ? 70 : 9;
    for (let k = 0; k < nb; k++) {
      const a = r.range(0, Math.PI * 2), d = this.perf ? r.range(0, n * 0.6) : r.range(15, n * 0.45);
      blobs.push({ i: c + Math.cos(a) * d, j: c + Math.sin(a) * d, rad: r.range(3, 7), kind: 'tree' });
    }
    if (!this.perf) {   // 처음부터 가까이에 숲과 바위가 있도록
      blobs.push({ i: c + 12, j: c + 8, rad: 5, kind: 'tree' }, { i: c - 6, j: c - 13, rad: 5, kind: 'tree' });
      blobs.push({ i: c + 11, j: c - 9, rad: 2.6, kind: 'rock' }, { i: c - 14, j: c + 10, rad: 2.4, kind: 'rock' }, { i: c + 18, j: c + 16, rad: 3, kind: 'rock' });
    } else {
      for (let k = 0; k < 18; k++) blobs.push({ i: r.range(5, n - 5), j: r.range(5, n - 5), rad: r.range(2, 3.5), kind: 'rock' });
    }
    for (const b of blobs) {
      for (let j = Math.floor(b.j - b.rad); j <= b.j + b.rad; j++) for (let i = Math.floor(b.i - b.rad); i <= b.i + b.rad; i++) {
        if (!map.inb(i, j) || clear(i, j) || map.objAt(i, j)) continue;
        const d = Math.hypot(i - b.i, j - b.j) / b.rad;
        if (d > 1) continue;
        if (b.kind === 'tree' && r.next() < 0.78 - d * 0.35) this.addTree(i, j, false);
        if (b.kind === 'rock' && r.next() < 0.55 - d * 0.3) this.addRock(i, j);
      }
    }
    for (let k = 0; k < n * n * 0.012; k++) {
      const i = r.int(1, n - 2), j = r.int(1, n - 2);
      if (!map.objAt(i, j) && !clear(i, j)) this.addBush(i, j);
    }
    this.treeTarget = this.countTrees();
  }

  countTrees() { let k = 0; for (const o of this.map.obj) if (o && o.type === 'tree') k++; return k; }

  addTree(i, j, grow) {
    const p = this.W(i + this.rng.range(-0.18, 0.18), j + this.rng.range(-0.18, 0.18));
    const f = ['tree_pine_a', 'tree_pine_b', 'tree_pine_snow'][this.rng.int(0, 2)];
    const spr = this.sprite('props_nature', f, p.x, p.y, i, j, this.rng.range(0.82, 1.0));
    const o = { type: 'tree', i, j, x: p.x, y: p.y, spr, reserved: false };
    this.map.setObj(i, j, o);
    if (grow) { const s = spr.scale; spr.setScale(s * 0.2); this.scene.tweens.add({ targets: spr, scale: s, duration: 4000, ease: 'Sine.out' }); }
    return o;
  }
  addRock(i, j) {
    const p = this.W(i, j);
    const f = this.rng.next() < 0.5 ? 'rock_ore' : 'rock_ore_b';
    const spr = this.sprite('props_nature', f, p.x, p.y, i, j, 0.78);
    const o = { type: 'rock', i, j, x: p.x, y: p.y, spr, amount: NUM.rockAmount, reserved: false };
    this.map.setObj(i, j, o);
    return o;
  }
  addBush(i, j) {
    const p = this.W(i + this.rng.range(-0.2, 0.2), j + this.rng.range(-0.2, 0.2));
    const f = this.rng.next() < 0.6 ? 'bush_snow' : 'snow_pile_b';
    const spr = this.sprite('props_nature', f, p.x, p.y, i, j, this.rng.range(0.55, 0.8));
    this.map.setObj(i, j, { type: 'bush', i, j, spr });
  }
  clearBush(i, j) {
    const o = this.map.objAt(i, j);
    if (o && o.type === 'bush') { this.killStatic(o.spr); this.map.setObj(i, j, null); }
  }

  /** 나무 베기 → 그루터기 */
  chopTree(o) {
    this.killStatic(o.spr);
    const spr = this.sprite('props_nature', 'tree_stump', o.x, o.y, o.i, o.j, 0.85);
    this.map.setObj(o.i, o.j, { type: 'stump', i: o.i, j: o.j, spr, t: NUM.stumpTime });
  }
  /** 바위 깨기 */
  mineRock(o) {
    o.amount--;
    o.spr.setScale(0.5 + 0.28 * (o.amount / NUM.rockAmount));
    if (o.amount <= 0) { this.killStatic(o.spr); this.map.setObj(o.i, o.j, null); }
  }

  // ---------------------------------------------------------------- 깃발
  canFlag(i, j) {
    const m = this.map, o = m.occAt(i, j);
    if (!m.inb(i, j)) return false;
    if (o && o.type !== 'road') return false;
    const ob = m.objAt(i, j);
    if (ob && ob.type !== 'bush') return false;
    return !m.flagNear(i, j);
  }
  flagAt(i, j) { const o = this.map.occAt(i, j); return o && o.type === 'flag' ? o.ref : null; }

  /** 깃발 꽂기. 길 위면 길을 둘로 나눈다. */
  placeFlag(i, j) {
    if (!this.canFlag(i, j)) return null;
    const o = this.map.occAt(i, j);
    if (o && o.type === 'road') return this.splitRoad(o.ref, i, j);
    return this.addFlag(i, j);
  }
  addFlag(i, j) {
    this.clearBush(i, j);
    const p = this.W(i, j);
    const f = { id: this.nid++, i, j, x: p.x, y: p.y, items: [], roads: [], bld: null, incoming: 0 };
    f.spr = this.sprite('gen_flag', null, p.x, p.y, i, j, 0.9);
    this.map.setOcc(i, j, { type: 'flag', ref: f });
    this.flags.push(f);
    this.dirty();
    return f;
  }
  removeFlag(f) {
    if (f.dead) return;
    if (f.bld) { this.removeBuilding(f.bld); return; }
    for (const r of f.roads.slice()) this.removeRoad(r);
    for (const it of f.items.slice()) this.killItem(it);
    f.dead = true;
    this.killStatic(f.spr);
    this.map.setOcc(f.i, f.j, null);
    this.flags.splice(this.flags.indexOf(f), 1);
    this.dirty();
  }

  // ---------------------------------------------------------------- 길
  /** 길 경로 미리보기: 시작 깃발에서 (i,j)까지. 반환 {path, ok} */
  planRoad(f, i, j) {
    const path = this.map.findRoad(f.i, f.j, i, j, NUM.maxRoad);
    if (!path || path.length < 2) return { path: null, ok: false };
    const end = path[path.length - 1], eo = this.map.occAt(end[0], end[1]);
    let ok = true;
    if (!(eo && eo.type === 'flag')) ok = this.canFlag(end[0], end[1]);
    if (eo && eo.type === 'flag' && eo.ref === f) ok = false;
    if (path.length === 2 && !(eo && eo.type === 'flag')) ok = false;     // 깃발끼리 붙을 수 없음
    if (eo && eo.type === 'flag' && f.roads.some((r) => r.a === eo.ref || r.b === eo.ref) && path.length === 2) ok = false;
    return { path, ok };
  }

  /** 길 만들기 (경로 첫 칸은 깃발). 자동 깃발을 꽂고 깃발 사이마다 길 한 토막. */
  buildRoad(path, autoFlags = true) {
    const m = this.map;
    const start = this.flagAt(path[0][0], path[0][1]);
    if (!start) return null;
    const last = path[path.length - 1];
    let end = this.flagAt(last[0], last[1]);
    if (!end) end = this.placeFlag(last[0], last[1]);
    if (!end) return null;
    for (let k = 1; k < path.length - 1; k++) {
      if (!m.isFree(path[k][0], path[k][1])) return null;
    }
    // 중간 깃발
    const cut = [0];
    if (autoFlags) {
      let lastCut = 0;
      for (let k = 1; k < path.length - 1; k++) {
        if (k - lastCut >= NUM.autoFlagEvery && path.length - 1 - k >= 2) {
          const [i, j] = path[k];
          if (this.canFlag(i, j)) { this.addFlag(i, j); cut.push(k); lastCut = k; }
        }
      }
    }
    cut.push(path.length - 1);
    const made = [];
    for (let s = 0; s < cut.length - 1; s++) made.push(this.makeRoad(path.slice(cut[s], cut[s + 1] + 1)));
    return made;
  }

  makeRoad(tiles) {
    const a = this.flagAt(tiles[0][0], tiles[0][1]), b = this.flagAt(tiles[tiles.length - 1][0], tiles[tiles.length - 1][1]);
    const r = { id: this.nid++, a, b, tiles, len: tiles.length - 1, carrier: null };
    r.pts = tiles.map(([i, j]) => this.W(i, j));
    for (let k = 1; k < tiles.length - 1; k++) { this.clearBush(tiles[k][0], tiles[k][1]); this.map.setOcc(tiles[k][0], tiles[k][1], { type: 'road', ref: r }); }
    a.roads.push(r); b.roads.push(r);
    this.roads.push(r);
    this.dirty();
    this.emit('roads');
    return r;
  }

  removeRoad(r) {
    if (r.dead) return;
    r.dead = true;
    for (let k = 1; k < r.tiles.length - 1; k++) this.map.setOcc(r.tiles[k][0], r.tiles[k][1], null);
    r.a.roads.splice(r.a.roads.indexOf(r), 1);
    r.b.roads.splice(r.b.roads.indexOf(r), 1);
    this.roads.splice(this.roads.indexOf(r), 1);
    if (r.carrier && this.people) this.people.loseJob(r.carrier);
    for (const it of this.items) if (it.road === r) it.road = null;
    this.dirty();
    this.emit('roads');
  }

  splitRoad(r, i, j) {
    const k = r.tiles.findIndex(([a, b]) => a === i && b === j);
    if (k <= 0 || k >= r.tiles.length - 1) return null;
    const tiles = r.tiles, carrier = r.carrier;
    if (carrier && this.people) this.people.loseJob(carrier);
    this.removeRoad(r);
    const f = this.addFlag(i, j);
    this.makeRoad(tiles.slice(0, k + 1));
    this.makeRoad(tiles.slice(k));
    return f;
  }

  other(r, f) { return r.a === f ? r.b : r.a; }

  // ---------------------------------------------------------------- 길 찾기 (깃발 그래프)
  dirty() { this.distCache.clear(); this.emit('dirty'); }

  distTo(dest) {
    let d = this.distCache.get(dest.id);
    if (d) return d;
    d = new Map([[dest.id, 0]]);
    const open = [dest];
    while (open.length) {
      let bi = 0;
      for (let k = 1; k < open.length; k++) if (d.get(open[k].id) < d.get(open[bi].id)) bi = k;
      const f = open[bi]; open[bi] = open[open.length - 1]; open.pop();
      const df = d.get(f.id);
      for (const r of f.roads) {
        const o = this.other(r, f), nd = df + r.len;
        if (nd < (d.has(o.id) ? d.get(o.id) : Infinity)) { d.set(o.id, nd); open.push(o); }
      }
    }
    this.distCache.set(dest.id, d);
    return d;
  }
  dist(a, b) { const d = this.distTo(b).get(a.id); return d == null ? Infinity : d; }
  nextRoad(from, dest) {
    if (from === dest) return null;
    const d = this.distTo(dest);
    let best = null, bv = Infinity;
    for (const r of from.roads) {
      const o = this.other(r, from), v = d.has(o.id) ? r.len + d.get(o.id) : Infinity;
      if (v < bv) { bv = v; best = r; }
    }
    return best;
  }

  // ---------------------------------------------------------------- 물건
  itemSprite(type) {
    const t = ITEMS[type].tex;
    const [k, f, ax, ay] = Assets.tex(this.scene, t[0], t[1]);
    return this.scene.add.image(0, 0, k, f).setOrigin(ax, ay).setScale(0.5);
  }
  newItem(type, flag, dest) {
    const it = { id: this.nid++, type, flag: null, dest: dest || null, carrier: null, road: null };
    it.spr = this.itemSprite(type);
    this.items.push(it);
    if (flag) this.putItem(it, flag);
    return it;
  }
  putItem(it, flag) {
    it.flag = flag; it.carrier = null;
    flag.items.push(it);
    this.layoutFlag(flag);
    it.road = it.dest ? this.nextRoad(flag, it.dest.flag) : null;
  }
  takeItem(it) {
    const f = it.flag;
    if (!f) return;
    f.items.splice(f.items.indexOf(it), 1);
    it.flag = null;
    this.layoutFlag(f);
  }
  killItem(it) {
    if (it.flag) this.takeItem(it);
    const k = this.items.indexOf(it);
    if (k >= 0) this.items.splice(k, 1);
    it.dead = true;
    it.spr.destroy();
  }
  layoutFlag(f) {
    const vis = this.chunkVis[this.chunkOf(f.i, f.j)];
    f.items.forEach((it, k) => {
      const a = -2.2 + k * 0.78, rr = 20 + (k % 2) * 6;
      const x = f.x + Math.cos(a) * rr * 1.25 + 10, y = f.y + Math.sin(a) * rr * 0.55 + 6;
      it.spr.setPosition(x, y).setDepth(y).setScale(0.48).setVisible(!!vis);
      it.spr.__fx = true;
    });
  }

  /** 물건을 건물 안으로 넣기 */
  deliver(it, b) {
    const t = it.type;
    this.killItem(it);
    if (b.dead) return;
    if (b.con && b.con.need[t] > (b.con.have[t] || 0)) { b.con.have[t] = (b.con.have[t] || 0) + 1; this.emit('bld', b); return; }
    if (b.def.kind === 'hq') { this.stock[t] = (this.stock[t] || 0) + 1; this.emit('stock'); return; }
    if (b.def.kind === 'process' && b.def.in === t) { b.inputs = (b.inputs || 0) + 1; this.emit('bld', b); return; }
    if (this.hall && !this.hall.dead) { this.stock[t] = (this.stock[t] || 0) + 1; this.emit('stock'); }
  }

  // ---------------------------------------------------------------- 건물
  footprint(type, bi, bj) {
    const s = BUILDINGS[type].size;
    const fi = bi + Math.floor((s - 1) / 2), fj = bj - 1;
    return { s, fi, fj };
  }
  /** 이 자리에 지을 수 있나 (bi,bj = 건물 앞 왼쪽 칸) */
  canBuild(type, bi, bj, area) {
    const { s, fi, fj } = this.footprint(type, bi, bj);
    const m = this.map;
    for (let j = bj; j < bj + s; j++) for (let i = bi; i < bi + s; i++) {
      if (!m.isFree(i, j)) return false;
      if (area && Math.hypot(i - area.i, j - area.j) > area.r) return false;
    }
    const fo = m.occAt(fi, fj);
    if (fo && fo.type === 'flag') return !fo.ref.bld;
    return this.canFlag(fi, fj);
  }
  /** 화면에서 누른 칸 → 건물 자리 (누른 칸이 건물 가운데쯤 오게) */
  originFor(type, ti, tj) {
    const s = BUILDINGS[type].size;
    return { bi: ti - Math.floor((s - 1) / 2), bj: tj - Math.floor((s - 1) / 2) };
  }

  placeBuilding(type, bi, bj, opts = {}) {
    const def = BUILDINGS[type];
    const { s, fi, fj } = this.footprint(type, bi, bj);
    let flag = this.flagAt(fi, fj) || this.placeFlag(fi, fj);
    if (!flag) return null;
    const cti = bi + (s - 1) / 2, ctj = bj + (s - 1) / 2;
    const c = this.W(cti, ctj);
    const b = {
      id: this.nid++, type, def, bi, bj, s, cti, ctj, x: c.x, y: c.y, flag, level: 0,
      door: this.W(fi, bj - 0.45), state: 'site', worker: null, builders: [], residents: [],
      inputs: 0, out: 0, busy: false, working: false, t: 0, plots: [], sprs: [],
      label: def.name, free: !!opts.free,
    };
    b.work = this.W(cti + s * 0.18, bj - 0.75);   // 일하는 자리 (건물 앞 오른쪽)
    flag.bld = b;
    for (let j = bj; j < bj + s; j++) for (let i = bi; i < bi + s; i++) { this.clearBush(i, j); this.map.setOcc(i, j, { type: 'bld', ref: b }); }
    this.blds.push(b);
    if (def.kind === 'hq') this.hall = b;
    if (opts.instant) { this.finishCon(b, true); }
    else {
      b.con = { kind: 'build', need: opts.free ? {} : Object.assign({}, def.cost || {}), have: {}, work: 0, workNeeded: def.buildTime || 8 };
      this.drawSite(b);
    }
    this.dirty();
    this.emit('bld', b);
    return b;
  }

  levelDef(b) { return b.def.levels ? b.def.levels[b.level] : null; }

  drawSprites(b) {
    for (const s of b.sprs) this.killStatic(s);
    b.sprs = [];
    const lv = this.levelDef(b);
    const sp = lv ? lv.sprite : b.def.sprite;
    const sc = lv && lv.scale ? lv.scale : 1;
    const main = this.sprite(sp[0], sp[1], b.x, b.y, b.cti, b.ctj, sc);
    b.spr = main;
    b.sprs.push(main);
    for (const d of (b.def.decor || []).concat(lv && lv.extra ? lv.extra : [])) {
      const p = this.W(b.bi + d[2], b.bj + d[3]);
      b.sprs.push(this.sprite(d[0], d[1], p.x, p.y, b.cti, b.ctj, d[4] || 1));
    }
    if (b.type === 'windmill') {
      const bl = this.scene.add.image(b.x + 1, b.y - 172, 'gen_windmill_blades').setDepth(b.y + 1).setScale(0.95);
      this.addStatic(bl, b.cti, b.ctj);
      b.blades = bl; b.sprs.push(bl);
    }
  }

  drawSite(b) {
    this.drawSprites(b);
    for (const s of b.sprs) s.setAlpha(0.25);
    const g = this.scene.add.graphics().setDepth(-14000);
    const d = this.iso.diamond(b.cti, b.ctj, (b.s - 1) / 2 + 0.05);
    g.fillStyle(0x9c7a58, 0.55); g.fillPoints(d, true);
    g.lineStyle(3, 0x6e5238, 0.8); g.strokePoints(d, true);
    this.addStatic(g, b.cti, b.ctj);
    b.siteG = g;
    for (const p of d) b.sprs.push(this.sprite('gen_stake', null, p.x, p.y, b.cti, b.ctj, 1).setOrigin(0.5, 1));
  }

  /** 공사 진행 비율 (재료 도착 비율과 망치질 비율 중 작은 것) */
  conProgress(b) {
    const c = b.con;
    if (!c) return 1;
    let need = 0, have = 0;
    for (const t in c.need) { need += c.need[t]; have += Math.min(c.need[t], c.have[t] || 0); }
    const mat = need ? have / need : 1;
    return Math.min(mat, c.work / c.workNeeded);
  }
  conMaterialsDone(b) {
    const c = b.con;
    for (const t in c.need) if ((c.have[t] || 0) < c.need[t]) return false;
    return true;
  }
  /** 망치질 (공사 일꾼이 부른다) */
  addConWork(b, dt) {
    const c = b.con;
    if (!c) return;
    let need = 0, have = 0;
    for (const t in c.need) { need += c.need[t]; have += Math.min(c.need[t], c.have[t] || 0); }
    const cap = (need ? have / need : 1) * c.workNeeded;
    c.work = Math.min(cap, c.work + dt);
    const p = this.conProgress(b);
    if (c.kind === 'build' && b.spr) {
      for (const s of b.sprs) s.setAlpha(0.25);
      const h = b.spr.height, w = b.spr.width;
      if (!b.real) {
        const sp = b.spr;
        const r = this.scene.add.image(sp.x, sp.y, sp.texture.key, sp.frame.name).setOrigin(sp.originX, sp.originY).setScale(sp.scaleX).setDepth(sp.depth + 0.5);
        this.addStatic(r, b.cti, b.ctj); b.real = r; b.sprs.push(r);
      }
      b.real.setCrop(0, h * (1 - p), w, h * p + 1);
    }
    if (c.work >= c.workNeeded && this.conMaterialsDone(b)) this.finishCon(b);
  }

  finishCon(b, silent) {
    const c = b.con;
    b.con = null;
    if (b.siteG) { this.killStatic(b.siteG); b.siteG = null; }
    b.real = null;
    if (c && c.kind === 'upgrade') b.level++;
    b.state = 'active';
    this.drawSprites(b);
    if (b.def.kind === 'farm') this.initPlots(b);
    if (!silent) { Assets.play(this.scene, 'sfx_complete', 0.8); this.emit('built', b, c ? c.kind : 'build'); }
    this.emit('bld', b);
  }

  upgradeHouse(b) {
    if (b.def.kind !== 'house' || b.con || b.state !== 'active') return false;
    const next = b.def.levels[b.level + 1];
    if (!next) return false;
    b.con = { kind: 'upgrade', need: Object.assign({}, next.cost), have: {}, work: 0, workNeeded: 8 };
    this.emit('bld', b);
    return true;
  }

  capacity(b) {
    if (b.def.kind === 'house') return b.def.levels[b.level].cap;
    if (b.def.kind === 'hq') return b.def.sleeps;
    return 0;
  }

  removeBuilding(b) {
    if (b.dead || b.def.kind === 'hq') return false;
    b.dead = true;
    for (const s of b.sprs) this.killStatic(s);
    if (b.siteG) this.killStatic(b.siteG);
    for (const p of b.plots) { this.killStatic(p.spr); this.map.setOcc(p.i, p.j, null); }
    for (let j = b.bj; j < b.bj + b.s; j++) for (let i = b.bi; i < b.bi + b.s; i++) this.map.setOcc(i, j, null);
    this.blds.splice(this.blds.indexOf(b), 1);
    b.flag.bld = null;
    for (const it of this.items) if (it.dest === b) it.dest = this.hall;
    if (this.people) this.people.buildingGone(b);
    this.dirty();
    this.emit('bld', b);
    return true;
  }

  // ---------------------------------------------------------------- 밀밭
  initPlots(b) { b.plotWanted = b.def.plots; }
  findPlotSpot(b) {
    const R = b.def.radius, cands = [];
    for (let j = Math.floor(b.ctj - R - 1); j <= b.ctj + R + 1; j++) for (let i = Math.floor(b.cti - R - 1); i <= b.cti + R + 1; i++) {
      if (!this.map.isFree(i, j, false) || this.map.flagNear(i, j)) continue;
      const d = Math.hypot(i - b.cti, j - b.ctj);
      if (d <= R + 0.5) cands.push([d, i, j]);
    }
    cands.sort((a, c) => a[0] - c[0]);
    return cands.length ? { i: cands[0][1], j: cands[0][2] } : null;
  }
  addPlot(b, i, j) {
    const p = this.W(i, j);
    const plot = { b, i, j, x: p.x, y: p.y, stage: 0, t: 0, reserved: false };
    plot.spr = this.sprite('props_nature', 'crop_wheat_0', p.x, p.y, i, j, 0.78);
    plot.spr.setDepth(p.y - 40);
    this.map.setOcc(i, j, { type: 'plot', ref: plot });
    b.plots.push(plot);
    return plot;
  }
  setPlotStage(plot, st) {
    plot.stage = st;
    const [k, f] = Assets.tex(this.scene, 'props_nature', 'crop_wheat_' + st);
    plot.spr.setTexture(k, f);
  }

  // ---------------------------------------------------------------- 매 프레임
  update(dt, working) {
    // 밀 자라기, 그루터기 없어지기
    for (const b of this.blds) for (const p of b.plots) {
      if (p.stage < 3) { p.t += dt; const st = Math.min(3, Math.floor(p.t / (b.def.grow / 3))); if (st !== p.stage) this.setPlotStage(p, st); }
    }
    this.regrowT += dt;
    if (this.regrowT > NUM.regrowEvery) { this.regrowT = 0; this.regrow(); }
    for (const b of this.blds) this.updateBuilding(b, dt, working);
    this.logT += dt;
    if (this.logT > 0.4) { this.logT = 0; this.logistics(); }
  }

  regrow() {
    const m = this.map;
    for (let k = 0; k < m.obj.length; k++) {
      const o = m.obj[k];
      if (o && o.type === 'stump') { o.t -= NUM.regrowEvery; if (o.t <= 0) { this.killStatic(o.spr); m.obj[k] = null; } }
    }
    if (this.countTrees() >= this.treeTarget) return;
    for (let tries = 0; tries < 30; tries++) {
      const k = this.rng.int(0, m.obj.length - 1), o = m.obj[k];
      if (!o || o.type !== 'tree') continue;
      const i = o.i + this.rng.int(-2, 2), j = o.j + this.rng.int(-2, 2);
      if (m.isFree(i, j, false) && !m.flagNear(i, j)) { this.addTree(i, j, true); return; }
    }
  }

  updateBuilding(b, dt, working) {
    if (b.state !== 'active' || b.dead) return;
    const def = b.def;
    // 결과물을 깃발에 내놓기
    if (b.out > 0 && b.flag.items.length < NUM.flagCap && def.out) {
      b.out--;
      const it = this.newItem(def.out, null, null);
      it.spr.setPosition(b.door.x, b.door.y);
      this.putItem(it, b.flag);
      if (def.out === 'bread') this.stats.breadMade++;
    }
    if (def.kind === 'process') {
      const here = b.worker && b.worker.atWork && working;
      if (b.working) {
        if (here) b.t += dt * (b.worker.workRate || 1);
        if (b.t >= def.time) { b.working = false; b.out += def.outN || 1; this.emit('bld', b); }
      } else if (here && b.inputs > 0 && b.out < NUM.outputCap) {
        b.inputs--; b.working = true; b.t = 0;
        if (def.sfx && this.scene.isVisible(b.x, b.y)) Assets.play(this.scene, def.sfx, 0.35);
        this.emit('bld', b);
      }
      const active = b.working && here;
      if (b.type === 'windmill' && b.blades) b.blades.rotation += dt * (active ? 2.2 : 0.08);
      this.setWorkAnim(b, active);
    }
  }

  /** 가공 건물의 작업 동작(불·연기·톱날)을 켜고 끄기 */
  setWorkAnim(b, on) {
    if (b.animOn === on || !b.spr) return;
    b.animOn = on;
    const key = 'work:' + (b.def.sprite[1] || '');
    if (!this.scene.anims.exists(key)) return;
    const old = b.spr;
    if (on) {
      const s = this.scene.add.sprite(old.x, old.y, old.texture.key, old.frame.name).setOrigin(old.originX, old.originY).setDepth(old.depth);
      s.play(key);
      this.addStatic(s, b.cti, b.ctj);
      old.setVisible(false); old.__hide = true;
      b.animSpr = s; b.sprs.push(s);
    } else if (b.animSpr) {
      b.sprs.splice(b.sprs.indexOf(b.animSpr), 1);
      this.killStatic(b.animSpr); b.animSpr = null;
      old.__hide = false; old.setVisible(!!this.chunkVis[old.__c]);
    }
  }

  // ---------------------------------------------------------------- 물류
  /** 이 건물이 지금 더 받고 싶은 물건 수 */
  wants(b, t, enroute) {
    if (b.dead) return 0;
    const e = enroute.get(b.id + ':' + t) || 0;
    if (b.con) return Math.max(0, (b.con.need[t] || 0) - (b.con.have[t] || 0) - e);
    if (b.state === 'active' && b.def.kind === 'process' && b.def.in === t) return Math.max(0, NUM.inputCap - b.inputs - (b.working ? 0 : 0) - e);
    return 0;
  }

  logistics() {
    const hall = this.hall && !this.hall.dead && this.hall.state === 'active' ? this.hall : null;
    const enroute = new Map();
    for (const it of this.items) if (it.dest && !it.dest.perf) { const k = it.dest.id + ':' + it.type; enroute.set(k, (enroute.get(k) || 0) + 1); }
    // 1) 갈 곳 없는 물건 → 마을회관, 마을회관행 물건 중 필요한 곳이 있으면 그쪽으로
    for (const it of this.items) {
      if (it.dest && it.dest.dead) it.dest = null;
      if (!it.dest && hall) it.dest = hall;
      if (it.dest === hall && it.flag) {
        let best = null, bd = Infinity;
        for (const b of this.blds) {
          if (b === hall || this.wants(b, it.type, enroute) <= 0) continue;
          const d = this.dist(it.flag, b.flag);
          if (d < bd) { bd = d; best = b; }
        }
        if (best) {
          it.dest = best;
          const k = best.id + ':' + it.type; enroute.set(k, (enroute.get(k) || 0) + 1);
        }
      }
    }
    // 2) 마을회관 창고에서 꺼내 보내기
    if (hall) {
      let pulls = 0;
      for (const b of this.blds) {
        if (b === hall || pulls >= 3) continue;
        const types = b.con ? Object.keys(b.con.need) : (b.def.kind === 'process' && b.state === 'active' ? [b.def.in] : []);
        for (const t of types) {
          if (pulls >= 3 || hall.flag.items.length >= NUM.flagCap - 3) break;
          if ((this.stock[t] || 0) <= 0 || this.wants(b, t, enroute) <= 0) continue;
          if (this.dist(hall.flag, b.flag) === Infinity) continue;
          this.stock[t]--;
          const it = this.newItem(t, null, b);
          it.spr.setPosition(hall.door.x, hall.door.y);
          this.putItem(it, hall.flag);
          const k = b.id + ':' + t; enroute.set(k, (enroute.get(k) || 0) + 1);
          pulls++;
          this.emit('stock');
        }
      }
    }
    // 3) 깃발 위 물건의 다음 길 정하기, 도착한 물건은 건물로
    for (const it of this.items.slice()) {
      if (!it.flag || it.carrier) continue;
      if (!it.dest) { it.road = null; continue; }
      if (it.flag === it.dest.flag) {
        if (it.dest.perf) { this.emit('perfArrive', it); continue; }
        const b = it.dest;
        this.takeItem(it);
        it.carrier = 'tween';
        this.scene.tweens.add({ targets: it.spr, x: b.door.x, y: b.door.y, duration: 300, onComplete: () => this.deliver(it, b) });
        continue;
      }
      it.road = this.nextRoad(it.flag, it.dest.flag);
    }
  }

  /** 짐꾼이 집어 갈 물건 (길 r 의 양 끝 깃발에서) */
  pickFor(r) {
    for (const end of [r.a, r.b]) {
      const to = this.other(r, end);
      for (const it of end.items) {
        if (it.road !== r || it.carrier) continue;
        const into = it.dest && !it.dest.perf && it.dest.flag === to;
        if (!into && to.items.length + to.incoming >= NUM.flagCap) {
          // 맞바꾸기: 반대편에 이쪽으로 올 물건이 있으면 한 칸 넘쳐도 가져간다 (정체 풀기)
          const back = to.items.some((x) => x.road === r && !x.carrier);
          if (!back || to.items.length + to.incoming >= NUM.flagCap + 2) continue;
        }
        return { it, from: end, to, into };
      }
    }
    return null;
  }

  // ---------------------------------------------------------------- 집 자리 찾기 (이주민)
  findHouseSpot() {
    const anchors = this.blds.filter((b) => b.def.kind === 'house' || b.def.kind === 'hq');
    const cands = [];
    for (const a of anchors) {
      for (let dj = -6; dj <= 6; dj++) for (let di = -6; di <= 6; di++) {
        const bi = Math.round(a.cti) + di, bj = Math.round(a.ctj) + dj;
        if (!this.canBuild('house', bi, bj)) continue;
        // 다른 건물과 한 칸 띄우기
        let ok = true;
        for (let j = bj - 1; j <= bj + 2 && ok; j++) for (let i = bi - 1; i <= bi + 2; i++) { const o = this.map.occAt(i, j); if (o && o.type === 'bld') { ok = false; break; } }
        if (!ok) continue;
        cands.push([Math.hypot(di, dj) + this.rng.next() * 1.5, bi, bj]);
      }
    }
    cands.sort((a, b) => a[0] - b[0]);
    return cands.length ? { bi: cands[0][1], bj: cands[0][2] } : null;
  }
}
