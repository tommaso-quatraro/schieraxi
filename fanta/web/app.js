"use strict";
// App SchieraXI: JavaScript semplice, senza librerie. Parla con il server Python (fanta/server.py).
// Sezioni: Formazione, Giornate, Squadra, Altro. La scheda di un giocatore è un pannello che sale dal basso.

const $ = (sel, el = document) => el.querySelector(sel);
const contenuto = $("#contenuto");
const VISTE = ["formazione", "giornate", "squadra", "altro"];
// Nomi vecchi che arrivano ancora da indirizzi, scorciatoie e avvisi: «oggi» è diventata la Formazione (una schermata sola, #616);
// «mercato» (Cambi consigliati, Seguiti, Elenco, Calendario) e «scambi» sono pagine tolte il 12/11/2026 (#615), «lega» è il nome di
// prima delle voci di Squadra e Altro. Portano alla scheda in cui stavano (schermataCheResta).
const SOTTO_VISTE = { oggi: "formazione", mercato: "squadra", scambi: "altro", lega: "altro" };
// Pulsante «torna indietro»: la freccia è un'icona, non un carattere nel testo (docs/STILE-SENZA-AI.md).
const ICONA_INDIETRO = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>`;
const SCHEDA_DI = v => VISTE.includes(v) ? v : Object.hasOwn(SOTTO_VISTE, String(v)) ? SOTTO_VISTE[v] : null;   // `v` viene anche dall'indirizzo: solo i nomi veri
// Le funzioni accese (dieta): una chiave che manca vale «acceso», così con un server vecchio o senza risposta si vede tutto come prima.
const funz = id => !stato.funzioni || stato.funzioni.funzioni[id] !== false;
const stato = { vista: "formazione", info: null, squadraVista: null, richiesta: 0, calendario: null };
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

// ETag e If-Match: il server dà a ogni risorsa personale (regole, rose, scelta di una giornata, avvisi) un ETag. L'app
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
      const intestazioni = { "X-Fanta": "1", "Accept-Language": LINGUA };    // il server scrive alcuni testi (le novità...) in questa lingua
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

// Il titolo della schermata c'è già mentre carica (opz come pagina(): di norma il nome della scheda). Finché carica l'area
// principale ha aria-busy="true" (lo dice ai lettori di schermo e ai test del browser): lo toglie la pagina() che arriva dopo.
function caricamento(testo = t("comune.calcolo_in_corso"), opz = {}) {
  pagina(`<div class="caricamento">${marchio(54, true)}${esc(testo)}</div>
    <div class="scheletro carta"><i></i><i></i><i class="corta"></i></div>
    <div class="scheletro carta"><i></i><i class="corta"></i></div>`, { ...opz, carica: true });
}
// «1 giornata», «2 giornate»: il plurale giusto per un numero
const nPl = (n, uno, molti) => `${n} ${n === 1 ? uno : molti}`;
// Con «troppe richieste» (429) il server dice quanto aspettare: lo diciamo anche noi.
// Se il messaggio del server dice già quando riprovare («Si azzera tra...») non lo ripetiamo; sopra l'ora si arrotonda alle ore.
const attesaTesto = s => s < 90 ? t("comune.attesa_secondi", { n: s }) : s < 3600 ? t("comune.attesa_minuti", { n: Math.ceil(s / 60) })
  : t(Math.round(s / 3600) <= 1 ? "comune.attesa_ora" : "comune.attesa_ore", { n: Math.max(1, Math.round(s / 3600)) });
const attesaDa = e => e && e.status === 429 && e.riprova && !/\btra\b/i.test(e.originale || e.message || "") ? t("comune.riprova_tra", { attesa: attesaTesto(e.riprova) }) : "";
// Un errore mostrato a chi usa l'app. `role="alert"`: il lettore di schermo lo dice subito, e i test del browser riconoscono una
// schermata che si rompe (la web cattura i suoi errori e non scrive in console). Solo per gli errori veri: avvisi, stati vuoti e
// promemoria non lo hanno.
const errore = e => `<div class="errore" role="alert">${esc(e.message || e)}${attesaDa(e)}</div>`;
// Errore a tutta pagina (una sezione che non si apre): c'è il pulsante «Riprova», senza dover cambiare sezione e tornare.
// Senza rose (409 dal server) non è un errore: è un inizio. Stato vuoto che porta a «Importa le rose» (si apre il primo avvio guidato).
const senzaRose = e => !!e && e.status === 409 && /nessuna rosa/i.test(e.originale || e.message || "");
const cartaSenzaRose = (titolo = t("comune.prima_rose")) => `<div class="carta benvenuto" role="status"><h2>${esc(titolo)}</h2>
  <p class="debole">${t("comune.importa_spiega")}</p>
  <div class="pulsanti"><button class="bottone" type="button" data-importa-rose>${t("comune.importa_rose")}</button></div></div>`;
// Funzione spenta (404 con il campo «funzione»): non è un guasto, quindi niente «Riprova» e niente avviso di errore; si spiega.
const funzioneSpenta = e => !!e && e.status === 404 && typeof e.funzione === "string";
const cartaFunzioneSpenta = e => `<div class="carta" role="status"><h2>${t("dieta.non_disponibile")}</h2><p class="debole">${esc(e.message)}</p>
  <div class="pulsanti"><button class="bottone" type="button" data-vai="formazione">${t("dieta.torna_formazione")}</button></div></div>`;
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
  stato.formaz = null;       // la formazione "in memoria" per la sostituzione non vale più
  stato.scelta = null;       // e nemmeno la formazione modificata a mano
  try { Object.keys(localStorage).filter(k => k.startsWith("cache:")).forEach(k => localStorage.removeItem(k)); } catch { /* niente memoria */ }
}
// Scrive la pagina: in cima il titolo della schermata (l'unico h1) e la riga di stato, poi il contenuto (grafica B, spec §8.2 e §10).
// opz.titolo: il titolo (di norma il nome della scheda accesa); opz.stato === false: niente riga di stato.
// Se i dati arrivano da copia salvata aggiunge la nota, se sostituisce non rifà l'entrata. opz.carica: è la schermata di attesa
// di caricamento() (aria-busy="true" sull'area principale); ogni altra pagina, anche quella di un errore, lo toglie.
function pagina(html, opz = {}) {
  const conFocus = !!document.activeElement && document.activeElement.id === "titolo-pagina";   // il titolo aveva il focus: lo ritrova ridisegnato
  if (opz.carica) contenuto.setAttribute("aria-busy", "true"); else contenuto.removeAttribute("aria-busy");
  contenuto.classList.toggle("ridisegna", !!opz.sostituisce);
  const scheda = SCHEDA_DI(stato.vista);
  const titolo = opz.titolo || (scheda ? t("nav." + scheda) : "SchieraXI");
  const riga = opz.stato === false ? "" : `<p class="stato-pagina">${rigaStato()}</p>`;
  const nota = opz.daCache ? `<div class="nota" id="nota-cache">${t("comune.dati_salvati", { quando: fDataOra(new Date(opz.daCache)) })}</div>` : "";
  contenuto.innerHTML = `<header class="capo-pagina"><h1 id="titolo-pagina" tabindex="-1">${esc(titolo)}</h1>${riga}</header>` + nota + html;
  document.title = `${titolo} · SchieraXI`;            // il nome della finestra è il titolo grande (chi usa un lettore di schermo sente dove è)
  if (conFocus) { const h = $("#titolo-pagina"); if (h) h.focus({ preventScroll: true }); }
}
// La riga di stato: [stemma] Giornata N · nome della mia squadra · dati del … (i pezzi li prepara caricaInfo, lo stemma caricaSquadre).
// Ogni pezzo sta intero: se la riga non ci sta si va a capo dopo un « · » (a 390 px la data si tagliava).
function rigaStato() {
  const r = stato.rigaStato;
  if (!r) return "";
  const mia = r.offline ? null : miaSquadra();
  const stemma = mia && mia.immagini && mia.immagini.stemma ? `<img class="stemma-stato" src="${esc(urlImg(mia.nome, "stemma"))}" alt="" width="20" height="20">` : "";
  const pezzi = r.offline ? [t("testata.offline")] : [r.giornata, r.squadra, r.dati].filter(Boolean);
  return stemma + pezzi.map(p => `<span>${esc(p)}</span>`).join(" · ");
}
// Dati nuovi (avvio, «Aggiorna i dati», rose o squadra cambiate): la riga di stato già in pagina si riscrive.
function aggiornaRigaStato() {
  document.querySelectorAll(".stato-pagina").forEach(e => { e.innerHTML = rigaStato(); });
}
// `percorso`: l'indirizzo da chiedere, oppure una funzione che legge più cose insieme e le restituisce (la Formazione).
// `mostra` può restituire `{ pronta() }`: si chiama quando i dati nuovi sono uguali alla copia già in pagina (la Formazione tiene
// spenti i comandi che scrivono finché non lo sa).
async function caricaConCache(chiave, percorso, mostra, testo) {
  const mia = nuovaRichiesta();
  let salvata = leggiCache(chiave), vista = null;
  if (salvata) {
    try { vista = mostra(salvata.dati, { daCache: salvata.quando }); }
    catch { rimuoviCache(chiave); salvata = null; caricamento(testo); }     // copia rovinata o di una versione vecchia
  } else caricamento(testo);
  try {
    const dati = typeof percorso === "function" ? await percorso() : await api(percorso);
    if (!ancoraValida(mia)) return;
    salvaCache(chiave, dati);
    if (!salvata || JSON.stringify(salvata.dati) !== JSON.stringify(dati)) mostra(dati, { sostituisce: !!salvata });
    else { const b = $("#nota-cache"); if (b) b.remove(); if (vista && typeof vista.pronta === "function") vista.pronta(); }
  } catch (e) {
    if (!ancoraValida(mia)) return;
    if (salvata) {
      const b = $("#nota-cache");
      if (b) b.textContent = e.rete ? t("comune.cache_offline") : t("comune.cache_errore", { errore: e.message });
      return;
    }
    pagina(erroreVista(e) + (!senzaRose(e) && /rosa|squadra/i.test(e.originale || e.message) ? `<button class="bottone" data-vai="squadra">${t("comune.vai_lega")}</button>` : ""));
  }
}

// ---------------------------------------------------------------- pezzi grafici riusati
// Colori principali e secondari delle squadre (per il cerchio degli avatar e la lineetta davanti alla sigla).
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
// Il volto nelle righe e nella scheda (`grande`): solo il volto, senza numeri sopra (l'indice 0-100 è stato tolto il 12/11/2026, #615).
const volto = (x, grande = false) => `<span class="avatar-anello ${grande ? "grande-a" : ""}">${avatar(x)}</span>`;
const diffPill = d => `<span class="diff d${d}"><i></i>${NOMI_DIFF[d]}</span>`;
// Il ruolo (Diario, ricerca): la lettera grigia delle righe dei giocatori (grafica B, spec §8.4), senza quadratino colorato.
// `piccolo`: davanti al nome, nella stessa riga di testo.
const badgeRuolo = (r, piccolo = false) => `<span class="ruolo-l${piccolo ? " ruolo-in" : ""}">${esc(ruoloSigla(r))}</span>`;
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
// Le regole riconosciute dal testo del regolamento («Rigore parato», «Moduli ammessi»...) hanno l'etichetta nella lingua scelta; una
// voce nuova del server, senza etichetta qui, si mostra com'è.
const etichettaRegola = m => (Object.hasOwn(TESTI.it, `regola.et.${m.chiave}`) ? t(`regola.et.${m.chiave}`) : m.etichetta);
// I motivi nella scheda: si scelgono dal testo italiano del server, si mostrano nella lingua scelta (motivi_frasi, vedi fanta/frasi.py).
const motiviUtili = x => (x.motivi || []).map((testo, i) => ({ testo, frase: (x.motivi_frasi || [])[i] }))
  .filter(m => !/^titolare|^parte dalla panchina|^partita (favorevole|difficile)/.test(m.testo)).slice(0, 2);
// Una sola percentuale per giocatore, «gioca N%»: gol atteso e porta inviolata (motivi con un numero) restano in «Tutti i numeri».
const MOTIVI_CON_PERCENTUALE = ["motivo.gol_atteso", "motivo.porta_inviolata"];
const senzaPercentuale = m => !(m.frase && MOTIVI_CON_PERCENTUALE.includes(m.frase.chiave)) && !/\d\s*%/.test(m.testo);
// Lo stato di un giocatore, dal codice dell'etichetta del server (fanta/etichette.py); con un server vecchio dai campi grezzi.
const codiceStato = x => !x ? null : etichettaPronta(x) ? x.etichetta.codice
  : ["infortunato", "squalificato"].includes(x.stato) ? x.stato : x.titolarita === "fuori" ? "fuori" : typeof x.rinvio === "string" || x.stato_partita === "rinviata" ? "rinviata" : x.dubbio ? "in_dubbio" : null;
// Le sole parole di stato che si mostrano prima della partita (#616): ciò che dice se non gioca. Le quattro etichette di titolarità
// («Probabile titolare», «In ballottaggio», «Probabile panchina», «Improbabile») non si mostrano più: «titolare» e «panchina» vogliono
// dire la tua formazione, e quanto è probabile che giochi lo dice «gioca N%». Le parole sono quelle del server (senza « · gioca N%»).
const PAROLE_STATO = { in_dubbio: ["tit.in_dubbio", "arancio"], rinviata: ["tit.st_rinviata", "arancio"], infortunato: ["oggi.infortunato", "rossa"],
  squalificato: ["oggi.squalificato", "rossa"], fuori: ["tit.fuori", "rossa"] };
function parolaStato(x) {
  const c = codiceStato(x);
  if (!Object.hasOwn(PAROLE_STATO, c || "")) return null;
  const [chiave, classe] = PAROLE_STATO[c];
  return { codice: c, classe, testo: etichettaPronta(x) ? x.etichetta.testo.split(" · ")[0] : t(chiave) };
}
// Non gioca di sicuro (infortunato, squalificato, fuori): la parola basta, «gioca 0%» non serve.
const nonGiocaDiSicuro = stato => !!stato && stato.classe === "rossa";
// La nota delle probabili su chi rischia di non esserci («contusione al ginocchio, in forte dubbio dal 1'»): il motivo dello stato
// a parole. È testo della fonte, scritto com'è. Vuota per chi non ha uno stato da spiegare e a partita cominciata.
const notaStato = (x, stato) => (stato && typeof x.nota === "string" && x.nota.trim() ? x.nota.trim() : "");
// Le parole sotto il nome in una riga: lo stato prima della partita, com'è andata dopo («Voto in arrivo», «Senza voto»), «Diffidato»
// e, in una riga sua, la nota che spiega lo stato. `inPiu`: altre etichette, prima della nota (già pronte per l'HTML).
function etichetteGiocatore(x, inPiu = "") {
  const esito = esitoPartita(x), stato = esito ? null : parolaStato(x);
  const parola = esito && esito.fv == null ? `<span class="etichetta ${etichettaPronta(x) ? classeTono(x.etichetta) : STATO_PARTITA[x.stato_partita][1]}">${esc(esito.testo)}</span>`
    : stato ? `<span class="etichetta ${stato.classe}">${esc(stato.testo)}</span>` : "";
  const nota = notaStato(x, stato);
  return parola + inPiu + (x.diffidato ? `<span class="etichetta arancio">${t("oggi.diffidato_tipo")}</span>` : "")
    + (nota ? `<span class="etichetta neutra nota-stato">${esc(nota)}</span>` : "");
}

// Il nome del club per i lettori di schermo («il Napoli»); la luminosità di un colore per il contrasto della lineetta (lineetta()).
const nomeClub = s => String(s || "").replace(/(^|[\s-])\S/g, c => c.toUpperCase());
function luminosita(hex) {
  const n = parseInt(String(hex).slice(1), 16);
  const c = [n >> 16, (n >> 8) & 255, n & 255].map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; });
  return .2126 * c[0] + .7152 * c[1] + .0722 * c[2];
}
// «gioca N%» si mostra solo quando conta (#616): sotto l'80%, arancio fra 50 e 79, rosso sotto 50. Sopra, il fantavoto atteso basta.
// Si decide sul numero che si legge: 79,6% si mostra «80%» e non è «sotto l'80%».
const SOGLIA_GIOCA = 0.8, SOGLIA_BASSA = 0.5;
const giocaLetto = x => Math.round((x.p_voto ?? 0) * 100) / 100;
const classeGioca = p => (p < SOGLIA_BASSA ? "basso" : "medio");
// Per i lettori di schermo la pedina in una frase, con le stesse cose che si vedono: «Rossi, fantavoto atteso 6,8, gioca al 45 per
// cento, In dubbio». `esito`: esitoPedina(x), a partita iniziata o rinviata; `stato`: parolaStato(x). A formazione chiusa, per chi
// deve ancora giocare (`da_giocare`), sulla pedina c'è quando gioca e non «gioca N%»: nemmeno qui.
function vocePedina(x, esito = null, stato = null) {
  const p = Math.round((x.p_voto ?? 0) * 100);
  const vocale = p === 1 || p === 8 || p === 11 || (p >= 80 && p <= 89);         // «all'85», «al 65»
  const preso = esito && esito.fv != null;
  return [x.nome, preso ? esito.testo : t("formazione.voce_fv", { fv: num(x.fv_atteso) }), esito && !preso ? esito.testo : "",
    !esito && x.stato_partita !== "da_giocare" && !nonGiocaDiSicuro(stato) && giocaLetto(x) < SOGLIA_GIOCA ? t(vocale ? "formazione.voce_gioca_v" : "formazione.voce_gioca", { p }) : "",
    !esito && stato ? stato.testo : ""].filter(Boolean).join(", ");
}
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
// La pedina (#616): un disco bianco con il fantavoto atteso e sotto il cognome; nient'altro, se il giocatore gioca quasi di sicuro.
// «gioca N%» compare solo sotto l'80% (pillola arancio fra 50 e 79, rossa sotto 50, con l'anello dello stesso colore attorno al
// disco); «In dubbio», «Infortunato», «Squalificato» a parole. Niente volto e niente avversario: stanno nella scheda, a un tocco.
// A partita cominciata il disco ha il fantavoto preso; finché non c'è, resta vuoto dentro (l'atteso) con sotto lo stato della partita
// o, se deve ancora giocare, quando gioca.
function pedina(x, k = 0) {
  const esito = esitoPedina(x), stato = esito ? null : parolaStato(x);
  const p = giocaLetto(x), preso = !!esito && esito.fv != null;
  const daGiocare = !esito && x.stato_partita === "da_giocare";                 // formazione chiusa, la sua partita non è cominciata
  const gioca = !esito && !daGiocare && !nonGiocaDiSicuro(stato) && p < SOGLIA_GIOCA;
  return `<button class="pedina${(esito && !preso) || daGiocare ? " attesa" : ""}" data-giocatore="${x.id}" style="--k:${k}">
    <span class="disco" aria-hidden="true">${num(preso ? esito.fv : x.fv_atteso)}</span>
    <span class="nome" aria-hidden="true">${esc(cognome(x))}</span>
    ${gioca ? `<span class="gioca ${classeGioca(p)}" aria-hidden="true">${t("giocatore.gioca", { p: perc(p) })}</span>` : ""}
    ${stato ? `<span class="gioca ${stato.classe === "rossa" ? "basso" : "parola"}" aria-hidden="true">${esc(stato.testo)}</span>` : ""}
    ${esito && !preso ? `<span class="gioca parola" aria-hidden="true">${esc(esito.testo)}</span>` : ""}
    ${daGiocare && x.data_partita ? `<span class="gioca parola" aria-hidden="true">${esc(quando(x.data_partita))}</span>` : ""}
    <span class="solo-lettori">${esc(vocePedina(x, esito, stato))}${daGiocare && x.data_partita ? `, ${esc(quando(x.data_partita))}` : ""}</span>
  </button>`;
}
// Il numero della giornata, uguale in ogni schermata: l'UNICO posto della web che lo scrive (docs/COERENZA-WEB-IPHONE.md, «Giornata: le
// forme»; sul server frasi.nome_giornata). Come su Leghe i due numeri insieme, «Giornata 8 · 11ª di Serie A» (lega, Serie A); senza il
// numero della lega (stagioni passate, prima che la lega parta, calendario di Serie A) «11ª giornata di Serie A». Solo numeri: si può
// mettere nell'HTML senza esc(). In una frase va in testa, seguito dai due punti.
function nomeGiornata(lega, serieA) {
  const n = Number(lega) || null, a = Number(serieA) || null;
  if (n && a) return t("frase.giornata.lega", { n, a });
  if (a) return t("frase.giornata.serie_a", { a });
  return n ? t("testata.giornata", { n }) : "";
}
// «la 8ª» si dice «l'8ª» («dall'8ª», «all'11ª»): l'articolo femminile perde la vocale davanti agli ordinali che si leggono con una vocale, fra 1 e 38
// l'8ª (ottava) e l'11ª (undicesima); «la 1ª» e «la Giornata 8» restano. Solo in italiano; uguale a frasi.elidi_ordinali sul server.
const elidiOrdinali = testo => (LINGUA === "it" ? String(testo).replace(/\b(la|alla|dalla|della|nella|sulla) ((?:8|11)ª)/g, (x, art, num) => `${art.slice(0, -1)}'${num}`) : testo);

// La partita in una riga, nella stessa forma del campo: «@ MIL · sab 31 20:45» (fuori) o «vs PAR · oggi 18:30» (in casa).
// «vs PAR» (in casa) / «@ UDI» (in trasferta): nelle celle del calendario e, con la squadra davanti, nelle righe. Per i lettori di schermo
// la frase con il nome intero, come VoiceOver sull'iPhone: «in casa contro Parma», «in trasferta contro Udinese» (mai «UDI fuori», #453).
const vsAt = x => `<span aria-hidden="true">${x.in_casa ? "vs" : "@"} ${sigla(x.avversario)}</span><span class="solo-lettori">${esc(t(x.in_casa ? "formazione.voce_casa" : "formazione.voce_fuori", { avv: nomeClub(x.avversario) }))}</span>`;
const partitaRiga = x => `${sigla(x.squadra)} ${vsAt(x)}`;
const partitaBreve = x => `${partitaRiga(x)} · ${quando(x.data_partita)}`;

// ---- la riga di un giocatore (grafica B, spec §8.4-8.5): una sola, uguale in Formazione e Rosa.
// Volto da 36 px, la lettera del ruolo grigia, il nome e sotto la partita (con la lineetta del club) e lo stato a parole, se c'è;
// a destra il fantavoto atteso e, solo sotto l'80%, «gioca N%», in due colonne della stessa larghezza in ogni riga (`--col-gioca`,
// `--col-fv`): uno sopra l'altro quando la riga è stretta, una riga sola con la colonna della partita quando è larga (stile.css).
// La lineetta nei colori sociali davanti alla sigla della squadra: decorativa (la sigla dice già la squadra), grigia per un club che
// non conosciamo. Per ogni tema il primo colore del club, o il secondo se il primo quasi sparisce sul fondo (il bianco della Juventus
// sul fondo chiaro, il verde scuro del Venezia su quello scuro). I colori vengono dalla nostra tabella, mai dai dati.
const FONDI_LINEETTA = { chiaro: "#ffffff", scuro: "#121513" };           // --sfondo dei due temi (stile.css)
const contrastoColori = (a, b) => { const [x, y] = [luminosita(a), luminosita(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
function lineetta(slug) {
  const [c1, c2] = (Object.hasOwn(COLORI_SQUADRA, slug) && COLORI_SQUADRA[slug]) || ["#6b7280", "#6b7280"];
  const sul = fondo => contrastoColori(c1, fondo) >= 1.6 || contrastoColori(c1, fondo) >= contrastoColori(c2, fondo) ? c1 : c2;
  return `<i class="lineetta" style="--c:${sul(FONDI_LINEETTA.chiaro)};--c-scuro:${sul(FONDI_LINEETTA.scuro)}" aria-hidden="true"></i>`;
}
// I nomi delle colonne sopra un elenco di giocatori, allineati alle colonne delle righe; nascosti ai lettori di schermo, perché il
// nome di ogni riga dice già tutto. `partita: false` senza la colonna della partita; `ferma` resta sotto la testata mentre si
// scorre (elenchi lunghi).
function intestazioneColonne(opz = { partita: true }) {
  return `<div class="intestazione-colonne${opz.ferma ? " ferma" : ""}" aria-hidden="true"><div class="voce-g">`
    + (opz.partita === false ? "" : `<span class="ic-partita">${t("mercato.partita")}</span>`)
    + `<span class="ic-fv">${t("mercato.fantavoto_atteso")}</span></div></div>`;
}

// La riga sotto il nome in pezzi interi («NAP vs LAZ · sab 31 20:45 ·», «Real Esempio»): va a capo tra un pezzo e l'altro, mai
// dentro il nome di una squadra; il «·» resta in fondo al pezzo prima. I pezzi sono già sicuri per l'HTML.
const pezziRiga = pezzi => pezzi.filter(Boolean).map((p, i, tutti) => `<span class="nb">${p}${i < tutti.length - 1 ? " ·" : ""}</span>`).join(" ");

// `posizione`: il numero d'ordine davanti al nome (la panchina, nell'ordine in cui entra). Un tocco apre la scheda del giocatore.
function voceGiocatore(x, posizione) {
  return `<li class="riga-gioc"><button class="voce voce-g" data-giocatore="${x.id}">
    ${volto(x)}
    <span class="testo-g"><span class="nome"><span class="ruolo-l">${esc(ruoloSigla(x.ruolo))}</span><span class="nome-t">${posizione ? `<span class="debole">${posizione}. </span>` : ""}${esc(x.nome)}</span></span>
      <span class="dettaglio">${lineetta(x.squadra)}${pezziRiga([x.avversario ? partitaBreve(x) : sigla(x.squadra)])}</span>
      <span class="etichette">${etichetteGiocatore(x)}</span></span>
    ${numeriRiga(x)}
  </button></li>`;
}

// I numeri a destra di una riga della Rosa: come le righe della Formazione (voceGiocatore). Senza previsione «non gioca» (o «?» per
// un giocatore che non abbiamo riconosciuto) al posto di «gioca N%».
function valoreRosa(p, x) {
  if (!p) return `<span class="pv-g">${x.id ? t("scambio.non_gioca") : "?"}</span><span class="valore"></span>`;
  return numeriRiga(p);
}

// Le due colonne dei numeri di ogni riga: il fantavoto atteso e, solo sotto l'80%, «gioca N%» (arancio fra 50 e 79, rosso sotto 50;
// niente per chi non gioca di sicuro: lo dice la parola). A partita iniziata il fantavoto preso con accanto «fantavoto», oppure «–»
// (lo stato è già scritto sotto il nome): mai «gioca N%». I nomi delle colonne sono nascosti ai lettori di schermo: il numero ha il
// suo nome accanto, solo per loro («gioca 45%, Fantavoto atteso 6,8»).
const nomeFvAtteso = () => `<span class="solo-lettori">${t("mercato.fantavoto_atteso")} </span>`;
function numeriRiga(p) {
  const esito = esitoPartita(p);
  if (esito) return esito.fv != null
    ? `<span class="pv-g">${t("mercato.fantavoto")}</span><span class="valore esito"><b>${num(esito.fv)}</b></span>`
    : `<span class="pv-g"></span><span class="valore esito"><b class="debole" aria-hidden="true">–</b></span>`;
  const q = giocaLetto(p), mostra = q < SOGLIA_GIOCA && !nonGiocaDiSicuro(parolaStato(p));
  return `<span class="pv-g${mostra ? " " + classeGioca(q) : ""}">${mostra ? t("giocatore.gioca", { p: perc(q) }) : ""}</span><span class="valore">${nomeFvAtteso()}<b>${num(p.fv_atteso)}</b></span>`;
}

// ---------------------------------------------------------------- navigazione
// Le schede (e il nome disegnato, che porta alla Formazione) sono collegamenti veri (spec grafica B §5 C2). Un clic normale cambia schermata
// dentro l'app; con Ctrl, ⌘, Maiusc, Alt o il tasto centrale decide il browser: la scheda si apre in un'altra scheda o finestra.
const clicSemplice = ev => ev.button === 0 && !ev.ctrlKey && !ev.metaKey && !ev.shiftKey && !ev.altKey;
document.querySelectorAll(".schede .scheda, .testata .marchio").forEach(a => a.addEventListener("click", ev => {
  if (!clicSemplice(ev)) return;
  ev.preventDefault();
  vai(a.dataset.vista || "formazione", undefined, { focoTitolo: true });
}));
// L'indirizzo di ogni schermata, lo stesso che l'app sa aprire all'avvio: va nella cronologia, così Indietro e Avanti funzionano.
// Anche le pagine dentro Squadra e Altro (#449): la voce (`&voce=`, Squadre e rose, Regole...) e la rosa di una squadra (`&rosa=`, il
// nome; vuoto = la mia). Scritto come lo scrive il browser (URLSearchParams: l'apostrofo diventa %27), così l'indirizzo resta uguale.
const indirizzoVista = (vista, gruppo, voce, rosa) => "/?" + new URLSearchParams([["vista", vista], ...(vista === "impostazioni" && gruppo ? [["gruppo", gruppo]] : []), ...((vista === "squadra" || vista === "altro") && voce && typeof rosa !== "string" ? [["voce", voce]] : []), ...(vista === "squadra" && typeof rosa === "string" ? [["rosa", rosa]] : [])]);
let indirizzoMostrato = null;      // l'indirizzo (senza «#…») della schermata in pagina: un popstate che porta qui non ridisegna niente
let timerConto = null;
let regoleAC = null;      // gestori della schermata regole: si staccano quando si esce

// Chi disegna ogni schermata: una mappa con i soli nomi ammessi. Il nome arriva anche dall'indirizzo (?vista=, Indietro): niente
// chiamate per nome su un oggetto («__proto__», «constructor»...); un nome che non c'è porta alla Formazione.
const DISEGNO_VISTE = new Map([["formazione", () => vistaFormazione()], ["giornate", () => vistaGiornate()], ["squadra", () => vistaLega("squadra")], ["altro", () => vistaLega("altro")]]);
// La schermata che resta per un indirizzo, una scorciatoia o un avviso: {vista, voce, gruppo}. «oggi» è la Formazione (#616). Le pagine
// tolte il 12/11/2026 (#615) portano alla più vicina: «mercato» (Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario) a Squadra, «scambi» ad Altro, una
// voce che non c'è più (Movimenti, Crediti, Nuova stagione) al menu della sua scheda, le Novità a Impostazioni > Informazioni.
// Il Diario, che era una voce di Altro, è la pagina Giornate (#617): il suo indirizzo di prima la apre.
// «lega» è il nome di prima delle voci di Squadra e Altro: vale la scheda della voce. `voci`: le voci di oggi ({id, ambito}).
function schermataCheResta(vista, voce, voci = VOCI_LEGA) {
  if (vista === "impostazioni") return { vista, voce: null };
  if (voce === "novita" && ["altro", "lega"].includes(vista)) return { vista: "impostazioni", voce: null, gruppo: "informazioni" };
  if (voce === "diario" && ["altro", "lega"].includes(vista)) return { vista: "giornate", voce: null };
  if (vista === "mercato") return { vista: "squadra", voce: null };
  if (vista === "scambi") return { vista: "altro", voce: null };
  const v = voci.find(x => x.id === voce);
  if (vista === "lega") return v ? { vista: v.ambito, voce } : { vista: "altro", voce: null };
  if (vista === "squadra" || vista === "altro") return { vista, voce: v && v.ambito === vista ? voce : null };
  return { vista: VISTE.includes(vista) ? vista : "formazione", voce: null };
}
// opz.daCronologia: si arriva da Indietro o Avanti del browser (l'indirizzo è già quello giusto: non si scrive di nuovo).
// opz.focoTitolo: cambio di scheda chiesto da chi usa l'app (clic, tasti 1-4, Indietro): il focus va sul titolo della schermata,
// così il lettore di schermo dice dove si è arrivati e il Tab riparte dal contenuto.
// opz.sostituisci: la schermata prende il posto della voce di adesso nella cronologia («‹ Altro» di una pagina aperta da un indirizzo,
// una voce di Squadra che porta subito a un'altra pagina): Indietro non torna a una voce che riaprirebbe la stessa cosa.
// La voce di Squadra o di Altro da aprire (`stato.legaTorna`) e la rosa di una squadra (`stato.rosaTorna`) vanno nell'indirizzo (#449).
function vai(vista, gruppo, opz = {}) {
  chiudiPannelloAffiancato();                                             // schede e tasti restano attivi con il pannello accanto (da 1200 px)
  const resta = schermataCheResta(vista, stato.legaTorna);                // nomi vecchi e pagine tolte: la schermata più vicina che resta
  vista = resta.vista;
  if (resta.gruppo) gruppo = resta.gruppo;
  if (typeof stato.legaTorna === "string") stato.legaTorna = resta.voce;  // una voce che non c'è più non resta nell'indirizzo
  const imp = vista === "impostazioni";                                   // l'ingranaggio in testata: non è una delle schede della barra
  const scheda = imp ? null : vista;                                      // la scheda della barra che si accende
  if (vista !== "squadra" && vista !== "altro") { stato.legaTorna = null; stato.rosaTorna = null; }   // valgono solo per Squadra e Altro
  const prima = stato.vista;
  stato.vista = vista;                                                    // il nome della finestra lo scrive pagina(), con il titolo grande
  document.querySelectorAll(".schede .scheda").forEach(b => {
    b.classList.toggle("attiva", b.dataset.vista === scheda);
    if (b.dataset.vista === scheda) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  const ing = $("#bottone-impostazioni");
  ing.classList.toggle("attiva", imp);
  if (imp) ing.setAttribute("aria-current", "page"); else ing.removeAttribute("aria-current");
  if (!imp) try { localStorage.setItem("vista", vista); } catch { /* niente memoria: va bene lo stesso */ }
  if (!opz.daCronologia) {
    // una voce nuova nella cronologia per ogni schermata nuova; la prima schermata e i ridisegni della stessa la sostituiscono
    const g = imp ? gruppo || stato.impDaUrl || null : null;
    const vl = (vista === "squadra" || vista === "altro") && typeof stato.legaTorna === "string" ? stato.legaTorna : null;
    const rosa = vista === "squadra" && typeof stato.rosaTorna === "string" ? stato.rosaTorna : null;
    const indirizzo = indirizzoVista(vista, g, vl, rosa), voce = { vista, gruppo: g, voce: vl, rosa };
    // da 1100 px Squadra e Altro sono una schermata sola (menu e pagina affiancati), da 768 px anche le Impostazioni: la scheda o il
    // tasto 3 con una voce aperta non aggiungono una voce che la pagina riporta subito lì (Indietro non farebbe niente). Non da
    // Regole o dalla rosa di una squadra, che sono pagine loro (`pagina`).
    const larga = imp ? !g && typeof impLargo === "function" && impLargo() : (vista === "squadra" || vista === "altro") && vl === null && rosa === null && legaLarga();
    const stessa = larga && prima === vista && !(history.state && history.state.pagina);
    try {
      // sostituendo la voce si tiene da dove era arrivata (`da`, scriviIndirizzo): è ancora la stessa pagina
      if (!history.state || location.pathname + location.search === indirizzo || stessa || opz.sostituisci) history.replaceState({ ...voce, da: (history.state && history.state.da) || null }, "", indirizzo);
      else history.pushState(voce, "", indirizzo);
    } catch { /* niente cronologia (pagina aperta da un file): si cambia schermata lo stesso */ }
  }
  indirizzoMostrato = location.pathname + location.search;
  window.scrollTo(0, 0);
  contenuto.classList.remove("ridisegna");
  delete contenuto.dataset.gruppo;
  clearInterval(timerConto);
  if (regoleAC) { regoleAC.abort(); regoleAC = null; }
  if (imp) vistaImpostazioni(gruppo);
  else DISEGNO_VISTE.get(vista)();
  if (opz.focoTitolo) { const h = $("#titolo-pagina"); if (h) h.focus({ preventScroll: true }); }   // pagina() lo tiene anche quando la schermata si ridisegna
}
// Indietro e Avanti del browser (e del mouse): la schermata di quella voce, come un clic sulla sua scheda (il foglio si chiude con lei).
window.addEventListener("popstate", ev => {
  if (location.pathname + location.search === indirizzoMostrato) return;   // è cambiata solo la parte dopo «#» (link «Vai al contenuto»): niente da ridisegnare
  chiudiFoglio();
  const q = new URLSearchParams(location.search);                          // voce senza stato: si legge l'indirizzo
  const v = ev.state && ev.state.vista ? ev.state : { vista: q.get("vista"), gruppo: q.get("gruppo"), voce: q.get("voce"), rosa: q.get("rosa") };
  stato.legaTorna = typeof v.voce === "string" ? v.voce : null;           // voce di Squadra o Altro, o il menu (#449)
  stato.rosaTorna = typeof v.rosa === "string" ? v.rosa : null;           // rosa di una squadra
  vai(v.vista || "formazione", v.gruppo || undefined, { daCronologia: true, focoTitolo: true });
});
// L'indirizzo di una pagina dentro Squadra, Altro o Impostazioni (#449): la voce aperta accanto al menu, Regole, la rosa di
// una squadra (`pagina: true`: pagine loro, non accanto al menu), il gruppo delle Impostazioni. `nuova` (un clic di chi usa l'app):
// una voce nuova nella cronologia, che si ricorda da dove si veniva (`da`), così i pulsanti «‹» dell'app tornano lì come Indietro.
// Senza (prima apertura, Indietro, ridisegno dopo un salvataggio) si corregge la voce di adesso, che tiene il suo `da`; con lo stesso
// indirizzo anche con `nuova` (una voce uguale non cambierebbe niente con Indietro).
function scriviIndirizzo(voce, nuova) {
  const indirizzo = indirizzoVista(voce.vista, voce.gruppo, voce.voce, voce.rosa), ora = location.pathname + location.search;
  try {
    if (nuova && ora !== indirizzo) history.pushState({ ...voce, da: ora }, "", indirizzo);
    else history.replaceState({ ...voce, da: (history.state && history.state.da) || null }, "", indirizzo);
  } catch { /* niente cronologia (pagina aperta da un file) */ }
  indirizzoMostrato = location.pathname + location.search;
}
// I pulsanti «‹ Squadra», «‹ Altro», «‹ Impostazioni»: se la voce di prima nella cronologia è quella giusta (`prima(da)`), sono
// Indietro del browser e non lasciano una voce morta. `inPosto`: l'indirizzo che la pagina ha già disegnato da sola (il menu accanto):
// Indietro non ridisegna niente. Torna false se non c'è una voce di prima giusta (pagina aperta da un indirizzo o da un collegamento).
function tornaIndietro(prima, inPosto) {
  const da = history.state && history.state.da;
  if (typeof da !== "string" || !prima(da)) return false;
  if (inPosto) indirizzoMostrato = inPosto;
  history.back();
  return true;
}
// «‹ Squadra» della rosa di una squadra (`squadre`: torna a Squadre e rose) e «‹ Altro» di Regole (`altro`). Senza una voce
// di prima nella stessa sezione, la sezione prende il posto della pagina nella cronologia.
function tornaAllaSezione(dove) {
  const sezione = dove === "altro" ? "altro" : "squadra";
  const vistaDi = u => { try { return new URLSearchParams(u.split("?")[1] || "").get("vista"); } catch { return null; } };
  if (tornaIndietro(da => vistaDi(da) === sezione)) return;
  stato.rosaTorna = null;
  if (dove === "altro") { stato.legaTorna = null; vai("altro", undefined, { sostituisci: true, focoTitolo: true }); }
  else vaiLega(dove, { sostituisci: true, focoTitolo: true });
}

// Stemma e maglia delle squadre (caricati dall'utente nella Lega).
const urlImg = (nome, tipo) => `/api/squadre/immagine?squadra=${encodeURIComponent(nome)}&tipo=${tipo}&v=${stato.vImg || 0}`;
async function caricaSquadre(seServono = false) {
  // seServono: all'avvio, se le rose non ci sono ancora (primo avvio) non si chiede nulla: niente errore in console.
  if (seServono && stato.info && stato.info.rose_importate === false) stato.squadre = [];
  else { try { stato.squadre = await api("/api/squadre"); } catch { stato.squadre = stato.squadre || []; } }
  aggiornaRigaStato();                                                     // lo stemma della mia squadra nella riga di stato
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
    const quandoAgg = i.ultimo_aggiornamento ? new Date(i.ultimo_aggiornamento) : null;
    // giornata, nome della mia squadra e data dei dati: la riga di stato sotto il titolo di ogni schermata (pagina())
    stato.rigaStato = {
      giornata: i.prossima_giornata ? nomeGiornata(i.prossima_giornata_lega, i.prossima_giornata) : null,   // «Giornata 8 · 11ª di Serie A», come altrove
      squadra: i.mia_squadra || null,
      dati: (quandoAgg ? t("testata.dati_del", { data: fData(quandoAgg), ora: fOra(quandoAgg) }) : t("testata.mai")).replace(/^\s*·\s*/, ""),
    };
    $("#bottone-aggiorna").classList.toggle("gira", i.aggiornamento_in_corso);
  } catch (e) {
    stato.rigaStato = { offline: true };
  }
  aggiornaRigaStato();
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

// ---------------------------------------------------------------- Formazione: la schermata che dice chi schierare (#616)
// Una schermata sola al posto di Oggi e Formazione. La testa cambia con la fase della giornata (`fase` di /api/oggi): prima della
// scadenza la giornata e quando si chiude; in corso i punti fatti finora; finita com'è andata e, sotto, la formazione della prossima.
// Poi al massimo due decisioni (dfDecisioni in dafare.js), il modulo con i punti attesi, il campo con gli 11, lo stato della scelta
// con «Copia per l'app della lega» e la spunta «L'ho messa», la panchina nell'ordine in cui entra, i non schierati, gli infortunati
// e gli squalificati. Il salvataggio è automatico: una sostituzione o un altro modulo si salvano al tocco.

// Quando si chiude la formazione che la schermata mostra: a giornata finita, o per chi è arrivato a giornata iniziata, la prossima.
const scadenzaDi = o => (o.prossima && (o.fase === "finita" || o.senza_formazione) && o.prossima.scadenza) || o.scadenza || o.inizio;
// «Si chiude oggi 18:20» e «fra 3 h 10 min»: il conto resta, piccolo, accanto alla scadenza.
function testoConto(o) {
  const quandoChiude = scadenzaDi(o), fine = parseData(quandoChiude);
  if (!fine) return { chiude: t("oggi.calendario_no"), manca: "" };
  const min = Math.round((fine - new Date()) / 60000);
  if (min <= 0) return { chiude: t("formazione.chiusa_breve"), manca: "" };
  const g = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
  // ogni numero resta attaccato alla sua unità (spazio che non va a capo): «1 giorno» / «8 h», mai «h» da sola su una riga (issue #286)
  const tempo = (g >= 1 ? tp("oggi.giorni_ore", g, { h }) : h >= 1 ? `${h} h ${m} min` : `${m} min`).replace(/(\d) /g, "$1 ");
  return { chiude: t("formazione.si_chiude", { quando: quando(quandoChiude) }), manca: t("formazione.fra", { tempo }) };
}

// Account nuovo, senza rose: benvenuto e un solo pulsante. Il primo avvio guidato si apre da solo (una volta, vedi primoAvvioSeServe).
function mostraSenzaRose(opz) {
  clearInterval(timerConto);
  pagina(`<div class="carta benvenuto" role="status"><h2>${t("oggi.benvenuto_schieraxi")}</h2>
    <p class="debole">${t("oggi.per_cominciare_importa")}</p>
    <div class="pulsanti"><button class="bottone" type="button" data-importa-rose>${t("comune.importa_rose")}</button></div></div>`, { ...opz, stato: false });
  if (typeof primoAvvioSeServe === "function") primoAvvioSeServe();
}

// Partite rinviate della giornata (campo `rinvio` di /api/oggi, docs/API.md): quali, i miei giocatori coinvolti e cosa vale per
// questa giornata, cambiabile solo per lei (PUT /api/regole/rinvio). Server vecchio senza il campo: niente riquadro.
const MODI_RINVIO = ["aspetta", "senza_voto", "voto_ufficio"];
function nomeModoRinvio(m, voto) {
  if (m === "voto_ufficio") return t("oggi.rinvio_ufficio", { v: num(voto ?? 6, Number.isInteger(voto ?? 6) ? 0 : 1) });
  return m === "aspetta" || m === "senza_voto" ? t("oggi.rinvio_" + m) : String(m);
}
// Il menu «per questa giornata i loro giocatori…»: cambia solo quella giornata. Un <select> non va a capo e tagliava la scelta
// («aspettano il recupero (conta il suo vo»): la scelta si legge intera nel riquadro (`.menu-scelta-testo`, va a capo), il <select>
// vero sta sopra, trasparente, e apre il menu del sistema. Come MenuRinvio dell'iPhone.
function menuRinvio(rv) {
  const modi = Array.isArray(rv.modi) && rv.modi.length ? rv.modi : MODI_RINVIO;
  const voto = rv.voto_ufficio ?? rv.valore;
  const scelto = modi.includes(rv.modo) ? rv.modo : modi[0];                // quello che il <select> mostra
  return `<label class="rinvio-scelta"><span class="debole">${t("oggi.rinvio_domanda")}</span>
      <span class="menu-scelta"><span class="menu-scelta-testo" aria-hidden="true">${esc(nomeModoRinvio(scelto, voto))}</span>
      <select class="rinvio-modo" data-giornata="${Number(rv.giornata)}" data-stagione="${esc(rv.stagione || "")}">${modi.map(m => `<option value="${esc(m)}" ${m === scelto ? "selected" : ""}>${esc(nomeModoRinvio(m, voto))}</option>`).join("")}</select></span></label>
    <p class="debole piccolo">${rv.eccezione ? t("oggi.rinvio_eccezione", { regola: esc(nomeModoRinvio(rv.predefinito, voto)) }) : t("oggi.rinvio_regola_lega")}</p>`;
}
// «UDI vs MIL»: le sigle, prima la squadra di casa. La usano il riquadro del rinvio e la riga dei recuperi che mancano (#310).
const partitaVs = p => `${sigla(p.casa)} vs ${sigla(p.trasferta)}`;
function cardRinvio(rv) {
  if (!rv || !Array.isArray(rv.partite) || !rv.partite.length) return "";
  const partite = rv.partite.map(p => `<li><b>${partitaVs(p)}</b>
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
        rileggiFormazione();
      } catch (e) { avviso(e.message, 8000); sel.value = salvato; mostra(); sel.disabled = false; }   // resta la scelta salvata
    });
  });
}

// Sul campo solo il cognome, senza l'iniziale («Rossi L.» → «Rossi»), come sull'iPhone: lo spazio è poco.
const cognome = x => String(x.nome).replace(/\s+\S{1,3}\.$/u, "");

// La formazione come testo, da copiare nell'app della lega (che non permette di incollarla: si inserisce a mano, leggendola da qui).
function testoFormazione(f, m, scheda) {
  const riga = r => `${ruoloSigla(r)}: ${m.titolari.map(scheda).filter(x => x && x.ruolo === r).map(x => x.nome).join(", ")}`;
  const righe = [`${nomeGiornata(f.giornata_lega, f.giornata)} · ${m.modulo}`, ...["P", "D", "C", "A"].map(riga)];
  const panchina = m.panchina.map(scheda).filter(Boolean);
  if (panchina.length) righe.push(t("scambi.panchina") + ": " + panchina.map((x, k) => `${k + 1}) ${x.nome}`).join(", "));
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

// «di solito fra 65 e 82»: dove cadono i punti veri 8 volte su 10 (fascia del server, calibrata sulle giornate passate). Le risposte
// vecchie hanno solo `dev`: «oscilla di ±N». Senza niente, vuota.
function fraseDiSolito(m) {
  const i = m && m.intervallo;
  if (i && Number.isFinite(i.basso) && Number.isFinite(i.alto) && i.basso <= i.alto) return t("formazione.di_solito", { a: num(i.basso, 0), b: num(i.alto, 0) });
  const d = m && m.dev;
  return Number.isFinite(d) && d >= 0 ? t("formazione.oscilla", { n: num(d, 0) }) : "";
}

const stessiIds = (a, b) => a.length === b.length && a.every(x => b.includes(x));
// La consigliata: un solo stile dal 12/11/2026 (#615), il livello «Equilibrata» del server (rischio 0). Gli altri livelli di
// `f.livelli` restano nella risposta per l'iPhone. Server senza `livelli`: i moduli in cima alla risposta.
const livelloBase = f => (f.livelli || []).find(x => x.rischio === 0) || { modulo: f.modulo, moduli: f.moduli };
// Il modulo già calcolato dal server che ha proprio questi 11 (l'ordine non conta), o null: allora serve una valutazione a parte.
const moduloDi = (f, ids) => livelloBase(f).moduli.find(m => stessiIds(m.titolari.map(Number), ids.map(Number))) || null;
// Il perché di un titolare in una riga (campo `perche_scelta` del modulo, fanta/perche_scelta.py; se manca, il campo `incerti`: titolare
// incerto con la riserva che gioca quasi di sicuro). Già pronto per l'HTML; vuoto se non c'è niente da dire. `altro` e `riserva`
// possono mancare (null): la frase del server basta a sé, quella degli incerti senza riserva non si scrive.
function percheTitolare(m, id, scheda) {
  const riga = (Array.isArray(m.perche_scelta) ? m.perche_scelta : []).find(x => x && Number(x.titolare) === Number(id) && x.testo);
  if (riga) return esc(testoDi(riga));
  const inc = (Array.isArray(m.incerti) ? m.incerti : []).find(x => x && Number(x.titolare) === Number(id));
  const a = inc && scheda(inc.titolare), b = inc && inc.riserva != null && scheda(inc.riserva);
  return a && b ? t("formazione.incerto", { p: perc(a.p_voto), riserva: esc(b.nome) }) : "";
}

// Dove rimettere il fuoco dopo che la Formazione si è ridisegnata: lo stesso comando, ritrovato nella pagina nuova. null = il fuoco
// non era nella schermata (non lo si sposta); "" = era su qualcosa che non si ritrova per nome.
function fuocoDi(e) {
  if (!e || !contenuto.contains(e) || e.id === "titolo-pagina") return null;
  if (e.id) return "#" + e.id;
  if (e.dataset.df !== undefined) return `#decisioni [data-df="${Number(e.dataset.df)}"]`;
  if (e.dataset.giocatore) return `#contenuto [data-giocatore="${Number(e.dataset.giocatore)}"]`;
  return e.matches("select.rinvio-modo") ? "select.rinvio-modo" : "";
}
// Rilegge la Formazione dal server tenendo il posto del fuoco (dopo un salvataggio arrivato a schermata già ridisegnata, la scelta
// sul rinvio, la scadenza passata con la pagina aperta).
function rileggiFormazione() {
  stato.fuocoFormazione = fuocoDi(document.activeElement);
  vistaFormazione();
}

// Anticipi già cominciati (#373): chi gioca una partita già cominciata non si sposta più (campo `bloccati` di GET /api/formazione;
// manca senza anticipi cominciati e con un server vecchio). Il server rifiuta comunque un salvataggio che ne sposta uno.
const giocatoriFermi = f => new Set((Array.isArray(f && f.bloccati) ? f.bloccati : []).map(Number));
// Chi può prendere il posto di `base`: stesso ruolo, non già fra i titolari (`dentro`) e non fermo, il migliore per punti attesi in
// cima. Nessuno se `base` stesso è fermo.
function sostituti(f, base, dentro) {
  const fermi = giocatoriFermi(f);
  if (fermi.has(Number(base.id))) return [];
  return Object.values(f.schede).filter(x => x.ruolo === base.ruolo && !dentro.has(x.id) && !fermi.has(Number(x.id)))
    .sort((a, b) => b.punti_attesi - a.punti_attesi);
}
// La Formazione si ridisegna (modulo, «Torna alla consigliata», un salvataggio arrivato): la sostituzione di un titolare aperta
// (`data-sostituzione`) si chiude, perché i suoi candidati erano quelli della formazione di prima. Le schede dei giocatori restano.
function chiudiSostituzione() {
  const foglio = $("#foglio");
  if (foglio && !foglio.hidden && $("#foglio-contenuto [data-sostituzione]")) chiudiFoglio();
}

function vistaFormazione() {
  const squadra = stato.squadraVista;
  if (squadra) {                                            // la formazione di un'altra squadra della lega: si guarda e basta
    caricaConCache("formazione-" + squadra, async () => ({ o: null, f: await api(`/api/formazione?squadra=${encodeURIComponent(squadra)}`) }),
      (b, opz) => mostraFormazione(b, squadra, opz), t("formazione.calcolo"));
    return;
  }
  caricaConCache("giornata", caricaGiornata, (b, opz) => mostraFormazione(b, null, opz), t("formazione.calcolo"));
}

// Tutto ciò che serve alla schermata, in una volta: la giornata (/api/oggi), la formazione, la scelta salvata e, se gli 11 salvati non
// sono quelli di un modulo già calcolato, la loro valutazione. Così la schermata si disegna una volta sola, già con la formazione
// giusta (prima compariva la consigliata e poi, un attimo dopo, la tua). `scelta`: null = niente di salvato; manca, con
// `scelta_non_letta`, = non letta (o non valutata): allora la schermata lo dice e non fa cambiare niente, perché un salvataggio
// scriverebbe sopra una scelta che non si è vista.
async function caricaGiornata() {
  // Account nuovo, senza rose (lo dice /api/stato, letto all'avvio): /api/formazione risponderebbe 409 e il browser lo scriverebbe fra
  // gli errori, quindi si chiede solo /api/oggi, che dà il benvenuto. Se le rose nel frattempo ci sono, la formazione si chiede dopo.
  const senzaRose = !!stato.info && stato.info.rose_importate === false;
  const [o, letta] = await Promise.all([api("/api/oggi"), senzaRose ? null : api("/api/formazione").catch(e => e)]);
  if (o.senza_rose) return { o, f: null };
  const f = letta || await api("/api/formazione");
  if (f instanceof Error) throw f;
  const b = { o, f };
  try {
    const s = await api(`/api/scelta?giornata=${f.giornata}`);
    b.scelta = s && Array.isArray(s.titolari) ? s : null;
  } catch { b.scelta_non_letta = true; return b; }
  const inCorso = o.fase === "in_corso" && o.in_corso;      // a giornata in corso la formazione che vale la dice /api/oggi
  if (b.scelta && f.stato_scelta !== "non_valida" && !inCorso && !moduloDi(f, b.scelta.titolari)) {
    try { b.valutata = await api("/api/formazione/valuta", { method: "POST", body: JSON.stringify({ titolari: b.scelta.titolari, giornata: f.giornata, salva: false }) }); }
    catch (e) { if (e.codice === "formazione_non_valida") b.non_valida = true; else { delete b.scelta; b.scelta_non_letta = true; } }
  }
  return b;
}

// La testa della schermata, diversa per fase. `o` manca quando si guarda la formazione di un'altra squadra.
function testaGiornata(o, f) {
  const giornata = `<p class="tg-giornata">${nomeGiornata(f.giornata_lega, f.giornata)}</p>`;
  if (!o) return giornata;
  const c = testoConto(o);
  const chiusura = `<p class="tg-scadenza"><b id="conto-chiude">${esc(c.chiude)}</b> <span id="conto">${esc(c.manca)}</span></p>`;
  const fase = o.fase || "prima";
  if (fase === "in_corso" && o.senza_formazione) {          // arrivato a partite cominciate: questa giornata non si gioca, si prepara la prossima
    return `<p class="tg-nota" role="status" id="formazione-prossima">${f.giornata_saltata
      ? elidiOrdinali(t("formazione.per_la_prossima", { g: nomeGiornata(f.giornata_saltata_lega, f.giornata_saltata), m: nomeGiornata(f.giornata_lega, f.giornata) }))
      : t("oggi.gia_iniziata_testo")}</p>${chiusura}`;
  }
  if (fase === "in_corso" && o.in_corso) {
    const c2 = o.in_corso;
    return `<p class="tg-giornata">${nomeGiornata(f.giornata_lega, f.giornata)} · <b>${t("formazione.in_corso")}</b></p>
      <p class="tg-punti"><b class="tg-numero" id="oggi-fatti">${num(c2.punti_fatti)}</b> ${t("formazione.punti_finora")}${c2.punti_previsti != null ? ` · ${t("formazione.circa_fine", { n: num(c2.punti_previsti, 0) })}` : ""}</p>
      <p class="tg-sotto">${c2.ancora_da_giocare ? tp("oggi.ancora_da_giocare", c2.ancora_da_giocare) : t("oggi.tutti_giocato")}</p>`;
  }
  if (fase === "finita" && o.riepilogo) {
    const r = o.riepilogo, tua = r.formazione_di === "tua";
    return `<div class="tg-finita" id="oggi-riepilogo"><div>
        <p class="tg-giornata">${t("oggi.giornata_finita", { g: nomeGiornata(r.giornata_lega, r.giornata) })}</p>
        <p class="tg-punti"><b class="tg-numero">${num(r.punti_fatti)}</b> ${r.punti_attesi != null ? t("formazione.punti_e_attesi", { n: num(r.punti_attesi) }) : t("formazione.punti")}</p></div>
        <button class="bottone secondario" type="button" data-apri-giornata="${Number(r.giornata)}">${t("formazione.come_andata")}</button></div>
      ${tua && r.consigliata && r.consigliata.punti_fatti !== r.punti_fatti ? `<p class="tg-sotto">${t("oggi.con_consigliata", { fatti: num(r.consigliata.punti_fatti), attesi: num(r.consigliata.punti_attesi) })}</p>` : ""}
      ${Array.isArray(r.recuperi) && r.recuperi.length ? `<p class="attenzione piccolo" id="oggi-recuperi">${t("oggi.recupero_manca", { partite: r.recuperi.map(partitaVs).join(", ") })}</p>` : ""}
      <div class="tg-prossima">${giornata}${chiusura}</div>`;
  }
  return giornata + (f.iniziata ? "" : chiusura);
}

// A giornata in corso: i cambi dalla panchina già fatti o probabili (campo `sostituzioni` di `in_corso`).
function cambiInCorso(c) {
  const cambi = (c.sostituzioni || []).filter(s => s && s.esce).map(s => `<li><span>${esc(s.esce.nome)} → ${s.entra ? esc(s.entra.nome) : t("oggi.nessun_sostituto")}</span>
    <span class="etichetta ${s.certa ? "" : "arancio"}">${t(s.certa ? "oggi.cambio_fatto" : "oggi.cambio_probabile")}</span></li>`).join("");
  return cambi ? `<div class="carta" id="cambi-panchina"><h2>${t("oggi.cambi_panchina")}</h2><ul class="cambi-live">${cambi}</ul></div>` : "";
}

// `b`: ciò che caricaGiornata ha letto ({o, f, scelta, valutata, non_valida}); per un'altra squadra solo {f}.
function mostraFormazione(b, squadra, opz = {}) {
  const { o, f } = b;
  if (o && o.senza_rose) { mostraSenzaRose(opz); return; }
  const l = livelloBase(f);
  const consigliato = l.moduli.find(m => m.modulo === l.modulo) || l.moduli[0];
  const fermi = giocatoriFermi(f);
  // a giornata in corso la formazione che vale la dice /api/oggi (titolari e panchina in ordine, con chi è entrato): non si cambia più
  const live = !squadra && o && o.fase === "in_corso" && o.in_corso && !o.senza_formazione && Array.isArray(o.in_corso.giocatori) ? o.in_corso : null;
  const diLive = new Map((live ? live.giocatori : []).map(g => [Number(g.id), g]));
  // la scheda di un giocatore: quella della Formazione, con sopra lo stato vero della sua partita a giornata in corso
  const scheda = id => {
    const x = f.schede[String(id)], g = diLive.get(Number(id));
    if (!g) return x;
    const dalVivo = { stato_partita: g.stato, fv_preso: g.fantavoto ?? null, ...(g.etichetta ? { etichetta: g.etichetta } : {}), ...(g.data ? { data_partita: g.data } : {}) };
    return x ? { ...x, ...dalVivo } : { id: g.id, nome: g.nome, ruolo: g.ruolo, squadra: g.squadra, ...dalVivo };
  };
  const chiusa = !!f.iniziata || !!live;
  const mia = !squadra;
  // `sola`: i comandi che scrivono sono spenti. Vale per la copia tenuta sul telefono, mostrata subito all'apertura, finché non
  // arrivano i dati nuovi (un tocco lì salvava, e i dati in arrivo ridisegnavano la pagina senza il cambio), e per la scelta non letta.
  const nonLetta = mia && (b.scelta_non_letta === true || b.scelta === undefined);
  const sc = stato.scelta = { chiave: `${squadra || "mia"}/${f.giornata}`, salvata: mia && !nonLetta ? b.scelta : undefined,
    nonValida: mia && (!!b.non_valida || f.stato_scelta === "non_valida"), manuale: null, richiesta: 0, occupato: false,
    nonLetta, copia: !!opz.daCache, sola: mia && (!!opz.daCache || nonLetta), fuoco: null };
  // la formazione di partenza: gli 11 salvati, se valgono e non sono proprio quelli della consigliata
  if (mia && sc.salvata && !sc.nonValida && !live) {
    const m = moduloDi(f, sc.salvata.titolari);
    if (m && m !== consigliato) sc.manuale = m;
    else if (!m && b.valutata) sc.manuale = { modulo: b.valutata.modulo, titolari: sc.salvata.titolari.map(Number), panchina: b.valutata.panchina,
      punteggio_atteso: b.valutata.punteggio_atteso, dev: b.valutata.dev, intervallo: b.valutata.intervallo };
  }
  const corrente = () => live ? { modulo: (o.formazione && o.formazione.modulo) || consigliato.modulo, titolari: live.giocatori.filter(g => g.titolare).map(g => Number(g.id)),
    panchina: live.giocatori.filter(g => !g.titolare).map(g => Number(g.id)) } : sc.manuale || consigliato;
  const diversi = m => m.titolari.filter(id => !consigliato.titolari.includes(id)).length;      // quanti titolari non sono quelli della consigliata
  const qui = n => n === sc.richiesta && stato.scelta === sc && document.body.contains($("#campo-formazione"));
  // dopo un salvataggio la copia sul telefono di questa schermata è già vecchia: la si aggiorna, così tornando qui non si rivede quella di prima
  // Il salvataggio è riuscito ma la schermata nel frattempo è stata ridisegnata (riaperta, o lasciata): la copia sul telefono è
  // vecchia e, se si è ancora nella Formazione, in pagina c'è altro. Si rilegge dal server: mai una scelta salvata che non si vede.
  const altrove = n => {
    rimuoviCache("giornata");
    if (n === sc.richiesta && stato.scelta !== sc && stato.vista === "formazione" && !stato.squadraVista) rileggiFormazione();
  };
  const ricorda = valutata => { if (mia) salvaCache("giornata", { ...b, scelta: sc.salvata, valutata: valutata || undefined, non_valida: false, f: { ...f, stato_scelta: sc.salvata ? "valida" : "nessuna" } }); };

  // Cambia gli 11 (una sostituzione, un altro modulo, la spunta «L'ho messa»): il server li valuta e li salva subito. Una richiesta
  // alla volta: se nel frattempo ne parte un'altra, la risposta di prima si ignora. `messa`: vero o falso dalla spunta; senza, resta
  // com'era finché gli 11 sono gli stessi (la stessa regola del server, scelte.salva).
  const salvaTitolari = async (ids, messa, fuoco = null) => {
    const n = ++sc.richiesta;
    sc.occupato = true;
    try {
      const r = await api("/api/formazione/valuta", { method: "POST", body: JSON.stringify({ titolari: ids, giornata: f.giornata, salva: true, ...(messa === undefined ? {} : { messa }) }) });
      if (!qui(n)) { altrove(n); return false; }
      const stessi = !!sc.salvata && stessiIds(ids, sc.salvata.titolari.map(Number));
      const eraConsigliata = stessiIds(ids, consigliato.titolari) || (stessi && sc.salvata.era_consigliata === true);
      sc.salvata = { titolari: ids, modulo: r.modulo, ...(eraConsigliata ? { era_consigliata: true } : {}), ...((messa ?? (stessi && sc.salvata.messa === true)) ? { messa: true } : {}) };
      sc.nonValida = false;
      const m = moduloDi(f, ids);
      sc.manuale = m === consigliato ? null : m || { modulo: r.modulo, titolari: ids, panchina: r.panchina, punteggio_atteso: r.punteggio_atteso, dev: r.dev, intervallo: r.intervallo };
      ricorda(m ? null : r);
      if (fuoco) sc.fuoco = fuoco;
      disegna(true);
      return true;
    } catch (e) {
      if (e.status === 412) { avviso(e.message, 5000); return false; }      // cambiata su un altro dispositivo: api() ricarica la pagina con i dati di là
      if (!qui(n)) return false;
      avviso(e.message, 5000);
      if (e.codice === "formazione_chiusa") rileggiFormazione(); else disegna(true);      // scadenza passata con la pagina aperta: si rilegge tutto
      return false;
    } finally { if (n === sc.richiesta) sc.occupato = false; }
  };
  // «Torna alla consigliata»: toglie la scelta salvata, e da lì in poi vale la consigliata (che si aggiorna da sola fino alla scadenza).
  const tornaConsigliata = async () => {
    if (!mia) { sc.manuale = null; disegna(true); return; }
    const n = ++sc.richiesta;
    sc.occupato = true;
    try {
      if (sc.salvata !== null) await api(`/api/scelta?giornata=${f.giornata}`, { method: "DELETE" });
      if (!qui(n)) { altrove(n); return; }
      sc.manuale = null; sc.salvata = null; sc.nonValida = false;
      ricorda();
      disegna(true);
    } catch (e) {
      if (e.status === 412) { avviso(e.message, 5000); return; }
      if (!qui(n)) return;
      avviso(e.message, 5000);                              // per esempio la consigliata sposterebbe chi gioca un anticipo già cominciato (#373)
      if (e.codice === "formazione_chiusa") rileggiFormazione(); else disegna(true);
    } finally { if (n === sc.richiesta) sc.occupato = false; }
  };
  const libero = () => { if (sc.occupato) avviso(t("formazione.sto_ancora_ricalcolando")); return !sc.occupato; };
  // Un titolare esce e al suo posto entra un altro dello stesso ruolo (dalla scheda del giocatore o da una decisione in cima).
  const sostituisci = (esce, entra) => {
    const m = corrente();
    if (chiusa || !mia || sc.sola || !m.titolari.includes(esce) || m.titolari.includes(entra) || fermi.has(esce) || fermi.has(entra)) return false;
    if (!libero()) return true;
    salvaTitolari(m.titolari.map(id => id === esce ? entra : id), undefined, `#campo-formazione [data-giocatore="${Number(entra)}"]`);   // dopo, il fuoco su chi è entrato
    return true;
  };

  // La riga dello stato sotto il campo: due stati («è la consigliata», «l'hai cambiata tu») più «chiusa» e «non più valida».
  const rigaStato = m => {
    // la scelta non si è letta: lo si dice (un errore, con «Riprova»); sulla copia del telefono no, i dati nuovi stanno arrivando
    if (mia && sc.nonLetta && !chiusa) return sc.copia ? "" : `<div class="scelta-non-letta">${errore({ message: t("formazione.scelta_non_letta") })}
      <div class="pulsanti"><button class="bottone secondario" type="button" data-riprova>${t("comune.riprova")}</button></div></div>`;
    if (!mia || sc.salvata === undefined) return "";
    const riga = (classe, testo, azione = "") => `<div class="stato-scelta ${classe}" id="stato-scelta"><p role="status">${testo}</p>${azione}</div>`;
    const torna = `<button class="azione-testo" type="button" id="torna-consigliata" data-scrive${sc.sola ? " disabled" : ""}>${t("formazione.torna_alla_consigliata")}</button>`;
    if (chiusa) return riga("chiusa", t(sc.nonValida ? "formazione.stato_chiusa_non_valida" : sc.salvata ? "formazione.stato_chiusa_tua" : "formazione.stato_chiusa"));
    if (sc.nonValida) return riga("non_valida", t("formazione.stato_non_valida_ora"), torna);
    const n = diversi(m);
    if (!n) return riga("consigliata", t("formazione.stato_e_consigliata"));
    // «(−0,4 punti attesi)»: quanto vale la tua rispetto alla consigliata, con il nome del numero
    const d = Number.isFinite(m.punteggio_atteso) && Number.isFinite(consigliato.punteggio_atteso)
      ? ` (${t("formazione.stato_punti", { d: segno(m.punteggio_atteso - consigliato.punteggio_atteso, 1) })})` : "";
    // era la consigliata quando l'hai salvata (o messa) ed è lei a essere cambiata dopo, oppure l'hai cambiata tu
    return riga("cambiata", sc.salvata && sc.salvata.era_consigliata ? tp("formazione.stato_superata", n, { d }) : tp("formazione.stato_cambiata", n, { d }), torna);
  };

  const disegna = (mantieniScroll = false) => {
    chiudiSostituzione();                                   // i candidati aperti erano quelli della formazione di prima
    const y0 = window.scrollY;
    // il fuoco dopo il ridisegno: dove l'ha chiesto chi ha fatto il cambio, altrimenti sullo stesso comando di prima
    const fuoco = sc.fuoco ?? stato.fuocoFormazione ?? fuocoDi(document.activeElement);
    sc.fuoco = null; stato.fuocoFormazione = null;
    const spento = sc.sola ? " disabled" : "";
    const m = corrente();
    const titolari = m.titolari.map(scheda).filter(Boolean), panchina = m.panchina.map(scheda).filter(Boolean);
    const scelti = new Set([...m.titolari, ...m.panchina]);
    const altri = Object.values(f.schede).filter(x => !scelti.has(x.id)).map(x => scheda(x.id)).sort((a, b) => b.punti_attesi - a.punti_attesi);
    const fermo = x => ["infortunato", "squalificato", "fuori"].includes(codiceStato(x));
    const nonSchierati = altri.filter(x => !fermo(x)), indisponibili = altri.filter(fermo);
    const linee = { P: [], D: [], C: [], A: [] };
    titolari.forEach(x => (linee[x.ruolo] || linee.A).push(x));
    // per la scheda del giocatore e la sostituzione: la formazione in pagina e cosa ci si può fare
    // `fermo`: un titolare che gioca un anticipo già cominciato; al posto di «Sostituisci» la scheda dice perché non si sposta
    stato.formaz = { f, modulo: m, scheda, perche: id => (sc.manuale || chiusa ? "" : percheTitolare(m, id, scheda)),
      pronta: () => !sc.sola,
      sostituibile: id => mia && !chiusa && m.titolari.includes(id) && !fermi.has(id),
      fermo: id => mia && !chiusa && m.titolari.includes(id) && fermi.has(id), sostituisci };
    // le decisioni che hanno ancora senso con la formazione in pagina: un cambio già fatto non si propone più, e «la consigliata è
    // cambiata» vale finché c'è una tua scelta salvata diversa da lei
    const vale = v => v.tipo === "dubbio" ? !chiusa && !!v.giocatore && m.titolari.includes(Number(v.giocatore.id)) && !m.titolari.includes(Number(v.alternativa.id))
      : dfConsigliataCambiata(v) ? !chiusa && !!sc.salvata && diversi(m) > 0 : true;
    const decisioni = mia && o ? dfDecisioni(o.da_fare, vale) : [];
    // «+0,9 punti»: quanto vale in più, da solo, il sostituto proposto rispetto al titolare (i punti attesi sono quelli del server)
    const guadagno = v => {
      const x = v.tipo === "dubbio" && v.giocatore ? scheda(v.giocatore.id) : null;
      const d = x && v.alternativa ? v.alternativa.punti_attesi - x.punti_attesi : NaN;
      return Number.isFinite(d) && d >= 0.05 ? t("formazione.decisione_punti", { d: segno(d, 1) }) : "";
    };
    const moduli = l.moduli.some(x => x.modulo === m.modulo) ? l.moduli : [...l.moduli, m];
    const opzione = x => `<option value="${esc(x.modulo)}" ${x.modulo === m.modulo ? "selected" : ""}>${t(x === consigliato ? "formazione.opzione_consigliato" : "formazione.opzione_modulo", { modulo: esc(x.modulo), punti: num(x.punteggio_atteso) })}</option>`;
    const diSolito = fraseDiSolito(m);
    const probabili = o && o.probabili && !chiusa ? `<p class="debole piccolo probabili-fresche" id="probabili-fresche">${esc(testoDi(o.probabili))} (${esc(o.probabili.eta_frase ? testoDi(o.probabili, "eta") : traduciDurata(o.probabili.eta))})</p>${o.probabili.vecchie && o.probabili.avviso ? `<div class="attenzione" role="status">${esc(testoDi(o.probabili, "avviso"))}</div>` : ""}` : "";
    const elenco = (righe, numerati) => `${intestazioneColonne({ partita: true })}<ul class="elenco">${righe.map((x, k) => voceGiocatore(x, numerati ? k + 1 : null)).join("")}</ul>`;
    pagina(`<div class="fz${chiusa ? " chiusa" : ""}">
      <div class="fz-testa">
        ${squadra ? `<div class="attenzione" role="status">${t("formazione.stai_guardando_formazione")} <b>${esc(f.squadra)}</b>.
          <button class="azione-testo" type="button" id="torna-mia">${t("formazione.torna_alla_tua")}</button></div>` : ""}
        ${testaGiornata(squadra ? null : o, f)}
      </div>
      ${decisioni.length ? `<ul class="fz-decisioni" id="decisioni" aria-label="${t("df.da_fare")}">${decisioni.map((v, i) => dfRiga(v, i, guadagno(v), sc.sola)).join("")}</ul>` : ""}
      <div class="fz-campo"><div class="campo-fermo">
        ${live ? "" : `<div class="riga-modulo">
          ${chiusa ? `<span class="modulo-fisso">${esc(m.modulo)}</span>` : `<label class="menu-scelta menu-modulo"><span class="solo-lettori">${t("formazione.modulo")}</span>
            <span class="menu-scelta-testo" aria-hidden="true">${esc(m.modulo)}</span><select id="modulo" data-scrive${spento}>${moduli.map(opzione).join("")}</select></label>`}
          <div class="punti-attesi"><span><b id="punti-attesi">${num(m.punteggio_atteso)}</b> ${t("formazione.punti_attesi")}</span>${diSolito ? `<span class="debole piccolo" id="di-solito">${esc(diSolito)}</span>` : ""}</div>
        </div>`}
        <div class="campo" id="campo-formazione"><i class="area-alta"></i><i class="cerchio"></i><i class="meta"></i>
          ${["P", "D", "C", "A"].map(rr => `<div class="linea">${linee[rr].map(pedina).join("")}</div>`).join("")}
        </div>
        ${rigaStato(m)}
        ${mia && !chiusa ? `<div class="azioni-formazione">
          <button class="bottone secondario" type="button" id="copia"${sc.nonLetta ? " disabled" : ""}>${t("formazione.copia_lega")}</button>
          <label class="spunta"><input type="checkbox" id="messa" ${sc.salvata && sc.salvata.messa ? "checked" : ""}${sc.nonValida ? " disabled" : ` data-scrive${spento}`}><span>${t("formazione.messa")}</span></label>
        </div>` : ""}
        ${chiusa || f.con_probabili ? "" : `<div class="attenzione" role="status" id="senza-probabili">${t("formazione.mancano_probabili_formazioni")}</div>`}
        ${probabili}
      </div></div>
      <div class="fz-lato">
        ${live ? cambiInCorso(live) : ""}
        <div class="carta" id="panchina"><h2>${t("scambi.panchina")}</h2><div class="debole piccolo">${t("formazione.quest_ordine_entra")}</div>
          ${elenco(panchina, true)}</div>
        ${nonSchierati.length || f.senza_dati.length ? `<div class="carta"><details><summary>${t("formazione.non_schierati", { n: nonSchierati.length })}</summary>${nonSchierati.length ? elenco(nonSchierati) : ""}
          ${f.senza_dati.length ? `<div class="debole piccolo">${t("formazione.senza_dati", { nomi: f.senza_dati.map(esc).join(", ") })}</div>` : ""}</details></div>` : ""}
        ${indisponibili.length ? `<div class="carta"><details><summary>${t("formazione.indisponibili", { n: indisponibili.length })}</summary>${elenco(indisponibili)}</details></div>` : ""}
        ${mia && o ? cardRinvio(o.rinvio) : ""}
        ${mia && o && o.fase === "finita" && o.riepilogo && o.riepilogo.rinvio ? `<div class="carta rinvio">${menuRinvio(o.riepilogo.rinvio)}</div>` : ""}
      </div></div>`,
      { ...opz, stato: false, daCache: mantieniScroll ? null : opz.daCache, sostituisce: opz.sostituisce || mantieniScroll });
    const bottone = (id, fn) => { const e = $(id); if (e) e.addEventListener("click", fn); };
    const sel = $("#modulo");
    if (sel) sel.addEventListener("change", () => {
      const scelto = l.moduli.find(x => x.modulo === sel.value);
      if (!scelto || sc.sola || !libero()) { disegna(true); return; }
      if (!mia) { sc.manuale = scelto === consigliato ? null : scelto; disegna(true); }
      else if (scelto === consigliato) tornaConsigliata();
      else salvaTitolari([...scelto.titolari]);
    });
    document.querySelectorAll("#decisioni [data-df]").forEach(el => el.addEventListener("click", () => {
      const v = decisioni[Number(el.dataset.df)];
      if (!v) return;
      if (sc.sola && dfScrive(v)) return;
      if (v.tipo === "dubbio" && v.alternativa && v.giocatore && sostituisci(Number(v.giocatore.id), Number(v.alternativa.id))) return;
      if (v.tipo === "dubbio" && v.giocatore) { apriGiocatore(Number(v.giocatore.id)); return; }      // il cambio non si può più fare da qui: la sua scheda
      if (dfConsigliataCambiata(v)) { if (libero()) tornaConsigliata(); return; }
      dfApri(v);
    }));
    bottone("#torna-consigliata", () => { if (!sc.sola && libero()) tornaConsigliata(); });
    bottone("#copia", async () => avviso(await copiaTesto(testoFormazione(f, m, scheda)) ? t("formazione.copiata_lega") : t("formazione.non_copio")));
    const messa = $("#messa");
    if (messa) messa.addEventListener("change", () => {
      if (sc.sola || !libero()) { messa.checked = !messa.checked; return; }
      // messa o tolta, la spunta salva gli 11 in pagina: una scelta salvata (anche da un altro dispositivo) non si cancella da sola,
      // si toglie solo con «Torna alla consigliata»
      salvaTitolari(m.titolari.map(Number), messa.checked);
    });
    bottone("#torna-mia", () => { stato.squadraVista = null; vistaFormazione(); });
    collegaRinvio();
    const comeAndata = $("[data-apri-giornata]");       // «Com'è andata»: la pagina Giornate, aperta sulla giornata appena finita
    if (comeAndata) comeAndata.addEventListener("click", () => vaiGiornate(Number(comeAndata.dataset.apriGiornata) || undefined));
    if (mantieniScroll) window.scrollTo(0, y0);
    // la scheda di un giocatore rimasta aperta: il suo «Sostituisci» segue lo stato della schermata
    document.querySelectorAll("#foglio-contenuto [data-sostituisci]").forEach(e => { e.disabled = sc.sola; });
    if (fuoco !== null) {                                   // mai sul vuoto: lo stesso comando, o il più vicino che c'è
      const dove = (fuoco ? [fuoco, "#copia", "#modulo", "#titolo-pagina"] : ["#titolo-pagina"]).map(s => $(s)).find(e => e && !e.disabled);
      // con il foglio modale ancora in chiusura la pagina sotto non prende il fuoco: glielo dà il foglio quando ha finito (sbloccaSfondo)
      if (dove && sfondoBloccato) focusPrima = dove; else if (dove) dove.focus({ preventScroll: true });
    }
  };

  disegna(false);
  // il conto alla rovescia si aggiorna da solo finché si resta in questa schermata
  clearInterval(timerConto);
  if (o && !squadra) {
    const idTimer = timerConto = setInterval(() => {
      const el = $("#conto"), chiude = $("#conto-chiude");
      if (!el || !chiude) { clearInterval(idTimer); return; }
      const ct = testoConto(o);
      el.textContent = ct.manca; chiude.textContent = ct.chiude;
    }, 30000);
  }
  // Per caricaConCache: i dati nuovi sono uguali alla copia in pagina, i comandi spenti si accendono dove sono (niente ridisegno).
  // Se la scelta non era stata letta nemmeno stavolta, ora lo si dice.
  return { pronta() {
    if (stato.scelta !== sc || !sc.sola) return;
    sc.copia = false;
    if (sc.nonLetta) { disegna(true); return; }
    sc.sola = false;
    document.querySelectorAll("#contenuto [data-scrive], #foglio-contenuto [data-sostituisci]").forEach(e => { e.disabled = false; });
  } };
}

async function datiCalendario() {
  if (stato.calendario) return stato.calendario;
  const salvata = leggiCache("calendario");
  const fresco = api("/api/calendario").then(c => { stato.calendario = c; salvaCache("calendario", c); return c; });
  if (salvata) { fresco.catch(() => {}); return salvata.dati; }
  return fresco;
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

// La squadra di Serie A di un giocatore come la tabella delle sigle la conosce: il listone a volte scrive il nome («Inter») invece della chiave.
const slugQualunque = s => SIGLE[s] ? s : SIGLE[normNome(s)] ? normNome(s) : s;

// ---------------------------------------------------------------- scheda giocatore (pannello)
function formaGiocatore(voti) {
  const ultimi = voti.slice(-5);
  if (!ultimi.length) return null;
  const colore = v => v == null ? "sv" : v >= 7 ? "alto" : v >= 6 ? "medio" : "basso";
  const pallini = `<div class="pallini">${ultimi.map(v => `<i class="${colore(v.fv)}" title="${nomeGiornata(null, v.giornata)}">${v.fv == null ? t("mercato.sv") : num(v.fv, 1)}</i>`).join("")}</div>`;
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
      punti.map(v => `<circle class="${cl}" r="3" cx="${x(v.giornata).toFixed(1)}" cy="${y(v[chiave]).toFixed(1)}"><title>${nomeGiornata(null, v.giornata)}: ${num(v[chiave])}</title></circle>`).join("");
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
  const righe = x.perche_numero.map(m => `<li class="perche-voce"><span>${esc(testoDi(m))}</span>${effetto(m.effetto)}</li>`).join("");   // l'effetto a destra, in colonna (spec §9)
  return `<div class="perche"><h3>${t("perche.titolo")}</h3>${righe ? `<ul class="perche-lista">${righe}</ul>` : ""}
    <div class="debole piccolo">${t(righe ? "perche.rispetto" : "perche.nessuno", { n: num(medio) })}</div></div>`;
}

// La scheda del giocatore (#616): una sola, al posto di scheda, «Perché questo numero» e sostituzione. In alto ciò che serve per
// decidere: il fantavoto atteso (se gioca), «gioca N%» con lo stato a parole e la nota che lo spiega, perché è titolare, i motivi del numero, gli ultimi voti
// e, per un titolare della tua formazione ancora aperta, «Sostituisci» (se gioca un anticipo già cominciato, la riga che dice che non
// si sposta più). Tutto il resto (probabilità, stagione, occasioni, prossime partite) sta dietro «Tutti i numeri».
// `c`: {id, nome, ruolo, squadra, squadra_slug}; `pr`: la sua previsione per la giornata (la scheda della Formazione o `previsione`
// di /api/giocatore), null se non c'è; `fz`: la Formazione in pagina (stato.formaz), se la scheda si apre da lì.
function htmlScheda(c, pr, fz) {
  const esito = pr ? esitoPartita(pr) : null, stato = pr && !esito ? parolaStato(pr) : null;
  const finitaP = !!pr && PARTITA_FINITA.includes(pr.stato_partita);
  const preso = !!esito && esito.fv != null;
  const q = pr ? giocaLetto(pr) : 0;
  const perche = fz && pr ? fz.perche(Number(c.id)) : "";
  // a partita cominciata «gioca N%» non serve più: fuori anche dai motivi
  const prSenzaGioca = pr && esito && Array.isArray(pr.perche_numero) ? { ...pr, perche_numero: pr.perche_numero.filter(m => m.chiave !== "gioca") } : pr;
  const nota = pr ? notaStato(pr, stato) : "";
  const partita = pr && pr.avversario ? t(pr.in_casa ? "formazione.partita_casa" : "formazione.partita_fuori", { avv: `<span style="text-transform:capitalize">${esc(pr.avversario)}</span>`, quando: quando(pr.data_partita) }) : "";
  const cifre = !pr ? `<div class="attenzione">${t("mercato.nessuna_previsione_per")}</div>`
    : `<div class="cifre-oggi cifre-scheda">
        ${preso ? `<div class="cifra"><div class="debole">${t("mercato.fantavoto")}</div><div class="enorme">${num(esito.fv)}</div></div>`
          : finitaP ? `<div class="cifra"><div class="grande stato-partita">${esc(esito.testo)}</div></div>`
          : `<div class="cifra"><div class="debole">${t("mercato.fantavoto_atteso")}, ${t("formazione.se_gioca")}</div><div class="enorme">${num(pr.fv_atteso)}</div></div>`}
        ${esito ? (finitaP ? "" : `<div class="cifra"><div class="grande stato-partita">${esc(esito.testo)}</div></div>`)
          : `<div class="cifra"><div class="debole">${t("mercato.gioca")}</div><div class="grande${q < SOGLIA_GIOCA ? " gioca-" + classeGioca(q) : ""}">${perc(q)}</div>
              ${stato ? `<div class="etichetta ${stato.classe}">${esc(stato.testo)}</div>` : ""}</div>`}
      </div>`;
  return `
    <div class="intestazione-scheda">
      ${volto({ id: c.id, nome: c.nome, squadra: c.squadra_slug, ruolo: c.ruolo }, true)}
      <div><h2>${esc(c.nome)}</h2>
        <div class="debole">${NOME_RUOLO_1[c.ruolo] || esc(c.ruolo)} · ${esc(c.squadra)}${pr && pr.diffidato ? ` · <span class="etichetta arancio">${t("oggi.diffidato_tipo")}</span>` : ""}</div>
        ${partita ? `<div class="debole">${partita}</div>` : ""}</div>
    </div>
    ${cifre}
    ${nota ? `<p class="scheda-nota">${esc(nota)}</p>` : ""}
    ${perche ? `<div class="scheda-pezzo" id="perche-titolare"><h3>${t("formazione.perche_titolare")}</h3><p>${perche}</p></div>` : ""}
    ${pr && !finitaP ? bloccoPerche(prSenzaGioca) : ""}
    <div class="scheda-pezzo" id="scheda-voti" aria-busy="true"><h3>${t("formazione.ultimi_voti")}</h3><div class="debole piccolo">${t("comune.carico")}</div></div>
    ${fz && fz.sostituibile(Number(c.id)) ? `<div class="pulsanti"><button class="bottone" type="button" data-sostituisci="${Number(c.id)}"${fz.pronta() ? "" : " disabled"}>${t("formazione.sostituisci")}</button></div>`
      : fz && fz.fermo(Number(c.id)) ? `<p class="debole piccolo" id="scheda-fermo">${t("formazione.bloccati")}</p>` : ""}
    <details class="scheda-numeri" id="scheda-numeri"><summary>${t("formazione.tutti_numeri")}</summary>
      <div id="scheda-numeri-corpo" aria-busy="true"><div class="debole piccolo">${t("comune.carico")}</div></div></details>`;
}

// Gli ultimi voti e «Tutti i numeri», quando arriva la scheda intera (/api/giocatore). `cal`: il calendario, per le prossime partite.
function riempiScheda(s, cal) {
  const voti = $("#scheda-voti"), numeri = $("#scheda-numeri-corpo");
  if (!voti || !numeri) return;
  const c = s.calciatore, st = s.stagione, av = s.avanzate, pr = s.previsione;
  const forma = formaGiocatore(s.voti || []);
  voti.innerHTML = `<h3>${t("formazione.ultimi_voti")}</h3>${forma ? forma.pallini : `<div class="debole">${t("mercato.nessuna_presenza_questa")}</div>`}`;
  voti.removeAttribute("aria-busy");
  const grafico = graficoVoti(s.voti || [], st.giornate_giocate_serie_a);
  const prossime = cal && pr ? (cal.squadre.find(x => x.squadra === pr.squadra) || { partite: [] }).partite : [];
  const iniziataP = !!pr && PARTITA_INIZIATA.includes(pr.stato_partita);
  const nonGioca = !!pr && nonGiocaDiSicuro(parolaStato(pr));              // infortunato o squalificato: niente partita, gol o cartellini
  const tile = (valore, etichetta) => `<div><b>${valore}</b><span>${etichetta}</span></div>`;
  const probabilita = !pr ? "" : c.ruolo === "P"
    ? tile(perc(pr.porta_inviolata), t("mercato.porta_inviolata")) + tile(num(pr.gol_avversario, 1), t("mercato.gol_subiti_attesi")) + tile(perc(pr.p_giallo), t("mercato.giallo"))
    : tile(perc(pr.p_gol), t("mercato.segna")) + tile(perc(pr.p_assist), t("mercato.assist")) + tile(perc(pr.p_giallo), t("mercato.giallo")) + tile(perc(pr.p_rosso), t("mercato.rosso"));
  const motivi = pr && !iniziataP ? motiviUtili(pr).filter(senzaPercentuale) : [];
  numeri.innerHTML = `
    <div class="etichette"><span class="etichetta ${s.proprietario ? "neutra" : "arancio"}">${s.proprietario ? esc(s.proprietario) : t("mercato.svincolato")}</span><span class="etichetta neutra">${t("mercato.quot", { n: c.quotazione })}</span></div>
    ${pr && !nonGioca && !iniziataP ? `<h3>${t("formazione.questa_partita")}</h3>
      <div class="riga"><span>${diffPill(pr.difficolta)}</span><span class="debole piccolo">${t("mercato.gol_attesi", { a: num(pr.gol_squadra, 1), b: num(pr.gol_avversario, 1) })}</span></div>
      ${motivi.length ? `<div class="etichette">${motivi.map(m => `<span class="etichetta neutra">${testoEtichetta(traduciFrase(m.frase, m.testo))}</span>`).join("")}</div>` : ""}
      <div class="stat-fila ${c.ruolo === "P" ? "" : "quattro"}" style="margin-top:12px">${probabilita}</div>` : ""}
    ${prossime.length ? `<h3>${t("mercato.prossime_partite")}</h3><div class="prossime">${prossime.map(p => `<span class="cella d${p.difficolta}">${vsAt(p)}</span>`).join("")}</div>
      <div class="debole piccolo" style="margin-top:8px">${t("mercato.colori_verde_partita")}</div>` : ""}
    ${forma ? `<h3>${t("mercato.forma")}</h3><div class="riga"><span class="debole piccolo">${t("mercato.andamento")}</span><b class="${forma.classe}">${forma.freccia} ${forma.testo}</b></div>` : ""}
    ${grafico}
    ${s.rendimento ? `<h3>${t("mercato.rende_sopra_sotto")}</h3>
      <div class="grande ${s.rendimento.sovra_rendimento > 0.3 ? "positivo" : s.rendimento.sovra_rendimento < -0.3 ? "negativo" : ""}">${segno(s.rendimento.sovra_rendimento, 2)} <span class="debole" style="font-size:var(--t-corpo);font-weight:400">${t("mercato.punti_partita")}</span></div>
      <div class="debole piccolo">${t("mercato.rendimento_riga", { g: segno(s.rendimento.gol_meno_xg), a: segno(s.rendimento.assist_meno_xa) })}
        ${t(s.rendimento.sovra_rendimento > 0.3 ? "mercato.rend_cala" : s.rendimento.sovra_rendimento < -0.3 ? "mercato.rend_sblocca" : "mercato.rend_linea")}</div>` : ""}
    <h3>${t("mercato.stagione")}</h3><div class="statistiche">
      ${tile(`${st.presenze}/${st.giornate_giocate_serie_a}`, t("mercato.presenze"))}${tile(num(st.media_voto, 2), t("mercato.media_voto"))}${tile(num(st.fantamedia, 2), t("mercato.fantamedia"))}
      ${tile(st.gol + st.rig_segnati, t("mercato.gol_rig", { n: st.rig_segnati }))}${tile(st.assist, tp("mercato.n_assist", st.assist))}${tile(`${st.ammonizioni}/${st.espulsioni}`, t("mercato.gialli_rossi"))}
      ${c.ruolo === "P" ? tile(st.gol_subiti, t("mercato.gol_subiti")) + tile(st.rig_parati, t("mercato.rigori_parati")) : ""}</div>
    ${av && av.minuti ? `<h3>${t("mercato.statistiche_avanzate")}</h3><div class="statistiche">
      ${tile(num(av.xg, 2), t("mercato.gol_attesi_tot"))}${tile(num(av.xa, 2), t("mercato.assist_attesi_tot"))}${tile(`${av.minuti}'`, t("mercato.minuti"))}
      ${tile(num(av.per_90?.xg, 2), t("mercato.xg_90"))}${tile(num(av.per_90?.xa, 2), t("mercato.xa_90"))}${tile(num(av.per_90?.tiri, 1), t("mercato.tiri_90"))}
      ${tile(av.rigori_calciati, t("mercato.rigori_calciati"))}${tile(av.passaggi_chiave, t("mercato.passaggi_chiave"))}${tile(av.punizioni, t("mercato.punizioni"))}</div>
      ${(av.stagioni_precedenti || []).map(p => `<div class="debole piccolo" style="margin-top:8px">${t("mercato.stagione_prec", { s: esc(p.stagione), m: p.minuti, g: p.gol, xg: num(p.xg), a: p.assist, xa: num(p.xa) })}</div>`).join("")}` : ""}`;
  numeri.removeAttribute("aria-busy");
}

let ultimaScheda = 0;
// Dalla Formazione i dati del giocatore ci sono già (la sua scheda nella risposta): la scheda si apre subito, con «Sostituisci», e gli
// ultimi voti e «Tutti i numeri» si riempiono quando arriva /api/giocatore. Da altrove (ricerca, rosa, Diario) si aspetta quella.
async function apriGiocatore(id) {
  const numero = ++ultimaScheda;
  const fz = stato.vista === "formazione" && stato.formaz ? stato.formaz : null;
  const locale = fz ? fz.scheda(id) : null;
  if (locale) apriFoglio(htmlScheda({ id, nome: locale.nome, ruolo: locale.ruolo, squadra: nomeClub(locale.squadra), squadra_slug: locale.squadra }, locale, fz), { affianco: true });
  else apriFoglio(`<div class="caricamento">${t("mercato.carico_scheda")}</div>`, { affianco: true });
  const ancoraLei = () => numero === ultimaScheda && !$("#foglio").hidden;
  try {
    const [s, cal] = await Promise.all([api(`/api/giocatore/${id}`), datiCalendario().catch(() => null)]);
    if (!ancoraLei()) return;
    if (!locale) apriFoglio(htmlScheda(s.calciatore, s.previsione, fz), { affianco: true });
    riempiScheda(s, cal);
  } catch (e) {
    if (!ancoraLei()) return;
    if (!locale) { apriFoglio(errore(e), { affianco: true }); return; }
    // la scheda aperta dalla Formazione resta com'è: mancano solo gli ultimi voti e «Tutti i numeri», e lo dice lì
    for (const pezzo of [$("#scheda-voti"), $("#scheda-numeri-corpo")]) if (pezzo) { pezzo.innerHTML = errore(e); pezzo.removeAttribute("aria-busy"); }
  }
}

// «Sostituisci» (dalla scheda di un titolare): i compagni dello stesso ruolo che non sono titolari, il migliore in cima, ognuno con
// i punti attesi in più o in meno rispetto a lui: è già il confronto, in una riga. Un tocco fa il cambio, che si salva da solo.
function apriSostituzione(id) {
  const fz = stato.vista === "formazione" ? stato.formaz : null, base = fz && fz.scheda(id);
  if (!base || !fz.sostituibile(Number(id)) || !fz.pronta()) return;
  ultimaScheda++;                                                         // una scheda ancora in arrivo non prende il posto dell'elenco
  const candidati = sostituti(fz.f, base, new Set(fz.modulo.titolari)).map(x => fz.scheda(x.id));
  // sotto il nome anche «gioca N%», se è sotto l'80%: spiega un numero grande basso per chi, quando gioca, vale quanto il titolare
  const giocaPoco = x => {
    const q = giocaLetto(x);
    return !esitoPartita(x) && !nonGiocaDiSicuro(parolaStato(x)) && q < SOGLIA_GIOCA
      ? `<span class="etichetta ${classeGioca(q) === "basso" ? "rossa" : "arancio"}">${t("giocatore.gioca", { p: perc(q) })}</span>` : "";
  };
  const riga = x => {
    const d = x.punti_attesi - base.punti_attesi;
    return `<li class="riga-gioc"><button class="voce voce-g" data-entra="${x.id}">${volto(x)}
      <span class="testo-g"><span class="nome"><span class="ruolo-l">${esc(ruoloSigla(x.ruolo))}</span><span class="nome-t">${esc(x.nome)}</span></span>
        <span class="dettaglio">${lineetta(x.squadra)}${pezziRiga([x.avversario ? partitaBreve(x) : sigla(x.squadra), postoInFormazione(x.id)])}</span>
        <span class="etichette">${etichetteGiocatore(x, giocaPoco(x))}</span></span>
      <span class="valore"><b class="${d > 0.04 ? "positivo" : ""}">${segno(d, 1)}</b><span class="solo-lettori"> ${t("formazione.punti_rispetto", { nome: esc(base.nome) })}</span></span>
      <span class="pv-g">${t("formazione.fv_atteso_breve", { fv: num(x.fv_atteso) })}</span></button></li>`;
  };
  apriFoglio(`<h2 class="titolo-foglio">${t("formazione.al_posto_di", { nome: esc(base.nome) })}</h2>
    <div class="debole piccolo">${t("formazione.sost_spiega", { nome: esc(base.nome) })}</div>
    <div data-sostituzione>${candidati.length ? `<ul class="elenco" style="margin-top:8px">${candidati.map(riga).join("")}</ul>` : `<div class="debole" style="margin-top:12px">${t("formazione.nessun_altro_giocatore")}</div>`}</div>`, { affianco: true });   // accanto al campo, da 1200 px
  document.querySelectorAll("#foglio-contenuto [data-entra]").forEach(b => b.addEventListener("click", () => {
    // con il pannello affiancato la pagina resta attiva: nel frattempo il modulo o «Torna alla consigliata» possono aver cambiato
    // la formazione. Si chiude comunque; il cambio si fa solo se il titolare c'è ancora.
    const formazione = stato.vista === "formazione" ? stato.formaz : null;
    chiudiFoglio();
    if (formazione) formazione.sostituisci(Number(id), Number(b.dataset.entra));
  }));
}

// Il posto in formazione a parole: «Titolare», «Panchina 2», «Non schierato» (codici `titolare`, `panchina N`, `fuori`). Parole
// proprie, mai quelle delle probabili: «titolare» e «panchina» vogliono dire la tua formazione.
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
// ---------------------------------------------------------------- pannello e foglio: apre, chiude, si trascina verso il basso
// Il foglio è modale (la pagina sotto è inerte): dal basso al telefono, di lato tra 1100 e 1199 px, e sempre per primo avvio,
// diario, stemma e maglia. Da 1200 px i dettagli dei giocatori (`opz.affianco`: scheda, sostituzione di un titolare, «Perché
// questo numero», risultati della ricerca) si aprono in un pannello accanto alla
// pagina (grafica B, spec §5 C5 e §8.11): la pagina si stringe e resta attiva, un clic su un altro giocatore cambia il pannello,
// Esc o ✕ lo chiudono e il focus torna a chi l'ha aperto. Stesso elemento (#foglio), stesso contenuto: cambia solo il modo.
let chiusura = null, focusPrima = null, chiedeAffianco = false, sfondoBloccato = false;
const PANNELLO_LARGO = matchMedia("(min-width: 1200px)");
const affiancato = () => chiedeAffianco && PANNELLO_LARGO.matches;
// Un foglio modale è aperto: i tasti dell'app (1-3, «,») non toccano la pagina sotto. Con il pannello affiancato sì.
const foglioModale = () => !$("#foglio").hidden && !document.body.classList.contains("con-pannello");
const SFONDO_FOGLIO = () => [document.querySelector(".salta"), document.querySelector(".testata"), contenuto, document.querySelector(".schede")].filter(Boolean);   // anche il link «Vai al contenuto»: il fuoco non esce dal pannello
function bloccaSfondo() {
  SFONDO_FOGLIO().forEach(e => { e.inert = true; });
  sfondoBloccato = true;
  // il focus va sulla ✕, a meno che il foglio non l'abbia già preso (la ricerca mette subito il cursore nel suo campo)
  setTimeout(() => { const c = document.querySelector(".foglio-chiudi"); if (c && !$("#foglio").hidden && !$(".foglio-corpo").contains(document.activeElement)) c.focus({ preventScroll: true }); }, 60);
}
function liberaSfondo() {
  SFONDO_FOGLIO().forEach(e => { e.inert = false; });
  sfondoBloccato = false;
}
function sbloccaSfondo() {
  liberaSfondo();
  if (focusPrima && document.body.contains(focusPrima) && focusPrima.focus) focusPrima.focus({ preventScroll: true });
  focusPrima = null;
}
// Il foglio aperto come pannello affiancato o come foglio modale: all'apertura e quando la finestra passa i 1200 px (rischio 5 della
// spec: sotto i 1200 px il pannello diventa il foglio modale, sopra torna affiancato; il focus resta dov'è, o va sulla ✕ se era fuori).
function modoFoglio() {
  const corpo = $(".foglio-corpo"), lato = affiancato();
  document.body.classList.toggle("con-pannello", lato);
  document.body.style.overflow = lato ? "" : "hidden";                   // affiancato: la pagina accanto si scorre
  if (lato) { corpo.removeAttribute("aria-modal"); liberaSfondo(); }     // finestra non modale (spec §8.11): niente aria-modal, niente inert
  else { corpo.setAttribute("aria-modal", "true"); if (!sfondoBloccato) bloccaSfondo(); }
}
// opz.affianco: da 1200 px nel pannello accanto alla pagina (sotto non cambia niente).
// opz.focusResta: il focus non va sul titolo del pannello (la ricerca della testata: si continua a scrivere nel campo).
function apriFoglio(html, opz = {}) {
  clearTimeout(chiusura);
  const foglio = $("#foglio");
  const corpo = $(".foglio-corpo");
  const eraAperto = !foglio.hidden, eraModale = eraAperto && !document.body.classList.contains("con-pannello");
  const attivo = document.activeElement;
  // chi l'ha aperto, dove torna il focus: alla prima apertura, o un clic nella pagina con il pannello affiancato già aperto (un altro
  // giocatore della lista); un clic dentro il pannello (risultato della ricerca, «Apri la scheda») non lo cambia
  if (!eraAperto || (!eraModale && attivo && attivo !== document.body && !corpo.contains(attivo))) focusPrima = attivo;
  chiedeAffianco = !!opz.affianco;
  foglio.classList.remove("chiude");
  corpo.classList.remove("trascina");
  corpo.style.transform = ""; corpo.style.transition = "";
  $("#foglio-contenuto").innerHTML = html;
  const statoRicerca = $("#stato-ricerca");                              // «12 risultati» vale per la ricerca: un contenuto nuovo la svuota
  if (statoRicerca) statoRicerca.textContent = "";
  const titoloFoglio = $("#foglio-contenuto").querySelector("h1, h2, h3");          // il pannello prende il nome dal suo primo titolo
  if (titoloFoglio && titoloFoglio.textContent.trim()) { titoloFoglio.id = "foglio-titolo"; corpo.setAttribute("aria-labelledby", "foglio-titolo"); corpo.removeAttribute("aria-label"); }
  else { corpo.removeAttribute("aria-labelledby"); corpo.setAttribute("aria-label", t("shell.dettagli")); }
  foglio.hidden = false;
  const lato = affiancato();
  if (!eraAperto || lato) corpo.scrollTop = 0;                           // un giocatore nuovo nel pannello: si legge dall'inizio
  if (!eraAperto || eraModale === lato) modoFoglio();                     // prima apertura, o da foglio modale a pannello e viceversa
  if (lato || eraModale) {
    // il titolo del contenuto prende il focus (spec §14), se il focus è ancora su chi l'ha aperto o è andato perso con il contenuto
    // di prima; non se nel frattempo si è andati altrove nella pagina. Anche nel foglio modale già aperto che cambia contenuto
    // (ricerca → scheda, Diario, #448): il pulsante premuto se ne va con il contenuto e il focus finiva sul body. Un contenuto senza
    // titolo (il caricamento) lo dà alla ✕, che resta: quando arriva il contenuto vero passa al suo titolo
    const ora = document.activeElement;
    if (!opz.focusResta && (!ora || ora === focusPrima || ora === document.body || corpo.contains(ora))) {
      const chiudi = document.querySelector(".foglio-chiudi");
      if (titoloFoglio) { titoloFoglio.tabIndex = -1; titoloFoglio.focus({ preventScroll: true }); }
      else if (!lato && chiudi) chiudi.focus({ preventScroll: true });
    }
  }
}
PANNELLO_LARGO.addEventListener("change", () => {
  if ($("#foglio").hidden || !chiedeAffianco) return;
  // la ricerca della testata non ha un campo suo e sotto i 1200 px la testata diventa inerte: riparte la ricerca del foglio, con il
  // suo campo e il testo già scritto, che lascia la testata (revisione della #426)
  if (!PANNELLO_LARGO.matches && $("#risultati-ricerca") && !$("#ricerca-veloce")) {
    const campo = $("#campo-cerca"), testo = campo.value;
    campo.value = "";
    apriRicerca(testo);
    return;
  }
  modoFoglio();
});
function chiudiFoglio() {
  const foglio = $("#foglio");
  if (foglio.hidden) return;
  const fine = () => { foglio.hidden = true; foglio.classList.remove("chiude"); document.body.style.overflow = ""; document.body.classList.remove("con-pannello"); sbloccaSfondo(); };
  foglio.classList.add("chiude");
  clearTimeout(chiusura);
  chiusura = setTimeout(fine, 240);
}
// Cambio di schermata (vai): il pannello affiancato si chiude con la pagina da cui è nato (la sostituzione di un titolare non resta
// aperta su una Formazione che non c'è più). Il focus non torna indietro: va sul titolo della schermata nuova.
function chiudiPannelloAffiancato() {
  if ($("#foglio").hidden || !document.body.classList.contains("con-pannello")) return;
  focusPrima = null;
  chiudiFoglio();
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
      setTimeout(() => { const f = $("#foglio"); f.hidden = true; document.body.style.overflow = ""; document.body.classList.remove("con-pannello"); corpo.style.transform = ""; corpo.style.transition = ""; sbloccaSfondo(); }, 230);
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
  const sost = ev.target.closest("[data-sostituisci]");                  // «Sostituisci» nella scheda di un titolare
  if (sost) apriSostituzione(Number(sost.dataset.sostituisci));
  const v = ev.target.closest("[data-vai]");
  if (v) { chiudiFoglio(); vai(v.dataset.vai); }
  const ind = ev.target.closest("[data-indietro]");                       // «‹ Squadra» della rosa, «‹ Altro» di Regole (#449)
  if (ind) { chiudiFoglio(); tornaAllaSezione(ind.dataset.indietro); }
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
  // Con il pannello affiancato (da 1200 px) la pagina resta attiva: `/`, 1-3 e «,» funzionano come a pannello chiuso.
  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const bersaglio = ev.target;
  if (bersaglio && (["INPUT", "TEXTAREA", "SELECT"].includes(bersaglio.tagName) || bersaglio.isContentEditable)) return;      // si sta scrivendo
  if (ev.key === "/") {                                                                                // tastiera: / cerca
    ev.preventDefault();
    const c = $("#campo-cerca");
    if (c && c.getClientRects().length && !foglioModale()) c.focus(); else apriRicerca();              // sul PC il campo della testata
  }
  else if (/^[1-9]$/.test(ev.key) && Number(ev.key) <= VISTE.length && !foglioModale()) vai(VISTE[Number(ev.key) - 1], undefined, { focoTitolo: true });   // tastiera: 1-4 cambiano sezione
  else if (ev.key === "," && !foglioModale()) vai("impostazioni", undefined, { focoTitolo: true });   // tastiera: , apre le impostazioni
});
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

// `o.nuova`: aperta con un clic da Squadre e rose, una voce nuova nella cronologia (#449: Indietro torna a Squadre e rose, un
// ricaricamento riapre la rosa); senza (indirizzo, Indietro, nome cambiato, stemma caricato) si corregge la voce di adesso.
async function vistaRosa(nome, o = {}) {
  const mia = nuovaRichiesta();
  stato.vista = "squadra";
  scriviIndirizzo({ vista: "squadra", gruppo: null, voce: "squadre", rosa: nome == null ? "" : String(nome), pagina: true }, !!o.nuova);
  caricamento(t("scambio.carico_rosa"));
  try {
    const r = await api("/api/rosa" + (nome ? `?squadra=${encodeURIComponent(nome)}` : ""));
    if (!ancoraValida(mia)) return;
    const senzaRuolo = r.giocatori.filter(x => !NOMI_RUOLO[x.ruolo]);
    let conIntestazione = false;                    // i nomi delle colonne una volta sola, sotto il titolo del primo ruolo; fermi scorrendo
    const gruppi = ["P", "D", "C", "A", "?"].map(ruolo => {
      const g = ruolo === "?" ? senzaRuolo : r.giocatori.filter(x => x.ruolo === ruolo);
      if (ruolo === "?" && !g.length) return "";
      const intestazione = g.length && !conIntestazione ? (conIntestazione = true, intestazioneColonne({ partita: true, ferma: true })) : "";
      // la riga di ogni giocatore come nelle altre schermate (grafica B): la partita con la lineetta del club, poi costo e quotazione
      return `<h3>${NOMI_RUOLO[ruolo] || t("scambio.senza_ruolo")} (${g.length})</h3>${intestazione}<ul class="elenco">${g.map(x => {
        const p = x.previsione, slug = slugQualunque((p && p.squadra) || x.squadra);
        const partita = pezziRiga([[[sigla(x.squadra), p ? vsAt(p) : ""].filter(Boolean).join(" "), p && p.data_partita ? quando(p.data_partita) : ""]
          .filter(Boolean).join(" · "), t("scambio.costo_quot", { c: x.costo ?? "–", q: x.quotazione ?? "–" })]);
        return `<li class="riga-gioc"><button class="voce voce-g" ${x.id ? `data-giocatore="${x.id}"` : "disabled"}>
          ${volto(p || { id: x.id, nome: x.nome, ruolo: x.ruolo, squadra: slug })}
          <span class="testo-g"><span class="nome"><span class="ruolo-l">${esc(ruoloSigla(x.ruolo || "?"))}</span><span class="nome-t">${esc(x.nome)}</span></span>
            <span class="dettaglio">${lineetta(slug)}${partita}</span>
            ${p ? `<span class="etichette">${etichetteGiocatore(p)}</span>` : ""}</span>
          ${valoreRosa(p, x)}
        </button></li>`;
      }).join("")}</ul>`;
    }).join("");
    // sul PC il menu di Squadra resta a sinistra, con «Squadre e rose» aperta: dalla rosa ad «Aggiorna le rose» con un clic (spec C10)
    pagina(`<div class="lega-colonne" data-aperto="1">${menuLega(vociLega("squadra"), "squadre", t("lega.aria_squadra"))}<div class="lega-pagina">
      <div class="carta">
        <div class="riga"><button class="bottone secondario indietro" data-indietro="squadre" style="padding:6px 14px;min-height:44px">${ICONA_INDIETRO}${t("scambio.squadra")}</button>${r.mia ? `<span class="etichetta">${t("lega.la_tua")}</span>` : ""}</div>
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
      </div></div></div>`, { titolo: r.nome });          // il titolo è il nome della squadra (pagina() lo scrive con esc); «la tua» accanto a «‹ Squadra»
    contenuto.querySelectorAll(".lega-menu [data-lega]").forEach(b => b.addEventListener("click", () => {
      const v = vociLega("squadra").find(x => x.id === b.dataset.lega);
      if (v) vaiVoceLega(v);
    }));
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
    if (ancoraValida(mia)) pagina(errore(e));
  }
}

const NOME_IMMAGINE = { stemma: "scambio.stemma", maglia: "scambio.maglia" };
const NOMI_CONTROLLI = { partite_per_giornata: t("sd.ctl_partite"), voti_per_giornata: t("sd.ctl_voti"), somma_xg: t("sd.ctl_xg"), titolari_per_squadra: t("sd.ctl_titolari"), sentinella: t("sd.ctl_sentinella") };
// righe della sentinella (fanta/sentinella.py): «sentinella_<invariante>», il nome dell'invariante con gli spazi; quelle a posto
// non si mostrano (le riassume la riga «sentinella»)
const nomeControllo = n => NOMI_CONTROLLI[n] || (n.startsWith("sentinella_") ? t("sd.ctl_sentinella_una", { nome: n.slice(11).replaceAll("_", " ") }) : n);
// Gol attesi nostri, senza Understat (I4 dal vivo, #401): i numeri calcolati solo con i voti di Fantacalcio.it contro quelli mostrati
// (campo `registro_nostri`), dopo il registro delle giornate e con le sue righe. Verdetto e soglie dal server (`regge`, `regge_tutto`),
// non si ricalcolano qui. Errore in percentuale come il registro, punti con due cifre e il segno, scarto con tre cifre, gol attesi su
// veri con due. Uguale sull'iPhone (`ParoleNostri`).
const statoNostri = n => !n.verdetto ? statoRegistro(n)
  : n.regge_tutto === true ? { testo: t("sd.nos_reggono"), colore: "var(--verde)" } : { testo: t("sd.nos_non_reggono"), colore: "var(--rosso)" };
function rigaNostri(st, nome, dettaglio) {
  return `<div class="riga"><span>${nome}</span><span class="piccolo${st.colore ? "" : " debole"}"${st.colore ? ` style="color:${st.colore}"` : ""}>${st.testo}</span></div>
      ${dettaglio ? `<div class="debole piccolo">${dettaglio}</div>` : ""}`;
}
// Una giornata: il motivo se è persa, quanti giocatori sono salvati se non è ancora misurata, altrimenti i suoi tre numeri; quelle di
// un'altra versione del calcolo non contano nel verdetto e lo dicono.
function statoGiornataNostri(g, versione) {
  if (g.persa) return { testo: esc(g.persa), colore: "var(--rosso)" };
  const altra = g.versione != null && versione != null && String(g.versione) !== String(versione) ? ` · ${t("sd.nos_g_versione", { v: esc(g.versione) })}` : "";
  const testo = !g.misurato ? tp("sd.nos_g_da_misurare", g.giocatori || 0)
    : (g.voti || 0) > 0 ? t("sd.nos_g_misurata", { e: regPerc(g.errore_pct, true), p: segno(g.punti, 2), g: num(g.gol_su_veri, 2) }) : t("sd.nos_g_vuota");
  return { testo: testo + altra, colore: "" };
}
function cartaNostri(n) {
  if (!n) return "";
  const s = n.soglie || {}, k = n.giornate || 0, v = esc(n.versione ?? "–");
  const misure = k ? rigaNostri(statoNostri(n), t("sd.nos_insieme"), "")
    + rigaNostri(statoRegistro(n, "errore"), t("sd.nos_errore"), t("sd.nos_errore_riga", { v: regPerc(n.errore_pct, true), s: regPerc(s.errore, true) }))
    + rigaNostri(statoRegistro(n, "punti"), t("sd.nos_punti"), t("sd.nos_punti_riga", { v: segno(n.punti, 2), s: regCifra(s.punti, 1, true) }))
    + rigaNostri(statoRegistro(n, "gol"), t("sd.nos_gol"), t("sd.nos_gol_riga", { v: num(n.scarto_gol, 3), s: num(s.scarto_gol, 3), g: num(n.gol_su_veri, 2), m: num(n.gol_su_veri_mostrati, 2) })) : "";
  const giornate = (n.per_giornata || []).filter(g => g);
  const righe = giornate.map(g => {
    const st = statoGiornataNostri(g, n.versione);
    return `<div class="riga"><span>${t("sd.reg_giornata", { s: esc(g.stagione), g: nomeGiornata(null, g.giornata) })}</span></div>
        <div class="piccolo${st.colore ? "" : " debole"}"${st.colore ? ` style="color:${st.colore}"` : ""}>${st.testo}</div>`;
  }).join("");
  return `<div class="carta" id="gol-attesi-nostri"><h2>${t("sd.nos_titolo")}</h2>
    <div class="debole piccolo">${t("sd.nos_spiega")}</div>
    <div class="debole piccolo" style="margin:4px 0 8px">${k ? tp("sd.nos_media", k, { v }) : t("sd.nos_nessuna")}</div>
    ${misure}
    ${righe ? `<details><summary class="debole piccolo">${t("sd.nos_per_giornata")}</summary>${righe}</details>` : ""}</div>`;
}
// Registro delle giornate (#344): le medie delle ultime giornate misurate, ognuna con la sua soglia e il verdetto del server
// (`regge`, che non si ricalcola qui), e le giornate perse con il motivo. Percentuali e punti con una cifra decimale, senza «,0»
// («−3%», «−5,7%»), come sull'iPhone (`ParoleRegistro`).
const regCifra = (x, per = 1, segnato = false) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : (segnato ? segno(x * per, 1) : num(x * per, 1)).replace(/[,.]0$/, "");
const regPerc = (x, segnato = false) => { const v = regCifra(x, 100, segnato); return v === "–" ? v : `${v}%`; };
// punti scritti come `regCifra`, al singolare quando il numero scritto è «1»: «1 punto», «2,1 punti», «– punti» (`ParoleRegistro.punti`)
const regPunti = (x, per = 1) => { const v = regCifra(x, per); return t(v === "1" ? "sd.reg_punti.one" : "sd.reg_punti.other", { n: v }); };
function statoRegistro(reg, k) {
  if (!reg.verdetto) return { testo: tp("sd.reg_servono", Math.max(1, (reg.finestra || 8) - (reg.giornate || 0))), colore: "" };
  const ok = (reg.regge || {})[k];
  if (ok === true) return { testo: t("sd.reg_regge"), colore: "var(--verde)" };
  return ok === false ? { testo: t("sd.reg_non_regge"), colore: "var(--rosso)" } : { testo: t("sd.nessun_dato"), colore: "" };
}
// Una misura (del registro o del consiglio): il nome, accanto il verdetto colorato ma sempre a parole, sotto media e soglia.
function rigaMisura(reg, k, nome, dettaglio) {
  const st = statoRegistro(reg, k);
  return `<div class="riga"><span>${t(nome)}</span><span class="piccolo${st.colore ? "" : " debole"}"${st.colore ? ` style="color:${st.colore}"` : ""}>${st.testo}</span></div>
      <div class="debole piccolo">${dettaglio}</div>`;
}
function cartaRegistro(reg) {
  if (!reg) return "";
  const s = reg.soglie || {}, n = reg.giornate || 0;
  const misura = (k, nome, dettaglio) => rigaMisura(reg, k, nome, dettaglio);
  const misure = n ? misura("I1", "sd.reg_i1", t("sd.reg_i1_riga", { v: regPerc(reg.i1, true), s: regPerc(s.I1, true), m: num(reg.errore_modello, 2), f: num(reg.errore_fantamedia, 2) }))
    + misura("I2", "sd.reg_i2", t("sd.reg_i2_riga", { c: regPunti(reg.calibrazione, 100), sc: regCifra(s.I2_calibrazione, 100), b: num(reg.brier, 3), sb: num(s.I2_brier, 3) }))
    + misura("I3", "sd.reg_i3", t("sd.reg_i3_riga", { v: regPerc(reg.copertura), min: regPerc(s.I3_minimo), max: regPerc(s.I3_massimo) })) : "";
  const perse = (reg.per_giornata || []).filter(g => g && g.persa);
  return `<div class="carta" id="registro-giornate"><h2>${t("sd.reg_titolo")}</h2>
    <div class="debole piccolo">${t("sd.reg_spiega")}</div>
    <div class="debole piccolo" style="margin:4px 0 8px">${n ? tp("sd.reg_media", n) : t("sd.reg_nessuna")}</div>
    ${misure}
    ${perse.length ? `<h3>${t("sd.reg_perse")}</h3><div class="debole piccolo">${t("sd.reg_perse_spiega")}</div>
      ${perse.map(g => `<div class="riga"><span>${t("sd.reg_giornata", { s: esc(g.stagione), g: nomeGiornata(null, g.giornata) })}</span></div>
        <div class="piccolo" style="color:var(--rosso)">${esc(g.persa)}</div>`).join("")}` : ""}</div>`;
}
// Consiglio di formazione (#366): gli indicatori del consiglio sommati sui Diari di tutti (campo `consiglio`, PR #362), resi come il
// registro: per ognuno la media delle ultime giornate, la soglia e il verdetto del server (`regge`, non si ricalcola qui). Punti con
// due cifre e il segno («+1,00», «−0,25»), totali interi, frazioni come percentuali; «–» se manca. Uguale sull'iPhone (`ParoleConsiglio`).
const consIntero = x => (typeof x === "number" && Number.isFinite(x)) ? String(x) : "–";
function cartaConsiglio(c) {
  if (!c) return "";
  const s = c.soglie || {}, n = c.giornate || 0;
  const valore = t("sd.cons_c1_riga", { v: segno(c.meno_s2, 2), s: regCifra(s.C1) })
    + (typeof c.meno_schierata === "number" ? ` · ${t("sd.cons_c1_schierata", { w: segno(c.meno_schierata, 2) })}` : "");
  const misure = n ? rigaMisura(c, "C1", "sd.cons_c1", valore)
    + rigaMisura(c, "C2", "sd.cons_c2", t("sd.cons_c2_riga", { c: regCifra(c.cambi), n: consIntero(c.cambi_sotto_soglia), s: regCifra(s.C2) }))
    + rigaMisura(c, "C3", "sd.cons_c3", t("sd.cons_c3_riga", { i: consIntero(c.improbabili), n: consIntero(c.con_compagno), s: regCifra(s.C3) }))
    + rigaMisura(c, "C4", "sd.cons_c4", t("sd.cons_c4_riga", { sp: consIntero(c.spiegate), st: consIntero(c.storte), v: regPerc(c.senza_motivo), s: regPerc(s.C4_senza_motivo) })) : "";
  return `<div class="carta" id="consiglio-formazione"><h2>${t("sd.cons_titolo")}</h2>
    <div class="debole piccolo">${t("sd.cons_spiega")}</div>
    <div class="debole piccolo" style="margin:4px 0 8px">${n ? tp("sd.cons_media", n, { f: tp("sd.cons_formazioni", c.voci || 0) }) : t("sd.cons_nessuna")}</div>
    ${misure}</div>`;
}
// Taratura di «gioca N%» con le probabili (#379, campo `calibrazione.taratura`): una frase sola sotto i gruppi della calibrazione.
// Stato, versione, numeri della prova e motivo sono quelli del server (`taratura_probabili.riepilogo`): qui si scrivono e basta,
// Brier con quattro cifre (con tre si leggeva «0,096 invece di 0,096»), scarto in punti come il registro («1 punto»). Un motivo
// che la web non conosce non si scrive (niente codici). Uguale sull'iPhone (`ParoleRegistro.taratura`).
const MOTIVI_TARATURA = { non_migliora: "sd.tar_m_non_migliora", poche_giornate: "sd.tar_m_poche_giornate", fuori_soglia: "sd.tar_m_fuori_soglia",
  incoerente: "sd.tar_m_incoerente", peggiorata: "sd.tar_m_peggiorata", scadenza_vicina: "sd.tar_m_scadenza_vicina", spenta_a_mano: "sd.tar_m_spenta_a_mano" };
// «15/1» dalla data del server («2027-01-15T10:00:00»), senza passare dal fuso orario; null se non è una data
const giornoMese = s => { const m = /^\d{4}-(\d{2})-(\d{2})/.exec(typeof s === "string" ? s : ""); return m ? `${Number(m[2])}/${Number(m[1])}` : null; };
function rigaTaratura(tar) {
  if (!tar) return "";
  const motivo = tar.motivo && Object.hasOwn(MOTIVI_TARATURA, tar.motivo) ? t(MOTIVI_TARATURA[tar.motivo], { n: Number(tar.giornate) || 0 }) : "";
  const v = esc(tar.versione ?? "–"), dal = giornoMese(tar.dal), p = tar.prova;
  let parti;
  if (tar.stato === "in_attesa") {
    const n = Number(tar.giornate) || 0, minimo = Number(tar.minimo) || 0;
    parti = [n < minimo ? tp("sd.tar_in_attesa_su", n, { m: minimo }) : tp("sd.tar_in_attesa", n)];
  } else if (tar.stato === "attiva") {
    parti = [dal ? t("sd.tar_attiva_dal", { d: dal, v }) : t("sd.tar_attiva", { v })];
    if (p) parti.push(tp("sd.tar_prova", Number(p.giornate) || 0, { b: num(p.brier, 4), p: num(p.brier_prima, 4), c: regPunti(p.calibrazione, 100) }));
    if (tar.motivo === "scadenza_vicina") parti.push(motivo);
  } else if (tar.stato === "non_attiva") {
    parti = [t("sd.tar_non_attiva"), motivo];
  } else if (tar.stato === "spenta") {
    parti = [t("sd.tar_spenta")];
  } else return "";
  return `<div class="debole piccolo" id="taratura-probabili" style="margin-top:8px">${t("sd.tar_riga", { s: parti.filter(Boolean).join(" · ") })}</div>`;
}
// Stato dei dati: da dove arriva tutto, quando è stato aggiornato, errori, foto e confronto tra probabilità previste e giocatori che hanno giocato.
async function apriStatoDati() {
  apriFoglio(`<div class="caricamento">${t("scambio.controllo_dati")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const s = await api("/api/stato-dati");
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const nomiFonte = { aggiornamento: t("sd.f_aggiornamento"), listone: t("sd.f_listone"), voti: t("sd.f_voti"), probabili: t("sd.f_probabili"),
      calendario: t("sd.f_calendario"), understat: t("sd.f_understat"), "taratura-probabili": t("sd.f_taratura") };
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
        ${s.probabili.length ? s.probabili.map(p => `<div class="riga"><span>${nomeGiornata(null, p.giornata)}</span><span class="debole piccolo">${tp("sd.n_giocatori", p.giocatori)} · ${p.rilevato ? esc(quando(p.rilevato)) : ""}</span></div>`).join("") : `<div class="debole">${t("scambio.ancora_nessuna")}</div>`}</div>
      <div class="carta"><h2>${t("scambio.controlli_sui_dati")}</h2>
        ${(s.controlli || []).length ? s.controlli.filter(k => !(k.nome.startsWith("sentinella_") && k.esito === "ok")).map(k => `<div class="riga"><span>${esc(nomeControllo(k.nome))}</span><span class="piccolo" style="color:${k.esito === "ok" ? "var(--verde)" : k.esito === "errore" ? "var(--rosso)" : "var(--arancio)"}">${t(k.esito === "ok" ? "sd.a_posto" : k.esito === "errore" ? "sd.errore" : "sd.da_guardare")}</span></div>
          ${k.esito === "ok" ? "" : `<div class="debole piccolo">${esc(k.dettaglio || "")}</div>`}`).join("") : `<div class="debole">${t("scambio.fanno_ogni_aggiornamento")}</div>`}</div>
      <div class="carta" id="affidabilita"><h2>${t("scambio.quanto_affidabile_modello")}</h2><div class="caricamento" style="padding:8px 0">${t("comune.carico")}</div></div>
      ${cartaRegistro(s.registro)}
      ${cartaNostri(s.registro_nostri)}
      ${cartaConsiglio(s.consiglio)}
      <div class="carta"><h2>${t("scambio.quanto_azzecca_modello")}</h2>
        <div class="debole piccolo">${c.giornate ? t("sd.giornate_giocate", { n: c.giornate }) : t("sd.appena_finisce")}
          ${t("sd.corregge")}</div>
        ${gruppi}
        ${rigaTaratura(c.taratura)}</div>`);
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

// Aspetto: tema (automatico, chiaro, scuro), ricordato su questo telefono. La dimensione del testo non si sceglie più qui (#615):
// vale quella del telefono e lo zoom del browser.
const ASPETTO = { tema: ["auto", "chiaro", "scuro"] };
function leggiAspetto() {
  try { return { tema: localStorage.getItem("tema") || "auto" }; } catch { return { tema: "auto" }; }
}
const pref = (k, def) => { try { return localStorage.getItem(k) || def; } catch { return def; } };
const salvaPref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* niente memoria: vale solo adesso */ } };
// Le scelte che non ci sono più (1/11/2026; la dimensione del testo dal 12/11/2026): si tolgono da questo dispositivo, così nessuno resta
// con un colore, una densità o un ingrandimento che non può più cambiare. La densità è sempre compatta; il movimento ridotto lo decide
// il sistema («Riduci movimento»).
const PREF_TOLTE = ["accento", "densita", "animazioni", "iniziale", "testo"];
function togliPrefVecchie() { try { PREF_TOLTE.forEach(k => localStorage.removeItem(k)); } catch { /* niente memoria */ } }
function applicaAspetto() {
  const a = leggiAspetto(), radice = document.documentElement;
  if (a.tema === "auto") delete radice.dataset.tema; else radice.dataset.tema = a.tema;
  // colore della barra del browser (le due righe di index.html): col tema automatico ognuna tiene il suo e sceglie il sistema
  // (attributo media); con un tema scelto a mano tutte e due prendono il fondo di quel tema
  const fondo = scuro => (scuro ? "#121513" : "#ffffff");
  document.querySelectorAll('meta[name="theme-color"]').forEach(m => { m.content = fondo(a.tema === "auto" ? m.media.includes("dark") : a.tema === "scuro"); });
  radice.dataset.densita = "compatta";
  segnaMovimento();
}
function schedaAspetto() {
  const a = leggiAspetto();
  const NOMI_TEMA = { auto: t("asp.tema_auto"), chiaro: t("asp.tema_chiaro"), scuro: t("asp.tema_scuro") };
  const lingue = `<div class="segmenti" style="margin:6px 0 14px" role="group" aria-label="${t("asp.lingua")}">${Object.keys(LINGUE).map(l =>
    `<button data-lingua="${l}" lang="${l}" class="${LINGUA === l ? "attivo" : ""}">${t("lingua." + l)}</button>`).join("")}</div>`;
  const seg = (chiave, valore, opzioni) => `<div class="segmenti" style="margin:6px 0 14px">${opzioni.map(([v, n]) =>
    `<button data-pref="${chiave}" data-valore="${v}" class="${String(valore) === String(v) ? "attivo" : ""}">${n}</button>`).join("")}</div>`;
  // Lingua e tema. Niente colori, densità, dimensione del testo o icone diverse.
  return `<div id="aspetto"><div class="carta"><h3>${t("asp.lingua")}</h3>${lingue}</div>
  <div class="carta"><h3>${t("asp.tema")}</h3>${seg("tema", a.tema, ASPETTO.tema.map(k => [k, NOMI_TEMA[k]]))}
    <div class="debole piccolo">${t("asp.auto_spiega")}</div></div></div>`;
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

// Ricerca veloce di un giocatore da qualsiasi schermata (la lente in alto, il tasto «/», il campo della testata sul PC).
// Da 1200 px si scrive nel campo della testata e i risultati stanno nel pannello accanto alla pagina (spec C4 e C5): il pannello non ha
// un campo suo e il cursore resta nella testata. Più stretto, il foglio con il suo campo, che prende subito il focus: le lettere che
// arrivano mentre il foglio sale finiscono lì (il resto della pagina è bloccato). `testo`: quello già scritto nel campo della testata.
function apriRicerca(testo = "") {
  if (ricercaInTestata()) {
    const f = $("#foglio");
    if (!$("#risultati-ricerca") || $("#ricerca-veloce") || f.hidden || f.classList.contains("chiude"))
      apriFoglio(`<h2 style="margin:0 0 10px;font-size:var(--t-card)">${t("shell.cerca")}</h2>
        <div class="risultati-ricerca" id="risultati-ricerca"></div>`, { affianco: true, focusResta: true });
    scriviRisultati(testo);
    return;
  }
  apriFoglio(`<h2 style="margin:0 0 10px;font-size:var(--t-card)">${t("shell.cerca")}</h2>
    <input class="campo-testo" id="ricerca-veloce" type="search" placeholder="${t("avv.nome_del_giocatore")}" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search">
    <div class="risultati-ricerca" id="risultati-ricerca"><div class="debole piccolo">${t("avv.scrivi_almeno_due")}</div></div>`, { affianco: true });
  const campo = $("#ricerca-veloce");
  campo.value = testo;
  campo.focus({ preventScroll: true });
  setTimeout(() => caricaListoneCerca().catch(() => {}), 350);
  campo.addEventListener("input", () => scriviRisultati(campo.value));
  campo.addEventListener("keydown", ev => {                             // Invio: il primo risultato; ↓ i risultati
    frecceRicerca(ev);
    if (ev.key !== "Enter" || ev.isComposing) return;
    ev.preventDefault();
    if (!ev.repeat) apriPrimoRisultato(campo);
  });
  if (testo.trim()) scriviRisultati(testo);                            // dalla testata: cerca subito quello che è già scritto
}
// I risultati (al massimo 12) nel posto della ricerca aperta; vale solo l'ultima ricerca partita. Nomi e squadre passano da esc().
// Quanti sono lo dice la riga `role="status"` del foglio (#stato-ricerca, fissa in index.html: un annuncio si sente solo se la riga
// c'era già), per chi usa un lettore di schermo: i risultati arrivano mentre si scrive, in un posto dove il cursore non c'è.
let giroRicerca = 0;
async function scriviRisultati(testo) {
  const q = String(testo).trim(), mio = ++giroRicerca, dove = $("#risultati-ricerca"), conta = $("#stato-ricerca");
  const annuncia = frase => { if (conta && conta.textContent !== frase) conta.textContent = frase; };
  if (!dove) return;
  if (q.length < 2) { dove.innerHTML = `<div class="debole piccolo">${t("avv.scrivi_almeno_due")}</div>`; annuncia(""); return; }
  try {
    const r = await cercaGiocatori(q, 12), qui = $("#risultati-ricerca");
    if (mio !== giroRicerca || !qui) return;
    qui.innerHTML = r.length ? `<ul class="elenco">${r.map(x => `<li><button class="voce" data-giocatore="${x.id}" style="grid-template-columns:1fr auto">
      <span><span class="nome">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</span><span class="dettaglio" style="display:block">${esc(x.squadra)}</span></span>
      <span class="debole piccolo">${t("avv.quot", { n: x.quotazione })}</span></button></li>`).join("")}</ul>` : `<div class="debole">${t("avv.nessun_giocatore_trovato")}</div>`;
    annuncia(r.length ? tp("avv.n_risultati", r.length) : t("avv.nessun_giocatore_trovato"));
  } catch (e) { if (e.name !== "AbortError" && mio === giroRicerca && $("#risultati-ricerca")) { $("#risultati-ricerca").innerHTML = errore(e); annuncia(""); } }
}
// Frecce nella ricerca (revisione della #426): i risultati stanno nel pannello, dopo la pagina, e con il solo Tab non si arrivava.
// ↓ nel campo porta al primo risultato, ↓ e ↑ passano dall'uno all'altro, ↑ sul primo torna al campo (quello della testata o del
// foglio). Senza risultati, a foglio chiuso o oltre l'ultimo le frecce fanno quello di sempre.
function frecceRicerca(ev) {
  if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
  const elenco = [...document.querySelectorAll("#risultati-ricerca [data-giocatore]")];
  if (!elenco.length || $("#foglio").hidden) return;
  const campo = $("#ricerca-veloce") || $("#campo-cerca"), k = elenco.indexOf(ev.target);
  let dove = null;
  if (ev.target === campo) dove = ev.key === "ArrowDown" ? elenco[0] : null;
  else if (k >= 0) dove = ev.key === "ArrowDown" ? elenco[k + 1] || null : k === 0 ? campo : elenco[k - 1];
  if (!dove) return;
  ev.preventDefault();
  dove.focus();
}
$("#foglio-contenuto").addEventListener("keydown", ev => { if (ev.target.closest("#risultati-ricerca")) frecceRicerca(ev); });
// Campo della testata svuotato: il pannello si chiude se mostra la ricerca (non una scheda aperta da lì).
function chiudiRicercaAffiancata() {
  if (!$("#foglio").hidden && $("#risultati-ricerca") && !$("#ricerca-veloce")) chiudiFoglio();
}
$("#bottone-cerca").addEventListener("click", () => apriRicerca());
// Il campo sempre aperto della testata (da 900 px). Da 1200 px il testo resta qui e i risultati si scrivono nel pannello accanto
// mentre si scrive, 150 ms dopo l'ultimo tasto (una ricerca sola anche scrivendo veloce); Invio apre il primo risultato; campo
// svuotato: il pannello della ricerca si chiude. Tra 900 e 1199 px al primo tasto il testo passa al foglio della ricerca, come prima.
const ricercaInTestata = () => PANNELLO_LARGO.matches && $("#campo-cerca").getClientRects().length > 0;
let attesaRicerca = null;
// Invio: si apre il primo risultato, nello stesso pannello; senza risultati, nella testata si vedono quelli («Nessun giocatore trovato»).
// Campo vuoto o una lettera sola: niente da aprire, il pannello della ricerca si chiude (revisione della #426).
async function apriPrimoRisultato(campo) {
  const q = campo.value;
  if (q.trim().length < 2) { if (campo === $("#campo-cerca")) chiudiRicercaAffiancata(); return; }
  let primo = null;
  try { primo = (await cercaGiocatori(q.trim(), 12))[0] || null; } catch { /* rete: restano i risultati con l'errore */ }
  if (campo.value !== q) return;                                      // nel frattempo si è scritto altro: vale l'ultima ricerca
  if (primo) apriGiocatore(primo.id);
  else if (campo === $("#campo-cerca")) apriRicerca(q);
}
$("#campo-cerca").placeholder = t("shell.cerca");
$("#campo-cerca").addEventListener("focus", () => { if (ricercaInTestata()) caricaListoneCerca().catch(() => {}); });   // l'elenco arriva prima del primo tasto
$("#campo-cerca").addEventListener("input", ev => {
  if (ricercaInTestata()) {
    clearTimeout(attesaRicerca);
    attesaRicerca = setTimeout(() => { const q = $("#campo-cerca").value; if (q.trim()) apriRicerca(q); else chiudiRicercaAffiancata(); }, 150);
    return;
  }
  const q = ev.target.value;
  if (!q.trim()) return;
  ev.target.value = "";
  apriRicerca(q);
});
$("#campo-cerca").addEventListener("keydown", ev => {
  frecceRicerca(ev);                                                  // ↓ porta ai risultati nel pannello
  if (ev.key !== "Enter" || ev.isComposing) return;
  ev.preventDefault();
  if (!ricercaInTestata()) { const q = ev.target.value; ev.target.value = ""; apriRicerca(q); return; }
  clearTimeout(attesaRicerca);
  if (!ev.repeat) return apriPrimoRisultato(ev.target);
});

// Numeri con la virgola in italiano, con il punto nelle altre lingue.
const virgola = x => (LINGUA === "it" ? String(x).replace(".", ",") : String(x));
// Giornate > «Dettagli» della riga sulla precisione (campo `precisione` di /api/diario, fanta/precisione.py): i numeri con una frase,
// l'andamento giornata per giornata e l'avviso se i dati sono pochi. Tutto viene dal server; si mostra anche quando va male.
// Numeri dal server (passati da Number) e, per la riga su tutta la Serie A, una frase del server passata da esc(); niente innerHTML.
// `conConfronto`: la voce «consigliata contro la tua» si mostra solo se c'è almeno una giornata con la consigliata mostrata prima
// della scadenza (#614): con il server di prima il confronto era con una formazione rifatta dopo, e non si mostra. Il server con #614
// dice anche quante giornate con la tua formazione restano fuori dal confronto (`confronto.senza_istantanea`): lo si scrive in fondo.
function dettagliPrecisione(p, conConfronto) {
  if (!p || !p.giornate) return "";
  const n = x => (x == null || !isFinite(Number(x)) ? null : Number(x));
  const v = x => (n(x) == null ? "–" : virgola(n(x).toFixed(1)));
  const suDieci = pct => Math.round((n(pct) || 0) / 10);
  const pg = p.per_giornata || [];
  const nomeG = g => nomeGiornata(g.giornata_lega, g.giornata);
  // sotto le barre lo spazio è poco: il numero della lega da solo; per una stagione passata «G11» di Serie A (forma stretta)
  const sottoBarra = g => (n(g.giornata_lega) != null ? n(g.giornata_lega) : `G${n(g.giornata)}`);
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
    : "";
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
        <text x="${(x + larga / 2).toFixed(1)}" y="${H - 3}" text-anchor="middle" class="qp-g">${sottoBarra(g)}</text>`;
    }).join("");
    grafico = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${t("diario.qp_grafico_aria")}" class="qp-grafico">${barre}</svg>
      <div class="debole piccolo">${t("diario.qp_grafico_leg")}</div>`;
  }
  // giornata per giornata solo l'errore e i punti della consigliata: quanto ha fatto la tua lo dice la riga di ogni giornata
  const righe = [...pg].reverse().map(g => `<li><b>${nomeG(g)}</b> · <span class="debole">${n(g.errore_fantavoto) != null ? t("diario.qp_riga_fv", { e: v(g.errore_fantavoto) }) + " · " : ""}${t("diario.qp_riga_sq", { a: v(g.attesi), f: v(g.fatti) })}</span></li>`).join("");
  const primo = pg.length ? nomeG(pg[0]) : null, ultimo = pg.length ? nomeG(pg[pg.length - 1]) : null;
  const ric = n((p.fonti || {}).ricostruiti) || 0;
  // la riga su tutta la Serie A (registro delle giornate, #374): frase del server, la stessa che mostra l'iPhone
  const sa = p.serie_a && typeof p.serie_a.testo === "string" && p.serie_a.testo.trim() ? testoDi(p.serie_a) : "";
  const serieA = sa ? `<div class="qp-frase qp-serie-a">${esc(sa)}</div>` : "";
  return `<div class="qp">
    <div class="debole piccolo">${t("diario.qp_intro")} ${elidiOrdinali(tp("diario.qp_su", n(p.giornate), { da: primo, a: ultimo }))}</div>
    ${p.pochi_dati ? `<div class="attenzione qp-pochi">${t("diario.qp_pochi", { n: n(p.giornate_minime) || 8 })}</div>` : ""}
    <div class="qp-griglia">
      ${voce(fv ? v(fv.errore_medio) : "–", t("diario.qp_fv_eti"), fvFrase)}
      ${voce(gp ? t("diario.qp_su_dieci", { k: suDieci(gp.giocato) }) : "–", t("diario.qp_gioca_eti"), gFrase, gp && n(gp.giocato) < n(gp.detto) - 10 ? "attenzione-testo" : "")}
      ${conConfronto && cf.giornate ? voce(t("diario.qp_k_su_n", { k: n(cf.meglio_consigliata), n: n(cf.giornate) }), t("diario.qp_cf_eti"), cfFrase) : ""}
      ${voce(sq ? v(sq.scarto_medio) : "–", t("diario.qp_sq_eti"), sqFrase)}
    </div>
    ${serieA}
    ${grafico}
    ${righe ? `<details class="qp-dettagli"><summary>${t("diario.qp_andamento")}</summary><ul class="qp-giornate">${righe}</ul></details>` : ""}
    ${ric ? `<div class="debole piccolo qp-nota">${tp("diario.qp_ricostruiti", ric, { t: n(p.giornate) })}</div>` : ""}
    ${n(cf.senza_istantanea) ? `<div class="debole piccolo qp-nota">${tp("giornate.fuori_confronto", n(cf.senza_istantanea))}</div>` : ""}</div>`;
}

// ---------------------------------------------------------------- Giornate (#617): il Diario come pagina della barra
// Una riga per giornata finita, dalla più recente: i punti fatti e attesi della formazione che conta e, al tocco, gli 11 con il fantavoto
// atteso e quello preso. Il confronto «tu contro la consigliata» c'è solo dove la consigliata è quella mostrata prima della scadenza
// (`consigliata.origine === "mostrata"`, #614): il server di prima non manda `origine`, la sua consigliata è sempre rifatta a giornata
// finita, e lì il confronto non si mostra. Numeri, nomi e frasi vengono da /api/diario: la pagina sceglie cosa mostrare, non calcola.
// Al telefono gli 11 si aprono sotto la riga (anche più giornate insieme); da 768 px l'elenco sta a sinistra e la giornata scelta a
// destra, una alla volta, con la più recente già aperta.
const GIORNATE_LARGHE = matchMedia("(min-width: 768px)");
// Una giornata è stagione + numero: con due stagioni la giornata 10 c'è due volte (#176). Nell'id solo cifre e trattini.
const idGiornata = g => `${String(g.stagione ?? "").replace(/[^0-9-]/g, "")}-g${Number(g.giornata)}`;
// `dati`: l'ultima risposta in pagina; `aperte`: gli id delle giornate aperte; `chiesta`: il numero della giornata da aprire
// («Com'è andata» della Formazione, una voce di «Da fare»), che vale finché non arriva una risposta che la contiene.
const giornate = { dati: null, aperte: new Set(), chiesta: null };
// La formazione che conta per la giornata, come nel riepilogo della Formazione: la tua, la consigliata salvata da sola alla scadenza
// se non avevi scelto, oppure la consigliata.
const formazioneDi = g => (g.schierata ? { tipo: "tua", f: g.schierata } : g.automatica ? { tipo: "automatica", f: g.automatica } : { tipo: "consigliata", f: g.consigliata });
const conMostrata = g => !!g.consigliata && g.consigliata.origine === "mostrata";
// La voce di `scelte_tue.per_giornata` (giornate con 11 diversi dai consigliati): nomi e differenza di punti li calcola il server.
const sceltaDi = (d, g) => (((d.scelte_tue || {}).per_giornata) || []).find(x => x && x.stagione === g.stagione && Number(x.giornata) === Number(g.giornata)) || null;
const voceGiornata = id => ((giornate.dati || {}).giornate || []).find(g => idGiornata(g) === id) || null;

function vaiGiornate(giornata) {
  giornate.chiesta = giornata == null || !Number(giornata) ? null : Number(giornata);
  vai("giornate", undefined, { focoTitolo: true });
}
function vistaGiornate() {
  if (giornate.chiesta == null) giornate.aperte.clear();              // si riparte con le righe chiuse (da 768 px: la più recente)
  caricaConCache("giornate", "/api/diario", mostraGiornate, t("giornate.carico"));
}

// Sotto la riga: hai schierato la consigliata, o quanti cambi tuoi e quanto sono valsi (solo con la consigliata mostrata); altrimenti
// di chi sono i punti.
function statoGiornata(d, g) {
  const { tipo } = formazioneDi(g);
  if (tipo === "tua" && conMostrata(g)) {
    const s = sceltaDi(d, g);
    if (!s) return t("giornate.hai_consigliata");
    const n = Array.isArray(s.hai_scelto) ? s.hai_scelto.length : 0, diff = Number(s.differenza);
    if (n && isFinite(diff)) return diff === 0 ? tp("giornate.cambi_pari", n) : tp("giornate.cambi", n, { d: segno(diff) });
  }
  return t(tipo === "tua" ? "giornate.tua" : tipo === "automatica" ? "giornate.automatica" : "giornate.non_salvata");
}

// Gli 11 della giornata con il fantavoto atteso e quello preso, cosa hai cambiato rispetto alla consigliata e la correzione.
// L'atteso è quello mostrato prima della scadenza, se c'è (`istantanea`, titolari e panchina); se no quello rifatto con i soli dati di
// prima (`giocatori`). Preso: `giocatori[].fv`, «senza voto» se non l'ha preso. Nomi dal server, passati da esc().
function dettaglioGiornata(d, g, stagioni) {
  const id = idGiornata(g), { tipo, f } = formazioneDi(g), mostrata = conMostrata(g), origine = (g.consigliata || {}).origine;
  const nome = nomeGiornata(g.giornata_lega, g.giornata) + (stagioni ? ` · ${esc(g.stagione)}` : "");
  const modulo = esc(f.modulo || "");
  const titolo = tipo === "tua" ? t("giornate.formazione_tua", { modulo }) : tipo === "automatica" ? t("giornate.formazione_automatica", { modulo })
    : t(mostrata ? "giornate.formazione_consigliata" : "giornate.formazione_rifatta", { modulo });
  const ist = g.istantanea || {};
  const mostrati = new Map([...(ist.titolari || []), ...(ist.panchina || [])].filter(x => x && x.fv_atteso != null).map(x => [x.id, x.fv_atteso]));
  const numeri = new Map((Array.isArray(g.giocatori) ? g.giocatori : []).map(x => [x.id, x]));
  const righe = (f.titolari || []).map(x => {
    const n = numeri.get(x.id), atteso = mostrati.has(x.id) ? mostrati.get(x.id) : n ? n.fv_atteso : null;
    const senza = !!n && n.fv == null;
    return `<tr><th scope="row">${badgeRuolo(x.ruolo, true)}${esc(x.nome)}</th><td>${num(atteso)}</td><td${senza ? ' class="gn-senza"' : ""}>${senza ? t("giornate.senza_voto") : num(n ? n.fv : null)}</td></tr>`;
  }).join("");
  const s = tipo === "tua" && mostrata ? sceltaDi(d, g) : null;
  const cambi = s && Array.isArray(s.hai_scelto) && s.hai_scelto.length
    ? `<p class="gn-cambi">${t("giornate.al_posto", { dentro: esc(s.hai_scelto.join(", ")), fuori: esc((s.consigliava || []).join(", ")) })}</p>`
    : tipo === "tua" && origine === "ricostruita" ? `<p class="gn-nota">${t("giornate.senza_confronto")}</p>` : "";
  const nota = tipo === "consigliata" && origine === "ricostruita" ? `<p class="gn-nota">${t("giornate.rifatta_nota")}</p>` : "";
  const correggi = g.modificabile === false ? "" : `<div class="pulsanti"><button class="bottone secondario" type="button" data-correggi="${id}">${t("giornate.correggi")}</button></div>`;
  return `<section class="gn-dettaglio" id="gn-d-${id}" aria-label="${nome}">
    <h2 class="gn-titolo">${titolo}</h2>${nota}
    <table class="gn-tabella"><caption class="solo-lettori">${t("giornate.tabella")}</caption>
      <thead><tr><th scope="col">${t("giornate.col_giocatore")}</th><th scope="col">${t("giornate.col_atteso")}</th><th scope="col">${t("giornate.col_preso")}</th></tr></thead>
      <tbody>${righe}</tbody></table>
    ${cambi}${correggi}</section>`;
}

// In cima una riga sola sulla precisione (`precisione.fantavoto.errore_medio`) con i dettagli a richiesta; poi una riga per giornata.
function mostraGiornate(d, opz = {}) {
  const voci = Array.isArray(d.giornate) ? d.giornate : [];
  giornate.dati = d;
  if (giornate.chiesta != null) {
    const g = voci.find(x => Number(x.giornata) === giornate.chiesta);      // dalla più recente: la stagione in corso
    if (g) giornate.aperte = new Set([idGiornata(g)]);
    if (g || !opz.daCache) giornate.chiesta = null;                         // la copia del telefono può non averla ancora
  }
  const largo = GIORNATE_LARGHE.matches, ids = voci.map(idGiornata);
  if (largo) { const scelta = ids.find(i => giornate.aperte.has(i)) || ids[0]; giornate.aperte = new Set(scelta ? [scelta] : []); }
  const stagioni = new Set(voci.map(g => g.stagione)).size > 1;
  const p = d.precisione || {}, fv = p.fantavoto;
  const errore = fv && fv.errore_medio != null && isFinite(Number(fv.errore_medio)) ? num(Number(fv.errore_medio)) : null;
  const dettagli = dettagliPrecisione(p, voci.some(conMostrata));
  const testa = errore || dettagli ? `<div class="gn-testa">${errore ? `<p class="gn-precisione">${t("giornate.precisione", { e: errore })}</p>` : ""}
    ${dettagli ? `<details class="gn-dettagli"><summary>${errore ? t("giornate.dettagli") : t("diario.af_titolo")}</summary>${dettagli}</details>` : ""}</div>` : "";
  const riga = g => {
    const id = idGiornata(g), aperta = giornate.aperte.has(id), { f } = formazioneDi(g);
    return `<li class="gn-voce"><button class="gn-riga" type="button" id="gn-r-${id}" data-giornata="${id}" aria-expanded="${aperta}"${aperta ? ` aria-controls="gn-d-${id}"` : ""}>
        <span class="gn-sx"><span class="gn-nome">${nomeGiornata(g.giornata_lega, g.giornata)}${stagioni ? ` <span class="gn-stagione">${esc(g.stagione)}</span>` : ""}</span>
          <span class="gn-stato">${statoGiornata(d, g)}</span></span>
        <span class="gn-dx"><b class="gn-num">${num(f.reale)}</b> <span class="gn-attesi">${f.atteso != null ? t("formazione.punti_e_attesi", { n: num(f.atteso) }) : t("formazione.punti")}</span></span>
      </button>${!largo && aperta ? dettaglioGiornata(d, g, stagioni) : ""}</li>`;
  };
  const vuoto = { squadra: t("giornate.vuoto_squadra"), giornate: t("giornate.vuoto_giornate"), calcolo: t("giornate.vuoto_calcolo") }[d.motivo_vuoto] || t("giornate.vuoto");
  const lato = largo ? `<div class="gn-lato">${voci.filter(g => giornate.aperte.has(idGiornata(g))).map(g => dettaglioGiornata(d, g, stagioni)).join("")}</div>` : "";
  // ridisegno della stessa pagina (dati nuovi dopo la copia del telefono, finestra più larga, correzione): «Dettagli» resta aperto
  const fuoco = document.activeElement && document.activeElement.closest && document.activeElement.closest(".gn-riga");
  const dettagliAperti = !!opz.sostituisce && !!($(".gn-dettagli", contenuto) || {}).open;
  pagina(voci.length ? `<div class="gn">${testa}<ul class="gn-elenco" aria-label="${t("giornate.elenco")}">${voci.map(riga).join("")}</ul>${lato}</div>`
    : `${testa}<p class="debole gn-vuoto">${vuoto}</p>`, opz);
  if (dettagliAperti) { const x = $(".gn-dettagli", contenuto); if (x) x.open = true; }
  const radice = $(".gn", contenuto);
  if (radice) radice.addEventListener("click", ev => {
    const r = ev.target.closest(".gn-riga");
    if (r) { apriChiudiGiornata(r.dataset.giornata); return; }
    const c = ev.target.closest("[data-correggi]"), g = c && voceGiornata(c.dataset.correggi);
    if (g) correggiGiornata(g);
  });
  if (fuoco) { const b = document.getElementById(fuoco.id); if (b) b.focus({ preventScroll: true }); }   // ridisegno (dati nuovi, finestra più larga)
}

// Un tocco su una riga: al telefono apre o chiude i suoi 11 sotto di lei; da 768 px la sceglie e i suoi 11 vanno a destra. La riga resta
// com'è (il focus non si perde): cambiano aria-expanded e il dettaglio.
function apriChiudiGiornata(id) {
  const d = giornate.dati, g = voceGiornata(id), b = document.getElementById(`gn-r-${id}`);
  if (!d || !g || !b) return;
  const stagioni = new Set(d.giornate.map(x => x.stagione)).size > 1;
  const segna = (riga, aperta) => {
    riga.setAttribute("aria-expanded", String(aperta));
    if (aperta) riga.setAttribute("aria-controls", `gn-d-${riga.dataset.giornata}`); else riga.removeAttribute("aria-controls");
  };
  if (GIORNATE_LARGHE.matches) {
    giornate.aperte = new Set([id]);
    contenuto.querySelectorAll(".gn-riga").forEach(r => segna(r, r.dataset.giornata === id));
    const lato = $(".gn-lato", contenuto);
    if (lato) lato.innerHTML = dettaglioGiornata(d, g, stagioni);
    return;
  }
  const aperta = !giornate.aperte.has(id);
  if (aperta) { giornate.aperte.add(id); b.insertAdjacentHTML("afterend", dettaglioGiornata(d, g, stagioni)); }
  else { giornate.aperte.delete(id); const z = document.getElementById(`gn-d-${id}`); if (z) z.remove(); }
  segna(b, aperta);
}
// La finestra passa i 768 px: la pagina si ridisegna con l'altra disposizione (la giornata aperta resta aperta).
GIORNATE_LARGHE.addEventListener("change", () => { if (stato.vista === "giornate" && giornate.dati && $(".gn", contenuto)) mostraGiornate(giornate.dati, { sostituisce: true }); });

// «Non è quello che ho schierato»: scegli a mano gli 11 che hai schierato in una giornata finita. Si parte dagli 11 della riga; il
// server controlla che siano 11 della tua rosa con un modulo valido. La correzione porta sempre la stagione della giornata (il server
// rifiuta quelle passate, senza scrivere sulla giornata di quest'anno).
const corpoSchierata = (g, tipo, titolari) => JSON.stringify({ giornata: Number(g.giornata), tipo, ...(titolari ? { titolari } : {}), stagione: g.stagione });
async function correggiGiornata(g) {
  apriFoglio(`<div class="caricamento">${t("scambio.carico_rosa")}</div>`);
  const numero = ++ultimaScheda;
  try {
    const r = await api("/api/rosa");
    if (numero !== ultimaScheda || $("#foglio").hidden) return;
    const iniziali = new Set((formazioneDi(g).f.titolari || []).map(p => p.id));
    const gruppi = ["P", "D", "C", "A"].map(ruolo => {
      const giocatori = r.giocatori.filter(x => x.ruolo === ruolo && x.id);
      return giocatori.length ? `<h3>${NOMI_RUOLO[ruolo]}</h3>${giocatori.map(x => `<label class="interruttore"><span>${badgeRuolo(x.ruolo, true)}${esc(x.nome)} <span class="debole piccolo">${sigla(x.squadra)}</span></span>
        <input type="checkbox" data-scelto="${Number(x.id)}" ${iniziali.has(x.id) ? "checked" : ""}></label>`).join("")}` : "";
    }).join("");
    apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("diario.cosa_hai_schierato_titolo")}</h2>
      <div class="debole piccolo">${t("diario.correggi_spiega", { g: nomeGiornata(g.giornata_lega, g.giornata) })}</div>
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
    $("#diario-annulla").addEventListener("click", () => chiudiFoglio());          // il focus torna al pulsante della correzione
    $("#diario-salva").addEventListener("click", async () => {
      const titolari = caselle().filter(c => c.checked).map(c => Number(c.dataset.scelto));
      if (titolari.length !== 11) return;
      $("#diario-salva").disabled = true;
      try { await api("/api/diario/schierata", { method: "POST", body: corpoSchierata(g, "manuale", titolari) }); }
      catch (e) { $("#diario-salva").disabled = false; avviso(e.message, 6000); return; }
      await rileggiGiornate(g);
      chiudiFoglio();
      avviso(t("diario.salvata_manuale"));
    });
  } catch (e) { if (numero === ultimaScheda && !$("#foglio").hidden) apriFoglio(errore(e)); }
}
// Dopo una correzione la pagina rilegge le giornate, con quella corretta aperta; chiuso il foglio, il focus va sulla sua riga.
async function rileggiGiornate(g) {
  const id = idGiornata(g);
  giornate.aperte = new Set([id]);
  giornate.chiesta = null;
  if (stato.vista !== "giornate") return;
  try {
    const d = await api("/api/diario");
    salvaCache("giornate", d);
    if (stato.vista === "giornate") mostraGiornate(d, { sostituisce: true });
  } catch { if (stato.vista === "giornate") vistaGiornate(); }              // come all'apertura: l'errore con «Riprova»
  const riga = document.getElementById(`gn-r-${id}`);
  if (riga) focusPrima = riga;
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
        <div class="debole piccolo"><b style="color:var(--verde)">—</b> ${t("avv.modello_nbsp")} <b style="color:var(--arancio)">—</b> ${t("avv.fantamedia_nbsp")} <b>- -</b> ${t("avv.max_possibile")} · ${elidiOrdinali(t("avv.giornate_da_a", { a: Number(righe[0].giornata), b: Number(righe[righe.length - 1].giornata) }))}</div>`;
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
  finally { dove.removeAttribute("aria-busy"); }                           // ha finito di caricare, bene o male
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

// Squadra e Altro: un menu di voci con la pagina accanto (stesso componente delle Impostazioni). `ambito` dice in quale scheda sta la
// voce; `vai` è una voce che porta a un'altra pagina invece di aprirsi accanto al menu.
// Restano tre voci. Dal 12/11/2026 (#615) Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario, Scambi, Movimenti, Crediti
// e Novità non ci sono più (le Novità si leggono in Impostazioni > Informazioni); «Nuova stagione» compare da sola quando serve.
// Il Diario è la pagina Giornate, nella barra (#617).
// `vai(o)`: `o.nuova` = clic nel menu (Regole scrive una voce nuova nella cronologia, #449); `o.sostituisci` = la voce è stata
// chiesta da un indirizzo o da un collegamento e la pagina prende il posto della voce di adesso (niente voce che riporta qui).
const VOCI_LEGA = [
  { id: "squadre", ambito: "squadra", nome: t("lega.voce_squadre"), sub: t("lega.voce_squadre_sub") },
  { id: "importa", ambito: "squadra", nome: t("lega.voce_importa"), sub: t("lega.voce_importa_sub") },
  { id: "regole", ambito: "altro", nome: t("lega.voce_regole"), sub: t("lega.voce_regole_sub"), vai: o => vistaRegole(o) },
];
const NOME_AMBITO = { squadra: t("nav.squadra"), altro: t("nav.altro") };
// Apre Squadra o Altro già su una voce (anche tornando da una pagina come la rosa di una squadra o le regole). `opz` come in vai().
function vaiLega(voce, opz) { stato.legaTorna = voce; vai("lega", undefined, opz); }

// Squadra e Altro sugli schermi larghi (spec grafica B §5 C10): da 1100 px il menu delle voci resta a sinistra e la voce scelta si apre
// a destra: da una all'altra con un clic, senza tornare al menu. Sotto i 1100 px una cosa alla volta: il menu, oppure la pagina con
// «‹ Squadra».
const LEGA_LARGA = matchMedia("(min-width: 1100px)");
const legaLarga = () => LEGA_LARGA.matches;
// Le voci di una scheda, nell'ordine di VOCI_LEGA. Senza le rose degli altri «La mia squadra».
function vociLega(ambito) {
  return VOCI_LEGA.filter(v => v.ambito === ambito)
    .map(v => v.id === "squadre" && !funz("squadre_altrui") ? { ...v, nome: t("lega.voce_miasquadra"), sub: t("lega.voce_miasquadra_sub") } : v);
}
// Una voce si apre accanto al menu se non porta altrove (`vai`): le Regole sono una pagina loro.
const nellaPagina = v => !v.vai;
// Da una pagina con il menu che non è la pagina della scheda (la rosa di una squadra): una voce porta alla sua pagina.
const vaiVoceLega = v => (v.vai ? v.vai({ nuova: true }) : vaiLega(v.id));
// Il menu delle voci: la voce aperta ha aria-current="page" (il lettore di schermo la dice; a vista il fondo e la linea a sinistra).
// Nomi e sottotitoli vengono da testi.js, non dall'utente.
function menuLega(voci, aperta, aria) {
  return `<nav class="lega-menu" aria-label="${aria}"><ul class="elenco">${voci.map(v => `<li><button class="voce lega-voce" type="button" data-lega="${v.id}"${v.id === aperta ? ' aria-current="page"' : ""}>
    <span><span class="nome">${v.nome}</span><span class="dettaglio">${v.sub}</span></span><span class="debole" aria-hidden="true">›</span></button></li>`).join("")}</ul></nav>`;
}
// L'indirizzo della voce aperta (spec C2): ?vista=squadra&voce=… o ?vista=altro&voce=… (#449: prima l'indirizzo non diceva la voce e sotto i 1100 px Indietro usciva dalla sezione). Così Indietro
// torna alla voce di prima (o al menu) e un ricaricamento riapre questa. `nuova` (un clic): una voce nuova nella cronologia; senza
// (prima apertura) si corregge quella di adesso (scriviIndirizzo). La voce aperta (`id`) sta anche nello stato della cronologia.
function indirizzoLega(vista, nuova, id) {
  stato.vista = vista;
  scriviIndirizzo({ vista, gruppo: null, voce: id }, nuova);
}
// Finestra allargata oltre i 1100 px con il solo menu in pagina: a destra si apre la voce dell'ultima volta (o la prima), invece di
// lasciare una colonna vuota. La prepara vistaLega a ogni disegno.
let legaQuandoLarga = null;
// Il focus non si perde quando la finestra passa i 1100 px: stringendo sparisce il menu (con la voce che aveva il focus), allargando
// sparisce «‹ Squadra». Il focus va sul titolo della voce aperta (o della pagina, nella rosa) stringendo, sulla voce aperta del menu
// allargando. Se il browser l'ha già tolto all'elemento nascosto (focus sul body) vale l'ultimo elemento di Squadra o Altro che l'aveva.
let focusLega = null;
document.addEventListener("focusin", ev => { focusLega = ev.target && ev.target.closest && ev.target.closest(".lega-colonne") ? ev.target : null; });
function focusLegaVisibile() {
  const ora = document.activeElement, prima = ora && ora !== document.body ? ora : focusLega;
  const radice = prima && prima.isConnected && prima.closest(".lega-colonne");
  if (!radice || prima.getClientRects().length) return;                  // non è di Squadra o Altro, oppure si vede ancora
  const dove = LEGA_LARGA.matches ? radice.querySelector('.lega-menu [aria-current="page"]') : $("#lega-titolo", radice) || $("#titolo-pagina");
  if (dove) dove.focus({ preventScroll: true });
}
LEGA_LARGA.addEventListener("change", () => { if (LEGA_LARGA.matches && legaQuandoLarga) legaQuandoLarga(); focusLegaVisibile(); });

async function vistaLega(ambito = "altro") {
  const rosaChiesta = stato.rosaTorna; stato.rosaTorna = null;
  if (ambito === "squadra" && typeof rosaChiesta === "string") { stato.legaTorna = null; return vistaRosa(rosaChiesta); }   // ?vista=squadra&rosa=… (indirizzo, Indietro)
  const mia = nuovaRichiesta();
  caricamento(t(ambito === "squadra" ? "lega.carico_squadra" : "comune.carico"));
  let squadre = [];
  try { squadre = await api("/api/squadre"); }
  catch (e) { if (e.rete) { if (ancoraValida(mia)) pagina(erroreVista(e)); return; } squadre = []; }
  if (!ancoraValida(mia)) return;
  const daUrl = stato.legaTorna; stato.legaTorna = null;
  const immagine = (sq, tipo) => sq.immagini && sq.immagini[tipo] ? `<img class="${tipo === "stemma" ? "stemma-lista" : "maglia-lista"}" src="${urlImg(sq.nome, tipo)}" alt="${t("lega.alt_immagine", { tipo: t(NOME_IMMAGINE[tipo]), nome: esc(sq.nome) })}" loading="lazy">` : "";
  const htmlSceltaMia = () => `<select class="campo-testo" id="mia-squadra" aria-label="${t("lega.tua_squadra")}">${squadre.map(x => `<option value="${esc(x.nome)}" ${x.mia ? "selected" : ""}>${esc(x.nome)}</option>`).join("")}</select>`;

  const corpi = {
    importa: () => `<div class="carta">
      <div class="debole piccolo">${t("lega.esporta_rose_excel")}</div>
      <div class="pulsanti"><label class="bottone" for="file-rose">${t("pav.scegli_file")}</label></div>
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
  };

  const aggiornaSquadre = () => { caricaInfo(); caricaSquadre(); };
  // Le pagine disegnano `squadre`, lette all'apertura: dopo un salvataggio si rileggono (con `voce`, quella pagina si ridisegna se è
  // ancora aperta), così «La mia squadra», i crediti e l'elenco delle squadre non restano quelli di prima finché non si cambia scheda.
  const rileggiSquadre = async (voce) => {
    try { squadre = await api("/api/squadre"); } catch { return; }
    if (voce && stato.legaVoce[ambito] === voce) apri(voce, false);
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
      document.querySelectorAll("[data-squadra]").forEach(b => b.addEventListener("click", () => vistaRosa(b.dataset.squadra, { nuova: true })));
      const asm = $("#apri-stemma-maglia");
      if (asm) asm.addEventListener("click", () => apriStemmaMaglia());
      const ms = $("#mia-squadra");
      if (ms) ms.addEventListener("change", async () => {
        try { await api("/api/mia-squadra", { method: "PUT", body: JSON.stringify({ nome: ms.value }) }); svuotaCache(); stato.squadraVista = null; avviso(t("lega.squadra_salvata")); aggiornaSquadre(); rileggiSquadre("squadre"); }
        catch (e) { avviso(e.message); }
      });
    },
  };

  const voci = vociLega(ambito);
  const diretta = voci.find(v => v.id === daUrl && !nellaPagina(v));      // «apri le regole» da Da fare o da un collegamento: subito lì
  if (diretta) { diretta.vai({ sostituisci: true }); return; }            // al posto della voce di adesso: Indietro non torna qui
  stato.legaVoce = stato.legaVoce || {};
  // a destra la voce chiesta (un collegamento, «‹ Squadra» dalla rosa) e, da 1100 px, quella dell'ultima volta in questa scheda o la prima
  const daAprire = () => { const accanto = voci.filter(v => nellaPagina(v)); return (accanto.find(v => v.id === stato.legaVoce[ambito]) || accanto[0] || {}).id; };
  const scelta = (voci.find(v => v.id === daUrl && nellaPagina(v)) || {}).id || (legaLarga() ? daAprire() : null);
  const nome = NOME_AMBITO[ambito];
  pagina(`<div class="lega-colonne" data-aperto="${scelta ? 1 : 0}">${menuLega(voci, scelta, t(ambito === "squadra" ? "lega.aria_squadra" : "lega.aria_altro"))}
    <section class="lega-pagina" id="lega-pagina" aria-label="${nome}"></section></div>`);
  const radice = $(".lega-colonne", contenuto);
  // Apre una voce nella pagina accanto al menu, che resta com'è (con il focus sulla voce cliccata). `sposta`: chiesta da chi usa l'app.
  const apri = (id, sposta = true) => {
    const v = voci.find(x => x.id === id), dove = $("#lega-pagina", radice);
    if (!v || !dove || !document.body.contains(radice)) return;
    if (sposta) chiudiPannelloAffiancato();                       // il pannello di un giocatore si chiude con la pagina da cui è nato
    stato.legaVoce[ambito] = id;
    radice.dataset.aperto = "1";
    radice.querySelectorAll("[data-lega]").forEach(b => { if (b.dataset.lega === id) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
    dove.innerHTML = `<button class="bottone secondario lega-indietro" id="lega-indietro" type="button">${ICONA_INDIETRO}${nome}</button>
      <h2 class="lega-titolo" id="lega-titolo" tabindex="-1">${v.nome}</h2><div id="lega-corpo">${corpi[id]()}</div>`;
    // «‹ Squadra» (sotto i 1100 px): il menu è già in pagina. Se la voce di prima nella cronologia è il menu è Indietro (#449), altrimenti
    // il menu prende il posto della voce
    $("#lega-indietro", dove).addEventListener("click", () => {
      radice.dataset.aperto = "0"; window.scrollTo(0, 0); const b = $(`[data-lega="${id}"]`, radice); if (b) b.focus();
      const menu = indirizzoVista(ambito);
      stato.vista = ambito;
      if (!tornaIndietro(da => da === menu, menu)) scriviIndirizzo({ vista: ambito, gruppo: null }, false);
    });
    indirizzoLega(ambito, sposta, id);
    collega[id]();
    if (sposta) { window.scrollTo(0, 0); if (!legaLarga()) $("#lega-titolo", dove).focus({ preventScroll: true }); }
  };
  radice.querySelectorAll("[data-lega]").forEach(b => b.addEventListener("click", () => {
    const v = voci.find(x => x.id === b.dataset.lega);
    if (v && nellaPagina(v)) apri(v.id); else if (v) v.vai({ nuova: true });   // una voce con `vai` porta a un'altra pagina (Regole)
  }));
  legaQuandoLarga = () => { if (document.body.contains(radice) && radice.dataset.aperto === "0") { const id = daAprire(); if (id) apri(id, false); } };
  if (scelta) apri(scelta, false);
  bannerNuovaStagione();
}

// Nuova stagione: quando le rose sono ancora quelle dell'anno prima, in cima a Squadra e ad Altro compare un avviso (non è più una
// voce del menu, #615: per undici mesi l'anno non c'era niente da fare). Un tocco apre il foglio con il pulsante per archiviarle.
// `s`: la risposta di GET /api/stagione.
function apriNuovaStagione(s) {
  apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("lega.nuova_stagione_n", { s: esc(s.corrente) })}</h2>
    <div class="debole piccolo">${t("lega.rose_ancora_quelle", { s: esc(s.rose) })}</div>
    <div class="pulsanti"><button class="bottone" id="nuova-stagione" type="button">${t("lega.archivia_riparti")}</button></div>`);
  $("#nuova-stagione").addEventListener("click", async () => {
    if (!confirm(t("lega.conferma_archivio", { s: s.rose }))) return;
    try {
      await api("/api/nuova-stagione", { method: "POST" }); svuotaCache();
      apriFoglio(`<h2 style="margin:0 0 4px;font-size:var(--t-card)">${t("lega.stagione_archiviata", { s: esc(s.rose) })}</h2>
        <div class="debole piccolo">${t("lega.tutto_salvato_nell")}</div>
        <div class="carta" style="margin-top:12px"><ol class="novita-voci">
          <li><b>${t("lega.importa_nuove_rose")}</b>${t("lega.squadra_aggiorna_rose")}</li>
          <li><b>${t("lega.controlla_regole")}</b>${t("lega.bonus_moduli_crediti")}</li>
          <li><b>${t("shell.aggiorna")}</b> ${t("lega.con_tasto_alto")}</li></ol></div>
        <div class="pulsanti"><button class="bottone" data-vai="squadra">${t("lega.vai_squadra")}</button></div>`);
      vaiLega("importa");
    } catch (e) { avviso(e.message, 5000); }
  });
}

async function bannerNuovaStagione() {
  try {
    const s = await api("/api/stagione");
    if (!s.nuova || !["squadra", "altro"].includes(stato.vista) || !$(".lega-colonne") || $("#banner-stagione")) return;
    const c = document.createElement("div");
    c.className = "carta"; c.dataset.g = "lega";
    c.innerHTML = `<button class="voce" id="banner-stagione" type="button" style="grid-template-columns:1fr auto"><span><span class="nome">${t("lega.nuova_stagione_n", { s: esc(s.corrente) })}</span>
      <span class="dettaglio" style="display:block">${t("lega.banner_stagione", { s: esc(s.rose) })}</span></span><span class="debole" aria-hidden="true">›</span></button>`;
    const capo = $(".capo-pagina", contenuto);                // sotto il titolo della schermata, prima del resto
    if (capo) capo.after(c); else contenuto.prepend(c);
    $("#banner-stagione").addEventListener("click", () => apriNuovaStagione(s));
  } catch { /* senza rose o senza rete: niente avviso */ }
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
// Il nome dei campi delle fasce del modificatore per i lettori di schermo: «Fascia 2, media almeno», «Fascia 2, bonus», «Togli la fascia 2»
// (#454: senza, sincronizzaAria dava a tutti il titolo della sezione, «Fasce di bonus»). `n` = posto della fascia, da 1; dopo «Togli» i numeri
// si rifanno (numeraFasce). Anche i quattro voti della prova hanno il loro nome.
const conNome = (controllo, nome) => controllo.replace("<input ", `<input aria-label="${esc(nome)}" `);
const nomiFascia = n => [t("regole.fascia_media", { n }), t("regole.fascia_bonus", { n }), t("regole.togli_fascia", { n })];
function rigaFascia(media, bonus, n) {
  const [nomeMedia, nomeBonus, nomeTogli] = nomiFascia(n);
  return `<div class="fascia"><div class="coppia"><span class="debole piccolo">${t("regole.media_almeno")}</span>${conNome(stepper("", media, { passo: 0.25, min: 4, max: 9, dec: 2 }), nomeMedia).replace('id=""', 'class="f-media"')}</div>
    <div class="coppia"><span class="debole piccolo">${t("regole.bonus")}</span>${conNome(stepper("", bonus, { passo: 0.5, min: 0, max: 20, dec: 1 }), nomeBonus).replace('id=""', 'class="f-bonus"')}</div>
    <button type="button" class="rimuovi-fascia" aria-label="${esc(nomeTogli)}">✕</button></div>`;
}
function numeraFasce() {
  document.querySelectorAll("#fasce .fascia").forEach((f, k) => {
    const [nomeMedia, nomeBonus, nomeTogli] = nomiFascia(k + 1);
    f.querySelector("input.f-media").setAttribute("aria-label", nomeMedia);
    f.querySelector("input.f-bonus").setAttribute("aria-label", nomeBonus);
    f.querySelector(".rimuovi-fascia").setAttribute("aria-label", nomeTogli);
  });
}
const votiProva = voti => voti.map((v, k) => conNome(stepper("pv" + k, v, { passo: 0.5, min: 3, max: 10 }),
  k ? t("regole.voto_difensore", { n: k }) : t("regole.voto_portiere"))).join("");

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

// `o.nuova`: aperta con un clic dal menu di Altro, una voce nuova nella cronologia (#449); senza (indirizzo, «Da fare», ridisegno dopo
// «Salva») si corregge quella di adesso.
async function vistaRegole(o = {}) {
  const mia = nuovaRichiesta();
  stato.vista = "altro";
  scriviIndirizzo({ vista: "altro", gruppo: null, voce: "regole", pagina: true }, !!o.nuova);
  caricamento(t("regole.carico"), { titolo: t("lega.voce_regole") });
  let r;
  try { r = await api("/api/regole"); } catch (e) { if (ancoraValida(mia)) pagina(errore(e), { titolo: t("lega.voce_regole") }); return; }
  if (!ancoraValida(mia)) return;
  if (regoleAC) regoleAC.abort();
  regoleAC = new AbortController();
  const sig = { signal: regoleAC.signal };
  const md = r.modificatore_difesa;
  const moduli = [...new Set([...TUTTI_MODULI, ...r.moduli])];
  const rigaGol = x => rigaRegola(t("regole.gol_di", { ruolo: NOME_RUOLO_1[x].toLowerCase() }), stepper("gol_" + x, r.bonus.gol[x], { passo: 0.5, min: 0, max: 20 }));
  const bonusRighe = [["assist", t("bonus.assist")], ["rigore_segnato", t("bonus.rigore_segnato")], ["rigore_parato", t("regole.rigore_parato_p")], ["portiere_imbattuto", t("bonus.portiere_imbattuto")], ["mvp", t("bonus.mvp")]];
  const malusRighe = [["ammonizione", t("bonus.ammonizione")], ["espulsione", t("bonus.espulsione")], ["autogol", t("bonus.autogol")], ["rigore_sbagliato", t("bonus.rigore_sbagliato")], ["gol_subito_portiere", t("bonus.gol_subito_portiere"), t("regole.per_ogni_gol")]];
  // Sul PC (da 1100 px) due colonne: a sinistra il nome della lega e «Importa da Leghe», a destra le sezioni con i «−/+», così l'anteprima
  // del testo riconosciuto sta accanto ai valori che cambia. Sotto, una colonna sola nello stesso ordine (stile.css, «regole»).
  pagina(`<div class="regole-colonne"><div class="regole-testa">
    <div class="carta">
      <div class="riga"><button class="bottone secondario indietro" data-indietro="altro" style="padding:6px 14px;min-height:44px">${ICONA_INDIETRO}${t("regole.altro")}</button>
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
    </div></div>

    <div class="regole-sezioni">
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
        <div id="fasce">${[...md.soglie].sort((a, b) => a[0] - b[0]).map((s, k) => rigaFascia(s[0], s[1], k + 1)).join("")}</div>
        <div class="pulsanti"><button type="button" class="bottone secondario" id="aggiungi-fascia">${t("regole.aggiungi_fascia")}</button></div>
        <h3>${t("regole.prova")}</h3>
        <div class="prova-difesa"><span class="debole piccolo">${t("regole.voti_portiere_difensori")}</span>
          <div class="prova-voti">${votiProva([6.5, 6, 6.5, 7])}</div>
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
      <div class="debole piccolo">${t("regole.rinviate_aiuto_formazione")}</div>
      <div class="segmenti" id="rinvio-modo">${[["aspetta", t("regole.rv_aspetta")], ["senza_voto", t("regole.rv_senza_voto")], ["voto_ufficio", t("regole.rv_ufficio")]].map(([k, nome]) => `<button type="button" data-valore="${k}" class="${r.partite_rinviate === k ? "attivo" : ""}">${nome}</button>`).join("")}</div>
      <div class="debole piccolo" id="aiuto-rinvio"></div>
      <div id="rinvio-voto-corpo" ${r.partite_rinviate === "voto_ufficio" ? "" : "hidden"}>${rigaRegola(t("regole.rv_voto"), stepper("voto_rinv", r.voto_ufficio_rinviate ?? 6, { passo: 0.5, min: 0, max: 10 }))}</div>
    </details>` : ""}

    <details class="carta regola-sez"><summary>${t("regole.rosa_crediti")}</summary>
      ${["P", "D", "C", "A"].map(x => rigaRegola(NOMI_RUOLO[x], stepper("rosa_" + x, r.rosa[x], { passo: 1, min: 0, max: 20, dec: 0 }))).join("")}
      ${rigaRegola(t("regole.crediti_iniziali"), stepper("crediti", r.crediti_iniziali, { passo: 10, min: 0, max: 5000, dec: 0 }))}
    </details>
    <div class="salva-fisso" hidden><button class="bottone" id="salva-regole">${t("regole.salva_regole")}</button></div></div></div>`, { titolo: t("lega.voce_regole") });
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
    $("#fasce").insertAdjacentHTML("beforeend", rigaFascia(Math.min(9, ultima[0] + 0.5), ultima[1] + 1, f.length + 1));
    aggiornaProva(); mostraSalva();
  });
  contenuto.addEventListener("click", ev => {
    const x = ev.target.closest(".rimuovi-fascia");
    if (x) { x.closest(".fascia").remove(); numeraFasce(); aggiornaProva(); mostraSalva(); }
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
      else if (k === "modificatore_difesa.soglie") { $("#fasce").innerHTML = v.map((s, i) => rigaFascia(s[0], s[1], i + 1)).join(""); aggiornaProva(); }
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
// La riga sopra i campi di «Registrati»: con il codice d'invito già scritto (arrivato dal link) non chiede di procurarselo (#580).
function spiegaRegistrazione(modo, conInvito) {
  if (modo === "aperta") return "accesso.serve_email";
  if (modo === "email") return conInvito ? "accesso.invito_inserito_email" : "accesso.serve_invito_email";
  return conInvito ? "accesso.invito_inserito" : "accesso.serve_invito";
}
// `extra.sub`: passo dentro la scheda (registra: "verifica"; recupero: "codice" | "email" | "email-codice"); `extra.email`: indirizzo del passo
function campiAccesso(scheda, extra = {}) {
  const modo = stato.registrazione || "invito";
  if (scheda === "accedi") return CAMPO_NOME() + campoAccesso("ac-pw", t("accesso.password"), "password", `autocomplete="current-password" ${CAMPO_PW}`);
  if (scheda === "registra" && extra.sub === "verifica") return `<div class="debole piccolo">${t("accesso.verifica_spiega", { email: esc(extra.email || "") })}</div>`
    + CAMPO_CODICE_EMAIL("ac-codice-email");
  if (scheda === "registra") return `<div class="debole piccolo">${t(spiegaRegistrazione(modo, !!invitoSalvato()))}</div>`
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

// Dopo un errore la password si svuota solo se è stata rifiutata (accesso o codice sbagliato: 401/403). In «Registrati» mai: la
// password è nuova e il rifiuto riguarda altro (invito non valido o già usato, registrazioni chiuse, #580). Un errore di compilazione
// (400, 422), una casella non spuntata o l'attesa (429) non fanno perdere quello che hai scritto.
function svuotaPassword(scheda, codiceHttp) {
  return scheda !== "registra" && (codiceHttp === 401 || codiceHttp === 403);
}

// La pagina di accesso copre tutto: finché non si entra, dell'app non si vede (e non si carica) niente.
function mostraAccesso(messaggio = "", scheda = "accedi", extra = {}) {
  accessoAperto = true;
  if (scheda === "recupero" && !extra.sub) extra = { ...extra, sub: (stato.registrazione || "invito") === "invito" || stato.emailAttiva === false ? "codice" : "email" };
  stato.account = null;
  document.body.classList.add("senza-accesso");
  contenuto.innerHTML = ""; contenuto.removeAttribute("aria-busy");
  let el = $("#accesso");
  const primaVolta = !el;
  if (!el) {
    el = document.createElement("div");
    el.id = "accesso"; el.className = "accesso";
    el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); el.setAttribute("aria-label", t("accesso.nome_aria"));
    document.body.appendChild(el);
  }
  // grafica B (spec §9): un modulo centrato senza carta; il nome è quello disegnato della testata, per i lettori di schermo «SchieraXI»
  el.innerHTML = `<div class="accesso-corpo${primaVolta ? " primo" : ""}">
    <div class="accesso-marchio">${marchio(72, true)}</div>
    <h1 class="accesso-titolo"><svg class="wm" aria-hidden="true" focusable="false"><use href="#wm-c"/></svg><span class="solo-lettori">SchieraXI</span></h1>
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
        const ep = await endpointPushQui();
        const r = await manda("/api/account/recupero-email/conferma", { email: extra.email, codice: v("#ac-codice-email").trim(), nuova: v("#ac-pw"), ...(ep ? { endpoint_push: ep } : {}) });
        if (!r || !r.codice_recupero) throw new Error(t("accesso.risposta_incompleta"));
        mostraCodiceAccesso(t("accesso.password_cambiata"), r.codice_recupero, t("accesso.vai_accesso"), () => mostraAccesso(t("accesso.password_cambiata_accedi")));
      } else {
        const ep = await endpointPushQui();
        const r = await manda("/api/account/recupero", { nome_utente: v("#ac-nome"), codice: v("#ac-codice"), nuova: v("#ac-pw"), ...(ep ? { endpoint_push: ep } : {}) });
        if (!r || !r.codice_recupero) throw new Error(t("accesso.risposta_incompleta"));
        mostraCodiceAccesso(t("accesso.password_cambiata"), r.codice_recupero, t("accesso.vai_accesso"), () => mostraAccesso(t("accesso.password_cambiata_accedi")));
      }
    } catch (e) {
      const attesa = e.status === 429 && e.riprova ? (e.riprova < 90 ? t("accesso.riprova_secondi", { n: e.riprova }) : e.riprova < 3600 ? t("accesso.riprova_minuti", { n: Math.ceil(e.riprova / 60) }) : t("accesso.riprova_ore", { n: Math.max(1, Math.round(e.riprova / 3600)) })) : "";
      const msg = document.createElement("div");
      msg.className = "errore"; msg.textContent = (e.message || t("accesso.errore_generico")) + attesa;
      if ($("#accesso-msg")) $("#accesso-msg").replaceChildren(msg);
      if ($("#ac-pw") && svuotaPassword(scheda, e.status)) $("#ac-pw").value = "";
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
  el.innerHTML = `<div class="accesso-corpo"><div class="accesso-marchio">${marchio(72, true)}</div>
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
  $("#accesso").innerHTML = `<div class="accesso-corpo"><h1 class="accesso-titolo">${esc(titolo)}</h1>
    <h2>${t("codice.titolo")}</h2>${htmlCodiceUnaVolta(codice)}
    <label class="interruttore"><span>${t("codice.salvato")}</span><input type="checkbox" id="codice-salvato"></label>
    <div class="pulsanti"><button class="bottone" id="codice-continua" disabled>${esc(continua)}</button></div></div>`;
  collegaCopiaCodice(codice);
  $("#codice-salvato").addEventListener("change", ev => { $("#codice-continua").disabled = !ev.target.checked; });
  $("#codice-continua").addEventListener("click", dopo);
}

// L'indirizzo delle notifiche web di questo dispositivo, o "" se non ci sono: dopo un cambio di password o un recupero il server
// tiene solo questo e toglie le altre iscrizioni. Non aspetta il service worker: se non c'è, non ci sono nemmeno le notifiche.
async function endpointPushQui() {
  try {
    if (!("serviceWorker" in navigator && "PushManager" in window)) return "";
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg && reg.pushManager ? await reg.pushManager.getSubscription() : null;
    return sub && sub.endpoint ? sub.endpoint : "";
  } catch { return ""; }
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
    const corpo = { attuale: valore("#acc-attuale"), nuova: valore("#acc-nuova") };
    const ep = await endpointPushQui();
    if (ep) corpo.endpoint_push = ep;                                     // le notifiche di questo dispositivo restano, le altre si tolgono
    const r = await api("/api/account/cambia-password", { method: "POST", body: JSON.stringify(corpo) });
    $("#acc-attuale").value = ""; $("#acc-nuova").value = ""; $("#acc-ripeti").value = "";
    if (r && r.codice_recupero) {                                         // il codice di prima non vale più: si mostra subito quello nuovo
      mostraCodice("#acc-esito-password", r.codice_recupero);
      avviso(t("account.password_cambiata_codice"), 6000);
    } else avviso(t("account.password_cambiata_ok"), 5000);
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
let iniziale = "formazione";
try { iniziale = localStorage.getItem("vista") || "formazione"; } catch { /* niente memoria */ }
togliPrefVecchie();                                                                        // colore, densità, animazioni e sezione iniziale non si scelgono più
try { const v = new URLSearchParams(location.search).get("vista"); if (SCHEDA_DI(v) || v === "impostazioni") iniziale = v; stato.impDaUrl = new URLSearchParams(location.search).get("gruppo"); } catch { /* indirizzo strano */ }   // scorciatoie dell'icona (Formazione, Squadra)
// la voce di Squadra o di Altro e la rosa di una squadra (#449): un ricaricamento riapre la pagina, senza voci nuove nella cronologia
try { const q = new URLSearchParams(location.search); if (q.get("voce")) stato.legaTorna = q.get("voce"); if (q.get("vista") === "squadra" && q.has("rosa")) stato.rosaTorna = q.get("rosa"); } catch { /* indirizzo strano */ }
if (!SCHEDA_DI(iniziale) && iniziale !== "impostazioni") iniziale = "formazione";    // «oggi», «mercato», «scambi» e «lega» dei vecchi salvataggi e indirizzi valgono ancora: vai() li porta alla schermata che resta
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
    // dal menu Condividi si apre il foglio di stemma e maglia: la guida non gli prende il posto
    if (typeof primoAvvioSeServe === "function" && !condivisa) primoAvvioSeServe();
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

// Colonne ferme in alto su tablet e PC (il campo della Formazione, l'elenco di Impostazioni, il menu di Squadra e Altro, la giornata
// scelta in Giornate): restano ferme solo se ci stanno nello schermo. Più alte, il loro fondo (il portiere, la spunta «L'ho messa»)
// restava sotto la barra o fuori dallo schermo, con il Tab e anche scorrendo: iPad con il testo grande, telefono in orizzontale, PC con
// la finestra bassa (#280).
const FERME = ".fz-campo .campo-fermo, .imp-elenco, .lega-menu, .gn-lato";
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
// I nomi delle colonne fermi sotto la testata negli elenchi lunghi (la rosa di una squadra; spec C7): oltre un terzo della finestra
// (zoom, testo grande, finestra bassa) scorrono con la pagina; la loro altezza vera, quando sono fermi, va in --alto-colonne per
// scroll-padding-top: la riga con il focus (Maiusc+Tab) non finisce sotto di loro.
const QUOTA_STATO = 1 / 3;
function controllaColonneFerme() {
  let alto = 0;
  document.querySelectorAll(".intestazione-colonne.ferma").forEach(el => {
    const era = el.classList.contains("non-ferma"), troppo = el.getBoundingClientRect().height > innerHeight * QUOTA_STATO;
    if (troppo !== era) el.classList.toggle("non-ferma", troppo);        // la classe si tocca solo quando cambia (sincronizzaAria)
    if (getComputedStyle(el).position === "sticky") alto = Math.max(alto, el.offsetHeight);
  });
  document.documentElement.style.setProperty("--alto-colonne", `${alto}px`);
}
(function seguiFerme() {
  let atteso = false;
  const pianifica = () => { if (!atteso) { atteso = true; requestAnimationFrame(() => { atteso = false; controllaFerme(); controllaColonneFerme(); }); } };
  new MutationObserver(pianifica).observe(contenuto, { subtree: true, childList: true });
  if (typeof ResizeObserver === "function") new ResizeObserver(pianifica).observe(contenuto);          // anche quando una carta cresce dopo
  addEventListener("resize", pianifica);
  pianifica();
})();
