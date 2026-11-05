"use strict";
// App SchieraXI: JavaScript semplice, senza librerie. Parla con il server Python (fanta/server.py).
// Sezioni: Oggi, Formazione, Squadra, Altro (la «dieta delle funzioni»: il resto sta dentro Squadra e Altro). La scheda di un giocatore è un pannello che sale dal basso.

const $ = (sel, el = document) => el.querySelector(sel);
const contenuto = $("#contenuto");
const VISTE = ["oggi", "formazione", "squadra", "altro"];
// Pagine che non sono nella barra: stanno sotto Squadra (Cambi consigliati, Seguiti, Elenco) o sotto Altro (Scambi). «lega» è il nome vecchio
// delle voci che ora stanno in Squadra o in Altro: i vecchi indirizzi e le scorciatoie continuano a funzionare.
const SOTTO_VISTE = { mercato: "squadra", scambi: "altro", lega: "altro" };
// Pulsante «torna indietro»: la freccia è un'icona, non un carattere nel testo (docs/STILE-SENZA-AI.md).
const ICONA_INDIETRO = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>`;
const SCHEDA_DI = v => VISTE.includes(v) ? v : SOTTO_VISTE[v] || null;
// Le funzioni accese (dieta): una chiave che manca vale «acceso», così con un server vecchio o senza risposta si vede tutto come prima.
const funz = id => !stato.funzioni || stato.funzioni.funzioni[id] !== false;
const stato = { vista: "oggi", info: null, squadraVista: null, confronto: null, richiesta: 0, ruoloClassifica: "A",
  soloLiberi: false, ruoloGiocatori: "", mercatoTab: "consigli", punteggioPrec: null, calendario: null };
// ogni cambio di sezione ha un numero: una risposta arrivata in ritardo per una sezione già lasciata viene ignorata
const nuovaRichiesta = () => ++stato.richiesta;
const ancoraValida = n => n === stato.richiesta;
const NOMI_RUOLO = { P: t("ruolo.P_pl"), D: t("ruolo.D_pl"), C: t("ruolo.C_pl"), A: t("ruolo.A_pl") };
const NOME_RUOLO_1 = { P: t("ruolo.P_1"), D: t("ruolo.D_1"), C: t("ruolo.C_1"), A: t("ruolo.A_1") };
// Le lettere dei ruoli (P, D, C, A) sono quelle del fantacalcio italiano; in inglese: G (portiere), D, M (centrocampista), F (attaccante).
const ruoloSigla = r => (LINGUA === "it" ? r : ({ P: "G", D: "D", C: "M", A: "F" }[r] || r));
const SIGLE = { atalanta: "ATA", bologna: "BOL", cagliari: "CAG", como: "COM", fiorentina: "FIO", frosinone: "FRO", genoa: "GEN", inter: "INT",
  juventus: "JUV", lazio: "LAZ", lecce: "LEC", milan: "MIL", monza: "MON", napoli: "NAP", parma: "PAR", roma: "ROM", sassuolo: "SAS",
  torino: "TOR", udinese: "UDI", venezia: "VEN", verona: "VER", cremonese: "CRE", pisa: "PIS", sampdoria: "SAM", palermo: "PAL", spezia: "SPE" };
const NOMI_DIFF = ["", t("diff.1"), t("diff.2"), t("diff.3"), t("diff.4"), t("diff.5")];
const TITOLARITA = { titolare: [t("tit.titolare"), ""], ballottaggio: [t("tit.ballottaggio"), "arancio"], panchina: [t("tit.panchina"), "arancio"],
  improbabile: [t("tit.improbabile"), "rossa"], fuori: [t("tit.fuori"), "rossa"] };

// La lingua degli avvisi sul telefono (PUT /api/avvisi): parte quando cambi lingua e finisce anche se la pagina si ricarica subito (keepalive).
function salvaLinguaAvvisi(lingua) {
  try {
    fetch("/api/avvisi", { method: "PUT", keepalive: true, headers: { "X-Fanta": "1", "Content-Type": "application/json" }, body: JSON.stringify({ lingua }) })
      .catch(() => { /* senza accesso o senza rete: resta la lingua di prima */ });
  } catch { /* come sopra */ }
}

function esc(x) {
  return String(x ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const sigla = s => esc(SIGLE[s] || (s || "").slice(0, 3).toUpperCase());
const num = (x, d = 1) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : (s => LINGUA === "it" ? s.replace(".", ",") : s)(Number(x).toFixed(d));
const perc = x => `${Math.round((x || 0) * 100)}%`;
// «al 98%», «all'83%»: l'articolo davanti a un numero che si legge con la vocale (8, 11, 80-89, 800..., 1, 1100...), come Precisione.alPercento dell'iPhone; in inglese il numero e basta
const alPercento = x => { const s = String(x); return typeof LINGUA !== "undefined" && LINGUA === "en" ? s + "%" : (s.startsWith("8") || x === 1 || x === 11 || (s.startsWith("11") && s.length === 4) ? "all'" : "al ") + s + "%"; };
// Numero con il segno: «+1,2», «−0,4» (il meno tipografico, come in «Perché questo numero»), «0,0» senza segno se arrotondato vale zero.
const segno = (x, d = 1) => { if (x === null || x === undefined || Number.isNaN(x)) return num(x, d); const v = num(Math.abs(x), d); return (/[1-9]/.test(v) ? (x > 0 ? "+" : "−") : "") + v; };
// Come `num`, ma un negativo ha il meno tipografico («−1,12», mai «-1,12») e niente «+» davanti ai positivi; «0,00» senza segno.
// Per i numeri che possono essere negativi (nel Confronto: porta, cartellini). `num` resta per i campi da modificare (regole).
const numMeno = (x, d = 1) => { const v = num(x, d); return v.startsWith("-") ? (/[1-9]/.test(v) ? "−" + v.slice(1) : v.slice(1)) : v; };
const menoMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.animazioni === "ridotte";
// «Ridurre movimento» fatto bene: con il sistema (o l'impostazione Animazioni > Ridotte) l'app passa alla versione calma, non a quella ferma.
// Restano dissolvenze, colori e pulsazioni leggere; spariscono scorrimenti, zoom e rotazioni (vedi `data-calmo` in stile.css).
function segnaMovimento() {
  const r = document.documentElement;
  if (menoMovimento()) r.dataset.calmo = "1"; else delete r.dataset.calmo;
}
{ const q = window.matchMedia("(prefers-reduced-motion: reduce)"); (q.addEventListener ? q.addEventListener("change", segnaMovimento) : q.addListener(segnaMovimento)); }
segnaMovimento();

function parseData(s) {
  if (!s) return null;
  const d = new Date(String(s).replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? null : d;
}
// "oggi 20:45", "domani 18:30", "sab 31 15:00"
function quando(s) {
  const d = parseData(s);
  if (!d) return "–";
  const inizio = x => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const diff = Math.round((inizio(d) - inizio(new Date())) / 864e5);
  const ora = fOra(d);
  const giorno = Math.abs(diff) > 6 ? fData(d) : d.getDate();          // oltre la settimana anche il mese
  return `${diff === 0 ? t("tempo.oggi") : diff === 1 ? t("tempo.domani") : diff === -1 ? t("tempo.ieri") : `${t("tempo.giorno_" + d.getDay())} ${giorno}`} ${ora}`;
}

// ETag e If-Match: il server dà a ogni risorsa personale (regole, rose, scelta di una giornata, osservati, avvisi) un ETag. L'app
// lo ricorda e lo rimanda in If-Match quando scrive: se nel frattempo un altro dispositivo ha cambiato la stessa cosa il server
// risponde 412, l'app lo dice e si ricarica con i dati nuovi. Le scritture sulla stessa risorsa partono una alla volta.
const etagDi = {};            // risorsa -> ultimo ETag visto
const codaScritture = {};     // risorsa -> promessa dell'ultima scrittura (la prossima aspetta)
const scrittureInCorso = {};  // risorsa -> quante scritture sono in volo
function risorsaDi(percorso, opzioni) {
  const [p, qs] = percorso.split("?");
  const metodo = (opzioni.method || "GET").toUpperCase();
  if (p === "/api/regole" || p === "/api/regole/rinvio") return "regole";
  if (["/api/squadre", "/api/rosa", "/api/crediti", "/api/mia-squadra", "/api/squadre/nome", "/api/rose/testo", "/api/rose/file", "/api/rose/correggi"].includes(p)) return "rose";
  if (p === "/api/osservati" || p.startsWith("/api/osservati/")) return "osservati";
  if (p === "/api/avvisi") return "avvisi";
  if (p === "/api/scelta") { const g = new URLSearchParams(qs || "").get("giornata"); return g ? `scelta:${g}` : null; }
  if (p === "/api/formazione/valuta" && metodo === "POST") {
    try { const b = JSON.parse(opzioni.body); if (b.salva && b.giornata) return `scelta:${b.giornata}`; } catch { /* corpo non JSON */ }
  }
  return null;
}
function nuovoCollegamento() { for (const k of Object.keys(etagDi)) delete etagDi[k]; }

// Il server con gli account non fa aspettare la richiesta durante un calcolo lungo: risponde 202 «sto calcolando» e l'app
// riprova da sola ogni pochi secondi, con il marchio che si muove in un angolo (fino a circa due minuti).
const TENTATIVI_CALCOLO = 40;
let inAttesa = 0;
function mostraCalcolo(mostra) {
  inAttesa += mostra ? 1 : -1;
  let c = $("#calcolo");
  if (!c && inAttesa > 0) {
    c = document.createElement("div");
    c.id = "calcolo"; c.className = "calcolo vetro"; c.setAttribute("role", "status");
    c.innerHTML = `${marchio(34, true)}<span>${t("comune.calcolo_attesa")}</span>`;
    document.body.append(c);
  }
  if (c) c.hidden = inAttesa <= 0;
}
async function api(percorso, opzioni = {}) {
  const risorsa = risorsaDi(percorso, opzioni);
  const scrive = !!risorsa && (opzioni.method || "GET").toUpperCase() !== "GET";
  let rilascia = null;
  if (scrive) {                                         // una scrittura alla volta per risorsa: la seconda usa l'ETag della prima
    const prima = codaScritture[risorsa] || Promise.resolve();
    codaScritture[risorsa] = new Promise(ok => { rilascia = ok; });
    scrittureInCorso[risorsa] = (scrittureInCorso[risorsa] || 0) + 1;
    await prima;
  }
  let attendo = false;
  try {
    for (let tentativo = 0; ; tentativo++) {
      const intestazioni = { "X-Fanta": "1", "Accept-Language": LINGUA };    // il server scrive alcuni testi (Novità, scambi...) in questa lingua
      if (!(opzioni.body instanceof FormData)) intestazioni["Content-Type"] = "application/json";
      // ifMatch: un ETag preciso al posto dell'ultimo visto (l'importazione delle rose manda quello della sua anteprima)
      const ifMatch = opzioni.ifMatch || etagDi[risorsa];
      if (scrive && ifMatch) intestazioni["If-Match"] = ifMatch;
      let r;
      // timeout (ms): la richiesta non resta appesa per sempre; senzaRicarica: col 412 ci pensa chi chiama; leggiEtag(etag): l'ETag della risposta
      const { timeout, ifMatch: _usato, senzaRicarica, leggiEtag, ...resto } = opzioni;
      const ferma = timeout ? new AbortController() : null;
      const sveglia = ferma ? setTimeout(() => ferma.abort(), timeout) : null;
      try { r = await fetch(percorso, { ...resto, headers: intestazioni, ...(ferma ? { signal: ferma.signal } : {}) }); }
      catch { const e = new Error(ferma && ferma.signal.aborted ? t("comune.rete_timeout") : t("comune.rete_no")); e.rete = true; throw e; }
      finally { if (sveglia) clearTimeout(sveglia); }
      let dati = null;
      try { dati = await r.json(); } catch { /* risposta vuota */ }
      if (r.status === 202 && dati && dati.calcolo === "in_corso") {
        if (tentativo >= TENTATIVI_CALCOLO) throw new Error(t("comune.calcolo_lungo"));
        if (!attendo) { attendo = true; mostraCalcolo(true); }
        await new Promise(ok => setTimeout(ok, Math.max(1, dati.riprova_tra || 3) * 1000));
        continue;
      }
      if (r.status === 412) {                           // un altro dispositivo ha cambiato questi dati: si riparte da quelli nuovi
        nuovoCollegamento();
        if (typeof svuotaCache === "function") svuotaCache();
        if (!senzaRicarica) setTimeout(() => location.reload(), 2500);
        const e = new Error(traduciErrore((dati && dati.detail) || "") || t("comune.cambiato_altrove")); e.originale = (dati && dati.detail) || ""; e.status = 412; throw e;
      }
      if (!r.ok) {
        if (dati && dati.registrazione) stato.registrazione = dati.registrazione;
        if (r.status === 401 && dati && dati.multiutente) sessioneScaduta();          // vedi "account" più sotto
        const testo = dati && typeof dati.detail === "string" ? dati.detail
          : r.status >= 500 ? t("comune.errore_server", { n: r.status }) : t("comune.errore_n", { n: r.status });
        const e = new Error(traduciErrore(testo)); e.originale = testo; e.status = r.status; e.riprova = Number(r.headers.get("Retry-After")) || 0;
        e.codice = dati && typeof dati.codice === "string" ? dati.codice : "";            // nome breve dell'errore (accesso con Google)
        if (dati && Array.isArray(dati.social)) stato.social = dati.social;
        if (dati && typeof dati.email_attiva === "boolean") stato.emailAttiva = dati.email_attiva;
        if (r.status === 404 && dati && typeof dati.funzione === "string") {           // funzione spenta: il server lo dice con il nome della funzione
          e.funzione = dati.funzione;
          if (stato.funzioni && stato.funzioni.funzioni) stato.funzioni.funzioni[dati.funzione] = false;       // la schermata la nasconde da qui in poi
        }
        throw e;
      }
      const etag = r.headers.get("ETag");
      if (leggiEtag) leggiEtag(etag);
      if (etag && risorsa && (scrive || !scrittureInCorso[risorsa])) etagDi[risorsa] = etag;
      if (scrive) lampoSalvato();
      if (percorso === "/api/nuova-stagione" || percorso === "/api/backup/ripristina") nuovoCollegamento();   // cambiano più risorse insieme
      return dati;
    }
  } finally {
    if (attendo) mostraCalcolo(false);
    if (scrive) { scrittureInCorso[risorsa]--; rilascia(); }
  }
}

// Conferma di un salvataggio: un anello verde breve sul pulsante appena toccato (colore, non movimento: vale anche nella versione calma).
function lampoSalvato() {
  const b = document.activeElement;
  if (!b || !b.matches || !b.matches("button, .bottone")) return;
  b.classList.remove("salvato"); void b.offsetWidth; b.classList.add("salvato");
  setTimeout(() => b.classList.remove("salvato"), 800);
}

function avviso(testo, durata = 3500) {
  const a = $("#avviso");
  a.textContent = testo;
  a.hidden = true; void a.offsetWidth; a.hidden = false;       // riparte l'animazione anche se l'avviso era già in vista
  clearTimeout(avviso.t);
  avviso.t = setTimeout(() => { a.hidden = true; }, durata);
}

// Il marchio di SchieraXI: undici punti in formazione 4-3-3 e il capitano. Con `muove` i punti passano al 3-5-2 e tornano (caricamenti).
// Per ogni punto: x, y e lo spostamento verso il 3-5-2.
const PUNTI_MARCHIO = [[34, 28, 11, 0], [60, 25, 15, 3], [86, 28, 14, 22], [30, 50, -10, 0], [90, 50, -10, 0], [24, 72, 6, 2], [47, 74, -7, -24], [73, 74, -13, 0], [96, 72, -6, 2], [60, 95, 0, 0]];
function marchio(dim = 48, muove = false) {
  const punti = PUNTI_MARCHIO.map(([x, y, dx, dy], i) => `<circle cx="${x}" cy="${y}" r="6.5" style="--dx:${dx}px;--dy:${dy}px;--i:${i}"/>`).join("");
  return `<svg class="marchio${muove ? " muove" : ""}" width="${dim}" height="${dim}" viewBox="0 0 120 120" role="img" aria-label="SchieraXI"><g class="punti">${punti}</g><circle class="capitano" cx="60" cy="50" r="9"/></svg>`;
}

function caricamento(testo = t("comune.calcolo_in_corso")) {
  contenuto.classList.remove("ridisegna");
  contenuto.innerHTML = `<div class="caricamento">${marchio(54, true)}${esc(testo)}</div>
    <div class="scheletro carta"><i></i><i></i><i class="corta"></i></div>
    <div class="scheletro carta"><i></i><i class="corta"></i></div>`;
}
// «1 giornata», «2 giornate»: il plurale giusto per un numero
const nPl = (n, uno, molti) => `${n} ${n === 1 ? uno : molti}`;
// Con «troppe richieste» (429) il server dice quanto aspettare: lo diciamo anche noi.
// Se il messaggio del server dice già quando riprovare («Si azzera tra...») non lo ripetiamo; sopra l'ora si arrotonda alle ore.
const attesaTesto = s => s < 90 ? t("comune.attesa_secondi", { n: s }) : s < 3600 ? t("comune.attesa_minuti", { n: Math.ceil(s / 60) })
  : t(Math.round(s / 3600) <= 1 ? "comune.attesa_ora" : "comune.attesa_ore", { n: Math.max(1, Math.round(s / 3600)) });
const attesaDa = e => e && e.status === 429 && e.riprova && !/\btra\b/i.test(e.originale || e.message || "") ? t("comune.riprova_tra", { attesa: attesaTesto(e.riprova) }) : "";
const errore = e => `<div class="errore">${esc(e.message || e)}${attesaDa(e)}</div>`;
// Errore a tutta pagina (una sezione che non si apre): c'è il pulsante «Riprova», senza dover cambiare sezione e tornare.
// Senza rose (409 dal server) non è un errore: è un inizio. Stato vuoto che porta a «Importa le rose» (si apre il primo avvio guidato).
const senzaRose = e => !!e && e.status === 409 && /nessuna rosa/i.test(e.originale || e.message || "");
const cartaSenzaRose = (titolo = t("comune.prima_rose")) => `<div class="carta benvenuto" role="status"><h2>${esc(titolo)}</h2>
  <p class="debole">${t("comune.importa_spiega")}</p>
  <div class="pulsanti"><button class="bottone" type="button" data-importa-rose>${t("comune.importa_rose")}</button></div></div>`;
// Funzione spenta (404 con il campo «funzione»): non è un guasto, quindi niente «Riprova»; si spiega e si indica dove riaccenderla.
const funzioneSpenta = e => !!e && e.status === 404 && typeof e.funzione === "string";
const cartaFunzioneSpenta = e => `<div class="carta" role="status"><h2>${t("dieta.non_disponibile")}</h2><p class="debole">${esc(e.message)}</p>
  <div class="pulsanti"><button class="bottone" type="button" data-vai="oggi">${t("dieta.torna_oggi")}</button>
  ${soloAmministratore() ? `<button class="bottone secondario" type="button" data-imp-gruppo="avanzate">${t("dieta.apri_impostazioni")}</button>` : ""}</div></div>`;
const erroreVista = e => senzaRose(e) ? cartaSenzaRose() : funzioneSpenta(e) ? cartaFunzioneSpenta(e) : errore(e) + `<div class="pulsanti"><button class="bottone secondario" type="button" data-riprova>${t("comune.riprova")}</button></div>`;

// ---------------------------------------------------------------- copia sul telefono delle ultime risposte
// L'app mostra subito i dati vecchi e li sostituisce con quelli nuovi appena arrivano: si apre senza attese.
const VERSIONE_CACHE = "3";   // da cambiare quando cambia la forma dei dati: le copie vecchie vengono ignorate
const chiaveCache = chiave => `cache:${VERSIONE_CACHE}:${stato.account ? `u${stato.account.id}:` : ""}${chiave}`;
function leggiCache(chiave) {
  try { const x = JSON.parse(localStorage.getItem(chiaveCache(chiave)) || "null"); return x && x.dati ? x : null; } catch { return null; }
}
function salvaCache(chiave, dati) {
  try { localStorage.setItem(chiaveCache(chiave), JSON.stringify({ quando: Date.now(), dati })); } catch { /* memoria piena o bloccata */ }
}
function rimuoviCache(chiave) {
  try { localStorage.removeItem(chiaveCache(chiave)); } catch { /* niente memoria */ }
}
function svuotaCache() {
  stato.formaz = null;       // la formazione "in memoria" per i confronti non vale più
  stato.scelta = null;       // e nemmeno la formazione modificata a mano
  try { Object.keys(localStorage).filter(k => k.startsWith("cache:")).forEach(k => localStorage.removeItem(k)); } catch { /* niente memoria */ }
}
// Scrive la pagina; se i dati arrivano da copia salvata aggiunge la nota, se sostituisce non rifà l'entrata a cascata.
function pagina(html, opz = {}) {
  contenuto.classList.toggle("ridisegna", !!opz.sostituisce);
  const nota = opz.daCache ? `<div class="nota" id="nota-cache">${t("comune.dati_salvati", { quando: fDataOra(new Date(opz.daCache)) })}</div>` : "";
  contenuto.innerHTML = nota + html;
}
async function caricaConCache(chiave, percorso, mostra, testo) {
  const mia = nuovaRichiesta();
  let salvata = leggiCache(chiave);
  if (salvata) {
    try { mostra(salvata.dati, { daCache: salvata.quando }); }
    catch { rimuoviCache(chiave); salvata = null; caricamento(testo); }     // copia rovinata o di una versione vecchia
  } else caricamento(testo);
  try {
    const dati = await api(percorso);
    if (!ancoraValida(mia)) return;
    salvaCache(chiave, dati);
    if (!salvata || JSON.stringify(salvata.dati) !== JSON.stringify(dati)) mostra(dati, { sostituisce: !!salvata });
    else { const b = $("#nota-cache"); if (b) b.remove(); }
  } catch (e) {
    if (!ancoraValida(mia)) return;
    if (salvata) {
      const b = $("#nota-cache");
      if (b) b.textContent = e.rete ? t("comune.cache_offline") : t("comune.cache_errore", { errore: e.message });
      return;
    }
    contenuto.innerHTML = erroreVista(e) + (!senzaRose(e) && /rosa|squadra/i.test(e.originale || e.message) ? `<button class="bottone" data-vai="squadra">${t("comune.vai_lega")}</button>` : "");
  }
}

// Un numero che sale (o scende) fino al valore finale: dà la sensazione che il calcolo sia "vivo".
function animaNumero(el, da, a, decimali = 1, durata = 650) {
  if (!el) return;
  const scrivi = v => { el.textContent = num(v, decimali); };
  if (!Number.isFinite(da) || da === a) { scrivi(a); return; }
  if (menoMovimento()) durata = Math.min(durata, 350);
  const inizio = performance.now();
  const passo = ora => {
    const k = Math.min(1, (ora - inizio) / durata);
    scrivi(da + (a - da) * (1 - Math.pow(1 - k, 3)));
    if (k < 1 && document.body.contains(el)) requestAnimationFrame(passo); else scrivi(a);
  };
  requestAnimationFrame(passo);
}

// ---------------------------------------------------------------- pezzi grafici riusati
const classeIndice = v => v >= 70 ? "alto" : v >= 40 ? "medio" : "basso";
const anello = (v, grande = false) => `<span class="indice ${classeIndice(v)} ${grande ? "grande-i" : ""}" style="--v:${v}"><b>${v}</b>${grande ? "<small>INDICE</small>" : ""}</span>`;
// Colori principali e secondari delle squadre (per il cerchio degli avatar).
const COLORI_SQUADRA = { atalanta: ["#1e71b8", "#111827"], bologna: ["#a21c26", "#1a2f5a"], cagliari: ["#a51e36", "#0b2a52"], como: ["#1b5fa8", "#f3f4f6"],
  fiorentina: ["#6b2f9a", "#f3f4f6"], frosinone: ["#f2d200", "#1a56a6"], genoa: ["#b3202a", "#0a2a52"], inter: ["#0a58a8", "#111827"],
  juventus: ["#f3f4f6", "#111827"], lazio: ["#8fc4ea", "#f3f4f6"], lecce: ["#d8232a", "#f2d200"], milan: ["#d11f2f", "#111827"], monza: ["#d11f2f", "#f3f4f6"],
  napoli: ["#3d8fd1", "#f3f4f6"], parma: ["#f2f2f2", "#f2c200"], roma: ["#8b1c2e", "#f2a900"], sassuolo: ["#1f8a4c", "#111827"], torino: ["#7a1f2a", "#f3f4f6"],
  udinese: ["#f3f4f6", "#111827"], venezia: ["#0b3d2e", "#f08a1a"], verona: ["#1a3a8a", "#f2d200"], cremonese: ["#b3202a", "#8b95a1"], pisa: ["#0b2a52", "#111827"],
  sampdoria: ["#1b5fa8", "#f3f4f6"], palermo: ["#f4a6c0", "#111827"], spezia: ["#f3f4f6", "#111827"] };
// Avatar: volto illustrato inventato, generato dal codice calciatore (fanta/web/avatar.js, specifica in docs/AVATAR.md). Nessuna foto,
// nessuna somiglianza con il giocatore vero. Cerchio nei colori della squadra, maglia con il colletto di squadra (portieri: grigia con i guanti).
// x: { id, nome, squadra (slug), ruolo }. Senza un id valido il volto si ricava dal nome (sempre lo stesso).
function idAvatar(x) {
  const n = Number(x.id);
  if (x.id != null && Number.isInteger(n) && n >= 0) return n;
  let h = 5381;
  for (const ch of String(x.nome || "")) h = (Math.imul(h, 33) + ch.codePointAt(0)) >>> 0;
  return h;
}
function svgAvatar(x) {
  const [c1, c2] = (Object.hasOwn(COLORI_SQUADRA, x.squadra) && COLORI_SQUADRA[x.squadra]) || ["#6b7280", "#e5e7eb"];
  // tratti grossolani (carnagione, capelli, barba) se il server li ha: danno al volto disegnato un'aria del giocatore; senza, carnagione neutra e il resto dal seme
  const tratti = x.avatar || (stato.tratti && stato.tratti[idAvatar(x)]) || null;
  return AvatarSchieraxi.svg(idAvatar(x), { ruolo: x.ruolo, c1, c2, tratti });
}
// Le foto dei giocatori restano spente (il server le attiva solo con FANTA_FOTO=1); se accese, il ritaglio va sopra il volto illustrato.
const fotoAccese = () => !!stato.fotoAttive;
function avatar(x) {
  return `<span class="avatar" role="img" aria-label="${esc(x.nome || t("comune.giocatore"))}">${svgAvatar(x)}`
    + `</span>`;
}
// Un ritaglio che non arriva sparisce e lascia il volto illustrato (niente gestori in linea: la CSP non li permette).
document.addEventListener("error", ev => { if (ev.target instanceof HTMLImageElement && ev.target.classList.contains("volto")) ev.target.remove(); }, true);
// Avatar con l'anello dell'indice (0-100) e il numero in un cartellino.
function avatarIndice(x, grande = false) {
  if (x.indice == null) return `<span class="avatar-anello ${grande ? "grande-a" : ""}">${avatar(x)}</span>`;
  return `<span class="avatar-anello ${classeIndice(x.indice)} ${grande ? "grande-a" : ""}" style="--v:${x.indice}">${avatar(x)}<b class="badge-indice" title="${esc(t("comune.indice_aria", { n: x.indice }))}" aria-label="${esc(t("comune.indice_aria", { n: x.indice }))}">${x.indice}</b></span>`;
}
const diffPill = d => `<span class="diff d${d}"><i></i>${NOMI_DIFF[d]}</span>`;
const badgeRuolo = (r, piccolo = false) => `<span class="ruolo ${esc(r)}" ${piccolo ? `style="width:21px;height:21px;font-size:var(--t-eti);border-radius:7px;display:inline-grid;vertical-align:-4px;margin-right:6px"` : ""}>${esc(ruoloSigla(r))}</span>`;
// A parole e senza numero: l'unica percentuale sul giocare è «gioca N%» (p_voto), quella delle probabili non si mostra.
// A giornata iniziata il server toglie `titolarita` e manda `stato_partita`: lo stato vero della giornata al posto delle probabili.
const STATO_PARTITA = { fatto: ["tit.st_fatto", ""], senza_voto: ["tit.st_senza_voto", "arancio"], attesa_voti: ["tit.st_attesa_voti", "neutra"],
  in_corso: ["tit.st_in_corso", ""], da_giocare: ["tit.st_da_giocare", "neutra"], rinviata: ["tit.st_rinviata", "arancio"] };
const PARTITA_INIZIATA = ["in_corso", "attesa_voti", "fatto", "senza_voto"], PARTITA_FINITA = ["attesa_voti", "fatto", "senza_voto"];
// Lo stato del giocatore lo scrive il server: `etichetta` = {codice, testo, tono} (fanta/etichette.py, docs/API.md), già nella
// lingua chiesta. Il web mostra il testo e prende il colore dal tono; `codice` serve solo per decidere, mai per scrivere.
const CLASSE_TONO = { positivo: "", attenzione: "arancio", negativo: "rossa", neutro: "neutra" };
const etichettaPronta = x => !!(x && x.etichetta && typeof x.etichetta.testo === "string" && x.etichetta.testo);
const classeTono = et => CLASSE_TONO[et && et.tono] ?? "neutra";
// Il testo di una pillola, mai tagliato con i puntini (issue #230, come l'iPhone): se non ci sta su una riga va a capo prima tra i
// pezzi separati da «·» («In dubbio ·» sopra, «gioca 62%» sotto), poi tra le parole. Ogni pezzo è un blocco (`.etichetta .pezzo`);
// il «·» resta attaccato alla parola prima (spazio che non va a capo), così non finisce mai da solo su una riga.
function testoEtichetta(testo) {
  const pezzi = String(testo ?? "").split(" · ");
  if (pezzi.length < 2) return esc(testo);
  return pezzi.map((p, i) => `<span class="pezzo">${esc(p)}${i < pezzi.length - 1 ? "&nbsp;·" : ""}</span>`).join(" ");
}
function pillTitolarita(x) {
  if (etichettaPronta(x)) return `<span class="etichetta ${classeTono(x.etichetta)}">${testoEtichetta(x.etichetta.testo)}</span>`;
  return pillRipiego(x);
}
// Ripiego per le risposte senza `etichetta` (server vecchio, Cambi consigliati, widget): le parole del vocabolario dai campi grezzi.
function pillRipiego(x) {
  if (x.titolarita == null && Object.hasOwn(STATO_PARTITA, x.stato_partita || "")) {
    const [chiave, classe] = STATO_PARTITA[x.stato_partita];
    return `<span class="etichetta ${classe}">${t(chiave)}</span>`;
  }
  const [testo, classe] = TITOLARITA[x.titolarita] || ["", "neutra"];
  return testo ? `<span class="etichetta ${classe}">${testo}</span>` : "";
}
// Il tocco sul fantavoto atteso apre «Perché questo numero» (nella Formazione; altrove il tocco apre la scheda come sempre).
// Le sette voci del confronto hanno l'etichetta nella lingua scelta; una voce nuova del server, senza etichetta qui, si mostra com'è.
const etichettaFattore = f => (Object.hasOwn(TESTI.it, `confronto.fattore_${f.chiave}`) ? t(`confronto.fattore_${f.chiave}`) : f.etichetta);
// Anche le regole riconosciute dal testo del regolamento («Rigore parato», «Moduli ammessi»...) hanno l'etichetta nella lingua scelta.
const etichettaRegola = m => (Object.hasOwn(TESTI.it, `regola.et.${m.chiave}`) ? t(`regola.et.${m.chiave}`) : m.etichetta);
const attrPerche = x => Array.isArray(x.perche_numero) ? ` data-perche="${Number(x.id)}" title="${t("perche.titolo")}"` : "";
// Quante volte parte titolare quando gioca, a parole: l'unica percentuale sul giocare resta «gioca N%».
const partenzaAParole = q => q == null ? "–" : t(q >= 0.7 ? "mercato.parte_quasi_sempre" : q >= 0.4 ? "mercato.parte_a_volte" : "mercato.parte_di_rado");
// I motivi sotto il nome: si scelgono dal testo italiano del server, si mostrano nella lingua scelta (motivi_frasi, vedi fanta/frasi.py).
const motiviUtili = x => (x.motivi || []).map((testo, i) => ({ testo, frase: (x.motivi_frasi || [])[i] }))
  .filter(m => !/^titolare|^parte dalla panchina|^partita (favorevole|difficile)/.test(m.testo)).slice(0, 2);
// Nelle righe una sola percentuale per giocatore, «gioca N%»: gol atteso e porta inviolata (motivi con un numero) restano nella scheda.
const MOTIVI_CON_PERCENTUALE = ["motivo.gol_atteso", "motivo.porta_inviolata"];
const senzaPercentuale = m => !(m.frase && MOTIVI_CON_PERCENTUALE.includes(m.frase.chiave)) && !/\d\s*%/.test(m.testo);
const MOTIVI_DI_STATO = ["motivo.infortunato", "motivo.squalificato", "motivo.non_convocato"];
const motivoDiStato = m => (m.frase ? MOTIVI_DI_STATO.includes(m.frase.chiave) : /^(infortunato|squalificato|non tra i convocati)/.test(m.testo));
function etichetteGiocatore(x) {
  const pronta = etichettaPronta(x);
  const altre = motiviUtili(x).filter(senzaPercentuale).filter(m => !(pronta && motivoDiStato(m))).map(m => `<span class="etichetta ${/infortunat|squalificat|dubbio|non tra/.test(m.testo) ? "rossa" : "neutra"}${m.testo.length > 28 ? " lunga" : ""}">${testoEtichetta(traduciFrase(m.frase, m.testo))}</span>`).join("");
  // ripiego: «Fuori» (infortunato) a partita finita, anche com'è andata («Voto in arrivo», «Senza voto»); con l'etichetta lo dice il server
  const esito = !pronta && x.titolarita != null && PARTITA_FINITA.includes(x.stato_partita || "")
    ? `<span class="etichetta ${STATO_PARTITA[x.stato_partita][1]}">${t(STATO_PARTITA[x.stato_partita][0])}</span>` : "";
  return pillTitolarita(x) + esito + (x.diffidato ? `<span class="etichetta arancio">${t("oggi.diffidato_tipo")}</span>` : "") + altre;
}

// Distintivo della squadra: solo la sigla nei colori sociali (niente stemmi: sono marchi dei club).
const nomeClub = s => String(s || "").replace(/(^|[\s-])\S/g, c => c.toUpperCase());
function luminosita(hex) {
  const n = parseInt(String(hex).slice(1), 16);
  const c = [n >> 16, (n >> 8) & 255, n & 255].map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; });
  return .2126 * c[0] + .7152 * c[1] + .0722 * c[2];
}
function distintivo(s) {
  const [c1, c2] = (Object.hasOwn(COLORI_SQUADRA, s) && COLORI_SQUADRA[s]) || ["#6b7280", "#e5e7eb"];
  // nero o bianco, quello con il contrasto più alto (come LetturaPedina.testoScuro sull'iPhone): con la soglia fissa a 0,35
  // la sigla bianca sull'azzurro del Napoli stava a 3,5:1 (issue #244)
  const l = luminosita(c1), testo = (l + .05) / .05 > 1.05 / (l + .05) ? "#000000" : "#ffffff";
  return `<i class="dist" style="--c1:${c1};--c2:${c2};--ct:${testo}">${sigla(s)}</i>`;
}
// Per i lettori di schermo: «gioca all'85 per cento, in casa contro il Napoli» (in italiano con l'articolo giusto).
const ARTICOLI_CLUB = { atalanta: "l'", inter: "l'", udinese: "l'", empoli: "l'", juventus: "la ", fiorentina: "la ", lazio: "la ", roma: "la ",
  sampdoria: "la ", cremonese: "la ", salernitana: "la ", spezia: "lo " };
function vocePedina(x, esito = null) {             // esito: esitoPedina(x), a partita iniziata o rinviata
  const p = Math.round((x.p_voto ?? 0) * 100);
  const vocale = p === 1 || p === 8 || p === 11 || (p >= 80 && p <= 89);         // «all'85», «al 65»
  const avv = (LINGUA === "it" ? (ARTICOLI_CLUB[x.avversario] ?? "il ") : "") + nomeClub(x.avversario);
  return [x.nome, t("formazione.voce_fv", { fv: num(x.fv_atteso) }), esito ? esito.testo : t(vocale ? "formazione.voce_gioca_v" : "formazione.voce_gioca", { p }),
    x.avversario ? t(x.in_casa ? "formazione.voce_casa" : "formazione.voce_fuori", { avv }) : ""].filter(Boolean).join(", ");
}
const SOGLIA_GIOCA = 0.7;                       // sotto: «⚠ gioca 45%» in una pillola arancio
// A partita iniziata «gioca N%» non serve più (come la scheda, PARTITA_INIZIATA): a partita finita il fantavoto preso (`fv_preso`
// del server) o lo stato («Voto in arrivo», «Senza voto»); in corso lo stato. Null = la partita non è cominciata: «gioca N%».
const CODICI_PARTITA_INIZIATA = ["voto", "senza_voto", "voto_in_arrivo", "in_corso"];
function esitoPartita(x) {
  const codice = etichettaPronta(x) ? x.etichetta.codice : null;
  if (!PARTITA_INIZIATA.includes(x.stato_partita || "") && !CODICI_PARTITA_INIZIATA.includes(codice)) return null;
  if (Number.isFinite(x.fv_preso) && (codice === "voto" || x.stato_partita === "fatto")) return { fv: x.fv_preso, testo: t("formazione.fv_preso", { fv: num(x.fv_preso) }) };
  return { fv: null, testo: etichettaPronta(x) ? x.etichetta.testo : t(STATO_PARTITA[x.stato_partita][0]) };
}
// Sulla pedina anche la partita rinviata prende il posto di «gioca N%» (#284), prima e dopo la scadenza, come l'elenco e Oggi:
// l'etichetta del server («Rinviata») o, con un server vecchio, la stessa parola dai campi grezzi.
function esitoPedina(x) {
  const esito = esitoPartita(x);
  if (esito) return esito;
  const rinviata = etichettaPronta(x) ? x.etichetta.codice === "rinviata" : x.stato_partita === "rinviata" || typeof x.rinvio === "string";
  return rinviata ? { fv: null, testo: etichettaPronta(x) ? x.etichetta.testo : t("tit.st_rinviata") } : null;
}
// Il nome per i lettori di schermo viene dal contenuto, non da un aria-label: le abbreviazioni che si vedono («6,8», «vs NAP»)
// sono nascoste ai lettori e accanto c'è la frase intera, che comincia con il nome (chi usa il controllo vocale dice «Rossi»).
// Con l'aria-label il testo visibile non stava nel nome (axe `label-content-name-mismatch`, WCAG 2.5.3, issue #244).
function pedina(x, k = 0) {
  const p = Math.round((x.p_voto ?? 0) * 100) / 100;            // soglia sul numero che si legge: 69,7% si mostra «70%» e non è «sotto il 70%»
  const esito = esitoPedina(x);
  return `<button class="pedina" data-giocatore="${x.id}" style="--k:${k}">
    <span class="avatar-pedina" aria-hidden="true">${avatar(x)}<b class="fv"${attrPerche(x)}>${num(x.fv_atteso)}</b></span>
    <span class="nome" aria-hidden="true">${esc(cognome(x))}</span>
    ${esito ? `<span class="gioca esito" aria-hidden="true">${esc(esito.testo)}</span>`
      : `<span class="gioca${p < SOGLIA_GIOCA ? " basso" : ""}" aria-hidden="true">${p < SOGLIA_GIOCA ? "⚠ " : ""}${t("giocatore.gioca", { p: perc(p) })}</span>`}
    ${x.avversario ? `<span class="avv" aria-hidden="true">${x.in_casa ? "vs" : "@"} ${distintivo(x.avversario)}</span>` : ""}
    <span class="solo-lettori">${esc(vocePedina(x, esito))}</span>
  </button>`;
}
// Legenda del campo: si vede una volta (finché non tocchi «Ho capito»), poi si riapre dal pulsante ⓘ «Cosa vuol dire».
const legendaCampoVista = () => memLeggi("legenda-campo") === "1";
function legendaCampo() {
  const vista = legendaCampoVista();
  return `<button class="info-campo" type="button" id="info-campo" aria-expanded="${!vista}" aria-controls="legenda-campo" ${vista ? "" : "hidden"}>
      <span aria-hidden="true">ⓘ</span> ${t("formazione.legenda_apri")}</button>
    <div class="legenda-campo" id="legenda-campo" ${vista ? "hidden" : ""}>
      <ul>
        <li><span class="leg-esempio"><b class="fv-esempio">${num(6.8)}</b></span>${t("formazione.legenda_fv")}</li>
        <li><span class="leg-esempio"><span class="gioca">${t("giocatore.gioca", { p: "85%" })}</span></span>${t("formazione.legenda_gioca")}</li>
        <li><span class="leg-esempio"><span class="gioca basso">⚠ ${t("giocatore.gioca", { p: "45%" })}</span></span>${t("formazione.legenda_gioca_basso")}</li>
        <li><span class="leg-esempio"><span class="avv">vs ${distintivo("napoli")}</span></span>${t("formazione.legenda_casa")}</li>
        <li><span class="leg-esempio"><span class="avv">@ ${distintivo("napoli")}</span></span>${t("formazione.legenda_fuori")}</li>
        <li><span class="leg-esempio"></span>${t("formazione.legenda_volto")}</li>
      </ul>
      <button class="bottone secondario" type="button" id="legenda-ok">${t("formazione.legenda_ok")}</button>
    </div>`;
}
function collegaLegenda() {
  const info = $("#info-campo"), leg = $("#legenda-campo"), ok = $("#legenda-ok");
  if (!info || !leg || !ok) return;
  ok.addEventListener("click", () => { memScrivi("legenda-campo", "1"); leg.hidden = true; info.hidden = false; info.setAttribute("aria-expanded", "false"); info.focus(); });
  info.addEventListener("click", () => { leg.hidden = false; info.hidden = true; info.setAttribute("aria-expanded", "true"); ok.focus(); });
}

// La partita in una riga, nella stessa forma del campo: «@ MIL · sab 31 20:45» (fuori) o «vs PAR · oggi 18:30» (in casa).
// «vs PAR» (in casa) / «@ UDI» (in trasferta): nelle celle del calendario e, con la squadra davanti, nelle righe. Per i lettori di schermo «UDI fuori».
const vsAt = x => `<span aria-hidden="true">${x.in_casa ? "vs" : "@"} ${sigla(x.avversario)}</span><span class="solo-lettori">${sigla(x.avversario)} ${t(x.in_casa ? "giocatore.casa" : "giocatore.fuori")}</span>`;
const partitaRiga = x => `${sigla(x.squadra)} ${vsAt(x)}`;
const partitaBreve = x => `${partitaRiga(x)} · ${quando(x.data_partita)}`;

function voceGiocatore(x, posizione, conConfronto = false, sostituisci = false) {
  const p = x.p_voto ?? 0;
  const livello = p >= 0.7 ? "" : p >= 0.4 ? "media" : "bassa";
  const esito = esitoPartita(x);
  return `<li class="${conConfronto ? "con-confronto" : ""}"><button class="voce" data-giocatore="${x.id}">
    ${avatarIndice(x)}
    <span><span class="nome">${posizione ? `<span class="debole">${posizione}. </span>` : ""}${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span>
      <span class="dettaglio" style="display:block"><span class="diff d${x.difficolta}"><i></i></span> ${partitaBreve(x)}</span>
      <span class="etichette">${etichetteGiocatore(x)}</span></span>
    ${esito ? `<span class="valore esito">${esito.fv != null ? `<b>${num(esito.fv)}</b><span class="debole piccolo">${t("mercato.fantavoto")}</span>`
        : `<b class="debole" aria-hidden="true">–</b>`}</span>`
      : `<span class="valore"><b${attrPerche(x)}>${num(x.fv_atteso)}</b><span class="debole piccolo">${t("giocatore.gioca", { p: perc(p) })}</span>
      <span class="barra-p ${livello}"><i style="width:${Math.round(p * 100)}%"></i></span></span>`}
  </button>${conConfronto ? (sostituisci
    ? `<button class="confronta-mini" data-sostituisci="${x.id}" aria-label="${t("formazione.sostituisci_aria", { nome: esc(x.nome) })}" title="${t("formazione.sostituisci_con")}">✎</button>`
    : `<button class="confronta-mini" data-confronta="${x.id}" aria-label="${t("formazione.confronta_aria", { nome: esc(x.nome) })}" title="${t("formazione.confronta_con")}">⇄</button>`) : ""}</li>`;
}

// Il numero a destra di una riga della Rosa: come le righe della Formazione (voceGiocatore). Prima della partita fantavoto atteso
// e «gioca N%»; a partita iniziata il fantavoto preso oppure «–» (lo stato è già nell'etichetta), mai «gioca N%».
function valoreRosa(p, x) {
  if (!p) return `<span class="valore"><span class="debole piccolo">${x.id ? t("scambio.non_gioca") : "?"}</span></span>`;
  const esito = esitoPartita(p);
  if (esito) return `<span class="valore esito">${esito.fv != null ? `<b>${num(esito.fv)}</b><span class="debole piccolo">${t("mercato.fantavoto")}</span>` : `<b class="debole" aria-hidden="true">–</b>`}</span>`;
  return `<span class="valore"><b>${num(p.fv_atteso)}</b><span class="debole piccolo">${t("giocatore.gioca", { p: perc(p.p_voto) })}</span></span>`;
}

// ---------------------------------------------------------------- navigazione
document.querySelectorAll(".schede button").forEach(b => b.addEventListener("click", () => vai(b.dataset.vista)));
let timerConto = null;
let regoleAC = null;      // gestori della schermata regole: si staccano quando si esce

function novitaDaVedere() {
  if (!funz("novita")) return false;
  try { return !!(stato.info && stato.info.versione && localStorage.getItem("novita-vista") !== stato.info.versione); } catch { return false; }
}

// «Modifica a mano» cambiata e non salvata nella Formazione (calcolato a ogni disegno, `sc.nonSalvata`).
const modificaNonSalvata = () => stato.vista === "formazione" && !!(stato.scelta && stato.scelta.nonSalvata);
// Prima di cambiare scheda si chiede; chi conferma lascia le modifiche (tornando, si riparte dalla consigliata o dalla scelta salvata).
function lasciaFormazione() {
  if (!modificaNonSalvata()) return true;
  if (!confirm(t("formazione.esci_senza_salvare"))) return false;
  Object.assign(stato.scelta, { manuale: null, nonSalvata: false, richiesta: (stato.scelta.richiesta || 0) + 1, occupato: false });
  return true;
}
// Ricaricare o chiudere la pagina: il browser mostra la sua domanda (il testo lo sceglie lui).
window.addEventListener("beforeunload", ev => { if (modificaNonSalvata()) { ev.preventDefault(); ev.returnValue = ""; } });

function vai(vista, gruppo) {
  if (vista !== "formazione" && !lasciaFormazione()) return;             // resta nella Formazione: la modifica a mano non è salvata
  const imp = vista === "impostazioni";                                   // l'ingranaggio in testata: non è una delle schede della barra
  if (vista === "lega") vista = ambitoVoce(stato.legaTorna);              // le voci della vecchia Lega stanno in Squadra o in Altro
  if (!imp && !SCHEDA_DI(vista)) vista = "oggi";
  const scheda = imp ? null : SCHEDA_DI(vista);                           // la scheda della barra che si accende
  const cambio = vista !== stato.vista;
  stato.vista = vista;
  const nomeVista = imp ? { textContent: t("shell.impostazioni") } : document.querySelector(`.schede button[data-vista="${scheda}"] span`);
  document.title = nomeVista ? `${nomeVista.textContent} · SchieraXI` : "SchieraXI – consigli formazione fantacalcio";          // chi usa un lettore di schermo sente dove è arrivato
  document.querySelectorAll(".schede button").forEach(b => {
    b.classList.toggle("attiva", b.dataset.vista === scheda);
    if (b.dataset.vista === scheda) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  const ing = $("#bottone-impostazioni");
  ing.classList.toggle("attiva", imp);
  if (imp) ing.setAttribute("aria-current", "page"); else ing.removeAttribute("aria-current");
  const barra = $(".schede"), lente = $(".lente");
  barra.classList.toggle("fuori", imp);
  if (!imp) barra.style.setProperty("--i", VISTE.indexOf(scheda));
  if (!imp && cambio && lente) { lente.classList.remove("muove"); void lente.offsetWidth; lente.classList.add("muove"); }
  if (!imp) try { localStorage.setItem("vista", vista); } catch { /* niente memoria: va bene lo stesso */ }
  window.scrollTo(0, 0);
  contenuto.classList.remove("ridisegna");
  delete contenuto.dataset.gruppo;
  clearInterval(timerConto);
  fermaLive();
  if (regoleAC) { regoleAC.abort(); regoleAC = null; }
  stato.punteggioPrec = null;
  if (imp) { vistaImpostazioni(gruppo); return; }
  ({ oggi: vistaOggi, formazione: vistaFormazione, squadra: () => vistaLega("squadra"), altro: () => vistaLega("altro"), mercato: vistaMercato, scambi: vistaScambi })[vista]();
}

// Stemma e maglia delle squadre (caricati dall'utente nella Lega).
const urlImg = (nome, tipo) => `/api/squadre/immagine?squadra=${encodeURIComponent(nome)}&tipo=${tipo}&v=${stato.vImg || 0}`;
async function caricaSquadre(seServono = false) {
  // seServono: all'avvio, se le rose non ci sono ancora (primo avvio) non si chiede nulla: niente errore in console.
  if (seServono && stato.info && stato.info.rose_importate === false) stato.squadre = [];
  else { try { stato.squadre = await api("/api/squadre"); } catch { stato.squadre = stato.squadre || []; } }
  const mia = (stato.squadre || []).find(s => s.mia);
  const img = $("#stemma-testata");
  if (mia && mia.immagini.stemma) { img.src = urlImg(mia.nome, "stemma"); img.hidden = false; } else img.hidden = true;
}
const miaSquadra = () => (stato.squadre || []).find(s => s.mia);

async function caricaTratti() {
  try { stato.tratti = (await api("/api/avatar")).tratti || null; } catch { stato.tratti = null; }     // senza: volti tutti dal seme
}
async function caricaFoto() {
  const tratti = caricaTratti();
  stato.foto = null; stato.fotoAttive = false;
  try {
    const r = { attive: false };                 // versione pubblica: nessuna foto
    if (r.attive) { stato.fotoAttive = true; stato.foto = new Set(r.ids); }     // di norma spente: nessuna foto, solo i volti illustrati
  } catch { /* senza foto: solo i volti illustrati */ }
  await tratti;
}

// Quali funzioni sono accese per questo utente (GET /api/funzioni). Se il server è vecchio o non risponde: tutto acceso, come prima.
async function caricaFunzioni() {
  try {
    const r = await api("/api/funzioni");
    stato.funzioni = r && r.funzioni && typeof r.funzioni === "object" ? { funzioni: r.funzioni, mostraTutte: !!r.mostra_tutte } : null;
  } catch { stato.funzioni = null; }
}

async function caricaInfo() {
  try {
    stato.info = await api("/api/stato");
    const i = stato.info;
    $("#titolo").textContent = i.mia_squadra || "SchieraXI";
    const quandoAgg = i.ultimo_aggiornamento ? new Date(i.ultimo_aggiornamento) : null;
    // giornata e data dei dati in due pezzi: sui telefoni stanno su due righe (stile.css), altrimenti la data si tagliava a 390 px
    const pezzo = (classe, testo) => { const e = document.createElement("span"); e.className = classe; e.textContent = testo; return e; };
    const dati = (quandoAgg ? t("testata.dati_del", { data: fData(quandoAgg), ora: fOra(quandoAgg) }) : t("testata.mai")).replace(/^\s*·\s*/, "");
    $("#sottotitolo").replaceChildren(...(i.prossima_giornata ? [pezzo("sotto-giornata", t("testata.giornata", { n: i.prossima_giornata_lega || i.prossima_giornata })), pezzo("sotto-sep", " · ")] : []),
      pezzo("sotto-dati", dati));
    $("#bottone-aggiorna").classList.toggle("gira", i.aggiornamento_in_corso);
  } catch (e) {
    $("#sottotitolo").textContent = t("testata.offline");
  }
}

// ---------------------------------------------------------------- aggiornamento dati
$("#bottone-aggiorna").addEventListener("click", async () => {
  const b = $("#bottone-aggiorna");
  try {
    const r = await api("/api/aggiorna", { method: "POST" });
    if (!r.avviato) { avviso(r.messaggio); return; }
    b.classList.add("gira");
    avviso(t("aggiorna.avviato"));
    let tentativi = 0;
    const controlla = async () => {
      let s;
      try { s = await api("/api/aggiorna"); tentativi = 0; }
      catch (e) {
        if (++tentativi < 5) { setTimeout(controlla, 3000); return; }
        b.classList.remove("gira");
        avviso(t("aggiorna.non_so"));
        return;
      }
      if (s.in_corso) { setTimeout(controlla, 2000); return; }
      b.classList.remove("gira");
      avviso(s.errori.length ? t("aggiorna.problemi", { errori: s.errori.join("; ") }) : t("aggiorna.ok"), 6000);
      stato.calendario = null;
      svuotaCache();
      await caricaInfo();
      vai(stato.vista);
    };
    setTimeout(controlla, 2000);
  } catch (e) { avviso(e.message); }
});

// ---------------------------------------------------------------- Oggi
function testoConto(o) {
  // il conto alla rovescia va alla SCADENZA della formazione (prima partita meno i minuti della regola della lega); i server vecchi non la mandano
  const inizio = parseData(o.scadenza || o.inizio);
  if (!inizio) return { grande: "–", piccolo: t("oggi.calendario_no") };
  const min = Math.round((inizio - new Date()) / 60000);
  const nGiornata = o.giornata_lega || o.giornata;
  if (min <= 0) return { grande: t("oggi.chiusa"), piccolo: t("oggi.chiusa_dettaglio", { n: nGiornata, quando: quando(o.scadenza || o.inizio) }) };
  const g = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
  // ogni numero resta attaccato alla sua unità (spazio che non va a capo): «1 giorno» / «8 h», mai «h» da sola su una riga (issue #286)
  const grande = (g >= 1 ? tp("oggi.giorni_ore", g, { h }) : h >= 1 ? `${h} h ${m} min` : `${m} min`).replace(/(\d) /g, "$1 ");
  return { grande, piccolo: o.scadenza && o.scadenza !== o.inizio
    ? t("oggi.si_chiude", { quando: quando(o.scadenza), min: o.minuti_scadenza })
    : t("oggi.prima_partita", { quando: quando(o.inizio) }) };
}

function vistaOggi() {
  caricaConCache("oggi", "/api/oggi", mostraOggi, t("oggi.preparo"));
}

// Account nuovo, senza rose: benvenuto e un solo pulsante. Il primo avvio guidato si apre da solo (una volta, vedi primoAvvioSeServe).
function mostraOggiSenzaRose(o, opz) {
  clearInterval(timerConto); fermaLive();
  pagina(`<div class="carta benvenuto" role="status"><h2>${t("oggi.benvenuto_schieraxi")}</h2>
    <p class="debole">${t("oggi.per_cominciare_importa")}</p>
    <div class="pulsanti"><button class="bottone" type="button" data-importa-rose>${t("comune.importa_rose")}</button></div></div>`, opz);
  if (typeof primoAvvioSeServe === "function") primoAvvioSeServe();
}

// Fasi della giornata (campo `fase` di /api/oggi, docs/API.md): «prima» come sempre; «in_corso» la giornata in diretta al posto
// dei consigli su chi schierare; «finita» il riepilogo e la prossima giornata. Server vecchio senza `fase`: tutto come prima.
const STATO_LIVE = { senza_voto: "oggi.st_senza_voto", attesa_voti: "oggi.st_attesa_voti", in_corso: "oggi.st_in_corso", rinviata: "oggi.st_rinviata" };
function valoreLive(g) {
  if (g.stato === "fatto") return `<b class="fv-fatto">${num(g.fantavoto)}</b>`;
  if (g.stato === "da_giocare" && g.data) return `<span class="debole piccolo">${esc(quando(g.data))}</span>`;
  if (etichettaPronta(g)) return `<span class="piccolo tono ${classeTono(g.etichetta)}">${esc(g.etichetta.testo)}</span>`;
  return `<span class="debole piccolo">${t(STATO_LIVE[g.stato] || "oggi.st_da_giocare")}</span>`;
}

function cardInCorso(c, f) {
  if (!c || !Array.isArray(c.giocatori)) return "";
  const righe = c.giocatori.filter(g => g.a_punteggio).map(g => `<button class="avviso-riga" data-giocatore="${Number(g.id)}">${badgeRuolo(g.ruolo)}
    <span><span class="nome">${esc(g.nome)}</span> <span class="dettaglio">${sigla(g.squadra)}</span>
      ${g.titolare ? "" : `<div class="dettaglio nota">${t("oggi.dalla_panchina")}</div>`}</span>${valoreLive(g)}</button>`).join("");
  const cambi = (c.sostituzioni || []).filter(s => s && s.esce).map(s => `<li><span>${esc(s.esce.nome)} → ${s.entra ? esc(s.entra.nome) : t("oggi.nessun_sostituto")}</span>
    <span class="etichetta ${s.certa ? "" : "arancio"}">${t(s.certa ? "oggi.cambio_fatto" : "oggi.cambio_probabile")}</span></li>`).join("");
  return `<div class="carta in-corso" id="oggi-in-corso">
    <div class="riga"><div><div class="debole">${t("oggi.punti_finora")}</div><div class="grande" id="oggi-fatti">${num(c.punti_fatti)}</div></div>
      <div class="a-destra"><div class="debole">${t("oggi.a_fine_giornata")}</div><div class="grande">≈ ${num(c.punti_previsti)}</div>
        ${f && f.punteggio_atteso != null ? `<div class="debole piccolo">${t("oggi.attesi_prima", { n: num(f.punteggio_atteso) })}</div>` : ""}</div></div>
    <div class="debole piccolo">${c.ancora_da_giocare ? tp("oggi.ancora_da_giocare", c.ancora_da_giocare) : t("oggi.tutti_giocato")}</div>
    ${righe}
    ${cambi ? `<div class="etichetta-riga">${t("oggi.cambi_panchina")}</div><ul class="cambi-live">${cambi}</ul>` : ""}
  </div>`;
}

// Chi è entrato a giornata iniziata senza una formazione (`senza_formazione` di /api/oggi): niente punti, si prepara la prossima.
function cardSenzaFormazione(p) {
  const gia = p && (p.con_probabili || !parseData(p.prepara_da) || parseData(p.prepara_da) <= new Date());
  return `<div class="carta riepilogo-giornata" id="oggi-senza-formazione">
    <h2>${t("oggi.gia_iniziata")}</h2><p>${t("oggi.gia_iniziata_testo")}</p>
    ${p && p.scadenza ? `<p class="prossima-giornata">${t("oggi.prossima_chiude", { n: p.giornata_lega || p.giornata, quando: esc(quando(p.scadenza)) })}
      ${gia ? t("oggi.prossima_pronta") : t("oggi.prossima_da", { quando: esc(quando(p.prepara_da)) })}</p>` : ""}
    <div class="pulsanti"><button class="bottone" data-vai="formazione">${t("oggi.prepara_prossima")}</button></div></div>`;
}

function cardRiepilogo(r, p) {
  if (!r && !p) return "";
  let html = "";
  if (r) {
    const tua = r.formazione_di === "tua";
    html += `<h2>${t("oggi.giornata_finita", { n: r.giornata_lega || r.giornata })}</h2>
      <div class="riga"><div><div class="debole">${t(tua ? "oggi.la_tua_formazione" : "oggi.la_consigliata")}</div><div class="grande">${num(r.punti_fatti)}</div>
        <div class="debole piccolo">${t("oggi.punti_fatti")}</div></div>
        ${r.punti_attesi != null ? `<div class="a-destra"><div class="debole">${t("oggi.punti_attesi")}</div><div class="grande">${num(r.punti_attesi)}</div></div>` : ""}</div>
      ${tua && r.consigliata ? `<p class="piccolo">${t("oggi.con_consigliata", { fatti: num(r.consigliata.punti_fatti), attesi: num(r.consigliata.punti_attesi) })}</p>` : ""}
      ${Array.isArray(r.recuperi) && r.recuperi.length ? `<p class="attenzione piccolo" id="oggi-recuperi">${t("oggi.recupero_manca", { partite: r.recuperi.map(x => `${sigla(x.casa)}–${sigla(x.trasferta)}`).join(", ") })}</p>` : ""}
      ${r.rinvio && typeof menuRinvio === "function" ? menuRinvio(r.rinvio) : ""}
      ${r.nel_diario ? "" : `<p class="debole piccolo">${t("oggi.confronto_in_arrivo")}</p>`}
      <div class="pulsanti"><button class="bottone secondario" type="button" data-apri-diario="${Number(r.giornata)}">${t("oggi.apri_diario")}</button></div>`;
  }
  if (p && p.scadenza) {
    const gia = p.con_probabili || !parseData(p.prepara_da) || parseData(p.prepara_da) <= new Date();
    html += `<p class="prossima-giornata">${t("oggi.prossima_chiude", { n: p.giornata_lega || p.giornata, quando: esc(quando(p.scadenza)) })}
      ${gia ? t("oggi.prossima_pronta") : t("oggi.prossima_da", { quando: esc(quando(p.prepara_da)) })}</p>`;
  }
  return `<div class="carta riepilogo-giornata" id="oggi-riepilogo">${html}</div>`;
}

// Nome e slogan in cima a Oggi (MARCHIO.md). Il carattere sta nella variabile CSS --font-marchio; a voce si legge «Schiera undici».
function marchioOggi() {
  const xi = `<span class="xi">XI</span>`;
  return `<div class="marchio-oggi">
    <p class="wordmark"><span aria-hidden="true">Schiera${xi}</span><span class="solo-lettori">${t("marchio.nome_voce")}</span></p>
    <p class="slogan-oggi"><span aria-hidden="true">${t("marchio.slogan", { xi })}</span><span class="solo-lettori">${t("marchio.slogan_voce")}</span></p>
  </div>`;
}
// Partite rinviate della giornata (campo `rinvio` di /api/oggi, docs/API.md): quali, i miei giocatori coinvolti e cosa vale per
// questa giornata, cambiabile solo per lei (PUT /api/regole/rinvio). Server vecchio senza il campo: niente riquadro.
const MODI_RINVIO = ["aspetta", "senza_voto", "voto_ufficio"];
function nomeModoRinvio(m, voto) {
  if (m === "voto_ufficio") return t("oggi.rinvio_ufficio", { v: num(voto ?? 6, Number.isInteger(voto ?? 6) ? 0 : 1) });
  return m === "aspetta" || m === "senza_voto" ? t("oggi.rinvio_" + m) : String(m);
}
// Il menu «per questa giornata i loro giocatori…» (riquadro di Oggi e riepilogo della giornata finita): cambia solo quella giornata.
// Un <select> non va a capo e tagliava la scelta («aspettano il recupero (conta il suo vo»): la scelta si legge intera nel riquadro
// (`.menu-scelta-testo`, va a capo), il <select> vero sta sopra, trasparente, e apre il menu del sistema. Come MenuRinvio dell'iPhone.
function menuRinvio(rv) {
  const modi = Array.isArray(rv.modi) && rv.modi.length ? rv.modi : MODI_RINVIO;
  const voto = rv.voto_ufficio ?? rv.valore;
  const scelto = modi.includes(rv.modo) ? rv.modo : modi[0];                // quello che il <select> mostra
  return `<label class="rinvio-scelta"><span class="debole">${t("oggi.rinvio_domanda")}</span>
      <span class="menu-scelta"><span class="menu-scelta-testo" aria-hidden="true">${esc(nomeModoRinvio(scelto, voto))}</span>
      <select class="rinvio-modo" data-giornata="${Number(rv.giornata)}" data-stagione="${esc(rv.stagione || "")}">${modi.map(m => `<option value="${esc(m)}" ${m === scelto ? "selected" : ""}>${esc(nomeModoRinvio(m, voto))}</option>`).join("")}</select></span></label>
    <p class="debole piccolo">${rv.eccezione ? t("oggi.rinvio_eccezione", { regola: esc(nomeModoRinvio(rv.predefinito, voto)) }) : t("oggi.rinvio_regola_lega")}</p>`;
}
function cardRinvio(rv) {
  if (!rv || !Array.isArray(rv.partite) || !rv.partite.length) return "";
  const partite = rv.partite.map(p => `<li><b>${sigla(p.casa)} vs ${sigla(p.trasferta)}</b>
    <span class="debole piccolo">${parseData(p.data) ? t("oggi.rinvio_recupero", { quando: esc(quando(p.data)) }) : t("oggi.rinvio_da_definire")}</span></li>`).join("");
  const miei = (rv.miei || []).map(g => esc(g.nome)).join(", ");
  return `<div class="carta rinvio" id="oggi-rinvio"><h2>${t(rv.partite.length > 1 ? "oggi.rinvio_titolo_n" : "oggi.rinvio_titolo_1")}</h2>
    <ul class="elenco-rinvii">${partite}</ul>
    ${miei ? `<p class="piccolo">${t("oggi.rinvio_miei", { nomi: miei })}</p>` : ""}
    ${menuRinvio(rv)}
  </div>`;
}
function collegaRinvio() {
  document.querySelectorAll("select.rinvio-modo").forEach(sel => {
    const riquadro = sel.closest(".menu-scelta"), testo = riquadro && riquadro.querySelector(".menu-scelta-testo");
    const mostra = () => { if (testo) testo.textContent = sel.selectedOptions[0] ? sel.selectedOptions[0].textContent : ""; };
    let salvato = sel.value;
    sel.addEventListener("change", async () => {
      mostra();
      sel.disabled = true;
      try {
        const corpo = { giornata: Number(sel.dataset.giornata), modo: sel.value };
        if (sel.dataset.stagione) corpo.stagione = sel.dataset.stagione;
        await api("/api/regole/rinvio", { method: "PUT", body: JSON.stringify(corpo) });
        salvato = sel.value;
        svuotaCache();
        avviso(t("oggi.rinvio_salvato"));
        vistaOggi();
      } catch (e) { avviso(e.message, 8000); sel.value = salvato; mostra(); sel.disabled = false; }   // resta la scelta salvata
    });
  });
}

function mostraOggi(o, opz = {}) {
  if (o.senza_rose) { mostraOggiSenzaRose(o, opz); return; }
  const fase = o.fase || "prima";
  const inCorso = fase === "in_corso", finita = fase === "finita";
  const c = testoConto(o);
  // a formazione chiusa niente «Da controllare» né migliori (non si può più cambiare); a giornata finita la prossima è ancora lontana
  const inFormazione = inCorso || finita ? [] : o.avvisi.filter(a => a.in_formazione);
  const migliori = inCorso || finita ? [] : o.migliori;
  const indisponibili = inCorso ? [] : o.avvisi.filter(a => !a.in_formazione && (a.tipo === "infortunato" || a.tipo === "squalificato"));
  const altri = inCorso ? [] : o.avvisi.filter(a => !a.in_formazione && a.tipo === "diffidato");
  const riga = a => {
    const pronta = etichettaPronta(a);
    const colore = pronta ? ({ negativo: "rosso", attenzione: "arancio" }[a.etichetta.tono] || "giallo")
      : a.tipo === "infortunato" || a.tipo === "squalificato" ? "rosso" : a.tipo === "dubbio" ? "arancio" : "giallo";
    const testo = pronta ? esc(a.etichetta.testo)
      : { infortunato: t("oggi.infortunato"), squalificato: t("oggi.squalificato"), dubbio: t("oggi.dubbio", { p: perc(a.p_voto) }), diffidato: t("oggi.diffidato_tipo") }[a.tipo];
    return `<button class="avviso-riga" data-giocatore="${a.id}">${badgeRuolo(a.ruolo)}
      <span><span class="nome">${esc(a.nome)}</span> <span class="dettaglio">${sigla(a.squadra)}</span>
        <div class="dettaglio nota">${testo}${a.nota ? ` · ${esc(a.nota)}` : ""}</div></span><span class="pallino-stato ${colore}"></span></button>`;
  };
  // partite del turno, divise per giorno
  const miei = o.miei_titolari || {};
  const perGiorno = {};
  o.partite.forEach(p => { const d = parseData(p.data); const k = d ? d.toDateString() : "?"; (perGiorno[k] ||= { d, lista: [] }).lista.push(p); });
  // le partite senza data (rinviate, recupero da definire) in fondo: prima si vede quello che si gioca
  const partite = Object.values(perGiorno).sort((x, y) => (x.d ? 0 : 1) - (y.d ? 0 : 1)).map(g => {
    const locale = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T12:00`;
    const titolo = g.d ? quando(locale(g.d)).replace(/ \d\d:\d\d$/, "") : t("oggi.data_da_definire");
    return `<div class="giorno-titolo">${titolo}</div>` + g.lista.map(p => {
      const ora = parseData(p.data);
      const rinviata = p.stato === "rinviata";                                // rinvio noto (diretta o calendario): l'etichetta al posto dell'ora
      // stato del server (fasi.py: calendario, diretta, poi orario): una partita cominciata senza dati di diretta dice «In corso», non l'ora
      const oraTesto = rinviata ? t("live.rinviata") : p.stato === "in_corso" ? t("oggi.partita_in_corso")
        : p.stato === "finita" && !p.giocata ? t("live.finita") : ora ? fOra(ora) : "–";
      const mm = [p.casa, p.trasferta].flatMap(s => (miei[s] || []).map(g => ({ ...g, squadra: s })));       // miei titolari delle due squadre
      const nomiMiei = mm.map(g => g.nome).join(", ");
      const ptUff = LiveSchieraxi.punteggioUfficiale(p);                         // risultato del calendario: c'è anche senza la diretta
      return `<div class="partita ${p.giocata || p.stato === "finita" ? "giocata" : ""} ${rinviata ? "rinviata" : ""} ${mm.length ? "mia" : ""}" data-k="${esc(LiveSchieraxi.chiave(p))}" data-ora="${esc(oraTesto)}" data-giocata="${p.giocata ? 1 : 0}" data-pt="${esc(ptUff || "")}">
        <span class="ora">${oraTesto}</span>
        <span class="sq casa">${sigla(p.casa)}</span><span class="vs">vs</span><span class="sq trasf">${sigla(p.trasferta)}</span><span class="pt">${esc(ptUff || "")}</span>
        ${mm.length ? `<span class="miei-live" role="img" aria-label="${esc(t("oggi.tuoi_titolari", { nomi: nomiMiei }))}">${mm.slice(0, 4).map(g => `<span class="mini-av">${avatar(g)}</span>`).join("")}${mm.length > 4 ? `<b class="piu">+${mm.length - 4}</b>` : ""}<span class="miei-testo">${tp("oggi.n_titolari", mm.length)}</span></span>` : ""}
        <span class="eventi-live" hidden></span></div>`;
    }).join("");
  }).join("");
  pagina(`
    <div class="colonne colonne-oggi"><div class="col">
    ${marchioOggi()}
    <div class="carta hero conto${miaSquadra() && miaSquadra().immagini.maglia ? " con-maglia" : ""}">
      ${miaSquadra() && miaSquadra().immagini.maglia ? `<img class="maglia-hero" src="${urlImg(miaSquadra().nome, "maglia")}" alt="">` : ""}
      <div class="debole">${t("testata.giornata", { n: o.giornata_lega || o.giornata })}</div>
      <div class="enorme" id="conto">${esc(c.grande)}</div>
      <div class="debole" id="conto-sotto">${esc(c.piccolo)}</div>
    </div>
    ${finita ? cardRiepilogo(o.riepilogo, o.prossima) : ""}
    ${inCorso ? (o.senza_formazione ? cardSenzaFormazione(o.prossima) : cardInCorso(o.in_corso, o.formazione)) : ""}
    ${cardRinvio(o.rinvio)}
    ${cardDaFare(o.da_fare)}
    ${novitaDaVedere() ? `<button class="banner-novita" data-vai-novita>${t("oggi.novita_banner", { versione: esc(stato.info.versione) })}</button>` : ""}
    ${o.con_probabili || inCorso || finita ? "" : `<div class="attenzione">${t("oggi.mancano_probabili_formazioni")}</div>`}
    ${o.probabili && !inCorso ? `<div class="debole piccolo probabili-fresche" id="probabili-fresche">${esc(testoDi(o.probabili))} (${esc(o.probabili.eta_frase ? testoDi(o.probabili, "eta") : traduciDurata(o.probabili.eta))})</div>${o.probabili.vecchie && o.probabili.avviso ? `<div class="attenzione" role="status">${esc(testoDi(o.probabili, "avviso"))}</div>` : ""}` : ""}
    ${inCorso && (o.in_corso || o.senza_formazione) ? "" : `<div class="carta">
      <div class="riga"><div><div class="debole">${t(o.formazione.tua_scelta ? "oggi.tua_formazione_scelta" : "oggi.tua_formazione")}</div><div class="grande">${esc(o.formazione.modulo)}</div></div>
        <div style="text-align:right"><div class="debole">${t("oggi.punti_attesi")}</div><div class="grande" id="oggi-punti">${num(o.formazione.punteggio_atteso)}</div>${fraseFascia(o.formazione) ? `<div class="debole piccolo" id="oggi-fascia">${esc(fraseFascia(o.formazione))}</div>` : ""}</div></div>
      <div class="pulsanti"><button class="bottone" data-vai="formazione">${t("oggi.apri_formazione")}</button></div>
    </div>`}
    </div><div class="col">
    ${inFormazione.length ? `<div class="carta"><h2>${t("oggi.da_controllare")}</h2><div class="debole piccolo">${t("oggi.giocatori_formazione_con")}</div>${inFormazione.map(riga).join("")}</div>` : ""}
    ${migliori.length ? `<div class="carta"><h2>${t("oggi.tuoi_migliori_della")}</h2><ul class="elenco">${migliori.map(x => voceGiocatore({ ...x, indice: null })).join("")}</ul></div>` : ""}
    ${indisponibili.length ? `<div class="carta"><details><summary>${t("oggi.indisponibili", { n: indisponibili.length })}</summary>${indisponibili.map(riga).join("")}</details></div>` : ""}
    ${altri.length ? `<div class="carta"><h2>${t("oggi.diffidati")}</h2>${altri.map(riga).join("")}</div>` : ""}
    <div class="carta"><h2>${t("oggi.partite_del_turno")}</h2><div class="partite-turno">${partite || `<div class="vuoto">${t("oggi.nessuna_partita_calendario")}</div>`}</div>
      <div class="debole piccolo live-agg" id="live-agg" hidden></div><div class="solo-lettori" id="live-annuncio" role="status" aria-live="polite"></div></div>
    </div></div>`, opz);
  collegaDaFare(o.da_fare);
  collegaRinvio();
  const diario = $("[data-apri-diario]");
  if (diario) diario.addEventListener("click", () => apriDiario(Number(diario.dataset.apriDiario) || undefined));
  if ($("#oggi-punti")) animaNumero($("#oggi-punti"), opz.sostituisce ? (o.formazione.punteggio_atteso ?? 0) : 0, o.formazione.punteggio_atteso ?? 0);
  if (funz("live")) avviaLive(miei);                   // con «Risultati in diretta» spenta non si chiede nulla al server
  // il conto alla rovescia si aggiorna da solo finché si resta in questa sezione
  clearInterval(timerConto);
  const idTimer = timerConto = setInterval(() => {
    const el = $("#conto");
    if (!el) { clearInterval(idTimer); return; }
    const ct = testoConto(o);
    el.textContent = ct.grande;
    const s = $("#conto-sotto");
    if (s) s.textContent = ct.piccolo;
  }, 30000);
}

// ---------------------------------------------------------------- risultati in diretta (Oggi > Partite del turno)
// Si richiede /api/live solo mentre la scheda è visibile e c'è una partita in corso o in arrivo (LiveSchieraxi.prossimoControllo);
// il server non fa richieste esterne per noi: legge una cache condivisa (vedi docs/LIVE.md).
let timerLive = null, giroLive = null, rispostaLive = null;
const golVisti = {};        // ultimo punteggio visto per partita: serve a far "pulsare" solo i gol nuovi

const LIVE_EVENTI = { gol: "oggi.ev_gol", rigore: "oggi.ev_rigore", autogol: "oggi.ev_autogol", rigore_sbagliato: "oggi.ev_rigore_sbagliato", rosso: "oggi.ev_rosso" };

function fermaLive() { clearTimeout(timerLive); timerLive = null; giroLive = null; }

// Una sola richiesta alla volta: Oggi si disegna due volte (copia salvata, poi dati nuovi) e ogni disegno fa partire un giro.
let leggendoLive = null;
function leggiLive() {
  if (!leggendoLive) leggendoLive = fetch("/api/live", { credentials: "same-origin" }).then(r => r.ok ? r.json() : null).finally(() => { leggendoLive = null; });
  return leggendoLive;
}

function avviaLive(miei) {
  fermaLive();
  const mio = [].concat(...Object.values(miei));
  const giro = async () => {
    clearTimeout(timerLive);
    if (!$(".partite-turno .partita")) { fermaLive(); return; }            // non siamo più in Oggi
    if (document.hidden) return;                                            // riparte da solo quando la scheda torna visibile
    let live = null;
    try { live = await leggiLive(); } catch { /* rete assente: si riprova più avanti */ }
    if (giroLive !== giro) return;                                          // nel frattempo si è cambiata schermata
    if (live) { rispostaLive = live; disegnaLive(live, mio); }
    const ms = live ? LiveSchieraxi.prossimoControllo(live, new Date()) : (rispostaLive && LiveSchieraxi.prossimoControllo(rispostaLive, new Date()) ? 90000 : null);
    if (ms) timerLive = setTimeout(giro, ms);
  };
  giroLive = giro;
  giro();
}
document.addEventListener("visibilitychange", () => { if (!document.hidden && giroLive) giroLive(); else clearTimeout(timerLive); });

function disegnaLive(live, mio) {
  const L = LiveSchieraxi;
  const nuovi = new Set(L.gol(golVisti, live));
  let annuncio = "";
  document.querySelectorAll(".partite-turno .partita").forEach(el => {
    const p = live.partite.find(x => L.chiave(x) === el.dataset.k);
    if (!p) return;
    const et = L.etichetta(p), pt = L.punteggio(p);
    el.classList.toggle("in-diretta", L.inDiretta(p));
    el.classList.toggle("giocata", p.stato === "finita" || (p.stato === "da_giocare" && el.dataset.giocata === "1"));
    const ora = el.querySelector(".ora");
    ora.classList.toggle("live", et.live);
    ora.textContent = "";
    if (et.live) {
      const b = document.createElement("b"); b.className = "badge-live"; b.textContent = et.testo;
      const m = document.createElement("span"); m.className = "minuto"; m.textContent = et.minuto;
      ora.append(b, m);
    } else ora.textContent = et.testo || el.dataset.ora;
    const pun = el.querySelector(".pt");                                   // colonna del punteggio: sempre la stessa, allineata a destra
    pun.textContent = pt || el.dataset.pt || "";                           // la diretta senza punteggio non cancella quello ufficiale
    if (nuovi.has(el.dataset.k)) {                                          // gol appena segnato: evidenziazione breve (calma con «Riduci movimento»)
      pun.classList.remove("gol"); void pun.offsetWidth; pun.classList.add("gol");
      setTimeout(() => pun.classList.remove("gol"), 2200);
      annuncio += t("oggi.annuncio_gol", { casa: sigla(p.casa), gc: p.gol_casa, trasf: sigla(p.trasferta), gt: p.gol_trasferta }) + " ";
    }
    const zona = el.querySelector(".eventi-live");
    const ev = L.eventiVisibili(p);
    zona.hidden = !ev.length;
    el.classList.toggle("con-eventi", ev.length > 0);
    zona.textContent = "";
    const colonne = { casa: document.createElement("div"), trasferta: document.createElement("div") };    // casa a sinistra, trasferta a destra
    colonne.casa.className = "ev-col"; colonne.trasferta.className = "ev-col trasf";
    ev.forEach(e => {
      const r = document.createElement("span");
      r.className = `ev-riga ${e.tipo}${L.eMio(e.chi, mio) ? " mio" : ""}`;
      const i = document.createElement("i"); i.className = `ev ${e.tipo}`;
      i.setAttribute("title", Object.hasOwn(LIVE_EVENTI, e.tipo) ? t(LIVE_EVENTI[e.tipo]) : "");
      r.append(i, document.createTextNode(L.testoEvento(e)));
      colonne[e.squadra === "trasferta" ? "trasferta" : "casa"].append(r);
    });
    zona.append(colonne.casa, colonne.trasferta);
  });
  const agg = $("#live-agg");
  if (agg) {
    agg.hidden = !live.aggiornato_il || !(live.in_corso || live.partite.some(x => x.stato === "finita" && x.eventi.length));
    const ora = live.aggiornato_il && parseData(live.aggiornato_il);
    agg.textContent = ora ? t("oggi.risultati_agg", { ora: fOra(ora) }) : "";
  }
  const ann = $("#live-annuncio");
  if (ann && annuncio) ann.textContent = annuncio;
}

// ---------------------------------------------------------------- formazione
function vistaFormazione() {
  const squadra = stato.squadraVista;
  caricaConCache("formazione-" + (squadra || "mia"), "/api/formazione" + (squadra ? `?squadra=${encodeURIComponent(squadra)}` : ""),
    (f, opz) => mostraFormazione(f, squadra, opz), t("formazione.calcolo"));
}

// Nome e descrizione di uno stile: in italiano quelli del server (se ci sono), nelle altre lingue quelli dei testi (per livello di rischio).
const codiceStile = r => String(r).replace("-", "m");
const nomeStile = l => (LINGUA === "it" && l.nome) || t("formazione.stile_nome_" + codiceStile(l.rischio));
const descrizioneStile = l => (LINGUA === "it" && l.descrizione) || t("formazione.stile_desc_" + codiceStile(l.rischio));

// Sul campo solo il cognome, senza l'iniziale («Rossi L.» → «Rossi»), come sull'iPhone: lo spazio è poco.
const cognome = x => String(x.nome).replace(/\s+\S{1,3}\.$/u, "");

// La formazione come testo da leggere (o da mandare nel gruppo): Leghe non permette di incollarla, si inserisce a mano.
function testoFormazione(f, m) {
  const sch = id => f.schede[String(id)];
  const riga = r => `${ruoloSigla(r)}: ${m.titolari.map(sch).filter(x => x.ruolo === r).map(x => x.nome).join(", ")}`;
  const righe = [`${t("testata.giornata", { n: f.giornata_lega || f.giornata })} · ${m.modulo}`, ...["P", "D", "C", "A"].map(riga)];
  if (m.panchina.length) righe.push(t("scambi.panchina") + ": " + m.panchina.map((id, k) => `${k + 1}) ${sch(id).nome}`).join(", "));
  return righe.join("\n");
}

async function copiaTesto(testo) {
  try { await navigator.clipboard.writeText(testo); return true; }
  catch {
    const t = document.createElement("textarea");
    t.value = testo; t.style.position = "fixed"; t.style.opacity = "0";
    document.body.appendChild(t); t.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { /* niente */ }
    t.remove();
    return ok;
  }
}

// Chi è in ballottaggio tra i titolari: i due della rosa dello stesso ruolo che gli stanno più vicini, con la differenza di punti attesi.
// `etichetta`: la scritta «In ballottaggio con» si vede solo sulla prima riga (prima si ripeteva per ogni titolare); nelle altre è per i lettori di schermo.
function alternativeVicine(x, m, f, etichetta = true) {
  if (f.iniziata || x.titolarita == null || x.titolarita === "titolare") return "";      // a formazione chiusa non si cambia più
  const dentro = new Set(m.titolari);
  const alt = Object.values(f.schede).filter(y => y.ruolo === x.ruolo && !dentro.has(y.id) && y.p_voto >= 0.2)
    .sort((a, b) => b.punti_attesi - a.punti_attesi).slice(0, 2);
  if (!alt.length) return "";
  return `<li class="alternative-li"><span class="${etichetta ? "debole piccolo" : "solo-lettori"}">${t("formazione.ballottaggio_alternative_vic")}</span>${alt.map(y => {
    const d = y.punti_attesi - x.punti_attesi;
    return `<button class="alt" data-coppia="${x.id},${y.id}">${esc(cognome(y))} <b class="${Math.abs(d) < 0.4 ? "" : d > 0 ? "positivo" : "debole"}">${segno(d, 1)}</b>${Math.abs(d) < 0.4 ? `<small>${t("formazione.quasi_pari")}</small>` : ""}</button>`;
  }).join("")}</li>`;
}

// La fascia in una riga, come sull'iPhone: «tra 62 e 84 · 8 volte su 10» (+ « (indicativo)»); senza fascia «oscilla di ±N»; senza niente, vuota.
function fraseFascia(m) {
  const i = m && m.intervallo;
  if (i && Number.isFinite(i.basso) && Number.isFinite(i.alto) && i.basso <= i.alto) {
    let frase = t("formazione.tra", { a: num(i.basso, 0), b: num(i.alto, 0) });
    const c = i.confidenza;
    if (Number.isFinite(c) && c > 0 && c < 1) {
      const base = [10, 20, 100].find(b => Math.abs(c * b - Math.round(c * b)) < 0.001);
      frase += ` · ${t("formazione.volte_su", base ? { x: Math.round(c * base), y: base } : { x: Math.round(c * 100), y: 100 })}`;
    }
    return frase + (i.indicativo ? t("formazione.indicativo") : "");
  }
  const d = m && m.dev;
  return Number.isFinite(d) && d >= 0 ? t("formazione.oscilla", { n: num(d, 0) }) : "";
}
// Dove cadranno i punti veri 8 volte su 10 (fascia calibrata sulle giornate passate); le risposte vecchie hanno solo `dev`.
function fascia(m) {
  const i = m.intervallo;
  if (!i) return `<div class="debole piccolo">${t("formazione.oscilla", { n: num(m.dev || 0, 0) })}</div>`;
  const nota = t(i.indicativo ? "formazione.fascia_nota_ind" : "formazione.fascia_nota");
  return `<div class="debole piccolo" title="${nota}">${t("formazione.tra", { a: num(i.basso, 0), b: num(i.alto, 0) })}</div>
            <div class="debole piccolo">${t(i.indicativo ? "formazione.fascia_riga_ind" : "formazione.fascia_riga")}</div>`;
}

// La ★ sta sul modulo dello stile, che con gli stili prudenti non è sempre quello col numero più alto: in quel caso lo si dice.
// (Con gli stili rischiosi la scelta punta sulla giornata eccezionale e la descrizione dello stile lo dice già.)
function stellaNonMassimo(l) {
  const stella = l.moduli.find(x => x.modulo === l.modulo);
  const top = l.moduli.reduce((a, b) => (b.punteggio_atteso > a.punteggio_atteso ? b : a), l.moduli[0]);
  if (!stella || !top || l.rischio > 0 || top.modulo === stella.modulo || Math.round(top.punteggio_atteso * 10) <= Math.round(stella.punteggio_atteso * 10)) return "";      // a schermo uguali: niente da spiegare
  return " " + t("formazione.stella_non_massimo", { modulo: esc(top.modulo), stile: esc(nomeStile(l)), consigliato: esc(l.modulo) });
}
const stessiIds = (a, b) => a.length === b.length && a.every(x => b.includes(x));
// Il perché della scelta in una riga (campo `perche_scelta` del modulo, fanta/perche_scelta.py): una riga per ogni titolare che
// sembra una scelta storta (meno punti attesi di un escluso dello stesso ruolo) o è incerto con la riserva sicura.
// [{id, nome, riga}] nell'ordine del server (riga già pronta per l'HTML); null = il server non manda il campo.
function righePercheScelta(m, scheda) {
  if (!Array.isArray(m.perche_scelta)) return null;
  return m.perche_scelta.map(x => [x, scheda(x && x.titolare)]).filter(([x, a]) => a && x.testo)
    .map(([x, a]) => ({ id: a.id, nome: a.nome, riga: esc(testoDi(x)) }));
}

// Stato della scelta della giornata, dal confronto fra gli 11 mostrati e quelli salvati sul server (l'ordine non conta).
// `salvata`: risposta di GET /api/scelta (null = nessuna scelta; undefined = non ancora letta o lettura fallita: nessuna riga).
// Risultato: null, "consigliata" (A), "salvata" (B), "modificata" (C), "mano" (D), "non_valida" (la scelta salvata non vale più)
// o "altra" (niente di salvato e sullo schermo un altro modulo o un altro stile: non è la consigliata e non si dice che lo sia).
// "chiusa": scadenza della lega passata (`iniziata` del server), niente più da salvare né da cambiare, anche prima di leggere la scelta.
function statoScelta(mostrati, salvata, manuale, nonValida = false, altra = false, chiusa = false) {
  if (chiusa) return "chiusa";
  if (salvata === undefined) return null;
  if (salvata && Array.isArray(salvata.titolari)) {
    if (nonValida && !manuale) return "non_valida";            // dopo «Modifica a mano» si può salvare la nuova (stato C)
    return stessiIds(mostrati.map(Number), salvata.titolari.map(Number)) ? "salvata" : "modificata";
  }
  return manuale ? "mano" : altra ? "altra" : "consigliata";
}
// «oggi alle 21:40» / «ieri alle 21:40» / «sab 31 alle 21:40»; con `breve` oggi resta «alle 21:40».
function quandoSalvata(s, breve = false) {
  const d = parseData(s);
  if (!d) return "";
  const inizio = x => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const diff = Math.round((inizio(d) - inizio(new Date())) / 864e5);
  const ora = fOra(d);
  if (diff === 0) return breve ? t("formazione.alle", { ora }) : t("formazione.giorno_alle", { giorno: t("tempo.oggi"), ora });
  return t("formazione.giorno_alle", { giorno: diff === -1 ? t("tempo.ieri") : `${t("tempo.giorno_" + d.getDay())} ${d.getDate()}`, ora });
}
const SEGNI_SCELTA = { consigliata: "○", altra: "○", salvata: "✓", modificata: "●", mano: "●", non_valida: "!", chiusa: "■" };
// A giornata chiusa la frase dice quale formazione vale. `nonValida`: la scelta salvata non si può schierare (regola unica del
// server: `stato_scelta: "non_valida"` di GET /api/formazione, o `formazione_non_valida` rileggendola): vale la consigliata, che è
// anche quella mostrata.
function rigaStatoScelta(st, salvata, nonValida = false) {
  const quando = salvata ? quandoSalvata(salvata.salvata) : "", breve = salvata ? quandoSalvata(salvata.salvata, true) : "";
  const testo = {
    consigliata: t("formazione.stato_consigliata"),
    altra: t("formazione.stato_altra"),
    salvata: quando ? t("formazione.stato_salvata_quando", { quando }) : t("formazione.stato_salvata"),
    modificata: breve ? t("formazione.stato_modificata_quando", { quando: breve }) : t("formazione.stato_modificata"),
    mano: t("formazione.stato_mano"),
    non_valida: t("formazione.stato_non_valida"),
    chiusa: t(nonValida ? "formazione.stato_chiusa_non_valida" : salvata ? "formazione.stato_chiusa_tua" : "formazione.stato_chiusa"),
  }[st];
  const b = (id, chiave, secondario = true) => `<button class="bottone${secondario ? " secondario" : ""}" type="button" id="${id}">${t(chiave)}</button>`;
  const pulsanti = {
    consigliata: b("salva-questa", "formazione.salva_questa", false) + b("modifica", "formazione.modifica_mano"),
    altra: b("salva-questa", "formazione.salva_questa", false) + b("modifica", "formazione.modifica_mano") + b("torna-consigliata", "formazione.torna_alla_consigliata"),
    salvata: b("torna-consigliata", "formazione.torna_alla_consigliata"),
    modificata: b("salva-scelta", "formazione.salva_modifiche", false) + b("annulla-modifiche", "formazione.annulla_modifiche") + b("torna-consigliata", "formazione.torna_alla_consigliata"),
    mano: b("salva-scelta", "formazione.salva_come_mia", false) + b("torna-consigliata", "formazione.torna_alla_consigliata"),
    non_valida: b("modifica", "formazione.modifica_mano", false) + b("torna-consigliata", "formazione.torna_alla_consigliata"),
    chiusa: "",                                           // dopo la scadenza il server rifiuta comunque (409 formazione_chiusa)
  }[st];
  return `<div class="stato-scelta ${st}" id="stato-scelta"><p role="status"><span class="segno" aria-hidden="true">${SEGNI_SCELTA[st]}</span><span>${testo}</span></p>
    ${pulsanti ? `<div class="pulsanti">${pulsanti}</div>` : ""}</div>`;
}

// Anticipi già cominciati (#373): chi gioca una partita già cominciata non si sposta più (campo `bloccati` di GET /api/formazione;
// manca senza anticipi cominciati e con un server vecchio). Il server rifiuta comunque un salvataggio che ne sposta uno.
const giocatoriFermi = f => new Set((Array.isArray(f && f.bloccati) ? f.bloccati : []).map(Number));
// Chi può prendere il posto di `base` nella modifica a mano: stesso ruolo, non già fra i titolari (`dentro`) e non fermo, il migliore
// per punti attesi in cima. Nessuno se `base` stesso è fermo.
function sostituti(f, base, dentro) {
  const fermi = giocatoriFermi(f);
  if (fermi.has(Number(base.id))) return [];
  return Object.values(f.schede).filter(x => x.ruolo === base.ruolo && !dentro.has(x.id) && !fermi.has(Number(x.id)))
    .sort((a, b) => b.punti_attesi - a.punti_attesi);
}

function mostraFormazione(f, squadra, opz = {}) {
  const scheda = id => f.schede[String(id)];
  const fermi = giocatoriFermi(f);
  const sc = stato.scelta || (stato.scelta = {});
  const chiaveSc = `${squadra || "mia"}/${f.giornata}`;
  if (sc.chiave !== chiaveSc) Object.assign(sc, { chiave: chiaveSc, livello: 0, modulo: null, manuale: null, letta: false, salvata: undefined, nonValida: false });
  if (sc.manuale && ![...sc.manuale.titolari, ...(sc.manuale.panchina || [])].every(id => f.schede[String(id)])) sc.manuale = null;      // la rosa è cambiata
  // gli 11 salvati sul server (la scelta resta «salvata» solo se gli 11 mostrati sono proprio quelli: niente segno acceso dopo una sostituzione)
  const comeSalvata = ids => !!(sc.salvata && Array.isArray(sc.salvata.titolari) && stessiIds(ids.map(Number), sc.salvata.titolari.map(Number)));
  // «Modifica a mano» aperta e lasciata senza cambiare niente né salvare: tornando qui si riparte dalla consigliata (non «la tua scelta 0,0»)
  if (sc.manuale && sc.manuale.uguale && !comeSalvata(sc.manuale.titolari)) sc.manuale = null;
  const LIVELLI = f.livelli || [{ rischio: 0, nome: "Equilibrata", modulo: f.modulo, punteggio_atteso: f.punteggio_atteso, dev: f.dev || 0, intervallo: f.intervallo, moduli: f.moduli }];
  const livello = () => LIVELLI.find(l => l.rischio === sc.livello) || LIVELLI.find(l => l.rischio === 0) || LIVELLI[0];
  const moduloAuto = () => { const l = livello(); return l.moduli.find(m => m.modulo === sc.modulo) || l.moduli.find(m => m.modulo === l.modulo) || l.moduli[0]; };
  const corrente = () => sc.manuale
    ? { modulo: sc.manuale.modulo, titolari: sc.manuale.titolari, panchina: sc.manuale.panchina, punteggio_atteso: sc.manuale.r.punteggio_atteso, dev: sc.manuale.r.dev, intervallo: sc.manuale.r.intervallo }
    : moduloAuto();

  // Titolari incerti con la riserva quasi sicura (campo `incerti` del modulo, fanta/consigli.py): solo per la proposta del server,
  // non dopo una modifica a mano né a giornata iniziata. {id del titolare: {nome, riga}} (riga già pronta per l'HTML)
  const incerti = m => {
    const r = {};
    if (sc.manuale || f.iniziata) return r;
    for (const i of (Array.isArray(m.incerti) ? m.incerti : [])) {
      const a = scheda(i && i.titolare), b = scheda(i && i.riserva);
      if (a && b) r[a.id] = { nome: a.nome, riga: t("formazione.incerto", { p: perc(a.p_voto), riserva: esc(b.nome) }) };
    }
    return r;
  };

  // Una sola valutazione alla volta; se nel frattempo scegli un modulo o uno stile, la risposta che arriva dopo si ignora.
  const valutaManuale = async (ids, salva = false, silenzioso = false) => {
    const n = sc.richiesta = (sc.richiesta || 0) + 1;
    sc.occupato = true;
    try {
      const r = await api("/api/formazione/valuta", { method: "POST", body: JSON.stringify({ titolari: ids, squadra: squadra || null, giornata: f.giornata, salva }) });
      const ancoraQui = () => n === sc.richiesta && sc.chiave === chiaveSc && document.body.contains($("#punti-attesi"));    // stessa richiesta e stessa giornata
      if (!ancoraQui()) return false;
      const disegna = sc.disegna, moduloAuto = sc.moduloAuto;         // la vista più recente (i dati nuovi arrivati nel frattempo), non la copia locale
      // uguale = gli stessi undici della scelta automatica (se non sono quelli salvati, tornando qui si riparte dalla consigliata)
      sc.manuale = { modulo: r.modulo, titolari: ids, panchina: r.panchina, r, uguale: stessiIds(ids, moduloAuto().titolari) };
      if (salva) {                                // lo stato «salvata» viene dal server: si rilegge la scelta appena scritta
        let riletta;
        try { const s = await api(`/api/scelta?giornata=${f.giornata}`); riletta = s && Array.isArray(s.titolari) ? s : { titolari: ids }; }
        catch { riletta = { titolari: ids }; }              // scritta (il server ha risposto), ma non riletta: senza l'ora
        if (!ancoraQui()) return false;                     // nel frattempo hai cambiato giornata: la scelta riletta non è di questa
        sc.salvata = riletta; sc.nonValida = false;
      }
      disegna(true);
      if (salva) avviso(t("formazione.salvata_come_tua"));
      return true;
    } catch (e) {
      if (n === sc.richiesta) {
        // la scelta salvata non vale più (rosa o regole cambiate): NON si cancella da sola, lo si dice nella riga dello stato
        const qui = sc.chiave === chiaveSc && document.body.contains($("#punti-attesi"));
        if (e.codice === "formazione_chiusa") { avviso(e.message, 5000); sc.manuale = null; sc.nonSalvata = false; if (qui) vistaFormazione(); }      // scadenza passata con la pagina aperta
        else if (silenzioso && e.codice === "formazione_non_valida") { if (sc.chiave === chiaveSc) sc.nonValida = true; if (qui) sc.disegna(true); }
        // rilettura della scelta fallita (rete): lo stato non è noto, la riga sparisce (niente falso «Modifiche non salvate») e si riprova la prossima volta
        else if (silenzioso) { if (sc.chiave === chiaveSc) { sc.salvata = undefined; sc.letta = false; } if (qui) sc.disegna(true); }
        else avviso(e.message, 5000);
      }
      return false;
    } finally { if (n === sc.richiesta) sc.occupato = false; }
  };
  const annullaRichieste = () => { sc.richiesta = (sc.richiesta || 0) + 1; sc.occupato = false; };

  const disegna = (mantieniScroll = false) => {
    const y0 = window.scrollY;
    const l = livello(), m = corrente(), manuale = !!sc.manuale;
    stato.formaz = { f, modulo: m, livello: sc.livello, manuale };      // serve al confronto: chi è titolare, in panchina o fuori in questa formazione
    const titolari = m.titolari.map(scheda), panchina = m.panchina.map(scheda);
    const scelti = new Set([...m.titolari, ...m.panchina]);
    const fuori = Object.values(f.schede).filter(x => !scelti.has(x.id)).sort((a, b) => b.punti_attesi - a.punti_attesi);
    const linee = { P: [], D: [], C: [], A: [] };
    titolari.forEach(x => linee[x.ruolo].push(x));
    const chip = l.moduli.map(x => `<button class="chip ${!manuale && x.modulo === m.modulo ? "attiva" : ""}" data-modulo="${esc(x.modulo)}">
      ${esc(x.modulo)}<span>${num(x.punteggio_atteso)}</span>${x.modulo === l.modulo ? `<i title="${t("formazione.consigliato")}">★</i>` : ""}</button>`).join("");
    const chipStile = LIVELLI.filter(x => funz("stili_ridotti") || x.rischio === l.rischio || Math.abs(x.rischio) < 2).map(x => `<button class="chip ${!manuale && x.rischio === l.rischio ? "attiva" : ""}" data-stile="${x.rischio}">
      ${esc(nomeStile(x))}<span>${num(x.punteggio_atteso)}</span>${x.rischio === 0 ? `<i title="${t("formazione.consigliata")}">★</i>` : ""}</button>`).join("");
    const r = manuale ? sc.manuale.r : null;
    const altra = !manuale && (l.rischio !== 0 || m.modulo !== l.modulo);                // un altro stile o un altro modulo: non è la consigliata
    const chiusa = !!f.iniziata;                                      // scadenza passata: niente «Modifica a mano» né «Salva»
    const st = squadra ? null : statoScelta(m.titolari, sc.salvata, manuale, sc.nonValida, altra, chiusa);     // mai per le squadre altrui
    // «Modifica a mano» cambiata e non salvata: chi lascia la pagina o la scheda lo sa prima (modificaNonSalvata)
    sc.nonSalvata = !squadra && !chiusa && manuale && (st === "modificata" || (st === "mano" && !sc.manuale.uguale));
    const modificabile = manuale && !chiusa;
    const inc = incerti(m);
    // la nota sotto il campo: il perché delle scelte che sembrano storte, solo per la proposta del server (server senza il campo: gli incerti)
    const nota = (sc.manuale || f.iniziata) ? [] : (righePercheScelta(m, scheda) ?? Object.values(inc));
    let etichettaAlt = true;                                          // «In ballottaggio con» scritto una volta sola
    const voceTit = x => {
      const h = voceGiocatore(x, null, true, modificabile && !fermi.has(x.id));      // fermo (anticipo cominciato): ⇄ al posto di ✎
      const alt = manuale ? "" : alternativeVicine(x, m, f, etichettaAlt);
      if (alt) etichettaAlt = false;
      return h + alt;
    };
    pagina(`
      ${squadra ? `<div class="attenzione">${t("formazione.stai_guardando_formazione")} <b>${esc(f.squadra)}</b>.
        <button class="bottone secondario" id="torna-mia" style="margin-left:6px;padding:4px 12px;min-height:0">${t("formazione.torna_alla_tua")}</button></div>` : ""}
      ${f.giornata_saltata ? `<div class="attenzione" id="formazione-prossima">${t("formazione.per_la_prossima", { n: f.giornata_saltata_lega || f.giornata_saltata, m: (f.giornata_saltata_lega || f.giornata_saltata) + 1 })}</div>` : ""}
      ${f.iniziata ? (st ? "" : `<div class="attenzione" id="formazione-chiusa">${t("formazione.chiusa")}</div>`) : f.con_probabili ? "" : `<div class="attenzione">${t("formazione.mancano_probabili_formazioni")}</div>`}
      <div class="colonne colonne-campo"><div class="col">
      <div class="carta hero">
        ${st ? rigaStatoScelta(st, sc.salvata, f.stato_scelta === "non_valida" || sc.nonValida) : ""}
        <div class="riga"><div><div class="debole">${t("testata.giornata", { n: f.giornata_lega || f.giornata })} · ${t(manuale ? "formazione.la_tua_scelta" : m.modulo === l.modulo && l.rischio === 0 ? "formazione.modulo_consigliato" : "formazione.modulo_scelto")}</div><div class="grande">${esc(m.modulo)}</div></div>
          <div style="text-align:right"><div class="debole">${t("formazione.punti_attesi")}</div><div class="grande" id="punti-attesi">${num(m.punteggio_atteso)}</div>
            ${fascia(m)}</div></div>
        ${manuale && r.differenza !== null ? `<div class="debole" style="margin-top:6px">${t("formazione.rispetto", { d: segno(r.differenza, 1), n: num(r.consigliata_stesso_modulo) })}</div>` : ""}
        ${chiusa ? "" : `<div class="etichetta-riga">${t("formazione.modulo")}</div>
        <div class="chips scorri" data-striscia>${chip}</div>
        <div class="etichetta-riga">${t("formazione.stile")}</div>
        <div class="chips scorri" data-striscia>${chipStile}</div>
        <div class="debole nota-riga" id="descrizione-stile">${manuale ? t("formazione.modificata_mano")
          : `<b>${esc(nomeStile(l))}</b>: ${esc(descrizioneStile(l))}${m.modulo !== l.modulo ? " " + t("formazione.modulo_fissato", { modulo: esc(l.modulo) }) : " " + t("formazione.propone", { modulo: esc(l.modulo) })}${stellaNonMassimo(l)}`}
          ${t("formazione.stella_consigliata")}</div>`}
        <div class="pulsanti">
          ${st || chiusa ? "" : manuale ? `${squadra ? "" : `<button class="bottone" id="salva-scelta">${t("formazione.salva_come_mia")}</button>`}<button class="bottone secondario" id="torna-consigliata">${t("formazione.torna_alla_consigliata")}</button>`
                    : `<button class="bottone" id="modifica">${t("formazione.modifica_mano")}</button>`}
          <details class="altre-azioni"><summary class="bottone secondario">${t("formazione.altro")}</summary>
            <div class="pulsanti"><button class="bottone secondario" id="copia">${t("formazione.copia_formazione")}</button>
              <button class="bottone secondario" id="condividi">${t("formazione.condividi_immagine")}</button></div></details>
        </div>
      </div>
      <div class="campo">${legendaCampo()}<i class="area-alta"></i><i class="cerchio"></i><i class="meta"></i>
        ${["P", "D", "C", "A"].map(rr => `<div class="linea">${linee[rr].map(pedina).join("")}</div>`).join("")}
      </div>
      ${nota.length ? `<div class="nota-incerti" id="nota-incerti">${nota.map(i => `<p><b>${esc(i.nome)}</b> · ${i.riga}</p>`).join("")}</div>` : ""}
      </div><div class="col">
      <div class="carta"><h2>${t("formazione.titolari")}</h2><div class="debole piccolo">${t(modificabile ? "formazione.tocca_sostituire" : "formazione.tocca_confronto")}</div>
        ${modificabile && fermi.size ? `<div class="debole piccolo">${t("formazione.bloccati")}</div>` : ""}
        <ul class="elenco">${titolari.map(voceTit).join("")}</ul></div>
      <div class="carta"><h2>${t("scambi.panchina")}</h2><div class="debole piccolo">${t("formazione.quest_ordine_entra")}</div>
        <ul class="elenco">${panchina.map((x, k) => voceGiocatore(x, k + 1, true)).join("")}</ul></div>
      ${fuori.length || f.senza_dati.length ? `<div class="carta"><details><summary>${t("formazione.fuori_dalla", { n: fuori.length })}</summary><ul class="elenco">${fuori.map(x => voceGiocatore(x)).join("")}</ul>
        ${f.senza_dati.length ? `<div class="debole piccolo">${t("formazione.senza_dati", { nomi: f.senza_dati.map(esc).join(", ") })}</div>` : ""}</details></div>` : ""}
      <p class="debole piccolo">${t("formazione.numero_sulla_maglia")}</p>
      </div></div>`,
      { ...opz, daCache: mantieniScroll ? null : opz.daCache, sostituisce: opz.sostituisce || mantieniScroll });
    document.querySelectorAll("[data-striscia]").forEach(striscia);
    document.querySelectorAll("[data-modulo]").forEach(b => b.addEventListener("click", () => { annullaRichieste(); sc.manuale = null; sc.modulo = b.dataset.modulo; disegna(true); }));
    document.querySelectorAll("[data-stile]").forEach(b => b.addEventListener("click", () => { annullaRichieste(); sc.manuale = null; sc.modulo = null; sc.livello = Number(b.dataset.stile); disegna(true); }));      // lo stile è un preset: torna al suo modulo
    document.querySelectorAll("[data-perche]").forEach(b => b.addEventListener("click", ev => {
      const x = scheda(b.dataset.perche);
      if (!x) return;
      ev.stopPropagation(); ev.preventDefault();          // non apre la scheda: apre «Perché questo numero»
      apriPerche(x, (inc[x.id] || {}).riga);
    }));
    document.querySelectorAll("[data-coppia]").forEach(b => b.addEventListener("click", () => { const [a, c] = b.dataset.coppia.split(",").map(Number); apriConfronto(a, c); }));
    document.querySelectorAll("[data-sostituisci]").forEach(b => b.addEventListener("click", () => apriSostituzione(Number(b.dataset.sostituisci))));
    const bottone = (id, fn) => { const e = $(id); if (e) e.addEventListener("click", fn); };
    bottone("#modifica", () => { if (!sc.occupato) valutaManuale([...m.titolari]); });
    bottone("#salva-scelta", () => { if (!sc.occupato) valutaManuale([...m.titolari], true); });
    bottone("#salva-questa", () => { if (!sc.occupato) valutaManuale([...m.titolari], true); });
    bottone("#annulla-modifiche", () => { if (!sc.occupato && sc.salvata) { annullaRichieste(); valutaManuale([...sc.salvata.titolari], false, true); } });
    bottone("#torna-consigliata", async () => {
      annullaRichieste();
      sc.manuale = null; sc.livello = 0; sc.modulo = null;            // anche stile e modulo: è la consigliata, non solo «niente a mano»
      disegna(true);
      if (squadra || sc.salvata === null) return;                       // niente di salvato da togliere
      try {
        await api(`/api/scelta?giornata=${f.giornata}`, { method: "DELETE" });
        sc.salvata = null; sc.nonValida = false;
      } catch (e) {
        avviso(e.message, 5000);
        if (e.codice === "formazione_chiusa") { if (document.body.contains($("#punti-attesi"))) vistaFormazione(); return; }     // scadenza passata: la scelta resta
      }
      if (document.body.contains($("#punti-attesi"))) disegna(true);
    });
    collegaLegenda();
    bottone("#copia", async () => avviso(await copiaTesto(testoFormazione(f, m)) ? t("formazione.copiata") : t("formazione.non_copio")));
    bottone("#condividi", () => condividiImmagine(f, m).catch(() => avviso(t("formazione.non_riesco_creare"))));
    if (mantieniScroll) window.scrollTo(0, y0);
    animaNumero($("#punti-attesi"), mantieniScroll ? stato.punteggioPrec : 0, m.punteggio_atteso);
    stato.punteggioPrec = m.punteggio_atteso;
    const torna = $("#torna-mia");
    if (torna) torna.addEventListener("click", () => { stato.squadraVista = null; vistaFormazione(); });
  };

  // Sostituisci un titolare con un altro della rosa dello stesso ruolo (il modulo non cambia): poi si ricalcola.
  function apriSostituzione(id) {
    const base = scheda(id);
    if (!base || !sc.manuale || f.iniziata) return;
    if (fermi.has(base.id)) return;                                     // gioca un anticipo già cominciato (#373): resta dov'è
    if (sc.occupato) { avviso(t("formazione.sto_ancora_ricalcolando")); return; }
    ultimaScheda++;
    const dentro = new Set(sc.manuale.titolari);
    const candidati = sostituti(f, base, dentro);
    const riga = x => `<li><button class="voce" data-entra="${x.id}">${avatarIndice(x)}
      <span><span class="nome">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span>
        <span class="etichette">${pillTitolarita(x)}<span class="etichetta neutra">${postoInFormazione(x.id) || testoPosto("fuori")}</span></span></span>
      <span class="valore"><b>${num(x.fv_atteso)}</b><span class="debole piccolo">${t("formazione.punti_da_solo", { d: segno(x.punti_attesi - base.punti_attesi, 1) })}</span></span></button></li>`;
    apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("formazione.al_posto_di", { nome: esc(base.nome) })}</h2>
      <div class="debole piccolo">${t("formazione.giocatori_dello_stesso")}</div>
      <div class="carta" style="margin-top:12px">${candidati.length ? `<ul class="elenco">${candidati.map(riga).join("")}</ul>` : `<div class="debole">${t("formazione.nessun_altro_giocatore")}</div>`}</div>`);
    document.querySelectorAll("[data-entra]").forEach(b => b.addEventListener("click", () => {
      const ids = sc.manuale.titolari.map(t => t === id ? Number(b.dataset.entra) : t);
      chiudiFoglio();
      valutaManuale(ids);
    }));
  }

  Object.assign(sc, { disegna, moduloAuto, valuta: valutaManuale });     // le risposte in arrivo usano sempre la vista più recente
  disegna(false);
  // se hai già salvato una tua scelta per questa giornata, riparte da quella; la riga dello stato compare solo dopo questa lettura
  if (!squadra && !sc.letta) {
    sc.letta = true;
    api(`/api/scelta?giornata=${f.giornata}`).then(s => {
      if (stato.scelta !== sc || sc.chiave !== chiaveSc) return;
      sc.salvata = s && Array.isArray(s.titolari) ? s : null;
      if (sc.salvata && !sc.manuale) sc.valuta(sc.salvata.titolari, false, true);
      else if (document.body.contains($("#punti-attesi"))) sc.disegna(true);
    }).catch(() => { sc.letta = false; });                               // lettura fallita: nessuna riga, si riprova la prossima volta
  }
}

// ---------------------------------------------------------------- mercato: consigliati, classifica, calendario, cerca
const TAB_MERCATO = [["consigli", "mercato.tab_consigli"], ["giocatori", "mercato.tab_giocatori"], ["osservati", "mercato.tab_osservati"], ["calendario", "mercato.tab_calendario"]];
let richiestaMercato = 0;
// Le schede di prima portano a quelle nuove: Classifica e Cerca sono diventate Giocatori (l'asta non c'è più: si va ai Consigliati).
const SCHEDE_MERCATO_VECCHIE = { classifica: "giocatori", cerca: "giocatori" };
// Le schede che restano con la dieta: Seguiti ("osservati") e l'elenco (Giocatori, Calendario) hanno il loro interruttore; i Consigliati ci sono sempre.
const FUNZIONE_TAB_MERCATO = { osservati: "seguiti", giocatori: "elenco_giocatori", calendario: "elenco_giocatori" };
const tabMercatoVisibili = () => TAB_MERCATO.filter(([k]) => !FUNZIONE_TAB_MERCATO[k] || funz(FUNZIONE_TAB_MERCATO[k]));
function schedaMercato(nome) {
  const k = SCHEDE_MERCATO_VECCHIE[nome] || nome;
  return tabMercatoVisibili().some(([n]) => n === k) ? k : "consigli";
}

function vistaMercato() {
  nuovaRichiesta();
  stato.mercatoTab = schedaMercato(stato.mercatoTab);
  const tabs = tabMercatoVisibili();
  contenuto.innerHTML = `
    <div class="segmenti" id="mercato-tab" ${tabs.length < 2 ? "hidden" : ""}>${tabs.map(([k, nome]) => `<button data-mtab="${k}" class="${k === stato.mercatoTab ? "attivo" : ""}">${t(nome)}</button>`).join("")}</div>
    <div id="mercato-corpo"></div>`;
  document.querySelectorAll("[data-mtab]").forEach(b => b.addEventListener("click", () => {
    stato.mercatoTab = b.dataset.mtab;
    document.querySelectorAll("[data-mtab]").forEach(x => x.classList.toggle("attivo", x === b));
    striscia($("#mercato-tab"));
    caricaMercato();
  }));
  striscia($("#mercato-tab"));
  caricaMercato();
}

// Striscia scorrevole di voci: porta in vista la scelta e accende il bordo sfumato dal lato dove c'è ancora altro da vedere.
function striscia(el) {
  if (!el) return;
  const agg = () => {
    el.style.setProperty("--fs", el.scrollLeft > 4 ? "22px" : "0px");
    el.style.setProperty("--fd", el.scrollLeft + el.clientWidth < el.scrollWidth - 4 ? "22px" : "0px");
  };
  const att = el.querySelector(".attivo, .attiva");
  if (att) el.scrollLeft = Math.max(0, att.offsetLeft - (el.clientWidth - att.offsetWidth) / 2);
  if (!el.dataset.striscia) {
    el.dataset.striscia = "1";
    el.addEventListener("scroll", agg, { passive: true });
    // con il tasto Tab: Chrome fa scorrere la striscia solo se la voce è tutta fuori, e una voce a metà restava mezza nascosta (issue #280)
    el.addEventListener("focusin", e => { const voce = e.target.closest("button"); if (voce && el.contains(voce)) voce.scrollIntoView({ block: "nearest", inline: "nearest" }); });
  }
  agg();
}

function caricaMercato() {
  const numero = ++richiestaMercato;
  const dove = $("#mercato-corpo");
  const ok = () => numero === richiestaMercato && document.body.contains(dove);
  if (stato.mercatoTab === "osservati") return tabOsservati(dove, ok);
  if (stato.mercatoTab === "giocatori") return tabGiocatori(dove, ok);
  if (stato.mercatoTab === "calendario") return tabCalendario(dove, ok);
  return tabConsigli(dove, ok);
}

// Osservati: i giocatori che segui, con la previsione di questa giornata. Ti avvisiamo sul telefono se cambia qualcosa.
async function tabOsservati(dove, ok) {
  dove.innerHTML = `<div class="caricamento">${t("mercato.carico_gli_osservati")}</div>`;
  try {
    const r = await api("/api/osservati");
    if (!ok()) return;
    dove.innerHTML = introCompatta(tp("mercato.n_osservati", r.giocatori.length, { n: `<b>${r.giocatori.length}</b>` }), t("mercato.osservati_spiega")) +
      (r.giocatori.length ? `<div class="carta"><ul class="elenco">${r.giocatori.map(x => x.assente
        ? `<li><button class="voce" data-giocatore="${x.id}" style="grid-template-columns:1fr auto"><span><span class="nome">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span>
            <span class="dettaglio" style="display:block">${t("mercato.non_gioca_questa")}</span></span><span class="debole piccolo">${esc(x.proprietario || t("mercato.svincolato"))}</span></button></li>`
        : voceGiocatore(x, null).replace("</li>", `<div class="debole piccolo" style="padding:0 0 10px 54px">${esc(x.proprietario || t("mercato.svincolato"))}</div></li>`)).join("")}</ul></div>`
        : `<div class="carta vuoto">${t("mercato.nessun_giocatore_osservato")}</div>`);
  } catch (e) { if (ok()) dove.innerHTML = erroreVista(e); }
}

// Card introduttiva compatta: una riga che dice l'essenziale e, dietro «Come si legge», la spiegazione lunga (chiusa di default).
const introCompatta = (riga, dettaglio) => `<div class="carta intro-c"><div class="intro-riga">${riga}</div>`
  + (dettaglio ? `<details class="come"><summary>${t("mercato.come_legge")}</summary><div class="debole">${dettaglio}</div></details>` : "") + `</div>`;

// «crediti dopo 2 · rimborso 18 · costo 34»: tre pezzi che a 390 px vanno a capo interi (il puntino resta in fondo al pezzo che lo precede).
const soldiDelCambio = p => [
  t("mercato.crediti_dopo", { dopo: `<b class="${p.fattibile ? "positivo" : "negativo"}">${p.crediti_dopo}</b>`, no: p.fattibile ? "" : t("mercato.non_bastano") }),
  t("mercato.rimborso_n", { r: p.rimborso }), t("mercato.costo_n", { c: p.entra.quotazione })]
  .map((x, i, tutti) => `<span class="nb">${x}${i < tutti.length - 1 ? " ·" : ""}</span>`).join(" ");

async function tabConsigli(dove, ok) {
  const salvata = leggiCache("mercato");
  const mostra = m => {
    dove.innerHTML = introCompatta(t("mercato.svincolati_in_lega", { n: `<b>${m.svincolati}</b>` }) + (m.crediti_residui != null ? t("mercato.crediti_riga", { n: `<b>${m.crediti_residui}</b>` }) : ""),
      t("mercato.consigli_spiega") + " " +
        (m.crediti_residui != null ? t("mercato.rimborso", { p: Math.round((m.rimborso_ipotizzato ?? 0.5) * 100) }) : t("mercato.inserisci_crediti"))) +
      // solo la tua rosa: chi non è tuo risulta libero, ma potrebbe stare in un'altra squadra
      ((stato.squadre || []).length === 1 ? `<div class="attenzione">${t("mercato.senza_altre")}</div>` : "") +
      (m.proposte.length ? `<div class="griglia-proposte">` + m.proposte.map(p => `<div class="carta proposta-r">
        ${avatarIndice(p.entra)}
        <div class="pr-testo">
          <button class="nome-g" data-giocatore="${p.entra.id}">${esc(p.entra.nome)}</button>
          <div class="pr-sec">${sigla(p.entra.squadra)} · ${t("mercato.quot", { n: p.entra.quotazione })} · ${t("mercato.al_posto_di", { nome: `<button class="nome-g piccolo" data-giocatore="${p.esce.id}">${esc(p.esce.nome)}</button>` })} (${sigla(p.esce.squadra)})</div>
          <div class="pr-sec">${tp("mercato.punti_prossime", p.giornate.length, { d: segno(p.breve) })}</div>
          ${p.crediti_dopo != null ? `<div class="pr-sec">${soldiDelCambio(p)}</div>` : ""}
        ${p.motivo ? `<div class="pr-sec">${esc(testoDi(p, "motivo"))}</div>` : ""}
        </div>
        <div class="pr-num"><b class="${p.guadagno > 0 ? "positivo" : p.guadagno < 0 ? "negativo" : ""}">${segno(p.guadagno)}</b><span>${t("mercato.punti_stagione")}</span></div></div>`).join("") + `</div>`
        : `<div class="carta vuoto">${m.crediti_residui != null ? t("mercato.nessuno_coi_crediti", { n: m.crediti_residui }) : t("mercato.nessuno_migliora")}</div>`);
  };
  if (salvata) mostra(salvata.dati); else dove.innerHTML = `<div class="caricamento">${t("mercato.cerco_gli_svincolati")}</div>`;
  try {
    const m = await api("/api/mercato");
    if (!ok()) return;
    salvaCache("mercato", m);
    if (!salvata || JSON.stringify(salvata.dati) !== JSON.stringify(m)) mostra(m);
  } catch (e) {
    if (!ok()) return;
    if (!salvata) dove.innerHTML = erroreVista(e); else avviso(e.rete ? t("mercato.non_aggiorno") : e.message);
  }
}

async function datiCalendario() {
  if (stato.calendario) return stato.calendario;
  const salvata = leggiCache("calendario");
  const fresco = api("/api/calendario").then(c => { stato.calendario = c; salvaCache("calendario", c); return c; });
  if (salvata) { fresco.catch(() => {}); return salvata.dati; }
  return fresco;
}

// Calendario: le sigle sono le intestazioni delle righe e G10, G11… quelle delle colonne; l'angolo è una cella vuota normale
// (un <th> senza testo è un'intestazione vuota per i lettori di schermo: axe `empty-table-header`, issue #265).
async function tabCalendario(dove, ok) {
  dove.innerHTML = `<div class="caricamento">${t("mercato.carico_calendario")}</div>`;
  try {
    const c = await datiCalendario();
    if (!ok()) return;
    let mie = new Set();
    try { const r = await api("/api/rosa"); mie = new Set(r.giocatori.map(g => g.squadra_slug).filter(Boolean)); } catch { /* niente evidenza */ }
    if (!ok()) return;
    dove.innerHTML = `<div class="carta"><h2>${t("mercato.calendario_difficolta")}</h2>
      <div class="debole piccolo">${tp("mercato.cal_spiega", c.giornate.length)}</div>
      <div class="scorri-tabella" role="region" tabindex="0" aria-label="${t("mercato.calendario_difficolta")}"><table class="tabella-cal"><thead><tr><td></td>${c.giornate.map(g => `<th scope="col">G${g}</th>`).join("")}</tr></thead>
      <tbody>${c.squadre.map(s => `<tr class="${mie.has(s.squadra) ? "mia" : ""}"><th scope="row">${sigla(s.squadra)}</th>${c.giornate.map(g => {
        const p = s.partite.find(x => x.giornata === g);
        return p ? `<td><span class="cella d${p.difficolta}">${vsAt(p)}</span></td>` : `<td></td>`;
      }).join("")}</tr>`).join("")}</tbody></table></div>
      <div class="legenda-cal">${t("diff.1")} ${[1, 2, 3, 4, 5].map(d => `<i class="d${d}"></i>`).join("")} ${t("diff.4")}</div></div>`;
  } catch (e) { if (ok()) dove.innerHTML = erroreVista(e); }
}

// Ricerca dei giocatori: l'elenco (circa 600 righe) si scarica una volta e si filtra sul dispositivo, così ogni tasto risponde subito
// anche con il server lontano o lento. Se l'elenco non arriva si torna alla ricerca sul server (una richiesta per volta: la vecchia si annulla).
const LETTERE_SPECIALI = { "ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th", "ı": "i", "œ": "oe" };
const normNome = s => String(s).replace(/[øØæÆßłŁđĐðþıœ]/g, c => LETTERE_SPECIALI[c]).normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
  .toLowerCase().replace(/['’`]/g, "").replace(/[^a-z0-9]+/g, " ").trim();                // stessa regola di nomi.normalizza (server)
let listoneCerca = null, listoneQuando = 0, listonePromessa = null, abortoCerca = null;
function caricaListoneCerca() {
  if (listoneCerca && Date.now() - listoneQuando < 600000) return Promise.resolve(listoneCerca);
  if (!listonePromessa) {
    // `nome_completo` (facoltativo): si cerca anche per nome proprio, «Lautaro» trova «Martinez L.»
    listonePromessa = api("/api/giocatori?tutti=1").then(l => { listoneCerca = l.map(x => ({ ...x, n: normNome(x.nome), nc: x.nome_completo ? normNome(x.nome_completo) : "" })); listoneQuando = Date.now(); return listoneCerca; })
      .finally(() => { listonePromessa = null; });
  }
  return listonePromessa;
}
async function cercaGiocatori(q, limite) {
  const n = normNome(q);
  if (!n) return [];
  if (listoneCerca && Date.now() - listoneQuando < 600000) return filtraListone(n, limite);
  try { return filtraListone(n, limite, await caricaListoneCerca()); }
  catch { /* elenco non disponibile: ricerca sul server */ }
  if (abortoCerca) abortoCerca.abort();
  abortoCerca = new AbortController();
  return api(`/api/giocatori?q=${encodeURIComponent(q)}&limite=${limite}`, { signal: abortoCerca.signal });
}
function filtraListone(n, limite, lista = listoneCerca) {
  const trovati = lista.filter(x => x.n.includes(n) || (x.nc && x.nc.includes(n)));
  const inizia = x => (x.n.startsWith(n) || (x.nc && x.nc.startsWith(n)) ? 0 : 1);
  trovati.sort((a, b) => inizia(a) - inizia(b) || b.quotazione - a.quotazione);
  return trovati.slice(0, limite).map(({ n: _n, nc: _nc, ...x }) => x);
}

// Giocatori: un solo elenco per cercare, filtrare per ruolo e vedere chi è libero. La classifica larga (tutti quelli che giocano, fino a 800 righe) si scarica una
// volta e si filtra sul dispositivo; la ricerca per nome parte dall'elenco completo, già presente, e si arricchisce appena arriva la classifica.
const datiGiocatori = {};
function classificaLarga(liberi) {
  const k = liberi ? "liberi" : "tutti", d = datiGiocatori[k];
  if (d && d.righe && Date.now() - d.t < 300000) return Promise.resolve(d.righe);
  if (d && d.promessa) return d.promessa;
  const promessa = api(`/api/classifica?liberi=${liberi ? "true" : "false"}&limite=800`)
    .then(r => { datiGiocatori[k] = { t: Date.now(), righe: r.giocatori }; return r.giocatori; })
    .catch(e => { delete datiGiocatori[k]; throw e; });
  datiGiocatori[k] = { ...(d || {}), promessa };
  return promessa;
}
const siglaQualunque = s => SIGLE[s] ? sigla(s) : SIGLE[normNome(s)] ? sigla(normNome(s)) : sigla(s);

function rigaGiocatoreCompatta(x) {
  const proprietario = x.proprietario === undefined ? "" : x.proprietario ? ` · ${esc(x.proprietario)}` : t("mercato.svincolato_riga");
  const atteso = x.fv_atteso != null
    ? `<b>${num(x.fv_atteso)}</b><span class="debole piccolo">${t("giocatore.gioca", { p: perc(x.p_voto) })}</span>`
    : `<b class="debole">–</b><span class="debole piccolo">${x.in_classifica === false ? t("mercato.non_gioca") : "&nbsp;"}</span>`;
  return `<li><button class="voce riga-g" data-giocatore="${x.id}">${avatarIndice(x)}
    <span><span class="nome">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span>
      <span class="dettaglio" style="display:block">${siglaQualunque(x.squadra)} · ${t("mercato.quot", { n: x.quotazione ?? "–" })}${proprietario}</span></span>
    <span class="valore">${atteso}</span></button></li>`;
}

function tabGiocatori(dove, ok) {
  const ruoli = [["", t("mercato.tutti"), t("mercato.tutti_ruoli")], ["P", ruoloSigla("P"), NOMI_RUOLO.P], ["D", ruoloSigla("D"), NOMI_RUOLO.D], ["C", ruoloSigla("C"), NOMI_RUOLO.C], ["A", ruoloSigla("A"), NOMI_RUOLO.A]];
  dove.innerHTML = `<div class="giocatori-pagina">
    <div class="carta filtri-giocatori">
      <input class="campo-testo" id="cerca" type="search" placeholder="${t("mercato.cerca_giocatore_lautaro")}" autocomplete="off" autocapitalize="off" aria-label="${t("shell.cerca")}">
      <div class="chips filtri" role="group" aria-label="${t("mercato.ruolo")}">${ruoli.map(([r, n, lungo]) => `<button class="chip ${r === stato.ruoloGiocatori ? "attiva" : ""}" data-ruolo="${r}" aria-pressed="${r === stato.ruoloGiocatori}" aria-label="${lungo}" title="${lungo}">${n}</button>`).join("")}</div>
      <label class="interruttore"><span>${t("mercato.solo_svincolati")}</span><input type="checkbox" id="solo-liberi" ${stato.soloLiberi ? "checked" : ""}></label>
      ${stato.confronto ? `<div class="attenzione" style="margin-top:12px">${t("mercato.scegli_giocatore_confrontare")} <b>${esc(stato.confronto.nome)}</b>
        <button class="bottone secondario" id="annulla-confronto" style="padding:4px 12px;min-height:44px;margin-left:6px">${t("mercato.annulla")}</button></div>` : ""}
    </div>
    <div class="carta"><div class="intestazione-elenco"><span>${t("mercato.giocatori")}</span><span>${t("mercato.voto_atteso")}</span></div><ul class="elenco" id="risultati"><li class="caricamento">${t("comune.carico")}</li></ul></div></div>`;
  const campo = $("#cerca"), lista = $("#risultati");
  let righe = null, errore_ = null;
  const disegna = async () => {
    const q = normNome(campo.value), ruolo = stato.ruoloGiocatori;
    let elenco;
    if (q.length >= 2) {
      let base;
      try { base = listoneCerca && Date.now() - listoneQuando < 600000 ? listoneCerca : await caricaListoneCerca(); } catch { base = null; }
      if (!ok() || !document.body.contains(lista)) return;
      if (base) {
        const perId = new Map((righe || []).map(x => [x.id, x]));
        elenco = filtraListone(q, 600, base).filter(x => !ruolo || x.ruolo === ruolo)
          .map(x => perId.has(x.id) ? { ...x, ...perId.get(x.id), squadra: perId.get(x.id).squadra } : (righe ? { ...x, in_classifica: false } : x));
        if (stato.soloLiberi && righe) elenco = elenco.filter(x => x.proprietario === null);
      } else elenco = (righe || []).filter(x => normNome(x.nome).includes(q) && (!ruolo || x.ruolo === ruolo));
    } else {
      if (!righe) { lista.innerHTML = errore_ ? `<li>${errore(errore_)}</li>` : `<li class="caricamento">${t("comune.carico")}</li>`; return; }
      elenco = righe.filter(x => !ruolo || x.ruolo === ruolo);
    }
    elenco = elenco.slice(0, 40);
    lista.innerHTML = elenco.length ? elenco.map(rigaGiocatoreCompatta).join("") : `<li class="vuoto">${t("mercato.nessun_giocatore_trovato")}</li>`;
  };
  const carica = () => {
    righe = null; errore_ = null;
    disegna();
    classificaLarga(!!stato.soloLiberi).then(r => { righe = r; })
      .catch(e => { errore_ = e; })
      .finally(() => { if (ok() && document.body.contains(lista)) disegna(); });
  };
  campo.addEventListener("input", disegna);
  dove.querySelectorAll("[data-ruolo]").forEach(b => b.addEventListener("click", () => {
    stato.ruoloGiocatori = b.dataset.ruolo;
    dove.querySelectorAll("[data-ruolo]").forEach(x => { x.classList.toggle("attiva", x === b); x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    disegna();
  }));
  $("#solo-liberi").addEventListener("change", ev => { stato.soloLiberi = ev.target.checked; carica(); });
  const ann = $("#annulla-confronto");
  if (ann) ann.addEventListener("click", () => { stato.confronto = null; caricaMercato(); });
  setTimeout(() => caricaListoneCerca().catch(() => {}), 250);              // l'elenco per la ricerca si prepara subito, senza rallentare l'apertura
  carica();
  if (stato.confronto) campo.focus({ preventScroll: true });
}

// ---------------------------------------------------------------- scheda giocatore (pannello) e confronto
function formaGiocatore(voti) {
  const ultimi = voti.slice(-5);
  if (!ultimi.length) return null;
  const colore = v => v == null ? "sv" : v >= 7 ? "alto" : v >= 6 ? "medio" : "basso";
  const pallini = `<div class="pallini">${ultimi.map(v => `<i class="${colore(v.fv)}" title="${t("mercato.g_n", { n: v.giornata })}">${v.fv == null ? t("mercato.sv") : num(v.fv, 1)}</i>`).join("")}</div>`;
  const con = voti.filter(v => v.fv != null);
  if (con.length < 4) return { pallini, freccia: "→", testo: t("mercato.pochi_dati"), classe: "" };
  const media = a => a.reduce((x, v) => x + v.fv, 0) / a.length;
  const differenza = media(con.slice(-3)) - media(con);
  if (differenza > 0.6) return { pallini, freccia: "↗", testo: t("mercato.in_crescita"), classe: "positivo" };
  if (differenza < -0.6) return { pallini, freccia: "↘", testo: t("mercato.in_calo"), classe: "negativo" };
  return { pallini, freccia: "→", testo: t("mercato.stabile"), classe: "" };
}

// Grafico a linee: fantavoto (verde) e voto (azzurro) giornata per giornata; "sv" dove non ha preso voto.
function graficoVoti(voti, giornate) {
  if (!voti.length) return "";
  const L = 320, A = 120, m = 18;
  const g0 = Math.max(1, Math.min(...voti.map(v => v.giornata))), g1 = Math.max(giornate || 0, ...voti.map(v => v.giornata));
  const valori = voti.flatMap(v => [v.fv, v.voto]).filter(x => x != null);
  const basso = Math.floor(Math.min(4, ...valori)), alto = Math.ceil(Math.max(8, ...valori));
  const x = g => m + (g1 === g0 ? (L - 2 * m) / 2 : (g - g0) / (g1 - g0) * (L - 2 * m));
  const y = v => A - m - (v - basso) / (alto - basso) * (A - 2 * m);
  const linea = (chiave, cl) => {
    const punti = voti.filter(v => v[chiave] != null);
    return `<polyline class="${cl}" pathLength="1" fill="none" points="${punti.map(v => `${x(v.giornata).toFixed(1)},${y(v[chiave]).toFixed(1)}`).join(" ")}"/>` +
      punti.map(v => `<circle class="${cl}" r="3" cx="${x(v.giornata).toFixed(1)}" cy="${y(v[chiave]).toFixed(1)}"><title>G${v.giornata}: ${num(v[chiave])}</title></circle>`).join("");
  };
  const sv = voti.filter(v => v.voto == null).map(v => `<text class="sv" x="${x(v.giornata).toFixed(1)}" y="${A - m - 8}" text-anchor="middle">${t("mercato.sv")}</text>`).join("");
  const passo = Math.ceil(voti.length / 12);
  const assi = voti.filter((v, k) => k % passo === 0 || k === voti.length - 1).map(v => `<text class="asse" x="${x(v.giornata).toFixed(1)}" y="${A - 2}" text-anchor="middle">${v.giornata}</text>`).join("");
  return `<h3>${t("mercato.voto_fantavoto_per")}</h3>
    <svg class="grafico" viewBox="0 0 ${L} ${A}" role="img" aria-label="${t("mercato.voti_giornata_per")}">
      <line class="rif" x1="${m}" x2="${L - m}" y1="${y(6).toFixed(1)}" y2="${y(6).toFixed(1)}"/>${linea("fv", "fv")}${linea("voto", "voto")}${sv}${assi}</svg>
    <div class="debole piccolo"><span class="legenda fv"></span>${t("mercato.fantavoto")} <span class="legenda voto"></span>${t("mercato.voto_linea_tratteggiata")}</div>`;
}

// «Perché questo numero»: i motivi principali del fantavoto atteso, come li manda il server (fanta/perche.py). L'effetto è in fantavoti
// rispetto a un giocatore medio del suo ruolo; «gioca N%» non ha effetto (il numero è «se gioca») e si vede con un punto esclamativo.
function bloccoPerche(x) {
  if (!Array.isArray(x.perche_numero)) return "";                  // server più vecchio: niente riquadro
  const medio = x.fv_atteso_medio_ruolo;
  if (!x.perche_numero.length && medio == null) return "";
  const effetto = e => e == null ? `<b class="perche-effetto dubbio" aria-hidden="true">!</b>`
    : `<b class="perche-effetto ${e > 0 ? "su" : "giu"}">${e > 0 ? "+" : "−"}${num(Math.abs(e))}</b>`;
  const righe = x.perche_numero.map(m => `<li class="perche-voce">${effetto(m.effetto)}<span>${esc(testoDi(m))}</span></li>`).join("");
  return `<div class="perche"><h3>${t("perche.titolo")}</h3>${righe ? `<ul class="perche-lista">${righe}</ul>` : ""}
    <div class="debole piccolo">${t(righe ? "perche.rispetto" : "perche.nessuno", { n: num(medio) })}</div></div>`;
}
const cartaPerche = x => { const b = bloccoPerche(x); return b ? `<div class="carta">${b}<div class="debole piccolo perche-definizione">${t("perche.definizione")}</div></div>` : ""; };
// Dalla Formazione: il tocco sul numero mostra subito il perché, con i dati già caricati (niente attesa); un tasto porta alla scheda intera.
// `incerto` (facoltativo, già pronto per l'HTML): perché è titolare anche se gioca poco (campo `incerti` del modulo).
function apriPerche(x, incerto = "") {
  apriFoglio(`<div class="intestazione-scheda">${avatarIndice(x, true)}
      <div><h2>${esc(x.nome)}</h2><div class="debole">${partitaBreve(x)}</div></div></div>
    <div class="carta"><div class="riga"><div><div class="debole">${t("mercato.fantavoto_atteso")}</div><div class="grande">${num(x.fv_atteso)}</div></div>
      <div style="text-align:right"><div class="debole">${t("mercato.gioca")}</div><div class="grande">${perc(x.p_voto)}</div></div></div>
      ${incerto ? `<p class="nota-incerto" id="perche-incerto">${incerto}</p>` : ""}
      ${bloccoPerche(x)}<div class="debole piccolo perche-definizione">${t("perche.definizione")}</div></div>
    <div class="pulsanti"><button class="bottone secondario" data-giocatore="${Number(x.id)}">${t("perche.apri_scheda")}</button></div>`);
}

let ultimaScheda = 0;
async function apriGiocatore(id) {
  if (stato.confronto && stato.confronto.id !== id) {
    const primo = stato.confronto;
    stato.confronto = null;
    if (stato.vista === "mercato" && stato.mercatoTab === "giocatori") caricaMercato();
    return apriConfronto(primo.id, id);
  }
  apriFoglio(`<div class="caricamento">${t("mercato.carico_scheda")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const [s, cal] = await Promise.all([api(`/api/giocatore/${id}`), datiCalendario().catch(() => null)]);
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const osservato = (await osservatiIds()).includes(s.calciatore.id);
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const c = s.calciatore, st = s.stagione, av = s.avanzate, pr = s.previsione;
    const forma = formaGiocatore(s.voti || []);
    const grafico = graficoVoti(s.voti || [], st.giornate_giocate_serie_a);
    const prossime = cal && pr ? (cal.squadre.find(x => x.squadra === pr.squadra) || { partite: [] }).partite : [];
    const nonGioca = !!pr && pr.titolarita === "fuori";          // infortunato o squalificato: niente partita, gol o cartellini
    // Partita iniziata o finita (giornata cominciata): le probabilità di prima non servono più. In corso resta il fantavoto atteso,
    // a partita finita solo com'è andata (il fantavoto preso, «Senza voto» o «Voto in arrivo»).
    const iniziataP = !!pr && PARTITA_INIZIATA.includes(pr.stato_partita), finitaP = !!pr && PARTITA_FINITA.includes(pr.stato_partita);
    const votoGiornata = finitaP && pr.stato_partita === "fatto" ? (s.voti || []).find(v => v.giornata === pr.giornata) : null;
    const statoInGrande = finitaP && !(votoGiornata && votoGiornata.fv != null);     // lo stato è già scritto in grande: niente pillola uguale in testa
    const prSenzaGioca = pr && iniziataP && Array.isArray(pr.perche_numero) ? { ...pr, perche_numero: pr.perche_numero.filter(m => m.chiave !== "gioca") } : pr;
    const tile = (valore, etichetta) => `<div><b>${valore}</b><span>${etichetta}</span></div>`;
    const probabilita = !pr ? "" : c.ruolo === "P"
      ? tile(perc(pr.porta_inviolata), t("mercato.porta_inviolata")) + tile(num(pr.gol_avversario, 1), t("mercato.gol_subiti_attesi")) + tile(perc(pr.p_giallo), t("mercato.giallo"))
      : tile(perc(pr.p_gol), t("mercato.segna")) + tile(perc(pr.p_assist), t("mercato.assist")) + tile(perc(pr.p_giallo), t("mercato.giallo")) + tile(perc(pr.p_rosso), t("mercato.rosso"));
    apriFoglio(`
      <div class="intestazione-scheda">
        ${avatarIndice({ id: c.id, nome: c.nome, squadra: c.squadra_slug, ruolo: c.ruolo, indice: pr ? pr.indice : null }, true)}
        <div><h2>${esc(c.nome)}</h2>
          <div class="debole">${NOME_RUOLO_1[c.ruolo] || c.ruolo} · ${esc(c.squadra)} · ${t("mercato.quot", { n: c.quotazione })}</div>
          <div class="etichette"><span class="etichetta ${s.proprietario ? "" : "arancio"}">${s.proprietario ? esc(s.proprietario) : t("mercato.svincolato")}</span>${pr && !statoInGrande ? pillTitolarita(pr) : ""}${pr && pr.diffidato ? `<span class="etichetta arancio">${t("oggi.diffidato_tipo")}</span>` : ""}</div></div>
      </div>
      ${pr ? `<div class="carta">
        <div class="riga"><div><div class="debole">${t(pr.in_casa ? "mercato.partita_casa" : "mercato.partita_fuori", { n: pr.giornata_lega || pr.giornata, avv: `<span style="text-transform:capitalize">${esc(pr.avversario)}</span>`, quando: quando(pr.data_partita) })}</div>
          ${finitaP ? (votoGiornata && votoGiornata.fv != null
            ? `<div class="grande">${num(votoGiornata.fv)} <span class="debole" style="font-size:var(--t-corpo);font-weight:400">${t("mercato.fantavoto")}</span></div>`
            : `<div class="grande stato-partita">${etichettaPronta(pr) ? esc(pr.etichetta.testo) : t(STATO_PARTITA[pr.stato_partita][0])}</div>`)
          : `<div class="grande">${num(pr.fv_atteso)} <span class="debole" style="font-size:var(--t-corpo);font-weight:400">${t("mercato.fantavoto_atteso")}</span></div>`}</div>
          ${iniziataP ? "" : `<div style="text-align:right"><div class="debole">${t("mercato.gioca")}</div><div class="grande">${perc(pr.p_voto)}</div></div>`}</div>
        ${nonGioca || iniziataP ? "" : `<div class="riga" style="margin-top:8px"><span>${diffPill(pr.difficolta)}</span><span class="debole piccolo">${t("mercato.gol_attesi", { a: num(pr.gol_squadra, 1), b: num(pr.gol_avversario, 1) })}</span></div>`}
        ${!finitaP && motiviUtili(pr).filter(senzaPercentuale).length ? `<div class="etichette">${motiviUtili(pr).filter(senzaPercentuale).map(m => `<span class="etichetta neutra">${testoEtichetta(traduciFrase(m.frase, m.testo))}</span>`).join("")}</div>` : ""}
        ${nonGioca || iniziataP ? "" : `<div class="stat-fila ${c.ruolo === "P" ? "" : "quattro"}" style="margin-top:12px">${probabilita}</div>`}</div>${finitaP ? "" : cartaPerche(prSenzaGioca)}` : `<div class="attenzione">${t("mercato.nessuna_previsione_per")}</div>`}
      ${prossime.length ? `<div class="carta"><h2>${t("mercato.prossime_partite")}</h2><div class="prossime">${prossime.map(p => `<span class="cella d${p.difficolta}">${vsAt(p)}</span>`).join("")}</div>
        <div class="debole piccolo" style="margin-top:8px">${t("mercato.colori_verde_partita")}</div></div>` : ""}
      <div class="carta"><h2>${t("mercato.forma")}</h2>
        ${forma ? `<div class="riga"><div>${forma.pallini}</div><div style="text-align:right"><div class="debole piccolo">${t("mercato.andamento")}</div><b class="${forma.classe}">${forma.freccia} ${forma.testo}</b></div></div>` : `<div class="debole">${t("mercato.nessuna_presenza_questa")}</div>`}
        ${grafico}</div>
      ${s.rendimento ? `<div class="carta"><h2>${t("mercato.rende_sopra_sotto")}</h2>
        <div class="grande ${s.rendimento.sovra_rendimento > 0.3 ? "positivo" : s.rendimento.sovra_rendimento < -0.3 ? "negativo" : ""}">${segno(s.rendimento.sovra_rendimento, 2)} <span class="debole" style="font-size:var(--t-corpo);font-weight:400">${t("mercato.punti_partita")}</span></div>
        <div class="debole piccolo">${t("mercato.rendimento_riga", { g: segno(s.rendimento.gol_meno_xg), a: segno(s.rendimento.assist_meno_xa) })}
          ${t(s.rendimento.sovra_rendimento > 0.3 ? "mercato.rend_cala" : s.rendimento.sovra_rendimento < -0.3 ? "mercato.rend_sblocca" : "mercato.rend_linea")}</div></div>` : ""}
      <div class="carta"><details><summary>${t("mercato.tutte_statistiche")}</summary>
        <h3>${t("mercato.stagione")}</h3><div class="statistiche">
          ${tile(`${st.presenze}/${st.giornate_giocate_serie_a}`, t("mercato.presenze"))}${tile(num(st.media_voto, 2), t("mercato.media_voto"))}${tile(num(st.fantamedia, 2), t("mercato.fantamedia"))}
          ${tile(st.gol + st.rig_segnati, t("mercato.gol_rig", { n: st.rig_segnati }))}${tile(st.assist, tp("mercato.n_assist", st.assist))}${tile(`${st.ammonizioni}/${st.espulsioni}`, t("mercato.gialli_rossi"))}
          ${c.ruolo === "P" ? tile(st.gol_subiti, t("mercato.gol_subiti")) + tile(st.rig_parati, t("mercato.rigori_parati")) : ""}</div>
        ${av && av.minuti ? `<h3>${t("mercato.statistiche_avanzate")}</h3><div class="statistiche">
          ${tile(num(av.xg, 2), t("mercato.gol_attesi_tot"))}${tile(num(av.xa, 2), t("mercato.assist_attesi_tot"))}${tile(`${av.minuti}'`, t("mercato.minuti"))}
          ${tile(num(av.per_90?.xg, 2), t("mercato.xg_90"))}${tile(num(av.per_90?.xa, 2), t("mercato.xa_90"))}${tile(num(av.per_90?.tiri, 1), t("mercato.tiri_90"))}
          ${tile(av.rigori_calciati, t("mercato.rigori_calciati"))}${tile(av.passaggi_chiave, t("mercato.passaggi_chiave"))}${tile(av.punizioni, t("mercato.punizioni"))}</div>
          ${(av.stagioni_precedenti || []).map(p => `<div class="debole piccolo" style="margin-top:8px">${t("mercato.stagione_prec", { s: esc(p.stagione), m: p.minuti, g: p.gol, xg: num(p.xg), a: p.assist, xa: num(p.xa) })}</div>`).join("")}` : ""}
      </details></div>
      <div class="pulsanti">${funz("seguiti") ? `<button class="bottone secondario" id="osserva">${t(osservato ? "mercato.osservato" : "mercato.osserva")}</button>` : ""}${funz("confronto") && funz("elenco_giocatori") ? `<button class="bottone" id="confronta">${t("mercato.confronta_con_altro")}</button>` : ""}
        ${funz("confronto") && stato.formaz && stato.formaz.f.schede[String(c.id)] ? `<button class="bottone secondario" data-confronta="${c.id}">${t("mercato.confronta_con_mia")}</button>` : ""}</div>`);
    if ($("#osserva")) $("#osserva").addEventListener("click", async () => {
      const b = $("#osserva"), era = b.textContent.startsWith("★");
      try {
        const r = await api(`/api/osservati/${c.id}`, { method: era ? "DELETE" : "PUT" });
        stato.osservati = r.osservati;
        b.textContent = t(era ? "mercato.osserva" : "mercato.osservato");
        avviso(t(era ? "mercato.non_osservi" : "mercato.osservi_avviso"));
      } catch (e) { avviso(e.message); }
    });
    if ($("#confronta")) $("#confronta").addEventListener("click", () => {
      stato.confronto = { id: c.id, nome: c.nome };
      stato.mercatoTab = "giocatori";
      chiudiFoglio();
      vai("mercato");
    });
  } catch (e) {
    if (numero === ultimaScheda && !$("#foglio").hidden) apriFoglio(errore(e));
  }
}

async function osservatiIds() {
  if (!stato.osservati) { try { stato.osservati = (await api("/api/osservati")).giocatori.map(x => x.id); } catch { stato.osservati = []; } }
  return stato.osservati;
}

// Il posto in formazione a parole: «Titolare», «Panchina 2», «Non schierato» (codici `titolare`, `panchina N`, `fuori`: quelli di
// `posto_a`/`posto_b` del confronto). Parole proprie, mai quelle della titolarità («Probabile titolare», «Fuori»): un giocatore al 2%
// può essere titolare nella tua formazione e «Improbabile» per le probabili (#281). Come `posto` dell'iPhone (ConfrontoViewModel).
const testoPosto = p => {
  const c = String(p || "");
  return c === "titolare" ? t("mercato.posto_titolare") : c.startsWith("panchina ") ? t("mercato.panchina_n", { n: Number(c.split(" ")[1]) })
    : c === "fuori" ? t("mercato.posto_fuori") : "";
};
// Dove sta un giocatore nella formazione che stai guardando.
function postoInFormazione(id) {
  const m = stato.formaz && stato.formaz.modulo;
  if (!m) return "";
  const k = m.panchina.indexOf(id);
  return testoPosto(m.titolari.includes(id) ? "titolare" : k >= 0 ? `panchina ${k + 1}` : stato.formaz.f.schede[String(id)] ? "fuori" : "");
}
const inTitolari = id => !!(stato.formaz && stato.formaz.modulo && stato.formaz.modulo.titolari.includes(id));

// Scelta dell'altro giocatore della rosa con cui confrontare: stesso ruolo per primo.
function apriScelta(id) {
  if (!stato.formaz) { avviso(t("mercato.apri_prima_formazione")); return; }
  const f = stato.formaz.f, base = f.schede[String(id)];
  if (!base) { avviso(t("mercato.questo_giocatore_non")); return; }
  ultimaScheda++;     // una scheda ancora in caricamento non deve sovrascrivere questa lista
  const altri = Object.values(f.schede).filter(x => x.id !== id)
    .sort((a, b) => (a.ruolo === base.ruolo ? 0 : 1) - (b.ruolo === base.ruolo ? 0 : 1) || b.punti_attesi - a.punti_attesi);
  const riga = x => `<li><button class="voce" data-scegli-confronto="${x.id}">${avatarIndice(x)}
    <span><span class="nome">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span>
      <span class="etichette">${pillTitolarita(x)}<span class="etichetta ${inTitolari(x.id) ? "" : "neutra"}">${postoInFormazione(x.id)}</span></span></span>
    <span class="valore"><b>${num(x.fv_atteso)}</b><span class="debole piccolo">${t("giocatore.gioca", { p: perc(x.p_voto) })}</span></span></button></li>`;
  apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("mercato.confronta_nome", { nome: esc(base.nome) })}</h2>
    <div class="debole piccolo">${t("mercato.con_chi_vuoi")}</div>
    <div class="carta" style="margin-top:12px"><ul class="elenco">${altri.map(riga).join("")}</ul></div>`);
  document.querySelectorAll("[data-scegli-confronto]").forEach(b => b.addEventListener("click", () => apriConfronto(id, Number(b.dataset.scegliConfronto))));
}

async function apriConfronto(a, b) {
  apriFoglio(`<div class="caricamento">${t("mercato.confronto")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const contesto = stato.formaz ? `&giornata=${Number(stato.formaz.f.giornata)}&livello=${stato.formaz.livello || 0}&modulo=${encodeURIComponent(stato.formaz.modulo.modulo)}${stato.squadraVista ? `&squadra=${encodeURIComponent(stato.squadraVista)}` : ""}` : "";
    const c = await api(`/api/confronto?a=${a}&b=${b}${contesto}`);
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const [x, y] = c.giocatori;
    const nomeCorto = g => g.nome.replace(/(\s+\p{L}{1,2}\.)+$/u, "").trim() || g.nome;
    const fo = c.formazione;
    // il posto nella formazione del sistema, dalla risposta del server (la stessa del titolo «Schiera X»), non dalla scheda Formazione
    const codicePosto = g => (!fo ? "" : g.id === x.id ? fo.posto_a : fo.posto_b) || "";
    const posto = g => testoPosto(codicePosto(g));
    const schierato = fo ? (fo.posto_a === "titolare" && fo.posto_b !== "titolare" ? x : fo.posto_b === "titolare" && fo.posto_a !== "titolare" ? y : null) : null;
    const vince = c.giocatori.find(g => g.id === c.consigliato);
    const intest = g => `<div class="duello-giocatore ${g.id === c.consigliato ? "scelto" : ""}">${avatarIndice(g, true)}
      <b class="nome">${esc(g.nome)}</b><span class="debole piccolo">${partitaRiga(g)}</span>
      ${posto(g) ? `<span class="etichetta ${codicePosto(g) === "titolare" ? "" : "neutra"}">${posto(g)}</span>` : ""}</div>`;
    const massimo = Math.max(0.3, ...c.fattori.map(f => Math.abs(f.effetto)));
    const valore = (f, v) => f.percentuale ? perc(v) : numMeno(v, 2);
    const fattori = c.fattori.filter(f => Math.abs(f.effetto) >= 0.005 || f.chiave === "giocare").map(f => {
      const larghezza = Math.min(100, Math.abs(f.effetto) / massimo * 100);
      const verso = f.effetto > 0.02 ? "sx" : f.effetto < -0.02 ? "dx" : "";
      return `<div class="fattore"><div class="riga"><span class="debole piccolo">${esc(etichettaFattore(f))}</span><b class="${verso ? "positivo" : "debole"}">${verso ? `${esc(nomeCorto(f.effetto > 0 ? x : y))} +${num(Math.abs(f.effetto), 2)}` : t("mercato.pari")}</b></div>
        <div class="barra-div"><i class="${verso}" style="width:${larghezza / 2}%"></i></div>
        <div class="riga piccolo debole"><span>${esc(x.nome.split(" ")[0])} ${valore(f, f.a)}</span><span>${valore(f, f.b)} ${esc(y.nome.split(" ")[0])}</span></div></div>`;
    }).join("");
    const riga = (etichetta, f) => `<div class="debole">${etichetta}</div><div class="numero"><b>${f(x)}</b></div><div class="numero"><b>${f(y)}</b></div>`;
    apriFoglio(`
      <h2 style="margin:0 0 10px;font-size:var(--t-card)">${t("mercato.chi_schierare", { n: c.giornata_lega ?? c.giornata })}</h2>
      <div class="duello">${intest(x)}<span class="vs-duello">VS</span>${intest(y)}</div>
      <div class="carta hero"><div class="debole">${fo ? t("mercato.nella_formazione", { modulo: esc(fo.modulo) }) : t("mercato.il_sistema_sceglie")}</div>
        <div class="grande">${schierato ? t("mercato.schiera", { nome: esc(schierato.nome) }) : esc(vince.nome)}</div>
        <div class="debole" style="margin-top:6px">${esc(fo ? testoDi(fo) : testoDi(c, "perche"))}</div></div>
      <div class="carta"><h2>${t(fo ? "mercato.se_giocassero" : "mercato.cosa_pesa")}</h2>
        <div class="debole piccolo">${fo ? `${esc(testoDi(c, "perche"))} ` : ""}${t("mercato.barra_spiega", { x: esc(nomeCorto(x)), y: esc(nomeCorto(y)), d: segno(x.punti_attesi - y.punti_attesi, 2) })}</div>
        <div class="fattori">${fattori}</div></div>
      <div class="carta"><details><summary>${t("mercato.tutti_numeri")}</summary><div style="display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:10px;align-items:center;margin-top:8px">
        <div></div><div><b>${esc(x.nome)}</b></div><div><b>${esc(y.nome)}</b></div>
        ${riga(t("mercato.indice"), g => g.indice)}
        ${riga(t("mercato.avversario"), g => vsAt(g))}
        ${riga(t("mercato.partita"), g => diffPill(g.difficolta))}
        ${riga(t("mercato.gioca_riga"), g => perc(g.p_voto))}
        ${riga(t("mercato.fantavoto_atteso_riga"), g => num(g.fv_atteso))}
        ${riga(t("mercato.atteso_ponderato"), g => num(g.punti_attesi, 2))}
        ${riga(t("mercato.parte_titolare"), g => partenzaAParole(g.quota_titolare))}
        ${riga(t("mercato.segna"), g => perc(g.p_gol))}
        ${riga(t("mercato.assist"), g => perc(g.p_assist))}
        ${riga(t("mercato.giallo"), g => perc(g.p_giallo))}
      </div></details></div>
      ${c.giocatori.map(g => `<div class="debole piccolo"><b>${esc(g.nome)}</b>: ${testiDi(g, "motivi").map(esc).join(" · ") || "–"}</div>`).join("")}`);
  } catch (e) {
    if (numero === ultimaScheda && !$("#foglio").hidden) apriFoglio(errore(e));
  }
}

// ---------------------------------------------------------------- pannello: apre, chiude, si trascina verso il basso
let chiusura = null, focusPrima = null;
const SFONDO_FOGLIO = () => [document.querySelector(".salta"), document.querySelector(".testata"), contenuto, document.querySelector(".schede")].filter(Boolean);   // anche il link «Vai al contenuto»: il fuoco non esce dal pannello
function bloccaSfondo() {
  focusPrima = document.activeElement;
  SFONDO_FOGLIO().forEach(e => { e.inert = true; });
  setTimeout(() => { const c = document.querySelector(".foglio-chiudi"); if (c && !$("#foglio").hidden) c.focus({ preventScroll: true }); }, 60);
}
function sbloccaSfondo() {
  SFONDO_FOGLIO().forEach(e => { e.inert = false; });
  if (focusPrima && document.body.contains(focusPrima) && focusPrima.focus) focusPrima.focus({ preventScroll: true });
  focusPrima = null;
}
function apriFoglio(html) {
  clearTimeout(chiusura);
  const foglio = $("#foglio");
  const eraAperto = !foglio.hidden;
  foglio.classList.remove("chiude");
  const corpo = $(".foglio-corpo");
  corpo.classList.remove("trascina");
  corpo.style.transform = ""; corpo.style.transition = "";
  $("#foglio-contenuto").innerHTML = html;
  const titoloFoglio = $("#foglio-contenuto").querySelector("h1, h2, h3");          // il pannello prende il nome dal suo primo titolo
  if (titoloFoglio && titoloFoglio.textContent.trim()) { titoloFoglio.id = "foglio-titolo"; corpo.setAttribute("aria-labelledby", "foglio-titolo"); corpo.removeAttribute("aria-label"); }
  else { corpo.removeAttribute("aria-labelledby"); corpo.setAttribute("aria-label", t("shell.dettagli")); }
  foglio.hidden = false;
  if (!eraAperto) { corpo.scrollTop = 0; bloccaSfondo(); }
  document.body.style.overflow = "hidden";
}
function chiudiFoglio() {
  const foglio = $("#foglio");
  if (foglio.hidden) return;
  const fine = () => { foglio.hidden = true; foglio.classList.remove("chiude"); document.body.style.overflow = ""; sbloccaSfondo(); };
  foglio.classList.add("chiude");
  clearTimeout(chiusura);
  chiusura = setTimeout(fine, 240);
}
(function trascinamento() {
  const corpo = $(".foglio-corpo"), maniglia = $("#maniglia");
  let y0 = null, dy = 0, t0 = 0;
  maniglia.addEventListener("pointerdown", ev => { y0 = ev.clientY; dy = 0; t0 = performance.now(); corpo.classList.add("trascina"); maniglia.setPointerCapture(ev.pointerId); });
  maniglia.addEventListener("pointermove", ev => {
    if (y0 === null) return;
    dy = Math.max(0, ev.clientY - y0);
    corpo.style.transform = `translateY(${dy}px)`;
  });
  const fine = () => {
    if (y0 === null) return;
    const veloce = dy / Math.max(1, performance.now() - t0) > 0.6;
    y0 = null;
    corpo.classList.remove("trascina");
    if (dy > 120 || (veloce && dy > 40)) {
      corpo.style.transition = "transform .22s ease-in";
      corpo.style.transform = "translateY(100%)";
      setTimeout(() => { const f = $("#foglio"); f.hidden = true; document.body.style.overflow = ""; corpo.style.transform = ""; corpo.style.transition = ""; sbloccaSfondo(); }, 230);
    } else {
      corpo.style.transition = "transform .4s var(--molla)";
      corpo.style.transform = "translateY(0)";
      setTimeout(() => { corpo.style.transition = ""; corpo.style.transform = ""; }, 420);
    }
  };
  maniglia.addEventListener("pointerup", fine);
  maniglia.addEventListener("pointercancel", fine);
})();

// ---------------------------------------------------------------- clic e tocchi globali
document.addEventListener("click", ev => {
  const g = ev.target.closest("[data-giocatore]");
  if (g && !g.disabled) apriGiocatore(Number(g.dataset.giocatore));
  const bz = ev.target.closest("[data-bozza]");
  if (bz) { copiaTesto(bz.dataset.bozza).then(ok => avviso(ok ? t("mercato.bozza_copiata") : t("comune.non_copio"))); return; }
  const cf = ev.target.closest("[data-confronta]");
  if (cf) { ev.stopPropagation(); apriScelta(Number(cf.dataset.confronta)); return; }
  const v = ev.target.closest("[data-vai]");
  if (v) { chiudiFoglio(); vai(v.dataset.vai); }
  if (ev.target.closest("[data-vai-novita]")) { vai("altro"); vistaNovita(); }
  const ig = ev.target.closest("[data-imp-gruppo]");
  if (ig) { chiudiFoglio(); vai("impostazioni", ig.dataset.impGruppo); }
  if (ev.target.closest("[data-chiudi]")) chiudiFoglio();
  if (ev.target.closest("[data-riprova]")) vai(stato.vista);
  if (ev.target.closest("[data-importa-rose]")) {
    if (typeof apriPrimoAvvio === "function") apriPrimoAvvio(); else { vaiLega("importa"); if (typeof dfPortaA === "function") dfPortaA("rose"); }
  }
});
document.addEventListener("keydown", ev => {
  if (ev.key === "Escape") { chiudiFoglio(); return; }
  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const bersaglio = ev.target;
  if (bersaglio && (["INPUT", "TEXTAREA", "SELECT"].includes(bersaglio.tagName) || bersaglio.isContentEditable)) return;      // si sta scrivendo
  if (ev.key === "/") { ev.preventDefault(); apriRicerca(); }                                          // tastiera: / cerca
  else if (/^[1-4]$/.test(ev.key) && $("#foglio").hidden) vai(VISTE[Number(ev.key) - 1]);             // tastiera: 1-4 cambiano sezione
  else if (ev.key === "," && $("#foglio").hidden) vai("impostazioni");                                 // tastiera: , apre le impostazioni
});
// il riflesso del vetro segue il dito
document.addEventListener("pointerdown", ev => {
  const carta = ev.target.closest(".carta");
  if (!carta) return;
  const r = carta.getBoundingClientRect();
  carta.style.setProperty("--px", `${ev.clientX - r.left}px`);
  carta.style.setProperty("--py", `${ev.clientY - r.top}px`);
  carta.classList.add("luce");
  setTimeout(() => carta.classList.remove("luce"), 450);
}, { passive: true });

// ---------------------------------------------------------------- scambi
const segnoSc = x => `<span class="guadagno ${x > 0.05 ? "su" : x < -0.05 ? "giu" : ""}">${segno(x, 1)}</span>`;

// Bozza del messaggio da mandare all'altro allenatore (si copia con un tocco).
function bozzaScambio(s) {
  const nomi = lista => lista.map(x => x.nome).join(t("scambio.bozza_e"));
  const quasi = Math.abs(s.guadagno_mio - s.guadagno_loro) < 1;
  return t("scambio.bozza", { do: nomi(s.do), ricevo: nomi(s.ricevo),
    quanto: quasi ? t("scambio.bozza_uguale") : t("scambio.bozza_punti", { loro: segno(s.guadagno_loro, 1), mio: segno(s.guadagno_mio, 1) }) });
}

// Quali squadre hanno più da guadagnare dagli scambi proposti, e in quale reparto: sono le più propense ad accettare.
function squadrePropense(proposte) {
  const per = {};
  proposte.forEach(s => {
    const x = per[s.altra] || (per[s.altra] = { n: 0, somma: 0, reparti: {} });
    x.n++; x.somma += s.guadagno_loro;
    Object.entries((s.reparti && s.reparti.loro) || {}).forEach(([r, v]) => { x.reparti[r] = Math.max(x.reparti[r] || -99, v); });
  });
  const elenco = Object.entries(per).map(([nome, x]) => ({ nome, n: x.n, media: x.somma / x.n, reparto: Object.entries(x.reparti).sort((a, b) => b[1] - a[1])[0] }))
    .sort((a, b) => b.media - a.media).slice(0, 4);
  if (elenco.length < 2) return "";
  return `<div class="carta"><h2>${t("scambio.chi_accetta_piu")}</h2>
    <div class="debole piccolo">${t("scambio.squadre_che_guadagnano")}</div>
    ${elenco.map(x => `<div class="riga"><span><b>${esc(x.nome)}</b><span class="debole piccolo" style="display:block">${tp("scambio.n_scambi", x.n)}${x.reparto && x.reparto[1] > 0 ? ` · ${t("scambio.migliora", { reparto: NOMI_RUOLO[x.reparto[0]] || x.reparto[0], p: segno(x.reparto[1], 1) })}` : ""}</span></span>
      <b class="positivo">${segno(x.media, 1)}</b></div>`).join("")}</div>`;
}

function cartaScambio(s, extra = "") {
  const lato = lista => lista.map(x => `<div>${badgeRuolo(x.ruolo, true)}<button class="nome-g" data-giocatore="${x.id}" style="display:inline">${esc(x.nome)}</button>
    <div class="debole piccolo">${sigla(x.squadra)} · ${t("scambio.quot", { n: x.quotazione })}</div></div>`).join("");
  return `<div class="carta scambio">
    <div class="debole piccolo">${t("scambio.con")} <b>${esc(s.altra)}</b>${s.n_do > 1 || s.n_ricevo > 1 ? ` · <span class="formato-scambio">${t("scambi.formato", { n: s.n_do, m: s.n_ricevo })}</span>` : ""}</div>
    <div class="proposta"><div class="lato"><div class="debole piccolo">${t("scambi.dai")}</div>${lato(s.do)}</div><span class="freccia">⇄</span>
      <div class="lato dx"><div class="debole piccolo">${t("scambi.ricevi")}</div>${lato(s.ricevo)}</div></div>
    <div class="guadagno-grande">${t("scambio.tu_loro_stagione", { mio: segnoSc(s.guadagno_mio), loro: segnoSc(s.guadagno_loro) })}</div>
    <div class="debole piccolo" style="text-align:center">${tp("scambio.prossime", s.giornate.length)}: ${t("scambio.tu_loro", { mio: segnoSc(s.breve_mio), loro: segnoSc(s.breve_loro) })} · ${t("scambio.quot", { n: `${s.quotazione_do} → ${s.quotazione_ricevo}` })}</div>
    <div class="pulsanti" style="justify-content:center"><button class="bottone secondario" data-bozza="${esc(bozzaScambio(s))}">${t("scambio.copia_bozza_del")}</button></div>
    ${extra}
  </div>`;
}

// Impatto dello scambio sui reparti della tua rosa (variazione % dei punti attesi nelle prossime giornate).
function impattoReparti(s) {
  if (!s.reparti || !s.reparti.mio) return "";
  const riga = r => { const x = s.reparti.mio[r]; return `<div class="reparto">${badgeRuolo(r)}<span>${NOMI_RUOLO[r]}</span>
    <b class="${x > 0.05 ? "positivo" : x < -0.05 ? "negativo" : ""}">${segno(x, 1)}%</b></div>`; };
  const tot = s.percentuale_mio;
  return `<div class="carta"><h2>${t("scambio.impatto_sulla_tua")}</h2>
    <div class="debole piccolo">${t("scambio.conta_anche_resto")}</div>
    ${["P", "D", "C", "A"].map(riga).join("")}
    <div class="riga" style="margin-top:8px"><span>${tp("scambio.in_totale", s.giornate.length)}</span>
      <b class="${tot > 0.05 ? "positivo" : tot < -0.05 ? "negativo" : ""}">${segno(tot, 1)}%</b></div></div>`;
}

// Archivio degli scambi analizzati, nella memoria di questo telefono (sparisce se si cancellano i dati del sito).
function leggiArchivio() {
  try {
    const a = JSON.parse(localStorage.getItem("archivio-scambi") || "[]");
    return Array.isArray(a) ? a.filter(v => v && Array.isArray(v.do) && Array.isArray(v.ricevo)) : [];
  } catch { return []; }
}
function salvaInArchivio(s) {
  const voce = { quando: new Date().toISOString(), con: s.altra, do: s.do.map(x => x.nome), ricevo: s.ricevo.map(x => x.nome),
                 mio: s.guadagno_mio, loro: s.guadagno_loro, percentuale: s.percentuale_mio };
  const chiave = v => `${v.con}|${v.do.join(",")}|${v.ricevo.join(",")}`;
  try {
    const nuovo = [voce, ...leggiArchivio().filter(v => chiave(v) !== chiave(voce))].slice(0, 20);
    localStorage.setItem("archivio-scambi", JSON.stringify(nuovo));
  } catch { /* niente memoria: va bene lo stesso */ }
}
function mostraArchivio() {
  const dove = $("#archivio-scambi");
  if (!dove) return;
  const a = leggiArchivio();
  dove.innerHTML = a.length ? `<div class="carta"><details><summary>${t("scambio.archivio", { n: a.length })}</summary><div class="debole piccolo">${t("scambio.gli_ultimi_scambi")}</div>
    <ul class="elenco">${a.map(v => `<li class="voce-archivio"><div><b>${v.do.map(esc).join(", ")}</b> ⇄ <b>${v.ricevo.map(esc).join(", ")}</b>
      <div class="debole piccolo">${t("scambio.con_minuscolo")} ${esc(v.con)} · ${fData(new Date(v.quando))}</div></div>
      <div style="text-align:right">${segnoSc(v.mio)}<div class="debole piccolo">${v.percentuale != null ? `${segno(v.percentuale, 1)}%` : ""}</div></div></li>`).join("")}</ul></details></div>` : "";
}

// Risultato dell'analizzatore: giudizio in parole, prima e dopo per le due squadre, rose, crediti. Tutti i dati passano da esc().
const CLASSE_CHI = { entrambi: "ok", te: "ok", lui: "attenzione-lieve", poco: "neutro", nessuno: "no" };
function esitoAnalisi(s) {
  const g = s.giudizio || { chi: "poco", testo: "", spiegazione: [] };
  const valido = s.valido !== false, c = s.conguaglio || { crediti: 0 };
  const titolo = valido ? t("scambi.chi_" + g.chi) : t("scambi.chi_non_valido");
  const tre = (a, b, c3) => `<div class="riga-confronto"><span>${a}</span><b>${b}</b><b>${c3}</b></div>`;
  const prima_dopo = x => `${num(x.prima)} → ${num(x.dopo)} <span class="debole">(${segnoSc(x.variazione)})</span>`;
  const conta = x => ["P", "D", "C", "A"].map(r => `${ruoloSigla(r)}${x.conteggio[r]}`).join(" ");      // in inglese G D M F, come altrove
  const stato = x => `<span class="${x.valida ? "positivo" : "negativo"}">${x.valida ? t("scambi.rosa_ok") : t("scambi.rosa_no")}</span>`;
  const vr = s.valore_rosa, pa = s.panchina, ro = s.rose;
  const confronto = `<div class="carta"><h2>${t("scambi.confronto")}</h2>
    <div class="confronto">
      <div class="riga-confronto intestazione"><span></span><b>${t("scambi.tu")}</b><b>${esc(s.altra)}</b></div>
      ${tre(s.giornate.length === 1 ? t("scambi.formazione_migliore_una") : t("scambi.formazione_migliore", { n: s.giornate.length }), prima_dopo(vr.mio), prima_dopo(vr.loro))}
      ${tre(t("scambi.panchina"), segnoSc(pa.mio.variazione), segnoSc(pa.loro.variazione))}
      ${tre(t("scambi.in_stagione"), segnoSc(s.guadagno_mio), segnoSc(s.guadagno_loro))}
      ${c.crediti && c.valore_mio != null ? tre(t("scambi.con_crediti"), segnoSc(s.netto_mio), segnoSc(s.netto_loro)) : ""}
      ${tre(t("scambi.rose_dopo"), `${conta(ro.mio)}<br>${stato(ro.mio)}`, `${conta(ro.loro)}<br>${stato(ro.loro)}`)}
    </div></div>`;
  const residui = x => (x == null ? "–" : x);
  const crediti = c.crediti ? `<div class="carta"><h2>${t("scambi.crediti_titolo")}</h2>
    <div class="debole">${t("scambi.crediti_prima_dopo", { nome: t("scambi.tu"), prima: residui(c.residui.mio), dopo: residui(c.dopo.mio) })}</div>
    <div class="debole">${t("scambi.crediti_prima_dopo", { nome: esc(s.altra), prima: residui(c.residui.loro), dopo: residui(c.dopo.loro) })}</div>
    <div class="debole piccolo" style="margin-top:8px">${c.tasso_mio != null ? t("scambi.crediti_valore", { tasso: num(c.tasso_mio, 2) }) : t("scambi.crediti_senza_stima")}</div>
    ${c.problema ? `<div class="attenzione" style="margin-top:10px">${esc(c.problema)}</div>` : ""}</div>` : "";
  const problemi = (s.problemi || []).length ? `<div class="attenzione"><b>${t("scambi.problemi")}</b><ul class="elenco-semplice">${s.problemi.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>` : "";
  return `<div class="esito-scambio-colonne">
    <div class="colonna-esito">
      <div class="verdetto ${valido ? CLASSE_CHI[g.chi] || "neutro" : "no"}"><h3>${titolo}</h3><p>${esc(g.testo)}</p></div>
      ${problemi}
      ${cartaScambio(s)}
      <div class="carta"><h2>${t("scambi.perche")}</h2><ul class="elenco-semplice">${(g.spiegazione || []).map(r => `<li>${esc(r)}</li>`).join("")}</ul>
        <div class="debole piccolo">${t("scambi.per_giornata")}: ${s.giornate.map((gg, i) => `G${gg} ${segnoSc(s.per_giornata_mio[i])}`).join(" · ")}</div></div>
    </div>
    <div class="colonna-esito">${confronto}${crediti}${impattoReparti(s)}</div>
  </div>`;
}

// Scambi in un punto solo, con tre modi: «Trova per me» (proposte), «Costruisci» (scegli tu chi dai e chi ricevi) e «Valuta un'offerta»
// (incolli il messaggio). Costruisci e Valuta mostrano lo stesso risultato (esitoAnalisi); ogni proposta di Trova lo apre con un tocco.
const MODI_SCAMBIO = [["trova", "scambio.trova_per"], ["costruisci", "scambio.costruisci"], ["valuta", "scambio.valuta_offerta"]];
const MISURE_SCAMBIO = [[0, "scambio.uno_contro_uno"], [2, "scambio.fino_a_2"], [3, "scambio.fino_a_3"], [4, "scambio.fino_a_4"]];

async function vistaScambi() {
  const mia = nuovaRichiesta();
  caricamento(t("scambio.carico_squadre"));
  let squadre;
  try { squadre = await api("/api/squadre"); } catch (e) { if (ancoraValida(mia)) contenuto.innerHTML = erroreVista(e); return; }
  if (!ancoraValida(mia)) return;
  const altre = squadre.filter(s => !s.mia);
  if (squadre.length && !altre.length) {              // solo la tua rosa: gli scambi aspettano quelle degli altri (non è un errore)
    contenuto.classList.remove("ridisegna");
    contenuto.innerHTML = `<div class="carta"><h2>${t("nav.scambi")}</h2><p class="debole">${t("scambio.servono_altre")}</p>
      <div class="pulsanti"><button class="bottone" type="button" id="scambi-aggiungi-rose">${t("lega.voce_importa")}</button></div></div>`;
    $("#scambi-aggiungi-rose").addEventListener("click", () => vaiLega("importa"));
    return;
  }
  const opzioni = altre.map(s => `<option value="${esc(s.nome)}">${esc(s.nome)}</option>`).join("");
  const FUNZIONE_MODO = { trova: "scambi_trova", costruisci: "scambi_costruisci" };           // «Valuta un'offerta» c'è sempre
  const modi = MODI_SCAMBIO.filter(([k]) => !FUNZIONE_MODO[k] || funz(FUNZIONE_MODO[k]));
  const modo0 = modi.some(([k]) => k === stato.scambiModo) ? stato.scambiModo : modi[0][0];
  const nascosto = m => (m === modo0 ? "" : "hidden");
  contenuto.classList.remove("ridisegna");
  contenuto.innerHTML = `
    <div class="segmenti" id="scambi-modi" role="group" aria-label="${t("scambio.cosa_vuoi_fare")}" ${modi.length < 2 ? "hidden" : ""}>${modi.map(([k, n]) =>
      `<button type="button" data-modo-scambio="${k}" class="${k === modo0 ? "attivo" : ""}" aria-pressed="${k === modo0}">${t(n)}</button>`).join("")}</div>
    <div class="scambi-colonne"><div class="scambi-sinistra">
    <div class="carta scambi-pannello" data-pannello="trova" ${nascosto("trova")}><h2>${t("scambio.trova_per")}</h2>
      <div class="debole piccolo">${t("scambio.scambi_cui_guadagnate")}</div>
      <label class="etichetta-campo" for="proposte-con">${t("scambio.con_quale_squadra")}</label>
      <select class="campo-testo" id="proposte-con"><option value="">${t("scambio.tutte_squadre")}</option>${opzioni}</select>
      <div class="etichetta-campo" id="titolo-misura">${t("scambio.quanti_giocatori_per")}</div>
      <div class="chips misure" id="proposte-misura" role="group" aria-labelledby="titolo-misura">${MISURE_SCAMBIO.map(([n, testo]) =>
        `<button type="button" class="chip ${n === 0 ? "attiva" : ""}" data-misura="${n}" aria-pressed="${n === 0}" ${n ? "disabled" : ""}>${t(testo)}</button>`).join("")}</div>
      <div class="debole piccolo">${t("scambio.per_gli_scambi")}</div>
      <div class="pulsanti"><button class="bottone" id="cerca-scambi">${t("scambio.cerca_scambi")}</button></div>
      <div class="contatore-scambi" id="contatore-scambi" aria-live="polite" hidden></div>
    </div>
    <div class="carta analizzatore scambi-pannello" data-pannello="costruisci" ${nascosto("costruisci")}><h2>${t("scambi.analizza_titolo")}</h2>
      <div class="debole piccolo">${t("scambi.analizza_spiega")}</div>
      <label class="etichetta-campo" for="analizza-con">${t("scambi.con")}</label>
      <select class="campo-testo" id="analizza-con">${opzioni}</select>
      <div class="parti">
        ${["do", "ricevo"].map(k => { const cerca = k === "do" ? t("scambi.cerca_mia") : t("scambi.cerca_loro", { squadra: altre.length ? altre[0].nome : "" });
          return `<section class="parte" aria-labelledby="titolo-${k}">
          <h3 id="titolo-${k}">${k === "do" ? t("scambi.dai") : t("scambi.ricevi")} <span class="conta-scelti" id="conta-${k}" aria-live="polite"></span></h3>
          <div class="scelti" id="scelti-${k}"></div>
          <input type="search" class="campo-testo" id="cerca-${k}" autocomplete="off" aria-label="${esc(cerca)}" placeholder="${esc(cerca)}">
          <div class="scelte" id="scelte-${k}" role="group" aria-labelledby="titolo-${k}"></div>
        </section>`; }).join("")}
      </div>
      <div class="conguaglio">
        <h3>${t("scambi.conguaglio")}</h3>
        <div class="debole piccolo">${t("scambi.conguaglio_aiuto")}</div>
        <div class="riga-conguaglio">
          <div class="segmenti" role="group" aria-label="${esc(t("scambi.conguaglio"))}">
            <button type="button" class="attivo" data-verso="1" aria-pressed="true">${t("scambi.ricevo_crediti")}</button>
            <button type="button" data-verso="-1" aria-pressed="false">${t("scambi.pago_crediti")}</button></div>
          <input type="number" min="0" max="100000" step="1" inputmode="numeric" class="campo-testo" id="conguaglio" placeholder="0" aria-label="${esc(t("scambi.crediti_quanti"))}">
        </div>
        <div class="debole piccolo" id="crediti-residui"></div>
        <div class="negativo piccolo" id="conguaglio-avviso" role="alert"></div>
      </div>
      <div class="pulsanti"><button class="bottone" id="analizza">${t("scambi.analizza")}</button></div>
    </div>
    <div class="carta scambi-pannello" data-pannello="valuta" ${nascosto("valuta")}><h2>${t("scambio.valuta_offerta")}</h2>
      <div class="debole piccolo">${t("scambio.incolla_messaggio_che")}</div>
      <textarea class="campo-testo" id="offerta-testo" rows="4" maxlength="4000" aria-label="${t("scambio.messaggio_dell_offerta")}" placeholder="${t("scambio.rowe_politano_dai")}" style="margin-top:10px;width:100%"></textarea>
      <div class="pulsanti"><button class="bottone" id="valuta-offerta">${t("scambio.valuta_offerta_2")}</button></div>
    </div></div>
    <div class="scambi-destra">
      <div id="elenco-scambi" data-esito="trova" ${nascosto("trova")}></div>
      <div id="esito-scambio" data-esito="costruisci" aria-live="polite" ${nascosto("costruisci")}></div>
      <div id="esito-offerta" data-esito="valuta" aria-live="polite" ${nascosto("valuta")}></div>
    </div></div>
    <div id="archivio-scambi"></div>`;

  const scegliModo = m => {
    stato.scambiModo = m;
    document.querySelectorAll("[data-modo-scambio]").forEach(b => { const on = b.dataset.modoScambio === m; b.classList.toggle("attivo", on); b.setAttribute("aria-pressed", on ? "true" : "false"); });
    document.querySelectorAll("[data-pannello]").forEach(p => { p.hidden = p.dataset.pannello !== m; });
    document.querySelectorAll("[data-esito]").forEach(p => { p.hidden = p.dataset.esito !== m; });
    const arch = $("#archivio-scambi");
    if (arch) arch.hidden = m === "trova";
  };
  $("#scambi-modi").addEventListener("click", ev => { const b = ev.target.closest("[data-modo-scambio]"); if (b) scegliModo(b.dataset.modoScambio); });
  scegliModo(modo0);

  // contatore delle ricerche di oggi (solo per chi ha un limite; l'amministratore non lo vede). Leggerlo non consuma niente.
  const mostraContatore = l => {
    const el = $("#contatore-scambi");
    if (!el) return;
    const n = l ? l.restano : null;
    el.hidden = n == null;
    el.textContent = n == null ? "" : n === 0 ? t("scambio.ricerche_finite") : tp("scambio.ricerche_restano", n);
  };
  if (funz("scambi_trova")) api("/api/scambi/limite").then(mostraContatore).catch(() => { /* senza contatore si può cercare lo stesso */ });    // spenta: niente richiesta (risponderebbe 404)

  // ---- analizzatore a selezione multipla: da 1 a 4 giocatori per parte, con ricerca, e conguaglio in crediti
  const MAX_PARTE = 4;
  const rose = { do: [], ricevo: [] };                            // giocatori della rosa di chi dà / di chi riceve
  const scelti = { do: new Map(), ricevo: new Map() };            // id -> giocatore
  const norm = x => String(x || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const cercati = k => norm($(`#cerca-${k}`).value).trim();
  function disegnaScelti(k) {
    const m = scelti[k];
    $(`#conta-${k}`).textContent = t("scambi.scelti", { n: m.size, max: MAX_PARTE });
    $(`#scelti-${k}`).innerHTML = m.size ? [...m.values()].map(x => `<button type="button" class="scelto-chip" data-togli="${x.id}" data-parte="${k}"
        aria-label="${esc(t("scambi.togli", { nome: x.nome }))}">${avatar({ id: x.id, nome: x.nome, squadra: x.squadra_slug, ruolo: x.ruolo })}
        <span>${esc(x.nome)}</span><i aria-hidden="true">×</i></button>`).join("")
      : `<span class="debole piccolo">${t("scambi.nessuno_scelto")}</span>`;
  }
  function disegnaLista(k) {
    const q = cercati(k), pieno = scelti[k].size >= MAX_PARTE;
    const righe = rose[k].filter(x => !q || norm(x.nome).includes(q));
    $(`#scelte-${k}`).innerHTML = righe.length ? righe.map(x => {
      const sel = scelti[k].has(x.id);
      return `<label class="voce-scelta ${sel ? "scelta" : ""}"><input type="checkbox" value="${x.id}" data-parte="${k}" ${sel ? "checked" : ""} ${pieno && !sel ? "disabled" : ""}>
        ${avatar({ id: x.id, nome: x.nome, squadra: x.squadra_slug, ruolo: x.ruolo })}
        <span class="nome-scelta">${esc(x.nome)}<span class="debole piccolo" style="display:block">${badgeRuolo(x.ruolo || "?", true)}${sigla(x.squadra_slug || x.squadra)} · ${t("scambio.quot", { n: x.quotazione ?? "–" })}</span></span></label>`;
    }).join("") : `<div class="debole piccolo vuoto-scelte">${t("scambi.nessun_risultato")}</div>`;
    $(`#conta-${k}`).classList.toggle("pieno", pieno);
    if (pieno) $(`#conta-${k}`).title = t("scambi.massimo", { max: MAX_PARTE });
  }
  const ridisegna = k => { disegnaScelti(k); disegnaLista(k); };
  const ultime = {};
  async function caricaRosa(k, squadra) {
    const numero = (ultime[k] = (ultime[k] || 0) + 1);
    const r = await api(`/api/rosa?squadra=${encodeURIComponent(squadra)}`);
    if (numero !== ultime[k] || !document.body.contains($(`#scelte-${k}`) || document.createElement("i"))) return;
    rose[k] = r.giocatori.filter(x => x.id);
    scelti[k].clear();
    ridisegna(k);
  }
  const miaSquadra = squadre.find(s => s.mia);
  const loro = () => squadre.find(s => s.nome === $("#analizza-con").value);
  function crediti() {
    const m = miaSquadra && miaSquadra.crediti_residui, l = loro() && loro().crediti_residui;
    const dove = $("#crediti-residui");
    if (dove) dove.textContent = t("scambi.crediti_residui", { mio: m ?? t("scambi.non_indicati"), altra: loro() ? loro().nome : "", loro: l ?? t("scambi.non_indicati") });
    const x = Number($("#conguaglio").value) || 0, verso = Number($(".riga-conguaglio .segmenti .attivo").dataset.verso);
    let a = "";
    if (x && verso < 0 && m != null && x > m) a = t("scambi.fondi_pochi", { mio: m });
    if (x && verso > 0 && l != null && x > l) a = t("scambi.fondi_pochi_loro", { altra: loro().nome, loro: l });
    $("#conguaglio-avviso").textContent = a;
  }
  mostraArchivio();
  const aggiornaCerca = () => { const n = loro() ? loro().nome : ""; $("#cerca-ricevo").placeholder = t("scambi.cerca_loro", { squadra: n }); $("#cerca-ricevo").setAttribute("aria-label", $("#cerca-ricevo").placeholder); };
  try {
    if (miaSquadra) await caricaRosa("do", miaSquadra.nome);
    if (altre.length) await caricaRosa("ricevo", altre[0].nome);
  } catch (e) { if (ancoraValida(mia)) avviso(e.message); }
  // le rose arrivano dopo: se intanto sei passato a un'altra pagina i campi degli scambi non ci sono più (era l'errore «reading 'value'»)
  if (!ancoraValida(mia) || !$("#analizza-con")) return;
  aggiornaCerca(); crediti();
  $("#analizza-con").addEventListener("change", ev => {
    caricaRosa("ricevo", ev.target.value).catch(e => avviso(e.message));
    aggiornaCerca(); crediti();
  });
  for (const k of ["do", "ricevo"]) {
    $(`#cerca-${k}`).addEventListener("input", () => disegnaLista(k));
    $(`#scelte-${k}`).addEventListener("change", ev => {
      const i = ev.target.closest("input[type=checkbox]");
      if (!i) return;
      const x = rose[k].find(g => String(g.id) === i.value);
      if (i.checked && scelti[k].size < MAX_PARTE) scelti[k].set(x.id, x); else scelti[k].delete(x.id);
      ridisegna(k);
      const ancora = $(`#scelte-${k} input[value="${x.id}"]`);          // chi usa la tastiera resta sul giocatore appena toccato
      if (ancora && ev.isTrusted) ancora.focus();
    });
    $(`#scelti-${k}`).addEventListener("click", ev => {
      const b = ev.target.closest("button[data-togli]");
      if (b) { scelti[k].delete(Number(b.dataset.togli)); ridisegna(k); }
    });
  }
  $(".riga-conguaglio .segmenti").addEventListener("click", ev => {
    const b = ev.target.closest("button");
    if (!b) return;
    for (const x of $(".riga-conguaglio .segmenti").children) { x.classList.toggle("attivo", x === b); x.setAttribute("aria-pressed", x === b ? "true" : "false"); }
    crediti();
  });
  $("#conguaglio").addEventListener("input", crediti);

  // ---- Trova per me: una ricerca solo quando tocchi il pulsante (mai da sola, mai due insieme)
  let misura = 0, proposteTrovate = [], cercando = false;
  const aggiornaMisure = () => {
    const con = $("#proposte-con").value;
    document.querySelectorAll("[data-misura]").forEach(b => {
      const n = Number(b.dataset.misura);
      b.disabled = !!n && !con;
      b.classList.toggle("attiva", n === misura);
      b.setAttribute("aria-pressed", n === misura ? "true" : "false");
    });
  };
  $("#proposte-con").addEventListener("change", () => { if (!$("#proposte-con").value) misura = 0; aggiornaMisure(); });
  $("#proposte-misura").addEventListener("click", ev => {
    const b = ev.target.closest("[data-misura]");
    if (b && !b.disabled) { misura = Number(b.dataset.misura); aggiornaMisure(); }
  });
  $("#cerca-scambi").addEventListener("click", async ev => {
    if (cercando) return;
    const pulsante = ev.currentTarget, con = $("#proposte-con").value;
    const elenco = $("#elenco-scambi");
    cercando = true; pulsante.disabled = true;
    elenco.innerHTML = `<div class="caricamento">${t("scambio.cerco_gli_scambi")}</div>`;
    try {
      const r = await api("/api/scambi/proposte" + (misura ? `?fino_a=${misura}&con=${encodeURIComponent(con)}` : (con ? `?con=${encodeURIComponent(con)}` : "")));
      if (!document.body.contains(elenco)) return;
      mostraContatore(r.ricerche);
      proposteTrovate = r.proposte;
      elenco.innerHTML = r.proposte.length ? squadrePropense(r.proposte) + r.proposte.map((s, i) => cartaScambio(s, `<div class="pulsanti" style="justify-content:center">
          <button class="bottone secondario" data-dettaglio="${i}" aria-expanded="false">${t("scambio.vedi_giudizio_completo")}</button></div><div class="dettaglio-scambio" id="dettaglio-${i}" aria-live="polite"></div>`)).join("")
        : `<div class="carta vuoto">${t("scambio.nessuno_scambio_che")}</div>`;
    } catch (e) {
      elenco.innerHTML = errore(e);                                                 // il testo è quello del server, con il tempo che manca
      if (e.status === 429) api("/api/scambi/limite").then(mostraContatore).catch(() => { /* resta il messaggio sopra */ });    // il contatore dice la verità: l'attesa breve («una alla volta») non è il tetto del giorno
    } finally { cercando = false; pulsante.disabled = false; }
  });
  $("#elenco-scambi").addEventListener("click", async ev => {
    const b = ev.target.closest("[data-dettaglio]");
    if (!b) return;
    const i = Number(b.dataset.dettaglio), s = proposteTrovate[i], dove = $(`#dettaglio-${i}`);
    if (!s || !dove) return;
    if (b.getAttribute("aria-expanded") === "true") { dove.innerHTML = ""; b.setAttribute("aria-expanded", "false"); b.textContent = t("scambio.vedi_giudizio_completo"); return; }
    b.disabled = true;
    dove.innerHTML = `<div class="caricamento">${t("scambi.calcolo")}</div>`;
    try {
      const completo = await api(`/api/scambi/analizza?completo=true&con=${encodeURIComponent(s.altra)}&do=${s.do.map(x => x.id).join(",")}&ricevo=${s.ricevo.map(x => x.id).join(",")}`);
      dove.innerHTML = esitoAnalisi(completo);
      b.setAttribute("aria-expanded", "true"); b.textContent = t("scambio.nascondi_giudizio");
    } catch (e) { dove.innerHTML = errore(e); }
    finally { b.disabled = false; }
  });

  // ---- Valuta un'offerta: riconosco chi dai e chi ricevi dal messaggio, poi stesso risultato di Costruisci
  let valutando = false;
  $("#esito-offerta").addEventListener("click", ev => { if (ev.target.closest("[data-passa-a-costruisci]")) scegliModo("costruisci"); });
  $("#valuta-offerta").addEventListener("click", async ev => {
    const testo = $("#offerta-testo").value.trim();
    if (!testo) { avviso(t("scambio.incolla_prima_messaggio")); return; }
    if (valutando) return;
    const pulsante = ev.currentTarget, esito = $("#esito-offerta");
    valutando = true; pulsante.disabled = true;
    esito.innerHTML = `<div class="caricamento">${t("scambio.leggo_messaggio")}</div>`;
    const aCostruisci = `<div class="pulsanti"><button class="bottone secondario" data-passa-a-costruisci>${t("scambio.scegli_mano_costruisci")}</button></div>`;
    try {
      const o = await api("/api/scambi/da-testo", { method: "POST", body: JSON.stringify({ testo, completo: true }) });
      const riga = (titolo, l) => `<div class="debole piccolo"><b>${titolo}</b>: ${l.length ? l.map(esc).join(", ") : "–"}</div>`;
      const noti = `<div class="carta">${o.con ? riga(t("scambio.riga_con"), [o.con]) : ""}${riga(t("scambi.dai"), o.do)}${riga(t("scambi.ricevi"), o.ricevo)}
        ${o.ambigui.length ? `<div class="attenzione">${t("scambio.ambigui", { nomi: o.ambigui.map(esc).join("; ") })}</div>` : ""}</div>`;
      const ids = o.ids || { do: [], ricevo: [] };
      if (!o.con || !ids.do.length || !ids.ricevo.length) {
        esito.innerHTML = noti + `<div class="attenzione">${t("scambio.non_trovato_giocatori")}</div>` + aCostruisci;
        return;
      }
      const s = await api(`/api/scambi/analizza?completo=true&con=${encodeURIComponent(o.con)}&do=${ids.do.join(",")}&ricevo=${ids.ricevo.join(",")}`);
      salvaInArchivio(s);
      esito.innerHTML = noti + esitoAnalisi(s);
      mostraArchivio();
    } catch (e) { esito.innerHTML = errore(e) + aCostruisci; }
    finally { valutando = false; pulsante.disabled = false; }
  });

  $("#analizza").addEventListener("click", async () => {
    const doIds = [...scelti.do.keys()].join(","), ricevoIds = [...scelti.ricevo.keys()].join(",");
    if (!doIds || !ricevoIds) { avviso(t("scambi.scegli_entrambi")); return; }
    const testoCrediti = $("#conguaglio").value.trim();
    if (testoCrediti && !/^\d{1,6}$/.test(testoCrediti)) { avviso(t("scambi.conguaglio_numero")); return; }
    const verso = Number($(".riga-conguaglio .segmenti .attivo").dataset.verso);
    const conguaglio = testoCrediti ? verso * Number(testoCrediti) : 0;
    const esito = $("#esito-scambio");
    esito.innerHTML = `<div class="caricamento">${t("scambi.calcolo")}</div>`;
    try {
      const s = await api(`/api/scambi/analizza?completo=true&con=${encodeURIComponent($("#analizza-con").value)}&do=${doIds}&ricevo=${ricevoIds}`
        + (conguaglio ? `&conguaglio=${conguaglio}` : ""));
      salvaInArchivio(s);
      esito.innerHTML = esitoAnalisi(s);
      mostraArchivio();
    } catch (e) { esito.innerHTML = errore(e); }
  });
}

// ---------------------------------------------------------------- lega: squadre, rose, regole
const ETICHETTE_BONUS = {
  rigore_segnato: t("bonus.rigore_segnato"), assist: t("bonus.assist"), rigore_parato: t("bonus.rigore_parato"), rigore_sbagliato: t("bonus.rigore_sbagliato"),
  autogol: t("bonus.autogol"), gol_subito_portiere: t("bonus.gol_subito_portiere"), portiere_imbattuto: t("bonus.portiere_imbattuto"),
  ammonizione: t("bonus.ammonizione"), espulsione: t("bonus.espulsione"), mvp: t("bonus.mvp"),
};
const TUTTI_MODULI = ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1", "3-6-1", "4-2-4", "5-2-3", "3-3-4", "4-6-0"];

// Cosa è cambiato nelle rose: scambi, svincolati presi, giocatori lasciati liberi, crediti.
function htmlDifferenze(d) {
  if (!d) return "";
  if (d.prima_importazione) return `<div class="attenzione">${esc(d.testo)}</div>`;
  if (d.nessuna_differenza) return `<div class="movimento ok"><span class="icona-mov">✓</span><span>${t("scambio.nessuna_differenza_rispetto")}</span></div>`;
  const nomi = gs => gs.map(g => `${g.id ? `<button class="nome-g" data-giocatore="${g.id}" style="display:inline">${esc(g.nome)}</button>` : esc(g.nome)}`).join(", ");
  const righe = [];
  if ((d.squadre_nuove || []).length) righe.push(`<div class="movimento"><span class="icona-mov su">＋</span><span>${t("scambio.squadre_aggiunte", { nomi: d.squadre_nuove.map(esc).join(", ") })}</span></div>`);
  if ((d.squadre_tolte || []).length) righe.push(`<div class="movimento"><span class="icona-mov giu">－</span><span>${t("scambio.squadre_tolte", { nomi: d.squadre_tolte.map(esc).join(", ") })}</span></div>`);
  (d.scambi || []).forEach(s => righe.push(`<div class="movimento"><span class="icona-mov">⇄</span><span>${s.da_b.length ? `<b>${t("scambio.scambio_b")}</b>` : `<b>${t("scambio.passaggio_b")}</b>`}
    ${esc(s.squadre[0])} → ${esc(s.squadre[1])}: ${nomi(s.da_a)}${s.da_b.length ? ` <span class="debole">${t("scambio.contro")}</span> ${nomi(s.da_b)}` : ""}</span></div>`));
  (d.svincolati_presi || []).forEach(s => righe.push(`<div class="movimento"><span class="icona-mov su">＋</span><span>${t("scambio.prende_svincolati", { squadra: `<b>${esc(s.squadra)}</b>`, nomi: nomi(s.giocatori) })}</span></div>`));
  (d.tagliati || []).forEach(s => righe.push(`<div class="movimento"><span class="icona-mov giu">－</span><span>${t("scambio.lascia_liberi", { squadra: `<b>${esc(s.squadra)}</b>`, nomi: nomi(s.giocatori) })}</span></div>`));
  (d.crediti || []).forEach(c => righe.push(`<div class="movimento"><span class="icona-mov">¢</span><span>${t("scambi.crediti_titolo")} <b>${esc(c.squadra)}</b>: ${c.prima ?? "–"} → ${c.dopo ?? "–"}</span></div>`));
  return righe.join("");
}

async function vistaRosa(nome) {
  const mia = nuovaRichiesta();
  caricamento(t("scambio.carico_rosa"));
  try {
    const r = await api("/api/rosa" + (nome ? `?squadra=${encodeURIComponent(nome)}` : ""));
    if (!ancoraValida(mia)) return;
    const senzaRuolo = r.giocatori.filter(x => !NOMI_RUOLO[x.ruolo]);
    const gruppi = ["P", "D", "C", "A", "?"].map(ruolo => {
      const g = ruolo === "?" ? senzaRuolo : r.giocatori.filter(x => x.ruolo === ruolo);
      if (ruolo === "?" && !g.length) return "";
      return `<h3>${NOMI_RUOLO[ruolo] || t("scambio.senza_ruolo")} (${g.length})</h3><ul class="elenco">${g.map(x => {
        const p = x.previsione;
        return `<li><button class="voce" ${x.id ? `data-giocatore="${x.id}"` : "disabled"}>
          ${p ? avatarIndice(p) : badgeRuolo(x.ruolo || "?")}
          <span><span class="nome">${esc(x.nome)}</span> <span class="dettaglio">${sigla(x.squadra)}</span>
            <span class="dettaglio" style="display:block">${t("scambio.costo_quot", { c: x.costo ?? "–", q: x.quotazione ?? "–" })}${p ? ` · ${vsAt(p)}${p.data_partita ? ` · ${quando(p.data_partita)}` : ""}` : ""}</span>
            ${p ? `<span class="etichette">${etichetteGiocatore(p)}</span>` : ""}</span>
          ${valoreRosa(p, x)}
        </button></li>`;
      }).join("")}</ul>`;
    }).join("");
    pagina(`
      <div class="carta">
        <div class="riga"><button class="bottone secondario indietro" data-vai="squadra" style="padding:6px 14px;min-height:44px">${ICONA_INDIETRO}${t("scambio.squadra")}</button></div>
        <h2 style="margin-top:14px">${esc(r.nome)}${r.mia ? t("scambio.la_tua") : ""}</h2>
        <details class="rinomina-squadra"><summary>${t("scambio.cambia_nome")}</summary>
          <div class="riga" style="gap:8px;margin-top:8px"><label class="solo-lettori" for="nome-squadra">${t("scambio.nuovo_nome")}</label>
            <input class="campo-testo" id="nome-squadra" type="text" maxlength="60" autocomplete="off" value="${esc(r.nome)}" style="flex:1;min-width:0">
            <button class="bottone secondario" id="salva-nome-squadra" type="button">${t("scambio.salva")}</button></div>
          <div class="debole piccolo">${t("scambio.nome_aiuto")}</div></details>
        <div class="riga riga-crediti"><label for="crediti-squadra">${t("scambio.crediti_residui")}</label>
          <span class="riga" style="gap:8px"><input class="campo-testo" id="crediti-squadra" type="number" min="0" max="99999" inputmode="numeric" value="${r.crediti_residui ?? ""}" style="width:96px;text-align:right">
          <button class="bottone secondario" id="salva-crediti-squadra" type="button">${t("scambio.salva")}</button></span></div>
        <div class="immagini-squadra">
          ${["stemma", "maglia"].map(tipo => { const s = (stato.squadre || []).find(x => x.nome === r.nome); const c = s && s.immagini[tipo]; return `<div class="immagine-squadra">
            ${c ? `<img src="${urlImg(r.nome, tipo)}" alt="${t(NOME_IMMAGINE[tipo])}">` : `<span class="vuota">${t(NOME_IMMAGINE[tipo])}</span>`}
            <label class="bottone secondario" for="img-${tipo}" style="padding:5px 12px;min-height:44px;font-size:var(--t-sec)">${t(c ? "scambio.cambia_tipo" : "scambio.carica_tipo", { tipo: t(NOME_IMMAGINE[tipo]).toLowerCase() })}</label>
            <input id="img-${tipo}" data-tipo="${tipo}" type="file" accept="image/png,image/jpeg,image/webp" hidden></div>`; }).join("")}
        </div>
        <div class="pulsanti">${r.mia ? "" : `<button class="bottone" id="vedi-formazione">${t("scambio.formazione_consigliata_per")}</button>`}</div>
        ${r.avvisi.length ? `<div class="attenzione" style="margin-top:12px">${testiDi(r, "avvisi").map(esc).join("<br>")}</div>` : ""}
        ${gruppi}
        <div class="debole piccolo" style="margin-top:12px">${t("scambio.rose_aggiornate", { data: parseData(r.aggiornato) ? esc(fData(parseData(r.aggiornato), { day: "numeric", month: "long", year: "numeric" })) : "–" })}</div>
      </div>`);
    const vf = $("#vedi-formazione");
    if (vf) vf.addEventListener("click", () => { stato.squadraVista = r.nome; vai("formazione"); });
    $("#salva-nome-squadra").addEventListener("click", async () => {
      const nuovo = $("#nome-squadra").value.trim().replace(/\s+/g, " ");
      if (!nuovo || nuovo.length > 60) { avviso(t("scambio.nome_non_valido")); return; }
      if (nuovo === r.nome) return;
      try {
        const esito = await api("/api/squadre/nome", { method: "PUT", body: JSON.stringify({ nome: r.nome, nuovo }) });
        svuotaCache();
        if (stato.squadraVista === r.nome) stato.squadraVista = null;
        await caricaSquadre();
        avviso(t("scambio.nome_salvato"));
        vistaRosa(esito.nome);
      } catch (e) { avviso(e.message, 5000); }
    });
    $("#salva-crediti-squadra").addEventListener("click", async () => {
      const testo = $("#crediti-squadra").value.trim();
      if (!/^\d{1,5}$/.test(testo)) { avviso(t("scambio.scrivi_crediti_come")); return; }
      try { await api("/api/crediti", { method: "PUT", body: JSON.stringify({ crediti: { [r.nome]: Number(testo) } }) }); svuotaCache(); caricaSquadre(); avviso(t("scambio.crediti_salvati")); }
      catch (e) { avviso(e.message, 5000); }
    });
    document.querySelectorAll(".immagini-squadra input[type=file]").forEach(inp => inp.addEventListener("change", async () => {
      const file = inp.files[0];
      inp.value = "";
      if (!file) return;
      const dati = new FormData();
      dati.append("file", file);
      try {
        const risposta = await fetch(`/api/squadre/immagine?squadra=${encodeURIComponent(r.nome)}&tipo=${inp.dataset.tipo}`, { method: "POST", body: dati, headers: { "X-Fanta": "1" } });
        const esito = await risposta.json().catch(() => ({}));
        if (!risposta.ok) throw new Error(traduciErrore(esito.detail) || t("scambio.caricamento_no"));
        stato.vImg = Date.now();
        await caricaSquadre();
        avviso(t(inp.dataset.tipo === "stemma" ? "scambio.stemma_aggiornato" : "scambio.maglia_aggiornata"));
        vistaRosa(r.nome);
      } catch (e) { avviso(e.message, 6000); }
    }));
  } catch (e) {
    if (ancoraValida(mia)) contenuto.innerHTML = errore(e);
  }
}

const NOME_IMMAGINE = { stemma: "scambio.stemma", maglia: "scambio.maglia" };
const NOMI_CONTROLLI = { partite_per_giornata: t("sd.ctl_partite"), voti_per_giornata: t("sd.ctl_voti"), somma_xg: t("sd.ctl_xg"), titolari_per_squadra: t("sd.ctl_titolari"), sentinella: t("sd.ctl_sentinella") };
// righe della sentinella (fanta/sentinella.py): «sentinella_<invariante>», il nome dell'invariante con gli spazi; quelle a posto
// non si mostrano (le riassume la riga «sentinella»)
const nomeControllo = n => NOMI_CONTROLLI[n] || (n.startsWith("sentinella_") ? t("sd.ctl_sentinella_una", { nome: n.slice(11).replaceAll("_", " ") }) : n);
// Registro delle giornate (#344): le medie delle ultime giornate misurate, ognuna con la sua soglia e il verdetto del server
// (`regge`, che non si ricalcola qui), e le giornate perse con il motivo. Percentuali e punti con una cifra decimale, senza «,0»
// («−3%», «−5,7%»), come sull'iPhone (`ParoleRegistro`).
const regCifra = (x, per = 1, segnato = false) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : (segnato ? segno(x * per, 1) : num(x * per, 1)).replace(/[,.]0$/, "");
const regPerc = (x, segnato = false) => { const v = regCifra(x, 100, segnato); return v === "–" ? v : `${v}%`; };
function statoRegistro(reg, k) {
  if (!reg.verdetto) return { testo: tp("sd.reg_servono", Math.max(1, (reg.finestra || 8) - (reg.giornate || 0))), colore: "" };
  const ok = (reg.regge || {})[k];
  if (ok === true) return { testo: t("sd.reg_regge"), colore: "var(--verde)" };
  return ok === false ? { testo: t("sd.reg_non_regge"), colore: "var(--rosso)" } : { testo: t("sd.nessun_dato"), colore: "" };
}
function cartaRegistro(reg) {
  if (!reg) return "";
  const s = reg.soglie || {}, n = reg.giornate || 0;
  const misura = (k, nome, dettaglio) => {
    const st = statoRegistro(reg, k);
    return `<div class="riga"><span>${t(nome)}</span><span class="piccolo${st.colore ? "" : " debole"}"${st.colore ? ` style="color:${st.colore}"` : ""}>${st.testo}</span></div>
      <div class="debole piccolo">${dettaglio}</div>`;
  };
  const misure = n ? misura("I1", "sd.reg_i1", t("sd.reg_i1_riga", { v: regPerc(reg.i1, true), s: regPerc(s.I1, true), m: num(reg.errore_modello, 2), f: num(reg.errore_fantamedia, 2) }))
    + misura("I2", "sd.reg_i2", t("sd.reg_i2_riga", { c: regCifra(reg.calibrazione, 100), sc: regCifra(s.I2_calibrazione, 100), b: num(reg.brier, 3), sb: num(s.I2_brier, 3) }))
    + misura("I3", "sd.reg_i3", t("sd.reg_i3_riga", { v: regPerc(reg.copertura), min: regPerc(s.I3_minimo), max: regPerc(s.I3_massimo) })) : "";
  const perse = (reg.per_giornata || []).filter(g => g && g.persa);
  return `<div class="carta" id="registro-giornate"><h2>${t("sd.reg_titolo")}</h2>
    <div class="debole piccolo">${t("sd.reg_spiega")}</div>
    <div class="debole piccolo" style="margin:4px 0 8px">${n ? tp("sd.reg_media", n) : t("sd.reg_nessuna")}</div>
    ${misure}
    ${perse.length ? `<h3>${t("sd.reg_perse")}</h3><div class="debole piccolo">${t("sd.reg_perse_spiega")}</div>
      ${perse.map(g => `<div class="riga"><span>${t("sd.reg_giornata", { s: esc(g.stagione), g: esc(g.giornata) })}</span></div>
        <div class="piccolo" style="color:var(--rosso)">${esc(g.persa)}</div>`).join("")}` : ""}</div>`;
}
// Stato dei dati: da dove arriva tutto, quando è stato aggiornato, errori, foto e confronto tra probabilità previste e giocatori che hanno giocato.
async function apriStatoDati() {
  apriFoglio(`<div class="caricamento">${t("scambio.controllo_dati")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const s = await api("/api/stato-dati");
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const nomiFonte = { aggiornamento: t("sd.f_aggiornamento"), listone: t("sd.f_listone"), voti: t("sd.f_voti"), probabili: t("sd.f_probabili"),
      calendario: t("sd.f_calendario"), understat: t("sd.f_understat") };
    const agg = s.aggiornamenti.length ? s.aggiornamenti.map(a => `<div class="riga"><span>${esc(nomiFonte[a.cosa] || nomiFonte[a.cosa.split(" ")[0]] || a.cosa)}</span>
      <span class="debole piccolo">${a.quando ? esc(quando(a.quando)) : t("sd.mai")}</span></div>
      ${a.errori.map(e => `<div class="debole piccolo" style="color:var(--rosso)">${esc(e)}</div>`).join("")}`).join("") : `<div class="debole">${t("scambio.nessun_aggiornamento_registr")}</div>`;
    const c = s.calibrazione;
    const gruppi = c.gruppi.map(g => `<div class="riga"><span>${esc(g.gruppo)}</span>
      <span class="debole piccolo">${g.n ? `${tp("sd.n_giocatori", g.n)} · ${t("sd.hanno_giocato", { o: perc(g.osservato), p: perc(g.previsto) })}${g.indicativo ? t("sd.pochi_dati") : ""}${c.fattori && c.fattori[g.gruppo] ? ` · ${t("sd.correzione", { f: fNum(c.fattori[g.gruppo], { maximumFractionDigits: 3 }) })}` : ""}` : t("sd.nessun_dato")}</span></div>`).join("");
    apriFoglio(`
      <h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("av.stato")}</h2>
      <div class="debole piccolo">${t("sd.riepilogo", { s: esc(s.stagione), g: s.partite.giocate, tot: s.partite.totali, v: s.voti, c: s.calciatori, f: s.foto })}</div>
      <div class="carta" style="margin-top:12px"><h2>${t("scambio.ultimi_aggiornamenti")}</h2>${agg}</div>
      <div class="carta" id="fonti-dati"><h2>${t("scambio.fonti_dei_dati")}</h2>
        ${(s.fonti || []).map(f => `<div class="riga"><span>${esc(f.nome)}</span>
          <button class="bottone secondario piccolo" data-fonte="${esc(f.id)}" data-acceso="${f.acceso ? "1" : "0"}">${t(f.acceso ? "sd.accesa_spegni" : "sd.spenta_accendi")}</button></div>
          ${f.acceso ? "" : `<div class="debole piccolo">${esc(f.messaggio || "")}</div>`}`).join("")}
        <div class="debole piccolo">${t("scambio.accendere_una_fonte")}</div></div>
      ${s.uso ? `<div class="carta" id="uso-app"><h2>${t("scambio.quanto_usa_app")}</h2>
        <div class="debole piccolo">${t("sd.uso_spiega", { dal: s.uso.dal ? ` (${t("sd.dal", { d: esc(fData(new Date(s.uso.dal + "T12:00:00"), {})) })})` : "", n: tp("sd.n_richieste", s.uso.richieste || 0) })}</div>
        ${(s.uso.per_funzione || []).length ? (s.uso.per_funzione).map(f => `<div class="riga"><span>${esc(f.funzione)}</span><span class="debole piccolo">${tp("sd.n_volte", f.richieste)}</span></div>`).join("") : `<div class="debole">${t("scambio.ancora_nessuna_funzione")}</div>`}
        <details><summary class="debole piccolo">${t("scambio.schermate_piu_usate")}</summary>
          ${(s.uso.per_rotta || []).slice(0, 15).map(r => `<div class="riga"><span class="piccolo">${esc(r.rotta)}</span><span class="debole piccolo">${tp("sd.n_volte", r.richieste)}</span></div>`).join("")}</details></div>` : ""}
      <div class="carta"><h2>${t("scambio.date_delle_coppe")}</h2>
        <div class="debole piccolo">${t("sd.coppe_spiega", { d: esc(fData(new Date(s.coppe_fino + "T12:00:00"), {})) })}${new Date(s.coppe_fino) < new Date() ? ` — <b style="color:var(--arancio)">${t("scambio.scadute_vanno_inserite")}</b>` : ""}.</div></div>
      <div class="carta"><h2>${t("scambio.probabili_formazioni_raccolt")}</h2>
        ${s.probabili.length ? s.probabili.map(p => `<div class="riga"><span>${t("testata.giornata", { n: p.giornata })}</span><span class="debole piccolo">${tp("sd.n_giocatori", p.giocatori)} · ${p.rilevato ? esc(quando(p.rilevato)) : ""}</span></div>`).join("") : `<div class="debole">${t("scambio.ancora_nessuna")}</div>`}</div>
      <div class="carta"><h2>${t("scambio.controlli_sui_dati")}</h2>
        ${(s.controlli || []).length ? s.controlli.filter(k => !(k.nome.startsWith("sentinella_") && k.esito === "ok")).map(k => `<div class="riga"><span>${esc(nomeControllo(k.nome))}</span><span class="piccolo" style="color:${k.esito === "ok" ? "var(--verde)" : k.esito === "errore" ? "var(--rosso)" : "var(--arancio)"}">${t(k.esito === "ok" ? "sd.a_posto" : k.esito === "errore" ? "sd.errore" : "sd.da_guardare")}</span></div>
          ${k.esito === "ok" ? "" : `<div class="debole piccolo">${esc(k.dettaglio || "")}</div>`}`).join("") : `<div class="debole">${t("scambio.fanno_ogni_aggiornamento")}</div>`}</div>
      <div class="carta" id="affidabilita"><h2>${t("scambio.quanto_affidabile_modello")}</h2><div class="caricamento" style="padding:8px 0">${t("comune.carico")}</div></div>
      ${cartaRegistro(s.registro)}
      <div class="carta"><h2>${t("scambio.quanto_azzecca_modello")}</h2>
        <div class="debole piccolo">${c.giornate ? t("sd.giornate_giocate", { n: c.giornate }) : t("sd.appena_finisce")}
          ${t("sd.corregge")}</div>
        ${gruppi}</div>`);
    document.querySelectorAll("#fonti-dati button[data-fonte]").forEach(bt => bt.addEventListener("click", async () => {
      try {
        await api("/api/admin/fonti", { method: "PUT", body: JSON.stringify({ fonte: bt.dataset.fonte, acceso: bt.dataset.acceso !== "1" }) });
        apriStatoDati();
      } catch (e) { avviso(t("scambio.non_sono_riuscito")); }
    }));
    mostraAffidabilita(numero);
  } catch (e) {
    if (numero === ultimaScheda && !$("#foglio").hidden) apriFoglio(errore(e));
  }
}

// Aspetto: tema (automatico, chiaro, scuro) e dimensione del testo, ricordati su questo telefono.
const ASPETTO = { tema: ["auto", "chiaro", "scuro"], testo: [["1", "asp.testo_normale"], ["1.12", "asp.testo_grande"], ["1.25", "asp.testo_molto"]] };
function leggiAspetto() {
  try { return { tema: localStorage.getItem("tema") || "auto", testo: localStorage.getItem("testo") || "1" }; } catch { return { tema: "auto", testo: "1" }; }
}
const pref = (k, def) => { try { return localStorage.getItem(k) || def; } catch { return def; } };
const salvaPref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* niente memoria: vale solo adesso */ } };
// Le scelte che non ci sono più (1/11/2026, come sull'iPhone): si tolgono da questo dispositivo, così nessuno resta con un colore o una densità
// che non può più cambiare. La densità è sempre compatta; il movimento ridotto lo decide il sistema («Riduci movimento»).
const PREF_TOLTE = ["accento", "densita", "animazioni", "iniziale"];
function togliPrefVecchie() { try { PREF_TOLTE.forEach(k => localStorage.removeItem(k)); } catch { /* niente memoria */ } }
function applicaAspetto() {
  const a = leggiAspetto(), radice = document.documentElement;
  if (a.tema === "auto") delete radice.dataset.tema; else radice.dataset.tema = a.tema;
  const scuro = a.tema === "scuro" || (a.tema === "auto" && !matchMedia("(prefers-color-scheme: light)").matches);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = scuro ? "#07100b" : "#eaf3ee";
  document.documentElement.style.zoom = a.testo === "1" ? "" : a.testo;      // vale per tutta l'app: testata, barra e pannelli compresi
  radice.dataset.densita = "compatta";
  segnaMovimento();
}
function schedaAspetto() {
  const a = leggiAspetto();
  const NOMI_TEMA = { auto: t("asp.tema_auto"), chiaro: t("asp.tema_chiaro"), scuro: t("asp.tema_scuro") };
  const lingue = `<div class="segmenti" style="margin:6px 0 14px" role="group" aria-label="${t("asp.lingua")}">${Object.keys(LINGUE).map(l =>
    `<button data-lingua="${l}" lang="${l}" class="${LINGUA === l ? "attivo" : ""}">${t("lingua." + l)}</button>`).join("")}</div>`;
  const seg = (chiave, valore, opzioni) => `<div class="segmenti" style="margin:6px 0 14px">${opzioni.map(([v, n]) =>
    `<button data-pref="${chiave}" data-valore="${v}" class="${String(valore) === String(v) ? "attivo" : ""}">${n.startsWith("asp.") ? t(n) : n}</button>`).join("")}</div>`;
  // Come sull'iPhone: lingua, tema e dimensione del testo. Niente colori, densità o icone diverse.
  return `<div id="aspetto"><div class="carta"><h3>${t("asp.lingua")}</h3>${lingue}</div>
  <div class="carta"><h3>${t("asp.tema")}</h3>${seg("tema", a.tema, ASPETTO.tema.map(k => [k, NOMI_TEMA[k]]))}
    <div class="debole piccolo">${t("asp.auto_spiega")}</div>
    <h3>${t("asp.testo")}</h3>${seg("testo", a.testo, ASPETTO.testo)}</div></div>`;
}
function collegaAspetto() {
  document.querySelectorAll("#aspetto [data-lingua]").forEach(b => b.addEventListener("click", () => {
    if (b.dataset.lingua !== LINGUA) scegliLingua(b.dataset.lingua, stato.account && stato.account.nome_utente);        // ricarica la pagina nella lingua scelta
  }));
  document.querySelectorAll("#aspetto [data-pref]").forEach(b => b.addEventListener("click", () => {
    salvaPref(b.dataset.pref, b.dataset.valore);
    applicaAspetto();
    document.querySelectorAll(`#aspetto [data-pref="${b.dataset.pref}"]`).forEach(x => x.classList.toggle("attivo", x === b));
  }));
}

// Ricerca veloce di un giocatore da qualsiasi schermata (la lente in alto).
function apriRicerca() {
  apriFoglio(`<h2 style="margin:0 0 10px;font-size:var(--t-card)">${t("shell.cerca")}</h2>
    <input class="campo-testo" id="ricerca-veloce" type="search" placeholder="${t("avv.nome_del_giocatore")}" autocomplete="off" autocapitalize="off" spellcheck="false">
    <div class="risultati-ricerca" id="risultati-ricerca"><div class="debole piccolo">${t("avv.scrivi_almeno_due")}</div></div>`);
  const campo = $("#ricerca-veloce");
  setTimeout(() => campo.focus(), 300);
  setTimeout(() => caricaListoneCerca().catch(() => {}), 350);
  let n = 0;
  campo.addEventListener("input", async () => {
    const q = campo.value.trim(), mio = ++n, dove = $("#risultati-ricerca");
    if (!dove) return;
    if (q.length < 2) { dove.innerHTML = `<div class="debole piccolo">${t("avv.scrivi_almeno_due")}</div>`; return; }
    try {
      const r = await cercaGiocatori(q, 12);
      if (mio !== n || !$("#risultati-ricerca")) return;
      dove.innerHTML = r.length ? `<ul class="elenco">${r.map(x => `<li><button class="voce" data-giocatore="${x.id}" style="grid-template-columns:1fr auto">
        <span><span class="nome">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span><span class="dettaglio" style="display:block">${esc(x.squadra)}</span></span>
        <span class="debole piccolo">${t("avv.quot", { n: x.quotazione })}</span></button></li>`).join("")}</ul>` : `<div class="debole">${t("avv.nessun_giocatore_trovato")}</div>`;
    } catch (e) { if (e.name !== "AbortError" && mio === n && $("#risultati-ricerca")) $("#risultati-ricerca").innerHTML = errore(e); }
  });
}
$("#bottone-cerca").addEventListener("click", apriRicerca);

// La formazione come immagine da mandare nel gruppo (nell'iPhone si apre il menu Condividi).
const caricaSvg = svg => new Promise(ok => {         // l'SVG diventa un'immagine per il disegno (data: è permesso dalla CSP)
  const img = new Image();
  img.onload = () => ok(img); img.onerror = () => ok(null);
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.replace("<svg ", '<svg width="240" height="240" '));
});
// Numeri con la virgola in italiano, con il punto nelle altre lingue.
const virgola = x => (LINGUA === "it" ? String(x).replace(".", ",") : String(x));
async function condividiImmagine(f, m) {
  const L = 1080, A = 1350, c = document.createElement("canvas");
  c.width = L; c.height = A;
  const g = c.getContext("2d");
  const sfondo = g.createLinearGradient(0, 0, 0, A);
  sfondo.addColorStop(0, "#0d2417"); sfondo.addColorStop(1, "#07100b");
  g.fillStyle = sfondo; g.fillRect(0, 0, L, A);
  g.textAlign = "center";
  g.fillStyle = "#eef6f0"; g.font = "700 64px -apple-system, Helvetica, Arial, sans-serif";
  g.fillText(`${t("testata.giornata", { n: f.giornata_lega || f.giornata })} · ${m.modulo}`, L / 2, 110);
  g.fillStyle = "#bccdc2"; g.font = "500 36px -apple-system, Helvetica, Arial, sans-serif";
  g.fillText(`${f.squadra} · ${t("avv.img_punti", { n: num(m.punteggio_atteso) })}`, L / 2, 168);
  const x0 = 50, y0 = 220, w = L - 100, h = 880;
  g.fillStyle = "#1f8a4b"; g.beginPath(); g.roundRect(x0, y0, w, h, 36); g.fill();
  g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 4;
  g.strokeRect(x0 + 30, y0 + 30, w - 60, h - 60);
  g.beginPath(); g.moveTo(x0 + 30, y0 + h / 2); g.lineTo(x0 + w - 30, y0 + h / 2); g.stroke();
  g.beginPath(); g.arc(L / 2, y0 + h / 2, 90, 0, Math.PI * 2); g.stroke();
  const colore = { P: "#f2c14e", D: "#4cc9f0", C: "#3ddc97", A: "#ff6b6b" };
  const sch = id => f.schede[String(id)];
  const righe = ["P", "D", "C", "A"].map(r => m.titolari.map(sch).filter(x => x.ruolo === r));
  // i volti illustrati (SVG) si caricano come immagini prima di disegnare; se uno non parte resta solo l'anello del ruolo
  const volti = new Map();
  await Promise.all(m.titolari.map(sch).map(async x => volti.set(x, await caricaSvg(svgAvatar(x)))));
  righe.forEach((riga, k) => {
    const y = y0 + h * [0.12, 0.37, 0.63, 0.88][k];
    riga.forEach((x, i) => {
      const cx = x0 + w * (i + 1) / (riga.length + 1);
      g.fillStyle = colore[x.ruolo]; g.beginPath(); g.arc(cx, y, 52, 0, Math.PI * 2); g.fill();          // anello del ruolo
      g.save(); g.beginPath(); g.arc(cx, y, 47, 0, Math.PI * 2); g.clip();
      if (volti.get(x)) g.drawImage(volti.get(x), cx - 47, y - 47, 94, 94);
      g.restore();
      g.fillStyle = "rgba(8,14,10,.92)"; g.beginPath(); g.roundRect(cx - 42, y + 34, 84, 38, 19); g.fill();   // fantavoto atteso
      g.fillStyle = "#ffffff"; g.font = "700 28px -apple-system, Helvetica, Arial, sans-serif";
      g.fillText(num(x.fv_atteso), cx, y + 62);
      g.font = "650 30px -apple-system, Helvetica, Arial, sans-serif";
      g.fillText(cognome(x), cx, y + 104);
    });
  });
  g.fillStyle = "#bccdc2"; g.font = "500 32px -apple-system, Helvetica, Arial, sans-serif";
  const pan = t("scambi.panchina") + ": " + m.panchina.map(sch).map(cognome).join(", ");
  const parole = pan.split(" "), righePan = [""];
  parole.forEach(p => { const ultima = righePan[righePan.length - 1]; if (g.measureText(ultima + " " + p).width > L - 120) righePan.push(p); else righePan[righePan.length - 1] = (ultima + " " + p).trim(); });
  righePan.slice(0, 3).forEach((r, i) => g.fillText(r, L / 2, 1160 + i * 44));
  g.fillStyle = "#3ddc97"; g.font = "600 28px -apple-system, Helvetica, Arial, sans-serif";
  g.fillText(t("avv.img_numero"), L / 2, 1316);
  const blob = await new Promise(r => c.toBlob(r, "image/png"));
  if (!blob) { avviso(t("formazione.non_riesco_creare")); return; }
  const file = new File([blob], `formazione-giornata-${f.giornata_lega || f.giornata}.png`, { type: "image/png" });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], title: t("avv.img_titolo", { n: f.giornata_lega || f.giornata }) }); return; }
    catch (e) { if (e && e.name === "AbortError") return; }
  }
  apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("nav.formazione")}</h2>
    <div class="debole piccolo">${t("avv.tieni_premuto_sull")}</div>
    <img class="immagine-condivisa" alt="${t("avv.formazione_della_giornata")}" src="${URL.createObjectURL(blob)}">`);
}

// Diario > «Quanto ci abbiamo preso» (campo `precisione` di /api/diario, fanta/precisione.py): quattro numeri con una frase,
// l'andamento giornata per giornata e l'avviso se i dati sono pochi. Tutto viene dal server; si mostra anche quando va male.
// Solo numeri dal server (passati da Number), niente testo dell'utente: nessun esc() necessario, ma niente innerHTML con dati liberi.
function cartaPrecisione(p) {
  if (!p || !p.giornate) return "";
  const n = x => (x == null || !isFinite(Number(x)) ? null : Number(x));
  const v = x => (n(x) == null ? "–" : virgola(n(x).toFixed(1)));
  const suDieci = pct => Math.round((n(pct) || 0) / 10);
  const pg = p.per_giornata || [];
  const nomeG = g => n(g.giornata_lega) ?? n(g.giornata);
  const voce = (numero, etichetta, frase, cls = "") => `<div class="qp-voce"><b class="qp-num ${cls}">${numero}</b><span class="qp-eti">${etichetta}</span><div class="qp-frase">${frase}</div></div>`;
  // 1. fantavoto atteso dei tuoi giocatori
  const fv = p.fantavoto;
  const sc = fv ? n(fv.scostamento) : null;
  const fvFrase = fv ? `${t("diario.qp_fv", { e: v(fv.errore_medio), k: suDieci(fv.entro_un_punto) })} ${tp("diario.qp_fv_voti", n(fv.voti))}${sc != null && Math.abs(sc) >= 0.3 ? " " + (sc > 0 ? t("diario.qp_fv_piu", { e: v(sc) }) : t("diario.qp_fv_meno", { e: v(-sc) })) : ""}` : t("diario.qp_fv_vuoto");
  // 2. «gioca N%»: la fascia principale e, sotto, tutte
  const gi = p.gioca, gp = gi && gi.principale != null ? gi.gruppi[gi.principale] : null;
  const giudizioFascia = g => (n(g.giocato) < n(g.detto) - 10 ? ` <span class="attenzione-testo">${t("diario.qp_gioca_ottimisti")}</span>` : n(g.giocato) > n(g.detto) + 10 ? ` <span class="debole">${t("diario.qp_gioca_prudenti")}</span>` : "");
  // con i numeri visti davvero (probabili comprese) «quando diciamo...»; con quelli ricostruiti senza probabili, una frase che lo dice
  const gArg = gp ? { p: n(gp.detto), al: alPercento(n(gp.detto)), k: suDieci(gp.giocato) } : null;
  const gFrase = gp ? `${gi.fonte === "ricostruiti" ? t("diario.qp_gioca_ric", gArg) : t("diario.qp_gioca", gArg)}${giudizioFascia(gp)}
      <details class="qp-dettagli"><summary>${t("diario.qp_gioca_tutte")}</summary><ul class="qp-fasce">${gi.gruppi.map(g => `<li>${t("diario.qp_gioca_fascia", { da: n(g.da), a: n(g.a) >= 100 ? 100 : n(g.a) - 1, d: n(g.detto), g: n(g.giocato) })} <span class="debole">(${tp("diario.qp_giocatori", n(g.giocatori))}${g.pochi ? ", " + t("diario.qp_pochi_casi") : ""})</span></li>`).join("")}</ul></details>`
    : t("diario.qp_fv_vuoto");
  // 3. consigliata contro la tua
  const cf = p.confronto || {};
  const punti = n(cf.punti);
  const cfFrase = cf.giornate ? `${t("diario.qp_cf", { k: n(cf.meglio_consigliata), n: n(cf.giornate), tua: n(cf.meglio_tua), pari: n(cf.pari) })} ${punti === 0 ? t("diario.qp_cf_pari") : punti > 0 ? tp("diario.qp_cf_piu", punti, { e: v(punti) }) : tp("diario.qp_cf_meno", -punti, { e: v(-punti) })}`
    : t("diario.qp_cf_vuoto");
  // 4. punti della squadra (consigliata): previsti contro fatti
  const sq = p.squadra;
  const sqFrase = sq ? t("diario.qp_sq", { a: v(sq.punti_medi_attesi), f: v(sq.punti_medi_fatti), k: n(sq.dentro_fascia), n: n(sq.con_fascia ?? sq.giornate), d: Math.round((n(sq.fascia_dichiarata) || 80) / 10) }) : t("diario.qp_fv_vuoto");
  // andamento: barre dell'errore del fantavoto atteso, una per giornata (più bassa = meglio), ultime 12
  const conErr = pg.filter(g => n(g.errore_fantavoto) != null).slice(-12);
  let grafico = "";
  if (conErr.length >= 2) {
    const W = 300, H = 96, alto = Math.max(2.5, ...conErr.map(g => n(g.errore_fantavoto))), passo = W / conErr.length, larga = Math.min(22, passo * 0.6);
    const barre = conErr.map((g, i) => {
      const e = n(g.errore_fantavoto), h = Math.max(2, e / alto * (H - 34)), x = i * passo + (passo - larga) / 2, y = H - 16 - h;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${larga.toFixed(1)}" height="${h.toFixed(1)}" rx="3" class="qp-barra"/>
        <text x="${(x + larga / 2).toFixed(1)}" y="${(y - 4).toFixed(1)}" text-anchor="middle" class="qp-val">${v(e)}</text>
        <text x="${(x + larga / 2).toFixed(1)}" y="${H - 3}" text-anchor="middle" class="qp-g">${nomeG(g)}</text>`;
    }).join("");
    grafico = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${t("diario.qp_grafico_aria")}" class="qp-grafico">${barre}</svg>
      <div class="debole piccolo">${t("diario.qp_grafico_leg")}</div>`;
  }
  const righe = [...pg].reverse().map(g => {
    const d = n(g.differenza);
    const tua = n(g.tua) != null ? " · " + t("diario.qp_riga_tua", { t: v(g.tua), d: (d > 0 ? "+" : d < 0 ? "−" : "") + v(Math.abs(d ?? 0)) }) : "";
    return `<li><b>${t("testata.giornata", { n: nomeG(g) })}</b> · <span class="debole">${n(g.errore_fantavoto) != null ? t("diario.qp_riga_fv", { e: v(g.errore_fantavoto) }) + " · " : ""}${t("diario.qp_riga_sq", { a: v(g.attesi), f: v(g.fatti) })}${tua}</span></li>`;
  }).join("");
  const primo = pg.length ? nomeG(pg[0]) : null, ultimo = pg.length ? nomeG(pg[pg.length - 1]) : null;
  const ric = n((p.fonti || {}).ricostruiti) || 0;
  return `<div class="carta qp"><h2>${t("diario.af_titolo")}</h2>
    <div class="debole piccolo">${t("diario.qp_intro")} ${tp("diario.qp_su", n(p.giornate), { da: primo, a: ultimo })}</div>
    ${p.pochi_dati ? `<div class="attenzione qp-pochi" role="status">${t("diario.qp_pochi", { n: n(p.giornate_minime) || 8 })}</div>` : ""}
    <div class="qp-griglia">
      ${voce(fv ? v(fv.errore_medio) : "–", t("diario.qp_fv_eti"), fvFrase)}
      ${voce(gp ? t("diario.qp_su_dieci", { k: suDieci(gp.giocato) }) : "–", t("diario.qp_gioca_eti"), gFrase, gp && n(gp.giocato) < n(gp.detto) - 10 ? "attenzione-testo" : "")}
      ${voce(cf.giornate ? t("diario.qp_k_su_n", { k: n(cf.meglio_consigliata), n: n(cf.giornate) }) : "–", t("diario.qp_cf_eti"), cfFrase)}
      ${voce(sq ? v(sq.scarto_medio) : "–", t("diario.qp_sq_eti"), sqFrase)}
    </div>
    ${grafico}
    ${righe ? `<details class="qp-dettagli"><summary>${t("diario.qp_andamento")}</summary><ul class="qp-giornate">${righe}</ul></details>` : ""}
    ${ric ? `<div class="debole piccolo qp-nota">${tp("diario.qp_ricostruiti", ric, { t: n(p.giornate) })}</div>` : ""}</div>`;
}

// Diario > «Quando hai scelto diversamente»: nelle giornate in cui i tuoi undici non erano quelli consigliati, chi ha fatto più punti.
function cartaScelteTue(st, sintesi, v) {
  if (!st || !sintesi || !sintesi.giornate) return "";
  if (!st.giornate) return `<div class="carta scelte-tue"><h2>${t("avv.tue_scelte")}</h2><div class="debole piccolo">${t("avv.finora_hai_schierato")}</div></div>`;
  const segno = x => (x > 0 ? "+" : x < 0 ? "−" : "") + v(Math.abs(x));
    const dueNomi = l => l.map(esc).join(", ");
  const riga = g => `<li>${t("avv.riga_scelta", { n: `<b>${t("testata.giornata", { n: Number(g.giornata_lega || g.giornata) })}</b>`, scelto: dueNomi(g.hai_scelto), cons: dueNomi(g.consigliava) })}
      <span class="debole piccolo">${t("avv.tu_consiglio", { tua: v(g.punti_tua), cons: v(g.punti_consigliata), d: segno(g.differenza) })}</span></li>`;
  const punti = st.punti_differenza;
  const totale = punti === 0 ? t("avv.totale_pari") : punti > 0 ? t("avv.totale_tue", { n: v(punti) }) : t("avv.totale_consiglio", { n: v(-punti) });
  const prime = st.per_giornata.slice(0, 5), altre = st.per_giornata.slice(5);
  return `<div class="carta scelte-tue"><h2>${t("avv.tue_scelte")}</h2>
    <div class="debole piccolo">${tp("avv.n_diverse", st.giornate)}</div>
    <div class="stat-fila"><div><b>${st.meglio_tua}</b><span>${t("avv.meglio_tue")}</span></div><div><b>${st.meglio_consigliata}</b><span>${t("avv.meglio_consiglio")}</span></div>
      <div><b>${st.pari}</b><span>${t("mercato.pari")}</span></div></div>
    <div>${totale} ${st.pochi_dati ? t("avv.pochi_dati") : t("avv.piu_punti_tu", { p: st.percentuale_tua })}</div>
    <ul class="elenco-scelte">${prime.map(riga).join("")}</ul>
    ${altre.length ? `<details><summary>${tp("avv.altre_giornate", altre.length)}</summary><ul class="elenco-scelte">${altre.map(riga).join("")}</ul></details>` : ""}</div>`;
}

// Diario delle giornate: formazione schierata contro consigliata, con i punti attesi e quelli fatti.
// Una voce è stagione + giornata: con due stagioni nel diario la giornata 10 c'è due volte (#176). Nell'id solo cifre e trattini.
const idVoceDiario = g => `diario-${String(g.stagione ?? "").replace(/[^0-9-]/g, "")}-g${Number(g.giornata)}`;
// «Ho schierato…» per una voce del diario: sempre con la sua stagione (il server rifiuta quelle passate, senza scrivere sulla giornata di quest'anno)
const corpoSchierata = (g, tipo, titolari) => JSON.stringify({ giornata: Number(g.giornata), tipo, ...(titolari ? { titolari } : {}), stagione: g.stagione });

// Dal «Da fare» di Oggi: il tocco su «Ho schierato la consigliata» salva subito la scelta e apre il Diario su quella giornata.
// La voce di «Da fare» ha solo la giornata ed è sempre della stagione in corso: senza `stagione` il server usa quella.
async function schieraDaOggi(giornata) {
  apriFoglio(`<div class="caricamento">${t("avv.segno_tua_formazione")}</div>`);
  try {
    await api("/api/diario/schierata", { method: "POST", body: JSON.stringify({ giornata: Number(giornata), tipo: "consigliata" }) });
    avviso(t("diario.salvata"));
  } catch (e) { avviso(e.message, 6000); }
  apriDiario(giornata);
}

// `giornata` (e `stagione`, se c'è): la voce da mostrare. Senza stagione vale la più recente con quel numero (Oggi e «Da fare» parlano della stagione in corso).
async function apriDiario(giornata, stagione) {
  apriFoglio(`<div class="caricamento">${t("avv.carico_diario")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const d = await api("/api/diario");
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const v = x => num(x, 1), s = d.sintesi;          // punti sempre con un decimale: «48,0», non «48»
    const ORDINE_RUOLI = { P: 0, D: 1, C: 2, A: 3 };
    // Un elenco di titolari per ruolo; chi non c'è nell'altra formazione è evidenziato. Dentro il nome solo testo (esc).
    const elencoFormazione = (titolari, altri, panchina) => `<ul class="diario-lista">${[...titolari].sort((a, b) => (ORDINE_RUOLI[a.ruolo] ?? 9) - (ORDINE_RUOLI[b.ruolo] ?? 9))
      .map(p => `<li${altri && !altri.has(p.id) ? ' class="diario-diverso"' : ""}><span class="diario-ruolo">${esc(p.ruolo)}</span> ${esc(p.nome)}</li>`).join("")}</ul>
      ${panchina && panchina.length ? `<div class="debole piccolo diario-panchina">${t("diario.panchina")}: ${panchina.map(p => esc(p.nome)).join(", ")}</div>` : ""}`;
    const quandoCalcolata = c => { const d = new Date(c); return isNaN(d) ? "" : fDataOra(d); };
    // la riga «previsti tra X e Y» di ogni giornata; il riassunto «Quanto ci abbiamo preso» sta in cartaPrecisione (dati dal server)
    const meno = x => segno(x, 1);                     // fatti meno estremo della fascia: arrotondato (prima «+1,7999999999999972»)
    const rigaFascia = g => {
      const r = g.atteso_vs_fatto;
      if (!r || !r.intervallo) return "";
      const a = v(r.intervallo.basso), b = v(r.intervallo.alto);
      const testo = r.nella_fascia ? t("diario.af_dentro", { a, b })
        : r.fatti < r.intervallo.basso ? t("diario.af_sotto_fascia", { a, b, d: meno(r.fatti - r.intervallo.basso) }) : t("diario.af_sopra_fascia", { a, b, d: meno(r.fatti - r.intervallo.alto) });
      return `<div class="debole piccolo af-fascia ${r.nella_fascia ? "dentro" : "fuori"}">${testo}</div>`;
    };
    const righePunti = (etichetta, r) => `<div class="riga"><span>${etichetta}</span><span><b>${v(r.reale)}</b> <span class="debole piccolo">${t("avv.attesi", { n: v(r.atteso) })}</span></span></div>`;
    const confronto = g => {
      const ist = g.istantanea, cons = ist || g.consigliata;                      // la consigliata di allora, o (se non registrata) la ricostruzione di oggi
      const idCons = new Set(cons.titolari.map(p => p.id));
      const idTue = g.schierata ? new Set(g.schierata.titolari.map(p => p.id)) : null;
      const titoloCons = ist ? t("diario.consigliava", { modulo: esc(ist.modulo) }) : t("diario.ricostruita", { modulo: esc(cons.modulo) });
      const sotto = ist ? `<div class="debole piccolo">${t("diario.consigliava_il", { quando: esc(quandoCalcolata(ist.calcolata)) })}${ist.stile ? " · " + esc(ist.stile) : ""}</div>` : `<div class="debole piccolo">${t("diario.non_registrata")}</div>`;
      const colCons = `<div class="diario-col"><h3>${titoloCons}</h3>${sotto}${elencoFormazione(cons.titolari, idTue, ist && ist.panchina)}</div>`;
      if (!g.schierata) return `<div class="diario-conf una">${colCons}</div>
        ${g.modificabile === false ? "" : `<div class="pulsanti"><button class="bottone" data-schierata="${idVoceDiario(g)}">${t("diario.ho_schierato_questa")}</button></div>`}`;
      const fuori = g.schierata.titolari.filter(p => !idCons.has(p.id)).map(p => p.nome), dentro = cons.titolari.filter(p => !idTue.has(p.id)).map(p => p.nome);
      const colTue = `<div class="diario-col"><h3>${t("diario.hai_schierato", { modulo: esc(g.schierata.modulo) })}</h3>${elencoFormazione(g.schierata.titolari, idCons)}</div>`;
      return `<div class="diario-conf">${colCons}${colTue}</div>
        <div class="debole piccolo">${fuori.length ? t("diario.cambiato", { n: fuori.length, nomi: t("diario.cambiato_nomi", { dentro: esc(fuori.join(", ")), fuori: esc(dentro.join(", ")) }) }) : t("diario.uguale")}</div>`;
    };
    // «Ho schierato…» e «Correggi» solo se la voce si può ancora cambiare (stagione in corso; un server vecchio senza il campo: sì)
    const righe = d.giornate.map(g => `<div class="carta" id="${idVoceDiario(g)}"><div class="riga"><h2 style="margin:0">${t("testata.giornata", { n: g.giornata_lega || g.giornata })}</h2><span class="debole piccolo">${esc(g.stagione)}</span></div>
      ${g.schierata ? "" : `<div class="debole piccolo">${t("diario.non_salvata")}</div>`}
      ${confronto(g)}
      ${g.modificabile === false ? "" : `<div class="pulsanti"><button class="bottone secondario" data-correggi="${idVoceDiario(g)}">${g.schierata ? t("diario.correggi") : t("diario.ho_schierato_altra")}</button></div>`}
      ${g.schierata ? righePunti(g.schierata.tipo === "consigliata" ? t("diario.tua_consigliata", { modulo: esc(g.schierata.modulo) }) : t("diario.tua", { modulo: esc(g.schierata.modulo) }), g.schierata)
        : g.automatica ? righePunti(t("diario.automatica", { modulo: esc(g.automatica.modulo) }), g.automatica) : ""}
      ${righePunti(g.istantanea ? t("diario.ricostruita", { modulo: esc(g.consigliata.modulo) }) : t("avv.del_modello", { modulo: esc(g.consigliata.modulo) }), g.consigliata)}
      ${rigaFascia(g)}</div>`).join("");
    apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("avv.diario_delle_giornate")}</h2>
      <div class="debole piccolo">${t("avv.diario_riga")}</div>
      <details class="come-diario"><summary>${t("mercato.come_legge")}</summary><div class="debole piccolo">${t("avv.per_ogni_giornata")}</div></details>
      ${cartaPrecisione(d.precisione)}
      ${cartaScelteTue(d.scelte_tue, s, v)}
      ${righe || `<div class="carta" style="margin-top:12px"><div class="debole">${t("diario.vuoto_" + d.motivo_vuoto) !== "diario.vuoto_" + d.motivo_vuoto ? t("diario.vuoto_" + d.motivo_vuoto) : t("diario.vuoto")}</div></div>`}`);
    const voceDi = id => d.giornate.find(x => idVoceDiario(x) === id);
    const daMostrare = giornata == null ? null : d.giornate.find(x => Number(x.giornata) === Number(giornata) && (stagione == null || x.stagione === stagione));
    if (daMostrare) { const el = document.getElementById(idVoceDiario(daMostrare)); if (el) el.scrollIntoView({ block: "start" }); }
    $("#foglio").querySelectorAll("[data-correggi]").forEach(bt => bt.addEventListener("click", () => {
      const g = voceDi(bt.dataset.correggi);
      if (g) correggiDiario(g);
    }));
    $("#foglio").querySelectorAll("[data-schierata]").forEach(b => b.addEventListener("click", async () => {
      const g = voceDi(b.dataset.schierata);
      if (!g) return;
      b.disabled = true;
      try {
        await api("/api/diario/schierata", { method: "POST", body: corpoSchierata(g, "consigliata") });
        avviso(t("diario.salvata"));
        apriDiario(g.giornata, g.stagione);
      } catch (e) { b.disabled = false; avviso(e.message, 6000); }
    }));
  } catch (e) { if (numero === ultimaScheda && !$("#foglio").hidden) apriFoglio(errore(e)); }
}

// Diario: scegli a mano gli undici che hai schierato in una giornata finita (come sull'iPhone). Si parte da quelli già salvati o, in mancanza, dalla consigliata;
// il server controlla che siano undici della tua rosa con un modulo valido.
async function correggiDiario(g) {
  apriFoglio(`<div class="caricamento">${t("scambio.carico_rosa")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const r = await api("/api/rosa");
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const iniziali = new Set((((g.schierata || g.consigliata) || {}).titolari || []).map(p => p.id));
    const reparti = ["P", "D", "C", "A"].map(r => [r, NOMI_RUOLO[r]]);
    const gruppi = reparti.map(([ruolo, nome]) => {
      const giocatori = r.giocatori.filter(x => x.ruolo === ruolo && x.id);
      return giocatori.length ? `<h3>${nome}</h3>${giocatori.map(x => `<label class="interruttore"><span>${badgeRuolo(x.ruolo, true)}${esc(x.nome)} <span class="debole piccolo">${sigla(x.squadra)}</span></span>
        <input type="checkbox" data-scelto="${Number(x.id)}" ${iniziali.has(x.id) ? "checked" : ""}></label>`).join("")}` : "";
    }).join("");
    apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("diario.cosa_hai_schierato_titolo")}</h2>
      <div class="debole piccolo">${t("diario.correggi_spiega", { giornata: g.giornata_lega || g.giornata })}</div>
      <div class="riga" style="margin:10px 0"><b id="diario-conta" role="status" aria-live="polite"></b>
        <span class="riga" style="gap:8px"><button class="bottone secondario" id="diario-annulla" type="button">${t("mercato.annulla")}</button><button class="bottone" id="diario-salva" type="button">${t("scambio.salva")}</button></span></div>
      ${gruppi}`);
    const caselle = () => [...$("#foglio").querySelectorAll("[data-scelto]")];
    const aggiorna = () => {
      const n = caselle().filter(c => c.checked).length;
      $("#diario-conta").textContent = t("avv.n_di_11", { n });
      $("#diario-conta").className = n === 11 ? "positivo" : n > 11 ? "attenzione" : "debole";
      $("#diario-salva").disabled = n !== 11;
    };
    caselle().forEach(c => c.addEventListener("change", aggiorna));
    aggiorna();
    $("#diario-annulla").addEventListener("click", () => apriDiario(g.giornata, g.stagione));
    $("#diario-salva").addEventListener("click", async () => {
      const titolari = caselle().filter(c => c.checked).map(c => Number(c.dataset.scelto));
      if (titolari.length !== 11) return;
      $("#diario-salva").disabled = true;
      try {
        await api("/api/diario/schierata", { method: "POST", body: corpoSchierata(g, "manuale", titolari) });
        avviso(t("diario.salvata_manuale"));
        apriDiario(g.giornata, g.stagione);
      } catch (e) { $("#diario-salva").disabled = false; avviso(e.message, 6000); }
    });
  } catch (e) { if (numero === ultimaScheda && !$("#foglio").hidden) apriFoglio(errore(e)); }
}

// Prova del modello sulle ultime giornate giocate: errore sui fantavoti e punti delle formazioni, con il confronto "da fantamedia".
async function mostraAffidabilita(numero) {
  const dove = $("#affidabilita");
  if (!dove) return;
  try {
    const a = await api("/api/affidabilita");
    if (numero !== ultimaScheda || !document.body.contains(dove)) return;
    const s = a.sintesi, righe = (a.righe || []).filter(r => r.punti_modello != null);
    if (!s || !s.giornate) { dove.innerHTML = `<h2>${t("scambio.quanto_affidabile_modello")}</h2><div class="debole piccolo">${t("avv.prova_sola_dopo")}</div>`; return; }
    const v = x => (x == null ? "–" : virgola(x));
    let grafico = "";
    if (righe.length >= 2) {
      const W = 300, H = 110, P = 8, tutti = righe.flatMap(r => [r.punti_modello, r.punti_fantamedia, r.punti_perfetta]).filter(x => x != null);
      const min = Math.min(...tutti) - 2, max = Math.max(...tutti) + 2;
      const xy = (i, y) => `${(P + i * (W - 2 * P) / (righe.length - 1)).toFixed(1)},${(H - P - (y - min) / (max - min) * (H - 2 * P)).toFixed(1)}`;
      const linea = (k, col, tratteggio) => `<polyline fill="none" stroke="${col}" stroke-width="2.2" ${tratteggio ? 'stroke-dasharray="4 4"' : ""} stroke-linecap="round" stroke-linejoin="round" points="${righe.map((r, i) => xy(i, r[k])).join(" ")}"/>`;
      grafico = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${t("avv.punti_delle_formazioni")}" style="margin-top:10px">
        ${linea("punti_perfetta", "var(--testo-2)", true)}${linea("punti_fantamedia", "var(--arancio)")}${linea("punti_modello", "var(--verde)")}</svg>
        <div class="debole piccolo"><b style="color:var(--verde)">—</b> ${t("avv.modello_nbsp")} <b style="color:var(--arancio)">—</b> ${t("avv.fantamedia_nbsp")} <b>- -</b> ${t("avv.max_possibile")} · ${t("avv.giornate_da_a", { a: righe[0].giornata, b: righe[righe.length - 1].giornata })}</div>`;
    }
    dove.innerHTML = `<h2>${t("scambio.quanto_affidabile_modello")}</h2>
      <div class="debole piccolo">${tp("avv.prova_su", s.giornate)}</div>
      <div class="stat-fila" style="margin-top:12px"><div><b>${v(s.errore_modello)}</b><span>${t("avv.errore_sui_fantavoti")}</span></div><div><b>${v(s.errore_fantamedia)}</b><span>${t("avv.errore_fantamedia")}</span></div>
        <div><b class="${s.punti_modello != null && s.punti_fantamedia != null && s.punti_modello >= s.punti_fantamedia ? "positivo" : ""}">${v(s.punti_modello)}</b><span>${t("avv.punti_formazione_modello")}</span></div></div>
      <div class="debole piccolo" style="margin-top:8px">${t("avv.punti_medi", { m: v(s.punti_modello), f: v(s.punti_fantamedia), p: v(s.punti_perfetta) })}
        ${t("avv.mancano_probabili")}</div>${grafico}`;
  } catch (e) { if (document.body.contains(dove)) dove.innerHTML = `<h2>${t("scambio.quanto_affidabile_modello")}</h2>${errore(e)}`; }
}

// Quando le rose sono di una stagione finita, propone di archiviarle e ripartire.

// Notifiche web: arrivano da questa app, senza ntfy. Su iPhone servono iOS 16.4 o più e l'app sulla schermata Home.
function chiaveInUint8(b64) {
  const p = "=".repeat((4 - b64.length % 4) % 4), s = atob((b64 + p).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(s, c => c.charCodeAt(0));
}
async function notificheWeb(dispositivi) {
  const dove = $("#notifiche-web");
  if (!dove) return;
  if (!("serviceWorker" in navigator && "PushManager" in window && "Notification" in window)) {
    dove.innerHTML = `<div class="debole piccolo" style="margin-top:10px">${t("avv.notifiche_dell_app")}</div>`;
    return;
  }
  // il service worker può non arrivare mai (navigazione privata, installazione fallita): senza, si dice che qui le notifiche non ci sono
  const reg = await Promise.race([navigator.serviceWorker.ready, new Promise(r => setTimeout(() => r(null), 4000))]).catch(() => null);
  if (!reg) {
    dove.innerHTML = `<div class="debole piccolo" style="margin-top:10px">${t("avv.notifiche_dell_app")}</div>`;
    return;
  }
  let sub = null;
  try { sub = await reg.pushManager.getSubscription(); } catch { /* senza service worker */ }
  const disegna = attiva => {
    dove.innerHTML = `<div class="riga" style="margin-top:12px"><span><b>${t("avv.notifiche_questa_app")}</b><span class="debole piccolo" style="display:block">${attiva
      ? t("avv.attive_qui") + (dispositivi > 1 ? t("avv.in_tutto", { n: dispositivi }) : "") + (stato.account ? "." : t("avv.non_piu_ntfy"))
      : t(stato.account ? "avv.attivale" : "avv.direttamente_qui")}</span></span>
      <button class="bottone ${attiva ? "secondario" : ""}" id="push-bottone">${t(attiva ? "avv.disattiva" : "avv.attiva")}</button></div>`;
    $("#push-bottone").addEventListener("click", attiva ? disattiva : attivaPush);
  };
  const attivaPush = async () => {
    try {
      if (await Notification.requestPermission() !== "granted") { avviso(t("avv.permesso_negato_abilita"), 6000); return; }
      const { chiave } = await api("/api/push/chiave");
      const reg = await navigator.serviceWorker.ready;
      sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chiaveInUint8(chiave) });
      const r = await api("/api/push/iscrivi", { method: "POST", body: JSON.stringify(sub.toJSON()) });
      dispositivi = r.dispositivi; disegna(true); avviso(t("avv.notifiche_attivate"), 5000);
    } catch (e) { avviso(e.message || t("avv.non_attivo"), 6000); }
  };
  const disattiva = async () => {
    try {
      if (sub) { const ep = sub.endpoint; await sub.unsubscribe(); const r = await api("/api/push/disiscrivi", { method: "POST", body: JSON.stringify({ endpoint: ep }) }); dispositivi = r.dispositivi; sub = null; }
      disegna(false); avviso(t("avv.notifiche_disattivate_questo"));
    } catch (e) { avviso(e.message || t("avv.non_disattivo"), 6000); }
  };
  disegna(!!sub);
}

// Avvisi sul telefono: cosa mandare, le ore tranquille e un avviso di prova.
const ORE_24 = Array.from({ length: 24 }, (_, h) => h);
async function avvisiTelefono() {
  const dove = $("#avvisi-telefono");
  if (!dove) return;
  try {
    const a = await api("/api/avvisi");
    if (!document.body.contains(dove)) return;
    const o = a.impostazioni;
    dove.innerHTML = `<h2>${t("asp.avvisi_titolo")}</h2>
      ${a.ore_tranquille_spente ? `<div class="piccolo" role="status" style="margin:8px 0;font-weight:600">${t("avv.avevi_scelto_ore")}</div>` : ""}
      <div class="debole piccolo">${t(stato.account ? "avv.arrivano_account" : "avv.arrivano_ntfy")}</div>
      ${interruttore("av_cambi", t("avv.cambi"), o.cambi, t("avv.cambi_aiuto"))}
      ${rigaRegola(t("avv.prima"), `<select class="campo-testo scelta-corta" id="av_prima" aria-label="${t("avv.prima")}">${[[0, "avv.prima_0"], [30, "avv.prima_30"], [60, "avv.prima_60"], [90, "avv.prima_90"]].map(([m, k]) => `<option value="${m}" ${m === (o.avviso_prima ?? 60) ? "selected" : ""}>${t(k)}</option>`).join("")}</select>`, t("avv.prima_aiuto"))}
      ${interruttore("av_60", t("avv.prom_60"), o.promemoria_60, t("avv.prom_60_aiuto"))}
      ${interruttore("av_15", t("avv.prom_15"), o.promemoria_15)}
      ${interruttore("av_riepilogo", t("avv.riepilogo"), o.riepilogo, t("avv.riepilogo_aiuto"))}
      ${interruttore("av_copertura", t("avv.copertura"), o.copertura, t("avv.copertura_aiuto"))}
      ${stato.account ? "" : interruttore("av_nativa", t("avv.nativa"), o.app_nativa, t("avv.nativa_aiuto"))}
      ${interruttore("av_silenzio", t("avv.ore_tranq"), o.silenzio, t("avv.ore_tranq_aiuto"))}
      <div class="riga" id="av-fascia" style="gap:10px;margin:6px 0 10px" ${o.silenzio ? "" : "hidden"}>
        <label class="debole piccolo" style="flex:1">${t("avv.dalle")}<select class="campo-testo" id="av_da" aria-label="${t("avv.inizio_delle_ore")}">${ORE_24.map(h => `<option value="${h}" ${h === o.silenzio_da ? "selected" : ""}>${String(h).padStart(2, "0")}:00</option>`).join("")}</select></label>
        <label class="debole piccolo" style="flex:1">${t("avv.alle")}<select class="campo-testo" id="av_a" aria-label="${t("avv.fine_delle_ore")}">${ORE_24.map(h => `<option value="${h}" ${h === o.silenzio_a ? "selected" : ""}>${String(h).padStart(2, "0")}:00</option>`).join("")}</select></label>
      </div>
      <div id="notifiche-web"></div>
      <div class="pulsanti"><button class="bottone secondario" id="avviso-prova" ${a.canale ? "" : "disabled"}>${t("avv.manda_avviso_prova")}</button></div>
      ${a.canale ? "" : `<div class="debole piccolo">${t(stato.account ? "avv.attiva_sopra" : "avv.non_attivi")}</div>`}`;
    notificheWeb(a.dispositivi);
    const salva = async () => {
      try {
        $("#av-fascia").hidden = !$("#av_silenzio").checked;
        if ($("#av_silenzio").checked && $("#av_da").value === $("#av_a").value) {
          avviso(t("avv.ore_tranquille_non"), 6000);
          $("#av_da").value = String(o.silenzio_da); $("#av_a").value = String(o.silenzio_a);
          return;
        }
        const r = await api("/api/avvisi", { method: "PUT", body: JSON.stringify({ cambi: $("#av_cambi").checked, promemoria_60: $("#av_60").checked, promemoria_15: $("#av_15").checked, riepilogo: $("#av_riepilogo").checked, copertura: $("#av_copertura").checked, app_nativa: $("#av_nativa") ? $("#av_nativa").checked : undefined,
          silenzio: $("#av_silenzio").checked, silenzio_da: Number($("#av_da").value), silenzio_a: Number($("#av_a").value), avviso_prima: Number($("#av_prima").value) }) });
        if (r && r.impostazioni) Object.assign(o, r.impostazioni);          // l'ultima fascia salvata, per tornarci se la prossima è sbagliata
      } catch (e) { avviso(e.message); }
    };
    ["#av_cambi", "#av_prima", "#av_60", "#av_15", "#av_riepilogo", "#av_copertura", "#av_nativa", "#av_silenzio", "#av_da", "#av_a"].filter(id => $(id)).forEach(id => $(id).addEventListener("change", salva));
    $("#avviso-prova").addEventListener("click", async () => {
      try { const r = await api("/api/avvisi/prova", { method: "POST" }); avviso(t(r.inviato ? "avv.prova_ok" : "avv.prova_no"), 5000); }
      catch (e) { avviso(e.message, 6000); }
    });
  } catch (e) { if (document.body.contains(dove)) dove.innerHTML = `<h2>${t("asp.avvisi_titolo")}</h2>${errore(e)}`; }
}

// ---------------------------------------------------------------- stemma e maglia (Lega)
// Da file, da un indirizzo web (lo scarica il server, solo https pubblico) o dal menu Condividi del telefono (app installata).
async function chiamaImmagine(percorso, opzioni = {}) {
  let r;
  try { r = await fetch(percorso, { cache: "no-store", ...opzioni, headers: { "X-Fanta": "1", "Accept-Language": LINGUA, ...(opzioni.headers || {}) } }); }
  catch { throw new Error(t("comune.rete_no")); }
  const dati = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(traduciErrore(dati.detail) || t("lega.operazione_no"));
  return dati;
}
async function apriStemmaMaglia(nome, inAttesa = false) {
  let squadre = stato.squadre || [];
  if (!squadre.length) { await caricaSquadre(); squadre = stato.squadre || []; }
  if (!squadre.length) { avviso(t("lega.importa_prima_rose_2")); return; }
  let scelta = (squadre.find(s => s.nome === nome) || squadre.find(s => s.mia) || squadre[0]).nome;
  let attesa = null;                                    // anteprima (blob) dell'immagine arrivata da Condividi
  if (inAttesa) {
    try { const r = await fetch("/api/squadre/immagine/in-attesa", { cache: "no-store", headers: { "X-Fanta": "1" } }); if (r.ok) attesa = await r.blob(); } catch { /* niente */ }
    if (!attesa) avviso(t("lega.immagine_condivisa_non"));
  }
  const urlAttesa = attesa ? URL.createObjectURL(attesa) : null;
  const NOMI = { stemma: "stemma", maglia: "maglia" };
  const fine = async (testo, ricarica = true) => {
    stato.vImg = Date.now(); svuotaCache();
    if (ricarica) await caricaSquadre();
    avviso(testo);
    disegna();
  };
  const disegna = () => {
    squadre = stato.squadre || squadre;
    const s = squadre.find(x => x.nome === scelta) || squadre[0];
    apriFoglio(`
      <h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("lega.stemma_maglia")}</h2>
      <div class="debole piccolo">${t("lega.immagini_png_jpeg")}</div>
      <select class="campo-testo" id="sm-squadra" aria-label="${t("col.squadra")}" style="margin-top:12px">${squadre.map(x => `<option value="${esc(x.nome)}" ${x.nome === s.nome ? "selected" : ""}>${esc(x.nome)}${x.mia ? t("lega.la_tua_paren") : ""}</option>`).join("")}</select>
      ${urlAttesa ? `<div class="carta sm-attesa"><h3 style="margin-top:0">${t("lega.immagine_condivisa")}</h3>
        <div class="riga"><img class="sm-anteprima" src="${urlAttesa}" alt="${t("lega.immagine_condivisa")}">
          <div class="pulsanti"><button class="bottone" data-usa="stemma">${t("lega.usa_come_stemma")}</button><button class="bottone" data-usa="maglia">${t("lega.usa_come_maglia")}</button>
          <button class="bottone secondario" id="sm-scarta">${t("lega.scarta")}</button></div></div></div>` : ""}
      <div class="immagini-squadra">
        ${["stemma", "maglia"].map(tipo => { const c = s.immagini && s.immagini[tipo]; return `<div class="immagine-squadra">
          <b>${t(NOME_IMMAGINE[tipo])}</b>
          ${c ? `<img src="${urlImg(s.nome, tipo)}" alt="${t("lega.alt_immagine", { tipo: t(NOME_IMMAGINE[tipo]), nome: esc(s.nome) })}">` : `<span class="vuota">${t("lega.nessuna_immagine")}</span>`}
          <label class="bottone secondario sm-pulsante" for="sm-file-${tipo}">${t("lega.file_foto")}</label>
          <input id="sm-file-${tipo}" data-tipo="${tipo}" type="file" accept="image/png,image/jpeg,image/webp" hidden>
          ${funz("immagini_web") ? `<input class="campo-testo" id="sm-url-${tipo}" type="url" inputmode="url" autocomplete="off" placeholder="${t("lega.https")}" aria-label="${t("lega.indirizzo_aria", { tipo: t(NOME_IMMAGINE[tipo]).toLowerCase() })}">
          <button class="bottone secondario sm-pulsante" data-scarica="${tipo}">${t("lega.indirizzo_web")}</button>` : ""}
          ${c ? `<button class="bottone secondario sm-pulsante" data-rimuovi="${tipo}">${t("lega.rimuovi")}</button>` : ""}
        </div>`; }).join("")}
      </div>
      <details style="margin-top:12px"><summary style="font-size:var(--t-corpo)">${t("lega.come_ottenere_stemma")}</summary>
        <ol class="guida">
          <li>${t("lega.nell_app_nel")} <b>${t("lega.salva_immagine")}</b>${t("lega.poi_usa")} <b>${t("lega.file_foto")}</b>.</li>
          ${funz("immagini_web") ? `<li>${t("lega.oppure")} <b>${t("lega.condividi")}</b> ${t("lega.immagine_verso_schieraxi")}</li>
          <li>${t("lega.oppure_copia_indirizzo")}</li>` : ""}
        </ol></details>
      <div class="pulsanti"><button class="bottone secondario" id="sm-chiudi">${t("shell.chiudi")}</button></div>`);
    $("#sm-squadra").addEventListener("change", ev => { scelta = ev.target.value; disegna(); });
    $("#sm-chiudi").addEventListener("click", chiudiFoglio);
    const carica = async (tipo, blob, nomeFile) => {
      const dati = new FormData();
      dati.append("file", blob, nomeFile || "immagine");
      await chiamaImmagine(`/api/squadre/immagine?squadra=${encodeURIComponent(s.nome)}&tipo=${tipo}`, { method: "POST", body: dati });
    };
    document.querySelectorAll("#foglio input[type=file]").forEach(inp => inp.addEventListener("change", async () => {
      const file = inp.files[0]; inp.value = "";
      if (!file) return;
      try { await carica(inp.dataset.tipo, file, file.name); await fine(t(inp.dataset.tipo === "stemma" ? "scambio.stemma_aggiornato" : "scambio.maglia_aggiornata")); }
      catch (e) { avviso(e.message, 6000); }
    }));
    document.querySelectorAll("#foglio [data-scarica]").forEach(b => b.addEventListener("click", async () => {
      const tipo = b.dataset.scarica, indirizzo = $(`#sm-url-${tipo}`).value.trim();
      if (!indirizzo) { avviso(t("lega.incolla_prima_indirizzo")); return; }
      b.disabled = true; b.textContent = t("lega.scarico");
      try {
        await chiamaImmagine("/api/squadre/immagine/da-url", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ squadra: s.nome, tipo, url: indirizzo }) });
        await fine(t(tipo === "stemma" ? "scambio.stemma_aggiornato" : "scambio.maglia_aggiornata"));
      } catch (e) { b.disabled = false; b.textContent = t("lega.indirizzo_web"); avviso(e.message, 7000); }
    }));
    document.querySelectorAll("#foglio [data-rimuovi]").forEach(b => b.addEventListener("click", async () => {
      const tipo = b.dataset.rimuovi;
      try { await chiamaImmagine(`/api/squadre/immagine?squadra=${encodeURIComponent(s.nome)}&tipo=${tipo}`, { method: "DELETE" }); await fine(t(tipo === "stemma" ? "lega.stemma_rimosso" : "lega.maglia_rimossa")); }
      catch (e) { avviso(e.message, 6000); }
    }));
    document.querySelectorAll("#foglio [data-usa]").forEach(b => b.addEventListener("click", async () => {
      const tipo = b.dataset.usa;
      try {
        await carica(tipo, attesa, "condivisa");
        await chiamaImmagine("/api/squadre/immagine/in-attesa", { method: "DELETE" }).catch(() => {});
        attesa = null; if (urlAttesa) URL.revokeObjectURL(urlAttesa);
        await fine(t(tipo === "stemma" ? "scambio.stemma_aggiornato" : "scambio.maglia_aggiornata"));
        apriStemmaMaglia(s.nome, false);                 // ridisegna senza il riquadro dell'immagine condivisa
      } catch (e) { avviso(e.message, 6000); }
    }));
    const scarta = $("#sm-scarta");
    if (scarta) scarta.addEventListener("click", async () => {
      await chiamaImmagine("/api/squadre/immagine/in-attesa", { method: "DELETE" }).catch(() => {});
      if (urlAttesa) URL.revokeObjectURL(urlAttesa);
      apriStemmaMaglia(s.nome, false);
    });
  };
  disegna();
}

// Lega: un elenco di voci con il pannello a destra (stesso componente delle Impostazioni), le stesse otto voci dell'app per iPhone.
// Dal 31/10/2026 le voci sono divise in due schede: Squadra (la mia squadra, cambi, seguiti, elenco, aggiornamento rose) e Altro (tutto il resto).
// `ambito` dice dove sta la voce; `f` è la funzione (docs/DIETA-FUNZIONI.md) che la accende; `vai` è una voce che porta a un'altra pagina invece di aprire un pannello.
const VOCI_LEGA = [
  { id: "squadre", ambito: "squadra", nome: t("lega.voce_squadre"), sub: t("lega.voce_squadre_sub") },
  { id: "consigli", ambito: "squadra", nome: t("lega.voce_consigli"), sub: t("lega.voce_consigli_sub"), vai: () => vaiMercato("consigli") },
  { id: "osservati", ambito: "squadra", f: "seguiti", nome: t("lega.voce_osservati"), sub: t("lega.voce_osservati_sub"), vai: () => vaiMercato("osservati") },
  { id: "giocatori", ambito: "squadra", f: "elenco_giocatori", nome: t("lega.voce_giocatori"), sub: t("lega.voce_giocatori_sub"), vai: () => vaiMercato("giocatori") },
  { id: "calendario", ambito: "squadra", f: "elenco_giocatori", nome: t("lega.voce_calendario"), sub: t("lega.voce_calendario_sub"), vai: () => vaiMercato("calendario") },
  { id: "importa", ambito: "squadra", nome: t("lega.voce_importa"), sub: t("lega.voce_importa_sub") },
  { id: "scambi", ambito: "altro", nome: t("lega.voce_scambi"), sub: t("lega.voce_scambi_sub"), vai: () => vai("scambi") },
  { id: "diario", ambito: "altro", f: "diario", nome: t("lega.voce_diario"), sub: t("lega.voce_diario_sub") },
  { id: "regole", ambito: "altro", nome: t("lega.voce_regole"), sub: t("lega.voce_regole_sub"), vai: () => vistaRegole() },
  { id: "movimenti", ambito: "altro", f: "movimenti", nome: t("lega.voce_movimenti"), sub: t("lega.voce_movimenti_sub") },
  { id: "crediti", ambito: "altro", f: "crediti", nome: t("lega.voce_crediti"), sub: t("lega.voce_crediti_sub") },
  { id: "stagione", ambito: "altro", nome: t("lega.voce_stagione"), sub: t("lega.voce_stagione_sub") },
  { id: "novita", ambito: "altro", f: "novita", nome: t("lega.voce_novita"), sub: t("lega.voce_novita_sub"), vai: () => vistaNovita() },
];
const NOME_AMBITO = { squadra: t("nav.squadra"), altro: t("nav.altro") };
// In quale scheda sta una voce (per i collegamenti che dicono solo «apri le regole»): se non la conosciamo, Altro.
const ambitoVoce = id => (VOCI_LEGA.find(v => v.id === id) || {}).ambito || "altro";
function vaiMercato(scheda) { stato.mercatoTab = schedaMercato(scheda); vai("mercato"); }
// Apre Squadra o Altro già su una voce (anche tornando da una pagina come la rosa di una squadra o le regole).
function vaiLega(voce) { stato.legaTorna = voce; vai("lega"); }

async function vistaLega(ambito = "altro") {
  const mia = nuovaRichiesta();
  caricamento(t(ambito === "squadra" ? "lega.carico_squadra" : "comune.carico"));
  let squadre = [];
  try { squadre = await api("/api/squadre"); }
  catch (e) { if (e.rete) { if (ancoraValida(mia)) contenuto.innerHTML = erroreVista(e); return; } squadre = []; }
  if (!ancoraValida(mia)) return;
  const daUrl = stato.legaTorna; stato.legaTorna = null;
  const immagine = (sq, tipo) => sq.immagini && sq.immagini[tipo] ? `<img class="${tipo === "stemma" ? "stemma-lista" : "maglia-lista"}" src="${urlImg(sq.nome, tipo)}" alt="${t("lega.alt_immagine", { tipo: t(NOME_IMMAGINE[tipo]), nome: esc(sq.nome) })}" loading="lazy">` : "";
  const htmlSceltaMia = () => `<select class="campo-testo" id="mia-squadra" aria-label="${t("lega.tua_squadra")}">${squadre.map(x => `<option value="${esc(x.nome)}" ${x.mia ? "selected" : ""}>${esc(x.nome)}</option>`).join("")}</select>`;

  const corpi = {
    importa: () => `<div class="carta">
      <div class="debole piccolo">${t("lega.esporta_rose_excel")}</div>
      <div class="pulsanti"><label class="bottone" for="file-rose">${t("lega.scegli_file_excel")}</label></div>
      <details style="margin-top:14px"><summary style="font-size:var(--t-corpo)">${t("lega.con_tocco_dal")}</summary>
        <div class="debole piccolo">${t("lega.una_volta_sola")}</div>
        <ol class="guida">
          <li>${t("lega.sc1")}</li>
          <li>${t("lega.sc2")}</li>
          <li>${t("lega.sc3", { url: `<code>${esc(location.origin)}/api/rose/file</code>` })}</li>
          <li>${t("lega.sc4")}</li>
          <li>${t("lega.sc5")}</li>
          <li>${t("lega.sc6")}</li>
        </ol>
        <div class="debole piccolo">${t("lega.per_usarlo_apri")}</div>
      </details>
      <details style="margin-top:14px"><summary style="font-size:var(--t-corpo)">${t("lega.incolla_testo_delle")}</summary>
        <div class="debole piccolo">${t("lega.non_hai_file")}</div>
        <textarea id="testo-rose" class="campo-testo" style="margin-top:12px" placeholder="${t("lega.incolla_qui_testo")}"></textarea>
        <label class="interruttore"><span>${t("lega.togli_squadre_che")}</span><input type="checkbox" id="sostituisci-tutto"></label>
        <div class="pulsanti"><button class="bottone" id="importa-testo">${t("lega.importa_testo")}</button></div>
      </details>
      <input id="file-rose" type="file" accept=".xlsx,.xlsm,.csv,.tsv,.txt,text/csv,text/plain,text/tab-separated-values" hidden>
      <div id="esito-import"></div></div>`,
    squadre: () => { const miaS = squadre.find(x => x.mia), sceltaMia = htmlSceltaMia(); return squadre.length ? `<div class="carta" id="mia-squadra-carta"><h3 style="margin-top:0">${t("lega.mia_squadra")}</h3>
      ${miaS ? `<div class="mia-riga">${immagine(miaS, "stemma") || `<span class="iniziale-squadra">${esc(miaS.nome.trim().slice(0, 1).toUpperCase())}</span>`}${immagine(miaS, "maglia")}
        <div><b>${esc(miaS.nome)}</b><span class="debole piccolo" style="display:block">${tp("sd.n_giocatori", miaS.giocatori)}${miaS.crediti_residui != null ? ` · ${tp("lega.n_crediti", miaS.crediti_residui)}` : ""}</span></div></div>
        <div class="pulsanti"><button class="bottone secondario" id="apri-stemma-maglia">${t("lega.stemma_maglia")}</button><button class="bottone secondario" data-squadra="${esc(miaS.nome)}">${t("lega.vedi_rosa")}</button></div>
        <details style="margin-top:10px"><summary style="font-size:var(--t-corpo)">${t("lega.non_tua_squadra")}</summary>${sceltaMia}</details>`
        : `<div class="debole piccolo">${t("lega.scegli_quale_delle")}</div>${sceltaMia}`}</div>
      ${!funz("squadre_altrui") ? "" : `<div class="carta"><h3 style="margin-top:0">${t("lega.squadre_rose")}</h3>
      <ul class="elenco">${squadre.map(x => `<li><button class="voce" style="grid-template-columns:46px 1fr auto" data-squadra="${esc(x.nome)}">
        ${x.immagini && x.immagini.stemma ? `<img class="stemma-lista" src="${urlImg(x.nome, "stemma")}" alt="" loading="lazy">` : `<span class="iniziale-squadra">${esc(x.nome.trim().slice(0, 1).toUpperCase())}</span>`}
        <span><span class="nome">${esc(x.nome)}</span>${x.mia ? ` <span class="etichetta">${t("lega.la_tua")}</span>` : ""}
          <span class="dettaglio" style="display:block">${tp("sd.n_giocatori", x.giocatori)}${x.crediti_residui != null ? ` · ${tp("lega.n_crediti", x.crediti_residui)}` : ""}</span></span>
        <span class="debole" aria-hidden="true">›</span></button></li>`).join("")}</ul>
      <div class="debole piccolo" style="margin-top:8px">${t("lega.tocca_una_squadra")}</div></div>`}`
      : `<div class="carta"><div class="debole">${t("lega.importa_prima_rose")}</div></div>`; },
    movimenti: () => `<div id="storico-movimenti"><div class="carta caricamento">${t("lega.carico_movimenti")}</div></div>`,
    diario: () => `<div class="carta"><div class="debole piccolo">${t("lega.per_ogni_giornata")}</div>
      <div class="pulsanti"><button class="bottone" id="apri-diario" type="button">${t("lega.apri_diario")}</button></div></div>`,
    crediti: () => squadre.length ? `<div class="carta"><h3 style="margin-top:0">${t("lega.crediti_residui_ogni")}</h3>
      ${squadre.map((x, i) => `<div class="riga riga-crediti"><label for="cred-${i}">${esc(x.nome)}</label>
        <input class="campo-testo cred-squadra" id="cred-${i}" data-nome="${esc(x.nome)}" type="number" min="0" max="99999" inputmode="numeric" value="${x.crediti_residui ?? ""}" placeholder="—" style="width:96px;text-align:right"></div>`).join("")}
      <p class="attenzione" id="crediti-non-salvati" role="status" hidden>${t("lega.crediti_non_salvati")}</p>
      <div class="pulsanti"><button class="bottone" id="salva-crediti" type="button">${t("lega.salva_crediti")}</button></div>
      <div class="debole piccolo">${t("lega.servono_per_consigli")}</div></div>`
      : `<div class="carta"><div class="debole">${t("lega.importa_prima_rose")}</div></div>`,
    stagione: () => `<div id="stagione-corpo"><div class="carta caricamento">${t("lega.controllo_stagione")}</div></div>`,
  };

  const aggiornaSquadre = () => { caricaInfo(); caricaSquadre(); };
  // I pannelli disegnano `squadre`, lette all'apertura: dopo un salvataggio si rileggono (con `voce`, quel pannello si ridisegna),
  // così «La mia squadra», i crediti e l'elenco delle squadre non restano quelli di prima finché non si cambia scheda.
  const rileggiSquadre = async (voce) => {
    try { squadre = await api("/api/squadre"); } catch { return; }
    if (voce && stato.pannelli === cfg && $("#imp-pagina")) apriPannello(cfg, voce, false);
  };
  const collega = {
    importa: () => {
      const mostraEsito = esito => {
        svuotaCache();
        $("#esito-import").innerHTML = `<h3>${t("lega.cosa_cambiato")}</h3>${htmlDifferenze(esito.differenze)}
          <div class="debole piccolo" style="margin-top:10px">${t("lega.importate", { nomi: esito.squadre_importate.map(esc).join(", "), n: tp("lega.n_squadre", esito.totale_squadre) })}</div>
          ${esito.avvisi.length ? `<div class="attenzione" style="margin-top:12px"><b>${t("lega.da_controllare")}</b><br>${esito.avvisi.map(esc).join("<br>")}</div>` : `<div class="debole piccolo">${t("lega.rose_controllate_tutto")}</div>`}`;
        aggiornaSquadre(); rileggiSquadre();
      };
      // in due passi (anteprima.js): prima si controlla cosa ha capito l'app, poi «Conferma e salva»
      const controlla = sorgente => anteprimaRose($("#esito-import"), sorgente, {
        sostituisci: $("#sostituisci-tutto").checked,
        fatto: esito => { mostraEsito(esito); avviso(t("ar.salvate")); },
      });
      $("#file-rose").addEventListener("change", ev => {
        const file = ev.target.files[0];
        ev.target.value = "";              // così si può scegliere di nuovo lo stesso file
        if (file) controlla({ file });
      });
      $("#importa-testo").addEventListener("click", () => {
        const testo = $("#testo-rose").value;
        if (!testo.trim()) { avviso(t("lega.incolla_prima_testo")); return; }
        controlla({ testo });
      });
    },
    squadre: () => {
      document.querySelectorAll("[data-squadra]").forEach(b => b.addEventListener("click", () => { stato.legaTorna = "squadre"; vistaRosa(b.dataset.squadra); }));
      const asm = $("#apri-stemma-maglia");
      if (asm) asm.addEventListener("click", () => apriStemmaMaglia());
      const ms = $("#mia-squadra");
      if (ms) ms.addEventListener("change", async () => {
        try { await api("/api/mia-squadra", { method: "PUT", body: JSON.stringify({ nome: ms.value }) }); svuotaCache(); stato.squadraVista = null; avviso(t("lega.squadra_salvata")); aggiornaSquadre(); rileggiSquadre("squadre"); }
        catch (e) { avviso(e.message); }
      });
    },
    movimenti: async () => {
      try {
        const s = await api("/api/movimenti?limite=20");
        const dove = $("#storico-movimenti");
        if (!dove) return;
        dove.innerHTML = s.length ? s.map(m => `<div class="carta"><h3 style="margin-top:0">${fDataOra(new Date(m.quando))}</h3>
          ${htmlDifferenze({ ...m, nessuna_differenza: false })}</div>`).join("") : `<div class="carta"><div class="debole">${t("lega.ancora_nessun_movimento")}</div></div>`;
      } catch (e) { const dove = $("#storico-movimenti"); if (dove) dove.innerHTML = `<div class="carta"><div class="debole">${esc(e.message)}</div></div>`; }
    },
    diario: () => $("#apri-diario").addEventListener("click", () => apriDiario()),
    crediti: () => {
      const b = $("#salva-crediti");
      if (!b) return;
      // «Ci sono crediti scritti e non ancora salvati»: confronto con i valori arrivati dal server (dopo il salvataggio: quelli salvati)
      const campi = [...document.querySelectorAll(".cred-squadra")];
      let salvati = campi.map(c => c.value.trim());
      const segnaModifiche = () => { const n = $("#crediti-non-salvati"); if (n) n.hidden = campi.every((c, i) => c.value.trim() === salvati[i]); };
      campi.forEach(c => c.addEventListener("input", segnaModifiche));
      b.addEventListener("click", async () => {
        const crediti = {};
        for (const c of document.querySelectorAll(".cred-squadra")) {
          const val = c.value.trim();
          if (!val) continue;
          if (!/^\d{1,5}$/.test(val)) { avviso(t("lega.crediti_numero", { nome: c.dataset.nome })); return; }
          crediti[c.dataset.nome] = Number(val);
        }
        try { await api("/api/crediti", { method: "PUT", body: JSON.stringify({ crediti }) }); salvati = campi.map(c => c.value.trim()); segnaModifiche(); svuotaCache(); caricaSquadre(); avviso(t("lega.crediti_salvati")); rileggiSquadre(); }
        catch (e) { avviso(e.message, 5000); }
      });
    },
    stagione: () => nuovaStagione($("#stagione-corpo")),
  };

  const voci = VOCI_LEGA.filter(v => v.ambito === ambito && (!v.f || funz(v.f)))
    .map(v => v.id === "squadre" && !funz("squadre_altrui") ? { ...v, nome: t("lega.voce_miasquadra"), sub: t("lega.voce_miasquadra_sub") } : v);
  const apribili = voci.filter(v => !v.vai);                      // le voci con `vai` portano altrove: non si aprono come pannello
  const diretta = voci.find(v => v.vai && v.id === daUrl);        // «apri le regole» da Da fare o da un collegamento: subito lì
  if (diretta) { diretta.vai(); return; }
  stato.legaVoce = stato.legaVoce || {};
  const cfg = {
    voci, corpi, collega, aria: t(ambito === "squadra" ? "lega.aria_squadra" : "lega.aria_altro"), indietro: NOME_AMBITO[ambito],
    scelto: (apribili.find(v => v.id === daUrl) || (impLargo() ? apribili.find(v => v.id === stato.legaVoce[ambito]) || apribili[0] : null) || {}).id,
    ricorda: id => { stato.legaVoce[ambito] = id; },
  };
  stato.pannelli = cfg;
  montaPannelli(cfg);
  bannerNuovaStagione();
}

// Nuova stagione: se le rose sono ancora quelle dell'anno prima compare il pulsante per archiviarle.
async function nuovaStagione(dove) {
  let s;
  try { s = await api("/api/stagione"); } catch (e) { if (document.body.contains(dove)) dove.innerHTML = `<div class="carta"><div class="debole">${esc(e.message)}</div></div>`; return; }
  if (!document.body.contains(dove)) return;
  if (!s.nuova) {
    dove.innerHTML = `<div class="carta"><div class="debole">${t("lega.stagione_in_corso", { s: esc(s.corrente) })}</div></div>`;
    return;
  }
  dove.innerHTML = `<div class="carta"><h3 style="margin-top:0">${t("lega.nuova_stagione_n", { s: esc(s.corrente) })}</h3>
    <div class="debole piccolo">${t("lega.rose_ancora_quelle", { s: esc(s.rose) })}</div>
    <div class="pulsanti"><button class="bottone" id="nuova-stagione">${t("lega.archivia_riparti")}</button></div></div>`;
  $("#nuova-stagione").addEventListener("click", async () => {
    if (!confirm(t("lega.conferma_archivio", { s: s.rose }))) return;
    try {
      await api("/api/nuova-stagione", { method: "POST" }); svuotaCache();
      apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("lega.stagione_archiviata", { s: esc(s.rose) })}</h2>
        <div class="debole piccolo">${t("lega.tutto_salvato_nell")}</div>
        <div class="carta" style="margin-top:12px"><ol class="novita-voci">
          <li><b>${t("lega.importa_nuove_rose")}</b>${t("lega.squadra_aggiorna_rose")}</li>
          <li><b>${t("lega.controlla_regole")}</b>${t("lega.bonus_moduli_crediti")}</li>
          <li><b>${t("lega.inserisci_crediti")}</b> ${t("lega.delle_squadre_altro")}</li>
          <li><b>${t("shell.aggiorna")}</b> ${t("lega.con_tasto_alto")}</li></ol></div>
        <div class="pulsanti"><button class="bottone" data-vai="squadra">${t("lega.vai_squadra")}</button></div>`);
      vaiLega("importa");
    } catch (e) { avviso(e.message, 5000); }
  });
}

// In cima alla Lega, solo quando serve: porta alla voce «Nuova stagione».
async function bannerNuovaStagione() {
  try {
    const s = await api("/api/stagione");
    if (!s.nuova || stato.vista !== "altro" || !$(".imp")) return;
    const c = document.createElement("div");
    c.className = "carta"; c.dataset.g = "lega";
    c.innerHTML = `<button class="voce" id="banner-stagione" type="button" style="grid-template-columns:1fr auto"><span><span class="nome">${t("lega.nuova_stagione_n", { s: esc(s.corrente) })}</span>
      <span class="dettaglio" style="display:block">${t("lega.banner_stagione", { s: esc(s.rose) })}</span></span><span class="debole" aria-hidden="true">›</span></button>`;
    contenuto.prepend(c);
    $("#banner-stagione").addEventListener("click", () => { if (stato.pannelli) apriPannello(stato.pannelli, "stagione"); });
  } catch { /* senza rose o senza rete: niente banner */ }
}


// ---------------------------------------------------------------- novità dell'app
const MESI_CORTI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
// "2026-10-30T14:05:12" -> "30 ott 2026, 14:05:12" (l'ora è già italiana: non si converte); senza ora, solo la data
function dataNovita(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}:\d{2}))?/.exec(String(d || ""));
  if (!m) return "";
  const giorno = fData(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])), { day: "numeric", month: "short", year: "numeric" });
  return `${giorno}${m[4] ? ", " + m[4] : ""}`;
}

// Novità: le ultime NOVITA_VISIBILI versioni; le altre (sono centinaia) solo a richiesta, così la pagina resta leggera.
// Alla prima visita (nessuna versione vista) è «Nuovo» solo l'ultima, non tutto lo storico.
const NOVITA_VISIBILI = 10;
async function vistaNovita() {
  const mia = nuovaRichiesta();
  caricamento(t("novita.carico"));
  try {
    const elenco = await api("/api/novita");
    if (!ancoraValida(mia)) return;
    const ultima = (() => { try { return localStorage.getItem("novita-vista"); } catch { return null; } })();
    const trovata = ultima ? elenco.findIndex(v => v.versione === ultima) : -1;
    const nuoveDa = !ultima ? Math.min(1, elenco.length) : trovata < 0 ? Math.min(NOVITA_VISIBILI, elenco.length) : trovata;
    const carta = (v, k) => `<div class="carta"><div class="riga"><h2 style="margin:0">${esc(v.titolo)}</h2>${k < nuoveDa ? `<span class="etichetta">${t("regole.nuovo")}</span>` : ""}</div>
        <div class="debole piccolo">${t("novita.versione", { v: esc(v.versione) })} · ${dataNovita(v.data)}</div>
        <ul class="novita-voci">${(v.voci || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    const visibili = Math.max(NOVITA_VISIBILI, nuoveDa), resto = elenco.length - visibili;
    pagina(`<div class="carta"><div class="riga"><button class="bottone secondario indietro" data-vai="altro" style="padding:6px 14px;min-height:44px">${ICONA_INDIETRO}${t("nav.altro")}</button>
        <span class="debole">${t("novita.versione", { v: esc(elenco[0] ? elenco[0].versione : "?") })}</span></div><h2 style="margin-top:14px">${t("info.novita")}</h2></div>
      ${elenco.slice(0, visibili).map(carta).join("")}
      ${resto > 0 ? `<div class="pulsanti" id="novita-altre-riga"><button class="bottone secondario" id="novita-altre">${tp("novita.precedenti", resto)}</button></div>` : ""}`);
    const altre = $("#novita-altre");
    if (altre) altre.addEventListener("click", () => {
      $("#novita-altre-riga").outerHTML = elenco.slice(visibili).map((v, k) => carta(v, visibili + k)).join("");
    });
    try { if (elenco[0]) localStorage.setItem("novita-vista", elenco[0].versione); } catch { /* niente memoria */ }
  } catch (e) { if (ancoraValida(mia)) contenuto.innerHTML = errore(e); }
}

// ---------------------------------------------------------------- regole: schermata semplice con − / +
const sistema = {};   // stato della schermata regole (regole originali)
function stepper(id, valore, { passo = 0.5, min = -50, max = 999, dec = 1 } = {}) {
  return `<div class="stepper" data-passo="${passo}" data-min="${min}" data-max="${max}" data-dec="${dec}">
    <button type="button" data-step="-1" aria-label="${t("regole.diminuisci")}">−</button>
    <input id="${id}" inputmode="decimal" autocomplete="off" value="${num(valore, dec)}">
    <button type="button" data-step="1" aria-label="${t("regole.aumenta")}">+</button></div>`;
}
const leggiN = id => { const el = $("#" + id); return el ? Number(String(el.value).replace(",", ".")) : NaN; };
const interruttore = (id, testo, acceso, aiuto = "") => `<label class="interruttore-ios"><span>${testo}${aiuto ? `<small>${aiuto}</small>` : ""}</span><input type="checkbox" id="${id}" ${acceso ? "checked" : ""}><i></i></label>`;
// Il campo della riga prende come nome per i lettori di schermo il testo della riga (testo semplice, passato per esc): prima restava senza nome o
// con il titolo della sezione («Gol» anche per l'assist).
const rigaRegola = (etichetta, controllo, aiuto = "") => `<div class="riga-regola"><span>${etichetta}${aiuto ? `<small>${aiuto}</small>` : ""}</span>${controllo.replace("<input ", `<input aria-label="${esc(etichetta)}" `)}</div>`;

document.addEventListener("click", ev => {
  const b = ev.target.closest(".stepper button[data-step]");
  if (!b) return;
  const s = b.closest(".stepper"), campo = $("input", s);
  const passo = Number(s.dataset.passo), dec = Number(s.dataset.dec);
  let v = Number(String(campo.value).replace(",", "."));
  if (!Number.isFinite(v)) v = 0;
  v = Math.min(Number(s.dataset.max), Math.max(Number(s.dataset.min), v + Number(b.dataset.step) * passo));
  campo.value = num(Math.round(v / passo) * passo, dec);
  campo.dispatchEvent(new Event("input", { bubbles: true }));
});

// bonus della difesa per una media: l'ultima fascia raggiunta (come fa il calcolo della formazione)
const bonusDifesa = (media, fasce) => fasce.filter(f => media >= f[0]).reduce((b, f) => f[1], 0);

async function vistaRegole() {
  const mia = nuovaRichiesta();
  caricamento(t("regole.carico"));
  let r;
  try { r = await api("/api/regole"); } catch (e) { if (ancoraValida(mia)) contenuto.innerHTML = errore(e); return; }
  if (!ancoraValida(mia)) return;
  if (regoleAC) regoleAC.abort();
  regoleAC = new AbortController();
  const sig = { signal: regoleAC.signal };
  const md = r.modificatore_difesa;
  const moduli = [...new Set([...TUTTI_MODULI, ...r.moduli])];
  const rigaGol = x => rigaRegola(t("regole.gol_di", { ruolo: NOME_RUOLO_1[x].toLowerCase() }), stepper("gol_" + x, r.bonus.gol[x], { passo: 0.5, min: 0, max: 20 }));
  const bonusRighe = [["assist", t("bonus.assist")], ["rigore_segnato", t("bonus.rigore_segnato")], ["rigore_parato", t("regole.rigore_parato_p")], ["portiere_imbattuto", t("bonus.portiere_imbattuto")], ["mvp", t("bonus.mvp")]];
  const malusRighe = [["ammonizione", t("bonus.ammonizione")], ["espulsione", t("bonus.espulsione")], ["autogol", t("bonus.autogol")], ["rigore_sbagliato", t("bonus.rigore_sbagliato")], ["gol_subito_portiere", t("bonus.gol_subito_portiere"), t("regole.per_ogni_gol")]];
  const fascia = (media, bonus) => `<div class="fascia"><div class="coppia"><span class="debole piccolo">${t("regole.media_almeno")}</span>${stepper("", media, { passo: 0.25, min: 4, max: 9, dec: 2 }).replace('id=""', 'class="f-media"')}</div>
    <div class="coppia"><span class="debole piccolo">${t("regole.bonus")}</span>${stepper("", bonus, { passo: 0.5, min: 0, max: 20, dec: 1 }).replace('id=""', 'class="f-bonus"')}</div>
    <button type="button" class="rimuovi-fascia" aria-label="${t("regole.togli_fascia")}">✕</button></div>`;
  contenuto.classList.remove("ridisegna");
  contenuto.innerHTML = `
    <div class="carta">
      <div class="riga"><button class="bottone secondario indietro" data-vai="altro" style="padding:6px 14px;min-height:44px">${ICONA_INDIETRO}${t("regole.altro")}</button>
        <button class="bottone secondario" id="annulla-regole" style="padding:6px 14px;min-height:44px">${t("regole.annulla_modifiche")}</button></div>
      <h2 style="margin-top:14px">${esc(r.nome_lega)}</h2>
      <div class="debole piccolo">${t("regole.regole_della_lega")}</div>
      <input class="campo-testo" id="nome_lega" value="${esc(r.nome_lega)}" aria-label="${t("regole.nome_della_lega")}" style="margin-top:8px">
    </div>

    <div class="carta hero"><h2>${t("regole.importa_leghe")}</h2>
      <div class="debole piccolo">${t("regole.leghe_apri_regolamento")}</div>
      <textarea id="testo-regole" class="campo-testo" style="margin-top:10px;min-height:96px" placeholder="${t("regole.incolla_qui_testo")}"></textarea>
      <div class="pulsanti"><button class="bottone" id="riconosci-regole">${t("regole.riconosci_regole")}</button></div>
      <div id="anteprima-regole"></div>
    </div>

    <details class="carta regola-sez" open><summary>${t("regole.punteggi")}</summary>
      <h3>${t("oggi.ev_gol")}</h3>${["P", "D", "C", "A"].map(rigaGol).join("")}
      <h3>${t("regole.altri_bonus")}</h3>${bonusRighe.map(([k, nome]) => rigaRegola(nome, stepper("b_" + k, r.bonus[k], { passo: 0.5, min: 0, max: 20 }))).join("")}
      <h3>${t("regole.malus")}</h3>${malusRighe.map(([k, nome, a]) => rigaRegola(nome, stepper("b_" + k, r.bonus[k], { passo: 0.5, min: -20, max: 0 }), a || "")).join("")}
      <h3>${t("regole.voto_partenza")}</h3>
      <div class="segmenti" id="fonte-voto">${[["redazione", t("regole.v_redazione")], ["statistico", t("regole.v_statistico")], ["italia", t("regole.v_italia")]].map(([k, nome]) => `<button type="button" data-valore="${k}" class="${r.fonte_voto === k ? "attivo" : ""}">${nome}</button>`).join("")}</div>
      <div class="debole piccolo">${t("regole.quale_voto_somma")}</div>
    </details>

    <details class="carta regola-sez"><summary>${t("regole.modificatore_difesa")}</summary>
      ${interruttore("md_attivo", t("regole.md_attivo"), md.attivo, t("regole.md_attivo_aiuto"))}
      <div id="md-corpo" ${md.attivo ? "" : "hidden"}>
        ${rigaRegola(t("regole.md_min"), stepper("md_min", md.min_difensori, { passo: 1, min: 3, max: 6, dec: 0 }), t("regole.md_min_aiuto"))}
        <h3>${t("regole.fasce_bonus")}</h3>
        <div class="debole piccolo">${t("regole.media_somma")} <b>${t("regole.portiere_migliori_difensori")}</b> ${t("regole.divisa_per_per")}</div>
        <div id="fasce">${[...md.soglie].sort((a, b) => a[0] - b[0]).map(s => fascia(s[0], s[1])).join("")}</div>
        <div class="pulsanti"><button type="button" class="bottone secondario" id="aggiungi-fascia">${t("regole.aggiungi_fascia")}</button></div>
        <h3>${t("regole.prova")}</h3>
        <div class="prova-difesa"><span class="debole piccolo">${t("regole.voti_portiere_difensori")}</span>
          <div class="prova-voti">${[6.5, 6, 6.5, 7].map((v, k) => stepper("pv" + k, v, { passo: 0.5, min: 3, max: 10 })).join("")}</div>
          <div id="prova-esito" class="prova-esito"></div></div>
      </div>
    </details>

    <details class="carta regola-sez"><summary>${t("regole.moduli_ammessi")}</summary>
      <div class="debole piccolo">${t("regole.quelli_che_puoi")}</div>
      <div class="chips" id="moduli">${moduli.map(m => `<button type="button" class="chip ${r.moduli.includes(m) ? "attiva" : ""}" data-modulo-regola="${m}">${m}</button>`).join("")}</div>
    </details>

    <details class="carta regola-sez"><summary>${t("regole.panchina_sostituzioni")}</summary>
      ${interruttore("posti_fissi", t("regole.posti_fissi"), !!r.panchina.posti, t("regole.posti_fissi_aiuto"))}
      <div id="posti-corpo" ${r.panchina.posti ? "" : "hidden"}>
        ${["P", "D", "C", "A"].map(x => rigaRegola(NOMI_RUOLO[x], stepper("posti_" + x, (r.panchina.posti || { P: 2, D: 3, C: 3, A: 3 })[x], { passo: 1, min: 0, max: 8, dec: 0 }))).join("")}
        <div class="debole piccolo" id="totale-posti" style="margin:4px 0 8px"></div>
      </div>
      <div id="numero-corpo" ${r.panchina.posti ? "hidden" : ""}>${rigaRegola(t("regole.giocatori_panchina"), stepper("p_numero", r.panchina.numero, { passo: 1, min: 1, max: 14, dec: 0 }))}</div>
      ${rigaRegola(t("regole.cambi_massimi"), stepper("p_max", r.panchina.max_sostituzioni, { passo: 1, min: 0, max: 14, dec: 0 }))}
      <h3>${t("regole.come_entrano_riserve")}</h3>
      <div class="segmenti" id="tipo-panchina">${[["per_ruolo", t("regole.per_ruolo")], ["libera", t("regole.libera")]].map(([k, nome]) => `<button type="button" data-valore="${k}" class="${r.panchina.tipo === k ? "attivo" : ""}">${nome}</button>`).join("")}</div>
      <div class="debole piccolo" id="aiuto-panchina"></div>
      ${interruttore("p_cambio", t("regole.cambio_modulo"), r.panchina.cambio_modulo, t("regole.cambio_modulo_aiuto"))}
      ${interruttore("vu_attivo", t("regole.vu_se_manca"), r.voto_senza_sostituto !== null && r.voto_senza_sostituto !== undefined)}
      <div id="vu-corpo" ${r.voto_senza_sostituto !== null && r.voto_senza_sostituto !== undefined ? "" : "hidden"}>${rigaRegola(t("regole.vu"), stepper("voto_ufficio", r.voto_senza_sostituto ?? 4, { passo: 0.5, min: 0, max: 10 }))}</div>
    </details>

    <details class="carta regola-sez"><summary>${t("regole.tempi_della_lega")}</summary>
      ${rigaRegola(t("regole.scadenza"), stepper("scad_min", r.scadenza_minuti ?? 0, { passo: 5, min: 0, max: 720, dec: 0 }), t("regole.scadenza_aiuto"))}
      ${rigaRegola(t("regole.prima_giornata"), stepper("prima_g", r.prima_giornata_lega ?? 1, { passo: 1, min: 1, max: 38, dec: 0 }), t("regole.prima_giornata_aiuto"))}
      ${interruttore("agg_vicini", t("regole.agg_vicini"), r.aggiornamenti_vicino_scadenza !== false, t("regole.agg_vicini_aiuto"))}
      <div class="debole piccolo">${t("regole.con_prima_giornata")}</div>
    </details>

    ${r.partite_rinviate !== undefined ? `<details class="carta regola-sez" id="sez-rinviate"><summary>${t("regole.rinviate")}</summary>
      <div class="debole piccolo">${t("regole.rinviate_aiuto")}</div>
      <div class="segmenti" id="rinvio-modo">${[["aspetta", t("regole.rv_aspetta")], ["senza_voto", t("regole.rv_senza_voto")], ["voto_ufficio", t("regole.rv_ufficio")]].map(([k, nome]) => `<button type="button" data-valore="${k}" class="${r.partite_rinviate === k ? "attivo" : ""}">${nome}</button>`).join("")}</div>
      <div class="debole piccolo" id="aiuto-rinvio"></div>
      <div id="rinvio-voto-corpo" ${r.partite_rinviate === "voto_ufficio" ? "" : "hidden"}>${rigaRegola(t("regole.rv_voto"), stepper("voto_rinv", r.voto_ufficio_rinviate ?? 6, { passo: 0.5, min: 0, max: 10 }))}</div>
    </details>` : ""}

    <details class="carta regola-sez"><summary>${t("regole.rosa_crediti")}</summary>
      ${["P", "D", "C", "A"].map(x => rigaRegola(NOMI_RUOLO[x], stepper("rosa_" + x, r.rosa[x], { passo: 1, min: 0, max: 20, dec: 0 }))).join("")}
      ${rigaRegola(t("regole.crediti_iniziali"), stepper("crediti", r.crediti_iniziali, { passo: 10, min: 0, max: 5000, dec: 0 }))}
    </details>
    <div class="salva-fisso" hidden><button class="bottone" id="salva-regole">${t("regole.salva_regole")}</button></div>`;
  const mostraSalva = () => { const s = $(".salva-fisso"); if (s) s.hidden = false; };

  // --- comportamenti
  const leggiFasce = () => [...document.querySelectorAll("#fasce .fascia")].map(f => [leggiN2($("input.f-media", f)), leggiN2($("input.f-bonus", f))]);
  const leggiN2 = el => Number(String(el.value).replace(",", "."));
  const aggiornaProva = () => {
    const voti = [0, 1, 2, 3].map(k => leggiN("pv" + k));
    const media = voti.reduce((a, b) => a + b, 0) / 4;
    const b = bonusDifesa(media, leggiFasce().sort((x, y) => x[0] - y[0]));
    $("#prova-esito").innerHTML = `${tp("regole.media_bonus", Math.abs(b), { m: `<b>${num(media, 2)}</b>`, b: `<b class="${b > 0 ? "positivo" : ""}">${b > 0 ? "+" : ""}${num(b, Number.isInteger(b) ? 0 : 1)}</b>` })}`;
  };
  const aiutoPanchina = () => {
    const tipo = $("#tipo-panchina .attivo").dataset.valore;
    $("#aiuto-panchina").textContent = tipo === "per_ruolo"
      ? t("regole.aiuto_per_ruolo")
      : t("regole.aiuto_libera");
  };
  const aiutoRinvio = () => {
    const el = $("#rinvio-modo .attivo");
    if (!el) return;
    $("#aiuto-rinvio").textContent = t("regole.rv_aiuto_" + el.dataset.valore);
    $("#rinvio-voto-corpo").hidden = el.dataset.valore !== "voto_ufficio";
  };
  const totalePosti = () => ["P", "D", "C", "A"].reduce((s, x) => s + (leggiN("posti_" + x) || 0), 0);
  const aggiornaPosti = () => { const el = $("#totale-posti"); if (el) el.textContent = t("regole.totale_panchina", { n: tp("sd.n_giocatori", totalePosti()) }); };
  aggiornaProva(); aiutoPanchina(); aggiornaPosti(); aiutoRinvio();
  $("#posti_fissi").addEventListener("change", ev => { $("#posti-corpo").hidden = !ev.target.checked; $("#numero-corpo").hidden = ev.target.checked; mostraSalva(); });
  contenuto.addEventListener("input", ev => { aggiornaProva(); aggiornaPosti(); if (ev.target.id !== "testo-regole") mostraSalva(); }, sig);
  $("#md_attivo").addEventListener("change", ev => { $("#md-corpo").hidden = !ev.target.checked; mostraSalva(); });
  $("#vu_attivo").addEventListener("change", ev => { $("#vu-corpo").hidden = !ev.target.checked; mostraSalva(); });
  $("#p_cambio").addEventListener("change", mostraSalva);
  $("#agg_vicini").addEventListener("change", mostraSalva);
  $("#aggiungi-fascia").addEventListener("click", () => {
    const f = leggiFasce(), ultima = f.length ? f[f.length - 1] : [6, 0];
    $("#fasce").insertAdjacentHTML("beforeend", fascia(Math.min(9, ultima[0] + 0.5), ultima[1] + 1));
    aggiornaProva(); mostraSalva();
  });
  contenuto.addEventListener("click", ev => {
    const x = ev.target.closest(".rimuovi-fascia");
    if (x) { x.closest(".fascia").remove(); aggiornaProva(); mostraSalva(); }
    const seg = ev.target.closest(".segmenti button[data-valore]");
    if (seg) { seg.parentElement.querySelectorAll("button").forEach(b => b.classList.toggle("attivo", b === seg)); aiutoPanchina(); aiutoRinvio(); mostraSalva(); }
    const m = ev.target.closest("[data-modulo-regola]");
    if (m) { m.classList.toggle("attiva"); mostraSalva(); }
  }, sig);
  $("#annulla-regole").addEventListener("click", vistaRegole);

  // --- importazione dal testo di Leghe
  $("#riconosci-regole").addEventListener("click", async () => {
    const testo = $("#testo-regole").value;
    if (!testo.trim()) { avviso(t("regole.incolla_prima_testo")); return; }
    const dove = $("#anteprima-regole");
    dove.innerHTML = `<div class="caricamento">${t("regole.leggo_testo")}</div>`;
    try {
      const esito = await api("/api/regole/riconosci", { method: "POST", body: JSON.stringify({ testo }) });
      if (!esito.modifiche.length) {
        dove.innerHTML = `<div class="attenzione" style="margin-top:12px">${t("regole.non_riconosciuto_nessuna")}</div>`;
        return;
      }
      const vedi = v => Array.isArray(v) ? (v.length && Array.isArray(v[0]) ? v.map(s => `${num(s[0], 2)}→+${num(s[1], 0)}`).join(" · ") : v.join(", ")) : typeof v === "boolean" ? t(v ? "regole.si" : "regole.no") : typeof v === "number" ? num(v, Number.isInteger(v) ? 0 : 1) : v;
      dove.innerHTML = `<h3>${t("regole.riconosciuto")}</h3>${esito.modifiche.map(m => `<div class="movimento"><span class="icona-mov su">✓</span><span>${esc(etichettaRegola(m))}: <b>${esc(vedi(m.valore))}</b>${m.riga ? `<span class="debole piccolo" style="display:block">${t("regole.da_riga", { r: esc(m.riga) })}</span>` : ""}</span></div>`).join("")}
        ${esito.non_riconosciute.length ? `<details><summary style="font-size:var(--t-corpo)">${t("regole.non_riconosciute", { n: esito.non_riconosciute.length })}</summary><div class="debole piccolo">${esito.non_riconosciute.map(esc).join("<br>")}</div></details>` : ""}
        <div class="pulsanti"><button class="bottone" id="applica-regole">${t("regole.applica_campi")}</button></div>
        <div class="debole piccolo">${t("regole.controlla_valori_qui")}</div>`;
      $("#applica-regole").addEventListener("click", () => { applicaModifiche(esito.modifiche); avviso(t("regole.valori_applicati_controlla")); });
    } catch (e) { dove.innerHTML = errore(e); }
  });
  const imposta = (id, valore, dec) => { const el = $("#" + id); if (el) { el.value = num(valore, dec ?? (Number.isInteger(valore) ? 0 : 1)); el.closest(".riga-regola")?.classList.add("evidenzia"); } };
  const applicaModifiche = mods => {
    for (const m of mods) {
      const k = m.chiave, v = m.valore;
      if (k.startsWith("bonus.gol.")) imposta("gol_" + k.slice(-1), v);
      else if (k.startsWith("bonus.")) imposta("b_" + k.slice(6), v);
      else if (k.startsWith("rosa.")) imposta("rosa_" + k.slice(5), v, 0);
      else if (k === "crediti_iniziali") imposta("crediti", v, 0);
      else if (k === "scadenza_minuti") imposta("scad_min", v, 0);
      else if (k === "prima_giornata_lega") imposta("prima_g", v, 0);
      else if (k === "panchina.numero") imposta("p_numero", v, 0);
      else if (k === "panchina.posti") { $("#posti_fissi").checked = true; $("#posti-corpo").hidden = false; $("#numero-corpo").hidden = true; for (const x of ["P", "D", "C", "A"]) imposta("posti_" + x, v[x], 0); aggiornaPosti(); }
      else if (k === "panchina.max_sostituzioni") imposta("p_max", v, 0);
      else if (k === "panchina.cambio_modulo") $("#p_cambio").checked = !!v;
      else if (k === "panchina.tipo") { document.querySelectorAll("#tipo-panchina button").forEach(b => b.classList.toggle("attivo", b.dataset.valore === v)); aiutoPanchina(); }
      else if (k === "moduli") document.querySelectorAll("[data-modulo-regola]").forEach(b => b.classList.toggle("attiva", v.includes(b.dataset.moduloRegola)));
      else if (k === "modificatore_difesa.attivo") { $("#md_attivo").checked = !!v; $("#md-corpo").hidden = !v; }
      else if (k === "modificatore_difesa.min_difensori") imposta("md_min", v, 0);
      else if (k === "modificatore_difesa.soglie") { $("#fasce").innerHTML = v.map(s => fascia(s[0], s[1])).join(""); aggiornaProva(); }
    }
    mostraSalva();
    setTimeout(() => document.querySelectorAll(".evidenzia").forEach(e => e.classList.remove("evidenzia")), 2500);
  };

  // --- salvataggio
  $("#salva-regole").addEventListener("click", async () => {
    const campi = [...contenuto.querySelectorAll(".stepper input")].filter(i => !i.closest("[hidden]"));
    const rotti = campi.filter(i => !Number.isFinite(Number(String(i.value).replace(",", "."))));
    if (rotti.length) { avviso(t("regole.sono_valori_non"), 5000); rotti[0].focus(); return; }
    const nuove = structuredClone(r);
    nuove.nome_lega = $("#nome_lega").value.trim() || t("regole.mia_lega");
    nuove.fonte_voto = $("#fonte-voto .attivo").dataset.valore;
    for (const x of ["P", "D", "C", "A"]) { nuove.bonus.gol[x] = leggiN("gol_" + x); nuove.rosa[x] = leggiN("rosa_" + x); }
    for (const [k] of [...bonusRighe, ...malusRighe]) nuove.bonus[k] = leggiN("b_" + k);
    nuove.moduli = [...document.querySelectorAll("[data-modulo-regola].attiva")].map(c => c.dataset.moduloRegola);
    if (!nuove.moduli.length) { avviso(t("regole.scegli_almeno_modulo"), 5000); return; }
    const postiOn = $("#posti_fissi").checked;
    const posti = postiOn ? Object.fromEntries(["P", "D", "C", "A"].map(x => [x, leggiN("posti_" + x)])) : null;
    nuove.panchina = { numero: postiOn ? totalePosti() : leggiN("p_numero"), max_sostituzioni: leggiN("p_max"), tipo: $("#tipo-panchina .attivo").dataset.valore,
                       cambio_modulo: $("#p_cambio").checked, posti };
    nuove.voto_senza_sostituto = $("#vu_attivo").checked ? leggiN("voto_ufficio") : null;
    nuove.crediti_iniziali = leggiN("crediti");
    nuove.scadenza_minuti = leggiN("scad_min");
    nuove.prima_giornata_lega = leggiN("prima_g");
    nuove.aggiornamenti_vicino_scadenza = $("#agg_vicini").checked;
    if ($("#rinvio-modo .attivo")) {             // (server vecchio senza la regola dei rinvii: la sezione non c'è e non si manda nulla)
      nuove.partite_rinviate = $("#rinvio-modo .attivo").dataset.valore;
      nuove.voto_ufficio_rinviate = leggiN("voto_rinv");
    }
    const fasce = leggiFasce().filter(f => Number.isFinite(f[0]) && Number.isFinite(f[1])).sort((a, b) => a[0] - b[0]);
    if (new Set(fasce.map(f => f[0])).size !== fasce.length) { avviso(t("regole.due_fasce_hanno"), 5000); return; }
    nuove.modificatore_difesa = { attivo: $("#md_attivo").checked, min_difensori: leggiN("md_min"), soglie: fasce };
    try {
      await api("/api/regole", { method: "PUT", body: JSON.stringify(nuove) });
      svuotaCache();
      stato.calendario = null;
      avviso(t("regole.regole_salvate_consigli"));
      caricaInfo();
      vistaRegole();
    } catch (e) { avviso(e.message, 8000); }
  });
}

// ---------------------------------------------------------------- account
// Funziona solo se il server ha gli account accesi (FANTA_MULTIUTENTE=1). Senza (l'app di sempre, per esempio sul server di oggi)
// niente di questo compare: `stato.account` resta vuoto e l'app si comporta come prima.
const soloAmministratore = () => !stato.account || stato.account.ruolo === "amministratore";

// All'uscita su questo dispositivo non deve restare niente dell'utente: copie dei dati, archivio scambi, copie dell'app del service worker.
async function svuotaDatiLocali() {
  try { Object.keys(localStorage).filter(k => k.startsWith("cache:") || ["archivio-scambi", "vista", "account"].includes(k)).forEach(k => localStorage.removeItem(k)); }
  catch { /* niente memoria */ }
  try { sessionStorage.clear(); } catch { /* niente memoria */ }
  try { if (window.caches) await Promise.all((await caches.keys()).map(k => caches.delete(k))); } catch { /* niente copie */ }
}
// Il tasto Indietro del browser può rimettere una pagina dalla sua memoria: con gli account si ricarica, così dopo un'uscita
// non ricompaiono i dati di chi è uscito.
window.addEventListener("pageshow", ev => { if (ev.persisted && (stato.account || accessoAperto)) location.reload(); });

// Le notifiche di questo dispositivo sono dell'utente che esce: si tolgono, così non arrivano a chi entra dopo di lui.
async function lasciaNotifiche() {
  try {
    if (!("serviceWorker" in navigator && "PushManager" in window)) return;
    const reg = await Promise.race([navigator.serviceWorker.ready, new Promise((_, no) => setTimeout(no, 2000))]);
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    const ep = sub.endpoint;
    await sub.unsubscribe();
    await api("/api/push/disiscrivi", { method: "POST", body: JSON.stringify({ endpoint: ep }) });
  } catch { /* non è un motivo per restare dentro */ }
}

let accessoAperto = false;
function sessioneScaduta() {
  if (accessoAperto) return;
  accessoAperto = true;
  svuotaDatiLocali().then(() => mostraAccesso(t("accesso.sessione_finita")));
}

// `aiuto`: la spiegazione sotto il campo, fuori dall'etichetta (non entra nel nome del campo) e legata con aria-describedby
const campoAccesso = (id, etichetta, tipo, extra = "", aiuto = "") =>
  `<label class="accesso-campo"><span class="debole piccolo">${etichetta}</span><input class="campo-testo" id="${id}" type="${tipo}" ${extra}${aiuto ? ` aria-describedby="${id}-aiuto"` : ""}></label>`
  + (aiuto ? `<div class="debole piccolo accesso-aiuto" id="${id}-aiuto">${aiuto}</div>` : "");
const CAMPO_NOME = () => campoAccesso("ac-nome", t("accesso.nome_utente"), "text", 'autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" maxlength="64" required');
const SENZA_AIUTI = 'autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false" maxlength="40" required';
const CAMPO_PW = 'autocapitalize="none" autocorrect="off" spellcheck="false" maxlength="200" required';
const SCHEDE_ACCESSO = ["accedi", "registra"];          // «Password dimenticata» è un link sotto il modulo, non una scheda
const CAMPO_EMAIL = (id, facoltativa) => campoAccesso(id, facoltativa ? t("accesso.email_facoltativa") : t("accesso.email"), "email",
  `autocomplete="email" autocapitalize="none" autocorrect="off" spellcheck="false" maxlength="254"${facoltativa ? "" : " required"}`,
  facoltativa ? t("accesso.email_facoltativa_aiuto") : "");
const CAMPO_CODICE_EMAIL = (id) => campoAccesso(id, t("accesso.codice_email"), "text",
  'autocomplete="one-time-code" inputmode="numeric" pattern="[0-9]*" maxlength="12" autocapitalize="none" autocorrect="off" spellcheck="false" required');
// `extra.sub`: passo dentro la scheda (registra: "verifica"; recupero: "codice" | "email" | "email-codice"); `extra.email`: indirizzo del passo
function campiAccesso(scheda, extra = {}) {
  const modo = stato.registrazione || "invito";
  if (scheda === "accedi") return CAMPO_NOME() + campoAccesso("ac-pw", t("accesso.password"), "password", `autocomplete="current-password" ${CAMPO_PW}`);
  if (scheda === "registra" && extra.sub === "verifica") return `<div class="debole piccolo">${t("accesso.verifica_spiega", { email: esc(extra.email || "") })}</div>`
    + CAMPO_CODICE_EMAIL("ac-codice-email");
  if (scheda === "registra") return `<div class="debole piccolo">${modo === "aperta" ? t("accesso.serve_email") : modo === "email" ? t("accesso.serve_invito_email") : t("accesso.serve_invito")}</div>`
    + (modo === "aperta" ? "" : campoAccesso("ac-invito", t("accesso.codice_invito"), "text", SENZA_AIUTI + valoreInvito())) + CAMPO_NOME()
    + (stato.emailAttiva === false && modo === "invito" ? "" : CAMPO_EMAIL("ac-email", modo === "invito"))
    + campoAccesso("ac-pw", t("accesso.password_10"), "password", `autocomplete="new-password" minlength="10" ${CAMPO_PW}`)
    + `<label class="interruttore accesso-letto"><span>${t("accesso.letto", { privacy: linkLegale("privacy", "legale.privacy"), termini: linkLegale("termini", "legale.termini"), eta: ETA_MINIMA })}</span><input type="checkbox" id="ac-letto"></label>`;
  if (extra.sub === "email") return `<div class="debole piccolo">${t("accesso.recupero_email_spiega")}</div>` + CAMPO_EMAIL("ac-email", false);
  if (extra.sub === "email-codice") return `<div class="debole piccolo">${t("accesso.recupero_codice_email_spiega", { email: esc(extra.email || "") })}</div>`
    + CAMPO_CODICE_EMAIL("ac-codice-email")
    + campoAccesso("ac-pw", t("accesso.password_nuova_10"), "password", `autocomplete="new-password" minlength="10" ${CAMPO_PW}`);
  return `<div class="debole piccolo">${t("accesso.recupero_spiega")}</div>`
    + CAMPO_NOME() + campoAccesso("ac-codice", t("accesso.codice"), "text", SENZA_AIUTI)
    + campoAccesso("ac-pw", t("accesso.password_nuova_10"), "password", `autocomplete="new-password" minlength="10" ${CAMPO_PW}`);
}
// il testo del pulsante di invio, a seconda del passo
function testoInvio(scheda, sub) {
  if (scheda === "registra" && sub === "verifica") return t("accesso.invio_verifica");
  if (scheda === "recupero" && sub === "email") return t("accesso.invio_recupero_email");
  return t("accesso.invio_" + scheda);
}

// La pagina di accesso copre tutto: finché non si entra, dell'app non si vede (e non si carica) niente.
function mostraAccesso(messaggio = "", scheda = "accedi", extra = {}) {
  accessoAperto = true;
  if (scheda === "recupero" && !extra.sub) extra = { ...extra, sub: (stato.registrazione || "invito") === "invito" || stato.emailAttiva === false ? "codice" : "email" };
  stato.account = null;
  document.body.classList.add("senza-accesso");
  contenuto.innerHTML = "";
  let el = $("#accesso");
  const primaVolta = !el;
  if (!el) {
    el = document.createElement("div");
    el.id = "accesso"; el.className = "accesso";
    el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); el.setAttribute("aria-label", t("accesso.nome_aria"));
    document.body.appendChild(el);
  }
  el.innerHTML = `<div class="carta accesso-corpo${primaVolta ? " primo" : ""}">
    <div class="accesso-marchio">${marchio(72, true)}</div>
    <h1 class="accesso-titolo">SchieraXI</h1>
    <div class="segmenti" id="accesso-schede">${SCHEDE_ACCESSO.map(k => `<button type="button" data-s="${k}" class="${k === scheda ? "attivo" : ""}" aria-pressed="${k === scheda}">${t("accesso.scheda_" + k)}</button>`).join("")}</div>
    <div id="accesso-msg" role="alert">${messaggio ? `<div class="attenzione">${esc(messaggio)}</div>` : ""}</div>
    ${socialPronto() && SCHEDE_ACCESSO.includes(scheda) && extra.sub !== "verifica" ? `<div class="accesso-social">${htmlGoogle(t("social.continua"))}<div class="accesso-oppure debole piccolo" aria-hidden="true"><span>${t("social.oppure")}</span></div></div>` : ""}
    ${scheda === "recupero" && stato.emailAttiva !== false && (extra.sub === "email" || extra.sub === "codice") ? `<div class="segmenti" id="accesso-metodi">${[["email", t("accesso.recupero_con_email")], ["codice", t("accesso.recupero_con_codice")]].map(([k, c]) => `<button type="button" data-m="${k}" class="${k === extra.sub ? "attivo" : ""}" aria-pressed="${k === extra.sub}">${c}</button>`).join("")}</div>` : ""}
    <form id="accesso-form" novalidate>${campiAccesso(scheda, extra)}
      <div class="pulsanti"><button class="bottone" type="submit" id="accesso-invia">${testoInvio(scheda, extra.sub)}</button></div></form>
    ${scheda === "accedi" ? `<p class="accesso-legale"><a href="#" id="accesso-dimenticata">${t("accesso.scheda_recupero")}</a></p>` : ""}
    ${scheda === "recupero" ? `<p class="accesso-legale"><a href="#" id="accesso-torna">${t("accesso.torna")}</a></p>` : ""}
    <p class="debole piccolo accesso-legale">${linkLegali()}</p></div>`;
  el.querySelectorAll("#accesso-schede button").forEach(b => b.addEventListener("click", () => mostraAccesso("", b.dataset.s)));
  const vaiA = (id, scheda_) => { const a = el.querySelector(id); if (a) a.addEventListener("click", ev => { ev.preventDefault(); mostraAccesso("", scheda_); }); };
  vaiA("#accesso-dimenticata", "recupero"); vaiA("#accesso-torna", "accedi");
  el.querySelectorAll("#accesso-metodi button").forEach(b => b.addEventListener("click", () => mostraAccesso("", "recupero", { sub: b.dataset.m })));
  collegaGoogleAccesso(el);
  const primo = $("#accesso-form input");
  if (primo && !messaggio) primo.focus();
  let inCorso = false;                                   // un invio alla volta (doppio tocco, Invio ripetuto)
  $("#accesso-form").addEventListener("submit", async ev => {
    ev.preventDefault();
    if (inCorso) return;
    const v = id => ($(id) ? $(id).value : "");
    const invia = $("#accesso-invia");
    const manda = (percorso, corpo) => api(percorso, { method: "POST", body: JSON.stringify(corpo), timeout: 30000 });
    inCorso = true; invia.disabled = true; invia.setAttribute("aria-busy", "true");
    $("#accesso-msg").textContent = "";
    try {
      if (scheda === "accedi") {
        await manda("/api/account/accedi", { nome_utente: v("#ac-nome"), password: v("#ac-pw") });
        location.reload();
        return;
      } else if (scheda === "registra" && extra.sub === "verifica") {
        const r = await manda("/api/account/registra/conferma", { email: extra.email, codice: v("#ac-codice-email").trim(), iscrizione: extra.iscrizione || "" });
        if (!r || !r.codice_recupero) throw new Error(t("accesso.risposta_incompleta_accedi"));
        dimenticaInvito();
        mostraCodiceAccesso(t("accesso.account_creato"), r.codice_recupero, t("accesso.entra"), () => location.reload());
      } else if (scheda === "registra") {
        if (!$("#ac-letto").checked) { const e = new Error(t("accesso.spunta_letto", { eta: ETA_MINIMA })); e.status = 400; throw e; }       // controllo locale: la password resta
        const corpo = { nome_utente: v("#ac-nome"), password: v("#ac-pw"), invito: v("#ac-invito"), accetto_termini: true };      // la casella è spuntata (controllo qui sopra)
        const email = $("#ac-email") ? v("#ac-email").trim() : "";
        if (email) corpo.email = email;                      // facoltativa: i server vecchi non la conoscono
        const r = await manda("/api/account/registra", corpo);
        if (r && r.verifica_email) { mostraAccesso("", "registra", { sub: "verifica", email, iscrizione: r.iscrizione || "" }); return; }   // l'account nasce col codice (legato a questa richiesta)
        if (!r || !r.codice_recupero) throw new Error(t("accesso.risposta_incompleta_accedi"));
        dimenticaInvito();
        mostraCodiceAccesso(t("accesso.account_creato"), r.codice_recupero, t("accesso.entra"), () => location.reload());
      } else if (extra.sub === "email") {
        const email = v("#ac-email").trim();
        await manda("/api/account/recupero-email", { email });
        mostraAccesso(t("accesso.codice_inviato"), "recupero", { sub: "email-codice", email });
        return;
      } else if (extra.sub === "email-codice") {
        const r = await manda("/api/account/recupero-email/conferma", { email: extra.email, codice: v("#ac-codice-email").trim(), nuova: v("#ac-pw") });
        if (!r || !r.codice_recupero) throw new Error(t("accesso.risposta_incompleta"));
        mostraCodiceAccesso(t("accesso.password_cambiata"), r.codice_recupero, t("accesso.vai_accesso"), () => mostraAccesso(t("accesso.password_cambiata_accedi")));
      } else {
        const r = await manda("/api/account/recupero", { nome_utente: v("#ac-nome"), codice: v("#ac-codice"), nuova: v("#ac-pw") });
        if (!r || !r.codice_recupero) throw new Error(t("accesso.risposta_incompleta"));
        mostraCodiceAccesso(t("accesso.password_cambiata"), r.codice_recupero, t("accesso.vai_accesso"), () => mostraAccesso(t("accesso.password_cambiata_accedi")));
      }
    } catch (e) {
      const attesa = e.status === 429 && e.riprova ? (e.riprova < 90 ? t("accesso.riprova_secondi", { n: e.riprova }) : e.riprova < 3600 ? t("accesso.riprova_minuti", { n: Math.ceil(e.riprova / 60) }) : t("accesso.riprova_ore", { n: Math.max(1, Math.round(e.riprova / 3600)) })) : "";
      const msg = document.createElement("div");
      msg.className = "errore"; msg.textContent = (e.message || t("accesso.errore_generico")) + attesa;
      if ($("#accesso-msg")) $("#accesso-msg").replaceChildren(msg);
      // la password si svuota solo se è stata rifiutata (accesso o codice sbagliato: 401/403); un errore di compilazione (400, 422),
      // una casella non spuntata o l'attesa (429) non fanno perdere quello che hai scritto
      if ($("#ac-pw") && (e.status === 401 || e.status === 403)) $("#ac-pw").value = "";
      invia.disabled = false; invia.removeAttribute("aria-busy");
    } finally { inCorso = false; }
  });
}

// ---------------------------------------------------------------- Accesso con Google
// Il giro con Google lo fa il server. Qui: si crea un segreto che resta in questa scheda, si apre l'indirizzo di Google e,
// al ritorno, si riscatta il codice monouso mostrando il segreto. Il pulsante c'è solo se il server ha Google acceso (stato.social).
const socialPronto = () => Array.isArray(stato.social) && stato.social.includes("google");
const soloGoogle = () => !!(stato.accessi && stato.accessi.password === false);          // account senza password: entra solo con Google
const GOOGLE_G = `<svg class="google-g" viewBox="0 0 48 48" width="20" height="20" aria-hidden="true" focusable="false"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>`;
const htmlGoogle = (testo, id = "") => `<button type="button" class="bottone-google"${id ? ` id="${id}"` : ' data-google="accedi"'}>${GOOGLE_G}<span>${esc(testo)}</span></button>`;
const base64url = byte => btoa(String.fromCharCode(...new Uint8Array(byte))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

// Il testo per l'utente di ogni errore con nome breve (il server manda `codice`); gli altri usano il messaggio del server.
function erroreGoogle(e) {
  const chiave = { email_gia_usata: "social.email_gia_usata", email_non_affidabile: "social.email_non_affidabile", google_gia_collegato: "social.google_gia_collegato",
    google_diverso: "social.google_diverso", ultimo_accesso: "social.ultimo_accesso", serve_riconferma: "social.serve_riconferma" }[e && e.codice];
  return chiave ? t(chiave) : (e && e.message) || t("social.errore");
}

async function avviaGoogle(scopo, password = "") {
  if (!(window.crypto && crypto.subtle)) throw new Error(t("social.browser_vecchio"));
  const verificatore = base64url(crypto.getRandomValues(new Uint8Array(48)));
  const sfida = base64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verificatore)));
  const r = await api("/api/account/social/google/inizia", { method: "POST", body: JSON.stringify({ scopo, sfida, piattaforma: "web", password }), timeout: 30000 });
  if (!r || typeof r.url !== "string" || !r.url.startsWith("https://accounts.google.com/")) throw new Error(t("social.errore"));
  try { sessionStorage.setItem("social", JSON.stringify({ v: verificatore, scopo })); } catch { throw new Error(t("social.altro_browser")); }
  location.assign(r.url);
}

function collegaGoogleAccesso(el) {
  const b = el.querySelector("[data-google]");
  if (!b) return;
  b.addEventListener("click", async () => {
    b.disabled = true;
    try { await avviaGoogle("accedi"); }
    catch (e) {
      b.disabled = false;
      const msg = document.createElement("div");
      msg.className = "errore"; msg.textContent = erroreGoogle(e);
      if ($("#accesso-msg")) $("#accesso-msg").replaceChildren(msg);
    }
  });
}

// Link d'invito (`https://<indirizzo>/?invito=CODICE`): il codice si legge, si toglie subito dall'indirizzo (niente cronologia
// col codice) e si tiene per la sessione del browser, così resta anche passando da «Accedi con Google» e ritorno.
function invitoDaIndirizzo(search) {
  let v = "";
  try { v = new URLSearchParams(search || "").get("invito") || ""; } catch { return ""; }
  v = v.toUpperCase().replace(/[^A-Z0-9-]/g, "");
  return v.length >= 4 && v.length <= 40 ? v : "";
}
function invitoSalvato() {
  try { return sessionStorage.getItem("invito") || ""; } catch { return ""; }
}
function leggiInvitoDaLink() {
  const v = invitoDaIndirizzo(location.search);
  if (v) {
    try { const u = new URL(location.href); u.searchParams.delete("invito"); history.replaceState(null, "", u.pathname + u.search + u.hash); } catch { /* niente cronologia */ }
    try { sessionStorage.setItem("invito", v); } catch { /* niente memoria */ }
  }
  return v || invitoSalvato();
}
const dimenticaInvito = () => { try { sessionStorage.removeItem("invito"); } catch { /* niente memoria */ } };
const valoreInvito = () => (invitoSalvato() ? ` value="${esc(invitoSalvato())}"` : "");
const linkInvito = codice => `${location.origin}/?invito=${encodeURIComponent(codice)}`;

// Al ritorno da Google l'indirizzo porta `?social=<codice>` o `?social_errore=<motivo>`: si leggono e si tolgono subito dall'indirizzo.
function leggiRitornoGoogle() {
  let p;
  try { p = new URLSearchParams(location.search); } catch { return null; }
  const codice = p.get("social"), errore = p.get("social_errore");
  if (!codice && !errore) return null;
  try { history.replaceState(null, "", "/"); } catch { /* niente cronologia */ }
  let salvato = null;
  try { salvato = JSON.parse(sessionStorage.getItem("social") || "null"); sessionStorage.removeItem("social"); } catch { /* niente memoria */ }
  return { codice, errore, verificatore: salvato && salvato.v };
}

// `dentro`: c'è già una sessione (collega, riconferma); altrimenti si è alla pagina di accesso.
async function gestisciRitornoGoogle(rit, dentro) {
  const fallito = testo => { if (dentro) { if (testo) avviso(testo, 6000); } else mostraAccesso(testo); };
  if (rit.errore) { fallito(rit.errore === "annullato" ? "" : t("social.errore")); return; }          // annullato: si torna alla schermata senza errori rossi
  if (!rit.verificatore || !rit.codice) { fallito(t("social.altro_browser")); return; }
  try {
    const r = await api("/api/account/social/scambio", { method: "POST", body: JSON.stringify({ codice: rit.codice, verificatore: rit.verificatore }), timeout: 30000 });
    if (r && r.stato === "ok") { location.reload(); return; }
    if (r && r.stato === "nuovo") { mostraAccesso(); mostraNuovoGoogle(r); return; }
    if (r && (r.stato === "collegato" || r.stato === "riconfermato")) {
      if (r.accessi) stato.accessi = r.accessi;
      iniziale = "impostazioni"; stato.impDaUrl = "account";
      avviso(t(r.stato === "collegato" ? "social.collegato_ok" : "social.riconfermato_ok"), 6000);
      return;
    }
    fallito(t("social.errore"));
  } catch (e) { fallito(erroreGoogle(e)); }
}

// Primo accesso con Google: un passo solo, il nome utente (e il codice d'invito se il server lo chiede).
function mostraNuovoGoogle(r, messaggio = "") {
  const el = $("#accesso");
  el.innerHTML = `<div class="carta accesso-corpo"><div class="accesso-marchio">${marchio(72, true)}</div>
    <h1 class="accesso-titolo">${t("social.scegli_nome")}</h1>
    <div class="debole piccolo">${t("social.scegli_spiega")}</div>
    <div id="accesso-msg" role="alert">${messaggio ? `<div class="errore">${esc(messaggio)}</div>` : ""}</div>
    <form id="accesso-form" novalidate>
      ${campoAccesso("ac-nome", t("accesso.nome_utente"), "text", `value="${esc(r.nome_suggerito || "")}" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" maxlength="64" required`)}
      ${r.serve_invito ? campoAccesso("ac-invito", t("accesso.codice_invito"), "text", SENZA_AIUTI + valoreInvito()) : ""}
      <label class="interruttore accesso-letto"><span>${t("accesso.letto", { privacy: linkLegale("privacy", "legale.privacy"), termini: linkLegale("termini", "legale.termini"), eta: ETA_MINIMA })}</span><input type="checkbox" id="ac-letto"></label>
      <div class="pulsanti"><button class="bottone" type="submit" id="accesso-invia">${t("social.crea")}</button></div></form>
    <p class="accesso-legale"><a href="#" id="accesso-torna">${t("accesso.torna")}</a></p>
    <p class="debole piccolo accesso-legale">${linkLegali()}</p></div>`;
  $("#accesso-torna").addEventListener("click", ev => { ev.preventDefault(); mostraAccesso(); });
  let inCorso = false;
  $("#accesso-form").addEventListener("submit", async ev => {
    ev.preventDefault();
    if (inCorso) return;
    const invia = $("#accesso-invia");
    const mostra = testo => { const m = document.createElement("div"); m.className = "errore"; m.textContent = testo; $("#accesso-msg").replaceChildren(m); };
    if (!$("#ac-letto").checked) { mostra(t("accesso.spunta_letto", { eta: ETA_MINIMA })); return; }
    inCorso = true; invia.disabled = true; invia.setAttribute("aria-busy", "true");
    try {
      await api("/api/account/social/completa", { method: "POST", timeout: 30000,
        body: JSON.stringify({ iscrizione: r.iscrizione, nome_utente: $("#ac-nome").value, invito: $("#ac-invito") ? $("#ac-invito").value : "", accetto_termini: true }) });
      dimenticaInvito();
      location.reload();
    } catch (e) {
      mostra(erroreGoogle(e));
      invia.disabled = false; invia.removeAttribute("aria-busy");
    } finally { inCorso = false; }
  });
}

// Impostazioni > Il tuo account > Accessi: password sì/no, Google collegato o no, conferma con Google per chi non ha password.
function htmlAccessi() {
  const ac = stato.accessi || { password: true, social: [] };
  const g = (ac.social || []).find(s => s.provider === "google");
  return `<div>${ac.password ? t("social.password_si") : t("social.password_no")}</div>
    <div>${g ? t("social.google_collegato", { email: esc(g.email || t("social.google_account")) }) : t("social.google_non_collegato")}</div>
    ${!g && ac.password ? `<label class="accesso-campo"><span class="debole piccolo">${t("social.password_collega")}</span><input class="campo-testo" id="acc-google-pw" type="password" autocomplete="current-password" maxlength="200"></label>` : ""}
    <div class="pulsanti">${g ? `<button class="bottone secondario" id="acc-google-scollega">${t("social.scollega")}</button>` : htmlGoogle(t("social.collega"), "acc-google-collega")}</div>
    ${soloGoogle() ? `<div class="debole piccolo">${t("social.conferma_spiega")}</div><div class="pulsanti">${htmlGoogle(t("social.conferma"), "acc-google-conferma")}</div>` : ""}`;
}
function collegaAccessi() {
  const prova = fai => async () => { try { await fai(); } catch (e) { avviso(erroreGoogle(e), 6000); } };
  const vai_ = (id, scopo) => { const b = $(id); if (b) b.addEventListener("click", prova(() => avviaGoogle(scopo))); };
  vai_("#acc-google-conferma", "riconferma");
  const col = $("#acc-google-collega");                                  // collegare Google chiede la password dell'account
  if (col) col.addEventListener("click", prova(async () => {
    const pw = $("#acc-google-pw") ? $("#acc-google-pw").value : "";
    if ($("#acc-google-pw") && !pw) { avviso(t("social.serve_password"), 5000); return; }
    await avviaGoogle("collega", pw);
  }));
  const s = $("#acc-google-scollega");
  if (s) s.addEventListener("click", prova(async () => {
    if (!confirm(t("social.scollega_conferma"))) return;
    const r = await api("/api/account/social/google", { method: "DELETE" });
    stato.accessi = r.accessi;
    $("#acc-accessi").innerHTML = htmlAccessi(); collegaAccessi();
    avviso(t("social.scollegato_ok"), 4000);
  }));
}

// Un codice che si vede una volta sola: va copiato prima di andare avanti.
function htmlCodiceUnaVolta(codice) {
  return `<p>${t("codice.a_cosa_serve")}</p><div class="attenzione"><b>${t("codice.salva")}</b> ${t("codice.spiega")}</div>
    <div class="codice-una-volta" id="codice-una-volta">${esc(codice)}</div>
    <div class="pulsanti"><button class="bottone secondario" type="button" id="copia-codice">${t("codice.copia")}</button></div>`;
}
function collegaCopiaCodice(codice) {
  $("#copia-codice").addEventListener("click", async () => avviso(await copiaTesto(codice) ? t("codice.copiato") : t("codice.non_copio")));
}
function mostraCodiceAccesso(titolo, codice, continua, dopo) {
  $("#accesso").innerHTML = `<div class="carta accesso-corpo"><h1 class="accesso-titolo">${esc(titolo)}</h1>
    <h2>${t("codice.titolo")}</h2>${htmlCodiceUnaVolta(codice)}
    <label class="interruttore"><span>${t("codice.salvato")}</span><input type="checkbox" id="codice-salvato"></label>
    <div class="pulsanti"><button class="bottone" id="codice-continua" disabled>${esc(continua)}</button></div></div>`;
  collegaCopiaCodice(codice);
  $("#codice-salvato").addEventListener("change", ev => { $("#codice-continua").disabled = !ev.target.checked; });
  $("#codice-continua").addEventListener("click", dopo);
}

async function esciDa(percorso) {
  await lasciaNotifiche();
  try { await api(percorso, { method: "POST" }); } catch { /* se la sessione era già finita, va bene lo stesso */ }
  await svuotaDatiLocali();
  location.reload();
}

// Email dell'account: aggiungere/cambiare (codice a 6 cifre per posta), confermare, togliere. Tutti i valori dell'utente passano da esc().
function htmlEmailAccount() {
  const e = stato.emailAccount || {};
  if (stato.emailAttiva === false && !e.email) return `<div class="debole piccolo">${t("account.email_spenta")}</div>`;
  const daGoogle = !!e.email && e.email_origine === "google";            // solo da mostrare: non vale per il recupero e non si «toglie» qui
  const propria = !!e.email && !daGoogle;
  return `<div>${propria ? t("account.email_verificata", { email: esc(e.email) }) : daGoogle ? t("account.email_google", { email: esc(e.email) }) : t("account.email_nessuna")}</div>`
    + (daGoogle ? `<div class="debole piccolo">${t("account.email_google_nota")}</div>` : "")
    + (e.email_in_attesa ? `<div class="attenzione">${t("account.email_attesa", { email: esc(e.email_in_attesa) })}</div>`
      + campoAccesso("acc-email-codice", t("account.email_codice"), "text", 'autocomplete="one-time-code" inputmode="numeric" pattern="[0-9]*" maxlength="12" spellcheck="false"')
      + `<div class="pulsanti"><button class="bottone" id="acc-email-conferma">${t("account.email_conferma")}</button></div>` : "")
    + campoAccesso("acc-email-nuova", t("account.email_nuova"), "email", 'autocomplete="email" autocapitalize="none" spellcheck="false" maxlength="254"')
    + (soloGoogle() ? "" : campoAccesso("acc-email-pw", t("account.la_tua_password"), "password", 'autocomplete="current-password" maxlength="200"'))
    + `<div class="pulsanti"><button class="bottone secondario" id="acc-email-invia">${t("account.email_invia")}</button>`
    + (propria ? `<button class="bottone secondario" id="acc-email-togli">${t("account.email_togli")}</button>` : "") + `</div>`;
}
async function aggiornaEmailAccount() {
  const me = await api("/api/account/me");
  stato.emailAccount = { email: me.email || null, email_origine: me.email_origine || null, email_in_attesa: me.email_in_attesa || null };
  const dove = $("#acc-email");
  if (dove) { dove.innerHTML = htmlEmailAccount(); collegaEmailAccount(); }
}
function collegaEmailAccount() {
  const prova = (cosa, fai) => async () => { try { await fai(); } catch (e) { avviso(e.message || cosa, 6000); } };
  const val = id => ($(id) ? $(id).value : "");
  const conPassword = () => { if (!soloGoogle() && !val("#acc-email-pw")) { avviso(t("account.email_serve_password")); return false; } return true; };
  const dopo = async messaggio => { avviso(messaggio, 5000); await aggiornaEmailAccount(); };
  if ($("#acc-email-invia")) $("#acc-email-invia").addEventListener("click", prova(t("account.email_no"), async () => {
    if (!conPassword()) return;
    await api("/api/account/email", { method: "POST", body: JSON.stringify({ email: val("#acc-email-nuova").trim(), password: val("#acc-email-pw") }) });
    await dopo(t("account.email_inviato"));
  }));
  if ($("#acc-email-conferma")) $("#acc-email-conferma").addEventListener("click", prova(t("account.email_no"), async () => {
    await api("/api/account/email/conferma", { method: "POST", body: JSON.stringify({ codice: val("#acc-email-codice").trim() }) });
    await dopo(t("account.email_confermata_ok"));
  }));
  if ($("#acc-email-togli")) $("#acc-email-togli").addEventListener("click", prova(t("account.email_no"), async () => {
    if (!conPassword()) return;
    await api("/api/account/email/togli", { method: "POST", body: JSON.stringify({ password: val("#acc-email-pw") }) });
    await dopo(t("account.email_tolta_ok"));
  }));
}

function schedaAccount() {
  const a = stato.account;
  if (!a) return "";
  const campo = (id, etichetta, extra = "") => `<label class="accesso-campo"><span class="debole piccolo">${etichetta}</span><input class="campo-testo" id="${id}" type="password" ${extra}></label>`;
  const data = new Date(a.creato).toLocaleDateString(t("lingua.locale"), { day: "numeric", month: "long", year: "numeric" });
  return `<div class="carta" id="scheda-account">
    <div><b class="nome-account">${esc(a.nome_visualizzato || a.nome_utente)}</b><span class="debole piccolo" style="display:block">${t("account.dal", { ruolo: a.ruolo === "amministratore" ? t("account.ruolo_admin") : t("account.ruolo_utente"), data })}</span></div>
    ${socialPronto() || (stato.accessi && stato.accessi.social && stato.accessi.social.length) ? `<details style="margin-top:14px"${soloGoogle() ? " open" : ""}><summary>${t("social.accessi")}</summary>
      <div id="acc-accessi">${htmlAccessi()}</div></details>` : ""}
    <details style="margin-top:14px"><summary>${soloGoogle() ? t("social.aggiungi_password") : t("account.cambia_password")}</summary>
      ${soloGoogle() ? `<div class="debole piccolo">${t("social.aggiungi_spiega")}</div>` : campo("acc-attuale", t("account.password_attuale"), 'autocomplete="current-password"')}${campo("acc-nuova", t("accesso.password_nuova_10"), 'autocomplete="new-password"')}${campo("acc-ripeti", t("account.ripeti_password"), 'autocomplete="new-password"')}
      <p class="attenzione piccolo" id="acc-diverse" role="status" hidden>${t("account.password_diverse")}</p>
      <div class="pulsanti"><button class="bottone" id="acc-cambia">${soloGoogle() ? t("social.aggiungi_password") : t("account.cambia_password")}</button></div>
      <div id="acc-esito-password"></div>
      ${soloGoogle() ? "" : `<div class="debole piccolo">${t("account.altri_scollegati")}</div>`}</details>
    <details><summary>${t("account.email")}</summary>
      <div class="debole piccolo">${t("account.email_spiega")}</div>
      <div id="acc-email">${htmlEmailAccount()}</div></details>
    ${soloGoogle() ? "" : `<details><summary>${t("account.recupero")}</summary>
      <div class="debole piccolo">${t("account.recupero_spiega")}</div>
      ${campo("acc-pw-codice", t("account.la_tua_password"), 'autocomplete="current-password"')}
      <div class="pulsanti"><button class="bottone secondario" id="acc-nuovo-codice">${t("account.nuovo_codice")}</button></div><div id="acc-esito-codice"></div></details>`}
    <details><summary>${t("account.dati_titolo")}</summary>
      <div class="debole piccolo">${t("account.dati_spiega")}</div>
      <div class="pulsanti"><button class="bottone secondario" id="acc-scarica-dati" type="button">${t("account.dati_scarica")}</button></div></details>
    <details><summary>${t("account.elimina_titolo")}</summary>
      <div class="attenzione">${t("account.elimina_avviso")}</div>
      ${soloGoogle() ? `<div class="debole piccolo">${t("social.elimina_spiega")}</div>` : campo("acc-pw-elimina", t("account.la_tua_password"), 'autocomplete="current-password"')}
      <div class="pulsanti"><button class="bottone secondario" id="acc-elimina" style="color:var(--rosso)">${t("account.elimina")}</button></div></details>
    <div class="pulsanti"><button class="bottone secondario" id="acc-esci">${t("account.esci")}</button></div>
  </div>`;
}

// Impostazioni > Il tuo account > «Scarica i tuoi dati» (portabilità, GDPR art. 20): il file JSON dei SOLI dati di chi è dentro.
// Usa l'esportazione di sempre (la sessione sceglie la cartella dell'utente, nessun parametro). Il ripristino non c'è, di proposito.
async function scaricaIMieiDati() {
  const b = $("#acc-scarica-dati");
  if (b) b.disabled = true;
  try {
    const dati = await api("/api/backup");
    const giorno = String((dati && dati.creato) || new Date().toISOString()).slice(0, 10);
    const file = new File([JSON.stringify(dati, null, 2)], `schieraxi-i-miei-dati-${giorno}.json`, { type: "application/json" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {       // iPhone e Android: il foglio Condividi (Salva su File)
      try { await navigator.share({ files: [file], title: t("account.dati_titolo") }); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(file); a.download = file.name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  } catch (e) { avviso(e.message || t("account.dati_no"), 5000); }
  finally { if (b) b.disabled = false; }
}

// Impostazioni > Avanzate (solo amministratore): inviti, codici per chi ha perso la password, utenti, errori del server.
function schedaAmministratore() {
  const a = stato.account;
  return a && a.ruolo === "amministratore" ? `<div class="carta" id="scheda-admin"><h3>${t("admin.titolo")}</h3>
    <h3>${t("admin.invito_titolo")}</h3>
    <div class="debole piccolo">${t("admin.invito_spiega")}</div>
    <label class="accesso-campo"><span class="debole piccolo">${t("admin.etichetta")}</span><input class="campo-testo" id="adm-etichetta" type="text" maxlength="60" autocomplete="off"></label>
    <label class="interruttore"><span>${t("admin.nuovo_admin")}</span><input type="checkbox" id="adm-admin"></label>
    <div class="pulsanti"><button class="bottone" id="adm-invito">${t("admin.crea_invito")}</button></div><div id="adm-esito-invito"></div>
    <h3>${t("admin.reset_titolo")}</h3>
    <div class="debole piccolo">${t("admin.reset_spiega")}</div>
    <label class="accesso-campo"><span class="debole piccolo">${t("accesso.nome_utente")}</span><input class="campo-testo" id="adm-nome" type="text" autocapitalize="none" autocorrect="off" spellcheck="false" autocomplete="off"></label>
    <div class="pulsanti"><button class="bottone secondario" id="adm-reset">${t("admin.genera_codice")}</button></div><div id="adm-esito-reset"></div>
    <h3>${t("admin.utenti_titolo")}</h3><div id="adm-utenti" class="debole piccolo">${t("admin.carico")}</div></div>
  <div class="carta" id="scheda-errori"><h3>${t("errori.titolo")}</h3>
    <div class="debole piccolo">${t("errori.spiega")}</div>
    <div id="adm-registro" class="debole piccolo" aria-live="polite">${t("admin.carico")}</div>
    <div class="pulsanti"><button class="bottone secondario" type="button" id="adm-registro-aggiorna">${t("errori.aggiorna")}</button></div></div>` : "";
}

function collegaAccount() {
  if (!stato.account || !$("#scheda-account")) return;
  const valore = id => ($(id) ? $(id).value : "");        // un campo che non c'è più (pagina già cambiata) vale vuoto, mai un errore
  const mostraCodice = (dove, codice) => {
    if (!$(dove)) return;
    $(dove).innerHTML = htmlCodiceUnaVolta(codice);
    collegaCopiaCodice(codice);
  };
  const provaCosi = async (cosa, fai) => { try { await fai(); } catch (e) { avviso(e.message || cosa, 6000); } };
  collegaEmailAccount();
  $("#acc-esci").addEventListener("click", () => esciDa("/api/account/esci"));
  $("#acc-scarica-dati").addEventListener("click", () => scaricaIMieiDati());
  if ($("#acc-accessi")) collegaAccessi();
  const passwordDiverse = () => valore("#acc-ripeti") !== "" && valore("#acc-nuova") !== valore("#acc-ripeti");
  for (const id of ["#acc-nuova", "#acc-ripeti"]) $(id).addEventListener("input", () => { $("#acc-diverse").hidden = !passwordDiverse(); });
  $("#acc-cambia").addEventListener("click", () => provaCosi(t("account.password_cambiata_no"), async () => {
    if (valore("#acc-nuova") !== valore("#acc-ripeti")) { $("#acc-diverse").hidden = false; throw new Error(t("account.password_diverse")); }
    if (soloGoogle()) {                                                  // chi è entrato con Google aggiunge una password (dopo la conferma con Google)
      let r;
      try { r = await api("/api/account/imposta-password", { method: "POST", body: JSON.stringify({ password: valore("#acc-nuova") }) }); }
      catch (e) { throw new Error(erroreGoogle(e)); }
      $("#acc-nuova").value = ""; $("#acc-ripeti").value = "";
      stato.accessi = { ...stato.accessi, password: true };
      $("#acc-esito-password").innerHTML = htmlCodiceUnaVolta(r.codice_recupero) + `<div class="pulsanti"><button class="bottone" id="acc-password-fatto">${t("social.fatto")}</button></div>`;
      collegaCopiaCodice(r.codice_recupero);
      $("#acc-password-fatto").addEventListener("click", () => vai("impostazioni", "account"));
      avviso(t("social.password_aggiunta"), 6000);
      return;
    }
    await api("/api/account/cambia-password", { method: "POST", body: JSON.stringify({ attuale: valore("#acc-attuale"), nuova: valore("#acc-nuova") }) });
    $("#acc-attuale").value = ""; $("#acc-nuova").value = ""; $("#acc-ripeti").value = "";
    avviso(t("account.password_cambiata_ok"), 5000);
  }));
  if ($("#acc-nuovo-codice")) $("#acc-nuovo-codice").addEventListener("click", () => provaCosi(t("account.nuovo_codice_no"), async () => {
    if (!valore("#acc-pw-codice")) { avviso(t("account.email_serve_password")); return; }
    const r = await api("/api/account/codice-recupero", { method: "POST", body: JSON.stringify({ password: valore("#acc-pw-codice") }) });
    $("#acc-pw-codice").value = "";
    mostraCodice("#acc-esito-codice", r.codice_recupero);
  }));
  $("#acc-elimina").addEventListener("click", () => provaCosi(t("account.elimina_no"), async () => {
    const pw = soloGoogle() ? "" : valore("#acc-pw-elimina");
    if (!soloGoogle() && !pw) { avviso(t("account.elimina_serve_password")); return; }
    if (!confirm(t("account.elimina_conferma"))) return;
    await lasciaNotifiche();
    try { await api("/api/account/elimina", { method: "POST", body: JSON.stringify({ password: pw }) }); }
    catch (e) { throw new Error(erroreGoogle(e)); }
    await svuotaDatiLocali();
    location.reload();
  }));
}

function collegaAmministratore() {
  if (!stato.account || stato.account.ruolo !== "amministratore" || !$("#scheda-admin")) return;
  const valore = id => ($(id) ? $(id).value : "");
  const mostraCodice = (dove, codice) => {
    if (!$(dove)) return;
    $(dove).innerHTML = htmlCodiceUnaVolta(codice);
    collegaCopiaCodice(codice);
  };
  const provaCosi = async (cosa, fai) => { try { await fai(); } catch (e) { avviso(e.message || cosa, 6000); } };
  $("#adm-invito").addEventListener("click", () => provaCosi(t("admin.crea_invito_no"), async () => {
    const r = await api("/api/admin/inviti", { method: "POST", body: JSON.stringify({ etichetta: valore("#adm-etichetta"), amministratore: $("#adm-admin").checked }) });
    $("#adm-etichetta").value = "";
    mostraInvito(r);
    caricaUtenti();
  }));
  const mostraInvito = r => {
    const dove = $("#adm-esito-invito");
    if (!dove) return;
    const link = linkInvito(r.codice), messaggio = t("admin.invito_messaggio", { link, giorni: r.valido_giorni });
    const condividi = typeof navigator.share === "function";
    dove.innerHTML = `<div class="debole piccolo">${t("admin.invito_esito", { etichetta: esc(r.etichetta), giorni: r.valido_giorni })}</div>
      <div class="attenzione">${t("admin.invito_manda")}</div>
      <div class="codice-una-volta piccolo" id="adm-link-invito">${esc(link)}</div>
      <div class="pulsanti">${condividi ? `<button class="bottone" type="button" id="adm-condividi">${t("admin.invito_condividi")}</button>` : ""}
        <button class="bottone ${condividi ? "secondario" : ""}" type="button" id="adm-copia-messaggio">${t("admin.invito_copia_messaggio")}</button></div>
      <div class="debole piccolo">${t("admin.invito_codice_app", { codice: esc(r.codice) })}</div>`;
    $("#adm-copia-messaggio").addEventListener("click", async () => avviso(await copiaTesto(messaggio) ? t("admin.invito_copiato") : t("codice.non_copio")));
    if (condividi) $("#adm-condividi").addEventListener("click", async () => {
      try { await navigator.share({ title: "SchieraXI", text: messaggio }); }
      catch (e) { if (e && e.name !== "AbortError") avviso(await copiaTesto(messaggio) ? t("admin.invito_copiato") : t("codice.non_copio")); }
    });
  };
  $("#adm-reset").addEventListener("click", () => provaCosi(t("account.nuovo_codice_no"), async () => {
    const r = await api("/api/admin/reset-password", { method: "POST", body: JSON.stringify({ nome_utente: valore("#adm-nome") }) });
    mostraCodice("#adm-esito-reset", r.codice);
    $("#adm-esito-reset").insertAdjacentHTML("afterbegin", `<div class="debole piccolo">${t("admin.reset_esito", { ore: r.valido_ore })}</div>`);
  }));
  const caricaUtenti = async () => {
    try {
      const r = await api("/api/admin/utenti");
      if (!$("#adm-utenti")) return;
      const elenco = r.utenti.map(u => esc(u.nome_visualizzato || u.nome_utente) + (u.ruolo === "amministratore" ? t("admin.admin_breve") : "")).join(", ");
      $("#adm-utenti").innerHTML = tp("admin.utenti_riepilogo", r.utenti.length, { massimo: r.massimo, elenco });
    } catch (e) { if ($("#adm-utenti")) $("#adm-utenti").textContent = e.message; }
  };
  caricaUtenti();
  const caricaRegistro = async () => {
    const dove = $("#adm-registro");
    if (!dove) return;
    try {
      const r = await api("/api/admin/registro"), c = r.contatori;
      const quando = q => esc(String(q).replace("T", " ").replace(/\+00:00$/, " UTC"));
      const righe = (elenco, vuoto, testo) => elenco.length ? `<ul class="registro-elenco">${elenco.map(testo).join("")}</ul>` : `<p>${vuoto}</p>`;
      dove.innerHTML = `<p>${t("errori.riepilogo", { richieste: c.richieste, rifiutate: c.rifiutate, errori: c.errori, medio: c.tempo_medio_ms, p95: c.tempo_p95_ms, max: c.tempo_max_ms })}</p>
        <h3>${t("errori.del_server")}</h3>${righe(r.errori, t("errori.nessun_errore"), e => `<li>${quando(e.quando)} · ${esc(e.metodo || "")} ${esc(e.rotta || "")} · ${esc(e.stato || "")} ${esc(e.errore || "")}</li>`)}
        <h3>${t("errori.sicurezza")}</h3>${righe(r.sicurezza, t("errori.nessun_evento"), e => `<li>${quando(e.quando)} · ${esc(e.tipo)}${e.nome ? " · " + esc(e.nome) : ""}${e.ip ? " · " + esc(e.ip) : ""}</li>`)}
        <h3>${t("errori.lente")}</h3>${righe(c.piu_lente, t("errori.ancora_niente"), p => `<li>${t("errori.lenta_riga", { rotta: esc(p.rotta), richieste: p.richieste, medio: p.medio_ms })}</li>`)}`;
    } catch (e) { dove.textContent = e.message; }
  };
  $("#adm-registro-aggiorna").addEventListener("click", caricaRegistro);
  caricaRegistro();
}

// Prima di tutto: chi sono? Senza account sul server (come oggi) risponde «utente locale» e l'app parte come sempre.
async function controllaAccesso() {
  let r, dati = null;
  try {
    r = await fetch("/api/account/me", { headers: { "X-Fanta": "1" } });
    try { dati = await r.json(); } catch { /* risposta vuota */ }
  } catch {
    // server non raggiungibile: si riparte con l'ultimo utente conosciuto, così le copie salvate si aprono lo stesso
    try { stato.account = JSON.parse(localStorage.getItem("account") || "null"); } catch { stato.account = null; }
    return true;
  }
  if (dati && dati.registrazione) stato.registrazione = dati.registrazione;
  stato.social = dati && Array.isArray(dati.social) ? dati.social : [];                    // servizi di accesso accesi sul server (per ora «google»)
  stato.accessi = dati && dati.accessi ? dati.accessi : null;
  stato.emailAttiva = !(dati && dati.email_attiva === false);                               // server vecchio (campo assente): come prima
  const ritornoGoogle = leggiRitornoGoogle();                                              // se si torna da Google: codice o errore nell'indirizzo
  const invito = leggiInvitoDaLink();                                                      // link d'invito: `?invito=CODICE`
  if (r.status === 401 && dati && dati.multiutente) {
    if (ritornoGoogle) await gestisciRitornoGoogle(ritornoGoogle, false); else mostraAccesso("", invito ? "registra" : "accedi");
    return false;
  }
  if (r.ok && dati && dati.multiutente) {
    stato.account = dati.utente;
    if (usaLinguaDi(dati.utente && dati.utente.nome_utente)) return false;           // l'utente aveva scelto un'altra lingua: ricarico con la sua
    stato.emailAccount = { email: dati.email || null, email_origine: dati.email_origine || null, email_in_attesa: dati.email_in_attesa || null };
    try { localStorage.setItem("account", JSON.stringify(dati.utente)); } catch { /* niente memoria */ }
    if (!soloAmministratore()) $("#bottone-aggiorna").hidden = true;          // aggiornare i dati spetta all'amministratore
    if (ritornoGoogle) await gestisciRitornoGoogle(ritornoGoogle, true);       // collega / conferma: si resta dentro
  }
  return true;
}

// ---------------------------------------------------------------- avvio
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  // Con una versione nuova il service worker prende il posto del vecchio (skipWaiting) ma la pagina aperta ha ancora il vecchio JavaScript:
  // si offre un avviso discreto per ricaricare. Alla prima installazione (nessun controllore prima) non c'è nulla da dire.
  const avevaControllore = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!avevaControllore || document.getElementById("aggiornamento-pronto")) return;
    const barra = document.createElement("div");
    barra.id = "aggiornamento-pronto"; barra.className = "aggiornamento-pronto vetro"; barra.setAttribute("role", "status");
    const testo = document.createElement("span"); testo.textContent = t("comune.aggiornamento_pronto") + " –";
    const bottone = document.createElement("button"); bottone.type = "button"; bottone.textContent = t("comune.ricarica");
    bottone.addEventListener("click", () => location.reload());
    barra.append(testo, bottone); document.body.appendChild(barra);
  });
  navigator.serviceWorker.register("sw.js").catch(() => { /* senza: funziona lo stesso, solo non offline */ });
  // Tocco su un avviso con l'app già aperta: il service worker dice quale scheda aprire (per esempio la Formazione).
  navigator.serviceWorker.addEventListener("message", e => {
    const v = e.data && e.data.tipo === "apri" ? String(e.data.vista || "") : "";
    if (SCHEDA_DI(v)) vai(v);
  });
}
let iniziale = "oggi";
try { iniziale = localStorage.getItem("vista") || "oggi"; } catch { /* niente memoria */ }
togliPrefVecchie();                                                                        // colore, densità, animazioni e sezione iniziale non si scelgono più
try { const v = new URLSearchParams(location.search).get("vista"); if (SCHEDA_DI(v) || v === "impostazioni") iniziale = v; stato.impDaUrl = new URLSearchParams(location.search).get("gruppo"); } catch { /* indirizzo strano */ }   // scorciatoie dell'icona (Formazione, Mercato)
try { const sc = new URLSearchParams(location.search).get("scheda"); if (sc) stato.mercatoTab = schedaMercato(sc); } catch { /* indirizzo strano */ }   // ?vista=mercato&scheda=classifica funziona ancora
if (!SCHEDA_DI(iniziale) && iniziale !== "impostazioni") iniziale = "oggi";          // «mercato», «scambi» e «lega» dei vecchi salvataggi e indirizzi valgono ancora
controllaAccesso().then(async entrato => {
  if (!entrato) return;
  Promise.all([caricaInfo().then(() => caricaSquadre(true)), caricaFoto(), caricaFunzioni()]).then(() => {
    let condivisa = null;
    try { condivisa = new URLSearchParams(location.search).get("condivisa"); } catch { /* indirizzo strano */ }
    if (condivisa) {                                     // arrivo dal menu Condividi del telefono (share_target)
      history.replaceState(null, "", "/");
      iniziale = "squadra";
    }
    vai(iniziale);
    if (typeof primoAvvioSeServe === "function") primoAvvioSeServe();
    if (condivisa === "1") apriStemmaMaglia(null, true);
    else if (condivisa === "no") avviso("Non ho potuto usare l'immagine condivisa: servono PNG, JPEG o WebP fino a 4 MB", 7000);
  });
});
applicaAspetto();
try { matchMedia("(prefers-color-scheme: light)").addEventListener("change", applicaAspetto); } catch { /* browser vecchio */ }

// Accessibilità: i pulsanti a scelta (moduli, stili, gruppi...) dicono ai lettori di schermo quale è attivo.
(function sincronizzaAria() {
  let atteso = false;
  const aggiorna = () => {
    atteso = false;
    // solo pulsanti: «Qual è la tua squadra?» (Aggiorna le rose) è un'etichetta con dentro un radio, che lo dice già (axe, issue #289)
    document.querySelectorAll("button.chip, .segmenti button").forEach(b => {
      b.setAttribute("aria-pressed", String(b.classList.contains("attiva") || b.classList.contains("attivo") || b.classList.contains("scelta")));
    });
    // campi senza etichetta: il testo d'esempio o il titolo della scheda in cui stanno diventano il loro nome per i lettori di schermo
    document.querySelectorAll("#contenuto input, #contenuto select, #contenuto textarea, #foglio-contenuto input, #foglio-contenuto select, #foglio-contenuto textarea").forEach(c => {
      if (c.type === "hidden" || c.type === "file" || c.type === "checkbox" || (c.labels && c.labels.length) || c.hasAttribute("aria-label") || c.hasAttribute("aria-labelledby")) return;
      const scheda = c.closest(".carta, .foglio-corpo"), titolo = scheda && scheda.querySelector("h1, h2, h3");
      const nome = c.getAttribute("placeholder") || (titolo ? titolo.textContent : "");
      if (nome.trim()) c.setAttribute("aria-label", nome.trim());
    });
  };
  const osservatore = new MutationObserver(() => { if (!atteso) { atteso = true; setTimeout(aggiorna, 30); } });
  osservatore.observe(contenuto, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
  osservatore.observe($("#foglio-contenuto"), { subtree: true, childList: true });
  aggiorna();
})();

// La testata resta ferma in alto e cresce quando il nome della squadra va a capo o con il testo grande: la sua altezza vera va in
// --alto-testata, che stile.css usa per scroll-padding-top. Così chi va avanti e indietro con il tasto Tab non trova il focus sotto la
// testata (WCAG 2.2, 2.4.11; issue #280). Sotto i 320 px utili la testata scorre via con la pagina: 0.
(function altezzaTestata() {
  const testata = document.querySelector(".testata"), radice = document.documentElement;
  if (!testata) return;
  const misura = () => radice.style.setProperty("--alto-testata", getComputedStyle(testata).position === "sticky" ? `${testata.offsetHeight}px` : "0px");
  if (typeof ResizeObserver === "function") new ResizeObserver(misura).observe(testata);
  misura();
})();

// Colonne ferme in alto su tablet e PC (la prima di Oggi, il campo della Formazione, l'elenco di Impostazioni, i filtri dei giocatori):
// restano ferme solo se ci stanno nello schermo. Più alte, il loro fondo (il portiere, «Apri la formazione») restava sotto la barra o
// fuori dallo schermo, con il Tab e anche scorrendo: iPad con il testo grande, telefono in orizzontale, PC con la finestra bassa (#280).
const FERME = ".colonne-oggi > .col:first-child, .colonne-campo .col > .campo, .imp-elenco, .giocatori-pagina .filtri-giocatori";
const SOPRA_FERME = new WeakMap();        // il `top` di quando la colonna era ferma: da `static` qualche browser (Safari) dà «auto»
function controllaFerme() {
  const sotto = parseFloat(getComputedStyle(document.documentElement).scrollPaddingBottom) || 0;      // la barra in basso, se c'è
  document.querySelectorAll(FERME).forEach(el => {
    const era = el.classList.contains("non-ferma"), stile = getComputedStyle(el);
    if (!era && stile.position !== "sticky") return;                     // non è ferma: niente da controllare
    if (!era) SOPRA_FERME.set(el, parseFloat(stile.top) || 0);           // si legge solo da ferma: così il conto non cambia e non oscilla
    const alto = el.getBoundingClientRect().height, z = el.offsetHeight ? alto / el.offsetHeight : 1;   // con il testo grande la pagina è ingrandita
    const troppo = alto + ((SOPRA_FERME.get(el) || 0) + sotto) * z > innerHeight;
    if (troppo !== era) el.classList.toggle("non-ferma", troppo);        // la classe si tocca solo quando cambia (sincronizzaAria osserva le classi)
  });
}
(function seguiFerme() {
  let atteso = false;
  const pianifica = () => { if (!atteso) { atteso = true; requestAnimationFrame(() => { atteso = false; controllaFerme(); }); } };
  new MutationObserver(pianifica).observe(contenuto, { subtree: true, childList: true });
  if (typeof ResizeObserver === "function") new ResizeObserver(pianifica).observe(contenuto);          // anche quando una carta cresce dopo
  addEventListener("resize", pianifica);
  pianifica();
})();
