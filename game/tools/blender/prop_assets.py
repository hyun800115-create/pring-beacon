"""
prop_assets.py - every Frost Village prop / station / building / decor / item,
built procedurally in Blender (bpy).  The registry ASSETS maps a sprite key
(CONTRACT section 4) to its builder + metadata.  prop_render.py renders them.

Conventions
  * 1 unit = 1 m, world origin = footprint centre = sprite anchor.
  * Buildings are aligned to the world axes (they read as iso diamonds).  Their
    "front" is local -Y, which faces screen DOWN-LEFT (SW).  Things whose
    opening must be seen (oven mouth, mine tunnel) face the camera (S) instead.
  * Snow sits on up-facing surfaces (geometry caps or the snowy() shader).
  * Items: no shadow, 72x72 frame, anchor (36,54) = bottom centre, lying flat,
    chunky thickness so stacks read like the reference's salmon tower.

Not run directly - see prop_render.py.
"""
import math
from collections import OrderedDict

import bpy  # noqa: F401  (must be imported before mathutils when bpy is a module)
from mathutils import Vector, Matrix

import prop_lib as L
from prop_lib import PAL, C, flat, snowy, tonal, box, cyl, sphere, blob, log, revolve, extrude, hexmix

ASSETS = OrderedDict()

ITEM_FRAME = (72, 72)
ITEM_ANCHOR = (36, 54)
CAM_DIR = Vector((0.612, -0.612, 0.5))      # from object toward the camera


def asset(key, kind, atlas, fp=None, shadow=True, samples=64, yaw=0.0, work=0, fps=8, notes='',
          item=None, front=None, catcher=14.0):
    """Register a builder.  fp = footprint in metres: (a along X, b along Y) or ('r', radius).
    item = {'thickness': m} for items.  work = number of work frames (stations: 4)."""
    def deco(fn):
        ASSETS[key] = dict(key=key, fn=fn, kind=kind, atlas=atlas, fp=fp, shadow=shadow and not item,
                           samples=samples, yaw=yaw, work=work, fps=fps, notes=notes, item=item,
                           front=front, catcher=catcher)
        return fn
    return deco


# =========================================================================== small helpers

def orient(ob, pos, xaxis, zaxis):
    """Place an object with explicit local X / Z axes (Y = Z x X)."""
    x = Vector(xaxis).normalized()
    z = Vector(zaxis).normalized()
    y = z.cross(x).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(pos)
    ob.matrix_world = m
    return ob


def arch_pts(w, h, n=12):
    """Arch outline (rectangle + half circle), base centred at (0,0), CCW."""
    r = w / 2.0
    rh = max(0.0, h - r)
    pts = [(-r, 0.0), (r, 0.0), (r, rh)]
    for i in range(1, n):
        t = math.pi * i / n
        pts.append((r * math.cos(t), rh + r * math.sin(t)))
    pts.append((-r, rh))
    return pts


def facing_rot(psi_deg):
    """rot for an XY outline extruded along +local Z so it stands vertical and
    extrudes toward direction (sin psi, -cos psi): psi=0 -> -Y, 90 -> +X, 45 -> camera."""
    return (90.0, 0.0, psi_deg)


def facing_dir(psi_deg):
    p = math.radians(psi_deg)
    return Vector((math.sin(p), -math.cos(p), 0.0))


def roof_panel(name, W, y0, z0, y1, z1, thick, mat, x=0.0, snow=True, seed=0, snow_t=0.11):
    """Sloped roof panel between (y0,z0) and (y1,z1) (bottom surface on that line),
    W long along X, with a soft snow layer on top."""
    dy, dz = y1 - y0, z1 - z0
    ln = math.hypot(dy, dz)
    ang = math.degrees(math.atan2(dz, dy))
    n = Vector((0.0, -math.sin(math.radians(ang)), math.cos(math.radians(ang))))
    mid = Vector((x, (y0 + y1) / 2, (z0 + z1) / 2))
    p = box(name, (W, ln, thick), tuple(mid + n * thick / 2), rot=(ang, 0, 0), mat=mat, bevel=0.035,
            origin='center')
    out = [p]
    if snow:
        # leave a strip of roof visible at the lower (eave) edge
        up = Vector((0.0, dy, dz)).normalized()
        if dz < 0:
            up = -up
        margin = min(0.55, ln * 0.33)
        c = mid + n * (thick - 0.01) + up * (margin / 2)
        s = L.snow_slab(name + '_snow', W - 0.1, ln - margin, snow_t, tuple(c), rot=(ang, 0, 0), seed=seed,
                        droop=0.0)
        out.append(s)
    return out


def snow_cap(name, r, loc, h=0.07, seed=0, scale=(1, 1, 1)):
    """Small snow mound (post tops, lids)."""
    return blob(name, r, loc, flat('snow_mat', 0.9), scale=(scale[0], scale[1], h / r * scale[2]), seed=seed,
                amp=0.12, freq=2.0, subdiv=2, flat_bottom=0.0)


def ore_mat():
    """Grey stone with orange ore veins and snow on top."""
    key = 'ore_rock'
    if key in L._CUSTOM:
        return L._CUSTOM[key]
    nb = L.NB('ore_rock', rough=0.8)
    nz = nb.noise(2.6, 3.0)
    v = nb.math('ABSOLUTE', nb.math('SUBTRACT', nz, 0.5))
    vein = nb.map_range(v, 0.035, 0.012)
    tone = nb.map_range(nb.noise(1.2, 1.0), 0.3, 0.7)
    stone = nb.mix_rgb(tone, C('#4E5562'), C('#677080'))
    col = nb.mix_rgb(vein, stone, C('ore'))
    geo = nb.n('ShaderNodeNewGeometry')
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.link(geo.outputs['Normal'], sep.inputs[0])
    sn = nb.math('ADD', sep.outputs['Z'], nb.math('MULTIPLY', nb.math('SUBTRACT', nb.noise(3.0, 2.0), 0.5), 0.5))
    col = nb.mix_rgb(nb.map_range(sn, 0.8, 0.92), col, C('snow_mat'))
    nb.base(col)
    L._CUSTOM[key] = nb.m
    return nb.m


def ore_nugget_mat():
    return flat('ore', 0.35, 0.25, emission='#FF9A3C', emission_strength=0.25)


# =========================================================================== shared sub-models

def pine(seed=1, tiers=4, base_r=1.05, top_z=3.15, tier_h=1.2, first_z=0.6, snow_f=0.7, tips=9,
         light='pine', dark='pine_dark', trunk_r=0.17, narrow=1.0, droop=0.11, base_snow=False):
    """Stylised pine: stacked star-shaped tiers with drooping bough tips and
    geometric snow caps with drippy edges."""
    rnd = L.rng(seed)
    bark = tonal('bark', 0.18, 6.0, rough=0.9)
    L.cyl('trunk', trunk_r, first_z + 0.5, mat=bark, r_top=trunk_r * 0.7, segs=12, bevel=0.03)
    L.cyl('root', trunk_r * 1.5, 0.12, mat=bark, r_top=trunk_r, segs=12, bevel=0.03)
    step = (top_z - tier_h * 0.75 - first_z) / max(1, tiers - 1)
    snow_m = flat('snow_mat', 0.9)
    for k in range(tiers):
        tk = k / max(1, tiers - 1)
        R = base_r * (1.0 - 0.62 * tk) * narrow
        h = tier_h * (1.0 - 0.28 * tk)
        z0 = first_z + k * step
        if k == tiers - 1:
            h = top_z - z0
        n = max(5, int(round(tips - 3 * tk)))
        tw = rnd.uniform(0, math.tau)
        depth = 0.22
        col = hexmix(dark, light, 0.2 + 0.65 * tk)
        M = 4 * n
        T = [0.0, 0.16, 0.36, 0.58, 0.8]

        def surf(theta, t, R=R, h=h, n=n, tw=tw):
            star = 0.5 + 0.5 * math.cos(n * (theta - tw))
            r = R * (1.0 - t) ** 0.9 * (1.0 - depth * (1.0 - t) * (1.0 - star))
            z = t * h - droop * (1.0 - t) ** 2 * star
            return r, z

        def prof(j, kk, surf=surf, M=M, T=T, z0=z0):
            th = math.tau * j / M
            r, z = surf(th, T[kk])
            return (r * math.cos(th), r * math.sin(th), z0 + z)

        mt = flat(col, 0.85)
        L.revolve('tier%d' % k, prof, M, len(T), mat=mt, top=(0, 0, z0 + h),
                  bottom=(0, 0, z0 + 0.22 * h))
        f = min(0.93, snow_f)
        if f <= 0.02:
            continue
        M2 = 6 * n
        ph = [rnd.uniform(0, math.tau) for _ in range(3)]
        cut = []
        for j in range(M2):
            th = math.tau * j / M2
            star = 0.5 + 0.5 * math.cos(n * (th - tw))
            c = 1.0 - f + 0.06 * (1 - star) - 0.04 * math.sin(2 * th + ph[0]) - 0.03 * math.sin(5 * th + ph[1])
            if rnd.random() < 0.2:
                c -= rnd.uniform(0.03, 0.07)
            cut.append(max(0.03, min(0.9, c)))
        S = [-0.02, 0.0, 0.25, 0.5, 0.75, 0.9]

        def sprof(j, kk, surf=surf, M2=M2, cut=cut, S=S, z0=z0):
            th = math.tau * j / M2
            c = cut[j]
            if kk == 0:
                r, z = surf(th, c)
                r = r * 0.97 + 0.01
                z -= 0.04
            else:
                t = c + (0.97 - c) * S[kk]
                r, z = surf(th, t)
                r += 0.04 + 0.035 * (1 - S[kk])
                z += 0.04
            return (r * math.cos(th), r * math.sin(th), z0 + z)

        L.revolve('snow%d' % k, sprof, M2, len(S), mat=snow_m, top=(0, 0, z0 + h + 0.05),
                  bottom=(0, 0, z0 + (1 - f) * h * 0.9))
    if base_snow:
        for i, (x, y, r) in enumerate([(0.45, -0.35, 0.32), (-0.35, -0.45, 0.26), (0.55, 0.3, 0.24)]):
            blob('basesnow', r, (x, y, 0.0), flat('snow_mat', 0.9), scale=(1.3, 1.1, 0.45), seed=seed + i,
                 amp=0.25, freq=2.0, subdiv=3)


def fish_model(name='fish', length=0.86, height=0.42, thick=0.2, cooked=False, loc=(0, 0, 0), rot=(0, 0, 0),
               scale=1.0):
    """Chubby cartoon fish lying on its side (flank up).  Local X = head(+X)->tail axis,
    local +Y = dorsal side.  Origin at body centre."""
    objs = []
    nb = L.NB(name + '_mat', rough=0.35 if not cooked else 0.55)
    tc = nb.n('ShaderNodeTexCoord')
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['Object'], sep.inputs[0])
    if not cooked:
        f1 = nb.map_range(sep.outputs['Y'], -0.16, 0.0)
        col = nb.mix_rgb(f1, C('#EEF3F8'), C('#9DBBDD'))
        f2 = nb.map_range(sep.outputs['Y'], 0.02, 0.15)
        col = nb.mix_rgb(f2, col, C('#3E6EA6'))
        # warm lateral stripe (trout-like) for colour + readability
        st = nb.math('ABSOLUTE', nb.math('SUBTRACT', sep.outputs['Y'], 0.005))
        st = nb.map_range(st, 0.045, 0.02)
        col = nb.mix_rgb(nb.math('MULTIPLY', st, 0.75), col, C('#F29A7A'))
    else:
        f1 = nb.map_range(sep.outputs['Y'], -0.15, 0.12)
        col = nb.mix_rgb(f1, C('#F0B868'), C('#B9652A'))
        v = nb.math('ADD', sep.outputs['X'], nb.math('MULTIPLY', sep.outputs['Y'], 0.6))
        v = nb.math('FRACT', nb.math('MULTIPLY', v, 6.0))
        g = nb.map_range(v, 0.12, 0.2)
        col = nb.mix_rgb(g, C('grill_mark'), col)
    nb.base(col)
    body_m = nb.m
    bm = L.bmesh.new()
    L.bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=16, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        taper = 1.0 + 0.18 * x
        v.co = Vector((x * length * 0.36, y * height * 0.5 * taper, z * thick * 0.5 * (0.9 + 0.12 * x)))
    body = L.finish(name + '_body', bm, [body_m], scale=(scale,) * 3)
    objs.append(body)
    fin_m = flat('#5C86BD', 0.45) if not cooked else flat('#9A5226', 0.6)
    tl = length * 0.36
    tail = extrude(name + '_tail', [(0.0, 0.0), (-0.22, -0.18), (-0.16, 0.0), (-0.22, 0.18)],
                   thick * 0.45, top=fin_m, side=fin_m, bevel=0.025)
    tail.location = (-tl * 0.85 * scale, 0, -thick * 0.22 * scale)
    tail.scale = (scale,) * 3
    objs.append(tail)
    dors = extrude(name + '_dorsal', [(-0.14, 0.0), (0.1, 0.0), (0.0, 0.1), (-0.12, 0.08)],
                   thick * 0.35, top=fin_m, side=fin_m, bevel=0.02)
    dors.location = (-0.02 * scale, height * 0.42 * scale, -thick * 0.17 * scale)
    dors.scale = (scale,) * 3
    objs.append(dors)
    eye_w = flat('#FFFFFF', 0.3)
    eye_b = flat('#1E2430', 0.2)
    ex, ey = tl * 0.6, height * 0.06
    objs.append(sphere(name + '_eye', 0.06, (ex * scale, ey * scale, thick * 0.33 * scale), eye_w,
                       scale=(scale, scale, scale * 0.4), segs=16, rings=10))
    objs.append(sphere(name + '_pupil', 0.042, (ex * scale * 1.02, ey * scale, thick * 0.37 * scale), eye_b,
                       scale=(scale, scale, scale * 0.4), segs=12, rings=8))
    gill = L.smooth_tube(name + '_gill', [(tl * 0.38 * scale, -height * 0.25 * scale, thick * 0.3 * scale),
                                          (tl * 0.32 * scale, 0, thick * 0.44 * scale),
                                          (tl * 0.38 * scale, height * 0.25 * scale, thick * 0.3 * scale)],
                         0.013 * scale, flat('#3E5A80' if not cooked else '#7A3A18', 0.5))
    objs.append(gill)
    return L.group(objs, name, loc=loc, rot=rot)


def salmon_top_mat(cooked=True):
    key = 'salmon_top%d' % cooked
    if key in L._CUSTOM:
        return L._CUSTOM[key]
    nb = L.NB(key, rough=0.45)
    tc = nb.n('ShaderNodeTexCoord')
    flesh = '#F58A4E' if cooked else '#F6935E'
    fat = '#FFE6D2'
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['Object'], sep.inputs[0])
    comb = nb.n('ShaderNodeCombineXYZ')
    nb.link(sep.outputs['X'], comb.inputs['X'])
    nb.link(nb.math('ADD', sep.outputs['Y'], 0.06), comb.inputs['Y'])
    wv = nb.n('ShaderNodeTexWave', wave_type='RINGS', rings_direction='Z')
    wv.inputs['Scale'].default_value = 2.2
    wv.inputs['Distortion'].default_value = 0.4
    nb.link(comb.outputs[0], wv.inputs['Vector'])
    f = nb.map_range(wv.outputs['Fac'], 0.84, 0.94)
    col = nb.mix_rgb(f, C(flesh), C(fat))
    if cooked:
        v = nb.math('SUBTRACT', sep.outputs['X'], sep.outputs['Y'])
        v = nb.math('FRACT', nb.math('MULTIPLY', v, 3.6))
        g = nb.map_range(v, 0.08, 0.16)
        col = nb.mix_rgb(g, C('#8A3E1C'), col)
    nb.base(col)
    L._CUSTOM[key] = nb.m
    return nb.m


def steak_model(name='steak', R=0.37, thick=0.17, cooked=True, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    """Salmon steak (horseshoe outline, notch toward local +Y) like the reference tower."""
    pts = []
    a0, a1 = math.radians(90 + 24), math.radians(90 - 24 + 360)
    N = 30
    for i in range(N + 1):
        a = a0 + (a1 - a0) * i / N
        rr = R * (1.0 + 0.05 * math.cos(2 * a))
        pts.append((rr * math.cos(a), rr * 0.94 * math.sin(a)))
    pts += [(0.08, 0.21), (0.03, 0.065), (-0.03, 0.065), (-0.08, 0.21)]
    if cooked:
        # seared golden-brown rim with a lighter band -> a stack reads warm, like grilled salmon
        key = 'steak_rim'
        if key not in L._CUSTOM:
            nb = L.NB(key, rough=0.5)
            tc = nb.n('ShaderNodeTexCoord')
            sep = nb.n('ShaderNodeSeparateXYZ')
            nb.link(tc.outputs['Generated'], sep.inputs[0])       # 0..1 over the bbox -> any scale
            f = nb.map_range(sep.outputs['Z'], 0.35, 0.75)
            nb.base(nb.mix_rgb(f, C('#C9733C'), C('#F0A866')))
            L._CUSTOM[key] = nb.m
        skin = L._CUSTOM[key]
    else:
        skin = flat('#C3D0DE', 0.4)
    return extrude(name, [(x * scale, y * scale) for x, y in pts], thick * scale, loc=loc, rot=rot,
                   top=salmon_top_mat(cooked), side=skin, bottom=skin, bevel=0.035 * scale, segs=3, angle=40)


def bread_model(name='bread', L_=0.64, W=0.38, H=0.25, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    key = 'bread_mat'
    if key not in L._CUSTOM:
        nb = L.NB('bread', rough=0.6)
        geo = nb.n('ShaderNodeNewGeometry')
        sep = nb.n('ShaderNodeSeparateXYZ')
        nb.link(geo.outputs['Normal'], sep.inputs[0])
        f = nb.map_range(sep.outputs['Z'], 0.1, 0.9)
        nb.base(nb.mix_rgb(f, C('#E6AE68'), C('#B86A28')))
        L._CUSTOM[key] = nb.m
    m = L._CUSTOM[key]
    bm = L.bmesh.new()
    L.bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=16, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        z2 = z if z > 0 else z * 0.2
        v.co = Vector((x * L_ / 2, y * W / 2 * (1 - 0.1 * x * x), (z2 + 0.2) / 1.2 * H * (1 - 0.15 * x * x)))
    body = L.finish(name, bm, [m], scale=(scale,) * 3)
    objs = [body]
    cut = flat('#E8B878', 0.8)
    for i, x in enumerate((-0.17, 0.0, 0.17)):
        s = box(name + '_score%d' % i, (0.045, W * 0.55, 0.03), (x * scale, 0, (H - 0.02) * scale),
                rot=(0, 0, 35), mat=cut, bevel=0.014, origin='center')
        s.scale = (scale,) * 3
        objs.append(s)
    return L.group(objs, name, loc=loc, rot=rot)


def meat_model(name='meat', cooked=False, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    """Cartoon ham/drumstick lying flat: meat lump (+X) with a bone (-X)."""
    key = 'meat%d' % cooked
    if key not in L._CUSTOM:
        nb = L.NB(key, rough=0.45 if cooked else 0.5)
        if cooked:
            geo = nb.n('ShaderNodeNewGeometry')
            sep = nb.n('ShaderNodeSeparateXYZ')
            nb.link(geo.outputs['Normal'], sep.inputs[0])
            f = nb.map_range(sep.outputs['Z'], 0.2, 0.9)
            col = nb.mix_rgb(f, C('#B8642E'), C('#8E3F1C'))
            tc = nb.n('ShaderNodeTexCoord')
            s2 = nb.n('ShaderNodeSeparateXYZ')
            nb.link(tc.outputs['Object'], s2.inputs[0])
            v = nb.math('FRACT', nb.math('MULTIPLY', nb.math('ADD', s2.outputs['X'], s2.outputs['Y']), 5.0))
            col = nb.mix_rgb(nb.map_range(v, 0.1, 0.17), C('#4E220E'), col)
        else:
            nz = nb.noise(7.0, 2.0)
            v = nb.math('ABSOLUTE', nb.math('SUBTRACT', nz, 0.5))
            marb = nb.map_range(v, 0.03, 0.01)
            col = nb.mix_rgb(marb, C('#D24A3F'), C('#F6D2CB'))
            geo = nb.n('ShaderNodeNewGeometry')
            sep = nb.n('ShaderNodeSeparateXYZ')
            nb.link(geo.outputs['Normal'], sep.inputs[0])
            col = nb.mix_rgb(nb.map_range(sep.outputs['Z'], 0.3, -0.3), col, C('#A8322B'))
        nb.base(col)
        L._CUSTOM[key] = nb.m
    m = L._CUSTOM[key]
    bm = L.bmesh.new()
    L.bmesh.ops.create_uvsphere(bm, u_segments=26, v_segments=14, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        k = 1.0 + 0.22 * x                       # fatter toward +X
        zz = z if z > 0 else z * 0.6
        v.co = Vector((x * 0.27 + 0.04, y * 0.2 * k, (zz + 0.6) / 1.6 * 0.2 * (0.85 + 0.25 * k)))
    meat = L.finish(name + '_lump', bm, [m])
    bone_m = flat('bone', 0.5)
    b1 = cyl(name + '_bone', 0.045, 0.28, (-0.32, 0, 0.1), rot=(0, 90, 0), mat=bone_m, segs=12, origin='center')
    k1 = sphere(name + '_k1', 0.055, (-0.47, 0.045, 0.1), bone_m, segs=12, rings=8)
    k2 = sphere(name + '_k2', 0.055, (-0.47, -0.045, 0.1), bone_m, segs=12, rings=8)
    objs = [meat, b1, k1, k2]
    for o in objs:
        o.location = Vector(o.location) * scale
        o.scale = (scale,) * 3
    return L.group(objs, name, loc=loc, rot=rot)


def crate_model(name='crate', s=0.8, loc=(0, 0, 0), rot=(0, 0, 0), snow=True, seed=0):
    objs = []
    inner = flat('wood_mid', 0.8)
    frame = flat('#D9A066', 0.8)
    objs.append(box(name + '_core', (s - 0.08, s - 0.08, s - 0.08), (0, 0, 0.04), mat=tonal('#B97C48', 0.1, 3.0),
                    bevel=0.02))
    t = 0.09
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(box(name + '_e', (t, t, s), (sx * (s - t) / 2, sy * (s - t) / 2, 0), mat=frame, bevel=0.02))
        for z in (0, s - t):
            objs.append(box(name + '_e', (t, s, t), (sx * (s - t) / 2, 0, z), mat=frame, bevel=0.02))
            objs.append(box(name + '_e', (s, t, t), (0, sx * (s - t) / 2, z), mat=frame, bevel=0.02))
    # diagonal braces on the two visible faces
    ln = math.hypot(s - 2 * t, s - 2 * t) * 0.98
    objs.append(box(name + '_d', (0.075, 0.05, ln), (0, -s / 2 + 0.03, s / 2), rot=(0, 45, 0), mat=inner, bevel=0.015,
                    origin='center'))
    objs.append(box(name + '_d', (0.05, 0.075, ln), (s / 2 - 0.03, 0, s / 2), rot=(-45, 0, 0), mat=inner, bevel=0.015,
                    origin='center'))
    if snow:
        objs.append(L.snow_slab(name + '_snow', s - 0.06, s - 0.06, 0.07, (0, 0, s - 0.01), seed=seed))
    return L.group(objs, name, loc=loc, rot=rot)


def barrel_model(name='barrel', r=0.34, h=0.85, loc=(0, 0, 0), snow=True, seed=0, scale=1.0):
    objs = []
    staves = L.stripes('#C08048', '#A86B3A', 7.0, 'X', rough=0.8, soft=0.08)

    def prof(j, k):
        M = 28
        th = math.tau * j / M
        zs = [0.0, 0.02, 0.25, 0.5, 0.75, 0.98, 1.0]
        z = zs[k] * h
        bulge = 1.0 + 0.16 * math.sin(math.pi * zs[k])
        rr = r * bulge * (0.92 if k in (0, 6) else 1.0)
        return (rr * math.cos(th), rr * math.sin(th), z)

    body = revolve(name + '_body', prof, 28, 7, mat=staves, top=(0, 0, h), bottom=(0, 0, 0))
    # lid colour on top faces
    body.data.materials.append(flat('#C9925A', 0.8))
    for p in body.data.polygons:
        if p.normal.z > 0.95:
            p.material_index = 1
    objs.append(body)
    hoop = flat('iron', 0.45, 0.6)
    for zf in (0.16, 0.84):
        z = zf * h
        rr = r * (1.0 + 0.16 * math.sin(math.pi * zf)) + 0.012
        objs.append(cyl(name + '_hoop', rr, 0.05, (0, 0, z - 0.025), mat=hoop, segs=28, bevel=0.01))
    if snow:
        objs.append(snow_cap(name + '_snow', r * 0.82, (0, 0, h - 0.01), 0.08, seed))
    for o in objs:
        o.location = Vector(o.location) * scale
        o.scale = (scale,) * 3
    return L.group(objs, name, loc=loc)


def log_pile(name, n_bottom=4, r=0.14, length=0.9, loc=(0, 0, 0), rot=(0, 0, 0), seed=0, snow=True, axis='X'):
    """Pyramid of logs lying along X (end grain faces +X / screen lower-right)."""
    rnd = L.rng(seed)
    objs = []
    rows = n_bottom
    endm = L.end_grain()
    for row in range(rows):
        n = n_bottom - row
        for i in range(n):
            y = (i - (n - 1) / 2) * 2 * r * 1.02
            z = r + row * r * 1.75
            barkc = ['bark', '#7C4D2C', '#6A4026'][rnd.randrange(3)]
            o = log(name + '_l', r * rnd.uniform(0.92, 1.05), length * rnd.uniform(0.94, 1.06),
                    (rnd.uniform(-0.04, 0.04), y, z), rot=(0, 90, 0), bark=tonal(barkc, 0.15, 6.0), end=endm,
                    segs=14)
            objs.append(o)
    if snow:
        top_z = r + (rows - 1) * r * 1.75 + r
        objs.append(snow_cap(name + '_snow', length * 0.45, (0, 0, top_z - 0.04), 0.09, seed,
                             scale=(1.0, 0.6, 1.0)))
    return L.group(objs, name, loc=loc, rot=rot)


def stone_ring(cx, cy, sx, sy, courses=2, h=0.26, seed=3, stone_l=0.42, depth=0.34, z0=0.0,
               cols=('#5F6773', '#535A66', '#6C7380', '#625C5A'), snow_top=True):
    """Rectangular wall of rounded stones (hearths)."""
    rnd = L.rng(seed)
    objs = []
    per = 2 * (sx + sy)
    n = max(4, int(round(per / stone_l)))
    for c in range(courses):
        for i in range(n):
            d = (i + 0.5 * (c % 2)) / n * per
            if d < sx:
                x, y, ang = -sx / 2 + d, -sy / 2, 0
            elif d < sx + sy:
                x, y, ang = sx / 2, -sy / 2 + (d - sx), 90
            elif d < 2 * sx + sy:
                x, y, ang = sx / 2 - (d - sx - sy), sy / 2, 0
            else:
                x, y, ang = -sx / 2, sy / 2 - (d - 2 * sx - sy), 90
            col = cols[rnd.randrange(len(cols))]
            m = snowy(col, lo=0.8, hi=0.95, noise_amt=0.35) if (c == courses - 1 and snow_top) else flat(col, 0.85)
            s = box('stone', (stone_l * rnd.uniform(0.95, 1.12), depth * rnd.uniform(0.9, 1.1), h * rnd.uniform(0.95, 1.12)),
                    (cx + x, cy + y, z0 + c * h * 0.92), rot=(rnd.uniform(-3, 3), rnd.uniform(-3, 3), ang + rnd.uniform(-6, 6)),
                    mat=m, bevel=0.07, segs=3)
            objs.append(s)
    return objs


def round_stone_ring(r, n, seed=0, size=0.17, z=0.0, cols=('#5F6773', '#535A66', '#6C7380')):
    rnd = L.rng(seed)
    out = []
    for i in range(n):
        a = math.tau * i / n + rnd.uniform(-0.1, 0.1)
        out.append(blob('rs', size * rnd.uniform(0.85, 1.15), (r * math.cos(a), r * math.sin(a), z + size * 0.45),
                        snowy(cols[i % len(cols)], lo=0.6, hi=0.85), scale=(1.15, 1.0, 0.75), seed=seed * 31 + i,
                        amp=0.18, subdiv=2, flat_bottom=0.5))
    return out


def awning(sx, sy, z_back, z_front, y_back, y_front, c1='red', c2='cream', stripes_n=8, thick=0.07,
           flaps=True, snow=True, name='awning', x=0.0):
    """Striped sloped awning from back (y_back, z_back) to front (y_front, z_front),
    plus a scalloped valance and a soft snow layer on top."""
    objs = []
    dy, dz = y_front - y_back, z_front - z_back
    length = math.hypot(dy, dz)
    ang = math.degrees(math.atan2(dz, dy))
    period = stripes_n / 2.0 / sx
    mt = L.stripes(c1, c2, period, 'X', rough=0.8, soft=0.01)
    a = box(name, (sx, length, thick), (x, (y_back + y_front) / 2, (z_back + z_front) / 2), rot=(ang, 0, 0),
            mat=mt, bevel=0.03, origin='center')
    objs.append(a)
    if flaps:
        w = sx / stripes_n
        for i in range(stripes_n):
            xx = x - sx / 2 + w * (i + 0.5)
            pts = [(-(w / 2 - 0.005) * math.cos(t), -(w * 0.55) * math.sin(t))
                   for t in [math.pi * k / 10 for k in range(0, 11)]]
            col = c1 if i % 2 == 0 else c2
            f = extrude(name + '_flap', pts[::-1], 0.05, top=flat(col, 0.8), side=flat(col, 0.8), bevel=0.012)
            f.rotation_euler = (math.radians(90), 0, 0)
            f.location = (xx, y_front + 0.025, z_front - 0.02)
            objs.append(f)
    if snow:
        n = Vector((0.0, -math.sin(math.radians(ang)), math.cos(math.radians(ang))))
        mid = Vector((x, (y_back + y_front) / 2, (z_back + z_front) / 2))
        objs.append(L.snow_slab(name + '_snow', sx - 0.1, length - 0.12, 0.07, tuple(mid + n * (thick / 2 - 0.01)),
                                rot=(ang, 0, 0), seed=3))
    return objs


def lantern(name, loc, size=0.18, strength=4.0, light=True):
    lm = L.emissive(name + '_glass', '#FFC46A', '#FFB347', strength)
    iron = flat('iron', 0.5, 0.6)
    x, y, z = loc
    box(name + '_base', (size * 1.2, size * 1.2, 0.04), (x, y, z), mat=iron, bevel=0.012)
    box(name + '_glass', (size, size, size * 1.3), (x, y, z + 0.04), mat=lm, bevel=0.02)
    box(name + '_cap', (size * 1.3, size * 1.3, 0.06), (x, y, z + 0.04 + size * 1.3), mat=iron, bevel=0.02, taper=(0.6, 0.6))
    if light:
        L.point_light(name + '_light', (x + 0.15, y - 0.15, z + size * 0.7), 'window', 6.0, 0.05)
    return lm


# =========================================================================== NATURE

@asset('tree_pine_a', 'prop', 'props_nature', fp=('r', 0.45),
       notes='Choppable pine (~3.2 m). Footprint = trunk area; the canopy may overlap sprites behind it.')
def b_tree_pine_a():
    pine(seed=11, tiers=4, base_r=1.05, top_z=3.2, tier_h=1.25, first_z=0.6, snow_f=0.66, tips=9)


@asset('tree_pine_b', 'prop', 'props_nature', fp=('r', 0.42),
       notes='Taller slimmer pine variant (~3.9 m), lighter snow.')
def b_tree_pine_b():
    pine(seed=23, tiers=5, base_r=0.92, top_z=3.9, tier_h=1.15, first_z=0.6, snow_f=0.5, tips=8,
         light='#3A7A58', dark='#1F4D3A')


@asset('tree_pine_snow', 'prop', 'props_nature', fp=('r', 0.45),
       notes='Heavily snow-laden pine (~3.3 m).')
def b_tree_pine_snow():
    pine(seed=37, tiers=4, base_r=1.1, top_z=3.3, tier_h=1.25, first_z=0.6, snow_f=0.88, tips=9,
         light='#2C6A50', dark='#1F4D3A', base_snow=True)


@asset('tree_stump', 'prop', 'props_nature', fp=('r', 0.4),
       notes='Chopped pine stump (shown while the tree regrows).')
def b_tree_stump():
    rnd = L.rng(4)
    bark = tonal('bark', 0.18, 6.0, rough=0.9)
    cyl('stump', 0.34, 0.42, mat=bark, r_top=0.31, segs=20, bevel=0.035, cap_mat=L.end_grain(scale=12.0))
    mb = L.MB()
    for i in range(5):
        a = math.radians(i * 72 + rnd.uniform(-15, 15))
        mb.seg((0.24 * math.cos(a), 0.24 * math.sin(a), 0.2), (0.55 * math.cos(a), 0.55 * math.sin(a), 0.02),
               0.11, bark, segs=10, r2=0.045)
    mb.done('roots')
    chip = flat('end_grain', 0.8)
    for i in range(6):
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(0.5, 0.8)
        box('chip', (0.1, 0.06, 0.03), (d * math.cos(a), d * math.sin(a), 0), rot=(0, 0, rnd.uniform(0, 180)),
            mat=chip, bevel=0.01)
    snow_cap('snow', 0.1, (-0.17, 0.16, 0.41), 0.05, 2, scale=(1.3, 0.9, 1.0))
    blob('basesnow', 0.3, (-0.42, 0.25, 0), flat('snow_mat', 0.9), scale=(1.3, 1.0, 0.35), seed=5, amp=0.2)


def ore_rock(name, r, loc, scale, seed, n_ore, ore_size=0.12):
    rnd = L.rng(seed)
    amp, freq = 0.22, 1.3
    blob(name, r, loc, ore_mat(), scale=scale, seed=seed, amp=amp, freq=freq, subdiv=4, flat_bottom=0.45)
    nug = ore_nugget_mat()
    placed = 0
    tries = 0
    while placed < n_ore and tries < 500:
        tries += 1
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 1)))
        if d.length < 0.2:
            continue
        d.normalize()
        if d.dot(CAM_DIR.normalized()) < 0.25 or d.z < -0.1:
            continue
        p = L.blob_surface(d, r, seed, amp, freq)
        p = Vector((p.x * scale[0], p.y * scale[1], max(p.z, -0.45 * r) * scale[2])) + Vector(loc)
        if p.z < 0.12:
            continue
        s = ore_size * rnd.uniform(0.75, 1.25)
        blob('nug', s, tuple(p - d * s * 0.35), nug, scale=(1.0, 1.0, 0.8), seed=seed * 13 + placed, amp=0.3,
             subdiv=1, facet=True, rot=(rnd.uniform(0, 90), rnd.uniform(0, 90), rnd.uniform(0, 90)))
        placed += 1


@asset('rock_ore', 'prop', 'props_nature', fp=(1.6, 1.4),
       notes='Mineable boulder with orange ore veins + nuggets.')
def b_rock_ore():
    ore_rock('rock', 0.72, (0, 0, 0.32), (1.12, 1.0, 0.92), 3, 9)
    ore_rock('rock2', 0.32, (0.62, -0.55, 0.14), (1.1, 1.0, 0.85), 8, 2, 0.09)


@asset('rock_ore_b', 'prop', 'props_nature', fp=(1.7, 1.5),
       notes='Mineable boulder variant (two-lobed, more ore).')
def b_rock_ore_b():
    ore_rock('rock', 0.6, (-0.22, 0.18, 0.27), (1.1, 1.0, 1.0), 17, 6)
    ore_rock('rock2', 0.48, (0.38, -0.28, 0.2), (1.1, 1.0, 0.85), 21, 5)


@asset('rock_rubble', 'prop', 'props_nature', fp=(1.3, 1.1),
       notes='Depleted ore rock (shown while it respawns).')
def b_rock_rubble():
    rnd = L.rng(9)
    pts = [(0, 0, 0.26), (0.38, -0.2, 0.18), (-0.36, 0.18, 0.2), (-0.15, -0.38, 0.15), (0.3, 0.3, 0.16),
           (-0.48, -0.15, 0.12), (0.52, 0.12, 0.11)]
    for i, (x, y, r) in enumerate(pts):
        blob('rub', r, (x, y, r * 0.35), snowy(['#535A66', '#5F6773', '#625C5A'][i % 3], lo=0.85, hi=0.95),
             scale=(1.15, 1.0, 0.7), seed=40 + i, amp=0.28, freq=1.8, subdiv=2, flat_bottom=0.5,
             facet=False)
    nug = ore_nugget_mat()
    for i, (x, y) in enumerate([(0.12, -0.12), (-0.2, -0.2), (0.25, 0.05)]):
        blob('nug', 0.06, (x, y, 0.2 + 0.05 * i), nug, seed=60 + i, amp=0.3, subdiv=1, facet=True)


def crop_plot(stage):
    rnd = L.rng(100 + stage)
    S = 1.5
    soil = tonal('#7A5038', 0.18, 5.0, rough=0.95)
    box('bed', (S - 0.1, S - 0.1, 0.14), mat=tonal('soil_dark', 0.12, 4.0, rough=0.95), bevel=0.04)
    fm = [flat('wood_mid', 0.8), flat('#B57A47', 0.8)]
    for sgn in (-1, 1):
        box('frame', (S, 0.1, 0.22), (0, sgn * (S / 2 - 0.05), 0), mat=fm[0], bevel=0.03)
        box('frame', (0.1, S - 0.2, 0.22), (sgn * (S / 2 - 0.05), 0, 0), mat=fm[1], bevel=0.03)
    rows = [-0.45, -0.15, 0.15, 0.45]
    for y in rows:
        cyl('ridge', 0.13, S - 0.26, (0, y, 0.13), rot=(0, 90, 0), mat=soil, segs=16, origin='center',
            scale=(0.5, 1.0, 1.0), bevel=0.04)
    if stage == 0:
        # a few clods + tiny snow specks
        for i in range(8):
            blob('clod', 0.035, (rnd.uniform(-0.6, 0.6), rnd.choice(rows) + rnd.uniform(-0.04, 0.04), 0.2), soil,
                 seed=i, amp=0.3, subdiv=1)
        return
    mb = L.MB()
    sprout = flat('#7CC35E', 0.6)
    green = flat('#58A04A', 0.6)
    green2 = flat('#4B8E40', 0.6)
    straw = flat('#D9B04E', 0.6)
    ear = flat('#E9BE4C', 0.55)
    ear2 = flat('#DDA93C', 0.55)
    for y in rows:
        for i in range(6):
            x = -0.56 + i * 0.224 + rnd.uniform(-0.03, 0.03)
            base = Vector((x, y + rnd.uniform(-0.03, 0.03), 0.18))
            if stage == 1:
                for k in range(3):
                    a = rnd.uniform(0, 360)
                    mb.sphere(0.05, sprout, loc=base + Vector((0, 0, 0.04)), rot=(55, 0, a),
                              scale=(0.45, 0.22, 1.25), segs=8, rings=5)
            elif stage == 2:
                for k in range(5):
                    a = math.radians(rnd.uniform(0, 360))
                    lean = rnd.uniform(0.02, 0.09)
                    h = rnd.uniform(0.42, 0.55)
                    tip = base + Vector((lean * math.cos(a), lean * math.sin(a), h))
                    mb.seg(base, tip, 0.016, green if k % 2 else green2, segs=5, r2=0.008)
                for k in range(3):
                    a = rnd.uniform(0, 360)
                    mb.sphere(0.06, green, loc=base + Vector((0, 0, 0.12)), rot=(60, 0, a), scale=(0.35, 0.18, 2.0),
                              segs=8, rings=5)
            else:
                for k in range(6):
                    a = math.radians(rnd.uniform(0, 360))
                    lean = rnd.uniform(0.04, 0.13)
                    h = rnd.uniform(0.68, 0.84)
                    d = Vector((lean * math.cos(a), lean * math.sin(a), h))
                    tip = base + d
                    mb.seg(base, tip, 0.015, straw, segs=5, r2=0.01)
                    dn = d.normalized()
                    ec = tip + dn * 0.07
                    rot = Vector((0, 0, 1)).rotation_difference(dn).to_euler()
                    mb.sphere(0.04, ear if k % 2 else ear2, loc=ec, rot=tuple(math.degrees(v) for v in rot),
                              scale=(1.0, 1.0, 2.6), segs=8, rings=6)
    mb.done('plants')


for _st, _desc in enumerate(['bare tilled soil', 'sprouts', 'green young wheat', 'golden ripe wheat (harvestable)']):
    def _mk(st=_st):
        def fn():
            crop_plot(st)
        return fn
    asset('crop_wheat_%d' % _st, 'prop', 'props_nature', fp=(1.5, 1.5),
          notes='1.5 m wheat plot, stage %d: %s. Plots can be placed edge to edge (1.5 m grid).' % (_st, _desc))(_mk())


@asset('bush_snow', 'decor', 'props_nature', fp=('r', 0.55), notes='Snowy bush with red berries.')
def b_bush_snow():
    rnd = L.rng(12)
    m = snowy('#3E7F55', lo=0.72, hi=0.88, noise_amt=0.45)
    parts = [((0, 0, 0.38), 0.42), ((0.36, -0.12, 0.26), 0.3), ((-0.34, 0.1, 0.26), 0.3), ((0.05, 0.32, 0.3), 0.3),
             ((-0.1, -0.3, 0.22), 0.26)]
    for i, (p, r) in enumerate(parts):
        blob('bush', r, p, m, seed=70 + i, amp=0.2, freq=2.2, subdiv=3, flat_bottom=0.6)
    berry = flat('berry', 0.3)
    for i in range(9):
        d = Vector((rnd.uniform(0.2, 1), rnd.uniform(-1, -0.2), rnd.uniform(-0.1, 0.5))).normalized()
        p = Vector((0, 0, 0.32)) + d * 0.45
        sphere('berry', 0.045, tuple(p), berry, segs=10, rings=6)


@asset('snow_pile_a', 'decor', 'props_nature', fp=(1.8, 1.3), notes='Large snow pile.')
def b_snow_pile_a():
    m = snowy('#D3DFEE', snow='snow_mat', lo=0.15, hi=0.75, noise_amt=0.2)
    blob('p1', 0.62, (0, 0, 0.05), m, scale=(1.3, 1.05, 0.62), seed=81, amp=0.18, freq=1.8, subdiv=4, flat_bottom=0.1)
    blob('p2', 0.42, (0.62, 0.32, 0.02), m, scale=(1.1, 1.0, 0.6), seed=82, amp=0.2, freq=2.0, subdiv=3,
         flat_bottom=0.1)
    blob('p3', 0.36, (-0.58, -0.32, 0.0), m, scale=(1.1, 1.0, 0.55), seed=83, amp=0.2, freq=2.0, subdiv=3,
         flat_bottom=0.1)


@asset('snow_pile_b', 'decor', 'props_nature', fp=(1.2, 1.0), notes='Small snow pile with snowballs.')
def b_snow_pile_b():
    m = snowy('#D3DFEE', snow='snow_mat', lo=0.15, hi=0.75, noise_amt=0.2)
    blob('p1', 0.45, (0, 0.05, 0.02), m, scale=(1.25, 1.0, 0.6), seed=91, amp=0.2, freq=2.0, subdiv=3, flat_bottom=0.1)
    blob('p2', 0.3, (0.38, -0.2, 0.0), m, scale=(1.1, 1.0, 0.55), seed=92, amp=0.2, freq=2.0, subdiv=3, flat_bottom=0.1)
    for i, (x, y, r) in enumerate([(-0.45, -0.3, 0.12), (-0.22, -0.45, 0.1), (-0.5, -0.05, 0.09)]):
        sphere('ball', r, (x, y, r * 0.9), m, segs=16, rings=10)


@asset('ice_chunk', 'decor', 'props_nature', fp=(1.2, 1.0), notes='Glossy ice block cluster with snow.')
def b_ice_chunk():
    nb = L.NB('ice', rough=0.08)
    nb.p.inputs['Coat Weight'].default_value = 1.0
    nb.p.inputs['Emission Color'].default_value = nb.rgb('#BFE6FF', raw=True)
    nb.p.inputs['Emission Strength'].default_value = 0.18
    geo = nb.n('ShaderNodeNewGeometry')
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.link(geo.outputs['Normal'], sep.inputs[0])
    tone = nb.map_range(nb.noise(2.5, 2.0), 0.3, 0.7)
    col = nb.mix_rgb(tone, C('#7FB4DD'), C('#B9DDF4'))
    col = nb.mix_rgb(nb.map_range(sep.outputs['Z'], 0.82, 0.95), col, C('snow_mat'))
    nb.base(col)
    m = nb.m
    blob('ice1', 0.45, (0, 0.05, 0.3), m, scale=(1.0, 0.85, 1.35), seed=5, amp=0.25, freq=1.2, subdiv=1, facet=True,
         flat_bottom=0.65, rot=(0, 8, 20))
    blob('ice2', 0.3, (0.42, -0.25, 0.16), m, scale=(1.0, 0.9, 1.1), seed=7, amp=0.25, freq=1.2, subdiv=1,
         facet=True, flat_bottom=0.6, rot=(10, 0, 40))
    blob('ice3', 0.2, (-0.38, -0.3, 0.1), m, seed=9, amp=0.3, freq=1.2, subdiv=1, facet=True, flat_bottom=0.6)
    blob('snow', 0.5, (0, -0.05, 0), flat('snow_mat', 0.9), scale=(1.3, 1.1, 0.18), seed=4, amp=0.2, subdiv=3)


# =========================================================================== STATIONS

@asset('station_grill', 'station', 'props_buildings', fp=(2.6, 1.6), work=4, fps=8,
       notes='Fish grill: stone hearth + iron grate with fish. work = embers pulse. Long axis along world X.')
def b_station_grill():
    rnd = L.rng(5)
    sx, sy = 2.3, 1.3
    L.box('pit', (sx - 0.1, sy - 0.1, 0.36), (0, 0, 0), mat=flat('charcoal', 0.95), bevel=0.05)
    stone_ring(0, 0, sx, sy, courses=2, h=0.27, seed=4, stone_l=0.46, depth=0.36)
    ember = L.emissive('ember', '#C9542A', 'fire', 3.0)
    coal = flat('#3A302B', 0.9)
    for i in range(36):
        x = rnd.uniform(-sx / 2 + 0.25, sx / 2 - 0.25)
        y = rnd.uniform(-sy / 2 + 0.25, sy / 2 - 0.25)
        m = ember if rnd.random() < 0.55 else coal
        blob('coal', rnd.uniform(0.07, 0.11), (x, y, 0.38), m, scale=(1, 1, 0.7), seed=i, amp=0.25, subdiv=1,
             facet=True)
    iron = flat('iron', 0.45, 0.7)
    gz = 0.62
    gx, gy = sx - 0.25, sy - 0.25
    for sgn in (-1, 1):
        L.box('grate_rim', (gx, 0.06, 0.05), (0, sgn * gy / 2, gz), mat=iron, bevel=0.015)
        L.box('grate_rim', (0.06, gy, 0.05), (sgn * gx / 2, 0, gz), mat=iron, bevel=0.015)
    nbars = 11
    for i in range(nbars):
        x = -gx / 2 + gx * (i + 0.5) / nbars
        L.cyl('bar', 0.02, gy, (x, 0, gz + 0.03), rot=(90, 0, 0), mat=iron, segs=8, bevel=0.0, origin='center')
    food = [fish_model('gfish1', cooked=True, loc=(-0.6, -0.12, gz + 0.13), rot=(0, 0, 80), scale=0.8),
            fish_model('gfish2', cooked=True, loc=(-0.1, 0.1, gz + 0.13), rot=(0, 0, 100), scale=0.8),
            steak_model('gsteak1', loc=(0.5, -0.18, gz + 0.05), rot=(0, 0, 20), scale=0.72),
            steak_model('gsteak2', loc=(0.62, 0.24, gz + 0.05), rot=(0, 0, -30), scale=0.66)]
    food_z = [o.location.z for o in food]
    for i, x in enumerate((-0.78, -0.26, 0.26, 0.78)):
        box('backstone', (0.5, 0.36, 0.42 + 0.06 * (i % 2)), (x, sy / 2 + 0.02, 0.48), rot=(0, 0, rnd.uniform(-5, 5)),
            mat=snowy(['#5F6773', '#6C7380'][i % 2], lo=0.75, hi=0.9), bevel=0.08)
    # tongs leaning on the right end + a small water bucket
    cyl('bucket', 0.2, 0.3, (sx / 2 + 0.38, 0.35, 0), mat=flat('wood_mid', 0.8), r_top=0.23, segs=18,
        cap_mat=flat('#4F86C2', 0.2))
    glow = L.point_light('pitglow', (0, 0, 0.5), 'fire', 40.0, 0.5)
    # work-loop life: flame tongues licking up through the grate, sizzling food, light smoke
    flames = L.Flames('gflame', [((x, y, 0.36), 0.075, h) for x, y, h in
                                 [(-0.95, 0.18, 0.26), (-0.72, -0.3, 0.3), (-0.35, 0.22, 0.28), (0.0, -0.22, 0.32),
                                  (0.28, 0.3, 0.27), (0.72, -0.02, 0.3), (0.98, 0.32, 0.24)]], lean=0.18)
    smoke = L.Smoke('gsmoke', (-0.3, 0.05, gz + 0.2), n=3, rise=1.0, drift=(0.2, 0.15), r0=0.11, r1=0.3,
                    color='#E6EAF0', alpha=0.72, seed=1, fade_in=0.18)
    hop = [0.0, 0.035, 0.012, 0.0]

    def idle():
        L.set_emission(ember, 1.6)
        glow.data.energy = 30
        flames.show(False)
        smoke.show(False)
        for o, z in zip(food, food_z):
            o.location.z = z

    def work(i):
        s = [3.0, 4.6, 6.2, 4.6][i]
        L.set_emission(ember, s)
        glow.data.energy = 40 + 12 * s
        flames.set(i)
        smoke.set(i)
        for k, (o, z) in enumerate(zip(food, food_z)):
            o.location.z = z + hop[(i + 2 * k) % 4]

    idle()
    return {'work': work, 'idle': idle, 'fx': {'fire': (0, 0, gz), 'smoke': (-0.3, 0.05, gz + 1.0)}}


@asset('station_sawmill', 'station', 'props_buildings', fp=(3.0, 1.4), work=4, fps=10,
       notes='Sawmill: log bench with circular blade (log feeds from the left/up-left, planks out at +X / '
             'screen down-right). work = blade spins (4-frame seamless loop).')
def b_station_sawmill():
    rnd = L.rng(6)
    top_m = tonal('#C98F55', 0.1, 3.0)
    legm = flat('wood_dark', 0.8)
    box('table', (2.8, 1.1, 0.12), (0, 0, 0.68), mat=top_m, bevel=0.04)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            box('leg', (0.15, 0.15, 0.7), (sx_ * 1.22, sy_ * 0.4, 0), mat=legm, bevel=0.03)
        box('brace', (0.1, 0.9, 0.1), (sx_ * 1.22, 0, 0.18), mat=legm, bevel=0.025)
    box('brace', (2.45, 0.08, 0.1), (0, -0.4, 0.22), mat=legm, bevel=0.025)
    # red guard box housing under the blade
    box('housing', (1.0, 0.5, 0.12), (0.25, 0, 0.8), mat=flat('red', 0.6), bevel=0.04)
    # blade assembly
    steel = flat('steel', 0.28, 0.85)
    dark = flat('iron', 0.5, 0.5)
    parts = []
    R = 0.52
    parts.append(cyl('disc', R, 0.035, (0, 0, 0), rot=(90, 0, 0), mat=steel, segs=48, origin='center', bevel=0.008))
    mb = L.MB()
    for k in range(24):
        a = math.tau * k / 24
        p = Vector((math.cos(a) * (R + 0.025), 0, math.sin(a) * (R + 0.025)))
        tdir = Vector((-math.sin(a), 0, math.cos(a)))
        mb.seg(p - Vector((math.cos(a), 0, math.sin(a))) * 0.03 - tdir * 0.02,
               p + Vector((math.cos(a), 0, math.sin(a))) * 0.04 + tdir * 0.02, 0.022, steel, segs=3, r2=0.002)
    parts.append(mb.done('teeth', smooth=False))
    for k in range(4):
        a = math.tau * k / 4 + 0.4
        parts.append(cyl('hole', 0.065, 0.045, (math.cos(a) * R * 0.54, 0, math.sin(a) * R * 0.54), rot=(90, 0, 0),
                         mat=flat('#2A2E36', 0.6), segs=16, origin='center', bevel=0.0))
        parts.append(box('slot', (0.03, 0.04, 0.13), (math.cos(a + 0.8) * R * 0.78, 0, math.sin(a + 0.8) * R * 0.78),
                         rot=(0, -math.degrees(a + 0.8) + 90, 0), mat=flat('#2A2E36', 0.6), bevel=0.0, origin='center'))
    parts.append(cyl('hub', 0.1, 0.08, (0, 0, 0), rot=(90, 0, 0), mat=flat('ui_gold', 0.4, 0.6), segs=20,
                     origin='center', bevel=0.015))
    blade = L.group(parts, 'blade', loc=(0.25, 0, 0.9))
    # log feeding in from the left, planks out on the right
    log('log', 0.17, 1.1, (-0.68, 0.0, 0.8 + 0.17), rot=(0, 90, 0), bark=tonal('#8A5A33', 0.16, 6.0), segs=18)
    for i in range(3):
        box('plank', (0.85, 0.32, 0.07), (1.0 + rnd.uniform(-0.03, 0.03), rnd.uniform(-0.04, 0.04), 0.8 + 0.075 * i),
            rot=(0, 0, rnd.uniform(-5, 5)), mat=flat(['plank', '#E0AA6C', 'wood_light'][i], 0.75), bevel=0.02)
    dust = flat('#EBCB98', 0.95)
    blob('dust', 0.2, (0.12, -0.92, 0.0), dust, scale=(1.4, 1.1, 0.5), seed=3, amp=0.3, subdiv=2)
    blob('dust2', 0.14, (0.35, -0.2, 0.8), dust, scale=(1.4, 1.0, 0.3), seed=4, amp=0.3, subdiv=2)
    # little motor box with belt wheel on the back
    box('motor', (0.55, 0.45, 0.45), (0.3, 0.85, 0), mat=flat('#5C7FA8', 0.5, 0.2), bevel=0.06)
    cyl('pulley', 0.13, 0.08, (0.3, 0.6, 0.32), rot=(90, 0, 0), mat=dark, segs=18, origin='center')
    L.snow_slab('msnow', 0.45, 0.35, 0.06, (0.3, 0.85, 0.44), seed=2)

    # work-loop life: blade spins (4 holes -> 90 deg symmetric, 22.5 deg/frame is seamless) and a
    # stream of sawdust chips sprays toward the camera onto the dust heap
    chips = L.Spray('chip', (-0.1, -0.12, 0.95), (0.15, -0.95, 0.45), flat('#E3B064', 0.9), n=10, grav=1.35,
                    r=0.075, spread=0.14, seed=6)

    def idle():
        blade.rotation_euler.y = 0.0
        chips.show(False)

    def work(i):
        blade.rotation_euler.y = math.radians(-22.5 * i)
        chips.set(i)

    return {'work': work, 'idle': idle, 'fx': {'blade': (0.25, 0, 0.9), 'dust': (0.12, -0.92, 0.1)}}


def voussoir_arch(name, center, psi, w, h, depth=0.2, block=0.16, n=7, mat=None, protrude=0.0):
    """Ring of stone blocks around an arch opening on a vertical plane facing psi."""
    u = Vector((math.cos(math.radians(psi)), math.sin(math.radians(psi)), 0.0))
    nrm = facing_dir(psi)
    r = w / 2.0 + block / 2
    rh = max(0.0, h - w / 2.0)
    out = []
    c = Vector(center)
    for k in range(n):
        t = math.pi * k / (n - 1)
        p = c + u * (r * math.cos(t)) + Vector((0, 0, rh + r * math.sin(t))) + nrm * protrude
        tang = u * (-math.sin(t)) + Vector((0, 0, math.cos(t)))
        rad = u * math.cos(t) + Vector((0, 0, math.sin(t)))
        b = box(name, (block * 1.15, depth, block * 1.25), (0, 0, 0), mat=mat, bevel=0.035, origin='center')
        # local x = tangent, local z = radial ; y = normal
        orient(b, p, tang, rad)
        out.append(b)
    for sgn in (-1, 1):
        for j in range(max(1, int(rh / block))):
            p = c + u * (sgn * r) + Vector((0, 0, block * 0.6 + j * block * 1.05)) + nrm * protrude
            b = box(name, (block * 1.25, depth, block), (0, 0, 0), mat=mat, bevel=0.035, origin='center')
            orient(b, p, u, Vector((0, 0, 1)))
            out.append(b)
    return out


@asset('station_bakery', 'station', 'props_buildings', fp=(2.4, 2.2), work=4, fps=6,
       notes='Bread oven: stone plinth + clay dome; the glowing mouth faces the camera (screen down). '
             'work = mouth glow pulses.')
def b_station_bakery():
    plinth = L.brick('#6C7380', '#5F6773', '#9AA1AB', scale=1.3, row_h=0.5, brick_w=0.55)
    box('plinth', (2.3, 2.1, 0.5), mat=plinth, bevel=0.06)
    clay = snowy('#C8764B', lo=0.62, hi=0.8, noise_amt=0.3)
    Rd, Hd, z0 = 0.98, 1.12, 0.5

    def prof(j, k):
        M = 40
        th = math.tau * j / M
        phis = [0, 12, 26, 40, 54, 68, 80]
        ph = math.radians(phis[k])
        r = Rd * math.cos(ph) * (1.0 + 0.05 * math.sin(2 * ph))
        return (r * math.cos(th), r * math.sin(th), z0 + Hd * math.sin(ph))

    revolve('dome', prof, 40, 7, mat=clay, top=(0, 0, z0 + Hd), bottom=(0, 0, z0))
    psi = 45.0
    fd = facing_dir(psi)
    # entrance vault + glowing opening
    vault = extrude('vault', arch_pts(1.0, 0.95), 0.85, rot=facing_rot(psi), top=clay, side=clay, bevel=0.05)
    vault.location = tuple(Vector((0, 0, z0)) + fd * 0.45)
    glow_m = L.emissive('mouth', '#5A1E10', '#FF8A2A', 3.0)
    mouth = extrude('mouth', arch_pts(0.66, 0.62), 0.02, rot=facing_rot(psi), top=glow_m, side=glow_m, bevel=0.0)
    mouth.location = tuple(Vector((0, 0, z0 + 0.02)) + fd * 1.305)
    voussoir_arch('vous', tuple(Vector((0, 0, z0)) + fd * 1.22), psi, 0.7, 0.66, depth=0.2, block=0.15, n=7,
                  mat=snowy('#E2D6C4', lo=0.7, hi=0.85))
    # chimney at the back
    back = Vector((-0.5, 0.5, 0))
    cyl('chimney', 0.17, 1.0, tuple(back + Vector((0, 0, z0 + 0.75))), mat=L.brick(scale=3.0, row_h=0.4, snow_top=False),
        segs=16, bevel=0.02)
    cyl('chimcap', 0.22, 0.1, tuple(back + Vector((0, 0, z0 + 1.75))), mat=flat('iron', 0.5, 0.4), segs=16)
    cyl('chimhole', 0.14, 0.012, tuple(back + Vector((0, 0, z0 + 1.85))), mat=flat('#241C18', 0.9), segs=16,
        bevel=0.0)
    # firewood stack on the back-right corner, bread on a peel front-left
    log_pile('wood', 3, 0.11, 0.6, (0.72, 0.55, 0.5), rot=(0, 0, 0), seed=3)
    box('peel', (0.5, 0.42, 0.04), (-0.62, -0.62, 0.5), mat=flat('wood_light', 0.8), bevel=0.015, rot=(0, 0, 20))
    cyl('peelh', 0.03, 0.6, (-0.95, -0.5, 0.52), rot=(0, 90, 20), mat=flat('wood_mid', 0.8), origin='center')
    bread_model('b1', loc=(-0.65, -0.68, 0.54), rot=(0, 0, 30), scale=0.6)
    bread_model('b2', loc=(-0.55, -0.48, 0.54), rot=(0, 0, 60), scale=0.55)
    glow = L.point_light('ovenglow', tuple(Vector((0, 0, z0 + 0.4)) + fd * 1.6), 'fire', 30.0, 0.3)
    # work-loop life: flames dancing in the oven mouth + chimney smoke; idle = banked embers
    u = Vector((math.cos(math.radians(psi)), math.sin(math.radians(psi)), 0.0))
    mouth_p = Vector((0, 0, z0 + 0.03)) + fd * 1.35
    flames = L.Flames('oflame', [(tuple(mouth_p + u * o), 0.095, h, psi) for o, h in
                                 ((-0.17, 0.28), (0.0, 0.38), (0.17, 0.3))], lean=0.08, flat_k=0.45)
    chim_top = back + Vector((0, 0, z0 + 1.8))
    smoke = L.Smoke('osmoke', tuple(chim_top), n=3, rise=1.1, drift=(0.25, 0.15), r0=0.12, r1=0.34, alpha=0.88,
                    seed=2)

    def idle():
        L.set_emission(glow_m, 0.45)
        glow.data.energy = 8
        flames.show(False)
        smoke.show(False)

    def work(i):
        s = [1.1, 1.6, 2.2, 1.6][i]
        L.set_emission(glow_m, s)
        glow.data.energy = 14 + 10 * s
        flames.set(i)
        smoke.set(i)

    idle()
    return {'work': work, 'idle': idle,
            'fx': {'fire': tuple(mouth_p + Vector((0, 0, 0.3))), 'smoke': tuple(chim_top + Vector((0, 0, 0.3)))}}


@asset('station_smelter', 'station', 'props_buildings', fp=(2.4, 2.0), work=4, fps=8,
       notes='Smelter: brick furnace (glowing door on the -Y / down-left face) + crucible of molten metal on the '
             '+X side + ingot mould. work = furnace + crucible glow pulse.')
def b_station_smelter():
    rnd = L.rng(7)
    box('base', (2.3, 1.9, 0.22), mat=L.brick('#6C7380', '#5F6773', '#8E96A3', scale=1.4, row_h=0.5, brick_w=0.55,
                                               snow_top=False), bevel=0.05)
    fx, fy = -0.35, 0.15
    bm = L.brick(scale=2.4, row_h=0.42, brick_w=0.5)
    box('furnace', (1.3, 1.3, 1.45), (fx, fy, 0.22), mat=bm, bevel=0.06, taper=(0.8, 0.8))
    box('band', (1.12, 1.12, 0.16), (fx, fy, 1.6), mat=flat('#5E4A44', 0.7), bevel=0.04)
    cyl('stack', 0.24, 0.75, (fx, fy, 1.72), mat=flat('#5A606B', 0.5, 0.4), r_top=0.2, segs=18)
    cyl('stack_rim', 0.25, 0.08, (fx, fy, 2.45), mat=flat('iron', 0.5, 0.5), segs=18)
    cyl('stackhole', 0.15, 0.012, (fx, fy, 2.53), mat=flat('#241C18', 0.9), segs=16, bevel=0.0)
    # snow on the band ledge
    L.snow_slab('ledge', 1.0, 1.0, 0.06, (fx, fy, 1.75), seed=5)
    glow_m = L.emissive('door', '#5A1E10', '#FF7A22', 3.0)
    door = extrude('door', arch_pts(0.55, 0.55), 0.03, rot=facing_rot(0), top=glow_m, side=glow_m, bevel=0.0)
    door.location = (fx, fy - 0.62, 0.36)
    frame = extrude('doorframe', arch_pts(0.75, 0.68), 0.05, rot=facing_rot(0), top=flat('iron', 0.5, 0.5),
                    side=flat('iron', 0.5, 0.5), bevel=0.015)
    frame.location = (fx, fy - 0.6, 0.3)
    # crucible on a stand
    iron = flat('iron', 0.5, 0.5)
    cx, cy = 0.68, -0.3
    for k in range(3):
        a = math.tau * k / 3 + 0.5
        L.MB  # noqa
        cyl('leg', 0.035, 0.4, (cx + 0.24 * math.cos(a), cy + 0.24 * math.sin(a), 0.22), mat=iron, segs=8)
    cyl('ring', 0.33, 0.05, (cx, cy, 0.6), mat=iron, segs=24)
    molten = L.emissive('molten', '#FFB34A', '#FFC24A', 5.0)
    cyl('pot', 0.3, 0.42, (cx, cy, 0.5), mat=flat('#3D424C', 0.45, 0.5), r_top=0.34, segs=28, bevel=0.03,
        cap_mat=molten)
    cyl('metal', 0.315, 0.02, (cx, cy, 0.915), mat=molten, segs=28, bevel=0.0)
    # ingot mould with two ingots
    box('mould', (0.75, 0.38, 0.1), (0.62, 0.55, 0.22), mat=iron, bevel=0.02)
    for i in range(2):
        ingot_model('ing%d' % i, loc=(0.45 + 0.34 * i, 0.55, 0.3), rot=(0, 0, 0), scale=0.5)
    # ore pile at the front-left (input side)
    nug = ore_nugget_mat()
    for i in range(6):
        blob('ore', rnd.uniform(0.1, 0.14), (-0.85 + rnd.uniform(-0.18, 0.18), -0.65 + rnd.uniform(-0.12, 0.12),
                                             0.3 + 0.06 * (i % 3)),
             ore_mat() if i % 2 else nug, seed=200 + i, amp=0.3, subdiv=1, facet=True)
    g1 = L.point_light('doorglow', (fx, fy - 1.1, 0.6), 'fire', 25.0, 0.3)
    g2 = L.point_light('potglow', (cx, cy, 1.2), 'fire_hot', 20.0, 0.2)

    # work-loop life: flames at the furnace door, dark smoke from the stack; idle = cooled glow
    flames = L.Flames('sflame', [((fx + o, fy - 0.66, 0.37), 0.075, h, 0.0) for o, h in
                                 ((-0.13, 0.24), (0.0, 0.32), (0.13, 0.26))], lean=0.06, flat_k=0.45)
    smoke = L.Smoke('ssmoke', (fx, fy, 2.48), n=3, rise=1.1, drift=(0.25, 0.15), r0=0.13, r1=0.36,
                    color='#A7AEB8', alpha=0.9, seed=3)

    def idle():
        L.set_emission(glow_m, 0.6)
        L.set_emission(molten, 1.2)
        g1.data.energy = 8
        g2.data.energy = 8
        flames.show(False)
        smoke.show(False)

    def work(i):
        s = [2.0, 3.0, 4.2, 3.0][i]
        L.set_emission(glow_m, s)
        L.set_emission(molten, s + 1.5)
        g1.data.energy = 15 + 6 * s
        g2.data.energy = 12 + 4 * s
        flames.set(i)
        smoke.set(i)

    idle()
    return {'work': work, 'idle': idle,
            'fx': {'fire': (fx, fy - 0.7, 0.6), 'crucible': (cx, cy, 0.95), 'smoke': (fx, fy, 2.8)}}


def ingot_model(name='ingot', loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    bm = L.bmesh.new()
    L.bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        x, y, z = v.co
        k = 0.78 if z > 0 else 1.0
        v.co = Vector((x * 0.68 * k, y * 0.34 * (0.7 if z > 0 else 1.0), (z + 0.5) * 0.16))
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z > 0.9:
            f.material_index = 1
    side = flat('#7F90A6', 0.3, 0.55)
    top = flat('#C9D5E3', 0.25, 0.45)
    ob = L.finish(name, bm, [side, top], loc=loc, rot=rot, scale=(scale,) * 3, bevel=0.03, segs=3)
    return ob


@asset('station_smokehouse', 'station', 'props_buildings', fp=(2.4, 2.0), work=4, fps=6,
       notes='Smokehouse: plank hut with an open meat rack in front (-Y / down-left) over embers. '
             'work = embers glow pulse.')
def b_station_smokehouse():
    rnd = L.rng(8)
    planks = L.stripes('#8A5A33', '#7A4D2B', 3.2, 'X', rough=0.85, soft=0.03)
    hy = 0.35
    box('hut', (1.9, 1.2, 1.5), (0, hy, 0), mat=planks, bevel=0.04)
    box('hutside', (0.08, 1.2, 1.45), (0.97, hy, 0), mat=L.stripes('#8A5A33', '#7A4D2B', 3.2, 'Y', rough=0.85, soft=0.03),
        bevel=0.02)
    gable = extrude('gable', [(-0.6, 0.0), (0.6, 0.0), (0.0, 0.62)], 0.1, rot=(90, 0, 90),
                    top=flat('#7A4D2B', 0.85), side=flat('#7A4D2B', 0.85), bevel=0.02)
    gable.location = (0.9, hy, 1.5)
    gable2 = extrude('gable2', [(-0.6, 0.0), (0.6, 0.0), (0.0, 0.62)], 0.1, rot=(90, 0, 90),
                     top=flat('#7A4D2B', 0.85), side=flat('#7A4D2B', 0.85), bevel=0.02)
    gable2.location = (-1.0, hy, 1.5)
    roofm = L.stripes('#6B3F2A', '#5A3322', 5.0, 'Y', rough=0.85, soft=0.05)
    roof_panel('roofF', 2.25, hy - 0.85, 1.38, hy, 2.15, 0.08, roofm, seed=1)
    roof_panel('roofB', 2.25, hy + 0.85, 1.38, hy, 2.15, 0.08, roofm, seed=2)
    box('vent', (0.35, 0.35, 0.35), (-0.4, hy, 2.0), mat=flat('#5A3322', 0.85), bevel=0.04)
    box('venthole', (0.22, 0.22, 0.012), (-0.4, hy, 2.35), mat=flat('#241C18', 0.9), bevel=0.0)
    # meat rack in front
    post = flat('wood_mid', 0.8)
    for sx_ in (-1, 1):
        cyl('rpost', 0.07, 1.55, (sx_ * 0.85, -0.75, 0), mat=post, segs=12)
    log('bar', 0.06, 1.95, (0, -0.75, 1.42), rot=(0, 90, 0), bark=post, segs=12)
    string = flat('rope', 0.8)
    hang = []
    for i, x in enumerate((-0.58, -0.2, 0.2, 0.58)):
        cooked = i % 2 == 0
        st = cyl('str', 0.012, 0.3, (0, 0, -0.3), mat=string, segs=6, bevel=0.0)
        mt = meat_model('m%d' % i, cooked=True if cooked else False, loc=(0, 0, -0.27), rot=(0, 90, 90), scale=0.75)
        hang.append(L.group([st, mt], 'hang%d' % i, loc=(x, -0.75, 1.42)))
    # ember pit under the rack
    for o in round_stone_ring(0.42, 9, seed=5, size=0.12):
        o.location.y -= 0.75
    ember = L.emissive('sember', '#C9542A', 'fire', 3.0)
    for i in range(12):
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(0, 0.28)
        blob('em', rnd.uniform(0.06, 0.09), (d * math.cos(a), -0.75 + d * math.sin(a), 0.03), ember if i % 3 else
             flat('charcoal', 0.9), seed=300 + i, amp=0.3, subdiv=1, facet=True)
    # firewood on the side
    log_pile('fw', 3, 0.1, 0.55, (1.25, 0.2, 0), seed=6)
    glow = L.point_light('sglow', (0, -0.95, 0.35), 'fire', 25.0, 0.3)
    # work-loop life: meat sways on its strings, little flames in the pit, smoke from the roof vent
    flames = L.Flames('kflame', [((-0.12, -0.8, 0.04), 0.06, 0.2), ((0.1, -0.68, 0.04), 0.065, 0.24),
                                 ((0.02, -0.9, 0.04), 0.055, 0.17)], lean=0.15)
    smoke = L.Smoke('ksmoke', (-0.4, hy, 2.28), n=3, rise=1.0, drift=(0.25, 0.15), r0=0.11, r1=0.32,
                    color='#E3E7EE', alpha=0.88, seed=4)
    swing = [0.0, 1.0, 0.0, -1.0]

    def idle():
        L.set_emission(ember, 1.0)
        glow.data.energy = 8
        flames.show(False)
        smoke.show(False)
        for h in hang:
            h.rotation_euler = (0.0, 0.0, 0.0)

    def work(i):
        s = [2.6, 4.0, 5.6, 4.0][i]
        L.set_emission(ember, s)
        glow.data.energy = 15 + 6 * s
        flames.set(i)
        smoke.set(i)
        for k, h in enumerate(hang):
            a = swing[(i + k) % 4]
            h.rotation_euler = (math.radians(4.0 * swing[(i + k + 1) % 4]), math.radians(10.0 * a), 0.0)

    idle()
    return {'work': work, 'idle': idle, 'fx': {'fire': (0, -0.75, 0.2), 'smoke': (-0.4, hy, 2.6)}}


# =========================================================================== BUILDINGS

@asset('market_counter', 'building', 'props_buildings', fp=(3.0, 1.3), front='-Y',
       notes='Food stall. Front (customer side) faces screen down-left (world -Y); the seller side is the back '
             '(screen up-right).')
def b_market_counter():
    rnd = L.rng(8)
    W, D, H = 2.9, 1.0, 0.95
    L.box('body', (W - 0.1, D - 0.1, H - 0.05), (0, 0, 0), mat=tonal('wood_dark', 0.12, 3.0), bevel=0.03)
    n = 10
    for i in range(n):
        x = -W / 2 + (i + 0.5) * W / n
        col = ['wood_light', 'plank', 'wood_mid'][i % 3]
        box('plank', (W / n - 0.02, 0.07, H - 0.12), (x, -D / 2 + 0.01, 0.02), mat=flat(col, 0.8), bevel=0.02)
    for sgn in (-1, 1):
        for j in range(3):
            y = -D / 2 + (j + 0.5) * D / 3
            box('splank', (0.07, D / 3 - 0.02, H - 0.12), (sgn * (W / 2 - 0.01), y, 0.02),
                mat=flat(['plank', 'wood_light', 'wood_mid'][j], 0.8), bevel=0.02)
    box('beam', (W + 0.04, 0.09, 0.12), (0, -D / 2 - 0.03, 0.18), mat=flat('wood_dark', 0.8), bevel=0.03)
    box('top', (W + 0.2, D + 0.2, 0.1), (0, 0, H - 0.04), mat=tonal('#D9A66B', 0.08, 2.0), bevel=0.035)
    for sx_ in (-1, 1):
        cyl('post', 0.075, 2.25, (sx_ * (W / 2 + 0.02), -D / 2 - 0.02, 0), mat=flat('wood_mid', 0.8), segs=12)
        cyl('post', 0.075, 2.55, (sx_ * (W / 2 + 0.02), D / 2 + 0.05, 0), mat=flat('wood_mid', 0.8), segs=12)
    awning(W + 0.35, D, 2.62, 2.18, D / 2 + 0.3, -D / 2 - 0.45, 'red', 'cream', 8)
    box('tray', (0.9, 0.62, 0.08), (-0.82, -0.05, H + 0.06), mat=flat('#9C6A3F', 0.8), bevel=0.03)
    for i, (x, y) in enumerate([(-1.05, -0.12), (-0.62, -0.1), (-0.85, 0.12)]):
        steak_model('s%d' % i, loc=(x, y, H + 0.13 + 0.07 * (i == 2)), rot=(0, 0, rnd.uniform(-30, 30)), scale=0.55)
    box('basket', (0.8, 0.55, 0.14), (0.35, 0.0, H + 0.06), mat=flat('straw', 0.9), bevel=0.05)
    for i, (x, y) in enumerate([(0.18, -0.08), (0.52, 0.02), (0.33, 0.12)]):
        bread_model('b%d' % i, loc=(x, y, H + 0.2), rot=(0, 0, 30 + 40 * i), scale=0.62)
    box('crate', (0.5, 0.5, 0.2), (1.05, 0.05, H + 0.06), mat=flat('wood_light', 0.8), bevel=0.03)
    fish_model('cf1', loc=(1.05, 0.0, H + 0.3), rot=(0, 0, 45), scale=0.5)
    fish_model('cf2', loc=(1.08, 0.12, H + 0.35), rot=(0, 0, 25), scale=0.5)
    L.cyl('hook', 0.015, 0.35, (-(W / 2 + 0.02), -D / 2 - 0.18, 1.92), rot=(90, 0, 0), mat=flat('iron', 0.5, 0.6),
          origin='center')
    lantern('lan', (-(W / 2 + 0.02), -D / 2 - 0.34, 1.52), 0.15, 3.0)
    barrel_model('barrel', loc=(W / 2 + 0.25, D / 2 + 0.3, 0), scale=0.75, seed=4)


@asset('trade_post', 'building', 'props_buildings', fp=(3.0, 1.7), front='-Y',
       notes='Merchant sled with crates, sacks and a blue awning. Front faces screen down-left (world -Y); '
             'runners curl up at +X (screen down-right).')
def b_trade_post():
    rnd = L.rng(10)
    iron = flat('#5C4430', 0.7)
    for sy_ in (-1, 1):
        y = sy_ * 0.62
        L.smooth_tube('runner', [(-1.4, y, 0.07), (0.6, y, 0.07), (1.25, y, 0.1), (1.5, y, 0.32), (1.4, y, 0.55)],
                      0.055, iron)
        for x in (-1.0, -0.2, 0.6):
            box('strut', (0.1, 0.1, 0.25), (x, y, 0.07), mat=flat('wood_dark', 0.8), bevel=0.02)
    deck = L.stripes('#C98F55', '#B27843', 3.3, 'X', rough=0.8, soft=0.03)
    box('deck', (2.7, 1.45, 0.16), (0, 0, 0.3), mat=deck, bevel=0.04)
    for sy_ in (-1, 1):
        box('rail', (2.7, 0.08, 0.14), (0, sy_ * 0.7, 0.46), mat=flat('wood_dark', 0.8), bevel=0.03)
    z = 0.46
    crate_model('c1', 0.62, (-0.85, 0.25, z), seed=1)
    crate_model('c2', 0.52, (-0.85, 0.28, z + 0.62), rot=(0, 0, 12), seed=2)
    crate_model('c3', 0.55, (-0.2, 0.35, z), rot=(0, 0, -8), seed=3)
    barrel_model('br', loc=(0.5, 0.3, z), scale=0.8, seed=5)
    sack = flat('#D8C39A', 0.9)
    for i, (x, y) in enumerate([(-0.3, -0.35), (0.25, -0.3)]):
        blob('sack', 0.3, (x, y, z + 0.2), sack, scale=(1.0, 0.85, 0.85), seed=400 + i, amp=0.15, subdiv=3,
             flat_bottom=0.6)
        cyl('tie', 0.07, 0.12, (x, y, z + 0.42), mat=flat('rope', 0.8), segs=10, r_top=0.05)
    # treasure-ish chest at the front right
    box('chest', (0.62, 0.42, 0.34), (1.0, -0.2, z), mat=flat('#A0522D', 0.7), bevel=0.04)
    box('lid', (0.64, 0.44, 0.14), (1.0, -0.2, z + 0.34), mat=flat('#B5653A', 0.7), bevel=0.06)
    gold = flat('gold', 0.3, 0.8)
    for x in (0.8, 1.2):
        box('band', (0.06, 0.46, 0.5), (x, -0.2, z - 0.01), mat=gold, bevel=0.015)
    box('lock', (0.1, 0.04, 0.12), (1.0, -0.43, z + 0.28), mat=gold, bevel=0.015)
    rolled = flat('#3D7CC9', 0.8)
    cyl('rug', 0.13, 0.9, (1.0, 0.35, z + 0.13), rot=(0, 90, 0), mat=rolled, segs=18, origin='center',
        cap_mat=flat('#2F64A6', 0.8))
    # canopy
    post = flat('wood_mid', 0.8)
    for sx_ in (-1, 1):
        cyl('post', 0.06, 1.95, (sx_ * 1.25, -0.68, 0.46), mat=post, segs=10)
        cyl('post', 0.06, 2.2, (sx_ * 1.25, 0.68, 0.46), mat=post, segs=10)
    awning(2.85, 1.4, 2.7, 2.4, 0.85, -0.95, 'blue', 'cream', 8)
    # hanging coin sign on the front-left post
    box('signarm', (0.04, 0.4, 0.04), (-1.25, -0.88, 2.05), mat=post, bevel=0.01)
    box('sign', (0.04, 0.42, 0.42), (-1.25, -1.0, 1.55), mat=flat('wood_light', 0.8), bevel=0.03)
    cyl('coin', 0.13, 0.03, (-1.28, -1.0, 1.76), rot=(0, 90, 0), mat=gold, segs=24, origin='center')
    lantern('lan', (1.25, -0.95, 1.75), 0.14, 3.0)


def log_house(W, D, wall_h, ridge_z, over=0.32, r=0.13, seed=1, door_x=0.0, windows=((0.0, 'x+'),),
              roof_col=('#7A3F2E', '#6B3526'), chimney_x=None, log_cols=('#B5763F', '#A86A36', '#C08049')):
    """Log cabin with gable roof along X.  Door on -Y face; windows: list of (offset, face)."""
    rnd = L.rng(seed)
    endm = L.end_grain()
    hc = r * 1.84
    n = int(round(wall_h / hc))
    for k in range(n):
        z = r + k * hc
        for sgn in (-1, 1):
            c = log_cols[(k + (sgn > 0)) % len(log_cols)]
            log('lx', r, W + 0.36, (rnd.uniform(-0.03, 0.03), sgn * D / 2, z), rot=(0, 90, 0),
                bark=tonal(c, 0.1, 3.0), end=endm, segs=14)
            c = log_cols[(k + 1 + (sgn > 0)) % len(log_cols)]
            log('ly', r, D + 0.36, (sgn * W / 2, rnd.uniform(-0.03, 0.03), z + hc / 2), rot=(90, 0, 0),
                bark=tonal(c, 0.1, 3.0), end=endm, segs=14)
    top = r + (n - 1) * hc + hc / 2 + r
    box('inner', (W - 0.1, D - 0.1, top), mat=flat('#8A5A33', 0.8), bevel=0.0)
    # gable ends (planks)
    gm = L.stripes('#A86A36', '#94592C', 3.5, 'Y', rough=0.85, soft=0.04)
    for sgn in (-1, 1):
        g = extrude('gable', [(-D / 2 - 0.05, 0.0), (D / 2 + 0.05, 0.0), (0.0, ridge_z - top + 0.02)], 0.12,
                    rot=(90, 0, 90), top=gm, side=gm, bevel=0.02)
        g.location = (sgn * W / 2 - 0.06, 0, top - 0.02)
    roofm = L.stripes(roof_col[0], roof_col[1], 4.0, 'Y', rough=0.85, soft=0.04)
    eave = top - over * (ridge_z - top) / (D / 2)
    roof_panel('roofF', W + 0.6, -D / 2 - over, eave, 0.0, ridge_z, 0.1, roofm, seed=seed)
    roof_panel('roofB', W + 0.6, D / 2 + over, eave, 0.0, ridge_z, 0.1, roofm, seed=seed + 1)
    log('ridge', 0.08, W + 0.7, (0, 0, ridge_z + 0.12), rot=(0, 90, 0), bark=flat('#6B3526', 0.8), end=endm, segs=12)
    L.snow_slab('ridgesnow', W + 0.5, 0.3, 0.1, (0, 0, ridge_z + 0.12), seed=seed + 7)
    # door
    dm = L.stripes('#7A4A2A', '#6A3E22', 5.0, 'X', rough=0.8, soft=0.05)
    box('doorframe', (0.95, 0.12, 1.45), (door_x, -D / 2 - r - 0.02, 0), mat=flat('#5E3A22', 0.8), bevel=0.03)
    box('door', (0.78, 0.12, 1.32), (door_x, -D / 2 - r - 0.06, 0), mat=dm, bevel=0.03)
    sphere('knob', 0.045, (door_x + 0.26, -D / 2 - r - 0.14, 0.68), flat('gold', 0.3, 0.8), segs=10, rings=6)
    box('step', (1.1, 0.45, 0.12), (door_x, -D / 2 - r - 0.2, 0), mat=snowy('stone', lo=0.6, hi=0.8), bevel=0.04)
    wm = L.emissive('window', '#FFE2A0', 'window', 2.2)
    frame = flat('#5E3A22', 0.8)
    for off, face in windows:
        if face in ('x+', 'x-'):
            sgn = 1 if face == 'x+' else -1
            x = sgn * (W / 2 + r + 0.02)
            box('wframe', (0.12, 0.8, 0.75), (x, off, 0.75), mat=frame, bevel=0.03)
            box('wglass', (0.12, 0.6, 0.55), (x + sgn * 0.02, off, 0.85), mat=wm, bevel=0.01)
            box('wbar', (0.13, 0.05, 0.55), (x + sgn * 0.04, off, 0.85), mat=frame, bevel=0.0)
            box('wbar', (0.13, 0.6, 0.05), (x + sgn * 0.04, off, 1.1), mat=frame, bevel=0.0)
            L.snow_slab('wsill', 0.2, 0.85, 0.05, (x + sgn * 0.03, off, 1.5), seed=9)
            box('shut', (0.06, 0.28, 0.66), (x, off - 0.5, 0.8), mat=flat('#3D7CC9', 0.7), bevel=0.02)
            box('shut', (0.06, 0.28, 0.66), (x, off + 0.5, 0.8), mat=flat('#3D7CC9', 0.7), bevel=0.02)
        else:
            y = -D / 2 - r - 0.02
            box('wframe', (0.8, 0.12, 0.75), (off, y, 0.75), mat=frame, bevel=0.03)
            box('wglass', (0.6, 0.12, 0.55), (off, y - 0.02, 0.85), mat=wm, bevel=0.01)
            box('wbar', (0.05, 0.13, 0.55), (off, y - 0.04, 0.85), mat=frame, bevel=0.0)
            box('wbar', (0.6, 0.13, 0.05), (off, y - 0.04, 1.1), mat=frame, bevel=0.0)
            L.snow_slab('wsill', 0.85, 0.2, 0.05, (off, y - 0.03, 1.5), seed=9)
            box('shut', (0.28, 0.06, 0.66), (off - 0.5, y, 0.8), mat=flat('#3D7CC9', 0.7), bevel=0.02)
            box('shut', (0.28, 0.06, 0.66), (off + 0.5, y, 0.8), mat=flat('#3D7CC9', 0.7), bevel=0.02)
    if chimney_x is not None:
        sm = snowy('#8E96A3', lo=0.75, hi=0.9)
        z_base = ridge_z - (ridge_z - eave) * 0.35 - 0.2
        box('chimney', (0.45, 0.45, ridge_z - z_base + 0.5), (chimney_x, 0.35, z_base), mat=L.brick(
            '#8E96A3', '#7A828E', '#C7CDD5', scale=3.0, row_h=0.45, snow_top=False), bevel=0.04)
        box('chimcap', (0.55, 0.55, 0.1), (chimney_x, 0.35, ridge_z + 0.5), mat=sm, bevel=0.03)
        L.snow_slab('chsnow', 0.5, 0.5, 0.07, (chimney_x, 0.35, ridge_z + 0.59), seed=4)
    return top, eave


@asset('worker_hut', 'building', 'props_buildings', fp=(2.8, 2.4), front='-Y', catcher=18.0,
       notes='Small log cabin for hired workers. Door faces screen down-left (world -Y).')
def b_worker_hut():
    log_house(2.4, 2.0, 1.55, 2.75, seed=3, windows=((0.0, 'x+'),), chimney_x=-0.6)
    log_pile('fw', 3, 0.1, 0.6, (1.62, 0.65, 0), seed=8)
    barrel_model('br', loc=(-1.05, -1.3, 0), scale=0.62, seed=11)


@asset('chief_lodge', 'building', 'props_buildings', fp=(4.6, 3.6), front='-Y', catcher=24.0, samples=64,
       notes="Chief's big log lodge (decor). Porch + door face screen down-left (world -Y).")
def b_chief_lodge():
    W, D = 4.0, 3.0
    top, eave = log_house(W, D, 2.1, 3.9, over=0.4, r=0.15, seed=5, door_x=0.0,
                          windows=((-0.6, 'x+'), (0.6, 'x+'), (-1.3, 'y-'), (1.3, 'y-')),
                          roof_col=('#3F5F8A', '#36527A'), chimney_x=1.1)
    # porch: deck + posts + small roof
    deck = L.stripes('#C98F55', '#B27843', 3.3, 'X', rough=0.8, soft=0.03)
    box('porch', (2.2, 1.0, 0.18), (0, -D / 2 - 0.65, 0), mat=deck, bevel=0.04)
    post = flat('wood_mid', 0.8)
    for sx_ in (-1, 1):
        cyl('ppost', 0.09, 1.62, (sx_ * 0.95, -D / 2 - 1.05, 0.18), mat=post, segs=12)
    roof_panel('proof', 2.6, -D / 2 - 1.3, 1.72, -D / 2 - 0.42, 1.9, 0.1,
               L.stripes('#3F5F8A', '#36527A', 4.0, 'Y', rough=0.85, soft=0.04), seed=12)
    # antlers over the door
    ant = flat('bone', 0.6)
    mb = L.MB()
    cx, cy, cz = 0.0, -D / 2 - 0.2, 1.75
    for sgn in (-1, 1):
        a0 = Vector((cx + sgn * 0.08, cy, cz))
        a1 = Vector((cx + sgn * 0.35, cy - 0.02, cz + 0.3))
        a2 = Vector((cx + sgn * 0.42, cy - 0.02, cz + 0.55))
        mb.seg(a0, a1, 0.035, ant, r2=0.03)
        mb.seg(a1, a2, 0.03, ant, r2=0.015)
        mb.seg(a1, a1 + Vector((-sgn * 0.08, 0, 0.22)), 0.025, ant, r2=0.012)
    mb.done('antlers')
    box('plaque', (0.4, 0.06, 0.3), (cx, cy + 0.03, cz - 0.15), mat=flat('wood_dark', 0.8), bevel=0.04)
    # banner on the ridge
    cyl('fpole', 0.035, 1.5, (-1.4, 0, 3.95), mat=flat('wood_dark', 0.8), segs=8)
    flag('banner', (-1.37, 0, 5.38), 0.7, 0.42, 'red', seed=2)
    log_pile('fw', 4, 0.12, 0.8, (W / 2 + 0.55, 0.9, 0), seed=9)
    barrel_model('br', loc=(-W / 2 - 0.35, -D / 2 - 0.3, 0), scale=0.8, seed=7)
    lantern('lan1', (-0.95, -D / 2 - 1.25, 1.55), 0.13, 3.0)
    lantern('lan2', (0.95, -D / 2 - 1.25, 1.55), 0.13, 3.0)


def flag(name, top_loc, w, h, color='red', seed=0, emblem=True):
    """Waving cloth flag hanging from (top_loc) toward +X (along world X)."""
    bm = L.bmesh.new()
    nx, nz = 12, 6
    verts = []
    for j in range(nz + 1):
        row = []
        for i in range(nx + 1):
            u = i / nx
            v = j / nz
            x = u * w
            y = 0.08 * math.sin(u * 5.0 + seed) * u
            z = -v * h - 0.04 * u * math.sin(v * 3 + u * 4)
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for j in range(nz):
        for i in range(nx):
            bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
    L.bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.02)
    nb = L.NB(name + '_cloth', rough=0.8)
    tc = nb.n('ShaderNodeTexCoord')
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['Object'], sep.inputs[0])
    # cream border stripe + centre disc emblem
    zc = nb.math('ADD', sep.outputs['Z'], h / 2)
    xc = nb.math('SUBTRACT', sep.outputs['X'], w * 0.45)
    d = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', xc, xc), nb.math('MULTIPLY', zc, zc)))
    disc = nb.map_range(d, h * 0.22, h * 0.2)
    stripe = nb.map_range(nb.math('ABSOLUTE', zc), h * 0.36, h * 0.38)
    col = nb.mix_rgb(stripe, C(color), C('cream'))
    if emblem:
        col = nb.mix_rgb(disc, col, C('gold'))
    nb.base(col)
    ob = L.finish(name, bm, [nb.m], loc=top_loc)
    return ob


@asset('tent_a', 'building', 'props_buildings', fp=(1.9, 2.4), front='-Y',
       notes='Canvas A-frame tent; entrance faces screen down-left (world -Y).')
def b_tent_a():
    canvas = tonal('canvas', 0.08, 2.0, rough=0.9)
    trim = flat('red', 0.8)
    Wd, Ln, Hh = 1.9, 2.2, 1.55     # width (X), length (Y), ridge height
    half = Wd / 2
    for sgn in (-1, 1):
        ln = math.hypot(half, Hh)
        ang = math.degrees(math.atan2(Hh, half))
        mid = Vector((sgn * half / 2, 0, Hh / 2))
        p = box('panel', (ln, Ln, 0.06), tuple(mid), rot=(0, sgn * ang, 0), mat=canvas, bevel=0.025, origin='center')
        n = Vector((sgn * math.sin(math.radians(ang)), 0, math.cos(math.radians(ang))))
        L.snow_slab('tsnow', ln * 0.42, Ln - 0.25, 0.08, tuple(Vector((sgn * half * 0.2, 0, Hh * 0.8)) + n * 0.02),
                    rot=(0, sgn * ang, 0), seed=3 + sgn, droop=0.03)
        # red hem band along the bottom edge + a mid patch
        hl = 0.34
        hc = Vector((sgn * (half - hl / 2 * math.cos(math.radians(ang))), 0, hl / 2 * math.sin(math.radians(ang))))
        box('hem', (hl, Ln + 0.02, 0.075), tuple(hc + n * 0.02), rot=(0, sgn * ang, 0), mat=trim,
            bevel=0.02, origin='center')
        pc = Vector((sgn * half * 0.5, 0.35, Hh * 0.5)) + n * 0.035
        box('patch', (0.3, 0.32, 0.02), tuple(pc), rot=(0, sgn * ang, 8), mat=flat('#D9C49A', 0.9),
            bevel=0.008, origin='center')
    # back wall + front opening (dark) with flaps tied back
    back = extrude('back', [(-half, 0), (half, 0), (0, Hh)], 0.05, rot=(90, 0, 0), top=canvas, side=canvas, bevel=0.01)
    back.location = (0, Ln / 2, 0)
    dark = flat('#3A2E2A', 0.9)
    opening = extrude('open', [(-half * 0.62, 0), (half * 0.62, 0), (0, Hh * 0.82)], 0.04, rot=(90, 0, 0), top=dark,
                      side=dark, bevel=0.0)
    opening.location = (0, -Ln / 2 + 0.25, 0)
    for sgn in (-1, 1):
        # rolled-up door flaps along the entrance edges
        a = Vector((sgn * half * 0.92, -Ln / 2 - 0.02, 0.05))
        b = Vector((sgn * 0.1, -Ln / 2 - 0.02, Hh * 0.92))
        mb = L.MB()
        mb.seg(a, b, 0.07, canvas, segs=10)
        mb.done('roll')
        mid = a + (b - a) * 0.45
        cyl('tie', 0.08, 0.06, tuple(mid), mat=trim, segs=12, origin='center',
            rot=(0, -sgn * math.degrees(math.atan2(b.x - a.x, b.z - a.z)) * -1, 0))
    pole = flat('wood_dark', 0.8)
    cyl('ridgepole', 0.05, Ln + 0.5, (0, 0, Hh + 0.02), rot=(90, 0, 0), mat=pole, segs=10, origin='center')
    for y in (-Ln / 2 - 0.25, Ln / 2 + 0.25):
        cyl('upright', 0.05, Hh + 0.12, (0, y, 0), mat=pole, segs=10)
    rope = flat('rope', 0.8)
    mb = L.MB()
    for y in (-Ln / 2 - 0.25, Ln / 2 + 0.25):
        for sgn in (-1, 1):
            a = Vector((0, y, Hh + 0.05))
            b = Vector((sgn * 0.55, y + (-0.55 if y < 0 else 0.55), 0.02))
            mb.seg(a, b, 0.012, rope, segs=5)
            mb.cone(0.03, 0.01, 0.2, pole, loc=tuple(b + Vector((0, 0, 0.05))), segs=6)
    mb.done('ropes')
    blob('snowbank', 0.4, (0.9, 0.8, 0), flat('snow_mat', 0.9), scale=(1.2, 1.4, 0.4), seed=5, amp=0.2)


@asset('campfire', 'decor', 'props_buildings', fp=('r', 0.6),
       notes='Logs + stone ring; the flames are drawn by the game (fx_fire) at the anchor, ~20 px up.')
def b_campfire():
    round_stone_ring(0.52, 10, seed=7, size=0.15)
    char = flat('#2E2724', 0.9)
    ember = L.emissive('cember', '#B4482A', 'fire', 2.0)
    for i in range(10):
        a = math.tau * i / 10
        blob('em', 0.07, (0.18 * math.cos(a), 0.18 * math.sin(a), 0.02), ember if i % 2 else char, seed=500 + i,
             amp=0.3, subdiv=1, facet=True)
    bark = tonal('bark', 0.15, 6.0)
    for i in range(5):
        a = math.tau * i / 5 + 0.3
        d = Vector((math.cos(a), math.sin(a), 0))
        p = d * 0.32 + Vector((0, 0, 0.08))
        q = d * -0.02 + Vector((0, 0, 0.45))
        mb = L.MB()
        mb.seg(p, q, 0.075, bark, segs=10)
        mb.done('log%d' % i)
        sphere('charend', 0.07, tuple(q), char, segs=10, rings=6)


@asset('upgrade_bench', 'building', 'props_buildings', fp=(2.4, 1.3), front='-Y',
       notes='Backpack upgrade workbench: table with backpack, anvil on a stump, tool board at the back.')
def b_upgrade_bench():
    top_m = tonal('#C98F55', 0.1, 3.0)
    legm = flat('wood_dark', 0.8)
    box('top', (2.0, 0.9, 0.12), (-0.2, 0, 0.78), mat=top_m, bevel=0.04)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            box('leg', (0.13, 0.13, 0.8), (-0.2 + sx_ * 0.88, sy_ * 0.36, 0), mat=legm, bevel=0.03)
    box('shelf', (1.85, 0.75, 0.06), (-0.2, 0, 0.25), mat=flat('wood_mid', 0.8), bevel=0.02)
    # tool board at the back
    box('board', (1.9, 0.08, 1.0), (-0.2, 0.48, 0.9), mat=L.stripes('#B27843', '#A06A3A', 3.0, 'X', soft=0.04),
        bevel=0.03)
    L.snow_slab('bsnow', 1.85, 0.1, 0.06, (-0.2, 0.48, 1.9), seed=2)
    iron = flat('iron', 0.4, 0.7)
    wood = flat('wood_light', 0.8)
    # hammer + saw on the board
    box('hh', (0.05, 0.05, 0.5), (-0.9, 0.42, 1.15), mat=wood, bevel=0.01)
    box('hhead', (0.22, 0.08, 0.1), (-0.9, 0.42, 1.6), mat=iron, bevel=0.02)
    box('saw', (0.55, 0.02, 0.2), (-0.3, 0.42, 1.35), mat=flat('steel', 0.3, 0.8), bevel=0.0, taper=(1.0, 1.0))
    box('sawh', (0.15, 0.05, 0.16), (0.02, 0.42, 1.38), mat=flat('red', 0.6), bevel=0.02)
    # backpack on the table
    pack = flat('#A0643A', 0.7)
    pack2 = flat('#7E4A2A', 0.7)
    bx, by, bz = -0.45, -0.05, 0.84
    k = 1.3
    box('pack', (0.62 * k, 0.42 * k, 0.7 * k), (bx, by, bz), mat=pack, bevel=0.16, segs=4)
    box('pocket', (0.42 * k, 0.12 * k, 0.3 * k), (bx, by - 0.24 * k, bz + 0.1 * k), mat=pack2, bevel=0.07)
    box('flap', (0.64 * k, 0.46 * k, 0.14 * k), (bx, by - 0.02 * k, bz + 0.62 * k), mat=pack2, bevel=0.07,
        rot=(-8, 0, 0))
    for x in (-0.15, 0.15):
        box('strap', (0.07, 0.48 * k, 0.5 * k), (bx + x * k, by, bz + 0.25 * k), mat=flat('#5A3620', 0.7), bevel=0.02)
        box('buckle', (0.1, 0.03, 0.08), (bx + x * k, by - 0.25 * k, bz + 0.35 * k), mat=flat('gold', 0.3, 0.8),
            bevel=0.01)
    cyl('bedroll', 0.15, 0.85, (bx, by, bz + 0.84 * k + 0.02), rot=(0, 90, 0), mat=flat('#3D7CC9', 0.8), segs=18,
        origin='center', cap_mat=flat('#2F64A6', 0.8))
    # big gold up-arrow badge on the board (reads as "upgrade")
    arrow = [(-0.1, 0.0), (0.1, 0.0), (0.1, 0.22), (0.22, 0.22), (0.0, 0.45), (-0.22, 0.22), (-0.1, 0.22)]
    up = extrude('uparrow', arrow, 0.04, rot=(90, 0, 0), top=flat('ui_gold', 0.35, 0.3), side=flat('#D9A42E', 0.4),
                 bevel=0.01)
    up.location = (0.35, 0.43, 1.1)
    # anvil on a stump at +X
    bark = tonal('bark', 0.15, 6.0)
    cyl('stump', 0.3, 0.45, (1.15, -0.05, 0), mat=bark, segs=18, cap_mat=L.end_grain())
    ax, ay, az = 1.15, -0.05, 0.45
    box('abase', (0.36, 0.26, 0.12), (ax, ay, az), mat=iron, bevel=0.02, taper=(0.75, 0.75))
    box('awaist', (0.2, 0.16, 0.12), (ax, ay, az + 0.12), mat=iron, bevel=0.02)
    box('atop', (0.5, 0.22, 0.12), (ax, ay, az + 0.24), mat=iron, bevel=0.03)
    cyl('ahorn', 0.08, 0.22, (ax - 0.33, ay, az + 0.3), rot=(0, -90, 0), r_top=0.01, mat=iron, segs=12, origin='center')
    box('smallhammer', (0.04, 0.3, 0.04), (ax + 0.1, ay - 0.2, az + 0.38), rot=(0, 0, 30), mat=wood, bevel=0.01)
    # a coin pouch + glowing "upgrade" gem on the table
    sphere('pouch', 0.12, (0.3, -0.15, 0.95), flat('#C49A5A', 0.8), scale=(1, 1, 0.9))
    sphere('gem', 0.07, (0.55, -0.1, 0.92), flat('#5CC86A', 0.2, emission='#5CC86A', emission_strength=1.0))


@asset('fish_net', 'building', 'props_buildings', fp=(2.8, 2.8),
       notes='V-shaped fish trap net on poles. The closed corner points at the camera (screen down); the open '
             'side faces screen up (the sea). Fish shown inside. Place it on the shoreline.')
def b_fish_net():
    rope = flat('#EFE9DA', 0.85)
    wood = flat('#D49A50', 0.8)
    S = 1.3
    corner = Vector((S, -S, 0))
    ends = [Vector((-S, -S, 0)), Vector((S, S, 0))]
    poles = [corner] + ends + [(corner + ends[0]) / 2, (corner + ends[1]) / 2]
    for i, p in enumerate(poles):
        h = 1.35 if i == 0 else 1.25
        cyl('pole', 0.075, h, tuple(p), mat=wood, segs=12, bevel=0.03, cap_mat=L.end_grain())
        snow_cap('ps', 0.07, tuple(p + Vector((0, 0, h - 0.01))), 0.05, i)
    mb = L.MB()
    z0, z1 = 0.08, 1.05
    step = 0.17
    for e in ends:
        a, b = corner, e
        ln = (b - a).length
        d = (b - a).normalized()
        Hn = z1 - z0
        c = -Hn
        while c < ln:
            # lines u - h = c  and u + h = c2
            for sgn in (1, -1):
                pts = []
                for h in (0.0, Hn):
                    u = c + h if sgn > 0 else (c + Hn) - h
                    pts.append((u, h))
                (u0, h0), (u1, h1) = pts
                # clip to [0, ln]
                if u0 < 0:
                    h0 = h0 + (0 - u0) * (h1 - h0) / (u1 - u0)
                    u0 = 0
                if u1 < 0:
                    h1 = h1 + (0 - u1) * (h0 - h1) / (u0 - u1)
                    u1 = 0
                if u0 > ln:
                    h0 = h0 + (ln - u0) * (h1 - h0) / (u1 - u0)
                    u0 = ln
                if u1 > ln:
                    h1 = h1 + (ln - u1) * (h0 - h1) / (u0 - u1)
                    u1 = ln
                if abs(u1 - u0) + abs(h1 - h0) > 0.05:
                    sag0 = 0.05 * math.sin(math.pi * u0 / ln)
                    sag1 = 0.05 * math.sin(math.pi * u1 / ln)
                    mb.seg(a + d * u0 + Vector((0, 0, z0 + h0 - sag0 * (h0 / Hn))),
                           a + d * u1 + Vector((0, 0, z0 + h1 - sag1 * (h1 / Hn))), 0.011, rope, segs=4)
            c += step
        mb.seg(a + Vector((0, 0, z1)), b + Vector((0, 0, z1)), 0.025, rope, segs=6)
        mb.seg(a + Vector((0, 0, z0)), b + Vector((0, 0, z0)), 0.02, rope, segs=6)
    net = mb.done('net', smooth=True)
    # floats along the top rope
    fl = [flat('#F08A3A', 0.5), flat('cream', 0.5)]
    k = 0
    for e in ends:
        for t in (0.25, 0.5, 0.75):
            p = corner + (e - corner) * t + Vector((0, 0, z1))
            sphere('float', 0.08, tuple(p), fl[k % 2], scale=(1, 1, 0.8), segs=14, rings=8)
            k += 1
    # catch inside
    fish_model('f1', loc=(0.2, -0.1, 0.1), rot=(0, 0, 30), scale=0.8)
    fish_model('f2', loc=(0.6, 0.4, 0.1), rot=(0, 0, 120), scale=0.75)
    fish_model('f3', loc=(-0.3, -0.6, 0.1), rot=(0, 0, -20), scale=0.75)
    # coiled rope + basket at the corner outside
    box('basket', (0.5, 0.5, 0.35), (S + 0.45, -S - 0.1, 0), mat=flat('straw', 0.9), bevel=0.1)
    fish_model('f4', loc=(S + 0.45, -S - 0.1, 0.42), rot=(0, 0, 45), scale=0.55)


@asset('dock_pier', 'building', 'props_buildings', fp=(2.0, 4.4),
       notes='Wooden pier 2 m wide, 4.4 m long along world +Y (runs screen up-right into the sea). Anchor = centre; '
             'the land end is at -Y (screen down-left).')
def b_dock_pier():
    rnd = L.rng(14)
    Wd, Ln = 2.0, 4.4
    dz = 0.38
    n = 15
    for i in range(n):
        y = -Ln / 2 + (i + 0.5) * Ln / n
        c = ['#C98F55', '#BD844C', '#D39A5E'][rnd.randrange(3)]
        box('plank', (Wd + rnd.uniform(-0.06, 0.06), Ln / n - 0.03, 0.08), (rnd.uniform(-0.03, 0.03), y, dz),
            rot=(0, 0, rnd.uniform(-1.2, 1.2)), mat=flat(c, 0.8), bevel=0.02)
    beam = flat('wood_dark', 0.8)
    for sx_ in (-1, 1):
        box('stringer', (0.14, Ln, 0.16), (sx_ * (Wd / 2 - 0.2), 0, dz - 0.16), mat=beam, bevel=0.03)
    post = flat('#8A5A33', 0.8)
    for y in (-Ln / 2 + 0.2, 0, Ln / 2 - 0.2):
        for sx_ in (-1, 1):
            h = 0.85 if y > Ln / 2 - 0.3 or y < -Ln / 2 + 0.3 else 0.4
            cyl('post', 0.12, h, (sx_ * (Wd / 2 + 0.05), y, 0), mat=post, segs=14, cap_mat=L.end_grain())
            if h > 0.5:
                snow_cap('psnow', 0.11, (sx_ * (Wd / 2 + 0.05), y, h - 0.01), 0.05, int(y * 10 + sx_))
    # rope looped between the far posts + lantern + bollard
    L.smooth_tube('rope', [(-Wd / 2 - 0.05, Ln / 2 - 0.2, 0.75), (0, Ln / 2 - 0.15, 0.55), (Wd / 2 + 0.05, Ln / 2 - 0.2, 0.75)],
                  0.025, flat('rope', 0.8))
    cyl('bollard', 0.1, 0.3, (Wd / 2 - 0.35, Ln / 2 - 0.5, dz + 0.08), mat=flat('iron', 0.5, 0.5), segs=14)
    cyl('lpost', 0.06, 1.3, (-Wd / 2 + 0.25, Ln / 2 - 0.45, dz + 0.08), mat=post, segs=10)
    lantern('lan', (-Wd / 2 + 0.25, Ln / 2 - 0.45, dz + 1.38), 0.15, 3.0)
    # a little snow on a few planks + a fish crate
    for i, (x, y) in enumerate([(-0.75, -1.6), (0.8, 0.9), (-0.8, 1.7)]):
        snow_cap('ps', 0.2, (x, y, dz + 0.07), 0.07, i, scale=(1.4, 1.0, 1.0))
    crate_model('cr', 0.5, (0.45, -1.2, dz + 0.08), seed=3)


@asset('mine_entrance', 'building', 'props_buildings', fp=(4.0, 2.6), yaw=45.0, front='S', catcher=20.0,
       notes='Rock face with a timber-framed tunnel; the tunnel faces the camera (screen down). Rails + ore cart '
             'come out toward the viewer. Anchor = centre of the rock base.')
def b_mine_entrance():
    rnd = L.rng(15)
    # built facing local -Y; yaw=45 turns it to face the camera.  The rock face sits
    # behind (local +Y) so the timber portal, rails and cart stay in front of it.
    rock = snowy('#6E7683', lo=0.66, hi=0.82, noise_amt=0.45)
    rock2 = snowy('#5E6673', lo=0.66, hi=0.82, noise_amt=0.45)
    blob('cliff', 1.2, (0, 1.0, 0.25), rock, scale=(1.65, 0.72, 1.25), seed=31, amp=0.16, freq=1.4, subdiv=4,
         flat_bottom=0.25)
    blob('cl2', 0.8, (-1.55, 0.45, 0.2), rock2, scale=(1.0, 0.95, 1.0), seed=32, amp=0.2, freq=1.5, subdiv=3,
         flat_bottom=0.3)
    blob('cl3', 0.72, (1.6, 0.5, 0.15), rock, scale=(1.05, 0.95, 1.05), seed=33, amp=0.2, freq=1.5, subdiv=3,
         flat_bottom=0.3)
    blob('cl4', 0.55, (0.7, 1.35, 1.85), rock2, scale=(1.2, 1.0, 0.8), seed=34, amp=0.2, subdiv=3)
    blob('cl5', 0.4, (-1.05, -0.15, 0.1), rock2, scale=(1.1, 1.0, 0.8), seed=35, amp=0.25, subdiv=3, flat_bottom=0.4)
    nug = ore_nugget_mat()
    for i, (x, y, z) in enumerate([(-1.55, -0.3, 0.75), (1.5, -0.15, 0.6), (-1.2, -0.45, 0.25), (1.05, 0.25, 1.35),
                                   (-0.6, 0.3, 1.75), (1.85, 0.0, 0.35)]):
        blob('ore', 0.1, (x, y, z), nug, seed=600 + i, amp=0.3, subdiv=1, facet=True)
    # tunnel: dark opening in front of the rock + timber portal
    dark = flat('#15100E', 0.95)
    tun = extrude('tunnel', arch_pts(1.25, 1.55, 10), 0.5, rot=facing_rot(0), top=dark, side=dark, bevel=0.0)
    tun.location = (0, -0.05, 0)
    box('tunwall', (2.2, 0.5, 1.9), (0, 0.15, 0), mat=rock2, bevel=0.2)
    timber = tonal('#8A5A33', 0.12, 4.0)
    for sx_ in (-1, 1):
        box('tpost', (0.24, 0.26, 1.72), (sx_ * 0.76, -0.62, 0), mat=timber, bevel=0.04)
    box('lintel', (2.0, 0.3, 0.26), (0, -0.62, 1.68), mat=timber, bevel=0.05)
    L.snow_slab('lsnow', 1.9, 0.26, 0.08, (0, -0.62, 1.93), seed=6)
    for sx_ in (-1, 1):
        box('brace', (0.12, 0.14, 0.55), (sx_ * 0.56, -0.66, 1.4), rot=(0, sx_ * 45, 0), mat=timber, bevel=0.02,
            origin='center')
    lantern('lan', (0.0, -0.84, 1.28), 0.14, 3.5)
    box('lanhook', (0.03, 0.15, 0.03), (0.0, -0.78, 1.62), mat=flat('iron', 0.5, 0.5), bevel=0.0)
    # rails coming out of the tunnel toward the viewer (-Y)
    steel = flat('#7D8591', 0.35, 0.8)
    sleeper = flat('#6E4428', 0.85)
    for i in range(7):
        box('sleeper', (1.0, 0.16, 0.06), (0, -0.45 - i * 0.3, 0), mat=sleeper, bevel=0.015)
    for sx_ in (-1, 1):
        box('rail', (0.05, 2.15, 0.06), (sx_ * 0.33, -1.35, 0.06), mat=steel, bevel=0.01)
    # ore cart on the rails
    cart = flat('#5D646F', 0.45, 0.5)
    cz, cy = 0.16, -1.6
    box('cart', (0.95, 0.7, 0.45), (0, cy, cz), mat=cart, bevel=0.05, taper=(1.12, 1.12))
    box('cartrim', (1.08, 0.82, 0.06), (0, cy, cz + 0.45), mat=flat('#7A3F2E', 0.6), bevel=0.02)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            cyl('wheel', 0.1, 0.06, (sx_ * 0.38, cy + sy_ * 0.22, 0.12), rot=(0, 90, 0), mat=flat('iron', 0.5, 0.5),
                segs=14, origin='center')
    for i in range(7):
        blob('cartore', 0.12, (rnd.uniform(-0.28, 0.28), cy + rnd.uniform(-0.18, 0.18), cz + 0.47 + 0.04 * (i % 2)),
             nug if i % 2 else ore_mat(), seed=620 + i, amp=0.3, subdiv=1, facet=True)
    # pick leaning on the left post
    box('pickh', (0.05, 0.05, 1.0), (-1.0, -0.75, 0.05), rot=(0, -12, 0), mat=flat('wood_light', 0.8), bevel=0.01)
    box('pickhead', (0.5, 0.06, 0.07), (-1.1, -0.75, 1.0), rot=(0, -12, 0), mat=flat('iron', 0.4, 0.7), bevel=0.02,
        taper=(0.3, 1.0))


@asset('boat_small', 'decor', 'props_buildings', fp=(2.6, 1.1),
       notes='Small rowboat floating (hull cut at the waterline z=0), long axis along world X.')
def b_boat_small():
    nb = L.NB('hull', rough=0.6)
    tc = nb.n('ShaderNodeTexCoord')
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.link(tc.outputs['Object'], sep.inputs[0])
    f = nb.map_range(sep.outputs['Z'], 0.27, 0.29)
    col = nb.mix_rgb(f, C('#D9483B'), C('cream'))
    f2 = nb.map_range(sep.outputs['Z'], 0.39, 0.41)
    col = nb.mix_rgb(f2, col, C('#3D7CC9'))
    nb.base(col)
    hull_m = nb.m
    inner = flat('#B98A57', 0.8)
    bm = L.bmesh.new()
    L.bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        if z > 0:
            z = 0
        # pointed bow at +X
        w = 0.55 * (1.0 - 0.55 * max(0.0, x) ** 2)
        v.co = Vector((x * 1.3, y * w, z * 0.55 + 0.45))
    L.bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0.02),
                             plane_no=(0, 0, 1), clear_inner=True)
    for f in bm.faces:
        if f.normal.z > 0.9 and f.calc_center_median().z > 0.4:
            f.material_index = 1
    bm.normal_update()
    hull = L.finish('hull', bm, [hull_m, inner])
    # inner floor (a little lower than the rim), rim, seats, oars
    sphere('innerfloor', 1.0, (0, 0, 0.42), inner, scale=(1.2, 0.47, 0.02))
    L.MB  # noqa
    rim = flat('wood_dark', 0.8)
    mb = L.MB()
    pts = []
    for i in range(41):
        t = math.tau * i / 40
        x = math.cos(t)
        w = 0.55 * (1.0 - 0.55 * max(0.0, x) ** 2)
        pts.append(Vector((x * 1.3, math.sin(t) * w, 0.46)))
    for i in range(40):
        mb.seg(pts[i], pts[i + 1], 0.035, rim, segs=6)
    mb.done('rim')
    seat = flat('wood_light', 0.8)
    for x in (-0.45, 0.35):
        w = 0.55 * (1.0 - 0.55 * max(0.0, x / 1.3) ** 2) * math.sqrt(max(0.0, 1 - (x / 1.3) ** 2))
        box('seat', (0.26, 2 * w, 0.05), (x, 0, 0.42), mat=seat, bevel=0.015)
    oar = flat('wood_light', 0.8)
    for sgn in (-1, 1):
        cyl('oar', 0.025, 1.6, (0.0, sgn * 0.42, 0.55), rot=(0, 86, sgn * 8), mat=oar, segs=8, origin='center')
        box('blade', (0.4, 0.14, 0.03), (-0.85, sgn * 0.5, 0.5), rot=(0, 4, sgn * 8), mat=oar, bevel=0.015)
    snow_cap('bsnow', 0.16, (0.8, 0.0, 0.44), 0.07, 4, scale=(1.3, 1.0, 1.0))
    fish_model('bf', loc=(-0.1, 0.0, 0.5), rot=(0, 0, 25), scale=0.5)


# =========================================================================== DECOR

def fence_logs(axis, neighbours=True):
    """3 vertical logs per metre with rounded light end-grain tops.  axis 'x' or 'y'."""
    heights = [0.84, 0.94, 0.88]
    cols = ['#C98A50', '#B97A43', '#D0955A']
    r = 0.16
    endm = L.end_grain(light='#EBC795', ring='#CF9F66', scale=10.0)
    made = []
    for seg in ((-1, 0, 1) if neighbours else (0,)):
        for i in range(3):
            o = (i - 1) / 3.0 + seg
            pos = (o, 0, 0) if axis == 'x' else (0, o, 0)
            ob = cyl('flog', r * (1.0 + 0.04 * ((i * 7) % 3 - 1)), heights[i], pos, mat=tonal(cols[i], 0.1, 3.0),
                     segs=18, bevel=0.07, bsegs=4, cap_mat=endm)
            if seg != 0:
                ob.visible_camera = False
                ob.visible_diffuse = True
            made.append(ob)
    return made


FENCE_NOTE = ('1 m palisade segment of 3 vertical logs (r 0.16 m, ~0.9 m tall), anchor = segment centre on the '
              'ground. Tiles seamlessly incl. the baked shadow: place consecutive segments 1 m apart along %s, '
              'and depth-sort by anchor y as usual. A run end looks best capped with fence_post.')


@asset('fence_log_x', 'decor', 'props_decor', fp=(1.0, 0.36),
       notes=FENCE_NOTE % 'world +X (the run goes screen down-right): screen step (+45.25, +22.63) px per segment')
def b_fence_log_x():
    # neighbours (invisible to camera) cast the shadow a continuous fence would; prop_pack.py
    # then splits the shadow between segments with a partition-of-unity weight (tileAxis).
    fence_logs('x')
    return {'extra': {'tileAxis': 'x'}}


@asset('fence_log_y', 'decor', 'props_decor', fp=(0.36, 1.0),
       notes=FENCE_NOTE % 'world +Y (the run goes screen up-right): screen step (+45.25, -22.63) px per segment')
def b_fence_log_y():
    fence_logs('y')
    return {'extra': {'tileAxis': 'y'}}


@asset('fence_post', 'decor', 'props_decor', fp=('r', 0.22), notes='Thick fence end/corner post with snow cap.')
def b_fence_post():
    cyl('post', 0.21, 1.08, mat=tonal('#B97A43', 0.1, 3.0), segs=20, bevel=0.08, bsegs=4,
        cap_mat=L.end_grain(light='#EBC795', ring='#CF9F66', scale=10.0))
    snow_cap('snow', 0.17, (0.0, 0.0, 1.06), 0.08, 2)
    cyl('band', 0.215, 0.06, (0, 0, 0.75), mat=flat('rope', 0.8), segs=20, bevel=0.0)


@asset('bench', 'decor', 'props_decor', fp=(1.9, 0.6), notes='Plank bench (like the reference), long axis along world X.')
def b_bench():
    seat = flat('#D39556', 0.75)
    leg = flat('#B57A43', 0.8)
    box('seat1', (1.9, 0.26, 0.09), (0, -0.14, 0.46), mat=seat, bevel=0.03)
    box('seat2', (1.9, 0.26, 0.09), (0, 0.14, 0.46), mat=flat('#C98A50', 0.75), bevel=0.03)
    for x in (-0.72, 0.72):
        box('leg', (0.14, 0.5, 0.46), (x, 0, 0), mat=leg, bevel=0.03)
    snow_cap('snow', 0.22, (0.5, 0.0, 0.54), 0.07, 3, scale=(1.6, 1.0, 1.0))
    snow_cap('snow2', 0.12, (-0.55, 0.08, 0.54), 0.05, 4, scale=(1.4, 1.0, 1.0))


@asset('lamp_post', 'decor', 'props_decor', fp=('r', 0.25), notes='Wooden lamp post with a warm glowing lantern (~2.4 m).')
def b_lamp_post():
    post = tonal('#7A4E2C', 0.1, 4.0)
    box('base', (0.4, 0.4, 0.2), mat=snowy('stone', lo=0.6, hi=0.8), bevel=0.05)
    cyl('post', 0.08, 2.1, (0, 0, 0.18), mat=post, segs=12)
    box('arm', (0.5, 0.06, 0.06), (0.2, 0, 2.1), mat=post, bevel=0.015)
    lantern('lan', (0.38, 0.0, 1.6), 0.2, 4.0)
    box('chain', (0.02, 0.02, 0.24), (0.38, 0, 1.88), mat=flat('iron', 0.5, 0.5), bevel=0.0)
    snow_cap('snow', 0.12, (0.0, 0.0, 2.26), 0.06, 1)
    snow_cap('snow2', 0.14, (0.38, 0.0, 1.9), 0.05, 2)


@asset('barrel', 'decor', 'props_decor', fp=('r', 0.38), notes='Wooden barrel with iron hoops and snow on the lid.')
def b_barrel():
    barrel_model('barrel', seed=1)


@asset('crate', 'decor', 'props_decor', fp=(0.8, 0.8), notes='Wooden crate with snow on top.')
def b_crate():
    crate_model('crate', 0.8, seed=2)


@asset('firewood_pile', 'decor', 'props_decor', fp=(1.0, 1.0),
       notes='Pyramid of logs (end grain faces screen down-right) with snow on top.')
def b_firewood_pile():
    log_pile('pile', 4, 0.14, 0.95, seed=5)


@asset('signpost', 'decor', 'props_decor', fp=('r', 0.25), notes='Post with two blank arrow boards (no baked text).')
def b_signpost():
    post = tonal('#8A5A33', 0.1, 4.0)
    cyl('post', 0.08, 1.9, mat=post, segs=12, cap_mat=L.end_grain())
    snow_cap('snow', 0.08, (0, 0, 1.89), 0.05, 2)
    board = flat('#D39A5E', 0.8)
    arrow = [(-0.45, -0.13), (0.3, -0.13), (0.45, 0.0), (0.3, 0.13), (-0.45, 0.13)]
    arrow_m = [(-x, y) for x, y in arrow][::-1]
    a1 = extrude('a1', arrow_m, 0.05, rot=(90, 0, 0), top=board, side=flat('#B27843', 0.8), bevel=0.015)
    a1.location = (-0.2, -0.06, 1.45)
    a2 = extrude('a2', arrow, 0.05, rot=(90, 0, 90), top=board, side=flat('#B27843', 0.8), bevel=0.015)
    a2.location = (0.06, 0.2, 1.12)
    L.snow_slab('s1', 0.75, 0.06, 0.05, (-0.2, -0.09, 1.58), seed=1)
    L.snow_slab('s2', 0.06, 0.75, 0.05, (0.09, 0.2, 1.25), seed=2)


@asset('flag_pole', 'decor', 'props_decor', fp=('r', 0.35), notes='Tall flag pole (~4 m) with a red village banner.')
def b_flag_pole():
    box('base', (0.6, 0.6, 0.3), mat=snowy('stone', lo=0.6, hi=0.8), bevel=0.06)
    cyl('pole', 0.05, 3.8, (0, 0, 0.3), mat=flat('#D9D2C5', 0.5, 0.3), segs=12, r_top=0.035)
    sphere('ball', 0.09, (0, 0, 4.15), flat('gold', 0.3, 0.8), segs=16, rings=10)
    flag('flag', (0.03, 0, 4.0), 1.1, 0.68, 'red', seed=1)


@asset('hay_bale', 'decor', 'props_decor', fp=(1.0, 0.6), notes='Rectangular hay bale with twine and a little snow.')
def b_hay_bale():
    nb = L.NB('hay', rough=0.95)
    nz = nb.noise(18.0, 3.0)
    f = nb.map_range(nz, 0.35, 0.65)
    nb.base(nb.mix_rgb(f, C('straw_dark'), C('#EBC86A')))
    box('bale', (1.0, 0.6, 0.5), mat=nb.m, bevel=0.1, segs=4)
    tw = flat('#8A5A33', 0.8)
    for x in (-0.25, 0.25):
        box('twine', (0.04, 0.62, 0.52), (x, 0, -0.01), mat=tw, bevel=0.015)
    snow_cap('snow', 0.26, (-0.15, 0.04, 0.48), 0.08, 2, scale=(1.5, 0.95, 1.0))
    mb = L.MB()
    rnd = L.rng(3)
    straw = flat('#E2B85A', 0.9)
    for i in range(14):
        p = Vector((rnd.uniform(-0.55, 0.55), rnd.uniform(-0.45, 0.45), 0.01))
        if abs(p.x) < 0.5 and abs(p.y) < 0.3:
            continue
        q = p + Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0.0))
        mb.seg(p, q, 0.008, straw, segs=4)
    mb.done('loose')


# =========================================================================== ITEMS

@asset('item_fish_raw', 'item', 'props_items', item={'thickness': 0.2},
       notes='Whole raw fish lying on its side.')
def b_item_fish_raw():
    fish_model('fish', length=0.9, height=0.44, thick=0.2, loc=(0, 0, 0.1), rot=(0, 0, 45))


@asset('item_fish_cooked', 'item', 'props_items', item={'thickness': 0.17},
       notes='Grilled salmon steak (like the reference tower).')
def b_item_fish_cooked():
    steak_model('steak', R=0.37, thick=0.17, cooked=True, rot=(0, 0, 45))


@asset('item_log', 'item', 'props_items', item={'thickness': 0.24},
       notes='Log lying along world X (end grain toward screen down-right).')
def b_item_log():
    log('log', 0.12, 0.8, (0, 0, 0.12), rot=(0, 90, 0), bark=tonal('#8A5A33', 0.15, 6.0),
        end=L.end_grain(scale=14.0), segs=18, bevel=0.03)
    cyl('twig', 0.035, 0.14, (-0.05, -0.08, 0.2), rot=(-50, 0, 0), mat=tonal('#8A5A33', 0.15, 6.0), segs=8,
        cap_mat=L.end_grain())


@asset('item_plank', 'item', 'props_items', item={'thickness': 0.14},
       notes='Sawn plank lying along world X.')
def b_item_plank():
    nb = L.NB('plankgrain', rough=0.75)
    tc = nb.n('ShaderNodeTexCoord')
    wv = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y')
    wv.inputs['Scale'].default_value = 4.0
    wv.inputs['Distortion'].default_value = 4.0
    wv.inputs['Detail'].default_value = 2.0
    nb.link(tc.outputs['Object'], wv.inputs['Vector'])
    f = nb.map_range(wv.outputs['Fac'], 0.3, 0.9)
    nb.base(nb.mix_rgb(f, C('#E9B678'), C('#CF9055')))
    box('plank', (0.86, 0.32, 0.14), mat=nb.m, bevel=0.03, top_mat=None)
    # end grain on the +X end
    box('end', (0.012, 0.29, 0.12), (0.43, 0, 0.01), mat=flat('#F0CF9E', 0.8), bevel=0.0)


@asset('item_wheat', 'item', 'props_items', item={'thickness': 0.2},
       notes='Wheat sheaf tied with a red band, ears toward screen right.')
def b_item_wheat():
    rnd = L.rng(21)
    mb = L.MB()
    straw = flat('#D9B04E', 0.6)
    ear = flat('#EBC14E', 0.55)
    ear2 = flat('#DCA83C', 0.55)
    for i in range(30):
        y = rnd.uniform(-0.1, 0.1)
        z = 0.1 + rnd.uniform(-0.07, 0.07)
        fan = rnd.uniform(-0.14, 0.14)
        p = Vector((-0.4, y * 1.2 + fan * 0.3, z))
        q = Vector((0.16, y + fan * 0.6, z + 0.01))
        mb.seg(p, q, 0.02, straw, segs=5)
        d = Vector((1.0, fan * 1.6, 0.06)).normalized()
        ec = q + d * 0.1
        rot = Vector((0, 0, 1)).rotation_difference(d).to_euler()
        mb.sphere(0.05, ear if i % 2 else ear2, loc=tuple(ec), rot=tuple(math.degrees(v) for v in rot),
                  scale=(1.0, 0.85, 2.5), segs=8, rings=6)
    sheaf = mb.done('sheaf')
    band = cyl('band', 0.135, 0.08, (-0.1, 0, 0.1), rot=(0, 90, 0), mat=flat('red', 0.6), segs=18, origin='center',
               scale=(0.85, 1.0, 1.0))
    L.group([sheaf, band], 'wheat', rot=(0, 0, 45))


@asset('item_bread', 'item', 'props_items', item={'thickness': 0.24}, notes='Bread loaf.')
def b_item_bread():
    bread_model('bread', L_=0.66, W=0.4, H=0.26, rot=(0, 0, 45))


@asset('item_ore', 'item', 'props_items', item={'thickness': 0.22}, notes='Chunk of orange iron ore.')
def b_item_ore():
    nb = L.NB('oreitem', rough=0.7)
    nz = nb.noise(4.0, 3.0)
    f = nb.map_range(nz, 0.4, 0.6)
    nb.base(nb.mix_rgb(f, C('#8A6A5A'), C('#B0704A')))
    blob('ore', 0.25, (0, 0, 0.1), nb.m, scale=(1.3, 1.05, 0.62), seed=7, amp=0.3, freq=1.6, subdiv=1, facet=True,
         flat_bottom=0.62)
    nug = flat('ore', 0.3, 0.3, emission='#FF9A3C', emission_strength=0.35)
    for i, (x, y, z, r) in enumerate([(0.05, -0.05, 0.2, 0.09), (-0.14, 0.05, 0.17, 0.07), (0.17, 0.1, 0.15, 0.065),
                                      (-0.02, 0.14, 0.18, 0.06), (0.2, -0.12, 0.1, 0.05)]):
        blob('n%d' % i, r, (x, y, z), nug, seed=30 + i, amp=0.3, subdiv=1, facet=True,
             rot=(i * 20, i * 33, i * 47))


@asset('item_ingot', 'item', 'props_items', item={'thickness': 0.16}, notes='Shiny steel ingot (trapezoid bar).')
def b_item_ingot():
    ingot_model('ingot', rot=(0, 0, 45))


@asset('item_meat_raw', 'item', 'props_items', item={'thickness': 0.2}, notes='Raw ham/drumstick with bone.')
def b_item_meat_raw():
    meat_model('meat', cooked=False, rot=(0, 0, 45))


@asset('item_meat_cooked', 'item', 'props_items', item={'thickness': 0.2}, notes='Smoked/roasted ham with bone.')
def b_item_meat_cooked():
    meat_model('meat', cooked=True, rot=(0, 0, 45))


@asset('item_coin', 'item', 'props_items', item={'thickness': 0.14}, notes='Thick gold coin with an embossed star.')
def b_item_coin():
    gold = flat('gold', 0.28, 0.85)
    gold2 = flat('#E6B03E', 0.3, 0.85)
    cyl('rim', 0.26, 0.14, mat=gold2, segs=40, bevel=0.03)
    cyl('face', 0.205, 0.145, mat=gold, segs=40, bevel=0.012)
    star = []
    for i in range(10):
        a = math.pi / 2 + math.tau * i / 10
        r = 0.13 if i % 2 == 0 else 0.055
        star.append((r * math.cos(a), r * math.sin(a)))
    s = extrude('star', star, 0.03, top=flat('#FFE08A', 0.25, 0.8), side=gold2, bevel=0.008)
    s.location = (0, 0, 0.14)
    s.rotation_euler.z = math.radians(45)
