// 모델 창고: GLB 불러오기, 주민 인형(동작 재생·물건 들기), 소품 복제, 숲처럼 많은 것은 인스턴싱.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const SRC_FPS = 24;   // Blender 시간줄 기본 fps
const GLB = (typeof window !== 'undefined' && window.__SM_GLB) || '.glb';   // 플레이 링크에서는 서버가 받는 이름(.glb.wasm)으로 올린다

export class Library {
  constructor() {
    this.loader = new GLTFLoader();
    this.loader.setMeshoptDecoder(MeshoptDecoder);   // 플레이 링크용 압축 모델
    this.chars = {};    // key -> { scene, clips:{name:{clip, fps, loop}}, meta }
    this.props = {};    // key -> scene (원본)
    this.blds = {};     // key -> { scene, meta }
    this.index = { props: {}, buildings: {} };
  }

  async json(url) { try { const r = await fetch(url); return r.ok ? await r.json() : null; } catch (e) { return null; } }

  async init() {
    this.index.props = (await this.json('assets3d/props/index.json')) || {};
    const b = await this.json('assets3d/buildings/index.json');
    if (b) for (const it of (Array.isArray(b) ? b : Object.entries(b).map(([k, v]) => Object.assign({ key: k }, v)))) this.index.buildings[it.key] = it;
  }

  async loadChar(key) {
    if (this.chars[key]) return this.chars[key];
    const [g, meta] = await Promise.all([this.loader.loadAsync(`assets3d/chars/${key}${GLB}`), this.json(`assets3d/chars/${key}.json`)]);
    const tracks = g.animations.flatMap((a) => a.tracks);
    for (const t of tracks) if (t.name.endsWith('.scale') && t.values.every((v) => v === 0 || v === 1)) t.setInterpolation(THREE.InterpolateDiscrete);
    const all = new THREE.AnimationClip('all', -1, tracks);
    const clips = {};
    for (const [name, c] of Object.entries(meta.clips)) {
      const sub = THREE.AnimationUtils.subclip(all, name, c.start, c.end, SRC_FPS);
      clips[name] = { clip: sub, fps: c.fps, loop: c.loop };
    }
    const scene = skinify(g.scene);
    return (this.chars[key] = { scene, clips, meta });
  }

  async loadProp(key) {
    if (this.props[key]) return this.props[key];
    try {
      const g = await this.loader.loadAsync(`assets3d/props/${key}${GLB}`);
      g.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      return (this.props[key] = g.scene);
    } catch (e) { console.warn('prop missing', key); return (this.props[key] = boxStandIn()); }
  }

  async loadBuilding(key) {
    if (this.blds[key] !== undefined) return this.blds[key];
    if (!this.index.buildings[key]) return (this.blds[key] = null);
    try {
      const [g, meta] = await Promise.all([this.loader.loadAsync(`assets3d/buildings/${key}${GLB}`), this.json(`assets3d/buildings/${key}.json`)]);
      g.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      return (this.blds[key] = { scene: g.scene, meta: meta || {} });
    } catch (e) { console.warn('building missing', key, e); return (this.blds[key] = null); }
  }

  prop(key) { const s = this.props[key]; return s ? s.clone(true) : boxStandIn(); }
  building(key) { const b = this.blds[key]; return b ? { scene: b.scene.clone(true), meta: b.meta } : null; }
  char(key) { return new Doll(this.chars[key] || this.chars[Object.keys(this.chars)[0]], key); }
}

/**
 * 관절(노드) 계층 + 관절마다 붙은 메쉬들 → 뼈대 하나 + 메쉬 하나(재질 하나, 색은 꼭짓점 색)로 바꾼다.
 * 주민 한 명을 한 번에 그릴 수 있어 수백 명도 가볍다. 동작(노드 이름 기준)은 같은 이름의 뼈에 그대로 붙는다.
 */
function skinify(root) {
  root.updateMatrixWorld(true);
  const bones = [], boneOf = new Map();
  const mk = (node, parent) => {
    const b = new THREE.Bone();
    b.name = node.name;
    b.position.copy(node.position); b.quaternion.copy(node.quaternion); b.scale.copy(node.scale);
    boneOf.set(node, bones.length); bones.push(b);
    if (parent) parent.add(b);
    for (const c of node.children) mk(c, b);
    return b;
  };
  const tops = root.children.map((c) => mk(c, null));
  const geos = [];
  const col = new THREE.Color();
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    let g = o.geometry.clone();
    g = g.index ? g.toNonIndexed() : g;
    g.applyMatrix4(o.matrixWorld);
    const n = g.attributes.position.count;
    const colors = new Float32Array(n * 3);
    const groups = g.groups.length ? g.groups : [{ start: 0, count: n, materialIndex: 0 }];
    for (const gr of groups) {
      const m = mats[gr.materialIndex || 0] || mats[0];
      col.copy(m.color || col.set(0xffffff));
      if (m.emissive && m.emissiveIntensity) col.add(m.emissive.clone().multiplyScalar(m.emissiveIntensity * 0.5));
      for (let i = gr.start; i < Math.min(n, gr.start + gr.count); i++) colors.set([col.r, col.g, col.b], i * 3);
    }
    const bi = boneOf.get(o);
    const si = new Uint16Array(n * 4), sw = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { si[i * 4] = bi; sw[i * 4] = 1; }
    const out = new THREE.BufferGeometry();
    out.setAttribute('position', g.attributes.position);
    out.setAttribute('normal', g.attributes.normal || g.computeVertexNormals() || g.attributes.normal);
    out.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    out.setAttribute('skinIndex', new THREE.BufferAttribute(si, 4));
    out.setAttribute('skinWeight', new THREE.BufferAttribute(sw, 4));
    geos.push(out);
  });
  const geo = mergeGeometries(geos, false);
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0.8, 0), 1.6);
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.72, metalness: 0 });
  const sm = new THREE.SkinnedMesh(geo, mat);
  sm.name = 'body';
  for (const t of tops) sm.add(t);
  sm.castShadow = true; sm.receiveShadow = false;
  const group = new THREE.Group();
  group.add(sm);
  group.updateMatrixWorld(true);
  sm.bind(new THREE.Skeleton(bones));
  return group;
}

function boxStandIn() {
  const m = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x9aa1ab }));
  m.position.y = 0.5; m.castShadow = true;
  const g = new THREE.Group(); g.add(m); return g;
}

/** 주민 인형: 모델 복제 + 동작 재생 + 손에 물건 들기 */
export class Doll {
  constructor(src, key) {
    this.key = key;
    this.src = src;
    this.root = new THREE.Group();
    this.model = SkeletonUtils.clone(src.scene);
    this.root.add(this.model);
    this.mixer = new THREE.AnimationMixer(this.model);
    this.actions = {};
    this.cur = null; this.curName = '';
    this.handR = this.model.getObjectByName('hand_R');
    this.handL = this.model.getObjectByName('hand_L');
    this.carryObj = null;
    this.speed = 1;
    this.tmpA = new THREE.Vector3(); this.tmpB = new THREE.Vector3();
  }
  has(name) { return !!this.src.clips[name]; }
  play(name, fade = 0.18, speed = 1) {
    if (!this.src.clips[name]) name = FALLBACK[name] && this.src.clips[FALLBACK[name]] ? FALLBACK[name] : 'idle';
    if (this.curName === name && this.cur) { this.cur.timeScale = (this.src.clips[name].fps / SRC_FPS) * speed; return; }
    const c = this.src.clips[name];
    let a = this.actions[name];
    if (!a) { a = this.actions[name] = this.mixer.clipAction(c.clip); a.setLoop(c.loop ? THREE.LoopRepeat : THREE.LoopOnce); a.clampWhenFinished = true; }
    a.reset(); a.timeScale = (c.fps / SRC_FPS) * speed; a.play();
    if (this.cur) this.cur.crossFadeTo(a, fade, false);
    this.cur = a; this.curName = name;
  }
  carry(obj) {
    if (this.carryObj) this.root.remove(this.carryObj);
    this.carryObj = obj || null;
    if (obj) this.root.add(obj);
  }
  update(dt, full = true) {
    this.mixer.update(dt);
    if (this.carryObj && this.handR && this.handL && full) {
      this.model.updateMatrixWorld(true);
      this.handR.getWorldPosition(this.tmpA); this.handL.getWorldPosition(this.tmpB);
      this.tmpA.add(this.tmpB).multiplyScalar(0.5);
      this.root.worldToLocal(this.tmpA);
      this.carryObj.position.set(this.tmpA.x, this.tmpA.y + 0.06, this.tmpA.z);
    }
  }
}
const FALLBACK = { carry_idle: 'idle', carry_walk: 'walk', run: 'walk', sit_talk: 'sit', sit_eat: 'sit', sit_read: 'sit', sit: 'idle', work_hands: 'idle', dance: 'happy', perform: 'happy', shiver: 'idle', chop: 'work', mine: 'work', harvest: 'work', sleep: 'idle' };

/** 같은 모델을 아주 많이 그리기 (나무·바위·덤불) */
export class Pool {
  constructor(scene, template, cap = 2000, shadow = true) {
    this.cap = cap; this.n = 0; this.ids = []; this.slot = new Map();
    this.parts = [];
    template.updateMatrixWorld(true);
    template.traverse((o) => {
      if (!o.isMesh) return;
      const im = new THREE.InstancedMesh(o.geometry, o.material, cap);
      im.castShadow = shadow; im.receiveShadow = true;
      im.count = 0;
      im.frustumCulled = false;
      scene.add(im);
      this.parts.push({ im, local: o.matrixWorld.clone() });
    });
    this.m = new THREE.Matrix4(); this.q = new THREE.Quaternion(); this.s = new THREE.Vector3(); this.p = new THREE.Vector3(); this.e = new THREE.Euler();
  }
  matrix(x, y, z, ry, sc, rx = 0, rz = 0) {
    this.e.set(rx, ry, rz); this.q.setFromEuler(this.e);
    return this.m.compose(this.p.set(x, y, z), this.q, this.s.set(sc, sc, sc));
  }
  add(id, x, z, ry = 0, sc = 1) {
    if (this.n >= this.cap) return;
    const k = this.n++;
    this.ids[k] = id; this.slot.set(id, k);
    this.set(id, x, 0, z, ry, sc);
  }
  set(id, x, y, z, ry, sc, rx = 0, rz = 0) {
    const k = this.slot.get(id);
    if (k == null) return;
    const base = this.matrix(x, y, z, ry, sc, rx, rz);
    for (const { im, local } of this.parts) {
      im.setMatrixAt(k, this.tmp = (this.tmp || new THREE.Matrix4()).multiplyMatrices(base, local));
      im.count = this.n; im.instanceMatrix.needsUpdate = true;
    }
  }
  remove(id) {
    const k = this.slot.get(id);
    if (k == null) return;
    const last = this.n - 1, lid = this.ids[last];
    const tmp = new THREE.Matrix4();
    for (const { im } of this.parts) { im.getMatrixAt(last, tmp); im.setMatrixAt(k, tmp); im.count = last; im.instanceMatrix.needsUpdate = true; }
    this.ids[k] = lid; this.slot.set(lid, k);
    this.slot.delete(id); this.n = last;
  }
}
