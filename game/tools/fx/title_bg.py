"""
title_bg.py - painterly 720x1280 snowy-dawn title backdrop for Frost Village (ui_title_bg).
Imported by gen_ui.py; can also be run alone for a quick look:
    python3 frost-village/tools/fx/title_bg.py          # -> tools/fx/_cache/ui_title_bg.png
Composition (top -> bottom): dawn sky with soft clouds and a few stars (calm band y 160-470
for the game's title text), low sun glowing between two mountain ranges, misty valley with a
blue pine forest, a little log-cabin village with warm windows and chimney smoke, framing
snowy pines left/right, a soft snow bank at the bottom (tap-to-start prompt ~ y 1060-1120),
falling snow.  A light Kuwahara filter + grain gives the painted finish.  Deterministic.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fxlib as F                                     # noqa: E402
from fxlib import hexc                                # noqa: E402

WHITE = hexc('#FFFFFF')
SUN = (452.0, 606.0)


def noise1d(n, seed, octaves=5, base=3.0, rough=0.55):
    """Smooth 1D fractal noise over n samples (not periodic), roughly in [-1, 1]."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, n, dtype=np.float32)
    out = np.zeros(n, np.float32)
    amp, f, tot = 1.0, base, 0.0
    for _ in range(octaves):
        for _k in range(2):
            out += amp * np.sin(2 * math.pi * (x * f * rng.uniform(0.8, 1.25)) + rng.uniform(0, 6.3)) * 0.7
        tot += amp * 1.4
        amp *= rough
        f *= 2.1
    return out / tot * 1.6


def kuwahara(img, r=2):
    """Kuwahara filter (painterly flattening that keeps edges).  img float (H,W,3) 0..1."""
    H, W, _ = img.shape
    lum = img @ np.array([0.3, 0.59, 0.11], np.float32)
    pad = r + 1
    P = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
    L = np.pad(lum, ((pad, pad), (pad, pad)), mode='edge')

    def integ(a):
        s = a.cumsum(0).cumsum(1)
        return np.pad(s, [(1, 0), (1, 0)] + [(0, 0)] * (a.ndim - 2))

    I_c, I_l, I_l2 = integ(P), integ(L), integ(L * L)
    n = float((r + 1) ** 2)
    best_v = np.full((H, W), np.inf, np.float32)
    out = np.zeros_like(img)
    ys = np.arange(H) + pad
    xs = np.arange(W) + pad
    for dy0, dx0 in ((-r, -r), (-r, 0), (0, -r), (0, 0)):
        y0 = ys + dy0
        x0 = xs + dx0
        y1 = y0 + r + 1
        x1 = x0 + r + 1

        def box(I):
            return I[y1][:, x1] - I[y0][:, x1] - I[y1][:, x0] + I[y0][:, x0]

        m = box(I_l) / n
        v = box(I_l2) / n - m * m
        mc = box(I_c) / n
        sel = v < best_v
        best_v = np.where(sel, v, best_v)
        out = np.where(sel[..., None], mc, out)
    return out


def pine(R, x, by, h, w, tiers, body, dark, snow, snow_sh, rim=None, shadow_a=0.3, k_round=2.0, seed=0):
    """Layered pine with drooping snow caps; lit from the right (dawn sun), cool shade left."""
    X, Y = R.X, R.Y
    rng = np.random.default_rng(seed)
    shapes = []
    for k in range(tiers):
        ty = by - h + k * h * (0.80 / tiers)
        yb = ty + h * (0.30 + 0.07 * k / max(1, tiers - 1))
        tw = w * (0.38 + 0.62 * (k + 1) / tiers)
        tri = F.sd_polygon(X, Y, [(x, ty), (x + tw, yb - tw * 0.12), (x - tw, yb - tw * 0.12)]) - k_round
        for j in (-0.66, -0.22, 0.22, 0.66):
            tri = F.smin(tri, F.sd_circle(X, Y, x + j * tw, yb - tw * 0.20 + rng.uniform(-1, 1) * tw * 0.03, tw * 0.25), tw * 0.07)
        tri = np.maximum(tri, F.sd_polygon(X, Y, [(x, ty - 4), (x + tw * 1.2, yb + 4), (x - tw * 1.2, yb + 4)]))
        shapes.append((ty, yb, tw, tri))
    trunk = F.sd_box(X, Y, x, by + h * 0.02, max(1.2, w * 0.08), h * 0.07, 1)
    R.fill(trunk, hexc('#4A3440'))
    for k in reversed(range(len(shapes))):
        ty, yb, tw, tri = shapes[k]
        cv = R.cov(tri)
        if shadow_a:
            R.shadow(cv, dx=-max(0.5, h * 0.004), dy=max(1.0, h * 0.014), sigma=max(0.8, h * 0.012), color='#0E1A30', opacity=shadow_a)
        t = np.clip((Y - ty) / (yb - ty), 0, 1)
        side = np.clip((X - x) / tw, -1, 1)
        col = F.mix(hexc(dark), hexc(body), np.clip(0.35 + 0.5 * side - 0.35 * t, 0, 1))
        R.paint(cv, col)
        if rim is not None:                        # warm rim on the sun side
            edge = np.clip(1 - (-tri) / max(1.5, tw * 0.05), 0, 1) * np.clip(side, 0, 1)
            R.paint(cv * edge, hexc(rim), 0.6)
        # snow lies on the visible 'shoulders' just below the tier above (or on the tip)
        if k == 0:
            top_y, depth = ty, (yb - ty) * 0.42
        else:
            pty, pyb, ptw, _ = shapes[k - 1]
            top_y, depth = pyb - ptw * 0.18, (yb - pyb) * 0.55 + tw * 0.08
        u_ = (X - x) / tw * 2.2 + 0.37 * k
        zig = 2 * np.abs(u_ - np.floor(u_ + 0.5))                 # triangle wave 0..1 (zigzag edge)
        wav = depth * (0.55 * zig - 0.2 + 0.06 * np.sin((X - x) / tw * 13.0 + k))
        cap_y = top_y + depth * (1.05 - 0.25 * np.clip(side, 0, 1)) + wav
        cap = np.maximum(tri + 0.8, Y - cap_y)
        lit = np.clip(0.5 + 0.5 * side, 0, 1)
        scol = F.mix(hexc(snow_sh), hexc(snow), lit ** 0.8)
        R.paint(R.cov(cap), scol)
        under = np.maximum(tri + 0.8, np.abs(Y - cap_y - 1.8) - 1.8)
        R.paint(R.cov(under, 1.0), hexc(dark), 0.35)


def mountain_range(c, peaks, base_y, seed, lit, shade, snow_lit, snow_sh, haze, rim, snow_frac=0.42,
                   haze_k=0.8, detail=9.0):
    W = c.w
    ss = c.ss
    xs = (np.arange(W * ss, dtype=np.float32) + 0.5) / ss
    tops = np.stack([py + np.abs(xs - px) * sl for px, py, sl in peaks])
    idx = np.argmin(tops, 0)
    crest = tops[idx, np.arange(xs.size)]
    pk = np.array(peaks, np.float32)
    hgt = np.clip((base_y - crest) / (base_y - pk[:, 1].min()), 0, 1)
    crest = crest + noise1d(xs.size, seed, 6, 6.0, 0.6) * detail * (0.3 + hgt)
    top = float(crest.min()) - 2
    R = c.region(0, top, W, base_y + 60)
    inside = R.Y - crest[None, :]
    cov = np.clip(inside * ss + 0.5, 0, 1)
    ppx = pk[idx, 0][None, :]
    ppy = pk[idx, 1][None, :]
    depth = np.clip((R.Y - ppy) / np.maximum(base_y - ppy, 1), 0, 1)
    hh, ww = R.a.shape
    gul = F.fft_noise(hh, ww, seed + 1, scale=3 * ss, aniso=4.5, angle=math.pi / 2)
    gul2 = F.fft_noise(hh, ww, seed + 2, scale=14 * ss, aniso=2.0, angle=math.pi / 2)
    wander = F.fft_noise(hh, 1, seed + 3, scale=30 * ss)[:, :1] if hh > 4 else 0
    ridge = ppx + wander * 14 * depth + (R.Y - ppy) * 0.18
    side = np.tanh((R.X - ridge) / (2.5 + 26 * depth))          # -1 left (shade) .. +1 right (lit)
    light = 0.55 * side + 0.28 * gul + 0.2 * gul2
    col = F.mix(hexc(shade), hexc(lit), np.clip(0.5 + 0.5 * light, 0, 1))
    snow_line = snow_frac + 0.06 * gul + 0.05 * gul2 + 0.1 * side
    sn = F.smoothstep(0.0, 0.04, snow_line - depth)
    # snow also lingers in a few gullies below the snow line
    sn = np.maximum(sn, F.smoothstep(1.1, 1.7, gul) * F.smoothstep(0.0, 0.3, snow_line + 0.3 - depth) * 0.85)
    scol = F.mix(hexc(snow_sh), hexc(snow_lit), np.clip(0.45 + 0.55 * light, 0, 1))
    col = F.mix(col, scol, sn)
    col = F.mix(col, hexc(haze), np.clip(depth, 0, 1) ** 1.6 * haze_k)
    near = np.clip(1 - np.abs(R.X - SUN[0]) / 330, 0, 1) ** 1.5
    rim_a = np.clip(1 - inside / 3.0, 0, 1) * (0.35 + 0.65 * near)
    col = F.mix(col, hexc(rim), rim_a * 0.9)
    R.paint(cov, col)


def ridge_field(c, y0, amp, seed, col_top, col_bot, depth=200.0, rim=True):
    W, ss = c.w, c.ss
    n = W * ss
    line = y0 - amp * (0.5 + 0.5 * noise1d(n, seed, 4, 1.5, 0.5))
    R = c.region(0, float(line.min()) - 2, W, c.h)
    inside = R.Y - line[None, :]
    cov = np.clip(inside * ss + 0.5, 0, 1)
    R.paint(cov, F.mix(hexc(col_top), hexc(col_bot), np.clip(inside / depth, 0, 1)))
    if rim:
        R.paint(np.clip(1 - inside / 5, 0, 1) * cov, WHITE, 0.7)
    return line


def cabin(c, cx, by, s, seed, chimney=True):
    """Little log cabin (front view, slight 3/4) with a snowy roof and warm windows."""
    R = c.region(cx - 70 * s, by - 170 * s, cx + 80 * s, by + 20 * s)
    X, Y = R.X, R.Y
    R.fill(F.sd_ellipse(X, Y, cx + 8 * s, by + 4 * s, 62 * s, 9 * s), hexc('#9DAFCB'), 0.45, feather=5 * s)
    body = F.sd_box(X, Y, cx, by - 20 * s, 40 * s, 21 * s, 2 * s)
    side = F.sd_polygon(X, Y, [(cx + 40 * s, by - 41 * s), (cx + 58 * s, by - 50 * s), (cx + 58 * s, by - 9 * s), (cx + 40 * s, by + 1 * s)])
    R.fill(side, hexc('#6E4A44'))
    t = np.clip((Y - (by - 41 * s)) / (42 * s), 0, 1)
    R.paint(R.cov(body), F.mix(hexc('#A8705A'), hexc('#8A5A4A'), t))
    for k in range(6):
        ly = by - 38 * s + k * 7 * s
        R.fill(np.maximum(np.abs(Y - ly) - 0.7 * s, body), hexc('#6E4440'), 0.55)
        R.fill(np.maximum(np.abs(Y - ly - 2 * s) - 0.6 * s, body), hexc('#C68C70'), 0.35)
    if chimney:
        ch = F.sd_box(X, Y, cx + 22 * s, by - 66 * s, 6 * s, 13 * s, 1 * s)
        R.fill(ch, hexc('#7C6470'))
        R.fill(F.sd_box(X, Y, cx + 22 * s, by - 79 * s, 8 * s, 3 * s, 2 * s), hexc('#F7F7FC'))
    roof = F.sd_polygon(X, Y, [(cx - 50 * s, by - 37 * s), (cx + 2 * s, by - 74 * s), (cx + 52 * s, by - 37 * s)]) - 3 * s
    roof_side = F.sd_polygon(X, Y, [(cx + 2 * s, by - 74 * s), (cx + 20 * s, by - 83 * s), (cx + 66 * s, by - 46 * s), (cx + 52 * s, by - 37 * s)]) - 2 * s
    R.fill(roof_side, hexc('#DCE4F2'))
    R.fill(roof, hexc('#FFFFFF'))
    R.fill(np.maximum(roof, -(Y - (by - 42 * s))), hexc('#C9D6E8'), 0.9)          # roof edge shade
    for k, xo in enumerate((-46, -30, -12, 8, 26, 44)):                            # icicles / snow drips
        R.fill(F.sd_teardrop(X, -Y, cx + xo * s, -(by - 38 * s + 1.5 * s), 2.2 * s, (5 + (k % 3) * 2.5) * s), hexc('#F2F6FC'))
    door = F.sd_box(X, Y, cx + 4 * s, by - 10 * s, 7 * s, 11 * s, 2 * s)
    R.fill(door, hexc('#4E3040'))
    for wx in (cx - 22 * s, cx + 26 * s):
        w_ = F.sd_box(X, Y, wx, by - 23 * s, 7 * s, 7 * s, 1.5 * s)
        R.glow(R.cov(w_), 12 * s, '#FFB050', 0.55)
        R.fill(w_ - 1.4 * s, hexc('#6A4038'))
        R.paint(R.cov(w_), F.mix(hexc('#FFE9A8'), hexc('#FFB858'), np.clip((Y - (by - 30 * s)) / (14 * s), 0, 1)))
        R.fill(np.maximum(np.minimum(np.abs(X - wx), np.abs(Y - (by - 23 * s))) - 0.7 * s, w_), hexc('#9A5A30'), 0.7)
    R.fill(F.sd_ellipse(X, Y, cx, by - 1 * s, 48 * s, 4 * s), hexc('#F4F7FB'), 0.9, feather=1.5 * s)


def smoke(c, x, y, s, n=7, seed=0):
    for i in range(n):
        sy = y - i * 22 * s
        sx = x + i * 6 * s + 5 * s * math.sin(i * 1.3 + seed)
        r = (6 + i * 3.2) * s
        R = c.region(sx - r * 3, sy - r * 3, sx + r * 3, sy + r * 3)
        R.fill(F.sd_circle(R.X, R.Y, sx, sy, r), hexc('#F3EEF6'), max(0.0, 0.42 - i * 0.05), feather=r * 0.8)


def render_title(W=720, H=1280, kuwa=2):
    c = F.Canvas(W, H, ss=2)
    rng = np.random.default_rng(1207)
    ss = c.ss
    # ---------------------------------------------------------------- sky
    t = c.Y / H
    sky = F.ramp([(0.00, hexc('#2B3A72')), (0.13, hexc('#435595')), (0.27, hexc('#7676B4')),
                  (0.38, hexc('#B391C2')), (0.46, hexc('#E7A9B6')), (0.52, hexc('#FFC9AC')),
                  (0.56, hexc('#FFE0BC'))], t)
    nz = F.fft_noise(H * ss, W * ss, 3, scale=40 * ss, aniso=3.0, angle=0.0)
    sky = sky * (1 + 0.025 * nz[..., None])
    c.paint(np.ones_like(c.X), sky)
    del sky
    r = np.hypot(c.X - SUN[0], (c.Y - SUN[1]) * 1.25)
    c.paint(np.clip(1 - r / 640, 0, 1) ** 2.4, hexc('#FFE7C4'), 0.9)
    c.paint(np.clip(1 - r / 260, 0, 1) ** 2, hexc('#FFF1D8'), 0.8)
    c.paint(np.clip((52 - r) / 4, 0, 1), hexc('#FFF8EA'), 1.0)
    # soft god rays from the sun
    ang = np.arctan2(c.Y - SUN[1], c.X - SUN[0])
    rays = (0.5 + 0.5 * np.sin(ang * 13 + 0.7)) ** 6 * np.clip(1 - r / 700, 0, 1) * (c.Y < SUN[1])
    c.paint(rays.astype(np.float32), hexc('#FFF4DE'), 0.07)
    del r, ang, rays
    # stars (fading toward the horizon)
    for _ in range(70):
        x, y = rng.uniform(0, W), rng.uniform(0, 330)
        rr = rng.uniform(0.6, 1.4)
        a = (1 - y / 380) * rng.uniform(0.3, 0.85)
        R = c.region(x - 4, y - 4, x + 4, y + 4)
        R.fill(F.sd_circle(R.X, R.Y, x, y, rr), WHITE, a, feather=0.6)
    for _ in range(5):
        x, y = rng.uniform(40, W - 40), rng.uniform(30, 200)
        R = c.region(x - 11, y - 11, x + 11, y + 11)
        R.fill(F.sd_glint(R.X, R.Y, x, y, 8, 8, R.px), WHITE, 0.8)
    # clouds: soft puffy banks, lit from below by the low sun
    L = c.layer()
    crng = np.random.default_rng(77)
    for (cx, cy, wdt, hgt, a, seed) in [(120, 515, 230, 40, 0.8, 11), (610, 470, 250, 46, 0.75, 12),
                                       (390, 560, 170, 28, 0.6, 13), (700, 590, 150, 26, 0.55, 14),
                                       (60, 380, 160, 22, 0.35, 15), (560, 330, 190, 20, 0.28, 16)]:
        R = L.region(cx - wdt - 40, cy - hgt * 2.6, cx + wdt + 40, cy + hgt * 1.4)
        hh, ww = R.a.shape
        d = None
        for j in range(9):
            ox = crng.uniform(-0.85, 0.85) * wdt
            fall = 1 - abs(ox) / wdt
            rr = hgt * crng.uniform(0.55, 1.0) * (0.45 + 0.55 * fall)
            e = F.sd_ellipse(R.X, R.Y, cx + ox, cy - rr * 0.35, rr * 1.5, rr)
            d = e if d is None else F.smin(d, e, hgt * 0.5)
        base = F.sd_ellipse(R.X, R.Y, cx, cy + hgt * 0.1, wdt, hgt * 0.32)
        d = F.smin(d, base, hgt * 0.4)
        n1 = F.fft_noise(hh, ww, seed, scale=4 * ss)
        dens = F.smoothstep(hgt * 0.25, -hgt * 0.35, d + n1 * hgt * 0.12)
        litc = np.clip((R.Y - (cy - hgt * 1.4)) / (1.9 * hgt), 0, 1)
        col = F.ramp([(0, hexc('#A59BCD')), (0.5, hexc('#D8A8C6')), (1.0, hexc('#FFD9C2'))], litc)
        R.paint(dens, col, a)
    c.over(L)
    del L
    # ---------------------------------------------------------------- mountains
    mountain_range(c, [(30, 520, 0.95), (175, 470, 1.05), (330, 560, 0.9), (575, 485, 0.95), (720, 540, 1.1)],
                   790, 21, '#D8C3DD', '#9C8FC4', '#FFF7F4', '#D3C8E8', '#E7DCEE', '#FFE9D6', snow_frac=0.3, haze_k=0.8)
    # mist band
    R = c.region(0, 640, W, 860)
    m = np.exp(-((R.Y - 770) / 55) ** 2)
    R.paint(m, hexc('#F2E6F0'), 0.55)
    mountain_range(c, [(-40, 640, 0.75), (110, 675, 0.85), (255, 620, 0.9), (440, 700, 0.8), (600, 640, 0.8), (780, 670, 0.85)],
                   860, 22, '#B9B2DC', '#7B7BB6', '#FBF7FD', '#BDB8E0', '#D9D5EE', '#FFE2D0', snow_frac=0.28, haze_k=0.7,
                   detail=7.0)
    R = c.region(0, 760, W, 900)
    R.paint(np.exp(-((R.Y - 845) / 30) ** 2), hexc('#EEEAF6'), 0.6)
    # ---------------------------------------------------------------- valley
    ridge_field(c, 862, 18, 31, '#E9E3F2', '#EEEAF6')

    def forest(base_y, count, hmin, hmax, body, dark, snow, snow_sh, seed, rim=None, shadow_a=0.0, blur=0.0):
        rr = np.random.default_rng(seed)
        Lf = c.layer()
        xs_ = rr.uniform(-30, W + 30, count)
        hs = rr.uniform(hmin, hmax, count)
        bys = base_y + rr.uniform(-12, 12, count)
        for i in np.argsort(bys):
            x, h, by = xs_[i], hs[i], bys[i]
            if 250 < x < 470 and seed == 33:          # leave the clearing for the village
                continue
            w = h * 0.36
            R = Lf.region(x - w - 6, by - h - 6, x + w + 6, by + h * 0.12)
            if R.empty:
                continue
            pine(R, x, by, h, w, 3, body, dark, snow, snow_sh, rim=rim, shadow_a=shadow_a, k_round=1.0, seed=int(i))
        if blur:
            Lf.rgb[...] = F.blur(Lf.rgb, blur * ss)
            Lf.a[...] = F.blur(Lf.a, blur * ss)
        c.over(Lf)

    forest(872, 60, 30, 56, '#9C9CCB', '#8086BC', '#F3EEF9', '#CFC9E6', 32)
    ridge_field(c, 905, 22, 32, '#EFEAF6', '#F3F0F9')
    forest(930, 40, 58, 96, '#7184B6', '#55689E', '#F6F3FB', '#C8CAE6', 33, rim='#FFD9C8', shadow_a=0.15)
    ridge_field(c, 985, 26, 33, '#F7F4FB', '#E9EFF8', depth=300)
    # village in the clearing
    cabin(c, 300, 1012, 1.0, 1)
    cabin(c, 418, 996, 0.78, 2)
    smoke(c, 322, 925, 1.0, seed=1)
    smoke(c, 435, 920, 0.8, seed=2)
    # lantern glow + campfire spot
    R = c.region(330, 960, 420, 1060)
    rr_ = np.hypot(R.X - 372, (R.Y - 1022) * 1.6)
    R.paint(np.exp(-(rr_ / 26) ** 2), hexc('#FFC27A'), 0.45)
    R.fill(F.sd_circle(R.X, R.Y, 372, 1018, 3.2), hexc('#FFE6A8'))
    for (px_, pb, ph, sd) in [(238, 1020, 76, 5), (480, 1004, 92, 6), (505, 1020, 60, 7), (205, 1030, 52, 8)]:
        R = c.region(px_ - 40, pb - ph - 6, px_ + 40, pb + 12)
        pine(R, px_, pb, ph, ph * 0.36, 3, '#3F7480', '#28505E', '#FFFFFF', '#CBD6EC', rim='#FFD9C8', shadow_a=0.2,
             k_round=1.2, seed=sd)
    # near snow field: soft drifts
    R = c.region(0, 980, W, H)
    g = np.clip((R.Y - 990) / 290, 0, 1)
    R.paint(np.clip((R.Y - 985) / 25, 0, 1), F.mix(hexc('#F6F4FB'), hexc('#E2E9F5'), g), 0.6)
    for (dx, dy, rx, ry) in [(140, 1105, 260, 34), (600, 1150, 300, 40), (330, 1250, 420, 50)]:
        R = c.region(dx - rx - 40, dy - ry - 40, dx + rx + 40, dy + ry + 40)
        d = F.sd_ellipse(R.X, R.Y, dx, dy, rx, ry)
        R.paint(R.cov(d, 24) * np.clip((R.Y - dy + ry) / (2 * ry), 0, 1), hexc('#C2D0E8'), 0.45)
        R.paint(R.cov(d + 6, 10) * np.clip(1 - (R.Y - dy + ry) / (0.8 * ry), 0, 1), WHITE, 0.65)
    for _ in range(55):
        x, y = rng.uniform(0, W), rng.uniform(1000, H)
        R = c.region(x - 7, y - 7, x + 7, y + 7)
        s_ = rng.uniform(2.5, 4.8)
        R.fill(F.sd_glint(R.X, R.Y, x, y, s_, s_, R.px), WHITE, rng.uniform(0.6, 0.95))
    # ---------------------------------------------------------------- framing pines (slightly soft)
    Lp = c.layer()
    for (x, by, h, sd) in [(-60, 1330, 440, 41), (52, 1215, 560, 42), (676, 1190, 520, 43), (790, 1330, 420, 44)]:
        w = h * 0.40
        R = Lp.region(x - w - 14, by - h - 14, x + w + 14, by + h * 0.12)
        if R.empty:
            continue
        pine(R, x, by, h, w, 5, '#2F6E62', '#1A4240', '#FFFFFF', '#C2D2EA', rim='#FFC9B0', shadow_a=0.35, k_round=3.0, seed=sd)
    Lp.rgb[...] = F.blur(Lp.rgb, 0.9 * ss)
    Lp.a[...] = F.blur(Lp.a, 0.9 * ss)
    c.over(Lp)
    del Lp
    ridge_field(c, 1232, 22, 41, '#F9FBFE', '#E8EEF8', depth=60)
    # ---------------------------------------------------------------- falling snow
    for _ in range(170):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        rr = rng.uniform(1.1, 2.8)
        R = c.region(x - 6, y - 6, x + 6, y + 6)
        R.fill(F.sd_circle(R.X, R.Y, x, y, rr), WHITE, rng.uniform(0.5, 0.95), feather=0.8)
    for _ in range(22):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        rr = rng.uniform(5, 11)
        R = c.region(x - 3 * rr, y - 3 * rr, x + 3 * rr, y + 3 * rr)
        R.fill(F.sd_circle(R.X, R.Y, x, y, rr), WHITE, rng.uniform(0.2, 0.42), feather=rr * 0.7)
    img = c.image().convert('RGB')
    # ---------------------------------------------------------------- painterly finish
    arr = np.asarray(img).astype(np.float32) / 255.0
    if kuwa:
        arr = 0.55 * kuwahara(arr, kuwa) + 0.45 * arr
    Y_, X_ = np.mgrid[0:H, 0:W].astype(np.float32)
    vx = (X_ / W - 0.5) * 2
    vy = (Y_ / H - 0.5) * 2
    vig = np.clip((vx * vx * 0.6 + vy * vy * 0.35) - 0.25, 0, 1)
    arr = arr * (1 - 0.2 * vig[..., None]) + hexc('#1B2840') * 0.2 * vig[..., None]
    grain = np.random.default_rng(5).standard_normal((H, W)).astype(np.float32)
    grain = F.blur(grain, 0.6) * 0.012
    arr = np.clip(arr + grain[..., None], 0, 1)
    return Image.fromarray((arr * 255 + 0.5).astype(np.uint8), 'RGB')


if __name__ == '__main__':
    out = os.path.join(HERE, '_cache', 'ui_title_bg.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    render_title().save(out)
    print('->', out)
