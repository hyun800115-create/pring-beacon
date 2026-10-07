// 봄날의 행진 (3D) 데이터: 물건, 건물(분류별), 길, 주민, 숫자. 밸런스 숫자는 여기서만 고친다.
// 크기는 미터. 건물 모델은 assets3d/buildings/<key>.glb (실내 있음) 가 있으면 그것을, 없으면 fallback 소품 조합을 쓴다.

export const ITEMS = {
  log:   { name: '통나무', model: 'item_log' },
  plank: { name: '판자',   model: 'item_plank' },
  stone: { name: '돌',     model: 'rock_rubble', scale: 0.45 },
  wheat: { name: '밀',     model: 'item_wheat' },
  flour: { name: '밀가루', model: null, color: 0xeee3c8 },
  bread: { name: '빵',     model: 'item_bread', food: true },
  fish:  { name: '생선',   model: 'item_fish_cooked', food: true },
};
export const ITEM_ORDER = ['log', 'plank', 'stone', 'wheat', 'flour', 'bread', 'fish'];

export const CATEGORIES = [
  { key: 'house', name: '주택', icon: '🏠' },
  { key: 'prod', name: '생산', icon: '⚒️' },
  { key: 'shop', name: '상업', icon: '🏪' },
  { key: 'public', name: '공공', icon: '🏛️' },
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
};
export const BUILD_MENU = {
  house: ['house'],
  prod: ['woodcutter', 'quarry', 'sawmill', 'farm', 'windmill', 'bakery'],
  shop: ['tavern', 'shop'],
  public: ['well', 'bench', 'lamp'],
};

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
