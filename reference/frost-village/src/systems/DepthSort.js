// Draw-order layers. Everything standing on the ground uses depth = its anchor y (screen-space
// depth sort, CONTRACT §1); only dynamic objects update their depth every frame.

export const DEPTH = {
  WATER: -20000,
  FISH: -19900,
  WAVES: -19800,
  GROUND: -15000,
  FLOOR: -14000,
  GROUND_DECAL: -13500,
  OUTLINE: -13000,
  PAD: -12000,
  PAD_ITEM: -11900,
  PAD_TEXT: -11800,
  SHADOW: -11000,
  DUST: -10900,
  // world objects: 0 .. world height (their y)
  FLY: 30000,
  FX: 31000,
  BUBBLE: 40000,
  LABEL: 41000,
  ARROW: 45000,
  TOP: 50000,
};

/** keep a list of dynamic objects whose depth follows their y */
export class DepthSort {
  constructor() { this.list = []; }
  add(obj, offset = 0) { obj.__dOff = offset; this.list.push(obj); return obj; }
  remove(obj) { const i = this.list.indexOf(obj); if (i >= 0) this.list.splice(i, 1); }
  update() {
    const l = this.list;
    for (let i = 0; i < l.length; i++) {
      const o = l[i];
      const d = o.y + o.__dOff;
      if (o.depth !== d) o.setDepth(d);
    }
  }
}
