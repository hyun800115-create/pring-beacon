"""
gen_fx.py - procedural particles + animated effect sheets for Frost Village (CONTRACT §5).

Re-run (from anywhere; deterministic, ~1-2 min on 1 core):
    python3 frost-village/tools/fx/gen_fx.py                 # build everything
    python3 frost-village/tools/fx/gen_fx.py --only fx_fire  # scratch preview of some keys
                                                             #   -> tools/fx/_cache/fx_only.png (+ gif)
    python3 frost-village/tools/fx/gen_fx.py --no-gif        # skip the preview GIFs
Outputs:
    assets/fx/fx_particles.png/.json   particle atlas (Phaser JSON hash, untrimmed frames)
    assets/fx/fx_<sheet>.png           horizontal animation strips (fixed frame size)
    assets/fx/manifest.json
    docs/previews/fx_sheet.png, docs/previews/fx_<sheet>.gif
Colour policy: particles are white/greyscale (the game tints them) except fx_heart (pink),
fx_flame (orange) and fx_coin (gold).  Sheets carry their own colours.  Every sheet uses NORMAL
blending on purpose: the world is mostly near-white snow where ADD blending is invisible, so
glows/sparkles/fire are painted with saturated cores and soft warm rims that read on snow,
plaza and sea alike (see manifest notes).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # frost-village/
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))              # tools/ (pack_utils)
import fxlib as F                                       # noqa: E402
from fxlib import hexc, toy, stroke                     # noqa: E402
import pack_utils                                       # noqa: E402

OUT = os.path.join(ROOT, 'assets', 'fx')
PREV = os.path.join(ROOT, 'docs', 'previews')
CACHE = os.path.join(HERE, '_cache')

WHITE = hexc('#FFFFFF')
G = lambda v: np.array([v, v, v], np.float32)          # neutral grey (tint friendly)


# =========================================================================== shared drawing
def puff_sdf(c, blobs, k):
    """Union (smooth) of circles [(x, y, r), ...]."""
    d = None
    for (x, y, r) in blobs:
        e = F.sd_circle(c.X, c.Y, x, y, r)
        d = e if d is None else F.smin(d, e, k)
    return d


def soft_mask(c, d, sigma):
    """Feathered coverage (blurred) - soft rim without interior blob artefacts."""
    return F.smoothstep(0.12, 0.8, F.blur(c.cov(d), sigma * c.ss))


def cloud(c, d, top, bot, lo_tint, alpha=1.0, bevel=10.0, feather=0.0, rim=None, rim_a=0.0):
    """Soft cotton-ball shading: vertical gradient, rounded bevel lit from the upper left."""
    ys = c.Y[d < 0]
    if ys.size == 0:
        return
    y0, y1 = float(ys.min()), float(ys.max())
    t = np.clip((c.Y - y0) / max(1.0, y1 - y0), 0, 1)
    base = F.mix(hexc(top) if isinstance(top, str) else top, hexc(bot) if isinstance(bot, str) else bot, t)
    n = F.pillow_normals(c.cov(d), bevel, c.ss, depth=1.1)
    col = F.shade(base, F.lambert(n), 0.5, 0.75, hexc(lo_tint) if isinstance(lo_tint, str) else lo_tint)
    if rim is not None and rim_a:
        c.paint(c.cov(d - 1.2, feather), hexc(rim), alpha * rim_a)
    c.paint(c.cov(d, feather), col, alpha)


def glint(c, x, y, s, core='#FFFFFF', glow='#FFD45A', edge=None, a=1.0, rot_=0.0, glow_a=0.55, thin=0.5,
          tip=None, halo=0.45):
    """Twinkle star of arm length s with a soft coloured halo, optional thin edge and
    optional tip colour (arms fade from core to tip)."""
    if s <= 0.3 or a <= 0.01:
        return
    R = c.region(x - s * 1.6, y - s * 1.6, x + s * 1.6, y + s * 1.6)
    if R.empty:
        return
    r = np.hypot(R.X - x, R.Y - y)
    if glow is not None:
        R.paint(np.exp(-(r / (s * halo)) ** 2), hexc(glow), glow_a * a)
    d = F.sd_glint(R.X, R.Y, x, y, s, s, R.px, rot_=rot_, pinch=thin)
    if edge is not None:
        R.fill(d - max(0.7, s * 0.06), hexc(edge), 0.85 * a)
    if tip is not None:
        R.paint(R.cov(d), F.mix(hexc(core), hexc(tip), np.clip(r / s, 0, 1) ** 0.8), a)
    else:
        R.fill(d, hexc(core), a)
    R.fill(F.sd_circle(R.X, R.Y, x, y, s * 0.16), WHITE, a)


def star5(c, x, y, r, rot_, top='#FFF3B0', bot='#FFC83D', outline='#B8650E', a=1.0, ow=None):
    R = c.region(x - r * 1.5, y - r * 1.5, x + r * 1.5, y + r * 1.6)
    if R.empty or a <= 0.01 or r < 0.5:
        return
    d = F.sd_star(R.X, R.Y, x, y, r, r * 0.48, 5, rot=-math.pi / 2 + rot_, round_=r * 0.14)
    toy(R, d, top, bot, outline, ow=ow if ow is not None else max(0.8, r * 0.13), bevel=r * 0.35,
        gloss=0.0, shadow=0.0, hi=0.6, lo=0.4, alpha=a)


def coin(c, cx, cy, R, theta=0.0):
    """Gold coin with embossed star turned by theta about the vertical axis (0 = facing).
    Thickness band shows on the side that turns away."""
    ct, st = math.cos(theta), math.sin(theta)
    rx = max(R * abs(ct), 0.6)
    T = R * 0.20                                         # coin thickness (screen px when edge-on)
    off = T * st                                         # where the back face sits
    face = F.sd_ellipse(c.X, c.Y, cx - off / 2, cy, rx, R)
    back = F.sd_ellipse(c.X, c.Y, cx + off / 2, cy, rx, R)
    band = F.sd_box(c.X, c.Y, cx, cy, abs(off) / 2 + 0.01, R * 0.985, 0)
    body = np.minimum(np.minimum(face, back), band)
    # soft outline + edge band
    c.fill(body - R * 0.07, hexc('#7A4A0E'))
    edge_col = F.mix(hexc('#E0A030'), hexc('#9A6312'), np.clip((c.Y - (cy - R)) / (2 * R), 0, 1))
    c.paint(c.cov(body), edge_col)
    # milled ridges on the band (vertical stripes)
    ridge = (0.5 + 0.5 * np.cos((c.Y - cy) / R * 30)) * c.cov(body) * c.cov(-face)
    c.paint(ridge, hexc('#7E4F0E'), 0.35)
    # face: bevelled rim + recessed field + embossed star (all squashed by cos(theta))
    light = 0.15 + 0.85 * (0.5 + 0.5 * math.cos(theta + 0.5))   # facing the upper-left sun
    fx_ = (c.X - (cx - off / 2)) / max(abs(ct), 0.05) + cx      # unsquash x for face details
    rim_d = F.sd_circle(fx_, c.Y, cx, cy, R)
    n = F.bevel_normals(rim_d * abs(ct) if abs(ct) > 0.05 else face, R * 0.16, c.px)
    t = np.clip((c.Y - (cy - R)) / (2 * R), 0, 1)
    base = F.mix(hexc('#FFE58A'), hexc('#E9A92C'), t)
    col = F.shade(base, F.lambert(n), 0.6, 0.5)
    col = col * (0.75 + 0.25 * light)
    c.paint(c.cov(face), col)
    if abs(ct) > 0.18:
        inner = F.sd_circle(fx_, c.Y, cx, cy, R * 0.74) * abs(ct)
        c.paint(c.cov(inner), F.mix(hexc('#F7C850'), hexc('#EDAE36'), t) * (0.78 + 0.22 * light))
        stroke(c, inner, R * 0.05, '#C8861E', 0.6)
        sd = F.sd_star(fx_, c.Y, cx, cy + R * 0.03, R * 0.52, R * 0.24, 5, round_=R * 0.07) * abs(ct)
        c.shadow(c.cov(sd), dx=R * 0.03, dy=R * 0.05, sigma=R * 0.03, color='#8A5A12', opacity=0.45)
        ns = F.bevel_normals(sd, R * 0.1, c.px)
        scol = F.shade(F.mix(hexc('#FFF0B0'), hexc('#F5B83A'), t), F.lambert(ns), 0.75, 0.55)
        c.paint(c.cov(sd), scol * (0.8 + 0.2 * light))
    # moving specular sweep (sells the rotation)
    sweep = math.sin(theta * 2.0)
    band_x = cx - off / 2 + rx * (-0.45 + 0.9 * (0.5 - 0.5 * sweep))
    sp = np.exp(-((c.X - band_x - (c.Y - cy) * 0.35) / (R * 0.16)) ** 2) * c.cov(face + R * 0.08)
    c.paint(sp, WHITE, 0.35 + 0.25 * abs(sweep))
    if abs(ct) > 0.3:
        ex, ey = cx - off / 2 - rx * 0.5, cy - R * 0.52
        g = F.sd_glint(c.X, c.Y, ex, ey, R * 0.22 * abs(ct) + 0.5, R * 0.22, c.px)
        c.fill(g, WHITE, 0.9)


# =========================================================================== particles
def p_spark(S=64):
    c = F.Canvas(S, S)
    cx = cy = S / 2
    r = np.hypot(c.X - cx, c.Y - cy)
    c.paint(np.exp(-(r / (S * 0.17)) ** 2), WHITE, 0.6)
    c.fill(F.sd_glint(c.X, c.Y, cx, cy, S * 0.30, S * 0.47, c.px, pinch=0.45), WHITE, feather=0.6)
    c.fill(F.sd_glint(c.X, c.Y, cx, cy, S * 0.16, S * 0.16, c.px, rot_=math.pi / 4, pinch=0.5), WHITE, 0.8, feather=0.5)
    return c.image()


def p_star(S=64):
    c = F.Canvas(S, S)
    d = F.sd_star(c.X, c.Y, S / 2, S * 0.53, S * 0.45, S * 0.215, 5, round_=S * 0.06)
    toy(c, d, G(1.0), G(0.86), G(0.55), ow=S * 0.035, bevel=S * 0.15, gloss=0.25, shadow=0, hi=0.7, lo=0.45,
        tint_lo=G(0.62))
    return c.image()


def p_glow(S=128):
    c = F.Canvas(S, S, ss=2)
    r = np.hypot(c.X - S / 2, c.Y - S / 2) / (S / 2)
    a = np.exp(-(r / 0.42) ** 2) * np.clip((1 - r) / 0.12, 0, 1)
    c.paint(a, WHITE)
    return c.image()


def p_smoke(S=128):
    c = F.Canvas(S, S, ss=2)
    k = S / 128
    blobs = [(52, 74, 30), (80, 70, 26), (66, 50, 28), (42, 56, 18), (90, 52, 16), (66, 82, 24)]
    d = puff_sdf(c, [(x * k, y * k, r * k) for x, y, r in blobs], 10 * k)
    L = c.layer()
    cloud(L, d, G(1.0), G(0.93), G(0.70), bevel=16 * k)
    c.over(L, mask=soft_mask(c, d, 7 * k))                   # soft feathered rim
    return c.image()


def p_snowflake(S=64):
    c = F.Canvas(S, S)
    cx = cy = S / 2
    R = S * 0.39
    d = F.sd_circle(c.X, c.Y, cx, cy, S * 0.09)
    for i in range(6):
        a = i * math.pi / 3 - math.pi / 2
        ex, ey = cx + R * math.cos(a), cy + R * math.sin(a)
        d = np.minimum(d, F.sd_segment(c.X, c.Y, cx, cy, ex, ey, S * 0.045))
        for f, L in ((0.5, 0.36), (0.75, 0.24)):
            bx, by = cx + R * f * math.cos(a), cy + R * f * math.sin(a)
            for s_ in (-1, 1):
                b = a + s_ * math.radians(48)
                d = np.minimum(d, F.sd_segment(c.X, c.Y, bx, by, bx + R * L * math.cos(b), by + R * L * math.sin(b), S * 0.035))
    r = np.hypot(c.X - cx, c.Y - cy)
    c.paint(np.exp(-(r / (S * 0.26)) ** 2) * np.clip((S * 0.5 - r) / (S * 0.1), 0, 1), WHITE, 0.35)
    c.fill(d - S * 0.025, G(0.72), 0.9)
    c.fill(d, WHITE)
    return c.image()


def p_chip_wood(S=48):
    c = F.Canvas(S, S)
    X, Y = F.rot(c.X, c.Y, S / 2, S / 2, math.radians(-28))
    pts = [(8, 21), (20, 17.5), (38, 19), (42, 24), (36, 29), (18, 31), (7, 27)]
    d = F.sd_polygon(X, Y, [(x * S / 48, y * S / 48) for x, y in pts]) - S * 0.03
    toy(c, d, G(1.0), G(0.84), G(0.42), ow=S * 0.045, bevel=S * 0.08, gloss=0.15, shadow=0, hi=0.6, lo=0.5)
    # grain lines + lighter end grain
    for gy in (22.5, 25.5, 28):
        g = np.maximum(np.abs(Y - gy * S / 48) - S * 0.012, d + S * 0.06)
        c.fill(g, G(0.66), 0.6)
    end = F.intersect(d + S * 0.01, X - S * 0.76)
    c.fill(end, G(0.97), 0.9)
    return c.image()


def p_chip_rock(S=48):
    c = F.Canvas(S, S)
    k = S / 48
    pts = [(10, 26), (15, 13), (28, 9), (39, 17), (40, 30), (29, 39), (15, 37)]
    pts = [(x * k, y * k) for x, y in pts]
    d = F.sd_polygon(c.X, c.Y, pts) - 1.0 * k
    c.fill(d - 2.0 * k, G(0.38))
    c.fill(d, G(0.70))
    top = F.intersect(F.sd_polygon(c.X, c.Y, [(13 * k, 25 * k), (16 * k, 14 * k), (28 * k, 10.5 * k), (36 * k, 17 * k), (27 * k, 24 * k)]), d)
    left = F.intersect(F.sd_polygon(c.X, c.Y, [(11 * k, 26 * k), (27 * k, 24.5 * k), (28 * k, 37 * k), (16 * k, 36 * k)]), d)
    c.fill(top, G(0.99))
    c.fill(left, G(0.84))
    c.fill(F.sd_circle(c.X, c.Y, 19 * k, 16 * k, 2.2 * k), WHITE, 0.9, feather=0.6 * k)
    return c.image()


def p_droplet(S=48):
    c = F.Canvas(S, S)
    d = F.sd_teardrop(c.X, c.Y, S / 2, S * 0.62, S * 0.24, S * 0.48, tip=S * 0.02)
    c.fill(d - S * 0.035, G(0.62), 0.9)
    t = np.clip((c.Y - S * 0.12) / (S * 0.75), 0, 1)
    n = F.bevel_normals(d, S * 0.2, c.px)
    col = F.shade(F.mix(G(1.0), G(0.86), t), F.lambert(n), 0.6, 0.5)
    c.paint(c.cov(d), col, 0.95)
    c.fill(F.sd_ellipse(c.X, c.Y, S * 0.43, S * 0.56, S * 0.05, S * 0.09), WHITE, 0.95)
    return c.image()


def p_wheat_bit(S=48):
    c = F.Canvas(S, S)
    X, Y = F.rot(c.X, c.Y, S / 2, S / 2, math.radians(35))
    seed = F.sd_ellipse(X, Y, S / 2, S * 0.56, S * 0.16, S * 0.28)
    awn = F.sd_segment(X, Y, S / 2, S * 0.32, S * 0.52, S * 0.14, S * 0.02)
    d = np.minimum(seed, awn)
    toy(c, d, G(1.0), G(0.84), G(0.5), ow=S * 0.035, bevel=S * 0.1, gloss=0.25, shadow=0, hi=0.6, lo=0.45)
    groove = np.maximum(np.abs(X - S / 2) - S * 0.012, seed + S * 0.05)
    c.fill(groove, G(0.7), 0.7)
    return c.image()


def p_heart(S=64):
    c = F.Canvas(S, S)
    hs = S * 0.355
    d = F.sd_heart_iq(c.X, c.Y, S / 2, S / 2 + 0.265 * hs, hs) - S * 0.025
    toy(c, d, '#FF9BB5', '#E8467A', '#9E2350', ow=S * 0.04, gloss=0.0, shadow=0, hi=0.55, lo=0.45, pillow=S * 0.12)
    c.fill(F.sd_ellipse(*F.rot(c.X, c.Y, S * 0.36, S * 0.36, math.radians(-35)), S * 0.36, S * 0.36, S * 0.075, S * 0.045), WHITE, 0.85)
    c.fill(F.sd_circle(c.X, c.Y, S * 0.27, S * 0.45, S * 0.025), WHITE, 0.7)
    return c.image()


def p_ring(S=128):
    c = F.Canvas(S, S, ss=2)
    r = np.hypot(c.X - S / 2, c.Y - S / 2)
    R = S * 0.40
    c.paint(np.exp(-((r - R) / (S * 0.07)) ** 2), WHITE, 0.45)
    c.fill(np.abs(r - R) - S * 0.03, WHITE, feather=0.8)
    return c.image()


def flame_layers(c, cx, by, h, w, sway=0.0, wob=0.0, phase=0.0, a=1.0, colours=None):
    """Toy flame: nested teardrops (red-orange rim -> yellow -> pale core)."""
    colours = colours or [('#FF5A1F', 1.0), ('#FF8A2A', 1.0), ('#FFC23A', 1.0), ('#FFF1B8', 0.95)]
    for j, (col, al) in enumerate(colours):
        s = 1.0 - j * 0.2
        hh = h * s
        r = w * s
        cy = by - r
        ty = np.clip((cy - c.Y) / max(hh, 1e-3), 0, 1)
        Xw = c.X - sway * ty ** 2 * hh * 0.35 - wob * np.sin(c.Y * 0.25 + phase) * ty * w * 0.12
        d = F.sd_teardrop(Xw, c.Y, cx, cy, r, hh, tip=r * 0.12)
        c.fill(d, hexc(col), al * a, feather=0.4 + 0.3 * j)


def p_flame(S=64):
    c = F.Canvas(S, S)
    r = np.hypot(c.X - S / 2, c.Y - S * 0.62)
    c.paint(np.exp(-(r / (S * 0.26)) ** 2) * np.clip((S * 0.5 - np.hypot(c.X - S / 2, c.Y - S / 2)) / (S * 0.12), 0, 1),
            hexc('#FF9A3A'), 0.35)
    flame_layers(c, S / 2, S * 0.92, S * 0.56, S * 0.22, sway=0.2)
    return c.image()


def p_coin(S=64):
    c = F.Canvas(S, S)
    coin(c, S / 2, S / 2, S * 0.44, 0.0)
    return c.image()


def p_leaf(S=48):
    c = F.Canvas(S, S)
    X, Y = F.rot(c.X, c.Y, S / 2, S / 2, math.radians(-40))
    a = F.sd_circle(X, Y, S / 2 - S * 0.21, S / 2, S * 0.32)
    b = F.sd_circle(X, Y, S / 2 + S * 0.21, S / 2, S * 0.32)
    d = np.maximum(a, b)
    d = np.minimum(d, F.sd_segment(X, Y, S / 2, S * 0.78, S / 2 + S * 0.02, S * 0.92, S * 0.025))
    toy(c, d, G(1.0), G(0.85), G(0.5), ow=S * 0.035, bevel=S * 0.1, gloss=0, shadow=0, hi=0.55, lo=0.5)
    shade_half = F.intersect(d + S * 0.02, X - S / 2)
    c.fill(shade_half, G(0.82), 0.55)
    c.fill(np.maximum(np.abs(X - S / 2) - S * 0.012, d + S * 0.05), G(0.62), 0.8)
    for yy in (0.36, 0.5, 0.64):
        for s_ in (-1, 1):
            v = F.sd_segment(X, Y, S / 2, yy * S, S / 2 + s_ * S * 0.13, yy * S - S * 0.08, S * 0.009)
            c.fill(np.maximum(v, d + S * 0.06), G(0.68), 0.6)
    return c.image()


def p_dust(S=96):
    c = F.Canvas(S, S, ss=2)
    k = S / 96
    blobs = [(38, 56, 20), (58, 54, 22), (48, 42, 18), (70, 46, 13), (28, 48, 11)]
    d = puff_sdf(c, [(x * k, y * k, r * k) for x, y, r in blobs], 14 * k)
    L = c.layer()
    cloud(L, d, G(1.0), G(0.92), G(0.74), bevel=14 * k)
    c.over(L, 0.85, mask=soft_mask(c, d, 7 * k))
    return c.image()


PARTICLES = {
    'fx_spark': (p_spark, True, 'Four-point glint. Tint gold/white.'),
    'fx_star': (p_star, True, 'Rounded 5-point star with grey rim (reads on snow when tinted).'),
    'fx_glow': (p_glow, True, 'Soft round gaussian glow (fills ~70% of the frame).'),
    'fx_smoke': (p_smoke, True, 'Cotton-ball smoke puff with feathered rim.'),
    'fx_snowflake': (p_snowflake, True, '6-arm snowflake with faint grey edge + halo.'),
    'fx_chip_wood': (p_chip_wood, True, 'Wood splinter (tint brown).'),
    'fx_chip_rock': (p_chip_rock, True, 'Faceted rock chip (tint grey / ore orange).'),
    'fx_droplet': (p_droplet, True, 'Teardrop pointing UP (rotate along velocity).'),
    'fx_wheat_bit': (p_wheat_bit, True, 'Wheat grain with awn (tint wheat yellow).'),
    'fx_heart': (p_heart, False, 'Pink heart, colours baked (do not tint).'),
    'fx_ring': (p_ring, True, 'Thin soft ring, radius 0.40 of the frame.'),
    'fx_flame': (p_flame, False, 'Orange flame tongue, colours baked; base at the bottom.'),
    'fx_coin': (p_coin, False, 'Gold coin with embossed star, colours baked.'),
    'fx_leaf': (p_leaf, True, 'Leaf with midrib (tint green).'),
    'fx_dust': (p_dust, True, 'Soft low dust puff (lighter than fx_smoke).'),
}


# =========================================================================== animated sheets
def ball(c, x, y, r, a=1.0, top='#FFFFFF', bot='#E4ECF6', lo='#93A9CA', rim='#A9BCD8'):
    """Cotton ball: sphere-lit circle with a soft cool rim (reads on white snow)."""
    if r < 0.5 or a <= 0.01:
        return
    R = c.region(x - r - 3, y - r - 3, x + r + 3, y + r + 3)
    if R.empty:
        return
    d = F.sd_circle(R.X, R.Y, x, y, r)
    R.fill(d - max(0.7, r * 0.07), hexc(rim), a)
    nx = (R.X - x) / r
    ny = (R.Y - y) / r
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.0, 1.0))
    n = np.dstack([nx, ny, nz]).astype(np.float32)
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    t = np.clip((R.Y - (y - r)) / (2 * r), 0, 1)
    col = F.shade(F.mix(hexc(top), hexc(bot), t), F.lambert(n), 0.5, 0.65, hexc(lo))
    R.paint(R.cov(d), col, a)


def sh_poof(i, n, S=128):
    """Snowy cloud burst: cotton balls shoot out on an iso ellipse, swell, then shrink away."""
    t = (i + 0.7) / (n - 1 + 0.7)                      # frame 0 already shows the pop
    c = F.Canvas(S, S)
    cx, cy = S / 2, S * 0.60
    rng = np.random.default_rng(11)
    balls = []
    K = 10
    for k in range(K):
        a = 2 * math.pi * k / K + rng.uniform(-0.2, 0.2)
        dist = rng.uniform(32, 42)
        rmax = rng.uniform(11, 16)
        tt = F.clamp01(t * 1.05 - rng.uniform(0, 0.05))
        p = F.ease_out(tt, 2.6)
        x = cx + math.cos(a) * (5 + dist * p)
        y = cy + math.sin(a) * (3 + dist * p) * 0.5 - 12 * p
        r = rmax * F.ease_out(min(1.0, tt * 3.2), 2) * (1 - F.ease_in(tt, 1.8))
        balls.append((y, x, r))
    rc = 21 * F.ease_out(min(1.0, t * 5), 2) * (1 - F.ease_in(min(1.0, t * 1.9), 1.4))
    balls.append((cy - 4 - 10 * t, cx, rc))
    # faint ground shadow so the burst sits on snow
    sh = F.bump(t, 0.0, 0.95)
    if sh > 0:
        c.fill(F.sd_ellipse(c.X, c.Y, cx + 3, cy + 6, 20 + 26 * F.ease_out(t), 7 + 9 * F.ease_out(t)),
               hexc('#5D7298'), 0.16 * sh, feather=6)
    if t < 0.25:
        r = np.hypot(c.X - cx, (c.Y - cy) * 1.4)
        c.paint(np.exp(-(r / (12 + 46 * t)) ** 2), WHITE, 0.95 * (1 - t / 0.25))
    for (y, x, r) in sorted(balls):
        ball(c, x, y, r)
    # snow bits thrown further out (with a little gravity)
    for k in range(7):
        a = 2 * math.pi * (k + 0.5) / 7 + 0.2
        p = F.ease_out(t, 2)
        x = cx + math.cos(a) * 56 * p
        y = cy + math.sin(a) * 28 * p - 30 * p + 34 * t * t
        ball(c, x, y, 3.2 * (1 - F.ease_in(t, 1.5)) * min(1.0, t * 6), rim='#8FA6C8')
    return c.image()


def water_part(c, d, y_top, h, a=1.0):
    """White-to-ice water body with a thin sea-blue rim and bevel light."""
    c.fill(d - 1.1, hexc('#2F86C9'), 0.55 * a)
    nn = F.bevel_normals(d, 3.5, c.px)
    base = F.mix(hexc('#FFFFFF'), hexc('#BCDDF3'), np.clip((c.Y - y_top) / max(h, 1), 0, 1))
    c.paint(c.cov(d), F.shade(base, F.lambert(nn), 0.5, 0.6, hexc('#5E9FD6')), a)


def sh_splash(i, n, S=128):
    """Water splash: central column + ring of tapered spikes + flying droplets + iso ripples.
    Anchor on the water surface."""
    t = i / (n - 1)
    c = F.Canvas(S, S)
    cx, wy = S / 2, S * 0.74
    # ripples on the surface (2:1 ellipses)
    for k, t0 in enumerate((-0.08, 0.2, 0.42)):
        tt = F.clamp01((t - t0) / 0.62)
        if 0 < tt < 1:
            rx = 9 + 48 * F.ease_out(tt, 2)
            d = np.abs(F.sd_ellipse(c.X, c.Y, cx, wy, rx, rx * 0.42)) - (3.0 * (1 - tt) + 0.8)
            c.fill(d - 1.0, hexc('#2F86C9'), 0.3 * (1 - tt))
            c.fill(d, hexc('#E8F5FF'), 0.95 * (1 - tt) ** 1.2)
    # foam disc at the impact
    fa = 1 - F.ease_in(t, 1.5)
    c.fill(F.sd_ellipse(c.X, c.Y, cx, wy, 10 + 10 * t, 4 + 4 * t), hexc('#F4FBFF'), 0.9 * fa, feather=1.5)
    hgt = F.bump(t, -0.08, 0.62)
    rng = np.random.default_rng(4)
    spikes = []
    for k in range(8):
        phi = 2 * math.pi * k / 8 + 0.35
        p = F.ease_out(t, 2)
        bx = cx + math.cos(phi) * (7 + 10 * p)
        by = wy + math.sin(phi) * (3 + 4 * p)
        L = rng.uniform(18, 28) * hgt
        dx, dy = math.cos(phi) * 1.05, -1.0
        nrm = math.hypot(dx, dy)
        tx, ty = bx + dx / nrm * L, by + dy / nrm * L * (0.9 + 0.2 * abs(math.cos(phi)))
        spikes.append((math.sin(phi), bx, by, tx, ty, L))

    def spike(sp):
        _, bx, by, tx, ty, L = sp
        R = c.region(min(bx, tx) - 8, ty - 8, max(bx, tx) + 8, by + 6)
        if R.empty or L < 2:
            return
        tt = np.clip(np.hypot(R.X - bx, R.Y - by) / max(L, 1), 0, 1)
        d = F.sd_segment(R.X, R.Y, bx, by, tx, ty, 0) - (2.9 - 2.0 * tt)
        d = np.minimum(d, F.sd_circle(R.X, R.Y, tx, ty, 1.9))
        d = np.maximum(d, R.Y - wy - 4)
        water_part(R, d, ty, L)
    for sp in sorted(spikes):
        if sp[0] < 0:
            spike(sp)
    # central column with a blob on top (pinches off at the end)
    H = 48 * F.bump(t, -0.05, 0.8) ** 0.8
    if H > 2:
        R = c.region(cx - 14, wy - H - 10, cx + 14, wy + 6)
        tt = np.clip((wy - R.Y) / H, 0, 1)
        d = np.abs(R.X - cx) - (5.0 - 2.6 * tt)
        d = np.maximum(d, R.Y - wy)
        d = np.maximum(d, (wy - H) - R.Y)
        d = F.smin(d, F.sd_circle(R.X, R.Y, cx, wy - H, 4.2), 2.0)
        water_part(R, d, wy - H, H)
    for sp in sorted(spikes):
        if sp[0] >= 0:
            spike(sp)
    # droplets flung from the crown tips: round head leading, tail trailing
    for k in range(12):
        phi = 2 * math.pi * k / 12 + rng.uniform(-0.2, 0.2)
        vx = math.cos(phi) * rng.uniform(45, 85)
        vy = rng.uniform(-150, -95)
        r = rng.uniform(1.8, 3.4)
        t0 = rng.uniform(0.12, 0.32)
        tt = (t - t0) * 0.8
        if tt <= 0:
            continue
        g = 430.0
        x = cx + math.cos(phi) * 16 + vx * tt
        y = wy - 18 + math.sin(phi) * 4 + vy * tt + 0.5 * g * tt * tt
        if y > wy + 1 or x < 2 or x > S - 2 or y < 2:
            continue
        vyy = vy + g * tt
        ang = math.atan2(vyy, vx)
        Rg = c.region(x - 12, y - 12, x + 12, y + 12)
        Xr, Yr = F.rot(Rg.X, Rg.Y, x, y, -(ang - math.pi / 2))
        sp_ = min(1.0, math.hypot(vx, vyy) / 170)
        d = F.sd_teardrop(Xr, Yr, x, y, r, r * (1.4 + 1.6 * sp_), tip=0.3)
        Rg.fill(d - 0.9, hexc('#2F86C9'), 0.6)
        Rg.fill(d, hexc('#F2FAFF'))
        Rg.fill(F.sd_circle(Rg.X, Rg.Y, x - r * 0.3, y - r * 0.3, r * 0.3), WHITE)
    return c.image()


def sh_hit(i, n, S=128):
    """Cartoon impact star: pops, wobbles, shrinks; speed lines."""
    t = i / (n - 1)
    c = F.Canvas(S, S)
    cx = cy = S / 2
    seq = [0.5, 1.0, 1.1, 1.0, 0.86, 0.64, 0.38, 0.12]
    sc = seq[min(i, 7)] if n == 8 else F.ease_out(min(1, t * 4)) * (1 - F.ease_in(t, 2.2)) * 1.1
    rng = np.random.default_rng(3)
    pts = []
    N = 9
    rot0 = 0.12 * t
    for k in range(2 * N):
        a = -math.pi / 2 + rot0 + k * math.pi / N
        rr = (rng.uniform(34, 44) if k % 2 == 0 else rng.uniform(16, 19)) * sc
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    if sc > 0.05:
        d = F.sd_polygon(c.X, c.Y, pts) - 2.0 * sc
        c.fill(d - 2.6, hexc('#C8501A'))
        r = np.hypot(c.X - cx, c.Y - cy) / (40 * sc)
        col = F.ramp([(0, hexc('#FFFFFF')), (0.35, hexc('#FFF6C4')), (0.7, hexc('#FFD45A')), (1.0, hexc('#FF9A2A'))], r)
        c.paint(c.cov(d), col)
        inner = F.sd_polygon(c.X, c.Y, [(cx + (x - cx) * 0.45, cy + (y - cy) * 0.45) for x, y in pts]) - 1.5
        c.fill(inner, WHITE, 0.9, feather=1.5)
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        r0 = 28 + 22 * F.ease_out(t, 2)
        ln = 16 * (1 - t) ** 1.2
        if ln < 1:
            continue
        x0, y0 = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        x1, y1 = cx + (r0 + ln) * math.cos(a), cy + (r0 + ln) * math.sin(a)
        tt = np.clip(np.hypot(c.X - x1, c.Y - y1) / ln, 0, 1)
        seg = F.sd_segment(c.X, c.Y, x0, y0, x1, y1, 0) - (0.6 + 2.6 * tt)
        c.fill(seg - 1.4, hexc('#C8501A'), 0.9)
        c.fill(seg, hexc('#FFF3C0'))
    return c.image()


def gold_ellipse_ring(c, cx, y, rx, ry, th, a, glow=True):
    R = c.region(cx - rx - 12, y - ry - 12, cx + rx + 12, y + ry + 12)
    if R.empty or a <= 0.01:
        return
    e = F.sd_ellipse(R.X, R.Y, cx, y, rx, ry)
    if glow:
        R.paint(np.exp(-(e / 5.0) ** 2), hexc('#FFD45A'), 0.45 * a)
    ring = np.abs(e) - th
    R.fill(ring - 1.1, hexc('#E09A22'), 0.85 * a)
    front = np.clip((R.Y - y) / max(ry, 1) + 0.5, 0, 1)
    R.paint(R.cov(ring), F.mix(hexc('#FFE27A'), hexc('#FFFBEA'), front), a)


def sh_levelup(i, n, S=192):
    """Level up: ground burst ring, golden rings rising from the feet, light column,
    a double chevron and sparkles floating up.  Anchor at the feet."""
    t = i / (n - 1)
    c = F.Canvas(S, S)
    cx, gy = S / 2, S * 0.80
    fade = 1 - F.ease_in(F.clamp01((t - 0.72) / 0.28), 1.5)
    # light column
    colA = (min(1.0, t * 5) * (1 - F.ease_in(t, 1.6))) * 0.5
    if colA > 0.01:
        R = c.region(cx - 50, 0, cx + 50, gy + 20)
        xx = np.abs(R.X - cx) / 30
        yy = np.clip((gy - R.Y) / 165, 0, 1)
        base_ = np.clip((gy + 10 - R.Y) / 14, 0, 1)
        R.paint(np.exp(-xx ** 2 * 1.6) * (1 - yy) ** 1.2 * base_, hexc('#FFD45A'), colA)
        R.paint(np.exp(-xx ** 2 * 7) * (1 - yy) ** 1.8 * base_, WHITE, colA * 1.3)
    # ground burst ring + glow
    tb = F.clamp01(t / 0.5)
    if tb < 1:
        rx = 16 + 62 * F.ease_out(tb, 2.4)
        gold_ellipse_ring(c, cx, gy, rx, rx * 0.45, 3.2 * (1 - tb) + 0.8, (1 - tb) ** 0.8, glow=False)
    r = np.hypot(c.X - cx, (c.Y - gy) * 2.2)
    c.paint(np.exp(-(r / 42) ** 2), hexc('#FFD45A'), 0.6 * F.bump(t, -0.1, 0.85))
    # rising rings
    for k, t0 in enumerate((0.0, 0.17, 0.34)):
        tt = F.clamp01((t - t0) / 0.56)
        if t < t0 or tt >= 1:
            continue
        y = gy - 96 * F.ease_out(tt, 1.25)
        rx = 40 - 14 * tt
        a = (0.6 + 0.4 * min(1.0, tt * 5)) * (1 - F.ease_in(tt, 1.8))
        gold_ellipse_ring(c, cx, y, rx, rx * 0.42, 2.6, a)
    # double chevron rising above the rings
    tt = F.clamp01((t - 0.06) / 0.8)
    if 0 < tt < 1:
        y = gy - 70 - 66 * F.ease_out(tt, 1.6)
        a = min(1.0, tt * 10) * (1 - F.ease_in(tt, 3.0))
        sc_ = 0.35 + 0.65 * F.ease_out(min(1.0, tt * 3.5), 3)
        w = 17 * sc_
        R = c.region(cx - 28, y - 26, cx + 28, y + 26)
        ch = np.minimum(F.sd_polyline(R.X, R.Y, [(cx - w, y + 2), (cx, y - 12 * sc_), (cx + w, y + 2)], 4.6 * sc_),
                        F.sd_polyline(R.X, R.Y, [(cx - w, y + 16 * sc_), (cx, y + 2), (cx + w, y + 16 * sc_)], 4.6 * sc_))
        R.paint(np.exp(-(np.maximum(ch, 0) / 5.0) ** 2), hexc('#FFD45A'), 0.5 * a)
        toy(R, ch, '#FFFBE0', '#FFB52E', '#B8650E', ow=2.0, bevel=3.5, gloss=0.2, shadow=0, alpha=a)
    # sparkles rising
    rng = np.random.default_rng(21)
    for k in range(12):
        x0 = cx + rng.uniform(-50, 50)
        t0 = rng.uniform(0.0, 0.5)
        sp = rng.uniform(80, 140)
        s = rng.uniform(5, 9)
        tt = F.clamp01((t - t0) / 0.5)
        if not 0 < tt < 1:
            continue
        y = gy - 6 - sp * F.ease_out(tt, 1.5)
        x = x0 + 5 * math.sin(tt * 6 + k)
        glint(c, x, y, s * F.bump(tt, 0, 1) ** 0.6, glow='#FFD45A', edge='#C87A12', a=1.0, glow_a=0.4,
              tip='#FFD45A', halo=0.7)
    if fade < 1:
        c.rgb *= fade
        c.a *= fade
    return c.image()


def sh_unlock(i, n, S=192):
    """Unlock burst: flash, expanding golden ring, rotating rays outside it, stars thrown out."""
    t = i / (n - 1)
    c = F.Canvas(S, S)
    cx = cy = S / 2
    r = np.hypot(c.X - cx, c.Y - cy)
    ang = np.arctan2(c.Y - cy, c.X - cx)
    rr = 14 + 50 * F.ease_out(t, 2.6)
    # rays (alternating long / short tapered wedges) from the ring outward
    ra = (1 - F.ease_in(t, 1.2)) * min(1.0, 0.3 + t * 5)
    if ra > 0.01:
        L = c.layer()
        r_in = rr + 2
        for k in range(12):
            a = k * math.pi / 6 + 0.3 * t
            ln = r_in + (14 + 18 * F.ease_out(t, 2)) * (1.0 if k % 2 == 0 else 0.55)
            ln = min(ln, S / 2 - 3)
            da = np.abs(np.angle(np.exp(1j * (ang - a))))
            u = np.clip((r - r_in) / max(ln - r_in, 1), 0, 1)
            wid = 0.11 * (1 - u) ** 0.9 + 0.006
            d = np.maximum((da - wid) * r, r - ln)
            d = np.maximum(d, r_in - 6 - r)
            L.paint(L.cov(d, 0.8), F.mix(hexc('#FFC23A'), hexc('#FFF3B8'), u), 1.0)
        c.over(L, ra * 0.95)
    # flash
    if t < 0.35:
        c.paint(np.exp(-(r / (20 + 60 * t)) ** 2), hexc('#FFFBEA'), 1.0 - t / 0.35)
    # ring
    th = 8 * (1 - t) + 1.5
    ringa = 1 - F.ease_in(F.clamp01((t - 0.3) / 0.7), 1.3)
    if ringa > 0.01:
        d = np.abs(r - rr) - th
        c.paint(np.exp(-((r - rr) / (th + 6)) ** 2), hexc('#FFD45A'), 0.35 * ringa)
        c.fill(d - 1.5, hexc('#D9861A'), ringa * 0.85)
        col = F.mix(hexc('#FFF8D8'), hexc('#FFC83D'), np.clip((r - rr + th) / (2 * th), 0, 1))
        c.paint(c.cov(d), col, ringa)
    # stars thrown out in all directions, slowing down, a little gravity
    rng = np.random.default_rng(8)
    for k in range(10):
        a = 2 * math.pi * k / 10 + rng.uniform(-0.15, 0.15) - math.pi / 2
        dist = rng.uniform(70, 82)
        p = F.ease_out(t, 4)
        x = cx + math.cos(a) * dist * p
        y = cy + math.sin(a) * dist * p + 26 * t * t
        s = rng.uniform(6.5, 9.0) * min(1.0, t * 8) * (1 - F.ease_in(t, 2.5))
        cols = [('#FFF3B0', '#FFC83D', '#B8650E'), ('#FFFFFF', '#CFE2FA', '#5D7DAA'), ('#FFD1DC', '#FF7A9C', '#9E2350')][k % 3]
        star5(c, x, y, s, t * 5 + k, *cols)
    return c.image()


def sh_fire(i, n, S=128):
    """Seamless flame loop (all motion periodic over n frames).  Anchor = base of the fire."""
    ph = 2 * math.pi * i / n
    c = F.Canvas(S, S)
    cx, by = S / 2, S * 0.88
    # warm halo
    r = np.hypot(c.X - cx, (c.Y - by + 30) * 0.9)
    c.paint(np.exp(-(r / 40) ** 2), hexc('#FFB04A'), 0.28 + 0.05 * math.sin(ph * 2))
    tongues = [  # dx, height, width, phase, speed(int)
        (-15, 50, 13, 0.0, 1), (16, 46, 12, 2.1, 1), (0, 74, 19, 1.0, 1), (-6, 40, 11, 3.9, 2), (8, 36, 10, 5.0, 2)]
    for j, (dx, h, w, p0, m) in enumerate(tongues):
        hh = h * (1 + 0.13 * math.sin(ph * m + p0) + 0.06 * math.sin(ph * 2 * m + p0 * 2))
        sway = 0.55 * math.sin(ph * m + p0 + 0.8)
        flame_layers(c, cx + dx, by, hh, w, sway=sway, wob=1.0, phase=ph * m + p0)
    # embers
    for k in range(5):
        u = (i / n + k / 5.0) % 1.0
        x = cx + (k - 2) * 7 + 6 * math.sin(2 * math.pi * u * 1 + k)
        y = by - 30 - 80 * u
        a = math.sin(math.pi * u) * 0.95
        R = c.region(x - 6, y - 6, x + 6, y + 6)
        R.paint(np.exp(-(np.hypot(R.X - x, R.Y - y) / 3.2) ** 2), hexc('#FFB03A'), a * 0.7)
        R.fill(F.sd_circle(R.X, R.Y, x, y, 1.6 - 0.6 * u), hexc('#FFF0B0'), a)
    return c.image()


def sh_smoke_puff(i, n, S=128):
    """One chimney puff: appears at the bottom, swells while drifting up/right, fades."""
    t = (i + 0.6) / (n - 1 + 0.6)
    c = F.Canvas(S, S, ss=3)
    p = F.ease_out(t, 1.8)
    x = S / 2 + 12 * p
    y = S * 0.86 - 66 * p
    R = 8 + 24 * F.ease_out(t, 1.4)
    blobs = [(x, y, R * 0.78), (x - R * 0.58, y + R * 0.26, R * 0.56), (x + R * 0.58, y + R * 0.22, R * 0.6),
             (x - R * 0.18, y - R * 0.5, R * 0.56), (x + R * 0.34, y - R * 0.34, R * 0.48)]
    d = puff_sdf(c, blobs, R * 0.14)
    a = min(1.0, 0.35 + t * 5) * (1 - F.ease_in(F.clamp01((t - 0.35) / 0.65), 1.3)) * 0.94
    L = c.layer()
    cloud(L, d, '#FFFFFF', '#E7EBF1', '#8D97A8', bevel=R * 0.45, rim='#A9B2C2', rim_a=0.8)
    c.over(L, a, mask=soft_mask(c, d, 0.6 + R * 0.12 * t))
    return c.image()


def sh_coin_spin(i, n, S=96):
    c = F.Canvas(S, S)
    theta = math.pi * i / n
    # soft contact shadow under the coin (changes width with the turn)
    w = S * 0.40 * (0.35 + 0.65 * abs(math.cos(theta))) + 4
    c.fill(F.sd_ellipse(c.X, c.Y, S / 2 + 3, S * 0.92, w, S * 0.045), hexc('#1B2840'), 0.18, feather=3)
    coin(c, S / 2, S * 0.47, S * 0.40, theta)
    return c.image()


def sh_sparkle(i, n, S=128):
    """Twinkle loop for 'ready' highlights (periodic over n frames)."""
    c = F.Canvas(S, S)
    stars = [(40, 44, 20, 0.0), (90, 36, 14, 0.33), (84, 88, 18, 0.62), (36, 92, 11, 0.8), (64, 64, 9, 0.15)]
    for (x, y, s, p0) in stars:
        u = (i / n + p0) % 1.0
        k = max(0.0, math.sin(2 * math.pi * u)) ** 1.4
        glint(c, x, y, s * (0.25 + 0.75 * k), glow='#FFC83D', edge='#B8650E', a=min(1.0, 0.15 + k * 1.2),
              rot_=0.25 * math.sin(2 * math.pi * u), glow_a=0.55, thin=0.55, tip='#FFC83D', halo=0.8)
    # tiny orbiting dots
    for k in range(6):
        a = 2 * math.pi * (i / n + k / 6)
        x = 64 + 44 * math.cos(a)
        y = 64 + 30 * math.sin(a)
        R = c.region(x - 4, y - 4, x + 4, y + 4)
        al = 0.5 + 0.5 * math.sin(a * 2 + k)
        R.fill(F.sd_circle(R.X, R.Y, x, y, 1.9), hexc('#C87A12'), 0.6 * al)
        R.fill(F.sd_circle(R.X, R.Y, x, y, 1.3), hexc('#FFF6C8'), al)
    return c.image()


# key: (fn, frameW, frameH, frames, fps, repeat, anchor, notes)
SHEETS = {
    'fx_poof': (sh_poof, 128, 128, 12, 24, 0, [0.5, 0.6], 'Snowy cloud burst for unlock / spawn / despawn. Anchor = ground point.'),
    'fx_splash': (sh_splash, 128, 128, 12, 24, 0, [0.5, 0.74], 'Water splash; anchor = water surface point (ripples are iso 2:1).'),
    'fx_hit': (sh_hit, 128, 128, 8, 30, 0, [0.5, 0.5], 'Cartoon impact star; anchor = impact point.'),
    'fx_levelup': (sh_levelup, 192, 192, 16, 20, 0, [0.5, 0.8], 'Rising golden rings + column + sparkles; anchor = feet.'),
    'fx_unlock': (sh_unlock, 192, 192, 14, 24, 0, [0.5, 0.5], 'Burst ring + rotating rays + thrown stars; anchor = centre.'),
    'fx_fire': (sh_fire, 128, 128, 12, 14, -1, [0.5, 0.88], 'Seamless fire loop; anchor = base of the flames.'),
    'fx_smoke_puff': (sh_smoke_puff, 128, 128, 12, 14, 0, [0.5, 0.86], 'One chimney puff rising ~70px; anchor = chimney top. Spawn every ~0.6 s.'),
    'fx_coin_spin': (sh_coin_spin, 96, 96, 10, 14, -1, [0.5, 0.5], 'Coin turning about its vertical axis (loop).'),
    'fx_sparkle': (sh_sparkle, 128, 128, 12, 12, -1, [0.5, 0.5], 'Twinkle loop for "ready" highlights.'),
}


# =========================================================================== previews
def tinted(im, rgb):
    a = np.asarray(im.convert('RGBA')).astype(np.float32)
    a[..., :3] *= np.array(rgb, np.float32)[None, None, :] / 255.0
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


TINTS = {  # how the game tints them (src/systems/Effects.js presets)
    'fx_chip_wood': (0xC9, 0x8F, 0x55), 'fx_leaf': (0x2E, 0x6B, 0x4F), 'fx_chip_rock': (0x8E, 0x96, 0xA3),
    'fx_spark': (0xFF, 0xD4, 0x5A), 'fx_wheat_bit': (0xE8, 0xC2, 0x5A), 'fx_droplet': (0x9C, 0xC7, 0xE6),
    'fx_star': (0xFF, 0xC8, 0x3D), 'fx_dust': (0xE6, 0xEE, 0xF7), 'fx_smoke': (0xD9, 0xDE, 0xE6),
}


def preview_sheet(parts, sheets):
    W = 1500
    rows = []
    # particle rows on 4 backgrounds: raw (dark), tinted on snow, tinted on plaza, tinted on sea
    cell = 100
    keys = list(parts)
    bgs = [('#2B2F3A', False), ('#F4F7FB', True), ('#D9A08A', True), ('#1F5FA8', True)]
    h_parts = len(bgs) * cell
    sh_h = sum(max(s[2], 96) + 10 for s in SHEETS.values())
    H = 30 + h_parts + 20 + sh_h + 20
    im = Image.new('RGBA', (W, H), (200, 208, 220, 255))
    dr = ImageDraw.Draw(im)
    dr.text((8, 8), 'fx_particles: raw on dark, then tinted as the game does on snow / plaza / sea.   Below: animated strips (frames left->right) on snow/plaza/sea', fill=(20, 24, 32, 255))
    y = 30
    for bg, tint in bgs:
        im.paste(Image.new('RGBA', (W, cell), bg), (0, y))
        for j, k in enumerate(keys):
            p = parts[k]
            if tint and k in TINTS:
                p = tinted(p, TINTS[k])
            s = min(1.0, 90 / max(p.size))
            if s < 1:
                p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
            x = 8 + j * cell
            im.alpha_composite(p, (x + (cell - p.width) // 2, y + (cell - p.height) // 2))
            if not tint:
                dr.text((x + 2, y + cell - 12), k[3:], fill=(220, 225, 235, 255))
        y += cell
    y += 20
    for k, frames in sheets.items():
        fw, fh = frames[0].size
        bgcols = ['#F4F7FB', '#D9A08A', '#1F5FA8']
        for j, f in enumerate(frames):
            x = 8 + j * (fw // 2 + 4) if fw > 128 else 8 + j * (fw + 4)
            ff = f.resize((fw // 2, fh // 2), Image.LANCZOS) if fw > 128 else f
            if x + ff.width > W:
                break
            bg = Image.new('RGBA', ff.size, bgcols[j % 3])
            bg.alpha_composite(ff)
            im.alpha_composite(bg, (x, y))
        dr.text((W - 130, y + 4), k, fill=(20, 24, 32, 255))
        y += max(fh if fw <= 128 else fh // 2, 96) + 10
    return im.crop((0, 0, W, y + 10))


# =========================================================================== main
def build(only=None, gifs=True):
    os.makedirs(OUT, exist_ok=True)
    parts = {}
    for k, (fn, _, _) in PARTICLES.items():
        if only and k not in only:
            continue
        parts[k] = fn()
        print('  particle', k, parts[k].size, flush=True)
    sheets = {}
    for k, (fn, fw, fh, nfr, fps, rep, anc, _) in SHEETS.items():
        if only and k not in only:
            continue
        frames = [fn(i, nfr, fw) if fw == fh else fn(i, nfr) for i in range(nfr)]
        for f in frames:
            assert f.size == (fw, fh), (k, f.size)
        sheets[k] = frames
        print('  sheet', k, nfr, 'x', (fw, fh), flush=True)

    if only:
        os.makedirs(CACHE, exist_ok=True)
        allp = list(parts.values()) + [f for fr in sheets.values() for f in fr]
        if allp:
            cw = max(i.width for i in allp) + 8
            chh = max(i.height for i in allp) + 8
            cols = 8
            rows = (len(allp) + cols - 1) // cols
            sheet = Image.new('RGBA', (cols * cw, rows * chh * 2), (244, 247, 251, 255))
            for j, p in enumerate(allp):
                x, y = (j % cols) * cw, (j // cols) * chh * 2
                sheet.alpha_composite(p, (x + 4, y + 4))
                bg = Image.new('RGBA', (cw, chh), (31, 95, 168, 255))
                bg.alpha_composite(p, (4, 4))
                sheet.alpha_composite(bg, (x, y + chh))
            sheet.save(os.path.join(CACHE, 'fx_only.png'))
            print('  preview ->', os.path.join(CACHE, 'fx_only.png'))
        for k, frames in sheets.items():
            d = SHEETS[k]
            F.save_gif(frames, os.path.join(CACHE, k + '.gif'), d[4], hold=0 if d[5] == -1 else 6, anchor=d[6])
        return

    # --- particle atlas (untrimmed so particle size maths in the game stays predictable)
    sheet, atlas = pack_utils.pack_atlas(list(parts.items()), max_width=512, trim=False, padding=2)
    F.save_png(sheet, os.path.join(OUT, 'fx_particles.png'))
    atlas['meta']['image'] = 'fx_particles.png'
    with open(os.path.join(OUT, 'fx_particles.json'), 'w', encoding='utf-8') as f:
        json.dump(atlas, f, separators=(',', ':'))
    manifest = {
        'version': 1,
        'generator': 'tools/fx/gen_fx.py',
        'conventions': {
            'particles': 'White/greyscale (tint in game) except fx_heart, fx_flame, fx_coin. Frames are untrimmed squares.',
            'blend': 'All sheets are NORMAL-blend artwork (saturated cores + warm/cool rims) so they read on white snow, '
                     'where ADD is invisible. fx_fire / fx_sparkle / fx_glow also look fine with ADD over dark ground.',
            'sheets': 'Frames left->right, then wrapped into rows so no sheet is wider than 2048 px '
                      '(GPUs with a 2048 texture limit). Phaser anim key = sheet key.',
        },
        'atlases': [{'key': 'fx_particles', 'png': 'fx/fx_particles.png', 'json': 'fx/fx_particles.json'}],
        'spritesheets': [],
        'sprites': {},
    }
    for k, im in parts.items():
        fn, tintable, note = PARTICLES[k]
        manifest['sprites'][k] = {'atlas': 'fx_particles', 'frame': k, 'anchor': [0.5, 0.5], 'kind': 'fx',
                                  'tintable': tintable, 'frameSize': list(im.size), 'notes': note}
    for k, frames in sheets.items():
        fn, fw, fh, nfr, fps, rep, anc, note = SHEETS[k]
        st = grid_strip(frames, 2048)
        F.save_png(st, os.path.join(OUT, k + '.png'), quant=256, dither=0.6)
        manifest['spritesheets'].append({'key': k, 'png': 'fx/%s.png' % k, 'frameWidth': fw, 'frameHeight': fh,
                                         'frameCount': nfr, 'fps': fps, 'repeat': rep, 'anchor': anc,
                                         'blend': 'NORMAL', 'notes': note})
        if gifs:
            F.save_gif(frames, os.path.join(PREV, k + '.gif'), fps, hold=0 if rep == -1 else 8, anchor=anc)
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    os.makedirs(PREV, exist_ok=True)
    preview_sheet(parts, sheets).convert('RGB').save(os.path.join(PREV, 'fx_sheet.png'), optimize=True)
    print('FX done ->', OUT)


def grid_strip(frames, max_w=2048):
    """frames left->right, wrapped into balanced rows so the sheet is at most max_w wide"""
    fw, fh = frames[0].size
    n = len(frames)
    cols = max(1, min(n, max_w // fw))
    rows = (n + cols - 1) // cols
    cols = (n + rows - 1) // rows
    out = Image.new('RGBA', (cols * fw, rows * fh), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        out.alpha_composite(fr, ((i % cols) * fw, (i // cols) * fh))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', default='', help='comma separated keys -> scratch preview in tools/fx/_cache only')
    ap.add_argument('--no-gif', action='store_true')
    a = ap.parse_args()
    only = set(k for k in a.only.split(',') if k) or None
    build(only, gifs=not a.no_gif)
