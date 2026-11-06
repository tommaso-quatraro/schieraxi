import Foundation

/// Le parole dei gol attesi «nostri» (senza Understat) in Stato dei dati (#401), uguali alla web: `cartaNostri` di `fanta/web/app.js`
/// e i testi `sd.nos_*` di `fanta/web/testi.js` (`GolAttesiNostriTests` li confronta). Soglie e verdetto (`regge`, `regge_tutto`)
/// arrivano dal server: qui si scrivono e basta, non si ricalcolano. Per chi legge ci sono le parole, mai la sigla I4.
enum ParoleNostri {
    /// Le tre misure, nell'ordine della web.
    enum Misura: CaseIterable {
        /// Errore del fantavoto atteso dei numeri nostri contro quello dei numeri mostrati.
        case errore
        /// Punti veri della formazione migliore con i numeri nostri contro quella con i mostrati, sulle rose estratte a sorte.
        case punti
        /// Gol attesi contro gol veri, per fasce di gol attesi.
        case gol
    }

    static let titolo = "Gol attesi nostri (senza Understat)"
    static let spiega = "Prima di ogni giornata l'app salva anche i numeri calcolati solo con i voti di Fantacalcio.it e, a giornata "
        + "finita, li confronta con quelli mostrati. Se le tre misure reggono per 8 giornate, si può fare a meno di Understat."
    static let insieme = "Le tre misure insieme"
    static let perGiornata = "Giornata per giornata"
    static let vuota = "misurata, ma senza giocatori da confrontare"

    static func media(giornate n: Int, versione v: String) -> String {
        n == 1 ? "Media di 1 giornata misurata, versione \(v) del calcolo."
            : "Media delle ultime \(n) giornate misurate, versione \(v) del calcolo."
    }

    /// Come la carta del registro: la versione del calcolo non si scrive (filtra soltanto le giornate che contano).
    static let nessuna = "Ancora nessuna giornata misurata: i numeri arrivano il giorno dopo la fine della prima giornata salvata."

    /// La riga sotto il titolo: su quante giornate (della versione di oggi) è la media, o che non ce n'è ancora nessuna misurata.
    static func sottotitolo(_ n: StatoDati.RegistroNostri) -> String {
        let k = n.giornate ?? 0
        let v = n.versione ?? "–"
        return k > 0 ? media(giornate: k, versione: v) : nessuna
    }

    static func nome(_ misura: Misura) -> String {
        switch misura {
        case .errore: return "Errore del fantavoto atteso contro i numeri mostrati"
        case .punti: return "Punti veri della formazione migliore contro i numeri mostrati"
        case .gol: return "Gol attesi contro gol veri, per fasce"
        }
    }

    /// Le tre misure insieme: senza verdetto quante giornate mancano; con il verdetto «reggono» solo se il server dice che reggono
    /// tutte e tre (`regge_tutto`), altrimenti «non reggono».
    static func esitoInsieme(_ n: StatoDati.RegistroNostri) -> ParoleRegistro.Esito {
        guard n.verdetto == true else {
            return ParoleRegistro.esito(verdetto: n.verdetto, regge: nil, giornate: n.giornate, finestra: n.finestra)
        }
        return n.reggeTutto == true ? .regge : .nonRegge
    }

    /// Il verdetto delle tre misure insieme a parole, al plurale: «reggono», «non reggono», «servono ancora N giornate».
    static func testoInsieme(_ esito: ParoleRegistro.Esito) -> String {
        switch esito {
        case .regge: return "reggono"
        case .nonRegge: return "non reggono"
        case .servono, .senzaDati: return esito.testo
        }
    }

    /// Senza verdetto (meno giornate della finestra) conta solo quante ne mancano; con il verdetto vale `regge` del server.
    static func esito(_ misura: Misura, di n: StatoDati.RegistroNostri) -> ParoleRegistro.Esito {
        let regge: Bool?
        switch misura {
        case .errore: regge = n.regge?.errore
        case .punti: regge = n.regge?.punti
        case .gol: regge = n.regge?.gol
        }
        return ParoleRegistro.esito(verdetto: n.verdetto, regge: regge, giornate: n.giornate, finestra: n.finestra)
    }

    /// Sotto il nome: la media e la soglia (per i gol anche gol attesi su veri, con i numeri nostri e con i mostrati).
    static func dettaglio(_ misura: Misura, di n: StatoDati.RegistroNostri) -> String {
        let s = n.soglie
        switch misura {
        case .errore:
            return "\(ParoleRegistro.percento(n.errorePct, segno: true)) (deve stare a \(ParoleRegistro.percento(s?.errore, segno: true)) o meno)"
        case .punti:
            return "\(punti(n.punti)) punti a rosa e giornata (deve stare a \(ParoleRegistro.cifra(s?.punti, segno: true)) o più)"
        case .gol:
            return "scarto più grande \(Formato.decimali(n.scartoGol, cifre: 3)) gol a giocatore (al massimo "
                + "\(Formato.decimali(s?.scartoGol, cifre: 3))) · gol attesi su veri \(Formato.decimali(n.golSuVeri, cifre: 2)), "
                + "con i numeri mostrati \(Formato.decimali(n.golSuVeriMostrati, cifre: 2))"
        }
    }

    /// «9ª giornata di Serie A · 2026-27» (`sd.reg_giornata` della web): il numero è quello della Serie A, non della lega, come il
    /// registro delle giornate (`ParoleRegistro.giornata`).
    static func giornata(_ g: StatoDati.RegistroNostri.Giornata) -> String {
        "\(g.giornata.map(TempiLega.serieA) ?? "") · \(g.stagione ?? "")"
    }

    /// Vero se la giornata è persa: i numeri nostri non salvati in tempo, o la misura non riuscita (il motivo lo scrive il server).
    static func persa(_ g: StatoDati.RegistroNostri.Giornata) -> Bool {
        !(g.persa ?? "").isEmpty
    }

    static func daMisurare(giocatori n: Int) -> String {
        "salvati i numeri di \(Formato.plurale(n, "giocatore", "giocatori")), da misurare a giornata finita"
    }

    /// Sotto una giornata: il motivo se è persa, quanti giocatori sono salvati se non è ancora misurata, altrimenti i suoi tre numeri.
    /// Una giornata di un'altra versione del calcolo non conta nel verdetto, e lo dice.
    static func stato(_ g: StatoDati.RegistroNostri.Giornata, versione: String?) -> String {
        if let motivo = g.persa, !motivo.isEmpty { return motivo }
        let testo: String
        if g.misurato == nil {
            testo = daMisurare(giocatori: g.giocatori ?? 0)
        } else if (g.voti ?? 0) > 0 {
            testo = "errore \(ParoleRegistro.percento(g.errorePct, segno: true)) · punti \(punti(g.punti)) · gol attesi su veri "
                + Formato.decimali(g.golSuVeri, cifre: 2)
        } else {
            testo = vuota
        }
        guard let sua = g.versione, let oggi = versione, sua != oggi else { return testo }
        return testo + " · versione \(sua), non conta"
    }

    /// Punti con due cifre e il segno, come `segno(x, 2)` della web: «+0,25», «−0,10», «0,00»; «–» se manca.
    static func punti(_ x: Double?) -> String {
        guard let x, x.isFinite else { return "–" }
        return Formato.conSegno(x, cifre: 2)
    }
}
