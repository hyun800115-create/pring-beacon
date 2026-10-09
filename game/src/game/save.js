// 저장하기·불러오기 (저장 팀이 채울 자리). main.js 는 아래 함수만 부른다.
export class SaveSystem {
  constructor(game) { this.g = game; }
  /** 시작할 때: 저장이 있으면 "이어하기/새로 시작"을 물어보고, 이어하면 불러온 뒤 true */
  async offerContinue() { return false; }
  /** 매 프레임 (자동 저장 등) */
  update(real) { void real; }
  /** 자동 시험용 함수 등록 */
  api(obj) { void obj; }
}
