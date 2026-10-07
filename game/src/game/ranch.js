// 목축·과수원·양봉·낚시: 울타리와 동물(돌아다니기·풀 뜯기·쉬기), 생산물이 생기면 일꾼이 거둔다.
// 과수원 나무·벌통·호수(물)도 여기서 만든다.

import * as THREE from 'three';
import { NUM } from './defs.js';

const rand = (a, b) => a + Math.random() * (b - a);

/** 울타리 칸 (건물 좌표, 앞쪽 +z 마당) */
export function penOf(b) {
  const m = b.meta && b.meta.pen;
  if (m) return { cx: m.center[0], cz: -m.center[1], w: m.size[0], d: m.size[1] };
  const [w, d] = b.size;
  return { cx: 0, cz: d * 0.12, w: w - 1.0, d: d * 0.62 };
}

export function decorate(b, world) {
  const def = b.def;
  if (def.kind === 'ranch' && def.fence && !(b.meta && b.meta.pen)) b.group.add(makeFence(penOf(b)));
  if (def.kind === 'orchard') {
    b.trees = [];
    const n = def.trees || def.hives || 5;
    const [w, d] = b.size;
    for (let k = 0; k < n; k++) {
      const cols = Math.ceil(Math.sqrt(n)), i = k % cols, j = Math.floor(k / cols);
      const lx = (i / Math.max(1, cols - 1) - 0.5) * (w - 2.5), lz = (j / Math.max(1, Math.ceil(n / cols) - 1) - 0.5) * (d - 3) + 0.8;
      let node = b.vis && b.vis.getObjectByName('tree_' + (k + 1));
      if (!node) { node = def.hives ? makeHive() : makeAppleTree(); node.position.set(lx, 0, lz); b.group.add(node); }
      const wp = b.toWorld(node.position.x, node.position.z);
      b.trees.push({ node, x: wp.x, z: wp.z, t: rand(0, def.every * 0.7), ready: false, reserved: false, fruit: def.hives ? null : node.userData.fruit });
    }
    if (def.hives) b.bees = makeBees(b);
  }
}

function makeFence(pen) {
  const g = new THREE.Group();
  const wood = new THREE.MeshStandardMaterial({ color: 0xa47a52, roughness: 0.9 }), snow = new THREE.MeshStandardMaterial({ color: 0xf4f7fb });
  const hw = pen.w / 2, hd = pen.d / 2;
  const edges = [[-hw, -hd, hw, -hd], [hw, -hd, hw, hd], [hw, hd, 0.9, hd], [-0.9, hd, -hw, hd], [-hw, hd, -hw, -hd]];
  for (const [ax, az, bx, bz] of edges) {
    const len = Math.hypot(bx - ax, bz - az), n = Math.max(1, Math.round(len / 1.4));
    for (let i = 0; i <= n; i++) {
      const t = i / n, x = pen.cx + ax + (bx - ax) * t, z = pen.cz + az + (bz - az) * t;
      const p = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.08, 0.9, 6), wood); p.position.set(x, 0.45, z); p.castShadow = true; g.add(p);
      const c = new THREE.Mesh(new THREE.SphereGeometry(0.085, 6, 4), snow); c.position.set(x, 0.92, z); c.scale.y = 0.5; g.add(c);
    }
    for (const y of [0.35, 0.7]) {
      const r = new THREE.Mesh(new THREE.BoxGeometry(len, 0.06, 0.05), wood);
      r.position.set(pen.cx + (ax + bx) / 2, y, pen.cz + (az + bz) / 2); r.rotation.y = -Math.atan2(bz - az, bx - ax); r.castShadow = true; g.add(r);
    }
  }
  return g;
}

function makeAppleTree() {
  const g = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.17, 1.3, 8), new THREE.MeshStandardMaterial({ color: 0x7a5236 })); trunk.position.y = 0.65; g.add(trunk);
  const leaf = new THREE.MeshStandardMaterial({ color: 0x4f9a52, roughness: 0.85 });
  for (const [x, y, z, r] of [[0, 1.75, 0, 0.75], [0.45, 1.5, 0.1, 0.5], [-0.4, 1.55, -0.1, 0.52], [0.05, 2.15, 0.1, 0.5]]) { const s = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 9), leaf); s.position.set(x, y, z); s.castShadow = true; g.add(s); }
  const snow = new THREE.Mesh(new THREE.SphereGeometry(0.45, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2.4), new THREE.MeshStandardMaterial({ color: 0xf4f7fb })); snow.position.y = 2.3; g.add(snow);
  const fruit = new THREE.Group();
  const red = new THREE.MeshStandardMaterial({ color: 0xd9443a, roughness: 0.5 });
  for (let k = 0; k < 9; k++) { const a = k * 2.4, s = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6), red); s.position.set(Math.cos(a) * 0.62, 1.4 + (k % 3) * 0.28, Math.sin(a) * 0.62); fruit.add(s); }
  fruit.visible = false;
  g.add(fruit); g.userData.fruit = fruit;
  return g;
}

function makeHive() {
  const g = new THREE.Group();
  const wood = new THREE.MeshStandardMaterial({ color: 0xe0b46a, roughness: 0.8 }), dark = new THREE.MeshStandardMaterial({ color: 0x8a6142 });
  const stand = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.3, 0.6), dark); stand.position.y = 0.15; g.add(stand);
  for (let k = 0; k < 3; k++) { const box = new THREE.Mesh(new THREE.BoxGeometry(0.62 - k * 0.04, 0.26, 0.52 - k * 0.04), wood); box.position.y = 0.43 + k * 0.27; box.castShadow = true; g.add(box); }
  const roof = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.07, 0.66), dark); roof.position.y = 1.2; g.add(roof);
  const snow = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.06, 0.6), new THREE.MeshStandardMaterial({ color: 0xf4f7fb })); snow.position.y = 1.26; g.add(snow);
  return g;
}

function makeBees(b) {
  const geo = new THREE.SphereGeometry(0.035, 5, 4), mat = new THREE.MeshBasicMaterial({ color: 0xffd23f });
  const bees = [];
  for (const t of b.trees) for (let k = 0; k < 4; k++) { const m = new THREE.Mesh(geo, mat); b.w.stage.scene.add(m); bees.push({ m, t, a: Math.random() * 6, r: rand(0.4, 0.9), h: rand(0.9, 1.6), s: rand(1.5, 3) }); }
  return bees;
}

// ---------------------------------------------------------------- 동물
export class Herds {
  constructor(game) { this.g = game; this.list = []; }

  async spawn(b) {
    const def = b.def, lib = this.g.lib;
    b.animals = [];
    const pen = penOf(b);
    const keys = [def.animal, def.animal2].filter(Boolean);
    for (let k = 0; k < (def.count || 3); k++) {
      const key = keys[k % keys.length];
      let doll = null;
      try { await lib.loadChar(key); if (lib.chars[key] && lib.chars[key].meta.key === key) doll = lib.char(key); } catch (e) { doll = null; }
      const lx = pen.cx + rand(-pen.w / 2 + 0.6, pen.w / 2 - 0.6), lz = pen.cz + rand(-pen.d / 2 + 0.6, pen.d / 2 - 0.6);
      const p = b.toWorld(lx, lz);
      const a = { b, key, doll, x: p.x, z: p.z, yaw: Math.random() * 6, state: 'idle', t: rand(1, 4), prod: rand(0, def.every * 0.7), ready: false, reserved: false };
      if (doll) { doll.root.position.set(a.x, 0, a.z); this.g.stage.scene.add(doll.root); doll.play('idle'); }
      b.animals.push(a); this.list.push(a);
    }
  }
  remove(b) {
    for (const a of b.animals || []) { if (a.doll) this.g.stage.scene.remove(a.doll.root); if (a.mark) a.mark.remove?.(); }
    this.list = this.list.filter((a) => a.b !== b);
  }

  update(dt) {
    const grow = 1 + this.g.econ.buff('grow');
    for (const a of this.list) {
      const b = a.b, pen = penOf(b);
      a.t -= dt;
      if (a.state === 'walk') {
        const dx = a.tx - a.x, dz = a.tz - a.z, d = Math.hypot(dx, dz);
        const sp = a.key === 'animal_chicken' ? 0.7 : 0.45;
        if (d < 0.05 || a.t < 0) { a.state = 'idle'; a.t = rand(2, 6); a.anim = Math.random() < 0.55 ? 'eat' : Math.random() < 0.5 ? 'sit' : 'idle'; }
        else { a.x += dx / d * sp * dt; a.z += dz / d * sp * dt; a.yaw = turn(a.yaw, Math.atan2(dx, dz), dt * 6); a.anim = 'walk'; }
      } else if (a.t < 0 && !a.held) {
        const lx = pen.cx + rand(-pen.w / 2 + 0.6, pen.w / 2 - 0.6), lz = pen.cz + rand(-pen.d / 2 + 0.6, pen.d / 2 - 0.6);
        const p = b.toWorld(lx, lz); a.tx = p.x; a.tz = p.z; a.state = 'walk'; a.t = 12;
      }
      // 생산
      if (!a.ready && b.state === 'active') {
        const fed = !b.def.feed || b.inputs > 0;
        if (fed) a.prod += dt * grow;
        if (a.prod >= b.def.every) { a.ready = true; a.prod = 0; if (b.def.feed) b.inputs = Math.max(0, b.inputs - 0.5); }
      }
      if (a.doll) {
        a.doll.root.position.set(a.x, 0, a.z); a.doll.root.rotation.y = a.yaw;
        a.doll.play(a.held ? 'happy' : (a.anim || 'idle'));
        if (this.g.stage.isNear(a.x, a.z)) a.doll.update(dt);
      }
    }
  }
}

/** 과수원 나무·벌통 열매 자라기, 벌 날기 */
export function updateOrchards(world, dt, grow) {
  for (const b of world.blds) {
    if (!b.trees || b.state !== 'active') continue;
    for (const t of b.trees) {
      if (!t.ready) { t.t += dt * grow; if (t.t >= b.def.every) { t.ready = true; if (t.fruit) t.fruit.visible = true; } }
    }
    if (b.bees) for (const e of b.bees) {
      e.a += dt * e.s;
      e.m.position.set(e.t.x + Math.cos(e.a) * e.r, e.h + Math.sin(e.a * 2.3) * 0.2, e.t.z + Math.sin(e.a) * e.r);
      e.m.visible = world.stage.isNear(e.t.x, e.t.z) && world.stage.night < 0.7;
    }
  }
}

// ---------------------------------------------------------------- 호수
export class Lake {
  constructor(world, cx, cz, rx, rz) {
    this.cx = cx; this.cz = cz; this.rx = rx; this.rz = rz;
    const shape = new THREE.Shape();
    const pts = [];
    for (let k = 0; k < 48; k++) { const a = k / 48 * Math.PI * 2, wob = 1 + 0.07 * Math.sin(a * 3 + 1) + 0.05 * Math.sin(a * 5); pts.push(new THREE.Vector2(Math.cos(a) * rx * wob, Math.sin(a) * rz * wob)); }
    shape.setFromPoints(pts);
    const water = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshStandardMaterial({ color: 0x5f9fd0, roughness: 0.15, metalness: 0.1, transparent: true, opacity: 0.92, polygonOffset: true, polygonOffsetFactor: -5, polygonOffsetUnits: -5 }));
    water.rotation.x = -Math.PI / 2; water.position.set(cx, 0.04, cz); water.receiveShadow = true;
    const shore = new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape(pts.map((p) => p.clone().multiplyScalar(1.12)))), new THREE.MeshStandardMaterial({ color: 0xdfe8f2, roughness: 0.6, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 }));
    shore.rotation.x = -Math.PI / 2; shore.position.set(cx, 0.03, cz);
    world.stage.scene.add(shore, water);
    this.water = water;
    // 얼음 조각 몇 개
    this.t = 0;
  }
  contains(x, z, m = 0) { const u = (x - this.cx) / (this.rx + m), v = (z - this.cz) / (this.rz + m); return u * u + v * v < 1; }
  update(dt) { this.t += dt; this.water.material.color.setHSL(0.57, 0.5, 0.58 + Math.sin(this.t * 0.6) * 0.02); }
}

function turn(a, b, k) { let d = b - a; while (d > Math.PI) d -= Math.PI * 2; while (d < -Math.PI) d += Math.PI * 2; return a + d * Math.min(1, k); }
export { NUM };
