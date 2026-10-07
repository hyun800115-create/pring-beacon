// 온기 영토와 이웃 마을(평화 경쟁).
//  - 우리 마을과 이웃 마을 '서리골'은 건물이 퍼뜨리는 온기로 땅을 차지한다. 온기가 더 센 쪽 땅이 된다.
//  - 우리 땅 안에만 지을 수 있다. 화톳불 망루로 땅을 넓힌다.
//  - 서리골도 스스로 집을 짓고 봉화를 준비한다. 봄의 봉화를 먼저 밝히는 시합.

import * as THREE from 'three';
import { BUILDINGS, WARMTH, NUM } from './defs.js';


export class Territory {
  constructor(game) {
    this.g = game;
    const S = this.S = NUM.mapSize;
    this.N = 256;
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.canvas.height = this.N;
    this.ctx = this.canvas.getContext('2d');
    this.tex = new THREE.CanvasTexture(this.canvas);
    this.tex.colorSpace = THREE.SRGBColorSpace;
    this.tex.minFilter = THREE.LinearFilter;
    const mat = new THREE.MeshBasicMaterial({ map: this.tex, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(S, S), mat);
    this.mesh.rotation.x = -Math.PI / 2;
    this.mesh.position.set(S / 2, 0.035, S / 2);
    this.mesh.renderOrder = 2;
    this.mesh.visible = false;
    game.stage.scene.add(this.mesh);
    this.dirty = true;
    this.t = 0;
  }

  sources(ai) {
    const out = [];
    for (const b of this.g.world.blds) {
      if (b.dead || !!b.ai !== ai) continue;
      const r = WARMTH[b.def.kind === 'house' ? 'house' : b.type];
      if (!r) continue;
      if (b.state !== 'active' && b.type !== 'hall') continue;
      out.push({ x: b.x, z: b.z, r: b.state === 'active' ? r : r * 0.6 });
    }
    return out;
  }
  field(src, x, z) { let f = -1; for (const s of src) f = Math.max(f, 1 - Math.hypot(x - s.x, z - s.z) / s.r); return f; }
  mine(x, z) {
    if (!this.cache) this.refresh();
    const m = this.field(this.cache.mine, x, z), r = this.field(this.cache.riv, x, z);
    return m > 0 && m >= r;
  }
  rivalAt(x, z) { if (!this.cache) this.refresh(); const m = this.field(this.cache.mine, x, z), r = this.field(this.cache.riv, x, z); return r > 0 && r > m; }

  /** 영토가 바뀔 때만 작은 그림으로 다시 그린다 (가볍게) */
  refresh() {
    this.cache = { mine: this.sources(false), riv: this.sources(true) };
    const N = this.N, S = this.S, img = this.ctx.createImageData(N, N), d = img.data;
    const own = new Int8Array(N * N);   // 0 추운 땅, 1 우리, 2 이웃
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const x = (i + 0.5) / N * S, z = (j + 0.5) / N * S;
      const m = this.field(this.cache.mine, x, z), r = this.field(this.cache.riv, x, z);
      own[j * N + i] = m > 0 && m >= r ? 1 : r > 0 && r > m ? 2 : 0;
    }
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const k = j * N + i, o = own[k];
      let edge = false;
      for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const ii = i + di, jj = j + dj; if (ii >= 0 && jj >= 0 && ii < N && jj < N && own[jj * N + ii] !== o) edge = true; }
      let c = [0, 0, 0, 0];
      if (o === 0) c = [140, 158, 200, 30];
      if (o === 2) c = [90, 140, 240, 28];
      if (edge && o === 1) c = [255, 158, 64, 190];
      if (edge && o === 2) c = [80, 140, 255, 190];
      d.set(c, k * 4);
    }
    this.ctx.putImageData(img, 0, 0);
    this.tex.needsUpdate = true;
    this.mesh.visible = this.cache.mine.length > 0 || this.cache.riv.length > 0;
  }
  update(dt) {
    this.t += dt;
    if (this.dirty && this.t > 0.5) { this.dirty = false; this.t = 0; this.refresh(); }
    this.mesh.material.opacity = 0.85 + 0.15 * Math.sin(performance.now() / 500);
  }
}

/** 이웃 마을 '서리골': 스스로 자라고 봉화를 준비한다 */
export class Rival {
  constructor(game) {
    this.g = game;
    this.name = '서리골';
    this.beacon = 0;        // 봉화 준비 (0~1)
    this.lit = false;
    this.t = 0;
    this.plan = ['house', 'woodcutter', 'house', 'farm', 'sawmill', 'house', 'watchtower', 'bakery', 'house', 'quarry', 'house', 'tavern', 'watchtower', 'house', 'well', 'house', 'windmill', 'house', 'watchtower'];
    this.step = 0;
  }

  async found(x, z) {
    const w = this.g.world;
    this.home = { x, z };
    // 이웃 마을 자리의 숲 정리
    const gone = []; w.natureNear(x, z, 9, (o) => gone.push(o)); for (const o of gone) w.removeNature(o);
    const hall = await w.place('hall', x, z, Math.atan2(w.size / 2 - x, w.size / 2 - z), { instant: true, ai: true });
    this.hall = hall;
    for (const [dx, dz, r] of [[-9, 4, 0.6], [8, 6, -0.4]]) await this.build('house', x + dx, z + dz, r, true);
    // 이웃 주민
    for (let k = 0; k < 8; k++) {
      const p = this.g.people.makePerson({ x: x + (Math.random() - 0.5) * 8, z: z + 6 + Math.random() * 4, stage: k === 7 ? 'elder' : 'adult' });
      p.ai = true; p.home = null;
    }
    this.g.territory.dirty = true;
  }

  async build(type, x, z, rot, instant) {
    const w = this.g.world;
    const b = await w.place(type, x, z, rot, { ai: true, instant, free: true });
    if (!instant) { b.aiWork = 0; }
    this.g.territory.dirty = true;
    return b;
  }

  /** 우리 땅 가장자리에서 빈 자리 찾기 */
  spot(type) {
    const w = this.g.world, T = this.g.territory;
    const mine = w.blds.filter((b) => b.ai && !b.dead);
    for (let tries = 0; tries < 60; tries++) {
      const a = mine[Math.floor(Math.random() * mine.length)];
      const ang = Math.random() * Math.PI * 2, d = 7 + Math.random() * (type === 'watchtower' ? 18 : 12);
      const x = a.x + Math.cos(ang) * d, z = a.z + Math.sin(ang) * d;
      const rot = Math.atan2(this.home.x - x, this.home.z - z) + Math.PI;
      if (!w.check(type, x, z, rot, null, true).ok) continue;
      if (!T.rivalAt(x, z) && type !== 'watchtower') continue;
      if (T.mine(x, z)) continue;
      return { x, z, rot };
    }
    return null;
  }

  async update(dt) {
    if (!this.hall) return;
    const days = this.g.clock.day + this.g.clock.frac;
    // 건물 짓기: 대략 하루에 하나
    this.t += dt;
    if (this.t > NUM.dayLength * 0.5 && this.step < this.plan.length) {
      this.t = 0;
      const type = this.plan[this.step];
      const s = this.spot(type);
      if (s) { this.step++; await this.build(type, s.x, s.z, s.rot, false); }
    }
    // 공사 진행 (이웃 주민이 망치질하는 모습은 people.aiThink 가)
    for (const b of this.g.world.blds) {
      if (!b.ai || !b.con) continue;
      b.con.work += dt * 0.5;
      b.setProgress(Math.min(1, b.con.work / b.con.workNeeded));
      if (b.con.work >= b.con.workNeeded) { await this.g.world.finish(b); this.g.territory.dirty = true; }
    }
    // 봉화 준비: 사흘째부터 천천히 (약 18일 걸림)
    if (!this.lit && days > 3) {
      this.beacon = Math.min(1, this.beacon + dt / (NUM.dayLength * 18));
      if (this.beacon >= 1) this.light();
    }
  }

  async light() {
    this.lit = true;
    const w = this.g.world;
    const s = this.spot('beacon') || { x: this.home.x + 6, z: this.home.z - 6, rot: 0 };
    const b = await w.place('beacon', s.x, s.z, s.rot, { ai: true, instant: true });
    this.g.lightBeacon(b, true);
  }
}

export { BUILDINGS };
