"use strict";
// Impostazioni (#618): una voce della barra, una pagina sola con le sezioni Avvisi, La mia lega, Aspetto, e le righe che aprono una
// pagina loro (Il tuo account, Informazioni, Gestione per chi gestisce il server). Al posto delle schede Squadra e Altro e dei gruppi
// di prima: chi la apre vede al massimo una decina di controlli. Si carica dopo app.js e ne usa le funzioni.
// Indirizzi: ?vista=impostazioni, ?vista=impostazioni&gruppo=<pagina> (rose, squadra, squadre, regole, account, informazioni,
// scrivici, gestione), ?vista=impostazioni&gruppo=squadre&rosa=<nome>. Gli indirizzi di prima (gruppi, Squadra, Altro) li traduce dove() in app.js.

// La schermata di un indirizzo già tradotto da dove(): {gruppo, rosa, sezione}.
function vistaImpostazioni(d = {}) {
  const PAGINE = { rose: () => vistaImportaRose(), squadra: () => vistaRosa(""), squadre: () => (d.rosa ? vistaRosa(d.rosa) : vistaAltreSquadre()),
    regole: () => vistaRegole(), account: paginaAccount, informazioni: paginaInformazioni, scrivici: paginaScrivici, gestione: paginaGestione };
  if (d.gruppo && Object.hasOwn(PAGINE, d.gruppo)) { PAGINE[d.gruppo](); return; }
  paginaImpostazioni(d.sezione);
}

// Una riga che apre una pagina di Impostazioni: il nome grande, sotto una riga piccola (testi dal catalogo o già passati da esc()).
const rigaImp = (gruppo, nome, sotto) => `<li><button class="voce imp-voce" type="button" data-imp-gruppo="${gruppo}">
  <span><span class="nome">${nome}</span>${sotto ? `<span class="dettaglio">${sotto}</span>` : ""}</span><span class="debole" aria-hidden="true">›</span></button></li>`;

// La pagina di Impostazioni. `sezione` (avvisi, lega, aspetto: un indirizzo di prima che portava lì) si porta in vista.
function paginaImpostazioni(sezione) {
  nuovaRichiesta();
  const squadre = stato.squadre || [], mia = miaSquadra(), conRose = squadre.length > 0;
  const lega = [rigaImp("rose", t("lega.voce_importa"), t("lega.voce_importa_sub")),
    conRose ? rigaImp("squadra", t("lega.mia_squadra"), mia ? esc(mia.nome) : t("imp.mia_squadra_nessuna")) : "",
    rigaImp("regole", t("imp.regole"), t("imp.regole_sub")),
    // il numero delle altre, senza la mia (#779): è quello dell'elenco che la riga apre (vistaAltreSquadre)
    conRose && squadre.length > 1 && funz("squadre_altrui") ? rigaImp("squadre", t("imp.altre_squadre"), tp("lega.n_squadre", squadre.filter(s => !s.mia).length)) : ""].join("");
  const a = stato.account;
  pagina(`<div class="imp-griglia">
    <section class="carta imp-sezione" id="imp-avvisi" aria-labelledby="imp-avvisi-t"><h2 id="imp-avvisi-t">${t("imp.sez_avvisi")}</h2>
      <div id="avvisi-telefono" aria-busy="true"><div class="caricamento">${t("comune.carico")}</div></div></section>
    <section class="carta imp-sezione" id="imp-lega" aria-labelledby="imp-lega-t"><h2 id="imp-lega-t">${t("imp.lega")}</h2>
      <ul class="elenco">${lega}</ul></section>
    ${a ? `<div class="carta imp-sezione"><ul class="elenco">${rigaImp("account", t("imp.account"), esc(a.nome_visualizzato || a.nome_utente))}</ul></div>` : ""}
    <section class="carta imp-sezione" id="imp-aspetto" aria-labelledby="imp-aspetto-t"><h2 id="imp-aspetto-t">${t("imp.aspetto")}</h2>${schedaAspetto()}</section>
    <div class="carta imp-sezione"><ul class="elenco">${rigaImp("informazioni", t("imp.informazioni"), t("imp.informazioni_sub"))}
      ${a ? rigaImp("scrivici", t("scrivici.voce"), t("scrivici.voce_sub")) : ""}
      ${soloAmministratore() ? rigaImp("gestione", t("imp.gestione"), t("imp.gestione_sub")) : ""}</ul></div>
  </div>`, { stato: false });
  collegaAspetto();
  const inVista = () => { const s = sezione && $(`#imp-${sezione}`); if (s) s.scrollIntoView({ block: "start" }); };
  inVista();
  avvisiTelefono().then(inVista);                     // gli avvisi arrivano dopo e cambiano l'altezza di ciò che sta sopra
  bannerNuovaStagione();
}

// ---------------------------------------------------------------- le pagine
function paginaAccount() {
  nuovaRichiesta();
  pagina(`<div class="imp-colonna">${schedaAccount()}</div>`, { titolo: t("imp.account"), stato: false, indietro: indietroImp() });
  collegaAccount();
}

// Una voce che apre una pagina legale (in una scheda nuova, nella lingua scelta).
const voceLegale = (pagina, chiave) => `<li><a class="voce voce-link" href="/${pagina}${queryLingua()}" target="_blank" rel="noopener" style="grid-template-columns:1fr auto">
  <span class="nome">${t(chiave)}</span><span class="debole" aria-hidden="true">›</span></a></li>`;

// Il codice sorgente (licenza AGPL-3.0): solo un indirizzo https dichiarato dal server (FANTA_SORGENTE, campo `sorgente` di /api/stato).
const voceSorgente = () => {
  const s = stato.info && stato.info.sorgente;
  return typeof s === "string" && /^https:\/\/[^\s"'<>]+$/.test(s) ? `<li><a class="voce voce-link" href="${esc(s)}" target="_blank" rel="noopener" style="grid-template-columns:1fr auto">
  <span class="nome">${t("info.sorgente")}</span><span class="debole" aria-hidden="true">›</span></a></li>` : "";
};

// Informazioni: pagine legali, versione e, sotto, le novità (dal 12/11/2026, #615: non sono più una voce di Altro né un banner).
function paginaInformazioni() {
  nuovaRichiesta();
  const v = stato.info && stato.info.versione;
  pagina(`<div class="imp-colonna"><div class="carta"><ul class="elenco">${voceLegale("privacy", "legale.privacy")}${voceLegale("termini", "legale.termini")}${voceLegale("crediti", "legale.crediti")}${voceSorgente()}</ul>
      <div class="riga"><span>${t("info.versione")}</span><b>${v ? esc(v) : "–"}</b></div></div>
    <div class="carta"><h2>${t("info.novita")}</h2><div id="novita-elenco" aria-busy="true"><div class="caricamento">${t("novita.carico")}</div></div></div></div>`,
  { titolo: t("imp.informazioni"), stato: false, indietro: indietroImp() });
  mostraNovita($("#novita-elenco"));
}

// Scrivici (26/11/2026): un commento a chi gestisce il server, solo con un account (senza account c'è solo lui, sul suo computer).
// La casella va a capo e tiene al massimo MAX_COMMENTO caratteri (il tetto del server); «Invia» resta spento finché è vuota.
// Riuscito: la casella si svuota e sotto c'è «Grazie, l'abbiamo ricevuto.»; non riuscito: il messaggio del server (per esempio il
// limite di 5 al giorno) in un role="alert", e il testo scritto resta. La versione è quella che mostra Informazioni.
const MAX_COMMENTO = 2000;
function paginaScrivici() {
  nuovaRichiesta();
  pagina(`<div class="imp-colonna"><div class="carta"><p>${t("scrivici.spiega")}</p>
      <label class="accesso-campo"><span class="debole piccolo">${t("scrivici.campo")}</span>
        <textarea class="campo-testo" id="scrivici-testo" maxlength="${MAX_COMMENTO}" rows="6"></textarea></label>
      <div class="pulsanti"><button class="bottone" id="scrivici-invia" type="button" disabled>${t("scrivici.invia")}</button></div>
      <p class="nota-pulsanti" id="scrivici-esito" role="status"></p><div id="scrivici-errore" role="alert"></div></div></div>`,
  { titolo: t("scrivici.voce"), stato: false, indietro: indietroImp() });
  const campo = $("#scrivici-testo"), invia = $("#scrivici-invia");
  const mostra = (esito, errore) => { $("#scrivici-esito").textContent = esito; $("#scrivici-errore").innerHTML = errore ? `<div class="errore">${esc(errore)}</div>` : ""; };
  campo.addEventListener("input", () => { invia.disabled = !campo.value.trim(); mostra("", ""); });
  invia.addEventListener("click", async () => {
    invia.disabled = true;
    mostra("", "");
    const versione = stato.info && stato.info.versione;
    try {
      await api("/api/feedback", { method: "POST", body: JSON.stringify({ testo: campo.value, ...(versione ? { versione: String(versione) } : {}) }) });
      if (!document.body.contains(campo)) return;                        // nel frattempo si è aperta un'altra pagina
      campo.value = "";
      mostra(t("scrivici.grazie"), "");
    } catch (e) {
      if (!document.body.contains(campo)) return;
      mostra("", e.message || t("scrivici.non_inviato"));
      invia.disabled = !campo.value.trim();
    }
  });
}

// Gestione › «Commenti degli utenti» (Scrivici): il più recente in alto; per ognuno chi, quando (ora italiana), da dove e il testo
// intero, che va a capo dove è andato a capo chi l'ha scritto, e «Segna come letto» su quelli nuovi. Il testo e il nome vengono
// dagli utenti: entrano nella pagina SOLO come textContent, mai come HTML.
const schedaCommenti = () => gestisceAccount() ? `<section class="carta" id="scheda-commenti" aria-labelledby="commenti-t">
    <h2 id="commenti-t">${t("scrivici.titolo_gestione")}</h2><p class="debole piccolo">${t("scrivici.spiega_gestione")}</p>
    <p class="piccolo" id="commenti-da-leggere"></p>
    <div id="commenti-elenco" aria-busy="true"><div class="caricamento">${t("comune.carico")}</div></div></section>` : "";
const DA_PIATTAFORMA = { web: "scrivici.da_web", ios: "scrivici.da_ios", android: "scrivici.da_android" };
const quandoCommento = q => { const d = new Date(q); return Number.isNaN(d.getTime()) ? String(q || "")
  : d.toLocaleString(t("lingua.locale"), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }); };
function rigaCommento(c, segnaLetto) {
  const li = document.createElement("li"), testa = document.createElement("div"), testo = document.createElement("p");
  const dove = [Object.hasOwn(DA_PIATTAFORMA, c.piattaforma) ? t(DA_PIATTAFORMA[c.piattaforma]) : "",
    c.versione ? t("scrivici.versione", { v: c.versione }) : ""].filter(Boolean).join(", ");
  testa.className = "debole piccolo";
  testa.textContent = [c.utente, quandoCommento(c.quando), dove].filter(Boolean).join(" · ");
  testo.className = "commento-testo";
  testo.textContent = c.testo;
  li.append(testa, testo);
  const coda = document.createElement("div");
  coda.className = "commento-coda";
  if (c.letto) { coda.classList.add("debole", "piccolo"); coda.textContent = t("scrivici.letto"); }
  else {
    const b = document.createElement("button");
    b.type = "button"; b.className = "azione-testo"; b.textContent = t("scrivici.segna_letto");
    b.setAttribute("aria-label", t("scrivici.segna_letto_di", { utente: c.utente }));
    b.addEventListener("click", () => segnaLetto(c, b));
    coda.append(b);
  }
  li.append(coda);
  return li;
}
async function caricaCommenti() {
  const dove = $("#commenti-elenco");
  if (!dove) return;
  let daLeggere = 0;
  const conta = () => { const p = $("#commenti-da-leggere"); if (p) p.textContent = daLeggere > 0 ? tp("scrivici.da_leggere", daLeggere) : ""; };
  const segnaLetto = async (c, b) => {
    b.disabled = true;
    try {
      await api(`/api/admin/feedback/${Number(c.id)}/letto`, { method: "POST" });
      const coda = b.parentElement;
      coda.classList.add("debole", "piccolo");
      coda.textContent = t("scrivici.letto");
      daLeggere = Math.max(0, daLeggere - 1);
      conta();
    } catch (e) { b.disabled = false; avviso(e.message || t("scrivici.non_segnato"), 5000); }
  };
  try {
    const r = await api("/api/admin/feedback");
    if (!document.body.contains(dove)) return;
    daLeggere = Number(r.da_leggere) || 0;
    conta();
    const commenti = Array.isArray(r.commenti) ? r.commenti : [];
    if (!commenti.length) { dove.innerHTML = `<p class="debole piccolo">${t("scrivici.nessuno")}</p>`; return; }
    const ul = document.createElement("ul");
    ul.className = "elenco commenti-elenco";
    ul.setAttribute("aria-labelledby", "commenti-t");
    ul.append(...commenti.map(c => rigaCommento(c, segnaLetto)));
    dove.replaceChildren(ul);
  } catch (e) { if (document.body.contains(dove)) dove.innerHTML = errore(e); }
  finally { dove.removeAttribute("aria-busy"); }
}

// Gestione, solo per chi gestisce il server: l'aggiornamento dei dati (le frecce che stavano in testata), lo stato dei dati, inviti,
// codici, utenti ed errori del server. Sul server senza account anche l'avviso con ntfy per l'app nativa. Con gli account, da
// 1100 px due colonne larghe come le altre pagine (#894): gli strumenti a sinistra, «Commenti degli utenti» ed «Errori recenti» a destra.
function paginaGestione() {
  nuovaRichiesta();
  const errori = schedaErrori();
  pagina(`<div class="imp-colonna${errori ? " gestione-colonne" : ""}"><div class="gestione-strumenti">
    <div class="carta"><h2>${t("shell.aggiorna")}</h2><p class="debole piccolo">${t("imp.aggiorna_spiega")}</p>
      <div class="pulsanti"><button class="bottone secondario" id="aggiorna-dati" type="button"${stato.aggiornoDati ? " disabled" : ""}>${t("shell.aggiorna")}</button></div>
      <p class="debole piccolo nota-pulsanti" id="aggiorna-in-corso" role="status">${stato.aggiornoDati ? t("aggiorna.in_corso") : ""}</p></div>
    <div class="carta"><h2>${t("av.stato")}</h2><p class="debole piccolo">${t("av.stato_spiega")}</p>
      <div class="pulsanti"><button class="bottone secondario" id="apri-stato-dati" type="button">${t("av.apri_stato")}</button></div></div>
    ${stato.account ? "" : `<div class="carta" id="avvisi-nativa" aria-busy="true"><div class="caricamento">${t("comune.carico")}</div></div>`}
    ${schedaAmministratore()}</div>${errori ? `<div class="gestione-errori">${schedaCommenti()}${errori}</div>` : ""}</div>`,
  { titolo: t("imp.gestione"), stato: false, indietro: indietroImp() });
  $("#aggiorna-dati").addEventListener("click", aggiornaDati);
  segnaAggiornamento(!!stato.aggiornoDati, true);      // server già occupato (letto prima): si rilegge subito, poi finché non finisce (#763)
  $("#apri-stato-dati").addEventListener("click", apriStatoDati);
  collegaAmministratore();
  caricaCommenti();
  avvisiNativa();
}

// Sul server senza account gli avvisi possono arrivare anche con ntfy, il cui tocco apre l'app nativa per iPhone (opzione `app_nativa`).
async function avvisiNativa() {
  const dove = $("#avvisi-nativa");
  if (!dove) return;
  try {
    const a = await api("/api/avvisi");
    if (!document.body.contains(dove)) return;
    dove.innerHTML = interruttore("av_nativa", t("avv.nativa"), a.impostazioni.app_nativa, t("avv.nativa_aiuto"));
    $("#av_nativa").addEventListener("change", async ev => {
      const acceso = ev.target.checked;
      try { await api("/api/avvisi", { method: "PUT", body: JSON.stringify({ app_nativa: acceso }) }); }
      catch (e) { ev.target.checked = !acceso; avviso(e.message); }
    });
  } catch (e) { if (document.body.contains(dove)) dove.innerHTML = errore(e); }
  finally { dove.removeAttribute("aria-busy"); }
}

// ---------------------------------------------------------------- le novità
// Le ultime NOVITA_VISIBILI versioni; le altre (sono centinaia) solo a richiesta, così la pagina resta leggera. Titoli e voci passano da esc().
const NOVITA_VISIBILI = 10;
// "2026-10-30T14:05:12" -> "30 ott 2026, 14:05:12" (l'ora è già italiana: non si converte); senza ora, solo la data
function dataNovita(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}:\d{2}))?/.exec(String(d || ""));
  if (!m) return "";
  const giorno = fData(parseData(`${m[1]}-${m[2]}-${m[3]}`), { day: "numeric", month: "short", year: "numeric" });
  return `${giorno}${m[4] ? ", " + m[4] : ""}`;
}
async function mostraNovita(dove) {
  if (!dove) return;
  try {
    const elenco = await api("/api/novita");
    if (!document.body.contains(dove)) return;                             // nel frattempo si è aperta un'altra pagina
    const carta = v => `<div class="novita-versione"><h3 class="novita-titolo">${esc(v.titolo)}</h3>
        <div class="debole piccolo">${t("novita.versione", { v: esc(v.versione) })} · ${dataNovita(v.data)}</div>
        <ul class="novita-voci">${(v.voci || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    const resto = elenco.length - NOVITA_VISIBILI;
    // una colonna da leggere: righe di testo al massimo 70 caratteri anche sul PC (spec grafica B, C12)
    dove.innerHTML = `<div class="novita-pagina">${elenco.slice(0, NOVITA_VISIBILI).map(carta).join("")}
      ${resto > 0 ? `<div class="pulsanti" id="novita-altre-riga"><button class="bottone secondario" id="novita-altre" type="button">${tp("novita.precedenti", resto)}</button></div>` : ""}</div>`;
    const altre = $("#novita-altre");
    if (altre) altre.addEventListener("click", () => { $("#novita-altre-riga").outerHTML = elenco.slice(NOVITA_VISIBILI).map(carta).join(""); });
  } catch (e) { if (document.body.contains(dove)) dove.innerHTML = errore(e); }
  finally { dove.removeAttribute("aria-busy"); }
}
