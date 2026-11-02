// Installazione come app (PWA): pulsante «Installa» solo quando il browser lo permette,
// suggerimento per Safari su iPhone, pulsante indietro nella finestra dell'app, service worker.
const $ = (id) => document.getElementById(id);

export function installa() {
  const radice = document.documentElement;
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const pulsante = $('installa');
  const indietro = $('indietro');

  if (standalone) {
    radice.classList.add('app');
    if (indietro) {
      indietro.hidden = false;
      indietro.addEventListener('click', () => {
        if (history.length > 1) history.back();
        else location.href = radice.lang === 'en' ? '/en/' : '/';
      });
    }
  }

  let evento = null;
  addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    evento = e;
    if (pulsante && !standalone) pulsante.hidden = false;
  });
  pulsante?.addEventListener('click', async () => {
    if (!evento) return;
    evento.prompt();
    await evento.userChoice.catch(() => {});
    evento = null;
    pulsante.hidden = true;
  });
  addEventListener('appinstalled', () => pulsante && (pulsante.hidden = true));

  // Safari su iPhone/iPad non ha il pulsante: si spiega il gesto, una volta sola
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const safari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  const hint = $('ios-hint');
  let visto = false;
  try {
    visto = localStorage.getItem('ios-hint') === '1';
  } catch (e) {}
  if (hint && ios && safari && !standalone && !visto) {
    setTimeout(() => (hint.hidden = false), 5000);
    $('ios-chiudi')?.addEventListener('click', () => {
      hint.hidden = true;
      try {
        localStorage.setItem('ios-hint', '1');
      } catch (e) {}
    });
  }

  // service worker: pagine e file anche senza rete, sempre rinfrescati in sottofondo
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
    const avviso = $('aggiorna');
    navigator.serviceWorker.addEventListener('message', (e) => {
      if (e.data === 'aggiornato' && avviso) avviso.hidden = false;
    });
    $('ricarica')?.addEventListener('click', () => location.reload());
    addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  }
}
