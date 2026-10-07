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
        base = lambda an, i: vil_build.pose_for(rig, an, i, 'S')  # noqa: E731
        if not key.startswith('pet_'):
            anims = dict(anims)
            anims.update(EXTRA)
        pose = lambda an, i, n: extra_pose(vil_build, rig, base, an, i, n)  # noqa: E731
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
    # 모양 단순하게 (몸 0.3, 얼굴 부품 0.6) — 둥근 치비 모양이라 거의 티가 안 난다
    for o in bpy.data.objects:
        if o.type != 'MESH' or len(o.data.polygons) < 300:
            continue
        m = o.modifiers.new('dec', 'DECIMATE')
        m.ratio = 0.6 if keep.get(o.name) else 0.3
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_apply(modifier=m.name)
    n1 = len([o for o in bpy.data.objects if o.type == 'MESH'])
    return n0, n1


# 실내 생활용 추가 동작 (주민만): 앉아서 이야기·먹기·읽기, 서서 손일(요리·빵·작업), 누워 자기
EXTRA = {
    'sit':        {'frames': 4, 'fps': 4, 'repeat': -1},
    'sit_talk':   {'frames': 8, 'fps': 8, 'repeat': -1},
    'sit_eat':    {'frames': 6, 'fps': 5, 'repeat': -1},
    'sit_read':   {'frames': 4, 'fps': 2, 'repeat': -1},
    'work_hands': {'frames': 6, 'fps': 7, 'repeat': -1},
    'sleep':      {'frames': 4, 'fps': 2, 'repeat': -1},
}
ARM_KEYS = ('ik_', 'sh_', 'el_', 'hand_', 'head', 'neck')


def extra_pose(vb, rig, base, an, i, n):
    import math
    if an not in EXTRA:
        return base(an, i)
    if an == 'sit':
        return base('sit', i % 4)
    if an == 'sit_talk':
        p = base('sit', i % 4)
        t = base('talk', i % 8)
        for k, v in t.items():
            if k.startswith(ARM_KEYS) or k == '_show':
                p[k] = v
        return p
    if an == 'sit_eat':
        p = base('sit', i % 4)
        up = [0.0, 0.0, 0.5, 1.0, 1.0, 0.4][i % 6]
        a = (-0.12, -0.24, -0.08)
        m = (-0.04, -0.17, 0.12)
        p['ik_R'] = tuple(a[k] + (m[k] - a[k]) * up for k in range(3)) + (-1.0, 0.2, -0.3)
        p['ik_L'] = (0.12, -0.24, -0.10, 1.0, 0.2, -0.3)
        p['_show'] = vb.show_set(rig, 'talk_mid' if up > 0.7 else 'talk_closed', set())
        return p
    if an == 'sit_read':
        p = base('sit', i % 4)
        p['ik_R'] = (-0.07, -0.24, -0.02, -1.0, 0.2, -0.5)
        p['ik_L'] = (0.07, -0.24, -0.02, 1.0, 0.2, -0.5)
        p['head'] = (12, 0, 0)
        p['_show'] = vb.show_set(rig, 'blink' if i == 3 else 'neutral', set())
        return p
    if an == 'work_hands':
        p = base('idle', 0)
        a = 2 * math.pi * i / 6
        p['ik_R'] = (-0.10, -0.26, -0.12 + 0.05 * math.sin(a), -1.0, 0.2, -0.4)
        p['ik_L'] = (0.10, -0.26, -0.12 + 0.05 * math.cos(a), 1.0, 0.2, -0.4)
        p['head'] = (14, 0, 0)
        p['_show'] = vb.show_set(rig, 'blink' if i == 5 else 'neutral', set())
        return p
    if an == 'sleep':
        p = base('idle', 0)
        p['root'] = (90, 0, 0)
        p['chest@'] = (0, 0, 0.006 * math.sin(2 * math.pi * i / 4))
        p['ik_R'] = (-0.14, -0.10, -0.18, -1.0, 0.2, -0.3)
        p['ik_L'] = (0.14, -0.10, -0.18, 1.0, 0.2, -0.3)
        p['_show'] = vb.show_set(rig, 'sleepy' if i % 2 else 'sleepy_b', set())
        return p
    return base(an, i)


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
