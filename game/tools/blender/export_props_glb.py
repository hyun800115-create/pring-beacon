"""
export_props_glb.py - 서리마을 소품·건물·자연물·물건·생활 소품을 3D 게임용 GLB 로 내보낸다.

    ../.cache/venv/Scripts/python.exe tools/blender/export_props_glb.py -- [키 ...]      (없으면 전부)

같은 재질끼리 메쉬를 합쳐 그리기 횟수를 줄인다. 원점 = 바닥 가운데(발자국 중심), 단위 m, +Y 위(glTF).
출력: assets3d/props/<key>.glb, assets3d/props/index.json (키 → 발자국 크기·종류)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))

import bpy                    # noqa: E402
import bl_common as bc        # noqa: E402
import prop_lib as L          # noqa: E402
import prop_assets as A       # noqa: E402

GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(GAME, 'assets3d', 'props')


def registries():
    reg = dict(A.ASSETS)
    try:
        import life_assets as LA
        reg.update(LA.LIFE if hasattr(LA, 'LIFE') else getattr(LA, 'ASSETS', {}))
    except Exception as e:  # 생활 소품이 없어도 계속
        print('life_assets skipped:', e)
    return reg


def clean_scene():
    for o in list(bpy.data.objects):
        if o.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        n = o.name.lower()
        if 'catcher' in n or 'shadow' in n:
            bpy.data.objects.remove(o, do_unlink=True)


def merge_by_material():
    bpy.context.view_layer.update()   # 부모-자식 위치 계산을 먼저 새로 고친다
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get()]
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and not o.visible_get()]:
        bpy.data.objects.remove(o, do_unlink=True)
    # 모든 변형을 굳혀 부모 없는 메쉬로 만든 뒤, 하나로 합친다 (glTF 가 재질별로 나눠 준다)
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        if o.data.users > 1:
            o.data = o.data.copy()
    if not meshes:
        return 0
    for o in meshes:
        for m in o.modifiers:
            try:
                with bpy.context.temp_override(object=o, active_object=o):
                    bpy.ops.object.modifier_apply(modifier=m.name)
            except Exception:
                pass
    for o in list(meshes):
        if o.hide_render:
            meshes.remove(o)
            bpy.data.objects.remove(o, do_unlink=True)
    if not meshes:
        return 0
    with bpy.context.temp_override(active_object=meshes[0], selected_editable_objects=meshes, selected_objects=meshes):
        bpy.ops.object.join()
    ob = meshes[0]
    with bpy.context.temp_override(active_object=ob, selected_editable_objects=[ob], selected_objects=[ob], object=ob):
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # 면 방향을 바깥쪽으로 (거울 복사 등으로 뒤집힌 면 바로잡기)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY':
            bpy.data.objects.remove(o, do_unlink=True)
    return len(ob.data.materials)


def bake_to_texture(ob, key):
    """재질 무늬(나무결·벽돌·눈 등 계산 무늬 포함)를 한 장의 그림으로 구워 재질 하나로 바꾼다."""
    import math
    dims = ob.dimensions
    big = max(dims.x, dims.y, dims.z)
    size = 256 if big < 0.8 else 512 if big < 2.0 else 1024 if big < 4.5 else 2048
    # 펼치기(UV)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    while ob.data.uv_layers:
        ob.data.uv_layers.remove(ob.data.uv_layers[0])
    ob.data.uv_layers.new(name='bake')
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    img = bpy.data.images.new(key + '_col', size, size, alpha=False)
    emit = {}
    for slot in ob.material_slots:
        m = slot.material
        if not m:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is not None:
            e = bsdf.inputs.get('Emission Strength')
            if e is not None and e.default_value > 0.05:
                emit[m.name] = True
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = img
        nt.nodes.active = node
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 8
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    sc.render.bake.margin = 6
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, target='IMAGE_TEXTURES', margin=6)
    img.pack()
    # 재질 하나로 바꾸기 (빛나는 창문 등은 따로 남김)
    nm = bpy.data.materials.new(key + '_baked')
    nm.use_nodes = True
    nt = nm.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.8
    keep = [sl.material for sl in ob.material_slots if sl.material and sl.material.name in emit]
    old = [sl.material for sl in ob.material_slots]
    idx_map = {}
    ob.data.materials.clear()
    ob.data.materials.append(nm)
    for m in keep:
        ob.data.materials.append(m)
    for i, m in enumerate(old):
        idx_map[i] = (1 + keep.index(m)) if m in keep else 0
    for poly in ob.data.polygons:
        poly.material_index = idx_map.get(poly.material_index, 0)
    return size


def export(key, spec):
    t0 = time.time()
    bc.reset_scene()
    try:
        L._CUSTOM.clear()
    except Exception:
        pass
    res = spec['fn']() or {}
    if 'idle' in res:
        try:
            res['idle']()
        except Exception:
            pass
    try:
        L.rotate_all(spec.get('yaw', 0.0))
    except Exception:
        pass
    clean_scene()
    nmat = merge_by_material()
    tex = 0
    obs = [o for o in bpy.data.objects if o.type == 'MESH']
    if obs and '--nobake' not in sys.argv:
        tex = bake_to_texture(obs[0], key)
        nmat = len(obs[0].data.materials)
    path = os.path.join(OUT, key + '.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                              export_animations=False, export_cameras=False, export_lights=False)
    fp = spec.get('fp')
    info = {'kind': spec.get('kind'), 'fp': list(fp) if fp else None, 'front': spec.get('front'), 'mats': nmat, 'tex': tex,
            'kb': os.path.getsize(path) // 1024}
    print(f'[{key}] {nmat} materials, {info["kb"]} KB, {time.time() - t0:.1f}s', flush=True)
    return info


def main():
    keys = [a for a in bc.script_args() if not a.startswith('--')]
    reg = registries()
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, 'index.json')
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    todo = keys or list(reg)
    for k in todo:
        if k not in reg:
            print('unknown', k)
            continue
        try:
            index[k] = export(k, reg[k])
        except Exception as e:
            print(f'[{k}] FAILED: {e}', flush=True)
    with open(idx_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
