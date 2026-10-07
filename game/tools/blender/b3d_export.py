"""
b3d_export.py - build + export the 3D buildings and furniture (docs/CONTRACT3D.md).

    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_export.py -- [keys...] [--furniture] [--buildings]

No keys = everything.  Writes
    assets3d/buildings/<key>.glb + <key>.json, assets3d/buildings/index.json
    assets3d/furniture/<key>.glb, assets3d/furniture/index.json
and prints node / triangle / slot statistics (read back from the written GLB).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,F401
import bl_common as bc  # noqa: E402
import b3d_kit as K  # noqa: E402
import b3d_furniture as F  # noqa: E402
import b3d_buildings as B  # noqa: E402

TRI_B, TRI_F, MAT_MAX = 60000, 3000, 30


def export_furniture(key):
    t0 = time.time()
    K.reset()
    fn, kw = F.FURNITURE[key]
    with K.grp(key):
        fn(**kw)
    nodes = K.finalize(low=False)
    K._limit_materials(list(nodes.values()), MAT_MAX)
    slots, fxl = K.write_empties(furniture=True)
    path = os.path.join(K.OUT_F, key + '.glb')
    K.export_glb(path)
    info = K.glb_info(path)
    ob = nodes[key]
    dims = ob.dimensions
    ok = info['total'] <= TRI_F
    print('[furn %-16s] tris %5d  mats %2d  slots %d  %.1fs %s' % (key, info['total'], info['mats'], len(slots),
                                                                   time.time() - t0, '' if ok else 'OVER BUDGET'),
          flush=True)
    return dict(tris=info['total'], mats=info['mats'], slots=[s['id'] for s in slots],
                size=[round(dims.x, 2), round(dims.y, 2)], height=round(dims.z, 2))


def export_building(key):
    t0 = time.time()
    K.reset()
    spec = B.BUILDINGS[key]
    spec['fn']()
    nodes = K.finalize(low=spec.get('low', True))
    nm = K._limit_materials(list(nodes.values()), MAT_MAX)
    height = K.scene_height(nodes)
    slots, fxl = K.write_empties()
    path = os.path.join(K.OUT_B, key + '.glb')
    K.export_glb(path)
    info = K.glb_info(path)
    side = dict(key=key, name=spec['name'], category=spec['cat'], size=list(spec['size']), height=height,
                rooms=K.S.rooms, slots=slots, door=K.S.door, levels=1, fx=fxl,
                nodes=sorted(n for n in info['tris']), tris=info['total'])
    with open(os.path.join(K.OUT_B, key + '.json'), 'w', encoding='utf-8') as f:
        json.dump(side, f, ensure_ascii=False, indent=1)
    need = ['roof', 'walls', 'floor', 'interior', 'exterior']
    if spec.get('low', True):
        need += ['walls_low']
    missing = [n for n in need if n not in info['nodes']]
    acts = {}
    for s in slots:
        acts[s['action']] = acts.get(s['action'], 0) + 1
    print('[bld %-11s] tris %6d  mats %2d  slots %2d %s  nodes %s  %s%s  %.1fs' % (
        key, info['total'], info['mats'], len(slots), acts,
        {k: v for k, v in info['tris'].items()}, 'MISSING ' + str(missing) if missing else '',
        ' OVER BUDGET' if info['total'] > TRI_B or info['mats'] > MAT_MAX else '', time.time() - t0), flush=True)
    return dict(key=key, name=spec['name'], category=spec['cat'], size=list(spec['size']), height=height,
                tris=info['total'], mats=info['mats'], slots=len(slots))


def main():
    args = bc.script_args()
    keys = [a for a in args if not a.startswith('--')]
    do_f = '--furniture' in args or not ('--buildings' in args)
    do_b = '--buildings' in args or not ('--furniture' in args)
    os.makedirs(K.OUT_B, exist_ok=True)
    os.makedirs(K.OUT_F, exist_ok=True)
    if do_b:
        idx_path = os.path.join(K.OUT_B, 'index.json')
        old = {}
        if os.path.exists(idx_path):
            try:
                old = {e['key']: e for e in json.load(open(idx_path, encoding='utf-8'))}
            except Exception:
                old = {}
        todo = [k for k in (keys or list(B.BUILDINGS)) if k in B.BUILDINGS]
        for k in todo:
            try:
                old[k] = export_building(k)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print('[bld %s] FAILED: %s' % (k, e), flush=True)
        out = [dict(key=e['key'], name=e['name'], category=e['category'], size=e['size'], height=e['height'])
               for k, e in sorted(old.items(), key=lambda kv: list(B.BUILDINGS).index(kv[0])
                                  if kv[0] in B.BUILDINGS else 99)]
        with open(idx_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    if do_f:
        idx_path = os.path.join(K.OUT_F, 'index.json')
        old = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
        todo = [k for k in (keys or list(F.FURNITURE)) if k in F.FURNITURE]
        for k in todo:
            try:
                old[k] = export_furniture(k)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print('[furn %s] FAILED: %s' % (k, e), flush=True)
        with open(idx_path, 'w', encoding='utf-8') as f:
            json.dump(old, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
