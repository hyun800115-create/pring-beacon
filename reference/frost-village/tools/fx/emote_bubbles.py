"""
emote_bubbles.py - speech / emote bubbles for Frost Village villagers (CONTRACT_VILLAGERS §C).
Library module (no CLI): imported by gen_emotes.py.  Same look as gen_ui.py's ui_bubble
(white -> ice-white gradient, blue-grey outline, rounded bevel, soft navy drop shadow).

  ui_emote_bubble  round bubble (~82 px) with a tail at the bottom centre; anchor = tail tip.
  ui_chat_bubble   9-slice speech-bubble BODY (no tail) for short text, 96x78 source.
                   Stretches cleanly from 80x56 up to 320x96 (and beyond).
  ui_chat_tail     tail piece for ui_chat_bubble.  It is "un-blended" against the exact pixels of
                   the body's bottom band, so  body(9-slice) + tail  ==  a bubble rendered in one
                   piece: no seam, the outline flows round the neck of the tail.

All geometry constants live here so gen_emotes.py can publish them in the manifest.
"""
import math

import numpy as np
from PIL import Image

import fxlib as F
from fxlib import hexc

LINE = '#8FA0BA'         # outline (same as ui_bubble)
TOP, BOT = '#FFFFFF', '#EEF3FA'
LO = '#B8C6DC'
OW = 2.2

# ---------------------------------------------------------------- emote bubble
EB_W, EB_H = 92, 106
EB_CX, EB_CY, EB_R = 46.0, 43.0, 38.5


def _bubble_paint(c, d, y0, y1, shadow=True, bevel=7.0, sh_dy=3.0, sh_sigma=2.6, sh_op=0.28):
    """Paint a bubble shape `d` with the house bubble look; gradient uses the fixed y-range y0..y1."""
    if shadow:
        c.shadow(c.cov(d - OW), dy=sh_dy, sigma=sh_sigma, opacity=sh_op)
    c.fill(d - OW, hexc(LINE))
    t = np.clip((c.Y - y0) / max(1.0, y1 - y0), 0, 1)
    base = F.mix(hexc(TOP), hexc(BOT), t)
    n = F.bevel_normals(d, bevel, c.px)
    c.paint(c.cov(d), F.shade(base, F.lambert(n), 0.5, 0.22, tint_lo=hexc(LO)))


def emote_bubble_sdf(c):
    cx, cy, r = EB_CX, EB_CY, EB_R
    body = F.sd_circle(c.X, c.Y, cx, cy, r)
    tail = F.sd_polygon(c.X, c.Y, [(cx - 11.5, cy + r - 9), (cx + 11.5, cy + r - 9), (cx + 1.4, cy + r + 11.5),
                                   (cx - 1.4, cy + r + 11.5)]) - 2.4
    return F.smin(body, tail, 5.0)


def emote_bubble(shadow=True):
    c = F.Canvas(EB_W, EB_H)
    d = emote_bubble_sdf(c)
    _bubble_paint(c, d, EB_CY - EB_R, EB_CY + EB_R, shadow=shadow)
    # faint inner rim highlight on the upper-left (glassy, matches the UI gloss)
    arc = F.sd_arc(c.X, c.Y, EB_CX, EB_CY, EB_R - 6.0, math.radians(200), math.radians(250), 1.8)
    c.fill(arc, hexc('#FFFFFF'), 0.9, feather=0.8)
    return c.image()


# ---------------------------------------------------------------- chat bubble (9-slice body)
CB_W, CB_H = 96, 78
CB_X0, CB_X1, CB_Y0, CB_Y1, CB_RAD = 4.0, 92.0, 4.0, 66.0, 16.0     # fill rectangle (outline is outside)
CB_NINE = dict(left=22, right=22, top=22, bottom=30)
TAIL_JOIN = 58            # source row where the tail piece starts (inside the body's bottom band)
TAIL_X0, TAIL_X1 = 26, 70  # source columns the tail piece covers (inside the uniform middle columns)
TAIL_H = 40               # tail piece height


def chat_body_sdf(c):
    return F.sd_box(c.X, c.Y, (CB_X0 + CB_X1) / 2, (CB_Y0 + CB_Y1) / 2, (CB_X1 - CB_X0) / 2, (CB_Y1 - CB_Y0) / 2,
                    CB_RAD)


def chat_tail_sdf(c, cx):
    return F.sd_polygon(c.X, c.Y, [(cx - 9.5, CB_Y1 - 6), (cx + 9.5, CB_Y1 - 6), (cx + 1.3, CB_Y1 + 12.5),
                                   (cx - 1.3, CB_Y1 + 12.5)]) - 2.2


def _chat_render(h, with_tail):
    c = F.Canvas(CB_W, h)
    d = chat_body_sdf(c)
    if with_tail:
        d = F.smin(d, chat_tail_sdf(c, CB_W / 2), 4.0)
    _bubble_paint(c, d, CB_Y0, CB_Y1, sh_dy=2.5, sh_sigma=2.2)
    return c.image()


def chat_bubble():
    """9-slice body source (96x78).  Content (text) box inside a stretched w x h bubble:
    x 12..w-12, y 8..h-18 (see manifest notes)."""
    return _chat_render(CB_H, False)


def _unblend(M, B):
    """Return T so that  T over B == M  (premultiplied float RGBA in 0..1, (H,W,4) arrays).
    Minimal-alpha solution; exact wherever B is opaque or M >= B in alpha."""
    Ma, Ba = M[..., 3], B[..., 3]
    Mp, Bp = M[..., :3], B[..., :3]
    out = np.zeros_like(M)
    opaque = Ba > 0.985
    # --- B opaque: classic alpha un-blending on straight colours
    with np.errstate(divide='ignore', invalid='ignore'):
        Mc = np.where(Ma[..., None] > 1e-4, Mp / np.maximum(Ma[..., None], 1e-4), 0)
        Bc = np.where(Ba[..., None] > 1e-4, Bp / np.maximum(Ba[..., None], 1e-4), 0)
    need_dn = np.where(Bc > 1e-4, (Bc - Mc) / np.maximum(Bc, 1e-4), 0)
    need_up = np.where(Bc < 1 - 1e-4, (Mc - Bc) / np.maximum(1 - Bc, 1e-4), 0)
    ta_o = np.clip(np.max(np.maximum(need_dn, need_up), axis=-1), 0, 1)
    ta_o = np.where(ta_o < 1.5 / 255, 0, ta_o)
    tc_o = np.where(ta_o[..., None] > 0, Mc - Bc * (1 - ta_o[..., None]), 0)     # premultiplied
    # --- B translucent (shadow / AA edge): alpha fixed by the over equation
    ta_t = np.clip((Ma - Ba) / np.maximum(1 - Ba, 1e-4), 0, 1)
    tc_t = Mp - Bp * (1 - ta_t[..., None])
    tc_t = np.clip(tc_t, 0, ta_t[..., None])
    out[..., 3] = np.where(opaque, ta_o, ta_t)
    out[..., :3] = np.where(opaque[..., None], np.clip(tc_o, 0, ta_o[..., None]), tc_t)
    return out


def _premul(img):
    a = np.asarray(img.convert('RGBA'), np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return a


def chat_tail():
    """Tail piece (44x40).  Place its top edge TAIL_JOIN - CB_H = -20 px above the bottom edge of the
    stretched ui_chat_bubble (origin [0.5, 0]), anywhere along the uniform middle part of the body."""
    H = CB_H + 26
    M = _premul(_chat_render(H, True))
    B = _premul(_chat_render(H, False))
    T = _unblend(M, B)[TAIL_JOIN:TAIL_JOIN + TAIL_H, TAIL_X0:TAIL_X1]
    a = np.clip(T[..., 3], 0, 1)
    with np.errstate(divide='ignore', invalid='ignore'):
        rgb = np.where(a[..., None] > 1e-4, T[..., :3] / np.maximum(a[..., None], 1e-4), 0)
    return F.to_rgba_image(rgb, a)


def chat_tail_tip():
    """(dx, dy) of the tail's visible tip relative to the tail piece's anchor (top centre)."""
    c = F.Canvas(CB_W, CB_H + 26)
    d = F.smin(chat_body_sdf(c), chat_tail_sdf(c, CB_W / 2), 4.0) - OW
    col = d[:, d.shape[1] // 2]
    inside = np.where(col < 0)[0]
    tip_y = (inside.max() + 1) / c.ss
    return 0.0, round(tip_y - TAIL_JOIN, 1)


def emote_bubble_tip():
    c = F.Canvas(EB_W, EB_H)
    d = emote_bubble_sdf(c) - OW
    col = d[:, d.shape[1] // 2]
    inside = np.where(col < 0)[0]
    return (inside.max() + 1) / c.ss


def nine_slice(img, w, h, m):
    """Plain 9-slice stretch (previews / checks), same maths as Phaser's NineSlice."""
    l, r, t, b = m['left'], m['right'], m['top'], m['bottom']
    W, H = img.size
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    xs = [(0, l, 0, l), (l, W - r, l, w - r), (W - r, W, w - r, w)]
    ys = [(0, t, 0, t), (t, H - b, t, h - b), (H - b, H, h - b, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            part = img.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR)
            out.alpha_composite(part, (dx0, dy0))
    return out


def compose_chat(body_img, tail_img, w, h, tail_dx=0, margin=4):
    """Preview helper: stretched body + tail at horizontal offset tail_dx from the centre.
    Returns (image, (tip_x, tip_y)) with room for the tail below the body."""
    th = tail_img.height
    can = Image.new('RGBA', (w + 2 * margin, h + th), (0, 0, 0, 0))
    can.alpha_composite(nine_slice(body_img, w, h, CB_NINE), (margin, 0))
    tx = margin + w // 2 + tail_dx - tail_img.width // 2
    ty = h - (CB_H - TAIL_JOIN)
    can.alpha_composite(tail_img, (tx, ty))
    return can
