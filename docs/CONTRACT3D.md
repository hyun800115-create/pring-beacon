# 봄날의 행진 — 3D 에셋 계약서 (v1, 2026-10-07)

3D 게임(three.js)과 Blender 에셋 도구가 서로 맞물리기 위한 규칙. 키 이름·노드 이름은 여기서만 정한다.

## 1. 공통
- 단위 **미터**. Blender 는 +Z 위. glTF 로 내보내면 three.js 에서 +Y 위 (Blender (x, y, z) → glTF (x, z, -y)).
- 원점 = **발자국(바닥) 가운데, 땅 높이 z = 0**.
- 건물 정문은 Blender **-Y 쪽**을 본다 (= 게임에서 모델의 +Z 쪽). 게임이 건물을 돌려 놓는다.
- 그림체: 서리마을과 같은 장난감 같은 부드러운 3D 치비 스타일. 두툼한 모서리(베벨), 통나무·판자, 눈 덮인 지붕, 따뜻한 색.
  서리마을 도구(`game/tools/blender/prop_lib.py`, `prop_assets.py`, `life_assets.py`, `bl_common.py`)의 함수와 색을 최대한 재사용한다.
- 재질: **단색 Principled 재질만** 쓴다 (계산 무늬·텍스처 노드 금지 → glTF 로 옮길 때 사라진다).
  나무결 느낌은 판자·통나무를 여러 개로 나누고 색을 조금씩 다르게 해서 낸다. 빛나는 것(창문 불빛, 화덕 불)은 Emission 사용 가능.
- 가벼움: 건물 하나(실내 포함) 삼각형 6만 개 이하, 재질 30개 이하. 가구 하나 삼각형 3천 개 이하.
- 같은 재질·같은 묶음(아래 노드 이름)끼리는 메쉬를 합친다 (그리기 횟수 줄이기).
- 내보내기: `bpy.ops.export_scene.gltf(export_format='GLB', export_yup=True, export_apply=True)` 전에 반드시 `bpy.context.view_layer.update()` 로 부모-자식 위치를 계산한 뒤 합칠 것.

## 2. 건물 GLB — `game/assets3d/buildings/<key>.glb` + `<key>.json`
최상위 노드(이름 정확히):
| 노드 | 내용 | 게임 동작 |
|---|---|---|
| `roof` | 지붕 전체(눈 포함), 굴뚝 윗부분 | 실내 보기 때 숨김 |
| `walls` | 바깥벽 전체 높이(창문·문틀 포함) | 실내 보기 때 숨김 |
| `walls_low` | 바깥벽의 아래 0.5m 만 (잘린 단면) | 실내 보기 때만 보임 (평소 숨김) |
| `iwalls` | 실내 칸막이벽 전체 높이 | 실내 보기 때 숨김 |
| `iwalls_low` | 실내 칸막이벽 아래 0.5m | 실내 보기 때만 보임 |
| `floor` | 바닥(마루), 문턱, 계단 | 항상 보임 |
| `interior` | 가구·소품 전부 | 항상 보임 (지붕·벽에 가려짐) |
| `exterior` | 바깥 장식(통·장작더미·간판·현관 지붕 등) | 항상 보임 |
| `anim_*` | 움직이는 부품(예: `anim_blades` 풍차 날개, 회전축 = 노드 원점, 도는 축 = 노드 로컬 Y(Blender)) | 게임이 돌린다 |
| `fx_*` | 빈 객체: 불(`fx_fire`), 연기(`fx_smoke`), 불빛(`fx_light`) 위치 | 효과 위치 |

**상호작용 자리(빈 객체)**: 이름 `slot.<동작>.<번호>` (예: `slot.sit.1`, `slot.sleep.2`).
- 위치 = 주민 발이 놓일 곳(앉기는 엉덩이 높이가 아니라 의자 앞 바닥, 침대는 침대 위 몸 가운데). 방향 = 빈 객체의 Blender -Y 가 주민이 바라보는 쪽.
- 동작 이름: `sit`(의자·벤치), `sleep`(침대), `eat`(식탁 앉기), `read`(책상·책장 앞), `cook`(화덕·조리대 앞 서기), `bake`(빵 화덕), `work`(작업대 서기), `desk`(사무 책상 앉기), `toilet`, `wash`(세면대), `tea`(차 마시기 앉기), `chat`(서서 이야기), `shop`(가게 손님 서기), `sell`(가게 주인 서기), `pray`, `play`(아이), `warm`(난로 앞).
- 각 자리 빈 객체에 커스텀 속성 `room` = 방 이름(한국어).

**문**: 빈 객체 `door.out`(정문 바깥 바닥, 길이 닿는 곳), `door.in`(정문 안쪽 바닥).

**JSON 사이드카** `<key>.json`:
```json
{ "key": "hall", "name": "마을회관", "size": [8.0, 6.0], "height": 6.5,
  "rooms": [ { "name": "사무실", "center": [x, y], "size": [w, d] } ],
  "slots": [ { "id": "slot.sit.1", "action": "sit", "room": "회의실", "pos": [x, y, z], "yaw": deg } ],
  "door": { "out": [x, y], "in": [x, y] }, "levels": 1 }
```
좌표는 Blender 좌표(x, y, z) 미터, yaw = Blender Z축 회전(도, 0 = -Y 를 봄).

## 3. 건설 단계
게임이 비계(나무 기둥·발판)와 재료 더미를 직접 만들고, 건물 모델을 아래에서 위로 잘라 보여 준다. 그래서 에셋은 **완성 모습 한 벌**이면 된다.
선택: `<key>_frame.glb` (뼈대만, 기둥·보) 가 있으면 공사 중간 단계에 보여 준다.

## 4. 가구 GLB — `game/assets3d/furniture/<key>.glb`
원점 = 바닥 가운데, 정면 -Y. 같은 `slot.*` 규칙 사용(가구 하나에 자리가 붙어 있을 수 있음).
최소 목록: `chair`, `stool`, `bench_in`, `table_round`, `table_long`, `bed_single`, `bed_double`, `crib`, `stove`(무쇠 난로), `hearth`(벽난로),
`kitchen_counter`, `cupboard`, `bookshelf`, `desk`, `sofa`, `rug_round`, `rug_long`, `lamp_floor`, `toilet`, `sink`, `bathtub`,
`wardrobe`, `plant_pot`, `tea_set`(탁자 위 소품), `bread_shelf`, `shop_counter`, `barrel_in`, `crate_in`, `meeting_table`, `notice_board_in`.

## 5. 첫 건물 목록 (분류)
| 분류 | 키 | 이름 | 실내 |
|---|---|---|---|
| 공공 | `hall` | 마을회관 | 사무실, 회의실, 화장실, 식당(부엌 포함), 현관 홀 |
| 주택 | `house_1` | 오두막 | 방 하나: 침대 2, 식탁, 난로, 작은 부엌 |
| 주택 | `house_2` | 큰 오두막 | 침실, 부엌·거실 |
| 주택 | `house_3` | 통나무집 | 침실 2, 부엌, 거실, 화장실 |
| 생산 | `woodcutter` | 나무꾼 작업장 | 작은 헛간(도구 걸이, 작업대) + 바깥 장작 패는 그루터기 |
| 생산 | `quarry` | 채석장 | 도구 헛간 + 바깥 돌무더기 |
| 생산 | `sawmill` | 제재소 | 지붕만 있는 작업장, 톱 작업대 |
| 생산 | `farm` | 밀 농장 | 헛간: 건초, 도구, 작은 침상 |
| 생산 | `windmill` | 풍차 | 1층 맷돌·밀가루 자루, `anim_blades` |
| 생산 | `bakery` | 빵집 | 빵 화덕, 반죽대, 손님 계산대, 빵 진열대 |
| 상업 | `tavern` | 선술집 | 술통, 바 카운터, 식탁들, 벽난로 |
| 상업 | `shop` | 잡화점 | 진열대, 계산대, 상자 |
| 공공 | `well` | 우물 | 실내 없음 |
