"""
vil_pack.py - rendered villager/pet frames -> game atlases + manifest + previews.

Run AFTER vil_render.py (plain python3 with numpy + Pillow + imagequant, no Blender):
    python3 tools/blender/vil_pack.py                     # everything in the cache
    python3 tools/blender/vil_pack.py --chars npc_bard    # one key (manifest keeps the others)
    python3 tools/blender/vil_pack.py --no-previews
    python3 tools/blender/vil_pack.py --colors 256        # palette size (default 192: keeps the folder < 10 MB)

What it does
  1. post-process each raw 128x128 frame with the SAME soft 1px ink outline as the
     base cast (char_pack.ink_outline)
  2. pack each key into assets/villagers/vil_<key>.png/.json (Phaser JSON hash,
     trimmed, anchor stays relative to the 128x128 frame), palettised with
     libimagequant (pip install imagequant)
  3. portraits -> assets/villagers/portrait_<key>.png
  4. assets/villagers/manifest.json (CONTRACT_VILLAGERS A)
  5. previews: docs/previews/vil_lineup.png, vil_<key>.png contact sheets,
     vil_<key>_<anim>.gif showcase animations
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
GAME = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)
import pack_utils              # noqa: E402
from char_pack import ink_outline   # noqa: E402
import vil_anim as va          # noqa: E402
import vil_build as vb         # noqa: E402
FV_CACHE = os.environ.get('FV_CACHE') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.cache', 'fv_cache'))  # 저장소/.cache/fv_cache

try:
    import imagequant
except ImportError:            # pragma: no cover
    imagequant = None

ASSETS = os.path.join(GAME, 'assets')
OUT = os.path.join(ASSETS, 'villagers')
PREV = os.path.join(GAME, 'docs', 'previews')
DEFAULT_CACHE = FV_CACHE + '/villagers'
DIRS = ['S', 'SE', 'E', 'NE', 'N']
MIRROR = {'SW': 'SE', 'W': 'E', 'NW': 'NE'}
BG = (201, 214, 232, 255)
LABEL = (43, 47, 58, 255)

SHOWCASE = [('npc_teen_girl', 'talk'), ('npc_uncle', 'laugh'), ('npc_kid_prankster', 'throw'),
            ('npc_kid_boy', 'hit'), ('npc_fashion', 'dance'), ('npc_uncle', 'angry'), ('npc_grandpa', 'angry'),
            ('npc_grandpa', 'sit'), ('npc_bard', 'perform'), ('npc_herbalist', 'surprised'),
            ('npc_kid_girl', 'happy'), ('npc_young_man', 'wave'), ('npc_aunt', 'sad'), ('npc_blacksmith', 'shiver'),
            ('pet_dog', 'run'), ('pet_dog', 'happy'), ('pet_cat', 'run'), ('pet_cat', 'loaf'),
            ('pet_penguin', 'run'), ('pet_penguin', 'happy'), ('npc_kid_girl', 'run')]


def quantize_save(img, path, colors=256, dither=0.6):
    if imagequant is not None:
        q = imagequant.quantize_pil_image(img, dithering_level=dither, max_quality=100, min_quality=0,
                                          max_colors=colors)
        q.save(path, optimize=True)
    else:
        img.save(path, optimize=True)


def load_meta(cache, key):
    p = os.path.join(cache, key, 'meta.json')
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def pack_key(cache, key, meta, colors):
    frames, processed, missing = [], {}, []
    for anim, info in meta['anims'].items():
        for d in info['dirs']:
            for i in range(info['frames']):
                p = os.path.join(cache, key, f'{anim}_{d}_{i}.png')
                if not os.path.exists(p):
                    missing.append(os.path.basename(p))
                    continue
                im = ink_outline(Image.open(p))
                name = f'{anim}_{d}_{i}'
                frames.append((name, im))
                processed[name] = im
    if missing:
        raise SystemExit(f'[{key}] missing {len(missing)} frames, e.g. {missing[:4]} - run vil_render.py')
    sheet, atlas = pack_utils.pack_atlas(frames, max_width=2048, trim=True, padding=2)
    png = os.path.join(OUT, f'vil_{key}.png')
    js = os.path.join(OUT, f'vil_{key}.json')
    pack_utils.save_atlas(sheet, atlas, png, js, quantize=False)
    quantize_save(sheet, png, colors)
    print(f'[{key}] atlas {sheet.size[0]}x{sheet.size[1]}  {os.path.getsize(png) / 1024:.0f} KB  '
          f'({len(frames)} frames)', flush=True)
    return processed


def head_top(im, anchor_y=104):
    bbox = im.getchannel('A').getbbox()
    return (bbox[1] - anchor_y) if bbox else -80


def manifest_entry(key, meta, processed, has_portrait):
    spec = vb.SPECS[key]
    anims = {}
    for anim, info in meta['anims'].items():
        e = {'frames': info['frames'], 'fps': info['fps'], 'repeat': info['repeat'], 'dirs': info['dirs']}
        if 'impactFrame' in info:
            e['impactFrame'] = info['impactFrame']
        if 'impactPoint' in info:
            e['impactPoint'] = info['impactPoint']
        anims[anim] = e
    ent = {
        'atlas': f'vil_{key}', 'frameSize': meta['frameSize'], 'anchor': meta['anchor'],
        'dirs': DIRS, 'mirror': MIRROR, 'frameName': '{anim}_{dir}_{i}',
        'kind': 'pet' if key in vb.PET_KEYS else 'villager',
        'role': spec['role'], 'name': {'ko': spec['name'][0], 'en': spec['name'][1]},
        'traits': spec['traits'], 'anims': anims,
    }
    if meta.get('carryPoint'):
        ent['carryPoint'] = meta['carryPoint']
    ent['headTop'] = head_top(processed['idle_S_0'])
    ent['shadow'] = meta.get('shadow', [46, 18])
    if has_portrait:
        ent['portrait'] = f'portrait_{key}'
    if 'seatOffset' in meta:
        ent['seatOffset'] = meta['seatOffset']
        ent['seatHeightPx'] = meta['seatHeightPx']
        ent['headTopSit'] = head_top(processed['sit_S_0'])
    return ent


# --------------------------------------------------------------------------- previews

def _cell(im, crop=(16, 0, 112, 128)):
    bg = Image.new('RGBA', (crop[2] - crop[0], crop[3] - crop[1]), (0, 0, 0, 0))
    bg.alpha_composite(im.crop(crop))
    return bg


def lineup(all_proc, path):
    keys = [k for k in vb.ALL_KEYS if k in all_proc]
    cw, z = 72, 2
    img = Image.new('RGBA', (len(keys) * cw * z, 128 * z + 40), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 100 * z, img.width, img.height], fill=(232, 238, 246, 255))
    for c, k in enumerate(keys):
        fr = all_proc[k]['idle_S_0'].crop((28, 0, 100, 128))
        sh = Image.new('RGBA', fr.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([36 - 18, 104 - 7, 36 + 18, 104 + 7], fill=(90, 110, 140, 70))
        cell = Image.alpha_composite(sh, fr).resize((cw * z, 128 * z), Image.LANCZOS)
        img.alpha_composite(cell, (c * cw * z, 0))
        nm = vb.SPECS[k]['name'][1]
        d.text((c * cw * z + 6, 128 * z + 4), k.replace('npc_', ''), fill=LABEL)
        d.text((c * cw * z + 6, 128 * z + 20), nm[:22], fill=(90, 96, 110, 255))
    img.convert('RGB').save(path, optimize=True)


def contact(key, meta, processed, path):
    rows = []
    for anim, info in meta['anims'].items():
        rows.append((anim, 'S', [processed[f'{anim}_S_{i}'] for i in range(info['frames'])]))
    rows.append(('dirs (idle)', '', [processed[f'idle_{d}_0'] for d in DIRS]))
    for anim in ('talk', 'throw', 'perform', 'sit'):
        if anim in meta['anims']:
            info = meta['anims'][anim]
            rows.append((anim, 'E', [processed[f'{anim}_E_{i}'] for i in range(info['frames'])]))
    cols = max(len(r[2]) for r in rows)
    lab, cw, ch = 92, 96, 120
    img = Image.new('RGBA', (lab + cols * cw, len(rows) * ch), BG)
    d = ImageDraw.Draw(img)
    for r, (name, dd, ims) in enumerate(rows):
        d.text((6, r * ch + ch // 2 - 6), f'{name} {dd}', fill=LABEL)
        info = meta['anims'].get(name, {})
        for c, im in enumerate(ims):
            x, y = lab + c * cw, r * ch
            img.alpha_composite(_cell(im, (16, 4, 112, 124)), (x, y))
            if info.get('impactFrame') == c and dd:
                d.rectangle([x + 1, y + 1, x + cw - 2, y + ch - 2], outline=(232, 67, 58, 255))
                ip = info.get('impactPoint', {}).get(dd)
                if ip:
                    cx, cy = x + 48 + ip[0], y + 100 + ip[1]
                    d.line([cx - 4, cy, cx + 4, cy], fill=(255, 200, 61, 255), width=2)
                    d.line([cx, cy - 4, cx, cy + 4], fill=(255, 200, 61, 255), width=2)
    quantize_save(img.convert('RGBA'), path, 256, dither=0.3)


def gif(key, meta, processed, anim, path, z=1.5):
    info = meta['anims'][anim]
    dirs = info['dirs'][:3]
    cw = 80
    frames = []
    n = info['frames']
    loops = 1 if info['repeat'] == 0 else 2
    seq = list(range(n)) * loops
    if info['repeat'] == 0:
        seq += [n - 1] * max(2, n // 2)
    for i in seq:
        canvas = Image.new('RGBA', (len(dirs) * cw, 120), BG)
        for c, d in enumerate(dirs):
            canvas.alpha_composite(processed[f'{anim}_{d}_{i}'].crop((24, 4, 104, 124)), (c * cw, 0))
        frames.append(canvas.resize((int(canvas.width * z), int(canvas.height * z)), Image.LANCZOS).convert('RGB'))
    pal = frames[0].quantize(colors=192, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=int(1000 / info['fps']), loop=0, optimize=True,
              disposal=1)


# --------------------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    cache, chars, previews, colors = DEFAULT_CACHE, None, True, 192
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--cache':
            cache = args[i + 1]; i += 2; continue
        if a == '--chars':
            chars = args[i + 1].split(','); i += 2; continue
        if a == '--colors':
            colors = int(args[i + 1]); i += 2; continue
        if a == '--no-previews':
            previews = False
        i += 1
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    man_path = os.path.join(OUT, 'manifest.json')
    old = {}
    if os.path.exists(man_path):
        with open(man_path, encoding='utf-8') as f:
            old = json.load(f)
    characters = dict(old.get('characters', {}))
    keys = [k for k in vb.ALL_KEYS if chars is None or k in chars]
    all_proc, metas = {}, {}
    for key in keys:
        meta = load_meta(cache, key)
        if meta is None:
            print(f'[{key}] no renders in cache, skipped')
            continue
        processed = pack_key(cache, key, meta, colors)
        all_proc[key], metas[key] = processed, meta
        pp = os.path.join(cache, key, 'portrait.png')
        has_p = os.path.exists(pp)
        if has_p:
            quantize_save(Image.open(pp).convert('RGBA'), os.path.join(OUT, f'portrait_{key}.png'), 256, 0.4)
        characters[key] = manifest_entry(key, meta, processed, has_p)
        if previews:
            contact(key, meta, processed, os.path.join(PREV, f'vil_{key}.png'))
            for k2, anim in SHOWCASE:
                if k2 == key and anim in meta['anims']:
                    gif(key, meta, processed, anim, os.path.join(PREV, f'vil_{key}_{anim}.gif'))
    present = [k for k in vb.ALL_KEYS if k in characters and os.path.exists(os.path.join(OUT, f'vil_{k}.png'))]
    man = {'version': 1,
           'notes': 'Villagers & pets (CONTRACT_VILLAGERS A). Frames {anim}_{dir}_{i}; each anim lists its dirs '
                    '(social anims S/SE/E only, mirror SW/W from SE/E). Expressions are baked per frame. '
                    'sit: anchor = seat-surface front-centre (0.45 m up); seatHeightPx = its height above the '
                    'ground for depth sorting. throw.impactPoint = snowball release point on impactFrame.',
           'atlases': [{'key': f'vil_{k}', 'png': f'villagers/vil_{k}.png', 'json': f'villagers/vil_{k}.json'}
                       for k in present],
           'images': [], 'sprites': {}, 'characters': {k: characters[k] for k in present}}
    for k in present:
        if os.path.exists(os.path.join(OUT, f'portrait_{k}.png')):
            man['images'].append({'key': f'portrait_{k}', 'png': f'villagers/portrait_{k}.png'})
            man['sprites'][f'portrait_{k}'] = {'image': f'portrait_{k}', 'anchor': [0.5, 0.5], 'kind': 'ui',
                                               'notes': '128x128 head-and-shoulders, facing S'}
    with open(man_path, 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    if previews and chars is None and all_proc:
        lineup(all_proc, os.path.join(PREV, 'vil_lineup.png'))
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f'manifest: {len(present)} keys; assets/villagers total {total / 1048576:.2f} MB')


if __name__ == '__main__':
    main()
