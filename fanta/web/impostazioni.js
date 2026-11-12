"use strict";
// Impostazioni: tutto quello che riguarda te e l'app (non la lega) in un posto solo, aperto dall'ingranaggio in testata.
// Poche voci, come nell'app per iPhone (ripulita del 1/11/2026): account, aspetto, notifiche, informazioni; «Avanzate» solo per
// chi gestisce SchieraXI. Si carica dopo app.js e ne usa le funzioni.
// Indirizzi: ?vista=impostazioni oppure ?vista=impostazioni&gruppo=avvisi (gruppi: account, aspetto, avvisi, informazioni, avanzate).

const GRUPPI_IMP = [
  { id: "account", nome: t("imp.account"), sub: t("imp.account_sub"), visibile: () => !!stato.account },
  { id: "aspetto", nome: t("imp.aspetto"), sub: t("imp.aspetto_sub") },
  { id: "avvisi", nome: t("imp.avvisi"), sub: t("imp.avvisi_sub") },
  { id: "informazioni", nome: t("imp.informazioni"), sub: t("imp.informazioni_sub") },
  { id: "avanzate", nome: t("imp.avanzate"), sub: t("imp.avanzate_sub"), visibile: () => soloAmministratore() },
];
const gruppiVisibili = () => GRUPPI_IMP.filter(g => !g.visibile || g.visibile());
const impLargo = () => window.matchMedia("(min-width: 768px)").matches;

function vistaImpostazioni(gruppo) {
  const visibili = gruppiVisibili();
  const daUrl = stato.impDaUrl; stato.impDaUrl = null;
  gruppo = gruppo || daUrl;
  let scelto = visibili.find(g => g.id === gruppo);
  if (!scelto && impLargo()) scelto = visibili.find(g => g.id === stato.impGruppo) || visibili[0];
  // titolo della schermata «Impostazioni», senza la riga della giornata: qui si parla di te e dell'app, non della lega
  const cfg = { voci: visibili, corpi: CORPI_IMP, collega: COLLEGA_IMP, aria: t("imp.gruppi_aria"), indietro: t("shell.impostazioni"), scelto: scelto && scelto.id, ricorda: id => { stato.impGruppo = id; },
    titolo: t("shell.impostazioni"), stato: false, indirizzo: indirizzoImp, lista: listaImp };
  stato.pannelli = cfg;
  montaPannelli(cfg);
}

// Il gruppo aperto ha il suo indirizzo (?vista=impostazioni&gruppo=…, #449): aperto con un clic (`nuova`) è una voce nuova nella
// cronologia, così Indietro torna all'elenco (sotto i 768 px) o al gruppo di prima; aperto da solo (da 768 px il primo, un indirizzo,
// Indietro) corregge la voce di adesso.
function indirizzoImp(id, nuova) {
  scriviIndirizzo({ vista: "impostazioni", gruppo: id, scheda: null }, nuova);
}
// «‹ Impostazioni» (sotto i 768 px): l'elenco è già in pagina. Se la voce di prima nella cronologia è l'elenco è Indietro (niente voce
// morta), altrimenti l'elenco prende il posto del gruppo.
function listaImp() {
  const lista = indirizzoVista("impostazioni");
  if (!tornaIndietro(da => da === lista, lista)) scriviIndirizzo({ vista: "impostazioni", gruppo: null, scheda: null }, false);
}

// Il componente a due pannelli (elenco di voci + pagina), usato da Impostazioni e da Lega.
// cfg: voci [{id, nome, sub}], corpi {id: () => html}, collega {id: () => void}, aria, indietro (nome della pagina madre), scelto (id o nulla), ricorda(id);
// titolo e stato (facoltativi) vanno a pagina(): senza, il titolo è il nome della scheda (Squadra, Altro).
function montaPannelli(cfg) {
  pagina(`<div class="imp" data-aperto="${cfg.scelto ? 1 : 0}">
    <nav class="imp-elenco carta" aria-label="${cfg.aria}"><ul class="elenco">${cfg.voci.map(g => `<li><button class="voce imp-voce" data-imp="${g.id}" style="grid-template-columns:1fr auto">
      <span><span class="nome">${g.nome}</span><span class="dettaglio" style="display:block">${g.sub}</span></span><span class="debole" aria-hidden="true">›</span></button></li>`).join("")}</ul></nav>
    <section class="imp-pagina" id="imp-pagina" aria-label="${cfg.indietro}"></section></div>`, { titolo: cfg.titolo, stato: cfg.stato });
  contenuto.querySelectorAll("[data-imp]").forEach(b => b.addEventListener("click", () => {
    const g = cfg.voci.find(x => x.id === b.dataset.imp);
    if (g && g.vai) g.vai(); else apriPannello(cfg, b.dataset.imp);          // una voce con `vai` porta a un'altra pagina (Squadra e Altro)
  }));
  if (cfg.scelto) apriPannello(cfg, cfg.scelto, false);
}

function apriPannello(cfg, id, sposta = true) {
  const g = cfg.voci.find(x => x.id === id);
  const radice = $(".imp"), pagina = $("#imp-pagina");
  if (!g || !radice || !pagina) return;
  cfg.ricorda(id);
  radice.dataset.aperto = "1";
  contenuto.querySelectorAll("[data-imp]").forEach(b => {
    b.classList.toggle("attiva", b.dataset.imp === id);
    if (b.dataset.imp === id) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
  });
  pagina.innerHTML = `<button class="bottone secondario imp-indietro" id="imp-indietro" type="button">${ICONA_INDIETRO}${cfg.indietro}</button>
    <h2 class="imp-titolo" id="imp-titolo" tabindex="-1">${g.nome}</h2><div id="imp-corpo">${cfg.corpi[id]()}</div>`;
  $("#imp-indietro").addEventListener("click", () => {
    radice.dataset.aperto = "0"; window.scrollTo(0, 0); const b = $(`[data-imp="${id}"]`); if (b) b.focus();
    if (cfg.lista) cfg.lista();
  });
  if (cfg.indirizzo) cfg.indirizzo(id, sposta);
  cfg.collega[id]();
  if (sposta) { window.scrollTo(0, 0); if (!impLargo()) $("#imp-titolo").focus({ preventScroll: true }); }
}

// ---------------------------------------------------------------- i gruppi
// Una voce che apre una pagina legale (in una scheda nuova, nella lingua scelta).
const voceLegale = (pagina, chiave) => `<li><a class="voce voce-link" href="/${pagina}${queryLingua()}" target="_blank" rel="noopener" style="grid-template-columns:1fr auto">
  <span class="nome">${t(chiave)}</span><span class="debole" aria-hidden="true">›</span></a></li>`;

// Il codice sorgente (licenza AGPL-3.0): solo un indirizzo https dichiarato dal server (FANTA_SORGENTE, campo `sorgente` di /api/stato).
const voceSorgente = () => {
  const s = stato.info && stato.info.sorgente;
  return typeof s === "string" && /^https:\/\/[^\s"'<>]+$/.test(s) ? `<li><a class="voce voce-link" href="${esc(s)}" target="_blank" rel="noopener" style="grid-template-columns:1fr auto">
  <span class="nome">${t("info.sorgente")}</span><span class="debole" aria-hidden="true">›</span></a></li>` : "";
};

// Novità, in fondo a Informazioni (dal 12/11/2026, #615: non sono più una voce di Altro né un banner in Oggi): le ultime
// NOVITA_VISIBILI versioni; le altre (sono centinaia) solo a richiesta, così la pagina resta leggera. Titoli e voci passano da esc().
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
    if (!document.body.contains(dove)) return;                             // nel frattempo si è aperto un altro gruppo
    const carta = v => `<div class="novita-versione"><h4 class="novita-titolo">${esc(v.titolo)}</h4>
        <div class="debole piccolo">${t("novita.versione", { v: esc(v.versione) })} · ${dataNovita(v.data)}</div>
        <ul class="novita-voci">${(v.voci || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    const resto = elenco.length - NOVITA_VISIBILI;
    // una colonna da leggere: righe di testo al massimo 70 caratteri anche sul PC (spec grafica B, C12)
    dove.innerHTML = `<div class="novita-pagina">${elenco.slice(0, NOVITA_VISIBILI).map(carta).join("")}
      ${resto > 0 ? `<div class="pulsanti" id="novita-altre-riga"><button class="bottone secondario" id="novita-altre" type="button">${tp("novita.precedenti", resto)}</button></div>` : ""}</div>`;
    const altre = $("#novita-altre");
    if (altre) altre.addEventListener("click", () => { $("#novita-altre-riga").outerHTML = elenco.slice(NOVITA_VISIBILI).map(carta).join(""); });
  } catch (e) { if (document.body.contains(dove)) dove.innerHTML = errore(e); }
}

const CORPI_IMP = {
  account: () => schedaAccount(),
  aspetto: () => schedaAspetto(),
  avvisi: () => `<div class="carta" id="avvisi-telefono"><div class="caricamento" style="padding:8px 0">${t("comune.carico")}</div></div>`,
  informazioni: () => {
    const v = stato.info && stato.info.versione;
    return `<div class="carta"><ul class="elenco">${voceLegale("privacy", "legale.privacy")}${voceLegale("termini", "legale.termini")}${voceLegale("crediti", "legale.crediti")}${voceSorgente()}</ul>
      <div class="riga"><span>${t("info.versione")}</span><b>${v ? esc(v) : "–"}</b></div></div>
      <div class="carta"><h3>${t("info.novita")}</h3><div id="novita-elenco"><div class="caricamento">${t("novita.carico")}</div></div></div>`;
  },
  avanzate: () => `<div class="carta"><h3>${t("av.stato")}</h3>
      <div class="debole piccolo">${t("av.stato_spiega")}</div>
      <div class="pulsanti"><button class="bottone secondario" id="apri-stato-dati" type="button">${t("av.apri_stato")}</button></div></div>
    ${schedaAmministratore()}`,
};

const COLLEGA_IMP = {
  account: () => collegaAccount(),
  aspetto: () => collegaAspetto(),
  avvisi: () => avvisiTelefono(),
  informazioni: () => mostraNovita($("#novita-elenco")),
  avanzate: () => {
    const b = $("#apri-stato-dati"); if (b) b.addEventListener("click", apriStatoDati);
    collegaAmministratore();
  },
};

$("#bottone-impostazioni").addEventListener("click", () => vai("impostazioni", undefined, { focoTitolo: true }));
