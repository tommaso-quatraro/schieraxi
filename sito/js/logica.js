// Dati di esempio e formula della demo. Nomi INVENTATI: nessun giocatore vero.
// Formula (semplice e onesta, molto più povera del modello vero):
//   fantavoto atteso = voto che il giocatore prende se gioca (mu)
//   punti attesi     = probabilità di giocare x fantavoto atteso
export const RUOLI = ['P', 'D', 'C', 'A'];

export const ROSA = [
  { id: 'torvelli', n: 'Torvelli', r: 'P', mu: 6.0, p: 0.97 },
  { id: 'bevrani', n: 'Bevrani', r: 'P', mu: 5.6, p: 0.96 },
  { id: 'dalvieri', n: 'Dalvieri', r: 'D', mu: 6.4, p: 0.95 },
  { id: 'cesolani', n: 'Cesolani', r: 'D', mu: 6.2, p: 0.93 },
  { id: 'pilvesi', n: 'Pilvesi', r: 'D', mu: 6.3, p: 0.9 },
  { id: 'gorvani', n: 'Gorvani', r: 'D', mu: 6.1, p: 0.88 },
  { id: 'mundoli', n: 'Mundoli', r: 'D', mu: 6.6, p: 0.6 },
  { id: 'vellaci', n: 'Vellaci', r: 'C', mu: 6.9, p: 0.94 },
  { id: 'ostrevi', n: 'Ostrevi', r: 'C', mu: 6.7, p: 0.92 },
  { id: 'calvessi', n: 'Calvessi', r: 'C', mu: 6.8, p: 0.85 },
  { id: 'sarvelli', n: 'Sarvelli', r: 'C', mu: 6.4, p: 0.9 },
  { id: 'pernoli', n: 'Pernoli', r: 'C', mu: 7.9, p: 0.55 },
  { id: 'valvesi', n: 'Valvesi', r: 'A', mu: 7.6, p: 0.9 },
  { id: 'lanvori', n: 'Lanvori', r: 'A', mu: 7.2, p: 0.88 },
  { id: 'rinvelli', n: 'Rinvelli', r: 'A', mu: 7.6, p: 0.7 },
  { id: 'cuvarri', n: 'Cuvarri', r: 'A', mu: 6.5, p: 0.93 },
];

export const MODULI = {
  '4-4-2': { D: 4, C: 4, A: 2 },
  '3-5-2': { D: 3, C: 5, A: 2 },
  '4-3-3': { D: 4, C: 3, A: 3 },
};

export const atteso = (g) => g.p * g.mu;
const perAtteso = (a, b) => atteso(b) - atteso(a) || a.id.localeCompare(b.id);
const mappa = (rosa) => Object.fromEntries(rosa.map((g) => [g.id, g]));

/** Mette il primo al centro, poi alternando a destra e a sinistra. */
export function centra(a) {
  const n = a.length;
  const ordine = [...Array(n).keys()].sort(
    (i, j) => Math.abs(i - (n - 1) / 2) - Math.abs(j - (n - 1) / 2) || i - j,
  );
  const out = [];
  ordine.forEach((pos, k) => (out[pos] = a[k]));
  return out;
}

const quanti = (modulo) => ({ P: 1, ...MODULI[modulo] });

/** I migliori undici per il modulo: { P:[id], D:[id...], C:[...], A:[...] }. */
export function migliori(modulo, rosa = ROSA) {
  const n = quanti(modulo);
  const out = {};
  for (const r of RUOLI) {
    const s = rosa.filter((g) => g.r === r).sort(perAtteso).slice(0, n[r]);
    out[r] = centra(s.map((g) => g.id));
  }
  return out;
}

export const tutti = (linea) => RUOLI.flatMap((r) => linea[r]);
export const totale = (ids, rosa = ROSA) => {
  const m = mappa(rosa);
  return ids.reduce((s, id) => s + atteso(m[id]), 0);
};

/** Il modulo con più punti attesi per questa rosa. */
export function moduloConsigliato(rosa = ROSA) {
  const v = (mod) => totale(tutti(migliori(mod, rosa)), rosa);
  return Object.keys(MODULI).reduce((a, b) => (v(b) > v(a) + 1e-9 ? b : a));
}

/** Nome del modulo se i numeri per reparto ne formano uno valido, altrimenti null. */
export function trovaModulo(linea) {
  if (linea.P.length !== 1) return null;
  return (
    Object.keys(MODULI).find((m) => RUOLI.slice(1).every((r) => linea[r].length === MODULI[m][r])) ||
    null
  );
}

/** Panchina: chi non è titolare, in ordine di punti attesi. */
export function panchina(linea, rosa = ROSA) {
  const dentro = new Set(tutti(linea));
  return rosa.filter((g) => !dentro.has(g.id)).sort(perAtteso).map((g) => g.id);
}

/** Posizioni in percentuale del campo (x da sinistra, y dall'alto). */
export function posizioni(modulo, y = { A: 17, C: 39, D: 61, P: 79 }) {
  const n = quanti(modulo);
  const out = {};
  for (const r of RUOLI) {
    out[r] = Array.from({ length: n[r] }, (_, i) => ({ x: 12 + (76 * (i + 0.5)) / n[r], y: y[r] }));
  }
  return out;
}

export const posPanchina = (i) => ({ x: 10 + (80 * (i + 0.5)) / 5, y: 93 });
