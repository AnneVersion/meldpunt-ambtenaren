// ============================================================
// MELDPUNT AMBTENAREN — Service Worker
// ============================================================
// Cache-first voor statische assets, network-first voor API
// ============================================================

var CACHE_NAME = 'meldpunt-v1';
var STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  'https://fonts.googleapis.com/css2?family=DM+Sans:wght@300..800&display=swap',
  'https://fonts.googleapis.com/icon?family=Material+Icons+Round'
];

// Install: cache statische bestanden
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: oude caches verwijderen
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// Fetch: strategie per type
self.addEventListener('fetch', function(e) {
  var url = new URL(e.request.url);

  // API calls + Supabase: altijd network-first
  if (url.pathname.startsWith('/api') ||
      url.hostname.includes('supabase.co') ||
      url.hostname.includes('supabase.in')) {
    e.respondWith(
      fetch(e.request).catch(function() {
        return new Response(JSON.stringify({ error: 'offline' }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // Statische assets: cache-first, dan network
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if (cached) return cached;
      return fetch(e.request).then(function(response) {
        // Cache succesvolle responses
        if (response.ok && e.request.method === 'GET') {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      }).catch(function() {
        // Offline fallback voor navigatie
        if (e.request.mode === 'navigate') {
          return caches.match('/index.html');
        }
      });
    })
  );
});
