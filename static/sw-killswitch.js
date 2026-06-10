// sw-killswitch.js — served at root paths where a stale Sovi SW likely lives.
// Self-unregisters on install, clears its own caches, then claims clients
// so any open tab using the old SW gets the new (no-op) one immediately.
self.addEventListener('install', (e) => {
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    const regs = await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window' });
    for (const c of clients) {
      try { c.navigate(c.url); } catch {}
    }
  })());
});
self.addEventListener('fetch', (e) => {
  // Pass-through; let the network handle everything.
});
