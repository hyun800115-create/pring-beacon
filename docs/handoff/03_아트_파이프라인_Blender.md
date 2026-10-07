# 03. 아트 파이프라인 — Blender로 캐릭터·주민·건물·소품 만들기

> **대표님께 (이 문서는 무엇인가요?)**
>
> - 서리마을의 입체 느낌 그림(일꾼·캐릭터 11명, 주민과 펫 20마리, 건물·소품·아이템 53종, 마을 생활 소품 20종)을 만든 **"그림 공장" 설명서**예요.
> - 그림을 손으로 그리지 않았어요. 프로그램이 3D 모형을 만들고 → 언제나 **같은 카메라·같은 조명**으로 사진을 찍듯 렌더하고 → 게임용 묶음 그림으로 포장하고 → 자동으로 검사해요.
> - 카메라 각도와 크기 규칙(1미터 = 64픽셀)을 절대 바꾸지 않기 때문에, 나중에 새 그림을 추가해도 기존 그림과 크기·빛·그림자가 딱 맞아요.
> - 전부 처음부터 다시 만들어도 클라우드 컴퓨터에서 **약 1시간 10분**이면 돼요.
> - 새 세틀러식 게임에 필요한 그림(공사 단계, 길과 깃발, 짐 나르는 일꾼, 영토 경계 말뚝)도 같은 공장으로 만들 수 있고, 만드는 방법을 맨 뒤(11장)에 정리해 두었어요.

이 아래는 새 프로젝트의 Claude가 읽는 기술 문서입니다. 경로는 **게임 루트 기준**입니다.
전작 저장소에서는 게임 루트 = `frost-village/`, 이사 키트를 옮긴 새 저장소에서는 원본이
`reference/frost-village/`, 새 게임은 도구를 복사한 `game/` (README/CLAUDE.md 참고)입니다.
모든 명령은 게임 루트에서 실행한다고 가정합니다 (`cd <게임루트>`).

---

## 목차
0. 한눈에 보기 (네 개의 파이프라인)
1. 실행 환경과 검증한 명령
2. 공통 기반 `tools/blender/bl_common.py` (투영·카메라·조명·재질)
3. 포장 도구 `tools/pack_utils.py`
4. 캐릭터 파이프라인 `tools/blender/char_*.py`
5. 주민·펫 파이프라인 `tools/blender/vil_*.py`
6. 소품·건물·아이템 파이프라인 `tools/blender/prop_*.py`
7. 생활 소품 파이프라인 `tools/blender/life_*.py`
8. 운영 팁과 함정 (캐시, 재개, 시간, 하드코딩된 목록)
9. 새 프로젝트에서 재사용하는 법
10. 확장 레시피 (새 캐릭터 / 새 건물 / 새 아이템 / 새 방향 / PPU·카메라)
11. 세틀러식 게임에 새로 필요한 그림과 만드는 법
12. 명령 빠른 참조

---

## 0. 한눈에 보기

네 개의 파이프라인 모두 같은 3단계 구조입니다.

```
[빌더: 모형+포즈를 코드로 생성] --(bpy, Cycles)--> [원본 프레임 캐시 /tmp/fv_cache/<종류>/]
      --(python3 + numpy + Pillow [+ imagequant])--> [assets/<폴더>/*.png/.json + manifest.json]
      --(python3)--> [check 스크립트: 계약서와 대조, 0 오류면 통과]  + docs/previews/ 미리보기
```

- 렌더 단계만 Blender(bpy)가 필요하고, 포장(pack)·검사(check)는 일반 `python3`(numpy, Pillow)로 돕니다.
- 렌더 결과는 저장소 **밖** `/tmp/fv_cache/...`에 캐시되고, 이미 있는 프레임은 건너뜁니다(이어서 하기 가능).
- 게임은 폴더마다 있는 `manifest.json`만 보고 그림을 찾습니다(형식: `docs/CONTRACT.md` §2).

| 파이프라인 | 스크립트 | 결과 폴더 | 규모 (전작 최종) | 전체 렌더 시간 (4코어) | 검사 |
|---|---|---|---|---|---|
| 캐릭터(일꾼·손님·동물) | `char_render/build/geo/anim/animals/extras/pack/check.py` | `assets/characters/` | 11키, 1,540프레임, 3.45 MB(256색) | 약 12분 (키당 23–108초) | `char_check.py` |
| 주민·펫 | `vil_render/build/face/body/dress/pets/anim/pack/check/lookdev.py` | `assets/villagers/` | 20키, 5,374프레임, 9.77 MB(192색) | 약 40분 (키당 34–300초) + 포장 약 2분 | `vil_check.py` |
| 소품·건물·아이템 | `prop_lib/assets/render/pack/check.py` | `assets/props/` | 53스프라이트, 아틀라스 4장, 2.21 MB(RGBA) | 6–8분 (로그 352–457초) | `prop_check.py` |
| 생활 소품 | `life_assets/render/pack/check.py` | `assets/life_props/` | 빌드 16개 → 스프라이트 20개, 26프레임, 0.43 MB | 약 6분 (384초) | `life_check.py` |

전부 합치면 렌더 약 65–70분입니다. 시간 출처: `/tmp/fv_cache/render_all.log`, `vil_render_all.log`,
`props/render*.log`, `life_props/render.log`, 그리고 `docs/build_reports/*.json`의 `regenerate` 항목.

현재 검사 결과(이 문서 작성 때 직접 실행):
```
char_check : checked 11 characters, 1540 frame names, payload 3.45 MB: 0 errors, 0 warnings
vil_check  : checked 20 keys, 5374 frame names, payload 9.77 MB: 0 errors, 0 warnings
prop_check : props manifest: 53 sprites (53 required, 0 extra), 4 atlases, payload 2.21 MB  OK
life_check : life_props manifest: 20 sprites, 1 atlas(es), payload 0.43 MB  OK
```

> 주의(작성 시점 기준): 게임 코드 `src/core/Assets.js`의 `FRAGMENTS`는
> `['characters', 'props', 'fx', 'ui', 'ground', 'audio']` 6개뿐이라, `villagers`·`life_props`·`emotes`
> 그림은 **만들어져 있지만 전작 게임에는 아직 로드되지 않습니다.** 새 게임에서 쓰려면 FRAGMENTS에
> 추가해야 합니다(05번 문서 참고). 이 세 폴더는 제작 에이전트가 임시 Phaser 페이지로만 확인했습니다.

---

## 1. 실행 환경과 검증한 명령

설치는 `02_도구와_환경.md`에 자세히 있습니다. 파이프라인에 필요한 것만 요약합니다.

- **bpy 5.2.2** (Blender를 파이썬 모듈로): `/tmp/bvenv` 가상환경. 휠 메타데이터 `Requires-Python: ==3.13.*`
  → 반드시 Python 3.13으로 venv를 만들어야 합니다. 전작 컨테이너: Python 3.13.16, numpy 2.5.3, Pillow 12.3.0.
- 렌더 엔진은 **Cycles CPU + OpenImageDenoise만** 씁니다. EEVEE/Workbench는 헤드리스 컨테이너에서 안 됩니다.
  실행 때 나오는 `CUEW initialization failed` 경고는 GPU(CUDA)가 없다는 뜻이라 무시해도 됩니다.
- 포장: 시스템 `python3` + numpy + Pillow + **imagequant**(`pip install imagequant`, 전작 1.1.5).
  imagequant가 없으면 `char_pack`은 RGBA로 저장해서 용량이 약 3배(캐릭터 약 10 MB)가 됩니다.
- 대표님 PC에서: `blender -b -P tools/blender/<script>.py -- [인자]`. 모든 렌더 스크립트는
  `bl_common.script_args()`로 `--` 뒤의 인자만 읽으므로 두 방식이 같은 인자를 받습니다.
  재질 소켓 이름(`Emission Color`, `Subsurface Weight`)과 `shade_auto_smooth` 때문에 **Blender 4.2 이상**이 필요하고,
  같은 결과를 원하면 5.2를 권장합니다. (이 컨테이너에는 `blender` 실행 파일이 없어 PC 방식은 직접 돌려보지 못했습니다.)
  PC에서는 캐시 경로를 `--cache`로 명시하는 것이 안전합니다(`/tmp/...`가 윈도에서는 `C:\tmp\...`가 됨).

**이 문서를 쓰면서 실제로 돌려 본 명령** (출력은 저장소 밖 스크래치 폴더로):
```bash
/tmp/bvenv/bin/python tools/blender/prop_render.py -- --list          # 53개 키·종류·아틀라스 목록 (1.4초)
/tmp/bvenv/bin/python tools/blender/life_render.py -- --list          # 16개 빌드 + bench_seats(가짜 키)
/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars deer --meta-only --cache <스크래치>
/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars player --anims idle --dirs S,E --frames 0 --samples 24 --cache <스크래치>
#   -> 2프레임 렌더 2초 (프레임당 약 0.5초, 128x128 RGBA, 장면 준비 약 1.4초 별도)
/tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars npc_grandpa --meta-only --cache <스크래치>
python3 tools/blender/char_check.py ; python3 tools/blender/vil_check.py
python3 tools/blender/prop_check.py ; python3 tools/blender/life_check.py
```
`*_pack.py`는 `assets/`와 `docs/previews/`에 바로 쓰기 때문에 이번에는 돌리지 않았습니다(문서의 사용법은 코드에서 확인).

**긴 렌더 실행 요령**: Claude Code의 Bash 한 번은 최대 10분입니다. 전체 렌더는 백그라운드로 돌리고 로그를 봅니다.
```bash
mkdir -p /tmp/fv_cache
nohup /tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars all --samples 24 --portraits \
      > /tmp/fv_cache/vil_render_all.log 2>&1 &
grep -E "done in|frames to render" /tmp/fv_cache/vil_render_all.log      # 진행 확인
```
Cycles가 한 프로세스에서 코어 4개를 다 쓰므로(`threads_mode='AUTO'`) 렌더를 여러 개 동시에 돌려도 빨라지지 않습니다.

---

## 2. 공통 기반 — `tools/blender/bl_common.py`

**모든 스프라이트는 이 모듈로 렌더합니다.** 각도·PPU·조명을 바꾸면 기존 그림과 안 맞으므로 고치지 않습니다
(계약서 `docs/CONTRACT.md` §0: "DO NOT MODIFY without need; never change angles/PPU").

### 2.1 상수
| 이름 | 값 | 의미 |
|---|---|---|
| `PPU` | `64` | 화면 픽셀 / 미터 (가로) |
| `CAM_ELEV_DEG` / `CAM_YAW_DEG` | `30.0` / `45.0` | 직교 카메라: 아래로 30°, 방위 45° → 땅의 정사각형이 2:1 마름모 |
| `GROUND_SQUASH` / `VERTICAL_SCALE` | `0.5` / `0.866` | 땅 깊이 방향 압축 / 세로 높이 배율 |
| `DIR_YAW` | `{'S':45,'SE':90,'E':135,'NE':180,'N':225,'NW':270,'W':315,'SW':0}` | 앞면이 −Y인 물체를 화면 방향 d로 돌리는 Z 회전(도) |
| `RENDER_DIRS` | `['S','SE','E','NE','N']` | 실제로 렌더하는 5방향. SW/W/NW는 게임에서 `flipX`로 SE/E/NE를 뒤집어 씀 |
| `GAME_ROOT` / `ASSETS` | `tools/blender/../..` , `<GAME_ROOT>/assets` | 모든 출력 경로는 `__file__` 기준 → 폴더째 복사해도 동작 |

**투영 계산 (검증값, `world_to_pixel` 공식과 동일)**

| 월드 이동 | 화면 이동 (px) |
|---|---|
| +1 m 월드 X | (+45.25, +22.63) — 화면 오른쪽 아래로 |
| +1 m 월드 Y | (+45.25, −22.63) — 화면 오른쪽 위로 |
| +1 m 위(Z) | (0, −55.43) |
| +√2 m (≈1.4142 m) 월드 X / Y | **(+64, +32) / (+64, −32)** — 정수! (11장 격자 설계에 사용) |
| 1.45 m 키의 캐릭터 | 약 80 px 높이 |

### 2.2 함수
- `script_args()` — `sys.argv`에서 리터럴 `--` 뒤만 반환 (bpy 모듈 실행/`blender -b -P` 공통).
- `yaw_for_dir(d)` — `DIR_YAW[d]`를 라디안으로.
- `reset_scene()` — `read_factory_settings(use_empty=True)` + 재질 캐시 비움. 빌더마다 첫 줄에서 호출.
- `setup_render(width, height, samples=32, denoise=True)` — Cycles CPU, 적응형 샘플링, `max_bounces=6`,
  OIDN 디노이즈, **`film_transparent=True`**(배경 투명), `filter_size=1.2`, PNG RGBA 8비트,
  **`view_transform='Standard'`**(AgX는 장난감 같은 채도를 바랜 색으로 만들어서 안 씀).
- `setup_camera(width, height, anchor_px, ppu=PPU, target=(0,0,0))` — 직교 카메라.
  `ortho_scale = max(w,h)/ppu`, `shift_x/shift_y`로 **월드 점 `target`이 정확히 픽셀 `anchor_px`에 오게** 함.
  회전 `Euler((60°, 0, 45°))`, 거리 60 m.
- `setup_lighting(sun_strength=3.2, ambient=(0.72,0.80,0.95), ambient_strength=0.85, fill_strength=0.9, sun_angle_deg=6.0)`
  - `KeySun`: 따뜻한 흰색 (1.0,0.96,0.88), 회전 (0,−40°,0) → 화면 왼쪽 위에서 비춤, 그림자는 **화면 오른쪽 아래**로.
  - `FillSun`: 카메라 쪽에서 오는 그림자 없는 따뜻한 보조광, 세기 0.9, 각도 20°.
  - 월드 배경: 차가운 하늘색 환경광 (0.72,0.80,0.95)×0.85 — 겨울 느낌의 핵심.
- `add_shadow_catcher(size=12.0)` — 그림자만 받는 투명 바닥(`is_shadow_catcher`). 정적 소품만 사용, 캐릭터는 안 씀.
- `mat(name, color, rough=0.75, metal=0.0, emission=None, emission_strength=0.0, subsurface=0.0, alpha=1.0)` —
  캐시되는 Principled 재질. `color`는 sRGB(0..1 튜플 또는 `'#RRGGBB'`), 내부에서 선형으로 변환.
- `hex_rgb`, `srgb_to_linear`, `assign(obj, material)`, `shade_smooth(obj, auto_angle_deg=40)`,
  `render_to(path)`(폴더 생성 후 렌더 저장), `world_to_pixel(point, w, h, anchor_px, ppu)`(월드 점 → 프레임 픽셀; carryPoint·impactPoint 계산에 사용).

### 2.3 앵커·방향 규칙
- 월드 원점 (0,0,0) = 스프라이트의 **앵커**(캐릭터는 발, 소품은 바닥 면적 중심). 매니페스트에는 잘리지 않은 원래 프레임 기준
  정규화 값 `[ax, ay]`로 저장. 깊이 정렬은 앵커 y.
- 캐릭터: 프레임 128×128, 앵커 픽셀 (64,104) → `[0.5, 0.8125]`. 아이템: 72×72, 앵커 (36,54) → `[0.5, 0.75]`.
  소품/건물: 렌더 직전에 `prop_lib.frame_fit()`이 물체+그림자를 감싸는 크기와 정수 앵커를 계산.
- 물체의 "앞"은 로컬 −Y. 소품 빌더에서 `yaw=0` → 앞면이 화면 **왼쪽 아래(SW)**, `yaw=45` → 카메라 정면(S),
  `yaw=90` → 화면 오른쪽 아래(SE) (`life_assets.py` 머리말).
- 좌우 반전의 함정: (1) 그림자를 구운 소품을 `flipX`하면 그림자가 왼쪽 아래로 가서 틀립니다 → 소품은 반전 금지.
  (2) 캐릭터의 손잡이(사냥꾼 활은 오른손)·글자·비대칭 무늬는 반전되면 바뀝니다 — 전작은 보이지 않게 설계.
- 게임 쪽 방향 계산(계약서 §9): `a = atan2(vy*2, vx)`, 구간 `round(a/45°) mod 8` → 0 E, 1 SE, 2 S, 3 SW, 4 W, 5 NW, 6 N, 7 NE.

---

## 3. 포장 도구 — `tools/pack_utils.py`

| 함수 | 하는 일 |
|---|---|
| `clean_alpha(img, floor=10)` | 알파 `floor` 미만을 0으로, 나머지를 0–255로 다시 늘림 → 그림자 받이 바닥이 남기는 희미한 안개 제거. 소품은 그림자 있는 프레임 floor 10, 그림자 없는 프레임(아이템 등) floor 3 |
| `pack_atlas(frames, max_width=2048, trim=True, padding=2)` | `frames=[(name, PIL RGBA)]`. 투명 여백을 1px 남기고 잘라냄(trim) → 키 큰 것부터 선반(shelf) 배치 → 시트 크기는 4의 배수 → 4096 초과면 `ValueError`. 반환 `(sheet, atlas_dict)` |
| `save_atlas(sheet, atlas, png_path, json_path, quantize=False)` | PNG + JSON 저장. `quantize=True`는 Pillow FASTOCTREE 256색 → **줄무늬(밴딩)가 생겨서 파이프라인들은 쓰지 않고**, 대신 imagequant로 따로 양자화함 |
| `contact_sheet(images, cols, out_path, cell=None, bg=..., labels=None)` | 미리보기 격자 |

아틀라스 JSON = **Phaser 3 "JSON Hash"(TexturePacker 호환)**:
```json
"frames": {"walk_SE_3": {"frame": {"x":0,"y":0,"w":52,"h":88}, "rotated": false, "trimmed": true,
            "spriteSourceSize": {"x":38,"y":20,"w":52,"h":88}, "sourceSize": {"w":128,"h":128}}},
"meta": {"app": "frost-village/tools/pack_utils.py", "image": "char_player.png", "format": "RGBA8888", ...}
```
Phaser가 `sourceSize`를 원점 계산에 쓰므로 잘라낸 프레임에도 `setOrigin(anchor)`가 그대로 맞습니다(크롬에서 검증됨).

알려진 사소한 점: (1) 팔레트 PNG여도 `meta.format`은 `RGBA8888`로 적힘(Phaser는 무시). (2) 선반 배치에서 너비 계산이
padding을 포함해 **최대 2052 px**가 될 수 있음 — 실제로 `vil_npc_kid_boy/kid_prankster/teen_girl`이 2052 px 폭.
2048 제한 기기를 고려한다면 `pack_atlas`에서 `used_w = max(used_w, x - padding)`으로 고치면 됩니다(전작에서는 미수정).

---

## 4. 캐릭터 파이프라인 — `tools/blender/char_*.py`

대상: `player, fisherman, lumberjack, farmer, miner, hunter, villager_a, villager_b, villager_c` (사람) + `deer, boar` (동물).

### 4.1 모듈
| 파일 | 역할 |
|---|---|
| `char_geo.py` | bmesh로 수학적으로 모양 생성(빠르고 결정적): `bm_lathe`(회전체, 타원 단면), `bm_ellipsoid`, `bm_capsule`, `bm_shell`(방향별 반지름 함수 → 머리카락·후드·수염), `bm_ring`(털 고리), `bm_box`, `bm_slab`, `bm_cyl`, `bm_tube_path`, `mesh_obj`, `empty`, **`Rig` 클래스** |
| `char_build.py` | 사람 몸·얼굴·옷·도구. `build(key)` → 장면 초기화 후 포즈 가능한 `Rig` 반환. `SPECS`(색·옵션), `dress_<직업>()`, 도구 `make_axe/make_pickaxe/make_sickle/make_rod/make_bow`, `anims_for(key)`, `HUMAN_KEYS`, `ANIMAL_KEYS`, `ALL_KEYS` |
| `char_animals.py` | 사슴·멧돼지(네발, 다리 대각선 짝 걸음) |
| `char_anim.py` | **순수 파이썬(bpy 없음)** 포즈 함수. `HUMAN_ANIMS`, `ANIMAL_ANIMS`, `WORK_IMPACT`, `pose_for(kind, anim, i, n, key)` |
| `char_extras.py` | 초상화 128×128(UI 카메라 고도 15°), 512×512 키아트, 사냥꾼 날아가는 화살 |
| `char_render.py` | 렌더 드라이버 + `meta.json`(carryPoint, impactPoint, shadow) |
| `char_pack.py` | 잉크 외곽선 → 아틀라스 → 양자화 → 매니페스트 → 미리보기 |
| `char_check.py` | 계약서 §3 대조 검사 |

### 4.2 리그와 포즈 형식 (`char_geo.Rig`)
- 리그 = 이름 붙은 회전축 empty들의 계층. 사람: `root > hips > spine > chest > neck > head`, `chest > sh_R/sh_L > el_R/el_L > hand_R/hand_L`,
  `hips > hip_R/hip_L > knee_R/knee_L`. 몸 부품은 이 empty에 **딱딱하게 붙은 메시**(스키닝 없음) → 애니메이션 = 관절 회전.
- 몸 치수(미터): `HIP_Z=0.34, CHEST_DZ=0.33, NECK_DZ=0.12, HEAD_C=0.27, HEAD_R=(0.300,0.285,0.280), UPPER_ARM=0.125, FOREARM=0.115, THIGH=0.150`.
  키 약 1.40–1.48 m(모자 포함), 약 2.5등신, 화면 약 80 px. 오른쪽 = −X.
- 포즈 = dict:
  - `'관절': (pitch, roll, yaw)` 도. 팔·다리는 pitch>0 = 앞으로, roll>0 = 바깥쪽. 무릎은 pitch>0 = 정강이 뒤로 접힘.
    (`vil_anim` 머리말: spine/chest/head/root는 pitch>0 = **뒤로** 기울기 → 앞으로 숙이기는 음수)
  - `'관절@': (dx,dy,dz)` 이동(m), `'관절%': (sx,sy,sz)` 크기, `'root'`는 방향 yaw에 더해짐.
  - `'ik_R'/'ik_L': (x,y,z[, px,py,pz])` 가슴 기준 손 목표점(+팔꿈치 방향) → `Rig.solve_arm()` 해석적 2관절 IK.
  - `'_show': {토글 이름...}` 이 프레임에 보일 부품(얼굴 표정, 도구 등). `Rig.toggle(name, objs)`로 등록한 것만.
- `Rig.apply(pose, yaw_deg)` → 매 프레임 리셋 후 적용. `Rig.update_strings()` = 낚싯줄·활시위 같은 동적 부품 갱신.
- 도구의 끝(도끼날, 곡괭이 끝…)에는 `fx_marker(rig, tool, parent, loc)` empty를 두고, 렌더 때 이것을 픽셀로 바꿔 `impactPoint`가 됩니다.

### 4.3 애니메이션 (`char_anim.py`)
| 애니 | 프레임 | fps | 비고 |
|---|---|---|---|
| idle / carry_idle | 4 | 6 | 숨쉬기. carry = 두 팔을 가슴 높이로 앞으로 (`CARRY_ARMS`) |
| walk / carry_walk | 8 | 12 | 통통 튀는 치비 걸음 (`legs_walk`) |
| chop / mine | 8 | 14 | `_tool_swing_keys('axe')` · `_tool_swing_keys('pickaxe', low=True)`: 준비→들기→뒤로 젖힘→정지→빠른 내려치기→**5번 타격**→반동→복귀. `impactFrame=5` |
| harvest | 6 | 10 | 쪼그려 집기, `impactFrame=3` (손 위치) |
| work | 8 | 14 | 직업별: 나무꾼 도끼, 광부 곡괭이(낮게), 어부 던지기·감기, 농부 낫, 사냥꾼 활. `WORK_IMPACT={'fisherman':4,'lumberjack':5,'farmer':4,'miner':5,'hunter':5}` |
| happy | 6 | 10 | 손 들고 깡충, ^^ 눈 |
| (동물) idle 4/6, walk 8/12 | | | 대각선 다리 짝 걸음, 꼬리·귀 움직임 |

- 루프는 주기적: n프레임 중 i번째 = 위상 i/n → 마지막 프레임이 첫 프레임으로 자연스럽게 이어짐(보고서: 모든 루프 수치 검사로 이음매 없음 확인).
- 키 포즈 보간: `keyed(keys, i)`(정확히 그 포즈), `cyc_spline(keys, t)`(주기적 Catmull-Rom), `lerp_pose`, `add_pose`.
- 어떤 키가 어떤 애니를 갖는지: `char_build.anims_for(key)` — player: idle, walk, carry_idle, carry_walk, chop, mine, harvest /
  villager_*: idle, walk, carry_walk, happy / 나머지 일꾼: idle, walk, carry_idle, carry_walk, work.

### 4.4 렌더 (`char_render.py`)
```bash
# 전체 (보고서 기준 약 12분, 결과 그대로 재현하려면 --samples 28)
/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars all --samples 28 --portraits --keyart
# 일부만
/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars lumberjack --anims work --dirs S,E --force
# 렌더 없이 meta.json(carryPoint/impactPoint)만 다시 계산
/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars all --meta-only
# PC
blender -b -P tools/blender/char_render.py -- --chars player --cache C:/fv_cache/characters
```
옵션: `--chars all|키,키` (기본 `player`), `--anims all|..`, `--dirs all|S,SE,..`, `--frames all|0,3`, `--samples 24`(기본),
`--cache /tmp/fv_cache/characters`(기본), `--force`(이미 있는 PNG도 다시), `--portraits`(초상화 + 사냥꾼 화살),
`--keyart`(512 키아트), `--only-extras`, `--meta-only`.

- 장면: `bc.setup_render(128,128)` + 바운스 줄임(`max_bounces=4`, diffuse/glossy/transmission 2), `adaptive_threshold=0.02`,
  `use_persistent_data=True`, `bc.setup_camera(128,128,(64,104))`, `bc.setup_lighting()`. 그림자 받이 **없음**.
- 쓰기는 `<path>.tmp.png`로 렌더 후 `os.replace` → 중간에 끊겨도 반쯤 쓴 파일이 남지 않음 → 그냥 다시 실행하면 이어짐.
- 출력: `/tmp/fv_cache/characters/<key>/<anim>_<dir>_<i>.png`(128×128), `meta.json`, `portrait.png`, `keyart_512.png`(player), `projectile_arrow.png`(hunter).
- `meta.json`: `carryPoint[dir] = [dx, dy, behind]` = carry_idle 0번 프레임에서 두 손 중간 +5 cm 위(NE/N은 `behind=true`),
  `anims.<anim>.impactPoint[dir] = [dx, dy]` = impactFrame에서 도구 끝 위치, `shadow = [w, h]` 바닥 타원.
- 초상화(`char_extras.render_portrait`): UI 카메라 고도 15°(얼굴이 잘 보이게), 대상 높이 ~1.02 m, 앵커 (64,70), 정면에서 −12° 돌림,
  모자가 큰 캐릭터는 `PORTRAIT_FIT`로 확대 조정. UI 전용이며 월드 스프라이트는 모두 30° 카메라.

### 4.5 포장 (`char_pack.py`)
```bash
python3 tools/blender/char_pack.py                  # 캐시에 있는 전부 (ORDER 순서)
python3 tools/blender/char_pack.py --chars player   # 한 명만 (매니페스트의 다른 키는 유지)
python3 tools/blender/char_pack.py --no-previews --cache /tmp/fv_cache/characters
```
1. **잉크 외곽선** `ink_outline(im, color=INK(52,40,48), strength=0.85, mix=0.70)`: 실루엣 바깥 1px, 대각선은 0.6배,
   선 색 = 이웃 픽셀 색 30% + 잉크 70% (색이 섞인 선화). 흰 파카가 눈밭에서 묻히지 않게 해 줌. **다시 외곽선을 넣지 말 것.**
2. `pack_utils.pack_atlas(max_width=2048, trim=True, padding=2)` → `assets/characters/char_<key>.png/.json`.
3. **imagequant 양자화** `imagequant.quantize_pil_image(sheet, dithering_level=0.6, max_quality=100, min_quality=0, max_colors=256)` —
   3배 확대해도 원본과 같아 보이고 약 3.5배 작음. (Pillow 자체 양자화는 머리카락·파카에 띠가 생김)
4. 초상화 복사, 매니페스트 작성, 미리보기.

**매니페스트 항목** (`assets/characters/manifest.json` → `characters.<key>`, 실제 값 예):
```json
"lumberjack": {"atlas": "char_lumberjack", "frameSize": [128,128], "anchor": [0.5,0.8125],
  "dirs": ["S","SE","E","NE","N"], "mirror": {"SW":"SE","W":"E","NW":"NE"}, "frameName": "{anim}_{dir}_{i}",
  "anims": {"idle": {"frames":4,"fps":6,"repeat":-1}, "walk": {...}, "carry_idle": {...}, "carry_walk": {...},
            "work": {"frames":8,"fps":14,"repeat":-1,"impactFrame":5,
                     "impactPoint": {"S":[6,-2],"SE":[29,-10],"E":[35,-24],"NE":[20,-35],"N":[-8,-38]}}},
  "carryPoint": {"S":[0,-31,false],"SE":[12,-34,false],"E":[17,-40,false],"NE":[12,-46,true],"N":[0,-48,true]},
  "shadow": [46,18], "portrait": "portrait_lumberjack", "kind": "human", "headTop": -85}
```
- `headTop` = idle_S_0의 불투명 영역 맨 위 − 앵커 y (말풍선 위치). 반전 방향(SW/W/NW)은 dx 부호를 뒤집어 씀.
- 그 밖: `images/sprites`에 `portrait_<key>`(kind `ui`), `portrait_player_512`, `projectile_arrow`(char_hunter 아틀라스 안의 64×32 프레임, kind `fx`).
- 미리보기(`docs/previews/`): `char_lineup.png`, `char_<key>.png`(애니별 S방향 + 5방향 + impact/carry 표시), `char_<key>_walk.gif`,
  `char_<key>_work.gif`(일꾼)/`_happy.gif`(손님)/`_idle.gif`(동물), player는 `chop/mine/harvest/carry_walk.gif`,
  `char_carry_check.png`(8방향에서 carryPoint에 생선 더미를 올려 본 것). 미리보기 합계 약 7.9 MB(대부분 GIF).

### 4.6 검사 (`char_check.py`)
`python3 tools/blender/char_check.py` (오류 시 종료 코드 1). 매니페스트가 암시하는 모든 프레임 이름 존재, `sourceSize == frameSize`,
PNG 크기 = JSON meta, 잘린 프레임이 128 테두리에 닿지 않는지(잘림 경고), mirror 대상이 렌더 방향인지, impactFrame 범위,
carry 캐릭터의 5방향 carryPoint, 초상화 존재, 용량 ≤ 8 MB. **필수 키·애니 목록은 `EXPECTED`/`FRAMES`에 하드코딩**되어 있음.

---

## 5. 주민·펫 파이프라인 — `tools/blender/vil_*.py`

캐릭터 파이프라인을 확장한 것(같은 `bl_common`, `char_geo.Rig`, `char_build`의 몸·옷 일부 재사용). 차이점은
**바꿔 끼우는 얼굴 부품(표정)**, **체형 7종**, **사회적 애니 3방향**, 펫입니다.
대상 키: `npc_kid_boy, npc_kid_girl, npc_kid_prankster, npc_teen_girl, npc_young_man, npc_aunt, npc_uncle, npc_grandma,
npc_grandpa, npc_merchant, npc_herbalist, npc_bard, npc_blacksmith, npc_fashion, npc_yellow, npc_red, npc_blue` + `pet_dog, pet_cat, pet_penguin`.

### 5.1 모듈
| 파일 | 역할 |
|---|---|
| `vil_face.py` | 머리 타원체 위에 감싸 붙이는 얼굴 "데칼" 부품을 전부 만들고 토글로 등록 (`build_face(rig, spec)`). 얼굴 공간(u=오른쪽, v=위, 미터)에서 그린 뒤 머리 앞면에 투영 → 체형이 머리를 키워도 같은 얼굴 재사용. 도구: `bm_stroke`, `bm_blob`, `ellipse`, `arc`, `heart`, `teardrop`, `lumpy` |
| `vil_body.py` | `BODY` 체형 표(`adult, tall, kid, teen, plump, strong, elder` — 몸통·머리·팔·손·다리 배율, 엉덩이 폭), `build_body(spec)`, `apply_proportions(rig, P)` |
| `vil_dress.py` | 캐릭터별 머리·모자·옷·소지품 `dress_<key>()`와 `DRESS` 매핑. 공용 도구: `std_profile`, `quilted_profile`(퀼팅 패딩), `sector_lathe`(앞치마처럼 일부만 덮는 회전체), `mat_bands`(줄무늬 재질), `round_glasses`, `scarf_ring`, `striped_tail`, `pompom`, `bow_ribbon`, 손 소품 `make_snowball/make_cane/make_lute/make_shades` |
| `vil_pets.py` | `build_dog/build_cat/build_penguin`, `PET_SCALE={'pet_dog':1.28,'pet_cat':1.30,'pet_penguin':1.18}`, 펫 눈 토글 |
| `vil_anim.py` | **순수 파이썬** 포즈 + 프레임별 표정. `ANIMS`, `PET_ANIMS`, `FACES`, `human_pose`, `pet_pose`, `SEAT_H=0.45` |
| `vil_build.py` | 로스터: `SPECS`, `KEYS`, `PET_KEYS`, `ALL_KEYS`, 애니 보유 집합 `RUNNERS/THROWERS/DANCERS/SITTERS/PERFORMERS`, `anims_for`, `build`, `pose_for` |
| `vil_render.py` | 렌더 + `meta.json` + 초상화 + 표정 룩데브 |
| `vil_pack.py` / `vil_check.py` / `vil_lookdev.py` | 포장 / 검사 / 표정 시트 합성 |

### 5.2 얼굴 부품과 표정
- 토글 이름(부품군, `vil_face.build_face`에서 `add(...)`로 등록된 실제 목록): 눈 `eye_dot, eye_blink, eye_happy(^^), eye_chevron(><), eye_round, eye_big, eye_teary, eye_glare, eye_sleep, eye_heart` /
  눈썹 `brow_neutral, brow_up, brow_angry, brow_sad` / 입 `m_smile, m_grin, m_D, m_open, m_mid, m_O, m_pout, m_frown, m_wavy, m_clench, m_sing, m_smirk, m_gap, m_gapD` /
  볼 `cheek_blush, cheek_red, cheek_cold` / 효과 `fx_tear, fx_snow, fx_sweat`. (장난꾸러기는 `face_sub`로 `m_grin→m_gap`, `m_D→m_gapD`, `m_smile→m_smirk` 치환)
- 표정 프리셋 `vil_anim.FACES`: `neutral, blink, smile, happy, laugh, laugh_b, talk_open, talk_mid, talk_closed, talk_blink, talk_happy,
  surprised, startle, angry, angry_huff, angry_shout, sad, sad_b, sad_blink, hurt, hurt_open, hurt_pout, sleepy, sleepy_b, shiver, shiver_b, sing, heart, scheme`
  — 각각 부품 이름 목록. 예: `'angry': ['eye_glare', 'brow_angry', 'm_pout', 'cheek_red']`.
- 포즈 함수는 `face(name, props)`로 `{'_face': 이름, '_props': {소품}}`을 넣고, `vil_build.show_set()`이 이를 리그의 `_show` 집합으로 바꿈
  (캐릭터별 `face_sub` 치환, 멋쟁이 선글라스 올리기, 음유시인 류트 등 처리).
- 얼굴 파라미터(`SPECS[key]['face']`): `skin, blush, eye, brow, eye_u, eye_v, eye_w, eye_h, mouth_v, mouth_out(수염 위로 입 올리기), brow_v, brow_w, brow_thick, lashes, ears, nose('dot'|'big'), nose_color, cheek_u, cheek_v`.
- 부품을 일부러 크고 두껍게 만들어 폰 1:1(약 80 px)에서도 읽힘(3배 최근접 확대로 확인).

### 5.3 애니메이션 (`vil_anim.ANIMS`)
| 애니 | 프레임/fps | 반복 | 방향 | 누가 |
|---|---|---|---|---|
| idle | 4/6 | 루프 | 5방향 | 전원 (2번 프레임에서 깜빡) |
| walk / carry_walk | 8/12 | 루프 | 5방향 | 전원 / 사람 |
| run | 8/16 | 루프 | 5방향 | `RUNNERS`(아이들, 십대, 청년), 펫 |
| happy, talk, laugh, wave, angry, dance, perform | 6–8/10 | 루프 | **S, SE, E** | 사람 (dance=`DANCERS`, perform=음유시인) |
| surprised | 6/12 | 한 번 | S, SE, E | 사람 |
| sad 4/6, shiver 4/12, sit 4/4 | | 루프 | S, SE, E | sit=`SITTERS` |
| throw | 8/14, `impactFrame=5` | 한 번 | S, SE, E | `THROWERS` |
| hit | 6/12 | 한 번 | S, SE, E | 사람 |
| (펫) idle 4, walk 8, run 8 (5방향); sit 4, happy 6, loaf 4(고양이) (3방향) | | | | |

- 사회적 애니를 N/NE/NW에서 해야 하면 게임이 가장 가까운 S/SE/E/SW/W로 돌림(계약서 부록 A).
- **카메라 쪽으로 속이기(cheat)**: E/SE에서 사회적 애니는 몸통·머리를 카메라 쪽으로 돌림 `CHEAT={'E':(-9,-20),'SE':(-3,-8)}`,
  perform은 `CHEAT_PERFORM`, throw는 제외(`NO_CHEAT`). 옆모습 대화에서도 표정이 보이게.
- `posture(ch, anim)`: 노인은 `hunch` 각도만큼 매 포즈에 굽은 자세를 더함. 노인 걷기 속도는 게임에서 0.75배 권장.
- `ik_R/ik_L` 목표는 표준 몸 기준이며 `vil_build.pose_for`가 캐릭터의 몸통 배율로 늘려 줌.

### 5.4 로스터 항목 예 (`vil_build.SPECS`)
```python
'npc_blacksmith': dict(
    name=('대장장이 언니', 'Blacksmith'), role='adult', traits=['hearty', 'belly_laugh', 'arms_akimbo'],
    body='strong', coat='#7A8A9A', hair='#4A2A1E', pants='#3B3540', boots='#3B2A20', bare_hands=True,
    bare_forearms=True, **NOFUR, hem_r=0.235, hem_z=-0.06,
    face=dict(brow='#4A2A1E', lashes=True, brow_thick=0.014), idle_style='hips', shadow=[50, 19]),
```
- `base='villager_a'`처럼 쓰면 `char_build.SPECS`의 옷 설정을 물려받음(`npc_yellow/red/blue`).
- `coat='bands'` → 줄무늬 코트(`vd.mat_bands`), `vest='plaid'`, `quilted=True`, `cardigan='#..'`, `torso_profile=LONG_DRESS/LONG_SKIRT/LONG_COAT`,
  `cane=True`, `hunch=13.0`, `sit_sleepy=True`, `shades=True`, `face_sub={...}`, `idle_style='hips'|'hip_one'|'clasp'|'back'`.

### 5.5 렌더·포장·검사
```bash
# 1) 렌더 (재개 가능, 약 40분)
/tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars all --samples 24 --portraits
#    하나만: --chars npc_bard --force / 애니 하나: --anims sit / 방향: --dirs S,E / --meta-only
#    PC: blender -b -P tools/blender/vil_render.py -- --chars npc_grandpa
# 2) 포장 (약 2분, imagequant 필요). 기본 192색 (256이면 폴더가 10.6 MB로 예산 10 MB 초과)
python3 tools/blender/vil_pack.py            # [--chars npc_bard] [--no-previews] [--colors 256] [--cache DIR]
# 3) 검사
python3 tools/blender/vil_check.py
# 4) 표정 시트 (룩데브)
/tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars npc_kid_prankster,npc_kid_girl,npc_uncle,npc_grandpa,npc_fashion --lookdev
python3 tools/blender/vil_lookdev.py          # [--keys a,b] [--out docs/previews/vil_expressions.png] [--faces ...]
```
- 렌더 기본값: `--chars npc_grandpa`, `--samples 20`, 캐시 `/tmp/fv_cache/villagers`. `--lookdev`(+ `--faces a,b`)는 `<cache>/_lookdev/<key>_<face>_<S|E>.png`(게임 크기, idle 0번 포즈)와 `<key>_<face>_S_zoom.png`(160×160 머리 클로즈업)를 만듦.
- `meta.json`: `carryPoint`(carry_walk 0번 프레임 기준; 아이들은 S 약 [2,−23]로 낮음), `throw.impactPoint`(눈덩이 놓는 점),
  앉는 캐릭터는 `seatOffset=[0,0]`, `seatHeightPx=25`(=0.45 m×0.866×64). sit 프레임의 앵커 = **좌석 윗면 앞 중앙**.
- 매니페스트 추가 필드: `kind(villager|pet), role, name{ko,en}, traits[], headTop, shadow, portrait, seatOffset, seatHeightPx, headTopSit`,
  그리고 **애니마다 자기 `dirs`**. 최상위 `notes`.
- `vil_check`: 20키 전부, 계약 표(TABLE — `vil_anim`과 독립적으로 다시 적은 표)대로 프레임/fps/repeat/dirs, 모든 프레임 이름, 테두리 닿음,
  throw impactPoint, 사람 carryPoint 5방향, 앉는 캐릭터 seatOffset, 이름·역할·특성, 초상화, 용량 ≤ 10 MB.
- 미리보기: `vil_lineup.png`, `vil_<key>.png`(시트), `vil_<key>_<anim>.gif`(SHOWCASE 목록), `vil_expressions.png`(5명 × 17표정), `vil_phaser_smoke.png`.
- 작업 흐름 교훈(보고서): 먼저 3명으로 룩데브 → 전 애니를 낮은 품질로 훑어보며 문제(머리 뒤로 숨는 팔, 너무 얇은 목도리, 수염에 묻힌 입 등)를 고친 뒤 전체 렌더.

---

## 6. 소품·건물·아이템 파이프라인 — `tools/blender/prop_*.py`

### 6.1 `prop_lib.py` — 모델링·재질·프레이밍 도구
- **팔레트 `PAL`**: 계약서 §1 색 + 소품용 추가색(`snow_mat '#E9EFF7'`, `plank`, `soil`, `brick`, `iron`, `steel`, `window`, `copper` …). `C(name_or_hex)`, `hexmix(a,b,t)`.
- **알베도 보정** `adj()`: 공용 조명이 옆면을 약 1.4배 밝게 하므로 선형 공간에서 `ALBEDO_K=0.8`을 곱함(눈 `snow_mat/snow`는 제외).
  `flat(color, rough, metal, ...)`이 자동 적용. (캐릭터는 이 보정 없이 `bc.mat` 직접 사용)
- 재질: `flat`, `snowy(base, ...)`(위를 향한 면에 노이즈 경계로 눈), `tonal`(얼룩), `end_grain`(통나무 나이테), `brick`, `stripes`,
  `emissive`, `set_emission`, `flame_mat`, `smoke_mat`, `set_alpha`, 노드 빌더 `NB`.
- 기본 도형: `box`, `cyl`, `sphere`, `blob`(울퉁불퉁 바위·눈더미), `log`(나이테 단면 통나무), `revolve`, `extrude`(2D 외곽선 돌출), `tube`, `smooth_tube`,
  `point_light`, `group`, `snow_slab`(지붕·뚜껑 위 둥근 눈층), 메시 합치기 빌더 `MB`(`cone/sphere/ico/cube/seg` → `done(name)`).
- 움직이는 부품(작업 프레임용): `Flames(name, spots)`(4프레임 불꽃 깜빡임, `set(i)`, `show(on)`), `Smoke(...)`(피어오르는 연기 `set(i)`), `Spray(...)`(톱밥 등 뿌리기).
- `Collect` — `with L.Collect() as c:` 블록 안에서 만든 객체를 `c.objs`로 모음(단계별 보이기/숨기기에 사용).
- `rotate_all(yaw_deg)` — 최상위 객체 전부를 Z축으로 회전(태양 제외).
- **`frame_fit(margin=6, shadow=True, ...)`** — 모든 꼭짓점과 (그림자 있으면) 바닥에 드리운 그림자 범위(`SHADOW_K`, 높이에 비례한 반그림자 여유)를
  화면에 투영해 프레임 크기(4의 배수)와 정수 앵커를 계산. 반환 `(w, h, (ax, ay), topPx)`.
- `footprint_px(size_m, yaw)` — 바닥 면적(m 또는 `('r', 반지름)`)의 화면 크기. `stack_step(thickness_m) = round(thickness*0.866*64)`.

### 6.2 `prop_assets.py` — 레지스트리와 빌더
```python
@asset(key, kind, atlas, fp=None, shadow=True, samples=64, yaw=0.0, work=0, fps=8, notes='',
       item=None, front=None, catcher=14.0)
def b_<key>():
    ...                                   # prop_lib로 모형 생성 (월드 원점 = 바닥 면적 중심)
    return {...}                          # 선택
```
- `kind`: `prop|station|building|decor|item|decal`. `atlas`: `props_nature|props_buildings|props_decor|props_items`(새 이름도 가능).
- `fp`: 바닥 면적 `(a_X, b_Y)` m 또는 `('r', 반지름)`. `catcher`: 그림자 받이 크기(큰 건물은 18–24).
- `item={'thickness': m}` → 그림자 없음, 고정 프레임 `ITEM_FRAME=(72,72)`, 앵커 `ITEM_ANCHOR=(36,54)`, `stackStep` 자동 계산(넘치면 WARNING 출력).
- `work=4`(작업 프레임 수), `fps`. 빌더가 `{'work': fn(i), 'idle': fn(), 'fx': {이름: 월드점}}`을 돌려줘야 함 — `idle()`은 정지 상태 복원.
  `fx` 점은 픽셀 오프셋 `fxPoints`가 됨(예: 그릴 `fire [0,-34]`, `smoke [-11,-98]`).
- `{'extra': {...}}`는 sidecar JSON에 그대로 병합(예: 울타리 `{'tileAxis': 'x'}`). `{'notes': ...}`, `{'custom_catcher': True}`도 가능.
- 등록 예: `crop_wheat_0..3`은 반복문으로 `asset(...)(fn)`을 4번 호출해 4개 키로 등록(성장 단계).
- 공유 서브모델: `log_house(W, D, wall_h, ridge_z, ...)`(통나무집, 지붕은 X축 방향, 문은 −Y), `roof_panel`, `snow_cap`, `pine`, `fish_model`, `steak_model`,
  `bread_model`, `meat_model`, `crate_model`, `barrel_model`, `log_pile`, `stone_ring`, `awning`, `lantern`, `flag`, `voussoir_arch`, `ingot_model`, `fence_logs`.

**스테이션(작업 애니) 만드는 기법** (`b_station_grill` 참고): idle은 불 꺼진/어두운 상태, `work(i)`에서 발광 세기(`set_emission`)·
점광원 세기·`Flames.set(i)`·`Smoke.set(i)`·부품 위치를 바꿈. 톱날은 프레임당 22.5° 회전 → 4프레임이 이음매 없이 반복.
`fit_states()`가 idle과 모든 work 상태를 합친 프레임 하나와 **공유 앵커**를 계산 → 연기가 잘리지 않고, 게임에서 프레임만 바꿔 끼우면 됨.
처음엔 프레임 간 변화가 14–34 px뿐이라 거의 정지해 보였고, 다시 만들어 700–2,500 px로 키웠음(보고서 props_run2) — **작업 애니는 눈에 띄게 크게 움직여야 함**.

**이어 붙는 울타리 기법** (`fence_log_x/y`): 1 m 구간을 렌더할 때 양옆 이웃 구간도 만들되 `visible_camera=False`(카메라엔 안 보이고 그림자만 드리움)로 두어
연속 울타리의 그림자를 얻음 → `prop_pack.tile_shadow()`가 자기 1 m 구간 몫만 남김(합이 1이 되는 가중치 w, `a' = 1-(1-a)^w`) → 겹쳐 그리면 정확히 연속 그림자.
배치: x 구간은 (+45.25, +22.63) px 간격, y 구간은 (+45.25, −22.63) px 간격, 끝과 모서리에 `fence_post`.

### 6.3 `prop_render.py`
```bash
/tmp/bvenv/bin/python tools/blender/prop_render.py -- --list                     # 키 목록만 (렌더 없음)
/tmp/bvenv/bin/python tools/blender/prop_render.py --                            # 캐시에 없는 것 전부 (재개)
/tmp/bvenv/bin/python tools/blender/prop_render.py -- --force                    # 전부 다시 (6–8분)
/tmp/bvenv/bin/python tools/blender/prop_render.py -- station_* --force          # 접두어 * / 아틀라스 이름(props_items)도 가능
blender -b -P tools/blender/prop_render.py -- station_grill --force             # PC
```
옵션: 키·아틀라스 이름들, `--force`, `--samples N`(기본: 키마다 64), `--cache DIR`(기본 `<tempdir>/fv_cache/props`), `--list`.
순서: `reset_scene` → `setup_lighting` → 빌더 → `rotate_all(yaw)` → 프레임 맞춤 → 그림자 받이 → `setup_render/setup_camera` → idle + work 프레임 렌더.
캐시에 `<key>.png`, `<key>_work_<i>.png`, sidecar `<key>.json`(`key, kind, atlas, frameSize, anchorPx, anchor, frames, shadow, notes, topPx, footprint, footprintM, front, anims, stackStep, thicknessM, fxPoints, + extra`).
렌더 시간(`props/render3.log`, 64샘플): 아이템 약 0.3초, 보통 소품 약 2초(중앙값), 통나무집 약 15초, 큰 집·스테이션 20–37초. 스테이션만 다시 렌더한 `render4.log`에서는 46–78초.

### 6.4 `prop_pack.py`
```bash
python3 tools/blender/prop_pack.py                   # [--cache DIR] [--no-previews] [--quantize]
```
1. 그림자 있는 프레임: `clean_alpha(floor=10)` → (울타리면 `tile_shadow`) → `tint_shadow`(검은 그림자를 차가운 남보라 `SHADOW_RGB=(38,46,82)`, 불투명도 0.85배) → `border_fade(width=10)`(프레임 끝에서 그림자가 칼같이 끊기지 않게).
   그림자 없는 프레임(아이템 등): `clean_alpha(floor=3)`만.
2. 아틀라스 그룹별 포장(`ATLAS_ORDER` + 새 그룹은 이름순), 2048 넘으면 `_2, _3`으로 분할(스프라이트의 프레임은 같은 시트에).
3. 아이템 `carryScale` 측정: 실제 불투명 폭이 약 31 px(`CARRY_TARGET_W`)가 되게, 0.55–0.65 범위, 0.05 단위.
4. `assets/props/manifest.json`(`version, generator, conventions, atlases, sprites`) + 미리보기
   `props_all.png, props_items.png, props_scene.png(가짜 마을 + 실제 캐릭터), props_stations_work.png/.gif, props_carry.png`.
- 기본은 양자화 안 함(RGBA): 부드러운 그림자에 띠가 생기기 때문. `--quantize`는 Pillow 내장 libimagequant(`Image.Quantize.LIBIMAGEQUANT`)를 시도하지만 이 컨테이너의 Pillow 12.3은 그 기능이 없어서(`features.check_feature("libimagequant") == False`) FASTOCTREE로 떨어져 띠가 생깁니다. 용량이 필요해지면 `char_pack`/`life_pack`처럼 pip 패키지 `imagequant.quantize_pil_image(...)`를 쓰도록 바꾸세요.

**매니페스트 예 (실제 값)**
```json
"station_grill": {"atlas":"props_buildings","frame":"station_grill","anchor":[0.44403,0.62719],"kind":"station",
  "footprint":[190,95],"anims":{"work":{"frames":["station_grill_work_0","station_grill_work_1","station_grill_work_2","station_grill_work_3"],"fps":8,"repeat":-1}},
  "frameSize":[268,228],"topPx":89,"footprintM":[2.6,1.6],"fxPoints":{"fire":[0,-34],"smoke":[-11,-98]},"notes":"..."}
"item_log": {"atlas":"props_items","frame":"item_log","anchor":[0.5,0.75],"kind":"item","stackStep":13,"icon":true,
  "carryScale":0.65,"frameSize":[72,72],"topPx":22,"thicknessM":0.24,"notes":"..."}
"worker_hut": {"atlas":"props_buildings","frame":"worker_hut","anchor":[0.39474,0.65489],"kind":"building",
  "footprint":[235,118],"frameSize":[380,368],"topPx":221,"front":"-Y","footprintM":[2.8,2.4],"notes":"..."}
```
- 아이템 쌓기: i번째 복사본을 `y - i*stackStep`에(바닥·패드 탑, UI 아이콘은 scale 1). 손에 들 때는 scale `carryScale`, 간격 `stackStep*carryScale`.
- `topPx`: 앵커 위 시각적 높이(말풍선·진행 링). `footprint`: 앵커 중심의 바닥 마름모/타원 화면 크기(충돌·배치).
- 게임이 스테이션의 `anims.work`를 `spr:<key>:work` 애니로 자동 생성(`src/core/Assets.js`; 생활 소품의 `anims`도 같은 방식).

### 6.5 `prop_check.py`
`python3 tools/blender/prop_check.py` — 계약서 §4의 53키(`NATURE/STATIONS/BUILDINGS/DECOR/ITEMS`에 하드코딩), 아틀라스·프레임 존재, 앵커 정규화와 sourceSize 일치,
시트 ≤ 2048, 스테이션 4프레임 루프와 idle과 같은 프레임 크기, 아이템 `stackStep` 8–14 정수와 `carryScale` 0.4–1.0, 비아이템 footprint, 용량 ≤ 5 MB.

---

## 7. 생활 소품 파이프라인 — `tools/blender/life_*.py`

소품 파이프라인과 같은 카메라·조명·PPU·그림자 받이·후처리(`prop_pack`의 `tint_shadow`, `border_fade`)를 쓰되, **한 빌드가 여러 상태 프레임을 공유 앵커로 내는 기능**과
**상호작용 점(마커)** 기능이 더해졌습니다. 세틀러식 게임의 "공사 단계"·"업그레이드 단계" 그림에 가장 알맞은 틀입니다.

### 7.1 `life_assets.py` — 레지스트리
```python
@life(key, kind='decor', fp=None, yaw=0.0, shadow=True, samples=64, notes='', front=None, catcher=14.0,
      sprites=None, extra=None)
def b_<key>():
    with L.Collect() as stage0: ...
    with L.Collect() as stage1: ...
    mark('work', (-0.72, -0.28, 0.0), facing=(1.0, 0.25, 0))       # 상호작용 점 (빈 객체)
    every = descendants(stage0.objs + stage1.objs)
    def setter(objs):
        def f():
            show(every, False); show(descendants(objs), True)
        return f
    return {'frames': [('<key>_0', setter(stage0.objs)), ('<key>_1', setter(stage0.objs + stage1.objs))],
            'sprites': {'<key>_0': {'frame': '<key>_0', 'stage': 0}, '<key>_1': {'frame': '<key>_1', 'stage': 1}},
            'rest': None}
```
- 빌더는 로컬 좌표(앞=−Y)로 만들고, `life_render.parent_to_root(yaw)`가 모든 객체를 회전된 루트 empty에 붙임 → setter가 자식들을 로컬 좌표로 계속 움직일 수 있음.
- `mark(kind, loc, parent=None, facing=None)` → 프레임마다 앵커 기준 픽셀 점과 화면 방향(S/SE/…)으로 기록. 종류→매니페스트 필드:
  `seat→seatPoints/seatDirs`, `hide→hidePoints`, `work→workPoints/workDirs`, `gather→gatherPoints`, `door→doorPoint/doorDir`, `pull→pullPoint`,
  `perform→performPoint`, `bulb→fxPoints.bulbs`. 애니 프레임마다 seat가 있으면 `anims.<a>.seatPoints[i]`(그네).
- `sprites` 항목에 `'stage': k`를 넣으면 매니페스트에 `stage`와 `stages`(같은 빌드의 모든 스프라이트 키) 목록이 생김.
  `'anims': {'swing': {'frames': [...], 'fps': 5, 'repeat': -1}}`처럼 프레임 이름을 되풀이해 적은 루프도 가능(그네: 이미지 5장으로 8프레임).
- 예시: `snowman`(눈사람 4단계, 공유 크기 196×180, 앵커 [0.40816,0.63889], 아이들 서는 workPoints), `kids_swing`(진자 루프), `lantern_string`(4프레임 반짝임),
  `log_seat/_x/_y`(같은 통나무를 yaw 45/0/90으로 세 방향), `ice_rink`(kind `decal`, 바닥 층에 그림), `notice_board`(gatherPoints), `dog_house`(doorPoint).
- 공용 도우미: `snow_m`, `snowball`, `snow_drift`, **`roof(name, W, y0, z0, y1, z1, thick, mat, ...)`** — 양쪽 경사 모두 올바른 지붕(아래 함정 참고).

### 7.2 렌더·포장·검사
```bash
/tmp/bvenv/bin/python tools/blender/life_render.py -- --list
/tmp/bvenv/bin/python tools/blender/life_render.py -- --force          # 전체 약 6분 (lantern_string ~130초, kids_swing ~120초, 나머지 2–25초)
/tmp/bvenv/bin/python tools/blender/life_render.py -- snowman kids_swing --force   # 빌드 키 / snowman_2 같은 스프라이트 키도 됨 / 접두어*
python3 tools/blender/life_pack.py      # [--cache DIR] [--quantize auto|on|off] [--no-previews]
python3 tools/blender/life_check.py
# PC: blender -b -P tools/blender/life_render.py -- --force
```
- `fit_frames()`가 모든 상태를 합친 프레임과 공유 앵커를 계산 → 상태 전환 = 프레임 이름만 교체.
- `bench_seats`는 가짜 키: 기존 `prop_assets.b_bench`를 그대로 만들어 좌석 판자 위치를 측정만 함(렌더 없음).
- 캐시 sidecar: `build, kind, atlas('life_props' 하드코딩), frameSize, anchorPx, anchor, frames, shadow, notes, yaw, topPx{프레임별}, framePoints, frameDirs, sprites, footprint, footprintM, front, glow, + extra`.
- `life_pack`: 아틀라스 1장 `ATLAS='life_props'`(≤2048), `--quantize auto`는 예산 `BUDGET_MB=1.5`의 90%를 넘을 때만 팔레트화, 전구 후광 추가,
  매니페스트에 `layouts.campfire_circle`(모닥불 주위 좌석 배치) + `conventions`. 미리보기 `life_props_all.png, life_scene.png(실제 주민을 앉혀 봄), life_anims.gif`.
- `life_check`: `REQUIRED`(하드코딩) 키, 아틀라스 ≤2048, 프레임 존재, 앵커/sourceSize, 좌석 점 형식, 눈사람 단계 크기 공유, 다른 매니페스트와 키 충돌 없음, 용량 ≤ 1.5 MB.

---

## 8. 운영 팁과 함정

1. **캐시는 `/tmp`에 있어서 새 컨테이너에서는 사라집니다.** 이사 후 처음엔 캐시가 비어 있습니다.
   - `char_pack`/`vil_pack`은 키마다 아틀라스를 따로 쓰고 기존 매니페스트 항목을 유지 → **한 명만 렌더하고 포장해도 안전**.
   - `prop_pack`은 시작할 때 `assets/props/props_*`를 **전부 지우고 캐시에 있는 것만** 다시 포장합니다. `life_pack`도 `life_props*`를 지움.
     → 소품을 하나 추가하려면 **먼저 전체 소품을 렌더해 캐시를 채운 뒤**(6–8분) 포장해야 다른 소품이 사라지지 않습니다.
     캐시 폴더가 아예 없으면 지우기 전에 오류로 멈추지만, **폴더가 있고 비어 있으면 `prop_pack`은 막지 않고 아틀라스를 지운 뒤 빈 매니페스트를 씁니다**
     (`life_pack`은 렌더가 없으면 `SystemExit`으로 멈춤). 실수했다면 `git checkout -- assets/props`로 되돌리세요.
2. **이어서 하기**: 모든 렌더 스크립트는 PNG가 있으면 건너뜀(소품은 sidecar JSON + 모든 프레임이 있어야 "cached"). 모형·포즈를 바꿨으면 반드시 `--force`(해당 키만).
3. **결정적**: 고정 시드·고정 샘플 수. 같은 기계에서는 같은 결과.
4. **캐시 이름이 `fv_cache`로 하드코딩**: 새 게임에서 원본(`reference/frost-village`)과 새 게임 도구를 같은 컨테이너에서 둘 다 돌리면 같은 캐시를 씁니다.
   새 게임 쪽은 이름을 바꾸세요: `char_render.py:52`, `char_pack.py:37`, `vil_render.py:46`, `vil_pack.py:45`, `vil_lookdev.py:22` (`/tmp/fv_cache/...`),
   `prop_render.py:40`, `prop_pack.py:594`, `life_render.py:44`, `life_pack.py:310, 631` (`tempfile.gettempdir()/fv_cache/...`). 또는 항상 `--cache`를 넘기기.
5. **하드코딩된 키 목록** (새 키를 추가할 때 같이 고칠 곳):
   - 캐릭터: `char_build.SPECS`, `HUMAN_KEYS`/`ANIMAL_KEYS`, `char_pack.ORDER`(**여기 없으면 포장 안 됨**), `char_check.EXPECTED`/`FRAMES`.
   - 주민: `vil_build.SPECS`, `KEYS`/`PET_KEYS`, 애니 집합(`RUNNERS…`), `vil_dress.DRESS`, `vil_check`의 `RUN/THROW/DANCE/SIT`(독립 표라 따로 고쳐야 함), `vil_pack.SHOWCASE`(GIF 미리보기, 선택).
   - 소품: `prop_assets`에 `@asset`만 추가하면 렌더·포장됨. `prop_pack.KEY_ORDER`는 순서용(없으면 뒤에 이름순).
   - 생활 소품: `@life` 추가로 끝.
   - **검사 스크립트는 전작 명단을 "필수"로 갖고 있습니다**: `char_check.EXPECTED`(11키), `vil_check`(=`vil_build.ALL_KEYS` 20키 전부),
     `prop_check`의 `NATURE/STATIONS/BUILDINGS/DECOR/ITEMS`(53키, 그리고 `docs/CONTRACT.md`의 `## 4.` 절에서 키를 읽어 목록에 없으면 경고),
     `life_check.REQUIRED`. 새 게임에서 전작 그림 일부를 빼면 이 목록들을 **새 계약서의 키로 바꿔야** 검사가 통과합니다.
6. **샘플 수**: 캐릭터 기본 24(보고서 재현은 28), 주민 기본 20(보고서는 24), 소품·생활 소품 64. 낮추면 빨라지지만 노이즈/디노이즈 얼룩.
   빠른 검토 렌더는 `--samples 8 --dirs S --cache <임시>`처럼 따로 캐시를 써서 본 캐시를 더럽히지 않기.
7. **용량 예산**(전작 계약): 캐릭터 8 MB, 주민 10 MB, 소품 5 MB, 생활 1.5 MB. 사람 한 명 아틀라스 약 0.25–0.62 MB(애니 수에 비례).
8. **알려진 문제**: `prop_assets.roof_panel()`은 `y0 > y1`이면 판이 뒤집혀 눈층이 지붕 아래 숨음 → `log_house`의 뒤쪽 지붕(`roofB`)에 눈이 없을 수 있음
   (보고서 lifeprops). 새 건물에는 양방향을 처리하는 `life_assets.roof()`를 쓰거나 `roof_panel`을 고치세요(고치면 기존 집 모습이 바뀜).
9. **bpy 임포트 순서**: bpy를 모듈로 쓸 때는 `mathutils`보다 `bpy`를 먼저 import (prop_assets 주석). 각 스크립트는 `sys.path.insert(0, HERE)` 후 `bl_common` 임포트.
10. **스테이션 프레임은 연기 때문에 큼**(예: 빵 화덕 264×348). 게임은 항상 매니페스트의 `anchor`를 써야 함.
11. **겨울 전용 요소**: 하늘색 환경광(`setup_lighting`의 `ambient`), `snowy()` 재질, `snow_slab/snow_cap`, 지붕 눈, 털 장식(`hem_fur/cuff_fur/boot_fur`).
    새 게임이 겨울이 아니라면 계약서 단계에서 한 번 정하고 **모든 그림을 같은 설정으로** 다시 렌더해야 섞여도 어색하지 않습니다(전체 약 70분).

---

## 9. 새 프로젝트에서 재사용하는 법

### 9.1 무엇을 복사하나
- 도구: `tools/blender/*.py` 전부 + `tools/pack_utils.py` → 새 게임 루트의 같은 위치(`game/tools/...`). 경로는 `__file__` 기준이라 그대로 동작.
  `__pycache__`는 제외. (FX/UI/바닥/소리 도구는 04번 문서)
- 기존 그림을 그대로 쓸 거면 `assets/characters`, `assets/villagers`, `assets/props`, `assets/life_props`(+매니페스트)도 복사.
  다시 렌더할 거면 도구만 복사해도 됩니다.
- 참고 문서: `docs/CONTRACT.md`, `docs/CONTRACT_VILLAGERS.md`, `docs/build_reports/*.json`(새 저장소에서는 `docs/reference/`).

### 9.2 무엇을 바꾸나
1. **새 계약서**를 먼저 씁니다(`CONTRACT.md` 형식 그대로: 투영·PPU·앵커·매니페스트·키 이름). 투영/PPU/조명은 **그대로 두는 것을 권장**.
2. 캐시 이름(8장 4번), 미리보기 제목의 "Frost Village" 문구(선택), `pack_utils.py`의 `meta.app` 문자열(선택).
3. 새 키는 8장 5번의 목록에 추가하고, 검사 스크립트의 필수 명단을 새 계약서 기준으로 교체. 계절·팔레트가 바뀌면 `prop_lib.PAL`, 각 `SPECS` 색, 필요하면 `setup_lighting`의 인자(모든 그림 공통으로).
4. 새 게임 코드가 읽을 매니페스트 폴더를 `Assets.js`의 `FRAGMENTS`에 등록(05번 문서).

### 9.3 바꾸지 말아야 할 것과 이유
- `PPU=64`, 카메라 30°/45°, `RENDER_DIRS`, 앵커 규칙(128×128의 (64,104), 아이템 72×72의 (36,54)), 조명 기본값.
  이유는 10.5 참고. 바꾸면 **모든** 그림을 다시 렌더하고 게임의 모든 픽셀 수치(carryPoint, impactPoint, footprint, stackStep, 울타리 간격, 월드 배치)를 다시 맞춰야 합니다.

---

## 10. 확장 레시피

### 10.1 새 캐릭터 (새 옷 + 새 표정)
표정이 필요하면 **주민 파이프라인(vil_*)**이 맞습니다(얼굴 부품 교체 지원). 도구 작업 애니가 중요하면 캐릭터 파이프라인(char_*)이 이미 갖춰져 있습니다(10.1-B).

**A. 주민 파이프라인으로 (예: `npc_builder`, 새 표정 `starry`)**
1. `vil_build.py`의 `SPECS`에 항목 추가: `name=('목수 민수','Builder'), role='adult', traits=[...], body='strong'` + 색·얼굴 파라미터·`shadow`.
   `KEYS`에 키 추가. 필요한 애니 집합(`RUNNERS` 등)에 넣기.
2. `vil_dress.py`에 `def dress_builder(rig, spec):` 작성 — `cb.hair_shell`, `cb.cap_shell`, `cb.tilted_ring`, `sector_lathe`(앞치마), `cb.belt`,
   `g.mesh_obj(..., rig.j['spine'|'head'|'hand_R'])`로 옷·모자·소품을 붙임(예시는 `dress_blacksmith`). `DRESS['npc_builder'] = dress_builder`.
   손에 드는 소품은 `rig.toggle('hammer', [obj])`로 등록하고 포즈에서 `p.update(face('neutral', {'hammer'}))`처럼 프레임마다 켬(`throw`의 `snowball`과 같은 방식).
3. 새 표정 부품: `vil_face.build_face()` 안에서 다른 부품처럼 `_obj(rig, '이름', bm_blob(...)/bm_stroke(...), 재질)`로 만들고
   `add('eye_star', objs)`로 등록. `vil_anim.FACES`에 `'starry': ['eye_star', 'brow_up', 'm_grin', 'cheek_blush']` 추가.
   애니 함수에서 `p.update(face('starry'))`.
4. `vil_check.py`의 `RUN/THROW/DANCE/SIT` 표에도 같은 키를 반영(애니를 줬다면).
5. 실행:
   ```bash
   /tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars npc_builder --lookdev --faces neutral,happy,starry   # 표정 먼저 확인
   python3 tools/blender/vil_lookdev.py --keys npc_builder --faces neutral,happy,starry --out docs/previews/vil_builder_faces.png
   #  (vil_lookdev 는 --cache 를 받지 않고 /tmp/fv_cache/villagers/_lookdev 를 읽음; 없는 표정 칸은 비워 둠)
   /tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars npc_builder --samples 24 --portraits          # 약 1–5분
   python3 tools/blender/vil_pack.py --chars npc_builder && python3 tools/blender/vil_check.py
   ```
   그리고 `docs/previews/vil_npc_builder.png`를 **직접 열어 눈으로 확인**.

**B. 캐릭터 파이프라인으로 (도구 작업 애니가 있는 일꾼, 예: `stonecutter`)**
1. `char_build.py`: 도구 함수(예: `make_hammer`를 `make_pickaxe` 복사로 시작, 끝에 `fx_marker(rig, 'hammer', t, (...))`), `dress_stonecutter(rig, spec)`,
   `SPECS['stonecutter']=dict(coat=..., dress=dress_stonecutter, ...)`, `HUMAN_KEYS`에 추가.
2. `char_anim.py`: `work_pose()`에 분기(`keyed(_tool_swing_keys('hammer', low=True), i)` 재사용 가능), `WORK_IMPACT['stonecutter']=5`.
   `char_render.IMPACT_TOOL`에 `'stonecutter': 'hammer'` 추가(impactPoint 계산용).
3. `char_pack.ORDER`, `char_check.EXPECTED`에 추가.
4. 실행: `char_render.py -- --chars stonecutter --portraits` → `char_pack.py --chars stonecutter` → `char_check.py`.

> 주민 파이프라인에는 아직 도구 작업 애니(`work`)와 그 impactPoint 계산이 없습니다(`vil_render.write_meta`는 `throw`만 처리).
> 표정 있는 일꾼이 필요하면 `vil_anim.ANIMS/HUMAN_ORDER/HUMAN_FN`에 `work`를 추가하고, `write_meta`에 `char_render.impact_points`와 같은 계산을 넣으면 됩니다.

### 10.2 새 건물 + 작업 애니 + 여러 업그레이드 단계
**방법 1 (지금 그대로 가능): 소품 파이프라인의 스테이션** — `prop_assets.py` 안에 추가한다고 가정(`math`, `L`, `cyl`, `flat`, `log_house` 이미 있음).
```python
@asset('bld_sawmill_t1', 'station', 'props_buildings', fp=(2.83, 2.83), work=4, fps=10, front='-Y', catcher=18.0,
       notes='제재소 1단계. work = 톱날 회전.')
def b_bld_sawmill_t1():
    log_house(2.4, 2.0, 1.55, 2.75, seed=3, windows=((0.0, 'x+'),))     # 공유 서브모델 재사용
    parts = [cyl('disc', 0.45, 0.035, (0, 0, 0), rot=(90, 0, 0), mat=flat('steel', 0.28, 0.85), segs=48,
                 origin='center', bevel=0.008)]
    # 회전이 보이려면 구멍·톱니 같은 무늬가 꼭 있어야 함. b_station_sawmill은 구멍 4개 → 22.5°씩 4프레임이 이음매 없이 반복.
    blade = L.group(parts, 'blade', loc=(1.6, -0.6, 0.9))               # 빈 객체에 묶어서 그 객체를 돌림
    def idle():
        blade.rotation_euler.y = 0.0
    def work(i):
        blade.rotation_euler.y = math.radians(-22.5 * i)
    idle()
    return {'work': work, 'idle': idle, 'fx': {'blade': (1.6, -0.6, 0.9)}}
```
(톱밥은 `L.Spray`, 연기는 `L.Smoke`, 불은 `L.Flames` — 사용 예는 `b_station_sawmill`, `b_station_grill`)
단계별로 `bld_sawmill_t2`, `_t3`를 따로 등록(서브모델 인자만 바꿈). 단점: 단계마다 프레임 크기·앵커가 달라짐(게임은 매니페스트 앵커를 쓰면 되므로 동작은 함).
`prop_render.py -- bld_sawmill_* --force` → (전체 캐시가 있는 상태에서) `prop_pack.py` → `prop_check.py`.

**방법 2 (권장, 복사 작업 필요): 생활 소품 틀로 "건물 빌드" 파이프라인 만들기**
여러 단계(공사 단계 + 업그레이드 단계 + 단계별 작업 프레임)를 **한 빌드에서 공유 앵커로** 내려면 7장의 `frames/sprites` 기능이 맞습니다.
1. `life_assets.py` → `bld_assets.py`로 복사: `life/mark/show/descendants/LIFE/MARKERS`와 공용 도우미는 남기고 눈 소품 빌더는 삭제.
2. `life_render.py` → `bld_render.py`: `import life_assets as LA` → `import bld_assets as LA`, 캐시 경로, sidecar의 `'atlas': 'life_props'`를 새 아틀라스 이름으로.
3. `life_pack.py` → `bld_pack.py`: `OUT`, `ATLAS`, `BUDGET_MB`, 캐시 경로, 미리보기 이름 변경; `bench_seats`·`layouts`·전구 후광·주민 앉히기 미리보기 같은 생활 소품 전용 부분 정리.
   아틀라스가 2048을 넘으면 `prop_pack._chunks`처럼 나누는 기능을 가져와야 함(life_pack은 한 장만 지원).
4. `life_check.py` → `bld_check.py`: `REQUIRED`, 예산 변경.
5. 빌더에서 작업 프레임은 `frames`에 `('bld_sawmill_t2_work_0', setter_work(0))`처럼 추가하고, `sprites['bld_sawmill_t2'] = {'frame': ..., 'stage': ..., 'anims': {'work': {'frames': [...], 'fps': 10, 'repeat': -1}}}`.
이 방법은 아직 만들어지지 않았습니다(재료는 모두 있음). 11.1에 구체적인 단계 설계가 있습니다.

**건물 방향**: 격자에 맞춘 건물은 `yaw=0`(문이 화면 왼쪽 아래, 전작 통나무집 기준) 또는 `yaw=90`(문이 오른쪽 아래). `yaw=45`면 카메라 정면이지만 격자와 45° 어긋남.

### 10.3 새 아이템
```python
@asset('item_hammer', 'item', 'props_items', item={'thickness': 0.12}, notes='망치 (도구). 바닥에 눕힘, 머리가 화면 오른쪽.')
def b_item_hammer():
    L.cyl('handle', 0.035, 0.6, (0, 0, 0.04), rot=(0, 90, 0), mat=L.flat('wood_light', 0.7), origin='center')
    L.box('head', (0.12, 0.26, 0.12), (0.3, 0, 0), mat=L.flat('iron', 0.4, 0.7), bevel=0.02)
```
- 바닥에 눕혀 두툼하게(32–48 px에서도 읽히게). 72×72 프레임을 넘으면 렌더 때 `WARNING item ... exceeds item frame` 출력 → 크기를 줄임.
- `stackStep`은 두께로 자동(`round(t*0.866*64)`), `carryScale`은 포장 때 자동 측정. UI 아이콘으로도 같은 그림 사용(`icon: true`).
- 실행: (소품 캐시가 차 있는 상태에서) `prop_render.py -- item_hammer --force` → `prop_pack.py` → `prop_check.py`. `docs/previews/props_items.png`, `props_carry.png` 확인.

### 10.4 다른 방향 세트 렌더
- 사회적 애니처럼 **방향을 줄이기**: 주민은 애니마다 `dirs`를 가짐(`vil_anim.ANIMS[..]['dirs']`). 렌더·포장·매니페스트가 자동으로 따름.
- **반전 없이 8방향 모두**(비대칭 캐릭터·글자): `bl_common.DIR_YAW`에 8방향 값이 이미 있음. 캐릭터는 `RENDER_DIRS`(char_render/vil의 dirs) 목록에
  `SW, W, NW`를 추가하고, `char_pack.DIRS`/`MIRROR`(또는 vil_pack)와 매니페스트 `dirs`/`mirror`를 맞추고, check 스크립트의 방향 가정도 수정.
  프레임 수와 용량이 1.6배. 게임 쪽이 `mirror`에 없는 방향을 그대로 찾는지 05번 문서로 확인.
- **UI용 한 방향**(초상화처럼): `char_extras.ui_camera(w, h, ppu, target, elev_deg=15, yaw_deg=45, anchor_px)`를 쓰는 별도 함수.
- 소품은 방향 개념 대신 `yaw` 값을 다르게 한 별도 키(예: `log_seat`(45) / `log_seat_x`(0) / `log_seat_y`(90)).

### 10.5 PPU·카메라를 바꾸려면 (그리고 왜 바꾸지 말아야 하나)
- 바꾸는 곳은 `bl_common.PPU`, `CAM_ELEV_DEG`, `CAM_YAW_DEG` 한 곳뿐이지만, 영향은 전부입니다:
  모든 그림 재렌더(약 70분), `prop_pack.tile_shadow`의 하드코딩 상수 `45.2548/22.6274`, `life_pack` 미리보기 배치, 바닥 텍스처(04번), 게임의 모든 px 수치
  (carryPoint·impactPoint·footprint·stackStep·울타리 간격·`src/data/world.js` 배치), 그리고 폰에서 읽히도록 맞춘 얼굴 크기(약 80 px 캐릭터).
- 고도를 바꾸면 2:1 마름모가 깨져 바닥 그림·격자 수학이 모두 틀어집니다.
- 일꾼을 작게 많이 보여주고 싶다면(세틀러 느낌) **그림은 그대로 두고 게임 카메라 줌**(예: 0.6–0.8)으로 먼저 시험해 보세요.
  줌 0.6이면 캐릭터 약 48 px이고 1px 외곽선은 흐려집니다 → 목업 스크린샷을 먼저 만들어 대표님께 확인받은 뒤 결정.
  정말 바꿔야 한다면 새 프로젝트 **첫날** 계약서에서 정하고 재사용 그림을 전부 새 값으로 다시 렌더합니다.

---

## 11. 세틀러식 게임에 새로 필요한 그림과 만드는 법

아래는 **아직 만들지 않은 것**이며, 위 도구로 만드는 권장 방법입니다.

### 11.0 격자(칸) 설계 — 먼저 정할 것
- 투영 계산상 칸 한 변을 **√2 m(≈1.4142 m)**로 하면 축 방향 한 칸이 화면에서 정확히 (+64, +32) / (+64, −32) px → **128×64 px 마름모**,
  칸 한 변을 √2/2 m(≈0.7071 m)로 하면 64×32 px 마름모. 정수 픽셀이라 길·영토 타일이 이음매 없이 맞습니다.
  (전작의 1 m 울타리는 45.25 px, 1.5 m 밭은 67.88 px 간격이라 소수 픽셀)
- 건물 바닥 면적(`fp`)을 칸 수의 배수로 잡습니다(예: 작은 건물 2×2칸 = 2.83 m × 2.83 m).
- 크기 감각: 사람은 약 80 px 높이, 바닥 그림자 타원 46×18 px → 128×64 칸 하나에 사람이 여유 있게 들어갑니다.

### 11.1 공사 단계 프레임 (부지 → 기초 → 비계 → 완성)
- **10.2 방법 2**(건물 빌드 파이프라인)로 한 빌드에 단계를 모두 넣습니다. 예: `bld_woodcutter_c0..c3` + 완성 `bld_woodcutter`.
  - c0 부지: 말뚝 4개 + 줄 + 평평하게 고른 흙(`box` 얇게, `tonal('soil')`).
  - c1 기초: 돌 기초(`stone_ring` 또는 `box` 줄), 쌓아 둔 재료 더미(통나무/판자 `log_pile`, 아이템 모델 재사용).
  - c2 벽 절반 + 비계: `log_house`를 직접 쓰지 말고 통나무 줄 수를 인자로 받는 복사본(벽 높이 비율)으로 아래 줄만, 나무 기둥·가로대로 비계.
  - c3 지붕틀: 서까래만(지붕판 없음).
  - 완성: 전체. 모든 단계가 **같은 frameSize·anchor**를 공유(`fit_frames`) → 게임은 진행도에 따라 프레임만 교체.
- `mark('work', ..., facing=...)`로 일꾼이 서서 망치질할 점 2–3개 → `workPoints/workDirs`. 재료 내려놓는 점은 `mark('drop', ...)`처럼 새 종류를 만들 수 있으나
  `life_pack`의 `POINT_FIELDS`에 새 종류를 추가해야 매니페스트에 나옵니다.
- 망치질하는 건설 일꾼: 10.1-B로 `builder` 키 + `make_hammer` + `_tool_swing_keys('hammer')` → `impactPoint`로 먼지·나뭇조각 FX와 소리 동기화.
- 업그레이드 단계(t1/t2/t3)도 같은 빌드에 넣고, 바닥 면적과 앵커(바닥 중심)를 단계끼리 같게 유지하면 그 자리에서 교체됩니다.

### 11.2 길과 깃발
- **길**(바닥 층, 그림자 없음): 두 가지 방법.
  1. Blender: 얇은 흙길 메시(`box`/`extrude` + `tonal('soil')` + 작은 자갈 `blob`)를 `shadow=False`, `kind='decal'`로 렌더(생활 소품 `ice_rink`와 같은 바닥층 처리).
     조각: X축 직선 1칸, Y축 직선 1칸, 깃발 자리 원형 마당. 칸 경계에서 **양 끝은 불투명하게 똑 자르고 옆 가장자리만 부드럽게** — 반투명 끝이 겹치면 이음매가 진해집니다
     (불가피하면 울타리의 `tile_shadow`처럼 합이 1인 가중치로 나누기).
  2. numpy 절차 생성: 04번 문서의 바닥 데칼 도구(`tools/fx/gen_ground.py`)로 128×64 마름모 타일을 직접 그림. 픽셀 단위로 이음매를 보장하기 쉬움.
- **깃발**(길의 마디): 작은 소품 `@asset('road_flag', 'decor', ..., fp=('r', 0.2), work=4, fps=8)` — `work(i)`로 천이 펄럭이는 4프레임.
  플레이어 색이 필요하면 **천만 흰색으로 따로 렌더**해서 게임에서 `setTint(색)`(Phaser tint는 곱하기라 흰색일 때 정확)하고,
  기둥 프레임에는 천을 `visible_camera=False`로 두어 **그림자만** 남깁니다(울타리 이웃 구간과 같은 기법). 두 프레임이 같은 앵커를 쓰도록 한 빌드에서 렌더.
  주의: `prop_lib.frame_fit()`은 카메라에 보이는 객체만 셉니다(`scene_meshes()`가 `visible_camera`로 거름) → 그림자만 남긴 천의 그림자가 프레임 밖으로
  나갈 수 있으니 `frame_fit(objs=...)`에 천을 포함시키거나 여백을 늘리세요.

### 11.3 짐꾼 (길 위에서 물건 나르기)
- 짐꾼 = idle, walk, carry_idle, carry_walk(+ 내려놓기/집기 한 번짜리)만 있는 캐릭터. `char_*` 일꾼 틀(carry_idle 포함)이 가장 가깝습니다.
  집기/내려놓기는 `char_anim.human_harvest`(쪼그려 집기)를 바탕으로 한 6프레임 한 번짜리를 추가(`HUMAN_ANIMS`·`pose_for`·`anims_for`·`char_check`에 등록;
  `char_pack.LOOP_ANIMS`에 넣지 않으면 매니페스트에 `repeat: 0`으로 나감).
- **물건 그림을 캐릭터에 구워 넣지 않습니다.** 게임이 `carryPoint[dir]`에 아이템 스프라이트를 `carryScale`로 그리고, NE/N은 `behind=true`라 몸 뒤에 그립니다.
  → 짐꾼 1명 아틀라스 + 아이템 N종으로 모든 조합이 나옴. 세틀러식 "물건 한 개 나르기"는 쌓기 개수 1로 두면 됨.
- 어깨에 메는 자세를 원하면 `char_anim`에 `carry_shoulder` 포즈 추가 + `char_render.carry_points`처럼 어깨 위 점을 계산하는 함수 추가.
- 많은 일꾼이 동시에 보이므로: 사람 1명 아틀라스 약 0.25–0.6 MB, 텍스처가 많아지면 묶음 그리기(batch)가 끊기니 짐꾼처럼 수가 많은 캐릭터는 애니를 최소로.

### 11.4 영토 경계 말뚝
- 작은 소품(높이 약 0.8–1.0 m, `fp=('r', 0.15)`): 나무 말뚝 + 색 띠/작은 깃발. 플레이어 색은 11.2의 흰색 천 + `setTint` 방식.
- 경계선을 따라 수십 개가 놓이므로 그림은 작게, 변형 2–3개(`seed`만 다르게)면 충분. 그림자는 구워도 됨(반전하지 않으므로).

### 11.5 그 밖에 생길 그림
- 도구 아이템(망치·도끼·톱·곡괭이·낫·낚싯대 — "도구가 있어야 직업이 생김"): 10.3 레시피. 손에 든 도구 모형(`make_axe` 등)은 리그가 필요하므로 아이템용은 단순 모형으로 따로.
- 새 원자재/식량(돌, 석탄, 금, 밀가루, 물 …): 10.3 레시피. 광산 음식(생선·빵·고기)은 이미 있음(`item_fish_cooked, item_bread, item_meat_cooked`).
- 자원별 광산 입구: `b_mine_entrance`(yaw 45, 카메라 정면) 복사 후 광석 색만 변경.
- 가축(양·돼지·당나귀): `char_animals.py`(사슴·멧돼지) 또는 `vil_pets.py`(개·고양이) 틀 + `char_anim.animal_walk/idle`.
- 대략 렌더 시간 감각: 일꾼 1명(5애니 160프레임) 약 35–75초, player(230프레임) 약 110초, 주민형(애니 많음, 256–344프레임) 약 1–5분, 아이템 1개 1초 미만, 건물 1개 15–40초(연기·불 있는 스테이션은 최대 약 80초).

---

## 12. 명령 빠른 참조

```bash
cd <게임루트>
# ── 캐릭터
/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars all --samples 28 --portraits --keyart   # ~12분, 재개 가능
python3 tools/blender/char_pack.py [--chars k] [--no-previews] [--cache DIR]
python3 tools/blender/char_check.py
# ── 주민·펫
/tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars all --samples 24 --portraits             # ~40분
python3 tools/blender/vil_pack.py [--chars k] [--colors 192|256] [--no-previews]                      # ~2분
python3 tools/blender/vil_check.py
/tmp/bvenv/bin/python tools/blender/vil_render.py -- --chars a,b --lookdev && python3 tools/blender/vil_lookdev.py --keys a,b
# ── 소품·건물·아이템
/tmp/bvenv/bin/python tools/blender/prop_render.py -- --list                                          # 키 목록
/tmp/bvenv/bin/python tools/blender/prop_render.py -- [키... | 아틀라스 | 접두어*] [--force] [--samples N] [--cache DIR]   # 전체 6–8분
python3 tools/blender/prop_pack.py [--no-previews] [--quantize] [--cache DIR]      # 주의: 캐시에 있는 것만 남김
python3 tools/blender/prop_check.py
# ── 생활 소품
/tmp/bvenv/bin/python tools/blender/life_render.py -- --list
/tmp/bvenv/bin/python tools/blender/life_render.py -- [키...] [--force] [--samples N] [--cache DIR]  # 전체 ~6분
python3 tools/blender/life_pack.py [--quantize auto|on|off] [--no-previews] [--cache DIR]
python3 tools/blender/life_check.py
# ── PC (Blender 4.2+, 5.2 권장): 위 /tmp/bvenv/bin/python 을 "blender -b -P" 로 바꾸고, --cache 를 명시
blender -b -P tools/blender/char_render.py -- --chars player --cache C:/fv_cache/characters
python tools/blender/char_pack.py --cache C:/fv_cache/characters      # numpy + Pillow + imagequant
```

| 산출물 | 위치 |
|---|---|
| 원본 프레임 캐시 | `/tmp/fv_cache/{characters,villagers,props,life_props}/` (+ 로그 `render_all.log`, `vil_render_all.log`, `props/render*.log`, `life_props/render.log`) |
| 게임용 그림 | `assets/characters/`, `assets/villagers/`, `assets/props/`, `assets/life_props/` (각 `manifest.json`) |
| 미리보기 | `docs/previews/char_*`, `vil_*`, `props_*`, `life_*` |
| 제작 보고서 | `docs/build_reports/characters.json`, `villagers.json`, `props_run1.json`, `props_run2.json`, `lifeprops.json` |
| 계약서 | `docs/CONTRACT.md` (§1 투영·팔레트, §2 매니페스트, §3 캐릭터, §4 소품), `docs/CONTRACT_VILLAGERS.md` (A 주민, B 생활 소품, C 이모티콘) |
