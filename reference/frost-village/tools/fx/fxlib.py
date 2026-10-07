"""
fxlib - tiny procedural 2D rendering kit (numpy + Pillow) shared by the FX / UI / ground
generators in tools/fx/.  Not a script; imported by gen_fx.py, gen_ui.py, gen_ground.py.

Model
-----
* Shapes are signed distance fields (SDF) in OUTPUT-pixel units (negative = inside).
* A Canvas is supersampled (default 4x).  Coordinates `c.X`, `c.Y` are output-pixel
  coordinates of the supersample centres, so all drawing code is resolution independent.
* Colour is premultiplied float RGBA in sRGB space (stylised art, so no linear-light maths).
* `c.image()` downsamples with LANCZOS on premultiplied channels (no dark fringes).
* Soft-3D "toy" look: `bevel_normals(d, width)` turns any SDF into a pillowy height field
  and `shade()` lights it from the shared upper-left sun (CONTRACT §1).
* Seamless textures: `fft_noise()` / `worley()` are periodic on their grid; `blur(wrap=True)`.

Everything is deterministic (explicit seeds).
"""
import math

import numpy as np
from PIL import Image

# Shared sun: from screen upper-left, slightly toward the viewer (CONTRACT §1).
LIGHT = np.array([-0.55, -0.62, 0.56], dtype=np.float32)
LIGHT = LIGHT / np.linalg.norm(LIGHT)


# --------------------------------------------------------------------------- colour
def hexc(h, a=None):
    """'#RRGGBB' -> float32 array (r,g,b) in 0..1 (or (r,g,b,a) if a is given)."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    if a is not None:
        c.append(a)
    return np.array(c, dtype=np.float32)


def mix(c0, c1, t):
    """Lerp between colours; t may be a scalar or an (H,W) array -> (...,3)."""
    c0 = np.asarray(c0, np.float32)
    c1 = np.asarray(c1, np.float32)
    t = np.asarray(t, np.float32)
    if t.ndim >= 1:
        t = t[..., None]
    return c0 + (c1 - c0) * t


def ramp(stops, t):
    """Multi-stop gradient. stops = [(pos, colour), ...] sorted by pos; t (H,W) -> (H,W,3)."""
    t = np.asarray(t, np.float32)
    out = np.zeros(t.shape + (3,), np.float32)
    out[...] = np.asarray(stops[0][1], np.float32)
    for (p0, c0), (p1, c1) in zip(stops[:-1], stops[1:]):
        k = np.clip((t - p0) / max(p1 - p0, 1e-6), 0, 1)
        m = t >= p0
        seg = mix(c0, c1, k)
        out = np.where(m[..., None], seg, out)
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------- SDFs
def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_ellipse(X, Y, cx, cy, rx, ry):
    """Good-enough ellipse distance (IQ's first-order approximation)."""
    px = (X - cx) / rx
    py = (Y - cy) / ry
    k0 = np.sqrt(px * px + py * py)
    k1 = np.sqrt((px / rx) ** 2 + (py / ry) ** 2)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def sd_box(X, Y, cx, cy, hw, hh, r=0.0):
    """Rounded box centred at (cx,cy), half size (hw,hh), corner radius r."""
    qx = np.abs(X - cx) - hw + r
    qy = np.abs(Y - cy) - hh + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_segment(X, Y, ax, ay, bx, by, r=0.0):
    """Capsule (segment a-b thickened by r)."""
    pax, pay = X - ax, Y - ay
    bax, bay = bx - ax, by - ay
    h = np.clip((pax * bax + pay * bay) / max(bax * bax + bay * bay, 1e-9), 0, 1)
    return np.hypot(pax - bax * h, pay - bay * h) - r


def sd_polyline(X, Y, pts, r):
    d = None
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        s = sd_segment(X, Y, ax, ay, bx, by, r)
        d = s if d is None else np.minimum(d, s)
    return d


def sd_polygon(X, Y, pts):
    """Exact signed distance to a simple polygon (list of (x,y))."""
    pts = [(float(a), float(b)) for a, b in pts]
    n = len(pts)
    d = np.full(X.shape, np.inf, np.float32)
    inside = np.zeros(X.shape, bool)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        wx, wy = X - ax, Y - ay
        h = np.clip((wx * ex + wy * ey) / max(ex * ex + ey * ey, 1e-9), 0, 1)
        dd = (wx - ex * h) ** 2 + (wy - ey * h) ** 2
        d = np.minimum(d, dd)
        c1 = Y >= ay
        c2 = Y < by
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        inside ^= flip
    d = np.sqrt(d)
    return np.where(inside, -d, d).astype(np.float32)


def star_points(cx, cy, r_out, r_in, n, rot=-math.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def sd_star(X, Y, cx, cy, r_out, r_in, n=5, rot=-math.pi / 2, round_=0.0):
    """Star polygon with rounded tips (round_ = rounding radius in px)."""
    if round_ > 0:
        pts = star_points(cx, cy, r_out - round_ * 1.6, r_in - round_ * 0.6, n, rot)
        return sd_polygon(X, Y, pts) - round_
    return sd_polygon(X, Y, star_points(cx, cy, r_out, r_in, n, rot))


def sd_arc(X, Y, cx, cy, r, a0, a1, t):
    """Arc of radius r from angle a0 to a1 (radians, a0<a1, screen y down) with round caps,
    half thickness t."""
    ang = np.arctan2(Y - cy, X - cx)
    mid = (a0 + a1) / 2
    half = (a1 - a0) / 2
    da = np.abs(np.angle(np.exp(1j * (ang - mid))))
    on = da <= half
    d_ring = np.abs(np.hypot(X - cx, Y - cy) - r) - t
    e0 = np.hypot(X - (cx + r * math.cos(a0)), Y - (cy + r * math.sin(a0))) - t
    e1 = np.hypot(X - (cx + r * math.cos(a1)), Y - (cy + r * math.sin(a1))) - t
    return np.where(on, d_ring, np.minimum(e0, e1)).astype(np.float32)


def sd_heart_iq(X, Y, cx, cy, s):
    """Exact heart SDF (Inigo Quilez), bottom tip at (cx, cy + s*0.62), width ~1.25*s*2, y down."""
    px = np.abs(X - cx) / (s * 1.6)
    py = (cy + s * 0.62 - Y) / (s * 1.6)          # 0 at the tip, up = positive
    d1 = np.sqrt((px - 0.25) ** 2 + (py - 0.75) ** 2) - math.sqrt(2.0) / 4.0
    m = np.maximum(px + py, 0.0) * 0.5
    d2 = np.sqrt(np.minimum(px ** 2 + (py - 1.0) ** 2, (px - m) ** 2 + (py - m) ** 2)) * np.sign(px - py)
    return (np.where(py + px > 1.0, d1, d2) * s * 1.6).astype(np.float32)


def sd_heart(X, Y, cx, cy, s):
    """Chubby heart of overall width ~2.1*s centred near (cx,cy)."""
    lx = sd_circle(X, Y, cx - 0.5 * s, cy - 0.28 * s, 0.56 * s)
    rx = sd_circle(X, Y, cx + 0.5 * s, cy - 0.28 * s, 0.56 * s)
    tri = sd_polygon(X, Y, [(cx - 1.03 * s, cy - 0.12 * s), (cx + 1.03 * s, cy - 0.12 * s), (cx, cy + 0.98 * s)])
    return smin(np.minimum(lx, rx), tri - 0.06 * s, 0.22 * s)


def sd_teardrop(X, Y, cx, cy, r, h, tip=0.0):
    """Teardrop: circle (cx,cy,r) with a pointed tip h px ABOVE the centre (h > r).
    tip = rounding radius of the point."""
    h = max(h, r * 1.05)
    beta = math.acos(min(0.999, r / h))
    tx, ty = cx, cy - h
    pr = (cx + r * math.sin(beta), cy - r * math.cos(beta))
    pl = (cx - r * math.sin(beta), cy - r * math.cos(beta))
    tri = sd_polygon(X, Y, [(tx, ty + tip * 1.5), pr, (cx, cy), pl])
    return np.minimum(sd_circle(X, Y, cx, cy, r), tri) - tip * 0.25


def sd_implicit(f, px):
    """Approximate signed distance from an implicit function f (negative inside):
    f / |grad f|, gradient taken on the supersampled grid (px = output px per sample)."""
    gy, gx = np.gradient(f.astype(np.float32), px)
    g = np.sqrt(gx * gx + gy * gy)
    return (f / np.maximum(g, 1e-4)).astype(np.float32)


def sd_glint(X, Y, cx, cy, rx, ry, px, rot_=0.0, pinch=0.5):
    """Concave 4-point 'twinkle' star (astroid-like), arms rx (horizontal) / ry (vertical).
    pinch < 1 makes the sides concave (0.5 = classic sparkle)."""
    if rot_:
        X, Y = rot(X, Y, cx, cy, rot_)
    ax = np.abs(X - cx) / max(rx, 1e-3)
    ay = np.abs(Y - cy) / max(ry, 1e-3)
    f = ax ** pinch + ay ** pinch - 1.0
    return sd_implicit(f * min(rx, ry), px)


def union(*ds):
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def subtract(a, b):
    return np.maximum(a, -b)


def intersect(a, b):
    return np.maximum(a, b)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


def rot(X, Y, cx, cy, ang):
    """Rotate the coordinate frame by -ang about (cx,cy): draw shapes 'rotated by ang'."""
    c, s = math.cos(ang), math.sin(ang)
    dx, dy = X - cx, Y - cy
    return cx + c * dx + s * dy, cy - s * dx + c * dy


# --------------------------------------------------------------------------- blur
def _gauss_fft(n, sigma):
    f = np.fft.fftfreq(n).astype(np.float32)
    return np.exp(-2 * (math.pi * sigma * f) ** 2).astype(np.float32)


def blur(a, sigma, wrap=False):
    """Gaussian blur of an (H,W) or (H,W,C) float array.  wrap=True keeps tiles seamless."""
    if sigma <= 0:
        return a
    a = np.asarray(a, np.float32)
    pad = 0 if wrap else int(math.ceil(sigma * 3)) + 1
    if pad:
        widths = [(pad, pad), (pad, pad)] + [(0, 0)] * (a.ndim - 2)
        src = np.pad(a, widths, mode='constant')
    else:
        src = a
    H, W = src.shape[:2]
    ky = _gauss_fft(H, sigma)[:, None]
    kx = np.exp(-2 * (math.pi * sigma * np.fft.rfftfreq(W)) ** 2).astype(np.float32)[None, :]
    k = ky * kx
    if src.ndim == 2:
        out = np.fft.irfft2(np.fft.rfft2(src) * k, s=(H, W))
    else:
        out = np.stack([np.fft.irfft2(np.fft.rfft2(src[..., i]) * k, s=(H, W)) for i in range(src.shape[2])], -1)
    if pad:
        out = out[pad:-pad, pad:-pad]
    return out.astype(np.float32)


def shift(a, dx, dy):
    """Integer shift (in array pixels) with zero fill."""
    out = np.zeros_like(a)
    H, W = a.shape[:2]
    dx, dy = int(round(dx)), int(round(dy))
    xs0, xs1 = max(0, -dx), min(W, W - dx)
    ys0, ys1 = max(0, -dy), min(H, H - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = a[ys0:ys1, xs0:xs1]
    return out


# --------------------------------------------------------------------------- canvas
class Canvas:
    """Supersampled premultiplied RGBA float canvas.  w,h = output size in px."""

    def __init__(self, w, h, ss=4):
        self.w, self.h, self.ss = int(w), int(h), int(ss)
        H, W = self.h * self.ss, self.w * self.ss
        ys = (np.arange(H, dtype=np.float32) + 0.5) / self.ss
        xs = (np.arange(W, dtype=np.float32) + 0.5) / self.ss
        self.X, self.Y = np.meshgrid(xs, ys)
        self.px = 1.0 / self.ss
        self.rgb = np.zeros((H, W, 3), np.float32)
        self.a = np.zeros((H, W), np.float32)

    # --- layers
    def layer(self):
        L = Canvas.__new__(Canvas)
        L.w, L.h, L.ss, L.X, L.Y, L.px = self.w, self.h, self.ss, self.X, self.Y, self.px
        L.rgb = np.zeros_like(self.rgb)
        L.a = np.zeros_like(self.a)
        return L

    def region(self, x0, y0, x1, y1):
        """Sub-canvas VIEW of the output-px box (shares pixels; all ops are in-place).
        Use it to evaluate expensive SDFs only where a shape can be."""
        s = self.ss
        H, W = self.a.shape
        i0 = min(H, max(0, int(math.floor(y0 * s))))
        i1 = min(H, max(i0, int(math.ceil(y1 * s))))
        j0 = min(W, max(0, int(math.floor(x0 * s))))
        j1 = min(W, max(j0, int(math.ceil(x1 * s))))
        R = Canvas.__new__(Canvas)
        R.w, R.h, R.ss, R.px = (j1 - j0) / s, (i1 - i0) / s, s, self.px
        R.X = self.X[i0:i1, j0:j1]
        R.Y = self.Y[i0:i1, j0:j1]
        R.rgb = self.rgb[i0:i1, j0:j1]
        R.a = self.a[i0:i1, j0:j1]
        R.empty = R.a.size == 0
        return R

    def over(self, L, opacity=1.0, mask=None):
        """Composite layer L over self (in place)."""
        a = L.a * opacity
        rgb = L.rgb * opacity
        if mask is not None:
            a = a * mask
            rgb = rgb * mask[..., None]
        self.rgb *= (1 - a[..., None])
        self.rgb += rgb
        self.a *= (1 - a)
        self.a += a

    def under(self, L, opacity=1.0):
        a = L.a * opacity
        rgb = L.rgb * opacity
        self.rgb += rgb * (1 - self.a[..., None])
        self.a += a * (1 - self.a)

    def clip(self, mask):
        self.rgb *= mask[..., None]
        self.a *= mask

    def erase(self, cov):
        k = 1 - np.clip(cov, 0, 1)
        self.rgb *= k[..., None]
        self.a *= k

    # --- coverage
    def cov(self, d, feather=0.0):
        """Anti-aliased coverage from an SDF.  feather (output px) softens the edge."""
        w = self.px + feather
        return np.clip(0.5 - d / w, 0.0, 1.0).astype(np.float32)

    # --- painting
    def paint(self, cov, color, alpha=1.0):
        """Paint colour (3,) or (H,W,3) with coverage (H,W) and alpha (scalar or (H,W))."""
        k = np.clip(cov * alpha, 0, 1).astype(np.float32)
        col = np.asarray(color, np.float32)
        if col.ndim == 1 and col.shape[0] == 4:
            k = k * col[3]
            col = col[:3]
        self.rgb *= (1 - k[..., None])
        self.rgb += col * k[..., None]
        self.a *= (1 - k)
        self.a += k

    def fill(self, d, color, alpha=1.0, feather=0.0):
        self.paint(self.cov(d, feather), color, alpha)

    def add(self, cov, color, alpha=1.0):
        """Additive light (keeps alpha)."""
        k = np.clip(cov * alpha, 0, 1)
        self.rgb += np.asarray(color, np.float32) * k[..., None]
        np.minimum(self.rgb, self.a[..., None], out=self.rgb)

    def shadow(self, cov, dx=0.0, dy=3.0, sigma=3.0, color='#1B2840', opacity=0.35):
        """Paint a blurred, offset copy of `cov` (output px units)."""
        s = shift(cov, dx * self.ss, dy * self.ss)
        s = blur(s, sigma * self.ss)
        self.paint(np.clip(s, 0, 1), hexc(color) if isinstance(color, str) else color, opacity)

    def glow(self, cov, sigma, color, opacity=1.0, additive=False):
        g = np.clip(blur(cov, sigma * self.ss), 0, 1)
        col = hexc(color) if isinstance(color, str) else color
        if additive:
            self.add(g, col, opacity)
        else:
            self.paint(g, col, opacity)

    # --- output
    def image(self, out_size=None):
        """Downsample to the output size (LANCZOS on premultiplied) -> PIL RGBA."""
        W, H = out_size or (self.w, self.h)
        chans = [self.rgb[..., 0], self.rgb[..., 1], self.rgb[..., 2], self.a]
        res = []
        for ch in chans:
            im = Image.fromarray(np.ascontiguousarray(ch, dtype=np.float32), 'F')
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            res.append(np.asarray(im, np.float32))
        r, g, b, a = res
        a = np.clip(a, 0, 1)
        rgb = np.stack([r, g, b], -1)
        rgb = np.clip(rgb, 0, None)
        with np.errstate(divide='ignore', invalid='ignore'):
            un = np.where(a[..., None] > 1e-4, rgb / np.maximum(a[..., None], 1e-4), 0)
        un = np.clip(un, 0, 1)
        out = np.dstack([un, a])
        arr = (out * 255 + 0.5).astype(np.uint8)
        arr[arr[..., 3] == 0] = 0
        return Image.fromarray(arr, 'RGBA')


# --------------------------------------------------------------------------- easing
def ease_out(t, p=3.0):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** p


def ease_in(t, p=2.0):
    t = min(max(t, 0.0), 1.0)
    return t ** p


def bump(t, a, b):
    """0 outside [a,b], smooth hump peaking in the middle."""
    if t <= a or t >= b:
        return 0.0
    return math.sin(math.pi * (t - a) / (b - a))


def clamp01(t):
    return min(max(t, 0.0), 1.0)


# --------------------------------------------------------------------------- shading
def bevel_normals(d, width, px, profile='round'):
    """Height field from an SDF (pillow-like rounded rim of `width` px) -> unit normals (H,W,3)."""
    t = np.clip(-d / width, 0, 1)
    if profile == 'round':
        h = np.sqrt(1 - (1 - t) ** 2) * width
    elif profile == 'smooth':
        h = smoothstep(0, 1, t) * width
    else:  # linear chamfer
        h = t * width
    gy, gx = np.gradient(h.astype(np.float32), px)
    n = np.dstack([-gx, -gy, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n


def pillow_normals(cov, sigma, ss, depth=1.0):
    """Inflated 'pillow' normals from a coverage mask: height = blurred coverage.
    No medial-axis ridges (unlike bevel_normals), good for clouds, hearts, blobs.
    sigma in output px; depth ~ slope near the rim (1 = 45 degrees)."""
    h = blur(np.clip(cov, 0, 1), sigma * ss) * depth * sigma
    gy, gx = np.gradient(h.astype(np.float32), 1.0 / ss)
    n = np.dstack([-gx, -gy, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n


def lambert(n, light=LIGHT):
    """Light term relative to a flat surface: 0 on flat, >0 facing the sun, <0 away."""
    return (n @ light) - light[2]


def shade(base, s, hi=0.55, lo=0.55, tint_lo=None):
    """Apply relative light s to base colour(s).  Positive s lerps to white, negative darkens
    (optionally toward tint_lo, e.g. a cool blue shadow)."""
    base = np.asarray(base, np.float32)
    if base.ndim == 1:
        base = np.broadcast_to(base, s.shape + (3,))
    up = np.clip(s, 0, None)[..., None] * hi
    dn = np.clip(-s, 0, None)[..., None] * lo
    out = base + (1 - base) * up
    if tint_lo is not None:
        dark = base * np.asarray(tint_lo, np.float32)
    else:
        dark = base * 0.35
    out = out + (dark - out) * np.clip(dn, 0, 1)
    return np.clip(out, 0, 1)


def specular(n, power=40.0, light=LIGHT):
    h = light + np.array([0, 0, 1.0], np.float32)
    h = h / np.linalg.norm(h)
    return np.clip(n @ h, 0, 1) ** power


def toy(c, d, top, bot, outline=None, ow=3.0, bevel=7.0, gloss=0.35, shadow=0.3,
        sh_dy=3.0, sh_sigma=2.2, hi=0.5, lo=0.45, spec=0.0, yr=None, tint_lo=None, gloss_h=0.45,
        alpha=1.0, sh_color='#1B2840', pillow=None):
    """Paint one 'soft toy' part on canvas c: drop shadow, outline, vertical gradient fill
    lit by a rounded bevel (shared sun), glossy highlight on the upper part."""
    as_c = lambda v: hexc(v) if isinstance(v, str) else np.asarray(v, np.float32)
    if shadow:
        dd = d - (ow if outline is not None else 0)
        c.shadow(c.cov(dd), dy=sh_dy, sigma=sh_sigma, opacity=shadow * alpha, color=sh_color)
    if outline is not None:
        c.fill(d - ow, as_c(outline), alpha)
    if yr is None:
        ys = c.Y[d < 0]
        yr = (float(ys.min()), float(ys.max())) if ys.size else (0, 1)
    t = np.clip((c.Y - yr[0]) / max(yr[1] - yr[0], 1e-3), 0, 1)
    base = mix(as_c(top), as_c(bot), t)
    if pillow:
        n = pillow_normals(c.cov(d), pillow, c.ss)
    else:
        n = bevel_normals(d, bevel, c.px)
    s = lambert(n)
    col = shade(base, s, hi, lo, None if tint_lo is None else as_c(tint_lo))
    if spec:
        col = np.clip(col + spec * specular(n, 30)[..., None], 0, 1)
    c.paint(c.cov(d), col, alpha)
    if gloss:
        g = c.cov(d + bevel * 0.5, feather=1.0) * np.clip(1 - (c.Y - yr[0]) / ((yr[1] - yr[0]) * gloss_h), 0, 1) ** 1.6
        c.paint(g, np.ones(3, np.float32), gloss * alpha)
    return yr


def stroke(c, d, width, color, alpha=1.0, feather=0.0):
    c.fill(np.abs(d) - width / 2, hexc(color) if isinstance(color, str) else color, alpha, feather)


# --------------------------------------------------------------------------- noise (periodic)
def fft_noise(h, w, seed, scale=16.0, beta=None, aniso=1.0, angle=0.0, band=None):
    """Periodic (seamless) noise on an h x w grid, zero-mean / unit-std.
    scale  : feature size in px (gaussian low-pass) when beta is None
    beta   : if given, 1/f^beta spectrum (fractal); scale then = high-frequency cut-off
    aniso  : >1 stretches features along `angle` (radians, screen coords)
    band   : (f_lo, f_hi) cycles/px band-pass instead (ripples)."""
    rng = np.random.default_rng(seed)
    wn = rng.standard_normal((h, w)).astype(np.float32)
    fy = np.fft.fftfreq(h)[:, None].astype(np.float32)
    fx = np.fft.fftfreq(w)[None, :].astype(np.float32)
    c, s = math.cos(angle), math.sin(angle)
    fu = fx * c + fy * s          # along the stretch direction
    fv = -fx * s + fy * c
    fu = fu * aniso
    f = np.sqrt(fu * fu + fv * fv)
    if band is not None:
        lo, hi = band
        filt = np.exp(-((f - (lo + hi) / 2) / ((hi - lo) / 2 + 1e-6)) ** 2)
    elif beta is not None:
        filt = np.where(f > 0, (np.maximum(f, 1.0 / max(h, w))) ** (-beta / 2), 0)
        filt *= np.exp(-(f * scale / 4) ** 2) if scale else 1
    else:
        filt = np.exp(-(math.pi * scale * f) ** 2 / 2)
    filt[0, 0] = 0
    out = np.real(np.fft.ifft2(np.fft.fft2(wn) * filt)).astype(np.float32)
    out -= out.mean()
    out /= out.std() + 1e-9
    return out


def worley(h, w, cells, seed, jitter=0.9, metric='euclid'):
    """Periodic cellular noise. cells = grid cells along the width (must divide nicely).
    Returns (F1, F2, cell_id) with distances in px."""
    rng = np.random.default_rng(seed)
    cx = cells
    cy = max(1, int(round(cells * h / w)))
    sx, sy = w / cx, h / cy
    pts = (0.5 + (rng.random((cy, cx, 2)) - 0.5) * jitter)  # within-cell offsets
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs += 0.5
    ys += 0.5
    gx = np.floor(xs / sx).astype(int)
    gy = np.floor(ys / sy).astype(int)
    F1 = np.full((h, w), np.inf, np.float32)
    F2 = np.full((h, w), np.inf, np.float32)
    ID = np.zeros((h, w), np.int32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            nx = gx + ox
            ny = gy + oy
            wx = nx % cx
            wy = ny % cy
            px_ = (nx + pts[wy, wx, 0]) * sx
            py_ = (ny + pts[wy, wx, 1]) * sy
            if metric == 'euclid':
                dist = np.hypot(xs - px_, ys - py_)
            else:
                dist = np.abs(xs - px_) + np.abs(ys - py_)
            cid = wy * cx + wx
            m1 = dist < F1
            F2 = np.where(m1, F1, np.minimum(F2, dist))
            ID = np.where(m1, cid, ID)
            F1 = np.where(m1, dist, F1)
    return F1, F2, ID


def downsample_wrap(arr, factor):
    """Seamless downsample of a periodic (H,W,C) float array by an integer factor."""
    H, W = arr.shape[:2]
    pad = 4 * factor
    big = np.pad(arr, [(pad, pad), (pad, pad)] + [(0, 0)] * (arr.ndim - 2), mode='wrap')
    oh, ow = big.shape[0] // factor, big.shape[1] // factor
    chans = []
    src = big if big.ndim == 3 else big[..., None]
    for i in range(src.shape[2]):
        im = Image.fromarray(np.ascontiguousarray(src[..., i], np.float32), 'F').resize((ow, oh), Image.LANCZOS)
        chans.append(np.asarray(im, np.float32))
    out = np.stack(chans, -1)[4:-4, 4:-4]
    return out if arr.ndim == 3 else out[..., 0]


def to_rgb_image(rgb):
    return Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')


def to_rgba_image(rgb, a):
    arr = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])
    arr = (arr * 255 + 0.5).astype(np.uint8)
    arr[arr[..., 3] == 0] = 0
    return Image.fromarray(arr, 'RGBA')


# --------------------------------------------------------------------------- saving
def save_png(img, path, quant=None, dither=1.0):
    """Save PNG.  quant=N -> libimagequant palette PNG with N colours (alpha kept)."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if quant:
        import imagequant
        src = img.convert('RGBA')
        q = imagequant.quantize_pil_image(src, dithering_level=dither, max_colors=quant)
        q.save(path, optimize=True)
    else:
        img.save(path, optimize=True)
    return path


def strip(frames):
    """Horizontal sprite strip from equally sized RGBA frames."""
    w, h = frames[0].size
    out = Image.new('RGBA', (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        out.paste(f, (i * w, 0))
    return out


def save_gif(frames, path, fps, panels=('#F4F7FB', '#D9A08A', '#1F5FA8'), hold=0, scale=1, anchor=None):
    """Preview GIF: every frame composited over side-by-side background panels.
    hold = extra blank frames appended (so one-shot effects read as separate bursts).
    anchor = (ax, ay) normalised -> draws a small cross where the sprite origin is."""
    import os
    from PIL import ImageDraw
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w, h = frames[0].size
    w2, h2 = w * scale, h * scale
    seq = list(frames) + [Image.new('RGBA', (w, h), (0, 0, 0, 0))] * hold
    out = []
    for f in seq:
        if scale != 1:
            f = f.resize((w2, h2), Image.LANCZOS)
        im = Image.new('RGBA', (w2 * len(panels), h2), (0, 0, 0, 255))
        for k, col in enumerate(panels):
            im.paste(Image.new('RGBA', (w2, h2), col), (k * w2, 0))
            im.alpha_composite(f, (k * w2, 0))
            if anchor is not None:
                ax, ay = anchor[0] * w2 + k * w2, anchor[1] * h2
                d = ImageDraw.Draw(im)
                d.line([(ax - 4, ay), (ax + 4, ay)], fill=(255, 0, 90, 160))
                d.line([(ax, ay - 4), (ax, ay + 4)], fill=(255, 0, 90, 160))
        out.append(im.convert('RGB').quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(round(1000 / fps)), loop=0,
                optimize=False, disposal=1)
    return path


def rgba_bg(img, color):
    """Flatten an RGBA image on a solid colour (for previews)."""
    bg = Image.new('RGBA', img.size, color)
    bg.alpha_composite(img.convert('RGBA'))
    return bg
