// 길: 자유롭게 그린 구불구불한 길의 연결망(교차점 자동 연결), 길 그리기(리본 메쉬), 길 따라 길 찾기.

import * as THREE from 'three';
import { ROADS, NUM } from './defs.js';

const STEP = 0.8;          // 길 점 간격(m)
const SNAP = 1.8;          // 기존 길·교차점에 붙는 거리
const Y0 = 0.025;

export class RoadNet {
  constructor(scene) {
    this.scene = scene;
    this.nodes = new Map(); this.edges = new Map();
    this.nid = 1;
    this.group = new THREE.Group(); this.group.name = 'roads';
    scene.add(this.group);
    this.mats = {};
    const tl = new THREE.TextureLoader();
    for (const [k, r] of Object.entries(ROADS)) {
      const m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.95, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2 - ROAD_Z[k], polygonOffsetUnits: -2 });
      tl.load(r.tex, (t) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; m.map = t; m.needsUpdate = true; });
      m.color.setHex(0xffffff);
      m.emissive = new THREE.Color(r.color); m.emissiveIntensity = 0.32;   // 무늬는 살리고 색은 밝게
      this.mats[k] = m;
    }
    this.edgeMat = new THREE.MeshStandardMaterial({ color: 0x8c7a66, roughness: 1, side: THREE.DoubleSide, transparent: true, opacity: 0.38, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
    this.listeners = [];
  }
  onChange(fn) { this.listeners.push(fn); }
  changed() { for (const f of this.listeners) f(); }

  // ---------------------------------------------------------------- 연결망
  addNode(x, z) { const n = { id: this.nid++, x, z, edges: new Set() }; this.nodes.set(n.id, n); return n; }

  /** (x,z) 근처의 교차점 또는 길 위 점 */
  snap(x, z, r = SNAP) {
    let best = null, bd = r;
    for (const n of this.nodes.values()) { const d = Math.hypot(n.x - x, n.z - z); if (d < bd) { bd = d; best = { node: n, x: n.x, z: n.z }; } }
    if (best) return best;
    bd = r;
    for (const e of this.edges.values()) {
      const p = this.project(e, x, z);
      if (p.d < bd) { bd = p.d; best = { edge: e, s: p.s, x: p.x, z: p.z }; }
    }
    return best;
  }

  /** 점을 길 위에 수직으로 내린 위치 (s = 길 시작에서의 거리) */
  project(e, x, z) {
    let best = { d: Infinity, s: 0, x: 0, z: 0, i: 0 };
    for (let i = 0; i < e.pts.length - 1; i++) {
      const a = e.pts[i], b = e.pts[i + 1];
      const vx = b.x - a.x, vz = b.z - a.z, L2 = vx * vx + vz * vz || 1e-9;
      let t = ((x - a.x) * vx + (z - a.z) * vz) / L2; t = Math.max(0, Math.min(1, t));
      const px = a.x + vx * t, pz = a.z + vz * t, d = Math.hypot(px - x, pz - z);
      if (d < best.d) best = { d, s: e.cum[i] + Math.sqrt(L2) * t, x: px, z: pz, i };
    }
    return best;
  }

  /** 길을 s 위치에서 둘로 나누고 그 자리에 교차점 */
  splitEdge(e, s) {
    if (s < 0.6) return e.a; if (s > e.len - 0.6) return e.b;
    const pts1 = [], pts2 = [];
    let mid = null;
    for (let i = 0; i < e.pts.length; i++) {
      if (e.cum[i] < s) pts1.push(e.pts[i]);
      else { if (!mid) { mid = pointAt(e, s); pts1.push(mid); pts2.push(mid); } pts2.push(e.pts[i]); }
    }
    const n = this.addNode(mid.x, mid.z);
    const type = e.type;
    this.removeEdge(e, false);
    this.makeEdge(e.a, n, pts1, type);
    this.makeEdge(n, e.b, pts2, type);
    return n;
  }

  makeEdge(a, b, pts, type = 'dirt') {
    const e = { id: this.nid++, a, b, pts: pts.map((p) => ({ x: p.x, z: p.z })), type, busy: false };
    e.pts[0] = { x: a.x, z: a.z }; e.pts[e.pts.length - 1] = { x: b.x, z: b.z };
    measure(e);
    if (e.len < 0.3) return null;
    a.edges.add(e); b.edges.add(e);
    this.edges.set(e.id, e);
    this.buildMesh(e);
    return e;
  }

  removeEdge(e, cleanup = true) {
    if (!this.edges.has(e.id)) return;
    this.edges.delete(e.id);
    e.a.edges.delete(e); e.b.edges.delete(e);
    if (e.mesh) { this.group.remove(e.mesh); e.mesh.geometry.dispose(); }
    if (e.border) { this.group.remove(e.border); e.border.geometry.dispose(); }
    if (cleanup) {
      for (const n of [e.a, e.b]) if (!n.edges.size && !n.keep) this.nodes.delete(n.id);
      this.mergeDeg2(e.a); this.mergeDeg2(e.b);
      this.rebuildJoints();
      this.changed();
    }
  }

  /** 두 길만 이어진 교차점은 하나로 합친다 (같은 종류일 때) */
  mergeDeg2(n) {
    if (!this.nodes.has(n.id) || n.edges.size !== 2 || n.keep) return;
    const [e1, e2] = [...n.edges];
    if (e1.type !== e2.type || e1 === e2) return;
    const p1 = e1.b === n ? e1.pts : e1.pts.slice().reverse();
    const p2 = e2.a === n ? e2.pts : e2.pts.slice().reverse();
    const A = e1.b === n ? e1.a : e1.b, B = e2.a === n ? e2.b : e2.a;
    if (A === B) return;
    this.removeEdge(e1, false); this.removeEdge(e2, false);
    this.nodes.delete(n.id);
    this.makeEdge(A, B, p1.concat(p2.slice(1)), e1.type);
  }

  /**
   * 그린 선(점 목록)으로 길 만들기. 시작·끝은 가까운 길/교차점에 붙고, 지나가며 만나는 길과는 교차점을 만든다.
   * 반환: 만든 길 목록 (없으면 [])
   */
  addPath(raw, type = 'dirt', blocked) {
    let pts = resample(smooth(simplify(raw, 0.35)), STEP);
    if (pts.length < 2) return [];
    // 시작·끝 붙이기
    const s0 = this.snap(pts[0].x, pts[0].z), s1 = this.snap(pts[pts.length - 1].x, pts[pts.length - 1].z);
    if (s0) pts[0] = { x: s0.x, z: s0.z };
    if (s1) pts[pts.length - 1] = { x: s1.x, z: s1.z };
    pts = resample(pts, STEP);
    if (polyLen(pts) < 1.5) return [];
    if (blocked && pts.some((p, i) => i > 0 && i < pts.length - 1 && blocked(p.x, p.z))) return null;
    // 교차점 찾기 (새 선분 × 기존 길 선분)
    const cuts = [];   // {k: 새 선 점 번호, x, z, edge, s}
    for (let k = 1; k < pts.length - 2; k++) {
      const a = pts[k], b = pts[k + 1];
      for (const e of this.edges.values()) {
        for (let i = 0; i < e.pts.length - 1; i++) {
          const hit = segX(a, b, e.pts[i], e.pts[i + 1]);
          if (hit) cuts.push({ k, t: hit.t, x: hit.x, z: hit.z, edge: e, s: e.cum[i] + hit.u * Math.hypot(e.pts[i + 1].x - e.pts[i].x, e.pts[i + 1].z - e.pts[i].z) });
        }
      }
    }
    // 끝점 노드 만들기
    const nodeFor = (sn, p) => {
      if (sn && sn.node) return sn.node;
      if (sn && sn.edge && this.edges.has(sn.edge.id)) return this.splitEdge(sn.edge, sn.s);
      return this.addNode(p.x, p.z);
    };
    const startN = nodeFor(s0, pts[0]);
    // 교차점마다 기존 길을 나누고 노드 만들기 (같은 길을 여러 번 나눌 수 있으니 하나씩 다시 찾는다)
    const marks = [];
    cuts.sort((p, q) => p.k + p.t - (q.k + q.t));
    for (const c of cuts) {
      let n = null;
      for (const m of marks) if (Math.hypot(m.n.x - c.x, m.n.z - c.z) < 1.2) n = m.n;
      if (!n) {
        const sn = this.snap(c.x, c.z, 0.9);
        n = sn ? (sn.node || this.splitEdge(sn.edge, sn.s)) : this.addNode(c.x, c.z);
      }
      marks.push({ k: c.k + c.t, n });
    }
    const endN = nodeFor(this.snap(pts[pts.length - 1].x, pts[pts.length - 1].z, 0.5) || s1, pts[pts.length - 1]);
    // 새 길을 교차점 사이 토막으로
    const made = [];
    let prevN = startN, seg = [pts[0]];
    let mi = 0;
    for (let k = 1; k < pts.length; k++) {
      while (mi < marks.length && marks[mi].k < k) {
        const n = marks[mi++].n;
        if (n !== prevN) { seg.push({ x: n.x, z: n.z }); const e = this.makeEdge(prevN, n, seg, type); if (e) made.push(e); prevN = n; seg = [{ x: n.x, z: n.z }]; }
      }
      seg.push(pts[k]);
    }
    if (endN !== prevN) { const e = this.makeEdge(prevN, endN, seg, type); if (e) made.push(e); }
    for (const n of [startN, endN]) if (!n.edges.size) this.nodes.delete(n.id);
    this.rebuildJoints();
    this.changed();
    return made;
  }

  setType(e, type) {
    e.type = type;
    this.buildMesh(e);
    this.changed();
  }

  // ---------------------------------------------------------------- 그리기
  buildMesh(e) {
    const r = ROADS[e.type];
    if (e.mesh) { this.group.remove(e.mesh); e.mesh.geometry.dispose(); }
    if (e.border) { this.group.remove(e.border); e.border.geometry.dispose(); }
    e.mesh = new THREE.Mesh(ribbon(e.pts, r.width, Y0 + ROAD_Z[e.type] * 0.004), this.mats[e.type]);
    e.mesh.receiveShadow = true;
    e.mesh.userData.edge = e;
    e.border = new THREE.Mesh(ribbon(e.pts, r.width + 0.7, Y0 - 0.006), this.edgeMat);
    e.border.receiveShadow = true;
    this.group.add(e.border, e.mesh);
  }

  rebuildJoints() {
    if (this.joints) { this.group.remove(this.joints); this.joints.traverse((o) => o.geometry && o.geometry.dispose()); }
    const g = new THREE.Group();
    for (const n of this.nodes.values()) {
      if (!n.edges.size) continue;
      let best = 'dirt', w = 0;
      for (const e of n.edges) { if (ROADS[e.type].width > w) { w = ROADS[e.type].width; best = e.type; } }
      const m = new THREE.Mesh(new THREE.CircleGeometry(w / 2 + 0.05, 20), this.mats[best]);
      m.rotation.x = -Math.PI / 2; m.position.set(n.x, Y0 + ROAD_Z[best] * 0.004 + 0.002, n.z);
      m.receiveShadow = true;
      const uv = m.geometry.attributes.uv, ps = m.geometry.attributes.position;
      for (let i = 0; i < uv.count; i++) uv.setXY(i, (n.x + ps.getX(i)) / 2.5, (n.z - ps.getY(i)) / 2.5);   // 땅 기준 무늬 (길과 이어짐)
      g.add(m);
    }
    this.joints = g; this.group.add(g);
  }

  // ---------------------------------------------------------------- 길 찾기
  /** from → to 걸어갈 점 목록 [{x,z,sp}] (sp = 그 구간 속도 배수). 길이 더 빠르면 길로 간다. */
  route(fx, fz, tx, tz) {
    const direct = Math.hypot(tx - fx, tz - fz);
    const off = NUM.offRoad;
    if (!this.edges.size || direct < 4) return [{ x: tx, z: tz, sp: off }];
    const entries = this.near(fx, fz), exits = this.near(tx, tz);
    if (!entries.length || !exits.length) return [{ x: tx, z: tz, sp: off }];
    // 다익스트라: 상태 = 노드. 시작 = 입구 점에서 각 길 양 끝까지
    const dist = new Map(), prev = new Map(), open = [];
    const push = (n, d, via) => { if (d < (dist.get(n) ?? Infinity)) { dist.set(n, d); prev.set(n, via); open.push(n); } };
    for (const en of entries) {
      const sp = ROADS[en.e.type].speed, c0 = en.d / off;
      push(en.e.a, c0 + en.s / sp, { entry: en, toA: true });
      push(en.e.b, c0 + (en.e.len - en.s) / sp, { entry: en, toA: false });
    }
    while (open.length) {
      let bi = 0; for (let i = 1; i < open.length; i++) if (dist.get(open[i]) < dist.get(open[bi])) bi = i;
      const n = open[bi]; open[bi] = open[open.length - 1]; open.pop();
      const dn = dist.get(n);
      for (const e of n.edges) { const o = e.a === n ? e.b : e.a; push(o, dn + e.len / ROADS[e.type].speed, { edge: e, from: n }); }
    }
    let best = { cost: direct / off, path: null };
    for (const ex of exits) {
      const sp = ROADS[ex.e.type].speed, c1 = ex.d / off;
      for (const [n, along] of [[ex.e.a, ex.s], [ex.e.b, ex.e.len - ex.s]]) {
        const dn = dist.get(n); if (dn == null) continue;
        const c = dn + along / sp + c1;
        if (c < best.cost) best = { cost: c, end: { ex, n } };
      }
      for (const en of entries) if (en.e === ex.e) {   // 같은 길 위에서 바로
        const c = en.d / off + Math.abs(en.s - ex.s) / sp + c1;
        if (c < best.cost) best = { cost: c, same: { en, ex } };
      }
    }
    if (!best.end && !best.same) return [{ x: tx, z: tz, sp: off }];
    const out = [];
    if (best.same) {
      const { en, ex } = best.same;
      out.push({ x: en.x, z: en.z, sp: off }, ...along(en.e, en.s, ex.s), { x: ex.x, z: ex.z, sp: ROADS[ex.e.type].speed }, { x: tx, z: tz, sp: off });
      return out;
    }
    // 끝에서 거슬러 올라가기
    const chain = [];
    let n = best.end.n;
    let start = null;
    while (n) {
      const v = prev.get(n);
      if (v.entry) { start = { en: v.entry, n }; break; }
      chain.unshift({ e: v.edge, from: v.from, to: n });
      n = v.from;
    }
    const en = start.en;
    out.push({ x: en.x, z: en.z, sp: off });
    out.push(...along(en.e, en.s, start.n === en.e.a ? 0 : en.e.len));
    for (const c of chain) out.push(...along(c.e, c.from === c.e.a ? 0 : c.e.len, c.to === c.e.a ? 0 : c.e.len));
    const ex = best.end.ex;
    out.push(...along(ex.e, best.end.n === ex.e.a ? 0 : ex.e.len, ex.s));
    out.push({ x: ex.x, z: ex.z, sp: ROADS[ex.e.type].speed }, { x: tx, z: tz, sp: off });
    return out;
  }

  near(x, z, maxD = 30, k = 3) {
    const out = [];
    for (const e of this.edges.values()) { const p = this.project(e, x, z); if (p.d < maxD) out.push({ e, s: p.s, x: p.x, z: p.z, d: p.d }); }
    out.sort((a, b) => a.d - b.d);
    return out.slice(0, k);
  }

  /** 점이 길 위인가 (건물 놓기 검사용) */
  onRoad(x, z, extra = 0) {
    for (const e of this.edges.values()) { const p = this.project(e, x, z); if (p.d < ROADS[e.type].width / 2 + extra) return e; }
    return null;
  }
  pick(x, z) { return this.onRoad(x, z, 0.3); }
}

const ROAD_Z = { dirt: 0, gravel: 1, stone: 2 };

// ---------------------------------------------------------------- 도형 계산
function measure(e) {
  e.cum = [0];
  for (let i = 1; i < e.pts.length; i++) e.cum.push(e.cum[i - 1] + Math.hypot(e.pts[i].x - e.pts[i - 1].x, e.pts[i].z - e.pts[i - 1].z));
  e.len = e.cum[e.cum.length - 1];
}
function pointAt(e, s) {
  for (let i = 0; i < e.pts.length - 1; i++) {
    if (e.cum[i + 1] >= s) { const t = (s - e.cum[i]) / Math.max(1e-6, e.cum[i + 1] - e.cum[i]); return { x: e.pts[i].x + (e.pts[i + 1].x - e.pts[i].x) * t, z: e.pts[i].z + (e.pts[i + 1].z - e.pts[i].z) * t }; }
  }
  return { x: e.pts[e.pts.length - 1].x, z: e.pts[e.pts.length - 1].z };
}
/** 길 e 위에서 s0 → s1 로 걸어갈 점들 */
function along(e, s0, s1) {
  const sp = ROADS[e.type].speed, out = [];
  if (s1 >= s0) { for (let i = 0; i < e.pts.length; i++) if (e.cum[i] > s0 && e.cum[i] < s1) out.push({ x: e.pts[i].x, z: e.pts[i].z, sp }); }
  else { for (let i = e.pts.length - 1; i >= 0; i--) if (e.cum[i] < s0 && e.cum[i] > s1) out.push({ x: e.pts[i].x, z: e.pts[i].z, sp }); }
  const p = pointAt(e, s1); out.push({ x: p.x, z: p.z, sp });
  return out;
}
function polyLen(p) { let s = 0; for (let i = 1; i < p.length; i++) s += Math.hypot(p[i].x - p[i - 1].x, p[i].z - p[i - 1].z); return s; }
function simplify(p, eps) {
  if (p.length < 3) return p.slice();
  const keep = new Uint8Array(p.length); keep[0] = keep[p.length - 1] = 1;
  const st = [[0, p.length - 1]];
  while (st.length) {
    const [a, b] = st.pop(); let md = 0, mi = -1;
    for (let i = a + 1; i < b; i++) { const d = segDist(p[i], p[a], p[b]); if (d > md) { md = d; mi = i; } }
    if (md > eps) { keep[mi] = 1; st.push([a, mi], [mi, b]); }
  }
  return p.filter((_, i) => keep[i]);
}
function segDist(q, a, b) {
  const vx = b.x - a.x, vz = b.z - a.z, L2 = vx * vx + vz * vz || 1e-9;
  let t = ((q.x - a.x) * vx + (q.z - a.z) * vz) / L2; t = Math.max(0, Math.min(1, t));
  return Math.hypot(a.x + vx * t - q.x, a.z + vz * t - q.z);
}
/** 부드럽게 (캣멀롬) */
function smooth(p) {
  if (p.length < 3) return p.slice();
  const out = [];
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[Math.max(0, i - 1)], p1 = p[i], p2 = p[i + 1], p3 = p[Math.min(p.length - 1, i + 2)];
    const n = Math.max(2, Math.ceil(Math.hypot(p2.x - p1.x, p2.z - p1.z) / 0.5));
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      const f = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
      out.push({ x: f(p0.x, p1.x, p2.x, p3.x), z: f(p0.z, p1.z, p2.z, p3.z) });
    }
  }
  out.push(p[p.length - 1]);
  return out;
}
function resample(p, step) {
  if (p.length < 2) return p.slice();
  const out = [p[0]];
  let acc = 0;
  for (let i = 1; i < p.length; i++) {
    let a = p[i - 1]; const b = p[i];
    let d = Math.hypot(b.x - a.x, b.z - a.z);
    while (acc + d >= step) {
      const t = (step - acc) / d;
      a = { x: a.x + (b.x - a.x) * t, z: a.z + (b.z - a.z) * t };
      out.push(a); d = Math.hypot(b.x - a.x, b.z - a.z); acc = 0;
    }
    acc += d;
  }
  const last = p[p.length - 1];
  if (Math.hypot(last.x - out[out.length - 1].x, last.z - out[out.length - 1].z) > step * 0.3) out.push(last); else out[out.length - 1] = last;
  return out;
}
function segX(a, b, c, d) {
  const r = { x: b.x - a.x, z: b.z - a.z }, s = { x: d.x - c.x, z: d.z - c.z };
  const den = r.x * s.z - r.z * s.x;
  if (Math.abs(den) < 1e-9) return null;
  const t = ((c.x - a.x) * s.z - (c.z - a.z) * s.x) / den;
  const u = ((c.x - a.x) * r.z - (c.z - a.z) * r.x) / den;
  if (t < 0 || t > 1 || u < 0 || u > 1) return null;
  return { t, u, x: a.x + r.x * t, z: a.z + r.z * t };
}
/** 길 리본 (가운데 선 pts, 폭 w) */
export function ribbon(pts, w, y) {
  const n = pts.length, pos = new Float32Array(n * 2 * 3), uv = new Float32Array(n * 2 * 2), idx = [];
  let v = 0;
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    let tx = b.x - a.x, tz = b.z - a.z; const L = Math.hypot(tx, tz) || 1; tx /= L; tz /= L;
    const nx = -tz * w / 2, nz = tx * w / 2;
    if (i > 0) v += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z);
    pos.set([pts[i].x + nx, y, pts[i].z + nz, pts[i].x - nx, y, pts[i].z - nz], i * 6);
    uv.set([(pts[i].x + nx) / 2.5, (pts[i].z + nz) / 2.5, (pts[i].x - nx) / 2.5, (pts[i].z - nz) / 2.5], i * 4);   // 땅 기준 무늬
    if (i < n - 1) { const k = i * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  // 아래를 보는 면 뒤집기 방지: 법선을 위로
  const nm = g.attributes.normal; for (let i = 0; i < nm.count; i++) nm.setXYZ(i, 0, 1, 0);
  return g;
}
