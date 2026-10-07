"""
char_pack.py - turn rendered character frames into game atlases + manifest + previews.

Run AFTER char_render.py (plain Python 3 with numpy + Pillow, no Blender needed):
    python3 tools/blender/char_pack.py                 # everything found in the cache
    python3 tools/blender/char_pack.py --chars player  # just one character (manifest keeps others)
    python3 tools/blender/char_pack.py --no-previews   # skip docs/previews images
    python3 tools/blender/char_pack.py --cache /tmp/fv_cache/characters

What it does
  1. post-process every raw 128x128 frame: soft 1px ink outline (matches the
     reference's inked look and separates white parkas from snow)
  2. pack each character into assets/characters/char_<key>.png/.json
     (Phaser JSON-hash, trimmed; anchor stays relative to the 128x128 frame)
  3. copy portraits -> assets/characters/portrait_<key>.png and
     portrait_player_512.png
  4. write assets/characters/manifest.json (CONTRACT section 2/3)
  5. previews in docs/previews: char_lineup.png, char_<key>.png contact sheets,
     char_<key>_<anim>.gif animations
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
GAME = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import pack_utils  # noqa: E402

ASSETS = os.path.join(GAME, 'assets')
OUT = os.path.join(ASSETS, 'characters')
PREV = os.path.join(GAME, 'docs', 'previews')
DEFAULT_CACHE = '/tmp/fv_cache/characters'

ORDER = ['player', 'fisherman', 'lumberjack', 'farmer', 'miner', 'hunter',
         'villager_a', 'villager_b', 'villager_c', 'deer', 'boar']
DIRS = ['S', 'SE', 'E', 'NE', 'N']
MIRROR = {'SW': 'SE', 'W': 'E', 'NW': 'NE'}
LOOP_ANIMS = {'idle', 'walk', 'carry_idle', 'carry_walk', 'chop', 'mine', 'harvest', 'work', 'happy'}
INK = (52, 40, 48)
# Atlases are palettised with libimagequant (pip install imagequant): 256 colours
# + light dithering is visually lossless here and ~3.5x smaller.  Pillow's own
# octree quantiser bands on the hair/parkas, so without imagequant we keep RGBA.
QUANTIZE_DEFAULT = True
try:
    import imagequant
except ImportError:          # pragma: no cover
    imagequant = None


# --------------------------------------------------------------------------- post

def _shift(a, dy, dx):
    H, W = a.shape[:2]
    pad = np.pad(a, ((1, 1), (1, 1)) + ((0, 0),) * (a.ndim - 2))
    return pad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]


def ink_outline(im, color=INK, strength=0.85, mix=0.70):
    """1px soft outline outside the silhouette.  The line colour is the ink
    colour mixed with the neighbouring sprite colour (coloured line art)."""
    a = np.asarray(im.convert('RGBA')).astype(np.float32) / 255.0
    al = a[..., 3]
    rgb = a[..., :3]
    orth = np.max(np.stack([_shift(al, dy, dx) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))]), 0)
    diag = np.max(np.stack([_shift(al, dy, dx) for dy, dx in ((-1, -1), (-1, 1), (1, -1), (1, 1))]), 0)
    ring = np.clip(np.maximum(orth, diag * 0.6), 0, 1) * strength
    prem = rgb * al[..., None]
    s = sum(_shift(prem, dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    sa = sum(_shift(al, dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    avg = s / np.maximum(sa, 1e-4)[..., None]
    line = avg * (1 - mix) + np.array(color, np.float32) / 255.0 * mix
    out_a = al + ring * (1 - al)
    out_rgb = (rgb * al[..., None] + line * (ring * (1 - al))[..., None]) / np.maximum(out_a, 1e-4)[..., None]
    res = np.concatenate([out_rgb, out_a[..., None]], -1)
    res[out_a < 1.5 / 255.0] = 0
    return Image.fromarray((np.clip(res, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')


# --------------------------------------------------------------------------- pack

def load_meta(cache, key):
    p = os.path.join(cache, key, 'meta.json')
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def frame_path(cache, key, anim, d, i):
    return os.path.join(cache, key, f'{anim}_{d}_{i}.png')


def pack_character(cache, key, meta, quantize):
    frames = []
    processed = {}
    missing = []
    for anim, info in meta['anims'].items():
        for d in DIRS:
            for i in range(info['frames']):
                p = frame_path(cache, key, anim, d, i)
                if not os.path.exists(p):
                    missing.append(os.path.basename(p))
                    continue
                im = ink_outline(Image.open(p))
                name = f'{anim}_{d}_{i}'
                frames.append((name, im))
                processed[name] = im
    extra = os.path.join(cache, key, 'projectile_arrow.png')
    if key == 'hunter' and os.path.exists(extra):
        frames.append(('projectile_arrow', ink_outline(Image.open(extra))))
    if missing:
        raise SystemExit(f'[{key}] missing {len(missing)} frames, e.g. {missing[:4]} - run char_render.py')
    sheet, atlas = pack_utils.pack_atlas(frames, max_width=2048, trim=True, padding=2)
    png = os.path.join(OUT, f'char_{key}.png')
    js = os.path.join(OUT, f'char_{key}.json')
    pack_utils.save_atlas(sheet, atlas, png, js, quantize=False)
    if quantize and imagequant is not None:
        q = imagequant.quantize_pil_image(sheet, dithering_level=0.6, max_quality=100, min_quality=0,
                                          max_colors=256)
        q.save(png, optimize=True)
    elif quantize:
        print('  (imagequant not installed -> atlas kept as RGBA; pip install imagequant)')
    print(f'[{key}] atlas {sheet.size[0]}x{sheet.size[1]}  {os.path.getsize(png) / 1024:.0f} KB  '
          f'({len(frames)} frames)')
    return processed


def head_top(im, anchor_y=104):
    bbox = im.getchannel('A').getbbox()
    return (bbox[1] - anchor_y) if bbox else -80


def manifest_entry(key, meta, processed, has_portrait):
    anims = {}
    for anim, info in meta['anims'].items():
        e = {'frames': info['frames'], 'fps': info['fps'], 'repeat': -1 if anim in LOOP_ANIMS else 0}
        if 'impactFrame' in info:
            e['impactFrame'] = info['impactFrame']
        if 'impactPoint' in info:
            e['impactPoint'] = info['impactPoint']
        anims[anim] = e
    ent = {
        'atlas': f'char_{key}', 'frameSize': meta['frameSize'], 'anchor': meta['anchor'],
        'dirs': DIRS, 'mirror': MIRROR, 'frameName': '{anim}_{dir}_{i}',
        'anims': anims,
    }
    if meta.get('carryPoint'):
        ent['carryPoint'] = meta['carryPoint']
    ent['shadow'] = meta.get('shadow', [46, 18])
    if has_portrait:
        ent['portrait'] = f'portrait_{key}'
    ent['kind'] = meta['kind']
    ent['headTop'] = head_top(processed.get('idle_S_0'))
    return ent


# --------------------------------------------------------------------------- previews

BG = (201, 214, 232, 255)        # snow-shadow blue (CONTRACT palette #C9D6E8)
LABEL = (43, 47, 58, 255)


def lineup(processed_all, path):
    keys = [k for k in ORDER if k in processed_all]
    cell_w, z = 96, 2
    img = Image.new('RGBA', (len(keys) * cell_w * z, 128 * z + 26), BG)
    # soft snowy ground band
    d = ImageDraw.Draw(img)
    d.rectangle([0, 100 * z, img.width, img.height], fill=(232, 238, 246, 255))
    for c, k in enumerate(keys):
        fr = processed_all[k]['idle_S_0'].crop((16, 0, 112, 128))
        sh = Image.new('RGBA', fr.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([48 - 22, 104 - 8, 48 + 22, 104 + 8], fill=(90, 110, 140, 70))
        cell = Image.alpha_composite(sh, fr).resize((cell_w * z, 128 * z), Image.LANCZOS)
        img.alpha_composite(cell, (c * cell_w * z, 0))
        d.text((c * cell_w * z + 8, 128 * z + 6), k, fill=LABEL)
    img.convert('RGB').save(path, optimize=True)


def contact(key, meta, processed, path):
    rows = [(anim, [processed[f'{anim}_S_{i}'] for i in range(info['frames'])])
            for anim, info in meta['anims'].items()]
    rows.append(('dirs', [processed[f'idle_{d}_0'] for d in DIRS]))
    cols = max(len(r[1]) for r in rows)
    lab = 84
    img = Image.new('RGBA', (lab + cols * 128, len(rows) * 128), BG)
    d = ImageDraw.Draw(img)
    cp = meta.get('carryPoint', {})
    for r, (name, ims) in enumerate(rows):
        d.text((6, r * 128 + 58), name, fill=LABEL)
        info = meta['anims'].get(name, {})
        for c, im in enumerate(ims):
            x, y = lab + c * 128, r * 128
            img.alpha_composite(im, (x, y))
            if info.get('impactFrame') == c:
                d.rectangle([x + 2, y + 2, x + 125, y + 125], outline=(232, 67, 58, 255))
                ip = info.get('impactPoint', {}).get('S')
                if ip:
                    cx, cy = x + 64 + ip[0], y + 104 + ip[1]
                    d.line([cx - 4, cy, cx + 4, cy], fill=(255, 200, 61, 255), width=2)
                    d.line([cx, cy - 4, cx, cy + 4], fill=(255, 200, 61, 255), width=2)
            if name.startswith('carry') and 'S' in cp:
                cx, cy = 64 + cp['S'][0], 104 + cp['S'][1]
                d.ellipse([x + cx - 2, y + cy - 2, x + cx + 2, y + cy + 2], fill=(232, 67, 58, 255))
            if name == 'dirs' and DIRS[c] in cp and 'carry_idle' in meta['anims']:
                cx, cy = 64 + cp[DIRS[c]][0], 104 + cp[DIRS[c]][1]
                d.ellipse([x + cx - 2, y + cy - 2, x + cx + 2, y + cy + 2],
                          fill=(61, 124, 201, 255) if cp[DIRS[c]][2] else (232, 67, 58, 255))
    img.convert('RGB').save(path, optimize=True)


def gif(key, meta, processed, anim, path, dirs=('S', 'SE', 'E', 'NE', 'N'), z=1.5):
    info = meta['anims'][anim]
    cw = 96
    frames = []
    for i in range(info['frames']):
        canvas = Image.new('RGBA', (len(dirs) * cw, 128), BG)
        for c, d in enumerate(dirs):
            canvas.alpha_composite(processed[f'{anim}_{d}_{i}'].crop((16, 0, 112, 128)), (c * cw, 0))
        frames.append(canvas.resize((int(canvas.width * z), int(canvas.height * z)), Image.LANCZOS).convert('RGB'))
    pal = frames[0].quantize(colors=160, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=int(1000 / info['fps']), loop=0,
              optimize=True, disposal=1)


def _item_sprite(key='item_fish_cooked'):
    """Full-frame item image + (anchor px, stackStep) from the props manifest, or a
    plain salmon disc if the props are not built yet (preview only)."""
    try:
        with open(os.path.join(ASSETS, 'props', 'manifest.json')) as f:
            pm = json.load(f)
        sp = pm['sprites'][key]
        at = next(a for a in pm['atlases'] if a['key'] == sp['atlas'])
        with open(os.path.join(ASSETS, at['json'])) as f:
            fr = json.load(f)['frames'][sp['frame']]
        sheet = Image.open(os.path.join(ASSETS, at['png'])).convert('RGBA')
        f2, ss, src = fr['frame'], fr['spriteSourceSize'], fr['sourceSize']
        full = Image.new('RGBA', (src['w'], src['h']), (0, 0, 0, 0))
        full.paste(sheet.crop((f2['x'], f2['y'], f2['x'] + f2['w'], f2['y'] + f2['h'])), (ss['x'], ss['y']))
        return full, (sp['anchor'][0] * src['w'], sp['anchor'][1] * src['h']), sp.get('stackStep', 10)
    except Exception:
        im = Image.new('RGBA', (40, 30), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([4, 8, 36, 24], fill=(240, 138, 93, 255), outline=(150, 70, 50, 255))
        return im, (20, 20), 8


def carry_check(processed_all, metas, path, n_items=4):
    """Every carrying character in all 8 directions with an item stack drawn at
    carryPoint exactly the way the game should do it (SW/W/NW = flipX of
    SE/E/NE with dx negated; behind=true -> stack drawn under the body)."""
    item, (iax, iay), step = _item_sprite()
    keys = [k for k in ORDER if k in processed_all and metas[k].get('carryPoint')]
    dirs8 = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW']
    cw, chh, top = 96, 150, 22
    img = Image.new('RGBA', (90 + len(dirs8) * cw, top + len(keys) * chh), BG)
    d = ImageDraw.Draw(img)
    for c, dd in enumerate(dirs8):
        d.text((90 + c * cw + 40, 6), dd, fill=LABEL)
    for r, k in enumerate(keys):
        meta = metas[k]
        anim = 'carry_idle' if 'carry_idle' in meta['anims'] else 'carry_walk'
        d.text((6, top + r * chh + 70), k, fill=LABEL)
        for c, dd in enumerate(dirs8):
            src = MIRROR.get(dd, dd)
            fr = processed_all[k][f'{anim}_{src}_0']
            dx, dy, behind = meta['carryPoint'][src]
            if dd in MIRROR:
                fr = fr.transpose(Image.FLIP_LEFT_RIGHT)
                dx = -dx
            cell = Image.new('RGBA', (128, 150), (0, 0, 0, 0))
            ax, ay = 64, 104 + 22
            stack = Image.new('RGBA', cell.size, (0, 0, 0, 0))
            for n in range(n_items):
                stack.alpha_composite(item, (int(round(ax + dx - iax)), int(round(ay + dy - iay - n * step))))
            sh = Image.new('RGBA', cell.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse([ax - 23, ay - 9, ax + 23, ay + 9], fill=(90, 110, 140, 70))
            cell.alpha_composite(sh)
            if behind:
                cell.alpha_composite(stack)
            cell.alpha_composite(fr, (0, 22))
            if not behind:
                cell.alpha_composite(stack)
            img.alpha_composite(cell.crop((16, 0, 112, 150)), (90 + c * cw, top + r * chh))
    img.convert('RGB').save(path, optimize=True)


# --------------------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    cache = DEFAULT_CACHE
    chars = None
    previews = True
    quantize = QUANTIZE_DEFAULT
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--cache':
            cache = args[i + 1]; i += 2; continue
        if a == '--chars':
            chars = args[i + 1].split(','); i += 2; continue
        if a == '--no-previews':
            previews = False
        if a == '--quantize':
            quantize = True
        i += 1
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    man_path = os.path.join(OUT, 'manifest.json')
    old = {}
    if os.path.exists(man_path):
        with open(man_path) as f:
            old = json.load(f)
    keys = [k for k in ORDER if (chars is None or k in chars)]
    characters = dict(old.get('characters', {}))
    processed_all = {}
    metas = {}
    for key in keys:
        meta = load_meta(cache, key)
        if meta is None:
            print(f'[{key}] no renders in cache, skipped')
            continue
        processed = pack_character(cache, key, meta, quantize)
        processed_all[key] = processed
        metas[key] = meta
        ppath = os.path.join(cache, key, 'portrait.png')
        has_portrait = os.path.exists(ppath)
        if has_portrait:
            Image.open(ppath).convert('RGBA').save(os.path.join(OUT, f'portrait_{key}.png'), optimize=True)
        characters[key] = manifest_entry(key, meta, processed, has_portrait)
        if previews:
            contact(key, meta, processed, os.path.join(PREV, f'char_{key}.png'))
            gif(key, meta, processed, 'walk', os.path.join(PREV, f'char_{key}_walk.gif'))
            second = {'player': 'chop', 'deer': 'idle', 'boar': 'idle'}.get(
                key, 'happy' if key.startswith('villager') else 'work')
            gif(key, meta, processed, second, os.path.join(PREV, f'char_{key}_{second}.gif'))
            if key == 'player':
                for extra in ('mine', 'harvest', 'carry_walk'):
                    gif(key, meta, processed, extra, os.path.join(PREV, f'char_{key}_{extra}.gif'))
    ka = os.path.join(cache, 'player', 'keyart_512.png')
    if os.path.exists(ka):
        Image.open(ka).convert('RGBA').save(os.path.join(OUT, 'portrait_player_512.png'), optimize=True)

    # ---- manifest (keys always in contract order)
    present = [k for k in ORDER if k in characters
               and os.path.exists(os.path.join(OUT, f'char_{k}.png'))]
    man = {'version': 1,
           'atlases': [{'key': f'char_{k}', 'png': f'characters/char_{k}.png',
                        'json': f'characters/char_{k}.json'} for k in present],
           'images': [], 'sprites': {}, 'characters': {k: characters[k] for k in present}}
    for k in present:
        if os.path.exists(os.path.join(OUT, f'portrait_{k}.png')):
            man['images'].append({'key': f'portrait_{k}', 'png': f'characters/portrait_{k}.png'})
            man['sprites'][f'portrait_{k}'] = {'image': f'portrait_{k}', 'anchor': [0.5, 0.5],
                                               'kind': 'ui', 'notes': '128x128 head-and-shoulders, facing S'}
    if 'hunter' in present:
        with open(os.path.join(OUT, 'char_hunter.json')) as f:
            if 'projectile_arrow' in json.load(f)['frames']:
                man['sprites']['projectile_arrow'] = {
                    'atlas': 'char_hunter', 'frame': 'projectile_arrow', 'anchor': [0.5, 0.5], 'kind': 'fx',
                    'notes': 'hunter arrow in flight; points screen-right, rotate to the flight angle; '
                             'spawn at characters.hunter.anims.work.impactPoint on impactFrame'}
    if os.path.exists(os.path.join(OUT, 'portrait_player_512.png')):
        man['images'].append({'key': 'portrait_player_512', 'png': 'characters/portrait_player_512.png'})
        man['sprites']['portrait_player_512'] = {'image': 'portrait_player_512', 'anchor': [0.5, 0.5],
                                                 'kind': 'ui', 'notes': '512x512 key art: the chief waving'}
    with open(man_path, 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    if previews and processed_all and (chars is None):
        lineup(processed_all, os.path.join(PREV, 'char_lineup.png'))
        carry_check(processed_all, metas, os.path.join(PREV, 'char_carry_check.png'))
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f'manifest: {len(present)} characters; assets/characters total {total / 1024 / 1024:.2f} MB')


if __name__ == '__main__':
    main()
