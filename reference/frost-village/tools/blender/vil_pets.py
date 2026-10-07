"""
vil_pets.py - cute round village pets: shiba dog (red scarf), orange tabby cat,
baby penguin.  Imported by vil_build.build('pet_*'); not run directly.

Quadruped rig (dog, cat): root > body > neck > head (> ear_R/L), body > tail,
body > leg_FR/FL/BR/BL > knee_*   (same joint names as char_animals, so the
vil_anim._quad poses drive both).
Penguin rig: root > body > head, body > flip_R/L, root > foot_R/L.
Face toggles: p_eye_dot, p_eye_blink, p_eye_happy, p_m_closed, p_m_open.
Front = local -Y.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy                                   # noqa: E402
from mathutils import Vector, Quaternion     # noqa: E402

import bl_common as bc                       # noqa: E402
import char_geo as g                         # noqa: E402
import char_animals as ca                    # noqa: E402
import vil_face as vf                        # noqa: E402
from vil_dress import fuzz, catmull3                   # noqa: E402

PI = math.pi
TAU = math.tau


def M(name, color, rough=0.75, **kw):
    return bc.mat(name, color, rough=rough, **kw)


def mat_stripes(name, base, dark, axis='Y', scale=26.0, width=0.30, wobble=0.25, rough=0.85):
    """Tabby stripes: bands across `axis` of the object's own coordinates."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    p.inputs['Roughness'].default_value = rough
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])

    def op(o, a, b):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = o
        for idx, x in enumerate((a, b)):
            if isinstance(x, float):
                n.inputs[idx].default_value = x
            else:
                nt.links.new(x, n.inputs[idx])
        return n.outputs[0]
    other = 'X' if axis != 'X' else 'Z'
    wob = op('MULTIPLY', op('SINE', op('MULTIPLY', sep.outputs[other], 18.0), 0.0), wobble * 0.08)
    s = op('FRACT', op('MULTIPLY', op('ADD', sep.outputs[axis], wob), scale / TAU), 0.0)
    band = op('LESS_THAN', s, width)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*bc.srgb_to_linear(base), 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (*bc.srgb_to_linear(dark), 1)
    nt.links.new(band, ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m


def decal(parent, name, bm, mat, center):
    return g.mesh_obj(name, bm, mat, parent, loc=center)


def pet_eyes(rig, head, hc, hr, eu=0.062, ev=0.012, ew=0.026, eh=0.034, brows=None):
    eye = M('eye', '#2A2026', rough=0.22)
    hi = M('eye_hi', '#FFFFFF', rough=0.3, emission='#FFFFFF', emission_strength=1.6)
    parts = {'p_eye_dot': [], 'p_eye_blink': [], 'p_eye_happy': []}
    for s in (-1, 1):
        u = s * eu
        parts['p_eye_dot'] += [
            decal(head, 'eye', vf.bm_blob(vf.ellipse(u, ev, ew, eh, 22), thick=0.012, radii=hr), eye, hc),
            decal(head, 'eye_hi', vf.bm_blob(vf.ellipse(u - ew * 0.3, ev + eh * 0.35, ew * 0.38, eh * 0.3, 12),
                                             thick=0.006, out=0.010, radii=hr), hi, hc)]
        parts['p_eye_blink'].append(decal(head, 'eye_blink', vf.bm_stroke(
            vf.arc(u, ev + eh * 0.2, ew * 1.1, PI + 0.4, TAU - 0.4, 9, ry=eh * 0.4), 0.0085, thick=0.010, radii=hr),
            eye, hc))
        parts['p_eye_happy'].append(decal(head, 'eye_happy', vf.bm_stroke(
            vf.arc(u, ev - eh * 0.3, ew * 1.1, 0.3, PI - 0.3, 9, ry=eh * 0.9), 0.0095, thick=0.012, taper=0.6,
            radii=hr), eye, hc))
    for k, v in parts.items():
        rig.toggle(k, v)
    if brows:
        for s in (-1, 1):
            decal(head, 'maro', vf.bm_blob(vf.ellipse(s * (eu - 0.008), ev + 0.062, 0.018, 0.012, 12), thick=0.006,
                                           radii=hr), M('maro', brows, rough=0.9), hc)


def blush(head, hc, hr, u=0.10, v=-0.03, a=0.03, b=0.017):
    for s in (-1, 1):
        decal(head, 'blush', vf.bm_blob(vf.ellipse(s * u, v, a, b, 16), thick=0.003, out=-0.001, edge=0.6, radii=hr),
              M('blush', '#F49A9A', rough=0.9), hc)


def quad_legs(rig, positions, upper, lower, r_up, r_low, mats, paw_mat, paw_r):
    for name, pos in positions.items():
        rig.add('leg_' + name, 'body', pos)
        rig.add('knee_' + name, 'leg_' + name, (0, 0, -upper))
        g.mesh_obj('thigh_' + name, g.bm_capsule(r_up, upper, r_end=r_up * 0.85), mats[0], rig.j['leg_' + name])
        g.mesh_obj('shin_' + name, g.bm_capsule(r_low, lower - paw_r * 0.6, r_end=r_low * 0.95), mats[1],
                   rig.j['knee_' + name])
        g.mesh_obj('paw_' + name, g.bm_ellipsoid(paw_r * 1.05, paw_r * 1.3, paw_r * 0.8, 14, 8), paw_mat,
                   rig.j['knee_' + name], loc=(0, -paw_r * 0.35, -lower + paw_r * 0.75))


def ear(rig, side, parent_loc, mat, inner, h=0.10, w=0.055, tilt=18, out_tilt=14):
    nm = side
    rig.add('ear_' + nm, 'head', parent_loc, side=1 if nm == 'R' else -1)
    s = -1 if nm == 'R' else 1
    q = Quaternion((0, 1, 0), math.radians(s * out_tilt)) @ Quaternion((1, 0, 0), math.radians(-tilt))
    cone = g.bm_lathe([(0.0, 0.0), (w, 0.005), (w * 0.75, h * 0.45), (0.0, h)], seg=14, sy=0.45, smooth_n=8)
    g.mesh_obj('ear', cone, mat, rig.j['ear_' + nm], rot=q)
    cin = g.bm_lathe([(0.0, 0.0), (w * 0.6, 0.004), (w * 0.4, h * 0.42), (0.0, h * 0.8)], seg=12, sy=0.25,
                     smooth_n=6)
    g.mesh_obj('ear_in', cin, inner, rig.j['ear_' + nm], loc=(0, -0.012, 0.006), rot=q)


# --------------------------------------------------------------------------- dog

def build_dog():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    rig.add('body', 'root', (0, 0, 0.215))
    org = M('shiba', '#E39A4E', rough=0.85)
    cream = M('shiba_cream', '#F8EBD3', rough=0.9)
    body = rig.j['body']
    g.mesh_obj('body', g.bm_ellipsoid(0.135, 0.20, 0.125, 28, 14), org, body, loc=(0, 0.02, 0))
    g.mesh_obj('belly', g.bm_ellipsoid(0.11, 0.17, 0.09, 24, 12), cream, body, loc=(0, 0.01, -0.05))
    g.mesh_obj('chest', g.bm_ellipsoid(0.10, 0.08, 0.11, 18, 10), cream, body, loc=(0, -0.15, 0.0))
    rig.add('neck', 'body', (0, -0.15, 0.07))
    rig.add('head', 'neck', (0, -0.04, 0.13))
    head = rig.j['head']
    hc, hr = Vector((0, 0, 0.0)), (0.150, 0.135, 0.128)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 32, 16), org, head, loc=tuple(hc))
    g.mesh_obj('cheeks', g.bm_ellipsoid(0.125, 0.10, 0.075, 24, 12), cream, head, loc=(0, -0.045, -0.055))
    mz_c, mz_r = Vector((0, -0.115, -0.045)), (0.060, 0.052, 0.045)
    g.mesh_obj('muzzle', g.bm_ellipsoid(*mz_r, 20, 10), cream, head, loc=tuple(mz_c))
    g.mesh_obj('nose', g.bm_ellipsoid(0.022, 0.016, 0.017, 12, 8), M('nose', '#2A2026', rough=0.3), head,
               loc=(0, -0.165, -0.020))
    pet_eyes(rig, head, hc, hr, eu=0.062, ev=0.020, ew=0.024, eh=0.032, brows='#F8EBD3')
    blush(head, hc, hr, u=0.105, v=-0.035)
    mouth = M('mouth_line', '#5A2A2A', rough=0.5)
    closed = decal(head, 'm_w', vf.bm_stroke([(-0.030, -0.006), (-0.014, -0.024), (0.0, -0.012), (0.014, -0.024),
                                              (0.030, -0.006)], 0.0055, thick=0.008, taper=0.6, radii=mz_r),
                   mouth, mz_c)
    opn = [decal(head, 'm_open', vf.bm_blob(vf.ellipse(0, -0.020, 0.028, 0.022, 18), thick=0.008, radii=mz_r),
                 M('mouth_in', '#6E2430', rough=0.5), mz_c),
           decal(head, 'tongue', vf.bm_blob(vf.ellipse(0, -0.040, 0.018, 0.022, 14), thick=0.012, out=0.004,
                                            radii=mz_r), M('tongue', '#EE7F86', rough=0.5), mz_c)]
    rig.toggle('p_m_closed', [closed])
    rig.toggle('p_m_open', opn)
    inner = M('ear_in', '#F8EBD3', rough=0.9)
    ear(rig, 'R', (-0.085, 0.01, 0.085), org, inner, h=0.095, w=0.055)
    ear(rig, 'L', (0.085, 0.01, 0.085), org, inner, h=0.095, w=0.055)
    # red scarf + knot
    red = M('scarf', '#D9483B', rough=0.85)
    g.mesh_obj('scarf', g.bm_ring(0.095, 0.035, seg=40, segr=10, sy=0.9), red, rig.j['neck'], loc=(0, -0.02, 0.05),
               rot=(-35, 0, 0))
    g.mesh_obj('scarf_knot', g.bm_ellipsoid(0.03, 0.025, 0.03, 10, 8), red, rig.j['neck'], loc=(0.03, -0.11, 0.0))
    g.mesh_obj('scarf_tail', g.bm_box(0.035, 0.012, 0.075, bevel=0.008), red, rig.j['neck'],
               loc=(0.045, -0.115, -0.04), rot=(10, 0, -12))
    # curly tail over the back
    rig.add('tail', 'body', (0, 0.19, 0.07))
    pts = []
    for k in range(16):
        a = k / 15 * 1.55 * PI
        pts.append((0.012 * math.sin(a * 2), 0.06 * (1 - math.cos(a)) * 0.55 - 0.02 * k / 15,
                    0.07 * math.sin(a) + 0.012 * k / 15))
    g.mesh_obj('tail', g.bm_tube_path(pts, lambda t: 0.040 - 0.016 * t, segr=12), org, rig.j['tail'])
    g.mesh_obj('tail_tip', g.bm_ellipsoid(0.028, 0.028, 0.028, 10, 8), cream, rig.j['tail'], loc=tuple(pts[-1]))
    quad_legs(rig, {'FR': (-0.075, -0.12, -0.06), 'FL': (0.075, -0.12, -0.06),
                    'BR': (-0.075, 0.12, -0.05), 'BL': (0.075, 0.12, -0.05)},
              upper=0.075, lower=0.095, r_up=0.045, r_low=0.034, mats=(org, cream), paw_mat=cream, paw_r=0.034)
    rig.meta['shadow'] = [42, 18]
    return rig


# --------------------------------------------------------------------------- cat

def build_cat():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    rig.add('body', 'root', (0, 0, 0.19))
    tab_body = mat_stripes('tabby_body', '#EE9F4E', '#C8692A', axis='Y', scale=60.0, width=0.32)
    tab_head = mat_stripes('tabby_head', '#EE9F4E', '#C8692A', axis='X', scale=70.0, width=0.22)
    tab_tail = mat_stripes('tabby_tail', '#EE9F4E', '#C8692A', axis='Z', scale=70.0, width=0.40)
    org = M('cat_org', '#EE9F4E', rough=0.85)
    cream = M('cat_cream', '#FBF0DC', rough=0.9)
    body = rig.j['body']
    g.mesh_obj('body', g.bm_ellipsoid(0.115, 0.19, 0.11, 28, 14), tab_body, body, loc=(0, 0.02, 0))
    g.mesh_obj('belly', g.bm_ellipsoid(0.09, 0.15, 0.075, 24, 12), cream, body, loc=(0, 0.0, -0.045))
    g.mesh_obj('chest', g.bm_ellipsoid(0.085, 0.07, 0.095, 18, 10), cream, body, loc=(0, -0.14, 0.0))
    rig.add('neck', 'body', (0, -0.14, 0.06))
    rig.add('head', 'neck', (0, -0.035, 0.115))
    head = rig.j['head']
    hc, hr = Vector((0, 0, 0)), (0.140, 0.120, 0.115)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 32, 16), tab_head, head, loc=tuple(hc))
    mz_c, mz_r = Vector((0, -0.095, -0.040)), (0.058, 0.045, 0.040)
    g.mesh_obj('muzzle', g.bm_ellipsoid(*mz_r, 20, 10), cream, head, loc=tuple(mz_c))
    g.mesh_obj('nose', g.bm_ellipsoid(0.016, 0.012, 0.012, 10, 6), M('cat_nose', '#E77A86', rough=0.4), head,
               loc=(0, -0.137, -0.020))
    pet_eyes(rig, head, hc, hr, eu=0.058, ev=0.012, ew=0.024, eh=0.032)
    blush(head, hc, hr, u=0.095, v=-0.03)
    mouth = M('mouth_line', '#5A2A2A', rough=0.5)
    closed = decal(head, 'm_w', vf.bm_stroke([(-0.024, -0.004), (-0.012, -0.018), (0.0, -0.008), (0.012, -0.018),
                                              (0.024, -0.004)], 0.005, thick=0.008, taper=0.6, radii=mz_r),
                   mouth, mz_c)
    opn = [decal(head, 'm_open', vf.bm_blob(vf.ellipse(0, -0.016, 0.020, 0.018, 16), thick=0.008, radii=mz_r),
                 M('mouth_in', '#6E2430', rough=0.5), mz_c),
           decal(head, 'tongue', vf.bm_blob(vf.ellipse(0, -0.026, 0.012, 0.008, 10), thick=0.006, out=0.004,
                                            radii=mz_r), M('tongue', '#EE7F86', rough=0.5), mz_c)]
    rig.toggle('p_m_closed', [closed])
    rig.toggle('p_m_open', opn)
    wh = M('whisker', '#FFFFFF', rough=0.5)
    for s in (-1, 1):
        for k, dv in enumerate((0.0, -0.016)):
            p0 = mz_c + Vector((s * 0.045, -0.02, dv))
            p1 = p0 + Vector((s * 0.075, 0.01, dv * 0.8 + 0.006 * (1 - k)))
            g.mesh_obj('whisker', g.bm_tube_path([p0, p1], 0.0028, segr=4), wh, head)
    inner = M('ear_in', '#F5B9B0', rough=0.9)
    ear(rig, 'R', (-0.075, 0.0, 0.075), org, inner, h=0.090, w=0.050, tilt=8, out_tilt=18)
    ear(rig, 'L', (0.075, 0.0, 0.075), org, inner, h=0.090, w=0.050, tilt=8, out_tilt=18)
    rig.add('tail', 'body', (0, 0.19, 0.03))
    pts = [(0, 0, 0), (0, 0.06, 0.03), (0, 0.10, 0.10), (0, 0.11, 0.18), (0, 0.08, 0.25), (0, 0.04, 0.27)]
    g.mesh_obj('tail', g.bm_tube_path(catmull3(pts, 18), lambda t: 0.028 - 0.006 * t, segr=12), tab_tail,
               rig.j['tail'])
    quad_legs(rig, {'FR': (-0.062, -0.11, -0.05), 'FL': (0.062, -0.11, -0.05),
                    'BR': (-0.062, 0.12, -0.045), 'BL': (0.062, 0.12, -0.045)},
              upper=0.065, lower=0.085, r_up=0.038, r_low=0.029, mats=(org, org), paw_mat=cream, paw_r=0.030)
    rig.meta['shadow'] = [36, 15]
    return rig


# --------------------------------------------------------------------------- penguin

def build_penguin():
    rig = g.Rig('animal')
    rig.add('root', None, (0, 0, 0))
    rig.add('body', 'root', (0, 0, 0.06))
    navy = M('peng_navy', '#2C3650', rough=0.6)
    white = M('peng_white', '#F4F7FB', rough=0.7)
    orange = M('peng_org', '#F2A03A', rough=0.5)
    body = rig.j['body']
    g.mesh_obj('body', g.bm_lathe([(0.0, 0.0), (0.12, 0.01), (0.16, 0.08), (0.165, 0.16), (0.14, 0.26),
                                   (0.10, 0.31), (0.0, 0.33)], seg=36, sy=0.92, smooth_n=20), navy, body)
    g.mesh_obj('belly', g.bm_ellipsoid(0.13, 0.10, 0.15, 28, 14), white, body, loc=(0, -0.07, 0.13))
    rig.add('head', 'body', (0, 0, 0.30))
    head = rig.j['head']
    hc, hr = Vector((0, 0, 0.07)), (0.140, 0.130, 0.130)
    g.mesh_obj('head', g.bm_ellipsoid(*hr, 32, 16), navy, head, loc=tuple(hc))
    # white face mask (heart-ish) as a decal on the head front
    mask = []
    for k in range(40):
        t = TAU * k / 40
        x = 0.085 * math.sin(t) * (1.0 + 0.25 * math.cos(t))
        y = -0.01 + 0.07 * math.cos(t) - 0.02 * math.cos(2 * t)
        mask.append((x, y))
    decal(head, 'face_mask', vf.bm_blob(mask, thick=0.010, out=0.0, edge=0.8, radii=hr), white, hc)
    for s in (-1, 1):
        decal(head, 'face_side', vf.bm_blob(vf.ellipse(s * 0.06, 0.0, 0.05, 0.06, 18), thick=0.010, out=0.0, edge=0.8,
                                            radii=hr), white, hc)
    pet_eyes(rig, head, hc, (hr[0], hr[1] * 0.92, hr[2]), eu=0.056, ev=0.008, ew=0.022, eh=0.030)
    blush(head, hc, hr, u=0.085, v=-0.040, a=0.026, b=0.015)
    # beak (closed / open)
    bk = Vector((0, -0.135, 0.045))
    closed = g.mesh_obj('beak', g.bm_lathe([(0.0, 0.0), (0.030, 0.005), (0.018, 0.030), (0.0, 0.045)], seg=14,
                                           sy=0.6, smooth_n=8), orange, head, loc=tuple(bk), rot=(90, 0, 0))
    top = g.mesh_obj('beak_top', g.bm_lathe([(0.0, 0.0), (0.030, 0.004), (0.016, 0.030), (0.0, 0.042)], seg=14,
                                            sy=0.45, smooth_n=8), orange, head, loc=tuple(bk + Vector((0, 0, 0.008))),
                     rot=(80, 0, 0))
    bot = g.mesh_obj('beak_bot', g.bm_lathe([(0.0, 0.0), (0.026, 0.004), (0.012, 0.024), (0.0, 0.032)], seg=14,
                                            sy=0.4, smooth_n=8), orange, head, loc=tuple(bk + Vector((0, 0, -0.012))),
                     rot=(115, 0, 0))
    inside = g.mesh_obj('beak_in', g.bm_ellipsoid(0.02, 0.012, 0.012, 10, 6), M('mouth_in', '#6E2430', rough=0.5),
                        head, loc=tuple(bk + Vector((0, -0.006, -0.004))))
    rig.toggle('p_m_closed', [closed])
    rig.toggle('p_m_open', [top, bot, inside])
    # tuft
    for k, (dx, tl) in enumerate(((-0.02, -25), (0.0, 0), (0.02, 25))):
        g.mesh_obj('tuft', g.bm_lathe([(0.0, 0.0), (0.012, 0.01), (0.006, 0.04), (0.0, 0.05)], seg=8, smooth_n=6),
                   navy, head, loc=(dx, 0.0, hc.z + hr[2] - 0.01), rot=(0, tl, 0))
    for nm, sx in (('R', -1), ('L', 1)):
        rig.add('flip_' + nm, 'body', (sx * 0.150, 0.0, 0.22), side=1 if nm == 'R' else -1)
        g.mesh_obj('flipper', g.bm_ellipsoid(0.03, 0.065, 0.11, 14, 10), navy, rig.j['flip_' + nm],
                   loc=(sx * 0.012, 0.0, -0.09), rot=(0, sx * 10, 0))
        rig.add('foot_' + nm, 'root', (sx * 0.065, -0.02, 0.0))
        g.mesh_obj('foot', g.bm_ellipsoid(0.045, 0.065, 0.022, 14, 8), orange, rig.j['foot_' + nm],
                   loc=(0, -0.03, 0.02))
    rig.meta['shadow'] = [32, 14]
    return rig


PET_SCALE = {'pet_dog': 1.28, 'pet_cat': 1.30, 'pet_penguin': 1.18}


def build(key):
    rig = {'pet_dog': build_dog, 'pet_cat': build_cat, 'pet_penguin': build_penguin}[key]()
    # uniform size-up: a non-joint parent of root (Rig.reset never touches it)
    s = PET_SCALE[key]
    top = g.empty('pet_scale', None, (0, 0, 0))
    top.scale = (s, s, s)
    rig.j['root'].parent = top
    rig.meta['scale'] = s
    rig.meta['shadow'] = [round(v * s) for v in rig.meta['shadow']]
    return rig
