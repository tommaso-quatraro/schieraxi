"use strict";
// Importazione delle rose in due passi (piano «Ingresso facile», docs/INGRESSO-FACILE.md; contratto in docs/API.md, «Anteprima delle rose»):
// 1) l'anteprima legge il testo o il file SENZA salvare e dice, squadra per squadra, chi è riconosciuto, chi è da controllare (con le
//    alternative) e chi non è stato trovato; l'utente sceglie i dubbi e la sua squadra;
// 2) «Conferma e salva» manda lo stesso contenuto con le scelte (`correzioni`), `mia_squadra` e If-Match = l'ETag dell'anteprima.
// La usano Impostazioni > Aggiorna le rose (app.js) e il primo avvio (primoavvio.js). Usa api, esc, errore, svuotaCache... di app.js:
// si chiama solo a pagina pronta.

const AR_TOGLI = "togli", AR_CERCA = "cerca";
const arChiave = (squadra, testo) => `${squadra}\u0000${testo}`;
// La scelta di partenza per un dubbio: la proposta del server (se c'è), altrimenti niente.
const arIniziale = g => (g.stato === "da_controllare" && g.id != null ? String(g.id) : "");
// Le squadre tra cui scegliere la propria: quelle lette più quella già scelta che resta com'era (si aggiungono le rose degli altri).
// Funzione pura (provata con node in tests/test_anteprima_rose_web.py).
const nomiMia = r => {
  const nomi = (r.squadre || []).map(s => s.nome);
  return r.mia_squadra && !nomi.includes(r.mia_squadra) ? [r.mia_squadra, ...nomi] : nomi;
};

// Le scelte da mandare con l'importazione: una per ogni dubbio deciso (id = il giocatore giusto, null = togli la riga).
// Funzione pura (provata con node in tests/test_anteprima_rose_web.py).
function arCorrezioni(squadre, scelte) {
  const fuori = [], viste = new Set();
  for (const s of squadre || []) {
    for (const g of s.giocatori || []) {
      if (g.stato === "sicuro") continue;
      const k = arChiave(s.nome, g.testo);
      if (viste.has(k)) continue;
      viste.add(k);
      const v = scelte.has(k) ? scelte.get(k) : arIniziale(g);
      if (v === AR_TOGLI) fuori.push({ squadra: s.nome, testo: g.testo, id: null });
      else if (/^\d+$/.test(v)) fuori.push({ squadra: s.nome, testo: g.testo, id: Number(v) });
    }
  }
  return fuori;
}

// I problemi di una rosa in parole («Manca 1 portiere», «1 attaccante in più»), dai campi strutturati dell'anteprima.
function arProblemi(s) {
  const ruolo = (r, n) => (n === 1 ? NOME_RUOLO_1[r] : NOMI_RUOLO[r] || r).toLowerCase();
  const fuori = [];
  for (const [r, n] of Object.entries(s.mancano || {})) fuori.push(t(n === 1 ? "ar.manca" : "ar.mancano", { n, ruolo: ruolo(r, n) }));
  for (const [r, n] of Object.entries(s.in_piu || {})) fuori.push(t("ar.in_piu", { n, ruolo: ruolo(r, n) }));
  if (s.senza_ruolo) fuori.push(tp("ar.senza_ruolo", s.senza_ruolo));
  return fuori;
}

// Quanti giocatori ha una squadra: «25 giocatori», oppure «1 giocatore su 25» se non sono quelli attesi.
const arConteggio = s => (s.totale === s.attesi ? tp("sd.n_giocatori", s.totale) : tp("ar.n_su", s.totale, { attesi: s.attesi }));

// La squadra di Serie A per esteso (il listone ha la sigla, «JUV» → «Juventus»); se non la conosciamo, com'è.
const arClub = c => {
  const intero = Object.keys(typeof SIGLE === "object" ? SIGLE : {}).find(k => SIGLE[k] === String(c || "").toUpperCase());
  return esc(intero ? intero.replace(/^./, x => x.toUpperCase()) : c || "");
};
const arDescrivi = c => `${esc(c.nome)} · ${esc((NOME_RUOLO_1[c.ruolo] || c.ruolo || "").toLowerCase())} · ${arClub(c.squadra)}`;

/**
 * Mostra l'anteprima delle rose in `dove` e, alla conferma, le salva.
 * sorgente: { testo } oppure { file }. opz: { sostituisci, fatto(esito, mia), annulla() }.
 */
async function anteprimaRose(dove, sorgente, opz = {}) {
  const st = { ris: null, etag: null, scelte: new Map(), trovati: new Map(), mia: null, righe: [] };

  const anteprima = async () => {
    const leggiEtag = e => { st.etag = e; };
    if (sorgente.file) {
      const dati = new FormData(); dati.append("file", sorgente.file);
      return api(`/api/rose/anteprima/file?sostituisci_tutto=${!!opz.sostituisci}`, { method: "POST", body: dati, leggiEtag });
    }
    return api("/api/rose/anteprima", { method: "POST", body: JSON.stringify({ testo: sorgente.testo, sostituisci_tutto: !!opz.sostituisci }), leggiEtag });
  };

  const carica = async messaggio => {
    dove.innerHTML = `<div class="ar-attesa" role="status">${marchio(34, true)}<span>${t("ar.leggo")}</span></div>`;
    try { st.ris = await anteprima(); }
    catch (e) {
      dove.innerHTML = `${errore(e)}<div class="pulsanti"><button class="bottone secondario" type="button" id="ar-indietro">${t("ar.indietro")}</button></div>`;
      $("#ar-indietro", dove).addEventListener("click", () => { dove.innerHTML = ""; if (opz.annulla) opz.annulla(); });
      $("#ar-indietro", dove).focus();
      return;
    }
    if (st.mia === null) st.mia = st.ris.mia_squadra || "";
    if (!nomiMia(st.ris).includes(st.mia)) st.mia = "";
    disegna(messaggio);
  };

  const opzioni = (k, g) => {
    const scelta = st.scelte.has(k) ? st.scelte.get(k) : arIniziale(g);
    const alt = [...(g.alternative || [])];
    const extra = st.trovati.get(k);
    if (extra && !alt.some(a => a.id === extra.id)) alt.push(extra);
    const o = (valore, testo) => `<option value="${esc(valore)}" ${scelta === valore ? "selected" : ""}>${testo}</option>`;
    const vuota = g.stato === "non_trovato" ? t("ar.lascia_cosi") : t("ar.scegli_chi");
    return (g.stato === "non_trovato" || g.id == null ? o("", vuota) : "")
      + alt.map(a => o(String(a.id), arDescrivi(a))).join("")
      + o(AR_CERCA, t("ar.cerco_io")) + o(AR_TOGLI, t("ar.togli"));
  };

  const rigaDubbio = i => {
    const { s, g } = st.righe[i];
    const k = arChiave(s.nome, g.testo);
    const scelta = st.scelte.has(k) ? st.scelte.get(k) : arIniziale(g);
    const cerca = scelta === AR_CERCA || (g.stato === "non_trovato" && scelta === "");
    const etichetta = g.stato === "non_trovato" ? `<span class="etichetta rossa">${t("ar.non_trovato")}</span>` : `<span class="etichetta arancio">${t("ar.da_controllare")}</span>`;
    return `<li class="ar-dubbio ${scelta === AR_TOGLI ? "tolto" : ""}" data-i="${i}">
      <div class="ar-dubbio-testa"><b>«${esc(g.testo)}»</b>${etichetta}</div>
      ${g.avviso ? `<div class="debole piccolo">${esc(testoDi(g, "avviso"))}</div>` : ""}
      <label class="ar-nascosto" for="ar-sel-${i}">${t("ar.chi_e", { nome: esc(g.testo), squadra: esc(s.nome) })}</label>
      <select class="campo-testo ar-scelta" id="ar-sel-${i}">${opzioni(k, g)}</select>
      ${cerca ? `<div class="ar-cerca"><label class="ar-nascosto" for="ar-cerca-${i}">${t("ar.cerca_per", { nome: esc(g.testo) })}</label>
        <input class="campo-testo" type="search" id="ar-cerca-${i}" autocomplete="off" enterkeyhint="search" placeholder="${t("ar.cerca_segnaposto")}">
        <div class="ar-risultati" aria-live="polite"></div></div>` : ""}
    </li>`;
  };

  const disegna = messaggio => {
    const r = st.ris;
    st.righe = [];
    const squadreHtml = r.squadre.map((s, si) => {
      const dubbi = s.giocatori.filter(g => g.stato !== "sicuro")
        .sort((a, b) => (a.stato === "non_trovato") - (b.stato === "non_trovato"));
      const sicuri = s.giocatori.filter(g => g.stato === "sicuro");
      const indici = dubbi.map(g => st.righe.push({ s, g }) - 1);
      const problemi = arProblemi(s);
      const conteggio = arConteggio(s);
      return `<section class="ar-squadra" aria-labelledby="ar-sq-${si}">
        <h4 id="ar-sq-${si}">${esc(s.nome)}${s.nuova ? ` <span class="etichetta neutra">${t("ar.nuova")}</span>` : ""}</h4>
        <div class="debole piccolo">${conteggio}${s.crediti_residui != null ? ` · ${tp("lega.n_crediti", s.crediti_residui)}` : ""}</div>
        ${problemi.length ? `<div class="ar-problemi">${problemi.map(esc).join(" · ")}</div>` : `<div class="ar-ok">${t("ar.rosa_completa")}</div>`}
        ${dubbi.length ? `<ul class="ar-dubbi">${indici.map(rigaDubbio).join("")}</ul>` : ""}
        ${sicuri.length ? `<details class="ar-sicuri"><summary>${tp("ar.riconosciuti", sicuri.length)}</summary>
          <p class="debole piccolo">${sicuri.map(g => esc(g.nome || g.testo)).join(", ")}</p></details>` : ""}
      </section>`;
    }).join("");
    // gli avvisi delle singole squadre si vedono già nella loro carta: in cima solo quelli di tutto il file
    const diSquadra = new Set(r.squadre.flatMap(s => (s.avvisi || []).map(a => `${s.nome}: ${a}`)));
    const avvisi = (r.avvisi || []).map((testo, i) => ({ testo, frase: (r.avvisi_frasi || [])[i] })).filter(a => !diSquadra.has(a.testo));
    const mia = r.squadre.length ? `<fieldset class="ar-mia"><legend>${t("ar.qual_e_tua")}</legend><div class="ar-mia-scelte">
      ${nomiMia(r).map(n => `<label class="chip ${st.mia === n ? "attiva" : ""}"><input type="radio" name="ar-mia" value="${esc(n)}" ${st.mia === n ? "checked" : ""}>${esc(n)}</label>`).join("")}
      </div></fieldset>` : "";
    const differenze = r.differenze && !r.differenze.prima_importazione && !r.differenze.nessuna_differenza
      ? `<details class="ar-differenze"><summary>${t("ar.cosa_cambia")}</summary>${htmlDifferenze(r.differenze)}</details>` : "";
    dove.innerHTML = `<div class="ar">
      <h3 class="ar-titolo" id="ar-titolo" tabindex="-1">${t("ar.controlla")}</h3>
      <p class="ar-riassunto" aria-live="polite">${arRiassuntoScelte(r, st.scelte)}</p>
      ${avvisi.length ? `<div class="attenzione">${avvisi.map(a => esc(traduciFrase(a.frase, a.testo))).join("<br>")}</div>` : ""}
      ${mia}
      <div class="ar-squadre">${squadreHtml}</div>
      ${differenze}
      <div id="ar-msg" role="status"></div>
      <div class="pulsanti"><button class="bottone" type="button" id="ar-salva">${t("ar.conferma")}</button>
        <button class="bottone secondario" type="button" id="ar-annulla">${t("ar.annulla")}</button></div>
    </div>`;
    collega();
    $("#ar-titolo", dove).focus({ preventScroll: false });
    if (messaggio) setTimeout(() => dici(`<div class="attenzione">${esc(messaggio)}</div>`), 100);
  };

  // Il riquadro dei messaggi (#ar-msg) è una regione role="status" che resta in pagina: un lettore di schermo legge ciò che ci
  // viene scritto DOPO, non una regione che nasce già con il suo testo. Per questo nasce vuoto e il messaggio di apertura arriva
  // un attimo dopo. Qui vanno gli avvisi; un errore vero ci entra con il suo role="alert" (errore()).
  const dici = html => { const m = $("#ar-msg", dove); if (m) m.innerHTML = html; };

  const collegaRiga = li => {
    const i = Number(li.dataset.i), { s, g } = st.righe[i], k = arChiave(s.nome, g.testo);
    const sel = $("select", li);
    sel.addEventListener("change", () => {
      st.scelte.set(k, sel.value);
      ridisegnaRiga(i, sel.value === AR_CERCA ? "input" : "select");
    });
    const campo = $("input[type=search]", li), uscita = $(".ar-risultati", li);
    if (!campo) return;
    let timer = null, ultima = 0;
    campo.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = campo.value.trim();
        if (q.length < 2) { uscita.innerHTML = ""; return; }
        const n = ++ultima;
        try {
          const trovati = await api(`/api/giocatori?q=${encodeURIComponent(q)}&limite=6`);
          if (n !== ultima) return;                  // è arrivata prima una ricerca più nuova
          uscita.innerHTML = trovati.length
            ? `<div class="chips">${trovati.map(c => `<button type="button" class="chip" data-id="${Number(c.id)}">${arDescrivi(c)}</button>`).join("")}</div>`
            : `<span class="debole piccolo">${t("onb.nessun_risultato")}</span>`;
          uscita.querySelectorAll("button[data-id]").forEach(b => b.addEventListener("click", () => {
            const c = trovati.find(x => Number(x.id) === Number(b.dataset.id));
            st.trovati.set(k, { id: Number(c.id), nome: c.nome, ruolo: c.ruolo, squadra: c.squadra });
            st.scelte.set(k, String(c.id));
            ridisegnaRiga(i, "select");
          }));
        } catch (e) { if (n === ultima) uscita.textContent = e.message; }
      }, 250);
    });
  };

  const ridisegnaRiga = (i, fuoco) => {
    const riassunto = $(".ar-riassunto", dove);
    if (riassunto) riassunto.innerHTML = arRiassuntoScelte(st.ris, st.scelte);       // i dubbi già decisi non si contano più
    const vecchia = $(`.ar-dubbio[data-i="${i}"]`, dove);
    if (!vecchia) return;
    vecchia.insertAdjacentHTML("afterend", rigaDubbio(i));
    vecchia.remove();
    const nuova = $(`.ar-dubbio[data-i="${i}"]`, dove);
    collegaRiga(nuova);
    const f = fuoco === "input" && $("input[type=search]", nuova) || $("select", nuova);
    if (f) f.focus();
  };

  const collega = () => {
    dove.querySelectorAll(".ar-dubbio").forEach(collegaRiga);
    dove.querySelectorAll('input[name="ar-mia"]').forEach(x => x.addEventListener("change", () => {
      st.mia = x.value;
      dove.querySelectorAll(".ar-mia .chip").forEach(c => c.classList.toggle("attiva", $("input", c).checked));
    }));
    $("#ar-annulla", dove).addEventListener("click", () => { dove.innerHTML = ""; if (opz.annulla) opz.annulla(); });
    $("#ar-salva", dove).addEventListener("click", salva);
  };

  const salva = async () => {
    const b = $("#ar-salva", dove), msg = $("#ar-msg", dove);
    // «lo cerco io» senza aver toccato un risultato: si salverebbe la proposta di prima senza che l'utente lo sappia
    const aMeta = st.righe.findIndex(({ s, g }) => st.scelte.get(arChiave(s.nome, g.testo)) === AR_CERCA);
    if (aMeta >= 0) {
      dici(`<div class="attenzione">${t("ar.cerca_incompleta", { nome: esc(st.righe[aMeta].g.testo) })}</div>`);
      const campo = $(`#ar-cerca-${aMeta}`, dove);
      if (campo) campo.focus();
      return;
    }
    b.disabled = true; b.setAttribute("aria-busy", "true"); msg.innerHTML = "";
    const correzioni = arCorrezioni(st.ris.squadre, st.scelte);
    const mia = st.mia || null;
    const comuni = { method: "POST", ifMatch: st.etag, senzaRicarica: true };
    try {
      let esito;
      if (sorgente.file) {
        const dati = new FormData(); dati.append("file", sorgente.file);
        if (correzioni.length) dati.append("correzioni", JSON.stringify(correzioni));
        if (mia) dati.append("mia_squadra", mia);
        esito = await api(`/api/rose/file?sostituisci_tutto=${!!opz.sostituisci}`, { ...comuni, body: dati });
      } else {
        esito = await api("/api/rose/testo", { ...comuni, body: JSON.stringify({ testo: sorgente.testo, sostituisci_tutto: !!opz.sostituisci,
          ...(correzioni.length ? { correzioni } : {}), ...(mia ? { mia_squadra: mia } : {}) }) });
      }
      svuotaCache();
      if (opz.fatto) await opz.fatto(esito, mia);
    } catch (e) {
      if (e.status === 412) { await carica(t("ar.cambiate")); return; }    // rose cambiate nel frattempo: si rifà l'anteprima, le scelte restano
      if (msg.isConnected) msg.innerHTML = errore(e);
    } finally {
      if (b.isConnected) { b.disabled = false; b.removeAttribute("aria-busy"); }
    }
  };

  await carica();
}

// Il riassunto in cima tiene conto delle scelte già fatte: un dubbio deciso (un giocatore scelto, o «toglilo») non è più da controllare
// né «non trovato»; chi è stato scelto conta tra i riconosciuti. Funzione pura (provata con node in tests/test_anteprima_rose_web.py).
function arRiassuntoScelte(r, scelte) {
  let sistemati = 0, dubbi = 0, nonTrovati = 0;
  for (const s of r.squadre || []) {
    for (const g of s.giocatori || []) {
      if (g.stato === "sicuro") continue;
      const v = scelte.get(arChiave(s.nome, g.testo));
      if (v !== AR_TOGLI && !/^\d+$/.test(v || "")) continue;
      if (g.stato === "non_trovato") nonTrovati++; else dubbi++;
      if (v !== AR_TOGLI) sistemati++;
    }
  }
  return arRiassunto({ ...r, sicuri: (r.sicuri || 0) + sistemati, da_controllare: Math.max(0, (r.da_controllare || 0) - dubbi),
    non_trovati: Math.max(0, (r.non_trovati || 0) - nonTrovati) });
}

function arRiassunto(r) {
  const parti = [tp("ar.riconosciuti", r.sicuri)];
  if (r.da_controllare) parti.push(tp("ar.r_da_controllare", r.da_controllare));
  if (r.non_trovati) parti.push(tp("ar.r_non_trovati", r.non_trovati));
  return `${tp("ar.r_squadre", r.squadre.length)}: ${parti.join(", ")}.${r.da_controllare || r.non_trovati ? ` ${t("ar.r_guarda")}` : ""}`;
}
