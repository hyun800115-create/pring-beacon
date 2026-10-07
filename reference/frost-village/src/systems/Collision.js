// Static obstacle collision in "ground space" (y doubled, so 2:1 footprint ellipses become circles).
// A uniform grid keeps queries cheap. Moving agents call resolve() after integrating velocity.

import { WORLD } from '../data/world.js';

const CELL = 160;

export class Collision {
  constructor(w, h) {
    this.w = w; this.h = h;
    this.cols = Math.ceil(w / CELL) + 1; this.rows = Math.ceil(h / CELL) + 1;
    this.grid = new Array(this.cols * this.rows);
    for (let i = 0; i < this.grid.length; i++) this.grid[i] = [];
    this.all = [];
    this._shoreCache = new Float32Array(Math.ceil(w / 8) + 2);
    for (let i = 0; i < this._shoreCache.length; i++) this._shoreCache[i] = shoreY(i * 8);
  }

  add(x, y, r, tag) {
    const o = { x, y, r, active: true, tag: tag || null };
    // insert into every cell the circle may touch (r in ground space; vertical extent r/2)
    const m = 26; // max agent radius
    const x0 = Math.max(0, Math.floor((x - r - m) / CELL)), x1 = Math.min(this.cols - 1, Math.floor((x + r + m) / CELL));
    const y0 = Math.max(0, Math.floor((y - (r + m) / 2) / CELL)), y1 = Math.min(this.rows - 1, Math.floor((y + (r + m) / 2) / CELL));
    for (let cy = y0; cy <= y1; cy++) for (let cx = x0; cx <= x1; cx++) this.grid[cy * this.cols + cx].push(o);
    this.all.push(o);
    return o;
  }

  /** true if a circle of radius `rad` at (x, y) overlaps an active obstacle or leaves the walkable area */
  blocked(x, y, rad, ignore) {
    if (x < 40 || x > this.w - 40 || y > this.h - 40 || y < this.shore(x) + 46) return true;
    const cx = Math.floor(x / CELL), cy = Math.floor(y / CELL);
    if (cx < 0 || cy < 0 || cx >= this.cols || cy >= this.rows) return true;
    const cell = this.grid[cy * this.cols + cx];
    for (let i = 0; i < cell.length; i++) {
      const o = cell[i];
      if (!o.active || o === ignore) continue;
      const dx = x - o.x, dy = (y - o.y) * 2, R = o.r + rad;
      if (dx * dx + dy * dy < R * R) return true;
    }
    return false;
  }

  shore(x) {
    const i = Math.max(0, Math.min(this._shoreCache.length - 2, Math.floor(x / 8)));
    const f = x / 8 - i;
    return this._shoreCache[i] * (1 - f) + this._shoreCache[i + 1] * f;
  }

  /** push a circle of radius `rad` at (p.x, p.y) out of obstacles; mutates p; returns true if it hit something */
  resolve(p, rad) {
    let hit = false;
    const cx = Math.floor(p.x / CELL), cy = Math.floor(p.y / CELL);
    if (cx >= 0 && cy >= 0 && cx < this.cols && cy < this.rows) {
      const cell = this.grid[cy * this.cols + cx];
      for (let i = 0; i < cell.length; i++) {
        const o = cell[i];
        if (!o.active) continue;
        const dx = p.x - o.x, dy = (p.y - o.y) * 2;
        const R = o.r + rad;
        const d2 = dx * dx + dy * dy;
        if (d2 >= R * R) continue;
        const d = Math.sqrt(d2) || 0.001;
        const push = (R - d) / d;
        p.x += dx * push; p.y += (dy * push) / 2;
        hit = true;
      }
    }
    // world bounds + shoreline
    const minY = this.shore(p.x) + 46;
    if (p.y < minY) { p.y = minY; hit = true; }
    if (p.x < 40) { p.x = 40; hit = true; } else if (p.x > this.w - 40) { p.x = this.w - 40; hit = true; }
    if (p.y > this.h - 40) { p.y = this.h - 40; hit = true; }
    return hit;
  }
}

export function shoreY(x) {
  const s = WORLD.shore;
  let y = s.base;
  for (const [a, f, ph] of s.waves) y += a * Math.sin(x * f + ph);
  return y;
}
