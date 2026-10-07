"""
char_geo.py - low-level procedural geometry + rig helpers for Frost Village characters.

Used by char_build.py (not run directly).  Everything is built with bmesh from
math (no bpy.ops), so it is fast and deterministic.

Shapes:  lathe (surface of revolution, optional oval cross-section), capsule,
ellipsoid, shell (sphere whose radius is a function of direction -> hair, hoods,
beards), fur ring (bumpy torus), rounded box, tube between two points.
Rig:     Rig() = named pivot empties (quaternion), rest pose + pose application.
"""
import math

import bpy
import bmesh
from mathutils import Vector, Quaternion, Matrix

TAU = math.tau


# --------------------------------------------------------------------------- objects

def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh_obj(name, bm, material, parent=None, loc=(0, 0, 0), rot=None, scale=None,
             smooth=True, subsurf=0):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.materials.append(material)
    ob = link(bpy.data.objects.new(name, me))
    if parent is not None:
        ob.parent = parent
    ob.location = loc
    if rot is not None:
        if isinstance(rot, Quaternion):
            ob.rotation_mode = 'QUATERNION'
            ob.rotation_quaternion = rot
        else:
            ob.rotation_euler = [math.radians(a) for a in rot]
    if scale is not None:
        ob.scale = scale
    if subsurf:
        m = ob.modifiers.new('sub', 'SUBSURF')
        m.levels = subsurf
        m.render_levels = subsurf
    return ob


def empty(name, parent=None, loc=(0, 0, 0)):
    e = link(bpy.data.objects.new(name, None))
    e.empty_display_size = 0.05
    e.rotation_mode = 'QUATERNION'
    if parent is not None:
        e.parent = parent
    e.location = loc
    return e


# --------------------------------------------------------------------------- curves

def catmull(ctrl, n=24):
    """Smooth polyline through 2D control points (Catmull-Rom), n samples total."""
    pts = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    segs = len(ctrl) - 1
    out = []
    for k in range(n):
        t = k / (n - 1) * segs
        i = min(int(t), segs - 1)
        u = t - i
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        u2, u3 = u * u, u * u * u
        out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * u +
                                (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * u2 +
                                (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * u3) for c in range(2)))
    return out


# --------------------------------------------------------------------------- bmesh shapes

def bm_lathe(profile, seg=32, sx=1.0, sy=1.0, cap_bottom=True, cap_top=True, smooth_n=0,
             yoff=None):
    """Surface of revolution around Z.  profile = [(r, z), ...] bottom->top.
    sx/sy scale the cross-section (oval bodies).  smooth_n>0 resamples the
    profile with Catmull-Rom.  yoff(z) optionally shifts rings along Y."""
    if smooth_n:
        profile = catmull(profile, smooth_n)
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        dy = yoff(z) if yoff else 0.0
        if r <= 1e-5:
            rings.append([bm.verts.new((0.0, dy, z))])
        else:
            rings.append([bm.verts.new((r * sx * math.cos(TAU * i / seg),
                                        r * sy * math.sin(TAU * i / seg) + dy, z))
                          for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(seg):
                bm.faces.new((a[0], b[(i + 1) % seg], b[i])[::-1])
        elif len(b) == 1:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[0]))
        else:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    if cap_bottom and len(rings[0]) > 1:
        c = bm.verts.new((0.0, yoff(profile[0][1]) if yoff else 0.0, profile[0][1]))
        a = rings[0]
        for i in range(seg):
            bm.faces.new((a[(i + 1) % seg], a[i], c))
    if cap_top and len(rings[-1]) > 1:
        c = bm.verts.new((0.0, yoff(profile[-1][1]) if yoff else 0.0, profile[-1][1]))
        a = rings[-1]
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], c))
    return bm


def bm_ellipsoid(rx, ry, rz, seg=32, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * rx, v.co.y * ry, v.co.z * rz))
    return bm


def bm_capsule(r, length, r_end=None, seg=24, rings=12, rz_end=None):
    """Capsule hanging DOWN from the origin: top sphere centre at z=0, bottom
    sphere centre at z=-length.  r_end tapers the lower end."""
    r_end = r if r_end is None else r_end
    prof = []
    n = rings
    # bottom hemisphere (radius r_end) then top hemisphere (radius r)
    for k in range(n + 1):
        a = -math.pi / 2 + (math.pi / 2) * k / n
        prof.append((r_end * math.cos(a), -length + (rz_end or r_end) * math.sin(a)))
    for k in range(n + 1):
        a = (math.pi / 2) * k / n
        prof.append((r * math.cos(a), r * math.sin(a)))
    prof[0] = (0.0, prof[0][1])
    prof[-1] = (0.0, prof[-1][1])
    return bm_lathe(prof, seg=seg, cap_bottom=False, cap_top=False)


def bm_shell(rx, ry, rz, radial, seg=48, rings=24, zmin=-1.0):
    """Sphere whose radius is multiplied by radial(x, y, z) for the unit
    direction (x, y, z).  Lets hair / hoods / beards dip smoothly *into* the
    head where they should not be, giving clean rounded edges."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        d = v.co.normalized()
        f = radial(d.x, d.y, d.z)
        v.co = Vector((d.x * rx * f, d.y * ry * f, d.z * rz * f))
    if zmin > -1.0:
        kill = [v for v in bm.verts if v.co.z < zmin * rz]
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    return bm


def _fur_noise(u, k, seed):
    return (0.55 * math.cos(k * u + seed) + 0.30 * math.cos((k * 2 + 1) * u + 1.3 * seed + 0.7)
            + 0.15 * math.cos((k * 3 - 1) * u + 2.1 * seed))


def bm_ring(R, r, seg=64, segr=14, sx=1.0, sy=1.0, rz=1.0, tufts=0, bump=0.0, seed=0.0,
            u0=0.0, u1=TAU, taper=None, closed=True, flat_in=0.0):
    """Torus around Z (major radius R, minor r).  tufts/bump make a puffy fur
    trim.  u0..u1 + taper(t)->scale make open crescents (sickle, pickaxe)."""
    bm = bmesh.new()
    full = closed and abs(u1 - u0 - TAU) < 1e-6
    nu = seg if full else seg + 1
    grid = []
    for i in range(nu):
        t = i / seg
        u = u0 + (u1 - u0) * t
        sc = taper(t) if taper else 1.0
        row = []
        for j in range(segr):
            v = TAU * j / segr
            rr = r * sc
            if bump:
                outer = 0.55 + 0.45 * math.cos(v)
                rr *= 1.0 + bump * outer * (0.5 + 0.5 * _fur_noise(u, tufts, seed))
            cx = (R + rr * math.cos(v) * (1 - flat_in * (math.cos(v) < 0)))
            row.append(bm.verts.new((cx * math.cos(u) * sx, cx * math.sin(u) * sy,
                                     rr * math.sin(v) * rz)))
        grid.append(row)
    rows = len(grid)
    for i in range(rows if full else rows - 1):
        a, b = grid[i], grid[(i + 1) % rows]
        for j in range(segr):
            bm.faces.new((a[j], b[j], b[(j + 1) % segr], a[(j + 1) % segr]))
    if not full:
        for row, flip in ((grid[0], True), (grid[-1], False)):
            c = bm.verts.new(sum((vv.co for vv in row), Vector()) / len(row))
            for j in range(segr):
                f = (row[j], row[(j + 1) % segr], c)
                bm.faces.new(f[::-1] if flip else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_box(sx, sy, sz, bevel=0.01, segs=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type='OFFSET',
                        segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)
    return bm


def bm_slab(points, thickness, bevel=0.006, segs=2):
    """Extrude a 2D outline [(y, z), ...] (counter-clockwise) along X, centred."""
    bm = bmesh.new()
    h = thickness / 2
    front = [bm.verts.new((h, y, z)) for y, z in points]
    back = [bm.verts.new((-h, y, z)) for y, z in points]
    n = len(points)
    bm.faces.new(front)
    bm.faces.new(back[::-1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[j], front[i], back[i], back[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type='OFFSET',
                        segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)
    return bm


def bm_cyl(r1, r2, h, seg=16, centered=False):
    """Cylinder/cone along +Z from z=0 to z=h (or centred)."""
    z0 = -h / 2 if centered else 0.0
    return bm_lathe([(r1, z0), (r2, z0 + h)], seg=seg)


def bm_transform(bm, mat):
    bmesh.ops.transform(bm, matrix=mat, verts=bm.verts)
    return bm


def merge(*bms):
    """Join several bmeshes into the first one."""
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new('_tmp')
        b.to_mesh(me)
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
        b.free()
    return out


def look_rot(direction, up=(0, 0, 1), axis='Z'):
    """Quaternion that turns local `axis` toward `direction`."""
    d = Vector(direction).normalized()
    return d.to_track_quat(axis, 'Y' if axis == 'Z' else 'Z')


# --------------------------------------------------------------------------- rig

def q_axis(axis, deg):
    return Quaternion(Vector(axis), math.radians(deg))


class Rig:
    """Named pivot empties with rest transforms.  Poses are dicts:
        joint -> (pitch, roll, yaw) degrees    (pitch>0 = forward / bend forward,
                                                roll>0  = outward for _R/_L limbs,
                                                yaw>0   = counter-clockwise from above)
        joint+'@' -> (dx, dy, dz) metres translation offset
    For knees, pitch>0 bends the shin backwards."""

    def __init__(self, kind='human'):
        self.kind = kind
        self.j = {}
        self.rest_loc = {}
        self.side = {}
        self.toggles = {}      # name -> list of objects (shown/hidden per frame)
        self.strings = []      # world-space dynamic objects updated after posing
        self.meta = {}
        self.state = {}

    def add(self, name, parent, loc, side=0):
        p = self.j[parent] if isinstance(parent, str) else parent
        e = empty(name, p, loc)
        self.j[name] = e
        self.rest_loc[name] = Vector(loc)
        self.side[name] = side
        return e

    def toggle(self, name, objs):
        self.toggles.setdefault(name, []).extend(objs)

    def reset(self):
        for n, e in self.j.items():
            e.rotation_quaternion = Quaternion()
            e.location = self.rest_loc[n]
            e.scale = (1, 1, 1)

    def apply(self, pose, yaw_deg=0.0):
        self.reset()
        root = self.j['root']
        root.rotation_quaternion = q_axis((0, 0, 1), yaw_deg)
        for key, val in pose.items():
            if key.startswith('_'):
                continue
            if key.endswith('@'):
                n = key[:-1]
                if n in self.j:
                    self.j[n].location = self.rest_loc[n] + Vector(val)
                continue
            if key.endswith('%'):
                n = key[:-1]
                if n in self.j:
                    self.j[n].scale = val
                continue
            if key not in self.j:
                continue
            if key == 'root':
                p, r, y = val
                root.rotation_quaternion = (q_axis((0, 0, 1), yaw_deg + y) @
                                            q_axis((0, 1, 0), r) @ q_axis((1, 0, 0), -p))
                continue
            if isinstance(val, (int, float)):
                val = (val, 0.0, 0.0)
            p, r, y = (list(val) + [0.0, 0.0])[:3]
            s = self.side.get(key, 0)
            # roll: outward for limbs.  Right side is -X, so outward = +Y rotation.
            rr = r * (1 if s >= 0 else -1) if s else r
            yy = y * (1 if s >= 0 else -1) if s else y
            q = q_axis((0, 0, 1), yy) @ q_axis((1, 0, 0), -p) @ q_axis((0, 1, 0), rr)
            if key.startswith('knee') or key.startswith('hock'):
                q = q_axis((1, 0, 0), p)
            self.j[key].rotation_quaternion = q
        for side in ('R', 'L'):
            if 'ik_' + side in pose:
                v = list(pose['ik_' + side])
                pole = v[3:6] if len(v) >= 6 else None
                self.solve_arm(side, v[:3], pole)
        self.state = {k: v for k, v in pose.items() if k.startswith('_')}
        shown = pose.get('_show', set())
        vis = {}
        for name, objs in self.toggles.items():
            for o in objs:
                vis[o.name] = vis.get(o.name, False) or (name in shown)
        for name, objs in self.toggles.items():
            for o in objs:
                o.hide_render = not vis[o.name]
                o.hide_viewport = not vis[o.name]

    def solve_arm(self, side, target, pole=None):
        """Analytic 2-bone IK: put hand_<side> at `target` (chest-local metres).
        `pole` = direction the elbow should point (default: down, back, outward)."""
        S = self.rest_loc['sh_' + side]
        L1 = self.rest_loc['el_' + side].length
        L2 = self.rest_loc['hand_' + side].length
        out = -1.0 if side == 'R' else 1.0
        pole = Vector(pole if pole else (0.6 * out, 0.5, -0.6))
        pole.x = abs(pole.x) * out if pole.x != 0 else 0.0
        v = Vector(target) - S
        d = max(abs(L1 - L2) + 1e-3, min(L1 + L2 - 1e-3, v.length))
        u = v.normalized()
        cos_a = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
        a = math.acos(max(-1.0, min(1.0, cos_a)))
        cos_e = (L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2)
        bend = math.pi - math.acos(max(-1.0, min(1.0, cos_e)))
        e_dir = pole - u * pole.dot(u)
        if e_dir.length < 1e-4:
            e_dir = u.orthogonal()
        e_dir.normalize()
        upper = (u * math.cos(a) + e_dir * math.sin(a)).normalized()
        b = -(e_dir - upper * e_dir.dot(upper))     # forearm bends toward local -Y
        z_axis = -upper
        y_axis = -b.normalized()
        x_axis = y_axis.cross(z_axis).normalized()
        m = Matrix((x_axis, y_axis, z_axis)).transposed()
        self.j['sh_' + side].rotation_quaternion = m.to_quaternion()
        self.j['el_' + side].rotation_quaternion = q_axis((1, 0, 0), -math.degrees(bend))

    def update_strings(self):
        if not self.strings:
            return
        bpy.context.view_layer.update()
        for fn in self.strings:
            fn(self)

    def world(self, name, local=(0, 0, 0)):
        return self.j[name].matrix_world @ Vector(local)


def tube_between(name, material, radius=0.006, seg=6):
    """A unit-length cylinder object that can be stretched between two world
    points each frame with set_tube()."""
    bm = bm_cyl(radius, radius, 1.0, seg=seg)
    ob = mesh_obj(name, bm, material, smooth=True)
    return ob


def set_tube(ob, a, b):
    a, b = Vector(a), Vector(b)
    d = b - a
    ln = max(d.length, 1e-4)
    q = d.normalized().to_track_quat('Z', 'Y')
    ob.matrix_world = Matrix.Translation(a) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((1, 1, ln, 1))


def set_oriented(ob, origin, direction, up=(0, 0, 1)):
    """Place an object (built along +Z) at `origin`, pointing along `direction`."""
    d = Vector(direction)
    if d.length < 1e-6:
        d = Vector((0, 0, 1))
    q = d.normalized().to_track_quat('Z', 'Y')
    ob.matrix_world = Matrix.Translation(Vector(origin)) @ q.to_matrix().to_4x4()


def bm_tube_path(points, radius, segr=8, side_ref=(1, 0, 0), flat=1.0, caps=True):
    """Sweep a (possibly flattened) circle along a polyline.
    radius: float or callable t->r (t in 0..1).  flat scales the cross-section
    along the side axis (derived from side_ref) -> blades, ribbons."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    bm = bmesh.new()
    rings = []
    ref = Vector(side_ref).normalized()
    for i, p in enumerate(pts):
        if i == 0:
            tdir = pts[1] - pts[0]
        elif i == n - 1:
            tdir = pts[-1] - pts[-2]
        else:
            tdir = pts[i + 1] - pts[i - 1]
        tdir.normalize()
        side = ref - tdir * ref.dot(tdir)
        if side.length < 1e-4:
            side = tdir.orthogonal()
        side.normalize()
        other = tdir.cross(side).normalized()
        t = i / (n - 1)
        r = radius(t) if callable(radius) else radius
        ring = []
        for j in range(segr):
            a = TAU * j / segr
            off = side * (math.cos(a) * r * flat) + other * (math.sin(a) * r)
            ring.append(bm.verts.new(p + off))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for j in range(segr):
            bm.faces.new((a[j], a[(j + 1) % segr], b[(j + 1) % segr], b[j]))
    if caps:
        for ring, p, flip in ((rings[0], pts[0], True), (rings[-1], pts[-1], False)):
            c = bm.verts.new(p)
            for j in range(segr):
                f = (ring[j], ring[(j + 1) % segr], c)
                bm.faces.new(f[::-1] if flip else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def arc_points(center, radius, a0, a1, n=16, plane='YZ'):
    """Points on a circular arc in a coordinate plane."""
    cx, cy, cz = center
    out = []
    for k in range(n):
        a = a0 + (a1 - a0) * k / (n - 1)
        c, s = math.cos(a) * radius, math.sin(a) * radius
        if plane == 'YZ':
            out.append((cx, cy + c, cz + s))
        elif plane == 'XZ':
            out.append((cx + c, cy, cz + s))
        else:
            out.append((cx + c, cy + s, cz))
    return out
