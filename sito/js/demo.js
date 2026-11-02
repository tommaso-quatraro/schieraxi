// Demo interattiva: modulo, scambio tra due giocatori, il perché di ogni numero.
// Dati di esempio con nomi inventati (vedi logica.js). Non è il modello vero.
import {
  RUOLI, ROSA, atteso, migliori, tutti, totale, trovaModulo, panchina, posizioni, posPanchina, centra, moduloConsigliato,
} from './logica.js';

const T = {
  it: {
    ruoli: { P: 'portiere', D: 'difensore', C: 'centrocampista', A: 'attaccante' },
    tit: 'titolare', pan: (n) => `in panchina, posizione ${n}`,
    aria: (g, r, s, mu, p, e) => `${g.n}, ${r}, ${s}, fantavoto atteso ${mu}, probabilità di giocare ${p}%, punti attesi ${e}`,
    scelto: (n) => `Hai scelto ${n}. Tocca un altro giocatore per scambiarli.`,
    campo: 'Sono tutti e due in campo: scegline uno in panchina.',
    pan2: 'Sono tutti e due in panchina: scegline uno in campo.',
    inval: 'Con questo cambio il modulo non è valido.',
    fatto: (a, b, t) => `Entra ${a}, esce ${b}. Punti attesi: ${t}.`,
    scambio: (a, b) => `${a} e ${b} si scambiano la posizione.`,
    mod: (m) => `Modulo ${m}: i migliori undici per questo schieramento.`,
    rip: (m) => `Di nuovo la formazione consigliata (${m}).`,
    ok: 'È la consigliata', meno: (d) => `${d} rispetto alla consigliata`,
    rango: (k, n) => `Titolare: è ${k}° su ${n} nel suo reparto.`,
    ranghi: (k) => `In panchina: entra se un titolare non gioca (è il ${k}°).`,
    dubbio: (n, p) => `${n} gioca solo con il ${p}%: per questo vale meno di quanto dice il suo voto.`,
  },
  en: {
    ruoli: { P: 'goalkeeper', D: 'defender', C: 'midfielder', A: 'forward' },
    tit: 'starter', pan: (n) => `on the bench, position ${n}`,
    aria: (g, r, s, mu, p, e) => `${g.n}, ${r}, ${s}, expected rating ${mu}, chance of playing ${p}%, expected points ${e}`,
    scelto: (n) => `You picked ${n}. Tap another player to swap them.`,
    campo: 'Both are on the pitch: pick one from the bench.',
    pan2: 'Both are on the bench: pick one on the pitch.',
    inval: "That swap doesn't give a valid formation.",
    fatto: (a, b, t) => `${a} comes on, ${b} goes off. Expected points: ${t}.`,
    scambio: (a, b) => `${a} and ${b} swap places.`,
    mod: (m) => `Formation ${m}: the best eleven for this shape.`,
    rip: (m) => `Back to the recommended lineup (${m}).`,
    ok: 'This is the recommended one', meno: (d) => `${d} vs the recommended one`,
    rango: (k, n) => `Starter: ranked ${k} of ${n} in his position.`,
    ranghi: (k) => `On the bench: comes on if a starter doesn't play (number ${k}).`,
    dubbio: (n, p) => `${n} only has a ${p}% chance of playing: that is why he is worth less than his rating says.`,
  },
};

export function avvia(radice, calmo) {
  const lang = document.documentElement.lang === 'en' ? 'en' : 'it';
  const t = T[lang];
  const f1 = new Intl.NumberFormat(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fs = new Intl.NumberFormat(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' });
  const $ = (id) => radice.querySelector('#' + id) || document.createElement('span'); // un id mancante non rompe la demo
  const campo = $('demo-campo');
  const radio = [...radice.querySelectorAll('input[name=modulo]')];
  const elTot = $('d-tot'), elConf = $('d-conf'), elStato = $('d-stato');
  const PER = Object.fromEntries(ROSA.map((g) => [g.id, g]));

  let modulo = moduloConsigliato();
  let linea = migliori(modulo);
  let sel = null, ultimo = null, tot = totale(tutti(linea)), blocca = false;

  const bottoni = new Map();
  for (const g of ROSA) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'gioc r-' + g.r;
    b.dataset.id = g.id;
    for (const c of ['faccia', 'ruolo', 'pt-e', 'pr', 'etq']) b.append(Object.assign(document.createElement('span'), { className: c }));
    b.querySelector('.faccia').textContent = g.n.slice(0, 2);
    b.querySelector('.ruolo').textContent = g.r;
    b.querySelector('.etq').textContent = g.n;
    b.querySelector('.pt-e').textContent = f1.format(g.mu);
    const barra = document.createElement('i');
    barra.style.setProperty('--v', g.p);
    b.querySelector('.pr').append(barra);
    b.classList.toggle('dubbio', g.p < 0.7);
    campo.append(b);
    bottoni.set(g.id, b);
  }

  const inLinea = (id) => tutti(linea).includes(id);

  function metti(id, p, k, ordine) {
    const b = bottoni.get(id), g = PER[id];
    b.style.setProperty('--x', p.x.toFixed(1));
    b.style.setProperty('--y', p.y.toFixed(1));
    b.style.setProperty('--k', k);
    if (ordine) b.dataset.ord = ordine;
    else delete b.dataset.ord;
    b.setAttribute('aria-label', t.aria(g, t.ruoli[g.r], ordine ? t.pan(ordine) : t.tit, f1.format(g.mu), Math.round(g.p * 100), f1.format(atteso(g))));
  }

  function numero(el, da, a) {
    if (calmo || da === a) {
      el.textContent = f1.format(a);
      return;
    }
    cancelAnimationFrame(el._r);
    const t0 = performance.now();
    const passo = (n) => {
      const k = Math.min(1, (n - t0) / 450);
      el.textContent = f1.format(da + (a - da) * (1 - (1 - k) ** 3));
      if (k < 1) el._r = requestAnimationFrame(passo);
    };
    el._r = requestAnimationFrame(passo);
  }

  function disegna() {
    const pos = posizioni(modulo);
    let k = 0;
    for (const r of RUOLI) linea[r].forEach((id, i) => metti(id, pos[r][i], k++ % 11, 0));
    panchina(linea).forEach((id, i) => metti(id, posPanchina(i), i, i + 1));
    radio.forEach((r) => (r.checked = r.value === modulo));
    const ids = tutti(linea);
    const nuovo = totale(ids);
    numero(elTot, tot, nuovo);
    tot = nuovo;
    // confronto con la migliore formazione possibile (con il modulo migliore)
    const migliore = migliori(moduloConsigliato());
    const diff = nuovo - totale(tutti(migliore));
    const uguale = Math.abs(diff) < 0.05;
    elConf.textContent = uguale ? t.ok : t.meno(fs.format(diff));
    elConf.classList.toggle('ok', uguale);
    $('d-reset').hidden = uguale;
    // il più atteso tra i titolari
    const top = ids.reduce((m, id) => (atteso(PER[id]) > atteso(PER[m]) ? id : m));
    bottoni.forEach((b2, id) => b2.classList.toggle('top', id === top));
    marca();
  }

  function marca() {
    bottoni.forEach((b, id) => {
      b.setAttribute('aria-pressed', String(id === sel));
      b.classList.toggle('sel', id === sel);
      b.classList.toggle('bersaglio', sel !== null && id !== sel && cambio(sel, id).ok);
    });
    campo.classList.toggle('scelto', sel !== null);
    dettaglio(sel || ultimo || 'valvesi');
  }

  function dettaglio(id) {
    ultimo = id;
    const g = PER[id], e = atteso(g);
    $('d-nome').textContent = g.n;
    $('d-ruolo').textContent = t.ruoli[g.r];
    $('d-mu').textContent = f1.format(g.mu);
    $('d-p').textContent = Math.round(g.p * 100) + '%';
    $('d-e').textContent = f1.format(e);
    $('d-mu-b').style.setProperty('--v', (g.mu / 10).toFixed(3));
    $('d-p-b').style.setProperty('--v', g.p);
    $('d-e-b').style.setProperty('--v', (e / 10).toFixed(3));
    const rep = ROSA.filter((x) => x.r === g.r).sort((a, b) => atteso(b) - atteso(a));
    const k = rep.findIndex((x) => x.id === id) + 1;
    const ord = panchina(linea).indexOf(id) + 1;
    $('d-nota').textContent = [inLinea(id) ? t.rango(k, rep.length) : t.ranghi(ord), g.p < 0.7 ? t.dubbio(g.n, Math.round(g.p * 100)) : '']
      .filter(Boolean).join(' ');
  }

  /** Esito di un cambio tra due giocatori (senza applicarlo). */
  function cambio(a, b) {
    const A = PER[a], B = PER[b];
    const ia = inLinea(a), ib = inLinea(b);
    if (ia && ib) {
      if (A.r !== B.r) return { ok: false, msg: t.campo };
      const arr = [...linea[A.r]];
      const x = arr.indexOf(a), y = arr.indexOf(b);
      [arr[x], arr[y]] = [arr[y], arr[x]];
      return { ok: true, linea: { ...linea, [A.r]: arr }, modulo, scambio: true };
    }
    if (!ia && !ib) return { ok: false, msg: t.pan2 };
    const [fuori, dentro] = ia ? [A, B] : [B, A];
    const nl = {};
    for (const r of RUOLI) nl[r] = linea[r].filter((i) => i !== fuori.id);
    if (fuori.r === dentro.r) nl[fuori.r] = linea[fuori.r].map((i) => (i === fuori.id ? dentro.id : i));
    else {
      nl[dentro.r] = [...nl[dentro.r], dentro.id];
      for (const r of [fuori.r, dentro.r]) {
        nl[r] = centra([...nl[r]].sort((p, q) => atteso(PER[q]) - atteso(PER[p])));
      }
    }
    const m = trovaModulo(nl);
    return m ? { ok: true, linea: nl, modulo: m, fuori, dentro } : { ok: false, msg: t.inval };
  }

  const di = (msg) => (elStato.textContent = msg);
  function tenta(a, b) {
    const r = cambio(a, b);
    sel = null;
    if (!r.ok) {
      di(r.msg);
      [a, b].forEach((id) => {
        const el = bottoni.get(id);
        el.classList.remove('no');
        void el.offsetWidth;
        el.classList.add('no');
      });
      return marca();
    }
    linea = r.linea;
    modulo = r.modulo;
    disegna();
    di(r.scambio ? t.scambio(PER[a].n, PER[b].n) : t.fatto(r.dentro.n, r.fuori.n, f1.format(tot)));
  }

  campo.addEventListener('click', (e) => {
    const b = e.target.closest('.gioc');
    if (!b) return;
    if (blocca) return (blocca = false);
    const id = b.dataset.id;
    if (sel === null) {
      sel = id;
      di(t.scelto(PER[id].n));
      marca();
    } else if (sel === id) {
      sel = null;
      marca();
    } else tenta(sel, id);
  });
  const mostra = (e) => {
    const b = e.target.closest('.gioc');
    if (b && sel === null) dettaglio(b.dataset.id);
  };
  campo.addEventListener('mouseover', mostra);
  campo.addEventListener('focusin', mostra);
  radice.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sel !== null) {
      sel = null;
      marca();
    }
  });

  radio.forEach((r) =>
    r.addEventListener('change', () => {
      modulo = r.value;
      linea = migliori(modulo);
      sel = null;
      disegna();
      di(t.mod(modulo));
    }),
  );
  $('d-reset').addEventListener('click', () => {
    modulo = moduloConsigliato();
    linea = migliori(modulo);
    sel = null;
    disegna();
    di(t.rip(modulo));
  });

  /* trascinamento: solo mouse e penna (sul touch si scorre la pagina, quindi si tocca) */
  let drag = null;
  campo.addEventListener('pointerdown', (e) => {
    const b = e.target.closest('.gioc');
    if (!b || e.pointerType === 'touch' || e.button > 0) return;
    drag = { b, id: b.dataset.id, x: e.clientX, y: e.clientY, on: false };
  });
  campo.addEventListener('pointermove', (e) => {
    if (!drag) return;
    if (!drag.on) {
      if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 8) return;
      drag.on = true;
      drag.b.setPointerCapture(e.pointerId);
      drag.b.classList.add('arrastra');
      sel = drag.id;
      marca();
    }
    const r = campo.getBoundingClientRect();
    drag.b.style.transform = `translate(calc(${e.clientX - r.left}px - 50%), calc(${e.clientY - r.top}px - 50%)) scale(1.14)`;
  });
  const lascia = (e) => {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (!d.on) return;
    blocca = true;
    setTimeout(() => (blocca = false), 50);
    let migliore = null, dmin = 1e9;
    const diam = d.b.querySelector('.faccia').getBoundingClientRect().width;
    bottoni.forEach((b, id) => {
      if (id === d.id) return;
      const r = b.querySelector('.faccia').getBoundingClientRect();
      const dist = Math.hypot(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
      if (dist < dmin) [dmin, migliore] = [dist, id];
    });
    d.b.style.transform = '';
    d.b.classList.remove('arrastra');
    sel = null;
    if (migliore && dmin < diam * 1.1) tenta(d.id, migliore);
    else marca();
  };
  campo.addEventListener('pointerup', lascia);
  campo.addEventListener('pointercancel', lascia);

  radice.classList.add('pronta');
  disegna();
}
