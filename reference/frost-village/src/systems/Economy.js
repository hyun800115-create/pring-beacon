// Coins.

export class Economy {
  constructor(gs, coins = 0) {
    this.gs = gs;
    this.coins = Math.max(0, Math.floor(coins));
    this.earned = 0;
  }
  add(n, wx, wy, fly) {
    n = Math.floor(n);
    if (n <= 0) return;
    this.coins += n;
    this.earned += n;
    const ui = this.gs.ui;
    if (fly && ui && wx !== undefined) ui.coinFly(wx, wy, Math.min(10, Math.max(3, Math.round(n / 4))));
    if (ui) ui.setCoins(this.coins, fly ? 380 : 0);
  }
  spend(n) {
    n = Math.min(this.coins, Math.floor(n));
    this.coins -= n;
    if (this.gs.ui) this.gs.ui.setCoins(this.coins, 0);
    return n;
  }
}
