"""
char_build.py - procedural chibi characters, tools and animals for Frost Village.

Not run directly: char_render.py imports build(key) which resets the scene and
returns a char_geo.Rig ready to pose.  Every character is a rigid-part
hierarchy of pivot empties (root > hips > spine > chest > neck/head, shoulders >
elbows > hands, hips > thighs > knees) so animation is just joint rotations.

Proportions: ~2.5 heads tall, about 1.40-1.48 m incl. hair/hat (~80 px on screen).
Front = local -Y (bl_common convention), character's right side = -X.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy                      # noqa: E402
from mathutils import Vector, Matrix, Quaternion   # noqa: E402

import bl_common as bc          # noqa: E402
import char_geo as g            # noqa: E402

PI = math.pi

# Body measurements (metres, world z at rest)
HIP_Z = 0.34
CHEST_DZ = 0.33           # chest pivot above hips
SHOULDER = (0.185, 0.0, 0.035)
NECK_DZ = 0.12
HEAD_C = 0.27             # head centre above neck pivot
HEAD_R = (0.300, 0.285, 0.280)
UPPER_ARM = 0.125
FOREARM = 0.115
THIGH = 0.150
HAND_DZ = 0.035           # mitten centre below wrist

SKIN = '#F6CFAE'
BLUSH = '#F49A9A'
EYE = '#2A2026'
MOUTH = '#8E3D3A'


def M(name, color, rough=0.75, **kw):
    return bc.mat(name, color, rough=rough, **kw)


def mat_plaid(name, base, dark, light=None, scale=11.0):
    """Red-plaid flannel (procedural stripes from object coordinates)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    p.inputs['Roughness'].default_value = 0.85
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])

    def stripes(sock):
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = scale
        nt.links.new(sock, mul.inputs[0])
        fr = nt.nodes.new('ShaderNodeMath'); fr.operation = 'FRACT'
        nt.links.new(mul.outputs[0], fr.inputs[0])
        lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'
        lt.inputs[1].default_value = 0.38
        nt.links.new(fr.outputs[0], lt.inputs[0])
        return lt.outputs[0]

    # diagonal-ish mix of X and Y so stripes show from every side
    addxy = nt.nodes.new('ShaderNodeMath'); addxy.operation = 'ADD'
    nt.links.new(sep.outputs['X'], addxy.inputs[0]); nt.links.new(sep.outputs['Y'], addxy.inputs[1])
    s1 = stripes(addxy.outputs[0])
    s2 = stripes(sep.outputs['Z'])
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'ADD'
    nt.links.new(s1, mx.inputs[0]); nt.links.new(s2, mx.inputs[1])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*bc.srgb_to_linear(base), 1)
    cr.elements[1].position = 0.5
    cr.elements[1].color = (*bc.srgb_to_linear(light or base), 1)
    e = cr.elements.new(0.75)
    e.color = (*bc.srgb_to_linear(dark), 1)
    div = nt.nodes.new('ShaderNodeMath'); div.operation = 'MULTIPLY'
    div.inputs[1].default_value = 0.5
    nt.links.new(mx.outputs[0], div.inputs[0])
    nt.links.new(div.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m


# --------------------------------------------------------------------------- face

def head_point(az, el, out=0.0, radii=HEAD_R):
    rx, ry, rz = radii
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    p = Vector((d.x * rx, d.y * ry, d.z * rz))
    n = Vector((d.x / rx, d.y / ry, d.z / rz)).normalized()
    return p + n * out, n


def on_head(name, bm, material, head, az, el, out=0.0, tilt=0.0, hc=HEAD_C):
    p, n = head_point(az, el, out)
    q = (-n).to_track_quat('Y', 'Z')
    if tilt:
        q = q @ Quaternion((0, 1, 0), math.radians(tilt))
    return g.mesh_obj(name, bm, material, head, loc=(p.x, p.y, p.z + hc), rot=q)


def arc_bm(R, r, a0, a1, seg=10):
    """Arc in the local XZ plane (thin axis = Y) - for happy eyes / smiles."""
    bm = g.bm_ring(R, r, seg=seg, segr=8, u0=a0, u1=a1, closed=False,
                   taper=lambda t: 0.75 + 0.25 * math.sin(PI * t))
    g.bm_transform(bm, Matrix.Rotation(PI / 2, 4, 'X'))
    return bm


def build_face(rig, head, spec):
    eye_m = M('eye', spec.get('eye', EYE), rough=0.25)
    hi_m = M('eye_hi', '#FFFFFF', rough=0.3, emission='#FFFFFF', emission_strength=1.5)
    sk = M('skin', spec.get('skin', SKIN), rough=0.55)
    ex, ey = spec.get('eye_spread', 0.37), spec.get('eye_el', -0.10)
    es = spec.get('eye_size', 1.12)
    normal = []
    happy = []
    for s in (-1, 1):
        normal.append(on_head('eye', g.bm_ellipsoid(0.034 * es, 0.016, 0.048 * es, 16, 10),
                              eye_m, head, s * ex, ey, out=-0.006))
        normal.append(on_head('eye_hi', g.bm_ellipsoid(0.012 * es, 0.006, 0.013 * es, 8, 6),
                              hi_m, head, s * ex - 0.035, ey + 0.07, out=0.004))
        happy.append(on_head('eye_happy', arc_bm(0.030 * es, 0.0095, 0.15, PI - 0.15), eye_m,
                             head, s * ex, ey - 0.02, out=-0.002))
        on_head('blush', g.bm_ellipsoid(0.050, 0.010, 0.030, 16, 8),
                M('blush', spec.get('blush', BLUSH), rough=0.9), head,
                s * spec.get('blush_spread', 0.62), -0.24, out=-0.002)
        if spec.get('ears', True):
            on_head('ear', g.bm_ellipsoid(0.028, 0.055, 0.065, 12, 8), sk, head,
                    s * PI / 2 * 0.98, -0.08, out=-0.02)
    on_head('nose', g.bm_ellipsoid(0.026, 0.018, 0.020, 12, 8), sk, head, 0.0, -0.18, out=-0.004)
    mouth_m = M('mouth', MOUTH, rough=0.5)
    m_small = on_head('mouth', arc_bm(0.022, 0.0065, PI + 0.35, 2 * PI - 0.35), mouth_m, head,
                      0.0, -0.34, out=-0.001)
    m_open = on_head('mouth_open', g.bm_ellipsoid(0.032, 0.010, 0.024, 12, 8), mouth_m, head,
                     0.0, -0.35, out=-0.004)
    rig.toggle('face_normal', normal + [m_small])
    rig.toggle('face_happy', happy + [m_open])
    rig.toggle('face_smile', normal + [m_open])


# --------------------------------------------------------------------------- body parts

def fur_mat(spec):
    return M('fur', spec.get('fur', '#E6DCCB'), rough=0.95)


def build_human(spec):
    """Base body.  Returns the rig; spec controls colours & optional parts."""
    rig = g.Rig('human')
    root = rig.add('root', None, (0, 0, 0))
    rig.j['root'] = root
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
    fur = fur_mat(spec)
    pants = M('pants', spec.get('pants', '#4A3830'), rough=0.85)
    boots = M('boots', spec.get('boots', '#5A3A26'), rough=0.6)
    mitt = M('mitten', spec.get('mitten', '#6B4A2E'), rough=0.7)
    skin = M('skin', spec.get('skin', SKIN), rough=0.55)

    # ---- torso (coat / shirt) on the spine pivot
    hem_r = spec.get('hem_r', 0.250)
    hz = spec.get('hem_z', -0.095)
    prof = spec.get('torso_profile', [(hem_r, hz), (hem_r - 0.012, hz + 0.08), (0.212, 0.10),
                                      (0.208, 0.22), (0.195, 0.31), (0.155, 0.39), (0.07, 0.45),
                                      (0.0, 0.46)])
    g.mesh_obj('torso', g.bm_lathe(prof, seg=40, sy=0.84, smooth_n=26, cap_top=False),
               coat, rig.j['spine'])
    if spec.get('hem_fur', True):
        g.mesh_obj('hem_fur', g.bm_ring(hem_r - 0.004, 0.042, seg=72, segr=12, sy=0.84, rz=0.85,
                                        tufts=13, bump=0.35, seed=1.0),
                   fur, rig.j['spine'], loc=(0, 0, hz + 0.015))

    # ---- head
    head = rig.j['head']
    g.mesh_obj('head', g.bm_ellipsoid(*HEAD_R, seg=40, rings=20), skin, head, loc=(0, 0, HEAD_C))
    build_face(rig, head, spec)

    # ---- arms
    for name in ('R', 'L'):
        g.mesh_obj('uarm_' + name, g.bm_capsule(0.076, UPPER_ARM, r_end=0.070), sleeve,
                   rig.j['sh_' + name])
        g.mesh_obj('farm_' + name, g.bm_capsule(0.070, FOREARM - 0.02, r_end=0.062), sleeve,
                   rig.j['el_' + name])
        if spec.get('cuff_fur', True):
            g.mesh_obj('cuff_' + name, g.bm_ring(0.056, 0.028, seg=32, segr=10, tufts=7, bump=0.3,
                                                 seed=2.0 if name == 'R' else 3.0),
                       fur, rig.j['el_' + name], loc=(0, 0, -FOREARM + 0.012))
        g.mesh_obj('mitt_' + name, g.bm_ellipsoid(0.058, 0.052, 0.060, 20, 12), mitt,
                   rig.j['hand_' + name])
        # thumb
        g.mesh_obj('thumb_' + name, g.bm_ellipsoid(0.024, 0.024, 0.032, 10, 8), mitt,
                   rig.j['hand_' + name], loc=(0.0, -0.045, 0.012), rot=(25, 0, 0))

    # ---- legs
    for name in ('R', 'L'):
        g.mesh_obj('thigh_' + name, g.bm_capsule(0.072, THIGH, r_end=0.064), pants,
                   rig.j['hip_' + name])
        g.mesh_obj('shin_' + name, g.bm_capsule(0.062, 0.07, r_end=0.060), pants,
                   rig.j['knee_' + name])
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


# --------------------------------------------------------------------------- hair & hats

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def hair_shell(rig, color, fringe=0.30, wave=0.08, waves=9.0, sweep=0.10, back_low=-0.62,
               top_puff=0.07, base=1.07, inner=0.90, name='hair', side_low=0.02):
    head = rig.j['head']

    def radial(x, y, z):
        front = smoothstep(-0.32, 0.30, -y)          # 0 behind the ears, 1 at the face
        edge_front = fringe + wave * math.cos(x * waves) - sweep * x
        edge_front = min(edge_front, side_low + (1 - abs(x)) * 2.0)   # sideburns by the ears
        edge = back_low * (1 - front) + edge_front * front
        t = smoothstep(edge - 0.05, edge + 0.05, z)
        f = inner + (base - inner) * t
        return f * (1.0 + top_puff * max(0.0, z) ** 2)

    bm = g.bm_shell(*HEAD_R, radial, seg=56, rings=28)
    return g.mesh_obj(name, bm, M('hair', color, rough=0.42), head, loc=(0, 0, HEAD_C))


def hair_tuft(rig, color, az, el, size=(0.05, 0.035, 0.08), tilt=(0, 0, 0), name='tuft'):
    p, n = head_point(az, el, out=0.0)
    head = rig.j['head']
    q = n.to_track_quat('Z', 'Y') @ Quaternion(Vector((1, 0, 0)), math.radians(tilt[0])) @ \
        Quaternion(Vector((0, 1, 0)), math.radians(tilt[1]))
    bm = g.bm_lathe([(0.0, 0.0), (size[0], size[2] * 0.25), (size[0] * 0.75, size[2] * 0.6),
                     (0.0, size[2])], seg=12, smooth_n=10, sy=size[1] / size[0])
    return g.mesh_obj(name, bm, M('hair', color, rough=0.42), head,
                      loc=(p.x, p.y, p.z + HEAD_C - 0.02), rot=q)


def collar_fur(rig, spec, R=0.135, r=0.072, dz=0.095, bump=0.38, tufts=9, mat=None):
    return g.mesh_obj('collar', g.bm_ring(R, r, seg=72, segr=14, tufts=tufts, bump=bump, seed=5.0,
                                          sy=0.92, rz=0.9),
                      mat or fur_mat(spec), rig.j['chest'], loc=(0, 0.01, dz))


def belt(rig, color, z=0.10, r=0.208, buckle='#C9A045', width=0.55):
    bm = g.bm_ring(r, 0.03, seg=56, segr=10, sy=0.84, rz=width)
    g.mesh_obj('belt', bm, M('belt', color, rough=0.55), rig.j['spine'], loc=(0, 0, z))
    if buckle:
        g.mesh_obj('buckle', g.bm_box(0.06, 0.02, 0.045, bevel=0.008), M('buckle', buckle, rough=0.35,
                                                                        metal=0.6),
                   rig.j['spine'], loc=(0, -0.84 * r - 0.018, z))


# --------------------------------------------------------------------------- tools

def fx_marker(rig, tool, parent, loc):
    """Empty at a tool's business end; char_render turns it into impactPoint."""
    e = g.empty('fx_' + tool, parent, loc)
    rig.meta.setdefault('fx', {})[tool] = e
    return e


WOOD = '#C98F55'
WOOD_D = '#8A5A33'
METAL = '#B9C2CE'
METAL_D = '#7D8794'


def make_axe(rig, name='axe', head_color=METAL, length=0.56, big=1.2, tilt=18.0):
    """Handle along the tool's local -Z from the grip; blade at the far end facing -Y."""
    t = g.empty(name + '_obj', rig.j['hand_R'])
    t.rotation_quaternion = g.q_axis((1, 0, 0), -tilt)
    objs = []
    objs.append(g.mesh_obj(name + '_handle', g.bm_lathe([(0.024, 0.06), (0.021, -length * 0.6),
                                                         (0.025, -length), (0.0, -length - 0.012)],
                                                        seg=12, smooth_n=8),
                           M('wood', WOOD, rough=0.6), t))
    # blade: fan-shaped slab (outline in the handle's Y/Z plane) + bright edge
    zc = -length + 0.07
    pts = []
    for k in range(9):                                   # curved cutting edge
        a = -0.62 + 1.24 * k / 8
        pts.append((-0.06 * big - 0.085 * big * math.cos(a), zc + 0.095 * big * math.sin(a)))
    pts = [(0.012, zc - 0.035 * big)] + pts + [(0.012, zc + 0.035 * big)]
    pts = [(y, z) for y, z in pts]
    objs.append(g.mesh_obj(name + '_blade', g.bm_slab(pts, 0.032 * big, bevel=0.007),
                           M('axe_head', head_color, rough=0.35, metal=0.55), t))
    edge = []
    for k in range(9):
        a = -0.66 + 1.32 * k / 8
        edge.append((-0.065 * big - 0.088 * big * math.cos(a), zc + 0.10 * big * math.sin(a)))
    inner = [(y + 0.03 * big, z * 0.92 + zc * 0.08) for y, z in edge[::-1]]
    objs.append(g.mesh_obj(name + '_edge', g.bm_slab(edge + inner, 0.022 * big, bevel=0.004),
                           M('edge', '#EEF3F8', rough=0.2, metal=0.6), t))
    objs.append(g.mesh_obj(name + '_butt', g.bm_box(0.045, 0.06, 0.075, bevel=0.012),
                           M('axe_head', head_color, rough=0.35, metal=0.55), t,
                           loc=(0, 0.02, zc)))
    fx_marker(rig, name, t, (0, -0.145 * big, zc))
    rig.toggle(name, objs)
    return t


def make_pickaxe(rig, name='pickaxe', length=0.56, tilt=18.0):
    t = g.empty(name + '_obj', rig.j['hand_R'])
    t.rotation_quaternion = g.q_axis((1, 0, 0), -tilt)
    objs = []
    objs.append(g.mesh_obj(name + '_handle', g.bm_lathe([(0.020, 0.06), (0.018, -length * 0.6),
                                                         (0.021, -length), (0.0, -length - 0.012)],
                                                        seg=12, smooth_n=8),
                           M('wood', WOOD, rough=0.6), t))
    # curved double pick: crescent in the YZ plane, centred on the handle top
    head = g.bm_ring(0.24, 0.034, seg=28, segr=10, u0=PI * 0.20, u1=PI * 0.80, closed=False,
                     taper=lambda tt: 0.25 + 0.75 * math.sin(PI * tt) ** 0.6)
    g.bm_transform(head, Matrix.Rotation(PI / 2, 4, 'Y') @ Matrix.Rotation(PI / 2, 4, 'Z'))
    objs.append(g.mesh_obj(name + '_head', head, M('pick_head', METAL_D, rough=0.35, metal=0.6), t,
                           loc=(0, 0, -length + 0.20), rot=(0, 0, 0)))
    objs.append(g.mesh_obj(name + '_collar', g.bm_cyl(0.032, 0.032, 0.07, seg=12, centered=True),
                           M('pick_head', METAL_D, rough=0.35, metal=0.6), t,
                           loc=(0, 0, -length + 0.0)))
    fx_marker(rig, name, t, (0, -0.22, -length + 0.06))
    rig.toggle(name, objs)
    return t


def make_sickle(rig, name='sickle', tilt=10.0):
    """Short handle continuing the arm; the crescent blade hooks out to the
    character's LEFT (+X) - the direction of the right-to-left sweep - so it
    stays at wheat height while the arm sweeps forward-down."""
    t = g.empty(name + '_obj', rig.j['hand_R'])
    t.rotation_quaternion = g.q_axis((1, 0, 0), -tilt) @ g.q_axis((0, 0, 1), 90)
    objs = [g.mesh_obj(name + '_handle', g.bm_lathe([(0.0, 0.05), (0.024, 0.045), (0.022, -0.15),
                                                     (0.0, -0.16)], seg=12, smooth_n=8),
                       M('wood', WOOD, rough=0.6), t)]
    R = 0.13
    pts = g.arc_points((0, -R, -0.15), R, 0.0, -4.5, n=22, plane='YZ')
    blade = g.bm_tube_path(pts, lambda tt: 0.030 * (1 - 0.85 * tt) + 0.004, segr=10,
                           side_ref=(1, 0, 0), flat=0.30)
    objs.append(g.mesh_obj(name + '_blade', blade, M('edge', '#E8EEF5', rough=0.25, metal=0.6), t))
    objs.append(g.mesh_obj(name + '_ferrule', g.bm_cyl(0.026, 0.026, 0.03, seg=12, centered=True),
                           M('pick_head', METAL_D, rough=0.35, metal=0.6), t, loc=(0, 0, -0.145)))
    fx_marker(rig, name, t, (0, -R * 2, -0.15))
    rig.toggle(name, objs)
    return t


def make_rod(rig, name='rod', tilt=70.0, length=0.86):
    """Fishing rod + dynamic line & bobber.  state['_cast'] 0 = bobber hangs from
    the tip, 1 = bobber out on the water in front of the fisher."""
    t = g.empty(name + '_obj', rig.j['hand_R'])
    t.rotation_quaternion = g.q_axis((1, 0, 0), -tilt)
    objs = []
    objs.append(g.mesh_obj(name + '_pole', g.bm_lathe([(0.0, 0.10), (0.017, 0.095), (0.014, -0.15),
                                                       (0.009, -0.5), (0.005, -length), (0.0, -length - 0.01)],
                                                      seg=10, smooth_n=12),
                           M('rod', '#5B3A24', rough=0.45), t))
    objs.append(g.mesh_obj(name + '_cork', g.bm_lathe([(0.0, 0.10), (0.025, 0.09), (0.024, -0.06),
                                                       (0.0, -0.07)], seg=12, smooth_n=8),
                           M('cork', '#D8A86A', rough=0.8), t))
    objs.append(g.mesh_obj(name + '_reel', g.bm_cyl(0.035, 0.035, 0.03, seg=16, centered=True),
                           M('reel', '#C8463D', rough=0.4, metal=0.2), t, loc=(0, 0.045, -0.10),
                           rot=(0, 90, 0)))
    tip = g.empty(name + '_tip', t, (0, 0, -length))
    rig.j[name + '_tip'] = tip
    rig.rest_loc[name + '_tip'] = Vector((0, 0, -length))
    line = g.tube_between(name + '_line', M('line', '#F4F7FB', rough=0.5), radius=0.0045, seg=5)
    bob_top = g.mesh_obj(name + '_bob', g.merge(g.bm_ellipsoid(0.034, 0.034, 0.03, 12, 8)),
                         M('bobber', '#E8433A', rough=0.3))
    bob_bot = g.mesh_obj(name + '_bob2', g.bm_ellipsoid(0.031, 0.031, 0.028, 12, 8),
                         M('bobber_w', '#FFFFFF', rough=0.3))
    objs += [line, bob_top, bob_bot]
    rig.toggle(name, objs)

    def update(r):
        if line.hide_render:
            return
        tipw = r.world(name + '_tip')
        cast = float(r.state.get('_cast', 0.0))
        hang = tipw + Vector((0, 0, -0.26))
        water = r.world('root', (0, -0.60, 0.03))
        water.z = 0.03
        b = hang.lerp(water, cast)
        r.meta['fx_point'] = b.copy()
        g.set_tube(line, tipw, b + Vector((0, 0, 0.03)))
        bob_top.matrix_world = Matrix.Translation(b + Vector((0, 0, 0.012)))
        bob_bot.matrix_world = Matrix.Translation(b + Vector((0, 0, -0.008)))
    rig.strings.append(update)
    return t


def make_arrow(name='bow', scale=1.0):
    """Arrow built along +Z from the nock (z=0) to the tip (z=0.60*scale)."""
    am = M('arrow', '#C98F55', rough=0.6)
    k = scale
    shaft = g.bm_lathe([(0.0, 0.0), (0.009 * k, 0.005 * k), (0.008 * k, 0.52 * k), (0.0, 0.53 * k)], seg=8)
    head = g.bm_lathe([(0.0, 0.50 * k), (0.022 * k, 0.53 * k), (0.0, 0.60 * k)], seg=8)
    fl = g.bm_slab([(-0.025 * k, 0.02 * k), (0.025 * k, 0.02 * k), (0.012 * k, 0.11 * k),
                    (-0.012 * k, 0.11 * k)], 0.004 * k, bevel=0.0)
    arrow = g.mesh_obj(name + '_arrow', shaft, am)
    ahead = g.mesh_obj(name + '_arrowhead', head, M('pick_head', METAL_D, rough=0.35, metal=0.6))
    afl = g.mesh_obj(name + '_fletch', fl, M('fletch', '#E8433A', rough=0.6))
    ahead.parent = arrow
    afl.parent = arrow
    return arrow, ahead, afl


def make_bow(rig, name='bow'):
    """Bow in the RIGHT hand (the camera-near side in E/SE/NE views; the game
    mirrors W views so handedness never shows).  Bow-space: limbs along Z, belly
    toward -Y.  state['_draw'] 0..1 pulls the string to the LEFT hand; '_show'
    containing 'arrow' shows the nocked arrow."""
    t = g.empty(name + '_obj', rig.j['hand_R'])
    t.rotation_quaternion = g.q_axis((1, 0, 0), 90)
    R, th = 0.46, 0.92
    pts = []
    for k in range(25):
        u = -th + 2 * th * k / 24
        # recurve the tips slightly
        bend = 0.03 * max(0.0, abs(u) / th - 0.75) / 0.25
        pts.append((0.0, R - R * math.cos(u) - bend, R * math.sin(u)))
    bow = g.bm_tube_path(pts, lambda tt: 0.016 + 0.010 * math.sin(PI * tt), segr=8,
                         side_ref=(1, 0, 0), flat=0.8)
    objs = [g.mesh_obj(name + '_limb', bow, M('bow', '#8A5A33', rough=0.45), t),
            g.mesh_obj(name + '_grip', g.bm_cyl(0.028, 0.028, 0.10, seg=12, centered=True),
                       M('grip', '#C8463D', rough=0.7), t)]
    tip_y = R - R * math.cos(th) - 0.03
    for nm, z in (('_tipA', R * math.sin(th)), ('_tipB', -R * math.sin(th))):
        e = g.empty(name + nm, t, (0, tip_y, z))
        rig.j[name + nm] = e
        rig.rest_loc[name + nm] = Vector((0, tip_y, z))
    fx_marker(rig, name, t, (0, -0.22, 0))       # arrow leaves the bow here
    e = g.empty(name + '_nock', t, (0, tip_y, 0))
    rig.j[name + '_nock'] = e
    rig.rest_loc[name + '_nock'] = Vector((0, tip_y, 0))
    smat = M('bowstring', '#F4EFE6', rough=0.5)
    s1 = g.tube_between(name + '_s1', smat, radius=0.005, seg=5)
    s2 = g.tube_between(name + '_s2', smat, radius=0.005, seg=5)
    objs += [s1, s2]
    rig.toggle(name, objs)
    arrow, ahead, afl = make_arrow(name)
    rig.toggle('arrow', [arrow, ahead, afl])

    def update(r):
        if s1.hide_render:
            return
        a, b = r.world(name + '_tipA'), r.world(name + '_tipB')
        rest = r.world(name + '_nock')
        draw = float(r.state.get('_draw', 0.0))
        hand = r.world('hand_L', (0.0, -0.02, 0.0))
        nock = rest.lerp(hand, draw)
        g.set_tube(s1, a, nock)
        g.set_tube(s2, b, nock)
        if not arrow.hide_render:
            grip = t.matrix_world.translation.copy()
            g.set_oriented(arrow, nock, grip - nock)
    rig.strings.append(update)
    return t


# --------------------------------------------------------------------------- shells

def shell(rig, material, radial, name='shell', seg=56, rings=28):
    return g.mesh_obj(name, g.bm_shell(*HEAD_R, radial, seg=seg, rings=rings), material,
                      rig.j['head'], loc=(0, 0, HEAD_C))


def cap_shell(rig, material, edge, base=1.12, inner=0.88, puff=0.0, name='cap', soft=0.05,
              lumps=0.0):
    """Covers the head where z > edge(x, y) (unit-direction coordinates)."""
    def radial(x, y, z):
        t = smoothstep(edge(x, y) - soft, edge(x, y) + soft, z)
        f = inner + (base - inner) * t
        if lumps:
            f *= 1.0 + lumps * t * (0.5 + 0.5 * math.sin(19 * x + 2.0) * math.sin(17 * y + 1.0)
                                    * math.cos(13 * z))
        return f * (1.0 + puff * max(0.0, z) ** 2)
    return shell(rig, material, radial, name)


def head_obj(rig, name, bm, material, loc=(0, 0, 0), rot=None):
    return g.mesh_obj(name, bm, material, rig.j['head'], loc=(loc[0], loc[1], loc[2] + HEAD_C), rot=rot)


def tilted_ring(rig, name, material, R, r, z_front, z_back, sy=1.0, tufts=0, bump=0.0, seed=0.0,
                rz=1.0, scale_r=1.0):
    """Ring around the head following a tilted plane (front edge higher)."""
    ry = HEAD_R[1]
    ang = math.degrees(math.atan2((z_front - z_back) * HEAD_R[2], 2 * ry))
    zc = (z_front + z_back) / 2 * HEAD_R[2]
    bm = g.bm_ring(R, r, seg=64, segr=12, sy=sy, rz=rz, tufts=tufts, bump=bump, seed=seed)
    return head_obj(rig, name, bm, material, loc=(0, 0, zc), rot=(-ang, 0, 0))


def beard(rig, color, edge=-0.26, curve=0.34, base=1.13, chin=0.10, name='beard'):
    def radial(x, y, z):
        e = edge + curve * x * x
        w = smoothstep(e + 0.05, e - 0.06, z) * smoothstep(-0.25, 0.10, -y)
        f = 0.9 + (base - 0.9) * w
        f += chin * w * smoothstep(-0.3, -0.9, z)
        return f
    return shell(rig, M('beard', color, rough=0.8), radial, name)


def front_point(z, r=0.21, out=0.004):
    """Point on the torso front surface at spine-local height z."""
    return (0.0, -0.84 * r - out, z)


# --------------------------------------------------------------------------- characters

def dress_player(rig, spec):
    collar_fur(rig, spec, R=0.165, r=0.088, dz=0.10, bump=0.42, tufts=10)
    g.mesh_obj('hood', g.bm_ellipsoid(0.19, 0.11, 0.14, 24, 12), spec['coat_mat'], rig.j['chest'],
               loc=(0, 0.20, 0.06), rot=(-25, 0, 0))
    g.mesh_obj('hood_fur', g.bm_ring(0.15, 0.04, seg=48, segr=10, tufts=9, bump=0.4, seed=7.0, sy=0.7),
               fur_mat(spec), rig.j['chest'], loc=(0, 0.25, 0.10), rot=(-70, 0, 0))
    belt(rig, '#6B4A2E', z=0.08)
    strap = g.bm_ring(0.212, 0.016, seg=64, segr=8, sy=0.86, rz=1.6)
    g.mesh_obj('strap', strap, M('belt', '#6B4A2E', rough=0.55), rig.j['spine'],
               loc=(0, 0, 0.20), rot=(0, 38, 0))
    g.mesh_obj('satchel', g.bm_box(0.06, 0.13, 0.11, bevel=0.02), M('satchel', '#8A5A33', rough=0.6),
               rig.j['spine'], loc=(0.225, 0.03, 0.02), rot=(0, 8, 0))
    hair_shell(rig, spec['hair'], fringe=0.36, wave=0.06, waves=10.0, sweep=0.14)
    hair_tuft(rig, spec['hair'], 0.0, 1.25, size=(0.045, 0.035, 0.075), tilt=(-55, 0, 0))
    for k, az in enumerate((2.7, 3.0, 3.3, 3.6)):
        hair_tuft(rig, spec['hair'], az, -0.42 + 0.05 * (k % 2), size=(0.055, 0.04, 0.09),
                  tilt=(150, 0, 0), name='nape')
    for az, el in ((2.4, 0.5), (3.9, 0.45), (3.14, 0.9)):
        hair_tuft(rig, spec['hair'], az, el, size=(0.06, 0.045, 0.07), tilt=(120, 0, 0), name='backtuft')
    make_axe(rig)
    make_pickaxe(rig)


def dress_fisherman(rig, spec):
    coat = spec['coat_mat']
    g.mesh_obj('collar', g.bm_ring(0.150, 0.052, seg=48, segr=12, sy=0.9, rz=1.0), coat,
               rig.j['chest'], loc=(0, 0.01, 0.09))
    btn = M('button', '#3B3F4A', rough=0.4)
    for z in (0.02, 0.12, 0.22):
        g.mesh_obj('button', g.bm_ellipsoid(0.018, 0.010, 0.018, 10, 6), btn, rig.j['spine'],
                   loc=front_point(z, 0.212 if z < 0.15 else 0.205))
    g.mesh_obj('placket', g.bm_box(0.012, 0.012, 0.30, bevel=0.004), M('placket', '#D9A520', rough=0.4),
               rig.j['spine'], loc=(0.03, -0.181, 0.12))
    hair_shell(rig, spec['hair'], fringe=0.26, wave=0.05, waves=12.0, sweep=0.0)
    hat = M('souwester', spec['coat'], rough=0.32)
    cap_shell(rig, hat, lambda x, y: 0.22 - 0.30 * y, base=1.12, puff=0.10, name='hat_crown')
    brim = g.bm_lathe([(0.27, 0.012), (0.36, -0.010), (0.42, -0.045), (0.425, -0.058),
                       (0.36, -0.026), (0.27, -0.006)], seg=56, sy=1.12, smooth_n=0,
                      cap_bottom=False, cap_top=False, yoff=lambda z: 0.075)
    head_obj(rig, 'hat_brim', brim, hat, loc=(0, 0.0, 0.10), rot=(-17, 0, 0))
    # tall rubber boots
    rub = M('rubber', spec['boots'], rough=0.3)
    for n in ('R', 'L'):
        g.mesh_obj('bootleg_' + n, g.bm_lathe([(0.070, -0.16), (0.072, -0.02), (0.075, 0.02),
                                              (0.0, 0.021)], seg=20, smooth_n=0, cap_top=False),
                   rub, rig.j['knee_' + n])
    make_rod(rig)


def dress_lumberjack(rig, spec):
    hair_shell(rig, spec['hair'], fringe=0.30, wave=0.05, waves=8.0, sweep=0.05, back_low=-0.4)
    beanie = M('beanie', '#3B4250', rough=0.92)
    cap_shell(rig, beanie, lambda x, y: 0.16 - 0.34 * y, base=1.12, puff=0.20, name='beanie',
              lumps=0.02)
    tilted_ring(rig, 'beanie_cuff', beanie, HEAD_R[0] * 1.03, 0.042, 0.52, -0.16, sy=0.96, rz=1.3)
    beard(rig, spec['hair'], edge=-0.36, curve=0.42, base=1.13, chin=0.16)
    bm = M('beard', spec['hair'], rough=0.8)
    for s in (-1, 1):
        on_head('stache', g.bm_ellipsoid(0.055, 0.03, 0.03, 12, 8), bm, rig.j['head'], s * 0.11, -0.29,
                out=-0.004, tilt=-s * 18)
        on_head('brow', g.bm_ellipsoid(0.045, 0.016, 0.016, 10, 6), bm, rig.j['head'], s * 0.37, 0.12,
                out=0.0, tilt=s * 8)
    sus = M('suspender', '#2E3440', rough=0.6)
    for s in (-1, 1):
        g.mesh_obj('suspender', g.bm_box(0.035, 0.012, 0.34, bevel=0.005), sus, rig.j['spine'],
                   loc=(s * 0.085, -0.178, 0.18), rot=(4, -s * 6, 0))
        g.mesh_obj('suspender_b', g.bm_box(0.035, 0.012, 0.34, bevel=0.005), sus, rig.j['spine'],
                   loc=(s * 0.085, 0.178, 0.18), rot=(-4, s * 6, 0))
    belt(rig, '#4A3020', z=0.0, r=0.226, buckle='#B9C2CE')
    make_axe(rig, length=0.62, big=1.35)


def dress_farmer(rig, spec):
    over = M('overalls', spec['pants'], rough=0.85)
    g.mesh_obj('overall_lower', g.bm_lathe([(0.228, -0.09), (0.222, 0.0), (0.214, 0.12), (0.212, 0.14)],
                                           seg=40, sy=0.86, smooth_n=0, cap_top=False, cap_bottom=True),
               over, rig.j['spine'])
    g.mesh_obj('bib', g.bm_box(0.20, 0.03, 0.16, bevel=0.012), over, rig.j['spine'],
               loc=(0, -0.170, 0.21), rot=(-6, 0, 0))
    g.mesh_obj('pocket', g.bm_box(0.09, 0.012, 0.06, bevel=0.006), M('pocket', '#3F7533', rough=0.85),
               rig.j['spine'], loc=(0, -0.189, 0.21), rot=(-6, 0, 0))
    gold = M('buckle', '#C9A045', rough=0.35, metal=0.6)
    for s in (-1, 1):
        g.mesh_obj('strap', g.bm_box(0.035, 0.014, 0.24, bevel=0.005), over, rig.j['spine'],
                   loc=(s * 0.075, -0.150, 0.33), rot=(-40, 0, 0))
        g.mesh_obj('strap_b', g.bm_box(0.035, 0.014, 0.40, bevel=0.005), over, rig.j['spine'],
                   loc=(s * 0.075, 0.172, 0.20), rot=(-8, 0, 0))
        g.mesh_obj('btn', g.bm_ellipsoid(0.017, 0.010, 0.017, 10, 6), gold, rig.j['spine'],
                   loc=(s * 0.075, -0.188, 0.275))
    hair_shell(rig, spec['hair'], fringe=0.24, wave=0.07, waves=11.0, sweep=-0.10)
    hm = M('hair', spec['hair'], rough=0.42)
    tie = M('tie', '#C8463D', rough=0.6)
    for s in (-1, 1):
        x0 = s * 0.26
        pts = [(x0, 0.10, 0.02), (s * 0.29, 0.08, -0.10), (s * 0.27, 0.06, -0.22), (s * 0.24, 0.05, -0.32)]
        for k, p in enumerate(pts):
            rr = 0.050 - 0.006 * k
            head_obj(rig, 'braid', g.bm_ellipsoid(rr, rr * 0.9, rr * 1.15, 14, 8), hm, loc=p)
        head_obj(rig, 'braid_tie', g.bm_ring(0.025, 0.012, seg=16, segr=6), tie,
                 loc=(s * 0.235, 0.05, -0.375))
        head_obj(rig, 'braid_end', g.bm_ellipsoid(0.030, 0.028, 0.045, 10, 6), hm,
                 loc=(s * 0.235, 0.05, -0.42))
    straw = M('straw', '#E8C25A', rough=0.8)
    head_obj(rig, 'hat_crown', g.bm_lathe([(0.21, 0.0), (0.205, 0.10), (0.17, 0.16), (0.0, 0.175)],
                                          seg=40, smooth_n=12, cap_bottom=False), straw,
             loc=(0, 0.02, 0.20), rot=(-8, 0, 0))
    head_obj(rig, 'hat_band', g.bm_ring(0.212, 0.022, seg=48, segr=8, rz=1.4), tie,
             loc=(0, 0.02, 0.235), rot=(-8, 0, 0))
    brim = g.bm_lathe([(0.20, 0.012), (0.36, 0.0), (0.47, -0.035), (0.48, -0.050), (0.36, -0.016),
                       (0.20, -0.004)], seg=64, smooth_n=0, cap_top=False, cap_bottom=False)
    head_obj(rig, 'hat_brim', brim, straw, loc=(0, 0.02, 0.21), rot=(-8, 0, 0))
    make_sickle(rig)


def vest_lathe(prof, gap_deg=40, seg=40, sy=0.86):
    """Lathe with an open front (vests, cloaks)."""
    bm = g.bm_lathe(prof, seg=seg, sy=sy, smooth_n=16, cap_top=False, cap_bottom=False)
    import bmesh
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        ang = math.degrees(math.atan2(c.x, -c.y))
        if abs(ang) < gap_deg:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    return bm


def dress_miner(rig, spec):
    vest = M('vest', '#7A5235', rough=0.75)
    g.mesh_obj('vest', vest_lathe([(0.226, -0.03), (0.222, 0.05), (0.218, 0.14), (0.214, 0.24),
                                   (0.200, 0.31), (0.160, 0.38)], gap_deg=24), vest, rig.j['spine'])
    g.mesh_obj('vest_edge', vest_lathe([(0.231, -0.03), (0.231, -0.01)], gap_deg=24), M('vest_d', '#5C3C26'),
               rig.j['spine'])
    belt(rig, '#3B2A20', z=-0.03, r=0.228, buckle='#B9C2CE')
    hair_shell(rig, spec['hair'], fringe=0.24, wave=0.05, waves=10.0, sweep=0.0, back_low=-0.45)
    hat = M('hardhat', '#E8892B', rough=0.35)
    cap_shell(rig, hat, lambda x, y: 0.16 - 0.05 * y, base=1.14, puff=0.12, name='hardhat', soft=0.02)
    tilted_ring(rig, 'hardhat_rim', hat, HEAD_R[0] * 1.10, 0.024, 0.22, 0.10, sy=0.96, rz=0.7)
    visor = g.bm_lathe([(0.30, 0.008), (0.37, -0.012), (0.375, -0.022), (0.30, -0.006)], seg=40,
                       sy=1.0, cap_top=False, cap_bottom=False)
    import bmesh
    kill = [f for f in visor.faces if f.calc_center_median().y > -0.12]
    bmesh.ops.delete(visor, geom=kill, context='FACES')
    head_obj(rig, 'hardhat_visor', visor, hat, loc=(0, 0.0, 0.055), rot=(-4, 0, 0))
    p, n = head_point(0.0, 0.38, out=0.04)
    lamp_rot = (-n).to_track_quat('Z', 'Y')
    lamp_house = g.bm_cyl(0.050, 0.055, 0.045, seg=20)
    head_obj(rig, 'lamp', lamp_house, M('lamp_body', '#5C636E', rough=0.4, metal=0.4),
             loc=(p.x, p.y + 0.03, p.z - 0.02), rot=lamp_rot)
    lens = g.bm_ellipsoid(0.040, 0.040, 0.012, 16, 8)
    pp = p + n * 0.003
    head_obj(rig, 'lamp_lens', lens, M('lamp_lens', '#FFF2B0', rough=0.2, emission='#FFE27A',
                                       emission_strength=4.0),
             loc=(pp.x, pp.y - 0.015, pp.z - 0.02), rot=lamp_rot)
    bm = M('beard', spec['hair'], rough=0.8)
    for s in (-1, 1):
        on_head('stache', g.bm_ellipsoid(0.060, 0.032, 0.034, 12, 8), bm, rig.j['head'], s * 0.12, -0.25,
                out=-0.002, tilt=-s * 22)
    on_head('smudge', g.bm_ellipsoid(0.035, 0.008, 0.022, 10, 6), M('smudge', '#B9A595', rough=0.9),
            rig.j['head'], 0.55, -0.05, out=-0.001)
    make_pickaxe(rig)


def dress_hunter(rig, spec):
    cloak = M('cloak', '#8A5A3A', rough=0.9)
    fur = M('fur', spec['fur'], rough=0.95)
    g.mesh_obj('cloak', vest_lathe([(0.262, -0.02), (0.250, 0.10), (0.232, 0.22), (0.214, 0.31),
                                    (0.180, 0.38), (0.12, 0.44)], gap_deg=34, seg=44, sy=0.90),
               cloak, rig.j['spine'])
    hem = g.bm_ring(0.26, 0.035, seg=64, segr=10, sy=0.90, tufts=11, bump=0.4, seed=3.0,
                    u0=-PI / 2 + math.radians(36), u1=3 * PI / 2 - math.radians(36), closed=False)
    g.mesh_obj('cloak_fur', hem, fur, rig.j['spine'], loc=(0, 0, -0.015))
    belt(rig, '#4A3020', z=0.05, r=0.214, buckle='#C9A045')
    hair_shell(rig, spec['hair'], fringe=0.20, wave=0.06, waves=10.0, sweep=0.1)

    def hood(x, y, z):
        face = smoothstep(0.05, 0.55, -y) * smoothstep(-0.95, -0.55, z) *             (1 - smoothstep(0.42, 0.62, z)) * (1 - smoothstep(0.62, 0.82, abs(x)))
        f = 1.16 - 0.30 * face
        return f * (1.0 + 0.05 * max(0.0, z) ** 2)
    shell(rig, cloak, hood, 'hood')
    ring = g.bm_ring(0.215, 0.050, seg=56, segr=12, tufts=10, bump=0.45, seed=9.0, sy=1.05)
    head_obj(rig, 'hood_fur', ring, fur, loc=(0, -0.20, -0.02), rot=(78, 0, 0))
    for s in (-1, 1):
        p, n = head_point(s * 0.55, 0.85, out=0.03, radii=tuple(r * 1.14 for r in HEAD_R))
        ear = g.bm_lathe([(0.0, 0.0), (0.060, 0.012), (0.045, 0.06), (0.0, 0.095)], seg=14, smooth_n=8,
                         sy=0.55)
        head_obj(rig, 'hood_ear', ear, cloak, loc=(p.x, p.y, p.z), rot=n.to_track_quat('Z', 'Y'))
        inner = g.bm_ellipsoid(0.030, 0.012, 0.040, 10, 6)
        head_obj(rig, 'hood_ear_in', inner, fur, loc=(p.x * 1.0, p.y - 0.024, p.z + 0.03),
                 rot=n.to_track_quat('Z', 'Y'))
    # quiver on the back
    qv = M('quiver', '#6B4A2E', rough=0.7)
    g.mesh_obj('quiver', g.bm_lathe([(0.0, -0.17), (0.048, -0.165), (0.052, 0.12), (0.056, 0.15),
                                     (0.0, 0.151)], seg=16, smooth_n=0),
               qv, rig.j['chest'], loc=(-0.06, 0.20, -0.08), rot=(-12, -24, 0))
    fl = M('fletch', '#E8433A', rough=0.6)
    for k in range(3):
        g.mesh_obj('q_arrow', g.bm_slab([(-0.02, 0.0), (0.02, 0.0), (0.012, 0.07), (-0.012, 0.07)],
                                        0.006, bevel=0.0), fl, rig.j['chest'],
                   loc=(-0.06 - 0.06 * math.sin(math.radians(24)) + (k - 1) * 0.02,
                        0.20 + 0.04 + (k - 1) * 0.008, 0.07 + 0.01 * k), rot=(-12, -24, k * 30))
    make_bow(rig)


def dress_villager(rig, spec):
    style = spec['style']
    if style != 'scarf':
        collar_fur(rig, spec, R=0.16, r=0.085, dz=0.10, bump=0.42, tufts=10)
        g.mesh_obj('hood', g.bm_ellipsoid(0.18, 0.10, 0.13, 24, 12), spec['coat_mat'], rig.j['chest'],
                   loc=(0, 0.19, 0.07), rot=(-25, 0, 0))
    if style == 'a':
        hair_shell(rig, spec['hair'], fringe=0.30, wave=0.08, waves=9.0, sweep=-0.08)
        for az, el in ((2.6, 0.6), (3.5, 0.55), (3.1, -0.35), (2.8, -0.38), (3.4, -0.38)):
            hair_tuft(rig, spec['hair'], az, el, size=(0.055, 0.04, 0.085),
                      tilt=(-40 if az < 1 else 140, 0, 0))
        belt(rig, '#3B2A20', z=0.08, buckle=None, width=0.45)
    elif style == 'b':
        hair_shell(rig, spec['hair'], fringe=0.22, wave=0.09, waves=13.0, sweep=0.0)
        knit = M('knit', '#F4EDE0', rough=0.95)
        cap_shell(rig, knit, lambda x, y: 0.18 - 0.22 * y, base=1.13, puff=0.25, name='beanie', lumps=0.03)
        tilted_ring(rig, 'beanie_cuff', knit, HEAD_R[0] * 1.07, 0.045, 0.40, -0.04, sy=0.97, rz=1.2)
        head_obj(rig, 'pompom', g.bm_ring(0.0, 0.085, seg=24, segr=14, tufts=6, bump=0.25, seed=2.0),
                 M('pompom', '#D9483B', rough=0.95), loc=(0.0, 0.03, 0.385))
        hm = M('hair', spec['hair'], rough=0.42)
        for s in (-1, 1):
            head_obj(rig, 'pigtail', g.bm_ellipsoid(0.075, 0.065, 0.10, 16, 10), hm,
                     loc=(s * 0.31, 0.06, -0.16), rot=(0, s * 25, 0))
            head_obj(rig, 'pig_tie', g.bm_ring(0.035, 0.016, seg=16, segr=6), M('tie', '#3D7CC9', rough=0.6),
                     loc=(s * 0.27, 0.06, -0.07), rot=(0, s * 60, 0))
        belt(rig, '#F4EDE0', z=0.08, buckle=None, width=0.45)
    elif style == 'scarf':
        hair_shell(rig, spec['hair'], fringe=0.20, wave=0.05, waves=10.0, sweep=0.0)
        fur = M('ushanka', '#8A6A4A', rough=0.95)
        cap_shell(rig, M('ushanka_top', '#7A5C40', rough=0.9), lambda x, y: 0.10 - 0.12 * y, base=1.15,
                  puff=0.12, name='ushanka', lumps=0.015)
        tilted_ring(rig, 'ushanka_band', fur, HEAD_R[0] * 1.12, 0.06, 0.30, 0.02, sy=1.0, tufts=12,
                    bump=0.3, seed=4.0)
        for s in (-1, 1):
            head_obj(rig, 'earflap', g.bm_ellipsoid(0.06, 0.13, 0.15, 16, 10), fur,
                     loc=(s * 0.30, 0.03, -0.10), rot=(0, s * 12, 0))
        scarf = M('scarf', '#F2C14E', rough=0.9)
        g.mesh_obj('scarf', g.bm_ring(0.135, 0.068, seg=48, segr=12, sy=0.92), scarf, rig.j['chest'],
                   loc=(0, 0.01, 0.10))
        stripe = M('scarf_s', '#C8463D', rough=0.9)
        g.mesh_obj('scarf_s', g.bm_ring(0.135, 0.069, seg=48, segr=12, sy=0.92, rz=0.25), stripe,
                   rig.j['chest'], loc=(0, 0.01, 0.10))
        tail = g.bm_box(0.08, 0.035, 0.22, bevel=0.015)
        g.mesh_obj('scarf_tail', tail, scarf, rig.j['chest'], loc=(0.09, -0.17, -0.04), rot=(-8, 0, 8))
        for z in (-0.06, 0.03):
            g.mesh_obj('scarf_tail_s', g.bm_box(0.084, 0.037, 0.025, bevel=0.008), stripe, rig.j['chest'],
                       loc=(0.09 + 0.012 * (z + 0.04), -0.17, z - 0.04 * 0.0), rot=(-8, 0, 8))
        belt(rig, '#2E3440', z=0.08, buckle='#C9A045', width=0.45)


SPECS = {
    'player': dict(coat='#F2F0EA', fur='#E6DCCB', hair='#3A2A22', pants='#4A3830',
                   boots='#5A3A26', mitten='#6B4A2E', dress=dress_player),
    'fisherman': dict(coat='#F2C230', coat_rough=0.32, hair='#9A5A32', pants='#2E3A55',
                      boots='#2F5D50', mitten='#E8783A', hem_fur=False, cuff_fur=False,
                      boot_fur=False, hem_r=0.245, dress=dress_fisherman),
    'lumberjack': dict(coat='plaid', hair='#7A4A2A', pants='#3F5675', boots='#6B4A2E',
                       mitten='#C98F55', hem_fur=False, cuff_fur=False, boot_fur=False,
                       hem_r=0.235, hem_z=-0.06, dress=dress_lumberjack),
    'farmer': dict(coat='#F4F1E8', hair='#A0582E', pants='#4E8A3E', boots='#7A5235',
                   mitten='#F6CFAE', hem_fur=False, cuff_fur=False, boot_fur=False,
                   hem_r=0.22, hem_z=-0.05, dress=dress_farmer, blush='#F28C8C'),
    'miner': dict(coat='#9AA2AC', hair='#3A2A22', pants='#4A3B35', boots='#3B2A20',
                  mitten='#C98F55', hem_fur=False, cuff_fur=False, boot_fur=False,
                  hem_r=0.225, hem_z=-0.05, dress=dress_miner),
    'hunter': dict(coat='#4F7A3A', fur='#D9C3A0', hair='#5A3A26', pants='#5A4030', boots='#6B4A2E',
                   mitten='#6B4A2E', hem_fur=False, cuff_fur=False, hem_r=0.235, hem_z=-0.06,
                   dress=dress_hunter),
    'villager_a': dict(coat='#F2C230', fur='#F4F1EA', hair='#2A2228', pants='#2E3440', boots='#2A2A30',
                       mitten='#3B3F4A', style='a', dress=dress_villager),
    'villager_b': dict(coat='#D9483B', fur='#F4F1EA', hair='#6B4026', pants='#2E3440', boots='#7A5235',
                       mitten='#F4EDE0', style='b', dress=dress_villager),
    'villager_c': dict(coat='#3D7CC9', fur='#F4F1EA', hair='#A0703F', pants='#3B3540', boots='#4A3830',
                       mitten='#C8463D', style='scarf', dress=dress_villager, hem_fur=True),
}

HUMAN_KEYS = ['player', 'fisherman', 'lumberjack', 'farmer', 'miner', 'hunter',
              'villager_a', 'villager_b', 'villager_c']
ANIMAL_KEYS = ['deer', 'boar']
ALL_KEYS = HUMAN_KEYS + ANIMAL_KEYS


def anims_for(key):
    """(kind, {anim: {frames, fps, [impactFrame]}}) in contract order."""
    import char_anim as ca
    if key in ANIMAL_KEYS:
        return 'animal', {k: dict(v) for k, v in ca.ANIMAL_ANIMS.items()}
    H = ca.HUMAN_ANIMS
    if key == 'player':
        names = ['idle', 'walk', 'carry_idle', 'carry_walk', 'chop', 'mine', 'harvest']
    elif key.startswith('villager'):
        names = ['idle', 'walk', 'carry_walk', 'happy']
    else:
        names = ['idle', 'walk', 'carry_idle', 'carry_walk', 'work']
    out = {n: dict(H[n]) for n in names}
    if 'work' in out:
        out['work']['impactFrame'] = ca.WORK_IMPACT[key]
    return 'human', out


def build(key):
    bc.reset_scene()
    if key in ANIMAL_KEYS:
        import char_animals
        rig = char_animals.build(key)
        rig.meta['key'] = key
        return rig
    spec = dict(SPECS[key])
    if spec['coat'] == 'plaid':
        spec['coat_mat'] = mat_plaid('plaid', '#C8402F', '#5E1A17', light='#D65A45', scale=7.0)
    else:
        spec['coat_mat'] = M('coat', spec['coat'], rough=spec.get('coat_rough', 0.8))
    rig = build_human(spec)
    spec['dress'](rig, spec)
    rig.meta['key'] = key
    return rig
