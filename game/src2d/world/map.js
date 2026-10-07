// 지도: 칸마다 무엇이 있는지(나무, 바위, 깃발, 길, 건물, 밭)와 길 찾기(A*).

export class Rng {
  constructor(seed) { this.s = seed >>> 0 || 1; }
  next() { let x = this.s; x ^= x << 13; x ^= x >>> 17; x ^= x << 5; this.s = x >>> 0; return this.s / 4294967296; }
  range(a, b) { return a + (b - a) * this.next(); }
  int(a, b) { return Math.floor(this.range(a, b + 1)); }
}

export class GridMap {
  constructor(n) {
    this.n = n;
    this.occ = new Array(n * n).fill(null);   // {type:'flag'|'road'|'bld'|'plot', ref}
    this.obj = new Array(n * n).fill(null);   // 자연물 {type:'tree'|'rock'|'stump'|'bush', sprite, ...}
  }
  inb(i, j) { return i >= 0 && j >= 0 && i < this.n && j < this.n; }
  idx(i, j) { return j * this.n + i; }
  occAt(i, j) { return this.inb(i, j) ? this.occ[this.idx(i, j)] : { type: 'edge' }; }
  objAt(i, j) { return this.inb(i, j) ? this.obj[this.idx(i, j)] : null; }
  setOcc(i, j, v) { if (this.inb(i, j)) this.occ[this.idx(i, j)] = v; }
  setObj(i, j, v) { if (this.inb(i, j)) this.obj[this.idx(i, j)] = v; }
  /** 아무것도 없는 칸 (덤불은 지나가도 됨: 길을 깔면 치워진다) */
  isFree(i, j, allowBush = true) {
    if (!this.inb(i, j) || this.occ[this.idx(i, j)]) return false;
    const o = this.obj[this.idx(i, j)];
    return !o || (allowBush && o.type === 'bush');
  }
  /** 주변 8칸에 깃발이 있나 */
  flagNear(i, j, except) {
    for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
      if (!di && !dj) continue;
      const o = this.occAt(i + di, j + dj);
      if (o && o.type === 'flag' && o.ref !== except) return true;
    }
    return false;
  }

  /**
   * 길 경로 찾기 (상하좌우 4방향). 시작은 깃발, 끝은 빈 칸이나 깃발(또는 길 위 = 새 깃발 자리).
   * 반환: [[i,j],...] 또는 null
   */
  findRoad(si, sj, ei, ej, maxLen) {
    if (si === ei && sj === ej) return null;
    const n = this.n, start = this.idx(si, sj), goal = this.idx(ei, ej);
    const endOcc = this.occAt(ei, ej);
    const endOk = this.isFree(ei, ej) || (endOcc && (endOcc.type === 'flag' || endOcc.type === 'road'));
    if (!endOk) return null;
    const g = new Map([[start, 0]]), came = new Map();
    const open = [[Math.abs(ei - si) + Math.abs(ej - sj), start]];
    const closed = new Set();
    while (open.length) {
      let bi = 0;
      for (let k = 1; k < open.length; k++) if (open[k][0] < open[bi][0]) bi = k;
      const cur = open[bi][1]; open[bi] = open[open.length - 1]; open.pop();
      if (cur === goal) {
        const out = [];
        for (let c = cur; c !== undefined; c = came.get(c)) out.push([c % n, Math.floor(c / n)]);
        return out.reverse();
      }
      if (closed.has(cur)) continue;
      closed.add(cur);
      const ci = cur % n, cj = Math.floor(cur / n), cg = g.get(cur);
      if (cg >= maxLen) continue;
      for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const ni = ci + di, nj = cj + dj;
        if (!this.inb(ni, nj)) continue;
        const ni2 = this.idx(ni, nj);
        if (ni2 !== goal && !this.isFree(ni, nj)) continue;
        const ng = cg + 1;
        if (ng < (g.has(ni2) ? g.get(ni2) : Infinity)) {
          g.set(ni2, ng); came.set(ni2, cur);
          open.push([ng + Math.abs(ei - ni) + Math.abs(ej - nj), ni2]);
        }
      }
      if (closed.size > 6000) break;
    }
    return null;
  }
}
