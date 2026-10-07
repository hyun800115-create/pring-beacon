// =====================================================================
//  게임 안의 모든 글자 (한국어 ko / 영어 en)
//  {n}, {name} 같은 부분은 게임이 숫자/이름으로 바꿔 넣습니다.
// =====================================================================

export const STRINGS = {
  ko: {
    title: '서리마을 개척기',
    subtitle: 'Frost Village',
    tapToStart: '탭하여 시작',
    clickToStart: '클릭하여 시작',
    pcHint: 'WASD · 방향키 · 마우스 드래그로 이동',
    loading: '불러오는 중…',
    continueHint: '이어서 하기',

    // HUD / 토스트
    bagFull: '가방이 가득 찼어요!',
    notEnoughCoins: '코인이 부족해요',
    stationFull: '가득 찼어요!',
    saved: '저장되었습니다',
    resetDone: '처음부터 다시 시작해요',
    noSave: '이 환경에서는 진행 상황이 저장되지 않아요',
    trash: '버리기',

    // 설정
    settings: '설정',
    sound: '효과음',
    music: '음악',
    language: '언어',
    langName: '한국어',
    reset: '처음부터 하기',
    resetConfirm: '정말 처음부터 다시 할까요?\n모든 진행 상황이 사라져요.',
    yes: '네, 다시 할래요',
    no: '아니요',
    on: '켜짐',
    off: '꺼짐',
    close: '닫기',

    // 튜토리얼 / 목표
    obj_fish: '그물 앞에 서서 물고기를 모으세요',
    obj_grill: '생선을 그릴 발판에 내려놓으세요',
    obj_take: '구운 생선을 가져가세요',
    obj_sell: '구운 생선을 판매대에 놓으세요',
    obj_cash: '손님이 낸 코인을 주우세요',
    obj_unlock: '코인을 들고 발판 위에 서 보세요',
    obj_wait: '손님이 오고 있어요…',
    obj_forest_1: '나무 앞에 서서 통나무를 모으세요',
    obj_forest_2: '통나무를 제재소에 넣으세요',
    obj_forest_3: '판자를 가져가세요',
    obj_forest_4: '판자를 교역소에 파세요',
    obj_farm_1: '다 익은 밀 앞에 서서 밀을 거두세요',
    obj_farm_2: '밀을 빵 오븐에 넣으세요',
    obj_farm_3: '빵을 가져가세요',
    obj_farm_4: '빵을 판매대에 놓으세요',
    obj_mine_1: '바위 앞에 서서 광석을 캐세요',
    obj_mine_2: '광석을 제련소에 넣으세요',
    obj_mine_3: '주괴를 가져가세요',
    obj_mine_4: '주괴를 교역소에 파세요',
    obj_hunt_1: '사슴이나 멧돼지 곁에 서서 잡으세요',
    obj_hunt_2: '생고기를 훈제장에 넣으세요',
    obj_hunt_3: '훈제 고기를 가져가세요',
    obj_hunt_4: '훈제 고기를 판매대에 놓으세요',
    obj_upgrade: '작업대에서 가방을 업그레이드하세요',
    obj_next: '다음 목표: {name} ({cost} 코인)',
    obj_trash: '받아 줄 곳이 없어요 — 모닥불 발판에서 버리세요',
    obj_sell_any: '들고 있는 것을 먼저 파세요',
    obj_courier: '배달꾼을 고용하면 일꾼이 물건을 대신 날라요',

    // 발판 이름
    hire_fisherman: '어부 고용',
    hire_lumberjack: '나무꾼 고용',
    hire_farmer: '농부 고용',
    hire_miner: '광부 고용',
    hire_hunter: '사냥꾼 고용',
    hire2_fisherman: '생선 배달꾼',
    hire2_lumberjack: '판자 배달꾼',
    hire2_farmer: '빵 배달꾼',
    hire2_miner: '주괴 배달꾼',
    hire2_hunter: '고기 배달꾼',
    zone_forest: '벌목장',
    zone_farm: '농장',
    zone_mine: '광산',
    zone_hunt: '사냥터',
    up_capacity: '가방',
    up_speed: '신발',
    max: 'MAX',
    level: 'Lv.{n}',

    // 구역 / 시설 이름
    w_fisherman: '어부', w_lumberjack: '나무꾼', w_farmer: '농부', w_miner: '광부', w_hunter: '사냥꾼', w_porter: '배달꾼',
    z_plaza: '광장',
    z_forest: '소나무 숲',
    z_farm: '밀밭',
    z_mine: '광산',
    z_hunt: '사냥터',
    unlocked: '{name} 열림!',
    hired: '{name} 합류!',
    upgraded: '{name} 업그레이드!',
    villageComplete: '마을 완성!',
    villageCompleteSub: '모든 구역이 열렸어요! 배달꾼을 고용해 보세요',
    newCustomer: '손님이 왔어요',
    capacityUp: '가방 +{n}',
    speedUp: '속도 업!',
  },

  en: {
    title: 'Frost Village',
    subtitle: '서리마을 개척기',
    tapToStart: 'Tap to start',
    clickToStart: 'Click to start',
    pcHint: 'Move with WASD · arrow keys · mouse drag',
    loading: 'Loading…',
    continueHint: 'Continue',

    bagFull: 'Your bag is full!',
    notEnoughCoins: 'Not enough coins',
    stationFull: 'It\'s full!',
    saved: 'Saved',
    resetDone: 'Starting over',
    noSave: 'Progress cannot be saved here',
    trash: 'Discard',

    settings: 'Settings',
    sound: 'Sound',
    music: 'Music',
    language: 'Language',
    langName: 'English',
    reset: 'Reset progress',
    resetConfirm: 'Really start over?\nAll progress will be lost.',
    yes: 'Yes, reset',
    no: 'No',
    on: 'On',
    off: 'Off',
    close: 'Close',

    obj_fish: 'Stand by the net to catch fish',
    obj_grill: 'Drop the fish on the grill pad',
    obj_take: 'Pick up the grilled fish',
    obj_sell: 'Put the grilled fish on the counter',
    obj_cash: 'Collect the coins',
    obj_unlock: 'Stand on the pad with your coins',
    obj_wait: 'Customers are coming…',
    obj_forest_1: 'Stand by a tree to chop logs',
    obj_forest_2: 'Put the logs into the sawmill',
    obj_forest_3: 'Pick up the planks',
    obj_forest_4: 'Sell the planks at the trade post',
    obj_farm_1: 'Stand by ripe wheat to harvest it',
    obj_farm_2: 'Put the wheat into the oven',
    obj_farm_3: 'Pick up the bread',
    obj_farm_4: 'Put the bread on the counter',
    obj_mine_1: 'Stand by a rock to mine ore',
    obj_mine_2: 'Put the ore into the smelter',
    obj_mine_3: 'Pick up the ingots',
    obj_mine_4: 'Sell the ingots at the trade post',
    obj_hunt_1: 'Stand next to a deer or boar to catch it',
    obj_hunt_2: 'Put the meat into the smokehouse',
    obj_hunt_3: 'Pick up the smoked meat',
    obj_hunt_4: 'Put the smoked meat on the counter',
    obj_upgrade: 'Upgrade your backpack at the workbench',
    obj_next: 'Next goal: {name} ({cost} coins)',
    obj_trash: 'Nobody takes these — throw them in the fire',
    obj_sell_any: 'Sell what you are carrying first',
    obj_courier: 'Hire couriers to carry goods for you',

    hire_fisherman: 'Hire Fisher',
    hire_lumberjack: 'Hire Lumberjack',
    hire_farmer: 'Hire Farmer',
    hire_miner: 'Hire Miner',
    hire_hunter: 'Hire Hunter',
    hire2_fisherman: 'Fish Courier',
    hire2_lumberjack: 'Plank Courier',
    hire2_farmer: 'Bread Courier',
    hire2_miner: 'Ingot Courier',
    hire2_hunter: 'Meat Courier',
    zone_forest: 'Lumber Camp',
    zone_farm: 'Farm',
    zone_mine: 'Mine',
    zone_hunt: 'Hunting Ground',
    up_capacity: 'Backpack',
    up_speed: 'Boots',
    max: 'MAX',
    level: 'Lv.{n}',

    w_fisherman: 'Fisher', w_lumberjack: 'Lumberjack', w_farmer: 'Farmer', w_miner: 'Miner', w_hunter: 'Hunter', w_porter: 'Courier',
    z_plaza: 'Plaza',
    z_forest: 'Pine Forest',
    z_farm: 'Wheat Farm',
    z_mine: 'Mine',
    z_hunt: 'Hunting Ground',
    unlocked: '{name} unlocked!',
    hired: '{name} joined!',
    upgraded: '{name} upgraded!',
    villageComplete: 'Village Complete!',
    villageCompleteSub: 'Every area is open! Hire couriers next',
    newCustomer: 'A customer arrived',
    capacityUp: 'Bag +{n}',
    speedUp: 'Speed up!',
  },
};

let current = 'ko';

export function detectLang() {
  try {
    const nav = (navigator.language || navigator.userLanguage || 'ko').toLowerCase();
    return nav.startsWith('ko') ? 'ko' : 'en';
  } catch (e) { return 'ko'; }
}

export function setLang(l) { current = STRINGS[l] ? l : 'ko'; }
export function getLang() { return current; }

export function t(key, params) {
  const table = STRINGS[current] || STRINGS.ko;
  let s = table[key];
  if (s === undefined) s = STRINGS.ko[key];
  if (s === undefined) return key;
  if (params) for (const k in params) s = s.split('{' + k + '}').join(String(params[k]));
  return s;
}

export const FONT = "Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif";

/** 12345 -> "12,345" */
export function fmt(n) { return String(Math.floor(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
