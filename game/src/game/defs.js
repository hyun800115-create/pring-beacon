// 봄날의 행진 (3D) 데이터: 물건, 건물(분류별), 길, 주민, 숫자. 밸런스 숫자는 여기서만 고친다.
// 크기는 미터. 건물 모델은 assets3d/buildings/<key>.glb (실내 있음) 가 있으면 그것을, 없으면 fallback 소품 조합을 쓴다.

export const ITEMS = {
  log:    { name: '통나무', model: 'item_log' },
  plank:  { name: '판자',   model: 'item_plank' },
  stone:  { name: '돌',     model: 'item_stone', alt: 'rock_rubble', scale: 0.45, color: 0x8c96a3 },
  wheat:  { name: '밀',     model: 'item_wheat' },
  flour:  { name: '밀가루', model: 'item_flour', color: 0xeee3c8 },
  bread:  { name: '빵',     model: 'item_bread', food: true, price: 3 },
  fish:   { name: '생선',   model: 'item_fish', alt: 'item_fish_cooked', food: true, price: 3, color: 0x8fb3d9 },
  egg:    { name: '달걀',   model: 'item_egg', food: true, price: 2, color: 0xfff3dc },
  milk:   { name: '우유',   model: 'item_milk', color: 0xffffff, price: 2 },
  cheese: { name: '치즈',   model: 'item_cheese', food: true, price: 5, color: 0xf2c14e },
  wool:   { name: '털',     model: 'item_wool', color: 0xf4f1ea, price: 4 },
  meat:   { name: '고기',   model: 'item_meat', alt: 'item_meat_cooked', food: true, price: 4, color: 0xc0574a },
  apple:  { name: '사과',   model: 'item_apple', food: true, price: 2, color: 0xd9443a },
  honey:  { name: '꿀',     model: 'item_honey', food: true, price: 5, color: 0xf0a92c },
};
export const ITEM_ORDER = ['log', 'plank', 'stone', 'wheat', 'flour', 'bread', 'fish', 'egg', 'milk', 'cheese', 'wool', 'meat', 'apple', 'honey'];
export const FOODS = ['bread', 'fish', 'egg', 'cheese', 'meat', 'apple', 'honey'];

export const CATEGORIES = [
  { key: 'house', name: '주택', icon: '🏠' },
  { key: 'prod', name: '생산', icon: '⚒️' },
  { key: 'farm', name: '목축·농사', icon: '🐄' },
  { key: 'shop', name: '상업', icon: '🏪' },
  { key: 'public', name: '공공', icon: '🏛️' },
  { key: 'deco', name: '장식', icon: '🌷' },
  { key: 'road', name: '길', icon: '🛤️' },
];

/**
 * 건물
 *  size [가로, 세로] m, kind: hq | house | gather | farm | process | shop | public
 *  fallback: 실내 모델이 아직 없을 때 쓰는 서리마을 소품 [[키, x, z, 회전도, 크기], ...] (건물 좌표, 정면 +z)
 */
export const BUILDINGS = {
  hall: {
    cat: 'public', name: '마을회관', desc: '마을의 중심. 창고이자 사무실·회의실·식당이 있어요', size: [7.4, 6.2], height: 6,
    kind: 'hq', buildable: false, work: 60, sleeps: 6, fallback: [['chief_lodge', 0, 0, 0, 1.25]],
  },
  house: {
    cat: 'house', name: '오두막', desc: '주민이 사는 집. 업그레이드하면 더 많이 살아요', size: [4.2, 3.8], height: 4.5,
    kind: 'house', cost: { plank: 3 }, work: 10, icon: '🏠',
    levels: [
      { key: 'house_1', name: '오두막', cap: 2, fallback: [['worker_hut', 0, 0, 0, 1.2]] },
      { key: 'house_2', name: '큰 오두막', cap: 4, cost: { plank: 4, stone: 2 }, fallback: [['worker_hut', 0, 0, 0, 1.3], ['clothesline', 2.2, 0.6, 90, 0.8], ['firewood_pile', 1.9, 1.4, 0, 0.8]] },
      { key: 'house_3', name: '통나무집', cap: 6, cost: { plank: 6, stone: 4 }, fallback: [['chief_lodge', 0, 0, 0, 0.9]] },
    ],
  },
  woodcutter: {
    cat: 'prod', name: '나무꾼 작업장', desc: '나무를 베어 통나무를 만들어요', size: [4.0, 3.2], height: 3,
    kind: 'gather', res: 'tree', radius: 16, workTime: 4.5, out: 'log', tool: 'lumberjack', cost: { plank: 2 }, work: 8, icon: '🪓',
    fallback: [['upgrade_bench', 0, 0, 0, 1.1], ['firewood_pile', 1.6, 0.6, 20, 0.9], ['tree_stump', -1.4, 1.0, 0, 0.9]],
  },
  quarry: {
    cat: 'prod', name: '채석장', desc: '바위를 깨서 돌을 만들어요', size: [5.0, 3.6], height: 4,
    kind: 'gather', res: 'rock', radius: 18, workTime: 5, out: 'stone', tool: 'miner', cost: { plank: 3 }, work: 10, icon: '⛏️',
    fallback: [['mine_entrance', 0, 0, 0, 1.1]],
  },
  sawmill: {
    cat: 'prod', name: '제재소', desc: '통나무 → 판자', size: [4.2, 3.0], height: 3,
    kind: 'process', in: 'log', out: 'plank', time: 6, look: 'lumberjack', anim: 'work', cost: { plank: 2, stone: 2 }, work: 10, icon: '🪚', sfx: 'saw',
    fallback: [['station_sawmill', 0, 0, 0, 1.2]],
  },
  farm: {
    cat: 'prod', name: '밀 농장', desc: '밭에 밀을 심고 거둬요', size: [4.0, 3.6], height: 3,
    kind: 'farm', radius: 7, plots: 8, grow: 36, workTime: 2.4, out: 'wheat', tool: 'farmer', cost: { plank: 3, stone: 1 }, work: 9, icon: '🌾',
    fallback: [['tent_a', 0, 0, 0, 1.2], ['hay_bale', 1.6, 0.8, 30, 0.9]],
  },
  windmill: {
    cat: 'prod', name: '풍차', desc: '밀 → 밀가루', size: [3.6, 3.6], height: 7,
    kind: 'process', in: 'wheat', out: 'flour', time: 5, anim: 'work_hands', cost: { plank: 3, stone: 3 }, work: 12, icon: '🌬️',
    fallback: 'windmill',
  },
  bakery: {
    cat: 'prod', name: '빵집', desc: '밀가루 → 빵 (가게에서 팔기도 해요)', size: [4.4, 3.8], height: 4,
    kind: 'process', in: 'flour', out: 'bread', outN: 2, time: 7, anim: 'work_hands', cost: { plank: 3, stone: 2 }, work: 12, icon: '🍞', sfx: 'oven',
    fallback: [['station_bakery', 0, 0, 0, 1.2]],
  },
  tavern: {
    cat: 'shop', name: '선술집', desc: '저녁에 주민들이 모여 먹고 마시며 이야기해요 (행복 ↑)', size: [6.0, 5.0], height: 5,
    kind: 'shop', cost: { plank: 6, stone: 3 }, work: 14, icon: '🍺', fun: 0.15,
    fallback: [['market_counter', 0, 0.6, 0, 1.2], ['picnic_table', -1.6, -1.2, 0, 1], ['picnic_table', 1.6, -1.2, 0, 1], ['barrel', 2.4, 1.2, 0, 1]],
  },
  shop: {
    cat: 'shop', name: '잡화점', desc: '생활용품을 팔아요. 주민 행복 ↑', size: [5.0, 4.0], height: 4.5,
    kind: 'shop', cost: { plank: 4, stone: 2 }, work: 12, icon: '🧺', fun: 0.08,
    fallback: [['trade_post', 0, 0, 0, 1.1]],
  },
  well: {
    cat: 'public', name: '우물', desc: '마을 사람들이 모여 물을 긷고 이야기해요', size: [2.4, 2.4], height: 3,
    kind: 'public', cost: { stone: 3 }, work: 6, icon: '🪣', fun: 0.04,
    fallback: 'well',
  },
  bench: {
    cat: 'public', name: '벤치', desc: '쉬어 가는 의자', size: [2.2, 1.0], height: 1,
    kind: 'decor', cost: { plank: 1 }, work: 2, icon: '🪑', fallback: [['bench', 0, 0, 0, 1]], slots: [['sit', -0.5, 0.45, 0], ['sit', 0.5, 0.45, 0]],
  },
  lamp: {
    cat: 'public', name: '가로등', desc: '밤길을 밝혀요', size: [0.8, 0.8], height: 2.6,
    kind: 'decor', cost: { plank: 1 }, work: 2, icon: '🏮', fallback: [['lamp_post', 0, 0, 0, 1]], light: true,
  },
  coop: {
    cat: 'farm', name: '닭장', desc: '닭이 달걀을 낳아요', size: [6.0, 5.0], height: 3,
    kind: 'ranch', animal: 'animal_chicken', count: 5, out: 'egg', every: 26, workTime: 2.0, cost: { plank: 3 }, work: 8, icon: '🐔',
    fallback: [['dog_house', -1.6, -1.2, 0, 1.0], ['hay_bale', 1.4, -1.4, 20, 0.8]], fence: true,
  },
  barn: {
    cat: 'farm', name: '외양간', desc: '젖소와 염소가 우유를 줘요 (밀을 먹여요)', size: [10.0, 8.0], height: 4.5,
    kind: 'ranch', animal: 'animal_cow', animal2: 'animal_goat', count: 3, out: 'milk', every: 30, feed: 'wheat', workTime: 3.0, cost: { plank: 5, stone: 2 }, work: 12, icon: '🐄',
    fallback: [['worker_hut', -2.8, -2.4, 0, 1.0], ['hay_bale', 1.5, -2.8, 0, 1.0]], fence: true,
  },
  sheepfold: {
    cat: 'farm', name: '양 우리', desc: '양털을 깎아요', size: [8.0, 7.0], height: 3,
    kind: 'ranch', animal: 'animal_sheep', count: 4, out: 'wool', every: 40, workTime: 3.0, cost: { plank: 4 }, work: 10, icon: '🐑',
    fallback: [['tent_a', -2.2, -2.0, 0, 1.0]], fence: true,
  },
  pigsty: {
    cat: 'farm', name: '축사', desc: '돼지와 소를 키워 고기를 얻어요 (밀을 먹여요)', size: [8.0, 6.0], height: 3,
    kind: 'ranch', animal: 'animal_pig', animal2: 'animal_cattle', count: 4, out: 'meat', every: 50, feed: 'wheat', workTime: 3.0, cost: { plank: 4, stone: 1 }, work: 10, icon: '🐷',
    fallback: [['tent_a', -2.2, -1.6, 0, 0.9], ['barrel', 2.4, -1.8, 0, 1]], fence: true,
  },
  orchard: {
    cat: 'farm', name: '과수원', desc: '사과나무에서 사과를 따요', size: [9.0, 8.0], height: 4,
    kind: 'orchard', out: 'apple', trees: 6, every: 35, workTime: 2.5, tool: 'farmer', cost: { plank: 3 }, work: 9, icon: '🍎',
    fallback: [['upgrade_bench', -3.0, -2.8, 0, 0.9]],
  },
  apiary: {
    cat: 'farm', name: '양봉장', desc: '벌들이 꿀을 모아요', size: [6.0, 5.0], height: 3,
    kind: 'orchard', out: 'honey', hives: 5, every: 45, workTime: 3.0, tool: 'farmer', cost: { plank: 3 }, work: 8, icon: '🍯',
    fallback: [['crate', -1.5, -1, 0, 0.9], ['crate', 0, -1, 0, 0.9], ['crate', 1.5, -1, 0, 0.9], ['crate', -0.7, 0.8, 0, 0.9], ['crate', 0.8, 0.8, 0, 0.9]],
  },
  fishing: {
    cat: 'prod', name: '낚시터', desc: '물가에서 생선을 낚아요 (호수 옆, 정문이 물을 보게)', size: [4.0, 5.0], height: 3,
    kind: 'fishing', out: 'fish', workTime: 7, tool: 'fisherman', cost: { plank: 3 }, work: 8, icon: '🎣', water: true,
    fallback: [['dock_pier', 0, 1.0, 0, 1.0], ['boat_small', 1.6, 1.8, 30, 0.8], ['fish_net', -1.2, -1.2, 0, 0.6]],
  },
  dairy: {
    cat: 'prod', name: '치즈 공방', desc: '우유 → 치즈', size: [4.6, 4.0], height: 4,
    kind: 'process', in: 'milk', out: 'cheese', time: 8, anim: 'work_hands', cost: { plank: 4, stone: 2 }, work: 10, icon: '🧀',
    fallback: [['station_smokehouse', 0, 0, 0, 1.2]],
  },
  watchtower: {
    cat: 'public', name: '화톳불 망루', desc: '온기를 퍼뜨려 영토를 넓혀요', size: [3.0, 3.0], height: 5,
    kind: 'tower', cost: { plank: 4, stone: 2 }, work: 10, icon: '🔥',
    fallback: [['flag_pole', 0, 0, 0, 1.2], ['campfire', 0, 1.0, 0, 1.4]],
  },
  beacon: {
    cat: 'public', name: '봄의 봉화대', desc: '봉화를 밝히면 겨울이 물러가고 봄이 와요! 이웃 마을보다 먼저 밝혀 보세요', size: [5.0, 5.0], height: 9,
    kind: 'beacon', cost: { plank: 20, stone: 30, bread: 10, honey: 3 }, work: 40, icon: '🏮',
    fallback: [['campfire', 0, 0, 0, 2.0], ['flag_pole', 1.6, 1.6, 0, 1.4], ['flag_pole', -1.6, 1.6, 0, 1.4]],
  },
  market: {
    cat: 'shop', name: '시장 가판대', desc: '외부 상인이 여기 머물러요. 주민들이 장을 봐요', size: [4.0, 3.0], height: 3,
    kind: 'shop', cost: { plank: 3 }, work: 6, icon: '🛒', fun: 0.06, fallback: [['market_counter', 0, 0, 0, 1.1]],
  },
};

/** 장식: 상인에게 사거나 카드로 얻어서 바로 놓아요 (주변 주민 기분 ↑) */
export const DECOS = {
  deco_fountain:       { name: '분수', joy: 0.08, size: [2.4, 2.4], fallback: [['ice_rink', 0, 0, 0, 0.45]] },
  deco_flowerbed:      { name: '꽃밭', joy: 0.05, size: [2.0, 1.4], fallback: [['bush_snow', -0.5, 0, 0, 0.7], ['bush_snow', 0.5, 0, 0, 0.6]] },
  deco_painting_easel: { name: '이젤 그림', joy: 0.06, size: [1.2, 1.0], fallback: [['notice_board', 0, 0, 0, 0.8]] },
  deco_gazebo:         { name: '정자', joy: 0.09, size: [3.6, 3.6], fallback: [['picnic_table', 0, 0, 0, 1.0], ['lantern_string', 0, 0, 0, 0.8]] },
  deco_snowman_big:    { name: '큰 눈사람', joy: 0.05, size: [1.6, 1.6], fallback: [['snowman', 0, 0, 0, 1.4]] },
  deco_lantern_post:   { name: '장식 등', joy: 0.03, size: [0.8, 0.8], fallback: [['lamp_post', 0, 0, 0, 1.1]] },
  deco_swing:          { name: '그네', joy: 0.06, size: [2.4, 1.6], fallback: [['kids_swing', 0, 0, 0, 1.0]] },
  statue:              { name: '마을 동상', joy: 0.1, size: [2.0, 2.0], fallback: [['flag_pole', 0, 0, 0, 1.0], ['snowman', 0, 0.4, 0, 1.0]] },
};

/** 외부 상인이 파는 것 (코인) */
export const MERCHANT = [
  { kind: 'deco', key: 'deco_fountain', price: 60, tag: '미술품' },
  { kind: 'deco', key: 'deco_painting_easel', price: 35, tag: '미술품' },
  { kind: 'deco', key: 'statue', price: 80, tag: '미술품' },
  { kind: 'deco', key: 'deco_gazebo', price: 70, tag: '특별한 물건' },
  { kind: 'deco', key: 'deco_swing', price: 30, tag: '특별한 물건' },
  { kind: 'deco', key: 'deco_flowerbed', price: 20, tag: '생활용품' },
  { kind: 'deco', key: 'deco_lantern_post', price: 15, tag: '생활용품' },
  { kind: 'buff', key: 'blanket', name: '따뜻한 담요 묶음', desc: '이틀 동안 모두 기분 ↑ (밤에 춥지 않아요)', price: 25, tag: '생활용품', buff: { mood: 0.12, days: 2 } },
  { kind: 'buff', key: 'tools', name: '튼튼한 연장 세트', desc: '사흘 동안 일하는 속도 +20%', price: 40, tag: '특별한 물건', buff: { work: 0.2, days: 3 } },
  { kind: 'buff', key: 'boots', name: '가벼운 장화', desc: '사흘 동안 걷는 속도 +15%', price: 30, tag: '생활용품', buff: { speed: 0.15, days: 3 } },
  { kind: 'goods', key: 'pack', name: '물건 꾸러미 (판자 10·돌 10)', price: 35, tag: '특별한 물건', goods: { plank: 10, stone: 10 } },
  { kind: 'goods', key: 'spice', name: '먹거리 꾸러미 (빵 8·꿀 2)', price: 30, tag: '생활용품', goods: { bread: 8, honey: 2 } },
];

/** 카드 뽑기 (코인). 확률은 화면에 그대로 공개 */
export const CARD_COST = 30;
export const CARDS = [
  { kind: 'person', rate: 0.05, name: '특별 주민', desc: '특별한 주민이 이사 와요' },
  { kind: 'deco', rate: 0.20, name: '장식', desc: '장식 하나' },
  { kind: 'buff', rate: 0.25, name: '능력 카드', desc: '며칠 동안 마을 능력 ↑' },
  { kind: 'goods', rate: 0.50, name: '물건 꾸러미', desc: '판자·돌·음식 묶음' },
];
export const BUFF_CARDS = [
  { name: '풍년의 축복', desc: '사흘 동안 밭·과수원이 1.5배 빨리 자라요', buff: { grow: 0.5, days: 3 } },
  { name: '힘센 손', desc: '사흘 동안 일하는 속도 +25%', buff: { work: 0.25, days: 3 } },
  { name: '날쌘 발', desc: '이틀 동안 걷는 속도 +20%', buff: { speed: 0.2, days: 2 } },
  { name: '잔치 기분', desc: '이틀 동안 모두 기분 좋음', buff: { mood: 0.15, days: 2 } },
];
export const SPECIAL_PEOPLE = [
  { look: 'npc_bard', name: '음유시인 라온', gender: 'm', trait: 'cheerful' },
  { look: 'npc_blacksmith', name: '대장장이 강철', gender: 'm', trait: 'diligent' },
  { look: 'npc_fashion', name: '멋쟁이 루비', gender: 'f', trait: 'brave' },
  { look: 'npc_merchant', name: '떠돌이 상인 바람', gender: 'm', trait: 'lazy' },
];
export const BUILD_MENU = {
  house: ['house'],
  prod: ['woodcutter', 'quarry', 'sawmill', 'windmill', 'bakery', 'dairy', 'fishing'],
  farm: ['farm', 'coop', 'barn', 'sheepfold', 'pigsty', 'orchard', 'apiary'],
  shop: ['tavern', 'shop', 'market'],
  public: ['well', 'bench', 'lamp', 'watchtower', 'beacon'],
};
/** 온기(영토): 이 건물들이 둘레를 따뜻하게 해서 그 안에만 지을 수 있어요 */
export const WARMTH = { hall: 30, house: 11, watchtower: 22, beacon: 34, tavern: 12 };

/** 길: 흙길 → 자갈길 → 돌길 (업그레이드) */
export const ROADS = {
  dirt:   { name: '흙길',   width: 2.0, speed: 1.0,  cost: null, color: 0xb59473, tex: 'assets/ground/ground_dirt.png' },
  gravel: { name: '자갈길', width: 2.2, speed: 1.15, cost: { stone: 1 }, per: 6, color: 0xb6b0a6, tex: 'assets/ground/ground_rock.png' },
  stone:  { name: '돌길',   width: 2.4, speed: 1.3,  cost: { stone: 2 }, per: 6, color: 0xc9c2b6, tex: 'assets/ground/ground_plaza.png' },
};
export const ROAD_ORDER = ['dirt', 'gravel', 'stone'];

export const NUM = {
  mapSize: 140,
  walkSpeed: 1.9,      // m/s (흙길 기준), 눈밭은 offRoad 배
  offRoad: 0.7,
  inputCap: 4, outputCap: 4,
  stumpTime: 40, regrowEvery: 6,
  rockAmount: 6,
  dayLength: 240,      // 하루 길이(초, 1배속)
  daysPerSeason: 4,
  foodPerDay: 0.4,
  immigrantEvery: 1.3,
  start: { log: 4, plank: 34, stone: 18, wheat: 0, flour: 0, bread: 0, fish: 40 },
  startCoins: 40,
  merchantEvery: 2,     // 외부 상인이 오는 간격(일)
};

export const SEASONS = [
  { name: '겨울', tint: 0xffffff },
  { name: '봄',   tint: 0xdcefd0 },
  { name: '여름', tint: 0xcde7b6 },
  { name: '가을', tint: 0xf1dfc2 },
];

export const LOOKS = {
  m: ['npc_young_man', 'npc_uncle', 'npc_blacksmith', 'npc_merchant', 'npc_bard', 'npc_yellow', 'npc_blue'],
  f: ['npc_aunt', 'npc_herbalist', 'npc_fashion', 'npc_red', 'npc_teen_girl'],
  oldM: ['npc_grandpa'], oldF: ['npc_grandma'],
  kidM: ['npc_kid_boy', 'npc_kid_prankster'], kidF: ['npc_kid_girl'],
};
export const WORK_LOOKS = ['lumberjack', 'miner', 'farmer'];
export const NAMES = {
  m: ['도윤', '태오', '민준', '서준', '하준', '지호', '건우', '우진', '현우', '선우', '은호', '시우', '유찬', '이안', '로운', '주원', '예준'],
  f: ['서연', '하은', '지유', '서아', '하린', '수아', '지안', '윤서', '채원', '다은', '소율', '예린', '나은', '아린', '시아', '유나', '봄이'],
};
export const TRAITS = {
  diligent: { name: '성실', work: 1.15 },
  lazy:     { name: '느긋', work: 0.85, grumble: 0.5 },
  cheerful: { name: '명랑', mood: 0.1, cheer: 0.5 },
  brave:    { name: '씩씩', speed: 1.1, brave: 0.6 },
  shy:      { name: '수줍', social: 0.6 },
  grumpy:   { name: '투덜', mood: -0.05, grumble: 0.6 },
};
export const LINES = {
  tired: ['휴, 무거워…', '힘들다~', '조금만 쉬자', '아이고 허리야'],
  grumble: ['에휴, 하기 싫다', '또 일이야?', '쳇…', '나중에 하면 안 돼?'],
  happy: ['좋아 좋아!', '기분 좋다~', '오늘 날씨 최고!', '헤헤'],
  brave: ['힘내자!', '맡겨 줘!', '영차!', '이 정도쯤이야!'],
  chat: ['그거 들었어?', '하하하!', '정말?', '오늘 뭐 먹지?', '눈이 많이 왔네', '우리 마을 좋다', '저녁에 선술집 갈래?'],
  love: ['우리 같이 걸을래?', '오늘 예쁘다…', '너랑 있으면 좋아'],
  hungry: ['배고파…', '먹을 게 없네'],
  cold: ['추워…', '집이 있었으면…'],
  sad: ['편히 쉬세요…', '보고 싶을 거야…'],
  party: ['축하해!', '오래오래 행복하게!', '건배!'],
  wait: ['재료가 아직이네…', '판자 언제 와?'],
  build: ['뚝딱뚝딱!', '조금만 더!', '튼튼하게!'],
  home: ['역시 집이 최고야', '오늘도 수고했어'],
  eat: ['맛있다!', '냠냠', '이 빵 최고야'],
  read: ['흠… 재밌네', '이 책 좋다'],
  cook: ['오늘은 수프!', '간이 딱 맞네'],
  tea: ['차 한 잔 할래?', '따뜻하다~'],
};

// 장식도 건물처럼 놓을 수 있게 (공사 없이 바로)
for (const [k, d] of Object.entries(DECOS)) {
  BUILDINGS[k] = { cat: 'deco', name: d.name, desc: '장식 · 둘레 주민 기분 +' + Math.round(d.joy * 100), size: d.size, height: 2.5, kind: 'decoration', deco: true, joy: d.joy, fallback: d.fallback, work: 0, icon: '🌷' };
}
