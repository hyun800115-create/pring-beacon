"""
vil_lookdev.py - compose the villager expression sheet (plain python3 + Pillow).

    .cache/venv/Scripts/python.exe tools/blender/vil_render.py -- --chars npc_grandpa,npc_kid_prankster,npc_fashion --lookdev
    python3 tools/blender/vil_lookdev.py [--keys a,b,c] [--out docs/previews/vil_expressions.png]

Each column is one expression preset (vil_anim.FACES); each character gets
  row 1: head close-up (for the art review)
  row 2: the real game-scale frame (S and E, 1:1 pixels = what a phone shows)
  row 3: the same at 2x nearest-neighbour (pixel check)
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from char_pack import ink_outline  # noqa: E402
FV_CACHE = os.environ.get('FV_CACHE') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.cache', 'fv_cache'))  # 저장소/.cache/fv_cache

CACHE = FV_CACHE + '/villagers/_lookdev'
FACES = ['neutral', 'blink', 'smile', 'happy', 'laugh', 'talk_open', 'talk_mid', 'surprised', 'angry',
         'angry_shout', 'sad', 'hurt', 'sleepy', 'shiver', 'sing', 'heart', 'scheme']
LABEL = {'neutral': 'neutral', 'blink': 'blink', 'smile': 'smile', 'happy': 'happy ^^', 'laugh': 'laugh D',
         'talk_open': 'talk A', 'talk_mid': 'talk o', 'surprised': 'surprised O', 'angry': 'angry',
         'angry_shout': 'angry shout', 'sad': 'sad / tear', 'hurt': 'hurt >< snow', 'sleepy': 'sleepy',
         'shiver': 'shiver brrr', 'sing': 'sing', 'heart': 'heart eyes', 'scheme': 'scheming'}
BG = (201, 214, 232, 255)
INK = (43, 47, 58, 255)


def main():
    args = sys.argv[1:]
    keys = ['npc_kid_prankster', 'npc_kid_girl', 'npc_uncle', 'npc_grandpa', 'npc_fashion']
    out = os.path.join(GAME, 'docs', 'previews', 'vil_expressions.png')
    faces = FACES
    i = 0
    while i < len(args):
        if args[i] == '--keys':
            keys = args[i + 1].split(',')
            i += 2
        elif args[i] == '--out':
            out = args[i + 1]
            i += 2
        elif args[i] == '--faces':
            faces = args[i + 1].split(',')
            i += 2
        else:
            i += 1
    cw, zh, gh = 120, 120, 92
    rowh = zh + gh + 92 + 8
    lab = 18
    img = Image.new('RGBA', (cw * len(faces), lab + rowh * len(keys)), BG)
    d = ImageDraw.Draw(img)
    for c, fc in enumerate(faces):
        d.text((c * cw + 6, 4), LABEL.get(fc, fc), fill=INK)
    for r, key in enumerate(keys):
        y0 = lab + r * rowh
        for c, fc in enumerate(faces):
            x0 = c * cw
            zp = os.path.join(CACHE, f'{key}_{fc}_S_zoom.png')
            if not os.path.exists(zp):
                continue
            z = Image.open(zp).convert('RGBA').resize((zh, zh), Image.LANCZOS)
            img.alpha_composite(z, (x0, y0))
            for k, dd in enumerate(('S', 'E')):
                gp = os.path.join(CACHE, f'{key}_{fc}_{dd}.png')
                if not os.path.exists(gp):
                    continue
                g = ink_outline(Image.open(gp))
                crop = g.crop((34, 14, 94, 106))              # 60x92 around the body
                img.alpha_composite(crop, (x0 + k * 60, y0 + zh))
                if k == 0:
                    bb = g.getchannel('A').getbbox()
                    cx = (bb[0] + bb[2]) // 2
                    top = bb[1] + {'npc_fashion': 8, 'npc_uncle': 9}.get(key, 3)
                    head = Image.new('RGBA', (40, 46), BG)
                    head.alpha_composite(g.crop((cx - 20, top, cx + 20, top + 46)))
                    img.alpha_composite(head.resize((80, 92), Image.NEAREST), (x0 + 20, y0 + zh + gh))
        d.line([0, y0 + rowh - 4, img.width, y0 + rowh - 4], fill=(170, 186, 210, 255))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        import imagequant
        imagequant.quantize_pil_image(img, dithering_level=0.4, max_quality=100, min_quality=0,
                                      max_colors=256).save(out, optimize=True)
    except ImportError:
        img.convert('RGB').save(out, optimize=True)
    print('wrote', out, img.size)


if __name__ == '__main__':
    main()
