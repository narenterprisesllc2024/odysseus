// sovi-cleanup.js — runs on every page load, kills any stale service worker
// + cache from the previous "Sovi" install (months-old AionUi fork era).
// The current Odysseus SW lives at /static/sw.js — anything else is stale.
(function () {
  if (!('serviceWorker' in navigator)) return;

  navigator.serviceWorker.getRegistrations().then((regs) => {
    let killed = 0;
    for (const reg of regs) {
      const url = (reg.active && reg.active.scriptURL) || (reg.installing && reg.installing.scriptURL) || '';
      // Keep ONLY the current Odysseus SW; nuke anything else.
      if (!url.includes('/static/sw.js')) {
        reg.unregister();
        killed++;
        console.log('[sovi-cleanup] unregistered stale SW:', url);
      }
    }
    if (killed > 0 && 'caches' in window) {
      caches.keys().then((keys) => {
        for (const key of keys) {
          if (!key.startsWith('odysseus-')) {
            caches.delete(key);
            console.log('[sovi-cleanup] deleted stale cache:', key);
          }
        }
      }).then(() => {
        // One forced reload so the user immediately sees the new Odysseus.
        if (!sessionStorage.getItem('sovi-cleanup-reloaded')) {
          sessionStorage.setItem('sovi-cleanup-reloaded', '1');
          location.reload();
        }
      });
    }
  }).catch(() => {});
})();
