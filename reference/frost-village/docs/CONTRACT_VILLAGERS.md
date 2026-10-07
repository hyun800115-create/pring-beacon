# Contract addendum — Villagers, pets, village-life props & emotes

Extends `docs/CONTRACT.md` (all its rules apply: PPU 64, bl_common camera/light, manifest §2
format, paths relative to `frost-village/assets/`). Design (Korean): `docs/주민기획.md`.
These live in NEW folders so nothing collides with the existing `assets/characters` etc.
The game will load these extra fragments: `assets/villagers/manifest.json`,
`assets/life_props/manifest.json`, `assets/emotes/manifest.json`.

## A. Villagers & pets — `assets/villagers/` (Blender)

Same rules as CONTRACT §3: one trimmed atlas per key `vil_<key>.png/.json`, frame names
`{anim}_{dir}_{i}`, full frame 128×128, anchor (64,104) → `[0.5,0.8125]`, no baked shadow,
1 px soft ink outline like the existing characters, palette-quantized with libimagequant.
Kids are modelled smaller (~1.1–1.2 m) in the same frame/anchor; elders slightly shorter/hunched.

Keys (see 주민기획.md §1 for looks): `npc_kid_boy`, `npc_kid_girl`, `npc_kid_prankster`,
`npc_teen_girl`, `npc_young_man`, `npc_aunt`, `npc_uncle`, `npc_grandma`, `npc_grandpa`,
`npc_merchant`, `npc_herbalist`, `npc_bard`, `npc_blacksmith`, `npc_fashion`, `npc_yellow`,
`npc_red`, `npc_blue`, pets `pet_dog`, `pet_cat`, `pet_penguin`.

### Animations
Locomotion in all 5 render dirs (S, SE, E, NE, N; game mirrors SW/W/NW).
Social/emote anims ONLY in 3 dirs **S, SE, E** (game mirrors to SW, W; when a character must
play one while facing N/NE/NW the game turns it to the nearest of S/SE/E/SW/W).
Each anim entry in the manifest lists its `dirs`.

| anim | frames/fps | dirs | who | face / body |
|---|---|---|---|---|
| idle | 4 / 6 loop | 5 | all | neutral, breathing, blink on one frame |
| walk | 8 / 12 loop | 5 | all | |
| run | 8 / 16 loop | 5 | kids, prankster, young_man, teen, pets | lean forward, big arm swing |
| carry_walk | 8 / 12 loop | 5 | all humans | arms forward like CONTRACT §3 carry |
| happy | 6 / 10 loop | 3 | all humans | hop, arms up, ^^ eyes |
| talk | 8 / 10 loop | 3 | all humans | mouth opens/closes, hand gestures, head nods |
| laugh | 6 / 10 loop | 3 | all humans | ^^ closed eyes, wide open mouth, hand on belly, shaking |
| wave | 6 / 10 loop | 3 | all humans | one arm waving overhead, smile |
| surprised | 6 / 12 once | 3 | all humans | small jump back, round eyes, O mouth, hands up |
| angry | 6 / 10 loop | 3 | all humans | stomping, fists down, frown brows, puffed red cheeks |
| sad | 4 / 6 loop | 3 | all humans | drooped head, teary eyes, sagging arms |
| throw | 8 / 14 once | 3 | kids, prankster, young_man, teen | wind-up, snowball in hand until `impactFrame`, release |
| hit | 6 / 12 once | 3 | all humans | knocked back, >< eyes, snow on face |
| dance | 8 / 10 loop | 3 | kids, teen, young_man, aunt, fashion, uncle, blacksmith | arms up sway / twirl |
| sit | 4 / 4 loop | 3 | grandma, grandpa, herbalist, aunt, bard | seated pose (seat height 0.45 m), gentle sway; grandpa nods off (closed eyes) |
| perform | 8 / 10 loop | 3 | bard | strumming a lute, ♪ mouth |
| shiver | 4 / 12 loop | 3 | all humans | cold shiver, clenched teeth |
| (pets) idle 4, walk 8, run 8 in 5 dirs; sit 4 (S,SE,E); happy 6 (S,SE,E: tail wag + hop); pet_cat also `loaf` 4 (S,SE,E) | | | | |

Expressions are baked into these anims (eyes/brows/mouth/cheek geometry swaps), so the face
must visibly change: neutral, ^^ smile, open laugh, O surprised, angry brows + red puffed
cheeks, sad tear, >< hurt, closed sleepy eyes, talking mouth flaps.

### Manifest entry (per key, inside `characters{}`)
```jsonc
"npc_kid_boy": {
  "atlas": "vil_npc_kid_boy", "frameSize": [128,128], "anchor": [0.5,0.8125],
  "dirs": ["S","SE","E","NE","N"], "mirror": {"SW":"SE","W":"E","NW":"NE"},
  "frameName": "{anim}_{dir}_{i}",
  "kind": "villager",            // or "pet"
  "role": "kid",                 // kid | teen | adult | elder | pet
  "name": {"ko": "꼬마 도윤", "en": "Doyun"},
  "traits": ["playful","prankster"],
  "anims": {"idle": {"frames":4,"fps":6,"repeat":-1,"dirs":["S","SE","E","NE","N"]},
            "throw": {"frames":8,"fps":14,"repeat":0,"dirs":["S","SE","E"],"impactFrame":5,
                      "impactPoint": {"S":[dx,dy],"SE":[..],"E":[..]}}, ...},
  "carryPoint": {...}, "headTop": -78, "shadow": [40,16],
  "portrait": "portrait_npc_kid_boy", "seatOffset": [0, -6]   // sit: anchor = seat front centre
}
```
Plus `images`/`sprites` for portraits `portrait_<key>` (128×128, same UI camera as existing portraits).
Previews: `docs/previews/vil_lineup.png`, `docs/previews/vil_<key>.png`, GIFs of talk/laugh/throw/dance.

## B. Village-life props — `assets/life_props/` (Blender, prop pipeline conventions)

`snowman_0`..`snowman_3` (snow pile → 2 balls → 3 balls → finished with carrot nose, coal
eyes, scarf and bucket hat), `snowball_pile`, `snow_fort` (low curved snow wall ~2 m),
`log_seat` (horizontal log bench for the campfire circle, sit height 0.45 m), `sled`
(wooden kids' sled), `dog_house` (small with red roof + snow), `music_stand`? (optional),
`picnic_table` (with snow), `lantern_string` (decor: posts with string of warm lights),
`market_umbrella`? (optional). Each in `sprites` with anchor, footprint, kind, `seatPoints`
([[dx,dy],...] px offsets from the anchor where a sitting character's anchor goes) for
seats/benches. Also add `seatPoints` for the EXISTING `bench` here as an override entry
`bench_seats` = {"of":"bench","seatPoints":[...]} (do not re-render bench).

## C. Emotes & social FX — `assets/emotes/` (procedural, numpy + Pillow)

Atlas `emotes` (each also in `sprites`, kind `emote`, ~64×64, soft-3D look matching the UI):
`emote_heart`, `emote_love` (heart eyes face), `emote_laugh` (squinting laughing face with
tears), `emote_exclaim`, `emote_question`, `emote_anger` (red cross-vein), `emote_sweat`,
`emote_music`, `emote_zzz`, `emote_idea`, `emote_sparkle`, `emote_cold` (blue shivering
face), `emote_tear`, `emote_dots` (… typing), `emote_star`, `emote_fish`, `emote_bread`,
`emote_wave` (waving hand), `emote_thumbs`, `emote_snowball`.
UI: `ui_emote_bubble` (round bubble ~84×84 with tail at bottom centre, anchor at tail tip),
`ui_chat_bubble` (9-slice speech bubble body for short text, with `nineSlice` margins) and
`ui_chat_tail` (separate tail piece).
FX: `fx_snowball` (projectile ~24 px, in the atlas), spritesheets `fx_snow_splat` (impact
burst, 8–10 frames), `fx_music_notes` (rising notes loop), `fx_hearts` (small hearts rising,
one-shot), `fx_anger_puff` (cartoon anger smoke puff, one-shot), `fx_sweat_drops` (one-shot).
