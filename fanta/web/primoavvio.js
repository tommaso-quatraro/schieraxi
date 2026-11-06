"use strict";
// Primo avvio: UN solo percorso breve (le rose o gli esempi; la squadra con le regole standard; i tempi della lega; fatto).
// Ogni passo si può saltare.
// A che punto sei resta sul server (GET e PUT /api/primo-avvio, vedi docs/API.md): si riprende da un altro dispositivo e si riapre
// quando vuoi da Impostazioni > Informazioni. Si apre da solo una volta sola, se non hai ancora le rose e non hai già chiuso la vecchia procedura.
// Usa le funzioni di app.js (api, esc, avviso, apriFoglio...), caricato dopo questo file: si chiamano solo a pagina pronta.
const PA_PASSI = ["rose", "squadra", "tempi"];
const PA_NOMI = { rose: t("pav.n_rose"), squadra: t("pav.n_squadra"), tempi: t("pav.n_tempi") };
// «Quando si chiude la formazione»: le scelte più comuni (minuti prima della prima partita); un valore diverso si aggiunge da solo
const PA_SCADENZE = [0, 5, 10, 15, 30, 60];
const pa = { stato: { fatti: [], saltati: [], chiuso: false }, passo: null };

const paFatto = p => pa.stato.fatti.includes(p);
const paSaltato = p => pa.stato.saltati.includes(p);

async function paSalva(campi) {
  try {
    const r = await api("/api/primo-avvio", { method: "PUT", body: JSON.stringify(campi) });
    if (r && r.primo_avvio) pa.stato = r.primo_avvio;
  } catch (e) {
    avviso(t("pav.non_sono_riuscito"));
    if (campi.fatti) pa.stato.fatti = campi.fatti;
    if (campi.saltati) pa.stato.saltati = campi.saltati;
  }
}
const paSegnaFatto = p => paSalva({ fatti: [...new Set([...pa.stato.fatti, p])], saltati: pa.stato.saltati.filter(x => x !== p) });
const paSalta = p => paSalva({ saltati: [...new Set([...pa.stato.saltati, p])] });

// Cose che si vedono già fatte: il passo si segna da solo.
async function paRileva() {
  await caricaInfo();
  await caricaSquadre(true);
  const gia = [];
  if ((stato.squadre || []).length) gia.push("rose");
  if (miaSquadra()) gia.push("squadra");
  const nuovi = gia.filter(p => !paFatto(p));
  if (nuovi.length || !pa.stato.fatti.includes("accesso")) {
    await paSalva({ fatti: [...new Set([...pa.stato.fatti, "server", "accesso", ...gia])], saltati: pa.stato.saltati.filter(p => !gia.includes(p)) });
  }
}

async function apriPrimoAvvio() {
  try {
    const r = await api("/api/primo-avvio");
    pa.stato = r.primo_avvio || { fatti: [], saltati: [], chiuso: false };
  } catch (e) { avviso(e.message); return; }
  await paRileva();
  pa.passo = PA_PASSI.find(p => !paFatto(p) && !paSaltato(p)) || PA_PASSI.find(p => !paFatto(p)) || null;
  paDisegna();
}

function paProgresso() {
  return `<ol class="pa-passi" aria-label="${t("pav.passi_del_primo")}">${PA_PASSI.map(p => {
    const stato_ = paFatto(p) ? "fatto" : paSaltato(p) ? "saltato" : "";
    const etichetta = paFatto(p) ? t("pav.fatto_par") : paSaltato(p) ? t("pav.saltato_par") : "";
    return `<li><button class="pa-passo ${stato_} ${p === pa.passo ? "attuale" : ""}" data-pa-passo="${p}" ${p === pa.passo ? 'aria-current="step"' : ""}>${esc(PA_NOMI[p])}${etichetta}</button></li>`;
  }).join("")}</ol>`;
}

function paDisegna() {
  const p = pa.passo;
  if (!p) { paFine(); return; }
  const corpo = PA_SCHERMATE[p]();
  apriFoglio(`<h2 class="pa-capo">${t("pav.primo_avvio")}</h2>${paProgresso()}
    <h3 class="pa-titolo">${esc(PA_NOMI[p])}</h3>${corpo.html}
    <div id="pa-msg" role="alert"></div>
    <div class="pulsanti">${corpo.principale ? `<button class="bottone" id="pa-avanti">${esc(corpo.principale)}</button>` : ""}
      <button class="bottone secondario" id="pa-salta">${t(corpo.principale ? "pav.salta" : "onb.avanti")}</button></div>`);
  document.querySelectorAll("[data-pa-passo]").forEach(b => b.addEventListener("click", () => { pa.passo = b.dataset.paPasso; paDisegna(); }));
  $("#pa-salta").addEventListener("click", async () => { if (corpo.principale && !paFatto(p)) await paSalta(p); paProssimo(); });
  const avanti = $("#pa-avanti");
  if (avanti) avanti.addEventListener("click", async () => {
    avanti.disabled = true; avanti.setAttribute("aria-busy", "true");
    try { if (await corpo.esegui()) { await paSegnaFatto(p); paProssimo(); } }
    catch (e) { paErrore(e); }
    finally { avanti.disabled = false; avanti.removeAttribute("aria-busy"); }
  });
  if (corpo.dopo) corpo.dopo();
}

function paErrore(e) { const d = $("#pa-msg"); if (d) d.innerHTML = `<div class="errore">${esc(e.message || e)}</div>`; }

// Il passo dopo quello attuale: il primo non fatto né saltato che viene dopo; se non c'è, un passo ancora aperto
// diverso dall'attuale; se non ce n'è, null (si chiude). Mai tornare al passo attuale: era il bug che bloccava «Avanti».
function paPassoDopo(passi, attuale, fatti, saltati) {
  const aperto = p => !fatti.includes(p) && !saltati.includes(p);
  return passi.slice(passi.indexOf(attuale) + 1).find(aperto)
    || passi.find(p => p !== attuale && aperto(p)) || null;
}

function paProssimo() {
  pa.passo = paPassoDopo(PA_PASSI, pa.passo, pa.stato.fatti, pa.stato.saltati);
  paDisegna();
}

const paAvvisiPossibili = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

function paFine() {
  const saltati = PA_PASSI.filter(p => !paFatto(p));
  apriFoglio(`<h2 class="pa-capo">${t("pav.tutto_pronto_mister")}</h2>${paProgresso()}
    <p class="debole">${saltati.length ? t("pav.hai_saltato", { nomi: saltati.map(p => esc(PA_NOMI[p])).join(", ") }) : t("pav.hai_finito")}</p>
    <p class="debole piccolo">${t("pav.il_resto")}</p>
    <div id="pa-msg" role="alert"></div>
    <div class="pulsanti"><button class="bottone" id="pa-chiudi">${t("pav.vai_oggi")}</button>
      ${paAvvisiPossibili() ? `<button class="bottone secondario" id="pa-avvisi">${t("onb.attiva_gli_avvisi_b")}</button>` : ""}</div>`);
  document.querySelectorAll("[data-pa-passo]").forEach(b => b.addEventListener("click", () => { pa.passo = b.dataset.paPasso; paDisegna(); }));
  const avvisi = $("#pa-avvisi");
  if (avvisi) avvisi.addEventListener("click", async () => {
    try {
      if (await Notification.requestPermission() !== "granted") throw new Error(t("pav.permesso_negato_abilita"));
      const { chiave } = await api("/api/push/chiave");
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chiaveInUint8(chiave) });
      await api("/api/push/iscrivi", { method: "POST", body: JSON.stringify(sub.toJSON()) });
      avvisi.remove(); $("#pa-msg").innerHTML = `<div class="onb-verde">${t("onb.avvisi_attivi_questo")}</div>`;
    } catch (e) { paErrore(e); }
  });
  $("#pa-chiudi").addEventListener("click", async () => {
    await paSalva({ chiuso: true });
    if (stato.account) {                                       // la vecchia procedura ricorda com'è finita: resta coerente
      try { await api("/api/onboarding", { method: "PUT", body: JSON.stringify({ stato: saltati.length ? "saltato" : "completato", passo: "avvisi" }) }); } catch { /* non blocca */ }
    }
    svuotaCache(); chiudiFoglio(); vai("oggi");
  });
}

const paAggiornaRose = async () => { svuotaCache(); await Promise.all([caricaInfo(), caricaSquadre()]); };

// Regole standard confermate, ma solo se non ne hai già confermate di tue (con gli account).
async function paRegoleStandard() {
  if (!stato.account) return;
  try {
    const c = (await api("/api/onboarding/controlli")).find(v => v.id === "regole");
    if (c && !c.ok) await api("/api/regole", { method: "PUT", body: JSON.stringify(await api("/api/regole")) });
  } catch { /* le regole si vedono e si cambiano in Impostazioni */ }
}

// Le rose in due passi (anteprima.js): «Controlla le rose» mostra cosa ha capito l'app, con i dubbi e la tua squadra;
// «Conferma e salva» salva tutto insieme. Con la tua squadra scelta qui, anche il passo «La tua squadra» è fatto.
function paAnteprima() {
  const file = $("#pa-file").files[0], testo = $("#pa-testo").value;
  if (!file && !testo.trim()) throw new Error(t("pav.incolla_testo_delle_2"));
  const ingresso = $("#pa-ingresso"), avanti = $("#pa-avanti"), salta = $("#pa-salta");
  const mostra = si => { ingresso.hidden = !si; avanti.hidden = !si; salta.hidden = !si; };
  $("#pa-msg").innerHTML = "";
  mostra(false);
  anteprimaRose($("#pa-anteprima"), file ? { file } : { testo }, {
    annulla: () => { mostra(true); $("#pa-testo").focus(); },
    fatto: async (esito, mia) => {
      await paAggiornaRose();
      // una squadra basta per cominciare: solo un avviso gentile (gli scambi aspettano le rose degli altri)
      if (esito && esito.totale_squadre === 1) avviso(t("srv.una_sola_squadra"), 8000);
      await paSegnaFatto("rose");
      if (mia) { await paRegoleStandard(); stato.squadraVista = null; await paSegnaFatto("squadra"); }
      paProssimo();
    },
  });
}

// Le due domande sui tempi della lega: scadenza della formazione e giornata di Serie A da cui parte la lega.
// Si leggono le regole di adesso e si salvano tutte, cambiando solo questi due valori (le altre restano come sono).
async function paTempiCarica() {
  try {
    const r = await api("/api/regole");
    const sc = $("#pa-scadenza"), pg = $("#pa-prima");
    if (!sc || !pg) return;
    const m = Number(r.scadenza_minuti ?? 0), g = Number(r.prima_giornata_lega ?? 1);
    if (!PA_SCADENZE.includes(m)) sc.insertAdjacentHTML("beforeend", `<option value="${m}">${esc(paScadenzaNome(m))}</option>`);
    sc.value = String(m); pg.value = String(g);
  } catch { /* restano i valori più comuni; si cambiano anche in Altro > Regole */ }
}
const paScadenzaNome = m => (m === 0 ? t("pav.scad_inizio") : tp("pav.scad_minuti", m));

async function paTempiSalva() {
  const r = await api("/api/regole");
  r.scadenza_minuti = Number($("#pa-scadenza").value);
  r.prima_giornata_lega = Number($("#pa-prima").value);
  await api("/api/regole", { method: "PUT", body: JSON.stringify(r) });
  svuotaCache();
  caricaInfo();                    // la testata passa subito alla «Giornata N» della lega (prima restava quella di Serie A fino a ricaricare)
  return true;
}

const PA_SCHERMATE = {
  rose: () => ({
    principale: t("pav.controlla"),
    html: `<div id="pa-ingresso"><p class="debole">${t("pav.incolla_testo_delle")}</p>
      <textarea id="pa-testo" class="campo-testo" placeholder="${t("lega.incolla_qui_testo")}" maxlength="200000" aria-label="${t("pav.testo_delle_rose")}"></textarea>
      <p class="debole piccolo" style="margin:12px 0 0">${t("pav.oppure_file")}</p>
      <div class="pulsanti"><button class="bottone secondario" id="pa-scegli-file" type="button">${t("lega.scegli_file_excel")}</button></div>
      <p class="debole piccolo" id="pa-file-nome" role="status"></p>
      <input id="pa-file" type="file" accept=".xlsx,.xlsm,.csv,.tsv,.txt,text/csv,text/plain,text/tab-separated-values" hidden>
      ${stato.account ? `<div class="onb-blocco"><b>${t("onb.prova_con_una")}</b><p class="debole piccolo">${t("onb.quattro_squadre_inventate")}</p>
        <button class="bottone secondario" id="pa-esempi" type="button">${t("pav.usa_esempi")}</button></div>` : ""}</div>
      <div id="pa-anteprima"></div>`,
    esegui: async () => { paAnteprima(); return false; },        // il passo si segna fatto alla conferma dell'anteprima
    dopo: () => {
      // il pulsante dell'app al posto del controllo del browser (#456), come in Squadra › Aggiorna le rose: scelto il file, si controlla subito
      $("#pa-scegli-file").addEventListener("click", () => $("#pa-file").click());
      $("#pa-file").addEventListener("change", ev => {
        const file = ev.target.files[0];
        $("#pa-file-nome").textContent = file ? t("pav.file_scelto", { nome: file.name }) : "";
        if (file) { try { paAnteprima(); } catch (err) { paErrore(err); } }
      });
      const e = $("#pa-esempi");
      if (e) e.addEventListener("click", async () => {
        e.disabled = true;
        try { await api("/api/onboarding/demo", { method: "POST" }); await paAggiornaRose(); await paSegnaFatto("rose"); pa.passo = "squadra"; paDisegna(); }
        catch (err) { paErrore(err); e.disabled = false; }
      });
    },
  }),
  squadra: () => {
    const squadre = stato.squadre || [];
    if (!squadre.length) return { principale: null, html: `<p class="debole">${t("pav.prima_servono_rose")}</p>` };
    return {
      principale: t("pav.questa_mia"),
      html: `<p class="debole">${t("pav.quale_squadra_tua")}</p>
        <select class="campo-testo" id="pa-squadra" aria-label="${t("lega.tua_squadra")}">${squadre.map(s => `<option value="${esc(s.nome)}" ${s.mia ? "selected" : ""}>${esc(s.nome)}</option>`).join("")}</select>
        <p class="debole piccolo">${t("onb.valori_piu_comuni")}</p><div id="pa-fix"></div>`,
      dopo: paNonRiconosciuti,
      esegui: async () => {
        await api("/api/mia-squadra", { method: "PUT", body: JSON.stringify({ nome: $("#pa-squadra").value }) });
        await paRegoleStandard();
        stato.squadraVista = null; await paAggiornaRose();
        return true;
      },
    };
  },
  tempi: () => ({
    principale: t("pav.tempi_salva"),
    html: `<p class="debole">${t("pav.tempi_spiega")}</p>
      <label class="accesso-campo"><span>${t("pav.scad_domanda")}</span>
        <select class="campo-testo" id="pa-scadenza">${PA_SCADENZE.map(m => `<option value="${m}" ${m === 0 ? "selected" : ""}>${esc(paScadenzaNome(m))}</option>`).join("")}</select></label>
      <label class="accesso-campo"><span>${t("pav.prima_domanda")}</span>
        <select class="campo-testo" id="pa-prima">${Array.from({ length: 38 }, (_, i) => i + 1).map(g => `<option value="${g}" ${g === 1 ? "selected" : ""}>${esc(g === 1 ? t("pav.prima_uno") : t("pav.prima_n", { n: g }))}</option>`).join("")}</select></label>
      <p class="debole piccolo">${t("pav.tempi_dove")}</p>`,
    dopo: paTempiCarica,
    esegui: paTempiSalva,
  }),
};

// Il titolo «Giocatori da sistemare (N)» segue le righe rimaste; quando non ne resta nessuna, il messaggio verde.
function paContaDaSistemare(dove) {
  const rimasti = dove.querySelectorAll("[data-i]").length;
  if (!rimasti) { dove.innerHTML = `<div class="onb-verde">${t("onb.tutti_giocatori_sono")}</div>`; return; }
  const titolo = dove.querySelector("#pa-fix-titolo");
  if (titolo) titolo.textContent = t("pav.da_sistemare", { n: rimasti });
}

// Giocatori che l'importazione non ha riconosciuto: si cerca quello giusto nel listone e si abbina.
async function paNonRiconosciuti() {
  const dove = $("#pa-fix");
  if (!dove) return;
  let dubbi = [];
  try {
    const rose = await Promise.all((stato.squadre || []).map(s => api(`/api/rosa?squadra=${encodeURIComponent(s.nome)}`)));
    dubbi = rose.flatMap(r => r.giocatori.filter(g => g.id === null).map(g => ({ squadra: r.nome, nome: g.nome })));
  } catch { return; }
  if (!dubbi.length) return;
  dove.innerHTML = `<h3 class="pa-titolo" id="pa-fix-titolo">${t("pav.da_sistemare", { n: dubbi.length })}</h3>
    <p class="debole piccolo">${t("onb.non_trovati_nel")}</p>
    ${dubbi.map((d, i) => `<div class="onb-blocco" data-i="${i}"><b>${esc(d.nome)}</b> <span class="debole piccolo">(${esc(d.squadra)})</span>
      <input class="campo-testo" placeholder="${t("onb.cerca_giocatore_giusto")}" aria-label="${t("onb.cerca_per", { nome: esc(d.nome) })}"><span class="pa-sugg"></span></div>`).join("")}`;
  dove.querySelectorAll("[data-i]").forEach(riga => {
    const d = dubbi[Number(riga.dataset.i)], campo = riga.querySelector("input"), sugg = riga.querySelector(".pa-sugg");
    let timer = null;
    campo.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        if (campo.value.trim().length < 2) { sugg.innerHTML = ""; return; }
        try {
          const trovati = await api(`/api/giocatori?q=${encodeURIComponent(campo.value.trim())}&limite=6`);
          sugg.innerHTML = trovati.map(c => `<button type="button" class="chip" data-id="${Number(c.id)}">${esc(c.nome)} · ${esc(c.ruolo)} · ${esc(c.squadra)}</button>`).join("") || `<span class="debole piccolo">${t("onb.nessun_risultato")}</span>`;
          sugg.querySelectorAll("button").forEach(b => b.addEventListener("click", async () => {
            try {
              await api("/api/rose/correggi", { method: "POST", body: JSON.stringify({ squadra: d.squadra, nome: d.nome, id: Number(b.dataset.id) }) });
              riga.remove(); avviso(t("onb.sistemato"));
              paContaDaSistemare(dove);
            } catch (e) { avviso(e.message); }
          }));
        } catch (e) { sugg.textContent = e.message; }
      }, 250);
    });
  });
}

// All'avvio: se non hai ancora le rose e non hai mai iniziato (né il primo avvio né la vecchia procedura), parte da solo
// (una volta: da quel momento il server ricorda che hai cominciato).
async function primoAvvioSeServe() {
  try {
    if ((stato.squadre || []).length) return;
    const r = await api("/api/primo-avvio");
    if (r.primo_avvio) return;
    if (stato.account) {
      const o = await api("/api/onboarding");
      if (o.stato === "completato" || o.stato === "saltato") return;
    }
    await paSalva({ fatti: ["server", "accesso"] });
    apriPrimoAvvio();
  } catch { /* il primo avvio è un di più: l'app funziona lo stesso */ }
}
