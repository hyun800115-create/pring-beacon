"""
b3d_buildings2.py - CONTRACT3D appendix A (6.2): farm-animal buildings, orchard, apiary, fishing spot, dairy,
the spring beacon, watchtower, market stall and village statue.

Same rules as b3d_buildings.py: metres, origin = footprint centre (fenced yards / piers included), front door -Y.
Groups -> GLB nodes: roof, walls, iwalls, floor, interior, exterior, anim_*, tree_* (orchard), fx_* empties.
Animal buildings store the wandering area in K.S.extra['pen'] = {center: [x, y], size: [w, d]} (Blender coords).

    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_export.py -- --buildings coop barn ...
"""
import math
from collections import OrderedDict

from mathutils import Vector

import b3d_kit as K
import b3d_furniture as F
from b3d_kit import bx, cy, sp, blob, seg, slot, fx, xf, grp, room, rnd, snow, snowcap, extr
from b3d_furniture import put
from b3d_buildings import Shell, place, yard_decor, tower_ring  # noqa: F401

BUILDINGS = OrderedDict()

DIRT = '#B08A5E'      # pen ground
DIRT2 = '#9C784F'
GRASS = '#8FBF6A'
GRASS2 = '#79AE58'
MUD = '#6E4B30'


def building(key, name, cat, size, low=True):
    def deco(fn):
        BUILDINGS[key] = dict(key=key, name=name, cat=cat, size=size, fn=fn, low=low)
        return fn
    return deco


# =========================================================================== shared yard helpers
def fence(pts, h=0.8, gaps=(), closed=False, spacing=1.05, seed=0, cols=('wood_l', 'plank', 'wood_m'),
          post='wood_m', caps=True):
    """Post-and-rail fence along a polyline (grp exterior).  gaps = [(x, y, width)] = openings (gates)."""
    R = rnd(seed)
    P = [Vector((x, y, 0.0)) for x, y in pts]
    if closed:
        P.append(P[0])

    def in_gap(p, pad=0.0):
        for gx, gy, gw in gaps:
            if (Vector((gx, gy, 0)) - p).length < gw / 2 + pad:
                return True
        return False

    with grp('exterior'):
        done = []
        for a, b in zip(P, P[1:]):
            d = b - a
            ln = d.length
            n = max(1, int(math.ceil(ln / spacing)))
            ang = math.degrees(math.atan2(d.y, d.x))
            pts_ = [a + d * (i / n) for i in range(n + 1)]
            for p in pts_:
                if in_gap(p, -0.05) or any((p - q).length < 0.05 for q in done):
                    continue
                done.append(p)
                cy(0.065, h + 0.08, (p.x, p.y, 0), post, segs=8, bev=0)
                cy(0.08, 0.05, (p.x, p.y, h + 0.06), 'wood_dd', segs=8, bev=0)
                if caps:
                    sp(0.075, (p.x, p.y, h + 0.12), 'snow', scale=(1, 1, 0.55), segs=8, rings=4)
            for p0, p1 in zip(pts_, pts_[1:]):
                mid = (p0 + p1) / 2
                if in_gap(mid):
                    continue
                L = (p1 - p0).length + 0.06
                for z in (h * 0.42, h * 0.8):
                    bx((L, 0.05, 0.1), (mid.x, mid.y, z), R.choice(cols), rot=(0, 0, ang + R.uniform(-1, 1)),
                       bev=0.012)


def gate(x, y, w=1.0, h=0.85, ang=0.0, swing=70, c='wood_l'):
    """Tall gate posts + an open gate leaf (grp exterior).  ang = direction of the fence line (deg)."""
    with grp('exterior'), xf((x, y), ang):
        for s in (-1, 1):
            cy(0.08, h + 0.3, (s * w / 2, 0, 0), 'wood_d', segs=8, bev=0)
            sp(0.09, (s * w / 2, 0, h + 0.33), 'snow', scale=(1, 1, 0.6), segs=8, rings=4)
        with xf((-w / 2 + 0.05, 0, 0.08), -swing):
            for z in (0.12, 0.42, 0.72):
                bx((w - 0.12, 0.05, 0.1), ((w - 0.12) / 2, 0, z), c, bev=0.012)
            for xx in (0.05, w - 0.17):
                bx((0.08, 0.05, 0.75), (xx, 0, 0.05), c, bev=0.012)
            seg((0.08, 0, 0.12), (w - 0.2, 0, 0.78), 0.025, 'wood_m')


def yard_ground(x0, y0, x1, y1, c=DIRT, c2=DIRT2, seed=0, tufts=8):
    """Flat yard patch (grp floor) with a few darker spots + grass tufts on top."""
    R = rnd(seed)
    with grp('floor'):
        bx((x1 - x0, y1 - y0, 0.03), ((x0 + x1) / 2, (y0 + y1) / 2, 0), c, bev=0.012)
        for i in range(4):
            sp(R.uniform(0.3, 0.6), (R.uniform(x0 + 0.6, x1 - 0.6), R.uniform(y0 + 0.6, y1 - 0.6), 0.02), c2,
               scale=(1.4, 1, 0.05), segs=12, rings=4)
    with grp('exterior'):
        for i in range(tufts):
            x, y = R.uniform(x0 + 0.2, x1 - 0.2), R.uniform(y0 + 0.2, y1 - 0.2)
            for k in range(3):
                seg((x, y, 0.02), (x + R.uniform(-0.06, 0.06), y + R.uniform(-0.06, 0.06), 0.14 + 0.04 * k), 0.012,
                    ('leaf_l', 'green')[k % 2])


def pen(x0, y0, x1, y1, gate_at=None, gate_w=1.1, skip=None, seed=0, ground=(DIRT, DIRT2), margin=0.35,
        tufts=8):
    """Rectangular fenced pen.  gate_at = x of a gate in the front (south) side.  skip = (y_lo, y_hi) part of the
    west side left open (where the animal house wall closes it).  Stores K.S.extra['pen']."""
    yard_ground(x0, y0, x1, y1, ground[0], ground[1], seed=seed, tufts=tufts)
    gaps = []
    if gate_at is not None:
        gaps.append((gate_at, y0, gate_w))
    if skip:
        fence([(x0, skip[1]), (x0, y1), (x1, y1), (x1, y0), (x0, y0), (x0, skip[0])], gaps=gaps, seed=seed)
    else:
        fence([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], gaps=gaps, closed=True, seed=seed)
    if gate_at is not None:
        gate(gate_at, y0, gate_w)
    K.S.extra['pen'] = dict(center=[round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)],
                            size=[round(x1 - x0 - 2 * margin, 3), round(y1 - y0 - 2 * margin, 3)])


def trough(x, y, rot=0.0, L=1.2, fill='water', h=0.32):
    with xf((x, y), rot):
        for s in (-1, 1):
            bx((0.08, 0.36, h - 0.1), (s * (L / 2 - 0.1), 0, 0), 'wood_d', bev=0.012)
        bx((L, 0.34, 0.2), (0, 0, h - 0.2), 'wood_m', bev=0.02)
        bx((L - 0.1, 0.24, 0.02), (0, 0, h - 0.04), fill, bev=0)
        if fill == 'straw':
            R = rnd(int(x * 10))
            for i in range(5):
                sp(0.1, (-L / 2 + 0.15 + i * (L - 0.3) / 4, R.uniform(-0.04, 0.04), h - 0.02), 'straw',
                   scale=(1.3, 1, 0.5), segs=8, rings=4)


def hay_rack(x, y, rot=0.0, L=1.1):
    """V-shaped hay feeder on legs."""
    with xf((x, y), rot):
        for s in (-1, 1):
            seg((s * L / 2, -0.25, 0), (s * L / 2, 0.0, 0.9), 0.035, 'wood_d')
            seg((s * L / 2, 0.25, 0), (s * L / 2, 0.0, 0.9), 0.035, 'wood_d')
        for s in (-1, 1):
            for i in range(5):
                xx = -L / 2 + 0.1 + i * (L - 0.2) / 4
                seg((xx, s * 0.05, 0.4), (xx, s * 0.32, 0.95), 0.015, 'wood_l')
            bx((L, 0.05, 0.05), (0, s * 0.32, 0.93), 'wood_m', bev=0)
        blob(0.3, (0, 0, 0.75), 'straw', scale=(L * 1.6, 1.0, 0.75), seed=3, amp=0.18, subdiv=1)
        bx((L, 0.2, 0.05), (0, 0, 0.38), 'wood_m', bev=0)


def hatch(sh, side, off, w=0.5, h=0.55, ramp=0.0):
    """Animal opening in an outer wall (no door empty)."""
    with grp('walls'):
        sh.openings.append(K.door(side, off, sh.Wd, sh.Dp, w=w, h=h, depth=2 * sh.r + 0.06, lantern_side=0,
                                  open_in=True, leaf='wood_l'))
    if ramp:
        x, y, rot = sh.wall_xy(side, off)
        with grp('exterior'), xf((x, y), rot):
            bx((w - 0.05, ramp, 0.04), (0, -sh.r - ramp / 2 + 0.05, 0.08), 'wood_l', rot=(-8, 0, 0), bev=0.01,
               origin='center')
            for i in range(4):
                bx((w - 0.1, 0.03, 0.025), (0, -sh.r - 0.1 - i * ramp / 4, 0.1 + 0.03 - i * 0.012), 'wood_d',
                   bev=0)


def my_sign(x, y, z, kind, w=0.55, h=0.4):
    """Hanging sign with a custom farm icon (local -Y = out).  Call inside grp('walls~')."""
    K.sign_board(x, y, z, w=w, h=h, emblem='none')
    with xf((x, y - 0.45, z - 0.12 - h), 90):
        for sx in (-1, 1):
            xx = sx * 0.045
            if kind == 'egg':
                sp(0.08, (xx, 0, h / 2), 'cream', scale=(0.4, 0.8, 1.05), segs=10, rings=6)
            elif kind == 'milk':
                cy(0.07, 0.18, (xx, 0, h / 2 - 0.1), 'stone_l', rot=(0, 0, 0), segs=10, bev=0)
                cy(0.04, 0.06, (xx, 0, h / 2 + 0.08), 'stone_l', segs=8, bev=0)
            elif kind == 'cheese':
                extr([(-0.12, -0.08), (0.12, -0.08), (0.12, 0.0), (-0.12, 0.08)], 0.05, loc=(xx - 0.025, 0, h / 2),
                     rot=(90, 0, 90), c='yellow')
            elif kind == 'apple':
                sp(0.09, (xx, 0, h / 2 - 0.01), 'red', scale=(0.45, 1, 0.95), segs=10, rings=6)
                bx((0.03, 0.02, 0.06), (xx, 0, h / 2 + 0.07), 'wood_d', bev=0)
                sp(0.04, (xx, 0.04, h / 2 + 0.1), 'leaf_l', scale=(0.4, 1.3, 0.6), segs=6, rings=4)
            elif kind == 'honey':
                cy(0.08, 0.15, (xx, 0, h / 2 - 0.09), 'orange', segs=10, bev=0)
                cy(0.085, 0.03, (xx, 0, h / 2 + 0.05), 'canvas', segs=10, bev=0)
            elif kind == 'fish':
                sp(0.09, (xx, -0.02, h / 2), 'blue_l', scale=(0.4, 1.4, 0.65), segs=10, rings=6)
                extr([(0.0, 0.0), (0.09, 0.07), (0.09, -0.07)], 0.04, loc=(xx - 0.02, 0.1, h / 2), rot=(90, 0, 90),
                     c='blue_l')
            elif kind == 'wool':
                for k, (yy, zz) in enumerate(((-0.06, 0), (0.06, 0), (0, 0.06), (0, -0.05))):
                    sp(0.06, (xx, yy, h / 2 + zz), 'cream', scale=(0.5, 1, 1), segs=8, rings=5)
            elif kind == 'pig':
                sp(0.1, (xx, 0, h / 2), 'pink', scale=(0.4, 1, 0.9), segs=10, rings=6)
                sp(0.04, (xx * 1.4, -0.06, h / 2 - 0.02), 'rose', scale=(0.4, 1, 0.8), segs=8, rings=5)
            elif kind == 'cow':
                sp(0.1, (xx, 0, h / 2), 'cream', scale=(0.4, 1, 0.9), segs=10, rings=6)
                sp(0.04, (xx * 1.4, 0.04, h / 2 + 0.03), 'ink', scale=(0.4, 1, 0.8), segs=8, rings=5)
                sp(0.05, (xx * 1.4, -0.03, h / 2 - 0.05), 'pink', scale=(0.4, 1.2, 0.7), segs=8, rings=5)


def flower_bed(x0, y0, x1, y1, seed=0, cols=('red', 'yellow', 'pink', 'white', 'purple', 'orange'), n=None,
               border=True):
    """Soil bed with rows of little flowers (grp exterior)."""
    R = rnd(seed)
    with grp('exterior'):
        bx((x1 - x0, y1 - y0, 0.1), ((x0 + x1) / 2, (y0 + y1) / 2, 0), 'soil', bev=0.03)
        if border:
            for s in (-1, 1):
                bx((x1 - x0 + 0.1, 0.08, 0.14), ((x0 + x1) / 2, (y0 + y1) / 2 + s * (y1 - y0) / 2, 0), 'wood_m',
                   bev=0.015)
        n = n or int((x1 - x0) * (y1 - y0) * 9)
        for i in range(n):
            x, y = R.uniform(x0 + 0.1, x1 - 0.1), R.uniform(y0 + 0.1, y1 - 0.1)
            hh = R.uniform(0.18, 0.32)
            seg((x, y, 0.1), (x, y, 0.1 + hh), 0.01, 'leaf')
            blob(0.06, (x, y, 0.08), 'leaf_l', scale=(1.2, 1.2, 0.8), seed=i + seed, subdiv=1, amp=0.2)
            sp(0.045, (x, y, 0.1 + hh), R.choice(cols), scale=(1, 1, 0.7), segs=8, rings=4)


def apple_tree(key, x, y, seed=0, s=1.0, apples=12):
    """Round apple tree as its own node `key` (origin = trunk base)."""
    R = rnd(seed)
    K.S.anim_origin[key] = (x, y, 0.0)
    with grp(key), xf((x, y), R.uniform(0, 360), scale=s):
        cy(0.12, 1.0, (0, 0, 0), 'bark', r_top=0.09, segs=10, bev=0)
        for a in (0, 130, 250):
            ra = math.radians(a)
            seg((0, 0, 0.8), (0.35 * math.cos(ra), 0.35 * math.sin(ra), 1.25), 0.05, 'bark', r2=0.03)
        blob(0.75, (0, 0, 1.55), 'leaf', scale=(1.0, 1.0, 0.85), seed=seed, amp=0.18, subdiv=2)
        blob(0.48, (0.42, 0.18, 1.35), 'leaf_l', scale=(1, 1, 0.9), seed=seed + 1, amp=0.2, subdiv=1)
        blob(0.45, (-0.38, -0.22, 1.4), 'leaf_l', scale=(1, 1, 0.9), seed=seed + 2, amp=0.2, subdiv=1)
        blob(0.4, (-0.1, 0.35, 1.95), 'leaf_l', scale=(1, 1, 0.85), seed=seed + 3, amp=0.2, subdiv=1)
        for i in range(apples):
            az = R.uniform(0, math.tau)
            el = R.uniform(-0.5, 0.75)
            r = 0.78
            p = (r * math.cos(az) * math.cos(el), r * math.sin(az) * math.cos(el), 1.55 + 0.68 * math.sin(el))
            sp(0.065, p, 'red', segs=8, rings=5)
        for i in range(3):
            az = R.uniform(0, math.tau)
            sp(0.06, (0.6 * math.cos(az), 0.6 * math.sin(az), 0.05), 'red', segs=8, rings=5)
        # little blossoms (spring)
        for i in range(6):
            az = R.uniform(0, math.tau)
            el = R.uniform(0.0, 0.9)
            p = (0.8 * math.cos(az) * math.cos(el), 0.8 * math.sin(az) * math.cos(el), 1.55 + 0.7 * math.sin(el))
            sp(0.04, p, 'white', scale=(1, 1, 0.6), segs=6, rings=4)


def beehive(x, y, rot=0.0, seed=0, stack=2):
    R = rnd(seed)
    with xf((x, y), rot):
        for s in (-1, 1):
            for t in (-1, 1):
                bx((0.06, 0.06, 0.3), (s * 0.2, t * 0.18, 0), 'wood_d', bev=0)
        bx((0.56, 0.5, 0.06), (0, 0, 0.3), 'wood_m', bev=0.012)
        z = 0.36
        cols = ['yellow', 'cream', 'mustard', 'white']
        for i in range(stack):
            hh = 0.24 if i == 0 else 0.18
            bx((0.5, 0.44, hh), (0, 0, z), cols[(i + seed) % 4], bev=0.015)
            bx((0.52, 0.46, 0.025), (0, 0, z + hh - 0.02), 'wood_l', bev=0)
            z += hh
        bx((0.62, 0.56, 0.08), (0, 0, z), 'roof_r1' if seed % 2 else 'roof_b1', taper=(0.8, 0.8), bev=0.015)
        snowcap(0.2, (0, 0, z + 0.07), 0.04, seed=seed)
        bx((0.18, 0.02, 0.04), (0, -0.225, 0.4), 'ink', bev=0)
        bx((0.24, 0.1, 0.02), (0, -0.27, 0.37), 'wood_l', bev=0)
        for i in range(3):
            sp(0.022, (R.uniform(-0.3, 0.3), -0.35 + R.uniform(-0.1, 0.05), 0.5 + R.uniform(0, 0.4)), 'yellow',
               scale=(1.3, 1, 1), segs=6, rings=4)


def milk_can(x, y, z=0.0, s=1.0):
    cy(0.12 * s, 0.32 * s, (x, y, z), 'stone_l', segs=12, bev=0.01)
    cy(0.08 * s, 0.1 * s, (x, y, z + 0.32 * s), 'stone_l', r_top=0.06 * s, segs=10, bev=0)
    cy(0.075 * s, 0.04 * s, (x, y, z + 0.42 * s), 'steel', segs=10, bev=0)
    cy(0.125 * s, 0.03 * s, (x, y, z + 0.08 * s), 'steel', segs=12, bev=0)


def bucket(x, y, z=0.0, fill='white'):
    cy(0.1, 0.18, (x, y, z), 'wood_m', r_top=0.12, segs=10, bev=0)
    cy(0.11, 0.015, (x, y, z + 0.16), fill, segs=10, bev=0)
    cy(0.123, 0.025, (x, y, z + 0.05), 'iron', segs=10, bev=0)


def pitchfork(x, y, lean=10, rot=0.0):
    with xf((x, y), rot):
        a = math.radians(lean)
        seg((0, 0, 0), (0, math.sin(a) * 1.3, math.cos(a) * 1.3), 0.018, 'wood_l')
        for k in (-1, 0, 1):
            seg((k * 0.05, math.sin(a) * 1.3, math.cos(a) * 1.3), (k * 0.05, math.sin(a) * 1.55, math.cos(a) * 1.55),
                0.008, 'iron')
        bx((0.14, 0.02, 0.02), (0, math.sin(a) * 1.3, math.cos(a) * 1.3), 'iron', bev=0)


def cheese_wheel(x, y, z, r=0.13, h=0.09, cut=False):
    cy(r, h, (x, y, z), 'yellow', segs=12, bev=0.012)
    cy(r * 1.01, h * 0.25, (x, y, z + h * 0.1), 'orange', segs=12, bev=0)


def flame(x, y, z, s=1.0, seed=0):
    """Stylised layered campfire flame (emissive): orange outer teardrops + yellow core."""
    R = rnd(seed)
    sp(0.26 * s, (x, y, z + 0.2 * s), 'fire', scale=(1, 1, 1.0), segs=12, rings=7)
    cy(0.22 * s, 0.5 * s, (x, y, z + 0.22 * s), 'fire', r_top=0.01, segs=12, bev=0)
    for k in range(4):
        a = math.tau * k / 4 + R.uniform(-0.3, 0.3)
        px, py = x + math.cos(a) * 0.17 * s, y + math.sin(a) * 0.17 * s
        h = R.uniform(0.22, 0.34) * s
        sp(0.11 * s, (px, py, z + 0.1 * s), 'fire', segs=8, rings=5)
        cy(0.1 * s, h, (px, py, z + 0.12 * s), 'fire', r_top=0.005, segs=8, bev=0)
    sp(0.16 * s, (x, y - 0.1 * s, z + 0.2 * s), 'ember', scale=(1, 1, 1.1), segs=10, rings=6)
    cy(0.13 * s, 0.32 * s, (x, y - 0.1 * s, z + 0.22 * s), 'ember', r_top=0.005, segs=10, bev=0)


def stall_awning(x, y, z, w, depth=0.7, drop=0.35, c1='red', c2='cream', n=7):
    """Striped awning (like K.awning) with only a thin snow line along the top edge."""
    ang = math.degrees(math.atan2(drop, depth))
    ln = math.hypot(depth, drop)
    sw = w / n
    for i in range(n):
        xx = x - w / 2 + sw * (i + 0.5)
        c = c1 if i % 2 == 0 else c2
        bx((sw + 0.004, ln, 0.05), (xx, y - depth / 2, z - drop / 2), c, rot=(ang, 0, 0), bev=0.01, origin='center')
        cy(sw / 2, 0.05, (xx, y - depth - 0.01, z - drop - 0.02), c, rot=(90, 0, 0), segs=10, origin='center', bev=0)
    for sd in (-1, 1):
        seg((x + sd * (w / 2 - 0.05), y, z - drop - 0.2), (x + sd * (w / 2 - 0.05), y - depth, z - drop), 0.015,
            'iron')
    snow(w - 0.2, ln * 0.22, 0.05, (x, y - depth * 0.1, z - drop * 0.1 + 0.03), rot=(ang, 0, 0), seed=n)


def straw_floor(x0, y0, x1, y1, n=10, seed=0):
    R = rnd(seed)
    for i in range(n):
        sp(R.uniform(0.15, 0.3), (R.uniform(x0, x1), R.uniform(y0, y1), K.FZ), 'straw', scale=(1.5, 1, 0.12),
           segs=8, rings=4)


# =========================================================================== 닭장 coop
@building('coop', '닭장', '생산', (8.6, 5.2))
def b_coop():
    ox, oy = -2.75, 0.5
    with xf((ox, oy)):
        sh = Shell(2.6, 2.3, H=1.95, seed=201, roof=('roof_r1', 'roof_r2'), shutter=None, curtain=None, over=0.35,
                   ridge=1.95 + 1.25)
        sh.door('S', -0.45, w=0.85, h=1.5, lantern_side=-1)
        sh.window('W', 0.2, w=0.5, h=0.45, zb=1.0, flowers=False)
        hatch(sh, 'E', -0.45, w=0.42, h=0.5, ramp=0.6)
        sh.walls(style='plank', cols=('plank', 'plank2'), trim='white')
        sh.floor(cols=('plank3', 'wood_m', 'plank2'))
        sh.roof(rows=4, gable_cols=('plank', 'plank2'))
        with grp('interior'), room('닭집'):
            # nest boxes on a shelf along the north wall
            with xf((0.15, sh.iy1 - 0.25, K.FZ)):
                for s in (-1, 1):
                    bx((0.06, 0.4, 0.45), (s * 0.78, 0, 0), 'wood_d', bev=0)
                bx((1.62, 0.42, 0.05), (0, 0, 0.42), 'wood_m', bev=0.01)
                for i in range(3):
                    xx = -0.52 + i * 0.52
                    bx((0.46, 0.38, 0.05), (xx, 0, 0.47), 'wood_l', bev=0.01)
                    for s in (-1, 1):
                        bx((0.04, 0.38, 0.3), (xx + s * 0.23, 0, 0.47), 'wood_l', bev=0)
                    bx((0.46, 0.04, 0.3), (xx, 0.18, 0.47), 'wood_l', bev=0)
                    bx((0.46, 0.04, 0.12), (xx, -0.18, 0.47), 'wood_l', bev=0)
                    sp(0.18, (xx, 0, 0.53), 'straw', scale=(1.1, 0.9, 0.3), segs=10, rings=5)
                    for k in range(1 + i % 2):
                        sp(0.04, (xx - 0.04 + k * 0.08, -0.02, 0.6), 'cream', scale=(0.85, 0.85, 1.1), segs=8,
                           rings=5)
                bx((1.62, 0.04, 0.05), (0, -0.2, 0.75), 'wood_m', bev=0)
                for k in range(2):
                    sp(0.18, (-0.5 + k * 0.9, 0, 0.0), 'straw', scale=(1.2, 1, 0.25), segs=8, rings=4)
            slot('work', 0.15, sh.iy1 - 0.85, 180)
            # roost ladder against the west wall
            with xf((sh.ix0 + 0.35, 0.05, K.FZ)):
                for s in (-1, 1):
                    seg((0.25, s * 0.45, 0), (-0.15, s * 0.45, 1.1), 0.03, 'wood_d')
                for i in range(3):
                    z = 0.35 + i * 0.3
                    xx = 0.25 - 0.4 * z / 1.1
                    seg((xx, -0.5, z), (xx, 0.5, z), 0.03, 'wood_l')
            F.sack(sh.ix1 - 0.3, sh.iy0 + 0.35, K.FZ, s=0.6, c='sack', flour=False)
            F.basket(sh.ix1 - 0.3, sh.iy1 - 0.75, K.FZ, fill='cream', seed=2, r=0.13)
            bucket(sh.ix0 + 0.35, sh.iy0 + 0.3, K.FZ, fill='blue_l')
            straw_floor(sh.ix0 + 0.2, sh.iy0 + 0.2, sh.ix1 - 0.2, sh.iy1 - 0.6, n=8, seed=4)
            slot('work', sh.ix1 - 0.3, sh.iy0 + 0.85, K.face(sh.ix1 - 0.3, sh.iy0 + 0.85, sh.ix1 - 0.3, sh.iy0 + 0.35))
        sh.hang('S', 0.45, 1.1, F.wall_shelf, w=0.5, items='jars')
        K.add_room('닭집', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(0.55, -sh.Dp / 2 - 0.02, 1.85, 'egg', w=0.45, h=0.34)
    # yard
    x0, x1, y0, y1 = -1.35, 4.15, -2.45, 2.45
    pen(x0, y0, x1, y1, gate_at=0.2, gate_w=0.95, skip=(oy - sh.Dp / 2 - 0.05, oy + sh.Dp / 2 + 0.05), seed=3,
        tufts=10)
    K.add_room('마당', x0, y0, x1, y1)
    with grp('exterior'), room('마당'):
        # feeder + water dish + scattered grain
        with xf((2.6, 1.5)):
            cy(0.22, 0.08, (0, 0, 0.02), 'wood_m', segs=12, bev=0.01)
            cy(0.12, 0.35, (0, 0, 0.1), 'steel', r_top=0.1, segs=10, bev=0)
            cy(0.16, 0.06, (0, 0, 0.45), 'red', r_top=0.04, segs=10, bev=0)
            sp(0.17, (0, 0, 0.08), 'wheat', scale=(1, 1, 0.2), segs=10, rings=4)
        slot('work', 2.6, 0.95, 180)
        cy(0.25, 0.08, (0.9, 1.8, 0.02), 'stone_l', segs=12, bev=0.01)
        cy(0.21, 0.01, (0.9, 1.8, 0.09), 'water', segs=12, bev=0)
        R = rnd(7)
        for i in range(14):
            sp(0.02, (2.0 + R.uniform(-0.8, 0.8), 0.6 + R.uniform(-0.6, 0.6), 0.03), 'wheat', segs=6, rings=3)
        # dust bath + a little straw stack
        sp(0.45, (3.2, -1.4, 0.0), DIRT2, scale=(1.3, 1, 0.08), segs=12, rings=4)
        with xf((-0.6, 2.0, 0.03), 90):
            F.hay_bale()
    yard_decor([('bush', -4.0, 2.2, 0.32, 4), ('snow', -3.9, -1.9, 0.3, 2), ('pot', -1.7, -1.3, 0, 1)])


# =========================================================================== 외양간 barn
@building('barn', '외양간', '생산', (13.0, 8.0))
def b_barn():
    ox, oy = -4.0, 0.6
    with xf((ox, oy)):
        sh = Shell(4.6, 4.2, H=2.5, seed=211, roof=('roof_g1', 'roof_g2'), shutter='white', curtain=None, over=0.45,
                   ridge=2.5 + 2.0)
        sh.door('S', -1.0, w=1.05, h=1.75, lantern_side=-1)
        sh.window('W', 0.4, w=0.6, flowers=False)
        sh.window('N', -1.1, w=0.6, flowers=False)
        sh.window('S', 0.9, w=0.6, flowers=True)
        hatch(sh, 'E', -0.3, w=1.5, h=1.95)
        sh.walls(style='plank', cols=('red', 'red_d'), trim='white')
        sh.floor(cols=('plank3', 'wood_m', 'plank2'), along='Y')
        sh.roof(rows=7, gable_cols=('red', 'red_d'))
        with grp('interior'), room('외양간'):
            # stall partitions + long feed trough along the north wall
            for xx in (-0.55, 0.85):
                with xf((xx, sh.iy1 - 0.7, K.FZ)):
                    bx((0.08, 1.3, 1.0), (0, 0, 0), 'wood_m', bev=0.01)
                    bx((0.12, 0.12, 1.25), (0, -0.65, 0), 'wood_d', bev=0.015)
            with xf((0.3, sh.iy1 - 0.3, K.FZ)):
                bx((3.4, 0.4, 0.45), (0, 0, 0), 'wood_d', bev=0.02)
                bx((3.3, 0.3, 0.05), (0, 0, 0.42), 'straw', bev=0.01)
                R = rnd(3)
                for i in range(7):
                    sp(0.14, (-1.5 + i * 0.5, R.uniform(-0.05, 0.05), 0.46), 'straw', scale=(1.4, 1, 0.6), segs=8,
                       rings=4)
            slot('work', 1.55, sh.iy1 - 0.95, 180)            # filling the trough
            # milking corner: stool + bucket (cow stands at the middle stall)
            put(F.stool, 0.55, -0.15, 90, sit=False, h=0.26)
            bucket(0.18, -0.1, K.FZ)
            slot('work', 0.55, -0.15, 270)                     # 우유 짜는 자리
            milk_can(sh.ix0 + 0.25, sh.iy0 + 0.3, K.FZ)
            milk_can(sh.ix0 + 0.55, sh.iy0 + 0.25, K.FZ, s=0.9)
            for i, (x, y, z, r) in enumerate(((sh.ix0 + 0.45, 0.3, 0, 90), (sh.ix0 + 0.45, 1.05, 0, 90),
                                              (sh.ix0 + 0.45, 0.65, 0.4, 90))):
                with xf((x, y, K.FZ + z), r):
                    F.hay_bale()
            pitchfork(sh.ix0 + 0.95, sh.iy0 + 0.15, lean=-12)
            straw_floor(-1.5, -1.6, 1.8, 1.2, n=12, seed=6)
            F.table_lamp(sh.ix1 - 0.35, sh.iy0 + 0.3, K.FZ + 0.45)
            put(F.crate_in, sh.ix1 - 0.35, sh.iy0 + 0.3, 0, s=0.45)
        sh.hang('W', -1.1, 1.0, F.tool_rack, w=1.0, tools=('rake', 'shovel', 'rake'))
        sh.hang('N', 1.75, 1.5, F.picture, w=0.35, h=0.28, art=('leaf_l', 'blue_l', 'cream'))
        K.add_room('외양간', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(-0.1, -sh.Dp / 2 - 0.02, 2.35, 'cow', w=0.5, h=0.36)
    x0, x1, y0, y1 = -1.55, 6.4, -3.9, 3.9
    pen(x0, y0, x1, y1, gate_at=0.6, gate_w=1.2, skip=(oy - sh.Dp / 2 - 0.05, oy + sh.Dp / 2 + 0.05), seed=5,
        ground=(GRASS, GRASS2), tufts=16)
    K.add_room('목장', x0, y0, x1, y1)
    with grp('exterior'), room('목장'):
        trough(4.2, 3.4, 0, L=1.6, fill='water')
        slot('work', 4.2, 2.8, 0 + 180)
        hay_rack(1.8, 3.35, 0, L=1.3)
        slot('work', 1.8, 2.75, 180)
        with xf((5.5, -3.0)):
            bx((0.25, 0.25, 0.2), (0, 0, 0), 'stone_l', bev=0.03)
            bx((0.18, 0.18, 0.12), (0, 0, 0.2), 'cream', bev=0.03)    # salt lick
        for i, (x, y) in enumerate(((3.0, -0.6), (4.9, 0.9), (2.0, -2.6))):
            blob(0.18, (x, y, 0.02), 'straw', scale=(1.5, 1, 0.35), seed=i, subdiv=1)
    yard_decor([('barrel', -6.1, -2.8, 0, 1), ('bush', -6.2, 3.3, 0.35, 4), ('snow', -2.2, 3.4, 0.35, 2),
                ('path', -5.0, -1.6, 3, 7)])
    with grp('exterior'):
        milk_can(-2.3, -1.85)
        milk_can(-2.0, -2.0, s=0.9)


# =========================================================================== 양 우리 sheepfold
@building('sheepfold', '양 우리', '생산', (11.0, 6.0))
def b_sheepfold():
    ox, oy = -3.3, 0.6
    with xf((ox, oy)):
        sh = Shell(4.0, 3.2, H=2.1, seed=221, roof=('roof_b1', 'roof_b2'), shutter='red', curtain=None, over=0.4,
                   ridge=2.1 + 1.55)
        sh.door('S', -0.9, w=0.95, h=1.6, lantern_side=-1)
        sh.window('W', 0.0, w=0.55, flowers=False)
        sh.window('S', 0.85, w=0.55, flowers=True)
        hatch(sh, 'E', 0.1, w=1.2, h=1.25)
        sh.walls(style='plank', cols=('pale', 'pale2'), trim='wood_d')
        sh.floor(cols=('plank', 'plank2', 'plank3'))
        sh.roof(rows=5, gable_cols=('pale', 'pale2'))
        with grp('interior'), room('털 깎는 곳'):
            # shearing platform + a big pile of wool + shears
            with xf((0.3, 0.45, K.FZ)):
                bx((1.3, 1.0, 0.12), (0, 0, 0), 'wood_l', bev=0.02)
                for s in (-1, 1):
                    bx((1.3, 0.06, 0.25), (0, s * 0.5, 0.12), 'wood_m', bev=0.01)
            slot('work', 0.3, -0.35, 0 + 180)                   # 털 깎는 자리
            put(F.stool, -0.55, -0.3, 30, sit=False, h=0.28)
            with xf((-0.55, -0.3, K.FZ + 0.28)):
                for s in (-1, 1):
                    seg((0, 0, 0.02), (s * 0.04, -0.2, 0.02), 0.012, 'steel')
                sp(0.03, (0, 0, 0.02), 'red', segs=6, rings=4)
            R = rnd(4)
            for i in range(6):
                sp(R.uniform(0.14, 0.22), (sh.ix1 - 0.45 + R.uniform(-0.2, 0.2), sh.iy1 - 0.45 + R.uniform(-0.2, 0.2),
                                           K.FZ + 0.06 + i * 0.05), 'cream', scale=(1.3, 1.1, 0.7), segs=10,
                   rings=6)
            for i in range(2):
                F.basket(sh.ix0 + 0.35, sh.iy1 - 0.35 - i * 0.45, K.FZ, fill='cream', seed=i, r=0.17)
            F.sack(sh.ix0 + 0.35, sh.iy0 + 0.4, K.FZ, s=0.7, c='canvas', flour=False)
            with xf((sh.ix1 - 0.4, sh.iy0 + 0.5, K.FZ), 90):
                F.hay_bale()
            slot('work', sh.ix1 - 0.95, sh.iy1 - 0.5, 90)      # wool bundling
        sh.hang('N', -1.0, 1.0, F.tool_rack, w=0.8, tools=('scythe', 'rake'))
        K.add_room('털 깎는 곳', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(0.0, -sh.Dp / 2 - 0.02, 1.95, 'wool', w=0.45, h=0.34)
    x0, x1, y0, y1 = -1.4, 5.4, -2.9, 2.9
    pen(x0, y0, x1, y1, gate_at=0.7, gate_w=1.1, skip=(oy - sh.Dp / 2 - 0.05, oy + sh.Dp / 2 + 0.05), seed=9,
        ground=(GRASS, GRASS2), tufts=14)
    K.add_room('우리 마당', x0, y0, x1, y1)
    with grp('exterior'), room('우리 마당'):
        hay_rack(3.4, 2.4, 0, L=1.1)
        slot('work', 3.4, 1.8, 180)
        trough(1.2, 2.45, 0, L=1.1, fill='water')
        with xf((4.5, -1.8), 20):
            F.hay_bale()
    yard_decor([('snow', -5.1, 2.4, 0.35, 3), ('bush', -5.2, -2.3, 0.3, 4), ('crate', -1.85, -2.35, 10, 2)])


# =========================================================================== 돼지우리 pigsty
@building('pigsty', '돼지우리', '생산', (9.0, 5.2))
def b_pigsty():
    ox, oy = -2.75, 0.55
    with xf((ox, oy)):
        sh = Shell(3.0, 2.6, H=1.75, seed=231, roof=('roof_t1', 'roof_t2'), shutter=None, curtain=None, over=0.35,
                   ridge=1.75 + 1.2)
        sh.door('S', -0.6, w=0.85, h=1.45, lantern_side=-1)
        sh.window('W', 0.1, w=0.5, h=0.45, zb=0.95, flowers=False)
        hatch(sh, 'E', -0.2, w=0.8, h=0.8)
        sh.walls(style='stone', cols=('stone', 'stone_d', 'stone_l', 'stone_w'))
        with grp('floor'):
            K.stone_floor(-sh.Wd / 2, -sh.Dp / 2, sh.Wd / 2, sh.Dp / 2, seed=5)
        sh.roof(rows=4, gable_cols=('stone', 'stone_d', 'stone_l', 'stone_w'))
        with grp('interior'), room('돼지집'):
            with xf((0.45, 0.5, K.FZ)):
                F.hay_pile(1.6, 1.1, 0.35, seed=2)
            put(F.barrel_in, sh.ix0 + 0.3, sh.iy1 - 0.3, 0, r=0.2, h=0.5)
            F.sack(sh.ix0 + 0.3, sh.iy1 - 0.85, K.FZ, s=0.6, c='sack', flour=False)
            bucket(sh.ix0 + 0.35, sh.iy0 + 0.35, K.FZ, fill='bread')
            slot('work', sh.ix0 + 0.8, sh.iy1 - 0.5, 270)
            F.broom(sh.ix1 - 0.2, sh.iy0 + 0.25, lean=-10)
        K.add_room('돼지집', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(0.35, -sh.Dp / 2 - 0.02, 1.65, 'pig', w=0.42, h=0.32)
    x0, x1, y0, y1 = -1.15, 4.45, -2.5, 2.5
    pen(x0, y0, x1, y1, gate_at=0.0, gate_w=0.95, skip=(oy - sh.Dp / 2 - 0.05, oy + sh.Dp / 2 + 0.05), seed=11,
        ground=(DIRT, DIRT2), tufts=6)
    K.add_room('진흙 마당', x0, y0, x1, y1)
    with grp('floor'):
        # mud puddles
        sp(1.0, (2.3, 0.4, 0.02), MUD, scale=(1.3, 0.95, 0.03), segs=20, rings=5)
        sp(0.5, (3.4, -0.9, 0.02), MUD, scale=(1.2, 1, 0.03), segs=14, rings=4)
        for i, (x, y) in enumerate(((1.6, 0.0), (2.9, 1.0), (2.2, 0.9))):
            sp(0.12, (x, y, 0.04), '#5A3C26', scale=(1.3, 1, 0.3), segs=8, rings=4)
    with grp('exterior'), room('진흙 마당'):
        trough(1.4, -2.05, 0, L=1.3, fill='bread')
        slot('work', 1.4, -2.95, 0 + 180)               # feeding over the fence (outside the pen)
        cy(0.25, 0.08, (3.9, 2.0, 0.02), 'stone_l', segs=12, bev=0.01)
        cy(0.21, 0.01, (3.9, 2.0, 0.09), 'water', segs=12, bev=0)
        with xf((-0.6, 2.1, 0.0), 0):
            F.hay_bale()
    yard_decor([('barrel', -4.2, -2.1, 0, 2), ('snow', -4.2, 2.1, 0.3, 3)])


# =========================================================================== 과수원 orchard
@building('orchard', '과수원', '생산', (9.6, 8.4))
def b_orchard():
    ox, oy = -3.3, 2.4
    with xf((ox, oy)):
        sh = Shell(2.6, 2.2, H=1.95, seed=241, roof=('roof_r1', 'roof_r2'), shutter='green', curtain=None, over=0.35,
                   ridge=1.95 + 1.2)
        sh.door('S', -0.35, w=0.85, h=1.5, lantern_side=1)
        sh.window('E', 0.0, w=0.5, flowers=True)
        sh.walls()
        sh.floor()
        sh.roof(rows=4)
        with grp('interior'), room('사과 창고'):
            for i, (x, y) in enumerate(((sh.ix1 - 0.3, sh.iy1 - 0.3), (sh.ix1 - 0.3, sh.iy1 - 0.8),
                                        (sh.ix1 - 0.8, sh.iy1 - 0.3))):
                put(F.crate_in, x, y, 0, s=0.42, fill='red', seed=i)
            put(F.crate_in, sh.ix1 - 0.3, sh.iy1 - 0.3, 10, s=0.36, fill='red', seed=5, z=K.FZ + 0.42)
            for i in range(3):
                F.basket(sh.ix0 + 0.3, sh.iy1 - 0.3 - i * 0.38, K.FZ, fill='red', seed=i, r=0.14)
            put(F.workbench, -0.15, sh.iy0 + 0.35, 180, w=0.9, d=0.45, vise=False, items=False, act=None)
            slot('work', -0.15, sh.iy0 + 0.85, 0)
            with xf((sh.ix0 + 0.15, sh.iy0 + 0.6, K.FZ), 0):
                for s in (-1, 1):
                    seg((0, s * 0.2, 0), (0.1, s * 0.2, 1.5), 0.025, 'wood_l')
                for i in range(5):
                    z = 0.25 + i * 0.28
                    seg((z / 15, -0.2, z), (z / 15, 0.2, z), 0.015, 'wood_m')
        K.add_room('사과 창고', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(0.45, -sh.Dp / 2 - 0.02, 1.85, 'apple', w=0.42, h=0.32)
    # 9 trees in rows (each its own node tree_N)
    K.add_room('과수원', -1.7, -4.2, 4.8, 4.2)
    trees = []
    n = 0
    with room('과수원'):
        for j, y in enumerate((2.6, 0.0, -2.6)):
            for i, x in enumerate((-0.6, 1.6, 3.8)):
                n += 1
                key = 'tree_%d' % n
                apple_tree(key, x, y, seed=40 + n, s=0.95 + 0.06 * ((i + j) % 3))
                trees.append(dict(id=key, pos=[x, y]))
                with grp('exterior'):
                    slot('work', x - 0.25, y - 0.95, K.face(x - 0.25, y - 0.95, x, y))
    K.S.extra['trees'] = trees
    with grp('floor'):
        for y in (2.6, 0.0, -2.6):
            bx((7.0, 1.3, 0.025), (1.6, y, 0), GRASS, bev=0.01)
    with grp('exterior'):
        # harvest cart + ladder + baskets on the path
        with xf((-3.0, -1.6), 90):
            bx((1.0, 0.65, 0.3), (0, 0, 0.32), 'wood_l', bev=0.02)
            for s in (-1, 1):
                cy(0.26, 0.06, (0.15, s * 0.38, 0.26), 'wood_m', rot=(90, 0, 0), segs=12, origin='center')
            seg((-0.5, 0, 0.45), (-1.1, 0, 0.35), 0.025, 'wood_d')
            for i in range(7):
                sp(0.065, (-0.3 + (i % 4) * 0.18, -0.12 + (i // 4) * 0.22, 0.64), 'red', segs=8, rings=5)
        for i in range(3):
            F.basket(-2.2 + i * 0.35, -3.2, 0.0, fill='red', seed=i + 4, r=0.15)
        with xf((-2.0, 0.6), 0):
            for s in (-1, 1):
                seg((s * 0.2, 0, 0), (s * 0.2, 0.3, 1.6), 0.025, 'wood_l')
            for i in range(5):
                z = 0.25 + i * 0.3
                seg((-0.2, z * 0.19, z), (0.2, z * 0.19, z), 0.015, 'wood_m')
        # low border logs
        for x, y, ln, r in ((1.6, -4.0, 6.4, 90), (4.75, 0.0, 7.8, 0)):
            K.log_(0.07, ln, (x, y, 0.07), (0, 90, 0) if r == 90 else (90, 0, 0), 'bark')
    yard_decor([('snow', -4.4, -3.8, 0.3, 3), ('path', -3.65, oy - 1.9, 3, 7)])
    fx('fx_bees', 1.6, 0.0, 2.2)


# =========================================================================== 양봉장 apiary
@building('apiary', '양봉장', '생산', (8.4, 6.4))
def b_apiary():
    ox, oy = -2.75, 1.4
    with xf((ox, oy)):
        sh = Shell(2.6, 2.3, H=1.95, seed=251, roof=('roof_t1', 'roof_t2'), shutter='yellow', curtain='white',
                   over=0.35, ridge=1.95 + 1.2)
        sh.door('S', -0.4, w=0.85, h=1.5, lantern_side=1)
        sh.window('E', 0.1, w=0.5, flowers=True)
        sh.window('W', 0.1, w=0.5, flowers=False)
        sh.walls(style='plank', cols=('mustard', 'yellow'), trim='white')
        sh.floor()
        sh.roof(rows=4, gable_cols=('mustard', 'yellow'))
        with grp('interior'), room('꿀 방'):
            # honey extractor (drum with crank)
            with xf((0.35, 0.45, K.FZ)):
                cy(0.3, 0.6, (0, 0, 0), 'steel', segs=14, bev=0.01)
                cy(0.31, 0.04, (0, 0, 0.58), 'stone_d', segs=14, bev=0)
                seg((0, 0, 0.62), (0, 0, 0.78), 0.02, 'iron')
                seg((0, 0, 0.78), (0.18, 0, 0.78), 0.015, 'iron')
                seg((0.18, 0, 0.78), (0.18, 0, 0.88), 0.02, 'wood_d')
                seg((0, -0.3, 0.12), (0, -0.4, 0.1), 0.02, 'iron')
            bucket(0.35, -0.05, K.FZ, fill='orange')
            slot('work', 0.35, -0.3, 180)                       # 꿀 짜는 자리
            with xf((sh.ix0 + 0.25, 0.3, K.FZ), 270):
                bx((1.2, 0.35, 0.05), (0, 0, 0.45), 'wood_l', bev=0.01)
                bx((1.2, 0.35, 0.05), (0, 0, 0.95), 'wood_l', bev=0.01)
                for s in (-1, 1):
                    bx((0.05, 0.35, 1.25), (s * 0.58, 0, 0), 'wood_m', bev=0)
                for z in (0.5, 1.0):
                    for i in range(5):
                        cy(0.06, 0.13, (-0.45 + i * 0.22, 0, z), 'orange', segs=8, bev=0)
                        cy(0.065, 0.02, (-0.45 + i * 0.22, 0, z + 0.13), 'canvas', segs=8, bev=0)
            slot('work', sh.ix0 + 0.75, 0.3, 270)
            with xf((sh.ix1 - 0.35, sh.iy1 - 0.35, K.FZ)):
                F.crate_in(0.45, fill='orange', seed=3)
            # smoker + spare frames
            cy(0.07, 0.18, (sh.ix1 - 0.3, sh.iy0 + 0.3, K.FZ), 'copper', segs=8, bev=0)
            for i in range(3):
                bx((0.4, 0.03, 0.25), (sh.ix1 - 0.6, sh.iy0 + 0.25 + i * 0.06, K.FZ), 'yellow', rot=(8, 0, 0),
                   bev=0)
        sh.hang('N', 0.4, 1.3, F.wall_shelf, w=0.6, items='jars')
        K.add_room('꿀 방', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(0.45, -sh.Dp / 2 - 0.02, 1.85, 'honey', w=0.42, h=0.32)
    K.add_room('벌통 마당', -1.0, -3.0, 4.1, 3.1)
    with grp('exterior'), room('벌통 마당'):
        k = 0
        for j, y in enumerate((1.5, -0.4)):
            for i, x in enumerate((0.0, 1.5, 3.0)):
                beehive(x, y, rot=0, seed=k, stack=2 + (k % 2))
                if j == 1 or i != 1:
                    pass
                k += 1
        for x in (0.0, 1.5, 3.0):
            slot('work', x + 0.45, -1.1, K.face(x + 0.45, -1.1, x, -0.4))
        fx('fx_bees', 1.5, 1.5, 1.4)
        fx('fx_bees', 1.5, -0.4, 1.4)
    flower_bed(-1.0, -2.95, 4.0, -2.15, seed=3)
    flower_bed(-1.0, 2.35, 4.0, 3.05, seed=5, cols=('purple', 'pink', 'white', 'purple'))
    flower_bed(-4.0, -1.6, -1.6, -0.9, seed=8)
    with grp('exterior'):
        for i in range(3):
            K.flower_pot(-1.5 + i * 0.35, -0.2, 0.0, seed=i, fc=('yellow', 'red', 'pink')[i], s=1.1)
    yard_decor([('path', ox - 0.4, oy - 1.9, 2, 5), ('bush', 3.9, -0.4, 0.3, 4)])


# =========================================================================== 낚시터 fishing
@building('fishing', '낚시터', '생산', (6.4, 10.0))
def b_fishing():
    ox, oy = 0.3, 3.15
    with xf((ox, oy)):
        sh = Shell(3.2, 2.6, H=2.0, seed=261, roof=('roof_b1', 'roof_b2'), shutter='blue', curtain='white',
                   over=0.4, ridge=2.0 + 1.3)
        sh.door('S', -0.35, w=0.9, h=1.55, lantern_side=1)
        sh.window('E', 0.0, w=0.55, flowers=False)
        sh.window('W', 0.0, w=0.55, flowers=False)
        sh.walls(logs=('log2', 'log1', 'log3'))
        sh.floor()
        sh.roof(rows=5, chimneys=[(1.05, 0.75)])
        with grp('interior'), room('어부 오두막'):
            put(F.stove, sh.ix1 - 0.4, sh.iy1 - 0.35, 0)
            put(F.bench_in, -0.7, sh.iy1 - 0.3, 180, length=1.1, cushion='blue', n=2)
            with xf((sh.ix0 + 0.35, -0.2, K.FZ), 270):
                F.barrel_in(0.22, 0.55)
            with xf((sh.ix0 + 0.35, 0.35, K.FZ), 270):
                F.crate_in(0.42, fill='blue_l', seed=2)
            # net mending spot: low stool + net pile
            put(F.stool, 0.4, 0.05, 180, sit=False, h=0.28)
            sp(0.35, (0.4, -0.45, K.FZ), 'teal', scale=(1.2, 0.8, 0.35), segs=12, rings=6)
            for i in range(4):
                sp(0.05, (0.15 + i * 0.17, -0.45, K.FZ + 0.1), 'orange', segs=6, rings=4)
            slot('work', 0.4, 0.05, 0)
        sh.hang('W', 0.8, 1.0, F.wall_shelf, w=0.6, items='jars')
        sh.hang('N', -0.7, 1.25, F.picture, w=0.45, h=0.32, art=('blue_l', 'blue', 'cream'))
        K.add_room('어부 오두막', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    with grp('walls~'), xf((ox, oy)):
        my_sign(0.6, -sh.Dp / 2 - 0.02, 1.95, 'fish', w=0.45, h=0.34)
    # pier sticking out toward -Y (over the water)
    DZ = 0.32
    y_root, y_end = 0.95, -4.6
    with grp('floor'):
        R = rnd(5)
        y = y_root
        while y > y_end - 1e-3:
            bx((1.5, 0.2, 0.07), (0.0 + R.uniform(-0.02, 0.02), y - 0.1, DZ - 0.07), R.choice(['plank', 'plank2',
                                                                                                'wood_l']),
               bev=0.012)
            y -= 0.22
        # wider T at the end
        for i in range(6):
            bx((2.8, 0.2, 0.07), (0, y_end + 0.5 - i * 0.22 + 0.02, DZ - 0.07 + 0.001), R.choice(['plank', 'plank2']),
               bev=0.012)
        bx((1.6, 0.35, 0.16), (0, y_root + 0.1, 0.0), 'stone_l', bev=0.03)        # step up to the deck
        K.stone_floor(-1.0, y_root + 0.28, 1.6, 1.8, seed=9, z0=-0.1)              # landing in front of the hut
    with grp('exterior'):
        for y in (y_root - 0.3, 0.0, -1.6, -3.2, y_end + 0.4, y_end - 0.15):
            for s in (-1, 1):
                xx = s * (0.7 if y > y_end + 0.45 else 1.32)
                cy(0.09, DZ + 0.8, (xx, y, -0.8), 'wood_d', segs=8, bev=0)
        for y in (-1.6, y_end - 0.15):
            for s in (-1, 1):
                xx = s * (0.7 if y > y_end + 0.45 else 1.32)
                cy(0.1, 0.35, (xx, y, DZ), 'wood_dd', segs=8, bev=0)       # bollards
                snowcap(0.09, (xx, y, DZ + 0.35), 0.04, seed=int(y * 10) + s)
        # rope railing on one side
        for y0, y1 in ((y_root - 0.3, 0.0), (0.0, -1.6), (-1.6, -3.2)):
            seg((0.7, y0, DZ + 0.55), (0.7, y1, DZ + 0.55), 0.015, 'rope')
        for y in (y_root - 0.3, 0.0, -3.2):
            cy(0.05, 0.6, (0.7, y, DZ), 'wood_m', segs=6, bev=0)
        # fishing spot at the end: stool, bucket, rods
        for k, x in enumerate((-0.6, 0.6)):
            slot('work', x, y_end - 0.15, 0, z=DZ)
            with xf((x + 0.25, y_end - 0.1, DZ)):
                seg((0, 0.1, 0.05), (0.1, -1.0, 1.0), 0.012, 'wood_l')
        bucket(0.0, y_end + 0.15, DZ, fill='blue_l')
        for i in range(2):
            sp(0.04, (0.0 + (i - 0.5) * 0.06, y_end + 0.15, DZ + 0.19), 'blue_l', scale=(0.5, 1.5, 0.6), segs=6,
               rings=4)
        put(F.stool, -1.1, y_end + 0.1, 0, sit=False, h=0.28, z=DZ)
        K.lantern(-0.7, y_end - 0.15, DZ + 1.35, bracket=False)
        cy(0.035, 1.25, (-0.7, y_end - 0.15, DZ), 'wood_d', segs=6, bev=0)
        # rowboat tied beside the pier (floating at z ~ 0)
        with xf((-1.65, -1.0), 90):
            prof = [(-0.85, 0.0), (0.85, 0.0)]
            bx((1.6, 0.6, 0.28), (0, 0, -0.08), 'red', taper=(1.15, 1.2), bev=0.05, seg=2)
            bx((1.45, 0.48, 0.05), (0, 0, 0.16), 'wood_l', bev=0)
            bx((0.12, 0.62, 0.05), (0.2, 0, 0.18), 'wood_m', bev=0)
            seg((-0.2, 0.25, 0.22), (0.5, 0.45, 0.22), 0.02, 'wood_l')
            del prof
        seg((-1.2, -1.0, 0.1), (-0.72, -1.0, DZ), 0.012, 'rope')
        # drying rack with fish beside the hut
        with xf((-2.3, 1.2), 90):
            for s in (-1, 1):
                seg((s * 0.6, -0.2, 0), (s * 0.6, 0, 1.1), 0.03, 'wood_d')
                seg((s * 0.6, 0.2, 0), (s * 0.6, 0, 1.1), 0.03, 'wood_d')
            seg((-0.7, 0, 1.1), (0.7, 0, 1.1), 0.025, 'wood_l')
            for i in range(5):
                xx = -0.45 + i * 0.22
                seg((xx, 0, 1.1), (xx, 0, 0.95), 0.006, 'rope')
                sp(0.05, (xx, 0, 0.85), ('blue_l', 'orange', 'stone_l')[i % 3], scale=(0.5, 0.7, 1.6), segs=6,
                   rings=4)
        put(F.crate_in, 2.2, 1.0, 15, s=0.5, z=0.0, fill='blue_l', seed=4)
        put(F.barrel_in, 2.35, 1.75, 0, r=0.24, h=0.6, z=0.0)
        with xf((1.5, 0.9)):
            for i in range(3):
                cy(0.2 - i * 0.02, 0.05, (0, 0, i * 0.05), 'rope', segs=12, bev=0)
    K.add_room('부두', -1.4, y_end - 0.4, 1.4, y_root)
    K.S.door['out'] = [-0.05, 1.25]
    K.S.extra['pier'] = dict(root=[0.0, y_root], end=[0.0, round(y_end - 0.4, 2)], deck_z=DZ, water='-Y')
    yard_decor([('snow', 2.6, 4.3, 0.35, 2), ('bush', -2.6, 4.2, 0.3, 4)])


# =========================================================================== 치즈 공방 dairy
@building('dairy', '치즈 공방', '생산', (6.6, 5.6))
def b_dairy():
    sh = Shell(5.6, 4.3, H=2.35, seed=271, roof=('roof_b1', 'roof_b2'), shutter='blue', curtain='cream', over=0.45)
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', 1.5, w=0.95)
    sh.window('S', -0.6, w=0.7)
    sh.window('S', -2.0, w=0.55)
    sh.window('E', 0.3, w=0.6)
    sh.window('N', 0.4, w=0.6, flowers=False)
    sh.walls(style='stone', cols=('stone_w', 'stone', 'stone_l', 'cream'))
    sh.floor(cols=('plank', 'plank2', 'plank3'))
    sh.roof(chimneys=[(-1.9, 1.35)], rows=6, gable_cols=('stone_w', 'stone', 'stone_l', 'cream'))
    K.add_room('공방', sh.ix0, sh.iy0, sh.ix1, sh.iy1)
    with grp('interior'), room('공방'):
        # big copper cauldron on a brick hearth (back left, under the chimney)
        with xf((-1.85, 1.15, K.FZ)):
            for i in range(10):
                a = math.tau * i / 10
                bx((0.26, 0.18, 0.4), (math.cos(a) * 0.5, math.sin(a) * 0.5, 0), ('brick', 'brick_d')[i % 2],
                   rot=(0, 0, math.degrees(a) + 90), bev=0.02)
            sp(0.12, (0, -0.48, 0.12), 'fire', scale=(1.2, 0.6, 0.9), segs=8, rings=5)
            cy(0.55, 0.45, (0, 0, 0.4), 'copper', r_top=0.6, segs=18, bev=0.02)
            cy(0.56, 0.04, (0, 0, 0.83), 'cream', segs=18, bev=0)
            seg((0.1, 0, 0.85), (0.35, 0.2, 1.4), 0.02, 'wood_l')
            fx('fx_fire', 0, -0.45, 0.15)
        slot('cook', -1.85, 0.25, 180)
        # cheese shelves along the north wall (wheels)
        with xf((0.9, sh.iy1 - 0.25, K.FZ)):
            for s in (-1, 1):
                bx((0.06, 0.4, 1.6), (s * 0.85, 0, 0), 'wood_d', bev=0.01)
            for k, z in enumerate((0.35, 0.8, 1.25)):
                bx((1.76, 0.4, 0.05), (0, 0, z), 'wood_l', bev=0.01)
                for i in range(4):
                    cheese_wheel(-0.6 + i * 0.4, 0, z + 0.05, r=0.15 if (i + k) % 2 else 0.13)
        slot('work', 0.9, sh.iy1 - 0.85, 180)
        # press + work table
        put(F.workbench, 0.6, -0.3, 0, w=1.3, d=0.6, vise=False, items=False)
        with xf((0.6, -0.3, K.FZ + 0.55)):
            cheese_wheel(-0.35, 0.05, 0.0, r=0.16, h=0.1)
            extr([(-0.0, 0.0), (0.16, 0.0), (0.0, 0.1)], 0.09, loc=(0.1, 0.05, 0.0), rot=(0, 0, 0), c='yellow')
            bx((0.25, 0.25, 0.25), (0.35, 0.05, 0.0), 'wood_m', bev=0.02)     # press
            seg((0.35, 0.05, 0.25), (0.35, 0.05, 0.55), 0.025, 'iron')
            seg((0.2, 0.05, 0.55), (0.5, 0.05, 0.55), 0.02, 'wood_d')
        # milk cans + butter churn
        for i, (x, y) in enumerate(((sh.ix1 - 0.3, sh.iy1 - 0.3), (sh.ix1 - 0.6, sh.iy1 - 0.25),
                                    (sh.ix1 - 0.3, sh.iy1 - 0.65))):
            milk_can(x, y, K.FZ, s=0.95)
        with xf((sh.ix1 - 0.35, -0.3, K.FZ)):
            cy(0.17, 0.55, (0, 0, 0), 'wood_l', r_top=0.13, segs=12, bev=0.01)
            cy(0.18, 0.04, (0, 0, 0.12), 'iron', segs=12, bev=0)
            seg((0, 0, 0.55), (0, 0, 0.9), 0.015, 'wood_d')
        slot('work', sh.ix1 - 0.85, -0.3, 90)
        # small sales counter by the door
        put(F.round_set, -0.9, -0.95, 0, r=0.38, n=2, start=90, seat='blue', seed=4, cloth='cream')
        put(F.cupboard, sh.ix0 + 0.25, -0.5, 90, w=0.85, seed=3)
    sh.hang('W', 0.8, 1.35, F.wall_shelf, w=0.7, items='jars')
    sh.hang('E', -1.2, 1.4, F.clock)
    with grp('walls~'):
        my_sign(0.6, -D / 2 - 0.02, 2.25, 'cheese', w=0.5, h=0.36)
    with grp('exterior'):
        for i, x in enumerate((2.9, 3.15, 2.95)):
            milk_can(x, -D / 2 - 0.4 - (i == 2) * 0.3, 0.0, s=0.95)
        bx((1.0, 0.45, 0.1), (-1.4, -D / 2 - 0.45, 0.4), 'wood_m', bev=0.02)        # bench
        for s in (-1, 1):
            bx((0.1, 0.35, 0.4), (-1.4 + s * 0.4, -D / 2 - 0.45, 0), 'wood_d', bev=0.01)
        cheese_wheel(-1.55, -D / 2 - 0.45, 0.5, r=0.14)
        cheese_wheel(-1.2, -D / 2 - 0.45, 0.5, r=0.12)
    yard_decor([('bush', -3.0, -2.6, 0.32, 3), ('snow', 3.0, 2.4, 0.35, 2), ('pot', 0.55, -D / 2 - 0.45, 0, 2)])


# =========================================================================== 봄의 봉화대 beacon
def square_tower(w0, w1, z0, H, openings, course=0.42, seed=0, cols=('stone_w', 'stone', 'stone_l', 'stone_d'),
                 th=0.34):
    """Tapering square stone shaft (grp current).  openings: (side, off, half_w, zb, zt)."""
    R = rnd(seed)
    z = 0.0
    k = 0
    while z < H - 0.01:
        f = z / H
        w = w0 + (w1 - w0) * f
        for side in 'SNEW':
            xw = side in 'SN'
            half = w / 2 + (th / 2 if (k + xw) % 2 else -th / 2)
            holes = [(o[1] - o[2], o[1] + o[2]) for o in openings if o[0] == side and z + course * 0.5 > o[3]
                     and z < o[4]]
            segs = K._subtract(-half, half, holes)
            for a, b in segs:
                x = a
                while x < b - 0.05:
                    ln = min(b - x, R.uniform(0.55, 0.95))
                    if b - (x + ln) < 0.3:
                        ln = b - x
                    mid = x + ln / 2
                    sz = (ln - 0.02, th + R.uniform(-0.01, 0.03), course - 0.02)
                    if side == 'S':
                        bx(sz, (mid, -w / 2, z0 + z), R.choice(cols), bev=0.05)
                    elif side == 'N':
                        bx(sz, (mid, w / 2, z0 + z), R.choice(cols), bev=0.05)
                    elif side == 'E':
                        bx((sz[1], sz[0], sz[2]), (w / 2, mid, z0 + z), R.choice(cols), bev=0.05)
                    else:
                        bx((sz[1], sz[0], sz[2]), (-w / 2, mid, z0 + z), R.choice(cols), bev=0.05)
                    x += ln
        z += course
        k += 1
    return z0 + z


def banner_string(p0, p1, n=8, sag=0.5, seed=0):
    R = rnd(seed)
    p0, p1 = Vector(p0), Vector(p1)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(p0 + (p1 - p0) * t + Vector((0, 0, -sag * 4 * t * (1 - t))))
    for a, b in zip(pts, pts[1:]):
        seg(tuple(a), tuple(b), 0.008, 'rope')
    cols = ['red', 'yellow', 'blue_l', 'pink', 'green', 'orange']
    d = (p1 - p0)
    ang = math.degrees(math.atan2(d.y, d.x))
    for i, p in enumerate(pts[1:-1]):
        extr([(-0.09, 0.0), (0.09, 0.0), (0.0, -0.2)], 0.01, loc=(p.x, p.y, p.z), rot=(90, 0, ang),
             c=cols[(i + seed) % len(cols)], bev=0)


@building('beacon', '봄의 봉화대', '공공', (5.6, 5.6))
def b_beacon():
    W0, W1 = 3.2, 2.7
    K.S.low_cap['walls'] = 'stone_l'
    with grp('floor'):
        # stepped plinth
        bx((5.0, 5.0, 0.14), (0, 0, 0), 'stone_d', bev=0.04)
        bx((4.3, 4.3, 0.12), (0, 0, 0.0), 'stone', bev=0.04)
        K.stone_floor(-1.3, -1.3, 1.3, 1.3, seed=7)
        bx((1.3, 0.8, 0.12), (0, -2.35, 0), 'stone_l', bev=0.03)
    ops = [('S', 0.0, 0.55, -1, 1.85), ('E', 0.0, 0.18, 3.2, 3.9), ('W', 0.3, 0.18, 4.6, 5.3),
           ('N', -0.3, 0.18, 2.4, 3.1), ('S', 0.0, 0.2, 5.6, 6.3)]
    with grp('walls'):
        top = square_tower(W0, W1, 0.12, 7.6, ops, seed=3, cols=('stone_w', 'stone_l', '#B9AC9C', 'stone'))
        # arched door frame
        y = -W0 / 2
        for s in (-1, 1):
            bx((0.22, 0.42, 1.85), (s * 0.66, y, 0.12), 'stone_l', bev=0.03)
        for i in range(7):
            a = math.pi * i / 6
            bx((0.26, 0.42, 0.22), (math.cos(a) * 0.66, y, 1.95 + math.sin(a) * 0.35), 'stone_l',
               rot=(0, -math.degrees(a) + 90, 0), bev=0.03, origin='center')
        # narrow glowing slit windows
        for (sd, off, hw, zb, zt) in ops[1:]:
            f = ((zb + zt) / 2) / 7.6
            w = W0 + (W1 - W0) * f
            pos = {'S': (off, -w / 2 + 0.05), 'N': (-off, w / 2 - 0.05), 'E': (w / 2 - 0.05, off),
                   'W': (-w / 2 + 0.05, -off)}[sd]
            rot = {'S': 0, 'N': 180, 'E': 90, 'W': 270}[sd]
            with xf(pos, rot):
                bx((hw * 2, 0.3, zt - zb), (0, 0, zb + 0.12), 'glow', bev=0)
        K.lantern(0.95, -W0 / 2 - 0.15, 2.3)
        K.lantern(-0.95, -W0 / 2 - 0.15, 2.3)
    with grp('walls~'):
        # spring garland over the door
        banner_string((-0.9, -W0 / 2 - 0.22, 2.55), (0.9, -W0 / 2 - 0.22, 2.55), n=6, sag=0.25, seed=1)
    with grp('roof'):
        # corbelled crown + crenellated parapet + golden brazier
        z = top
        bx((W1 + 0.5, W1 + 0.5, 0.25), (0, 0, z), 'stone_l', bev=0.05)
        bx((W1 + 0.8, W1 + 0.8, 0.22), (0, 0, z + 0.25), 'stone', bev=0.05)
        zt = z + 0.47
        bx((W1 + 0.6, W1 + 0.6, 0.06), (0, 0, zt), 'stone_d', bev=0)
        Wc = W1 + 0.8
        R = rnd(2)
        for side in range(4):
            for i in range(5):
                t = -Wc / 2 + 0.2 + i * (Wc - 0.4) / 4
                p = [(t, -Wc / 2 + 0.15), (Wc / 2 - 0.15, t), (-t, Wc / 2 - 0.15), (-Wc / 2 + 0.15, -t)][side]
                h = 0.55 if i % 2 == 0 else 0.3
                bx((0.36, 0.36, h), (p[0], p[1], zt), R.choice(['stone_w', 'stone_l', 'stone']), bev=0.04)
                if i % 2 == 0:
                    snowcap(0.17, (p[0], p[1], zt + h), 0.05, seed=side * 5 + i)
        # brazier: stone pedestal + golden bowl + logs + flames
        cy(0.45, 0.35, (0, 0, zt), 'stone_d', r_top=0.35, segs=12, bev=0.03)
        cy(0.22, 0.35, (0, 0, zt + 0.35), 'iron', segs=10, bev=0)
        cy(0.4, 0.3, (0, 0, zt + 0.68), 'gold', r_top=0.68, segs=16, bev=0.03)
        cy(0.6, 0.05, (0, 0, zt + 0.96), 'ember', segs=16, bev=0)
        for i in range(5):
            a = 360 * i / 5
            K.log_(0.06, 0.8, (0, 0, zt + 1.05), (70, 0, a), 'bark')
        flame(0, 0, zt + 0.95, s=1.7, seed=4)
        fx('fx_fire', 0, 0, zt + 1.3)
        fx('fx_light', 0, 0, zt + 1.6)
        fx('fx_smoke', 0, 0, zt + 2.3)
        # flag poles on two corners
        for s in (-1, 1):
            x, y = s * (Wc / 2 - 0.15), Wc / 2 - 0.15
            cy(0.03, 1.4, (x, y, zt + 0.55), 'wood_d', segs=6, bev=0)
            extr([(0.0, 0.0), (0.55, -0.12), (0.0, -0.32)], 0.02, loc=(x, y, zt + 1.95), rot=(90, 0, 0),
                 c='red' if s < 0 else 'yellow', bev=0)
    K.add_room('봉화대 1층', -1.25, -1.25, 1.25, 1.25)
    with grp('interior'), room('봉화대 1층'):
        # stair ladder up the north-east corner + firewood
        with xf((0.95, 0.4, K.FZ), 0):
            for s in (-1, 1):
                seg((s * 0.18, 0.5, 0), (s * 0.18, 0.75, 2.6), 0.03, 'wood_l')
            for i in range(8):
                z = 0.25 + i * 0.3
                seg((-0.18, 0.5 + z * 0.1, z), (0.18, 0.5 + z * 0.1, z), 0.02, 'wood_m')
        with xf((-0.75, 0.75, K.FZ), 90):
            F.log_stack(3, 0.09, 0.9, seed=4, snow_top=False)
        slot('work', -0.2, 0.5, K.face(-0.2, 0.5, -0.75, 0.75))
        put(F.barrel_in, -0.9, -0.75, 0, r=0.2, h=0.5)
        with grp('walls'):
            bx((2.4, 0.6, 0.06), (0, 0.1, 2.55), 'wood_m', bev=0.01)      # landing (hidden in the cutaway)
    with grp('exterior'):
        # four little flower boxes + garland poles around the plinth
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * 2.35, sy * 2.35
                cy(0.05, 2.0, (x, y, 0), 'wood_d', segs=6, bev=0)
                sp(0.07, (x, y, 2.02), 'gold', segs=8, rings=5)
                with grp('roof'):
                    banner_string((x, y, 2.0), (sx * (W1 + 0.8) / 2, sy * (W1 + 0.8) / 2, top + 0.15), n=8, sag=0.6,
                                  seed=sx + 2 * sy + 3)
        for sx in (-1, 1):
            K.flower_pot(sx * 1.0, -2.3, 0.0, seed=sx + 3, fc='pink' if sx < 0 else 'yellow', s=1.3)
    slot('chat', -1.6, -2.6, K.face(-1.6, -2.6, 0, 0))
    slot('chat', 1.6, -2.6, K.face(1.6, -2.6, 0, 0))
    slot('pray', 0.0, -2.75, 180)
    K.set_door((0.0, -2.85), (0.0, -0.95))


# =========================================================================== 화톳불 망루 watchtower
@building('watchtower', '화톳불 망루', '공공', (3.0, 3.0), low=False)
def b_watchtower():
    P = 3.25      # platform height
    with grp('floor'):
        R = rnd(1)
        for i in range(10):
            a = math.tau * i / 10
            bx((0.5, 0.4, 0.06), (math.cos(a) * 1.15, math.sin(a) * 1.15, 0), R.choice(['stone_l', 'stone']),
               rot=(0, 0, math.degrees(a)), bev=0.025)
    with grp('exterior'):
        b0, b1 = 1.0, 0.72
        for sx in (-1, 1):
            for sy in (-1, 1):
                seg((sx * b0, sy * b0, 0), (sx * b1, sy * b1, P + 0.9), 0.1, 'log1', r2=0.085)
                bx((0.32, 0.32, 0.14), (sx * b0, sy * b0, 0), 'stone', bev=0.03)
        for k, (za, zb) in enumerate(((0.3, 1.6), (1.6, 3.0))):
            fa, fb = za / (P + 0.9), zb / (P + 0.9)
            ra, rb = b0 + (b1 - b0) * fa, b0 + (b1 - b0) * fb
            for side in range(4):
                if side == 0 and k == 0:
                    continue
                c = [(1, 0), (0, 1), (-1, 0), (0, -1)][side]
                for s in (-1, 1):
                    if c[0]:
                        seg((c[0] * ra, -s * ra, za), (c[0] * rb, s * rb, zb), 0.04, 'wood_m')
                    else:
                        seg((-s * ra, c[1] * ra, za), (s * rb, c[1] * rb, zb), 0.04, 'wood_m')
        # ladder on the front (-Y)
        for s in (-1, 1):
            seg((s * 0.22, -1.25, 0), (s * 0.22, -0.82, P + 0.1), 0.03, 'wood_l')
        for i in range(10):
            z = 0.25 + i * 0.31
            y = -1.25 + 0.43 * z / (P + 0.1)
            seg((-0.22, y, z), (0.22, y, z), 0.02, 'wood_m')
        slot('work', 0.0, -1.6, 180)
        # bench + small woodpile at the base
        with xf((1.2, -0.9), 90):
            F.log_stack(3, 0.08, 0.7, seed=2)
        put(F.bench_in, -1.1, -1.05, 45, length=0.9, cushion=None, n=1, z=0.0)
    with grp('roof'):
        # platform, railing, brazier
        R = rnd(3)
        for i in range(9):
            bx((2.0, 0.22, 0.07), (0, -0.9 + i * 0.225, P), R.choice(['plank', 'plank2', 'wood_l']), bev=0.012)
        bx((2.1, 2.1, 0.1), (0, 0, P - 0.1), 'wood_d', bev=0.02)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cy(0.05, 0.75, (sx * 0.95, sy * 0.95, P + 0.07), 'wood_m', segs=6, bev=0)
        for i in range(4):
            c = [(0, -0.95, 0), (0, 0.95, 0), (0.95, 0, 90), (-0.95, 0, 90)][i]
            bx((1.95, 0.06, 0.08), (c[0], c[1], P + 0.72), 'wood_l', rot=(0, 0, c[2]), bev=0.01)
            bx((1.95, 0.05, 0.06), (c[0], c[1], P + 0.4), 'wood_l', rot=(0, 0, c[2]), bev=0)
        # little banners on the rail
        for i, (x, y) in enumerate(((-0.95, -0.95), (0.95, -0.95))):
            cy(0.025, 0.9, (x, y, P + 0.8), 'wood_d', segs=6, bev=0)
            extr([(0.0, 0.0), (0.4, -0.1), (0.0, -0.25)], 0.02, loc=(x, y, P + 1.65), rot=(90, 0, 0),
                 c=('red', 'yellow')[i], bev=0)
        # fire basket
        cy(0.08, 0.35, (0, 0, P + 0.07), 'iron', segs=8, bev=0)
        cy(0.28, 0.25, (0, 0, P + 0.42), 'iron', r_top=0.42, segs=12, bev=0.02)
        cy(0.4, 0.04, (0, 0, P + 0.65), 'ember', segs=12, bev=0)
        for i in range(4):
            K.log_(0.05, 0.6, (0, 0, P + 0.72), (70, 0, 90 * i + 20), 'bark')
        flame(0, 0, P + 0.62, s=1.0, seed=2)
        fx('fx_fire', 0, 0, P + 0.95)
        fx('fx_light', 0, 0, P + 1.2)
        fx('fx_smoke', 0, 0, P + 1.8)
    K.add_room('망루 아래', -1.4, -1.4, 1.4, 1.4)
    for s in K.S.slots:
        s['room'] = '망루 아래'
    K.set_door((0.0, -1.95), (0.0, -1.5))


# =========================================================================== 시장 가판대 market
@building('market', '시장 가판대', '상업', (4.2, 3.2), low=False)
def b_market():
    W, D = 3.0, 1.6
    with grp('floor'):
        R = rnd(2)
        for i in range(14):
            bx((W / 14 * 1.0 - 0.01, D + 0.4, 0.1), (-W / 2 + W / 14 * (i + 0.5), 0.1, 0),
               R.choice(['plank', 'plank2', 'wood_l']), bev=0.012)
    with grp('exterior'):
        for sx in (-1, 1):
            for y, h in ((-D / 2 + 0.05, 2.0), (D / 2 + 0.25, 2.35)):
                bx((0.12, 0.12, h), (sx * (W / 2 - 0.06), y, 0.1), 'wood_d', bev=0.015)
        # back shelf with goods
        with xf((0, D / 2 + 0.15, 0.1)):
            for z in (0.5, 1.0, 1.5):
                bx((W - 0.3, 0.3, 0.05), (0, 0, z), 'wood_l', bev=0.01)
            bx((W - 0.3, 0.04, 1.6), (0, 0.16, 0.0), 'wood_m', bev=0)
            R = rnd(7)
            goods = ['red', 'orange', 'yellow', 'leaf_l', 'cream', 'blue_l', 'pink']
            for z in (0.55, 1.05):
                for i in range(6):
                    x = -1.1 + i * 0.44
                    if (i + int(z * 2)) % 3 == 0:
                        cy(0.07, 0.16, (x, 0, z), R.choice(['orange', 'blue_l', 'cream']), segs=8, bev=0)
                        cy(0.072, 0.02, (x, 0, z + 0.16), 'canvas', segs=8, bev=0)
                    else:
                        F.basket(x, 0, z, fill=R.choice(goods), seed=i, r=0.13)
            for i in range(4):
                bx((0.3, 0.2, 0.18), (-1.0 + i * 0.66, 0, 1.55), R.choice(['wood_l', 'sack', 'canvas']), bev=0.02)
        slot('sell', 0.0, 0.3, 0)
    with grp('interior'):
        put(F.shop_counter, 0.0, -0.45, 0, w=2.6, d=0.6, seed=4, act=False)
        slot('shop', -0.6, -1.25, 180)
        slot('shop', 0.6, -1.25, 180)
        put(F.crate_in, -1.75, -0.95, 15, s=0.45, fill='red', seed=1, z=0.0)
        put(F.crate_in, 1.75, -0.95, -10, s=0.45, fill='orange', seed=2, z=0.0)
        F.sack(1.7, 0.5, 0.1, s=0.7, c='sack', flour=False)
        put(F.stool, -0.9, 0.4, 0, sit=False, h=0.32)
    with grp('roof'):
        stall_awning(0, D / 2 + 0.35, 2.45, W + 0.4, depth=D + 0.7, drop=0.55, c1='red', c2='cream', n=9)
        for sx in (-1, 1):
            K.lantern(sx * 1.2, -D / 2 - 0.05, 1.95, bracket=False)
        # sign board on top
        bx((1.4, 0.08, 0.42), (0, D / 2 + 0.3, 2.5), 'wood_m', bev=0.02)
        bx((1.26, 0.09, 0.3), (0, D / 2 + 0.3, 2.56), 'cream', bev=0)
        for i, c in enumerate(('red', 'yellow', 'green')):
            sp(0.07, (-0.35 + i * 0.35, D / 2 + 0.24, 2.71), c, scale=(1, 0.5, 1), segs=8, rings=5)
    K.add_room('가판대', -W / 2, -D / 2 - 0.9, W / 2, D / 2 + 0.3)
    for s in K.S.slots:
        s['room'] = '가판대'
    K.set_door((0.0, -1.55), (0.0, -1.05))


# =========================================================================== 마을 동상 statue
@building('statue', '마을 동상', '공공', (4.2, 4.2), low=False)
def b_statue():
    with grp('floor'):
        R = rnd(3)
        for i in range(16):
            a = math.tau * i / 16
            bx((0.62, 0.5, 0.05), (math.cos(a) * 1.75, math.sin(a) * 1.75, 0), R.choice(['stone_l', 'stone_w']),
               rot=(0, 0, math.degrees(a)), bev=0.02)
        cy(1.5, 0.05, (0, 0, 0), 'stone_l', segs=16, bev=0.02)
    with grp('exterior'):
        # octagonal plinth (3 steps)
        cy(1.15, 0.2, (0, 0, 0.0), 'stone', segs=8, bev=0.04)
        cy(0.85, 0.25, (0, 0, 0.2), 'stone_l', segs=8, bev=0.04)
        cy(0.6, 0.7, (0, 0, 0.45), 'stone_w', r_top=0.55, segs=8, bev=0.04)
        cy(0.68, 0.12, (0, 0, 1.15), 'stone_l', segs=8, bev=0.04)
        bx((0.5, 0.05, 0.3), (0, -0.585, 0.65), 'gold', bev=0.015)        # plaque
        bx((0.42, 0.06, 0.22), (0, -0.59, 0.69), 'wood_d', bev=0)
        # chibi villager statue raising a spring flower torch (warm bronze)
        br = '#B07A45'
        br2 = '#93633A'
        z = 1.27
        cy(0.32, 0.08, (0, 0, z), br2, segs=12, bev=0.02)
        for s in (-1, 1):
            cy(0.09, 0.32, (s * 0.12, 0, z + 0.06), br, segs=10, bev=0.02)
            sp(0.11, (s * 0.12, -0.04, z + 0.1), br2, scale=(1, 1.3, 0.6), segs=10, rings=6)
        cy(0.28, 0.55, (0, 0, z + 0.35), br, r_top=0.2, segs=14, bev=0.04)          # coat
        cy(0.3, 0.1, (0, 0, z + 0.35), br2, segs=14, bev=0.02)
        sp(0.42, (0, 0, z + 1.18), br, scale=(1, 0.95, 0.95), segs=18, rings=10)       # big head
        sp(0.44, (0, 0.1, z + 1.36), br2, scale=(1.0, 0.92, 0.72), segs=18, rings=10)   # hair cap
        for s in (-1, 1):
            sp(0.03, (s * 0.2, -0.36, z + 1.05), '#D9A06A', scale=(1.3, 0.4, 0.8), segs=8, rings=4)
        for s in (-1, 1):
            sp(0.05, (s * 0.15, -0.38, z + 1.15), '#5E3E22', scale=(1, 0.5, 1.2), segs=8, rings=5)
        # scarf
        cy(0.24, 0.1, (0, 0, z + 0.85), 'red', segs=14, bev=0.03)
        seg((0.12, -0.18, z + 0.88), (0.22, -0.26, z + 0.55), 0.05, 'red')
        # left arm down, right arm up with a torch of flowers + golden flame
        seg((0.22, 0, z + 0.8), (0.33, -0.05, z + 0.45), 0.07, br)
        seg((-0.22, 0, z + 0.8), (-0.4, -0.05, z + 1.4), 0.07, br)
        sp(0.08, (-0.42, -0.06, z + 1.45), br2, segs=10, rings=6)
        cy(0.04, 0.45, (-0.43, -0.06, z + 1.35), br2, segs=8, bev=0)
        cy(0.09, 0.12, (-0.43, -0.06, z + 1.78), 'gold', r_top=0.13, segs=10, bev=0.01)
        sp(0.12, (-0.43, -0.06, z + 1.98), 'ember', scale=(1, 1, 1.4), segs=10, rings=6)
        for k in range(5):
            a = math.tau * k / 5
            sp(0.05, (-0.43 + 0.12 * math.cos(a), -0.06 + 0.12 * math.sin(a), z + 1.9), ('pink', 'yellow')[k % 2],
               segs=8, rings=5)
        # little bird on the shoulder
        sp(0.07, (0.25, 0.02, z + 0.98), 'stone_l', scale=(1.2, 0.9, 0.9), segs=10, rings=6)
        sp(0.05, (0.25, -0.06, z + 1.06), 'stone_l', segs=8, rings=5)
        bx((0.03, 0.04, 0.02), (0.25, -0.11, z + 1.05), 'gold', bev=0)
        fx('fx_light', -0.43, -0.06, z + 2.0)
    # flower beds + benches around
    with grp('exterior'):
        R = rnd(5)
        for i in range(4):
            a = math.radians(45 + 90 * i)
            x, y = math.cos(a) * 1.45, math.sin(a) * 1.45
            cy(0.32, 0.18, (x, y, 0), 'stone', segs=10, bev=0.02)
            blob(0.28, (x, y, 0.2), 'leaf', scale=(1, 1, 0.6), seed=i, subdiv=1)
            for k in range(6):
                b = R.uniform(0, math.tau)
                sp(0.05, (x + math.cos(b) * 0.18, y + math.sin(b) * 0.18, 0.33), R.choice(['pink', 'yellow', 'red',
                                                                                            'white']),
                   segs=8, rings=4)
        for sx in (-1, 1):
            put(F.bench_in, sx * 1.75, 0.25, -90 * sx, length=1.1, cushion=None, n=2, z=0.0)
    K.add_room('광장', -2.1, -2.1, 2.1, 2.1)
    with room('광장'):
        slot('chat', -0.8, -1.55, K.face(-0.8, -1.55, 0, 0))
        slot('chat', 0.85, -1.5, K.face(0.85, -1.5, 0, 0))
        slot('pray', 0.0, -1.7, 180)
    for s in K.S.slots:
        s['room'] = '광장'
    K.set_door((0.0, -2.2), (0.0, -1.6))


ORDER = ['coop', 'barn', 'sheepfold', 'pigsty', 'orchard', 'apiary', 'fishing', 'dairy', 'beacon', 'watchtower',
         'market', 'statue']
BUILDINGS = OrderedDict((k, BUILDINGS[k]) for k in ORDER)
