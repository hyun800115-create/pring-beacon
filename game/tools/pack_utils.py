"""
Shared image helpers (Pillow + numpy) used by every asset pipeline.

  clean_alpha(img)            remove the faint alpha haze a Cycles shadow catcher leaves
  pack_atlas(frames, ...)     trim + shelf-pack frames into one sheet, Phaser "JSON Hash" atlas
  save_atlas(...)             write sheet PNG + atlas JSON
  contact_sheet(...)          preview grid for docs/previews

Atlas JSON format = Phaser 3 JSON Hash (TexturePacker compatible), with trimming:
  frames[name] = {frame:{x,y,w,h}, rotated:false, trimmed:true|false,
                  spriteSourceSize:{x,y,w,h}, sourceSize:{w,h}}
Phaser keeps the untrimmed sourceSize for origin maths, so a sprite's anchor
(e.g. 0.5, 0.8125) still refers to the original full frame.
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw


def clean_alpha(img, floor=10):
    """Zero alpha below `floor` and rescale the rest (kills shadow-catcher haze)."""
    a = np.asarray(img.convert('RGBA')).copy()
    alpha = a[..., 3].astype(np.float32)
    alpha = np.clip((alpha - floor) * 255.0 / (255.0 - floor), 0, 255)
    a[..., 3] = alpha.astype(np.uint8)
    a[a[..., 3] == 0] = 0
    return Image.fromarray(a, 'RGBA')


def _trim_box(img, pad=1):
    bbox = img.getchannel('A').getbbox()
    if bbox is None:
        return (0, 0, 1, 1)
    x0, y0, x1, y1 = bbox
    return (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))


def pack_atlas(frames, max_width=2048, trim=True, padding=2):
    """frames: list of (name, PIL.Image RGBA).  Returns (sheet, atlas_dict)."""
    items = []
    for name, im in frames:
        im = im.convert('RGBA')
        box = _trim_box(im) if trim else (0, 0, im.width, im.height)
        crop = im.crop(box)
        items.append((name, im.size, box, crop))
    # Shelf pack, tallest first.
    order = sorted(range(len(items)), key=lambda i: (-items[i][3].height, -items[i][3].width))
    placements = {}
    x = y = shelf_h = 0
    used_w = 0
    for i in order:
        w, h = items[i][3].size
        if x + w > max_width:
            x = 0
            y += shelf_h + padding
            shelf_h = 0
        placements[i] = (x, y)
        x += w + padding
        used_w = max(used_w, x)
        shelf_h = max(shelf_h, h)
    total_h = y + shelf_h
    sheet_w = _pow2ish(used_w)
    sheet_h = _pow2ish(total_h)
    sheet = Image.new('RGBA', (sheet_w, sheet_h), (0, 0, 0, 0))
    atlas_frames = {}
    for i, (name, (sw, sh), box, crop) in enumerate(items):
        px, py = placements[i]
        sheet.paste(crop, (px, py))
        atlas_frames[name] = {
            'frame': {'x': px, 'y': py, 'w': crop.width, 'h': crop.height},
            'rotated': False,
            'trimmed': (crop.width, crop.height) != (sw, sh),
            'spriteSourceSize': {'x': box[0], 'y': box[1], 'w': crop.width, 'h': crop.height},
            'sourceSize': {'w': sw, 'h': sh},
        }
    atlas = {'frames': atlas_frames,
             'meta': {'app': 'frost-village/tools/pack_utils.py', 'version': '1.0',
                      'image': '', 'format': 'RGBA8888',
                      'size': {'w': sheet_w, 'h': sheet_h}, 'scale': '1'}}
    if sheet_w > 4096 or sheet_h > 4096:
        raise ValueError(f'atlas too large ({sheet_w}x{sheet_h}); split it')
    return sheet, atlas


def _pow2ish(v):
    """Round up to a multiple of 4 (keeps GPU uploads happy without pow2 waste)."""
    return max(4, (int(v) + 3) // 4 * 4)


def save_atlas(sheet, atlas, png_path, json_path, quantize=False):
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    atlas['meta']['image'] = os.path.basename(png_path)
    if quantize:
        # 256-colour palette with alpha: ~3-4x smaller, fine for soft 3D renders.
        q = sheet.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        q.save(png_path, optimize=True)
    else:
        sheet.save(png_path, optimize=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(atlas, f, separators=(',', ':'))
    return png_path


def contact_sheet(images, cols, out_path, cell=None, bg=(150, 168, 190, 255), labels=None):
    """Grid preview (light blue-grey ground so white snow gear stays visible)."""
    if not images:
        return None
    cw = cell[0] if cell else max(im.width for im in images)
    ch = cell[1] if cell else max(im.height for im in images)
    rows = (len(images) + cols - 1) // cols
    label_h = 14 if labels else 0
    sheet = Image.new('RGBA', (cols * cw, rows * (ch + label_h)), bg)
    draw = ImageDraw.Draw(sheet)
    for i, im in enumerate(images):
        cx, cy = (i % cols) * cw, (i // cols) * (ch + label_h)
        sheet.alpha_composite(im.convert('RGBA'), (cx + (cw - im.width) // 2, cy + (ch - im.height) // 2))
        if labels:
            draw.text((cx + 3, cy + ch), str(labels[i])[:24], fill=(20, 24, 32, 255))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)
    return out_path
