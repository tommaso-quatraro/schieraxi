"use strict";
// Le decisioni in cima alla Formazione (#616): al massimo due righe, ognuna con la sua azione, scelte dalla lista che calcola il
// server (campo da_fare di /api/oggi, vedi docs/API.md). Prima erano la sezione «Da fare» di Oggi, con anche le righe che non
// chiedevano niente. Usa le funzioni di app.js (esc, vai, apriGiocatore...), caricato dopo questo file: si chiamano solo a pagina
// pronta. Tutti i testi del server passano da esc().
const DF_DECISIONI = 2;
const DF_URGENTE = 1;

// Cambi consigliati («mercato») e Scambi sono stati tolti dalla web il 12/11/2026 (#615); il server manda ancora le sue righe come
// prima (le usa l'iPhone). Una riga che resta ma portava lì (il reparto scoperto: «Cerca un rimpiazzo») sulla web apre la rosa della
// propria squadra, e il pulsante lo dice.
const DF_SCHEDE_TOLTE = ["mercato", "scambi"];
const dfAllaRosa = v => DF_SCHEDE_TOLTE.includes((v.destinazione || {}).scheda);
// «La consigliata è cambiata da quando l'hai salvata» (id «consigliata:N»): il suo pulsante prende la consigliata di adesso.
const dfConsigliataCambiata = v => v.tipo === "formazione" && String(v.id || "").startsWith("consigliata:");

// Una riga è una decisione vera se chiede di fare qualcosa. Sulla web non lo sono:
// - i due consigli delle funzioni tolte (il cambio con uno svincolato, lo scambio);
// - un titolare incerto senza un cambio da fare («X resta titolare: se non gioca entra Y»): è un'informazione, e sta sul giocatore
//   (il colore di «gioca N%») e nella sua scheda;
// - «la formazione si chiude e non l'hai salvata»: qui il salvataggio è automatico e, se non tocchi niente, vale la consigliata; una
//   formazione salvata che non vale più la dice la riga dello stato sotto il campo;
// - «dimmi se hai schierato la consigliata»: lo dice la spunta «L'ho messa», e la giornata finita ha «Com'è andata» in testa.
function dfVera(v) {
  if (!v || typeof v.testo !== "string") return false;
  if (["svincolato", "scambio", "diario"].includes(v.tipo)) return false;
  if (v.tipo === "dubbio") return !!v.alternativa;
  if (v.tipo === "formazione") return dfConsigliataCambiata(v);
  return true;
}
// Le decisioni da mostrare: al massimo due. Prima le righe urgenti, e fra loro prima quelle con un'azione vera; poi le non urgenti
// con un'azione vera; poi il resto. Dentro ogni gruppo resta l'ordine del server. Il reparto scoperto («Vedi la rosa», che porta
// solo a guardare la rosa) prende al massimo un posto: due righe sue nascondevano «rose da aggiornare», un cambio da fare o la
// consigliata cambiata; ma un «nessun portiere» urgente non resta più dietro a due righe meno importanti. `vale(v)`: la riga ha
// ancora senso con la formazione che è in pagina (un cambio già fatto non si propone più).
function dfDecisioni(voci, vale = () => true) {
  const vere = (Array.isArray(voci) ? voci : []).filter(v => dfVera(v) && vale(v));
  const scoperto = v => v.tipo === "copertura", urgente = v => v.priorita === DF_URGENTE;
  const gruppi = [v => urgente(v) && !scoperto(v), v => urgente(v) && scoperto(v), v => !urgente(v) && !scoperto(v), v => !urgente(v) && scoperto(v)];
  const ordinate = gruppi.flatMap(g => vere.filter(g));
  const unoScoperto = ordinate.find(scoperto);
  return ordinate.filter(v => !scoperto(v) || v === unoScoperto).slice(0, DF_DECISIONI);
}
// La decisione, al tocco, scrive sul server (un cambio di titolare, «Usa la consigliata»): sulla copia del telefono resta spenta.
const dfScrive = v => (v.tipo === "dubbio" && !!v.alternativa) || dfConsigliataCambiata(v);

// Una decisione: il testo del server, la sua azione a destra nel colore delle azioni (grafica B, spec C9: niente pulsanti a contorno
// in fila; quella urgente la dice la parola «Urgente»). `nota` (già pronta per l'HTML): i punti attesi in più del cambio proposto.
// `sola`: la schermata è di sola lettura, i pulsanti che scrivono sono spenti (restano al loro posto).
function dfRiga(v, i, nota = "", sola = false) {
  const urgente = v.priorita === DF_URGENTE;
  const azione = dfAllaRosa(v) ? t("lega.vedi_rosa") : dfConsigliataCambiata(v) ? t("formazione.usa_consigliata") : esc(v.azione ? testoDi(v, "azione") : t("df.apri"));
  return `<li class="df-riga${urgente ? " urgente" : ""}">
    <span class="df-testo">${urgente ? `<span class="df-etichetta">${t("df.urgente")}</span> ` : ""}${esc(testoDi(v))}${nota ? ` <b class="df-nota">${nota}</b>` : ""}</span>
    <button class="azione-testo df-azione" type="button" data-df="${i}"${dfScrive(v) ? ` data-scrive${sola ? " disabled" : ""}` : ""}>${azione}</button></li>`;
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

// L'azione di una decisione che porta in un'altra schermata (le rose, le impostazioni, il primo avvio). Il cambio di un titolare e
// «Usa la consigliata» li fa la Formazione, che ha la formazione in pagina (mostraFormazione in app.js).
function dfApri(v) {
  const d = v.destinazione || {};
  if (v.tipo === "primo_avvio") { if (typeof apriPrimoAvvio === "function") apriPrimoAvvio(); return; }
  // «I dati non si aggiornano da N giorni» → «Controlla»: direttamente Stato dei dati (sotto Impostazioni > Avanzate), non la pagina che lo contiene
  if (v.id === "dati-vecchi" && typeof apriStatoDati === "function") { vai("impostazioni", "avanzate"); apriStatoDati(); return; }
  if (dfAllaRosa(v)) { stato.legaTorna = null; stato.rosaTorna = ""; vai("squadra"); return; }      // la rosa della mia squadra (rosa senza nome)
  const DF_IMP = { avanzate: "avanzate" };                               // sezioni che stanno in Impostazioni
  if (d.scheda === "impostazioni" || DF_IMP[d.sezione]) { vai("impostazioni", DF_IMP[d.sezione] || d.sezione); return; }
  const scheda = SCHEDA_DI(d.scheda) ? d.scheda : "lega";            // «lega» è il nome vecchio delle voci di Squadra e Altro
  const VOCE_LEGA = { rose: "importa", diario: "diario", regole: "regole", squadre: "squadre" };     // la voce di Lega che si apre da sola
  if (scheda === "lega" && VOCE_LEGA[d.sezione]) stato.legaTorna = VOCE_LEGA[d.sezione];
  vai(scheda);
  if (scheda === "lega" && d.sezione) dfPortaA(d.sezione);
}
