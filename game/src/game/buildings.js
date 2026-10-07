// 건물: 위치·회전, 모습(실내 모델 또는 서리마을 소품), 공사 현장(터·비계·재료 더미·아래에서 위로 올라가는 건물),
// 실내 보기(지붕·벽 숨기기), 상호작용 자리(slot), 결과물 더미.

import * as THREE from 'three';
import { BUILDINGS, ITEMS } from './defs.js';

const UP = new THREE.Vector3(0, 1, 0);

export class Building {
  constructor(world, type, x, z, rot, opts = {}) {
    this.w = world; this.type = type; this.def = BUILDINGS[type];
    this.id = world.nid++;
    this.x = x; this.z = z; this.rot = rot;
    this.size = this.def.size.slice();
    this.level = 0;
    this.state = 'site';
    this.free = !!opts.free;
    this.builders = []; this.worker = null; this.residents = [];
    this.inputs = 0; this.out = 0; this.working = false; this.t = 0;
    this.plots = []; this.slots = []; this.reserved = new Set();
    this.group = new THREE.Group();
    this.group.position.set(x, 0, z);
    this.group.rotation.y = rot;
    this.group.userData.bld = this;
    world.stage.scene.add(this.group);
    this.cutaway = false; this.pinned = false;
    this.door = this.toWorld(0, this.size[1] / 2 + 0.9);
    this.doorIn = this.toWorld(0, this.size[1] / 2 - 0.6);
    this.workSpot = this.toWorld(this.size[0] * 0.25, this.size[1] / 2 + 0.7);
  }

  get name() { const lv = this.levelDef; return lv ? lv.name : this.def.name; }
  get levelDef() { return this.def.levels ? this.def.levels[this.level] : null; }
  get modelKey() { const lv = this.levelDef; return lv ? lv.key : this.type; }
  get height() { return this.def.height || 4; }

  /** 건물 좌표(정면 +z) → 세계 좌표 */
  toWorld(lx, lz) {
    const c = Math.cos(this.rot), s = Math.sin(this.rot);
    return { x: this.x + lx * c + lz * s, z: this.z - lx * s + lz * c };
  }
  toLocal(x, z) {
    const dx = x - this.x, dz = z - this.z, c = Math.cos(this.rot), s = Math.sin(this.rot);
    return { x: dx * c - dz * s, z: dx * s + dz * c };
  }
  /** 발자국 안인가 (여유 m) */
  contains(x, z, m = 0) {
    const l = this.toLocal(x, z);
    return Math.abs(l.x) <= this.size[0] / 2 + m && Math.abs(l.z) <= this.size[1] / 2 + m;
  }
  corners(m = 0) {
    const hw = this.size[0] / 2 + m, hd = this.size[1] / 2 + m;
    return [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(([a, b]) => this.toWorld(a, b));
  }

  // ---------------------------------------------------------------- 모습
  async buildVisual() {
    const lib = this.w.lib;
    if (this.vis) { this.group.remove(this.vis); this.vis = null; }
    const vis = new THREE.Group();
    this.parts = {}; this.anim = null; this.lights = [];
    const real = await lib.loadBuilding(this.modelKey);
    if (real) {
      const inst = lib.building(this.modelKey);
      vis.add(inst.scene);
      this.meta = inst.meta;
      for (const n of ['roof', 'walls', 'walls_low', 'iwalls', 'iwalls_low', 'floor', 'interior', 'exterior']) this.parts[n] = inst.scene.getObjectByName(n) || null;
      for (const n of ['walls_low', 'iwalls_low']) if (this.parts[n]) this.parts[n].visible = false;
      inst.scene.traverse((o) => { if (o.name && o.name.startsWith('anim_')) this.anim = o; });
      if (inst.meta.size) this.size = inst.meta.size.slice();
      this.readSlots(inst.scene, inst.meta);
      this.hasInterior = !!(this.parts.roof && this.parts.interior);
    } else {
      this.hasInterior = false;
      const fb = (this.levelDef && this.levelDef.fallback) || this.def.fallback;
      if (fb === 'windmill') vis.add(this.makeWindmill());
      else if (fb === 'well') vis.add(makeWell());
      else for (const [k, lx, lz, deg, sc] of fb || []) {
        await lib.loadProp(k);
        const o = lib.prop(k);
        o.position.set(lx, 0, lz); o.rotation.y = (deg || 0) * Math.PI / 180; o.scale.setScalar(sc || 1);
        vis.add(o);
      }
      for (const s of this.def.slots || []) this.slots.push({ action: s[0], x: s[1], z: s[2], yaw: s[3] || 0, room: '' });
    }
    // 문 위치
    if (this.meta && this.meta.door) {
      const o = this.meta.door.out, i = this.meta.door.in;
      this.door = this.toWorld(o[0], -o[1]);
      this.doorIn = this.toWorld(i[0], -i[1]);
    } else {
      this.door = this.toWorld(0, this.size[1] / 2 + 0.9);
      this.doorIn = this.toWorld(0, this.size[1] / 2 - 0.6);
    }
    this.workSpot = this.toWorld(this.size[0] * 0.3, this.size[1] / 2 + 0.8);
    vis.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.userData.bld = this; } });
    this.vis = vis;
    this.group.add(vis);
    if (this.def.light) this.addLamp();
    if (this.state === 'site') this.setProgress(this.progress || 0);
  }

  readSlots(scene, meta) {
    this.slots = [];
    const list = (meta && meta.slots) || [];
    if (list.length) {
      for (const s of list) this.slots.push({ id: s.id, action: s.action, room: s.room || '', x: s.pos[0], z: -s.pos[1], y: s.pos[2] || 0, yaw: (s.yaw || 0) * Math.PI / 180 });
    } else {
      scene.traverse((o) => {
        if (!o.name || !o.name.startsWith('slot.')) return;
        const [, action] = o.name.split('.');
        this.slots.push({ id: o.name, action, room: (o.userData && o.userData.room) || '', x: o.position.x, z: o.position.z, y: o.position.y, yaw: o.rotation.y });
      });
    }
  }

  /** 상호작용 자리의 세계 좌표·방향 */
  slotWorld(s) {
    const p = this.toWorld(s.x, s.z);
    return { x: p.x, z: p.z, y: s.y || 0, yaw: this.rot + s.yaw };
  }
  freeSlot(actions) {
    const list = this.slots.filter((s) => actions.includes(s.action) && !this.reserved.has(s));
    return list.length ? list[Math.floor(Math.random() * list.length)] : null;
  }

  makeWindmill() {
    const { g, hub } = makeWindmillModel();
    this.anim = hub; this.animAxis = 'z';
    return g;
  }

  addLamp() {
    const l = new THREE.PointLight(0xffc477, 0, 9, 1.6);
    l.position.set(0, 2.3, 0);
    this.group.add(l);
    this.lights.push(l);
  }

  // ---------------------------------------------------------------- 공사 현장
  startSite() {
    this.state = 'site';
    this.progress = 0;
    const cost = this.free ? {} : Object.assign({}, this.def.cost || {});
    this.con = { kind: 'build', need: cost, have: {}, used: {}, work: 0, workNeeded: this.def.work || 8 };
    this.makeSiteVisual();
    this.setProgress(0);
  }

  makeSiteVisual() {
    this.clearSite();
    const g = this.site = new THREE.Group();
    const [w, d] = this.size;
    // 흙 바닥
    const dirt = new THREE.Mesh(new THREE.PlaneGeometry(w + 1.2, d + 1.2), new THREE.MeshStandardMaterial({ color: 0x9c7a58, roughness: 1, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3 }));
    dirt.rotation.x = -Math.PI / 2; dirt.position.y = 0.03; dirt.receiveShadow = true;
    g.add(dirt);
    // 말뚝과 줄
    const stakeM = new THREE.MeshStandardMaterial({ color: 0x8a6142 }), ropeM = new THREE.LineBasicMaterial({ color: 0xf2c14e });
    const cs = [[-w / 2 - 0.5, -d / 2 - 0.5], [w / 2 + 0.5, -d / 2 - 0.5], [w / 2 + 0.5, d / 2 + 0.5], [-w / 2 - 0.5, d / 2 + 0.5]];
    for (const [a, b] of cs) { const s = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.8, 6), stakeM); s.position.set(a, 0.4, b); s.castShadow = true; g.add(s); }
    g.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(cs.map(([a, b]) => new THREE.Vector3(a, 0.6, b))), ropeM));
    // 비계 (기둥·가로대·발판)
    const sc = this.scaffold = new THREE.Group();
    const poleM = new THREE.MeshStandardMaterial({ color: 0xa47a52, roughness: 0.9 }), boardM = new THREE.MeshStandardMaterial({ color: 0xc89c68, roughness: 0.9 });
    const H = this.height * 0.95;
    const pw = w / 2 + 0.55, pd = d / 2 + 0.55;
    const posts = [];
    const nx = Math.max(2, Math.round(w / 1.6)), nz = Math.max(2, Math.round(d / 1.6));
    for (let i = 0; i <= nx; i++) { const x = -pw + (2 * pw * i) / nx; posts.push([x, -pd], [x, pd]); }
    for (let i = 1; i < nz; i++) { const z = -pd + (2 * pd * i) / nz; posts.push([-pw, z], [pw, z]); }
    for (const [x, z] of posts) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, H, 6), poleM); p.position.set(x, H / 2, z); p.castShadow = true; sc.add(p); }
    for (let y = 1.3; y < H; y += 1.3) {
      for (const [ax, az, bx, bz] of [[-pw, -pd, pw, -pd], [-pw, pd, pw, pd], [-pw, -pd, -pw, pd], [pw, -pd, pw, pd]]) {
        const len = Math.hypot(bx - ax, bz - az);
        const r = new THREE.Mesh(new THREE.BoxGeometry(len, 0.07, 0.07), poleM);
        r.position.set((ax + bx) / 2, y, (az + bz) / 2); r.rotation.y = Math.atan2(-(bz - az), bx - ax); r.castShadow = true; sc.add(r);
        const bd = new THREE.Mesh(new THREE.BoxGeometry(len, 0.05, 0.42), boardM);
        bd.position.set((ax + bx) / 2, y - 0.04, (az + bz) / 2); bd.rotation.y = r.rotation.y;
        const out = new THREE.Vector3((ax + bx) / 2, 0, (az + bz) / 2).normalize().multiplyScalar(0.22);
        bd.position.add(out); bd.castShadow = true; bd.receiveShadow = true; sc.add(bd);
      }
    }
    sc.visible = false;
    g.add(sc);
    // 재료 더미 자리 (정면 오른쪽 앞)
    this.pileSpot = { x: w / 2 + 1.3, z: d / 2 + 0.6 };
    this.pile = new THREE.Group(); this.pile.position.set(this.pileSpot.x, 0, this.pileSpot.z);
    g.add(this.pile);
    this.group.add(g);
    this.pileCount = {};
  }

  clearSite() {
    if (this.site) { this.group.remove(this.site); this.site = null; this.scaffold = null; this.pile = null; }
  }

  /** 재료 더미 모습 갱신 (배달 - 사용) */
  updatePile() {
    if (!this.pile || !this.con) return;
    const want = {};
    for (const t in this.con.need) want[t] = (this.con.have[t] || 0) - (this.con.used[t] || 0);
    const key = JSON.stringify(want);
    if (this.pileKey === key) return;
    this.pileKey = key;
    this.pile.clear();
    let ox = 0;
    for (const t in want) {
      const n = Math.max(0, want[t]);
      for (let k = 0; k < n; k++) {
        const o = this.w.itemModel(t);
        if (t === 'plank') { o.position.set(ox, 0.06 + k * 0.1, (k % 2) * 0.05); o.rotation.y = k % 2 ? 0.08 : -0.05; }
        else { o.position.set(ox + (k % 3) * 0.32 - 0.3, 0.02 + Math.floor(k / 3) * 0.18, (k % 2) * 0.2); }
        this.pile.add(o);
      }
      ox -= 1.0;
    }
  }

  /** 공사 진행 (0~1): 건물이 아래에서 위로 올라간다 */
  setProgress(p) {
    this.progress = p;
    if (!this.vis) return;
    if (this.state !== 'site') { this.setClip(null); return; }
    if (this.scaffold) this.scaffold.visible = p > 0.04 && p < 0.985;
    this.setClip(Math.max(0.0001, p) * this.height * 1.02);
    this.vis.visible = p > 0.005;
  }

  setClip(h) {
    if (!this.vis) return;
    if (h == null) {
      if (this.clipPlane) { this.vis.traverse((o) => { if (o.isMesh && o.material && o.material.__clipped) { o.material = o.material.__orig; } }); this.clipPlane = null; }
      return;
    }
    if (!this.clipPlane) {
      this.clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
      this.vis.traverse((o) => {
        if (!o.isMesh) return;
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        const cl = mats.map((m) => { const c = m.clone(); c.clippingPlanes = [this.clipPlane]; c.clipShadows = true; c.side = THREE.DoubleSide; c.__clipped = true; c.__orig = m; return c; });
        if (Array.isArray(o.material)) { o.material = cl; o.material.__clipped = true; o.material.__orig = mats; } else o.material = cl[0];
      });
    }
    this.clipPlane.constant = h;
  }

  finish() {
    this.state = 'active';
    this.con = null;
    this.setClip(null);
    this.clearSite();
    if (this.vis) this.vis.visible = true;
  }

  // ---------------------------------------------------------------- 실내 보기
  setCutaway(on) {
    if (!this.hasInterior || this.state !== 'active') return;
    if (this.cutaway === on) return;
    this.cutaway = on;
    const p = this.parts;
    if (p.roof) p.roof.visible = !on;
    if (p.walls) p.walls.visible = !on;
    if (p.iwalls) p.iwalls.visible = !on;
    if (p.walls_low) p.walls_low.visible = on;
    if (p.iwalls_low) p.iwalls_low.visible = on;
  }

  // ---------------------------------------------------------------- 결과물 더미 (문 옆)
  updateOutPile() {
    const n = Math.min(6, this.out + (this.stockShow || 0));
    if (this.outN === n) return;
    this.outN = n;
    if (!this.outPile) {
      this.outPile = new THREE.Group();
      const sp = { x: -this.size[0] / 2 + 0.2, z: this.size[1] / 2 + 0.9 };
      this.outPile.position.set(sp.x, 0, sp.z);
      this.group.add(this.outPile);
    }
    this.outPile.clear();
    const t = this.def.out;
    if (!t) return;
    for (let k = 0; k < n; k++) {
      const o = this.w.itemModel(t);
      o.position.set((k % 3) * 0.34 - 0.34, 0.05 + Math.floor(k / 3) * 0.16, 0);
      o.rotation.y = 0.3 * (k % 2);
      this.outPile.add(o);
    }
  }

  update(dt, night) {
    if (this.anim && this.state === 'active') {
      const spin = this.type === 'windmill' ? (this.working ? 1.8 : 0.12) : 0.5;
      if (this.animAxis === 'z') this.anim.rotation.z -= dt * spin; else this.anim.rotation.y += dt * spin;
    }
    for (const l of this.lights) l.intensity = night * 6;
  }

  dispose() {
    this.w.stage.scene.remove(this.group);
    this.group.traverse((o) => { if (o.geometry && !o.geometry.__shared) o.geometry.dispose?.(); });
  }
}

export function makeWindmillModel() {
  const g = new THREE.Group();
    const mat = (c, r = 0.8) => new THREE.MeshStandardMaterial({ color: c, roughness: r });
    const base = new THREE.Mesh(new THREE.CylinderGeometry(1.75, 1.85, 0.5, 20), mat(0x9aa3ad));
    base.position.y = 0.25; g.add(base);
    const tower = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.55, 4.6, 16), mat(0xeadfca));
    tower.position.y = 2.8; g.add(tower);
    for (const y of [1.7, 3.3]) { const band = new THREE.Mesh(new THREE.TorusGeometry(1.48 - (y - 1.7) * 0.15, 0.07, 6, 24), mat(0x8a6142)); band.rotation.x = Math.PI / 2; band.position.y = y; g.add(band); }
    const roof = new THREE.Mesh(new THREE.ConeGeometry(1.35, 1.9, 16), mat(0xb4553d));
    roof.position.y = 6.0; g.add(roof);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.5, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), mat(0xffffff, 0.9));
    cap.position.y = 6.55; cap.scale.set(1, 0.6, 1); g.add(cap);
    const door = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.4, 0.12), mat(0x7a5236));
    door.position.set(0, 1.2, 1.5); door.rotation.x = -0.12; g.add(door);
    const hub = new THREE.Group(); hub.position.set(0, 4.9, 1.25);
    const axle = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.5, 10), mat(0x6e4a30)); axle.rotation.x = Math.PI / 2; hub.add(axle);
    for (let k = 0; k < 4; k++) {
      const arm = new THREE.Group(); arm.rotation.z = k * Math.PI / 2 + Math.PI / 4;
      const spar = new THREE.Mesh(new THREE.BoxGeometry(0.12, 3.0, 0.08), mat(0x6e4a30)); spar.position.y = 1.5; arm.add(spar);
      const sail = new THREE.Mesh(new THREE.BoxGeometry(0.62, 2.3, 0.04), mat(0xf5efe3, 0.9)); sail.position.set(0.36, 1.75, 0.03); arm.add(sail);
      for (let r = 0; r < 4; r++) { const slat = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.05, 0.06), mat(0xb59a7a)); slat.position.set(0.36, 0.8 + r * 0.6, 0.06); arm.add(slat); }
      hub.add(arm);
    }
    g.add(hub);
    return { g, hub };
}

export function makeWell() {
  const g = new THREE.Group();
  const stone = new THREE.MeshStandardMaterial({ color: 0x9aa3ad, roughness: 0.9 }), wood = new THREE.MeshStandardMaterial({ color: 0x8a6142 }), roof = new THREE.MeshStandardMaterial({ color: 0xb4553d }), snow = new THREE.MeshStandardMaterial({ color: 0xf4f7fb });
  const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.0, 0.8, 18, 1, true), stone); ring.position.y = 0.4; g.add(ring);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.95, 0.12, 8, 20), stone); rim.rotation.x = Math.PI / 2; rim.position.y = 0.82; g.add(rim);
  const water = new THREE.Mesh(new THREE.CircleGeometry(0.85, 18), new THREE.MeshStandardMaterial({ color: 0x3b6a9a, roughness: 0.2 })); water.rotation.x = -Math.PI / 2; water.position.y = 0.5; g.add(water);
  for (const s of [-1, 1]) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.14, 1.9, 0.14), wood); p.position.set(s * 0.95, 0.95, 0); g.add(p); }
  const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.1, 8), wood); bar.rotation.z = Math.PI / 2; bar.position.y = 1.6; g.add(bar);
  const r1 = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.08, 1.0), roof); r1.position.set(0, 2.05, 0.38); r1.rotation.x = 0.55; g.add(r1);
  const r2 = r1.clone(); r2.position.z = -0.38; r2.rotation.x = -0.55; g.add(r2);
  const s1 = new THREE.Mesh(new THREE.BoxGeometry(2.3, 0.06, 0.8), snow); s1.position.set(0, 2.1, 0.36); s1.rotation.x = 0.55; g.add(s1);
  const s2 = s1.clone(); s2.position.z = -0.36; s2.rotation.x = -0.55; g.add(s2);
  const bucket = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.12, 0.25, 10), wood); bucket.position.set(0.3, 1.1, 0); g.add(bucket);
  return g;
}

export { ITEMS, UP };
