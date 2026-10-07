# CLAUDE.md — 세틀러식 새 게임 프로젝트 (서리마을 도구 이어받음)

## 사용자 (가장 중요)
- 사용자는 **한국인 인디게임 기획자**이고 코딩을 모른다. 사용자는 아이디어와 기획을 주고, Claude가 기획·아트·사운드·코드·테스트·배포를 알아서 한다.
- **모든 설명은 한국어로만**, 쉬운 말로 한다. 영어 용어를 섞지 말고, 꼭 필요하면 한국어로 풀어서 쓴다. (사용자가 영어 섞인 답에 불편해했다.)
- 결과는 그림(미리보기 이미지·스크린샷)과 **휴대폰으로 바로 해볼 수 있는 플레이 링크**로 보여준다. 사용자는 디자인을 아주 좋아했다(장난감 같은 부드러운 3D 치비 스타일 유지).
- 사용자가 "잠시만"이라고 하면 새 작업을 시작하지 말고 멈춰서 의논한다. 큰 방향 결정(게임 방식, 범위)은 추천안을 주고 사용자에게 정하게 한다.

## 이 저장소
- 새 게임: 세틀러(The Settlers)식 마을 건설·경영 게임. 기획 초안은 `docs/handoff/07_세틀러식_새게임_기획초안.md`.
- `reference/frost-village/` = 전작 "서리마을 개척기" 전체(실행 가능한 원본). **도구·에셋의 원본 저장소**이므로 고치지 말고, 필요한 걸 새 게임 폴더로 복사해서 쓴다.
- 새 게임은 새 폴더(예: `game/`)에 만든다. 도구는 `reference/frost-village/tools/` 를 `game/tools/` 로 복사하면 그대로 동작한다(도구는 자기 위치 기준 `../..` 을 게임 루트로 보고 `assets/` 에 출력한다).
- 문서: `docs/handoff/01~07` (작업 방식, 도구, 파이프라인, 교훈, 새 기획), `docs/reference/` (전작 계약서 `CONTRACT.md`, `CONTRACT_VILLAGERS.md`, 기획서, 제작 보고서 `build_reports/*.json`, 미리보기).

## 환경 설정 — 윈도우 PC (`C:\시라이스`, 2026-10-07 설정 완료)
이 저장소는 이제 **대표님 윈도우 PC**에서 돌린다. 키트의 리눅스 명령(`/tmp/...`, `python3`)은 아래처럼 바꿔 쓴다.
모든 설치물·임시 파일은 저장소 안 **`.cache/`** 폴더에 둔다(git 에 올리지 않음, `.gitignore`).

| 키트(리눅스) | 이 PC(윈도우) |
|---|---|
| `/tmp/bvenv/bin/python` (bpy) | `.cache\venv\Scripts\python.exe` |
| `/tmp/fv_audio_venv` (scipy) | 같은 `.cache\venv` 하나로 합침 |
| `python3` (시스템 파이썬) | `.cache\venv\Scripts\python.exe` (PC 기본 `python` 은 3.9 32비트라 쓰지 않는다) |
| `/tmp/fv_cache/...` (렌더 원본 프레임) | `.cache\fv_cache\...` (환경변수 `FV_CACHE` 로 바꿀 수 있음) |
| `/tmp/fv_review/...` (검수 결과) | `.cache\fv_review\...` (환경변수 `FV_REVIEW`) |
| 시스템 ffmpeg | `.cache\bin\ffmpeg.exe` (libvorbis·libmp3lame 포함) |
| 전역 Playwright, `/opt/pw-browsers` | 저장소 루트 `node_modules\playwright` + `.cache\pw-browsers` |

다시 설치할 때(새 PC 이거나 `.cache` 를 지웠을 때), 저장소 루트에서 Git Bash 로:
```bash
export UV_CACHE_DIR=.cache/uv
uv python install 3.13 && uv venv --python 3.13 .cache/venv
uv pip install --python .cache/venv/Scripts/python.exe bpy==5.2.2 numpy pillow imagequant scipy static-ffmpeg
.cache/venv/Scripts/python.exe -c "import static_ffmpeg.run as r; print(r.get_or_fetch_platform_executables_else_raise())"
mkdir -p .cache/bin && cp .cache/venv/Lib/site-packages/static_ffmpeg/bin/win32/*.exe .cache/bin/
npm install                                                   # 루트 package.json → playwright
PLAYWRIGHT_BROWSERS_PATH=.cache/pw-browsers npx playwright install chromium
(cd game/tools/build && npm install)                          # 배포 번들러(esbuild)
```
- 설치된 버전: Python 3.13.14, bpy 5.2.2 (Cycles CPU), numpy 2.5, Pillow 12.3, scipy 1.18, Node 24, Playwright 1.63. CPU 16코어.
- 도구는 `game/tools/` 에 복사해 두었고, 거기서 `/tmp` 경로를 `.cache` 로 고쳤다(`reference/` 원본은 그대로).
  고친 곳: `blender/*_render.py`·`*_pack.py`·`vil_lookdev.py`·`char_extras.py`(`FV_CACHE`), `test/review_*.mjs`(`FV_REVIEW`),
  `audio/deps.py`(`.cache/venv` 와 `.cache/bin` 의 ffmpeg 자동 사용), `test/pw.mjs`(`.cache/pw-browsers` 자동 사용),
  `build/build_artifact.mjs`(`--webp` 때 `.cache/venv` 파이썬 사용).
- `reference/frost-village/tools/` 를 그대로 돌릴 땐 `PLAYWRIGHT_BROWSERS_PATH=.cache/pw-browsers` 를 붙인다. 렌더/검수 도구는 `/tmp` 경로가 남아 있으니 `game/tools/` 쪽을 쓴다.
- `docs/handoff/` 와 `명령어모음.md` 의 `/tmp/bvenv/bin/python`, `python3` 는 위 표대로 읽는다.
- Bash 한 번에 10분 제한은 같다 → 긴 렌더는 백그라운드로 돌린다.

## 핵심 규칙 (전작에서 검증됨)
1. **계약서 먼저**: 여러 팀(에이전트)이 동시에 만들려면 먼저 `CONTRACT.md` 같은 기술 계약서(투영·PPU·앵커·매니페스트 형식·에셋 키 이름)를 쓴다. 키 이름은 계약서에서만 정한다.
2. **공용 카메라/조명/크기 고정**: 모든 스프라이트는 `tools/blender/bl_common.py` 로 렌더한다 — 직교 카메라 고도 30°·방위 45°(2:1 아이소), **PPU 64**(1m = 64px), 5방향 렌더(S,SE,E,NE,N) + 게임에서 좌우 반전. 이 값을 바꾸면 기존 에셋과 크기가 안 맞는다.
3. **폴더별 매니페스트**: 에셋 폴더마다 `manifest.json`(아틀라스·이미지·스프라이트시트·스프라이트·나인슬라이스·오디오). 게임은 매니페스트로만 에셋을 찾고, 없으면 대체 그림으로 계속 돈다.
4. **파일 소유권**: 동시에 일하는 에이전트마다 쓸 수 있는 폴더를 정해준다. 확장은 **새 폴더 + 계약서 부록**으로 해서 충돌을 피한다.
5. **검증은 실제 브라우저로**: Playwright 헤드리스 크롬 + 게임의 `window.__FV`식 테스트 훅으로 실제 입력처럼 플레이해서 확인한다. 화면은 스크린샷을 직접 보고 판단한다.
6. **검수 → 재현 → 수정 → 독립 검증**: 여러 관점(게임플레이 봇, 화면, 안정성, 배포)으로 검수하고, 고치는 쪽은 먼저 재현한 뒤 고치고, 다른 에이전트가 다시 확인한다.

## 에이전트 운영 주의 (전작에서 실제로 겪음)
- 워크플로 동시 실행 수 = CPU-2 (4코어면 2개). 많이 돌리려면 워크플로를 나눠 띄운다. Blender 렌더와 크롬 테스트는 CPU를 많이 먹는다.
- **실행 중인 워크플로 에이전트에게 SendMessage 를 보내지 않는다** — 같은 에이전트가 복제되어 둘이 같은 파일을 덮어썼다. 지시가 필요하면 멈추고(TaskStop) 새로 띄우거나, 공유 파일에 메모를 남긴다.
- 백그라운드 작업은 끊길 수 있다. 생성 스크립트는 **이어서 하기(resume) 가능**하게, 캐시는 저장소 밖(`/tmp/...`)에 둔다. Bash 한 번은 10분 제한 → 긴 렌더는 nohup + 로그 폴링.
- 다른 에이전트가 코드를 고치는 중에 배포판을 만들 땐 `git worktree` 로 커밋 시점을 떼어서 빌드한다.
- 작업 중간중간 커밋·푸시한다(컨테이너는 사라질 수 있다).

## 자주 쓰는 명령 (`game/` 폴더에서 실행. 이 PC 에서는 `PY=../.cache/venv/Scripts/python.exe`)
- 캐릭터 렌더/패킹/검사: `$PY tools/blender/char_render.py -- --chars all` → `$PY tools/blender/char_pack.py` → `$PY tools/blender/char_check.py`
- 주민: `vil_render.py` / `vil_pack.py` / `vil_check.py`, 건물·소품: `prop_render.py` / `prop_pack.py` / `prop_check.py`, 생활 소품: `life_*.py`
- 이펙트/UI/바닥/이모티콘: `$PY tools/fx/gen_fx.py`, `gen_ui.py`, `gen_ground.py`, `gen_emotes.py`
- 소리: `$PY tools/audio/build_audio.py` (옵션 `--only 키,키`, `--skip-render`)
- 게임 실행: `node tools/test/serve.mjs` → 브라우저로 열기(`?debug=1`), 자동 테스트: `node tools/test/smoke.mjs`, 스크린샷: `node tools/test/shot.mjs out.png`
- 플레이 링크(Claude 아티팩트)용 빌드: `node tools/build/build_artifact.mjs --webp` → `node tools/build/test_deploy.mjs standalone sameorigin --quick`
- 시험 결과(2026-10-07): 주인공 캐릭터 렌더 10장 약 1초, 서리마을 원본 실행 스크린샷 오류 0건.
- 정확한 사용법·옵션은 `docs/handoff/03~05` 참고.

## 새 게임 「봄날의 행진」 현재 상태 (2026-10-07, 3D 전환 중)
- 결정 사항: `docs/기획_결정.md` (질문 13개 + 마을 생활 + 1판 피드백: 3D·360° 회전, 깃발 없는 직접 운반, 자유 길·배치, 분류 메뉴, 건설 현장, 실내 생활).
- **3D 계약서**: `docs/CONTRACT3D.md` (건물 GLB 노드 이름 roof/walls/walls_low/iwalls/iwalls_low/floor/interior/exterior/anim_*/fx_*, slot.<동작>.<번호>, 가구 목록).
- 2D 시제품은 보관만: `game/index2d.html` + `game/src2d/` (Phaser).
- 3D 게임: `game/index.html` + `game/src/` (three.js 0.180, 가져오기 지도(importmap)로 `game/node_modules/three` 사용, 빌드 없이 실행).
  - `src/render/stage.js` 화면·빛·카메라·조작(가운데 버튼/오른쪽 끌기 = 360° 회전, 휠 확대, 두 손가락 비틀기·벌리기), 낮밤 하늘
  - `src/render/models.js` GLB 창고, `Doll`(주민 인형: 동작 재생·손에 물건), `Pool`(나무·바위 인스턴싱)
  - `src/game/defs.js` 건물(분류 house/prod/shop/public), 길 3종(흙길·자갈길·돌길), 숫자
  - `src/game/roads.js` 자유 곡선 길 연결망(교차 자동 연결) + 길 따라 길찾기(길이 빠르면 길로)
  - `src/game/buildings.js` 건물 모습(실내 GLB 있으면 사용, 없으면 서리마을 소품 조합), 공사 현장(흙바닥·말뚝·비계·재료 더미·아래서 위로 자르기), 실내 보기
  - `src/game/world.js` 자연·건물 놓기 검사(회전 사각형 겹침)·물류(나르기 일감)·효과
  - `src/game/people.js` 주민 행동 전부 (2D 판에서 옮김 + 3D: 비계 위 망치질, 나무 쓰러짐, 가구 자리 사용, 침대에서 눕기)
  - `src/ui/hud.js`·`bubbles.js` HTML 메뉴·말풍선
- 3D 에셋 도구 (`game/tools/blender/`): `export_glb.py`(캐릭터+동작, 관절별 부품 합치기, 모양 단순화), `export_props_glb.py`(소품, 계산 무늬를 그림으로 굽기, 단순화),
  Blender 팀 담당 `b3d_*.py`(실내 있는 건물·가구) → `game/assets3d/{chars,props,buildings,furniture}`.
  - 주의: Blender 에서 위치 읽기 전에 `bpy.context.view_layer.update()`, 합친 뒤 면 방향 다시 계산. 계산 무늬 재질은 굽지 않으면 하얗게 나옴.
- 시험: `cd game && PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers node tools/test/g3d.mjs ../.cache/shots/g3d --play 120` (`--gpu` = 이 PC 그래픽카드, `--perf` = 주민 300명). 모델 보기: `viewer.html?k=npc_aunt&c=idle,walk&p=tree_pine_a`.
- 2D 판 플레이 링크(보관): https://claude.ai/artifact/8eXSM5tB3aDGm83kWFPWVF
