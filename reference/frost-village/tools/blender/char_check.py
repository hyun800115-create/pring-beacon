"""
char_check.py - verify assets/characters against CONTRACT section 3.

    python3 tools/blender/char_check.py        (exit code 1 on any error)

Checks: every frame name the manifest implies ({anim}_{dir}_{i} for all dirs,
anims and frames) exists in its atlas JSON; sourceSize == frameSize; atlas PNG
size matches its JSON meta; trimmed frames are not clipped at the 128x128 frame
edge; mirror targets are rendered dirs; impactFrame within range; carryPoint
for all dirs of carrying characters; portrait sprites/images exist; payload
budget (<= 8 MB).
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(GAME, 'assets')
CHAR = os.path.join(ASSETS, 'characters')

EXPECTED = {
    'player': ['idle', 'walk', 'carry_idle', 'carry_walk', 'chop', 'mine', 'harvest'],
    'fisherman': ['idle', 'walk', 'carry_idle', 'carry_walk', 'work'],
    'lumberjack': ['idle', 'walk', 'carry_idle', 'carry_walk', 'work'],
    'farmer': ['idle', 'walk', 'carry_idle', 'carry_walk', 'work'],
    'miner': ['idle', 'walk', 'carry_idle', 'carry_walk', 'work'],
    'hunter': ['idle', 'walk', 'carry_idle', 'carry_walk', 'work'],
    'villager_a': ['idle', 'walk', 'carry_walk', 'happy'],
    'villager_b': ['idle', 'walk', 'carry_walk', 'happy'],
    'villager_c': ['idle', 'walk', 'carry_walk', 'happy'],
    'deer': ['idle', 'walk'],
    'boar': ['idle', 'walk'],
}
FRAMES = {'idle': 4, 'walk': 8, 'carry_idle': 4, 'carry_walk': 8, 'chop': 8, 'mine': 8, 'harvest': 6,
          'work': 8, 'happy': 6}


def main():
    errors, warns = [], []
    with open(os.path.join(CHAR, 'manifest.json'), encoding='utf-8') as f:
        man = json.load(f)
    atlases = {a['key']: a for a in man.get('atlases', [])}
    images = {i['key']: i for i in man.get('images', [])}
    chars = man.get('characters', {})
    for key, anims in EXPECTED.items():
        if key not in chars:
            errors.append(f'{key}: missing from manifest.characters')
            continue
        c = chars[key]
        for a in anims:
            if a not in c['anims']:
                errors.append(f'{key}: anim {a} missing')
            elif c['anims'][a]['frames'] != FRAMES[a]:
                errors.append(f'{key}.{a}: {c["anims"][a]["frames"]} frames, contract says {FRAMES[a]}')
    n_frames = 0
    for key, c in chars.items():
        a = atlases.get(c['atlas'])
        if not a:
            errors.append(f'{key}: atlas {c["atlas"]} not in atlases[]')
            continue
        png, js = os.path.join(ASSETS, a['png']), os.path.join(ASSETS, a['json'])
        if not (os.path.exists(png) and os.path.exists(js)):
            errors.append(f'{key}: atlas files missing ({a["png"]}, {a["json"]})')
            continue
        with open(js) as f:
            atlas = json.load(f)
        frames = atlas['frames']
        w, h = Image.open(png).size
        ms = atlas['meta']['size']
        if (w, h) != (ms['w'], ms['h']):
            errors.append(f'{key}: png {w}x{h} != json meta {ms}')
        if atlas['meta'].get('image') != os.path.basename(png):
            errors.append(f'{key}: json meta.image {atlas["meta"].get("image")} != {os.path.basename(png)}')
        fw, fh = c['frameSize']
        for d in c['mirror'].values():
            if d not in c['dirs']:
                errors.append(f'{key}: mirror target {d} not rendered')
        for anim, info in c['anims'].items():
            if 'impactFrame' in info and not (0 <= info['impactFrame'] < info['frames']):
                errors.append(f'{key}.{anim}: impactFrame out of range')
            for d in c['dirs']:
                for i in range(info['frames']):
                    name = c['frameName'].format(anim=anim, dir=d, i=i)
                    fr = frames.get(name)
                    n_frames += 1
                    if fr is None:
                        errors.append(f'{key}: frame {name} missing in atlas')
                        continue
                    if (fr['sourceSize']['w'], fr['sourceSize']['h']) != (fw, fh):
                        errors.append(f'{key}: {name} sourceSize != frameSize')
                    ss, f2 = fr['spriteSourceSize'], fr['frame']
                    if f2['x'] + f2['w'] > w or f2['y'] + f2['h'] > h:
                        errors.append(f'{key}: {name} outside the sheet')
                    if ss['x'] <= 0 or ss['y'] <= 0 or ss['x'] + ss['w'] >= fw or ss['y'] + ss['h'] >= fh:
                        warns.append(f'{key}: {name} touches the frame edge (possible clipping) {ss}')
        if 'carry_idle' in c['anims'] or 'carry_walk' in c['anims']:
            cp = c.get('carryPoint', {})
            for d in c['dirs']:
                if d not in cp or len(cp[d]) != 3:
                    errors.append(f'{key}: carryPoint[{d}] missing')
        if 'portrait' in c:
            sp = man.get('sprites', {}).get(c['portrait'])
            if not sp or sp.get('image') not in images:
                errors.append(f'{key}: portrait sprite {c["portrait"]} missing')
    for k, sp in man.get('sprites', {}).items():
        if 'atlas' in sp:
            a = atlases.get(sp['atlas'])
            if not a:
                errors.append(f'sprite {k}: atlas {sp["atlas"]} missing')
                continue
            with open(os.path.join(ASSETS, a['json'])) as f:
                if sp['frame'] not in json.load(f)['frames']:
                    errors.append(f'sprite {k}: frame {sp["frame"]} missing in {sp["atlas"]}')
        elif sp.get('image') not in images:
            errors.append(f'sprite {k}: image {sp.get("image")} missing')
    for k, im in images.items():
        if not os.path.exists(os.path.join(ASSETS, im['png'])):
            errors.append(f'image {k}: file {im["png"]} missing')
    for k in ('portrait_player_512',):
        if k not in images:
            errors.append(f'{k} missing from images')
    total = sum(os.path.getsize(os.path.join(CHAR, f)) for f in os.listdir(CHAR))
    if total > 8 * 1024 * 1024:
        errors.append(f'payload {total / 1048576:.2f} MB > 8 MB budget')
    for wmsg in warns[:20]:
        print('WARN ', wmsg)
    if len(warns) > 20:
        print(f'WARN  ... {len(warns) - 20} more')
    for e in errors:
        print('ERROR', e)
    print(f'checked {len(chars)} characters, {n_frames} frame names, payload {total / 1048576:.2f} MB: '
          f'{len(errors)} errors, {len(warns)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
