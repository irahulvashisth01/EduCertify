/*
=========================================================
 EDUCERTIFY — PROGRESSIVE WEB APP
 SERVICE WORKER
 Version: 2.0.0
=========================================================
*/

const CACHE_NAME = "educertify-v2";

const APP_SHELL = [
    "/",
    "/manifest.json",
    "/static/manifest.json",
    "/static/images/icon-192.png",
    "/static/images/icon-512.png"
];


/* ========================================================
   INSTALL
======================================================== */

self.addEventListener("install", event => {

    console.log(
        "[EduCertify SW] Installing..."
    );

    event.waitUntil(

        caches.open(CACHE_NAME)
            .then(cache => {

                return cache.addAll(APP_SHELL);

            })
            .then(() => {

                console.log(
                    "[EduCertify SW] Installation complete."
                );

                return self.skipWaiting();

            })

    );

});


/* ========================================================
   ACTIVATE
======================================================== */

self.addEventListener("activate", event => {

    console.log(
        "[EduCertify SW] Activating..."
    );

    event.waitUntil(

        caches.keys()
            .then(cacheNames => {

                return Promise.all(

                    cacheNames
                        .filter(
                            cacheName =>
                                cacheName !== CACHE_NAME
                        )
                        .map(
                            cacheName =>
                                caches.delete(cacheName)
                        )

                );

            })
            .then(() => {

                console.log(
                    "[EduCertify SW] Old caches removed."
                );

                return self.clients.claim();

            })

    );

});


/* ========================================================
   FETCH
======================================================== */

self.addEventListener("fetch", event => {

    const request = event.request;

    /*
    Only handle GET requests.
    */
    if (request.method !== "GET") {
        return;
    }

    /*
    Ignore browser extension requests.
    */
    const url = new URL(request.url);

    if (
        url.protocol !== "http:" &&
        url.protocol !== "https:"
    ) {
        return;
    }


    /* ====================================================
       PAGE NAVIGATION
       Network First
    ==================================================== */

    if (request.mode === "navigate") {

        event.respondWith(

            fetch(request)
                .then(response => {

                    if (
                        response &&
                        response.ok
                    ) {

                        const responseClone =
                            response.clone();

                        caches.open(CACHE_NAME)
                            .then(cache => {

                                cache.put(
                                    request,
                                    responseClone
                                );

                            });

                    }

                    return response;

                })
                .catch(() => {

                    return caches.match(
                        request
                    ).then(cachedResponse => {

                        if (cachedResponse) {
                            return cachedResponse;
                        }

                        return caches.match(
                            "/"
                        );

                    });

                })

        );

        return;
    }


    /* ====================================================
       STATIC FILES
       Cache First
    ==================================================== */

    if (
        url.pathname.startsWith("/static/") ||
        request.destination === "style" ||
        request.destination === "script" ||
        request.destination === "image" ||
        request.destination === "font"
    ) {

        event.respondWith(

            caches.match(request)
                .then(cachedResponse => {

                    if (cachedResponse) {

                        /*
                        Update cache in background.
                        */

                        fetch(request)
                            .then(response => {

                                if (
                                    response &&
                                    response.ok
                                ) {

                                    caches.open(
                                        CACHE_NAME
                                    ).then(cache => {

                                        cache.put(
                                            request,
                                            response
                                        );

                                    });

                                }

                            })
                            .catch(() => {});

                        return cachedResponse;
                    }


                    return fetch(request)
                        .then(response => {

                            if (
                                response &&
                                response.ok
                            ) {

                                const responseClone =
                                    response.clone();

                                caches.open(
                                    CACHE_NAME
                                ).then(cache => {

                                    cache.put(
                                        request,
                                        responseClone
                                    );

                                });

                            }

                            return response;

                        });

                })

        );

    }

});


/* ========================================================
   MESSAGE
======================================================== */

self.addEventListener("message", event => {

    if (!event.data) {
        return;
    }


    if (
        event.data.type ===
        "SKIP_WAITING"
    ) {

        self.skipWaiting();

    }

});