# Review helper (read-only): per-frame body/feet centroid relative to the anchor, per character/anim/dir.
# Usage: python3 tools/test/review_visual_atlas.py [char ...]
import json, sys, os
from PIL import Image
import numpy as np
ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'characters')
man = json.load(open(os.path.join(ROOT, 'manifest.json')))
chars = sys.argv[1:] or list(man['characters'].keys())
for ck in chars:
    cd = man['characters'][ck]
    atlas = json.load(open(os.path.join(ROOT, f'char_{ck}.json')))
    img = np.array(Image.open(os.path.join(ROOT, f'char_{ck}.png')).convert('RGBA'))
    fw, fh = cd['frameSize']; ax, ay = cd['anchor'][0] * fw, cd['anchor'][1] * fh
    print(f'== {ck} anchor=({ax},{ay})')
    for an in cd['anims']:
        row = []
        for d in cd['dirs']:
            cxs, fxs, bots, tops, lefts, rights = [], [], [], [], [], []
            i = 0
            while f'{an}_{d}_{i}' in atlas['frames']:
                f = atlas['frames'][f'{an}_{d}_{i}']
                fr, ss = f['frame'], f['spriteSourceSize']
                a = img[fr['y']:fr['y'] + fr['h'], fr['x']:fr['x'] + fr['w'], 3].astype(float) / 255
                full = np.zeros((fh, fw)); full[ss['y']:ss['y'] + ss['h'], ss['x']:ss['x'] + ss['w']] = a
                ys, xs = np.nonzero(full > 0.5)
                w = full[full > 0.5]
                cxs.append((xs * w).sum() / w.sum() - ax)
                bot = ys.max(); bots.append(bot - ay); tops.append(ys.min() - ay)
                lefts.append(xs.min() - ax); rights.append(xs.max() - ax)
                feet = full[bot - 8:bot + 1]
                fy, fx = np.nonzero(feet > 0.5)
                fxs.append(fx.mean() - ax)
                i += 1
            if not cxs: continue
            row.append(f'{d}: body{np.mean(cxs):+5.1f} feet{np.mean(fxs):+5.1f} bot{np.max(bots):+4.0f} top{np.min(tops):+4.0f}')
        print(f'  {an:11s} ' + ' | '.join(row))
