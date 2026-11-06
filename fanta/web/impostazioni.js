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
    titolo: t("shell.impostazioni"), stato: false };
  stato.pannelli = cfg;
  montaPannelli(cfg);
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
  $("#imp-indietro").addEventListener("click", () => { radice.dataset.aperto = "0"; window.scrollTo(0, 0); const b = $(`[data-imp="${id}"]`); if (b) b.focus(); });
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

const CORPI_IMP = {
  account: () => schedaAccount(),
  aspetto: () => schedaAspetto(),
  avvisi: () => `<div class="carta" id="avvisi-telefono"><div class="caricamento" style="padding:8px 0">${t("comune.carico")}</div></div>`,
  informazioni: () => {
    const v = stato.info && stato.info.versione;
    return `<div class="carta"><ul class="elenco">${voceLegale("privacy", "legale.privacy")}${voceLegale("termini", "legale.termini")}${voceLegale("crediti", "legale.crediti")}${voceSorgente()}</ul>
      <div class="riga"><span>${t("info.versione")}</span><b>${v ? esc(v) : "–"}</b></div></div>`;
  },
  avanzate: () => `<div class="carta"><h3>${t("av.funzioni")}</h3>
      <label class="interruttore"><span>${t("av.mostra_tutte")}</span><input type="checkbox" id="mostra-tutte" ${stato.funzioni && stato.funzioni.mostraTutte ? "checked" : ""}></label>
      <div class="debole piccolo">${t("av.mostra_tutte_spiega")}</div></div>
    <div class="carta"><h3>${t("av.stato")}</h3>
      <div class="debole piccolo">${t("av.stato_spiega")}</div>
      <div class="pulsanti"><button class="bottone secondario" id="apri-stato-dati" type="button">${t("av.apri_stato")}</button></div></div>
    ${schedaAmministratore()}`,
};

const COLLEGA_IMP = {
  account: () => collegaAccount(),
  aspetto: () => collegaAspetto(),
  avvisi: () => avvisiTelefono(),
  informazioni: () => {},
  avanzate: () => {
    const mt = $("#mostra-tutte");
    if (mt) mt.addEventListener("change", async () => {
      mt.disabled = true;
      try {
        const r = await api("/api/funzioni", { method: "PUT", body: JSON.stringify({ mostra_tutte: mt.checked }) });
        stato.funzioni = r && r.funzioni ? { funzioni: r.funzioni, mostraTutte: !!r.mostra_tutte } : null;
        svuotaCache();
        avviso(t(mt.checked ? "av.ora_tutte" : "av.ora_essenziale"));
      } catch (e) { mt.checked = !mt.checked; avviso(e.message, 5000); }
      mt.disabled = false;
    });
    const b = $("#apri-stato-dati"); if (b) b.addEventListener("click", apriStatoDati);
    collegaAmministratore();
  },
};

$("#bottone-impostazioni").addEventListener("click", () => vai("impostazioni"));
