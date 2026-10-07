// =====================================================================
//  월드 배치 (world.js) — 마을 지도.
//  좌표는 화면 픽셀(px): x 는 오른쪽으로, y 는 아래로 갈수록 커집니다.
//  구역(zone) 안의 물건은 Z('구역', mx, my) 로 '구역 중심에서 몇 미터' 로 적습니다.
//    mx: +1 이면 오른쪽 아래로 1m (+45, +23 px),  my: +1 이면 오른쪽 위로 1m (+45, -23 px)
//  구역 size 는 [X축 m, Y축 m] — 아이소 마름모 모양 바닥이 됩니다.
// =====================================================================

const ZONES = {
  plaza:  { center: [990, 800],   size: [14, 14],   floor: 'ground_plaza', unlock: null,          name: 'z_plaza' },
  forest: { center: [470, 1250],  size: [9, 9],     floor: 'ground_dirt',  unlock: 'zone_forest', name: 'z_forest', floorAlpha: 0.5 },
  farm:   { center: [1410, 1270], size: [8, 8],     floor: 'ground_farm',  unlock: 'zone_farm',   name: 'z_farm' },
  mine:   { center: [430, 1900],  size: [9, 9],     floor: 'ground_rock',  unlock: 'zone_mine',   name: 'z_mine' },
  hunt:   { center: [1400, 1960], size: [8.5, 8.5], floor: 'ground_dirt',  unlock: 'zone_hunt',   name: 'z_hunt', floorAlpha: 0.45 },
};

/** zone-local metres -> screen px [x, y] */
export function Z(zone, mx, my) {
  const c = ZONES[zone].center;
  return [Math.round(c[0] + 45.25 * (mx + my)), Math.round(c[1] + 22.63 * (mx - my))];
}
const P = (zone, mx, my) => { const [x, y] = Z(zone, mx, my); return { x, y }; };

// station pads are placed at the ends of the station's long axis (world X) or in front (-Y)
const XOFF = (m) => [Math.round(45.25 * m), Math.round(22.63 * m)];      // along +X
const YOFF = (m) => [Math.round(45.25 * m), Math.round(-22.63 * m)];     // along +Y

const grill = Z('plaza', -4.5, 4.8);
const market = Z('plaza', 2.0, 2.8);
const trade = Z('plaza', -4.6, -1.0);
const bench = Z('plaza', 3.6, -4.6);
const sawmill = Z('forest', 1.3, 2.6);
const bakery = Z('farm', -1.6, 1.2);
const smelter = Z('mine', 1.6, 2.4);
const smokehouse = Z('hunt', -1.8, 1.6);

const rel = (a, b) => [b[0] - a[0], b[1] - a[1]];

export const WORLD = {
  width: 1800,
  height: 2620,

  // 바닷가: y 값보다 위쪽이 바다. 물결 모양 = base + Σ amp*sin(x*freq + phase)
  shore: { base: 372, waves: [[16, 0.0052, 0.4], [7, 0.0165, 1.7], [3, 0.041, 0.2]] },

  player: { x: 935, y: 520 },          // 시작 위치
  // 첫 판매(튜토리얼) 동안 카메라가 비추는 곳: 그물·그릴·판매대·손님 줄이 한 화면에 들어오도록
  // (촌장이 화면 가장자리로 가면 카메라가 따라감)
  tutorialView: [1095, 670],

  zones: ZONES,

  // ── 가공소 ─────────────────────────────────────────────
  // in / out: 입구·출구 발판 위치 (가공소 기준 상대 px)
  stations: [
    { id: 'grill',      sprite: 'station_grill',      x: grill[0], y: grill[1], in: XOFF(-2.15), out: XOFF(2.15), input: 'item_fish_raw', output: 'item_fish_cooked', zone: 'plaza', sfx: 'sfx_sizzle', fire: [0, -30] },
    { id: 'sawmill',    sprite: 'station_sawmill',    x: sawmill[0], y: sawmill[1], in: XOFF(-2.3), out: XOFF(2.3), input: 'item_log', output: 'item_plank', zone: 'forest', sfx: 'sfx_saw' },
    { id: 'bakery',     sprite: 'station_bakery',     x: bakery[0], y: bakery[1], in: [118, 28], out: [-118, 30], input: 'item_wheat', output: 'item_bread', zone: 'farm', sfx: 'sfx_oven', smoke: [40, -150] },
    { id: 'smelter',    sprite: 'station_smelter',    x: smelter[0], y: smelter[1], in: [-122, 4], out: [112, 52], input: 'item_ore', output: 'item_ingot', zone: 'mine', sfx: 'sfx_smelt', smoke: [-14, -150] },
    { id: 'smokehouse', sprite: 'station_smokehouse', x: smokehouse[0], y: smokehouse[1], in: [122, 26], out: [-124, 40], input: 'item_meat_raw', output: 'item_meat_cooked', zone: 'hunt', sfx: 'sfx_sizzle', smoke: [-10, -140] },
  ],

  // ── 판매처 ─────────────────────────────────────────────
  market: {
    sprite: 'market_counter', x: market[0], y: market[1],
    shelf: rel(market, Z('plaza', 4.35, 2.8)),     // 음식 놓는 발판 (판매대 오른쪽 끝)
    cash: rel(market, Z('plaza', 4.7, 0.3)),       // 손님 코인 쌓이는 발판
    queueStart: rel(market, Z('plaza', 2.0, 1.25)),// 맨 앞 손님 위치 (판매대 앞)
    queueStep: YOFF(-0.9),                         // 줄 간격 (뒤로 갈수록 왼쪽 아래)
    queueTurn: 6,                                  // 이 수만큼 선 뒤에는 줄이 꺾여서
    queueStep2: XOFF(0.9),                         //   이 방향(오른쪽 아래)으로 이어짐
    // 손님이 걸어오는 길 (끝나면 줄 끝으로). 손님은 화면 밖에서 이 길 위의 가장 가까운 곳에 나타납니다.
    // (주의: 모든 점은 걸을 수 있는 땅 안쪽이어야 합니다 — 지도 아래 끝 y 2570 보다 위)
    entry: [[990, 2200], [990, 1260], [1080, 1080]],
    exit: [[1080, 1080], [990, 1260], [990, 2200]],     // 다 산 손님이 돌아가는 길 (화면 밖으로 나가거나 길 끝에 닿으면 사라짐)
  },
  trade: {
    sprite: 'trade_post', x: trade[0], y: trade[1], zone: 'forest',
    shelf: rel(trade, Z('plaza', -4.6, -2.85)),    // 판자/주괴 놓는 발판 (앞쪽)
    cash: rel(trade, Z('plaza', -2.1, -2.75)),     // 상인이 낸 코인
    merchant: rel(trade, Z('plaza', -4.3, 0.5)),   // 상인 위치 (썰매 뒤)
  },
  // 버리기 발판: 위에 잠깐 서 있으면 들고 있는 물건을 모닥불에 던져 버립니다 (어부 고용 후 나타남)
  trash: { x: 585, y: 680, fire: [520, 574] },
  bench: { sprite: 'upgrade_bench', x: bench[0], y: bench[1], pads: { capacity: rel(bench, Z('plaza', 1.55, -4.75)), speed: rel(bench, Z('plaza', 5.65, -4.45)) } },

  // ── 자원 ───────────────────────────────────────────────
  net: { x: 880, y: 398, gather: [0, 86], fisherSpot: [-128, 30] },
  trees: { zone: 'forest', grid: 2.05, jitter: 0.3, margin: 0.95, scale: 0.9, cornerCut: -5.5, avoid: [[sawmill[0], sawmill[1], 170], [sawmill[0] - 104, sawmill[1] - 52, 90], [sawmill[0] + 104, sawmill[1] + 52, 90], [Z('forest', -3.2, 2.4)[0], Z('forest', -3.2, 2.4)[1], 90]] },
  rocks: [
    [...Z('mine', -2.6, -0.4), 'rock_ore'], [...Z('mine', -0.6, -1.6), 'rock_ore_b'], [...Z('mine', -2.8, -2.8), 'rock_ore_b'],
    [...Z('mine', 0.9, -3.2), 'rock_ore'], [...Z('mine', -0.6, 0.6), 'rock_ore'], [...Z('mine', 2.6, -1.0), 'rock_ore_b'],
    [...Z('mine', -1.2, -3.9), 'rock_ore'],
  ],
  wheat: { zone: 'farm', origin: Z('farm', 1.3, -1.2), rows: 3, cols: 3, step: 1.5 },
  hunt: { zone: 'hunt' },

  // ── 해금 / 고용 발판 ────────────────────────────────────
  //  worker: 고용되는 일꾼, hut: 일꾼 오두막 위치 (구역이 열릴 때 함께 나타남)
  pads: {
    hire_fisherman:  { x: 900,  y: 700,  worker: 'fisherman',  hut: [585, 470] },
    zone_forest:     { x: 760,  y: 1130, zone: 'forest' },
    hire_lumberjack: { ...P('forest', -0.6, 3.6), worker: 'lumberjack', hut: [300, 1010] },
    zone_farm:       { x: 1190, y: 1135, zone: 'farm' },
    hire_farmer:     { ...P('farm', -1.0, 3.0), worker: 'farmer',     hut: [1606, 1112] },
    zone_mine:       { x: 760,  y: 1760, zone: 'mine' },
    hire_miner:      { ...P('mine', -0.4, 3.6), worker: 'miner',      hut: [236, 1730] },
    zone_hunt:       { x: 1160, y: 1800, zone: 'hunt' },
    hire_hunter:     { ...P('hunt', 1.6, 2.6), worker: 'hunter',     hut: [1616, 1790] },
    hire2_fisherman: { x: 640,  y: 610,  worker: 'fisherman' },
    hire2_lumberjack:{ ...P('forest', -1.0, 3.3), worker: 'lumberjack' },
    hire2_farmer:    { ...P('farm', 0.6, 3.1), worker: 'farmer' },
    hire2_miner:     { ...P('mine', -0.4, 3.6), worker: 'miner' },
    hire2_hunter:    { ...P('hunt', 2.9, 1.5), worker: 'hunter' },
  },

  // 고용된 일꾼의 대기 위치
  workerHome: {
    fisherman: [700, 470], lumberjack: Z('forest', -2.0, 1.6), farmer: Z('farm', -0.2, 2.2), miner: Z('mine', -0.2, 2.2), hunter: Z('hunt', 0.6, 2.2),
  },

  // ── 길 (눈이 다져진 길) ─────────────────────────────────
  paths: [
    [[990, 2700], [990, 2240], [990, 1700], [990, 1150]],
    [[990, 1440], [880, 1390], [790, 1300]],
    [[990, 1440], [1090, 1390], [1180, 1320]],
    [[990, 2040], [880, 2000], [790, 1950]],
    [[990, 2040], [1090, 2010], [1170, 1980]],
    [[990, 2240], [800, 2330], [620, 2380]],
    [[990, 2240], [1180, 2330], [1360, 2380]],
  ],

  // ── 울타리 ─────────────────────────────────────────────
  //  zone 의 가장자리: tl(왼쪽위) tr(오른쪽위) bl(왼쪽아래) br(오른쪽아래)
  //  gaps: 변 위의 [시작m, 끝m] 구간은 비워 둠 (입구). tl/bl 은 왼쪽 꼭짓점부터, tr 은 위 꼭짓점부터, br 은 아래 꼭짓점부터 잰 거리
  fences: [
    { zone: 'plaza',  edges: { tr: [[0, 3.2]] } },
    { zone: 'forest', edges: { tl: [], bl: [] } },
    { zone: 'farm',   edges: { tr: [], br: [] } },
    { zone: 'mine',   edges: { tl: [[6.2, 9]], bl: [] } },
    { zone: 'hunt',   edges: { tr: [], br: [], bl: [[0, 2.5]], tl: [[0.8, 5.2]] } },
  ],

  // ── 장식 ───────────────────────────────────────────────
  // [스프라이트, x, y, {zone: 해금 후에만 보임, flip: 좌우 반전, scale: 크기}]
  decor: [
    // 바다
    ['dock_pier', 1460, 300], ['boat_small', 1650, 250], ['ice_chunk', 210, 318], ['ice_chunk', 470, 340, { scale: 0.7 }],
    ['boat_small', 1290, 214, { flip: true, scale: 0.85 }], ['ice_chunk', 1120, 350, { scale: 0.55 }],
    // 해변
    ['lamp_post', 800, 480], ['barrel', 1150, 470], ['crate', 1205, 492], ['crate', 1182, 448, { scale: 0.8 }],
    ['flag_pole', 1330, 540], ['snow_pile_a', 330, 520], ['snow_pile_b', 410, 590], ['bush_snow', 1560, 560], ['bush_snow', 1615, 640],
    ['snow_pile_b', 1700, 520], ['campfire', 520, 590], ['firewood_pile', 445, 640], ['barrel', 495, 520],
    // 광장
    ['lamp_post', ...Z('plaza', -6.6, -6.6)], ['lamp_post', ...Z('plaza', 6.6, -6.6)], ['lamp_post', ...Z('plaza', -0.5, 6.7)],
    ['bench', ...Z('plaza', -1.4, -6.4)], ['barrel', ...Z('plaza', 6.4, 5.2)], ['crate', ...Z('plaza', 6.5, 4.4), { scale: 0.85 }],
    ['signpost', 1040, 1180], ['bush_snow', ...Z('plaza', 1.0, 7.3)], ['snow_pile_b', ...Z('plaza', 7.4, 1.5)],
    // 남쪽 마을
    ['chief_lodge', 960, 2400], ['tent_a', 660, 2380], ['tent_a', 1260, 2370, { flip: true }], ['campfire', 870, 2525],
    ['flag_pole', 1345, 2285], ['lamp_post', 700, 2270], ['lamp_post', 1080, 2560], ['firewood_pile', 760, 2500], ['barrel', 1200, 2500],
    ['crate', 1240, 2530], ['bench', 975, 2555], ['hay_bale', 1340, 2470], ['snow_pile_a', 520, 2490], ['bush_snow', 1420, 2480],
    ['snow_pile_b', 780, 2250], ['barrel', 820, 2420],
    // 길가
    ['lamp_post', 1040, 1500], ['lamp_post', 940, 1850], ['signpost', 940, 1520], ['bush_snow', 1060, 1640], ['snow_pile_b', 900, 1640],
    ['barrel', 1050, 1900], ['crate', 920, 2080], ['bush_snow', 900, 1250], ['snow_pile_a', 1100, 1580], ['lamp_post', 935, 1180],
    ['ice_chunk', 1080, 1700, { scale: 0.6 }], ['snow_pile_b', 860, 1530],
    // 구역 장식 (해금 후)
    ['firewood_pile', ...Z('forest', -3.4, 1.0), { zone: 'forest' }], ['tree_stump', ...Z('forest', 2.6, -1.2), { zone: 'forest' }],
    ['hay_bale', ...Z('farm', 3.2, 2.6), { zone: 'farm' }], ['hay_bale', ...Z('farm', 3.0, 1.8), { zone: 'farm', scale: 0.85 }], ['barrel', ...Z('farm', -3.3, -1.0), { zone: 'farm' }],
    ['mine_entrance', ...Z('mine', -2.6, 2.6), { zone: 'mine' }], ['crate', ...Z('mine', 2.8, 0.6), { zone: 'mine' }], ['barrel', ...Z('mine', 3.4, -0.4), { zone: 'mine' }],
    ['lamp_post', ...Z('mine', 0.4, 3.9), { zone: 'mine' }],
    ['hay_bale', ...Z('hunt', 2.6, -2.8), { zone: 'hunt' }], ['bush_snow', ...Z('hunt', 3.2, 0.4), { zone: 'hunt' }], ['bush_snow', ...Z('hunt', -2.8, -2.6), { zone: 'hunt' }],
    ['snow_pile_b', ...Z('hunt', 0.4, -3.4), { zone: 'hunt' }],
  ],

  // 가장자리 소나무 숲 (장식, 벨 수 없음): 자동 배치 영역 [x0, y0, x1, y1, 간격]
  borderTrees: [
    [0, 420, 150, 2620, 100], [1650, 420, 1800, 2620, 100], [0, 2560, 760, 2620, 115], [1180, 2560, 1800, 2620, 115],
  ],
  // 그 밖에 흩어진 소나무 [x, y, 종류] (구역 안이나 길 위면 자동으로 빠짐)
  extraTrees: [
    [260, 720, 'tree_pine_snow'], [190, 860, 'tree_pine_a'], [300, 930, 'tree_pine_b'], [1600, 760, 'tree_pine_snow'], [1560, 900, 'tree_pine_a'],
    [1680, 980, 'tree_pine_b'], [880, 1350, 'tree_pine_snow'], [1100, 1460, 'tree_pine_a'], [190, 1560, 'tree_pine_snow'], [700, 1560, 'tree_pine_a'],
    [1190, 1580, 'tree_pine_b'], [1660, 1640, 'tree_pine_snow'], [760, 2220, 'tree_pine_a'], [1540, 2300, 'tree_pine_snow'], [330, 2330, 'tree_pine_b'],
    [600, 2570, 'tree_pine_snow'], [1340, 2580, 'tree_pine_a'], [180, 2260, 'tree_pine_a'], [1700, 2230, 'tree_pine_b'], [1500, 1600, 'tree_pine_a'],
    [380, 1600, 'tree_pine_b'], [640, 1640, 'tree_pine_snow'], [1240, 2260, 'tree_pine_a'], [520, 2240, 'tree_pine_snow'],
  ],

  // 바닥 데칼 [키, x, y, 크기배율, 회전(도)]
  decals: [
    ['decal_snow_drift_a', 360, 660, 1], ['decal_snow_drift_b', 1580, 700, 1], ['decal_snow_drift_a', 760, 1580, 1.1], ['decal_snow_drift_b', 1220, 1590, 1],
    ['decal_snow_drift_a', 1580, 2420, 1], ['decal_snow_drift_b', 330, 2440, 1], ['decal_puddle_ice', 1120, 1520, 1], ['decal_puddle_ice', 640, 2250, 0.9],
    ['decal_dirt_patch', 700, 1640, 1.0], ['decal_dirt_patch', 300, 2120, 1],
    ['decal_footprints', 1010, 1720, 1], ['decal_footprints', 970, 2100, 1], ['decal_footprints', 760, 520, 0.9], ['decal_snow_drift_b', 1250, 1150, 0.8],
  ],
};
