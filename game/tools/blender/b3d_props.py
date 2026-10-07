"""
b3d_props.py - CONTRACT3D appendix A 6.3 / 6.4: carried items (item_*) and merchant deco props (deco_*).

    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_props.py -- [keys...]
    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_props.py -- --sheet [--samples 16]

One mesh node named <key> per GLB (flat Principled colours, origin = bottom centre, front -Y),
plus optional slot.* / fx_* empties.  Written to assets3d/props/<key>.glb.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,F401
from mathutils import Vector  # noqa: E402
import bl_common as bc  # noqa: E402
import b3d_kit as K  # noqa: E402
import b3d_furniture as F  # noqa: E402
from b3d_kit import bx, cy, sp, blob, seg, slot, fx, xf, grp, rnd, snowcap, extr  # noqa: E402

OUT = os.path.join(K.GAME, 'assets3d', 'props')
SHOTS = os.path.normpath(os.path.join(K.GAME, '..', '.cache', 'shots', 'b3d2'))
PROPS = {}


def prop(key):
    def deco(fn):
        PROPS[key] = fn
        return fn
    return deco


# =========================================================================== items (hand size 0.2-0.4 m)
def basket_base(r=0.13, h=0.1, c='straw_d', handle=True):
    cy(r * 0.8, h, (0, 0, 0), c, r_top=r, segs=12, bev=0.01)
    cy(r * 1.02, 0.02, (0, 0, h - 0.015), 'straw', segs=12, bev=0)
    cy(r * 0.84, 0.018, (0, 0, h * 0.45), 'straw', r_top=r * 0.92, segs=12, bev=0)
    if handle:
        pts = [(-r * 0.9, 0, h)]
        for k in range(1, 8):
            a = math.pi * k / 8
            pts.append((-r * 0.9 * math.cos(a), 0, h + r * 1.1 * math.sin(a)))
        pts.append((r * 0.9, 0, h))
        for a, b in zip(pts, pts[1:]):
            seg(a, b, 0.012, c)


@prop('item_egg')
def item_egg():
    basket_base(0.13, 0.09)
    sp(0.12, (0, 0, 0.085), 'red', scale=(1, 1, 0.15), segs=12, rings=4)
    for i in range(4):
        a = math.tau * i / 4 + 0.4
        sp(0.04, (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.09), 'red', scale=(1, 1, 0.5), segs=6, rings=4)
    for i, (x, y, z, r) in enumerate(((-0.05, -0.03, 0.1, 0), (0.05, -0.02, 0.1, 25), (0.0, 0.05, 0.1, -20),
                                      (0.0, -0.01, 0.15, 10))):
        sp(0.042, (x, y, z + 0.035), ('cream', '#F2D9B8')[i % 2], scale=(0.85, 0.85, 1.12), rot=(r, 0, 0), segs=10,
           rings=7)


@prop('item_milk')
def item_milk():
    cy(0.1, 0.22, (0, 0, 0), 'stone_l', r_top=0.1, segs=14, bev=0.01)
    cy(0.1, 0.06, (0, 0, 0.22), 'stone_l', r_top=0.055, segs=14, bev=0)
    cy(0.055, 0.06, (0, 0, 0.28), 'stone_l', segs=12, bev=0)
    cy(0.06, 0.03, (0, 0, 0.34), 'steel', segs=12, bev=0.005)
    cy(0.103, 0.025, (0, 0, 0.05), 'blue', segs=14, bev=0)
    cy(0.103, 0.025, (0, 0, 0.16), 'blue', segs=14, bev=0)
    for s in (-1, 1):
        seg((s * 0.1, 0, 0.2), (s * 0.13, 0, 0.24), 0.012, 'steel')
        seg((s * 0.13, 0, 0.24), (s * 0.1, 0, 0.28), 0.012, 'steel')
    sp(0.035, (0, 0, 0.375), 'white', scale=(1, 1, 0.4), segs=8, rings=4)


@prop('item_cheese')
def item_cheese():
    # wheel with a wedge cut out + the wedge leaning on it
    r, h = 0.15, 0.1
    n = 16
    pts = []
    for i in range(n - 1):
        a = math.radians(40) + (math.tau - math.radians(80)) * i / (n - 2)
        pts.append((math.cos(a) * r, math.sin(a) * r))
    pts.append((0.0, 0.0))
    with xf((0, 0, 0), 0):
        o = K.L.extrude('ch', [(x, y) for x, y in pts], h, loc=(0, 0, 0), rot=(0, 0, 0), top=K.M('yellow'),
                        side=K.M('yellow'), bevel=0.012, segs=1)
        K.reg(o)
    cy(r * 1.01, 0.025, (0, 0, 0.02), 'orange', segs=n, bev=0)
    cy(r * 1.01, 0.02, (0, 0, h - 0.035), 'orange', segs=n, bev=0)
    # holes
    for (x, y, z, rr) in ((-0.06, -0.12, 0.05, 0.016), (0.03, 0.13, 0.06, 0.013), (-0.12, 0.05, 0.04, 0.015)):
        sp(rr, (x, y, z), '#D99A2B', segs=6, rings=4)
    with xf((0.19, -0.03, 0), -10):
        o = K.L.extrude('wd', [(0, 0), (0.14, -0.04), (0.14, 0.04)], 0.08, loc=(0, 0, 0.0), top=K.M('yellow'),
                        side=K.M('yellow'), bevel=0.008, segs=1)
        K.reg(o)


@prop('item_wool')
def item_wool():
    R = rnd(3)
    for i in range(9):
        a = math.tau * i / 9
        rr = 0.07 if i % 2 else 0.09
        sp(0.075, (math.cos(a) * rr, math.sin(a) * rr, 0.07 + R.uniform(-0.01, 0.02)), ('cream', 'white')[i % 2],
           segs=10, rings=6)
    sp(0.1, (0, 0, 0.1), 'cream', scale=(1, 1, 0.9), segs=12, rings=7)
    sp(0.07, (0.02, -0.01, 0.17), 'white', segs=10, rings=6)
    cy(0.105, 0.025, (0, 0, 0.08), 'rope', segs=12, bev=0)
    seg((0.1, -0.02, 0.09), (0.16, -0.06, 0.04), 0.008, 'rope')


@prop('item_meat')
def item_meat():
    # big cartoon ham leg on a paper sheet
    bx((0.3, 0.22, 0.008), (0, 0, 0), 'paper', rot=(0, 0, 15), bev=0)
    with xf((0, 0, 0.0), 20):
        sp(0.1, (-0.03, 0, 0.09), 'meat' if 'meat' in K.P else '#C8463D', scale=(1.25, 1.0, 0.85), segs=14, rings=8)
        sp(0.085, (-0.03, 0, 0.1), '#E2675A', scale=(1.2, 0.95, 0.85), segs=12, rings=7)
        seg((0.07, 0, 0.09), (0.17, 0, 0.11), 0.025, 'cream')
        sp(0.032, (0.18, 0.015, 0.11), 'cream', segs=8, rings=5)
        sp(0.032, (0.18, -0.015, 0.11), 'cream', segs=8, rings=5)
        cy(0.035, 0.03, (0.07, 0, 0.09), 'rope', rot=(0, 90, 0), origin='center', segs=8, bev=0)


@prop('item_apple')
def item_apple():
    basket_base(0.14, 0.1)
    R = rnd(4)
    for i, (x, y, z) in enumerate(((-0.05, -0.04, 0.12), (0.05, -0.03, 0.12), (0.0, 0.05, 0.12),
                                   (-0.05, 0.04, 0.11), (0.01, -0.0, 0.17))):
        c = 'red' if i != 3 else '#9CC64A'
        sp(0.05, (x, y, z), c, scale=(1, 1, 0.9), segs=10, rings=6)
        seg((x, y, z + 0.04), (x + 0.005, y, z + 0.065), 0.006, 'wood_d')
    sp(0.025, (0.015, 0.0, 0.235), 'leaf_l', scale=(1.4, 0.6, 0.3), segs=6, rings=4)


@prop('item_honey')
def item_honey():
    cy(0.08, 0.04, (0, 0, 0), 'orange', r_top=0.1, segs=14, bev=0.01)
    cy(0.1, 0.12, (0, 0, 0.04), 'orange', r_top=0.085, segs=14, bev=0.01)
    cy(0.065, 0.03, (0, 0, 0.16), 'orange', segs=12, bev=0)
    sp(0.1, (0, 0, 0.19), 'red', scale=(1, 1, 0.25), segs=12, rings=6)        # cloth lid
    cy(0.07, 0.02, (0, 0, 0.175), 'rope', segs=12, bev=0)
    for i in range(4):
        a = math.tau * i / 4 + 0.3
        sp(0.03, (math.cos(a) * 0.085, math.sin(a) * 0.085, 0.16), 'red', scale=(1, 1, 1.4), segs=6, rings=4)
    bx((0.09, 0.012, 0.06), (0, -0.098, 0.07), 'cream', bev=0)                 # label
    sp(0.018, (0, -0.105, 0.1), 'yellow', scale=(1, 0.4, 1), segs=6, rings=4)
    # drips + dipper
    sp(0.02, (0.06, -0.07, 0.15), 'gold', scale=(0.8, 0.8, 1.6), segs=6, rings=4)
    seg((0.03, 0.02, 0.2), (0.09, 0.05, 0.33), 0.01, 'wood_l')
    sp(0.025, (0.025, 0.018, 0.2), 'wood_l', scale=(1, 1, 1.2), segs=6, rings=4)


@prop('item_fish')
def item_fish():
    for k, (x, rot, c) in enumerate(((-0.055, -6, 'blue_l'), (0.055, 8, '#F08A5D'))):
        with xf((x, 0, 0.0), rot):
            sp(0.055, (0, 0, 0.065), c, scale=(0.55, 2.3, 1.15), segs=12, rings=7)
            sp(0.05, (0, 0.14, 0.065), c, scale=(0.25, 0.7, 1.25), segs=8, rings=5)          # tail fin
            sp(0.03, (0, 0.0, 0.13), c, scale=(0.25, 1.6, 0.6), segs=8, rings=4)            # back fin
            sp(0.04, (0, -0.02, 0.04), 'cream', scale=(0.5, 2.0, 0.6), segs=8, rings=5)     # belly
            for sd in (-1, 1):
                sp(0.011, (sd * 0.028, -0.085, 0.08), 'ink', segs=6, rings=4)
    # string through the mouths, tied into a loop
    seg((-0.055, -0.12, 0.07), (0.0, -0.13, 0.2), 0.007, 'rope')
    seg((0.055, -0.12, 0.07), (0.0, -0.13, 0.2), 0.007, 'rope')
    cy(0.03, 0.008, (0.0, -0.13, 0.23), 'rope', rot=(90, 0, 0), origin='center', segs=8, bev=0)


@prop('item_flour')
def item_flour():
    sp(0.13, (0, 0, 0.13), 'sack', scale=(1, 0.85, 1.05), segs=14, rings=8)
    cy(0.06, 0.06, (0, 0, 0.26), 'sack', r_top=0.04, segs=10, bev=0)
    cy(0.065, 0.02, (0, 0, 0.26), 'rope', segs=10, bev=0)
    sp(0.04, (0, 0, 0.33), 'sack', scale=(1.4, 1.2, 0.6), segs=8, rings=5)
    sp(0.05, (0, -0.105, 0.13), 'cream', scale=(0.9, 0.3, 0.9), segs=10, rings=6)   # flour print
    seg((-0.02, -0.12, 0.1), (0.02, -0.12, 0.16), 0.008, 'wheat')
    sp(0.06, (0.11, -0.05, 0.01), 'cream', scale=(1.2, 1, 0.25), segs=8, rings=4)


@prop('item_stone')
def item_stone():
    blob(0.11, (-0.05, 0.0, 0.0), 'stone', scale=(1.25, 1.0, 0.75), seed=2, amp=0.15, subdiv=1, flat_bottom=0.02,
         facet=True)
    bx((0.16, 0.12, 0.1), (0.1, -0.03, 0.0), 'stone_l', rot=(0, 0, 20), bev=0.02)
    blob(0.07, (0.06, 0.07, 0.1), 'stone_d', scale=(1.2, 1, 0.8), seed=5, amp=0.15, subdiv=1, facet=True)


@prop('item_coin_bag')
def item_coin_bag():
    sp(0.11, (0, 0, 0.1), 'leather', scale=(1, 1, 0.95), segs=14, rings=8)
    cy(0.045, 0.06, (0, 0, 0.19), 'leather', r_top=0.06, segs=10, bev=0)
    cy(0.05, 0.02, (0, 0, 0.19), 'gold', segs=10, bev=0)
    sp(0.05, (0, 0, 0.26), 'leather', scale=(1.5, 1.5, 0.45), segs=10, rings=5)
    for i in range(4):
        a = math.tau * i / 4
        sp(0.02, (math.cos(a) * 0.05, math.sin(a) * 0.05, 0.26), 'leather', segs=6, rings=4)
    cy(0.04, 0.008, (0, -0.105, 0.11), 'gold', rot=(90, 0, 0), origin='center', segs=10, bev=0)   # emblem
    for i, (x, y, z, rx) in enumerate(((0.12, -0.06, 0.0, 0), (0.15, 0.02, 0.0, 0), (0.13, -0.03, 0.015, 15),
                                       (-0.12, -0.07, 0.0, 0))):
        cy(0.032, 0.012, (x, y, z), 'gold', rot=(rx, 0, 0), segs=10, bev=0)


# =========================================================================== deco props
@prop('deco_fountain')
def deco_fountain():
    R = rnd(1)
    n = 14
    for i in range(n):
        a = math.tau * (i + 0.5) / n
        bx((0.5, 0.26, 0.42), (math.cos(a) * 0.98, math.sin(a) * 0.98, 0), R.choice(['stone_l', 'stone_w']),
           rot=(0, 0, math.degrees(a) + 90), bev=0.04)
    for i in range(n):
        a = math.tau * i / n
        bx((0.6, 0.3, 0.08), (math.cos(a) * 0.98, math.sin(a) * 0.98, 0.42), 'stone', rot=(0, 0, math.degrees(a) + 90),
           bev=0.02)
    cy(0.9, 0.3, (0, 0, 0), 'stone_d', segs=14, bev=0)
    cy(0.88, 0.02, (0, 0, 0.32), 'water', segs=14, bev=0)
    cy(0.16, 0.95, (0, 0, 0.3), 'stone_l', r_top=0.12, segs=10, bev=0.02)
    cy(0.45, 0.12, (0, 0, 0.95), 'stone', r_top=0.5, segs=12, bev=0.02)
    cy(0.44, 0.02, (0, 0, 1.06), 'water', segs=12, bev=0)
    cy(0.09, 0.4, (0, 0, 1.05), 'stone_l', r_top=0.07, segs=8, bev=0)
    cy(0.22, 0.08, (0, 0, 1.42), 'stone', r_top=0.25, segs=10, bev=0.015)
    sp(0.09, (0, 0, 1.55), 'blue_l', scale=(1, 1, 1.5), segs=10, rings=6)
    for i in range(6):
        a = math.tau * i / 6
        p0 = (math.cos(a) * 0.22, math.sin(a) * 0.22, 1.5)
        p1 = (math.cos(a) * 0.45, math.sin(a) * 0.45, 1.08)
        seg(p0, p1, 0.022, 'blue_l')
        p2 = (math.cos(a + 0.26) * 0.88, math.sin(a + 0.26) * 0.88, 0.34)
        p3 = (math.cos(a + 0.26) * 0.5, math.sin(a + 0.26) * 0.5, 1.0)
        seg(p3, p2, 0.02, 'blue_l')
    for i in range(5):
        a = R.uniform(0, math.tau)
        sp(0.04, (math.cos(a) * 0.6, math.sin(a) * 0.6, 0.33), ('orange', 'gold')[i % 2], scale=(1, 0.5, 0.2),
           segs=6, rings=3)
    for i in range(4):
        a = math.tau * i / 4 + 0.4
        sp(0.08, (math.cos(a) * 1.0, math.sin(a) * 1.0, 0.52), 'snow', scale=(1.6, 1.2, 0.45), segs=8, rings=4)
    slot('chat', 0, -1.45, 180)
    slot('chat', 1.45, 0, 90)


@prop('deco_flowerbed')
def deco_flowerbed():
    R = rnd(5)
    W, D = 1.6, 0.8
    for s in (-1, 1):
        K.log_(0.07, W + 0.1, (0, s * D / 2, 0.07), (0, 90, 0), 'wood_m', segs=8)
        K.log_(0.07, D - 0.05, (s * W / 2, 0, 0.07), (90, 0, 0), 'wood_d', segs=8)
    bx((W - 0.05, D - 0.05, 0.12), (0, 0, 0), 'soil', bev=0.02)
    cols = ['red', 'yellow', 'pink', 'white', 'purple', 'orange']
    for i in range(16):
        x = -W / 2 + 0.15 + (i % 8) * (W - 0.3) / 7 + R.uniform(-0.04, 0.04)
        y = -0.18 + (i // 8) * 0.36 + R.uniform(-0.04, 0.04)
        h = R.uniform(0.15, 0.3)
        seg((x, y, 0.12), (x, y, 0.12 + h), 0.01, 'leaf')
        blob(0.065, (x, y, 0.1), 'leaf_l', scale=(1.2, 1.2, 0.7), seed=i, subdiv=1)
        c = cols[(i * 7) % len(cols)]
        for k in range(4):
            a = math.tau * k / 4
            sp(0.03, (x + math.cos(a) * 0.035, y + math.sin(a) * 0.035, 0.12 + h), c, scale=(1, 1, 0.5), segs=6,
               rings=3)
        sp(0.02, (x, y, 0.135 + h), 'yellow', segs=6, rings=3)


@prop('deco_painting_easel')
def deco_painting_easel():
    for s in (-1, 1):
        seg((s * 0.3, -0.12, 0), (s * 0.08, 0.02, 1.55), 0.025, 'wood_l')
    seg((0, 0.45, 0), (0, 0.05, 1.45), 0.025, 'wood_l')
    bx((0.7, 0.08, 0.04), (0, -0.07, 0.62), 'wood_m', rot=(-8, 0, 0), bev=0)
    with xf((0, -0.06, 0.66), 0):
        bx((0.66, 0.04, 0.55), (0, 0, 0), 'wood_d', rot=(-8, 0, 0), bev=0.01)
        bx((0.6, 0.045, 0.49), (0, -0.005, 0.03), 'cream', rot=(-8, 0, 0), bev=0)
        # little landscape: sky, hill, sun, tree
        bx((0.58, 0.05, 0.22), (0, -0.01, 0.27), 'blue_l', rot=(-8, 0, 0), bev=0)
        bx((0.58, 0.05, 0.14), (0, -0.012, 0.06), 'leaf_l', rot=(-8, 0, 0), bev=0)
        sp(0.06, (0.18, -0.03, 0.4), 'yellow', scale=(1, 0.3, 1), segs=8, rings=5)
        sp(0.08, (-0.15, -0.02, 0.25), 'green', scale=(1, 0.3, 1.1), segs=8, rings=5)
        bx((0.02, 0.05, 0.08), (-0.15, -0.03, 0.12), 'wood_d', rot=(-8, 0, 0), bev=0)
        sp(0.04, (0.05, -0.02, 0.17), 'pink', scale=(1, 0.3, 1), segs=6, rings=4)
    # stool + palette
    with xf((0.55, -0.35), 20):
        F.stool(sit=False, h=0.35)
        cy(0.11, 0.015, (0, 0, 0.36), 'wood_l', segs=10, bev=0)
        for i, c in enumerate(('red', 'yellow', 'blue', 'green', 'pink')):
            a = math.tau * i / 5
            sp(0.02, (math.cos(a) * 0.065, math.sin(a) * 0.065, 0.38), c, scale=(1, 1, 0.4), segs=6, rings=3)
        seg((-0.05, 0.08, 0.38), (0.12, 0.15, 0.4), 0.008, 'wood_d')
    slot('work', 0.0, -0.75, 180)


@prop('deco_gazebo')
def deco_gazebo():
    Wd = 2.6
    cy(1.55, 0.18, (0, 0, 0), 'stone', segs=8, bev=0.03, rot=(0, 0, 22.5))
    R = rnd(2)
    for i in range(8):
        bx((2.7, 0.33, 0.03), (0, -1.15 + i * 0.33, 0.18), R.choice(['plank', 'plank2']), bev=0)
    H = 2.1
    pts = []
    for i in range(8):
        a = math.tau * (i + 0.5) / 8
        pts.append((math.cos(a) * 1.35, math.sin(a) * 1.35))
    for i, (x, y) in enumerate(pts):
        cy(0.07, H, (x, y, 0.2), 'red', segs=8, bev=0)
    for i in range(8):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % 8]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        ln = math.hypot(x1 - x0, y1 - y0)
        bx((ln + 0.1, 0.1, 0.16), (mx, my, H + 0.05), 'wood_d', rot=(0, 0, ang), bev=0.01)
        if i not in (5, 6):    # open on the front (-Y)
            bx((ln, 0.08, 0.06), (mx, my, 0.75), 'wood_l', rot=(0, 0, ang), bev=0)
            for t in (0.25, 0.5, 0.75):
                cy(0.018, 0.55, (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0.2), 'wood_l', segs=5, bev=0)
    # octagonal roof (cone) with upturned eaves + snow
    cy(1.85, 0.12, (0, 0, H + 0.12), 'wood_d', segs=8, bev=0.02, rot=(0, 0, 22.5))
    cy(1.9, 1.1, (0, 0, H + 0.24), 'roof_g1', r_top=0.12, segs=8, bev=0.02, rot=(0, 0, 22.5))
    cy(1.35, 0.8, (0, 0, H + 0.62), 'snow', r_top=0.08, segs=8, bev=0.03, rot=(0, 0, 22.5))
    cy(0.1, 0.25, (0, 0, H + 1.3), 'gold', r_top=0.02, segs=8, bev=0)
    sp(0.08, (0, 0, H + 1.33), 'gold', segs=8, rings=5)
    for (x, y) in pts:
        sp(0.06, (x * 1.33, y * 1.33, H + 0.33), 'red', segs=6, rings=4)
        K.lantern(x * 1.12, y * 1.12, H + 0.05, size=0.11, bracket=False, light=False) if (x < 0 and y < 0) else None
    # bench around the inside back
    for i in (1, 2, 3):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % 8]
        mx, my = (x0 + x1) / 2 * 0.82, (y0 + y1) / 2 * 0.82
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        bx((0.95, 0.34, 0.06), (mx, my, 0.45), 'wood_l', rot=(0, 0, ang), bev=0.01)
        bx((0.8, 0.3, 0.25), (mx, my, 0.2), 'wood_m', rot=(0, 0, ang), bev=0)
    slot('sit', 0.0, 0.55, 0, z=0.2)
    slot('sit', -0.75, 0.25, K.face(-0.75, 0.25, 0, -1), z=0.2)
    slot('sit', 0.75, 0.25, K.face(0.75, 0.25, 0, -1), z=0.2)
    fx('fx_light', 0, 0, H - 0.2)


@prop('deco_snowman_big')
def deco_snowman_big():
    sp(0.5, (0, 0, 0.42), 'snow', scale=(1, 1, 0.88), segs=16, rings=9)
    sp(0.36, (0, 0, 1.0), 'snow', segs=16, rings=9)
    sp(0.27, (0, 0, 1.48), 'snow', segs=14, rings=8)
    for s in (-1, 1):
        sp(0.035, (s * 0.1, -0.24, 1.55), 'ink', segs=8, rings=5)
        sp(0.03, (s * 0.15, -0.21, 1.44), 'pink', scale=(1.2, 0.5, 0.7), segs=8, rings=4)
    cy(0.045, 0.22, (0, -0.25, 1.48), 'orange', r_top=0.005, rot=(90, 0, 0), segs=8, bev=0)
    for i in range(5):
        a = math.radians(-50 + i * 25)
        sp(0.02, (math.sin(a) * 0.2, -0.2 * math.cos(a) - 0.02, 1.36 - 0.03 * math.cos(a * 1.6)), 'ink', segs=6,
           rings=4)
    for z in (0.85, 1.05, 1.22):
        sp(0.035, (0, -0.33 + (z - 1.0) * 0.25, z), 'ink', segs=6, rings=4)
    # scarf + hat + broom arms
    cy(0.29, 0.1, (0, 0, 1.24), 'red', segs=14, bev=0.03)
    seg((0.15, -0.22, 1.27), (0.24, -0.28, 0.95), 0.05, 'red')
    bx((0.1, 0.03, 0.08), (0.24, -0.29, 0.89), 'yellow', bev=0)
    cy(0.26, 0.04, (0, 0, 1.68), 'ink', segs=14, bev=0.01)
    cy(0.17, 0.26, (0, 0, 1.7), 'ink', segs=14, bev=0.01)
    cy(0.175, 0.05, (0, 0, 1.75), 'red', segs=14, bev=0)
    for s in (-1, 1):
        seg((s * 0.3, 0, 1.08), (s * 0.75, 0.05, 1.38), 0.025, 'wood_d')
        seg((s * 0.66, 0.04, 1.33), (s * 0.78, -0.04, 1.48), 0.015, 'wood_d')
        seg((s * 0.66, 0.04, 1.33), (s * 0.85, 0.08, 1.32), 0.015, 'wood_d')


@prop('deco_lantern_post')
def deco_lantern_post():
    cy(0.2, 0.15, (0, 0, 0), 'stone', segs=8, bev=0.02)
    cy(0.06, 1.9, (0, 0, 0.15), 'iron', r_top=0.045, segs=8, bev=0)
    for z in (0.35, 1.5):
        cy(0.08, 0.06, (0, 0, z), 'gold', segs=8, bev=0)
    # curled arm + hanging lantern
    seg((0, 0, 1.9), (0.25, 0, 2.05), 0.025, 'iron')
    seg((0.25, 0, 2.05), (0.45, 0, 2.0), 0.025, 'iron')
    sp(0.05, (0.0, 0, 2.08), 'gold', segs=8, rings=5)
    K.lantern(0.45, 0, 2.02, size=0.18, bracket=False)
    # flower basket
    cy(0.12, 0.1, (-0.0, 0, 1.2), 'straw_d', r_top=0.16, segs=10, bev=0)
    blob(0.14, (0, 0, 1.33), 'leaf', scale=(1, 1, 0.6), seed=2, subdiv=1)
    for i in range(5):
        a = math.tau * i / 5
        sp(0.04, (math.cos(a) * 0.1, math.sin(a) * 0.1, 1.38), ('pink', 'yellow', 'red')[i % 3], segs=6, rings=4)
    snowcap(0.07, (0.45, 0, 2.03), 0.03, seed=1)


@prop('deco_swing')
def deco_swing():
    H = 2.0
    for s in (-1, 1):
        seg((s * 0.95, -0.55, 0), (s * 0.85, 0, H), 0.06, 'log1')
        seg((s * 0.95, 0.55, 0), (s * 0.85, 0, H), 0.06, 'log1')
        seg((s * 0.93, -0.35, 0.5), (s * 0.93, 0.35, 0.5), 0.03, 'wood_m')
    K.log_(0.07, 2.0, (0, 0, H), (0, 90, 0), 'log2', segs=8)
    snowcap(0.12, (0, 0, H + 0.06), 0.04, seed=3, scale=(6, 1, 1))
    for s in (-1, 1):
        seg((s * 0.25, 0, H), (s * 0.25, 0, 0.47), 0.012, 'rope')
    bx((0.62, 0.25, 0.05), (0, 0, 0.42), 'red', bev=0.015)
    bx((0.5, 0.2, 0.02), (0, 0, 0.47), 'yellow', bev=0)
    slot('play', 0, -0.45, 180)


# =========================================================================== export / preview
def export(key):
    t0 = time.time()
    K.reset()
    with grp(key):
        PROPS[key]()
    nodes = K.finalize(low=False)
    K._limit_materials(list(nodes.values()), 30)
    slots, fxl = K.write_empties(furniture=True)
    path = os.path.join(OUT, key + '.glb')
    K.export_glb(path)
    info = K.glb_info(path)
    ob = nodes[key]
    d = ob.dimensions
    bpy.context.view_layer.update()
    zmin = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
    print('[prop %-20s] tris %5d mats %2d size %.2f x %.2f x %.2f zmin %.3f slots %d %s %.1fs' % (
        key, info['total'], info['mats'], d.x, d.y, d.z, zmin, len(slots), '' if info['total'] <= 3000 else 'OVER',
        time.time() - t0), flush=True)
    return info['total']


def sheet(samples=16, keys=None):
    import b3d_preview as PV
    keys = keys or list(PROPS)
    PV.setup(samples)
    items = [k for k in keys if k.startswith('item_')]
    decos = [k for k in keys if k.startswith('deco_')]
    allo = []
    x = 0
    for k in items:
        allo += PV.import_glb(os.path.join(OUT, k + '.glb'), (x, -1.8, 0), 20)
        x += 0.5
    x = -0.5
    for k in decos:
        w = 3.2 if k == 'deco_gazebo' else (2.4 if k in ('deco_fountain', 'deco_swing') else 1.6)
        x += w / 2
        allo += PV.import_glb(os.path.join(OUT, k + '.glb'), (x, 0.6, 0), 15)
        x += w / 2 + 0.2
    far = os.path.join(K.GAME, 'assets3d', 'chars', 'farmer.glb')
    if os.path.exists(far):
        PV.import_glb(far, (-0.7, -1.4, 0), 20)
    PV.ground(80)
    PV.lights()
    c, r = PV.mesh_bounds(allo)
    PV.camera(c, r, (-0.3, -1.0, 0.8), (1700, 900), fill=0.55)
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, 'props_sheet.png')
    bc.render_to(path)
    print('wrote', path, flush=True)
    # close-up of the hand items
    PV.setup(samples)
    allo = []
    for i, k in enumerate(items):
        allo += PV.import_glb(os.path.join(OUT, k + '.glb'), ((i % 6) * 0.5, -(i // 6) * 0.55, 0), 20)
    PV.ground(40)
    PV.lights()
    c, r = PV.mesh_bounds(allo)
    PV.camera(c, r, (-0.25, -1.0, 0.9), (1400, 800), fill=0.6)
    path = os.path.join(SHOTS, 'items_sheet.png')
    bc.render_to(path)
    print('wrote', path, flush=True)


def main():
    a = bc.script_args()
    keys = [x for x in a if not x.startswith('--') and x in PROPS]
    if '--sheet' in a:
        sheet(int(a[a.index('--samples') + 1]) if '--samples' in a else 16, keys or None)
        return
    os.makedirs(OUT, exist_ok=True)
    for k in keys or list(PROPS):
        export(k)


if __name__ == '__main__':
    main()
