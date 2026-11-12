// Service worker: tiene in memoria la "scocca" dell'app (pagina, stile, script, icone) così si apre subito, anche senza rete.
// La scocca arriva tutta dalla copia di questa versione: una pagina non mescola mai file di due versioni (#654). La versione nuova
// arriva con il service worker nuovo (il job `rilascia` alza VERSIONE), che salva la sua copia e prende il posto del vecchio; la
// pagina aperta offre «Ricarica». I dati (/api/...) arrivano sempre freschi dal server; se il server non risponde, l'app lo dice.
const VERSIONE = "fanta-251";
const FILE = ["/", "/stile.css", "/app.js", "/impostazioni.js", "/dafare.js", "/primoavvio.js", "/anteprima.js", "/avatar.js", "/testi.js", "/manifest.webmanifest", "/icona.svg", "/icona-180.png", "/icona-192.png", "/caratteri/archivo.woff2"];

// Risposte del proxy davanti al server quando il servizio dietro non risponde (per esempio mentre riparte dopo un rilascio).
const SERVER_ASSENTE = [502, 503, 504];

// Pagina mostrata quando non c'è rete e nessuna copia salvata: per l'app senza la sua scocca e per le altre pagine (Privacy,
// Termini, Crediti...), che non devono aprire un'altra copia dell'app.
const PAGINA_SENZA_RETE = `<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>SchieraXI: nessuna connessione</title></head><body style="margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;background:#121513;color:#e9edea;font-family:system-ui,sans-serif;text-align:center"><main style="max-width:340px"><h1 style="font-size:22px;margin:0 0 10px">Nessuna connessione</h1><p style="line-height:1.45;color:#bccdc2;margin:0">SchieraXI non riesce a raggiungere il server. Controlla la connessione e riprova.</p><p style="margin:18px 0 0"><a href="/" style="display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;padding:0 22px;border-radius:999px;background:#3ddc97;color:#04301c;font-weight:650;text-decoration:none">Riprova</a></p></main></body></html>`;
function senzaRete() {
  return new Response(PAGINA_SENZA_RETE, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
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
  // il ritorno da Google (codice monouso) e i link d'invito (codice) non si salvano nella cache
  if (url.searchParams.has("social") || url.searchParams.has("social_errore") || url.searchParams.has("invito")) return;
  // la scocca: la pagina dell'app (con qualunque indirizzo, «/?vista=...») e i file che carica
  const scocca = url.origin === self.location.origin && FILE.includes(url.pathname) && (url.pathname === "/" || !url.search);
  e.respondWith(scocca ? dallaScocca(e.request, url.pathname) : primaLaRete(e.request));
});

// Dalla copia di questa versione, senza chiedere alla rete: così pagina e script sono sempre della stessa versione, anche con la
// rete lenta, e l'app si apre anche mentre il server riparte. Un file che manca (installazione a metà) si chiede alla rete.
function dallaScocca(richiesta, percorso) {
  return caches.open(VERSIONE).then(c => c.match(percorso).then(copia => copia || fetch(richiesta, { cache: "no-cache" }).then(r => {
    if (r.ok) c.put(percorso, r.clone());
    return r;
  }, errore => {
    if (richiesta.mode === "navigate") return senzaRete();
    throw errore;
  })));
}

// Le altre pagine e risorse: prima la rete (versione aggiornata). Se non risponde entro 2,5 secondi, se manca o se il server
// dietro non c'è (502, 503, 504), la copia salvata; senza copia, una pagina dice «Nessuna connessione», una risorsa aspetta la rete.
function primaLaRete(richiesta) {
  const copia = () => caches.open(VERSIONE).then(c => c.match(richiesta));
  const rete = fetch(richiesta, { cache: "no-cache" }).then(r => {
    if (r.ok) {
      const doppia = r.clone();
      caches.open(VERSIONE).then(c => c.put(richiesta, doppia));
    }
    return SERVER_ASSENTE.includes(r.status) ? copia().then(c => c || r) : r;
  });
  const scadenza = new Promise((_, no) => setTimeout(no, 2500));
  return Promise.race([rete, scadenza]).catch(() => copia().then(c =>
    c || (richiesta.mode === "navigate" ? rete.catch(senzaRete) : rete)));
}
