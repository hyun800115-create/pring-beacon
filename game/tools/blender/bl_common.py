"""
Shared Blender setup for every Frost Village sprite.

Every sprite (characters, props, buildings, items) MUST be rendered through
this module so that camera angle, pixel scale, lighting and colour handling
match exactly across all assets.

Works in two ways:
  1) Blender as a Python module:  python render_xxx.py [-- args]
     (pip install bpy  -> this is what the build machine uses)
  2) Real Blender on your PC:      blender -b -P render_xxx.py -- [args]

Conventions (see docs/CONTRACT.md):
  * 1 Blender unit = 1 metre.  PPU = 64 screen pixels per metre (horizontal).
  * Orthographic camera, elevation 30 deg (rotation X = 60 deg), yaw 45 deg.
    -> ground squares appear as 2:1 diamonds, vertical things are x0.866.
  * Character/prop "front" faces local -Y.  yaw_for_dir('S') turns it to
    face the camera (screen-down).
  * World origin (0,0,0) is the sprite's ground anchor (feet / footprint
    centre).  setup_camera() puts the origin at an exact pixel in the frame.
  * Sun comes from screen upper-left, so shadows fall to screen lower-right.
"""
import math
import os
import sys

import bpy
from mathutils import Vector, Euler

PPU = 64                    # screen pixels per metre
CAM_ELEV_DEG = 30.0         # camera looks down 30 deg -> 2:1 diamonds
CAM_YAW_DEG = 45.0
GROUND_SQUASH = math.sin(math.radians(CAM_ELEV_DEG))      # 0.5
VERTICAL_SCALE = math.cos(math.radians(CAM_ELEV_DEG))     # 0.866

# Screen-direction -> object Z rotation (degrees), for an object whose front is -Y.
DIR_YAW = {
    'S': 45.0, 'SE': 90.0, 'E': 135.0, 'NE': 180.0,
    'N': 225.0, 'NW': 270.0, 'W': 315.0, 'SW': 0.0,
}
RENDER_DIRS = ['S', 'SE', 'E', 'NE', 'N']      # SW/W/NW are mirrored in game

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))      # frost-village/
ASSETS = os.path.join(GAME_ROOT, 'assets')


def script_args():
    """Arguments after a literal '--' (works for both bpy-module and blender -P)."""
    argv = sys.argv
    return argv[argv.index('--') + 1:] if '--' in argv else []


def yaw_for_dir(d):
    return math.radians(DIR_YAW[d])


# --------------------------------------------------------------------------- scene

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MAT_CACHE.clear()
    return bpy.context.scene


def setup_render(width, height, samples=32, denoise=True):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.max_bounces = 6
    sc.cycles.use_denoising = denoise
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.film_transparent_glass = True
    sc.render.film_transparent = True
    sc.render.resolution_x = int(width)
    sc.render.resolution_y = int(height)
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1
    sc.render.filter_size = 1.2
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 90
    # 'Standard' keeps the saturated, toy-like colours (AgX washes them out).
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.threads_mode = 'AUTO'
    return sc


def setup_camera(width, height, anchor_px, ppu=PPU, target=(0.0, 0.0, 0.0)):
    """Orthographic iso camera.  `anchor_px` = (x, y) pixel, measured from the
    frame's top-left, where world point `target` will land."""
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new('IsoCam')
    cam_data.type = 'ORTHO'
    big = max(width, height)
    cam_data.ortho_scale = big / ppu
    cam_data.clip_start = 0.1
    cam_data.clip_end = 200.0
    cam_data.sensor_fit = 'AUTO'
    # Shift (fraction of the larger side) so `target` lands on anchor_px.
    cam_data.shift_x = -(anchor_px[0] - width / 2.0) / big
    cam_data.shift_y = (anchor_px[1] - height / 2.0) / big
    cam = bpy.data.objects.new('IsoCam', cam_data)
    sc.collection.objects.link(cam)
    rot = Euler((math.radians(90.0 - CAM_ELEV_DEG), 0.0, math.radians(CAM_YAW_DEG)), 'XYZ')
    cam.rotation_euler = rot
    back = rot.to_matrix() @ Vector((0.0, 0.0, 1.0))           # camera local +Z
    cam.location = Vector(target) + back * 60.0
    sc.camera = cam
    return cam


def setup_lighting(sun_strength=3.2, ambient=(0.72, 0.80, 0.95), ambient_strength=0.85,
                   fill_strength=0.9, sun_angle_deg=6.0):
    """Key sun from screen upper-left (world -X, high), cool sky ambient,
    and a shadowless warm fill from the camera side."""
    sc = bpy.context.scene
    world = bpy.data.worlds.new('World')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*ambient, 1.0)
    bg.inputs['Strength'].default_value = ambient_strength
    sc.world = world

    def sun(name, strength, rot_deg, color, angle, cast_shadow=True):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = strength
        ld.color = color
        ld.angle = math.radians(angle)
        ld.use_shadow = cast_shadow
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = Euler([math.radians(a) for a in rot_deg], 'XYZ')
        sc.collection.objects.link(ob)
        return ob

    # Sun travels toward +X and down: elevation 50 deg, coming from -X.
    key = sun('KeySun', sun_strength, (0.0, -40.0, 0.0), (1.0, 0.96, 0.88), sun_angle_deg)
    # Fill: from the camera direction, no shadows, slightly warm.
    fill = sun('FillSun', fill_strength, (60.0, 0.0, 45.0), (1.0, 0.93, 0.85), 20.0,
               cast_shadow=False)
    try:
        fill.visible_shadow = False
    except Exception:
        pass
    return key, fill


def add_shadow_catcher(size=12.0):
    """Invisible ground that only receives shadows (for static props)."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    plane = bpy.context.object
    plane.name = 'ShadowCatcher'
    plane.is_shadow_catcher = True
    return plane


# --------------------------------------------------------------------------- materials

_MAT_CACHE = {}


def mat(name, color, rough=0.75, metal=0.0, emission=None, emission_strength=0.0,
        subsurface=0.0, alpha=1.0):
    """Cached Principled material.  `color` is sRGB 0..1 (or hex string)."""
    key = (name, tuple(color) if not isinstance(color, str) else color, rough, metal,
           emission if emission is None or isinstance(emission, str) else tuple(emission),
           emission_strength, alpha)
    if key in _MAT_CACHE:
        return _MAT_CACHE[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*srgb_to_linear(color), 1.0)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if emission is not None:
        p.inputs['Emission Color'].default_value = (*srgb_to_linear(emission), 1.0)
        p.inputs['Emission Strength'].default_value = emission_strength
    if subsurface:
        p.inputs['Subsurface Weight'].default_value = subsurface
    if alpha < 1.0:
        p.inputs['Alpha'].default_value = alpha
    _MAT_CACHE[key] = m
    return m


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_linear(c):
    if isinstance(c, str):
        c = hex_rgb(c)

    def f(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return tuple(f(v) for v in c[:3])


def assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def shade_smooth(obj, auto_angle_deg=40.0):
    """Smooth shading with sharp edges kept (Blender 4.1+ API, with fallback)."""
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(auto_angle_deg))
    except Exception:
        for p in obj.data.polygons:
            p.use_smooth = True
    finally:
        obj.select_set(False)


# --------------------------------------------------------------------------- output

def render_to(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def world_to_pixel(point, width, height, anchor_px, ppu=PPU):
    """Where a world point lands in the frame (pixel coords from top-left).
    Handy for computing attachment points (e.g. where the carried stack sits)."""
    yaw = math.radians(CAM_YAW_DEG)
    elev = math.radians(CAM_ELEV_DEG)
    x, y, z = point
    cam_x = (math.cos(yaw), math.sin(yaw), 0.0)                       # screen right
    fwd_h = (-math.sin(yaw), math.cos(yaw), 0.0)                      # into screen, on ground
    sx = x * cam_x[0] + y * cam_x[1]
    sy_ground = x * fwd_h[0] + y * fwd_h[1]
    up = sy_ground * math.sin(elev) + z * math.cos(elev)
    return (anchor_px[0] + sx * ppu, anchor_px[1] - up * ppu)
