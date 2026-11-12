"use strict";
// Impostazioni (#618): una voce della barra, una pagina sola con le sezioni Avvisi, La mia lega, Aspetto, e le righe che aprono una
// pagina loro (Il tuo account, Informazioni, Gestione per chi gestisce il server). Al posto delle schede Squadra e Altro e dei gruppi
// di prima: chi la apre vede al massimo una decina di controlli. Si carica dopo app.js e ne usa le funzioni.
// Indirizzi: ?vista=impostazioni, ?vista=impostazioni&gruppo=<pagina> (rose, squadra, squadre, regole, account, informazioni,
// gestione), ?vista=impostazioni&gruppo=squadre&rosa=<nome>. Gli indirizzi di prima (gruppi, Squadra, Altro) li traduce dove() in app.js.

// La schermata di un indirizzo già tradotto da dove(): {gruppo, rosa, sezione}.
function vistaImpostazioni(d = {}) {
  const PAGINE = { rose: () => vistaImportaRose(), squadra: () => vistaRosa(""), squadre: () => (d.rosa ? vistaRosa(d.rosa) : vistaAltreSquadre()),
    regole: () => vistaRegole(), account: paginaAccount, informazioni: paginaInformazioni, gestione: paginaGestione };
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
    conRose && squadre.length > 1 && funz("squadre_altrui") ? rigaImp("squadre", t("imp.altre_squadre"), tp("lega.n_squadre", squadre.length)) : ""].join("");
  const a = stato.account;
  pagina(`<div class="imp-griglia">
    <section class="carta imp-sezione" id="imp-avvisi" aria-labelledby="imp-avvisi-t"><h2 id="imp-avvisi-t">${t("imp.sez_avvisi")}</h2>
      <div id="avvisi-telefono" aria-busy="true"><div class="caricamento">${t("comune.carico")}</div></div></section>
    <section class="carta imp-sezione" id="imp-lega" aria-labelledby="imp-lega-t"><h2 id="imp-lega-t">${t("imp.lega")}</h2>
      <ul class="elenco">${lega}</ul></section>
    ${a ? `<div class="carta imp-sezione"><ul class="elenco">${rigaImp("account", t("imp.account"), esc(a.nome_visualizzato || a.nome_utente))}</ul></div>` : ""}
    <section class="carta imp-sezione" id="imp-aspetto" aria-labelledby="imp-aspetto-t"><h2 id="imp-aspetto-t">${t("imp.aspetto")}</h2>${schedaAspetto()}</section>
    <div class="carta imp-sezione"><ul class="elenco">${rigaImp("informazioni", t("imp.informazioni"), t("imp.informazioni_sub"))}
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

// Gestione, solo per chi gestisce il server: l'aggiornamento dei dati (le frecce che stavano in testata), lo stato dei dati, inviti,
// codici, utenti ed errori del server. Sul server senza account anche l'avviso con ntfy per l'app nativa.
function paginaGestione() {
  nuovaRichiesta();
  pagina(`<div class="imp-colonna">
    <div class="carta"><h2>${t("shell.aggiorna")}</h2><p class="debole piccolo">${t("imp.aggiorna_spiega")}</p>
      <div class="pulsanti"><button class="bottone secondario" id="aggiorna-dati" type="button"${stato.aggiornoDati ? " disabled" : ""}>${t("shell.aggiorna")}</button></div></div>
    <div class="carta"><h2>${t("av.stato")}</h2><p class="debole piccolo">${t("av.stato_spiega")}</p>
      <div class="pulsanti"><button class="bottone secondario" id="apri-stato-dati" type="button">${t("av.apri_stato")}</button></div></div>
    ${stato.account ? "" : `<div class="carta" id="avvisi-nativa" aria-busy="true"><div class="caricamento">${t("comune.carico")}</div></div>`}
    ${schedaAmministratore()}</div>`, { titolo: t("imp.gestione"), stato: false, indietro: indietroImp() });
  $("#aggiorna-dati").addEventListener("click", aggiornaDati);
  $("#apri-stato-dati").addEventListener("click", apriStatoDati);
  collegaAmministratore();
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
  const giorno = fData(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])), { day: "numeric", month: "short", year: "numeric" });
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
