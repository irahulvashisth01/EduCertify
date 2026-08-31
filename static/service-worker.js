const CACHE_NAME = "sms-portal-v1";

const STATIC_ASSETS = [
    "/",
    "/static/manifest.json",
    "/static/images/icon-192.png",
    "/static/images/icon-512.png"
];


self.addEventListener("install", event => {

    event.waitUntil(

        caches.open(CACHE_NAME)
            .then(cache => {

                return cache.addAll(STATIC_ASSETS);

            })

    );

    self.skipWaiting();

});


self.addEventListener("activate", event => {

    event.waitUntil(

        caches.keys()
            .then(cacheNames => {

                return Promise.all(

                    cacheNames
                        .filter(name => {
                            return name !== CACHE_NAME;
                        })
                        .map(name => {
                            return caches.delete(name);
                        })

                );

            })

    );

    self.clients.claim();

});


self.addEventListener("fetch", event => {

    event.respondWith(

        caches.match(event.request)
            .then(cachedResponse => {

                if (cachedResponse) {
                    return cachedResponse;
                }

                return fetch(event.request);

            })

    );

});