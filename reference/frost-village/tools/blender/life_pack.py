"""
life_pack.py - turn the raw village-life renders (life_render.py cache) into ONE trimmed Phaser
atlas `life_props` + assets/life_props/manifest.json + previews.

No Blender needed: python3 with numpy + Pillow (+ optional `imagequant` for palette PNGs).
    python3 tools/blender/life_pack.py [--cache DIR] [--quantize auto|on|off] [--no-previews]

Steps
  1. read every <build>.json sidecar + frame PNGs from the cache (default <tmp>/fv_cache/life_props)
  2. shadow-caught frames get the SAME post as the base props (prop_pack.clean_alpha +
     tint_shadow (cool blue-violet) + border_fade); the lantern bulbs get a soft warm halo
     whose strength follows the twinkle loop
  3. pack all frames into one atlas (<= 2048 x 2048); --quantize auto palettises it with
     libimagequant only when the RGBA payload would exceed the 1.5 MB budget
  4. write assets/life_props/{life_props.png,.json,manifest.json}: sprites with anchor,
     footprint, kind, frameSize, topPx and the interaction points (seatPoints / seatDirs /
     seatDepth, hidePoints, workPoints, doorPoint, pullPoint, fxPoints.bulbs, per-frame swing
     seatPoints), the `bench_seats` override for the existing bench, and `layouts`
  5. previews: docs/previews/life_props_all.png, life_scene.png (with real characters for
     scale; seated villagers from assets/villagers or the villager render cache when present),
     life_anims.gif (snowman stages, swing, lantern twinkle)
"""
import json
import math
import os
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(GAME, 'tools'))
sys.path.insert(0, HERE)
import pack_utils as pu  # noqa: E402
import prop_pack as pp   # noqa: E402  (read-only reuse: tint_shadow, border_fade, shelf_preview, font, iso)

ASSETS = os.path.join(GAME, 'assets')
OUT = os.path.join(ASSETS, 'life_props')
PREV = os.path.join(GAME, 'docs', 'previews')
ATLAS = 'life_props'
MAX_SHEET = 2048
BUDGET_MB = 1.5

ORDER = ['snowman', 'snowball_pile', 'snow_fort', 'log_seat', 'log_seat_x', 'log_seat_y', 'sled', 'dog_house',
         'picnic_table', 'lantern_string', 'kids_swing', 'ice_rink', 'clothesline', 'igloo', 'notice_board',
         'music_stand']

# campfire circle around the EXISTING props `campfire` (world metres from the campfire anchor; the
# logs are 1.6 m long, seats 0.8 m apart - this spacing keeps neighbouring sitters' heads apart)
CAMP_D, CAMP_S = 1.7, 0.4
CAMP_LAYOUT = [('log_seat', (-CAMP_D * math.sqrt(0.5), CAMP_D * math.sqrt(0.5))),
               ('log_seat_y', (-CAMP_D, -CAMP_S)),
               ('log_seat_x', (CAMP_S, CAMP_D))]


def world_px(x, y):
    """ground metres -> screen px offset (PPU 64, 2:1 iso)."""
    return [int(round((x + y) * 45.2548)), int(round((x - y) * 22.6274))]


# --------------------------------------------------------------------------- load + post

def load(cache):
    builds, bench = {}, None
    for fn in sorted(os.listdir(cache)):
        if not fn.endswith('.json'):
            continue
        m = json.load(open(os.path.join(cache, fn)))
        if m.get('build') == 'bench_seats':
            bench = m
        elif 'build' in m and 'frames' in m:
            builds[m['build']] = m
    keys = [k for k in ORDER if k in builds] + sorted(k for k in builds if k not in ORDER)
    frames = {}
    for k in keys:
        m = builds[k]
        for n in m['frames']:
            im = Image.open(os.path.join(cache, n + '.png')).convert('RGBA')
            if m.get('shadow'):
                im = pp.border_fade(pp.tint_shadow(pu.clean_alpha(im, floor=10)))
            else:
                im = pu.clean_alpha(im, floor=3)
            if m.get('glow'):
                im = add_glow(im, m, n)
            frames[n] = im
    return keys, builds, bench, frames


def add_glow(im, m, frame, radius=11.0, peak=0.5):
    """Warm halo around each bulb (bulb colour sampled from the render), drawn UNDER the sprite so
    the bulb stays crisp; strength follows the twinkle level of that bulb in this frame."""
    levels = m['glow'].get(frame)
    pts = m['framePoints'].get(frame, {}).get('bulb', [])
    if not levels or not pts:
        return im
    W, H = im.size
    ax, ay = m['anchorPx']
    src = np.asarray(im).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    col_acc = np.zeros((H, W, 3), np.float32)
    w_acc = np.zeros((H, W), np.float32)
    keep = np.ones((H, W), np.float32)              # product of (1 - a_i) -> alpha = 1 - keep
    for (dx, dy), lv in zip(pts, levels):
        cx, cy = ax + dx, ay + dy
        x0, y0 = int(round(cx)), int(round(cy))
        patch = src[max(0, y0 - 2):y0 + 3, max(0, x0 - 2):x0 + 3]
        col = patch[..., :3].reshape(-1, 3).mean(0) if patch.size else np.array([255, 200, 90], np.float32)
        col = np.clip(col * 1.05 + np.array([12, 0, -25], np.float32), 0, 255)
        r = radius * (0.6 + 0.4 * lv)
        a = peak * (0.2 + 0.8 * lv) * np.exp(-2.6 * (((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)))
        col_acc += col[None, None, :] * a[..., None]
        w_acc += a
        keep *= (1.0 - a)
    rgb = np.clip(col_acc / np.maximum(w_acc, 1e-6)[..., None], 0, 255)
    alpha = np.clip((1.0 - keep) * 255.0, 0, 255)
    out = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), 'RGBA')
    out.alpha_composite(im)
    return out


# --------------------------------------------------------------------------- manifest

POINT_FIELDS = {'seat': 'seatPoints', 'hide': 'hidePoints', 'work': 'workPoints', 'gather': 'gatherPoints'}
DIR_FIELDS = {'seat': 'seatDirs', 'hide': 'hideDirs', 'work': 'workDirs', 'gather': 'gatherDirs'}


def sprite_entries(k, m):
    out = {}
    for skey, sd in m['sprites'].items():
        fr = sd['frame']
        s = {'atlas': ATLAS, 'frame': fr, 'anchor': m['anchor'], 'kind': m['kind']}
        if 'footprint' in m:
            s['footprint'] = m['footprint']
        s['frameSize'] = m['frameSize']
        s['topPx'] = m['topPx'][fr]
        for f in ('footprintM', 'front', 'seatDepth', 'seatHeightM', 'tableHeightM', 'wallHeightM'):
            if f in m:
                s[f] = m[f]
        pts = m['framePoints'].get(fr, {})
        dirs = m['frameDirs'].get(fr, {})
        for kind, field in POINT_FIELDS.items():
            if kind in pts:
                s[field] = pts[kind]
                if kind in dirs:
                    s[DIR_FIELDS[kind]] = dirs[kind]
        if 'door' in pts:
            s['doorPoint'] = pts['door'][0]
            if 'door' in dirs:
                s['doorDir'] = dirs['door'][0]
        if 'pull' in pts:
            s['pullPoint'] = pts['pull'][0]
        if 'perform' in pts:
            s['performPoint'] = pts['perform'][0]
            if 'perform' in dirs:
                s['performDir'] = dirs['perform'][0]
        if 'bulb' in pts:
            s['fxPoints'] = {'bulbs': pts['bulb']}
        if 'stage' in sd:
            s['stage'] = sd['stage']
            s['stages'] = [n for n in m['sprites']]
        if 'anims' in sd:
            s['anims'] = {}
            for an, a in sd['anims'].items():
                e = {'frames': a['frames'], 'fps': a['fps'], 'repeat': a['repeat']}
                if any('seat' in m['framePoints'].get(f, {}) for f in a['frames']):
                    e['seatPoints'] = [m['framePoints'][f]['seat'][0] for f in a['frames']]
                s['anims'][an] = e
        if m.get('notes'):
            s['notes'] = m['notes']
        out[skey] = s
    return out


def bench_entry(bench):
    if not bench:
        return None
    e = {'of': 'bench', 'kind': 'seats'}
    for f in ('seatPoints', 'seatDirs', 'petPoints', 'seatDepth', 'notes'):
        e[f] = bench[f]
    e['seatHeightM'] = bench['measured']['seatTopM']
    return e


def layouts():
    items = [{'sprite': s, 'offset': world_px(x, y), 'worldM': [round(x, 3), round(y, 3)]} for s, (x, y) in
             CAMP_LAYOUT]
    return {'campfire_circle': {
        'center': 'campfire', 'items': items,
        'notes': 'Three log seats in a U behind the existing props campfire: place each sprite anchor at '
                 'campfire anchor + offset (px). All 6 sitters face the fire (log_seat: S, log_seat_y: SE, '
                 'log_seat_x: SW = sit_SE flipped). Leave the camera side open for the bard / dancers.'}}


def build_manifest(keys, builds, bench, atlas_size):
    sprites = {}
    for k in keys:
        sprites.update(sprite_entries(k, builds[k]))
    b = bench_entry(bench)
    if b:
        sprites['bench_seats'] = b
    return {
        'version': 1,
        'generator': 'tools/blender/life_render.py + life_pack.py (CONTRACT_VILLAGERS.md section B)',
        'conventions': {
            'ppu': 64,
            'anchor': 'normalised [ax, ay] of the full untrimmed frame = world origin = footprint centre.',
            'footprint': 'screen-px bounding size [w, h] of the ground footprint, centred on the anchor.',
            'topPx': 'visual height above the anchor in px (bubbles / emotes).',
            'shadows': 'baked soft cool shadow falling screen down-right (same as assets/props).',
            'points': 'every *Point(s) value is a px offset [dx, dy] from the sprite anchor (unscaled sprite).',
            'seatPoints': 'where a SITTING villager\'s anchor goes (villager sit anims put the anchor at the '
                          'front-centre of a 0.45 m seat). seatDirs[i] = facing of seat i (S, SE, SW...; SW/W = '
                          'the SE/E frames flipped).',
            'seatDepth': '"front": draw the sitter just above the prop (sitter depth = prop depth + 1; '
                         'benches, logs, swing); with several sitters on one prop add a tiny bias by seat dy '
                         '(larger dy = nearer = drawn later). "behind": normal anchor-y sort already puts the '
                         'sitter behind the prop (picnic table: the table top hides the lap). bench_seats.petPoints: '
                         'draw the pet BELOW the bench sitters (it sits further back on the seat).',
            'gatherPoints': 'notice_board: anchors where villagers stand to read / chat (gatherDirs = facing).',
            'performPoint': 'music_stand: where the bard stands behind the stand (perform_S).',
            'doorPoint': 'dog_house / igloo: ground point in front of the door (pet / kid anchor).',
            'pullPoint': 'sled: the rope loop on the snow.',
            'hidePoints': 'snow_fort: character anchors behind the wall (normal y-sort hides their legs).',
            'workPoints': 'snowman: where kids stand while building (workDirs = facing).',
            'stages': 'snowman_0..3 share frameSize + anchor: swap the frame in place as it is built.',
            'anims': 'frame lists inside atlas life_props (names may repeat); the swing anim also lists a '
                     'seatPoint per frame so a sitting kid can ride along.',
            'bench_seats': 'override entry for the existing props bench (not an image): {of, seatPoints, '
                           'seatDirs, petPoints, seatDepth}.',
            'layouts': 'suggested arrangements (offsets in px from the named centre sprite anchor).',
        },
        'atlases': [{'key': ATLAS, 'png': 'life_props/%s.png' % ATLAS, 'json': 'life_props/%s.json' % ATLAS}],
        'sprites': sprites,
        'layouts': layouts(),
    }


# --------------------------------------------------------------------------- pack

def pack(frames, quantize):
    items = list(frames.items())
    sheet, atlas = pu.pack_atlas(items, max_width=MAX_SHEET, trim=True, padding=2)
    if sheet.width > MAX_SHEET or sheet.height > MAX_SHEET:
        raise SystemExit('atlas %dx%d exceeds %d' % (sheet.width, sheet.height, MAX_SHEET))
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, ATLAS + '.png')
    js = os.path.join(OUT, ATLAS + '.json')
    pu.save_atlas(sheet, atlas, png, js, quantize=False)
    size = os.path.getsize(png) + os.path.getsize(js)
    do_q = quantize == 'on' or (quantize == 'auto' and size / 1048576.0 > BUDGET_MB * 0.9)
    if do_q:
        try:
            import imagequant
            q = imagequant.quantize_pil_image(sheet, dithering_level=0.6, max_quality=100, min_quality=0,
                                              max_colors=256)
            q.save(png, optimize=True)
            print('  palettised with libimagequant (RGBA would be %.2f MB)' % (size / 1048576.0))
        except ImportError:
            print('  imagequant not installed -> kept RGBA (pip install imagequant)')
    return sheet, atlas, png, js


# --------------------------------------------------------------------------- characters for previews

def char_lib():
    """Standing characters from assets/characters (read-only) -> {key: (get(frame), anchor_px)}."""
    try:
        return pp.char_frames()
    except Exception as e:          # preview only
        print('note: characters unavailable:', e)
        return {}


def _atlas_getter(base, a):
    sheet = Image.open(os.path.join(base, a['png'])).convert('RGBA')
    fr = json.load(open(os.path.join(base, a['json'])))['frames']

    def get(name):
        f = fr.get(name)
        if not f:
            return None
        r = f['frame']
        crop = sheet.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
        im = Image.new('RGBA', (f['sourceSize']['w'], f['sourceSize']['h']), (0, 0, 0, 0))
        im.paste(crop, (f['spriteSourceSize']['x'], f['spriteSourceSize']['y']))
        return im
    return get


def villager_lib():
    """New villagers for seated / throwing poses: assets/villagers atlases if they exist, else the
    villager agent's raw render caches.  Returns get(key, anim, dir, i) -> (img, anchor_px, flipped, src)."""
    srcs = []
    vm = os.path.join(ASSETS, 'villagers', 'manifest.json')
    if os.path.exists(vm):
        try:
            man = json.load(open(vm, encoding='utf-8'))
            atl = {a['key']: a for a in man.get('atlases', [])}
            chars = {}
            for ck, c in man.get('characters', {}).items():
                if c.get('atlas') in atl:
                    fw, fh = c.get('frameSize', [128, 128])
                    chars[ck] = (_atlas_getter(ASSETS, atl[c['atlas']]), (c['anchor'][0] * fw, c['anchor'][1] * fh))
            srcs.append(('assets/villagers', lambda k, n: (chars[k][0](n), chars[k][1]) if k in chars else (None, None)))
        except Exception as e:
            print('note: assets/villagers unreadable:', e)
    for d in ('villagers', 'villagers_test'):
        root = os.path.join(tempfile.gettempdir(), 'fv_cache', d)
        if os.path.isdir(root):
            def g(k, n, root=root):
                p = os.path.join(root, k, n + '.png')
                return (Image.open(p).convert('RGBA'), (64, 104)) if os.path.exists(p) else (None, None)
            srcs.append(('cache/' + d, g))

    mirror = {'SW': 'SE', 'W': 'E', 'NW': 'NE'}
    near = {'S': ['S', 'SE', 'E'], 'SE': ['SE', 'S', 'E'], 'E': ['E', 'SE', 'S']}

    def get(key, anim, d, i=0):
        flip = d in mirror
        base = mirror.get(d, d)
        for label, fn in srcs:
            for dd in near.get(base, [base]):
                im, anc = fn(key, '%s_%s_%d' % (anim, dd, i))
                if im is not None:
                    if flip:
                        im = im.transpose(Image.FLIP_LEFT_RIGHT)
                        anc = (im.width - anc[0], anc[1])
                    return im, anc, label, dd
        return None, None, None, None
    return get


def props_lib():
    """Existing props (campfire, bench) from assets/props (read-only)."""
    mp = os.path.join(ASSETS, 'props', 'manifest.json')
    if not os.path.exists(mp):
        return {}
    man = json.load(open(mp, encoding='utf-8'))
    atl = {a['key']: _atlas_getter(ASSETS, a) for a in man.get('atlases', [])}
    out = {}
    for k in ('campfire', 'bench', 'barrel', 'tree_pine_snow', 'tree_pine_a', 'bush_snow', 'lamp_post', 'snow_pile_b'):
        s = man['sprites'].get(k)
        if s and s.get('atlas') in atl:
            im = atl[s['atlas']](s['frame'])
            if im is not None:
                out[k] = (im, (s['anchor'][0] * im.width, s['anchor'][1] * im.height))
    return out


def fire_frame(i=3):
    try:
        man = json.load(open(os.path.join(ASSETS, 'fx', 'manifest.json'), encoding='utf-8'))
        s = [x for x in man['spritesheets'] if x['key'] == 'fx_fire'][0]
        sheet = Image.open(os.path.join(ASSETS, s['png'])).convert('RGBA')
        fw, fh = s['frameWidth'], s['frameHeight']
        cols = sheet.width // fw
        im = sheet.crop(((i % cols) * fw, (i // cols) * fh, (i % cols + 1) * fw, (i // cols + 1) * fh))
        return im, (s['anchor'][0] * fw, s['anchor'][1] * fh)
    except Exception:
        return None, None


# --------------------------------------------------------------------------- previews

def preview_all(keys, builds, bench, frames, out):
    ents = []
    for k in keys:
        m = builds[k]
        for n in m['frames']:
            ents.append((n.replace('lantern_string_', 'lantern_').replace('kids_swing_', 'swing_'), frames[n]))
    pp.shelf_preview(ents, out, title='Frost Village - village-life props (atlas life_props, 1x, PPU 64; '
                                      'stage / anim frames included)')


def preview_scene(keys, builds, bench, frames, out):
    W, H = 1600, 1180
    img = Image.new('RGBA', (W, H), (244, 247, 251, 255))
    d = ImageDraw.Draw(img)
    ox, oy = 800, 560

    def iso(x, y):
        return pp.iso(x, y, ox, oy)

    def at(sx, sy):
        """screen px -> world metres (so the mock layout can be designed on screen)."""
        u, v = (sx - ox) / 45.2548, (sy - oy) / 22.6274
        return (u + v) / 2.0, (u - v) / 2.0

    # terracotta plaza patch for the bench + lantern corner (like the game's plaza)
    px0, py0 = at(420, 330)
    plaza = [iso(px0 + x, py0 + y) for x, y in [(-2.6, -2.6), (-2.6, 2.6), (2.6, 2.6), (2.6, -2.6)]]
    d.polygon(plaza, fill=(217, 160, 138, 255))
    for i in range(0, 15):
        x = px0 - 2.6 + i * 0.37
        d.line([iso(x, py0 - 2.6), iso(x, py0 + 2.6)], fill=(200, 143, 120, 255), width=1)
    placed, shadows, labels = [], [], []
    chars = char_lib()
    vil = villager_lib()
    props = props_lib()
    srcs, approx, missing = set(), set(), set()

    def put_img(im, anc, x, y, depth=None):
        sx, sy = iso(x, y)
        placed.append((sy if depth is None else depth, len(placed), im, int(round(sx - anc[0])), int(round(sy - anc[1]))))
        return sx, sy

    def put(key, sx_, sy_, label=None, frame=None):
        x, y = at(sx_, sy_)
        for k in keys:
            m = builds[k]
            if key in m['sprites']:
                fr = frame or m['sprites'][key]['frame']
                sx, sy = put_img(frames[fr], m['anchorPx'], x, y)
                if label is not False:
                    labels.append((sx, sy + 12, label or key))
                return m, fr, sx, sy
        if key in props:
            im, anc = props[key]
            sx, sy = put_img(im, anc, x, y)
            if label:
                labels.append((sx, sy + 12, label))
            return None, None, sx, sy
        return None, None, None, None

    def stand(ck, fname, sx_, sy_):
        if ck not in chars:
            return
        get, anc = chars[ck]
        im = get(fname) or get('idle_S_0')
        if im is not None:
            sx, sy = put_img(im, anc, *at(sx_, sy_))
            shadows.append((sx, sy, 23, 9))

    def actor(vk, anim, dd, sx, sy, depth, shadow=False):
        im, anc, src, used = vil(vk, anim, dd)
        if im is None:
            missing.add('%s.%s' % (vk, anim))
            return
        srcs.add(src)
        want = {'SW': 'SE', 'W': 'E', 'NW': 'NE'}.get(dd, dd)
        if used != want:
            approx.add('%s %s_%s->%s' % (vk.replace('npc_', ''), anim, want, used))
        placed.append((depth, len(placed), im, int(round(sx - anc[0])), int(round(sy - anc[1]))))
        if shadow:
            shadows.append((sx, sy, 21, 8))

    def seat_people(m, fr, sx, sy, vkeys, anim='sit', kind='seat'):
        pts = m['framePoints'][fr].get(kind, [])
        dirs = m['frameDirs'][fr].get(kind, ['S'] * len(pts))
        front = kind == 'seat' and m.get('seatDepth', 'front') == 'front'
        for (dx, dy), dd, vk in zip(pts, dirs, vkeys):
            if vk:
                actor(vk, anim, dd, sx + dx, sy + dy, (sy + 0.5 + dy * 0.001) if front else (sy + dy),
                      shadow=(kind != 'seat'))

    # --- campfire circle: existing campfire + layouts.campfire_circle
    cx, cy = at(420, 640)
    csx, csy = put_img(props['campfire'][0], props['campfire'][1], cx, cy) if 'campfire' in props else iso(cx, cy)
    fim, fanc = fire_frame()
    if fim is not None:
        placed.append((csy + 0.2, len(placed), fim, int(round(csx - fanc[0])), int(round(csy - 4 - fanc[1]))))
    labels.append((csx, csy + 34, 'campfire (existing) + layouts.campfire_circle'))
    sitters = {'log_seat': ['npc_grandma', 'npc_aunt'], 'log_seat_y': ['npc_herbalist', 'npc_aunt'],
               'log_seat_x': ['npc_grandpa', 'npc_grandma']}
    m, fr, sx, sy = put('music_stand', 650, 610)
    if m and 'perform' in m['framePoints'][fr]:
        dx, dy = m['framePoints'][fr]['perform'][0]
        actor('npc_bard', 'perform', m['frameDirs'][fr]['perform'][0], sx + dx, sy + dy, sy + dy, shadow=True)
    for key, (x, y) in CAMP_LAYOUT:
        for k in keys:
            m = builds[k]
            if key in m['sprites']:
                fr = m['sprites'][key]['frame']
                sx, sy = put_img(frames[fr], m['anchorPx'], cx + x, cy + y)
                labels.append((sx, sy + 10, key))
                seat_people(m, fr, sx, sy, sitters[key])
    # --- plaza corner: lantern string over the existing bench (bench_seats) + barrel
    m, fr, sx, sy = put('lantern_string', 430, 255)
    if 'bench' in props and bench:
        im, anc = props['bench']
        sx, sy = put_img(im, anc, *at(400, 360))
        labels.append((sx, sy + 26, 'bench (existing) + bench_seats'))
        for (dx, dy), dd, vk in zip(bench['seatPoints'], bench['seatDirs'], ['npc_grandpa', 'npc_grandma']):
            actor(vk, 'sit', dd, sx + dx, sy + dy, sy + 0.5 + dy * 0.001)
        pdx, pdy = bench['petPoints'][0]
        actor('pet_cat', 'loaf', 'SE', sx + pdx, sy + pdy, sy + 0.4)
    if 'barrel' in props:
        put_img(props['barrel'][0], props['barrel'][1], *at(560, 330))
    # --- picnic table (sitters on the far bench), clothesline, dog house + dog
    m, fr, sx, sy = put('picnic_table', 760, 380)
    if m:
        seat_people(m, fr, sx, sy, ['npc_aunt', 'npc_herbalist'])
    put('clothesline', 1010, 250)
    m, fr, sx, sy = put('dog_house', 1300, 330)
    if m and 'door' in m['framePoints'][fr]:
        dx, dy = m['framePoints'][fr]['door'][0]
        actor('pet_dog', 'sit', m['frameDirs'][fr].get('door', ['S'])[0], sx + dx, sy + dy, sy + dy)
    # --- swing + ice rink
    m, fr, sx, sy = put('kids_swing', 1010, 600)
    if m:
        seat_people(m, fr, sx, sy, ['npc_kid_girl'])
    m, fr, sx, sy = put('ice_rink', 1330, 610)
    stand('villager_c', 'idle_S_0', 1300, 600)
    # --- snow fort with kids hiding behind it, snowball pile, sled + villagers for scale
    m, fr, sx, sy = put('snow_fort', 800, 800)
    if m:
        seat_people(m, fr, sx, sy, ['npc_kid_prankster', 'npc_kid_boy'], anim='throw', kind='hide')
    put('snowball_pile', 930, 845)
    m, fr, sx, sy = put('igloo', 200, 820)
    m, fr, sx, sy = put('notice_board', 1010, 990, label=False)
    if m:
        labels.append((sx + 80, sy + 6, 'notice_board'))
        for (dx, dy), dd, ck in zip(m['framePoints'][fr]['gather'], m['frameDirs'][fr]['gather'],
                                    ['villager_b', None, 'villager_c']):
            if ck and ck in chars:
                get, anc = chars[ck]
                mir = {'SW': 'SE', 'W': 'E', 'NW': 'NE'}
                im = get('idle_%s_0' % mir.get(dd, dd))
                if im is not None:
                    ax_ = anc[0]
                    if dd in mir:
                        im = im.transpose(Image.FLIP_LEFT_RIGHT)
                        ax_ = im.width - anc[0]
                    placed.append((sy + dy, len(placed), im, int(round(sx + dx - ax_)), int(round(sy + dy - anc[1]))))
                    shadows.append((sx + dx, sy + dy, 23, 9))
    put('sled', 1150, 860)
    stand('villager_a', 'idle_S_0', 1225, 845)
    stand('player', 'idle_SE_0', 640, 790)
    # --- snowman stages along the bottom, kids building the finished one
    for i, x in enumerate((140, 290, 440, 610)):
        m, fr, sx, sy = put('snowman_%d' % i, x, 1030)
    if m:
        for (dx, dy), dd, vk in zip(m['framePoints'][fr]['work'], m['frameDirs'][fr]['work'],
                                    ['npc_kid_boy', 'npc_kid_girl']):
            actor(vk, 'happy', dd, sx + dx, sy + dy, sy + dy, shadow=True)
    for k, sx_, sy_ in (('tree_pine_snow', 90, 420), ('tree_pine_a', 1530, 470), ('tree_pine_snow', 1480, 1000),
                        ('bush_snow', 1390, 800), ('tree_pine_snow', 200, 170), ('bush_snow', 60, 700)):
        if k in props:
            put_img(props[k][0], props[k][1], *at(sx_, sy_))
    # shadows first, then everything depth-sorted (anchor y; sitters with seatDepth front just above the seat)
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for sx, sy, rx, ry in shadows:
        sd.ellipse([sx - rx, sy - ry, sx + rx, sy + ry], fill=(38, 46, 82, 70))
    img.alpha_composite(sh)
    for _, _, im, x, y in sorted(placed, key=lambda t: (t[0], t[1])):
        img.alpha_composite(im, (x, y))
    d = ImageDraw.Draw(img)
    f = pp.font(13)
    for sx, sy, lab in labels:
        tw = f.getlength(lab)
        d.rounded_rectangle([sx - tw / 2 - 4, sy - 1, sx + tw / 2 + 4, sy + 16], radius=6, fill=(255, 255, 255, 190))
        d.text((sx - tw / 2, sy), lab, fill=(30, 36, 48), font=f)
    d.rectangle([0, H - 62, W, H], fill=(31, 95, 168, 255))
    d.text((16, H - 56), 'Village-life props at 1x (PPU 64) at their anchors. Standing: assets/characters; '
           'seated / throwing / pets: %s.' % (' + '.join(sorted(srcs)) or 'no villager renders found'),
           fill=(255, 255, 255), font=pp.font(16))
    msg = []
    if approx:
        msg.append('nearest-dir stand-ins: ' + ', '.join(sorted(approx)))
    if missing:
        msg.append('no frames (seat shown empty): ' + ', '.join(sorted(missing)))
    d.text((16, H - 30), ('; '.join(msg))[:200], fill=(220, 232, 248), font=pp.font(12))
    img.convert('RGB').save(out, optimize=True)
    return out


def preview_gif(keys, builds, frames, out):
    """Snowman stages | swing loop (+ a kid riding it) | lantern twinkle, side by side."""
    vil = villager_lib()
    parts = []
    if 'snowman' in builds:
        m = builds['snowman']
        parts.append(('snowman stages', m, [n for n in m['frames']], [700] * 4, None))
    for k, an in (('kids_swing', 'swing'), ('lantern_string', 'twinkle')):
        if k in builds:
            m = builds[k]
            a = m['sprites'][k]['anims'][an]
            rider = None
            if k == 'kids_swing':
                for cand in ('npc_kid_girl', 'npc_kid_boy', 'npc_aunt', 'npc_grandma'):
                    if vil(cand, 'sit', 'S')[0] is not None:
                        rider = cand
                        break
            parts.append((k + ' ' + an + (' (rider: %s)' % rider.replace('npc_', '') if rider else ''), m,
                          a['frames'], [int(1000 / a['fps'])] * len(a['frames']), rider))
    if not parts:
        return None
    gap = 16
    Wt = sum(p[1]['frameSize'][0] for p in parts) + gap * (len(parts) + 1)
    Ht = max(p[1]['frameSize'][1] for p in parts) + 34
    total = 2800
    step = 100
    outs = []
    for t in range(0, total, step):
        im = Image.new('RGBA', (Wt, Ht), (236, 242, 249, 255))
        dr = ImageDraw.Draw(im)
        x = gap
        for label, m, fl, durs, rider in parts:
            fw, fh = m['frameSize']
            cyc = sum(durs)
            tt = t % cyc
            i = 0
            while tt >= durs[i]:
                tt -= durs[i]
                i += 1
            n = fl[i]
            y0 = Ht - 26 - fh
            im.alpha_composite(frames[n], (x, y0))
            if rider:
                pts = m['framePoints'][n].get('seat')
                vim, vanc, _, _ = vil(rider, 'sit', 'S')
                if pts and vim is not None:
                    ax, ay = m['anchorPx']
                    im.alpha_composite(vim, (int(x + ax + pts[0][0] - vanc[0]), int(y0 + ay + pts[0][1] - vanc[1])))
            dr.text((x + 4, Ht - 20), label, fill=(30, 36, 48), font=pp.font(13))
            x += fw + gap
        outs.append(im.convert('RGB'))
    pal = outs[len(outs) // 2].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in outs]
    q[0].save(out, save_all=True, append_images=q[1:], duration=step, loop=0, optimize=False, disposal=1)
    return out


# --------------------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    cache = os.path.join(tempfile.gettempdir(), 'fv_cache', 'life_props')
    if '--cache' in args:
        cache = args[args.index('--cache') + 1]
    quantize = 'auto'
    if '--quantize' in args:
        quantize = args[args.index('--quantize') + 1]
    keys, builds, bench, frames = load(cache)
    if not keys:
        raise SystemExit('no renders in %s - run life_render.py first' % cache)
    for fn in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if fn.startswith(ATLAS) and fn.endswith(('.png', '.json')):
            os.remove(os.path.join(OUT, fn))
    sheet, atlas, png, js = pack(frames, quantize)
    man = build_manifest(keys, builds, bench, sheet.size)
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    total = os.path.getsize(png) + os.path.getsize(js) + os.path.getsize(os.path.join(OUT, 'manifest.json'))
    print('%s %dx%d  %d frames  %d sprites  payload %.2f MB' % (ATLAS, sheet.width, sheet.height,
                                                               len(atlas['frames']), len(man['sprites']),
                                                               total / 1048576.0))
    if '--no-previews' not in args:
        preview_all(keys, builds, bench, frames, os.path.join(PREV, 'life_props_all.png'))
        preview_scene(keys, builds, bench, frames, os.path.join(PREV, 'life_scene.png'))
        preview_gif(keys, builds, frames, os.path.join(PREV, 'life_anims.gif'))
        print('previews: docs/previews/life_props_all.png, life_scene.png, life_anims.gif')


if __name__ == '__main__':
    main()
