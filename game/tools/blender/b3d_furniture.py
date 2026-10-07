"""
b3d_furniture.py - furniture + small props for the 3D buildings (CONTRACT3D section 4).

Every builder models in a LOCAL frame: origin = floor centre, front = -Y, z = 0 floor.
Place one with  put(fn, x, y, rot, **kw)  (frame at floor height FZ) inside a building,
or export it standalone (b3d_export.py).  Builders add their own interaction slots.

Scale: residents are ~1.1 m chibis -> seats ~0.3 m, tables ~0.5 m, beds ~1.45 m long,
counters ~0.6 m.
"""
import math

import b3d_kit as K
from b3d_kit import bx, cy, sp, blob, seg, slot, fx, xf, rnd, snowcap, extr


def put(fn, x, y, rot=0.0, z=None, **kw):
    with xf((x, y, K.FZ if z is None else z), rot):
        return fn(**kw)


# =========================================================================== seating
def chair(c='wood_l', seat='red', back=True, sit=True, act='sit'):
    sh = 0.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.05, 0.05, sh - 0.04), (sx * 0.15, sy * 0.15, 0), c, bev=0.012)
    bx((0.4, 0.4, 0.05), (0, 0, sh - 0.05), c, bev=0.02)
    bx((0.34, 0.34, 0.05), (0, -0.01, sh), seat, bev=0.02)
    if back:
        for sx in (-1, 1):
            bx((0.05, 0.05, 0.42), (sx * 0.16, 0.17, sh), c, bev=0.012)
        bx((0.38, 0.05, 0.12), (0, 0.17, sh + 0.28), c, bev=0.02)
        bx((0.06, 0.04, 0.22), (0, 0.17, sh + 0.06), c, bev=0.01)
    if sit:
        slot(act, 0, -0.3, 0)


def stool(c='wood_l', top='wood_m', sit=True, h=0.3):
    for i in range(3):
        a = math.tau * i / 3 + 0.5
        seg((0.12 * math.cos(a), 0.12 * math.sin(a), 0), (0.07 * math.cos(a), 0.07 * math.sin(a), h - 0.04), 0.022, c)
    cy(0.17, 0.05, (0, 0, h - 0.05), top, segs=14, bev=0.015)
    if sit:
        slot('sit', 0, -0.3, 0)


def bench_in(length=1.2, c='wood_m', cushion='blue', sit=True, act='sit', n=None):
    sh = 0.3
    for sx in (-1, 1):
        bx((0.08, 0.3, sh - 0.05), (sx * (length / 2 - 0.1), 0, 0), c, bev=0.015)
    bx((length, 0.36, 0.06), (0, 0, sh - 0.05), c, bev=0.02)
    bx((length - 0.2, 0.05, 0.05), (0, 0, 0.08), c, bev=0)
    if cushion:
        bx((length - 0.12, 0.3, 0.05), (0, 0, sh + 0.01), cushion, bev=0.02)
    if sit:
        n = n or max(1, int(length / 0.55))
        for i in range(n):
            slot(act, -length / 2 + length / n * (i + 0.5), -0.32, 0)


def sofa(c='rose', wood='wood_d', w=1.3, sit=True):
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.035, 0.08, (sx * (w / 2 - 0.08), sy * 0.22, 0), wood, segs=8, bev=0)
    bx((w, 0.6, 0.2), (0, 0, 0.08), c, bev=0.05, seg=2)
    bx((w, 0.18, 0.48), (0, 0.22, 0.12), c, bev=0.06, seg=2)
    for sx in (-1, 1):
        bx((0.16, 0.6, 0.36), (sx * (w / 2 - 0.08), 0, 0.12), c, bev=0.06, seg=2)
    for i in (-1, 1):
        bx((w / 2 - 0.16, 0.42, 0.08), (i * (w / 4 - 0.04), -0.06, 0.28), c, bev=0.04, seg=2)
    bx((0.22, 0.08, 0.2), (-w / 2 + 0.3, 0.1, 0.36), 'cream', rot=(10, 0, 8), bev=0.04)
    if sit:
        slot('sit', -w / 4, -0.42, 0)
        slot('sit', w / 4, -0.42, 0)


def armchair(c='teal', wood='wood_d', sit=True, act='sit'):
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.03, 0.08, (sx * 0.24, sy * 0.2, 0), wood, segs=8, bev=0)
    bx((0.6, 0.55, 0.2), (0, 0, 0.08), c, bev=0.05, seg=2)
    bx((0.6, 0.16, 0.5), (0, 0.2, 0.12), c, bev=0.06, seg=2)
    for sx in (-1, 1):
        bx((0.13, 0.55, 0.34), (sx * 0.24, 0, 0.12), c, bev=0.05, seg=2)
    bx((0.36, 0.4, 0.08), (0, -0.05, 0.28), c, bev=0.03)
    if sit:
        slot(act, 0, -0.42, 0)


# =========================================================================== tables
def table_round(r=0.45, c='wood_l', cloth=None, h=0.5):
    cy(0.06, h - 0.05, (0, 0, 0.05), c, segs=10)
    cy(0.2, 0.05, (0, 0, 0), c, segs=14, r_top=0.12)
    cy(r, 0.05, (0, 0, h - 0.05), c, segs=20, bev=0.02)
    if cloth:
        cy(r * 0.75, 0.012, (0, 0, h), cloth, segs=20, bev=0)


def table_long(w=1.6, d=0.75, c='wood_l', h=0.5, runner=None):
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.07, 0.07, h - 0.05), (sx * (w / 2 - 0.1), sy * (d / 2 - 0.1), 0), c, bev=0.015)
    bx((w - 0.2, 0.04, 0.08), (0, d / 2 - 0.1, h - 0.13), c, bev=0)
    bx((w - 0.2, 0.04, 0.08), (0, -d / 2 + 0.1, h - 0.13), c, bev=0)
    n = 4
    for i in range(n):
        bx((w, d / n - 0.008, 0.05), (0, -d / 2 + d / n * (i + 0.5), h - 0.05), (c, K.P.get('wood_m') and 'wood_m')[i % 2]
           if c == 'wood_l' else c, bev=0.012)
    if runner:
        bx((w * 0.7, 0.24, 0.008), (0, 0, h), runner, bev=0)


def dining_set(w=1.4, d=0.75, n_side=2, c='wood_l', seat='red', act='eat', ends=False, dishes=True, seed=0,
               runner='cream'):
    """Long table with chairs on both long sides (+ optional ends) and eat slots at every chair."""
    table_long(w, d, c, runner=runner)
    R = rnd(seed)
    xs = [(-w / 2 + w / n_side * (i + 0.5)) for i in range(n_side)]
    for sy, rot in ((-1, 0), (1, 180)):
        for x in xs:
            with xf((x, sy * (d / 2 + 0.2)), rot):
                chair(c, seat, sit=False)
            # facing the table
            slot(act, x, sy * (d / 2 + 0.05), 180 if sy < 0 else 0)
            if dishes:
                plate(x, sy * (d / 2 - 0.17), 0.5, food=R.random() < 0.6, seed=seed + int(x * 10) + sy)
    if ends:
        for sx, rot in ((-1, 270), (1, 90)):
            with xf((sx * (w / 2 + 0.2), 0), rot):
                chair(c, seat, sit=False)
            slot(act, sx * (w / 2 + 0.05), 0, 90 if sx < 0 else 270)
    vase(0, 0, 0.5, seed=seed)


def round_set(r=0.45, n=4, c='wood_l', seat='blue', act='eat', start=45, seed=0, cloth='cream', tea=False):
    table_round(r, c, cloth=cloth)
    for i in range(n):
        a = math.radians(start + 360.0 / n * i)
        ca, sa = math.cos(a), math.sin(a)
        rot = math.degrees(a) + 90
        with xf(((r + 0.22) * ca, (r + 0.22) * sa), rot):
            chair(c, seat, sit=False)
        # resident faces the table centre: facing vector = (-ca, -sa) -> yaw with (sin y, -cos y)
        yaw = math.degrees(math.atan2(-ca, sa))
        slot(act, (r + 0.05) * ca, (r + 0.05) * sa, yaw)
        if not tea:
            plate((r - 0.17) * ca, (r - 0.17) * sa, 0.5, food=(i % 2 == 0), seed=seed + i)
        else:
            mug((r - 0.15) * ca, (r - 0.15) * sa, 0.5, c=('cream', 'blue_l', 'pink', 'white')[i % 4])
    if tea:
        with xf((0, 0, 0.5)):
            tea_set(tray=False)
    else:
        vase(0, 0, 0.5, seed=seed)


def meeting_table(w=2.0, d=1.0, n_side=3, seat='navy', chairs=True, act='sit'):
    for sx in (-1, 1):
        bx((0.12, d - 0.3, 0.45), (sx * (w / 2 - 0.25), 0, 0), 'wood_d', bev=0.02)
    bx((w, d, 0.06), (0, 0, 0.45), 'wood_m', bev=0.03, seg=2)
    bx((w - 0.1, d - 0.1, 0.01), (0, 0, 0.51), 'green', bev=0)
    for i, x in enumerate((-0.5, 0.15, 0.6)):
        paper(x, (-0.2, 0.15, -0.1)[i], 0.52, rot=(i * 23) % 40 - 20)
    cy(0.06, 0.12, (-0.1, 0.05, 0.51), 'ink', segs=8, bev=0)
    seg((-0.08, 0.05, 0.6), (0.0, 0.1, 0.75), 0.008, 'white')
    if chairs:
        xs = [(-w / 2 + w / n_side * (i + 0.5)) for i in range(n_side)]
        for sy, rot in ((-1, 0), (1, 180)):
            for x in xs:
                with xf((x, sy * (d / 2 + 0.2)), rot):
                    chair('wood_d', seat, sit=False)
                slot(act, x, sy * (d / 2 + 0.05), 180 if sy < 0 else 0)


def desk(w=1.0, d=0.55, c='wood_m', with_chair=True, seat='green', lamp=True, act='desk'):
    h = 0.5
    bx((0.3, d - 0.04, h - 0.05), (w / 2 - 0.17, 0, 0), c, bev=0.02)
    for i in range(3):
        bx((0.24, 0.02, 0.1), (w / 2 - 0.17, -d / 2 + 0.01, 0.06 + i * 0.13), 'wood_l', bev=0.005)
        sp(0.018, (w / 2 - 0.17, -d / 2 - 0.01, 0.11 + i * 0.13), 'gold', segs=6, rings=4)
    for sy in (-1, 1):
        bx((0.06, 0.06, h - 0.05), (-w / 2 + 0.05, sy * (d / 2 - 0.05), 0), c, bev=0.012)
    bx((w, d, 0.05), (0, 0, h - 0.05), c, bev=0.02)
    paper(-0.15, -0.05, h, rot=8)
    paper(-0.1, 0.0, h + 0.004, rot=-12)
    books_stack(w / 2 - 0.18, 0.12, h, n=3, seed=3)
    cy(0.035, 0.08, (-w / 2 + 0.15, 0.15, h), 'ink', segs=8, bev=0)
    seg((-w / 2 + 0.16, 0.15, h + 0.08), (-w / 2 + 0.2, 0.18, h + 0.2), 0.006, 'white')
    if lamp:
        table_lamp(-w / 2 + 0.17, -0.1, h)
    if with_chair:
        with xf((-0.05, -d / 2 - 0.12), 180):
            chair('wood_d', seat, sit=False)
        slot(act, -0.05, -d / 2 - 0.02, 180)


# =========================================================================== beds
def bed_single(quilt='blue', c='wood_l', stripe='cream', act='sleep'):
    L_, Wd = 1.45, 0.8
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.07, 0.07, 0.3 if sy < 0 else 0.62), (sx * (Wd / 2 - 0.04), sy * (L_ / 2 - 0.04), 0), c, bev=0.015)
    bx((Wd - 0.08, 0.06, 0.4), (0, L_ / 2 - 0.04, 0.18), c, bev=0.02)
    bx((Wd - 0.08, 0.06, 0.18), (0, -L_ / 2 + 0.04, 0.12), c, bev=0.02)
    bx((Wd - 0.04, L_ - 0.1, 0.12), (0, 0, 0.12), c, bev=0.02)
    bx((Wd - 0.1, L_ - 0.16, 0.1), (0, 0, 0.24), 'white', bev=0.04, seg=2)
    bx((Wd - 0.04, L_ * 0.62, 0.06), (0, -L_ * 0.17, 0.3), quilt, bev=0.03, seg=2)
    bx((Wd - 0.03, 0.08, 0.065), (0, -L_ * 0.17 + L_ * 0.31 - 0.06, 0.302), stripe, bev=0.02)
    bx((Wd - 0.26, 0.28, 0.1), (0, L_ / 2 - 0.25, 0.32), 'cream', bev=0.05, seg=2)
    if act:
        slot(act, 0, 0.0, 0, z=0.36)


def bed_double(quilt='rose', c='wood_m', stripe='cream', act='sleep'):
    L_, Wd = 1.5, 1.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.08, 0.08, 0.3 if sy < 0 else 0.72), (sx * (Wd / 2 - 0.05), sy * (L_ / 2 - 0.05), 0), c, bev=0.015)
            if sy > 0:
                sp(0.05, (sx * (Wd / 2 - 0.05), L_ / 2 - 0.05, 0.75), c, segs=8, rings=5)
    bx((Wd - 0.1, 0.06, 0.48), (0, L_ / 2 - 0.05, 0.18), c, bev=0.02)
    extr([(-0.25, 0), (0.25, 0), (0.0, 0.12)], 0.06, loc=(0, L_ / 2 - 0.02, 0.66), rot=(90, 0, 0), c=c)
    bx((Wd - 0.1, 0.06, 0.18), (0, -L_ / 2 + 0.05, 0.12), c, bev=0.02)
    bx((Wd - 0.05, L_ - 0.12, 0.12), (0, 0, 0.12), c, bev=0.02)
    bx((Wd - 0.12, L_ - 0.18, 0.1), (0, 0, 0.24), 'white', bev=0.04, seg=2)
    bx((Wd - 0.05, L_ * 0.62, 0.06), (0, -L_ * 0.17, 0.3), quilt, bev=0.03, seg=2)
    bx((Wd - 0.04, 0.08, 0.065), (0, -L_ * 0.17 + L_ * 0.31 - 0.06, 0.302), stripe, bev=0.02)
    for sx in (-1, 1):
        bx((Wd / 2 - 0.16, 0.26, 0.1), (sx * Wd / 4, L_ / 2 - 0.25, 0.32), 'cream', bev=0.05, seg=2)
    if act:
        slot(act, -Wd / 4, 0.0, 0, z=0.36)
        slot(act, Wd / 4, 0.0, 0, z=0.36)


def crib(c='wood_l', quilt='pink', act='sleep'):
    Wd, L_ = 0.55, 0.85
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.05, 0.05, 0.6), (sx * (Wd / 2 - 0.03), sy * (L_ / 2 - 0.03), 0), c, bev=0.01)
    bx((Wd, L_, 0.06), (0, 0, 0.18), c, bev=0.015)
    bx((Wd - 0.08, L_ - 0.08, 0.06), (0, 0, 0.24), 'white', bev=0.02)
    bx((Wd - 0.08, L_ * 0.5, 0.04), (0, -0.1, 0.3), quilt, bev=0.02)
    for z in (0.22, 0.56):
        for sx in (-1, 1):
            bx((0.04, L_, 0.04), (sx * (Wd / 2 - 0.03), 0, z), c, bev=0)
        for sy in (-1, 1):
            bx((Wd, 0.04, 0.04), (0, sy * (L_ / 2 - 0.03), z), c, bev=0)
    for sx in (-1, 1):
        for i in range(5):
            cy(0.012, 0.3, (sx * (Wd / 2 - 0.03), -L_ / 2 + 0.15 + i * 0.14, 0.26), 'white', segs=5, bev=0)
    # rocker feet
    for sx in (-1, 1):
        bx((0.05, L_ + 0.1, 0.05), (sx * (Wd / 2 - 0.03), 0, 0), c, bev=0.02)
    sp(0.05, (0.08, 0.2, 0.34), 'yellow', segs=8, rings=5)
    if act:
        slot(act, 0, -0.05, 0, z=0.3)


# =========================================================================== heat / kitchen
def stove(pot=True, act=True):
    """Little cast-iron stove on legs, with stovepipe to 2.2 m, kettle on top."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.03, 0.12, (sx * 0.2, sy * 0.17, 0), 'iron', segs=6, bev=0)
    bx((0.55, 0.48, 0.42), (0, 0, 0.1), 'iron', bev=0.04, seg=2, rough=0.5)
    bx((0.6, 0.53, 0.05), (0, 0, 0.52), 'iron_l', bev=0.02, rough=0.5)
    bx((0.3, 0.04, 0.2), (0, -0.24, 0.17), 'charcoal', bev=0.01)
    bx((0.24, 0.02, 0.14), (0, -0.26, 0.2), 'fire', bev=0.0)
    sp(0.025, (0.1, -0.28, 0.27), 'gold', segs=6, rings=4)
    cy(0.07, 1.6, (0.12, 0.12, 0.57), 'iron', segs=10, bev=0)
    cy(0.09, 0.05, (0.12, 0.12, 0.57), 'iron_l', segs=10, bev=0)
    fx('fx_fire', 0, -0.2, 0.25)
    if pot:
        cy(0.11, 0.12, (-0.12, -0.05, 0.57), 'copper', segs=12, r_top=0.08, bev=0.02)
        seg((-0.05, -0.05, 0.69), (0.03, -0.05, 0.62), 0.015, 'copper')
        cy(0.04, 0.03, (-0.12, -0.05, 0.69), 'iron', segs=8, bev=0)
    if act:
        slot('warm', 0, -0.65, 180)


def hearth(w=1.3, d=0.55, tall=True, act=True, mantle_items=True):
    """Stone fireplace, back against +Y.  tall=False stops at the mantle (the building adds the stack)."""
    R = rnd(7)
    cols = ('stone', 'stone_d', 'stone_l', 'stone_w')
    for k, z in enumerate((0.0, 0.25, 0.5, 0.75)):
        for i in range(4):
            x = -w / 2 + w / 4 * (i + 0.5) + (0.06 if k % 2 else 0)
            if abs(x) < 0.32 and z < 0.65:
                continue
            bx((w / 4 + 0.02, d, 0.26), (max(-w / 2 + w / 8, min(w / 2 - w / 8, x)), 0, z), R.choice(cols), bev=0.04)
    bx((0.7, d - 0.15, 0.62), (0, 0.08, 0.0), 'charcoal', bev=0.0)
    bx((w + 0.2, d + 0.1, 0.1), (0, -0.02, 1.0), 'wood_d', bev=0.03)
    bx((w + 0.3, 0.4, 0.06), (0, -d / 2 - 0.15, 0), 'stone_d', bev=0.02)
    # logs + fire
    for i, a in enumerate((-15, 20)):
        K.log_(0.05, 0.42, (0, 0.05 + i * 0.05, 0.08 + i * 0.04), (0, 90, a), 'bark')
    blob(0.11, (0, 0.05, 0.18), 'fire', scale=(1.4, 0.8, 1.3), seed=2, amp=0.25)
    blob(0.06, (0.02, 0.0, 0.2), 'ember', scale=(1.2, 0.8, 1.6), seed=5, amp=0.2)
    fx('fx_fire', 0, 0.05, 0.25)
    if tall:
        for k, z in enumerate((1.1, 1.35, 1.6, 1.85, 2.1)):
            bx((0.8, d - 0.1, 0.25), (0, 0.05, z), cols[(k + 1) % 4], bev=0.04)
        fx('fx_smoke', 0, 0.05, 2.5)
    if mantle_items:
        candle(-w / 2 + 0.15, -0.05, 1.1)
        candle(w / 2 - 0.2, -0.05, 1.1)
        vase(0.25, 0.0, 1.1, seed=4)
        cy(0.08, 0.14, (-0.25, 0.0, 1.1), 'wood_l', segs=10)
        cy(0.065, 0.01, (-0.25, -0.075, 1.17), 'cream', rot=(90, 0, 0), segs=10, bev=0)
    # fire tools
    seg((w / 2 + 0.05, -0.15, 0), (w / 2 + 0.05, -0.15, 0.55), 0.015, 'iron')
    seg((w / 2 + 0.12, -0.15, 0), (w / 2 + 0.12, -0.15, 0.5), 0.015, 'iron')
    if act:
        slot('warm', -0.3, -d / 2 - 0.55, 180)
        slot('warm', 0.3, -d / 2 - 0.55, 180)


def kitchen_counter(w=1.2, d=0.5, top='pale', body='blue_l', items=True, sink=False, act='cook', seed=0):
    h = 0.58
    bx((w, d - 0.04, 0.08), (0, 0.02, 0), 'wood_dd', bev=0.01)
    bx((w - 0.02, d - 0.06, h - 0.13), (0, 0.02, 0.06), body, bev=0.02)
    n = max(1, int(round(w / 0.4)))
    for i in range(n):
        x = -w / 2 + w / n * (i + 0.5)
        bx((w / n - 0.06, 0.03, 0.18), (x, -d / 2 + 0.02, h - 0.3), body, bev=0.015)
        bx((w / n - 0.06, 0.03, 0.2), (x, -d / 2 + 0.02, 0.1), body, bev=0.015)
        bx((0.1, 0.03, 0.025), (x, -d / 2, h - 0.2), 'gold', bev=0)
    bx((w + 0.04, d + 0.02, 0.06), (0, 0, h - 0.06), top, bev=0.015)
    R = rnd(seed)
    if sink:
        bx((0.4, 0.32, 0.02), (w / 2 - 0.28, 0.02, h), 'steel', bev=0.01)
        bx((0.32, 0.24, 0.015), (w / 2 - 0.28, 0.02, h + 0.006), 'water', bev=0)
        seg((w / 2 - 0.28, d / 2 - 0.05, h), (w / 2 - 0.28, d / 2 - 0.05, h + 0.22), 0.015, 'steel')
        seg((w / 2 - 0.28, d / 2 - 0.05, h + 0.22), (w / 2 - 0.28, d / 2 - 0.15, h + 0.18), 0.015, 'steel')
    if items:
        bx((0.3, 0.2, 0.025), (-w / 2 + 0.3, -0.03, h), 'wood_l', bev=0.008)
        for i in range(3):
            cy(0.025, 0.04, (-w / 2 + 0.22 + i * 0.07, -0.03, h + 0.025), ('orange', 'red', 'leaf_l')[i], segs=8, bev=0)
        jar(-w / 2 + 0.15, d / 2 - 0.12, h, 'cream', seed=seed)
        jar(-w / 2 + 0.28, d / 2 - 0.1, h, 'blue_l', seed=seed + 1, s=0.8)
        if not sink:
            bowl(w / 2 - 0.25, 0.0, h, 'cream', fill='flour')
    if act:
        slot(act, 0, -d / 2 - 0.4, 180)


def cooking_range(w=0.8, d=0.55, act='cook'):
    """Small brick cooking range with an iron top, pots and a little fire."""
    bx((w, d, 0.5), (0, 0, 0), 'brick', bev=0.03)
    bx((w + 0.04, d + 0.04, 0.06), (0, 0, 0.5), 'iron', bev=0.02, rough=0.5)
    bx((0.32, 0.04, 0.2), (0, -d / 2, 0.12), 'charcoal', bev=0)
    bx((0.26, 0.02, 0.14), (0, -d / 2 - 0.01, 0.15), 'fire', bev=0)
    cy(0.12, 0.14, (-0.18, 0.0, 0.56), 'iron', segs=12, bev=0.02)
    cy(0.1, 0.01, (-0.18, 0.0, 0.7), 'orange', segs=12, bev=0)
    cy(0.1, 0.06, (0.18, -0.02, 0.56), 'iron_l', segs=12, bev=0.01)
    seg((0.28, -0.02, 0.6), (0.48, -0.05, 0.6), 0.012, 'wood_d')
    cy(0.1, 0.3, (0, 0.18, 0.56), 'stone_d', segs=8, r_top=0.06, bev=0)
    fx('fx_fire', 0, -d / 2 + 0.05, 0.2)
    if act:
        slot(act, 0, -d / 2 - 0.4, 180)


def cupboard(w=0.9, d=0.4, c='wood_m', dish='blue_l', seed=0):
    h = 1.3
    bx((w, d, 0.6), (0, 0, 0), c, bev=0.02)
    for s in (-1, 1):
        bx((w / 2 - 0.05, 0.03, 0.48), (s * w / 4, -d / 2, 0.06), 'wood_l', bev=0.015)
        sp(0.025, (s * 0.06, -d / 2 - 0.02, 0.36), 'gold', segs=6, rings=4)
    bx((w + 0.04, d + 0.04, 0.04), (0, 0, 0.6), 'wood_l', bev=0.01)
    for s in (-1, 1):
        bx((0.05, d * 0.6, h - 0.64), (s * (w / 2 - 0.025), d * 0.2, 0.64), c, bev=0.01)
    bx((w, 0.03, h - 0.64), (0, d / 2 - 0.015, 0.64), c, bev=0)
    for z in (0.92, h - 0.02):
        bx((w, d * 0.6, 0.04), (0, d * 0.2, z), c, bev=0.01)
    bx((w + 0.1, d * 0.7, 0.06), (0, d * 0.18, h + 0.02), c, bev=0.02)
    R = rnd(seed)
    for i in range(5):
        x = -w / 2 + 0.1 + i * (w - 0.2) / 4
        cy(0.08, 0.012, (x, d * 0.33, 0.66 + 0.08), dish, rot=(80, 0, 0), segs=12, bev=0, origin='center')
    for i in range(4):
        x = -w / 2 + 0.14 + i * (w - 0.28) / 3
        mug(x, d * 0.15, 0.96, c=R.choice(['cream', 'red', 'blue_l', 'yellow']))
    jar(w / 2 - 0.14, d * 0.2, h + 0.08, 'terracotta', seed=seed)


def bookshelf(w=0.9, d=0.32, h=1.4, c='wood_d', seed=0, act='read'):
    for s in (-1, 1):
        bx((0.05, d, h), (s * (w / 2 - 0.025), 0, 0), c, bev=0.01)
    bx((w, 0.03, h), (0, d / 2 - 0.015, 0), c, bev=0)
    shelves = [0.04, 0.38, 0.72, 1.06]
    for z in shelves + [h - 0.04]:
        bx((w, d, 0.04), (0, 0, z), c, bev=0.01)
    bx((w + 0.08, d + 0.04, 0.06), (0, 0, h), c, bev=0.02)
    R = rnd(seed)
    for k, z in enumerate(shelves):
        x = -w / 2 + 0.06
        while x < w / 2 - 0.1:
            bw = R.uniform(0.035, 0.06)
            bh = R.uniform(0.2, 0.28)
            if R.random() < 0.12 and k > 0:
                x += 0.08
                continue
            bx((bw, d * 0.75, bh), (x + bw / 2, -0.02, z + 0.04), R.choice(['book_r', 'book_b', 'book_g', 'book_y',
                                                                              'cream', 'purple']), bev=0)
            x += bw + 0.006
    if act:
        slot(act, 0, -d / 2 - 0.42, 180)


def wardrobe(w=0.9, d=0.45, c='wood_m', trim='wood_l'):
    h = 1.6
    bx((w, d, 0.08), (0, 0, 0), 'wood_dd', bev=0.01)
    bx((w, d, h - 0.08), (0, 0, 0.08), c, bev=0.025)
    for s in (-1, 1):
        bx((w / 2 - 0.06, 0.03, h - 0.3), (s * w / 4, -d / 2, 0.16), trim, bev=0.02)
        bx((w / 2 - 0.16, 0.03, 0.5), (s * w / 4, -d / 2 - 0.012, 0.3), c, bev=0.015)
        bx((w / 2 - 0.16, 0.03, 0.5), (s * w / 4, -d / 2 - 0.012, 0.9), c, bev=0.015)
        sp(0.025, (s * 0.06, -d / 2 - 0.03, 0.8), 'gold', segs=6, rings=4)
    bx((w + 0.1, d + 0.06, 0.08), (0, 0, h), trim, bev=0.02)
    extr([(-w / 2, 0), (w / 2, 0), (w / 4, 0.12), (-w / 4, 0.12)], 0.04, loc=(0, -d / 2 + 0.02, h + 0.08),
         rot=(90, 0, 0), c=trim)
    # hat box + folded blanket on top
    cy(0.13, 0.14, (-0.15, 0.0, h + 0.08), 'pink', segs=12)
    bx((0.3, 0.3, 0.1), (0.2, 0.0, h + 0.08), 'blue', bev=0.03)


def toilet(act='toilet'):
    cy(0.12, 0.26, (0, -0.05, 0), 'ceramic', segs=12, r_top=0.16, bev=0.02)
    cy(0.19, 0.04, (0, -0.07, 0.26), 'wood_l', segs=14, bev=0.015)
    bx((0.36, 0.17, 0.32), (0, 0.17, 0.22), 'ceramic', bev=0.04, seg=2)
    bx((0.4, 0.2, 0.04), (0, 0.17, 0.54), 'wood_l', bev=0.015)
    sp(0.025, (0.14, 0.07, 0.48), 'steel', segs=6, rings=4)
    if act:
        slot(act, 0, -0.38, 0)


def sink(act='wash', mirror=False):
    cy(0.06, 0.45, (0, 0.05, 0), 'ceramic', segs=10, r_top=0.08)
    cy(0.24, 0.12, (0, 0.0, 0.44), 'ceramic', segs=16, r_top=0.27, bev=0.02)
    cy(0.2, 0.01, (0, 0.0, 0.555), 'water', segs=16, bev=0)
    seg((0, 0.22, 0.5), (0, 0.22, 0.72), 0.018, 'steel')
    seg((0, 0.22, 0.72), (0, 0.1, 0.68), 0.016, 'steel')
    for s in (-1, 1):
        sp(0.025, (s * 0.07, 0.22, 0.66), 'steel', segs=6, rings=4)
    bx((0.12, 0.08, 0.04), (0.2, 0.12, 0.56), 'pink', bev=0.02)   # soap
    if mirror:
        cy(0.2, 0.04, (0, 0.27, 1.05), 'wood_l', rot=(90, 0, 0), segs=16, origin='center')
        cy(0.16, 0.05, (0, 0.27, 1.05), 'blue_l', rot=(90, 0, 0), segs=16, origin='center', bev=0)
    if act:
        slot(act, 0, -0.5, 180)


def bathtub(act='wash'):
    for sx in (-1, 1):
        for sy in (-1, 1):
            sp(0.06, (sx * 0.45, sy * 0.2, 0.05), 'gold', scale=(1, 1, 0.9), segs=8, rings=5)
    bx((1.2, 0.62, 0.36), (0, 0, 0.08), 'ceramic', bev=0.12, seg=3)
    bx((1.04, 0.46, 0.04), (0, 0, 0.38), 'water', bev=0.06, seg=2)
    for i in range(5):
        sp(0.06, (-0.3 + i * 0.15, 0.08 * (-1) ** i, 0.43), 'white', segs=8, rings=5)
    sp(0.05, (0.2, -0.05, 0.44), 'yellow', scale=(1.3, 1, 0.9), segs=8, rings=5)   # rubber duck
    seg((0.62, 0.0, 0.3), (0.62, 0.0, 0.62), 0.02, 'steel')
    seg((0.62, 0.0, 0.62), (0.5, 0.0, 0.58), 0.02, 'steel')
    if act:
        slot(act, 0, -0.65, 180)


def plant_pot(big=True, seed=0, c='terracotta'):
    s = 1.0 if big else 0.6
    cy(0.16 * s, 0.3 * s, (0, 0, 0), c, segs=12, r_top=0.2 * s, bev=0.02)
    cy(0.21 * s, 0.04 * s, (0, 0, 0.3 * s), c, segs=12, bev=0.01)
    cy(0.18 * s, 0.01, (0, 0, 0.32 * s), 'soil', segs=12, bev=0)
    R = rnd(seed)
    for i in range(5):
        a = math.tau * i / 5 + R.uniform(-0.3, 0.3)
        p = (math.cos(a) * 0.12 * s, math.sin(a) * 0.12 * s, 0.5 * s + R.uniform(0, 0.25) * s)
        seg((0, 0, 0.32 * s), p, 0.012, 'leaf')
        blob(0.11 * s, p, ('leaf', 'leaf_l', 'green')[i % 3], scale=(1.2, 0.8, 0.6), seed=seed + i, amp=0.2,
             subdiv=1, rot=(0, 0, math.degrees(a)))
    blob(0.14 * s, (0, 0, 0.75 * s), 'leaf_l', scale=(1, 1, 1.1), seed=seed + 9, subdiv=1)


def tea_set(tray=True):
    if tray:
        cy(0.22, 0.02, (0, 0, 0), 'wood_l', segs=16, bev=0.008)
    sp(0.09, (0, 0.02, 0.1), 'ceramic', scale=(1, 1, 0.85), segs=12, rings=7)
    cy(0.04, 0.03, (0, 0.02, 0.17), 'ceramic', segs=8, bev=0)
    sp(0.02, (0, 0.02, 0.21), 'blue', segs=6, rings=4)
    seg((0.07, 0.02, 0.09), (0.15, 0.02, 0.15), 0.018, 'ceramic', r2=0.01)
    seg((-0.08, 0.02, 0.14), (-0.12, 0.02, 0.06), 0.012, 'blue')
    for i, (x, y) in enumerate(((-0.12, -0.1), (0.12, -0.1))):
        cy(0.05, 0.008, (x, y, 0.02), 'ceramic', segs=10, bev=0)
        cy(0.032, 0.045, (x, y, 0.028), ('blue_l', 'pink')[i], segs=10, bev=0)


def bread_shelf(w=1.2, d=0.4, act='shop', seed=0):
    h = 1.3
    for s in (-1, 1):
        bx((0.05, d, h), (s * (w / 2 - 0.025), 0, 0), 'wood_m', bev=0.01)
    bx((w, 0.03, h), (0, d / 2 - 0.015, 0), 'wood_m', bev=0)
    R = rnd(seed)
    for k, z in enumerate((0.1, 0.48, 0.86)):
        bx((w, d, 0.04), (0, 0, z), 'wood_l', bev=0.01, rot=(-8 if k else 0, 0, 0))
        bx((w - 0.1, d - 0.08, 0.02), (0, 0, z + 0.04), 'canvas', bev=0)
        n = 4
        for i in range(n):
            x = -w / 2 + 0.15 + i * (w - 0.3) / (n - 1)
            kind = (k + i + seed) % 3
            if kind == 0:
                loaf(x, -0.02, z + 0.06, rot=R.uniform(-20, 20))
            elif kind == 1:
                sp(0.09, (x, -0.02, z + 0.1), 'bread', scale=(1, 1, 0.6), segs=10, rings=6)
                sp(0.05, (x, -0.02, z + 0.14), 'bread_d', scale=(1, 1, 0.5), segs=8, rings=5)
            else:
                for j in range(3):
                    sp(0.045, (x - 0.06 + j * 0.06, -0.04 + 0.03 * (j % 2), z + 0.08), 'bread', scale=(1.3, 1, 0.7),
                       segs=8, rings=5)
    bx((w + 0.1, d + 0.06, 0.06), (0, 0, h), 'wood_m', bev=0.02)
    basket(w / 2 - 0.25, 0, h + 0.06, fill='bread', seed=seed)
    if act:
        slot(act, 0, -d / 2 - 0.45, 180)


def shop_counter(w=1.6, d=0.6, c='wood_m', top='wood_l', front='wood_l', seed=0, act=True, items=True):
    h = 0.6
    bx((w, d, h - 0.06), (0, 0, 0), c, bev=0.02)
    n = max(1, int(round(w / 0.3)))
    for i in range(n):
        bx((w / n - 0.03, 0.04, h - 0.14), (-w / 2 + w / n * (i + 0.5), -d / 2, 0.04), (front, 'wood_m')[i % 2]
           if front == 'wood_l' else front, bev=0.012)
    bx((w + 0.1, d + 0.1, 0.06), (0, 0, h - 0.06), top, bev=0.02)
    if items:
        # scale (balance)
        x = -w / 2 + 0.3
        cy(0.08, 0.03, (x, 0.05, h), 'gold', segs=10, bev=0)
        seg((x, 0.05, h + 0.03), (x, 0.05, h + 0.28), 0.012, 'gold')
        seg((x - 0.16, 0.05, h + 0.28), (x + 0.16, 0.05, h + 0.28), 0.01, 'gold')
        for s in (-1, 1):
            cy(0.07, 0.015, (x + s * 0.16, 0.05, h + 0.16), 'gold', segs=10, bev=0)
            seg((x + s * 0.16, 0.05, h + 0.17), (x + s * 0.16, 0.05, h + 0.28), 0.004, 'iron')
        bx((0.24, 0.18, 0.12), (w / 2 - 0.25, 0.08, h), 'red_d', bev=0.02)
        bx((0.25, 0.19, 0.03), (w / 2 - 0.25, 0.08, h + 0.12), 'gold', bev=0.01)
        jar(0.0, 0.1, h, 'cream', seed=seed, s=0.9)
        for i in range(4):
            sp(0.025, (0.08 + i * 0.04, 0.0, h + 0.02), ('red', 'yellow', 'pink', 'green')[i], segs=6, rings=4)
    if act:
        slot('sell', 0, d / 2 + 0.35, 0)
        slot('shop', 0, -d / 2 - 0.45, 180)


def barrel_in(r=0.28, h=0.7, c=('wood_m', 'wood_l'), tap=False, lid=True):
    M_ = 14
    for j in range(M_):
        a = math.tau * (j + 0.5) / M_
        bulge = r * 1.08
        bx((2 * math.pi * r / M_ * 1.12, 0.05, h), (math.cos(a) * bulge * 0.95, math.sin(a) * bulge * 0.95, 0),
           c[j % 2], rot=(0, 0, math.degrees(a) + 90), bev=0.0)
    cy(r * 1.02, h - 0.04, (0, 0, 0.02), c[0], segs=M_, bev=0)
    for z in (0.12, h - 0.16):
        cy(r * 1.1, 0.05, (0, 0, z), 'iron', segs=M_, bev=0)
    if lid:
        cy(r * 0.98, 0.02, (0, 0, h - 0.02), 'wood_l', segs=M_, bev=0)
    if tap:
        seg((0, -r * 1.05, 0.2), (0, -r * 1.05 - 0.1, 0.2), 0.02, 'copper')
        seg((0, -r * 1.05 - 0.1, 0.2), (0, -r * 1.05 - 0.1, 0.15), 0.015, 'copper')


def crate_in(s=0.55, c='wood_l', fill=None, seed=0):
    t = 0.06
    bx((s - 0.04, s - 0.04, s - 0.04), (0, 0, 0.02), 'wood_m', bev=0.01)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((t, t, s), (sx * (s - t) / 2, sy * (s - t) / 2, 0), c, bev=0.012)
    for z in (0, s - t):
        for sy in (-1, 1):
            bx((s, t, t), (0, sy * (s - t) / 2, z), c, bev=0.012)
            bx((t, s, t), (sy * (s - t) / 2, 0, z), c, bev=0.012)
    bx((0.05, 0.04, (s - 2 * t) * 1.3), (0, -s / 2 - 0.005, s / 2), c, rot=(0, 45, 0), bev=0, origin='center')
    if fill:
        R = rnd(seed)
        for i in range(6):
            sp(0.07, (R.uniform(-0.15, 0.15), R.uniform(-0.15, 0.15), s - 0.02 + R.uniform(0, 0.04)), fill, segs=8,
               rings=5)


def notice_board_in(act='read'):
    for s in (-1, 1):
        bx((0.08, 0.08, 1.4), (s * 0.52, 0, 0), 'wood_d', bev=0.015)
    bx((1.0, 0.06, 0.7), (0, 0, 0.62), 'wood_m', bev=0.02)
    bx((0.92, 0.07, 0.62), (0, -0.005, 0.66), 'cork' if 'cork' in K.P else 'straw_d', bev=0.0)
    R = rnd(5)
    for i in range(6):
        x = -0.32 + (i % 3) * 0.32 + R.uniform(-0.04, 0.04)
        z = 0.75 + (i // 3) * 0.28 + R.uniform(-0.03, 0.03)
        bx((0.18, 0.012, 0.2), (x, -0.045, z), R.choice(['paper', 'cream', 'pink', 'blue_l', 'yellow']),
           rot=(0, R.uniform(-8, 8), 0), bev=0)
        sp(0.015, (x, -0.055, z + 0.17), R.choice(['red', 'blue', 'green']), segs=6, rings=4)
    bx((1.12, 0.14, 0.08), (0, 0, 1.33), 'red', bev=0.02)
    if act:
        slot(act, 0, -0.5, 180)


# =========================================================================== soft furnishing / lighting
def rug_round(r=0.9, c='red', border='cream', inner='mustard'):
    cy(r, 0.015, (0, 0, 0), border, segs=28, bev=0)
    cy(r - 0.08, 0.018, (0, 0, 0), c, segs=28, bev=0)
    cy(r * 0.45, 0.021, (0, 0, 0), inner, segs=24, bev=0)


def rug_long(w=1.8, d=1.0, c='blue', border='cream', stripe='red'):
    bx((w, d, 0.015), (0, 0, 0), border, bev=0)
    bx((w - 0.14, d - 0.14, 0.018), (0, 0, 0), c, bev=0)
    for s in (-1, 1):
        bx((0.08, d - 0.14, 0.021), (s * (w / 2 - 0.25), 0, 0), stripe, bev=0)
    bx((w * 0.3, d * 0.3, 0.021), (0, 0, 0), stripe, bev=0, rot=(0, 0, 0))
    for s in (-1, 1):
        for i in range(7):
            bx((0.03, 0.06, 0.01), (s * (w / 2 + 0.02), -d / 2 + 0.1 + i * (d - 0.2) / 6, 0), border, bev=0,
               rot=(0, 0, 90))


def lamp_floor(shade='lamp'):
    cy(0.14, 0.04, (0, 0, 0), 'wood_d', segs=12, bev=0.01)
    cy(0.025, 1.2, (0, 0, 0.04), 'wood_d', segs=8, bev=0)
    cy(0.2, 0.22, (0, 0, 1.12), shade, segs=14, r_top=0.12, bev=0.01)
    fx('fx_light', 0, 0, 1.2)


def table_lamp(x, y, z, shade='lamp'):
    cy(0.06, 0.03, (x, y, z), 'wood_d', segs=10, bev=0)
    cy(0.015, 0.16, (x, y, z + 0.03), 'gold', segs=6, bev=0)
    cy(0.1, 0.12, (x, y, z + 0.15), shade, segs=12, r_top=0.06, bev=0)
    fx('fx_light', x, y, z + 0.2)


def candle(x, y, z):
    cy(0.04, 0.02, (x, y, z), 'gold', segs=8, bev=0)
    cy(0.022, 0.1, (x, y, z + 0.02), 'cream', segs=8, bev=0)
    sp(0.018, (x, y, z + 0.14), 'ember', scale=(1, 1, 1.6), segs=6, rings=4)


def vase(x, y, z, c='blue_l', seed=0):
    cy(0.05, 0.14, (x, y, z), c, segs=10, r_top=0.035, bev=0.01)
    R = rnd(seed)
    for i in range(4):
        a = math.tau * i / 4 + R.uniform(0, 0.6)
        tip = (x + math.cos(a) * 0.07, y + math.sin(a) * 0.07, z + 0.26 + R.uniform(0, 0.05))
        seg((x, y, z + 0.12), tip, 0.006, 'leaf')
        sp(0.035, tip, ('red', 'yellow', 'pink', 'white')[(i + seed) % 4], segs=8, rings=5)


def jar(x, y, z, c='cream', seed=0, s=1.0):
    cy(0.06 * s, 0.14 * s, (x, y, z), c, segs=10, bev=0.012)
    cy(0.045 * s, 0.03 * s, (x, y, z + 0.14 * s), 'wood_d', segs=10, bev=0)


def mug(x, y, z, c='cream'):
    cy(0.035, 0.07, (x, y, z), c, segs=10, bev=0.008)
    cy(0.028, 0.012, (x + 0.04, y, z + 0.035), c, rot=(90, 0, 0), segs=8, bev=0, origin='center')


def plate(x, y, z, food=True, seed=0):
    cy(0.09, 0.014, (x, y, z), 'ceramic', segs=14, bev=0.004)
    if food:
        k = seed % 3
        if k == 0:
            sp(0.045, (x, y, z + 0.025), 'bread', scale=(1.3, 1, 0.7), segs=8, rings=5)
        elif k == 1:
            sp(0.05, (x, y, z + 0.015), 'orange', scale=(1, 1, 0.4), segs=8, rings=5)
            sp(0.02, (x + 0.03, y, z + 0.03), 'leaf_l', segs=6, rings=4)
        else:
            sp(0.035, (x - 0.02, y, z + 0.03), 'red', segs=8, rings=5)
            sp(0.035, (x + 0.03, y + 0.01, z + 0.03), 'green', segs=8, rings=5)


def bowl(x, y, z, c='cream', fill=None):
    cy(0.05, 0.03, (x, y, z), c, segs=12, r_top=0.11, bev=0.008)
    cy(0.1, 0.04, (x, y, z + 0.03), c, segs=12, r_top=0.12, bev=0.008)
    if fill:
        sp(0.1, (x, y, z + 0.06), fill, scale=(1, 1, 0.35), segs=12, rings=6)


def basket(x, y, z, fill='bread', seed=0, r=0.15):
    cy(r * 0.8, r * 0.6, (x, y, z), 'straw_d', segs=12, r_top=r, bev=0.01)
    seg((x - r * 0.9, y, z + r * 0.6), (x, y, z + r * 1.4), 0.012, 'straw_d')
    seg((x, y, z + r * 1.4), (x + r * 0.9, y, z + r * 0.6), 0.012, 'straw_d')
    if fill:
        R = rnd(seed)
        for i in range(4):
            sp(r * 0.35, (x + R.uniform(-r * 0.4, r * 0.4), y + R.uniform(-r * 0.4, r * 0.4), z + r * 0.62), fill,
               scale=(1.3, 1, 0.8), segs=8, rings=5)


def loaf(x, y, z, rot=0.0):
    sp(0.1, (x, y, z + 0.05), 'bread', scale=(1.5, 0.85, 0.65), rot=(0, 0, rot), segs=12, rings=6)
    for i in (-1, 0, 1):
        bx((0.02, 0.1, 0.012), (x + i * 0.06, y, z + 0.1), 'flour', rot=(0, 0, rot + 20), bev=0)


def books_stack(x, y, z, n=3, seed=0):
    R = rnd(seed)
    zz = z
    for i in range(n):
        h = R.uniform(0.03, 0.05)
        bx((0.2, 0.15, h), (x, y, zz), R.choice(['book_r', 'book_b', 'book_g', 'book_y']), rot=(0, 0, R.uniform(-15, 15)),
           bev=0.005)
        zz += h


def paper(x, y, z, rot=0.0, c='paper'):
    bx((0.16, 0.22, 0.004), (x, y, z), c, rot=(0, 0, rot), bev=0)


def cushion(x, y, z, c='yellow', rot=0.0):
    bx((0.3, 0.3, 0.1), (x, y, z), c, rot=(0, 0, rot), bev=0.04, seg=2)


def sack(x, y, z=0.0, c='sack', s=1.0, seed=0, flour=True):
    sp(0.2 * s, (x, y, z + 0.2 * s), c, scale=(1, 0.85, 1.1), segs=12, rings=7)
    cy(0.06 * s, 0.1 * s, (x, y, z + 0.4 * s), c, segs=8, bev=0)
    cy(0.065 * s, 0.03 * s, (x, y, z + 0.4 * s), 'rope', segs=8, bev=0)
    if flour:
        sp(0.06 * s, (x, y, z + 0.5 * s), 'flour', scale=(1.2, 1.2, 0.5), segs=8, rings=5)


def broom(x, y, z=0.0, lean=12):
    with xf((x, y, z), 0):
        with xf((0, 0, 0), 0):
            seg((0, 0, 0.18), (math.sin(math.radians(lean)) * 0.9, 0, 1.05), 0.018, 'wood_l')
            cy(0.09, 0.2, (0, 0, 0), 'straw', segs=8, r_top=0.03, bev=0)


def coat_rack(c='wood_d', seed=0):
    cy(0.14, 0.04, (0, 0, 0), c, segs=10, bev=0.01)
    cy(0.025, 1.3, (0, 0, 0.04), c, segs=8, bev=0)
    for i in range(4):
        a = math.tau * i / 4
        seg((0, 0, 1.2), (math.cos(a) * 0.14, math.sin(a) * 0.14, 1.3), 0.012, c)
    sp(0.1, (0.12, 0, 1.1), 'red', scale=(0.8, 0.8, 1.5), segs=10, rings=6)       # coat
    cy(0.12, 0.06, (-0.1, 0.05, 1.32), 'navy', segs=10, bev=0.01)                   # hat brim
    cy(0.07, 0.08, (-0.1, 0.05, 1.37), 'navy', segs=10, bev=0.01)


def toy_blocks(seed=0):
    R = rnd(seed)
    for i in range(5):
        bx((0.1, 0.1, 0.1), (R.uniform(-0.2, 0.2), R.uniform(-0.2, 0.2), 0), R.choice(['red', 'yellow', 'blue',
                                                                                       'green']),
           rot=(0, 0, R.uniform(0, 90)), bev=0.015)
    bx((0.1, 0.1, 0.1), (0.0, 0.0, 0.1), 'pink', rot=(0, 0, 30), bev=0.015)
    # rocking horse-ish duck
    sp(0.1, (0.3, 0.1, 0.12), 'yellow', scale=(1.3, 1, 1), segs=10, rings=6)
    sp(0.07, (0.4, 0.1, 0.25), 'yellow', segs=10, rings=6)
    bx((0.05, 0.03, 0.02), (0.48, 0.1, 0.25), 'orange', bev=0)
    bx((0.35, 0.06, 0.03), (0.3, 0.1, 0.0), 'red', bev=0.01)


def wall_shelf(w=0.8, seed=0, items='jars'):
    """Hanging shelf: back at +Y (wall), bottom at z=0 of the frame (place at z ~1.2)."""
    bx((w, 0.22, 0.04), (0, 0, 0), 'wood_m', bev=0.01)
    for s in (-1, 1):
        extr([(0, 0), (0.18, 0), (0, -0.16)], 0.03, loc=(s * (w / 2 - 0.08) - 0.015, 0.1, 0), rot=(90, 0, 270),
             c='wood_d')
    R = rnd(seed)
    x = -w / 2 + 0.1
    while x < w / 2 - 0.08:
        if items == 'jars':
            jar(x, 0, 0.04, R.choice(['cream', 'blue_l', 'terracotta', 'yellow']), seed=seed, s=R.uniform(0.7, 1.0))
            x += 0.15
        elif items == 'books':
            bw = R.uniform(0.04, 0.06)
            bx((bw, 0.15, R.uniform(0.15, 0.22)), (x, 0, 0.04), R.choice(['book_r', 'book_b', 'book_g', 'book_y']),
               bev=0.004)
            x += bw + 0.005
        else:
            cy(0.07, 0.01, (x + 0.05, 0.03, 0.12), 'ceramic', rot=(75, 0, 0), segs=12, bev=0, origin='center')
            x += 0.15


def picture(w=0.5, h=0.4, c='wood_d', art=('blue_l', 'leaf_l', 'yellow'), seed=0):
    """Framed picture: back at +Y (wall), centre at z = 0 of the frame."""
    bx((w, 0.04, h), (0, 0, -h / 2), c, bev=0.012)
    bx((w - 0.08, 0.045, h - 0.08), (0, -0.004, -h / 2 + 0.04), art[0], bev=0)
    # simple landscape: hill + sun
    sp(h * 0.45, (-w * 0.1, -0.03, -h / 2 + 0.04), art[1], scale=(1.4, 0.05, 0.6), segs=12, rings=6)
    sp(0.045, (w * 0.22, -0.03, h * 0.18), art[2], scale=(1, 0.3, 1), segs=8, rings=5)


def clock(r=0.17):
    cy(r, 0.05, (0, 0, 0), 'wood_d', rot=(90, 0, 0), segs=16, origin='center')
    cy(r - 0.03, 0.055, (0, 0, 0), 'cream', rot=(90, 0, 0), segs=16, origin='center', bev=0)
    bx((0.015, 0.06, r * 0.6), (0, -0.01, 0), 'ink', bev=0)
    bx((r * 0.45, 0.06, 0.015), (r * 0.2, -0.01, 0), 'ink', bev=0)


def tool_rack(w=1.2, tools=('axe', 'saw', 'shovel', 'pick', 'rake')):
    """Wall board with hanging tools; back at +Y; bottom of board at z=0 of frame."""
    bx((w, 0.05, 0.6), (0, 0, 0), 'wood_m', bev=0.015)
    n = len(tools)
    for i, t in enumerate(tools):
        x = -w / 2 + w / n * (i + 0.5)
        cy(0.015, 0.06, (x, -0.04, 0.5), 'iron', rot=(90, 0, 0), segs=6, bev=0, origin='center')
        with xf((x, -0.06, 0)):
            hang_tool(t)


def hang_tool(t):
    if t == 'axe':
        seg((0, 0, 0.55), (0, 0, -0.1), 0.02, 'wood_l')
        bx((0.18, 0.03, 0.1), (0.07, 0, -0.1), 'steel', bev=0.01)
    elif t == 'saw':
        bx((0.14, 0.04, 0.06), (0, 0, 0.42), 'wood_l', bev=0.01)
        extr([(-0.06, 0), (0.06, 0), (0.03, -0.5), (-0.03, -0.5)], 0.01, loc=(0, 0.005, 0.42), rot=(90, 0, 0),
             c='steel', bev=0)
    elif t == 'shovel':
        seg((0, 0, 0.55), (0, 0, -0.05), 0.018, 'wood_l')
        bx((0.16, 0.02, 0.2), (0, 0, -0.25), 'iron_l', bev=0.02)
    elif t == 'pick':
        seg((0, 0, 0.55), (0, 0, -0.1), 0.018, 'wood_l')
        seg((-0.18, 0, -0.08), (0.18, 0, -0.08), 0.025, 'iron_l', r2=0.008)
    elif t == 'rake':
        seg((0, 0, 0.55), (0, 0, -0.15), 0.015, 'wood_l')
        bx((0.26, 0.03, 0.03), (0, 0, -0.18), 'iron', bev=0)
        for i in range(6):
            seg((-0.12 + i * 0.048, 0, -0.18), (-0.12 + i * 0.048, -0.0, -0.26), 0.008, 'iron')
    elif t == 'hammer':
        seg((0, 0, 0.5), (0, 0, 0.1), 0.015, 'wood_l')
        bx((0.14, 0.05, 0.06), (0, 0, 0.08), 'iron', bev=0.01)
    elif t == 'scythe':
        seg((0, 0, 0.55), (0, 0, -0.4), 0.016, 'wood_l')
        extr([(0, 0), (0.35, 0.05), (0.32, 0.1), (0, 0.07)], 0.01, loc=(0, 0.005, -0.42), rot=(90, 0, 0),
             c='steel', bev=0)


def workbench(w=1.4, d=0.6, act='work', vise=True, seed=0, items=True):
    h = 0.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.08, 0.08, h - 0.08), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), 0), 'wood_d', bev=0.015)
        bx((0.06, d - 0.1, 0.06), (sx * (w / 2 - 0.08), 0, 0.12), 'wood_d', bev=0)
    bx((w - 0.1, d - 0.1, 0.03), (0, 0, 0.14), 'wood_m', bev=0)
    for i in range(3):
        bx((w, d / 3 - 0.01, 0.08), (0, -d / 2 + d / 3 * (i + 0.5), h - 0.08), ('wood_l', 'wood_m', 'plank')[i],
           bev=0.015)
    if vise:
        bx((0.14, 0.1, 0.1), (w / 2 - 0.15, -d / 2 + 0.02, h - 0.04), 'iron', bev=0.01)
        seg((w / 2 - 0.15, -d / 2 - 0.05, h), (w / 2 - 0.15, -d / 2 - 0.15, h), 0.012, 'iron_l')
    if items:
        bx((0.5, 0.12, 0.05), (-0.15, 0.05, h), 'plank', rot=(0, 0, 12), bev=0.008)
        with xf((0.25, -0.05, h)):
            seg((0, 0, 0.02), (0.22, 0.05, 0.02), 0.014, 'wood_l')
            bx((0.05, 0.12, 0.05), (0, 0, 0), 'iron', bev=0.01)
        for i in range(5):
            sp(0.03, (-0.5 + i * 0.03, -0.15, h + 0.015), 'wood_l', scale=(1, 0.6, 0.4), segs=6, rings=4)   # shavings
        # boxes / logs below
        crate_mini(-w / 2 + 0.3, 0.02, 0.17)
    if act:
        slot(act, 0, -d / 2 - 0.4, 180)


def crate_mini(x, y, z):
    bx((0.3, 0.25, 0.18), (x, y, z), 'wood_l', bev=0.015)
    bx((0.26, 0.21, 0.02), (x, y, z + 0.17), 'iron_l', bev=0)


# =========================================================================== production
def bread_oven(w=1.4, d=1.2, act='bake'):
    """Brick dome oven with a glowing mouth (front -Y)."""
    R = rnd(3)
    bx((w, d, 0.55), (0, 0, 0), 'stone', bev=0.04)
    bx((w + 0.06, d + 0.06, 0.06), (0, 0, 0.55), 'stone_l', bev=0.02)
    sp(w * 0.45, (0, 0.05, 0.6), 'brick', scale=(1, d / w * 0.95, 0.75), segs=18, rings=9)
    for i in range(14):
        a = R.uniform(0, math.tau)
        e = R.uniform(0.2, 1.1)
        rr = w * 0.45
        p = (math.cos(a) * math.cos(e) * rr, 0.05 + math.sin(a) * math.cos(e) * rr * d / w * 0.95,
             0.6 + math.sin(e) * rr * 0.75)
        bx((0.14, 0.14, 0.08), p, R.choice(['brick_d', 'mortar', 'brick']), rot=(R.uniform(-20, 20), 0,
                                                                                 math.degrees(a)), bev=0.02,
           origin='center')
    # mouth arch
    with xf((0, -d / 2 + 0.05, 0.6)):
        pts = []
        for i in range(9):
            t = math.pi * i / 8
            pts.append((0.32 * math.cos(t), 0.32 * math.sin(t)))
        pts = [(0.32, -0.0)] + pts + [(-0.32, 0.0)]
        extr(pts[::-1], 0.12, loc=(0, -0.05, 0), rot=(90, 0, 0), c='charcoal', bev=0.0)
        extr([(p[0] * 0.8, p[1] * 0.8) for p in pts][::-1], 0.1, loc=(0, -0.04, 0), rot=(90, 0, 0), c='fire',
             bev=0.0)
        blob(0.1, (0, 0.05, 0.05), 'ember', scale=(1.5, 1, 0.6), seed=1)
    cy(0.13, 0.9, (0.2, 0.25, 1.15), 'brick_d', segs=10, bev=0.01)
    cy(0.16, 0.06, (0.2, 0.25, 2.05), 'stone_d', segs=10, bev=0.01)
    fx('fx_fire', 0, -d / 2 + 0.1, 0.7)
    fx('fx_smoke', 0.2, 0.25, 2.2)
    # peel + logs beside
    seg((w / 2 + 0.1, -0.2, 0), (w / 2 + 0.1, -0.3, 1.3), 0.018, 'wood_l')
    bx((0.22, 0.03, 0.26), (w / 2 + 0.1, -0.2, 0.0), 'wood_l', rot=(0, 0, 90), bev=0.02)
    for i in range(3):
        K.log_(0.06, 0.45, (-w / 2 - 0.15, -0.2 + i * 0.13, 0.06), (90, 0, 0), 'bark')
    K.log_(0.06, 0.45, (-w / 2 - 0.15, -0.135, 0.17), (90, 0, 0), 'bark')
    if act:
        slot(act, 0, -d / 2 - 0.45, 180)


def dough_table(w=1.3, d=0.65, act='bake'):
    h = 0.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.08, 0.08, h - 0.06), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), 0), 'wood_m', bev=0.015)
    bx((w - 0.1, d - 0.1, 0.03), (0, 0, 0.12), 'wood_m', bev=0)
    bx((w, d, 0.07), (0, 0, h - 0.07), 'pale', bev=0.02)
    bx((w * 0.7, d * 0.6, 0.008), (0, 0, h), 'flour', bev=0)
    for i in range(3):
        sp(0.08, (-0.3 + i * 0.28, 0.05 * (-1) ** i, h + 0.04), 'cream', scale=(1.2, 1, 0.55), segs=10, rings=6)
    cy(0.035, 0.36, (0.1, -0.15, h + 0.035), 'wood_l', rot=(0, 90, 15), segs=8, bev=0, origin='center')
    bowl(w / 2 - 0.2, 0.15, h, 'blue_l', fill='flour')
    sack(-w / 2 + 0.15, 0.05, 0.15, s=0.6, flour=True)
    if act:
        slot(act, 0, -d / 2 - 0.4, 180)


def hay_pile(w=1.2, d=1.0, h=0.6, seed=0):
    blob(0.5, (0, 0, 0.0), 'straw', scale=(w, d, h * 1.8), seed=seed, amp=0.15, flat_bottom=0.02)
    R = rnd(seed)
    for i in range(12):
        a = R.uniform(0, 6.28)
        rr = R.uniform(0.2, 0.5)
        p = (math.cos(a) * rr * w, math.sin(a) * rr * d, R.uniform(0.15, h * 0.75))
        seg(p, (p[0] + R.uniform(-0.15, 0.15), p[1] + R.uniform(-0.15, 0.15), p[2] + 0.1), 0.012, 'straw_d')


def hay_bale(rot=0.0):
    bx((0.7, 0.45, 0.4), (0, 0, 0), 'straw', rot=(0, 0, rot), bev=0.06, seg=2)
    for s in (-1, 1):
        bx((0.04, 0.47, 0.42), (s * 0.18, 0, -0.01), 'rope', rot=(0, 0, rot), bev=0.01)


def cot(act='sleep', blanket='red'):
    """Small straw-mattress cot (farm hand)."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.06, 0.06, 0.22), (sx * 0.33, sy * 0.65, 0), 'wood_d', bev=0.01)
    bx((0.74, 1.4, 0.06), (0, 0, 0.18), 'wood_m', bev=0.015)
    bx((0.68, 1.32, 0.08), (0, 0, 0.24), 'straw', bev=0.03)
    bx((0.7, 0.75, 0.04), (0, -0.25, 0.31), blanket, bev=0.02)
    bx((0.4, 0.22, 0.08), (0, 0.5, 0.31), 'canvas', bev=0.03)
    if act:
        slot(act, 0, 0, 0, z=0.33)


def millstone(act='work'):
    cy(0.75, 0.35, (0, 0, 0), 'wood_m', segs=20, bev=0.03)
    cy(0.7, 0.18, (0, 0, 0.35), 'stone_l', segs=20, bev=0.03)
    cy(0.62, 0.2, (0, 0, 0.53), 'stone', segs=20, bev=0.04)
    cy(0.1, 0.05, (0, 0, 0.73), 'charcoal', segs=10, bev=0)
    cy(0.06, 2.6, (0, 0, 0.73), 'wood_d', segs=10, bev=0)     # drive shaft up to the cap
    # hopper
    bx((0.45, 0.45, 0.35), (0, 0, 1.0), 'wood_l', taper=(1.6, 1.6), bev=0.02)
    sp(0.25, (0, 0, 1.3), 'wheat', scale=(1.1, 1.1, 0.35), segs=12, rings=6)
    bx((0.06, 0.4, 0.06), (0, 0.32, 0.85), 'wood_d', bev=0)
    bx((0.12, 0.2, 0.04), (0.0, -0.66, 0.36), 'wood_l', rot=(-25, 0, 0), bev=0)   # chute
    sp(0.12, (0, -0.85, 0.12), 'flour', scale=(1.2, 1.2, 0.5), segs=10, rings=6)
    if act:
        slot(act, 0.0, -1.05, 180)


def saw_bench(w=2.2, d=0.7, act='work'):
    """Long saw table with a big round blade and a log being cut."""
    h = 0.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.1, 0.1, h - 0.06), (sx * (w / 2 - 0.12), sy * (d / 2 - 0.1), 0), 'wood_d', bev=0.015)
        bx((0.08, d - 0.1, 0.08), (sx * (w / 2 - 0.12), 0, 0.15), 'wood_d', bev=0)
    for i in range(3):
        bx((w, d / 3 - 0.01, 0.07), (0, -d / 2 + d / 3 * (i + 0.5), h - 0.07), ('wood_l', 'plank', 'wood_m')[i],
           bev=0.015)
    cy(0.38, 0.03, (0.15, 0, h + 0.05), 'steel', rot=(90, 0, 0), segs=24, origin='center', bev=0)
    cy(0.06, 0.06, (0.15, 0, h + 0.05), 'iron', rot=(90, 0, 0), segs=10, origin='center', bev=0)
    for i in range(16):
        a = math.tau * i / 16
        bx((0.05, 0.03, 0.05), (0.15 + math.cos(a) * 0.38, 0, h + 0.05 + math.sin(a) * 0.38), 'steel',
           rot=(0, -math.degrees(a) + 45, 0), bev=0, origin='center')
    bx((0.25, 0.14, 0.3), (0.15, 0.32, 0.18), 'iron', bev=0.02)      # motor box / gear
    K.log_(0.13, 1.1, (-0.55, 0.0, h + 0.13), (0, 90, 0), 'bark')
    for i in range(6):
        sp(0.05, (0.2 + i * 0.07, -0.25 + (i % 2) * 0.1, 0.03), 'pale', scale=(1, 1, 0.3), segs=6, rings=4)
    if act:
        slot(act, -0.3, -d / 2 - 0.4, 180)


def plank_stack(w=1.6, n=6, seed=0):
    R = rnd(seed)
    for i in range(n):
        z = i * 0.07
        bx((w + R.uniform(-0.1, 0.1), 0.3, 0.06), (R.uniform(-0.03, 0.03), 0, z), R.choice(['plank', 'pale', 'plank2']),
           rot=(0, 0, R.uniform(-2, 2)), bev=0.012)


def log_stack(n_bottom=4, r=0.13, length=1.2, seed=0, snow_top=True):
    R = rnd(seed)
    for row in range(n_bottom):
        n = n_bottom - row
        for i in range(n):
            y = (i - (n - 1) / 2) * 2 * r * 1.02
            z = r + row * r * 1.75
            K.log_(r * R.uniform(0.92, 1.05), length * R.uniform(0.94, 1.06), (R.uniform(-0.04, 0.04), y, z),
                   (0, 90, 0), R.choice(['bark', 'log2', 'wood_d']))
    if snow_top:
        snowcap(length * 0.4, (0, 0, r + (n_bottom - 1) * r * 1.75 + r - 0.04), 0.08, seed, scale=(1.0, 0.6, 1.0))


def chop_stump(act='work'):
    """Chopping block stump with an axe stuck in it and split wood around."""
    cy(0.3, 0.42, (0, 0, 0), 'bark', segs=14, cap='end', bev=0.03)
    for i in range(5):
        a = math.tau * i / 5
        bx((0.12, 0.12, 0.12), (math.cos(a) * 0.3, math.sin(a) * 0.3, 0), 'bark', rot=(0, 0, math.degrees(a)),
           bev=0.03)
    with xf((0.05, 0.02, 0.42), 0):
        bx((0.04, 0.2, 0.12), (0, 0, -0.05), 'steel', rot=(0, 20, 0), bev=0.01)
        seg((0, 0.08, 0.02), (0.22, 0.45, 0.35), 0.022, 'wood_l')
    R = rnd(2)
    for i in range(5):
        a = R.uniform(0, 6.28)
        rr = R.uniform(0.5, 0.75)
        bx((0.1, 0.1, 0.35), (math.cos(a) * rr, math.sin(a) * rr, 0.05), R.choice(['end', 'pale']),
           rot=(90, 0, math.degrees(a)), bev=0.02)
    if act:
        slot(act, 0, -0.65, 180)


def stone_pile(w=1.4, seed=0, snow_on=True, cut=True):
    R = rnd(seed)
    for i in range(10):
        a = R.uniform(0, 6.28)
        rr = R.uniform(0, w * 0.4)
        z = 0.0 if rr > w * 0.25 else R.uniform(0.15, 0.3)
        if cut and i % 2:
            bx((0.35, 0.25, 0.22), (math.cos(a) * rr, math.sin(a) * rr, z), R.choice(['stone', 'stone_l', 'stone_w']),
               rot=(0, 0, math.degrees(a)), bev=0.04)
        else:
            blob(R.uniform(0.18, 0.28), (math.cos(a) * rr, math.sin(a) * rr, z + 0.12),
                 R.choice(['stone', 'stone_d', 'stone_l']), scale=(1.2, 1, 0.8), seed=seed * 7 + i, facet=True,
                 subdiv=1)
    if snow_on:
        snowcap(0.25, (0, 0, 0.45), 0.07, seed)


def anvil_block(act='work'):
    """Stone-cutter's block: big flat stone on a stump, chisel + mallet."""
    cy(0.28, 0.35, (0, 0, 0), 'bark', segs=12, cap='end', bev=0.02)
    bx((0.6, 0.45, 0.2), (0, 0, 0.35), 'stone_l', bev=0.05)
    bx((0.24, 0.2, 0.15), (0.05, 0.0, 0.55), 'stone', bev=0.04)
    seg((-0.15, -0.1, 0.57), (-0.05, 0.12, 0.6), 0.015, 'steel')
    bx((0.14, 0.08, 0.08), (0.24, -0.1, 0.55), 'wood_m', bev=0.02)
    seg((0.24, -0.1, 0.59), (0.35, -0.12, 0.85), 0.015, 'wood_l')
    if act:
        slot(act, 0, -0.62, 180)


def bar_counter(w=2.6, d=0.6, act=True, seed=0):
    """Tavern bar with taps, mugs and bottles. Front (customer side) -Y."""
    h = 0.62
    bx((w, d, h - 0.06), (0, 0, 0), 'wood_d', bev=0.02)
    n = int(round(w / 0.3))
    for i in range(n):
        bx((w / n - 0.04, 0.04, h - 0.18), (-w / 2 + w / n * (i + 0.5), -d / 2, 0.06), ('wood_m', 'wood_l')[i % 2],
           bev=0.012)
    bx((w, 0.06, 0.06), (0, -d / 2 - 0.05, 0.08), 'copper', bev=0.02)        # foot rail
    bx((w + 0.12, d + 0.12, 0.07), (0, 0, h - 0.06), 'wood_m', bev=0.025)
    R = rnd(seed)
    for i in range(3):
        x = -0.4 + i * 0.25
        seg((x, 0.1, h), (x, 0.1, h + 0.25), 0.02, 'copper')
        seg((x, 0.1, h + 0.25), (x, -0.02, h + 0.22), 0.018, 'copper')
        sp(0.03, (x, 0.1, h + 0.3), ('red', 'gold', 'green')[i], segs=6, rings=4)
    for i in range(5):
        mug(-w / 2 + 0.2 + i * 0.15, -0.12 + 0.05 * (i % 2), h + 0.01, c='gold' if i % 2 else 'cream')
    for i in range(3):
        x = w / 2 - 0.3 - i * 0.12
        cy(0.04, 0.18, (x, 0.12, h + 0.01), R.choice(['green', 'leaf', 'red_d']), segs=8, bev=0.01)
        cy(0.015, 0.06, (x, 0.12, h + 0.19), 'cream', segs=6, bev=0)
    bowl(0.5, -0.05, h + 0.01, 'wood_l', fill='orange')
    if act:
        slot('sell', -0.2, d / 2 + 0.35, 0)
        for x in (-0.8, 0.0, 0.8):
            slot('shop', x, -d / 2 - 0.45, 180)


def keg_rack(n=3, act=False):
    """Wooden cradle with kegs lying on their sides (taps toward -Y)."""
    w = n * 0.62
    for sx in (-1, 1):
        bx((0.1, 0.6, 0.25), (sx * (w / 2), 0, 0), 'wood_d', bev=0.02)
    for sy in (-1, 1):
        bx((w + 0.1, 0.08, 0.12), (0, sy * 0.2, 0.15), 'wood_d', bev=0.015)
    for i in range(n):
        x = -w / 2 + 0.31 + i * 0.62
        with xf((x, 0.3, 0.55), 0):
            # keg lying along Y
            cy(0.27, 0.62, (0, 0, 0), 'wood_m', rot=(90, 0, 0), segs=14, origin='center', cap='wood_l', bev=0.03)
            for yy in (-0.2, 0.2):
                cy(0.285, 0.05, (0, yy, 0), 'iron', rot=(90, 0, 0), segs=14, origin='center', bev=0)
        seg((x, -0.02, 0.48), (x, -0.12, 0.48), 0.02, 'copper')
        seg((x, -0.12, 0.48), (x, -0.12, 0.42), 0.015, 'copper')


def counter_shelf(w=1.4, d=0.35, h=1.5, seed=0, goods='mixed', act='shop'):
    """Tall shop shelf with goods: jars, bolts of cloth, boxes, bottles."""
    for s in (-1, 1):
        bx((0.05, d, h), (s * (w / 2 - 0.025), 0, 0), 'wood_m', bev=0.01)
    bx((w, 0.03, h), (0, d / 2 - 0.015, 0), 'wood_d', bev=0)
    R = rnd(seed)
    zs = [0.05, 0.42, 0.79, 1.16]
    for k, z in enumerate(zs):
        bx((w, d, 0.04), (0, 0, z), 'wood_l', bev=0.01)
        x = -w / 2 + 0.12
        while x < w / 2 - 0.12:
            kind = R.randrange(5)
            if kind == 0:
                jar(x, 0, z + 0.04, R.choice(['cream', 'blue_l', 'terracotta', 'yellow']), seed=k, s=1.1)
                x += 0.15
            elif kind == 1:
                cy(0.07, 0.24, (x + 0.04, 0, z + 0.11), R.choice(['red', 'blue', 'green', 'purple', 'pink']),
                   rot=(90, 0, 0), segs=10, origin='center', bev=0.01)
                x += 0.17
            elif kind == 2:
                bx((0.16, 0.2, 0.12), (x + 0.04, 0, z + 0.04), R.choice(['wood_l', 'canvas', 'red_d']), bev=0.01)
                x += 0.2
            elif kind == 3:
                cy(0.035, 0.18, (x, 0, z + 0.04), R.choice(['green', 'leaf', 'blue_l']), segs=8, bev=0.008)
                x += 0.09
            else:
                sp(0.07, (x + 0.02, 0, z + 0.1), R.choice(['red', 'orange', 'yellow', 'leaf_l']), segs=8, rings=5)
                x += 0.15
    bx((w + 0.08, d + 0.04, 0.06), (0, 0, h), 'wood_m', bev=0.02)
    if act:
        slot(act, 0, -d / 2 - 0.4, 180)


def market_table(w=1.2, d=0.6, seed=0, act='shop'):
    """Low display table with produce baskets (shop floor)."""
    h = 0.45
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.06, 0.06, h - 0.05), (sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), 0), 'wood_d', bev=0.01)
    bx((w, d, 0.05), (0, 0, h - 0.05), 'wood_l', bev=0.02)
    bx((w + 0.02, 0.02, 0.18), (0, -d / 2 - 0.0, h - 0.2), 'red', bev=0)
    fills = ['orange', 'red', 'leaf_l', 'yellow', 'bread']
    for i in range(3):
        basket(-w / 2 + 0.22 + i * (w - 0.44) / 2, 0, h, fill=fills[(i + seed) % 5], seed=seed + i, r=0.14)
    if act:
        slot(act, 0, -d / 2 - 0.4, 180)


def well_roof():
    for s in (-1, 1):
        bx((1.7, 0.75, 0.07), (0, s * 0.33, 1.98), ('roof_r1', 'roof_r2')[s > 0], rot=(-s * 32, 0, 0), bev=0.02,
           origin='center')
        K.snow(1.6, 0.6, 0.08, (0, s * 0.31, 2.05), rot=(-s * 32, 0, 0), seed=s + 3)
    for s in (-1, 1):
        extr([(-0.62, 0), (0.62, 0), (0, 0.38)], 0.06, loc=(s * 0.68 - 0.03, 0, 1.8), rot=(90, 0, 90),
             c='wood_m')
    K.log_(0.06, 1.85, (0, 0, 2.2), (0, 90, 0), 'wood_dd')
    K.snow(1.75, 0.22, 0.07, (0, 0, 2.22), seed=9)


def well_model(roof=False):
    """Stone well with a roof, crank and bucket (exterior)."""
    R = rnd(4)
    n = 12
    for k in range(3):
        for i in range(n):
            a = math.tau * (i + 0.5 * (k % 2)) / n
            bx((0.36, 0.24, 0.22), (math.cos(a) * 0.62, math.sin(a) * 0.62, k * 0.21),
               R.choice(['stone', 'stone_d', 'stone_l', 'stone_w']), rot=(0, 0, math.degrees(a) + 90), bev=0.05)
    cy(0.55, 0.02, (0, 0, 0.45), 'water', segs=20, bev=0)
    cy(0.56, 0.4, (0, 0, 0.05), 'charcoal', segs=20, bev=0)
    for i in range(n):
        a = math.tau * (i + 0.25) / n
        snowcap(0.16, (math.cos(a) * 0.62, math.sin(a) * 0.62, 0.64), 0.05, seed=i)
    for s in (-1, 1):
        bx((0.12, 0.12, 1.55), (s * 0.68, 0, 0.3), 'wood_m', bev=0.02)
    seg((-0.75, 0, 1.4), (0.75, 0, 1.4), 0.05, 'wood_l')
    with xf((0.8, 0, 1.4)):
        bx((0.04, 0.04, 0.25), (0, 0, -0.25), 'iron', bev=0)
        seg((0, 0, -0.25), (0.15, 0, -0.25), 0.02, 'wood_d')
    cy(0.08, 0.3, (0, 0, 1.4), 'rope', rot=(0, 90, 0), segs=8, origin='center', bev=0)
    seg((0, 0, 1.36), (0, 0, 0.95), 0.012, 'rope')
    cy(0.13, 0.2, (0, 0, 0.75), 'wood_l', segs=12, r_top=0.15, bev=0.01)
    cy(0.155, 0.03, (0, 0, 0.82), 'iron', segs=12, bev=0)
    seg((-0.14, 0, 0.95), (0.14, 0, 0.95), 0.008, 'iron')
    if roof:
        well_roof()
    bx((0.5, 0.35, 0.05), (0.75, -0.6, 0.0), 'stone_d', bev=0.02)
    cy(0.13, 0.22, (0.75, -0.62, 0.05), 'wood_m', segs=12, r_top=0.15, bev=0.01)
    cy(0.12, 0.01, (0.75, -0.62, 0.26), 'water', segs=12, bev=0)


# =========================================================================== registry (standalone GLBs)
FURNITURE = {
    'chair': (chair, {}), 'stool': (stool, {}), 'bench_in': (bench_in, {}), 'table_round': (table_round, {}),
    'table_long': (table_long, {}), 'bed_single': (bed_single, {}), 'bed_double': (bed_double, {}),
    'crib': (crib, {}), 'stove': (stove, {}), 'hearth': (hearth, {}), 'kitchen_counter': (kitchen_counter, {}),
    'cupboard': (cupboard, {}), 'bookshelf': (bookshelf, {}), 'desk': (desk, {}), 'sofa': (sofa, {}),
    'rug_round': (rug_round, {}), 'rug_long': (rug_long, {}), 'lamp_floor': (lamp_floor, {}),
    'toilet': (toilet, {}), 'sink': (sink, {}), 'bathtub': (bathtub, {}), 'wardrobe': (wardrobe, {}),
    'plant_pot': (plant_pot, {}), 'tea_set': (tea_set, {}), 'bread_shelf': (bread_shelf, {}),
    'shop_counter': (shop_counter, {}), 'barrel_in': (barrel_in, {}), 'crate_in': (crate_in, {}),
    'meeting_table': (meeting_table, {}), 'notice_board_in': (notice_board_in, {}),
    # extras used inside the buildings
    'armchair': (armchair, {}), 'workbench': (workbench, {}), 'bread_oven': (bread_oven, {}),
    'dough_table': (dough_table, {}), 'cot': (cot, {}), 'millstone': (millstone, {}), 'saw_bench': (saw_bench, {}),
    'bar_counter': (bar_counter, {}), 'keg_rack': (keg_rack, {}), 'counter_shelf': (counter_shelf, {}),
    'cooking_range': (cooking_range, {}), 'hay_bale': (hay_bale, {}), 'chop_stump': (chop_stump, {}),
}
