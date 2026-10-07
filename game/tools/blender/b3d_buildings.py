"""
b3d_buildings.py - the 12 first buildings of 봄날의 행진 (CONTRACT3D section 5), procedurally built.

Every builder works in metres, origin = footprint centre on the ground, front door on -Y.
Groups (-> GLB nodes): roof, walls, iwalls, floor, interior, exterior, anim_*.
walls_low / iwalls_low are cut automatically by b3d_kit.finalize().
Wall-hung decor (pictures, shelves, curtains, mirrors) lives in `walls` / `iwalls` so it hides
with the walls in the cutaway view.
"""
import math
from collections import OrderedDict

import b3d_kit as K
import b3d_furniture as F
from b3d_kit import bx, cy, sp, blob, seg, slot, fx, xf, grp, room, rnd, snow, snowcap, extr
from b3d_furniture import put

BUILDINGS = OrderedDict()


def building(key, name, cat, size, low=True):
    def deco(fn):
        BUILDINGS[key] = dict(key=key, name=name, cat=cat, size=size, fn=fn, low=low)
        return fn
    return deco


# =========================================================================== shared shell
class Shell:
    """Log cabin shell: walls with windows/doors, plank floor, gable roof.  Wd/Dp = wall centre lines."""

    def __init__(self, Wd, Dp, H=2.3, ridge=None, seed=1, roof=('roof_r1', 'roof_r2'), over=0.45,
                 logs=K.LOGC, r=0.13, shutter='blue', curtain='red'):
        self.Wd, self.Dp, self.H, self.seed, self.r = Wd, Dp, H, seed, r
        self.ridge = ridge or (H + Dp * 0.42 + 0.3)
        self.roof_cols, self.over, self.logs = roof, over, logs
        self.openings = []
        self.shutter, self.curtain = shutter, curtain
        self.top = None
        self.ix0, self.ix1 = -Wd / 2 + r, Wd / 2 - r
        self.iy0, self.iy1 = -Dp / 2 + r, Dp / 2 - r

    def window(self, side, off, w=0.7, zb=0.85, h=0.75, **kw):
        kw.setdefault('shutter', self.shutter)
        kw.setdefault('curtain', self.curtain)
        with grp('walls'):
            self.openings.append(K.window(side, off, self.Wd, self.Dp, w=w, zb=zb, h=h, depth=2 * self.r + 0.04,
                                          seed=self.seed + len(self.openings), **kw))

    def door(self, side, off, w=0.95, h=1.55, **kw):
        with grp('walls'):
            self.openings.append(K.door(side, off, self.Wd, self.Dp, w=w, h=h, depth=2 * self.r + 0.06, **kw))
        # threshold + step outside
        with grp('floor'):
            x, y, rot = self.wall_xy(side, off)
            with xf((x, y), rot):
                bx((w + 0.1, 2 * self.r + 0.06, K.FZ), (0, 0, 0), 'wood_m', bev=0.015)
                bx((w + 0.35, 0.5, 0.08), (0, -self.r - 0.3, 0), 'stone_l', bev=0.03)
                bx((w + 0.1, 0.32, 0.03), (0, -self.r - 0.3, 0.08), 'red_d', bev=0.0)   # door mat
        # door empties
        x, y, rot = self.wall_xy(side, off)
        with xf((x, y), rot):
            po = K.W((0, -self.r - 0.9))
            pi = K.W((0, self.r + 0.45))
        K.set_door((po.x, po.y), (pi.x, pi.y))

    def wall_xy(self, side, off):
        """Frame on wall centre line, local -Y = outside, local +X along the wall (S: +X, E: +Y ...)."""
        if side == 'S':
            return (off, -self.Dp / 2, 0)
        if side == 'N':
            return (off, self.Dp / 2, 180)
        if side == 'E':
            return (self.Wd / 2, off, 90)
        return (-self.Wd / 2, off, 270)

    def walls(self, sides='SNEW', style='log', **kw):
        self.style = style
        K.S.low_cap['walls'] = {'log': 'end', 'stone': 'stone_l'}.get(style, (kw.get('cols') or ('pale',))[0])
        with grp('walls'):
            if style == 'stone':
                self.top = K.stone_walls(self.Wd, self.Dp, self.H, self.openings, r=self.r, seed=self.seed,
                                         sides=sides, **kw)
            elif style == 'plank':
                self.top = K.plank_walls(self.Wd, self.Dp, self.H, self.openings, r=self.r, seed=self.seed,
                                         sides=sides, **kw)
            else:
                self.top = K.log_walls(self.Wd, self.Dp, self.H, self.openings, r=self.r, cols=self.logs,
                                       seed=self.seed, sides=sides)
            # corner posts hide the log-end gaps a bit + foundation stones
            R = rnd(self.seed + 11)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    bx((0.42, 0.42, 0.14), (sx * self.Wd / 2, sy * self.Dp / 2, 0), R.choice(['stone', 'stone_d']),
                       bev=0.04)
        return self.top

    def floor(self, cols=('plank', 'plank2', 'plank3'), along='X'):
        with grp('floor'):
            K.floor_boards(-self.Wd / 2, -self.Dp / 2, self.Wd / 2, self.Dp / 2, cols=cols, seed=self.seed,
                           along=along)

    def roof(self, chimneys=(), rows=6, **kw):
        with grp('roof'):
            kw.setdefault('gable_cols', self.logs)
            kw.setdefault('gable_style', getattr(self, 'style', 'log') if getattr(self, 'style', 'log') != 'plank'
                          else 'board')
            K.gable_roof(self.Wd, self.Dp, self.top, self.ridge, over=self.over, cols=self.roof_cols, seed=self.seed,
                         rows=rows, r=self.r, **kw)
            for (x, y) in chimneys:
                z0 = K.roof_z(y, self.Dp, self.top, self.ridge, self.over) - 0.3
                K.chimney(x, y, z0, self.ridge + 0.55, seed=self.seed + 3)

    def against(self, side, off, depth):
        """(x, y, rot) for a piece of `depth` whose back touches the inner face of an outer wall."""
        return K.on_wall(side, off, self.Wd, self.Dp, inset=depth / 2 + 0.03)

    def hang(self, side, off, z, fn, **kw):
        """Wall-mounted decor (in grp walls) on the inner face."""
        x, y, rot = K.on_wall(side, off, self.Wd, self.Dp, inset=0.0)
        with grp('walls~'):
            with xf((x, y, z), rot):
                fn(**kw)


def place(fn, xyr, z=None, **kw):
    x, y, rot = xyr
    return put(fn, x, y, rot, z=z, **kw)


def iwall(p0, p1, H, doors=(), seed=0, cols=('pale', 'pale2')):
    with grp('iwalls'):
        K.plank_wall(p0, p1, H, doors=doors, seed=seed, cols=cols)


def ihang(x, y, z, rot, fn, **kw):
    """Decor hung on an interior partition (grp iwalls).  rot: front direction like furniture."""
    with grp('iwalls~'):
        with xf((x, y, z), rot):
            fn(**kw)


def yard_decor(items):
    """items: list of (kind, x, y, rot/size, seed)."""
    with grp('exterior'):
        for it in items:
            kind, x, y = it[0], it[1], it[2]
            a = it[3] if len(it) > 3 else 0
            sd = it[4] if len(it) > 4 else 0
            if kind == 'logs':
                with xf((x, y), a):
                    F.log_stack(4, 0.11, 0.9, seed=sd)
            elif kind == 'barrel':
                with xf((x, y), a):
                    F.barrel_in(0.26, 0.62)
                    snowcap(0.22, (0, 0, 0.62), 0.07, seed=sd)
            elif kind == 'crate':
                with xf((x, y), a):
                    F.crate_in(0.5)
                    snowcap(0.2, (0, 0, 0.5), 0.06, seed=sd)
            elif kind == 'bush':
                K.bush(x, y, a or 0.35, seed=sd)
            elif kind == 'snow':
                K.snow_pile(x, y, a or 0.35, seed=sd)
            elif kind == 'pot':
                K.flower_pot(x, y, 0.0, seed=sd, fc=('red', 'yellow', 'pink')[sd % 3], s=1.3)
            elif kind == 'bench':
                with xf((x, y), a):
                    F.bench_in(1.1, 'wood_m', None, sit=True, n=2)
                    snow(0.9, 0.25, 0.05, (0, 0, 0.31), seed=sd)
            elif kind == 'lamp':
                cy(0.06, 1.7, (x, y, 0), 'wood_dd', segs=8)
                K.lantern(x, y - 0.0, 1.95, bracket=False)
                bx((0.3, 0.3, 0.08), (x, y, 0), 'stone', bev=0.02)
            elif kind == 'stones':
                for i in range(4):
                    blob(0.12, (x + i * 0.35, y, 0.03), 'stone_l', scale=(1.3, 1, 0.35), seed=sd + i, facet=True,
                         subdiv=1)
            elif kind == 'path':
                R = rnd(sd)
                n = int(a)
                for i in range(n):
                    bx((0.42, 0.36, 0.05), (x + R.uniform(-0.08, 0.08), y - i * 0.45, 0), R.choice(['stone_l',
                                                                                                   'stone']),
                       rot=(0, 0, R.uniform(-12, 12)), bev=0.03)


# =========================================================================== 오두막 house_1
@building('house_1', '오두막', '주택', (4.9, 4.1))
def b_house_1():
    sh = Shell(4.4, 3.6, H=2.2, seed=21, roof=('roof_r1', 'roof_r2'), shutter='blue', curtain='red')
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', -1.15)
    sh.window('S', 0.75)
    sh.window('E', -0.1)
    sh.window('W', -0.15)
    sh.window('N', 1.0, w=0.6)
    sh.walls()
    sh.floor()
    sh.roof(chimneys=[(-1.48, 1.32)])
    K.add_room('방', sh.ix0, sh.iy0, sh.ix1, sh.iy1)
    with room('방'):
        with grp('interior'):
            # sleeping corner (back right)
            place(F.bed_single, (0.45, sh.iy1 - 0.75, 0), quilt='blue')
            place(F.bed_single, (1.6, sh.iy1 - 0.75, 0), quilt='green', stripe='yellow')
            F.table_lamp(1.025, sh.iy1 - 0.2, K.FZ + 0.32)
            put(F.stool, 1.025, sh.iy1 - 0.2, 0, sit=False, h=0.32)
            put(F.rug_long, 1.03, -0.1, 0, w=1.6, d=0.8, c='teal', stripe='yellow')
            # stove + kitchen corner (back left)
            put(F.stove, -1.6, 1.2, 0)
            place(F.kitchen_counter, sh.against('W', -0.2, 0.5), w=1.0, seed=3)
            # table
            put(F.round_set, -0.1, -0.75, 0, r=0.42, n=2, start=0, seat='red', seed=5)
            put(F.plant_pot, 1.75, -1.35, 0, big=False, seed=3)
            put(F.coat_rack, -0.35, -1.42, 0)
            F.basket(-1.75, 0.55 + 0.1, K.FZ, fill='orange', seed=2)
    # wall decor
    sh.hang('E', -1.05, 1.55, F.picture, w=0.45, h=0.36)
    sh.hang('W', 1.0 - 0.1, 1.2, F.wall_shelf, w=0.6, items='plates')
    sh.hang('S', 1.75, 1.75, F.clock)
    sh.hang('N', -0.35, 1.5, F.picture, w=0.4, h=0.5, art=('pink', 'leaf', 'cream'))
    yard_decor([('logs', Wd / 2 + 0.55, 0.6, 90, 3), ('barrel', -Wd / 2 - 0.35, -D / 2 - 0.35, 0, 1),
                ('bush', Wd / 2 + 0.25, -D / 2 - 0.4, 0.3, 4), ('snow', -Wd / 2 - 0.4, 1.0, 0.4, 2),
                ('path', -1.15, -D / 2 - 0.75, 3, 7), ('pot', 0.05, -D / 2 - 0.45, 0, 1)])


def porch_door_out(x, y):
    """Move door.out to the end of a porch / path."""
    K.S.door['out'] = [round(x, 3), round(y, 3)]


def mirror(x, y, z, rot, g='walls~'):
    with grp(g):
        with xf((x, y, z), rot):
            cy(0.2, 0.04, (0, 0, 0), 'wood_l', rot=(90, 0, 0), segs=16, origin='center')
            cy(0.16, 0.05, (0, -0.01, 0), 'blue_l', rot=(90, 0, 0), segs=16, origin='center', bev=0)


def cupola(x, y, z, seed=0):
    """Little bell tower on the ridge (grp roof)."""
    bx((0.8, 0.8, 0.35), (x, y, z - 0.1), 'wood_m', bev=0.02)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.09, 0.09, 0.6), (x + sx * 0.33, y + sy * 0.33, z + 0.25), 'white', bev=0.015)
    bx((0.86, 0.86, 0.08), (x, y, z + 0.25), 'white', bev=0.02)
    cy(0.17, 0.26, (x, y, z + 0.5), 'gold', r_top=0.08, segs=12, bev=0.02)
    sp(0.04, (x, y, z + 0.47), 'iron_l', segs=8, rings=5)
    bx((1.05, 1.05, 0.25), (x, y, z + 0.85), 'roof_b1', taper=(0.05, 0.05), bev=0.02)
    snowcap(0.42, (x, y, z + 0.92), 0.1, seed=seed)
    sp(0.06, (x, y, z + 1.14), 'gold', segs=10, rings=6)


def flagpole(x, y, h=3.2, c='red'):
    bx((0.4, 0.4, 0.15), (x, y, 0), 'stone', bev=0.03)
    cy(0.04, h, (x, y, 0.15), 'white', segs=8)
    sp(0.07, (x, y, h + 0.17), 'gold', segs=10, rings=6)
    for i in range(6):
        bx((0.14, 0.03, 0.42), (x + 0.1 + i * 0.13, y + 0.025 * math.sin(i * 1.3), h - 0.5),
           c if i not in (2, 3) else 'yellow', bev=0.0, rot=(0, 0, 12 * math.sin(i)))


# =========================================================================== 마을회관 hall
@building('hall', '마을회관', '공공', (9.6, 8.8))
def b_hall():
    sh = Shell(9.0, 7.0, H=2.5, seed=31, roof=('roof_b1', 'roof_b2'), shutter='red', curtain='cream',
               logs=('log1', 'log3', 'log2'))
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', 0.4, w=1.05, h=1.6)
    for side, off, kw in (('S', -3.0, {}), ('S', 1.6, {}), ('S', 3.4, dict(w=0.5, zb=1.3, h=0.5, flowers=False)),
                          ('N', -3.2, {}), ('N', -1.5, {}), ('N', 0.8, {}), ('N', 2.6, {}),
                          ('W', -1.8, {}), ('W', 0.6, {}), ('E', 1.7, {}),
                          ('E', -2.2, dict(w=0.5, zb=1.3, h=0.5, flowers=False))):
        sh.window(side, off, **kw)
    sh.walls()
    sh.floor()
    sh.roof(chimneys=[(-4.2, 1.6), (3.75, 3.1)], rows=8)
    with grp('roof'):
        cupola(0.4, 0, sh.ridge + 0.05, seed=4)
    H = sh.top
    X0, X1, Y0, Y1 = sh.ix0, sh.ix1, sh.iy0, sh.iy1
    iwall((X0, 0.0), (X1, 0.0), H, doors=[(-1.0 - X0, 0.9), (1.4 - X0, 0.9)], seed=1)
    iwall((-1.6, Y0), (-1.6, 0.0), H, doors=[(-1.2 - Y0, 0.9)], seed=2)
    iwall((2.4, Y0), (2.4, 0.0), H, doors=[(-1.0 - Y0, 0.8)], seed=3)
    iwall((-0.4, 0.0), (-0.4, Y1), H, doors=[(0.8, 0.9)], seed=4)
    K.add_room('사무실', X0, Y0, -1.6, 0.0)
    K.add_room('현관 홀', -1.6, Y0, 2.4, 0.0)
    K.add_room('화장실', 2.4, Y0, X1, 0.0)
    K.add_room('회의실', X0, 0.0, -0.4, Y1)
    K.add_room('식당', -0.4, 0.0, X1, Y1)
    with grp('interior'):
        with room('사무실'):
            put(F.rug_long, -3.0, -1.3, 0, w=1.8, d=1.2, c='navy', stripe='mustard')
            put(F.desk, -3.0, -0.48, 0, w=1.1, seat='red')
            place(F.bookshelf, sh.against('W', -0.75, 0.32), seed=11)
            put(F.armchair, -3.6, -2.75, 200, c='rose', act='read')
            F.table_lamp(-4.05, -3.05, K.FZ)
            put(F.plant_pot, -1.95, -3.05, 0, seed=4)
            put(F.crate_in, -1.95, -2.35, 10, s=0.45, fill='paper')
        with room('현관 홀'):
            put(F.rug_long, 0.4, -1.6, 90, w=2.2, d=1.2, c='red', stripe='navy')
            put(F.bench_in, -0.75, Y0 + 0.21, 180, length=1.2, cushion='blue')
            put(F.notice_board_in, 2.25, -2.4, 270)
            put(F.plant_pot, -1.35, -0.3, 0, seed=7)
            put(F.plant_pot, 2.15, -0.3, 0, seed=8, big=False)
            put(F.coat_rack, -1.3, -2.0, 0)
            put(F.lamp_floor, 1.7, -3.05, 0)
            slot('chat', 0.0, -1.3, K.face(0.0, -1.3, 0.8, -1.3))
            slot('chat', 0.8, -1.3, K.face(0.8, -1.3, 0.0, -1.3))
        with room('화장실'):
            place(F.toilet, sh.against('E', -2.75, 0.4))
            place(F.sink, sh.against('E', -1.25, 0.5))
            put(F.plant_pot, 2.7, -3.05, 0, seed=9, big=False)
            put(F.rug_long, 3.3, -1.95, 90, w=1.0, d=0.6, c='blue', border='cream', stripe='white')
            F.basket(2.7, -0.3, K.FZ, fill='white', seed=2)
        with room('회의실'):
            put(F.rug_long, -1.85, 1.6, 0, w=2.9, d=1.9, c='green', stripe='cream')
            put(F.meeting_table, -1.85, 1.6, 0, w=2.0, d=1.0, n_side=3)
            place(F.hearth, sh.against('W', 1.6, 0.55), tall=False)
            put(F.bookshelf, -0.62, 2.85, 270, w=0.8, seed=12)
            put(F.plant_pot, X0 + 0.3, Y1 - 0.3, 0, seed=10)
            put(F.plant_pot, -0.75, 0.35, 0, seed=12, big=False)
        with room('식당'):
            place(F.cooking_range, sh.against('N', 3.75, 0.55))
            place(F.kitchen_counter, sh.against('N', 2.55, 0.5), w=1.4, sink=True, seed=4)
            place(F.cupboard, sh.against('E', 1.0, 0.4), seed=2)
            put(F.dining_set, 2.6, 1.1, 0, w=1.6, d=0.75, n_side=2, seat='yellow', seed=3)
            put(F.round_set, 0.55, 2.45, 0, r=0.38, n=2, start=90, act='tea', tea=True, seat='pink')
            put(F.barrel_in, 4.05, 2.2, 0, r=0.24, h=0.6)
            put(F.lamp_floor, -0.1, 0.3, 0)
            put(F.plant_pot, -0.1, 3.05, 0, seed=13, big=False)
    sh.hang('S', -2.0, 1.75, F.clock)
    sh.hang('N', -2.35, 1.85, F.picture, w=0.6, h=0.45)
    sh.hang('W', -0.7, 1.15, F.wall_shelf, w=0.7, items='books')
    sh.hang('E', 2.6, 1.4, F.picture, w=0.45, h=0.6, art=('cream', 'red', 'yellow'))
    mx, my, _ = K.on_wall('E', -1.25, Wd, D)
    mirror(mx, my, K.FZ + 1.15, 270)
    ihang(-1.6 - 0.05, -2.6, K.FZ + 1.5, 270, F.picture, w=0.5, h=0.4, art=('blue_l', 'green', 'cream'))
    ihang(-1.85, 0.05, K.FZ + 1.6, 0, F.picture, w=0.8, h=0.5, art=('navy', 'leaf_l', 'gold'))
    ihang(3.4, -0.05, K.FZ + 1.2, 180, F.wall_shelf, w=0.6, items='jars')
    K.porch(0.4, -D / 2 - 0.13, 2.4, 1.2, 2.35, 2.0, cols=('roof_b1', 'roof_b2'), seed=5)
    porch_door_out(0.4, -D / 2 - 1.75)
    with grp('exterior'):
        flagpole(-4.3, -4.4, 3.3)
        put(F.bench_in, -2.3, -4.35, 0, length=1.3, cushion=None, z=0.0)
        snow(1.1, 0.25, 0.05, (-2.3, -4.35, 0.31), seed=3)
    yard_decor([('lamp', -1.0, -4.7), ('lamp', 1.8, -4.7),
                ('bush', -4.9, -2.5, 0.38, 1), ('bush', 4.9, -2.0, 0.4, 2), ('bush', 4.85, 2.2, 0.35, 3),
                ('snow', -4.9, 2.4, 0.45, 4), ('pot', 2.0, -4.2, 0, 5), ('pot', -1.15, -4.2, 0, 6),
                ('barrel', 4.85, 0.3, 0, 7), ('logs', -5.0, 0.2, 90, 8)])


# =========================================================================== 큰 오두막 house_2
@building('house_2', '큰 오두막', '주택', (6.6, 5.6))
def b_house_2():
    sh = Shell(6.0, 4.6, H=2.3, seed=41, roof=('roof_g1', 'roof_g2'), shutter='red', curtain='yellow')
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', -0.4)
    sh.window('S', -1.9)
    sh.window('S', 1.9)
    sh.window('N', -1.3)
    sh.window('N', 1.9)
    sh.window('W', 0.9)
    sh.window('E', -0.15, w=0.6)
    sh.walls()
    sh.floor()
    sh.roof(chimneys=[(-2.4, 1.85), (-2.65, -0.55)])
    H = sh.top
    X0, X1, Y0, Y1 = sh.ix0, sh.ix1, sh.iy0, sh.iy1
    iwall((0.9, Y0), (0.9, Y1), H, doors=[(-0.6 - Y0, 0.9)], seed=5)
    K.add_room('부엌·거실', X0, Y0, 0.9, Y1)
    K.add_room('침실', 0.9, Y0, X1, Y1)
    with grp('interior'):
        with room('부엌·거실'):
            place(F.cooking_range, sh.against('N', -2.4, 0.55))
            place(F.kitchen_counter, sh.against('N', -1.25, 0.5), w=1.2, sink=True, body='green', seed=2)
            put(F.cupboard, 0.63, 1.5, 270, seed=6, dish='pink')
            put(F.round_set, -0.95, 0.15, 0, r=0.42, n=3, start=-90, seat='blue', seed=7)
            place(F.stove, sh.against('W', -0.6, 0.5), pot=False)
            put(F.rug_round, -1.75, -1.15, 0, r=0.75, c='rose', inner='cream', border='mustard')
            put(F.sofa, -1.95, Y0 + 0.36, 180, c='teal')
            put(F.plant_pot, 0.6, -1.9, 0, seed=3)
            put(F.coat_rack, 0.55, -1.15, 0)
            F.basket(-2.6, -1.95, K.FZ, fill='orange', seed=4)
            put(F.stool, -2.2, -0.05, 30, sit=False)
        with room('침실'):
            put(F.bed_double, 1.9, Y1 - 0.78, 0, quilt='rose')
            place(F.wardrobe, sh.against('E', -1.4, 0.45))
            put(F.stool, 2.66, 0.42, 0, sit=False, h=0.3)
            F.table_lamp(2.66, 0.42, K.FZ + 0.3)
            put(F.rug_round, 1.85, -0.35, 0, r=0.55, c='blue_l', inner='white', border='blue')
            put(F.crib, 1.35, -1.65, 0)
            put(F.plant_pot, 2.62, -0.62, 0, seed=8, big=False)
    sh.hang('S', -0.95, 1.55, F.picture, w=0.35, h=0.45, art=('cream', 'rose', 'leaf'))
    sh.hang('W', -1.65, 1.5, F.picture, w=0.6, h=0.45)
    sh.hang('E', 1.2, 1.45, F.picture, w=0.4, h=0.35, art=('pink', 'leaf_l', 'yellow'))
    sh.hang('S', 0.6, 1.8, F.clock)
    ihang(0.85, -1.5, K.FZ + 1.3, 270, F.wall_shelf, w=0.6, items='jars')
    with grp('roof'):
        K.porch_roof(-0.4, -D / 2 - 0.05, -D / 2 - 1.0, 2.15, 1.9, 1.6, cols=('roof_g1',), seed=6, posts=True)
    yard_decor([('logs', Wd / 2 + 0.55, 0.9, 90, 3), ('barrel', -Wd / 2 - 0.35, -D / 2 - 0.3, 0, 1),
                ('bush', Wd / 2 + 0.3, -D / 2 - 0.35, 0.33, 4), ('snow', -Wd / 2 - 0.45, 1.3, 0.4, 2),
                ('path', -0.4, -D / 2 - 0.75, 3, 7), ('pot', 0.55, -D / 2 - 0.4, 0, 2),
                ('pot', -1.4, -D / 2 - 0.4, 0, 3), ('bench', 1.9, -D / 2 - 0.55, 0, 5)])


# =========================================================================== 통나무집 house_3
@building('house_3', '통나무집', '주택', (8.2, 8.0))
def b_house_3():
    sh = Shell(7.6, 6.2, H=2.4, seed=51, roof=('roof_r1', 'roof_r2'), shutter='green', curtain='rose',
               logs=('log2', 'log1', 'log3'))
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', -1.6)
    for side, off, kw in (('S', -3.0, {}), ('S', 0.0, {}), ('S', 3.0, {}), ('N', -2.5, {}),
                          ('N', -0.55, dict(w=0.5, zb=1.3, h=0.5, flowers=False)), ('N', 2.5, {}),
                          ('W', -2.4, {}), ('W', 2.05, dict(w=0.6)), ('E', -0.95, dict(w=0.5)),
                          ('E', 2.0, dict(w=0.6))):
        sh.window(side, off, **kw)
    sh.walls()
    sh.floor()
    sh.roof(chimneys=[(-3.55, -1.2), (3.5, -0.4)], rows=7)
    H = sh.top
    X0, X1, Y0, Y1 = sh.ix0, sh.ix1, sh.iy0, sh.iy1
    iwall((X0, 0.3), (X1, 0.3), H, doors=[(-1.9 - X0, 0.85), (-0.3 - X0, 0.75), (1.0 - X0, 0.7)], seed=6)
    iwall((-1.2, 0.3), (-1.2, Y1), H, seed=7)
    iwall((0.6, 0.3), (0.6, Y1), H, seed=8)
    iwall((1.4, Y0), (1.4, 0.3), H, doors=[(-1.2 - Y0, 1.3)], seed=9)
    K.add_room('거실', X0, Y0, 1.4, 0.3)
    K.add_room('부엌', 1.4, Y0, X1, 0.3)
    K.add_room('침실1', X0, 0.3, -1.2, Y1)
    K.add_room('화장실', -1.2, 0.3, 0.6, Y1)
    K.add_room('침실2', 0.6, 0.3, X1, Y1)
    with grp('interior'):
        with room('거실'):
            place(F.hearth, sh.against('W', -1.2, 0.55), tall=False)
            put(F.rug_round, -2.35, -1.2, 0, r=0.8, c='red', inner='mustard')
            put(F.sofa, -1.5, -1.2, 270, c='blue')
            put(F.bookshelf, -2.7, 0.3 - 0.05 - 0.17, 0, seed=21)
            put(F.armchair, -3.0, -2.45, 135, c='mustard', act='read')
            put(F.lamp_floor, -3.42, -2.75, 0)
            put(F.dining_set, 0.0, -1.3, 0, w=1.2, d=0.75, n_side=2, seat='green', seed=8)
            put(F.plant_pot, 1.12, -2.72, 0, seed=5)
            put(F.plant_pot, -0.85, 0.02, 0, seed=6, big=False)
            put(F.lamp_floor, 1.15, 0.02, 0)
        with room('부엌'):
            place(F.cooking_range, sh.against('E', -0.4, 0.55))
            place(F.kitchen_counter, sh.against('E', -1.7, 0.5), w=1.2, sink=True, body='rose', seed=9)
            place(F.cupboard, sh.against('S', 2.2, 0.4), seed=9, dish='blue_l')
            put(F.barrel_in, 1.75, 0.0, 0, r=0.22, h=0.55)
            F.sack(1.8, -0.45, K.FZ, s=0.7, flour=False, c='sack')
            put(F.rug_long, 2.6, -1.1, 90, w=1.4, d=0.7, c='yellow', stripe='red')
        with room('침실1'):
            put(F.bed_double, -2.5, Y1 - 0.78, 0, quilt='purple', stripe='cream')
            place(F.wardrobe, sh.against('W', 0.95, 0.45))
            put(F.stool, -1.5, Y1 - 0.25, 0, sit=False)
            F.table_lamp(-1.5, Y1 - 0.25, K.FZ + 0.3)
            put(F.rug_long, -2.5, 1.05, 0, w=1.5, d=0.7, c='pink', stripe='purple')
        with room('화장실'):
            put(F.bathtub, -0.5, Y1 - 0.34, 0)
            put(F.toilet, 0.22, 2.35, 270)
            put(F.sink, -0.92, 1.05, 90)
            put(F.rug_round, -0.3, 1.3, 0, r=0.35, c='blue_l', border='white', inner='white')
            put(F.plant_pot, 0.35, 0.6, 0, seed=7, big=False)
        with room('침실2'):
            put(F.bed_single, 1.9, Y1 - 0.75, 0, quilt='yellow', stripe='red')
            put(F.bed_single, 3.1, Y1 - 0.75, 0, quilt='teal', stripe='white')
            put(F.stool, 2.5, Y1 - 0.25, 0, sit=False)
            F.table_lamp(2.5, Y1 - 0.25, K.FZ + 0.3)
            place(F.desk, sh.against('E', 0.95, 0.55), w=0.9, seat='red')
            put(F.wardrobe, 0.9, 1.95, 90, w=0.8, c='blue_l', trim='white')
            put(F.rug_round, 1.95, 1.0, 0, r=0.55, c='green', inner='yellow', border='white')
            put(F.toy_blocks, 1.85, 0.95, 0, seed=2)
            slot('play', 1.55, 1.25, K.face(1.55, 1.25, 1.9, 0.95))
            slot('play', 2.35, 0.75, K.face(2.35, 0.75, 1.9, 0.95))
    sh.hang('S', -2.2, 1.8, F.clock)
    sh.hang('S', 1.0, 1.5, F.picture, w=0.5, h=0.4, art=('blue_l', 'leaf', 'yellow'))
    sh.hang('E', -2.4, 1.3, F.wall_shelf, w=0.7, items='jars')
    sh.hang('N', -1.6, 1.5, F.picture, w=0.35, h=0.45, art=('pink', 'leaf_l', 'white'))
    sh.hang('N', 1.0, 1.45, F.picture, w=0.35, h=0.3, art=('yellow', 'green', 'red'))
    mirror(-1.2 + 0.07, 1.05, K.FZ + 1.1, 90, g='iwalls~')
    ihang(0.0, 0.25, K.FZ + 1.5, 0, F.picture, w=0.55, h=0.4, art=('cream', 'rose', 'leaf'))
    ihang(2.6, 0.25, K.FZ + 1.25, 0, F.wall_shelf, w=0.8, items='plates')
    K.porch(-1.6, -D / 2 - 0.13, 2.6, 1.2, 2.3, 1.95, cols=('roof_r1', 'roof_r2'), seed=7)
    porch_door_out(-1.6, -D / 2 - 1.75)
    with grp('exterior'):
        put(F.bench_in, -0.15, -D / 2 - 0.55, 0, length=0.9, cushion='red', z=0.0, n=1)
    yard_decor([('logs', Wd / 2 + 0.55, 1.2, 90, 3), ('barrel', -Wd / 2 - 0.4, -D / 2 - 0.2, 0, 1),
                ('crate', -Wd / 2 - 0.4, -D / 2 + 0.55, 15, 2),
                ('bush', Wd / 2 + 0.3, -D / 2 - 0.35, 0.38, 4), ('bush', 1.0, -D / 2 - 0.45, 0.3, 9),
                ('snow', -Wd / 2 - 0.45, 1.6, 0.42, 2), ('path', -1.6, -D / 2 - 1.75, 2, 7),
                ('pot', -3.0, -D / 2 - 0.45, 0, 2), ('pot', 2.8, -D / 2 - 0.4, 0, 3), ('lamp', 0.6, -D / 2 - 1.5)])


# =========================================================================== 나무꾼 작업장 woodcutter
@building('woodcutter', '나무꾼 작업장', '생산', (6.0, 5.6))
def b_woodcutter():
    oy = 1.0
    with xf((0, oy)):
        sh = Shell(3.6, 2.8, H=2.0, seed=61, roof=('roof_g1', 'roof_g2'), shutter='red', curtain=None,
                   logs=('log2', 'log3', 'log1'), over=0.4)
        sh.door('S', -0.55, w=1.1, h=1.55, lantern_side=1)
        sh.window('E', 0.15, w=0.6)
        sh.window('W', 0.15, w=0.6, flowers=False)
        sh.walls()
        sh.floor(cols=('plank2', 'plank3', 'wood_m'))
        sh.roof(rows=5)
        with grp('interior'), room('헛간'):
            place(F.workbench, sh.against('N', 0.35, 0.6), w=1.4, seed=2)
            put(F.stool, -1.15, 0.7, 0, sit=True)
            put(F.barrel_in, 1.35, -0.85, 0, r=0.22, h=0.58)
            put(F.crate_in, 1.3, -0.15, 15, s=0.45, fill=None)
            with xf((-1.3, -0.3), 90):
                F.log_stack(3, 0.09, 0.7, seed=4, snow_top=False)
            F.broom(0.1, -1.05)
            F.sack(1.35, 0.55, K.FZ, s=0.6, c='sack', flour=False)
        sh.hang('N', 0.35, 1.0, F.tool_rack, w=1.3, tools=('axe', 'saw', 'hammer', 'shovel', 'axe'))
        sh.hang('W', -0.8, 1.25, F.wall_shelf, w=0.5, items='jars')
        sh.hang('E', -0.8, 1.35, F.clock)
        ix0, iy0 = sh.ix0, sh.iy0 + oy
        K.add_room('헛간', sh.ix0, sh.iy0 + oy, sh.ix1, sh.iy1 + oy)
    K.add_room('마당', -2.8, -2.7, 2.8, -0.6)
    with grp('exterior'), room('마당'):
        put(F.chop_stump, 1.25, -1.45, 0, z=0.0)
        with xf((-2.3, -0.3), 90):
            F.log_stack(4, 0.13, 1.3, seed=5)
        with xf((-1.5, -2.0), 0):
            F.log_stack(2, 0.08, 0.55, seed=8, snow_top=False)
        # split firewood rack against the east wall
        with xf((2.25, 1.0), 90):
            for i in range(3):
                for j in range(4):
                    bx((0.1, 0.1, 0.45), (-0.45 + j * 0.3 + (i % 2) * 0.15, 0, 0.05 + i * 0.12),
                       ('end', 'pale', 'pale2')[(i + j) % 3], rot=(90, 0, 0), bev=0.02, origin='center')
            bx((1.3, 0.5, 0.06), (0, 0, 0), 'wood_d', bev=0.02)
            snow(1.0, 0.4, 0.06, (0, 0, 0.42), seed=2)
        # sawhorse with a log
        with xf((-0.2, -2.2), 15):
            for s in (-1, 1):
                seg((s * 0.4, -0.2, 0), (s * 0.4, 0.05, 0.55), 0.03, 'wood_m')
                seg((s * 0.4, 0.2, 0), (s * 0.4, -0.05, 0.55), 0.03, 'wood_m')
            K.log_(0.12, 1.1, (0, 0, 0.62), (0, 90, 0), 'bark')
            snowcap(0.15, (0.2, 0, 0.72), 0.05, seed=3)
        slot('work', -0.2, -1.65, 165)
        for i, (x, y) in enumerate(((0.75, -2.15), (1.75, -0.85), (1.6, -2.1))):
            bx((0.1, 0.1, 0.32), (x, y, 0.05), ('end', 'pale')[i % 2], rot=(90, 0, 30 * i), bev=0.02,
               origin='center')
    with grp('walls~'):
        with xf((0, oy)):
            K.sign_board(1.3, -1.4 - 0.05, 1.95, emblem='axe', w=0.55, h=0.38)
    yard_decor([('bush', 2.6, 2.1, 0.35, 3), ('snow', -2.6, 2.0, 0.4, 2), ('snow', 2.5, -2.4, 0.3, 5),
                ('barrel', -2.45, -1.6, 0, 6)])


# =========================================================================== 채석장 quarry
@building('quarry', '채석장', '생산', (6.4, 5.6))
def b_quarry():
    ox, oy = -1.1, 1.0
    with xf((ox, oy)):
        sh = Shell(3.4, 2.8, H=2.0, seed=71, roof=('roof_t1', 'roof_t2'), shutter=None, curtain=None, over=0.4)
        sh.door('S', 0.4, w=1.05, h=1.55, lantern_side=-1)
        sh.window('W', 0.1, w=0.55, flowers=False)
        sh.walls(style='stone')
        with grp('floor'):
            K.stone_floor(-sh.Wd / 2, -sh.Dp / 2, sh.Wd / 2, sh.Dp / 2, seed=3)
        sh.roof(rows=5, gable_cols=('stone', 'stone_d', 'stone_l', 'stone_w'))
        with grp('interior'), room('도구 헛간'):
            place(F.workbench, sh.against('N', -0.3, 0.6), w=1.3, seed=5)
            put(F.crate_in, 1.25, 0.75, 0, s=0.45)
            put(F.crate_in, 1.25, 0.75, 20, s=0.38, z=K.FZ + 0.45)
            put(F.barrel_in, -1.3, -0.85, 0, r=0.2, h=0.5)
            put(F.stool, -1.25, 0.05, 0, sit=True)
            F.sack(1.3, -0.25, K.FZ, s=0.55, c='sack', flour=False)
            F.broom(-0.6, -1.05)
            with xf((0.9, -0.85), 20):
                for i in range(3):
                    bx((0.3, 0.22, 0.16), (i * 0.05, 0, i * 0.16), ('stone_l', 'stone', 'stone_w')[i], bev=0.03)
        sh.hang('N', -0.3, 1.0, F.tool_rack, w=1.2, tools=('pick', 'hammer', 'shovel', 'pick'))
        sh.hang('E', -0.2, 1.2, F.wall_shelf, w=0.6, items='jars')
        K.add_room('도구 헛간', sh.ix0 + ox, sh.iy0 + oy, sh.ix1 + ox, sh.iy1 + oy)
    K.add_room('돌 마당', -3.0, -2.7, 3.0, -0.6)
    with grp('exterior'), room('돌 마당'):
        with xf((2.0, 1.2)):
            F.stone_pile(1.8, seed=3)
        with xf((2.3, -0.6)):
            F.stone_pile(1.2, seed=7, cut=False)
        # rocky outcrop at the back right
        R = rnd(9)
        for i in range(5):
            blob(R.uniform(0.35, 0.55), (1.6 + i * 0.35, 2.3 + R.uniform(-0.2, 0.2), 0.15),
                 ('stone', 'stone_d', 'stone_l')[i % 3], scale=(1.2, 1, 0.9), seed=20 + i, facet=True, subdiv=1)
        snowcap(0.4, (2.2, 2.3, 0.65), 0.08, seed=4)
        put(F.anvil_block, 0.6, -1.5, 0, z=0.0)
        # cut stone stack
        with xf((-1.8, -1.6), 0):
            for k in range(3):
                for j in range(3 - k):
                    bx((0.4, 0.3, 0.22), (-0.42 + j * 0.42 + k * 0.21, 0, k * 0.22), R.choice(['stone_l', 'stone_w']),
                       bev=0.03)
            snow(0.35, 0.25, 0.05, (0, 0, 0.66), seed=2)
        slot('work', -1.8, -2.15, 0)
        # wheelbarrow
        with xf((1.7, -2.1), -30):
            bx((0.55, 0.4, 0.22), (0, 0, 0.25), 'wood_m', taper=(1.2, 1.15), bev=0.03)
            cy(0.15, 0.06, (0, -0.42, 0.15), 'iron', rot=(0, 90, 0), segs=12, origin='center')
            for s in (-1, 1):
                seg((s * 0.18, 0.15, 0.3), (s * 0.2, 0.75, 0.35), 0.02, 'wood_l')
                seg((s * 0.18, 0.1, 0.25), (s * 0.18, 0.12, 0.0), 0.02, 'wood_d')
            blob(0.16, (0.0, 0.0, 0.48), 'stone_l', facet=True, subdiv=1, seed=2)
    with grp('walls~'):
        with xf((ox, oy)):
            K.sign_board(-1.0, -1.45, 1.95, emblem='pick', w=0.55, h=0.38)
    yard_decor([('snow', -2.9, 2.2, 0.4, 2), ('bush', -2.95, -2.3, 0.3, 4), ('stones', -0.2, -2.5, 0, 5)])


# =========================================================================== 제재소 sawmill (open-sided)
@building('sawmill', '제재소', '생산', (7.4, 5.4))
def b_sawmill():
    Wd, Dp, H = 6.2, 4.0, 2.4
    with grp('floor'):
        K.floor_boards(-Wd / 2 - 0.1, -Dp / 2 - 0.1, Wd / 2 + 0.1, Dp / 2 + 0.1, seed=3, cols=('plank2', 'wood_m',
                                                                                                 'plank3'), along='Y')
        bx((1.4, 0.5, 0.08), (0.0, -Dp / 2 - 0.35, 0), 'stone_l', bev=0.03)
    with grp('walls'):
        # posts + braces + low back rail
        xs = (-Wd / 2, -Wd / 6, Wd / 6, Wd / 2)
        for x in xs:
            for y in (-Dp / 2, Dp / 2):
                bx((0.22, 0.22, H), (x, y, K.FZ), 'wood_d', bev=0.03)
                bx((0.34, 0.34, 0.14), (x, y, 0), 'stone', bev=0.03)
        for y in (-Dp / 2, 0.0, Dp / 2):
            if y == 0.0:
                continue
        for x in (-Wd / 2, Wd / 2):
            bx((0.22, 0.22, H), (x, 0.0, K.FZ), 'wood_d', bev=0.03)
        for y in (-Dp / 2, Dp / 2):
            bx((Wd + 0.3, 0.2, 0.2), (0, y, H), 'wood_m', bev=0.03)
        for x in (-Wd / 2, Wd / 2):
            bx((0.2, Dp + 0.3, 0.2), (x, 0, H), 'wood_m', bev=0.03)
        for x in xs[:-1]:
            for y in (-Dp / 2, Dp / 2):
                xa = x + 0.15
                seg((xa, y, H - 0.05), (xa + 0.55, y, H - 0.6), 0.04, 'wood_m')
                seg((x + Wd / 3 - 0.15, y, H - 0.05), (x + Wd / 3 - 0.7, y, H - 0.6), 0.04, 'wood_m')
        # back and side rails
        for z in (0.45, 0.85):
            bx((Wd, 0.08, 0.1), (0, Dp / 2, K.FZ + z), 'wood_l', bev=0.015)
            for x in (-Wd / 2, Wd / 2):
                bx((0.08, Dp, 0.1), (x, 0, K.FZ + z), 'wood_l', bev=0.015)
        top = H + 0.2
    with grp('roof'):
        ridge = top + 1.5
        K.gable_roof(Wd, Dp, top, ridge, over=0.5, over_x=0.4, cols=('roof_t1', 'roof_t2'), seed=81, rows=6,
                     gable=False)
        for x in (-Wd / 2, 0.0, Wd / 2):
            extr([(-Dp / 2 - 0.05, 0.0), (Dp / 2 + 0.05, 0.0), (0.0, ridge - top - 0.05)], 0.1,
                 loc=(x - 0.05, 0, top), rot=(90, 0, 90), c='wood_d', bev=0.02)
    K.add_room('작업장', -Wd / 2 + 0.1, -Dp / 2 + 0.1, Wd / 2 - 0.1, Dp / 2 - 0.1)
    with grp('interior'), room('작업장'):
        put(F.saw_bench, -0.2, 0.1, 0, w=2.4)
        put(F.workbench, -2.0, Dp / 2 - 0.45, 0, w=1.3, seed=7)
        with xf((2.0, 1.15, K.FZ)):
            F.plank_stack(1.7, 7, seed=3)
        with xf((2.0, -0.85, K.FZ)):
            F.plank_stack(1.5, 5, seed=4)
        with xf((-2.45, -0.6, K.FZ), 90):
            F.log_stack(3, 0.12, 1.1, seed=6, snow_top=False)
        F.broom(1.0, -1.7)
        put(F.barrel_in, 2.75, -1.65, 0, r=0.2, h=0.5)
        F.sack(-0.9, 1.65, K.FZ, s=0.55, c='sack', flour=False)
        for i in range(6):
            sp(0.12, (0.2 + i * 0.25, -0.55 + (i % 3) * 0.1, K.FZ), 'pale', scale=(1.4, 1, 0.25), segs=8, rings=5)
    K.set_door((0.0, -Dp / 2 - 0.9), (0.0, -Dp / 2 + 0.5))
    with grp('exterior'):
        with xf((-Wd / 2 - 0.65, 0.3), 90):
            F.log_stack(4, 0.15, 1.6, seed=9)
        with xf((Wd / 2 + 0.55, -0.3), 90):
            F.plank_stack(1.3, 5, seed=8)
            snow(1.1, 0.25, 0.05, (0, 0, 0.35), seed=2)
        put(F.crate_in, Wd / 2 + 0.5, 1.4, 0, s=0.5, z=0.0)
    with grp('walls~'):
        K.sign_board(-1.4, -Dp / 2 - 0.0, 2.0, emblem='saw', w=0.6, h=0.4)
        K.lantern(1.5, -Dp / 2 - 0.12, 2.1)
    yard_decor([('snow', -3.4, 2.2, 0.4, 2), ('bush', 3.5, 2.3, 0.35, 4), ('snow', 3.2, -2.3, 0.3, 5)])


# =========================================================================== 밀 농장 farm (red barn)
@building('farm', '밀 농장', '생산', (7.6, 7.4))
def b_farm():
    oy = 0.8
    with xf((0, oy)):
        sh = Shell(5.6, 4.4, H=2.5, seed=91, roof=('roof_t1', 'roof_t2'), shutter='white', curtain=None, over=0.45,
                   ridge=2.5 + 2.4)
        sh.door('S', 0.0, w=1.5, h=1.9, leaf='red_d', lantern_side=1)
        sh.window('E', 0.6, w=0.6, flowers=False)
        sh.window('W', -0.6, w=0.6, flowers=False)
        sh.window('S', -1.8, w=0.6, flowers=True)
        sh.walls(style='plank', cols=('red', 'red_d'), trim='white')
        sh.floor(cols=('plank3', 'wood_m', 'plank2'))
        sh.roof(rows=7, gable_cols=('red', 'red_d'))
        with grp('interior'), room('헛간'):
            with xf((-1.6, 1.1)):
                F.hay_pile(1.9, 1.5, 0.75, seed=3)
            for i, (x, y, z, r) in enumerate(((-2.2, -1.2, 0, 90), (-2.2, -0.45, 0, 90), (-2.2, -0.8, 0.4, 90),
                                              (-1.55, -1.55, 0, 0))):
                with xf((x, y, K.FZ + z), r):
                    F.hay_bale()
            put(F.cot, 2.15, 1.15, 0, blanket='blue')
            put(F.crate_in, 1.45, 1.75, 0, s=0.38)
            F.table_lamp(1.45, 1.75, K.FZ + 0.38)
            put(F.stool, 1.3, 0.9, 0, sit=True)
            F.sack(2.3, -1.55, K.FZ, s=0.75, c='sack', flour=False)
            F.sack(1.85, -1.7, K.FZ, s=0.65, c='canvas', flour=False)
            F.sack(2.25, -1.0, K.FZ, s=0.6, c='sack', flour=False)
            put(F.barrel_in, -0.6, 1.8, 0, r=0.22, h=0.55)
            F.basket(-0.1, 1.85, K.FZ, fill='wheat', seed=3)
            slot('work', -0.55, 0.45, K.face(-0.55, 0.45, -1.6, 1.1))
            slot('work', 1.95, -0.2, 90)
            put(F.rug_round, 1.65, 1.0, 0, r=0.5, c='mustard', inner='red', border='cream')
        sh.hang('E', -0.6, 0.95, F.tool_rack, w=1.2, tools=('rake', 'scythe', 'shovel', 'rake'))
        sh.hang('N', 1.6, 1.4, F.picture, w=0.4, h=0.3, art=('blue_l', 'wheat', 'yellow'))
        K.add_room('헛간', sh.ix0, sh.iy0 + oy, sh.ix1, sh.iy1 + oy)
    K.add_room('밭', 0.6, -3.6, 3.6, -1.9)
    with grp('exterior'), room('밭'):
        # small wheat plot with a log border
        bx((2.8, 1.5, 0.06), (2.1, -2.75, 0), 'soil', bev=0.02)
        for s in (-1, 1):
            K.log_(0.07, 2.9, (2.1, -2.75 + s * 0.78, 0.07), (0, 90, 0), 'bark')
        R = rnd(5)
        for i in range(7):
            for j in range(3):
                x, y = 0.95 + i * 0.38, -3.2 + j * 0.45
                seg((x, y, 0.06), (x + R.uniform(-0.04, 0.04), y, 0.55), 0.012, 'straw_d')
                sp(0.04, (x, y, 0.58), 'wheat', scale=(1, 1, 2.2), segs=6, rings=4)
        slot('work', 2.1, -1.8, 180)
        # sheaves
        for k, (x, y) in enumerate(((-1.6, -2.4), (-2.4, -2.9))):
            with xf((x, y)):
                for i in range(6):
                    a = math.tau * i / 6
                    seg((math.cos(a) * 0.15, math.sin(a) * 0.15, 0), (0, 0, 0.6), 0.045, 'straw')
                cy(0.1, 0.08, (0, 0, 0.35), 'rope', segs=8)
                sp(0.12, (0, 0, 0.66), 'wheat', scale=(1, 1, 1.4), segs=8, rings=5)
        # fence posts
        for i in range(5):
            cy(0.05, 0.75, (-3.5, -3.3 + i * 0.75, 0), 'wood_m', segs=8)
            snowcap(0.06, (-3.5, -3.3 + i * 0.75, 0.75), 0.04, seed=i)
        for z in (0.35, 0.6):
            bx((0.05, 3.0, 0.07), (-3.5, -1.8, z), 'wood_l', bev=0)
        # cart wheel + trough
        cy(0.4, 0.07, (3.5, 0.4, 0.45), 'wood_m', rot=(90, 0, 80), segs=14, origin='center')
        bx((1.0, 0.4, 0.3), (3.4, 1.6, 0), 'wood_d', bev=0.03)
        bx((0.9, 0.3, 0.02), (3.4, 1.6, 0.28), 'water', bev=0)
    yard_decor([('barrel', -3.3, 1.7, 0, 1), ('snow', 3.3, 2.9, 0.4, 2), ('bush', -3.3, 3.0, 0.35, 4)])


# =========================================================================== 풍차 windmill
def tower_ring(r0, r1, H, openings, n=16, course=0.25, seed=0, cols=('stone_w', 'stone', 'stone_l', 'mortar')):
    """Round stone tower (tapering from r0 to r1).  openings: (angle_deg, half_width_m, zb, zt)."""
    R = rnd(seed)
    k = 0
    z = 0.0
    while z < H - 0.01:
        rr = r0 + (r1 - r0) * (z / H)
        for i in range(n):
            a = math.tau * (i + 0.5 * (k % 2)) / n
            ad = math.degrees(a)
            skip = False
            for (oa, hw, zb, zt) in openings:
                da = (ad - oa + 180) % 360 - 180
                if abs(math.radians(da)) * rr < hw and z + course * 0.5 > zb and z < zt:
                    skip = True
            if skip:
                continue
            ln = math.tau * rr / n * 1.02
            bx((ln, 0.3, course - 0.015), (math.cos(a) * rr, math.sin(a) * rr, z), R.choice(cols),
               rot=(0, 0, ad + 90), bev=0.04)
        z += course
        k += 1
    return z


@building('windmill', '풍차', '생산', (5.0, 5.0))
def b_windmill():
    r0, r1, H = 1.95, 1.65, 4.5
    door_a = -90.0
    ops = [(door_a, 0.55, -1, 1.65), (0.0, 0.3, 2.3, 2.9), (180.0, 0.3, 2.3, 2.9), (-90.0, 0.28, 3.1, 3.7),
           (135.0, 0.25, 1.0, 1.5)]
    K.S.low_cap['walls'] = 'stone_l'
    with grp('walls'):
        top = tower_ring(r0, r1, H, ops, seed=3)
        # door frame
        y = -r0 + 0.02
        for s in (-1, 1):
            bx((0.12, 0.38, 1.7), (s * 0.58, y, 0), 'wood_dd', bev=0.02)
        bx((1.35, 0.42, 0.16), (0, y, 1.65), 'wood_dd', bev=0.03)
    with grp('walls~'):
        with xf((-0.5, y + 0.15, K.FZ), 100):
            for i in range(4):
                bx((0.24, 0.06, 1.45), (0.13 + i * 0.25, 0.03, 0), ('wood_d', 'wood_dd')[i % 2], bev=0.01)
        # windows (round-ish glow)
        for (a, hw, zb, zt) in ops[1:]:
            rr = r0 + (r1 - r0) * ((zb + zt) / 2 / H)
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            with xf((ca * rr, sa * rr, (zb + zt) / 2), a + 90):
                bx((hw * 2 + 0.1, 0.36, zt - zb + 0.1), (0, 0, -(zt - zb) / 2 - 0.05), 'wood_dd', bev=0.02)
                bx((hw * 2 - 0.06, 0.38, zt - zb - 0.06), (0, 0, -(zt - zb) / 2 + 0.03), 'glow', bev=0)
                bx((0.04, 0.4, zt - zb - 0.06), (0, 0, -(zt - zb) / 2 + 0.03), 'wood_dd', bev=0)
        K.lantern(0.85, -r0 - 0.08, 1.75)
        K.sign_board(-0.95, -r0 + 0.05, 2.0, emblem='wheat', w=0.5, h=0.36)
    with grp('floor'):
        cy(r0 - 0.05, K.FZ, (0, 0, 0), 'stone_l', segs=20, bev=0.02)
        R = rnd(4)
        for i in range(-3, 4):
            for j in range(-3, 4):
                if math.hypot(i * 0.48, j * 0.48) < r0 - 0.45:
                    bx((0.45, 0.45, 0.012), (i * 0.48, j * 0.48, K.FZ - 0.006), R.choice(['stone_l', 'stone_w']),
                       bev=0)
        bx((1.2, 0.6, 0.08), (0, -r0 - 0.3, 0), 'stone_l', bev=0.03)
    # cap roof + axle (static)
    with grp('roof'):
        cy(r1 + 0.18, 0.18, (0, 0, top), 'wood_d', segs=20, bev=0.03)
        cy(r1 + 0.32, 1.7, (0, 0, top + 0.15), 'roof_r1', r_top=0.12, segs=16, bev=0.03)
        cy(r1 - 0.25, 1.05, (0, 0, top + 0.82), 'snow', r_top=0.08, segs=16, bev=0.03)
        for i in range(8):
            a = math.tau * i / 8
            blob(0.18, (math.cos(a) * (r1 - 0.3), math.sin(a) * (r1 - 0.3), top + 0.8), 'snow',
                 scale=(1.3, 1.3, 0.5), seed=i, subdiv=1)
        sp(0.12, (0, 0, top + 1.9), 'gold', segs=10, rings=6)
        # dormer box holding the axle
        bx((0.8, 0.9, 0.8), (0, -r1 + 0.1, top + 0.15), 'wood_m', bev=0.03)
        bx((0.95, 1.0, 0.1), (0, -r1 + 0.1, top + 0.95), 'roof_r2', bev=0.03)
        snow(0.85, 0.85, 0.07, (0, -r1 + 0.1, top + 1.04), seed=3)
        hub_y, hub_z = -r1 - 0.62, top + 0.55
        cy(0.12, 1.0, (0, -r1 - 0.1, hub_z), 'wood_dd', rot=(90, 0, 0), segs=10, origin='center')
    K.S.anim_origin['anim_blades'] = (0.0, hub_y, hub_z)
    with grp('anim_blades'):
        with xf((0.0, hub_y, hub_z)):
            cy(0.26, 0.3, (0, 0, 0), 'wood_dd', rot=(90, 0, 0), segs=14, origin='center', bev=0.04)
            sp(0.15, (0, -0.2, 0), 'red', segs=12, rings=7)
            for k in range(4):
                ang = 45 + 90 * k
                with xf((0, 0, 0)):
                    rot = math.radians(ang)
                    ca, sa = math.cos(rot), math.sin(rot)
                    # arm along direction (ca, 0, sa) in the XZ plane
                    seg((ca * 0.15, -0.05, sa * 0.15), (ca * 3.1, -0.05, sa * 3.1), 0.06, 'wood_d')
                    # sail: lattice + canvas on one side of the arm
                    px, pz = -sa, ca          # perpendicular in XZ
                    for t in range(5):
                        d = 0.8 + t * 0.55
                        seg((ca * d, -0.08, sa * d), (ca * d + px * 0.62, -0.08, sa * d + pz * 0.62), 0.022,
                            'wood_l')
                    seg((ca * 0.8 + px * 0.62, -0.08, sa * 0.8 + pz * 0.62),
                        (ca * 3.0 + px * 0.62, -0.08, sa * 3.0 + pz * 0.62), 0.025, 'wood_l')
                    cx, cz = ca * 1.9 + px * 0.31, sa * 1.9 + pz * 0.31
                    bx((2.2, 0.03, 0.56), (cx, -0.12, cz), ('canvas', 'cream')[k % 2], rot=(0, -ang, 0),
                       bev=0, origin='center')
    K.add_room('방앗간', -r0 + 0.3, -r0 + 0.3, r0 - 0.3, r0 - 0.3)
    with grp('interior'), room('방앗간'):
        put(F.millstone, 0.0, 0.25, 0)
        for i, (x, y, s) in enumerate(((-1.25, 0.65, 0.8), (-1.0, 1.15, 0.75), (-1.45, 0.15, 0.7), (-1.15, 0.45, 0.6))):
            F.sack(x, y, K.FZ + (0.55 if i == 3 else 0.0), s=s, c='sack' if i % 2 else 'flour', flour=True)
        put(F.crate_in, 1.2, 0.85, 20, s=0.45)
        put(F.barrel_in, 1.35, 0.1, 0, r=0.2, h=0.5)
        put(F.bench_in, 0.95, -1.0, 210, length=0.8, cushion=None, n=1)
        # ladder up to the cap
        with xf((0.7, 1.25, K.FZ), -35):
            for s in (-1, 1):
                seg((s * 0.2, 0, 0), (s * 0.2, 0.25, 3.6), 0.03, 'wood_l')
            for i in range(10):
                z = 0.25 + i * 0.34
                seg((-0.2, z / 3.6 * 0.25, z), (0.2, z / 3.6 * 0.25, z), 0.018, 'wood_m')
        slot('work', -0.55, 0.65, K.face(-0.55, 0.65, -1.2, 0.7))
        F.broom(-0.9, -1.2)
    K.set_door((0.0, -r0 - 0.95), (0.0, -r0 + 0.55))
    yard_decor([('barrel', 1.7, -1.6, 0, 1), ('crate', -1.75, -1.5, 25, 2), ('snow', 1.9, 1.7, 0.4, 3),
                ('bush', -1.9, 1.6, 0.35, 4), ('path', 0.0, -r0 - 0.8, 2, 5)])
    with grp('exterior'):
        F.sack(-1.25, -1.95, 0.0, s=0.7, c='sack', flour=False)
        F.sack(-0.95, -2.15, 0.0, s=0.6, c='flour', flour=False)


# =========================================================================== 빵집 bakery
@building('bakery', '빵집', '생산', (7.0, 6.2))
def b_bakery():
    sh = Shell(6.4, 5.0, H=2.4, seed=101, roof=('roof_r1', 'roof_r2'), shutter='red', curtain='white', over=0.45)
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', 1.7, w=0.95)
    sh.window('S', -1.2, w=1.4, zb=0.75, h=0.85, flowers=False, shutter=None)
    sh.window('E', -1.0, w=0.6)
    sh.window('W', 0.2, w=0.6)
    sh.window('N', 0.4, w=0.6, flowers=False)
    sh.window('E', 1.6, w=0.5, flowers=False)
    sh.walls(style='plank', cols=('cream', 'canvas'), trim='wood_d')
    sh.floor(cols=('plank', 'plank2', 'pale2'))
    sh.roof(chimneys=[(-1.3, 2.0)], rows=7, gable_cols=('cream', 'canvas'))
    X0, X1, Y0, Y1 = sh.ix0, sh.ix1, sh.iy0, sh.iy1
    K.add_room('가게', X0, Y0, X1, 0.0)
    K.add_room('굽는 곳', X0, 0.0, X1, Y1)
    with grp('interior'):
        with room('가게'):
            put(F.shop_counter, 0.2, -0.2, 0, w=1.6, act=False)
            slot('sell', 0.2, 0.45, 0, room='가게')
            slot('shop', 0.2, -0.95, 180)
            place(F.bread_shelf, sh.against('W', -1.2, 0.4), seed=1)
            put(F.market_table, -1.2, Y0 + 0.4, 180, act=False)
            slot('shop', -1.2, Y0 + 1.1, 0)
            put(F.round_set, 2.4, -0.85, 0, r=0.34, n=2, start=90, act='tea', tea=True, seat='red')
            put(F.plant_pot, X1 - 0.3, Y0 + 0.3, 0, seed=3, big=False)
            put(F.rug_long, 0.3, -1.5, 0, w=1.6, d=0.8, c='red', stripe='cream')
        with room('굽는 곳'):
            place(F.bread_oven, sh.against('N', -1.5, 1.2))
            place(F.dough_table, sh.against('N', 1.35, 0.65))
            for i, (x, y) in enumerate(((2.7, 2.0), (2.75, 1.5), (2.45, 1.75))):
                F.sack(x, y, K.FZ + (0.32 if i == 2 else 0.0), s=0.7, c='flour' if i % 2 else 'sack', flour=True)
            place(F.cupboard, sh.against('E', 0.35, 0.4), seed=5, dish='cream')
            place(F.bread_shelf, sh.against('W', 1.3, 0.4), w=1.0, act=None, seed=4)
    sh.hang('E', -0.45 - 1.0, 1.35, F.wall_shelf, w=0.6, items='jars')
    sh.hang('S', 0.3, 1.6, F.clock)
    sh.hang('N', 2.5, 1.4, F.picture, w=0.4, h=0.3, art=('cream', 'bread', 'yellow'))
    with grp('walls~'):
        K.awning(-1.2, -D / 2 - 0.15, 2.05, 1.9, depth=0.7, drop=0.35, c1='red', c2='cream', n=7)
        K.awning(1.7, -D / 2 - 0.15, 2.1, 1.3, depth=0.55, drop=0.25, c1='red', c2='cream', n=5)
        K.sign_board(0.55, -D / 2 - 0.13, 2.25, emblem='bread', w=0.6, h=0.42)
    with grp('exterior'):
        put(F.bench_in, -1.2, -D / 2 - 0.55, 0, length=1.2, cushion='red', z=0.0)
        F.basket(-2.6, -D / 2 - 0.4, 0.0, fill='bread', seed=2, r=0.2)
        put(F.crate_in, Wd / 2 + 0.35, -1.5, 10, s=0.45, z=0.0, fill='bread')
        F.sack(Wd / 2 + 0.35, -0.8, 0.0, s=0.75, c='flour', flour=False)
        F.sack(Wd / 2 + 0.4, -0.25, 0.0, s=0.7, c='sack', flour=False)
    yard_decor([('logs', -Wd / 2 - 0.5, 1.2, 90, 3), ('pot', 0.65, -D / 2 - 0.4, 0, 1), ('pot', 2.55, -D / 2 - 0.4, 0, 2),
                ('bush', Wd / 2 + 0.3, 1.7, 0.35, 4), ('path', 1.7, -D / 2 - 0.75, 2, 5)])


# =========================================================================== 선술집 tavern
@building('tavern', '선술집', '상업', (9.0, 7.6))
def b_tavern():
    sh = Shell(8.4, 6.4, H=2.6, seed=111, roof=('roof_g1', 'roof_g2'), shutter='green', curtain='red',
               logs=('log2', 'wood_m', 'log1'))
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', 0.2, w=1.1, h=1.65)
    for side, off, kw in (('S', -2.6, {}), ('S', 2.6, {}), ('N', -2.6, {}), ('N', -1.2, dict(w=0.6)),
                          ('W', -1.7, {}), ('W', 2.3, dict(w=0.6)), ('E', -1.5, {}),
                          ('E', 2.1, dict(w=0.5, flowers=False))):
        sh.window(side, off, **kw)
    sh.walls()
    sh.floor(cols=('plank3', 'wood_m', 'plank2'))
    sh.roof(chimneys=[(-3.95, 0.9)], rows=8)
    H = sh.top
    X0, X1, Y0, Y1 = sh.ix0, sh.ix1, sh.iy0, sh.iy1
    iwall((2.4, 1.0), (2.4, Y1), H, doors=[(0.55, 0.8)], seed=11, cols=('wood_l', 'plank2'))
    iwall((2.4, 1.0), (X1, 1.0), H, seed=12, cols=('wood_l', 'plank2'))
    K.add_room('홀', X0, Y0, X1, 1.0)
    K.add_room('바', X0, 1.0, 2.4, Y1)
    K.add_room('창고', 2.4, 1.0, X1, Y1)
    with grp('interior'):
        with room('바'):
            put(F.bar_counter, 0.4, 1.35, 0, w=2.6, act=False)
            slot('sell', 0.2, 2.0, 0)
            put(F.keg_rack, 0.4, Y1 - 0.6, 0, n=3)
            place(F.hearth, sh.against('W', 0.9, 0.55), act=False, tall=False)
            put(F.armchair, -2.75, 0.3, 245, c='red', act='warm')
            put(F.armchair, -2.75, 1.5, 295, c='green', act='warm')
            put(F.rug_round, -3.0, 0.9, 0, r=0.75, c='red_d', inner='mustard', border='cream')
            put(F.plant_pot, 2.1, Y1 - 0.3, 0, seed=4)
            put(F.bench_in, -1.6, Y1 - 0.22, 0, length=1.3, cushion='red')
        with room('홀'):
            for i, x in enumerate((-0.4, 0.4, 1.2)):
                slot('shop', x, 0.6, 180)
            for x in (-0.8, 1.6):
                put(F.stool, x, 0.62, 0, sit=True)
            put(F.round_set, -2.55, -1.5, 0, r=0.45, n=4, start=45, seat='red', seed=11)
            put(F.round_set, 2.6, -1.4, 0, r=0.45, n=4, start=45, seat='green', seed=12)
            put(F.round_set, 0.2, -0.95, 0, r=0.4, n=3, start=-90 + 60, seat='mustard', seed=13)
            put(F.lamp_floor, X0 + 0.3, Y0 + 0.3, 0)
            put(F.plant_pot, X1 - 0.3, Y0 + 0.3, 0, seed=6)
            put(F.barrel_in, X1 - 0.3, 0.6, 0, r=0.24, h=0.62)
            slot('chat', 2.0, 0.35, K.face(2.0, 0.35, 2.7, 0.2))
            slot('chat', 2.7, 0.2, K.face(2.7, 0.2, 2.0, 0.35))
        with room('창고'):
            put(F.barrel_in, 3.75, 2.7, 0, r=0.26, h=0.68)
            put(F.barrel_in, 3.75, 2.1, 0, r=0.26, h=0.68)
            put(F.barrel_in, 3.2, 2.75, 0, r=0.24, h=0.62)
            put(F.crate_in, 3.7, 1.4, 10, s=0.5)
            put(F.crate_in, 3.7, 1.4, 30, s=0.42, z=K.FZ + 0.5)
            F.sack(2.9, 1.35, K.FZ, s=0.7, c='sack', flour=False)
    sh.hang('W', -0.3, 1.5, F.picture, w=0.5, h=0.4, art=('navy', 'leaf_l', 'gold'))
    sh.hang('S', -1.2, 1.7, F.clock)
    sh.hang('E', -0.2, 1.4, F.wall_shelf, w=0.8, items='plates')
    sh.hang('N', 0.4, 1.35, F.wall_shelf, w=1.4, items='jars')
    K.porch(0.2, -D / 2 - 0.13, 2.6, 1.1, 2.4, 2.05, cols=('roof_g1', 'roof_g2'), seed=8)
    porch_door_out(0.2, -D / 2 - 1.65)
    with grp('walls~'):
        K.sign_board(-1.4, -D / 2 - 0.13, 2.3, emblem='mug', w=0.6, h=0.45)
    with grp('exterior'):
        for i, (x, y) in enumerate(((-3.2, -3.75), (-2.65, -3.85), (-2.9, -3.75))):
            put(F.barrel_in, x, y, 0, z=0.0 if i < 2 else 0.62, r=0.26, h=0.62)
        snowcap(0.22, (-2.9, -3.75, 1.24), 0.06, seed=3)
        put(F.bench_in, 2.5, -3.75, 0, length=1.3, cushion=None, z=0.0)
        snow(1.1, 0.25, 0.05, (2.5, -3.75, 0.31), seed=4)
    yard_decor([('lamp', -1.7, -4.3), ('lamp', 2.1, -4.3), ('logs', Wd / 2 + 0.55, 1.5, 90, 3),
                ('bush', -Wd / 2 - 0.35, -2.5, 0.38, 4), ('snow', -Wd / 2 - 0.45, 2.2, 0.42, 5),
                ('crate', Wd / 2 + 0.4, -1.2, 10, 6)])


# =========================================================================== 잡화점 shop
@building('shop', '잡화점', '상업', (6.8, 6.0))
def b_shop():
    sh = Shell(6.0, 4.6, H=2.4, seed=121, roof=('roof_r1', 'roof_r2'), shutter='white', curtain='yellow', over=0.45)
    D, Wd = sh.Dp, sh.Wd
    sh.door('S', 1.0, w=0.95)
    sh.window('S', -1.2, w=1.3, zb=0.75, h=0.85, flowers=False, shutter=None)
    sh.window('W', -1.3, w=0.6)
    sh.window('E', 0.9, w=0.6)
    sh.window('N', -1.2, w=0.6, flowers=False)
    sh.walls(style='plank', cols=('blue_l', 'teal'), trim='white')
    sh.floor(cols=('plank', 'plank2', 'pale'))
    sh.roof(rows=7, gable_cols=('blue_l', 'teal'))
    X0, X1, Y0, Y1 = sh.ix0, sh.ix1, sh.iy0, sh.iy1
    K.add_room('가게', X0, Y0, X1, Y1)
    with grp('interior'), room('가게'):
        put(F.shop_counter, 0.9, 0.7, 0, w=1.6, c='wood_d', front='wood_l')
        place(F.counter_shelf, sh.against('N', 0.9, 0.35), act=None, seed=1)
        place(F.counter_shelf, sh.against('W', 0.3, 0.35), seed=2)
        place(F.counter_shelf, sh.against('E', -0.8, 0.35), seed=3)
        put(F.market_table, -0.9, -0.85, 0, seed=1)
        put(F.crate_in, -2.4, 1.75, 0, s=0.5, fill='orange')
        put(F.crate_in, -1.85, 1.8, 20, s=0.45, fill='red')
        put(F.crate_in, -2.4, 1.75, 35, s=0.4, z=K.FZ + 0.5)
        put(F.barrel_in, 2.5, 1.65, 0, r=0.24, h=0.62)
        F.sack(-1.3, 1.85, K.FZ, s=0.65, c='sack', flour=False)
        put(F.rug_long, -0.9, -1.75, 0, w=1.6, d=0.7, c='blue', stripe='yellow')
        put(F.plant_pot, X1 - 0.3, Y0 + 0.3, 0, seed=4, big=False)
        put(F.plant_pot, X0 + 0.3, Y0 + 0.3, 0, seed=5)
        F.broom(2.6, 0.3)
    sh.hang('S', 0.0, 1.7, F.clock)
    with grp('walls~'):
        K.awning(-1.2, -D / 2 - 0.15, 2.05, 1.8, depth=0.7, drop=0.35, c1='blue', c2='white', n=7)
        K.sign_board(0.25, -D / 2 - 0.13, 2.25, emblem='bag', w=0.55, h=0.4)
    with grp('exterior'):
        put(F.crate_in, -2.4, -D / 2 - 0.45, 10, s=0.48, z=0.0, fill='orange')
        put(F.crate_in, -1.85, -D / 2 - 0.5, -8, s=0.45, z=0.0, fill='red')
        put(F.barrel_in, Wd / 2 + 0.35, -1.6, 0, r=0.24, h=0.6, z=0.0)
        F.basket(Wd / 2 + 0.35, -1.6, 0.6, fill='leaf_l', seed=3, r=0.18)
        put(F.crate_in, Wd / 2 + 0.4, -0.9, 0, s=0.45, z=0.0)
    yard_decor([('pot', 1.95, -D / 2 - 0.4, 0, 1), ('bush', -Wd / 2 - 0.35, 1.4, 0.35, 4),
                ('snow', Wd / 2 + 0.4, 1.6, 0.4, 2), ('path', 1.0, -D / 2 - 0.75, 2, 5)])


# =========================================================================== 우물 well
@building('well', '우물', '공공', (2.6, 2.6), low=False)
def b_well():
    with grp('floor'):
        R = rnd(2)
        for i in range(14):
            a = math.tau * i / 14
            bx((0.42, 0.34, 0.06), (math.cos(a) * 1.0, math.sin(a) * 1.0, 0), R.choice(['stone_l', 'stone', 'stone_w']),
               rot=(0, 0, math.degrees(a)), bev=0.025)
    with grp('exterior'):
        F.well_model()
    with grp('roof'):
        F.well_roof()
    K.add_room('우물가', -1.3, -1.3, 1.3, 1.3)
    with room('우물가'):
        slot('wash', 0.75, -1.15, K.face(0.75, -1.15, 0.75, -0.6))
        slot('chat', -1.2, -0.5, K.face(-1.2, -0.5, 0, 0))
        slot('chat', 1.25, 0.6, K.face(1.25, 0.6, 0, 0))
        slot('chat', -0.4, 1.3, K.face(-0.4, 1.3, 0, 0))
    K.set_door((0.0, -1.45), (0.0, -1.0))
