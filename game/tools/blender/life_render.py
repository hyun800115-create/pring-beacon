"""
life_render.py - render the village-life props (CONTRACT_VILLAGERS.md section B) into a raw
frame cache: one PNG per frame + one sidecar JSON per build.  life_pack.py then makes the
`life_props` atlas + assets/life_props/manifest.json.

Same camera / light / PPU / shadow catcher as the base props (bl_common + prop_lib).

Re-run (build machine, Blender as a Python module):
    .cache/venv/Scripts/python.exe tools/blender/life_render.py -- [keys ...] [--force] [--samples N] [--cache DIR] [--list]
Re-run (your PC, Blender 4.2+):
    blender -b -P tools/blender/life_render.py -- [same args]

  * no keys    -> render every build that is not cached yet (resumable), plus bench_seats
  * keys       -> build keys (snowman, snow_fort, log_seat, ...; trailing * = prefix match)
  * --force    -> re-render even if cached
  * bench_seats is a pseudo key: it builds the EXISTING bench (prop_assets.b_bench, unchanged),
    measures its seat planks and writes seat points - nothing is rendered.
Default cache: .cache/fv_cache/life_props.  Deterministic: fixed seeds + sample counts.
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
import life_assets as LA  # noqa: E402
FV_CACHE = os.environ.get('FV_CACHE') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.cache', 'fv_cache'))  # 저장소/.cache/fv_cache

MARGIN = 8
SECTORS = ['E', 'SE', 'S', 'SW', 'W', 'NW', 'N', 'NE']


def parse(argv):
    opts = {'keys': [], 'force': False, 'samples': None,
            'cache': os.path.join(FV_CACHE, 'life_props'), 'list': False}
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
    allk = list(LA.LIFE) + ['bench_seats']
    if not keys:
        return allk
    out = []
    for k in keys:
        if k.endswith('*'):
            out += [n for n in allk if n.startswith(k[:-1])]
        elif k in allk:
            out.append(k)
        else:
            hit = [n for n, s in LA.LIFE.items() if k in s['sprites']]
            if not hit:
                raise SystemExit('unknown key: ' + k)
            out += hit
    seen = set()
    return [k for k in out if not (k in seen or seen.add(k))]


def screen_dir(v):
    """World direction -> screen facing name (CONTRACT section 9 sector maths)."""
    sx = (v.x + v.y) * math.sqrt(0.5)
    sy = (v.x - v.y) * math.sqrt(0.5) * 0.5
    a = math.atan2(sy * 2.0, sx)
    return SECTORS[int(round(a / (math.pi / 4))) % 8]


def px(p):
    x, y = bc.world_to_pixel(tuple(p), 0, 0, (0.0, 0.0))
    return [int(round(x)), int(round(y))]


def parent_to_root(yaw_deg):
    """Parent every top-level object to a root empty rotated by yaw, so setters can keep
    animating children in the builder's local frame."""
    root = bpy.data.objects.new('LifeRoot', None)
    bpy.context.scene.collection.objects.link(root)
    for o in list(bpy.context.scene.objects):
        if o is root or o.parent is not None or o.type == 'CAMERA' or o.name == 'ShadowCatcher':
            continue
        if o.type == 'LIGHT' and o.data.type == 'SUN':
            continue
        o.parent = root
    root.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    bpy.context.view_layer.update()
    return root


def markers(yaw_deg):
    """{kind: [[dx, dy], ...]} + {kind: [dir, ...]} for the current pose."""
    bpy.context.view_layer.update()
    R = Matrix.Rotation(math.radians(yaw_deg), 3, 'Z')
    pts, dirs = {}, {}
    for kind, em, facing in LA.MARKERS:
        pts.setdefault(kind, []).append(px(em.matrix_world.translation))
        if facing is not None:
            dirs.setdefault(kind, []).append(screen_dir(R @ facing))
    return pts, dirs


def fit_frames(frames):
    """Frame that fits every state with one shared anchor.  Returns W, H, anchor, {frame: topPx}."""
    left = right = up = down = 0
    tops = {}
    for name, setter in frames:
        if setter:
            setter()
        bpy.context.view_layer.update()
        w, h, (x, y), top = L.frame_fit(margin=MARGIN, shadow=True)
        left, right, up, down = max(left, x), max(right, w - x), max(up, y), max(down, h - y)
        tops[name] = int(round(top))
    W = (left + right + 3) // 4 * 4
    H = (up + down + 3) // 4 * 4
    return W, H, (left, up), tops


def render_build(spec, cache, samples=None):
    key = spec['key']
    t0 = time.time()
    bc.reset_scene()
    L._CUSTOM.clear()
    LA.MARKERS.clear()
    bc.setup_lighting()
    res = spec['fn']() or {}
    parent_to_root(spec['yaw'])
    frames = res.get('frames') or [(key, None)]
    W, H, anchor, tops = fit_frames(frames)
    if spec['shadow']:
        bc.add_shadow_catcher(size=spec['catcher'])
    bc.setup_render(W, H, samples=samples or spec['samples'])
    bc.setup_camera(W, H, anchor)
    fpts, fdirs = {}, {}
    for name, setter in frames:
        if setter:
            setter()
        bpy.context.view_layer.update()
        bc.render_to(os.path.join(cache, name + '.png'))
        fpts[name], fdirs[name] = markers(spec['yaw'])
    if res.get('rest'):
        res['rest']()
    sprites = res.get('sprites') or {key: {'frame': key}}
    meta = {
        'build': key, 'kind': spec['kind'], 'atlas': 'life_props', 'frameSize': [W, H],
        'anchorPx': list(anchor), 'anchor': [round(anchor[0] / W, 5), round(anchor[1] / H, 5)],
        'frames': [n for n, _ in frames], 'shadow': spec['shadow'], 'notes': spec['notes'],
        'yaw': spec['yaw'], 'topPx': tops, 'framePoints': fpts, 'frameDirs': fdirs, 'sprites': sprites,
    }
    if spec['fp'] is not None:
        meta['footprint'] = L.footprint_px(spec['fp'], spec['yaw'])
        meta['footprintM'] = list(spec['fp']) if spec['fp'][0] != 'r' else {'radius': spec['fp'][1]}
    if spec['front']:
        meta['front'] = spec['front']
    if 'glow' in res:
        meta['glow'] = res['glow']
    meta.update(spec['extra'])
    with open(os.path.join(cache, key + '.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('[%s] %dx%d anchor %s  %d frame(s)  %.1fs' % (key, W, H, anchor, len(frames), time.time() - t0), flush=True)
    return meta


def bench_seats(cache):
    """Seat points for the EXISTING props bench, measured from its geometry (prop_assets.b_bench is
    built unchanged; nothing is rendered or written to assets/props)."""
    import prop_assets as PA
    bc.reset_scene()
    L._CUSTOM.clear()
    spec = PA.ASSETS['bench']
    spec['fn']()
    L.rotate_all(spec['yaw'])
    bpy.context.view_layer.update()
    seats = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('seat')]
    pts = L.world_points(seats)
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    top, front, back = max(zs), min(ys), max(ys)
    x0, x1 = min(xs), max(xs)
    half = (x1 - x0) / 2.0
    sx = round(half * 0.5, 3)                      # two seats, a quarter of the length from each end
    seat_world = [Vector((cx, front + 0.02, top)) for cx in (-sx, sx)]
    pet = Vector(((x0 + x1) / 2.0, (front + back) / 2.0, top))
    meta = {
        'build': 'bench_seats', 'of': 'bench', 'measured': {
            'seatTopM': round(top, 3), 'seatFrontYM': round(front, 3), 'seatBackYM': round(back, 3),
            'lengthM': round(x1 - x0, 3), 'seatXM': [-sx, sx]},
        'seatPoints': [px(p) for p in seat_world],
        'seatDirs': [screen_dir(Vector((0, -1, 0))) for _ in seat_world],
        'petPoints': [px(pet)],
        'seatDepth': 'front',
        'notes': 'Seat points for the existing props bench (not re-rendered): 2 seats on the front (-Y, screen '
                 'down-left) edge, sitters face SW (sit_SE flipped). petPoints = middle of the seat (cat loaf). '
                 'Bench seat top is %.2f m (sit poses are modelled for 0.45 m: legs dangle a little more).' % top,
    }
    with open(os.path.join(cache, 'bench_seats.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('[bench_seats] top %.3f front %.3f  seats %s pet %s' % (top, front, meta['seatPoints'], meta['petPoints']))
    return meta


def cached(spec, cache):
    side = os.path.join(cache, spec['key'] + '.json')
    if not os.path.exists(side):
        return False
    try:
        meta = json.load(open(side))
    except Exception:
        return False
    return all(os.path.exists(os.path.join(cache, n + '.png')) for n in meta.get('frames', []))


def main():
    opts = parse(bc.script_args())
    keys = select(opts['keys'])
    if opts['list']:
        for k in keys:
            s = LA.LIFE.get(k)
            print(k, '(pseudo)' if s is None else '%s yaw %s -> %s' % (s['kind'], s['yaw'], ', '.join(s['sprites'])))
        return
    os.makedirs(opts['cache'], exist_ok=True)
    for k in keys:
        if k == 'bench_seats':
            if opts['force'] or not os.path.exists(os.path.join(opts['cache'], 'bench_seats.json')):
                bench_seats(opts['cache'])
            else:
                print('[bench_seats] cached')
            continue
        spec = LA.LIFE[k]
        if not opts['force'] and cached(spec, opts['cache']):
            print('[%s] cached' % k)
            continue
        render_build(spec, opts['cache'], opts['samples'])


if __name__ == '__main__':
    main()
