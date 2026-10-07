"""
gen_emotes.py - emote icons, emote / chat bubbles and social FX for the village NPCs
(docs/CONTRACT_VILLAGERS.md section C).  Procedural: numpy + Pillow, no Blender needed.

Re-run (from anywhere, also on a PC with Python 3 + numpy + Pillow (+ imagequant optional)):
    python3 frost-village/tools/fx/gen_emotes.py              # build everything (~1-2 min)
    python3 frost-village/tools/fx/gen_emotes.py --no-gif     # skip the preview GIFs
    python3 frost-village/tools/fx/gen_emotes.py --only emote_laugh,fx_hearts
                                     # scratch preview only -> tools/fx/_cache/emotes/ (assets untouched)
    python3 frost-village/tools/fx/emote_check.py             # verify the output (exit 0 = OK)
Code:
    emote_art.py      the 20 emote drawings + snowball (64-px units, soft-toy look of gen_ui.py)
    emote_bubbles.py  ui_emote_bubble, ui_chat_bubble (9-slice body), ui_chat_tail (seamless join)
    emote_fx.py       animated strips: fx_snow_splat, fx_music_notes, fx_hearts, fx_anger_puff,
                      fx_sweat_drops (+ extra fx_zzz)
    fxlib.py / gen_fx.py (shared, imported read-only)
Outputs:
    assets/emotes/emotes.png/.json      atlas: 20 emote_* + emote_dots_a0..2 + ui_emote_bubble +
                                        ui_chat_tail + fx_snowball (Phaser JSON hash, trimmed)
    assets/emotes/ui_chat_bubble.png    9-slice source image (margins in manifest.nineSlice)
    assets/emotes/fx_*.png              horizontal animation strips (palette PNG)
    assets/emotes/manifest.json         CONTRACT §2 fragment (atlases, images, sprites, spritesheets, nineSlice)
    docs/previews/emotes_sheet.png      everything on snow AND plaza, in bubbles, at phone sizes
    docs/previews/emotes_scene.png/.gif villagers chatting / snowball fight / music, at game scale
    docs/previews/emotes_fx_<key>.gif   each animated FX on snow / plaza / sea (+ anchor cross)
Deterministic: fixed seeds only.
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # frost-village/
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))              # tools/ (pack_utils)
import fxlib as F                                       # noqa: E402
import pack_utils                                       # noqa: E402
import emote_art as EA                                  # noqa: E402
import emote_bubbles as EB                              # noqa: E402
import emote_fx as EF                                   # noqa: E402

OUT = os.path.join(ROOT, 'assets', 'emotes')
PREV = os.path.join(ROOT, 'docs', 'previews')
CACHE = os.path.join(HERE, '_cache', 'emotes')
ASSETS = os.path.join(ROOT, 'assets')

SNOW, PLAZA, SEA = (244, 247, 251, 255), (217, 160, 138, 255), (31, 95, 168, 255)
INK = (43, 47, 58, 255)
EMOTE_KEYS = [k for k, _, _ in EA.EMOTES]

# recommended in-game sizes (world px at camera zoom 1.2, see notes in the manifest)
EMOTE_BUBBLE_SCALE = 0.75
FLOAT_EMOTE_SCALE = 0.7


# =========================================================================== building
def build_images():
    """-> (atlas_items {key: img}, chat_bubble img, meta dict)"""
    items = {}
    for k, fn, _ in EA.EMOTES:
        items[k] = EA.render(fn)
    for k, fn in EA.DOTS_FRAMES:
        items[k] = EA.render(fn)
    c = F.Canvas(28, 28)
    EA.fx_snowball(c)
    items['fx_snowball'] = c.image()
    items['ui_emote_bubble'] = EB.emote_bubble()
    items['ui_chat_tail'] = EB.chat_tail()
    chat = EB.chat_bubble()
    meta = {'eb_tip': EB.emote_bubble_tip(), 'tail_tip': EB.chat_tail_tip()}
    return items, chat, meta


def build_sheets(only=None):
    sheets = {}
    for k, (fn, fw, fh, n, fps, rep, anc, _) in EF.SHEETS.items():
        if only and k not in only:
            continue
        frames = [fn(i, n) for i in range(n)]
        for f in frames:
            assert f.size == (fw, fh), (k, f.size)
        sheets[k] = frames
        print('  sheet', k, n, 'x', (fw, fh), flush=True)
    return sheets


# =========================================================================== manifest
def _sg(v):
    """-20 -> '- 20', 5.0 -> '+ 5'"""
    v = float(v)
    return ('- ' if v < 0 else '+ ') + ('%g' % abs(v))


def make_manifest(items, chat, meta, atlas):
    eb_w, eb_h = items['ui_emote_bubble'].size
    tip_y = meta['eb_tip']
    ay = round(tip_y / eb_h, 4)
    content_dy = round(EB.EB_CY - tip_y, 1)
    tdx, tdy = meta['tail_tip']
    join_dy = EB.TAIL_JOIN - EB.CB_H                       # tail top relative to the stretched bubble's bottom
    m = {
        'version': 1,
        'generator': 'tools/fx/gen_emotes.py',
        'conventions': {
            'emotes': ('emote_* are 64x64 frames (trimmed in the atlas, anchor = centre), soft-3D, no text. '
                       'Show them inside ui_emote_bubble (bubble scale ~%.2f, emote at the same scale placed at '
                       'the bubble contentCenter) or floating alone at scale ~%.1f with a pop (0 -> 1.15 -> 1 in '
                       '~200 ms) and a gentle bob. Readable down to ~32 px.' % (EMOTE_BUBBLE_SCALE, FLOAT_EMOTE_SCALE)),
            'emoteBubble': ('ui_emote_bubble anchor = tail tip: put it at the villager anchor + (0, headTop - 4) '
                            '(times the character scale). Emote centre = anchor + contentCenter * bubbleScale.'),
            'chatBubble': ('Speech bubble = nineslice(ui_chat_bubble, w, h) with origin (0.5, 1) at (x, y) + image '
                           'ui_chat_tail with origin (0.5, 0) at (x + dx, y %s). Tail tip = (x + dx, y %s) -> to '
                           'point at a head top P use y = P.y %s. Keep |dx| <= w/2 - 36. Sizes 80x56 .. 320x96 '
                           '(any size >= 80x56 works). Text: dark #2B2F3A, ~20 px, centred in the content box '
                           '(inset l12 r12 t8 b18). For an emote inside a chat bubble use scale ~0.55.'
                           % (_sg(join_dy), _sg(join_dy + tdy), _sg(-(join_dy + tdy)))),
            'blend': 'All spritesheets are NORMAL-blend artwork with dark tinted rims: they read on snow, plaza and sea.',
            'sheets': 'Horizontal strips, frame i at x = i*frameWidth. Phaser anim key = sheet key.',
        },
        'atlases': [{'key': 'emotes', 'png': 'emotes/emotes.png', 'json': 'emotes/emotes.json'}],
        'images': [{'key': 'ui_chat_bubble', 'png': 'emotes/ui_chat_bubble.png'}],
        'spritesheets': [],
        'sprites': {},
        'nineSlice': {'ui_chat_bubble': dict(image='ui_chat_bubble', **EB.CB_NINE)},
    }
    for k, fn, note in EA.EMOTES:
        e = {'atlas': 'emotes', 'frame': k, 'anchor': [0.5, 0.5], 'kind': 'emote', 'frameSize': list(items[k].size),
             'notes': note}
        if k == 'emote_dots':
            e['anims'] = {'typing': {'frames': ['emote_dots_a0', 'emote_dots_a1', 'emote_dots_a2', 'emote_dots'],
                                     'fps': 6, 'repeat': -1}}
        m['sprites'][k] = e
    m['sprites']['ui_emote_bubble'] = {
        'atlas': 'emotes', 'frame': 'ui_emote_bubble', 'anchor': [0.5, ay], 'kind': 'ui', 'frameSize': [eb_w, eb_h],
        'contentCenter': [0, content_dy], 'contentRadius': round(EB.EB_R - 3, 1),
        'notes': 'Round emote bubble (~%d px across) with tail at the bottom centre; anchor = tail tip. Draw the emote '
                 'at anchor + contentCenter (scaled with the bubble). Recommended bubble scale %.2f.'
                 % (round(2 * (EB.EB_R + EB.OW)), EMOTE_BUBBLE_SCALE)}
    m['sprites']['ui_chat_bubble'] = {
        'image': 'ui_chat_bubble', 'anchor': [0.5, 1.0], 'kind': 'ui', 'frameSize': list(chat.size),
        'minSize': [80, 56], 'contentInset': {'left': 12, 'right': 12, 'top': 8, 'bottom': 18},
        'bodyBottomInset': round(EB.CB_H - (EB.CB_Y1 + EB.OW), 1),
        'notes': '9-slice speech-bubble BODY (no tail; add ui_chat_tail). Bottom %s px of the frame are drop shadow. '
                 'See conventions.chatBubble.' % round(EB.CB_H - (EB.CB_Y1 + EB.OW), 1)}
    m['sprites']['ui_chat_tail'] = {
        'atlas': 'emotes', 'frame': 'ui_chat_tail', 'anchor': [0.5, 0.0], 'kind': 'ui',
        'frameSize': list(items['ui_chat_tail'].size), 'attachTo': 'ui_chat_bubble', 'attachY': join_dy,
        'tip': [tdx, tdy],
        'notes': 'Tail for ui_chat_bubble. Origin (0.5, 0) at (bubble x + dx, bubble bottom %s): it merges seamlessly '
                 'with the body outline. Tip = anchor + tip. Mirror-safe (symmetric).' % _sg(join_dy)}
    m['sprites']['fx_snowball'] = {
        'atlas': 'emotes', 'frame': 'fx_snowball', 'anchor': [0.5, 0.5], 'kind': 'fx',
        'frameSize': list(items['fx_snowball'].size),
        'notes': 'Thrown snowball (~22 px). Lighting is baked from the upper-left: do not rotate. Fly it on a '
                 'parabola (~0.35-0.5 s) with a soft ground-shadow ellipse below; on arrival play fx_snow_splat '
                 'at the hit point and the target\'s hit anim.'}
    for k, (fn, fw, fh, n, fps, rep, anc, note) in EF.SHEETS.items():
        m['spritesheets'].append({'key': k, 'png': 'emotes/%s.png' % k, 'frameWidth': fw, 'frameHeight': fh,
                                  'frameCount': n, 'fps': fps, 'repeat': rep, 'anchor': anc, 'blend': 'NORMAL',
                                  'notes': note})
    return m


# =========================================================================== preview helpers
def font(size, bold=False):
    for p in ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
              'C:/Windows/Fonts/malgunbd.ttf', '/System/Library/Fonts/AppleSDGothicNeo.ttc'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size), True
            except OSError:
                pass
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',):
        if os.path.isfile(p):
            return ImageFont.truetype(p, size), False
    return ImageFont.load_default(), False


def scaled(im, s):
    if abs(s - 1) < 1e-3:
        return im
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def paste_anchor(dst, im, x, y, anchor, s=1.0):
    im = scaled(im, s)
    dst.alpha_composite(im, (int(round(x - anchor[0] * im.width)), int(round(y - anchor[1] * im.height))))


def emote_in_bubble(dst, items, key, x, y, s=EMOTE_BUBBLE_SCALE, meta=None, pop=1.0):
    """Draw ui_emote_bubble with its tail tip at (x, y) and emote `key` inside (preview only)."""
    eb = items['ui_emote_bubble']
    ay = meta['eb_tip'] / eb.height
    ss = s * pop
    if ss < 0.05:
        return
    paste_anchor(dst, eb, x, y, (0.5, ay), ss)
    cy = y + (EB.EB_CY - meta['eb_tip']) * ss
    paste_anchor(dst, items[key], x, cy, (0.5, 0.5), ss)


def chat_bubble_img(chat, tail, w, h, dx=0):
    return EB.compose_chat(chat, tail, w, h, dx, margin=0)


def draw_chat(dst, chat, tail, items, text, tip, w=None, h=56, emote=None, dx=0, fnt=None):
    """Speech bubble whose tail tip is at `tip` (preview only, mirrors the manifest recipe:
    body bottom = tip.y - (attachY + tip dy), tail at bubble x + dx)."""
    fnt = fnt or font(20)[0]
    dr = ImageDraw.Draw(dst)
    lines = text.split('\n') if text else []
    tw = max([dr.textlength(t, font=fnt) for t in lines] or [0])
    ew = 36 if emote else 0
    if w is None:
        w = int(max(80, tw + ew + 30))
    tdx, tdy = EB.chat_tail_tip()
    join = EB.TAIL_JOIN - EB.CB_H
    by = tip[1] - (join + tdy)                         # bubble bottom
    bx = tip[0] - dx
    im = chat_bubble_img(chat, tail, w, h, dx)
    dst.alpha_composite(im, (int(round(bx - w / 2)), int(round(by - h))))
    cy = by - h + 8 + (h - 26) / 2                     # centre of the content box (inset t8 b18)
    x0 = bx - (tw + ew) / 2
    if emote:
        paste_anchor(dst, items[emote], x0 + 15, cy, (0.5, 0.5), 0.5)
    lh = fnt.size * 1.2 if hasattr(fnt, 'size') else 14
    for j, t in enumerate(lines):
        dr.text((x0 + ew, cy + (j - (len(lines) - 1) / 2) * lh), t, font=fnt, fill=INK, anchor='lm')


_char_cache = {}


def char_frame(key, name):
    """Untrimmed 128x128 frame from the existing character atlases (read-only)."""
    if key not in _char_cache:
        base = os.path.join(ASSETS, 'characters', 'char_%s' % key)
        if not os.path.isfile(base + '.png'):
            _char_cache[key] = None
        else:
            with open(base + '.json', encoding='utf-8') as f:
                _char_cache[key] = (Image.open(base + '.png').convert('RGBA'), json.load(f)['frames'])
    cc = _char_cache[key]
    if cc is None or name not in cc[1]:
        return None
    sheet, frames = cc
    fr = frames[name]
    r, ss = fr['frame'], fr['spriteSourceSize']
    out = Image.new('RGBA', (fr['sourceSize']['w'], fr['sourceSize']['h']), (0, 0, 0, 0))
    out.paste(sheet.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])), (ss['x'], ss['y']))
    return out


def draw_char(dst, key, anim, d, i, x, y, flip=False, s=1.0):
    fr = char_frame(key, '%s_%s_%d' % (anim, d, i))
    if fr is None:
        return
    if flip:
        fr = fr.transpose(Image.FLIP_LEFT_RIGHT)
    # soft ground shadow ellipse like the game
    sh = Image.new('RGBA', dst.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((x - 23 * s, y - 9 * s, x + 23 * s, y + 9 * s), fill=(27, 40, 64, 60))
    dst.alpha_composite(sh)
    paste_anchor(dst, fr, x, y, (0.5, 0.8125), s)


def ground(w, h, kind):
    p = os.path.join(ASSETS, 'ground', 'ground_%s.png' % kind)
    col = SNOW if kind == 'snow' else PLAZA
    if not os.path.isfile(p):
        return Image.new('RGBA', (w, h), col)
    tile = Image.open(p).convert('RGBA')
    out = Image.new('RGBA', (w, h))
    for yy in range(0, h, tile.height):
        for xx in range(0, w, tile.width):
            out.paste(tile, (xx, yy))
    return out


# =========================================================================== previews
def preview_sheet(items, chat, sheets, meta):
    W = 1240
    fnt_s = font(12)[0]
    fnt_k, has_ko = font(19)
    rows_h = [26, 300, 300, 330, 300, 0]
    fx_h = sum(max(fr[0].height, 64) + 10 for fr in sheets.values()) + 60
    H = sum(rows_h) + fx_h
    im = Image.new('RGBA', (W, H), (200, 208, 220, 255))
    dr = ImageDraw.Draw(im)
    dr.text((8, 7), 'emotes_sheet - emotes at 1x (64 px) + in ui_emote_bubble (x0.62) on snow and plaza | phone-size '
                    'test | chat bubbles 80x56..320x96 | social FX strips', fill=INK, font=fnt_s)
    y = 26
    for bg in (SNOW, PLAZA):
        im.paste(bg, (0, y, W, y + 300))
        for j, k in enumerate(EMOTE_KEYS):
            col, row = j % 10, j // 10
            x0 = 14 + col * 122
            yy = y + 8 + row * 146
            im.alpha_composite(items[k], (x0 + 14, yy + 2))
            emote_in_bubble(im, items, k, x0 + 46 + 58, yy + 128, 0.62, meta)
            dr.text((x0 + 2, yy + 128), k[6:], fill=(70, 74, 90, 255), font=fnt_s)
        y += 300
    # phone-size test: in bubbles at 0.56 (= 0.75 on a small phone) and alone at 40 / 32 px
    im.paste(SNOW, (0, y, W // 2, y + 330))
    im.paste(PLAZA, (W // 2, y, W, y + 330))
    for half in (0, 1):
        for j, k in enumerate(EMOTE_KEYS):
            col, row = j % 10, j // 10
            x = half * W // 2 + 40 + col * 58
            emote_in_bubble(im, items, k, x, y + 78 + row * 66, EMOTE_BUBBLE_SCALE * 0.75, meta)
            paste_anchor(im, items[k], x - 6, y + 176 + row * 80, (0.5, 0.5), 40 / 64)
            paste_anchor(im, items[k], x + 22, y + 210 + row * 80, (0.5, 0.5), 32 / 64)
    dr.text((8, y + 2), 'phone test: bubbles at x0.56 (= recommended 0.75 on a small phone); emotes alone at 40 px and '
                        '32 px', fill=INK, font=fnt_s)
    y += 330
    # chat bubbles
    im.paste(SNOW, (0, y, W // 2, y + 300))
    im.paste(PLAZA, (W // 2, y, W, y + 300))
    texts = (['생선 최고!', '촌장님 멋져~', '눈싸움 하자!\n준비됐지?', '빵 냄새~'] if has_ko else
             ['Fish!', 'Chief, cool~', 'Snowball fight!\nReady?', 'Bread~'])
    tdy = EB.TAIL_JOIN - EB.CB_H + EB.chat_tail_tip()[1]
    for half in (0, 1):
        x0 = half * W // 2
        # (w, h, tail dx, emote, text, body centre x, tail tip y)
        layout = [(80, 56, 0, 'emote_laugh', None, 64, 110), (160, 64, -30, 'emote_fish', texts[0], 205, 118),
                  (240, 80, 50, 'emote_heart', texts[1], 440, 132), (320, 96, 0, 'emote_snowball', texts[2], 182, 272),
                  (100, 56, 0, 'emote_dots', None, 402, 260), (160, 60, 40, 'emote_bread', texts[3], 530, 268)]
        for w, h, dx, em, tx, px, py in layout:
            tip = (x0 + px + dx, y + py)
            if tx is None:     # emote-only bubble (typing dots / reaction)
                draw_chat(im, chat, items['ui_chat_tail'], items, '', tip, w=w, h=h, dx=dx)
                paste_anchor(im, items[em], tip[0] - dx, tip[1] - tdy - h + 8 + (h - 26) / 2, (0.5, 0.5),
                             0.6 if em == 'emote_dots' else 0.55)
                continue
            draw_chat(im, chat, items['ui_chat_tail'], items, tx, tip, w=w, h=h, emote=em, dx=dx, fnt=fnt_k)
    dr.text((8, y + 2), 'ui_chat_bubble 9-slice + ui_chat_tail at 80x56, 160x64 (tail -30), 240x80 (tail +50), 320x96 '
                        '(2 lines), 100x56 (typing dots), 160x60 (tail +40)', fill=INK, font=fnt_s)
    y += 300
    # FX strips
    dr.text((8, y + 4), 'animated FX strips (frames left -> right on alternating snow / plaza / sea)   + fx_snowball:',
            fill=INK, font=fnt_s)
    for j, bg in enumerate((SNOW, PLAZA, SEA)):
        b = Image.new('RGBA', (36, 36), bg)
        b.alpha_composite(items['fx_snowball'], (4, 4))
        im.alpha_composite(b, (620 + j * 40, y))
    y += 40
    for k, frames in sheets.items():
        fw, fh = frames[0].size
        x = 8
        for j, f in enumerate(frames):
            if x + fw > W - 120:
                break
            b = Image.new('RGBA', f.size, (SNOW, PLAZA, SEA)[j % 3])
            b.alpha_composite(f)
            im.alpha_composite(b, (x, y))
            x += fw + 2
        dr.text((W - 116, y + 4), k, fill=INK, font=fnt_s)
        y += fh + 10
    return im.crop((0, 0, W, y + 6))


SCENE_W, SCENE_H = 720, 400


def scene_frame(items, chat, sheets, meta, f, n_frames, fps):
    """One frame of the little village-life scene (game scale: world px x camera zoom 1.2)."""
    Z = 1.2
    w, h = int(SCENE_W / Z), int(SCENE_H / Z)
    im = ground(w, h, 'snow')
    pl = ground(w, h, 'plaza')
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).polygon([(w * 0.42, h), (w * 0.86, h * 0.36), (w + 400, h * 0.36), (w + 400, h)], fill=255)
    im.paste(pl, (0, 0), mask)
    t = f / fps
    fnt_k, has_ko = font(16)
    # characters (anchor positions in world px)
    A = (112, 238)   # talker (villager_b) facing SE
    B = (212, 222)   # listener (villager_a) facing SW, gets hit
    C = (345, 272)   # thrower (villager_c) facing SW
    D = (420, 196)   # bard (hunter stand-in) with music notes
    E = (528, 250)   # dozing villager with zzz
    S = (452, 312)   # a happy villager with hearts
    chars = [(A, 'villager_b', 'SE', False, -90), (B, 'villager_a', 'SE', True, -81), (C, 'villager_c', 'SE', True, -84),
             (D, 'hunter', 'S', False, -83), (E, 'villager_a', 'S', False, -81), (S, 'villager_b', 'SE', True, -90)]
    for (p, key, d, flip, ht) in sorted(chars, key=lambda c_: c_[0][1]):
        anim = 'happy' if (key == 'villager_b' and p == S and 1.4 < t < 2.6) else 'idle'
        fi = (f // 2) % (6 if anim == 'happy' else 4)
        draw_char(im, key, anim, d, fi, p[0], p[1], flip)
    # --- chat: A talks (typing dots -> text) to B
    def pop(t0, dur=0.2):
        u = (t - t0) / dur
        if u <= 0:
            return 0.0
        if u >= 1:
            return 1.0
        return F.ease_out(u, 3) * (1 + 0.18 * math.sin(math.pi * u))
    headA = (A[0], A[1] - 90 - 4)
    if t < 0.9:
        k = pop(0.0)
        if k > 0:
            sub = Image.new('RGBA', im.size, (0, 0, 0, 0))
            draw_chat(sub, chat, items['ui_chat_tail'], items, '', headA, w=80, h=56)
            tdy = EB.TAIL_JOIN - EB.CB_H + EB.chat_tail_tip()[1]
            dots = ['emote_dots_a0', 'emote_dots_a1', 'emote_dots_a2', 'emote_dots'][(f // 3) % 4]
            paste_anchor(sub, items[dots], headA[0], headA[1] - tdy - 56 + 8 + 15, (0.5, 0.5), 0.6)
            im.alpha_composite(sub)
    elif t < 3.0:
        txt = '오늘 생선 최고!' if has_ko else 'Fish is great!'
        draw_chat(im, chat, items['ui_chat_tail'], items, txt, headA, h=56, emote='emote_fish', fnt=fnt_k)
    # --- B: question -> laugh -> hit (splat) -> anger puff + anger emote
    headB = (B[0], B[1] - 81 - 4)
    t_throw, t_hit = 1.6, 2.05
    if t < 1.0:
        emote_in_bubble(im, items, 'emote_question', headB[0], headB[1], EMOTE_BUBBLE_SCALE, meta, pop(0.3))
    elif t < t_hit:
        emote_in_bubble(im, items, 'emote_laugh', headB[0], headB[1], EMOTE_BUBBLE_SCALE, meta, pop(1.0))
    elif t > t_hit + 0.8:      # after the huff puff: sulking anger bubble
        emote_in_bubble(im, items, 'emote_anger', headB[0], headB[1], EMOTE_BUBBLE_SCALE, meta, pop(t_hit + 0.8))
    # snowball from C's hand to B's face
    src = (C[0] - 12, C[1] - 48)
    dst = (B[0] + 4, B[1] - 58)
    if t_throw <= t < t_hit:
        u = (t - t_throw) / (t_hit - t_throw)
        x = src[0] + (dst[0] - src[0]) * u
        y = src[1] + (dst[1] - src[1]) * u - 60 * 4 * u * (1 - u)
        gy = C[1] + (B[1] - C[1]) * u
        sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((x - 8, gy - 3, x + 8, gy + 3), fill=(27, 40, 64, 50))
        im.alpha_composite(sh)
        paste_anchor(im, items['fx_snowball'], x, y, (0.5, 0.5))
    if t >= t_hit:
        fs = sheets['fx_snow_splat']
        k = int((t - t_hit) * 24)
        if k < len(fs):
            paste_anchor(im, fs[k], dst[0], dst[1], EF.SHEETS['fx_snow_splat'][6])
    if t >= t_hit + 0.15:
        fa = sheets['fx_anger_puff']
        k = int((t - t_hit - 0.15) * 18)
        if k < len(fa):
            paste_anchor(im, fa[k], headB[0], headB[1] + 4, EF.SHEETS['fx_anger_puff'][6])
    # C laughs after throwing
    headC = (C[0], C[1] - 84 - 4)
    if t >= t_hit + 0.1:
        emote_in_bubble(im, items, 'emote_laugh', headC[0], headC[1], EMOTE_BUBBLE_SCALE, meta, pop(t_hit + 0.1))
    elif t < t_throw:
        emote_in_bubble(im, items, 'emote_snowball', headC[0], headC[1], EMOTE_BUBBLE_SCALE, meta, pop(0.5))
    # bard: music loop
    mn = sheets['fx_music_notes']
    paste_anchor(im, mn[int(t * 12) % len(mn)], D[0] + 14, D[1] - 50, EF.SHEETS['fx_music_notes'][6])
    # dozing villager: zzz loop
    zz = sheets['fx_zzz']
    paste_anchor(im, zz[int(t * 8) % len(zz)], E[0] + 6, E[1] - 81, EF.SHEETS['fx_zzz'][6])
    # happy villager: hearts one-shot + sparkle emote
    headS = (S[0], S[1] - 90 - 4)
    if t >= 1.3:
        hs = sheets['fx_hearts']
        k = int((t - 1.3) * 16)
        if k < len(hs):
            paste_anchor(im, hs[k], headS[0], headS[1] + 6, EF.SHEETS['fx_hearts'][6])
    if 0.2 <= t < 1.3:
        emote_in_bubble(im, items, 'emote_love', headS[0], headS[1], EMOTE_BUBBLE_SCALE, meta, pop(0.2))
    elif t >= 2.4:
        swt = sheets['fx_sweat_drops']
        k = int((t - 2.4) * 18)
        if k < len(swt):
            paste_anchor(im, swt[k], headS[0], headS[1] + 6, EF.SHEETS['fx_sweat_drops'][6])
        emote_in_bubble(im, items, 'emote_sweat', headS[0], headS[1], EMOTE_BUBBLE_SCALE, meta, pop(2.4))
    return im.resize((SCENE_W, SCENE_H), Image.LANCZOS)


def write_scene(items, chat, sheets, meta, gif=True):
    fps = 12
    n = int(3.6 * fps)
    still = scene_frame(items, chat, sheets, meta, int(round(2.33 * fps)), n, fps)
    still.convert('RGB').save(os.path.join(PREV, 'emotes_scene.png'), optimize=True)
    if not gif:
        return
    frames = [scene_frame(items, chat, sheets, meta, f, n, fps).convert('RGB') for f in range(n)]
    pal = frames[int(2.25 * fps)].quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = [np.asarray(fr.quantize(palette=pal, dither=Image.Dither.NONE)) for fr in frames]
    palette = pal.getpalette()[:255 * 3] + [255, 0, 255]          # index 255 = transparent "unchanged" pixel
    out = []
    for k, a in enumerate(idx):
        if k:                                                     # delta frame: keep only changed pixels
            a = np.where(a == idx[k - 1], 255, a).astype(np.uint8)
        im = Image.fromarray(a, 'P')
        im.putpalette(palette)
        out.append(im)
    out[0].save(os.path.join(PREV, 'emotes_scene.gif'), save_all=True, append_images=out[1:], transparency=255,
                duration=int(round(1000 / fps)), loop=0, optimize=False, disposal=1)


# =========================================================================== main
def build(only=None, gifs=True):
    t0 = time.time()
    if only:
        os.makedirs(CACHE, exist_ok=True)
        imgs = {}
        for k, fn, _ in EA.EMOTES:
            if k in only:
                imgs[k] = EA.render(fn, S=64, ss=12, out=(256, 256))
        if {'ui_emote_bubble', 'ui_chat_bubble', 'ui_chat_tail'} & only:
            imgs['ui_emote_bubble'] = EB.emote_bubble()
            imgs['ui_chat_bubble'] = EB.chat_bubble()
            imgs['ui_chat_tail'] = EB.chat_tail()
        if imgs:
            cw = max(i.width for i in imgs.values()) + 8
            chh = max(i.height for i in imgs.values()) + 8
            sheet = Image.new('RGBA', (len(imgs) * cw, chh * 2), SNOW)
            for j, im in enumerate(imgs.values()):
                sheet.alpha_composite(im, (j * cw + 4, 4))
                b = Image.new('RGBA', (cw, chh), PLAZA)
                b.alpha_composite(im, (4, 4))
                sheet.alpha_composite(b, (j * cw, chh))
            sheet.save(os.path.join(CACHE, 'emotes_only.png'))
            print('  preview ->', os.path.join(CACHE, 'emotes_only.png'))
        sheets = build_sheets(only)
        for k, frames in sheets.items():
            d = EF.SHEETS[k]
            F.save_gif(frames, os.path.join(CACHE, k + '.gif'), d[4], hold=0 if d[5] == -1 else 6, anchor=d[6], scale=2)
            F.strip(frames).save(os.path.join(CACHE, k + '_strip.png'))
            print('  preview ->', os.path.join(CACHE, k + '.gif'))
        return

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    items, chat, meta = build_images()
    print('  built %d atlas images (%.1fs)' % (len(items), time.time() - t0), flush=True)
    sheets = build_sheets()
    # --- atlas (trimmed; anchors refer to the untrimmed frame like every other atlas in the game)
    order = EMOTE_KEYS + [k for k, _ in EA.DOTS_FRAMES] + ['ui_emote_bubble', 'ui_chat_tail', 'fx_snowball']
    sheet, atlas = pack_utils.pack_atlas([(k, items[k]) for k in order], max_width=512, padding=2)
    F.save_png(sheet, os.path.join(OUT, 'emotes.png'))
    atlas['meta']['image'] = 'emotes.png'
    with open(os.path.join(OUT, 'emotes.json'), 'w', encoding='utf-8') as f:
        json.dump(atlas, f, separators=(',', ':'))
    F.save_png(chat, os.path.join(OUT, 'ui_chat_bubble.png'))
    for k, frames in sheets.items():
        F.save_png(F.strip(frames), os.path.join(OUT, k + '.png'), quant=256, dither=0.6)
    manifest = make_manifest(items, chat, meta, atlas)
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print('  assets written (%.1fs)' % (time.time() - t0), flush=True)
    # --- previews
    for p in os.listdir(PREV):                        # drop stale previews of renamed keys
        if p.startswith('emotes_fx_') and p.endswith('.gif') and p[len('emotes_'):-4] not in EF.SHEETS:
            os.remove(os.path.join(PREV, p))
    preview_sheet(items, chat, sheets, meta).convert('RGB').save(os.path.join(PREV, 'emotes_sheet.png'), optimize=True)
    if gifs:
        for k, frames in sheets.items():
            d = EF.SHEETS[k]
            F.save_gif(frames, os.path.join(PREV, 'emotes_%s.gif' % k), d[4], hold=0 if d[5] == -1 else 8, anchor=d[6])
    write_scene(items, chat, sheets, meta, gif=gifs)
    print('Emotes done -> %s (%.1fs)' % (OUT, time.time() - t0))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', default='', help='comma separated keys -> scratch preview in tools/fx/_cache/emotes only')
    ap.add_argument('--no-gif', action='store_true', help='skip preview GIFs')
    a = ap.parse_args()
    only = set(k for k in a.only.split(',') if k) or None
    build(only, gifs=not a.no_gif)
    if not only:
        import emote_check
        sys.exit(emote_check.main())
