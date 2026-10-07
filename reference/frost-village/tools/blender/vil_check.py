"""
vil_check.py - verify assets/villagers against CONTRACT_VILLAGERS section A.

    python3 tools/blender/vil_check.py        (exit code 1 on any error)

Checks: all 20 keys present; every anim the contract table requires for that
key exists with the right frames/fps/repeat/dirs; every frame name the manifest
implies ({anim}_{dir}_{i} for each anim's own dirs) exists in its atlas JSON;
sourceSize == frameSize; atlas PNG size == JSON meta; frames inside the sheet;
no trimmed frame touches the 128x128 edge (clipping warning); mirror targets
rendered; throw impactFrame/impactPoint; carryPoint for all 5 dirs (humans);
seatOffset on sitters; headTop/shadow/name/role/traits; portraits resolve;
payload budget (<= 10 MB).
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import vil_anim as va          # noqa: E402
import vil_build as vb         # noqa: E402

ASSETS = os.path.join(GAME, 'assets')
VIL = os.path.join(ASSETS, 'villagers')
BUDGET_MB = 10.0

# contract table (CONTRACT_VILLAGERS.md section A) - written out independently of vil_anim
L5, S3 = ['S', 'SE', 'E', 'NE', 'N'], ['S', 'SE', 'E']
TABLE = {
    'idle': (4, 6, -1, L5), 'walk': (8, 12, -1, L5), 'run': (8, 16, -1, L5), 'carry_walk': (8, 12, -1, L5),
    'happy': (6, 10, -1, S3), 'talk': (8, 10, -1, S3), 'laugh': (6, 10, -1, S3), 'wave': (6, 10, -1, S3),
    'surprised': (6, 12, 0, S3), 'angry': (6, 10, -1, S3), 'sad': (4, 6, -1, S3), 'throw': (8, 14, 0, S3),
    'hit': (6, 12, 0, S3), 'dance': (8, 10, -1, S3), 'sit': (4, 4, -1, S3), 'perform': (8, 10, -1, S3),
    'shiver': (4, 12, -1, S3),
}
PET_TABLE = {'idle': (4, 6, -1, L5), 'walk': (8, 12, -1, L5), 'run': (8, 16, -1, L5), 'sit': (4, 4, -1, S3),
             'happy': (6, 10, -1, S3), 'loaf': (4, 4, -1, S3)}
ALL_HUMAN = ['idle', 'walk', 'carry_walk', 'happy', 'talk', 'laugh', 'wave', 'surprised', 'angry', 'sad', 'hit',
             'shiver']
KIDS = ['npc_kid_boy', 'npc_kid_girl', 'npc_kid_prankster']
RUN = KIDS + ['npc_young_man', 'npc_teen_girl']
THROW = RUN
DANCE = KIDS + ['npc_teen_girl', 'npc_young_man', 'npc_aunt', 'npc_fashion', 'npc_uncle', 'npc_blacksmith']
SIT = ['npc_grandma', 'npc_grandpa', 'npc_herbalist', 'npc_aunt', 'npc_bard']


def expected(key):
    if key.startswith('pet_'):
        out = ['idle', 'walk', 'run', 'sit', 'happy'] + (['loaf'] if key == 'pet_cat' else [])
        return {a: PET_TABLE[a] for a in out}
    out = list(ALL_HUMAN)
    out += ['run'] if key in RUN else []
    out += ['throw'] if key in THROW else []
    out += ['dance'] if key in DANCE else []
    out += ['sit'] if key in SIT else []
    out += ['perform'] if key == 'npc_bard' else []
    return {a: TABLE[a] for a in out}


def main():
    errors, warns = [], []
    with open(os.path.join(VIL, 'manifest.json'), encoding='utf-8') as f:
        man = json.load(f)
    atlases = {a['key']: a for a in man.get('atlases', [])}
    images = {i['key']: i for i in man.get('images', [])}
    chars = man.get('characters', {})
    n_frames = 0
    for key in vb.ALL_KEYS:
        if key not in chars:
            errors.append(f'{key}: missing from manifest.characters')
            continue
        c = chars[key]
        for f in ('name', 'role', 'traits', 'kind', 'headTop', 'shadow', 'portrait'):
            if f not in c:
                errors.append(f'{key}: field {f} missing')
        exp = expected(key)
        for a, (fr, fps, rep, dirs) in exp.items():
            info = c['anims'].get(a)
            if not info:
                errors.append(f'{key}: anim {a} missing')
                continue
            if (info['frames'], info['fps'], info['repeat'], info['dirs']) != (fr, fps, rep, dirs):
                errors.append(f'{key}.{a}: {info["frames"]}f/{info["fps"]}fps/rep{info["repeat"]}/{info["dirs"]} '
                              f'!= contract {fr}/{fps}/{rep}/{dirs}')
        for a in c['anims']:
            if a not in exp:
                warns.append(f'{key}: extra anim {a} (not in the contract table)')
        a = atlases.get(c['atlas'])
        if not a:
            errors.append(f'{key}: atlas {c["atlas"]} not in atlases[]')
            continue
        png, js = os.path.join(ASSETS, a['png']), os.path.join(ASSETS, a['json'])
        if not (os.path.exists(png) and os.path.exists(js)):
            errors.append(f'{key}: atlas files missing')
            continue
        with open(js) as f:
            atlas = json.load(f)
        frames = atlas['frames']
        w, h = Image.open(png).size
        if (w, h) != (atlas['meta']['size']['w'], atlas['meta']['size']['h']):
            errors.append(f'{key}: png size != json meta size')
        if atlas['meta'].get('image') != os.path.basename(png):
            errors.append(f'{key}: json meta.image mismatch')
        if w > 4096 or h > 4096:
            errors.append(f'{key}: atlas {w}x{h} exceeds 4096')
        fw, fh = c['frameSize']
        for d in c['mirror'].values():
            if d not in c['dirs']:
                errors.append(f'{key}: mirror target {d} not rendered')
        for anim, info in c['anims'].items():
            for d in info['dirs']:
                if d not in c['dirs']:
                    errors.append(f'{key}.{anim}: dir {d} not in dirs')
                for i in range(info['frames']):
                    name = c['frameName'].format(anim=anim, dir=d, i=i)
                    n_frames += 1
                    fr = frames.get(name)
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
            if anim == 'throw':
                if info.get('impactFrame') is None or not (0 <= info['impactFrame'] < info['frames']):
                    errors.append(f'{key}.throw: impactFrame missing/out of range')
                ip = info.get('impactPoint', {})
                for d in info['dirs']:
                    if d not in ip or len(ip[d]) != 2:
                        errors.append(f'{key}.throw: impactPoint[{d}] missing')
        if c['kind'] == 'villager':
            cp = c.get('carryPoint', {})
            for d in c['dirs']:
                if d not in cp or len(cp[d]) != 3:
                    errors.append(f'{key}: carryPoint[{d}] missing')
        if 'sit' in c['anims'] and c['kind'] == 'villager' and 'seatOffset' not in c:
            errors.append(f'{key}: sit without seatOffset')
        sp = man.get('sprites', {}).get(c.get('portrait'))
        if not sp or sp.get('image') not in images:
            errors.append(f'{key}: portrait sprite missing')
        else:
            ip = os.path.join(ASSETS, images[sp['image']]['png'])
            if not os.path.exists(ip) or Image.open(ip).size != (128, 128):
                errors.append(f'{key}: portrait image missing or not 128x128')
    total = sum(os.path.getsize(os.path.join(VIL, f)) for f in os.listdir(VIL))
    if total > BUDGET_MB * 1048576:
        errors.append(f'payload {total / 1048576:.2f} MB > {BUDGET_MB} MB budget')
    for wmsg in warns[:25]:
        print('WARN ', wmsg)
    if len(warns) > 25:
        print(f'WARN  ... {len(warns) - 25} more')
    for e in errors[:80]:
        print('ERROR', e)
    print(f'checked {len(chars)} keys, {n_frames} frame names, payload {total / 1048576:.2f} MB: '
          f'{len(errors)} errors, {len(warns)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
