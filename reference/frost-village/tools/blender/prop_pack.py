"""
prop_pack.py - turn the raw prop renders (prop_render.py output cache) into
trimmed Phaser atlases + assets/props/manifest.json + preview sheets.

No Blender needed: any Python 3 with numpy + Pillow.
    python3 tools/blender/prop_pack.py [--cache DIR] [--no-previews] [--quantize]

Steps
  1. read every <key>.json sidecar + its frame PNGs from the cache
  2. shadow-caught frames: pack_utils.clean_alpha() (kills catcher haze), then
     tint the baked shadow a cool blue-violet so it reads like the reference on
     snow and on the terracotta plaza
  3. pack per atlas group (props_nature / props_buildings / props_decor /
     props_items), splitting a group into _2, _3 ... if it would exceed 2048x2048
  4. write assets/props/<atlas>.png/.json and assets/props/manifest.json
     (items get a measured carryScale; stations pass through fxPoints + anims.work)
  5. previews in docs/previews/: props_all.png, props_items.png, props_scene.png,
     props_stations_work.png + .gif (work loops), props_carry.png (player carrying
     each item at its carryScale; needs assets/characters)
"""
import json
import math
import os
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(GAME, 'tools'))
import pack_utils as pu  # noqa: E402

OUT = os.path.join(GAME, 'assets', 'props')
PREV = os.path.join(GAME, 'docs', 'previews')
ATLAS_ORDER = ['props_nature', 'props_buildings', 'props_decor', 'props_items']
MAX_SHEET = 2048
SHADOW_RGB = np.array([38, 46, 82], np.float32)     # cool blue-violet shadow tint
SHADOW_OPACITY = 0.85                                 # soften baked shadows a bit

KEY_ORDER = """tree_pine_a tree_pine_b tree_pine_snow tree_stump rock_ore rock_ore_b rock_rubble crop_wheat_0
crop_wheat_1 crop_wheat_2 crop_wheat_3 bush_snow snow_pile_a snow_pile_b ice_chunk station_grill station_sawmill
station_bakery station_smelter station_smokehouse market_counter trade_post worker_hut chief_lodge tent_a campfire
upgrade_bench fish_net dock_pier mine_entrance boat_small fence_log_x fence_log_y fence_post bench lamp_post barrel
crate firewood_pile signpost flag_pole hay_bale item_fish_raw item_fish_cooked item_log item_plank item_wheat
item_bread item_ore item_ingot item_meat_raw item_meat_cooked item_coin""".split()


def font(size):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              'C:/Windows/Fonts/arialbd.ttf', '/Library/Fonts/Arial Bold.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def tint_shadow(img):
    """Recolour the (black) baked shadow to a cool tint; leave the object alone."""
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    lum = a[..., :3].mean(-1)
    semi = a[..., 3] < 252
    w = np.clip(1.0 - lum / 70.0, 0.0, 1.0) * semi
    a[..., :3] = a[..., :3] * (1 - w[..., None]) + SHADOW_RGB * w[..., None]
    # soften pure-shadow pixels
    a[..., 3] = np.where(semi & (w > 0.5), a[..., 3] * SHADOW_OPACITY, a[..., 3])
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')


def tile_shadow(img, anchor_px, axis, h=0.07):
    """Seamless tiling for 1 m fence segments rendered with neighbour shadow casters:
    keep the shadow only around this segment's own metre along `axis`, using a
    partition-of-unity weight w(u) (w(u) + w(u-1) = 1) and a' = 1 - (1-a)^w so two
    overlapping segments composite back to exactly the continuous shadow."""
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    H, W = a.shape[:2]
    ax, ay = anchor_px
    px, py = np.meshgrid(np.arange(W) + 0.5 - ax, np.arange(H) + 0.5 - ay)
    gx = (px / 45.2548 + py / 22.6274) / 2.0       # ground point under the pixel (metres)
    gy = (px / 45.2548 - py / 22.6274) / 2.0
    u = np.abs(gx if axis == 'x' else gy)
    w = np.clip(0.5 + (0.5 - u) / (2 * h), 0.0, 1.0)
    alpha = a[..., 3] / 255.0
    lum = a[..., :3].mean(-1)
    m = np.clip(1.0 - lum / 70.0, 0.0, 1.0) * (a[..., 3] < 252)
    new = 1.0 - np.power(np.clip(1.0 - alpha, 1e-6, 1.0), w)
    alpha = alpha * (1 - m) + new * m
    a[..., 3] = np.clip(alpha * 255.0, 0, 255)
    return Image.fromarray(a.astype(np.uint8), 'RGBA')


def border_fade(img, width=10):
    """Fade alpha to 0 over the last `width` px of the frame so the soft baked
    shadow never ends in a hard frame edge (objects sit further inside)."""
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    H, W = a.shape[:2]
    rx = np.minimum(np.arange(W), np.arange(W)[::-1]) + 0.5
    ry = np.minimum(np.arange(H), np.arange(H)[::-1]) + 0.5
    ramp = np.clip(np.minimum(rx[None, :], ry[:, None]) / width, 0.0, 1.0)
    a[..., 3] *= ramp * ramp * (3 - 2 * ramp)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')


def load_frames(cache):
    metas = {}
    for fn in os.listdir(cache):
        if fn.endswith('.json'):
            with open(os.path.join(cache, fn)) as f:
                m = json.load(f)
            if 'key' in m and 'frames' in m:
                metas[m['key']] = m
    keys = [k for k in KEY_ORDER if k in metas] + sorted(k for k in metas if k not in KEY_ORDER)
    frames = {}
    for k in keys:
        m = metas[k]
        for n in m['frames']:
            im = Image.open(os.path.join(cache, n + '.png')).convert('RGBA')
            if m.get('shadow'):
                im = pu.clean_alpha(im, floor=10)
                if m.get('tileAxis'):
                    im = tile_shadow(im, m['anchorPx'], m['tileAxis'])
                im = border_fade(tint_shadow(im))
            else:
                im = pu.clean_alpha(im, floor=3)
            frames[n] = im
    return keys, metas, frames


def _chunks(items):
    """Split frame list so each chunk packs into <= MAX_SHEET (keeps a sprite's frames together)."""
    sheet, atlas = pu.pack_atlas(items, max_width=MAX_SHEET, trim=True, padding=2)
    if sheet.height <= MAX_SHEET or len(items) < 2:
        return [(items, sheet, atlas)]
    area = [im.width * im.height for _, im in items]
    half, acc, cut = sum(area) / 2, 0, 1
    for i, a in enumerate(area):
        acc += a
        if acc >= half:
            cut = i + 1
            break
    while 0 < cut < len(items) and '_work_' in items[cut][0]:
        cut += 1
    return _chunks(items[:cut]) + _chunks(items[cut:])


def pack_group(name, items):
    """items: list of (frame_name, img).  Returns list of (atlas_key, sheet, atlas)."""
    out = []
    for i, (its, sheet, atlas) in enumerate(_chunks(items)):
        out.append((name if i == 0 else '%s_%d' % (name, i + 1), sheet, atlas))
    return out


def save_png(sheet, atlas, key, quantize):
    png = os.path.join(OUT, key + '.png')
    js = os.path.join(OUT, key + '.json')
    pu.save_atlas(sheet, atlas, png, js, quantize=False)
    if quantize:
        q = quantize_rgba(sheet)
        q.save(png, optimize=True)
    return png, js


def quantize_rgba(img, colors=256):
    """Palette PNG with alpha.  Uses libimagequant via Pillow if present, else
    Pillow's fast octree (good enough for soft renders)."""
    try:
        return img.quantize(colors=colors, method=Image.Quantize.LIBIMAGEQUANT, dither=Image.Dither.FLOYDSTEINBERG)
    except Exception:
        return img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)


CARRY_TARGET_W = 31          # px: carried item width ~ 2/3 of a chibi head (heads are ~46 px wide)
CARRY_RANGE = (0.55, 0.65)


def carry_scale(img):
    """Recommended draw scale for hand-carried stacks (characters are chibi: at 1x an
    item is as wide as the head and a 4-stack hides the face).  Rounded to 0.05."""
    a = np.asarray(img)[..., 3] > 40
    cols = np.nonzero(a.any(0))[0]
    w = (cols[-1] - cols[0] + 1) if len(cols) else 48
    s = min(max(CARRY_TARGET_W / float(w), CARRY_RANGE[0]), CARRY_RANGE[1])
    return round(round(s / 0.05) * 0.05, 2)


def build_manifest(keys, metas, frame_atlas, atlas_keys, frames=None):
    sprites = {}
    for k in keys:
        m = metas[k]
        s = {'atlas': frame_atlas[k], 'frame': k, 'anchor': m['anchor'], 'kind': m['kind']}
        if 'footprint' in m:
            s['footprint'] = m['footprint']
        if 'anims' in m:
            fr = m['anims']['work']['frames']
            atl = {frame_atlas[f] for f in fr}
            s['anims'] = {'work': dict(m['anims']['work'])}
            if len(atl) > 1 or frame_atlas[fr[0]] != s['atlas']:
                s['anims']['work']['atlas'] = frame_atlas[fr[0]]
        if 'stackStep' in m:
            s['stackStep'] = m['stackStep']
            s['icon'] = True
            if frames is not None:
                s['carryScale'] = carry_scale(frames[k])
        s['frameSize'] = m['frameSize']
        s['topPx'] = m['topPx']
        for extra in ('front', 'footprintM', 'thicknessM', 'tileAxis', 'fxPoints'):
            if extra in m:
                s[extra] = m[extra]
        if m.get('notes'):
            s['notes'] = m['notes']
        sprites[k] = s
    man = {
        'version': 1,
        'generator': 'tools/blender/prop_render.py + prop_pack.py',
        'conventions': {
            'ppu': 64,
            'anchor': 'normalised [ax, ay] of the full untrimmed frame = world origin = footprint centre '
                      '(items: bottom centre of the item).',
            'footprint': 'screen-px bounding size [w, h] of the ground footprint (diamond for boxes, ellipse for '
                         'round things); centred on the anchor.',
            'topPx': 'visual height above the anchor in px (for bubbles / progress rings).',
            'front': '-Y = faces screen down-left (SW); S = faces the camera (screen down).',
            'stackStep': 'items: px between stacked copies at scale 1 (draw copy i at y - i*stackStep).',
            'shadows': 'props/buildings have a baked soft shadow falling screen down-right; items have none.',
            'carryScale': 'items: recommended scale for stacks carried in a character\'s hands (chibi bodies; at 1x '
                          'an item is head-wide). Draw carried copy i at scale carryScale and y - i*stackStep*'
                          'carryScale. Ground/pad towers and UI icons stay at scale 1 (stackStep is native).',
            'fxPoints': 'stations: px offsets [dx, dy] from the anchor where game FX can be spawned '
                        '(fire = flame/heat source, smoke = just above the chimney/vent top, blade, dust, crucible).',
            'work': 'stations: the idle frame is the resting state (embers banked, no smoke); anims.work is a seamless '
                    '4-frame loop with flames, smoke puffs and moving parts baked in. All frames share frameSize and '
                    'anchor, so swap frames in place.',
        },
        'atlases': [{'key': a, 'png': 'props/%s.png' % a, 'json': 'props/%s.json' % a} for a in atlas_keys],
        'sprites': sprites,
    }
    return man


# --------------------------------------------------------------------------- previews

def shelf_preview(entries, out, bg=(150, 168, 190), max_w=1800, label_size=13, pad=14, scale=1.0, title=None):
    """entries: list of (label, img).  Shelf layout with labels under each image."""
    f = font(label_size)
    tf = font(22)
    cells = []
    for lab, im in entries:
        bb = im.getbbox() or (0, 0, 1, 1)
        im2 = im.crop(bb)
        if scale != 1.0:
            im2 = im2.resize((max(1, int(im2.width * scale)), max(1, int(im2.height * scale))), Image.LANCZOS)
        tw = int(f.getlength(lab)) + 4
        cells.append((lab, im2, max(im2.width, tw) + pad, im2.height + label_size + pad + 6))
    rows = []
    row, x, h = [], 0, 0
    for c in cells:
        if x + c[2] > max_w and row:
            rows.append((row, h))
            row, x, h = [], 0, 0
        row.append(c)
        x += c[2]
        h = max(h, c[3])
    if row:
        rows.append((row, h))
    top = 40 if title else 0
    W = max_w
    H = top + sum(h for _, h in rows) + pad
    sheet = Image.new('RGBA', (W, H), bg + (255,))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((pad, 8), title, fill=(25, 30, 40), font=tf)
    y = top
    for row, h in rows:
        x = pad
        for lab, im, cw, ch in row:
            iy = y + (h - label_size - 6 - pad) - im.height
            sheet.alpha_composite(im, (x + (cw - pad - im.width) // 2, max(y, iy)))
            d.text((x + (cw - pad - int(f.getlength(lab))) // 2, y + h - label_size - pad + 2), lab,
                   fill=(20, 24, 32), font=f)
            x += cw
        y += h
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.convert('RGB').save(out, optimize=True)
    return out


def iso(x, y, ox, oy):
    """world metres -> screen px (relative to an origin pixel)."""
    return ox + (x + y) * 45.2548, oy + (x - y) * 22.6274


def char_frames():
    """Optional: untrimmed character frames from assets/characters (read-only), for the
    scale check in the scene preview.  Returns {char_key: (img_fn(frame_name), anchor_px)}."""
    base = os.path.join(GAME, 'assets')
    mp = os.path.join(base, 'characters', 'manifest.json')
    out = {}
    if not os.path.exists(mp):
        return out
    try:
        man = json.load(open(mp, encoding='utf-8'))
        atl = {a['key']: a for a in man.get('atlases', [])}
        for ck, c in man.get('characters', {}).items():
            a = atl.get(c.get('atlas'))
            if not a:
                continue
            sheet = Image.open(os.path.join(base, a['png'])).convert('RGBA')
            fr = json.load(open(os.path.join(base, a['json'])))['frames']
            fw, fh = c.get('frameSize', [128, 128])
            anc = (c['anchor'][0] * fw, c['anchor'][1] * fh)

            def get(name, sheet=sheet, fr=fr, fw=fw, fh=fh):
                f = fr.get(name)
                if not f:
                    return None
                r = f['frame']
                crop = sheet.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
                im = Image.new('RGBA', (f['sourceSize']['w'], f['sourceSize']['h']), (0, 0, 0, 0))
                im.paste(crop, (f['spriteSourceSize']['x'], f['spriteSourceSize']['y']))
                return im
            out[ck] = (get, anc)
    except Exception as e:      # preview only - never fail the pack
        print('note: character preview skipped:', e)
    return out


def scene_preview(metas, frames, out):
    W, H = 1600, 1110
    img = Image.new('RGBA', (W, H), (244, 247, 251, 255))
    d = ImageDraw.Draw(img)
    ox, oy = 760, 560
    # sea band at the top (world -X/+Y side) and shoreline foam
    sea = [iso(x, y, ox, oy) for x, y in [(-30, -8), (-30, 30), (-9.5, 30), (-9.5, -8)]]
    d.polygon(sea, fill=(47, 134, 201, 255))
    deep = [iso(x, y, ox, oy) for x, y in [(-30, -8), (-30, 30), (-12, 30), (-12, -8)]]
    d.polygon(deep, fill=(31, 95, 168, 255))
    d.line([iso(-9.5, -8, ox, oy), iso(-9.5, 30, ox, oy)], fill=(230, 242, 250, 255), width=7)
    # terracotta plaza diamond with plank lines
    plaza = [iso(x, y, ox, oy) for x, y in [(-6, -5), (-6, 4), (3.5, 4), (3.5, -5)]]
    d.polygon(plaza, fill=(217, 160, 138, 255))
    for i in range(0, 20):
        x = -6 + i * 0.5
        d.line([iso(x, -5, ox, oy), iso(x, 4, ox, oy)], fill=(200, 143, 120, 255), width=1)
    # farm/mine dirt patch on the right
    dirt = [iso(x, y, ox, oy) for x, y in [(-2, 5.5), (-2, 10.5), (3.2, 10.5), (3.2, 5.5)]]
    d.polygon(dirt, fill=(176, 140, 112, 255))

    placed = []

    def put(key, x, y, frame=None):
        m = metas.get(key)
        if not m:
            return
        if frame is None and 'anims' in m:          # show stations mid-work (flames / smoke)
            frame = m['anims']['work']['frames'][1]
        im = frames[frame or key]
        ax, ay = m['anchorPx']
        sx, sy = iso(x, y, ox, oy)
        placed.append((sy, key, im, int(round(sx - ax)), int(round(sy - ay))))

    # forest (left)
    for x, y, k in [(-7.5, -8.8, 'tree_pine_a'), (-5.6, -9.6, 'tree_pine_b'), (-3.9, -8.9, 'tree_pine_snow'),
                    (-8.2, -6.6, 'tree_pine_b'), (-2.2, -9.9, 'tree_pine_a'), (-6.0, -7.3, 'tree_stump'),
                    (-0.6, -8.6, 'tree_pine_a'), (1.4, -10.6, 'tree_pine_snow'), (-4.6, -11.4, 'tree_pine_a'),
                    (0.6, -12.2, 'tree_pine_b'), (-1.6, -11.6, 'tree_stump')]:
        put(k, x, y)
    # mine (bottom-left)
    put('mine_entrance', 8.6, -9.4)
    put('rock_ore', 5.0, -8.0)
    put('rock_ore_b', 6.6, -6.4)
    put('rock_rubble', 4.0, -6.6)
    put('rock_ore', 7.4, -4.8)
    put('station_smelter', 4.6, -3.6)
    # shoreline: net, pier, boat
    put('fish_net', -8.2, -1.4)
    put('dock_pier', -11.2, 2.4)
    put('boat_small', -12.0, 5.5)
    put('ice_chunk', -9.4, 7.0)
    # plaza: stations, counter, trade post
    put('station_grill', -3.6, -1.6)
    put('market_counter', 0.6, -3.0)
    put('trade_post', 0.8, 2.0)
    put('station_sawmill', -4.0, 2.4)
    put('upgrade_bench', -1.4, 5.4)
    put('bench', 2.4, -1.4)
    put('lamp_post', -5.4, -4.4)
    put('lamp_post', 2.8, -5.4)
    put('barrel', 2.8, -4.0)
    put('crate', 3.0, 0.2)
    put('signpost', 1.4, -6.4)
    put('flag_pole', -7.0, 4.6)
    # farm (top-right) with bakery
    for i, st in enumerate([3, 3, 2, 1, 0, 3]):
        put('crop_wheat_%d' % st, -1.4 + (i % 3) * 1.5, 8.6 + (i // 3) * 1.5)
    put('station_bakery', 3.0, 6.4)
    put('hay_bale', 2.6, 11.6)
    put('chief_lodge', -5.4, 10.4)
    # fences: a run along +X and a run along +Y meeting at a corner post
    for i in range(7):
        put('fence_log_x', 4.4 + i * 1.0, 4.4)
    for i in range(6):
        put('fence_log_y', 4.0, 4.8 + i * 1.0)
    put('fence_post', 4.0, 4.4)
    put('fence_post', 11.0, 4.4)
    # workers' corner + hunting camp (bottom-right)
    put('worker_hut', 7.6, 8.2)
    put('firewood_pile', 9.4, 6.4)
    put('station_smokehouse', 8.2, 0.6)
    put('tent_a', 11.6, 1.6)
    put('campfire', 10.2, -1.0)
    put('bush_snow', 12.4, -1.8)
    put('bush_snow', 9.0, -3.0)
    put('snow_pile_a', 12.4, -4.6)
    put('snow_pile_b', 10.6, -5.4)
    # 20-high cooked fish tower on a pad next to the grill (like the reference)
    fm = metas.get('item_fish_cooked')
    tower = []
    if fm:
        tx, ty = -1.7, -0.9
        sx, sy = iso(tx, ty, ox, oy)
        pad = [iso(tx + a, ty + b, ox, oy) for a, b in [(-0.55, -0.55), (-0.55, 0.55), (0.55, 0.55), (0.55, -0.55)]]
        d.polygon(pad, fill=(200, 140, 118, 255), outline=(255, 255, 255, 255))
        d.line(pad + [pad[0]], fill=(255, 255, 255, 255), width=4)
        im = frames['item_fish_cooked']
        ax, ay = fm['anchorPx']
        for i in range(20):
            tower.append((sy, 'tower', im, int(round(sx - ax)), int(round(sy - ay - i * fm['stackStep']))))
    # characters for scale: real sprites from assets/characters when present, else a 1.45 m capsule
    chars = char_frames()
    shadow_layer = []
    spots = [('player', 'idle_S_0', -2.4, 0.9)]
    for i, ck in enumerate(['villager_a', 'villager_b', 'villager_c', 'villager_a', 'villager_b']):
        spots.append((ck, 'idle_E_0', -0.2 - 0.9 * i, -4.3))
    for ck, fname, x, y in spots:
        if ck in chars:
            get, (ax, ay) = chars[ck]
            im = get(fname) or get('idle_S_0')
            if im is None:
                continue
            sx, sy = iso(x, y, ox, oy)
            shadow_layer.append((sx, sy))
            placed.append((sy, ck, im, int(round(sx - ax)), int(round(sy - ay))))
    cap = None
    if 'player' not in chars:
        cap = iso(-2.4, 0.9, ox, oy)
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for sx, sy in shadow_layer:
        sd.ellipse([sx - 23, sy - 9, sx + 23, sy + 9], fill=(38, 46, 82, 70))
    img.alpha_composite(sh)
    for sy_, key, im, px, py in sorted(placed + tower, key=lambda t: t[0]):
        img.alpha_composite(im, (px, py))
    d = ImageDraw.Draw(img)
    f = font(14)
    if cap:
        cx, cy = cap
        hpx = 1.45 * 0.866 * 64
        d.rounded_rectangle([cx - 17, cy - hpx, cx + 17, cy], radius=16, fill=(242, 240, 234, 255),
                            outline=(80, 80, 90, 255), width=2)
        d.text((cx + 22, cy - hpx), '1.45 m\n(character\nscale)', fill=(30, 30, 40), font=f)
    d.rectangle([0, H - 40, W, H], fill=(31, 95, 168, 255))
    d.text((16, H - 33), 'Frost Village props - mock layout at 1x (anchors + relative scale check, PPU 64; '
           'characters from assets/characters when present)', fill=(255, 255, 255), font=font(20))
    img.convert('RGB').save(out, optimize=True)
    return out


def char_carry_points(ck):
    try:
        man = json.load(open(os.path.join(GAME, 'assets', 'characters', 'manifest.json'), encoding='utf-8'))
        return man['characters'][ck]['carryPoint']
    except Exception:
        return {'S': [0, -31, False], 'SE': [12, -34, False], 'E': [17, -40, False], 'NE': [12, -46, True],
                'N': [0, -48, True]}


def carry_preview(keys, metas, frames, out, n=4, ck='player'):
    """Player carry_idle in 5 dirs holding an n-stack of each item at its carryScale
    (+ a native-scale column for comparison)."""
    chars = char_frames()
    if ck not in chars:
        return None
    get, (cax, cay) = chars[ck]
    cps = char_carry_points(ck)
    items = [k for k in keys if metas[k]['kind'] == 'item']
    dirs = ['S', 'SE', 'E', 'NE', 'N']
    cw, ch = 110, 150
    W, H = 150 + cw * (len(dirs) + 1), 50 + ch * len(items)
    img = Image.new('RGBA', (W, H), (217, 160, 138, 255))
    d = ImageDraw.Draw(img)
    f = font(13)
    d.text((10, 8), '%s carry_idle with a %d-stack at carryScale (last column: scale 1 for comparison)' % (ck, n),
           fill=(20, 24, 32), font=font(16))
    for j, dn in enumerate(dirs + ['S']):
        d.text((150 + j * cw + 40, 30), dn if j < len(dirs) else 'S @1x', fill=(20, 24, 32), font=f)
    for r, k in enumerate(items):
        m = metas[k]
        cs = carry_scale(frames[k])
        d.text((10, 50 + r * ch + 60), '%s\ncarryScale %.2f' % (k.replace('item_', ''), cs), fill=(20, 24, 32), font=f)
        for j, dn in enumerate(dirs + ['S']):
            sc = cs if j < len(dirs) else 1.0
            body = get('carry_idle_%s_0' % dn)
            if body is None:
                continue
            fx, fy = 150 + j * cw + cw // 2, 50 + r * ch + 135        # feet (anchor) position
            dx, dy, behind = cps.get(dn, [0, -34, False])
            it = frames[k]
            if sc != 1.0:
                it = it.resize((max(1, round(it.width * sc)), max(1, round(it.height * sc))), Image.LANCZOS)
            iax, iay = m['anchorPx'][0] * sc, m['anchorPx'][1] * sc
            stack = [(it, int(round(fx + dx - iax)), int(round(fy + dy - iay - i * m['stackStep'] * sc)))
                     for i in range(n)]
            sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse([fx - 23, fy - 9, fx + 23, fy + 9], fill=(38, 46, 82, 70))
            img.alpha_composite(sh)
            layers = [(body, fx - int(cax), fy - int(cay))]
            layers = (stack + layers) if behind else (layers + stack)
            for im, x, y in layers:
                img.alpha_composite(im, (x, y))
    img.convert('RGB').save(out, optimize=True)
    return out


def stations_gif(keys, metas, frames, out, bg=(217, 160, 138)):
    """Animated GIF: every station's work loop side by side (idle frame shown first, labelled)."""
    st = [k for k in keys if 'anims' in metas[k]]
    if not st:
        return None
    gap = 10
    W = sum(metas[k]['frameSize'][0] for k in st) + gap * (len(st) + 1)
    H = max(metas[k]['frameSize'][1] for k in st) + 40
    fps = 8
    out_frames = []

    def compose(idx):
        im = Image.new('RGBA', (W, H), bg + (255,))
        d = ImageDraw.Draw(im)
        x = gap
        for k in st:
            fw, fh = metas[k]['frameSize']
            n = k if idx is None else metas[k]['anims']['work']['frames'][idx % 4]
            im.alpha_composite(frames[n], (x, H - 30 - fh))
            d.text((x + 10, H - 24), k.replace('station_', '') + (' (idle)' if idx is None else ''),
                   fill=(20, 24, 32), font=font(14))
            x += fw + gap
        return im.convert('RGB')
    out_frames.append(compose(None))
    for rep in range(6):
        for i in range(4):
            out_frames.append(compose(i))
    durs = [900] + [int(1000 / fps)] * (len(out_frames) - 1)
    pal = out_frames[2].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in out_frames]
    q[0].save(out, save_all=True, append_images=q[1:], duration=durs, loop=0, optimize=False, disposal=1)
    return out


def items_preview(keys, metas, frames, out):
    items = [k for k in keys if metas[k]['kind'] == 'item']
    f = font(13)
    cw, ch = 150, 300
    W = cw * len(items) + 20
    H = ch + 40
    img = Image.new('RGBA', (W, H), (150, 168, 190, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 8), 'Items: 2x render | 1x | 48px & 32px icon | 6-stack at 1x', fill=(20, 24, 32), font=font(16))
    for i, k in enumerate(items):
        im = frames[k]
        m = metas[k]
        x0 = 10 + i * cw
        big = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
        img.alpha_composite(big, (x0 + (cw - big.width) // 2, 30))
        img.alpha_composite(im, (x0 + 4, 180))
        bb = im.getbbox()
        icon = im.crop(bb)
        for j, sz in enumerate((48, 32)):
            s = sz / max(icon.width, icon.height)
            ic = icon.resize((max(1, int(icon.width * s)), max(1, int(icon.height * s))), Image.LANCZOS)
            img.alpha_composite(ic, (x0 + 80 + j * 4, 176 + j * 52 if j else 176))
        # 6-stack
        ax, ay = m['anchorPx']
        base_y = 300
        for s_ in range(6):
            img.alpha_composite(im, (x0 + 4, base_y - ay - s_ * m['stackStep'] - 10))
        d.text((x0 + 4, H - 22), k.replace('item_', ''), fill=(20, 24, 32), font=f)
        d.text((x0 + 80, 280), 'step %d' % m['stackStep'], fill=(20, 24, 32), font=f)
    img.convert('RGB').save(out, optimize=True)
    return out


def main():
    args = sys.argv[1:]
    cache = os.path.join(tempfile.gettempdir(), 'fv_cache', 'props')
    if '--cache' in args:
        cache = args[args.index('--cache') + 1]
    quantize = '--quantize' in args          # off by default: octree palettes band the soft shadows
    keys, metas, frames = load_frames(cache)
    os.makedirs(OUT, exist_ok=True)
    # remove stale atlases we own
    for fn in os.listdir(OUT):
        if fn.startswith('props_') and (fn.endswith('.png') or fn.endswith('.json')):
            os.remove(os.path.join(OUT, fn))
    groups = {}
    for k in keys:
        groups.setdefault(metas[k]['atlas'], []).extend((n, frames[n]) for n in metas[k]['frames'])
    frame_atlas = {}
    atlas_keys = []
    total = 0
    for g in ATLAS_ORDER + sorted(set(groups) - set(ATLAS_ORDER)):
        if g not in groups:
            continue
        for akey, sheet, atlas in pack_group(g, groups[g]):
            png, js = save_png(sheet, atlas, akey, quantize)
            for n in atlas['frames']:
                frame_atlas[n] = akey
            atlas_keys.append(akey)
            sz = os.path.getsize(png)
            total += sz + os.path.getsize(js)
            print('%-18s %4dx%-4d %3d frames %7.1f KB' % (akey, sheet.width, sheet.height, len(atlas['frames']),
                                                         sz / 1024))
    man = build_manifest(keys, metas, frame_atlas, atlas_keys, frames)
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    print('sprites: %d   total payload %.2f MB' % (len(man['sprites']), total / 1024 / 1024))
    if '--no-previews' not in args:
        ents = [(k, frames[k]) for k in keys]
        shelf_preview(ents, os.path.join(PREV, 'props_all.png'),
                      title='Frost Village - props / stations / buildings / decor / items (1x, PPU 64, idle frames)')
        items_preview(keys, metas, frames, os.path.join(PREV, 'props_items.png'))
        scene_preview(metas, frames, os.path.join(PREV, 'props_scene.png'))
        # station work loops strip
        work = []
        for k in keys:
            if 'anims' in metas[k]:
                for n in [k] + metas[k]['anims']['work']['frames']:
                    work.append((n.replace('station_', ''), frames[n]))
        if work:
            shelf_preview(work, os.path.join(PREV, 'props_stations_work.png'), title='Station idle + work frames')
            stations_gif(keys, metas, frames, os.path.join(PREV, 'props_stations_work.gif'))
        carry_preview(keys, metas, frames, os.path.join(PREV, 'props_carry.png'))
        print('previews written to', PREV)


if __name__ == '__main__':
    main()
