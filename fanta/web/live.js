/* Risultati in diretta: parte che decide (testi, punteggio, quando richiedere ancora). Niente DOM qui: si prova con node.
   I dati arrivano da GET /api/live (contratto in docs/LIVE.md). */
(function (radice) {
  "use strict";
  const tx = (chiave, italiano, valori) => (typeof t === "function" ? t(chiave, valori) : italiano);          // senza testi.js (prove in node): italiano
  const IN_GIOCO = ["primo_tempo", "intervallo", "secondo_tempo", "in_corso"];
  const CON_PUNTEGGIO = [...IN_GIOCO, "finita", "sospesa"];
  const PRIMA_MIN = 10, FINE_MIN = 130;           // come il server: da 10 minuti prima a 20 dopo la fine stimata (110)

  const TIPI = ["gol", "rigore", "autogol", "rigore_sbagliato", "rosso"];   // i gialli non si mostrano mai (anche se un server vecchio li manda)
  const chiave = p => `${p.casa}|${p.trasferta}`;
  const NOTI = [...CON_PUNTEGGIO, "da_giocare", "rinviata"];
  const conGol = p => p.gol_casa != null && p.gol_trasferta != null;
  // Uno stato mai visto (la fonte ne ha inventato uno nuovo) con un punteggio vale «in corso», come dice docs/LIVE.md.
  const sconosciuto = p => !NOTI.includes(p.stato) && conGol(p);
  const statoDi = p => sconosciuto(p) ? "in_corso" : p.stato;
  const inDiretta = p => IN_GIOCO.includes(statoDi(p));
  const haPunteggio = p => CON_PUNTEGGIO.includes(statoDi(p)) && conGol(p);
  const punteggio = p => haPunteggio(p) ? `${p.gol_casa} – ${p.gol_trasferta}` : null;

  // Cosa scrivere al posto dell'orario. `testo` null = lasciare l'orario di inizio.
  function etichetta(p) {
    switch (statoDi(p)) {
      case "primo_tempo": case "secondo_tempo": case "in_corso": return { live: true, testo: "LIVE", minuto: p.minuto || (sconosciuto(p) ? tx("live.aggiornamento", "In aggiornamento") : "") };
      case "intervallo": return { live: true, testo: "LIVE", minuto: tx("live.intervallo", "Intervallo") };
      case "finita": return { live: false, testo: tx("live.finita", "Finita"), minuto: "" };
      case "rinviata": return { live: false, testo: tx("live.rinviata", "Rinviata"), minuto: "" };
      case "sospesa": return { live: false, testo: tx("live.sospesa", "Sospesa"), minuto: "" };
      default: return { live: false, testo: null, minuto: "" };
    }
  }

  function dataLocale(s) {
    const d = new Date(String(s || "").replace(" ", "T"));
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const inFinestra = (p, adesso) => {
    const i = dataLocale(p.data);
    return !!i && adesso >= new Date(i.getTime() - PRIMA_MIN * 6e4) && adesso <= new Date(i.getTime() + FINE_MIN * 6e4);
  };

  // Tra quanti millisecondi richiedere ancora, oppure null = basta (niente in corso e niente in arrivo).
  // Con partite in gioco ogni 45 secondi; poco prima dell'inizio (e finché la fonte non dice «finita») ogni minuto;
  // altrimenti si aspetta la prossima partita di oggi.
  function prossimoControllo(live, adesso) {
    const partite = (live && live.partite) || [];
    if (partite.some(inDiretta)) return 45000;
    if (partite.some(p => p.stato === "da_giocare" && inFinestra(p, adesso))) return 60000;
    // niente in corso: ricontrollare poco prima della prossima partita di oggi (se mancano meno di 6 ore)
    const attese = partite.filter(p => p.stato === "da_giocare").map(p => dataLocale(p.data))
      .filter(d => d && d > adesso).map(d => d.getTime() - PRIMA_MIN * 6e4 - adesso.getTime());
    const prima = Math.min(...attese);
    return Number.isFinite(prima) && prima <= 6 * 36e5 ? Math.max(prima, 60000) : null;
  }

  // Chiavi delle partite dove il punteggio è salito rispetto all'ultima lettura (`prec` = {chiave: [casa, trasferta]}). Aggiorna `prec`.
  function gol(prec, live) {
    const nuovi = [];
    for (const p of (live && live.partite) || []) {
      if (!haPunteggio(p)) continue;
      const k = chiave(p), v = prec[k];
      if (v && (p.gol_casa > v[0] || p.gol_trasferta > v[1])) nuovi.push(k);
      prec[k] = [p.gol_casa, p.gol_trasferta];
    }
    return nuovi;
  }

  const normalizza = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  // «M. Thuram» riguarda un mio giocatore se il suo cognome (prima parola del nome nell'app) compare nel nome dell'evento
  function eMio(chi, titolari) {
    const parole = normalizza(chi).split(/[^a-z']+/).filter(Boolean);
    return (titolari || []).some(t => {
      const cognome = normalizza(t.nome).split(/[^a-z']+/).filter(Boolean)[0];
      return !!cognome && cognome.length > 3 && parole.includes(cognome);
    });
  }

  // Gli eventi da mostrare: tutti (gol con assist, autogol, rigori, rossi), sempre, in gioco e a partita finita.
  function eventiVisibili(p) {
    return (p.eventi || []).filter(e => TIPI.includes(e.tipo));
  }

  // «6' Varela (rig.)», «33' Pobega (ass. Ferguson)», «58' Lucchesi»: il testo di una riga.
  function testoEvento(e) {
    const nota = e.tipo === "autogol" ? ` (${tx("live.autogol", "autogol")})` : e.tipo === "rigore" ? ` (${tx("live.rigore", "rig.")})` : e.tipo === "rigore_sbagliato" ? ` (${tx("live.rigore_sbagliato", "rig. sbagliato")})`
      : e.assist ? ` (${tx("live.assist", "ass. {nome}", { nome: e.assist }).replace("{nome}", e.assist)})` : "";
    return `${e.minuto} ${e.chi}${nota}`.trim();
  }

  const api = { chiave, inDiretta, haPunteggio, punteggio, etichetta, inFinestra, prossimoControllo, gol, eMio, eventiVisibili, testoEvento };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else radice.LiveSchieraxi = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
