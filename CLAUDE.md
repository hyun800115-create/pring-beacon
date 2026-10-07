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

## 환경 설정 (클라우드 컨테이너마다 한 번)
```bash
# Blender 5.2 를 파이썬 모듈로 (Cycles CPU + OpenImageDenoise 만 됨; EEVEE/Workbench 는 헤드리스에서 안 됨)
python3 -m venv /tmp/bvenv && /tmp/bvenv/bin/pip install bpy==5.2.2 numpy pillow imagequant
# 시스템 파이썬: 아틀라스 팔레트 압축
python3 -m pip install imagequant            # (권한 문제면 --user 또는 --break-system-packages)
# 사운드 합성용 scipy (audio 도구는 이 venv 로 자동 재실행됨)
python3 -m venv --system-site-packages /tmp/fv_audio_venv && /tmp/fv_audio_venv/bin/pip install scipy
# 배포 번들러
(cd <게임폴더>/tools/build && npm install)
```
- bpy 휠은 특정 파이썬 버전용이다(5.2.x ↔ Python 3.13). 버전이 안 맞으면 `uv python install 3.13` 후 그 파이썬으로 venv 를 만든다.
- 이미 있는 것: ffmpeg(libvorbis, libmp3lame), Node 22, Playwright + Chromium(`/opt/pw-browsers`, 전역 npm 패키지 `playwright`).
- 네트워크: PyPI·npm 만 된다고 가정(허깅페이스 등 AI 모델 다운로드 불가 → 그림은 Blender, 소리는 합성).
- 매 세션 자동 설정이 필요하면 SessionStart 훅으로 위 명령을 넣는다.

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

## 자주 쓰는 명령 (전작 기준 경로, 새 게임 폴더에서도 동일)
- 캐릭터 렌더/패킹/검사: `/tmp/bvenv/bin/python tools/blender/char_render.py -- --chars all` → `python3 tools/blender/char_pack.py` → `python3 tools/blender/char_check.py`
- 주민: `vil_render.py` / `vil_pack.py` / `vil_check.py`, 건물·소품: `prop_render.py` / `prop_pack.py` / `prop_check.py`, 생활 소품: `life_*.py`
- 이펙트/UI/바닥/이모티콘: `python3 tools/fx/gen_fx.py`, `gen_ui.py`, `gen_ground.py`, `gen_emotes.py`
- 소리: `python3 tools/audio/build_audio.py` (옵션 `--only 키,키`, `--skip-render`)
- 게임 실행: `node tools/test/serve.mjs` → 브라우저로 열기(`?debug=1`), 자동 테스트: `node tools/test/smoke.mjs`, 스크린샷: `node tools/test/shot.mjs out.png`
- 플레이 링크(Claude 아티팩트)용 빌드: `node tools/build/build_artifact.mjs --webp` → `node tools/build/test_deploy.mjs standalone sameorigin --quick`
- 정확한 사용법·옵션은 `docs/handoff/03~05` 참고.
