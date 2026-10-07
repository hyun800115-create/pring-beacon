"""
export_glb.py - 서리마을 캐릭터(주민·일꾼)를 3D 게임용 GLB 로 내보낸다 (동작 포함).

    ../.cache/venv/Scripts/python.exe tools/blender/export_glb.py -- --chars npc_young_man,lumberjack
    ../.cache/venv/Scripts/python.exe tools/blender/export_glb.py -- --chars all

캐릭터는 관절(빈 객체) 계층 + 관절에 붙은 몸 부품(메쉬) 구조다. 동작은 파이썬 포즈로 계산되므로
동작 하나하나를 한 시간줄에 이어서 키프레임으로 굽는다 (동작 i: 프레임 start..end, 마지막 = 처음 포즈라 반복이 매끄럽다).
얼굴 표정·소품 켜기/끄기는 크기(scale) 0/1 계단 키프레임으로 담는다.
출력: assets3d/chars/<key>.glb + <key>.json (동작별 프레임 구간, fps, 손 위치 관절 등)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))

import bpy                       # noqa: E402
import bl_common as bc           # noqa: E402

GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(GAME, 'assets3d', 'chars')

VIL = None
CHR = None


def args():
    a = bc.script_args()
    opt = {'chars': 'npc_young_man', 'dir': 'S'}
    i = 0
    while i < len(a):
        k = a[i].lstrip('-')
        opt[k] = a[i + 1]
        i += 2
    return opt


def is_villager(key):
    return key.startswith('npc_') or key.startswith('pet_')


def build(key):
    global VIL, CHR
    bc.reset_scene()
    if is_villager(key):
        import vil_build
        VIL = vil_build
        rig = vil_build.build(key)
        anims = vil_build.anims_for(key)
        pose = lambda an, i, n: vil_build.pose_for(rig, an, i, 'S')  # noqa: E731
    else:
        import char_build
        import char_anim
        CHR = char_build
        rig = char_build.build(key)
        kind, anims = char_build.anims_for(key)
        pose = lambda an, i, n: char_anim.pose_for(kind, an, i, n, key)  # noqa: E731
    return rig, anims, pose


def join_parts(rig):
    """같은 관절에 붙은 고정 부품(표정·소품 아님)을 한 메쉬로 합쳐 그리기 횟수를 줄인다."""
    bpy.context.view_layer.update()
    member = {}
    for tn, objs in rig.toggles.items():
        for o in objs:
            member.setdefault(o.name, set()).add(tn)
    groups = {}
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.children or o.parent is None:
            continue
        tg = tuple(sorted(member.get(o.name, ())))
        groups.setdefault((o.parent.name, tg), []).append(o)
    n0 = sum(len(g) for g in groups.values())
    keep = {}   # 남는 메쉬 이름 -> 표정 묶음
    for (pname, tg), objs in groups.items():
        if len(objs) >= 2:
            for o in objs:
                if o.data.users > 1:
                    o.data = o.data.copy()
            with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
                bpy.ops.object.join()
            objs[0].name = pname + ('_' + '+'.join(tg) if tg else '_body')
        keep[objs[0].name] = tg
    toggles = {}
    for name, tg in keep.items():
        for tn in tg:
            toggles.setdefault(tn, []).append(bpy.data.objects[name])
    for tn in rig.toggles:
        rig.toggles[tn] = toggles.get(tn, [])
    n1 = len([o for o in bpy.data.objects if o.type == 'MESH'])
    return n0, n1


def bake(rig, anims, pose):
    joints = list(rig.j.values())
    togg = sorted({o for objs in rig.toggles.values() for o in objs}, key=lambda o: o.name)
    for o in togg:
        o.hide_render = False
        o.hide_viewport = False
    clips = {}
    f = 0
    for an, info in anims.items():
        n = int(info['frames'])
        start = f
        for i in list(range(n)) + [0]:
            p = pose(an, i, n)
            rig.apply(p, yaw_deg=0.0)
            try:
                rig.update_strings()
            except Exception:
                pass
            for e in joints:
                e.keyframe_insert('location', frame=f)
                e.keyframe_insert('rotation_quaternion', frame=f)
                e.keyframe_insert('scale', frame=f)
            for o in togg:
                vis = not o.hide_render
                o.hide_render = False
                o.hide_viewport = False
                o.scale = (1, 1, 1) if vis else (0, 0, 0)
                o.keyframe_insert('scale', frame=f)
            f += 1
        clips[an] = {'start': start, 'end': f - 1, 'frames': n, 'fps': info.get('fps', 8),
                     'loop': info.get('repeat', -1) == -1}
        f += 1   # 동작 사이 한 칸 띄움
    # 표정 키는 계단식(보간 없음)
    for o in togg:
        ad = o.animation_data
        if ad and ad.action:
            for fc in _fcurves(ad.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = max(0, f - 2)
    return clips


def _fcurves(action):
    """Blender 5 (슬롯 액션)과 이전 버전 모두에서 fcurve 목록"""
    if hasattr(action, 'fcurves') and action.fcurves is not None:
        try:
            return list(action.fcurves)
        except Exception:
            pass
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                out.extend(bag.fcurves)
    return out


def export(key):
    t0 = time.time()
    rig, anims, pose = build(key)
    rig.reset()
    n0, n1 = join_parts(rig)
    clips = bake(rig, anims, pose)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, key + '.glb')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', use_selection=False,
        export_animations=True, export_animation_mode='SCENE', export_force_sampling=False,
        export_frame_range=False, export_apply=False, export_yup=True, export_cameras=False, export_lights=False,
    )
    meta = {'key': key, 'clips': clips, 'joints': sorted(rig.j.keys()),
            'hand': ['hand_R', 'hand_L'], 'height': rig.meta.get('height', None)}
    with open(os.path.join(OUT, key + '.json'), 'w', encoding='utf-8') as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=1)
    nobj = len(bpy.data.objects)
    print(f'[{key}] {nobj} objects (meshes {n0}->{n1}), {len(clips)} clips -> {path} ({os.path.getsize(path) // 1024} KB, {time.time() - t0:.1f}s)', flush=True)


def main():
    opt = args()
    if opt['chars'] == 'all':
        import vil_build
        import char_build
        keys = [k for k in vil_build.KEYS] + ['lumberjack', 'miner', 'farmer', 'player']
    else:
        keys = opt['chars'].split(',')
    for k in keys:
        export(k)


if __name__ == '__main__':
    main()
