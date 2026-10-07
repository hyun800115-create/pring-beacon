"""
vil_face.py - parametric, swappable face parts for Frost Village villagers.

Not run directly (imported by vil_build.py).  Every face part is a small mesh
"decal" wrapped onto the head ellipsoid and registered as a Rig toggle, so an
animation frame picks its expression by listing part names in pose['_show']
(see vil_anim.FACES for the presets: neutral, blink, happy, laugh, talk_*,
surprised, angry, sad, hurt, sleepy, shiver, sing, heart ...).

Part families (toggle names):
  eyes   eye_dot  eye_blink  eye_happy (^^)  eye_chevron (><)  eye_round (white,
         surprised)  eye_big (sparkly / teary)  eye_glare (angry)  eye_sleep
         eye_heart
  brows  brow_neutral  brow_up  brow_angry  brow_sad
  mouth  m_smile  m_grin  m_D (laugh)  m_open  m_mid  m_O  m_pout  m_frown
         m_wavy  m_clench  m_sing  m_gap / m_gapD (gap-tooth grin, prankster)
  cheeks cheek_blush  cheek_red (puffed angry)  cheek_cold (red nose + blue
         chill lines)
  extras fx_tear  fx_snow (snow splat for 'hit')  fx_sweat

All shapes are drawn in "face space" (u = metres to the viewer's right,
v = metres up from the head centre, on the STANDARD char_build head
HEAD_R/HEAD_C) and projected onto the head front; vil_body scales the whole
head group afterwards, so kids/elders reuse the same face.
Features are deliberately oversized/thick so they read at ~80 px on a phone.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bmesh                                   # noqa: E402
from mathutils import Vector                   # noqa: E402

import bl_common as bc                         # noqa: E402
import char_geo as g                           # noqa: E402
import char_build as cb                        # noqa: E402

PI = math.pi
TAU = math.tau
HEAD_R = cb.HEAD_R
HEAD_C = cb.HEAD_C

EYE_DARK = '#2A2026'
MOUTH_IN = '#6E2430'
MOUTH_LINE = '#7A3034'
TONGUE = '#EE7F86'
TEETH = '#FFFFFF'
TEAR = '#6FC0F2'
SNOW = '#F4F7FB'


def M(name, color, rough=0.6, **kw):
    return bc.mat(name, color, rough=rough, **kw)


# --------------------------------------------------------------------------- projection

def surf(u, v, out=0.0, radii=HEAD_R):
    """Point on the head-front surface for face coords (u, v) + outward offset."""
    rx, ry, rz = radii
    t = 1.0 - (u / rx) ** 2 - (v / rz) ** 2
    y = -ry * math.sqrt(max(t, 0.0025))
    p = Vector((u, y, v))
    n = Vector((u / rx ** 2, y / ry ** 2, v / rz ** 2)).normalized()
    return p + n * out, n


def _resample(pts, n):
    if len(pts) >= 3:
        return g.catmull(pts, n)
    (a, b) = pts
    return [(a[0] + (b[0] - a[0]) * k / (n - 1), a[1] + (b[1] - a[1]) * k / (n - 1)) for k in range(n)]


def bm_stroke(pts, width, thick=0.016, out=0.002, taper=0.55, segr=10, n=None, closed=False,
              radii=HEAD_R):
    """Brush stroke along face-space control points.  width = half-width (m)
    or callable t->half-width.  The cross-section is an ellipse lying on the
    skin: wide along the surface, `thick` along the normal."""
    if closed:
        n = n or 40
        path = [pts[k % len(pts)] for k in range(len(pts))]
        path = [(a, b) for a, b in path]
        cyc = path + path[:3]
        dense = g.catmull([path[-1]] + cyc, n + 8)[4:4 + n]
        path = dense
    else:
        n = n or max(10, len(pts) * 7)
        path = _resample(pts, n)
    P, N = [], []
    for u, v in path:
        p, nn = surf(u, v, 0.0, radii)
        P.append(p)
        N.append(nn)
    m = len(P)
    bm = bmesh.new()
    rings = []
    for i in range(m):
        if closed:
            T = P[(i + 1) % m] - P[(i - 1) % m]
        else:
            T = P[min(i + 1, m - 1)] - P[max(i - 1, 0)]
        nrm = N[i]
        T = (T - nrm * T.dot(nrm)).normalized()
        B = nrm.cross(T).normalized()
        t = i / max(1, m - 1)
        if callable(width):
            w = width(t)
        elif closed:
            w = width
        else:
            w = width * (taper + (1 - taper) * math.sin(PI * t) ** 0.5)
        ring = []
        for j in range(segr):
            a = TAU * j / segr
            off = B * (math.cos(a) * w) + nrm * (out + math.sin(a) * thick * 0.5)
            ring.append(bm.verts.new(P[i] + off))
        rings.append(ring)
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for j in range(segr):
            bm.faces.new((a[j], a[(j + 1) % segr], b[(j + 1) % segr], b[j]))
    if not closed:
        for ring, p, nrm, flip in ((rings[0], P[0], N[0], True), (rings[-1], P[-1], N[-1], False)):
            c = bm.verts.new(p + nrm * out)
            for j in range(segr):
                f = (ring[j], ring[(j + 1) % segr], c)
                bm.faces.new(f[::-1] if flip else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_blob(outline, thick=0.016, out=0.0, rings=4, edge=0.35, sink=0.008, radii=HEAD_R,
            center=None):
    """Filled, slightly domed shape from a closed face-space outline (star-shaped
    around its centroid).  Sits on the skin like a glossy sticker."""
    n = len(outline)
    if center is None:
        cu = sum(p[0] for p in outline) / n
        cv = sum(p[1] for p in outline) / n
    else:
        cu, cv = center
    bm = bmesh.new()
    layers = []
    # base ring (sunk into the head so the edge is clean)
    base = []
    for u, v in outline:
        p, nn = surf(u, v, 0.0, radii)
        base.append(bm.verts.new(p + nn * (-sink)))
    layers.append(base)
    for k in range(rings):
        s = 1.0 - k / rings
        h = out + thick * (edge + (1 - edge) * math.sqrt(max(0.0, 1 - s * s)))
        ring = []
        for u, v in outline:
            uu, vv = cu + (u - cu) * s, cv + (v - cv) * s
            p, nn = surf(uu, vv, 0.0, radii)
            ring.append(bm.verts.new(p + nn * h))
        layers.append(ring)
    for a, b in zip(layers, layers[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    p, nn = surf(cu, cv, 0.0, radii)
    c = bm.verts.new(p + nn * (out + thick))
    last = layers[-1]
    for j in range(n):
        bm.faces.new((last[j], last[(j + 1) % n], c))
    bot = bm.verts.new(p + nn * (-sink - 0.004))
    for j in range(n):
        bm.faces.new((base[(j + 1) % n], base[j], bot))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def ellipse(cu, cv, a, b, n=28, rot=0.0):
    cr, sr = math.cos(rot), math.sin(rot)
    out = []
    for k in range(n):
        t = TAU * k / n
        x, y = a * math.cos(t), b * math.sin(t)
        out.append((cu + x * cr - y * sr, cv + x * sr + y * cr))
    return out


def arc(cu, cv, r, a0, a1, n=9, ry=None):
    ry = r if ry is None else ry
    return [(cu + r * math.cos(a0 + (a1 - a0) * k / (n - 1)),
             cv + ry * math.sin(a0 + (a1 - a0) * k / (n - 1))) for k in range(n)]


def heart(cu, cv, s, n=36):
    pts = []
    for k in range(n):
        t = TAU * k / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cu + x * s / 16.0, cv + (y + 2.0) * s / 16.0))
    return pts


def teardrop(cu, cv, w, h, n=24):
    """Drop with the point upward."""
    pts = []
    for k in range(n):
        t = TAU * k / n
        r = (1 - math.cos(t)) / 2          # 0 at top (t=0), 1 at the bottom
        x = w * math.sin(t) * (r ** 0.6)
        y = h * (0.5 * math.cos(t))
        pts.append((cu + x, cv + y))
    return pts


def lumpy(cu, cv, r, n=30, k=6, amp=0.22, seed=0.0, sq=1.0):
    pts = []
    for i in range(n):
        t = TAU * i / n
        rr = r * (1 + amp * math.sin(k * t + seed) * 0.6 + amp * 0.4 * math.cos((k + 3) * t + 2 * seed))
        pts.append((cu + rr * math.cos(t), cv + rr * math.sin(t) * sq))
    return pts


# --------------------------------------------------------------------------- face builder

def _obj(rig, name, bm, material):
    return g.mesh_obj(name, bm, material, rig.j['head'], loc=(0, 0, HEAD_C))


def build_face(rig, spec):
    """Create all swappable face parts on rig.j['head'] and register toggles.
    spec keys (all optional): skin, blush, eye, brow (colour), eye_u, eye_v,
    eye_w, eye_h, mouth_v, mouth_out (raise the mouth above a beard), brow_v,
    brow_w, brow_thick, lashes (bool), ears (bool), nose ('dot'|'big'|None),
    nose_color, cheek_u, cheek_v."""
    head = rig.j['head']
    skin = M('skin', spec.get('skin', cb.SKIN), rough=0.55)
    eye_m = M('eye', spec.get('eye', EYE_DARK), rough=0.22)
    hi_m = M('eye_hi', '#FFFFFF', rough=0.3, emission='#FFFFFF', emission_strength=1.6)
    white_m = M('eye_white', '#FFFFFF', rough=0.35, emission='#FFFFFF', emission_strength=0.35)
    brow_m = M('brow', spec.get('brow', '#3A2A22'), rough=0.6)
    mouth_m = M('mouth_line', MOUTH_LINE, rough=0.5)
    mouth_in = M('mouth_in', MOUTH_IN, rough=0.5)
    tongue_m = M('tongue', TONGUE, rough=0.5)
    teeth_m = M('teeth', TEETH, rough=0.35, emission='#FFFFFF', emission_strength=0.25)
    blush_m = M('blush', spec.get('blush', cb.BLUSH), rough=0.9)
    red_m = M('cheek_red', '#F2585A', rough=0.6)
    tear_m = M('tear', TEAR, rough=0.15, emission='#BFE6FF', emission_strength=0.6)
    heart_m = M('heart_eye', '#F2456A', rough=0.3)
    snow_m = M('snow_splat', SNOW, rough=0.8, emission='#FFFFFF', emission_strength=0.15)
    chill_m = M('chill', '#6E9EE0', rough=0.6)

    eu = spec.get('eye_u', 0.116)
    ev = spec.get('eye_v', -0.030)
    ew = spec.get('eye_w', 0.045)
    eh = spec.get('eye_h', 0.062)
    mv = spec.get('mouth_v', -0.094)
    mo = spec.get('mouth_out', 0.0)
    bv = spec.get('brow_v', ev + 0.098)
    bw = spec.get('brow_w', 0.046)
    bt = spec.get('brow_thick', 0.0125)
    bo = spec.get('brow_out', 0.010)
    cu_ = spec.get('cheek_u', 0.172)
    cv_ = spec.get('cheek_v', -0.080)
    lashes = spec.get('lashes', False)
    parts = {}

    def add(tog, objs):
        objs = objs if isinstance(objs, list) else [objs]
        parts.setdefault(tog, []).extend(objs)

    sides = (-1, 1)          # -1 = viewer-left eye (character's right), +1 = viewer-right

    def lash(s, u0, v0, objs, scale=1.0):
        # little flick at the outer-top corner
        pts = [(u0 + s * ew * 0.55, v0 + eh * 0.55), (u0 + s * ew * 1.05, v0 + eh * 0.80),
               (u0 + s * ew * 1.35, v0 + eh * 0.98)]
        objs.append(_obj(rig, 'lash', bm_stroke(pts, 0.0085 * scale, thick=0.012, taper=0.3), eye_m))

    # ---- eyes ------------------------------------------------------------------------
    for s in sides:
        u = s * eu
        # dot (normal open)
        objs = [_obj(rig, 'eye', bm_blob(ellipse(u, ev, ew, eh), thick=0.018), eye_m),
                _obj(rig, 'eye_hi', bm_blob(ellipse(u - ew * 0.32, ev + eh * 0.36, ew * 0.36, eh * 0.30, 16),
                                            thick=0.008, out=0.015), hi_m)]
        if lashes:
            lash(s, u, ev, objs)
        add('eye_dot', objs)
        # blink: soft downward-curved closed line
        objs = [_obj(rig, 'eye_blink', bm_stroke(arc(u, ev + eh * 0.25, ew * 1.15, PI + 0.35, TAU - 0.35, 9,
                                                      ry=eh * 0.45), 0.0115, thick=0.014), eye_m)]
        if lashes:
            lash(s, u, ev - eh * 0.45, objs, 0.9)
        add('eye_blink', objs)
        # happy ^^ : thick upward arcs
        add('eye_happy', _obj(rig, 'eye_happy', bm_stroke(arc(u, ev - eh * 0.35, ew * 1.15, 0.25, PI - 0.25, 11,
                                                              ry=eh * 0.95), 0.0135, thick=0.016, taper=0.6),
                               eye_m))
        # sleepy: lower, flatter closed arcs with a lash
        objs = [_obj(rig, 'eye_sleep', bm_stroke(arc(u, ev + eh * 0.05, ew * 1.2, PI + 0.30, TAU - 0.30, 9,
                                                      ry=eh * 0.55), 0.0115, thick=0.014), eye_m)]
        add('eye_sleep', objs)
        # >< chevrons (hurt): point toward the nose
        pts = [(u + s * ew * 0.95, ev + eh * 0.85), (u - s * ew * 0.85, ev), (u + s * ew * 0.95, ev - eh * 0.85)]
        add('eye_chevron', _obj(rig, 'eye_chev', bm_stroke(pts, 0.0125, thick=0.016, taper=0.7, n=15), eye_m))
        # round surprised: white disc, dark rim, small pupil
        rr = ew * 1.32
        objs = [_obj(rig, 'eye_white', bm_blob(ellipse(u, ev + 0.006, rr, rr * 1.1), thick=0.016), white_m),
                _obj(rig, 'eye_rim', bm_stroke(ellipse(u, ev + 0.006, rr, rr * 1.1, 24), 0.0085, thick=0.016,
                                               closed=True, n=36, out=0.004), eye_m),
                _obj(rig, 'eye_pupil', bm_blob(ellipse(u, ev + 0.002, ew * 0.48, ew * 0.55, 18), thick=0.012,
                                               out=0.012), eye_m)]
        add('eye_round', objs)
        # big sparkly / teary eye
        objs = [_obj(rig, 'eye_big', bm_blob(ellipse(u, ev - 0.002, ew * 1.18, eh * 1.12), thick=0.018), eye_m),
                _obj(rig, 'eye_big_hi', bm_blob(ellipse(u - ew * 0.38, ev + eh * 0.40, ew * 0.42, eh * 0.34, 16),
                                                thick=0.008, out=0.015), hi_m),
                _obj(rig, 'eye_big_hi2', bm_blob(ellipse(u + ew * 0.40, ev - eh * 0.45, ew * 0.22, eh * 0.18, 12),
                                                 thick=0.006, out=0.015), hi_m)]
        if lashes:
            lash(s, u, ev, objs)
        add('eye_big', objs)
        # teary: big eye + wet blue lower lid
        add('eye_teary', objs[:])
        add('eye_teary', _obj(rig, 'eye_wet', bm_stroke(arc(u, ev + eh * 0.15, ew * 1.25, PI + 0.5, TAU - 0.5, 9,
                                                             ry=eh * 1.15), 0.010, thick=0.012, out=0.010),
                              tear_m))
        # glare (angry): eye with the inner-top cut off at a slant
        gl = []
        for (pu, pv) in ellipse(u, ev - 0.004, ew * 1.05, eh * 0.95, 32):
            cut = ev + eh * 0.30 + 0.75 * s * (pu - u)       # inner side (toward the nose) lower
            gl.append((pu, min(pv, cut)))
        objs = [_obj(rig, 'eye_glare', bm_blob(gl, thick=0.018, center=(u, ev - eh * 0.3)), eye_m),
                _obj(rig, 'eye_glare_hi', bm_blob(ellipse(u - ew * 0.25, ev - eh * 0.05, ew * 0.26, eh * 0.2, 12),
                                                  thick=0.006, out=0.015), hi_m)]
        add('eye_glare', objs)
        # heart eyes
        add('eye_heart', [_obj(rig, 'eye_heart', bm_blob(heart(u, ev, ew * 1.45), thick=0.02), heart_m),
                          _obj(rig, 'eye_heart_hi', bm_blob(ellipse(u - ew * 0.5, ev + ew * 0.55, ew * 0.25,
                                                                    ew * 0.2, 12), thick=0.006, out=0.017), hi_m)])

    # ---- brows -----------------------------------------------------------------------
    for s in sides:
        u = s * eu
        o, i_ = u + s * bw, u - s * bw * 0.9          # outer / inner ends (viewer coords)
        add('brow_neutral', _obj(rig, 'brow', bm_stroke([(o, bv - 0.006), (u, bv + 0.008), (i_, bv)], bt,
                                                        thick=0.014, taper=0.45, out=bo), brow_m))
        add('brow_up', _obj(rig, 'brow_up', bm_stroke([(o, bv + 0.014), (u, bv + 0.040), (i_, bv + 0.026)], bt,
                                                      thick=0.014, taper=0.45, out=bo), brow_m))
        add('brow_angry', _obj(rig, 'brow_angry', bm_stroke([(o + s * 0.004, bv + 0.020), (u, bv + 0.004),
                                                             (i_ - s * 0.006, bv - 0.026)],
                                                            lambda t: bt * (1.25 - 0.15 * t), thick=0.016, out=bo),
                                brow_m))
        add('brow_sad', _obj(rig, 'brow_sad', bm_stroke([(o, bv - 0.016), (u, bv + 0.002), (i_ - s * 0.004,
                                                                                            bv + 0.028)], bt,
                                                        thick=0.014, taper=0.45, out=bo), brow_m))

    # ---- mouths ----------------------------------------------------------------------
    def mobj(name, bm, mat):
        return _obj(rig, name, bm, mat)

    add('m_smile', mobj('m_smile', bm_stroke(arc(0, mv + 0.030, 0.047, PI + 0.55, TAU - 0.55, 9, ry=0.040),
                                             0.012, thick=0.013, out=mo), mouth_m))
    add('m_smirk', mobj('m_smirk', bm_stroke([(-0.046, mv + 0.006), (-0.014, mv - 0.012), (0.018, mv - 0.010),
                                              (0.046, mv + 0.012), (0.058, mv + 0.028)], 0.012, thick=0.013,
                                             taper=0.55, out=mo), mouth_m))
    add('m_frown', mobj('m_frown', bm_stroke(arc(0, mv - 0.034, 0.046, 0.6, PI - 0.6, 9, ry=0.036),
                                             0.012, thick=0.013, out=mo), mouth_m))
    add('m_pout', mobj('m_pout', bm_stroke(arc(0, mv - 0.026, 0.031, 0.45, PI - 0.45, 9, ry=0.028),
                                           0.012, thick=0.013, out=mo), mouth_m))
    wav = [(-0.060 + 0.120 * k / 12, mv + 0.012 * math.sin(k / 12 * TAU * 1.5 + 0.3)) for k in range(13)]
    add('m_wavy', mobj('m_wavy', bm_stroke(wav, 0.011, thick=0.013, taper=0.6, n=40, out=mo), mouth_m))

    def open_mouth(name, hw, depth, tongue=True, teeth=None, top_curve=0.008):
        """D-shaped open mouth: slightly smiling top lip line + round lower bowl."""
        v0 = mv + depth * 0.45
        pts = []
        n = 24
        for k in range(n):                       # bowl: right corner -> bottom -> left corner
            a = PI * k / (n - 1)
            pts.append((hw * math.cos(a), v0 - depth * math.sin(a)))
        for k in range(1, 8):                    # top lip back to the right corner
            x = -hw + 2 * hw * k / 8
            pts.append((x, v0 - top_curve * (1 - (x / hw) ** 2)))
        objs = [mobj(name, bm_blob(pts, thick=0.010, out=mo, center=(0, v0 - depth * 0.45)), mouth_in)]
        if tongue:
            objs.append(mobj(name + '_tg', bm_blob(ellipse(0, v0 - depth * 0.74, hw * 0.55, depth * 0.24, 18),
                                                   thick=0.008, out=mo + 0.006), tongue_m))
        if teeth == 'top':
            objs.append(mobj(name + '_teeth', bm_blob([(-hw * 0.80, v0 - 0.002), (hw * 0.80, v0 - 0.002),
                                                       (hw * 0.66, v0 - depth * 0.26),
                                                       (-hw * 0.66, v0 - depth * 0.26)],
                                                      thick=0.007, out=mo + 0.007), teeth_m))
        if teeth == 'gap':
            for sx in (-1, 1):
                objs.append(mobj(name + '_tooth', bm_blob([(sx * hw * 0.20, v0 - 0.002), (sx * hw * 0.78, v0 - 0.002),
                                                           (sx * hw * 0.66, v0 - depth * 0.34),
                                                           (sx * hw * 0.22, v0 - depth * 0.34)],
                                                          thick=0.007, out=mo + 0.007), teeth_m))
        return objs

    add('m_grin', open_mouth('m_grin', 0.060, 0.056, teeth='top'))
    add('m_D', open_mouth('m_D', 0.078, 0.090, teeth='top'))
    add('m_gap', open_mouth('m_gap', 0.062, 0.058, teeth='gap'))
    add('m_gapD', open_mouth('m_gapD', 0.078, 0.090, teeth='gap'))
    add('m_open', [mobj('m_open', bm_blob(ellipse(0, mv - 0.004, 0.043, 0.036, 24), thick=0.010, out=mo), mouth_in),
                   mobj('m_open_tg', bm_blob(ellipse(0, mv - 0.024, 0.026, 0.013, 14), thick=0.006, out=mo + 0.006),
                        tongue_m)])
    add('m_mid', mobj('m_mid', bm_blob(ellipse(0, mv, 0.038, 0.018, 20), thick=0.010, out=mo), mouth_in))
    add('m_O', [mobj('m_O', bm_blob(ellipse(0, mv - 0.008, 0.035, 0.047, 24), thick=0.010, out=mo), mouth_in),
                mobj('m_O_tg', bm_blob(ellipse(0, mv - 0.036, 0.020, 0.012, 12), thick=0.006, out=mo + 0.006),
                     tongue_m)])
    add('m_sing', [mobj('m_sing', bm_blob(ellipse(0.004, mv - 0.004, 0.037, 0.031, 22, rot=0.25), thick=0.010,
                                          out=mo), mouth_in),
                   mobj('m_sing_tg', bm_blob(ellipse(0.004, mv - 0.019, 0.021, 0.011, 12), thick=0.006,
                                             out=mo + 0.006), tongue_m)])
    # clenched teeth (shiver): white bar, dark rim, tooth lines
    cw_, ch_ = 0.066, 0.028
    clench = [mobj('m_clench', bm_blob(_round_rect(0, mv, cw_, ch_), thick=0.010, out=mo), teeth_m),
              mobj('m_clench_rim', bm_stroke(_round_rect(0, mv, cw_, ch_, n=8), 0.0075, thick=0.013, closed=True,
                                             n=44, out=mo + 0.002), mouth_m),
              mobj('m_clench_mid', bm_stroke([(-cw_ * 0.95, mv), (cw_ * 0.95, mv)], 0.0045, thick=0.010,
                                             out=mo + 0.008, taper=0.9), mouth_m)]
    for x in (-0.020, 0.020):
        clench.append(mobj('m_clench_t', bm_stroke([(x, mv + ch_ * 0.9), (x, mv - ch_ * 0.9)], 0.0042, thick=0.010,
                                                   out=mo + 0.008, taper=0.9), mouth_m))
    add('m_clench', clench)

    # ---- cheeks ----------------------------------------------------------------------
    for s in sides:
        add('cheek_blush', _obj(rig, 'blush', bm_blob(ellipse(s * cu_, cv_, 0.052, 0.030, 20), thick=0.004,
                                                      out=-0.001, edge=0.6), blush_m))
        add('cheek_red', _obj(rig, 'cheek_red', bm_blob(ellipse(s * (cu_ + 0.004), cv_ - 0.004, 0.070, 0.050, 24),
                                                        thick=0.030, out=0.0, edge=0.2), red_m))
        add('cheek_cold', _obj(rig, 'blush_c', bm_blob(ellipse(s * cu_, cv_, 0.056, 0.032, 20), thick=0.004,
                                                       out=-0.001, edge=0.6), M('blush_cold', '#F27C86', rough=0.9)))
    # chill lines on the forehead (cold) - three short blue vertical strokes, viewer-right
    for k, x in enumerate((0.04, 0.085, 0.13)):
        add('cheek_cold', _obj(rig, 'chill', bm_stroke([(x, ev + 0.075 + 0.006 * k), (x, ev + 0.020)], 0.0075,
                                                       thick=0.010, taper=0.6), chill_m))

    # ---- nose ------------------------------------------------------------------------
    nose = spec.get('nose', 'dot')
    nv = spec.get('nose_v', -0.052)
    if nose == 'big':
        g.mesh_obj('nose', g.bm_ellipsoid(0.042, 0.032, 0.034, 14, 10), M('nose', spec.get('nose_color', '#F0B494'),
                                                                         rough=0.5), head,
                   loc=tuple(surf(0, nv, -0.008)[0] + Vector((0, 0, HEAD_C))))
    elif nose == 'dot':
        g.mesh_obj('nose', g.bm_ellipsoid(0.026, 0.018, 0.020, 12, 8), skin, head,
                   loc=tuple(surf(0, nv, -0.004)[0] + Vector((0, 0, HEAD_C))))
    add('cheek_cold', g.mesh_obj('nose_red', g.bm_ellipsoid(0.034, 0.022, 0.028, 12, 8),
                                 M('nose_red', '#F06A6A', rough=0.45), head,
                                 loc=tuple(surf(0, nv, 0.000)[0] + Vector((0, 0, HEAD_C)))))

    # ---- extras ----------------------------------------------------------------------
    tears = []
    for s in sides:
        tears.append(_obj(rig, 'tear', bm_blob(teardrop(s * (eu + 0.012), ev - eh - 0.042, 0.022, 0.050), thick=0.016,
                                               out=0.006), tear_m))
        tears.append(_obj(rig, 'tear_hi', bm_blob(ellipse(s * (eu + 0.012) - 0.007, ev - eh - 0.050, 0.006, 0.008, 10),
                                                  thick=0.004, out=0.020), hi_m))
    add('fx_tear', tears)
    sweat = [_obj(rig, 'sweat', bm_blob(teardrop(-0.215, 0.040, 0.026, 0.060), thick=0.020, out=0.008), tear_m),
             _obj(rig, 'sweat_hi', bm_blob(ellipse(-0.222, 0.030, 0.006, 0.010, 10), thick=0.004, out=0.026), hi_m)]
    add('fx_sweat', sweat)
    # snow splat: lumpy white patch over the viewer-right eye/cheek + crumbs
    splat = [_obj(rig, 'splat', bm_blob(lumpy(0.075, -0.010, 0.085, n=36, k=7, amp=0.30, seed=1.3), thick=0.040,
                                        out=0.004, edge=0.5, rings=5), snow_m)]
    for (cx, cy, r) in ((-0.035, 0.075, 0.020), (0.175, 0.080, 0.018), (0.165, -0.105, 0.022), (-0.020, -0.075, 0.016),
                        (0.020, 0.105, 0.014)):
        splat.append(_obj(rig, 'crumb', bm_blob(ellipse(cx, cy, r, r, 12), thick=0.020, out=0.004), snow_m))
    add('fx_snow', splat)

    # ---- ears (always visible; hats cover them) -----------------------------------------
    if spec.get('ears', True):
        for s in (-1, 1):
            cb.on_head('ear', g.bm_ellipsoid(0.028, 0.055, 0.065, 12, 8), skin, head, s * PI / 2 * 0.98, -0.08,
                       out=-0.02)

    for tog, objs in parts.items():
        rig.toggle(tog, objs)
    rig.meta['face_parts'] = sorted(parts)
    return parts


def _round_rect(cu, cv, hw, hh, n=6):
    """Rounded rectangle outline (face space)."""
    r = min(hw, hh) * 0.75
    pts = []
    corners = ((hw - r, hh - r, 0.0), (-hw + r, hh - r, PI / 2), (-hw + r, -hh + r, PI), (hw - r, -hh + r, 1.5 * PI))
    for cx, cy, a0 in corners:
        for k in range(n):
            a = a0 + (PI / 2) * k / (n - 1)
            pts.append((cu + cx + r * math.cos(a), cv + cy + r * math.sin(a)))
    return pts
