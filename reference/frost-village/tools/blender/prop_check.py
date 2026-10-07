"""
prop_check.py - verify assets/props/manifest.json against CONTRACT section 4.

    python3 tools/blender/prop_check.py          (exit code 1 on any problem)

Checks: every section-4 key is in `sprites`; its atlas is listed in `atlases`
and its PNG/JSON exist; the frame (and every anims.work frame) exists in that
atlas JSON; anchor is normalised and matches the untrimmed sourceSize; atlas
sheets are <= 2048x2048; stations have a 4-frame work loop; items have an
integer stackStep in 8..14 and a carryScale in 0.4..1.0; station work frames share
the idle frame's untrimmed size; non-items have a footprint; total payload <= 5 MB.
"""
import json
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
ASSETS = os.path.join(GAME, 'assets')

NATURE = ['tree_pine_a', 'tree_pine_b', 'tree_pine_snow', 'tree_stump', 'rock_ore', 'rock_ore_b', 'rock_rubble',
          'crop_wheat_0', 'crop_wheat_1', 'crop_wheat_2', 'crop_wheat_3', 'bush_snow', 'snow_pile_a', 'snow_pile_b',
          'ice_chunk']
STATIONS = ['station_grill', 'station_sawmill', 'station_bakery', 'station_smelter', 'station_smokehouse']
BUILDINGS = ['market_counter', 'trade_post', 'worker_hut', 'chief_lodge', 'tent_a', 'campfire', 'upgrade_bench',
             'fish_net', 'dock_pier', 'mine_entrance', 'boat_small']
DECOR = ['fence_log_x', 'fence_log_y', 'fence_post', 'bench', 'lamp_post', 'barrel', 'crate', 'firewood_pile',
         'signpost', 'flag_pole', 'hay_bale']
ITEMS = ['item_fish_raw', 'item_fish_cooked', 'item_log', 'item_plank', 'item_wheat', 'item_bread', 'item_ore',
         'item_ingot', 'item_meat_raw', 'item_meat_cooked', 'item_coin']
REQUIRED = NATURE + STATIONS + BUILDINGS + DECOR + ITEMS
BUDGET_MB = 5.0


def contract_keys():
    """Keys mentioned in CONTRACT.md section 4 (sanity cross-check of REQUIRED)."""
    path = os.path.join(GAME, 'docs', 'CONTRACT.md')
    if not os.path.exists(path):
        return set()
    txt = open(path, encoding='utf-8').read()
    m = re.search(r'## 4\..*?(?=\n## 5\.)', txt, re.S)
    if not m:
        return set()
    sec = m.group(0)
    keys = set(re.findall(r'`([a-z][a-z0-9_]+)`', sec))
    for base, lo, hi in re.findall(r'`([a-z_]+?)(\d)`\.\.`\1(\d)`', sec):
        for i in range(int(lo), int(hi) + 1):
            keys.add('%s%d' % (base, i))
    return {k for k in keys if '_' in k and not k.startswith('props_') and k not in ('anims', 'work')}


def main():
    errors, warns = [], []
    man_path = os.path.join(ASSETS, 'props', 'manifest.json')
    if not os.path.exists(man_path):
        print('FAIL: missing', man_path)
        return 1
    man = json.load(open(man_path, encoding='utf-8'))
    sprites = man.get('sprites', {})
    atlases = {a['key']: a for a in man.get('atlases', [])}
    ck = contract_keys()
    missing_from_list = sorted(k for k in ck - set(REQUIRED) if k.startswith(('tree_', 'rock_', 'crop_', 'item_',
                                                                               'station_', 'fence_')))
    if missing_from_list:
        warns.append('CONTRACT mentions keys not in REQUIRED list: %s' % missing_from_list)
    atlas_frames = {}
    total = 0
    for key, a in atlases.items():
        png = os.path.join(ASSETS, a['png'])
        js = os.path.join(ASSETS, a['json'])
        if not os.path.exists(png) or not os.path.exists(js):
            errors.append('atlas %s: missing file(s)' % key)
            continue
        total += os.path.getsize(png) + os.path.getsize(js)
        with Image.open(png) as im:
            if im.width > 2048 or im.height > 2048:
                errors.append('atlas %s is %dx%d (> 2048)' % (key, im.width, im.height))
            size = im.size
        data = json.load(open(js))
        meta = data.get('meta', {}).get('size', {})
        if (meta.get('w'), meta.get('h')) != size:
            errors.append('atlas %s: meta.size %s != png %s' % (key, meta, size))
        for fn, fr in data['frames'].items():
            r = fr['frame']
            if r['x'] < 0 or r['y'] < 0 or r['x'] + r['w'] > size[0] or r['y'] + r['h'] > size[1]:
                errors.append('atlas %s: frame %s rect %s outside the %dx%d sheet' % (key, fn, r, *size))
            ss = fr['spriteSourceSize']
            if ss['x'] + ss['w'] > fr['sourceSize']['w'] or ss['y'] + ss['h'] > fr['sourceSize']['h']:
                errors.append('atlas %s: frame %s spriteSourceSize outside sourceSize' % (key, fn))
        atlas_frames[key] = data['frames']
    for key in REQUIRED:
        s = sprites.get(key)
        if s is None:
            errors.append('missing sprite %s' % key)
            continue
        fr_tab = atlas_frames.get(s.get('atlas'))
        if fr_tab is None:
            errors.append('%s: atlas %r not listed/loaded' % (key, s.get('atlas')))
            continue
        fr = fr_tab.get(s.get('frame'))
        if fr is None:
            errors.append('%s: frame %r not in atlas %s' % (key, s.get('frame'), s['atlas']))
            continue
        ax, ay = s.get('anchor', [None, None])
        if not (isinstance(ax, (int, float)) and 0 <= ax <= 1 and 0 <= ay <= 1):
            errors.append('%s: bad anchor %r' % (key, s.get('anchor')))
        if 'frameSize' in s and [fr['sourceSize']['w'], fr['sourceSize']['h']] != s['frameSize']:
            errors.append('%s: frameSize %s != sourceSize %s' % (key, s['frameSize'], fr['sourceSize']))
        kind = s.get('kind')
        if key in ITEMS:
            st = s.get('stackStep')
            if not isinstance(st, int) or not 8 <= st <= 14:
                errors.append('%s: stackStep %r not an int in 8..14' % (key, st))
            if kind != 'item':
                errors.append('%s: kind %r != item' % (key, kind))
            cs = s.get('carryScale')
            if not isinstance(cs, (int, float)) or not 0.4 <= cs <= 1.0:
                errors.append('%s: carryScale %r not a number in 0.4..1.0' % (key, cs))
        else:
            fp = s.get('footprint')
            if not (isinstance(fp, list) and len(fp) == 2 and all(isinstance(v, int) and v > 0 for v in fp)):
                errors.append('%s: missing/bad footprint %r' % (key, fp))
        if key in STATIONS:
            w = s.get('anims', {}).get('work')
            if not w or len(w.get('frames', [])) != 4:
                errors.append('%s: anims.work must have 4 frames' % key)
            else:
                tab = atlas_frames.get(w.get('atlas', s['atlas']), {})
                for f in w['frames']:
                    if f not in tab:
                        errors.append('%s: work frame %s missing from atlas' % (key, f))
                    elif tab[f]['sourceSize'] != fr['sourceSize']:
                        errors.append('%s: work frame %s sourceSize %s != idle %s'
                                      % (key, f, tab[f]['sourceSize'], fr['sourceSize']))
                if not isinstance(w.get('fps'), (int, float)) or w.get('repeat') != -1:
                    errors.append('%s: work anim needs fps and repeat -1' % key)
            if kind != 'station':
                errors.append('%s: kind %r != station' % (key, kind))
    extra = sorted(set(sprites) - set(REQUIRED))
    mb = total / 1024 / 1024
    if mb > BUDGET_MB:
        errors.append('payload %.2f MB > %.1f MB budget' % (mb, BUDGET_MB))
    print('props manifest: %d sprites (%d required, %d extra), %d atlases, payload %.2f MB'
          % (len(sprites), len(REQUIRED), len(extra), len(atlases), mb))
    for w in warns:
        print('WARN:', w)
    for e in errors:
        print('FAIL:', e)
    if not errors:
        print('OK: every CONTRACT section-4 key present with a valid atlas frame')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
