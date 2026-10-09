// 게임 화면과 앱 사이의 작은 다리. 게임 쪽에서는 window.smApp 으로 쓸 수 있다.
//   window.smApp.pc           → true (PC 앱에서 돌고 있음)
//   window.smApp.fullscreen() → 전체 화면 켜기/끄기
//   window.smApp.quit()       → 앱 끄기 (예: 메뉴의 "게임 끄기" 버튼)
'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smApp', Object.freeze({
  pc: true,
  fullscreen: () => ipcRenderer.send('sm:fullscreen'),
  quit: () => ipcRenderer.send('sm:quit'),
}));

// F11 · Alt+Enter = 전체 화면. (진짜 키보드는 앱 쪽에서 먼저 받지만, 혹시 화면까지 온 키도 여기서 받는다)
window.addEventListener('keydown', (e) => {
  if (e.key === 'F11' || (e.altKey && e.key === 'Enter')) { e.preventDefault(); ipcRenderer.send('sm:fullscreen'); }
}, true);
