"""
emote_fx.py - animated social FX for the villagers (CONTRACT_VILLAGERS §C).
Library module (no CLI): imported by gen_emotes.py.  Horizontal strips, fixed frame size,
NORMAL blending (ADD vanishes on white snow), so everything carries a dark tinted rim.

  fx_snow_splat   snowball impact burst (one-shot)        anchor = impact point
  fx_music_notes  notes rising and swaying (seamless loop) anchor = instrument / mouth
  fx_hearts       small hearts popping up (one-shot)       anchor = head top
  fx_anger_puff   two dark steam puffs + throbbing vein    anchor = head top
  fx_sweat_drops  nervous sweat drops flung off the head   anchor = head top
  fx_zzz          (extra) Z shapes drifting up (loop)      anchor = sleeper's head

Each sheet function is fn(i, n) -> PIL RGBA frame.  All motion is a function of the frame
index only (loops are periodic over n), so output is deterministic.
"""
import math

import numpy as np

import fxlib as F
from fxlib import hexc
import emote_art as E
import gen_fx as G             # reuse the cotton-ball / cloud helpers of the base FX set

WHITE = hexc('#FFFFFF')


def _frame(w, h, ss=4):
    return F.Canvas(w, h, ss=ss)


def _t1(i, n, lead=0.6):
    """One-shot time base 0..1 where frame 0 is already `lead` of a frame in (never an empty first frame)."""
    return (i + lead) / (n - 1 + lead)


# =========================================================================== snow splat
def sh_snow_splat(i, n, W=112, H=112):
    """Snowball hits something: squash flash, lumpy splat star, chunks flying out and falling,
    a few tiny flakes.  Anchor (0.5, 0.45) = impact point."""
    t = i / (n - 1)
    c = _frame(W, H)
    cx, cy = W * 0.5, H * 0.45
    tau = t * 0.42                                        # seconds (10 frames @ 24 fps)
    rim = '#7F98C0'
    # --- radial impact streaks (frames 1-3)
    sa = F.bump(t, 0.02, 0.42)
    if sa > 0.02:
        for k in range(7):
            a = 2 * math.pi * k / 7 + 0.4
            r0 = 14 + 22 * F.ease_out(t / 0.42, 2)
            ln = 11 * sa
            x0, y0 = cx + r0 * math.cos(a), cy + r0 * math.sin(a) * 0.9
            x1, y1 = cx + (r0 + ln) * math.cos(a), cy + (r0 + ln) * math.sin(a) * 0.9
            R = c.region(min(x0, x1) - 5, min(y0, y1) - 5, max(x0, x1) + 5, max(y0, y1) + 5)
            if R.empty:
                continue
            tt = np.clip(np.hypot(R.X - x0, R.Y - y0) / max(ln, 1), 0, 1)
            d = F.sd_segment(R.X, R.Y, x0, y0, x1, y1, 0) - (0.6 + 1.7 * (1 - tt)) * sa
            R.fill(d - 1.1, hexc(rim), 0.9 * sa)
            R.fill(d, WHITE, sa)
    # --- the splat blob (squashed ball on frame 0, then a lumpy star that sags and melts away)
    grow = F.ease_out(min(1.0, t / 0.22), 2.5)
    fade = 1 - F.ease_in(F.clamp01((t - 0.45) / 0.55), 1.6)
    if fade > 0.02:
        sag = 7 * F.ease_in(F.clamp01((t - 0.25) / 0.75), 1.5)
        Rc = (8 + 9 * grow) * (0.55 + 0.45 * fade)
        blobs = [(cx, cy + sag, Rc)]
        rng = np.random.default_rng(31)
        for k in range(9):
            a = 2 * math.pi * k / 9 + rng.uniform(-0.25, 0.25)
            dist = (7 + rng.uniform(11, 17) * grow) * (0.7 + 0.3 * fade)
            rr = rng.uniform(4.0, 6.6) * (0.4 + 0.6 * grow) * (0.5 + 0.5 * fade)
            blobs.append((cx + dist * math.cos(a), cy + sag * (0.6 + 0.4 * (math.sin(a) > 0)) + dist * math.sin(a) * 0.85,
                          rr))
        if i == 0:   # squashed snowball, wider than tall
            blobs = [(cx, cy, 10.5), (cx - 6, cy + 1, 7.5), (cx + 6, cy + 1, 7.5)]
        R = c.region(cx - 40, cy - 36, cx + 40, cy + 44)
        d = G.puff_sdf(R, blobs, 2.6)
        R.fill(d - 1.4, hexc(rim), fade)
        G.cloud(R, d, '#FFFFFF', '#DCE6F3', '#7E9CCC', alpha=fade, bevel=5.0)
        # bright core flash early on
        if t < 0.3:
            q = np.hypot(R.X - cx, R.Y - cy)
            R.paint(np.exp(-(q / (5 + 14 * t)) ** 2) * R.cov(d), WHITE, 0.9 * (1 - t / 0.3))
    # --- chunks (cotton balls) flying out with gravity
    rng = np.random.default_rng(7)
    for k in range(12):
        a = 2 * math.pi * k / 12 + rng.uniform(-0.2, 0.2)
        v = rng.uniform(70, 118)
        vx, vy = math.cos(a) * v, math.sin(a) * v * 0.8 - 55
        g = 520.0
        t0 = rng.uniform(0.0, 0.06)
        tt = max(0.0, tau - t0)
        if tt <= 0:
            continue
        x = cx + math.cos(a) * 8 + vx * tt
        y = cy + math.sin(a) * 6 + vy * tt + 0.5 * g * tt * tt
        r = rng.uniform(2.4, 5.4) * (1 - F.ease_in(F.clamp01((t - 0.55) / 0.45), 1.5)) * min(1.0, 0.4 + tt * 30)
        G.ball(c, x, y, r, rim=rim)
    # --- tiny flakes
    for k in range(6):
        a = 2 * math.pi * (k + 0.5) / 6 + 0.3
        p = F.ease_out(t, 2)
        x = cx + math.cos(a) * 42 * p
        y = cy + math.sin(a) * 34 * p - 10 * p + 28 * t * t
        al = F.bump(t, 0.05, 1.0)
        if al > 0.05:
            R = c.region(x - 4, y - 4, x + 4, y + 4)
            if not R.empty:
                R.fill(F.sd_circle(R.X, R.Y, x, y, 2.1), hexc(rim), al * 0.9)
                R.fill(F.sd_circle(R.X, R.Y, x, y, 1.3), WHITE, al)
    return c.image()


# =========================================================================== music notes
NOTE_COLS = ['purple', 'pink', 'blue', 'gold']


def note_sdf(X, Y, x, y, h, kind, rot_deg=0.0):
    """Music note glyph of total height h whose (first) note head centre is at (x, y).
    kind 0 = eighth note with flag, 1 = two beamed eighths."""
    Xl, Yl = F.rot(X, Y, x, y, math.radians(rot_deg))
    u, v = (Xl - x) / h, (Yl - y) / h
    hd = lambda hx, hy: F.sd_ellipse(*F.rot(u, v, hx, hy, math.radians(-22)), hx, hy, 0.30, 0.22)
    if kind == 0:
        head = hd(0.0, 0.0)
        stem = F.sd_box(u, v, 0.245, -0.46, 0.06, 0.46, 0.02)
        flag = F.sd_polyline(u, v, [(0.25, -0.90), (0.47, -0.72), (0.56, -0.52), (0.47, -0.34)], 0.075)
        d = F.union(head, stem, flag)
    else:
        h1, h2 = hd(0.0, 0.0), hd(0.62, -0.16)
        s1 = F.sd_box(u, v, 0.245, -0.47, 0.06, 0.47, 0.02)
        s2 = F.sd_box(u, v, 0.865, -0.63, 0.06, 0.47, 0.02)
        beam = F.sd_polygon(u, v, [(0.185, -0.98), (0.925, -1.14), (0.925, -0.98), (0.185, -0.82)])
        d = F.union(h1, h2, s1, s2, beam)
    return d * h


def paint_note(c, x, y, h, kind, rot_deg, pal, alpha=1.0):
    R = c.region(x - h * 0.6, y - h * 1.4, x + h * 1.3, y + h * 0.6)
    if R.empty or alpha <= 0.01 or h < 2:
        return
    d = note_sdf(R.X, R.Y, x, y, h, kind, rot_deg)
    ow = max(1.1, h * 0.085)
    E.group_shadow(R, d, ow, opacity=0.26 * alpha, dy=1.6, sigma=1.3)
    E.part(R, d, pal, ow=ow, bevel=h * 0.12, gloss=0.0, hi=0.6, lo=0.45, alpha=alpha)
    gx, gy = x - h * 0.1, y - h * 0.08
    R.fill(F.sd_ellipse(*F.rot(R.X, R.Y, gx, gy, math.radians(-30)), gx, gy, h * 0.1, h * 0.05), WHITE, 0.8 * alpha,
           feather=0.4)


def sh_music_notes(i, n, W=96, H=128):
    """Seamless loop: 4 notes rise from the anchor, swaying left/right, popping in and fading out."""
    c = _frame(W, H)
    bx, by = W * 0.5, H * 0.9
    notes = [  # phase, side, kind, colour, height
        (0.00, -1, 1, 0, 23.0), (0.25, 1, 0, 1, 21.0), (0.50, -1, 0, 2, 20.0), (0.75, 1, 1, 3, 22.0)]
    for p0, side, kind, ci, hgt in notes:
        u = (i / n + p0) % 1.0
        pop = F.ease_out(min(1.0, u / 0.14), 3) * (1 + 0.18 * F.bump(u, 0.06, 0.24))
        al = min(1.0, (1 - u) / 0.28) * min(1.0, u / 0.06 + 0.2)
        y = by - 6 - 80 * u + hgt * 0.15
        x = bx + side * (6 + 12 * u) + 6 * math.sin(2 * math.pi * u + p0 * 7) - hgt * 0.3
        rot = 14 * math.sin(2 * math.pi * u + p0 * 5) - side * 6
        paint_note(c, x, y, hgt * pop, kind, rot, NOTE_COLS[ci], al)
    return c.image()


# =========================================================================== hearts
def sh_hearts(i, n, W=96, H=128):
    """One-shot: 5 hearts pop out of the head one after another, rise with a sway and fade."""
    t = _t1(i, n)
    c = _frame(W, H)
    bx, by = W * 0.5, H * 0.9
    hearts = [  # t0, dx, size, drift, rot, palette
        (0.00, 0.0, 24.0, -4, -6, 'heart'), (0.10, -17, 17.0, -10, -14, 'pink'), (0.18, 16, 18.0, 9, 12, 'heart'),
        (0.28, -6, 14.0, -14, -8, 'pink'), (0.36, 10, 13.0, 14, 10, 'heart')]
    life = 0.62
    for t0, dx, w, drift, rot0, pal in hearts:
        u = (t - t0) / life
        if u <= 0 or u >= 1:
            continue
        sc = F.ease_out(min(1.0, u / 0.2), 3) * (1 + 0.25 * F.bump(u, 0.1, 0.34))
        al = 1 - F.ease_in(F.clamp01((u - 0.6) / 0.4), 1.5)
        x = bx + dx + drift * F.ease_out(u, 2) + 4 * math.sin(u * 2 * math.pi * 1.2 + dx)
        y = by - 14 - 78 * F.ease_out(u, 1.6)
        ww = w * sc
        if ww < 1.5:
            continue
        R = c.region(x - ww, y - ww, x + ww, y + ww)
        if R.empty:
            continue
        X2, Y2 = F.rot(R.X, R.Y, x, y, math.radians(rot0 * (1 - u)))
        d = E.heart_sdf(X2, Y2, x, y, ww) - ww * 0.02
        E.group_shadow(R, d, 1.5, opacity=0.26 * al, dy=1.6, sigma=1.3)
        E.part(R, d, pal, ow=max(1.1, ww * 0.075), gloss=0.0, hi=0.55, lo=0.45, pillow=ww * 0.16, alpha=al)
        gx, gy = x - ww * 0.24, y - ww * 0.17
        R.fill(F.sd_ellipse(*F.rot(R.X, R.Y, gx, gy, math.radians(-35)), gx, gy, ww * 0.12, ww * 0.07), WHITE,
               0.85 * al, feather=0.4)
    # small twinkles
    for k, (t0, dx, dy) in enumerate(((0.12, -26, -40), (0.3, 24, -58), (0.45, -18, -80))):
        u = (t - t0) / 0.35
        if 0 < u < 1:
            G.glint(c, bx + dx, by + dy - 10 * u, 6.0 * F.bump(u, 0, 1) ** 0.7, glow='#FF9BB5', edge='#B0204E',
                    tip='#FFB3C8', glow_a=0.35, halo=0.6)
    return c.image()


# =========================================================================== anger puff
def _smoke_puff(c, x, y, R, a):
    if R < 1.0 or a <= 0.01:
        return
    blobs = [(x, y, R * 0.78), (x - R * 0.6, y + R * 0.22, R * 0.55), (x + R * 0.6, y + R * 0.2, R * 0.58),
             (x - R * 0.2, y - R * 0.48, R * 0.55), (x + R * 0.35, y - R * 0.32, R * 0.48)]
    Rg = c.region(x - R * 1.6, y - R * 1.4, x + R * 1.6, y + R * 1.3)
    if Rg.empty:
        return
    d = G.puff_sdf(Rg, blobs, R * 0.16)
    Rg.shadow(Rg.cov(d), dy=1.6, sigma=1.4, opacity=0.25 * a)
    Rg.fill(d - max(1.0, R * 0.09), hexc('#353A46'), a)
    G.cloud(Rg, d, '#B4BBC8', '#6A7284', '#353B49', alpha=a, bevel=R * 0.45)


def sh_anger_puff(i, n, W=144, H=96):
    """One-shot: two dark 'huff' puffs blast out of the head (up-left / up-right), swell and
    dissolve; a red anger vein pops above the head and throbs.  Anchor (0.5, 0.85) = head top."""
    t = _t1(i, n)
    c = _frame(W, H)
    bx, by = W * 0.5, H * 0.85
    for s in (-1, 1):
        for j, (t0, dist, size) in enumerate(((0.0, 1.0, 1.0), (0.12, 0.62, 0.62))):
            u = F.clamp01((t - t0) / (1 - t0))
            if u <= 0:
                continue
            p = F.ease_out(u, 3)
            x = bx + s * (8 + 34 * p * dist)
            y = by - 8 - 36 * p * dist + 4 * F.ease_in(u, 2)
            R = (4 + 11.5 * F.ease_out(min(1.0, u / 0.35), 2)) * size * (1 - 0.5 * F.ease_in(F.clamp01((u - 0.55) / 0.45), 1.4))
            a = 1 - F.ease_in(F.clamp01((u - 0.6) / 0.4), 1.6)
            _smoke_puff(c, x, y, R, a)
    # anger vein above the head: pop with overshoot, throb, fade
    pop = F.ease_out(F.clamp01((t - 0.04) / 0.16), 3) * (1 + 0.3 * F.bump(t, 0.1, 0.3))
    if pop > 0.05:
        throb = 1.0 + 0.10 * (1 if (i % 2 == 0) else -0.4) * (t > 0.3)
        al = 1 - F.ease_in(F.clamp01((t - 0.72) / 0.28), 1.5)
        E.anger_vein(c, bx + 1, by - 54, k=0.5 * pop * throb, alpha=al)
    return c.image()


# =========================================================================== sweat drops
def sh_sweat_drops(i, n, W=112, H=96):
    """One-shot: 4 nervous sweat drops spring off the head in arcs and fall.  Anchor (0.5, 0.7)."""
    t = _t1(i, n)
    c = _frame(W, H)
    bx, by = W * 0.5, H * 0.7
    drops = [  # side, x0, vx, vy, r, t0
        (1, 9, 54, -215, 5.6, 0.0), (-1, -9, -50, -205, 5.2, 0.06), (1, 5, 28, -245, 4.2, 0.16),
        (-1, -5, -31, -235, 4.0, 0.22)]
    g = 760.0
    for s, x0, vx, vy, r, t0 in drops:
        u = (t - t0) / (1 - t0)
        if u <= 0:
            continue
        tau = u * 0.58
        x = bx + x0 + vx * tau
        y = by - 6 + vy * tau + 0.5 * g * tau * tau
        vyy = vy + g * tau
        theta = math.atan2(-vx, vyy)          # F.rot turns the up-pointing tip clockwise by theta
        sc = F.ease_out(min(1.0, u / 0.15), 3)
        al = 1 - F.ease_in(F.clamp01((u - 0.7) / 0.3), 1.5)
        if sc * r < 0.6 or al < 0.02:
            continue
        R = c.region(x - 16, y - 16, x + 16, y + 16)
        if R.empty:
            continue
        # teardrop: round end leads, tip trails (tip points against the velocity)
        X2, Y2 = F.rot(R.X, R.Y, x, y, theta)
        rr = r * sc
        d = F.sd_teardrop(X2, Y2, x, y, rr, rr * 2.2, tip=rr * 0.12)
        E.group_shadow(R, d, 1.4, opacity=0.24 * al, dy=1.4, sigma=1.1)
        E.part(R, d, 'water', ow=max(1.1, rr * 0.3), bevel=rr * 0.7, gloss=0.0, hi=0.55, lo=0.4, alpha=al)
        R.fill(F.sd_circle(R.X, R.Y, x - rr * 0.35, y - rr * 0.3, rr * 0.28), WHITE, 0.9 * al)
    return c.image()


# =========================================================================== zzz (extra)
def sh_zzz(i, n, W=96, H=128):
    """Seamless loop: three Z shapes drift up and to the right, growing then fading.
    Anchor (0.35, 0.92) = the sleeper's head top (mirror with flipX for the other side)."""
    c = _frame(W, H)
    bx, by = W * 0.35, H * 0.92
    for p0 in (0.0, 1 / 3, 2 / 3):
        u = (i / n + p0) % 1.0
        x = bx + 6 + 34 * u + 5 * math.sin(2 * math.pi * u * 1.5 + p0 * 4)
        y = by - 8 - 92 * u
        s = 8 + 12 * F.ease_out(u, 1.5)
        al = min(1.0, u / 0.12) * (1 - F.ease_in(F.clamp01((u - 0.6) / 0.4), 1.4))
        rot = 12 * math.sin(2 * math.pi * u + p0 * 3)
        R = c.region(x - s, y - s, x + s, y + s)
        if R.empty or al < 0.02:
            continue
        X2, Y2 = F.rot(R.X, R.Y, x, y, math.radians(rot))
        th = s * 0.17
        d = E._z(X2, Y2, x, y, s, s, th)
        E.group_shadow(R, d, 1.6, opacity=0.25 * al, dy=1.5, sigma=1.2)
        E.part(R, d, 'zzz', ow=max(1.2, s * 0.11), bevel=th * 1.1, gloss=0.0, hi=0.6, lo=0.45, alpha=al)
    return c.image()


# key: (fn, frameW, frameH, frames, fps, repeat, anchor, notes)
SHEETS = {
    'fx_snow_splat': (sh_snow_splat, 112, 112, 10, 24, 0, [0.5, 0.45],
                      'Snowball impact burst: squash, lumpy splat, chunks flying out and falling. Anchor = impact '
                      'point (where fx_snowball hits, e.g. the target\'s face/chest ~ anchor + (0, -40)).'),
    'fx_music_notes': (sh_music_notes, 96, 128, 16, 12, -1, [0.5, 0.9],
                       'Seamless loop of rising, swaying notes (purple/pink/blue/gold). Anchor = bard\'s lute / '
                       'head side. Notes rise ~85 px.'),
    'fx_hearts': (sh_hearts, 96, 128, 16, 16, 0, [0.5, 0.9],
                  'One-shot: 5 hearts pop up one after another and float ~80 px up. Anchor = head top.'),
    'fx_anger_puff': (sh_anger_puff, 144, 96, 12, 18, 0, [0.5, 0.85],
                      'One-shot: two dark huff puffs blast out sideways from the head + throbbing red anger vein '
                      'above. Anchor = head top (character anchor + (0, headTop)).'),
    'fx_sweat_drops': (sh_sweat_drops, 112, 96, 12, 18, 0, [0.5, 0.7],
                       'One-shot: 4 sweat drops spring off the head in arcs. Anchor = head top.'),
    'fx_zzz': (sh_zzz, 96, 128, 18, 8, -1, [0.35, 0.92],
               'EXTRA (not in contract): looping Z shapes drifting up-right for dozing villagers (grandpa on the '
               'bench). Anchor = head top; use flipX when the sleeper faces right.'),
}
