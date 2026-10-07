// 시제품 데이터: 물건, 건물, 주민, 숫자. 밸런스 숫자는 여기서만 고친다.

/** 물건. tex = [아틀라스, 프레임] (프레임 없음 = 게임이 직접 그린 그림) */
export const ITEMS = {
  log:   { name: '통나무', tex: ['props_items', 'item_log'] },
  plank: { name: '판자',   tex: ['props_items', 'item_plank'] },
  stone: { name: '돌',     tex: ['gen_item_stone', null] },
  wheat: { name: '밀',     tex: ['props_items', 'item_wheat'] },
  flour: { name: '밀가루', tex: ['gen_item_flour', null] },
  bread: { name: '빵',     tex: ['props_items', 'item_bread'], food: true },
  fish:  { name: '생선',   tex: ['props_items', 'item_fish_cooked'], food: true },
};
export const ITEM_ORDER = ['log', 'plank', 'stone', 'wheat', 'flour', 'bread', 'fish'];

/**
 * 건물.
 *  size: 칸 수(정사각형). 깃발은 앞쪽(화면 왼쪽 아래) 가운데 바로 앞 칸.
 *  kind: hq(마을회관·창고) | house(집) | gather(나무·돌) | farm(밀 농사) | process(가공)
 *  decor: [아틀라스, 프레임, 칸 i, 칸 j, 크기] 건물 옆 장식
 */
export const BUILDINGS = {
  hall: {
    name: '마을회관', desc: '마을의 중심. 물건을 모아 두고, 집 없는 주민이 잠을 자요', size: 3,
    sprite: ['props_buildings', 'chief_lodge'], kind: 'hq', buildable: false, sleeps: 6, buildTime: 64,   // 여럿이 함께 지으면 빨라짐 (사람×초)
  },
  house: {
    name: '오두막', desc: '주민이 사는 집. 업그레이드하면 더 많이 살아요', size: 2, kind: 'house', icon: '🏠',
    cost: { plank: 3 }, buildTime: 8,
    levels: [
      { name: '오두막', sprite: ['props_buildings', 'worker_hut'], cap: 2 },
      { name: '큰 오두막', sprite: ['props_buildings', 'worker_hut'], cap: 4, cost: { plank: 4, stone: 2 },
        extra: [['life_props', 'clothesline', 1.7, 0.5, 0.75], ['props_decor', 'firewood_pile', 1.55, -0.2, 0.7]] },
      { name: '통나무집', sprite: ['props_buildings', 'chief_lodge'], scale: 0.72, cap: 6, cost: { plank: 6, stone: 4 } },
    ],
  },
  woodcutter: {
    name: '나무꾼 작업장', desc: '나무를 베어 통나무를 만들어요', size: 2, sprite: ['props_buildings', 'upgrade_bench'],
    decor: [['props_decor', 'firewood_pile', 1.5, -0.1, 0.8]], kind: 'gather', res: 'tree', radius: 7, work: 3.2, out: 'log',
    tool: 'lumberjack', cost: { plank: 2 }, icon: '🪓', buildTime: 6,
  },
  stonecutter: {
    name: '채석장', desc: '바위를 깨서 돌을 만들어요', size: 3, sprite: ['props_buildings', 'mine_entrance'],
    kind: 'gather', res: 'rock', radius: 8, work: 3.6, out: 'stone', tool: 'miner', cost: { plank: 3 }, icon: '⛏️', buildTime: 8,
  },
  sawmill: {
    name: '제재소', desc: '통나무 → 판자', size: 2, sprite: ['props_buildings', 'station_sawmill'],
    kind: 'process', in: 'log', out: 'plank', time: 5, cost: { plank: 2, stone: 2 }, icon: '🪚', buildTime: 8, sfx: 'sfx_saw',
  },
  farm: {
    name: '밀 농장', desc: '밭에 밀을 심고 거둬요', size: 2, sprite: ['props_buildings', 'tent_a'],
    decor: [['props_decor', 'hay_bale', 1.5, -0.15, 0.85]], kind: 'farm', radius: 3, plots: 8, grow: 30, work: 1.8, out: 'wheat',
    tool: 'farmer', cost: { plank: 3, stone: 1 }, icon: '🌾', buildTime: 7,
  },
  windmill: {
    name: '풍차', desc: '밀 → 밀가루', size: 2, sprite: ['gen_windmill', null],
    kind: 'process', in: 'wheat', out: 'flour', time: 5, cost: { plank: 3, stone: 3 }, icon: '🌬️', buildTime: 9,
  },
  bakery: {
    name: '빵집', desc: '밀가루 → 빵', size: 2, sprite: ['props_buildings', 'station_bakery'],
    kind: 'process', in: 'flour', out: 'bread', outN: 2, time: 7, cost: { plank: 3, stone: 2 }, icon: '🍞', buildTime: 9, sfx: 'sfx_oven',
  },
};
export const BUILD_MENU = ['house', 'woodcutter', 'stonecutter', 'sawmill', 'farm', 'windmill', 'bakery'];

export const NUM = {
  flagCap: 8,          // 깃발 하나에 쌓을 수 있는 물건 수
  inputCap: 4,         // 가공 건물이 받아 두는 재료 수
  outputCap: 3,        // 건물 안에 쌓아 두는 결과물 수 (깃발이 꽉 차면)
  walkSpeed: 1.6,      // 사람 걷는 속도, 칸/초
  autoFlagEvery: 4,    // 길에 자동 깃발 간격(칸). 깃발 사이마다 짐꾼 한 명
  maxRoad: 40,         // 한 번에 그릴 수 있는 길 길이(칸)
  stumpTime: 25,       // 그루터기가 사라지는 시간
  regrowEvery: 5,      // 숲이 새 나무를 키우는 간격(초)
  rockAmount: 6,       // 바위 하나에서 나오는 돌
  dayLength: 180,      // 하루 길이(초, 1배속)
  daysPerSeason: 4,
  foodPerDay: 0.4,     // 주민 한 명이 하루에 먹는 양
  immigrantEvery: 1.3, // 이주민이 찾아오는 간격(일)
  start: { log: 4, plank: 30, stone: 16, wheat: 0, flour: 0, bread: 0, fish: 40 },
};

export const SEASONS = [
  { name: '겨울', tint: 0xffffff, sky: 'rgba(120,150,210,0.10)' },
  { name: '봄',   tint: 0xe4f2d2, sky: 'rgba(255,220,240,0.06)' },
  { name: '여름', tint: 0xd5ecbd, sky: 'rgba(255,240,180,0.06)' },
  { name: '가을', tint: 0xf3e2c6, sky: 'rgba(255,190,120,0.08)' },
];

/** 주민 모습 (서리마을 주민 그림). 성별·나이대별 */
export const LOOKS = {
  m: ['npc_young_man', 'npc_uncle', 'npc_blacksmith', 'npc_merchant', 'npc_bard', 'npc_yellow', 'npc_blue'],
  f: ['npc_aunt', 'npc_herbalist', 'npc_fashion', 'npc_red', 'npc_teen_girl'],
  oldM: ['npc_grandpa'], oldF: ['npc_grandma'],
  kidM: ['npc_kid_boy', 'npc_kid_prankster'], kidF: ['npc_kid_girl'],
};
export const NAMES = {
  m: ['도윤', '태오', '민준', '서준', '하준', '지호', '건우', '우진', '현우', '선우', '은호', '시우', '유찬', '이안', '로운'],
  f: ['서연', '하은', '지유', '서아', '하린', '수아', '지안', '윤서', '채원', '다은', '소율', '예린', '나은', '아린', '시아'],
};

/** 성격: 감정 표현 방식이 달라진다 */
export const TRAITS = {
  diligent: { name: '성실', work: 1.1 },
  lazy:     { name: '느긋', work: 0.9, grumble: 0.5 },
  cheerful: { name: '명랑', mood: 0.1, cheer: 0.5 },
  brave:    { name: '씩씩', speed: 1.1, brave: 0.6 },
  shy:      { name: '수줍', social: 0.6 },
  grumpy:   { name: '투덜', mood: -0.05, grumble: 0.6 },
};

/** 일할 때 입는 모습 (작업 동작이 있는 서리마을 캐릭터) */
export const BUILDER_LOOK = 'lumberjack';
export const CHARS_NEEDED = [
  'lumberjack', 'miner', 'farmer',
  ...LOOKS.m, ...LOOKS.f, ...LOOKS.oldM, ...LOOKS.oldF, ...LOOKS.kidM, ...LOOKS.kidF,
];

/** 말풍선 대사 */
export const LINES = {
  tired: ['휴, 무거워…', '힘들다~', '조금만 쉬자', '아이고 허리야'],
  grumble: ['에휴, 하기 싫다', '또 일이야?', '쳇…', '나중에 하면 안 돼?'],
  happy: ['좋아 좋아!', '기분 좋다~', '오늘 날씨 최고!', '헤헤'],
  brave: ['힘내자!', '맡겨 줘!', '영차!', '이 정도쯤이야!'],
  chat: ['그거 들었어?', '하하하!', '정말?', '오늘 뭐 먹지?', '눈이 많이 왔네', '우리 마을 좋다'],
  love: ['우리 같이 걸을래?', '오늘 예쁘다…', '너랑 있으면 좋아'],
  hungry: ['배고파…', '먹을 게 없네'],
  cold: ['추워…', '집이 있었으면…'],
};
