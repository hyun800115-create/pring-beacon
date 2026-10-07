"""
b3d_preview.py - Cycles CPU preview renders of the exported building / furniture GLBs.

    cd game && ../.cache/venv/Scripts/python.exe tools/blender/b3d_preview.py -- [keys...] [--mode ext|cut|both]
           [--samples 16] [--res 1000] [--furniture-sheet] [--no-char] [--angle back]

Writes  .cache/shots/b3d/<key>_ext.png  (exterior 3/4 view, a farmer for scale at the door)
        .cache/shots/b3d/<key>_cut.png  (roof/walls/iwalls hidden, walls_low shown, slot markers:
                                         small discs + arrows = where a resident stands and looks)
        .cache/shots/b3d/furniture_sheet.png
Imports the real GLB files, so it checks what the game will load.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector, Euler  # noqa: E402
import bl_common as bc  # noqa: E402

GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT = os.path.normpath(os.path.join(GAME, '..', '.cache', 'shots', 'b3d'))
BDIR = os.path.join(GAME, 'assets3d', 'buildings')
FDIR = os.path.join(GAME, 'assets3d', 'furniture')
CHAR = os.path.join(GAME, 'assets3d', 'chars', 'farmer.glb')

SLOT_COL = {'sit': '#3D7CC9', 'eat': '#F2C230', 'sleep': '#9A6FC0', 'cook': '#E8893A', 'bake': '#E8893A',
            'warm': '#D9483B', 'read': '#5CA76A', 'desk': '#3FA39A', 'work': '#8A5A33', 'toilet': '#7FB2E5',
            'wash': '#7FB2E5', 'tea': '#F29BB0', 'chat': '#FFFFFF', 'shop': '#F2C14E', 'sell': '#2B2F3A',
            'play': '#F29BB0', 'pray': '#FFFFFF'}


def import_glb(path, loc=(0, 0, 0), rot=0.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    holder = bpy.data.objects.new('holder', None)
    bpy.context.scene.collection.objects.link(holder)
    for o in roots:
        o.parent = holder
    holder.location = loc
    holder.rotation_euler = (0, 0, math.radians(rot))
    bpy.context.view_layer.update()
    return new


def mat(c, emit=0.0):
    return bc.mat('pv_' + c, c, rough=0.6, emission=c if emit else None, emission_strength=emit)


def marker(pos, yaw, c):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.13, depth=0.03, location=(pos[0], pos[1], pos[2] + 0.03))
    d = bpy.context.object
    d.data.materials.append(mat(c, 1.5))
    a = math.radians(yaw)
    fwd = Vector((math.sin(a), -math.cos(a), 0))
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.07, depth=0.22,
                                    location=Vector(pos) + fwd * 0.2 + Vector((0, 0, 0.06)))
    cn = bpy.context.object
    cn.rotation_euler = Vector((0, 0, 1)).rotation_difference(fwd).to_euler()
    cn.data.materials.append(mat(c, 1.5))


def ground(size=40, c='#DCE5DA'):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, -0.002))
    g = bpy.context.object
    g.data.materials.append(bc.mat('pv_ground', c, rough=0.95))


def lights():
    sc = bpy.context.scene
    world = bpy.data.worlds.new('W')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.62, 0.72, 0.9, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sc.world = world
    ld = bpy.data.lights.new('sun', 'SUN')
    ld.energy = 3.2
    ld.angle = math.radians(8)
    ld.color = (1.0, 0.95, 0.86)
    ob = bpy.data.objects.new('sun', ld)
    ob.rotation_euler = Euler((math.radians(42), math.radians(-18), math.radians(-35)), 'XYZ')
    sc.collection.objects.link(ob)


def mesh_bounds(objs):
    pts = []
    for o in objs:
        if o.type == 'MESH' and not o.hide_render:
            pts += [o.matrix_world @ v.co for v in list(o.data.vertices)[::7]]
    if not pts:
        return Vector((0, 0, 0)), 1.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, (hi - lo).length / 2


def camera(center, radius, direction, res=(1000, 760), lens=40.0, fill=1.0):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new('cam')
    cd.lens = lens
    cd.clip_end = 400
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    d = Vector(direction).normalized()
    fov = 2 * math.atan(36 / 2 / lens) * min(1.0, res[1] / res[0])
    dist = radius / math.sin(fov / 2) * fill
    cam.location = center + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    return cam


def setup(samples):
    bc.reset_scene()
    sc = bc.setup_render(1000, 760, samples=samples, denoise=True)
    sc.render.film_transparent = False
    sc.render.image_settings.color_mode = 'RGB'
    sc.cycles.max_bounces = 4
    return sc


def render_building(key, mode, samples, res, with_char=True, angle='front'):
    setup(samples)
    meta = json.load(open(os.path.join(BDIR, key + '.json'), encoding='utf-8'))
    objs = import_glb(os.path.join(BDIR, key + '.glb'))
    names = {o.name: o for o in objs}
    cut = mode in ('cut', 'plan')
    for o in objs:
        base = o.name.split('.')[0] if not o.name.startswith(('slot.', 'door.')) else o.name
        if base in ('walls_low', 'iwalls_low'):
            o.hide_render = not cut
        elif base in ('roof', 'walls', 'iwalls'):
            o.hide_render = cut
    ground()
    lights()
    c, r = mesh_bounds(objs)
    if cut:
        for s in meta['slots']:
            marker(s['pos'], s['yaw'], SLOT_COL.get(s['action'], '#FFFFFF'))
        for k in ('out', 'in'):
            p = meta['door'][k]
            marker((p[0], p[1], 0.12 if k == 'in' else 0.0), 0, '#FFFFFF' if k == 'out' else '#000000')
        if mode == 'plan':
            sc = bpy.context.scene
            cd = bpy.data.cameras.new('cam')
            cd.type = 'ORTHO'
            cd.ortho_scale = max(meta['size'][0], meta['size'][1] * res[0] / res[1]) * 1.08
            cam = bpy.data.objects.new('cam', cd)
            sc.collection.objects.link(cam)
            cam.location = (0, 0, 30)
            sc.camera = cam
            sc.render.resolution_x, sc.render.resolution_y = res
        else:
            direc = (-0.18, -0.45, 1.0)
            camera(Vector((c.x, c.y, 0.5)), max(meta['size']) * 0.62, direc, res, fill=1.0)
    else:
        direc = (-0.75, -1.0, 0.62) if angle == 'front' else (0.8, 1.0, 0.62)
        camera(c, r, direc, res, fill=0.92)
    if with_char and os.path.exists(CHAR):
        if cut:
            # residents at the first two non-sleep slots
            sl = [s for s in meta['slots'] if s['action'] not in ('sleep',)][:2]
            for s in sl:
                import_glb(CHAR, (s['pos'][0], s['pos'][1], s['pos'][2]), s['yaw'])
        else:
            p = meta['door']['out']
            import_glb(CHAR, (p[0] + 0.5, p[1], 0), 0)
    path = os.path.join(OUT, '%s_%s.png' % (key, mode if angle == 'front' else mode + '_back'))
    bc.render_to(path)
    print('wrote', path, flush=True)


def furniture_sheet(samples, res, keys=None):
    setup(samples)
    idx = json.load(open(os.path.join(FDIR, 'index.json'), encoding='utf-8'))
    keys = keys or list(idx)
    cols = 9
    pitch = 2.3
    all_objs = []
    for i, k in enumerate(keys):
        x = (i % cols) * pitch
        y = -(i // cols) * pitch
        all_objs += import_glb(os.path.join(FDIR, k + '.glb'), (x, y, 0))
    ground(200)
    lights()
    c, r = mesh_bounds(all_objs)
    camera(c, r, (-0.35, -1.0, 1.5), (1600, 1100), fill=0.62)
    if os.path.exists(CHAR):
        import_glb(CHAR, (-1.6, 0, 0), 0)
    path = os.path.join(OUT, 'furniture_sheet.png')
    bc.render_to(path)
    print('wrote', path, flush=True)


def main():
    args = bc.script_args()
    mode = 'both'
    samples = 16
    res = 1000
    angle = 'front'
    keys = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--mode':
            mode = args[i + 1]
            i += 1
        elif a == '--samples':
            samples = int(args[i + 1])
            i += 1
        elif a == '--res':
            res = int(args[i + 1])
            i += 1
        elif a == '--out':
            global OUT
            OUT = os.path.abspath(args[i + 1])
            i += 1
        elif a == '--angle':
            angle = args[i + 1]
            i += 1
        elif not a.startswith('--'):
            keys.append(a)
        i += 1
    os.makedirs(OUT, exist_ok=True)
    rs = (res, int(res * 0.76))
    if '--furniture-sheet' in args:
        furniture_sheet(samples, rs, keys or None)
        return
    if not keys:
        keys = [e['key'] for e in json.load(open(os.path.join(BDIR, 'index.json'), encoding='utf-8'))]
    for k in keys:
        for m in (('ext', 'cut') if mode == 'both' else mode.split(',')):
            render_building(k, m, samples, rs, with_char='--no-char' not in args, angle=angle)


if __name__ == '__main__':
    main()
