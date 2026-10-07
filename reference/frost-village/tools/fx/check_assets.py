"""
check_assets.py - validates the procedural FX / UI / ground assets against CONTRACT §2, §5-§7.

Re-run (from anywhere; exit code 0 = all good, 1 = errors):
    python3 frost-village/tools/fx/check_assets.py
Checks:
  * manifest.json of assets/fx, assets/ui, assets/ground parse and use paths relative to assets/
  * every key required by CONTRACT §5-§7 resolves (sprites -> atlas frame / image; spritesheets)
  * atlas JSON frames lie inside their PNG; spritesheet PNG = cols*frameWidth x rows*frameHeight
    (a single-row strip, or a grid wrapped by gen_fx.grid_strip: frames left->right, top->bottom,
    cols = min(frameCount, width // frameWidth), rows = ceil(frameCount / cols) - the order Phaser reads),
    frames are non-empty, fps / repeat / anchor / blend are sane
  * nineSlice margins fit their image
  * 512x512 ground textures are seamless (edge-wrap difference ~ interior neighbour difference)
    and shore_foam is seamless in x; decals have transparent borders (soft edges)
  * payload of fx + ui + ground <= 4 MB; unreferenced files are reported
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, 'assets')

FX_PARTICLES = ['fx_spark', 'fx_star', 'fx_glow', 'fx_smoke', 'fx_snowflake', 'fx_chip_wood', 'fx_chip_rock',
                'fx_droplet', 'fx_wheat_bit', 'fx_heart', 'fx_ring', 'fx_flame', 'fx_coin', 'fx_leaf', 'fx_dust']
FX_SHEETS = ['fx_poof', 'fx_splash', 'fx_hit', 'fx_levelup', 'fx_unlock', 'fx_fire', 'fx_smoke_puff',
             'fx_coin_spin', 'fx_sparkle']
UI_KEYS = ['ui_joystick_base', 'ui_joystick_knob', 'ui_panel', 'ui_button_blue', 'ui_button_green', 'ui_button_gray',
           'ui_icon_coin', 'ui_icon_settings', 'ui_icon_sound_on', 'ui_icon_sound_off', 'ui_icon_music_on',
           'ui_icon_music_off', 'ui_icon_lock', 'ui_icon_close', 'ui_icon_check', 'ui_icon_backpack', 'ui_icon_speed',
           'ui_icon_worker', 'ui_arrow', 'ui_bubble', 'ui_coin_bar', 'ui_badge_max', 'ui_pad_unlock', 'ui_pad_input',
           'ui_pad_output', 'ui_pad_cash', 'ui_pad_hire', 'ui_pad_upgrade', 'ui_ring_bg', 'ui_ring_fill', 'ui_title_bg']
UI_NINE = ['ui_panel', 'ui_button_blue', 'ui_button_green', 'ui_button_gray']
GROUND_TILES = ['ground_snow', 'ground_plaza', 'ground_dirt', 'ground_farm', 'ground_rock', 'water_sea', 'water_shallow']
GROUND_DECALS = ['decal_path_a', 'decal_path_b', 'decal_snow_drift_a', 'decal_snow_drift_b', 'decal_dirt_patch',
                 'decal_footprints', 'decal_puddle_ice']
GROUND_OTHER = ['shore_foam', 'fish_school']

errors, warns, notes = [], [], []


def err(m):
    errors.append(m)


def warn(m):
    warns.append(m)


def load_manifest(folder):
    p = os.path.join(ASSETS, folder, 'manifest.json')
    if not os.path.isfile(p):
        err('%s/manifest.json missing' % folder)
        return {}
    try:
        with open(p, encoding='utf-8') as f:
            m = json.load(f)
    except Exception as e:  # noqa: BLE001
        err('%s/manifest.json invalid JSON: %s' % (folder, e))
        return {}
    if m.get('version') != 1:
        warn('%s manifest version is %r (expected 1)' % (folder, m.get('version')))
    return m


def asset_path(rel, folder):
    if not isinstance(rel, str) or rel.startswith('/') or '..' in rel or '\\' in rel:
        err('bad path %r in %s manifest' % (rel, folder))
        return None
    if not rel.startswith(folder + '/'):
        warn('path %r does not live in assets/%s/' % (rel, folder))
    p = os.path.join(ASSETS, rel)
    if not os.path.isfile(p):
        err('missing file assets/%s' % rel)
        return None
    return p


def open_rgba(p):
    return np.asarray(Image.open(p).convert('RGBA'))


def open_any(p):
    im = Image.open(p)
    return im.convert('RGBA') if im.mode in ('P', 'LA', 'L', 'RGB') else im


class Frag:
    """Resolved view of one manifest fragment."""

    def __init__(self, folder):
        self.folder = folder
        self.m = load_manifest(folder)
        self.atlases, self.images, self.sheets = {}, {}, {}
        self.used = {'manifest.json'}
        for a in self.m.get('atlases', []):
            png, js = asset_path(a.get('png'), folder), asset_path(a.get('json'), folder)
            if png and js:
                self.used.update([os.path.basename(png), os.path.basename(js)])
                with open(js, encoding='utf-8') as f:
                    data = json.load(f)
                img = Image.open(png)
                frames = data.get('frames', {})
                for name, fr in frames.items():
                    r = fr.get('frame', {})
                    if r.get('x', -1) < 0 or r.get('y', -1) < 0 or r['x'] + r['w'] > img.width or r['y'] + r['h'] > img.height:
                        err('%s: frame %s outside atlas %s' % (folder, name, a['key']))
                    for k in ('sourceSize', 'spriteSourceSize'):
                        if k not in fr:
                            err('%s: frame %s lacks %s' % (folder, name, k))
                meta = data.get('meta', {}).get('size', {})
                if meta and (meta.get('w'), meta.get('h')) != img.size:
                    err('%s: atlas %s meta.size %s != png %s' % (folder, a['key'], meta, img.size))
                self.atlases[a['key']] = (png, frames, img)
        for a in self.m.get('images', []):
            p = asset_path(a.get('png'), folder)
            if p:
                self.used.add(os.path.basename(p))
                self.images[a['key']] = p
        for s in self.m.get('spritesheets', []):
            p = asset_path(s.get('png'), folder)
            if p:
                self.used.add(os.path.basename(p))
                self.sheets[s['key']] = (p, s)
        self.sprites = self.m.get('sprites', {})
        self.nine = self.m.get('nineSlice', {})

    def sprite_rgba(self, key):
        """RGBA array of the untrimmed frame of sprites[key], or None (+error)."""
        s = self.sprites.get(key)
        if s is None:
            err('%s: sprites[%s] missing' % (self.folder, key))
            return None
        anc = s.get('anchor')
        if not (isinstance(anc, list) and len(anc) == 2 and all(isinstance(v, (int, float)) for v in anc)):
            err('%s: sprites[%s].anchor invalid: %r' % (self.folder, key, anc))
        if 'atlas' in s:
            at = self.atlases.get(s['atlas'])
            if not at:
                err('%s: sprites[%s] references unknown atlas %s' % (self.folder, key, s['atlas']))
                return None
            png, frames, img = at
            fr = frames.get(s.get('frame'))
            if not fr:
                err('%s: sprites[%s] frame %s not in atlas' % (self.folder, key, s.get('frame')))
                return None
            r, ss, src = fr['frame'], fr['spriteSourceSize'], fr['sourceSize']
            crop = open_any(img.filename).crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
            full = Image.new('RGBA', (src['w'], src['h']))
            full.paste(crop, (ss['x'], ss['y']))
            return np.asarray(full)
        if 'image' in s:
            p = self.images.get(s['image'])
            if not p:
                err('%s: sprites[%s] references unknown image %s' % (self.folder, key, s['image']))
                return None
            return open_rgba(p)
        err('%s: sprites[%s] has neither atlas nor image' % (self.folder, key))
        return None

    def unreferenced(self):
        d = os.path.join(ASSETS, self.folder)
        for f in sorted(os.listdir(d)):
            if f not in self.used:
                warn('assets/%s/%s is not referenced by its manifest' % (self.folder, f))


def seam_ratio(arr, axis):
    """Wrap-around neighbour difference divided by the neighbour differences right next to the
    seam (3 column pairs on each side).  ~1 for a seamless tile, >> 1 for a visible seam.
    (Local comparison, because texture content is not stationary across the tile.)"""
    a = arr.astype(np.float32)
    if axis == 0:
        a = np.swapaxes(a, 0, 1)
    edge = np.abs(a[:, 0] - a[:, -1]).mean()
    d = np.abs(a[:, 1:] - a[:, :-1]).mean(axis=tuple(i for i in range(a.ndim) if i != 1))
    local = np.concatenate([d[:3], d[-3:]]).mean()
    return edge / max(local, 1e-3, 0.2 * d.mean())


def check_fx():
    f = Frag('fx')
    for k in FX_PARTICLES:
        a = f.sprite_rgba(k)
        if a is None:
            continue
        if a[..., 3].max() < 200:
            err('fx: %s looks empty / too transparent' % k)
        if a[0, :, 3].max() > 40 or a[-1, :, 3].max() > 40 or a[:, 0, 3].max() > 40 or a[:, -1, 3].max() > 40:
            warn('fx: %s touches its frame edge (alpha at the border)' % k)
        s = f.sprites[k]
        if s.get('kind') != 'fx':
            warn('fx: sprites[%s].kind = %r (expected fx)' % (k, s.get('kind')))
        rgb = a[..., :3][a[..., 3] > 128].astype(np.float32)
        if s.get('tintable') and rgb.size and (rgb.max(1) - rgb.min(1)).mean() > 12:
            err('fx: %s is marked tintable but is not greyscale' % k)
    for k in FX_SHEETS:
        if k not in f.sheets:
            err('fx: spritesheets[%s] missing' % k)
            continue
        p, s = f.sheets[k]
        img = Image.open(p)
        fw, fh, n = s.get('frameWidth'), s.get('frameHeight'), s.get('frameCount')
        if not (isinstance(fw, int) and isinstance(fh, int) and isinstance(n, int) and n > 0):
            err('fx: %s frame fields invalid' % k)
            continue
        # single-row strip or a grid wrapped by gen_fx.grid_strip (rows <= 2048 px); Phaser reads
        # spritesheet frames left->right, top->bottom, so both layouts load the same way
        cols = max(1, min(n, img.width // fw))
        rows = -(-n // cols)
        size_ok = img.size == (cols * fw, rows * fh)
        if not size_ok:
            err('fx: %s png is %s, expected %s (%d x %d grid of %dx%d frames)'
                % (k, img.size, (cols * fw, rows * fh), cols, rows, fw, fh))
        if img.width > 4096 or img.height > 4096:
            warn('fx: %s sheet larger than 4096 px (mobile GPU limit)' % k)

        def cell(arr, i, cols=cols, fw=fw, fh=fh):
            r, c = divmod(i, cols)
            return arr[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw]
        if not (isinstance(s.get('fps'), (int, float)) and s['fps'] > 0):
            err('fx: %s fps invalid' % k)
        if s.get('repeat') not in (-1, 0) and not isinstance(s.get('repeat'), int):
            err('fx: %s repeat invalid' % k)
        if s.get('blend') not in ('NORMAL', 'ADD', 'MULTIPLY', 'SCREEN'):
            err('fx: %s blend invalid %r' % (k, s.get('blend')))
        anc = s.get('anchor')
        if not (isinstance(anc, list) and len(anc) == 2 and all(0 <= v <= 1 for v in anc)):
            err('fx: %s anchor invalid %r' % (k, anc))
        if not size_ok:
            continue                                   # frame cells would not line up
        a = np.asarray(img.convert('RGBA'))
        empty = [i for i in range(n) if cell(a, i)[..., 3].max() < 8]
        if empty and (s.get('repeat') == -1 or len(empty) > 1 or empty[0] != n - 1):
            err('fx: %s has empty frames %s' % (k, empty))
        if s.get('repeat') == -1 and n > 2:
            # loop closure: last->first change should be like an ordinary frame step
            fr = [cell(a, i).astype(np.float32) for i in range(n)]
            steps = [np.abs(fr[i + 1] - fr[i]).mean() for i in range(n - 1)]
            wrap = np.abs(fr[0] - fr[-1]).mean()
            if wrap > 2.0 * max(np.mean(steps), 1e-3):
                warn('fx: %s loop wrap step %.2f vs mean step %.2f (possible pop)' % (k, wrap, np.mean(steps)))
    f.unreferenced()
    return f


def check_ui():
    f = Frag('ui')
    for k in UI_KEYS:
        a = f.sprite_rgba(k)
        if a is None:
            continue
        if a[..., 3].max() < 128:
            err('ui: %s looks empty' % k)
        if k.startswith('ui_pad_'):
            h, w = a.shape[:2]
            if abs(w - 2 * h) > 2:
                err('ui: %s is %dx%d, expected a 2:1 diamond frame' % (k, w, h))
        if k == 'ui_title_bg' and a.shape[:2] != (1280, 720):
            err('ui: ui_title_bg is %s, expected 720x1280' % (a.shape[:2][::-1],))
    for k in UI_NINE:
        n = f.nine.get(k)
        if not n:
            err('ui: nineSlice[%s] missing' % k)
            continue
        img_key = n.get('image', k)
        p = f.images.get(img_key)
        if not p:
            s = f.sprites.get(img_key, {})
            if 'atlas' in s:
                warn('ui: nineSlice %s uses an atlas frame (ok for Phaser NineSlice)' % k)
                continue
            err('ui: nineSlice[%s] image %s unknown' % (k, img_key))
            continue
        w, h = Image.open(p).size
        if n['left'] + n['right'] >= w or n['top'] + n['bottom'] >= h:
            err('ui: nineSlice[%s] margins do not fit %dx%d' % (k, w, h))
        # smallest heights the game code stretches them to (src/scenes/UI.js, entities/UnlockPad.js)
        min_h = {'ui_panel': 56, 'ui_button_blue': 76, 'ui_button_green': 76, 'ui_button_gray': 76}.get(k)
        if min_h and n['top'] + n['bottom'] > min_h:
            warn('ui: nineSlice[%s] top+bottom = %d > smallest in-game height %d' % (k, n['top'] + n['bottom'], min_h))
    f.unreferenced()
    return f


def check_ground():
    f = Frag('ground')
    for k in GROUND_TILES:
        a = f.sprite_rgba(k)
        if a is None:
            continue
        if a.shape[:2] != (512, 512):
            err('ground: %s is %s, expected 512x512' % (k, a.shape[:2][::-1]))
        if a[..., 3].min() < 255:
            warn('ground: %s has transparent pixels' % k)
        rx, ry = seam_ratio(a[..., :3], 1), seam_ratio(a[..., :3], 0)
        notes.append('seam %-14s x %.2f  y %.2f' % (k, rx, ry))
        if rx > 1.5 or ry > 1.5:
            err('ground: %s is not seamless (edge/inner ratio x %.2f, y %.2f)' % (k, rx, ry))
    a = f.sprite_rgba('shore_foam')
    if a is not None:
        r = seam_ratio(a.astype(np.float32), 1)
        notes.append('seam %-14s x %.2f' % ('shore_foam', r))
        if r > 1.5:
            err('ground: shore_foam is not seamless in x (%.2f)' % r)
    for k in GROUND_DECALS + ['fish_school']:
        a = f.sprite_rgba(k)
        if a is None:
            continue
        border = max(a[0, :, 3].max(), a[-1, :, 3].max(), a[:, 0, 3].max(), a[:, -1, 3].max())
        if border > 24:
            err('ground: %s is cut by its frame (border alpha %d)' % (k, border))
        if a[..., 3].max() < 100:
            err('ground: %s is (almost) empty' % k)
    fs = f.sprites.get('fish_school')
    if fs:
        w, h = fs.get('frameSize', [0, 0])
        if not (180 <= w <= 384 and 90 <= h <= 192):
            warn('ground: fish_school is %dx%d (asked ~256x128)' % (w, h))
    f.unreferenced()
    return f


def main():
    check_fx()
    check_ui()
    check_ground()
    total = 0
    for d in ('fx', 'ui', 'ground'):
        p = os.path.join(ASSETS, d)
        size = sum(os.path.getsize(os.path.join(p, x)) for x in os.listdir(p))
        notes.append('payload assets/%-7s %7.1f KB' % (d + '/', size / 1024))
        total += size
    notes.append('payload total          %7.1f KB (limit 4096 KB)' % (total / 1024))
    if total > 4 * 1024 * 1024:
        err('payload %.2f MB exceeds 4 MB' % (total / 1048576))
    for n in notes:
        print('  ' + n)
    for w in warns:
        print('WARN  ' + w)
    for e in errors:
        print('ERROR ' + e)
    print('check_assets: %d error(s), %d warning(s)' % (len(errors), len(warns)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
