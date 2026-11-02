"use strict";
// «Da fare» in Oggi: le cose da sbrigare, calcolate dal server (campo da_fare di /api/oggi, vedi docs/API.md).
// Ogni riga ha UN pulsante che porta alla schermata giusta. Usa le funzioni di app.js (esc, vai, apriGiocatore...), caricato dopo
// questo file: si chiamano solo a pagina pronta. Tutti i testi del server passano da esc().
const DF_VISIBILI = 4;                                   // le altre stanno in «Altre cose da fare»
const DF_URGENTE = 1;

function dfRiga(v, i) {
  const urgente = v.priorita === DF_URGENTE;
  return `<li class="df-riga${urgente ? " urgente" : ""}">
    <span class="df-testo">${urgente ? `<span class="df-etichetta">${t("df.urgente")}</span> ` : ""}${esc(traduciErrore(v.testo))}</span>
    <button class="bottone ${urgente ? "" : "secondario"} df-azione" data-df="${i}">${esc(v.azione ? traduciErrore(v.azione) : t("df.apri"))}</button></li>`;
}

function cardDaFare(voci) {
  if (!Array.isArray(voci)) return "";                  // server vecchio: nessun campo, nessuna card
  const valide = voci.filter(v => v && typeof v.testo === "string");
  if (!valide.length) return `<div class="carta df-vuoto" role="status">✓ <b>${t("df.tutto_posto_mister")}</b> ${t("df.non_niente_sbrigare")}</div>`;
  const primi = valide.slice(0, DF_VISIBILI), altri = valide.slice(DF_VISIBILI);
  return `<div class="carta df-carta"><h2>${t("df.da_fare")} <span class="df-conto">${valide.length}</span></h2>
    <ul class="df-elenco">${primi.map((v, i) => dfRiga(v, i)).join("")}</ul>
    ${altri.length ? `<details><summary>${tp("df.altre", altri.length)}</summary>
      <ul class="df-elenco">${altri.map((v, i) => dfRiga(v, i + DF_VISIBILI)).join("")}</ul></details>` : ""}</div>`;
}

// Dove si trova, dentro Squadra o Altro, il punto indicato dalla voce (se la schermata cambia e non si trova, si resta in cima a Lega).
const DF_PUNTI = { rose: ["#testo-rose", "#file-rose"], diario: ["#apri-diario"] };
function dfPortaA(sezione) {
  const cerca = () => {
    for (const sel of DF_PUNTI[sezione] || []) {
      const el = document.querySelector(sel);
      if (el) { (el.closest(".carta") || el).scrollIntoView({ block: "start", behavior: "smooth" }); return true; }
    }
    return false;
  };
  let prove = 0;
  const riprova = () => { if (!cerca() && ++prove < 8) setTimeout(riprova, 250); };      // Lega si disegna dopo aver caricato i dati
  setTimeout(riprova, 250);
}

function dfApri(v) {
  const d = v.destinazione || {};
  if (v.tipo === "primo_avvio") { if (typeof apriPrimoAvvio === "function") apriPrimoAvvio(); return; }
  // «I dati non si aggiornano da N giorni» → «Controlla»: direttamente Stato dei dati (sotto Impostazioni > Avanzate), non la pagina che lo contiene
  if (v.id === "dati-vecchi" && typeof apriStatoDati === "function") { vai("impostazioni", "avanzate"); apriStatoDati(); return; }
  if (v.tipo === "diario" && Number.isInteger(v.giornata) && typeof schieraDaOggi === "function") { schieraDaOggi(v.giornata); return; }
  if (v.tipo === "diario" && typeof apriDiario === "function") { apriDiario(); return; }
  if (d.giocatore && d.scheda === "mercato") { apriGiocatore(Number(d.giocatore)); return; }
  const DF_IMP = { avanzate: "avanzate" };                               // sezioni che stanno in Impostazioni
  if (d.scheda === "impostazioni" || DF_IMP[d.sezione]) { vai("impostazioni", DF_IMP[d.sezione] || d.sezione); return; }
  const scheda = SCHEDA_DI(d.scheda) ? d.scheda : "lega";            // «mercato», «scambi» e «lega» sono pagine dentro Squadra e Altro
  const VOCE_LEGA = { rose: "importa", diario: "diario", regole: "regole", crediti: "crediti", stagione: "stagione", movimenti: "movimenti", squadre: "squadre" };     // la voce di Lega che si apre da sola
  if (scheda === "lega" && VOCE_LEGA[d.sezione]) stato.legaTorna = VOCE_LEGA[d.sezione];
  vai(scheda);
  if (scheda === "lega" && d.sezione) dfPortaA(d.sezione);
}

function collegaDaFare(voci) {
  const valide = (Array.isArray(voci) ? voci : []).filter(v => v && typeof v.testo === "string");
  document.querySelectorAll("[data-df]").forEach(b => b.addEventListener("click", () => {
    const v = valide[Number(b.dataset.df)];
    if (v) dfApri(v);
  }));
}
