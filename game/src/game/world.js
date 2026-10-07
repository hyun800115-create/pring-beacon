// 세계: 자연(숲·바위·덤불, 많이 그리기), 건물 놓기 규칙, 길, 창고와 물건 나르기 일감(물류), 효과.

import * as THREE from 'three';
import { Pool } from '../render/models.js';
import { RoadNet } from './roads.js';
import { Building } from './buildings.js';
import { BUILDINGS, ITEMS, NUM, ROADS } from './defs.js';

const CELL = 6;   // 공간 격자(m)

export class Rng {
  constructor(seed) { this.s = seed >>> 0 || 1; }
  next() { let x = this.s; x ^= x << 13; x ^= x >>> 17; x ^= x << 5; this.s = x >>> 0; return this.s / 4294967296; }
  range(a, b) { return a + (b - a) * this.next(); }
}

export class World {
  constructor(stage, lib, opts = {}) {
    this.stage = stage; this.lib = lib;
    this.size = NUM.mapSize;
    this.rng = new Rng(opts.seed || 20261007);
    this.nid = 1;
    this.blds = []; this.hall = null; this.wagon = null;
    this.stock = Object.assign({}, NUM.start);
    this.nature = new Map();          // id -> 자연물
    this.grid = new Map();            // "cx,cz" -> Set(id)
    this.pools = {};
    this.tasks = [];                  // 나르기 일감
    this.roads = new RoadNet(stage.scene);
    this.listeners = {};
    this.stats = { breadMade: 0 };
    this.itemTpl = {};
  }

  on(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  emit(ev, a, b) { for (const f of this.listeners[ev] || []) f(a, b); }

  // ---------------------------------------------------------------- 자연
  async loadNature() {
    const keys = ['tree_pine_a', 'tree_pine_b', 'tree_pine_snow', 'tree_stump', 'rock_ore', 'rock_ore_b', 'bush_snow', 'snow_pile_b', 'snow_pile_a'];
    await Promise.all(keys.map((k) => this.lib.loadProp(k)));
    for (const k of keys) this.pools[k] = new Pool(this.stage.scene, this.lib.props[k], k.startsWith('tree_pine') ? 3000 : 800, !k.startsWith('snow_pile'));
  }

  cellKey(x, z) { return Math.floor(x / CELL) + ',' + Math.floor(z / CELL); }
  addNature(type, model, x, z, ry, sc, extra) {
    const o = Object.assign({ id: this.nid++, type, model, x, z, ry, sc, reserved: false }, extra || {});
    this.nature.set(o.id, o);
    const k = this.cellKey(x, z);
    if (!this.grid.has(k)) this.grid.set(k, new Set());
    this.grid.get(k).add(o.id);
    this.pools[model].add(o.id, x, z, ry, sc);
    return o;
  }
  removeNature(o) {
    if (!this.nature.has(o.id)) return;
    this.nature.delete(o.id);
    const s = this.grid.get(this.cellKey(o.x, o.z)); if (s) s.delete(o.id);
    this.pools[o.model].remove(o.id);
  }
  natureNear(x, z, r, fn) {
    const c0 = Math.floor((x - r) / CELL), c1 = Math.floor((x + r) / CELL), d0 = Math.floor((z - r) / CELL), d1 = Math.floor((z + r) / CELL);
    for (let cx = c0; cx <= c1; cx++) for (let cz = d0; cz <= d1; cz++) {
      const s = this.grid.get(cx + ',' + cz); if (!s) continue;
      for (const id of s) { const o = this.nature.get(id); if (o && Math.hypot(o.x - x, o.z - z) <= r) fn(o); }
    }
  }
  findNature(type, x, z, r) {
    let best = null, bd = Infinity;
    this.natureNear(x, z, r, (o) => { if (o.type === type && !o.reserved) { const d = Math.hypot(o.x - x, o.z - z); if (d < bd) { bd = d; best = o; } } });
    return best;
  }

  generate(start) {
    const r = this.rng, S = this.size;
    this.start = start;
    const clearR = 13;
    const blob = (cx, cz, rad, kind, dens) => {
      for (let k = 0; k < rad * rad * dens; k++) {
        const a = r.range(0, Math.PI * 2), d = Math.sqrt(r.next()) * rad;
        const x = cx + Math.cos(a) * d, z = cz + Math.sin(a) * d;
        if (x < 2 || z < 2 || x > S - 2 || z > S - 2 || Math.hypot(x - start.x, z - start.z) < clearR) continue;
        let near = false;
        this.natureNear(x, z, kind === 'tree' ? 1.5 : 2.2, () => { near = true; });
        if (near) continue;
        if (kind === 'tree') this.addNature('tree', ['tree_pine_a', 'tree_pine_b', 'tree_pine_snow'][Math.floor(r.next() * 3)], x, z, r.range(0, 6.28), r.range(0.85, 1.25));
        else this.addNature('rock', r.next() < 0.5 ? 'rock_ore' : 'rock_ore_b', x, z, r.range(0, 6.28), r.range(0.8, 1.15), { amount: NUM.rockAmount });
      }
    };
    for (let k = 0; k < 22; k++) {
      const a = r.range(0, Math.PI * 2), d = r.range(24, S * 0.55);
      blob(start.x + Math.cos(a) * d, start.z + Math.sin(a) * d, r.range(7, 15), 'tree', 0.32);
    }
    blob(start.x + 22, start.z - 10, 9, 'tree', 0.4);
    blob(start.x - 14, start.z + 22, 9, 'tree', 0.4);
    blob(start.x - 20, start.z - 18, 4, 'rock', 0.35);
    blob(start.x + 18, start.z + 20, 4, 'rock', 0.35);
    blob(start.x + 40, start.z + 35, 5, 'rock', 0.3);
    for (let k = 0; k < 220; k++) {
      const x = r.range(3, S - 3), z = r.range(3, S - 3);
      if (Math.hypot(x - start.x, z - start.z) < 8) continue;
      this.addNature('bush', r.next() < 0.55 ? 'bush_snow' : (r.next() < 0.5 ? 'snow_pile_b' : 'snow_pile_a'), x, z, r.range(0, 6.28), r.range(0.7, 1.1));
    }
    this.treeTarget = [...this.nature.values()].filter((o) => o.type === 'tree').length;
  }

  /** 나무 쓰러뜨리기 (보이는 효과) → 그루터기 */
  fellTree(o, fromX, fromZ) {
    this.removeNature(o);
    const tpl = this.lib.props[o.model];
    if (tpl) {
      const t = tpl.clone(true);
      t.position.set(o.x, 0, o.z); t.rotation.y = o.ry; t.scale.setScalar(o.sc);
      const pivot = new THREE.Group(); pivot.position.set(o.x, 0, o.z);
      t.position.set(0, 0, 0);
      const away = Math.atan2(o.x - fromX, o.z - fromZ);
      pivot.rotation.y = away; t.rotation.y = o.ry - away;
      pivot.add(t);
      this.stage.scene.add(pivot);
      this.fx.push({ t: 0, dur: 2.6, upd: (k) => { const e = Math.min(1, k * 1.6); pivot.rotation.x = (Math.PI / 2 - 0.08) * e * e; if (k > 0.75) t.traverse((m) => { if (m.isMesh) { m.material = m.material.clone(); m.material.transparent = true; m.material.opacity = 1 - (k - 0.75) / 0.25; } }); }, end: () => this.stage.scene.remove(pivot) });
      this.puff(o.x + Math.sin(away) * 3, o.z + Math.cos(away) * 3, 0xf4f7fb, 10, 1.4);
    }
    this.addNature('stump', 'tree_stump', o.x, o.z, o.ry, o.sc * 0.9, { t: NUM.stumpTime });
  }
  mineRock(o) {
    o.amount--;
    const sc = o.sc * (0.45 + 0.55 * o.amount / NUM.rockAmount);
    this.pools[o.model].set(o.id, o.x, 0, o.z, o.ry, sc);
    if (o.amount <= 0) this.removeNature(o);
  }

  regrow(dt) {
    this.regrowT = (this.regrowT || 0) + dt;
    if (this.regrowT < NUM.regrowEvery) return;
    this.regrowT = 0;
    for (const o of [...this.nature.values()]) if (o.type === 'stump') { o.t -= NUM.regrowEvery; if (o.t <= 0) this.removeNature(o); }
    let trees = 0; for (const o of this.nature.values()) if (o.type === 'tree') trees++;
    if (trees >= this.treeTarget) return;
    const all = [...this.nature.values()].filter((o) => o.type === 'tree');
    for (let k = 0; k < 20; k++) {
      const t = all[Math.floor(this.rng.next() * all.length)]; if (!t) return;
      const x = t.x + this.rng.range(-4, 4), z = t.z + this.rng.range(-4, 4);
      if (!this.freeSpot(x, z, 1.4)) continue;
      const o = this.addNature('tree', t.model, x, z, this.rng.range(0, 6.28), 0.2);
      o.grow = 0.2; o.target = this.rng.range(0.85, 1.2);
      return;
    }
  }
  growTrees(dt) {
    for (const o of this.nature.values()) if (o.grow != null && o.grow < o.target) { o.grow = Math.min(o.target, o.grow + dt * 0.02); o.sc = o.grow; this.pools[o.model].set(o.id, o.x, 0, o.z, o.ry, o.sc); if (o.grow >= o.target) o.grow = null; }
  }

  freeSpot(x, z, r) {
    if (x < 1 || z < 1 || x > this.size - 1 || z > this.size - 1) return false;
    let ok = true;
    this.natureNear(x, z, r, (o) => { if (o.type !== 'bush') ok = false; });
    if (!ok) return false;
    for (const b of this.blds) if (b.contains(x, z, r)) return false;
    if (this.roads.onRoad(x, z, r * 0.5)) return false;
    return true;
  }

  // ---------------------------------------------------------------- 건물 놓기
  check(type, x, z, rot, area) {
    const def = BUILDINGS[type];
    const [w, d] = def.size;
    const c = Math.cos(rot), s = Math.sin(rot);
    const pts = [];
    for (let i = 0; i <= 4; i++) for (let j = 0; j <= 4; j++) { const lx = (i / 4 - 0.5) * w, lz = (j / 4 - 0.5) * d; pts.push({ x: x + lx * c + lz * s, z: z - lx * s + lz * c }); }
    for (const p of pts) {
      if (p.x < 1 || p.z < 1 || p.x > this.size - 1 || p.z > this.size - 1) return { ok: false, why: '지도 밖이에요' };
      if (area && Math.hypot(p.x - area.x, p.z - area.z) > area.r) return { ok: false, why: '마차에서 너무 멀어요' };
    }
    const tmp = { size: def.size, x, z, rot };
    for (const b of this.blds) {
      if (b.dead) continue;
      if (obbOverlap(tmp, b, 0.6)) return { ok: false, why: `${b.name}과(와) 겹쳐요` };
    }
    for (const p of pts) if (this.roads.onRoad(p.x, p.z, 0.1)) return { ok: false, why: '길 위에는 지을 수 없어요' };
    if (this.wagon && Math.hypot(this.wagon.x - x, this.wagon.z - z) < Math.max(w, d) / 2 + 2.5 && type !== 'hall') return { ok: false, why: '마차와 겹쳐요' };
    let rocks = 0;
    for (const p of pts) this.natureNear(p.x, p.z, 0.8, (o) => { if (o.type === 'rock') rocks++; });
    if (rocks) return { ok: false, why: '바위가 있어요' };
    return { ok: true };
  }

  async place(type, x, z, rot, opts = {}) {
    const b = new Building(this, type, x, z, rot, opts);
    // 자리의 나무·덤불·그루터기 치우기
    const r = Math.hypot(b.size[0], b.size[1]) / 2 + 1;
    const gone = [];
    this.natureNear(x, z, r, (o) => { if (b.contains(o.x, o.z, 0.8) && o.type !== 'rock') gone.push(o); });
    for (const o of gone) this.removeNature(o);
    this.blds.push(b);
    if (BUILDINGS[type].kind === 'hq') this.hall = b;
    if (opts.instant) { b.state = 'active'; await b.buildVisual(); }
    else { await b.buildVisual(); b.startSite(); }
    this.emit('bld', b);
    return b;
  }

  remove(b) {
    if (b.def.kind === 'hq' || b.dead) return false;
    b.dead = true;
    for (const p of b.plots) this.removePlot(p);
    b.dispose();
    this.blds.splice(this.blds.indexOf(b), 1);
    // 남은 재료·결과물은 창고로
    if (b.con) for (const t in b.con.have) this.stock[t] = (this.stock[t] || 0) + (b.con.have[t] - (b.con.used[t] || 0));
    if (b.def.kind === 'process' && b.def.in) this.stock[b.def.in] = (this.stock[b.def.in] || 0) + b.inputs;
    if (b.def.out) this.stock[b.def.out] = (this.stock[b.def.out] || 0) + b.out;
    this.tasks = this.tasks.filter((t) => { if (t.to === b || t.from === b) { if (t.carrier) t.cancel = true; return false; } return true; });
    this.emit('removed', b);
    this.emit('stock');
    return true;
  }

  // ---------------------------------------------------------------- 공사
  conFraction(b) {
    const c = b.con; if (!c) return 1;
    let need = 0, have = 0;
    for (const t in c.need) { need += c.need[t]; have += Math.min(c.need[t], c.have[t] || 0); }
    return need ? have / need : 1;
  }
  /** 망치질: 재료가 온 만큼만 올라간다 */
  addWork(b, dt) {
    const c = b.con; if (!c) return false;
    const cap = this.conFraction(b) * c.workNeeded;
    if (c.work >= cap - 1e-6) return false;
    c.work = Math.min(cap, c.work + dt);
    // 쓴 재료 표시 (더미에서 줄어듦)
    const p = c.work / c.workNeeded;
    for (const t in c.need) c.used[t] = Math.min(c.have[t] || 0, Math.floor(c.need[t] * p + 1e-6));
    b.updatePile();
    b.setProgress(p);
    if (c.work >= c.workNeeded - 1e-6 && this.conFraction(b) >= 1) this.finish(b);
    return true;
  }
  async finish(b) {
    const kind = b.con ? b.con.kind : 'build';
    if (kind === 'upgrade') { b.level++; b.con = null; b.state = 'active'; b.clearSite(); await b.buildVisual(); }
    else b.finish();
    this.puff(b.x, b.z, 0xffffff, 26, Math.max(b.size[0], b.size[1]) * 0.6);
    this.emit('built', b, kind);
  }
  upgrade(b) {
    const next = b.def.levels && b.def.levels[b.level + 1];
    if (!next || b.con || b.state !== 'active') return false;
    b.con = { kind: 'upgrade', need: Object.assign({}, next.cost), have: {}, used: {}, work: 0, workNeeded: (b.def.work || 8) * 1.2 };
    b.makeSiteVisual();
    if (b.scaffold) b.scaffold.visible = true;
    this.emit('bld', b);
    return true;
  }

  // ---------------------------------------------------------------- 물건·물류
  itemModel(t) {
    const it = ITEMS[t];
    if (it.model && this.lib.props[it.model]) { const o = this.lib.prop(it.model); o.scale.setScalar((it.scale || 1) * 0.9); return o; }
    if (!this.itemTpl[t]) {
      const g = new THREE.Group();
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.17, 10, 8), new THREE.MeshStandardMaterial({ color: it.color || 0xcccccc, roughness: 0.9 }));
      m.scale.set(1, 0.85, 0.8); m.position.y = 0.15; m.castShadow = true; g.add(m);
      const tie = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.09, 0.1, 8), new THREE.MeshStandardMaterial({ color: it.color || 0xcccccc })); tie.position.y = 0.32; g.add(tie);
      this.itemTpl[t] = g;
    }
    return this.itemTpl[t].clone(true);
  }

  /** 이 건물이 더 받아야 하는 물건 수 (오는 중인 것 빼고) */
  wants(b, t) {
    if (b.dead) return 0;
    const coming = this.tasks.filter((k) => k.to === b && k.type === t).length;
    if (b.con) return Math.max(0, (b.con.need[t] || 0) - (b.con.have[t] || 0) - coming);
    if (b.state === 'active' && b.def.kind === 'process' && b.def.in === t) return Math.max(0, NUM.inputCap - b.inputs - coming);
    return 0;
  }

  /** 나르기 일감 만들기: 결과물 → 필요한 곳 또는 창고, 창고 → 필요한 곳 */
  logistics() {
    const hall = this.hall && this.hall.state === 'active' && !this.hall.dead ? this.hall : null;
    if (!hall) return;
    const open = (from, to, type) => this.tasks.push({ id: this.nid++, from, to, type, carrier: null });
    // 1) 건물의 결과물 내보내기
    for (const b of this.blds) {
      if (b.dead || !b.def.out || b.state !== 'active') continue;
      const leaving = this.tasks.filter((k) => k.from === b).length;
      let avail = b.out - leaving;
      while (avail > 0) {
        let best = null, bd = Infinity;
        for (const c of this.blds) { if (c === b || this.wants(c, b.def.out) <= 0) continue; const d = Math.hypot(c.x - b.x, c.z - b.z); if (d < bd) { bd = d; best = c; } }
        open(b, best || hall, b.def.out);
        avail--;
      }
    }
    // 2) 창고에서 꺼내 보내기
    for (const b of this.blds) {
      if (b === hall || b.dead) continue;
      const types = b.con ? Object.keys(b.con.need) : (b.def.kind === 'process' && b.state === 'active' ? [b.def.in] : []);
      for (const t of types) {
        let n = Math.min(this.wants(b, t), Math.floor(this.stock[t] || 0) - this.tasks.filter((k) => k.from === hall && k.type === t).length);
        while (n-- > 0) open(hall, b, t);
      }
    }
  }

  /** 짐 내리기 */
  deliver(type, b) {
    if (!b || b.dead) { this.stock[type] = (this.stock[type] || 0) + 1; this.emit('stock'); return; }
    if (b.con && (b.con.need[type] || 0) > (b.con.have[type] || 0)) { b.con.have[type] = (b.con.have[type] || 0) + 1; b.updatePile(); this.emit('bld', b); return; }
    if (b.def.kind === 'process' && b.def.in === type && b.state === 'active') { b.inputs++; this.emit('bld', b); return; }
    this.stock[type] = (this.stock[type] || 0) + 1;
    if (type === 'bread') this.stats.breadIn = (this.stats.breadIn || 0) + 1;
    this.emit('stock');
  }
  /** 짐 들기 (출발지에서 꺼내기) */
  take(type, b) {
    if (b === this.hall) { if ((this.stock[type] || 0) <= 0) return false; this.stock[type]--; this.emit('stock'); return true; }
    if (b.out <= 0) return false;
    b.out--; b.updateOutPile();
    return true;
  }

  // ---------------------------------------------------------------- 밭
  addPlot(b, x, z) {
    const p = { b, x, z, stage: 0, t: 0, reserved: false };
    p.obj = this.lib.prop('crop_wheat_0');
    p.obj.position.set(x, 0, z); p.obj.rotation.y = b.rot; p.obj.scale.setScalar(0.78);
    this.stage.scene.add(p.obj);
    b.plots.push(p);
    return p;
  }
  setPlotStage(p, st) {
    p.stage = st;
    this.stage.scene.remove(p.obj);
    p.obj = this.lib.prop('crop_wheat_' + st);
    p.obj.position.set(p.x, 0, p.z); p.obj.rotation.y = p.b.rot; p.obj.scale.setScalar(0.78);
    this.stage.scene.add(p.obj);
  }
  removePlot(p) { this.stage.scene.remove(p.obj); }
  findPlotSpot(b) {
    for (let k = 0; k < 40; k++) {
      // 농장 앞쪽과 옆에 1.2m 간격 격자
      const gx = (k % 6) - 2.5, gz = Math.floor(k / 6);
      const lx = gx * 1.25, lz = b.size[1] / 2 + 2.0 + gz * 1.25;
      const p = b.toWorld(lx, lz);
      if (b.plots.some((q) => Math.hypot(q.x - p.x, q.z - p.z) < 1)) continue;
      if (!this.freeSpot(p.x, p.z, 0.6)) continue;
      return p;
    }
    return null;
  }

  // ---------------------------------------------------------------- 효과 (조각·먼지·연기)
  initFx() {
    this.fx = [];
    this.partMat = {};
    this.partGeo = new THREE.SphereGeometry(0.08, 6, 4);
  }
  puff(x, z, color, n = 8, spread = 0.6, y = 0.3) {
    if (!this.partMat[color]) this.partMat[color] = new THREE.MeshStandardMaterial({ color, roughness: 1, transparent: true });
    for (let k = 0; k < n; k++) {
      const m = new THREE.Mesh(this.partGeo, this.partMat[color].clone());
      const a = Math.random() * Math.PI * 2, r = Math.random() * spread;
      m.position.set(x + Math.cos(a) * r, y + Math.random() * 0.4, z + Math.sin(a) * r);
      const v = new THREE.Vector3(Math.cos(a) * 0.6, 0.8 + Math.random() * 0.8, Math.sin(a) * 0.6);
      const s = 1 + Math.random() * 2.5;
      m.scale.setScalar(s);
      this.stage.scene.add(m);
      this.fx.push({ t: 0, dur: 0.9 + Math.random() * 0.6, upd: (u, dt) => { m.position.addScaledVector(v, dt); v.y -= dt * 0.6; m.scale.setScalar(s * (1 + u)); m.material.opacity = 1 - u; }, end: () => { this.stage.scene.remove(m); m.material.dispose(); } });
    }
  }
  chips(x, y, z, color = 0x9b6a3c, n = 5) {
    if (!this.partMat['c' + color]) this.partMat['c' + color] = new THREE.MeshStandardMaterial({ color, roughness: 0.8 });
    for (let k = 0; k < n; k++) {
      const m = new THREE.Mesh(this.partGeo, this.partMat['c' + color]);
      m.scale.set(0.6, 0.3, 0.9);
      m.position.set(x, y, z);
      const v = new THREE.Vector3((Math.random() - 0.5) * 3, 1.5 + Math.random() * 2, (Math.random() - 0.5) * 3);
      this.stage.scene.add(m);
      this.fx.push({ t: 0, dur: 0.8, upd: (u, dt) => { m.position.addScaledVector(v, dt); v.y -= dt * 9; if (m.position.y < 0.03) { m.position.y = 0.03; v.set(0, 0, 0); } m.rotation.x += dt * 8; }, end: () => this.stage.scene.remove(m) });
    }
  }
  smoke(x, y, z) { this.puff(x, z, 0xc9ced6, 1, 0.1, y); }
  updateFx(dt) {
    for (let i = this.fx.length - 1; i >= 0; i--) {
      const f = this.fx[i]; f.t += dt;
      const u = Math.min(1, f.t / f.dur);
      f.upd(u, dt);
      if (u >= 1) { f.end && f.end(); this.fx.splice(i, 1); }
    }
  }

  /** 이주민 집 자리: 기존 집·마을회관 근처, 길을 바라보게 */
  findHouseSpot() {
    const anchors = this.blds.filter((b) => (b.def.kind === 'house' || b.def.kind === 'hq') && !b.dead);
    const cands = [];
    for (const a of anchors) {
      for (let k = 0; k < 40; k++) {
        const ang = this.rng.range(0, Math.PI * 2), d = this.rng.range(7, 16);
        const x = a.x + Math.cos(ang) * d, z = a.z + Math.sin(ang) * d;
        const e = this.roads.near(x, z, 20, 1)[0];
        const rot = e ? Math.atan2(e.x - x, e.z - z) : Math.atan2(a.x - x, a.z - z);
        if (this.check('house', x, z, rot).ok) cands.push({ x, z, rot, score: d + this.rng.next() * 3 });
      }
    }
    cands.sort((p, q) => p.score - q.score);
    return cands[0] || null;
  }

  makeGrave(x, z, rot) {
    const g = new THREE.Group();
    const stone = new THREE.MeshStandardMaterial({ color: 0x9aa3ae, roughness: 0.9 });
    const s = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.8, 0.18), stone); s.position.y = 0.4; s.castShadow = true; g.add(s);
    const top = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.18, 16, 1, false, 0, Math.PI), stone); top.rotation.set(Math.PI / 2, 0, Math.PI / 2); top.position.y = 0.8; g.add(top);
    const fl = [0xf28fb0, 0xffe07a, 0xffffff];
    for (let k = 0; k < 5; k++) { const f = new THREE.Mesh(new THREE.SphereGeometry(0.07, 6, 4), new THREE.MeshStandardMaterial({ color: fl[k % 3] })); f.position.set(-0.3 + k * 0.15, 0.06, 0.25); g.add(f); }
    g.position.set(x, 0, z); g.rotation.y = rot;
    this.stage.scene.add(g);
  }

  /** 건물을 피해 가는 점 추가 (눈밭 걷기용, 간단한 우회) */
  detour(fx, fz, tx, tz, skip) {
    for (const b of this.blds) {
      if (b.dead || b === skip || b.contains(fx, fz, 0.3) || b.contains(tx, tz, 0.3)) continue;
      if (!segHitsBox(fx, fz, tx, tz, b, 0.5)) continue;
      const cs = b.corners(1.1);
      let best = null, bd = Infinity;
      for (const c of cs) { const d = Math.hypot(c.x - fx, c.z - fz) + Math.hypot(tx - c.x, tz - c.z); if (d < bd && !segHitsBox(fx, fz, c.x, c.z, b, 0.4)) { bd = d; best = c; } }
      if (best) return [best];
    }
    return [];
  }
}

function obbOverlap(a, b, m) {
  // 분리축 검사 (2D 회전 사각형)
  const ax = axes(a), bx = axes(b);
  for (const ax2 of [...ax, ...bx]) {
    const pa = proj(a, ax2, m / 2), pb = proj(b, ax2, m / 2);
    if (pa[1] < pb[0] || pb[1] < pa[0]) return false;
  }
  return true;
}
function axes(o) { const c = Math.cos(o.rot), s = Math.sin(o.rot); return [{ x: c, z: -s }, { x: s, z: c }]; }
function proj(o, ax, m) {
  const c = Math.cos(o.rot), s = Math.sin(o.rot), hw = o.size[0] / 2 + m, hd = o.size[1] / 2 + m;
  const pts = [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(([a, b]) => ({ x: o.x + a * c + b * s, z: o.z - a * s + b * c }));
  const v = pts.map((p) => p.x * ax.x + p.z * ax.z);
  return [Math.min(...v), Math.max(...v)];
}
function segHitsBox(ax, az, bx, bz, b, m) {
  const n = Math.ceil(Math.hypot(bx - ax, bz - az) / 0.5);
  for (let i = 1; i < n; i++) { const t = i / n; if (b.contains(ax + (bx - ax) * t, az + (bz - az) * t, m)) return true; }
  return false;
}

export { ROADS };
