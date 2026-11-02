// Service worker di SchieraXI: leggero e senza rete esterna.
// - pagine: prima la rete (con un attesa breve), se manca la rete la copia salvata, poi la pagina «offline»;
// - file di stile, script, immagini: subito dalla copia salvata e intanto si rinfrescano dalla rete
//   (stale-while-revalidate, saltando la cache del browser); se il file è cambiato, la pagina propone di ricaricare.
// Per forzare un rinnovo completo basta alzare VERSIONE.
const VERSIONE = '9';
const CACHE = 'schieraxi-' + VERSIONE;
const PRECACHE = [
  '/', '/en/', '/offline.html', '/stile.css', '/favicon.svg', '/icona-192.png', '/icona-512.png',
  '/manifest.webmanifest', '/en/manifest.webmanifest',
  '/js/tema.js', '/js/principale.js', '/js/effetti.js', '/js/logica.js', '/js/demo.js', '/js/installa.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(PRECACHE.map((u) => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((k) => Promise.all(k.filter((n) => n.startsWith('schieraxi-') && n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

const firma = (r) => (r ? (r.headers.get('etag') || '') + '|' + (r.headers.get('last-modified') || '') + '|' + (r.headers.get('content-length') || '') : '');

async function avvisa() {
  const tutti = await self.clients.matchAll({ type: 'window' });
  tutti.forEach((c) => c.postMessage('aggiornato'));
}

async function pagina(req) {
  // la chiave non ha la query: /?da=app e / sono la stessa pagina
  const url = new URL(req.url);
  const chiave = new Request(url.origin + url.pathname);
  const cache = await caches.open(CACHE);
  const copia = await cache.match(chiave);
  // sempre la versione fresca dal server (niente max-age di Pages), così HTML e file non si mescolano
  const rete = fetch(url.href, { cache: 'no-cache', redirect: 'manual' }).then((r) => {
    if (r.ok) cache.put(chiave, r.clone());
    return r;
  });
  rete.catch(() => {});
  try {
    if (!copia) return await rete; // senza copia si aspetta la rete: «offline» solo se la rete manca davvero
    return await Promise.race([rete, new Promise((_, no) => setTimeout(() => no(new Error('lenta')), 4000))]);
  } catch (err) {
    return copia || (await cache.match('/offline.html'));
  }
}

async function risorsa(e) {
  const req = e.request;
  const cache = await caches.open(CACHE);
  const vecchia = await cache.match(req);
  const aggiorna = fetch(req, { cache: 'no-cache' })
    .then(async (r) => {
      if (r.ok) {
        if (vecchia && firma(vecchia) !== firma(r)) e.waitUntil(avvisa());
        await cache.put(req, r.clone());
      }
      return r;
    })
    .catch(() => null);
  if (vecchia) {
    e.waitUntil(aggiorna);
    return vecchia;
  }
  return (await aggiorna) || Response.error();
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || req.headers.has('range')) return;
  if (url.pathname === '/sw.js') return;
  e.respondWith(req.mode === 'navigate' ? pagina(req) : risorsa(e));
});
