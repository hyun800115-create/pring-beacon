"""Frost Village: shrink a BUILT copy of the assets by re-encoding big PNGs as WebP.

Used by `build_artifact.mjs --webp` (never touches frost-village/assets/ itself):
    python3 webp_assets.py <dist_dir> [quality]

For every assets/**/*.png under <dist_dir>, encode WebP (lossy colour at `quality`, default 90,
lossless alpha) and keep it only when it is clearly smaller (< 60 % of the PNG). Palette PNGs
that are already small (the character atlases) stay PNG. Then every manifest.json string that
pointed at a converted .png is rewritten to the .webp. Prints a JSON summary on the last line.
Needs Pillow with WebP support (pip install pillow).
"""
import io
import json
import os
import sys

from PIL import Image, features

KEEP_RATIO = 0.60


def main():
    dist = os.path.abspath(sys.argv[1])
    quality = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    if not features.check('webp'):
        print(json.dumps({'error': 'Pillow has no WebP support'}))
        sys.exit(1)
    assets = os.path.join(dist, 'assets')
    mapping, before, after = {}, 0, 0
    for root, _dirs, files in os.walk(assets):
        for name in sorted(files):
            if not name.lower().endswith('.png'):
                continue
            src = os.path.join(root, name)
            size = os.path.getsize(src)
            im = Image.open(src)
            im.load()
            rgba = im.convert('RGBA')
            buf = io.BytesIO()
            rgba.save(buf, 'WEBP', quality=quality, alpha_quality=100, method=5)
            if buf.tell() < size * KEEP_RATIO:
                dst = src[:-4] + '.webp'
                with open(dst, 'wb') as f:
                    f.write(buf.getvalue())
                os.remove(src)
                rel = os.path.relpath(src, assets).replace(os.sep, '/')
                mapping[rel] = rel[:-4] + '.webp'
                before += size
                after += buf.tell()
    # rewrite manifests (paths in manifests are relative to assets/)
    def fix(v):
        if isinstance(v, str):
            return mapping.get(v, v)
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        return v
    for frag in os.listdir(assets):
        mp = os.path.join(assets, frag, 'manifest.json')
        if os.path.isfile(mp):
            with open(mp, encoding='utf-8') as f:
                j = json.load(f)
            with open(mp, 'w', encoding='utf-8') as f:
                json.dump(fix(j), f, ensure_ascii=False, indent=1)
    print(json.dumps({'converted': len(mapping), 'png_bytes': before, 'webp_bytes': after, 'files': sorted(mapping)}))


if __name__ == '__main__':
    main()
