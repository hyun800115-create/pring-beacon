"""
b3d_kit.py - shared helpers for the 3D building / furniture generators of
"봄날의 행진" (docs/CONTRACT3D.md).

  * palette + flat Principled materials only (no procedural textures)
  * group tagging (roof / walls / iwalls / floor / interior / exterior / anim_*)
  * a transform stack so furniture builders model in a local frame (front -Y)
    and get placed with  `with xf((x, y), rot):`
  * slots / fx / door empties, rooms
  * building parts: log walls with openings, plank partition walls, plank floors,
    gable roofs with snow, chimneys, windows, doors
  * finalize(): merges every group into one mesh per node, builds walls_low /
    iwalls_low (cut at FZ + 0.5 m with capped section), writes GLB + JSON.

Deterministic: every random choice goes through rnd(seed).
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector, Matrix, Euler  # noqa: E402

import bl_common as bc  # noqa: E402
import prop_lib as L  # noqa: E402

GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT_B = os.path.join(GAME, 'assets3d', 'buildings')
OUT_F = os.path.join(GAME, 'assets3d', 'furniture')

FZ = 0.12          # floor top height (feet of residents indoors)
LOW_CUT = 0.5      # walls_low height above the floor

# --------------------------------------------------------------------------- palette
P = {
    # woods
    'wood_l': '#C98F55', 'wood_m': '#AE7444', 'wood_d': '#8A5A33', 'wood_dd': '#5E3A22', 'bark': '#6E4428',
    'plank': '#D39A5E', 'plank2': '#C78A50', 'plank3': '#B97C48', 'pale': '#E2BC86', 'pale2': '#D6AD76',
    'log1': '#B5763F', 'log2': '#A86A36', 'log3': '#C08049', 'end': '#E9C690',
    # roofs
    'roof_r1': '#8C4632', 'roof_r2': '#7A3F2E', 'roof_b1': '#4A6C98', 'roof_b2': '#3F5F8A',
    'roof_g1': '#4F7F56', 'roof_g2': '#436E4A', 'roof_t1': '#9A6A3E', 'roof_t2': '#87592F',
    # stone / metal
    'stone': '#8E96A3', 'stone_d': '#727A87', 'stone_l': '#A9B0BB', 'stone_w': '#9A8F86',
    'iron': '#474D58', 'iron_l': '#6B7380', 'gold': '#F2C14E', 'copper': '#C87533', 'steel': '#B3BECB',
    'brick': '#B4593F', 'brick_d': '#94442F', 'mortar': '#D9CFC2', 'charcoal': '#2E2724',
    # cloth / colour
    'snow': '#F4F7FB', 'cream': '#FFF8EC', 'canvas': '#EFE1C4', 'white': '#F2F0EA',
    'red': '#D9483B', 'red_d': '#B23A30', 'blue': '#3D7CC9', 'blue_l': '#7FB2E5', 'navy': '#2F4E7A',
    'green': '#5CA76A', 'leaf': '#3E7F55', 'leaf_l': '#6BAF5E', 'yellow': '#F2C230', 'orange': '#E8893A',
    'pink': '#F29BB0', 'purple': '#9A6FC0', 'teal': '#3FA39A', 'mustard': '#D9A93A', 'rose': '#D96C7E',
    'straw': '#E2B85A', 'straw_d': '#C49A3E', 'wheat': '#E8C25A', 'bread': '#C9853F', 'bread_d': '#A86A2E',
    'flour': '#F3EBDD', 'sack': '#D8C49A', 'soil': '#6A4632', 'water': '#4C8FCB', 'ceramic': '#F5F2EC',
    'terracotta': '#C76B43', 'leather': '#8B5A35', 'rope': '#D9C39A', 'paper': '#FBF5E6',
    'ink': '#2B2F3A', 'book_r': '#B8443A', 'book_b': '#3F6FB0', 'book_g': '#4F8F5A', 'book_y': '#D9A93A',
}
EMIT = {   # name: (base, emission colour, strength)
    'glow': ('#FFD27A', '#FFC060', 2.4),        # windows
    'lamp': ('#FFE2A0', '#FFD27A', 3.0),        # lamp shades / lanterns
    'fire': ('#FF8A2A', '#FF8A2A', 4.0),
    'ember': ('#FFD45A', '#FFB030', 3.0),
}
_MATS = {}


def col(c):
    return P.get(c, c)


# near-duplicate palette entries folded together so a building stays under 30 materials
HARD = {
    'plank3': 'log1', 'plank2': 'log3', 'wood_l': 'plank', 'wood_m': 'log2', 'bark': 'wood_d', 'pale': 'end',
    'stone_w': 'stone', 'iron_l': 'stone_d', 'steel': 'stone_l', 'charcoal': 'iron', 'ink': 'iron',
    'white': 'cream', 'ceramic': 'cream', 'paper': 'cream', 'flour': 'cream', 'mortar': 'canvas', 'rope': 'sack',
    'brick_d': 'red_d', 'book_r': 'red', 'terracotta': 'brick', 'book_b': 'blue', 'water': 'blue_l',
    'book_g': 'green', 'book_y': 'mustard', 'wheat': 'straw', 'gold': 'yellow', 'copper': 'orange',
    'bread_d': 'bread', 'soil': 'wood_dd', 'leather': 'wood_d', 'straw_d': 'mustard', 'pale2': 'end',
}


def M(c, rough=0.75, metal=0.0):
    """Flat Principled material from a palette name or hex (cached)."""
    c = HARD.get(c, c)
    if c in EMIT:
        key = ('E', c)
        if key not in _MATS:
            b, e, s = EMIT[c]
            _MATS[key] = bc.mat('e_' + c, L.adj(b), rough=0.5, emission=e, emission_strength=s)
        return _MATS[key]
    key = (c, metal)
    if key not in _MATS:
        hx = col(c)
        base = hx if c in ('snow',) else L.adj(hx)
        nm = c if c in P else 'c' + hx.lstrip('#')
        if metal:
            nm += '_met'
        _MATS[key] = bc.mat(nm, base, rough=rough, metal=metal)
    return _MATS[key]


def rnd(seed):
    return random.Random(seed)


# --------------------------------------------------------------------------- state
class State:
    def __init__(self):
        self.grp = ['interior']
        self.xf = [Matrix.Identity(4)]
        self.room = ['']
        self.slots = []        # dict(action, room, pos(Vector), yaw)
        self.fx = []           # (kind, pos)
        self.rooms = []
        self.door = None
        self.anim_origin = {}
        self.low_cap = {'walls': 'end', 'iwalls': 'pale2'}
        self.wall_cut = []     # extra info
        self.extra = {}        # extra JSON sidecar fields (pen, trees, ...)
        self.n = 0


S = State()


def reset():
    global S
    bc.reset_scene()
    _MATS.clear()
    L._CUSTOM.clear()
    S = State()
    return S


class _Ctx:
    def __init__(self, enter, leave):
        self.enter, self.leave = enter, leave

    def __enter__(self):
        self.enter()
        return self

    def __exit__(self, *a):
        self.leave()
        return False


def grp(name):
    return _Ctx(lambda: S.grp.append(name), lambda: S.grp.pop())


def room(name):
    return _Ctx(lambda: S.room.append(name), lambda: S.room.pop())


def xf(loc=(0, 0, 0), rot=0.0, scale=1.0):
    """Push a local frame: translate to loc (x, y[, z]) and rotate rot degrees about Z."""
    loc = tuple(loc) + (0.0,) * (3 - len(loc))
    m = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(math.radians(rot), 4, 'Z') @ Matrix.Scale(scale, 4)
    return _Ctx(lambda: S.xf.append(S.xf[-1] @ m), lambda: S.xf.pop())


def cur_yaw():
    return math.degrees(S.xf[-1].to_euler().z)


def reg(o):
    """Tag a freshly made object with the current group and put it in the current frame."""
    if o.parent is None:
        o.matrix_basis = S.xf[-1] @ o.matrix_basis
    o['grp'] = S.grp[-1]
    S.n += 1
    return o


def W(p):
    """Local point -> world point."""
    p = tuple(p) + (0.0,) * (3 - len(p))
    return S.xf[-1] @ Vector(p)


# --------------------------------------------------------------------------- primitives
def bx(size, loc=(0, 0, 0), c='wood_l', rot=(0, 0, 0), bev=0.03, seg=1, origin='bottom', taper=None, rough=0.75,
       mat=None):
    loc = tuple(loc) + (0.0,) * (3 - len(loc))
    if min(size) < 0.065 or (size[0] * size[1] * size[2] < 0.0012):
        bev = 0.0                      # tiny parts: plain boxes keep the triangle budget down
    o = L.box('b', tuple(size), loc, rot=rot, mat=mat or M(c, rough), bevel=bev, segs=seg, origin=origin,
              taper=taper)
    if bev <= 0.0015:
        o.modifiers.clear()
    return reg(o)


def cy(r, h, loc=(0, 0, 0), c='wood_l', rot=(0, 0, 0), segs=12, bev=0.015, bseg=1, r_top=None, cap=None,
       origin='bottom', scale=(1, 1, 1), smooth=True, mat=None):
    loc = tuple(loc) + (0.0,) * (3 - len(loc))
    if r < 0.05:
        segs = min(segs, 6)
        bev = 0.0
    elif r < 0.12:
        segs = min(segs, 10)
    o = L.cyl('c', r, h, loc, rot=rot, mat=mat or M(c), segs=segs, r_top=r_top, bevel=bev, bsegs=bseg,
              cap_mat=M(cap) if cap else None, origin=origin, scale=scale, smooth=smooth)
    if bev <= 0.0015:
        o.modifiers.clear()
    return reg(o)


def sp(r, loc=(0, 0, 0), c='red', scale=(1, 1, 1), segs=12, rings=7, rot=(0, 0, 0)):
    loc = tuple(loc) + (0.0,) * (3 - len(loc))
    if r * max(scale) < 0.05:
        segs, rings = min(segs, 6), min(rings, 4)
    return reg(L.sphere('s', r, loc, M(c), scale=scale, segs=segs, rings=rings, rot=rot))


def blob(r, loc=(0, 0, 0), c='leaf', scale=(1, 1, 1), seed=0, amp=0.2, subdiv=2, flat_bottom=0.0, facet=False,
         rot=(0, 0, 0)):
    loc = tuple(loc) + (0.0,) * (3 - len(loc))
    return reg(L.blob('bl', r, loc, M(c), scale=scale, seed=seed, amp=amp, subdiv=subdiv, flat_bottom=flat_bottom,
                      facet=facet, rot=rot))


def snow(sx, sy, t, loc, rot=(0, 0, 0), seed=0, droop=0.0, cuts=None):
    """Soft snow slab (light version of prop_lib.snow_slab): bottom at loc, gentle bulges on top."""
    from mathutils import noise
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, t), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, t / 2.0), verts=bm.verts)
    if cuts is None:
        cuts = 2 if max(sx, sy) > 1.5 else (1 if max(sx, sy) > 0.6 else 0)
    if cuts:
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6],
                                  cuts=cuts, use_grid_fill=True)
    off = Vector((seed * 1.3, seed * 2.1, 0.0))
    for v in bm.verts:
        if v.co.z > t * 0.6:
            v.co.z += 0.3 * t * noise.noise(Vector((v.co.x * 2.2, v.co.y * 2.2, 0)) + off)
    o = L.finish('snow', bm, [M('snow', 0.9)], tuple(loc), rot, bevel=min(t * 0.45, 0.06), segs=2, angle=30)
    return reg(o)


def snowcap(r, loc, h=0.07, seed=0, scale=(1, 1, 1)):
    return blob(r, loc, 'snow', scale=(scale[0], scale[1], h / r * scale[2]), seed=seed, amp=0.12, subdiv=2)


def seg(p, q, r, c='rope', segs=6, r2=None):
    """Thin cylinder from p to q (local coords)."""
    p, q = Vector(p), Vector(q)
    d = q - p
    ln = d.length
    rotq = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o = L.cyl('sg', r, ln, tuple((p + q) / 2), mat=M(c), segs=segs, r_top=r2, bevel=0.0, origin='center')
    o.modifiers.clear()
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = rotq
    return reg(o)


def extr(pts, th, loc=(0, 0, 0), rot=(0, 0, 0), c='wood_l', bev=0.01):
    o = L.extrude('ex', pts, th, loc=loc, rot=rot, top=M(c), side=M(c), bevel=bev, segs=1)
    return reg(o)


def log_(r, length, loc, rot, c='log1', segs=8, bev=0.025, cap='end'):
    o = L.cyl('log', r, length, loc, rot=rot, mat=M(c, 0.85), segs=segs, bevel=bev, bsegs=1, cap_mat=M(cap, 0.8),
              origin='center')
    return reg(o)


# --------------------------------------------------------------------------- empties
def slot(action, x, y, yaw=0.0, z=None, room=None):
    """Interaction spot in the current local frame.  yaw 0 = resident looks toward local -Y.
    z defaults to the floor top (FZ) in world space."""
    p = W((x, y, 0.0 if z is None else z))
    S.slots.append(dict(action=action, room=room if room is not None else S.room[-1], pos=p,
                        yaw=(yaw + cur_yaw()) % 360.0))


def fx(kind, x, y, z):
    S.fx.append((kind, W((x, y, z))))


def add_room(name, x0, y0, x1, y1):
    S.rooms.append(dict(name=name, center=[round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)],
                        size=[round(abs(x1 - x0), 3), round(abs(y1 - y0), 3)]))


def set_door(out_xy, in_xy):
    S.door = dict(out=[round(out_xy[0], 3), round(out_xy[1], 3)], **{'in': [round(in_xy[0], 3), round(in_xy[1], 3)]})


# --------------------------------------------------------------------------- building parts
LOGC = ('log1', 'log2', 'log3')


def _subtract(a, b, holes):
    segs = [(a, b)]
    for h0, h1 in holes:
        nxt = []
        for s0, s1 in segs:
            if h1 <= s0 or h0 >= s1:
                nxt.append((s0, s1))
                continue
            if h0 > s0:
                nxt.append((s0, h0))
            if h1 < s1:
                nxt.append((h1, s1))
        segs = nxt
    return [s for s in segs if s[1] - s[0] > 0.1]


def log_walls(Wd, Dp, H, openings, r=0.13, over=0.2, cols=LOGC, seed=1, sides='SNEW'):
    """Log-cabin walls on the rectangle |x|<=Wd/2, |y|<=Dp/2 (centre lines).
    openings: list of dict(side='S'|'N'|'E'|'W', off, w, zb, zt).  Returns the top z."""
    R = rnd(seed)
    hc = r * 1.84
    n = int(round(H / hc))
    for side in sides:
        xw = side in 'SN'
        Lh = (Wd if xw else Dp) / 2 + over
        holes_all = [o for o in openings if o['side'] == side]
        for k in range(n):
            z = r + k * hc + (0 if xw else hc / 2)
            holes = [(o['off'] - o['w'] / 2 - 0.02, o['off'] + o['w'] / 2 + 0.02) for o in holes_all
                     if z + r * 0.5 > o['zb'] and z - r * 0.5 < o['zt']]
            for s0, s1 in _subtract(-Lh, Lh, holes):
                c = cols[(k * 2 + (side in 'NE') + R.randrange(2)) % len(cols)]
                mid = (s0 + s1) / 2 + R.uniform(-0.01, 0.01)
                ln = s1 - s0
                if xw:
                    y = (-Dp / 2 if side == 'S' else Dp / 2)
                    log_(r * R.uniform(0.97, 1.03), ln, (mid, y, z), (0, 90, 0), c)
                else:
                    x = (Wd / 2 if side == 'E' else -Wd / 2)
                    log_(r * R.uniform(0.97, 1.03), ln, (x, mid, z), (90, 0, 0), c)
    return r + (n - 1) * hc + hc / 2 + r


def wall_frame(side, Wd, Dp):
    """(x, y, yaw_in) on a wall centre line: yaw so that local -Y faces INTO the room."""
    return {'S': (0, -Dp / 2, 180.0), 'N': (0, Dp / 2, 0.0), 'E': (Wd / 2, 0, 270.0), 'W': (-Wd / 2, 0, 90.0)}[side]


def on_wall(side, off, Wd, Dp, inset=0.0):
    """Frame for things standing/hanging against the inner face of an outer wall.
    Returns (x, y, rot) where the piece's back (+Y local) touches the wall and its front faces the room."""
    x, y, yaw = wall_frame(side, Wd, Dp)
    d = 0.13 + inset
    if side == 'S':
        return (off, y + d, 180.0)
    if side == 'N':
        return (off, y - d, 0.0)
    if side == 'E':
        return (x - d, off, 270.0)
    return (x + d, off, 90.0)


def _side_xf(side, off, Wd, Dp):
    """Frame on the wall centre line at offset `off`, local -Y = outside."""
    if side == 'S':
        return xf((off, -Dp / 2), 0)
    if side == 'N':
        return xf((-off, Dp / 2), 180)
    if side == 'E':
        return xf((Wd / 2, off), 90)
    return xf((-Wd / 2, -off), 270)


def window(side, off, Wd, Dp, w=0.7, zb=0.85, h=0.75, depth=0.3, shutter='blue', flowers=True, curtain='red',
           seed=0):
    """Glowing window with frame, cross bars, snowy sill, shutters, flower box, inside curtains.
    Must be called inside grp('walls').  off measured along the wall: S/N along +X, E/W along +Y.
    (N and W use mirrored offsets internally so the same off means the same world coordinate.)"""
    if side in 'NW':
        off = -off
    R = rnd(seed)
    with _side_xf(side, off, Wd, Dp), grp('walls~'):
        t = 0.07
        fr = 'wood_dd'
        bx((w + 2 * t, depth, t), (0, 0, zb - t), fr, bev=0.02)
        bx((w + 2 * t, depth, t), (0, 0, zb + h), fr, bev=0.02)
        for s in (-1, 1):
            bx((t, depth, h), (s * (w + t) / 2, 0, zb), fr, bev=0.015)
        bx((w, 0.04, h), (0, 0, zb), 'glow', bev=0)
        bx((0.045, depth * 0.5, h), (0, 0, zb), fr, bev=0)
        bx((w, depth * 0.5, 0.045), (0, 0, zb + h * 0.55), fr, bev=0)
        # outside sill + snow
        bx((w + 0.3, 0.16, 0.06), (0, -depth / 2 - 0.05, zb - 0.1), 'wood_m', bev=0.02)
        bx((w + 0.22, 0.14, 0.05), (0, -depth / 2 - 0.05, zb - 0.045), 'snow', bev=0.02)
        if shutter:
            for s in (-1, 1):
                bx((w * 0.42, 0.05, h + 0.06), (s * (w / 2 + t + w * 0.21 + 0.02), -depth / 2 - 0.02, zb - 0.03),
                   shutter, bev=0.015)
                bx((w * 0.3, 0.06, 0.05), (s * (w / 2 + t + w * 0.21 + 0.02), -depth / 2 - 0.03, zb + h * 0.5),
                   'white', bev=0.0)
        if flowers:
            bx((w + 0.1, 0.2, 0.16), (0, -depth / 2 - 0.16, zb - 0.32), 'wood_l', bev=0.02)
            bx((w + 0.02, 0.14, 0.03), (0, -depth / 2 - 0.16, zb - 0.17), 'soil', bev=0)
            fc = ['red', 'yellow', 'pink', 'white', 'purple']
            for i in range(5):
                x = -w / 2 + 0.06 + i * (w - 0.12) / 4
                blob(0.07, (x, -depth / 2 - 0.16, zb - 0.14), 'leaf_l', scale=(1, 0.9, 0.8), seed=seed + i, subdiv=1)
                sp(0.04, (x + R.uniform(-0.03, 0.03), -depth / 2 - 0.2, zb - 0.08), fc[(i + seed) % 5],
                   segs=8, rings=5)
        if curtain:
            for s in (-1, 1):
                bx((w * 0.28, 0.05, h + 0.1), (s * (w / 2 - w * 0.1), depth / 2 + 0.04, zb - 0.02), curtain,
                   bev=0.02)
            bx((w + 0.3, 0.05, 0.05), (0, depth / 2 + 0.06, zb + h + 0.06), 'wood_dd', bev=0)
    return dict(side=side, off=off if side not in 'NW' else -off, w=w + 0.16, zb=zb - 0.08, zt=zb + h + 0.08)


def door(side, off, Wd, Dp, w=0.95, h=1.55, depth=0.32, leaf='wood_d', lantern_side=1, open_in=True, seed=0):
    """Door frame + open door leaf + lantern.  In grp('walls')."""
    if side in 'NW':
        off = -off
    with _side_xf(side, off, Wd, Dp):
        t = 0.1
        bx((t, depth, h + t), (-(w + t) / 2, 0, 0), 'wood_dd', bev=0.02)
        bx((t, depth, h + t), ((w + t) / 2, 0, 0), 'wood_dd', bev=0.02)
        bx((w + 2 * t + 0.1, depth + 0.04, 0.14), (0, 0, h), 'wood_dd', bev=0.03)
        # open leaf (hinged on the left, swung into the room)
        with xf((-w / 2 + 0.03, depth / 2 + 0.03, FZ), 95 if open_in else 0), grp('walls~'):
            for i in range(4):
                bx((w / 4 - 0.01, 0.06, h - FZ - 0.04), (-(w / 2) + w / 8 + i * w / 4 + w / 2, 0.03, 0),
                   (leaf, 'wood_dd')[i % 2] if leaf == 'wood_d' else leaf, bev=0.01)
            bx((w - 0.04, 0.08, 0.08), (w / 2, 0.03, 0.3), 'wood_dd', bev=0.01)
            bx((w - 0.04, 0.08, 0.08), (w / 2, 0.03, h - FZ - 0.4), 'wood_dd', bev=0.01)
            sp(0.04, (w - 0.12, -0.03, 0.72), 'gold', segs=8, rings=5)
        if lantern_side:
            with grp('walls~'):
                lantern(lantern_side * (w / 2 + 0.32), -depth / 2 - 0.12, h - 0.15)
    return dict(side=side, off=off if side not in 'NW' else -off, w=w + 0.1, zb=-1.0, zt=h + 0.1)


def lantern(x, y, z, size=0.16, bracket=True, light=True):
    """Hanging lantern; (x, y, z) = top of the bracket."""
    if bracket:
        bx((0.05, 0.22, 0.05), (x, y + 0.11, z), 'iron', bev=0)
        seg((x, y, z), (x, y, z - 0.1), 0.012, 'iron')
    zz = z - 0.1 - size * 1.4
    bx((size * 1.15, size * 1.15, 0.035), (x, y, zz), 'iron', bev=0.01)
    bx((size, size, size * 1.2), (x, y, zz + 0.035), 'lamp', bev=0.015)
    bx((size * 1.3, size * 1.3, 0.06), (x, y, zz + 0.035 + size * 1.2), 'iron', bev=0.015, taper=(0.5, 0.5))
    if light:
        fx('fx_light', x, y, zz + size * 0.6)


def floor_boards(x0, y0, x1, y1, cols=('plank', 'plank2', 'plank3'), bw=0.22, seed=0, along='X', z0=0.0):
    """Plank floor: top at FZ.  Boards run along X (or Y)."""
    R = rnd(seed)
    th = FZ - z0
    if along == 'X':
        n = max(1, int(round((y1 - y0) / bw)))
        w = (y1 - y0) / n
        for i in range(n):
            # two boards per row with a staggered joint
            cut = x0 + (x1 - x0) * R.uniform(0.3, 0.7)
            for a, b in ((x0, cut), (cut, x1)):
                bx((b - a - 0.01, w - 0.012, th), ((a + b) / 2, y0 + w * (i + 0.5), z0), R.choice(cols), bev=0)
    else:
        n = max(1, int(round((x1 - x0) / bw)))
        w = (x1 - x0) / n
        for i in range(n):
            cut = y0 + (y1 - y0) * R.uniform(0.3, 0.7)
            for a, b in ((y0, cut), (cut, y1)):
                bx((w - 0.012, b - a - 0.01, th), (x0 + w * (i + 0.5), (a + b) / 2, z0), R.choice(cols), bev=0)


def stone_floor(x0, y0, x1, y1, cols=('stone_l', 'stone', 'stone_w'), tile=0.45, seed=0, z0=0.0):
    R = rnd(seed)
    nx = max(1, int(round((x1 - x0) / tile)))
    ny = max(1, int(round((y1 - y0) / tile)))
    tx, ty = (x1 - x0) / nx, (y1 - y0) / ny
    for i in range(nx):
        for j in range(ny):
            bx((tx - 0.03, ty - 0.03, FZ - z0), (x0 + tx * (i + 0.5), y0 + ty * (j + 0.5), z0), R.choice(cols),
               bev=0.02)


def plank_wall(p0, p1, H, doors=(), t=0.1, cols=('pale', 'pale2'), seed=0, door_h=1.6, trim='wood_m'):
    """Interior partition: vertical boards between p0 and p1 (axis-aligned), with door gaps.
    doors: list of (offset_from_p0, width).  Must be in grp('iwalls')."""
    R = rnd(seed)
    p0, p1 = Vector((*p0, 0)), Vector((*p1, 0))
    d = p1 - p0
    ln = d.length
    ang = math.degrees(math.atan2(d.y, d.x))
    with xf(tuple(p0), ang):
        holes = [(o - w / 2, o + w / 2) for o, w in doors]
        segs = _subtract(0.0, ln, holes)
        for a, b in segs:
            n = max(1, int(round((b - a) / 0.26)))
            bw = (b - a) / n
            for i in range(n):
                bx((bw - 0.008, t, H - FZ), (a + bw * (i + 0.5), 0, FZ), R.choice(cols), bev=0)
            bx((b - a, t + 0.03, 0.1), ((a + b) / 2, 0, FZ), trim, bev=0.01)          # skirting
        bx((ln, t + 0.04, 0.08), (ln / 2, 0, H), trim, bev=0.01)                   # top rail
        for o, w in doors:
            for s in (-1, 1):
                bx((0.08, t + 0.06, door_h - FZ), (o + s * (w / 2 + 0.04), 0, FZ), trim, bev=0.015)
            n = max(1, int(round(w / 0.26)))
            for i in range(n):
                bx((w / n - 0.008, t, H - door_h), (o - w / 2 + w / n * (i + 0.5), 0, door_h), R.choice(cols),
                   bev=0)
            bx((w + 0.24, t + 0.08, 0.1), (o, 0, door_h), trim, bev=0.015)


def gable_roof(Wd, Dp, top, ridge, over=0.4, over_x=0.35, cols=('roof_r1', 'roof_r2'), snow_on=True, seed=0,
               rows=6, gable=True, gable_cols=LOGC, r=0.13, ridge_log='wood_dd', snow_frac=0.78, gable_style='log'):
    """Gable roof with the ridge along X (in the current frame).  grp('roof')."""
    R = rnd(seed)
    run = Dp / 2 + over
    eave = top - over * (ridge - top) / (Dp / 2)
    rise = ridge - eave
    slope = math.hypot(run, rise)
    ang = math.degrees(math.atan2(rise, run))
    th = 0.08
    for s in (-1, 1):
        a = math.radians(ang)
        n = Vector((0, s * math.sin(a), math.cos(a)))           # outward normal
        up = Vector((0, -s * math.cos(a), math.sin(a)))         # toward ridge
        base = Vector((0, s * run, eave))
        rl = slope / rows
        for i in range(rows):
            c = cols[(i + R.randrange(2)) % len(cols)] if i % 2 else cols[0]
            pc = base + up * (rl * (i + 0.5)) + n * (th / 2 + 0.012 * (rows - i))
            bx((Wd + 2 * over_x, rl * 1.12, th), tuple(pc), c, rot=(-s * ang, 0, 0), bev=0.02, origin='center')
        if snow_on:
            ls = slope * snow_frac
            pc = Vector((0, 0, ridge)) - up * (ls / 2) + n * (th + 0.03)
            snow(Wd + 2 * over_x - 0.12, ls, 0.12, tuple(pc), rot=(-s * ang, 0, 0), seed=seed + s, droop=0.0)
            # little icicle-free drip edge
        # fascia board under the eave
        pe = base + n * 0.0 - up * 0.02
        bx((Wd + 2 * over_x, 0.06, 0.14), (0, pe.y, pe.z - 0.1), 'wood_dd', bev=0.02)
    log_(0.09, Wd + 2 * over_x + 0.1, (0, 0, ridge + 0.1), (0, 90, 0), ridge_log, cap='end')
    if snow_on:
        snow(Wd + 2 * over_x, 0.34, 0.1, (0, 0, ridge + 0.12), seed=seed + 5)
    if gable and gable_style == 'board':
        n = int(round(Dp / 0.26))
        bw = Dp / n
        for i in range(n):
            yy = -Dp / 2 + bw * (i + 0.5)
            hh = (ridge - top) * (1 - abs(yy) / (Dp / 2 + over * 0.3)) + 0.05
            for sx in (-1, 1):
                bx((2 * r, bw - 0.01, hh), (sx * Wd / 2, yy, top - 0.02), gable_cols[(i + (sx > 0)) % len(gable_cols)],
                   bev=0.01)
        for sx in (-1, 1):
            # hay-loft door
            bx((0.08, 0.7, 0.8), (sx * (Wd / 2 + r), 0, top + 0.1), 'white', bev=0.02)
            bx((0.09, 0.56, 0.66), (sx * (Wd / 2 + r + 0.005), 0, top + 0.17), gable_cols[1], bev=0.01)
            seg((sx * (Wd / 2 + r + 0.06), -0.26, top + 0.2), (sx * (Wd / 2 + r + 0.06), 0.26, top + 0.8), 0.025,
                'white')
    elif gable and gable_style == 'stone':
        R = rnd(seed + 40)
        z = top
        while z < ridge - 0.25:
            f = (ridge - z - 0.12) / (ridge - top)
            ln = Dp * f
            a = -ln / 2
            while a < ln / 2 - 0.05:
                l2 = min(ln / 2 - a, R.uniform(0.32, 0.6))
                for sx in (-1, 1):
                    bx((2 * r, l2 - 0.02, 0.225), (sx * Wd / 2, a + l2 / 2, z), R.choice(gable_cols), bev=0.04)
                a += l2
            z += 0.24
    if gable and gable_style == 'log':
        hc = r * 1.84
        z = top - r + hc / 2
        k = 0
        while z < ridge - 0.2:
            f = (ridge - z) / (ridge - top)
            ln = Dp * f + 0.05
            for sx in (-1, 1):
                log_(r, ln, (sx * Wd / 2, 0, z), (90, 0, 0), gable_cols[(k + (sx > 0)) % len(gable_cols)])
            z += hc
            k += 1
        for sx in (-1, 1):
            # little round attic vent
            cy(0.16, 0.06, (sx * (Wd / 2 + r + 0.01), 0, top + (ridge - top) * 0.32), 'wood_dd', rot=(0, 90, 0),
               segs=12, origin='center')
            cy(0.11, 0.07, (sx * (Wd / 2 + r + 0.02), 0, top + (ridge - top) * 0.32), 'glow', rot=(0, 90, 0),
               segs=12, origin='center', bev=0)
    return eave


def roof_z(y, Dp, top, ridge, over=0.4):
    """Height of the roof underside at |y| (for chimneys)."""
    eave = top - over * (ridge - top) / (Dp / 2)
    run = Dp / 2 + over
    return eave + (ridge - eave) * (1 - abs(y) / run)


def chimney(x, y, z0, z1, w=0.5, seed=0, cols=('stone', 'stone_d', 'stone_l')):
    """Stone chimney stack from z0 to z1 with cap + snow.  grp('roof')."""
    R = rnd(seed)
    z = z0
    k = 0
    while z < z1 - 0.01:
        h = min(0.22, z1 - z)
        bx((w + R.uniform(-0.02, 0.03), w + R.uniform(-0.02, 0.03), h), (x, y, z), cols[(k + R.randrange(3)) % 3],
           bev=0.03, rot=(0, 0, R.uniform(-2, 2)))
        z += h
        k += 1
    bx((w + 0.12, w + 0.12, 0.09), (x, y, z1), 'stone_d', bev=0.03)
    snowcap(w * 0.55, (x, y, z1 + 0.08), 0.08, seed=seed)
    fx('fx_smoke', x, y, z1 + 0.2)


def porch_roof(x, y0, y1, z0, z1, w, cols=('roof_r1', 'roof_r2'), seed=0, posts=True, post_z=0.0):
    """Small lean-to roof from the wall (y0, z0) out to (y1, z1) (y1 more negative).  grp('roof') for the
    roof; posts go to grp('exterior')."""
    run = abs(y1 - y0)
    ang = math.degrees(math.atan2(z0 - z1, run))
    ln = math.hypot(run, z0 - z1)
    mid = ((y0 + y1) / 2, (z0 + z1) / 2)
    n = Vector((0, -math.sin(math.radians(ang)), math.cos(math.radians(ang))))
    bx((w, ln + 0.1, 0.08), (x, mid[0], mid[1]), cols[0], rot=(ang, 0, 0), bev=0.02, origin='center')
    snow(w - 0.1, ln * 0.8, 0.09, (x, mid[0] + 0.05, mid[1] + 0.04 + n.z * 0.02), rot=(ang, 0, 0), seed=seed)
    bx((w, 0.06, 0.12), (x, y1 - 0.02, z1 - 0.12), 'wood_dd', bev=0.02)
    if posts:
        with grp('exterior'):
            for s in (-1, 1):
                cy(0.07, z1 - post_z - 0.05, (x + s * (w / 2 - 0.15), y1 + 0.12, post_z), 'wood_m', segs=8)


# --------------------------------------------------------------------------- small decor (generic)
def flower_pot(x, y, z=0.0, c='terracotta', fc='red', seed=0, s=1.0):
    cy(0.1 * s, 0.14 * s, (x, y, z), c, r_top=0.12 * s, segs=10)
    blob(0.12 * s, (x, y, z + 0.2 * s), 'leaf', scale=(1, 1, 0.9), seed=seed)
    R = rnd(seed)
    for i in range(3):
        a = R.uniform(0, 6.28)
        sp(0.035 * s, (x + math.cos(a) * 0.08 * s, y + math.sin(a) * 0.08 * s, z + 0.27 * s), fc, segs=8, rings=5)


def snow_pile(x, y, r=0.35, seed=0):
    blob(r, (x, y, 0), 'snow', scale=(1.3, 1.0, 0.45), seed=seed, amp=0.18, flat_bottom=0.1)


def bush(x, y, r=0.35, seed=0, berries=True):
    blob(r, (x, y, r * 0.7), 'leaf', scale=(1.2, 1.0, 0.85), seed=seed, amp=0.22)
    snowcap(r * 0.8, (x, y, r * 1.35), 0.08, seed=seed)
    if berries:
        R = rnd(seed)
        for i in range(4):
            a = R.uniform(0, 6.28)
            sp(0.04, (x + math.cos(a) * r * 1.0, y + math.sin(a) * r * 0.9, r * 0.8 + R.uniform(-0.1, 0.1)), 'red',
               segs=6, rings=4)


def sign_board(x, y, z, shape='bread', w=0.7, h=0.45, c='wood_l', emblem='bread', ec=None):
    """Hanging sign on a bracket (local -Y = outward), with a simple emblem (no text)."""
    bx((0.05, 0.6, 0.05), (x, y - 0.25, z), 'iron', bev=0)
    for s in (-1, 1):
        seg((x + s * w * 0.35, y - 0.45, z), (x + s * w * 0.35, y - 0.45, z - 0.12), 0.01, 'iron')
    with xf((x, y - 0.45, z - 0.12 - h), 90):
        bx((0.06, w, h), (0, 0, 0), c, bev=0.03)
        bx((0.07, w - 0.08, h - 0.08), (0, 0, 0.04), 'cream', bev=0.01)
        emblem_shape(emblem, ec, h)


def emblem_shape(kind, ec, h):
    """Small relief icon on both faces of a sign (local frame: board in YZ plane)."""
    for sx in (-1, 1):
        x = sx * 0.045
        if kind == 'bread':
            sp(0.12, (x, 0, h / 2), ec or 'bread', scale=(0.4, 1.4, 0.7), segs=10, rings=6)
        elif kind == 'mug':
            bx((0.04, 0.16, 0.2), (x, -0.02, h / 2 - 0.1), ec or 'gold', bev=0.02)
            bx((0.04, 0.17, 0.05), (x, -0.02, h / 2 + 0.08), 'white', bev=0.02)
            cy(0.05, 0.03, (x, 0.09, h / 2), ec or 'gold', rot=(0, 90, 0), origin='center', segs=8)
        elif kind == 'bag':
            sp(0.1, (x, 0, h / 2 - 0.02), ec or 'sack', scale=(0.4, 1.0, 1.0), segs=10, rings=6)
            cy(0.035, 0.06, (x, 0, h / 2 + 0.08), 'rope', segs=8)
        elif kind == 'house':
            extr([(-0.13, -0.1), (0.13, -0.1), (0.13, 0.04), (0, 0.15), (-0.13, 0.04)], 0.04,
                 loc=(x - 0.02, 0, h / 2), rot=(90, 0, 90), c=ec or 'red')
        elif kind == 'axe':
            bx((0.04, 0.03, 0.26), (x, 0, h / 2 - 0.13), 'wood_d', bev=0)
            bx((0.04, 0.12, 0.08), (x, 0.05, h / 2 + 0.04), ec or 'steel', bev=0.01)
        elif kind == 'wheat':
            for i in (-1, 0, 1):
                seg((x, 0, h / 2 - 0.12), (x, i * 0.07, h / 2 + 0.08), 0.012, 'straw_d')
                sp(0.03, (x, i * 0.075, h / 2 + 0.1), ec or 'wheat', scale=(1, 1, 1.8), segs=6, rings=4)
        elif kind == 'saw':
            cy(0.12, 0.04, (x, 0, h / 2), ec or 'steel', rot=(0, 90, 0), origin='center', segs=14)
        elif kind == 'pick':
            bx((0.04, 0.03, 0.26), (x, 0, h / 2 - 0.13), 'wood_d', bev=0)
            bx((0.04, 0.3, 0.05), (x, 0, h / 2 + 0.1), ec or 'iron_l', bev=0.01)
        elif kind == 'star':
            sp(0.09, (x, 0, h / 2), ec or 'gold', scale=(0.4, 1, 1), segs=8, rings=5)


# --------------------------------------------------------------------------- finalize / export
def _to_meshes(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        if o.type not in ('MESH', 'CURVE'):
            continue
        oe = o.evaluated_get(dg)
        try:
            me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
        except Exception:
            continue
        if len(me.polygons) == 0:
            bpy.data.meshes.remove(me)
            continue
        mw = o.matrix_world.copy()
        nob = bpy.data.objects.new(o.name + '_m', me)
        bpy.context.scene.collection.objects.link(nob)
        nob.matrix_world = mw
        out.append(nob)
    return out


def _join(obs, name):
    if not obs:
        return None
    with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, selected_objects=obs):
        bpy.ops.object.join()
    ob = obs[0]
    with bpy.context.temp_override(active_object=ob, selected_editable_objects=[ob], selected_objects=[ob],
                                   object=ob):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.name = name
    ob.data.name = name
    return ob


def _cut_low(src, name, zc, cap='end'):
    """Copy of `src` cut at height zc, keeping the part below, with capped cut faces."""
    me = src.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, zc), plane_no=(0, 0, 1), clear_outer=True)
    edges = [e for e in bm.edges if e.is_boundary and all(abs(v.co.z - zc) < 1e-4 for v in e.verts)]
    capm = M(cap, 0.8)
    mats = list(me.materials)
    if capm.name not in [m.name for m in mats if m]:
        me.materials.append(capm)
        mats = list(me.materials)
    ci = [m.name if m else '' for m in mats].index(capm.name)
    if edges:
        res = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        for f in res['faces']:
            f.material_index = ci
            f.smooth = False
        bmesh.ops.recalc_face_normals(bm, faces=res['faces'])
        for f in res['faces']:
            if f.normal.z < 0:
                f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    try:
        if 'custom_normal' in me.attributes:
            me.attributes.remove(me.attributes['custom_normal'])
    except Exception:
        pass
    try:
        me.set_sharp_from_angle(angle=math.radians(40))
    except Exception:
        pass
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.name = name
    return ob


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


PROTECT = ('log', 'roof_', 'plank', 'end')


def _limit_materials(nodes, limit=30):
    """If more than `limit` materials are used, remap the rarest non-emissive ones to the nearest colour."""
    use = {}
    for ob in nodes:
        for p in ob.data.polygons:
            m = ob.data.materials[p.material_index] if ob.data.materials else None
            if m:
                use[m.name] = use.get(m.name, 0) + 1
    if len(use) <= limit:
        return len(use)

    def rgb(m):
        p = m.node_tree.nodes.get('Principled BSDF')
        return tuple(p.inputs['Base Color'].default_value[:3])

    def emissive(m):
        p = m.node_tree.nodes.get('Principled BSDF')
        return p.inputs['Emission Strength'].default_value > 0.01

    def enc(v):
        return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055

    def lab(m):
        r, g, b = [enc(max(0.0, v)) for v in rgb(m)]
        # cheap perceptual-ish space: luma + two chroma axes
        return (0.6 * (0.3 * r + 0.59 * g + 0.11 * b), r - g, (r + g) / 2 - b)

    keep = set(use)
    remap = {}
    cand = sorted(n for n in keep if not emissive(bpy.data.materials[n]) and n != "snow")
    while len(keep) > limit and len(cand) > 1:
        best = None
        for i, a in enumerate(cand):
            la = lab(bpy.data.materials[a])
            for b2 in cand[i + 1:]:
                lb = lab(bpy.data.materials[b2])
                d = sum((x - y) ** 2 for x, y in zip(la, lb))
                if a.startswith(PROTECT) or b2.startswith(PROTECT):
                    d = d * 12 + 0.002          # keep log / roof / floor variation as long as possible
                if best is None or d < best[0]:
                    best = (d, a, b2)
        _, a, b2 = best
        lo, hi = (a, b2) if use[a] < use[b2] else (b2, a)
        remap[lo] = hi
        use[hi] += use[lo]
        keep.discard(lo)
        cand.remove(lo)
    for nm in list(remap):
        t = remap[nm]
        while t in remap:
            t = remap[t]
        remap[nm] = t
    for ob in nodes:
        for i, m in enumerate(ob.data.materials):
            if m and m.name in remap:
                ob.data.materials[i] = bpy.data.materials[remap[m.name]]
    print('  materials remapped:', remap)
    return len(keep)


ALIAS = {
    'iron_l': ('stone_d', 'iron', 'stone'), 'charcoal': ('iron', 'wood_dd'), 'ink': ('iron', 'wood_dd', 'navy'),
    'navy': ('blue', 'iron'), 'soil': ('wood_dd', 'bark'), 'copper': ('orange', 'gold', 'log3'),
    'terracotta': ('brick', 'orange', 'log3'), 'flour': ('white', 'cream', 'paper'), 'ceramic': ('white', 'cream'),
    'paper': ('cream', 'white'), 'white': ('cream', 'paper'), 'cream': ('white', 'canvas'),
    'straw_d': ('mustard', 'straw', 'wood_l'), 'straw': ('wheat', 'mustard', 'yellow'), 'teal': ('green', 'blue_l'),
    'green': ('leaf_l', 'leaf'), 'leaf_l': ('green', 'leaf'), 'leaf': ('leaf_l', 'green'),
    'book_r': ('red', 'red_d'), 'book_b': ('blue', 'navy'), 'book_g': ('green', 'leaf'), 'book_y': ('mustard', 'yellow'),
    'purple': ('pink', 'rose', 'blue'), 'rose': ('pink', 'red'), 'pink': ('rose', 'red'), 'mustard': ('yellow', 'gold'),
    'yellow': ('gold', 'mustard'), 'gold': ('yellow', 'mustard'), 'orange': ('copper', 'gold'),
    'red_d': ('red', 'brick'), 'red': ('red_d', 'rose'), 'blue_l': ('blue', 'steel'), 'blue': ('blue_l', 'navy'),
    'steel': ('stone_l', 'blue_l'), 'stone_w': ('stone', 'stone_l'), 'stone_l': ('stone', 'stone_w'),
    'stone_d': ('stone', 'iron'), 'iron': ('stone_d', 'charcoal'), 'bark': ('wood_dd', 'wood_d'),
    'wood_dd': ('wood_d', 'bark'), 'wood_d': ('wood_dd', 'wood_m'), 'wood_m': ('wood_d', 'wood_l'),
    'wood_l': ('plank', 'wood_m'), 'plank': ('wood_l', 'plank2'), 'plank2': ('plank', 'plank3'),
    'plank3': ('plank2', 'wood_m'), 'pale': ('pale2', 'end'), 'pale2': ('pale', 'end'), 'end': ('pale', 'pale2'),
    'sack': ('canvas', 'pale'), 'canvas': ('sack', 'cream'), 'bread_d': ('bread', 'wood_m'), 'bread': ('bread_d', 'log3'),
    'wheat': ('straw', 'yellow'), 'water': ('blue_l', 'blue'), 'brick_d': ('brick', 'red_d'), 'brick': ('brick_d', 'terracotta'),
    'mortar': ('canvas', 'stone_l'), 'leather': ('wood_d', 'bark'), 'rope': ('sack', 'canvas'),
    'roof_r2': ('roof_r1',), 'roof_b2': ('roof_b1',), 'roof_g2': ('roof_g1',), 'roof_t2': ('roof_t1',),
    'log3': ('log1', 'wood_l'), 'log2': ('log1', 'wood_m'), 'log1': ('log2', 'log3'),
}


def _empty(name, pos, yaw=0.0, props=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SINGLE_ARROW'
    e.empty_display_size = 0.3
    bpy.context.scene.collection.objects.link(e)
    e.location = pos
    e.rotation_euler = (0, 0, math.radians(yaw))
    for k, v in (props or {}).items():
        e[k] = v
    return e


NODE_ORDER = ['roof', 'walls', 'walls_low', 'iwalls', 'iwalls_low', 'floor', 'interior', 'exterior']


def finalize(low=True):
    """Merge tagged objects into the contract nodes.  Returns (nodes dict, slot list)."""
    bpy.context.view_layer.update()
    # drop hidden-render helpers and lights/cameras
    for o in list(bpy.data.objects):
        if o.type in ('LIGHT', 'CAMERA') or (o.type in ('MESH', 'CURVE') and o.hide_render):
            bpy.data.objects.remove(o, do_unlink=True)
    groups = {}
    for o in bpy.data.objects:
        if o.type in ('MESH', 'CURVE'):
            groups.setdefault(o.get('grp', 'interior'), []).append(o)
    nodes = {}
    for g, objs in groups.items():
        ms = _to_meshes(objs)
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)
        ob = _join(ms, g)
        if ob is None:
            continue
        nodes[g] = ob
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY':
            bpy.data.objects.remove(o, do_unlink=True)
    if low:
        for g in ('walls', 'iwalls'):
            if g in nodes:
                nodes[g + '_low'] = _cut_low(nodes[g], g + '_low', FZ + LOW_CUT, cap=S.low_cap.get(g, 'end'))
    for g in [k for k in nodes if k.endswith('~')]:
        base = g[:-1]
        if base in nodes:
            nodes[base] = _join([nodes[base], nodes.pop(g)], base)
        else:
            nodes[base] = nodes.pop(g)
            nodes[base].name = base
    # anim nodes: move origin to the pivot
    for g, ob in nodes.items():
        if g in S.anim_origin:          # anim_* pivots, tree_* bases
            pv = Vector(S.anim_origin[g])
            ob.data.transform(Matrix.Translation(-pv))
            ob.location = pv
    return nodes


def write_empties(furniture=False):
    counts = {}
    slots = []
    for s in S.slots:
        counts[s['action']] = counts.get(s['action'], 0) + 1
        sid = 'slot.%s.%d' % (s['action'], counts[s['action']])
        p = s['pos']
        _empty(sid, p, s['yaw'], {'room': s['room']})
        slots.append(dict(id=sid, action=s['action'], room=s['room'], pos=[round(p.x, 3), round(p.y, 3),
                                                                             round(p.z, 3)],
                          yaw=round(s['yaw'] if s['yaw'] <= 180 else s['yaw'] - 360, 1)))
    fxc = {}
    for kind, p in S.fx:
        fxc[kind] = fxc.get(kind, 0) + 1
    fxi = {}
    fx_list = []
    for kind, p in S.fx:
        fxi[kind] = fxi.get(kind, 0) + 1
        nm = kind if fxc[kind] == 1 else '%s_%d' % (kind, fxi[kind])
        _empty(nm, p)
        fx_list.append(dict(id=nm, pos=[round(p.x, 3), round(p.y, 3), round(p.z, 3)]))
    if S.door and not furniture:
        _empty('door.out', (S.door['out'][0], S.door['out'][1], 0.0), 0.0)
        _empty('door.in', (S.door['in'][0], S.door['in'][1], FZ), 0.0)
    return slots, fx_list


def export_glb(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                              export_extras=True, export_animations=False, export_cameras=False,
                              export_lights=False)


def scene_height(nodes):
    bpy.context.view_layer.update()
    zmax = 0.0
    for ob in nodes.values():
        for v in ob.data.vertices:
            z = (ob.matrix_world @ v.co).z
            if z > zmax:
                zmax = z
    return round(zmax, 2)


def glb_info(path):
    """Parse a GLB: node names, triangles per node, material count."""
    import struct
    d = open(path, 'rb').read()
    n = struct.unpack('<I', d[12:16])[0]
    js = json.loads(d[20:20 + n].decode('utf-8'))
    acc = js.get('accessors', [])
    tris = {}
    for nd in js.get('nodes', []):
        if 'mesh' in nd:
            t = 0
            for pr in js['meshes'][nd['mesh']]['primitives']:
                if 'indices' in pr:
                    t += acc[pr['indices']]['count'] // 3
                else:
                    t += acc[pr['attributes']['POSITION']]['count'] // 3
            tris[nd['name']] = t
    names = [nd.get('name') for nd in js.get('nodes', [])]
    extras = {nd.get('name'): nd.get('extras', {}) for nd in js.get('nodes', [])}
    return dict(nodes=names, tris=tris, total=sum(tris.values()), mats=len(js.get('materials', [])),
                extras=extras)


# --------------------------------------------------------------------------- more wall styles
def stone_walls(Wd, Dp, H, openings, r=0.13, cols=('stone', 'stone_d', 'stone_l', 'stone_w'), seed=1, sides='SNEW',
                course=0.24):
    """Rough stone-block walls (same footprint rules as log_walls).  Returns top z."""
    R = rnd(seed)
    n = int(round(H / course))
    for side in sides:
        xw = side in 'SN'
        holes_all = [o for o in openings if o['side'] == side]
        for k in range(n):
            z0 = k * course
            zc = z0 + course / 2
            if xw:
                Lh = Wd / 2 + r if k % 2 == 0 else Wd / 2 - r
            else:
                Lh = Dp / 2 - r if k % 2 == 0 else Dp / 2 + r
            holes = [(o['off'] - o['w'] / 2 - 0.02, o['off'] + o['w'] / 2 + 0.02) for o in holes_all
                     if zc + course * 0.3 > o['zb'] and zc - course * 0.3 < o['zt']]
            for s0, s1 in _subtract(-Lh, Lh, holes):
                a = s0
                while a < s1 - 0.05:
                    ln = min(s1 - a, R.uniform(0.32, 0.6))
                    if s1 - (a + ln) < 0.18:
                        ln = s1 - a
                    mid = a + ln / 2
                    c = R.choice(cols)
                    sz = (ln - 0.02, 2 * r + R.uniform(-0.01, 0.03), course - 0.015)
                    if xw:
                        y = (-Dp / 2 if side == 'S' else Dp / 2)
                        bx(sz, (mid, y, z0), c, bev=0.045)
                    else:
                        x = (Wd / 2 if side == 'E' else -Wd / 2)
                        bx((sz[1], sz[0], sz[2]), (x, mid, z0), c, bev=0.045)
                    a += ln
    return n * course


def plank_walls(Wd, Dp, H, openings, r=0.13, cols=('red', 'red_d'), trim='white', seed=1, sides='SNEW', bw=0.26):
    """Vertical board walls with trim (barn style).  Returns top z."""
    R = rnd(seed)
    for side in sides:
        xw = side in 'SN'
        Lh = (Wd if xw else Dp) / 2 - r
        holes_all = [o for o in openings if o['side'] == side]
        n = max(1, int(round(2 * Lh / bw)))
        w = 2 * Lh / n
        for i in range(n):
            mid = -Lh + w * (i + 0.5)
            pieces = [(0.0, H)]
            for o in holes_all:
                if abs(mid - o['off']) < o['w'] / 2 + w * 0.3:
                    nxt = []
                    for a, b in pieces:
                        if o['zt'] <= a or o['zb'] >= b:
                            nxt.append((a, b))
                            continue
                        if o['zb'] > a:
                            nxt.append((a, o['zb']))
                        if o['zt'] < b:
                            nxt.append((o['zt'], b))
                    pieces = nxt
            c = cols[(i + R.randrange(2)) % len(cols)]
            for a, b in pieces:
                a = max(a, 0.0)
                if b - a < 0.05:
                    continue
                sz = (w - 0.012, 2 * r, b - a)
                if xw:
                    y = (-Dp / 2 if side == 'S' else Dp / 2)
                    bx(sz, (mid, y, a), c, bev=0.012)
                else:
                    x = (Wd / 2 if side == 'E' else -Wd / 2)
                    bx((sz[1], sz[0], sz[2]), (x, mid, a), c, bev=0.012)
        # trims: top + bottom bands
        for z, h in ((0.0, 0.16), (H - 0.12, 0.14)):
            if xw:
                y = (-Dp / 2 if side == 'S' else Dp / 2)
                for s0, s1 in _subtract(-Lh, Lh, [(o['off'] - o['w'] / 2, o['off'] + o['w'] / 2) for o in holes_all
                                                  if o['zb'] < z + h and o['zt'] > z]):
                    bx((s1 - s0, 2 * r + 0.04, h), ((s0 + s1) / 2, y, z), trim, bev=0.015)
            else:
                x = (Wd / 2 if side == 'E' else -Wd / 2)
                for s0, s1 in _subtract(-Lh, Lh, [(o['off'] - o['w'] / 2, o['off'] + o['w'] / 2) for o in holes_all
                                                  if o['zb'] < z + h and o['zt'] > z]):
                    bx((2 * r + 0.04, s1 - s0, h), (x, (s0 + s1) / 2, z), trim, bev=0.015)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((2 * r + 0.06, 2 * r + 0.06, H), (sx * Wd / 2, sy * Dp / 2, 0), trim, bev=0.02)
    return H


def awning(x, y, z, w, depth=0.7, drop=0.35, c1='red', c2='cream', n=7):
    """Striped awning sticking out toward local -Y from (x, y, z) (back top edge).  Use grp('walls~')."""
    ang = math.degrees(math.atan2(drop, depth))
    ln = math.hypot(depth, drop)
    sw = w / n
    for i in range(n):
        xx = x - w / 2 + sw * (i + 0.5)
        c = c1 if i % 2 == 0 else c2
        bx((sw + 0.004, ln, 0.05), (xx, y - depth / 2, z - drop / 2), c, rot=(ang, 0, 0), bev=0.01, origin='center')
        cy(sw / 2, 0.05, (xx, y - depth - 0.01, z - drop - 0.02), c, rot=(90, 0, 0), segs=10, origin='center', bev=0)
    for s in (-1, 1):
        seg((x + s * (w / 2 - 0.05), y, z - drop - 0.2), (x + s * (w / 2 - 0.05), y - depth, z - drop), 0.015, 'iron')
    nrm = Vector((0, -math.sin(math.radians(ang)), math.cos(math.radians(ang))))
    snow(w - 0.15, ln * 0.7, 0.06, (x, y - depth * 0.45, z - drop * 0.45 + 0.03), rot=(ang, 0, 0), seed=n)


def porch(cx, y_wall, w, depth, z_roof0, z_roof1, cols=('roof_r1', 'roof_r2'), seed=0, rail=True):
    """Front deck + posts + railing + lean-to roof, in front of a south wall at y_wall."""
    y1 = y_wall - depth
    with grp('floor'):
        R = rnd(seed)
        n = int(round(w / 0.22))
        for i in range(n):
            bx((w / n - 0.012, depth, 0.1), (cx - w / 2 + w / n * (i + 0.5), y_wall - depth / 2, 0.0),
               R.choice(['plank', 'plank2', 'wood_l']), bev=0.012)
    with grp('exterior'):
        for s in (-1, 1):
            cy(0.07, z_roof1 - 0.12, (cx + s * (w / 2 - 0.1), y1 + 0.1, 0.1), 'wood_m', segs=8)
            bx((0.18, 0.18, 0.1), (cx + s * (w / 2 - 0.1), y1 + 0.1, 0.0), 'stone', bev=0.02)
        if rail:
            for s in (-1, 1):
                bx((0.06, depth - 0.15, 0.06), (cx + s * (w / 2 - 0.1), y_wall - depth / 2 + 0.05, 0.6), 'wood_m',
                   bev=0.01)
                for k in range(3):
                    cy(0.02, 0.5, (cx + s * (w / 2 - 0.1), y_wall - 0.2 - k * (depth - 0.3) / 2, 0.1), 'wood_l',
                       segs=6, bev=0)
    with grp('roof'):
        porch_roof(cx, y_wall + 0.1, y1 - 0.15, z_roof0, z_roof1, w + 0.3, cols=cols, seed=seed, posts=False)


def face(px, py, tx, ty):
    """yaw (deg) for a resident at (px, py) looking at (tx, ty)."""
    return math.degrees(math.atan2(tx - px, -(ty - py)))
