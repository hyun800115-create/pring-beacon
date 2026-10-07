// Iso / direction maths (CONTRACT §1, §9).
// The game world is screen-space 2D. Ground axes on screen:
//   +1 m along world X  = (+45.25, +22.63) px  (runs screen down-right)
//   +1 m along world Y  = (+45.25, -22.63) px  (runs screen up-right)

export const AX = { x: 45.25, y: 22.63 };   // world X axis on screen
export const AY = { x: 45.25, y: -22.63 };  // world Y axis on screen
export const PPU = 64;

// 8 screen directions, index = sector of atan2(vy*2, vx)
export const DIRS8 = ['E', 'SE', 'S', 'SW', 'W', 'NW', 'N', 'NE'];
// which rendered direction + flipX to use for each of the 8 directions
const BASE = { E: ['E', false], SE: ['SE', false], S: ['S', false], SW: ['SE', true], W: ['E', true], NW: ['NE', true], N: ['N', false], NE: ['NE', false] };
export const DIR_BASE = DIRS8.map((d) => BASE[d][0]);
export const DIR_FLIP = DIRS8.map((d) => BASE[d][1]);

/** direction index 0..7 from a screen velocity (vx, vy). */
export function dirFromVec(vx, vy) {
  const a = Math.atan2(vy * 2, vx);
  let s = Math.round(a / (Math.PI / 4));
  s = ((s % 8) + 8) % 8;
  return s;
}

/** screen point for a local (mx, my) metre offset from a centre */
export function isoPt(cx, cy, mx, my) {
  return { x: cx + AX.x * mx + AY.x * my, y: cy + AX.y * mx + AY.y * my };
}

/** inverse: screen offset (dx, dy) from a centre -> metres (mx, my) */
export function isoInv(dx, dy) {
  // dx = 45.25 (mx + my); dy = 22.63 (mx - my)
  const s = dx / AX.x, d = dy / AX.y;
  return { mx: (s + d) / 2, my: (s - d) / 2 };
}

/** the four corners (screen) of a w x h metre ground rectangle centred at (cx, cy), order: left, top, right, bottom */
export function isoRect(cx, cy, w, h) {
  const hw = w / 2, hh = h / 2;
  return [
    isoPt(cx, cy, -hw, -hh), // left
    isoPt(cx, cy, -hw, hh),  // top
    isoPt(cx, cy, hw, hh),   // right
    isoPt(cx, cy, hw, -hh),  // bottom
  ];
}

/** is screen point inside the w x h metre ground rectangle centred at (cx, cy) (with optional margin in metres) */
export function inIsoRect(px, py, cx, cy, w, h, margin = 0) {
  const m = isoInv(px - cx, py - cy);
  return Math.abs(m.mx) <= w / 2 - margin && Math.abs(m.my) <= h / 2 - margin;
}

/** "ground distance" between two screen points (y doubled so 2:1 ellipses become circles) */
export function gdist(ax, ay, bx, by) {
  const dx = ax - bx, dy = (ay - by) * 2;
  return Math.sqrt(dx * dx + dy * dy);
}

export function gdist2(ax, ay, bx, by) {
  const dx = ax - bx, dy = (ay - by) * 2;
  return dx * dx + dy * dy;
}

/** a direction index that faces from (ax, ay) toward (bx, by) */
export function dirTo(ax, ay, bx, by) {
  return dirFromVec(bx - ax, by - ay);
}
