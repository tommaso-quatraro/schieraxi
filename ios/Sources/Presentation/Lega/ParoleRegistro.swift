import Foundation

/// Le parole del registro delle giornate in Stato dei dati (#344), uguali alla web: `cartaRegistro` di `fanta/web/app.js` e i testi
/// `sd.reg_*` di `fanta/web/testi.js` (`RegistroGiornateTests` li confronta). Soglie e verdetto («regge») arrivano dal server:
/// qui si scrivono e basta, non si ricalcolano.
enum ParoleRegistro {
    /// Le tre misure del registro, nell'ordine della web (sul server I1, I2, I3).
    enum Misura: CaseIterable {
        /// Errore del fantavoto atteso contro quello della fantamedia (I1).
        case fantavoto
        /// «Gioca N%» contro chi ha giocato davvero (I2).
        case gioca
        /// Punti veri dentro la fascia «8 volte su 10» (I3).
        case fascia
    }

    /// Accanto al nome della misura: regge, non regge, quante giornate servono ancora per dirlo, o nessun dato.
    enum Esito: Equatable {
        case regge
        case nonRegge
        case servono(Int)
        case senzaDati

        var testo: String {
            switch self {
            case .regge: return "regge"
            case .nonRegge: return "non regge"
            case .servono(let n): return n == 1 ? "serve ancora 1 giornata" : "servono ancora \(n) giornate"
            case .senzaDati: return "ancora nessun dato"
            }
        }
    }

    static let titolo = "Registro delle giornate"
    static let spiega = "Prima di ogni giornata l'app salva i numeri che mostra per tutta la Serie A e, a giornata finita, li confronta con com'è andata."
    static let nessuna = "Ancora nessuna giornata misurata: i numeri arrivano il giorno dopo la fine della prima giornata salvata."
    static let titoloPerse = "Giornate perse"
    static let spiegaPerse = "Non salvate prima della prima partita: non si possono più misurare."

    static func media(giornate n: Int) -> String {
        n == 1 ? "Media di 1 giornata misurata." : "Media delle ultime \(n) giornate misurate."
    }

    /// La riga sotto il titolo: su quante giornate è la media, o che non ce n'è ancora nessuna misurata.
    static func sottotitolo(_ r: StatoDati.Registro) -> String {
        let n = r.giornate ?? 0
        return n > 0 ? media(giornate: n) : nessuna
    }

    static func nome(_ misura: Misura) -> String {
        switch misura {
        case .fantavoto: return "Errore del fantavoto atteso contro la fantamedia"
        case .gioca: return "«Gioca N%» contro chi ha giocato davvero"
        case .fascia: return "Punti veri dentro la fascia «8 volte su 10»"
        }
    }

    static func esito(_ misura: Misura, di r: StatoDati.Registro) -> Esito {
        let regge: Bool?
        switch misura {
        case .fantavoto: regge = r.regge?.i1
        case .gioca: regge = r.regge?.i2
        case .fascia: regge = r.regge?.i3
        }
        return esito(verdetto: r.verdetto, regge: regge, giornate: r.giornate, finestra: r.finestra)
    }

    /// Senza verdetto (meno giornate della finestra) conta solo quante ne mancano; con il verdetto vale `regge` del server.
    static func esito(verdetto: Bool?, regge: Bool?, giornate: Int?, finestra: Int?) -> Esito {
        guard verdetto == true else {
            let tutte = finestra.flatMap { $0 > 0 ? $0 : nil } ?? 8
            return .servono(max(1, tutte - (giornate ?? 0)))
        }
        switch regge {
        case true?: return .regge
        case false?: return .nonRegge
        case nil: return .senzaDati
        }
    }

    /// Sotto il nome: la media e la soglia (più i due errori per il fantavoto, il punteggio di Brier per «gioca N%»).
    static func dettaglio(_ misura: Misura, di r: StatoDati.Registro) -> String {
        let s = r.soglie
        switch misura {
        case .fantavoto:
            return "\(percento(r.i1, segno: true)) (deve stare a \(percento(s?.i1, segno: true)) o meno) · errore "
                + "\(Formato.decimali(r.erroreModello, cifre: 2)) contro \(Formato.decimali(r.erroreFantamedia, cifre: 2))"
        case .gioca:
            return "scarto \(cifra(r.calibrazione, per: 100)) punti (al massimo \(cifra(s?.i2Calibrazione, per: 100))) · punteggio di Brier "
                + "\(Formato.decimali(r.brier, cifre: 3)) (al massimo \(Formato.decimali(s?.i2Brier, cifre: 3)))"
        case .fascia:
            return "\(percento(r.copertura)) (deve stare tra \(percento(s?.i3Minimo)) e \(percento(s?.i3Massimo)))"
        }
    }

    /// Le giornate non salvate in tempo, dalla più recente (come le manda il server).
    static func perse(_ r: StatoDati.Registro) -> [StatoDati.Registro.Giornata] {
        (r.perGiornata ?? []).filter { !($0.persa ?? "").isEmpty }
    }

    /// «9ª giornata di Serie A · 2026-27» (`sd.reg_giornata` della web): il numero è quello della Serie A, non della lega.
    static func giornata(_ g: StatoDati.Registro.Giornata) -> String {
        "\(g.giornata.map(TempiLega.serieA) ?? "") · \(g.stagione ?? "")"
    }

    /// Un numero (moltiplicato per `per`) con una cifra decimale e senza «,0», come `regCifra` della web: «10», «3,4», «−3».
    static func cifra(_ x: Double?, per: Double = 1, segno: Bool = false) -> String {
        guard let x, x.isFinite else { return "–" }
        let testo = segno ? Formato.conSegno(x * per, cifre: 1) : Formato.decimali(x * per, cifre: 1)
        return testo.hasSuffix(",0") ? String(testo.dropLast(2)) : testo
    }

    /// Una quota come percentuale, come `regPerc` della web: 0,057 → «5,7%», −0,03 con il segno → «−3%».
    static func percento(_ x: Double?, segno: Bool = false) -> String {
        let testo = cifra(x, per: 100, segno: segno)
        return testo == "–" ? testo : testo + "%"
    }
}
