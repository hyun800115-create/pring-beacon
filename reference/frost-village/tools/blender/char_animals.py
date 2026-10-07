"""
char_animals.py - cute round quadrupeds (deer, boar) for Frost Village.

Imported by char_build.build('deer' | 'boar'); not run directly.
Rig joints: root > body > neck > head (> ear_R/L), body > tail,
body > leg_FR/FL/BR/BL > knee_*.  Front = local -Y.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mathutils import Vector, Quaternion   # noqa: E402
import bl_common as bc                     # noqa: E402
import char_geo as g                       # noqa: E402

PI = math.pi


def M(name, color, rough=0.75, **kw):
    return bc.mat(name, color, rough=rough, **kw)


def sph_point(center, radii, az, el, out=0.0):
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    p = Vector((d.x * radii[0], d.y * radii[1], d.z * radii[2]))
    n = Vector((d.x / radii[0], d.y / radii[1], d.z / radii[2])).normalized()
    return Vector(center) + p + n * out, n


def on_sph(name, bm, mat, parent, center, radii, az, el, out=0.0):
    p, n = sph_point(center, radii, az, el, out)
    return g.mesh_obj(name, bm, mat, parent, loc=tuple(p), rot=(-n).to_track_quat('Y', 'Z'))


def cute_eyes(rig, head, center, radii, az=0.62, el=0.12, size=1.0, blush=True):
    eye = M('eye', '#2A2026', rough=0.25)
    hi = M('eye_hi', '#FFFFFF', rough=0.3, emission='#FFFFFF', emission_strength=1.5)
    for s in (-1, 1):
        on_sph('eye', g.bm_ellipsoid(0.030 * size, 0.016, 0.036 * size, 14, 8), eye, head, center, radii,
               s * az, el, out=-0.006)
        on_sph('eye_hi', g.bm_ellipsoid(0.010 * size, 0.006, 0.011 * size, 8, 6), hi, head, center, radii,
               s * az - 0.07, el + 0.08, out=0.003)
        if blush:
            on_sph('blush', g.bm_ellipsoid(0.034, 0.008, 0.020, 12, 6), M('blush', '#F49A9A', rough=0.9), head,
                   center, radii, s * (az + 0.32), el - 0.28, out=-0.002)


def legs(rig, positions, upper, lower, r_up, r_low, mat, hoof_mat, hoof_r=0.036):
    for name, pos in positions.items():
        rig.add('leg_' + name, 'body', pos)
        rig.add('knee_' + name, 'leg_' + name, (0, 0, -upper))
        g.mesh_obj('thigh_' + name, g.bm_capsule(r_up, upper, r_end=r_up * 0.85), mat, rig.j['leg_' + name])
        g.mesh_obj('shin_' + name, g.bm_capsule(r_low, lower - hoof_r * 0.6, r_end=r_low * 0.9), mat,
                   rig.j['knee_' + name])
        g.mesh_obj('hoof_' + name, g.bm_lathe([(0.0, -hoof_r), (hoof_r * 1.05, -hoof_r * 0.95),
                                               (hoof_r, hoof_r * 0.4), (0.0, hoof_r * 0.5)],
                                              seg=14, sy=1.15, smooth_n=8),
                   hoof_mat, rig.j['knee_' + name], loc=(0, -0.006, -lower + hoof_r * 0.05))


def build_deer():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    rig.add('body', 'root', (0, 0, 0.50))
    fur = M('deer_fur', '#C98B55', rough=0.85)
    cream = M('deer_cream', '#F3E3C6', rough=0.9)
    spot = M('deer_spot', '#FBF3E4', rough=0.9)
    dark = M('hoof', '#4A3426', rough=0.5)
    body = rig.j['body']
    g.mesh_obj('body', g.bm_ellipsoid(0.180, 0.29, 0.175, 32, 16), fur, body, loc=(0, 0.02, 0))
    g.mesh_obj('chest', g.bm_ellipsoid(0.165, 0.15, 0.175, 24, 12), fur, body, loc=(0, -0.15, 0.03))
    g.mesh_obj('belly', g.bm_ellipsoid(0.135, 0.24, 0.11, 24, 12), cream, body, loc=(0, 0.0, -0.065))
    g.mesh_obj('bib', g.bm_ellipsoid(0.10, 0.08, 0.12, 16, 10), cream, body, loc=(0, -0.24, 0.02))
    for k, (x, y) in enumerate(((0.07, -0.02), (-0.06, 0.06), (0.05, 0.14), (-0.08, -0.08), (0.0, 0.20),
                                (0.10, 0.08))):
        z = 0.165 * math.sqrt(max(0.0, 1 - (x / 0.165) ** 2 - ((y - 0.02) / 0.29) ** 2))
        g.mesh_obj('spot', g.bm_ellipsoid(0.026, 0.030, 0.010, 10, 6), spot, body, loc=(x, y, z - 0.002))
    rig.add('neck', 'body', (0, -0.21, 0.08))
    g.mesh_obj('neck', g.bm_ellipsoid(0.075, 0.075, 0.15, 16, 10), fur, rig.j['neck'], loc=(0, -0.04, 0.10),
               rot=(-24, 0, 0))
    rig.add('head', 'neck', (0, -0.09, 0.24))
    head = rig.j['head']
    hc, hr = (0, 0, 0.03), (0.150, 0.145, 0.138)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 28, 14), fur, head, loc=hc)
    g.mesh_obj('snout', g.bm_ellipsoid(0.072, 0.085, 0.062, 18, 10), cream, head, loc=(0, -0.125, -0.025))
    g.mesh_obj('nose', g.bm_ellipsoid(0.030, 0.022, 0.022, 12, 8), M('nose', '#3A2A22', rough=0.3), head,
               loc=(0, -0.205, -0.002))
    cute_eyes(rig, head, hc, hr, az=0.70, el=0.10, size=1.1)
    for s, nm in ((1, 'R'), (-1, 'L')):
        x = -0.115 if nm == 'R' else 0.115
        rig.add('ear_' + nm, 'head', (x, 0.03, 0.09), side=s)
        q = Quaternion((0, 1, 0), math.radians(55 if nm == 'R' else -55))
        g.mesh_obj('ear', g.bm_ellipsoid(0.038, 0.024, 0.085, 14, 8), fur, rig.j['ear_' + nm], loc=(0, 0, 0.06),
                   rot=q)
        g.mesh_obj('ear_in', g.bm_ellipsoid(0.024, 0.012, 0.060, 12, 6), M('ear_in', '#F2B8A8', rough=0.9),
                   rig.j['ear_' + nm], loc=(0, -0.014, 0.06), rot=q)
        # small antlers: main beam + one tine
        ant = M('antler', '#E6D3A8', rough=0.6)
        bx = 0.055 if nm == 'L' else -0.055
        sx = 1 if nm == 'L' else -1
        beam = [(bx, 0.01, 0.15), (bx + sx * 0.02, 0.0, 0.22), (bx + sx * 0.05, 0.015, 0.28),
                (bx + sx * 0.06, 0.04, 0.32)]
        g.mesh_obj('antler', g.bm_tube_path(beam, lambda t: 0.020 - 0.010 * t, segr=8), ant, head)
        tine = [(bx + sx * 0.02, 0.0, 0.21), (bx + sx * 0.0, -0.035, 0.26), (bx - sx * 0.005, -0.045, 0.285)]
        g.mesh_obj('tine', g.bm_tube_path(tine, lambda t: 0.014 - 0.006 * t, segr=8), ant, head)
    rig.add('tail', 'body', (0, 0.29, 0.07))
    g.mesh_obj('tail', g.bm_ring(0.0, 0.045, seg=16, segr=10, tufts=5, bump=0.3, seed=1.0, rz=1.3), spot,
               rig.j['tail'], loc=(0, 0.02, 0.03), rot=(30, 0, 0))
    legs(rig, {'FR': (-0.085, -0.16, -0.07), 'FL': (0.085, -0.16, -0.07),
               'BR': (-0.085, 0.17, -0.05), 'BL': (0.085, 0.17, -0.05)},
         upper=0.19, lower=0.235, r_up=0.056, r_low=0.036, mat=fur, hoof_mat=dark, hoof_r=0.036)
    rig.meta['shadow'] = [56, 22]
    return rig


def build_boar():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    rig.add('body', 'root', (0, 0, 0.37))
    fur = M('boar_fur', '#7A5440', rough=0.9)
    dark = M('boar_dark', '#4A3226', rough=0.9)
    belly = M('boar_belly', '#A47C62', rough=0.9)
    snout = M('snout', '#E3AD98', rough=0.6)
    body = rig.j['body']
    g.mesh_obj('body', g.bm_ellipsoid(0.235, 0.33, 0.225, 32, 16), fur, body, loc=(0, 0.03, 0))
    g.mesh_obj('hump', g.bm_ellipsoid(0.225, 0.19, 0.235, 24, 12), fur, body, loc=(0, -0.13, 0.04))
    g.mesh_obj('belly', g.bm_ellipsoid(0.19, 0.27, 0.15, 24, 12), belly, body, loc=(0, 0.02, -0.08))
    for k in range(9):
        t = k / 8
        y = -0.26 + 0.50 * t
        z = 0.235 * math.sqrt(max(0.0, 1 - ((y - 0.0) / 0.36) ** 2)) + 0.03 * (1 - t)
        h = 0.07 - 0.03 * abs(t - 0.3)
        g.mesh_obj('bristle', g.bm_lathe([(0.0, 0.0), (0.032, 0.01), (0.02, h * 0.6), (0.0, h)], seg=10,
                                         smooth_n=6, sy=0.6),
                   dark, body, loc=(0, y, z - 0.03), rot=(25, 0, 0))
    rig.add('neck', 'body', (0, -0.26, 0.02))
    rig.add('head', 'neck', (0, -0.05, 0.0))
    head = rig.j['head']
    hc, hr = (0, -0.05, 0.0), (0.175, 0.165, 0.160)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 28, 14), fur, head, loc=hc)
    g.mesh_obj('snout', g.bm_lathe([(0.0, -0.005), (0.072, 0.0), (0.078, 0.06), (0.074, 0.085), (0.0, 0.09)],
                                   seg=24, smooth_n=10, sx=1.0, sy=0.80),
               snout, head, loc=(0, -0.16, -0.045), rot=(90, 0, 0))
    for s in (-1, 1):
        g.mesh_obj('nostril', g.bm_ellipsoid(0.014, 0.010, 0.020, 8, 6), M('nostril', '#5A3028', rough=0.5),
                   head, loc=(s * 0.028, -0.252, -0.045))
        tusk = [(s * 0.06, -0.20, -0.075), (s * 0.085, -0.215, -0.045), (s * 0.095, -0.215, -0.005),
                (s * 0.088, -0.205, 0.022)]
        g.mesh_obj('tusk', g.bm_tube_path(tusk, lambda t: 0.017 * (1 - 0.8 * t) + 0.003, segr=8),
                   M('tusk', '#F6EEDC', rough=0.4), head)
    cute_eyes(rig, head, hc, hr, az=0.62, el=0.22, size=0.95)
    for s, nm in ((1, 'R'), (-1, 'L')):
        x = -0.10 if nm == 'R' else 0.10
        rig.add('ear_' + nm, 'head', (x, -0.02, 0.12), side=s)
        ear = g.bm_lathe([(0.0, 0.0), (0.050, 0.01), (0.035, 0.05), (0.0, 0.10)], seg=12, smooth_n=8, sy=0.45)
        g.mesh_obj('ear', ear, fur, rig.j['ear_' + nm], rot=(-20, 35 * (-s), 0))
        g.mesh_obj('ear_in', g.bm_ellipsoid(0.022, 0.010, 0.040, 10, 6), M('ear_in', '#D98C80', rough=0.9),
                   rig.j['ear_' + nm], loc=(0, -0.018, 0.04), rot=(-20, 35 * (-s), 0))
    g.mesh_obj('brow', g.bm_ellipsoid(0.12, 0.05, 0.05, 16, 8), dark, head, loc=(0, -0.03, 0.12))
    rig.add('tail', 'body', (0, 0.35, 0.06))
    curl = [(0.0, 0.0, 0.0)]
    for k in range(1, 14):
        a = k / 13 * 1.6 * PI
        curl.append((0.035 * math.sin(a), 0.03 + 0.015 * k / 13 + 0.03 * (1 - math.cos(a)) * 0.6,
                     0.035 * (1 - math.cos(a)) * 0.9))
    g.mesh_obj('tail', g.bm_tube_path(curl, lambda t: 0.014 - 0.006 * t, segr=8), fur, rig.j['tail'])
    legs(rig, {'FR': (-0.12, -0.17, -0.13), 'FL': (0.12, -0.17, -0.13),
               'BR': (-0.12, 0.19, -0.13), 'BL': (0.12, 0.19, -0.13)},
         upper=0.11, lower=0.135, r_up=0.064, r_low=0.050, mat=fur, hoof_mat=M('hoof', '#3A2A22', rough=0.5),
         hoof_r=0.042)
    rig.meta['shadow'] = [62, 26]
    return rig


def build(key):
    return build_deer() if key == 'deer' else build_boar()
