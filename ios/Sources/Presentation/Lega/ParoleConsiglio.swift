import Foundation

/// Le parole degli indicatori del consiglio di formazione in Stato dei dati (#366), uguali alla web: `cartaConsiglio` di
/// `fanta/web/app.js` e i testi `sd.cons_*` di `fanta/web/testi.js` (`ConsiglioFormazioneTests` li confronta). Soglie e verdetto
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

    static let titolo = "Consiglio di formazione"
    static let spiega = "Dopo ogni giornata l'app misura la consigliata mostrata prima della scadenza, nei Diari di tutti. "
        + "La scelta semplice è quella di chi non ha l'app: schiera chi ha preso voto la giornata prima e ha la fantamedia più alta."
    static let nessuna = "Ancora nessuna giornata misurata: i numeri arrivano dopo la fine della prima giornata."

    static func formazioni(_ n: Int) -> String {
        Formato.plurale(n, "formazione", "formazioni")
    }

    static func media(giornate n: Int, formazioni f: Int) -> String {
        n == 1 ? "Media di 1 giornata, su \(formazioni(f))." : "Media delle ultime \(n) giornate, su \(formazioni(f))."
    }

    /// La riga sotto il titolo: su quante giornate e formazioni è la media, o che non c'è ancora nessuna giornata misurata.
    static func sottotitolo(_ c: StatoDati.Consiglio) -> String {
        let n = c.giornate ?? 0
        return n > 0 ? media(giornate: n, formazioni: c.voci ?? 0) : nessuna
    }

    static func nome(_ indicatore: Indicatore) -> String {
        switch indicatore {
        case .valore: return "Punti in più della consigliata rispetto alla scelta semplice"
        case .stabilita: return "Cambi della consigliata nelle 24 ore prima della scadenza"
        case .chiGioca: return "Titolari che rischiano di non giocare"
        case .perche: return "Scelte strane senza un motivo detto"
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
            let semplice = "\(punti(c.menoS2)) punti a giornata (deve stare a \(ParoleRegistro.cifra(s?.c1)) o più)"
            guard let schierata = c.menoSchierata else { return semplice }
            return semplice + " · \(punti(schierata)) rispetto alla formazione schierata, quando è diversa"
        case .stabilita:
            return "\(ParoleRegistro.cifra(c.cambi)) a formazione, in media · per meno di 1 punto atteso, senza un titolare diventato "
                + "fuori o improbabile: \(intero(c.cambiSottoSoglia)) (devono essere \(ParoleRegistro.cifra(s?.c2)))"
        case .chiGioca:
            return "sotto il 20% o fuori: \(intero(c.improbabili)) · con un compagno di ruolo al 50% o più tra gli esclusi: "
                + "\(intero(c.conCompagno)) (devono essere \(ParoleRegistro.cifra(s?.c3)))"
        case .perche:
            return "spiegate \(intero(c.spiegate)) su \(intero(c.storte)) (devono essere tutte) · titolari senza un motivo loro in "
                + "«Perché questo numero»: \(ParoleRegistro.percento(c.senzaMotivo)) (al massimo \(ParoleRegistro.percento(s?.c4SenzaMotivo)))"
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
