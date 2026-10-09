"""
b3d_seasons.py - 계절 모습 팀: 계절 나무·덤불·꽃·낙엽 더미·눈 없는 바위(GLB)와 계절 땅 그림(PNG)을 만든다.

    (game/ 에서)  ../.cache/venv/Scripts/python.exe tools/blender/b3d_seasons.py -- [키 ...]     모델 (없으면 전부)
                  ../.cache/venv/Scripts/python.exe tools/blender/b3d_seasons.py -- --ground      땅 그림만
                  ../.cache/venv/Scripts/python.exe tools/blender/b3d_seasons.py -- --list        키 목록

모델은 서리마을 소품 도구(prop_lib / prop_assets 의 도우미)로 같은 장난감 느낌으로 만들고,
export_props_glb.py 의 내보내기 순서(재질별 합치기 → 단순화 → 색 굽기 → GLB)를 그대로 불러 쓴다(그 파일은 고치지 않음).
출력: assets3d/props/season_<이름>.glb, assets3d/props/season_index.json (삼각형 수·크기)
      assets/ground/ground_grass_spring.png, ground_grass_summer.png, ground_autumn.png (512px, 이음매 없이 반복)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'fx'))


def script_args():
    argv = sys.argv
    return argv[argv.index('--') + 1:] if '--' in argv else []


# =========================================================================== 땅 그림 (numpy + Pillow)
def ground_textures():
    import numpy as np
    import fxlib as F
    from fxlib import hexc
    import gen_ground as G

    N = 512
    ss = 2
    M = N * ss
    out_dir = os.path.join(GAME, 'assets', 'ground')

    def lerp(rgb, col, t):
        return G.lerp3(rgb, hexc(col) if isinstance(col, str) else col, np.clip(t, 0, 1))

    def stamp(rng, n, kernel_fn):
        """주기적(이음매 없는) 도장 찍기: 무작위 점 n 개 * 모양 → 덮임 정도 0~1"""
        imp = np.zeros((M, M), np.float32)
        pts = rng.integers(0, M, (n, 2))
        imp[pts[:, 1], pts[:, 0]] = 1.0
        return np.clip(G.periodic_conv(imp, G.centred_kernel(M, kernel_fn)), 0, 1)

    def blade_kernel(ang, length, width):
        ca, sa = math.cos(ang), math.sin(ang)

        def k(dx, dy):
            along = dx * ca + dy * sa
            across = dx * sa - dy * ca
            taper = np.clip(1.0 - np.abs(along) / (length * ss), 0, 1)
            return np.exp(-(across ** 2) / (width * ss * ss) / np.maximum(taper, 0.05)) * (np.abs(along) < length * ss) * taper
        return k

    def leaf_kernel(ang, length, width):
        ca, sa = math.cos(ang), math.sin(ang)

        def k(dx, dy):
            u = (dx * ca + dy * sa) / (length * ss)
            v = (dx * sa - dy * ca) / (width * ss)
            d = u * u + v * v * np.clip(1.0 + 0.6 * u, 0.4, 2.0)     # 한쪽이 뾰족한 잎
            return np.clip((1.0 - d) * 3.0, 0, 1) * (np.abs(u) < 1.0)
        return k

    def disc(r):
        return lambda dx, dy: np.clip((r * ss - np.sqrt(dx * dx + dy * dy)) * 1.2 + 0.5, 0, 1)

    def grass_base(seed, c_mid, c_dark, c_light, c_dry, dry_amt, blade_cols):
        rng = np.random.default_rng(seed)
        n1 = F.fft_noise(M, M, seed + 1, scale=46 * ss)
        n2 = F.fft_noise(M, M, seed + 2, scale=12 * ss)
        n3 = F.fft_noise(M, M, seed + 3, scale=3 * ss)
        rgb = np.broadcast_to(hexc(c_mid), (M, M, 3)).copy()
        rgb = lerp(rgb, c_dark, -n1 * 0.55)
        rgb = lerp(rgb, c_light, n1 * 0.5)
        rgb = lerp(rgb, c_dry, np.clip(n2 * 0.7 - 0.35, 0, 1) * dry_amt)
        h = n1 * 1.6 + n2 * 0.9 + n3 * 0.35
        lit = G.relief(h, ss, 1.4)
        rgb = lerp(rgb, c_light, np.clip(lit, 0, 1) * 0.45)
        rgb = lerp(rgb, c_dark, np.clip(-lit, 0, 1) * 0.45)
        # 풀잎 결: 짧은 획 여러 방향 (밝은 잎끝, 어두운 그늘)
        for j in range(8):
            ang = rng.uniform(0, math.pi)
            ang = -math.pi / 2 + (ang - math.pi / 2) * 0.55          # 대체로 위아래로 선 잎
            cov = stamp(rng, 900, blade_kernel(ang, rng.uniform(3.0, 5.0), 0.35))
            col = blade_cols[j % len(blade_cols)]
            rgb = lerp(rgb, col, cov * 0.55)
        return rgb, rng

    def save(rgb, key):
        img = F.to_rgb_image(G.finish(rgb, ss))
        path = os.path.join(out_dir, key + '.png')
        F.save_png(img, path, quant=256, dither=0.75)
        # 이음매 검사: 반대쪽 가장자리끼리의 차이가 안쪽 이웃 차이와 비슷해야 한다
        a = np.asarray(img.convert('RGB'), np.float32)
        seam = (np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()) / 2
        inner = (np.abs(a[:, 1:] - a[:, :-1]).mean() + np.abs(a[1:] - a[:-1]).mean()) / 2
        print(f'[{key}] mean {a.mean(axis=(0, 1)).round(1)}  seam {seam:.2f} vs inner {inner:.2f}', flush=True)
        return path

    # ---------------------------------------------------------------- 봄: 새 풀 + 녹는 눈 조각
    rgb, rng = grass_base(500, '#86B95E', '#5E9446', '#A9CF78', '#A39A63', 0.35,
                          ['#B6DA86', '#5B8E43', '#9CCB6E', '#6E9E4C'])
    # 녹는 눈 조각: 낮은 주파수 노이즈의 꼭대기만 (적게), 가장자리는 들쭉날쭉
    sn = F.fft_noise(M, M, 511, scale=40 * ss)
    sn2 = F.fft_noise(M, M, 512, scale=5 * ss)
    field = sn + sn2 * 0.25
    thr = np.quantile(field, 0.985)
    cov = np.clip((field - thr) * 2.6, 0, 1)
    wet = np.clip((field - (thr - 0.5)) * 1.3, 0, 1) * (1 - cov)
    rgb = lerp(rgb, '#6E8048', wet * 0.5)                                    # 젖은 땅 테두리
    rgb = lerp(rgb, '#8E7A5A', np.clip(wet - 0.6, 0, 1) * 0.7)               # 녹은 물에 드러난 흙
    hgt = cov * 4.0 + sn2 * cov * 1.2
    lit = G.relief(hgt, ss, 0.8)
    snow = np.broadcast_to(hexc('#E4EBF2'), (M, M, 3)).copy()               # 녹는 눈: 살짝 회색빛
    snow = lerp(snow, '#BCCAD8', np.clip(-lit, 0, 1) * 0.7)
    snow = lerp(snow, '#F8FAFC', np.clip(lit, 0, 1) * 0.6)
    rgb = G.lerp3(rgb, snow, np.clip(cov, 0, 1) * 0.92)
    # 아주 작은 들꽃 몇 송이 (흰색·노랑)
    for col, n in (('#FFFFFF', 40), ('#FFE27A', 28)):
        c = stamp(rng, n, disc(1.6)) * (1 - cov)
        rgb = lerp(rgb, col, c)
    save(rgb, 'ground_grass_spring')

    # ---------------------------------------------------------------- 여름: 짙은 풀 + 작은 꽃
    rgb, rng = grass_base(600, '#6FA64B', '#4C833A', '#93C463', '#9AA758', 0.2,
                          ['#9ACB66', '#477F35', '#84BC58', '#5D9441'])
    # 큰 얼룩: 풀이 더 짙은 곳·밝은 곳
    big = F.fft_noise(M, M, 613, scale=60 * ss)
    rgb = lerp(rgb, '#5A9440', np.clip(big * 0.5, 0, 1) * 0.5)
    # 작은 꽃: 꽃잎 원 + 가운데 점
    for col, n, r in (('#FFFFFF', 70, 2.0), ('#FFD84A', 60, 1.8), ('#F59CC0', 45, 1.9), ('#B9A2F0', 30, 1.7), ('#FF8A5C', 18, 1.7)):
        imp_rng = np.random.default_rng(abs(hash(col)) % 9999)
        pts = imp_rng.integers(0, M, (n, 2))
        imp = np.zeros((M, M), np.float32)
        imp[pts[:, 1], pts[:, 0]] = 1.0
        shadow = np.clip(G.periodic_conv(np.roll(np.roll(imp, 2 * ss, 0), 1 * ss, 1), G.centred_kernel(M, disc(r + 0.6))), 0, 1)
        rgb = lerp(rgb, '#3E6E30', shadow * 0.45)
        petal = np.clip(G.periodic_conv(imp, G.centred_kernel(M, disc(r))), 0, 1)
        rgb = lerp(rgb, col, petal)
        center = np.clip(G.periodic_conv(imp, G.centred_kernel(M, disc(r * 0.42))), 0, 1)
        rgb = lerp(rgb, '#F2B53A' if col != '#FFD84A' else '#E08A2A', center * 0.9)
    save(rgb, 'ground_grass_summer')

    # ---------------------------------------------------------------- 가을: 누런 풀 + 떨어진 잎
    rgb, rng = grass_base(700, '#B0A052', '#8E8840', '#CDB868', '#C28E4E', 0.45,
                          ['#D6C274', '#837C3A', '#C4AE5C', '#9C9446'])
    big = F.fft_noise(M, M, 713, scale=55 * ss)
    rgb = lerp(rgb, '#9A9A4C', np.clip(big * 0.55, 0, 1) * 0.6)             # 아직 푸른 기 남은 곳
    rgb = lerp(rgb, '#C79A55', np.clip(-big * 0.55, 0, 1) * 0.45)           # 마른 곳
    # 떨어진 잎: 여러 색·방향, 아래에 옅은 그림자
    leaf_cols = ['#E2762E', '#D2452E', '#F0B23A', '#C9622A', '#A8452A', '#E89A2E']
    for j in range(18):
        col = leaf_cols[j % len(leaf_cols)]
        ang = rng.uniform(0, math.pi * 2)
        ln = rng.uniform(4.0, 5.8)
        pts = rng.integers(0, M, (8, 2))
        imp = np.zeros((M, M), np.float32)
        imp[pts[:, 1], pts[:, 0]] = 1.0
        kern = G.centred_kernel(M, leaf_kernel(ang, ln, ln * 0.5))
        shadow = np.clip(G.periodic_conv(np.roll(np.roll(imp, 2 * ss, 0), 2 * ss, 1), kern), 0, 1)
        rgb = lerp(rgb, '#6B5A2E', shadow * 0.4)
        cov = np.clip(G.periodic_conv(imp, kern), 0, 1)
        shade = F.fft_noise(M, M, 720 + j, scale=2 * ss)
        lc = G.lerp3(np.broadcast_to(hexc(col), (M, M, 3)), hexc('#7A3A1E'), np.clip(-shade * 0.3, 0, 0.4))
        rgb = G.lerp3(rgb, lc, cov)
        rib = np.clip(G.periodic_conv(imp, G.centred_kernel(M, blade_kernel(ang, ln * 0.8, 0.12))), 0, 1)
        rgb = lerp(rgb, '#8A3A1E', rib * cov * 0.5)
    save(rgb, 'ground_autumn')
    print('ground done ->', out_dir)


# =========================================================================== 3D 모델 (Blender bpy)
MODELS = {}


def model(key, decimate=0.7):
    def deco(fn):
        MODELS[key] = dict(fn=fn, decimate=decimate)
        return fn
    return deco


def build_models(keys):
    import bpy                         # noqa: F401
    import bl_common as bc             # noqa: F401
    import prop_lib as L
    import prop_assets as A
    import export_props_glb as E
    from mathutils import Vector
    from prop_lib import flat, snowy, tonal, blob, sphere

    def snow_m():
        return flat('snow_mat', 0.9)

    # ------------------------------------------------------------------ 재질
    def birch_bark():
        key = 'season_birch'
        if key in L._CUSTOM:
            return L._CUSTOM[key]
        nb = L.NB('birch_bark', rough=0.85)
        nz = nb.noise(7.0, 2.0)
        marks = nb.map_range(nz, 0.6, 0.66)
        tone = nb.map_range(nb.noise(2.0, 1.0), 0.3, 0.7)
        base = nb.mix_rgb(tone, L.C('#D8D0C2'), L.C('#F1ECE2'))
        nb.base(nb.mix_rgb(marks, base, L.C('#3B3632')))
        L._CUSTOM[key] = nb.m
        return nb.m

    def leafy(base, top, noise_amt=0.55, scale=3.2):
        """잎 덩어리: 옆은 짙고 위는 밝은 장난감 느낌 (snowy 의 '눈' 자리에 밝은 잎색)"""
        return snowy(base, snow=top, lo=0.25, hi=0.85, noise_amt=noise_amt, noise_scale=scale, rough=0.85)

    def blossom(base, top, spot='#FFF6F8', spot_scale=9.0, spot_lo=0.5, spot_hi=0.6):
        """꽃 덩어리: 분홍·흰 꽃잎이 얼룩덜룩 (spot_lo/hi 가 높을수록 얼룩이 적다)"""
        key = ('season_blossom', base, top, spot, spot_scale, spot_lo, spot_hi)
        if key in L._CUSTOM:
            return L._CUSTOM[key]
        nb = L.NB('blossom_' + base.lstrip('#'), rough=0.8)
        geo = nb.n('ShaderNodeNewGeometry')
        sep = nb.n('ShaderNodeSeparateXYZ')
        nb.link(geo.outputs['Normal'], sep.inputs[0])
        spots = nb.map_range(nb.noise(spot_scale, 2.0), spot_lo, spot_hi)
        up = nb.map_range(nb.math('ADD', sep.outputs['Z'], nb.math('MULTIPLY', nb.math('SUBTRACT', nb.noise(3.0, 2.0), 0.5), 0.6)), 0.1, 0.8)
        col = nb.mix_rgb(up, L.C(base), L.C(top))
        col = nb.mix_rgb(spots, col, L.C(spot))
        nb.base(col)
        L._CUSTOM[key] = nb.m
        return nb.m

    def ore_mat_plain():
        """prop_assets.ore_mat 과 같은 바위인데 꼭대기 눈만 없앤 것 (이끼 조금)"""
        key = 'ore_rock_plain'
        if key in L._CUSTOM:
            return L._CUSTOM[key]
        nb = L.NB('ore_rock_plain', rough=0.8)
        nz = nb.noise(2.6, 3.0)
        v = nb.math('ABSOLUTE', nb.math('SUBTRACT', nz, 0.5))
        vein = nb.map_range(v, 0.035, 0.012)
        tone = nb.map_range(nb.noise(1.2, 1.0), 0.3, 0.7)
        stone = nb.mix_rgb(tone, L.C('#4E5562'), L.C('#677080'))
        col = nb.mix_rgb(vein, stone, L.C('ore'))
        geo = nb.n('ShaderNodeNewGeometry')
        sep = nb.n('ShaderNodeSeparateXYZ')
        nb.link(geo.outputs['Normal'], sep.inputs[0])
        sn = nb.math('ADD', sep.outputs['Z'], nb.math('MULTIPLY', nb.math('SUBTRACT', nb.noise(3.0, 2.0), 0.5), 0.6))
        col = nb.mix_rgb(nb.map_range(sn, 0.85, 1.0), col, L.C('#6E8A4E'))
        nb.base(col)
        L._CUSTOM[key] = nb.m
        return nb.m

    # ------------------------------------------------------------------ 활엽수 (봄·여름·가을·겨울 같은 모양)
    SHAPES = {
        # 둥근 나무 (벚나무·사과나무 느낌)
        'a': dict(seed=101, trunk=(0.17, 1.35), bark='bark', lean=(0.06, 0.03),
                  canopy=[((0.0, 0.0, 2.6), 0.98), ((0.66, 0.22, 2.22), 0.68), ((-0.6, 0.36, 2.28), 0.7),
                          ((0.1, -0.64, 2.25), 0.7), ((-0.12, 0.08, 3.22), 0.62)]),
        # 키 큰 자작나무 느낌 (흰 줄기)
        'b': dict(seed=202, trunk=(0.13, 1.9), bark='birch', lean=(-0.04, 0.05),
                  canopy=[((0.0, 0.0, 2.55), 0.66), ((0.06, 0.02, 3.3), 0.6), ((0.42, 0.18, 2.85), 0.5),
                          ((-0.38, -0.24, 2.92), 0.5), ((0.02, 0.0, 3.92), 0.42)]),
    }
    PALETTE = {
        # 봄: a = 진분홍 벚꽃, b = 흰빛 도는 연분홍 꽃 + 새잎 조금
        'spring': {'a': ('blossom', '#E98AAE', '#FFD3E2'), 'b': ('blossom', '#EDC6D4', '#FFF7FA')},
        'summer': {'a': ('leafy', '#3F8A45', '#7CC160'), 'b': ('leafy', '#5E9E44', '#A4D06A')},
        'autumn': {'a': ('leafy', '#D0552A', '#F3A23A'), 'b': ('leafy', '#D99A22', '#F7D458')},
    }

    def decid(shape, season):
        S = SHAPES[shape]
        rnd = L.rng(S['seed'])
        bark = birch_bark() if S['bark'] == 'birch' else tonal('bark', 0.18, 6.0, rough=0.9)
        r0, th = S['trunk']
        top = Vector((S['lean'][0], S['lean'][1], th))
        mb = L.MB()
        # 줄기 (살짝 굽음) + 뿌리
        mid = Vector((S['lean'][0] * 0.3, S['lean'][1] * 0.3, th * 0.5))
        mb.seg((0, 0, 0), tuple(mid), r0, bark, segs=8, r2=r0 * 0.88)
        mb.seg(tuple(mid), tuple(top), r0 * 0.88, bark, segs=8, r2=r0 * 0.72)
        for i in range(4):
            a = math.radians(i * 90 + 30)
            mb.seg((0.08 * math.cos(a), 0.08 * math.sin(a), 0.16), (0.36 * math.cos(a), 0.36 * math.sin(a), 0.0),
                   r0 * 0.55, bark, segs=6, r2=r0 * 0.2)
        # 큰 가지: 줄기 끝 → 잎 덩어리 가운데 쪽
        bare = season == 'winter'
        tips = []
        for k, (c, r) in enumerate(S['canopy'][1:]):
            c = Vector(c)
            start = top + Vector((0, 0, -0.12 * k))
            end = start + (c - start) * (1.0 if bare else 0.8)
            mb.seg(tuple(start), tuple(end), r0 * 0.55, bark, segs=6, r2=r0 * 0.24)
            tips.append((end, (end - start).normalized(), r))
        # 꼭대기 가지
        c0 = Vector(S['canopy'][0][0])
        up_end = top + (c0 - top) * (1.25 if bare else 0.9)
        mb.seg(tuple(top), tuple(up_end), r0 * 0.6, bark, segs=6, r2=r0 * 0.22)
        tips.append((up_end, (up_end - top).normalized(), S['canopy'][0][1]))
        if bare:
            # 잔가지: 끝마다 4 개, 위·바깥으로 퍼지고 다시 갈라짐. 위를 보는 면에만 눈이 살짝 (snowy)
            twig = snowy('#7A5A44' if S['bark'] == 'birch' else '#6E4428', snow='snow_mat', lo=0.45, hi=0.62,
                         noise_amt=0.3, noise_scale=6.0, rough=0.9)
            for (p, d, r) in tips:
                for j in range(4):
                    side = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.1, 1.0))).normalized()
                    dd = (d * 0.5 + side * 0.7).normalized()
                    q = p + dd * rnd.uniform(0.4, 0.66) * (r / 0.7)
                    mb.seg(tuple(p), tuple(q), r0 * 0.26, twig, segs=5, r2=0.016)
                    for jj in range(2):
                        q2 = q + (dd + Vector((rnd.uniform(-0.7, 0.7), rnd.uniform(-0.7, 0.7), 0.45))).normalized() * rnd.uniform(0.2, 0.34)
                        mb.seg(tuple(q), tuple(q2), 0.017, twig, segs=4, r2=0.006)
            mb.done('branches')
            # 뿌리에 얇은 눈
            blob('basesnow', 0.42, (0.15, -0.1, 0.0), snow_m(), scale=(1.4, 1.1, 0.2), seed=S['seed'], amp=0.25,
                 subdiv=2)
            return
        mb.done('branches')
        kind, base, topc = PALETTE[season][shape]
        if kind == 'blossom':
            m = blossom(base, topc) if shape == 'a' else blossom(base, topc, '#9CCB6C', 11.0, 0.6, 0.65)
        else:
            m = leafy(base, topc)
        mats = [m]
        if season == 'autumn' and shape == 'a':
            mats.append(leafy('#B8372A', '#E8703A'))       # 붉은 덩어리 하나 섞기
        for i, (c, r) in enumerate(S['canopy']):
            mm = mats[1] if (len(mats) > 1 and i in (2,)) else mats[0]
            blob('leaf%d' % i, r, c, mm, seed=S['seed'] + i * 7, amp=0.16, freq=1.7, subdiv=3)
        # 나무 밑에 떨어진 꽃잎·잎 조각 (봄·가을)
        if season in ('spring', 'autumn'):
            cols = (['#F7B8CF', '#FFFFFF', '#F28DB2'] if shape == 'a' else ['#FFFFFF', '#F7D9E4']) if season == 'spring' \
                else (['#E07A30', '#C8402E', '#F0B23A'] if shape == 'a' else ['#EBB436', '#F2C94E', '#D98A2A'])
            fb = L.MB()
            for i in range(16):
                a = rnd.uniform(0, math.tau)
                d = rnd.uniform(0.3, 1.15)
                fb.ico(0.075, flat(cols[i % len(cols)], 0.8), loc=(d * math.cos(a), d * math.sin(a), 0.012),
                       rot=(0, 0, rnd.uniform(0, 180)), scale=(1.0, 0.6, 0.12), subdiv=1)
            fb.done('fallen')

    for shp in ('a', 'b'):
        for sea in ('spring', 'summer', 'autumn', 'winter'):
            model('season_decid_%s_%s' % (shp, sea), 0.62 if sea != 'winter' else 0.8)(
                (lambda s=shp, e=sea: decid(s, e)))

    # ------------------------------------------------------------------ 눈 없는 소나무 (봄·여름·가을)
    @model('season_pine_a', 0.32)
    def _pa():
        A.pine(seed=11, tiers=4, base_r=1.05, top_z=3.2, tier_h=1.25, first_z=0.6, snow_f=0.0, tips=9,
               light='#3F8A5C', dark='#24593F')

    @model('season_pine_b', 0.32)
    def _pb():
        A.pine(seed=23, tiers=5, base_r=0.92, top_z=3.9, tier_h=1.15, first_z=0.6, snow_f=0.0, tips=8,
               light='#4A9462', dark='#235640')

    @model('season_pine_c', 0.32)
    def _pc():
        A.pine(seed=37, tiers=4, base_r=1.1, top_z=3.3, tier_h=1.25, first_z=0.6, snow_f=0.0, tips=9,
               light='#368058', dark='#1F5039')

    # ------------------------------------------------------------------ 덤불 (bush_snow 모양, 눈 없음)
    def bush(m, dots, dot_r=0.045):
        rnd = L.rng(12)
        parts = [((0, 0, 0.38), 0.42), ((0.36, -0.12, 0.26), 0.3), ((-0.34, 0.1, 0.26), 0.3),
                 ((0.05, 0.32, 0.3), 0.3), ((-0.1, -0.3, 0.22), 0.26)]
        for i, (p, r) in enumerate(parts):
            blob('bush', r, p, m, seed=70 + i, amp=0.2, freq=2.2, subdiv=3, flat_bottom=0.6)
        for i in range(len(dots) * 4):
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.1, 0.8))).normalized()
            p = Vector((0, 0, 0.32)) + d * 0.46
            sphere('dot', dot_r, tuple(p), flat(dots[i % len(dots)], 0.4), segs=8, rings=5)

    @model('season_bush_spring', 0.3)
    def _bs():
        bush(leafy('#4C9450', '#8FCB6E'), ['#FFFFFF', '#F7B3CB', '#FFE07A'], 0.05)

    @model('season_bush_summer', 0.3)
    def _bu():
        bush(leafy('#3B8048', '#6DB35E'), ['berry'])

    @model('season_bush_autumn', 0.3)
    def _ba():
        bush(leafy('#8E3226', '#C9562E', noise_amt=0.7), ['#5E1E18', '#E0A23A'], 0.04)

    # ------------------------------------------------------------------ 꽃·풀 무더기·낙엽 더미 (덤불 자리)
    def blades(mb, rnd, n, r_spread, h, cols, r=0.035):
        for i in range(n):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0, r_spread)
            p = Vector((d * math.cos(a), d * math.sin(a), 0))
            tilt = Vector((math.cos(a) * rnd.uniform(0.1, 0.45), math.sin(a) * rnd.uniform(0.1, 0.45), 1)).normalized()
            q = p + tilt * h * rnd.uniform(0.6, 1.1)
            mb.seg(tuple(p), tuple(q), r, cols[i % len(cols)], segs=4, r2=0.004)

    def flower_tuft(seed, colors):
        rnd = L.rng(seed)
        mb = L.MB()
        greens = [flat('#4E9A48', 0.8), flat('#6DB55A', 0.8), flat('#3F8240', 0.8)]
        blades(mb, rnd, 16, 0.32, 0.36, greens)
        heads = []
        for i in range(8):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0.05, 0.36)
            p = Vector((d * math.cos(a), d * math.sin(a), 0))
            top = p + Vector((math.cos(a) * 0.06, math.sin(a) * 0.06, rnd.uniform(0.28, 0.46)))
            mb.seg(tuple(p), tuple(top), 0.012, greens[0], segs=4, r2=0.01)
            heads.append((top, colors[i % len(colors)]))
        mb.done('stems')
        for i, (p, col) in enumerate(heads):
            blob('petals', 0.085, tuple(p), flat(col, 0.6), scale=(1.0, 1.0, 0.45), seed=seed + i, amp=0.25,
                 freq=2.5, subdiv=1)
            sphere('eye', 0.035, (p.x, p.y, p.z + 0.03), flat('#F2B53A' if col != '#FFD84A' else '#E07A2A', 0.5),
                   segs=6, rings=4)
        blob('leafbase', 0.3, (0, 0, 0), flat('#4E9A48', 0.85), scale=(1.2, 1.0, 0.18), seed=seed + 40, amp=0.3,
             subdiv=1)

    @model('season_flowers_a', 0.75)
    def _fa():
        flower_tuft(301, ['#FFFFFF', '#FFD84A', '#FFFFFF', '#FFD84A', '#F7F0C8'])

    @model('season_flowers_b', 0.75)
    def _fb():
        flower_tuft(302, ['#F59CC0', '#B9A2F0', '#F59CC0', '#FFFFFF', '#E86A8E'])

    @model('season_grass', 0.85)
    def _gr():
        rnd = L.rng(401)
        mb = L.MB()
        blades(mb, rnd, 26, 0.34, 0.42, [flat('#5EA64E', 0.8), flat('#7CC060', 0.8), flat('#468A3E', 0.8),
                                           flat('#93C86A', 0.8)], r=0.03)
        mb.done('grass')

    @model('season_grass_dry', 0.85)
    def _gd():
        rnd = L.rng(402)
        mb = L.MB()
        blades(mb, rnd, 24, 0.34, 0.4, [flat('#C9B060', 0.8), flat('#A89A4C', 0.8), flat('#D9C27A', 0.8),
                                          flat('#B88E4A', 0.8)], r=0.03)
        mb.done('grass')

    @model('season_leaves', 0.85)
    def _lv():
        rnd = L.rng(501)
        cols = ['#E2762E', '#D2452E', '#F0B23A', '#C9622A']
        m = leafy('#C9622A', '#F0A23A', noise_amt=0.8, scale=6.0)
        m2 = leafy('#B8372A', '#E8703A', noise_amt=0.8, scale=6.0)
        blob('pile', 0.4, (0, 0, 0.0), m, scale=(1.3, 1.1, 0.6), seed=17, amp=0.3, freq=2.4, subdiv=3,
             flat_bottom=0.15)
        blob('pile2', 0.27, (0.42, 0.22, 0.0), m2, scale=(1.2, 1.0, 0.55), seed=18, amp=0.3, freq=2.4, subdiv=2,
             flat_bottom=0.15)
        blob('pile3', 0.22, (-0.38, -0.2, 0.0), leafy('#D99A22', '#F7D458', noise_amt=0.8, scale=6.0),
             scale=(1.2, 1.0, 0.5), seed=19, amp=0.3, freq=2.4, subdiv=2, flat_bottom=0.15)
        mb = L.MB()
        for i in range(16):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0.35, 0.85)
            z = 0.01 if d > 0.5 else rnd.uniform(0.1, 0.18)
            mb.ico(0.07, flat(cols[i % 4], 0.7), loc=(d * math.cos(a), d * math.sin(a), z),
                   rot=(rnd.uniform(-20, 20), rnd.uniform(-20, 20), rnd.uniform(0, 180)), scale=(1.0, 0.55, 0.12),
                   subdiv=1)
        mb.done('leaves')

    # ------------------------------------------------------------------ 눈 없는 그루터기·바위
    @model('season_stump', 0.3)
    def _st():
        rnd = L.rng(4)
        bark = tonal('bark', 0.18, 6.0, rough=0.9)
        L.cyl('stump', 0.34, 0.42, mat=bark, r_top=0.31, segs=20, bevel=0.035, cap_mat=L.end_grain(scale=12.0))
        mb = L.MB()
        for i in range(5):
            a = math.radians(i * 72 + rnd.uniform(-15, 15))
            mb.seg((0.24 * math.cos(a), 0.24 * math.sin(a), 0.2), (0.55 * math.cos(a), 0.55 * math.sin(a), 0.02),
                   0.11, bark, segs=10, r2=0.045)
        mb.done('roots')
        chip = flat('end_grain', 0.8)
        for i in range(6):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0.5, 0.8)
            L.box('chip', (0.1, 0.06, 0.03), (d * math.cos(a), d * math.sin(a), 0), rot=(0, 0, rnd.uniform(0, 180)),
                  mat=chip, bevel=0.01)
        blob('moss', 0.12, (-0.17, 0.16, 0.41), flat('#5E9A4A', 0.9), scale=(1.3, 0.9, 0.3), seed=2, amp=0.2,
             subdiv=1)

    def plain_rock(fn, snow):
        """바위: 원본 광석 조각은 빛나는 재질이라 색 굽기에서 빠져 바위 전체가 주황이 된다.
        여기서는 조각을 빛나지 않는 재질로 바꿔 한 장의 그림으로 굽는다 (겨울용은 눈 있는 바위)."""
        old_m, old_n = A.ore_mat, A.ore_nugget_mat
        if not snow:
            A.ore_mat = ore_mat_plain
        A.ore_nugget_mat = lambda: flat('#E8892E', 0.35)
        try:
            fn()
        finally:
            A.ore_mat, A.ore_nugget_mat = old_m, old_n

    @model('season_rock_a', 0.35)
    def _ra():
        plain_rock(A.b_rock_ore, False)

    @model('season_rock_b', 0.35)
    def _rb():
        plain_rock(A.b_rock_ore_b, False)

    @model('season_rock_a_snow', 0.35)
    def _ras():
        plain_rock(A.b_rock_ore, True)

    @model('season_rock_b_snow', 0.35)
    def _rbs():
        plain_rock(A.b_rock_ore_b, True)

    if keys == ['--list']:
        print('\n'.join(MODELS))
        return
    todo = keys or list(MODELS)
    out = E.OUT
    idx_path = os.path.join(out, 'season_index.json')
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}

    def export_small(key, fn, tex):
        """export_props_glb.export 와 같은 순서. 다만 색 그림 크기를 줄인다(나무 512, 작은 것 256):
        굽기 함수는 물체 크기로 그림 크기를 고르므로, 굽는 동안만 물체를 줄였다가 되돌린다."""
        import time
        t0 = time.time()
        bc.reset_scene()
        L._CUSTOM.clear()
        fn()
        E.clean_scene()
        E.merge_by_material()
        obs = [o for o in bpy.data.objects if o.type == 'MESH']
        ob = obs[0]
        E.decimate(ob, key)
        big = max(ob.dimensions)
        want = 0.7 if tex <= 256 else 1.9           # bake_to_texture: <0.8 → 256, <2.0 → 512
        s = min(1.0, want / max(big, 1e-3))

        def scale_apply(k):
            ob.scale = (k, k, k)
            with bpy.context.temp_override(active_object=ob, selected_editable_objects=[ob], selected_objects=[ob], object=ob):
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if s < 1.0:
            scale_apply(s)
        size = E.bake_to_texture(ob, key)
        if s < 1.0:
            scale_apply(1.0 / s)
        path = os.path.join(out, key + '.glb')
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                                  export_animations=False, export_cameras=False, export_lights=False)
        info = {'kind': 'prop', 'mats': len(ob.data.materials), 'tex': size, 'kb': os.path.getsize(path) // 1024}
        print(f'[{key}] {info["mats"]} materials, tex {size}, {info["kb"]} KB, {time.time() - t0:.1f}s', flush=True)
        return info

    import bpy
    import bl_common as bc
    for k in todo:
        if k not in MODELS:
            print('unknown', k)
            continue
        E.DECIMATE[k] = MODELS[k]['decimate']           # 내 키만 단순화 비율 지정 (원본 표는 실행 중에만 덧붙임)
        tex = 512 if ('decid' in k or 'pine' in k) else 256
        try:
            info = export_small(k, MODELS[k]['fn'], tex)
            info['tris'] = glb_tris(os.path.join(out, k + '.glb'))
            index[k] = info
            print(f'  -> {k}: {info["tris"]} tris', flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'[{k}] FAILED: {e}', flush=True)
    with open(idx_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


def glb_tris(path):
    import struct
    b = open(path, 'rb').read()
    ln = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + ln])
    t = 0
    for m in j.get('meshes', []):
        for p in m['primitives']:
            acc = j['accessors'][p['indices']] if 'indices' in p else j['accessors'][p['attributes']['POSITION']]
            t += acc['count'] // 3
    return t


if __name__ == '__main__':
    args = script_args()
    if '--ground' in args:
        ground_textures()
    else:
        build_models([a for a in args if a != '--ground'] if args != ['--list'] else ['--list'])
