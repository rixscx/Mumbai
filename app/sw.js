/* Service worker — the thing that makes this work in a tunnel, and installable.

   Strategy, deliberately boring:
     - the app shell and the dataset are precached on install, so a cold start
       with no network works on first launch after installing;
     - navigations are cache-first with a network revalidate, because a trip
       companion that waits on a hotel wifi timeout before drawing is useless;
     - Google Places calls are NEVER cached or intercepted. They are live data
       with their own terms, and a stale "open now" is worse than none.

   CACHE is rewritten by tools/build_app_data.py from a hash of the precached
   files. Do not edit it by hand — if it stops changing, phones keep serving an
   old app forever and that failure is invisible until someone reports a bug
   that was fixed weeks ago.
*/
const CACHE = "mumbai-c57069364a0d";

const SHELL = [
  "./",
  "index.html",
  "app.css",
  "app.js",
  "places.json",
  "trip.json",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/maskable-512.png",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const { request } = e;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Third-party live data is none of this cache's business.
  if (url.origin !== self.location.origin) return;

  // Navigations always resolve to the shell so deep links survive a cold start.
  if (request.mode === "navigate") {
    e.respondWith(
      caches.match("index.html").then(hit => hit || fetch(request))
    );
    return;
  }

  e.respondWith(
    caches.match(request).then(hit => {
      const fresh = fetch(request)
        .then(res => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(request, copy));
          }
          return res;
        })
        .catch(() => hit);          // offline: whatever we already have
      return hit || fresh;
    })
  );
});
