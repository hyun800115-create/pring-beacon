// 시간: 하루(낮·저녁·밤)와 계절, 해.
//  하루 비율 0~0.62 낮(일하는 시간), 0.62~0.76 저녁(쉬는 시간: 수다·산책), 0.76~1 밤(잠)

import { NUM, SEASONS } from '../data/defs.js';

export const PHASE = { DAY: 'day', EVENING: 'evening', NIGHT: 'night' };

export class Clock {
  constructor() {
    this.t = 0.08;      // 아침 조금 지난 때부터
    this.day = 1;       // 1일차부터
    this.listeners = [];
  }
  on(fn) { this.listeners.push(fn); }
  get frac() { return this.t; }
  get phase() { return this.t < 0.62 ? PHASE.DAY : this.t < 0.76 ? PHASE.EVENING : PHASE.NIGHT; }
  get seasonIndex() { return Math.floor((this.day - 1) / NUM.daysPerSeason) % 4; }
  get season() { return SEASONS[this.seasonIndex]; }
  get year() { return 1 + Math.floor((this.day - 1) / (NUM.daysPerSeason * 4)); }
  get dayOfSeason() { return ((this.day - 1) % NUM.daysPerSeason) + 1; }
  /** 시계 글자 (예: 오전 9시) */
  get timeText() {
    const h = (6 + this.t * 24) % 24;
    const hh = Math.floor(h);
    return (hh < 12 ? '오전 ' : '오후 ') + (hh % 12 === 0 ? 12 : hh % 12) + '시';
  }

  update(dt) {
    const before = this.phase;
    this.t += dt / NUM.dayLength;
    if (this.t >= 1) {
      this.t -= 1;
      this.day++;
      for (const f of this.listeners) f('morning');
      if ((this.day - 1) % NUM.daysPerSeason === 0) for (const f of this.listeners) f('season');
    }
    const after = this.phase;
    if (before !== after) for (const f of this.listeners) f(after);
  }

  /** 하늘 색 덧씌우기 (CSS 색, 곱하기 혼합) */
  skyColor() {
    const t = this.t;
    // 새벽(0~0.06) 밝아짐, 낮, 노을(0.58~0.7), 밤(0.76~0.95), 새벽(0.95~1)
    const key = [
      [0.00, [255, 214, 196, 0.25]],
      [0.07, [255, 255, 255, 0.0]],
      [0.55, [255, 255, 255, 0.0]],
      [0.66, [255, 170, 110, 0.32]],
      [0.76, [70, 80, 170, 0.55]],
      [0.94, [60, 70, 160, 0.58]],
      [1.00, [255, 214, 196, 0.25]],
    ];
    let a = key[0], b = key[key.length - 1];
    for (let k = 0; k < key.length - 1; k++) if (t >= key[k][0] && t <= key[k + 1][0]) { a = key[k]; b = key[k + 1]; break; }
    const u = (t - a[0]) / Math.max(1e-6, b[0] - a[0]);
    const c = a[1].map((v, k) => v + (b[1][k] - v) * u);
    return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${c[3].toFixed(3)})`;
  }
  /** 밤인 정도 0~1 (창문 불빛 등) */
  get darkness() {
    const t = this.t;
    if (t < 0.06) return 1 - t / 0.06;
    if (t < 0.6) return 0;
    if (t < 0.76) return (t - 0.6) / 0.16;
    return 1;
  }
}
