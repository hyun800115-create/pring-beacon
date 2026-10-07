"""
life_assets.py - village-life props for Frost Village (CONTRACT_VILLAGERS.md section B):
snowman building stages, snowball pile, snow fort, log seats, sled, dog house, picnic
table, lantern string, kids' swing, ice rink, clothesline.

Built with the SAME helpers, palette, camera, light and PPU as the base props
(prop_lib / prop_assets / bl_common - imported read-only, never modified).
The registry LIFE maps a build key to its builder + metadata; life_render.py renders it.

Conventions (as prop_assets.py)
  * 1 unit = 1 m, world origin = footprint centre = sprite anchor.
  * Builders model in a LOCAL frame whose front is -Y.  life_render.py parents every
    object to a root empty rotated by the spec's `yaw` (degrees about Z):
        yaw   0 -> front faces screen down-left (SW, world -Y)
        yaw  45 -> front faces the camera (S)
        yaw  90 -> front faces screen down-right (SE, world +X)
        yaw -45 -> local +X faces the camera (used by the dog house: door on the +X gable)
  * Markers (bpy empties made with mark()) record interaction points: seats, hiding
    spots behind the snow fort, bulb centres, the dog-house door, the sled rope end,
    where kids stand to build the snowman.  life_render.py converts them to px offsets
    from the anchor per rendered frame.
  * A builder may return {'frames': [(frame_name, setter_or_None), ...],
    'sprites': {sprite_key: {'frame': frame_name, 'anims': {...}}}} for multi-state
    sprites (snowman stages, lantern twinkle, swing loop).  All frames of one build
    share frameSize + anchor, so the game can swap them in place.

Not run directly - see life_render.py.
"""
import math
from collections import OrderedDict

import bmesh
import bpy
from mathutils import Vector, Euler

import prop_lib as L
from prop_lib import C, flat, snowy, tonal, box, cyl, sphere, blob, log, extrude
import prop_assets as PA          # shared sub-models (snow_cap, roof_panel, arch_pts, lantern ...)

LIFE = OrderedDict()
MARKERS = []                      # (kind, empty, facing_local_vector or None)


def life(key, kind='decor', fp=None, yaw=0.0, shadow=True, samples=64, notes='', front=None, catcher=14.0,
         sprites=None, extra=None):
    """Register a builder.  fp = footprint metres (a along local X, b along local Y) or ('r', radius).
    sprites: the sprite keys this build produces (default [key])."""
    def deco(fn):
        LIFE[key] = dict(key=key, fn=fn, kind=kind, fp=fp, yaw=yaw, shadow=shadow, samples=samples,
                         notes=notes, front=front, catcher=catcher, sprites=sprites or [key], extra=extra or {})
        return fn
    return deco


# =========================================================================== helpers

def mark(kind, loc, parent=None, facing=None):
    """Interaction marker (an empty).  facing = local direction a character there looks toward."""
    em = bpy.data.objects.new('MK_%s_%d' % (kind, len(MARKERS)), None)
    bpy.context.scene.collection.objects.link(em)
    em.location = loc
    if parent is not None:
        em.parent = parent
    MARKERS.append((kind, em, None if facing is None else Vector(facing)))
    return em


def empty(name, loc=(0, 0, 0)):
    em = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(em)
    em.location = loc
    return em


def show(objs, on):
    for o in objs:
        o.hide_render = not on
        o.hide_viewport = not on


def descendants(objs):
    out = []
    for o in objs:
        out.append(o)
        out.extend(descendants(list(o.children)))
    return out


def align_y(ob, normal):
    """Rotate so the object's local +Y points along `normal` (stickers on a ball)."""
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(normal).normalized().to_track_quat('Y', 'Z')
    return ob


def on_ball(c, r, a_deg, e_deg, out=0.0):
    """Point on a sphere (centre c, radius r) at azimuth a (0 = local front -Y, + = toward +X)
    and elevation e.  Returns (point, outward normal)."""
    a, e = math.radians(a_deg), math.radians(e_deg)
    n = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    return Vector(c) + n * (r + out), n


def snow_m(base='#D6E1EE', lo=0.12, hi=0.72, amt=0.22):
    """Packed snow: bluish on the sides, white on top (same family as snow_pile_a/b)."""
    return snowy(base, snow='snow_mat', lo=lo, hi=hi, noise_amt=amt, noise_scale=2.4)


def snowball(name, r, loc, seed=0, mat=None, squash=1.0, amp=0.05, flat_bottom=0.0):
    return blob(name, r, loc, mat or snow_m(), scale=(1.0, 1.0, squash), seed=seed, amp=amp, freq=2.2,
                subdiv=4 if r > 0.15 else 3, flat_bottom=flat_bottom)


def coal_mat():
    return flat('#2B2629', 0.32)


def snow_drift(name, r, loc, seed=0, scale=(1.3, 1.0, 0.35)):
    return blob(name, r, loc, flat('snow_mat', 0.9), scale=scale, seed=seed, amp=0.22, freq=2.0, subdiv=3)


def roof(name, W, y0, z0, y1, z1, thick, mat, snow_frac=0.55, seed=0, snow_t=0.09):
    """Copy of prop_assets.roof_panel (unchanged there) that accepts either slope direction and lets
    the snow cover only the upper `snow_frac` of the panel (so a red roof stays red at the eaves)."""
    if y0 > y1:
        y0, z0, y1, z1 = y1, z1, y0, z0
    dy, dz = y1 - y0, z1 - z0
    ln = math.hypot(dy, dz)
    ang = math.degrees(math.atan2(dz, dy))
    n = Vector((0.0, -math.sin(math.radians(ang)), math.cos(math.radians(ang))))
    mid = Vector((0.0, (y0 + y1) / 2, (z0 + z1) / 2))
    out = [box(name, (W, ln, thick), tuple(mid + n * thick / 2), rot=(ang, 0, 0), mat=mat, bevel=0.03,
               origin='center')]
    if snow_frac > 0:
        up = Vector((0.0, dy, dz)).normalized()
        if dz < 0:
            up = -up                                   # toward the ridge
        sl = ln * snow_frac
        c = mid + n * (thick - 0.01) + up * (ln - sl) / 2
        out.append(L.snow_slab(name + '_snow', W - 0.08, sl, snow_t, tuple(c), rot=(ang, 0, 0), seed=seed,
                               droop=0.02))
    return out


# =========================================================================== SNOWMAN (4 stages)

SN_B = (0.0, 0.0, 0.29, 0.34)        # bottom ball: x, y, z, r
SN_M = (0.0, 0.0, 0.79, 0.255)       # middle ball
SN_H = (0.0, 0.0, 1.235, 0.25)       # head (big = cute)


def _snowman_face(head_c, rh):
    coal = coal_mat()
    shine = L.emissive('eyeshine', '#FFFFFF', '#FFFFFF', 1.2)
    objs = []
    # big round coal eyes with a sparkle
    for sgn in (-1, 1):
        p, n = on_ball(head_c, rh, sgn * 21, 17, out=-0.012)
        e = sphere('eye', 0.046, tuple(p), coal, scale=(1.0, 0.55, 1.2), segs=16, rings=10)
        align_y(e, -n)
        objs.append(e)
        q = p + n * 0.024 + Vector((-0.016, 0, 0.018))
        objs.append(sphere('shine', 0.0125, tuple(q), shine, segs=8, rings=6))
    # carrot nose (points at the viewer, tilted a little down + right)
    p, n = on_ball(head_c, rh, 4, 1, out=-0.03)
    tip = p + Vector(n) * 0.2 + Vector((0.05, 0, -0.035))
    mb = L.MB()
    mb.seg(p, tip, 0.043, flat('#F2862E', 0.55), segs=14, r2=0.006)
    objs.append(mb.done('carrot'))
    for k in (0.3, 0.55):                      # two tiny grooves
        q = p + (tip - p) * k
        objs.append(cyl('groove', 0.043 * (1 - k) + 0.004, 0.006, tuple(q), mat=flat('#C8641E', 0.6), segs=14,
                        bevel=0.0, origin='center'))
        align_z = (tip - p).normalized().to_track_quat('Z', 'Y')
        objs[-1].rotation_mode = 'QUATERNION'
        objs[-1].rotation_quaternion = align_z
    # coal smile
    for i, a in enumerate((-30, -15, 0, 15, 30)):
        e_ = -21 + 0.008 * a * a
        p, n = on_ball(head_c, rh, a, e_, out=-0.006)
        objs.append(sphere('smile', 0.019 if a else 0.021, tuple(p), coal, segs=10, rings=6))
    # rosy cheeks (soft pink stickers)
    blush = flat('#F28A98', 0.7)
    for sgn in (-1, 1):
        p, n = on_ball(head_c, rh, sgn * 42, -3, out=-0.017)
        b = sphere('blush', 0.062, tuple(p), blush, scale=(1.0, 0.3, 0.7), segs=16, rings=8)
        align_y(b, n)
        objs.append(b)
    return objs


def _bucket(name, loc, rot=(0, 0, 0), snow=True):
    """Upside-down tin pail (snowman hat).  Origin at the rim (opening) centre."""
    paint = flat('#4F86C6', 0.45, 0.15)
    rim = flat('#3F6EA8', 0.45, 0.2)
    objs = [cyl(name + '_body', 0.15, 0.2, (0, 0, 0), mat=paint, r_top=0.112, segs=28, bevel=0.012,
                cap_mat=flat('#5A93D3', 0.5, 0.15)),
            cyl(name + '_rim', 0.158, 0.035, (0, 0, -0.004), mat=rim, segs=28, bevel=0.01),
            cyl(name + '_band', 0.132, 0.025, (0, 0, 0.13), mat=rim, segs=28, bevel=0.008, r_top=0.124)]
    # wire handle dangling at the side
    mb = L.MB()
    hm = flat('#9AA4B2', 0.4, 0.6)
    pts = [Vector((0.15 * math.cos(t), 0.15 * math.sin(t) * 0.15, -0.02 - 0.09 * math.sin(t)))
           for t in [math.pi * k / 8 for k in range(9)]]
    for a, b in zip(pts, pts[1:]):
        mb.seg(a + Vector((0, -0.02, 0.05)), b + Vector((0, -0.02, 0.05)), 0.008, hm, segs=6)
    objs.append(mb.done(name + '_handle'))
    if snow:
        objs.append(PA.snow_cap(name + '_snow', 0.1, (0, 0, 0.195), 0.055, 3))
    return L.group(objs, name, loc=loc, rot=rot)


def _scarf(neck_c, r_neck):
    red = flat('#D9483B', 0.8)
    knit = L.stripes('#D9483B', '#FFF3DE', 9.0, 'Z', rough=0.85, soft=0.06)
    objs = []
    # wrap: a fat torus around the neck
    bm = bmesh.new()
    M, K = 32, 10
    R, rr = r_neck, 0.058
    verts = []
    for j in range(M):
        th = math.tau * j / M
        row = []
        for k in range(K):
            ph = math.tau * k / K
            wob = 1.0 + 0.06 * math.sin(3 * th)
            x = (R + rr * math.cos(ph)) * math.cos(th)
            y = (R + rr * math.cos(ph)) * math.sin(th)
            z = rr * 0.85 * math.sin(ph) * wob - 0.012 * math.cos(th + 0.6)
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for j in range(M):
        for k in range(K):
            bm.faces.new((verts[j][k], verts[(j + 1) % M][k], verts[(j + 1) % M][(k + 1) % K], verts[j][(k + 1) % K]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    objs.append(L.finish('scarf_wrap', bm, [red], loc=neck_c))
    # knot + two striped tails hanging at the front-right, one fluttering
    p, n = on_ball(neck_c, r_neck + 0.03, 32, 0)
    objs.append(sphere('knot', 0.06, tuple(p), red, scale=(1.0, 0.8, 0.9), segs=14, rings=10))
    for i, (ang, ln, dx) in enumerate(((10, 0.36, 0.0), (-24, 0.3, 0.05))):
        t = box('tail%d' % i, (0.11, 0.035, ln), (0, 0, -ln), mat=knit, bevel=0.015, origin='bottom')
        fr = L.MB()
        for k in range(5):
            x = -0.045 + k * 0.0225
            fr.seg((x, 0, -ln), (x, 0, -ln - 0.05), 0.007, flat('#FFF3DE', 0.8), segs=5)
        f = fr.done('fringe%d' % i)
        g = L.group([t, f], 'tailg%d' % i, loc=tuple(p + Vector((dx, -0.035, -0.01))), rot=(-12, ang, 32))
        objs.append(g)
    return objs


def _stick_arm(name, start, d, length=0.46, up=0.0):
    bark = flat('#6E4428', 0.85)
    mb = L.MB()
    d = Vector(d).normalized()
    end = Vector(start) + d * length
    mb.seg(start, end, 0.022, bark, segs=8, r2=0.013)
    side = d.cross(Vector((0, 1, 0))).normalized()
    if side.z < 0:
        side = -side
    for k, (t, sgn, ln) in enumerate(((0.62, 1, 0.12), (1.0, 1, 0.1), (1.0, -1, 0.09))):
        p = Vector(start) + d * length * t
        q = p + (d * 0.7 + side * 0.8 * sgn).normalized() * ln
        mb.seg(p, q, 0.012, bark, segs=6, r2=0.007)
    return mb.done(name)


def _shovel(name, loc, rot=(0, 0, 0)):
    """Kid's red plastic snow shovel stuck in the snow (origin = blade tip on the ground)."""
    red = flat('#E0523F', 0.45)
    wood = tonal('#C98F55', 0.08, 3.0)
    objs = [box(name + '_blade', (0.24, 0.035, 0.26), (0, 0, 0.0), mat=red, bevel=0.03),
            box(name + '_neck', (0.07, 0.05, 0.08), (0, 0, 0.24), mat=red, bevel=0.02),
            cyl(name + '_handle', 0.02, 0.5, (0, 0, 0.3), mat=wood, segs=10),
            cyl(name + '_grip', 0.026, 0.16, (0, 0, 0.82), rot=(0, 90, 0), mat=red, segs=10, origin='center')]
    objs.append(PA.snow_cap(name + '_snow', 0.09, (0.0, -0.01, 0.0), 0.06, 4, scale=(1.6, 1.2, 1.0)))
    return L.group(objs, name, loc=loc, rot=rot)


@life('snowman', kind='decor', fp=('r', 0.42), yaw=45.0, sprites=['snowman_0', 'snowman_1', 'snowman_2', 'snowman_3'],
      notes='Snowman building stages (0 gathered snow + first ball, 1 big ball + 2nd ball rolled beside it, '
            '2 three balls stacked with carrot/bucket ready on the snow, 3 finished: coal eyes + smile, carrot '
            'nose, rosy cheeks, striped red scarf, blue bucket hat, stick arms). All 4 frames share frameSize + '
            'anchor: swap the frame in place as kids build it. workPoints = where kids stand to build (anchors).')
def b_snowman():
    m = snow_m('#D9E3EF')
    with L.Collect() as c0:
        blob('heap', 0.3, (-0.05, 0.05, 0.0), m, scale=(1.35, 1.15, 0.55), seed=3, amp=0.2, freq=2.0, subdiv=4,
             flat_bottom=0.15)
        snowball('ball0', 0.17, (0.3, -0.24, 0.15), seed=11, flat_bottom=0.8)
        for i, (x, y, r) in enumerate(((-0.42, -0.2, 0.07), (0.36, 0.18, 0.06), (-0.2, -0.36, 0.05))):
            snowball('clump', r, (x, y, r * 0.5), seed=20 + i, amp=0.18)
    with L.Collect() as cb:
        x, y, z, r = SN_B
        snowball('bottom', r, (x, y, z), seed=5, squash=0.93, flat_bottom=0.82)
        for i, (a, rr) in enumerate(((200, 0.2), (300, 0.17), (40, 0.15), (120, 0.14))):
            q = (0.3 * math.cos(math.radians(a)), 0.3 * math.sin(math.radians(a)), 0.0)
            snow_drift('bdrift', rr, q, seed=8 + i, scale=(1.4, 1.2, 0.5))
    with L.Collect() as c1:
        snowball('mid_ground', SN_M[3], (0.62, -0.2, SN_M[3] * 0.92), seed=6, flat_bottom=0.85)
        snow_drift('trail', 0.22, (0.62, 0.22, 0.0), seed=9, scale=(0.9, 1.8, 0.2))
    with L.Collect() as cs:
        snowball('mid', SN_M[3], SN_M[:3], seed=6, squash=0.95)
        snowball('head', SN_H[3], SN_H[:3], seed=7, amp=0.035)
    with L.Collect() as c2:
        _bucket('bucket_g', (0.58, -0.24, 0.15), rot=(0, 90, 30), snow=False)
        mb = L.MB()
        mb.seg((0.42, -0.5, 0.045), (0.62, -0.55, 0.04), 0.04, flat('#F2862E', 0.55), segs=12, r2=0.006)
        mb.done('carrot_g')
        _stick_arm('stick_g1', (0.2, -0.62, 0.02), (1.0, 0.25, 0.0), 0.42)
        _stick_arm('stick_g2', (0.3, 0.32, 0.02), (1.0, -0.4, 0.0), 0.38)
    with L.Collect() as c3:
        hc, rh = Vector(SN_H[:3]), SN_H[3]
        mc, rm = Vector(SN_M[:3]), SN_M[3]
        _snowman_face(hc, rh)
        _scarf(Vector((0, 0, 1.0)), 0.185)
        _bucket('hat', tuple(hc + Vector((0.035, 0.02, rh * 0.78))), rot=(-8, 17, 0))
        coal = coal_mat()
        for e in (32, 2):
            p, n = on_ball(mc, rm, 0, e, out=-0.01)
            sphere('button', 0.03, tuple(p), coal, scale=(1, 0.6, 1), segs=12, rings=8)
        pr, nr = on_ball(mc, rm, 86, 14, out=-0.05)
        _stick_arm('arm_r', tuple(pr), (0.75, 0.05, 0.62), 0.46)        # waving up
        pl, nl = on_ball(mc, rm, -86, 8, out=-0.05)
        _stick_arm('arm_l', tuple(pl), (-0.85, 0.05, 0.12), 0.42)
    with L.Collect() as csh:
        _shovel('shovel', (-0.62, 0.22, 0.0), rot=(14, -24, 20))
    stages = {
        0: c0.objs + csh.objs,
        1: cb.objs + c1.objs + csh.objs,
        2: cb.objs + cs.objs + c2.objs + csh.objs,
        3: cb.objs + cs.objs + c3.objs,
    }
    every = descendants(c0.objs + cb.objs + c1.objs + cs.objs + c2.objs + c3.objs + csh.objs)
    # kids stand left / right of the snowman, a bit in front, facing it
    mark('work', (-0.72, -0.28, 0.0), facing=(1.0, 0.25, 0))
    mark('work', (0.74, -0.32, 0.0), facing=(-1.0, 0.25, 0))

    def setter(k):
        def f():
            show(every, False)
            show(descendants(stages[k]), True)
        return f
    return {'frames': [('snowman_%d' % k, setter(k)) for k in range(4)],
            'sprites': {'snowman_%d' % k: {'frame': 'snowman_%d' % k, 'stage': k} for k in range(4)}}


# =========================================================================== SNOWBALL PILE

@life('snowball_pile', kind='decor', fp=('r', 0.4),
      notes='Pyramid of ready-made snowballs on a little snow mound (ammo for snowball fights).')
def b_snowball_pile():
    m = snow_m('#DCE6F1')
    blob('mound', 0.36, (0, 0, 0), flat('snow_mat', 0.9), scale=(1.25, 1.15, 0.22), seed=4, amp=0.2, subdiv=3)
    r = 0.095
    rnd = L.rng(7)
    k = 0
    for layer, n, rad in ((0, 7, 0.21), (1, 4, 0.11), (2, 1, 0.0)):
        z = 0.06 + r + layer * r * 1.55
        for i in range(n):
            a = math.tau * i / max(1, n) + layer * 0.4
            p = (rad * math.cos(a) + rnd.uniform(-0.01, 0.01), rad * math.sin(a) + rnd.uniform(-0.01, 0.01), z)
            snowball('sb', r * rnd.uniform(0.94, 1.06), p, seed=40 + k, mat=m, amp=0.06)
            k += 1
        if layer == 0:
            snowball('sb', r, (0, 0, z), seed=60, mat=m, amp=0.06)
    for i, (x, y) in enumerate(((0.36, -0.2), (-0.3, -0.3))):
        snowball('loose', r * 0.95, (x, y, r * 0.85), seed=70 + i, mat=m, amp=0.06)


# =========================================================================== SNOW FORT

FORT_C, FORT_R, FORT_SPAN = (0.0, 1.32), 1.5, 41.0      # arc centre (local), radius, half-angle (deg)


def fort_pt(phi_deg, dr=0.0):
    p = math.radians(phi_deg)
    return Vector((FORT_C[0] + (FORT_R + dr) * math.sin(p), FORT_C[1] - (FORT_R + dr) * math.cos(p), 0.0))


@life('snow_fort', kind='decor', fp=(2.1, 0.75), yaw=45.0, front='S', catcher=12.0,
      extra={'wallHeightM': 0.68},
      notes='Low curved wall of snow bricks (~2 m, 0.68 m high) with crenels, a red pennant and snowballs. '
            'Convex side faces the camera. hidePoints = character anchors BEHIND the wall (kids hide there and '
            'throw snowballs toward screen-down); normal y-sort already draws them behind the wall, which '
            'covers them up to the chest.')
def b_snow_fort():
    rnd = L.rng(21)
    mats = [snow_m('#D5E0EE', lo=0.3, hi=0.7, amt=0.12), snow_m('#DCE6F2', lo=0.3, hi=0.7, amt=0.12),
            snow_m('#CFDBEA', lo=0.3, hi=0.7, amt=0.12)]
    h, depth = 0.235, 0.34
    n = 5
    arc_len = 2 * math.radians(FORT_SPAN) * FORT_R / n
    courses = [[(i + 0.5) / n for i in range(n)],                       # bottom: 5 bricks
               [(i + 1.0) / n for i in range(n - 1)],                   # middle: 4 bricks, offset half a brick
               [(i + 0.5) / n for i in (0, 2, 4)]]                      # top: 3 merlons (crenels between)
    for c, ts in enumerate(courses):
        for i, t in enumerate(ts):
            phi = -FORT_SPAN + 2 * FORT_SPAN * t
            p = fort_pt(phi)
            ln = arc_len * (0.95 if c < 2 else 0.84) * rnd.uniform(0.96, 1.03)
            box('brick', (ln, depth * rnd.uniform(0.94, 1.04) * (0.92 if c == 2 else 1.0), h * rnd.uniform(0.97, 1.05)),
                (p.x, p.y, c * h * 0.97), rot=(rnd.uniform(-2, 2), rnd.uniform(-2, 2), phi + rnd.uniform(-3, 3)),
                mat=mats[(i + c) % 3], bevel=0.075, segs=4)
        if c == 1:                                                       # half bricks at both ends
            for s_ in (-1, 1):
                phi = s_ * (FORT_SPAN - FORT_SPAN / n * 0.5)
                p = fort_pt(phi)
                box('halfbrick', (arc_len * 0.45, depth, h), (p.x, p.y, h * 0.97), rot=(0, 0, phi),
                    mat=mats[2], bevel=0.07, segs=4)
    # soft drift along the base, both sides
    for i, phi in enumerate((-30, -8, 14, 33)):
        p = fort_pt(phi, 0.3)
        snow_drift('drift', 0.2, (p.x, p.y, 0.0), seed=30 + i, scale=(1.4, 0.85, 0.55))
    for i, phi in enumerate((-20, 18)):
        p = fort_pt(phi, -0.28)
        snow_drift('drift_in', 0.22, (p.x, p.y, 0.0), seed=40 + i, scale=(1.4, 0.8, 0.3))
    # snowballs in the crenels + a little ammo pile inside
    sm = snow_m('#DCE6F2')
    for i, phi in enumerate((-FORT_SPAN + 2 * FORT_SPAN * 0.35, -FORT_SPAN + 2 * FORT_SPAN * 0.75)):
        p = fort_pt(phi)
        snowball('topball', 0.085, (p.x, p.y, 2 * h * 0.97 + 0.08), seed=50 + i, mat=sm)
    for i, (dp, dr, z) in enumerate(((-30, 0.42, 0.09), (-25, 0.47, 0.09), (-27.5, 0.44, 0.23), (2, -0.5, 0.09),
                                     (6, -0.46, 0.09), (4, -0.48, 0.23))):
        p = fort_pt(dp, dr)
        snowball('ammo', 0.088, (p.x, p.y, z), seed=60 + i, mat=sm)
    # pennant on a stick at the right end
    p = fort_pt(FORT_SPAN - 2, 0.02)
    cyl('flagstick', 0.016, 1.0, (p.x, p.y, 2 * h * 0.97), mat=flat('#8A5A33', 0.8), segs=8)
    pen = extrude('pennant', [(0.0, 0.0), (0.0, 0.2), (0.3, 0.1)], 0.02, rot=(90, 0, 25),
                  top=flat('#D9483B', 0.7), side=flat('#B23A30', 0.7), bevel=0.006)
    pen.location = (p.x + 0.01, p.y + 0.01, 2 * h * 0.97 + 0.76)
    sphere('flagtop', 0.026, (p.x, p.y, 2 * h * 0.97 + 1.0), flat('gold', 0.3, 0.6), segs=10, rings=6)
    # hiding spots: behind the wall (inner side), characters look toward the camera side
    for phi in (-22, 22):
        q = fort_pt(phi, -0.55)
        mark('hide', (q.x, q.y, 0.0), facing=(0, -1, 0))


# =========================================================================== LOG SEAT (3 orientations)

LOG_LEN, LOG_R, SEAT_Z = 1.6, 0.2, 0.45


def build_log_seat(seed=0):
    rnd = L.rng(seed)
    bark = tonal('#7A4C2A', 0.18, 5.0, rough=0.9)
    endm = L.end_grain(light='#EBC795', ring='#CF9F66', scale=10.0)
    zc = SEAT_Z - 0.025 - LOG_R            # log top just under the planed seat strip
    log('log', LOG_R, LOG_LEN, (0, 0, zc), rot=(0, 90, 0), bark=bark, end=endm, segs=22)
    # planed seat strip on top (light wood) so it reads as a bench
    box('seat', (LOG_LEN - 0.28, 0.21, 0.045), (0, 0.0, SEAT_Z - 0.045), mat=tonal('#D9A066', 0.08, 3.0),
        bevel=0.014)
    # two chocks underneath
    chock = tonal('#8A5A33', 0.12, 4.0)
    for sx in (-1, 1):
        box('chock', (0.16, 0.38, 0.1), (sx * (LOG_LEN / 2 - 0.25), 0, 0), mat=chock, bevel=0.03)
    # knots + a short broken branch stub
    for i, x in enumerate((-0.42, 0.18)):
        sphere('knot', 0.035, (x, -LOG_R + 0.01, zc + 0.05 * (i - 0.5)), flat('#5A3820', 0.8), scale=(1, 0.5, 1))
    mb = L.MB()
    mb.seg((0.5, LOG_R * 0.6, zc + 0.08), (0.62, LOG_R + 0.12, zc + 0.2), 0.03, bark, segs=8, r2=0.022)
    mb.done('stub')
    # snow: on the log ends (not on the seat spots) + drifts against the chocks
    for sx in (-1, 1):
        PA.snow_cap('endsnow', 0.12, (sx * (LOG_LEN / 2 - 0.08), 0.0, SEAT_Z - 0.01), 0.06, 3 + sx,
                    scale=(0.9, 1.1, 1.0))
        snow_drift('drift', 0.18, (sx * (LOG_LEN / 2 - 0.15), 0.12 * sx, 0.0), seed=10 + sx, scale=(1.4, 1.2, 0.4))
    # seats: front-centre of the seat surface (front = local -Y)
    for x in (-0.4, 0.4):
        mark('seat', (x, -0.1, SEAT_Z), facing=(0, -1, 0))


LOG_NOTE = ('Log bench for the campfire circle: 1.6 m log on two chocks, planed seat at 0.45 m. '
            'seatPoints = where a sitting villager anchor goes (seat front-centre, 2 seats); seatDirs = which way '
            'the sitter faces; seatDepth "front" = draw the sitter just above the log (depth = log depth + 1). ')


@life('log_seat', kind='decor', fp=(1.6, 0.45), yaw=45.0, front='S',
      extra={'seatDepth': 'front', 'seatHeightM': SEAT_Z},
      notes=LOG_NOTE + 'This one runs screen-horizontal: sitters face the camera (S). Put it on the far side of a '
                       'campfire.')
def b_log_seat():
    build_log_seat(1)


@life('log_seat_x', kind='decor', fp=(1.6, 0.45), yaw=0.0, front='-Y',
      extra={'seatDepth': 'front', 'seatHeightM': SEAT_Z},
      notes=LOG_NOTE + 'Runs along world X (screen down-right): sitters face SW (use sit_SE flipped). Put it on the '
                       'upper-right side of a campfire.')
def b_log_seat_x():
    build_log_seat(2)


@life('log_seat_y', kind='decor', fp=(1.6, 0.45), yaw=90.0, front='+X',
      extra={'seatDepth': 'front', 'seatHeightM': SEAT_Z},
      notes=LOG_NOTE + 'Runs along world Y (screen up-right): sitters face SE. Put it on the upper-left side of a '
                       'campfire.')
def b_log_seat_y():
    build_log_seat(3)


# =========================================================================== SLED

@life('sled', kind='decor', fp=(1.25, 0.55), yaw=0.0, front='+X',
      notes="Kids' wooden sled: slatted deck on red curled runners, red rope. Curl/front points screen down-right "
            '(world +X). pullPoint = rope loop on the snow (where a kid holds it when pulling).')
def b_sled():
    red = flat('#D9483B', 0.45, 0.1)
    for sy in (-1, 1):
        y = sy * 0.21
        L.smooth_tube('runner', [(-0.56, y, 0.03), (0.25, y, 0.03), (0.5, y, 0.05), (0.64, y, 0.17), (0.6, y, 0.3),
                                 (0.5, y, 0.31), (0.46, y, 0.24)], 0.028, red, res=8)
        for x in (-0.38, 0.0, 0.32):
            box('strut', (0.05, 0.04, 0.16), (x, y, 0.03), mat=red, bevel=0.012)
        box('rail', (1.0, 0.07, 0.06), (-0.05, y, 0.17), mat=tonal('#B97A43', 0.08, 3.0), bevel=0.02)
    cols = ['#D9A066', '#CC9258', '#E0AA72', '#D39556', '#C98A50', '#DDA56C']
    for i in range(6):
        x = -0.48 + i * 0.165
        box('slat', (0.13, 0.56, 0.035), (x, 0, 0.22), mat=flat(cols[i], 0.75), bevel=0.014)
    # front bumper bar (steering bar)
    cyl('bar', 0.03, 0.6, (0.38, 0, 0.26), rot=(90, 0, 0), mat=tonal('#B97A43', 0.08, 3.0), segs=12,
        origin='center', cap_mat=L.end_grain())
    # rope from the bar ends to a loop on the snow in front
    rope = flat('#F2F0EA', 0.85)
    ropr = flat('#D9483B', 0.8)
    pts = [(0.4, -0.29, 0.26), (0.62, -0.22, 0.08), (0.85, -0.05, 0.02), (0.95, 0.1, 0.02), (0.82, 0.24, 0.02),
           (0.62, 0.22, 0.08), (0.4, 0.29, 0.26)]
    L.smooth_tube('rope', pts, 0.016, ropr, res=10)
    sphere('ropeknot', 0.03, (0.95, 0.1, 0.03), rope, segs=10, rings=6)
    # snow dusting on the deck + tiny drift
    PA.snow_cap('decksnow', 0.14, (-0.32, 0.08, 0.235), 0.05, 2, scale=(1.4, 1.1, 1.0))
    PA.snow_cap('decksnow2', 0.08, (0.18, -0.14, 0.235), 0.04, 5)
    snow_drift('drift', 0.16, (-0.55, 0.05, 0.0), seed=3, scale=(0.9, 1.5, 0.5))
    mark('pull', (0.95, 0.1, 0.0))


# =========================================================================== DOG HOUSE

@life('dog_house', kind='decor', fp=(1.0, 0.9), yaw=-45.0, front='S', catcher=10.0,
      notes='Small dog house: red gabled roof with snow, light plank walls, arched door facing the camera, '
            'bone-shaped name plate (no text), food bowl + bone. doorPoint = where the dog sits/lies in front '
            'of the door (pet anchor).')
def b_dog_house():
    # local frame: door on the +X gable (yaw -45 turns +X toward the camera); ridge along X
    W, D, wall = 0.92, 0.82, 0.52          # W along X (depth from camera), D along Y (width on screen)
    ridge = 0.98
    walls = L.stripes('#E3B47A', '#D5A169', 7.0, 'Y', rough=0.8, soft=0.04)
    box('walls', (W, D, wall), (0, 0, 0.0), mat=walls, bevel=0.025)
    box('base', (W + 0.06, D + 0.06, 0.07), (0, 0, 0.0), mat=flat('#B57A43', 0.8), bevel=0.02)
    # gables (triangles) front and back
    for sx in (-1, 1):
        g = extrude('gable', [(-D / 2, 0.0), (D / 2, 0.0), (0.0, ridge - wall)], 0.06, rot=(90, 0, 90), top=walls,
                    side=walls, bevel=0.015)
        g.location = (sx * W / 2 - 0.03, 0, wall - 0.005)
    # roof: two red panels along X sloping to +-Y, eave overhang, snow
    roofm = L.stripes('#D9483B', '#BF3D33', 3.5, 'Y', rough=0.7, soft=0.05)
    over = 0.13
    eave = wall - over * (ridge - wall) / (D / 2)
    roof('roofL', W + 0.24, -D / 2 - over, eave, 0.0, ridge, 0.07, roofm, snow_frac=0.5, seed=3)
    roof('roofR', W + 0.24, D / 2 + over, eave, 0.0, ridge, 0.07, roofm, snow_frac=0.42, seed=4)
    log('ridge', 0.045, W + 0.3, (0, 0, ridge + 0.05), rot=(0, 90, 0), bark=flat('#B23A30', 0.7),
        end=flat('#B23A30', 0.7), segs=12)
    L.snow_slab('ridgesnow', W + 0.22, 0.2, 0.07, (0, 0, ridge + 0.06), seed=6)
    # arched door on the +X gable
    fx = W / 2 + 0.005
    trim = flat('#FFF3DE', 0.7)
    fr = extrude('doorframe', PA.arch_pts(0.42, 0.5, 14), 0.03, rot=(90, 0, 90), top=trim, side=trim, bevel=0.01)
    fr.location = (fx + 0.0, 0, 0.065)
    dk = flat('#2E2226', 0.95)
    hole = extrude('door', PA.arch_pts(0.34, 0.44, 14), 0.03, rot=(90, 0, 90), top=dk, side=dk, bevel=0.0)
    hole.location = (fx + 0.015, 0, 0.065)
    # bone-shaped name plate above the door
    plate = flat('#FFF8EC', 0.6)
    pz = 0.68
    box('plate', (0.03, 0.2, 0.065), (fx + 0.035, 0, pz - 0.0325), mat=plate, bevel=0.02, origin='bottom')
    for sy in (-1, 1):
        for sz in (-1, 1):
            sphere('bonek', 0.036, (fx + 0.04, sy * 0.105, pz + sz * 0.024), plate, scale=(0.6, 1, 1), segs=12,
                   rings=8)
    # bowl with kibble + a bone on the snow
    bowl = flat('#3D7CC9', 0.4, 0.1)
    cyl('bowl', 0.12, 0.075, (fx + 0.36, -0.36, 0), mat=bowl, r_top=0.14, segs=24, bevel=0.015,
        cap_mat=flat('#8A5A33', 0.8))
    rnd = L.rng(4)
    for i in range(7):
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(0, 0.08)
        sphere('kib', 0.022, (fx + 0.36 + rr * math.cos(a), -0.36 + rr * math.sin(a), 0.08), flat('#9A5A2E', 0.8),
               segs=8, rings=5)
    bone = flat('#FFF3DE', 0.6)
    bx, by = fx + 0.36, 0.42
    cyl('bone', 0.025, 0.2, (bx, by, 0.03), rot=(90, 0, 20), mat=bone, segs=10, origin='center')
    for s in (-1, 1):
        for t in (-1, 1):
            sphere('bonek', 0.03, (bx + s * 0.034 + t * 0.012, by + s * 0.094 - t * 0.008, 0.03), bone, segs=10,
                   rings=6)
    # snow drifts around the base
    snow_drift('d1', 0.2, (-0.35, -0.5, 0.0), seed=11, scale=(1.4, 0.9, 0.5))
    snow_drift('d2', 0.17, (-0.5, 0.45, 0.0), seed=12, scale=(1.3, 1.0, 0.5))
    mark('door', (fx + 0.32, 0.02, 0.0), facing=(1, 0, 0))


# =========================================================================== PICNIC TABLE

@life('picnic_table', kind='decor', fp=(1.8, 1.55), yaw=45.0, front='S', catcher=12.0,
      extra={'seatDepth': 'behind', 'seatHeightM': 0.45, 'tableHeightM': 0.7},
      notes='Picnic table with attached benches (table 0.70 m, seats 0.45 m), snow on top and two cocoa mugs. '
            'Long axis runs screen-horizontal. seatPoints are on the FAR bench only (sitters face the camera, S); '
            'seatDepth "behind" = normal y-sort, the table top then hides their laps.')
def b_picnic_table():
    TL, TD, TZ = 1.7, 0.72, 0.70
    BZ, BY, BD = 0.45, 0.63, 0.3
    planks = ['#D9A066', '#CC9258', '#D39556']
    for i in range(3):
        y = -TD / 2 + TD / 6 + i * TD / 3
        box('top', (TL, TD / 3 - 0.02, 0.055), (0, y, TZ - 0.055), mat=flat(planks[i], 0.75), bevel=0.018)
    for sy in (-1, 1):
        for i in range(2):
            y = sy * BY + (i - 0.5) * BD / 2
            box('bench', (TL + 0.1, BD / 2 - 0.02, 0.05), (0, y, BZ - 0.05), mat=flat(planks[(i + 1) % 3], 0.75),
                bevel=0.016)
    leg = tonal('#B57A43', 0.08, 3.0)
    for sx in (-1, 1):
        x = sx * (TL / 2 - 0.25)
        box('cross', (0.08, 2 * BY + BD, 0.07), (x, 0, BZ - 0.12), mat=leg, bevel=0.02)
        box('cross_top', (0.08, TD - 0.05, 0.06), (x, 0, TZ - 0.115), mat=leg, bevel=0.02)
        for sy in (-1, 1):
            a = Vector((x, sy * (BY + 0.02), 0.0))
            b = Vector((x, sy * 0.12, TZ - 0.06))
            ln = (b - a).length
            ang = math.degrees(math.atan2(b.y - a.y, b.z - a.z))
            box('leg', (0.08, 0.1, ln), tuple(a), rot=(-ang, 0, 0), mat=leg, bevel=0.02)
    # snow: on the table ends and on the near bench (the far bench stays clear for sitters)
    PA.snow_cap('tsnow1', 0.15, (-0.6, 0.06, TZ - 0.012), 0.08, 3, scale=(1.25, 1.3, 1.0))
    PA.snow_cap('tsnow2', 0.09, (0.68, -0.1, TZ - 0.012), 0.06, 4, scale=(1.2, 1.2, 1.0))
    PA.snow_cap('bsnow', 0.11, (0.42, -BY, BZ - 0.012), 0.065, 5, scale=(1.7, 0.95, 1.0))
    PA.snow_cap('bcap', 0.1, (-0.75, BY, BZ - 0.005), 0.04, 6, scale=(1.3, 1.0, 1.0))
    # two cocoa mugs with marshmallows
    for i, (x, y, col) in enumerate(((-0.12, -0.05, '#D9483B'), (0.22, 0.08, '#4F86C6'))):
        cyl('mug', 0.055, 0.1, (x, y, TZ), mat=flat(col, 0.45), segs=20, bevel=0.012, cap_mat=flat('#6B3A22', 0.4))
        bpy_t = L.MB()
        pts = [Vector((x + 0.055 + 0.035 * math.sin(math.pi * k / 6), y, TZ + 0.02 + 0.06 * k / 6)) for k in range(7)]
        for a, b in zip(pts, pts[1:]):
            bpy_t.seg(a, b, 0.011, flat(col, 0.45), segs=6)
        bpy_t.done('handle')
        sphere('mallow', 0.018, (x - 0.01, y - 0.01, TZ + 0.1), flat('#FFF8EC', 0.6), segs=8, rings=6)
    snow_drift('d1', 0.17, (-0.98, -0.5, 0.0), seed=13, scale=(1.3, 1.0, 0.55))
    for x in (-0.42, 0.42):
        mark('seat', (x, BY - BD / 2 + 0.01, BZ), facing=(0, -1, 0))


# =========================================================================== LANTERN STRING

LS_X, LS_TOP, LS_SAG = 1.6, 2.12, 0.42
BULB_COLS = ['#FFB21F', '#FF6A3D', '#FFD23F', '#FF5C7A', '#FF9A2E']
BULB_E = 1.25                      # emission at full brightness (kept low so colours do not clip to white)
TWINKLE = [1.0, 0.5, 0.1, 0.5]


def ls_z(x):
    return LS_TOP - LS_SAG * (1.0 - (x / LS_X) ** 2)


@life('lantern_string', kind='decor', fp=(3.4, 0.3), yaw=45.0, front='S', catcher=12.0,
      notes='Two wooden posts with a sagging string of warm glowing bulbs (festive plaza decor), runs '
            'screen-horizontal. anims.twinkle = 4-frame chase loop (frame 0 = the static frame). fxPoints.bulbs '
            '= bulb centres (px from the anchor) if the game wants extra fx_glow (ADD blend) on top.')
def b_lantern_string():
    post = tonal('#7A4E2C', 0.1, 4.0)
    wire = flat('#3A2A22', 0.7)
    for sx in (-1, 1):
        x = sx * LS_X
        box('base', (0.32, 0.32, 0.16), (x, 0, 0), mat=snowy('stone', lo=0.6, hi=0.8), bevel=0.045)
        cyl('post', 0.075, LS_TOP + 0.02, (x, 0, 0.14), mat=post, segs=14, cap_mat=L.end_grain())
        for zz in (0.95, 1.35):                                      # festive red ribbon bands
            cyl('ribbon', 0.079, 0.07, (x, 0, zz), mat=flat('#D9483B', 0.6), segs=14, bevel=0.01)
        box('cap', (0.18, 0.18, 0.05), (x, 0, LS_TOP + 0.15), mat=flat('#6B4226', 0.8), bevel=0.02)
        PA.snow_cap('psnow', 0.1, (x, 0, LS_TOP + 0.195), 0.05, 2 + sx)
        cyl('hook', 0.012, 0.12, (x - sx * 0.06, 0, LS_TOP + 0.02), rot=(0, 90, 0), mat=flat('iron', 0.5, 0.6),
            origin='center')
        snow_drift('drift', 0.2, (x + 0.08, 0.05, 0.0), seed=5 + sx, scale=(1.3, 1.1, 0.4))
    # sagging wire (smooth)
    n = 24
    pts = [(-LS_X + 0.12 + (2 * LS_X - 0.24) * k / n, 0.0, 0.0) for k in range(n + 1)]
    pts = [(x, 0.0, ls_z(x)) for x, _, _ in pts]
    L.smooth_tube('wire', pts, 0.011, wire, res=4)
    bulbs = []
    NB_ = 11
    for i in range(NB_):
        x = -LS_X + 0.35 + (2 * LS_X - 0.7) * i / (NB_ - 1)
        z = ls_z(x)
        col = BULB_COLS[i % len(BULB_COLS)]
        m = L.emissive('bulb%d' % i, col, col, BULB_E, rough=0.3)
        cyl('socket', 0.026, 0.05, (x, 0, z - 0.055), mat=flat('#2E3A2E', 0.6), segs=10)
        b = sphere('bulb', 0.074, (x, 0, z - 0.125), m, scale=(1.0, 1.0, 1.2), segs=16, rings=10)
        b.visible_shadow = False
        bulbs.append(m)
        mark('bulb', (x, 0, z - 0.125))
    # light snow resting on the wire near the posts
    for sx in (-1, 1):
        x = sx * (LS_X - 0.3)
        PA.snow_cap('wsnow', 0.05, (x, 0, ls_z(x) + 0.008), 0.025, 7 + sx, scale=(1.6, 0.6, 1.0))

    def tw(f):
        def s():
            for i, m in enumerate(bulbs):
                L.set_emission(m, BULB_E * TWINKLE[(i + f) % 4])
        return s
    names = ['lantern_string'] + ['lantern_string_twinkle_%d' % k for k in (1, 2, 3)]
    return {'frames': [(names[k], tw(k)) for k in range(4)],
            'sprites': {'lantern_string': {'frame': 'lantern_string',
                                           'anims': {'twinkle': {'frames': names, 'fps': 4, 'repeat': -1}}}},
            'glow': {nm: [TWINKLE[(i + k) % 4] for i in range(NB_)] for k, nm in enumerate(names)}}


# =========================================================================== KIDS' SWING

SW_BEAM, SW_HALF, SW_SEAT = 1.95, 0.85, 0.45
SW_AMP = 26.0


@life('kids_swing', kind='decor', fp=(2.0, 1.3), yaw=45.0, front='S', catcher=14.0,
      extra={'seatDepth': 'front', 'seatHeightM': SW_SEAT},
      notes="Kids' A-frame swing (beam 2 m) with a red seat at 0.45 m; sitters face the camera (S). "
            'anims.swing = 8-frame pendulum loop (frame names repeat; only 4 extra images). seatPoints = rest '
            'seat; anims.swing.seatPoints[i] = seat point in frame i -> move the sitting kid with it '
            '(seatDepth "front": draw the kid just above the swing).')
def b_kids_swing():
    wood = tonal('#B97A43', 0.1, 3.0)
    endm = L.end_grain(light='#EBC795', ring='#CF9F66', scale=10.0)
    log('beam', 0.085, 2 * SW_HALF + 0.35, (0, 0, SW_BEAM), rot=(0, 90, 0), bark=wood, end=endm, segs=16)
    mb = L.MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.seg((sx * (SW_HALF + 0.05), sy * 0.62, 0.0), (sx * SW_HALF, 0.0, SW_BEAM + 0.04), 0.075, wood,
                   segs=12, r2=0.065)
        mb.seg((sx * (SW_HALF + 0.03), -0.36, 0.85), (sx * (SW_HALF + 0.03), 0.36, 0.85), 0.04, wood, segs=10)
    mb.done('legs')
    for sx in (-1, 1):
        for sy in (-1, 1):
            snow_drift('foot', 0.12, (sx * (SW_HALF + 0.05), sy * 0.62, 0.0), seed=3 + sx + 2 * sy,
                       scale=(1.3, 1.3, 0.5))
    L.snow_slab('beamsnow', 2 * SW_HALF + 0.2, 0.1, 0.05, (0, 0, SW_BEAM + 0.06), seed=8)
    # swinging part: ropes + seat under a pivot on the beam axis
    piv = empty('swing_pivot', (0, 0, SW_BEAM - 0.02))
    rope = flat('#D9C39A', 0.85)
    parts = []
    L_ = SW_BEAM - 0.02 - (SW_SEAT - 0.02)
    for sx in (-1, 1):
        r = cyl('rope', 0.017, L_, (sx * 0.26, 0, -L_), mat=rope, segs=8, bevel=0.0)
        parts.append(r)
        parts.append(cyl('ring', 0.032, 0.045, (sx * 0.26, 0, -0.02), mat=flat('iron', 0.5, 0.6), segs=12,
                         bevel=0.008))
    parts.append(box('seat', (0.64, 0.26, 0.055), (0, 0, -L_ - 0.055 + 0.02), mat=flat('#D9483B', 0.55),
                     bevel=0.02))
    for o in parts:
        o.parent = piv
    mark('seat', (0, -0.12, -L_ + 0.02), parent=piv, facing=(0, -1, 0))

    def setter(th):
        def f():
            piv.rotation_euler = Euler((math.radians(th), 0, 0), 'XYZ')
        return f
    a, b = SW_AMP, SW_AMP * 0.7071
    fr = [('kids_swing', setter(0.0)), ('kids_swing_sw_a', setter(-a)), ('kids_swing_sw_b', setter(-b)),
          ('kids_swing_sw_c', setter(b)), ('kids_swing_sw_d', setter(a))]
    loop = ['kids_swing_sw_a', 'kids_swing_sw_b', 'kids_swing', 'kids_swing_sw_c', 'kids_swing_sw_d',
            'kids_swing_sw_c', 'kids_swing', 'kids_swing_sw_b']
    return {'frames': fr,
            'sprites': {'kids_swing': {'frame': 'kids_swing',
                                       'anims': {'swing': {'frames': loop, 'fps': 5, 'repeat': -1}}}},
            'rest': setter(0.0)}


# =========================================================================== ICE RINK (flat)

def rink_outline(n=48, a=1.6, b=1.05):
    pts = []
    for k in range(n):
        t = math.tau * k / n
        w = 1.0 + 0.06 * math.sin(3 * t + 1.0) + 0.035 * math.sin(5 * t + 2.0)
        pts.append((a * w * math.cos(t), b * w * math.sin(t)))
    return pts


@life('ice_rink', kind='decal', fp=(3.4, 2.3), yaw=45.0, catcher=10.0,
      notes='Frozen pond for skating / sliding kids: glossy pale-blue ice with skate swirls and a soft snow rim '
            '(~0.1 m). Flat: draw it on the ground layer UNDER characters (not y-sorted with them). footprint = '
            'the walkable ice area.')
def b_ice_rink():
    nb = L.NB('rink_ice', rough=0.12)
    nb.p.inputs['Coat Weight'].default_value = 0.6
    nb.p.inputs['Coat Roughness'].default_value = 0.05
    nb.p.inputs['Emission Color'].default_value = nb.rgb('#CFEBFF', raw=True)
    nb.p.inputs['Emission Strength'].default_value = 0.12
    tone = nb.map_range(nb.noise(1.3, 2.0), 0.3, 0.7)
    col = nb.mix_rgb(tone, C('#86BDE3'), C('#B8DDF5'))
    frost = nb.map_range(nb.noise(9.0, 3.0), 0.62, 0.72)
    col = nb.mix_rgb(nb.math('MULTIPLY', frost, 0.55), col, C('#E6F3FC'))
    nb.base(col)
    out = rink_outline()
    extrude('ice', out, 0.03, top=nb.m, side=flat('#7FB2D8', 0.3), bevel=0.0)
    # skate swirls (thin white scratches)
    scr = L.emissive('scratch', '#F4FAFF', '#FFFFFF', 0.25, rough=0.5)
    mb = L.MB()
    for (cx, cy, rx, ry, a0, a1) in ((-0.55, 0.05, 0.55, 0.32, 0.2, 5.6), (0.45, -0.1, 0.6, 0.34, 3.4, 8.9),
                                     (0.1, 0.25, 0.9, 0.42, 3.6, 5.6)):
        pts = [Vector((cx + rx * math.cos(t), cy + ry * math.sin(t), 0.034))
               for t in [a0 + (a1 - a0) * k / 28 for k in range(29)]]
        for p, q in zip(pts, pts[1:]):
            mb.seg(p, q, 0.009, scr, segs=4)
    mb.done('swirls')
    # snow rim (tube along the outline) + lumps
    rim = [(x * 1.03, y * 1.04, 0.03) for x, y in out] + [(out[0][0] * 1.03, out[0][1] * 1.04, 0.03)]
    L.smooth_tube('rim', rim, 0.1, flat('snow_mat', 0.9), res=3)
    rnd = L.rng(9)
    for k in range(0, len(out), 3):
        x, y = out[k]
        snow_drift('lump', rnd.uniform(0.1, 0.17), (x * 1.08, y * 1.09, 0.0), seed=20 + k,
                   scale=(1.4, 1.1, 0.55))


# =========================================================================== CLOTHESLINE

CL_X, CL_Z = 1.25, 1.62


def cl_z(x):
    return CL_Z - 0.13 * (1.0 - (x / CL_X) ** 2)


def _cloth(name, pts, col, x, thick=0.035, tex=None):
    """2D outline in (x, z) hanging from the line at local x; extruded toward the camera (-Y)."""
    m = tex or tonal(col, 0.08, 6.0, rough=0.9)
    ob = extrude(name, pts, thick, rot=(90, 0, 0), top=m, side=flat(col, 0.9), bevel=0.012)
    ob.location = (x, thick / 2, cl_z(x))
    return ob


@life('clothesline', kind='decor', fp=(2.8, 0.4), yaw=45.0, front='S', catcher=12.0,
      notes='Two T-posts with a washing line: red mittens, a blue sweater, a striped scarf and yellow socks '
            '(cosy village life). Runs screen-horizontal.')
def b_clothesline():
    post = tonal('#8A5A33', 0.1, 4.0)
    for sx in (-1, 1):
        x = sx * CL_X
        cyl('post', 0.055, CL_Z + 0.12, (x, 0, 0), mat=post, segs=12, cap_mat=L.end_grain())
        box('tbar', (0.08, 0.5, 0.07), (x, 0, CL_Z), mat=post, bevel=0.02)
        PA.snow_cap('psnow', 0.07, (x, 0, CL_Z + 0.12), 0.04, 3 + sx)
        L.snow_slab('tsnow', 0.06, 0.45, 0.035, (x, 0, CL_Z + 0.07), seed=4 + sx)
        snow_drift('drift', 0.18, (x + 0.06, 0.04, 0.0), seed=5 + sx, scale=(1.3, 1.1, 0.4))
    n = 20
    pts = [(-CL_X + 2 * CL_X * k / n, 0.0, 0.0) for k in range(n + 1)]
    L.smooth_tube('line', [(x, -0.02, cl_z(x)) for x, _, _ in pts], 0.009, flat('#F2F0EA', 0.8), res=4)
    peg = flat('#D9A066', 0.7)

    def pegs(x0, x1):
        for x in (x0, x1):
            box('peg', (0.025, 0.03, 0.08), (x, -0.04, cl_z(x) - 0.05), mat=peg, bevel=0.008)

    # red mittens
    mit = [(-0.08, 0.0), (0.08, 0.0), (0.085, -0.17), (0.07, -0.25), (0.0, -0.29), (-0.07, -0.25), (-0.09, -0.17),
           (-0.13, -0.12), (-0.15, -0.07), (-0.12, -0.05), (-0.08, -0.08)]
    for i, x in enumerate((-0.92, -0.68)):
        pts_ = [(-px, pz) for px, pz in mit][::-1] if i == 1 else mit
        _cloth('mitten', pts_, '#D9483B', x, 0.05)
        box('cuff', (0.18, 0.06, 0.06), (x, -0.005, cl_z(x) - 0.05), mat=flat('#FFF3DE', 0.9), bevel=0.02)
        pegs(x - 0.04, x + 0.04)
    # blue sweater with a cream band
    sw = [(-0.18, 0.0), (-0.06, 0.0), (0.0, -0.04), (0.06, 0.0), (0.18, 0.0), (0.34, -0.12), (0.28, -0.2),
          (0.19, -0.12), (0.19, -0.46), (-0.19, -0.46), (-0.19, -0.12), (-0.28, -0.2), (-0.34, -0.12)]
    x = -0.22
    _cloth('sweater', [(px, pz) for px, pz in sw][::-1], '#3D7CC9', x, 0.05)
    box('band', (0.39, 0.06, 0.07), (x, -0.012, cl_z(x) - 0.3), mat=flat('#FFF3DE', 0.9), bevel=0.01)
    for k in (-1, 0, 1):
        sphere('dot', 0.022, (x + k * 0.11, -0.04, cl_z(x) - 0.265), flat('#D9483B', 0.8), segs=8, rings=6)
    pegs(x - 0.14, x + 0.14)
    # striped scarf folded over the line
    knit = L.stripes('#F2C230', '#D9483B', 7.0, 'Z', rough=0.9, soft=0.05)
    x = 0.36
    for k, (dx, ln) in enumerate(((-0.05, 0.62), (0.07, 0.5))):
        b = box('scarf', (0.12, 0.035, ln), (x + dx, -0.02 + 0.03 * k, cl_z(x) - ln + 0.01), mat=knit, bevel=0.012)
        fr = L.MB()
        for j in range(5):
            xx = x + dx - 0.045 + j * 0.0225
            fr.seg((xx, -0.02 + 0.03 * k, cl_z(x) - ln + 0.015), (xx, -0.02 + 0.03 * k, cl_z(x) - ln - 0.04), 0.007,
                   flat('#F2C230', 0.8), segs=5)
        fr.done('fringe')
    pegs(x - 0.06, x + 0.08)
    # yellow socks
    sock = [(-0.05, 0.0), (0.05, 0.0), (0.05, -0.2), (0.12, -0.25), (0.12, -0.3), (0.0, -0.3), (-0.05, -0.25)]
    for i, x in enumerate((0.72, 0.9)):
        _cloth('sock', [(px, pz) for px, pz in sock][::-1], '#F2C230', x, 0.04)
        box('stripe', (0.105, 0.05, 0.03), (x, -0.005, cl_z(x) - 0.07), mat=flat('#3D7CC9', 0.8), bevel=0.008)
        pegs(x, x)


# =========================================================================== EXTRAS: igloo, notice board, music stand

@life('igloo', kind='decor', fp=('r', 1.0), yaw=45.0, front='S', catcher=12.0,
      notes="Kids' snow-brick igloo (1.6 m dome, 0.95 m tall) with an entrance tunnel facing the camera. "
            'doorPoint = in front of the tunnel (a kid can pop in / out: fade the sprite at the door).')
def b_igloo():
    rnd = L.rng(31)
    mats = [snow_m('#D5E0EE', lo=0.25, hi=0.75, amt=0.12), snow_m('#DCE6F2', lo=0.25, hi=0.75, amt=0.12),
            snow_m('#CFDBEA', lo=0.25, hi=0.75, amt=0.12)]
    R = 0.8
    rings = [(0.0, 12), (0.24, 11), (0.47, 10), (0.66, 8), (0.8, 6)]          # (elevation fraction, blocks)
    for r_i, (ef, n) in enumerate(rings):
        el = ef * math.pi / 2 * 0.86
        rr = R * math.cos(el)
        z = R * math.sin(el) * 1.15
        for i in range(n):
            a = math.tau * (i + 0.5 * (r_i % 2)) / n
            if r_i < 2 and abs(((a - math.radians(-90)) + math.pi) % math.tau - math.pi) < 0.42:
                continue                                              # leave the doorway open (local -Y)
            ln = math.tau * rr / n * 0.95
            box('iblk', (ln, 0.3, 0.27), (rr * math.cos(a), rr * math.sin(a), z - 0.02),
                rot=(-math.degrees(el) * 0.9, 0, math.degrees(a) + 90 + rnd.uniform(-3, 3)),
                mat=mats[(i + r_i) % 3], bevel=0.075, segs=4, origin='center')
    blob('icap', 0.24, (0, 0, R * 1.12), mats[1], scale=(1.0, 1.0, 0.55), seed=7, amp=0.08, subdiv=3)
    blob('inner', R * 0.92, (0, 0, 0.0), flat('#C9D6E8', 0.9), scale=(1.0, 1.0, 1.1), seed=3, amp=0.02, subdiv=3)
    # entrance tunnel (arch of blocks) + dark doorway
    dk = flat('#2A3550', 0.95)
    hole = extrude('idoor', PA.arch_pts(0.46, 0.56, 14), 0.05, rot=(90, 0, 0), top=dk, side=dk, bevel=0.0)
    hole.location = (0, -R - 0.28, 0.0)
    for k, y in enumerate((-R - 0.06, -R - 0.32)):
        for s_ in (-1, 1):
            box('tblk', (0.18, 0.26, 0.3), (s_ * 0.33, y, 0.0), rot=(0, 0, rnd.uniform(-3, 3)), mat=mats[k],
                bevel=0.06, segs=3)
            box('tblk2', (0.17, 0.25, 0.22), (s_ * 0.3, y, 0.29), rot=(0, s_ * 18, 0), mat=mats[k + 1], bevel=0.06,
                segs=3)
        box('ttop', (0.42, 0.26, 0.14), (0, y, 0.52), mat=mats[(k + 2) % 3], bevel=0.06, segs=3)
    for i, a in enumerate((20, 70, 140, 200, 250, 320)):
        p = (R * 1.02 * math.cos(math.radians(a)), R * 1.02 * math.sin(math.radians(a)), 0.0)
        snow_drift('idrift', 0.2, p, seed=40 + i, scale=(1.4, 1.1, 0.5))
    snowball('iball', 0.11, (0.62, -0.85, 0.1), seed=9)
    mark('door', (0.0, -R - 0.75, 0.0), facing=(0, -1, 0))


@life('notice_board', kind='decor', fp=(1.4, 0.4), yaw=45.0, front='S', catcher=12.0,
      notes='Village notice board (blank pinned notes, no baked text) under a small red roof: a natural chat '
            'spot. gatherPoints = where 2-3 villagers stand to read / chat (anchors; gatherDirs = facing).')
def b_notice_board():
    post = tonal('#8A5A33', 0.1, 4.0)
    for sx in (-1, 1):
        cyl('post', 0.06, 1.8, (sx * 0.62, 0, 0), mat=post, segs=12, cap_mat=L.end_grain())
        snow_drift('drift', 0.15, (sx * 0.62 + 0.05, 0.05, 0.0), seed=3 + sx, scale=(1.3, 1.1, 0.5))
    board = L.stripes('#D9A066', '#CC9258', 6.0, 'Z', rough=0.8, soft=0.03)
    box('board', (1.22, 0.07, 0.82), (0, -0.04, 0.82), mat=board, bevel=0.025)
    fr = flat('#8A5A33', 0.8)
    for z in (0.8, 1.64):
        box('rail', (1.32, 0.09, 0.06), (0, -0.06, z), mat=fr, bevel=0.02)
    roofm = L.stripes('#D9483B', '#BF3D33', 4.0, 'X', rough=0.7, soft=0.05)
    roof('nroof', 1.55, -0.38, 1.76, 0.22, 1.9, 0.05, roofm, snow_frac=0.6, seed=5, snow_t=0.07)
    # pinned notes: cream / pale blue / pale pink with faint scribble lines, coloured pins
    rnd = L.rng(12)
    notes = [(-0.36, 1.33, 0.3, 0.36, '#FFF8EC'), (0.02, 1.38, 0.28, 0.3, '#DDEBFA'), (0.36, 1.3, 0.3, 0.4, '#FFF8EC'),
             (-0.3, 0.98, 0.34, 0.26, '#FDE3E6'), (0.12, 1.0, 0.26, 0.28, '#FFF1C9')]
    pins = ['#D9483B', '#3D7CC9', '#5CC86A', '#F2C14E', '#D9483B']
    for i, (x, z, w, h, col) in enumerate(notes):
        rz = rnd.uniform(-5, 5)
        box('note', (w, 0.012, h), (x, -0.082, z - h / 2), rot=(0, rz, 0), mat=flat(col, 0.8), bevel=0.004)
        for k in range(3):
            lw = w * rnd.uniform(0.45, 0.75)
            box('line', (lw, 0.006, 0.014), (x - (w - lw) / 2 + 0.03, -0.09, z + h * 0.18 - k * h * 0.22), rot=(0, rz, 0),
                mat=flat('#8E96A3', 0.8), bevel=0.0)
        sphere('pin', 0.022, (x, -0.1, z + h / 2 - 0.035), flat(pins[i], 0.4), segs=10, rings=6)
    PA.snow_cap('bsnow', 0.12, (0.45, -0.05, 1.67), 0.04, 6, scale=(1.4, 0.6, 1.0))
    for x, f in ((-0.55, (0.6, 1, 0)), (0.0, (0, 1, 0)), (0.55, (-0.6, 1, 0))):
        mark('gather', (x, -0.75 - 0.12 * (x == 0.0), 0.0), facing=f)


@life('music_stand', kind='decor', fp=('r', 0.3), yaw=30.0, front='S', catcher=8.0,
      notes='Little music stand with a song sheet (for the bard by the campfire). performPoint = where the bard '
            'stands behind it facing the camera (play perform_S there; the desk covers his belly).')
def b_music_stand():
    wood = tonal('#A86A36', 0.08, 3.0)
    dark = flat('#7A4A2A', 0.8)
    mb = L.MB()
    for i in range(3):
        a = math.tau * i / 3 + 0.5
        mb.seg((0.28 * math.cos(a), 0.28 * math.sin(a), 0.0), (0, 0, 0.34), 0.024, wood, segs=8)
    mb.seg((0, 0, 0.3), (0, 0, 0.98), 0.028, wood, segs=10)
    mb.done('tripod')
    cyl('knob', 0.04, 0.05, (0, 0, 0.62), mat=flat('gold', 0.3, 0.7), segs=12, bevel=0.01)
    desk = L.group([box('desk', (0.6, 0.035, 0.44), (0, 0, 0), mat=wood, bevel=0.014, origin='center'),
                    box('lip', (0.62, 0.09, 0.035), (0, -0.05, -0.22), mat=dark, bevel=0.01, origin='center'),
                    box('sheet', (0.5, 0.012, 0.38), (0, -0.026, 0.01), mat=flat('#FFF8EC', 0.8), bevel=0.004,
                        origin='center')], 'deskg', loc=(0, -0.02, 1.1), rot=(-28, 0, 0))
    notes = L.MB()
    ink = flat('#3A2A22', 0.6)
    for r_ in range(3):
        z = 0.13 - r_ * 0.12
        notes.seg((-0.22, -0.034, z - 0.035), (0.22, -0.034, z - 0.035), 0.0025, flat('#8E96A3', 0.8), segs=4)
        for c in range(4):
            x = -0.16 + c * 0.11
            notes.sphere(0.018, ink, loc=(x, -0.036, z + 0.022 * ((c * 7 + r_) % 3 - 1)), scale=(1.25, 0.5, 1.0),
                         segs=8, rings=5)
            notes.seg((x + 0.016, -0.036, z), (x + 0.016, -0.036, z + 0.07), 0.004, ink, segs=4)
    nb = notes.done('notes')
    nb.parent = desk
    PA.snow_cap('dsnow', 0.07, (0.22, 0.08, 1.31), 0.035, 2, scale=(1.3, 0.6, 1.0))
    mark('perform', (0.0, 0.42, 0.0), facing=(0, -1, 0))
