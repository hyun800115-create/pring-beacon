"""
b3d_animals.py - 봄날의 행진 farm animals (CONTRACT3D 6.1): rigged joint-hierarchy toy animals + clips.

    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_animals.py -- [keys...]
    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_animals.py -- --preview [--samples 16]

Keys: animal_chicken, animal_cow, animal_cattle, animal_sheep, animal_pig, animal_goat.
Rig (quadrupeds): root > body > neck > head > ear_R/L,  body > tail,  body > leg_FR/FL/BR/BL > knee_*.
Rig (chicken):    root > body > neck > head,  body > wing_R/L, body > tail, body > leg_R/L > knee_R/L.
Front = Blender -Y, origin = ground between the feet.  Clips: idle(4) walk(8) eat(6) sit(4) happy(6),
baked on one timeline with export_glb.join_parts / bake -> assets3d/chars/<key>.glb + <key>.json.
Flat Principled colours only.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector, Quaternion  # noqa: E402
import bl_common as bc  # noqa: E402
import char_geo as g  # noqa: E402
from char_animals import M, on_sph, sph_point  # noqa: E402,F401

TAU = math.tau
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(GAME, 'assets3d', 'chars')
SHOTS = os.path.normpath(os.path.join(GAME, '..', '.cache', 'shots', 'b3d2'))

KEYS = ['animal_chicken', 'animal_cow', 'animal_cattle', 'animal_sheep', 'animal_pig', 'animal_goat']
ANIMS = {
    'idle':  {'frames': 4, 'fps': 4, 'repeat': -1},
    'walk':  {'frames': 8, 'fps': 10, 'repeat': -1},
    'eat':   {'frames': 6, 'fps': 6, 'repeat': -1},
    'sit':   {'frames': 4, 'fps': 3, 'repeat': -1},
    'happy': {'frames': 6, 'fps': 9, 'repeat': -1},
}


# --------------------------------------------------------------------------- shared parts
def eyes(head, center, radii, az=0.62, el=0.14, s=1.0, blush=True, white=False):
    """Cute glossy eyes (+ optional blush) on an ellipsoid head; s scales everything."""
    eye = M('eye', '#2A2026', rough=0.25)
    hi = M('eye_hi', '#FFFFFF', rough=0.3, emission='#FFFFFF', emission_strength=1.2)
    for sd in (-1, 1):
        if white:
            on_sph('eye_w', g.bm_ellipsoid(0.040 * s, 0.012 * s, 0.046 * s, 12, 8), M('eye_white', '#FFFFFF', 0.4),
                   head, center, radii, sd * az, el, out=-0.004 * s)
        on_sph('eye', g.bm_ellipsoid(0.030 * s, 0.016 * s, 0.036 * s, 12, 8), eye, head, center, radii,
               sd * az, el, out=-0.004 * s)
        on_sph('eye_hi', g.bm_ellipsoid(0.010 * s, 0.006 * s, 0.011 * s, 6, 4), hi, head, center, radii,
               sd * az - 0.07, el + 0.08, out=0.004 * s)
        if blush:
            on_sph('blush', g.bm_ellipsoid(0.034 * s, 0.008 * s, 0.020 * s, 10, 6), M('blush', '#F49A9A', 0.9),
                   head, center, radii, sd * (az + 0.32), el - 0.30, out=-0.002 * s)


def quad_legs(rig, body_z, L, xs, ys, upper, r_up, r_low, fur, hoof, hoof_h=None, hoof_r=None, fur_low=None):
    """Four chunky legs.  Leg joints at body-local (x, y, L-body_z) so the hoof bottom touches z=0."""
    lower = L - upper
    hoof_h = hoof_h or r_low * 0.9
    hoof_r = hoof_r or r_low * 1.12
    for nm, x, y in (('FR', -xs, -ys[0]), ('FL', xs, -ys[0]), ('BR', -xs, ys[1]), ('BL', xs, ys[1])):
        rig.add('leg_' + nm, 'body', (x, y, L - body_z))
        rig.add('knee_' + nm, 'leg_' + nm, (0, 0, -upper))
        g.mesh_obj('thigh', g.bm_capsule(r_up, upper, r_end=r_low * 1.05, seg=14, rings=6), fur,
                   rig.j['leg_' + nm])
        g.mesh_obj('shin', g.bm_capsule(r_low, max(0.01, lower - hoof_h - r_low * 0.4), seg=12, rings=5),
                   fur_low or fur, rig.j['knee_' + nm])
        g.mesh_obj('hoof', g.bm_lathe([(0.0, 0.0), (hoof_r, 0.0), (hoof_r * 1.0, hoof_h * 0.6),
                                       (hoof_r * 0.85, hoof_h), (0.0, hoof_h)], seg=14),
                   hoof, rig.j['knee_' + nm], loc=(0, -0.004, -lower))
    rig.meta['L'] = L


def tail_tube(rig, pos, pts, r0, r1, mat, tuft=None, tuft_r=0.05):
    rig.add('tail', 'body', pos)
    g.mesh_obj('tail', g.bm_tube_path(pts, lambda t: r0 + (r1 - r0) * t, segr=8), mat, rig.j['tail'])
    if tuft is not None:
        g.mesh_obj('tuft', g.bm_ellipsoid(tuft_r, tuft_r, tuft_r * 1.4, 10, 6), tuft, rig.j['tail'],
                   loc=pts[-1])


def ears(rig, head, x, y, z, bm_fn, mat, inner=None, rot=(0, 0, 0), inner_fn=None, inner_loc=(0, -0.01, 0)):
    for nm, s in (('R', 1), ('L', -1)):
        xx = -x if nm == 'R' else x
        rig.add('ear_' + nm, 'head', (xx, y, z), side=s)
        rr = (rot[0], rot[1] * (1 if nm == 'R' else -1), rot[2] * (1 if nm == 'R' else -1))
        g.mesh_obj('ear', bm_fn(), mat, rig.j['ear_' + nm], rot=rr)
        if inner is not None:
            g.mesh_obj('ear_in', inner_fn(), inner, rig.j['ear_' + nm], loc=inner_loc, rot=rr)


def horn(head, base, sx, mat, h=0.08, r=0.03, curl=(0.0, 0.25), up=1.0):
    """Little curved cone horn starting at head-local `base`, sx = side sign (+1 left/-1 right)."""
    pts = []
    for k in range(6):
        t = k / 5
        pts.append((base[0] + sx * h * 0.45 * t, base[1] + curl[1] * h * t * t, base[2] + up * h * t))
    g.mesh_obj('horn', g.bm_tube_path(pts, lambda t: r * (1 - 0.85 * t) + 0.003, segr=8), mat, head)


def finish_rig(rig, head_parts_z=None):
    rig.meta['height'] = None
    return rig


# --------------------------------------------------------------------------- animals
def build_cow(beef=False):
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    BZ, L = 0.66, 0.36
    rig.add('body', 'root', (0, 0, BZ))
    if beef:
        fur, fur2, muzzle = M('cattle_fur', '#A2603A', 0.85), M('cattle_dark', '#6B3D24', 0.9), M('cattle_muzzle', '#F0D6B4', 0.7)
    else:
        fur, fur2, muzzle = M('cow_white', '#F7F3EC', 0.8), M('cow_black', '#2F2B2E', 0.8), M('cow_pink', '#F5B3B4', 0.6)
    hoof = M('hoof', '#4A3A34', 0.5)
    hornm = M('horn', '#F1E3C2', 0.5)
    body = rig.j['body']
    br = (0.34, 0.50, 0.31)
    g.mesh_obj('body', g.bm_ellipsoid(*br, 28, 14), fur, body)
    g.mesh_obj('chest', g.bm_ellipsoid(0.31, 0.22, 0.30, 20, 10), fur, body, loc=(0, -0.30, 0.04))
    if beef:
        g.mesh_obj('belly', g.bm_ellipsoid(0.27, 0.36, 0.17, 20, 10), M('cattle_belly', '#C98A5E', 0.9), body,
                   loc=(0, 0.02, -0.15))
    else:
        for (az, el, sx, sz) in ((1.2, 0.35, 0.15, 0.12), (-1.5, 0.1, 0.17, 0.13), (2.4, 0.5, 0.13, 0.11),
                                 (-2.5, 0.2, 0.12, 0.10), (0.6, -0.15, 0.10, 0.09), (-0.9, 0.75, 0.12, 0.10),
                                 (3.05, 0.2, 0.10, 0.10)):
            on_sph('spot', g.bm_ellipsoid(sx, 0.03, sz, 14, 8), fur2, body, (0, 0, 0), br, az, el, out=-0.014)
        g.mesh_obj('udder', g.bm_ellipsoid(0.12, 0.11, 0.08, 14, 8), muzzle, body, loc=(0, 0.24, -0.27))
        for tx in (-0.04, 0.04):
            for ty in (-0.035, 0.035):
                g.mesh_obj('teat', g.bm_capsule(0.016, 0.03, seg=8, rings=3), muzzle, body,
                           loc=(tx, 0.24 + ty, -0.31))
    # neck + head (big chibi head)
    rig.add('neck', 'body', (0, -0.40, 0.10))
    g.mesh_obj('neck', g.bm_ellipsoid(0.17, 0.15, 0.18, 16, 8), fur, rig.j['neck'], loc=(0, -0.04, 0.06))
    rig.add('head', 'neck', (0, -0.14, 0.14))
    head = rig.j['head']
    hc, hr = (0, -0.06, 0.06), (0.25, 0.23, 0.23)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 26, 13), fur, head, loc=hc)
    g.mesh_obj('muzzle', g.bm_ellipsoid(0.20, 0.13, 0.135, 20, 10), muzzle, head, loc=(0, -0.25, -0.05))
    nost = M('nostril', '#7A4B4E' if not beef else '#5A3A2A', 0.5)
    for s in (-1, 1):
        g.mesh_obj('nostril', g.bm_ellipsoid(0.022, 0.012, 0.030, 8, 6), nost, head, loc=(s * 0.07, -0.375, -0.03))
    if beef:
        # white blaze + fluffy forelock
        on_sph('blaze', g.bm_ellipsoid(0.07, 0.02, 0.10, 12, 8), M('blaze', '#F7F0E4', 0.8), head, hc, hr,
               0.0, 0.25, out=-0.008)
        for k, (x, z) in enumerate(((-0.06, 0.24), (0.0, 0.27), (0.06, 0.24), (-0.03, 0.21), (0.03, 0.21))):
            g.mesh_obj('lock', g.bm_ellipsoid(0.055, 0.05, 0.05, 10, 6), fur2, head, loc=(x, -0.13, z + 0.01))
    else:
        on_sph('eyepatch', g.bm_ellipsoid(0.09, 0.02, 0.085, 12, 8), fur2, head, hc, hr, 0.55, 0.20, out=-0.012)
        # little bell on a red collar
        g.mesh_obj('collar', g.bm_ring(0.16, 0.022, seg=24, segr=6, sy=0.9), M('collar', '#D9483B', 0.6),
                   rig.j['neck'], loc=(0, -0.04, 0.0), rot=(-25, 0, 0))
        g.mesh_obj('bell', g.bm_lathe([(0.0, -0.06), (0.05, -0.055), (0.042, -0.02), (0.025, 0.0), (0.0, 0.005)],
                                      seg=12), M('bell', '#F2C14E', 0.35, metal=0.4), rig.j['neck'],
                   loc=(0, -0.20, -0.08))
    eyes(head, hc, hr, az=0.58, el=0.16, s=1.45)
    ears(rig, head, 0.22, 0.0, 0.10,
         lambda: g.bm_ellipsoid(0.10, 0.035, 0.05, 12, 6), fur2 if not beef else fur,
         inner=muzzle, inner_fn=lambda: g.bm_ellipsoid(0.07, 0.02, 0.032, 10, 6), rot=(0, 25, 0),
         inner_loc=(0, -0.018, 0))
    # move the ear meshes outward from the joint
    for nm in ('R', 'L'):
        for ch in rig.j['ear_' + nm].children:
            ch.location.x += 0.07 * (-1 if nm == 'R' else 1)
    for sx in (-1, 1):
        horn(head, (sx * 0.12, -0.02, 0.22), sx, hornm, h=0.10 if beef else 0.08, r=0.035, curl=(0, 0.1))
    tail_tube(rig, (0, 0.48, 0.14), [(0, 0, 0), (0, 0.06, -0.04), (0, 0.09, -0.16), (0, 0.10, -0.30)],
              0.022, 0.016, fur, tuft=fur2, tuft_r=0.045)
    quad_legs(rig, BZ, L, 0.19, (0.30, 0.30), upper=0.17, r_up=0.10, r_low=0.085,
              fur=fur, hoof=hoof, fur_low=fur)
    rig.meta['dims'] = 1.3
    return rig


def build_sheep():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    BZ, L = 0.44, 0.22
    rig.add('body', 'root', (0, 0, BZ))
    wool = M('wool', '#FAF6EE', 0.95)
    wool2 = M('wool_shade', '#EFE8DA', 0.95)
    face = M('sheep_face', '#4A3F3E', 0.8)
    legm = M('sheep_leg', '#3E3536', 0.8)
    body = rig.j['body']
    br = (0.29, 0.34, 0.25)
    g.mesh_obj('body', g.bm_ellipsoid(*br, 24, 12), wool, body)
    k = 0
    for el in (-0.35, 0.1, 0.55, 1.0):
        n = {-0.35: 9, 0.1: 10, 0.55: 8, 1.0: 4}[el]
        for i in range(n):
            az = TAU * (i + 0.5 * (k % 2)) / n
            k += 1
            r = 0.105 if el < 0.9 else 0.11
            on_sph('tuft', g.bm_ellipsoid(r, r, r * 0.9, 10, 6), wool if (i + k) % 3 else wool2, body,
                   (0, 0, 0), br, az, el, out=-0.05)
    rig.add('neck', 'body', (0, -0.30, 0.06))
    rig.add('head', 'neck', (0, -0.06, 0.08))
    head = rig.j['head']
    hc, hr = (0, -0.05, 0.02), (0.15, 0.15, 0.155)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 22, 11), face, head, loc=hc)
    g.mesh_obj('muzzle', g.bm_ellipsoid(0.10, 0.08, 0.075, 14, 8), M('sheep_muzzle', '#5C504E', 0.8), head,
               loc=(0, -0.15, -0.04))
    for s in (-1, 1):
        g.mesh_obj('nostril', g.bm_ellipsoid(0.012, 0.008, 0.014, 6, 4), M('nostril_d', '#2A2224', 0.5), head,
                   loc=(s * 0.03, -0.225, -0.02))
    eyes(head, hc, hr, az=0.55, el=0.12, s=1.0, white=True, blush=False)
    for s in (-1, 1):
        on_sph('blush', g.bm_ellipsoid(0.028, 0.008, 0.016, 10, 6), M('blush', '#F49A9A', 0.9), head, hc, hr,
               s * 0.95, -0.15, out=-0.002)
    # wool cap
    for (x, y, z, r) in ((0, -0.02, 0.15, 0.085), (-0.07, 0.0, 0.13, 0.07), (0.07, 0.0, 0.13, 0.07),
                         (0, 0.05, 0.12, 0.08), (0, -0.09, 0.12, 0.06)):
        g.mesh_obj('cap', g.bm_ellipsoid(r, r, r * 0.85, 10, 6), wool, head, loc=(x, y, z))
    ears(rig, head, 0.13, 0.0, 0.05, lambda: g.bm_ellipsoid(0.075, 0.028, 0.035, 10, 6), face,
         inner=M('ear_in', '#E8A7A0', 0.9), inner_fn=lambda: g.bm_ellipsoid(0.05, 0.015, 0.022, 8, 4),
         rot=(0, -20, 0), inner_loc=(0, -0.015, 0))
    for nm in ('R', 'L'):
        for ch in rig.j['ear_' + nm].children:
            ch.location.x += 0.05 * (-1 if nm == 'R' else 1)
    rig.add('tail', 'body', (0, 0.34, 0.06))
    g.mesh_obj('tail', g.bm_ellipsoid(0.07, 0.06, 0.08, 10, 6), wool, rig.j['tail'], loc=(0, 0.02, -0.02))
    quad_legs(rig, BZ, L, 0.15, (0.20, 0.20), upper=0.10, r_up=0.055, r_low=0.045, fur=legm,
              hoof=M('hoof_d', '#2A2224', 0.5))
    return rig


def build_pig():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    BZ, L = 0.34, 0.16
    rig.add('body', 'root', (0, 0, BZ))
    pink = M('pig_pink', '#F6AFB4', 0.6)
    pink2 = M('pig_dark', '#E88E99', 0.6)
    body = rig.j['body']
    br = (0.30, 0.40, 0.27)
    g.mesh_obj('body', g.bm_ellipsoid(*br, 26, 13), pink, body)
    on_sph('spot', g.bm_ellipsoid(0.11, 0.03, 0.09, 12, 8), pink2, body, (0, 0, 0), br, 2.3, 0.55, out=-0.014)
    rig.add('neck', 'body', (0, -0.32, 0.05))
    rig.add('head', 'neck', (0, -0.06, 0.06))
    head = rig.j['head']
    hc, hr = (0, -0.06, 0.04), (0.22, 0.20, 0.20)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 24, 12), pink, head, loc=hc)
    g.mesh_obj('snout', g.bm_lathe([(0.0, 0.0), (0.085, 0.0), (0.09, 0.05), (0.085, 0.085), (0.0, 0.09)], seg=18),
               pink2, head, loc=(0, -0.20, -0.02), rot=(90, 0, 0), scale=(1.0, 0.8, 1.0))
    for s in (-1, 1):
        g.mesh_obj('nostril', g.bm_ellipsoid(0.017, 0.01, 0.026, 8, 6), M('pig_nostril', '#9C4E5A', 0.5), head,
                   loc=(s * 0.035, -0.29, -0.02))
    eyes(head, hc, hr, az=0.62, el=0.20, s=1.25)
    ear = lambda: g.bm_lathe([(0.0, 0.0), (0.07, 0.01), (0.045, 0.07), (0.0, 0.12)], seg=10, sy=0.35)  # noqa: E731
    for nm, s in (('R', 1), ('L', -1)):
        x = -0.13 if nm == 'R' else 0.13
        rig.add('ear_' + nm, 'head', (x, -0.02, 0.17), side=s)
        g.mesh_obj('ear', ear(), pink2, rig.j['ear_' + nm], rot=(-55, 20 * (1 if nm == 'L' else -1), 0))
    rig.add('tail', 'body', (0, 0.39, 0.06))
    curl = [(0.0, 0.0, 0.0)]
    for k in range(1, 14):
        a = k / 13 * 1.8 * math.pi
        curl.append((0.035 * math.sin(a), 0.03 + 0.02 * k / 13 + 0.02 * (1 - math.cos(a)) * 0.6,
                     0.035 * (1 - math.cos(a)) * 0.9))
    g.mesh_obj('tail', g.bm_tube_path(curl, lambda t: 0.016 - 0.006 * t, segr=8), pink2, rig.j['tail'])
    quad_legs(rig, BZ, L, 0.17, (0.22, 0.24), upper=0.07, r_up=0.075, r_low=0.062, fur=pink,
              hoof=M('pig_hoof', '#B86A74', 0.5))
    return rig


def build_goat():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    BZ, L = 0.47, 0.30
    rig.add('body', 'root', (0, 0, BZ))
    fur = M('goat_fur', '#F4EFE6', 0.85)
    tan = M('goat_tan', '#C99A6A', 0.85)
    hornm = M('goat_horn', '#8E7B6A', 0.5)
    pinky = M('goat_nose', '#E9B5AE', 0.6)
    body = rig.j['body']
    br = (0.21, 0.32, 0.20)
    g.mesh_obj('body', g.bm_ellipsoid(*br, 24, 12), fur, body)
    g.mesh_obj('chest', g.bm_ellipsoid(0.19, 0.15, 0.19, 18, 9), fur, body, loc=(0, -0.20, 0.03))
    rig.add('neck', 'body', (0, -0.26, 0.10))
    g.mesh_obj('neck', g.bm_ellipsoid(0.10, 0.09, 0.13, 12, 6), fur, rig.j['neck'], loc=(0, -0.03, 0.05))
    rig.add('head', 'neck', (0, -0.07, 0.12))
    head = rig.j['head']
    hc, hr = (0, -0.05, 0.03), (0.155, 0.15, 0.15)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 22, 11), fur, head, loc=hc)
    g.mesh_obj('muzzle', g.bm_ellipsoid(0.085, 0.09, 0.075, 14, 8), fur, head, loc=(0, -0.16, -0.03))
    g.mesh_obj('nose', g.bm_ellipsoid(0.035, 0.015, 0.022, 8, 6), pinky, head, loc=(0, -0.245, -0.01))
    g.mesh_obj('beard', g.bm_lathe([(0.0, 0.0), (0.03, 0.01), (0.025, 0.06), (0.0, 0.09)], seg=10, sy=0.7),
               fur, head, loc=(0, -0.15, -0.08), rot=(180, 0, 0))
    eyes(head, hc, hr, az=0.60, el=0.15, s=1.0)
    ears(rig, head, 0.13, 0.0, 0.06, lambda: g.bm_ellipsoid(0.075, 0.03, 0.035, 10, 6), fur,
         inner=pinky, inner_fn=lambda: g.bm_ellipsoid(0.05, 0.015, 0.02, 8, 4), rot=(0, 30, 0),
         inner_loc=(0, -0.016, 0))
    for nm in ('R', 'L'):
        for ch in rig.j['ear_' + nm].children:
            ch.location.x += 0.055 * (-1 if nm == 'R' else 1)
            ch.location.z -= 0.02
    for sx in (-1, 1):
        pts = []
        for k in range(7):
            t = k / 6
            pts.append((sx * (0.06 + 0.03 * t), 0.0 + 0.10 * t, 0.15 + 0.10 * math.sin(t * 1.6)))
        g.mesh_obj('horn', g.bm_tube_path(pts, lambda t: 0.028 * (1 - 0.8 * t) + 0.004, segr=8), hornm, head)
    tail_tube(rig, (0, 0.31, 0.10), [(0, 0, 0), (0, 0.04, 0.05), (0, 0.05, 0.10)], 0.03, 0.02, fur)
    quad_legs(rig, BZ, L, 0.12, (0.20, 0.21), upper=0.14, r_up=0.05, r_low=0.04, fur=fur,
              hoof=M('hoof_g', '#5A4A40', 0.5))
    return rig


def build_chicken():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    BZ = 0.17
    rig.add('body', 'root', (0, 0, BZ))
    white = M('hen_white', '#FFFDF7', 0.8)
    cream = M('hen_cream', '#F1E6D2', 0.8)
    red = M('comb', '#E0453A', 0.55)
    beak = M('beak', '#F2B23A', 0.45)
    legm = M('hen_leg', '#F09A3A', 0.5)
    body = rig.j['body']
    g.mesh_obj('body', g.bm_ellipsoid(0.125, 0.14, 0.12, 22, 11), white, body)
    g.mesh_obj('breast', g.bm_ellipsoid(0.10, 0.08, 0.10, 14, 8), white, body, loc=(0, -0.07, 0.01))
    rig.add('neck', 'body', (0, -0.06, 0.07))
    rig.add('head', 'neck', (0, -0.02, 0.07))
    head = rig.j['head']
    hc, hr = (0, -0.01, 0.03), (0.085, 0.08, 0.085)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 18, 9), white, head, loc=hc)
    g.mesh_obj('neckfill', g.bm_ellipsoid(0.07, 0.07, 0.07, 12, 6), white, rig.j['neck'], loc=(0, -0.01, 0.02))
    g.mesh_obj('beak', g.bm_lathe([(0.0, 0.0), (0.026, 0.0), (0.0, 0.045)], seg=10, sy=0.8), beak, head,
               loc=(0, -0.085, 0.02), rot=(90, 0, 0))
    g.mesh_obj('wattle', g.bm_ellipsoid(0.016, 0.014, 0.026, 8, 6), red, head, loc=(0, -0.08, -0.02))
    for k, (y, z, r) in enumerate(((-0.04, 0.105, 0.022), (-0.01, 0.12, 0.026), (0.025, 0.11, 0.022))):
        g.mesh_obj('comb', g.bm_ellipsoid(r * 0.6, r, r * 1.1, 8, 6), red, head, loc=(0, y, z))
    eyes(head, hc, hr, az=0.75, el=0.12, s=0.55, blush=False)
    for s in (-1, 1):
        on_sph('blush', g.bm_ellipsoid(0.018, 0.005, 0.011, 8, 4), M('blush', '#F49A9A', 0.9), head, hc, hr,
               s * 1.15, -0.15, out=-0.001)
    for nm, s in (('R', 1), ('L', -1)):
        x = -0.11 if nm == 'R' else 0.11
        rig.add('wing_' + nm, 'body', (x, -0.01, 0.04), side=s)
        g.mesh_obj('wing', g.bm_ellipsoid(0.03, 0.10, 0.07, 12, 6), cream, rig.j['wing_' + nm],
                   loc=(0, 0.03, -0.03), rot=(-15, 0, 0))
    rig.add('tail', 'body', (0, 0.12, 0.05))
    for k, (x, ry) in enumerate(((-0.03, -15), (0.0, 0), (0.03, 15))):
        g.mesh_obj('feather', g.bm_ellipsoid(0.025, 0.05, 0.075, 10, 6), white if k != 1 else cream,
                   rig.j['tail'], loc=(x, 0.02, 0.05), rot=(-35, ry, 0))
    L = 0.07
    for nm, s in (('R', 1), ('L', -1)):
        x = -0.05 if nm == 'R' else 0.05
        rig.add('leg_' + nm, 'body', (x, 0.0, L + 0.035 - BZ), side=s)
        rig.add('knee_' + nm, 'leg_' + nm, (0, 0, -0.04))
        g.mesh_obj('thigh', g.bm_capsule(0.032, 0.03, r_end=0.02, seg=10, rings=4), white, rig.j['leg_' + nm])
        g.mesh_obj('shin', g.bm_cyl(0.011, 0.011, 0.06, seg=6), legm, rig.j['knee_' + nm], loc=(0, 0, -0.065))
        for a in (-35, 0, 35):
            ra = math.radians(a)
            p1 = (0.04 * math.sin(ra), -0.04 * math.cos(ra), -0.06)
            g.mesh_obj('toe', g.bm_tube_path([(0, 0, -0.062), p1], 0.008, segr=5), legm, rig.j['knee_' + nm])
        g.mesh_obj('toe', g.bm_tube_path([(0, 0, -0.062), (0, 0.025, -0.06)], 0.007, segr=5), legm,
                   rig.j['knee_' + nm])
    rig.meta['L'] = L
    rig.meta['biped'] = True
    return rig


BUILD = {
    'animal_chicken': build_chicken,
    'animal_cow': lambda: build_cow(False),
    'animal_cattle': lambda: build_cow(True),
    'animal_sheep': build_sheep,
    'animal_pig': build_pig,
    'animal_goat': build_goat,
}

# per-animal motion tuning
TUNE = {
    'animal_cow':    dict(amp=24, kb=40, bob=0.022, hop=0.10, eat=(-8, -62, 8, -0.06)),
    'animal_cattle': dict(amp=24, kb=40, bob=0.022, hop=0.09, eat=(-8, -62, 8, -0.06)),
    'animal_sheep':  dict(amp=28, kb=40, bob=0.022, hop=0.12, eat=(-8, -62, 8, -0.05)),
    'animal_pig':    dict(amp=32, kb=36, bob=0.02, hop=0.10, eat=(-6, -45, 0, -0.03)),
    'animal_goat':   dict(amp=28, kb=46, bob=0.022, hop=0.16, eat=(-8, -65, 10, -0.05)),
    'animal_chicken': dict(amp=34, kb=50, bob=0.015, hop=0.08, eat=(-45, -45, 5, -0.01)),
}


# --------------------------------------------------------------------------- calibration
def _min_z(objs):
    bpy.context.view_layer.update()
    z = 9.0
    for o in objs:
        mw = o.matrix_world
        for v in o.data.vertices:
            z = min(z, (mw @ v.co).z)
    return z


def _desc_meshes(joint):
    out = []
    for c in joint.children_recursive:
        if c.type == 'MESH':
            out.append(c)
    return out


def calibrate(rig, key):
    """Find neck/head dip so the mouth reaches the grass, and the body drop for lying down."""
    rig.reset()
    head_meshes = [c for c in rig.j['head'].children if c.type == 'MESH']
    biped = rig.meta.get('biped')
    B, N1, N2, fy = TUNE[key]['eat']
    best = 0.45
    for k in range(0, 46):
        fz = k * 0.01
        rig.apply({'body': (B, 0, 0), 'neck': (N1, 0, 0), 'head': (N2, 0, 0), 'neck@': (0, fy, -fz)})
        if _min_z(head_meshes) <= 0.02:
            best = fz
            break
    rig.meta['eat'] = (B, N1, N2, fy, best)
    rig.meta['dip'] = best
    rig.reset()
    body_meshes = [c for c in rig.j['body'].children if c.type == 'MESH']
    rig.meta['drop'] = max(0.0, _min_z(body_meshes) - (0.015 if not biped else 0.03))
    rig.reset()
    print('  [%s] eat drop %.2f, lie drop %.3f m' % (key, best, rig.meta['drop']), flush=True)


# --------------------------------------------------------------------------- poses
def quad_pose(rig, key, an, i, n):
    T = TUNE[key]
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    p = {}
    legs = ('FL', 'FR', 'BL', 'BR')
    if an == 'idle':
        p = {'body@': (0, 0, 0.006 * s), 'body': (0.8 * s, 0, 0), 'neck': (2 * s, 0, 0),
             'head': (2 * c, 0, 8 * s), 'tail': (0, 0, 22 * s)}
        if i == 2:
            p['ear_R'] = (-20, 0, 0)
        for lg in legs:
            p['knee_' + lg] = (2 + 2 * s if lg[0] == 'F' else -2 - 2 * s, 0, 0)
    elif an == 'walk':
        for lg, sgn in (('FL', 1), ('BR', 1), ('FR', -1), ('BL', -1)):
            p['leg_' + lg] = (T['amp'] * sgn * s, 0, 0)
            fwd = sgn * c
            bend = T['kb'] * max(0.0, fwd) ** 1.3 + 4
            p['knee_' + lg] = (bend if lg[0] == 'F' else -bend * 0.8, 0, 0)
        p['body@'] = (0, 0, T['bob'] * (0.5 + 0.5 * math.cos(2 * a)) - 0.01)
        p['body'] = (1.5 * math.sin(2 * a), 2.0 * c, 0)
        p['neck'] = (-3 * math.cos(2 * a), 0, 0)
        p['head'] = (4 * math.cos(2 * a), 0, 4 * s)
        p['tail'] = (6 * math.cos(2 * a), 0, 18 * s)
        p['ear_R'] = (8 * math.cos(2 * a), 0, 0)
        p['ear_L'] = (8 * math.cos(2 * a + 0.8), 0, 0)
    elif an == 'eat':
        B, N1, N2, fy, fz = rig.meta['eat']
        chew = [0.0, 1.0, 0.3, 1.0, 0.0, 0.6][i % 6]
        p['neck'] = (N1, 0, 3 * s)
        p['head'] = (N2 + 7 * chew, 0, 4 * s)
        p['neck@'] = (0, fy, -fz)
        p['body'] = (B, 0, 0)
        p['leg_FL'] = (-6, 0, 0)
        p['leg_FR'] = (-6, 0, 0)
        p['tail'] = (0, 0, 25 * s)
        p['ear_R'] = (-10 * chew, 0, 0)
        p['ear_L'] = (-10 * chew, 0, 0)
    elif an == 'sit':
        dr = rig.meta['drop']
        p['body@'] = (0, 0, -dr + 0.004 * s)
        for lg in legs:
            if lg[0] == 'F':
                p['leg_' + lg] = (80, 0, 0)
                p['knee_' + lg] = (-10, 0, 0)
            else:
                p['leg_' + lg] = (78, -10, 0)
                p['knee_' + lg] = (150, 0, 0)
        p['neck'] = (6 + 2 * s, 0, 0)
        p['head'] = (-6, 0, 10 * math.sin(a))
        p['tail'] = (0, 0, 12 * s)
        if i == 2:
            p['ear_L'] = (-20, 0, 0)
    elif an == 'happy':
        up = math.sin(math.pi * i / n)
        p['root@'] = (0, 0, T['hop'] * up)
        for lg in legs:
            tuck = 30 * up
            p['leg_' + lg] = ((tuck if lg[0] == 'F' else -tuck * 0.6), 0, 0)
            p['knee_' + lg] = ((40 * up if lg[0] == 'F' else -40 * up), 0, 0)
        p['body'] = (6 * up - 3, 0, 0)
        p['neck'] = (10 * up, 0, 0)
        p['head'] = (8 * up, 0, 12 * math.sin(2 * a))
        p['tail'] = (20, 0, 40 * math.sin(2 * a))
        p['ear_R'] = (-25 * up, 0, 0)
        p['ear_L'] = (-25 * up, 0, 0)
    return p


def hen_pose(rig, key, an, i, n):
    T = TUNE[key]
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    p = {}
    if an == 'idle':
        p = {'body@': (0, 0, 0.003 * s), 'head': (4 * c, 0, 25 * s if i in (1, 2) else -10),
             'tail': (4 * s, 0, 0), 'wing_R': (0, 3 * s, 0), 'wing_L': (0, 3 * s, 0)}
        if i == 3:
            p['head'] = (8, 12, -15)
    elif an == 'walk':
        for lg, sgn in (('R', 1), ('L', -1)):
            p['leg_' + lg] = (T['amp'] * sgn * s, 0, 0)
            fwd = sgn * c
            p['knee_' + lg] = (T['kb'] * max(0.0, fwd) ** 1.3, 0, 0)
        p['body@'] = (0, 0, T['bob'] * (0.5 + 0.5 * math.cos(2 * a)) - 0.004)
        p['body'] = (-4, 0, 0)
        p['body'] = (-4 + 2 * math.cos(2 * a), 6 * s, 0)
        p['neck@'] = (0, -0.02 * math.cos(2 * a), 0)
        p['head'] = (3, 0, 0)
        p['tail'] = (5 * math.cos(2 * a), 0, 6 * s)
    elif an == 'eat':
        k = [0.0, 0.5, 1.0, 0.2, 1.0, 0.4][i % 6]
        B, N1, N2, fy, fz = rig.meta['eat']
        p['body'] = (B * k - 4 * (1 - k), 0, 0)
        p['neck'] = (N1 * k, 0, 0)
        p['head'] = (N2 * k, 0, 0)
        p['neck@'] = (0, fy * k, -fz * k)
        for lg in ('R', 'L'):
            p['leg_' + lg] = (-B * k, 0, 0)
        p['body@'] = (0, 0, -0.02 * k)
        p['tail'] = (18 * k, 0, 0)
        p['wing_R'] = (0, 4 * k, 0)
        p['wing_L'] = (0, 4 * k, 0)
    elif an == 'sit':
        p['body@'] = (0, 0, -rig.meta['drop'] + 0.003 * s)
        for lg in ('R', 'L'):
            p['leg_' + lg + '%'] = (0.7, 0.7, 0.12)
        p['head'] = (-6 + 2 * s, 0, 10 if i in (2, 3) else 0)
        p['tail'] = (-6, 0, 0)
        p['wing_R'] = (0, -4, 0)
        p['wing_L'] = (0, -4, 0)
    elif an == 'happy':
        up = math.sin(math.pi * i / n)
        p['root@'] = (0, 0, T['hop'] * up)
        flap = 70 * abs(math.sin(2 * a))
        p['wing_R'] = (0, flap, 0)
        p['wing_L'] = (0, flap, 0)
        for lg in ('R', 'L'):
            p['leg_' + lg] = (20 * up, 0, 0)
            p['knee_' + lg] = (40 * up, 0, 0)
        p['head'] = (15 * up, 0, 0)
        p['tail'] = (20 * up, 0, 0)
    return p


def make(key):
    bc.reset_scene()
    rig = BUILD[key]()
    bpy.context.view_layer.update()
    calibrate(rig, key)
    fn = hen_pose if rig.meta.get('biped') else quad_pose
    pose = lambda an, i, n: fn(rig, key, an, i, n)  # noqa: E731
    return rig, pose


def tri_total():
    n = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles()
            n += len(o.data.loop_triangles)
    return n


def export(key):
    import export_glb as EG
    t0 = time.time()
    rig, pose = make(key)
    rig.reset()
    bpy.context.view_layer.update()
    hmax = max((o.matrix_world @ v.co).z for o in bpy.data.objects if o.type == 'MESH' for v in o.data.vertices)
    n0, n1 = EG.join_parts(rig)
    tris = tri_total()
    clips = EG.bake(rig, ANIMS, pose)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, key + '.glb')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', use_selection=False,
        export_animations=True, export_animation_mode='SCENE', export_force_sampling=False,
        export_frame_range=False, export_apply=False, export_yup=True, export_cameras=False, export_lights=False,
    )
    meta = {'key': key, 'clips': clips, 'joints': sorted(rig.j.keys()), 'height': round(hmax, 3),
            'tris': tris, 'kind': 'animal'}
    with open(os.path.join(OUT, key + '.json'), 'w', encoding='utf-8') as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=1)
    print('[%s] meshes %d->%d tris %d height %.2f m  %d clips -> %s (%d KB, %.1fs)' % (
        key, n0, n1, tris, hmax, len(clips), path, os.path.getsize(path) // 1024, time.time() - t0), flush=True)
    return dict(tris=tris, height=hmax)


# --------------------------------------------------------------------------- preview
def _activate(objs):
    """glTF import leaves the clips in (muted) NLA strips: make them the active action."""
    for o in objs:
        ad = o.animation_data
        if not ad or not ad.nla_tracks:
            continue
        for t in ad.nla_tracks:
            if t.strips:
                st = t.strips[0]
                ad.action = st.action
                try:
                    ad.action_slot = st.action_slot
                except Exception:
                    pass
            t.mute = True


def _freeze(objs):
    """Bake the current animated pose into plain transforms (so later frame changes do not move them)."""
    _activate(objs)
    bpy.context.view_layer.update()
    mw = {o: o.matrix_world.copy() for o in objs}
    for o in objs:
        o.animation_data_clear()
    for o in sorted(objs, key=lambda o: len(o.children_recursive), reverse=True):
        o.matrix_world = mw[o]
    bpy.context.view_layer.update()
    for o in objs:
        o.matrix_world = mw[o]


def preview(samples=16, keys=None, rows=(('idle', 0), ('walk', 2), ('eat', 2), ('sit', 0), ('happy', 2)),
            name='animals_grid', yaw=25, direc=(-0.35, -1.0, 0.75), res=(1600, 1200)):
    import b3d_preview as PV
    keys = keys or KEYS
    os.makedirs(SHOTS, exist_ok=True)
    PV.setup(samples)
    PV.ground(80)
    PV.lights()
    W = {'animal_chicken': 0.7, 'animal_cow': 1.55, 'animal_cattle': 1.55}
    xmax = 0
    for r, (cl, sub) in enumerate(rows):
        x = 0.0
        y = r * 1.5
        for k in keys:
            meta = json.load(open(os.path.join(OUT, k + '.json'), encoding='utf-8'))
            info = meta['clips'][cl]
            w = W.get(k, 1.05)
            x += w / 2
            objs = PV.import_glb(os.path.join(OUT, k + '.glb'), (x, y, 0), yaw)
            _activate(objs)
            bpy.context.scene.frame_set(info['start'] + min(sub, info['frames'] - 1))
            _freeze(objs)
            x += w / 2 + 0.2
        xmax = max(xmax, x)
    far = os.path.join(GAME, 'assets3d', 'chars', 'farmer.glb')
    if os.path.exists(far):
        objs = PV.import_glb(far, (-0.5, 0, 0), 20)
        _activate(objs)
        bpy.context.scene.frame_set(0)
        _freeze(objs)
    c = Vector((xmax / 2 - 0.3, (len(rows) - 1) * 1.5 / 2, 0.3))
    PV.camera(c, max(xmax, len(rows) * 1.5) * 0.55, direc, res, fill=0.85)
    path = os.path.join(SHOTS, name + '.png')
    bc.render_to(path)
    print('wrote', path, flush=True)


def strips(samples=12, keys=None, yaw=60):
    """One image per animal: idle / walk / eat / sit / happy side by side (3/4 side view)."""
    import b3d_preview as PV
    for k in keys or KEYS:
        PV.setup(samples)
        PV.ground(60)
        PV.lights()
        meta = json.load(open(os.path.join(OUT, k + '.json'), encoding='utf-8'))
        h = meta['height']
        step = max(0.55, h * 1.45)
        poses = [('idle', 0), ('walk', 1), ('walk', 5), ('eat', 2), ('sit', 0), ('happy', 2)]
        for i, (cl, sub) in enumerate(poses):
            info = meta['clips'][cl]
            objs = PV.import_glb(os.path.join(OUT, k + '.glb'), (i * step, 0, 0), yaw)
            _activate(objs)
            bpy.context.scene.frame_set(info['start'] + sub)
            _freeze(objs)
        w = (len(poses) - 1) * step
        PV.camera(Vector((w / 2, 0, h * 0.45)), w / 2 + step * 0.5, (-0.1, -1.0, 0.45), (1500, 420), fill=0.30)
        path = os.path.join(SHOTS, 'strip_%s.png' % k)
        bc.render_to(path)
        print('wrote', path, flush=True)


def main():
    a = bc.script_args()
    keys = [x for x in a if not x.startswith('--') and x in BUILD]
    if '--strips' in a:
        strips(int(a[a.index('--samples') + 1]) if '--samples' in a else 12, keys or None)
        return
    if '--preview' in a:
        smp = int(a[a.index('--samples') + 1]) if '--samples' in a else 16
        preview(smp, keys or None)
        preview(smp, keys or None, rows=(('walk', 0), ('walk', 4), ('eat', 1), ('happy', 3)), name='animals_grid_side',
                yaw=90, direc=(0.0, -1.0, 0.35), res=(1600, 1000))
        return
    for k in keys or KEYS:
        export(k)


if __name__ == '__main__':
    main()
