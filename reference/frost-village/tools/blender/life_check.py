"""
life_check.py - verify assets/life_props/manifest.json against CONTRACT_VILLAGERS.md section B.

    python3 tools/blender/life_check.py          (exit code 1 on any problem)

Checks: required keys present (snowman_0..3, snowball_pile, snow_fort, log_seat, sled, dog_house,
picnic_table, lantern_string, bench_seats); the atlas PNG/JSON exist and are <= 2048 px; every
sprite frame (and anim frame) exists; anchors are normalised and frameSize matches the untrimmed
sourceSize; footprints / topPx are ints; seatPoints / seatDirs / seatDepth are well formed (seats
have points, dirs are renderable-or-mirrored facings); anim seatPoints match the frame count;
snowman stages share frameSize + anchor; bench_seats refers to the existing props bench; no sprite
key collides with another manifest fragment; layouts reference real sprites; payload <= 1.5 MB.
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
ASSETS = os.path.join(GAME, 'assets')
REQUIRED = ['snowman_0', 'snowman_1', 'snowman_2', 'snowman_3', 'snowball_pile', 'snow_fort', 'log_seat', 'sled',
            'dog_house', 'picnic_table', 'lantern_string', 'bench_seats']
SEATED = ['log_seat', 'log_seat_x', 'log_seat_y', 'picnic_table', 'kids_swing', 'bench_seats']
KINDS = {'prop', 'station', 'building', 'decor', 'item', 'ui', 'icon', 'decal', 'seats'}
DIRS = {'S', 'SE', 'E', 'NE', 'N', 'SW', 'W', 'NW'}
SIT_DIRS = {'S', 'SE', 'E', 'SW', 'W'}            # sit anims exist for S/SE/E (+ mirrored SW/W)
BUDGET_MB = 1.5
OTHER = ['characters', 'props', 'fx', 'ui', 'ground', 'audio', 'emotes', 'villagers']


def is_pt(p):
    return isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) for v in p)


def main():
    errors, warns = [], []
    mp = os.path.join(ASSETS, 'life_props', 'manifest.json')
    if not os.path.exists(mp):
        print('FAIL: missing', mp)
        return 1
    man = json.load(open(mp, encoding='utf-8'))
    sprites = man.get('sprites', {})
    total = os.path.getsize(mp)
    frames = {}
    for a in man.get('atlases', []):
        png, js = os.path.join(ASSETS, a['png']), os.path.join(ASSETS, a['json'])
        if not (os.path.exists(png) and os.path.exists(js)):
            errors.append('atlas %s: missing file(s)' % a['key'])
            continue
        total += os.path.getsize(png) + os.path.getsize(js)
        with Image.open(png) as im:
            if im.width > 2048 or im.height > 2048:
                errors.append('atlas %s is %dx%d (> 2048)' % (a['key'], im.width, im.height))
            size = im.size
        data = json.load(open(js))
        if (data['meta']['size']['w'], data['meta']['size']['h']) != size:
            errors.append('atlas %s: meta.size != png size' % a['key'])
        for fn, fr in data['frames'].items():
            r = fr['frame']
            if r['x'] + r['w'] > size[0] or r['y'] + r['h'] > size[1]:
                errors.append('atlas %s: frame %s outside the sheet' % (a['key'], fn))
        frames[a['key']] = data['frames']
    for k in REQUIRED:
        if k not in sprites:
            errors.append('missing sprite %s' % k)
    for k, s in sprites.items():
        if s.get('kind') not in KINDS:
            errors.append('%s: kind %r not allowed' % (k, s.get('kind')))
        if k == 'bench_seats':
            continue
        tab = frames.get(s.get('atlas'))
        if tab is None:
            errors.append('%s: atlas %r not listed' % (k, s.get('atlas')))
            continue
        fr = tab.get(s.get('frame'))
        if fr is None:
            errors.append('%s: frame %r missing' % (k, s.get('frame')))
            continue
        src = [fr['sourceSize']['w'], fr['sourceSize']['h']]
        if s.get('frameSize') != src:
            errors.append('%s: frameSize %s != sourceSize %s' % (k, s.get('frameSize'), src))
        ax, ay = s.get('anchor', [None, None])
        if not (isinstance(ax, (int, float)) and 0 <= ax <= 1 and 0 <= ay <= 1):
            errors.append('%s: bad anchor %r' % (k, s.get('anchor')))
        fp = s.get('footprint')
        if not (isinstance(fp, list) and len(fp) == 2 and all(isinstance(v, int) and v > 0 for v in fp)):
            errors.append('%s: bad footprint %r' % (k, fp))
        if not isinstance(s.get('topPx'), int):
            errors.append('%s: topPx missing' % k)
        for an, a in (s.get('anims') or {}).items():
            for f in a.get('frames', []):
                if f not in tab:
                    errors.append('%s.%s: frame %s missing' % (k, an, f))
                elif tab[f]['sourceSize'] != fr['sourceSize']:
                    errors.append('%s.%s: frame %s size differs from the idle frame' % (k, an, f))
            if 'seatPoints' in a and (len(a['seatPoints']) != len(a['frames']) or
                                      not all(is_pt(p) for p in a['seatPoints'])):
                errors.append('%s.%s: seatPoints must give one [dx,dy] per frame' % (k, an))
            if not isinstance(a.get('fps'), (int, float)) or 'repeat' not in a:
                errors.append('%s.%s: needs fps + repeat' % (k, an))
        for field in ('hidePoints', 'workPoints', 'gatherPoints'):
            if field in s and not all(is_pt(p) for p in s[field]):
                errors.append('%s: bad %s' % (k, field))
        for field in ('doorPoint', 'pullPoint', 'performPoint'):
            if field in s and not is_pt(s[field]):
                errors.append('%s: bad %s' % (k, field))
    for k in SEATED:
        s = sprites.get(k)
        if s is None:
            continue
        pts, dirs = s.get('seatPoints'), s.get('seatDirs')
        if not pts or not all(is_pt(p) for p in pts):
            errors.append('%s: seatPoints missing/bad %r' % (k, pts))
        elif not dirs or len(dirs) != len(pts) or not all(d in SIT_DIRS for d in dirs):
            errors.append('%s: seatDirs %r must match seatPoints and be one of %s' % (k, dirs, sorted(SIT_DIRS)))
        if s.get('seatDepth') not in ('front', 'behind'):
            errors.append('%s: seatDepth %r' % (k, s.get('seatDepth')))
        for p in pts or []:
            if is_pt(p) and not (-200 < p[0] < 200 and -120 < p[1] < 10):
                warns.append('%s: seat point %s looks far from the anchor' % (k, p))
    st = [sprites.get('snowman_%d' % i) for i in range(4)]
    if all(st) and len({(tuple(x['frameSize']), tuple(x['anchor'])) for x in st}) != 1:
        errors.append('snowman stages must share frameSize + anchor')
    b = sprites.get('bench_seats')
    if b:
        if b.get('of') != 'bench':
            errors.append('bench_seats.of must be "bench"')
        pm = os.path.join(ASSETS, 'props', 'manifest.json')
        if os.path.exists(pm) and 'bench' not in json.load(open(pm, encoding='utf-8')).get('sprites', {}):
            errors.append('bench_seats: props manifest has no bench sprite')
    for name in OTHER:
        p = os.path.join(ASSETS, name, 'manifest.json')
        if not os.path.exists(p):
            continue
        try:
            o = json.load(open(p, encoding='utf-8'))
        except Exception:
            warns.append('could not read %s' % p)
            continue
        clash = (set(o.get('sprites', {})) | set(o.get('characters', {}))) & set(sprites)
        ak = {a['key'] for a in o.get('atlases', [])} & {a['key'] for a in man.get('atlases', [])}
        if clash or ak:
            errors.append('key collision with %s: %s' % (name, sorted(clash | ak)))
    for ln, lay in (man.get('layouts') or {}).items():
        for it in lay.get('items', []):
            if it.get('sprite') not in sprites or not is_pt(it.get('offset')):
                errors.append('layout %s: bad item %r' % (ln, it))
    mb = total / 1048576.0
    if mb > BUDGET_MB:
        errors.append('payload %.2f MB > %.1f MB' % (mb, BUDGET_MB))
    print('life_props manifest: %d sprites, %d atlas(es), payload %.2f MB' % (len(sprites), len(frames), mb))
    for w in warns:
        print('WARN:', w)
    for e in errors:
        print('FAIL:', e)
    if not errors:
        print('OK: all CONTRACT_VILLAGERS section-B keys present and valid')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
