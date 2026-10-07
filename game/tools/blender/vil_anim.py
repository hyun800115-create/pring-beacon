"""
vil_anim.py - poses + per-frame expressions for Frost Village villagers & pets.

Pure python (no bpy): importable anywhere for checks.

    pose(anim, i, n, ch, d='S') -> pose dict for char_geo.Rig.apply()
        plus '_face' (a FACES preset name) and '_props' (set of prop toggles).
    vil_build converts '_face'/'_props' into the Rig's '_show' toggle set.

Joint sign conventions (verified numerically, see char_geo.Rig.apply):
  * arms / legs (hanging):  pitch > 0 swings FORWARD, roll > 0 = outward
  * spine / chest / head / root (pointing up): pitch > 0 tilts BACK
    -> lean forward / look down = NEGATIVE pitch (helpers lean(), look())
  * yaw > 0 = counter-clockwise seen from above (towards the character's left)
  * 'root@' offsets are WORLD space; 'hips@' offsets are facing-relative
    (x = character's left, y = backward, z = up)
  * 'ik_R'/'ik_L' targets are chest-local metres for the STANDARD body; vil_build
    scales them by the character's torso proportions.

Loops are cyclic (frame i of n = phase i/n).  One-shot anims (surprised, throw,
hit) end on a holdable pose.
"""
import math

TAU = math.tau

LOCO_DIRS = ['S', 'SE', 'E', 'NE', 'N']
SOCIAL_DIRS = ['S', 'SE', 'E']

# anim -> frames, fps, repeat, dirs                         (CONTRACT_VILLAGERS section A)
ANIMS = {
    'idle':       dict(frames=4, fps=6, repeat=-1, dirs=LOCO_DIRS),
    'walk':       dict(frames=8, fps=12, repeat=-1, dirs=LOCO_DIRS),
    'run':        dict(frames=8, fps=16, repeat=-1, dirs=LOCO_DIRS),
    'carry_walk': dict(frames=8, fps=12, repeat=-1, dirs=LOCO_DIRS),
    'happy':      dict(frames=6, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'talk':       dict(frames=8, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'laugh':      dict(frames=6, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'wave':       dict(frames=6, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'surprised':  dict(frames=6, fps=12, repeat=0, dirs=SOCIAL_DIRS),
    'angry':      dict(frames=6, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'sad':        dict(frames=4, fps=6, repeat=-1, dirs=SOCIAL_DIRS),
    'throw':      dict(frames=8, fps=14, repeat=0, dirs=SOCIAL_DIRS, impactFrame=5),
    'hit':        dict(frames=6, fps=12, repeat=0, dirs=SOCIAL_DIRS),
    'dance':      dict(frames=8, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'sit':        dict(frames=4, fps=4, repeat=-1, dirs=SOCIAL_DIRS),
    'perform':    dict(frames=8, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'shiver':     dict(frames=4, fps=12, repeat=-1, dirs=SOCIAL_DIRS),
}
PET_ANIMS = {
    'idle':  dict(frames=4, fps=6, repeat=-1, dirs=LOCO_DIRS),
    'walk':  dict(frames=8, fps=12, repeat=-1, dirs=LOCO_DIRS),
    'run':   dict(frames=8, fps=16, repeat=-1, dirs=LOCO_DIRS),
    'sit':   dict(frames=4, fps=4, repeat=-1, dirs=SOCIAL_DIRS),
    'happy': dict(frames=6, fps=10, repeat=-1, dirs=SOCIAL_DIRS),
    'loaf':  dict(frames=4, fps=4, repeat=-1, dirs=SOCIAL_DIRS),
}
SOCIAL = {'happy', 'talk', 'laugh', 'wave', 'surprised', 'angry', 'sad', 'throw', 'hit', 'dance', 'sit',
          'perform', 'shiver'}
HUMAN_ORDER = ['idle', 'walk', 'run', 'carry_walk', 'happy', 'talk', 'laugh', 'wave', 'surprised', 'angry',
               'sad', 'throw', 'hit', 'dance', 'sit', 'perform', 'shiver']
PET_ORDER = ['idle', 'walk', 'run', 'sit', 'happy', 'loaf']

SEAT_H = 0.45          # bench / log seat height (m)

# --------------------------------------------------------------------------- faces

FACES = {
    'neutral':     ['eye_dot', 'brow_neutral', 'm_smile', 'cheek_blush'],
    'blink':       ['eye_blink', 'brow_neutral', 'm_smile', 'cheek_blush'],
    'smile':       ['eye_dot', 'brow_up', 'm_grin', 'cheek_blush'],
    'happy':       ['eye_happy', 'brow_up', 'm_grin', 'cheek_blush'],
    'laugh':       ['eye_happy', 'brow_up', 'm_D', 'cheek_blush'],
    'laugh_b':     ['eye_happy', 'brow_up', 'm_open', 'cheek_blush'],
    'talk_open':   ['eye_dot', 'brow_up', 'm_open', 'cheek_blush'],
    'talk_mid':    ['eye_dot', 'brow_neutral', 'm_mid', 'cheek_blush'],
    'talk_closed': ['eye_dot', 'brow_neutral', 'm_smile', 'cheek_blush'],
    'talk_blink':  ['eye_blink', 'brow_neutral', 'm_mid', 'cheek_blush'],
    'talk_happy':  ['eye_happy', 'brow_up', 'm_open', 'cheek_blush'],
    'surprised':   ['eye_round', 'brow_up', 'm_O', 'cheek_blush', 'fx_sweat'],
    'startle':     ['eye_round', 'brow_up', 'm_mid', 'cheek_blush'],
    'angry':       ['eye_glare', 'brow_angry', 'm_pout', 'cheek_red'],
    'angry_huff':  ['eye_glare', 'brow_angry', 'm_frown', 'cheek_red'],
    'angry_shout': ['eye_glare', 'brow_angry', 'm_open', 'cheek_red'],
    'sad':         ['eye_teary', 'brow_sad', 'm_wavy', 'fx_tear'],
    'sad_b':       ['eye_teary', 'brow_sad', 'm_frown', 'fx_tear'],
    'sad_blink':   ['eye_sleep', 'brow_sad', 'm_frown', 'fx_tear'],
    'hurt':        ['eye_chevron', 'brow_sad', 'm_wavy', 'cheek_blush', 'fx_snow'],
    'hurt_open':   ['eye_chevron', 'brow_sad', 'm_O', 'cheek_blush', 'fx_snow'],
    'hurt_pout':   ['eye_chevron', 'brow_angry', 'm_pout', 'cheek_red', 'fx_snow'],
    'sleepy':      ['eye_sleep', 'brow_neutral', 'm_mid', 'cheek_blush'],
    'sleepy_b':    ['eye_sleep', 'brow_neutral', 'm_smile', 'cheek_blush'],
    'shiver':      ['eye_dot', 'brow_sad', 'm_clench', 'cheek_cold'],
    'shiver_b':    ['eye_chevron', 'brow_sad', 'm_clench', 'cheek_cold'],
    'sing':        ['eye_happy', 'brow_up', 'm_sing', 'cheek_blush'],
    'heart':       ['eye_heart', 'brow_up', 'm_grin', 'cheek_blush'],
    'scheme':      ['eye_glare', 'brow_neutral', 'm_grin', 'cheek_blush'],
}

# Faces whose eyes must be visible (fashion pushes the shades up for these)
EYES_SHOWN = {'surprised', 'startle', 'sad', 'sad_b', 'sad_blink', 'hurt', 'hurt_open', 'hurt_pout', 'heart'}


# --------------------------------------------------------------------------- helpers

def V(v):
    if isinstance(v, (int, float)):
        return (float(v), 0.0, 0.0)
    v = tuple(float(a) for a in v)
    return v + (0.0,) * (3 - len(v))


def add(*poses):
    """Sum joint values (vectors add); '_' keys and ik targets: last wins."""
    out = {}
    for p in poses:
        for k, v in p.items():
            if k.startswith('_') or k.startswith('ik_'):
                out[k] = v
                continue
            vv = V(v)
            out[k] = tuple(a + b for a, b in zip(out[k], vv)) if k in out else vv
    return out


def lerp(a, b, t):
    out = {}
    for k in set(a) | set(b):
        if k.startswith('_'):
            out[k] = (b if t >= 0.5 else a).get(k, a.get(k, b.get(k)))
            continue
        if k.startswith('ik_'):
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None:
                out[k] = vb if t >= 0.5 else va
                if out[k] is None:
                    out.pop(k)
                continue
            out[k] = tuple(x + (y - x) * t for x, y in zip(va, vb))
            continue
        va, vb = V(a.get(k, 0.0)), V(b.get(k, 0.0))
        out[k] = tuple(x + (y - x) * t for x, y in zip(va, vb))
    return out


def lean(fwd=0.0, side=0.0, twist=0.0):
    """Spine: forward lean (deg), side lean (+ = character's left), twist (+ = turn left)."""
    return {'spine': (-fwd, side, twist)}


def look(down=0.0, tilt=0.0, turn=0.0):
    return {'head': (-down, tilt, turn)}


def arm(side, fwd=0.0, out=0.0, yaw=0.0, elbow=0.0):
    return {'sh_' + side: (fwd, out, yaw), 'el_' + side: (elbow, 0, 0)}


def arms(fwd=0.0, out=0.0, elbow=0.0, yaw=0.0):
    return {**arm('R', fwd, out, yaw, elbow), **arm('L', fwd, out, yaw, elbow)}


def body(dx=0.0, back=0.0, up=0.0):
    """Facing-relative body translation (moves everything incl. legs)."""
    return {'hips@': (dx, back, up)}


def legs_stand(spread=3.0, bend=0.0):
    return {'hip_R': (bend, spread, 0), 'hip_L': (bend, spread, 0), 'knee_R': (bend * 2, 0, 0),
            'knee_L': (bend * 2, 0, 0)}


def squat(t, leg_len=0.34):
    """Bend both legs t degrees at the hip (2t at the knee) and drop the body so
    the feet stay planted."""
    drop = leg_len * 0.5 * (1 - math.cos(math.radians(t)) * 1.0) * 1.15
    return {'hip_R': (t, 4, 0), 'hip_L': (t, 4, 0), 'knee_R': (2 * t, 0, 0), 'knee_L': (2 * t, 0, 0),
            'hips@': (0, 0, -drop)}


def legs_walk(a, amp=34.0, knee=55.0, leg_len=0.34, bob=0.022):
    s, c = math.sin(a), math.cos(a)
    hip_r, hip_l = amp * s, -amp * s
    knee_r = knee * max(0.0, c) ** 1.5 + 6
    knee_l = knee * max(0.0, -c) ** 1.5 + 6
    drop = leg_len * (1 - math.cos(math.radians(abs(hip_r) * 0.85)))
    return {'hip_R': (hip_r, 2, 0), 'hip_L': (hip_l, 2, 0), 'knee_R': (knee_r, 0, 0), 'knee_L': (knee_l, 0, 0),
            'hips@': (0, 0, bob * (0.5 + 0.5 * math.cos(2 * a)) - drop * 0.7),
            'root': (0, 3.5 * c, 0)}


def face(name, props=()):
    return {'_face': name, '_props': set(props)}


BASE = {**arm('R', 4, 9, 0, 12), **arm('L', 4, 9, 0, 12)}
CARRY = {'sh_R': (66, -16, 0), 'sh_L': (66, -16, 0), 'el_R': (34, 0, 0), 'el_L': (34, 0, 0),
         'hand_R': (-30, 0, 0), 'hand_L': (-30, 0, 0)}

# idle arm styles (chest-local IK targets for the standard body)
HOLD_STYLES = {
    'hips':  {'ik_R': (-0.215, -0.02, -0.215, -1.0, 0.25, 0.1), 'ik_L': (0.215, -0.02, -0.215, 1.0, 0.25, 0.1)},
    'hip_one': {'ik_L': (0.215, -0.02, -0.215, 1.0, 0.25, 0.1)},
    'clasp': {'ik_R': (-0.075, -0.215, -0.19, -0.4, 0.3, -1.0), 'ik_L': (0.075, -0.215, -0.19, 0.4, 0.3, -1.0)},
    'back':  {'sh_R': (-28, 6, 0), 'sh_L': (-28, 6, 0), 'el_R': (70, 0, 0), 'el_L': (70, 0, 0)},
}

CANE_HAND = (-0.215, -0.16, -0.17, -1.0, 0.4, -0.4)      # right hand resting on the cane top


# --------------------------------------------------------------------------- human anims

def _blink_face(i, n, ch, base='neutral'):
    return 'blink' if i == ch.get('blink_frame', 2) % n else base


def h_idle(i, n, ch):
    a = TAU * i / n
    s = math.sin(a)
    p = dict(BASE)
    p.update({'chest@': (0, 0, 0.007 * s), 'neck@': (0, 0, 0.004 * s), **look(2.0 * s),
              **lean(-1.5 - 1.0 * s), 'hips@': (0, 0, -0.004 - 0.004 * s),
              'hip_R': (2 + 1.5 * s, 3, 0), 'hip_L': (2 + 1.5 * s, 3, 0), 'knee_R': (3 + 3 * s, 0, 0),
              'knee_L': (3 + 3 * s, 0, 0), 'sh_R': (4 - 2 * s, 9 + 3 * s, 0), 'sh_L': (4 - 2 * s, 9 + 3 * s, 0)})
    st = ch.get('idle_style')
    if st in HOLD_STYLES:
        p.update(HOLD_STYLES[st])
    props = set()
    if ch.get('cane'):
        p['ik_R'] = CANE_HAND
        props.add('cane')
    f = _blink_face(i, n, ch, ch.get('idle_face', 'neutral'))
    p.update(face(f, props))
    return p


def h_walk(i, n, ch, carry=False):
    a = TAU * i / n
    s = math.sin(a)
    elder = ch.get('role') == 'elder'
    amp, kn = (24.0, 36.0) if elder else (36.0 if ch.get('role') == 'kid' else 34.0,
                                          60.0 if ch.get('role') == 'kid' else 55.0)
    bob = 0.014 if elder else (0.03 if ch.get('role') == 'kid' else 0.022)
    p = legs_walk(a, amp, kn, ch.get('leg_len', 0.34), bob)
    p.update({**lean(-5 if not carry else 2, 0, 7 * s), 'hips': (0, 0, -5 * s),
              **look(3 - 2 * math.cos(2 * a), 0, -5 * s), 'chest@': (0, 0, 0.004 * math.cos(2 * a))})
    props = set()
    if carry:
        p.update(CARRY)
        p.update(lean(3, 0, 3 * s))
        p['hips'] = (0, 0, -6 * s)
        p.update(look(2, 0, -3 * s))
    else:
        sw = 26.0 if elder else (46.0 if ch.get('role') == 'kid' else 40.0)
        p['sh_R'] = (-sw * s + 4, 10, 0)
        p['sh_L'] = (sw * s + 4, 10, 0)
        p['el_R'] = (18 + 14 * max(0, -s), 0, 0)
        p['el_L'] = (18 + 14 * max(0, s), 0, 0)
        st = ch.get('walk_style')
        if st in HOLD_STYLES:
            p.update(HOLD_STYLES[st])
        if ch.get('cane'):
            # cane swings forward with the left leg (opposite to the right leg)
            p['ik_R'] = (-0.215, -0.17 - 0.06 * (-s), -0.16 + 0.025 * max(0.0, -s), -1.0, 0.4, -0.4)
            props.add('cane')
    f = 'blink' if (i == 5 and not carry) else ch.get('walk_face', 'neutral')
    p.update(face(f, props))
    return p


def h_run(i, n, ch):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    p = legs_walk(a, 50.0, 88.0, ch.get('leg_len', 0.34), 0.0)
    # flight phase: up twice per cycle, highest between foot contacts
    p['hips@'] = (0, 0, 0.045 * abs(math.sin(2 * a + 0.6)) - 0.018)
    p['root'] = (0, 4.0 * c, 0)
    p.update({**lean(16, 0, 10 * s), 'hips': (0, 0, -8 * s), **look(-10, 0, -6 * s)})
    sw = 58.0
    p['sh_R'] = (-sw * s + 10, 16, 0)
    p['sh_L'] = (sw * s + 10, 16, 0)
    p['el_R'] = (80, 0, 0)
    p['el_L'] = (80, 0, 0)
    p.update(face(ch.get('run_face', 'smile')))
    return p


def up_hands(spread=0.30, height=0.34, fwd=-0.05, asym=0.0):
    """Both hands raised in a V beside/above the head (IK; unreachable targets just
    straighten the arm toward them, which is what we want)."""
    return {'ik_R': (-spread - asym, fwd, height + asym * 0.5, -1.0, 0.1, -0.4),
            'ik_L': (spread - asym, fwd, height - asym * 0.5, 1.0, 0.1, -0.4)}


def h_happy(i, n, ch):
    L = ch.get('leg_len', 0.34)
    keys = [
        {**arms(14, 14, 30), **body(0, 0, -0.03 * L / 0.34), **lean(-8), **look(6), **squat(24, L)},
        {**up_hands(0.30, 0.22), **body(0, 0, 0.05), **lean(4), **look(-8), **legs_stand(3, 4)},
        {**up_hands(0.33, 0.36), **body(0, 0, 0.10), **lean(8), **look(-12), **legs_stand(3, 14),
         'knee_R': (40, 0, 0), 'knee_L': (40, 0, 0)},
        {**up_hands(0.32, 0.30), **body(0, 0, 0.07), **lean(6), **look(-10), **legs_stand(3, 8)},
        {**arms(40, 50, 40), **body(0, 0, -0.025), **lean(-8), **look(4), **squat(20, L)},
        {**arms(16, 14, 24), **body(0, 0, -0.008), **lean(-3), **legs_stand(3, 6)},
    ]
    p = dict(keys[i % 6])
    p.update(face('happy' if i in (1, 2, 3, 4) else 'smile'))
    return p


def h_talk(i, n, ch):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    mouths = ['talk_open', 'talk_mid', 'talk_closed', 'talk_open', 'talk_blink', 'talk_open', 'talk_closed',
              'talk_mid']
    p = dict(BASE)
    p.update({**lean(-1 + 1.5 * s, 2.5 * c, 0), **look(5 * math.sin(2 * a) - 1, 4 * c, 0),
              'chest@': (0, 0, 0.004 * math.sin(2 * a)), **legs_stand(3, 2)})
    # right hand gestures: forearm up, palm out, little circles
    p.update(arm('R', 34 + 10 * s, 20 + 6 * c, -10, 78 + 22 * c))
    p['hand_R'] = (-20, 0, 20 * s)
    p.update(arm('L', 6 - 3 * s, 10, 0, 16))
    props = set()
    if ch.get('cane'):
        p['ik_R'] = CANE_HAND
        p.update(arm('L', 34 + 10 * s, 20 + 6 * c, -10, 78 + 22 * c))
        props.add('cane')
    if ch.get('idle_style') == 'hips':
        p['ik_L'] = HOLD_STYLES['hips']['ik_L']
    p.update(face(mouths[i % 8], props))
    return p


def h_laugh(i, n, ch):
    k = i % 6
    shake = [0.0, 1.0, -0.4, 1.0, -0.4, 0.6][k]
    p = dict(BASE)
    p.update({**lean(-10 + 3 * shake, 3 * (1 if k % 2 else -1), 0), **look(-10 - 6 * shake, 4 * (1 if k % 2 else -1)),
              **body(0, 0, 0.012 * shake), **legs_stand(4, 3)})
    p['ik_L'] = (0.11, -0.215, -0.22, 0.6, 0.2, -1.0)          # hand on the belly
    p.update(arm('R', 40 + 12 * shake, 42, 0, 60 + 15 * shake))   # other hand up, slapping the air
    props = set()
    if ch.get('cane'):
        p['ik_R'] = CANE_HAND
        props.add('cane')
    p.update(face('laugh' if k != 3 else 'laugh_b', props))
    return p


def h_wave(i, n, ch):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    p = dict(BASE)
    p.update({**lean(3, -5 + 2 * s, 0), **look(-6, -6 + 4 * s), **legs_stand(3, 2),
              'ik_R': (-0.31 - 0.06 * s, -0.06 - 0.04 * c, 0.26 + 0.02 * c, -1.0, 0.1, -0.6),
              'hand_R': (0, 0, 20 * s), **arm('L', 4, 12, 0, 14), **body(0, 0, 0.012 * abs(s))})
    p.update(face('happy' if i % 3 != 2 else 'smile'))
    return p


def h_surprised(i, n, ch):
    L = ch.get('leg_len', 0.34)
    up_arms = {'ik_R': (-0.31, -0.10, 0.22, -1.0, 0.0, -1.0), 'ik_L': (0.31, -0.10, 0.22, 1.0, 0.0, -1.0)}
    whoa = {'ik_R': (-0.30, -0.14, 0.16, -1.0, 0.0, -1.0), 'ik_L': (0.30, -0.14, 0.16, 1.0, 0.0, -1.0)}
    keys = [
        ({**arms(30, 22, 30), **body(0, 0.0, -0.02), **lean(-4), **look(2), **squat(10, L)}, 'startle'),
        ({**up_arms, **body(0, 0.035, 0.07), **lean(12), **look(-10), **legs_stand(4, 10),
          'knee_R': (24, 0, 0), 'knee_L': (24, 0, 0)}, 'surprised'),
        ({**up_arms, **body(0, 0.050, 0.09), **lean(14), **look(-12), **legs_stand(4, 22),
          'knee_R': (48, 0, 0), 'knee_L': (48, 0, 0)}, 'surprised'),
        ({**up_arms, **body(0, 0.045, 0.0), **lean(4), **look(-4), **squat(22, L)}, 'surprised'),
        ({**whoa, **body(0, 0.035, 0.0), **lean(8), **look(-6), **squat(6, L)}, 'surprised'),
        ({**whoa, **body(0, 0.03, 0.0), **lean(7), **look(-6), **squat(4, L)}, 'surprised'),
    ]
    p, f = keys[i % 6]
    p = dict(p)
    p.update(face(f))
    return p


def h_angry(i, n, ch):
    k = i % 6
    L = ch.get('leg_len', 0.34)
    lift = [('R', 1.0), ('R', 0.0), (None, 0), ('L', 1.0), ('L', 0.0), (None, 0)][k]
    p = {**legs_stand(4, 3), **lean(-8, 0, 0), **look(6, 0, 0)}
    if lift[0] and lift[1] > 0:
        sd = lift[0]
        p['hip_' + sd] = (34, 6, 0)
        p['knee_' + sd] = (62, 0, 0)
        p['hips@'] = (0, 0, 0.012)
        p.update(lean(-10, 4 if sd == 'R' else -4))
    elif lift[0]:
        p['hips@'] = (0, 0, -0.018)          # stomp squash
        p.update(lean(-12, 0, 0))
        p.update(look(10, 0, 0))
    pump = 1.0 if k in (0, 3) else (0.0 if k in (1, 4) else 0.5)
    p.update(arm('R', -14 + 10 * pump, 26, 0, 8 + 20 * pump))
    p.update(arm('L', -14 + 10 * (1 - pump), 26, 0, 8 + 20 * (1 - pump)))
    p['hand_R'] = (0, 0, 0)
    props = set()
    if ch.get('cane'):
        # grandpa shakes his cane in the air
        p.update(arm('R', 150 + 16 * pump, 30, 0, 40 - 20 * pump))
        props.add('cane_hold')
    faces = ['angry', 'angry_huff', 'angry', 'angry_shout', 'angry_huff', 'angry']
    p.update(face(faces[k], props))
    return p


def h_sad(i, n, ch):
    a = TAU * i / n
    s = math.sin(a)
    p = {**lean(-9 + 1.5 * s), **look(13 - 2 * s), 'chest@': (0, 0, -0.006 + 0.004 * s), **legs_stand(1, 4),
         **arm('R', -3, 4, 0, 6), **arm('L', -3, 4, 0, 6), **body(0, 0, -0.01 + 0.004 * s)}
    props = set()
    if ch.get('cane'):
        p['ik_R'] = CANE_HAND
        props.add('cane')
    f = ['sad', 'sad', 'sad_blink', 'sad_b'][i % 4]
    p.update(face(f, props))
    return p


def h_throw(i, n, ch):
    """Overhand snowball throw, impact (release) on frame 5."""
    keys = [
        # 0 ready: both hands packing the snowball in front of the chest
        ({'ik_R': (-0.10, -0.24, -0.05, -1, 0.3, -1), 'ik_L': (0.10, -0.25, -0.03, 1, 0.3, -1),
          **lean(-6), **look(4), **legs_stand(5, 6)}, 'scheme', True),
        # 1 wind-up starts: twist right shoulder back, left arm points at the target
        ({'ik_R': (-0.24, 0.04, 0.10, -1, 0.2, -0.6), **arm('L', 62, 12, 0, 10), **lean(4, 0, -16),
          **look(0, 0, 14), 'hip_L': (16, 6, 0), 'hip_R': (-10, 6, 0), 'knee_L': (8, 0, 0)}, 'scheme', True),
        # 2 full wind-up
        ({'ik_R': (-0.21, 0.13, 0.22, -1, 0.3, -0.2), **arm('L', 84, 14, 0, 6), **lean(9, 0, -28),
          **look(-2, 0, 26), 'hip_L': (20, 6, 0), 'hip_R': (-12, 6, 0), 'knee_L': (10, 0, 0),
          **body(0, 0.01, -0.012)}, 'scheme', True),
        # 3 anticipation hold
        ({'ik_R': (-0.20, 0.16, 0.24, -1, 0.3, -0.2), **arm('L', 88, 14, 0, 4), **lean(11, 0, -30),
          **look(-2, 0, 28), 'hip_L': (20, 6, 0), 'hip_R': (-12, 6, 0), 'knee_L': (12, 0, 0),
          **body(0, 0.015, -0.016)}, 'scheme', True),
        # 4 fast forward swing
        ({'ik_R': (-0.15, -0.10, 0.27, -1, 0.0, 0.3), **arm('L', 40, 18, 0, 20), **lean(-4, 0, -2),
          **look(2, 0, 4), 'hip_L': (18, 6, 0), 'hip_R': (-14, 6, 0), **body(0, 0.0, -0.006)}, 'scheme', True),
        # 5 RELEASE (impactFrame): arm extended forward-high, ball leaves the hand
        ({'ik_R': (-0.07, -0.42, 0.20, -1, 0.0, 0.3), **arm('L', -18, 26, 0, 24), **lean(-14, 0, 20),
          **look(4, 0, -16), 'hip_L': (16, 6, 0), 'hip_R': (-18, 6, 0), **body(0, -0.015, -0.008)}, 'smile', False),
        # 6 follow-through
        ({'ik_R': (0.06, -0.25, -0.16, -0.2, 0.0, -1), **arm('L', -22, 30, 0, 26), **lean(-18, 0, 26),
          **look(6, 0, -20), 'hip_L': (14, 6, 0), 'hip_R': (-28, 6, 0), 'knee_R': (44, 0, 0),
          **body(0, -0.02, -0.012)}, 'smile', False),
        # 7 recover, pleased
        ({**arm('R', 20, 18, 0, 30), **arm('L', 8, 16, 0, 24), **lean(-6, 0, 8), **look(0, 0, -6),
          **legs_stand(5, 4), **body(0, -0.01, 0)}, 'happy', False),
    ]
    p, f, ball = keys[i % 8]
    p = dict(p)
    p.update(face(f, {'snowball'} if ball else set()))
    return p


def h_hit(i, n, ch):
    keys = [
        ({**arm('R', 50, 62, 0, 30), **arm('L', 46, 58, 0, 34), **lean(18), **look(-18, 6), **body(0, 0.03, 0.01),
          **legs_stand(5, 4)}, 'hurt_open'),
        ({**arm('R', 62, 70, 0, 40), **arm('L', 58, 66, 0, 44), **lean(22, 4), **look(-20, 10),
          **body(0, 0.05, 0.02), 'hip_R': (24, 6, 0), 'knee_R': (36, 0, 0), 'hip_L': (-4, 6, 0)}, 'hurt_open'),
        ({**arm('R', 30, 40, 0, 40), **arm('L', 26, 44, 0, 44), **lean(8, 8), **look(-4, -12, 14),
          **body(0, 0.05, -0.012), **legs_stand(5, 10)}, 'hurt'),
        ({**arm('R', 24, 36, 0, 40), **arm('L', 22, 40, 0, 36), **lean(4, -7), **look(0, 10, -12),
          **body(0, 0.045, -0.006), **legs_stand(5, 6)}, 'hurt'),
        ({**arm('R', 14, 22, 0, 30), **arm('L', 12, 22, 0, 28), **lean(-2, 2), **look(4, -4, 0),
          **body(0, 0.04, 0), **legs_stand(4, 3)}, 'hurt'),
        ({**arm('R', 10, 18, 0, 26), **arm('L', 10, 18, 0, 26), **lean(-4, 0), **look(6, 0, 0),
          **body(0, 0.04, 0), **legs_stand(4, 3)}, 'hurt_pout'),
    ]
    p, f = keys[i % 6]
    p = dict(p)
    p.update(face(f))
    return p


def h_dance(i, n, ch):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    L = ch.get('leg_len', 0.34)
    p = {**up_hands(0.30, 0.30, -0.06, asym=0.10 * s), 'hand_R': (0, 0, 30 * s), 'hand_L': (0, 0, -30 * s),
         'hips': (0, 9 * s, 10 * s), **lean(2, -8 * s, -6 * s), **look(-4, 10 * s, 0),
         'root': (0, 0, 14 * s)}
    if i % 4 == 3:                                 # clap-ish: hands come together overhead
        p.update(up_hands(0.12, 0.40, -0.10))
    p.update(squat(10 + 10 * abs(math.sin(2 * a)), L))
    bob = p['hips@']
    p['hips@'] = (0.025 * s, 0, bob[2] + 0.02 * abs(math.cos(2 * a)))
    if i % 4 == 2:                                 # little kick on the off-beat, alternating feet
        sd = 'R' if i % 8 == 2 else 'L'
        p['hip_' + sd] = (36, 8, 0)
        p['knee_' + sd] = (30, 0, 0)
    p.update(face('sing' if i % 4 in (1, 2) else 'happy'))
    return p


def h_sit(i, n, ch):
    """Seated on a 0.45 m seat.  World origin (= sprite anchor) is the FRONT-CENTRE
    of the seat surface; the hips sit 0.12 m behind it, legs dangle (chibi)."""
    a = TAU * i / n
    s = math.sin(a)
    sleepy = ch.get('sit_sleepy')
    hz = ch.get('hip_z', 0.338)
    p = {'hips@': (0, 0.12, 0.065 - hz + 0.004 * s),
         'hip_R': (84, 5, 0), 'hip_L': (84, 5, 0),
         'knee_R': (72 + 10 * s, 0, 0), 'knee_L': (72 - 10 * s, 0, 0),
         **lean(-4 + 1.5 * s, 2 * s), 'chest@': (0, 0, 0.004 * s)}
    p['ik_R'] = (-0.12, -0.22, -0.20, -1.0, 0.2, -0.3)       # hands resting on the thighs
    p['ik_L'] = (0.12, -0.22, -0.20, 1.0, 0.2, -0.3)
    if sleepy:
        nod = [0.0, 0.5, 1.0, 0.6][i % 4]
        p.update(look(8 + 16 * nod, 6 * nod))
        p.update(face('sleepy' if i % 4 in (1, 2) else 'sleepy_b'))
    else:
        p.update(look(-2 + 3 * s, 5 * s))
        p.update(face('blink' if i % 4 == 3 else ch.get('sit_face', 'neutral')))
    return p


def h_perform(i, n, ch):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    strum = [1.0, -1.0] * 4
    p = {**lean(2 + 2 * math.sin(2 * a), 4 * s, 6), **look(4 * math.sin(2 * a), 8 * s, -6),
         **legs_stand(4, 3), 'hip_R': (3 + 8 * max(0.0, s), 4, 0), 'knee_R': (6 + 14 * max(0.0, s), 0, 0)}
    p['ik_L'] = (0.20, -0.21, 0.08, 1.0, 0.0, -0.6)          # fretting hand on the neck
    p['ik_R'] = (-0.03, -0.25 + 0.012 * strum[i], -0.13 + 0.035 * strum[i], -1.0, 0.2, -0.6)   # strumming
    p.update(face('sing' if i % 4 in (0, 1) else 'happy', {'lute_front'}))
    return p


def h_shiver(i, n, ch):
    k = i % 4
    j = [1, -1, 1, -1][k]
    p = {'ik_R': (-0.07, -0.245, -0.03, -0.3, 0.3, -1.0), 'ik_L': (0.07, -0.25, -0.01, 0.3, 0.3, -1.0),
         'hand_R': (0, 0, 10 * j), 'hand_L': (0, 0, -10 * j),
         **lean(-8, 1.5 * j), **look(6, 3 * j, 2 * j), 'hip_R': (6, -4, 0), 'hip_L': (6, -4, 0),
         'knee_R': (14, 0, 0), 'knee_L': (14, 0, 0), 'hips@': (0.006 * j, 0, -0.012),
         'chest@': (0.004 * j, 0, 0)}
    props = set()
    if ch.get('cane'):
        p['ik_R'] = CANE_HAND
        props.add('cane')
    p.update(face('shiver' if k != 2 else 'shiver_b', props))
    return p


HUMAN_FN = {'idle': h_idle, 'walk': h_walk, 'run': h_run, 'carry_walk': lambda i, n, ch: h_walk(i, n, ch, True),
            'happy': h_happy, 'talk': h_talk, 'laugh': h_laugh, 'wave': h_wave, 'surprised': h_surprised,
            'angry': h_angry, 'sad': h_sad, 'throw': h_throw, 'hit': h_hit, 'dance': h_dance, 'sit': h_sit,
            'perform': h_perform, 'shiver': h_shiver}

# Per-direction "cheat to camera": in E the head/torso turn toward the viewer so
# the face (and its expression) stays readable in side views.
CHEAT = {'E': (-9.0, -20.0), 'SE': (-3.0, -8.0)}
CHEAT_PERFORM = {'E': (-28.0, -6.0), 'SE': (-12.0, -4.0)}
NO_CHEAT = {'throw'}


def posture(ch, anim):
    """Character posture added on top of every pose (elders hunch)."""
    h = ch.get('hunch', 0.0)
    if not h or anim == 'sit':
        return {}
    return {**lean(h), 'neck': (h * 1.15, 0, 0), 'hip_R': (h * 0.3, 0, 0), 'hip_L': (h * 0.3, 0, 0),
            'knee_R': (h * 0.6, 0, 0), 'knee_L': (h * 0.6, 0, 0), 'hips@': (0, 0, -0.004 * h / 10)}


def human_pose(anim, i, n, ch, d='S'):
    p = HUMAN_FN[anim](i, n, ch)
    extra = posture(ch, anim)
    if extra:
        p = add(p, extra)
    if anim in SOCIAL and anim not in NO_CHEAT and d in CHEAT:
        sp, hd = (CHEAT_PERFORM if anim == 'perform' else CHEAT)[d]
        p = add(p, {'spine': (0, 0, sp), 'head': (0, 0, hd)})
    return p


# --------------------------------------------------------------------------- pets

def pet_pose(key, anim, i, n, d='S'):
    if key == 'pet_penguin':
        return _penguin(anim, i, n)
    return _quad(key, anim, i, n)


def _quad(key, anim, i, n):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    cat = key == 'pet_cat'
    p = {}
    f = 'pet_neutral'
    if anim == 'idle':
        p = {'body@': (0, 0, 0.004 * s), 'body': (0.8 * s, 0, 0), 'neck': (2 * s, 0, 0),
             'head': (2 * c, 4 * s if not cat else 2 * s, 6 * s), 'tail': (0, 0, (14 if cat else 26) * s)}
        for leg in ('FL', 'FR', 'BL', 'BR'):
            p['knee_' + leg] = (3 + 2 * s if leg[0] == 'F' else -3 - 2 * s, 0, 0)
        if i == 2:
            p['ear_R'] = (-16, 0, 0)
        f = 'pet_blink' if i == 3 else 'pet_neutral'
    elif anim in ('walk', 'run'):
        run = anim == 'run'
        amp = 44.0 if run else 30.0
        kb = 60.0 if run else 40.0
        if run:                                   # bound: fronts together, backs together
            pairs = (('FL', 1, 0.0), ('FR', 1, 0.35), ('BL', -1, 0.0), ('BR', -1, 0.35))
        else:                                     # trot: diagonal pairs
            pairs = (('FL', 1, 0.0), ('BR', 1, 0.0), ('FR', -1, 0.0), ('BL', -1, 0.0))
        for leg, sgn, ph in pairs:
            sw = sgn * math.sin(a + ph)
            p['leg_' + leg] = (amp * sw, 0, 0)
            fwd = sgn * math.cos(a + ph)
            bend = kb * max(0.0, fwd) ** 1.3 + 4
            p['knee_' + leg] = (bend if leg[0] == 'F' else -bend * 0.8, 0, 0)
        if run:
            p['body@'] = (0, 0, 0.045 * max(0.0, math.sin(a + 0.5)) - 0.01)
            p['body'] = (-10 * c, 0, 0)
            p['neck'] = (6 * c, 0, 0)
            p['head'] = (-4 * c, 0, 0)
            p['tail'] = (-20 + 10 * s, 0, 18 * s) if cat else (0, 0, 30 * math.sin(2 * a))
            f = 'pet_happy' if not cat else 'pet_neutral'
        else:
            p['body@'] = (0, 0, 0.018 * (0.5 + 0.5 * math.cos(2 * a)) - 0.008)
            p['body'] = (2.0 * math.sin(2 * a), 2.0 * c, 0)
            p['neck'] = (-3 * math.cos(2 * a), 0, 0)
            p['head'] = (4 * math.cos(2 * a), 0, 4 * s)
            p['tail'] = (6 * c, 0, 22 * s) if cat else (0, 0, 28 * math.sin(2 * a))
            f = 'pet_neutral' if i != 5 else 'pet_blink'
        p['ear_R'] = (6 * math.cos(2 * a), 0, 0)
        p['ear_L'] = (6 * math.cos(2 * a + 0.8), 0, 0)
    elif anim == 'sit':
        # hind legs folded under, body tilted up, front legs straight
        p = {'body': (24 + 1.0 * s, 0, 0), 'body@': (0, 0.03, -0.075 + 0.003 * s), 'neck': (-14, 0, 0),
             'head': (-8 + 3 * s, 6 * s, 5 * s),
             'leg_BL': (62, 0, 0), 'leg_BR': (62, 0, 0), 'knee_BL': (-110, 0, 0), 'knee_BR': (-110, 0, 0),
             'leg_FL': (-24, 0, 0), 'leg_FR': (-24, 0, 0), 'knee_FL': (2, 0, 0), 'knee_FR': (2, 0, 0),
             'tail': (-40, 0, 20 * s) if cat else (0, 0, 22 * s)}
        f = 'pet_blink' if i == 3 else ('pet_neutral' if cat else 'pet_happy')
    elif anim == 'happy':
        k = i % 6
        hop = [0.0, 0.05, 0.09, 0.06, 0.0, -0.01][k]
        p = {'body@': (0, 0, hop - 0.005), 'body': (6 * math.sin(a), 0, 0), 'neck': (-6, 0, 0),
             'head': (-6, 8 * math.sin(2 * a), 0), 'tail': (0, 0, 40 * (1 if k % 2 else -1))}
        tuck = 30.0 if hop > 0.03 else 4.0
        for leg in ('FL', 'FR', 'BL', 'BR'):
            p['leg_' + leg] = ((tuck if leg[0] == 'F' else -tuck) * 0.6, 0, 0)
            p['knee_' + leg] = ((tuck if leg[0] == 'F' else -tuck), 0, 0)
        p['ear_R'] = (-14 * (hop > 0.03), 0, 0)
        p['ear_L'] = (-14 * (hop > 0.03), 0, 0)
        f = 'pet_happy'
    elif anim == 'loaf':
        # cat loaf: legs tucked under, body low, content eyes
        p = {'body@': (0, 0, -0.105 + 0.003 * s), 'body': (0.6 * s, 0, 0), 'neck': (6, 0, 0),
             'head': (2, 4 * s, 3 * s), 'tail': (-70, 0, 75 + 4 * s)}
        for leg in ('FL', 'FR', 'BL', 'BR'):
            p['leg_' + leg] = ((-80 if leg[0] == 'F' else 80), 0, 0)
            p['knee_' + leg] = ((150 if leg[0] == 'F' else -150), 0, 0)
        f = 'pet_content' if i != 2 else 'pet_blink'
    p['_face'] = f
    p['_props'] = set()
    return p


def _penguin(anim, i, n):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    p = {}
    f = 'pet_neutral'
    if anim == 'idle':
        p = {'body': (0, 3 * s, 0), 'body@': (0, 0, 0.004 * s), 'head': (3 * c, 8 * s, 6 * s),
             'flip_R': (0, 10 + 8 * max(0.0, s), 0), 'flip_L': (0, 10 + 8 * max(0.0, -s), 0)}
        f = 'pet_blink' if i == 3 else 'pet_neutral'
    elif anim in ('walk', 'run'):
        run = anim == 'run'
        roll = 14.0 if run else 11.0
        lift = 0.035 if run else 0.025
        p = {'body': (-12 if run else -2, roll * s, 4 * s), 'body@': (0, 0, (0.03 if run else 0.012) *
                                                                       abs(math.sin(a)) - 0.004),
             'head': (6 if run else 2, -roll * 0.5 * s, 0),
             'foot_R': (26 * s, 0, 0), 'foot_L': (-26 * s, 0, 0),
             'foot_R@': (0, 0, lift * max(0.0, math.cos(a))), 'foot_L@': (0, 0, lift * max(0.0, -math.cos(a))),
             'flip_R': (0, (50 if run else 24) + 12 * s, 0), 'flip_L': (0, (50 if run else 24) - 12 * s, 0)}
        f = 'pet_happy' if run else ('pet_blink' if i == 6 else 'pet_neutral')
    elif anim == 'sit':
        p = {'body': (22 + 1.5 * s, 0, 0), 'body@': (0, 0.02, -0.075), 'head': (-14, 6 * s, 4 * s),
             'foot_R': (82, 4, 0), 'foot_L': (82, 4, 0), 'foot_R@': (0, -0.02, 0.02), 'foot_L@': (0, -0.02, 0.02),
             'flip_R': (0, 20 + 4 * s, 0), 'flip_L': (0, 20 - 4 * s, 0)}
        f = 'pet_blink' if i == 3 else 'pet_happy'
    elif anim == 'happy':
        k = i % 6
        hop = [0.0, 0.05, 0.085, 0.055, 0.0, -0.01][k]
        flap = 1 if k % 2 else -1
        p = {'body@': (0, 0, hop), 'body': (0, 4 * flap, 0), 'head': (-12, 6 * flap, 0),
             'flip_R': (0, 70 + 25 * flap, 0), 'flip_L': (0, 70 - 25 * flap, 0),
             'foot_R': (10 * (hop > 0.03), 0, 0), 'foot_L': (10 * (hop > 0.03), 0, 0)}
        f = 'pet_happy'
    p['_face'] = f
    p['_props'] = set()
    return p


PET_FACES = {
    'pet_neutral': ['p_eye_dot', 'p_m_closed'],
    'pet_blink':   ['p_eye_blink', 'p_m_closed'],
    'pet_happy':   ['p_eye_happy', 'p_m_open'],
    'pet_content': ['p_eye_happy', 'p_m_closed'],
}
