// 이웃 마을 서리골과 사이좋게 지내기 (평화 경쟁).
//  - 우호도(0~100, 처음 30): 교환·선물·마실·잔치로 오르고, 제안을 거절하면 조금 내려가요.
//  - 교환: 하루이틀마다 아침에 서리골이 서로 넉넉한 물건을 바꾸자고 해요. 받아들이면 서리골 짐꾼 둘이 물건을 들고 걸어와
//    마을회관 앞에 내려놓고 인사한 뒤 돌아가요. 우리 물건은 쉬는 주민 한 명이 들고 서리골 회관까지 가져다줘요.
//    우리가 먼저 바꾸자고 할 수도 있고(늘 하는 교환 3가지, 우호도가 높을수록 더 많이 줘요), 선물을 보낼 수도 있어요.
//  - 마실: 저녁에 서리골 사람들이 놀러 와서 선술집·우물·광장에서 놀고 수다 떨다 돌아가요. 우리 주민도 가끔 놀러 가요.
//  - 잔치: 우호도 60 이상이면 서리골이 두 마을 사이 들판에서 함께 잔치를 열자고 초대해요.
//  - 봉화: 서리골이 먼저 밝히면 봄맞이 선물을, 우리가 먼저 밝히면 축하하러 와요.
//  - 우호도 80 이상이면 서리골 주민이 우리 마을로 이사 오고 싶어 하기도 해요.
// 주민을 잠시 맡을 때는 p.ctrl 연결 고리를 쓴다. 맡은 사람은 "일정(steps)"을 하나씩 하고,
// 끝나거나 중간에 끊겨도(밤·행사·건물 없어짐·사람 없어짐) 늘 p.ctrl = null 로 돌려준다.
//  - 함께 가는 무리는 한 줄로 모였다가(sync) 앞사람부터 차례로(stagger) 같은 빠르기로 걸어요 (겹치지 않게)
//  - 두 마을 사람 수다는 chatWith (people.chat 과 같은 모양, 다른 마을 사람끼리 사랑은 안 싹터요)
//  - 서리골 사람은 밤에 돌아가면 바로 자기 집에 들어가 자요 (people.aiThink 와 같은 집)
//  - 저장: saveData()/loadData() (save.js 가 불러요). 길 위에 있던 짐은 불러올 때 도착한 것으로 쳐요
//  - 두 마을은 따로 살아요: 우리 주민은 서리골 집을 받지 않고, 다른 마을 사람끼리는 사귀지 않아요 (People 덧씌움, 아래)
//  - 선물은 하루 두 번, 들고 갈 주민이 있을 때만. 서리골 창은 다른 팝업(이주민 등)을 덮지 않아요

import * as THREE from 'three';
import { ITEMS, FOODS, NUM } from './defs.js';
import { PHASE } from './clock.js';
import { People } from './people.js';

// ---------------------------------------------------------------- 두 마을은 따로 살아요 (people.js 를 고치지 않고 여기서 덧씌움)
// 집 정하기: 우리 주민은 서리골 집에 살지 않고, 서리골 사람은 집을 따로 정하지 않아요 (people.aiThink 가 서리골 집에서 재워요).
//  원래 assignHomes 는 서리골 집도 빈집으로 보고 우리 주민을 넣었어요 → 밤마다 60m 넘게 걸어가 서리골에서 자던 문제.
//  원래 방법을 그대로 쓰되, 그동안만 서리골 건물·사람을 빼고 봐요.
const baseAssignHomes = People.prototype.assignHomes;
People.prototype.assignHomes = function () {
  const w = this.w, blds = w.blds, list = this.list;
  for (const p of list) if (p.home && (p.ai || p.home.ai)) p.home = null;
  if (!blds.some((b) => b.ai) && !list.some((p) => p.ai)) return baseAssignHomes.call(this);
  w.blds = blds.filter((b) => !b.ai); this.list = list.filter((p) => !p.ai);
  try { return baseAssignHomes.call(this); } finally { w.blds = blds; this.list = list; }
};
// 사랑은 같은 마을 사람끼리만: 두 마을 사람이 수다를 떨어도(people.chat) 친구만 되고 사귀지는 않아요.
//  (서리골에서 이사 오면 p.ai 가 꺼지니까 그때부터는 우리 주민과 사랑이 싹틀 수 있어요)
const baseCompatible = People.prototype.compatible;
People.prototype.compatible = function (a, b) { return !!a.ai === !!b.ai && baseCompatible.call(this, a, b); };

// 물건 값어치 (교환 비율 계산용, 코인 1개 = 1)
const VAL = { log: 1, plank: 2, stone: 1.5, wheat: 1, flour: 2, bread: 3, fish: 3, egg: 2, milk: 2, cheese: 5, wool: 4, meat: 4, apple: 2, honey: 5, coins: 1 };
const EMOJI = { log: '🪵', plank: '🟫', stone: '🪨', wheat: '🌾', flour: '🥡', bread: '🍞', fish: '🐟', egg: '🥚', milk: '🥛', cheese: '🧀', wool: '🧶', meat: '🍖', apple: '🍎', honey: '🍯', coins: '🪙' };
const THEY_MAKE = ['log', 'plank', 'stone', 'wheat', 'bread', 'fish'];      // 서리골이 만드는 것
const KEEP = { log: 10, plank: 8, stone: 8, wheat: 6, flour: 2, bread: 6, fish: 6 };   // 서리골이 남겨 두는 양
const SPECIAL = ['egg', 'milk', 'cheese', 'wool', 'meat', 'apple', 'honey'];          // 서리골이 못 만드는 것 (좋아해요)
const MAX_DEALS = 3;      // 우리가 먼저 하는 교환: 하루 횟수
const MAX_GIFTS = 2;      // 선물: 하루 횟수 (우호도를 한꺼번에 사지 못하게)
// 저녁 마실 시각 (하루 비율): 해 질 녘(오후 5시쯤)에 도착해서 늦어도 밤 8시 반쯤 떠나요.
//  두 마을이 멀어서 걷는 데 오래 걸리니, 실제로는 지금 자리에서 집까지 걸리는 때를 따져서 밤(0.76) 전에 닿게 더 일찍 떠나요 (mustGo)
const ARRIVE = 0.45, LEAVE = 0.6, NIGHT = 0.76;
const HOME_BY = NIGHT - 0.035;     // 마실 다녀온 사람이 늦어도 이때까지는 집에 닿게 (밤 전에 조금 여유)

const LINES = {
  porterGo: ['다녀올게요!', '짐 싣고 출발~', '영차, 가 볼까?'],
  porterHi: ['서리골에서 왔어요!', '물건 가져왔어요~', '잘 받아 주세요!'],
  welcome: ['어서 와요!', '먼 길 오셨네요', '고마워요!', '반가워요~'],
  ourPorter: ['서리골에 전해 주고 올게요!', '우리 마을 물건이에요'],
  delivered: ['서리골에 잘 전했어요!', '여기 있어요~'],
  thanks: ['고마워요!', '잘 쓸게요~', '또 놀러 와요!'],
  goVisit: ['마실 가요~', '놀러 가 볼까?', '저 마을 구경 가자!'],
  visitHi: ['놀러 왔어요!', '안녕하세요~', '여기 정말 따뜻하네요'],
  visit: ['여기 선술집 좋네요', '우리 마을에도 놀러 와요', '봄이 오면 같이 놀아요', '이 마을 예쁘다!', '하하, 재밌어요', '오늘 저녁 뭐 드세요?'],
  bye: ['또 올게요!', '잘 있어요~', '오늘 즐거웠어요'],
  goOut: ['서리골 구경 가요!', '이웃 마을 놀러 가자~'],
  outHi: ['서리골 구경 왔어요!', '여기도 예쁘다!'],
  out: ['눈이 반짝반짝하네', '집이 귀엽다~', '서리골 빵 맛있다!', '여기 사람들 친절하네'],
  homeBack: ['재밌었다~', '집에 가자!'],
  goFest: ['잔치 가자!', '들판에서 잔치래!'],
  fest: ['함께 춤춰요!', '두 마을 만세!', '건배!', '즐겁다~', '랄랄라~', '내년에도 같이 해요!'],
  cheer: ['봄이 왔어요!', '축하해요!', '정말 멋진 봉화예요!', '봄을 데려와 줘서 고마워요!'],
  move: ['잘 부탁해요!', '오늘부터 이웃이에요~'],
  // 두 마을 사람 수다 (손님 / 주인)
  guestR: ['서리골은 눈이 정말 많이 와요', '여기는 참 따뜻하네요', '우리 마을에도 놀러 와요!', '봄이 오면 같이 꽃 보러 가요', '이 마을 사람들 다정하네요', '서리골 생선 맛 보셨어요?', '봉화는 잘 돼 가요?'],   // 서리골 손님
  guestO: ['여기 눈이 반짝반짝해요', '서리골 생선이 그렇게 맛있대요!', '우리 마을에도 놀러 와요!', '봄이 오면 같이 꽃 보러 가요', '집들이 참 예쁘네요', '봉화는 잘 돼 가요?'],   // 우리 마을 손님
  host: ['어서 와요, 반가워요!', '추운데 오느라 고생했어요', '천천히 구경하고 가요', '다음엔 우리가 놀러 갈게요', '하하, 그렇군요!', '또 놀러 와요~'],
};

// ---------------------------------------------------------------- 작은 도우미
const batchim = (w) => { const s = String(w), c = s.charCodeAt(s.length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0; };
const ga = (w) => w + (batchim(w) ? '이' : '가');
const eul = (w) => w + (batchim(w) ? '을' : '를');
const iname = (t) => (t === 'coins' ? '코인' : ITEMS[t] ? ITEMS[t].name : t);
const itxt = (t, n) => `${EMOJI[t] || ''} ${iname(t)} ${n}개`.trim();
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const dist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
const ring = (c, k, n, r, a0 = 0.4) => { const a = a0 + (k / Math.max(1, n)) * Math.PI * 2; return { x: c.x + Math.cos(a) * r, z: c.z + Math.sin(a) * r }; };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
/** 하루 비율 → 시계 글자 (clock.timeText 와 같은 셈: 0 = 오전 6시) */
const timeTxt = (f) => { const h = Math.floor((6 + Math.max(0, f) * 24) % 24); return (h < 12 ? '오전 ' : '오후 ') + (h % 12 === 0 ? 12 : h % 12) + '시'; };
const friendName = (f) => (f >= 80 ? '단짝 마을 💞' : f >= 60 ? '아주 친해요 💛' : f >= 40 ? '친해요 🙂' : f >= 20 ? '알고 지내요' : '서먹해요');

// 서리골 손님 머리 위 작은 눈꽃 표시 (누가 이웃 마을 사람인지 알아보기)
let BADGE_MAT = null;
function badgeMat() {
  if (BADGE_MAT) return BADGE_MAT;
  const cv = document.createElement('canvas'); cv.width = cv.height = 64;
  const c = cv.getContext('2d');
  c.fillStyle = '#4f86e8'; c.beginPath(); c.arc(32, 32, 27, 0, Math.PI * 2); c.fill();
  c.lineWidth = 4; c.strokeStyle = '#ffffff'; c.stroke();
  c.lineCap = 'round'; c.lineWidth = 4.5;
  for (let k = 0; k < 3; k++) {
    const a = k * Math.PI / 3 + Math.PI / 2, ca = Math.cos(a), sa = Math.sin(a);
    c.beginPath(); c.moveTo(32 - ca * 16, 32 - sa * 16); c.lineTo(32 + ca * 16, 32 + sa * 16); c.stroke();
    for (const s of [-1, 1]) {   // 가지 끝의 작은 갈래
      const ex = 32 + ca * 11 * s, ez = 32 + sa * 11 * s;
      c.lineWidth = 3;
      c.beginPath(); c.moveTo(ex, ez); c.lineTo(ex + Math.cos(a + 0.7 * s) * 5 * s, ez + Math.sin(a + 0.7 * s) * 5 * s); c.stroke();
      c.beginPath(); c.moveTo(ex, ez); c.lineTo(ex + Math.cos(a - 0.7 * s) * 5 * s, ez + Math.sin(a - 0.7 * s) * 5 * s); c.stroke();
      c.lineWidth = 4.5;
    }
  }
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  BADGE_MAT = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
  return BADGE_MAT;
}
// 코인 꾸러미 (금화 한 줌)
let COIN = null;
function coinStack() {
  if (!COIN) COIN = { geo: new THREE.CylinderGeometry(0.13, 0.13, 0.05, 14), mat: new THREE.MeshStandardMaterial({ color: 0xf2c14e, metalness: 0.45, roughness: 0.35 }) };
  const g = new THREE.Group();
  for (let k = 0; k < 4; k++) { const m = new THREE.Mesh(COIN.geo, COIN.mat); m.position.set((k % 2) * 0.035, 0.03 + k * 0.055, 0); m.castShadow = true; g.add(m); }
  return g;
}

// 잔치 모닥불의 불꽃 (불빛은 빛 계산을 늘리지 않게 빛나는 둥근 그림으로)
let FIRE = null;
function campFire() {
  if (!FIRE) {
    const cv = document.createElement('canvas'); cv.width = cv.height = 64;
    const c = cv.getContext('2d'), gr = c.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,214,120,0.9)'); gr.addColorStop(0.4, 'rgba(255,150,60,0.35)'); gr.addColorStop(1, 'rgba(255,120,40,0)');
    c.fillStyle = gr; c.fillRect(0, 0, 64, 64);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    FIRE = {
      outer: new THREE.MeshBasicMaterial({ color: 0xff8a2a, transparent: true, opacity: 0.88 }),
      inner: new THREE.MeshBasicMaterial({ color: 0xffe07a, transparent: true, opacity: 0.95 }),
      cone: new THREE.ConeGeometry(0.2, 0.85, 7),
      glow: new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }),
    };
  }
  const g = new THREE.Group(); g.userData.flames = [];
  for (let k = 0; k < 8; k++) {
    const inner = k >= 5, a = k * 2.39, r = inner ? 0.08 : 0.22;
    const m = new THREE.Mesh(FIRE.cone, inner ? FIRE.inner : FIRE.outer);
    m.position.set(Math.cos(a) * r, 0.62, Math.sin(a) * r);
    if (inner) m.scale.setScalar(0.7);
    g.add(m); g.userData.flames.push({ m, s: inner ? 0.7 : 1, sp: 5 + Math.random() * 4, p: Math.random() * 6 });
  }
  const glow = new THREE.Sprite(FIRE.glow); glow.scale.setScalar(3.6); glow.position.y = 0.9; glow.renderOrder = 5; g.add(glow);
  g.userData.glow = glow; g.userData.t = 0;
  return g;
}
function flicker(g, dt) {
  const u = g.userData; u.t += dt;
  for (const f of u.flames) { const k = 0.8 + 0.3 * Math.sin(u.t * f.sp + f.p); f.m.scale.set(f.s * (1.1 - k * 0.2), f.s * k * 1.1, f.s * (1.1 - k * 0.2)); f.m.position.y = 0.55 + k * 0.12 * f.s; }
  u.glow.material.opacity = 0.8 + 0.2 * Math.sin(u.t * 7.3);
}

export class Diplomacy {
  constructor(game) {
    this.g = game;
    this.friend = 30;
    this.theirs = { log: 24, plank: 16, stone: 14, wheat: 6, flour: 0, bread: 8, fish: 14 };   // 서리골 창고 (어림)
    this.theirCoins = 80;
    this.offer = null;          // 서리골의 교환 제안 {give:{type,n}, want:{type,n}, until}
    this.offerIn = 1;           // 다음 제안까지 남은 아침 수
    this.trips = [];            // 지금 진행 중인 나들이(짐꾼·마실·잔치·축하·이사)
    this.pending = [];          // 밤이라 아침에 떠날 짐꾼
    this.plan = {};             // 오늘의 계획 (마실 시각 등)
    this.invite = null; this.lastInvite = -9; this.fest = null;
    this.moveAsk = null; this.lastMoveAsk = -9;
    this.dealsToday = 0; this.giftsToday = 0;
    this.seen = { rival: false, ours: false, intro: false };
    this.log = [];
    this.tk = 0; this.fxT = 0;
    this.btn = null; this.panelOpen = false; this.panelH = ''; this.modalQ = [];
  }

  get pp() { return this.g.people; }
  get w() { return this.g.world; }
  /** 게임 시각 (날 + 하루 비율) */
  get T() { const c = this.g.clock; return c.day + c.frac; }
  ready() { const r = this.g.rival, h = this.w && this.w.hall; return !this.g.perf && !!(r && r.hall && h && !h.dead && h.state === 'active'); }

  news(text, kind = 'info') { this.log.unshift({ day: this.g.clock.day, text }); if (this.log.length > 30) this.log.length = 30; this.pp.news(text, kind); }
  addFriend(n) {
    const before = this.friend;
    this.friend = clamp(this.friend + n, 0, 100);
    if (before < 60 && this.friend >= 60) this.news('💛 서리골과 아주 친해졌어요! 이제 함께 잔치를 열자고 할지도 몰라요', 'love');
    if (before < 80 && this.friend >= 80) this.news('💞 서리골과 단짝 마을이 되었어요! 서리골 주민이 이사 오고 싶어 할지도 몰라요', 'love');
  }
  /** 우호도가 높을수록 서리골이 더 후하게 쳐 줘요 (30 → 1.08배, 100 → 1.25배) */
  fair() { return 1 + this.friend / 400; }

  // ================================================================ 자리
  ourHall() { const h = this.w.hall; return h && !h.dead ? h : null; }
  theirHall() { const h = this.g.rival.hall; return h && !h.dead ? h : null; }
  ourDoor() { const h = this.ourHall(); return h ? h.door : { x: this.w.size / 2, z: this.w.size / 2 }; }
  theirDoor() { const h = this.theirHall(); return h ? h.door : this.g.rival.home; }
  ourPlaza() { const h = this.ourHall(); return h ? h.toWorld(0, h.size[1] / 2 + 5) : this.ourDoor(); }
  theirPlaza() { const h = this.theirHall(); return h ? h.toWorld(0, h.size[1] / 2 + 4) : this.g.rival.home; }
  /** 건물 정문 앞에 나란히 서는 자리 */
  front(b, k, n, d = 1.4) {
    if (!b || b.dead) return null;
    const dl = b.toLocal(b.door.x, b.door.z);
    return b.toWorld(dl.x + (k - (n - 1) / 2) * 1.2, b.size[1] / 2 + d);
  }
  mine(type) { return this.w.blds.filter((b) => b.type === type && !b.ai && !b.dead && b.state === 'active'); }
  /** 손님이 모이는 곳: 선술집 → 우물 → 마을회관 앞 광장 */
  meetPlace() {
    const h = this.ourHall();
    const near = (a) => (h ? a.sort((x, y) => dist(x, h) - dist(y, h))[0] : a[0]);
    return near(this.mine('tavern')) || near(this.mine('well')) || null;
  }
  meetSpot(k, n) { const b = this.meetPlace(); return b ? this.front(b, k, n, 2.2) : ring(this.ourPlaza(), k, n, 1.6); }
  travelDays(a, b, mul = 1.15) { return dist(a, b) / (NUM.walkSpeed * NUM.offRoad * mul) / NUM.dayLength; }
  /** 걸어가는 데 드는 날 (건물 피해 돌아가는 길·인사 몫을 조금 더 쳐요) */
  walkDays(a, b, mul) { return this.travelDays(a, b, mul) * 1.1 + 0.01; }
  /** 서리골에서 우리 마을까지 돌아오는 길 (집으로 갈 때는 조금 서둘러요: homeMul) */
  backDays() { return this.walkDays(this.theirPlaza(), this.ourPlaza(), 1.2); }
  /** 마실 손님이 늦어도 이때는 떠나야 밤이 되기 전에 집에 닿아요 (오늘 날짜 + 하루 비율) */
  leaveBy() { return Math.floor(this.T) + Math.min(LEAVE, HOME_BY - this.backDays()); }
  /** 서리골 창에서 마실을 보낼 수 있는 마지막 시각 (모이기 + 가기 + 잠깐 놀기 + 돌아오기 가 밤 전에 끝나게) */
  outingLatest() { return HOME_BY - (0.04 + this.walkDays(this.ourPlaza(), this.theirPlaza(), 1.15) + 0.03 + this.backDays()); }
  /**
   * 지금 있는 자리에서 집까지 걸어야 하니, 이제 떠나야 밤 전에 닿는지 (놀다가 마을 반대편까지 갔어도 맞게)
   * where: 'ours' = 우리 마을에 놀러 온 서리골 사람 (집은 서리골), 'theirs' = 서리골에 놀러 간 우리 주민
   */
  mustGo(p, where) {
    const home = where === 'ours' ? this.theirDoor() : this.ourPlaza();
    return this.T + this.walkDays(p, home, 1.2) >= Math.floor(this.T) + HOME_BY;
  }

  // ================================================================ 사람 고르기
  freeAI(n, near) {
    const c = near || this.theirDoor();
    return this.pp.list.filter((p) => p.ai && !p.dead && !p.hidden && !p.sleeping && !p.ctrl && !p.chatting && p.stage === 'adult')
      .sort((a, b) => dist(a, c) - dist(b, c)).slice(0, n);
  }
  /** 우리 주민 중 쉬는 사람 (o.jobs: 일하는 사람도 잠시 빼 옴, o.kids: 아이·어르신도) */
  freeOurs(n, o = {}) {
    const not = o.not || [];
    const base = (p) => !p.ai && !p.dead && !p.sleeping && !p.ctrl && !p.event && !p.leaving && !p.carry && !p.weddingPlanned && !p.chatting && !not.includes(p);
    const calm = (p) => !this.busy(p) || !!p.slot;      // 하던 걸 끊어도 괜찮은 사람 (앉아 있는 사람은 일어나면 돼요)
    const tiers = [
      (p) => p.stage === 'adult' && !p.job && !p.hidden && calm(p),
      (p) => o.kids && p.stage !== 'adult' && !p.hidden && calm(p),
      (p) => p.stage === 'adult' && !p.job && calm(p),
      (p) => p.stage === 'adult' && !p.job,
      (p) => o.jobs && p.stage === 'adult' && p.job && p.job.kind === 'worker',
    ];
    const out = [];
    for (const t of tiers) for (const p of this.pp.list) { if (out.length >= n) return out; if (!out.includes(p) && base(p) && t(p)) out.push(p); }
    return out;
  }
  chatPartner(p, wantAI, rad) {
    const day = this.g.clock.phase === PHASE.DAY;
    let best = null, bd = rad;
    for (const q of this.pp.list) {
      if (q === p || q.dead || q.hidden || q.sleeping || q.ctrl || q.event || q.chatting || q.slot || q.carry || q.inside || q.leaving || !!q.ai !== wantAI || q.stage === 'kid') continue;
      if (!wantAI && day && q.job) continue;
      if (this.busy(q)) continue;
      const d = dist(p, q); if (d < bd) { bd = d; best = q; }
    }
    return best;
  }
  /** 하던 일을 끊으면 안 되는 사람 (가구 자리로 가는 중·일하는 중: 할 일 줄에 '하기'가 남아 있음) */
  busy(q) { return (q.cur && (q.cur.t === 'do' || q.cur.t === 'until')) || q.q.some((x) => x.t === 'do' || x.t === 'until'); }
  nearest(p, ok, rad) { let best = null, bd = rad; for (const q of this.pp.list) { if (q === p || !ok(q)) continue; const d = dist(p, q); if (d < bd) { bd = d; best = q; } } return best; }

  // ================================================================ 사람 맡기 (p.ctrl)
  newTrip(kind, o = {}) { const t = Object.assign({ kind, members: [], t0: this.T }, o); this.trips.push(t); return t; }
  addMember(trip, p, steps, o = {}) {
    if (p.job) this.pp.loseJob(p);
    const m = { p, trip, steps, i: 0, tries: 0, cache: {}, done: false, settle: o.settle || null, setLeaving: false };
    m.fn = (pq, phase) => this.drive(m, phase);
    if (!p.ai && !p.leaving) { p.leaving = true; m.setLeaving = true; }   // 맡은 동안은 일·마을 행사에 안 불려 가요
    this.prep(p);
    p.ctrl = m.fn;
    trip.members.push(m);
    return m;
  }
  /** people.useSlot 과 같지만, 어느 자리를 맡았는지 기억해요 */
  useSlot(p, m, b, actions, secs, after) {
    const before = new Set(b.reserved);
    const ok = this.pp.useSlot(p, b, actions, secs, () => { m.resv = null; if (after) after(); });
    if (ok) { const s = [...b.reserved].find((x) => !before.has(x)); m.resv = s ? { b, s } : null; }
    return ok;
  }
  /** 앉으러 가던 중에 끊겼으면 자리 예약을 풀어요 (앉아 있으면 leaveSlot 이 풀어 줘요) */
  freeResv(m) {
    const r = m.resv; if (!r) return;
    m.resv = null;
    const p = m.p;
    if (p.slot && p.slot.s === r.s) { this.pp.leaveSlot(p); return; }
    r.b.reserved.delete(r.s);
  }
  /** 하던 것 정리: 수다·자리·건물 안에서 나오기 */
  prep(p) {
    const pp = this.pp;
    if (p.chatting) { const q = p.chatting; if (q.chatting === p) q.chatting = null; p.chatting = null; }
    pp.clearQ(p);
    if (p.slot) pp.leaveSlot(p);
    if (p.inside) { const b = p.inside; if (p.hidden || b.dead || !b.hasInterior) { p.inside = null; pp.show(p, b.door.x, b.door.z); } else pp.exitBuilding(p); }
    else if (p.hidden) pp.show(p);
    p.sleeping = false; p.y = 0;
    if (p.lookNow !== p.look) pp.setLook(p, p.look);
  }
  outside(p) {
    const pp = this.pp;
    if (p.slot) pp.leaveSlot(p);
    const b = p.inside; if (!b) return;
    if (p.hidden || b.dead || !b.hasInterior) { p.inside = null; pp.show(p, b.door.x, b.door.z); return; }
    pp.exitBuilding(p);
  }
  /** people.think 가 부르는 맡은 사람의 생각: 일정을 차례로. 끝나면 false (평소대로) */
  drive(m, phase) {
    const p = m.p;
    if (m.done) return false;
    if (p.dead) { this.endMember(m, true); return false; }
    try {
      for (let guard = 0; guard < 12; guard++) {
        const st = m.steps[m.i];
        if (!st) { this.endMember(m, false); return false; }
        const r = st(p, m, phase);
        if (r === 'next') { m.i++; m.tries = 0; continue; }
        if (r === 'adv') { m.i++; m.tries = 0; }
        return true;
      }
    } catch (e) { console.warn('서리골 일정 오류', e); this.endMember(m, true); return false; }
    return true;
  }
  /** 맡은 일 끝 (abort: 중간에 끊김 → 남은 짐은 바로 전해 주고, 하던 동작 정리) */
  endMember(m, abort) {
    if (m.done) return;
    m.done = true;
    const p = m.p, pp = this.pp;
    if (abort && m.settle) m.settle(m);
    if (p.ctrl === m.fn) p.ctrl = null;
    if (m.carried && p.carry) { p.doll.carry(null); p.carry = null; }
    this.badge(p, false);
    if (m.setLeaving) p.leaving = false;
    if (abort && !p.dead) {
      this.freeResv(m);
      if (p.chatting) { const q = p.chatting; if (q.chatting === p) q.chatting = null; p.chatting = null; }
      if (p.slot) pp.leaveSlot(p);
      if (p.inside) { const b = p.inside; if (p.hidden && !p.sleeping) pp.show(p, b.door.x, b.door.z); p.inside = null; }
      pp.clearQ(p);
    }
    this.checkTrip(m.trip);
  }
  checkTrip(t) {
    if (t.closed || !t.members.every((m) => m.done)) return;
    t.closed = true;
    const k = this.trips.indexOf(t); if (k >= 0) this.trips.splice(k, 1);
    if (t.onEnd) t.onEnd(t);
  }
  endTrip(t) { for (const m of [...t.members]) this.endMember(m, true); this.checkTrip(t); }

  // ---------------------------------------------------------------- 일정 조각
  /** 그 자리까지 걷기 (끊기면 다시 걷기) */
  go(target, mul = 1, rad = 0.6) {
    return (p, m) => {
      const key = 'g' + m.i;
      if (!(key in m.cache)) m.cache[key] = typeof target === 'function' ? target(p, m) : target;
      const t = m.cache[key];
      if (!t) return 'next';
      if (p.inside || p.slot) { this.outside(p); return 'stay'; }
      if (Math.hypot(t.x - p.x, t.z - p.z) <= rad) return 'next';
      if (++m.tries > 6) return 'next';
      this.pp.walkTo(p, t.x, t.z, typeof mul === 'function' ? mul(p, m) : mul);
      return 'stay';
    };
  }
  /** 서리골 사람이 잘 집 (people.aiThink 와 같은 방법으로 골라요) */
  aiBed(p) {
    const homes = this.w.blds.filter((b) => b.ai && !b.dead && (b.def.kind === 'house' || b.def.kind === 'hq'));
    return homes.length ? homes[p.id % homes.length] : null;
  }
  /** 서리골 사람이 돌아갈 곳: 낮에는 회관 앞, 저녁 늦게는 바로 자기 집 문 앞 */
  homeSpotAI(p, k, n, r) {
    const h = this.g.clock.frac >= 0.6 || this.g.clock.phase === PHASE.NIGHT ? this.aiBed(p) : null;
    return h ? h.door : ring(this.theirDoor(), k, n, r);
  }
  /** 밤에 집 앞에 닿았으면 바로 들어가 자요 (people.aiThink 와 같은 잠) */
  sleepIfNight(p) {
    if (!p.ai || this.g.clock.phase !== PHASE.NIGHT) return;
    const h = this.aiBed(p);
    if (h && Math.hypot(h.door.x - p.x, h.door.z - p.z) < 2.5) { this.pp.clearQ(p); this.pp.hide(p); p.sleeping = true; p.sleepAt = h; }
  }
  /** 집에 돌아가는 걸음: 해가 지면 서둘러 뛰어가요 */
  homeMul(p) { const f = this.g.clock.frac, mul = f > 0.7 || this.g.clock.phase === PHASE.NIGHT ? 1.35 : 1.2; return p ? this.evenMul(p, mul) : mul; }
  /** 무리가 같은 빠르기로 걷게 (성격·나이에 따른 빠르기 차이를 없애서 줄이 흐트러지지 않게) */
  evenMul(p, mul) { return mul * NUM.walkSpeed / Math.max(0.5, this.pp.speed(p, 1)); }
  even(mul) { return (p) => this.evenMul(p, mul); }
  /** 한 번 하기 (동작을 넣으면 그 동작을 마치고 다음으로) */
  act(fn) { return (p, m) => { fn(p, m); return p.q.length ? 'adv' : 'next'; }; }
  pause(secs, anim) { return (p) => { this.pp.wait(p, secs, anim); return 'adv'; }; }
  /** 조건이 될 때까지 동작 되풀이 */
  until(cond, anim, secs = 1.5, yawFn) {
    return (p, m) => {
      if (cond(p, m)) return 'next';
      this.pp.wait(p, secs, typeof anim === 'function' ? anim(p, m) : anim, yawFn ? yawFn(p, m) : undefined);
      return 'stay';
    };
  }
  /** 일정 조각에 이름표 달기 (시험·상태 보기용: gather/walk/arrive/stay/home ...) */
  lab(name, fn) { fn.label = name; return fn; }
  /** 한 줄로 서는 자리: from 에서 to 쪽을 보고 맨 앞이 0번 (앞사람부터 출발하니까 걸을 때 겹치지 않아요) */
  lineUp(from, to, k, n, start = 2.2, gap = 1.4) {
    const dx = to.x - from.x, dz = to.z - from.z, d = Math.hypot(dx, dz) || 1, ux = dx / d, uz = dz / d;
    const fwd = start + (n - 1 - k) * gap, side = k % 2 ? 0.3 : -0.3;
    return { x: from.x + ux * fwd - uz * side, z: from.z + uz * fwd + ux * side };
  }
  /** 같이 가는 사람들이 다 모일 때까지 기다리기 (늦으면 20초쯤 뒤 먼저 출발) */
  sync(grp, key, maxWait = 20) {
    return this.lab('gather', (p, m) => {
      const at = grp[key] || (grp[key] = new Set());
      at.add(m);
      const live = grp.list.filter((x) => !x.done);
      const w = (m.cache['w' + key] = (m.cache['w' + key] || 0) + 1);
      if (live.every((x) => at.has(x)) || w > maxWait / 0.4) { if (grp[key + 'T'] == null) grp[key + 'T'] = this.T; return 'next'; }
      if (w === 1 && Math.random() < 0.5) this.talk(p, ['다들 모였나?', '조금만 기다려요~'], 'emote_dots', 1.6);
      this.pp.wait(p, 0.4, 'idle');
      return 'stay';
    });
  }
  /** 모두 모인 뒤 차례로 출발: k번째 사람은 모인 때부터 0.4 + k×gap 초 뒤에 (손 흔들며 기다려요) */
  stagger(grp, key, k, lines, emote, gap = 1.7) {
    return this.lab('depart', (p, m) => {
      if (!m.cache.said) { m.cache.said = true; this.talk(p, lines, emote); }
      const t0 = grp[key + 'T'];
      const left = t0 == null ? 0 : 0.4 + k * gap - (this.T - t0) * NUM.dayLength;
      if (left <= 0.02) return 'next';
      this.pp.wait(p, Math.min(0.5, left), left > 1.4 ? 'idle' : 'wave');   // 떠나기 직전에 손 흔들기
      return 'stay';
    });
  }
  /** 함께 가는 무리 (sync 와 같이 써요) */
  group() { return { list: [] }; }
  talk(p, lines, emote, secs = 2.6) {
    if (!p || p.hidden || p.dead) return;
    p.lastSay = performance.now() / 1000;
    // 눈 이야기·'봄이 오면'은 겨울에만 (다른 계절에는 빼고 고른다)
    if (lines && this.g.clock.seasonIndex !== 0) { const ls = lines.filter((l) => !/눈이|봄이 오면/.test(l)); if (ls.length) lines = ls; }
    this.g.bub.show(p, lines ? pick(lines) : '', emote, secs);
  }
  carry(p, type, n = 1, m) {
    if (!type) { if (p.carry) { p.doll.carry(null); p.carry = null; } if (m) m.carried = false; return; }
    if (type === 'coins') { p.doll.carry(coinStack()); p.carry = 'coins'; }
    else this.pp.carryItem(p, type, clamp(Math.ceil(n / 3), 1, 3));
    if (m) m.carried = true;
  }
  badge(p, on) {
    const d = p.doll; if (!d) return;
    if (on && !p.dBadge) { const s = new THREE.Sprite(badgeMat()); s.scale.setScalar(0.3); s.position.y = (p.headY || 1.55) + 0.4; s.renderOrder = 6; d.root.add(s); p.dBadge = s; }
    if (!on && p.dBadge) { if (p.dBadge.parent) p.dBadge.parent.remove(p.dBadge); p.dBadge = null; }
  }
  /**
   * 두 마을 사람의 수다 (people.chat 과 같은 모양: 마주 보고 번갈아 말하기).
   * 다른 마을 사람끼리라 사랑은 싹트지 않고 친구 사이만 가까워져요. a = 맡은 사람(손님), b = 그 마을 사람
   */
  chatWith(a, b) {
    const pp = this.pp;
    if (!b || b === a || b.chatting || a.chatting) return false;
    const mx = (a.x + b.x) / 2, mz = (a.z + b.z) / 2, ang = Math.atan2(b.x - a.x, b.z - a.z);
    const pa = { x: mx - Math.sin(ang) * 0.55, z: mz - Math.cos(ang) * 0.55 }, pb = { x: mx + Math.sin(ang) * 0.55, z: mz + Math.cos(ang) * 0.55 };
    a.chatting = b; b.chatting = a;
    pp.clearQ(b);
    pp.walkTo(a, pa.x, pa.z); pp.walkTo(b, pb.x, pb.z);
    let tmo = 12;
    const meet = (p, q) => pp.until(p, (x, dt) => { tmo -= dt / 2; if (q.chatting !== p) return true; return ((!a.cur || a.cur.t === 'until') && (!b.cur || b.cur.t === 'until')) || tmo < 0 ? true : 'idle'; });
    meet(a, b); meet(b, a);
    const n = 2 + Math.floor(Math.random() * 3);
    for (const [p, q] of [[a, b], [b, a]]) {
      for (let k = 0; k < n; k++) {
        const mine = (k % 2 === 0) === (p === a);
        pp.doit(p, () => { p.yaw = Math.atan2(q.x - p.x, q.z - p.z); if (mine && q.chatting === p) this.talk(p, p === a ? (a.ai ? LINES.guestR : LINES.guestO) : LINES.host, Math.random() < 0.5 ? 'emote_laugh' : 'emote_heart', 2); });
        pp.wait(p, 1.8, mine ? 'talk' : (Math.random() < 0.4 ? 'laugh' : 'idle'));
      }
      pp.doit(p, () => {
        if (p.chatting === q) p.chatting = null;
        if (p.friends) p.friends.set(q.id, Math.min(5, (p.friends.get(q.id) || 0) + 0.35));
        p.mood = Math.min(1, (p.mood || 0) + 0.04);
      });
    }
    return true;
  }
  /** 우리 마을 사람과 인사 (가까운 쉬는 주민과 수다, 없으면 손 흔들기) */
  greet(p, wantAI = false) {
    const q = this.chatPartner(p, wantAI, 14);
    if (q && Math.random() < 0.75 && this.chatWith(p, q)) return;
    const near = this.nearest(p, (x) => !!x.ai === wantAI && !x.dead && !x.hidden && !x.sleeping, 16);
    if (near) { p.yaw = Math.atan2(near.x - p.x, near.z - p.z); this.talk(near, wantAI ? LINES.thanks : LINES.welcome, 'emote_heart'); }
    this.pp.wait(p, 1.2, 'wave');
  }

  // ================================================================ 서리골 창고 (하루 살림)
  produce() {
    const th = this.theirs, w = this.w;
    const has = (t) => w.blds.some((b) => b.ai && !b.dead && b.type === t && b.state === 'active');
    const add = (k, n) => { th[k] = clamp(Math.round((th[k] || 0) + n), 0, 80); };
    add('log', 3); add('fish', 3); add('stone', 1);            // 기본: 땔감 줍기·얼음 낚시·돌 줍기
    if (has('woodcutter')) add('log', 6);
    if (has('sawmill')) { const n = Math.min(5, th.log || 0); add('log', -n); add('plank', n); } else add('plank', 1);
    if (has('quarry')) add('stone', 5);
    if (has('farm')) add('wheat', 6);
    if (has('bakery') || has('windmill')) { const n = Math.min(4, th.wheat || 0); add('wheat', -n); add('bread', n + 1); } else add('bread', 1);
    let eat = Math.ceil(this.pp.list.filter((p) => p.ai && !p.dead).length * NUM.foodPerDay);
    for (const k of ['bread', 'fish']) { const e = Math.min(eat, th[k] || 0); add(k, -e); eat -= e; }
    if (w.blds.some((b) => b.ai && !b.dead && b.con)) { add('plank', -2); add('stone', -1); }
    for (const k of SPECIAL) if (th[k]) add(k, -1);             // 받은 특산물은 조금씩 써요
    this.theirCoins = Math.min(300, this.theirCoins + 6);
  }
  ourCount() { return this.pp.list.filter((p) => !p.ai && !p.dead).length; }
  reserve(k) { return k === 'plank' ? 8 : k === 'stone' ? 6 : k === 'log' ? 4 : FOODS.includes(k) ? Math.max(3, Math.ceil(this.ourCount() * NUM.foodPerDay * 1.5)) : 2; }
  ourSurplus(k) { return k === 'coins' ? this.g.econ.coins - 20 : Math.floor((this.w.stock[k] || 0) - this.reserve(k)); }
  theirSurplus(k) { return k === 'coins' ? this.theirCoins - 20 : Math.floor((this.theirs[k] || 0) - (KEEP[k] != null ? KEEP[k] : 2)); }
  have(t) { return t === 'coins' ? this.g.econ.coins : Math.floor(this.w.stock[t] || 0); }
  take(t, n) { if (t === 'coins') this.g.econ.coins -= n; else { this.w.stock[t] -= n; this.w.emit('stock'); } }
  /** 서리골 창고에 넣기 */
  give(l) { if (!l) return; if (l.type === 'coins') this.theirCoins += l.n; else this.theirs[l.type] = (this.theirs[l.type] || 0) + l.n; }

  // ================================================================ 교환
  /** 서리골의 제안: 서리골이 넉넉한 것을 주고, 우리가 넉넉한(서리골에 모자란) 것을 달라고 해요 */
  makeOffer(forced) {
    if (!this.ready()) return null;
    const s = this.w.stock, th = this.theirs;
    const wants = Object.keys(ITEMS).filter((k) => this.ourSurplus(k) >= 2)
      .map((k) => ({ k, sc: (THEY_MAKE.includes(k) ? ((th[k] || 0) < 10 ? 1.4 : 0.5) : 2) * (0.6 + Math.random()) }))
      .sort((a, b) => b.sc - a.sc);
    let want = wants.length ? wants[0].k : null;
    if (!want && this.ourSurplus('coins') >= 10) want = 'coins';
    const gives = THEY_MAKE.filter((k) => k !== want && this.theirSurplus(k) >= 3)
      .map((k) => ({ k, sc: (1 + Math.max(0, (20 - (s[k] || 0)) / 20)) * (0.6 + Math.random()) }))
      .sort((a, b) => b.sc - a.sc);
    let give = gives.length ? gives[0].k : null;
    if (!give && want && want !== 'coins' && this.theirSurplus('coins') >= 10) give = 'coins';
    if (!want || !give) {
      if (!forced) return null;
      give = 'log'; want = 'coins';
    }
    const f = this.fair();
    let wn = want === 'coins' ? clamp(Math.floor(this.g.econ.coins * 0.3), 6, 25) : clamp(Math.floor(this.ourSurplus(want) * 0.5), 2, 8);
    let gn = Math.max(1, Math.round(wn * VAL[want] * f / VAL[give]));
    const cap = Math.max(1, this.theirSurplus(give));
    if (gn > cap && !forced) { gn = cap; wn = Math.max(1, Math.round(gn * VAL[give] / f / VAL[want])); }
    this.offer = { give: { type: give, n: gn }, want: { type: want, n: wn }, until: this.g.clock.day + 1, day: this.g.clock.day };
    this.news(`🤝 서리골이 교환하자고 해요: ${itxt(give, gn)} 줄 테니 ${itxt(want, wn)} 달래요 (위쪽 🏘️ 서리골 버튼)`, 'info');
    if (this.g.hud && !this.panelOpen) this.g.hud.toast('🏘️ 서리골이 교환을 제안했어요');
    return this.offer;
  }
  offerText(o) { return `${itxt(o.give.type, o.give.n)} ↔ ${itxt(o.want.type, o.want.n)}`; }

  acceptTrade() {
    const o = this.offer;
    if (!o) return { err: true, msg: '지금은 서리골의 제안이 없어요' };
    if (this.have(o.want.type) < o.want.n) return { err: true, msg: `${ga(iname(o.want.type))} ${o.want.n - this.have(o.want.type)}개 모자라요` };
    this.offer = null;
    this.take(o.want.type, o.want.n);
    if (o.give.type === 'coins') this.theirCoins = Math.max(0, this.theirCoins - o.give.n); else this.theirs[o.give.type] = Math.max(0, (this.theirs[o.give.type] || 0) - o.give.n);
    const n = o.give.n, loads = n >= 2 ? [{ type: o.give.type, n: Math.ceil(n / 2) }, { type: o.give.type, n: Math.floor(n / 2) }] : [{ type: o.give.type, n }];
    const r = this.startCaravan(loads, { type: o.want.type, n: o.want.n }, 'trade');
    this.addFriend(5);
    this.news(`🤝 서리골과 교환했어요! ${eul(itxt(o.give.type, o.give.n))} 짐꾼이 들고 와요 (우호도 +5)`, 'party');
    return { msg: r === 'later' ? '교환했어요! 짐꾼은 내일 아침에 출발해요' : '교환했어요! 서리골 짐꾼이 출발했어요' };
  }
  declineTrade() {
    if (!this.offer) return { err: true, msg: '지금은 서리골의 제안이 없어요' };
    this.offer = null;
    this.addFriend(-1);
    this.news('🙇 서리골의 교환 제안을 거절했어요. 서리골이 조금 서운해해요 (우호도 -1)', 'info');
    return { msg: '거절했어요' };
  }
  /** 우리가 먼저 하자고 하는 교환 3가지 (서리골 창고에 따라 받는 것이 바뀌어요) */
  deals() {
    const f = this.fair();
    const best = (cands, dflt) => cands.filter((k) => this.theirSurplus(k) >= 3).sort((a, b) => this.theirSurplus(b) - this.theirSurplus(a))[0] || dflt;
    const mk = (give, gn, get) => ({ give, gn, get, n: Math.max(1, Math.round(gn * VAL[give] * f / VAL[get])) });
    return [mk('plank', 4, best(['bread', 'fish'], 'fish')), mk('fish', 3, best(['stone', 'log'], 'log')), mk('coins', 15, best(['plank', 'log', 'stone', 'wheat'], 'log'))];
  }
  doDeal(i) {
    const d = this.deals()[i];
    if (!d) return { err: true, msg: '없는 교환이에요' };
    if (!this.ready()) return { err: true, msg: '아직 서리골과 오갈 수 없어요' };
    if (this.dealsToday >= MAX_DEALS) return { err: true, msg: '오늘은 서리골이 더 바꿀 물건이 없대요. 내일 다시 해 주세요' };
    if (this.have(d.give) < d.gn) return { err: true, msg: `${ga(iname(d.give))} ${d.gn - this.have(d.give)}개 모자라요` };
    if ((this.theirs[d.get] || 0) < d.n) return { err: true, msg: `서리골에 ${ga(iname(d.get))} 모자라요` };
    if (this.trips.filter((t) => t.kind === 'caravan').length >= 3) return { err: true, msg: '짐꾼들이 아직 오가는 중이에요. 조금 뒤에 다시 해 주세요' };
    this.take(d.give, d.gn);
    this.theirs[d.get] -= d.n;
    this.dealsToday++;
    const r = this.startCaravan([{ type: d.get, n: d.n }], { type: d.give, n: d.gn }, 'deal');
    this.addFriend(2);
    this.news(`🔁 서리골과 ${itxt(d.give, d.gn)} → ${itxt(d.get, d.n)} 교환을 했어요 (우호도 +2)`, 'info');
    return { msg: r === 'later' ? '교환했어요! 짐꾼은 내일 아침에 와요' : '교환했어요! 짐꾼이 곧 와요' };
  }
  /** 선물 보내기: 먹을거리 5개 또는 코인 20 → 우호도 ↑ (하루 두 번까지, 우리 주민이 직접 들고 가요) */
  gift(kind) {
    if (!this.ready()) return { err: true, msg: '아직 서리골과 오갈 수 없어요' };
    if (this.giftsToday >= MAX_GIFTS) return { err: true, msg: `오늘은 벌써 선물을 ${MAX_GIFTS}번 보냈어요. 내일 또 보내 주세요` };
    // 지금 떠나는 선물인데 들고 갈 사람이 없으면 보내지 않아요 (늦은 때는 내일 아침에 사람을 골라요)
    const c = this.g.clock, now = c.phase === PHASE.DAY && c.frac <= 0.55;
    if (now && !this.freeOurs(1, { jobs: true }).length) return { err: true, msg: '선물을 들고 갈 주민이 없어요. 쉬는 주민이 생기면 다시 해 주세요' };
    let l;
    if (kind === 'coins') {
      if (this.g.econ.coins < 20) return { err: true, msg: `코인이 ${20 - this.g.econ.coins}개 모자라요` };
      l = { type: 'coins', n: 20 };
    } else {
      const food = FOODS.filter((k) => (this.w.stock[k] || 0) >= 5).sort((a, b) => (this.w.stock[b] || 0) - (this.w.stock[a] || 0))[0];
      if (!food) return { err: true, msg: '선물할 먹을거리가 모자라요 (한 가지를 5개 이상)' };
      l = { type: food, n: 5 };
    }
    this.take(l.type, l.n);
    const up = kind === 'coins' ? 3 : 4;
    this.giftsToday++;
    this.startCaravan([], l, 'gift');
    this.addFriend(up);
    this.news(`🎁 서리골에 ${eul(itxt(l.type, l.n))} 선물했어요. 서리골이 정말 고마워해요 (우호도 +${up})`, 'love');
    return { msg: `선물을 보냈어요 (우호도 +${up})` };
  }

  /**
   * 짐꾼 행렬. loads = 서리골이 보내는 짐 [{type, n}] (짐꾼 한 명에 하나), ours = 우리가 보내는 짐 {type, n} (창고에서 이미 뺐음)
   * 서리골 짐꾼: 서리골 회관 → 우리 마을회관 앞에 내려놓기 → 인사 → 돌아가기
   * 우리 짐꾼: 마을회관에서 짐 들기 → 서리골 회관 앞에 내려놓기 → 인사 → 돌아오기
   */
  startCaravan(loads, ours, why = 'trade') {
    const c = this.g.clock;
    // 늦은 오후부터는 다녀오기 전에 밤이 되니까 내일 아침에 출발해요
    if (c.phase !== PHASE.DAY || c.frac > 0.55) { this.pending.push({ loads, ours, why }); this.news('🌙 오늘은 늦어서 짐꾼은 내일 아침에 출발해요', 'info'); return 'later'; }
    const trip = this.newTrip('caravan', { why, hardEnd: this.T + 1.2, loads, got: [] });
    const ais = loads.length ? this.freeAI(Math.min(2, loads.length), this.theirDoor()) : [];
    const per = ais.map(() => []);
    loads.forEach((l, k) => { if (ais.length) per[k % ais.length].push(l); else this.receive(trip, l, null); });
    const ourP = ours ? this.freeOurs(1, { jobs: true })[0] : null;
    let backLoad = ours && !ourP ? ours : null;          // 우리 쪽에 쉬는 사람이 없으면 서리골 짐꾼이 돌아갈 때 들고 가요
    if (backLoad && !ais.length) { this.give(backLoad); backLoad = null; }
    const grp = this.group();
    ais.forEach((p, k) => {
      const my = per[k], n = ais.length;
      const steps = [
        this.lab('gather', this.go(() => this.lineUp(this.theirDoor(), this.ourDoor(), k, n), 1)),
        this.lab('gather', this.act((p, m) => { this.carry(p, my[0].type, my[0].n, m); this.badge(p, true); })),
        this.sync(grp, 'dep'),
        this.stagger(grp, 'dep', k, LINES.porterGo, 'emote_star'),     // 한 줄로 걸어가게 차례로 출발
        this.lab('walk', this.go(() => this.front(this.ourHall(), k, n, 2.4) || this.ourDoor(), this.even(1.2))),
        this.lab('arrive', this.act((p, m) => {
          this.carry(p, null, 0, m);
          for (const l of my) this.receive(trip, l, p);
          m.settled = true;
          const h = this.ourHall(); if (h) p.yaw = Math.atan2(h.x - p.x, h.z - p.z);
          this.talk(p, why === 'gift' ? ['봄맞이 선물이에요!'] : LINES.porterHi, 'emote_heart');
          this.pp.wait(p, 1.6, 'wave');
        })),
        this.lab('greet', this.act((p) => this.greet(p, false))),
        this.lab('greet', this.pause(0.8 + k * 1.4, 'happy')),
      ];
      if (backLoad && k === 0) steps.push(this.lab('greet', this.act((p, m) => { this.carry(p, backLoad.type, backLoad.n, m); this.talk(p, ['이건 서리골로 가져갈게요!'], 'emote_thumbs'); })));
      steps.push(
        this.lab('home', this.go((p) => this.homeSpotAI(p, k, n, 1.4), (p) => this.homeMul(p))),
        this.lab('home', this.act((p, m) => { if (m.back) { this.carry(p, null, 0, m); this.give(backLoad); m.back = false; } this.badge(p, false); this.sleepIfNight(p); })),
      );
      const mm = this.addMember(trip, p, steps, { settle: (m) => { if (!m.settled) { m.settled = true; for (const l of my) this.receive(trip, l, null); } if (m.back) { this.give(backLoad); m.back = false; } } });
      mm.back = !!(backLoad && k === 0); mm.my = my; mm.backLoad = backLoad;
      grp.list.push(mm);
    });
    if (ourP) {
      const steps = [
        this.lab('gather', this.go(() => this.front(this.ourHall(), 0, 1, 1.0) || this.ourDoor(), 1)),
        this.lab('depart', this.act((p, m) => { this.carry(p, ours.type, ours.n, m); this.talk(p, LINES.ourPorter, 'emote_thumbs'); })),
        this.lab('walk', this.go(() => this.front(this.theirHall(), 0, 1, 1.8) || this.theirDoor(), 1.2)),
        this.lab('arrive', this.act((p, m) => {
          this.carry(p, null, 0, m); this.give(ours); m.settled = true;
          const th = this.theirHall(); if (th) p.yaw = Math.atan2(th.x - p.x, th.z - p.z);
          this.w.puff(p.x, p.z, 0xffe9a8, 8, 0.8, 0.6);
          this.talk(p, LINES.delivered, 'emote_star'); this.pp.wait(p, 1.4, 'wave');
        })),
        this.lab('greet', this.act((p) => this.greet(p, true))),
        this.lab('home', this.go(() => ring(this.ourPlaza(), 0, 1, 1.5), (p) => this.homeMul(p))),
        this.lab('home', this.act((p) => { if (Math.random() < 0.5) this.talk(p, LINES.homeBack, 'emote_star'); })),
      ];
      this.addMember(trip, ourP, steps, { settle: (m) => { if (!m.settled) { this.give(ours); m.settled = true; } } }).ours = ours;
    }
    this.checkTrip(trip);
    return trip;
  }
  /** 서리골 짐이 우리 창고에 들어옴 */
  receive(trip, l, p) {
    const w = this.w;
    if (l.type === 'coins') this.g.econ.coins += l.n; else { w.stock[l.type] = (w.stock[l.type] || 0) + l.n; w.emit('stock'); }
    trip.got.push(l);
    if (p) {
      w.puff(p.x, p.z, 0xffe9a8, 10, 0.8, 0.6);
      if (this.g.audio) this.g.audio.play('coin', 0.5, p.x, p.z);
      this.g.bub.show({ x: p.x, z: p.z, y: 0.6, headY: 1.9 }, `+${l.n}`, 'emote_star', 1.8);
    }
    if (trip.got.length === trip.loads.length) {
      const sum = {}; for (const g of trip.got) sum[g.type] = (sum[g.type] || 0) + g.n;
      const list = Object.entries(sum).map(([t, n]) => itxt(t, n)).join(', ');
      this.news(trip.why === 'gift' ? `🎁 서리골의 봄맞이 선물이 도착했어요: ${list}` : `📦 서리골 짐꾼이 ${eul(list)} 마을회관 앞에 내려놓았어요`, 'party');
    }
  }

  // ================================================================ 마실 (서리골 → 우리 마을)
  startVisit(forced) {
    if (!this.ready() || this.trips.some((t) => t.kind === 'visit')) return null;
    const want = 2 + Math.floor(Math.random() * 3);
    const ais = this.freeAI(want, this.theirDoor());
    if (ais.length < 2) return null;
    const n = ais.length;
    const trip = this.newTrip('visit', { hardEnd: this.T + 0.6, leaveAt: forced ? null : this.leaveBy(), forced, arrived: 0 });
    const grp = this.group();
    ais.forEach((p, k) => {
      const steps = [
        this.lab('gather', this.act((p) => { this.badge(p, true); })),
        this.lab('gather', this.go(() => this.lineUp(this.theirPlaza(), this.ourDoor(), k, n, 0), 1.05)),
        this.sync(grp, 'dep'),
        this.stagger(grp, 'dep', k, LINES.goVisit, 'emote_music'),
        this.lab('walk', this.go(() => this.meetSpot(k, n), this.even(1.15))),
        this.lab('arrive', this.act((p) => {
          if (!trip.arrived) { if (trip.leaveAt == null) trip.leaveAt = this.T + 0.14; this.news(`🏘️ 서리골 사람 ${n}명이 우리 마을에 놀러 왔어요! 선술집·우물·광장에서 놀다 가요`, 'party'); }
          trip.arrived++;
          const b = this.meetPlace(); if (b) p.yaw = Math.atan2(b.x - p.x, b.z - p.z);
          this.talk(p, LINES.visitHi, 'emote_heart'); this.pp.wait(p, 1.4, 'wave');
        })),
        this.lab('stay', this.hang(trip, 'ours')),
        this.lab('bye', this.act((p) => { this.talk(p, LINES.bye, 'emote_star'); this.pp.wait(p, 1.2 + k * 0.9, 'wave'); })),
        this.lab('home', this.go((p) => this.homeSpotAI(p, k, n, 2.0), (p) => this.homeMul(p))),
        this.lab('home', this.act((p) => { this.badge(p, false); this.sleepIfNight(p); })),
      ];
      grp.list.push(this.addMember(trip, p, steps));
    });
    trip.onEnd = () => { if (trip.arrived) this.addFriend(2); };
    this.news(`🚶 서리골 사람 ${n}명이 우리 마을로 마실을 나섰어요`, 'info');
    this.checkTrip(trip);
    return ais.map((p) => p.name);
  }
  /** 머무는 동안: 시간이 될 때까지 이것저것 하며 놀기 */
  hang(trip, where) {
    return (p, m) => {
      const leaveAt = trip.leaveAt != null ? trip.leaveAt : this.T + 0.1;
      if (this.T >= leaveAt || (!trip.forced && (this.g.clock.phase === PHASE.NIGHT || this.mustGo(p, where)))) return 'next';
      if (where === 'ours') this.hangOurs(p, m); else this.hangTheirs(p, m);
      if (!p.q.length) this.pp.wait(p, 1, 'idle');
      return 'stay';
    };
  }
  hangOurs(p, m) {
    const pp = this.pp, r = !m.last ? 0.5 : m.last === 'chat' ? 0.2 : Math.random();     // 처음에는 수다, 수다 다음엔 선술집
    const tav = this.mine('tavern').filter((b) => b.hasInterior).sort((a, b) => dist(a, p) - dist(b, p))[0];
    const well = this.mine('well').sort((a, b) => dist(a, p) - dist(b, p))[0];
    if (tav && m.last && m.last !== 'tav' && r < 0.45) {
      if (p.inside && p.inside !== tav) { this.outside(p); return; }
      const ok = this.useSlot(p, m, tav, ['eat', 'tea', 'sit', 'chat'], 7 + Math.random() * 6, () => {
        if (Math.random() < 0.6 && this.g.econ) this.g.econ.shopVisit(p, tav);   // 우리 선술집에서 사 먹어요 (코인)
        if (Math.random() < 0.5) this.talk(p, LINES.visit, 'emote_heart');
      });
      if (ok) { m.last = 'tav'; return; }
    }
    if (p.inside || p.slot) { this.outside(p); return; }
    if (m.last !== 'chat' && r < 0.8) {
      const q = this.chatPartner(p, false, 32);
      if (q && this.chatWith(p, q)) { m.last = 'chat'; return; }
    }
    if (well && m.last !== 'well') {
      const s = well.slots.filter((x) => x.action === 'chat' && !well.reserved.has(x));
      const t = s.length ? well.slotWorld(pick(s)) : pp.near(well, 2.6);
      pp.walkTo(p, t.x, t.z, 0.9);
      pp.doit(p, () => { p.yaw = Math.atan2(well.x - p.x, well.z - p.z); this.talk(p, LINES.visit, 'emote_laugh'); });
      pp.wait(p, 3 + Math.random() * 3, Math.random() < 0.5 ? 'talk' : 'laugh');
      m.last = 'well';
      return;
    }
    const t = pp.near({ door: this.ourPlaza() }, 4);
    pp.walkTo(p, t.x, t.z, 0.8);
    pp.wait(p, 2 + Math.random() * 2, Math.random() < 0.4 ? 'laugh' : 'idle');
    if (Math.random() < 0.4) pp.doit(p, () => this.talk(p, LINES.visit, 'emote_music'));
    m.last = 'look';
  }

  // ================================================================ 마실 (우리 주민 → 서리골)
  /** forced: 시험용 (밤에도), byPlayer: 서리골 창에서 보낸 마실 (도착해서 잠깐 놀다 와요) */
  startOuting(forced, byPlayer) {
    if (!this.ready() || this.trips.some((t) => t.kind === 'outing')) return null;
    const want = 1 + Math.floor(Math.random() * 3);
    const ours = this.freeOurs(want, { jobs: !!forced });
    if (!ours.length) return null;
    const n = ours.length;
    const trip = this.newTrip('outing', { hardEnd: this.T + 0.7, leaveAt: forced || byPlayer ? null : this.leaveBy(), forced, arrived: 0, stay: byPlayer ? 0.14 : 0.1 });
    const grp = this.group();
    ours.forEach((p, k) => {
      const steps = [
        this.lab('gather', this.go(() => this.lineUp(this.ourPlaza(), this.theirDoor(), k, n, 0), 1.05)),
        this.sync(grp, 'dep'),
        this.stagger(grp, 'dep', k, LINES.goOut, 'emote_music'),
        this.lab('walk', this.go(() => ring(this.theirPlaza(), k, n, 1.8), this.even(1.15))),
        this.lab('arrive', this.act((p) => {
          if (!trip.arrived) { if (trip.leaveAt == null) trip.leaveAt = Math.max(this.T + 0.03, Math.min(this.T + trip.stay, this.leaveBy())); this.news(`🧭 우리 주민 ${ga(ours.map((q) => q.name).join(', '))} 서리골에 놀러 갔어요`, 'info'); }
          trip.arrived++;
          this.talk(p, LINES.outHi, 'emote_sparkle'); this.pp.wait(p, 1.2, 'happy');
        })),
        this.lab('stay', this.hang(trip, 'theirs')),
        this.lab('bye', this.act((p) => { this.talk(p, LINES.bye, 'emote_star'); this.pp.wait(p, 1.0 + k * 0.9, 'wave'); })),
        this.lab('home', this.go(() => ring(this.ourPlaza(), k, n, 2.0), (p) => this.homeMul(p))),
        this.lab('home', this.act((p) => { p.joy = Math.min(0.3, (p.joy || 0) + 0.1); if (Math.random() < 0.6) this.talk(p, LINES.homeBack, 'emote_heart'); })),
      ];
      grp.list.push(this.addMember(trip, p, steps));
    });
    trip.onEnd = () => { if (trip.arrived) this.addFriend(2); };
    this.checkTrip(trip);
    return ours.map((p) => p.name);
  }
  hangTheirs(p, m) {
    const pp = this.pp, r = Math.random();
    const blds = this.w.blds.filter((b) => b.ai && !b.dead && b.state === 'active');
    const tav = blds.find((b) => b.type === 'tavern' && b.hasInterior);
    if (tav && m.last !== 'tav' && r < 0.35) {
      if (p.inside && p.inside !== tav) { this.outside(p); return; }
      if (this.useSlot(p, m, tav, ['eat', 'tea', 'sit', 'chat'], 7 + Math.random() * 5, () => { if (Math.random() < 0.5) this.talk(p, LINES.out, 'emote_heart'); })) { m.last = 'tav'; return; }
    }
    if (p.inside || p.slot) { this.outside(p); return; }
    if (m.last !== 'chat' && r < 0.7) {
      const q = this.chatPartner(p, true, 24);
      if (q && this.chatWith(p, q)) { m.last = 'chat'; return; }
    }
    const b = blds.length ? pick(blds) : null;
    const t = b ? pp.near(b, 5) : pp.near({ door: this.theirPlaza() }, 4);
    pp.walkTo(p, t.x, t.z, 0.8);
    if (b) pp.doit(p, () => { p.yaw = Math.atan2(b.x - p.x, b.z - p.z); });
    pp.wait(p, 2 + Math.random() * 2, Math.random() < 0.4 ? 'surprised' : 'happy');
    pp.doit(p, () => { if (Math.random() < 0.5) this.talk(p, LINES.out, 'emote_sparkle'); });
    m.last = 'look';
  }

  // ================================================================ 두 마을 잔치 (우호도 60 이상)
  makeInvite(forced) {
    if (!this.ready() || this.invite || this.fest) return null;
    const c = this.g.clock;
    this.invite = { day: c.day, startAt: forced ? c.frac : 0.34, answer: null };
    this.lastInvite = c.day;
    this.news('💌 서리골이 오늘 오후 두 마을 사이 들판에서 함께 잔치를 열자고 초대했어요! (🏘️ 서리골 버튼)', 'party');
    if (!forced) this.queueModal(() => this.inviteModal());
    return this.invite;
  }
  answerInvite(yes, now) {
    const iv = this.invite; if (!iv) return null;
    if (!yes) { this.invite = null; this.news('🙏 이번 잔치는 사양했어요. 서리골이 다음에 또 부르겠대요', 'info'); return 'no'; }
    iv.answer = true;
    if (now) return this.startFestival();
    this.news('🎉 잔치에 가기로 했어요! 오후가 되면 쉬는 주민 몇 명이 들판으로 가요', 'party');
    return 'yes';
  }
  festSpot() {
    const a = this.ourHall() || this.ourDoor(), b = this.theirHall() || this.g.rival.home, w = this.w;
    const mx = (a.x + b.x) / 2, mz = (a.z + b.z) / 2;
    let best = null;
    for (let r = 0; r <= 20 && !best; r += 2) {
      for (let k = 0; k < (r ? 12 : 1); k++) {
        const ang = (k / 12) * Math.PI * 2, x = mx + Math.cos(ang) * r, z = mz + Math.sin(ang) * r;
        if (w.freeSpot(x, z, 3.8)) { best = { x, z }; break; }
      }
    }
    const open = !!best;
    if (!best) best = { x: mx, z: mz };
    // 잔치 마당 치우기 (덤불·그루터기, 빈 자리를 못 찾았으면 나무도)
    const gone = []; w.natureNear(best.x, best.z, 5, (o) => { if (o.type !== 'rock' && (o.type !== 'tree' || !open)) gone.push(o); });
    for (const o of gone) w.removeNature(o);
    return best;
  }
  async decorate(f) {
    const lib = this.g.lib, sc = this.w.stage.scene, c = f.at, h = this.ourHall() || this.ourDoor();
    const face = Math.atan2(h.x - c.x, h.z - c.z), cs = Math.cos(face), sn = Math.sin(face);
    const put = async (k, lx, lz, ry, s = 1) => {
      await lib.loadProp(k);
      if (f.cleaned) return;
      const o = lib.prop(k);
      o.position.set(c.x + lx * cs + lz * sn, 0, c.z - lx * sn + lz * cs); o.rotation.y = face + ry; o.scale.setScalar(s);
      o.traverse((q) => { if (q.isMesh) { q.castShadow = true; q.receiveShadow = true; } });
      sc.add(o); f.decor.push(o);
    };
    await put('campfire', 0, 0, 0, 1.3);
    if (!f.cleaned) { const fire = campFire(); fire.position.set(c.x, 0, c.z); sc.add(fire); f.decor.push(fire); f.fire = fire; }
    await put('lantern_string', -5.2, -1.6, 0.4); await put('lantern_string', 5.2, -1.6, -0.4);
    await put('picnic_table', 0, -5.4, 0); await put('trade_post', 5.0, 3.6, -0.8, 0.9);
    await put('flag_pole', -4.8, 3.4, 0, 1.1);
  }
  startFestival() {
    if (!this.ready() || this.fest) return null;
    this.invite = null;
    const hm = this.g.hud && this.g.hud.modalEl;            // 아직 떠 있는 초대 팝업은 닫아요 (잔치가 벌써 시작)
    if (hm && hm.style.display !== 'none' && hm.querySelector('[data-invite]')) hm.style.display = 'none';
    const at = this.festSpot();
    const ours = this.freeOurs(4, { kids: true });
    if (ours.length < 3) ours.push(...this.freeOurs(3 - ours.length, { jobs: true, not: ours }));
    const ais = this.freeAI(4, at);
    const all = [...ours, ...ais];
    if (!all.length) return null;
    const n = all.length;
    const est = Math.max(...all.map((p) => this.travelDays(p, at, 1.2)));
    const trip = this.newTrip('fest', { hardEnd: this.T + est + 0.5 });
    const f = this.fest = { at, decor: [], start: this.T, endAt: this.T + Math.min(0.35, est) + 0.09, arrived: 0, trip, names: { ours: ours.map((p) => p.name), ais: ais.map((p) => p.name) } };
    this.decorate(f);
    all.forEach((p, k) => {
      const home = () => (p.ai ? ring(this.theirDoor(), k, n, 2.0) : ring(this.ourPlaza(), k, n, 2.0));
      const steps = [
        this.lab('depart', this.act((p) => { if (p.ai) this.badge(p, true); this.talk(p, LINES.goFest, 'emote_music'); })),
        this.lab('walk', this.go(() => ring(at, k, n, 2.7 + (k % 2) * 0.8), 1.2)),
        this.lab('arrive', this.act((p, m) => { m.dancing = true; f.arrived++; if (f.arrived === 1) { this.news('🎪 두 마을 잔치가 시작됐어요! 함께 춤추며 놀아요', 'party'); if (this.g.audio) this.g.audio.play('complete', 0.6, at.x, at.z); } })),
        this.lab('stay', this.until(() => this.T >= f.endAt, (p, m) => { m.k = (m.k || 0) + 1; return ['dance', 'happy', 'dance', 'laugh', 'dance', 'wave'][m.k % 6]; }, 1.7, (p) => Math.atan2(at.x - p.x, at.z - p.z))),
        this.lab('bye', this.act((p, m) => { m.dancing = false; if (!p.ai) p.joy = Math.min(0.3, (p.joy || 0) + 0.2); this.talk(p, LINES.bye, 'emote_heart'); this.pp.wait(p, 1.2, 'wave'); })),
        this.lab('home', this.go(home, 1.1)),
        this.lab('home', this.act((p) => this.badge(p, false))),
      ];
      this.addMember(trip, p, steps);
    });
    trip.onEnd = () => this.endFest(true);
    this.news(`💃 잔치에 가요: 우리 마을 ${ours.length}명, 서리골 ${ais.length}명이 들판으로 모여요`, 'party');
    this.checkTrip(trip);
    return { at, ours: f.names.ours, ais: f.names.ais };
  }
  festFx(dt) {
    const f = this.fest; if (!f || f.cleaned) return;
    if (f.fire) flicker(f.fire, dt);
    if (this.T >= f.endAt + 0.03) { this.endFest(false); return; }
    if (!f.arrived || this.T >= f.endAt) return;
    this.fxT += dt;
    if (this.fxT < 0.9) return;
    this.fxT = 0;
    if (this.w.stage.isNear(f.at.x, f.at.z)) {
      this.w.puff(f.at.x + (Math.random() - 0.5) * 3, f.at.z + (Math.random() - 0.5) * 3, pick([0xff8fb5, 0xffe066, 0x8fd3ff, 0xa8f0a0]), 6, 2.6, 2.4);
      this.w.smoke(f.at.x, 1.1, f.at.z);
    }
    const ms = f.trip.members.filter((m) => !m.done && m.dancing);
    if (ms.length && Math.random() < 0.8) this.talk(pick(ms).p, LINES.fest, pick(['emote_music', 'emote_laugh', 'emote_heart']), 2);
  }
  /** 잔치 마무리: 장식 치우기, 마을 기분 ↑ */
  endFest(tripDone) {
    const f = this.fest; if (!f) return;
    if (!f.cleaned) {
      f.cleaned = true;
      for (const o of f.decor) this.w.stage.scene.remove(o);
      f.decor.length = 0;
      if (f.arrived) {
        this.addFriend(6);
        const e = this.g.econ;
        if (e) e.buffs.push({ name: '이웃 잔치의 여운', buff: { mood: 0.06 }, until: this.g.clock.day + 1 });
        this.news('🎉 두 마을 잔치가 끝났어요! 모두 기분이 좋아졌어요 (우호도 +6)', 'party');
      }
    }
    if (tripDone || f.trip.closed) this.fest = null;
  }

  // ================================================================ 봉화
  beaconWatch() {
    const rv = this.g.rival, c = this.g.clock;
    const ours = this.w.blds.find((b) => b.type === 'beacon' && !b.ai && !b.dead && b.state === 'active');
    if (ours && !this.seen.ours) {
      this.seen.ours = true;
      if (!rv.lit) { this.plan.cheer = true; this.news('🏘️ 봉화 소식을 들은 서리골 사람들이 축하하러 온대요!', 'party'); }
    }
    if (rv.lit && !this.seen.rival) {
      this.seen.rival = true;
      if (!ours) this.rivalGift();
      else this.news('🔥 서리골도 봄의 봉화를 밝혔어요. 이제 두 마을 모두 봄이에요!', 'party');
    }
    if (this.plan.cheer && c.phase === PHASE.DAY && c.frac > 0.06 && c.frac < 0.55) { this.plan.cheer = false; this.startCheer(); }
  }
  /** 서리골이 먼저 밝혔을 때: 뽐내지 않고 봄맞이 선물을 보내요 */
  rivalGift() {
    const th = this.theirs;
    const food = (th.bread || 0) >= (th.fish || 0) ? 'bread' : 'fish';
    const n = clamp(Math.floor((th[food] || 0) * 0.5), 4, 8);
    th[food] = Math.max(0, (th[food] || 0) - n);
    this.theirCoins = Math.max(0, this.theirCoins - 25);
    this.news("💐 서리골이 '봄은 다 같이 맞아요!' 하며 봄맞이 선물을 보내요", 'love');
    this.startCaravan([{ type: food, n }, { type: 'coins', n: 25 }], null, 'gift');
    this.addFriend(3);
  }
  /** 우리가 먼저 밝혔을 때: 서리골 사람들이 봉화 앞에 와서 축하해요 */
  startCheer() {
    const b = this.w.blds.find((x) => x.type === 'beacon' && !x.ai && !x.dead && x.state === 'active');
    if (!b) return null;
    const ais = this.freeAI(4, this.theirDoor());
    if (!ais.length) { this.plan.cheer = true; return null; }
    const n = ais.length, r = Math.max(b.size[0], b.size[1]) / 2 + 1.6;
    const trip = this.newTrip('cheer', { hardEnd: this.T + 0.7, endAt: null });
    const grp = this.group();
    ais.forEach((p, k) => {
      const steps = [
        this.lab('gather', this.act((p) => this.badge(p, true))),
        this.lab('gather', this.go(() => this.lineUp(this.theirPlaza(), b, k, n, 0), 1.05)),
        this.sync(grp, 'dep'),
        this.stagger(grp, 'dep', k, ['봉화 보러 가요!'], 'emote_exclaim'),
        this.lab('walk', this.go(() => ring(b, k, n * 2, r, Math.PI / 2 - b.rot - (n - 1) * Math.PI / (2 * n)), this.even(1.2))),   // 봉화대 앞쪽 반원
        this.lab('arrive', this.act(() => { if (!trip.endAt) { trip.endAt = this.T + 0.1; this.addFriend(4); this.news('🎉 서리골 사람들이 우리 봉화를 축하하러 왔어요! "봄을 데려와 줘서 고마워요!" (우호도 +4)', 'party'); } })),
        this.lab('stay', this.until(() => this.T >= trip.endAt, (p, m) => { m.k = (m.k || 0) + 1; if (Math.random() < 0.35) this.talk(p, LINES.cheer, pick(['emote_heart', 'emote_music', 'emote_star'])); return ['happy', 'dance', 'wave', 'laugh'][m.k % 4]; }, 1.6, (p) => Math.atan2(b.x - p.x, b.z - p.z))),
        this.lab('bye', this.act((p) => { this.talk(p, LINES.bye, 'emote_star'); this.pp.wait(p, 1 + k * 0.9, 'wave'); })),
        this.lab('home', this.go((p) => this.homeSpotAI(p, k, n, 1.8), (p) => this.homeMul(p))),
        this.lab('home', this.act((p) => { this.badge(p, false); this.sleepIfNight(p); })),
      ];
      grp.list.push(this.addMember(trip, p, steps));
    });
    this.checkTrip(trip);
    return ais.map((p) => p.name);
  }

  // ================================================================ 이사 (우호도 80 이상)
  askMove(forced) {
    if (!this.ready() || this.moveAsk) return null;
    const adults = this.pp.list.filter((p) => p.ai && !p.dead && p.stage === 'adult');
    if (!forced && adults.length < 5) return null;
    const free = this.freeAI(99, this.theirDoor());
    const p = free.length ? pick(free) : null;
    if (!p) return null;
    this.moveAsk = { p, day: this.g.clock.day };
    this.lastMoveAsk = this.g.clock.day;
    this.news(`🏡 서리골의 ${ga(p.name)} 우리 마을로 이사 오고 싶대요 (🏘️ 서리골 버튼)`, 'love');
    this.queueModal(() => this.moveModal());
    return p.name;
  }
  answerMove(yes) {
    const a = this.moveAsk; this.moveAsk = null;
    if (!a) return null;
    const p = a.p;
    if (p.dead || !p.ai) return null;
    if (!yes) { this.news(`🙂 ${ga(p.name)} 서리골에 남기로 했어요. 그래도 마음 써 줘서 고맙대요`, 'info'); return 'no'; }
    for (const t of [...this.trips]) for (const m of [...t.members]) if (m.p === p && !m.done) this.endMember(m, true);
    p.ai = false; p.home = null; p.sleepAt = null;
    const trip = this.newTrip('move', { hardEnd: this.T + 1 });
    const steps = [
      this.lab('depart', this.act((p) => { this.talk(p, ['우리 마을로 이사 가요!'], 'emote_heart'); this.pp.wait(p, 1, 'wave'); })),
      this.lab('walk', this.go(() => ring(this.ourPlaza(), 0, 1, 1.2), 1.1)),
      this.lab('arrive', this.act((p) => {
        this.talk(p, LINES.move, 'emote_love'); this.pp.wait(p, 1.6, 'wave');
        this.pp.assignHomes();                            // 우리 마을 집 중에서만 골라요 (맨 위 덧씌움)
        this.news(`🏡 ${ga(p.name)} 우리 마을 주민이 되었어요! 모두 반갑게 맞아 줘요`, 'party');
      })),
    ];
    this.addMember(trip, p, steps);
    trip.onEnd = () => { if (!p.home) this.pp.assignHomes(); };     // 중간에 끊겼어도 우리 집을 정해 줘요
    this.addFriend(3);
    this.checkTrip(trip);
    return p.name;
  }

  // ================================================================ 팝업
  queueModal(fn) { this.modalQ.push(fn); this.modalPump(); }
  /** 답하지 않은 이주민 제안이 있는데 팝업이 안 보이면 다시 띄워요 (아니면 다음 이주민이 영영 안 와요) */
  reshowOffer() {
    const hud = this.g.hud, o = this.pp.offer;
    if (!hud || !o || hud.modalEl.style.display !== 'none') return;
    this.w.emit('offer', o);
  }
  modalPump() {
    const hud = this.g.hud; if (!hud || !this.modalQ.length) return;
    if (hud.modalEl.style.display !== 'none') return;     // 다른 팝업이 떠 있으면 기다려요
    this.modalQ.shift()();
  }
  inviteModal() {
    const iv = this.invite; if (!iv || iv.answer != null || !this.g.hud) return;
    this.g.hud.modal('<h2 data-invite="1" data-dask="1">💌 서리골의 잔치 초대</h2><div>오늘 오후, 두 마을 사이 들판에서 함께 춤추고 장을 보재요.<br><small>쉬고 있는 주민 몇 명이 다녀와요. 다녀오면 모두 기분이 좋아져요.</small></div>' +
      '<button data-y="1">🎉 갈래요</button><button class="gray" data-y="0">다음에</button>',
      (m, close) => { for (const b of m.querySelectorAll('button[data-y]')) b.onclick = () => { close(); this.answerInvite(b.dataset.y === '1'); }; });
  }
  moveModal() {
    const a = this.moveAsk; if (!a || !this.g.hud) return;
    if (a.p.dead || !a.p.ai) { this.moveAsk = null; return; }
    const p = a.p;
    this.g.hud.modal(`<h2 data-dask="1">🏡 이사 오고 싶대요</h2><div>서리골의 <b>${esc(ga(p.name))}</b> 우리 마을에서 살고 싶대요.<br><small>두 마을이 단짝이 되어서 생긴 일이에요. 받아 줄까요?</small></div>` +
      `<div class="ppl"><div><span style="font-size:40px">${p.gender === 'm' ? '🧑' : '👩'}</span><br>${esc(p.name)}<br>${p.age}세</div></div>` +
      '<button data-y="1">🤗 받기</button><button class="gray" data-y="0">거절</button>',
      (m, close) => { for (const b of m.querySelectorAll('button[data-y]')) b.onclick = () => { close(); this.answerMove(b.dataset.y === '1'); }; });
  }

  // ================================================================ 서리골 창 (위쪽 🏘️ 서리골 버튼)
  ensureButton() {
    const hud = this.g.hud;
    if (!hud || this.btn || !hud.addSysButton) return;
    this.btn = hud.addSysButton('🏘️ 서리골', '이웃 마을 서리골과 사이좋게 지내기 (교환·선물·초대)', () => this.openPanel());
    this.btn.style.display = 'none';
  }
  refreshUi() {
    if (!this.btn) return;
    const show = this.ready();
    if ((this.btn.style.display === 'none') === show) this.btn.style.display = show ? '' : 'none';
    const ping = !!(this.offer || (this.invite && this.invite.answer == null) || this.moveAsk);
    const label = ping ? '🏘️ 서리골 ❗' : '🏘️ 서리골';
    if (this.btn.textContent !== label) { this.btn.textContent = label; this.btn.style.background = ping ? '#ffe7a8' : ''; }
    this.refreshPanel(false);
  }
  openPanel() {
    const hud = this.g.hud; if (!hud) return;
    if (!this.ready()) { hud.toast('아직 이웃 마을이 없어요. 마을회관을 다 지으면 서리골이 생겨요'); return; }
    // 다른 팝업(이주민·상인 등)이 떠 있으면 덮어쓰지 않아요 (덮어쓰면 이주민 제안에 답할 수 없게 돼요).
    //  서리골 창이나 서리골의 초대·이사 팝업은 이 창에도 같은 버튼이 있으니 바꿔 띄워도 괜찮아요
    const m = hud.modalEl;
    if (m && m.style.display !== 'none' && !m.querySelector('[data-diplo],[data-dask]')) { hud.toast('먼저 떠 있는 창에 답하거나 닫아 주세요', true); return; }
    this.panelOpen = true;
    if (hud.toastEl) hud.toastEl.style.opacity = 0;      // 떠 있던 알림이 창 아래에 겹치지 않게
    this.panelH = this.panelHtml();
    hud.modal(this.panelH, (m) => this.bindPanel(m));
  }
  bindPanel(m) {
    const hud = this.g.hud;
    const x = m.querySelector('[data-x]'); if (x) x.onclick = () => { this.panelOpen = false; m.style.display = 'none'; this.reshowOffer(); this.modalPump(); };
    for (const b of m.querySelectorAll('button[data-dp]')) b.onclick = () => {
      const r = this.panelAct(b.dataset.dp, +b.dataset.i);
      if (r && r.msg) this.panelMsg = { text: r.msg, err: !!r.err, until: performance.now() + 4500 };   // 결과는 창 안에 보여요 (알림이 창에 가리지 않게)
      if (this.g.audio) this.g.audio.play(r && r.err ? 'error' : 'click', 0.5);
      this.refreshPanel(true);
    };
  }
  panelAct(a, i) {
    if (a === 'accept') return this.acceptTrade();
    if (a === 'decline') return this.declineTrade();
    if (a === 'deal') return this.doDeal(i);
    if (a === 'gift') return this.gift(i === 1 ? 'coins' : 'food');
    if (a === 'outing') {
      const c = this.g.clock;
      if (c.phase !== PHASE.DAY || c.frac > this.outingLatest()) return { err: true, msg: `지금 가면 밤이 되기 전에 못 돌아와요. 내일 ${timeTxt(this.outingLatest())} 전에 보내 주세요` };
      if (this.trips.some((t) => t.kind === 'outing')) return { err: true, msg: '벌써 서리골에 놀러 간 주민이 있어요' };
      const r = this.startOuting(false, true);
      if (!r) return { err: true, msg: '쉬고 있는 주민이 없어요' };
      return { msg: `${ga(r.join(', '))} 서리골로 마실을 가요` };
    }
    if (a === 'invite') { const r = this.answerInvite(i === 1); return { msg: r === 'no' ? '다음에 가기로 했어요' : '잔치에 가기로 했어요!' }; }
    if (a === 'move') { const r = this.answerMove(i === 1); return { msg: r === 'no' || !r ? '알겠어요' : '새 주민을 맞았어요!' }; }
    return null;
  }
  refreshPanel(force) {
    if (!this.panelOpen || !this.g.hud) return;
    const m = this.g.hud.modalEl;
    if (m.style.display === 'none' || !m.querySelector('[data-diplo]')) { this.panelOpen = false; return; }
    const html = this.panelHtml();
    if (!force && html === this.panelH) return;
    const sc = m.querySelector('[data-scroll]'), top = sc ? sc.scrollTop : 0;
    this.panelH = html; m.innerHTML = html;
    const sc2 = m.querySelector('[data-scroll]'); if (sc2) sc2.scrollTop = top;
    this.bindPanel(m);
  }
  panelHtml() {
    const g = this.g, rv = g.rival, f = Math.round(this.friend);
    const aiN = this.pp.list.filter((p) => p.ai && !p.dead).length;
    const bN = this.w.blds.filter((b) => b.ai && !b.dead).length;
    const ourB = this.w.blds.find((b) => b.type === 'beacon' && !b.ai && !b.dead);
    const ourTxt = ourB ? (ourB.state === 'active' ? '🔥 밝혔어요' : `짓는 중 ${Math.round((ourB.con ? ourB.con.work / ourB.con.workNeeded : 0) * 100)}%`) : '아직 안 지었어요';
    const bar = (pct, col) => `<div class="bar2" style="height:10px"><i style="width:${clamp(pct, 0, 100)}%;background:${col}"></i></div>`;
    const sec = (title, body) => `<div style="margin-top:8px;padding:8px 10px;background:#f4f7fb;border-radius:12px"><div style="font-weight:900;font-size:13.5px;margin-bottom:4px">${title}</div>${body}</div>`;
    const btn = (act, label, i, gray, dis) => `<button data-dp="${act}"${i != null ? ` data-i="${i}"` : ''}${gray ? ' class="gray"' : ''}${dis ? ' disabled' : ''} style="padding:6px 11px;font-size:13px;margin:3px 4px 0 0;${dis ? 'opacity:.45;cursor:default' : ''}">${label}</button>`;
    const small = (t) => `<div style="font-size:11.5px;color:#6a7487;margin-top:3px">${t}</div>`;
    let h = '<div data-diplo="1"><h2>🏘️ 이웃 마을 서리골</h2>';
    const pm = this.panelMsg && performance.now() < this.panelMsg.until ? this.panelMsg : null;
    h += `<div style="font-size:12.5px;color:#5d6b80;font-weight:700">눈 덮인 골짜기 마을 · 주민 ${aiN}명 · 건물 ${bN}채</div>`;
    if (pm) h += `<div data-msg="1" style="margin-top:6px;padding:6px 10px;border-radius:10px;font-weight:800;font-size:13px;background:${pm.err ? '#ffe3df;color:#b03a2e' : '#e3f6e3;color:#2f7d3a'}">${pm.err ? '⚠️ ' : '✅ '}${esc(pm.text)}</div>`;
    h += '<div data-scroll="1" style="max-height:min(58vh,500px);overflow-y:auto;text-align:left;font-size:13px;margin-top:6px">';
    // 우호도
    h += sec('💛 우호도', `<div style="display:flex;justify-content:space-between;font-weight:800"><span>${friendName(f)}</span><span>${f} / 100</span></div>${bar(f, f >= 60 ? '#f29fb5' : '#6fc36f')}` +
      small('교환·선물·마실·잔치로 올라가요. 60이 넘으면 함께 잔치, 80이 넘으면 이사 오고 싶어 하는 주민도 있어요'));
    // 봉화
    h += sec('🏮 봄의 봉화', `<div style="display:flex;justify-content:space-between"><span>서리골</span><b>${rv.lit ? '🔥 밝혔어요' : Math.round(rv.beacon * 100) + '%'}</b></div>${bar(rv.beacon * 100, '#6f9ee8')}` +
      `<div style="display:flex;justify-content:space-between;margin-top:4px"><span>우리 마을</span><b>${ourTxt}</b></div>`);
    // 서리골의 제안
    const o = this.offer;
    const moving = this.trips.filter((t) => t.kind === 'caravan').reduce((a, t) => a + t.members.filter((m) => !m.done).length, 0);
    let ob = '';
    if (o) {
      const have = this.have(o.want.type), ok = have >= o.want.n;
      ob += `<div>서리골이 주는 것: <b>${esc(itxt(o.give.type, o.give.n))}</b></div><div>서리골이 원하는 것: <b>${esc(itxt(o.want.type, o.want.n))}</b> <span style="color:${ok ? '#3a9a4a' : '#c43e30'};font-size:12px">(우리 창고 ${have}개)</span></div>`;
      ob += btn('accept', '🤝 받아들이기', null, false, !ok) + btn('decline', '거절', null, true);
      ob += small('내일 아침까지 기다려 줘요. 받아들이면 짐꾼이 직접 물건을 들고 와요');
    } else ob += '<div style="color:#5d6b80">지금은 제안이 없어요. 하루이틀마다 아침에 찾아와요</div>';
    if (moving) ob += `<div style="margin-top:4px;color:#3d6fb8;font-weight:800">🚶 짐꾼 ${moving}명이 오가는 중이에요</div>`;
    if (this.pending.length) ob += `<div style="margin-top:4px;color:#3d6fb8;font-weight:800">🌙 내일 아침에 떠날 짐꾼 행렬 ${this.pending.length}개</div>`;
    h += sec('🤝 서리골의 교환 제안', ob);
    // 우리가 먼저 하자고 하기
    const left = MAX_DEALS - this.dealsToday;
    let db = '';
    this.deals().forEach((d, i) => {
      const ok = this.have(d.give) >= d.gn && (this.theirs[d.get] || 0) >= d.n && left > 0;
      db += `<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;padding:3px 0;border-bottom:1px solid #e6ebf2"><span>${esc(itxt(d.give, d.gn))} → <b>${esc(itxt(d.get, d.n))}</b></span>${btn('deal', '바꾸기', i, false, !ok)}</div>`;
    });
    db += small(`오늘 남은 횟수 ${Math.max(0, left)}번 · 우호도가 높을수록 더 많이 줘요`);
    h += sec('🔁 우리가 먼저 바꾸자고 하기', db);
    // 선물·마실
    const giftLeft = Math.max(0, MAX_GIFTS - this.giftsToday), late = g.clock.phase !== PHASE.DAY || g.clock.frac > this.outingLatest();
    h += sec('🎁 선물과 마실', btn('gift', '🍞 먹을거리 5개 선물', 0, false, !giftLeft) + btn('gift', '🪙 코인 20 선물', 1, false, !giftLeft) + btn('outing', '🚶 우리 주민 마실 보내기', null, true, late) +
      small(`선물은 우리 주민이 직접 들고 가요. 하루 ${MAX_GIFTS}번까지 (오늘 남은 횟수 ${giftLeft}번)`) +
      small(`마실은 ${timeTxt(this.outingLatest())} 전에 보내야 밤이 되기 전에 돌아와요`));
    // 초대·이사
    if (this.invite && this.invite.answer == null) h += sec('💌 잔치 초대', '<div>오늘 오후 두 마을 사이 들판에서 함께 잔치를 열재요</div>' + btn('invite', '🎉 갈래요', 1) + btn('invite', '다음에', 0, true));
    else if (this.invite) h += sec('💌 잔치 초대', '<div>잔치에 가기로 했어요. 오후에 주민들이 들판으로 가요</div>');
    if (this.fest && !this.fest.cleaned) h += sec('🎪 잔치 중', `<div>우리 마을 ${this.fest.names.ours.length}명, 서리골 ${this.fest.names.ais.length}명이 함께 놀아요</div>`);
    if (this.moveAsk) h += sec('🏡 이사 오고 싶대요', `<div>서리골의 <b>${esc(ga(this.moveAsk.p.name))}</b> 우리 마을에서 살고 싶대요</div>` + btn('move', '🤗 받기', 1) + btn('move', '거절', 0, true));
    // 최근 일
    if (this.log.length) h += sec('📜 최근 일', this.log.slice(0, 5).map((l) => `<div style="font-size:12px;padding:1px 0">${l.day}일 · ${esc(l.text)}</div>`).join(''));
    h += '</div><button class="gray" data-x="1" style="margin-top:10px">닫기</button></div>';
    return h;
  }

  // ================================================================ 매 순간 / 아침
  update(dt) {
    this.ensureButton();
    if (!this.ready()) { if (this.btn && this.btn.style.display !== 'none') this.btn.style.display = 'none'; return; }
    if (this.fest) this.festFx(dt);
    this.tk += dt;
    if (this.tk < 0.4) return;
    this.tk = 0;
    if (!this.seen.intro) { this.seen.intro = true; this.news('🏘️ 이웃 마을 서리골과 사이좋게 지내 봐요! 위쪽 🏘️ 서리골 버튼으로 교환·선물을 할 수 있어요', 'info'); }
    this.housekeep();
    this.schedule();
    this.beaconWatch();
    this.modalPump();
    this.refreshUi();
  }
  /** 맡은 사람 점검: 사라졌거나, 다른 데서 데려갔거나, 너무 오래 걸리면 정리 */
  housekeep() {
    const T = this.T, list = this.pp.list;
    // 예전 저장에서 서리골 집을 받은 우리 주민이 있으면 바로 우리 마을 집으로 다시 정해요
    if (list.some((p) => p.home && (p.ai || p.home.ai))) this.pp.assignHomes();
    for (const t of [...this.trips]) {
      for (const m of [...t.members]) {
        if (m.done) continue;
        const p = m.p;
        if (p.dead || !list.includes(p) || p.ctrl !== m.fn || (t.hardEnd && T > t.hardEnd)) { this.endMember(m, true); continue; }
        const st = m.steps[m.i];
        if (!st || st.label !== 'stay' || p.chatting || !(p.q.length || p.cur)) continue;
        // 갈 때가 지났으면 하던 놀이(자리·걷기)를 끊고 인사하러 (마실은 지금 자리에서 집까지 거리로도 따져요)
        const roam = !t.forced && (t.kind === 'visit' || t.kind === 'outing') && this.mustGo(p, t.kind === 'visit' ? 'ours' : 'theirs');
        const late = roam || (t.leaveAt != null && (T > t.leaveAt + 0.012 || (!t.forced && this.g.clock.phase === PHASE.NIGHT)));
        if (late) { this.freeResv(m); if (p.slot) this.pp.leaveSlot(p); this.pp.clearQ(p); }
      }
      this.checkTrip(t);
    }
  }
  schedule() {
    const c = this.g.clock, f = c.frac, night = c.phase === PHASE.NIGHT;
    if (this.plan.visitAt != null && f >= this.plan.visitAt && !night) { this.plan.visitAt = null; this.startVisit(false); }
    if (this.plan.outAt != null && f >= this.plan.outAt && !night) { this.plan.outAt = null; this.startOuting(false); }
    const iv = this.invite;
    if (iv) {
      if (iv.day !== c.day) this.invite = null;            // 지난 초대
      else if (iv.answer !== false && !this.fest && c.phase === PHASE.DAY && f >= iv.startAt && f < 0.55) this.startFestival();
    }
    if (this.pending.length && c.phase === PHASE.DAY && f > 0.04 && f < 0.5) {
      // 우리 짐만 가는 행렬(선물)은 들고 갈 주민이 생길 때까지 기다려요 (오늘 안 되면 내일 아침에). 뒤에 선 교환 행렬은 먼저 떠나요
      const giftOnly = (pc) => pc.ours && !(pc.loads && pc.loads.length);
      const free = this.freeOurs(1, { jobs: true }).length > 0;
      const k = this.pending.findIndex((pc) => !giftOnly(pc) || free);
      if (k >= 0) { const [pc] = this.pending.splice(k, 1); this.startCaravan(pc.loads, pc.ours, pc.why); }
      else if (f > 0.4 && this.waitNewsDay !== c.day) { this.waitNewsDay = c.day; this.news('🎁 선물을 들고 갈 주민이 모두 바빠서 기다리고 있어요', 'info'); }
    }
  }
  morning() {
    if (!this.ready()) return;
    const c = this.g.clock;
    this.produce();
    this.dealsToday = 0; this.giftsToday = 0;
    // 밤사이 덜 끝난 마실·잔치는 정리 (짐꾼은 마저 가요)
    for (const t of [...this.trips]) if (t.kind !== 'caravan' && t.kind !== 'move') this.endTrip(t);
    if (this.fest) this.endFest(true);
    if (this.offer && c.day >= this.offer.until) { this.offer = null; this.news('👋 서리골 짐꾼이 답을 기다리다 돌아갔어요. 다음에 또 올게요', 'info'); }
    if (this.moveAsk && c.day - this.moveAsk.day >= 2) this.moveAsk = null;
    this.offerIn--;
    if (!this.offer && this.offerIn <= 0 && this.makeOffer(false)) this.offerIn = 1 + (Math.random() < 0.5 ? 1 : 0);
    // 오늘의 계획
    this.plan = { cheer: this.plan.cheer };
    if (this.friend >= 60 && c.day - this.lastInvite >= 3 && Math.random() < 0.4) this.makeInvite(false);
    else {
      const lead = this.walkDays(this.ourDoor(), this.theirDoor(), 1.15) + 0.04;     // 모이기 + 걸어가기
      if (Math.random() < 0.3 + this.friend / 250) this.plan.visitAt = clamp(ARRIVE - lead, 0.15, 0.4);
      else if (Math.random() < 0.25 + this.friend / 300) this.plan.outAt = clamp(ARRIVE - lead, 0.15, 0.4);
    }
    if (this.friend >= 80 && c.day - this.lastMoveAsk >= 3 && Math.random() < 0.3) this.askMove(false);
  }

  // ================================================================ 저장 (save.js 가 saveData/loadData 를 불러요)
  /** 아직 길 위에 있는 짐 (저장할 때: 불러오면 바로 받은 것으로 쳐요) */
  owed() {
    const us = [], them = [];
    for (const t of this.trips) {
      if (t.kind !== 'caravan') continue;
      for (const m of t.members) {
        if (m.done || m.settled) { if (m.back) them.push(m.backLoad); continue; }
        if (m.p.ai) for (const l of m.my || []) us.push(l);
        else if (m.ours) them.push(m.ours);
        if (m.back) them.push(m.backLoad);
      }
    }
    return { us: us.filter(Boolean), them: them.filter(Boolean) };
  }
  saveData() {
    const o = this.offer;
    return {
      friend: Math.round(this.friend * 10) / 10, theirs: Object.assign({}, this.theirs), theirCoins: this.theirCoins,
      offer: o ? { give: o.give, want: o.want, until: o.until, day: o.day } : null, offerIn: this.offerIn,
      lastInvite: this.lastInvite, lastMoveAsk: this.lastMoveAsk, seen: Object.assign({}, this.seen),
      pending: this.pending.slice(), log: this.log.slice(0, 20), dealsToday: this.dealsToday, giftsToday: this.giftsToday,
      plan: { cheer: !!this.plan.cheer }, owed: this.owed(),
    };
  }
  loadData(d) {
    if (!d || typeof d !== 'object') return;
    for (const t of [...this.trips]) this.endTrip(t);
    if (this.fest) this.endFest(true);
    this.friend = clamp(Number.isFinite(+d.friend) ? +d.friend : 30, 0, 100);
    if (d.theirs) this.theirs = Object.assign({}, d.theirs);
    if (Number.isFinite(+d.theirCoins)) this.theirCoins = +d.theirCoins;
    const ok = (l) => l && typeof l.type === 'string' && Number.isFinite(+l.n);
    this.offer = d.offer && ok(d.offer.give) && ok(d.offer.want) ? d.offer : null;
    this.offerIn = d.offerIn != null ? d.offerIn : 1;
    this.lastInvite = d.lastInvite != null ? d.lastInvite : -9; this.lastMoveAsk = d.lastMoveAsk != null ? d.lastMoveAsk : -9;
    if (d.seen) Object.assign(this.seen, d.seen);
    this.pending = Array.isArray(d.pending) ? d.pending.filter((p) => p && Array.isArray(p.loads)) : [];
    this.log = Array.isArray(d.log) ? d.log : [];
    this.dealsToday = d.dealsToday || 0; this.giftsToday = d.giftsToday || 0;
    this.invite = null; this.moveAsk = null; this.plan = { cheer: !!(d.plan && d.plan.cheer) };
    // 저장할 때 길 위에 있던 짐은 도착한 것으로
    if (d.owed) {
      for (const l of d.owed.us || []) if (ok(l)) { if (l.type === 'coins') this.g.econ.coins += l.n; else { this.w.stock[l.type] = (this.w.stock[l.type] || 0) + l.n; } }
      for (const l of d.owed.them || []) if (ok(l)) this.give(l);
      this.w.emit('stock');
    }
  }
  toJSON() { return this.saveData(); }
  fromJSON(d) { this.loadData(d); }

  // ================================================================ 자동 시험용
  api(obj) {
    this.ensureButton();
    const self = this;
    Object.assign(obj, {
      diploState() {
        const pp = self.pp, ai = pp.list.filter((p) => p.ai && !p.dead);
        return {
          friend: Math.round(self.friend), offer: self.offer ? self.offerText(self.offer) : null, theirs: Object.assign({}, self.theirs), theirCoins: self.theirCoins,
          trips: self.trips.map((t) => ({ kind: t.kind, why: t.why, members: t.members.map((m) => ({ n: m.p.name, ai: !!m.p.ai, i: m.i, of: m.steps.length, st: m.done ? 'done' : (m.steps[m.i] && m.steps[m.i].label) || '', done: m.done, x: +m.p.x.toFixed(1), z: +m.p.z.toFixed(1), hid: !!m.p.hidden, carry: m.p.carry || null, slot: m.p.slot ? m.p.slot.s.action : null, inside: m.p.inside ? m.p.inside.type : null, chat: !!m.p.chatting })) })),
          ctrl: pp.list.filter((p) => p.ctrl && !p.dead).map((p) => p.name),
          // 맡은 일이 끝났는데 p.ctrl 이 남은 사람 (있으면 안 됨)
          stray: pp.list.filter((p) => p.ctrl && !p.dead && !self.trips.some((t) => t.members.some((m) => m.fn === p.ctrl && !m.done))).map((p) => p.name),
          leaving: pp.list.filter((p) => p.leaving && !p.dead && !p.ai).map((p) => p.name),
          invite: self.invite ? { answer: self.invite.answer, startAt: self.invite.startAt } : null,
          fest: self.fest ? { at: self.fest.at, arrived: self.fest.arrived, endAt: +self.fest.endAt.toFixed(3), cleaned: !!self.fest.cleaned } : null,
          moveAsk: self.moveAsk ? self.moveAsk.p.name : null, pending: self.pending.length, plan: Object.assign({}, self.plan), dealsToday: self.dealsToday,
          ourDoor: self.ready() ? self.ourDoor() : null, theirDoor: self.ready() ? self.theirDoor() : null, meet: self.ready() && self.meetPlace() ? self.meetPlace().type : null,
          ai: { total: ai.length, asleep: ai.filter((p) => p.hidden && p.sleeping).length, visible: ai.filter((p) => !p.hidden).length,
            // 밤에 자러 집에 가는 중 (people.aiThink 의 '걸어가서 숨기' 줄이 남아 있음, 우리 기능이 맡지 않음)
            bedward: self.g.clock.phase === PHASE.NIGHT ? ai.filter((p) => !p.hidden && !p.ctrl && ((p.cur && p.cur.t === 'do') || p.q.some((x) => x.t === 'do'))).length : 0,
            // 깨어 있는데 우리 마을 쪽에 있는 서리골 사람 (밤에 있으면 안 돼요)
            inOurs: self.ready() ? ai.filter((p) => !p.hidden && dist(p, self.ourDoor()) < dist(p, self.theirDoor())).length : 0 },
          // 두 마을이 섞이면 안 되는 것: 서리골 집을 받은 우리 주민·집을 받은 서리골 사람, 다른 마을 사람에게 생긴 사랑·짝
          cross: {
            homes: pp.list.filter((p) => !p.dead && p.home && (p.ai || p.home.ai)).length,
            romance: pp.list.filter((p) => !p.dead && [...(p.romance || new Map()).entries()].some(([id, v]) => v > 0 && ai.some((q) => q.id === id) !== !!p.ai)).length,
            partners: pp.list.filter((p) => !p.dead && ((p.partner && !!p.partner.ai !== !!p.ai) || (p.spouse && !!p.spouse.ai !== !!p.ai))).length,
          },
          // 서리골 쪽에 있는 우리 주민 (밤에는 0 이어야 해요: 자기 마을에서 자요)
          oursAway: self.ready() ? pp.list.filter((p) => !p.ai && !p.dead && dist(p, self.ourDoor()) > dist(p, self.theirDoor())).map((p) => p.name) : [],
          gifts: self.giftsToday, outingLatest: self.ready() ? +self.outingLatest().toFixed(3) : null, phase: self.g.clock.phase,
          T: +self.T.toFixed(3), log: self.log.slice(0, 8).map((l) => l.text),
        };
      },
      forceTrade() { const o = self.makeOffer(true); return o ? self.offerText(o) : null; },
      acceptTrade() { return self.acceptTrade(); },
      declineTrade() { return self.declineTrade(); },
      forceVisit(kind = 'theirs') { return kind === 'ours' ? self.startOuting(true) : self.startVisit(true); },
      forceInvite() { if (self.fest) return null; self.invite = null; self.makeInvite(true); return self.answerInvite(true, true); },
      friendship(n) { if (typeof n === 'number') self.friend = clamp(n, 0, 100); return Math.round(self.friend); },
      diploDeal(i) { return self.doDeal(i); },
      diploGift(kind) { return self.gift(kind); },
      forceMoveAsk() { return self.askMove(true); },
      answerMove(yes) { const m = self.g.hud && self.g.hud.modalEl; if (m && m.querySelector('button[data-y]')) m.style.display = 'none'; return self.answerMove(yes); },
      forceCheer() { return self.startCheer(); },
      diploPanel(on = true) { if (on) self.openPanel(); else if (self.g.hud) { self.panelOpen = false; self.g.hud.modalEl.style.display = 'none'; } return self.panelOpen; },
      diploMorning() { self.morning(); return self.plan; },
    });
  }
}
