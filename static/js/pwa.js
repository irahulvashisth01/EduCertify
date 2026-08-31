if ("serviceWorker" in navigator) {

    window.addEventListener("load", () => {

        navigator.serviceWorker
            .register("/static/service-worker.js")
            .then(registration => {

                console.log(
                    "PWA service worker registered:",
                    registration.scope
                );

            })
            .catch(error => {

                console.error(
                    "Service worker registration failed:",
                    error
                );

            });

    });

}