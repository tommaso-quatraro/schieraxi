import Foundation

/// Le parole dei gol attesi «nostri» (senza Understat) in Stato dei dati (#401), uguali alla web: `cartaNostri` di `fanta/web/app.js`
/// e i testi `sd.nos_*` del catalogo comune (`Catalogo+Sd.swift`; `GolAttesiNostriTests` prova le frasi composte). Soglie e verdetto (`regge`, `regge_tutto`)
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

    static let titolo = Catalogo.Sd.nosTitolo
    static let spiega = Catalogo.Sd.nosSpiega
    static let insieme = Catalogo.Sd.nosInsieme
    static let perGiornata = Catalogo.Sd.nosPerGiornata
    static let vuota = Catalogo.Sd.nosGVuota

    static func media(giornate n: Int, versione v: String) -> String { Catalogo.Sd.nosMedia(n, v: v) }

    /// Come la carta del registro: la versione del calcolo non si scrive (filtra soltanto le giornate che contano).
    static let nessuna = Catalogo.Sd.nosNessuna

    /// La riga sotto il titolo: su quante giornate (della versione di oggi) è la media, o che non ce n'è ancora nessuna misurata.
    static func sottotitolo(_ n: StatoDati.RegistroNostri) -> String {
        let k = n.giornate ?? 0
        let v = n.versione ?? "–"
        return k > 0 ? media(giornate: k, versione: v) : nessuna
    }

    static func nome(_ misura: Misura) -> String {
        switch misura {
        case .errore: return Catalogo.Sd.nosErrore
        case .punti: return Catalogo.Sd.nosPunti
        case .gol: return Catalogo.Sd.nosGol
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
        case .regge: return Catalogo.Sd.nosReggono
        case .nonRegge: return Catalogo.Sd.nosNonReggono
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
            return Catalogo.Sd.nosErroreRiga(s: ParoleRegistro.percento(s?.errore, segno: true), v: ParoleRegistro.percento(n.errorePct, segno: true))
        case .punti:
            return Catalogo.Sd.nosPuntiRiga(s: ParoleRegistro.cifra(s?.punti, segno: true), v: punti(n.punti))
        case .gol:
            return Catalogo.Sd.nosGolRiga(g: Formato.decimali(n.golSuVeri, cifre: 2), m: Formato.decimali(n.golSuVeriMostrati, cifre: 2),
                                          s: Formato.decimali(s?.scartoGol, cifre: 3), v: Formato.decimali(n.scartoGol, cifre: 3))
        }
    }

    /// «9ª giornata di Serie A · 2026-27» (`sd.reg_giornata` della web): il numero è quello della Serie A, non della lega, come il
    /// registro delle giornate (`ParoleRegistro.giornata`).
    static func giornata(_ g: StatoDati.RegistroNostri.Giornata) -> String {
        Catalogo.Sd.regGiornata(g: g.giornata.map(TempiLega.serieA) ?? "", s: g.stagione ?? "")
    }

    /// Vero se la giornata è persa: i numeri nostri non salvati in tempo, o la misura non riuscita (il motivo lo scrive il server).
    static func persa(_ g: StatoDati.RegistroNostri.Giornata) -> Bool {
        !(g.persa ?? "").isEmpty
    }

    static func daMisurare(giocatori n: Int) -> String { Catalogo.Sd.nosGDaMisurare(n) }

    /// Sotto una giornata: il motivo se è persa, quanti giocatori sono salvati se non è ancora misurata, altrimenti i suoi tre numeri.
    /// Una giornata di un'altra versione del calcolo non conta nel verdetto, e lo dice.
    static func stato(_ g: StatoDati.RegistroNostri.Giornata, versione: String?) -> String {
        if let motivo = g.persa, !motivo.isEmpty { return motivo }
        let testo: String
        if g.misurato == nil {
            testo = daMisurare(giocatori: g.giocatori ?? 0)
        } else if (g.voti ?? 0) > 0 {
            testo = Catalogo.Sd.nosGMisurata(e: ParoleRegistro.percento(g.errorePct, segno: true), g: Formato.decimali(g.golSuVeri, cifre: 2),
                                             p: punti(g.punti))
        } else {
            testo = vuota
        }
        guard let sua = g.versione, let oggi = versione, sua != oggi else { return testo }
        return testo + " · " + Catalogo.Sd.nosGVersione(v: sua)
    }

    /// Punti con due cifre e il segno, come `segno(x, 2)` della web: «+0,25», «−0,10», «0,00»; «–» se manca.
    static func punti(_ x: Double?) -> String {
        guard let x, x.isFinite else { return "–" }
        return Formato.conSegno(x, cifre: 2)
    }
}
