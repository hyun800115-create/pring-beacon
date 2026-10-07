"""
prop_render.py - render Frost Village props / stations / buildings / decor / items
(CONTRACT section 4) into a raw frame cache, one PNG per frame + a sidecar JSON
per sprite.  prop_pack.py then turns the cache into atlases + manifest.

Re-run (build machine, bpy module):
    .cache/venv/Scripts/python.exe tools/blender/prop_render.py -- [keys or atlas names ...] [--force]
        [--samples N] [--cache DIR] [--list]
Re-run (your PC, real Blender 4.2+):
    blender -b -P tools/blender/prop_render.py -- [same args]

  * no keys      -> render everything that is not cached yet (resumable)
  * key names    -> e.g. tree_pine_a station_grill   (prefix match with a trailing *: crop_wheat_*)
  * atlas names  -> props_nature props_buildings props_decor props_items
  * --force      -> re-render even if cached
Default cache: .cache/fv_cache/props  (on the build machine .cache/fv_cache/props).
Deterministic: fixed seeds, fixed sample counts.
"""
import json
import math
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bl_common as bc  # noqa: E402
import prop_lib as L  # noqa: E402
import prop_assets as A  # noqa: E402
FV_CACHE = os.environ.get('FV_CACHE') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.cache', 'fv_cache'))  # 저장소/.cache/fv_cache


def parse(argv):
    opts = {'keys': [], 'force': False, 'samples': None,
            'cache': os.path.join(FV_CACHE, 'props'), 'list': False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--force':
            opts['force'] = True
        elif a == '--samples':
            i += 1
            opts['samples'] = int(argv[i])
        elif a == '--cache':
            i += 1
            opts['cache'] = argv[i]
        elif a == '--list':
            opts['list'] = True
        else:
            opts['keys'].append(a)
        i += 1
    return opts


def select(keys):
    if not keys:
        return list(A.ASSETS)
    out = []
    for k in keys:
        if k.endswith('*'):
            out += [n for n in A.ASSETS if n.startswith(k[:-1])]
        elif k in A.ASSETS:
            out.append(k)
        else:
            grp = [n for n, s in A.ASSETS.items() if s['atlas'] == k]
            if not grp:
                raise SystemExit('unknown key/atlas: ' + k)
            out += grp
    seen = set()
    return [k for k in out if not (k in seen or seen.add(k))]


def frame_names(spec):
    names = [spec['key']]
    names += ['%s_work_%d' % (spec['key'], i) for i in range(spec['work'])]
    return names


def cached(spec, cache):
    side = os.path.join(cache, spec['key'] + '.json')
    if not os.path.exists(side):
        return False
    return all(os.path.exists(os.path.join(cache, n + '.png')) for n in frame_names(spec))


def fit_states(res, spec):
    """Frame that fits the idle state AND every work state (moving parts, flames,
    smoke puffs), with one shared anchor.  topPx comes from the idle state."""
    W, H, (ax, ay), top = L.frame_fit(margin=8, shadow=spec['shadow'])
    if not spec['work']:
        return W, H, (ax, ay), top
    if 'idle' not in res:
        raise SystemExit('%s: a station with work frames must return an idle() restore' % spec['key'])
    left, right, up, down = ax, W - ax, ay, H - ay
    for i in range(spec['work']):
        res['work'](i)
        bpy.context.view_layer.update()
        w, h, (x, y), _ = L.frame_fit(margin=8, shadow=spec['shadow'])
        left, right, up, down = max(left, x), max(right, w - x), max(up, y), max(down, h - y)
    res['idle']()
    bpy.context.view_layer.update()
    W = (left + right + 3) // 4 * 4
    H = (up + down + 3) // 4 * 4
    return W, H, (left, up), top


def fx_points(res, spec, W, H, anchor):
    """res['fx'] = {name: world point} -> px offsets [dx, dy] from the anchor."""
    out = {}
    R = Matrix.Rotation(math.radians(spec['yaw']), 3, 'Z')
    for name, p in (res.get('fx') or {}).items():
        q = R @ Vector(p)
        x, y = bc.world_to_pixel(tuple(q), W, H, anchor)
        out[name] = [int(round(x - anchor[0])), int(round(y - anchor[1]))]
    return out


def render_one(spec, cache, samples=None):
    key = spec['key']
    t0 = time.time()
    bc.reset_scene()
    L._CUSTOM.clear()
    bc.setup_lighting()
    res = spec['fn']() or {}
    L.rotate_all(spec['yaw'])
    item = spec['item']
    if item:
        W, H = A.ITEM_FRAME
        anchor = A.ITEM_ANCHOR
        w2, h2, an2, top = L.frame_fit(margin=0, shadow=False)
        # check it fits inside the fixed item frame
        if an2[0] > anchor[0] or an2[1] > anchor[1] or (w2 - an2[0]) > (W - anchor[0]) or \
                (h2 - an2[1]) > (H - anchor[1]):
            print('WARNING item %s exceeds item frame: need anchor %s size %sx%s' % (key, an2, w2, h2))
    else:
        W, H, anchor, top = fit_states(res, spec)
    if spec['shadow'] and not res.get('custom_catcher'):
        bc.add_shadow_catcher(size=spec['catcher'])
    bc.setup_render(W, H, samples=samples or spec['samples'])
    bc.setup_camera(W, H, anchor)
    frames = []
    bc.render_to(os.path.join(cache, key + '.png'))
    frames.append(key)
    if spec['work']:
        for i in range(spec['work']):
            res['work'](i)
            n = '%s_work_%d' % (key, i)
            bc.render_to(os.path.join(cache, n + '.png'))
            frames.append(n)
        if 'idle' in res:
            res['idle']()
    meta = {
        'key': key, 'kind': spec['kind'], 'atlas': spec['atlas'], 'frameSize': [W, H],
        'anchorPx': list(anchor), 'anchor': [round(anchor[0] / W, 5), round(anchor[1] / H, 5)],
        'frames': frames, 'shadow': spec['shadow'], 'notes': res.get('notes', spec['notes']),
        'topPx': int(round(top)),
    }
    if spec['fp'] is not None:
        meta['footprint'] = L.footprint_px(spec['fp'], spec['yaw'])
        meta['footprintM'] = list(spec['fp']) if spec['fp'][0] != 'r' else {'radius': spec['fp'][1]}
    if spec['front']:
        meta['front'] = spec['front']
    if spec['work']:
        meta['anims'] = {'work': {'frames': frames[1:], 'fps': spec['fps'], 'repeat': -1}}
    if item:
        meta['stackStep'] = L.stack_step(item['thickness'])
        meta['thicknessM'] = item['thickness']
    fx = fx_points(res, spec, W, H, anchor)
    if fx:
        meta['fxPoints'] = fx
    for k in ('extra',):
        if k in res:
            meta.update(res[k])
    with open(os.path.join(cache, key + '.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('[%s] %dx%d anchor %s  %.1fs' % (key, W, H, anchor, time.time() - t0), flush=True)
    return meta


def main():
    opts = parse(bc.script_args())
    keys = select(opts['keys'])
    if opts['list']:
        for k in keys:
            s = A.ASSETS[k]
            print(k, s['kind'], s['atlas'])
        return
    os.makedirs(opts['cache'], exist_ok=True)
    explicit = bool(opts['keys'])
    for k in keys:
        spec = A.ASSETS[k]
        if not opts['force'] and cached(spec, opts['cache']) and not (explicit and opts['force']):
            print('[%s] cached' % k)
            continue
        render_one(spec, opts['cache'], opts['samples'])


if __name__ == '__main__':
    main()
