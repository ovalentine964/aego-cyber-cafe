/**
 * Aego Cyber Cafe — Service Worker
 * Offline-first caching strategy
 */

const CACHE_NAME = 'aego-kiosk-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/service.html',
  '/payment.html',
  '/admin.html',
  '/style.css',
  '/app.js'
];

const OFFLINE_FALLBACK = '/index.html';

// === INSTALL ===
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// === ACTIVATE ===
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

// === FETCH — Network-first for API, Cache-first for static ===
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // API requests: network-first with offline fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache successful GET API responses
          if (response.ok) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, cloned);
            });
          }
          return response;
        })
        .catch(() => {
          // Try cache on network failure
          return caches.match(event.request).then((cached) => {
            if (cached) return cached;
            // Return offline response for API calls
            return new Response(
              JSON.stringify({
                error: 'Offline',
                message: 'This feature requires internet. Your request has been queued.'
              }),
              {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
              }
            );
          });
        })
    );
    return;
  }

  // Static assets: cache-first, then network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        // Return cached, update in background
        const fetchPromise = fetch(event.request)
          .then((response) => {
            if (response.ok) {
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(event.request, response.clone());
              });
            }
            return response;
          })
          .catch(() => cached);

        return cached;
      }

      // Not in cache, try network
      return fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, cloned);
            });
          }
          return response;
        })
        .catch(() => {
          // Offline fallback for navigation requests
          if (event.request.mode === 'navigate') {
            return caches.match(OFFLINE_FALLBACK);
          }
          return new Response('Offline', { status: 503 });
        });
    })
  );
});

// === BACKGROUND SYNC ===
self.addEventListener('sync', (event) => {
  if (event.tag === 'offline-queue') {
    event.waitUntil(syncOfflineQueue());
  }
});

async function syncOfflineQueue() {
  try {
    const clients = await self.clients.matchAll();
    clients.forEach((client) => {
      client.postMessage({ type: 'sync-offline-queue' });
    });
  } catch (err) {
    console.error('[SW] Sync failed:', err);
  }
}

// === PUSH NOTIFICATIONS ===
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const options = {
    body: data.body || 'You have a notification from Aego Cyber Cafe',
    icon: '/icon-192.png',
    badge: '/badge-72.png',
    vibrate: [200, 100, 200],
    data: data.url || '/',
    actions: data.actions || []
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Aego Cyber Cafe', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.openWindow(event.notification.data || '/')
  );
});
