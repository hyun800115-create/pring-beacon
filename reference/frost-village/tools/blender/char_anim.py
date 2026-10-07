"""
char_anim.py - procedural animation poses for Frost Village characters.

pose_for(kind, anim, i, n, key) -> pose dict for char_geo.Rig.apply().
Loops are cyclic: frame i of n is phase i/n, so the last frame flows into the
first.  Work anims are key-posed (anticipation -> fast hit -> recover) and
interpolated with cyclic Catmull-Rom so they also loop.
Pure python (no bpy) so it can be unit-tested anywhere.
"""
import math

TAU = math.tau

# Frame counts / fps / impact frames (CONTRACT section 3)
HUMAN_ANIMS = {
    'idle': dict(frames=4, fps=6),
    'walk': dict(frames=8, fps=12),
    'carry_idle': dict(frames=4, fps=6),
    'carry_walk': dict(frames=8, fps=12),
    'chop': dict(frames=8, fps=14, impactFrame=5),
    'mine': dict(frames=8, fps=14, impactFrame=5),
    'harvest': dict(frames=6, fps=10, impactFrame=3),
    'work': dict(frames=8, fps=14),
    'happy': dict(frames=6, fps=10),
}
ANIMAL_ANIMS = {
    'idle': dict(frames=4, fps=6),
    'walk': dict(frames=8, fps=12),
}
WORK_IMPACT = {'fisherman': 4, 'lumberjack': 5, 'farmer': 4, 'miner': 5, 'hunter': 5}


# --------------------------------------------------------------------------- helpers

def _vec(v):
    if isinstance(v, (int, float)):
        return (float(v), 0.0, 0.0)
    v = tuple(float(a) for a in v)
    return v + (0.0,) * (3 - len(v))


def lerp_pose(a, b, t):
    out = {}
    for k in set(a) | set(b):
        if k.startswith('_'):
            continue
        va, vb = _vec(a.get(k, 0.0)), _vec(b.get(k, 0.0))
        out[k] = tuple(x + (y - x) * t for x, y in zip(va, vb))
    return out


def add_pose(*poses):
    out = {}
    for p in poses:
        for k, v in p.items():
            if k.startswith('_'):
                out[k] = v
                continue
            vv = _vec(v)
            if k in out:
                out[k] = tuple(x + y for x, y in zip(out[k], vv))
            else:
                out[k] = vv
    return out


def keyed(keys, i):
    """keys: list of poses, one per frame position 0..len-1 (cyclic).
    Returns the pose at integer frame i (exact)."""
    return dict(keys[i % len(keys)])


def cyc_spline(keys, t):
    """Cyclic Catmull-Rom through key poses spaced evenly; t in [0,1)."""
    n = len(keys)
    x = t * n
    i = int(math.floor(x)) % n
    u = x - math.floor(x)
    p0, p1, p2, p3 = keys[(i - 1) % n], keys[i], keys[(i + 1) % n], keys[(i + 2) % n]
    out = {}
    names = set()
    for p in (p0, p1, p2, p3):
        names |= {k for k in p if not k.startswith('_')}
    for k in names:
        a, b, c, d = (_vec(p.get(k, 0.0)) for p in (p0, p1, p2, p3))
        out[k] = tuple(0.5 * (2 * b[m] + (-a[m] + c[m]) * u + (2 * a[m] - 5 * b[m] + 4 * c[m] - d[m]) * u * u
                              + (-a[m] + 3 * b[m] - 3 * c[m] + d[m]) * u ** 3) for m in range(3))
    return out


def sym_arms(pitch, spread=0.0, elbow=0.0, yaw=0.0):
    return {'sh_R': (pitch, spread, yaw), 'sh_L': (pitch, spread, yaw),
            'el_R': (elbow, 0, 0), 'el_L': (elbow, 0, 0)}


# --------------------------------------------------------------------------- human

BASE = {'sh_R': (4, 9, 0), 'sh_L': (4, 9, 0), 'el_R': (12, 0, 0), 'el_L': (12, 0, 0)}

CARRY_ARMS = {'sh_R': (66, -16, 0), 'sh_L': (66, -16, 0), 'el_R': (34, 0, 0), 'el_L': (34, 0, 0),
              'hand_R': (-30, 0, 0), 'hand_L': (-30, 0, 0)}


def legs_walk(a, amp=34.0, knee=55.0):
    """Leg swing for phase a (radians).  R leg forward when sin(a) > 0."""
    s = math.sin(a)
    c = math.cos(a)
    hip_r = amp * s
    hip_l = -amp * s
    # knee bends while the leg swings forward (lifted), straight on contact
    knee_r = knee * max(0.0, c) ** 1.5 + 6
    knee_l = knee * max(0.0, -c) ** 1.5 + 6
    # keep the planted foot near the ground: lower the hips by leg drop
    L = 0.34
    drop = L * (1 - math.cos(math.radians(abs(hip_r) * 0.85)))
    bob = 0.022 * (0.5 + 0.5 * math.cos(2 * a))
    # chibi waddle: lean over the planted foot
    return {'hip_R': (hip_r, 2, 0), 'hip_L': (hip_l, 2, 0), 'knee_R': (knee_r, 0, 0),
            'knee_L': (knee_l, 0, 0), 'root@': (0, 0, bob - drop * 0.7),
            'root': (0, 3.5 * c, 0)}


def human_idle(i, n, carry=False):
    a = TAU * i / n
    s = math.sin(a)
    p = dict(BASE)
    p.update({'chest@': (0, 0, 0.007 * s), 'neck@': (0, 0, 0.004 * s),
              'head': (-2.0 * s, 0, 0), 'spine': (1.5 + 1.0 * s, 0, 0),
              'hips@': (0, 0, -0.004 - 0.004 * s), 'hip_R': (2 + 1.5 * s, 3, 0),
              'hip_L': (2 + 1.5 * s, 3, 0), 'knee_R': (3 + 3 * s, 0, 0), 'knee_L': (3 + 3 * s, 0, 0)})
    if carry:
        p.update(CARRY_ARMS)
        p['spine'] = (-3 + 0.8 * s, 0, 0)       # lean back a bit to balance the load
    else:
        p['sh_R'] = (4 - 2 * s, 9 + 3 * s, 0)
        p['sh_L'] = (4 - 2 * s, 9 + 3 * s, 0)
    p['_show'] = {'face_normal'}
    return p


def human_walk(i, n, carry=False):
    a = TAU * i / n
    s = math.sin(a)
    p = legs_walk(a)
    p.update({'spine': (5 if not carry else -2, 0, 7 * s), 'hips': (0, 0, -5 * s),
              'head': (-3 + 2 * math.cos(2 * a), 0, -5 * s), 'chest@': (0, 0, 0.004 * math.cos(2 * a))})
    if carry:
        p.update(CARRY_ARMS)
        p['spine'] = (-3, 0, 3 * s)
        p['hips'] = (0, 0, -6 * s)
        p['head'] = (-2, 0, -3 * s)
        # counter-rotate the shoulders so the hands stay square to the front
        p['sh_R'] = (66, -16, 0)
        p['sh_L'] = (66, -16, 0)
    else:
        sw = 40.0
        p['sh_R'] = (-sw * s + 4, 10, 0)
        p['sh_L'] = (sw * s + 4, 10, 0)
        p['el_R'] = (18 + 14 * max(0, -s), 0, 0)
        p['el_L'] = (18 + 14 * max(0, s), 0, 0)
    p['_show'] = {'face_normal'}
    return p


def _tool_swing_keys(tool, low=False):
    """8 key poses for a two-handed overhead swing.  Frame 5 = impact."""
    # total tool angle from straight down = arm pitch + elbow + spine pitch + tool tilt(18)
    imp_arm = 8 if low else 16
    imp_sp = 30 if low else 22
    keys = [
        # 0 ready (tool raised in front)
        {**sym_arms(40, -26, 30), 'spine': (6, 0, 0), 'head': (4, 0, 0)},
        # 1 lift
        {**sym_arms(100, -24, 40), 'spine': (-4, 0, 10), 'head': (-4, 0, 0)},
        # 2 wind-up (anticipation)
        {**sym_arms(140, -22, 50), 'spine': (-12, 0, 16), 'head': (-10, 0, 0), 'root@': (0, 0.02, 0)},
        # 3 hold at the top (squash)
        {**sym_arms(146, -22, 54), 'spine': (-15, 0, 18), 'head': (-12, 0, 0), 'root@': (0, 0.025, -0.012)},
        # 4 fast swing
        {**sym_arms(80, -26, 10), 'spine': (8, 0, 4), 'head': (2, 0, 0), 'root@': (0, 0.0, 0.006)},
        # 5 IMPACT
        {**sym_arms(imp_arm, -28, 0), 'spine': (imp_sp, 0, -6), 'head': (8, 0, 0), 'root@': (0, -0.02, -0.012)},
        # 6 recoil
        {**sym_arms(imp_arm + 10, -28, 6), 'spine': (imp_sp - 3, 0, -4), 'head': (6, 0, 0),
         'root@': (0, -0.015, -0.006)},
        # 7 recover
        {**sym_arms(32, -27, 20), 'spine': (10, 0, -1), 'head': (5, 0, 0), 'root@': (0, -0.006, 0)},
    ]
    stance = {'hip_R': (-8, 6, 0), 'hip_L': (14, 6, 0), 'knee_R': (8, 0, 0), 'knee_L': (10, 0, 0)}
    out = []
    for k in keys:
        k = {**stance, **k}
        k['_show'] = {'face_normal', tool}
        out.append(k)
    return out


def human_harvest(i, n):
    """Squat & grab.  Hip/knee pairs keep the feet planted (thigh fwd t, knee 2t,
    root drop ~ leg shortening)."""
    def squat(t, drop):
        return {'hip_R': (t, 4, 0), 'hip_L': (t, 4, 0), 'knee_R': (2 * t, 0, 0), 'knee_L': (2 * t, 0, 0),
                'root@': (0, 0, -drop)}
    keys = [
        {**sym_arms(20, 4, 30), 'spine': (4, 0, 0), **squat(4, 0.002)},
        {**sym_arms(46, -8, 16), 'spine': (16, 0, 0), 'head': (4, 0, 0), **squat(18, 0.018)},
        {**sym_arms(60, -14, 6), 'spine': (24, 0, 0), 'head': (8, 0, 0), **squat(30, 0.046)},
        # 3 grab (impact)
        {**sym_arms(56, -22, 2), 'spine': (26, 0, 0), 'head': (10, 0, 0), **squat(32, 0.052)},
        # 4 pull up
        {**sym_arms(34, -20, 64), 'spine': (8, 0, 0), 'head': (-4, 0, 0), **squat(10, 0.006)},
        # 5 proud little lift
        {**sym_arms(28, -12, 78), 'spine': (-4, 0, 0), 'head': (-8, 0, 0), 'root@': (0, 0, 0.014)},
    ]
    p = keys[i % len(keys)]
    p['_show'] = {'face_normal'} if i not in (4, 5) else {'face_happy'}
    return p


def human_happy(i, n):
    keys = [
        {**sym_arms(14, 14, 30), 'root@': (0, 0, -0.03), 'spine': (8, 0, 0), 'head': (6, 0, 0),
         'hip_R': (24, 4, 0), 'hip_L': (24, 4, 0), 'knee_R': (44, 0, 0), 'knee_L': (44, 0, 0)},
        {**sym_arms(120, 34, 20), 'root@': (0, 0, 0.05), 'spine': (-4, 0, 0), 'head': (-8, 0, 0),
         'hip_R': (4, 4, 0), 'hip_L': (4, 4, 0), 'knee_R': (10, 0, 0), 'knee_L': (10, 0, 0)},
        {**sym_arms(158, 40, 14), 'root@': (0, 0, 0.10), 'spine': (-8, 0, 0), 'head': (-12, 0, 0),
         'hip_R': (14, 4, 0), 'hip_L': (14, 4, 0), 'knee_R': (40, 0, 0), 'knee_L': (40, 0, 0)},
        {**sym_arms(150, 42, 20), 'root@': (0, 0, 0.07), 'spine': (-6, 0, 0), 'head': (-10, 0, 0),
         'hip_R': (8, 4, 0), 'hip_L': (8, 4, 0), 'knee_R': (24, 0, 0), 'knee_L': (24, 0, 0)},
        {**sym_arms(60, 30, 30), 'root@': (0, 0, -0.025), 'spine': (8, 0, 0), 'head': (4, 0, 0),
         'hip_R': (22, 4, 0), 'hip_L': (22, 4, 0), 'knee_R': (40, 0, 0), 'knee_L': (40, 0, 0)},
        {**sym_arms(16, 14, 24), 'root@': (0, 0, -0.008), 'spine': (3, 0, 0), 'head': (0, 0, 0),
         'hip_R': (6, 4, 0), 'hip_L': (6, 4, 0), 'knee_R': (10, 0, 0), 'knee_L': (10, 0, 0)},
    ]
    p = keys[i % len(keys)]
    p['_show'] = {'face_happy'} if i in (1, 2, 3, 4) else {'face_normal'}
    return p


def _fish_keys():
    """Rod angle from straight down = sh_R pitch + el_R + spine pitch + 70 (rod tilt)."""
    L = lambda p, sp, e: {'sh_L': (p, sp, 0), 'el_L': (e, 0, 0)}
    R = lambda p, sp, e: {'sh_R': (p, sp, 0), 'el_R': (e, 0, 0)}
    keys = [
        {**R(40, -8, 25), **L(36, -30, 46), 'spine': (4, 0, 0), '_cast': 0.0},
        {**R(92, -5, 45), **L(42, -26, 52), 'spine': (-6, 0, 6), 'head': (-6, 0, 0), '_cast': 0.0},
        {**R(122, 0, 58), **L(40, -24, 50), 'spine': (-10, 0, 10), 'head': (-8, 0, 0),
         'root@': (0, 0.02, -0.008), '_cast': 0.0},
        {**R(74, -8, 25), **L(36, -28, 46), 'spine': (6, 0, 2), 'head': (2, 0, 0), '_cast': 0.25},
        # 4 IMPACT: bobber lands on the water
        {**R(34, -10, 12), **L(34, -30, 44), 'spine': (10, 0, -2), 'head': (6, 0, 0),
         'root@': (0, -0.015, 0), '_cast': 1.0},
        {**R(38, -10, 18), **L(28, -30, 62), 'spine': (6, 0, 0), 'head': (4, 0, 0), '_cast': 1.0},
        {**R(33, -10, 12), **L(42, -28, 38), 'spine': (7, 0, 0), 'head': (5, 0, 0), '_cast': 1.0},
        {**R(44, -9, 24), **L(34, -32, 54), 'spine': (5, 0, 0), 'head': (2, 0, 0), '_cast': 0.55},
    ]
    stance = {'hip_R': (-6, 6, 0), 'hip_L': (10, 6, 0), 'knee_R': (6, 0, 0), 'knee_L': (8, 0, 0)}
    return [{**stance, **k, '_show': {'face_normal', 'rod'}} for k in keys]


def _sickle_keys():
    """Low horizontal sweep at wheat height: right arm pitched forward-down (arm pitch +
    spine bend ~ 60 deg from straight down), yaw swings it across the body."""
    keys = [
        {'sh_R': (34, 10, -38), 'el_R': (22, 0, 0), 'spine': (24, 0, 10), 'sh_L': (58, -8, 0), 'el_L': (14, 0, 0)},
        {'sh_R': (32, 16, -58), 'el_R': (28, 0, 0), 'spine': (24, 0, 18), 'sh_L': (56, -8, 0), 'el_L': (16, 0, 0)},
        {'sh_R': (30, 18, -66), 'el_R': (30, 0, 0), 'spine': (25, 0, 22), 'sh_L': (58, -10, 0), 'el_L': (12, 0, 0),
         'root@': (0, 0.01, -0.01)},
        {'sh_R': (38, 4, -10), 'el_R': (12, 0, 0), 'spine': (26, 0, 4), 'sh_L': (52, -8, 0), 'el_L': (24, 0, 0)},
        # 4 IMPACT (cut)
        {'sh_R': (40, -6, 30), 'el_R': (6, 0, 0), 'spine': (27, 0, -14), 'sh_L': (40, -6, 0), 'el_L': (52, 0, 0),
         'root@': (0, -0.012, -0.01)},
        {'sh_R': (36, -6, 40), 'el_R': (10, 0, 0), 'spine': (26, 0, -18), 'sh_L': (36, -6, 0), 'el_L': (60, 0, 0)},
        {'sh_R': (34, 4, 10), 'el_R': (18, 0, 0), 'spine': (25, 0, -6), 'sh_L': (46, -8, 0), 'el_L': (36, 0, 0)},
        {'sh_R': (34, 8, -20), 'el_R': (20, 0, 0), 'spine': (24, 0, 4), 'sh_L': (54, -8, 0), 'el_L': (18, 0, 0)},
    ]
    stance = {'hip_R': (18, 8, 0), 'hip_L': (18, 8, 0), 'knee_R': (30, 0, 0), 'knee_L': (30, 0, 0),
              'root@': (0, 0, -0.025), 'head': (10, 0, 0)}
    out = []
    for k in keys:
        kk = {**stance, **k}
        if 'root@' in k:
            kk['root@'] = tuple(a + b for a, b in zip(stance['root@'], k['root@']))
        kk['_show'] = {'face_normal', 'sickle'}
        out.append(kk)
    return out


def _bow_keys():
    """Bow in the right hand at chest height, string drawn by the left hand
    (IK target under the chin).  Slight archer twist brings the bow forward."""
    B = lambda p, sp, yw, e: {'sh_R': (p, sp, yw), 'el_R': (e, 0, 0)}
    keys = [
        # 0 bow low, nocking
        ({**B(34, 4, 0, 14), 'ik_L': (-0.05, -0.20, -0.10), 'spine': (3, 0, 4)}, 0.0, True),
        # 1 raise
        ({**B(66, -4, -12, 8), 'ik_L': (-0.10, -0.28, -0.04), 'spine': (1, 0, 12), 'head': (0, 0, -8)}, 0.05, True),
        # 2 draw
        ({**B(76, -6, -18, 2), 'ik_L': (-0.06, -0.20, 0.0), 'spine': (-1, 0, 18), 'head': (2, 0, -12)}, 0.55, True),
        # 3 full draw
        ({**B(80, -6, -22, 0), 'ik_L': (0.02, -0.10, 0.03), 'spine': (-3, 0, 22), 'head': (2, 0, -16)}, 1.0, True),
        # 4 hold (tension)
        ({**B(80, -6, -22, 0), 'ik_L': (0.04, -0.09, 0.03), 'spine': (-4, 0, 23), 'head': (2, 0, -16),
          'root@': (0, 0.005, -0.006)}, 1.0, True),
        # 5 IMPACT: release - the drawing hand flicks back and out
        ({**B(82, -6, -22, 0), 'sh_L': (40, 52, 0), 'el_L': (40, 0, 0), 'spine': (-6, 0, 22), 'head': (0, 0, -16),
          'root@': (0, 0.012, 0)}, 0.0, False),
        ({**B(78, -5, -18, 4), 'sh_L': (24, 46, 0), 'el_L': (36, 0, 0), 'spine': (-3, 0, 16), 'head': (0, 0, -12)},
         0.0, False),
        ({**B(52, 0, -6, 10), 'sh_L': (14, 24, 0), 'el_L': (36, 0, 0), 'spine': (1, 0, 8), 'head': (0, 0, -4)},
         0.0, False),
    ]
    stance = {'hip_R': (12, 8, 0), 'hip_L': (-8, 8, 0), 'knee_R': (8, 0, 0), 'knee_L': (6, 0, 0),
              'hips': (0, 0, 6)}
    out = []
    for k, draw, arrow in keys:
        kk = {**stance, **k, '_draw': draw}
        kk['_show'] = {'face_normal', 'bow'} | ({'arrow'} if arrow else set())
        out.append(kk)
    return out


def work_pose(key, i, n):
    if key == 'lumberjack':
        return keyed(_tool_swing_keys('axe'), i)
    if key == 'miner':
        return keyed(_tool_swing_keys('pickaxe', low=True), i)
    if key == 'fisherman':
        return keyed(_fish_keys(), i)
    if key == 'farmer':
        return keyed(_sickle_keys(), i)
    if key == 'hunter':
        return keyed(_bow_keys(), i)
    raise KeyError(key)


# --------------------------------------------------------------------------- animals

def animal_walk(i, n, key):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    amp = 28.0 if key == 'deer' else 30.0
    kb = 46.0 if key == 'deer' else 34.0
    p = {}
    # trot: diagonal pairs move together
    for leg, sgn in (('FL', 1), ('BR', 1), ('FR', -1), ('BL', -1)):
        sw = sgn * s
        p['leg_' + leg] = (amp * sw, 0, 0)
        fwd = sgn * c                       # >0 while this leg swings forward
        bend = kb * max(0.0, fwd) ** 1.3 + 4
        p['knee_' + leg] = (bend if leg[0] == 'F' else -bend * 0.8, 0, 0)
    bob = 0.020 if key == 'deer' else 0.026
    p['body@'] = (0, 0, bob * (0.5 + 0.5 * math.cos(2 * a)) - 0.012)
    p['body'] = (2.0 * math.sin(2 * a), 2.5 * c if key == 'boar' else 1.5 * c, 0)
    p['neck'] = (-3 * math.cos(2 * a), 0, 0)
    p['head'] = (4 * math.cos(2 * a), 0, 3 * s)
    p['tail'] = (0, 0, 22 * s) if key == 'boar' else (10 * math.cos(2 * a), 0, 10 * s)
    p['ear_R'] = (6 * math.cos(2 * a), 0, 0)
    p['ear_L'] = (6 * math.cos(2 * a + 0.8), 0, 0)
    return p


def animal_idle(i, n, key):
    a = TAU * i / n
    s, c = math.sin(a), math.cos(a)
    p = {'body@': (0, 0, 0.006 * s), 'body': (0.8 * s, 0, 0),
         'neck': (-4 + 3 * s, 0, 0) if key == 'deer' else (2 * s, 0, 0),
         'head': (2 * c, 0, 7 * s), 'tail': (0, 0, 24 * s),
         'ear_R': (0, 0, 0), 'ear_L': (0, 0, 0)}
    if i == 2:
        p['ear_R'] = (-18, 0, 0)            # ear twitch
    for leg in ('FL', 'FR', 'BL', 'BR'):
        p['knee_' + leg] = (3 + 2 * s if leg[0] == 'F' else -3 - 2 * s, 0, 0)
    return p


def pose_for(kind, anim, i, n, key=''):
    if kind == 'human':
        if anim == 'idle':
            return human_idle(i, n)
        if anim == 'carry_idle':
            return human_idle(i, n, carry=True)
        if anim == 'walk':
            return human_walk(i, n)
        if anim == 'carry_walk':
            return human_walk(i, n, carry=True)
        if anim == 'chop':
            return keyed(_tool_swing_keys('axe'), i)
        if anim == 'mine':
            return keyed(_tool_swing_keys('pickaxe', low=True), i)
        if anim == 'harvest':
            return human_harvest(i, n)
        if anim == 'happy':
            return human_happy(i, n)
        if anim == 'work':
            return work_pose(key, i, n)
    if kind == 'animal':
        if anim == 'idle':
            return animal_idle(i, n, key)
        if anim == 'walk':
            return animal_walk(i, n, key)
    raise KeyError((kind, anim))
