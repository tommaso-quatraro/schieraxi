import Foundation

/// Le parole degli indicatori del consiglio di formazione in Stato dei dati (#366), uguali alla web: `cartaConsiglio` di
/// `fanta/web/app.js` e i testi `sd.cons_*` del catalogo comune (`Catalogo+Sd.swift`; `ConsiglioFormazioneTests` prova le frasi composte). Soglie e verdetto
/// («regge») arrivano dal server: qui si scrivono e basta, non si ricalcolano. Per chi legge ci sono le parole, mai le sigle C1-C4.
enum ParoleConsiglio {
    /// I quattro indicatori, nell'ordine della web (sul server C1, C2, C3, C4).
    enum Indicatore: CaseIterable {
        /// Punti in più della consigliata rispetto alla scelta semplice (C1).
        case valore
        /// Cambi della consigliata nelle 24 ore prima della scadenza (C2).
        case stabilita
        /// Titolari che rischiano di non giocare (C3).
        case chiGioca
        /// Scelte strane senza un motivo detto (C4).
        case perche
    }

    static let titolo = Catalogo.Sd.consTitolo
    static let spiega = Catalogo.Sd.consSpiega
    static let nessuna = Catalogo.Sd.consNessuna

    static func formazioni(_ n: Int) -> String { Catalogo.Sd.consFormazioni(n) }

    static func media(giornate n: Int, formazioni f: Int) -> String { Catalogo.Sd.consMedia(n, f: formazioni(f)) }

    /// La riga sotto il titolo: su quante giornate e formazioni è la media, o che non c'è ancora nessuna giornata misurata.
    static func sottotitolo(_ c: StatoDati.Consiglio) -> String {
        let n = c.giornate ?? 0
        return n > 0 ? media(giornate: n, formazioni: c.voci ?? 0) : nessuna
    }

    static func nome(_ indicatore: Indicatore) -> String {
        switch indicatore {
        case .valore: return Catalogo.Sd.consC1
        case .stabilita: return Catalogo.Sd.consC2
        case .chiGioca: return Catalogo.Sd.consC3
        case .perche: return Catalogo.Sd.consC4
        }
    }

    /// Senza verdetto (meno giornate della finestra) conta solo quante ne mancano; con il verdetto vale `regge` del server.
    static func esito(_ indicatore: Indicatore, di c: StatoDati.Consiglio) -> ParoleRegistro.Esito {
        let regge: Bool?
        switch indicatore {
        case .valore: regge = c.regge?.c1
        case .stabilita: regge = c.regge?.c2
        case .chiGioca: regge = c.regge?.c3
        case .perche: regge = c.regge?.c4
        }
        return ParoleRegistro.esito(verdetto: c.verdetto, regge: regge, giornate: c.giornate, finestra: c.finestra)
    }

    /// Sotto il nome: la media e la soglia, come le righe `sd.cons_c*_riga` della web.
    static func dettaglio(_ indicatore: Indicatore, di c: StatoDati.Consiglio) -> String {
        let s = c.soglie
        switch indicatore {
        case .valore:
            let semplice = Catalogo.Sd.consC1Riga(s: ParoleRegistro.cifra(s?.c1), v: punti(c.menoS2))
            guard let schierata = c.menoSchierata else { return semplice }
            return semplice + " · " + Catalogo.Sd.consC1Schierata(w: punti(schierata))
        case .stabilita:
            return Catalogo.Sd.consC2Riga(c: ParoleRegistro.cifra(c.cambi), n: intero(c.cambiSottoSoglia), s: ParoleRegistro.cifra(s?.c2))
        case .chiGioca:
            return Catalogo.Sd.consC3Riga(i: intero(c.improbabili), n: intero(c.conCompagno), s: ParoleRegistro.cifra(s?.c3))
        case .perche:
            return Catalogo.Sd.consC4Riga(s: ParoleRegistro.percento(s?.c4SenzaMotivo), sp: intero(c.spiegate), st: intero(c.storte),
                                          v: ParoleRegistro.percento(c.senzaMotivo))
        }
    }

    /// Punti a giornata con due cifre e il segno, come `segno(x, 2)` della web: «+1,00», «−0,25», «0,00»; «–» se manca.
    static func punti(_ x: Double?) -> String {
        guard let x, x.isFinite else { return "–" }
        return Formato.conSegno(x, cifre: 2)
    }

    /// Un totale com'è, senza separatore delle migliaia (come `String(x)` della web); «–» se manca.
    static func intero(_ n: Int?) -> String {
        n.map(String.init) ?? "–"
    }
}
