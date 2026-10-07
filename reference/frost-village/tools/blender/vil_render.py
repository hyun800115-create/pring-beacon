"""
vil_render.py - render Frost Village villagers & pets (Blender Cycles).

Re-run (build machine, bpy module):
    /tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars all --portraits
On your PC with Blender installed:
    blender -b -P tools/blender/vil_render.py -- --chars npc_grandpa,pet_dog

Options (after the literal --):
    --chars   all | comma list of keys (see vil_build.ALL_KEYS)
    --anims   all | comma list         --dirs all | S,SE,E,NE,N   --frames all | 0,3
    --samples 20                       --cache /tmp/fv_cache/villagers
    --force   re-render existing frames (default: resumable, skips PNGs that exist)
    --portraits    also render 128x128 portraits (UI camera, like char_extras)
    --only-extras  portraits only           --meta-only  only rewrite <cache>/<key>/meta.json
    --lookdev      expression look-dev: <cache>/_lookdev/<key>_<face>.png (game scale)
                   and <key>_<face>_zoom.png (head close-up), for vil_lookdev.py

Output: <cache>/<key>/<anim>_<dir>_<i>.png (128x128 RGBA, anchor (64,104)),
<cache>/<key>/meta.json (anims+dirs, carryPoint, throw impactPoint, seatOffset, shadow),
<cache>/<key>/portrait.png.
Then: python3 tools/blender/vil_pack.py  &&  python3 tools/blender/vil_check.py

Modules: vil_face.py (expression parts), vil_body.py (body types), vil_dress.py
(hair/hats/outfits/props), vil_pets.py, vil_anim.py (poses + faces, pure python),
vil_build.py (roster).  Shares bl_common / char_geo / char_build with the base cast.
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
from mathutils import Vector     # noqa: E402
import bl_common as bc           # noqa: E402
import vil_build                 # noqa: E402
import vil_anim as va            # noqa: E402

FRAME = 128
ANCHOR = (64, 104)
DEFAULT_CACHE = '/tmp/fv_cache/villagers'


def setup_scene(samples, w=FRAME, h=FRAME, anchor=ANCHOR, ppu=bc.PPU, target=(0, 0, 0)):
    sc = bc.setup_render(w, h, samples=samples, denoise=True)
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 4
    sc.cycles.adaptive_threshold = 0.02
    sc.render.use_persistent_data = True
    bc.setup_camera(w, h, anchor, ppu=ppu, target=target)
    bc.setup_lighting()
    return sc


def parse_args():
    a = bc.script_args()
    opt = {'chars': 'npc_grandpa', 'anims': 'all', 'dirs': 'all', 'frames': 'all', 'samples': '20',
           'cache': DEFAULT_CACHE, 'force': False, 'portraits': False, 'only-extras': False,
           'meta-only': False, 'lookdev': False, 'faces': 'all'}
    i = 0
    while i < len(a):
        k = a[i].lstrip('-')
        if k in ('force', 'portraits', 'only-extras', 'meta-only', 'lookdev'):
            opt[k] = True
            i += 1
        else:
            opt[k] = a[i + 1]
            i += 2
    return opt


def apply(rig, pose, d):
    rig.apply(pose, yaw_deg=bc.DIR_YAW[d])
    rig.update_strings()


def render_character(key, opt):
    t0 = time.time()
    anims = vil_build.anims_for(key)
    want = list(anims) if opt['anims'] == 'all' else [x for x in opt['anims'].split(',') if x in anims]
    outdir = os.path.join(opt['cache'], key)
    os.makedirs(outdir, exist_ok=True)
    todo = []
    for anim in want:
        info = anims[anim]
        dirs = info['dirs'] if opt['dirs'] == 'all' else [d for d in opt['dirs'].split(',') if d in info['dirs']]
        n = info['frames']
        frames = range(n) if opt['frames'] == 'all' else [int(f) for f in opt['frames'].split(',') if int(f) < n]
        for d in dirs:
            for i in frames:
                path = os.path.join(outdir, f'{anim}_{d}_{i}.png')
                if opt['force'] or not os.path.exists(path):
                    todo.append((anim, d, i, path))
    rig = vil_build.build(key)
    setup_scene(int(opt['samples']))
    write_meta(key, rig, anims, outdir)
    if opt['meta-only']:
        print(f'[{key}] meta written', flush=True)
        return rig
    print(f'[{key}] {len(todo)} frames to render', flush=True)
    for k, (anim, d, i, path) in enumerate(todo):
        apply(rig, vil_build.pose_for(rig, anim, i, d), d)
        tmp = path + '.tmp.png'
        bc.render_to(tmp)
        os.replace(tmp, path)
        if k % 20 == 0:
            print(f'[{key}] {k + 1}/{len(todo)} {anim}_{d}_{i}  {time.time() - t0:.0f}s', flush=True)
    print(f'[{key}] done in {time.time() - t0:.0f}s', flush=True)
    return rig


def px_off(p):
    px = bc.world_to_pixel(tuple(p), FRAME, FRAME, ANCHOR)
    return [round(px[0] - ANCHOR[0]), round(px[1] - ANCHOR[1])]


def write_meta(key, rig, anims, outdir):
    meta = {'key': key, 'kind': 'pet' if key in vil_build.PET_KEYS else 'villager',
            'anims': {a: dict(v) for a, v in anims.items()}, 'frameSize': [FRAME, FRAME],
            'anchor': [ANCHOR[0] / FRAME, ANCHOR[1] / FRAME], 'shadow': rig.meta.get('shadow', [46, 18])}
    if 'carry_walk' in anims:
        cp = {}
        for d in anims['carry_walk']['dirs']:
            apply(rig, vil_build.pose_for(rig, 'carry_walk', 0, d), d)
            bpy.context.view_layer.update()
            mid = (rig.world('hand_R') + rig.world('hand_L')) * 0.5
            mid.z += 0.05
            cp[d] = px_off(mid) + [d in ('NE', 'N')]
        meta['carryPoint'] = cp
    if 'throw' in anims:
        info = meta['anims']['throw']
        ip = {}
        for d in info['dirs']:
            apply(rig, vil_build.pose_for(rig, 'throw', info['impactFrame'], d), d)
            bpy.context.view_layer.update()
            # snowball centre if it were still in the hand = release point
            p = rig.j['hand_R'].matrix_world @ Vector((0.0, -0.045, -0.02))
            ip[d] = px_off(p)
        info['impactPoint'] = ip
    if 'sit' in anims and key not in vil_build.PET_KEYS:          # pets sit on the ground (plain anchor)
        meta['seatOffset'] = [0, 0]
        meta['seatHeightPx'] = round(va.SEAT_H * bc.VERTICAL_SCALE * bc.PPU)
    with open(os.path.join(outdir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)


# --------------------------------------------------------------------------- portraits

def ui_camera(w, h, ppu, target, elev_deg=15.0, yaw_deg=45.0, anchor_px=None):
    import char_extras
    return char_extras.ui_camera(w, h, ppu, target, elev_deg=elev_deg, yaw_deg=yaw_deg, anchor_px=anchor_px)


PORTRAIT_PPU = {'npc_fashion': 104, 'npc_merchant': 112, 'npc_kid_girl': 120, 'npc_teen_girl': 124,
                'npc_young_man': 120, 'npc_bard': 116, 'npc_kid_boy': 124, 'pet_dog': 150, 'pet_cat': 160,
                'pet_penguin': 150}


def render_portrait(key, opt):
    out = os.path.join(opt['cache'], key, 'portrait.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out) and not opt['force']:
        return out
    rig = vil_build.build(key)
    sc = bc.setup_render(128, 128, samples=max(48, int(opt['samples'])), denoise=True)
    sc.cycles.max_bounces = 4
    bc.setup_lighting()
    pose = vil_build.pose_for(rig, 'idle', 0, 'S')
    if key not in vil_build.PET_KEYS:
        pose['head'] = (4, 0, 0)
        pose['_show'] = vil_build.show_set(rig, 'smile', pose['_show'] & {'cane', 'lute_back'})
    else:
        pose['_show'] = vil_build.show_set(rig, 'pet_happy', set())
    rig.apply(pose, yaw_deg=bc.DIR_YAW['S'] - 12)
    rig.update_strings()
    bpy.context.view_layer.update()
    if key in vil_build.PET_KEYS:
        tz = rig.world('head').z - 0.05
    else:
        hs = rig.meta['body']['head']
        tz = rig.world('head').z + 0.27 * hs - 0.02
    ui_camera(128, 128, PORTRAIT_PPU.get(key, 128), (0, 0, tz), anchor_px=(64, 70))
    bc.render_to(out)
    print(f'[{key}] portrait -> {out}', flush=True)
    return out


# --------------------------------------------------------------------------- look-dev

LOOKDEV_FACES = ['neutral', 'blink', 'smile', 'happy', 'laugh', 'talk_open', 'talk_mid', 'surprised', 'angry',
                 'angry_shout', 'sad', 'hurt', 'sleepy', 'shiver', 'sing', 'heart', 'scheme']


def render_lookdev(key, opt):
    """Game-scale (128px world camera) + zoomed head close-ups of each expression."""
    out = os.path.join(opt['cache'], '_lookdev')
    os.makedirs(out, exist_ok=True)
    rig = vil_build.build(key)
    faces = LOOKDEV_FACES if opt['faces'] == 'all' else opt['faces'].split(',')
    setup_scene(int(opt['samples']))
    for zoom in (False, True):
        if zoom:
            for obj in [o for o in bpy.data.objects if o.type == 'CAMERA']:
                bpy.data.objects.remove(obj)
            pose = vil_build.pose_for(rig, 'idle', 0, 'S')
            apply(rig, pose, 'S')
            bpy.context.view_layer.update()
            hs = rig.meta.get('body', {}).get('head', 1.0)
            hc = rig.j['head'].matrix_world @ Vector((0, 0, 0.27 * hs - 0.03))
            sc = bpy.context.scene
            sc.render.resolution_x = sc.render.resolution_y = 160
            sc.cycles.samples = int(opt['samples']) + 12
            bc.setup_camera(160, 160, (80, 80), ppu=230, target=tuple(hc))
        for fc in faces:
            for d in (('S', 'E') if not zoom else ('S',)):
                pose = vil_build.pose_for(rig, 'idle', 0, d)
                pose['_show'] = vil_build.show_set(rig, fc, pose['_show'] & {'cane', 'lute_back'})
                if d == 'E':
                    pose['head'] = (0, 0, -20)
                    pose['spine'] = (0, 0, -9)
                apply(rig, pose, d)
                path = os.path.join(out, f'{key}_{fc}_{d}{"_zoom" if zoom else ""}.png')
                bc.render_to(path)
        print(f'[{key}] lookdev zoom={zoom} done', flush=True)


def main():
    opt = parse_args()
    keys = vil_build.ALL_KEYS if opt['chars'] == 'all' else opt['chars'].split(',')
    for key in keys:
        if opt['lookdev']:
            render_lookdev(key, opt)
            continue
        if not opt['only-extras']:
            render_character(key, opt)
        if opt['portraits']:
            render_portrait(key, opt)


if __name__ == '__main__':
    main()
