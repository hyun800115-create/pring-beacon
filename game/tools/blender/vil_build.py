"""
vil_build.py - the Frost Village villager & pet roster (CONTRACT_VILLAGERS A).

Not run directly: vil_render.py imports
    build(key)                    -> char_geo.Rig ready to pose (scene reset)
    anims_for(key)                -> {anim: {frames, fps, repeat, dirs[, impactFrame]}}
    pose_for(rig, anim, i, d)     -> pose dict incl. '_show' (face parts + props)
SPECS holds every villager's look (colours, body type, face tweaks), name,
role, traits and which optional anims (run / throw / dance / sit / perform) it has.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vil_anim as va             # noqa: E402   (pure python; bpy modules are imported lazily)

KEYS = ['npc_kid_boy', 'npc_kid_girl', 'npc_kid_prankster', 'npc_teen_girl', 'npc_young_man', 'npc_aunt',
        'npc_uncle', 'npc_grandma', 'npc_grandpa', 'npc_merchant', 'npc_herbalist', 'npc_bard',
        'npc_blacksmith', 'npc_fashion', 'npc_yellow', 'npc_red', 'npc_blue']
PET_KEYS = ['pet_dog', 'pet_cat', 'pet_penguin']
ALL_KEYS = KEYS + PET_KEYS

RUNNERS = {'npc_kid_boy', 'npc_kid_girl', 'npc_kid_prankster', 'npc_teen_girl', 'npc_young_man'}
THROWERS = RUNNERS
DANCERS = {'npc_kid_boy', 'npc_kid_girl', 'npc_kid_prankster', 'npc_teen_girl', 'npc_young_man', 'npc_aunt',
           'npc_fashion', 'npc_uncle', 'npc_blacksmith'}
SITTERS = {'npc_grandma', 'npc_grandpa', 'npc_herbalist', 'npc_aunt', 'npc_bard'}
PERFORMERS = {'npc_bard'}

LONG_DRESS = [(0.29, -0.21), (0.272, -0.10), (0.240, 0.0), (0.214, 0.10), (0.208, 0.22), (0.195, 0.31),
              (0.155, 0.39), (0.07, 0.45), (0.0, 0.46)]
LONG_SKIRT = [(0.285, -0.255), (0.272, -0.13), (0.245, 0.0), (0.215, 0.10), (0.208, 0.22), (0.195, 0.31),
              (0.155, 0.39), (0.07, 0.45), (0.0, 0.46)]
LONG_COAT = [(0.272, -0.20), (0.262, -0.10), (0.236, 0.0), (0.214, 0.10), (0.208, 0.22), (0.195, 0.31),
             (0.155, 0.39), (0.07, 0.45), (0.0, 0.46)]

NOFUR = dict(hem_fur=False, cuff_fur=False, boot_fur=False)

SPECS = {
    'npc_kid_boy': dict(
        name=('꼬마 도윤', 'Doyun'), role='kid', traits=['playful', 'snowball_fights', 'tag'], body='kid',
        coat='#4FA3E0', quilted=True, hair='#4A3020', pants='#5A4636', boots='#8A5A33', mitten='#F2C230',
        hem_r=0.245, hem_z=-0.08, **NOFUR,
        face=dict(brow='#4A3020', eye_w=0.048, eye_h=0.066, blush='#F48A8A'), shadow=[36, 14]),
    'npc_kid_girl': dict(
        name=('꼬마 하린', 'Harin'), role='kid', traits=['cheerful', 'tag', 'dance', 'snowman'], body='kid',
        coat='#F59AB8', fur='#FFFFFF', hair='#8A5232', pants='#F4EDE0', boots='#C9853F', mitten='#F4F1EA',
        face=dict(brow='#6E4026', eye_w=0.048, eye_h=0.066, lashes=True, blush='#F48A8A'), shadow=[36, 14]),
    'npc_kid_prankster': dict(
        name=('장난꾸러기 준', 'Jun'), role='kid', traits=['prankster', 'snowball_fights', 'runs_away'], body='kid',
        coat='#F08A3A', coat_rough=0.9, hair='#5A3A26', pants='#3D4A6B', boots='#C8463D', mitten='#3D4A6B',
        hem_r=0.24, hem_z=-0.07, **NOFUR,
        face=dict(brow='#5A3A26', eye_w=0.048, eye_h=0.066, blush='#F48A8A'),
        face_sub={'m_grin': 'm_gap', 'm_D': 'm_gapD', 'm_smile': 'm_smirk'}, run_face='happy', shadow=[36, 14]),
    'npc_teen_girl': dict(
        name=('소녀 서아', 'Seoa'), role='teen', traits=['chatty', 'dance'], body='teen',
        coat='#8A63C9', hair='#3A2A30', pants='#2E3440', boots='#5A3A4A', mitten='#F4EDE0',
        hem_r=0.245, hem_z=-0.09, hem_fur=False, cuff_fur=False, boot_fur=True, fur='#F4F1EA',
        face=dict(brow='#3A2A30', lashes=True, eye_w=0.046, eye_h=0.064), shadow=[42, 16]),
    'npc_young_man': dict(
        name=('청년 태오', 'Taeo'), role='adult', traits=['show_off', 'snowball_fights', 'waves'], body='tall',
        coat='#5E7A3A', hair='#6B4026', pants='#3F5675', boots='#3B2A20', mitten='#3B2A20',
        hem_r=0.235, hem_z=-0.06, **NOFUR, fur='#EADCC4',
        face=dict(brow='#4A2A18', brow_thick=0.0145), shadow=[46, 18]),
    'npc_aunt': dict(
        name=('빵집 아주머니', 'Baker Auntie'), role='adult', traits=['kind', 'chatty', 'compliments'], body='adult',
        coat='#9A6A48', hair='#5A3A26', pants='#9A6A48', boots='#5A3A26', bare_hands=True,
        torso_profile=LONG_DRESS, hem_r=0.29, hem_z=-0.21, **NOFUR,
        face=dict(brow='#5A3A26', lashes=True, blush='#F49090'), idle_style=None, shadow=[48, 19]),
    'npc_uncle': dict(
        name=('아저씨', 'Uncle'), role='adult', traits=['grumpy', 'sulks', 'belly_laugh'], body='plump',
        coat='#F2EDE2', hair='#3A2A22', pants='#4A4A52', boots='#3B2A20', bare_hands=True,
        hem_r=0.24, hem_z=-0.07, **NOFUR, vest='plaid',
        face=dict(brow='#3A2A22', brow_thick=0.016, mouth_v=-0.118, nose='big'), idle_style='hips',
        shadow=[54, 21]),
    'npc_grandma': dict(
        name=('할머니', 'Grandma'), role='elder', traits=['gentle', 'bench', 'praises_kids'], body='elder',
        coat='#5A4A6A', sleeve='#C98C8C', hair='#C8C6C2', pants='#5A4A6A', boots='#5A3A26', bare_hands=True,
        torso_profile=LONG_SKIRT, hem_r=0.285, hem_z=-0.255, **NOFUR, cardigan='#C98C8C',
        face=dict(brow='#8A8680', blush='#F2A0A0'), idle_style='clasp', hunch=9.0, shadow=[46, 18]),
    'npc_grandpa': dict(
        name=('할아버지', 'Grandpa'), role='elder', traits=['easygoing', 'bench', 'naps'], body='elder',
        coat='#8A5A3A', hair='#F2F0EA', pants='#6A6A70', boots='#3B2A20', bare_hands=True,
        torso_profile=LONG_COAT, hem_r=0.272, hem_z=-0.20, **NOFUR,
        face=dict(brow='#BDB6AA', brow_thick=0.018, mouth_v=-0.120, mouth_out=0.052, nose='big',
                  nose_color='#F2B898'),
        cane=True, hunch=13.0, sit_sleepy=True, shadow=[46, 18]),
    'npc_merchant': dict(
        name=('떠돌이 상인', 'Wandering Merchant'), role='adult', traits=['sly', 'chatty', 'calls_customers'],
        body='stout', coat='bands', fur='#E6DCCB', hair='#3A2A22', pants='#4A3830', boots='#6B4A2E',
        mitten='#6B4A2E',
        face=dict(brow='#3A2A22', brow_thick=0.0155, mouth_v=-0.122, nose='big'), idle_style='hips',
        shadow=[52, 20]),
    'npc_herbalist': dict(
        name=('약초꾼', 'Herbalist'), role='adult', traits=['shy', 'startles'], body='adult',
        coat='#E8DCC0', hair='#B5652E', pants='#6E5A3A', boots='#5A3A26', bare_hands=True, **NOFUR,
        hem_r=0.235, hem_z=-0.07, face=dict(brow='#8A4A22'), idle_style='clasp', shadow=[48, 19]),
    'npc_bard': dict(
        name=('음유시인', 'Bard'), role='adult', traits=['romantic', 'plays_music', 'campfire'], body='adult',
        coat='#2E8A8A', hair='#D9A85A', pants='#5A3A26', boots='#6B4A2E', bare_hands=True, **NOFUR,
        hem_r=0.24, hem_z=-0.08, face=dict(brow='#A87A3A'), shadow=[46, 18]),
    'npc_blacksmith': dict(
        name=('대장장이 언니', 'Blacksmith'), role='adult', traits=['hearty', 'belly_laugh', 'arms_akimbo'],
        body='strong', coat='#7A8A9A', hair='#4A2A1E', pants='#3B3540', boots='#3B2A20', bare_hands=True,
        bare_forearms=True, **NOFUR, hem_r=0.235, hem_z=-0.06,
        face=dict(brow='#4A2A1E', lashes=True, brow_thick=0.014), idle_style='hips', shadow=[50, 19]),
    'npc_fashion': dict(
        name=('멋쟁이', 'Fashionista'), role='adult', traits=['vain', 'dance', 'poses'], body='adult',
        coat='#F28CB8', coat_rough=0.95, fur='#F9C6DD', hair='#2A1E1A', pants='#F4F1EA', boots='#F2C14E',
        mitten='#F2456A', face=dict(brow='#2A1E1A', lashes=True, brow_v=0.090, brow_thick=0.014), idle_style='hip_one', shades=True,
        shadow=[48, 19]),
    'npc_yellow': dict(
        name=('노란 파카 주민', 'Yellow Parka'), role='adult', traits=['ordinary', 'customer'], body='adult',
        base='villager_a', face=dict(brow='#2A2228'), shadow=[46, 18]),
    'npc_red': dict(
        name=('빨간 파카 주민', 'Red Parka'), role='adult', traits=['ordinary', 'customer'], body='adult',
        base='villager_b', face=dict(brow='#6B4026', lashes=True), shadow=[46, 18]),
    'npc_blue': dict(
        name=('파란 파카 주민', 'Blue Parka'), role='adult', traits=['ordinary', 'customer'], body='adult',
        base='villager_c', face=dict(brow='#7A5030'), shadow=[46, 18]),
    'pet_dog': dict(name=('시바견 콩이', 'Kongi'), role='pet', traits=['energetic', 'chases_kids', 'tail_wag']),
    'pet_cat': dict(name=('고양이 나비', 'Nabi'), role='pet', traits=['aloof', 'loafs_on_benches']),
    'pet_penguin': dict(name=('펭귄 뽀삐', 'Ppoppi'), role='pet', traits=['quirky', 'waddles', 'kids_chase']),
}


def anims_for(key):
    """{anim: info} in contract order for this key."""
    if key in PET_KEYS:
        names = ['idle', 'walk', 'run', 'sit', 'happy'] + (['loaf'] if key == 'pet_cat' else [])
        return {n: dict(va.PET_ANIMS[n]) for n in names}
    out = {}
    for n in va.HUMAN_ORDER:
        if n == 'run' and key not in RUNNERS:
            continue
        if n == 'throw' and key not in THROWERS:
            continue
        if n == 'dance' and key not in DANCERS:
            continue
        if n == 'sit' and key not in SITTERS:
            continue
        if n == 'perform' and key not in PERFORMERS:
            continue
        out[n] = dict(va.ANIMS[n])
    return out


def make_spec(key):
    import char_build as cb
    import vil_dress as vd
    s = dict(SPECS[key])
    if s.get('base'):
        b = dict(cb.SPECS[s['base']])
        b.pop('dress', None)
        s = {**b, **s}
    face = dict(s.get('face', {}))
    face.setdefault('skin', s.get('skin', cb.SKIN))
    s['face'] = face
    for k, v in face.items():
        s[k] = v
    coat = s['coat']
    if coat == 'bands':
        s['coat_mat'] = vd.mat_bands('coat_bands', ['#C8463D', '#F2C14E', '#2E8A8A', '#F4EDE0', '#C8463D',
                                                    '#2E3F6E'], scale=11.0)
        s['sleeve_mat'] = s['coat_mat']
    else:
        s['coat_mat'] = cb.M('coat', coat, rough=s.get('coat_rough', 0.8))
    if s.get('sleeve'):
        s['sleeve_mat'] = cb.M('sleeve', s['sleeve'], rough=0.9)
    if s.get('vest') == 'plaid':
        s['vest_mat'] = cb.mat_plaid('vest_plaid', '#B5763F', '#6E4428', light='#D0965A', scale=9.0)
    if s.get('quilted'):
        s['torso_profile'] = vd.quilted_profile(vd.std_profile(s.get('hem_r', 0.245), s.get('hem_z', -0.08)),
                                                step=0.075, amp=0.06)
    return s


def build(key):
    import bl_common as bc
    import char_build as cb
    bc.reset_scene()
    if key in PET_KEYS:
        import vil_pets
        rig = vil_pets.build(key)
        rig.meta['key'] = key
        rig.meta['ch'] = {'role': 'pet'}
        return rig
    import vil_body
    import vil_dress as vd
    spec = make_spec(key)
    rig = vil_body.build_body(spec)
    vd.DRESS[key](rig, spec)
    if spec.get('cardigan'):
        cm = cb.M('cardigan', spec['cardigan'], rough=0.95)
        import char_geo as g
        g.mesh_obj('cardigan', vd.fuzz(g.bm_lathe([(0.262, -0.03), (0.250, 0.06), (0.222, 0.16), (0.212, 0.24),
                                                   (0.198, 0.31), (0.158, 0.39)], seg=44, sy=0.86, smooth_n=16,
                                                  cap_top=False, cap_bottom=False), 0.003, 50.0), cm,
                   rig.j['spine'])
    if key in THROWERS:
        vd.make_snowball(rig)
    P = vil_body.BODY.get(spec['body']) or STOUT
    vil_body.apply_proportions(rig, P)
    ch = {k: spec.get(k) for k in ('role', 'idle_style', 'cane', 'hunch', 'sit_sleepy', 'run_face', 'shades')
          if spec.get(k) is not None}
    ch['leg_len'] = rig.meta['leg_len']
    ch['hip_z'] = rig.meta['leg_len']
    ch['face_sub'] = spec.get('face_sub', {})
    ch['bard'] = key == 'npc_bard'
    rig.meta.update(key=key, ch=ch, shadow=spec.get('shadow', [46, 18]))
    return rig


STOUT = dict(torso=(1.13, 1.12, 1.0), head=1.0, arm=(1.06, 1.0), hand=1.04, leg=(1.08, 0.95, 0.97), hip_w=1.12)


def show_set(rig, face, props):
    ch = rig.meta.get('ch', {})
    if ch.get('role') == 'pet':
        return set(va.PET_FACES[face]) | set(props)
    sub = ch.get('face_sub', {})
    parts = {sub.get(p, p) for p in va.FACES[face]}
    show = parts | set(props)
    if ch.get('shades'):
        show.add('shades_up' if face in va.EYES_SHOWN else 'shades')
    if ch.get('bard') and 'lute_front' not in show:
        show.add('lute_back')
    return show


def pose_for(rig, anim, i, d):
    key = rig.meta['key']
    ch = rig.meta['ch']
    if key in PET_KEYS:
        info = va.PET_ANIMS[anim]
        p = va.pet_pose(key, anim, i, info['frames'], d)
    else:
        info = va.ANIMS[anim]
        p = va.human_pose(anim, i, info['frames'], ch, d)
        tx, ty, tz = rig.meta['torso_scale']
        for side in ('R', 'L'):
            k = 'ik_' + side
            if k in p:
                v = list(p[k])
                v[0] *= tx
                v[1] *= ty
                v[2] *= tz
                p[k] = tuple(v)
    p['_show'] = show_set(rig, p.pop('_face'), p.pop('_props', set()))
    return p
