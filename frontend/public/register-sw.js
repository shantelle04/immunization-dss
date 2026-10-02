// The service worker runs only for a built app; the development server serves modules from /src/.
if ("serviceWorker" in navigator && !document.querySelector('script[src^="/src/"]')) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
}
