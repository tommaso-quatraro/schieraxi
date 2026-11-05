// Il sito si legge e funziona anche senza JavaScript. Qui solo: pulsante del tema e installazione come app.
import { installa } from './installa.js';

const radice = document.documentElement;
// colore della barra del browser per ogni tema: lo stesso di --fondo in stile.css
const BARRA = { chiaro: '#ffffff', scuro: '#121513' };

// tema: automatico -> scuro -> chiaro
function tema() {
  const b = document.getElementById('tema');
  if (!b) return;
  const ordine = ['auto', 'scuro', 'chiaro'];
  const leggi = () => radice.dataset.tema || 'auto';
  const mostra = () => {
    b.hidden = false;
    const t = leggi();
    b.setAttribute('aria-label', b.dataset['t' + t[0].toUpperCase() + t.slice(1)] || 'Tema');
    // la barra del browser o della finestra dell'app segue il tema scelto a mano
    document.querySelectorAll('meta[name=theme-color]').forEach((m) => {
      m.dataset.o ??= m.content;
      m.dataset.m ??= m.media;
      m.content = BARRA[radice.dataset.tema] || m.dataset.o;
      m.media = radice.dataset.tema ? 'all' : m.dataset.m;
    });
  };
  mostra();
  b.addEventListener('click', () => {
    const prossimo = ordine[(ordine.indexOf(leggi()) + 1) % 3];
    if (prossimo === 'auto') delete radice.dataset.tema;
    else radice.dataset.tema = prossimo;
    try {
      prossimo === 'auto' ? localStorage.removeItem('tema') : localStorage.setItem('tema', prossimo);
    } catch (e) {}
    mostra();
  });
}

tema();
installa();
