// Avatar illustrati di SchieraXI: volti inventati, generati dal codice calciatore. Specifica completa (parti, pesi, vettori di prova) in docs/AVATAR.md:
// iOS e Android devono dare gli STESSI indici per lo stesso id. Volti disegnati (nessuna foto): con i tratti del giocatore (carnagione, capelli, barba) hanno
// un'aria di somiglianza; senza tratti tutto viene dal seme tranne la carnagione, che è neutra e fissa.
(function (radice) {
  "use strict";
  const SALE = 0xA5C1D1CE;

  // ---- parti: pesi (la somma fa sempre 100) e colori ----
  const PESI = {
    pelle: [20, 26, 24, 12, 8, 6, 4],
    forma: [50, 25, 25],
    acconciatura: [10, 16, 8, 5, 7, 6, 12, 7, 8, 5, 9, 7],
    colore: [24, 22, 18, 10, 8, 6, 4, 8],
    barba: [40, 20, 16, 14, 10],
    sopracciglia: [40, 30, 30],
    occhi: [40, 30, 30],
    bocca: [30, 35, 20, 15],
    accessorio: [78, 8, 8, 6],
    orecchie: [70, 30],
  };
  const ORDINE = ["pelle", "forma", "acconciatura", "colore", "barba", "sopracciglia", "occhi", "bocca", "accessorio", "orecchie"];
  // Versione 3: altre nove estrazioni IN CODA (dopo u11 e u12), tutte dal seme e mai dal giocatore: espressione, ritocco dei capelli, guance, rughe,
  // naso, motivo dello sfondo, disegno della maglia, colletto, spalle. Le dieci di sopra non cambiano.
  const PESI2 = {
    espressione: [52, 20, 12, 8, 8],
    variante: [50, 28, 22],
    guance: [62, 38],
    rughe: [84, 16],
    naso: [50, 28, 22],
    sfondo: [28, 24, 18, 16, 14],
    maglia: [40, 22, 20, 18],
    colletto: [55, 25, 20],
    spalle: [60, 40],
  };
  const ORDINE2 = ["espressione", "variante", "guance", "rughe", "naso", "sfondo", "maglia", "colletto", "spalle"];
  const PELLI = ["#f6d5bd", "#efc2a0", "#e0a97e", "#c98e5f", "#a56a43", "#7a4a2d", "#5a3722"];
  const CAPELLI = ["#17171b", "#3a2618", "#6a4328", "#a9793a", "#d9b45a", "#a8441f", "#9aa0a6", "#e8dcc0"];
  const FORME = [[18, 21], [20, 20], [16, 22]];                // [semiasse x, semiasse y] del viso, centro (50,42)
  const ORECCHIE = [[3.2, 4.6], [4.4, 6]];
  const CALVO = 9, CRESTA = 7;
  const COPRONO_ORECCHIE = [3, 4, 8];                          // afro, lunga, ondulata

  // ---- numeri casuali: mulberry32 a 32 bit ----
  function mulberry32(seme) {
    let a = seme >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const scegli = (rnd, pesi) => {
    const tot = pesi.reduce((s, p) => s + p, 0);
    const n = Math.floor(rnd() * tot);                          // esatto: rnd() è k/2^32 e tot è intero piccolo
    let c = 0;
    for (let i = 0; i < pesi.length; i++) { c += pesi[i]; if (n < c) return i; }
    return pesi.length - 1;
  };
  // Famiglie di acconciatura dei tratti (versione 2): R rasati o calvi, C corti, L lunghi, I ricci o afro.
  const FAMIGLIE = { R: [0, 9], C: [1, 6, 7, 10, 11], L: [4, 5, 8], I: [2, 3] };
  const BARBE_VISIBILI = [2, 3, 4];
  const numeroValido = n => (Number.isInteger(n) && n >= 1 && n <= 99 ? n : 0);
  const idValido = id => { const n = Number(id); return Number.isInteger(n) && n >= 0 && n <= 4294967295 ? n : 0; };

  const intIn = (x, max) => Number.isInteger(x) && x >= 0 && x <= max;
  // Senza il tratto `p` la carnagione è questa, uguale per tutti: MAI estratta dal seme (una carnagione a caso sarebbe sbagliata più spesso che giusta).
  const PELLE_NEUTRA = 2;
  // Tratti grossolani del giocatore (facoltativi, contratto versione 3): {p: carnagione 0-6, c: colore capelli 0-7, a: famiglia R|C|L|I, b: barba 0|1, f: barba folta 0|1 (solo con b=1)}.
  // Ogni campo non valido si ignora.
  function pulisciTratti(t) {
    if (!t || typeof t !== "object") return null;
    const o = {};
    if (intIn(t.p, 6)) o.p = t.p;
    if (intIn(t.c, 7)) o.c = t.c;
    if (typeof t.a === "string" && Object.prototype.hasOwnProperty.call(FAMIGLIE, t.a)) o.a = t.a;
    if (t.b === 0 || t.b === 1) o.b = t.b;
    if (o.b === 1 && (t.f === 0 || t.f === 1)) o.f = t.f;
    return Object.keys(o).length ? o : null;
  }

  // Gli indici di ogni parte per un codice calciatore (con le regole di coerenza). Stesso id (e stessi tratti), stessi indici, sempre.
  // Versione 2: dopo le dieci estrazioni se ne fanno altre due (u11, u12) SEMPRE; i tratti, se ci sono, correggono colore, famiglia
  // dell'acconciatura e barba; senza tratti il risultato è identico alla versione 1.
  function estrai(id, tratti) {
    const n = idValido(id);
    const rnd = mulberry32((Math.imul(n, 0x9E3779B1) ^ SALE) >>> 0);
    const v = {};
    for (const k of ORDINE) v[k] = scegli(rnd, PESI[k]);
    const u11 = rnd(), u12 = rnd();
    for (const k of ORDINE2) v[k] = scegli(rnd, PESI2[k]);
    const tr = pulisciTratti(tratti);
    v.pelle = tr && tr.p !== undefined ? tr.p : PELLE_NEUTRA;      // l'estrazione della pelle si fa comunque (l'ordine non cambia) ma il valore si scarta
    if (tr) {
      if (tr.c !== undefined) v.colore = tr.c;
      if (tr.a !== undefined && !FAMIGLIE[tr.a].includes(v.acconciatura)) {
        const pesi = FAMIGLIE[tr.a].map(i => PESI.acconciatura[i]);
        v.acconciatura = FAMIGLIE[tr.a][scegli(() => u11, pesi)];
      }
      if (tr.b === 0) v.barba = 0;
      else if (tr.b === 1 && v.barba < 2) v.barba = BARBE_VISIBILI[scegli(() => u12, BARBE_VISIBILI.map(i => PESI.barba[i]))];
      if (tr.f === 1) v.barba = 3;                                                              // barba folta: piena
      else if (tr.f === 0 && v.barba === 3) v.barba = [2, 4][scegli(() => u12, [16, 10])];      // barba non folta: corta o baffi
    }
    if (v.accessorio === 2 && COPRONO_ORECCHIE.includes(v.acconciatura)) v.accessorio = 0;   // R1: l'orecchino sotto i capelli lunghi non si vede
    if (v.accessorio === 1 && v.acconciatura === CRESTA) v.accessorio = 0;                   // R2: la fascia non sta con la cresta
    return v;
  }

  // ---- colori derivati (aritmetica intera, uguale ovunque) ----
  const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const esa = c => "#" + c.map(x => x.toString(16).padStart(2, "0")).join("");
  const scuri = (h, k) => esa(rgb(h).map(c => Math.floor(c * (1 - k) + 0.5)));
  const misce = (a, b, t) => { const A = rgb(a), B = rgb(b); return esa(A.map((c, i) => Math.floor(c * (1 - t) + B[i] * t + 0.5))); };
  const lum = h => { const [r, g, b] = rgb(h).map(c => c / 255).map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };

  // ---- acconciature: [dietro, davanti] (c = colore dei capelli, s = versione più scura per i dettagli) ----
  const CAP_CORTO = "M30.5 43C29.5 26 40 19 50 19S70.5 26 69.5 43C67 36 62 33.5 50 33.5S33 36 30.5 43Z";
  const ACCONCIATURE = [
    /* 0 rasata */ (c) => ["", `<path d="M32.5 40C32.5 28 41 22 50 22S67.5 28 67.5 40C65 35 59 32 50 32S35 35 32.5 40Z" fill="${c}" fill-opacity=".8"/>`],
    /* 1 corta */ (c) => ["", `<path d="${CAP_CORTO}" fill="${c}"/>`],
    /* 2 riccia */ (c) => [
      [[32, 38, 6.5], [68, 38, 6.5], [36, 28, 8], [50, 22, 9], [64, 28, 8]].map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}"/>`).join(""),
      `<path d="${CAP_CORTO}" fill="${c}"/>` + [[37, 33, 3.6], [44, 32, 3.6], [51, 32, 3.6], [58, 32, 3.6], [64, 33, 3.6]].map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}"/>`).join("")],
    /* 3 afro */ (c) => [`<circle cx="50" cy="33" r="26" fill="${c}"/>`, `<path d="${CAP_CORTO}" fill="${c}"/>`],
    /* 4 lunga */ (c) => [`<path d="M29 38C27 22 38 17 50 17S73 22 71 38L74 70Q74 80 66 82H34Q26 80 26 70Z" fill="${c}"/>`,
      `<path d="M31 44C30 27 40 19 50 19S70 27 69 44C67 37 62 31 54 30C46 35 38 36 31 44Z" fill="${c}"/>`],
    /* 5 chignon */ (c) => [`<circle cx="50" cy="14" r="7.5" fill="${c}"/>`, `<path d="${CAP_CORTO}" fill="${c}"/>`],
    /* 6 riga di lato */ (c, s) => ["",
      `<path d="M30.5 43C29 26 40 19 50 19S70 26 69.5 40C66 33 58 30 44 33C38 35 34 38 30.5 43Z" fill="${c}"/><path d="M44 32.4Q41 27 40 22" fill="none" stroke="${s}" stroke-width="1.2" stroke-linecap="round"/>`],
    /* 7 cresta bassa */ (c) => ["", `<path d="M32.5 40C32.5 28 41 22 50 22S67.5 28 67.5 40C65 35 59 32 50 32S35 35 32.5 40Z" fill="${c}" fill-opacity=".4"/>`
      + `<path d="M43.5 31C43 22 46 16 50 16S57 22 56.5 31C54 29.5 46 29.5 43.5 31Z" fill="${c}"/>`],
    /* 8 ondulata */ (c) => [`<ellipse cx="50" cy="36" rx="22" ry="21" fill="${c}"/>` + [[28, 52, 7], [72, 52, 7], [26, 62, 5.5], [74, 62, 5.5]].map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}"/>`).join(""),
      `<path d="M30.5 43C29 26 40 19 50 19S71 26 69.5 43C68 38 66 34 61 33C58 36 54 31 50 33C46 36 42 31 39 33C34 34 32 38 30.5 43Z" fill="${c}"/>`],
    /* 9 calvo */ () => ["", ""],
    /* 10 pettinata indietro */ (c, s) => ["", `<path d="M30.5 41C29.5 25 40 18.5 50 18.5S70.5 25 69.5 41C67 33 60 28 50 28S33 33 30.5 41Z" fill="${c}"/>`
      + `<path d="M40 29Q42 22 46 19.5M50 28V19.5M60 29Q58 22 54 19.5" fill="none" stroke="${s}" stroke-width="1" stroke-linecap="round"/>`],
    /* 11 frangia */ (c) => ["", `<path d="M30.5 43C29.5 26 40 19 50 19S70.5 26 69.5 43L67 33Q63 34.5 59 33Q54 35 50 33Q45 35 41 33Q37 34.5 33 33Z" fill="${c}"/>`],
  ];

  // ---- barbe (dentro il contorno del viso) ----
  const BARBA_PIENA = "M30 40H33Q35 50 42 51.5Q50 49.5 58 51.5Q65 50 67 40H70V70H30Z";
  const BARBA_CORTA = "M30 44H33.5Q35 56 44 57.5H56Q65 56 66.5 44H70V70H30Z";

  const OCCHI = [
    (x) => `<circle cx="${x}" cy="43" r="1.9" fill="#1d1d22"/>`,
    (x) => `<ellipse cx="${x}" cy="43" rx="2.6" ry="1.5" fill="#1d1d22"/>`,
    (x) => `<ellipse cx="${x}" cy="43" rx="3.3" ry="2.4" fill="#fff"/><circle cx="${x}" cy="43" r="1.6" fill="#2a1d14"/>`,
  ];
  const SOPRACCIGLIA = [
    ["M37.5 37.5H47", "M53 37.5H62.5", 2.2],
    ["M37.5 37.5H47", "M53 37.5H62.5", 3.4],
    ["M37.5 36.5L47 38.5", "M53 38.5L62.5 36.5", 2.4],
  ];
  const BOCCA = [
    (m) => `<path d="M44.5 57.5H55.5" fill="none" stroke="${m}" stroke-width="2" stroke-linecap="round"/>`,
    (m) => `<path d="M44 56Q50 61 56 56" fill="none" stroke="${m}" stroke-width="2" stroke-linecap="round"/>`,
    (m) => `<path d="M45.5 58H54.5" fill="none" stroke="${m}" stroke-width="2.4" stroke-linecap="round"/>`,
    (m) => `<path d="M44 56Q50 63.5 56 56Z" fill="#fff" stroke="${m}" stroke-width="1.6" stroke-linejoin="round"/>`,
  ];

  // Colori della maglia: i portieri hanno sempre grigio neutro con colletto scuro e guanti lime.
  const MAGLIA_PORTIERE = ["#8d99a8", "#1f2937"];

  function sfondo(c1, c2) {
    const L = lum(c1);
    const base = L > 0.25 ? [scuri(c1, 0.55), scuri(c1, 0.3)] : L < 0.04 ? [misce(c1, "#ffffff", 0.3), misce(c1, "#ffffff", 0.12)] : [scuri(c1, 0.5), scuri(c1, 0.25)];
    return [misce(base[0], c2, 0.22), base[1]];
  }

  // ---- versione 3: dettagli tutti dal seme ----
  const SPALLE = ["M10 100C12 84 28 77 50 77S88 84 90 100Z", "M5 100C8 85 26 77 50 77S92 85 95 100Z"];
  // Espressioni (indice 0 = il volto di sempre). Sostituiscono bocca, sopracciglia o occhi.
  const BOCCA_SORRISO = (m) => `<path d="M42.5 55.5Q50 65.5 57.5 55.5Z" fill="#fff" stroke="${m}" stroke-width="1.6" stroke-linejoin="round"/>`;
  const BOCCA_URLO = (m) => `<ellipse cx="50" cy="59" rx="5" ry="5.6" fill="#3b1219" stroke="${m}" stroke-width="1.4"/><ellipse cx="50" cy="62" rx="3.1" ry="1.9" fill="#e0707a"/>`;
  const NASI = [
    (o) => `<path d="M49.5 46.5Q47.5 51.5 51 52" fill="none" stroke="${o}" stroke-width="1.6" stroke-linecap="round"/>`,
    (o) => `<path d="M48 51.6Q50 53.6 52 51.6" fill="none" stroke="${o}" stroke-width="1.5" stroke-linecap="round"/><circle cx="47.6" cy="51.4" r=".8" fill="${o}"/><circle cx="52.4" cy="51.4" r=".8" fill="${o}"/>`,
    (o) => `<path d="M50.5 44.5V51.2Q48.6 52.4 46.8 51.6" fill="none" stroke="${o}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
  ];
  // Ritocchi dei capelli: 1 riflessi chiari, 2 ombra alle tempie. Non su calvo, rasata e cresta (non c'è dove disegnarli).
  const RITOCCHI_CAPELLI = [
    () => "",
    (c) => `<path d="M38 26Q44 22 51 21.5M53 22.5Q58.5 22.5 63 26.5" fill="none" stroke="${misce(c, "#ffffff", 0.3)}" stroke-opacity=".6" stroke-width="1.4" stroke-linecap="round"/>`,
    (c, s) => `<path d="M30.5 43C29.5 36 30.5 30 33 27L36 30C34 34 33.5 38 34 43ZM69.5 43C70.5 36 69.5 30 67 27L64 30C66 34 66.5 38 66 43Z" fill="${s}" fill-opacity=".5"/>`,
  ];
  const SENZA_RITOCCHI = [0, 9, 7];                             // rasata, calvo, cresta bassa
  // Motivo dello sfondo (colori della squadra, forme neutre: mai uno stemma vero).
  const MOTIVI = [
    () => "",
    (c) => `<g transform="rotate(35 50 50)" fill="${c}" fill-opacity=".14"><rect x="-20" y="6" width="140" height="9"/><rect x="-20" y="28" width="140" height="9"/><rect x="-20" y="50" width="140" height="9"/><rect x="-20" y="72" width="140" height="9"/></g>`,
    (c) => `<g fill="none" stroke="${c}" stroke-opacity=".16" stroke-width="3"><circle cx="50" cy="50" r="45"/><circle cx="50" cy="50" r="34"/><circle cx="50" cy="50" r="23"/></g>`,
    (c) => `<path d="M50 5L83 15V46Q83 70 50 91Q17 70 17 46V15Z" fill="${c}" fill-opacity=".14"/>`,
    (c) => `<g fill="${c}" fill-opacity=".11">` + [0, 1, 2, 3, 4, 5, 6, 7].map(i => `<path d="M50 50L43 -20H57Z" transform="rotate(${i * 45} 50 50)"/>`).join("") + `</g>`,
  ];

  // SVG (viewBox 0 0 100 100, con il cerchio di sfondo) del volto di un calciatore.
  // opz: { ruolo: "P"|"D"|"C"|"A", c1, c2 (colori squadra, "#rrggbb"), numero (facoltativo, 1-99, scritto sulla maglia), tratti (facoltativi, vedi pulisciTratti) }
  function costruisci(id, opz) {
    const o = opz || {}, v = estrai(id, o.tratti);
    const c1 = o.c1 || "#6b7280", c2 = o.c2 || "#e5e7eb", portiere = o.ruolo === "P";
    const numero = numeroValido(o.numero);
    const pelle = PELLI[v.pelle], ombra = scuri(pelle, 0.14), cap = CAPELLI[v.colore], capScuro = scuri(cap, 0.3);
    const [rx, ry] = FORME[v.forma], [ox, oy] = ORECCHIE[v.orecchie];
    const [mag, col] = portiere ? MAGLIA_PORTIERE : [c1, c2];
    const [g1, g2] = sfondo(c1, c2);
    const gid = "ug" + (g1 + g2).replace(/#/g, "");
    const bocca = v.pelle >= 4 ? misce(pelle, "#f0b8a8", 0.55) : scuri(pelle, 0.45);       // sulle pelli scure la bocca è più chiara della pelle
    const ep = v.espressione;
    const occhio = x => (v.pelle >= 5 && v.occhi < 2 ? `<ellipse cx="${x}" cy="43" rx="3.1" ry="2.1" fill="#f3ede4"/>` : "") + OCCHI[v.occhi](x);   // sulle pelli più scure gli occhi chiusi hanno il bianco
    const occhioChiuso = x => `<path d="M${x - 3} 43.6Q${x} 40.4 ${x + 3} 43.6" fill="none" stroke="#1d1d22" stroke-width="1.8" stroke-linecap="round"/>`;
    const [dietro, davanti] = ACCONCIATURE[v.acconciatura](cap, capScuro);
    const sc = ep === 2 ? ["M37.5 38.6L47 36.6", "M53 36.6L62.5 38.6", 2.8] : ep === 3 ? ["M37.5 36Q42 33.5 47 35.5", "M53 35.5Q58 33.5 62.5 36", 2.2] : SOPRACCIGLIA[v.sopracciglia];
    const b = v.barba;
    const spalle = SPALLE[v.spalle];
    const vestiamo = !portiere && v.maglia > 0;
    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" aria-hidden="true" focusable="false">`
      + `<defs><linearGradient id="${gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${g1}"/><stop offset="1" stop-color="${g2}"/></linearGradient>`
      + `<linearGradient id="ufs" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".13"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".2"/></linearGradient>`
      + `<linearGradient id="ush" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-color="#000" stop-opacity=".24"/></linearGradient>`
      + `<clipPath id="ucv${v.forma}"><ellipse cx="50" cy="42" rx="${rx}" ry="${ry}"/></clipPath>`
      + `<clipPath id="ucc"><circle cx="50" cy="50" r="50"/></clipPath><clipPath id="ums${v.spalle}"><path d="${spalle}"/></clipPath></defs>`
      + `<circle cx="50" cy="50" r="50" fill="url(#${gid})"/>`;
    if (v.sfondo) s += `<g clip-path="url(#ucc)">${MOTIVI[v.sfondo](c2)}</g>`;
    s += dietro
      + `<rect x="42" y="58" width="16" height="26" rx="6" fill="${ombra}"/>`
      + `<rect x="42" y="58" width="16" height="12" rx="6" fill="#000" fill-opacity=".16"/>`
      + `<path d="${spalle}" fill="${mag}"/>`;
    if (vestiamo) {
      s += `<g clip-path="url(#ums${v.spalle})">`
        + (v.maglia === 1 ? [18, 34, 50, 66, 82].map(x => `<rect x="${x - 4}" y="76" width="8" height="26" fill="${c2}" fill-opacity=".3"/>`).join("")
          : v.maglia === 2 ? `<rect x="0" y="88" width="100" height="5.5" fill="${c2}" fill-opacity=".65"/>`
            : `<path d="M0 100C0 96 5 91 12.5 89L24 91.5C22.5 94 21.5 97 21 100ZM100 100C100 96 95 91 87.5 89L76 91.5C77.5 94 78.5 97 79 100Z" fill="${c2}" fill-opacity=".55"/>`)
        + `</g>`;
    }
    s += `<path d="${spalle}" fill="url(#ush)"/>`;
    if (v.colletto === 1) {
      s += `<path d="M41 77L50 90L59 77Z" fill="${ombra}"/><path d="M38 77.2L50 92.5L62 77.2" fill="none" stroke="${col}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>`;
    } else if (v.colletto === 2) {
      s += `<path d="M41 77Q50 85 59 77Z" fill="${ombra}"/><path d="M39 77.5Q50 85 61 77.5L58.5 75.6Q50 80.6 41.5 75.6Z" fill="${col}"/><path d="M50 81.5V87" stroke="${col}" stroke-width="1.3" stroke-linecap="round"/><circle cx="50" cy="84" r=".8" fill="${mag}"/>`;
    } else {
      s += `<path d="M41 77Q50 87 59 77Z" fill="${ombra}"/><path d="M37 77.5Q50 92 63 77.5L59 76.5Q50 85 41 76.5Z" fill="${col}"/>`;
    }
    if (numero) s += `<text x="50" y="97.5" text-anchor="middle" font-family="system-ui,Arial,sans-serif" font-size="9" font-weight="800" fill="${col}">${numero}</text>`;
    if (portiere) {
      for (const x of [18, 66]) s += `<rect x="${x}" y="81" width="16" height="18" rx="6" fill="#d4f34a" stroke="#1f2937" stroke-width="1.2"/><path d="M${x + 5.3} 87V93M${x + 10.7} 87V93" stroke="#1f2937" stroke-width="1" stroke-linecap="round"/>`;
    }
    s += `<ellipse cx="${50 - rx}" cy="44" rx="${ox}" ry="${oy}" fill="${pelle}"/><ellipse cx="${50 + rx}" cy="44" rx="${ox}" ry="${oy}" fill="${pelle}"/>`
      + `<ellipse cx="50" cy="42" rx="${rx}" ry="${ry}" fill="${pelle}"/>`
      + `<ellipse cx="50" cy="42" rx="${rx}" ry="${ry}" fill="url(#ufs)"/>`
      + `<g clip-path="url(#ucv${v.forma})"><ellipse cx="50" cy="35" rx="26" ry="6" fill="#000" fill-opacity=".1"/><ellipse cx="50" cy="66" rx="${rx + 2}" ry="9" fill="#000" fill-opacity=".09"/>`
      + (v.guance ? `<ellipse cx="36.8" cy="50.5" rx="4.3" ry="2.6" fill="#e8667a" fill-opacity=".24"/><ellipse cx="63.2" cy="50.5" rx="4.3" ry="2.6" fill="#e8667a" fill-opacity=".24"/>` : "")
      + `</g>`;
    if (b === 1) s += `<g clip-path="url(#ucv${v.forma})"><path d="M30 44Q50 56 70 44V70H30Z" fill="${cap}" fill-opacity=".25"/></g>`;
    if (b === 2 || b === 3) {
      s += `<g clip-path="url(#ucv${v.forma})"><path d="${b === 3 ? BARBA_PIENA : BARBA_CORTA}" fill="${cap}"/>`
        + `<ellipse cx="50" cy="57.5" rx="${b === 3 ? 8 : 7.5}" ry="${b === 3 ? 4 : 3.6}" fill="${pelle}"/></g>`;
    }
    const segno = scuri(pelle, 0.22);
    if (v.rughe) s += `<path d="M41 52.5Q39.2 56.5 41.4 59.5M59 52.5Q60.8 56.5 58.6 59.5" fill="none" stroke="${segno}" stroke-opacity=".6" stroke-width=".9" stroke-linecap="round"/>`;
    s += NASI[v.naso](segno)
      + (ep === 3 ? occhioChiuso(42.5) + occhioChiuso(57.5) : ep === 4 ? occhio(42.5) + occhioChiuso(57.5) : occhio(42.5) + occhio(57.5))
      + `<path d="${sc[0]}M${sc[1].slice(1)}" fill="none" stroke="${scuri(cap, 0.2)}" stroke-width="${sc[2]}" stroke-linecap="round"/>`
      + (ep === 1 ? BOCCA_SORRISO(bocca) : ep === 2 ? `<path d="M46 58.5H54" fill="none" stroke="${bocca}" stroke-width="2.4" stroke-linecap="round"/>` : ep === 3 ? BOCCA_URLO(bocca) : ep === 4 ? BOCCA[1](bocca) : BOCCA[v.bocca](bocca));
    if (b === 4) s += `<path d="M42 54.5Q46 51.5 50 54Q54 51.5 58 54.5Q54 57.2 50 55.6Q46 57.2 42 54.5Z" fill="${cap}"/>`;
    if (v.accessorio === 3) s += `<g transform="rotate(-20 63.5 52)"><rect x="59" y="50" width="9" height="4" rx="1.2" fill="#f1e3c8" stroke="#c9b48e" stroke-width=".6"/><circle cx="62" cy="52" r=".5" fill="#c9b48e"/><circle cx="65" cy="52" r=".5" fill="#c9b48e"/></g>`;
    s += davanti;
    if (v.variante && !SENZA_RITOCCHI.includes(v.acconciatura)) s += RITOCCHI_CAPELLI[v.variante](cap, capScuro);
    if (v.accessorio === 1) s += `<path d="M31 33Q50 27 69 33V37Q50 31 31 37Z" fill="${c2}" stroke="${scuri(c2, 0.35)}" stroke-width=".8" stroke-linejoin="round"/>`;
    if (v.accessorio === 2) s += `<circle cx="${50 - rx}" cy="50.5" r="1.9" fill="#e9c24a" stroke="#a8841c" stroke-width=".6"/>`;
    return s + `</svg>`;
  }

  const cache = new Map();
  function svg(id, opz) {
    const o = opz || {};
    const tr = pulisciTratti(o.tratti);
    const chiave = idValido(id) + "|" + (o.ruolo === "P" ? "P" : "-") + "|" + (o.c1 || "") + "|" + (o.c2 || "") + "|" + numeroValido(o.numero) + "|" + (tr ? JSON.stringify(tr) : "");
    let r = cache.get(chiave);
    if (!r) {
      if (cache.size > 3000) cache.clear();
      r = costruisci(id, o);
      cache.set(chiave, r);
    }
    return r;
  }

  const Avatar = { svg, estrai, mulberry32, ORDINE, PESI, ORDINE2, PESI2, versione: 3, FAMIGLIE };
  if (typeof module !== "undefined" && module.exports) module.exports = Avatar;
  else radice.AvatarSchieraxi = Avatar;
})(typeof globalThis !== "undefined" ? globalThis : this);
