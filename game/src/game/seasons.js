// 계절 모습 (계절 팀이 채울 자리): 나무·땅·지붕 눈·날리는 것.
export class Seasons {
  constructor(game) { this.g = game; this.groundTint = null; }
  /** 세계가 만들어진 뒤(새 게임·불러오기 모두) 한 번 */
  async init() {}
  /** 매 프레임 (real = 실제 초, dt = 게임 초) */
  update(real, dt) { void real; void dt; }
  api(obj) { void obj; }
}
