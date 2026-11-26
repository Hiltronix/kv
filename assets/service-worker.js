/* global self, caches */
// Remove caches from earlier releases. Live KVM data must never be cached.
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting())
})
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith('kvm-cache-')) await caches.delete(name)
    }
    await self.registration.unregister()
  })())
})
