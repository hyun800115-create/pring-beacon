"""
emote_check.py - validates assets/emotes against docs/CONTRACT_VILLAGERS.md section C and CONTRACT §2.

Re-run (from anywhere; exit code 0 = all good, 1 = errors):
    python3 frost-village/tools/fx/emote_check.py
Checks:
  * assets/emotes/manifest.json parses; every path is relative to assets/ and the file exists
  * every key of section C resolves: 20 emote_* (kind emote, ~64x64), ui_emote_bubble, ui_chat_bubble,
    ui_chat_tail, fx_snowball (sprites -> atlas frame or image) and the 5 spritesheets
  * atlas frames lie inside the atlas PNG; sprite anim frames exist
  * spritesheets: PNG = frameWidth*frameCount x frameHeight, every frame non-empty, fps / repeat /
    anchor / blend NORMAL sane; fx_snow_splat has 8-10 frames; loops (repeat -1) wrap smoothly
  * emotes are not clipped by the frame edge and fill enough of it to read at 32-40 px
  * ui_chat_bubble nineSlice margins fit the image and allow 80x56 .. 320x96
  * ui_emote_bubble anchor sits on the tail tip; ui_chat_tail merges with the body (no seam)
  * payload of assets/emotes <= 1 MB; unreferenced files are reported
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, 'assets')
FOLDER = os.path.join(ASSETS, 'emotes')

EMOTES = ['emote_heart', 'emote_love', 'emote_laugh', 'emote_exclaim', 'emote_question', 'emote_anger', 'emote_sweat',
          'emote_music', 'emote_zzz', 'emote_idea', 'emote_sparkle', 'emote_cold', 'emote_tear', 'emote_dots',
          'emote_star', 'emote_fish', 'emote_bread', 'emote_wave', 'emote_thumbs', 'emote_snowball']
UI = ['ui_emote_bubble', 'ui_chat_bubble', 'ui_chat_tail']
FX_SPRITES = ['fx_snowball']
SHEETS = ['fx_snow_splat', 'fx_music_notes', 'fx_hearts', 'fx_anger_puff', 'fx_sweat_drops']
PAYLOAD_MAX = 1024 * 1024


def main():
    errors, warns, notes = [], [], []
    err, warn, note = errors.append, warns.append, notes.append
    mp = os.path.join(FOLDER, 'manifest.json')
    if not os.path.isfile(mp):
        print('ERROR: assets/emotes/manifest.json missing (run tools/fx/gen_emotes.py)')
        return 1
    with open(mp, encoding='utf-8') as f:
        m = json.load(f)
    referenced = {'emotes/manifest.json'}

    def path_ok(p):
        if not isinstance(p, str) or p.startswith('/') or '..' in p.split('/') or '\\' in p:
            err('bad path %r (must be relative to assets/)' % p)
            return None
        full = os.path.join(ASSETS, p)
        if not os.path.isfile(full):
            err('missing file %s' % p)
            return None
        referenced.add(p)
        return full

    # --- atlases / images
    atlases, images = {}, {}
    for a in m.get('atlases', []):
        png, js = path_ok(a.get('png')), path_ok(a.get('json'))
        if not png or not js:
            continue
        im = Image.open(png)
        with open(js, encoding='utf-8') as f:
            fr = json.load(f)['frames']
        for name, d in fr.items():
            r = d['frame']
            if r['x'] < 0 or r['y'] < 0 or r['x'] + r['w'] > im.width or r['y'] + r['h'] > im.height:
                err('atlas %s frame %s outside the PNG' % (a['key'], name))
            ss, so = d['spriteSourceSize'], d['sourceSize']
            if ss['x'] + ss['w'] > so['w'] or ss['y'] + ss['h'] > so['h']:
                err('atlas %s frame %s: trimmed box outside sourceSize' % (a['key'], name))
        atlases[a['key']] = (im.convert('RGBA'), fr)
    for a in m.get('images', []):
        png = path_ok(a.get('png'))
        if png:
            images[a['key']] = Image.open(png).convert('RGBA')

    def frame_img(atlas, name):
        im, fr = atlases[atlas]
        d = fr[name]
        r, ss, so = d['frame'], d['spriteSourceSize'], d['sourceSize']
        out = Image.new('RGBA', (so['w'], so['h']), (0, 0, 0, 0))
        out.paste(im.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])), (ss['x'], ss['y']))
        return out

    # --- sprites
    sprites = m.get('sprites', {})
    resolved = {}
    for k in EMOTES + UI + FX_SPRITES:
        s = sprites.get(k)
        if s is None:
            err('sprite %s missing' % k)
            continue
        anc = s.get('anchor')
        if not (isinstance(anc, list) and len(anc) == 2 and all(0 <= v <= 1 for v in anc)):
            err('sprite %s: bad anchor %r' % (k, anc))
        if 'atlas' in s:
            if s['atlas'] not in atlases or s.get('frame') not in atlases[s['atlas']][1]:
                err('sprite %s: frame %s not in atlas %s' % (k, s.get('frame'), s['atlas']))
                continue
            resolved[k] = frame_img(s['atlas'], s['frame'])
        elif 'image' in s:
            if s['image'] not in images:
                err('sprite %s: image %s not loaded' % (k, s['image']))
                continue
            resolved[k] = images[s['image']]
        else:
            err('sprite %s has neither atlas+frame nor image' % k)
        for an, ad in (s.get('anims') or {}).items():
            for fn in ad.get('frames', []):
                if fn not in atlases.get(s.get('atlas'), (None, {}))[1]:
                    err('sprite %s anim %s: frame %s missing' % (k, an, fn))
    for k in EMOTES:
        s = sprites.get(k, {})
        if s.get('kind') != 'emote':
            err('%s: kind must be "emote"' % k)
        im = resolved.get(k)
        if im is None:
            continue
        if not (56 <= im.width <= 72 and 56 <= im.height <= 72):
            warn('%s: frame %dx%d (contract ~64x64)' % (k, im.width, im.height))
        a = np.asarray(im)[..., 3]
        edge = max(a[0].max(), a[-1].max(), a[:, 0].max(), a[:, -1].max())
        if edge > 40:
            err('%s: art touches the frame edge (alpha %d) - clipped?' % (k, edge))
        ys, xs = np.where(a > 128)
        if xs.size == 0:
            err('%s: empty' % k)
            continue
        ext = max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
        if ext < 0.6 * im.width:
            warn('%s: solid part only %d px across (small at 32 px)' % (k, ext))
    # emote bubble: anchor on the tail tip
    eb = resolved.get('ui_emote_bubble')
    if eb is not None:
        ay = sprites['ui_emote_bubble']['anchor'][1] * eb.height
        col = np.asarray(eb)[:, eb.width // 2, 3]
        solid = np.where(col > 200)[0]
        if solid.size and abs((solid.max() + 1) - ay) > 2.0:
            err('ui_emote_bubble: anchor y %.1f is not at the tail tip (%d)' % (ay, solid.max() + 1))
        if not (76 <= eb.width <= 100):
            warn('ui_emote_bubble width %d (contract ~84)' % eb.width)
    # chat bubble 9-slice
    ns = m.get('nineSlice', {}).get('ui_chat_bubble')
    cb = resolved.get('ui_chat_bubble')
    if ns is None:
        err('nineSlice.ui_chat_bubble missing')
    elif cb is not None:
        l, r, t, b = ns['left'], ns['right'], ns['top'], ns['bottom']
        if l + r >= cb.width or t + b >= cb.height:
            err('ui_chat_bubble: margins exceed the image')
        if l + r > 80 or t + b > 56:
            err('ui_chat_bubble: margins %d+%d / %d+%d do not allow an 80x56 bubble' % (l, r, t, b))
        # 9-slice stretch must not change the middle: stretched middle columns/rows are uniform
        arr = np.asarray(cb).astype(np.int16)
        midc = arr[:, l:cb.width - r]
        if np.abs(midc - midc[:, :1]).max() > 3:
            warn('ui_chat_bubble: middle columns not uniform (horizontal stretch may show)')
        midr = arr[t:cb.height - b, :]
        if np.abs(np.diff(midr, axis=0)).max() > 6:
            warn('ui_chat_bubble: middle rows vary strongly (vertical stretch may show)')
    tail = resolved.get('ui_chat_tail')
    tdef = sprites.get('ui_chat_tail', {})
    if cb is not None and tail is not None and ns is not None:
        for w, h in ((80, 56), (160, 64), (320, 96)):
            body = _nine(cb, w, h, ns)
            can = Image.new('RGBA', (w, h + tail.height), (0, 0, 0, 0))
            can.alpha_composite(body, (0, 0))
            ty = h + int(tdef.get('attachY', -20))
            can.alpha_composite(tail, (w // 2 - tail.width // 2, ty))
            a = np.asarray(can)[..., 3]
            # the outline row just above the old body bottom must be continuous fill at the neck
            neck = a[h + int(tdef.get('attachY', -20)) + 8, w // 2 - 3:w // 2 + 4]
            if neck.min() < 250:
                err('ui_chat_tail at %dx%d: neck not solid (seam?)' % (w, h))
        tip = tdef.get('tip')
        if not tip:
            err('ui_chat_tail: missing tip')
    # --- spritesheets
    sheets = {s.get('key'): s for s in m.get('spritesheets', [])}
    for k in SHEETS + [k for k in sheets if k not in SHEETS]:
        s = sheets.get(k)
        if s is None:
            err('spritesheet %s missing' % k)
            continue
        png = path_ok(s.get('png'))
        if not png:
            continue
        im = Image.open(png).convert('RGBA')
        fw, fh, n = s.get('frameWidth'), s.get('frameHeight'), s.get('frameCount')
        if im.size != (fw * n, fh):
            err('%s: PNG %s != %dx%d frames of %dx%d' % (k, im.size, n, 1, fw, fh))
            continue
        if not (1 <= s.get('fps', 0) <= 60):
            err('%s: fps %r' % (k, s.get('fps')))
        if s.get('repeat') not in (0, -1):
            err('%s: repeat %r' % (k, s.get('repeat')))
        if s.get('blend') != 'NORMAL':
            err('%s: blend must be NORMAL (ADD vanishes on snow)' % k)
        anc = s.get('anchor')
        if not (isinstance(anc, list) and len(anc) == 2 and all(0 <= v <= 1 for v in anc)):
            err('%s: bad anchor' % k)
        a = np.asarray(im)[..., 3].astype(np.float32)
        frames = [a[:, i * fw:(i + 1) * fw] for i in range(n)]
        for i, fr in enumerate(frames):
            if fr.max() < 30 and not (s.get('repeat') == 0 and i == n - 1):
                err('%s: frame %d empty' % (k, i))
            if max(fr[0].max(), fr[-1].max(), fr[:, 0].max(), fr[:, -1].max()) > 60:
                warn('%s: frame %d touches the frame edge' % (k, i))
        if k == 'fx_snow_splat' and not (8 <= n <= 10):
            err('fx_snow_splat: %d frames (contract 8-10)' % n)
        if k == 'fx_music_notes' and s.get('repeat') != -1:
            err('fx_music_notes must loop')
        if k in ('fx_hearts', 'fx_anger_puff', 'fx_sweat_drops', 'fx_snow_splat') and s.get('repeat') != 0:
            err('%s must be one-shot (repeat 0)' % k)
        if s.get('repeat') == -1:
            steps = [np.abs(frames[i + 1] - frames[i]).mean() for i in range(n - 1)]
            wrap = np.abs(frames[0] - frames[-1]).mean()
            if wrap > 2.0 * max(np.mean(steps), 1e-3):
                warn('%s: loop seam (wrap diff %.2f vs mean step %.2f)' % (k, wrap, np.mean(steps)))
    # --- payload / unreferenced
    total = 0
    for root, _, files in os.walk(FOLDER):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), ASSETS).replace(os.sep, '/')
            total += os.path.getsize(os.path.join(root, fn))
            if rel not in referenced:
                warn('unreferenced file %s' % rel)
    note('payload assets/emotes = %.0f KB (limit %d KB)' % (total / 1024, PAYLOAD_MAX // 1024))
    if total > PAYLOAD_MAX:
        err('payload %.0f KB > 1 MB' % (total / 1024))
    note('%d sprites, %d spritesheets, %d atlas frames' % (len(sprites), len(sheets),
                                                         sum(len(v[1]) for v in atlases.values())))
    for e in errors:
        print('ERROR:', e)
    for w in warns:
        print('warn :', w)
    for n_ in notes:
        print('note :', n_)
    print('emote_check: %s (%d errors, %d warnings)' % ('OK' if not errors else 'FAILED', len(errors), len(warns)))
    return 1 if errors else 0


def _nine(img, w, h, m):
    l, r, t, b = m['left'], m['right'], m['top'], m['bottom']
    W, H = img.size
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for sx0, sx1, dx0, dx1 in ((0, l, 0, l), (l, W - r, l, w - r), (W - r, W, w - r, w)):
        for sy0, sy1, dy0, dy1 in ((0, t, 0, t), (t, H - b, t, h - b), (H - b, H, h - b, h)):
            if sx1 > sx0 and sy1 > sy0 and dx1 > dx0 and dy1 > dy0:
                out.alpha_composite(img.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR),
                                    (dx0, dy0))
    return out


if __name__ == '__main__':
    sys.exit(main())
