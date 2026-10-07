// 칸(타일) ↔ 화면 좌표. 서리마을과 같은 투영(고도 30°, 방위 45°, 1m = 64px)을 쓴다.
//   세계 X축 1m = 화면 (+45.25, +22.63)px (오른쪽 아래), 세계 Y축 1m = 화면 (+45.25, -22.63)px (오른쪽 위)
// 한 칸 = 1.5m (밀밭 한 판 크기와 같음).

export const PPU = 64;
export const TILE_M = 1.5;
export const TX = 45.25 * TILE_M;   // 칸 i 가 1 늘 때 화면 x 증가량 (j 도 같음)
export const TY = 22.63 * TILE_M;   // 칸 i 가 1 늘 때 화면 y 증가량 (j 는 반대로 감소)

export class Iso {
  constructor(n) {
    this.n = n;
    this.ox = TX * 2;
    this.oy = TY * (n + 1);
    this.width = this.ox * 2 + TX * 2 * (n - 1);
    this.height = TY * 2 * (n + 1);
  }

  /** 칸 중심(소수 가능)의 화면 좌표 */
  toWorld(i, j) {
    return { x: this.ox + TX * (i + j), y: this.oy + TY * (i - j) };
  }

  /** 화면 좌표 → 칸 좌표(소수) */
  toTileF(x, y) {
    const s = (x - this.ox) / TX, d = (y - this.oy) / TY;
    return { i: (s + d) / 2, j: (s - d) / 2 };
  }

  /** 화면 좌표 → 가장 가까운 칸 */
  toTile(x, y) {
    const t = this.toTileF(x, y);
    return { i: Math.round(t.i), j: Math.round(t.j) };
  }

  /** 칸 하나의 마름모 네 꼭짓점 (왼쪽, 위, 오른쪽, 아래) */
  diamond(i, j, grow = 0) {
    const h = 0.5 + grow;
    return [this.toWorld(i - h, j - h), this.toWorld(i - h, j + h), this.toWorld(i + h, j + h), this.toWorld(i + h, j - h)];
  }
}

// 8방향: 0=E 1=SE 2=S 3=SW 4=W 5=NW 6=N 7=NE. 렌더된 5방향 + 좌우 반전.
export const DIRS8 = ['E', 'SE', 'S', 'SW', 'W', 'NW', 'N', 'NE'];
const BASE = { E: ['E', false], SE: ['SE', false], S: ['S', false], SW: ['SE', true], W: ['E', true], NW: ['NE', true], N: ['N', false], NE: ['NE', false] };
export const DIR_BASE = DIRS8.map((d) => BASE[d][0]);
export const DIR_FLIP = DIRS8.map((d) => BASE[d][1]);

/** 화면 속도 → 방향 번호 */
export function dirFromVec(vx, vy) {
  const a = Math.atan2(vy * 2, vx);
  let s = Math.round(a / (Math.PI / 4));
  return ((s % 8) + 8) % 8;
}
