"""
gen_ground.py - seamless ground / water textures, shore foam, decals and the fish school
for Frost Village (CONTRACT §7).  numpy + Pillow only, deterministic.

Re-run (from anywhere, ~1-2 min):
    python3 frost-village/tools/fx/gen_ground.py                    # build everything
    python3 frost-village/tools/fx/gen_ground.py --only ground_plaza # scratch preview only
                                                                    #   -> tools/fx/_cache/ground_only.png
Outputs:
    assets/ground/<key>.png        512x512 seamless textures, shore_foam strip, decals, fish_school
    assets/ground/manifest.json
    docs/previews/ground_sheet.png (each texture tiled 2x2 + decals), ground_scene.png (in context)

Geometry notes (CONTRACT §1, PPU 64, 2:1 iso):
  * World axis "A" (screen direction (2,1), down-right) and "B" (screen (2,-1), up-right):
    1 m along A = (+45.25, +22.63) px.  Plank / furrow coordinates use  a = x + 2y,  b = x - 2y
    (both 90.5 units per metre).  Rows have a period of 512/11 b-units (0.51 m) so that the
    pattern wraps exactly on the 512 px torus (x+512 -> b+512, y+512 -> b-1024).
  * Every texture is built from periodic noise / periodic distance fields and verified by
    tools/fx/check_assets.py (seam continuity test).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import fxlib as F                                      # noqa: E402
from fxlib import hexc                                 # noqa: E402

OUT = os.path.join(ROOT, 'assets', 'ground')
PREV = os.path.join(ROOT, 'docs', 'previews')
CACHE = os.path.join(HERE, '_cache')
N = 512
LXY = np.array([-0.66, -0.75], np.float32)            # screen direction toward the sun (upper-left)
WHITE = hexc('#FFFFFF')


# =========================================================================== periodic helpers
def coords(n=N, ss=1):
    """Pixel-centre coordinates (output px units) of an n*ss periodic grid."""
    s = (np.arange(n * ss, dtype=np.float32) + 0.5) / ss
    X, Y = np.meshgrid(s, s)
    return X, Y


def roll_grad(h, ss=1):
    """Periodic central-difference gradient (per output px)."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * ss
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * ss
    return gx, gy


def relief(h, ss=1, k=1.0):
    """Relative sun light on a height field (positive = facing the sun)."""
    gx, gy = roll_grad(h, ss)
    return -(gx * LXY[0] + gy * LXY[1]) * k


def sample(tex, u, v):
    """Bilinear periodic sampling of tex (H,W[,C]) at float coords u (x), v (y) in texel units."""
    H, W = tex.shape[:2]
    u = np.mod(u - 0.5, W)
    v = np.mod(v - 0.5, H)
    x0 = np.floor(u).astype(np.int32)
    y0 = np.floor(v).astype(np.int32)
    fx = (u - x0).astype(np.float32)
    fy = (v - y0).astype(np.float32)
    x1 = (x0 + 1) % W
    y1 = (y0 + 1) % H
    x0 %= W
    y0 %= H
    if tex.ndim == 3:
        fx = fx[..., None]
        fy = fy[..., None]
    a = tex[y0, x0] * (1 - fx) + tex[y0, x1] * fx
    b = tex[y1, x0] * (1 - fx) + tex[y1, x1] * fx
    return a * (1 - fy) + b * fy


def periodic_conv(img, kernel):
    """Circular convolution (keeps tiles seamless).  kernel centred at [0,0] (wrapped)."""
    return np.real(np.fft.ifft2(np.fft.fft2(img) * np.fft.fft2(kernel))).astype(np.float32)


def centred_kernel(n, fn):
    """Build an n x n kernel from fn(dx, dy) with (0,0) at index [0,0] (wrapped offsets)."""
    d = np.arange(n, dtype=np.float32)
    d = np.where(d > n / 2, d - n, d)
    DX, DY = np.meshgrid(d, d)
    return fn(DX, DY).astype(np.float32)


def worley_xy(X, Y, W, H, cells, seed, jitter=0.9):
    """Periodic Worley noise evaluated at arbitrary coords (X,Y) on a W x H torus.
    Returns (F1, F2, id)."""
    rng = np.random.default_rng(seed)
    cx = cells
    cy = max(1, int(round(cells * H / W)))
    sx, sy = W / cx, H / cy
    pts = 0.5 + (rng.random((cy, cx, 2)) - 0.5) * jitter
    Xm = np.mod(X, W)
    Ym = np.mod(Y, H)
    gx = np.floor(Xm / sx).astype(np.int32)
    gy = np.floor(Ym / sy).astype(np.int32)
    F1 = np.full(X.shape, np.inf, np.float32)
    F2 = np.full(X.shape, np.inf, np.float32)
    ID = np.zeros(X.shape, np.int32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            nx, ny = gx + ox, gy + oy
            wx, wy = nx % cx, ny % cy
            px = (nx + pts[wy, wx, 0]) * sx
            py = (ny + pts[wy, wx, 1]) * sy
            dist = np.hypot(Xm - px, Ym - py)
            cid = wy * cx + wx
            m1 = dist < F1
            F2 = np.where(m1, F1, np.minimum(F2, dist))
            ID = np.where(m1, cid, ID)
            F1 = np.where(m1, dist, F1)
    return F1, F2, ID


def ab(X, Y):
    """Iso plank coordinates: a along screen (2,1), b along (2,-1); 90.5 units per metre."""
    return X + 2 * Y, X - 2 * Y


ROW_P = 512.0 / 11.0          # 0.514 m rows (planks / furrows), wraps exactly on the 512 torus
B2PX = 1.0 / math.sqrt(5.0)   # b-units -> perpendicular screen px across a row line


def lerp3(c0, c1, t):
    return F.mix(c0, c1, np.clip(t, 0, 1))


def finish(rgb, ss):
    """Downsample a periodic supersampled RGB array to N x N."""
    if ss > 1:
        rgb = F.downsample_wrap(rgb, ss)
    return np.clip(rgb, 0, 1)


def to_img(rgb):
    return F.to_rgb_image(rgb)


# =========================================================================== textures
def tex_snow():
    """Soft blue-white snow: gentle drifts, wind ripples along the B axis, rare glitter."""
    rng = np.random.default_rng(101)
    base = hexc('#F4F7FB')
    low = F.fft_noise(N, N, 1, scale=70)
    mid = F.fft_noise(N, N, 2, scale=18)
    rip = F.fft_noise(N, N, 3, band=(1 / 30.0, 1 / 16.0), aniso=4.0, angle=math.atan2(-1, 2))
    rip *= np.clip(0.55 + 0.45 * F.fft_noise(N, N, 4, scale=40), 0, 1)       # ripples come and go
    h = low * 1.6 + mid * 0.5 + rip * 0.55
    lit = relief(h, 1, 1.0)
    rgb = np.broadcast_to(base, (N, N, 3)).copy()
    shadow = hexc('#D5E0EE')
    rgb = lerp3(rgb, shadow, np.clip(-lit * 0.9 - low * 0.05, 0, 1) * 0.55)
    rgb = lerp3(rgb, WHITE, np.clip(lit * 0.9 + low * 0.06, 0, 1) * 0.9)
    # faint cool mottling
    rgb = lerp3(rgb, hexc('#E6EDF7'), np.clip(-mid * 0.25, 0, 1) * 0.5)
    # glitter: tiny white cross glints sitting in a faint ice-blue halo (pops on near-white snow)
    imp = np.zeros((N, N), np.float32)
    pts = rng.integers(0, N, (48, 2))
    imp[pts[:, 1], pts[:, 0]] = rng.uniform(0.7, 1.0, 48)
    halo = periodic_conv(imp, centred_kernel(N, lambda dx, dy: np.exp(-(dx * dx + dy * dy) / 5.0)))
    core = periodic_conv(imp, centred_kernel(N, lambda dx, dy: np.exp(-(dx * dx + dy * dy) / 0.35)
                                              + 0.7 * np.exp(-(dx * dx) / 0.12 - (dy * dy) / 2.2)
                                              + 0.7 * np.exp(-(dy * dy) / 0.12 - (dx * dx) / 2.2)))
    rgb = lerp3(rgb, hexc('#C8D8EC'), np.clip(halo, 0, 1) * 0.55)
    rgb = lerp3(rgb, WHITE, np.clip(core * 1.2, 0, 1))
    return np.clip(rgb, 0, 1)


def tex_plaza():
    """Terracotta deck planks along the A axis (screen (2,1)), like the reference plaza floor."""
    ss = 2
    X, Y = coords(N, ss)
    A, B = ab(X, Y)
    rng = np.random.default_rng(202)
    q = np.floor(B / ROW_P).astype(np.int32)
    fb = (B - q * ROW_P) / ROW_P                    # 0 = lower edge of the plank, 1 = upper edge
    r = np.mod(q, 11)
    Am = np.mod(A, 512.0)
    # joints per row class (A positions, wrap 512)
    joints = []
    for k in range(11):
        n_j = int(rng.integers(1, 3))
        start = rng.uniform(0, 512)
        pos = [(start + j * 512.0 / n_j + rng.uniform(-40, 40)) % 512 for j in range(n_j)]
        joints.append(sorted(pos))
    dj = np.full(X.shape, 1e9, np.float32)          # signed A distance to the nearest joint
    plank = np.zeros(X.shape, np.int32)
    for k in range(11):
        m = r == k
        if not m.any():
            continue
        js = np.array(joints[k], np.float32)
        a = Am[m]
        diff = (a[:, None] - js[None, :] + 256.0) % 512.0 - 256.0
        idx = np.argmin(np.abs(diff), axis=1)
        dj[m] = diff[np.arange(a.size), idx]
        seg = np.searchsorted(js, a) % len(js)
        plank[m] = k * 8 + seg
    # per-plank colour
    tone = rng.uniform(-1, 1, 11 * 8).astype(np.float32)
    warm = rng.uniform(-1, 1, 11 * 8).astype(np.float32)
    base = hexc('#D9A08A')
    rgb = np.broadcast_to(base, X.shape + (3,)).copy()
    rgb = lerp3(rgb, hexc('#CF9480'), np.clip(-tone[plank], 0, 1) * 0.55)
    rgb = lerp3(rgb, hexc('#E2AC96'), np.clip(tone[plank], 0, 1) * 0.55)
    rgb = lerp3(rgb, hexc('#D99A80'), np.clip(warm[plank], 0, 1) * 0.35)
    # wood grain: noise in (a, b) space stretched along a
    grain_tex = F.fft_noise(512, 512, 7, scale=2.2, aniso=10.0, angle=0.0)
    g = sample(grain_tex, Am + plank * 37.0, np.mod(B * 2.0, 512.0))
    rgb = lerp3(rgb, hexc('#C98A74'), np.clip(g - 0.6, 0, 1) * 0.35)
    rgb = lerp3(rgb, hexc('#E6B4A0'), np.clip(-g - 0.8, 0, 1) * 0.25)
    # gentle wear / dust (screen periodic)
    wear = F.fft_noise(N * ss, N * ss, 8, scale=50 * ss)
    rgb = lerp3(rgb, hexc('#E2B19D'), np.clip(wear * 0.5, 0, 1) * 0.22)
    rgb = lerp3(rgb, hexc('#CF9581'), np.clip(-wear * 0.5, 0, 1) * 0.2)
    # plank edges: rounded chamfers (upper edge lit, lower edge shaded) + dark gap
    d_lo = fb * ROW_P * B2PX                          # px from the lower seam
    d_hi = (1 - fb) * ROW_P * B2PX                    # px from the upper seam
    rgb = lerp3(rgb, hexc('#ECBBA6'), np.clip(1 - (d_hi - 0.5) / 1.6, 0, 1) * 0.7)
    rgb = lerp3(rgb, hexc('#C08470'), np.clip(1 - (d_lo - 0.4) / 1.8, 0, 1) * 0.65)
    gap = np.clip(1 - (np.minimum(d_lo, d_hi) - 0.35) / 0.55, 0, 1)
    rgb = lerp3(rgb, hexc('#A86F5D'), gap * 0.75)
    # joints across the plank (lines of constant a): end grain lit on the +a side
    dpx = dj * B2PX
    rgb = lerp3(rgb, hexc('#EAB9A4'), np.clip(1 - (dpx - 0.4) / 1.4, 0, 1) * (dpx > 0) * 0.6)
    rgb = lerp3(rgb, hexc('#C4887A'), np.clip(1 - (-dpx - 0.4) / 1.4, 0, 1) * (dpx < 0) * 0.6)
    rgb = lerp3(rgb, hexc('#A26A58'), np.clip(1 - (np.abs(dpx) - 0.3) / 0.5, 0, 1) * 0.85)
    # nail heads near the joints (world circles -> 2:1 ellipses)
    for side in (-1, 1):
        for fbn in (0.27, 0.73):
            da = dj - side * 9.0
            dbb = (fb - fbn) * ROW_P
            dn = np.sqrt(da * da + dbb * dbb)
            rgb = lerp3(rgb, hexc('#9A6252'), np.clip(1 - (dn - 1.7) / 0.9, 0, 1) * 0.55)
            dh = np.sqrt((da + 0.8) ** 2 + (dbb - 0.8) ** 2)
            rgb = lerp3(rgb, hexc('#E9C2B2'), np.clip(1 - (dh - 0.6) / 0.6, 0, 1) * 0.6)
    return finish(rgb, ss)


def tex_dirt():
    """Trodden forest earth: soft mottling, a few embedded stones, pine needles, snow specks
    (used half-transparent over snow in the forest / hunting zones)."""
    ss = 2
    X, Y = coords(N, ss)
    rng = np.random.default_rng(303)
    n1 = F.fft_noise(N * ss, N * ss, 31, scale=40 * ss)
    n2 = F.fft_noise(N * ss, N * ss, 32, scale=7 * ss)
    n3 = F.fft_noise(N * ss, N * ss, 33, scale=1.6 * ss)
    rgb = np.broadcast_to(hexc('#A88A70'), X.shape + (3,)).copy()
    rgb = lerp3(rgb, hexc('#8E725C'), np.clip(-n1 * 0.6, 0, 1))
    rgb = lerp3(rgb, hexc('#BA9F86'), np.clip(n1 * 0.5, 0, 1))
    h = n1 * 2.0 + n2 * 0.8 + n3 * 0.15
    lit = relief(h, ss, 1.6)
    rgb = lerp3(rgb, hexc('#C8AF96'), np.clip(lit, 0, 1) * 0.5)
    rgb = lerp3(rgb, hexc('#7C624E'), np.clip(-lit, 0, 1) * 0.5)
    rgb = lerp3(rgb, hexc('#957860'), np.clip(n3 - 0.8, 0, 1) * 0.6)
    # embedded stones: shrunken Worley cells (irregular, not round), few of them
    for cells, seed, frac, shrink in ((40, 34, 0.10, 0.30), (20, 35, 0.07, 0.24)):
        F1, F2, ID = worley_xy(X, Y, N, N, cells, seed, jitter=0.8)
        k = cells * cells
        r2 = np.random.default_rng(seed + 1)
        keep = (r2.random(k) < frac)[ID]
        g = r2.uniform(0, 1, k).astype(np.float32)[ID]
        cell = N / cells
        edge = (F2 - F1) * 0.5
        d = np.maximum(cell * shrink - edge, F1 - cell * 0.45)
        cov = np.clip(0.5 - d * ss, 0, 1) * keep
        hgt = np.sqrt(np.clip(-d / (cell * 0.2), 0, 1)) * cell * 0.25
        litp = relief(hgt, ss, 1.0)
        col = F.mix(hexc('#8A8078'), hexc('#ADA297'), g)
        col = lerp3(col, hexc('#D9D0C6'), np.clip(litp, 0, 1) * 0.5)
        col = lerp3(col, hexc('#5E534A'), np.clip(-litp, 0, 1) * 0.5)
        shd = np.clip(0.5 - (d - 1.0) * ss, 0, 1) * keep
        rgb = lerp3(rgb, hexc('#6E5644'), shd * 0.35)
        rgb = lerp3(rgb, col, cov)
    # pine needles: short thin strokes in four orientations (periodic stamping)
    for j, ang in enumerate((0.3, 1.1, 2.0, 2.7)):
        imp = np.zeros((N * ss, N * ss), np.float32)
        pts = rng.integers(0, N * ss, (26, 2))
        imp[pts[:, 1], pts[:, 0]] = 1.0
        ca, sa = math.cos(ang), math.sin(ang)
        ker = centred_kernel(N * ss, lambda dx, dy: np.exp(-((dx * sa - dy * ca) ** 2) / (0.35 * ss * ss))
                             * (np.abs(dx * ca + dy * sa) < 5.5 * ss))
        nd = np.clip(periodic_conv(imp, ker), 0, 1)
        rgb = lerp3(rgb, hexc('#5A4632') if j % 2 else hexc('#4E5A3A'), nd * 0.75)
    # snow specks
    sn = F.fft_noise(N * ss, N * ss, 36, scale=2.5 * ss)
    sn2 = F.fft_noise(N * ss, N * ss, 37, scale=30 * ss)
    rgb = lerp3(rgb, hexc('#F4F7FB'), np.clip((sn - 2.0) * 1.5, 0, 1) * np.clip(sn2 + 0.6, 0, 1))
    return finish(rgb, ss)


def tex_farm():
    """Tilled soil: rounded ridges along the A axis (screen (2,1)) like the crop plots."""
    ss = 2
    X, Y = coords(N, ss)
    A, B = ab(X, Y)
    Am = np.mod(A, 512.0)
    q = np.floor(B / ROW_P)
    fb = B / ROW_P - q
    clod_tex = F.fft_noise(512, 512, 41, scale=2.2)
    lump_tex = F.fft_noise(512, 512, 42, scale=10.0, aniso=2.0, angle=0.0)
    cl = sample(clod_tex, Am, np.mod(B, 512.0))
    lp = sample(lump_tex, Am, np.mod(B, 512.0))
    prof = np.sin(np.clip(fb, 0, 1) * math.pi)            # 1 on the ridge crest, 0 in the furrow
    prof = np.clip(prof, 0, 1) ** 0.6
    h = prof * 6.0 + cl * 0.35 + lp * 0.8
    lit = relief(h, ss, 0.55)
    rgb = F.ramp([(0, hexc('#553C32')), (0.4, hexc('#735446')), (1.0, hexc('#8A6654'))], np.clip(prof + lp * 0.08, 0, 1))
    rgb = lerp3(rgb, hexc('#AC8672'), np.clip(lit, 0, 1) * 0.7)
    rgb = lerp3(rgb, hexc('#45302A'), np.clip(-lit, 0, 1) * 0.6)
    # crumbly speckles and a little frost in the furrows
    sp = F.fft_noise(N * ss, N * ss, 43, scale=1.3 * ss)
    rgb = lerp3(rgb, hexc('#9C7A66'), np.clip(sp - 1.2, 0, 1) * 0.6)
    rgb = lerp3(rgb, hexc('#4E372D'), np.clip(-sp - 1.4, 0, 1) * 0.5)
    fr = F.fft_noise(N * ss, N * ss, 44, scale=2.0 * ss)
    frost = np.clip((fr - 1.3) * 1.2, 0, 1) * np.clip(1 - prof * 1.6, 0, 1)
    rgb = lerp3(rgb, hexc('#E4ECF5'), frost * 0.85)
    return finish(rgb, ss)


def tex_rock():
    """Mine gravel: big rounded stones over fine grey gravel, rare ore-orange chips."""
    ss = 2
    X, Y = coords(N, ss)
    rng = np.random.default_rng(505)
    rgb = np.broadcast_to(hexc('#6F6966'), X.shape + (3,)).copy()
    n1 = F.fft_noise(N * ss, N * ss, 51, scale=30 * ss)
    rgb = lerp3(rgb, hexc('#5E5754'), np.clip(-n1 * 0.6, 0, 1))
    layers = [(64, 52, 0.36, 0.95, 0.9), (30, 53, 0.40, 0.75, 1.0), (15, 54, 0.40, 0.55, 1.15)]
    for cells, seed, rmin, frac, hk in layers:
        F1, F2, ID = worley_xy(X, Y, N, N, cells, seed, jitter=0.85)
        k = cells * cells
        r2 = np.random.default_rng(seed)
        keep = (r2.random(k) < frac)[ID]
        grey = r2.uniform(0, 1, k).astype(np.float32)[ID]
        ore = (r2.random(k) < 0.022)[ID]
        warmish = (r2.random(k) < 0.25)[ID]
        cell = N / cells
        # stone = cell interior shrunk from its border (F2-F1 ~ 2x distance to the border)
        edge = (F2 - F1) * 0.5
        size = cell * rmin
        d = -(edge - cell * 0.10)
        d = np.maximum(d, F1 - size * 1.6)
        cov = np.clip(0.5 - d * ss, 0, 1) * keep
        hgt = np.sqrt(np.clip(-d / (cell * 0.32), 0, 1)) * cell * 0.35 * hk
        lit = relief(hgt, ss, 1.3)
        col = F.mix(hexc('#7D8592'), hexc('#B4BBC6'), grey)
        col = np.where(warmish[..., None], F.mix(col, hexc('#A89A90'), 0.5), col)
        col = np.where(ore[..., None], F.mix(hexc('#C9701F'), hexc('#F0A050'), grey), col)
        col = lerp3(col, hexc('#EEF2F7'), np.clip(lit, 0, 1) * 0.65)
        col = lerp3(col, hexc('#4A4F5A'), np.clip(-lit, 0, 1) * 0.6)
        shd = np.clip(0.5 - (np.maximum(-(edge - cell * 0.10), F1 - size * 1.6) - 0.8 * hk) * ss, 0, 1) * keep
        rgb = lerp3(rgb, hexc('#3E3A3A'), shd * 0.35)
        rgb = lerp3(rgb, col, cov)
    sp = F.fft_noise(N * ss, N * ss, 55, scale=1.2 * ss)
    rgb = lerp3(rgb, hexc('#C9CED6'), np.clip(sp - 1.6, 0, 1) * 0.5)
    sn = F.fft_noise(N * ss, N * ss, 56, scale=2.4 * ss)
    rgb = lerp3(rgb, hexc('#F4F7FB'), np.clip((sn - 2.1) * 1.4, 0, 1) * 0.9)
    del rng
    return finish(rgb, ss)


def caustics(X, Y, seed, cells, width, warp=6.0, ss=1):
    wx = F.fft_noise(N * ss, N * ss, seed + 1, scale=22 * ss) * warp
    wy = F.fft_noise(N * ss, N * ss, seed + 2, scale=22 * ss) * warp
    F1, F2, _ = worley_xy(X + wx, Y + wy, N, N, cells, seed)
    return np.exp(-((F2 - F1) / width) ** 2)


def tex_sea():
    """Deep sea blue (#1F5FA8 like the props scene) with soft caustic webs."""
    ss = 2
    X, Y = coords(N, ss)
    n1 = F.fft_noise(N * ss, N * ss, 61, scale=60 * ss)
    rgb = np.broadcast_to(hexc('#1F5FA8'), X.shape + (3,)).copy()
    rgb = lerp3(rgb, hexc('#1A549A'), np.clip(-n1 * 0.6, 0, 1))
    rgb = lerp3(rgb, hexc('#2569B2'), np.clip(n1 * 0.6, 0, 1))
    c1 = F.blur(caustics(X, Y, 62, 9, 3.6, warp=7.0, ss=ss), 0.8 * ss, wrap=True)
    c2 = F.blur(caustics(X, Y, 63, 14, 2.4, warp=5.0, ss=ss), 0.8 * ss, wrap=True)
    mod = np.clip(0.5 + 0.5 * F.fft_noise(N * ss, N * ss, 64, scale=40 * ss), 0, 1)
    rgb = lerp3(rgb, hexc('#3A84CC'), c1 * (0.16 + 0.22 * mod))
    rgb = lerp3(rgb, hexc('#3F8AD0'), c2 * 0.12 * mod)
    # sparse glints on wave crests
    w = F.fft_noise(N * ss, N * ss, 65, band=(1 / 20.0, 1 / 12.0), aniso=3.0, angle=0.0)
    rgb = lerp3(rgb, hexc('#8CC0EA'), np.clip((w - 2.3) * 0.9, 0, 1) * 0.6)
    return finish(rgb, ss)


def tex_shallow():
    """Shallow water: brighter turquoise blue with strong caustics over a pale bed."""
    ss = 2
    X, Y = coords(N, ss)
    n1 = F.fft_noise(N * ss, N * ss, 71, scale=50 * ss)
    rgb = np.broadcast_to(hexc('#3F97D4'), X.shape + (3,)).copy()
    rgb = lerp3(rgb, hexc('#3488C8'), np.clip(-n1 * 0.6, 0, 1))
    rgb = lerp3(rgb, hexc('#55AADD'), np.clip(n1 * 0.6, 0, 1))
    c1 = caustics(X, Y, 72, 8, 3.0, warp=7.0, ss=ss)
    c2 = caustics(X, Y, 73, 13, 2.0, warp=5.0, ss=ss)
    mod = np.clip(0.55 + 0.45 * F.fft_noise(N * ss, N * ss, 74, scale=40 * ss), 0, 1)
    rgb = lerp3(rgb, hexc('#9FD6F5'), c1 * (0.35 + 0.35 * mod))
    rgb = lerp3(rgb, hexc('#CDEBFB'), c2 * 0.3 * mod)
    return finish(rgb, ss)


# =========================================================================== strips / overlays
def shore_foam(W=512, H=64):
    """Seamless (x) foam band.  Land side at the bottom: bright foam lip centred at y=44
    (0.69 H), a broken second wave line and lacy foam fading toward the water above,
    a soft wet edge below."""
    ss = 3
    xs = (np.arange(W * ss, dtype=np.float32) + 0.5) / ss
    ys = (np.arange(H * ss, dtype=np.float32) + 0.5) / ss
    X, Y = np.meshgrid(xs, ys)

    def wob(seed, amp, kmax, kmin=1):
        r = np.random.default_rng(seed)
        out = np.zeros_like(xs)
        for k in range(kmin, kmax + 1):
            out += amp / k * np.sin(2 * math.pi * k * xs / W + r.uniform(0, 6.3)) * r.uniform(0.5, 1.0)
        return out

    def pnoise1(seed, kmin, kmax):
        """periodic 1D noise in [-1,1]-ish (integer frequencies only)."""
        r = np.random.default_rng(seed)
        out = np.zeros_like(xs)
        for k in range(kmin, kmax + 1):
            out += np.sin(2 * math.pi * k * xs / W + r.uniform(0, 6.3)) * r.uniform(0.3, 1.0)
        return out / math.sqrt(kmax - kmin + 1)

    lip_y = 44 + wob(82, 2.6, 8)
    lip_w = 3.6 + 1.2 * pnoise1(83, 3, 12)
    d_lip = np.abs(Y - lip_y[None, :]) - lip_w[None, :]
    lip_a = np.clip(0.5 - d_lip * 1.2, 0, 1)
    # broken second line (receding wave)
    l2_y = lip_y - 13 + wob(84, 2.0, 6)
    l2_on = np.clip(pnoise1(85, 2, 9) * 2.2 + 0.4, 0, 1)
    d2 = np.abs(Y - l2_y[None, :]) - (1.3 * l2_on[None, :])
    l2_a = np.clip(0.5 - d2 * 1.5, 0, 1) * l2_on[None, :] * 0.8
    # lace between the two lines: warped worley web, patchy
    wx = np.sin(Y * 0.35 + xs[None, :] * 2 * math.pi * 3 / W) * 2.5
    F1, F2, _ = worley_xy(X + wx, Y * 1.6, W, H * 4, 44, 86)
    web = np.exp(-((F2 - F1) / 1.3) ** 2)
    patch = np.clip(pnoise1(87, 4, 16)[None, :] * 1.8 + 0.3, 0, 1)
    band = np.clip((Y - (l2_y[None, :] - 4)) / 8, 0, 1) * np.clip((lip_y[None, :] - Y) / 3, 0, 1)
    lace_a = web * band * patch * 0.75
    # bubbles near the lip
    rng = np.random.default_rng(81)
    bub = np.zeros_like(X)
    for k in range(60):
        bx = rng.uniform(0, W)
        off = rng.uniform(-14, -5)
        br = rng.uniform(0.7, 1.8)
        dx = ((X - bx) + W / 2) % W - W / 2
        ly = np.interp(bx, xs, lip_y)
        dist = np.hypot(dx, Y - (ly + off))
        bub = np.maximum(bub, np.clip(1 - np.abs(dist - br) / 0.55, 0, 1))
    wet = np.clip(1 - (Y - lip_y[None, :] - lip_w[None, :]) / 8.0, 0, 1) * (Y > lip_y[None, :])
    a = np.maximum.reduce([lip_a, l2_a, lace_a, bub * 0.8, wet * 0.3])
    shade_ = np.clip((Y - lip_y[None, :]) / (lip_w[None, :] + 1e-3), 0, 1)
    rgb = F.mix(WHITE, hexc('#D5E7F6'), shade_ * 0.8)
    rgb = F.mix(rgb, hexc('#BFD8EE'), (wet * (lip_a < 0.5)).astype(np.float32))
    rgb = F.mix(rgb, hexc('#E8F4FC'), ((lace_a + bub) > lip_a).astype(np.float32) * 0.6)
    arr = np.dstack([rgb, a])
    arr = F.downsample_wrap(arr, ss)
    return F.to_rgba_image(arr[..., :3], np.clip(arr[..., 3], 0, 1))


def fish_school(W=256, H=128):
    """Dark-blue fish silhouettes (top-down, facing LEFT and slightly up) with soft alpha."""
    c = F.Canvas(W, H)
    rng = np.random.default_rng(91)
    fish = []
    tries = 0
    while len(fish) < 12 and tries < 3000:
        tries += 1
        L = rng.uniform(32, 50)
        x = rng.uniform(L * 0.55 + 4, W - L * 0.55 - 4)
        y = rng.uniform(13, H - 13)
        if all(math.hypot(x - fx, (y - fy) * 1.9) > (L + fl) * 0.6 for fx, fy, fl, _ in fish):
            fish.append((x, y, L, math.radians(rng.uniform(-22, -12))))
    Lyr = c.layer()
    for (x, y, L, ang) in sorted(fish, key=lambda f: f[1]):
        R = Lyr.region(x - L, y - L, x + L, y + L)
        Xr, Yr = F.rot(R.X, R.Y, x, y, ang)                  # local frame: nose toward -x
        u = (Xr - x) / L                                     # -0.5 nose .. +0.5 tail
        v = (Yr - y) / L
        # spindle body: half-thickness peaks behind the head, tapers to the tail stalk
        tt = np.clip((u + 0.46) / 0.82, 0, 1)
        half = 0.165 * np.sin(np.clip(tt, 0, 1) ** 0.75 * math.pi) + 0.012
        body = (np.abs(v) - half) * L
        body = np.maximum(body, (np.abs(u - (-0.05)) - 0.41) * L)
        tail = F.sd_polygon(u, v, [(0.30, 0.0), (0.52, -0.16), (0.47, 0.0), (0.52, 0.16)]) * L - L * 0.008
        pec = np.minimum(F.sd_segment(u, v, -0.18, -0.10, -0.06, -0.19, 0.022),
                         F.sd_segment(u, v, -0.18, 0.10, -0.06, 0.19, 0.022)) * L
        d = F.smin(F.smin(body, tail, L * 0.03), pec, L * 0.03)
        sh = rng.uniform(0.8, 1.0)
        R.fill(d, hexc('#0E2C58'), 0.66 * sh, feather=0.6)
        spine = (np.abs(v) - 0.03) * L
        spine = np.maximum(spine, (np.abs(u + 0.06) - 0.32) * L)
        R.fill(spine, hexc('#33639A'), 0.5 * sh, feather=1.4)
        R.fill(F.sd_circle(u, v, -0.36, -0.045, 0.028) * L, hexc('#7FA7D2'), 0.55 * sh, feather=0.4)
    c.over(Lyr)
    img = c.image()
    arr = np.asarray(img).astype(np.float32) / 255.0
    a = F.blur(arr[..., 3], 0.55)
    pm = F.blur(arr[..., :3] * arr[..., 3:4], 0.55)
    rgb = np.where(a[..., None] > 1e-4, pm / np.maximum(a[..., None], 1e-4), 0)
    return F.to_rgba_image(rgb, a)


# =========================================================================== decals
def iso_world(X, Y, cx, cy):
    """Screen px -> world metres (u along A / screen (2,1), v along B / screen (2,-1))."""
    x, y = (X - cx) / 45.25, (Y - cy) / 22.63
    return (x + y) / 2, (x - y) / 2


def lowfreq(w, h, ss, seed, scale):
    return F.fft_noise(h * ss, w * ss, seed, scale=scale * ss)


def snow_relief_colour(hgt, ss, base='#F4F7FB', lo='#B9C9DE', k=1.0):
    """Shade a snow height field (px units) with the shared sun."""
    gy, gx = np.gradient(hgt.astype(np.float32), 1.0 / ss)
    s = -(gx * LXY[0] + gy * LXY[1]) * k
    col = np.broadcast_to(hexc(base), hgt.shape + (3,)).copy()
    col = F.mix(col, hexc(lo), np.clip(-s, 0, 1))
    col = F.mix(col, WHITE, np.clip(s, 0, 1))
    return col


def decal_path(direction, W=256, H=128, seed=0):
    """Trodden snow path along an iso axis (direction +1: A axis / screen down-right,
    -1: B axis / screen up-right).  Compacted bluish snow with lit / shaded banks."""
    ss = 4
    c = F.Canvas(W, H, ss=ss)
    u, v = iso_world(c.X, c.Y, W / 2, H / 2)
    along, across = (u, v) if direction > 0 else (v, -u)
    nz = lowfreq(W, H, ss, seed, 22)
    nz2 = F.fft_noise(H * ss, W * ss, seed + 1, scale=2.5 * ss)
    wig = 0.07 * np.sin(along * 2.4 + seed) + 0.03 * nz
    half = 0.33 + 0.04 * nz
    acr = across - wig
    length = 1.2 + 0.1 * nz
    end = np.clip((length - np.abs(along)) / 0.6, 0, 1)
    # height: trough (path) with small raised banks
    t = np.abs(acr) / half
    trough = -np.clip(1 - t ** 4, 0, 1) * 2.6
    bank = np.exp(-((t - 1.08) / 0.18) ** 2) * 1.6
    hgt = (trough + bank) * end
    hgt = F.blur(hgt, 0.6 * ss)
    col = snow_relief_colour(hgt, ss, base='#F4F7FB', lo='#AFC1DA', k=0.9)
    inside = np.clip(1 - t, 0, 1) * end
    col = F.mix(col, hexc('#DDE6F1'), np.clip(inside * 1.6, 0, 1) * 0.8)
    tracks = np.exp(-((np.abs(acr) - 0.14) / 0.06) ** 2) * inside
    col = F.mix(col, hexc('#CCD8E8'), np.clip(tracks * (0.6 + 0.3 * nz2), 0, 1))
    dirt = np.clip((0.1 - np.abs(acr)) / 0.1, 0, 1) * np.clip(nz2 * 0.7, 0, 1) * end
    col = F.mix(col, hexc('#B9A08A'), dirt * 0.35)
    a = np.clip((1.25 - t) / 0.35, 0, 1) * end
    c.rgb[...] = col * a[..., None]
    c.a[...] = a
    return c.image()


def decal_drift(seed, W=256, H=128):
    """Wind-swept lumpy snow mound (like the snow_pile props): lit top-left, blue shade
    bottom-right, cast shadow, soft base that melts into ground_snow."""
    ss = 4
    c = F.Canvas(W, H, ss=ss)
    rng = np.random.default_rng(seed)
    sgn = 1 if seed % 2 else -1
    d = None
    blobs = []
    for k in range(9):
        t = (k / 8.0 - 0.5) * 0.85 + rng.uniform(-0.04, 0.04)
        fall = 1 - abs(t) * 1.2
        x = W / 2 + t * W * 0.6
        y = H * 0.56 + t * H * 0.28 * sgn + rng.uniform(-5, 5)
        rx = rng.uniform(17, 29) * max(0.5, fall)
        blobs.append((x, y, rx))
    for (x, y, rx) in blobs:
        e = F.sd_ellipse(c.X, c.Y, x, y, rx, rx * 0.62)
        d = e if d is None else F.smin(d, e, 9)
    cov = c.cov(d)
    sh = np.clip(F.blur(F.shift(cov, 8 * ss, 5 * ss), 5 * ss), 0, 1) * (1 - cov)
    c.paint(sh, hexc('#9DB1CE'), 0.4)
    hgt = F.blur(cov, 6 * ss) * 18
    for (x, y, rx) in blobs:                                  # lumps
        hgt += np.exp(-(((c.X - x) / (rx * 0.7)) ** 2 + ((c.Y - y + rx * 0.15) / (rx * 0.5)) ** 2)) * rx * 0.25
    hgt *= np.clip(F.blur(cov, 2 * ss) * 1.5, 0, 1)
    col = snow_relief_colour(hgt, ss, base='#F4F7FB', lo='#B8C8DE', k=0.75)
    mask = F.smoothstep(0.02, 0.6, F.blur(cov, 2.0 * ss))
    c.paint(mask, col)
    return c.image()


def decal_dirt_patch(W=192, H=96, seed=12):
    ss = 4
    c = F.Canvas(W, H, ss=ss)
    rng = np.random.default_rng(seed)
    u, v = iso_world(c.X, c.Y, W / 2, H / 2)
    r = np.hypot(u, v * 1.1)
    nz = lowfreq(W, H, ss, seed, 14)
    nz2 = F.fft_noise(H * ss, W * ss, seed + 1, scale=2.0 * ss)
    rad = 0.78 + 0.13 * nz
    a = np.clip((rad - r) / 0.22, 0, 1) ** 1.2
    col = F.mix(hexc('#A68263'), hexc('#8D6C50'), np.clip(0.5 + nz * 0.4, 0, 1))
    col = F.mix(col, hexc('#C4A586'), np.clip(nz2 - 0.6, 0, 1) * 0.6)
    col = F.mix(col, hexc('#6F5440'), np.clip(-nz2 - 1.0, 0, 1) * 0.6)
    # slushy rim: whitish band where the patch meets snow
    rim = np.clip(1 - np.abs(r - rad + 0.1) / 0.09, 0, 1)
    col = F.mix(col, hexc('#E3E9F1'), rim * 0.55)
    c.rgb[...] = col * a[..., None]
    c.a[...] = a
    placed = 0
    for k in range(60):
        if placed >= 12:
            break
        px, py = rng.uniform(0.2, 0.8) * W, rng.uniform(0.25, 0.75) * H
        uu, vv = iso_world(np.float32(px), np.float32(py), W / 2, H / 2)
        if math.hypot(uu, vv * 1.1) > 0.5:
            continue
        placed += 1
        rr = rng.uniform(1.3, 2.6)
        R = c.region(px - 6, py - 6, px + 6, py + 6)
        e = F.sd_ellipse(R.X, R.Y, px, py, rr * 1.3, rr)
        R.fill(F.sd_ellipse(R.X, R.Y, px + 0.8, py + 0.8, rr * 1.3, rr), hexc('#5E4634'), 0.4)
        g = rng.uniform(0.55, 0.78)
        R.fill(e, np.array([g, g * 0.97, g * 0.94], np.float32))
        R.fill(F.sd_ellipse(R.X, R.Y, px - rr * 0.35, py - rr * 0.35, rr * 0.5, rr * 0.35), WHITE, 0.5)
    return c.image()


def decal_footprints(W=256, H=128):
    """Boot prints walking down-right along the A axis (indented snow, alternating feet)."""
    ss = 4
    c = F.Canvas(W, H, ss=ss)
    u, v = iso_world(c.X, c.Y, W / 2, H / 2)
    d = None
    for k in range(6):
        uc = -1.05 + k * 0.42
        vc = 0.09 if k % 2 == 0 else -0.09
        uu, vv = u - uc, v - vc
        sole = (np.hypot(uu / 0.115, vv / 0.058) - 1.0) * 0.058
        heel = (np.hypot((uu + 0.13) / 0.055, vv / 0.05) - 1.0) * 0.05
        dd = F.smin(sole, heel, 0.012) * 64
        d = dd if d is None else np.minimum(d, dd)
    cov = c.cov(d)
    hgt = -F.blur(cov, 1.3 * ss) * 5.0 + F.blur(c.cov(d - 2.5), 2.0 * ss) * 1.2
    gy, gx = np.gradient(hgt, 1.0 / ss)
    s = -(gx * LXY[0] + gy * LXY[1])
    col = np.broadcast_to(hexc('#F4F7FB'), cov.shape + (3,)).copy()
    col = F.mix(col, hexc('#C9D6E8'), cov * 0.9)
    col = F.mix(col, hexc('#9FB3D0'), np.clip(-s * 0.8, 0, 1))
    col = F.mix(col, WHITE, np.clip(s * 0.8, 0, 1))
    a = np.clip(F.blur(c.cov(d - 4), 1.5 * ss) * 1.3, 0, 1)
    c.rgb[...] = col * a[..., None]
    c.a[...] = a
    return c.image()


def decal_puddle_ice(W=160, H=80, seed=14):
    ss = 4
    c = F.Canvas(W, H, ss=ss)
    u, v = iso_world(c.X, c.Y, W / 2, H / 2)
    r = np.hypot(u, v * 1.15)
    nz = F.fft_noise(H * ss, W * ss, seed, scale=7 * ss)
    rad = 0.62 + 0.07 * nz
    d = (r - rad) * 64
    cov = c.cov(d)
    # snow rim around the ice (raised, bevel-lit)
    rim = np.clip(c.cov(d - 7, 3) - cov * 0.0, 0, 1)
    hgt = F.blur(c.cov(d - 6), 2.0 * ss) * 3 - F.blur(cov, 1.0 * ss) * 3
    gy, gx = np.gradient(hgt, 1.0 / ss)
    s = -(gx * LXY[0] + gy * LXY[1])
    snow = F.mix(np.broadcast_to(hexc('#F4F7FB'), cov.shape + (3,)), hexc('#C9D6E8'), np.clip(-s, 0, 1) * 0.9)
    snow = F.mix(snow, WHITE, np.clip(s, 0, 1))
    c.rgb[...] = snow * rim[..., None] * np.clip(rim * 1.0, 0, 1)[..., None]
    c.a[...] = rim * F.smoothstep(0.0, 1.0, rim)
    # ice
    t = np.clip(r / np.maximum(rad, 0.1), 0, 1)
    ice = F.ramp([(0, hexc('#8EC2E8')), (0.75, hexc('#A9D3EF')), (1.0, hexc('#D7ECF8'))], t)
    c.paint(cov, ice)
    X2, Y2 = c.X - W / 2, c.Y - H / 2
    streak = np.exp(-((X2 * 0.45 + Y2 + 2) / 3.2) ** 2) + 0.7 * np.exp(-((X2 * 0.45 + Y2 - 9) / 1.6) ** 2)
    c.paint(cov * np.clip(streak, 0, 1) * np.clip(1 - np.abs(X2) / 60, 0, 1), WHITE, 0.75)
    # cracks
    rng = np.random.default_rng(seed + 1)
    for k in range(4):
        x, y = W / 2 + rng.uniform(-14, 14), H / 2 + rng.uniform(-6, 6)
        pts = [(x, y)]
        a0 = rng.uniform(0, 2 * math.pi)
        for j in range(3):
            a0 += rng.uniform(-0.6, 0.6)
            x += math.cos(a0) * rng.uniform(7, 13)
            y += math.sin(a0) * rng.uniform(3, 6)
            pts.append((x, y))
        cr = F.sd_polyline(c.X, c.Y, pts, 0.35)
        c.paint(c.cov(cr) * cov, WHITE, 0.8)
        c.paint(c.cov(F.sd_polyline(c.X + 0.6, c.Y + 0.5, pts, 0.3)) * cov, hexc('#6FA3CC'), 0.45)
    # sparkle
    for (gx_, gy_, s_) in ((W / 2 - 22, H / 2 - 9, 5.5), (W / 2 + 18, H / 2 + 6, 3.5)):
        R = c.region(gx_ - 8, gy_ - 8, gx_ + 8, gy_ + 8)
        R.fill(F.sd_glint(R.X, R.Y, gx_, gy_, s_, s_, R.px), WHITE, 0.95)
    return c.image()


# =========================================================================== registry
TEXTURES = {
    'ground_snow': (tex_snow, 'Soft blue-white snow (#F4F7FB avg) with wind ripples + glitter.'),
    'ground_plaza': (tex_plaza, 'Terracotta deck planks along screen (2,1); 0.51 m wide, joints + nails.'),
    'ground_dirt': (tex_dirt, 'Trodden earth with pebbles and snow specks (works at 0.45-1.0 alpha over snow).'),
    'ground_farm': (tex_farm, 'Tilled soil, ridges along screen (2,1) every 0.51 m (matches crop plots).'),
    'ground_rock': (tex_rock, 'Mine gravel: grey stones + rare orange ore chips.'),
    'water_sea': (tex_sea, 'Deep sea #1F5FA8 with soft caustic webs. Scroll slowly for motion.'),
    'water_shallow': (tex_shallow, 'Shallow turquoise water with bright caustics.'),
}
OVERLAYS = {
    'shore_foam': (shore_foam, [0.5, 0.69], 'decal', 'Seamless in x (512x64). Water above, land below; foam lip centre at y=44 (0.69). Tile along the shoreline.'),
    'fish_school': (fish_school, [0.5, 0.5], 'decal', '13 dark-blue fish facing LEFT (slightly up), soft alpha; scroll left across water_sea, flipX to swim right.'),
    'decal_path_a': (lambda: decal_path(+1, seed=21), [0.5, 0.5], 'decal', 'Trodden path running screen down-right (A axis), ~2.5 m long.'),
    'decal_path_b': (lambda: decal_path(-1, seed=23), [0.5, 0.5], 'decal', 'Trodden path running screen up-right (B axis), ~2.5 m long.'),
    'decal_snow_drift_a': (lambda: decal_drift(31), [0.5, 0.6], 'decal', 'Snow mound with blue shade + cast shadow.'),
    'decal_snow_drift_b': (lambda: decal_drift(34), [0.5, 0.6], 'decal', 'Snow mound (other orientation).'),
    'decal_dirt_patch': (decal_dirt_patch, [0.5, 0.5], 'decal', 'Bare earth patch with pebbles, soft edge.'),
    'decal_footprints': (decal_footprints, [0.5, 0.5], 'decal', 'Boot prints walking down-right (A axis).'),
    'decal_puddle_ice': (decal_puddle_ice, [0.5, 0.5], 'decal', 'Frozen puddle with snow rim, glare and cracks.'),
}


# =========================================================================== previews
def tiled(img, nx=2, ny=2):
    w, h = img.size
    out = Image.new(img.mode, (w * nx, h * ny))
    for j in range(ny):
        for i in range(nx):
            out.paste(img, (i * w, j * h))
    return out


def preview_sheet(texs, overlays):
    cell = 512
    keys = list(texs)
    cols = 4
    rows = (len(keys) + cols - 1) // cols
    W = cols * cell + (cols + 1) * 10
    H = rows * (cell + 24) + 20 + 300
    im = Image.new('RGB', (W, H), (40, 44, 54))
    dr = ImageDraw.Draw(im)
    for n_, k in enumerate(keys):
        x = 10 + (n_ % cols) * (cell + 10)
        y = 10 + (n_ // cols) * (cell + 24)
        t = tiled(texs[k].convert('RGB')).resize((cell, cell), Image.LANCZOS)
        im.paste(t, (x, y))
        dr.text((x, y + cell + 4), k + '  (2x2 tiles, half scale)', fill=(230, 232, 240))
    # last free cell: full-res seam crop of the plaza and snow (corner of 4 tiles)
    n_ = len(keys)
    x = 10 + (n_ % cols) * (cell + 10)
    y = 10 + (n_ // cols) * (cell + 24)
    for j, k in enumerate(['ground_plaza', 'ground_rock']):
        t = tiled(texs[k].convert('RGB'))
        crop = t.crop((512 - 128, 512 - 128, 512 + 128, 512 + 128))
        im.paste(crop, (x + (j % 2) * 256, y))
    for j, k in enumerate(['water_sea', 'ground_farm']):
        t = tiled(texs[k].convert('RGB'))
        crop = t.crop((512 - 128, 512 - 128, 512 + 128, 512 + 128))
        im.paste(crop, (x + j * 256, y + 256))
    dr.text((x, y + cell + 4), 'seam corners at 1:1 (4 tiles meet in the middle)', fill=(230, 232, 240))
    # overlays on snow / sea
    y0 = 10 + rows * (cell + 24) + 6
    snow = texs['ground_snow'].convert('RGBA')
    sea = texs['water_sea'].convert('RGBA')
    bgs = Image.new('RGBA', (W, 290))
    for i in range(0, W, 512):
        bgs.paste(snow, (i, 0))
    sea_strip = Image.new('RGBA', (W, 140))
    for i in range(0, W, 512):
        sea_strip.paste(sea.crop((0, 0, 512, 140)), (i, 0))
    bgs.paste(sea_strip.crop((0, 0, 800, 140)), (0, 0))
    x = 10
    fs = overlays['fish_school']
    bgs.alpha_composite(fs, (20, 6))
    bgs.alpha_composite(fs, (300, 10))
    foam = overlays['shore_foam']
    bgs.alpha_composite(foam.crop((0, 0, 512, 64)), (0, 140 - 44))
    bgs.alpha_composite(foam.crop((0, 0, 288, 64)), (512, 140 - 44))
    x = 820
    for k in ['decal_path_a', 'decal_path_b', 'decal_snow_drift_a', 'decal_snow_drift_b']:
        im_ = overlays[k]
        bgs.alpha_composite(im_, (x, 10 if 'path' in k else 150))
        x += 270 if 'path' in k else 0
        if k == 'decal_path_b':
            x = 820
        elif 'drift' in k:
            x += 270
    x = 20
    for k in ['decal_dirt_patch', 'decal_footprints', 'decal_puddle_ice']:
        im_ = overlays[k]
        bgs.alpha_composite(im_, (x, 160))
        x += im_.width + 30
    im.paste(bgs.convert('RGB'), (0, y0))
    return im


def scene_preview(texs, overlays):
    """Mock in-context view: snow field, plaza diamond, sea with foam + fish, decals, pads/props."""
    W, H = 1280, 760
    snow = tiled(texs['ground_snow'], 3, 2).convert('RGBA')
    im = snow.crop((0, 0, W, H))
    # sea in the upper-left triangle (shore along the B axis)
    sea = tiled(texs['water_sea'], 3, 2).convert('RGBA').crop((0, 0, W, H))
    shallow = tiled(texs['water_shallow'], 3, 2).convert('RGBA').crop((0, 0, W, H))
    yy, xx = np.mgrid[0:H, 0:W]
    shore = 330 - xx * 0.5 + 8 * np.sin(xx * 0.02)
    m_sea = np.clip((shore - yy) / 2.0, 0, 1)
    m_sh = np.clip((shore - yy) / 2.0, 0, 1) * np.clip(1 - (shore - yy) / 60.0, 0, 1)
    def comp(base, top, m):
        a = np.asarray(base).astype(np.float32)
        b = np.asarray(top).astype(np.float32)
        out = a * (1 - m[..., None]) + b * m[..., None]
        return Image.fromarray(out.astype(np.uint8), 'RGBA')
    im = comp(im, sea, m_sea)
    im = comp(im, shallow, m_sh * 0.85)
    fs = overlays['fish_school']
    fish_l = Image.new('RGBA', (W, H))
    for (fx, fy) in ((30, 30), (300, 10), (20, 170), (520, -40), (250, 120)):
        fish_l.alpha_composite(fs, (fx, fy)) if fy >= 0 else fish_l.alpha_composite(fs.crop((0, -fy, fs.width, fs.height)), (fx, 0))
    fa = np.asarray(fish_l).copy()
    fa[..., 3] = (fa[..., 3] * np.clip((shore - 18 - yy) / 10.0, 0, 1)).astype(np.uint8)
    im.alpha_composite(Image.fromarray(fa, 'RGBA'))
    # foam along the shore (rotated strip pieces)
    foam = overlays['shore_foam']
    ang = math.degrees(math.atan2(0.5, 1))
    seg = foam.crop((0, 0, 512, 64)).rotate(ang, resample=Image.BICUBIC, expand=True)
    for sx in range(-200, W, 400):
        sy = 330 - sx * 0.5
        cx, cy = sx + 200, sy - 100
        im.alpha_composite(seg, (int(cx - seg.width / 2), int(cy - seg.height / 2 + 4)))
    # plaza diamond 8m x 8m around (760, 470)
    pl = tiled(texs['ground_plaza'], 3, 2).convert('RGBA').crop((0, 0, W, H))
    u = ((xx - 760) / 45.25 + (yy - 470) / 22.63) / 2
    v = ((xx - 760) / 45.25 - (yy - 470) / 22.63) / 2
    m_pl = np.clip((4.0 - np.maximum(np.abs(u), np.abs(v))) * 30, 0, 1)
    im = comp(im, pl, m_pl)
    # farm + rock patches
    fm = tiled(texs['ground_farm'], 3, 2).convert('RGBA').crop((0, 0, W, H))
    u2 = ((xx - 1110) / 45.25 + (yy - 600) / 22.63) / 2
    v2 = ((xx - 1110) / 45.25 - (yy - 600) / 22.63) / 2
    im = comp(im, fm, np.clip((2.2 - np.maximum(np.abs(u2), np.abs(v2))) * 30, 0, 1))
    rk = tiled(texs['ground_rock'], 3, 2).convert('RGBA').crop((0, 0, W, H))
    u3 = ((xx - 250) / 45.25 + (yy - 600) / 22.63) / 2
    v3 = ((xx - 250) / 45.25 - (yy - 600) / 22.63) / 2
    im = comp(im, rk, np.clip((2.0 - np.maximum(np.abs(u3), np.abs(v3))) * 30, 0, 1))
    dt = tiled(texs['ground_dirt'], 3, 2).convert('RGBA').crop((0, 0, W, H))
    u4 = ((xx - 520) / 45.25 + (yy - 640) / 22.63) / 2
    v4 = ((xx - 520) / 45.25 - (yy - 640) / 22.63) / 2
    im = comp(im, dt, np.clip((1.8 - np.maximum(np.abs(u4), np.abs(v4))) * 30, 0, 1) * 0.55)
    for k, (x, y) in [('decal_snow_drift_a', (1050, 300)), ('decal_snow_drift_b', (420, 420)),
                      ('decal_footprints', (420, 560)), ('decal_puddle_ice', (960, 420)),
                      ('decal_dirt_patch', (620, 690)), ('decal_path_a', (1060, 720)), ('decal_path_b', (330, 700))]:
        d = overlays[k]
        im.alpha_composite(d, (x - d.width // 2, y - d.height // 2))
    # UI pads + props if available (coherence check)
    try:
        uj = json.load(open(os.path.join(ROOT, 'assets', 'ui', 'ui_icons.json')))
        ua = Image.open(os.path.join(ROOT, 'assets', 'ui', 'ui_icons.png')).convert('RGBA')
        for k, (x, y) in [('ui_pad_unlock', (560, 420)), ('ui_pad_input', (690, 430)), ('ui_pad_output', (860, 520)),
                          ('ui_pad_cash', (900, 600)), ('ui_pad_unlock', (1110, 470))]:
            f = uj['frames'][k]['frame']
            p = ua.crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h']))
            im.alpha_composite(p, (x - p.width // 2, y - p.height // 2))
    except Exception:
        pass
    try:
        pj = json.load(open(os.path.join(ROOT, 'assets', 'props', 'props_nature.json')))
        pa = Image.open(os.path.join(ROOT, 'assets', 'props', 'props_nature.png')).convert('RGBA')
        def put(name, x, y):
            fr = pj['frames'][name]
            f, sss, src = fr['frame'], fr['spriteSourceSize'], fr['sourceSize']
            p = pa.crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h']))
            full = Image.new('RGBA', (src['w'], src['h']))
            full.paste(p, (sss['x'], sss['y']))
            im.alpha_composite(full, (int(x - src['w'] * 0.5), int(y - src['h'] * 0.88)))
        for name, x, y in [('tree_pine_snow', 120, 520), ('tree_pine_a', 200, 600), ('tree_pine_snow', 1220, 420),
                           ('rock_ore', 250, 590), ('crop_wheat_3', 1110, 600), ('bush_snow', 980, 330)]:
            if name in pj['frames']:
                put(name, x, y)
    except Exception:
        pass
    return im


# =========================================================================== main
def build(only=None):
    os.makedirs(OUT, exist_ok=True)
    texs, overlays = {}, {}
    for k, (fn, _) in TEXTURES.items():
        if only and k not in only:
            continue
        texs[k] = to_img(fn())
        print('  texture', k, texs[k].size, flush=True)
    for k, (fn, *_r) in OVERLAYS.items():
        if only and k not in only:
            continue
        overlays[k] = fn()
        print('  overlay', k, overlays[k].size, flush=True)
    if only:
        os.makedirs(CACHE, exist_ok=True)
        items = [(k, tiled(v.convert('RGBA'))) for k, v in texs.items()]
        bgsnow = Image.new('RGBA', (256, 128), (244, 247, 251, 255))
        for k, v in overlays.items():
            bg = Image.new('RGBA', (v.width * 2 + 10, max(v.height, 64)), (244, 247, 251, 255))
            bg.alpha_composite(v, (0, 0))
            sea = Image.new('RGBA', (v.width, v.height), (31, 95, 168, 255))
            sea.alpha_composite(v)
            bg.alpha_composite(sea, (v.width + 10, 0))
            items.append((k, bg))
        del bgsnow
        W = max(i.width for _, i in items)
        Ht = sum(i.height + 6 for _, i in items)
        sheet = Image.new('RGBA', (W, Ht), (40, 44, 54, 255))
        y = 0
        for k, i in items:
            sheet.alpha_composite(i, (0, y))
            y += i.height + 6
        sheet.save(os.path.join(CACHE, 'ground_only.png'))
        print('  preview ->', os.path.join(CACHE, 'ground_only.png'))
        return

    manifest = {
        'version': 1,
        'generator': 'tools/fx/gen_ground.py',
        'conventions': {
            'textures': '512x512, seamless in x and y (tile with TileSprite or a canvas pattern at scale 1).',
            'isoAxes': 'Planks / furrows run along screen (2,1) (world A axis); rows every 0.514 m.',
            'decals': 'Alpha PNGs with soft edges; anchor = centre unless noted. Draw above ground, below props.',
        },
        'images': [],
        'sprites': {},
    }
    for k, im in texs.items():
        F.save_png(im, os.path.join(OUT, k + '.png'), quant=256, dither=0.75)
        manifest['images'].append({'key': k, 'png': 'ground/%s.png' % k})
        manifest['sprites'][k] = {'image': k, 'anchor': [0.5, 0.5], 'kind': 'tile', 'tile': 'xy',
                                  'frameSize': list(im.size), 'notes': TEXTURES[k][1]}
    for k, im in overlays.items():
        fn, anc, kind, note = OVERLAYS[k]
        F.save_png(im, os.path.join(OUT, k + '.png'), quant=256, dither=0.75)
        manifest['images'].append({'key': k, 'png': 'ground/%s.png' % k})
        e = {'image': k, 'anchor': anc, 'kind': kind, 'frameSize': list(im.size), 'notes': note}
        if k == 'shore_foam':
            e['tile'] = 'x'
        manifest['sprites'][k] = e
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    # previews read back the saved (quantised) files so they show exactly what ships
    texs_s = {k: Image.open(os.path.join(OUT, k + '.png')).convert('RGBA').convert('RGB') for k in texs}
    ov_s = {k: Image.open(os.path.join(OUT, k + '.png')).convert('RGBA') for k in overlays}
    os.makedirs(PREV, exist_ok=True)
    preview_sheet(texs_s, ov_s).save(os.path.join(PREV, 'ground_sheet.png'), optimize=True)
    scene_preview(texs_s, ov_s).convert('RGB').save(os.path.join(PREV, 'ground_scene.png'), optimize=True)
    print('ground done ->', OUT)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', default='', help='comma separated keys -> scratch preview in tools/fx/_cache only')
    a = ap.parse_args()
    only = set(k for k in a.only.split(',') if k) or None
    build(only)
