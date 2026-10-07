// Boot: settings + language, then the preloader.
import { Settings } from '../core/Save.js';
import { setLang, detectLang } from '../data/strings.js';
import { Audio } from '../core/Audio.js';

export class Boot extends Phaser.Scene {
  constructor() { super('Boot'); }
  create() {
    Settings.load();
    setLang(Settings.data.lang || detectLang());
    Audio.init(this.game);
    this.scene.start('Preload');
  }
}
