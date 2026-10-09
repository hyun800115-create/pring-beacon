# 기능 팀 계약서 (2026-10-10) — 저장·계절·외교·PC 설치판

여러 팀이 동시에 일한다. **자기 파일만 고친다.** 공용 파일(main.js, hud.js, people.js, world.js, buildings.js 등)은 이미 아래 연결 고리를 넣어 두었으니 고치지 않는다.
꼭 다른 클래스에 함수가 필요하면, 자기 파일 안에서 `Class.prototype.이름 = function…` 으로 덧붙인다(원본 파일은 건드리지 않음).

## 연결 고리 (이미 들어가 있음)
| 위치 | 부르는 것 |
|---|---|
| `main.js` boot | `this.saver = new SaveSystem(this)`, `this.seasons = new Seasons(this)`, `this.diplo = new Diplomacy(this)` (People·Economy·Rival 등을 만든 뒤, Hud 만들기 전) |
| `main.js` boot | `if (!(await this.saver.offerContinue())) await this.setupStart();` → 그다음 `await this.seasons.init()` |
| `main.js` 매 프레임 | 게임 시간 잘게 나눈 단계마다 `this.diplo.update(h)` / 화면 프레임마다 `this.seasons.update(real, dt)`, `this.saver.update(real)` |
| `main.js` 아침 | `this.diplo.morning()` (경제 아침 다음) |
| `main.js` 땅 색 | `this.seasons.groundTint` 가 null 이 아니면 그 색을 땅에 곱한다 (아니면 계절 기본 색) |
| `main.js` 시험 훅 | `window.__SM.api` 를 만든 뒤 `saver.api(api)`, `seasons.api(api)`, `diplo.api(api)` 로 각자 시험 함수를 더한다 |
| `hud.js` | `hud.addSysButton(글자, 설명, 누르면)` → 위쪽 오른쪽 버튼, `hud.modal(html, (요소, 닫기) => {...})` → 가운데 팝업, `hud.toast(글)`, `hud.news(글, 종류)` |
| `people.js` think | 사람에게 `p.ctrl = (p, phase) => {...}` 를 달면 그 사람의 생각을 대신 맡는다 (false 를 돌려주면 평소대로). 다 끝나면 `p.ctrl = null` |

## 팀별 파일
| 팀 | 쓸 수 있는 파일 |
|---|---|
| 저장 | `game/src/game/save.js`, `game/tools/test/save_test.mjs` |
| 계절 | `game/src/game/seasons.js`, `game/tools/blender/b3d_seasons.py`, `game/assets3d/props/season_*.glb`(+json), `game/assets/ground/ground_grass*.png`·`ground_autumn*.png` 같은 새 땅 그림, `game/tools/test/seasons_test.mjs` |
| 외교 | `game/src/game/diplomacy.js`, `game/tools/test/diplo_test.mjs` |
| PC 설치판 | `game/app/pc/**`, `game/tools/build/build_app.mjs`, `game/tools/test/app_test.mjs`, 결과물은 `.cache/app-pc/`, `.cache/release/` |
| 안드로이드 (허락 뒤) | `game/app/android/**`, `game/tools/build/build_android.mjs`, 설치물은 `.cache/jdk`, `.cache/android-sdk`, 결과물 `.cache/release/` |

## 공통
- 모든 글(화면 글자·뉴스·말풍선)은 쉬운 한국어. 코드 주석도 한국어.
- 시험: `cd /c/시라이스/game && PLAYWRIGHT_BROWSERS_PATH=/c/시라이스/.cache/pw-browsers node tools/test/<자기 시험>.mjs` — `tools/test/features.mjs`, `g3d.mjs` 를 본보기로. **화면에 창을 띄우지 않는다** — `tools/test/pw.mjs` 의 `launchGpu()` (창 없이 진짜 그래픽카드, 초당 60장)를 쓴다. `headless: false` 금지. Electron 앱 시험은 `SM_HIDDEN=1`, 명령 실행은 `windowsHide: true`.
- 게임 상태는 `window.__SM.game` (Game 객체), 시험 함수는 `window.__SM.api`.
- git 명령은 쓰지 않는다 (정리는 총괄이 한다).
