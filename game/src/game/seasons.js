// 계절 모습: 땅 그림(몇 초에 걸쳐 겹쳐 바뀜), 숲(눈 덮인 소나무 → 초록 소나무, 활엽수 약 30%: 봄 꽃·여름 초록·가을 단풍·겨울 맨가지),
// 덤불 자리(눈 더미 → 꽃·풀 무더기·낙엽 더미), 눈 없는 바위·그루터기, 지붕 눈 녹기(녹아 없어지는 무늬),
// 카메라 둘레에 날리는 것(겨울 눈송이·봄 꽃잎·여름 나비와 밤 반딧불이·가을 낙엽), 겨울 호수 얼음 테두리.
//  - 자연물은 id·종류(type)·자리를 그대로 두고 모델 이름(o.model)만 바꿔 world.pools 의 인스턴스 묶음 사이를 옮긴다
//    (나무꾼은 계속 type === 'tree' 로 나무를 찾는다).
//  - clock.seasonIndex: 0 겨울, 1 봄, 2 여름, 3 가을 (봉화를 밝히면 봄으로 건너뛴다 → 자동으로 바뀜)
//  - 매 프레임 새 물건(배열·함수)을 만들지 않는다.

import * as THREE from 'three';
import { Pool } from '../render/models.js';
import { NUM, SEASONS } from './defs.js';

const WINTER = 0, SPRING = 1, SUMMER = 2, AUTUMN = 3;
const FADE = 4.5;          // 땅·지붕 눈·숲이 바뀌는 데 걸리는 시간(초)
const GROUND_TEX = ['assets/ground/ground_snow.png', 'assets/ground/ground_grass_spring.png', 'assets/ground/ground_grass_summer.png', 'assets/ground/ground_autumn.png'];
const SHORE = [0xdfe8f2, 0xb3ae7c, 0xc8b88a, 0xb39c6c];              // 호숫가 띠 색
// 호수 물 색에 곱하는 값 (겨울은 원래의 옅은 얼음빛, 나머지는 더 맑고 짙은 물빛)
const WATER = [[1, 1, 1], [0.55, 0.86, 0.86], [0.42, 0.74, 0.86], [0.5, 0.7, 0.78]];
// 나무 쓰러질 때 이는 먼지 (원래는 눈가루 색)
const PUFF = [0xf4f7fb, 0xf6cfdc, 0xb8d890, 0xe8a85a];
// 작은 계절 소품은 조금 크게 (잘 보이게): 모델 이름 → 크기 배수
const MUL = { season_flowers_a: 1.5, season_flowers_b: 1.5, season_grass: 1.4, season_grass_dry: 1.4, season_leaves: 1.2 };
const MACRO_AMP = [0.04, 0.13, 0.13, 0.14];                           // 땅 큰 얼룩 밝기 차이

// ---------------------------------------------------------------- 모델 묶음 (계절 순서: 겨울, 봄, 여름, 가을)
const TREE = {
  pa: ['tree_pine_a', 'season_pine_a', 'season_pine_a', 'season_pine_a'],
  pb: ['tree_pine_b', 'season_pine_b', 'season_pine_b', 'season_pine_b'],
  pc: ['tree_pine_snow', 'season_pine_c', 'season_pine_c', 'season_pine_c'],
  da: ['season_decid_a_winter', 'season_decid_a_spring', 'season_decid_a_summer', 'season_decid_a_autumn'],
  db: ['season_decid_b_winter', 'season_decid_b_spring', 'season_decid_b_summer', 'season_decid_b_autumn'],
};
const BUSH = ['bush_snow', 'season_bush_spring', 'season_bush_summer', 'season_bush_autumn'];
const ROCK = {
  ra: ['season_rock_a_snow', 'season_rock_a', 'season_rock_a', 'season_rock_a'],
  rb: ['season_rock_b_snow', 'season_rock_b', 'season_rock_b', 'season_rock_b'],
};
const STUMP = ['tree_stump', 'season_stump', 'season_stump', 'season_stump'];
const HIDDEN = 'season_hidden';    // 그리지 않는 빈 묶음 (여름의 눈 더미 자리 등)
// 눈 더미 자리: 계절마다 [모델, 누적 비율]
const PILE = [
  null,
  [['season_flowers_a', 0.3], ['season_flowers_b', 0.52], ['season_grass', 0.8], [HIDDEN, 1]],
  [['season_flowers_a', 0.28], ['season_flowers_b', 0.56], ['season_grass', 0.86], [HIDDEN, 1]],
  [['season_leaves', 0.45], ['season_grass_dry', 0.72], [HIDDEN, 1]],
];
// 모델 이름 → 무리
const FAM = {};
for (const [f, list] of Object.entries(TREE)) for (const m of list) FAM[m] = 'tree:' + f;
for (const m of BUSH) FAM[m] = 'bush';
for (const m of ['snow_pile_a', 'snow_pile_b', 'season_flowers_a', 'season_flowers_b', 'season_grass', 'season_grass_dry', 'season_leaves', HIDDEN]) FAM[m] = 'pile';
FAM.rock_ore = 'ra'; FAM.rock_ore_b = 'rb';
for (const [f, list] of Object.entries(ROCK)) for (const m of list) FAM[m] = f;
for (const m of STUMP) FAM[m] = 'stump';
// 계절마다 필요한 모델 (그 계절이 오기 전에 미리 불러 둔다)
function seasonModels(s) {
  const out = new Set();
  for (const list of Object.values(TREE)) out.add(list[s]);
  out.add(BUSH[s]); out.add(STUMP[s]);
  for (const list of Object.values(ROCK)) out.add(list[s]);
  if (PILE[s]) for (const [m] of PILE[s]) if (m !== HIDDEN) out.add(m);
  return [...out].filter((m) => m.startsWith('season_'));
}
const SHADOWLESS = /season_(flowers|grass|leaves)/;
const TREE_LIKE = /season_(decid|pine)/;

const fract = (v) => v - Math.floor(v);
const hash = (x, z, k) => fract(Math.sin(x * 12.9898 + z * 78.233 + k * 37.719) * 43758.5453);
/** 활엽수 자리인가: 숲마다 활엽수가 많은 곳·적은 곳이 생기게 (평균 약 30%) */
function isDecid(x, z) {
  const n = 0.5 + 0.5 * Math.sin(x * 0.11 + 1.3) * Math.sin(z * 0.093 + 0.4);
  return hash(x, z, 1) < 0.07 + 0.46 * n;
}

export class Seasons {
  constructor(game) {
    this.g = game;
    this.groundTint = 0xffffff;     // 땅 색은 그림이 다 가지고 있다 (계절 기본 색을 또 곱하지 않게)
    this.ready = false; this.loaded = false;
    this.target = -1;               // 지금 보여 주는(또는 바뀌어 가는) 계절
    this.loadedSeason = [false, false, false, false];
    this.loading = [null, null, null, null];
    this.queue = []; this.qi = 0; this.qRate = 0;
    this.melt = { value: 0 };       // 지붕 눈 녹은 정도 (0 = 눈 그대로, 1 = 다 녹음) — 모든 눈 재질이 같이 쓴다
    this.snowOn = true;             // 눈 덩어리 메쉬를 보이게 둘지
    this.snowFade = 0; this.snowDir = 0;
    this.groundFade = -1;
    this.timer = 0; this.time = 0;
    this.patched = new WeakSet();
    this.tmpV = new THREE.Vector2();
    this.shoreCol = new THREE.Color(SHORE[0]); this.shoreFrom = new THREE.Color(); this.shoreTo = new THREE.Color();
    this.waterTint = { value: new THREE.Color(1, 1, 1) }; this.waterFrom = new THREE.Color(); this.waterTo = new THREE.Color();
    this.iceOp = 1;
    this.lastGhost = null;
    this.installAddHook();
  }

  // ================================================================ 시작
  /** 세계가 만들어진 뒤(새 게임·불러오기 모두) 한 번 */
  async init() {
    const g = this.g, s = g.clock.seasonIndex;
    if (!this.loaded) {
      this.loaded = true;
      const w = g.world;
      if (!w.pools[HIDDEN]) w.pools[HIDDEN] = new Pool(g.stage.scene, new THREE.Group(), 4000, false);
      this.makeGround();
      this.makeParticles();
      // 'bld' 는 짐을 내릴 때마다도 오므로, 모습이 바뀐 때만 다시 살핀다
      const rescan = (b) => { if (b && b.group && (b.vis !== b.__sVis || b.group.children.length !== b.__sN)) this.scanBuilding(b); };
      w.on('bld', rescan);
      w.on('built', rescan);
    }
    // 지금 계절 모델은 기다렸다가, 나머지는 뒤에서 불러 둔다
    await this.loadSeason(s);
    if (s !== WINTER) await this.loadSeason(WINTER);
    this.ready = true;
    this.apply(s, true);
    for (const k of [(s + 1) % 4, (s + 2) % 4, (s + 3) % 4]) this.loadSeason(k);
  }

  loadSeason(s) {
    if (this.loading[s]) return this.loading[s];
    const g = this.g, w = g.world, lib = g.lib;
    const tex = this.groundTex[s];
    const texP = new THREE.TextureLoader().loadAsync(GROUND_TEX[s])
      .then((tt) => { tex.image = tt.image; }, () => { tex.image = fallbackGround(s); })
      .then(() => { tex.needsUpdate = true; });
    this.loading[s] = Promise.all([texP, ...seasonModels(s).map((k) => lib.loadProp(k))]).then(() => {
      for (const k of seasonModels(s)) {
        if (w.pools[k] || !lib.props[k]) continue;
        const tree = TREE_LIKE.test(k);
        w.pools[k] = new Pool(g.stage.scene, lib.props[k], tree ? 3000 : 1500, !SHADOWLESS.test(k));
      }
      this.loadedSeason[s] = true;
    });
    return this.loading[s];
  }

  /**
   * world.addNature 를 감싼다: 새로 생기는 자연물(처음 숲 만들기·다시 자라는 나무·그루터기·불러오기)이
   * 지금 계절 모델로 바로 들어가게. 아직 계절 모델이 없으면 원래(겨울) 모델로 넣는다.
   */
  installAddHook() {
    const w = this.g.world;
    if (!w || w.__seasonHook) return;
    w.__seasonHook = true;
    const orig = w.addNature;
    w.addNature = (type, model, x, z, ry, sc, extra) => {
      const m = this.pick(model, x, z, this.ready ? this.target : WINTER, null);
      if (w.pools[m]) showPool(w.pools[m]);
      const k = MUL[m] || 1;
      const o = orig.call(w, type, m, x, z, ry, sc * k, extra);
      if (k !== 1) o.sc = sc;                 // 저장되는 크기는 원래 크기
      if (model.startsWith('snow_pile')) o.sv = model;
      return o;
    };
    // 나무 쓰러질 때의 눈가루 → 계절에 맞는 먼지·꽃잎·잎 색
    const puff = w.puff;
    w.puff = (x, z, color, n, spread, y) => puff.call(w, x, z, color === 0xf4f7fb && this.ready && this.target > 0 ? PUFF[this.target] : color, n, spread, y);
  }

  /** 이 자연물이 계절 s 에 쓸 모델 (묶음이 아직 없으면 쓸 수 있는 것으로) */
  pick(model, x, z, s, sv) {
    const w = this.g.world, fam = FAM[model];
    if (!fam) return model;
    let m = model;
    if (fam.startsWith('tree:')) {
      let f = fam.slice(5);
      if (isDecid(x, z)) f = hash(x, z, 2) < 0.55 ? 'da' : 'db';
      else if (f === 'da' || f === 'db') f = ['pa', 'pb', 'pc'][Math.floor(hash(x, z, 3) * 3)];
      m = TREE[f][s];
      if (!w.pools[m]) m = TREE[f === 'da' || f === 'db' ? 'pa' : f][s];
      if (!w.pools[m]) m = TREE[f === 'da' || f === 'db' ? 'pa' : f][WINTER];
    } else if (fam === 'bush') m = BUSH[s];
    else if (fam === 'pile') {
      if (s === WINTER) m = sv || (model.startsWith('snow_pile') ? model : hash(x, z, 4) < 0.5 ? 'snow_pile_a' : 'snow_pile_b');
      else { const h = hash(x, z, 5); for (const [k, p] of PILE[s]) if (h < p) { m = k; break; } }
      if (!w.pools[m]) m = sv || 'snow_pile_a';
    } else if (fam === 'stump') m = STUMP[s];
    else if (fam === 'ra' || fam === 'rb') { m = ROCK[fam][s]; if (!w.pools[m]) m = fam === 'ra' ? 'rock_ore' : 'rock_ore_b'; }
    return w.pools[m] ? m : model;
  }

  // ================================================================ 계절 바꾸기
  /** 계절 s 로 (instant 면 바로, 아니면 몇 초에 걸쳐) */
  apply(s, instant) {
    const from = this.target;
    this.target = s;
    const g = this.g, w = g.world;
    // 1) 땅
    const tex = this.groundTex[s];
    if (instant || from < 0) { this.finishGround(); this.setGroundMap(tex); this.gU.uMap2.value = tex; this.gU.uMix.value = 0; this.groundFade = -1; }
    else { this.finishGround(); this.gU.uMap2.value = tex; this.gU.uMix.value = 0; this.groundFade = 0; }
    this.gU.uAmp.value = MACRO_AMP[s];
    // 2) 자연물: 바뀔 것들을 카메라 가까운 곳부터 차례로
    const q = this.queue; q.length = 0; this.qi = 0;
    for (const o of w.nature.values()) { if (o.model.startsWith('snow_pile') && !o.sv) o.sv = o.model; if (this.pick(o.model, o.x, o.z, s, o.sv) !== o.model) q.push(o); }
    if (instant || from < 0) { for (const o of q) this.swap(o); q.length = 0; this.syncPools(); }
    else {
      const r = g.stage.rig;
      q.sort((a, b) => ((a.x - r.tx) ** 2 + (a.z - r.tz) ** 2) - ((b.x - r.tx) ** 2 + (b.z - r.tz) ** 2));
      this.qRate = q.length / (FADE * 0.8);
      this.qAcc = 0;
      this.syncPools();
    }
    // 3) 지붕 눈
    const wantSnow = s === WINTER;
    if (instant || from < 0) { this.melt.value = wantSnow ? 0 : 1; this.snowOn = wantSnow; this.snowDir = 0; this.setSnowVisible(wantSnow); }
    else if (wantSnow !== (this.snowDir === 0 ? this.snowOn : this.snowDir < 0)) {
      if (wantSnow) { this.snowOn = true; this.setSnowVisible(true); this.snowDir = -1; }   // 녹은 상태(1)에서 0 으로 → 눈이 쌓임
      else { this.snowDir = 1; }
    }
    // 4) 날리는 것
    for (const P of this.parts) P.want = P.season === s ? 1 : 0;
    if (instant || from < 0) for (const P of this.parts) { P.mat.uniforms.uOpacity.value = P.want; P.pts.visible = P.want > 0; }
    // 5) 호수
    this.shoreFrom.copy(this.shoreCol); this.shoreTo.setHex(SHORE[s]); this.shoreT = instant || from < 0 ? 1 : 0;
    this.waterFrom.copy(this.waterTint.value); this.waterTo.setRGB(WATER[s][0], WATER[s][1], WATER[s][2]);
    if (instant || from < 0) { this.shoreCol.copy(this.shoreTo); this.waterTint.value.copy(this.waterTo); }
    this.iceWant = wantSnow ? 1 : 0;
    if (instant || from < 0) this.iceOp = this.iceWant;
    this.syncLake(true);
    // 알림 (진짜로 계절이 바뀔 때만)
    if (!instant && from >= 0 && g.people && g.people.news) {
      const msg = ['❄️ 겨울이 왔어요. 지붕에 눈이 소복이 쌓여요', '🌱 봄이에요! 눈이 녹고 꽃이 피기 시작해요', '☀️ 여름이에요! 숲이 짙어지고 밤엔 반딧불이가 날아요', '🍁 가을이에요! 나뭇잎이 붉게 물들어요'][s];
      g.people.news(msg, 'info');
    }
  }

  finishGround() {
    if (this.groundFade >= 0 && this.gU.uMap2.value) this.setGroundMap(this.gU.uMap2.value);
    this.gU.uMix.value = 0; this.groundFade = -1;
  }
  setGroundMap(t) {
    const m = this.groundMat;
    if (!m.map) m.needsUpdate = true;     // 그림 없음 → 있음: 셰이더를 다시 만든다
    m.map = t;
  }

  /** 자연물 하나를 계절 모델로 옮기기 (id·자리·크기 그대로) */
  swap(o) {
    const w = this.g.world;
    if (!w.nature.has(o.id)) return;
    const m = this.pick(o.model, o.x, o.z, this.target, o.sv);
    if (m === o.model) return;
    w.pools[o.model].remove(o.id);
    o.model = m;
    const sc = (o.type === 'rock' && o.amount != null ? o.sc * (0.45 + 0.55 * o.amount / NUM.rockAmount) : o.sc) * (MUL[m] || 1);
    showPool(w.pools[m]);
    w.pools[m].add(o.id, o.x, o.z, o.ry, sc);
  }

  /** 빈 인스턴스 묶음은 그리지 않는다 (그리기 횟수 줄이기) */
  syncPools() {
    const pools = this.g.world.pools;
    for (const k in pools) { const p = pools[k]; for (let i = 0; i < p.parts.length; i++) p.parts[i].im.visible = p.n > 0; }
  }

  // ================================================================ 매 프레임
  /** 매 프레임 (real = 실제 초, dt = 게임 초) */
  update(real, dt) {
    void dt;
    if (!this.ready) return;
    const g = this.g, st = g.stage;
    const s = g.clock.seasonIndex;
    if (s !== this.target) {
      if (this.loadedSeason[s]) this.apply(s, false);
      else this.loadSeason(s);          // 다 불러오면 다음 프레임에 바뀐다
    }
    this.time += real;
    // 땅 겹쳐 바뀌기
    if (this.groundFade >= 0) {
      this.groundFade += real / FADE;
      const u = Math.min(1, this.groundFade);
      this.gU.uMix.value = u * u * (3 - 2 * u);
      if (u >= 1) this.finishGround();
    }
    if (this.groundFade < 0 && this.groundMat.map !== this.groundTex[this.target]) this.setGroundMap(this.groundTex[this.target]);   // 무대가 늦게 받은 눈 그림으로 덮어쓴 경우
    // 숲 바꾸기 (카메라 가까운 곳부터 물결처럼)
    if (this.qi < this.queue.length) {
      this.qAcc += this.qRate * real;
      let n = Math.floor(this.qAcc); this.qAcc -= n;
      while (n-- > 0 && this.qi < this.queue.length) this.swap(this.queue[this.qi++]);
      if (this.qi >= this.queue.length) { this.queue.length = 0; this.qi = 0; this.syncPools(); }
    }
    // 지붕 눈 녹기·쌓이기
    if (this.snowDir) {
      const m = this.melt;
      m.value = Math.max(0, Math.min(1, m.value + this.snowDir * real / FADE));
      if (this.snowDir > 0 && m.value >= 1) { this.snowDir = 0; this.snowOn = false; this.setSnowVisible(false); }
      else if (this.snowDir < 0 && m.value <= 0) { this.snowDir = 0; }
    }
    // 호수
    if (this.shoreT < 1 || Math.abs(this.iceOp - this.iceWant) > 1e-3) {
      this.shoreT = Math.min(1, this.shoreT + real / FADE);
      this.shoreCol.copy(this.shoreFrom).lerp(this.shoreTo, this.shoreT);
      this.waterTint.value.copy(this.waterFrom).lerp(this.waterTo, this.shoreT);
      this.iceOp += Math.sign(this.iceWant - this.iceOp) * Math.min(Math.abs(this.iceWant - this.iceOp), real / FADE);
      this.syncLake(false);
    }
    // 날리는 것
    this.updateParticles(real);
    // 놓기 그림자(유령 건물)의 눈도 계절에 맞게
    if (g.ghost !== this.lastGhost) { this.lastGhost = g.ghost; if (g.ghost && !this.snowOn) this.hideSnowIn(g.ghost); }
    // 가끔: 새로 생긴 건물 모습 살피기, 빈 묶음 숨기기, 호수 새로 생겼는지
    this.timer += real;
    if (this.timer > 1) {
      this.timer = 0;
      const blds = g.world.blds;
      for (let i = 0; i < blds.length; i++) { const b = blds[i]; if (b.vis !== b.__sVis || b.group.children.length !== b.__sN) this.scanBuilding(b); }
      if (this.qi >= this.queue.length) this.syncPools();
      if (g.world.lake !== this.lake) this.syncLake(true);
    }
    void st;
  }

  // ================================================================ 땅
  makeGround() {
    const st = this.g.stage, S = st.size;
    this.groundMat = st.groundMat;
    // 그림은 loadSeason 에서 받는다 (받기 전에는 올리지 않음: 올린 뒤 크기가 바뀌면 안 되므로)
    this.groundTex = GROUND_TEX.map(() => {
      const t = new THREE.Texture();
      t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(S * 3 / 7, S * 3 / 7); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
      return t;
    });
    // 큰 얼룩(타일 반복이 눈에 덜 띄게): 이음매 없는 부드러운 노이즈 3 채널
    const N = 64, data = new Uint8Array(N * N * 4);
    const waves = [];
    let seed = 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let c = 0; c < 3; c++) for (let k = 0; k < 6; k++) waves.push({ c, fx: Math.floor(rnd() * 4) + 1, fy: Math.floor(rnd() * 4) - 2, ph: rnd() * 6.283, a: 1 / (1 + k * 0.4) });
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      const v = [0, 0, 0];
      for (const w of waves) v[w.c] += w.a * Math.cos(2 * Math.PI * (w.fx * x + w.fy * y) / N + w.ph);
      for (let c = 0; c < 3; c++) data[(y * N + x) * 4 + c] = Math.max(0, Math.min(255, 128 + v[c] * 42));
      data[(y * N + x) * 4 + 3] = 255;
    }
    const macro = new THREE.DataTexture(data, N, N, THREE.RGBAFormat);
    macro.wrapS = macro.wrapT = THREE.RepeatWrapping; macro.magFilter = THREE.LinearFilter; macro.minFilter = THREE.LinearMipmapLinearFilter; macro.generateMipmaps = true; macro.needsUpdate = true;
    this.gU = { uMap2: { value: this.groundTex[0] }, uMix: { value: 0 }, uMacro: { value: macro }, uAmp: { value: 0.04 } };
    const m = this.groundMat, gU = this.gU;
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, gU);
      sh.fragmentShader = sh.fragmentShader
        .replace('void main() {', 'uniform sampler2D uMap2; uniform float uMix; uniform sampler2D uMacro; uniform float uAmp;\nvoid main() {')
        .replace('#include <map_fragment>', GROUND_FRAG);
    };
    m.customProgramCacheKey = () => 'season-ground';
    m.color.setHex(0xffffff);
    m.needsUpdate = true;
  }

  // ================================================================ 지붕 눈
  /**
   * 건물 안의 지붕 눈 메쉬 찾기: 재질 이름 'snow' (Blender 건물) 또는 이름 없는 눈 색 재질(코드로 만든 울타리·우물 등).
   * 땅에서부터 높이 솟은 눈 덩어리(큰 눈사람 몸통 같은 것)는 '눈으로 만든 물건'이라 녹이지 않는다.
   */
  scanBuilding(b) {
    if (!b || !b.group) return;
    b.__sVis = b.vis; b.__sN = b.group.children.length;
    const list = b.__snow || (b.__snow = []);
    list.length = 0;
    const root = b.group;
    root.traverse((o) => {
      if (!o.isMesh || !o.material) return;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      if (mats.length !== 1 || !isSnowMat(mats[0])) return;
      if (isSnowBody(o, root)) { this.keepBody(o); return; }
      list.push(o);
      this.patchSnow(mats[0]);
      if (mats[0].__orig && !Array.isArray(mats[0].__orig)) this.patchSnow(mats[0].__orig);
      o.visible = this.snowOn;
    });
  }

  /** 눈사람 몸통 같은 '눈 물건'은 늘 보이게. 녹는 무늬가 들어간 재질을 같이 쓰고 있었다면 무늬 없는 복사본으로 바꾼다 */
  keepBody(o) {
    o.visible = true;
    const m = o.material;
    if (this.patched.has(m)) o.material = plainOf(m);
    else if (m.__orig && !Array.isArray(m.__orig) && this.patched.has(m.__orig)) m.__orig = plainOf(m.__orig);   // 공사 중 잘린 재질: 다 지은 뒤 돌아갈 재질
  }

  setSnowVisible(on) {
    const blds = this.g.world.blds;
    for (let i = 0; i < blds.length; i++) {
      const b = blds[i];
      if (!b.__snow || b.vis !== b.__sVis) this.scanBuilding(b);
      for (let j = 0; j < b.__snow.length; j++) b.__snow[j].visible = on;
    }
    if (this.g.ghost) { if (on) this.g.ghost.traverse(showSnow); else this.hideSnowIn(this.g.ghost); }
  }
  hideSnowIn(root) { snowRoot = root; root.traverse(hideSnow); snowRoot = null; }

  /** 눈 재질에 '녹는 무늬'를 넣는다: 녹은 정도(melt)보다 낮은 곳부터 구멍이 나며 사라진다 */
  patchSnow(m) {
    if (this.patched.has(m)) return;
    this.patched.add(m);
    const melt = this.melt;
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uMelt = melt;
      sh.vertexShader = sh.vertexShader.replace('void main() {', 'varying vec3 vSnowW;\nvoid main() {')
        .replace('#include <project_vertex>', '#include <project_vertex>\n  vSnowW = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('void main() {', 'uniform float uMelt; varying vec3 vSnowW;\n' + NOISE_GLSL + '\nvoid main() {')
        .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n  if (uMelt > 0.001) { float k = vnoise(vSnowW.xz * 2.3 + vSnowW.y) * 0.7 + vnoise(vSnowW.xz * 8.0) * 0.3; if (k < uMelt * 1.05) discard; }');
    };
    m.customProgramCacheKey = () => 'season-snow';
    m.needsUpdate = true;
  }

  // ================================================================ 호수
  syncLake(rebuild) {
    const w = this.g.world, lake = w.lake;
    if (rebuild && lake !== this.lake) {
      if (this.ice) { this.g.stage.scene.remove(this.ice); this.ice = null; }
      this.lake = lake; this.shore = null;
      if (lake) {
        const sc = this.g.stage.scene, i = sc.children.indexOf(lake.water);
        const sh = i > 0 ? sc.children[i - 1] : null;
        if (sh && sh.isMesh && Math.abs(sh.position.y - 0.03) < 1e-4 && sh.material && sh.material.color) { this.shore = sh; sh.material = sh.material.clone(); }
        // 물 색: 호수가 매 프레임 바꾸는 색에 계절 값을 곱한다 (셰이더에서)
        const wm = lake.water && lake.water.material;
        if (wm && !wm.__season) {
          wm.__season = true;
          const tint = this.waterTint;
          wm.onBeforeCompile = (sh2) => {
            sh2.uniforms.uSeasonWater = tint;
            sh2.fragmentShader = sh2.fragmentShader.replace('void main() {', 'uniform vec3 uSeasonWater;\nvoid main() {')
              .replace('#include <color_fragment>', '#include <color_fragment>\n  diffuseColor.rgb *= uSeasonWater;');
          };
          wm.customProgramCacheKey = () => 'season-water';
          wm.needsUpdate = true;
        }
        this.ice = makeIce(lake);
        sc.add(this.ice);
      }
    }
    if (this.shore) this.shore.material.color.copy(this.shoreCol);
    if (this.ice) { this.ice.visible = this.iceOp > 0.01; this.ice.userData.mat.opacity = 0.92 * this.iceOp; }
  }

  // ================================================================ 날리는 것
  makeParticles() {
    const sc = this.g.stage.scene;
    const atlas = new THREE.CanvasTexture(spriteAtlas());
    atlas.generateMipmaps = true; atlas.minFilter = THREE.LinearMipmapLinearFilter;
    // [계절, 종류, 개수, 크기(m), 아틀라스 칸, 더하기 섞기]
    const defs = [[WINTER, 0, 520, 0.11, [0, 0.5], false], [SPRING, 1, 280, 0.16, [0.5, 0.5], false], [SUMMER, 3, 40, 0.3, [0.5, 0], false],
      [SUMMER, 4, 90, 0.34, [0, 0.5], true], [AUTUMN, 2, 280, 0.2, [0, 0], false]];
    this.parts = [];
    let seed = 11;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (const [season, kind, n, size, cell, add] of defs) {
      const geo = new THREE.BufferGeometry();
      const pos = new Float32Array(n * 3), sd = new Float32Array(n * 4);
      for (let i = 0; i < n * 4; i++) sd[i] = rnd();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.setAttribute('aSeed', new THREE.BufferAttribute(sd, 4));
      const mat = new THREE.ShaderMaterial({
        defines: { KIND: kind },
        uniforms: { uTime: { value: 0 }, uCenter: { value: new THREE.Vector3() }, uBox: { value: new THREE.Vector3(20, 8, 20) }, uScale: { value: 800 }, uSize: { value: size },
          uOpacity: { value: 0 }, uNight: { value: 0 }, uLight: { value: 1 }, uTex: { value: atlas }, uCell: { value: new THREE.Vector2(cell[0], cell[1]) } },
        vertexShader: PART_VERT, fragmentShader: PART_FRAG, transparent: true, depthWrite: false,
        blending: add ? THREE.AdditiveBlending : THREE.NormalBlending,
      });
      const pts = new THREE.Points(geo, mat);
      pts.frustumCulled = false; pts.visible = false; pts.renderOrder = 5;
      sc.add(pts);
      this.parts.push({ season, kind, pts, mat, base: size, want: 0 });
    }
  }

  updateParticles(real) {
    const st = this.g.stage, r = st.rig;
    st.renderer.getDrawingBufferSize(this.tmpV);
    const scale = this.tmpV.y / (2 * Math.tan(st.cam.fov * Math.PI / 360));
    const hx = Math.max(10, Math.min(70, r.dist * 0.75)), hy = Math.max(4, Math.min(24, r.dist * 0.32));
    const k = Math.pow(Math.max(0.7, Math.min(3, r.dist / 34)), 0.75);
    const night = st.night || 0, light = 1 - 0.55 * night;
    for (let i = 0; i < this.parts.length; i++) {
      const P = this.parts[i], u = P.mat.uniforms;
      if (u.uOpacity.value !== P.want) {
        const d = P.want - u.uOpacity.value;
        u.uOpacity.value += Math.sign(d) * Math.min(Math.abs(d), real / 2.5);
      }
      P.pts.visible = u.uOpacity.value > 0.005;
      if (!P.pts.visible) continue;
      u.uTime.value = this.time;
      u.uCenter.value.set(r.tx, P.kind >= 3 ? 0 : hy, r.tz);
      u.uBox.value.set(P.kind >= 3 ? Math.min(hx, 30) : hx, hy, P.kind >= 3 ? Math.min(hx, 30) : hx);
      u.uScale.value = scale;
      u.uSize.value = P.base * k;
      u.uNight.value = night; u.uLight.value = light;
    }
  }

  // ================================================================ 시험 함수
  setSeason(i) {
    const c = this.g.clock, per = NUM.daysPerSeason;
    const yearStart = Math.floor((c.day - 1) / (per * 4)) * per * 4 + 1;
    c.day = yearStart + ((i % 4) + 4) % 4 * per;
    const s = c.seasonIndex;
    return this.loadSeason(s).then(() => { this.apply(s, true); return this.status(); });
  }

  status() {
    const w = this.g.world, models = {};
    let trees = 0, decid = 0;
    for (const o of w.nature.values()) { models[o.model] = (models[o.model] || 0) + 1; if (o.type === 'tree') { trees++; if (o.model.startsWith('season_decid')) decid++; } }
    let snow = 0, snowShown = 0, snowBody = 0;
    for (const b of w.blds) {
      for (const m of b.__snow || []) { snow++; if (m.visible) snowShown++; }
      b.group.traverse((o) => { if (o.isMesh && o.userData.__snowBody && o.visible) snowBody++; });
    }
    return {
      index: this.g.clock.seasonIndex, shown: this.target, name: SEASONS[this.target] ? SEASONS[this.target].name : '?',
      changing: this.groundFade >= 0 || this.qi < this.queue.length || this.snowDir !== 0,
      trees, decid, models, snow, snowShown, snowBody, melt: +this.melt.value.toFixed(2),
      particles: this.parts.filter((p) => p.pts.visible).map((p) => ['눈', '꽃잎', '낙엽', '나비', '반딧불이'][p.kind]),
      ground: (this.groundMat.map && this.groundMat.map === this.groundTex[this.target]) ? GROUND_TEX[this.target].split('/').pop() : 'fading',
      ice: !!(this.ice && this.ice.visible),
    };
  }

  api(obj) {
    obj.setSeason = (i) => this.setSeason(i);
    obj.season = () => this.status();
  }
}

// ---------------------------------------------------------------- 도우미
function showPool(p) { for (let i = 0; i < p.parts.length; i++) p.parts[i].im.visible = true; }
function isSnowMat(m) {
  if (!m) return false;
  if (m.name === 'snow') return true;
  return !m.name && !m.map && m.color && m.color.getHex() === 0xf4f7fb;
}
/** 녹는 무늬 없는 재질 복사본 (한 번만 만든다) */
function plainOf(m) { return m.__plain || (m.__plain = m.clone()); }
/**
 * 눈 메쉬가 '눈으로 만든 물건'(눈사람 몸통 등)인가: 건물 기준으로 땅에서 시작해 폭보다 높이 솟은 덩어리.
 * 지붕 눈(땅보다 높이 얹힘)·바닥 눈 더미(납작함)는 아니다. 메쉬마다 한 번만 재서 기억한다.
 */
const _rel = new THREE.Matrix4(), _box = new THREE.Box3();
function isSnowBody(o, root) {
  const ud = o.userData;
  if (ud.__snowBody !== undefined) return ud.__snowBody;
  const geo = o.geometry;
  if (!geo || !geo.attributes || !geo.attributes.position) return (ud.__snowBody = false);
  if (!geo.boundingBox) geo.computeBoundingBox();
  root.updateWorldMatrix(true, false); o.updateWorldMatrix(true, false);
  _rel.copy(root.matrixWorld).invert().multiply(o.matrixWorld);
  _box.copy(geo.boundingBox).applyMatrix4(_rel);
  const h = _box.max.y - _box.min.y, wide = Math.max(_box.max.x - _box.min.x, _box.max.z - _box.min.z);
  return (ud.__snowBody = h > 0.4 && h > 0.8 * wide && _box.min.y < 0.25 * h);
}
let snowRoot = null;     // hideSnow/showSnow 가 기준으로 삼는 뿌리 (놓기 그림자)
function hideSnow(o) { if (o.isMesh && !Array.isArray(o.material) && isSnowMat(o.material) && !isSnowBody(o, snowRoot)) o.visible = false; }
function showSnow(o) { if (o.isMesh && !Array.isArray(o.material) && isSnowMat(o.material)) o.visible = true; }

// 땅 그림을 못 받았을 때 그리는 대신 그림의 재료 (계절 순서): 밝은 풀색·짙은 풀색, 꽃 점, 낙엽, 남은 눈 무더기 수
const FB_GROUND = [
  { a: 0xf6f9fd, b: 0xe6edf6 },
  { a: 0x96c26a, b: 0x74a454, dots: [[0xffffff, 36], [0xf6e27a, 10]], snow: 4 },
  { a: 0x80b256, b: 0x5e9240, dots: [[0xffffff, 55], [0xf3d14a, 40], [0xeaa2bc, 30], [0xb9a6e0, 12]] },
  { a: 0xbeaa5c, b: 0x9c9448, leaves: [[0xd9531f, 70], [0xe98a24, 60], [0xb8401c, 30], [0xf0b23a, 30]] },
];
/**
 * 땅 그림을 못 받았을 때: 그 자리에서 그리는 이음매 없는 풀밭 그림 (256px).
 * 큰 얼룩(밝은·짙은 풀) + 잔풀 결 + 계절 점(꽃·낙엽·남은 눈). 반복돼도 물방울 무늬처럼 보이지 않게.
 */
function fallbackGround(s) {
  const N = 256, P = FB_GROUND[s] || FB_GROUND[1];
  const cv = document.createElement('canvas'); cv.width = cv.height = N;
  const x = cv.getContext('2d');
  let seed = 1234 + s * 777;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  // 이음매 없는 값 노이즈 (격자 칸 수 k 로 감김)
  const lat = (k) => { const a = new Float32Array(k * k); for (let i = 0; i < a.length; i++) a[i] = rnd(); return a; };
  const L4 = lat(4), L9 = lat(9);
  const noise = (L, k, u, v) => {
    const fx = u * k, fy = v * k, ix = Math.floor(fx), iy = Math.floor(fy);
    let tx = fx - ix, ty = fy - iy; tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty);
    const x0 = ix % k, y0 = iy % k, x1 = (x0 + 1) % k, y1 = (y0 + 1) % k;
    const a = L[y0 * k + x0] + (L[y0 * k + x1] - L[y0 * k + x0]) * tx, b = L[y1 * k + x0] + (L[y1 * k + x1] - L[y1 * k + x0]) * tx;
    return a + (b - a) * ty;
  };
  const rgb = (h) => ({ r: (h >> 16 & 255) / 255, g: (h >> 8 & 255) / 255, b: (h & 255) / 255 });   // 그림 칸 값 그대로 (색 공간 바꾸지 않음)
  const ca = rgb(P.a), cb = rgb(P.b);
  const img = x.createImageData(N, N), d = img.data;
  for (let y = 0; y < N; y++) for (let i = 0; i < N; i++) {
    const n = 0.65 * noise(L4, 4, i / N, y / N) + 0.35 * noise(L9, 9, i / N, y / N);
    let t = Math.max(0, Math.min(1, (n - 0.3) / 0.4)); t = t * t * (3 - 2 * t);
    const j = (rnd() - 0.5) * 0.06, o = (y * N + i) * 4;
    d[o] = Math.max(0, Math.min(255, (cb.r + (ca.r - cb.r) * t + j) * 255));
    d[o + 1] = Math.max(0, Math.min(255, (cb.g + (ca.g - cb.g) * t + j) * 255));
    d[o + 2] = Math.max(0, Math.min(255, (cb.b + (ca.b - cb.b) * t + j) * 255));
    d[o + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  // 가장자리를 넘는 것은 반대쪽에도 그려 이음매가 없게
  const wrap = (px, py, r, fn) => {
    for (const ox of [-N, 0, N]) for (const oy of [-N, 0, N]) {
      const qx = px + ox, qy = py + oy;
      if (qx > -r && qx < N + r && qy > -r && qy < N + r) fn(qx, qy);
    }
  };
  // 잔풀 결 (짧은 붓질)
  if (s !== WINTER) {
    x.lineWidth = 1; x.lineCap = 'round';
    for (let k = 0; k < 2200; k++) {
      const px = rnd() * N, py = rnd() * N, len = 2 + rnd() * 3.5, ang = -Math.PI / 2 + (rnd() - 0.5) * 0.9;
      const lit = rnd() < 0.5;
      x.strokeStyle = lit ? 'rgba(235,255,200,0.16)' : 'rgba(30,60,20,0.16)';
      wrap(px, py, 6, (qx, qy) => { x.beginPath(); x.moveTo(qx, qy); x.lineTo(qx + Math.cos(ang) * len, qy + Math.sin(ang) * len); x.stroke(); });
    }
  } else {
    for (let k = 0; k < 500; k++) {
      const px = rnd() * N, py = rnd() * N;
      x.fillStyle = rnd() < 0.5 ? 'rgba(255,255,255,0.35)' : 'rgba(200,215,235,0.18)';
      wrap(px, py, 3, (qx, qy) => { x.beginPath(); x.ellipse(qx, qy, 2.5, 1, 0, 0, 6.283); x.fill(); });
    }
  }
  // 남은 눈 무더기 (봄)
  for (let k = 0; k < (P.snow || 0); k++) {
    const px = rnd() * N, py = rnd() * N, r = 3 + rnd() * 4;
    const blobs = [];    // 눈 무더기 = 크기가 다른 동그라미 여럿 (모양은 무더기마다 다르게)
    for (let m = 0; m < 7; m++) { const a = rnd() * 6.283, q = rnd() * r * 0.9; blobs.push([Math.cos(a) * q * 1.3, Math.sin(a) * q * 0.7, r * (0.35 + rnd() * 0.4)]); }
    wrap(px, py, r * 2.5, (qx, qy) => {
      x.fillStyle = 'rgba(205,220,235,0.9)';
      for (const [bx, by, br] of blobs) { x.beginPath(); x.arc(qx + bx, qy + by + 1, br * 1.12, 0, 6.283); x.fill(); }
      x.fillStyle = 'rgba(250,252,255,0.95)';
      for (const [bx, by, br] of blobs) { x.beginPath(); x.arc(qx + bx, qy + by, br, 0, 6.283); x.fill(); }
    });
  }
  // 작은 꽃 (흰 테두리 점 + 가운데 색)
  for (const [hex, n] of P.dots || []) {
    const c = '#' + new THREE.Color(hex).getHexString();
    for (let k = 0; k < n; k++) {
      const px = rnd() * N, py = rnd() * N;
      wrap(px, py, 3, (qx, qy) => {
        x.fillStyle = 'rgba(40,70,30,0.25)'; x.beginPath(); x.arc(qx + 0.5, qy + 0.7, 1.5, 0, 6.283); x.fill();
        x.fillStyle = c; x.beginPath(); x.arc(qx, qy, 1.25, 0, 6.283); x.fill();
      });
    }
  }
  // 낙엽 (가을)
  for (const [hex, n] of P.leaves || []) {
    const c = '#' + new THREE.Color(hex).getHexString();
    for (let k = 0; k < n; k++) {
      const px = rnd() * N, py = rnd() * N, ang = rnd() * Math.PI, l = 2 + rnd() * 1.4;
      wrap(px, py, 5, (qx, qy) => {
        x.fillStyle = 'rgba(60,50,20,0.22)'; x.beginPath(); x.ellipse(qx + 0.6, qy + 0.8, l, l * 0.5, ang, 0, 6.283); x.fill();
        x.fillStyle = c; x.beginPath(); x.ellipse(qx, qy, l, l * 0.5, ang, 0, 6.283); x.fill();
      });
    }
  }
  return cv;
}

/** 겨울 호수: 물가를 따라 얇은 얼음 테두리 + 얼음 조각 몇 개 */
function makeIce(lake) {
  const wob = (a) => 1 + 0.07 * Math.sin(a * 3 + 1) + 0.05 * Math.sin(a * 5);
  const n = 96, pos = [], col = [], idx = [];
  for (let k = 0; k <= n; k++) {
    const a = k / n * Math.PI * 2, w = wob(a);
    const jag = 0.8 + 0.05 * Math.sin(a * 11 + 0.5) + 0.04 * Math.sin(a * 23 + 2) + 0.03 * Math.sin(a * 37);
    for (const [f, al] of [[jag, 0.25], [jag + 0.035, 0.8], [1.03, 0.95]]) {
      pos.push(Math.cos(a) * lake.rx * w * f, Math.sin(a) * lake.rz * w * f, 0);
      col.push(1, 1, 1, al);
    }
  }
  for (let k = 0; k < n; k++) for (let j = 0; j < 2; j++) {
    const a = k * 3 + j, b = (k + 1) * 3 + j;
    idx.push(a, b, a + 1, b, b + 1, a + 1);
  }
  // 얼음 조각
  let base = pos.length / 3;
  for (let f = 0; f < 7; f++) {
    const a = f / 7 * Math.PI * 2 + 0.4, rr = 0.62 + 0.1 * Math.sin(f * 2.3), w = wob(a);
    const cx = Math.cos(a) * lake.rx * w * rr, cy = Math.sin(a) * lake.rz * w * rr, R = 0.35 + 0.25 * ((f * 7) % 3) / 2;
    pos.push(cx, cy, 0); col.push(1, 1, 1, 0.8);
    const m = 7;
    for (let k = 0; k < m; k++) { const t = k / m * Math.PI * 2, q = R * (0.75 + 0.3 * Math.sin(k * 2.7 + f)); pos.push(cx + Math.cos(t) * q * 1.3, cy + Math.sin(t) * q, 0); col.push(1, 1, 1, 0.7); }
    for (let k = 0; k < m; k++) idx.push(base, base + 1 + k, base + 1 + (k + 1) % m);
    base += m + 1;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 4));
  geo.setIndex(idx); geo.computeVertexNormals();
  const mat = new THREE.MeshStandardMaterial({ color: 0xe6f1fa, roughness: 0.25, metalness: 0.05, vertexColors: true, transparent: true, opacity: 0.92, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -7, polygonOffsetUnits: -7, side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2; mesh.position.set(lake.cx, 0.05, lake.cz); mesh.receiveShadow = true;
  mesh.userData.mat = mat;
  return mesh;
}

/** 날리는 것 그림 (2×2 칸, 흰색 → 셰이더에서 색을 곱함): 동그란 빛 / 꽃잎 / 잎 / 나비 */
function spriteAtlas() {
  const cv = document.createElement('canvas'); cv.width = cv.height = 128;
  const x = cv.getContext('2d');
  // 왼쪽 위: 부드러운 동그라미 (눈송이·반딧불이)
  let gr = x.createRadialGradient(32, 32, 0, 32, 32, 28);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.45, 'rgba(255,255,255,0.9)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = gr; x.beginPath(); x.arc(32, 32, 28, 0, 6.283); x.fill();
  // 오른쪽 위: 꽃잎 (끝이 살짝 패인 둥근 잎)
  x.save(); x.translate(96, 32);
  gr = x.createLinearGradient(0, -24, 0, 24); gr.addColorStop(0, '#ffffff'); gr.addColorStop(1, '#e8d8de');
  x.fillStyle = gr; x.beginPath();
  x.moveTo(0, 24); x.bezierCurveTo(-22, 10, -18, -20, -5, -22); x.lineTo(0, -16); x.lineTo(5, -22); x.bezierCurveTo(18, -20, 22, 10, 0, 24); x.fill();
  x.restore();
  // 왼쪽 아래: 낙엽 (뾰족한 잎 + 잎맥)
  x.save(); x.translate(32, 96); x.rotate(0.6);
  x.fillStyle = '#ffffff'; x.beginPath(); x.moveTo(0, -26); x.bezierCurveTo(18, -12, 16, 14, 0, 24); x.bezierCurveTo(-16, 14, -18, -12, 0, -26); x.fill();
  x.strokeStyle = 'rgba(120,80,50,0.55)'; x.lineWidth = 2.2; x.beginPath(); x.moveTo(0, -22); x.lineTo(0, 28); x.stroke();
  x.lineWidth = 1.4; for (const y of [-10, 0, 10]) { x.beginPath(); x.moveTo(0, y); x.lineTo(9, y - 7); x.moveTo(0, y); x.lineTo(-9, y - 7); x.stroke(); }
  x.restore();
  // 오른쪽 아래: 나비 (날개 두 쌍 + 몸)
  x.save(); x.translate(96, 96);
  x.fillStyle = '#ffffff';
  for (const sx of [-1, 1]) {
    x.beginPath(); x.ellipse(sx * 12, -7, 12, 14, sx * 0.5, 0, 6.283); x.fill();
    x.beginPath(); x.ellipse(sx * 9, 11, 8, 10, -sx * 0.4, 0, 6.283); x.fill();
  }
  x.fillStyle = 'rgba(255,255,255,0.0)';
  x.globalCompositeOperation = 'source-atop'; x.fillStyle = 'rgba(0,0,0,0.18)';
  for (const sx of [-1, 1]) { x.beginPath(); x.arc(sx * 14, -9, 4, 0, 6.283); x.fill(); }
  x.globalCompositeOperation = 'source-over';
  x.fillStyle = '#3a2e28'; x.beginPath(); x.ellipse(0, 2, 2.6, 15, 0, 0, 6.283); x.fill();
  x.restore();
  return cv;
}

const NOISE_GLSL = `
float h21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vnoise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y); }`;

// 땅: 계절 그림 두 장 겹치기(uMix) + 큰 얼룩으로 반복 무늬 감추기
const GROUND_FRAG = `
#ifdef USE_MAP
  float gm = texture2D( uMacro, vMapUv * 0.173 ).r * 0.6 + texture2D( uMacro, vMapUv * 0.071 + 0.3 ).g * 0.4;
  float gw = smoothstep( 0.4, 0.6, gm );
  vec2 guv = vec2( vMapUv.x * 0.8 - vMapUv.y * 0.6, vMapUv.x * 0.6 + vMapUv.y * 0.8 ) + vec2( 0.37, 0.61 );
  vec4 sampledDiffuseColor = mix( texture2D( map, vMapUv ), texture2D( map, guv ), gw );
  if ( uMix > 0.0 ) {
    vec4 gB = mix( texture2D( uMap2, vMapUv ), texture2D( uMap2, guv ), gw );
    sampledDiffuseColor = mix( sampledDiffuseColor, gB, uMix );
  }
  float gl = texture2D( uMacro, vMapUv * 0.043 + 0.7 ).b;
  sampledDiffuseColor.rgb *= 1.0 + uAmp * ( gl - 0.5 ) * 2.0;
  diffuseColor *= sampledDiffuseColor;
#endif
`;

// 날리는 것: 위치는 셰이더가 시간으로 계산 (CPU 는 매 프레임 숫자 몇 개만 넘김)
//  KIND 0 눈, 1 꽃잎, 2 낙엽, 3 나비(낮), 4 반딧불이(밤)
const PART_VERT = `
attribute vec4 aSeed;
uniform float uTime, uScale, uSize, uOpacity, uNight, uLight;
uniform vec3 uCenter, uBox;
varying vec4 vCol; varying vec2 vRot; varying float vFlip;
void main() {
  float s = aSeed.w, t = uTime;
  vec3 size = uBox * 2.0, lo = uCenter - uBox;
  vec3 p; float a = 1.0, sz = uSize; vec3 col = vec3(1.0);
  vRot = vec2(1.0, 0.0); vFlip = 1.0;
#if KIND <= 2
  #if KIND == 0
    vec3 v = vec3(0.3, -(0.55 + s * 0.5), 0.15);
    vec3 sw = vec3(sin(t * 0.9 + s * 40.0), 0.0, cos(t * 0.7 + s * 30.0)) * 0.35;
    sz *= 0.6 + 0.8 * aSeed.y;
    col = vec3(1.0);
  #elif KIND == 1
    vec3 v = vec3(0.55, -(0.32 + s * 0.28), 0.25);
    vec3 sw = vec3(sin(t * 1.3 + s * 50.0) * 0.9, sin(t * 2.1 + s * 20.0) * 0.15, cos(t * 1.1 + s * 31.0) * 0.6);
    float an = t * (1.2 + s * 2.0) + s * 20.0; vRot = vec2(cos(an), sin(an));
    vFlip = abs(cos(t * (1.6 + s * 1.2) + s * 7.0));
    col = mix(vec3(1.0, 0.72, 0.84), vec3(1.0, 0.95, 0.97), fract(s * 7.3));
  #else
    vec3 v = vec3(0.7, -(0.75 + s * 0.5), 0.3);
    vec3 sw = vec3(sin(t * 1.0 + s * 50.0) * 1.2, 0.0, cos(t * 0.8 + s * 31.0) * 0.9);
    float an = t * (1.5 + s * 2.5) + s * 20.0; vRot = vec2(cos(an), sin(an));
    vFlip = abs(cos(t * (2.0 + s * 1.5) + s * 9.0));
    float c = fract(s * 5.17);
    col = c < 0.35 ? vec3(0.95, 0.5, 0.18) : c < 0.6 ? vec3(0.86, 0.27, 0.17) : c < 0.85 ? vec3(0.98, 0.76, 0.24) : vec3(0.75, 0.42, 0.16);
  #endif
  p = aSeed.xyz * size + v * t;
  p = lo + mod(p - lo, size) + sw;
  col *= uLight;
#else
  vec3 base = vec3(aSeed.x, 0.0, aSeed.z) * size + vec3(sin(t * 0.05 + s * 9.0), 0.0, cos(t * 0.043 + s * 7.0)) * 6.0;
  base = lo + mod(base - lo, size);
  #if KIND == 3
    p = base + vec3(sin(t * 0.45 + s * 10.0) * 2.2 + sin(t * 1.3 + s * 3.0) * 0.4, 0.0, cos(t * 0.37 + s * 17.0) * 2.2);
    p.y = 0.5 + aSeed.y * 1.8 + sin(t * 1.9 + s * 9.0) * 0.25;
    vFlip = 0.25 + 0.75 * abs(sin(t * 13.0 + s * 30.0));
    float an = sin(t * 0.8 + s * 12.0) * 0.5; vRot = vec2(cos(an), sin(an));
    float c = fract(s * 3.7);
    col = c < 0.3 ? vec3(1.0, 1.0, 0.97) : c < 0.55 ? vec3(1.0, 0.86, 0.3) : c < 0.8 ? vec3(1.0, 0.62, 0.25) : vec3(0.55, 0.75, 1.0);
    col *= uLight;
    a = 1.0 - smoothstep(0.3, 0.7, uNight);
  #else
    p = base + vec3(sin(t * 0.3 + s * 10.0) * 1.5, 0.0, cos(t * 0.27 + s * 17.0) * 1.5);
    p.y = 0.35 + aSeed.y * 2.3 + sin(t * 0.7 + s * 9.0) * 0.4;
    float bl = 0.5 + 0.5 * sin(t * (1.2 + s * 1.3) + s * 40.0);
    a = smoothstep(0.55, 0.85, uNight) * (0.15 + 0.85 * bl * bl);
    col = vec3(1.0, 0.92, 0.45) * (0.6 + 0.6 * bl);
    sz *= 0.7 + 0.5 * bl;
  #endif
#endif
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float d = -mv.z;
  a *= smoothstep(1.5, 5.0, d);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = clamp(sz * uScale / max(d, 0.1), 0.0, 72.0);
  vCol = vec4(col, a * uOpacity);
}`;
const PART_FRAG = `
uniform sampler2D uTex; uniform vec2 uCell;
varying vec4 vCol; varying vec2 vRot; varying float vFlip;
void main() {
  if (vCol.a < 0.01) discard;
  vec2 c = gl_PointCoord - 0.5;
  c = vec2(c.x * vRot.x - c.y * vRot.y, c.x * vRot.y + c.y * vRot.x);
  c.x /= max(0.18, vFlip);
  if (abs(c.x) > 0.5 || abs(c.y) > 0.5) discard;
  vec4 tx = texture2D(uTex, vec2(c.x + 0.5, 0.5 - c.y) * 0.5 + uCell);
  float a = tx.a * vCol.a;
  if (a < 0.02) discard;
  gl_FragColor = vec4(tx.rgb * vCol.rgb, a);
}`;
