// Service worker del sito: dal 20/11/2026 il sito non si installa più come app e non salva più copie delle pagine.
// Questo file resta per chi ha ancora il service worker di prima (chiunque abbia aperto il sito, non solo chi l'aveva
// installato). Al primo controllo il browser lo scarica al posto del vecchio, e lui:
// - si attiva subito, senza aspettare che le pagine aperte si chiudano;
// - svuota le copie salvate del sito;
// - si toglie da solo: dalla visita dopo il sito non ha più nessun service worker.
// Non risponde a nessuna richiesta (niente «fetch»): anche nel frattempo tutto arriva dalla rete, e le pagine aperte non
// serve ricaricarle. Non va cancellato: un 404 nel controllo non toglie il service worker vecchio, che resterebbe a
// servire le copie salvate.
self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((nomi) => Promise.all(nomi.map((n) => caches.delete(n))))
      .then(() => self.registration.unregister()),
  );
});
