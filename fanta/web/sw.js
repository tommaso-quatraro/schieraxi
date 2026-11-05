// Service worker: tiene in memoria la "scocca" dell'app (pagine, stile, icone) così si apre subito.
// I dati (/api/...) arrivano sempre freschi dal server; se il server non risponde, l'app lo dice.
const VERSIONE = "fanta-208";
const FILE = ["/", "/stile.css", "/app.js", "/impostazioni.js", "/dafare.js", "/primoavvio.js", "/anteprima.js", "/avatar.js", "/live.js", "/testi.js", "/manifest.webmanifest", "/icona.svg", "/icona-180.png", "/icona-192.png", "/caratteri/archivo.woff2"];

// Pagina mostrata quando non c'è rete e nessuna copia salvata (si apre aprendo o ricaricando l'app).
const PAGINA_SENZA_RETE = `<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>SchieraXI: nessuna connessione</title></head><body style="margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;background:#07100b;color:#eaf3ee;font-family:system-ui,sans-serif;text-align:center"><main style="max-width:340px"><h1 style="font-size:22px;margin:0 0 10px">Nessuna connessione</h1><p style="line-height:1.45;color:#b9c9c0;margin:0">SchieraXI non riesce a raggiungere il server. Controlla la connessione e riprova.</p><p style="margin:18px 0 0"><a href="/" style="display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;padding:0 22px;border-radius:999px;background:#3ddc97;color:#07100b;font-weight:650;text-decoration:none">Riprova</a></p></main></body></html>`;
// Senza rete, una pagina aperta dà la scocca salvata (l'app mostra poi gli ultimi dati salvati); se manca, la pagina qui sopra.
function ripiego() {
  return caches.match("/").then(c => c || new Response(PAGINA_SENZA_RETE, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }));
}

// Notifiche web: il server manda titolo e testo, qui si mostrano; un tocco apre l'app.
self.addEventListener("push", e => {
  let d = {};
  try { d = e.data.json(); } catch { d = { title: "SchieraXI", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "SchieraXI", {
    body: d.body || "", icon: "/icona-192.png", badge: "/icona-192.png", tag: d.tag || undefined, data: { url: d.url || "/" } }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  let vista = null;
  try { vista = new URL(url, self.location.origin).searchParams.get("vista"); } catch { /* indirizzo strano */ }
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(lista => {
    const aperta = lista.find(c => "focus" in c);
    if (!aperta) return self.clients.openWindow(url);
    if (vista) aperta.postMessage({ tipo: "apri", vista });          // app già aperta: va sulla scheda giusta (es. Formazione)
    return aperta.focus();
  }));
});

self.addEventListener("install", e => {
  // Una copia che manca non deve impedire l'installazione: senza service worker l'app non parte offline.
  e.waitUntil(caches.open(VERSIONE).then(c => Promise.allSettled(FILE.map(f => c.add(f)))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(chiavi => Promise.all(chiavi.filter(k => k !== VERSIONE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  if (url.searchParams.has("social") || url.searchParams.has("social_errore")) return;       // il ritorno da Google (codice monouso) non si salva nella cache
  // prima la rete (versione aggiornata); se non risponde entro 2,5 secondi o manca, la copia salvata
  const rete = fetch(e.request, { cache: "no-cache" }).then(r => {
    if (r.ok) {
      const copia = r.clone();
      caches.open(VERSIONE).then(c => c.put(e.request, copia));
    }
    return r;
  });
  const scadenza = new Promise((_, no) => setTimeout(no, 2500));
  // pagina senza copia e senza rete: il ripiego; le altre risorse aspettano la rete come prima
  e.respondWith(Promise.race([rete, scadenza]).catch(() => caches.match(e.request).then(c =>
    c || (e.request.mode === "navigate" ? rete.catch(ripiego) : rete))));
});
