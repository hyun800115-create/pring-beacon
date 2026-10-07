"""
vil_body.py - villager base body (chibi human) + body-type proportions.

Not run directly (imported by vil_build.py).

build_body(spec)   standard-size chibi body (same joints/measurements as
                   char_build.build_human, so every char_build hair / hat / tool
                   helper fits), but with the swappable vil_face expression
                   system instead of the fixed face.
apply_proportions(rig, P)
                   turns the standard body into a kid / teen / elder / plump /
                   strong body AFTER dressing: every joint's geometry is moved
                   under a scale empty (never reset by Rig.apply) and child
                   joint rest positions are scaled to match, so hats, hair and
                   clothes built for the standard head/torso follow along.

BODY presets (P): kid ~1.1-1.2 m incl. hat, teen ~1.3 m, adult ~1.42 m,
tall, plump (round belly), strong (thick arms), elder (slightly smaller; the
hunch is a posture added to every pose in vil_anim).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mathutils import Vector               # noqa: E402

import char_geo as g                       # noqa: E402
import char_build as cb                    # noqa: E402
import vil_face                            # noqa: E402

M = cb.M
HIP_Z, CHEST_DZ, SHOULDER, NECK_DZ = cb.HIP_Z, cb.CHEST_DZ, cb.SHOULDER, cb.NECK_DZ
HEAD_C, HEAD_R = cb.HEAD_C, cb.HEAD_R
UPPER_ARM, FOREARM, THIGH, HAND_DZ = cb.UPPER_ARM, cb.FOREARM, cb.THIGH, cb.HAND_DZ
SOLE = 0.188            # knee pivot -> boot sole (standard leg)

# torso (sx, sy, sz) | head s | arm (radius, length) | hand s | leg (radius, thigh, shin) | hip spread
BODY = {
    'adult':  dict(torso=(1.0, 1.0, 1.0), head=1.0, arm=(1.0, 1.0), hand=1.0, leg=(1.0, 1.0, 1.0), hip_w=1.0),
    'tall':   dict(torso=(1.0, 0.98, 1.05), head=0.97, arm=(1.0, 1.06), hand=1.0, leg=(1.0, 1.12, 1.06),
                   hip_w=1.0),
    'kid':    dict(torso=(0.84, 0.86, 0.70), head=0.96, arm=(0.90, 0.88), hand=0.96, leg=(0.88, 0.66, 0.72),
                   hip_w=0.86),
    'teen':   dict(torso=(0.90, 0.90, 0.90), head=0.94, arm=(0.90, 0.94), hand=0.90, leg=(0.88, 0.96, 0.95),
                   hip_w=0.9),
    'plump':  dict(torso=(1.26, 1.22, 0.98), head=1.0, arm=(1.12, 0.98), hand=1.06, leg=(1.16, 0.88, 0.94),
                   hip_w=1.25),
    'strong': dict(torso=(1.08, 1.02, 1.0), head=0.98, arm=(1.20, 1.04), hand=1.12, leg=(1.06, 1.0, 1.0),
                   hip_w=1.06),
    'elder':  dict(torso=(1.0, 1.0, 0.92), head=0.98, arm=(1.0, 0.96), hand=0.96, leg=(1.0, 0.88, 0.92),
                   hip_w=1.0),
}


def build_body(spec):
    """Standard-size body; spec controls colours & optional parts (see vil_build)."""
    rig = g.Rig('human')
    rig.add('root', None, (0, 0, 0))
    rig.add('hips', 'root', (0, 0, HIP_Z))
    rig.add('spine', 'hips', (0, 0, 0))
    rig.add('chest', 'spine', (0, 0, CHEST_DZ))
    rig.add('neck', 'chest', (0, 0, NECK_DZ))
    rig.add('head', 'neck', (0, 0, 0))
    for s, name in ((1, 'R'), (-1, 'L')):
        x = -SHOULDER[0] if name == 'R' else SHOULDER[0]
        rig.add('sh_' + name, 'chest', (x, SHOULDER[1], SHOULDER[2]), side=s)
        rig.add('el_' + name, 'sh_' + name, (0, 0, -UPPER_ARM), side=s)
        rig.add('hand_' + name, 'el_' + name, (0, 0, -FOREARM - HAND_DZ), side=s)
        rig.add('hip_' + name, 'hips', (-0.085 if name == 'R' else 0.085, 0, 0), side=s)
        rig.add('knee_' + name, 'hip_' + name, (0, 0, -THIGH), side=s)

    coat = spec['coat_mat']
    sleeve = spec.get('sleeve_mat', coat)
    fur = cb.fur_mat(spec)
    pants = spec.get('pants_mat') or M('pants', spec.get('pants', '#4A3830'), rough=0.85)
    boots = M('boots', spec.get('boots', '#5A3A26'), rough=0.6)
    mitt = M('mitten', spec.get('mitten', '#6B4A2E'), rough=0.7)
    skin = M('skin', spec.get('skin', cb.SKIN), rough=0.55)

    hem_r = spec.get('hem_r', 0.250)
    hz = spec.get('hem_z', -0.095)
    prof = spec.get('torso_profile', [(hem_r, hz), (hem_r - 0.012, hz + 0.08), (0.212, 0.10),
                                      (0.208, 0.22), (0.195, 0.31), (0.155, 0.39), (0.07, 0.45),
                                      (0.0, 0.46)])
    g.mesh_obj('torso', g.bm_lathe(prof, seg=40, sy=spec.get('torso_sy', 0.84), smooth_n=26, cap_top=False),
               coat, rig.j['spine'])
    if spec.get('hem_fur', True):
        g.mesh_obj('hem_fur', g.bm_ring(hem_r - 0.004, 0.042, seg=72, segr=12, sy=0.84, rz=0.85,
                                        tufts=13, bump=0.35, seed=1.0),
                   fur, rig.j['spine'], loc=(0, 0, hz + 0.015))

    head = rig.j['head']
    g.mesh_obj('head', g.bm_ellipsoid(*HEAD_R, seg=40, rings=20), skin, head, loc=(0, 0, HEAD_C))
    vil_face.build_face(rig, spec)

    forearm_mat = skin if spec.get('bare_forearms') else sleeve
    for name in ('R', 'L'):
        g.mesh_obj('uarm_' + name, g.bm_capsule(0.076, UPPER_ARM, r_end=0.070), sleeve, rig.j['sh_' + name])
        g.mesh_obj('farm_' + name, g.bm_capsule(0.066 if spec.get('bare_forearms') else 0.070, FOREARM - 0.02,
                                                r_end=0.058 if spec.get('bare_forearms') else 0.062),
                   forearm_mat, rig.j['el_' + name])
        if spec.get('bare_forearms'):
            g.mesh_obj('rollup_' + name, g.bm_ring(0.064, 0.026, seg=28, segr=10), sleeve, rig.j['el_' + name],
                       loc=(0, 0, 0.0))
        if spec.get('cuff_fur', True):
            g.mesh_obj('cuff_' + name, g.bm_ring(0.056, 0.028, seg=32, segr=10, tufts=7, bump=0.3,
                                                 seed=2.0 if name == 'R' else 3.0),
                       fur, rig.j['el_' + name], loc=(0, 0, -FOREARM + 0.012))
        hand_mat = skin if spec.get('bare_hands') else mitt
        g.mesh_obj('mitt_' + name, g.bm_ellipsoid(0.058, 0.052, 0.060, 20, 12), hand_mat, rig.j['hand_' + name])
        g.mesh_obj('thumb_' + name, g.bm_ellipsoid(0.024, 0.024, 0.032, 10, 8), hand_mat,
                   rig.j['hand_' + name], loc=(0.0, -0.045, 0.012), rot=(25, 0, 0))

    for name in ('R', 'L'):
        g.mesh_obj('thigh_' + name, g.bm_capsule(0.072, THIGH, r_end=0.064), pants, rig.j['hip_' + name])
        g.mesh_obj('shin_' + name, g.bm_capsule(0.062, 0.07, r_end=0.060), pants, rig.j['knee_' + name])
        bprof = [(0.0, -0.200), (0.055, -0.198), (0.072, -0.17), (0.070, -0.12),
                 (0.064, -0.07), (0.0, -0.05)]
        g.mesh_obj('boot_' + name, g.bm_lathe(bprof, seg=24, sy=1.25, smooth_n=14,
                                              yoff=lambda z: -0.028 * (1 - (z + 0.2) / 0.15)),
                   boots, rig.j['knee_' + name], loc=(0, -0.012, 0.012))
        if spec.get('boot_fur', True):
            g.mesh_obj('bootfur_' + name, g.bm_ring(0.062, 0.026, seg=32, segr=10, tufts=7,
                                                    bump=0.35, seed=4.0, sy=1.1),
                       fur, rig.j['knee_' + name], loc=(0, -0.006, -0.06))
    rig.meta['mats'] = dict(coat=coat, fur=fur, pants=pants, boots=boots, mitt=mitt, skin=skin)
    return rig


# --------------------------------------------------------------------------- proportions

def _group(rig, jname, scale):
    """Move the non-joint children of joint `jname` under a scale empty."""
    j = rig.j[jname]
    joints = set(rig.j.values())
    kids = [c for c in j.children if c not in joints]
    if not kids or tuple(scale) == (1.0, 1.0, 1.0):
        return None
    s = g.empty(jname + '_S', j, (0, 0, 0))
    s.scale = scale
    for c in kids:
        c.parent = s
    return s


def apply_proportions(rig, P):
    """Scale part groups + child joint rest positions (call after dressing)."""
    tx, ty, tz = P['torso']
    hs = P['head']
    ar, al = P['arm']
    hd = P['hand']
    lr, lt, ls = P['leg']
    scales = {'spine': (tx, ty, tz), 'chest': (tx, ty, tz), 'neck': (1, 1, 1), 'head': (hs, hs, hs),
              'hips': (tx, ty, 1.0)}
    for side in ('R', 'L'):
        scales['sh_' + side] = (ar, ar, al)
        scales['el_' + side] = (ar, ar, al)
        scales['hand_' + side] = (hd, hd, hd)
        scales['hip_' + side] = (lr, lr, lt)
        scales['knee_' + side] = (lr, lr, ls)
    for jn, sc in scales.items():
        if jn in rig.j:
            _group(rig, jn, sc)
    # child joint rest positions follow their parent's group scale
    for jn, e in rig.j.items():
        par = e.parent
        pname = next((k for k, v in rig.j.items() if v == par), None)
        if pname is None or pname not in scales:
            continue
        sx, sy, sz = scales[pname]
        rl = rig.rest_loc[jn]
        rig.rest_loc[jn] = Vector((rl.x * sx, rl.y * sy, rl.z * sz))
        e.location = rig.rest_loc[jn]
    for side, sx in (('R', -1), ('L', 1)):
        rig.rest_loc['hip_' + side] = Vector((sx * 0.085 * P['hip_w'], 0, 0))
        rig.j['hip_' + side].location = rig.rest_loc['hip_' + side]
    hip_z = THIGH * lt + SOLE * ls
    rig.rest_loc['hips'] = Vector((0, 0, hip_z))
    rig.j['hips'].location = rig.rest_loc['hips']
    rig.meta['body'] = dict(P)
    rig.meta['leg_len'] = hip_z
    rig.meta['torso_scale'] = (tx, ty, tz)
    return rig
