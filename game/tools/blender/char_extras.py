"""
char_extras.py - hire-UI portraits (128x128) and the 512x512 player key art.

Called from char_render.py (--portraits / --keyart), e.g.
    .cache/venv/Scripts/python.exe tools/blender/char_render.py -- --chars all --portraits --only-extras --keyart
    blender -b -P tools/blender/char_render.py -- --chars player --portraits --keyart --only-extras

Portraits are UI pictures, not world sprites, so they use a friendlier,
lower camera (15 deg instead of the 30 deg world camera) with the same
lighting and materials.  Output goes to the raw cache (<cache>/<key>/portrait.png
and <cache>/player/keyart_512.png); char_pack.py copies them into assets/.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy                          # noqa: E402
from mathutils import Vector, Euler  # noqa: E402
import bl_common as bc              # noqa: E402
import char_build                   # noqa: E402
import char_anim                    # noqa: E402

# per-character framing tweaks (ppu, target z) - wide hats need a little more room
PORTRAIT_FIT = {
    'farmer': (116, 1.03), 'fisherman': (124, 1.03), 'villager_b': (124, 1.04),
}


def ui_camera(w, h, ppu, target, elev_deg=15.0, yaw_deg=45.0, anchor_px=None):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new('UICam')
    cd.type = 'ORTHO'
    big = max(w, h)
    cd.ortho_scale = big / ppu
    if anchor_px:
        cd.shift_x = -(anchor_px[0] - w / 2.0) / big
        cd.shift_y = (anchor_px[1] - h / 2.0) / big
    cam = bpy.data.objects.new('UICam', cd)
    sc.collection.objects.link(cam)
    rot = Euler((math.radians(90.0 - elev_deg), 0.0, math.radians(yaw_deg)), 'XYZ')
    cam.rotation_euler = rot
    cam.location = Vector(target) + (rot.to_matrix() @ Vector((0, 0, 1))) * 60.0
    sc.camera = cam
    return cam


def _setup(w, h, samples):
    sc = bc.setup_render(w, h, samples=samples, denoise=True)
    sc.cycles.max_bounces = 4
    sc.cycles.adaptive_threshold = 0.01
    bc.setup_lighting()
    return sc


def render_portrait(key, opt):
    out = os.path.join(opt['cache'], key, 'portrait.png')
    if os.path.exists(out) and not opt['force']:
        return out
    rig = char_build.build(key)
    _setup(128, 128, max(48, int(opt['samples'])))
    ppu, tz = PORTRAIT_FIT.get(key, (128, 1.02))
    ui_camera(128, 128, ppu, (0, 0, tz), anchor_px=(64, 70))
    pose = char_anim.pose_for('human', 'idle', 0, 4, key)
    pose['head'] = (-4, 0, 0)
    pose['_show'] = {'face_smile'}
    rig.apply(pose, yaw_deg=bc.DIR_YAW['S'] - 12)
    rig.update_strings()
    bc.render_to(out)
    print(f'[{key}] portrait -> {out}', flush=True)
    return out


def render_keyart(opt):
    out = os.path.join(opt['cache'], 'player', 'keyart_512.png')
    if os.path.exists(out) and not opt['force']:
        return out
    rig = char_build.build('player')
    _setup(512, 512, 96)
    ui_camera(512, 512, 300, (0, 0, 0.0), elev_deg=14.0, anchor_px=(250, 478))
    pose = char_anim.pose_for('human', 'idle', 0, 4, 'player')
    pose.update({
        'ik_R': (-0.42, -0.14, 0.20, -1.0, 0.2, -1.0), 'hand_R': (15, 0, 30),    # wave beside the face
        'ik_L': (0.235, 0.02, -0.26),                                        # fist on the hip
        'spine': (-2, 6, 6), 'head': (-6, -8, 4),
        'hip_R': (4, 7, 0), 'hip_L': (-3, 9, 0),
    })
    pose['_show'] = {'face_smile'}
    rig.apply(pose, yaw_deg=bc.DIR_YAW['S'] - 18)
    rig.update_strings()
    bc.render_to(out)
    print(f'[player] key art -> {out}', flush=True)
    return out


def render_arrow(opt):
    """Flying-arrow sprite for the hunter (64x32, centre anchor, pointing screen
    right = world (1,1,0)/sqrt2, slightly nose-down).  Rotate it in-game to the
    flight direction."""
    import char_geo as g
    out = os.path.join(opt['cache'], 'hunter', 'projectile_arrow.png')
    if os.path.exists(out) and not opt['force']:
        return out
    bc.reset_scene()
    sc = bc.setup_render(64, 32, samples=48, denoise=True)
    bc.setup_camera(64, 32, (32, 16), target=(0, 0, 0.3))
    bc.setup_lighting()
    arrow, _, _ = char_build.make_arrow('proj', scale=1.15)
    d = Vector((1.0, 1.0, -0.12)).normalized()
    g.set_oriented(arrow, Vector((0, 0, 0.3)) - d * 0.345, d)
    bc.render_to(out)
    print(f'[hunter] projectile arrow -> {out}', flush=True)
    return out
