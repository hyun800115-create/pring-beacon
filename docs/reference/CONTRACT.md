# Frost Village — Technical & Asset Contract

This file is the single source of truth that lets the art, audio, FX and game-code
work proceed in parallel. **Do not rename keys or paths defined here.** If you must
add something, add it (new keys are fine) and record it in your manifest.

Game design (Korean): `docs/기획서.md`. Visual reference: a Whiteout Survival ad
(soft-3D, cute chibi survivors in fur parkas, snowy ground, salmon/terracotta plaza
floor, log palisade fences, a tall tower of stacked items next to a processing machine,
a crowd of yellow-parka villagers queuing behind a fence). Reference image:
`/root/.claude/uploads/8cadcbb8-7304-572f-9d68-572175fda0e7/d44748b2-image.jpg`.

## 0. Layout of the project

```
frost-village/
  index.html                 game entry (full HTML doc; loads lib/phaser.min.js + src/main.js as ES module)
  lib/phaser.min.js          Phaser 3.90.0 (vendored, global `Phaser`)
  src/                       game code (ES modules, no build step)
  assets/
    characters/  manifest.json + char_<key>.png/.json atlases + portraits      (Blender)
    props/       manifest.json + props_*.png/.json atlases                       (Blender)
    fx/          manifest.json + particle atlas + animated effect spritesheets  (procedural)
    ui/          manifest.json + UI images                                       (procedural)
    ground/      manifest.json + seamless ground/water textures + decals        (procedural)
    audio/       manifest.json + <key>.ogg + <key>.mp3                          (procedural synthesis)
  tools/
    blender/bl_common.py     shared camera / light / material setup (DO NOT MODIFY without need; never change angles/PPU)
    pack_utils.py            shared atlas packer (Phaser JSON-hash, trimmed) + contact sheets
    blender/*.py             character & prop builders/renderers
    audio/*.py               music & sfx synthesis
    fx/*.py                  particle / effect / UI / ground generators
    test/                    headless browser smoke tests
  docs/previews/             contact sheets & screenshots for humans
```

Build machine tools: Blender 5.2 as a Python module at `/tmp/bvenv/bin/python` (`import bpy`,
Cycles CPU + OpenImageDenoise work; EEVEE/Workbench do NOT work headless here),
system `python3` 3.13 with numpy + Pillow, `ffmpeg` (libvorbis, libmp3lame), Node 22,
Playwright with Chromium at `/opt/pw-browsers` (global `playwright` npm package).
No internet model downloads (Hugging Face is blocked) → everything is procedural/Blender.

All generator scripts must be **re-runnable** (deterministic seeds) and runnable on the
user's PC too: Blender scripts as `blender -b -P tools/blender/<script>.py -- [args]`
(and also `python <script>.py` with the bpy module). Put `sys.path.insert(0, <dir of script>)`
before importing `bl_common`, and compute output paths from `__file__`.

## 1. Projection & scale (shared by every sprite)

* 1 Blender unit = 1 m. **PPU = 64** screen px per metre (horizontal).
* Orthographic camera, elevation 30° (rotation X=60°), yaw 45°. Ground squares → 2:1 diamonds.
  Vertical extents appear ×0.866. A 1.45 m character ≈ 80 px tall.
* Object "front" = local −Y. `bl_common.yaw_for_dir(d)` rotates to face screen direction `d`.
* Sun from screen upper-left, shadows fall screen lower-right. Use `bl_common.setup_lighting()`.
* Colour: `view_transform='Standard'`, materials via `bl_common.mat()` (sRGB hex input).
* Each sprite's **anchor** = where world origin (ground contact / footprint centre) lands.
  `bl_common.setup_camera(w, h, anchor_px)` places it exactly; manifest stores anchor as
  normalised `[ax, ay]` of the full (untrimmed) frame.
* Characters: **no baked ground shadow** (game draws a soft ellipse). Static props/buildings
  MAY bake a shadow with `bl_common.add_shadow_catcher()` — then run `pack_utils.clean_alpha()`.
* Game world is screen-space 2D. Depth sort = sprite `y` (anchor y). Iso illusion comes from the art.

### Shared palette (sRGB) — keep the world coherent
| use | hex | use | hex |
|---|---|---|---|
| snow | #F4F7FB | snow shadow | #C9D6E8 |
| ice | #9CC7E6 | sea deep / mid | #1F5FA8 / #2F86C9 |
| plaza floor (terracotta) | #D9A08A | plaza floor dark | #B97E6A |
| wood light / dark | #C98F55 / #8A5A33 | bark | #6E4428 |
| pine / pine dark | #2E6B4F / #1F4D3A | stone | #8E96A3 |
| ore orange | #D9822B | gold | #F2C14E |
| fire | #FF8A2A / #FFD45A | wheat | #E8C25A |
| bread | #C9853F | salmon/fish | #F08A5D |
| raw meat | #C8463D | skin | #F6CFAE |
| hair | #3A2A22 | player parka | #F2F0EA (fur trim #E6DCCB, belt #6B4A2E) |
| villager parkas | #F2C230 / #D9483B / #3D7CC9 | UI blue / green / gold | #3D8BE0 / #5CC86A / #FFC83D |
| UI dark text | #2B2F3A | UI panel cream | #FFF8EC |

## 2. Manifest format (every asset folder has `manifest.json`)

The game loads, in order: `assets/{characters,props,fx,ui,ground,audio}/manifest.json`.
Each is a "fragment" with any of these top-level fields. **All paths are relative to
`frost-village/assets/`.** Missing fragments/keys must not crash the game (fallback art).

```jsonc
{
  "version": 1,
  "atlases":      [{"key": "char_player", "png": "characters/char_player.png", "json": "characters/char_player.json"}],
  "images":       [{"key": "ground_snow", "png": "ground/ground_snow.png"}],
  "spritesheets": [{"key": "fx_poof", "png": "fx/fx_poof.png", "frameWidth": 128, "frameHeight": 128,
                    "frameCount": 8, "fps": 24, "repeat": 0, "anchor": [0.5, 0.5], "blend": "NORMAL"}],
  "characters":   {"player": { /* §3 */ }},
  "sprites":      {"tree_pine_a": {"atlas": "props_nature", "frame": "tree_pine_a", "anchor": [0.5, 0.88],
                                   "footprint": [90, 44], "kind": "prop"}},
  "nineSlice":    {"ui_panel": {"image": "ui_panel", "left": 28, "right": 28, "top": 28, "bottom": 28}},
  "audio":        {"sfx_coin": {"files": ["audio/sfx_coin.ogg", "audio/sfx_coin.mp3"], "volume": 0.6,
                                "loop": false, "kind": "sfx"}},
  "audioGroups":  {"sfx_chop": ["sfx_chop_1", "sfx_chop_2", "sfx_chop_3"]}
}
```

`sprites[key]` is the universal way to look up a static picture: it has either
`atlas`+`frame` **or** `image` (a key from `images`), plus `anchor`. Optional fields:
`footprint` [w,h] px (ground ellipse/diamond used for collision & pad placement),
`kind` (`prop|station|building|decor|item|ui|icon|decal`), `anims` (named frame lists, e.g.
`{"work": {"frames": ["station_grill_work_0", ...], "fps": 8, "repeat": -1}}`),
`stackStep` (items only: vertical px between stacked copies at scale 1), `tint`able flag, `notes`.

## 3. Characters — `assets/characters/` (Blender)

One trimmed atlas per character: `char_<key>.png` + `char_<key>.json` (Phaser JSON hash via
`pack_utils.pack_atlas`). Frame names: **`{anim}_{dir}_{i}`** e.g. `walk_SE_3` (i from 0, no padding).
Render dirs **S, SE, E, NE, N**; game mirrors SW←SE, W←E, NW←NE with `flipX`.
Full frame **128×128**, anchor pixel **(64,104)** → `[0.5, 0.8125]` (animals may use a larger frame;
record it).

| key | look | anims (frames) |
|---|---|---|
| player | chief / pioneer: white fur parka with fur-trimmed hood down, brown belt & strap, dark hair, rosy cheeks | idle(4) walk(8) carry_idle(4) carry_walk(8) chop(8) mine(8) harvest(6) |
| fisherman | yellow raincoat + sou'wester hat, rubber boots; fishing rod in `work` | idle walk carry_idle carry_walk work(8) |
| lumberjack | red plaid shirt, dark beanie, brown beard, axe in `work` | same |
| farmer | straw hat, green overalls over white shirt; sickle in `work` | same |
| miner | orange hard hat with lamp, brown vest, grey shirt; pickaxe in `work` | same |
| hunter | brown fur cloak with hood, green tunic; bow in `work` (draw+release) | same |
| villager_a / villager_b / villager_c | customers: yellow / red / blue parkas, varied hair & hats | idle walk carry_walk happy(6) |
| deer | stylised cute deer (small antlers) | idle(4) walk(8) |
| boar | round cute boar with tusks | idle(4) walk(8) |

Default fps: idle 6, walk 12, carry_idle 6, carry_walk 12, chop/mine/work 14, harvest 10, happy 10.
Carry poses hold both arms forward at chest height (the game draws the item stack there).

Manifest entry:
```jsonc
"player": {
  "atlas": "char_player", "frameSize": [128,128], "anchor": [0.5, 0.8125],
  "dirs": ["S","SE","E","NE","N"], "mirror": {"SW":"SE","W":"E","NW":"NE"},
  "frameName": "{anim}_{dir}_{i}",
  "anims": {"idle": {"frames":4,"fps":6,"repeat":-1},
            "chop": {"frames":8,"fps":14,"repeat":-1,"impactFrame":5}, ...},
  "carryPoint": {"S":[0,-34,false], "SE":[10,-34,false], "E":[14,-34,false], "NE":[8,-38,true], "N":[0,-40,true]},
  "shadow": [46, 18],
  "portrait": "portrait_player"
}
```
`carryPoint[dir] = [dx, dy, behind]`: px offset from the anchor where the **bottom** of the
carried stack sits; `behind=true` → game draws the stack behind the body. Mirrored dirs negate dx.
`impactFrame` = frame where the tool hits (game syncs sfx + particles).
Portraits: `sprites["portrait_<key>"]` 128×128 head-and-shoulders, facing S (used in hire UI),
plus `characters/portrait_player_512.png` (for app icon / title).

## 4. Props, buildings, items — `assets/props/` (Blender)

Atlases (suggested grouping, record actual in manifest): `props_nature`, `props_buildings`,
`props_decor`, `props_items`. Every key below must appear in `sprites`.

Nature: `tree_pine_a`, `tree_pine_b`, `tree_pine_snow`, `tree_stump`, `rock_ore` (grey boulder with
orange ore veins), `rock_ore_b`, `rock_rubble` (depleted), `crop_wheat_0`..`crop_wheat_3`
(one 1.5 m tilled plot: 0 bare soil, 1 sprouts, 2 green, 3 golden ripe), `bush_snow`, `snow_pile_a`,
`snow_pile_b`, `ice_chunk`.

Stations (each: idle frame + `anims.work` 4-frame loop): `station_grill` (stone hearth + grate, for
fish), `station_sawmill` (log bench with circular blade), `station_bakery` (domed stone oven +
chimney), `station_smelter` (brick furnace + crucible), `station_smokehouse` (wooden smoke hut /
meat rack). Footprint ≈ 2.5–3 m.

Buildings & sellers: `market_counter` (wooden food stall with striped awning), `trade_post`
(merchant sled/wagon with crates & awning), `worker_hut` (small log cabin), `chief_lodge` (big log
house, decor), `tent_a`, `campfire` (logs + stones, fire added by game FX), `upgrade_bench`
(workbench with anvil & backpack), `fish_net` (net on poles at the shore, open toward the sea),
`dock_pier`, `mine_entrance` (rock face with timber-framed tunnel), `boat_small`.

Decor: `fence_log_x` and `fence_log_y` (1 m palisade segments along the two ground axes: x = runs
screen down-right, y = runs screen up-right), `fence_post`, `bench`, `lamp_post`, `barrel`,
`crate`, `firewood_pile`, `signpost`, `flag_pole`, `hay_bale`.

Items (stack/hand-carried, ALSO used as UI icons; render chunky & readable, lying flat):
`item_fish_raw`, `item_fish_cooked`, `item_log`, `item_plank`, `item_wheat`, `item_bread`,
`item_ore`, `item_ingot`, `item_meat_raw`, `item_meat_cooked`, `item_coin`.
Each item has `stackStep` (≈ 8–14 px) so towers read like the reference's salmon tower.
Frame ≈ 72×72, anchor = bottom centre of the item's ground contact.

## 5. FX — `assets/fx/` (procedural)

Particle atlas `fx_particles` (white/greyscale unless noted, so the game can tint), each listed in
`sprites` with kind `fx`: `fx_spark`, `fx_star`, `fx_glow` (soft round), `fx_smoke`, `fx_snowflake`,
`fx_chip_wood`, `fx_chip_rock`, `fx_droplet`, `fx_wheat_bit`, `fx_heart` (pink), `fx_ring`,
`fx_flame` (orange), `fx_coin` (gold), `fx_leaf`, `fx_dust`.

Animated spritesheets (listed in `spritesheets`): `fx_poof` (unlock / spawn cloud), `fx_splash`
(water), `fx_hit` (impact star), `fx_levelup` (rising rings + sparkles), `fx_unlock` (burst
ring + rays), `fx_fire` (loop), `fx_smoke_puff`, `fx_coin_spin` (rotating coin loop),
`fx_sparkle` (twinkle loop for "ready" highlights).

## 6. UI — `assets/ui/` (procedural; text is NOT baked — the game renders text)

`ui_joystick_base`, `ui_joystick_knob`, `ui_panel` (9-slice, cream with soft shadow),
`ui_button_blue`, `ui_button_green`, `ui_button_gray` (9-slice, chunky with bottom bevel),
`ui_icon_coin`, `ui_icon_settings`, `ui_icon_sound_on`, `ui_icon_sound_off`, `ui_icon_music_on`,
`ui_icon_music_off`, `ui_icon_lock`, `ui_icon_close`, `ui_icon_check`, `ui_icon_backpack`,
`ui_icon_speed`, `ui_icon_worker`, `ui_arrow` (big bouncing tutorial arrow pointing DOWN),
`ui_bubble` (speech bubble, tail at bottom centre), `ui_coin_bar` (rounded pill for coin HUD),
`ui_badge_max`, `ui_pad_unlock` (iso 2:1 diamond floor pad, white rounded dashed border, slightly
transparent fill — like the reference's square pads), `ui_pad_input`, `ui_pad_output`,
`ui_pad_cash`, `ui_pad_hire`, `ui_pad_upgrade` (iso diamonds with simple engraved symbols),
`ui_ring_bg`, `ui_ring_fill` (unlock progress ring, fill is white to tint),
`ui_title_bg` (portrait 720×1280 title backdrop).

## 7. Ground — `assets/ground/` (procedural, seamless where noted)

Seamless 512×512: `ground_snow`, `ground_plaza` (terracotta wood/stone floor like the reference),
`ground_dirt`, `ground_farm` (tilled rows), `ground_rock` (mine gravel), `water_sea` (deep blue with
subtle caustics), `water_shallow`. Strips: `shore_foam` (seamless horizontally, alpha). Decals
(alpha PNG): `decal_path_a`, `decal_path_b`, `decal_snow_drift_a`, `decal_snow_drift_b`,
`decal_dirt_patch`, `decal_footprints`, `decal_puddle_ice`. Also `fish_school` (a group of fish
silhouettes under water with alpha, ~256×128, used scrolling in the sea like the reference).

## 8. Audio — `assets/audio/` (procedural synthesis → .ogg + .mp3)

Music (`kind: music`, seamless loops): `bgm_village` (cosy winter village, ~100 bpm, 60–100 s),
`bgm_title` (short, warm). Ambience (`kind: ambience`, loops): `amb_wind`, `amb_sea`, `amb_fire`.
SFX (`kind: sfx`): `sfx_chop_1..3`, `sfx_mine_1..3`, `sfx_harvest_1..2`, `sfx_splash`, `sfx_reel`,
`sfx_bow`, `sfx_hit_animal`, `sfx_animal_deer`, `sfx_animal_boar`, `sfx_pickup` (short bright pop —
game raises pitch as the stack grows), `sfx_drop`, `sfx_coin`, `sfx_coins_many`, `sfx_cash`,
`sfx_unlock`, `sfx_build`, `sfx_levelup`, `sfx_hire`, `sfx_click`, `sfx_error`, `sfx_whoosh`,
`sfx_step_snow_1..3`, `sfx_saw`, `sfx_smelt`, `sfx_sizzle`, `sfx_oven`, `sfx_customer_happy`,
`sfx_pad_fill` (soft tick while paying), `sfx_complete` (village complete fanfare).
Groups in `audioGroups`: `sfx_chop`, `sfx_mine`, `sfx_harvest`, `sfx_step_snow`.
Peak ≤ −1 dBFS; music ~−18 LUFS, sfx ~−14 LUFS-ish. Seamless loops must click-free.

## 9. Game code rules — `src/`

* Phaser 3.90 global `Phaser`; ES modules; **no build step, no npm deps at runtime, no network
  requests except our own relative files**. Must work from any static server sub-path (relative URLs).
* Portrait logical size 720×1280, `Scale.FIT`, `autoCenter`. Touch: floating virtual joystick
  anywhere; desktop: WASD/arrows (+ mouse drag).
* Direction from screen velocity (vx, vy): `a = atan2(vy*2, vx)`; sector `round(a/45°) mod 8` →
  0 E, 1 SE, 2 S, 3 SW, 4 W, 5 NW, 6 N, 7 NE. SW/W/NW use SE/E/NE frames with `flipX`.
* All asset access through one registry (e.g. `src/core/Assets.js`) that reads the manifests and
  falls back to generated placeholder textures + a single `console.warn` per missing key.
* All tunable numbers in `src/data/balance.js` (Korean comments — the designer edits it).
  World layout in `src/data/world.js`. Strings in `src/data/strings.js` (ko default, en).
* No `alert/confirm/prompt` (build confirmations in-game). Wrap every `localStorage` access in
  try/catch. Audio starts only after the first tap (title screen "탭하여 시작").
* Save key `frostVillage.save.v1`. Autosave every 5 s + on `visibilitychange`.
* Test hooks: `window.__FV = { game, state(), give(coins), unlockAll(), teleport(x,y),
  setInput(vx,vy) }`. `?debug=1` shows FPS + key `M` = +1000 coins.
