"""
vil_dress.py - hair, hats, outfits and hand props for the Frost Village villagers.

Not run directly (imported by vil_build.py).  Every dress_<key>(rig, spec)
works on the STANDARD body from vil_body.build_body (char_build measurements),
before vil_body.apply_proportions() turns it into a kid / elder / plump body.
Reuses char_build's hair/hat/fur helpers; new pieces (quilted puffer, bear-ear
hood, earmuffs, ponytail, spiky hair, apron, flat cap, glasses, sunglasses,
afro, beret + feather, lute, cane, fur hat, handlebar moustache, shawl ...) live
here.

Toggled props (shown per frame through pose['_props']):
  snowball      white ball in the right hand (throw, until impactFrame)
  cane          grandpa's walking stick planted on the ground (dynamic)
  cane_hold     the same stick held up in the fist (angry)
  lute_front    bard's lute held for 'perform'      lute_back  slung on the back
  shades        fashion's sunglasses on the eyes    shades_up  pushed up (eyes shown)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy                                       # noqa: E402
import bmesh                                     # noqa: E402
from mathutils import Vector, Matrix             # noqa: E402

import bl_common as bc                           # noqa: E402
import char_geo as g                             # noqa: E402
import char_build as cb                          # noqa: E402
import vil_face as vf                            # noqa: E402

PI = math.pi
TAU = math.tau
M = cb.M
HEAD_R, HEAD_C = cb.HEAD_R, cb.HEAD_C
smoothstep = cb.smoothstep


# --------------------------------------------------------------------------- helpers

def catmull3(ctrl, n=24):
    """Catmull-Rom through 3D control points (char_geo.catmull is 2D only)."""
    pts = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    segs = len(ctrl) - 1
    out = []
    for k in range(n):
        t = k / (n - 1) * segs
        i = min(int(t), segs - 1)
        u = t - i
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * u +
                                (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * u * u +
                                (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * u ** 3) for c in range(3)))
    return out


def interp_profile(prof, z):
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / max(1e-6, z1 - z0)
            return r0 + (r1 - r0) * t
    return prof[0][0] if z < prof[0][1] else prof[-1][0]


def std_profile(hem_r=0.25, hz=-0.095):
    return [(hem_r, hz), (hem_r - 0.012, hz + 0.08), (0.212, 0.10), (0.208, 0.22), (0.195, 0.31),
            (0.155, 0.39), (0.07, 0.45), (0.0, 0.46)]


def quilted_profile(prof, step=0.075, amp=0.05, z0=None):
    """Puffer-jacket profile: bulges between horizontal seams."""
    smooth = g.catmull(prof, 60)
    zmin, zmax = smooth[0][1], smooth[-1][1]
    z0 = zmin if z0 is None else z0
    out = []
    n = 90
    for k in range(n):
        z = zmin + (zmax - zmin) * k / (n - 1)
        r = interp_profile(smooth, z)
        t = ((z - z0) / step) % 1.0
        bulge = math.sin(PI * t) ** 0.6 if z < 0.40 else 0.0
        out.append((r * (1 + amp * bulge) if r > 0.02 else r, z))
    out[-1] = (0.0, out[-1][1])
    return out


def fuzz(bm, amp=0.01, f=23.0, seed=0.0):
    """Deterministic lumpy displacement along vertex normals (fur, knit)."""
    bm.normal_update()
    for v in bm.verts:
        x, y, z = v.co
        nz = (math.sin(f * x + seed) * math.sin(f * 1.13 * y + 2.0 * seed) * math.cos(f * 0.91 * z + 1.7)
              + 0.5 * math.sin(f * 2.1 * (x + z) + 3.0 * seed))
        v.co += v.normal * amp * nz
    return bm


def sector_lathe(prof, keep_deg=70, seg=48, sy=0.86, center_deg=0.0):
    """Lathe that keeps only the sector |angle - centre| < keep_deg (aprons)."""
    bm = g.bm_lathe(prof, seg=seg, sy=sy, smooth_n=0, cap_top=False, cap_bottom=False)
    kill = []
    for fc in bm.faces:
        c = fc.calc_center_median()
        ang = math.degrees(math.atan2(c.x, -c.y)) - center_deg
        ang = (ang + 180) % 360 - 180
        if abs(ang) > keep_deg:
            kill.append(fc)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    return bm


def mat_bands(name, colors, scale=9.0, wobble=0.10, wfreq=26.0, rough=0.8):
    """Folk-pattern coat: horizontal zigzag colour bands (object Z + sin(X,Y))."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    p.inputs['Roughness'].default_value = rough
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])

    def op(o, a, b=None, v=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = o
        if isinstance(a, float):
            n.inputs[0].default_value = a
        else:
            nt.links.new(a, n.inputs[0])
        if b is not None:
            if isinstance(b, float):
                n.inputs[1].default_value = b
            else:
                nt.links.new(b, n.inputs[1])
        return n.outputs[0]
    xy = op('ADD', sep.outputs['X'], op('MULTIPLY', sep.outputs['Y'], 0.7))
    zig = op('MULTIPLY', op('ABSOLUTE', op('SINE', op('MULTIPLY', xy, wfreq))), wobble)
    zz = op('ADD', sep.outputs['Z'], zig)
    fr = op('FRACT', op('MULTIPLY', zz, scale / len(colors)))
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    k = len(colors)
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*bc.srgb_to_linear(colors[0]), 1)
    cr.elements[1].position = 1.0 / k
    cr.elements[1].color = (*bc.srgb_to_linear(colors[1]), 1)
    for i in range(2, k):
        e = cr.elements.new(i / k)
        e.color = (*bc.srgb_to_linear(colors[i]), 1)
    nt.links.new(fr, ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m


def ho(rig, name, bm, mat, loc=(0, 0, 0), rot=None):
    return cb.head_obj(rig, name, bm, mat, loc=loc, rot=rot)


def face_obj(rig, name, bm, mat):
    return vf._obj(rig, name, bm, mat)


def round_glasses(rig, color, r=0.068, out=0.024, lens_tint=None):
    eu, ev = 0.116, -0.030
    fm = M('glasses', color, rough=0.3, metal=0.5)
    objs = []
    for s in (-1, 1):
        objs.append(face_obj(rig, 'glass_rim', vf.bm_stroke(vf.ellipse(s * eu, ev, r, r * 0.95, 24), 0.0085,
                                                            thick=0.012, closed=True, n=40, out=out), fm))
        objs.append(face_obj(rig, 'glass_glint', vf.bm_stroke([(s * eu - r * 0.55, ev + r * 0.05),
                                                               (s * eu - r * 0.15, ev + r * 0.55)], 0.006,
                                                              thick=0.006, out=out + 0.004),
                             M('glint', '#FFFFFF', rough=0.2, emission='#FFFFFF', emission_strength=1.2)))
        # temple arm to the ear
        p0, _ = vf.surf(s * (eu + r), ev, out)
        p1 = cb.head_point(s * PI / 2 * 0.92, -0.04, out=0.02)[0]
        objs.append(ho(rig, 'glass_arm', g.bm_tube_path([p0, (p0 + p1) / 2 + Vector((0, 0, 0.01)), p1], 0.007,
                                                        segr=6), fm))
    objs.append(face_obj(rig, 'glass_bridge', vf.bm_stroke(vf.arc(0, ev + 0.012, eu - r, 0.25, PI - 0.25, 7,
                                                                  ry=0.016), 0.0075, thick=0.010, out=out), fm))
    return objs


def scarf_ring(rig, color, stripe=None, R=0.135, r=0.068, dz=0.10):
    sm = M('scarf', color, rough=0.92)
    g.mesh_obj('scarf', fuzz(g.bm_ring(R, r, seg=48, segr=12, sy=0.92), 0.003, 40.0), sm, rig.j['chest'],
               loc=(0, 0.01, dz))
    if stripe:
        st = M('scarf_s', stripe, rough=0.92)
        g.mesh_obj('scarf_s', g.bm_ring(R, r + 0.002, seg=48, segr=12, sy=0.92, rz=0.28), st, rig.j['chest'],
                   loc=(0, 0.01, dz))
    return sm


def striped_tail(rig, parent, pts, width, colors, name='scarf_tail', seg_len=0.05, thick=0.035):
    """Flat scarf tail along chest-local points, alternating stripe colours."""
    pts = [Vector(p) for p in pts]
    dense = []
    for a, b in zip(pts, pts[1:]):
        n = max(2, int((b - a).length / 0.01))
        for k in range(n):
            dense.append(a.lerp(b, k / n))
    dense.append(pts[-1])
    # split into stripe segments
    total = 0.0
    seg = [dense[0]]
    idx = 0
    out = []
    for p, q in zip(dense, dense[1:]):
        total += (q - p).length
        seg.append(q)
        if total >= seg_len:
            out.append((seg, colors[idx % len(colors)]))
            idx += 1
            seg = [q]
            total = 0.0
    if len(seg) > 1:
        out.append((seg, colors[idx % len(colors)]))
    objs = []
    for k, (sp, col) in enumerate(out):
        if len(sp) < 2:
            continue
        bm = g.bm_tube_path(sp, thick / 2, segr=10, side_ref=(1, 0, 0), flat=width / (thick / 2))
        objs.append(g.mesh_obj(name, bm, M('scarf_' + col, col, rough=0.92), parent))
    # fringe at the end
    end = dense[-1]
    d = (dense[-1] - dense[-4]).normalized()
    for k in range(4):
        off = Vector(((k - 1.5) * width * 0.55, 0, 0))
        objs.append(g.mesh_obj(name + '_fr', g.bm_tube_path([end + off, end + off + d * 0.03], 0.007, segr=5),
                               M('scarf_' + colors[0], colors[0], rough=0.92), parent))
    return objs


def pompom(rig, color, loc, r=0.085):
    return ho(rig, 'pompom', g.bm_ring(0.0, r, seg=24, segr=14, tufts=6, bump=0.28, seed=2.0), M('pompom', color,
                                                                                                  rough=0.95), loc=loc)


def bow_ribbon(rig, color, loc, rot=(0, 0, 0), s=1.0):
    m = M('ribbon', color, rough=0.45)
    e = g.empty('bow', rig.j['head'], (loc[0], loc[1], loc[2] + HEAD_C))
    e.rotation_mode = 'XYZ'
    e.rotation_euler = [math.radians(a) for a in rot]
    for sx in (-1, 1):
        g.mesh_obj('bow_loop', g.bm_ellipsoid(0.055 * s, 0.022 * s, 0.040 * s, 14, 8), m, e,
                   loc=(sx * 0.05 * s, 0, 0.004), rot=(0, sx * -18, 0))
        g.mesh_obj('bow_tail', g.bm_ellipsoid(0.018 * s, 0.012 * s, 0.045 * s, 10, 6), m, e,
                   loc=(sx * 0.022 * s, 0.004, -0.045 * s), rot=(0, sx * 25, 0))
    g.mesh_obj('bow_knot', g.bm_ellipsoid(0.024 * s, 0.022 * s, 0.024 * s, 10, 8), m, e)
    return e


# --------------------------------------------------------------------------- hand props

def make_snowball(rig):
    ob = g.mesh_obj('snowball', fuzz(g.bm_ellipsoid(0.062, 0.062, 0.058, 20, 12), 0.004, 40.0),
                    M('snowball', '#F4F7FB', rough=0.7, emission='#FFFFFF', emission_strength=0.12),
                    rig.j['hand_R'], loc=(0.0, -0.045, -0.02))
    rig.toggle('snowball', [ob])
    return ob


def make_cane(rig):
    wood = M('cane', '#8A5A33', rough=0.5)
    shaft = g.tube_between('cane_shaft', wood, radius=0.017, seg=10)
    tip = g.mesh_obj('cane_tip', g.bm_ellipsoid(0.022, 0.022, 0.018, 10, 6), M('cane_tip', '#3A2A22', rough=0.6))
    # crook: arc in the local YZ plane, starting at the grip, curling forward (-Y)
    pts = [(0, 0, 0)] + [(0, -0.05 + 0.05 * math.cos(a), 0.05 * math.sin(a) + 0.0)
                         for a in [PI * k / 8 for k in range(0, 9)]][1:]
    pts = [(0.0, 0.0, -0.01)] + [(0.0, -0.05 + 0.05 * math.cos(a), 0.05 * math.sin(a)) for a in
                                 [PI * k / 8 for k in range(0, 10)]]
    crook = g.mesh_obj('cane_crook', g.bm_tube_path(pts, 0.018, segr=10), wood)
    objs = [shaft, tip, crook]
    rig.toggle('cane', objs)
    rig.toggle('cane_hold', objs)

    def update(r):
        if shaft.hide_render:
            return
        shown = r.state.get('_show', set())
        hand = r.world('hand_R')
        root = r.j['root'].matrix_world
        fwd = (root.to_3x3() @ Vector((0, -1, 0))).normalized()
        right = (root.to_3x3() @ Vector((-1, 0, 0))).normalized()
        if 'cane_hold' in shown and 'cane' not in shown:
            el = r.world('el_R')
            d = (hand - el).normalized()
            top = hand - d * 0.02
            bot = hand + d * 0.50
            up = -d
        else:
            top = hand + Vector((0, 0, 0.005))
            bot = Vector((top.x, top.y, 0.0)) + fwd * 0.05 + right * 0.02
            up = (top - bot).normalized()
        g.set_tube(shaft, bot, top)
        tip.matrix_world = Matrix.Translation(bot)
        zx = up
        xx = right - zx * right.dot(zx)
        if xx.length < 1e-4:
            xx = fwd.cross(zx)
        xx.normalize()
        yy = zx.cross(xx)
        # make the crook curl toward the character's front
        if yy.dot(fwd) > 0:
            xx, yy = -xx, -yy
        m = Matrix((xx, yy, zx)).transposed().to_4x4()
        crook.matrix_world = Matrix.Translation(top) @ m
    rig.strings.append(update)
    return objs


def build_lute(parent, name, loc, rot):
    """Small lute; soundboard faces local -Y, neck along +Z."""
    e = g.empty(name, parent, loc)
    e.rotation_mode = 'XYZ'
    e.rotation_euler = [math.radians(a) for a in rot]
    wood = M('lute_wood', '#C98F55', rough=0.5)
    dark = M('lute_dark', '#8A5A33', rough=0.5)
    top = M('lute_top', '#EBC690', rough=0.55)
    objs = []
    body = g.bm_ellipsoid(0.115, 0.06, 0.145, 24, 14)
    for v in body.verts:
        if v.co.y < 0:
            v.co.y *= 0.35                     # flat soundboard
    objs.append(g.mesh_obj(name + '_body', body, dark, e))
    objs.append(g.mesh_obj(name + '_board', g.bm_ellipsoid(0.108, 0.012, 0.138, 24, 10), top, e,
                           loc=(0, -0.016, 0.0)))
    objs.append(g.mesh_obj(name + '_hole', g.bm_ellipsoid(0.034, 0.006, 0.034, 16, 8),
                           M('lute_hole', '#3A2418', rough=0.6), e, loc=(0, -0.027, 0.04)))
    objs.append(g.mesh_obj(name + '_bridge', g.bm_box(0.06, 0.012, 0.012, bevel=0.003), dark, e,
                           loc=(0, -0.028, -0.07)))
    objs.append(g.mesh_obj(name + '_neck', g.bm_box(0.040, 0.026, 0.22, bevel=0.006), wood, e,
                           loc=(0, -0.006, 0.245)))
    objs.append(g.mesh_obj(name + '_peg', g.bm_box(0.046, 0.024, 0.075, bevel=0.008), dark, e,
                           loc=(0, 0.02, 0.38), rot=(-30, 0, 0)))
    for k in (-1, 1):
        objs.append(g.mesh_obj(name + '_pegs', g.bm_ellipsoid(0.012, 0.012, 0.012, 8, 6),
                               M('lute_pegs', '#F2E6D0', rough=0.5), e, loc=(k * 0.032, 0.02, 0.38)))
    sm = M('lute_str', '#F4F1EA', rough=0.4)
    for k in (-1, 0, 1):
        objs.append(g.mesh_obj(name + '_str', g.bm_tube_path([(k * 0.010, -0.026, -0.07), (k * 0.008, -0.022, 0.35)],
                                                             0.0028, segr=4), sm, e))
    return objs


def make_lute(rig):
    front = build_lute(rig.j['chest'], 'lute_f', (-0.05, -0.27, -0.21), (8, 50, 0))
    back = build_lute(rig.j['chest'], 'lute_b', (0.03, 0.31, -0.13), (-10, -40, 180))
    rig.toggle('lute_front', front)
    rig.toggle('lute_back', back)


def make_shades(rig):
    lens = M('shade_lens', '#24202E', rough=0.12)
    frame = M('shade_frame', '#F2456A', rough=0.3)
    glint = M('glint', '#FFFFFF', rough=0.2, emission='#FFFFFF', emission_strength=1.2)
    sets = {}
    for tog, dv, out in (('shades', 0.0, 0.026), ('shades_up', 0.150, 0.075)):
        objs = []
        eu, ev = 0.116, -0.030 + dv
        for s in (-1, 1):
            rr = vf._round_rect(s * eu, ev, 0.078, 0.060, n=6)
            objs.append(face_obj(rig, tog + '_lens', vf.bm_blob(rr, thick=0.012, out=out), lens))
            objs.append(face_obj(rig, tog + '_rim', vf.bm_stroke(rr, 0.0085, thick=0.014, closed=True, n=40,
                                                                 out=out + 0.002), frame))
            objs.append(face_obj(rig, tog + '_glint', vf.bm_stroke([(s * eu - 0.045, ev + 0.012),
                                                                    (s * eu - 0.012, ev + 0.042)], 0.0075,
                                                                   thick=0.006, out=out + 0.012), glint))
        objs.append(face_obj(rig, tog + '_bridge', vf.bm_stroke([(-0.040, ev + 0.02), (0.0, ev + 0.03),
                                                                 (0.040, ev + 0.02)], 0.008, thick=0.012,
                                                                out=out), frame))
        sets[tog] = objs
        rig.toggle(tog, objs)
    return sets


# --------------------------------------------------------------------------- characters

def dress_kid_boy(rig, spec):
    hair = spec['hair']
    cb.hair_shell(rig, hair, fringe=0.34, wave=0.07, waves=11.0, sweep=0.06, back_low=-0.45)
    red = M('beanie', '#D9483B', rough=0.92)
    cb.cap_shell(rig, red, lambda x, y: 0.22 - 0.22 * y, base=1.13, puff=0.30, name='beanie', lumps=0.03)
    cb.tilted_ring(rig, 'beanie_cuff', M('beanie_cuff', '#F4EDE0', rough=0.92), HEAD_R[0] * 1.07, 0.046, 0.44,
                   0.0, sy=0.97, rz=1.2)
    pompom(rig, '#F4EDE0', (0.0, 0.02, 0.405), r=0.09)
    # stand-up collar + hood at the back of the puffer
    coat = spec['coat_mat']
    g.mesh_obj('collar', g.bm_ring(0.14, 0.055, seg=48, segr=12, sy=0.92, rz=1.2), coat, rig.j['chest'],
               loc=(0, 0.01, 0.10))
    g.mesh_obj('hood', g.bm_ellipsoid(0.17, 0.10, 0.12, 24, 12), coat, rig.j['chest'], loc=(0, 0.19, 0.06),
               rot=(-25, 0, 0))
    zipm = M('zip', '#F2C230', rough=0.4, metal=0.3)
    g.mesh_obj('zip', g.bm_box(0.014, 0.012, 0.34, bevel=0.004), zipm, rig.j['spine'], loc=(0, -0.193, 0.13))
    g.mesh_obj('zip_pull', g.bm_box(0.02, 0.012, 0.035, bevel=0.005), zipm, rig.j['spine'], loc=(0, -0.20, 0.28))


def dress_kid_girl(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.42)
    cb.hair_shell(rig, hair, fringe=0.36, wave=0.10, waves=12.0, sweep=0.0, back_low=-0.55, top_puff=0.06)
    for s in (-1, 1):
        # high side pigtails: tie, then a fat curl hanging down
        base = (s * 0.29, 0.06, 0.12)
        ho(rig, 'pigtail_root', g.bm_ellipsoid(0.06, 0.055, 0.06, 14, 8), hm, loc=base)
        pts = [(s * 0.33, 0.07, 0.10), (s * 0.40, 0.08, 0.02), (s * 0.41, 0.07, -0.10), (s * 0.37, 0.06, -0.20)]
        ho(rig, 'pigtail', g.bm_tube_path(pts, lambda t: 0.072 - 0.035 * t ** 1.5, segr=14), hm)
        bow_ribbon(rig, '#E8435A', (s * 0.31, 0.04, 0.17), rot=(0, s * -35, s * 20), s=1.0)
        # earmuffs: fluffy ball over each ear
        ho(rig, 'earmuff', g.bm_ring(0.0, 0.075, seg=24, segr=14, tufts=6, bump=0.3, seed=3.0 + s),
           M('earmuff', '#F4F1EA', rough=0.95), loc=(s * 0.315, 0.0, -0.06))
    band = [cb.head_point(s * a, 0.0, out=0.035)[0] for s, a in ((-1, PI / 2),)]
    pts = []
    for k in range(11):
        t = -PI / 2 + PI * k / 10
        pts.append((math.sin(t) * HEAD_R[0] * 1.12, 0.02, math.cos(t) * HEAD_R[2] * 1.16 - 0.03))
    ho(rig, 'earmuff_band', g.bm_tube_path(pts, 0.016, segr=8), M('earmuff_band', '#E8435A', rough=0.5))
    del band
    btn = M('button', '#F4F1EA', rough=0.4)
    for z in (0.05, 0.15, 0.25):
        g.mesh_obj('button', g.bm_ellipsoid(0.02, 0.010, 0.02, 10, 6), btn, rig.j['spine'],
                   loc=cb.front_point(z, 0.212 if z < 0.15 else 0.205))
    cb.collar_fur(rig, spec, R=0.14, r=0.065, dz=0.10, bump=0.42, tufts=10)


def dress_prankster(rig, spec):
    hoodm = spec['coat_mat']
    lining = M('lining', '#F6D9A8', rough=0.9)
    hair = spec['hair']
    hm = M('hair', hair, rough=0.42)
    # messy bangs peeking out of the hood
    for az, el, tl in ((-0.30, 0.52, -62), (0.0, 0.56, -72), (0.30, 0.52, -62)):
        cb.hair_tuft(rig, hair, az, el, size=(0.05, 0.035, 0.07), tilt=(tl, 0, 0))

    def hood(x, y, z):
        face = smoothstep(0.02, 0.42, -y) * smoothstep(-0.98, -0.62, z) * \
            (1 - smoothstep(0.44, 0.60, z)) * (1 - smoothstep(0.70, 0.88, abs(x)))
        f = 1.17 - 0.32 * face
        return f * (1.0 + 0.06 * max(0.0, z) ** 2)
    cb.shell(rig, hoodm, hood, 'hood')
    ring = g.bm_ring(0.238, 0.030, seg=56, segr=12, sy=1.0)
    ho(rig, 'hood_rim', ring, lining, loc=(0, -0.188, -0.01), rot=(76, 0, 0))
    for s in (-1, 1):
        p, n = cb.head_point(s * 0.62, 0.78, out=0.03, radii=tuple(r * 1.15 for r in HEAD_R))
        q = n.to_track_quat('Z', 'Y')
        ho(rig, 'bear_ear', g.bm_ellipsoid(0.100, 0.050, 0.094, 18, 10), hoodm, loc=(p.x, p.y, p.z), rot=q)
        pi_ = p + n * 0.01 + Vector((0, -0.03, 0))
        ho(rig, 'bear_ear_in', g.bm_ellipsoid(0.060, 0.022, 0.056, 14, 8), lining, loc=(pi_.x, pi_.y, pi_.z), rot=q)
    # kangaroo pocket + drawstrings
    g.mesh_obj('pocket', sector_lathe([(0.226, 0.02), (0.218, 0.16)], keep_deg=48, sy=0.86),
               M('pocket', '#D97430', rough=0.9), rig.j['spine'])
    for s in (-1, 1):
        g.mesh_obj('string', g.bm_tube_path([(s * 0.04, -0.17, 0.43), (s * 0.045, -0.20, 0.36),
                                             (s * 0.05, -0.20, 0.27)], 0.008, segr=6), lining, rig.j['spine'])
        g.mesh_obj('string_end', g.bm_ellipsoid(0.014, 0.014, 0.02, 8, 6), lining, rig.j['spine'],
                   loc=(s * 0.05, -0.20, 0.26))
    # band-aid on the viewer-left cheek
    ba = vf._round_rect(-0.165, -0.040, 0.050, 0.020, n=5)
    rot = [(-0.165 + (u + 0.165) * math.cos(0.5) - (v + 0.04) * math.sin(0.5),
            -0.040 + (u + 0.165) * math.sin(0.5) + (v + 0.04) * math.cos(0.5)) for u, v in ba]
    face_obj(rig, 'bandaid', vf.bm_blob(rot, thick=0.008, out=0.0, edge=0.7), M('bandaid', '#EDC497', rough=0.7))
    face_obj(rig, 'bandaid_pad', vf.bm_blob(vf.ellipse(-0.165, -0.040, 0.016, 0.014, 12), thick=0.006, out=0.006),
             M('bandaid_pad', '#F7E3C8', rough=0.7))


def dress_teen_girl(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.42)
    cb.hair_shell(rig, hair, fringe=0.34, wave=0.06, waves=10.0, sweep=0.18, back_low=-0.30, top_puff=0.05)
    # side locks framing the face
    for s in (-1, 1):
        pts = [(s * 0.27, -0.06, 0.02), (s * 0.29, -0.08, -0.10), (s * 0.27, -0.09, -0.20)]
        ho(rig, 'sidelock', g.bm_tube_path(pts, lambda t: 0.035 - 0.018 * t, segr=10), hm)
    # high ponytail: scrunchie + long swinging tail down the back
    ho(rig, 'scrunchie', g.bm_ring(0.045, 0.024, seg=24, segr=8, tufts=5, bump=0.3), M('scrunchie', '#F08A8A',
                                                                                      rough=0.8),
       loc=(0, 0.25, 0.20), rot=(-60, 0, 0))
    pts = [(0, 0.26, 0.22), (0, 0.36, 0.20), (0.02, 0.42, 0.06), (0.03, 0.42, -0.10), (0.04, 0.38, -0.28),
           (0.06, 0.34, -0.40)]
    ho(rig, 'ponytail', g.bm_tube_path(catmull3(pts, 20), lambda t: 0.070 * (1 - 0.75 * t ** 1.3) + 0.012,
                                       segr=14), hm)
    # long striped scarf: ring + front tail + tail over the shoulder
    scarf_ring(rig, '#F4EDE0', stripe='#F08A8A', R=0.135, r=0.07, dz=0.10)
    cols = ['#F4EDE0', '#F08A8A']
    striped_tail(rig, rig.j['chest'], [(0.07, -0.17, 0.08), (0.08, -0.215, -0.02), (0.085, -0.235, -0.16),
                                       (0.09, -0.245, -0.28)], 0.045, cols)
    striped_tail(rig, rig.j['chest'], [(-0.10, 0.10, 0.13), (-0.13, 0.20, 0.06), (-0.12, 0.25, -0.06),
                                       (-0.10, 0.27, -0.20)], 0.045, cols)
    cb.belt(rig, '#5E3F8A', z=0.08, buckle=None, width=0.45)
    btn = M('button', '#F2C14E', rough=0.35, metal=0.4)
    for z in (0.14, 0.24):
        for s in (-1, 1):
            g.mesh_obj('button', g.bm_ellipsoid(0.016, 0.010, 0.016, 10, 6), btn, rig.j['spine'],
                       loc=(s * 0.05, -0.178, z))


def dress_young_man(rig, spec):
    hair = spec['hair']
    cb.hair_shell(rig, hair, fringe=0.36, wave=0.10, waves=13.0, sweep=0.10, back_low=-0.45, top_puff=0.10)
    # anime spikes all over the top and back
    spikes = [(0.0, 1.20, -20), (-0.6, 0.95, 0), (0.6, 0.95, 0), (-1.2, 0.70, 10), (1.2, 0.70, 10),
              (2.0, 0.65, 30), (-2.0, 0.65, 30), (2.7, 0.55, 40), (-2.7, 0.55, 40), (PI, 0.45, 50),
              (2.6, 0.05, 70), (-2.6, 0.05, 70), (PI, -0.15, 80), (-0.3, 0.55, -50), (0.35, 0.55, -50),
              (0.0, 0.62, -55)]
    for k, (az, el, tl) in enumerate(spikes):
        big = 1.0 if abs(az) < 2.2 else 0.85
        cb.hair_tuft(rig, hair, az, el, size=(0.06 * big, 0.045 * big, 0.15 * big), tilt=(tl, 0, 0), name='spike')
    coat = spec['coat_mat']
    rib = M('rib', '#3F5530', rough=0.9)
    g.mesh_obj('hem_rib', g.bm_ring(0.232, 0.032, seg=56, segr=10, sy=0.86, rz=1.3), rib, rig.j['spine'],
               loc=(0, 0, -0.07))
    for nm in ('R', 'L'):
        g.mesh_obj('cuff_rib', g.bm_ring(0.058, 0.024, seg=28, segr=8, rz=1.3), rib, rig.j['el_' + nm],
                   loc=(0, 0, -cb.FOREARM + 0.016))
    # ribbed bomber collar + chunky scarf
    g.mesh_obj('collar_rib', g.bm_ring(0.13, 0.03, seg=48, segr=8, sy=0.92, rz=1.4), rib, rig.j['chest'],
               loc=(0, 0.01, 0.085))
    scarf_ring(rig, '#C8463D', stripe='#F4EDE0', R=0.132, r=0.066, dz=0.11)
    striped_tail(rig, rig.j['chest'], [(-0.06, -0.15, 0.12), (-0.075, -0.205, 0.02), (-0.08, -0.22, -0.10)],
                 0.042, ['#C8463D', '#C8463D', '#F4EDE0'], seg_len=0.04)
    zipm = M('zip', '#B9C2CE', rough=0.35, metal=0.6)
    g.mesh_obj('zip', g.bm_box(0.012, 0.012, 0.30, bevel=0.004), zipm, rig.j['spine'], loc=(0.0, -0.19, 0.10))
    g.mesh_obj('patch', g.bm_box(0.06, 0.012, 0.045, bevel=0.006), M('patch', '#F2C14E', rough=0.6),
               rig.j['sh_L'], loc=(0.06, -0.01, -0.05), rot=(0, 90, 0))


def dress_aunt(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.42)
    cb.hair_shell(rig, hair, fringe=0.40, wave=0.05, waves=8.0, sweep=-0.25, back_low=-0.40, top_puff=0.12)
    ho(rig, 'bun', fuzz(g.bm_ellipsoid(0.13, 0.12, 0.11, 20, 12), 0.006, 30.0), hm, loc=(0, 0.10, 0.31))
    ho(rig, 'bun_band', g.bm_ring(0.10, 0.018, seg=32, segr=8), M('scrunchie', '#E07A7A', rough=0.7),
       loc=(0, 0.09, 0.26), rot=(-15, 0, 0))
    # apron: bib + skirt panel + pocket + straps
    apron = M('apron', '#FBF6EC', rough=0.85)
    trim = M('apron_trim', '#E07A7A', rough=0.8)
    hem_r = spec.get('hem_r', 0.25)
    prof = [(hem_r + 0.018, spec.get('hem_z', -0.2) + 0.01), (0.232, 0.0), (0.222, 0.10), (0.219, 0.14)]
    g.mesh_obj('apron', sector_lathe(prof, keep_deg=55, sy=0.88), apron, rig.j['spine'])
    g.mesh_obj('apron_hem', sector_lathe([(hem_r + 0.022, spec.get('hem_z', -0.2) + 0.006),
                                          (hem_r + 0.022, spec.get('hem_z', -0.2) + 0.03)], keep_deg=56, sy=0.88),
               trim, rig.j['spine'])
    g.mesh_obj('apron_bib', sector_lathe([(0.214, 0.12), (0.212, 0.22), (0.200, 0.30)], keep_deg=34, sy=0.88),
               apron, rig.j['spine'])
    g.mesh_obj('apron_pocket', sector_lathe([(0.240, -0.07), (0.236, 0.0)], keep_deg=22, sy=0.88), trim,
               rig.j['spine'])
    cb.belt(rig, '#E07A7A', z=0.13, r=0.215, buckle=None, width=0.4)
    for s in (-1, 1):
        g.mesh_obj('apron_strap', g.bm_tube_path([(s * 0.07, -0.18, 0.30), (s * 0.09, -0.12, 0.40),
                                                  (s * 0.10, 0.0, 0.43)], 0.012, segr=6), apron, rig.j['spine'])
    g.mesh_obj('collar', g.bm_ring(0.125, 0.03, seg=48, segr=8, sy=0.92, rz=1.2), M('apron_trim', '#E07A7A',
                                                                                rough=0.8),
               rig.j['chest'], loc=(0, 0.01, 0.09))


def dress_uncle(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.42)
    cb.hair_shell(rig, hair, fringe=0.42, wave=0.04, waves=8.0, sweep=0.0, back_low=-0.45)
    # flat cap (newsboy): puffy crown leaning forward + short brim
    cap = M('cap', '#7A6A58', rough=0.92)
    cb.cap_shell(rig, cap, lambda x, y: 0.28 - 0.16 * y, base=1.12, puff=0.10, name='cap_base', soft=0.03)
    crown = g.bm_ellipsoid(0.33, 0.335, 0.12, 32, 14)
    ho(rig, 'cap_crown', fuzz(crown, 0.003, 30.0), cap, loc=(0, -0.035, 0.205), rot=(-10, 0, 0))
    ho(rig, 'cap_button', g.bm_ellipsoid(0.03, 0.03, 0.02, 10, 6), cap, loc=(0, -0.05, 0.325))
    brim = g.bm_lathe([(0.0, 0.0), (0.16, 0.0), (0.17, -0.008), (0.0, -0.012)], seg=32, sx=1.0, sy=0.6)
    ho(rig, 'cap_brim', brim, M('cap_brim', '#6A5A48', rough=0.9), loc=(0, -0.26, 0.135), rot=(-14, 0, 0))
    # bushy moustache + brows
    sm = M('stache', hair, rough=0.8)
    for s in (-1, 1):
        cb.on_head('stache', fuzz(g.bm_ellipsoid(0.068, 0.034, 0.036, 14, 8), 0.004, 50.0), sm, rig.j['head'],
                   s * 0.13, -0.235, out=0.002, tilt=-s * 18)
    # checked vest over a shirt
    vest = spec['vest_mat']
    g.mesh_obj('vest', cb.vest_lathe([(0.262, -0.07), (0.256, 0.05), (0.236, 0.15), (0.222, 0.24),
                                      (0.206, 0.31), (0.165, 0.38)], gap_deg=22, seg=44, sy=0.88), vest,
               rig.j['spine'])
    btn = M('button', '#3B2A20', rough=0.4)
    for z in (0.0, 0.08, 0.16):
        g.mesh_obj('button', g.bm_ellipsoid(0.016, 0.010, 0.016, 10, 6), btn, rig.j['spine'],
                   loc=(0.085, -0.232 + 0.06 * (z / 0.16) * 0.2, z))
    g.mesh_obj('tie', g.bm_box(0.04, 0.012, 0.13, bevel=0.008), M('tie', '#C8463D', rough=0.6), rig.j['spine'],
               loc=(0, -0.196, 0.31), rot=(-10, 0, 0))
    g.mesh_obj('belly', g.bm_ellipsoid(0.18, 0.12, 0.16, 24, 12), spec['coat_mat'], rig.j['spine'],
               loc=(0, -0.10, 0.05))
    cb.belt(rig, '#4A3020', z=-0.05, r=0.255, buckle='#C9A045', width=0.5)


def dress_grandma(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.45)
    cb.hair_shell(rig, hair, fringe=0.42, wave=0.03, waves=2.0, sweep=0.0, back_low=-0.35, top_puff=0.06,
                  base=1.08)
    # centre part: two smooth swept sides (thin darker line)
    ho(rig, 'part', g.bm_tube_path([cb.head_point(0, el, out=0.028)[0] for el in (0.55, 0.85, 1.15)], 0.006,
                                   segr=6), M('part', '#9A9690', rough=0.5))
    ho(rig, 'bun', fuzz(g.bm_ellipsoid(0.11, 0.09, 0.10, 20, 12), 0.005, 30.0), hm, loc=(0, 0.30, -0.02))
    pin = M('hairpin', '#C9A045', rough=0.3, metal=0.6)
    ho(rig, 'hairpin', g.bm_tube_path([(-0.15, 0.31, 0.03), (0.15, 0.32, -0.05)], 0.008, segr=6), pin)
    ho(rig, 'hairpin_end', g.bm_ellipsoid(0.02, 0.02, 0.02, 8, 6), M('pin_bead', '#C8463D', rough=0.3),
       loc=(0.16, 0.32, -0.055))
    round_glasses(rig, '#C9A045', r=0.070)
    # knitted shawl: capelet over the shoulders with a scalloped hem + tassel knot
    shawl = M('shawl', '#F2E6D0', rough=0.95)
    prof = [(0.29, -0.11), (0.28, -0.05), (0.25, 0.02), (0.20, 0.08), (0.14, 0.12), (0.12, 0.13)]
    bm = g.bm_lathe(prof, seg=48, sy=0.92, smooth_n=14, cap_top=False, cap_bottom=False)
    for v in bm.verts:
        a = math.atan2(v.co.x, -v.co.y)
        if v.co.z < -0.08:
            v.co.z -= 0.03 * (0.5 + 0.5 * math.cos(9 * a)) + 0.07 * max(0.0, math.cos(a)) ** 6
    fuzz(bm, 0.004, 45.0)
    g.mesh_obj('shawl', bm, shawl, rig.j['chest'])
    rose = M('shawl_rose', '#C26A7A', rough=0.95)
    g.mesh_obj('shawl_stripe', g.bm_lathe([(0.262, -0.035), (0.247, 0.0)], seg=48, sy=0.92, cap_top=False,
                                          cap_bottom=False), rose, rig.j['chest'])
    g.mesh_obj('brooch', g.bm_ellipsoid(0.03, 0.014, 0.03, 12, 8), M('brooch', '#C8463D', rough=0.3),
               rig.j['chest'], loc=(0, -0.205, 0.05))


def dress_grandpa(rig, spec):
    white = spec['hair']
    wm = M('hair', white, rough=0.75)

    # bald crown; white hair only around the sides/back below the ears' top
    def side_hair(x, y, z):
        band = (1 - smoothstep(0.05, 0.25, z)) * smoothstep(-0.75, -0.45, z) * smoothstep(-0.35, 0.05, y)
        f = 0.92 + (1.13 - 0.92) * band
        return f
    cb.shell(rig, wm, side_hair, 'side_hair')
    for s in (-1, 1):
        for az, el in ((0.85 * PI / 2 * 2 * 0.5 + 0.55, 0.08), (1.95, 0.0)):
            cb.on_head('hair_puff', fuzz(g.bm_ellipsoid(0.06, 0.05, 0.065, 14, 8), 0.006, 40.0), wm, rig.j['head'],
                       s * az, el, out=0.02)
    # long white beard: jaw shell + hanging point down onto the chest
    cb.beard(rig, white, edge=-0.40, curve=0.30, base=1.14, chin=0.18)
    ho(rig, 'beard_long', fuzz(g.bm_lathe([(0.0, -0.40), (0.06, -0.36), (0.12, -0.25), (0.14, -0.16),
                                           (0.12, -0.10), (0.0, -0.08)], seg=20, sy=0.6, smooth_n=12),
                               0.006, 35.0), wm, loc=(0, -0.20, -0.06), rot=(14, 0, 0))
    for s in (-1, 1):
        cb.on_head('stache', fuzz(g.bm_ellipsoid(0.068, 0.032, 0.030, 14, 8), 0.004, 50.0), wm, rig.j['head'],
                   s * 0.16, -0.215, out=0.006, tilt=-s * 26)
    # long coat details: lapels, buttons, scarf
    btn = M('button', '#4A3020', rough=0.4)
    for z in (-0.10, 0.0, 0.10, 0.20):
        g.mesh_obj('button', g.bm_ellipsoid(0.018, 0.010, 0.018, 10, 6), btn, rig.j['spine'],
                   loc=(0.04, -0.188 - 0.012 * (z < 0), z))
    scarf_ring(rig, '#4F7A3A', stripe='#E8DCC0', R=0.13, r=0.06, dz=0.10)
    make_cane(rig)


def dress_merchant(rig, spec):
    hair = spec['hair']
    cb.hair_shell(rig, hair, fringe=0.30, wave=0.04, waves=8.0, sweep=0.0, back_low=-0.45)
    furm = M('furhat', '#6E4A30', rough=0.98)
    hat = g.bm_lathe([(0.31, 0.0), (0.33, 0.08), (0.335, 0.20), (0.30, 0.27), (0.0, 0.29)], seg=40, smooth_n=14,
                     cap_bottom=False)
    fuzz(hat, 0.012, 34.0, seed=1.0)
    ho(rig, 'furhat', hat, furm, loc=(0, 0.0, 0.16), rot=(-6, 0, 0))
    cb.tilted_ring(rig, 'furhat_rim', furm, HEAD_R[0] * 1.06, 0.06, 0.62, 0.42, sy=1.0, tufts=12, bump=0.35,
                   seed=5.0)
    ho(rig, 'furhat_top', g.bm_ellipsoid(0.20, 0.20, 0.04, 24, 8), M('furhat_top', '#C8463D', rough=0.8),
       loc=(0, 0.0, 0.445), rot=(-6, 0, 0))
    # handlebar moustache with curled tips
    sm = M('stache', hair, rough=0.75)
    for s in (-1, 1):
        pts = [(s * 0.01, -0.272, -0.07), (s * 0.08, -0.26, -0.085), (s * 0.16, -0.225, -0.075),
               (s * 0.21, -0.19, -0.04), (s * 0.215, -0.18, -0.005), (s * 0.19, -0.19, 0.005)]
        ho(rig, 'handlebar', g.bm_tube_path(catmull3(pts, 16), lambda t: 0.036 * (1 - 0.72 * t) + 0.004,
                                            segr=10), sm)
    # sash + backpack
    cb.belt(rig, '#F2C14E', z=0.06, r=0.232, buckle=None, width=0.8)
    g.mesh_obj('sash_knot', g.bm_ellipsoid(0.045, 0.03, 0.04, 12, 8), M('belt', '#F2C14E', rough=0.55),
               rig.j['spine'], loc=(0.10, -0.20, 0.06))
    g.mesh_obj('sash_tail', g.bm_box(0.04, 0.015, 0.12, bevel=0.008), M('belt', '#F2C14E', rough=0.55),
               rig.j['spine'], loc=(0.12, -0.205, -0.01), rot=(0, -8, 0))
    pack = M('pack', '#8A5A33', rough=0.7)
    g.mesh_obj('backpack', g.bm_box(0.30, 0.16, 0.30, bevel=0.05, segs=4), pack, rig.j['chest'],
               loc=(0, 0.27, -0.10))
    g.mesh_obj('bedroll', g.bm_cyl(0.07, 0.07, 0.36, seg=16, centered=True), M('bedroll', '#3D7CC9', rough=0.9),
               rig.j['chest'], loc=(0, 0.28, 0.10), rot=(0, 90, 0))
    g.mesh_obj('pack_flap', g.bm_box(0.26, 0.02, 0.12, bevel=0.01), M('pack_d', '#6E4428', rough=0.7),
               rig.j['chest'], loc=(0, 0.355, -0.02))
    g.mesh_obj('pot', g.bm_lathe([(0.0, 0.0), (0.06, 0.0), (0.07, 0.07), (0.075, 0.08)], seg=16, cap_top=False),
               M('pot', '#9AA2AC', rough=0.35, metal=0.6), rig.j['chest'], loc=(0.17, 0.27, -0.20),
               rot=(0, 90, 0))
    for s in (-1, 1):
        g.mesh_obj('pack_strap', g.bm_tube_path([(s * 0.10, 0.14, 0.07), (s * 0.11, -0.05, 0.10),
                                                 (s * 0.12, -0.17, 0.02), (s * 0.12, -0.17, -0.12)], 0.014,
                                                segr=6), pack, rig.j['chest'])


def dress_herbalist(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.45)
    cb.hair_shell(rig, hair, fringe=0.34, wave=0.10, waves=9.0, sweep=-0.12, back_low=-0.55, top_puff=0.10)
    for az, el in ((2.5, 0.2), (-2.5, 0.2), (PI, 0.0), (2.8, -0.25), (-2.8, -0.25), (0.9, 0.85), (-0.7, 0.9)):
        cb.hair_tuft(rig, hair, az, el, size=(0.06, 0.045, 0.09), tilt=(120 if abs(az) > 1.5 else -40, 0, 0))
    round_glasses(rig, '#5A3A26', r=0.074)
    cloak = M('cloak', '#4F8A4A', rough=0.9)
    g.mesh_obj('cloak', cb.vest_lathe([(0.285, -0.10), (0.268, 0.04), (0.245, 0.17), (0.222, 0.29), (0.185, 0.37),
                                       (0.13, 0.43)], gap_deg=30, seg=44, sy=0.92), cloak, rig.j['spine'])
    g.mesh_obj('cloak_hood', fuzz(g.bm_ellipsoid(0.20, 0.12, 0.13, 24, 12), 0.002), cloak, rig.j['chest'],
               loc=(0, 0.21, 0.06), rot=(-28, 0, 0))
    g.mesh_obj('clasp', g.bm_ellipsoid(0.028, 0.014, 0.028, 12, 8), M('clasp', '#C9A045', rough=0.3, metal=0.6),
               rig.j['chest'], loc=(0, -0.175, 0.07))
    # herb satchel on the left hip + strap across the chest
    bag = M('satchel', '#8A6A3A', rough=0.7)
    g.mesh_obj('strap', g.bm_ring(0.215, 0.015, seg=64, segr=8, sy=0.86, rz=1.6), bag, rig.j['spine'],
               loc=(0, 0, 0.20), rot=(0, -38, 0))
    g.mesh_obj('satchel', g.bm_box(0.08, 0.17, 0.14, bevel=0.03), bag, rig.j['spine'], loc=(0.25, -0.02, 0.0),
               rot=(0, -8, 0))
    g.mesh_obj('satchel_flap', g.bm_box(0.085, 0.175, 0.05, bevel=0.015), M('satchel_d', '#6E4E2A', rough=0.7),
               rig.j['spine'], loc=(0.257, -0.02, 0.06), rot=(0, -8, 0))
    leaf = M('leaf', '#6BBE5A', rough=0.6)
    leaf2 = M('leaf2', '#3F8F3A', rough=0.6)
    for k, (dy, dz, tl) in enumerate(((-0.06, 0.12, -20), (0.0, 0.14, 5), (0.05, 0.11, 25), (-0.03, 0.10, -40))):
        g.mesh_obj('herb', g.bm_ellipsoid(0.018, 0.028, 0.065, 10, 8), leaf if k % 2 == 0 else leaf2,
                   rig.j['spine'], loc=(0.25, -0.02 + dy, 0.06 + dz * 0.6), rot=(tl, 0, 0))
    g.mesh_obj('flower', g.bm_ellipsoid(0.022, 0.022, 0.022, 10, 8), M('flower', '#F2C14E', rough=0.6),
               rig.j['spine'], loc=(0.25, 0.03, 0.16))


def dress_bard(rig, spec):
    hair = spec['hair']
    hm = M('hair', hair, rough=0.42)
    cb.hair_shell(rig, hair, fringe=0.34, wave=0.12, waves=9.0, sweep=0.15, back_low=-0.62, top_puff=0.04)
    for s in (-1, 1):
        pts = [(s * 0.27, 0.02, 0.0), (s * 0.31, 0.04, -0.12), (s * 0.30, 0.06, -0.22), (s * 0.27, 0.08, -0.28)]
        ho(rig, 'curl', g.bm_tube_path(catmull3(pts, 12), lambda t: 0.05 - 0.02 * t, segr=12), hm)
    beret = M('beret', '#9E2A3A', rough=0.85)
    ho(rig, 'beret', fuzz(g.bm_ellipsoid(0.335, 0.32, 0.085, 32, 14), 0.002), beret, loc=(-0.04, 0.02, 0.24),
       rot=(-10, -14, 0))
    ho(rig, 'beret_band', g.bm_ring(0.25, 0.022, seg=40, segr=8), beret, loc=(-0.02, 0.01, 0.205), rot=(-10, -10, 0))
    ho(rig, 'beret_nub', g.bm_ellipsoid(0.025, 0.025, 0.03, 8, 6), beret, loc=(-0.06, 0.03, 0.33))
    # feather tucked in the band, sweeping back
    fpts = [(0.20, 0.10, 0.26), (0.27, 0.17, 0.31), (0.31, 0.26, 0.33), (0.32, 0.35, 0.32)]
    ho(rig, 'feather', g.bm_tube_path(catmull3(fpts, 14), lambda t: 0.012 + 0.030 * math.sin(PI * t) ** 0.8,
                                      segr=10, side_ref=(1, 0, 0), flat=0.30), M('feather', '#F4F7FB', rough=0.7))
    ho(rig, 'feather_tip', g.bm_ellipsoid(0.012, 0.03, 0.03, 8, 6), M('feather_tip', '#2E8A8A', rough=0.7),
       loc=(0.32, 0.36, 0.32))
    # short cape + belt + gold trim
    cape = M('cape', '#9E2A3A', rough=0.85)
    g.mesh_obj('cape', cb.vest_lathe([(0.275, -0.17), (0.262, -0.06), (0.242, 0.04), (0.19, 0.10), (0.13, 0.13)],
                                     gap_deg=58, seg=44, sy=0.92), cape, rig.j['chest'])
    g.mesh_obj('cape_trim', g.bm_ring(0.135, 0.022, seg=40, segr=8, sy=0.92), M('trim', '#F2C14E', rough=0.4,
                                                                                metal=0.4),
               rig.j['chest'], loc=(0, 0, 0.13))
    cb.belt(rig, '#5A3A26', z=0.06, buckle='#F2C14E', width=0.5)
    make_lute(rig)


def dress_blacksmith(rig, spec):
    hair = spec['hair']
    cb.hair_shell(rig, hair, fringe=0.34, wave=0.12, waves=10.0, sweep=0.22, back_low=-0.40, top_puff=0.10)
    for az, el in ((-0.35, 0.60), (0.0, 0.70), (0.35, 0.62), (2.6, 0.3), (-2.6, 0.3), (PI, 0.0)):
        cb.hair_tuft(rig, hair, az, el, size=(0.06, 0.045, 0.09), tilt=(-55 if abs(az) < 1 else 120, 0, 0))
    cb.tilted_ring(rig, 'bandana', M('bandana', '#C8463D', rough=0.8), HEAD_R[0] * 1.08, 0.030, 0.62, 0.20,
                   sy=0.98, rz=1.6)
    ho(rig, 'bandana_knot', g.bm_ellipsoid(0.04, 0.03, 0.035, 12, 8), M('bandana', '#C8463D', rough=0.8),
       loc=(0, 0.29, 0.10))
    for s in (-1, 1):
        ho(rig, 'bandana_tail', g.bm_box(0.03, 0.012, 0.09, bevel=0.006), M('bandana', '#C8463D', rough=0.8),
           loc=(s * 0.03, 0.30, 0.04), rot=(15, s * 20, 0))
    leather = M('leather', '#7A4E2E', rough=0.6)
    hem_z = spec.get('hem_z', -0.095)
    g.mesh_obj('apron', sector_lathe([(0.262, hem_z - 0.12), (0.245, -0.02), (0.226, 0.10), (0.220, 0.20),
                                      (0.205, 0.31), (0.17, 0.38)], keep_deg=58, sy=0.88), leather, rig.j['spine'])
    g.mesh_obj('apron_pocket', sector_lathe([(0.255, -0.06), (0.248, 0.02)], keep_deg=26, sy=0.88),
               M('leather_d', '#5E3A22', rough=0.6), rig.j['spine'])
    for s in (-1, 1):
        g.mesh_obj('apron_strap', g.bm_tube_path([(s * 0.10, -0.15, 0.36), (s * 0.12, -0.06, 0.44),
                                                  (s * 0.10, 0.08, 0.43)], 0.014, segr=6), leather,
                   rig.j['spine'])
    cb.belt(rig, '#3B2A20', z=0.10, r=0.226, buckle='#B9C2CE', width=0.5)
    # soot smudges on cheek & nose
    soot = M('soot', '#7E7472', rough=0.95)
    face_obj(rig, 'soot', vf.bm_blob(vf.lumpy(0.17, -0.035, 0.026, n=18, k=5, amp=0.3, seed=0.4), thick=0.004,
                                     out=0.0), soot)
    face_obj(rig, 'soot2', vf.bm_blob(vf.lumpy(-0.20, 0.03, 0.016, n=14, k=4, amp=0.3, seed=1.1), thick=0.004,
                                      out=0.0), soot)


def dress_fashion(rig, spec):
    afro = M('afro', spec['hair'], rough=0.9)

    def afro_r(x, y, z):
        face = smoothstep(0.10, 0.45, -y) * (1 - smoothstep(0.30, 0.46, z)) * (1 - smoothstep(0.74, 0.90, abs(x)))
        big = 1.30 + 0.08 * max(0.0, z)
        return big - (big - 0.90) * face
    bm = g.bm_shell(*HEAD_R, afro_r, seg=48, rings=24)
    fuzz(bm, 0.012, 28.0, seed=0.7)
    ho(rig, 'afro', bm, afro)
    # curls: little balls all over the afro surface (deterministic golden-angle spiral)
    nb = 90
    for k in range(nb):
        z = 1 - 2 * (k + 0.5) / nb
        r = math.sqrt(max(0.0, 1 - z * z))
        a = k * 2.399963
        x, y = r * math.cos(a), r * math.sin(a)
        f = afro_r(x, y, z)
        if f < 1.15:
            continue
        p = Vector((x * HEAD_R[0] * f, y * HEAD_R[1] * f, z * HEAD_R[2] * f))
        ho(rig, 'curl', g.bm_ellipsoid(0.050, 0.050, 0.046, 10, 6), afro, loc=tuple(p))
    make_shades(rig)
    # big pink fur collar + fluffy hem/cuffs come from spec (fur colour)
    cb.collar_fur(rig, spec, R=0.17, r=0.095, dz=0.09, bump=0.50, tufts=12)
    for s in (-1, 1):
        cb.on_head('earring', g.bm_ring(0.025, 0.007, seg=20, segr=6), M('gold', '#F2C14E', rough=0.25, metal=0.8),
                   rig.j['head'], s * PI / 2 * 0.98, -0.30, out=0.0)
    g.mesh_obj('necklace', g.bm_ring(0.12, 0.010, seg=40, segr=6, sy=0.95), M('gold', '#F2C14E', rough=0.25,
                                                                             metal=0.8),
               rig.j['chest'], loc=(0, -0.03, 0.05), rot=(-25, 0, 0))


def dress_parka(rig, spec):
    cb.dress_villager(rig, spec)


DRESS = {
    'npc_kid_boy': dress_kid_boy, 'npc_kid_girl': dress_kid_girl, 'npc_kid_prankster': dress_prankster,
    'npc_teen_girl': dress_teen_girl, 'npc_young_man': dress_young_man, 'npc_aunt': dress_aunt,
    'npc_uncle': dress_uncle, 'npc_grandma': dress_grandma, 'npc_grandpa': dress_grandpa,
    'npc_merchant': dress_merchant, 'npc_herbalist': dress_herbalist, 'npc_bard': dress_bard,
    'npc_blacksmith': dress_blacksmith, 'npc_fashion': dress_fashion, 'npc_yellow': dress_parka,
    'npc_red': dress_parka, 'npc_blue': dress_parka,
}
