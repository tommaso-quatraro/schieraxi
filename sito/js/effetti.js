// Effetti della pagina, pochi e una volta sola. Nessuna libreria.
// Senza JavaScript (o con movimento ridotto) la pagina si legge e funziona uguale.
const radice = document.documentElement;

/* ---- tema: automatico -> scuro -> chiaro ---- */
export function tema() {
  const b = document.getElementById('tema');
  if (!b) return;
  const ordine = ['auto', 'scuro', 'chiaro'];
  const leggi = () => radice.dataset.tema || 'auto';
  const mostra = () => {
    b.hidden = false;
    b.setAttribute('aria-label', b.dataset['t' + leggi()[0].toUpperCase() + leggi().slice(1)] || 'Tema');
    // la barra del browser o della finestra dell'app segue il tema scelto a mano
    document.querySelectorAll('meta[name=theme-color]').forEach((m) => {
      m.dataset.o ??= m.content;
      m.dataset.m ??= m.media;
      m.content = { chiaro: '#f4f9f4', scuro: '#07100b' }[radice.dataset.tema] || m.dataset.o;
      m.media = radice.dataset.tema ? 'all' : m.dataset.m;
    });
  };
  mostra();
  b.addEventListener('click', () => {
    const prossimo = ordine[(ordine.indexOf(leggi()) + 1) % 3];
    const cambia = () => {
      if (prossimo === 'auto') delete radice.dataset.tema;
      else radice.dataset.tema = prossimo;
      try {
        prossimo === 'auto' ? localStorage.removeItem('tema') : localStorage.setItem('tema', prossimo);
      } catch (e) {}
      mostra();
    };
    if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.startViewTransition(cambia);
    } else cambia();
  });
}

/* ---- comparsa allo scorrimento: una dissolvenza, una volta ---- */
export function rivela() {
  radice.classList.add('pronto');
  document.querySelectorAll('[data-sfalsa]').forEach((g) => {
    [...g.children].forEach((f, i) => f.style.setProperty('--i', i));
  });
  const els = document.querySelectorAll('.r');
  if (!('IntersectionObserver' in window)) return els.forEach((e) => e.classList.add('visto'));
  const io = new IntersectionObserver(
    (voci) =>
      voci.forEach((v) => {
        if (v.isIntersecting) {
          v.target.classList.add('visto');
          io.unobserve(v.target);
        }
      }),
    { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
  );
  els.forEach((e) => io.observe(e));
}

/* ---- bordo della testata e pulsante «Apri la web app» dopo la prima schermata ---- */
export function barra() {
  const eroe = document.getElementById('eroe');
  if (!eroe) return;
  new IntersectionObserver((e) => document.body.classList.toggle('dopo-eroe', !e[0].isIntersecting), {
    rootMargin: '-35% 0px 0px 0px',
  }).observe(eroe);
}

/* ---- voce del menu evidenziata mentre si scorre ---- */
export function spia() {
  const link = [...document.querySelectorAll('.menu a[href^="#"]')];
  const mappa = new Map(link.map((a) => [a.getAttribute('href').slice(1), a]));
  const io = new IntersectionObserver(
    (voci) =>
      voci.forEach((v) => {
        if (!v.isIntersecting) return;
        link.forEach((a) => a.removeAttribute('aria-current'));
        mappa.get(v.target.id)?.setAttribute('aria-current', 'true');
      }),
    { rootMargin: '-45% 0px -50% 0px' },
  );
  mappa.forEach((_, id) => {
    const el = document.getElementById(id);
    if (el) io.observe(el);
  });
  // in cima (prima schermata) nessuna voce del menu è quella corrente
  const eroe = document.getElementById('eroe');
  if (eroe) io.observe(eroe);
}

/* ---- il fantavoto atteso che si costruisce voce per voce (la prima volta che si vede, poi a ogni tocco) ---- */
export function fantavoto(calmo) {
  const box = document.getElementById('fv-es');
  const num = document.getElementById('fv-num');
  if (!box || !num || calmo || !('IntersectionObserver' in window)) return;
  const f1 = new Intl.NumberFormat(radice.lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const voci = [...box.querySelectorAll('[data-d]')];
  const base = Number(box.dataset.base);
  const fine = voci.reduce((s, v) => s + Number(v.dataset.d), base);
  let giro = 0;
  const pausa = (ms) => new Promise((ok) => setTimeout(ok, ms));
  const conta = (da, a, mio) => {
    const t0 = performance.now();
    const passo = (t) => {
      if (mio !== giro) return;
      const k = Math.min(1, (t - t0) / 450);
      num.textContent = f1.format(da + (a - da) * (1 - (1 - k) ** 3));
      if (k < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  };
  const vai = async () => {
    const mio = ++giro;
    box.classList.add('anima');
    box.classList.remove('fatto');
    voci.forEach((v) => v.classList.remove('on'));
    let v = base;
    num.textContent = f1.format(v);
    for (const li of voci) {
      await pausa(700);
      if (mio !== giro) return;
      li.classList.add('on');
      conta(v, v + Number(li.dataset.d), mio);
      v += Number(li.dataset.d);
    }
    await pausa(600);
    if (mio !== giro) return;
    num.textContent = f1.format(fine);
    box.classList.add('fatto');
  };
  new IntersectionObserver(
    (e) => {
      if (e[0].isIntersecting && !box.classList.contains('fatto')) vai();
      else if (!box.classList.contains('fatto')) giro++;
    },
    { threshold: 0.5 },
  ).observe(box);
  box.addEventListener('click', vai);
}
