"""
char_render.py - render Frost Village character frames with Blender (Cycles).

Re-run (build machine, bpy module):
    /tmp/bvenv/bin/python tools/blender/char_render.py -- --chars all
On your PC with Blender installed:
    blender -b -P tools/blender/char_render.py -- --chars player,deer

Options (after the literal --):
    --chars  all | comma list of keys (player,fisherman,lumberjack,farmer,miner,hunter,
             villager_a,villager_b,villager_c,deer,boar)
    --anims  all | comma list (idle,walk,...)     --dirs all | S,SE,E,NE,N
    --frames all | comma list of frame indices    --samples 24
    --cache  raw frame folder (default /tmp/fv_cache/characters)
    --force  re-render frames that already exist (otherwise resumable: skips them)
    --portraits   also render 128x128 head-and-shoulder portraits (S) and the hunter's
                  flying-arrow sprite
    --keyart      render the 512x512 player key art
    --only-extras render only portraits / key art (skip frames)
    --meta-only   only rebuild <cache>/<key>/meta.json (carry/impact points), no rendering

Output: <cache>/<key>/<anim>_<dir>_<i>.png (128x128 RGBA, anchor (64,104)) plus
<cache>/<key>/meta.json (carryPoint, impactPoint, ...).

Full character pipeline (about 10-15 min on 4 cores):
    /tmp/bvenv/bin/python tools/blender/char_render.py -- --chars all --portraits --keyart
    python3 tools/blender/char_pack.py        # atlases + manifest + docs/previews (pip install imagequant)
    python3 tools/blender/char_check.py       # verifies every frame name / budget
After changing a model or pose, add --force (renders are skipped when the PNG exists).

Modules: char_geo.py (bmesh shapes + Rig with IK), char_build.py (humans, tools),
char_animals.py (deer, boar), char_anim.py (all poses, pure python),
char_extras.py (portraits, key art).
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy                       # noqa: E402
import bl_common as bc           # noqa: E402
import char_build                # noqa: E402
import char_anim                 # noqa: E402

FRAME = 128
ANCHOR = (64, 104)
DEFAULT_CACHE = '/tmp/fv_cache/characters'


def setup_scene(samples):
    sc = bc.setup_render(FRAME, FRAME, samples=samples, denoise=True)
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 4
    sc.cycles.adaptive_threshold = 0.02
    sc.render.use_persistent_data = True
    bc.setup_camera(FRAME, FRAME, ANCHOR)
    bc.setup_lighting()
    return sc


def parse_args():
    a = bc.script_args()
    opt = {'chars': 'player', 'anims': 'all', 'dirs': 'all', 'frames': 'all', 'samples': '24',
           'cache': DEFAULT_CACHE, 'force': False, 'portraits': False, 'keyart': False,
           'only-extras': False, 'meta-only': False}
    i = 0
    while i < len(a):
        k = a[i].lstrip('-')
        if k in ('force', 'portraits', 'keyart', 'only-extras', 'meta-only'):
            opt[k] = True
            i += 1
        else:
            opt[k] = a[i + 1]
            i += 2
    return opt


def render_character(key, opt):
    t0 = time.time()
    kind, anims = char_build.anims_for(key)
    dirs = bc.RENDER_DIRS if opt['dirs'] == 'all' else opt['dirs'].split(',')
    want = list(anims) if opt['anims'] == 'all' else [x for x in opt['anims'].split(',') if x in anims]
    outdir = os.path.join(opt['cache'], key)
    os.makedirs(outdir, exist_ok=True)
    todo = []
    for anim in want:
        n = anims[anim]['frames']
        frames = range(n) if opt['frames'] == 'all' else [int(f) for f in opt['frames'].split(',') if int(f) < n]
        for d in dirs:
            for i in frames:
                path = os.path.join(outdir, f'{anim}_{d}_{i}.png')
                if opt['force'] or not os.path.exists(path):
                    todo.append((anim, d, i, n, path))
    rig = char_build.build(key)
    sc = setup_scene(int(opt['samples']))
    write_meta(key, rig, kind, anims, outdir)
    if opt['meta-only']:
        print(f'[{key}] meta written', flush=True)
        return rig
    print(f'[{key}] {len(todo)} frames to render', flush=True)
    for k, (anim, d, i, n, path) in enumerate(todo):
        pose = char_anim.pose_for(kind, anim, i, n, key)
        rig.apply(pose, yaw_deg=bc.DIR_YAW[d])
        rig.update_strings()
        tmp = path + '.tmp.png'
        bc.render_to(tmp)
        os.replace(tmp, path)
        if k % 10 == 0:
            print(f'[{key}] {k + 1}/{len(todo)} {anim}_{d}_{i}  {time.time() - t0:.0f}s', flush=True)
    print(f'[{key}] done in {time.time() - t0:.0f}s', flush=True)
    return rig


def write_meta(key, rig, kind, anims, outdir):
    meta = {'key': key, 'kind': kind, 'anims': anims, 'frameSize': [FRAME, FRAME],
            'anchor': [ANCHOR[0] / FRAME, ANCHOR[1] / FRAME]}
    if kind == 'human' and ('carry_idle' in anims or 'carry_walk' in anims):
        meta['carryPoint'] = carry_points(rig, kind, key)
    if kind == 'human':
        for anim, info in anims.items():
            if 'impactFrame' in info:
                info['impactPoint'] = impact_points(rig, kind, key, anim, info)
    meta['shadow'] = rig.meta.get('shadow', [46, 18])
    with open(os.path.join(outdir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)


IMPACT_TOOL = {'chop': 'axe', 'mine': 'pickaxe', 'harvest': None,
               'lumberjack': 'axe', 'miner': 'pickaxe', 'farmer': 'sickle', 'fisherman': 'rod',
               'hunter': 'bow'}


def impact_points(rig, kind, key, anim, info):
    """Pixel offset from the anchor of the tool's business end at impactFrame
    (axe blade, pick tip, sickle blade, bobber splash, arrow launch, hands for
    harvest) - lets the game spawn chips/sparks/splash exactly there."""
    tool = IMPACT_TOOL.get(anim if anim != 'work' else key)
    pose = char_anim.pose_for(kind, anim, info['impactFrame'], info['frames'], key)
    out = {}
    for d in bc.RENDER_DIRS:
        rig.meta.pop('fx_point', None)
        rig.apply(pose, yaw_deg=bc.DIR_YAW[d])
        rig.update_strings()
        bpy.context.view_layer.update()
        if tool == 'rod':
            p = rig.meta['fx_point']
        elif tool:
            p = rig.meta['fx'][tool].matrix_world.translation
        else:
            p = (rig.world('hand_R') + rig.world('hand_L')) * 0.5
        px = bc.world_to_pixel(tuple(p), FRAME, FRAME, ANCHOR)
        out[d] = [round(px[0] - ANCHOR[0]), round(px[1] - ANCHOR[1])]
    return out


def carry_points(rig, kind, key):
    """Pixel offset (from the anchor) of the point where the carried stack's
    bottom sits: midway between the palms, on top of the mittens."""
    out = {}
    pose = char_anim.pose_for(kind, 'carry_idle', 0, 4, key)
    for d in bc.RENDER_DIRS:
        rig.apply(pose, yaw_deg=bc.DIR_YAW[d])
        bpy.context.view_layer.update()
        a = rig.world('hand_R')
        b = rig.world('hand_L')
        mid = (a + b) * 0.5
        mid.z += 0.05
        px = bc.world_to_pixel(tuple(mid), FRAME, FRAME, ANCHOR)
        out[d] = [round(px[0] - ANCHOR[0]), round(px[1] - ANCHOR[1]), d in ('NE', 'N')]
    return out


def main():
    opt = parse_args()
    keys = char_build.ALL_KEYS if opt['chars'] == 'all' else opt['chars'].split(',')
    for key in keys:
        if not opt['only-extras']:
            render_character(key, opt)
        if opt['portraits'] and char_build.anims_for(key)[0] == 'human':
            import char_extras
            char_extras.render_portrait(key, opt)
            if key == 'hunter':
                char_extras.render_arrow(opt)
    if opt['keyart']:
        import char_extras
        char_extras.render_keyart(opt)


if __name__ == '__main__':
    main()
