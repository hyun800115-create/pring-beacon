// Logical layout size vs. real canvas resolution.
// All layout code works in a 720-wide logical space (height 1280..1600 follows the screen's aspect).
// The canvas itself is rendered at k x that size (k from devicePixelRatio, max 2) so text and art
// stay sharp on high-density phones; every camera multiplies its zoom by k.

export const MAX_RENDER_SCALE = 2;

export const View = {
  W: 720,          // logical width
  H: 1280,         // logical height
  k: 1,            // canvas pixels per logical pixel
  forceK: 0,       // set to 1 when a weak GPU cannot keep up at the sharper scale
  safeTop: 0,      // notch / status-bar inset in logical px (Capacitor / standalone apps)
  safeBottom: 0,   // home-indicator inset in logical px

  /** camera for a screen-space scene (title, HUD): layout in logical px from the top-left */
  applyUI(cam) {
    cam.setOrigin(0, 0);
    cam.setZoom(this.k);
  },

  /** canvas px -> logical px (pointer positions) */
  toLogical(v) { return v / this.k; },
};
