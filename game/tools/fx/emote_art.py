"""
emote_art.py - the emote icons + snowball projectile for Frost Village (CONTRACT_VILLAGERS §C).
Library module (no CLI): imported by gen_emotes.py.  Built on fxlib.py (numpy + Pillow SDF kit).

Every drawing function takes a fxlib.Canvas whose coordinates are in "64-px emote units"
(the canvas is created as Canvas(64, 64, ss)), so the same code renders the 64x64 asset
(ss=4, LANCZOS down) and crisp zoomed previews (c.image((256, 256)) with a high ss).

Style = the house "soft toy" look of gen_ui.py: dark tinted outline, vertical gradient lit by a
rounded bevel from the shared upper-left sun, glossy highlight, one soft navy drop shadow per
icon.  Faces are warm emoji-yellow with the villagers' dark-brown eyes and rosy cheeks.
No text/letters except the Z shapes of zzz and the ! ? marks.
"""
import math

import numpy as np

import fxlib as F
from fxlib import hexc, toy

WHITE = hexc('#FFFFFF')
INK = '#4A2616'                  # face features (warm dark brown, like the villagers' eyes)
MOUTH = '#8E2C1E'
TONGUE = '#FF7F8E'
CHEEK = '#FF7A8A'

# (top, bottom, outline) per material
PAL = {
    'face': ('#FFEE9E', '#F7B23A', '#9A520C'),
    'cold': ('#E2F4FF', '#78B4EE', '#245592'),
    'heart': ('#FFA0BC', '#E8336A', '#8E1238'),
    'red': ('#FF8E6E', '#E3302A', '#741410'),
    'blue': ('#94D2FF', '#2F78D6', '#143B74'),
    'purple': ('#D9BBFF', '#7C4FE0', '#35206E'),
    'pink': ('#FFC0D6', '#F05C93', '#8A1E4E'),
    'gold': ('#FFF4AE', '#F5A623', '#8E520A'),
    'water': ('#DDF4FF', '#4AA2EC', '#1B5296'),
    'skin': ('#FFE2C8', '#F2AE86', '#8E4A2A'),
    'snow': ('#FFFFFF', '#CFDDF0', '#56739F'),
    'zzz': ('#DCE8FF', '#6D8CEB', '#24337A'),
    'slate': ('#9AA6C0', '#4C5874', '#222A40'),
    'dots': ('#B8C2D4', '#7E8AA4', '#4A5570'),
    'bread': ('#F6BE6C', '#C46F2C', '#62300E'),
    'steel': ('#F4F7FB', '#97A2B4', '#3A4352'),
    'parka': ('#FF7A6A', '#C9362C', '#681510'),
    'fur': ('#FFFFFF', '#E6DCCB', '#6B5A44'),
}
LO_TINT = {  # colour the bevel darkens toward (keeps shadows saturated, never grey/muddy)
    'face': '#E06A2A', 'cold': '#3E62B8', 'heart': '#B0204E', 'red': '#A0201A', 'blue': '#2A55B0',
    'purple': '#5A30B0', 'pink': '#C03070', 'gold': '#D0701A', 'water': '#2A70C8', 'skin': '#C86A50',
    'snow': '#7E9CCC', 'zzz': '#4060C0', 'slate': '#303A58', 'dots': '#4A5672', 'bread': '#9A4A1A', 'steel': '#5A6780',
    'parka': '#901E18', 'fur': '#A89880',
}


def part(c, d, pal, ow=2.3, bevel=6.0, gloss=0.3, hi=0.5, lo=0.45, alpha=1.0, gloss_h=0.45, pillow=None, spec=0.0,
         yr=None):
    """One soft-toy part (no own drop shadow: icons get a single group shadow)."""
    top, bot, line = PAL[pal]
    return toy(c, d, top, bot, line if ow else None, ow=ow, bevel=bevel, gloss=gloss, shadow=0, hi=hi, lo=lo,
               tint_lo=hexc(LO_TINT[pal]), alpha=alpha, gloss_h=gloss_h, pillow=pillow, spec=spec, yr=yr)


def group_shadow(c, d, ow=2.3, opacity=0.30, dy=2.0, sigma=1.6):
    """One soft navy drop shadow under the whole icon silhouette (offset down, shared sun)."""
    c.shadow(c.cov(d - ow), dy=dy, sigma=sigma, opacity=opacity, color='#1B2840')


def glossy_spot(c, x, y, rx, ry, ang_deg=-35, a=0.75, feather=0.8):
    X2, Y2 = F.rot(c.X, c.Y, x, y, math.radians(ang_deg))
    c.fill(F.sd_ellipse(X2, Y2, x, y, rx, ry), WHITE, a, feather=feather)


def twinkle(c, x, y, s, a=1.0, edge='#B8650E', core='#FFFFFF', tip='#FFD45A'):
    """Small 4-point twinkle with a thin dark edge (reads on white bubbles and snow)."""
    d = F.sd_glint(c.X, c.Y, x, y, s, s, c.px, pinch=0.5)
    c.fill(d - 0.9, hexc(edge), 0.9 * a)
    r = np.hypot(c.X - x, c.Y - y)
    c.paint(c.cov(d), F.mix(hexc(core), hexc(tip), np.clip(r / s, 0, 1) ** 0.8), a)


# =========================================================================== face kit
def face(c, cx, cy, r, pal='face', ow=2.5):
    """Round chubby face ball: outline, bevel-lit gradient, soft top-left gloss."""
    d = F.sd_circle(c.X, c.Y, cx, cy, r)
    part(c, d, pal, ow=ow, bevel=r * 0.5, gloss=0.0, hi=0.55, lo=0.42)
    glossy_spot(c, cx - r * 0.40, cy - r * 0.55, r * 0.30, r * 0.15, -32, 0.6, 1.0)
    glossy_spot(c, cx - r * 0.70, cy - r * 0.18, r * 0.06, r * 0.06, 0, 0.45, 0.6)
    return d


def eye_dot(c, x, y, rx=2.9, ry=3.9, glint=True, big_glint=False):
    c.fill(F.sd_ellipse(c.X, c.Y, x, y, rx, ry), hexc(INK))
    if glint:
        g = 1.25 if not big_glint else 1.6
        c.fill(F.sd_circle(c.X, c.Y, x - rx * 0.32, y - ry * 0.4, g), WHITE)
        if big_glint:
            c.fill(F.sd_circle(c.X, c.Y, x + rx * 0.35, y + ry * 0.38, 0.8), WHITE, 0.9)


def eye_happy(c, x, y, w=3.8, t=1.45):
    """Closed smiling eye '^' (arc bulging up)."""
    c.fill(F.sd_arc(c.X, c.Y, x, y + w * 0.55, w, math.radians(200), math.radians(340), t), hexc(INK))


def eye_chevron(c, x, y, s=3.6, t=1.6, right=True):
    """Squeezed laughing eye: '>' (right=True points to the right) or '<'."""
    sx = 1 if right else -1
    pts = [(x - sx * s * 0.75, y - s), (x + sx * s * 0.75, y), (x - sx * s * 0.75, y + s)]
    c.fill(F.sd_polyline(c.X, c.Y, pts, t), hexc(INK))


def cheeks(c, cx, cy, dx, dy, rx=4.3, ry=2.7, a=0.55):
    for s in (-1, 1):
        c.fill(F.sd_ellipse(c.X, c.Y, cx + s * dx, cy + dy, rx, ry), hexc(CHEEK), a, feather=1.4)


def mouth_open(c, cx, my, rw, depth, teeth=True, tongue=True, ink_w=1.1):
    """D-shaped open mouth: flat top edge at y=my, round bottom."""
    d = np.maximum(F.sd_ellipse(c.X, c.Y, cx, my, rw, depth), my - c.Y)
    d = d - 0.4
    c.fill(d - ink_w, hexc(INK))
    c.fill(d, hexc(MOUTH))
    m = c.cov(d)
    if tongue:
        tg = F.sd_ellipse(c.X, c.Y, cx + rw * 0.12, my + depth * 0.98, rw * 0.58, depth * 0.52)
        c.paint(c.cov(tg) * m, hexc(TONGUE))
    if teeth:
        c.paint(c.cov(c.Y - (my + max(1.6, depth * 0.24))) * m, hexc('#FFFDF6'))


def brows_worried(c, cx, y, dx, t=1.3, ln=4.6, tilt=24):
    """Worried brows: inner ends raised (tilt degrees), centred dx either side of cx."""
    a = math.radians(tilt)
    for s in (-1, 1):
        x0 = cx + s * dx
        outer = (x0 + s * ln * 0.5 * math.cos(a), y + ln * 0.5 * math.sin(a))
        inner = (x0 - s * ln * 0.5 * math.cos(a), y - ln * 0.5 * math.sin(a))
        c.fill(F.sd_segment(c.X, c.Y, outer[0], outer[1], inner[0], inner[1], t), hexc(INK))


def droplet(c, x, y, r, ang_deg=0.0, h=None, pal='water', ow=1.6, glint=True):
    """Glossy water drop; ang_deg turns the tip away from straight up (positive = counter-clockwise)."""
    X2, Y2 = F.rot(c.X, c.Y, x, y, math.radians(-ang_deg))
    d = F.sd_teardrop(X2, Y2, x, y, r, h if h is not None else r * 2.1, tip=r * 0.12)
    part(c, d, pal, ow=ow, bevel=r * 0.7, gloss=0.0, hi=0.55, lo=0.4)
    if glint:
        # glint on the upper-left of the round part
        gx, gy = x - r * 0.38, y - r * 0.22
        c.fill(F.sd_ellipse(*F.rot(c.X, c.Y, gx, gy, math.radians(-30)), gx, gy, r * 0.2, r * 0.32), WHITE, 0.9)
    return d


def heart_sdf(X, Y, cx, cy, w):
    """Chubby heart, overall width ~w, vertically centred at cy."""
    s = w / 1.93
    tip = cy + s * 0.88
    return F.sd_heart_iq(X, Y, cx, tip - s * 0.62, s)


def heart(c, cx, cy, w, rot_deg=0.0, ow=2.0, pal='heart', gloss=True):
    X2, Y2 = F.rot(c.X, c.Y, cx, cy, math.radians(rot_deg))
    d = heart_sdf(X2, Y2, cx, cy, w) - w * 0.02
    part(c, d, pal, ow=ow, gloss=0.0, hi=0.55, lo=0.45, pillow=w * 0.16)
    if gloss:
        gx, gy = cx - w * 0.24, cy - w * 0.17
        X3, Y3 = F.rot(c.X, c.Y, gx, gy, math.radians(rot_deg - 35))
        c.fill(F.sd_ellipse(X3, Y3, gx, gy, w * 0.12, w * 0.07), WHITE, 0.85, feather=0.4)
    return d


# =========================================================================== emotes (64x64 units)
def e_heart(c):
    cx, cy, w = 32, 33.5, 50
    d = heart_sdf(c.X, c.Y, cx, cy, w) - 1.0
    group_shadow(c, d, 2.4)
    part(c, d, 'heart', ow=2.5, gloss=0.0, hi=0.6, lo=0.5, pillow=8.0)
    glossy_spot(c, cx - 12.5, cy - 9.5, 6.2, 3.6, -38, 0.85, 0.6)
    c.fill(F.sd_circle(c.X, c.Y, cx - 17.5, cy - 1.5, 1.6), WHITE, 0.75)
    twinkle(c, 55.5, 8.0, 5.4, edge='#9E2350', tip='#FFC0D6')


def e_love(c):
    cx, cy, r = 31, 34, 24
    dface = F.sd_circle(c.X, c.Y, cx, cy, r)
    hs = heart_sdf(c.X, c.Y, 52, 11.5, 13)
    group_shadow(c, np.minimum(dface, hs), 2.5)
    face(c, cx, cy, r)
    cheeks(c, cx, cy, 15.5, 5.5, a=0.65)
    for s in (-1, 1):
        heart(c, cx + s * 8.8, cy - 3.2, 11.5, rot_deg=-s * 8, ow=1.5)
    mouth_open(c, cx, cy + 6.0, 7.5, 7.5, teeth=False, tongue=True)
    heart(c, 52, 11.5, 13, rot_deg=14, ow=1.8)


def e_laugh(c):
    cx, cy, r = 32, 33, 23.0
    tilt = math.radians(-9)
    Xr, Yr = F.rot(c.X, c.Y, cx, cy, tilt)

    v = c.region(0, 0, c.w, c.h)        # full view sharing c's pixels, drawn with rotated coordinates
    v.X, v.Y = Xr, Yr
    dface = F.sd_circle(Xr, Yr, cx, cy, r)
    # tear drops flying out of the outer eye corners
    tears = [(-1, cx - 22.0, cy - 0.5, 4.4, -62), (1, cx + 22.0, cy - 0.5, 4.4, 62),
             (-1, cx - 25.0, cy + 9.0, 2.4, -40), (1, cx + 25.0, cy + 9.0, 2.4, 40)]
    sh = dface
    for s, x, y, rr, ang in tears:
        X2, Y2 = F.rot(Xr, Yr, x, y, math.radians(-ang))
        sh = np.minimum(sh, F.sd_teardrop(X2, Y2, x, y, rr, rr * 2.3, tip=rr * 0.12))
    group_shadow(c, sh, 2.4)
    face(v, cx, cy, r)
    cheeks(v, cx, cy, 15.5, 6.0, a=0.6)
    eye_chevron(v, cx - 9, cy - 5.5, 3.5, 1.65, right=True)
    eye_chevron(v, cx + 9, cy - 5.5, 3.5, 1.65, right=False)
    mouth_open(v, cx, cy + 1.5, 11.5, 12.0, teeth=True, tongue=True)
    for s, x, y, rr, ang in tears:
        droplet(v, x, y, rr, ang_deg=ang, h=rr * 2.3, ow=1.5)


def e_exclaim(c):
    cx = 32
    X2, Y2 = F.rot(c.X, c.Y, 32, 32, math.radians(8))
    bar = F.sd_polygon(X2, Y2, [(cx - 6.4, 9.0), (cx + 6.4, 9.0), (cx + 3.3, 38.0), (cx - 3.3, 38.0)]) - 3.0
    dot = F.sd_circle(X2, Y2, cx, 49.5, 6.3)
    d = np.minimum(bar, dot)
    group_shadow(c, d, 2.6)
    part(c, d, 'red', ow=2.6, bevel=5.0, gloss=0.0, hi=0.6, lo=0.45)
    # glossy streak along the bar + spot on the dot
    gl = F.sd_segment(X2, Y2, cx - 3.5, 11.0, cx - 1.6, 27, 1.5)
    c.fill(gl, WHITE, 0.75, feather=0.6)
    c.fill(F.sd_circle(X2, Y2, cx - 2.5, 47.4, 1.6), WHITE, 0.8, feather=0.4)


def e_question(c):
    X2, Y2 = F.rot(c.X, c.Y, 32, 32, math.radians(-7))
    cx, cy, R, t = 32, 21.0, 11.0, 4.6
    arc = F.sd_arc(X2, Y2, cx, cy, R, math.radians(188), math.radians(418), t)
    ex, ey = cx + R * math.cos(math.radians(58)), cy + R * math.sin(math.radians(58))
    stem = F.sd_polyline(X2, Y2, [(ex, ey), (cx + 0.5, cy + 15.0), (cx, cy + 17.5)], t)
    dot = F.sd_circle(X2, Y2, cx, 50.0, 6.0)
    d = F.union(arc, stem, dot)
    group_shadow(c, d, 2.6)
    part(c, d, 'blue', ow=2.6, bevel=4.5, gloss=0.0, hi=0.6, lo=0.45)
    gl = F.sd_arc(X2, Y2, cx, cy, R + 1.0, math.radians(205), math.radians(258), 1.3)
    c.fill(gl, WHITE, 0.75, feather=0.5)
    c.fill(F.sd_circle(X2, Y2, cx - 2.3, 48.1, 1.5), WHITE, 0.8, feather=0.4)


def anger_pieces(X, Y, cx, cy, k=1.0, pulse=1.0):
    """The four bulging pieces of the manga anger vein (SDFs in px), centred at (cx,cy), scale k
    (k=1 -> ~46 px wide).  pulse > 1 fattens the pieces (throbbing)."""
    a, R = 20.5 * k, 16.0 * k
    t0, t1 = 4.6 * k * pulse, 2.1 * k * pulse
    half = math.radians(44)
    pieces = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        ox, oy = cx + sx * a, cy + sy * a
        mid = math.atan2(-sy, -sx)
        ang = np.arctan2(Y - oy, X - ox)
        da = np.abs(np.angle(np.exp(1j * (ang - mid))))
        u = np.clip(da / half, 0, 1)
        thick = t0 - (t0 - t1) * u ** 2
        ring = np.abs(np.hypot(X - ox, Y - oy) - R) - thick
        e0 = np.hypot(X - (ox + R * math.cos(mid - half)), Y - (oy + R * math.sin(mid - half))) - t1
        e1 = np.hypot(X - (ox + R * math.cos(mid + half)), Y - (oy + R * math.sin(mid + half))) - t1
        pieces.append(np.where(da <= half, ring, np.minimum(e0, e1)).astype(np.float32))
    return pieces


def anger_vein(c, cx, cy, k=1.0, pulse=1.0, alpha=1.0, shadow=True):
    """Paint the red cross-vein (used by emote_anger and fx_anger_puff)."""
    pieces = anger_pieces(c.X, c.Y, cx, cy, k, pulse)
    if shadow:
        group_shadow(c, F.union(*pieces), 2.5 * k, opacity=0.30 * alpha, dy=2.2 * max(k, 0.5),
                     sigma=1.8 * max(k, 0.5))
    for p in pieces:
        part(c, p, 'red', ow=max(1.2, 2.5 * k), bevel=4.0 * k, gloss=0.0, hi=0.65, lo=0.45,
             yr=(cy - 22 * k, cy + 22 * k), alpha=alpha)
    a, R = 20.5 * k, 16.0 * k
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        ox, oy = cx + sx * a, cy + sy * a
        mid = math.atan2(-sy, -sx)
        mx, my = ox + R * math.cos(mid) - 1.2 * k, oy + R * math.sin(mid) - 1.4 * k
        c.fill(F.sd_ellipse(*F.rot(c.X, c.Y, mx, my, mid + math.pi / 2), mx, my, 2.6 * k, 1.2 * k),
               WHITE, 0.7 * alpha, feather=0.5 * k)


def e_anger(c):
    """Manga anger cross-vein: four bulging curved pieces around a '+' shaped gap."""
    anger_vein(c, 32.0, 32.0)


def e_sweat(c):
    """Awkward smile '^^;' with a big sweat drop on the forehead."""
    cx, cy, r = 30, 34.5, 23.5
    dface = F.sd_circle(c.X, c.Y, cx, cy, r)
    dx, dy, dr = 50.0, 18.0, 6.9
    drop = F.sd_teardrop(c.X, c.Y, dx, dy, dr, dr * 2.1, tip=dr * 0.12)
    group_shadow(c, np.minimum(dface, drop), 2.5)
    face(c, cx, cy, r)
    cheeks(c, cx, cy, 15, 5.5, a=0.5)
    eye_happy(c, cx - 8.5, cy - 3.5, 3.9, 1.5)
    eye_happy(c, cx + 8.5, cy - 3.5, 3.9, 1.5)
    # wobbly awkward smile
    xs = np.linspace(cx - 7, cx + 7, 15)
    pts = [(x, cy + 9.5 + 1.3 * math.sin((x - cx) / 7 * math.pi * 1.5)) for x in xs]
    c.fill(F.sd_polyline(c.X, c.Y, pts, 1.35), hexc(INK))
    droplet(c, dx, dy, dr, 0, dr * 2.1, ow=2.0)


def e_music(c):
    X, Y = F.rot(c.X, c.Y, 32, 32, math.radians(-8))
    Y = Y - 2.5
    h1 = F.sd_ellipse(*F.rot(X, Y, 19, 47, math.radians(-24)), 19, 47, 8.2, 6.0)
    h2 = F.sd_ellipse(*F.rot(X, Y, 45, 41, math.radians(-24)), 45, 41, 8.2, 6.0)
    s1 = F.sd_box(X, Y, 25.4, 30.5, 2.3, 16.5, 1.0)
    s2 = F.sd_box(X, Y, 51.4, 24.5, 2.3, 16.5, 1.0)
    beam = F.sd_polygon(X, Y, [(23.1, 12.5), (53.7, 6.0), (53.7, 15.0), (23.1, 21.5)]) - 1.0
    d = F.union(h1, h2, s1, s2, beam)
    group_shadow(c, d, 2.5)
    part(c, d, 'purple', ow=2.5, bevel=4.0, gloss=0.0, hi=0.6, lo=0.45)
    for (hx, hy) in ((19, 47), (45, 41)):
        c.fill(F.sd_ellipse(*F.rot(X, Y, hx - 3.0, hy - 2.2, math.radians(-30)), hx - 3.0, hy - 2.2, 3.0, 1.6),
               WHITE, 0.8, feather=0.4)
    c.fill(F.sd_segment(X, Y, 27, 13.5, 44, 10, 1.1), WHITE, 0.55, feather=0.5)
    twinkle(c, 10.0, 15.5, 5.3, edge='#5A30B0', tip='#E6D6FF')


def _z(X, Y, x, y, w, h, t):
    """Z glyph: top bar, diagonal, bottom bar (round joins)."""
    return F.sd_polyline(X, Y, [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x - w / 2, y + h / 2),
                                (x + w / 2, y + h / 2)], t)


def e_zzz(c):
    zs = [(19.5, 43.5, 19.0, 3.3), (38.5, 26.0, 13.5, 2.6), (51.5, 12.5, 9.0, 2.0)]
    ds = [_z(c.X, c.Y, x, y, s, s, t) for x, y, s, t in zs]
    group_shadow(c, F.union(*ds), 2.3)
    for (x, y, s, t), d in zip(zs, ds):
        part(c, d, 'zzz', ow=2.2, bevel=t * 1.1, gloss=0.0, hi=0.6, lo=0.45)
        c.fill(F.sd_segment(c.X, c.Y, x - s / 2 + 0.5, y - s / 2 - t * 0.35, x + s / 2 - 1.5, y - s / 2 - t * 0.35,
                            t * 0.3), WHITE, 0.7, feather=0.4)


def e_idea(c):
    cx, cy, r = 32, 28.5, 13.8
    glass = F.smin(F.sd_circle(c.X, c.Y, cx, cy, r),
                   F.sd_polygon(c.X, c.Y, [(cx - 7.6, cy + 7.6), (cx + 7.6, cy + 7.6), (cx + 6.3, cy + 15.6),
                                           (cx - 6.3, cy + 15.6)]), 4.0)
    base = F.sd_box(c.X, c.Y, cx, cy + 19.6, 7.1, 5.0, 2.3)
    nub = F.sd_box(c.X, c.Y, cx, cy + 25.6, 3.4, 1.8, 1.5)
    rays = []
    for ang, ln in ((-162, 8.2), (-126, 9.0), (-90, 9.6), (-54, 9.0), (-18, 8.2)):
        a = math.radians(ang)
        r0, r1 = r + 4.2, r + ln
        rays.append(F.sd_segment(c.X, c.Y, cx + r0 * math.cos(a), cy + r0 * math.sin(a),
                                 cx + r1 * math.cos(a), cy + r1 * math.sin(a), 2.0))
    rd = F.union(*rays)
    allsh = F.union(glass, base, nub, rd)
    # warm glow behind the bulb
    rr = np.hypot(c.X - cx, c.Y - cy)
    c.paint(np.exp(-(rr / 14.0) ** 2) * np.clip((27.0 - rr) / 7.0, 0, 1), hexc('#FFE27A'), 0.55)
    group_shadow(c, allsh, 2.3)
    part(c, rd, 'gold', ow=1.8, bevel=2.0, gloss=0.0, hi=0.5, lo=0.3)
    part(c, nub, 'slate', ow=1.8, bevel=1.5, gloss=0.0)
    part(c, base, 'steel', ow=2.2, bevel=3.0, gloss=0.0, hi=0.6, lo=0.5)
    for gy in (cy + 18.0, cy + 21.4):
        c.fill(F.sd_segment(c.X, c.Y, cx - 6.0, gy - 0.9, cx + 6.0, gy + 0.9, 0.75), hexc('#6E7A8E'), 0.85)
    part(c, glass, 'gold', ow=2.4, bevel=7.0, gloss=0.0, hi=0.75, lo=0.35)
    # filament
    wires = F.union(F.sd_segment(c.X, c.Y, cx - 3.1, cy + 14, cx - 3.6, cy + 4, 0.75),
                    F.sd_segment(c.X, c.Y, cx + 3.1, cy + 14, cx + 3.6, cy + 4, 0.75))
    coil = F.sd_polyline(c.X, c.Y, [(cx - 3.6 + i * 0.9, cy + 4 + 1.4 * math.sin(i * 1.75)) for i in range(9)], 0.75)
    c.paint(np.exp(-(np.hypot(c.X - cx, c.Y - cy - 4) / 5.0) ** 2), WHITE, 0.6)
    c.fill(wires, hexc('#C9832E'), 0.75)
    c.fill(coil, hexc('#E0661A'), 0.95)
    glossy_spot(c, cx - 6.0, cy - 6.5, 4.2, 2.4, -40, 0.9, 0.6)
    c.fill(F.sd_circle(c.X, c.Y, cx - 9.5, cy - 0.5, 1.2), WHITE, 0.8)


def e_sparkle(c):
    """Three chunky 4-point twinkles (like the sparkle emoji), gold with dark-gold rims."""
    stars = [(25.5, 36.0, 21.0), (48.5, 15.5, 10.5), (50.0, 48.0, 7.5)]
    ds = [F.sd_star(c.X, c.Y, x, y, r, r * 0.34, 4, rot=-math.pi / 2, round_=r * 0.07) for x, y, r in stars]
    rr = np.hypot(c.X - 25.5, c.Y - 36)
    c.paint(np.exp(-(rr / 12.0) ** 2) * np.clip((26.0 - rr) / 6.0, 0, 1), hexc('#FFE27A'), 0.5)
    group_shadow(c, F.union(*ds), 2.2)
    for (x, y, r), d in zip(stars, ds):
        part(c, d, 'gold', ow=2.3 if r > 10 else 1.9, bevel=r * 0.22, gloss=0.0, hi=0.75, lo=0.4)
        q = np.hypot(c.X - x, c.Y - y)
        c.paint(c.cov(d) * np.exp(-(q / (r * 0.28)) ** 2), WHITE, 0.95)


def _dots(c, raised=None):
    ys = [35.0, 35.0, 35.0]
    rs = [6.2, 6.2, 6.2]
    if raised is not None:
        ys[raised] -= 5.0
        rs[raised] = 6.8
    xs = [15.0 + 17.0 * i for i in range(3)]
    ds = [F.sd_circle(c.X, c.Y, xs[i], ys[i], rs[i]) for i in range(3)]
    group_shadow(c, F.union(*ds), 2.0)
    for i, d in enumerate(ds):
        part(c, d, 'dots', ow=1.5, gloss=0.0, hi=0.45, lo=0.3, pillow=3.0)
        c.fill(F.sd_ellipse(c.X, c.Y, xs[i] - 2.0, ys[i] - 2.4, 1.8, 1.1), WHITE, 0.7, feather=0.5)


def e_dots(c):
    _dots(c, None)


def e_star(c):
    cx, cy = 32, 34.5
    d = F.sd_star(c.X, c.Y, cx, cy, 27.5, 13.5, 5, round_=3.6)
    group_shadow(c, d, 2.5)
    part(c, d, 'gold', ow=2.5, bevel=8.0, gloss=0.0, hi=0.65, lo=0.42)
    # facet hint: slightly lighter upper-left half of each arm
    glossy_spot(c, cx - 7.5, cy - 7.0, 4.6, 2.4, -40, 0.85, 0.6)
    c.fill(F.sd_circle(c.X, c.Y, cx - 13.5, cy - 2.5, 1.3), WHITE, 0.75)
    twinkle(c, 53.5, 10.5, 6.2)


def e_fish(c):
    X, Y = F.rot(c.X, c.Y, 32, 33, math.radians(-14))
    X = X + 1.5
    body = F.sd_ellipse(X, Y, 28, 33, 19.0, 12.0)
    tail = F.sd_polygon(X, Y, [(43, 33), (56.5, 22.0), (53.5, 33), (56.5, 44.0)]) - 1.6
    dorsal = F.sd_polygon(X, Y, [(21, 23.5), (31, 17.5), (37, 23.5)]) - 1.2
    pelvic = F.sd_polygon(X, Y, [(25, 42.5), (33, 49.5), (34, 42.0)]) - 1.0
    fins = F.union(tail, dorsal, pelvic)
    d = F.smin(body, tail, 2.0)
    group_shadow(c, F.union(d, fins), 2.4)
    yr = (16, 48)
    part(c, fins, 'blue', ow=2.2, bevel=2.5, gloss=0.0, hi=0.5, lo=0.4, yr=yr)
    # body: steel-blue back to pale belly
    toy(c, body, '#5E95DE', '#F2F7FF', '#173E78', ow=2.4, bevel=6.0, gloss=0.0, shadow=0, hi=0.5, lo=0.4,
        tint_lo=hexc('#3A62A8'), yr=(21, 41))
    # salmon lateral stripe (like item_fish_raw)
    stripe = np.abs(Y - 34.5) - 2.2
    c.paint(c.cov(stripe, 1.2) * c.cov(body + 2.2), hexc('#F79A78'), 0.75)
    # tail fin rays
    for yy in (27.5, 33, 38.5):
        c.fill(np.maximum(F.sd_segment(X, Y, 47, 33, 55, yy, 0.55), tail + 1.4), hexc('#2E5FA6'), 0.6)
    # gill + eye + mouth
    c.fill(np.maximum(F.sd_arc(X, Y, 15.5, 33, 9.5, math.radians(-40), math.radians(40), 0.75), body + 1.0),
           hexc('#2E5FA6'), 0.7)
    c.fill(F.sd_circle(X, Y, 16.0, 30.0, 4.0), hexc('#173E78'))
    c.fill(F.sd_circle(X, Y, 16.0, 30.0, 3.1), WHITE)
    c.fill(F.sd_circle(X, Y, 15.0, 30.2, 2.0), hexc(INK))
    c.fill(F.sd_circle(X, Y, 14.4, 29.3, 0.8), WHITE)
    c.fill(F.sd_segment(X, Y, 9.6, 35.2, 12.6, 35.8, 0.6), hexc('#173E78'), 0.9)
    glossy_spot(c, 26, 25.5, 6.5, 1.8, -14 - 4, 0.7, 0.6)


def e_bread(c):
    cx = 32
    dome = F.sd_ellipse(c.X, c.Y, cx, 41.5, 24.5, 18.5)
    dome = np.maximum(dome, c.Y - 49.0)
    base = F.sd_box(c.X, c.Y, cx, 47.5, 24.0, 5.0, 4.8)
    d = F.smin(dome, base, 3.0)
    steam = [F.sd_polyline(c.X, c.Y, [(x + 1.6 * math.sin(t * 2.2 + ph), 18.5 - t * 3.0) for t in np.linspace(0, 4, 12)],
                           1.5) for x, ph in ((24.5, 0.0), (36.5, 1.8))]
    group_shadow(c, d, 2.4)
    for s in steam:
        c.fill(s - 1.2, hexc('#8FA0BA'), 0.85)
        c.fill(s, WHITE, 0.95)
    part(c, d, 'bread', ow=2.5, bevel=7.5, gloss=0.25, hi=0.55, lo=0.45, gloss_h=0.5)
    # pale underside band
    c.paint(c.cov(d + 0.5) * np.clip((c.Y - 44) / 6, 0, 1), hexc('#F7D49A'), 0.55)
    # three score marks
    for k, sx in enumerate((-11, 0, 11)):
        x0, y0 = cx + sx - 3.6, 33.5 + abs(sx) * 0.22
        x1, y1 = cx + sx + 3.6, 27.0 + abs(sx) * 0.22
        sc = F.sd_segment(c.X, c.Y, x0, y0, x1, y1, 1.9)
        c.fill(sc - 0.9, hexc('#8A4214'), 0.8)
        c.fill(sc, hexc('#FCE3B0'))
    glossy_spot(c, cx - 11, 29.5, 4.2, 1.8, -28, 0.55, 0.8)


def _cuff(c, cx, cy, w, ang_deg):
    """Red parka sleeve stub with a white fur cuff (village style), centred at (cx,cy)."""
    X2, Y2 = F.rot(c.X, c.Y, cx, cy, math.radians(ang_deg))
    sleeve = F.sd_box(X2, Y2, cx, cy + 4.6, w * 0.46, 3.8, 2.2)
    fur = F.sd_box(X2, Y2, cx, cy, w * 0.56, 3.6, 3.4)
    for i in range(5):
        fur = F.smin(fur, F.sd_circle(X2, Y2, cx - w * 0.44 + i * w * 0.22, cy - 0.3 + (i % 2) * 0.6, 3.2), 1.6)
    return sleeve, fur


def e_wave(c):
    ang = 15
    X, Y = F.rot(c.X, c.Y, 33, 31, math.radians(ang))
    X = 33 + (X - 33) / 1.04         # draw the hand 4% bigger
    Y = 31 + (Y - 31) / 1.04
    cx, py = 33.0, 32.5
    palm = F.sd_box(X, Y, cx, py, 10.4, 9.2, 6.0)
    fingers = []
    for i, (dx, ln, a) in enumerate([(-7.4, 12.0, -17), (-2.5, 14.2, -6), (2.5, 13.6, 5), (7.3, 10.6, 16)]):
        bx, by = cx + dx, py - 4
        aa = math.radians(a)
        fingers.append(F.sd_segment(X, Y, bx, by, bx + ln * math.sin(aa), by - ln * math.cos(aa), 2.6))
    thumb = F.sd_segment(X, Y, cx - 8.5, py + 3.5, cx - 18.0, py - 3.0, 2.9)
    hand = F.smin(F.union(*fingers), palm, 1.2)
    hand = F.smin(hand, thumb, 1.8) * 1.04
    sleeve, fur = _cuff(c, 30.5, 48.8, 17, ang)
    motion = [F.sd_arc(c.X, c.Y, 33, 27.5, 26.0, math.radians(a0), math.radians(a1), 1.5)
              for a0, a1 in ((198, 228), (312, 342))]
    allsh = F.union(hand, sleeve, fur)
    group_shadow(c, allsh, 2.3)
    for m in motion:
        c.fill(m, hexc('#6F82A3'), 0.9)
    part(c, sleeve, 'parka', ow=2.0, bevel=2.5, gloss=0.0)
    part(c, hand, 'skin', ow=2.3, bevel=4.5, gloss=0.0, hi=0.55, lo=0.45, yr=(6, 50))
    # finger creases (each finger's edge, only above the palm)
    above = np.clip((py - 3.0 - Y) / 2.5, 0, 1)
    for f in fingers:
        c.paint(c.cov(np.abs(f * 1.04) - 0.45) * above * c.cov(hand + 1.0), hexc('#B86A48'), 0.9)
    c.fill(np.maximum(F.sd_arc(X, Y, cx - 13.0, py - 1.0, 7.0, math.radians(-20), math.radians(55), 0.5) * 1.04,
                      palm * 1.04 + 0.8), hexc('#B86A48'), 0.75)
    part(c, fur, 'fur', ow=1.8, bevel=2.5, gloss=0.0, hi=0.5, lo=0.4)


def e_thumbs(c):
    ang = -6
    X, Y = F.rot(c.X, c.Y, 32, 34, math.radians(ang))
    Y = Y + 3.0
    fist = F.sd_box(X, Y, 33.5, 37.5, 13.0, 11.5, 6.0)
    thumb = F.sd_segment(X, Y, 26.0, 30.0, 23.5, 12.0, 5.0)
    fingers = [F.sd_box(X, Y, 38.5, 28.6 + i * 6.2, 10.0, 3.2, 3.1) for i in range(4)]
    hand = F.smin(fist, thumb, 2.5)
    sleeve, fur = _cuff(c, 30.5, 50.0, 22, ang)
    allsh = F.union(hand, sleeve, fur, *fingers)
    group_shadow(c, allsh, 2.3)
    part(c, sleeve, 'parka', ow=2.2, bevel=3.0, gloss=0.0)
    part(c, hand, 'skin', ow=2.3, bevel=5.0, gloss=0.0, hi=0.55, lo=0.45, yr=(8, 50))
    for f in fingers:
        part(c, f, 'skin', ow=1.5, bevel=2.2, gloss=0.0, hi=0.55, lo=0.4, yr=(24, 50))
    # thumb nail
    c.fill(F.sd_ellipse(*F.rot(X, Y, 24.0, 13.6, math.radians(8)), 24.0, 13.6, 2.6, 2.0), hexc('#FFEDE0'), 0.9)
    part(c, fur, 'fur', ow=2.0, bevel=3.0, gloss=0.0, hi=0.5, lo=0.4)
    glossy_spot(c, 21.8, 17.0, 1.4, 3.6, ang, 0.6, 0.6)
    twinkle(c, 52.5, 10.5, 5.8)


def snowball(c, x, y, r, ow=1.8, crumbs=True):
    """Packed snowball: sphere-lit, cool blue shadow side, clumpy surface, crisp blue-grey rim."""
    d = F.sd_circle(c.X, c.Y, x, y, r)
    # slightly lumpy silhouette
    ang = np.arctan2(c.Y - y, c.X - x)
    d = d - r * 0.035 * (np.sin(ang * 5 + 0.7) + 0.6 * np.sin(ang * 9 + 2.1))
    c.fill(d - ow, hexc(PAL['snow'][2]))
    nx = (c.X - x) / r
    ny = (c.Y - y) / r
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.0, 1.0))
    n = np.dstack([nx, ny, nz]).astype(np.float32)
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    t = np.clip((c.Y - (y - r)) / (2 * r), 0, 1)
    col = F.shade(F.mix(hexc('#FFFFFF'), hexc('#DCE7F5'), t), F.lambert(n), 0.5, 0.75, hexc('#7E9CCC'))
    c.paint(c.cov(d), col)
    if crumbs:
        rng = np.random.default_rng(5)
        for _ in range(9):
            a = rng.uniform(0, 2 * math.pi)
            rr = math.sqrt(rng.uniform(0.05, 0.75)) * r
            px_, py_ = x + rr * math.cos(a), y + rr * math.sin(a)
            cr = r * rng.uniform(0.09, 0.15)
            lit = (-(px_ - x) * 0.55 - (py_ - y) * 0.62) / r
            c.fill(F.sd_circle(c.X, c.Y, px_ + cr * 0.35, py_ + cr * 0.45, cr), hexc('#A9BCD8'), 0.55)
            c.fill(F.sd_circle(c.X, c.Y, px_, py_, cr), hexc('#FFFFFF') if lit > -0.2 else hexc('#E6EEF8'), 0.9)
    glossy_spot(c, x - r * 0.38, y - r * 0.42, r * 0.22, r * 0.13, -40, 0.9, 0.4)
    return d


def e_snowball(c):
    x, y, r = 27.0, 37.0, 17.5
    lines = [F.sd_segment(c.X, c.Y, 46.0 + dx, yy, 58.5, yy - 5.5, 0) - (0.9 + 1.4 * np.clip((58.5 - c.X) / 12.5, 0, 1))
             for yy, dx in ((25.5, 2.0), (35.0, -1.0), (44.5, 2.5))]
    bits = [(47.0, 49.0, 2.4), (52.5, 15.5, 1.9), (43.0, 17.0, 1.5)]
    dball = F.sd_circle(c.X, c.Y, x, y, r)
    group_shadow(c, F.union(dball, *lines), 2.0)
    for ln in lines:
        c.fill(ln - 1.4, hexc('#56739F'))
        c.fill(ln, WHITE)
    for bx, by, br in bits:
        c.fill(F.sd_circle(c.X, c.Y, bx, by, br + 1.3), hexc('#56739F'))
        c.fill(F.sd_circle(c.X, c.Y, bx, by, br), WHITE)
    snowball(c, x, y, r, ow=2.2)


def e_cold(c):
    """Blue shivering face: worried brows, chattering teeth, red nose, a snow lump on the head,
    vibration marks on both sides."""
    cx, cy, r = 32, 35.0, 21.5
    dface = F.sd_circle(c.X, c.Y, cx, cy, r)
    cap = None
    for (x, y, rr) in ((cx - 6.0, cy - 20.0, 6.0), (cx + 2.5, cy - 22.5, 6.8), (cx + 10.0, cy - 19.0, 5.0),
                       (cx - 12.5, cy - 16.0, 3.8)):
        e = F.sd_circle(c.X, c.Y, x, y, rr)
        cap = e if cap is None else F.smin(cap, e, 2.6)
    marks = []
    for mid in (0.0, math.pi):
        for rad, span in ((r + 4.2, 22), (r + 7.6, 15)):
            marks.append(F.sd_arc(c.X, c.Y, cx, cy + 1.0, rad, mid - math.radians(span), mid + math.radians(span), 1.1))
    group_shadow(c, F.union(dface, cap), 2.5)
    for m in marks:
        c.fill(m, hexc('#3F6FB4'), 0.95)
    face(c, cx, cy, r, pal='cold')
    brows_worried(c, cx, cy - 8.5, 8.3, 1.25, 5.2, 24)
    eye_dot(c, cx - 8.0, cy - 2.5, 2.6, 3.3)
    eye_dot(c, cx + 8.0, cy - 2.5, 2.6, 3.3)
    # rosy cold cheeks + red nose
    cheeks(c, cx, cy, 13.5, 5.0, 3.6, 2.3, a=0.45)
    nose = F.sd_ellipse(c.X, c.Y, cx, cy + 3.0, 2.8, 2.2)
    part(c, nose, 'red', ow=0.9, bevel=1.6, gloss=0.0, hi=0.6, lo=0.3)
    c.fill(F.sd_circle(c.X, c.Y, cx - 1.0, cy + 2.3, 0.75), WHITE, 0.85)
    # chattering teeth
    mt = F.sd_box(c.X, c.Y, cx, cy + 10.5, 8.0, 3.5, 2.5)
    c.fill(mt - 1.1, hexc('#24406E'))
    c.fill(mt, hexc('#FFFFFF'))
    zig = F.sd_polyline(c.X, c.Y, [(cx - 7.2 + i * 1.8, cy + 10.5 + (0.85 if i % 2 else -0.85)) for i in range(9)], 0.5)
    c.fill(np.maximum(zig, mt + 0.3), hexc('#5A78A8'), 0.95)
    # snow lump on the head
    part(c, cap, 'snow', ow=1.8, bevel=3.0, gloss=0.0, hi=0.45, lo=0.5)
    c.fill(F.sd_ellipse(c.X, c.Y, cx - 0.5, cy - 25.0, 2.6, 1.2), WHITE, 0.9, feather=0.5)


def e_tear(c):
    """Sad crying face: worried brows, glossy teary eyes, wobbly frown, tear rolling down."""
    cx, cy, r = 31.5, 32.5, 23.5
    dface = F.sd_circle(c.X, c.Y, cx, cy, r)
    group_shadow(c, dface, 2.5)
    face(c, cx, cy, r)
    cheeks(c, cx, cy, 15, 6.0, a=0.45)
    brows_worried(c, cx, cy - 10.0, 8.6, 1.3, 6.0, 26)
    for s in (-1, 1):
        ex, ey = cx + s * 8.6, cy - 2.0
        eye_dot(c, ex, ey, 3.4, 4.3, big_glint=True)
        # tear pool along the lower lid
        pool = np.maximum(F.sd_ellipse(c.X, c.Y, ex, ey + 2.6, 4.6, 2.6), (ey + 1.6) - c.Y)
        c.fill(pool - 0.7, hexc('#1B5296'), 0.85)
        c.fill(pool, hexc('#8FD0FF'), 0.95)
    # frown
    c.fill(F.sd_arc(c.X, c.Y, cx, cy + 16.5, 6.0, math.radians(218), math.radians(322), 1.4), hexc(INK))
    # tears rolling down both cheeks (the right one big)
    droplet(c, cx + 11.0, cy + 10.5, 4.4, 0, 9.0, ow=1.6)
    droplet(c, cx - 11.5, cy + 8.0, 3.0, 0, 6.2, ow=1.4)
    droplet(c, cx + 13.5, cy + 21.5, 2.4, 0, 5.0, ow=1.3)


# fx_snowball: projectile (28x28 frame, ~24 px ball incl. outline)
def fx_snowball(c):
    snowball(c, 14.0, 14.0, 10.6, ow=1.5)


EMOTES = [
    ('emote_heart', e_heart, 'Big glossy pink heart (like / love).'),
    ('emote_love', e_love, 'Face with heart eyes + blush (loves it / crush).'),
    ('emote_laugh', e_laugh, 'Squinting laughing face (>< eyes, wide open mouth) with tears flying.'),
    ('emote_exclaim', e_exclaim, 'Red "!" (surprise / alert / got hit).'),
    ('emote_question', e_question, 'Blue "?" (confused / what?).'),
    ('emote_anger', e_anger, 'Red manga cross-vein (angry / sulking).'),
    ('emote_sweat', e_sweat, 'Awkward smile ^^; with a big sweat drop (embarrassed / nervous).'),
    ('emote_music', e_music, 'Purple beamed notes (singing / bard performing).'),
    ('emote_zzz', e_zzz, 'Three blue Z shapes (sleeping / dozing on the bench).'),
    ('emote_idea', e_idea, 'Glowing light bulb (idea!).'),
    ('emote_sparkle', e_sparkle, 'Gold twinkles (pretty / impressed / new).'),
    ('emote_cold', e_cold, 'Blue shivering face, chattering teeth, red nose, snow on the head.'),
    ('emote_tear', e_tear, 'Sad crying face with tears (sad / hurt feelings).'),
    ('emote_dots', e_dots, 'Typing dots "..." (static). Animated version: sprites.emote_dots.anims.typing.'),
    ('emote_star', e_star, 'Gold star (great job / best).'),
    ('emote_fish', e_fish, 'Fish (talking about fish / wants fish).'),
    ('emote_bread', e_bread, 'Warm bread loaf with steam (talking about bread / hungry).'),
    ('emote_wave', e_wave, 'Waving hand with a red parka cuff (hello / bye).'),
    ('emote_thumbs', e_thumbs, 'Thumbs up with a red parka cuff (good / nice).'),
    ('emote_snowball', e_snowball, 'Flying snowball (snowball fight! / challenge).'),
]
DOTS_FRAMES = [('emote_dots_a%d' % i, (lambda i_: (lambda c: _dots(c, i_)))(i)) for i in range(3)]


def render(fn, S=64, ss=4, out=None, margin=1.0, pad=12):
    """Draw `fn` in 64-unit coordinates and return an S x S PIL RGBA image (optionally resized to `out`).
    The art is drawn on a padded canvas; if anything (tear, ray, sleeve, shadow) pokes out of the
    64-unit frame, the frame is widened symmetrically about the centre and scaled back to S so the
    icon is never clipped and keeps `margin` units of clear space.  Most icons fit at scale 1."""
    k = S / 64.0
    c = F.Canvas(64 + 2 * pad, 64 + 2 * pad, ss=max(1, int(round(ss * k))))
    c.X -= pad
    c.Y -= pad
    fn(c)
    ys, xs = np.where(c.a > 0.06)
    e = 32.0
    if xs.size:
        px = 1.0 / c.ss
        x0, x1 = xs.min() * px - pad, (xs.max() + 1) * px - pad
        y0, y1 = ys.min() * px - pad, (ys.max() + 1) * px - pad
        e = max(32.0, 32 - x0 + margin, x1 - 32 + margin, 32 - y0 + margin, y1 - 32 + margin)
    e = min(e, 32.0 + pad)
    R = c.region(pad + 32 - e, pad + 32 - e, pad + 32 + e, pad + 32 + e)
    return R.image(out or (S, S))


def fit_scale(fn):
    """Scale factor render() applies to keep `fn` inside its frame (1.0 = no shrink)."""
    c = F.Canvas(88, 88, ss=2)
    c.X -= 12
    c.Y -= 12
    fn(c)
    ys, xs = np.where(c.a > 0.06)
    if not xs.size:
        return 1.0
    px = 0.5
    e = max(32.0, 32 - (xs.min() * px - 12) + 1.0, (xs.max() + 1) * px - 12 - 32 + 1.0,
            32 - (ys.min() * px - 12) + 1.0, (ys.max() + 1) * px - 12 - 32 + 1.0)
    return round(32.0 / e, 3)
